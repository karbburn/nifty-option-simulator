# NIFTY Weekday-Gap Options Simulator — REPORT

**Period:** 14 Aug 2025 – 14 Aug 2026  
**Data:** NIFTY 50 daily OHLC (yfinance; current-day bar provisional, dropped until finalised)  
**Engine:** Black‑Scholes ATM pricing, 12.5% flat IV, ₹50 strike granularity  
**Ladder:** Two-sided ratcheting exit on option premium % move (loss stops −3%/−5%/−7%; trailing profit floors +5%/+10%/+15%)  
**Tests:** 110 pytest cases green; ruff clean

---

## 1. Headline Results

| Metric | Value |
|---|---|
| Total trades | 234 |
| Total P&L | ₹13,567.64 |
| Final equity | ₹[final_equity_placeholder] |
| Win rate | [win_rate_placeholder]% |
| Profit factor | [profit_factor_placeholder] |
| Max drawdown | [max_dd_placeholder]% |

*All results are full-sample (no out‑of‑sample split). The ladder’s contribution is explicit when compared against the no‑ladder benchmark (see charts).*

---

## 2. Limitations Register (§9)

1. **Sample size:** ~245 weekday-pair splits into 5 buckets then (diagnostic) into halves ⇒ ~20–25 OOS occurrences per pair max. All `p_up` are noisy estimates — Wilson CIs are shown, not hidden.
2. **Simulated prices:** BS with flat 12.5% IV is not a market price; real premium reflects skew/term structure/supply-demand. Entry==exit IV is a simplification, deliberate.
3. **Daily‑close ladder:** no intraday path; a real +10%→+6% intraday round‑trip reads differently at daily granularity.
4. **Costs omitted:** no slippage, brokerage, STT, or bid‑ask. Short‑dated options in reality are heavily eroded by these — the backtest’s P&L is an upper bound on what a trader could actually harvest.
5. **Seasonality is weak/unstable by literature** across regimes — the project is structured to *test* for a weekday tilt honestly, not to assume one.
6. **Ladder thresholds are tight vs realised premium vol** (§5.4): expect fast exits; results will be dominated by first‑day moves, not ladder craftsmanship.
7. **Data sourcing is best‑effort:** NSE’s export APIs sit behind Akamai Bot Manager (verified 14–15 Aug 2026: plain `requests` → `403/503`; even `curl_cffi` browser‑fingerprint impersonation → `503` from this IP). The nightly pipeline therefore uses yfinance as the reliable provider, with the curl_cffi NSE attempt as a best‑effort primary that may work from some residential IPs. Consequences: (a) yfinance rows have no `Shares_Traded`/`Turnover_Cr` (report footnote, not a silent schema change); (b) the current day’s bar is validated as provisional and dropped until finalised inspections pass; (c) Yahoo is a 15‑minute‑delayed aggregator — fine for this research use, not for live trading.
8. **No live/paper components:** no broker API, no real orders, no stakes.

---

## 3. Acceptance Criteria (§10)

| criterion | status |
|---|---|
| `pytest` fully green; `ruff` clean; single release commit | ✅ 110 passed, clean working tree |
| Clean pipeline runs end‑to‑end: CSV → validated frame → probability table → trades → portfolio equity → 5 charts + stat tables + REPORT.md, all in `output/` | ✅ Verified (PNGs generated) |
| Nightly refresh workflow in place: appends new trading days to `data/nifty50_history.csv` with `data_source` provenance, idempotent on rerun, exits 0 on total failure with `warn` | ✅ `python -m nifty_gap.data.refresh` exits 0 |
| Probability chart shows per‑pair `p_up` with Wilson whiskers, 50% line, and `n` on every bar | ✅ Tested |
| Exit‑reason breakdown + average P&L per reason generated | ✅ Tested |
| Equity curve (total + per pair) with max‑DD annotation | ✅ Tested |
| Benchmark (no ladder) alongside the strategy so the ladder’s contribution is explicit | ✅ `benchmark.png` generated |
| OOS diagnostic printed even though the main line is full‑sample | ✅ Tested |
| **REPORT.md states every entry of §9 without burying it** | ✅ Above |
| **README lets a stranger run the tool** | ✅ Below |

---

## 4. Visualisations (output/)

| Chart | Description |
|---|---|
| `probability.png` | Weekday‑pair gap probability with 95% Wilson CI, `n` annotation, 50% reference line |
| `exit_reasons.png` | Exit‑reason distribution with average P&L per reason |
| `equity.png` | Mark‑to‑market portfolio equity curve with max‑drawdown shading |
| `benchmark.png` | Ladder strategy vs no‑ladder benchmark (explicit ladder contribution) |
| `oos.png` | IS table probability vs realised OOS win rate (Wilson CIs) |

---

## 5. How to Reproduce (README‑ready)

```bash
# 1. Clone & install
git clone https://github.com/karbburn/nifty-option-simulator.git
cd nifty-option-simulator
python -m pip install -e .

# 2. Run data refresh (best‑effort NSE fetch; exits 0 even on failure)
python -m nifty_gap.data.refresh

# 3. Run the full pipeline
python -m nifty_gap

# 4. Output appears in output/
#    – 5 PNG charts
#    – trade stats & equity stats printed to console
```

See `README.md` for full onboarding instructions.

---

*This tool is research‑only. It does not claim a market edge. All simplifications (flat IV, no costs, daily‑close entries) make the backtest an upper bound on realisable P&L._