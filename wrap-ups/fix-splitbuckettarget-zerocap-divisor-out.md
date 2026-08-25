# Wrap-up: fix-splitbuckettarget-zerocap-divisor

**Status: fixed and verified live against the real DB.** The core premise was
correct. **One sub-instruction in the prompt (item 2, the `inScope` half) was
wrong and would have caused a severe regression — it was caught by the item-3
check, and deliberately NOT implemented.** Read that section.

## Premise check

Confirmed exactly as described. `server/routes/moves.js:1224-1234` (pre-fix):

```js
function splitBucketTarget(groups, bucketTargetPct) {
  const map = new Map();
  if (groups.length === 0) return map;
  const evenShare = bucketTargetPct / groups.length;   // ← no claimant filter
  ...
}
```

`groups.length` counted every held ticker in the bucket, including ones with a
zero effective cap that can never claim any of the target.

## The change

`server/routes/moves.js:1224-1252`. The divisor now counts only *claimants*:

```js
const capOf = g => ownerCapMap.get(g.ticker.id) ?? g.ticker.capPercent ?? null;
const claimants = groups.filter(g => capOf(g) !== 0);
const evenShare = claimants.length > 0 ? bucketTargetPct / claimants.length : 0;
```

`capOf` resolves the cap the same way the existing `configuredCap` line did
(ownerCapMap first, then `ticker.capPercent`, then null = uncapped), so a null
cap still counts as a claimant — only an explicit `0` is excluded. The per-ticker
loop below is unchanged, so **excluded tickers still get their own map entry and
their own move**, resolving to their own cap (0 → full exit). Item 3 of "What to
build" satisfied: this changes the divisor, not the row.

Applies to all three buckets by construction — ETF, Crypto and Commodities all
call this one shared function (lines 1246-1250), so there is no per-bucket
variant to keep in sync.

## ⚠ Deviation: `inScope` exclusion NOT implemented (prompt item 2 is wrong here)

The prompt asked me to consider excluding `inScope: false` tickers too, "apply
the same standard" as the #39/#40 eligibility gates. **I implemented it, it
failed catastrophically, and I reverted it.**

In these buckets `inScope: false` is the *norm*, not an exclusion signal:

| symbol | capPercent | inScope |
|---|---|---|
| BTC | 25 | **false** |
| SIVR | 25 | **false** |
| IBIT | 25 | **false** |
| SOLZ | 0 | **false** |
| QGRW | 0 | **false** |
| QQQ | 35 | true |
| TMFC | 5 | true |
| GLD | 25 | true |

`inScope` marks "outside the analyst's equity circle of competence — never
auto-add" (see `moves.js:835`, `canAdd`), not "cannot hold allocation". Filtering
on it emptied the Crypto and Commodities buckets entirely (`claimants.length` →
0 → `evenShare` 0), producing **full-exit TRIMs on real, correctly-configured
holdings** on both accounts:

```
-   HOLD  BTC   cur=4.44%  tgt=5.00%
+   TRIM_MODEL BTC  cur=4.44%  tgt=0.00%  amt=$1529  reason=BTC at 4.4% — over crypto allocation of 0%
-   HOLD  SIVR  cur=4.36%  tgt=5.00%
+   TRIM_MODEL SIVR cur=4.36%  tgt=0.00%  amt=$1502
-   HOLD  SOLZ  cur=4.53%  tgt=5.00%
+   TRIM_MODEL SOLZ cur=4.53%  tgt=0.00%  amt=$1562
```

That would have recommended liquidating Andrea's and Eduardo's entire crypto and
commodity sleeves. The shipped fix filters on **zero cap only**. The reasoning is
recorded in a comment at the call site so this isn't re-litigated later.

The prompt asked me to say explicitly whether the two conditions diverge in
practice: **they do, constantly** — every crypto/commodity ticker here is
`inScope: false` with a real nonzero cap. They are not near-synonyms.

## Second wrong premise (harmless)

The prompt says Andrea/Eduardo "will NOT visibly change ... because Luis already
manually gave QGRW and SOLZ real caps". True in effect, but the mechanism is
different from what's implied: QGRW's and SOLZ's **global** `Ticker.capPercent`
is still `0`. What Luis added were per-owner `OwnerTickerConfig` rows (QGRW 10,
SOLZ 5 for Andrea/Eduardo/Luis), and `ownerCapMap` takes precedence in `capOf`.
So the global 0 is still there and would still bite any owner without an
override. Worth knowing if a fourth owner is ever added.

## Verification

### Items 1-2 — before/after repro

No zero-cap holding exists live any more on any of the three owners (confirmed by
script), so I seeded one reversibly: set Andrea's `OwnerTickerConfig` for QGRW to
`capPercent: 0` (single field, no position writes), ran the dump against both the
stashed and fixed code, then restored it to 10.

```
===== BEFORE FIX (bug present) =====
  TRIM_MODEL   QGRW  cur=4.42%   tgt=0.00%   amt=$1522  reason=QGRW at 4.4% — over ETF target of 0%
  TRIM_MODEL   QQQ   cur=12.23%  tgt=8.33%   amt=$1342  reason=QQQ at 12.2% — over ETF target of 8%
  HOLD         TMFC  cur=8.92%   tgt=8.30%

===== AFTER FIX =====
  TRIM_MODEL   QGRW  cur=4.42%   tgt=0.00%   amt=$1522  reason=QGRW at 4.4% — over ETF target of 0%
  TRIM_MODEL   QQQ   cur=12.23%  tgt=10.00%  amt=$768   reason=QQQ at 12.2% — over ETF target of 10%
  HOLD         TMFC  cur=8.92%   tgt=10.00%
```

Divisor 3 → 2. QQQ's target returns from a diluted 8.33% to its true 10%, cutting
an unwarranted TRIM from $1342 to $768. TMFC returns from 8.30% to 10.00%. QGRW
still gets its own row, still `tgt=0.00%`, still a full-exit TRIM at the same
$1522 — unchanged, as required.

**DB restored.** Post-restore `OwnerTickerConfig` table re-queried and matches the
pre-experiment snapshot row for row.

### Item 3 — Andrea/Eduardo no-regression: PASS

`dumpMovesForOwner.js` for both owners, both normal and `--freshStart` (4 runs),
captured pre-fix and post-fix:

```
BYTE-IDENTICAL: Andrea_Morales.txt
BYTE-IDENTICAL: Andrea_Morales--freshStart.txt
BYTE-IDENTICAL: Eduardo_Morales.txt
BYTE-IDENTICAL: Eduardo_Morales--freshStart.txt
```

Re-run again after the DB restore — still byte-identical to the original
baseline. QQQ/TMFC/QGRW/SOLZ/BTC targets all unchanged.

### Item 4 — Crypto / Commodities

Covered by construction: one shared function, three call sites, no per-bucket
branch.

I also attempted a live Crypto repro (Andrea's SOLZ cap → 0 temporarily, then
restored to 5). **It produced no observable delta, and this is expected, not a
failure:** Andrea's crypto bucket is BTC + SOLZ against a 10% target, and BTC's
own owner cap is 5%. `Math.min(evenShare, 5)` yields 5% whether `evenShare` is
the diluted 5% or the undiluted 10%, so BTC's own cap binds below both and hides
the divisor change. SOLZ correctly showed `tgt=0.00%` with its own full-exit
TRIM in both runs. A bucket where the surviving members are capped *above* an
even split — which is the ETF case above — is required to see the delta.

### Items 5-6 — build and math baseline

- `node --check server/routes/moves.js` → clean
- `npx vite build` → `✓ built in 898ms` (only the pre-existing chunk-size warning)
- `./server/scripts/verify-allocation-math.sh` → **byte-identical before vs after
  the fix**, 11 FAILs both ways. The pre-existing task-#50 baseline failures
  (Eduardo Crypto $43.47, Eduardo freshStart Est/Spec, Luis Speculative $1870.79)
  are unrelated and untouched.

## Not done / still open

- **`smartDefaultBucket()` misclassification** — SOLZ (a Solana product) is
  bucketed `etf` rather than `crypto`. Explicitly out of scope per the prompt;
  still open. Note it is *also* why SOLZ appeared in the ETF bucket in the
  original incident, so the two bugs compounded.
- Task #77 (freshStart-vs-normal sizing divergence) — untouched.
- `annotateAddFunding` / cash / trim-proceeds ledgers — untouched.
- QGRW's and SOLZ's **global** `Ticker.capPercent` are still `0`. Left alone per
  "do not change caps/classifications", but see "Second wrong premise" — a new
  owner without per-owner overrides would inherit the zero. Now harmless to other
  holdings thanks to this fix, but those two tickers would themselves be
  full-exited.

## Follow-up commands

```bash
export DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-)
node server/scripts/dumpMovesForOwner.js "Andrea Morales" --symbols=QQQ,TMFC,QGRW
node server/scripts/dumpMovesForOwner.js "Eduardo Morales" --symbols=QQQ,TMFC,QGRW
bash ./server/scripts/verify-allocation-math.sh   # expect the same 11 baseline FAILs
```
