"""ATM strike routing to the nearest interval multiple."""

from __future__ import annotations

import math

_TIE_RULES = frozenset({"half-up", "half-down"})


def nearest_strike(price, interval: int = 50, tie_rule: str = "half-up") -> int:
    if price <= 0:
        raise ValueError("price must be positive")
    if interval <= 0:
        raise ValueError("interval must be positive")
    if tie_rule not in _TIE_RULES:
        raise ValueError(f"unsupported tie_rule: {tie_rule!r}")
    x = price / interval
    if tie_rule == "half-up":
        return math.floor(x + 0.5) * interval
    return math.ceil(x - 0.5) * interval