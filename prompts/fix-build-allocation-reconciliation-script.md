# Build: automated allocation reconciliation check (replace manual screenshot verification)

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-build-allocation-reconciliation-script-out.md`. State up
front what was built, where, how to run it, and paste its actual output
from running it against every real owner in production data. Write for
someone reading cold later who needs to know how to use this script
without re-deriving what it does.

## Context

This session, Luis and Cowork have repeatedly hand-verified that
`computeMovesPayload`'s bucket-level targets (Established, Speculative,
ETF, Crypto, Commodities) reconcile with the sum of the individual moves
it generates — by screenshotting the Admin panel, the Allocation tab, and
the Recommended Moves tab, then manually adding up numbers. That process
found four real bugs (stale cache, a cash-scaling design flaw, a
contradictory scarcity-row framing bug, and a ratchet-vs-model-weight
mismatch — see `wrap-ups/*.md` in this repo for the full history if
useful context, but you don't need to re-read all of them to build this).
It's time-consuming and Luis wants it automated instead of repeated by
hand every time a change is made to the allocation engine.

## What to build

A script, runnable as a single `.sh` file in the repo (something like
`server/scripts/verify-allocation-math.sh` — a thin wrapper that sets
`DATABASE_URL` from `.env` the same way other commands in this repo's
`CLAUDE.md` do, and invokes a companion Node script that does the actual
work, e.g. `server/scripts/verifyAllocationMath.js`), that:

1. **Loads every `OwnerProfile`** in the database (not just Andrea/
   Eduardo/Luis — this should generalize to any current or future owner).

2. For each owner, calls `computeMovesPayload(owner, { bypassWinnerProtection: true })`
   directly (exported from `server/routes/moves.js` — this is the
   function Cowork's recon sessions have been calling directly all
   session; no HTTP/auth layer needed).

3. **For each of the six buckets** (Established, Speculative, ETF,
   Crypto, Commodities, Cash), reconstruct what the bucket's total
   *should* resolve to from the individual moves/holds the payload
   actually generated, and compare it against `payload.allocation.buckets`'
   `targetValue` for that bucket. The reconciliation rule, learned the
   hard way this session:

   - **For Established/Speculative** (the barbell equity buckets): sum,
     across every ticker classified into that side (held, new-open, AND
     held-but-out-of-scope/`HOLD`), that ticker's **actual resolved move
     target** — not a recomputed "ideal" model weight. This matters
     specifically for tickers on a `TRIM_RATCHET`/`TRIM_CAP` path, whose
     displayed target is NOT the raw model weight (see
     `wrap-ups/recon-spec-achievable-gap-out.md` for exactly why — a
     ticker's ratchet target can differ from its model weight by
     hundreds of dollars, and using the wrong one was a real bug found
     this session). For a `HOLD` (including out-of-scope tickers), the
     "resolved target" is just its unchanged current value. Then add any
     "Established/Speculative Equities (unallocated)" scarcity-gap row's
     `dollarAmount`, if one exists for that side. This total should equal
     the bucket's `targetValue`.
   - **For ETF/Crypto/Commodities** (fixed-target buckets): sum each held
     ticker's resolved target (from `splitBucketTarget`'s per-ticker
     capped value, reflected in that ticker's move) plus the
     "(unallocated)" row's `dollarAmount` if one exists. Should equal the
     bucket's `targetValue`.
   - **For Cash**: no reconciliation needed against individual moves —
     just confirm `targetValue` matches `cashReservePct × totalPortfolioValue`
     directly.

   Use a small tolerance (e.g. $2) to allow for `.toFixed(2)` rounding
   noise across many summed figures — don't flag sub-$2 differences as
   failures.

4. **Probe the actual payload shape before hardcoding field names.** This
   codebase's move objects have accumulated several fields across this
   session (`isBucketLevel`, `isScarcityGap`, `bucket`, `tier`, `symbol`,
   `targetValue`, `dollarAmount`, `moveType`, etc.) — read the current
   `computeMovesPayload` source directly rather than assuming the field
   names/shapes described above are exactly right; this document
   describes the *intent* of the check, not a guaranteed-accurate field
   reference. Run it against one owner first and inspect the raw payload
   JSON to confirm you're reading the right fields before writing the
   full reconciliation logic.

5. **Print a clear pass/fail report per owner per bucket** — owner name,
   bucket label, target value, reconstructed achievable value, difference,
   PASS or FAIL. Exit code `0` if everything passes (within tolerance)
   across all owners, non-zero if anything fails — so this can eventually
   be wired into a pre-deploy check or CI, not just run manually.

## Verify it actually catches things

Before considering this done, sanity-check that the script's logic is
real and not just "always passes": temporarily reintroduce one of the
already-fixed bugs from this session in a scratch copy of the relevant
function (e.g. sum raw model weight instead of resolved target for
Speculative) and confirm the script reports a FAIL with a sensible
dollar delta, then revert that change. Don't skip this step — a
reconciliation script that can't actually detect the bug class it was
built for isn't useful, and this is the cheapest way to prove it works
before trusting it.

## Document how to run it

In the wrap-up, include the exact command Luis/Cowork should run going
forward, e.g.:

```bash
./server/scripts/verify-allocation-math.sh
```

## Commit and push

You have real local git access — commit and push this yourself, Luis
doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "Add automated allocation reconciliation script (server/scripts/verify-allocation-math.sh)"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without `./wrap-ups/fix-build-allocation-reconciliation-script-out.md`
existing — include the script's real output run against every current
owner, not just a claim that it works.
