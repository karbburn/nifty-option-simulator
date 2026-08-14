"""Shared fixtures for the test suite."""

from __future__ import annotations

import pandas as pd
import pytest

from nifty_gap.data.loader import add_derived_columns, read_csv

ROWS = [
    ["17-AUG-2026", 24650, 24750, 24550, 24700, 110000, 110.0],
    ["14-AUG-2026", 24600, 24650, 24500, 24500, 105000, 105.0],
    ["13-AUG-2026", 24600, 24700, 24550, 24650, 104000, 104.0],
    ["12-AUG-2026", 24500, 24600, 24450, 24550, 103000, 103.0],
    ["11-AUG-2026", 24550, 24650, 24500, 24600, 102000, 102.0],
    ["10-AUG-2026", 24500, 24600, 24400, 24500, 101000, 101.0],
]


@pytest.fixture
def sample_raw_csv(tmp_path):
    header = "\ufeffDate ,Open ,High ,Low ,Close ,Shares Traded ,Turnover (₹ Cr)"
    lines = [header] + [",".join(str(x) for x in row) for row in ROWS]
    path = tmp_path / "sample.csv"
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    return path


@pytest.fixture
def sample_df(sample_raw_csv):
    return add_derived_columns(read_csv(sample_raw_csv))


@pytest.fixture
def holiday_gap_df():
    rows = [
        ["2026-08-11", 24500, 24600, 24400, 24500, 101000, 101.0],
        ["2026-08-12", 24550, 24650, 24500, 24600, 102000, 102.0],
        ["2026-08-13", 24500, 24600, 24450, 24550, 103000, 103.0],
        ["2026-08-14", 24600, 24700, 24550, 24650, 104000, 104.0],
        ["2026-08-18", 24700, 24800, 24600, 24700, 105000, 105.0],
    ]
    df = pd.DataFrame(
        rows, columns=["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr"]
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df["data_source"] = "nse"
    return add_derived_columns(df)