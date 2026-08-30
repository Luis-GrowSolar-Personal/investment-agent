# Recon: does RebaselineModal actually distinguish "plain re-baseline" from "full reset"?

## Report your findings

Write a wrap-up to `./wrap-ups/recon-rebaseline-modal-choices-out.md`.
Recon only — do not implement or change anything. Write for someone
reading cold later. This is the first piece of prep work for the
"should Full Reset be a sticky mode" discussion
(`memory/freshstart_mode_sticky_ux_question.md`) — no build decisions
are being made yet, just fact-finding.

## Context

The backend treats "plain re-baseline" (`bypassWinnerProtection: true,
freshStart: false`) and "Full Reset" (`bypassWinnerProtection: true,
freshStart: true`) as genuinely different computations — different
candidate pools, different treatment of existing positions (Principle 9
exception only applies in freshStart). It's unconfirmed whether the
frontend's `RebaselineModal` actually presents these as two distinct,
clearly-labeled user choices, or whether the UI collapses them into one
button/flow while the backend silently picks a mode.

## What to check

1. **Read `RebaselineModal`'s full component** (find it — likely
   `client/src/pages/PortfolioManager.jsx` or its own file; grep for
   "RebaselineModal" or the modal's trigger). Document exactly what
   choices the user is presented with: is there a toggle/checkbox for
   "full reset" vs. a plain re-baseline, are they two separate buttons,
   or is "Reset" the only option shown (with plain re-baseline not
   reachable from the UI at all)?
2. **Trace what request each visible button/control actually sends** —
   confirm which UI action results in `freshStart: true` vs. `false` in
   the `POST /:owner/rebaseline` call body.
3. **Check the copy/labels shown to the user for each choice.** Do they
   explain the difference in consequence (e.g. "rebuilds every position
   from scratch" vs. "closes the gap without touching existing
   positions")? Or is the language ambiguous/similar between the two?
4. **Check what happens after confirming each choice** — does the modal
   or a subsequent screen tell the user "this account is now in Full
   Reset mode" in any way, or does it just close and refresh the Moves
   tab with no persistent indication of which mode was chosen?
5. **Confirm whether a user can currently ever choose PLAIN re-baseline
   for an account that's already in Full Reset mode from the UI** — i.e.
   is there any existing "go back to normal" action reachable today, or
   does every visible path from this modal always set `freshStart: true`
   in practice (even if the backend technically supports `false`)?

## What NOT to do

- Do not modify `RebaselineModal`, the rebaseline route, or any
  copy/labels.
- Do not trigger a real rebaseline or full reset against live account
  data — read the code and, if helpful, inspect the rendered modal via
  Claude in Chrome (if connected) without submitting it, rather than
  actually executing a reset.

## Report format

For each of the 5 questions above, give a direct, evidence-based answer
(quote the actual JSX/copy where relevant). End with a plain summary:
does the current UI actually offer two distinct, well-labeled choices,
or does it functionally only offer one (Full Reset) with the other mode
existing only in the backend?

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-rebaseline-modal-choices-out.md` existing.
