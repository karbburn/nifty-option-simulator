# NIFTY Day-of-Week Gap Probability & Options Trade Simulator — Project Plan (v2)

## 1. Objective

For each weekday pair (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri, Fri→Mon), calculate the historical probability that the second day's **Open** is higher than the first day's **Close**. If P(up) > 50%, that weekday pattern is a **CE side**; if P(up) < 50% (i.e. P(down) > 50%), it's a **PE side**. Every time that weekday occurs going forward, take the corresponding trade — buy ATM CE or ATM PE at the prior day's close, hold into the next weekly expiry, and manage the trade with a trailing target/stop-loss ladder based on the option premium's own % move.

This is a research/backtesting tool, not a live trading system. No real capital, no real options data — everything downstream of the index price is simulated via Black-Scholes.

## 2. Locked-in Scope Decisions (from our discussion)

| Decision | Choice |
|---|---|
| Signal unit | Per weekday pair (e.g. "Tuesday→Wednesday"), not per individual day |
| Signal definition | P(Open[day2] > Close[day1]) computed historically for that specific weekday pair |
| Side selection | P > 50% → trade CE that pattern; P < 50% → trade PE that pattern. No separate conviction filter — pure majority rule |
| Entry | Buy ATM CE/PE at Close of day1, for the weekday pair that's signaling |
| Holding period | Held toward next weekly expiry (not exited next day) — exit governed entirely by the trigger ladder below, or expiry, whichever comes first |
| Exit logic | Trailing/ratcheting target-stop ladder on the **option premium's own % move** (see Section 6) |
| Option pricing | Black-Scholes, ATM strike, flat IV (constant, value TBD) |
| Probability model | v1 only — a lookup table of historical hit-rate per weekday pair. No regression model — this is now a rule-based seasonality strategy, not an ML model |
| Deliverable (this stage) | Planning doc only — no code yet |

## 3. Data Pipeline

**Source:** Your uploaded CSV (`NIFTY_50-14-08-2025-to-14-08-2026.csv`), 246 trading days, columns: Date, Open, High, Low, Close, Shares Traded, Turnover.

**Cleaning steps needed:**
- Strip the BOM/whitespace in column headers (`﻿Date `, `Open ` etc. have trailing spaces)
- Parse `Date` (format `DD-MMM-YYYY`) and sort ascending (currently descending — most recent first)
- Check for missing trading days (holidays are fine, just confirm no data gaps mid-series)
- Confirm no duplicate dates

**No external data is strictly required for v1.** If you want more history for a more stable base rate later, NSE's own historical data archives (nseindia.com) are free but need a scripted session/cookie workaround; Yahoo Finance (`^NSEI` via `yfinance`, free, no key) is the easiest free fallback for extending history.

## 4. Signal Construction — Day-of-Week Gap Table

For every consecutive trading-day pair in the dataset, tag it by weekday-pair label (e.g. "Tue→Wed"). Note: with holidays, the "next trading day" isn't always the calendar-next weekday — a Friday might be followed by Tuesday if Monday's a holiday. Decide upfront whether to:
- (a) bucket strictly by actual weekday names as they occurred (simpler, matches raw calendar), or
- (b) bucket by "trading-day position" (1st/2nd/3rd/4th/5th day of the trading week) which is more robust to holidays

Recommend (a) for v1 — simpler, and holidays are infrequent enough not to distort the sample much over 1 year.

For each weekday-pair bucket, compute:
- `n`: number of historical occurrences (with only ~246 days, each weekday pair has roughly ~48–50 samples — small)
- `p_up`: fraction where Open[day2] > Close[day1]
- 95% binomial confidence interval on `p_up` (important — with n≈49, a 55% observed rate could easily be 45–65% true rate; this needs to be shown, not hidden)
- Side: CE if `p_up` > 50%, PE if `p_up` < 50%

Output: a single table, one row per weekday pair, this **is** the probability chart you asked for (bar chart of `p_up` per weekday pair with confidence interval whiskers, and a 50% reference line).

## 5. Probability Model

This is now a **lookup table**, not a fitted statistical model — deliberately, since the signal is "does this specific weekday pair have a historical tilt," not "predict each day individually from features." No train/test split is needed for the signal itself since it's descriptive, not predictive-by-features — but see Section 8 for why the whole approach still needs an honest out-of-sample check (the table shouldn't be built and traded on the exact same data).

**Recommended addition (flagging for your decision):** split the ~1 year into two halves — compute the weekday-pair table on the first half, then simulate trading it on the second half only. Otherwise "P(up) 56% on Wednesdays" and "we made money trading that 56% edge" are measured on the same data, which isn't a real test of anything. This is the single most important methodological point in this whole plan — happy to build it either way, but you should decide knowingly.

## 6. Options Pricing Module (Black-Scholes simulation)

Since no real options price history is used, each trade's option price is computed, not observed:

- **Underlying price:** NIFTY Close[t] (entry) and Close[t+1] (exit)
- **Strike:** ATM, rounded to nearest 50 (NIFTY's strike interval) based on Close[t]
- **IV:** flat constant (you specified ~12–13%) — same value used for entry and exit pricing, so the entry/exit price difference reflects only spot movement + one day of theta decay, not an IV change
- **Time to expiry:** 7 days at entry, 6 days at exit (theta decay of exactly 1 day baked in)
- **Risk-free rate:** use a fixed proxy like RBI's repo rate (~6.5%, free public data from RBI website) — flag this as a simplifying constant, not updated daily
- **Formula:** standard Black-Scholes-Merton for European CE/PE (NIFTY options are European-style, so this is actually appropriate, not just a simplification)
- **Lot size:** NIFTY lot size (currently 75, but this changes periodically — will need to be updated to whatever's current if you want a rupee P&L rather than a per-share P&L)

**What "keeping other factors constant" excludes here, explicitly, so it's not accidentally hidden:**
- No bid-ask spread / slippage
- No brokerage or STT/transaction costs
- No IV changes overnight (real IV moves with events, expiry proximity, etc. — flat IV is a real simplification, not reality)
- No liquidity constraints (assumes you can always buy/sell at the BS fair price)

## 6. Exit Ladder (Trailing Trigger on Option Premium %)

All percentages below are moves in the **option premium itself**, tracked from entry price, marked at each day's close (daily granularity, since we only have daily OHLC — an intraday version would need intraday data, which isn't free/available here, so this is a known simplification, flagged in Section 9).

The rule, as confirmed:

1. **Entry**: buy ATM CE or PE at Close[day1], priced via Black-Scholes
2. **Downside**: hard stop-loss at **−7%** of entry premium — trade closes here, no exceptions, no ladder
3. **Upside, stage 1**: once premium is up **+3%**, this becomes the new "give-back" floor to watch — if it later falls back through +3% without ever reaching +5%, exit at that floor (a "good-till-triggered" stop that only activates after the threshold is first touched)
4. **Upside, stage 2**: if premium instead pushes on to **+5%** without falling back, the floor ratchets up — this is now the new give-back level to trail from
5. **Upside, stage 3**: if premium continues to **+10%**, treat as a resistance test — hold, target **+15%** next
   - If it reaches +15%: exit here (final target hit)
   - If it fails to reach +15% and instead falls back down to +10%: exit at +10% (lock in the level it already proved it could hold)
6. **Time exit**: if none of the above trigger before the next weekly expiry arrives, exit at expiry regardless of premium level (since the position is European-style and effectively worthless past expiry if OTM)

This needs to be implemented as a proper state machine (which stage has the trade "unlocked" so far) rather than independent if/else checks on each day, since the rule is path-dependent (e.g. reaching +10% then dropping to +6% is NOT a +3%-floor breach if +5% was already banked — need to confirm this reading is right when we get to building it).

## 7. Trade / Backtest Logic

For each weekday-pair signal day in the (out-of-sample half of the) dataset:
1. Look up that weekday pair's `p_up` from the table (Section 4) — side = CE if >50%, PE if <50%
2. Buy the ATM option at Close[day1] via Black-Scholes (strike = nearest 50 to Close[day1], IV = flat assumed value, time-to-expiry = actual calendar days to that week's expiry)
3. Walk forward day by day, re-pricing the same option via Black-Scholes at each subsequent day's Close (spot moves, time-to-expiry decays by 1 day each day) until the exit ladder (Section 6) triggers, or expiry is reached
4. Record entry price, exit price, exit reason (SL / +3% floor / +5% floor / +15% target / +10% lock / expiry), and days held
5. P&L = (exit price − entry price) × lot size, per trade
6. Aggregate: cumulative P&L curve, win rate, average win/loss, hit rate per weekday pair (does the trade P&L actually track the raw `p_up` edge, or does the exit ladder change that story), Sharpe-like ratio

## 8. Evaluation & Outputs

- **Probability chart (core deliverable):** bar chart, one bar per weekday pair, showing `p_up` with a 95% confidence interval and a 50% reference line — this is what actually drives every trade decision, so it's the centerpiece
- **Sample-size annotation on every bar:** n for each weekday pair, directly on the chart — a 56% bar built on n=49 needs to visually read as less certain than it would with n=500
- **Exit-reason breakdown:** of all trades, what % closed via SL, +3% floor, +5% floor, +10% lock, +15% target, or expiry — tells you which part of the ladder is actually doing the work
- **Equity curve:** cumulative simulated P&L from the CE/PE trades, split by weekday pair (does Tue→Wed carry the strategy, or does one pattern dominate/drag)
- **In-sample vs out-of-sample comparison:** `p_up` as measured on the first half vs the realized win rate when traded on the second half — the single most important number in the whole project, per Section 5
- **Benchmark comparison:** what a "trade every signal day, no ladder, just hold to expiry" version would have made, so you can see how much the exit ladder itself is adding or costing

## 9. Known Limitations to State Upfront in Any Report

1. ~246 days total, split further into build/test halves and then into 5 weekday buckets — each bucket ends up with roughly 20–25 out-of-sample occurrences at most. That is a small sample for a real edge claim; treat all `p_up` numbers as noisy estimates, not settled facts
2. Simulated option prices are not real market prices — real CE/PE prices reflect skew, term structure, and supply/demand that flat-IV BS ignores
3. The exit ladder is evaluated at daily close only (no intraday data available for free at this stage) — a real +10%-then-pullback-to-10% sequence could look completely different intraday than it does on a daily-close approximation
4. No transaction costs, slippage, or bid-ask spread modeled — short-dated option trading in reality is heavily eroded by these
5. Day-of-week seasonality effects, if any exist, are well-documented in academic literature as weak and unstable across regimes — this plan is structured to test honestly for that rather than assume it, per Section 5's in-sample/out-of-sample split

## 10. Suggested Staged Build Order (once you're ready to code)

1. Data loading + cleaning + weekday-pair tagging (decide (a) vs (b) bucketing from Section 4)
2. Build the weekday-pair probability table on the in-sample half, with confidence intervals — produces the core probability chart
3. Black-Scholes pricing module (standalone, testable independent of the signal logic) — needs a weekly-expiry calendar (which weekday is NIFTY's current expiry day — worth confirming, this has changed on NSE before)
4. Exit-ladder state machine (Section 6), unit-tested on a few hand-constructed price paths before running on real data, since the path-dependency is easy to get subtly wrong
5. Backtest engine: signal table → trade decision → BS pricing → ladder → P&L, run on out-of-sample half only
6. Visualization suite (probability chart, exit-reason breakdown, equity curve, in-sample vs out-of-sample comparison)
7. Write-up of results + limitations

## 11. Open Decisions Still Needed Before Coding

- Exact flat IV number (12%? 13%? something else?)
- Exact risk-free rate to hard-code
- Current NIFTY lot size to use
- Bucketing method for weekday pairs: strict calendar weekday names, or trading-day position (Section 4)
- In-sample/out-of-sample split for the table itself: confirm you want the table built on one half and traded on the other (Section 5) — or if you'd rather build the table on the full year and accept that as a v1 known limitation, saving the honest split for a v2
- Confirm the path-dependency reading in Section 6 (does hitting +10% then dropping to +6% count as breaching the +3% floor, or does banking +5% permanently retire that floor?)
