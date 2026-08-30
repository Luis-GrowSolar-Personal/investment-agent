# Recon: do Andrea's and Eduardo's Full Reset candidate pools diverge for a real reason?

## Verdict up front

**No unexplained divergence.** The two Full Resets are running against an
**identical target model** — same six Established winners at 4.6% each
(NVDA, ORCL, GOOGL, MSFT, AMD, AVGO) and the same three Speculative
winners at 9.2% each (QS, ENVX, AMPX), for **both** owners. Every visible
difference in the output rows is produced downstream of candidate
selection, by exactly two mechanisms:

1. **different starting holdings** (Andrea already holds 6/6 Established
   winners, Eduardo holds 2/6 → his four "brand-new ADD" rows are the
   four slots she has already filled), and
2. **the ±1.0 percentage-point `MODEL_WEIGHT_TOL` dead band** — which is
   what actually suppresses Andrea's GOOGL/AMD/MSFT rows, not "she's in
   the No-action list."

The candidate pools themselves **did not diverge at all** this time. That
is the meaningful difference from task #38: back then the pools genuinely
differed (AMD/AVGO missing for Eduardo, ENVX missing for Andrea). Post-
#39/#40 they converge, which is the expected result of those fixes.

The working hypothesis is therefore **confirmed, but it was incomplete** —
see §3, where "already held near target" turns out to be the wrong
explanation for GOOGL and MSFT specifically (they're held *above* target,
not near it, and are silent because of the tolerance band).

One **incidental, unrelated real finding** surfaced while checking the
reverse direction (§6): `splitBucketTarget` divides a bucket target by a
ticker count that includes zero-cap tickers, which is currently cutting
Andrea's QQQ and TMFC targets from 10% to 6.25% and generating two
TRIM rows that are artifacts. Flagged, **not fixed**, per recon
discipline. It does not touch candidate selection and does not affect the
verdict above.

---

## 0. What was actually compared

Both Full Resets are frozen snapshots living in `MovesCache` (one row per
owner — there is no snapshot history table, so these are the only
persisted copies):

| Owner | `computedAt` | `isFreshStart` | totalPortfolioValue |
|---|---|---|---|
| Andrea Morales | 2026-08-24T13:49:49Z | `true` | $30,250.35 |
| Eduardo Morales | 2026-08-24T18:17:06Z | `true` | $30,652.83 |

**~4h27m apart, same day** — not "a few days apart" as the prompt's
Context states. Minor premise correction; it makes the shared-snapshot
question in check #1 easier to answer cleanly, not harder.

## 1. Are both resets scoring against the same analysis snapshot? — YES

`Analysis` latest-per-ticker, as of both `computedAt` timestamps:

| Ticker | latest `Analysis.createdAt` | callDate | thesisHealth | trajectory | action | tier |
|---|---|---|---|---|---|---|
| GOOGL | 2026-07-29 | 2026-07-22 | Strengthening | softening | Add | established |
| AMD | 2026-08-05 | 2026-08-04 | Strengthening | softening | Add | established |
| MSFT | 2026-07-30 | 2026-07-29 | Strengthening | softening | Add | established |
| ENVX | 2026-08-13 | 2026-08-12 | Strengthening | softening | Add | speculative |
| AVGO | 2026-06-14 | 2026-06-03 | Strengthening | softening | Add | established |
| AMPX | 2026-08-07 | 2026-08-05 | Strengthening | softening | Add | speculative |
| QS | 2026-07-29 | 2026-07-22 | Intact | softening | Hold | established\* |
| NVDA | 2026-05-21 | 2026-05-20 | Strengthening | stable | Add | established |
| ORCL | 2026-06-14 | 2026-06-10 | Strengthening | softening | Add | established |
| AMZN | 2026-07-31 | 2026-07-30 | Strengthening | softening | **Trim** | established |
| EOSE | 2026-08-07 | 2026-08-05 | Intact | softening | **Trim** | speculative |
| SPWR | 2026-07-29 | 2026-07-28 | **Weakening** | deteriorating | Trim | speculative |
| BTC / QQQ / TMFC / SIVR / BYDDY | *no Analysis rows* | — | — | — | — | — |

\* QS's `Analysis.tier` says `established` but `Ticker.tierOverride =
'speculative'` wins in `barbellSide()` — which is why QS lands in the
Speculative pool for both owners. Same as documented in the #39 wrap-up;
unchanged.

**The newest relevant `Analysis` row is 2026-08-13 — eleven days before
either reset, and nothing at all was ingested in the 4h27m gap between
them.** Both resets scored the identical snapshot for every ticker in the
divergence. Data-timing is fully ruled out as an explanation.

## 2. Confirming the pools are genuinely identical (not just similar)

Derived from the profile settings, which are **identical between Andrea
and Eduardo on every allocation-relevant field**:

```
minPositionDollar 1000 | maxPositions null | cashReservePct 0.05
estSpecRatio 0.5 | equitiesTargetPct 0.55 | etfTargetPct 0.25
cryptoTargetPct 0.10 | commoditiesTargetPct 0.05
```

(They differ only on `enoughNumber` — 35M vs 33M — and on the *ordering*
of `domainsOfInterest`, whose member sets are identical. Neither feeds
candidate selection or sizing.)

That gives est pool = 55% × 0.5 = 27.5%, spec pool = 27.5%. Observed
targets reconcile exactly:

- 27.5% ÷ 6 established slots = 4.58% → **4.6% observed, both owners**
- 27.5% ÷ 3 speculative slots = 9.17% → **9.2% observed, both owners**

And the winning slates match ticker-for-ticker:

| Pool | Winners (both owners) | Andrea holds | Eduardo holds |
|---|---|---|---|
| Established (6 × 4.6%) | NVDA, ORCL, GOOGL, MSFT, AMD, AVGO | **all 6** | NVDA, ORCL only |
| Speculative (3 × 9.2%) | QS, ENVX, AMPX | all 3 | all 3 |

Eduardo's four "brand-new Established ADD" rows are **MSFT, AVGO, GOOGL,
AMD at $1,410 each** — and $1,410 = 4.6% × $30,652.83 exactly. They are
the four slots Andrea has already filled. NFLX (rank 9, Type A) lost the
6-slot Established cut for **both** owners identically; ENVX/AMPX/QS
(rank 9/9/6) all fit the 3 Speculative slots for both. **No asymmetry in
who reached the ranking at all.**

## 3. Per-ticker verdict on the "already held near target" explanation

Using each reset's own `currentPct` (the frozen values the reset actually
computed against — Andrea's live positions have since drifted, so live
numbers would be the wrong comparison). Band = ±1.0pp
(`MODEL_WEIGHT_TOL`, `server/routes/moves.js:60`; applied at lines
786–787).

| Ticker | Andrea `currentPct` | target | delta | Andrea row | Explanation confirmed? |
|---|---|---|---|---|---|
| **GOOGL** | 4.78% | 4.6% | **+0.18** | no action | ⚠️ **Not "near target below" — held slightly ABOVE target.** Silent because +0.18 < +1.0 band. Correct behavior, wrong stated reason. |
| **MSFT** | 4.78% | 4.6% | **+0.18** | no action | ⚠️ Same as GOOGL — held above target, inside the band. |
| **AMD** | 4.23% | 4.6% | −0.37 | no action | ✅ Confirmed — genuinely below target, but −0.37 is inside the band, so no ADD. |
| **ENVX** | 10.98% | 9.2% | **+1.78** | **TRIM_MODEL $539** | ✅ Confirmed — exceeds the band on the high side, hence TRIM not ADD, exactly as the prompt described. |

For contrast, the two Andrea rows that *did* fire prove the band is the
operative mechanism and not a $-minimum:

- **AVGO** 2.90% vs 4.6% = **−1.70pp** → exceeds band → **ADD $514.77**.
  Note $514 is well under `minPositionDollar` ($1,000) and an ADD was
  still generated — `minPositionDollar` gates *new* positions and
  bucket-level rows, not top-ups of held ones. So "below $1,000" is not
  what silenced GOOGL/AMD/MSFT.
- Andrea's NVDA (4.39%, −0.21) and ORCL (4.55%, −0.05) are silent by the
  same band rule.

Eduardo's side of each, for completeness: he holds **zero** GOOGL / MSFT
/ AMD / AVGO (confirmed against his `Position`/`Lot` rows), so each is a
new open at the full 4.6%; his ENVX is 3.77% (−5.43pp) → **ADD $1,663**,
the mirror image of Andrea's TRIM.

**So: the divergence is fully explained, but the mechanism is the
tolerance band as much as the holdings.** Anyone reading "she already
holds them near target" off the No-action list would be right about
GOOGL/MSFT by accident — they're above target, not below it.

## 4. Global-eligibility gate (#38/#39/#40) — no regression

Re-read `recon-freshstart-candidate-pool-divergence-out.md`,
`fix-freshstart-global-status-eligibility-out.md` (commit `ff2ca55`) and
`fix-normal-path-global-status-eligibility-out.md` (commit `50adb1e`)
first, then checked the current file.

Both fixes are **intact**. `grep -n "status: 'watchlist'" server/routes/moves.js`
returns **nothing** — neither the freshStart nor the normal-path candidate
query filters on the global `Ticker.status` any more:

```
1422:        where: { inScope: { not: false } },        # freshStart candidates (Fix 1)
1676:      where: { inScope: { not: false } },          # normal-path candidates
1449:        if (g.ticker.inScope === false) continue;  # freshStart held-loop (Fix 2)
186-191:  estGroup/specGroup/unclassified inScope filters  # normal-path held analog
```

That this is genuinely working is visible in the data, not just the code:
AMD, AVGO, GOOGL and MSFT all carry `Ticker.status = 'portfolio'`
(Andrea's holdings promoted them globally), and they nonetheless appear
as **live ranked candidates for Eduardo, who holds none of them** — which
is precisely the case that was broken pre-`ff2ca55`. No re-emergence in a
different form found.

`inScope` gating also still behaves: BYDDY (`inScope: false`, held by
Eduardo) is routed to **EXIT**, never competing for a slot — Fix 2's
intended behavior.

## 5. Funding/routing commits (`0021bcc`, `a93edb1`) — boundary held

Diffed `ce1e725..a93edb1` (covering `844e3c7`, `7a75576`, `0021bcc`,
`a93edb1`) against every candidate-selection identifier:

```
git diff ce1e725..a93edb1 -- server/routes/moves.js | grep '^[-+]' | \
  grep -iE "fsUniverse|fsEligible|scoreCandidate|barbellSide|rankScore|sizeSide|findMany|inScope|status:|targetEst|estPoolPct|MODEL_WEIGHT_TOL|computeIndividualModelWeights"
```

Only five hits, **all additive reads, no selection logic touched**:

```
+ * Conviction uses scoreCandidate() — the same signal the engine already uses to
+      for (const c of fsOpenCandidates) newPositionMeta.set(c.symbol, {side: c.side, score: c.rankScore});
+    for (const c of candidates)        newPositionMeta.set(c.symbol, {side: c.side, score: c.rankScore});
+        side:  barbellSide(ticker, a),
+        score: scoreCandidate(a, ticker.type),
```

`newPositionMeta` is declared at line 1125, **populated at 1486/1763 —
after `sizeSide()` has already chosen the winners** — and consumed only at
line 1915 to order funding. It cannot influence which tickers were
selected. The remaining hunks in those commits are `committed`-parameter
threading through `buildAddRouting`/`buildNewPositionRouting` call sites.
**The routing/selection boundary the prompt asked about genuinely held.**

## 6. Reverse direction — nothing Andrea-side is unexplained

Cross-checked every symbol in each owner's output against their actual
`Position`/`Lot` rows in both directions.

**Tickers Andrea's reset touches:** AMZN (EXIT), EOSE (EXIT), BTC (TRIM),
QQQ (TRIM), ENVX (TRIM), QS/AVGO/AMPX (ADD), + 3 bucket-level rows.
**Every one is also touched by Eduardo's reset**, except that ENVX is his
ADD vs her TRIM (holdings, §3) and AVGO is his new-open vs her top-up
(holdings, §2). There is **no ticker Andrea's reset acts on that
Eduardo's ignores.** Eduardo additionally EXITs SPWR and BYDDY — Andrea
holds neither (confirmed: no position rows), so nothing to act on.

Eduardo's TRIMs of NVDA (16.31%), ORCL (12.30%) and TMFC (11.35%) have no
Andrea counterpart because her NVDA (4.39%), ORCL (4.55%) and TMFC
(10.14% vs 10%) are all inside the band. Explained.

**Two held tickers absent from Andrea's snapshot entirely — investigated
and explained:** she currently holds **QGRW ($1,519)** and **SOLZ
($1,530)** — together ~10% of her portfolio — and neither appears as a
move, hold, or advisory in her frozen reset. This looked like a silent
drop of the kind #38 found. It isn't:

```
QGRW  Ticker.createdAt = 2026-08-24T14:12:30.457Z
SOLZ  Ticker.createdAt = 2026-08-24T14:12:30.407Z
Andrea's reset computedAt = 2026-08-24T13:49:49.368Z
```

**Both tickers were created 23 minutes AFTER her reset was computed** (a
Schwab sync created them, along with the positions). They did not exist
when the snapshot was frozen. Absence is correct.

I verified rather than assumed what happens now that they do exist, by
running a live uncached `computeMovesPayload(owner, {freshStart: true})`
for both owners. Result confirms §2 still holds (both owners still show
identical 4.6%/9.2% targets and the same winning slate) — and both QGRW
and SOLZ now surface as `TRIM_MODEL @ targetPct 0`, correctly gated as
out-of-scope.

### Incidental finding worth a fix prompt (NOT fixed, NOT a divergence bug)

The same live run exposed a real, separate defect in
`splitBucketTarget` (`server/routes/moves.js:1224-1233`):

```js
const evenShare = bucketTargetPct / groups.length;
for (const g of groups) {
  const configuredCap = ownerCapMap.get(g.ticker.id) ?? g.ticker.capPercent ?? null;
  map.set(g.ticker.id, configuredCap != null ? Math.min(evenShare, configuredCap) : evenShare);
}
```

`groups.length` counts **every held ticker in the bucket, including ones
whose effective cap is 0**. QGRW and SOLZ both have `capPercent = 0` and
`inScope = false`, and both land in Andrea's ETF bucket. So:

- **Before** (2 ETFs held): `evenShare` = 25 ÷ 2 = 12.5 → QQQ
  `min(12.5, 10) = 10%`, TMFC `min(12.5, 10) = 10%`. Matches her frozen
  snapshot exactly.
- **Now** (4 ETFs held): `evenShare` = 25 ÷ 4 = 6.25 → QQQ **6.25%**,
  TMFC **6.25%**, QGRW `min(6.25, 0) = 0%`, SOLZ `0%`.

The two zero-cap tickers each claim a 6.25% share of the 25% ETF target
and are then capped to 0%, so **12.5% of the ETF target is stranded**
while QQQ and TMFC are cut from 10% to 6.25% — which is what generates
the `TRIM_MODEL:QQQ` and `TRIM_MODEL:TMFC` rows in the live run. Those two
trims are artifacts of the divisor, not real overweights.

Scoped for a fix without re-investigation: `splitBucketTarget` should
exclude zero-effective-cap (and/or `inScope: false`) groups from
`groups.length` before computing `evenShare`, so the bucket target
divides only among tickers actually eligible to hold it. Note the same
function is used for the crypto and commodity buckets (lines 1236-1237),
so the fix applies to all three. Andrea's caps for QQQ/TMFC (10/10) come
from `OwnerTickerConfig` and are **identical to Eduardo's**, so this is
not owner-specific — it will bite any owner who acquires an unclassified
ticker that maps into a fixed-target bucket. Verified this is *not* a
divergence cause: it postdates both snapshots and is unrelated to
candidate selection.

Adjacent, lower-priority observation for Luis: QGRW and SOLZ are sitting
at ~10% of Andrea's portfolio with `inScope: false`, `capPercent: 0`,
`tierOverride: null`, `status: 'watchlist'` — i.e. never classified after
the sync created them. They'll keep being trimmed to zero until
classified. That's a data-hygiene call, not a code bug.

---

## Direct answers to the prompt's questions

1. **Same analysis snapshot for both resets?** Yes. Newest relevant
   `Analysis` row is 2026-08-13, eleven days before either reset; nothing
   ingested in the 4h27m gap. Data timing explains nothing here.
2. **"Already held near target" confirmed for every divergence ticker?**
   Confirmed for **AMD** and **ENVX**. For **GOOGL** and **MSFT** the
   *outcome* is correct but the *stated reason* is wrong — both are held
   slightly **above** target (+0.18pp), silenced by the ±1.0pp band, not
   "near target from below."
3. **#38/#39/#40 eligibility gate regressed?** No. Both fixes intact; no
   `status: 'watchlist'` filter anywhere in `moves.js`; verified
   behaviorally by AMD/AVGO/GOOGL/MSFT (`status: 'portfolio'`) reaching
   Eduardo's candidate pool.
4. **Reverse direction unexplained?** No. No ticker Andrea's reset acts
   on is untouched by Eduardo's. The two Andrea holdings missing from her
   snapshot (QGRW, SOLZ) postdate it by 23 minutes.
5. **Did `0021bcc`/`a93edb1` alter candidate selection?** No. Their only
   contact with selection identifiers is a read-only `newPositionMeta`
   map populated after `sizeSide()` and consumed for funding order.

**Is there any unexplained divergence between Andrea's and Eduardo's Full
Reset candidate pools? NO.** The pools are identical; all output
differences trace to holdings plus the ±1.0pp tolerance band.

## What was deliberately NOT done

- **No code changed.** Investigation only, per the prompt.
- The `splitBucketTarget` zero-cap divisor defect (§6) is **flagged, not
  fixed** — it's a real bug but outside this recon's question, and it
  affects live recomputes rather than the snapshots under comparison.
- QGRW/SOLZ classification (`inScope`/`capPercent`/`tierOverride`) left
  untouched — Luis's call.
- No `verify-allocation-math.sh` run: no code changed, so there is no
  before/after to compare.

## Follow-up commands for Luis

```bash
# The two frozen Full Reset snapshots actually compared here:
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
const { PrismaClient } = require('@prisma/client'); const p = new PrismaClient();
p.movesCache.findMany().then(rs => { for (const r of rs)
  console.log(r.owner, r.computedAt.toISOString(), 'freshStart=' + r.payload.isFreshStart,
    (r.payload.moves||[]).map(m => m.moveType + ':' + (m.symbol||'[bucket]') + '@' + m.targetPct).join(', '));
  return p.\$disconnect(); });
"
```

```bash
# Confirm the #39/#40 eligibility fixes are still in place (expect: no output):
grep -n "status: 'watchlist'" server/routes/moves.js
```

```bash
# Reproduce the splitBucketTarget dilution (expect QQQ and TMFC at 6.25, QGRW/SOLZ at 0):
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  node -e "
require('./routes/moves.js').computeMovesPayload('Andrea Morales',
  { bypassWinnerProtection: true, freshStart: true })
  .then(pl => console.log([...(pl.moves||[]), ...(pl.holds||[])]
    .filter(m => ['QQQ','TMFC','QGRW','SOLZ'].includes(m.symbol))
    .map(m => m.moveType + ' ' + m.symbol + ' cur=' + m.currentPct + ' tgt=' + m.targetPct)));
"
```
