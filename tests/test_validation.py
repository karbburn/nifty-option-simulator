"""Phase 2: validation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nifty_gap.data.validation import (
    DataValidationError,
    validate_holidays,
    validate_integrity,
)


def _frame(rows, dates):
    df = pd.DataFrame(
        rows,
        columns=["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr", "data_source"],
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df["Shares_Traded"] = df["Shares_Traded"].astype("Int64")
    return df


def _base_rows():
    return [
        ["2026-08-10", 24500, 24600, 24400, 24500, 101000, 101.0, "nse"],
        ["2026-08-11", 24550, 24650, 24500, 24600, 102000, 102.0, "nse"],
        ["2026-08-12", 24500, 24600, 24450, 24550, 103000, 103.0, "nse"],
    ]


def test_valid_frame_passes(sample_df):
    validate_integrity(sample_df)
    validate_holidays(sample_df)


def test_duplicate_date_raises(sample_df):
    bad = pd.concat([sample_df, sample_df.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError):
        validate_integrity(bad)


@pytest.mark.parametrize("col", ["Open", "High", "Low", "Close"])
def test_null_ohlc_raises(sample_df, col):
    bad = sample_df.copy()
    bad.loc[0, col] = np.nan
    with pytest.raises(DataValidationError):
        validate_integrity(bad)


def test_high_violation_raises(sample_df):
    bad = sample_df.copy()
    bad.loc[0, "High"] = bad.loc[0, "Open"] - 1
    with pytest.raises(DataValidationError):
        validate_integrity(bad)


def test_low_violation_raises(sample_df):
    bad = sample_df.copy()
    bad.loc[0, "Low"] = bad.loc[0, "Close"] + 1
    with pytest.raises(DataValidationError):
        validate_integrity(bad)


def test_weekend_row_raises():
    rows = _base_rows() + [["2026-08-15", 24600, 24700, 24550, 24650, 105000, 105.0, "nse"]]
    df = _frame(rows, None)
    with pytest.raises(DataValidationError):
        validate_integrity(df)


def test_calendar_gap_too_large_raises():
    rows = [
        ["2026-08-03", 24400, 24500, 24300, 24400, 100000, 100.0, "nse"],
        ["2026-08-10", 24500, 24600, 24400, 24500, 101000, 101.0, "nse"],
    ]
    df = _frame(rows, None)
    with pytest.raises(DataValidationError):
        validate_integrity(df)


def test_holiday_present_raises(sample_df):
    bad = sample_df.copy()
    bad.loc[0, "Date"] = pd.Timestamp("2025-08-15")
    with pytest.raises(DataValidationError):
        validate_holidays(bad)


def test_nse_zero_shares_raises(sample_df):
    bad = sample_df.copy()
    bad.loc[0, "Shares_Traded"] = 0
    with pytest.raises(DataValidationError):
        validate_integrity(bad)


def test_yfinance_null_shares_allowed():
    rows = [
        ["2026-08-10", 24500, 24600, 24400, 24500, None, None, "yfinance"],
        ["2026-08-11", 24550, 24650, 24500, 24600, None, None, "yfinance"],
    ]
    df = _frame(rows, None)
    validate_integrity(df)


def test_data_profile(sample_df):
    from nifty_gap.data.validation import data_profile

    profile = data_profile(sample_df)
    assert profile["rows"] == 6
    assert profile["first_date"] == "2026-08-10"
    assert profile["source_counts"] == {"nse": 6}
    assert profile["shares_traded_nulls"] == 0