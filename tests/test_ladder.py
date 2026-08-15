"""Exit-ladder state machine tests (two-sided: profit floors trail, loss stops cascade)."""

from __future__ import annotations

import pytest

from nifty_gap.trade.ladder import simulate


def test_floor_5_banked_then_dip():
    result = simulate([100, 105, 104], 100)
    assert result.exit_reason == "floor_5"
    assert result.exit_index == 2
    assert result.exit_premium == pytest.approx(104)
    assert result.floor_level == pytest.approx(0.05)
    at_floor = simulate([100, 105, 104], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(105)


def test_floor_10_banked_then_reversal():
    result = simulate([100, 105, 110, 109], 100)
    assert result.exit_reason == "floor_10"
    assert result.exit_index == 3
    assert result.exit_premium == pytest.approx(109)
    at_floor = simulate([100, 105, 110, 109], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(110)


def test_floor_15_banked_then_dip():
    result = simulate([100, 105, 110, 115, 114], 100)
    assert result.exit_reason == "floor_15"
    assert result.exit_index == 4
    assert result.exit_premium == pytest.approx(114)
    assert result.floor_level == pytest.approx(0.15)
    at_floor = simulate([100, 105, 110, 115, 114], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(115)


def test_floor_15_trails_above_banked_level():
    result = simulate([100, 105, 115, 116, 113], 100)
    assert result.exit_reason == "floor_15"
    assert result.exit_index == 4
    assert result.exit_premium == pytest.approx(113)


def test_retired_floors_floor_10_beats_floor_5():
    result = simulate([100, 110, 106], 100)
    assert result.exit_reason == "floor_10"
    assert result.exit_index == 2
    assert result.exit_premium == pytest.approx(106)


def test_stop_3():
    result = simulate([100, 97], 100)
    assert result.exit_reason == "stop_3"
    assert result.exit_index == 1
    assert result.exit_premium == pytest.approx(97)
    at_floor = simulate([100, 97], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(97.0)


def test_stop_5():
    result = simulate([100, 94], 100)
    assert result.exit_reason == "stop_5"
    assert result.exit_index == 1
    assert result.exit_premium == pytest.approx(94)
    at_floor = simulate([100, 94], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(95.0)


def test_stop_7():
    result = simulate([100, 92], 100)
    assert result.exit_reason == "stop_7"
    assert result.exit_index == 1
    assert result.exit_premium == pytest.approx(92)
    at_floor = simulate([100, 92], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(93.0)


def test_stop_wins_over_banked_floor():
    result = simulate([100, 105, 92], 100)
    assert result.exit_reason == "stop_7"
    assert result.exit_index == 2
    assert result.exit_premium == pytest.approx(92)
    assert result.floor_level == pytest.approx(0.05)


def test_never_triggering_held_to_expiry():
    result = simulate([100, 102, 101, 99], 100)
    assert result.exit_reason == "expiry"
    assert result.exit_index == 3
    assert result.exit_premium == pytest.approx(99)
    assert result.floor_level is None
    at_floor = simulate([100, 102, 101, 99], 100, fill_mode="at_floor")
    assert at_floor.exit_premium == pytest.approx(99)


def test_single_observation_held_to_expiry():
    result = simulate([100], 100)
    assert result.exit_reason == "expiry"
    assert result.exit_index == 0
    assert result.exit_premium == pytest.approx(100)
    assert result.floor_level is None


def test_dip_above_banked_floor_then_ratchet():
    result = simulate([100, 112, 110.5, 116], 100)
    assert result.exit_reason == "expiry"
    assert result.exit_index == 3
    assert result.exit_premium == pytest.approx(116)
    assert result.floor_level == pytest.approx(0.15)


def test_inexact_floats_decisive():
    result = simulate([100, 105.0000001, 104.995], 100)
    assert result.exit_reason == "floor_5"
    assert result.exit_index == 2
    assert result.exit_premium == pytest.approx(104.995)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        simulate([], 100)
    with pytest.raises(ValueError):
        simulate([100], 0)
    with pytest.raises(ValueError):
        simulate([100], -1.0)
