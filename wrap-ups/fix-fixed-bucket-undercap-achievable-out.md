# Fix: fixed-target bucket "(unallocated)" shortfall overstated achievable value for under-cap tickers

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)

## The fix, up front

In `computeMovesPayload`'s `fixedBuckets` block (`server/routes/moves.js`),
`achievableValue` used to sum each held ticker's **capped target**
unconditionally (`fixedTargetMap.get(ticker.id)`). Changed to
`Math.min(currentValue, cappedTarget)` per ticker:

```js
const achievableValue = b.groups.reduce((s, g) => {
  const cappedTarget = (fixedTargetMap.get(g.ticker.id) ?? 0) / 100 * totalPortfolioValue;
  const tickerCurrentValue = positionMetrics(g.positions, totalPortfolioValue).mktValue;
  return s + Math.min(tickerCurrentValue, cappedTarget);
}, 0);
```

Rationale (unchanged from the diagnosis in `wrap-ups/fix-build-allocation-reconciliation-script-out.md`):
`generateFixedTargetMove` has no `ADD` branch — a fixed-target ticker only
ever gets `TRIM` (if over its own cap) or `HOLD` (otherwise), so nothing
ever moves it *up*. The capped target is only actually reachable when a
ticker is over cap (a real `TRIM` lands it exactly there); when under cap,
its current value is what will actually remain. `Math.min` picks whichever
one genuinely applies.

## Verified with the reconciliation script

**Before** (`./server/scripts/verify-allocation-math.sh`):
```
===== Andrea Morales =====
  [FAIL] ETF                    target=$9436.29  reconstructed=$9420.54  diff=$-15.75
  [FAIL] Crypto                 target=$3145.43  reconstructed=$2665.56  diff=$-479.87
  [FAIL] Commodities            target=$3145.43  reconstructed=$2307.12  diff=$-838.31

===== Eduardo Morales =====
  [FAIL] Commodities            target=$1606.31  reconstructed=$734.4  diff=$-871.91
```

**After**:
```
===== Andrea Morales =====
  [PASS] ETF                    target=$9436.29  reconstructed=$9436.29  diff=$0
  [PASS] Crypto                 target=$3145.43  reconstructed=$3145.43  diff=$0
  [PASS] Commodities            target=$3145.43  reconstructed=$3145.43  diff=$0

===== Eduardo Morales =====
  [FAIL] Commodities            target=$1606.31  reconstructed=$734.4  diff=$-871.91   (unchanged — see below)
```

Andrea's Crypto and Commodities — the two buckets explicitly named in the
prior session's bug report — now reconcile exactly. **Bonus**: Andrea's ETF
also flipped from a small `-$15.75` FAIL to an exact PASS — that drift was
the same root cause (QQQ/TMFC sitting fractionally under their 10% cap;
the old calc assumed they'd reach it, the reconciliation script correctly
used their real current value, and now the engine's own calc agrees with
that instead of disagreeing by the sliver each was under-cap).

## Eduardo's Commodities does NOT flip to PASS — and it can't, without a separate, out-of-scope change

This was named in the bug report as a target for this fix, but the fix
doesn't (and structurally can't) resolve it, for a reason distinct from
the bug this fix targets:

Eduardo holds only SIVR in Commodities, at 2.29% against a 5% cap
(currentMktValue $734.40, no change from before). With the fix applied,
the corrected shortfall calculation now correctly computes `$1,606.31
(target) - $734.40 (achievable, SIVR's real current value) = $871.91` —
this is the CORRECT number now, whereas before the fix it was silently
computing something close to `$0` (the old code assumed SIVR would reach
its $1,606.31 cap, wiping out the apparent gap). **But `$871.91` is still
below `minPositionDollar`** (the $1,500 floor below which the engine
won't bother recommending a position), so no "Commodities (unallocated)"
row gets generated — exactly the same floor-suppression behavior already
documented for Luis's Crypto/Commodities buckets in
`wrap-ups/fix-build-allocation-reconciliation-script-out.md`. The
reconciliation script has no way to know a gap was intentionally
suppressed below the floor, so it keeps reporting a FAIL — correctly, in
the sense that the bucket genuinely won't reach its target via any move
the engine will generate, but this is now a **known, by-design**
divergence in the same category as Luis's case, not a bug in the
`achievableValue` calc this session fixed.

Whether floor-suppressed gaps like this should get some kind of $0-action
informational row (so they reconcile visibly instead of just vanishing) is
a real product question, but it's a change to the floor/threshold logic,
not to `achievableValue` — out of scope for this fix. Flagging for Luis
and Cowork to decide, not picking silently.

## No regressions — confirmed by rerunning the full script, not just the affected buckets

```
===== Eduardo Morales =====
  [FAIL] Established Equities   target=$8834.72  reconstructed=$8849.23  diff=$14.51   (unchanged — HOLD tolerance band, expected)
  [PASS] Speculative Equities   target=$8834.72  reconstructed=$8834.72  diff=$0
  [PASS] ETF                    target=$8031.56  reconstructed=$8031.57  diff=$0.01    (unchanged — rounding, expected)
  [FAIL] Crypto                 target=$3212.62  reconstructed=$3419.57  diff=$206.95  (unchanged — HOLD tolerance band, expected, not a target of this fix)
  [FAIL] Commodities            target=$1606.31  reconstructed=$734.4  diff=$-871.91   (unchanged for the floor reason above)
  [PASS] Cash                   target=$1606.31  reconstructed=$1606.31  diff=$0

===== Luis Morales =====
  [PASS] Established Equities   target=$2776.98  reconstructed=$2777  diff=$0.02
  [FAIL] Speculative Equities   target=$925.66  reconstructed=$2823.64  diff=$1897.98  (unchanged — TRIM_CAP-vs-model-weight, expected)
  [PASS] ETF                    target=$1851.32  reconstructed=$1851.32  diff=$0
  [FAIL] Crypto                 target=$740.53  reconstructed=$0  diff=$-740.53        (unchanged — below floor, expected)
  [FAIL] Commodities            target=$740.53  reconstructed=$0  diff=$-740.53        (unchanged — below floor, expected)
  [PASS] Cash                   target=$370.26  reconstructed=$370.26  diff=$0

===== Andrea Morales =====
  [FAIL] Established Equities   target=$9200.39  reconstructed=$9269.66  diff=$69.27   (unchanged — HOLD tolerance band, expected)
  [PASS] Speculative Equities   target=$4954.05  reconstructed=$4954.05  diff=$0
  [PASS] ETF                    target=$9436.29  reconstructed=$9436.29  diff=$0       ← fixed (bonus)
  [PASS] Crypto                 target=$3145.43  reconstructed=$3145.43  diff=$0       ← fixed (targeted)
  [PASS] Commodities            target=$3145.43  reconstructed=$3145.43  diff=$0       ← fixed (targeted)
  [PASS] Cash                   target=$1572.72  reconstructed=$1572.72  diff=$0

RECONCILIATION FAILURES FOUND — exit code 1
```

Every "expected FAIL" from the prior session's interpretation (HOLD
tolerance band, TRIM_CAP priority, sub-floor gaps) stayed exactly the same
size — none shifted, confirming this fix was scoped correctly and didn't
touch anything beyond the intended `achievableValue` calc. Two of the
three named target buckets flipped to exact PASS, plus one bonus (Andrea's
ETF); the third (Eduardo's Commodities) remains a FAIL for the
floor-suppression reason explained above, not a leftover bug.

## Files touched

- `server/routes/moves.js` (one calculation: `achievableValue` inside the
  `fixedBuckets` loop)

No schema/migration changes, no frontend changes — the corrected dollar
figures flow through to the Allocation tab and re-baseline modal
automatically.
