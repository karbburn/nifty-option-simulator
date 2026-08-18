# Mobile UI Plan — NIFTY Option Simulator Dashboard

Companion to `PLAN.md`. Specifies mobile layout, **bottom tab bar** navigation, and touch handling. Desktop layout is unchanged (top nav, per `PLAN.md` / `UI-SPEC.md`).

## Goal

The dashboard must be fully usable on a phone — single thumb, no hover, no desktop-first pinching. Use a bottom tab bar to group the 6 dashboard sections into 4 tabs. Vanilla JS show/hide, no router, no URL changes.

---

## Section → Tab Mapping

| Desktop Section | Mobile Tab | Notes |
|-----------------|------------|-------|
| Header (spot ticker + freshness badge) | always visible (above tabs) | Sticky top bar |
| Live Positions (incl. Next Trade Preview) | **Live** | Preview card folds under positions |
| Past Trades | **Trades** | Table with horizontal scroll + tap-to-expand rows |
| Equity Curve + Probability/OOS + Benchmark | **Charts** | 3 charts stacked vertically |
| Expiry Explainer | **Expiry** | Static page, scoped to this tab |
| "Coming soon" blocks | hidden | Collapse to one dismissible note on the Trades tab |

Tabs: `Live`, `Trades`, `Charts`, `Expiry`.

---

## Layout

```
┌─────────────────────────────┐
│  header: NIFTY 24,950.75 ▲ │  ← sticky top bar, spot ticker + freshness badge
├─────────────────────────────┤
│                             │
│  [tab content]              │  ← one section visible at a time
│                             │
├─────────────────────────────┤
│  ● Live   Trades  Charts  Expiry │  ← fixed bottom tab bar
└─────────────────────────────┘
```

### Top header (mobile)
- Compact: logo mark left, spot ticker + delta flash right, freshness badge as a small dot/tooltip.
- `position: sticky; top: 0` with solid background.

### Bottom tab bar
- `position: fixed; bottom: 0; left: 0; right: 0; height: 56px`.
- `display: flex`; 4 equal tabs. Icon (emoji or inline SVG) + 11px label.
- Active tab: accent color underline + `aria-current="page"`.
- `padding-bottom: 56px` on `<main>` so content isn't hidden under the bar.
- `z-index` above charts (Chart.js canvases can overlay fixed elements otherwise).

### Tab switching (vanilla JS)
- Each tab is a `<section id="tab-live" class="tab-panel">` etc.
- Buttons `data-tab="live|trades|charts|expiry"`.
- Click → hide all `.tab-panel`, show target, update `aria-selected`/`aria-current`.
- Default tab: `live`. No URL hash, no history (single-user, YAGNI).

---

## Touch / Interaction Requirements

- **Tap targets ≥ 44×44px** for tab bar, sort headers, filter dropdowns, expandable rows.
- **No hover-only interactions.** Anything reachable by hover must be reachable by tap.
- Charts: Chart.js tooltips respond to touch by default; verify `interaction.mode` gives reasonable tap accuracy. Tap tooltips to pin them (default behavior).
- `touch-action: manipulation` on tab bar and table rows (kills 300ms delay / double-tap zoom).
- Sort headers: `aria-sort` + tap to cycle asc/desc/none.

---

## Component-Specific Mobile Rules

### Live Positions cards
- 1 per row (UI-SPEC §12 already spec'd `<768px` = 1 per row). `auto-fit` + `minmax(300px, 1fr)`.
- Card content stays as-is; ensure the premium sparkline canvas has an explicit height (UI-SPEC Gotcha 4) so it renders on narrow widths.
- Next Trade Preview renders as a compact card between positions and the tab content bottom.

### Trades table
- Wrapped in `overflow-x: auto` (UI-SPEC §12). Min column width so columns don't crush.
- **Tap-to-expand rows**: each `<tr>` has a chevron; tapping expands a detail row (side, strike, entry/exit premium, days held) beneath it. Vanilla JS toggling `hidden`. `aria-expanded` on the toggle.
- Sort/filter controls sit above the table, full-width stacked on mobile.

### Charts
- `maintainAspectRatio: false` + container height reduced (UI-SPEC §12: 200-250px).
- Charts stack vertically (already spec'd for `<992px`).
- Verify legend wraps to 2 lines on narrow widths; if cramped, `legend.position: 'bottom'`.

### Coming-soon blocks
- Hidden on mobile (`@media (max-width: 767px) { display: none }`).
- Replace with a single dismissible note on Trades tab: "Full data export & signals — coming soon."

### Expiry tab
- Reuses `expiry.html` content, rendered inside the tab panel. Text sizes ≥ 14px, line-height 1.5.

---

## Meta / Setup

- `<meta name="viewport" content="width=device-width, initial-scale=1">` in `base.html` head (required for all mobile layout).
- `<meta name="theme-color" content="#1976d2">` for the mobile browser chrome.
- Apple/Android icons already covered: `apple-touch-icon.png`, `icon-192.png` (see `PLAN.md` favicon tasks).

---

## Responsive Breakpoints

Desktop top nav / bottom tab bar switch:
- **≥ 768px** (tablet +): desktop top nav, sections all visible (no tabs).
- **< 768px** (mobile): bottom tab bar, one section at a time.
- The tab panels still render on desktop as normal sections; CSS shows/hides based on the breakpoint, and the JS tab buttons are only injected/active below 768px.

Simplest implementation: bottom tab bar HTML always present but `display: none` at ≥768px; `.tab-panel` only gets `display:none` styling inside the mobile media query.

---

## Files Touched

| File | Change |
|------|--------|
| `nifty_gap/web/templates/base.html` | viewport + theme-color meta, bottom tab bar markup + CSS, tab-switch JS |
| `nifty_gap/web/templates/dashboard.html` | wrap sections in `.tab-panel`, tap-to-expand rows, mobile coming-soon note |
| `nifty_gap/web/templates/trade.html` | verify responsive (no layout change expected) |
| `nifty_gap/web/templates/expiry.html` | usable inside tab panel (no change expected) |
| `tests/test_web.py` | assert viewport meta + tab bar present in `/` response HTML |

---

## Mobile Test Checklist

- [ ] 375px (iPhone SE/mini), 414px (iPhone Pro Max), 768px (tablet boundary) widths
- [ ] Landscape phone (spot ticker + one chart visible, no overflow)
- [ ] iOS Safari + Chrome Android (both engines)
- [ ] Bottom bar doesn't overlap last content (padding-bottom applied)
- [ ] Tap-to-expand rows work, `aria-expanded` toggles
- [ ] Sort headers ≥44px tap targets, `aria-sort` updates
- [ ] Charts render at reduced height, tooltips respond to touch
- [ ] Freshness badge readable at small size
- [ ] No horizontal page scroll (only table scrolls internally)

---

## ponytail Notes

- No router, no URL hash, no view transitions. Show/hide with JS is enough.
- Tab bar is plain HTML + flex + one small script — no framework, no library.
- Icons: emoji (`📈`, `📊`, `🔒` style) rather than an icon font/SVG sprite.