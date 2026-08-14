"""Integration test against the real uploaded NSE CSV (skipped if absent)."""

from __future__ import annotations

import pytest

from nifty_gap.config import Config
from nifty_gap.data.loader import load_dataframe
from nifty_gap.data.validation import (
    MAX_CALENDAR_GAP_DAYS,
    data_profile,
    validate_holidays,
    validate_integrity,
)


@pytest.mark.filterwarnings("ignore:dropping")
@pytest.mark.skipif(not Config().data_path.exists(), reason="uploaded NSE CSV not present")
def test_real_csv_clean():
    df = load_dataframe(Config().data_path)
    validate_integrity(df)
    validate_holidays(df)
    profile = data_profile(df)
    assert profile["rows"] == 246
    assert profile["source_counts"] == {"nse": 246}
    assert profile["shares_traded_nulls"] == 0
    assert profile["turnover_nulls"] == 0
    assert df["Date"].diff().dt.days.dropna().max() <= MAX_CALENDAR_GAP_DAYS
    assert not df["Date"].dt.day_name().str[:3].isin(["Sat", "Sun"]).any()


@pytest.mark.filterwarnings("ignore:dropping")
@pytest.mark.skipif(not Config().data_path.exists(), reason="uploaded NSE CSV not present")
def test_real_csv_has_no_weekend_rows():
    df = load_dataframe(Config().data_path)
    assert not df["Date"].dt.day_name().str[:3].isin(["Sat", "Sun"]).any()