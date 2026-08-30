# Verify: shared drag-scroll standardization (Radar, Portfolio, Recommended Moves)

## Report your findings

Write a wrap-up to
`./wrap-ups/verify-drag-scroll-standardization-out.md`. This is a
**verification-only task — no code changes.** Do not fix anything you
find; report it clearly instead, so a separate fix prompt can be scoped
correctly. Write for someone reading cold later.

## Context

`wrap-ups/fix-position-table-sticky-actions-column-out.md` (commit
`af48727`) extracted a shared `DragScrollContainer` (drag-to-pan) from
`Radar.jsx` into `client/src/components/DragScrollContainer.jsx`, and
wired it into Portfolio's positions table and the Recommended Moves
grid in `PortfolioManager.jsx`. That entire task shipped with **zero
visual verification** — the Chrome browser tools were not connected in
that session. This task exists specifically to close that gap, now that
Claude in Chrome is connected.

Confirm first: check `railway status --json` (or equivalent) to confirm
`investment-agent-DEV` has picked up commit `af48727` before testing —
if it's still on an older commit, stop and report that rather than
testing stale code. The app's live URL is expected to be
`https://investment-agent-dev-production.up.railway.app` per
`docs/CoWork_handoff_2026-06-13b.md` — confirm this is still correct
(e.g. via `railway status` or asking Luis) rather than assuming a
months-old doc is current.

## What to check — in order

**1. Radar — confirm the extraction was a true no-op.**
Navigate to the Radar page. Drag-scroll a section horizontally (the
Portfolio or Watchlist table, whichever has enough columns to overflow).
Confirm:
- The drag gesture still works exactly as before (cursor changes to
  grabbing, table pans smoothly).
- The card's visual chrome (border, rounded bottom corners, background)
  looks unchanged — this is the thing the wrap-up was most worried about
  regressing, since the extraction had to pull Radar's hardcoded styling
  out into a passed-in prop.
- No stray visual artifacts (double borders, wrong corner radius,
  mismatched background) appeared.

**2. Recommended Moves — confirm the "ugly cutoff" symptom is actually fixed.**
Navigate to an owner's Moves/Action Required view. Resize the browser
window narrow — below roughly 820px wide (use `resize_window` if
available, or note if this must be done manually and ask Luis).
Confirm:
- The Accept/Decline buttons and other columns are no longer abruptly
  cut off or overlapping.
- Drag-scrolling the grid horizontally now works and reveals the
  Decision column.
- Take note of exactly how it looks at the narrowest reasonable width
  (e.g. 375px, a phone-sized viewport) even though mobile wasn't the
  original target — report what you see, don't just check the one
  820px boundary.

**3. Portfolio — confirm the click-suppression logic actually works.**
This is the check the wrap-up was least able to vouch for. Navigate to
an account with a wide table (Eduardo Custodial, per prior recons, has
the longest symbol/name values). Drag-scroll the positions table
horizontally across several rows.
Confirm:
- Rows do **NOT** expand/collapse as a side effect of the drag (this
  was the specific regression risk — dragging across a row triggers its
  `onClick` unless `suppressClickAfterDrag` is working).
- A genuine, deliberate click (no drag) on a row still expands/collapses
  it normally — confirm the suppression didn't overcorrect and break
  normal clicking.
- A genuine click on an action icon (rename/edit/remove) still fires
  that icon's own handler and does NOT also toggle the row.

**4. General regression check.**
- Confirm normal-width tables/rows (e.g. Luis ROTH IRA, short symbols)
  look completely unchanged from before this fix.
- Note the browser console for any errors during these interactions
  (`read_console_messages` if available).

## What NOT to do

- Do not attempt to fix anything found — this is verification only.
- Do not click Accept/Decline on any real move, or Remove on any real
  position — this is a live production-adjacent environment with real
  account data; look, don't act.
- Do not run a Force Sync or trigger any Schwab API call.

## Report format

For each of the 4 checks above, state clearly: **PASS**, **FAIL**, or
**COULD NOT TEST** (with why), plus a one-line description of what was
actually observed. If anything failed, describe it precisely enough
that a fix prompt could be written directly from your description
without re-investigating from scratch.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/verify-drag-scroll-standardization-out.md` existing, with a
clear pass/fail verdict for each of the 4 checks.
