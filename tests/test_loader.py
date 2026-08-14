"""Phase 2: loader tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nifty_gap.data.loader import add_derived_columns, load_dataframe, read_csv


def test_read_csv_cleans_header_and_sorts(sample_raw_csv):
    df = read_csv(sample_raw_csv)
    assert list(df.columns) == [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Shares_Traded",
        "Turnover_Cr",
        "data_source",
    ]
    assert df["Date"].is_monotonic_increasing
    assert df["Date"].min() == pd.Timestamp("2026-08-10")
    assert df["Date"].max() == pd.Timestamp("2026-08-17")


def test_dtypes(sample_raw_csv):
    df = read_csv(sample_raw_csv)
    assert df["Open"].dtype == np.float64
    assert df["Close"].dtype == np.float64
    assert str(df["Shares_Traded"].dtype) == "Int64"
    assert df["Turnover_Cr"].dtype == np.float64
    assert (df["data_source"] == "nse").all()


def test_derived_columns(sample_df):
    assert list(sample_df["weekday"]) == ["Mon", "Tue", "Wed", "Thu", "Fri", "Mon"]
    assert pd.isna(sample_df.loc[0, "prev_close"])
    assert sample_df.loc[1, "prev_close"] == 24500.0
    assert list(sample_df["weekday_pair"].dropna()) == [
        "Mon→Tue",
        "Tue→Wed",
        "Wed→Thu",
        "Thu→Fri",
        "Fri→Mon",
    ]
    assert list(sample_df["gap_up"].dropna()) == [1.0, 0.0, 1.0, 0.0, 1.0]
    assert sample_df.loc[1, "gap_pct"] == pytest.approx(24550 / 24500 - 1)


def test_load_dataframe_applies_derived(sample_raw_csv):
    df = load_dataframe(sample_raw_csv)
    assert "weekday_pair" in df.columns
    assert "gap_up" in df.columns
    assert "gap_pct" in df.columns


def test_irregular_pair_label(holiday_gap_df):
    pairs = holiday_gap_df["weekday_pair"].dropna().tolist()
    assert pairs[-1] == "Fri→Tue"
    assert holiday_gap_df.iloc[-1]["gap_up"] == 1.0


def test_irregular_pair_comparison_is_strict(holiday_gap_df):
    holiday_gap_df.loc[holiday_gap_df.index[-1], "Open"] = 24650.0
    g = add_derived_columns(holiday_gap_df.drop(columns=["weekday", "prev_close", "prev_weekday", "weekday_pair", "gap_up", "gap_pct"]))
    assert g.iloc[-1]["gap_up"] == 0.0


def test_weekend_row_dropped_with_warning(sample_raw_csv):
    content = "\ufeffDate ,Open ,High ,Low ,Close ,Shares Traded ,Turnover (₹ Cr)\n"
    content += "15-AUG-2026,24700,24800,24600,24700,1,1\n"
    content += "14-AUG-2026,24600,24700,24550,24600,1,1\n"
    path = sample_raw_csv.parent / "weekend.csv"
    path.write_text(content, encoding="utf-8-sig")
    with pytest.warns(UserWarning, match="dropping 1 non-trading"):
        df = read_csv(path)
    assert len(df) == 1
    assert df.iloc[0]["Date"] == pd.Timestamp("2026-08-14")