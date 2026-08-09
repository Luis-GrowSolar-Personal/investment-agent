# Fix: surface bucket gaps below the minimum-position-size floor

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)

## What was added, up front

A third bucket-level row type, `isBelowFloor: true`, added as an `else if`
branch at both existing gate points in `computeMovesPayload`
(`server/routes/moves.js`):

1. The `fixedBuckets` loop (ETF/Crypto/Commodities) — right after the
   existing `if (shortfall > minPositionDollar)` actionable
   "(unallocated)" block.
2. The Established/Speculative scarcity-gap block — right after the
   existing `if (shortfall > minPositionDollar && b.sideCandidates.length === 0)`
   `isScarcityGap` block.

In both places: `else if (shortfall > 0)` — a real, permanent gap exists
(nothing currently held or candidate will ever close it) but it's too
small to justify recommending a new position. Pushes a
`"<label> (below minimum)"` row, `moveType: 'ADD'`, `priority: 6`,
`isBucketLevel: true`, `isBelowFloor: true`, with `dollarAmount` = the
real shortfall and a reason string naming the actual `minPositionDollar`
threshold.

Frontend (`client/src/pages/PortfolioManager.jsx`, `MoveRow`): added a
third branch to the existing `isBucketLevel` conditional chain — a dim
gray "BELOW MINIMUM" tag, distinct from both "NO QUALIFYING CANDIDATES"
(amber — a Radar/sourcing gap) and "Outside agent scope" (plain text — a
user-choice gap). The meaning here is a third, different thing: the gap is
real but the dollar amount itself isn't worth acting on.

## Confirmed: Eduardo's Commodities case now gets the row instead of silence

```json
{
  "shortName": "Commodities (below minimum)",
  "dollarAmount": 871.91,
  "reason": "Commodities is $872 short of target, but that's below the $1000 minimum position size — not worth a new position. Will stay this way until either the target model changes or commodities holdings grow enough on their own."
}
```

(Eduardo's `minPositionDollar` is configured at $1,000, not the $1,500
default — the reason string correctly reflects his actual owner-level
setting rather than a hardcoded number.)

Luis's Crypto and Commodities — the other two known cases — also now get
rows:

```json
[
  {"shortName":"Crypto (below minimum)","dollarAmount":740.53,"reason":"Crypto is $741 short of target, but that's below the $1500 minimum position size — not worth a new position. ..."},
  {"shortName":"Commodities (below minimum)","dollarAmount":740.53,"reason":"Commodities is $741 short of target, but that's below the $1500 minimum position size — not worth a new position. ..."}
]
```

## Reconciliation script — no change needed, and here's why

The prompt asked me to consider whether `server/scripts/verifyAllocationMath.js`
needed updating to treat `isBelowFloor` rows as an accounted-for category.
**It didn't need any change.** Its bucket-reconstruction logic already
sums `dollarAmount` for *any* row where `isBucketLevel === true` and the
bucket matches, without checking which specific bucket-level flag is set:

```js
for (const row of allRows) {
  if (row.isBucketLevel && row.bucket === unallocatedKey) sum += row.dollarAmount;
}
```

So the new `(below minimum)` rows were picked up automatically, with no
script edit. Before/after:

**Before:**
```
===== Eduardo Morales =====
  [FAIL] Commodities   target=$1606.31  reconstructed=$734.4    diff=$-871.91

===== Luis Morales =====
  [FAIL] Crypto         target=$740.53   reconstructed=$0        diff=$-740.53
  [FAIL] Commodities    target=$740.53   reconstructed=$0        diff=$-740.53
```

**After:**
```
===== Eduardo Morales =====
  [PASS] Commodities   target=$1606.31  reconstructed=$1606.31  diff=$0

===== Luis Morales =====
  [PASS] Crypto         target=$740.53   reconstructed=$740.53   diff=$0
  [PASS] Commodities    target=$740.53   reconstructed=$740.53   diff=$0
```

All three named cases now PASS. **What "PASS" means for these buckets has
subtly changed**, worth stating plainly: it no longer means "a move exists
that will close this gap" — it means "the engine has explicitly accounted
for and explained why this gap exists and won't be closed." The
reconciliation script can't tell those two apart (both just sum
`dollarAmount` on an `isBucketLevel` row), which is fine for its purpose
(catching silent/unexplained math errors) but worth remembering next time
a PASS shows up here — check whether it's a real closed gap or an
explained-and-accepted one.

## Full script output after the fix — confirms no regressions and no spurious firing

```
===== Eduardo Morales =====
  [FAIL] Established Equities   target=$8834.72  reconstructed=$8849.23  diff=$14.51   (unchanged — HOLD tolerance band)
  [PASS] Speculative Equities   target=$8834.72  reconstructed=$8834.72  diff=$0
  [PASS] ETF                    target=$8031.56  reconstructed=$8031.57  diff=$0.01
  [FAIL] Crypto                 target=$3212.62  reconstructed=$3419.57  diff=$206.95  (unchanged — HOLD tolerance band, not a below-floor case)
  [PASS] Commodities            target=$1606.31  reconstructed=$1606.31  diff=$0       ← now explained
  [PASS] Cash                   target=$1606.31  reconstructed=$1606.31  diff=$0

===== Luis Morales =====
  [PASS] Established Equities   target=$2776.98  reconstructed=$2777  diff=$0.02
  [FAIL] Speculative Equities   target=$925.66  reconstructed=$2823.64  diff=$1897.98  (unchanged — TRIM_CAP priority, not below-floor)
  [PASS] ETF                    target=$1851.32  reconstructed=$1851.32  diff=$0
  [PASS] Crypto                 target=$740.53  reconstructed=$740.53  diff=$0         ← now explained
  [PASS] Commodities            target=$740.53  reconstructed=$740.53  diff=$0         ← now explained
  [PASS] Cash                   target=$370.26  reconstructed=$370.26  diff=$0

===== Andrea Morales =====
  [FAIL] Established Equities   target=$9200.39  reconstructed=$9269.66  diff=$69.27   (unchanged — HOLD tolerance band)
  [PASS] Speculative Equities   target=$4954.05  reconstructed=$4954.05  diff=$0
  [PASS] ETF                    target=$9436.29  reconstructed=$9436.29  diff=$0
  [PASS] Crypto                 target=$3145.43  reconstructed=$3145.43  diff=$0
  [PASS] Commodities            target=$3145.43  reconstructed=$3145.43  diff=$0
  [PASS] Cash                   target=$1572.72  reconstructed=$1572.72  diff=$0
```

Andrea has **zero** below-floor rows — spot-checked directly (queried
`payload.moves.filter(m => m.isBelowFloor)` → `[]`), confirming the new
branch doesn't fire spuriously: every one of her gaps is either exactly
$0 or large enough to already trigger the existing actionable/scarcity
rows, and the `if`/`else if` structure means a bucket can never get both a
"(unallocated)"/"(scarcity)" row and a "(below minimum)" row
simultaneously.

Eduardo's Established ($14.51) and Crypto ($206.95), Luis's Speculative
($1,897.98), and Andrea's Established ($69.27) remain FAIL, unchanged in
size from the prior session — these are the HOLD-tolerance-band and
TRIM_CAP-priority cases documented in
`wrap-ups/fix-build-allocation-reconciliation-script-out.md`, not
below-floor cases, and this fix correctly leaves them alone.

## Files touched

- `server/routes/moves.js` (two `else if` branches added)
- `client/src/pages/PortfolioManager.jsx` (one new `MoveRow` tag branch)

No changes to `server/scripts/verifyAllocationMath.js` — confirmed
unnecessary, see above. No schema/migration changes.
