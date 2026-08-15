"""GTT-style ratcheting ladder on the premium's own % move from entry.

Two-sided: loss stops cascade down (-3%/-5%/-7%), profit floors trail up
(+5%/+10%/+15%). Exit at the banked floor, a loss stop, or expiry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LadderExit:
    exit_reason: str
    exit_premium: float
    exit_index: int
    floor_level: float | None = None


def _floor_reason(level, floor_pcts: tuple[float, float, float]) -> str:
    return f"floor_{int(round(level * 100))}"


def _stop_level(m, stop_pcts: tuple[float, float, float]) -> float:
    return max(stop for stop in stop_pcts if m <= -stop)


def _fill(reason, level, entry_premium, observed, fill_mode):
    if fill_mode != "at_floor":
        return observed
    if reason == "expiry":
        return observed
    if reason.startswith("floor_"):
        return entry_premium * (1.0 + level)
    return entry_premium * (1.0 - level)


def simulate(
    premiums: list[float],
    entry_premium: float,
    floor_pcts: tuple[float, float, float] = (0.05, 0.10, 0.15),
    stop_pcts: tuple[float, float, float] = (0.03, 0.05, 0.07),
    fill_mode: str = "observed_close",
) -> LadderExit:
    if not premiums:
        raise ValueError("premiums must be non-empty")
    if entry_premium <= 0:
        raise ValueError("entry_premium must be positive")

    floor_level = None
    for t in range(1, len(premiums)):
        m = round(premiums[t] / entry_premium - 1.0, 10)
        if m <= -stop_pcts[0]:
            stop_level = _stop_level(m, stop_pcts)
            reason = f"stop_{int(round(stop_level * 100))}"
            return LadderExit(
                reason,
                _fill(reason, stop_level, entry_premium, premiums[t], fill_mode),
                t,
                floor_level,
            )
        if floor_level is not None and m <= floor_level:
            reason = _floor_reason(floor_level, floor_pcts)
            return LadderExit(
                reason,
                _fill(reason, floor_level, entry_premium, premiums[t], fill_mode),
                t,
                floor_level,
            )
        if floor_level is None and m >= floor_pcts[0]:
            floor_level = floor_pcts[0]
        for level in floor_pcts[1:]:
            if floor_level is not None and floor_level < level and m >= level:
                floor_level = level

    last = len(premiums) - 1
    return LadderExit("expiry", premiums[last], last, floor_level)
