## UI-SPEC Review — Phase Web Dashboard

| Dimension | Verdict | Notes |
|-----------|---------|-------|
| 1 Copywriting | PASS | No generic CTA labels; empty states have specific copy with solution paths; badges use "CE ▲"/"PE ▼" with text labels |
| 2 Visuals | PASS | Focal point declared (header/spot ticker); icon-only actions have text labels; visual hierarchy indicated via layout grid |
| 3 Color | PASS (FLAG) | Accent reserved for specific elements only; 60/30/10 split not explicitly declared (FLAG, not BLOCK) |
| 4 Typography | FLAG | 6 unique font sizes declared (11, 12, 13, 14, 18, 24) vs. 4 specified in UI-SPEC scale; line height 1.5 declared for body |
| 5 Spacing | BLOCK | Spacing scale contains values (12px, 20px, 40px) not in standard set {4, 8, 16, 24, 32, 48, 64} — --sp-3, --sp-5, --sp-10 outside spec |
| 6 Registry Safety | PASS | No third-party registries listed; only Chart.js official CDN; no shadcn registry |

### Status: BLOCKED

**Blocking Issues:** Dimension 5 (Spacing) — the sole blocker preventing plan-phase from running.

### Blocking Issues Detail

**Dimension 5 — Spacing: BLOCK**

- **Description:** The spacing scale contains values not in the standard set {4, 8, 16, 24, 32, 48, 64}. The UI-SPEC defines CSS custom properties `--sp-3: 12px`, `--sp-5: 20px`, and `--sp-10: 40px`, all of which fall outside the standard set. These values are used throughout the implementation via `var(--sp-3)`, `var(--sp-5)`, and `var(--sp-10)` in CSS rules for padding, margins, and grid gaps across base.html, dashboard.html, trade.html, and expiry_content.html.

- **Fix:** Revise the UI-SPEC spacing variables to use only values from the standard set {4, 8, 16, 24, 32, 48, 64}. Specific remediation:
  - Replace `--sp-3: 12px` with one of: `--sp-3: 8px` or `--sp-3: 16px`
  - Replace `--sp-5: 20px` with one of: `--sp-5: 24px` or `--sp-5: 16px`
  - Replace `--sp-10: 40px` with one of: `--sp-10: 32px` or `--sp-10: 48px`
  
  Alternatively, adjust the implementation CSS to use absolute pixel values from the standard set where `var(--sp-3)`, `var(--sp-5)`, and `var(--sp-10)` are referenced (e.g., map 12px→16px, 20px→24px, 40px→32px). Since the UI-SPEC cannot be modified by the verifier, the remediation must either update the UI-SPEC spacing variables or adjust the implementation to use standard set values, and then re-run `/gsd-ui-phase`.

### Recommendations (non-blocking)

- **Dimension 4 — Typography:** Consider whether the 2 extra font sizes (11px for badges/labels, 13px for table numeric cells) can map to the existing "Small 12px" role rather than being declared as separate sizes. The line height of 1.5 for body text is correctly implemented.
- **Dimension 3 — Color:** The 60/30/10 surface dominance split could be explicitly documented in the UI-SPEC or CSS comments, though the variables are already defined (`--bg-primary`, `--bg-secondary`, `--bg-tertiary`). The accent color reservation is correct and specific.

### Action Required

Fix blocking issue in Dimension 5 (Spacing) by revising UI-SPEC spacing variables or adjusting implementation CSS to use only standard set values {4, 8, 16, 24, 32, 48, 64}. After remediation, re-run `/gsd-ui-phase` to re-verify. Do not proceed with plan-phase while any dimension is BLOCKED.