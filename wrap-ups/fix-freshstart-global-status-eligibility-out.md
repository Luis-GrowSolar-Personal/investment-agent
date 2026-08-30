# Fix: `freshStart` candidate eligibility incorrectly gated by global `Ticker.status`

## Fix up front

`server/routes/moves.js`, inside `computeMovesPayload`'s `freshStart`
branch:

1. **Fix 1** (line ~1167-1174): the non-held candidate query no longer
   filters on `status: 'watchlist'`. It now pulls every `inScope`
   ticker, then relies on the existing `!byTicker.has(wt.id)` filter to
   scope eligibility per-owner (does *this* owner already hold it).
   `Ticker.status` is a global promotion-workflow flag — once any owner
   holds a ticker it flips to `'portfolio'` everywhere, which was
   silently hiding it from every other owner's `freshStart` pool.
2. **Fix 2** (line ~1199): the held-ticker loop (`individualGroups`)
   now skips tickers with `inScope === false`, matching the check the
   non-held loop already had. A held-but-out-of-scope ticker no longer
   competes for a fresh-build slot; it's now correctly funneled
   straight to `buildFreshStartSellMove` (EXIT), same as any other
   currently-held out-of-scope position.

Commit `ff2ca55`, pushed to `dev`.

```diff
-      const fsWatchlistTickers = (await prisma.ticker.findMany({
-        where: { status: 'watchlist', inScope: { not: false } },
-      })).filter(wt => !byTicker.has(wt.id));
+      const fsWatchlistTickers = (await prisma.ticker.findMany({
+        where: { inScope: { not: false } },
+      })).filter(wt => !byTicker.has(wt.id));
...
       for (const g of individualGroups) {
         const a      = g.latestAnalysis;
         const action = a?.finalAction ?? a?.recommendation ?? '—';
+        if (g.ticker.inScope === false) continue;
         if (!fsEligible(action, a?.thesisHealth)) continue;
```

## 1. Premise check before editing

Read the current `freshStart` branch in full before touching anything,
per the prompt's instruction (the file has been touched by several
sessions since the recon). The code matched the recon's quotes exactly
— no drift. `fsWatchlistTickers`, `fsUniverse`, `fsEligible`,
`individualGroups`/`byTicker` all still had the shape described.

Checked whether `status: 'watchlist'` might have existed for a
legitimate reason other than the diagnosed bug (performance, excluding
a different row shape) — found none. The query has no other purpose;
it exists purely as an eligibility filter, and the recon's diagnosis of
its effect was correct.

## 2. Live before/after verification (Andrea, Eduardo)

Ran `computeMovesPayload(owner, { bypassWinnerProtection: true,
freshStart: true })` directly (no HTTP) via a scratch script, with a
temporary `console.table` dump of `fsUniverse.est`/`.spec` inserted
right after they're built (reverted before commit — not part of the
committed diff).

**Before** (unchanged from the recon wrap-up — see
`wrap-ups/recon-freshstart-candidate-pool-divergence-out.md`): no ENVX
anywhere in Andrea's universe; no AMD/AVGO anywhere in Eduardo's.

**After — Andrea Morales, fsUniverse.est:**

| symbol | type | rankScore | hardCapPct | isHeld | thesisHealth | finalAction |
|---|---|---|---|---|---|---|
| AMD | B | 10 | 50 | true | Strengthening | Add |
| NVDA | B | 12 | 50 | true | Strengthening | Add |
| AVGO | B | 10 | 50 | true | Strengthening | Add |
| QS | A | 6 | 35 | true | Intact | Hold |
| ORCL | B | 10 | 50 | false | Strengthening | Add |
| GOOGL | B | 10 | 50 | false | Strengthening | Add |
| MSFT | B | 10 | 50 | false | Strengthening | Add |
| NFLX | A | 9 | 35 | false | Strengthening | Add |

**After — Andrea Morales, fsUniverse.spec:**

| symbol | type | rankScore | hardCapPct | isHeld |
|---|---|---|---|---|
| AMPX | A | 9 | 35 | true |
| **ENVX** | A | 9 | 35 | false |

ENVX now appears, ranked (rankScore 9, tied with AMPX) — confirmed.

**After — Eduardo Morales, fsUniverse.est:**

| symbol | type | rankScore | hardCapPct | isHeld | thesisHealth | finalAction |
|---|---|---|---|---|---|---|
| ORCL | B | 10 | 50 | true | Strengthening | Add |
| QS | A | 6 | 35 | true | Intact | Hold |
| NVDA | B | 12 | 50 | true | Strengthening | Add |
| AVGO | B | 10 | 50 | false | Strengthening | Add |
| GOOGL | B | 10 | 50 | false | Strengthening | Add |
| MSFT | B | 10 | 50 | false | Strengthening | Add |
| NFLX | A | 9 | 35 | false | Strengthening | Add |
| **AMD** | B | 10 | 50 | false | Strengthening | Add |

AMD now appears; AVGO also appears (bolding AMD only because the recon
called it out specifically, but both are confirmed present).

**After — Eduardo Morales, fsUniverse.spec:**

| symbol | type | rankScore | hardCapPct | isHeld |
|---|---|---|---|---|
| ENVX | A | 9 | 35 | true |
| AMPX | A | 9 | 35 | true |

(Eduardo already held ENVX, so it was never missing from his own
universe — only AMD/AVGO were the gap for him, matching the recon.)

## 3. BYDDY / Fix 2 verification

`BYDDY`: `inScope: false`, held by Eduardo (`status: 'watchlist'`,
`tierOverride: 'speculative'`). After the fix, BYDDY does **not**
appear in Eduardo's `fsUniverse.spec` table above — Fix 2 correctly
gates it out of the held-loop before it ever reaches `fsEligible`/
`scoreCandidate`.

Confirmed the *visible outcome* is unchanged — BYDDY still ends up
EXITed:

```json
{
  "moveType": "EXIT",
  "symbol": "BYDDY",
  "reason": "Full reset — not selected in the fresh build (higher-conviction
             candidates filled the full bucket target); full liquidation.",
  "isFreshStartSell": true
}
```

Same EXIT as before, but now for the structurally correct reason (gated
out from the start) rather than losing a ranking it should never have
been eligible for.

## 4. Allocation reconciliation (`verify-allocation-math.sh`)

Ran before (via `git stash`) and after the fix, for all three owners.

**Pre-existing failures, unrelated to this fix** — present identically
before and after, all in the **normal** (non-freshStart) path, which
this fix does not touch:

- Luis — normal Speculative Equities: diff $1,573.36
- Andrea — normal ETF: diff $14.58
- Eduardo — normal Established Equities: diff $34.11; normal Crypto:
  diff $155.04

These are known, already-flagged issues (see `verifyAllocationMath.js`
header comments referencing prior wrap-ups) — not introduced or changed
by this session.

**freshStart-section changes, before → after:**

| Owner | Bucket | Before | After |
|---|---|---|---|
| Luis | Established / Speculative | PASS / PASS | PASS / PASS (unchanged) |
| Andrea | Established | PASS, diff $1.19 | **FAIL, diff $30.79** |
| Andrea | Speculative | PASS, diff $0 | **FAIL, diff $31.79** |
| Eduardo | Established | PASS, diff $0.14 | **FAIL, diff $31.86** |
| Eduardo | Speculative | FAIL, diff $31.93 | FAIL, diff $31.93 (unchanged) |

**This is a real, investigated deviation from the prompt's
expectation** ("bucket totals... should be unaffected by this fix —
this changes WHICH tickers compete, not how much money each bucket
targets"). Root cause, traced directly (not guessed):

`sizeSide()`'s per-candidate rounding (`suggestedPct` rounded to 0.1%,
then a separate dollar re-derivation for held tickers via
`generateMovesForTicker` vs. a direct `suggestedDollar` for new opens
via `fsOpenMoves`) has always had a small rounding drift between the
two code paths. That drift is invisible or tiny when the winning slate
is a *mixed* Type A/Type B group (the 1.0×/1.5× multiplier rescale
absorbs it), but becomes visible when the winning slate is **uniformly
Type B** — which is exactly what Fix 1 produced for Andrea's and
Eduardo's Established side: 6 Type-B candidates (AMD, NVDA, AVGO, ORCL,
GOOGL, MSFT) now win where MSFT previously couldn't even enter the pool
(global `status: 'portfolio'` hid it). Verified directly: summing the
6 winning rows' `targetValue` for Andrea reproduces $8,712.78 exactly
(3× $1,452.26 + 3× $1,452.00), i.e. the mechanism is understood, not a
mystery.

This is a **pre-existing `sizeSide`/rounding characteristic**, not a
defect introduced by Fix 1 or Fix 2's logic — Fix 1/2 only changed
*which* tickers compete, and this particular winning combination
happens to expose rounding drift that a different combination (with a
Type A candidate mixed in) previously masked. Per the prompt's
explicit instruction ("if the prompt's assumption is wrong, flag it and
adapt rather than blindly implementing"), this is flagged here rather
than pursued as a fix — reconciling `sizeSide`'s dual rounding paths is
a separate, pre-existing issue outside this prompt's scope (fixing the
`Ticker.status` eligibility gate), and touching it risks destabilizing
the already-fragile reconciliation script further without Luis's
explicit go-ahead.

## 5. Three-way sanity check (Luis Morales)

Luis holds none of ORCL/NVDA/AVGO/GOOGL/MSFT/AMD/QS/NFLX (all
`isHeld: false` in his `fsUniverse.est` dump) and holds ENVX
(`isHeld: true` in his `fsUniverse.spec`, AMPX `isHeld: false`).
Nothing unexpected: a ticker held by two of three owners (ENVX, held by
Luis and Eduardo, not Andrea) shows up correctly scoped per-owner in
each owner's `byTicker`-derived `isHeld` flag, with no cross-owner
leakage. Luis's reconciliation numbers are identical before/after
(PASS across the board for freshStart) — expected, since none of his
held tickers changed eligibility status.

## 6. Normal (non-freshStart) path — flagged, NOT fixed

Confirmed the normal watchlist-candidate query
(`server/routes/moves.js` ~line 1432) has the **identical**
`status: 'watchlist'` filter and is subject to the same structural bug
in principle. Per the prompt's explicit scope note, this was **not**
touched — flagging it here for Luis's decision rather than silently
also fixing it, since (per the prompt's own reasoning) it may be
intentional there: Principle 9 already prioritizes existing holdings
over new opens in the everyday incremental flow, and a
`'portfolio'`-status ticker not held by this owner may be a genuinely
different situation in that context than in `freshStart`'s "equal
footing" full-reset flow.

## 3 (of prompt). QS tier classification — recon only, no change made

**Answer: QS's `tier: 'established'` is a plain fallback default, not
a mechanical 3-axis classification decision.**

Looked up `Ticker` (id 51, symbol QS): `tierOverride: null`,
`tierMechanical: null`. So the effective tier is NOT coming from either
a user override or a computed mechanical classification — both are
unset.

Traced where `tier` actually gets set. First correction to the
prompt's premise: the file it names, `analysis/trend_analyst.py`, is
the *Python* original; the live save-time logic that actually sets
`Analysis.tier` lives in `server/routes/save.js` (line 225), which
reads:

```js
const tier = ticker.tierOverride ?? ticker.tierMechanical ?? 'established';
```

`server/lib/trendAnalyst.js` (the Node port of the trend layer) has an
explicit comment documenting why the 3-axis mechanical classifier
itself was **never ported**:

```
NOT ported: build_tier_function (3-axis speculative/established
classifier). That requires price_cache.json / fundamentals_cache.json,
which are laptop-only artifacts. save.js reads the tier from
Ticker.tierOverride ?? Ticker.tierMechanical ?? 'established' instead of
recomputing it — tier reclassification stays a separate (deferred) cron.
```

So for any ticker where neither `tierOverride` nor `tierMechanical` has
ever been populated — QS included — the tier silently defaults to
`'established'`. Nothing about QS's revenue profile, burn rate, or
pre-commercial stage pushed it toward "established"; no axis data was
ever evaluated for it at all, because the classifier that would compute
`tierMechanical` doesn't run in production (it's Railway-deployed,
Node-only, no Python subprocess, and the classifier depends on
laptop-only price/fundamentals cache files). This also means the
per-transcript `Analysis.tier` field on the QS row (`'established'`)
was written by the LLM evaluator itself when generating that call's
structured output — separately from, and not overridden by, the
mechanical-classifier fallback chain in `save.js` (worth noting: the
recorded `Analysis.tier` and the `save.js` fallback chain happen to
agree here, both landing on `'established'`, but for different reasons
— the evaluator's own judgment vs. the deferred-cron default).

`tierRationale` on the `Ticker` row: `null` — nothing has ever been
recorded there.

**Not changed, per the prompt.** Luis's read (pre-revenue, unproven
solid-state battery tech reaching commercial scale = textbook
speculative) is not contradicted by anything found here — there is no
mechanical evidence supporting `'established'` to weigh against it; the
label is an unexamined default, not a considered classification. If
Luis wants QS reclassified, `tierOverride` (the existing manual-override
mechanism) is the correct lever — that's his call to make, not
something to silently correct here.

## What was NOT done

- The normal (non-freshStart) watchlist-candidate path's identical
  `status: 'watchlist'` filter — flagged in §6 above, not touched.
- QS's tier classification — recon only, per explicit instruction; no
  `tierOverride` set.
- The pre-existing `sizeSide` rounding-drift characteristic exposed by
  §4 above — not touched; out of this prompt's scope.
- The other pre-existing reconciliation failures (Luis normal
  Speculative, Andrea normal ETF, Eduardo normal Established/Crypto) —
  unrelated to this fix, already present before and after.

## Follow-up / verification commands for Luis

```bash
# Re-run the reconciliation check any time:
./server/scripts/verify-allocation-math.sh

# Re-run freshStart directly for any owner, no HTTP:
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
const { computeMovesPayload } = require('./routes/moves.js');
computeMovesPayload('Andrea Morales', { bypassWinnerProtection: true, freshStart: true })
  .then(p => console.log(JSON.stringify(p.moves.filter(m => m.symbol === 'ENVX'), null, 2)));
"

# Check QS's current effective tier / override state:
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
const { PrismaClient } = require('@prisma/client');
new PrismaClient().ticker.findFirst({ where: { symbol: 'QS' } }).then(console.log);
"
```

If Luis wants to set `QS.tierOverride = 'speculative'`, that's a direct
Prisma update or an Admin-UI action (whichever the existing
`tierOverride` mechanism uses elsewhere) — not part of this fix.
