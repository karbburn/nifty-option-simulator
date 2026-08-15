# Run: 3 pairs + Fri->Mon as opposite side (CE -> PE)

**Date:** 2026-08-15
**Config:** current `nifty_gap/config.py` defaults (two-sided ladder: loss stops -3/-5/-7, trailing profit floors +5/+10/+15, fill = observed close)
**Traded pairs:** Tue->Wed, Thu->Fri, Mon->Tue (unchanged) + Fri->Mon with its **side flipped to the opposite** (Fri->Mon is normally CE per the probability table; this run forces PE). Done at runtime; no code changes.

## Results
- 185 trades | P&L **+₹154,303** | win rate 24.9% | profit factor 1.23 | max drawdown 2.97%
- Exit mix: stop_7=122, expiry=48, floor_15=8, stop_5=4, stop_3=1, floor_5=1, floor_10=1

| Pair | Trades | Side | P&L | Win rate |
|------|--------|------|-----|----------|
| Tue->Wed | 46 | CE | +₹123,054 | 37.0% |
| Thu->Fri | 44 | PE | +₹35,450 | 20.5% |
| Mon->Tue | 48 | CE | +₹18,313 | 20.8% |
| Fri->Mon | 47 | PE | **-₹22,512** | 21.3% |

## Why Fri->Mon loses on BOTH sides (see temp_results/three_pair for the 3-pair baseline)
- The loss is **weekend time decay (theta), not direction**.
- Friday->Monday spot barely moves (mean -0.03%, |spot| ~0.7%), but the option premium collapses ~30% on both CE and PE (median -27% CE, -31% PE).
- Why: the Friday entry is priced with ~6 days of time value (weekend counted as live days); Monday's close re-prices with 3 of those days gone. The model uses **flat 12.5% IV**, so it charges no weekend volatility premium on Friday - the inflated Friday premium is simply deflated Monday morning.
- The ladder's first stop is -3% on the premium, so ~70% of Fri->Mon trades get stopped out by theta alone (stop_7 dominates: 122/185 across the run; 33-35 of 47 Fri->Mon trades are stop_7).
- The rare expiry winners (8 expiry PE = +₹197,654) don't offset the theta stops.

## Conclusion
Flipping the side does not fix Fri->Mon - the pair loses because of how the model prices the weekend, not because the signal direction is wrong. Dropping Fri->Mon entirely (as in the 3-pair run) is better.

- Files: trades.csv, equity.csv, stats.json, params.json, 4 charts.
