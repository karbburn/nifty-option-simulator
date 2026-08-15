# Run (v2): 3-pair + Fri->Mon opposite (PE), with Friday 7/10/13 ladder

**Date:** 2026-08-15
**Config:** current `nifty_gap/config.py` defaults, now with `ladder_floor_pcts_friday = (0.07, 0.10, 0.13)` (committed `63ab55d`). Friday entries trail profit floors from +7% instead of +5%; other days keep 5/10/15. Loss stops -3/-5/-7 unchanged.
**Traded pairs:** Tue->Wed, Thu->Fri, Mon->Tue + Fri->Mon. Fri->Mon forced to the **opposite side** (PE) of the signal.

## Results
- 185 trades | P&L **+₹154,303** | win rate 24.9% | profit factor 1.23 | max drawdown 2.97%
- Exit mix: stop_7=122, expiry=48, floor_15=6, floor_13=2, stop_5=4, stop_3=1, floor_7=1, floor_10=1

| Pair | Trades | Side | P&L | Win rate |
|------|--------|------|-----|----------|
| Tue->Wed | 46 | CE | +₹123,054 | 37.0% |
| Thu->Fri | 44 | PE | +₹35,450 | 20.5% |
| Fri->Mon | 47 | PE | -₹22,512 | 21.3% |
| Mon->Tue | 48 | CE | +₹18,313 | 20.8% |

## Notes
- Total P&L identical to the v1 opposite run; only the exit-reason labels shifted (floor_7 / floor_13 now appear instead of some floor_15) because the Friday ladder changed which floor level banks.
- The higher +7% Friday start does **not** rescue Fri->Mon: stops still dominate (122/185 stop_7 overall) and the pair stays at -₹22,512, consistent with the weekend-theta diagnosis.
- Files: trades.csv, equity.csv, stats.json, params.json, 4 charts.
