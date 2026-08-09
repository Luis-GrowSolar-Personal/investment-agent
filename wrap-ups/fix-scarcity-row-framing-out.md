# Fix: scarcity-gap row contradictory numbers and missing Target $ — findings

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)

## Root cause (both bugs traced to the same mechanism)

`computeMovesPayload` (`server/routes/moves.js`) has one generic
post-processing loop that derives `targetValue`/`currentShares`/
`targetShares` for every move in `allMoves`:

```js
m.targetValue = +(m.moveType === 'ADD' ? m.currentMktValue + m.dollarAmount : ...).toFixed(2);
```

This assumes `dollarAmount` always means "how much more to add to reach
`currentMktValue + dollarAmount`" — true for a real per-ticker ADD, false
for every `isBucketLevel` row, where `dollarAmount` is a *structural
shortfall against the bucket's own target*, unrelated to `currentMktValue`
by simple addition.

- The **fixed-bucket rows** (ETF/Crypto/Commodity "(unallocated)") are
  pushed into `allMoves` *before* this loop runs, so it silently overwrote
  their `targetValue` with a wrong number. E.g. Andrea's ETF row showed
  `$9,420.54` instead of the real 30% target of `$9,436.29` — off by
  $15.75, small enough to go unnoticed, but wrong for the same structural
  reason as the scarcity row below.
- The **scarcity-gap rows** (added last session) are pushed into
  `actionMoves` directly, *after* this loop already ran — so they never got
  a `targetValue` at all, rendering as `money(undefined)` → `'—'`.

The self-contradictory reason text ("at 29.7% — below target of 18.0%")
was a separate, compounding bug: the row's `currentPct`/`currentMktValue`
were the bucket's *raw current* value — which can legitimately sit above
target when a concentrated holding (SPWR, in Andrea's case) is
simultaneously overweight and being trimmed elsewhere. The scarcity
concept has nothing to do with the bucket's current aggregate $ — it's
about a reserved new-open slot (the `denom = max(group.length,
targetCount)` headroom from `computeIndividualModelWeights`) that stays
empty regardless of what the existing holdings are doing.

## Fix applied

**1. `server/routes/moves.js`, the generic derivation loop** (~line 1038):
added `if (m.isBucketLevel) continue;` — bucket-level rows now always set
their own `targetValue` explicitly, never derived generically.

**2. Fixed-bucket "(unallocated)" rows** (ETF/Crypto/Commodity): added
`currentShares: null, targetShares: null, targetValue: +targetValue.toFixed(2)`
to the pushed object, using the `targetValue` local variable already
computed a few lines above (`totalPortfolioValue * (b.targetPct / 100)`) —
the number that was always correct, just getting clobbered downstream.

**3. Scarcity-gap rows — reframed, not just patched.** Changed what
`currentPct`/`currentMktValue` mean for this row type specifically:

- **Before**: raw bucket current value/%.
- **After**: `achievableValue`/`achievablePct` — `heldTargetSum +
  newOpenSum`, i.e. where the bucket lands once its *other* recommended
  moves (trims, holds) execute. This is the same figure the shortfall
  calculation already used; it just wasn't also used for the "current"
  side of the display.
- `targetValue` set explicitly to `bucketTargetValue` (`totalPortfolioValue
  × poolPct`).
- Reason string reworded: *"{label}: once recommended trims/holds are
  applied, held positions plus any new opens account for {achievablePct}%
  against a {targetPct}% target — the remaining {shortfallPct}% has no
  watchlist candidate that currently clears the conviction bar..."*

Because `achievableValue <= bucketTargetValue` whenever `shortfall > 0` by
construction, this framing cannot produce the "29.7% below 18.0%"
contradiction — achievable is always at or below target when the row
fires at all.

**4. Frontend** (`client/src/pages/PortfolioManager.jsx`, `MoveRow`): added
a conditional `title` tooltip on the Current-column cell for
`isScarcityGap` rows, clarifying it shows the achievable position, not raw
current value. Didn't restructure the column layout beyond that — the
reframed numbers read correctly in the existing "Current / Target /
Amount" layout without needing a distinct visual structure, and the
`currentPct`/`targetPct` values now also flow correctly into the existing
"{current}% current / {target}% model" caption line (`PortfolioManager.jsx`
~line 569-572), which reads `move.currentPct`/`move.targetPct` directly —
no separate fix needed there since it consumes the same now-corrected
fields.

## Open design question — resolved, not left open

**Should this row fire while the bucket is aggregate overweight?** Yes,
and the fix keeps it firing in that case. Reasoning: the reserved new-open
slot's emptiness is independent of whether existing holdings are currently
over or under their own targets. Suppressing the row until the overweight
holding's trim executes wouldn't make the gap go away — it would just
delay surfacing it, and in Andrea's case the gap becomes *more* exposed
once the SPWR trim lands (the bucket drops toward `achievableValue`, which
is exactly the number this row is already built around). The reframing
already implemented is what makes firing-while-overweight correct instead
of contradictory, so no additional suppression logic was added. Documented
inline in the code comment at the `if (shortfall > minPositionDollar && ...)`
check.

## Verified against production data

Re-ran `computeMovesPayload(owner, { bypassWinnerProtection: true })` for
both owners.

**Andrea Morales — Speculative Equities (unallocated)** (the row from the
bug report):
```
currentPct: 9.0%       (was raw-current 29.7%)
targetPct:  18.0%
currentMktValue: $2,830.89   (was raw-current $9,345.19)
targetValue:     $5,661.78   (was undefined → "—")
dollarAmount:    $2,830.89
reason: "Speculative Equities: once recommended trims/holds are applied,
held positions plus any new opens account for 9.0% against a 18.0%
target — the remaining 9.0% has no watchlist candidate that currently
clears the conviction bar. Needs new names sourced (Layer 3 / Opportunity
Scanner), not a bigger allocation to what's already held."
```
No contradiction (9.0% is genuinely below 18.0%), Target column has a real
number.

**Andrea Morales — ETF (unallocated)**: `targetValue` now `$9,436.29`
(was `$9,420.54`) — matches `30% × $31,454.31` exactly.

**Eduardo Morales — Speculative Equities (unallocated)**: `currentPct
19.7%` vs `targetPct 27.5%`, `targetValue $8,834.72` (matches `27.5% ×
$32,126.25`) — consistent, no contradiction.

**Eduardo Morales — ETF (unallocated)**: `targetValue $8,031.56` (matches
`25% × $32,126.25`, was previously wrong under the old generic-derivation
bug too, just not flagged in the original report since it hadn't been
checked there).

## Files touched

- `server/routes/moves.js`
- `client/src/pages/PortfolioManager.jsx`

No schema/migration changes.
