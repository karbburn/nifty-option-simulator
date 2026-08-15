"""Probability table & signal tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nifty_gap.data.loader import add_derived_columns
from nifty_gap.signals.probability_table import build_probability_table, wilson_interval


def test_hand_computed_on_sample(sample_df):
    t = build_probability_table(sample_df, min_pair_sample=1)
    assert list(t["weekday_pair"]) == [
        "Mon→Tue",
        "Tue→Wed",
        "Wed→Thu",
        "Thu→Fri",
        "Fri→Mon",
    ]
    assert t["n"].tolist() == [1, 1, 1, 1, 1]
    assert t["p_up"].tolist() == [1.0, 0.0, 1.0, 0.0, 1.0]
    assert t["side"].tolist() == ["CE", "PE", "CE", "PE", "CE"]
    lo, hi = t["ci_low"].iloc[0], t["ci_high"].iloc[0]
    assert lo == pytest.approx(0.2063, abs=1e-3)
    assert hi == pytest.approx(1.0, abs=1e-3)


def test_wilson_scalar_values():
    lo, hi = wilson_interval(3, 5)
    assert lo == pytest.approx(0.2307, abs=1e-3)
    assert hi == pytest.approx(0.8824, abs=1e-3)
    assert wilson_interval(0, 1) == (pytest.approx(0.0), pytest.approx(0.793, abs=1e-3))
    assert wilson_interval(1, 1) == (pytest.approx(0.206, abs=1e-3), pytest.approx(1.0))


def test_wilson_n_zero_is_nan():
    lo, hi = wilson_interval(0, 0)
    assert np.isnan(lo) and np.isnan(hi)


def test_wilson_p_at_bounds_no_nan():
    lo, hi = wilson_interval(0, 20)
    assert not np.isnan(lo) and not np.isnan(hi)
    assert lo == pytest.approx(0.0, abs=1e-9)
    lo2, hi2 = wilson_interval(20, 20)
    assert not np.isnan(lo2) and not np.isnan(hi2)
    assert hi2 == pytest.approx(1.0, abs=1e-9)


def test_tie_at_50_percent_is_pe():
    rows = [
        ["2026-08-11", 24600, 24700, 24500, 24600, 1, 1.0],
        ["2026-08-12", 24550, 24650, 24500, 24550, 1, 1.0],
        ["2026-08-13", 24600, 24700, 24550, 24650, 1, 1.0],
        ["2026-08-19", 24700, 24800, 24600, 24700, 1, 1.0],
        ["2026-08-20", 24600, 24700, 24550, 24600, 1, 1.0],
    ]
    df = pd.DataFrame(
        rows, columns=["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr"]
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df = add_derived_columns(df)
    t = build_probability_table(df, min_pair_sample=1)
    row = t[t["weekday_pair"] == "Wed→Thu"]
    assert len(row) == 1
    assert row["n"].iloc[0] == 2
    assert row["p_up"].iloc[0] == 0.5
    assert row["side"].iloc[0] == "PE"
    assert bool(row["tradeable"].iloc[0])


def test_exclusion_below_min_sample(sample_df):
    t = build_probability_table(sample_df, min_pair_sample=5)
    assert not t["tradeable"].any()
    assert t["n"].le(1).all()


def test_excluded_pairs_marked_non_tradeable(sample_df):
    t = build_probability_table(sample_df, min_pair_sample=1, excluded_pairs=frozenset({"Fri→Mon"}))
    assert not t.loc[t["weekday_pair"] == "Fri→Mon", "tradeable"].iloc[0]
    assert t.loc[t["weekday_pair"] == "Fri→Mon", "n"].iloc[0] == 1
    assert t.loc[t["weekday_pair"] != "Fri→Mon", "tradeable"].all()


def test_groupby_includes_irregular_pairs(holiday_gap_df):
    t = build_probability_table(holiday_gap_df, min_pair_sample=1)
    assert "Fri→Tue" in set(t["weekday_pair"])


def test_uses_real_weekday_ordering(sample_df):
    t = build_probability_table(sample_df, min_pair_sample=1)
    assert t["weekday_pair"].tolist() == [
        "Mon→Tue",
        "Tue→Wed",
        "Wed→Thu",
        "Thu→Fri",
        "Fri→Mon",
    ]