# Automated allocation reconciliation script — build + first real run

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)

## What was built

- **`server/scripts/verifyAllocationMath.js`** — for every `OwnerProfile`
  in the database, calls `computeMovesPayload(owner, { bypassWinnerProtection: true })`
  directly (no HTTP/auth), and for each of the six allocation buckets
  (Established, Speculative, ETF, Crypto, Commodities, Cash) reconstructs
  what the bucket total *should* equal from the individual moves/holds the
  engine actually generated, then compares it against
  `payload.allocation.buckets`' own `targetValue`. $2 tolerance for
  `.toFixed(2)` rounding noise. Prints PASS/FAIL per owner per bucket with
  target/reconstructed/diff. Exit code `0` if everything passes, `1` if
  anything fails.
- **`server/scripts/verify-allocation-math.sh`** — thin wrapper, loads
  `DATABASE_URL` from `.env` the same way every other DB command in
  `CLAUDE.md` does.

### How to run it

```bash
./server/scripts/verify-allocation-math.sh
```

### Reconciliation rule implemented

- **Established/Speculative**: sum every row with `bucket ∈ {'equity', null}`
  and `tier === <side>` (covers held tickers, new-open ADD candidates, and
  HOLD/out-of-scope tickers), using each row's `targetValue` if it has one
  (a real move) or `currentMktValue` if not (a HOLD never changes the
  position). Add the matching `"<side> (unallocated)"` scarcity-gap row's
  `dollarAmount` if one exists.
- **ETF/Crypto/Commodities**: same idea, rows matched by `bucket === <key>`
  instead of `tier` — this is what correctly *excludes* SIVR/BTC from the
  Speculative sum (they're `bucket: 'commodity'/'crypto'` even though
  tagged `tier: 'speculative'` for display) while *including* them here.
- **Cash**: independently re-derived from `cashReservePct/100 × totalPortfolioValue`,
  no individual-move reconciliation needed.

This directly encodes the two "learned the hard way" lessons from this
session's recon passes (`wrap-ups/recon-established-spec-shortfall-out.md`:
don't mix up `tier` label with actual `bucket`; `wrap-ups/recon-spec-achievable-gap-out.md`:
use the ticker's *resolved* move target, not its raw model weight).

## Proof it actually catches bugs (the required sanity check)

Temporarily reverted the `heldTargetSum` fix from this session (back to
summing `modelWeights.get()` — the raw pre-ratchet model weight — instead
of each ticker's resolved `targetValue`), reran the script, and confirmed
Andrea's Speculative row flipped from PASS to a FAIL with a sensible,
exactly-explained delta:

```
[FAIL] Speculative Equities   target=$4954.05  reconstructed=$4402.63  diff=$-551.42
```

`-$551.42` is exactly SPWR's ratchet-target-vs-model-weight gap identified
in `wrap-ups/recon-spec-achievable-gap-out.md` for this same target model.
Reverted immediately after (`cp /tmp/moves.js.bak server/routes/moves.js`,
confirmed `git diff` clean before moving on).

## Real run against all three current owners

```
===== Eduardo Morales =====
  [FAIL] Established Equities   target=$8834.72  reconstructed=$8849.23  diff=$14.51
  [PASS] Speculative Equities   target=$8834.72  reconstructed=$8834.72  diff=$0
  [PASS] ETF                    target=$8031.56  reconstructed=$8031.57  diff=$0.01
  [FAIL] Crypto                 target=$3212.62  reconstructed=$3419.57  diff=$206.95
  [FAIL] Commodities            target=$1606.31  reconstructed=$734.4  diff=$-871.91
  [PASS] Cash                   target=$1606.31  reconstructed=$1606.31  diff=$0

===== Luis Morales =====
  [PASS] Established Equities   target=$2776.98  reconstructed=$2777  diff=$0.02
  [FAIL] Speculative Equities   target=$925.66  reconstructed=$2823.64  diff=$1897.98
  [PASS] ETF                    target=$1851.32  reconstructed=$1851.32  diff=$0
  [FAIL] Crypto                 target=$740.53  reconstructed=$0  diff=$-740.53
  [FAIL] Commodities            target=$740.53  reconstructed=$0  diff=$-740.53
  [PASS] Cash                   target=$370.26  reconstructed=$370.26  diff=$0

===== Andrea Morales =====
  [FAIL] Established Equities   target=$9200.39  reconstructed=$9269.66  diff=$69.27
  [PASS] Speculative Equities   target=$4954.05  reconstructed=$4954.05  diff=$0
  [FAIL] ETF                    target=$9436.29  reconstructed=$9420.54  diff=$-15.75
  [FAIL] Crypto                 target=$3145.43  reconstructed=$2665.56  diff=$-479.87
  [FAIL] Commodities            target=$3145.43  reconstructed=$2307.12  diff=$-838.31
  [PASS] Cash                   target=$1572.72  reconstructed=$1572.72  diff=$0

RECONCILIATION FAILURES FOUND — exit code 1
```

**Important: exit code 1 does NOT mean 9 new bugs.** Interpreting each
failure by inspecting the underlying rows (below) — most are legitimate,
by-design behavior the engine is supposed to have; one class is a real,
previously-undiscovered bug.

## Interpretation, failure by failure

### Not bugs — expected, by-design divergence

**Established (Andrea $69.27, Eduardo $14.51) — HOLD tolerance-band
drift.** `generateMovesForTicker` deliberately doesn't move a `HOLD`
ticker (Andrea's AVGO, Eduardo's QS) that's within ±1 percentage point
(`MODEL_WEIGHT_TOL`) of its model weight — that's the anti-thrash
tolerance band. A ticker sitting anywhere inside that band has a real
current value that isn't *exactly* its model weight, so summing resolved
targets (which for a HOLD is just current value) drifts from the bucket
target by up to roughly 1 point of portfolio value ($300ish on these
accounts). This is the intended behavior, not a bug — the script's flat $2
tolerance is just tighter than the engine's own 1-point HOLD tolerance.

**Speculative — Luis ($1,897.98).** Luis's SPWR is at 76% of portfolio
(!), trimmed via `TRIM_CAP` down to its 35% hard cap — not down to its
proportional model weight. `TRIM_CAP` (priority 2) exists specifically to
enforce the Type A/B hard-cap ceiling independent of the bucket-level
target; the graduated exit ratchet brings a position the rest of the way
toward model weight over subsequent quarters, not in one pass (see
CLAUDE.md's "Graduated exit ratchet" design decision). So after this
session's recommended trim, SPWR alone will still sit at $2,591.85 — nearly
3× the entire $925.66 Speculative bucket target — and that's correct,
intentional, single-pass behavior, not a reconciliation bug.

**ETF (Andrea -$15.75, Eduardo +$0.01) and Eduardo's Crypto (+$206.95) —
same HOLD tolerance-band mechanism as Established**, applied to fixed-
target tickers sitting within their own tolerance band of their per-ticker
cap (Andrea's QQQ/TMFC at ~9.97-9.98% vs a 10% cap; Eduardo's BTC at 5.64%
vs a 5% cap, both within the 1-point band). Small, expected, not a bug.

**Crypto/Commodities — Luis (-$740.53 each, both buckets $0 achievable).**
No crypto/commodity ticker held at all, and the shortfall ($740.53) is
below `minPositionDollar` (the floor below which the engine won't bother
recommending a position) — so no "(unallocated)" row gets generated,
by design. The gap is real but deliberately unsurfaced at this account
size. Not a bug, though arguably worth a UI note some day that a bucket
target can be structurally unreachable below the position-size floor.

### A real bug, found by this script

**Crypto/Commodities — Andrea (-$479.87 Crypto, -$838.31 Commodities) and
Eduardo (-$871.91 Commodities).** This is a genuine, previously-
undiscovered gap in the fixed-target-bucket "(unallocated)" shortfall
calculation (`server/routes/moves.js`, the `fixedBuckets` block fixed two
sessions ago in `wrap-ups/allocation-admin-gap-fix-out.md`).

`generateFixedTargetMove` has **no ADD branch** — a fixed-target ticker
(ETF/commodity/crypto) only ever gets `TRIM` (if over its cap) or `HOLD`
(otherwise). It never gets pulled *up* to its cap. But the "(unallocated)"
shortfall is computed as `bucketTarget - achievableValue`, where
`achievableValue` sums `fixedTargetMap.get(ticker.id)` — **each held
ticker's per-ticker CAPPED target**, not its actual current value. That's
correct when a ticker is *over* its cap (a real `TRIM` move will land it
exactly there), but wrong when a ticker is *under* its cap (nothing will
ever move it there — it just `HOLD`s at its current, lower value).

Concretely, Andrea's BTC sits at 3.47% against a 5% per-ticker cap. The
shortfall calc assumes BTC contributes its full 5% ($1,572.72) toward the
Crypto bucket, so it only flags the *remaining* gap to the 10% bucket
target ($1,572.72 more, via "Crypto (unallocated)"). But BTC will actually
stay at 3.47% ($1,092.84) — nothing moves it up — so the TRUE gap is
$1,572.72 (BTC's own shortfall to its cap) + $1,572.72 (the unallocated
slice) = the full bucket target is essentially unaddressed by any
generated move. Same mechanism for Andrea's SIVR (Commodities) and
Eduardo's SIVR (Commodities).

**This was not fixed this session** — the assignment was to build and
verify the reconciliation script, not to fix bugs it finds. Flagging this
clearly as a candidate for a dedicated fix session: the "(unallocated)"
`achievableValue` calc should use `Math.min(currentValue, fixedTargetMap
capped target)` per held ticker, not the capped target unconditionally —
mirroring how the TRIM_CAP-vs-model-weight distinction already works
correctly for individual equities.

## Files added

- `server/scripts/verifyAllocationMath.js`
- `server/scripts/verify-allocation-math.sh`

No existing files modified (the sanity-check edit to `server/routes/moves.js`
was reverted before committing — confirmed via `git diff` showing no
changes to that file).
