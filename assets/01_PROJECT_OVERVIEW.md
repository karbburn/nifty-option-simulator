# 01 — Project Overview

## What this is

A backtesting tool that:
1. Uses one year of NIFTY 50 daily OHLC data to measure, per weekday pair (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri, Fri→Mon), how often the second day's Open beats the first day's Close.
2. Converts that into a standing trade rule: if a weekday pair's historical P(up) > 50%, buy ATM CE on every future occurrence of that pattern; if < 50%, buy ATM PE.
3. Prices the option via Black-Scholes (since no real historical options premium data is used), and manages each trade with a GTT-style trailing target/stop-loss ladder on the premium's own % move.
4. Reports results as a probability chart, exit-reason breakdown, and equity curve.

This is **not** a live trading system and does not use real money or real options quotes. It's a research/portfolio project demonstrating quantitative signal construction, options pricing, and backtest engineering — consistent with the rest of your quant finance project portfolio (BondFactor, PathPricer, MacroPulse).

## Why this project (positioning)

- Demonstrates: statistical signal discovery under small-sample constraints, Black-Scholes implementation from first principles, state-machine design for path-dependent trade management, and honest reporting of a strategy's limitations rather than overclaiming an edge.
- Fits your existing narrative: another solo-built, documentation-first, free-tier quant tool for your portfolio/GitHub.

## Explicit non-goals

- Not a live/paper trading bot (no broker API, no real order placement)
- Not using real historical options chain data (Black-Scholes-simulated premiums only)
- Not claiming a validated trading edge — the small sample size (~246 days, ~49 occurrences per weekday pair) is treated as a first-class limitation throughout, not a footnote

## Locked design decisions (reference — see other docs for detail)

| Parameter | Value |
|---|---|
| Data source | Uploaded NIFTY 50 daily OHLC, 14-Aug-2025 to 14-Aug-2026 (246 rows) |
| Signal granularity | Per weekday pair, strict calendar weekday bucketing |
| Side selection | P(up) > 50% → CE, else → PE. No conviction filter |
| Position size | Fixed 1 lot, every signal day trades (no skip rule) |
| Option pricing | Black-Scholes, ATM strike, flat IV = 12.5% |
| Risk-free rate | Sourced dynamically at runtime (not hardcoded) |
| Exit management | GTT-style ratcheting ladder on option premium % (Doc 05) |
| Validation | Full-sample table build (no held-out split) — flagged limitation, not a blind spot |

## Doc map

| Doc | Purpose |
|---|---|
| 01_PROJECT_OVERVIEW.md | This file |
| 02_DATA_SPEC.md | Data cleaning, schema, weekday tagging rules |
| 03_SIGNAL_METHODOLOGY.md | Probability table construction + statistical caveats |
| 04_OPTIONS_PRICING_SPEC.md | Black-Scholes implementation, IV, risk-free rate sourcing, expiry calendar |
| 05_TRADE_EXECUTION_SPEC.md | Entry rule + GTT exit ladder state machine |
| 06_BACKTEST_ENGINE_SPEC.md | How signals + pricing + ladder combine into trade-level P&L |
| 07_VISUALIZATION_SPEC.md | Chart specs (probability chart, exit-reason breakdown, equity curve) |
| 08_TECH_STACK_ARCHITECTURE.md | Free-tier stack, folder structure, libraries |
| 09_ASSUMPTIONS_LIMITATIONS.md | Full limitations register |
| IMPLEMENTATION_PROMPTS.md | Staged, one-prompt-per-stage build plan |
