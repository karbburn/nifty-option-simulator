# Run (v2): 3-pair filter with Friday 7/10/13 ladder

**Date:** 2026-08-15
**Config:** current `nifty_gap/config.py` defaults, now with `ladder_floor_pcts_friday = (0.07, 0.10, 0.13)` (committed `63ab55d`). Friday entries trail profit floors from +7% instead of +5%; other days keep 5/10/15. Loss stops -3/-5/-7 unchanged.
**Traded pairs:** Tue->Wed, Thu->Fri, Mon->Tue only (no Friday pair, so this run is a control).

## Results
- 138 trades | P&L **+₹176,816** | win rate 26.1% | profit factor 1.39 | max drawdown 1.86%
- Exit mix: stop_7=87, expiry=40, floor_15=6, stop_5=3, stop_3=1, floor_10=1

| Pair | Trades | Side | P&L | Win rate |
|------|--------|------|-----|----------|
| Tue->Wed | 46 | CE | +₹123,054 | 37.0% |
| Thu->Fri | 44 | PE | +₹35,450 | 20.5% |
| Mon->Tue | 48 | CE | +₹18,313 | 20.8% |

## Notes
- **Identical to the original three_pair run** (same folder). Expected: no Friday pair trades here, so the Friday ladder change has no effect.
- Files: trades.csv, equity.csv, stats.json, params.json, 4 charts.
