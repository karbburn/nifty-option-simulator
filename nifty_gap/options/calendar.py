"""Weekly expiry calendar for NIFTY weekly options."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

_WEEKDAY_NAMES = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
}


def _as_date(d):
    if isinstance(d, (datetime, pd.Timestamp)):
        return d.date()
    return d


def next_expiry(d, expiry_weekday: str = "Thursday") -> date:
    if expiry_weekday not in _WEEKDAY_NAMES:
        raise ValueError(f"unsupported expiry weekday: {expiry_weekday!r}")
    d0 = _as_date(d)
    delta = (_WEEKDAY_NAMES[expiry_weekday] - d0.weekday()) % 7
    if delta == 0:
        delta = 7
    return d0 + timedelta(days=delta)


def days_to_expiry(d, expiry_weekday: str = "Thursday") -> int:
    return (next_expiry(d, expiry_weekday) - _as_date(d)).days


def years_to_expiry(d, expiry_weekday: str = "Thursday", day_count: int = 365) -> float:
    return days_to_expiry(d, expiry_weekday) / day_count