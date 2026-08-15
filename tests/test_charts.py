"""Visualization tests — render without error, files exist and non-empty."""

from __future__ import annotations

import pandas as pd

from nifty_gap.visualization.charts import (
    benchmark_chart,
    equity_chart,
    exit_reasons_chart,
    oos_chart,
    probability_chart,
    render_all,
)


def _table():
    return pd.DataFrame(
        {
            "weekday_pair": ["Fri→Mon", "Mon→Tue", "Thu→Fri", "Tue→Wed", "Wed→Thu"],
            "n": [48, 3, 49, 49, 50],
            "p_up": [0.52, 0.55, 0.46, 0.5, 0.6],
            "ci_low": [0.37, 0.36, 0.32, 0.36, 0.45],
            "ci_high": [0.66, 0.8, 0.61, 0.64, 0.74],
            "side": ["CE", "CE", "PE", "PE", "CE"],
            "tradeable": [True, False, True, True, True],
        }
    )


def _trades():
    return pd.DataFrame(
        {
            "entry_date": pd.to_datetime(["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"]),
            "exit_date": pd.to_datetime(["2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17"]),
            "pair": ["Mon→Tue", "Mon→Tue", "Tue→Wed", "Tue→Wed"],
            "exit_reason": ["floor_15", "stop_7", "floor_10", "expiry"],
            "pnl": [6000.0, -4000.0, 2000.0, 0.0],
        }
    )


def _equity():
    dates = pd.to_datetime(["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14", "2026-08-17"])
    return pd.DataFrame({"Date": dates, "equity": [0.0, 1500.0, -500.0, 1000.0, 2500.0, 4000.0]})


def _oos():
    return pd.DataFrame(
        {
            "weekday_pair": ["Mon→Tue", "Tue→Wed"],
            "side": ["CE", "PE"],
            "p_up": [0.56, 0.44],
            "ci_low": [0.42, 0.31],
            "ci_high": [0.7, 0.57],
            "realized_p_up": [0.5, 0.48],
            "realized_ci_low": [0.3, 0.29],
            "realized_ci_high": [0.7, 0.67],
        }
    )


def _assert_png(path):
    p = path
    assert p.exists()
    assert p.stat().st_size > 0


def test_probability_chart_renders(tmp_path):
    p = tmp_path / "probability.png"
    probability_chart(_table(), p)
    _assert_png(p)


def test_exit_reasons_chart_renders(tmp_path):
    p = tmp_path / "exit_reasons.png"
    exit_reasons_chart(_trades(), p)
    _assert_png(p)


def test_equity_chart_renders(tmp_path):
    p = tmp_path / "equity.png"
    equity_chart(_equity(), _trades(), p)
    _assert_png(p)


def test_benchmark_chart_renders(tmp_path):
    p = tmp_path / "benchmark.png"
    benchmark_chart(_equity(), _equity(), p)
    _assert_png(p)


def test_oos_chart_renders(tmp_path):
    p = tmp_path / "oos.png"
    oos_chart(_oos(), p)
    _assert_png(p)


def test_render_all_produces_five_pngs(tmp_path):
    paths = render_all(_table(), _trades(), _equity(), _equity(), _oos(), tmp_path)
    assert len(paths) == 5
    for p in paths:
        _assert_png(p)
    assert all(p.suffix == ".png" for p in paths)