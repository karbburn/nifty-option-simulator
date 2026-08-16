# NIFTY Weekday‑Gap Options Simulator

[![GitHub](https://img.shields.io/github/stars/karbburn/nifty-option-simulator?style=social)](https://github.com/karbburn/nifty-option-simulator)
[![Tests](https://img.shields.io/badge/tests-116‑green.svg)](https://github.com/karbburn/nifty-option-simulator)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

A research/backtesting tool that measures weekday‑pair gap probabilities, converts them to CE/PE trade rules, prices options with Black‑Scholes, manages trades via a GTT‑style premium‑% ladder, and honestly reports results and limitations.

**Not a live trading system.** No broker API, no real orders, no stakes.

---

## 1. Quick Start

```bash
# 1. Clone & install
git clone https://github.com/karbburn/nifty-option-simulator.git
cd nifty-option-simulator
python -m pip install -e .

# 2. (Optional) Refresh daily data — exits 0 even if NSE APIs are unavailable
python -m nifty_gap.data.refresh

# 3. Run the full pipeline
python -m nifty_gap

# 4. Results appear in output/
#    – 5 PNG charts (probability, exit reasons, equity, benchmark, OOS)
#    – Trade stats & equity stats printed to console
```

---

## 2. What It Does

For each weekday pair (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri; Fri→Mon is excluded):

1. **Compute** `P(open_day2 > close_day1)` from historical data
2. **Trade** long ATM Call if `p_up > 50%`, else long ATM Put
3. **Price** the option via Black‑Scholes (ATM strike, nearest ₹50, 12.5% IV)
4. **Exit** via a two-sided ratcheting ladder on the option premium's own % move
   - Loss stops cascade: −3% / −5% (first breach exits)
   - Profit floors trail up: +5% / +10% / +15% (exit when the premium falls back through the highest banked floor)
   - Forced exit at next weekly expiry
5. **Report** exit reasons, per‑pair P&L, equity curve, and benchmark comparison

`ladder_rollover` (default `False`) re-enters a fresh ATM weekly option when a trade reaches expiry without hitting any ladder condition, chaining legs until a stop/floor triggers or data runs out. On the current sample this is **loss-making** (full-sample −₹329.7k vs −₹75.5k without rollover) because the rolled-in ATM premium mostly theta‑decays into the −5% stop. Set `ladder_rollover=True` to opt in. `excluded_pairs` (default `{"Fri→Mon"}`) drops the named weekday pairs from the tradeable universe — Fri→Mon has been excluded because weekend theta and gap behavior made it consistently loss-making (−₹202k over the sample).

---

## 3. Output

| File | Description |
|---|---|
| `output/probability.png` | Per‑pair `p_up` with 95% Wilson CI, `n` on each bar, 50% line |
| `output/exit_reasons.png` | Exit‑reason breakdown with average P&L per reason |
| `output/equity.png` | Portfolio equity curve with max‑drawdown shading |
| `output/benchmark.png` | Ladder strategy vs no‑ladder benchmark |
| `output/oos.png` | IS table probability vs realised OOS win rate |
| `REPORT.md` | Full limitations register and acceptance criteria |

Console output prints: total trades, total P&L, win rate, profit factor, max drawdown.

---

## 4. Web Dashboard

The project ships a read‑only web dashboard that serves the backtest results as interactive HTML charts.

```bash
pip install -e ".[web]"
uvicorn nifty_gap.web.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/`. Routes:

| Route | Purpose |
|---|---|
| `/` | Dashboard — KPIs, live positions, trades table, equity curve, OOS, benchmark |
| `/trade/{entry_date}` | Per‑trade premium path chart with ladder stop/floor lines |
| `/expiry` | Expiry weekday explainer with OOS table |
| `/api/dashboard` | Full `dashboard.json` snapshot (JSON) |
| `/api/spot` | Live NIFTY spot (yfinance, 60s cache, history fallback) |
| `/api/live-positions?spot=X` | Re‑mark open positions at a given spot |
| `/health` | Liveness check |

### Deploy (Render)

1. Push `main`; create a Render Web Service from the repo (Python runtime).
2. Start command: `uvicorn nifty_gap.web.app:app --host 0.0.0.0 --port 8000`.
3. Add a cron ping (e.g. UptimeRobot) to `/health` every 5 min to keep the free tier awake.
4. The `refresh-data` GitHub Action runs on weekdays at 11:30 UTC, regenerates `output/dashboard.json`, and commits it — Render auto‑deploys on push.

---

## 5. Configuration (`nifty_gap/config.py`)

Key parameters you may want to adjust:

- `min_pair_sample` — minimum rows per pair before a probability is computed (default: 5)
- `z_score` — how many standard deviations to use for Wilson CI (default: 2)
- `iv` — implied volatility flat rate used for all BS prices (default: 0.125)
- `ladder_*` — exit‑ladder levels: loss stops (`ladder_stop_pcts`) and trailing profit floors (`ladder_floor_pcts`)

All parameters are exposed in `config.py` and are individually reversible.

---

## 6. Limitations (abridged)

1. **Sample size** is small (~245 pairs across 5 buckets) ⇒ noisy `p_up` estimates
2. **BS with flat 12.5% IV** is not a market price; real premium reflects skew, term structure, supply‑demand
3. **Costs omitted** (slippage, brokerage, STT, bid‑ask) make the backtest an upper bound
4. **Data sourcing** best‑effort: NSE APIs behind Akamai Bot Manager; yfinance is the reliable nightly provider
5. **No live/paper components**: no broker API, no real orders, no stakes

See `REPORT.md` for the complete, unabridged limitations register.

---

## 7. Acknowledgement

Data sourced from NSE via yfinance (delayed, best‑effort). The project is built as a research backtesting tool, not a live trading system.

---

*Generated 15 Aug 2026. For the full limitations register, see `REPORT.md`.*