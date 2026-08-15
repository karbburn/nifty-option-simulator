"""Backtest engine + benchmark tests."""

from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd
import pytest

from nifty_gap.backtest.engine import (
    Trade,
    build_signals,
    daily_mtm,
    export_results,
    ladder_log_gate,
    oos_diagnostic,
    run_backtest,
)
from nifty_gap.config import Config
from nifty_gap.data.loader import add_derived_columns
from nifty_gap.data.validation import validate_integrity
from nifty_gap.options.black_scholes import black_scholes
from nifty_gap.options.rate import get_risk_free_rate
from nifty_gap.options.strikes import nearest_strike
from nifty_gap.signals.probability_table import build_probability_table

cfg = Config()
RATE = get_risk_free_rate(cfg.rate_default)

ROWS = [
    # ==== Week A ====
    ["2026-08-10", 24000, 24100, 23900, 24000, 1000, 100.0],  # Mon
    ["2026-08-11", 24500, 24600, 21900, 22000, 1000, 100.0],  # Tue (gap-up, intraday crash)
    ["2026-08-12", 22500, 24100, 22400, 24000, 1000, 100.0],  # Wed
    ["2026-08-13", 23000, 24100, 22900, 24000, 1000, 100.0],  # Thu (expiry day)
    ["2026-08-14", 23000, 24100, 22900, 23000, 1000, 100.0],  # Fri
    # ==== Week B ====
    ["2026-08-17", 23500, 24100, 23400, 24000, 1000, 100.0],  # Mon
    ["2026-08-18", 24500, 24600, 23900, 24000, 1000, 100.0],  # Tue (gap-up, strong CE hold)
    ["2026-08-19", 22500, 24100, 22400, 23500, 1000, 100.0],  # Wed
    ["2026-08-20", 23500, 24100, 23400, 24000, 1000, 100.0],  # Thu (expiry day)
    ["2026-08-21", 24000, 24100, 23900, 24000, 1000, 100.0],  # Fri
]


@pytest.fixture
def engine_df():
    df = pd.DataFrame(
        ROWS,
        columns=["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr"],
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df["data_source"] = "nse"
    df = add_derived_columns(df)
    validate_integrity(df)
    return df


def _table(engine_df, min_pair_sample=1):
    return build_probability_table(engine_df, min_pair_sample=min_pair_sample)


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def _trade_for(engine_df, entry_date, rollover=True):
    local = replace(cfg, ladder_rollover=rollover)
    trades = run_backtest(engine_df, _table(engine_df), local)
    return next(t for t in trades if t.entry_date == _ts(entry_date))


# ---------- signals ----------

def test_signal_universe_is_every_tradeable_observation(engine_df):
    table = _table(engine_df)
    sig = build_signals(engine_df, table)
    assert len(sig) == 9
    assert set(sig["pair"]) == {"Mon→Tue", "Tue→Wed", "Wed→Thu", "Thu→Fri", "Fri→Mon"}
    assert list(sig["entry_date"]) == list(engine_df["Date"].iloc[:-1])
    side_of = dict(zip(table["weekday_pair"], table["side"]))
    assert (sig["side"] == sig["pair"].map(side_of)).all()


def test_non_tradeable_pairs_excluded(engine_df):
    table = _table(engine_df, min_pair_sample=5)
    assert not table["tradeable"].any()
    assert build_signals(engine_df, table).empty


def test_trade_count_and_entry_pricing_match_bs(engine_df):
    trades = run_backtest(engine_df, _table(engine_df), cfg)
    assert len(trades) == 9
    for t in trades:
        strike = nearest_strike(t.entry_close, cfg.strike_interval, cfg.strike_tie_rule)
        t0 = (t.legs[0]["expiry"] - t.entry_date).days / 365.0
        expected = black_scholes(t.entry_close, strike, t0, cfg.iv_flat, RATE, t.side)
        assert t.entry_premium == pytest.approx(expected, rel=1e-9)
        assert t.strike == strike


def test_stop_trade_hand_checked(engine_df):
    t = _trade_for(engine_df, "2026-08-10")
    assert t.pair == "Mon→Tue"
    assert t.side == "CE"
    assert t.exit_reason == "stop_7"
    assert t.exit_date == _ts("2026-08-11")
    assert t.days_held == 1
    expected_entry = black_scholes(24000, 24000, 3 / 365, cfg.iv_flat, RATE, "CE")
    expected_exit = black_scholes(22000, 24000, 2 / 365, cfg.iv_flat, RATE, "CE")
    assert t.entry_premium == pytest.approx(expected_entry, rel=1e-9)
    assert t.exit_premium == pytest.approx(expected_exit, rel=1e-9)
    assert t.pnl == pytest.approx((expected_exit - expected_entry) * cfg.lot_size, rel=1e-9)


def test_trailing_floor_holds_rally_to_expiry(engine_df):
    t = _trade_for(engine_df, "2026-08-14", rollover=False)
    assert t.pair == "Fri→Mon"
    assert t.side == "CE"
    assert t.exit_reason == "expiry"
    assert t.exit_date == _ts("2026-08-20")
    assert t.days_held == 6
    assert t.exit_premium == pytest.approx(1000.0, rel=1e-9)


def test_expiry_exit_at_intrinsic(engine_df):
    t = _trade_for(engine_df, "2026-08-12", rollover=False)
    assert t.pair == "Wed→Thu"
    assert t.side == "PE"
    assert t.exit_reason == "expiry"
    assert t.exit_date == _ts("2026-08-13")
    assert t.days_held == 1
    assert t.exit_premium == pytest.approx(0.0, abs=1e-9)
    assert t.pnl == pytest.approx(-t.entry_premium * cfg.lot_size, rel=1e-9)


def test_rollover_rolls_expiry_trades_to_next_expiry(engine_df):
    baseline = run_backtest(engine_df, _table(engine_df), replace(cfg, ladder_rollover=False))
    rolled = run_backtest(engine_df, _table(engine_df), cfg)
    by_entry = {t.entry_date: t for t in rolled}
    for a in baseline:
        if a.exit_reason != "expiry":
            continue
        b = by_entry[a.entry_date]
        assert b.rolls >= 1
        assert b.exit_date > a.exit_date
        assert all(leg["exit_reason"] == "expiry" for leg in b.legs[:-1])


def test_rollover_never_chains_past_available_data(engine_df):
    t = _trade_for(engine_df, "2026-08-14", rollover=True)
    assert t.legs[-1]["exit_date"] <= engine_df["Date"].max()
    assert t.rolls == len(t.legs) - 1


def test_pnl_arithmetic_is_exit_minus_entry_times_lot(engine_df):
    for t in run_backtest(engine_df, _table(engine_df), cfg):
        assert t.pnl == pytest.approx(sum(leg["pnl"] for leg in t.legs), rel=1e-9)
        for leg in t.legs:
            assert leg["pnl"] == pytest.approx(
                (leg["exit_premium"] - leg["entry_premium"]) * cfg.lot_size, rel=1e-9
            )


# ---------- portfolio MTM ----------

def test_equity_starts_zero_and_ends_at_total_pnl(engine_df):
    trades = run_backtest(engine_df, _table(engine_df), cfg)
    eq = daily_mtm(engine_df, trades, cfg)
    total = sum(t.pnl for t in trades)
    assert eq["equity"].iloc[0] == pytest.approx(0.0, abs=1e-6)
    assert eq["equity"].iloc[-1] == pytest.approx(total, abs=1e-6)


def test_overlap_two_live_positions_mtm_correct(engine_df):
    t1 = Trade(
        entry_date=_ts("2026-08-10"),
        exit_date=_ts("2026-08-14"),
        pair="Mon→Tue",
        side="CE",
        strike=24500.0,
        entry_close=24000.0,
        expiry=_ts("2026-08-14"),
        entry_premium=100.0,
        exit_premium=150.0,
        exit_reason="expiry",
        days_held=4,
        pnl=50.0 * cfg.lot_size,
    )
    t2 = Trade(
        entry_date=_ts("2026-08-11"),
        exit_date=_ts("2026-08-21"),
        pair="Tue→Wed",
        side="PE",
        strike=24400.0,
        entry_close=24250.0,
        expiry=_ts("2026-08-21"),
        entry_premium=90.0,
        exit_premium=130.0,
        exit_reason="expiry",
        days_held=10,
        pnl=40.0 * cfg.lot_size,
    )
    eq = daily_mtm(engine_df, [t1, t2], cfg).set_index("Date")

    mid = _ts("2026-08-12")
    s_mid = float(engine_df.set_index("Date").loc[mid, "Close"])
    mark1_mid = black_scholes(s_mid, t1.strike, 2 / 365, cfg.iv_flat, RATE, t1.side)
    mark2_mid = black_scholes(s_mid, t2.strike, 9 / 365, cfg.iv_flat, RATE, t2.side)
    expected_mid = (mark1_mid - t1.entry_premium) * cfg.lot_size + (
        mark2_mid - t2.entry_premium
    ) * cfg.lot_size
    assert eq.loc[mid, "equity"] == pytest.approx(expected_mid, rel=1e-9)

    last = _ts("2026-08-14")
    s_last = float(engine_df.set_index("Date").loc[last, "Close"])
    mark2_last = black_scholes(s_last, t2.strike, 7 / 365, cfg.iv_flat, RATE, t2.side)
    expected_last = t1.pnl + (mark2_last - t2.entry_premium) * cfg.lot_size
    assert eq.loc[last, "equity"] == pytest.approx(expected_last, rel=1e-9)


# ---------- benchmark ----------

def test_benchmark_holds_every_trade_to_expiry(engine_df):
    ladder = run_backtest(engine_df, _table(engine_df), cfg, mode="ladder")
    hold = run_backtest(engine_df, _table(engine_df), cfg, mode="hold")
    assert len(ladder) == len(hold) == 9
    assert all(t.exit_reason == "expiry" for t in hold)
    for h, lad in zip(hold, ladder):
        assert h.entry_date == lad.entry_date
        assert h.pair == lad.pair
        assert h.entry_premium == pytest.approx(lad.entry_premium, rel=1e-9)
        assert h.exit_date <= h.expiry
    assert any(lad.exit_reason != "expiry" for lad in ladder)


# ---------- oos diagnostic ----------

def test_oos_diagnostic_structure(engine_df):
    res = oos_diagnostic(engine_df, cfg)
    assert "split_date" in res
    assert "table" in res and "oos" in res
    oos = res["oos"]
    assert {"weekday_pair", "p_up", "n_oos", "realized_p_up"} <= set(oos.columns)
    assert len(oos) == len(res["table"])
    assert oos["n_oos"].sum() >= 1
    assert res["split_date"] >= engine_df["Date"].min()
    assert res["split_date"] <= engine_df["Date"].max()


# ---------- export + log gate ----------

def test_export_results_writes_three_artifacts(engine_df, tmp_path):
    trades = run_backtest(engine_df, _table(engine_df), cfg)
    eq = daily_mtm(engine_df, trades, cfg)
    export_results(trades, eq, {"answer": 42}, tmp_path)
    assert (tmp_path / "trades.csv").exists()
    assert (tmp_path / "equity.csv").exists()
    assert (tmp_path / "params.json").exists()
    written = pd.read_csv(tmp_path / "trades.csv")
    assert len(written) == len(trades)
    assert json.loads((tmp_path / "params.json").read_text(encoding="utf-8"))["answer"] == 42
    assert list(written.columns) == [
        "entry_date",
        "exit_date",
        "pair",
        "side",
        "strike",
        "entry_close",
        "expiry",
        "entry_premium",
        "exit_premium",
        "exit_reason",
        "days_held",
        "pnl",
        "rolls",
    ]


def test_ladder_log_gate_reports_reasons_and_hold(engine_df):
    trades = run_backtest(engine_df, _table(engine_df), cfg)
    gate = ladder_log_gate(trades)
    assert sum(gate["exit_reason_counts"].values()) == 9
    assert any(r.startswith(("stop_", "floor_")) for r in gate["exit_reason_counts"])
    assert gate["avg_days_held"] > 0
    assert gate["max_days_held"] >= gate["avg_days_held"]