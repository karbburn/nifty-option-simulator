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
from starlette.requests import Request

from nifty_gap.backtest.engine import Trade
from nifty_gap.web.snapshot import OUTPUT_DIR, generate_snapshot
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

# 60s in-memory spot cache (single user, no Redis)
_spot_cache: dict = {"value": None, "ts": 0.0}
_SPOT_CACHE_TTL = 60


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "favicon.ico"))


@app.on_event("startup")
def _seed_snapshot() -> None:
    """Ensure snapshot exists; no-op if already seeded above."""
    if not SNAPSHOT_PATH.exists():
        generate_snapshot()
    import json

    global snapshot
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