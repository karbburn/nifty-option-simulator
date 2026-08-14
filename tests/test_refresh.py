"""Phase 3: refresh pipeline tests (fully offline)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from nifty_gap.data import refresh
from nifty_gap.data.loader import load_history

EXPECTED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Shares_Traded", "Turnover_Cr", "data_source"]

BASE_DATES = ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"]


def _frame(dates, source="nse"):
    n = len(dates)
    if source == "nse":
        shares = pd.array([100000 + i for i in range(n)], dtype="Int64")
        turnover = [100.0 + i for i in range(n)]
    else:
        shares = pd.array([pd.NA] * n, dtype="Int64")
        turnover = [np.nan] * n
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(dates),
            "Open": [24500.0 + i for i in range(n)],
            "High": [24600.0 + i for i in range(n)],
            "Low": [24400.0 + i for i in range(n)],
            "Close": [24550.0 + i for i in range(n)],
            "Shares_Traded": shares,
            "Turnover_Cr": turnover,
            "data_source": [source] * n,
        }
    )


def test_normalise_yfinance_flattens_and_drops_bad_volume():
    dates = pd.date_range("2026-08-11", periods=4, freq="B")
    raw = pd.DataFrame(
        {
            ("Open", "^NSEI"): [24500.0, 24550.0, 24600.0, 24650.0],
            ("High", "^NSEI"): [24600.0, 24650.0, 24700.0, 24750.0],
            ("Low", "^NSEI"): [24400.0, 24450.0, 24500.0, 24550.0],
            ("Close", "^NSEI"): [24550.0, 24600.0, 24650.0, 24700.0],
            ("Volume", "^NSEI"): [1000.0, 0.0, 2000.0, np.nan],
        },
        index=dates,
    )
    out = refresh.normalise_yfinance(raw)
    assert list(out.columns) == EXPECTED_COLUMNS
    assert len(out) == 2
    assert out["Date"].tolist() == [pd.Timestamp("2026-08-11"), pd.Timestamp("2026-08-13")]
    assert out["Open"].dtype == np.float64
    assert out["Close"].dtype == np.float64
    assert str(out["Shares_Traded"].dtype) == "Int64"
    assert out["Shares_Traded"].isna().all()
    assert out["Turnover_Cr"].isna().all()
    assert (out["data_source"] == "yfinance").all()
    assert out.iloc[0]["Close"] == pytest.approx(24550.0)


def test_normalise_yfinance_drops_timezone():
    tz = dt.timezone(dt.timedelta(hours=-4))
    idx = pd.DatetimeIndex(["2026-08-11 00:30:00"], tz=tz)
    raw = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100.0]},
        index=idx,
    )
    out = refresh.normalise_yfinance(raw)
    assert out["Date"].iloc[0] == pd.Timestamp("2026-08-11")
    assert out["Date"].dt.tz is None


def test_normalise_yfinance_empty_frame():
    out = refresh.normalise_yfinance(pd.DataFrame())
    assert out.empty
    assert list(out.columns) == EXPECTED_COLUMNS
    assert str(out["Shares_Traded"].dtype) == "Int64"
    assert out["data_source"].dtype == object


def test_upsert_appends_sorts_and_keeps_existing():
    history = _frame(BASE_DATES)
    history.loc[history["Date"] == pd.Timestamp("2026-08-14"), "Close"] = 24500.0
    new = _frame(["2026-08-14", "2026-08-17"])
    merged = refresh.upsert(history, new)
    assert merged["Date"].is_monotonic_increasing
    assert merged["Date"].is_unique
    assert list(merged.index) == list(range(len(merged)))
    assert len(merged) == 6
    assert merged["Date"].tolist() == [pd.Timestamp(d) for d in BASE_DATES + ["2026-08-17"]]
    aug14 = merged[merged["Date"] == pd.Timestamp("2026-08-14")]
    assert aug14["Close"].iloc[0] == pytest.approx(24500.0)


def test_run_refresh_appends_new_row_and_writes(tmp_path, monkeypatch):
    def fake_seed(history_path, seed_path):
        return _frame(BASE_DATES)

    monkeypatch.setattr(refresh, "seed_history", fake_seed)
    monkeypatch.setattr(refresh, "fetch_nse", lambda f, t: _frame(["2026-08-17"]))
    hp = tmp_path / "history.csv"
    result = refresh.run_refresh(hp, tmp_path / "seed.csv", to_date=dt.date(2026, 8, 17))
    assert result["status"] == "ok"
    assert result["provider"] == "nse"
    assert result["rows_added"] == 1
    assert result["window_start"] == "2026-08-15"
    assert result["window_end"] == "2026-08-17"
    loaded = load_history(hp)
    assert loaded is not None
    assert len(loaded) == 6
    assert dt.date(2026, 8, 17) in loaded["Date"].dt.date.tolist()


def test_run_refresh_falls_back_to_yfinance(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "seed_history", lambda hp, sp: _frame(BASE_DATES))
    monkeypatch.setattr(refresh, "fetch_nse", lambda f, t: None)
    monkeypatch.setattr(refresh, "fetch_yfinance", lambda f, t: _frame(["2026-08-17", "2026-08-18"], source="yfinance"))
    hp = tmp_path / "history.csv"
    result = refresh.run_refresh(hp, tmp_path / "seed.csv", to_date=dt.date(2026, 8, 18))
    assert result["status"] == "ok"
    assert result["provider"] == "yfinance"
    assert result["rows_added"] == 2


def test_run_refresh_warns_when_all_providers_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "seed_history", lambda hp, sp: _frame(BASE_DATES))
    monkeypatch.setattr(refresh, "fetch_nse", lambda f, t: None)
    monkeypatch.setattr(refresh, "fetch_yfinance", lambda f, t: _frame([], source="yfinance"))
    hp = tmp_path / "history.csv"
    result = refresh.run_refresh(hp, tmp_path / "seed.csv", to_date=dt.date(2026, 8, 17))
    assert result["status"] == "warn"
    assert result["rows_added"] == 0
    assert result["provider"] is None
    assert result["reason"] == "all providers failed"
    assert not hp.exists()


def test_run_refresh_noop_when_start_after_end(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "seed_history", lambda hp, sp: _frame(BASE_DATES))
    hp = tmp_path / "history.csv"
    result = refresh.run_refresh(hp, tmp_path / "seed.csv", to_date=dt.date(2026, 8, 14))
    assert result["status"] == "noop"
    assert result["rows_added"] == 0
    assert result["provider"] is None
    assert not hp.exists()


def test_main_returns_zero_on_warn(monkeypatch, capsys):
    result = {
        "status": "warn",
        "rows_added": 0,
        "provider": None,
        "reason": "all providers failed",
        "window_start": "2026-08-15",
        "window_end": "2026-08-15",
    }
    monkeypatch.setattr(refresh, "run_refresh", lambda *a, **k: result)
    assert refresh.main(["refresh"]) == 0
    assert '"status": "warn"' in capsys.readouterr().out


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, page, api):
        self._page = page
        self._api = api

    def get(self, url, params=None, headers=None):
        if "indicesHistory" in str(url) or (params and "indicesHistory" in str(params)):
            return self._api
        return self._page


def test_fetch_nse_returns_data_on_200(monkeypatch):
    payload = {
        "indexName": "NIFTY 50",
        "indexHistoricalData": [
            {
                "OPEN": "24641.00",
                "HIGH": "24677.05",
                "LOW": "24604.15",
                "CLOSE": "24636.00",
                "SHARES_TRADED": "344001180",
                "TURNOVER": "30115.41",
                "TIMESTAMP": "13-Aug-2026",
            }
        ],
    }
    fake = _FakeSession(_FakeResponse(200, payload), _FakeResponse(200, payload))
    monkeypatch.setattr(refresh, "_nse_session", lambda timeout=20: fake)
    df = refresh.fetch_nse(dt.date(2026, 8, 13), dt.date(2026, 8, 14))
    assert df is not None
    assert len(df) == 1
    assert df["Date"].iloc[0] == pd.Timestamp("2026-08-13")
    assert df["Close"].iloc[0] == pytest.approx(24636.0)
    assert df["data_source"].iloc[0] == "nse"


def test_fetch_nse_returns_none_on_503(monkeypatch):
    fake = _FakeSession(_FakeResponse(200), _FakeResponse(503))
    monkeypatch.setattr(refresh, "_nse_session", lambda timeout=20: fake)
    assert refresh.fetch_nse(dt.date(2026, 8, 13), dt.date(2026, 8, 14)) is None