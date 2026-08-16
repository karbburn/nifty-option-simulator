"""Unit tests for the dashboard state layer."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from nifty_gap.backtest.engine import Trade
from nifty_gap.config import Config
from nifty_gap.data.loader import add_derived_columns
from nifty_gap.options.black_scholes import black_scholes
from nifty_gap.options.rate import get_risk_free_rate
from nifty_gap.signals.probability_table import build_probability_table
from nifty_gap.web.state import (
    compute_live_positions,
    compute_next_trade_preview,
    compute_premium_series,
)

cfg = Config()
RATE = get_risk_free_rate(cfg.rate_default)

ROWS = [
    ["2026-08-10", 24500, 24600, 24400, 24500, 1000, 100.0],  # Mon
    ["2026-08-11", 24600, 24700, 24500, 24650, 1000, 100.0],  # Tue (gap up)
    ["2026-08-12", 24550, 24650, 24500, 24600, 1000, 100.0],  # Wed
    ["2026-08-13", 24650, 24750, 24600, 24700, 1000, 100.0],  # Thu (expiry day)
    ["2026-08-14", 24700, 24800, 24650, 24750, 1000, 100.0],  # Fri
    ["2026-08-17", 24800, 24900, 24700, 24850, 1000, 100.0],  # Mon
    ["2026-08-18", 24900, 25000, 24800, 24950, 1000, 100.0],  # Tue (gap up)
]

DATES = [pd.Timestamp(r[0]) for r in ROWS]


@pytest.fixture
def wdf():
    df = pd.DataFrame(
        ROWS,
        columns=["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr"],
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df["data_source"] = "nse"
    return add_derived_columns(df)


def _mk_trade(entry_idx, exit_idx, pair, side, strike, expiry_idx, pnl):
    entry_close = float(ROWS[entry_idx][4])
    expiry = DATES[expiry_idx]
    tte = max((expiry - DATES[entry_idx]).days, 1) / 365.0
    entry_premium = black_scholes(entry_close, strike, tte, cfg.iv_flat, RATE, side)
    exit_premium = entry_premium + pnl / cfg.lot_size
    return Trade(
        entry_date=DATES[entry_idx],
        exit_date=DATES[exit_idx],
        pair=pair,
        side=side,
        strike=strike,
        entry_close=entry_close,
        expiry=expiry,
        entry_premium=entry_premium,
        exit_premium=exit_premium,
        exit_reason="expiry",
        days_held=exit_idx - entry_idx,
        pnl=pnl,
        legs=(
            {
                "entry_date": DATES[entry_idx],
                "exit_date": DATES[exit_idx],
                "expiry": expiry,
                "strike": strike,
                "entry_premium": entry_premium,
                "exit_premium": exit_premium,
            },
        ),
    )


def test_live_positions_selects_most_recent_unexpired_per_pair(wdf):
    open_trade = _mk_trade(0, 5, "Mon→Tue", "CE", 24600, 6, 750.0)
    older_open = _mk_trade(0, 5, "Mon→Tue", "CE", 24600, 6, 0.0)
    closed = _mk_trade(2, 4, "Wed→Thu", "PE", 24700, 4, -300.0)
    today = date(2026, 8, 14)
    positions = compute_live_positions([closed, older_open, open_trade], 25000, cfg, today=today)
    assert len(positions) == 1
    assert positions[0]["pair"] == "Mon→Tue"
    assert positions[0]["entry_date"] == "2026-08-10"


def test_live_positions_expiry_filtering(wdf):
    closed = _mk_trade(0, 2, "Mon→Tue", "CE", 24600, 2, 500.0)
    today = date(2026, 8, 14)
    positions = compute_live_positions([closed], 25000, cfg, today=today)
    assert positions == []


def test_live_positions_pnl_math(wdf):
    t = _mk_trade(0, 5, "Mon→Tue", "CE", 24600, 6, 0.0)
    today = date(2026, 8, 12)
    positions = compute_live_positions([t], 25000, cfg, today=today)
    live = positions[0]
    assert live["strike"] == 24600
    assert live["days_to_expiry"] == 6
    assert live["side"] == "CE"


def test_next_trade_preview_finds_next_tradeable_pair(wdf):
    table = build_probability_table(
        wdf, min_pair_sample=1, z=cfg.z_score, excluded_pairs=frozenset()
    )
    preview = compute_next_trade_preview(wdf, table, 25000.0, cfg, today=date(2026, 8, 14))
    assert preview["pair"] == "Fri→Mon"
    assert preview["side"] in ("CE", "PE")
    assert preview["strike"] > 0
    assert preview["entry_premium"] > 0


def test_next_trade_preview_skips_excluded_pairs(wdf):
    table = build_probability_table(
        wdf, min_pair_sample=1, z=cfg.z_score, excluded_pairs=frozenset({"Fri→Mon"})
    )
    preview = compute_next_trade_preview(wdf, table, 25000.0, cfg, today=date(2026, 8, 14))
    assert preview["note"] == "Next pair not tradeable"


def test_premium_series_first_element_is_entry_premium(wdf):
    t = _mk_trade(0, 3, "Mon→Tue", "CE", 24600, 3, 300.0)
    series = compute_premium_series(wdf, t, cfg)
    assert series[0]["premium"] == pytest.approx(t.entry_premium, abs=1.0)
    assert series[0]["date"] == "2026-08-10"
    assert series[-1]["date"] == "2026-08-13"


def test_premium_series_length_matches_duration(wdf):
    t = _mk_trade(1, 4, "Mon→Tue", "CE", 24600, 4, 0.0)
    series = compute_premium_series(wdf, t, cfg)
    assert len(series) == 4


def test_live_positions_spot_affects_premium(wdf):
    t = _mk_trade(0, 5, "Mon→Tue", "CE", 24600, 6, 0.0)
    today = date(2026, 8, 12)
    low = compute_live_positions([t], 24500, cfg, today=today)[0]
    high = compute_live_positions([t], 25200, cfg, today=today)[0]
    assert high["live_premium"] > low["live_premium"]