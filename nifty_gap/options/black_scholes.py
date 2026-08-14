"""Black-Scholes-Merton pricing for European options (NIFTY uses European)."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

_CALL_TYPES = frozenset({"CE", "CALL", "C"})
_PUT_TYPES = frozenset({"PE", "PUT", "P"})


def black_scholes(S, K, T, sigma, r, option_type="CE") -> float:
    if S <= 0 or K <= 0 or sigma <= 0:
        raise ValueError("S, K, and sigma must be positive")
    dtype = str(option_type).upper()
    if dtype not in _CALL_TYPES and dtype not in _PUT_TYPES:
        raise ValueError(f"unsupported option_type: {option_type!r}")
    if T <= 0:
        if dtype in _CALL_TYPES:
            return max(S - K, 0.0)
        return max(K - S, 0.0)
    d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if dtype in _CALL_TYPES:
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)