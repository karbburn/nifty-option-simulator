from fastapi.testclient import TestClient

from nifty_gap.web.app import app

client = TestClient(app)


def _snapshot() -> dict:
    return client.get("/api/dashboard").json()


def test_health():
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard_snapshot():
    snap = _snapshot()
    assert snap["last_trading_date"] >= "2026-01-01"
    assert len(snap["trades"]) > 100
    assert snap["trade_stats"]["total_pnl"] > 0


def test_api_spot():
    resp = client.get("/api/spot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["spot"] > 20000
    assert data["source"] in ("yfinance", "history")


def test_api_live_positions_default():
    resp = client.get("/api/live-positions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for p in data:
        assert "side" in p and "strike" in p and "live_pnl" in p


def test_api_live_positions_with_spot():
    resp = client.get("/api/live-positions", params={"spot": 24000})
    assert resp.status_code == 200
    data = resp.json()
    for p in data:
        assert isinstance(p["live_pnl"], (int, float))
        assert isinstance(p["pct_move"], (int, float))


def test_dashboard_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "NIFTY Gap Dashboard" in resp.text
    assert "Live Positions" in resp.text


def test_dashboard_page_mobile_layout_meta():
    resp = client.get("/")
    assert 'name="viewport"' in resp.text
    assert 'content="width=device-width, initial-scale=1, viewport-fit=cover"' in resp.text
    assert "bottom-nav" in resp.text
    assert "data-tab=" in resp.text


def test_dashboard_page_has_theme_color():
    resp = client.get("/")
    assert 'name="theme-color"' in resp.text
    assert "Chart" in resp.text


def test_trade_page():
    snap = _snapshot()
    entry = snap["trades"][0]["entry_date"]
    resp = client.get(f"/trade/{entry}")
    assert resp.status_code == 200
    assert "Premium Path" in resp.text


def test_trade_page_404():
    resp = client.get("/trade/1999-01-01")
    assert resp.status_code == 404


def test_expiry_page():
    resp = client.get("/expiry")
    assert resp.status_code == 200
    assert "Expiry Weekday Pairs" in resp.text


def test_static_favicon():
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    resp2 = client.get("/static/favicon.ico")
    assert resp2.status_code == 200
    resp3 = client.get("/static/icon-192.png")
    assert resp3.status_code == 200


def test_snapshot_legs_are_dicts():
    snap = _snapshot()
    for t in snap["trades"]:
        for leg in t["legs"]:
            assert isinstance(leg, dict)
            assert "entry_premium" in leg


def test_json_dumpable():
    import json as _json

    snap = _snapshot()
    _json.dumps(snap)  # must not raise


def test_recompute_default_matches_snapshot():
    base = _snapshot()
    rec = client.post("/api/recompute", json={}).json()
    assert rec["trade_stats"]["total_pnl"] == base["trade_stats"]["total_pnl"]
    assert len(rec["trades"]) == len(base["trades"])


def test_recompute_applies_costs():
    base = client.post("/api/recompute", json={}).json()
    costed = client.post(
        "/api/recompute", json={"brokerage_per_trade": 40, "slippage_pct": 0.005}
    ).json()
    assert costed["trade_stats"]["total_pnl"] < base["trade_stats"]["total_pnl"]


def test_recompute_changes_config():
    rec = client.post("/api/recompute", json={"iv_flat": 0.11}).json()
    assert rec["config"]["iv_flat"] == 0.11


def test_recompute_bad_excluded_pair_list():
    rec = client.post("/api/recompute", json={"excluded_pairs": ["Fri→Mon", "Tue→Wed"]}).json()
    assert rec["config"]["excluded_pairs"] == ["Fri→Mon", "Tue→Wed"]


def test_report_charts_served():
    for name in ("probability", "exit_reasons", "equity", "benchmark", "oos"):
        resp = client.get(f"/charts/{name}.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/")


def test_dashboard_page_has_config_explorer():
    resp = client.get("/")
    assert "Config Explorer" in resp.text
    assert "cfgApply" in resp.text
    assert "cfgRefresh" in resp.text
    assert "themeToggle" in resp.text


def test_dashboard_page_has_report_gallery():
    resp = client.get("/")
    assert "Equity Curve" in resp.text
    assert "Exit Reasons" in resp.text
    assert "/charts/equity.png" in resp.text


def test_dashboard_table_filters_present():
    resp = client.get("/")
    assert "filterDateFrom" in resp.text
    assert "filterPnlMin" in resp.text
    assert "filterDaysMin" in resp.text


def test_refresh_endpoint_structure():
    resp = client.post("/api/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "rows_added" in data