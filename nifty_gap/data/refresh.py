"""NIFTY 50 data refresh pipeline: Yahoo Finance primary, NSE API opt-in."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import time

import pandas as pd

from nifty_gap.config import Config
from nifty_gap.data.loader import seed_history, write_history
from nifty_gap.data.validation import validate_integrity

logger = logging.getLogger(__name__)

_NSE_RETRY_SLEEP = 1.5

OUTPUT_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr", "data_source"]

OUTPUT_DTYPES = {
    "Date": "datetime64[ns]",
    "Open": "float64",
    "High": "float64",
    "Low": "float64",
    "Close": "float64",
    "Shares_Traded": "Int64",
    "Turnover_Cr": "float64",
    "data_source": "object",
}

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in OUTPUT_DTYPES.items()})


def normalise_yfinance(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None:
        raw = pd.DataFrame()
    if isinstance(getattr(raw, "columns", None), pd.MultiIndex):
        raw = raw.copy()
        raw.columns = raw.columns.get_level_values(0)
    keep = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in raw.columns for col in keep):
        return _empty_output()
    raw = raw[keep].copy()
    raw = raw[raw["Volume"].notna() & (raw["Volume"] != 0)]
    idx = raw.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(IST).tz_localize(None)
    return pd.DataFrame(
        {
            "Date": pd.DatetimeIndex(idx).normalize(),
            # Round to NSE's 2-dp convention — yfinance floats carry
            # float32 transport artifacts (e.g. 24284.05078125).
            "Open": raw["Open"].astype("float64").round(2).to_numpy(),
            "High": raw["High"].astype("float64").round(2).to_numpy(),
            "Low": raw["Low"].astype("float64").round(2).to_numpy(),
            "Close": raw["Close"].astype("float64").round(2).to_numpy(),
            "Shares_Traded": pd.array([pd.NA] * len(raw), dtype="Int64"),
            "Turnover_Cr": pd.Series([float("nan")] * len(raw), dtype="float64").to_numpy(),
            "data_source": pd.Series(["yfinance"] * len(raw)).to_numpy(),
        }
    )


def fetch_yfinance(start: dt.date, end: dt.date) -> pd.DataFrame:
    try:
        import yfinance as yf

        raw = yf.download(
            "^NSEI",
            start=start,
            end=end + dt.timedelta(days=1),
            auto_adjust=False,
            threads=False,
            progress=False,
        )
        return normalise_yfinance(raw)
    except Exception:
        return _empty_output()


def _nse_session(timeout: float = 20):
    from curl_cffi import requests as cffi

    session = cffi.Session(impersonate="chrome124", timeout=timeout)
    session.headers.update({"Accept-Language": "en-US,en;q=0.9"})
    return session


def fetch_nse(from_date: dt.date, to_date: dt.date, requests_timeout: float = 20) -> pd.DataFrame | None:
    """Best-effort NSE direct fetch. Usually fails from server IPs: the
    historical API sits behind Akamai Bot Manager, whose ``_abck`` sensor
    challenge cannot be solved without a real browser. Failures are logged
    with a reason and returned as ``None`` so callers can fall back."""
    session = _nse_session(requests_timeout)
    home_url = "https://www.nseindia.com"
    reports_url = "https://www.nseindia.com/reports-indices-historical-index-data"
    api_url = "https://www.nseindia.com/api/historical/indicesHistory"
    params = {
        "indexType": "NIFTY 50",
        "from": from_date.strftime("%d-%m-%Y"),
        "to": to_date.strftime("%d-%m-%Y"),
    }

    def _attempt() -> tuple[pd.DataFrame | None, str | None]:
        res = session.get(home_url)
        if res.status_code != 200:
            return None, f"homepage returned {res.status_code}"
        res = session.get(reports_url)
        if res.status_code != 200:
            return None, f"reports page returned {res.status_code}"
        time.sleep(2.0)
        res = session.get(api_url, params=params, headers={"Referer": reports_url})
        if res.status_code != 200:
            return None, f"api returned {res.status_code}"
        items = res.json().get("indexHistoricalData") or []
        records = [
            {
                "Date": pd.to_datetime(item["TIMESTAMP"], format="%d-%b-%Y"),
                "Open": float(item["OPEN"]),
                "High": float(item["HIGH"]),
                "Low": float(item["LOW"]),
                "Close": float(item["CLOSE"]),
                "Shares_Traded": item["SHARES_TRADED"],
                "Turnover_Cr": float(item["TURNOVER"]),
                "data_source": "nse",
            }
            for item in items
        ]
        df = pd.DataFrame(records)
        if df.empty:
            return _empty_output(), None
        df["Shares_Traded"] = df["Shares_Traded"].astype("Int64")
        df["Turnover_Cr"] = df["Turnover_Cr"].astype("float64")
        return df.sort_values("Date").reset_index(drop=True), None

    reason = "unknown"
    for attempt in (1, 2):
        try:
            df, reason = _attempt()
        except Exception as exc:
            df, reason = None, f"{type(exc).__name__}: {exc}"
        if df is not None:
            return df
        if attempt == 1:
            time.sleep(_NSE_RETRY_SLEEP)
    logger.warning("NSE direct fetch failed (%s .. %s): %s", from_date, to_date, reason)
    return None


def upsert(history: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([history, new], ignore_index=True)
    merged = merged.drop_duplicates(subset="Date", keep="first")
    return merged.sort_values("Date").reset_index(drop=True)


BOOTSTRAP_WINDOW_DAYS = 400


def run_refresh(
    history_path,
    seed_path,
    provider_order: tuple[str, ...] | None = None,
    backfill_from: dt.date | None = None,
    to_date: dt.date | None = None,
    dry_run: bool = False,
) -> dict:
    if provider_order is None:
        raw = os.getenv("REFRESH_PROVIDER_ORDER", "")
        provider_order = tuple(p.strip().lower() for p in raw.split(",") if p.strip()) or ("yfinance",)
    history = seed_history(history_path, seed_path)
    if history is None:
        end = to_date or dt.date.today()
        bootstrap = fetch_yfinance(end - dt.timedelta(days=BOOTSTRAP_WINDOW_DAYS), end)
        if bootstrap.empty:
            return {
                "status": "warn",
                "rows_added": 0,
                "provider": None,
                "reason": "no history/seed available; yfinance bootstrap empty",
            }
        history = bootstrap
        if not dry_run:
            write_history(history_path, history)
        validate_integrity(history)
        return {"status": "ok", "rows_added": len(history), "provider": "yfinance", "reason": "bootstrap"}
    validate_integrity(history)
    latest = history["Date"].max().date()
    start = backfill_from or latest + dt.timedelta(days=1)
    end = to_date or dt.date.today()
    if start > end:
        return {"status": "noop", "rows_added": 0, "provider": None}
    merged = history
    used = None
    for provider in provider_order:
        if provider == "nse":
            candidate = fetch_nse(start, end)
            if candidate is None or candidate.empty:
                continue
        else:
            candidate = fetch_yfinance(start, end)
            if candidate is None or candidate.empty:
                continue
        validate_integrity(candidate)
        merged = upsert(history, candidate)
        used = provider
        break
    if used is None:
        return {"status": "warn", "rows_added": 0, "provider": None, "reason": "all providers failed"}
    if not dry_run and len(merged) > len(history):
        write_history(history_path, merged)
    return {
        "status": "ok",
        "rows_added": len(merged) - len(history),
        "provider": used,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh NIFTY 50 history data (idempotent).")
    parser.add_argument("command", nargs="?", choices=["refresh"], default="refresh", help="command (default: refresh)")
    parser.add_argument("--backfill", type=dt.date.fromisoformat, default=None, help="start date YYYY-MM-DD")
    parser.add_argument("--to", type=dt.date.fromisoformat, default=dt.date.today(), help="end date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="validate without writing")
    args = parser.parse_args(argv)
    cfg = Config()
    result = run_refresh(
        cfg.data_history_path,
        cfg.data_path,
        backfill_from=args.backfill,
        to_date=args.to,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())