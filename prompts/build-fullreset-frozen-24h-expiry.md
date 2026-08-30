# Build: Full Reset becomes a frozen snapshot with a 24-hour expiry

## Report your findings

Write a wrap-up to
`./wrap-ups/build-fullreset-frozen-24h-expiry-out.md`. This implements a
design decision finalized across several sessions — see
`memory/freshstart_mode_sticky_ux_question.md` for full background. Read
that context before starting; this task changes real behavior around
tax-adjacent, trade-affecting recommendations, so trace carefully rather
than assuming.

## Sequencing — check this first

This task depends on / interacts with two other pieces of work:

1. **`prompts/fix-movescache-preserve-freshstart.md`** (task tracked as
   #63) — a small, already-scoped bug fix for `refreshMovesCache()`
   silently dropping `isFreshStart`. Check whether its wrap-up
   (`wrap-ups/fix-movescache-preserve-freshstart-out.md`) already exists.
   If it hasn't landed yet, that's fine — implement this task's changes
   regardless, but don't undo or conflict with that fix if it lands
   later; the two are complementary (the bug fix matters most *within*
   the 24h window this task introduces).
2. **`prompts/build-moves-banner-reason-badge.md`** — builds a
   mode-parameterized banner component for the everyday Moves view. If
   its wrap-up already exists, read it and extend that same banner
   component with the freshStart branch below rather than building a
   second, separate banner mechanism.

## Context — current behavior, confirmed by direct code read

Today, `GET /:owner` (`server/routes/moves.js`, ~line 1915) does NOT
freeze anything: it reads `isFreshStart` from the cached payload and
**recomputes live** via `computeMovesPayload(owner, {
bypassWinnerProtection, freshStart })` on every single view, for as long
as the flag persists. This is a genuinely different mechanism from what
this task builds — today, Full Reset is an indefinitely-live recompute
mode; this task changes it to a frozen snapshot with a hard expiry.

## The decision being implemented

When a user confirms a Full Reset (`POST /:owner/rebaseline` with
`freshStart: true`):

1. The resulting payload is computed once and persisted (as today), but
   from that point forward it should be served **as a frozen snapshot**,
   not recomputed, for as long as it's within 24 hours of its
   `computedAt` timestamp.
2. **Fixed expiry, not sliding**: the 24-hour window is measured from
   `computedAt` (generation time), NOT from when it was last viewed.
   Viewing the tab must never extend the window — that would silently
   recreate indefinite stickiness, which is the exact thing being
   removed.
3. **Once 24 hours have passed**, if the account is still in Full Reset
   mode, treat it as expired: recompute via `computeMovesPayload` with
   `bypassWinnerProtection: false, freshStart: false` (pure normal mode)
   and persist that as the new cache entry, so `isFreshStart` naturally
   clears going forward. No special "expired" state needs to persist —
   the account just becomes a normal account again.
4. **Decisions made during the frozen window are NOT subject to
   expiry.** If the user accepted or declined a specific move before the
   24-hour mark, that `OwnerDecision` row is permanent, exactly like any
   other decision in the app. Expiry only affects *undecided* moves from
   that batch — an accepted-but-unexecuted move should keep being
   treated per the everyday accept/decline rules
   (`build-moves-banner-reason-badge.md`'s pending-execution badge, etc.)
   after expiry, same as before it. Declined moves keep their logged
   reason permanently regardless of mode expiry.

## What to build

1. In whatever code path serves moves for a given owner (`GET
   /:owner`), before recomputing: check `existingCache.payload.isFreshStart`
   and `existingCache.computedAt` (or wherever the timestamp actually
   lives — confirm the exact field name/location, don't assume).
   - If `isFreshStart` is true and `now - computedAt < 24h`: **serve the
     stored payload as-is**, not a fresh `computeMovesPayload` call —
     but still overlay current `OwnerDecision` state on top (accept/
     decline must still function normally on a frozen payload; read how
     `priorDecision` attachment currently works and make sure it still
     applies here).
   - If `isFreshStart` is true and `now - computedAt >= 24h`: recompute
     in normal mode (as described above) and persist the new payload.
   - Otherwise: existing behavior, unchanged.
2. Add the Full Reset banner (extending the mode-parameterized component
   from the other task, or building fresh if that task hasn't landed
   yet):
   > "This view reflects a full reset of the account, generated on
   > [date] — potentially selling every existing position and rebuilding
   > from your highest-conviction ideas. These recommendations expire 24
   > hours after generation unless acted upon. Declining any trade still
   > requires a logged reason."
   Substitute the actual `computedAt` date into `[date]`.

## Open question — trace this, don't silently assume an answer

**What happens to an accepted-but-unexecuted full-reset move once the
mode expires, if normal-mode computation wouldn't generate a move for
that same ticker at all?** Example: a full reset recommended trimming a
Strengthening-thesis position that would normally be protected by the
"winner protection" exception under everyday rules. The user accepted
it but hasn't executed. 24 hours pass and the mode expires, reverting to
normal-mode computation — which might not produce a move object for
that ticker at all, since winner protection would exempt it under
everyday logic.

**Trace what actually happens under your implementation and report it
clearly.** If there's a clean way to make sure a previously-accepted,
still-unexecuted move keeps surfacing regardless of whether normal-mode
generation would have produced it independently, and it's low-risk to
implement, do so. If it's genuinely ambiguous or would require deeper
changes to the move-generation pipeline, **stop and report the specific
mechanism you found, with a concrete example**, rather than guessing at
a fix — this is a real design question, not just an edge case to note in
passing.

## What NOT to do

- Do not touch the "Strengthening exception" / winner-protection logic
  itself — confirmed correct and staying as-is per prior discussion.
- Do not build a sliding-window expiry — fixed 24h from `computedAt`
  only.
- Do not touch `RebaselineModal`'s preview-fidelity bug (the preview not
  recomputing when the mode toggle changes) or the header-copy overlap
  ("Full reset" appearing in both modes' subtitle) — both are known,
  separate, smaller issues from `recon-rebaseline-modal-choices-out.md`,
  intentionally out of scope here.

## Verify

1. Confirm a freshly confirmed Full Reset is served as a frozen
   snapshot on immediate reload — numbers should be identical to what
   was shown at confirm time, not recomputed against live prices.
2. Simulate (or artificially backdate a `computedAt` in a read-only-safe
   way, e.g. a throwaway script against a test/dev row, not live data
   without explicit care) the 24h-elapsed case and confirm it correctly
   falls back to normal-mode computation and persists that as the new
   cache state.
3. Confirm accepting or declining a move during the frozen window still
   works normally, and that decision survives the mode's later expiry.
4. Confirm viewing the tab repeatedly during the 24h window does NOT
   extend the expiry clock.
5. Confirm the banner shows the correct generation date.
6. Run `./server/scripts/verify-allocation-math.sh` after any real
   writes.

## Commit and push

```bash
git add -A
git commit -m "Make Full Reset a frozen 24-hour snapshot instead of an indefinitely-live mode"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/build-fullreset-frozen-24h-expiry-out.md` existing, with the
open question above explicitly addressed — traced and either resolved
or clearly reported as needing a design decision.
