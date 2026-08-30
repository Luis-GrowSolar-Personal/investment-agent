# Recon: ~$500-550 gap between scarcity row's "achievable" figure and sum of displayed Speculative TRIM targets

This is a **recon task, not a fix task**. Only touch code if you find an
unambiguous bug; if it's a legitimate difference in what two numbers
represent, report that clearly and don't change anything.

## Report your findings

Write findings to `./wrap-ups/recon-spec-achievable-gap-out.md`. State
the conclusion first (legitimate difference, or bug — and if bug, where),
then the supporting numbers. Write for someone reading cold later.

## Context

Last session's fix (`wrap-ups/fix-scarcity-row-framing-out.md`) redefined
the "Speculative Equities (unallocated)" row's current-value field to be
`achievableValue = heldTargetSum + newOpenSum` — i.e. where the
Speculative bucket lands once its other recommended trims/holds execute,
plus any new opens. That fix is verified internally consistent (current +
amount = target, exactly, every time) and eliminated the earlier
contradictory framing.

But comparing that `achievableValue` against a **manual sum of the
individual Speculative TRIM rows actually shown in Recommended Moves**
for Andrea Morales, there's a gap that shows up consistently across two
different target-model configurations:

**Before an est/spec-split edit (60/40 split, Speculative target 18.0% /
$5,662):**
- Scarcity row: `achievableValue` (shown as "current") = **$2,831**
- Manual sum of displayed TRIM targets — SPWR $439 + AMPX $944 +
  EOSE $944 = **$2,327**
- Gap: **$504**

**After editing the split to 65/35 (Speculative target 15.7% / $4,954):**
- Scarcity row: `achievableValue` = **$2,972**
- Manual sum of displayed TRIM targets — SPWR $439 + AMPX $991 +
  EOSE $991 = **$2,421**
- Gap: **$551**

The gap isn't fixed-dollar (it moved from $504 to $551 when the pool
changed), which suggests it's proportional to something in the
calculation rather than a flat rounding artifact or an off-by-one dollar
amount.

## What to check

1. Find where `heldTargetSum` is computed for the scarcity-row fix (in
   `computeMovesPayload`, `server/routes/moves.js`, near the
   `sizeSide(eligible.spec, ...)` call and the scarcity-row block added
   in the previous two sessions). Confirm exactly which tickers it sums
   over and what value it pulls for each (likely
   `modelWeights.get(ticker.id)` from `computeIndividualModelWeights`'s
   output, in dollars).

2. For each ticker in Andrea's held Speculative group (SPWR, AMPX, EOSE),
   compare:
   - The **raw value** `modelWeights.get(ticker.id)` produces (what
     `heldTargetSum` actually sums).
   - The **displayed TRIM target** shown in the Recommended Moves table
     for that ticker (what `generateMovesForTicker` ultimately assigns as
     `targetPct`/the move's dollar target after whatever move-type-
     specific logic applies — ratchet, hard cap, etc.).

   If these differ for one or more tickers, that's the source of the gap
   — find out *why* they differ. Candidates to check specifically:
   - Is one of these tickers hitting a ratchet tranche
     (`TRIM_RATCHET`) where the displayed target is
     `currentPct * 0.60` (ratchet 2) or similar, rather than the raw
     model weight? AMPX and EOSE both show "+$X harvest" tax notes in the
     UI, which might correlate with a full-lot ratchet-driven exit rather
     than a plain model-weight trim — check their `ratchetTranche` /
     `finalAction` / `thesisHealth` values directly.
   - Is a Type A/B multiplier (`ticker.type === 'B' ? 1.5 : 1.0` in
     `computeIndividualModelWeights.allocate()`) inflating one ticker's
     raw `modelWeights` entry above what actually gets displayed, because
     the *displayed* move used a different, lower target (e.g. clipped by
     `hardCapPct`, or overridden by a ratchet branch that takes priority
     over the plain `TRIM_MODEL` path in `generateMovesForTicker`)?
   - Double-check none of BTC/SIVR/other fixed-target ("commodity"/
     "crypto" bucket) tickers are leaking into this specific sum via
     their `tier` label — a previous recon this session found the
     opposite mistake (manually including SIVR/BTC in a Speculative tally
     when they're actually fixed-target tickers) and confirmed the actual
     code correctly excludes them from `computeIndividualModelWeights`'s
     input (`individualGroups`, not `fixedGroups`). Re-verify that's
     still true for the `heldTargetSum` computation specifically, since
     it's new code from the last session and hasn't been checked for this
     particular mistake.

3. Once you know which ticker(s) account for the gap and why, decide:
   - **If the difference is intentional/correct** (e.g. `heldTargetSum`
     is deliberately using the *pre-ratchet* model weight because that's
     the "ideal" figure the scarcity gap should be measured against, and
     the *displayed* trim target is deliberately more conservative for
     this one pass) — report that clearly, including which field means
     what, so it doesn't get re-flagged as a mystery next time.
   - **If it's a bug** (e.g. `heldTargetSum` should be using the same
     final per-ticker target the TRIM row displays, and isn't) — fix it
     in `computeMovesPayload`, re-verify against Andrea's real numbers
     that `heldTargetSum` now equals the sum of displayed TRIM targets
     for Speculative (and spot-check Established too, and Eduardo's
     account, to make sure the fix doesn't break the buckets that were
     already correct), and commit/push it yourself:

     ```bash
     git add -A
     git commit -m "<describe the fix>"
     git push origin dev
     ```

     If `git push` fails or the branch is behind, resolve it yourself
     (`git pull --rebase origin dev` then retry) and report what happened
     in the wrap-up.

## Reminder: write the wrap-up

Don't finish without `./wrap-ups/recon-spec-achievable-gap-out.md`
existing, stating the conclusion plainly up front.
