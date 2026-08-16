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
    excluded = set(snap["config"]["excluded_pairs"])
    assert excluded <= set(snap["config"]["pair_universe"])
    traded = {t["pair"] for t in snap["trades"]}
    assert traded
    assert traded.isdisjoint(excluded)


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


def test_recompute_default_restores_snapshot():
    client.post("/api/recompute", json={})
    assert _snapshot()["trade_stats"]["n_trades"] > 0


def test_recompute_excluding_one_pair_drops_its_trades():
    client.post("/api/recompute", json={})
    base = _snapshot()
    traded = sorted({t["pair"] for t in base["trades"]})
    drop = traded[0]
    try:
        rec = client.post(
            "/api/recompute", json={"excluded_pairs": sorted(base["config"]["excluded_pairs"]) + [drop]}
        ).json()
        assert drop not in {t["pair"] for t in rec["trades"]}
        assert len(rec["trades"]) < len(base["trades"])
    finally:
        client.post("/api/recompute", json={})


def test_recompute_all_pairs_excluded_returns_zero_trades():
    import json as _json

    client.post("/api/recompute", json={})
    base = _snapshot()
    try:
        rec = client.post(
            "/api/recompute", json={"excluded_pairs": list(base["config"]["pair_universe"])}
        ).json()
        assert rec["trade_stats"]["n_trades"] == 0
        assert rec["trades"] == []
        assert rec["trade_stats"]["win_rate"] is None
        _json.dumps(rec)  # no bare NaN
    finally:
        client.post("/api/recompute", json={})


def test_recompute_stale_seq_dropped_server_side():
    client.post("/api/recompute", json={"seq": 1})
    current = client.post("/api/recompute", json={"seq": 2, "iv_flat": 0.11}).json()
    stale = client.post("/api/recompute", json={"seq": 1, "iv_flat": 0.05}).json()
    assert stale["config"]["iv_flat"] == current["config"]["iv_flat"]
    assert stale["trade_stats"] == current["trade_stats"]


def test_recompute_updates_global_snapshot():
    client.post("/api/recompute", json={})
    client.post("/api/recompute", json={"iv_flat": 0.11})
    assert _snapshot()["config"]["iv_flat"] == 0.11
    client.post("/api/recompute", json={})


def test_pair_chips_render_from_universe():
    import re

    resp = client.get("/")
    snap = _snapshot()
    for pair in snap["config"]["pair_universe"]:
        assert f'value="{pair}"' in resp.text
    for m in re.finditer(
        r'<label class="pair-chip"><input type="checkbox" value="([^"]+)"( checked)?>',
        resp.text,
    ):
        pair, checked = m.groups()
        assert (checked is not None) == (pair not in snap["config"]["excluded_pairs"])


def test_dashboard_aria_sort_initial_state():
    resp = client.get("/")
    assert 'data-sort="entry_date" aria-sort="descending"' in resp.text


def test_dashboard_script_delimiters_balanced():
    import re

    resp = client.get("/")
    m = re.search(r"<script>\n(.*?)</script>", resp.text, re.S)
    assert m
    src = m.group(1)
    code = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if src[i : i + 2] == "//":
            j = src.find("\n", i)
            i = j if j != -1 else n
            continue
        if src[i : i + 2] == "/*":
            j = src.find("*/", i)
            i = j + 2 if j != -1 else n
            continue
        if c in "\"'`":
            q = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q:
                    break
                i += 1
            i += 1
            continue
        code.append(c)
        i += 1
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in code:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            assert stack and stack[-1] == pairs[ch], f"unbalanced {ch}"
            stack.pop()
    assert not stack


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