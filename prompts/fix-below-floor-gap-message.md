# Fix: surface bucket gaps that are real but below the minimum-position-size floor

## Report your findings

Write a wrap-up to `./wrap-ups/fix-below-floor-gap-message-out.md`. State
up front what was added and where, then show the reconciliation script's
output (or the raw payload) confirming Eduardo's Commodities case now
gets this new informational row instead of silence. Write for someone
reading cold later.

## Context

`server/scripts/verify-allocation-math.sh` and this session's fixes have
surfaced a recurring, deliberate design gap: when a bucket has a real
shortfall between its target and what's actually achievable, but that
shortfall is below `minPositionDollar` (too small to justify recommending
a brand-new position), the engine currently generates **no row at all**
for it — the gap is silently invisible in the Moves tab. Confirmed
examples from this session:

- **Eduardo Morales, Commodities**: target $1,606.31, achievable $734.40
  (his only commodity holding, SIVR, sits under its own cap and nothing
  will ever move it up — see `wrap-ups/fix-fixed-bucket-undercap-achievable-out.md`),
  a genuine $871.91 gap that will never close via any move the engine
  generates, but below the $1,500 floor so nothing gets shown.
- **Luis Morales, Crypto and Commodities**: $740.53 gap each, same
  mechanism, same silence.

Luis's own framing for why this needs fixing (verbatim): *"Otherwise, 3
months from now, I'll be wondering 'why isn't it recommending an add?'"*
— the tool needs to explain itself even when the answer is "there's
nothing worth recommending," not just go quiet.

**Important distinction — don't confuse this with the existing HOLD
tolerance band.** A single ticker sitting within ~1 point of its own
model weight already correctly gets a `HOLD` move and shows up in "No
Action Needed" — that part already works and needs no change. This fix
is specifically for the case where a *bucket-level* gap exists (current
achievable total vs. bucket target) that's real, permanent (no move will
ever close it), and small enough that no actionable recommendation makes
sense.

## What to build

This applies to **both** places in `computeMovesPayload`
(`server/routes/moves.js`) that currently gate a bucket-level
informational row behind `shortfall > minPositionDollar`:

1. The `fixedBuckets` loop (ETF/Crypto/Commodities "(unallocated)" rows).
2. The Established/Speculative scarcity-gap block (added two sessions
   ago — "(unallocated)" rows with `isScarcityGap: true`).

In both places, add an `else if` branch: when `shortfall > 0` (a real gap
exists) but `shortfall <= minPositionDollar` (too small to act on), push
a new kind of informational bucket-level row — distinct from both the
existing "(unallocated)" actionable rows and the "no qualifying
candidates" scarcity rows. Something like:

```js
{
  moveType: 'ADD', priority: 6, symbol: null,
  shortName: `${label} (below minimum)`,
  bucket: ..., tier: ...,
  currentMktValue: +achievableValue.toFixed(2),
  targetValue: +bucketTargetValue.toFixed(2),
  dollarAmount: +shortfall.toFixed(2),
  isBucketLevel: true,
  isBelowFloor: true,   // new flag, distinct from isScarcityGap
  reason: `${label} is $${shortfall.toFixed(0)} short of target, but that's below the $${minPositionDollar} minimum position size — not worth a new position. Will stay this way until either the target model changes or ${label.toLowerCase()} holdings grow enough on their own.`,
}
```

Adjust field names/values to match whatever the surrounding code
actually uses — read the current source at both call sites rather than
assuming the shape above is exact (this codebase's move objects have
picked up several fields across sessions).

### Frontend — `client/src/pages/PortfolioManager.jsx`

In `MoveRow`, the `move.isBucketLevel` branch currently checks
`isScarcityGap` (from last session's fix) to choose between "NO
QUALIFYING CANDIDATES" and "Outside agent scope". Add a third branch for
`isBelowFloor`: a distinct, clearly non-actionable tag — something like a
dim gray "BELOW MINIMUM" — different from both existing treatments, since
the meaning is different again: this isn't "pick a ticker yourself" or
"nothing qualifies," it's "the gap is real but too small to bother with."

## Verify

Run `./server/scripts/verify-allocation-math.sh` before and after. The
script currently reports FAILs for Eduardo's Commodities and Luis's
Crypto/Commodities because it has no concept of floor-suppression — after
this fix, those buckets will now have a row to point to, but the
underlying dollar reconciliation won't change (this fix adds
*visibility*, not a new move that closes the gap). Consider whether the
reconciliation script itself should be updated to recognize
`isBelowFloor` rows as an accounted-for, expected category rather than a
FAIL — if you make that change too, note it clearly in the wrap-up since
it changes what "PASS" means for these buckets going forward.

Also spot-check that this doesn't fire where it shouldn't: buckets with
zero gap, or a gap large enough to already trigger the existing
actionable/scarcity rows, must not additionally get a "below minimum" row.

## Commit and push

You have real local git access — commit and push this yourself, Luis
doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "Surface bucket gaps below minPositionDollar as an informational row instead of silence"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without `./wrap-ups/fix-below-floor-gap-message-out.md`
existing.
