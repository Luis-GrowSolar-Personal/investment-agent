# Build: everyday Moves tab — banner, mandatory decline reason, pending-execution badge

## Report your findings

Write a wrap-up to `./wrap-ups/build-moves-banner-reason-badge-out.md`.
This implements design decisions finalized across several sessions —
see `memory/freshstart_mode_sticky_ux_question.md` for full background.
Three independent pieces; verify and report each separately. Write for
someone reading cold later.

## Part 1 — Banner

Add a banner at the top of the everyday (non-full-reset) Moves/Action
Required view, above the move list:

> "These are today's recommended trades to bring your allocation back
> toward target, based on current prices. Declining any trade requires
> a logged reason."

This banner text is specific to everyday mode. A separate, differently-
worded banner for Full Reset mode is being built in a different task
(`build-fullreset-frozen-24h-expiry.md`) — **structure this as a small
component/function parameterized by mode** (e.g. `MovesBanner({ mode,
... })`) rather than hardcoding the everyday text inline, so the other
task can add the freshStart branch without restructuring what you build.
If that other task has already landed by the time you read this, read
its wrap-up first and extend what's there instead of creating a second,
conflicting banner mechanism.

## Part 2 — Mandatory decline reason, with prefill on repeat decline

Design decision (see memory doc): decline must always require a logged
reason — no suppression of any trim/exit recommendation was chosen
specifically so users can't quietly avoid confronting an over-target
position; the reason is the accountability mechanism instead.

Current state: `MoveRow` (`PortfolioManager.jsx`) already has
`inputReason` state and a decline flow — confirm whether submitting a
decline with an empty reason is currently possible. If so, block it:
disable the confirm/submit action until the reason field is non-empty
(whitespace-only should not count as filled).

**Prefill on repeat decline**: if the user is declining a move that has
a `priorDecision` with `decision === 'declined'`, prefill the reason
input with `priorDecision.reason` (editable, not read-only) rather than
starting blank. Confirming still writes a fresh `OwnerDecision` row with
a new `decidedAt` — this is a reaffirm-with-edit-option, not a dedupe;
every decline still gets its own timestamped record even if the text is
identical to last time.

Read the current file before editing — confirm current decline-submit
validation and exact prior-decision data shape.

## Part 3 — Pending-execution badge

Design decision: an accepted-but-not-yet-executed move currently renders
as a green `✓ Accepted $X`, which reads as "done" when it may mean
"agreed three days ago, never executed." Per
`wrap-ups/recon-accept-pending-execution-badge-out.md`: **no new data
model is needed** — a move that is still being rendered already has a
live diff, so `decision.status === 'accepted'` on a rendered row already
means "accepted, still pending." The gap is purely visual.

**1. Extract a shared badge component.** Currently exactly one
circled-bang instance exists: `StaleTranscriptBadge`
(`Radar.jsx:162-192` — 14×14 circle, `borderRadius:'50%'`, `1.5px solid
${color}`, `fontSize:9`, `fontWeight:800`, `cursor:'help'`,
`flexShrink:0`, tooltip via `title`). Extract the visual into
`client/src/components/CircledBangBadge.jsx` taking `color` and `title`
props. Refactor `StaleTranscriptBadge` to wrap it, preserving its exact
existing thresholds/tooltip logic (`daysSinceLastCall < 85` early
return, its two tooltip strings) — this refactor must be a true no-op
for Radar, verify it renders identically.

**2. Add the badge to the Decision cell.** In `PortfolioManager.jsx`'s
Decision cell (~line 508, already a flex row with `gap: 6` containing
the `✓ Accepted $X` span and `change` button — no layout change should
be needed), add the badge inline when `decision.status === 'accepted'`
(recall: if the row is rendering at all, it's pending by definition).
Tooltip text: "Accepted on [date], still pending execution" using
`decidedAt`.

**3. Historically accurate dollar amount for the tooltip.** If the
tooltip should also state the amount ("Accepted on [date] at $[X], still
pending execution"), note the existing gap found in the recon: the
frontend's fallback is `m.priorDecision.acceptedAmount ??
m.dollarAmount`, which falls back to **today's freshly recomputed**
number when `acceptedAmount` is null (i.e. the user accepted "the full
recommendation" rather than a partial amount) — this would misreport
today's number as if it were the historical one. The correct historical
value is stored in `OwnerDecision.systemSnapshot.dollarAmount`, but
`systemSnapshot` is not currently included in the `priorMap` payload
built in `moves.js` (~line 1403-1407). Add it (the whole
`systemSnapshot` object, or just `dollarAmount` — pick whichever is
cleaner given how `priorMap` is structured) so the frontend has the real
historical figure instead of guessing from a fallback.

**Note on interaction with pending sticky-column work**: the Decision
column is the same one `fix-position-table-sticky-actions-column`'s
still-unshipped part 4 (sticky columns) would eventually pin — if that
work has landed by the time you build this, make sure the badge sits
correctly inside whatever background treatment the sticky cell uses.

## Edge cases to decide or flag (do not silently pick one without noting it)

1. **Partial execution** — user accepts $500 of a $1,000 trim and
   executes exactly that. The diff shrinks but doesn't vanish, so the
   row keeps showing, still badged pending. The data model can't
   distinguish this from "did nothing." Not fixable without execution
   tracking (out of scope) — just don't let the badge/tooltip imply more
   precision than the data supports.
2. **Accepted-then-drifted-further** — price moves the wrong way after
   acceptance; today's recomputed number is now larger than what was
   accepted. Decide whether the tooltip should show both numbers or just
   today's — either is defensible, state which you picked and why.
3. **Declined moves have the identical staleness ambiguity** (a `✗
   Declined` from a week ago looks the same as one from today) — out of
   scope for this task, note it for a future pass, do not attempt to fix.

## Verify

1. Banner renders correctly in everyday mode with the exact copy above.
2. Attempting to decline with an empty reason is blocked; a non-empty
   reason succeeds and creates a new `OwnerDecision` row.
3. Declining the same move a second time prefills the previous reason,
   editable, and still logs a fresh `decidedAt`.
4. `StaleTranscriptBadge` in Radar renders pixel-identical to before the
   extraction (visual verification if Chrome tools are connected; if not,
   say so plainly and do a careful source diff instead, per this
   session's established standard for this file).
5. An accepted, still-open move shows the pending badge with a correct
   tooltip; a fully resolved (diff-cleared) move does not show at all,
   confirming no suppression/persistence logic was accidentally added
   beyond what already existed.
6. Confirm `systemSnapshot` (or `dollarAmount` from it) is present in the
   payload the client receives for a decision with `acceptedAmount:
   null`, and that the tooltip uses it correctly instead of the live
   fallback.

## Commit and push

```bash
git add -A
git commit -m "Add Moves tab banner, mandatory decline reason with prefill, and pending-execution badge"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/build-moves-banner-reason-badge-out.md` existing, with each
of the three parts verified and reported separately, and the edge-case
decisions stated explicitly.
