"""Metrics tests (hand-computed)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from nifty_gap.reporting.metrics import (
    equity_stats,
    export_json,
    oos_summary,
    pair_stats,
    provenance,
    trade_stats,
)

TRADE_COLUMNS = ["entry_date", "exit_date", "pair", "side", "strike", "entry_close",
                 "expiry", "entry_premium", "exit_premium", "exit_reason", "days_held", "pnl"]


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["2026-08-10", "2026-08-11", "Mon→Tue", "CE", 24500, 24500, "2026-08-13", 100.0, 200.0, "floor_15", 1, 100.0],
            ["2026-08-11", "2026-08-12", "Mon→Tue", "CE", 24500, 24500, "2026-08-13", 100.0, 50.0, "stop_7", 1, -50.0],
            ["2026-08-12", "2026-08-13", "Tue→Wed", "PE", 24600, 24600, "2026-08-13", 100.0, 100.0, "expiry", 1, 0.0],
            ["2026-08-13", "2026-08-14", "Tue→Wed", "PE", 24600, 24600, "2026-08-20", 100.0, 130.0, "floor_5", 1, 30.0],
        ],
        columns=TRADE_COLUMNS,
    )


def test_trade_stats_hand_computed():
    stats = trade_stats(_trades())
    assert stats["n_trades"] == 4
    assert stats["total_pnl"] == pytest.approx(80.0)
    assert stats["win_rate"] == pytest.approx(0.5)
    assert stats["avg_win"] == pytest.approx(65.0)
    assert stats["avg_loss"] == pytest.approx(-25.0)
    assert stats["profit_factor"] == pytest.approx(2.6)
    by_reason = {r["exit_reason"]: r for r in stats["exit_reasons"]}
    assert by_reason["stop_7"]["count"] == 1 and by_reason["stop_7"]["pct"] == pytest.approx(25.0)
    assert by_reason["floor_15"]["avg_pnl"] == pytest.approx(100.0)
    assert by_reason["expiry"]["avg_pnl"] == pytest.approx(0.0)


def test_win_rate_tie_counts_as_loss():
    trades = _trades()
    zero = trades[trades["exit_reason"] == "expiry"]
    stats = trade_stats(zero)
    assert len(zero) == 1
    assert stats["win_rate"] == pytest.approx(0.0)
    assert stats["avg_loss"] == pytest.approx(0.0)
    assert pd.isna(stats["profit_factor"])


def test_empty_trades_edge():
    stats = trade_stats(pd.DataFrame(columns=TRADE_COLUMNS))
    assert stats["n_trades"] == 0
    assert stats["total_pnl"] == 0.0
    assert pd.isna(stats["win_rate"])
    assert pd.isna(stats["profit_factor"])
    assert stats["exit_reasons"] == []


def test_single_trade_edge():
    one = _trades().iloc[[0]]
    stats = trade_stats(one)
    assert stats["n_trades"] == 1
    assert stats["win_rate"] == pytest.approx(1.0)
    assert stats["profit_factor"] == math.inf  # wins-only -> no losses to divide by


def test_equity_stats_hand_computed():
    eq = pd.DataFrame({"Date": pd.date_range("2026-08-10", periods=5), "equity": [0.0, 100.0, 150.0, 120.0, 120.0]})
    stats = equity_stats(eq)
    assert stats["n_days"] == 5
    assert stats["final_equity"] == pytest.approx(120.0)
    assert stats["max_drawdown"] == pytest.approx(30.0)
    assert stats["max_drawdown_pct"] == pytest.approx(0.2)
    assert stats["sharpe_annualized"] == pytest.approx(8.3323, abs=1e-3)


def test_equity_flat_series_sharpe_nan():
    eq = pd.DataFrame({"Date": pd.date_range("2026-08-10", periods=3), "equity": [0.0, 0.0, 0.0]})
    stats = equity_stats(eq)
    assert pd.isna(stats["sharpe_annualized"])
    assert stats["max_drawdown"] == pytest.approx(0.0)


def test_pair_stats_merges_table_and_trades():
    table = pd.DataFrame(
        {
            "weekday_pair": ["Mon→Tue", "Tue→Wed"],
            "n": [50, 49],
            "p_up": [0.56, 0.47],
            "ci_low": [0.42, 0.33],
            "ci_high": [0.70, 0.61],
            "side": ["CE", "PE"],
            "tradeable": [True, True],
        }
    )
    out = pair_stats(_trades(), table)
    assert list(out["weekday_pair"]) == ["Mon→Tue", "Tue→Wed"]
    mon = out[out["weekday_pair"] == "Mon→Tue"].iloc[0]
    assert mon["traded"] == 2
    assert mon["wins"] == 1
    assert mon["win_rate"] == pytest.approx(0.5)
    assert mon["total_pnl"] == pytest.approx(50.0)
    tue = out[out["weekday_pair"] == "Tue→Wed"].iloc[0]
    assert tue["p_up"] == pytest.approx(0.47)
    assert tue["total_pnl"] == pytest.approx(30.0)


def test_oos_summary_structure():
    oos = pd.DataFrame(
        {
            "weekday_pair": ["Mon→Tue"],
            "side": ["CE"],
            "n": [50],
            "p_up": [0.56],
            "ci_low": [0.42],
            "ci_high": [0.70],
            "n_oos": [23],
            "realized_p_up": [0.52],
            "realized_ci_low": [0.31],
            "realized_ci_high": [0.72],
        }
    )
    rows = oos_summary(oos)
    assert rows[0]["n_in"] == 50
    assert rows[0]["n_oos"] == 23
    assert rows[0]["realized_p_up"] == pytest.approx(0.52)


def test_oos_summary_missing_oos_pair():
    oos = pd.DataFrame(
        {
            "weekday_pair": ["Mon→Tue"],
            "side": ["CE"],
            "n": [50],
            "p_up": [0.56],
            "ci_low": [0.42],
            "ci_high": [0.70],
            "n_oos": [pd.NA],
            "realized_p_up": [pd.NA],
            "realized_ci_low": [pd.NA],
            "realized_ci_high": [pd.NA],
        }
    )
    rows = oos_summary(oos)
    assert rows[0]["n_oos"] == 0
    assert pd.isna(rows[0]["realized_p_up"])


def test_provenance_block():
    info = provenance()
    assert "generated_at" in info and "git_sha" in info


def test_export_json(tmp_path):
    export_json({"a": 1, "nested": {"b": 2}}, tmp_path / "sub" / "out.json")
    import json

    data = json.loads((tmp_path / "sub" / "out.json").read_text(encoding="utf-8"))
    assert data == {"a": 1, "nested": {"b": 2}}