"""Integrity and holiday validation for the cleaned frame."""

from __future__ import annotations

import pandas as pd

MAX_CALENDAR_GAP_DAYS = 4

KNOWN_HOLIDAYS = [
    "2025-08-15",
    "2025-10-02",
    "2025-12-25",
    "2026-01-26",
]


class DataValidationError(ValueError):
    pass


def validate_integrity(df: pd.DataFrame) -> None:
    required = ["Date", "Open", "High", "Low", "Close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataValidationError(f"missing required columns: {missing}")

    if df["Date"].isna().any():
        raise DataValidationError("null dates present")
    if df["Date"].duplicated().any():
        raise DataValidationError("duplicate dates present")
    if df[["Open", "High", "Low", "Close"]].isna().any().any():
        raise DataValidationError("null OHLC values present")
    if not (df["High"] >= df[["Open", "Close"]].max(axis=1)).all():
        raise DataValidationError("High < max(Open, Close) on at least one row")
    if not (df["Low"] <= df[["Open", "Close"]].min(axis=1)).all():
        raise DataValidationError("Low > min(Open, Close) on at least one row")
    if df["Close"].le(0).any():
        raise DataValidationError("non-positive Close present")

    weekdays = df["Date"].dt.day_name().str[:3]
    if weekdays.isin(["Sat", "Sun"]).any():
        raise DataValidationError("weekend rows present")

    gaps = df["Date"].diff().dt.days.dropna()
    if gaps.gt(MAX_CALENDAR_GAP_DAYS).any():
        raise DataValidationError(f"calendar gap > {MAX_CALENDAR_GAP_DAYS} days between consecutive rows")

    if "data_source" in df.columns:
        nse_rows = df[df["data_source"] == "nse"]
    else:
        nse_rows = df
    if "Shares_Traded" in nse_rows.columns and nse_rows["Shares_Traded"].notna().any():
        if nse_rows["Shares_Traded"].isna().any() or (nse_rows["Shares_Traded"] <= 0).any():
            raise DataValidationError("nse rows require Shares_Traded > 0")
    if "Turnover_Cr" in nse_rows.columns and nse_rows["Turnover_Cr"].notna().any():
        if nse_rows["Turnover_Cr"].isna().any() or (nse_rows["Turnover_Cr"] <= 0).any():
            raise DataValidationError("nse rows require Turnover_Cr > 0")


def validate_holidays(df: pd.DataFrame, holidays: list[str] | None = None) -> None:
    dates = set(df["Date"].dt.strftime("%Y-%m-%d"))
    for day in holidays or KNOWN_HOLIDAYS:
        if day in dates:
            raise DataValidationError(f"unexpected trading row on holiday {day}")


def data_profile(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "first_date": df["Date"].min().strftime("%Y-%m-%d"),
        "last_date": df["Date"].max().strftime("%Y-%m-%d"),
        "weekday_counts": df["Date"].dt.day_name().str[:3].value_counts().to_dict(),
        "pair_counts": df["weekday_pair"].dropna().value_counts().to_dict(),
        "source_counts": df["data_source"].value_counts().to_dict()
        if "data_source" in df.columns
        else {"nse": len(df)},
        "shares_traded_nulls": int(df["Shares_Traded"].isna().sum())
        if "Shares_Traded" in df.columns
        else 0,
        "turnover_nulls": int(df["Turnover_Cr"].isna().sum())
        if "Turnover_Cr" in df.columns
        else 0,
    }