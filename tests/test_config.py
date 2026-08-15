"""Config tests: resolved defaults and registry completeness."""

from __future__ import annotations

from nifty_gap.config import Config, print_config


def test_defaults():
    cfg = Config()
    assert cfg.iv_flat == 0.125
    assert cfg.rate_default == 0.065
    assert cfg.expiry_weekday == "Thursday"
    assert cfg.strike_interval == 50
    assert cfg.lot_size == 75
    assert cfg.min_pair_sample == 5
    assert cfg.ladder_floor_pcts == (0.05, 0.10, 0.15)
    assert cfg.ladder_stop_pcts == (0.03, 0.05, 0.07)
    assert cfg.ladder_fill_mode == "observed_close"
    assert cfg.refresh_provider_order == ("nse", "yfinance")
    assert cfg.validation_mode == "full_sample"


def test_z_score():
    assert abs(Config().z_score - 1.959963984540054) < 1e-6


def test_print_config():
    out = print_config()
    assert "iv_flat = 0.125" in out
    assert "lot_size = 75" in out