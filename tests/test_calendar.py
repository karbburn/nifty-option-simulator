"""Phase 5: weekly expiry calendar tests."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from nifty_gap.options.calendar import days_to_expiry, next_expiry, years_to_expiry


def test_next_expiry_thursday():
    cases = [
        (date(2026, 8, 10), date(2026, 8, 13)),
        (date(2026, 8, 11), date(2026, 8, 13)),
        (date(2026, 8, 12), date(2026, 8, 13)),
        (date(2026, 8, 13), date(2026, 8, 20)),
        (date(2026, 8, 14), date(2026, 8, 20)),
    ]
    for d, expected in cases:
        assert next_expiry(d) == expected


def test_next_expiry_custom_weekday():
    assert next_expiry(date(2026, 8, 10), "Friday") == date(2026, 8, 14)


def test_all_valid_weekdays():
    expected = {
        "Monday": date(2026, 8, 17),
        "Tuesday": date(2026, 8, 11),
        "Wednesday": date(2026, 8, 12),
        "Thursday": date(2026, 8, 13),
        "Friday": date(2026, 8, 14),
    }
    for name, expiry in expected.items():
        assert next_expiry(date(2026, 8, 10), name) == expiry


def test_days_and_years_to_expiry():
    d = date(2026, 8, 10)
    assert days_to_expiry(d) == (next_expiry(d) - d).days
    assert days_to_expiry(d) == 3
    assert years_to_expiry(d) == pytest.approx(3 / 365)


def test_input_types():
    d = date(2026, 8, 10)
    assert next_expiry(datetime(2026, 8, 10, 15, 30)) == next_expiry(d)
    assert next_expiry(pd.Timestamp("2026-08-10")) == next_expiry(d)
    assert days_to_expiry(pd.Timestamp("2026-08-10")) == days_to_expiry(d)
    assert years_to_expiry(datetime(2026, 8, 10, 15, 30)) == years_to_expiry(d)


def test_bad_expiry_weekday():
    with pytest.raises(ValueError):
        next_expiry(date(2026, 8, 10), "Saturday")