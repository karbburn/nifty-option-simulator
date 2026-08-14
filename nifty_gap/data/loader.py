"""CSV loading, cleaning, and derived-column construction."""

from __future__ import annotations

import warnings

import pandas as pd

COLUMN_ALIASES = {
    "Date": "Date",
    "Open": "Open",
    "High": "High",
    "Low": "Low",
    "Close": "Close",
    "Shares Traded": "Shares_Traded",
    "Shares_Traded": "Shares_Traded",
    "Turnover (₹ Cr)": "Turnover_Cr",
    "Turnover_Cr": "Turnover_Cr",
    "data_source": "data_source",
}

CORE_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr"]


def read_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=COLUMN_ALIASES)
    df["Date"] = pd.to_datetime(df["Date"].str.strip(), format="%d-%b-%Y")
    for col in ["Open", "High", "Low", "Close", "Turnover_Cr"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="raise").astype("float64")
    if "Shares_Traded" in df.columns:
        df["Shares_Traded"] = pd.to_numeric(df["Shares_Traded"], errors="raise").astype("Int64")
    df = df.sort_values("Date").reset_index(drop=True)
    weekend = df["Date"].dt.day_name().str[:3].isin(["Sat", "Sun"])
    if weekend.any():
        n = int(weekend.sum())
        warnings.warn(f"dropping {n} non-trading (weekend) row(s): {df.loc[weekend, 'Date'].dt.strftime('%d-%b-%Y').tolist()}", stacklevel=2)
        df = df[~weekend].reset_index(drop=True)
    if "data_source" not in df.columns:
        df["data_source"] = "nse"
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["weekday"] = df["Date"].dt.day_name().str[:3]
    df["prev_close"] = df["Close"].shift(1)
    df["prev_weekday"] = df["weekday"].shift(1)
    df["weekday_pair"] = df["prev_weekday"] + "→" + df["weekday"]
    df["gap_up"] = (df["Open"] > df["prev_close"]).astype(float)
    df.loc[df["prev_close"].isna(), "gap_up"] = pd.NA
    df["gap_pct"] = df["Open"] / df["prev_close"] - 1
    return df


def load_dataframe(path) -> pd.DataFrame:
    return add_derived_columns(read_csv(path))


def load_history(path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return read_csv(path)


def write_history(path, df: pd.DataFrame) -> None:
    out = df.copy()
    out["Date"] = out["Date"].dt.strftime("%d-%b-%Y").str.upper()
    out.to_csv(path, index=False)


def seed_history(history_path, seed_path) -> pd.DataFrame | None:
    history = load_history(history_path)
    if history is not None:
        return history
    if not seed_path.exists():
        return None
    df = read_csv(seed_path)
    df["data_source"] = "nse"
    write_history(history_path, df)
    return df