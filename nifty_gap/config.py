"""Single source of truth for all simulation parameters."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    iv_flat: float = 0.125
    rate_source: str = "config"
    rate_default: float = 0.065
    expiry_weekday: str = "Thursday"
    strike_interval: int = 50
    strike_tie_rule: str = "half-up"
    lot_size: int = 75
    min_pair_sample: int = 5
    ci_alpha: float = 0.05
    validation_mode: str = "full_sample"
    position_mode: str = "fixed_lot"
    ladder_sl_pct: float = -0.07
    ladder_floor_pcts: tuple[float, float, float] = (0.03, 0.05, 0.10)
    ladder_target_pct: float = 0.15
    ladder_fill_mode: str = "observed_close"
    data_path: Path = PROJECT_ROOT / "assets" / "NIFTY 50-14-08-2025-to-14-08-2026.csv"
    data_history_path: Path = PROJECT_ROOT / "data" / "nifty50_history.csv"
    refresh_provider_order: tuple[str, ...] = ("nse", "yfinance")

    @property
    def z_score(self) -> float:
        from scipy.stats import norm

        return norm.ppf(1 - self.ci_alpha / 2)


def print_config() -> str:
    cfg = Config()
    lines = [f"{f.name} = {getattr(cfg, f.name)!r}" for f in fields(cfg)]
    return "\n".join(lines)