"""FastAPI app: serves the dashboard HTML pages and JSON API."""

import json
import logging
import threading
import datetime as dt
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from starlette.requests import Request

from nifty_gap.backtest.engine import Trade
from nifty_gap.config import Config
from nifty_gap.data.loader import seed_history
from nifty_gap.web.snapshot import OUTPUT_DIR, build_snapshot_and_charts, generate_snapshot
from nifty_gap.web.state import (
    compute_live_positions,
    compute_premium_series,
    load_history_df,
)

logger = logging.getLogger("nifty_gap.web")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
SNAPSHOT_PATH = OUTPUT_DIR / "dashboard.json"

# Module-level snapshot — loaded lazily at startup (never at import time).
snapshot: dict = {}

# Guards concurrent readers/writers of the global snapshot.
_snapshot_lock = threading.Lock()

# Last-served recompute seq — stale requests (older seq) are dropped early
# so superseded recomputes don't burn CPU server-side. Single user.
_recompute_seq = 0

# Serializes /api/refresh so concurrent clicks don't double-fetch/double-write.
_refresh_lock = threading.Lock()

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_snapshot() -> dict:
    """Build snapshot once, lazily, with logging — never at import time."""
    if SNAPSHOT_PATH.exists():
        try:
            return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("stored snapshot unreadable; regenerating")
    try:
        snap = generate_snapshot()
        logger.info("snapshot generated: %d trades", len(snap.get("trades", [])))
        return snap
    except Exception:
        logger.exception("snapshot generation failed (data missing?)")
        return {}


def _ensure_snapshot() -> dict:
    """Return the current snapshot, loading/generating it on first use.

    Guards the lazy path so requests work even when lifespan was skipped
    (e.g. bare TestClient); regenerates only when no snapshot exists yet.
    """
    global snapshot
    if snapshot:
        return snapshot
    with _snapshot_lock:
        if not snapshot:
            snapshot = _load_snapshot()
        return snapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed history, load/generate the snapshot, then refresh charts best-effort."""
    global snapshot
    try:
        cfg = Config()
        seed_history(cfg.data_history_path, cfg.data_path)
    except Exception:
        logger.exception("history seeding failed")
    snapshot = _load_snapshot()
    try:
        from nifty_gap.web.snapshot import render_report_pngs

        expected = [
            OUTPUT_DIR / name
            for name in ("equity.png", "benchmark.png", "exit_reasons.png", "probability.png", "oos.png")
        ]
        if not all(p.exists() for p in expected):
            render_report_pngs()
            logger.info("report PNGs regenerated")
    except Exception:
        logger.warning("report PNG regeneration skipped", exc_info=True)
    yield


app = FastAPI(title="NIFTY Gap Dashboard", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/charts", StaticFiles(directory=str(OUTPUT_DIR)), name="charts")


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    logger.exception("unhandled error on %s: %s", request.url.path, exc)
    return HTMLResponse("Internal Server Error", status_code=500)


# Embedding allow-list: same origin + the portfolio site. Modern browsers use
# CSP frame-ancestors; X-Frame-Options is omitted because it has no supported
# cross-origin allow-list syntax (ALLOW-FROM was never standardised).
_FRAME_ANCESTORS = "'self' https://sourabh08.vercel.app"


@app.middleware("http")
async def _set_frame_ancestors(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = f"frame-ancestors {_FRAME_ANCESTORS}"
    return response

# 60s in-memory spot cache (single user, no Redis)
_spot_cache: dict = {"value": None, "ts": 0.0}
_SPOT_CACHE_TTL = 60


class RecomputeRequest(BaseModel):
    seq: int | None = Field(default=None, ge=0)
    iv_flat: float | None = Field(default=None, gt=0, le=1)
    ladder_stop_pcts: list[float] | None = None
    ladder_floor_pcts: list[float] | None = None
    ladder_rollover: bool | None = None
    excluded_pairs: list[str] | None = None
    brokerage_per_trade: float = Field(default=0.0, ge=0)
    slippage_pct: float = Field(default=0.0, ge=0, lt=1)

    @field_validator("ladder_stop_pcts")
    @classmethod
    def _two_stops(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("ladder_stop_pcts must have exactly 2 entries")
        return v

    @field_validator("ladder_floor_pcts")
    @classmethod
    def _three_floors(cls, v):
        if v is not None and len(v) != 3:
            raise ValueError("ladder_floor_pcts must have exactly 3 entries")
        return v


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "favicon.ico"))


def _degraded() -> HTMLResponse:
    """503 page shown when the snapshot/data is unavailable."""
    return HTMLResponse(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>NIFTY Gap Dashboard</title></head>"
        "<body style='font-family:system-ui;max-width:640px;margin:48px auto;padding:0 24px'>"
        "<h1>Data is not available yet</h1>"
        "<p>The dashboard snapshot could not be generated (market data may be missing). "
        "Please try again shortly.</p>"
        "</body></html>",
        status_code=503,
    )


def _fetch_spot() -> dict:
    now = time.monotonic()
    if _spot_cache["value"] is not None and now - _spot_cache["ts"] < _SPOT_CACHE_TTL:
        return _spot_cache["value"]
    spot = None
    source = "history"
    try:
        import yfinance as yf

        last = yf.Ticker("^NSEI").fast_info.last_price
        if last:
            spot = float(last)
            source = "yfinance"
    except Exception:
        logger.debug("yfinance spot fetch failed", exc_info=True)
    if spot is None:
        try:
            df = load_history_df()
            spot = float(df["Close"].iloc[-1])
        except Exception:
            logger.warning("spot fallback failed", exc_info=True)
    if spot is not None:
        _spot_cache["value"] = {"spot": spot, "source": source, "as_of": dt.datetime.now(dt.timezone.utc).isoformat()}
        _spot_cache["ts"] = now
        return _spot_cache["value"]
    return {"spot": None, "source": "unavailable", "as_of": dt.datetime.now(dt.timezone.utc).isoformat()}


def _clean_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _trade_from_dict(t: dict) -> Trade:
    return Trade(
        entry_date=pd.Timestamp(t["entry_date"]).normalize(),
        exit_date=pd.Timestamp(t["exit_date"]).normalize(),
        pair=t["pair"],
        side=t["side"],
        strike=t["strike"],
        entry_close=t["entry_close"],
        expiry=pd.Timestamp(t["expiry"]).normalize(),
        entry_premium=_clean_float(t["entry_premium"]),
        exit_premium=_clean_float(t["exit_premium"]),
        exit_reason=t["exit_reason"],
        days_held=t["days_held"],
        pnl=_clean_float(t["pnl"]),
        rolls=_clean_float(t.get("rolls", 0)),
        legs=tuple(t.get("legs") or ()),
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def api_dashboard() -> dict:
    return _ensure_snapshot()


@app.post("/api/recompute")
def api_recompute(body: RecomputeRequest) -> dict:
    from dataclasses import replace

    global snapshot, _recompute_seq
    if body.seq is not None:
        if body.seq < _recompute_seq:
            return snapshot
        _recompute_seq = body.seq

    cfg = Config()
    kwargs = {}
    if body.iv_flat is not None:
        kwargs["iv_flat"] = body.iv_flat
    if body.ladder_stop_pcts is not None:
        kwargs["ladder_stop_pcts"] = tuple(body.ladder_stop_pcts)
    if body.ladder_floor_pcts is not None:
        kwargs["ladder_floor_pcts"] = tuple(body.ladder_floor_pcts)
    if body.ladder_rollover is not None:
        kwargs["ladder_rollover"] = body.ladder_rollover
    if body.excluded_pairs is not None:
        kwargs["excluded_pairs"] = frozenset(body.excluded_pairs)
    cfg = replace(cfg, **kwargs)
    try:
        new_snap = build_snapshot_and_charts(cfg, body.brokerage_per_trade, body.slippage_pct)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid recompute parameters: {exc}") from exc
    with _snapshot_lock:
        if body.seq is not None and body.seq < _recompute_seq:
            return snapshot  # stale result — superseded while building
        snapshot = new_snap
    return new_snap


@app.post("/api/refresh")
def api_refresh() -> dict:
    from nifty_gap.data.refresh import run_refresh

    global snapshot
    if not _refresh_lock.acquire(blocking=False):
        return {"status": "busy", "rows_added": 0, "provider": None, "reason": "refresh already in progress"}
    try:
        cfg = Config()
        result = run_refresh(cfg.data_history_path, cfg.data_path)
        if result["status"] != "warn":
            with _snapshot_lock:
                snapshot = generate_snapshot(cfg)
        return result
    except Exception as exc:
        logger.exception("data refresh failed")
        raise HTTPException(status_code=500, detail=f"refresh failed: {exc}") from exc
    finally:
        _refresh_lock.release()


@app.get("/api/spot")
def api_spot() -> dict:
    return _fetch_spot()


@app.get("/api/live-positions")
def api_live_positions(spot: float | None = None) -> list:
    if spot is None:
        spot = _fetch_spot()["spot"]
    if not spot or spot <= 0:
        raise HTTPException(status_code=400, detail="spot must be a positive number")
    snap = _ensure_snapshot()
    with _snapshot_lock:
        trades = [_trade_from_dict(t) for t in snap["trades"]]
    return compute_live_positions(trades, spot)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snap = _ensure_snapshot()
    if not snap:
        return _degraded()
    today = dt.date.today()
    last_trading = dt.date.fromisoformat(snap["last_trading_date"])
    age = (today - last_trading).days
    if age <= 1:
        badge = ("fresh", "Data current")
    elif age <= 5:
        badge = ("stale", f"{age}d stale")
    else:
        badge = ("stale-red", f"{age}d old")
    ctx = {
        "request": request,
        "snap": snap,
        "spot": _fetch_spot(),
        "badge_class": badge[0],
        "badge_text": badge[1],
    }
    return templates.TemplateResponse("dashboard.html", ctx)


@app.get("/trade/{entry_date}", response_class=HTMLResponse)
def trade_detail(entry_date: str, request: Request) -> HTMLResponse:
    snap = _ensure_snapshot()
    if not snap:
        return _degraded()
    match = [t for t in snap["trades"] if t["entry_date"] == entry_date]
    if not match:
        raise HTTPException(status_code=404, detail="trade not found")
    df = load_history_df()
    series = compute_premium_series(df, _trade_from_dict(match[0]))
    ctx = {"request": request, "trade": match[0], "premium_series": series, "spot": _fetch_spot(), "snap": snap}
    return templates.TemplateResponse("trade.html", ctx)


@app.get("/expiry", response_class=HTMLResponse)
def expiry(request: Request) -> HTMLResponse:
    snap = _ensure_snapshot()
    if not snap:
        return _degraded()
    ctx = {"request": request, "snap": snap, "spot": _fetch_spot()}
    return templates.TemplateResponse("expiry.html", ctx)


@app.get("/methodology", response_class=HTMLResponse)
def methodology(request: Request) -> HTMLResponse:
    snap = _ensure_snapshot()
    if not snap:
        return _degraded()
    ctx = {"request": request, "snap": snap, "spot": _fetch_spot()}
    return templates.TemplateResponse("methodology.html", ctx)