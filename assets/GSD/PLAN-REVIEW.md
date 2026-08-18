# PLAN-REVIEW.md — NIFTY Option Simulator Web Dashboard

**Verdict: NEEDS_WORK** — 2 critical gaps, 2 majors, 4 minors. Fix the data flow issues before executing.

---

## Findings

### 1. CRITICAL — Trade detail page has no data source for premium series

**What:** `GET /trade/{entry_date}` needs to compute a premium path chart. `compute_premium_series(df, trade, cfg)` requires a `Trade` object (with `legs` tuple). But the snapshot stores trades via `trades_frame(trades).to_dict("records")` — and `trades_frame()` explicitly drops the `legs` column (engine.py:169). The route handler gets a dict, not a Trade object.

**Fix:** Either:
- **(a)** Include `legs` in snapshot trades — add `legs` field to the dict before serializing. ~1KB per trade, negligible for 234 trades.
- **(b)** Pre-compute premium series in `snapshot.py` and store as `premium_series` keyed by entry_date.
- **(c)** Re-run backtest in the route handler (wasteful, single-user but still ~2s per page load).

Option (a) is simplest. Add to snapshot generator: `trade_dict["legs"] = trade.legs` before `to_dict()`.

### 2. CRITICAL — Live position re-marking has no implementation path

**What:** Plan says the spot ticker "re-marks live position cards (fetches `/api/dashboard` for position data, applies new spot to premium calculation client-side OR re-fetches from server)". This is ambiguous — it describes two mutually exclusive approaches without committing to either.

- **Client-side** requires a Black-Scholes formula in JavaScript (not mentioned anywhere in the plan).
- **Server-side** requires an API endpoint like `GET /api/live-positions?spot=X` (not defined in the API contract).

**Fix:** Pick server-side. Add `GET /api/live-positions?spot={float}` to the API contract. Route handler calls `compute_live_positions(trades, spot, cfg)` and returns the result. The spot ticker JS fetches this endpoint every 60s instead of re-fetching the full dashboard.

### 3. MAJOR — `equity_curve` column name mismatch

**What:** `daily_mtm()` returns a DataFrame with columns `Date` (capital D) and `equity`. The plan's API contract shows equity_curve entries as `{"date": "...", "equity": 0.0}` (lowercase d). The snapshot generator must rename `Date` → `date` when serializing, or the frontend will look for a key that doesn't exist.

**Fix:** In `snapshot.py`, when building equity_curve: `equity.rename(columns={"Date": "date"}).to_dict("records")`.

### 4. MAJOR — `oos_diagnostic` return shape not mapped to snapshot

**What:** `oos_diagnostic()` returns `{"split_date", "table", "oos"}` where `oos` is a DataFrame. The plan lists `oos_data` in the snapshot but doesn't show the mapping. The snapshot generator needs to call `metrics.oos_summary(result["oos"])` to convert the DataFrame to the list-of-dicts shape the API contract specifies.

**Fix:** Add explicit mapping in Phase 2 Task 1: `oos_data = metrics.oos_summary(oos_result["oos"])`.

### 5. MINOR — Missing `__main__.py` for web package

**What:** Plan says `python -m nifty_gap.web.snapshot` as CLI entry point. This requires `nifty_gap/web/__main__.py`. Not listed in file manifest.

**Fix:** Add `nifty_gap/web/__main__.py` to file manifest. Content: `from nifty_gap.web.snapshot import main; main()`.

### 6. MINOR — `app.py` startup behavior contradicts risk mitigation

**What:** Phase 3 Task 1 says startup "loads `output/dashboard.json` into `app.state.snapshot`". Risks section says "app.py generates snapshot on startup if file missing". These are contradictory — one implies crash on missing file, the other implies graceful generation.

**Fix:** Pick one. Recommended: generate on startup if missing (matches risk mitigation). Update Phase 3 Task 1 to say: "Startup: load `output/dashboard.json` into `app.state.snapshot`; if missing, call `generate_snapshot()` first."

### 7. MINOR — Phase 5 is mostly redundant

**What:** Phase 5 Task 1 says "Already included in Phase 4 dashboard.html — verify Chart.js renders correctly". This is verification, not new work. Phase 5 Task 2 (spot ticker + freshness badge + sort/filter JS) is the only real work, and it's already partially described in Phase 4 Task 1.

**Fix:** Fold Phase 5 into Phase 4. The plan has 6 phases for what's effectively 4 phases of work. Not a blocker, but unnecessary ceremony.

### 8. MINOR — Missing `output/` directory in file manifest

**What:** Plan references `output/dashboard.json` but doesn't list creating the `output/` directory. `snapshot.py` will need `output/` to exist (or `Path.mkdir(parents=True)`).

**Fix:** Either add `output/` to file manifest or note that `snapshot.py` creates it via `Path.mkdir(parents=True, exist_ok=True)` (which `export_json` already does — verify).

---

## What's Good

- **Architecture is sound.** Pre-computed snapshot + lightweight FastAPI server is the right call for a single-user dashboard. No over-engineering.
- **Ponytail notes are accurate.** No React, no Node, no build step. Jinja2 + CDN Chart.js is the minimum viable stack.
- **Risk table is thorough.** Cold start, yfinance failures, rate limiting, market holidays — all accounted for with practical mitigations.
- **Existing code reuse is well-planned.** `state.py` wraps existing backtest engine functions rather than reimplementing. `_mark()`, `build_probability_table`, `run_backtest` — all reused.
- **API contracts are explicit.** JSON shapes are fully documented with example values. Frontend developers (or AI) can implement against these without ambiguity.
- **Scope is right-sized.** 234 trades × ~100 bytes = ~25KB snapshot. No WebSocket, no real-time streaming. Poll every 60s. This will work.
- **Test plan covers the right things.** Unit tests for state layer (pure functions), integration tests for routes (smoke). No over-testing.
- **File manifest is complete.** Every file listed with action and purpose. No orphans.

---

## Summary

The plan is well-structured and the architecture is correct. The two critical issues are both data flow gaps — the plan describes *what* each page needs but doesn't fully trace *how* the data gets there. Fix finding #1 (trade detail data source) and #2 (live position re-marking path), and the plan is executable. The majors (#3, #4) are straightforward serialization fixes. The minors are documentation gaps.

**Recommended action:** Revise findings #1 and #2, then re-verify.
