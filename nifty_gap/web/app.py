"""FastAPI app: serves the dashboard HTML pages and JSON API."""

import json
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from nifty_gap.backtest.engine import Trade
from nifty_gap.config import Config
from nifty_gap.web.snapshot import OUTPUT_DIR, build_snapshot_and_charts, generate_snapshot
from nifty_gap.web.state import (
    compute_live_positions,
    compute_premium_series,
    load_history_df,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
SNAPSHOT_PATH = OUTPUT_DIR / "dashboard.json"

# Module-level snapshot — populated once at import
snapshot: dict = {}

if not SNAPSHOT_PATH.exists():
    generate_snapshot()
snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="NIFTY Gap Dashboard")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/charts", StaticFiles(directory=str(OUTPUT_DIR)), name="charts")

# 60s in-memory spot cache (single user, no Redis)
_spot_cache: dict = {"value": None, "ts": 0.0}
_SPOT_CACHE_TTL = 60


class RecomputeRequest(BaseModel):
    seq: int | None = None
    iv_flat: float | None = None
    ladder_stop_pcts: list[float] | None = None
    ladder_floor_pcts: list[float] | None = None
    ladder_rollover: bool | None = None
    excluded_pairs: list[str] | None = None
    brokerage_per_trade: float = 0.0
    slippage_pct: float = 0.0


# Last-served recompute seq — stale requests (older seq) are dropped early
# so superseded recomputes don't burn CPU server-side. Single user, no lock.
_recompute_seq = 0


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "favicon.ico"))


@app.on_event("startup")
def _seed_snapshot() -> None:
    """Ensure snapshot + report charts exist; no-op if already seeded above."""
    import json

    global snapshot
    if not SNAPSHOT_PATH.exists():
        generate_snapshot()
    from nifty_gap.web.snapshot import render_report_pngs

    expected = [OUTPUT_DIR / name for name in ("equity.png", "benchmark.png", "exit_reasons.png", "probability.png", "oos.png")]
    if not all(p.exists() for p in expected):
        render_report_pngs()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _fetch_spot() -> dict:
    now = time.monotonic()
    if _spot_cache["value"] is not None and now - _spot_cache["ts"] < _SPOT_CACHE_TTL:
        return _spot_cache["value"]
    spot = None
    source = "history"
    try:
        last = yf.Ticker("^NSEI").fast_info.last_price
        if last:
            spot = float(last)
            source = "yfinance"
    except Exception:
        pass
    if spot is None:
        df = load_history_df()
        spot = float(df["Close"].iloc[-1])
    data = {"spot": spot, "source": source, "as_of": dt.datetime.now(dt.timezone.utc).isoformat()}
    _spot_cache["value"] = data
    _spot_cache["ts"] = now
    return data


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
    return snapshot


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
    snapshot = build_snapshot_and_charts(cfg, body.brokerage_per_trade, body.slippage_pct)
    return snapshot


@app.post("/api/refresh")
def api_refresh() -> dict:
    from nifty_gap.data.refresh import run_refresh

    cfg = Config()
    result = run_refresh(cfg.data_history_path, cfg.data_path)
    if result["status"] != "warn":
        global snapshot
        snapshot = generate_snapshot(cfg)
    return result


@app.get("/api/spot")
def api_spot() -> dict:
    return _fetch_spot()


@app.get("/api/live-positions")
def api_live_positions(spot: float | None = None) -> list:
    if spot is None:
        spot = _fetch_spot()["spot"]
    trades = [_trade_from_dict(t) for t in snapshot["trades"]]
    return compute_live_positions(trades, spot)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snap = snapshot
    today = dt.date.today()
    last_trading = dt.date.fromisoformat(snap["last_trading_date"])
    age = (today - last_trading).days
    if age <= 1:
        badge = ("fresh", "● Data current")
    elif age <= 5:
        badge = ("stale", f"● {age}d stale")
    else:
        badge = ("stale-red", f"● {age}d old")
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
    snap = snapshot
    match = [t for t in snapshot["trades"] if t["entry_date"] == entry_date]
    if not match:
        raise HTTPException(status_code=404, detail="trade not found")
    df = load_history_df()
    series = compute_premium_series(df, _trade_from_dict(match[0]))
    ctx = {"request": request, "trade": match[0], "premium_series": series, "spot": _fetch_spot(), "snap": snap}
    return templates.TemplateResponse("trade.html", ctx)


@app.get("/expiry", response_class=HTMLResponse)
def expiry(request: Request) -> HTMLResponse:
    ctx = {"request": request, "snap": snapshot, "spot": _fetch_spot()}
    return templates.TemplateResponse("expiry.html", ctx)