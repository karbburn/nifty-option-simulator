"""Audit our history against the official NSE report (frozen fixture).

The fixture ``data/NIFTY 50-22-08-2025-to-22-08-2026.csv`` is the exchange's
own export covering 22-Aug-2025 .. 21-Aug-2026. If these tests fail, either a
trading session went missing from ``data/nifty50_history.csv`` or a value was
revised -- investigate before shipping. Deliberately strict: the fixture never
changes, so any drift in the pipeline turns red here first.
"""

import csv
import io
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REPORT_PATH = DATA_DIR / "NIFTY 50-22-08-2025-to-22-08-2026.csv"
HISTORY_PATH = DATA_DIR / "nifty50_history.csv"

# One paisa of slack: history stores rounded floats, the report integers-as-floats.
TOLERANCE = 0.011


def _load_nse_report() -> dict:
    out = {}
    with io.open(REPORT_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # The official export pads header names: "Date ", "Open ", ...
        reader.fieldnames = [k.strip() for k in reader.fieldnames]
        for r in reader:
            d = datetime.strptime(r["Date"].strip(), "%d-%b-%Y").date()
            out[d] = {k: float(r[k]) for k in ("Open", "High", "Low", "Close")}
    return out


def _load_history() -> dict:
    out = {}
    with io.open(HISTORY_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = datetime.strptime(r["Date"].strip(), "%d-%b-%Y").date()
            out[d] = {k: round(float(r[k]), 2) for k in ("Open", "High", "Low", "Close")}
    return out


def test_history_covers_every_weekday_session_in_nse_report():
    nse, hist = _load_nse_report(), _load_history()
    missing = sorted(d for d in nse if d not in hist and d.weekday() < 5)
    assert not missing, f"weekday sessions missing from history: {[str(d) for d in missing[-5:]]}"


def test_history_ohlc_matches_official_nse_values():
    nse, hist = _load_nse_report(), _load_history()
    common = sorted(set(nse) & set(hist))
    assert len(common) >= 240, "fixture/history overlap shrank unexpectedly"
    mismatches = []
    for d in common:
        for field in ("Open", "High", "Low", "Close"):
            ours, official = hist[d][field], nse[d][field]
            if abs(ours - official) > TOLERANCE:
                mismatches.append((str(d), field, ours, official))
    assert not mismatches, f"OHLC drift vs official NSE report: {mismatches[:10]}"
