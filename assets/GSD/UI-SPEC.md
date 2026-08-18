# UI-SPEC.md — NIFTY Option Simulator Web Dashboard

**Status:** draft
**Phase:** Web Dashboard (all phases)
**Design System:** Manual — plain HTML + inline CSS + Chart.js 4.x CDN
**Stack:** FastAPI + Jinja2 + Chart.js 4.x (unpkg CDN) + vanilla JS

---

## 1. Tech Stack & Constraints

| Constraint | Value |
|---|---|
| Framework | None — Jinja2 server-rendered HTML |
| CSS | Inline `<style>` block in `base.html`. No Tailwind, no build step |
| Charts | Chart.js 4.4.x via CDN (`https://cdn.jsdelivr.net/npm/chart.js@4.4.7`) |
| Error bars | `chartjs-chart-error-bars` plugin via CDN (`https://cdn.jsdelivr.net/npm/chartjs-chart-error-bars@4.4.5`) |
| Date adapter | `chartjs-adapter-date-fns@3.0.0` via CDN (`https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0`) |
| JS | Vanilla. No React, no build step |
| Deployment | Render free tier, auto-deploy from `main` |

### CDN Script Tags (in `base.html` head)

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-error-bars@4.4.5"></script>
```

Register the error bars plugin after Chart.js loads:

```js
Chart.register(
  ChartErrorBars.BarWithErrorBarsController,
  ChartErrorBars.BarWithErrorBar
);
```

---

## 2. Color Palette (CSS Variables)

All colors defined as CSS custom properties in `:root`. Matches existing matplotlib chart colors from `charts.py`.

```css
:root {
  /* ── Surfaces ── */
  --bg-primary: #ffffff;        /* page background — 60% dominant */
  --bg-secondary: #f8f9fa;      /* card backgrounds, sidebar — 30% */
  --bg-tertiary: #e9ecef;       /* table stripes, hover states */
  --border: #dee2e6;            /* card/table borders */

  /* ── Text ── */
  --text-primary: #212529;      /* headings, body */
  --text-secondary: #6c757d;    /* labels, captions, timestamps */
  --text-muted: #adb5bd;        /* disabled, placeholder */

  /* ── Accent — 10% usage, reserved for these elements ONLY ── */
  --accent: #1976d2;            /* active nav links, focused inputs, chart axis highlights */

  /* ── Financial semantic ── */
  --ce-green: #2e7d32;          /* CE badges, profit, positive P&L */
  --pe-red: #c62828;            /* PE badges, loss, negative P&L */
  --profit-bg: #e8f5e9;         /* profit cell background */
  --loss-bg: #ffebee;           /* loss cell background */
  --neutral-grey: #757575;      /* benchmark lines, 50% reference, "hold" series */

  /* ── Chart palette ── */
  --chart-blue: #1565c0;        /* equity curve, strategy line, IS bars */
  --chart-yellow: #f9a825;      /* OOS realized bars */
  --chart-drawdown: rgba(198, 40, 40, 0.18); /* drawdown shading */
  --chart-grid: #e9ecef;        /* grid lines */
  --chart-crosshair: rgba(0,0,0,0.12);

  /* ── Badge / status ── */
  --badge-fresh: #28a745;       /* data is current (< 2 days old) */
  --badge-stale: #ffc107;       /* data is 2-5 days old */
  --badge-stale-red: #dc3545;   /* data is > 5 days old */

  /* ── Spacing (8-point scale, multiples of 4) ── */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 8px;
  --sp-4: 16px;
  --sp-5: 24px;
  --sp-6: 24px;
  --sp-8: 32px;
  --sp-12: 48px;
  --sp-16: 64px;

  /* ── Typography ── */
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: "SF Mono", "Cascadia Code", "Fira Code", monospace;

  /* ── Radius ── */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;

  /* ── Shadows ── */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-hover: 0 2px 8px rgba(0,0,0,0.12);
}
```

---

## 3. Typography Scale

| Role | Size | Weight | Line-height | Usage |
|---|---|---|---|---|
| Body | 14px | 400 | 1.5 | All body text, table cells, form labels |
| Small | 12px | 400 | 1.5 | Timestamps, captions, chart axis labels, "n=49" annotations |
| Heading | 18px | 600 | 1.2 | Section headings ("Live Positions", "Equity Curve") |
| KPI | 24px | 600 | 1.1 | Hero numbers (spot price, P&L, equity) |

**Font stack:** system fonts only (no web font loading). `--font-body` covers all UI text. `--font-mono` for numeric values in tables and KPI cards where alignment matters.

---

## 4. Layout Grid

Single-page dashboard. No sidebar. Full-width scroll.

```
┌─────────────────────────────────────────────────────────┐
│  HEADER BAR                                             │
│  [Logo] NIFTY Gap Dashboard     [NIFTY 24,395.85 ▲]    │
│  [Dashboard nav] [Expiry Explainer nav]    [fresh badge]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─── KPI Row (4 cards, equal width) ──────────────┐   │
│  │  Total P&L  │  Win Rate  │  Sharpe  │  Max DD   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Live Positions (full width card) ────────────┐   │
│  │  [Card: Mon→Tue CE] [Card: Tue→Wed CE] [empty?] │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Next Trade Preview (full width card) ────────┐   │
│  │  Mon→Tue | CE | Strike 24950 | Prem ₹108.22     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Equity Curve (full width) ──────────────────┐   │
│  │  [Chart.js line — shaded drawdown]              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Two-Column Row ─────────────────────────────┐   │
│  │  ┌─── Probability & OOS ──┐ ┌─── Benchmark ──┐ │   │
│  │  │  Grouped bars + CI     │ │  Dual line      │ │   │
│  │  └────────────────────────┘ └────────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Past Trades Table (full width) ─────────────┐   │
│  │  [sortable headers] [filter dropdowns]           │   │
│  │  Entry Date | Exit Date | Pair | Side | ...      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─── Coming Soon (full width) ───────────────────┐   │
│  │  CSV Download  │  Trade Analytics               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  FOOTER: git sha · generated at · "research tool" note │
└─────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints

| Breakpoint | KPI Row | Two-Column Row | Position Cards |
|---|---|---|---|
| **≥ 992px** (desktop) | 4 columns | 2 columns (50/50) | Inline row, 2-3 per row |
| **768–991px** (tablet) | 2 columns | 1 column (stacked) | 2 per row |
| **< 768px** (mobile) | 1 column (stacked) | 1 column (stacked) | 1 per row |

All sections are full-width at every breakpoint. The two-column row (Probability + Benchmark) stacks vertically on < 992px.

---

## 5. Chart.js Configurations

### 5.1 Equity Curve (Line + Drawdown Shading)

**Canvas ID:** `equityChart`

```js
new Chart(document.getElementById('equityChart'), {
  type: 'line',
  data: {
    labels: equityCurve.map(d => d.date),        // ["2025-08-14", ...]
    datasets: [
      {
        label: 'Strategy Equity',
        data: equityCurve.map(d => d.equity),
        borderColor: '#1565c0',
        backgroundColor: 'rgba(21,101,192,0.08)',
        borderWidth: 1.5,
        pointRadius: 0,          // hide points on dense series
        fill: false,
        tension: 0.1,
        order: 1
      },
      {
        label: 'Drawdown',
        data: equityCurve.map(d => d.peak - d.equity),  // pre-computed in Jinja
        borderColor: 'transparent',
        backgroundColor: 'rgba(198,40,40,0.18)',
        borderWidth: 0,
        pointRadius: 0,
        fill: true,              // fills area below the equity line
        tension: 0.1,
        order: 2                 // renders behind equity line
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => ctx.dataset.label + ': ₹' + ctx.parsed.y.toLocaleString('en-IN', { maximumFractionDigits: 0 })
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'month', displayFormats: { month: 'MMM yyyy' } },
        grid: { display: false },
        ticks: { font: { size: 11 }, maxTicksLimit: 12 }
      },
      y: {
        grid: { color: '#e9ecef' },
        ticks: {
          font: { size: 11 },
          callback: v => '₹' + (v >= 0 ? '' : '-') + Math.abs(v/1000).toFixed(0) + 'k'
        }
      }
    }
  }
});
```

**Key decisions:**
- `pointRadius: 0` — 246 data points would be a blob of dots
- Drawdown as second dataset with `fill: true` and transparent border — standard equity-curve shading pattern
- Y-axis uses ₹k shorthand for readability
- Time scale with monthly ticks, auto-skips labels

### 5.2 Probability & OOS Chart (Grouped Bars with Error Bars)

**Canvas ID:** `probabilityChart`

Uses `chartjs-chart-error-bars` plugin. Each bar carries `y`, `yMin`, `yMax`.

```js
new Chart(document.getElementById('probabilityChart'), {
  type: 'barWithErrorBars',
  data: {
    labels: oosData.map(d => d.weekday_pair),  // ["Mon→Tue", "Tue→Wed", ...]
    datasets: [
      {
        label: 'Table (IS p_up)',
        data: oosData.map(d => ({
          y: d.p_up,
          yMin: d.ci_low,
          yMax: d.ci_high
        })),
        backgroundColor: 'rgba(25,118,210,0.8)',
        borderColor: '#1976d2',
        borderWidth: 1,
        barPercentage: 0.8,
        categoryPercentage: 0.7
      },
      {
        label: 'Realized (OOS)',
        data: oosData.map(d => ({
          y: d.realized_p_up,
          yMin: d.realized_ci_low,
          yMax: d.realized_ci_high
        })),
        backgroundColor: 'rgba(249,168,37,0.8)',
        borderColor: '#f9a825',
        borderWidth: 1,
        barPercentage: 0.8,
        categoryPercentage: 0.7
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => {
            const v = ctx.raw;
            const ci = ` [${(v.yMin*100).toFixed(1)}%–${(v.yMax*100).toFixed(1)}%]`;
            return ctx.dataset.label + ': ' + (v.y*100).toFixed(1) + '%' + ci;
          }
        }
      },
      // 50% reference line via annotation-like plugin (inline)
      annotation: false  // we draw this as a custom plugin below
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 }, maxRotation: 20 } },
      y: {
        min: 0, max: 1.05,
        grid: { color: '#e9ecef' },
        ticks: { font: { size: 11 }, callback: v => (v*100).toFixed(0) + '%' }
      }
    }
  },
  plugins: [{
    id: 'refLine50',
    afterDraw(chart) {
      const yScale = chart.scales.y;
      const ctx = chart.ctx;
      const y = yScale.getPixelForValue(0.5);
      ctx.save();
      ctx.strokeStyle = '#757575';
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(chart.chartArea.left, y);
      ctx.lineTo(chart.chartArea.right, y);
      ctx.stroke();
      ctx.restore();
      // label
      ctx.fillStyle = '#757575';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText('50%', chart.chartArea.right - 4, y - 4);
    }
  }]
});
```

**Key decisions:**
- Error bars are native to the `barWithErrorBars` chart type from the plugin
- 50% reference line drawn as an inline plugin (avoids the full `chartjs-plugin-annotation` dependency)
- Tooltip shows CI range in brackets

### 5.3 Benchmark Comparison (Dual Line)

**Canvas ID:** `benchmarkChart`

```js
new Chart(document.getElementById('benchmarkChart'), {
  type: 'line',
  data: {
    labels: benchmarkData.map(d => d.date),
    datasets: [
      {
        label: 'Ladder Strategy',
        data: benchmarkData.map(d => d.ladder_equity),
        borderColor: '#1565c0',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.1
      },
      {
        label: 'Hold-to-Expiry (benchmark)',
        data: benchmarkData.map(d => d.hold_equity),
        borderColor: '#757575',
        backgroundColor: 'transparent',
        borderWidth: 1.4,
        borderDash: [6, 3],
        pointRadius: 0,
        tension: 0.1
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => ctx.dataset.label + ': ₹' + ctx.parsed.y.toLocaleString('en-IN', { maximumFractionDigits: 0 })
        }
      }
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'month', displayFormats: { month: 'MMM yyyy' } },
        grid: { display: false },
        ticks: { font: { size: 11 }, maxTicksLimit: 12 }
      },
      y: {
        grid: { color: '#e9ecef' },
        ticks: {
          font: { size: 11 },
          callback: v => '₹' + (v >= 0 ? '' : '-') + Math.abs(v/1000).toFixed(0) + 'k'
        }
      }
    }
  }
});
```

### 5.4 Live Position Sparkline (Mini Line Charts)

Each live position card contains a small `<canvas>` with 5-10 data points (premium since entry). Rendered per-card.

```js
// Called once per position card
function renderSparkline(canvasId, premiums, side) {
  const color = side === 'CE' ? '#2e7d32' : '#c62828';
  return new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: {
      labels: premiums.map((_, i) => i),
      datasets: [{
        data: premiums,
        borderColor: color,
        backgroundColor: color + '18',
        borderWidth: 1.5,
        pointRadius: premiums.length <= 8 ? 2 : 0,
        pointBackgroundColor: color,
        fill: true,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: { display: false }
      },
      elements: { line: { borderJoinStyle: 'round' } }
    }
  });
}
```

**Canvas sizing:** `width: 100%; height: 48px` via CSS. Container is `position: relative` with fixed height.

### 5.5 Premium Path Chart (Trade Detail — `trade.html`)

**Canvas ID:** `premiumChart`

Horizontal reference lines for entry, stop levels, floor levels. Vertical line at exit day.

```js
new Chart(document.getElementById('premiumChart'), {
  type: 'line',
  data: {
    labels: premiumSeries.map(d => d.date),
    datasets: [
      {
        label: 'Premium Path',
        data: premiumSeries.map(d => d.premium),
        borderColor: '#1565c0',
        backgroundColor: 'rgba(21,101,192,0.08)',
        borderWidth: 1.8,
        pointRadius: 3,
        pointBackgroundColor: premiumSeries.map(d =>
          d.day === exitDay ? '#c62828' : '#1565c0'
        ),
        fill: false,
        tension: 0.15
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: ctx => '₹' + ctx.parsed.y.toFixed(2)
        }
      }
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 } } },
      y: {
        grid: { color: '#e9ecef' },
        ticks: { font: { size: 11 }, callback: v => '₹' + v.toFixed(0) }
      }
    }
  },
  plugins: [
    // Horizontal reference lines for ladder levels
    {
      id: 'ladderLines',
      afterDraw(chart) {
        const ctx = chart.ctx;
        const yScale = chart.scales.y;
        const levels = [
          { value: entryPremium, color: '#1565c0', label: 'Entry' },
          { value: entryPremium * 0.97, color: '#c62828', label: '-3% SL' },
          { value: entryPremium * 0.95, color: '#c62828', label: '-5% SL' },
          { value: entryPremium * 1.05, color: '#2e7d32', label: '+5% Floor' },
          { value: entryPremium * 1.10, color: '#2e7d32', label: '+10% Floor' },
          { value: entryPremium * 1.15, color: '#2e7d32', label: '+15% Target' }
        ];
        ctx.save();
        levels.forEach(lv => {
          const y = yScale.getPixelForValue(lv.value);
          if (y < chart.chartArea.top || y > chart.chartArea.bottom) return;
          ctx.strokeStyle = lv.color;
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 3]);
          ctx.globalAlpha = 0.6;
          ctx.beginPath();
          ctx.moveTo(chart.chartArea.left, y);
          ctx.lineTo(chart.chartArea.right, y);
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.fillStyle = lv.color;
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(lv.label + ' ₹' + lv.value.toFixed(0), chart.chartArea.left + 4, y - 3);
        });
        ctx.restore();
      }
    },
    // Vertical line at exit day
    {
      id: 'exitLine',
      afterDraw(chart) {
        const ctx = chart.ctx;
        const xScale = chart.scales.x;
        const exitIdx = premiumSeries.findIndex(d => d.day === exitDay);
        if (exitIdx < 0) return;
        const x = xScale.getPixelForValue(exitIdx);
        ctx.save();
        ctx.strokeStyle = '#c62828';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(x, chart.chartArea.top);
        ctx.lineTo(x, chart.chartArea.bottom);
        ctx.stroke();
        ctx.restore();
      }
    }
  ]
});
```

**Key decisions:**
- `pointRadius: 3` on the premium path to mark each daily close
- Exit day point colored red as a visual marker
- Ladder levels drawn as dashed horizontal lines with labels
- Only shows levels within the chart's Y range (avoids overflow labels)

---

## 6. Spot Ticker UX Pattern

### Location
Header bar, right-aligned, always visible.

### Update Pattern
- Polls `GET /api/spot` every 60 seconds via `fetch()`
- On update: flash the value green (up) or red (down) for 1.2s, then fade back to default color
- Arrow indicator: `▲` (green) / `▼` (red) / `—` (unchanged)

### Implementation

```html
<!-- base.html header -->
<header class="header">
  <div class="header-left">
    <a href="/" class="logo">NIFTY Gap Dashboard</a>
  </div>
  <div class="header-right">
    <span class="spot-ticker" id="spotTicker">
      <span class="spot-label">NIFTY 50</span>
      <span class="spot-value" id="spotValue">—</span>
      <span class="spot-change" id="spotChange"></span>
    </span>
    <span class="fresh-badge" id="freshBadge" title="Last data refresh"></span>
  </div>
</header>
```

```js
let lastSpot = null;

async function pollSpot() {
  try {
    const resp = await fetch('/api/spot');
    const data = await resp.json();
    const el = document.getElementById('spotValue');
    const change = document.getElementById('spotChange');
    const fmt = data.spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    el.textContent = '₹' + fmt;

    if (lastSpot !== null && data.spot !== lastSpot) {
      const dir = data.spot > lastSpot ? 'up' : 'down';
      el.classList.remove('flash-up', 'flash-down');
      void el.offsetWidth; // force reflow to restart animation
      el.classList.add(dir === 'up' ? 'flash-up' : 'flash-down');
      change.textContent = dir === 'up' ? '▲' : '▼';
      change.className = 'spot-change ' + dir;
    } else {
      change.textContent = '—';
      change.className = 'spot-change neutral';
    }
    lastSpot = data.spot;
  } catch (e) {
    document.getElementById('spotValue').textContent = '—';
  }
}

pollSpot();
setInterval(pollSpot, 60000);
```

### CSS for Flash Animation

```css
.spot-value {
  transition: color 0.3s ease;
}
.flash-up {
  color: var(--ce-green) !important;
  animation: spotFade 1.2s ease forwards;
}
.flash-down {
  color: var(--pe-red) !important;
  animation: spotFade 1.2s ease forwards;
}
@keyframes spotFade {
  0% { opacity: 1; }
  70% { opacity: 1; }
  100% { opacity: 1; color: var(--text-primary); }
}
```

**Key decisions:**
- No WebSocket — 60s polling is sufficient for a research tool
- Flash is a CSS class toggle + reflow trick, not a timeout
- Falls back to `—` on fetch failure (graceful degradation)
- Spot value formatted in Indian locale (`₹24,395.85`)

---

## 7. Data Freshness Badge

### Logic

```python
# In Jinja template context
from datetime import date, timedelta
today = date.fromisoformat("2026-08-15")  # or actual today
last_trading = date.fromisoformat(snapshot["last_trading_date"])
age = (today - last_trading).days
if age <= 1:
    badge_class, badge_text = "fresh", "● Data current"
elif age <= 5:
    badge_class, badge_text = "stale", f"● {age}d stale"
else:
    badge_class, badge_text = "stale-red", f"● {age}d old"
```

### HTML + CSS

```html
<span class="fresh-badge {{ badge_class }}" title="Last trading date: {{ last_trading_date }}">
  {{ badge_text }}
</span>
```

```css
.fresh-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  white-space: nowrap;
}
.fresh-badge.fresh { background: #e8f5e9; color: var(--badge-fresh); }
.fresh-badge.stale { background: #fff8e1; color: #f57f17; }
.fresh-badge.stale-red { background: #ffebee; color: var(--badge-stale-red); }
```

**Key decisions:**
- Badge is always visible in the header — not buried in a footer
- Three states: fresh (≤1d), stale (2-5d), old (>5d)
- Tooltip shows the exact `last_trading_date` on hover

---

## 8. Past Trades Table — Vanilla JS Sort & Filter

### Table Structure

```html
<section class="card">
  <div class="card-header">
    <h2>Past Trades</h2>
    <div class="filters">
      <select id="filterPair" onchange="filterTrades()">
        <option value="">All Pairs</option>
        <!-- populated from data -->
      </select>
      <select id="filterReason" onchange="filterTrades()">
        <option value="">All Reasons</option>
        <!-- populated from data -->
      </select>
      <select id="filterSide" onchange="filterTrades()">
        <option value="">All Sides</option>
        <option value="CE">CE</option>
        <option value="PE">PE</option>
      </select>
    </div>
  </div>
  <div class="table-wrap">
    <table id="tradesTable">
      <thead>
        <tr>
          <th data-sort="entry_date" class="sortable">Entry ↓</th>
          <th data-sort="exit_date" class="sortable">Exit ↓</th>
          <th data-sort="pair" class="sortable">Pair ↓</th>
          <th data-sort="side" class="sortable">Side ↓</th>
          <th data-sort="strike">Strike</th>
          <th data-sort="entry_premium">Entry ₹</th>
          <th data-sort="exit_premium">Exit ₹</th>
          <th data-sort="exit_reason" class="sortable">Reason ↓</th>
          <th data-sort="days_held">Days</th>
          <th data-sort="pnl" class="sortable">P&L ↓</th>
        </tr>
      </thead>
      <tbody id="tradesBody">
        <!-- Jinja-rendered rows, then JS re-sorts/filters -->
      </tbody>
    </table>
  </div>
</section>
```

### Number/Currency Alignment

```css
/* All numeric/currency cells right-aligned */
td:nth-child(n+6), th:nth-child(n+6) {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  font-size: 13px;
}

/* Profit/loss cell coloring */
td.pnl-positive { color: var(--ce-green); background: var(--profit-bg); }
td.pnl-negative { color: var(--pe-red); background: var(--loss-bg); }
```

### Sort Implementation (Vanilla JS)

```js
let currentSort = { col: 'entry_date', dir: 'desc' };

document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.sort;
    if (currentSort.col === col) {
      currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
      currentSort = { col, dir: 'desc' };
    }
    sortAndRender();
  });
});

function sortAndRender() {
  const tbody = document.getElementById('tradesBody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const colIdx = [...tbody.closest('table').querySelectorAll('th')].findIndex(
    th => th.dataset.sort === currentSort.col
  );
  rows.sort((a, b) => {
    let va = a.cells[colIdx].textContent.trim();
    let vb = b.cells[colIdx].textContent.trim();
    // Numeric sort for currency columns
    if (['entry_premium', 'exit_premium', 'pnl', 'strike', 'days_held'].includes(currentSort.col)) {
      va = parseFloat(va.replace(/[₹,]/g, '')) || 0;
      vb = parseFloat(vb.replace(/[₹,]/g, '')) || 0;
    }
    if (va < vb) return currentSort.dir === 'asc' ? -1 : 1;
    if (va > vb) return currentSort.dir === 'asc' ? 1 : -1;
    return 0;
  });
  rows.forEach(r => tbody.appendChild(r));
}
```

### Filter Implementation

```js
function filterTrades() {
  const pair = document.getElementById('filterPair').value;
  const reason = document.getElementById('filterReason').value;
  const side = document.getElementById('filterSide').value;
  const rows = document.querySelectorAll('#tradesBody tr');
  rows.forEach(row => {
    const show =
      (!pair || row.dataset.pair === pair) &&
      (!reason || row.dataset.reason === reason) &&
      (!side || row.dataset.side === side);
    row.style.display = show ? '' : 'none';
  });
}
```

**Key decisions:**
- Data attributes (`data-pair`, `data-reason`, `data-side`) on `<tr>` for filtering — no data re-parsing
- Numeric sort uses `parseFloat` with `₹,` stripped — handles ₹12,345.67 format
- `font-variant-numeric: tabular-nums` for aligned columns
- Monospace font for numeric cells prevents layout shift during sort
- Sort indicator: `↓`/`↑` appended to header text on click

---

## 9. Jinja ↔ Chart.js Data Injection Pattern

Data flows: Python `dashboard.json` → Jinja template → `<script>` tag → Chart.js constructor.

### Pattern

```html
<!-- dashboard.html, inside a <script> block -->
<script>
  // 1. Inject data from Jinja context as a JSON literal
  const equityCurve = {{ equity_curve | tojson }};
  const oosData = {{ oos_data | tojson }};
  const benchmarkData = {{ benchmark_data | tojson }};
  const trades = {{ trades | tojson }};
  const livePositions = {{ live_positions | tojson }};

  // 2. Render charts using the injected data
  renderEquityChart(equityCurve);
  renderProbabilityChart(oosData);
  renderBenchmarkChart(benchmarkData);
  renderLivePositions(livePositions);
</script>
```

### Gotchas

1. **`tojson` filter escapes `</script>`** — safe to embed in `<script>` tags. Never use `| safe` for data.
2. **NaN/Infinity in JSON** — `tojson` renders `null`. Chart.js handles `null` as a gap (correct). Verify the Python side converts `NaN` → `None` before serialization.
3. **Large arrays** — 246 equity points × ~30 bytes ≈ 7KB. 234 trades × ~200 bytes ≈ 47KB. Total payload < 100KB. No streaming needed.
4. **Date strings** — pass as ISO date strings (`"2025-08-14"`), not timestamps. Chart.js time scale parses ISO strings natively.
5. **Indian number format** — `toLocaleString('en-IN')` in JS tooltips/labels. Don't pre-format in Python.

---

## 10. Live Position Cards

### Card Layout

```html
<div class="positions-grid" id="positionsGrid">
  <!-- One card per active position -->
  <div class="position-card" data-pair="Mon→Tue" data-side="CE">
    <div class="position-header">
      <span class="pair-label">Mon→Tue</span>
      <span class="side-badge ce">CE</span>
      <span class="dte-badge">4 DTE</span>
    </div>
    <div class="position-body">
      <div class="position-stat">
        <span class="stat-label">Strike</span>
        <span class="stat-value">₹24,900</span>
      </div>
      <div class="position-stat">
        <span class="stat-label">Entry</span>
        <span class="stat-value">₹112.50</span>
      </div>
      <div class="position-stat">
        <span class="stat-label">Live</span>
        <span class="stat-value" id="live-prem-0">₹125.30</span>
      </div>
      <div class="position-stat">
        <span class="stat-label">P&L</span>
        <span class="stat-value profit">+₹960</span>
      </div>
    </div>
    <div class="position-chart">
      <canvas id="spark-0" height="48"></canvas>
    </div>
    <div class="position-footer">
      <span class="pct-move">+11.4% move</span>
      <span class="banked-floor">Floor: none</span>
    </div>
  </div>
</div>
```

### CSS

```css
.positions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--sp-4);
}
.position-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--sp-4);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}
.position-card:hover { box-shadow: var(--shadow-hover); }
.side-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.side-badge.ce { background: var(--ce-green); color: #fff; }
.side-badge.pe { background: var(--pe-red); color: #fff; }
.dte-badge {
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: auto;
}
.position-chart { height: 48px; margin: var(--sp-2) 0; }
.stat-label { font-size: 11px; color: var(--text-secondary); display: block; }
.stat-value { font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-value.profit { color: var(--ce-green); }
.stat-value.loss { color: var(--pe-red); }
```

### No Positions State

```html
<div class="empty-state" id="noPositions">
  <p>No live positions currently open.</p>
  <p class="empty-sub">Positions appear here when a tradeable weekday pair signals and the entry date passes.</p>
</div>
```

---

## 11. KPI Row Cards

Four equal-width cards at the top of the dashboard.

```html
<div class="kpi-row">
  <div class="kpi-card">
    <span class="kpi-label">Total P&L</span>
    <span class="kpi-value {{ 'profit' if total_pnl >= 0 else 'loss' }}">
      {{ "₹{:,.0f}".format(total_pnl) }}
    </span>
  </div>
  <div class="kpi-card">
    <span class="kpi-label">Win Rate</span>
    <span class="kpi-value">{{ "{:.1f}".format(win_rate * 100) }}%</span>
  </div>
  <div class="kpi-card">
    <span class="kpi-label">Sharpe (Ann.)</span>
    <span class="kpi-value">{{ "{:.2f}".format(sharpe) }}</span>
  </div>
  <div class="kpi-card">
    <span class="kpi-label">Max Drawdown</span>
    <span class="kpi-value loss">{{ "₹{:,.0f}".format(max_dd) }}</span>
  </div>
</div>
```

```css
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-4);
}
.kpi-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--sp-4) var(--sp-5);
  box-shadow: var(--shadow-card);
  text-align: center;
}
.kpi-label { font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: var(--sp-1); }
.kpi-value { font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.kpi-value.profit { color: var(--ce-green); }
.kpi-value.loss { color: var(--pe-red); }

@media (max-width: 991px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .kpi-row { grid-template-columns: 1fr; }
}
```

---

## 12. Responsive Strategy Summary

| Element | Desktop (≥992px) | Tablet (768-991px) | Mobile (<768px) |
|---|---|---|---|
| Header | Logo left, spot + badge right | Same | Stack: logo top, spot below |
| KPI Row | 4 columns | 2 columns | 1 column |
| Live Positions | auto-fill grid, min 260px | 2 per row | 1 per row |
| Equity Curve | Full width, ~300px height | Full width, 250px | Full width, 200px |
| Two-Column Row | 50/50 side by side | Stacked | Stacked |
| Trades Table | Full width, scrollable | Full width, scrollable | Horizontal scroll wrapper |
| Chart height | 300-350px | 250-300px | 200-250px |

### Chart Container Pattern

```html
<div class="chart-container">
  <canvas id="equityChart"></canvas>
</div>
```

```css
.chart-container {
  position: relative;
  width: 100%;
  height: 320px;       /* desktop */
}
@media (max-width: 991px) { .chart-container { height: 260px; } }
@media (max-width: 767px) { .chart-container { height: 220px; } }
```

---

## 13. Chart.js Gotchas & Jinja Integration Notes

### Gotcha 1: `NaN` in JSON
Chart.js silently drops `NaN` points (creates gaps in line charts). This is usually correct. But for bar charts, `NaN` makes bars vanish. **Fix:** filter `NaN` in Python before serialization:
```python
import math
data = [None if math.isnan(v) else v for v in raw_list]
```

### Gotcha 2: Time Scale Requires Date Adapter
Chart.js 4.x does NOT include a date adapter. Without it, `type: 'time'` silently falls back to `category` and dates display as raw strings. **Fix:** include `chartjs-adapter-date-fns` in `base.html`.

### Gotcha 3: Error Bars Plugin Registration
`chartjs-chart-error-bars` must be registered globally before chart creation. Register after Chart.js loads but before any chart constructor runs. **Fix:** put `Chart.register(...)` in a `<script>` tag at the end of `base.html`'s `<head>`, before body scripts.

### Gotcha 4: `responsive: true` + Container Height
Chart.js respects the container's CSS height only if `maintainAspectRatio: false`. Every chart must set both. **Fix:** always use the `.chart-container` pattern from §12.

### Gotcha 5: Canvas Re-render on Spot Update
When spot updates, only the KPI values and live position cards need re-rendering. Do NOT re-render the entire chart set. **Fix:** spot poll updates DOM text only; charts are static (built from nightly snapshot).

### Gotcha 6: `tojson` and Date Strings
Jinja's `tojson` filter serializes Python `datetime.date` as `{"year": 2025, "month": 8, "day": 14}` — not an ISO string. **Fix:** convert dates to ISO strings in Python before passing to template:
```python
snapshot["equity_curve"] = [
    {"date": d["date"].isoformat() if hasattr(d["date"], "isoformat") else str(d["date"]),
     "equity": d["equity"]}
    for d in raw_equity
]
```

### Gotcha 7: Chart.js Destroy/Recreate
If you ever need to update a chart (e.g. live re-marking), call `chart.destroy()` before creating a new one on the same canvas. Otherwise you get doubled/misaligned canvases. For this dashboard, charts are static and rendered once on page load, so this shouldn't apply.

---

## 14. Coming Soon / Paywall Placeholders

```html
<section class="card coming-soon">
  <div class="coming-soon-overlay">
    <span class="coming-soon-badge">Coming Soon</span>
  </div>
  <div class="coming-soon-content">
    <h3>Export Trade Data</h3>
    <p>Download full trade log as CSV with detailed exit analytics.</p>
  </div>
</section>
```

```css
.coming-soon {
  position: relative;
  opacity: 0.7;
}
.coming-soon-overlay {
  position: absolute;
  top: var(--sp-3);
  right: var(--sp-3);
}
.coming-soon-badge {
  background: var(--text-secondary);
  color: #fff;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
```

---

## 15. File Manifest

| File | Role |
|---|---|
| `nifty_gap/web/templates/base.html` | Base layout: nav, header (spot ticker + badge), footer, CDN scripts, CSS variables, shared JS (spot poll, fresh badge) |
| `nifty_gap/web/templates/dashboard.html` | Main dashboard: KPI row, live positions, next trade, equity curve, probability/OOS, benchmark, trades table, coming soon |
| `nifty_gap/web/templates/trade.html` | Trade detail: summary header + premium path chart with ladder lines |
| `nifty_gap/web/templates/expiry.html` | Static explainer: ladder mechanics, exit reasons, rollover finding |

---

## 16. Design Decisions Log

| # | Decision | Rationale |
|---|---|---|
| 1 | CSS variables, no utility framework | Single-user tool, < 500 lines of CSS total. Variables give consistency without build step. |
| 2 | System font stack | Zero load time. Render free tier cold-starts are already slow — no font blocking. |
| 3 | Error bars via plugin, not custom drawing | `chartjs-chart-error-bars` handles the CI whisker rendering correctly (caps, alignment, grouped layout). Custom plugin is error-prone for grouped bars. |
| 4 | 50% reference line as inline plugin | Avoids `chartjs-plugin-annotation` (another CDN dependency). A 15-line afterDraw plugin is sufficient. |
| 5 | `pointRadius: 0` on equity/benchmark lines | 246 points with dots = unreadable blob. Dots only on sparklines (5-10 points). |
| 6 | Flash animation via CSS class toggle + reflow | No `setTimeout` chains. Single reflow trigger handles the animation cleanly. |
| 7 | Table sort in JS, not Jinja | Jinja sorts at render time only. JS sort gives instant feedback on header click without page reload. |
| 8 | Data attributes on table rows for filtering | Avoids re-parsing JSON or querying a JS array. Direct DOM filter is O(n) with no framework overhead. |
| 9 | `font-variant-numeric: tabular-nums` on all numbers | Prevents layout shift when values change (KPI updates, sort). Monospace font for currency columns as secondary alignment. |
| 10 | Charts rendered once on load, not re-rendered on spot update | Spot update only changes KPI text and position card text. Charts reflect the nightly snapshot — no live re-marking needed for v1. |

---

*Generated 15 Aug 2026. For the implementation plan, see `PLAN.md`.*
