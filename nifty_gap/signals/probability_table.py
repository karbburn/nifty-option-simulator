"""Weekday-pair probability table and signal construction."""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAY_ORDER = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def wilson_interval(successes, n, z: float = 1.96):
    with np.errstate(divide="ignore", invalid="ignore"):
        n = np.asarray(n, dtype=float)
        successes = np.asarray(successes, dtype=float)
        p = successes / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt((p * (1 - p)) / n + z**2 / (4 * n**2)) / denom
        ci_low = np.maximum(center - half, 0.0)
        ci_high = np.minimum(center + half, 1.0)
        ci_low = np.where(n <= 0, np.nan, ci_low)
        ci_high = np.where(n <= 0, np.nan, ci_high)
        if np.ndim(successes) == 0:
            return float(ci_low), float(ci_high)
        return ci_low, ci_high


def build_probability_table(df: pd.DataFrame, min_pair_sample: int = 5, z: float = 1.96) -> pd.DataFrame:
    g = df.dropna(subset=["weekday_pair"]).copy()
    stats = (
        g.groupby("weekday_pair", sort=False)["gap_up"]
        .agg(["size", "sum"])
        .rename(columns={"size": "n", "sum": "n_up"})
        .reset_index()
    )
    stats["p_up"] = stats["n_up"] / stats["n"]
    stats["ci_low"], stats["ci_high"] = wilson_interval(stats["n_up"], stats["n"], z)
    stats["side"] = np.where(stats["p_up"] > 0.5, "CE", "PE")
    stats["tradeable"] = (stats["n"] >= min_pair_sample) & stats["ci_low"].notna()
    stats["_d1"] = stats["weekday_pair"].str[:3].map(WEEKDAY_ORDER)
    stats["_d2"] = stats["weekday_pair"].str[-3:].map(WEEKDAY_ORDER)
    stats = stats.sort_values(["_d1", "_d2"]).drop(columns=["_d1", "_d2"]).reset_index(drop=True)
    return stats