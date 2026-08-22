# NIFTY Weekday‑Gap Options Simulator

A research and backtesting tool for NIFTY 50 that measures weekday‑pair gap probabilities, converts them into CE/PE trade rules, prices options with Black–Scholes, manages trades through a GTT‑style premium‑percentage exit ladder, and reports results , including their limitations, honestly.

**This is not a live trading system.** No broker API, no real orders, no capital at risk.

🔗 **Live dashboard:** <https://nifty-opt-sim.onrender.com/>

---

## Features

- **Gap‑probability research**: per‑weekday‑pair probability of an up‑open, with Wilson 95% confidence intervals and minimum‑sample guards
- **Rule generation**: each pair maps to a long ATM Call (bullish edge) or Put (bearish edge) at the nearest ₹50 strike
- **Black–Scholes pricing**: flat implied volatility, with an IV sweep mode for sensitivity analysis
- **GTT‑style exit ladder**: ratcheting stop/floor levels on the option premium's own % move, plus forced exit at weekly expiry
- **Benchmark comparison**: ladder strategy vs. hold‑to‑expiry baseline to isolate what the exit logic adds or costs
- **In‑sample vs. out‑of‑sample diagnostics**: realised OOS win rates against IS probabilities
- **Interactive web dashboard**: KPIs, live position re‑marking, trade explorer, equity curve, and a config explorer that recomputes the backtest on parameter changes

---

## Methodology

For each weekday pair (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri):

1. **Compute** `P(open_day2 > close_day1)` from historical data
2. **Trade** long ATM Call if `p_up > 50%`, else long ATM Put
3. **Price** the option via Black–Scholes (ATM strike, nearest ₹50, 12.5% flat IV)
4. **Manage** the position with a two‑sided ratcheting ladder on the option premium's own % move:
   - Loss stops cascade: −3% / −5% (first breach exits)
   - Profit floors trail up: +5% / +10% / +15% (exit when premium falls back through the highest banked floor)
   - Forced exit at next weekly expiry
5. **Report** exit reasons, per‑pair P&L, equity curve, and benchmark comparison

Two notable configuration levers:

- `ladder_rollover` (default `False`) re‑enters a fresh ATM weekly option when a trade reaches expiry without hitting a ladder condition. On the current sample this is loss‑making (full‑sample −₹329.7k vs. −₹75.5k without), because rolled‑in ATM premium mostly theta‑decays into the −5% stop.
- `excluded_pairs` (default `{"Fri→Mon"}`) removes weekday pairs from the tradeable universe. Fri→Mon is excluded because weekend theta made it consistently loss‑making (−₹202k over the sample).

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/karbburn/nifty-option-simulator.git
cd nifty-option-simulator
python -m pip install -e .

# 2. (Optional) Refresh daily data (exits 0 even if NSE APIs are unavailable)
python -m nifty_gap.data.refresh

# 3. Run the full pipeline
python -m nifty_gap

# 4. Results appear in output/
```

Outputs written to `output/`: five PNG charts (probability, exit reasons, equity, benchmark, OOS) plus trade statistics printed to the console (total trades, total P&L, win rate, profit factor, max drawdown).

---

## Web Dashboard

The project ships a read‑only web dashboard that serves backtest results as interactive HTML charts, with live NIFTY spot marking of open positions.

```bash
pip install -e ".[web]"
uvicorn nifty_gap.web.app:app --host 0.0.0.0 --port 8000
```

### Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Dashboard: KPIs, live positions, trades table, equity curve, config explorer |
| `/trade/{entry_date}` | GET | Per‑trade premium path chart with ladder stop/floor lines |
| `/expiry` | GET | Expiry weekday explainer with IS vs. OOS table |
| `/health` | GET | Liveness check |
| `/api/dashboard` | GET | Full dashboard snapshot (JSON) |
| `/api/recompute` | POST | Recompute backtest with modified parameters |
| `/api/refresh` | POST | Refresh market data and regenerate snapshot |
| `/api/spot` | GET | Live NIFTY spot (yfinance, 60s cache, history fallback) |
| `/api/live-positions` | GET | Re‑mark open positions at a given spot |

---

## Deployment (Render)

**Live:** <https://nifty-opt-sim.onrender.com/> · **Health:** <https://nifty-opt-sim.onrender.com/health>

The service deploys from `main` via the repository blueprint (`render.yaml`):

1. Push `main`; create a Render Web Service from the repo (Python runtime).
2. Build command: `pip install -e ".[web]"`.
3. Start command: `uvicorn nifty_gap.web.app:app --host 0.0.0.0 --port $PORT` (Render injects `$PORT` ; do not hardcode).
4. Optional: external cron ping (e.g. UptimeRobot) to `/health` every 5 minutes keeps the free tier awake.
5. A scheduled GitHub Action refreshes history and regenerates `output/dashboard.json` + PNGs on weekdays, committing the results; Render auto‑deploys on push. Committed snapshots mean the app boots instantly without regenerating on startup. No environment variables or secrets required.

Embedding: the app sets `Content-Security-Policy: frame-ancestors 'self' https://sourabh08.vercel.app`, so the dashboard can be framed from the portfolio site while remaining protected elsewhere.

---

## Configuration

Key parameters live in [`nifty_gap/config.py`](nifty_gap/config.py). All are individually reversible.

| Parameter | Default | Description |
|---|---|---|
| `min_pair_sample` | `5` | Minimum observations per pair before a probability is computed |
| `z_score` | `2` | Standard deviations used for the Wilson confidence interval |
| `iv` | `0.125` | Flat implied volatility rate for all Black–Scholes prices |
| `ladder_stop_pcts` | `(−3%, −5%)` | Cascading loss stops on premium % move |
| `ladder_floor_pcts` | `(+5%, +10%, +15%)` | Trailing profit floors |
| `ladder_rollover` | `False` | Roll into a fresh ATM option at expiry if no ladder condition hit |
| `excluded_pairs` | `{"Fri→Mon"}` | Weekday pairs removed from the tradeable universe |

---

## Testing & Quality

```bash
python -m pip install -e ".[dev]"
python -m pytest        # 155 tests
ruff check .            # linting (line length 100)
```

The suite covers signal computation, Black–Scholes pricing (parity, intrinsic‑value and T→0 invariants), ladder mechanics, portfolio accounting continuity, and web API contract tests.

---

## Limitations (abridged)

1. **Sample size**: ~245 pairs across 5 buckets ⇒ noisy `p_up` estimates
2. **Flat 12.5% IV** is not a market price; real premiums reflect skew, term structure, and supply–demand
3. **Costs omitted** (slippage, brokerage, STT, bid–ask spread) make backtest results an upper bound
4. **Data sourcing** is best‑effort: NSE APIs sit behind Akamai Bot Manager; yfinance is the reliable nightly provider
5. **No live/paper components**: no broker API, no real orders, no stakes

---

## Disclaimer

This project is published for educational and research purposes only. Nothing here constitutes investment advice, a recommendation, or an offer to transact. Options trading involves substantial risk of loss. Past performance (simulated or real) does not guarantee future results.

---

*Data sourced from NSE via yfinance (delayed, best‑effort).*
