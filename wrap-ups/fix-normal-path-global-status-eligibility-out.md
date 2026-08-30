# Fix: normal (non-freshStart) watchlist-candidate eligibility had the same global-`Ticker.status` bug

## Fix up front

`server/routes/moves.js`, two changes, both non-`freshStart`-only code
paths:

1. **Line ~1441-1443** (the normal-path new-open candidate query): no
   longer filters on `status: 'watchlist'`. Now pulls every `inScope`
   ticker, scoped per-owner by the existing `!byTicker.has(wt.id)`
   filter — identical shape to the `freshStart` fix in
   `wrap-ups/fix-freshstart-global-status-eligibility-out.md`.
2. **`computeIndividualModelWeights` (line ~183-188)**: the held-ticker
   analog of that session's Fix 2. Out-of-scope held tickers
   (`inScope === false`) are now folded into the same zero-weight
   bucket as `barbellSide === null` ("unclassified") tickers, instead
   of silently receiving a real, non-zero model weight. Previously an
   out-of-scope held ticker still got Principle-9 funding priority
   toward that weight; now it gets 0% and is correctly funneled to a
   HOLD-advisory row with `targetPct: 0`.

Commit `50adb1e`, pushed to `dev`.

```diff
-  const estGroup  = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'est');
-  const specGroup = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'spec');
-  const unclassified = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === null);
+  const estGroup  = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'est'  && g.ticker.inScope !== false);
+  const specGroup = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === 'spec' && g.ticker.inScope !== false);
+  const unclassified = groups.filter(g => barbellSide(g.ticker, g.latestAnalysis) === null || g.ticker.inScope === false);
...
     const watchlistTickers = (await prisma.ticker.findMany({
-      where: { status: 'watchlist', inScope: { not: false } },
+      where: { inScope: { not: false } },
     })).filter(wt => !byTicker.has(wt.id));
```

## 1. Premise check before editing

Confirmed the query was still exactly where the freshStart wrap-up
flagged it (line ~1438-1440 as of this session, shifted by 6 lines
from the ~1432 the recon originally cited — the freshStart-fix session
added comment lines above it). Query shape unchanged: `status:
'watchlist', inScope: { not: false }`, filtered by
`!byTicker.has(wt.id)` — same pattern as the already-fixed `freshStart`
query, confirming Luis's read that this is the identical bug, not a
superficially-similar one.

## 2. `buildCapitalFlow` coupling check (per the prompt's caution)

The prompt asked to confirm eligibility (which tickers exist as
candidates) and funding priority (Principle 9 — existing positions
funded before new opens) are genuinely separate mechanisms before
editing, and to stop and report if they turned out to be more coupled
than assumed.

Traced it directly: `buildCapitalFlow(trimMoves, addUses, promUses,
freeCash)` is called once (line ~1688) as
`buildCapitalFlow(trimMoves, addMoves, [], freeCash)` — `promUses` is
always `[]` in this codebase currently. `addMoves` is a plain filter
of `allMoves` (moves already generated upstream by
`generateMovesForTicker`/the new-open candidate loop). `buildCapitalFlow`
itself does no ticker lookups, no `status`/`inScope` filtering, and no
re-derivation of eligibility — it only orders and allocates already-
built move rows by `usePriority` (`addUses` at priority 1, `promUses` at
priority 2). Confirmed: the eligibility-query fix only changes which
tickers appear in `allMoves` in the first place; `buildCapitalFlow`'s
ordering runs unchanged and downstream of that. No additional coupling
found — the prompt's assumption held, so no `buildCapitalFlow` changes
were made.

## 3. Held-loop `inScope` check — found missing, fixed

Checked whether the normal path's held-ticker treatment
(`computeIndividualModelWeights`, which produces `modelWeights` used to
size TRIM/HOLD/ADD moves for currently-held tickers) had the same
missing `inScope` check that freshStart's Fix 2 addressed. It did not:
`estGroup`/`specGroup` were built purely from `barbellSide`, with no
scope filter, so an out-of-scope held ticker still received a real,
non-zero model weight and — per Principle 9 — got funding priority
alongside every other held position. Fixed as shown above by folding
`inScope === false` tickers into the zero-weight `unclassified` bucket,
the same effect Fix 2 achieved for `freshStart`'s held loop, using the
mechanism this path already has (weight 0 == "doesn't compete/doesn't
get funded"), rather than duplicating freshStart's separate
"exclude-from-consideration-entirely" approach.

## 4. Verification: AMD / Eduardo concrete case

AMD is held by Andrea, not by Eduardo — `Ticker.status` was
`'portfolio'` (Andrea's Schwab sync promoted it), which hid it from
Eduardo's normal-path new-open candidates before this fix.

**Before** (confirmed via `git stash` + direct call, no HTTP):

```
computeMovesPayload('Eduardo Morales', { bypassWinnerProtection: true, freshStart: false })
→ p.moves.filter(m => m.symbol === 'AMD')  ===  []
```

AMD did not appear anywhere in Eduardo's normal-mode candidate list —
same absence pattern as the freshStart bug.

**After:**

```json
{
  "moveType": "ADD",
  "symbol": "AMD",
  "tier": "established",
  "targetPct": 4.3,
  "hardCapPct": 50,
  "dollarAmount": 1373,
  "targetValue": 1373,
  "isNewPosition": true,
  "reason": "New position — established pool, rank score 10"
}
```

AMD is now a real, ranked ADD candidate for Eduardo in the normal flow
— rank score 10, sized to $1,373 (4.3% of portfolio) within its 50%
Type-B hard cap. Whether it actually wins funding against other
open/held candidates is Principle 9's call (funding priority), which
this fix deliberately did not touch — confirmed above.

## 5. BYDDY-style held-and-out-of-scope verification

BYDDY: held by Eduardo, `inScope: false`, `status: 'watchlist'`.

**Before:**

```json
{ "symbol": "BYDDY", "currentPct": 0.85, "targetPct": 3.93, "currentMktValue": 270.24 }
```

BYDDY had a real, non-zero `targetPct` (3.93% model weight) despite
being out of the circle of competence — it was competing for and
potentially receiving Principle-9 funding priority just because
Eduardo already held it.

**After:**

```json
{ "symbol": "BYDDY", "currentPct": 0.85, "targetPct": 0, "currentMktValue": 270.24 }
```

`targetPct` is now `0` — BYDDY gets no model weight and no funding
priority, correctly treated the same as any other out-of-scope held
position, shown as a HOLD-advisory row (`currentPct: 0.85, targetPct:
0`) rather than a funded target.

## 6. Reconciliation (`verify-allocation-math.sh`), all three owners, before/after

Ran with `git stash`/`git stash pop` to get a true before/after on
this session's diff alone (i.e., starting from the already-committed
`freshStart` fix as the baseline).

**Normal-path rows — the only ones this fix could plausibly move:**

| Owner | Bucket | Before | After | Note |
|---|---|---|---|---|
| Luis | Established | PASS, $0 | PASS, $0 | unchanged |
| Luis | Speculative | FAIL, $1,573.36 | FAIL, $1,573.36 | unchanged — pre-existing, unrelated |
| Andrea | Established | PASS, $0 | PASS, $0 | unchanged |
| Andrea | Speculative | PASS, $0 | PASS, $0 | unchanged |
| Andrea | ETF | FAIL, $14.58 | FAIL, $14.58 | unchanged — pre-existing, unrelated |
| Eduardo | Established | FAIL, $6.53 | FAIL, $5.53 | **shifted ~$1**, explained below |
| Eduardo | Speculative | PASS, $0 | PASS, $0 | unchanged |
| Eduardo | Crypto | FAIL, $155.04 | FAIL, $155.04 | unchanged — pre-existing, unrelated |

**Eduardo's Established shift ($6.53 → $5.53) explained:** AMD and
AVGO are now real, ranked new-open candidates for Eduardo (previously
invisible), which changes the composition of `candidates` fed into
`sizeSide` for the remaining established slots. This shifts the same
kind of small per-candidate rounding noise documented in the
`freshStart` wrap-up (§4 there) by about a dollar — a byproduct of
which tickers now compete, not a new defect. No bucket flipped from
PASS to FAIL, or vice versa, anywhere for any owner. The pre-existing
FAILs (Luis Speculative, Andrea ETF, Eduardo Crypto) are byte-for-byte
identical before and after — confirmed unrelated to this change.

**`freshStart` rows — confirmed completely unaffected**, byte-for-byte
identical before and after, for all three owners (Andrea's freshStart
Established/Speculative $30.79/$32.05 diffs and Eduardo's
$31.86/$31.93 diffs — the same pre-existing rounding characteristic
flagged in the prior wrap-up — are untouched, as expected, since this
fix only edits the normal-path query and
`computeIndividualModelWeights`, which `freshStart` mode doesn't call
for held-ticker sizing).

## What was NOT done

- No `buildCapitalFlow` changes — confirmed unnecessary (§2 above).
- No changes to `freshStart` mode's own logic — already fixed in the
  prior session; confirmed unaffected by this one.
- The pre-existing reconciliation failures (Luis Speculative, Andrea
  ETF, Eduardo Crypto, and the `freshStart`-section rounding drift) —
  unrelated to either fix, left as-is per this prompt's scope.

## Follow-up / verification commands for Luis

```bash
# Re-run the reconciliation check any time:
./server/scripts/verify-allocation-math.sh

# Confirm AMD is a live candidate for Eduardo in the normal flow:
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
const { computeMovesPayload } = require('./routes/moves.js');
computeMovesPayload('Eduardo Morales', { bypassWinnerProtection: true, freshStart: false })
  .then(p => console.log(JSON.stringify(p.moves.filter(m => m.symbol === 'AMD'), null, 2)));
"

# Confirm BYDDY no longer gets funding priority for Eduardo:
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
const { computeMovesPayload } = require('./routes/moves.js');
computeMovesPayload('Eduardo Morales', { bypassWinnerProtection: true, freshStart: false })
  .then(p => console.log(JSON.stringify((p.holds||[]).filter(m => m.symbol === 'BYDDY'), null, 2)));
"
```
