# Fix: replace misleading ADD-row funding flags with an honest split note

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-add-routing-honest-funding-note-out.md`.

## Context

`fix-add-routing-cash-double-counting` (commit `844e3c7`) fixed a real
bug — ADD rows no longer overlap-claim the same idle cash — but surfaced
a deeper framing problem, discussed and resolved with Luis 2026-08-24
(background: `memory/freshstart_mode_sticky_ux_question.md` and
`memory/accept_triggers_trade_ticket_backlog.md`).

**The problem:** in a Full Reset (and to a lesser extent everyday mode),
most of the dollar amount behind an ADD recommendation is not sitting in
the account as idle cash — it's expected to come from TRIM/EXIT
recommendations in the *same* batch, which haven't been executed yet.
The app has a standing rule (do not assume trim proceeds fund a specific
add — no pairwise coupling, see `CLAUDE.md` Never-Do list and the
"linked trim/add pairs NOT specially coupled" decision in
`memory/freshstart_mode_sticky_ux_question.md`) — so the routing layer
correctly refuses to credit unexecuted trim proceeds toward funding an
add. The result, after the double-counting fix, is that almost every ADD
row in a Full Reset now shows `insufficientCash` or `partiallyFunded`
against a tiny idle-cash balance — which is technically accurate but
reads as "something is broken" rather than "this is normal; the money
comes from trims you haven't done yet."

**Explicitly rejected alternatives** (do not build either of these):
gating Accept/Decline availability on other rows' accepted-trim totals,
or a sequenced "close out all trims before adds unlock" UI mode. Both
were rejected because `OwnerDecision`/Accept only logs intent — it does
not execute a trade or verify real cash — so any gate built on accepted-
but-unexecuted trims is guessing, not verifying. That kind of gate only
becomes valid once trade *execution* + balance re-verification exists
(tracked separately, backlogged, not this task —
`memory/accept_triggers_trade_ticket_backlog.md`).

## What to build

Replace the current `insufficientCash` / `partiallyFunded` flags (added
in `844e3c7`) on ADD rows with an **honest, informational split** — no
gating, no disabled buttons, Accept/Decline behavior on every row stays
exactly as free as it is today.

For each ADD row (both `buildAddRouting` ticker-specific rows and
`buildNewPositionRouting` bucket-level rows), the routing detail should
communicate, in plain terms:

- How much of the requested amount is covered by real, currently-idle
  cash in the routed account(s) (this is what the committed-cash ledger
  from `844e3c7` already computes correctly — reuse it, don't recompute).
- How much of the requested amount is *not* covered by idle cash, framed
  as "expected from trims in this reset, once executed" (or similar —
  exact wording your call, aim for something like: "$X available now ·
  $Y expected from trims in this reset, once executed") rather than the
  current "insufficient cash" / partial-funding warning language, which
  reads as an error state.
- Where cash genuinely is short **and there's no plausible trim in the
  same batch that could cover it** (e.g. every trim/exit in the batch is
  scoped to a different account or a different tax-treatment bucket than
  this add needs), that's still worth a distinct, more pointed note —
  trace whether this situation can actually occur and decide how to
  phrase it if so; don't silently fold it into the same soft language if
  it's a genuinely different situation.

## What NOT to do

- Do not gate Accept/Decline on any row based on other rows' decisions,
  accepted amounts, or funding totals. Every row's accept/decline button
  must remain independently clickable, exactly as today.
- Do not build a sequenced/staged UI mode ("do trims first, then
  adds unlock"). Explicitly out of scope, tracked as a future feature
  contingent on real trade execution existing first.
- Do not touch the committed-cash ledger's core logic
  (`availableCash`/`commitCash` in `server/routes/moves.js`, from
  `844e3c7`) — it's correct and should be reused as-is for the "covered
  by idle cash" figure.
- Do not touch the funding-order question (which row gets first claim on
  idle cash) — separately flagged in `844e3c7`'s wrap-up, not yet
  decided, not in scope here.

## Verify

1. Confirm the previous "insufficient cash" / partial-funding warning
   language is gone from ADD rows, replaced with the split note
   described above.
2. Confirm the split note's numbers are internally consistent: covered
   amount + uncovered amount = the row's total requested amount, for a
   sample of rows across all three owners.
3. Confirm Accept/Decline remain fully functional and independent on
   every row — no button disabled, no cross-row dependency introduced.
   Spot check by attempting (and cancelling before submit, per this
   session's established technique) an accept/decline on a row that
   would have been flagged `insufficientCash` under the old logic.
4. Confirm the genuinely-no-plausible-trim-coverage case (if it exists)
   is traced and reported, whether or not it warranted different
   wording.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` — display-only
   change, no writes expected; confirm output matches the tracked
   task-#50 baseline.

## Commit and push

```bash
git add -A
git commit -m "Replace ADD-row funding warnings with an honest idle-cash-vs-expected-from-trims split note"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-add-routing-honest-funding-note-out.md` existing, with
item 4 (the no-plausible-coverage edge case) explicitly addressed.
