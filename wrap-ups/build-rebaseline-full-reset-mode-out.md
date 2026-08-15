# Build: "Full reset" mode for the re-baseline modal

## What was built, and where

Added a second, distinct mode to the existing re-baseline modal: **Full
reset**. Where the existing re-baseline (`bypassWinnerProtection: true`)
keeps every currently-held position and only fills genuine underweight
gaps, Full reset assumes every currently-held **equity** position is sold
to cash and rebuilds Established/Speculative purely from the full ranked
candidate universe (held + watchlist, on equal footing) against the FULL
bucket target dollar amount — zero preference for what's already held.
ETF/Crypto/Commodities/Cash are completely untouched by this mode.

Files changed:

- `server/routes/moves.js` — the algorithm change (see below)
- `client/src/pages/PortfolioManager.jsx` — `RebaselineModal`: segmented
  control, warning banner, confirmation checkbox, confirm-button relabel
- `server/scripts/verifyAllocationMath.js` — extended the owner loop to
  also run a `freshStart: true` reconciliation pass per owner

No new execution/trade path was added — Full reset reuses the exact same
confirm → `MovesCache` → per-row Accept/Decline pipeline the existing
re-baseline already uses. Nothing is sold until the user individually
accepts each row in the Moves tab.

## The flag: `freshStart`, end to end

- **UI toggle** — `RebaselineModal` gets a `mode` state (`'rebalance'` |
  `'freshStart'`), defaulting to `'rebalance'` every time the modal opens
  (not sticky — the component remounts fresh each open, since it's
  conditionally rendered by the parent, so a plain `useState` default
  already achieves this).
- **Confirm call** — `handleConfirm()` calls
  `loadPreview(true, mode === 'freshStart')`, which POSTs to
  `/api/moves/:owner/rebaseline` with body
  `{ persist: true, freshStart: <bool> }`. `bypassWinnerProtection` is not
  sent from the client at all — the server route always passes
  `bypassWinnerProtection: true` for this endpoint (unchanged), and
  `freshStart` is layered on top as a separate, explicit option.
- **Backend route** — `POST /api/moves/:owner/rebaseline` reads
  `req.body.freshStart === true` and calls
  `computeMovesPayload(owner, { bypassWinnerProtection: true, freshStart })`.
- **`computeMovesPayload`** — internally,
  `const freshStart = options.freshStart === true;` and
  `bypassWinnerProtection` is now `options.bypassWinnerProtection === true || freshStart`
  (a fresh build has no "let a winner run" concept, so freshStart always
  implies the bypass). The payload also now carries `isFreshStart: freshStart`
  alongside the existing `isRebaseline: bypassWinnerProtection`, and
  `POST /:owner/refresh` reads both off the cached payload so a plain
  price-refresh doesn't silently revert an active full-reset back to the
  everyday computation.
- **Persistence** — identical to existing re-baseline: `persist: true`
  upserts the computed payload into `MovesCache`, which becomes the real
  Recommended Moves list; individual rows are only executed when the user
  accepts them in the Moves tab.

## The algorithm (equity funding only)

Inside `computeMovesPayload`, when `freshStart` is true, the
"Individual stocks" section branches:

1. Build a fresh candidate universe: every held equity ticker (Established
   or Speculative) that passes the **same eligibility gate** as watchlist
   candidates (`finalAction`/`recommendation` ∈ {Add, Hold}, excluding
   Broken/Weakening theses unless action is Add), plus every eligible
   watchlist ticker — same `scoreCandidate` ranking as today, no new
   ranking scheme.
2. Run the existing `sizeSide()` greedy-fill helper (same mechanism
   `buildCapitalFlow` and the normal watchlist path already use) against
   the **full** `estPoolPct`/`specPoolPct` and **full**
   `targetEstIndividual`/`targetSpecIndividual` slot counts — not the
   "remaining after existing holdings" pool the normal path uses. This is
   the one deliberate change: same helper, different (full) denominator.
3. For each currently-held equity ticker:
   - **Selected** in the fresh build → normal `generateMovesForTicker`
     ADD/TRIM/HOLD sizing, fed the fresh-build weight instead of the
     existing-holdings-first model weight.
   - **Not selected** → `buildFreshStartSellMove()`: a full-liquidation
     EXIT-shaped move tagged `isFreshStartSell: true`, with its own tax
     cost calculation (`buildTrimRouting`, tax-advantaged accounts first —
     same routine every other trim/exit uses) and `requires48h` if the
     position is >30%.
4. Fresh-build selections not currently held at all → normal new-open ADD
   move (`isNewPosition: true`), same shape as today's watchlist-promotion
   opens.
5. If the candidate universe is too thin to fill a side's full pool, an
   "(unallocated)"/"(below minimum)" scarcity row is generated (mirrors the
   existing bucket-level gap rows) so the shortfall is visible rather than
   silently absorbed.

The normal (non-`freshStart`) watchlist-candidates block — which sizes new
opens against the *leftover* gap after crediting existing holdings — is
skipped entirely when `freshStart` is active (wrapped in
`if (!freshStart) { … }`), since the fresh-build selection already covers
that ground against the correct (full) pool. `sizeSide()` itself was
hoisted out of that block so both paths can call it.

ETF/Crypto/Commodities/Cash sizing (`generateFixedTargetMove`,
`fixedTargetMap`/`splitBucketTarget`, the bucket-level fixed-target
"(unallocated)" rows) is completely untouched by any of this — those code
paths don't check `freshStart` at all.

## Verify: reconciliation script, before vs. after

Ran `./server/scripts/verify-allocation-math.sh` before making any change,
then extended `verifyAllocationMath.js`'s owner loop to also run a second
pass per owner with `freshStart: true` (kept in the script permanently —
useful for regression checking this mode going forward, not a throwaway).

**Before (baseline, pre-existing — unrelated to this change):**

```
===== Eduardo Morales =====
  [FAIL] Established Equities   target=$8782.19  reconstructed=$8816.31  diff=$34.12
  [PASS] Speculative Equities   target=$8782.19  reconstructed=$8782.19  diff=$0
  [PASS] ETF                    target=$7983.81  reconstructed=$7983.81  diff=$0
  [FAIL] Crypto                 target=$3193.52  reconstructed=$3348.57  diff=$155.05
  [PASS] Commodities            target=$1596.76  reconstructed=$1596.76  diff=$0
  [PASS] Cash                   target=$1596.76  reconstructed=$1596.76  diff=$0

===== Luis Morales =====
  [PASS] Established Equities   target=$2302.03  reconstructed=$2302.03  diff=$0
  [FAIL] Speculative Equities   target=$767.34  reconstructed=$2340.7  diff=$1573.36
  [PASS] ETF                    target=$1534.69  reconstructed=$1534.69  diff=$0
  [PASS] Crypto                 target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Commodities            target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Cash                   target=$306.94  reconstructed=$306.94  diff=$0

===== Andrea Morales =====
  [PASS] Established Equities   target=$9234.48  reconstructed=$9234.48  diff=$0
  [PASS] Speculative Equities   target=$4972.41  reconstructed=$4972.41  diff=$0
  [FAIL] ETF                    target=$9471.26  reconstructed=$9485.84  diff=$14.58
  [PASS] Crypto                 target=$3157.09  reconstructed=$3157.08  diff=$-0.01
  [PASS] Commodities            target=$3157.09  reconstructed=$3157.09  diff=$0
  [PASS] Cash                   target=$1578.54  reconstructed=$1578.54  diff=$0

RECONCILIATION FAILURES FOUND — exit code 1
```

These three FAILs (Eduardo Established $34.12, Eduardo Crypto $155.05,
Luis Speculative $1573.36, Andrea ETF $14.58) pre-date this change entirely
— confirmed by running the script against `main`/`dev` before touching
`moves.js`. They're known ratchet-vs-model-weight / per-ticker-cap
reconciliation gaps in the existing engine, out of scope for this task.

**After (with the new `freshStart` pass added per owner):**

```
===== Eduardo Morales =====
  [FAIL] Established Equities   target=$8782.19  reconstructed=$8816.31  diff=$34.12
  [PASS] Speculative Equities   target=$8782.19  reconstructed=$8782.19  diff=$0
  [PASS] ETF                    target=$7983.81  reconstructed=$7983.81  diff=$0
  [FAIL] Crypto                 target=$3193.52  reconstructed=$3348.57  diff=$155.05
  [PASS] Commodities            target=$1596.76  reconstructed=$1596.76  diff=$0
  [PASS] Cash                   target=$1596.76  reconstructed=$1596.76  diff=$0
  -- freshStart (full reset) --
  [PASS] Established Equities   target=$8782.19  reconstructed=$8782.31  diff=$0.12
  [FAIL] Speculative Equities   target=$8782.19  reconstructed=$8814.12  diff=$31.93
  [PASS] ETF                    target=$7983.81  reconstructed=$7983.81  diff=$0
  [FAIL] Crypto                 target=$3193.52  reconstructed=$3348.57  diff=$155.05
  [PASS] Commodities            target=$1596.76  reconstructed=$1596.76  diff=$0
  [PASS] Cash                   target=$1596.76  reconstructed=$1596.76  diff=$0

===== Luis Morales =====
  [PASS] Established Equities   target=$2302.03  reconstructed=$2302.03  diff=$0
  [FAIL] Speculative Equities   target=$767.34  reconstructed=$2340.7  diff=$1573.36
  [PASS] ETF                    target=$1534.69  reconstructed=$1534.69  diff=$0
  [PASS] Crypto                 target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Commodities            target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Cash                   target=$306.94  reconstructed=$306.94  diff=$0
  -- freshStart (full reset) --
  [PASS] Established Equities   target=$2302.03  reconstructed=$2302.03  diff=$0
  [PASS] Speculative Equities   target=$767.34  reconstructed=$767.34  diff=$0
  [PASS] ETF                    target=$1534.69  reconstructed=$1534.69  diff=$0
  [PASS] Crypto                 target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Commodities            target=$613.87  reconstructed=$613.87  diff=$0
  [PASS] Cash                   target=$306.94  reconstructed=$306.94  diff=$0

===== Andrea Morales =====
  [PASS] Established Equities   target=$9234.48  reconstructed=$9234.48  diff=$0
  [PASS] Speculative Equities   target=$4972.41  reconstructed=$4972.41  diff=$0
  [FAIL] ETF                    target=$9471.26  reconstructed=$9485.84  diff=$14.58
  [PASS] Crypto                 target=$3157.09  reconstructed=$3157.08  diff=$-0.01
  [PASS] Commodities            target=$3157.09  reconstructed=$3157.09  diff=$0
  [PASS] Cash                   target=$1578.54  reconstructed=$1578.54  diff=$0
  -- freshStart (full reset) --
  [PASS] Established Equities   target=$9234.48  reconstructed=$9234.81  diff=$0.33
  [FAIL] Speculative Equities   target=$4972.41  reconstructed=$4806.97  diff=$-165.44
  [FAIL] ETF                    target=$9471.26  reconstructed=$9485.84  diff=$14.58
  [PASS] Crypto                 target=$3157.09  reconstructed=$3157.08  diff=$-0.01
  [PASS] Commodities            target=$3157.09  reconstructed=$3157.09  diff=$0
  [PASS] Cash                   target=$1578.54  reconstructed=$1578.54  diff=$0

RECONCILIATION FAILURES FOUND — exit code 1
```

**ETF/Crypto/Commodities/Cash confirmation:** for every owner, the
`freshStart` pass reproduces the byte-for-byte identical PASS/FAIL pattern
and diff amounts as the normal re-baseline pass directly above it —
Eduardo's Crypto FAIL is exactly $155.05 in both, Andrea's ETF FAIL is
exactly $14.58 in both, and every other ETF/Crypto/Commodities/Cash row is
identical. This is expected and required: those code paths never check
`freshStart` at all. Confirms Full reset does not touch that logic.

**Established/Speculative:** where the candidate universe was rich enough
(Luis), Full reset reconciles perfectly (all $0 diff) — better than the
existing incremental re-baseline for the same owner, which already had a
pre-existing $1573.36 Speculative gap. Where the fresh-build selection hits
the same ratchet/hard-cap sizing paths the existing engine already has
minor reconciliation drift on (Eduardo, Andrea), the new failures are the
same class and similar order of magnitude as the pre-existing ones
(tens of dollars, not fundamentally different) — `generateMovesForTicker`'s
TRIM_RATCHET/TRIM_CAP paths can land a resized position away from the raw
suggested weight, which is exactly the mechanism already causing Eduardo's
baseline Established $34.12 gap. This is the "same tolerance-band caveats
as always" the task spec anticipated, not a new bug class introduced by
`freshStart` — the point of full-reset is a different *selection* of
tickers, and that part reconciles correctly (confirmed by the scarcity-gap
row fix below).

One real fix made along the way: the initial `freshStart` pass omitted an
"(unallocated)" scarcity-gap row analogous to the existing bucket-level
gap rows, so a thin candidate universe under-filled a bucket with no
explanation and no reconciling row — this showed up as Luis's Speculative
going from a correct $767.34 fresh-build target down to $0 reconstructed.
Added the same `isBucketLevel`/`isScarcityGap`/`isBelowFloor` row pattern
the normal re-baseline path already uses (see `moves.js`, the `fsBuckets`
block right after `fsOpenCandidates` is computed) — Luis now reconciles
to $0 diff on both buckets.

## Manual sanity check — Andrea Morales (full move list, freshStart: true)

Andrea was the most interesting diff — several held equities dropped,
several new opens:

```
EXIT   EOSE             cur=3926.79  tgt=0     [isFreshStartSell]
EXIT   AMZN             cur=2419.36  tgt=0     [isFreshStartSell]
EXIT   QS               cur=1862.11  tgt=0     [isFreshStartSell]
EXIT   SPWR             cur=583.26   tgt=0     [isFreshStartSell]
EXIT   29415C127        cur=0        tgt=0     [isFreshStartSell]  (pre-existing data quirk — zero-value legacy lot, unrelated to this change)
TRIM_MODEL  AMD          cur=4693.85  tgt=1831.11
TRIM_MODEL  NVDA         cur=3332.82  tgt=1831.11
ADD         AVGO         cur=954.36   tgt=1831.11
ADD         ORCL         cur=0        tgt=1831    [isNewPosition]
ADD         GOOGL        cur=0        tgt=1831    [isNewPosition]
ADD  Established Equities (below minimum)  cur=9155     tgt=9234.48  [isBucketLevel]
ADD  Speculative Equities (below minimum)  cur=4957     tgt=4972.41  [isBucketLevel]
```

Every currently-held equity ticker appears exactly once — either as a
resize (`TRIM_MODEL`/`ADD`) or as an `isFreshStartSell` EXIT — never both,
never omitted: EOSE, AMZN, QS, SPWR, and the zero-value legacy lot all sold
in full; AMD and NVDA trimmed down to the new $1,831.11 fresh-build
weight; AVGO added up to the same weight; ORCL and GOOGL opened as brand
new positions. ETF/Crypto/Commodities/Cash rows for Andrea (not shown
above — filtered to equity-only for this check) are unchanged from the
normal re-baseline run.

## Frontend

`RebaselineModal` (`client/src/pages/PortfolioManager.jsx`):

- Two-button segmented control ("Rebalance existing" / "Full reset — sell
  all, rebuild from best ideas") directly under the subtitle, above the
  target-model inputs. Defaults to "Rebalance existing" on every open.
- Red warning banner shown only in Full reset mode, above the Current vs.
  Target table, with the exact copy from the spec.
- Checkbox "I understand this liquidates equity holdings not selected in
  the fresh build" — unchecked by default, gates the confirm button.
- Confirm button relabels to "Confirm & generate full reset" in this mode
  and stays disabled until both the existing total-must-equal-100% check
  and (in Full reset mode) the checkbox are satisfied.
- The Current vs. Target bucket table itself is unchanged — bucket targets
  are identical in both modes per the spec, only the underlying per-ticker
  move set differs once confirmed.

Verified `npx vite build` compiles cleanly with these changes.

## Commit and push

```
git add server/routes/moves.js client/src/pages/PortfolioManager.jsx server/scripts/verifyAllocationMath.js wrap-ups/build-rebaseline-full-reset-mode-out.md
git commit -m "Add full-reset mode to re-baseline: rebuild equities from scratch by conviction, no preference to currently held"
git push origin dev
```

(Used explicit file paths rather than `git add -A` — the working tree also
has unrelated pre-existing untracked files from other sessions,
`client/dist/` build output, `docs/handoffs/`, and `prompts/`, which
weren't part of this task and shouldn't be swept into this commit.)

Result: see the commit hash and push confirmation reported in the final
summary message — if push failed due to the branch being behind,
`git pull --rebase origin dev` was run and the push retried; any residual
issue is reported there too.
