# Recon: unifying individual-ticker sizing across Full Reset and normal mode

**Recon only. No code was changed.** `computeIndividualModelWeights`, `sizeSide`,
their call sites, and `RebaselineModal` are all untouched.

## Headline

**The held-vs-new-candidate inconsistency inside normal mode is CONFIRMED, and
it is larger than the prompt suspected.** Live, right now, with no Full Reset
involved:

```
=== Luis Morales === totalPortfolioValue=$7026.49 isFreshStart=false isRebaseline=false
  ADD  NVDA  cur=0.00%  tgt=37.50%  amt=$2635  reason=New position — established pool, rank score 12
```

NVDA — a brand-new position — is sized at **37.50%**, the *entire* Established
pool. A currently-held Established position for the same owner would be sized at
`estPoolPct / max(heldEst, 11)` = **3.41%**. Same side, same pool, same portfolio,
same instant: **11× apart**, purely because one is held and one is new.

But the prompt's stated mechanism is **not quite right**, and the correction
matters for the build. See "Correction to the premise" below — the two formulas
do *not* simply run side by side on the same pool. Normal mode pre-scales the
pool before handing it to the full-deploy formula, and the divergence only opens
up when **qualifying candidates < remaining slots**.

## 1. Call sites (line numbers re-verified 2026-08-25, post-#75)

| What | Where | Notes |
|---|---|---|
| `computeIndividualModelWeights` def | `moves.js:183` | prompt said ~183 ✓ |
| └ inner `allocate` (reserve formula) | `moves.js:193-229` | prompt said ~193-227, drifted +2 |
| `computeIndividualModelWeights` call | `moves.js:1262-1266` | **only call site** |
| `sizeSide` def (full-deploy formula) | `moves.js:1384-1419` | prompt said ~1363-1399, drifted +21 |
| `sizeSide` call — Full Reset, est | `moves.js:1502` | `sizeSide(fsUniverse.est, estPoolPct, targetEstIndividual)` |
| `sizeSide` call — Full Reset, spec | `moves.js:1503` | full pool, full target count |
| `sizeSide` call — normal, est | `moves.js:1780` | `sizeSide(eligible.est, remainingEstPoolPct, remainingEstSlots)` |
| `sizeSide` call — normal, spec | `moves.js:1781` | **pre-scaled pool — see below** |

**Four `sizeSide` call sites, one `computeIndividualModelWeights` call site. No
others exist.** Both functions are module-local; neither is exported (`grep`
confirms `module.exports` carries `computeMovesPayload` and the router only).

## 2. The inconsistency — CONFIRMED, with a correction to the premise

### Correction to the premise

The prompt describes normal mode's new-candidate path as using `poolCount =
min(targetCount, active.length)` against the pool — implying held and new
positions are sized against the *same* pool by different divisors, which would
double-count. **That is not what the code does**, and the guard is deliberate
(`moves.js:1763-1778`, added 2026-08-08 after exactly that double-counting bug):

```js
const remainingEstSlots  = Math.max(0, targetEstIndividual - heldEst);
const remainingEstPoolPct = targetEstIndividual > 0
  ? estPoolPct * (remainingEstSlots / targetEstIndividual) : 0;
const estCandidates = sizeSide(eligible.est, remainingEstPoolPct, remainingEstSlots);
```

So normal mode is **globally coherent at the pool level**:

- held claim `poolPct × heldEst/target` (via `allocate`'s `fairShareSum`, `:222`)
- new claim `poolPct × remainingSlots/target`
- total = `poolPct` exactly. No double-count.

### Where it nonetheless diverges

The divergence is not pool-level, it is **per-position**, and it opens precisely
when **qualifying candidates < remaining slots**. `sizeSide` always rescales to
its *full* given pool (`scale = poolPct / rawSum`, `:1400`), so a short candidate
list concentrates the whole remaining slice into however few names qualify:

| scenario (target 6, pool 30%) | held each | new each |
|---|---|---|
| held 4, 2 qualify for 2 open slots | 30/6 = **5.0%** | (30×2/6)/2 = **5.0%** — consistent |
| held 4, **1** qualifies for 2 open slots | 30/6 = **5.0%** | (30×2/6)/1 = **10.0%** — **2× a held peer** |
| held 0, 1 qualifies for 6 open slots | — | 30×6/6 / 1 = **30%** — whole pool, one name |

The live Luis Morales case is row 3. `targetEst=11`, `heldEst=0` (both holdings,
ENVX and SPWR, are Type A speculative — `barbellSide` returns `spec`), so
`remainingEstSlots=11`, `remainingEstPoolPct = 37.5 × 11/11 = 37.5`, and
`sizeSide` finds exactly one eligible Established candidate (NVDA, Type B,
hardCap 50). `poolCount = min(11, 1) = 1` → NVDA gets the full 37.50%.

**So: confirmed, and it is not a rounding-scale disagreement — it is an
11×-scale disagreement reachable in production today.** Whether row 3 is
*wrong* is a design question, not a bug: `sizeSide`'s own comment (`:1369-1378`)
says a thin candidate list should not "silently orphan capital." That intent is
defensible. What is not defensible is that the same portfolio applies the
opposite intent (strict headroom reservation) to a held position one line away.

## 3. Separability from ADD-routing / funding (item 3)

**Cleanly separable — confirmed.** The routing and cash-ledger layer consumes
sizing output and never feeds back into it:

- `routeAddsInFundingOrder(actionMoves, ...)` — `:1939`
- `annotateAddFunding(actionMoves)` — `:1942`, def `:399`

Both run on `actionMoves` *after* every move object is fully built, and both only
read/write `m.accounts[]`, `m.dollarAmount`, `m.fundingOrder`. Neither reads
`modelWeights`, `suggestedPct`, `targetCount`, or any pool variable. `grep` for
`modelWeights|poolPct|targetEstIndividual` inside `annotateAddFunding` and
`routeAddsInFundingOrder`: no hits.

**A sizing unification does not need to touch the routing chain.** The one-way
dependency is sizing → dollarAmount → routing, so changed sizing changes routed
dollars, but no routing logic branches on *which formula* produced them.

## 4. Slot-count source (item 4)

Both formulas read the **same** source, no drift:

```
moves.js:1082  const estSpecRatio = profile.estSpecRatio ?? DEFAULT_EST_RATIO;   // 0.60
moves.js:1083  const maxPositions = profile.maxPositions ?? DEFAULT_MAX_POS;     // 15
moves.js:1212  const targetIndividual     = Math.max(0, maxPositions);
moves.js:1213  const targetEstIndividual  = Math.round(targetIndividual * estSpecRatio);
moves.js:1214  const targetSpecIndividual = targetIndividual - targetEstIndividual;
```

`targetEstIndividual`/`targetSpecIndividual` are computed once and passed to
`computeIndividualModelWeights` (`:1265`) and to all four `sizeSide` calls. Source
is `OwnerProfile.maxPositions` + `OwnerProfile.estSpecRatio` as the prompt
assumed — **re-verified ✓**.

⚠ **Live data note:** Andrea's and Eduardo's `maxPositions` are **`null`** in the
DB, so both silently fall back to `DEFAULT_MAX_POS = 15` with `estSpecRatio 0.5`
→ target 8 est / 7 spec. Only Luis has an explicit value (15, ratio 0.75 → 11/4).
Any build touching slot counts should decide whether null-means-15 is intended or
whether Admin should require the value.

## 5. Unified-allocator sketch, verified against real numbers (item 5)

The two behaviors differ in exactly **two** expressions — the divisor and the
normalization target. One boolean covers both:

```js
function allocateUnified({ poolPct, members, targetSlotCount, reserveHeadroom }) {
  const n = members.length;
  if (poolPct <= 0 || n === 0) return members.map(m => ({ ...m, pct: 0 }));
  const denom = reserveHeadroom ? Math.max(n, targetSlotCount)     // today: allocate()
                                : Math.min(targetSlotCount, n);    // today: sizeSide()
  if (denom === 0) return members.map(m => ({ ...m, pct: 0 }));
  const base = poolPct / denom;
  const raws = members.map(m => ({ m, raw: base * (m.type === 'B' ? 1.5 : 1.0) }));
  const rawSum   = raws.reduce((s, r) => s + r.raw, 0);
  const claimSum = reserveHeadroom ? base * n : poolPct;           // the other difference
  const scale    = rawSum > 0 ? claimSum / rawSum : 1;
  return raws.map(({ m, raw }) => ({ ...m, pct: +Math.min(raw * scale, m.hardCapPct ?? 100).toFixed(2) }));
}
```

Executed against the session's own Established-slot example (pool 30%, target 6,
held/qualifying 4):

```
reserveHeadroom:true  (pool/6)     5% 5% 5% 5%             | sum 20.00%
reserveHeadroom:false (pool/4)     7.5% 7.5% 7.5% 7.5%     | sum 30.00%
```

Both reproduced exactly: `30/6 = 5.00` each summing to 4/6 of the pool (reserve),
and `30/4 = 7.50` each summing to the full pool (deploy). Type A/B mix also
checks out (2×A + 1×B, pool 30, target 6 → reserve `4.29/4.29/6.43` sum 15.01 =
3/6 of pool; deploy `8.57/8.57/12.86` sum 30.00).

**The signature the prompt guessed is right in spirit but carries one parameter
too many.** `heldCount` and `activeQualifyingCount` never both matter in the same
call — each call site sizes *one* homogeneous list. `members.length` covers both.

**What the sketch does NOT yet cover** — a build must add these:
1. `sizeSide`'s **`minPositionDollar` convergence loop** (`:1391-1418`): re-divide
   among survivors, then drop the worst-ranked one at a time. `allocate` has no
   equivalent — held positions are never dropped for being too small. This is
   real behavior, not incidental, and the unified function needs it gated or
   generalized.
2. `sizeSide`'s **pre-slice** `ranked.slice(0, targetCount)` (`:1386`) — a count
   ceiling, not just a divisor. `allocate` never truncates its group.
3. `allocate`'s **`inScope`/unclassified zeroing** (`:186-191`) — held tickers
   that are out-of-scope or unclassified get weight 0. `sizeSide`'s inputs are
   pre-filtered upstream instead.
4. `allocate` uses `Math.min(ticker.capPercent, analysis.capPercent)` for
   `hardCapPct` (`:206`); `sizeSide` receives a precomputed `c.hardCapPct` from
   `effectiveCap()` at `:1457` — **which respects per-owner cap overrides while
   `allocate` does NOT.** This is a *third*, previously-unflagged divergence:
   a held position ignores `ownerCapMap` when its model weight is computed.
   Worth confirming as intended before unification silently changes it.
5. Rounding differs: `allocate` → `toFixed(2)`, `sizeSide` → `toFixed(1)`.

## 6. Behaviors that implicitly depend on the two-formula split (item 6)

Checked, not assumed:

- **Winner protection / "Strengthening exception"** (`:790-820`, gate at `:795`)
  — reads `bypassWinnerProtection`, `finalAction`, `thesisHealth`, and
  `modelWeightPct`. It consumes the model weight as a scalar and does **not**
  branch on which formula produced it. Safe. **But note:** it compares current %
  against model weight, so if unification raises held positions' model weights
  (deploy mode), fewer positions read as "over model weight" and some TRIMs
  disappear. That is a real behavioral consequence to decide on deliberately.
- **Scarcity-gap "(unallocated)" rows** (`:1796-1840`) — **this one genuinely
  depends on the split.** `achievableValue = heldTargetSum + newOpenSum` sums the
  reserve-formula output and the deploy-formula output and compares to the bucket
  target. Under a unified deploy-mode allocator, `heldTargetSum` alone would
  reach the full pool and `shortfall` would collapse to ~0 — **the scarcity rows
  would silently stop firing.** They are re-baseline-only, but this must be an
  explicit design decision in the build, not a side effect.
- **Slot-overflow guard** (`:2048-2050`, `maxPositions` warning) — counts
  positions, not weights. Unaffected.
- **Fixed buckets** (`splitBucketTarget`, `:1224`) — separate function, separate
  code path, unaffected by individual-sizing unification.
- **Task #75** (zero-cap divisor, shipped today) — different function; no overlap.

## 7. UI scope for the proposed checkbox (item 7)

The modal is **not** a separate file — it is `RebaselineModal`, a component inside
`client/src/pages/PortfolioManager.jsx:1258-1560`.

Current state: `step`, `draft`, `preview`, `err`, `mode` (`'rebalance'` |
`'freshStart'`, `:1269`), `ackFreshStart` (`:1270`).

Existing shape to copy — the `ackFreshStart` checkbox at `:1526-1534` is rendered
`{mode === 'freshStart' && (...)}` and gates the confirm button at `:1538`. The
new checkbox would sit alongside it, defaulting **ON** per Luis's framing.

Wiring needed:
1. `const [deployOnlyStrongest, setDeployOnlyStrongest] = useState(true);` (~`:1270`)
2. Checkbox in the `mode === 'freshStart'` block (~`:1526`), advisory not gating —
   it must **not** be added to `confirmDisabled` at `:1538`.
3. `loadPreview(persist, freshStart)` at `:1280-1288` → add the flag to the
   `JSON.stringify({ persist, freshStart })` body. Also pass it at the
   `handleConfirm` call (`:1345`) and the initial `loadPreview()` (`:1298`).
4. Server: `POST /:owner/rebaseline` (`:2299`) reads `req.body?.freshStart`
   (`:2305`) — add the new flag and thread it into `computeMovesPayload(owner,
   { bypassWinnerProtection: true, freshStart, reserveHeadroom })`.
5. `computeMovesPayload` options destructure at `:703` — add the new option with
   an explicit default that preserves today's behavior.
6. ⚠ **`POST /:owner/refresh` (`:2274`) must also be considered.** It recomputes
   from `existingCache.payload.isRebaseline` and passes **no** freshStart flag. If
   the choice is only stored in the request and not in the cached payload, a
   later refresh silently reverts to the default. **The flag needs to persist in
   the cached payload**, the way `isRebaseline`/`isFreshStart` already do
   (`:2176`), or the setting will not survive a refresh.

## Does the proposed direction break anything intentional?

Two things to surface before locking the design:

1. **The scarcity-gap rows depend on the formulas differing** (item 6). Unifying
   without addressing them removes a signal Luis built deliberately.
2. **"Full Reset = normal mode where every asset is cash" is a clean frame but
   not literally true today.** Full Reset passes the *full* pool and *full*
   target count (`:1502-1503`), whereas normal mode's candidate path passes the
   *remaining* slice (`:1780-1781`). Under the frame, Full Reset would have
   held=0 → remaining = target → remaining pool = full pool, which **does**
   reduce to today's Full Reset behavior. **The frame holds.** The catch is that
   Full Reset also puts held tickers into the candidate universe on equal footing
   (`:1429-1442`), so "every asset is cash" is achieved by *reclassifying held as
   candidate*, not by the allocator. Unification must preserve that reclassifying
   step as a separate concern from the deploy/reserve boolean, or Full Reset
   loses its defining behavior.

## What a build prompt would need to cover

1. Write `allocateUnified` with the 5 gaps from item 5 folded in.
2. Decide the `minPositionDollar` drop-loop question for held positions.
3. Decide the `ownerCapMap` divergence (item 5 note 4) — likely a bug to fix
   independently first.
4. Explicitly decide the scarcity-gap rows' fate under deploy mode.
5. Explicitly decide the winner-protection TRIM consequence.
6. Thread the flag through modal → rebaseline route → `computeMovesPayload` →
   **cached payload** (so refresh preserves it).
7. Regression bar: with the flag at its default, `dumpMovesForOwner.js` output for
   all three owners, normal and `--freshStart`, must be **byte-identical**.

## Follow-up commands

```bash
export DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-)
node server/scripts/dumpMovesForOwner.js "Luis Morales"            # the 37.50% NVDA row
node server/scripts/dumpMovesForOwner.js "Luis Morales" --freshStart
sed -n '183,232p;1384,1420p;1760,1785p' server/routes/moves.js     # both formulas + the pre-scale
```

## Not done

Nothing was built, changed, or committed. No checkbox, no allocator, no call-site
edits. `git status` for `server/routes/moves.js` and
`client/src/pages/PortfolioManager.jsx`: clean.
