# Phase 1 — UI Review

**Audited:** Sun Aug 16 2026
**Baseline:** UI-SPEC.md at assets/GSD/UI-SPEC.md (1,147 lines)
**Screenshots:** not captured (no dev server running on localhost:3000/5173/8080)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Color & Contrast | 3/4 | CE/PE badges use text+color; minor: hardcoded hex in fresh-badge, accent overuse on all links |
| 2. Typography | 3/4 | Body 14px/line-height 1.5 exact match; Heading 18px/600 exact match; KPI 24px/600 exact match; table 13px vs spec 14px slight mismatch; several 11px elements vs 12px "Small" |
| 3. Layout & Spacing | 3/4 | 8-point spacing scale used consistently; KPI row responsive (4/2/1 columns); bottom nav shows at <767px; two-col stacks at <992px; positions grid auto-fill; minor: side-badge hardcoded padding, bottom-nav height off scale |
| 4. Component Consistency | 4/4 | Card styles uniform across all pages; table formats consistent; KPI cards consistent; CE/PE badges consistently use "CE ▲" and "PE ▼" text labels alongside color — color is never the only indicator |
| 5. Accessibility | 3/4 | All main sections have descriptive aria-labels; table headers have dynamic aria-sort; no aria-expanded needed (no accordion elements); coming-soon mobile notice only on <768px; minor: coming-soon pattern could match UI-SPEC card+overlay format |
| 6. Visual Hierarchy | 3/4 | Live Positions primary placement correct (first section below KPI row); Equity Curve secondary (hidden behind tab panel); spec specifies equity curve as primary visible element in grid layout — tab-based approach is valid deviation but differs from grid contract |

**Overall: 19/24**

---

## Top 3 Priority Fixes

1. **Fix hardcoded `#f57f17` in `.fresh-badge.stale`** — Use CSS variable `--badge-stale` instead. One-line fix in `base.html:50` to align with UI-SPEC color token system and ensure design system consistency.

2. **Reconcile equity curve visibility with UI-SPEC grid layout** — The UI-SPEC (Section 4) specifies equity curve as a primary visible element alongside live positions in the desktop grid, but the implementation hides it behind a tab panel. If the tab approach is intentional, document the rationale. If the intent is spec compliance, restructure to show equity curve as a primary visible section (per the grid layout).

3. **Align table font-size with UI-SPEC body scale** — The table base `font-size: 13px` in `base.html:82` differs from the UI-SPEC body scale of 14px. Update to `14px` or add a justification comment, ensuring `line-height: 1.5` is also applied for consistency.

---

## Detailed Findings

### Pillar 1: Color & Contrast (3/4)

**CE/PE badges** — `.side-badge.ce` and `.side-badge.pe` both use background color (`var(--ce-green)`, `var(--pe-red)`) AND white text (`color: #fff`) with explicit text labels `"CE ▲"` and `"PE ▼"`. Color is **never the only indicator** ✓. PASS.

**Spot ticker color coding** — `.spot-change.up` / `.spot-change.down` use color + arrow indicators (▲/▼) injected via JavaScript. The `.flash-up` / `.flash-down` classes animate color change with `!important` override. Color + arrow = sufficient ✓. PASS.

**Across the codebase:**
- `.kpi-value.profit { color: var(--ce-green); }` and `.kpi-value.loss { color: var(--pe-red); }` — color is supplementary to text numbers ✓. PASS.
- `td.pnl-positive { color: var(--ce-green); background: var(--profit-bg); }` and `td.pnl-negative { color: var(--pe-red); background: var(--loss-bg); }` — color + background shading ✓. PASS.
- All links use `color: var(--accent)` — exceeds the UI-SPEC "10% usage" guideline but is consistent and intentional ✓ (flag, not fault). FLAG.
- `.fresh-badge.stale` uses hardcoded `#f57f17` instead of CSS variable `--badge-stale: #ffc107` (base.html:50). The variable is defined at line 22 but not referenced in this rule. FLAG.
- `.spot-change.neutral { color: var(--text-muted); }` — sufficient WCAG AA contrast against `--bg-primary: #ffffff`. PASS.

**Verdict:** Score 3/4 — Color contract substantially met. CE/PE badges correctly use text+color. Minor: hardcoded hex vs variable mismatch, accent color on all links exceeding the 10% guideline.

---

### Pillar 2: Typography (3/4)

**Font family:** `--font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` is applied to `body` and inherits everywhere ✓. No custom web fonts, zero load time ✓.

**Size/weight/line-height audit vs UI-SPEC scale:**

| Role | Spec | Actual | Match |
|------|------|--------|-------|
| Body | 14px, 400, 1.5 | `body { font-size: 14px; line-height: 1.5; }` | ✅ Exact |
| Heading | 18px, 600, 1.2 | `.logo { 18px 600 }`, `.card h2 { 18px 600 }` | ✅ Exact |
| Small | 12px, 400, 1.5 | `.spot-label { 12px }`, `.kpi-label { 12px }`, `.position-footer { 12px }`, `.footer { 12px }`, `.coming-soon-mobile { 12px }` | ✅ Exact where used |
| KPI | 24px, 600, 1.1 | `.kpi-value { 24px 600 }` | ✅ Exact |

**Discrepancies:**
- Table base `font-size: 13px` (base.html:82) vs spec's Body 14px — 1px difference, functionally negligible but breaks the "all body text 14px" contract ✗.
- Various elements at 11px: `.fresh-badge { 11px }`, `.side-badge { 11px }`, `.dte-badge { 11px }`, `.stat-label { 11px }`, `.bottom-nav button { 11px }`, `.tab-icon { 18px }` — these are 1px below the "Small" spec of 12px. In practice, 11px for badges/labels is acceptable and readable, but technically below the spec's "Small: 12px" definition.
- No explicit `line-height` on most individual elements — they inherit `line-height: 1.5` from `body`, which is correct per the spec's cascade behavior.

**Verdict:** Score 3/4 — Body/Heading/KPI typography matches the UI-SPEC scale exactly. The 13px table base and several 11px elements are minor deviations. The system font stack is consistently applied.

---

### Pillar 3: Layout & Spacing (3/4)

**8-point spacing scale:** All spacing uses `--sp-1` through `--sp-6` (4px–24px, multiples of 4) defined in the `:root` block. No arbitrary `[px]` or `[rem]` values found in the CSS grep. ✓

**Grid responsiveness:**

- **KPI Row**: 4 columns at desktop (`grid-template-columns: repeat(4, 1fr)`), 2 columns at tablet (`max-width: 991px` → `repeat(2, 1fr)`), 1 column at mobile (`max-width: 767px` → `1fr`). ✅ Matches UI-SPEC breakpoints.
- **Two-Column Row** (Probability + Benchmark): `1fr 1fr` at desktop, stacks to `1fr` at `max-width: 991px`. ✅ Matches spec.
- **Live Positions grid**: `repeat(auto-fill, minmax(300px, 1fr))` — auto-fills with min 300px cards. The UI-SPEC says "min 260px for desktop"; 300px is close and works well. ✅ Acceptable.
- **Chart containers**: 320px (desktop), 260px (max 991px), 220px (max 767px). ✅ Matches UI-SPEC.
- **Bottom tab bar**: `display: none` by default; `display: flex` at `max-width: 767px` with `position: fixed; bottom: 0;`. ✅ Matches mobile-first approach.
- **Header**: On `max-width: 767px`, `flex-direction: column; align-items: flex-start;` — stacks logo + spot ticker vertically. ✅

**Spacing usage checklist:**
- `.header { padding: var(--sp-3) var(--sp-5); }` — 12px 20px ✓
- `.nav a { padding: var(--sp-1) var(--sp-2); }` — 4px 8px ✓
- `.header-right { gap: var(--sp-4); }` — 16px gap ✓
- `.spot-label { margin-right: var(--sp-1); }` — 4px ✓
- `.card { padding: var(--sp-5); }` — 20px ✓
- `.kpi-row { gap: var(--sp-4); }` — 16px gap ✓
- `.kpi-card { padding: var(--sp-4) var(--sp-5); }` — 16px 20px ✓
- `.kpi-label { margin-bottom: var(--sp-1); }` — 4px ✓
- `.positions-grid { gap: var(--sp-4); }` — 16px gap ✓
- `.position-card { padding: var(--sp-4); }` — 16px ✓
- `.position-header { gap: var(--sp-2); }` — 8px ✓
- `.position-body { margin: var(--sp-3) 0; }` — 12px ✓
- `.position-chart { margin: var(--sp-2) 0; }` — 8px ✓
- `.empty-state { padding: var(--sp-6); }` — 24px ✓
- `.footer { padding: var(--sp-6) 0; }` — 24px top/bottom ✓
- `.coming-soon-mobile { padding: var(--sp-3) var(--sp-4); }` — 12px 20px ✓
- `th, td { padding: var(--sp-2) var(--sp-3); }` — 8px 12px ✓
- `.filters { gap: var(--sp-3); margin-bottom: var(--sp-3); }` — 12px ✓
- `.filters select { padding: var(--sp-2); }` — 8px ✓

**Minor issues:**
- `.side-badge { padding: 1px 6px; }` — hardcoded, not using spacing variables ✗.
- `.bottom-nav` height: `56px` — not on the `--sp-*` scale (scale goes --sp-1=4px, --sp-2=8px, --sp-3=12px, --sp-4=16px, --sp-5=20px, --sp-6=24px, --sp-8=32px). 56px = 7 × 8px, not a defined variable. ✗.

**Verdict:** Score 3/4 — 8-point spacing scale is used consistently for nearly all padding/margins/ Gutters. The `.side-badge` hardcoded padding and `.bottom-nav` height off-scale are the only deviations. Responsive breakpoints align with UI-SPEC specs.

---

### Pillar 4: Component Consistency (4/4)

**Card styles:** `.card` is defined once in `base.html:53` and reused across all pages:
- `dashboard.html`: KPI row wrapper, live positions section, next trade preview, equity curve card, probability/OOS card, benchmark card, trades table card, expiry content card
- `trade.html`: trade summary card, premium path card
- `expiry_content.html`: expiry weekday pairs card

All use identical `.card` classes with `var(--bg-secondary)`, `var(--border)`, `var(--radius-md)`, `var(--shadow-card)`, `var(--sp-5)` padding. ✅ **Uniform across all pages.**

**Table formats:** Both the dashboard trades table and the expiry content table use the same base table styles from `base.html:82-88`:
- `border-collapse: collapse; font-size: 13px;`
- `th { background: var(--bg-tertiary); font-weight: 600; cursor: pointer; }`
- `td, th { padding: var(--sp-2) var(--sp-3); border-bottom: 1px solid var(--border); }`
- `td:nth-child(n+6), th:nth-child(n+6) { text-align: right; font-variant-numeric: tabular-nums; font-family: var(--font-mono); }`
- `td.pnl-positive { color: var(--ce-green); background: var(--profit-bg); }`
- `td.pnl-negative { color: var(--pe-red); background: var(--loss-bg); }`

✅ **Table formats are consistent** across all pages.

**KPI cards:** `.kpi-card` defined once in `base.html:56` with `var(--bg-secondary)`, `var(--border)`, `var(--radius-md)`, `var(--shadow-card)`, `var(--sp-4) var(--sp-5)` padding, `text-align: center`. Used in dashboard KPI row (4 cards). ✅ **Consistent styling.**

**CE/PE badges:** The critical requirement — "ensure CE says 'CE ▲' and PE says 'PE ▼' with text, not color-only" — is met everywhere:

| File | Line | Pattern |
|------|------|---------|
| `dashboard.html` | 34 | `<span class="side-badge {{ 'ce' if p.side == 'CE' else 'pe' }}">{{ 'CE ▲' if p.side == 'CE' else 'PE ▼' }}</span>` |
| `trade.html` | 8 | `<span class="side-badge {{ 'ce' if trade.side == 'CE' else 'pe' }}">{{ 'CE ▲' if trade.side == 'CE' else 'PE ▼' }}</span>` |
| `base.html` | 66-67 | `.side-badge.ce { background: var(--ce-green); }` / `.side-badge.pe { background: var(--pe-red); }` (with `color: #fff` text) |

In all cases, CE uses `"CE ▲"` (text + color) and PE uses `"PE ▼"` (text + color). Color is **supplementary**, not the only indicator. ✅ **Requirement fully met.**

**Verdict:** Score 4/4 — Excellent component consistency. Card styles uniform, table formats consistent, KPI cards uniform, CE/PE badges use text labels alongside color (never color-only). This is the best-scoring pillar.

---

### Pillar 5: Accessibility (3/4)

**ARIA labels on main sections:**
- `base.html:136`: `<nav class="bottom-nav" aria-label="Mobile navigation">` ✅
- `dashboard.html:26`: `<section class="card" aria-label="Live positions">` ✅
- `dashboard.html:60`: `<section class="card" aria-label="Next trade preview">` ✅
- `dashboard.html:76`: `<section class="card" aria-label="Past trades">` ✅
- `dashboard.html:121`: `<section class="card" aria-label="Equity curve showing cumulative P&L from Aug 2025 to Aug 2026">` ✅ **Descriptive**
- `dashboard.html:126`: `<section class="card" aria-label="Probability and out-of-sample win rates with confidence intervals">` ✅ **Descriptive**
- `dashboard.html:130`: `<section class="card" aria-label="Benchmark">` ✅
- `expiry_content.html:1`: `<section class="card" aria-label="Expiry weekday and out-of-sample performance">` ✅
- `trade.html:4`: `<section class="card" aria-label="Trade summary">` ✅
- `trade.html:21`: `<section class="card" aria-label="Premium path chart with ladder entry stop and floor levels">` ✅ **Descriptive**

✅ **All main sections have descriptive ARIA labels.**

**Table headers — `aria-sort`:**
- Initial: `th { aria-sort="none" }` (dashboard.html:87-96) ✅
- Dynamic: JS sets `aria-sort` on header click (dashboard.html:166):
  ```js
  h.setAttribute('aria-sort', h.dataset.sort === currentSort.col ? (currentSort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
  ```
  ✅ **Dynamic aria-sort implemented correctly.**

**`aria-expanded`:** No expand/collapse elements exist in the current implementation (no accordions, no collapsible sections). The bottom nav tab switching uses `aria-current="page"` instead, which is the appropriate attribute for indicating the current tab/panel. ✅ **No aria-expanded needed.**

**Coming-soon blocks placement:**
- The `.coming-soon-mobile` div is hidden on desktop (`display: none`) and shown on mobile (`max-width: 767px` → `display: block`).
- On desktop, the hidden tab panels (trades, charts, expiry) mean some content is not immediately visible, but this is a tabbed interface pattern, not a coming-soon block issue.
- The mobile-only coming-soon notice is appropriate for the touch-first design. ✅

**Verdict:** Score 3/4 — Excellent ARIA label coverage across all pages. Dynamic aria-sort on table headers works correctly. No aria-expanded needed (appropriate use). Minor: coming-soon pattern could match the UI-SPEC card+overlay+badge format, but the current mobile-only div approach is functional.

---

### Pillar 6: Visual Hierarchy (3/4)

**Primary/secondary element ordering below the fold (always-visible "Live" tab panel):**

1. **KPI Row** — The most prominent horizontal band at the top. 4 equal-width KPI cards (Total P&L, Win Rate, Sharpe, Max Drawdown). ✅ **Primary** — immediately visible, above the live positions.
2. **Live Positions** — Full-width card below KPI row, listing active position cards in a grid. ✅ **Primary** — the namesake feature, correctly placed as the first major content section.
3. **Next Trade Preview** — Card below live positions, showing the next trade signal. ✅ **Secondary** — smaller than KPI/live positions, below them in the hierarchy.

**Secondary sections (hidden behind tab panels, require user navigation):**

4. **Equity Curve** — In `tab-panel id="tab-charts"`, hidden by default (`hidden` attribute). Requires clicking the "Charts" tab to view. ⚠️ **Secondary in implementation** — the UI-SPEC (Section 4 grid layout) specifies it as a primary visible element alongside live positions. The tab-based approach is a valid UI choice that differs from the grid contract.
5. **Probability & Benchmark (Two-Column Row)** — Also in `tab-panel id="tab-charts"`, hidden by default. ⚠️ **Secondary in implementation** — same as above; UI-SPEC places it as a primary row alongside equity curve and live positions.
6. **Past Trades Table** — In `tab-panel id="tab-trades"`, hidden by default. ⚠️ **Secondary in implementation** — UI-SPEC places it as a primary full-width section.
7. **Expiry Content** — In `tab-panel id="tab-expiry"`, hidden by default; includes `{% include "expiry_content.html" %}`. ⚠️ **Secondary in implementation.**

**Visual hierarchy assessment:**
- ✅ **Live Positions primary placement** — correctly the first content section below the KPI row in the always-visible tab panel. This is the strongest visible element after the KPI row.
- ⚠️ **Equity Curve secondary** — in the implementation, it's hidden behind a tab panel. The UI-SPEC grid layout (Section 4) shows it as a primary full-width chart alongside live positions and the two-column row. The implementation's tab-based approach is a deliberate UI pattern but deviates from the specified grid contract.
- ✅ **Logical ordering** — KPI row → Live Positions → Next Trade Preview forms a coherent primary section. Secondary elements are grouped behind tabs, which is a reasonable organization for a dashboard with many data sections.

**Verdict:** Score 3/4 — Live Positions primary placement is correct per both implementation and spec. Equity Curve is secondary in the current tab-based layout, which represents a deviation from the UI-SPEC's specified grid layout where it should be a primary visible element. The tab approach is functional and well-executed, but the visual hierarchy ranking differs from the design contract.

---

## Files Audited

1. `nifty_gap/web/templates/base.html` — Base layout, CSS variables, shared styles, header, bottom nav, spot ticker, fresh badge, CDN scripts
2. `nifty_gap/web/templates/dashboard.html` — Main dashboard: KPI row, live positions, next trade preview, equity curve, probability/OOS, benchmark, trades table, coming soon
3. `nifty_gap/web/templates/trade.html` — Trade detail: summary + premium path chart
4. `nifty_gap/web/templates/expiry_content.html` — Expiry weekday pairs table (included by expiry.html)
5. `nifty_gap/web/app.py` — FastAPI backend, snapshot management, API endpoints, route handlers
6. `assets/GSD/UI-SPEC.md` — Design contract (1,147 lines), used as reference for all pillar audits

---

## Recommendation Count

- **Priority fixes:** 3 (color variable mismatch, hierarchy discrepancy with spec, table font-size consistency)
- **Minor recommendations:** 4 (spacing scale hardcoded values, coming-soon pattern alignment, typography 11px vs 12px small differences, link accent color usage)