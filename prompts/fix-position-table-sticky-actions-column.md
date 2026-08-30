# Fix: standardize horizontal scroll across all data tables (shared DragScrollContainer + sticky identity/action columns)

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-position-table-sticky-actions-column-out.md`. Write for
someone reading cold later. This is a larger, three-file fix — take it
in the order below rather than all at once.

## Context

This started as a narrow fix for the Portfolio positions table (icons
disappearing off-screen on long symbol/name values). Two prior attempts
at pixel-width caps didn't fully solve it. A follow-up proposal to pin
just the actions column was reviewed and rejected — pinning only the
right edge means the row's identity (Symbol) scrolls away while
actions stay visible, so you can click something without knowing what
it acts on.

**Then a wider problem was found.** `Radar.jsx` already has a working,
well-built drag-to-pan implementation (`DragScrollContainer`,
~line 1601-1654) — it correctly excludes buttons/inputs/links from
initiating a drag, uses a 5px movement threshold to distinguish a
click from a drag, and resets cursor/selection state on mouseup/
mouseleave. It is NOT used anywhere else. Meanwhile, the Recommended
Moves table (`PortfolioManager.jsx`, `MOVE_GRID_COLS` grid starting
~line 408, rendered ~line 1803) has **no horizontal scroll handling of
any kind** — it's a fixed-width CSS Grid with nothing catching overflow
on a narrow viewport, which is why Luis saw the Accept/Decline actions
fall off in an "ugly" way on resize.

**Decision: standardize on the existing, proven `DragScrollContainer`
everywhere, layered with sticky identity/action columns on the two
tables where losing row context during a trade decision is unacceptable.**
Do not build a second scrolling mechanism (no arrow-ribbon, no new
custom gesture code) — reuse what's already working in Radar.

## The fix — four parts, in order

**1. Extract `DragScrollContainer` into a shared component.** Move it
out of `Radar.jsx` into a shared location (e.g.
`client/src/components/DragScrollContainer.jsx`), export it, and update
`Radar.jsx` to import it from there instead of defining it locally.
**Radar's own rendered behavior must be pixel-identical after this
move** — this step is a pure refactor, verify it stays inert.

**2. Apply it to Portfolio's positions table.** In
`client/src/pages/Portfolio.jsx`, replace the current plain
`<div style={{ overflowX: 'auto' }}>` wrapper (~line 377) with the
shared `<DragScrollContainer>`. Keep the existing Name/Symbol `maxWidth`
truncation from the two prior fixes — don't revert those.

**3. Apply it to the Recommended Moves grid.** In
`PortfolioManager.jsx`, wrap the grid (~line 1803, the
`gridTemplateColumns: MOVE_GRID_COLS` div and its `MoveTableHeader` +
`MoveRow` children) in the same shared `<DragScrollContainer>`. This is
the table that currently has zero overflow handling — confirm this
alone fixes the "ugly cutoff on resize" symptom before adding sticky
columns on top.

**4. Add sticky identity (left) + sticky action (right) columns — Portfolio
and Recommended Moves only, not Radar:**
   - **Portfolio positions table**: sticky-left on the Symbol cell,
     sticky-right on the rename/edit/remove actions cell (this was the
     original ask).
   - **Recommended Moves grid**: sticky-left on the Ticker column,
     sticky-right on the Decision column (Accept/Decline buttons) —
     these are the two columns of `MOVE_GRID_COLS` that matter most for
     "what am I deciding on and where's the button." Note this is a CSS
     Grid, not a `<table>` — `position: sticky` on a grid item works the
     same way, but confirm the grid's parent (the `DragScrollContainer`)
     is the actual scrolling ancestor for the sticky positioning to
     resolve against.
   - **Do not add sticky columns to Radar's table** — it's explicitly
     the reference/unchanged case; only the shared scroll mechanism
     applies there, not the sticky treatment.
   - Same background-tracks-hover-state care as before: sticky cells
     need a real (non-transparent) background that matches row hover
     state, not a static color, or scrolled content will visibly bleed
     through or mismatch on hover.

## Verify — visual verification required, check tool availability first

**State plainly and prominently at the top of the wrap-up whether
Chrome browser tools are connected this session.** The last two
Portfolio table fixes both shipped with zero visual verification.
That needs to either stop, or be flagged loudly again — don't bury it.

If connected:
1. Radar — confirm pixel-identical drag-scroll behavior after the
   extraction (step 1 is a pure refactor; regressions here are not
   acceptable).
2. Portfolio Custodial (Andrea) → Commodities (SIVR) and Eduardo
   Custodial → Equities (`*MATURED*` row) — confirm Symbol stays visible
   while dragging, actions stay visible and clickable, row identity is
   never ambiguous.
3. Recommended Moves — resize the browser narrow (simulate mobile) and
   confirm Accept/Decline no longer falls off ungracefully; confirm
   drag-to-pan works the same way it does in Portfolio/Radar; confirm
   Ticker and Decision stay visible while dragging through Current/
   Target/Amount/Tax.
4. Confirm dragging doesn't accidentally trigger a row's
   expand/collapse or a button's click in any of the three tables (the
   5px-threshold logic already handles this in Radar — confirm it
   still holds after the extraction and in the two new usages).
5. Confirm normal-width content in all three tables is visually
   unchanged from before this task.

If Chrome tools are NOT connected: say so immediately, do the best
static/analytical verification available, and explicitly tell Luis to
confirm visually before trusting this closed.

## Commit and push

```bash
git add -A
git commit -m "Standardize horizontal scroll (shared drag-to-pan + sticky identity/action columns) across Portfolio, Recommended Moves, and Radar tables"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-position-table-sticky-actions-column-out.md` existing.
