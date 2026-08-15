# Run: 3-pair filter (Tue->Wed, Thu->Fri, Mon->Tue)

**Date:** 2026-08-15
**Config:** current `nifty_gap/config.py` defaults (two-sided ladder: loss stops -3/-5/-7, trailing profit floors +5/+10/+15, fill = observed close)
**Traded pairs:** only Tue->Wed, Thu->Fri, Mon->Tue (all other pairs set non-tradeable at runtime; no code changes)

## Results
- 138 trades | P&L **+₹176,816** | win rate 26.1% | profit factor 1.39 | max drawdown 1.86%
- Exit mix: stop_7=87, expiry=40, floor_15=6, stop_5=3, stop_3=1, floor_10=1

| Pair | Trades | Side | P&L | Win rate |
|------|--------|------|-----|----------|
| Tue->Wed | 46 | CE | +₹123,054 | 37.0% |
| Thu->Fri | 44 | PE | +₹35,450 | 20.5% |
| Mon->Tue | 48 | CE | +₹18,313 | 20.8% |

## Notes
- Tue->Wed carries the book; Thu->Fri and Mon->Tue are marginal.
- stop_7 is still the dominant exit (87/138) - gap-through stops.
- Full-sample (all pairs) run was -₹74,139; filtering to these 3 pairs flips it positive, so pair selection matters more than the ladder tuning.
- Files: trades.csv, equity.csv, stats.json, params.json, 4 charts.
