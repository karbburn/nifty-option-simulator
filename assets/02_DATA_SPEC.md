# 02 — Data Spec

## Source file

`NIFTY_50-14-08-2025-to-14-08-2026.csv` — 246 rows, one per trading day, descending date order (most recent first).

Raw columns (note trailing spaces and BOM in header row — must be stripped):
```
﻿Date , Open , High , Low , Close , Shares Traded , Turnover (₹ Cr)
```

## Cleaning steps

1. Read with encoding that handles the BOM (`utf-8-sig`)
2. Strip whitespace from all column names → `Date, Open, High, Low, Close, Shares_Traded, Turnover_Cr`
3. Parse `Date` from `DD-MMM-YYYY` (e.g. `14-AUG-2026`) to a proper date type
4. Sort ascending by date (currently descending)
5. Validate: no duplicate dates, no null OHLC values, `High >= max(Open, Close)` and `Low <= min(Open, Close)` for every row (sanity check for data corruption)
6. Cast Open/High/Low/Close to float, Shares_Traded to int, Turnover_Cr to float

## Derived columns

| Column | Formula | Purpose |
|---|---|---|
| `weekday` | day name of `Date` (Mon/Tue/Wed/Thu/Fri) | bucketing key |
| `prev_close` | `Close.shift(1)` | previous trading day's close |
| `prev_weekday` | `weekday.shift(1)` | previous trading day's weekday label |
| `weekday_pair` | `prev_weekday + "→" + weekday` | e.g. `"Tue→Wed"` — the signal bucket key |
| `gap_up` | `1 if Open > prev_close else 0` | the outcome label |
| `gap_pct` | `Open / prev_close - 1` | magnitude of the gap (for diagnostics, not used in the core signal) |

## Weekday-pair bucketing rule (locked decision)

**Strict calendar weekday bucketing** (not trading-day-position bucketing). This means:
- A pair is labeled by the actual weekday names involved, however they occurred (e.g. if Monday was a holiday, a Friday→Tuesday transition is labeled `Fri→Tue`, and is a *separate* bucket from `Mon→Tue`)
- This is simpler and matches the literal calendar-day story you're trading, but means holiday-adjacent transitions (`Fri→Tue`, `Wed→Fri`, etc.) will have very small sample counts — some may have n<5. These irregular pairs should either be excluded from trading (insufficient sample) or explicitly flagged with a "low confidence — do not trade" tag rather than silently folded into the regular five pairs.
- The five "regular" pairs (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri, Fri→Mon) will carry the vast majority of the ~245 pair-observations and are the ones that actually get traded in practice.

## Known data quirks to check for during Stage 1

- Confirm the file only contains NSE trading days (no weekend/holiday rows already present — if some are, they must be dropped, not treated as valid gap observations)
- Spot-check a few known Indian market holidays in the Aug 2025–Aug 2026 window to confirm they're correctly absent from the file
- Confirm `Shares_Traded` and `Turnover_Cr` have no zero/null rows (would indicate a data issue on that date, e.g. a special trading session)
