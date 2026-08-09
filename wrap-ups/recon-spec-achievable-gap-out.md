# Recon: achievable/displayed-TRIM gap in scarcity row — findings

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)
Commit: see `git log` — "Fix heldTargetSum to use each ticker's actual
displayed move target, not raw pre-ratchet model weight"

## Conclusion: real bug, fixed

`heldTargetSum` (in the scarcity-row block added two sessions ago, `server/routes/moves.js`)
summed `modelWeights.get(ticker.id)` — the **raw, pre-ratchet model weight**
computed by `computeIndividualModelWeights` — for every held ticker on a
barbell side. But the scarcity row's own promise, from last session's
reframing, is *"once recommended trims/holds are applied"* — i.e. it should
sum whatever each ticker's own displayed move actually resolves to, which
is not always the raw model weight.

## Root cause, confirmed against Andrea's SPWR

SPWR is on **`TRIM_RATCHET` tranche 2** (thesis Weakening). Its ratchet
target is `currentPct × 0.60` (moves.js ~line 557), a graduated-exit rule
that's intentionally more aggressive than a plain rebalance-to-model-weight
trim:

| | SPWR |
|---|---|
| Raw model weight (`modelWeights.get()`) | $990.81 (3.15%) — same as AMPX/EOSE, all three split the pool evenly |
| Displayed `TRIM_RATCHET` target (`currentPct × 0.60`) | $439.39 (1.4%) |
| Difference | **$551.42** |

That $551.42 is *exactly* the gap the recon prompt reported ($551, matching
to the dollar after rounding) for the 65/35-split scenario. The earlier
60/40-split scenario ($504 gap) is the same mechanism at a different pool
size — SPWR's ratchet target is a fixed fraction of its *current* value
(`currentPct × 0.60`), independent of the target-model split, so the raw
model weight (which does scale with the pool) pulls further away from the
ratchet target as the pool shrinks, and closer as it grows — consistent
with the gap being proportional rather than a flat dollar amount, as the
recon prompt observed.

AMPX and EOSE are both on the plain `TRIM_MODEL` path (ratchetTranche 0),
where the displayed target IS the raw model weight — no gap there. SIVR/BTC
were confirmed excluded from `individualGroups`/`heldGroup` entirely (they're
`fixedGroups` members, routed through `splitBucketTarget` instead) — the
mistake flagged as a thing to re-check in item 3 of "what to check" did NOT
recur.

## Fix applied

In the scarcity-row block, `heldTargetSum` now looks up each held ticker's
**actual displayed `targetValue`** from `allMoves` (built via a
`targetValueBySymbol` map, since individual moves are generated and get
their `targetValue` set by the generic derivation loop earlier in the same
function) instead of recomputing from `modelWeights.get()`. Falls back to
the raw model-weight calculation only if a ticker somehow has no move in
`allMoves` (shouldn't happen in practice — every `individualGroups` entry
gets exactly one move — but kept as a defensive fallback rather than
crashing).

## Verified against production data

**Andrea Morales — Speculative** (the reported case, 65/35 split):
```
achievableValue (scarcity row "current")  = $2,421.01
sum of displayed TRIM targets (SPWR+AMPX+EOSE) = $2,421.01
```
Exact match — the $551 gap is gone.

**Eduardo Morales — Speculative**: `achievableValue = $4,452.01`. Manually
summing only the *action* rows (SPWR+EOSE+AMPX+ENVX = $4,175.77) looked
like a $276.24 residual gap at first — but that's `BYDDY`'s current value
($276.24), which sits in `payload.holds` (a `HOLD` move, `dollarAmount: 0`)
rather than `payload.moves`, because `BYDDY` is `inScope: false` (a
regression/out-of-scope ticker — see the `canAdd` gate at moves.js
~line 619-621) and is therefore correctly denied an ADD recommendation
despite sitting under its model weight. Its "achievable" value is
genuinely its *unchanged* current value ($276.24), since no move will touch
it. $4,175.77 + $276.24 = $4,452.01 — matches exactly once the held-but-
untouched ticker is included. This is a second, independent confirmation
that `heldTargetSum` using each ticker's actual resolved move (including
`HOLD`'s "no change") is the right semantics, not a new bug.

**Established (both owners)**: no scarcity row fires for either (unchanged
from before this fix — Established has enough new-open candidates/held
coverage to reach target), so there was nothing to regress there. Spot-
checked that the fix's `targetValueBySymbol` lookup doesn't change any
Established number since none of Andrea's or Eduardo's Established holdings
are on the `TRIM_RATCHET` path this session.

## Files touched

- `server/routes/moves.js` (one block: the scarcity-row `heldTargetSum`
  computation)

No frontend changes needed — the corrected dollar figures flow through the
existing rendering from last session's fix.
