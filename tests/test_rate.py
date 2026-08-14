"""Risk-free rate sourcing tests."""

from __future__ import annotations

from nifty_gap.options.rate import get_risk_free_rate


def test_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("NIFTY_GAP_RATE", raising=False)
    assert get_risk_free_rate() == 0.065


def test_env_override(monkeypatch):
    monkeypatch.setenv("NIFTY_GAP_RATE", "0.07")
    assert get_risk_free_rate() == 0.07


def test_custom_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("NIFTY_GAP_RATE", raising=False)
    assert get_risk_free_rate(0.08) == 0.08


def test_unparseable_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("NIFTY_GAP_RATE", "not-a-number")
    assert get_risk_free_rate() == 0.065