# Recon: why Andrea's and Eduardo's `freshStart` picks diverge despite identical settings

## Answer up front

**ENVX/AMD/AVGO/BYDDY vanish per-owner because `Ticker.status` is a
GLOBAL field, not per-owner** — once any owner is actually holding a
ticker, `Ticker.status` flips to `'portfolio'` for that ticker
everywhere, which silently drops it out of the `status: 'watchlist'`
query every OTHER owner's freshStart pool draws non-held candidates
from. An owner who doesn't hold that ticker gets it from neither path
(not in their own `byTicker`, not in the global watchlist query) — it's
a genuine eligibility bug, not intended behavior, even though it's easy
to mistake for something ticker-specific (thesis/domain) at first
glance. **The established-slot sizing divergence ($2,012 vs $1,341 for
Eduardo, uniform $1,736 for Andrea) is NOT a bug** — `sizeSide()`
weights every slot by a fixed Type A/B multiplier (B=1.5×, A=1.0×) off
the SAME base weight, identically for both owners; Andrea's top-5
happen to be all Type B, so the multiplier is invisible in her output.

## 1. The eligibility gate (freshStart candidate universe), quoted

`server/routes/moves.js`, inside `computeMovesPayload`, freshStart branch:

```js
const fsWatchlistTickers = (await prisma.ticker.findMany({
  where: { status: 'watchlist', inScope: { not: false } },
})).filter(wt => !byTicker.has(wt.id));
...
function fsEligible(action, thesisHealth) {
  if (!['Add', 'Hold'].includes(action)) return false;
  if (['Broken', 'Weakening'].includes(thesisHealth) && action !== 'Add') return false;
  return true;
}

// Held equities compete on equal footing with watchlist candidates —
// "no preference to what's currently held" (Luis, confirmed).
for (const g of individualGroups) {
  const a      = g.latestAnalysis;
  const action = a?.finalAction ?? a?.recommendation ?? '—';
  if (!fsEligible(action, a?.thesisHealth)) continue;
  const side = barbellSide(g.ticker, a);
  if (!side) continue;
  fsUniverse[side].push({ ... isHeld: true });
}
for (let i = 0; i < fsWatchlistTickers.length; i++) {
  const wt = fsWatchlistTickers[i];
  const a  = fsWatchlistAnalyses[i];
  if (!a) continue;
  const action = a.finalAction ?? a.recommendation ?? '—';
  if (!fsEligible(action, a.thesisHealth)) continue;
  const side = barbellSide(wt, a);
  if (!side) continue;
  fsUniverse[side].push({ ... isHeld: false });
}
```

`fsEligible` and `scoreCandidate`/`barbellSide` (below) are purely
global — they read only `Analysis` (latest per ticker) and
`Ticker.tierOverride`/`type`/`capPercent`. No `OwnerDecision`, no
`Position`, no per-owner watchlist flag is referenced inside the
scoring/eligibility logic itself:

```js
function barbellSide(ticker, latestAnalysis) {
  if (isETF(ticker))             return 'est';
  if (isCommodityOrCrypto(ticker)) return 'spec';
  const tier = ticker.tierOverride ?? latestAnalysis?.tier ?? null;
  if (tier === 'established')  return 'est';
  if (tier === 'speculative')  return 'spec';
  return null;
}

function scoreCandidate(a, type) {
  return (TRAJ_SCORE[a?.trajectory] ?? 0)
       + (HEALTH_SCORE[a?.thesisHealth] ?? 0)
       + (ACTION_SCORE[a?.finalAction ?? a?.recommendation] ?? 0)
       + (type === 'B' ? 2 : 1);
}
```

**So the scoring/eligibility conditions themselves are owner-agnostic,
exactly as designed.** The divergence isn't in the scoring function —
it's in *what set of candidates ever reaches it*, via the split
between the "held" loop (fed from `individualGroups`, i.e. this
owner's actual `byTicker`) and the "watchlist" loop (fed from a GLOBAL
`Ticker.status === 'watchlist'` query, filtered only by
`!byTicker.has(wt.id)`).

## 2. The actual owner-scoping mechanism (the bug)

`Ticker.status` ('watchlist' | 'portfolio') is a single column on the
shared `Ticker` row — not per-owner. Per the code's own comment
elsewhere in the file (line ~1425, normal watchlist path):

```js
// Ticker.status is global (shared across all owners), not owner-specific
// — a ticker can still say "watchlist" even after THIS owner has a real
// position in it (e.g. before the next Schwab-sync auto-promotion runs,
// or if another owner's sync hasn't touched it).
```

That comment flags the *stale* direction of the problem (still
'watchlist' after a promotion). The freshStart bug is the *opposite*
direction, and worse: once a ticker IS promoted to `'portfolio'`
(because SOME owner holds it), it's gone from the `status: 'watchlist'`
query for EVERY owner — including owners who never held it and would
otherwise be eligible watchlist candidates for it. Since the held-loop
only picks up tickers in `byTicker` (this owner's own positions), an
owner who doesn't hold a `'portfolio'`-status ticker gets it from
neither loop. It never enters `fsUniverse` at all — not ranked, not
rejected, just absent.

Verified directly against the DB:

```
ENVX   | status: portfolio | inScope: true  | held by: Luis Morales, Eduardo Morales
AVGO   | status: portfolio | inScope: true  | held by: Andrea Morales
AMD    | status: portfolio | inScope: true  | held by: Andrea Morales
BYDDY  | status: watchlist | inScope: false | held by: Eduardo Morales
```

- **ENVX**: `status='portfolio'` (Luis and Eduardo hold it). Andrea
  doesn't hold it → not in her `byTicker` → excluded from her held-loop
  → also excluded from her watchlist query (status isn't `'watchlist'`)
  → **never enters `fsUniverse` for Andrea at all.** Confirmed live
  (dump below): Andrea's `fsUniverse.est`/`.spec` contain no ENVX row
  whatsoever.
- **AVGO / AMD**: `status='portfolio'` (Andrea holds both). Eduardo
  doesn't hold either → same mechanism → **absent from Eduardo's
  `fsUniverse` entirely**, confirmed live below.
- **BYDDY**: different mechanism — `inScope: false`. It's excluded from
  the *global* watchlist query (`inScope: { not: false }`) for anyone
  who doesn't hold it, which is correct/intended (out-of-circle-of-
  competence tickers shouldn't surface as new-open candidates). But
  Eduardo holds it directly, so it still enters via the held-loop,
  which does **not** check `inScope` at all — held tickers bypass the
  scope gate entirely. That's a second, smaller inconsistency worth
  flagging: `inScope` is enforced for new-open candidates but not for
  already-held ones, so a ticker that's fallen out of the circle of
  competence still fights for a fresh-build slot if you happen to hold
  it, while it's invisible to any other owner. In Eduardo's case it
  lost anyway and was exited, so the net visible effect (an EXIT) looks
  "correct," but for the wrong structural reason — it's not exiting on
  ranking, it exits because nothing in fsEligible/sizeSide holds it
  back and it never had a chance to be favorably re-added since it's
  gated out for everyone else.

## 3. Live ranked candidate lists, both owners, side by side

Captured via a direct (temporary, reverted — no code changes were
committed) `console.table` dump inside the freshStart branch, then
calling:

```js
const { computeMovesPayload } = require('./server/routes/moves.js');
await computeMovesPayload('Andrea Morales', { bypassWinnerProtection: true, freshStart: true });
await computeMovesPayload('Eduardo Morales', { bypassWinnerProtection: true, freshStart: true });
```

**Andrea — fsUniverse.est (pre-sizeSide, full ranked pool):**

| symbol | type | rankScore | hardCapPct | isHeld | thesisHealth | finalAction |
|---|---|---|---|---|---|---|
| AMD | B | 10 | 50 | true | Strengthening | Add |
| NVDA | B | 12 | 50 | true | Strengthening | Add |
| AVGO | B | 10 | 50 | true | Strengthening | Add |
| QS | A | 6 | 35 | true | Intact | Hold |
| ORCL | B | 10 | 50 | false | Strengthening | Add |
| GOOGL | B | 10 | 50 | false | Strengthening | Add |
| NFLX | A | 9 | 35 | false | Strengthening | Add |

No ENVX row — confirms it never enters Andrea's candidate universe.

**Andrea — fsUniverse.spec:**

| symbol | type | rankScore | hardCapPct | isHeld |
|---|---|---|---|---|
| AMPX | A | 9 | 35 | true |

Only one speculative candidate exists in Andrea's entire universe —
that's why AMPX gets the whole speculative pool: there's no second
name to split it with, not a scoring artifact.

**Andrea — fsEst after sizeSide (winners):** NVDA, AMD, AVGO, ORCL,
GOOGL — all $1,736 (all Type B). QS and NFLX (the two Type A
candidates) lost the ranking cut (targetEstIndividual = 5 slots, 7
candidates competing, QS/NFLX ranked lowest by `rankScore`).

**Eduardo — fsUniverse.est (pre-sizeSide, full ranked pool):**

| symbol | type | rankScore | hardCapPct | isHeld | thesisHealth | finalAction |
|---|---|---|---|---|---|---|
| ORCL | B | 10 | 50 | true | Strengthening | Add |
| QS | A | 6 | 35 | true | Intact | Hold |
| NVDA | B | 12 | 50 | true | Strengthening | Add |
| GOOGL | B | 10 | 50 | false | Strengthening | Add |
| NFLX | A | 9 | 35 | false | Strengthening | Add |

No AMD, no AVGO — confirms neither ever enters Eduardo's candidate
universe. All 5 candidates fit within his 5 established slots, so
nothing is cut on ranking here — QS and NFLX are "winners" only because
there was no competition to displace them, not because of any
conviction edge.

**Eduardo — fsUniverse.spec:**

| symbol | type | rankScore | hardCapPct | isHeld |
|---|---|---|---|---|
| ENVX | A | 9 | 35 | true |
| AMPX | A | 9 | 35 | true |

Two speculative candidates, tied rankScore — both fit inside the
speculative pool, hence the pool splits across both (matches the
observed "ADD AMPX AND ADD ENVX" for Eduardo, vs. Andrea's single-name
AMPX fill — a direct consequence of pool composition, not divergent
scoring).

**Eduardo — fsEst after sizeSide (winners):** NVDA, ORCL, GOOGL ($2,012
each, Type B), QS, NFLX ($1,341 each, Type A).

## 4. Direct answers

- **Is ENVX in Andrea's ranked candidate list at all?** No. Confirmed
  by the live dump above — not present in `fsUniverse.est` or
  `fsUniverse.spec` for Andrea. Root cause: `status='portfolio'`
  (Eduardo/Luis hold it) + Andrea doesn't hold it → falls through both
  the held-loop and the global watchlist query.
- **Is BYDDY in Andrea's ranked candidate list?** No — excluded via the
  global `inScope: { not: false }` filter (BYDDY's `inScope=false`),
  and she doesn't hold it so the held-loop bypass doesn't apply. This
  part IS working as designed (BYDDY is explicitly out-of-scope).
- **Is AMD in Eduardo's ranked candidate list?** No. Confirmed absent
  from `fsUniverse.est` for Eduardo. Root cause: `status='portfolio'`
  (Andrea holds it) + Eduardo doesn't hold it → same mechanism as ENVX.
- **Is AVGO in Eduardo's ranked candidate list?** No, same mechanism.

## 5. Established slot-sizing formula, quoted and verified

`server/routes/moves.js`, `sizeSide()` — shared by both the normal
watchlist path and the freshStart path, called identically for both
owners:

```js
function sizeSide(list, poolPct, targetCount) {
  const ranked = [...list].sort((a, b) => b.rankScore - a.rankScore);
  let active = ranked.slice(0, targetCount);
  for (;;) {
    const poolCount  = Math.min(targetCount, active.length);
    if (poolCount === 0) return [];
    const baseWeight = poolPct / poolCount;
    const raws   = active.map(c => ({ c, raw: baseWeight * (c.type === 'B' ? 1.5 : 1.0) }));
    const rawSum = raws.reduce((s, r) => s + r.raw, 0);
    const scale  = rawSum > 0 ? poolPct / rawSum : 1;
    const sized = raws.map(({ c, raw }) => {
      const suggestedPct    = +Math.min(raw * scale, c.hardCapPct ?? 100).toFixed(1);
      const suggestedDollar = +(totalPortfolioValue * (suggestedPct / 100)).toFixed(0);
      return { ...c, suggestedPct, suggestedDollar };
    });
    ...
  }
}
```

**This is Type-A/B-multiplier weighted, not raw-conviction weighted and
not literally "cap-weighted"** (it uses a fixed 1.5×/1.0× multiplier
keyed off `type`, not off `hardCapPct` directly — though since Type B
is always the 50%-cap class and Type A is always the 35%-cap class in
this dataset, the two amount to the same grouping in practice).
`rankScore` only decides WHICH candidates survive the initial
`targetCount` cut (via the `.sort()`+`.slice()` at the top) — it plays
no role in how big each surviving slot is. Once inside `active`, every
candidate of the same type gets the exact same `baseWeight`, then
rescaled by the same `scale` factor — identical mechanism for both
owners, with the same `poolPct`/`targetCount` inputs (both use
`estPoolPct`, `targetEstIndividual` — both owners have the same
`estSpecRatio`/`maxPositions`/`equitiesTargetPct` per the verified-
identical OwnerProfile).

**Confirmed live**:
- Eduardo's 5 established winners are 3× Type B (NVDA, ORCL, GOOGL) at
  $2,012 each and 2× Type A (QS, NFLX) at $1,341 each — ratio 2012:1341
  ≈ 1.5, exactly the B/A multiplier.
- Andrea's 5 established winners are ALL Type B (NVDA, AMD, AVGO, ORCL,
  GOOGL) — no Type A survived the ranking cut for her (QS/NFLX both
  ranked below the Type-B pack and lost 2 of the 5 slots), so the
  multiplier never has anything to differentiate against and every slot
  looks uniform at $1,736.

**Conclusion: this is pre-existing, intentional `sizeSide()` behavior,
not something `freshStart` introduced and not owner-specific.** It's
invisible in Andrea's output purely because her top-5-by-rankScore
established candidates happen to all be the same type — a downstream
consequence of the candidate-pool bug in §2 (Andrea's pool has fewer
Type A competitors partly because AMD/AVGO — both Type B — are in her
pool inflating Type-B representation, while ENVX — Type A — is
missing from her pool entirely), not a separate sizing bug.

## Bug summary for follow-up

Genuine bug: **`Ticker.status` global-field promotion silently removes
a ticker from every non-holding owner's freshStart (and normal
watchlist-candidate) eligibility pool once any one owner holds it.**
This directly contradicts the freshStart design intent ("held +
watchlist, on equal footing... zero preference for what's currently
held" — per the design comment in `computeMovesPayload`). The fix
likely needs either (a) freshStart's watchlist query to also include
tickers with `status='portfolio'` that this owner doesn't hold
(inverting the current owner-scoping so status becomes irrelevant to
freshStart eligibility, only `byTicker.has(wt.id)` matters), or (b) a
broader status-per-owner rework. Left to a follow-up prompt per
instructions — no code changed in this recon.

Secondary inconsistency worth a follow-up look: the held-loop doesn't
check `inScope`, so an out-of-scope ticker (like BYDDY) can still
compete for a freshStart slot if the owner happens to hold it, while
being fully invisible to every other owner. Net effect in this case was
harmless (BYDDY lost anyway) but the mechanism is inconsistent with how
non-held candidates are gated.
