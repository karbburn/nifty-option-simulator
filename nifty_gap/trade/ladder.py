"""GTT-style ratcheting trailing ladder on the premium's own % move from entry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LadderExit:
    exit_reason: str
    exit_premium: float
    exit_index: int
    floor_level: float | None = None


def _reason_name(level, level3, level5):
    if level == level3:
        return "floor_3"
    if level == level5:
        return "floor_5"
    return "floor_10"


def _fill(reason, level, entry_premium, sl_pct, target_pct, observed, fill_mode):
    if fill_mode != "at_floor":
        return observed
    if reason == "SL":
        return entry_premium * (1.0 + sl_pct)
    if reason == "target_15":
        return entry_premium * (1.0 + target_pct)
    if reason == "expiry":
        return observed
    return entry_premium * (1.0 + level)


def simulate(
    premiums: list[float],
    entry_premium: float,
    sl_pct: float = -0.07,
    floor_pcts: tuple[float, float, float] = (0.03, 0.05, 0.10),
    target_pct: float = 0.15,
    fill_mode: str = "observed_close",
) -> LadderExit:
    if not premiums:
        raise ValueError("premiums must be non-empty")
    if entry_premium <= 0:
        raise ValueError("entry_premium must be positive")

    level3, level5, level10 = floor_pcts
    floor_level = None
    for t in range(1, len(premiums)):
        m = premiums[t] / entry_premium - 1.0
        if m <= sl_pct:
            return LadderExit(
                "SL",
                _fill("SL", None, entry_premium, sl_pct, target_pct, premiums[t], fill_mode),
                t,
                floor_level,
            )
        if floor_level == level10 and m >= target_pct:
            return LadderExit(
                "target_15",
                _fill("target_15", floor_level, entry_premium, sl_pct, target_pct, premiums[t], fill_mode),
                t,
                floor_level,
            )
        if floor_level is not None and m <= floor_level:
            name = _reason_name(floor_level, level3, level5)
            return LadderExit(
                name,
                _fill(name, floor_level, entry_premium, sl_pct, target_pct, premiums[t], fill_mode),
                t,
                floor_level,
            )
        if floor_level is None and m >= level3:
            floor_level = level3
        if floor_level == level3 and m >= level5:
            floor_level = level5
        if floor_level == level5 and m >= level10:
            floor_level = level10

    last = len(premiums) - 1
    return LadderExit("expiry", premiums[last], last, floor_level)