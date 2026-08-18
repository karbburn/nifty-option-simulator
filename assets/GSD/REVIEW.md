---
phase: code-review
reviewed: 2026-08-18T00:00:00Z
depth: deep
files_reviewed: 28
files_reviewed_list:
  - nifty_gap/web/app.py
  - nifty_gap/web/state.py
  - nifty_gap/web/snapshot.py
  - nifty_gap/web/__main__.py
  - nifty_gap/web/make_favicon.py
  - nifty_gap/config.py
  - nifty_gap/data/loader.py
  - nifty_gap/data/refresh.py
  - nifty_gap/data/validation.py
  - nifty_gap/backtest/engine.py
  - nifty_gap/trade/ladder.py
  - nifty_gap/options/black_scholes.py
  - nifty_gap/options/calendar.py
  - nifty_gap/options/rate.py
  - nifty_gap/options/strikes.py
  - nifty_gap/reporting/metrics.py
  - nifty_gap/signals/probability_table.py
  - nifty_gap/visualization/charts.py
  - nifty_gap/__main__.py
  - pyproject.toml
  - render.yaml
  - Procfile
  - .gitignore
  - nifty_gap/web/templates/base.html
  - nifty_gap/web/templates/dashboard.html
  - nifty_gap/web/templates/expiry.html
  - nifty_gap/web/templates/expiry_content.html
  - nifty_gap/web/templates/trade.html
findings:
  critical: 4
  warning: 0
  info: 0
  total: 20
status: issues_found
---

# Code Review Report

**Reviewed:** 2026-08-18
**Depth:** deep
**Files Reviewed:** 28
**Status:** issues_found

> Severity classification used here: **CRITICAL** (boot failure / data loss / security), **HIGH** (functional bug), **MEDIUM** (quality/correctness), **LOW** (style/hygiene). Note: the classification in this report deliberately uses CRITICAL/HIGH/MEDIUM/LOW labels with full counts below.

## Summary

Deep review of the complete `nifty_gap` package, the web frontend, and the new Render deployment configuration. The wheel produced by `pip install .` was **built and inspected during this review** — it contains **only `.py` files** (no `web/templates/*.html`, no `web/static/*`, no `data/*.csv`, no `assets/*.csv`, no `output/*`). That, together with the module-level import-time `generate_snapshot()` fallback in `app.py`, is the root of the Render boot/500 problem.

The app currently boots on Render **by luck**: uvicorn's default `--app-dir "."` inserts the repo root ahead of site-packages in `sys.path`, so the source-tree copy (with templates/static/data present) shadows the broken wheel. Any mechanism that imports the installed package (gunicorn, `python -c`, different cwd, or a Render runtime change) crashes at import on the `/static` mount. Independently, if `output/dashboard.json` or the data CSV is missing/unreadable, the import-time block silently sets `snapshot = {}`, and **every page 500s** (`snap["last_trading_date"]` at `app.py:217`, `snap.git_sha` at `base.html:192`, etc.).

Security scan: no hardcoded secrets, no `eval`/`exec`, no `shell=True`, no unsafe deserialization. `refresh.py` uses constant hardcoded NSE/Yahoo URLs (no SSRF). `/trade/{entry_date}` uses the user input only in a list comprehension and template rendering (no filesystem access; no traversal). Jinja2 autoescape is active (Starlette default) and the JS-side DOM building uses `esc()` consistently; `snap | tojson` is used for the snapshot payload; CDN Chart.js is fine with a PNG fallback. The main security-adjacent gap is the **unvalidated `RecomputeRequest`** (H-01), which turns malformed numeric input into 500s.

Also good: matplotlib figures are closed in `_save` (`charts.py:24`) — no figure leak; `_equity_curve` zips columns from the same DataFrame (equal length); `apply_costs` brokerage is not double-counted (`daily_mtm` recomputes P&L from adjusted legs, and `_subtract_brokerage` subtracts fees once more only in the equity curve — matching `Trade.pnl`); `compute_live_positions` per-pair "latest entry" is consistent with the single-open-position-per-pair design.

**Finding counts:** CRITICAL 4 · HIGH 3 · MEDIUM 8 · LOW 5 (total 20)

---

## CRITICAL

### CR-01: Module-level `generate_snapshot()` at import plus silent empty-snapshot fallback → 500 on every page

**File:** `nifty_gap/web/app.py:31-39` (also `:45-47`, `:75-100`, `:117-118`, `:213-232`)

**Issue:** The import-time block runs a **full backtest + 5 matplotlib PNG renders** whenever `output/dashboard.json` is absent, then `json.loads` the file. On a fresh Render instance (especially the first deploy before `output/` was committed, or after matplotlib's first-run font-cache build) this can take 60s+ at import → Render marks the deploy failed. The working-tree `try/except Exception: snapshot = {}` turns any failure (missing CSV, invalid JSON, backtest exception) into a silent empty dict — then `dashboard()` does `snap["last_trading_date"]` → `KeyError` → **500 on `/`, `/expiry`, and `/trade/...`** (template `UndefinedError` for `snap.git_sha`), while `/api/dashboard` returns `{}`. The same silent-swallow pattern in `_seed_snapshot` (`app.py:99-100`, `except Exception: pass`) hides data/backtest failures with zero logging. Separately, `_fetch_spot()`'s fallback `load_history_df()` (`app.py:117-118`) raises uncaught `FileNotFoundError` → 500 on `/` when the data CSV is missing.

**Fix:**
```python
import logging
logger = logging.getLogger("nifty_gap.web")

def _load_snapshot() -> dict:
    """Build snapshot once, lazily, with logging — never at import time."""
    if SNAPSHOT_PATH.exists():
        try:
            return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("stored snapshot unreadable; regenerating")
    try:
        snap = generate_snapshot()
        logger.info("snapshot generated: %d trades", len(snap.get("trades", [])))
        return snap
    except Exception:
        logger.exception("snapshot generation failed (data missing?)")
        return {}
```
- Remove the import-time block; keep `snapshot: dict = {}` and call `_load_snapshot()` inside a `lifespan` handler (see M-01) or lazily on first request.
- Never serve an empty dict as "the dashboard": in `dashboard()`, `expiry()`, `trade_detail()`, if `not snapshot`: return a rendered 503 status page (`status_code=503`, clear "data not yet available" message). Keep `/health` returning `{"status": "ok"}` even when degraded so Render's health check passes.
- Guard `_fetch_spot()` fallback:
```python
if spot is None:
    try:
        df = load_history_df()
        spot = float(df["Close"].iloc[-1])
    except Exception:
        logger.warning("spot fallback failed", exc_info=True)
        return {"spot": None, "source": "unavailable", "as_of": ...}
```
and make `base.html:173` render `—` when `spot.spot is none`.

### CR-02: `pip install .` wheel ships only `.py` files — deployed app is missing templates, static, data, and output

**File:** `pyproject.toml:23-24` (no `[tool.setuptools.package-data]`, no `MANIFEST.in`)

**Issue:** Verified empirically: `python -m pip wheel . --no-deps` produces a wheel containing **only** `nifty_gap/**/*.py` + `dist-info`. Missing from the wheel: `web/templates/*.html`, `web/static/*` (favicon/PNGs), `data/nifty50_history.csv`, `assets/NIFTY 50-*.csv`, `output/dashboard.json`, `output/*.png`. When the import resolves to the installed copy (site-packages) instead of the repo checkout — which happens with **gunicorn**, `python -c "import nifty_gap.web.app"`, a changed working directory, or `PYTHONPATH` manipulation — the app hard-crashes at import: `app.mount("/static", StaticFiles(directory=STATIC_DIR))` (`app.py:46`) raises Starlette `RuntimeError: Directory '...' does not exist`; `PROJECT_ROOT` (`config.py:8`) resolves to site-packages so data/output/seed paths are all missing; `TEMPLATES_DIR` is gone → `TemplateNotFound` 500s on every route. This is the fragility underneath the current Render 500; it is only masked because uvicorn CLI inserts `--app-dir "."` (cwd) at `sys.path[0]`.

**Fix (do at least one, preferably both):**
```toml
[tool.setuptools.package-data]
"nifty_gap.web" = ["templates/*.html", "static/*"]
```
```yaml
# render.yaml — editable install keeps everything rooted at the repo checkout
buildCommand: pip install -e ".[web]"
```
If not using editable, also ship runtime data: `"nifty_gap" = []` + `MANIFEST.in` (`recursive-include nifty_gap/web/templates *.html`, `recursive-include nifty_gap/web/static *`), and pass data/output paths via env-selected roots rather than `PROJECT_ROOT`.

### CR-03: `.gitignore` state flip-flop — runtime-critical files can silently stop being tracked

**File:** `.gitignore` (HEAD and working tree still list `output/`, `assets/`, `data/nifty50_history.csv`; the staged index removes them)

**Issue:** The working tree has re-added the three ignore rules (8 lines) while the index removes them (5 lines), reported as `MM .gitignore`. Any `git add .`/`git commit -a` before the fix commits the wrong version. If the ignores come back, every future `/api/refresh` CSV rewrite, regenerated `dashboard.json`, and new `output/*.png` stays untracked → **every Render deploy serves stale data forever** (Render filesystem is ephemeral; the repo is the only persistence). Additionally `assets/icon.png` (4.5 MB, staged) contradicts `make_favicon.py:4-5` ("gitignored") and is only needed to regenerate favicons; `output/equity.csv`, `output/params.json`, `output/stats.json`, `output/trades.csv` (staged) are not needed at runtime.

**Fix:**
```bash
git add .gitignore            # the 5-line version (un-ignore output/, assets/, data/)
git rm --cached assets/icon.png
git rm --cached output/equity.csv output/params.json output/stats.json output/trades.csv
git commit -m "chore: un-ignore runtime data; drop non-runtime artifacts"
```

### CR-04: `render.yaml` and `Procfile` are untracked — the deployment config is not applied

**File:** `render.yaml`, `Procfile` (both `??` in `git status`)

**Issue:** Deploying the repo as-is gives Render no manifest. Without the committed `render.yaml`, the default Python buildpack runs `pip install -r requirements.txt` (which does not exist) and the default start command `gunicorn app:app` (module `app` does not exist) → guaranteed boot failure/500. The Blueprint config only exists once the files are committed.

**Fix:** commit both files with the CR-01/CR-02 fixes:
```bash
git add render.yaml Procfile
git commit -m "deploy: add Render blueprint and Procfile"
```

---

## HIGH

### H-01: `RecomputeRequest` has no bounds or length validation → user-triggerable 500s

**File:** `nifty_gap/web/app.py:54-62`, `:161-185`; `nifty_gap/web/templates/dashboard.html:45-61`

**Issue:** The API accepts arbitrary values:
- `iv_flat: -1` → `black_scholes` raises `ValueError` (`options/black_scholes.py:13-14`) → uncaught → 500.
- `ladder_stop_pcts: [0.01]` (length 1) → snapshot regenerated with a 1-element config → `dashboard.html:49` reads `ladder_stop_pcts[1]` → Jinja `IndexError` → 500 on the whole dashboard. Same for `ladder_floor_pcts` needing exactly 3 (`dashboard.html:53-61`) and the JS `updateConfigUI` (`dashboard.html:442-446`).
- `slippage_pct: -0.5`, negative brokerage, `spot <= 0` on `/api/live-positions` (`app.py:206-210` → `black_scholes` ValueError → 500).

**Fix:** validate in the model and translate domain errors to HTTP 4xx:
```python
from pydantic import BaseModel, Field, field_validator

class RecomputeRequest(BaseModel):
    seq: int | None = Field(default=None, ge=0)
    iv_flat: float | None = Field(default=None, gt=0, le=1)
    ladder_stop_pcts: list[float] | None = None
    ladder_floor_pcts: list[float] | None = None

    @field_validator("ladder_stop_pcts")
    @classmethod
    def _two_stops(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("ladder_stop_pcts must have exactly 2 entries")
        return v

    @field_validator("ladder_floor_pcts")
    @classmethod
    def _three_floors(cls, v):
        if v is not None and len(v) != 3:
            raise ValueError("ladder_floor_pcts must have exactly 3 entries")
        return v
```
and wrap the `build_snapshot_and_charts` call in `try/except (ValueError, KeyError) -> HTTPException(400)`.

### H-02: Race conditions on the global `snapshot` / `_recompute_seq`

**File:** `nifty_gap/web/app.py:67`, `:161-185`; readers at `:156-158`, `:205-210`, `:213-232`

**Issue:** FastAPI runs these sync endpoints in a threadpool. A recompute with an older `seq` that *started* earlier can *finish* later and overwrite the newer result — the staleness check happens only at entry, not before assignment. Concurrent readers (`/api/dashboard`, `/api/live-positions`, `/`) can observe a torn dict during `snapshot = build_snapshot_and_charts(...)` reassignment → `KeyError` → 500. `_seed_snapshot` combined with first requests has the same exposure.

**Fix:** assign through a lock and re-check seq after the long build:
```python
import threading
_snapshot_lock = threading.Lock()
_recompute_seq = 0

def api_recompute(body: RecomputeRequest) -> dict:
    if body.seq is not None and body.seq < _recompute_seq:
        return snapshot
    cfg = replace(cfg, **kwargs)
    new_snap = build_snapshot_and_charts(cfg, body.brokerage_per_trade, body.slippage_pct)
    with _snapshot_lock:
        if body.seq is not None and body.seq < _recompute_seq:
            return snapshot          # stale result — drop it
        global snapshot
        snapshot = new_snap
        _recompute_seq = body.seq if body.seq is not None else _recompute_seq
    return new_snap
```
Readers either hold the lock (cheap) or read the reference once into a local before indexing.

### H-03: `_seed_snapshot` swallows every exception and runs heavy work before the first request

**File:** `nifty_gap/web/app.py:75-100`

**Issue:** The startup handler wraps everything in `except Exception: pass` — if `seed_history`, `generate_snapshot()`, or `render_report_pngs()` fails (bad CSV, transient backtest error), the app starts with `snapshot = {}` and zero log output; diagnosis is impossible from Render logs. Because startup handlers run before the server accepts connections, the full backtest + PNG render path on a fresh deploy delays readiness and can trip Render's deploy-liveness timeout.

**Fix:** convert to `lifespan` (M-01), log via `logger.exception(...)` instead of `pass`, and keep the heavy generate/render inside the same catch-all only for *best-effort refresh of already-present data* — never as the only way to get a snapshot. If generation fails, serve the degraded 503 page from CR-01.

---

## MEDIUM

### M-01: `@app.on_event("startup")` is deprecated

**File:** `nifty_gap/web/app.py:75`

**Issue:** Deprecated in FastAPI (will be removed); not the current failure, but the startup logic should move to a lifespan context so ordering with lazy snapshot loading is explicit.

**Fix:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # seed data, load/generate snapshot, log failures
    yield
    # teardown

app = FastAPI(title="NIFTY Gap Dashboard", lifespan=lifespan)
```

### M-02: `_clean` converts NaN to None but not `inf` → invalid strict JSON

**File:** `nifty_gap/web/snapshot.py:27-28`; `nifty_gap/reporting/metrics.py:33-38`

**Issue:** `trade_stats.profit_factor` can be `math.inf` (gross_loss == 0 with wins). `json.dumps(snapshot, indent=2)` then writes literal `Infinity` into `dashboard.json` — invalid strict JSON. Python's `json.loads` and the browser tolerate it today, but any strict consumer (or a future `response.json()` on `/api/dashboard`) breaks. `math.isnan` also misses `np.inf` inside nested lists.

**Fix:** `if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)): return None`. Optionally force `allow_nan=False` in `generate_snapshot` (`snapshot.py:141`) so future non-finite values fail loudly instead of silently shipping bad JSON.

### M-03: `/api/refresh` — slow, unlocked, and non-persistent on Render

**File:** `nifty_gap/web/app.py:188-197`; `nifty_gap/data/refresh.py:89-127`, `:139-194`

**Issue:** A refresh can take 20-40s (NSE 20s timeout + `time.sleep(2.0)` + yfinance fallback). There is no lock, so two concurrent clicks double-fetch and double-write. On Render the write to `data/nifty50_history.csv` lands on **ephemeral disk** and is lost when the instance is recycled — the dashboard silently reverts to the committed (stale) CSV. NSE also rate-limits aggressively from cloud IPs; `fetch_nse` returning `None` causes the whole refresh to fail rather than falling back immediately to yfinance when the `reports_url` returns non-200.

**Fix:** add a module-level `threading.Lock` in `api_refresh`; treat `fetch_nse()` returning `None` as "provider failed" and continue to yfinance (it already does via `continue`); document/accept ephemerality or persist the history to external storage (e.g., a Render disk volume or an object store). Consider a `last-refresh` timestamp guard so repeated clicks are no-ops.

### M-04: `seed_history` can return an empty DataFrame → crash in `run_refresh`

**File:** `nifty_gap/data/loader.py:75-84`; `nifty_gap/data/refresh.py:164`

**Issue:** If `data/nifty50_history.csv` exists but is empty, `load_history()` returns a header-only DataFrame, `seed_history` returns it, and `run_refresh`'s `latest = history["Date"].max().date()` raises `AttributeError` on `NaT` → 500 from `/api/refresh`.

**Fix:**
```python
history = load_history(history_path)
if history is not None and not history.empty:
    return history
```

### M-05: `/api/live-positions?spot=0` → `black_scholes` ValueError → 500

**File:** `nifty_gap/web/app.py:205-210`; `nifty_gap/options/black_scholes.py:13-14`

**Issue:** A caller-supplied `spot` of 0 or negative reaches `black_scholes` and raises. The dashboard never sends it, but the endpoint is public.

**Fix:** `if not spot or spot <= 0: raise HTTPException(status_code=400, detail="spot must be positive")` and wrap the per-trade `black_scholes` call (or let `compute_live_positions` skip invalid trades).

### M-06: `provenance()` spawns `git rev-parse HEAD` twice per snapshot build

**File:** `nifty_gap/reporting/metrics.py:124-137`; called at `nifty_gap/web/snapshot.py:79` and `:81`

**Issue:** Each recompute (`/api/recompute`) spawns two subprocesses just to label the snapshot. On Render the checkout has `.git`, so it works, but it is wasted work per recompute and fails silently to "unknown" when installed from a wheel (no `.git`).

**Fix:** cache the sha once at import/startup:
```python
_GIT_SHA = None
def _git_sha() -> str:
    global _GIT_SHA
    if _GIT_SHA is None:
        ...  # subprocess once
    return _GIT_SHA
```

### M-07: render.yaml has no `healthCheckPath` — Render health-checks the heavy `/` route

**File:** `render.yaml:1-9`

**Issue:** Render's default health check issues GET `/` (the full dashboard route, including a live yfinance spot fetch). During the degraded/empty-snapshot state this returns 500 → the deploy is marked failed instead of the lightweight `/health` endpoint reporting state.

**Fix:**
```yaml
    healthCheckPath: /health
```

### M-08: OOS table renders "nan%" for pairs without out-of-sample data

**File:** `nifty_gap/web/templates/expiry_content.html:28-29`; `nifty_gap/reporting/metrics.py:106-121`

**Issue:** `float("nan")` is truthy, so `(d.realized_p_up or 0)` evaluates to `nan` → the template renders `nan%` (and the red `pnl-negative` class) for pairs with `n_oos == 0`.

**Fix:** emit `None` in `oos_summary` when not finite (`realized_ci_low=None`, etc.) and render `—` when `d.realized_p_up is none`:
```html
<td>{{ "{:.1f}".format((d.realized_p_up or 0) * 100) if d.realized_p_up is not none else "—" }}%</td>
```

---

## LOW

### L-01: `import yfinance as yf` at module level in app.py

**File:** `nifty_gap/web/app.py:9`

**Issue:** yfinance is only used by `_fetch_spot` (line 110). Importing it at module import adds ~1-2s and pulls its whole dependency chain into the boot path for no benefit. `refresh.py:66` already does the lazy-import pattern.

**Fix:** move `import yfinance as yf` inside `_fetch_spot`.

### L-02: Redundant duplicate imports

**File:** `nifty_gap/web/app.py:78` (`import json` inside `_seed_snapshot`), `:82` and `:171` (`from nifty_gap.config import Config`)

**Issue:** All already imported at module level (lines 3, 19). Noise; `json` at `:78` shadows nothing but is dead weight.

**Fix:** delete the inner imports.

### L-03: Dead code

**File:** `nifty_gap/backtest/engine.py:222-227` (`export_results`), `:230-241` (`ladder_log_gate`); `nifty_gap/reporting/metrics.py:91-103` (`pair_stats`); `nifty_gap/options/calendar.py:34-39` (`days_to_expiry`, `years_to_expiry` — only re-exported in `options/__init__.py`); `nifty_gap/data/validation.py:60-83` (`validate_holidays`, `data_profile` — exported but never called outside tests)

**Issue:** Six public functions are never called by app code. They are small and tested; either delete them or keep them only under `tests/` usage, but they currently read as dead weight.

**Fix:** remove `export_results`, `ladder_log_gate`, `pair_stats`; keep or document the others.

### L-04: Unquoted `.[web]` in render.yaml buildCommand

**File:** `render.yaml:5`

**Issue:** `pip install .[web]` is passed to a shell; `.[web]` is a glob pattern (matches `.w`, `.e`, `.b`). It happens to pass through because no such files exist, but a stray dotfile would silently corrupt the install.

**Fix:** `buildCommand: pip install ".[web]"` (also matches the CR-02 editable recommendation: `pip install -e ".[web]"`).

### L-05: Procfile duplicates render.yaml startCommand

**File:** `Procfile:1`; `render.yaml:6`

**Issue:** For a Blueprint deploy, `startCommand` in render.yaml wins; the Procfile is dead weight for this deployment path. It is harmless if kept (useful for `render deploy` single-service flows) but the two must never drift.

**Fix:** keep both in sync or drop the Procfile; either way, document which one is authoritative.

---

## Investigated-and-clean (for the record)

- **Path traversal (`/trade/{entry_date}`)** — `app.py:235-244`: `entry_date` is compared to `t["entry_date"]` strings only; never used in filesystem/URL operations. Clean.
- **SSRF (`refresh.py`)** — NSE/Yahoo URLs are compile-time constants; only date params vary. Clean.
- **`eval`/`exec`/`shell=True`/unsafe deserialization** — grep across `nifty_gap/` found none.
- **XSS/template injection** — Jinja2 autoescape on (Starlette default); JS DOM building escapes via `esc()` (`dashboard.html:230-234`); `snap | tojson` used for payload embedding; PNG fallback if Chart.js CDN is unreachable (`dashboard.html:589-591`). Clean (only LOW note: CDN scripts without SRI, `base.html:11-13`).
- **`_equity_curve` zip** (`snapshot.py:58-62`) — zips `equity_curve`/`benchmark_equity` columns from the same DataFrames produced by `daily_mtm`; lengths always equal. Clean.
- **Division by zero** (`state.py:170`) — `pct_move` guarded by `if t.entry_premium`; since `_clean_float` maps missing entries to `0.0`, the guard holds. (NaN would be truthy — prefer `> 0` anyway.)
- **Matplotlib figure leaks** (`charts.py:19-24`) — every chart path ends in `_save()` → `plt.close(fig)`. Clean.
- **Brokerage double-count** (`state.py:37-90`) — verified `daily_mtm` recomputes from adjusted legs and `_subtract_brokerage` subtracts fees once in the equity curve; consistent with `Trade.pnl`. Clean.
- **`compute_live_positions` per-pair keying** (`state.py:149-155`) — keeps most-recent open trade per pair; consistent with the one-position-per-pair dashboard design. Worth a code comment; not a bug.
- **yfinance import safety** — `import yfinance` performs no network I/O; the network risk is only the lazy `fast_info` call, which is already wrapped in try/except with a `load_history_df` fallback (`app.py:109-118`).

---

_Reviewed: 2026-08-18_
_Reviewer: gsd-code-reviewer (deep)_
_Depth: deep_