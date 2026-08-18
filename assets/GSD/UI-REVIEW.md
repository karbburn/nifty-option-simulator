# UI Review — NIFTY Option Simulator Dashboard

**Reviewed:** 2026-08-15
**Source:** `assets/GSD/PLAN.md`

---

## Dimension Verdicts

### 1. Information Density — PASS
The dashboard packs 6 sections into one page. For a single-user power-user tool analyzing backtest results, density is expected. No need for collapsible sections or tabs — user wants everything visible at once. The "Coming soon" placeholders are noted as temporary and acceptable in v1.

### 2. Visual Hierarchy — FLAG
The plan lists sections in order (Live Positions → Past Trades → Equity Curve → etc.) but never declares what the user should look at first. Live Positions appears most dynamic (real-time spot updates), but the Equity Curve likely matters most for overall performance understanding. Without an explicit focal point, the executor will guess visual priority.

**Recommendation:** Declare that Live Positions is the primary visual anchor (it's the only real-time element). Equity Curve is secondary. Everything else is tertiary.

### 3. Data-Ink Ratio — FLAG
- **Mini Chart.js line charts** for 5-10 data points in Live Positions are overkill. Chart.js adds ~200KB of JS overhead for what could be a simple HTML/CSS sparkline or just text.
- **"Coming soon" placeholders** are pure dead weight. If they don't function, don't render them.

**Recommendation:** Replace mini Chart.js charts with inline SVG sparklines or plain text. Remove "Coming soon" elements until they work.

### 4. Responsiveness — FLAG
The plan mentions "Charts resize" but provides no:
- Explicit responsive breakpoints
- Mobile-first layout strategy
- How the card grid (Live Positions) adapts to narrow screens
- Whether tables get horizontal scroll on mobile

Chart.js is responsive by default, but the surrounding layout needs explicit handling. A card grid with 3+ columns will break on mobile without media queries.

**Recommendation:** Add a note: "Use CSS Grid with `auto-fit` and `minmax(300px, 1fr)` for card layout. Tables get `overflow-x: auto` wrapper."

### 5. Accessibility — BLOCK
- **CE/PE badges use green/red color encoding** — classic colorblind issue (deuteranopia affects ~8% of males). Color alone cannot distinguish CE from PE.
- **No alt text** mentioned for any charts.
- **No ARIA labels** for interactive elements (sort headers, filter dropdowns).
- **No keyboard navigation** plan for table sorting.

**Fix required:** Add text labels to CE/PE badges (e.g., "CE ▲" / "PE ▼" or "CE (Call)" / "PE (Put)"). Document that charts need descriptive `<figcaption>` or `aria-label`. Sort headers need `aria-sort` attribute.

### 6. Consistency — FLAG
- **Number format:** API returns raw floats (e.g., `112.50`). Display format not specified — should it be `₹112.50` or `₹112.50`? Indian grouping (`₹1,12,500`) vs Western (`₹112,500`)?
- **Date format:** API returns ISO (`2026-08-15`). Display format not specified — should it be `Aug 15` or `15 Aug` or `2026-08-15`?
- **P&L format:** Should losses show `-₹4,865` or `₹-4,865` or `(₹4,865)`?

**Recommendation:** Add a "Formatting Conventions" section to the plan:
- Currency: `₹{value:,.2f}` (Indian grouping, 2 decimals)
- Dates: `{month} {day}` (e.g., "Aug 15") for trade dates, full ISO for timestamps
- P&L: Sign before currency symbol for negatives (`-₹4,865.34`)

---

## Blocking Issues

| # | Dimension | Issue | Severity | Fix |
|---|-----------|-------|----------|-----|
| 1 | Accessibility | CE/PE badges use color-only encoding (green/red) | BLOCK | Add text labels: "CE ▲" / "PE ▼" or include "(Call)"/"(Put)" |
| 2 | Accessibility | No alt text or ARIA labels for charts | BLOCK | Add `aria-label` to chart containers, descriptive `<figcaption>` |
| 3 | Accessibility | Sort headers lack `aria-sort` attribute | BLOCK | Add `aria-sort="ascending"` / `"descending"` / `"none"` |

---

## Non-Blocking Recommendations

| # | Dimension | Issue | Severity | Recommendation |
|---|-----------|-------|----------|----------------|
| 1 | Visual Hierarchy | No focal point declared | FLAG | Declare Live Positions as primary visual anchor |
| 2 | Data-Ink Ratio | Mini Chart.js for 5-10 data points | FLAG | Use inline SVG sparklines or text instead |
| 3 | Data-Ink Ratio | "Coming soon" placeholders | FLAG | Remove until functional |
| 4 | Responsiveness | No responsive layout strategy | FLAG | Document CSS Grid `auto-fit` approach |
| 5 | Consistency | Number/date format undefined | FLAG | Add formatting conventions section |

---

## Overall Verdict: **BLOCKED**

The accessibility issues (color-only encoding, missing ARIA) are real UX problems that affect ~8% of male users and all screen reader users. These must be fixed before the plan is implementable.

**Action required:** Fix the 3 blocking issues in PLAN.md, then re-run review.
