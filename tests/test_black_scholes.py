"""Phase 5: Black-Scholes pricer tests."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from nifty_gap.options.black_scholes import black_scholes


def test_hull_golden_reference():
    assert black_scholes(42, 40, 0.5, 0.20, 0.10, "CE") == pytest.approx(4.7594, rel=1e-3)


def test_call_put_parity():
    for S, K, r, sigma, T in itertools.product(
        (42, 100, 24500),
        (40, 95, 24600),
        (0.0, 0.065, 0.10),
        (0.1, 0.2, 0.3),
        (1 / 365, 7 / 365, 0.5),
    ):
        call = black_scholes(S, K, T, sigma, r, "CE")
        put = black_scholes(S, K, T, sigma, r, "PE")
        assert abs(call - put - (S - K * np.exp(-r * T))) < 1e-6


def test_zero_time_to_expiry_intrinsic():
    assert black_scholes(25000, 24600, 0.0, 0.2, 0.065, "CE") == 400
    assert black_scholes(25000, 24600, 0.0, 0.2, 0.065, "PE") == 0
    assert black_scholes(24000, 24600, 0.0, 0.2, 0.065, "CE") == 0
    assert black_scholes(24000, 24600, 0.0, 0.2, 0.065, "PE") == 600
    assert black_scholes(24600, 24600, 0.0, 0.2, 0.065, "CE") == 0
    assert black_scholes(24600, 24600, 0.0, 0.2, 0.065, "PE") == 0


def test_negative_time_to_expiry_is_intrinsic():
    assert black_scholes(24000, 24600, -1.0, 0.2, 0.065, "PE") == 600


def test_deep_otm_premium_approx_zero():
    assert black_scholes(100, 500, 0.5, 0.2, 0.065, "CE") == pytest.approx(0.0, abs=1e-9)
    assert black_scholes(500, 100, 0.5, 0.2, 0.065, "PE") == pytest.approx(0.0, abs=1e-9)


def test_monotonicity():
    for sigma in (0.1, 0.2):
        calls = [black_scholes(S, 300, 0.5, sigma, 0.065, "CE") for S in (100, 200, 500)]
        puts = [black_scholes(S, 300, 0.5, sigma, 0.065, "PE") for S in (100, 200, 500)]
        assert calls[0] < calls[1] < calls[2]
        assert puts[0] > puts[1] > puts[2]
    for option_type in ("CE", "PE"):
        prices = [
            black_scholes(300, 300, 0.5, sigma, 0.065, option_type)
            for sigma in (0.05, 0.2, 0.5)
        ]
        assert prices[0] < prices[1] < prices[2]


def test_option_type_aliases_case_insensitive():
    call = black_scholes(100, 105, 0.25, 0.2, 0.065, "CE")
    put = black_scholes(100, 105, 0.25, 0.2, 0.065, "PE")
    for alias in ("call", "C", "ce"):
        assert black_scholes(100, 105, 0.25, 0.2, 0.065, alias) == pytest.approx(call)
    for alias in ("put", "P", "pe"):
        assert black_scholes(100, 105, 0.25, 0.2, 0.065, alias) == pytest.approx(put)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        black_scholes(0, 100, 0.5, 0.2, 0.065)
    with pytest.raises(ValueError):
        black_scholes(-100, 100, 0.5, 0.2, 0.065)
    with pytest.raises(ValueError):
        black_scholes(100, 0, 0.5, 0.2, 0.065)
    with pytest.raises(ValueError):
        black_scholes(100, 100, 0.5, 0, 0.065)


def test_bad_option_type_raises():
    with pytest.raises(ValueError):
        black_scholes(100, 100, 0.5, 0.2, 0.05, "WE")