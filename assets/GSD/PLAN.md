# NIFTY Option Simulator — Web Dashboard Plan

## Goal

Add a single-user web dashboard that serves pre-computed backtest results as interactive HTML charts (Chart.js via CDN) and live-marks open positions to real-time NIFTY spot. The nightly GitHub Action refreshes data AND regenerates a `dashboard.json` snapshot; Render serves the FastAPI app that displays it. No Node build step, no frontend framework — just Python, Jinja2, and CDN Chart.js.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Nightly (GitHub Action, 11:30 UTC)                        │
│                                                             │
│  data/refresh.py ──→ data/nifty50_history.csv               │
│         │                                                    │
│         └──→ nifty_gap/web/snapshot.py                      │
│                  ├── run_backtest()                          │
│                  ├── build_probability_table()               │
│                  ├── oos_diagnostic()                        │
│                  └── benchmark equity (hold mode)            │
│                       │                                      │
│                       ▼                                      │
│                  output/dashboard.json                       │
│                       │                                      │
│                       ▼ (git commit + push)                  │
│              Render auto-deploy                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Render Web Service (uvicorn)                               │
│                                                             │
│  nifty_gap/web/app.py                                       │
│    ├── GET /           → dashboard.html (Jinja2)            │
│    ├── GET /trade/{d}  → trade.html (premium path chart)    │
│    ├── GET /expiry     → expiry.html (explainer)            │
│    ├── GET /api/dashboard → JSON (full snapshot)            │
│    ├── GET /api/live-positions?spot=X → live positions      │
│    ├── GET /api/spot   → {spot, source, as_of}              │
│    └── GET /health     → {status: ok}                       │
│                                                             │
│  Startup: load snapshot; generate if missing                │
│  /api/spot: yfinance ^NSEI → fallback to last history close │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│                                                             │
│  dashboard.html                                             │
│    ├── Header: NIFTY spot ticker (polls /api/spot)          │
│    ├── Live Positions card (re-marked on spot fetch)        │
│    ├── Past Trades table (client-side sort/filter)          │
│    ├── Equity Curve chart (Chart.js line)                   │
│    ├── Next Trade Preview card                              │
│    └── "Coming soon" placeholders (trade data, CSV)         │
│                                                             │
│  trade.html                                                 │
│    └── Premium path chart (entry line, stop/floor levels)   │
│                                                             │
│  expiry.html                                                │
│    └── Static content explaining ladder mechanics           │
└─────────────────────────────────────────────────────────────┘
```

---

## File Manifest

| File | Action | Purpose |
|------|--------|---------|
| `nifty_gap/web/__init__.py` | Create | Package marker |
| `nifty_gap/web/__main__.py` | Create | CLI entry: `python -m nifty_gap.web.snapshot` calls `generate_snapshot()` |
| `nifty_gap/web/state.py` | Create | Data layer: load history, run backtest, compute live positions, next trade preview, premium series |
| `nifty_gap/web/snapshot.py` | Create | Generate `output/dashboard.json` from state layer (creates `output/` via `Path.mkdir`) |
| `nifty_gap/web/app.py` | Create | FastAPI app, routes, template rendering, `/static` mount |
| `nifty_gap/web/make_favicon.py` | Create | One-time Pillow script: `assets/icon.png` → `nifty_gap/web/static/` favicon files |
| `nifty_gap/web/static/favicon.ico` | Create (generated) | Multi-size ICO (16/32/48), committed |
| `nifty_gap/web/static/apple-touch-icon.png` | Create (generated) | 180×180, committed |
| `nifty_gap/web/static/icon-192.png` | Create (generated) | 192×192, committed |
| `nifty_gap/web/templates/base.html` | Create | Base template: nav, header with spot ticker, favicon links, footer |
| `nifty_gap/web/templates/dashboard.html` | Create | Main dashboard page |
| `nifty_gap/web/templates/trade.html` | Create | Trade detail page with premium path chart |
| `nifty_gap/web/templates/expiry.html` | Create | Expiry explainer page |
| `tests/test_web_state.py` | Create | Unit tests for state layer (live_positions, next_trade, premium_series, spot fallback) |
| `tests/test_web.py` | Create | Integration tests via TestClient (smoke routes, API shapes) |
| `pyproject.toml` | Modify | Add `web = ["fastapi", "uvicorn[standard]", "jinja2"]` to optional deps |
| `.github/workflows/refresh-data.yml` | Modify | Add snapshot generation step after data refresh |
| `README.md` | Modify | Add run/deploy instructions for dashboard |

---

## Formatting Conventions

- **Currency:** `₹{value:,.2f}` (Indian grouping, 2 decimals) for premiums, P&L, equity
- **P&L sign:** `-₹4,865.34` for losses, `₹12,500.00` for gains (sign before currency)
- **Dates:** `{month} {day}` (e.g., "Aug 15") for trade dates in tables; full ISO for timestamps
- **Percentages:** `{value:.1f}%` for win rates, drawdown, etc.
- **Spot ticker:** `₹{value:,.2f}` with flash animation on price change (CSS transition)

---

## Visual Hierarchy

- **Primary:** Live Positions (top of dashboard, real-time spot updates, most dynamic element)
- **Secondary:** Equity Curve (overall performance picture)
- **Tertiary:** Past Trades, Probability/OOS, Benchmark, Next Trade Preview

---

## Accessibility Requirements

- **CE/PE badges:** MUST include text labels alongside color — "CE ▲" / "PE ▼" (not color-only)
- **Charts:** MUST have `aria-label` describing the chart (e.g., "Equity curve showing cumulative P&L from Aug 2025 to Aug 2026")
- **Sort headers:** MUST include `aria-sort="ascending"` / `"descending"` / `"none"`
- **Tables:** MUST use `tabular-nums` font-variant-numeric for aligned numbers
- **Responsive:** CSS Grid with `auto-fit` + `minmax(300px, 1fr)` for card layout; tables wrapped in `overflow-x: auto`

---

## Phase Breakdown

### Phase 1: State/Data Layer

**Goal:** Compute everything the dashboard needs from existing backtest code. No web code yet — pure functions that return dicts/lists.

**Task 1: `state.py` — backtest data layer**

- `load_history_df()` — reads `data/nifty50_history.csv` via existing `load_dataframe()`
- `run_full_backtest(cfg=None)` — runs `build_probability_table`, `run_backtest` (ladder), `run_backtest` (hold for benchmark), `daily_mtm`, `oos_diagnostic`. Returns dict with: `trades`, `trades_df`, `equity`, `equity_hold`, `probability_table`, `oos_data`, `trade_stats`, `equity_stats`
- `compute_premium_series(df, trade, cfg)` — re-computes the daily premium path for a single trade using existing BS engine. Returns `list[float]` (premium at entry + each trading day through exit)
- `compute_live_positions(trades, spot, cfg, today=None)` — for each tradeable pair, takes the most recent trade whose `expiry > today`. Marks entry_premium to live spot via `_mark()`. Returns list of dicts: `{pair, side, strike, entry_date, entry_premium, live_premium, live_pnl, pct_move, banked_floor, days_to_expiry}`
- `compute_next_trade_preview(df, table, spot, cfg, today=None)` — finds the next trading day, checks if its pair is tradeable, computes ATM strike and BS entry premium at spot. Returns dict: `{pair, side, strike, entry_premium, tte, note}`

Files: `nifty_gap/web/state.py`, `tests/test_web_state.py`

**Task 2: `test_web_state.py` — unit tests**

- Test `compute_live_positions`: mock trades list, verify correct pair selection, verify P&L math, verify expiry filtering
- Test `compute_next_trade_preview`: verify correct next pair, verify excluded pairs skipped, verify BS premium calculation
- Test `compute_premium_series`: verify entry premium is first element, verify series length matches trade duration
- Test spot fallback: when spot is None, verify falls back to last history close

Files: `tests/test_web_state.py`

---

### Phase 2: Snapshot Generator

**Goal:** Produce `output/dashboard.json` that the app serves. Entry point for nightly GH Action.

**Task 1: `snapshot.py` — snapshot generator**

- `generate_snapshot(cfg=None, out_path=None)` — calls `run_full_backtest`, `compute_live_positions` (with last history close as spot), `compute_next_trade_preview` (with last history close as spot). Serializes to JSON with: `generated_at`, `last_trading_date`, `git_sha`, `config`, `trade_stats`, `equity_stats`, `trades` (list of dicts from trades_df, with `legs` field included for premium series computation), `equity_curve` (list of `{date, equity}` — rename `Date` → `date` from `daily_mtm()`), `probability_table` (list of dicts), `oos_data` (list of dicts from `metrics.oos_summary(oos_result["oos"])`), `benchmark_equity` (list of `{date, equity}`), `live_positions` (list), `next_trade_preview` (dict)
- CLI entry: `python -m nifty_gap.web.snapshot` calls `generate_snapshot()` and prints result

Files: `nifty_gap/web/snapshot.py`

**Task 2: GH Action wiring**

- Modify `.github/workflows/refresh-data.yml`: after `python -m nifty_gap.data.refresh`, add `pip install -e .[web] && python -m nifty_gap.web.snapshot`
- Both `data/nifty50_history.csv` and `output/dashboard.json` committed together

Files: `.github/workflows/refresh-data.yml`

---

### Phase 3: FastAPI App + API Routes

**Goal:** Serve the dashboard. FastAPI app with JSON API endpoints and HTML pages.

**Task 1: `app.py` — FastAPI app**

- `app = FastAPI(title="NIFTY Gap Dashboard")`
- Mount `StaticFiles` at `/static` → `nifty_gap/web/static/` (serves favicon.ico, apple-touch-icon.png, icon-192.png)
- Startup event: load `output/dashboard.json` into `app.state.snapshot`
- `GET /health` → `{"status": "ok"}`
- `GET /api/dashboard` → return `app.state.snapshot`
- `GET /api/spot` → fetch NIFTY spot via `yf.Ticker("^NSEI").fast_info.last_price`, fallback to last history close from snapshot. Return `{"spot": float, "source": "yfinance"|"history", "as_of": str}`
- `GET /` → render `dashboard.html` with snapshot data + spot
- `GET /trade/{entry_date}` → find trade by entry_date, compute premium series, render `trade.html`
- `GET /expiry` → render `expiry.html` (static content)

Files: `nifty_gap/web/app.py`

**Task 2: `test_web.py` — integration tests**

- TestClient smoke tests for all routes: `/health` returns 200, `/api/dashboard` returns valid JSON with expected keys, `/api/spot` returns spot float, `/` returns 200 with HTML, `/trade/{date}` returns 200, `/expiry` returns 200
- Test 404 for nonexistent trade date

Files: `tests/test_web.py`

---

### Phase 4: Templates + Chart.js

**Goal:** HTML pages with interactive charts. All Chart.js via CDN (no build step). Mobile layout, bottom tab bar, and touch handling are specified in `PLAN-MOBILE.md`.

**Task 1: `base.html` + `dashboard.html`**

- `base.html`: minimal HTML5 skeleton with `<meta name="viewport" content="width=device-width, initial-scale=1">`, favicon links (`<link rel="icon" href="/static/favicon.ico">`, `apple-touch-icon` → `/static/apple-touch-icon.png`, `icon-192` → `/static/icon-192.png`, `theme-color`), nav (Dashboard | Expiry Explainer), header with NIFTY spot ticker (JS fetches `/api/spot` every 60s, CSS flash animation on price change, also calls `/api/live-positions?spot=X` to re-mark position cards), Chart.js CDN script tag, block `content`
- `dashboard.html`:
  - **Live Positions section** (primary visual anchor): card grid with `auto-fit` + `minmax(300px, 1fr)`. Each card shows pair, side badge ("CE ▲" green / "PE ▼" red — text + color, not color-only), strike, entry premium, live premium, live P&L (green/red), % move, banked floor, DTE. Mini Chart.js line chart of premium since entry (5-10 data points). Cards re-marked via `/api/live-positions?spot=X` called by spot ticker JS.
  - **Past Trades section**: HTML table with columns: Entry Date, Exit Date, Pair, Side, Reason, P&L. `aria-sort` on headers. Client-side JS for sort (click headers) and filter (dropdowns for pair, reason). Currency: `₹{value:,.2f}`, P&L: `-₹4,865.34` for losses.
  - **Equity Curve section** (secondary visual anchor): Chart.js line chart from `equity_curve` data. Drawdown shading.
  - **Next Trade Preview section**: card showing next pair, side, ATM strike, entry premium at live spot. Note: "fires on next close if signal confirms."
  - **Probability & OOS section**: Chart.js grouped bar chart (IS p_up vs realized OOS win rate with Wilson CI error bars). `aria-label` on chart container.
  - **Benchmark section**: Chart.js dual-line chart (ladder equity vs hold-to-expiry). `aria-label` on chart container.
  - **Data Freshness badge**: small badge showing `last_trading_date` and `generated_at`. States: fresh (<1 day), stale (1-3 days), old (>3 days).

Files: `nifty_gap/web/templates/base.html`, `nifty_gap/web/templates/dashboard.html`

**Task 2: `trade.html` + `expiry.html`**

- `trade.html`: trade summary header (pair, side, strike, entry/exit dates, P&L, reason). Chart.js line chart of premium path with `aria-label`. Overlay horizontal lines for: entry premium, stop levels (-3%, -5%), floor levels (+5%, +10%, +15%). Vertical line at exit. Color-coded: green zone above entry, red zone below.
- `expiry.html`: static content explaining ladder mechanics. Sections: (1) Exit at first -3%/-5% stop breach, (2) Profit floors trail at +5%/+10%/+15%, (3) Forced exit at Thursday expiry, (4) `ladder_rollover=False` = close at first expiry, (5) Rollover finding: loss-making (-₹76.6k). Uses existing stats from snapshot.

Files: `nifty_gap/web/templates/trade.html`, `nifty_gap/web/templates/expiry.html`

---

### Phase 5: Finalize

**Task 1: Favicon generation**

- Write `nifty_gap/web/make_favicon.py`: reads `assets/icon.png` (2048×2048, gitignored source), resizes via Pillow → writes `nifty_gap/web/static/favicon.ico` (16/32/48 multi-size), `apple-touch-icon.png` (180), `icon-192.png` (192)
- Run once, commit the ~20KB outputs. Render builds from git so favicon must be committed, not generated at deploy.
- Source `assets/icon.png` stays gitignored; only small generated files are committed.

Files: `nifty_gap/web/make_favicon.py`, `nifty_gap/web/static/*`

**Task 2: README + pyproject.toml + final checks**

- Update `README.md`: add "Web Dashboard" section with run instructions (`pip install -e .[web]`, `uvicorn nifty_gap.web.app:app`), deploy instructions (Render), nightly refresh explanation
- Verify `pyproject.toml` has `web = ["fastapi", "uvicorn[standard]", "jinja2"]`
- Run `ruff check .` and `pytest` — fix any issues
- Final commit

Files: `README.md`, `pyproject.toml`

---

## API Contract

### `GET /health`
```json
{"status": "ok"}
```

### `GET /api/dashboard`
Returns the full `dashboard.json` snapshot. Shape:
```json
{
  "generated_at": "2026-08-15T11:30:00Z",
  "last_trading_date": "2026-08-14",
  "git_sha": "abc123def",
  "config": {
    "iv_flat": 0.125,
    "lot_size": 75,
    "ladder_floor_pcts": [0.05, 0.10, 0.15],
    "ladder_stop_pcts": [0.03, 0.05],
    "ladder_rollover": false,
    "excluded_pairs": ["Fri→Mon"]
  },
  "trade_stats": {
    "n_trades": 234,
    "total_pnl": -74139.29,
    "win_rate": 0.248,
    "avg_win": 13485.53,
    "avg_loss": -4865.34,
    "profit_factor": 0.913,
    "exit_reasons": [{"exit_reason": "expiry", "count": 96, "pct": 41.0, "avg_pnl": 5856.43}]
  },
  "equity_stats": {
    "n_days": 246,
    "final_equity": -74139.29,
    "max_drawdown": 217400.29,
    "max_drawdown_pct": 7.28,
    "sharpe_annualized": -0.335
  },
  "trades": [
    {
      "entry_date": "2025-08-18",
      "exit_date": "2025-08-21",
      "pair": "Mon→Tue",
      "side": "CE",
      "strike": 24900.0,
      "entry_close": 24876.95,
      "expiry": "2025-08-21",
      "entry_premium": 107.68,
      "exit_premium": 183.75,
      "exit_reason": "expiry",
      "days_held": 3,
      "pnl": 5705.11,
      "legs": [{"strike": 24900.0, "side": "CE", "premium": 107.68}]
    }
  ],
  "equity_curve": [
    {"date": "2025-08-14", "equity": 0.0},
    {"date": "2025-08-18", "equity": 0.0}
  ],
  "probability_table": [
    {
      "weekday_pair": "Mon→Tue",
      "n": 49,
      "p_up": 0.612,
      "ci_low": 0.472,
      "ci_high": 0.737,
      "side": "CE",
      "tradeable": true
    }
  ],
  "oos_data": [
    {
      "weekday_pair": "Mon→Tue",
      "side": "CE",
      "n_in": 24,
      "p_up": 0.625,
      "ci_low": 0.425,
      "ci_high": 0.791,
      "n_oos": 25,
      "realized_p_up": 0.600,
      "realized_ci_low": 0.406,
      "realized_ci_high": 0.766
    }
  ],
  "benchmark_equity": [
    {"date": "2025-08-14", "equity": 0.0}
  ],
  "live_positions": [
    {
      "pair": "Mon→Tue",
      "side": "CE",
      "strike": 24900.0,
      "entry_date": "2026-08-10",
      "entry_premium": 112.50,
      "live_premium": 125.30,
      "live_pnl": 960.0,
      "pct_move": 11.38,
      "banked_floor": null,
      "days_to_expiry": 4
    }
  ],
  "next_trade_preview": {
    "pair": "Mon→Tue",
    "side": "CE",
    "strike": 24950,
    "entry_premium": 108.22,
    "tte_days": 5,
    "note": "Fires on next close if signal confirms"
  }
}
```

### `GET /api/spot`
```json
{
  "spot": 24950.75,
  "source": "yfinance",
  "as_of": "2026-08-15T10:30:00+05:30"
}
```
Fallback: if yfinance fails or market closed, returns last history close with `"source": "history"`.

### `GET /api/live-positions?spot={float}`
Re-marks live positions to the provided spot price. Returns the same shape as the `live_positions` array in the dashboard snapshot. The spot ticker JS calls this endpoint every 60s instead of re-fetching the full dashboard. If `spot` param is omitted, uses last history close.

### `GET /trade/{entry_date}`
HTML page. `entry_date` format: `YYYY-MM-DD`. Finds matching trade from snapshot (which includes `legs` tuple), computes premium series via `compute_premium_series()`, renders chart.

---

## Data Model: `dashboard.json`

Generated nightly by `snapshot.py`. Static between refreshes. App loads into memory on startup.

| Field | Type | Source |
|-------|------|--------|
| `generated_at` | ISO timestamp | `metrics.provenance()` |
| `last_trading_date` | ISO date | `df["Date"].max()` |
| `git_sha` | string | `metrics.provenance()` |
| `config` | dict | `Config()` fields |
| `trade_stats` | dict | `metrics.trade_stats(trades_df)` |
| `equity_stats` | dict | `metrics.equity_stats(equity)` |
| `trades` | list[dict] | `engine.trades_frame(trades).to_dict("records")` + `legs` field per trade |
| `equity_curve` | list[dict] | `equity.rename(columns={"Date": "date"}).to_dict("records")` |
| `probability_table` | list[dict] | `table.to_dict("records")` |
| `oos_data` | list[dict] | `metrics.oos_summary(oos)` |
| `benchmark_equity` | list[dict] | hold-mode `equity.to_dict("records")` |
| `live_positions` | list[dict] | `state.compute_live_positions()` at snapshot time |
| `next_trade_preview` | dict | `state.compute_next_trade_preview()` at snapshot time |

**Note:** `live_positions` and `next_trade_preview` are pre-computed with last history close as spot. The app re-marks them with live spot via `/api/live-positions?spot=X` (called by spot ticker JS every 60s).

---

## Risks / Gotchas

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Render cold start** (free tier spins down after 15 min idle) | 30-60s load on first visit | UptimeRobot 5-min ping on `/health` keeps service alive |
| **yfinance spot fetch fails** | Spot ticker shows stale data | Fallback to last history close; badge shows "as of" timestamp |
| **yfinance rate limiting** | Spot endpoint 429s | Cache spot for 60s in app memory; single user so minimal |
| **NSE API blocked** (Akamai bot manager) | Nightly refresh gets no new data | yfinance is fallback provider; snapshot still generates from existing history |
| **dashboard.json missing** (first deploy before GH Action runs) | App crashes on startup | `app.py` generates snapshot on startup if file missing |
| **Chart.js CDN unavailable** | Charts don't render | Low risk (unpkg/cdnjs very reliable); could self-host later |
| **Large dashboard.json** | Slow initial load | 234 trades × ~100 bytes = ~25KB. Equity curve: 246 points × 30 bytes = ~7KB. Total well under 100KB — no issue |
| **Market holiday = no new data** | Snapshot shows same data multiple days | Badge shows `last_trading_date` so user knows |
| **Trade date timezone mismatch** | `entry_date` comparison fails | All dates normalized to date-only (no timezone) in state layer |
| **`ladder_rollover=True` changes trade count** | Live positions logic assumes default | State layer uses current Config (default `False`); document in snapshot |
| **Multiple legs per trade** | Premium path chart needs all legs | `compute_premium_series` iterates through `trade.legs` tuple |

---

## ponytail Notes

- No React, no Node, no build step. Jinja2 + CDN Chart.js = zero frontend tooling.
- Spot caching: 60s in-memory dict, not Redis. Single user.
- Templates: no Tailwind, no component library. Plain HTML + inline styles or a single `<style>` block. Charts do the heavy lifting.
- No WebSocket for live spot. Simple poll every 60s.
- `snapshot.py` is a script, not a class. `generate_snapshot()` → write file → done.
