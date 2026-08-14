"""Risk-free rate sourcing: env override, otherwise default."""

from __future__ import annotations

import os

_ENV_VAR = "NIFTY_GAP_RATE"


def get_risk_free_rate(rate_default: float = 0.065) -> float:
    raw = os.environ.get(_ENV_VAR)
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return rate_default