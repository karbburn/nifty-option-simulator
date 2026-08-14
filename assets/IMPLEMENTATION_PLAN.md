# NIFTY Day-of-Week Gap Probability & Options Trade Simulator — Implementation Plan

Written as a joint finance + engineering plan. Goal: build a **research/backtesting tool** (not a live system) that measures weekday-pair gap probabilities, converts them to CE/PE trade rules, prices options with Black-Scholes, manages trades via a GTT-style premium-% ladder, and honestly reports results and limitations.

Deliverable of *this* document: the full phased build plan, algorithm specifications, config registry, decision log, testing strategy, and acceptance criteria. Nothing here is code yet.

---

## 1. What we are building (one-paragraph view)

For each weekday pair (Mon→Tue, Tue→Wed, Wed→Thu, Thu→Fri, Fri→Mon) we compute how often the second day's **Open** exceeds the first day's **Close**. If a pair's historical P(up) > 50% we trade that pattern long ATM **Call**; else long ATM **Put**. Entry: at **Close of day1**, priced via Black-Scholes (ATM strike, nearest ₹50, flat IV 12.5%). Exit: a ratcheting target/stop ladder on the **option premium's own % move** (hard SL −7%, floors at +3%/+5%/+10%, final target +15%), or forced exit at the next weekly expiry. Outputs: probability chart with confidence intervals, exit-reason breakdown, portfolio equity curve, benchmark comparison, and an honest limitations register.

---

## 2. Sources of truth

| Doc | Purpose | Status |
|---|---|---|
| `assets/01_PROJECT_OVERVIEW.md` | Vision + locked decisions + doc map | Read |
| `assets/02_DATA_SPEC.md` | Cleaning, schema, weekday tag rules, data quirks | Read |
| `assets/nifty-gap-options-project-plan.md` | v2 plan: signal, pricing, ladder, backtest, limitations, staged order | Read |
| `assets/NIFTY 50-14-08-2025-to-14-08-2026.csv` | 1 yr daily OHLC, 246 rows, descending order, BOM + trailing-space header | Read (sample) |
| `assets/AGENTS.md` | Behavioral guidelines (think-first, simplicity, surgical changes, goal-driven execution) | Adopted as working rules |

**Note:** Docs 03–09 (`03_SIGNAL_METHODOLOGY` … `09_ASSUMPTIONS_LIMITATIONS`) and `IMPLEMENTATION_PROMPTS.md` referenced in the overview **do not exist** in `assets/`. This plan is therefore the authoritative build specification; where it disagrees with the v2 plan we say so explicitly (see §8 Decision log).

---

## 3. Architecture & data flow

```
 data/

   GH Action (nightly 17:00 IST) ──► refresh.py: NSE attempt → yfinance fallback ──► upsert data/nifty50_history.csv (commit-if-changed)
   │
   ▼
 assets/*.csv  (seed, tagged source=nse)
   │   read utf-8-sig, strip header spaces, parse DD-MMM-YYYY, sort asc
   ▼
 [Cleaning & Validation]  →  clean OHLC df + derived cols
   │                       (weekday, prev_close, prev_weekday, weekday_pair, gap_up, gap_pct)
   ▼
 [Probability Table]      →  per-weekday-pair: n, p_up, 95% CI (Wilson), side (CE/PE), sample flag
   │                                          ▲ used both as "report" and "trade config"
   ▼
 [Signals]  →  ordered list of trade candidates: (entry_date=day1, pair, side)
   │
   ▼
 [Options Stack]                    ┌──────────────────────────────┐
   BS pricer (S,K,σ=12.5%,r,T)      │ [Ladder state machine]       │
   expiry calendar (weekly, day=?)  │  pure function over the      │
   strike router (nearest ₹50)      │  observed premium path →     │
   rate source (config→env→default) │  exit_reason + exit price    │
   └──────────────────────► re-price same option each subsequent close │
   ▼
 [Backtest Engine]  →  for each candidate: BS entry @Close[day1] → walk days
                        re-marking premium until ladder/expiry → trade P&L = (exit−entry)×lot
                        (engine is portfolio-aware: positions can overlap)
   ▼
 [Benchmark variant]  →  identical but "hold to expiry, no ladder"
   ▼
 [Metrics & Reporting]  →  win rate, avg win/loss, profit factor, Sharpe, max DD,
                           exit-reason %, per-pair P&L, IS-vs-OOS diagnostic
   ▼
 [Visualization]  →  probability chart, exit-reason breakdown, equity curve,
                     benchmark overlay, OOS diagnostic → PNGs
   ▼
 [Write-up]  →  REPORT.md embedding numbers + limitations register
```

### Directory layout (target)

```
nifty-gap-simulator/
├─ data/                          # input CSV lives here (seed) + maintained nifty50_history.csv
├─ nifty_gap/
│  ├─ config.py                   # single source of truth for ALL parameters
│  ├─ data/
│  │  ├─ loader.py                # read, parse, sort, dtype-cast (both seed & history file)
│  │  ├─ validation.py            # integrity + holiday/gap sanity checks
│  │  └─ refresh.py               # daily fetch: NSE attempt → yfinance fallback, upsert
│  ├─ signals/
│  │  └─ probability_table.py     # n, p_up, Wilson CI, side, flags
│  ├─ options/
│  │  ├─ black_scholes.py         # CE/PE pricer (T=0 safe), parity test helper
│  │  ├─ calendar.py              # weekly expiry calendar
│  │  └─ strikes.py               # nearest-₹50 routing
│  ├─ trade/
│  │  └─ ladder.py                # pure state machine (no BS knowledge)
│  ├─ backtest/
│  │  └─ engine.py                # orchestration + portfolio MTM + benchmark mode
│  ├─ reporting/
│  │  ├─ metrics.py               # trade/portfolio stats
│  │  └─ report.py                # REPORT.md / JSON export
│  └─ visualization/
│     └─ charts.py                # the 5 PNG outputs
├─ .github/workflows/
│  └─ refresh-data.yml            # nightly: run refresh.py, commit-if-changed
├─ tests/                         # pytest, one module per layer
├─ output/                        # charts, exports, REPORT.md
├─ pyproject.toml
├─ README.md
└─ IMPLEMENTATION_PLAN.md
```

### Tech stack (free tier, minimal)

| Tool | Purpose | Notes |
|---|---|---|
| Python 3.11+ | runtime | single free-tier language, keeps portfolio consistent |
| pandas | data frame ops | cleaning, derived cols, aggregations |
| numpy | vectorized math | BS, CI, metrics |
| scipy | `stats.norm`, beta/CI math | Wilson/Clopper-Pearson optional exact CI |
| matplotlib | all charts | static PNGs, no web UI in v1 |
| pytest | unit + integration tests | required gate per phase |
| ruff | lint | run before each phase commit |
| git | version control | one atomic commit per phase, conventional messages |
| yfinance | **daily data fallback** | `^NSEI`, free, no API key (validated against our CSV, Ohio 2026-08-13/14 match exactly) |
| curl_cffi | NSE API scrape attempt | browser-fingerprint impersonation; best-effort primary, see Akamai finding below |
| GitHub Actions | scheduled nightly data refresh | cron weekday 17:00 IST, commit-if-changed |

**No** broker API, no DB, no Streamlit (see §11 stretch). Rationale: simplicity-first per AGENTS.md. Notes: `yfinance` is *not* a locked data source of record — it is the scheduled fallback; the uploaded NSE CSV remains the historical seed. Data-source provenance is tracked per row (§5.7).

---

## 4. Parameter / config registry

Single `config.py` (dataclass or frozen dict). Every number below is exposed + documented; nothing is silently hardcoded twice.

| Key | Default | Locked/Open | Rationale / note |
|---|---|---|---|
| `data_path` | `data/NIFTY_50-…csv` | locked | the uploaded file (historical seed) |
| `data_history_path` | `data/nifty50_history.csv` | new | maintained, append-only-by-date file produced by §5.7 |
| `refresh_provider_order` | `["nse", "yfinance"]` | open | NSE attempt first, yfinance fallback (§5.7) |
| `refresh_schedule_tz` | Asia/Kolkata, weekdays 17:00 IST | open | after close (15:30) + ~1.5 h for finalized Yahoo rows |
| `iv_flat` | 0.125 | **locked** (12.5%) | flat across time & strike; entry==exit IV so premium moves show spot+theta only |
| `rate_source` | `config` | open (see §8 #3) | dynamic-at-runtime is stated; we implement best-effort fetch with graceful fallback |
| `rate_default` | 0.065 | open | RBI repo proxy; BS rho for 7-day options is negligible → precision doesn't matter |
| `expiry_weekday` | `Thu` | **open** | current NSE weekly expiry is Thursday; v2 plan's "7/6 day" example implies Friday — confirm (§8 #4) |
| `strike_interval` | 50 | locked | NIFTY strike interval |
| `strike_tie_rule` | half-up | open | ₹24725→24750 (§8 #6) |
| `lot_size` | 75 | **open** | NIFTY lot changes periodically; verify current (§8 #5) |
| `min_pair_sample` | 5 | open | pairs with n<5 excluded from trading, flagged on chart (§8 #2) |
| `ladder.sl_pct` | −7 | locked | hard stop, no exceptions |
| `ladder.floor_pcts` | [3, 5, 10] | locked | ratcheting floors: +3 → +5 → +10 |
| `ladder.target_pct` | 15 | locked | final target |
| `ladder.fill_mode` | `observed_close` | **open** | fill-at-observed-close (conservative) vs fill-at-floor (GTT-optimistic) (§8 #1) |
| `ci_alpha` | 0.05 | open | Wilson 95% |
| `validation_mode` | `full_sample` | locked (flagged) | doc 01 locks full-sample table; we add `oos_diagnostic` as a *separate diagnostic report*, not the main line (§8 #7) |
| `position_mode` | fixed 1 lot, every signal day | locked | no skip rule, no conviction filter |

---

## 5. Algorithm specifications (precise, implementation-ready)

### 5.1 Data pipeline (per `02_DATA_SPEC.md`, extended for multi-source)

Schema: the maintained `data/nifty50_history.csv` carries one extra column `data_source` (`nse` | `yfinance`); the uploaded seed file has no such column (legacy → tagged `nse` on ingestion). The core `Date, Open, High, Low, Close` set is mandatory from every source; `Shares_Traded, Turnover_Cr` are mandatory for `nse` rows and **null-allowed** for `yfinance` rows (Yahoo does not provide them — see §5.7).

1. Read with `encoding="utf-8-sig"` (kills BOM).
2. Strip whitespace from header tokens → `Date, Open, High, Low, Close, Shares_Traded, Turnover_Cr[, data_source]`.
3. Parse `Date` as `DD-MMM-YYYY` (case-insensitive month names; `14-AUG-2026` style).
4. Sort ascending by date (source is descending).
5. Cast: OHLC → float, `Shares_Traded` → int (NaN-safe), `Turnover_Cr` → float (NaN-safe).
6. Derived columns:
   - `weekday` = `Date.dt.day_name()` (Mon/Tue/Wed/Thu/Fri)
   - `prev_close` = `Close.shift(1)`
   - `prev_weekday` = `weekday.shift(1)`
   - `weekday_pair` = `prev_weekday + "→" + weekday` (e.g. `Tue→Wed`)
   - `gap_up` = `1 if Open > prev_close else 0` (strict; equality counts down — note in report)
   - `gap_pct` = `Open / prev_close − 1` (diagnostic only)
7. Integrity assertions (fail loudly, not silently):
   - No duplicate dates; no null OHLC (any source).
   - `High >= max(Open,Close)` and `Low <= min(Open,Close)` on every row.
   - For `nse` rows only: `Shares_Traded > 0`, `Turnover_Cr > 0`.
   - Average row count per weekday ≈ 49 (expect 48–50 since the year starts mid-Aug).
   - **Gap sanity:** `Date.diff()` (calendar days) must be ≤ 4 for consecutive rows (mon–fri max 3, plus-holiday max 4). Anything > 4 ⇒ missing trading day ⇒ hard error.
   - No weekend rows (Sat/Sun must not appear).
   - Holiday spot-check: assert the file has *no* row on a small documented list {Independence Day 15-Aug-2025, Gandhi Jayanti 02-Oct-2025, Christmas 25-Dec-2025, Republic Day 26-Jan-2026}; **and** confirm the full 2025–26 NSE holiday calendar against NSE's site during Phase 2 execution (not guessed now — never fabricate market-calendar facts).

### 5.2 Probability table & signals

- Bucketing: **strict calendar weekday names** (locked). Holiday-adjacent transitions (e.g. Fri→Tue when Monday is a holiday) form their own small buckets.
- Per bucket compute:
  - `n` = count of observations
  - `p_up` = `gap_up.mean()` (fraction where Open[day2] > Close[day1])
  - **Wilson** 95% CI: with $z=1.96$, $\hat p=p_{up}$, `den = 1 + z²/n`, `center = (p̂ + z²/2n)/den`, `half = z·sqrt((p̂(1−p̂))/n + z²/4n²)/den`. (`n=0` → CI undefined, flag, do not trade.)
  - `side` = `CE` if `p_up > 0.5` else `PE` (pure majority; `p_up == 0.5` → PE by `else`; document).
  - `tradeable` = `n >= min_pair_sample` (default 5). Non-tradeable rows still get charted and reported — never silently folded into a regular pair.
- Table is the single source for signal direction; every tradeable signal day trades (no skip).

### 5.3 Options stack

**Black-Scholes-Merton (European; institutions NIFTY options are European — appropriate, not just an approximation):**

```
d1 = (ln(S/K) + (r + σ²/2)·T) / (σ·√T)
d2 = d1 − σ·√T
C  = S·N(d1) − K·e^(−rT)·N(d2)
P  = K·e^(−rT)·N(−d2) − S·N(−d1)
```
- `T = calendar_days / 365` (calendar-day convention; weekends do decay premium). T ≥ 0.
- **T=0 guard:** return intrinsic `max(S−K,0)` / `max(K−S,0)`; never feed `ln(0)`.
- Same `σ = 0.125` and same `r` mark every observation → premium movement reflects only spot + theta (by design; flat IV is a stated simplification).
- **Parity invariant test:** `C − P ≈ S − K·e^(−rT)` to 1e-6 relative.
- Boundary tests: deep-ITM call → `S − K·e^(−rT)`; deep-OTM → ≈ 0; monotone increasing in S (call), decreasing in S (put), increasing in σ.

**Strike router:** ATM strike = round-to-nearest₹50 of `Close[day1]`, tie → half-up (₹24725 → 24750). Config override exists.

**Expiry calendar:** configurable weekday (default Thu). `next_expiry(entry_date) = earliest expiry_date where (expiry_date − entry_date).days >= 1`. Consequences: Wed→Thu entry (Wed close) → Thu expiry (T≈1 day); Thu→Fri entry → following Thursday (T=7); Fri→Mon entry → following Thursday (T=6). Verify the "7/6-day entry/exit" claim in the v2 plan — it only holds under a *Friday* expiry (§8 #4).

**Rate source:** `get_risk_free_rate()` = (env/CLI override) → (attempted runtime fetch) → config default (6.5%), always with a logged source note. BS rho ≈ 0 for 7-day options, so the default is financially harmless; the "dynamic" requirement is honoured as best-effort-with-fallback and documented.

### 5.4 Exit-ladder state machine (the delicate part)

Pure function `simulate(premium_path, entry_premium) -> {exit_idx, exit_reason, exit_price}`. Knows nothing about BS/spot — fully deterministic and unit-testable on hand-built premium arrays.

Definitions: `P0` = entry premium; observation `M_t = P_t/P0 − 1` (premium % move tracked **from entry each day's close**); `floor` = current ratchet level or `None`; `state ∈ {armed, at3, at5, at10}`; evaluation order below is the contract for edge cases.

**Per observation (in priority order):**
1. `M_t ≤ −7%` → **EXIT (SL)**. Hard stop, no exceptions, evaluated first.
2. `state == at10 and M_t ≥ +15%` → **EXIT (target)**. (Priority 2 keeps an exact +15% close from being misread as a floor-break.)
3. If a floor is banked and `M_t ≤ floor` → **EXIT (floor)**, reason named by the *banked* floor (`+3%` / `+5%` / `+10%` lock). (`≤` inclusive = conservative reading of "falls back through".)
4. Else, ratchet forward (order matters):
   - `state == armed and M_t ≥ +3%` → `state=at3`, bank floor +3%.
   - `state == at3 and M_t ≥ +5%` → `state=at5`, floor ratchets to +5% (the +3% floor is permanently retired).
   - `state == at5 and M_t ≥ +10%` → `state=at10`, floor ratchets to +10% (= the "resistance test": hold for +15%, give back no more than to +10%).
   - `state == at10 and M_t ≥ +15%` → handled by rule 2.
5. If expiry reached with no trigger → **EXIT (expiry)** at T=0 intrinsic.

**Path-dependency contract (answers v2 §11's open question):** once +5% is banked it permanently retires +3%; once +10% is banked it retires +5%. So **+10% → +6%** exits at the *+10% lock* (not the +3% floor). This is exactly why the ladder is a state machine and not independent if/else checks.

**Fill convention (§8 #1, default `observed_close`):** one close per day; when a floor/SL is first breached the fill is the **observed close premium** that day, not a synthetic "perfectly at the trigger" price. Rationale: with daily data we cannot prove the spot traded through the trigger intraday; optimistic "fill-at-floor" overstates fills on gap-through days. `fill_mode` is config so the user can toggle and quantify the difference (Phase 11).

**Expected-behaviour sanity check (finance note, not a rule):** with σ=12.5%, a 7-day ATM premium is ~₹90–150 on a ~₹24,500 index (≈ 0.2σ√T·S), one-day spot vol ≈ 0.79% ≈ ₹194, and ATM delta ≈ 0.5 ⇒ a ±1% spot day moves premium ±50%+. The ±3/5/10/15% premium ladder is therefore **far tighter than one day of realized premium volatility**. Consequence: most trades are expected to exit within 1–3 days, dominated by SL or the upper targets (there is rarely a slow grind for the mid-floors to matter). This is an *empirically verifiable expectation*, checked in Phase 7 exit criteria and discussed in the final report — **we do not silently "tune" thresholds** without sign-off.

### 5.5 Backtest engine & P&L

- For each tradeable signal day (with a valid previous day):
  1. Side from the probability table; strike = nearest₹50(Close[day1]); entry premium = BS(S=Close[day1], T=days_to_next_expiry).
  2. Walk subsequent trading days re-marking the *same* option at each day's Close until the ladder triggers or expiry. (Daily-close granularity is a locked simplification; no intraday path — stated in limitations.)
  3. Record: entry_date, entry_premium, exit_date, exit_premium, exit_reason, days_held, pair, side.
  4. `trade_pnl = (exit_premium − entry_premium) × lot_size` (both CE and PE are bought long, so the formula is side-symmetric).
- **Portfolio awareness:** positions overlap by design (e.g. Fri→Mon, Mon→Tue, Wed→Thu can all be live simultaneously). Engine maintains a position book + daily mark-to-market equity = realized cash + Σ(open position marks). Sharpe/DD are computed on this *portfolio* MTM series (§5.6), not on independent per-trade lines.
- **Benchmark variant:** identical universe, `ladder` disabled, forced exit at expiry. Difference = ladder's contribution. Run side-by-side from the same entry set.
- **OOS diagnostic (separate from the main run):** build the table on the *first half* of dates, trade the *second half*, and compare realized trade win-rate vs the table's `p_up` (with its own CI). Runs as `--oos-diagnostic`; the main deliverable stays full-sample per the locked decision (§8 #7).

### 5.7 Daily data-refresh pipeline (scraper + GitHub Actions)

**Feasibility finding (verified 14-Aug-2026, live probe):** the NSE historical-index page loads as plain HTML, but its JSON/CSV export APIs sit behind **Akamai Bot Manager** (`_abck`, `bm_sz` cookies). A plain `requests` session that performs the classic "hit home → hit page → call API" handshake still gets `home=403`, `api=503` — the old session-cookie trick documented by most tutorials is dead. Upgrade tried 15-Aug-2026: `curl_cffi` browser-fingerprint impersonation (`chrome`/`chrome99..131`/`safari/`firefox`) gets further into the flow (page 200, Akamai cookies issued) but the API still returns `503` from this IP — Akamai's JS sensor solve for `_abck` cannot be produced without a headless-stealth browser, which is out of scope (fragile + ToS-gray + near-useless from GitHub Actions shared IPs). **yfinance `^NSEI` works reliably** and was validated to reproduce our CSV's OHLC exactly for 2026-08-10→14 (e.g. 13-Aug `Close` 24395.85, 14-Aug `Close` 24366.0). Conclusion: schedule the robust fallback (`yfinance`), keep the `curl_cffi` NSE attempt as best-effort primary (a strict improvement over plain `requests`, and may work from some residential IPs if Akamai softens).

Pipeline design (`nifty_gap/data/refresh.py`, run by GH Action weekday 17:00 IST):

1. **Determine fetch window:** `max(data_history.csv.Date) + 1` → today. If window is empty → no-op exit 0 (holiday / data-current).
2. **Provider 1 — NSE (best-effort):** `requests.Session()`; warm up with `GET /reports-indices-historical-index-data` (UA + `Accept-Language` headers), 2 s pause, then `GET /api/historical/indicesHistory?indexType=NIFTY%2050&from=…&to=…` with `Referer`. Any non-200 → **skip to provider 2, record `warn:nse_blocked`** (don't retry harder; anti-bot).
3. **Provider 2 — yfinance (fallback):** `yf.download("^NSEI", start=window_start, end=today+1, auto_adjust=False, threads=False, progress=False)`; take the OHLCV `Close` frame, rename `Open/High/Low` explicitly (never rely on `Adj Close`); **drop the current UTC day's row if `Volume == 0` or price is provisional** (today's bar is not final until after ~18:30 IST); map `Volume` (in thousands) to `Shares_Traded`? **No** — Yahoo index volume is *not* NSE `Shares_Traded`. Leave those two columns null for `yfinance` rows and let §5.1 validation relax them for `data_source="yfinance"`; the report footnote states the gap.
4. **Normalise:** both providers emit `Date(DD-MMM-YYYY), Open, High, Low, Close[, Shares_Traded, Turnover_Cr]` → tag `data_source`, cast to the §5.1 schema, no weekend rows (assert), no duplicate dates (assert), OHLC invariant checks (assert).
5. **Upsert:** append only rows with `Date` not already present (idempotent — reruns on the same day produce no changes). Never overwrite existing history.
6. **Commit-if-changed:** GH Action runs `git diff --quiet data/nifty50_history.csv || (git add + commit + push)` with `permissions: contents: write`. Identity: `github-actions[bot]`.
7. **Failure policy:** if *both* providers fail and there are missing trading days, run still exits 0 with a `warn:` log (a 403 that wakes a human tomorrow beats a red build); schedule keeps the loop self-healing. A manual `--backfill YYYY-MM-DD` mode exists for wholesale re-source.

Workflow (` .github/workflows/refresh-data.yml`): `schedule: cron "11 30 * * 1-5"` (17:00 IST), `workflow_dispatch` for manual backfill; python 3.12; `pip install -e .`; runs only `refresh.py` (never the backtest — backtesting is a deliberate, local, versioned act, not a cron).

### 5.6 Metrics (exact definitions)

| Metric | Definition |
|---|---|
| Total P&L | Σ trade P&L (₹) and per-pair |
| Win rate | % of trades with P&L > 0 (tie counts as loss; documented) |
| Avg win / avg loss / profit factor | gross wins ÷ Σ \|losses\| over count; factor = Σwins/Σ\|losses\| |
| Max drawdown | max peak-to-trough on portfolio MTM equity series |
| Sharpe (annualized) | `mean(daily_equity_returns)/std(daily_equity_returns) × √252` (trading-day returns, zero-return on flat days) |
| Exit-reason breakdown | % of trades + avg P&L per reason {SL, +3%, +5%, +10% lock, +15%, expiry} |
| Per-pair stats | n, p_up (with CI), side, traded count, win rate, total P&L |
| IS vs OOS | table p_up (±CI) vs realized OOS win rate (±CI) |

---

## 6. Open decisions (status: all confirmed by user on 14-Aug-2026)

| # | Decision | Resolution | Why |
|---|---|---|---|
| 1 | Ladder fill convention | **fill at observed close** ✅ | honest with daily data; `fill_mode` toggle still exists (Phase 11) to quantify optimism |
| 2 | Min pair sample to trade | **n ≥ 5** ✅ | per doc 02's "n<5" language; n<5 flagged "do not trade" |
| 3 | Risk-free source | **best-effort fetch with config fallback** (default 6.5%) | rho≈0 for 7-day options, so the default is financially safe |
| 4 | Weekly expiry weekday | **Thursday** ✅ | current NSE practice (moved from Friday Nov 2023); still re-verified live in Phase 5 |
| 5 | Lot size | default **75**, re-verify live in Phase 5 | NSE revises periodically; config so `P&L(₹)` stays right |
| 6 | Strike tie-rule | **half-up** (₹24725→24750) | determinism; negligible P&L effect |
| 7 | Validation scheme | **full-sample main line + mandatory OOS sidebar report** ✅ | honours doc 01's locked decision *and* v2 §5's methodological warning |

Pre-existing tension surfaced here (not resolved silently): v2 §5 argues the *table* must not be traded on the data it was built from; doc 01 §Locked decisions says full-sample. Our resolution: full-sample is the headline run (per doc 01), the split-half OOS diagnostic is a mandatory sidebar report so the honest comparison "P(up) 56% vs what actually happened out-of-sample" is always printed. If you'd rather make the split the headline, it's a one-line config change.

---

## 7. Phased build plan

Each phase: **Goal** → **Tasks** → **Exit criteria** → **Tests/artifacts**. Exit criteria are objective so we can loop independently. Phases are sequential except where noted; each ends with a green test run + `ruff` + one atomic git commit.

### Phase 1 — Scaffolding & config
- **Goal:** a runnable Python package with zero business logic and a single config source.
- **Tasks:** `pyproject.toml` (pandas, numpy, scipy, matplotlib, pytest, ruff, dev deps); package skeleton per §3; `config.py` implementing §4 registry; empty-but-wired module tree; `tests/conftest.py` + smoke test that imports the package and prints the resolved config.
- **Exit:** `pytest` green (≥2 tests), `ruff check` clean, `python -m nifty_gap --print-config` prints full resolved registry.
- **Artifacts:** skeleton commit.

### Phase 2 — Data pipeline
- **Goal:** turn the raw CSV into the validated, derived-column frame of §5.1.
- **Tasks:** loader (BOM/space/parse/sort/casts); validators (rows, nulls, OHLC sanity, weekend absence, gap>4 detection, holiday spot-checks incl. verifying the full NSE 2025–26 holiday list live); derived columns incl. weekday-pair tagging; a `data_profile()` report (row counts per weekday, per pair; shares/turnover zeros).
- **Exit:** 246 rows, no nulls, `High/Low` invariants hold on all rows, weekday distribution ≈ 48–50/weekday, pair-observation count = 245 − holiday-crossings, zero weekend rows, maximum calendar gap ≤ 4 confirmed.
- **Tests:** loader fixtures incl. a BOM'd header, a bad-date row (fails), a weekend row (fails), a 5-day gap (fails); derived-column unit checks (known holiday → `Fri→Tue` label; `gap_pct` math).
- **Artifacts:** cleaned data profile, tiny CSV export for downstream dev.

### Phase 3 — Data refresh & automation pipeline
- **Goal:** a maintained, self-refreshing dataset: GH Action fetches nightly (NSE best-effort → yfinance fallback) and commits-if-changed.
- **Tasks:** `nifty_gap/data/refresh.py` per §5.7 (provider abstraction, session warm-up, yfinance fallback, upsert-by-date, provisional-row guard, `--backfill` mode); migrate `data/` to the managed `data/nifty50_history.csv` seeded from the uploaded CSV (seed rows tagged `nse`); `.github/workflows/refresh-data.yml` (cron `11 30 * * 1-5` = 17:00 IST, `workflow_dispatch`, `permissions: contents: write`, commit-if-changed); add `yfinance`, `requests` to `pyproject.toml`.
- **Exit (verified, not assumed):** offline tests green (upsert idempotency, provisional-row drop, dual-provider normalisation, date format parity); a *live* run from this machine appends the correct post-seed rows (e.g. the next trading day after the seed's max date) and the row count/latest date are sanity-printed; a manual workflow dispatch backfills a test range end-to-end; the action succeeds with `no changes` on rerun.
- **Tests:** fixtures for the NSE API JSON shape and yfinance frame (incl. the multi-level column quirk), upsert-no-duplicates, weekend-row rejection, OHLC invariant rejection, `Volume==0` provisional-row drop, both-providers-fail → exit 0 + `warn`.
- **Artifacts:** `refresh.py`, workflow YAML, `data/nifty50_history.csv`.

### Phase 4 — Probability table & signals
- **Goal:** produce the number that drives every trade: per-pair `n, p_up, Wilson CI, side, tradeable`.
- **Tasks:** implement §5.2; non-tradeable flags; table → CSV/JSON export (entry point to the visualization work later).
- **Exit:** hand-computed `p_up`/CI match for a 5-row synthetic sample; regular pairs all `n≥45`; every irregular pair either `n≥5` & tradeable or flagged; `p_up == 0.5` cases resolve to PE deterministically.
- **Tests:** Wilson interval edge cases (n=0, n=1, p=0 or 1 — CI must not produce [0,1] numerically NaN); side assignment; exclusion flag.
- **Log gates:** small-sample honesty is built here: any pair with n<30 gets bumped in the chart export regardless of tradeability.

### Phase 5 — Options stack
- **Goal:** trusted BS pricer + expiry calendar + strike router + rate sourcing.
- **Tasks:** §5.3 implementations; expiry calendar builder from data dates (`next_expiry` semantics incl. same-day close → next week); strike router; `get_risk_free_rate()` with fallback chain; **live verification during this phase**: current NIFTY lot size, current expiry weekday (NSE source) — update config if reality differs from defaults 75 / Thu.
- **Exit:** call-put parity holds to 1e-6 relative across 50 random (S,K,r,σ,T); T→0 collapses to intrinsic; deep-OTM ≈ 0; 24725→24750 tie-rule; Mon/Wed/Thu/Fri close all resolve to the *right* next expiry; black-box known value: a hand-computed premium matches BS to ~1e-6.
- **Tests:** parity, bounds, monotonicity, T=0 guard, strike ties, expiry calendar incl. holidays, rate fallback chain.

### Phase 6 — Ladder state machine
- **Goal:** the ratcheting exit logic as a pure, exhaustively-tested function (§5.4).
- **Tasks:** `simulate(premium_path, entry_premium, config)`; six exit reasons; ratchets; path-dependency contract; fill convention; T=0 expiry marking hook.
- **Exit:** every exit reason reached at least once in crafted paths; **all** of these paths behave *exactly* as specified: direct +15%; +3 touched then back to +2.9 (floor exit @+3%); +5 banked then +4 (floor +5%); +10 banked → +14 → +9 (lock @+10 observed-close); +10 → +6 (**lock, NOT +3 floor**); −7 SL from a banked floor (SL wins, priority rule); 10-day path, never triggers → expiry exit at T=0; exact-at-level ties (M=+5.00 on ratchet day) resolved deterministically.
- **Tests:** table-driven path fixtures; evaluation-order priority tests; determinism/immutability (no shared state); fill-mode toggle diff.
- **Finance check-in:** print avg days-to-exit across a quick BS-driven smoke path to confirm the "≤3-day typical hold" expectation of §5.4 before wiring the engine.

### Phase 7 — Backtest engine + benchmark
- **Goal:** connect signals + pricing + ladder into trade-level and portfolio-level results.
- **Tasks:** §5.5 engine incl. overlapping-position book and daily portfolio MTM; benchmark (no-ladder) mode; `--oos-diagnostic` mode; results export (trades CSV, portfolio equity CSV, params JSON for provenance).
- **Exit (objective, verifiable):** trade count = # tradeable signal days across the run; each trade's entry premium = BS(Close[day1]) exactly; exit prices match ladder outputs; P&L arithmetic = (exit−entry)×lot; portfolio equity is continuous (marks open positions on non-exit days); benchmark holds every trade to expiry; synthetic 2-week fixture produces hand-checkable trade-level records.
- **Tests:** end-to-end synthetic fixture (tiny cleaned frame) asserting every record; overlap case (two live positions same day) MTM correct; benchmark-vs-ladder counts identical except exits.
- **Log gate:** record realized exit-reason distribution + avg days held and ✓ against the §5.4 expectation. If wildly different, stop and report (investigate before proceeding — do not "fix" by tuning).

### Phase 8 — Metrics & reporting layer
- **Goal:** all §5.6 metrics computed, exported, reproducible.
- **Tasks:** metric functions on trades + portfolio MTM; per-pair and exit-reason aggregations; IS-vs-OOS diagnostic numbers; JSON export + a `REPORT.md` skeleton with placeholders.
- **Exit:** metric outputs match hand-computed values on the synthetic fixture; Sharpe/DD computed on the *right* (portfolio MTM) series; ISO8601 + git-sha provenance block printed into the report header.
- **Tests:** metric unit tests incl. empty-trade edge, single-trade edge, and the tie-counts-as-loss rule.

### Phase 9 — Visualization
- **Goal:** the five chart deliverables, publication-quality PNGs.
- **Tasks:** (1) probability chart — bars of `p_up` per pair, Wilson whiskers, dashed 50% line, `n` annotations, low-sample hatch, CE/PE colour; (2) exit-reason breakdown — bar + average-P&L per reason; (3) portfolio equity curve — total + per-pair lines (or stacked area), max-DD shaded; (4) benchmark overlay — strategy viz no-ladder; (5) OOS diagnostic — paired bars, table `p_up` vs realized win rate, CI whiskers on both.
- **Exit:** all five PNGs generated from real runs; visually reviewed (axis labels, `n` visible, 50% ref line, no overlapping text); saved to `output/`.
- **Tests:** chart functions run without error on synthetic results; file-existence + non-zero-size checks.

### Phase 10 — Write-up, docs, limitations register
- **Goal:** an honest, self-contained report; README; repo ready for the portfolio.
- **Tasks:** fill `REPORT.md` from Phase 8 exports — headline numbers, all charts, stated limitations (small n≈20–25 OOS per pair, BS-not-real-prices, flat IV, daily-close ladder granularity, no costs/slippage/bid-ask, weak & regime-unstable day-of-week seasonality per academic literature, full-sample build caveat, fill convention, refresh-source provenance incl. `yfinance`-rows-missing-shares/turnover); `README.md` (what/why/how to run, doc map, how the GH Action maintains data); final ruff + full test run; one release commit.
- **Exit:** a reviewer with no context can run the tool and understand results + limits from `REPORT.md` alone; AGENTS.md's "honest reporting" bar is met — the report explicitly refuses to claim an edge.

### Phase 11 — Robustness/sensitivity (stretch, optional)
- **Goal:** quantify how fragile the headline numbers are.
- **Tasks (each behind a flag, all cheap given the engine is tiny):** IV sweep {10%, 12.5%, 15%}; `min_pair_sample` sweep {3,5,10}; fill-mode toggle (observed vs at-floor, deltas reported); `p_up` bootstrap percentile interval (resample the 245 pairs, show the p_up distribution width); optional no-threshold variant (hold-to-expiry everywhere) as the ultimate "ladder does/doesn't add" statement.
- **Exit:** a sensitivity table in REPORT.md; no change to core modules unless a real bug appears.

### Dependency graph

```
1 ─► 2 ─► 3 ─► 4 ─► 5 ┐
      │                ├─► 7 ─► 8 ─► 9 ─► 10
      └► (3 can overlap 4-6; needed before 10)   └─(11 stretch)
```
- Phase 3 (data refresh) depends on Phase 2's loader/validator and can be built in parallel with Phases 4-6.
- Phase 10 must show data provenance from Phase 3 (source mix in the report).

---

## 8. Testing strategy summary

| Layer | Tests | Why |
|---|---|---|
| data | fixtures, invariants, holiday/gap detection | garbage-in guard; the CSV's quirks are documented, so prove we handle them |
| refresh | §5.7 providers, upsert, provisional-row drop, fail-policy | the nightly GH Action must be idempotent and self-healing, not flaky |
| signals | CI edges, side ties, flags | small-n honesty must not emit NaN/insane CIs |
| options | parity 1e-6, bounds, T=0, strikes, calendar | the number that prices every position; wrong here = everything wrong |
| ladder | exhaustive path table (§7/Phase 6) | path-dependency is the easiest place to get subtly wrong |
| engine | synthetic E2E, overlap MTM, benchmark | correctness of "trade count / P&L / equity" as *one* verifiable story |
| metrics | empty/single-trade edges, tie rule | stats must not silently mislead |
| viz | renders + files exist | deliverables are the point of the project |

Floating point: `pytest.approx`. Determinism: seed-free (no randomness anywhere in the core path).

---

## 9. Risk / limitations register (carried into REPORT.md)

1. **Sample size:** ~245 pairs split into 5 buckets then (diagnostic) into halves ⇒ ~20–25 OOS occurrences per pair max. All `p_up` are noisy estimates — Wilson CIs are shown, not hidden.
2. **Simulated prices:** BS with flat 12.5% IV is not a market price; real premium reflects skew/term structure/supply-demand. Entry==exit IV is a simplification, deliberate.
3. **Daily-close ladder:** no intraday path; a real +10%→+6% intraday round-trip reads differently at daily granularity.
4. **Costs omitted:** no slippage, brokerage, STT, or bid-ask. Short-dated options in reality are heavily eroded by these — the backtest's P&L is an upper bound on what a trader could actually harvest.
5. **Seasonality is weak/unstable by literature** across regimes — the plan is structured to *test* for a weekday tilt honestly, not to assume one.
6. **Ladder thresholds are tight vs realized premium vol** (§5.4): expect fast exits; results will be dominated by first-day moves, not ladder craftsmanship.
7. **Automated data sourcing is best-effort:** NSE's export APIs sit behind Akamai Bot Manager (verified 14–15-Aug-2026: plain `requests` → `403/503`; even `curl_cffi` browser-fingerprint impersonation → `503` from this IP, since Akamai requires its JS sensor solve). Bypassing the sensor is out of scope (fragile + ToS-gray). The nightly pipeline therefore runs yfinance as the reliable provider, with the curl_cffi NSE attempt as a best-effort primary that may work from some residential IPs. Consequences: (a) `yfinance` rows have no `Shares_Traded`/`Turnover_Cr` (report footnote, not a silent schema change); (b) the current day's bar is validated as provisional and dropped until finalized inspections pass; (c) Yahoo is a 15-minute-delayed aggregator — fine for this research use, not for live trading.
8. **No live/paper components:** no broker API, no real orders, no stakes.

---

## 10. Acceptance criteria (final)

- [ ] `pytest` fully green; `ruff` clean; single release commit.
- [ ] Clean pipeline runs end-to-end: CSV → validated frame → probability table → trades → portfolio equity → 5 charts + stat tables + REPORT.md, all in `output/`.
- [ ] Nightly refresh workflow in place: a live/dispatch run appends new trading days to `data/nifty50_history.csv` with `data_source` provenance, is idempotent on rerun, and exits 0 on total failure with a `warn`.
- [ ] Probability chart shows per-pair `p_up` with Wilson whiskers, 50% line, and `n` on every bar.
- [ ] Exit-reason breakdown + average P&L per reason generated.
- [ ] Equity curve (total + per pair) with max-DD annotation.
- [ ] Benchmark (no ladder) alongside the strategy so the ladder's contribution is explicit.
- [ ] OOS diagnostic printed even though the main line is full-sample.
- [ ] REPORT.md states every entry of §9 without burying it; README lets a stranger run the tool.

---

*Decision log (all confirmed by user 14-Aug-2026):* this plan introduces/changes the following vs the source docs — (a) fill-at-observed-close convention; (b) `min_pair_sample=5`; (c) Thursday expiry (contradicting the 7/6-day example); (d) rate as best-effort-fetch-with-fallback; (e) OOS diagnostics as a mandated sidebar rather than the main line; (f) Wilson CI + `n` annotation as chart contract per v2 §8. Each remains individually reversible via `config.py`.