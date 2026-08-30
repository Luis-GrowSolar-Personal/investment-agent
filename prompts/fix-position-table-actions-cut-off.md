# Fix: long ticker names push Rename/Edit/Remove icons off-screen

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-position-table-actions-cut-off-out.md`. This should be
a small, low-risk fix — implement it directly. Write for someone
reading cold later.

## Context

On Eduardo Custodial's Equities tab, the Rename/Edit/Remove (×) icons
in the last column are invisible/unreachable for every row — confirmed
via screenshot. Andrea Custodial's equivalent table shows all three
icons fine. Luis was unable to remove the `29415C127` placeholder
position (same one already handled correctly for Andrea last week) on
Eduardo's account because of this.

**Root cause, already traced — not the question here:**
`client/src/pages/Portfolio.jsx:377` wraps the positions table in a div
with `overflowX: 'auto'` (a scroll container is already present), but
the `<table>` itself (line 378) is pinned to `width: '100%'`. With
default `table-layout: auto`, this forces the browser to compress every
column to fit the container's visible width regardless of content
length, rather than letting the table grow wider and engage the
existing scroll container. Eduardo Custodial has a row with an
unusually long name (`BYD CO LTD FUNSPONSORED ADR 1 ADR REPS 1` for
BYDDY) that consumes the extra horizontal space, squeezing the
actions column (`PositionRow`, ~line 223-241 — three icon buttons in
one `whiteSpace: 'nowrap'` cell) off the visible/interactive area.
Andrea's and Luis's tables don't have any row with a name this long, so
they never hit it.

## The fix

Change `client/src/pages/Portfolio.jsx:378`'s table style from
`width: '100%'` to `minWidth: '100%'` (do NOT remove `width` entirely if
that changes narrow-table behavior unexpectedly — test both approaches
and pick whichever preserves normal-width-table appearance while
allowing overflow when content demands it). This lets the table exceed
the container's width when a long cell (like a long ticker name)
requires it, and the existing `overflowX: 'auto'` wrapper will then
show a real horizontal scrollbar/support trackpad-swipe scrolling to
reach the actions column — no custom drag-to-pan implementation needed.

Read the current file before editing — confirm line numbers, since
other fixes landed in this file recently (delete-button `res.ok` fix,
per `wrap-ups/fix-position-delete-check-res-ok-out.md`, if that's
landed by the time you read this).

**Secondary, optional improvement** (only if trivially easy alongside
the main fix — don't scope-creep if it's not): consider whether the
Name column (`PositionRow`, ~line 197-199, `{pos.ticker.shortName ||
pos.ticker.name}`) should truncate very long names with
`textOverflow: 'ellipsis'`/`whiteSpace: 'nowrap'`/a `maxWidth`, showing
the full name on hover via a `title` attribute — this would reduce how
often a single long name blows out the table width in the first place.
Implement only if it's a clean, small addition; otherwise just fix the
scroll behavior and leave this as a note in the wrap-up.

## Verify

1. Reproduce first: confirm Eduardo Custodial's actions column is
   genuinely unreachable before the fix (screenshot or DOM inspection),
   not just visually cramped.
2. After the fix: confirm the actions column (rename/edit/remove) is
   reachable via horizontal scroll on Eduardo Custodial specifically —
   scroll the table right and confirm all three icons appear and are
   clickable.
3. Confirm Andrea Custodial and Luis ROTH IRA (tables without long
   names) look visually unchanged — no new unwanted horizontal
   scrollbar appearing where there wasn't one before.
4. Confirm this applies to every bucket tab (Equities, ETFs, Crypto,
   Commodities), not just Equities, since they likely share the same
   table component/styles — check by reading the code, not just testing
   one tab.
5. Do NOT attempt to remove the `29415C127`/`EOS ENERGY ENTERP 26 XXX
   *MATURED*` positions yourself as part of this fix — that's Luis's
   own manual data-cleanup decision (he's confirming these are
   worthless/non-taxable first), not something to do proactively.

## Commit and push

```bash
git add -A
git commit -m "Allow positions table to scroll horizontally instead of squeezing action icons off-screen"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-position-table-actions-cut-off-out.md` existing.
