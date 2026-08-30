# Recon: what happens today to an accepted-but-unexecuted move?

## Report your findings

Write a wrap-up to `./wrap-ups/recon-accept-pending-execution-badge-out.md`.
This is recon only — do not implement anything. Write for someone
reading cold later.

## Context

Design decision made 2026-08-23 (see
`memory/freshstart_mode_sticky_ux_question.md` for full context): when a
user Accepts a move but hasn't actually executed the real trade at
their brokerage yet, the Moves tab should, on next view:
- If the live-recomputed diff for that ticker naturally resolves (price
  moved such that the position is back at/under target), stop showing
  it — no special handling needed, this should already be true of the
  live-recompute engine.
- If the diff still exists (or the position moved further from target),
  keep showing the move at its freshly recomputed numbers, with a
  "pending execution" badge — a small circled "!" indicator, visually
  modeled on `client/src/pages/Radar.jsx`'s `StaleTranscriptBadge`
  (~line 162-192: 14×14 circle, 1.5px border, color-coded, bold "!" at
  9px, tooltip via `title`).

**The open question this recon answers:** how much of this already
works? `server/routes/moves.js` already attaches prior `OwnerDecision`
rows on load specifically so "accept/decline state doesn't reset every
visit" (comment at ~line 1387-1392: "lets the frontend hydrate
accept/decline state... instead of resetting to 'undecided' every
visit"). Does the frontend actually render anything differently today
for an already-accepted move, or does `priorDecision` get attached to
the payload but never surfaced visually?

## What to check

1. **Trace what `priorDecision` actually does on the frontend.** Find
   where `MoveRow` (or equivalent) consumes `move.priorDecision` in
   `PortfolioManager.jsx` — does it change the row's rendering at all
   (a badge, a different button state, greyed-out Accept/Decline), or
   is it currently unused/only logged?
2. **Confirm the "diff naturally clears" case really needs no new
   code.** Trace `generateMovesForTicker` (or equivalent) to confirm
   that if a ticker's `currentPct` moves back under target, no move is
   generated for it regardless of any `OwnerDecision` history — i.e.
   accepted-and-resolved moves genuinely just stop appearing on their
   own.
3. **If nothing currently renders an "already accepted" state visually**,
   scope what would be needed: where exactly would the badge slot into
   `MoveRow`'s existing layout, what data is already available on the
   move object to determine "still needs this trade" vs. "resolved," and
   whether `StaleTranscriptBadge`-style logic can be reused directly or
   needs its own small component (recommend extracting a shared
   `CircledBangBadge` component if there's already more than one use
   case for this visual pattern — check if one exists first).
4. **Confirm date/amount context needed for the tooltip** — the
   design calls for something like "Accepted on [date] at $[X], still
   pending execution" — confirm `OwnerDecision.decidedAt` and
   `acceptedAmount` are both already stored and available for this.

## Report format

State clearly: does this already work end-to-end, partially, or not at
all? If partial, describe exactly what's missing so a fix prompt can be
written directly. Do not implement anything — this is fact-finding only.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-accept-pending-execution-badge-out.md` existing.
