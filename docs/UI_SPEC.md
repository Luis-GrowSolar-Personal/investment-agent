# Investment Agent — UI Design Specification

## Core principle
**Icons for actions. Labels for information.**

- You *do* actions → icon button (compact, universal, tooltipped)
- You *read* information → colored label/badge (explicit, scannable)

---

## Action icons

All action icons use the same style: no border, no background, grey stroke (`#475569`),
colored on hover, `title` attribute for tooltip. Size: 13×13px SVG or equivalent Unicode.

| Action | Icon | Hover color | Notes |
|--------|------|-------------|-------|
| Edit / Rename | `<PencilIcon />` (SVG outline) | `#a78bfa` purple | Opens inline edit row or modal |
| View / Preview | `<EyeIcon />` (SVG outline) | `#60a5fa` blue | Opens read-only modal |
| Re-score / Refresh | `<ResyncIcon />` (SVG outline) | `#fbbf24` amber | Re-runs computation |
| Remove / Delete | `×` (Unicode U+00D7) | `#ef4444` red | Destructive; always confirm |

**Rule:** Never use text labels for these four actions in a table row. Always use the icon.

**Exception:** Promote/demote actions ("→ Portfolio", "→ Watchlist") stay as text labels
because they communicate destination, not just action type.

---

## Informational badges

Badges communicate state — they are not clickable. Use colored pills with a subtle
background tint and border.

```
background: {color}1a
color: {color}
border: 1px solid {color}33
border-radius: 4px
font-size: 11px
font-weight: 600
letter-spacing: 0.04em
text-transform: uppercase
padding: 1px 7px
```

### Thesis Health badge colors
| Value | Color |
|-------|-------|
| Strengthening | `#34d399` green |
| Intact | `#60a5fa` blue |
| Weakening | `#f59e0b` amber |
| Broken | `#ef4444` red |

### Recommendation badge colors
| Value | Color |
|-------|-------|
| Add | `#34d399` green |
| Hold | `#60a5fa` blue |
| Trim | `#f59e0b` amber |
| Exit | `#ef4444` red |

### Trajectory badge colors
| Value | Color |
|-------|-------|
| Strengthening | `#34d399` green |
| Improving | `#86efac` light green |
| Stable | `#60a5fa` blue |
| Flattening | `#94a3b8` slate |
| Softening | `#f59e0b` amber |
| Deteriorating | `#ef4444` red |
| Unknown | `#334155` dark slate |

### Future portfolio badges (allocator recommendations)
Follow the same pill style as Recommendation badges above.
| Value | Color |
|-------|-------|
| Add more | `#34d399` green |
| Hold | `#60a5fa` blue |
| Trim | `#f59e0b` amber |
| Exit | `#ef4444` red |
| New position | `#818cf8` indigo |

---

## Table structure

### Column headers
- Font: 10–11px, `font-weight: 600`, `letter-spacing: 0.05em`, `text-transform: uppercase`
- Color: `#475569` default, `#cbd5e1` when sort-active
- Sortable columns: `cursor: pointer`, `user-select: none`
- Sort indicator: ↑ or ↓ in `#3b82f6` blue, appended after label

### Row style
- Border: `1px solid #1e2330` bottom
- Hover background: `#0d1018`
- Font: 13px
- Primary data (symbol, value): `#f1f5f9`
- Secondary data (name, date): `#94a3b8`
- Muted / empty: `#475569` or `—`

### Action column (rightmost)
- Icon buttons: `display: flex`, `gap: 6px`, `flex-wrap: nowrap`
- Consistent order: navigate → edit → view → resync → remove
- No borders on icon buttons; rely on hover color change for affordance

---

## Sortable tables

Every table with more than 3 columns should support sorting. Implement via:
1. `useState({ key: 'defaultColumn', dir: 'asc' })`
2. `SortableTh` component (or equivalent) wrapping clickable `<th>`
3. Clicking active sort key toggles `asc` ↔ `desc`
4. Clicking new key sets it with `asc` (exception: date columns default to `desc`)
5. Secondary sort: symbol/name alphabetically breaks ties

### RADAR sortable columns
Symbol, Company, Type, Cap %, Calls, Last Updated

### Portfolio sortable columns (per account bucket tab)
Symbol, Name, Shares, Price, Mkt Value, Total G/L, Day G/L, % Acct

---

## Modals

- Background overlay: `#00000099`
- Modal card: `background: #0f1117`, `border: 1px solid #1e2330`, `border-radius: 10px`, `padding: 24px`
- Max width: 420–580px depending on content, `max-width: 95vw`
- Destructive modals: `border: 1px solid #3d1515`
- Button row: `justify-content: flex-end`, `gap: 8px`
- Cancel button: transparent, `border: 1px solid #2d3748`, color `#94a3b8`
- Primary button: `background: #3b82f6`, no border
- Destructive button: `background: #ef4444` (enabled only after confirmation)

---

## Color palette reference

| Purpose | Hex |
|---------|-----|
| Primary text | `#f1f5f9` |
| Secondary text | `#94a3b8` |
| Muted / disabled | `#475569` |
| Very muted | `#334155` |
| Border default | `#1e2330` |
| Border hover | `#2d3748` |
| Background surface | `#0f1117` |
| Background inset | `#0d1018` |
| Background deep | `#090c12` |
| Blue accent | `#60a5fa` |
| Green accent | `#34d399` |
| Amber accent | `#f59e0b` |
| Red accent | `#ef4444` |
| Purple accent | `#a78bfa` |
| Indigo accent | `#818cf8` |
