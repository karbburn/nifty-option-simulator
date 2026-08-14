"""Nearest strike router tests."""

from __future__ import annotations

import pytest

from nifty_gap.options.strikes import nearest_strike


def test_half_up_default():
    assert nearest_strike(24725) == 24750
    assert nearest_strike(24724.99) == 24700
    assert nearest_strike(24361.9) == 24350
    assert nearest_strike(24600) == 24600
    assert nearest_strike(24575) == 24600


def test_half_down_tie():
    assert nearest_strike(24575, tie_rule="half-down") == 24550


def test_invalid_inputs():
    with pytest.raises(ValueError):
        nearest_strike(0)
    with pytest.raises(ValueError):
        nearest_strike(-100)
    with pytest.raises(ValueError):
        nearest_strike(100, interval=0)
    with pytest.raises(ValueError):
        nearest_strike(100, tie_rule="banker")