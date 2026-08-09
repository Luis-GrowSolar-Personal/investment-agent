# Surface "no qualifying candidates" for Established/Speculative — findings

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)

## What changed

- **`server/routes/moves.js`** (`computeMovesPayload`): after the
  `sizeSide(eligible.est, ...)` / `sizeSide(eligible.spec, ...)` calls, added
  a new block (gated by `bypassWinnerProtection`, same as the existing
  ETF/Crypto/Commodity "(unallocated)" block) that computes, per barbell
  side:
  - `heldTargetSum` — sum of `modelWeights.get(ticker.id)` (dollars) for
    currently-held tickers on that side.
  - `newOpenSum` — sum of `suggestedDollar` for whatever `sizeSide()`
    actually returned.
  - `shortfall = (estPoolPct or specPoolPct, in dollars) - (heldTargetSum + newOpenSum)`.

  If `shortfall > minPositionDollar` **and** `sideCandidates.length === 0`
  (i.e. `sizeSide` returned nothing usable — no eligible watchlist candidate
  cleared the conviction bar), pushes a synthetic bucket-level `ADD` move:
  `symbol: null`, `isBucketLevel: true`, **`isScarcityGap: true`** (new flag,
  distinct from the fixed-bucket rows which don't set it), labeled
  `"Established Equities (unallocated)"` / `"Speculative Equities (unallocated)"`,
  with a reason string pointing at Layer 3/Opportunity Scanner sourcing
  rather than "pick a ticker yourself."

- **`client/src/pages/PortfolioManager.jsx`** (`MoveRow`): the
  `move.isBucketLevel` branch now checks `isScarcityGap` first — renders an
  amber "NO QUALIFYING CANDIDATES" tag (distinct styling from the existing
  gray "Outside agent scope" text) when set, falls through to the original
  "Outside agent scope" rendering otherwise. Recommended Moves tab only, per
  this session's decision — not duplicated into the Allocation tab.

## Verification against production data

Ran `computeMovesPayload(owner, { bypassWinnerProtection: true })` directly
(exported from `server/routes/moves.js`) for both owners:

| Owner | Established fires? | Speculative fires? | Speculative shortfall $ |
|---|---|---|---|
| Andrea Morales | No | **Yes** | $4,048.17 (22.5% target) |
| Eduardo Morales | No | **Yes** | $2,521.91 (27.5% target) |

Both Established buckets correctly show **no** scarcity row (they have
either enough held names or eligible new-open candidates — ORCL/GOOGL for
Andrea, GOOGL/NFLX for Eduardo — to fill the target). Both Speculative
buckets fire, and in both cases the gate condition is genuinely true: the
shared watchlist (`Ticker.status` is global, not owner-specific) has zero
tickers eligible for the speculative side for *either* owner — every
watchlist candidate that could barbell into "spec" fails the `['Add','Hold']`
eligibility filter (`GLD`: `finalAction: 'Unknown'`; `RUN`: `finalAction:
'Exit'`). `sizeSide()` correctly returns `[]` for both.

## Correction to the prior recon report

`wrap-ups/recon-established-spec-shortfall-out.md` (this session, earlier)
concluded Eduardo's Speculative bucket "balances... within ~$184" once
SIVR/BTC/BYDDY holdings were included in the manual tally. **That
conclusion was wrong**, for two compounding reasons:

1. **SIVR and BTC are not part of the equity Speculative pool at all.**
   `barbellSide()` returns `'spec'` for them (used only for their `tier`
   display label / TierChip), but `isFixedTarget()` routes them into
   `fixedGroups` — they're funded from the Commodity and Crypto bucket
   targets respectively (`commodityTargetPct`/`cryptoTargetPct`), not from
   `specPoolPct`. Their `targetPct` values (5%, 5%) look like part of "the
   speculative bucket" in the UI's `tier` tag, but that dollar amount comes
   out of a different top-level bucket's target. Summing them into the
   Established/Speculative equity-pool total double-counts against the
   Commodity/Crypto bucket targets that already account for them.

2. **`computeIndividualModelWeights` deliberately reserves headroom for new
   opens** — that's the `denom = max(group.length, targetCount)` mechanism
   documented at moves.js ~line 1199-1214 (added 2026-08-08 specifically to
   stop double-counting existing holdings against the full pool). When held
   count < target count, `heldTargetSum` alone is *supposed* to be less than
   the full pool target — that gap is reserved for new opens, not a bug and
   not something the old recon's flat "sum what's displayed" tally could
   see. When there genuinely are no new-open candidates (as here), that
   reserved slice is a real, uncovered gap — which is exactly what this
   session's fix now surfaces correctly.

Net effect: **both Andrea's and Eduardo's Speculative buckets have a
genuine, legitimate scarcity gap**, not just Andrea's as the earlier recon
concluded. The earlier recon's methodology (manually summing displayed
`targetPct` values from screenshots/JSON without separating fixed-target
buckets from the barbell equity pools, and without accounting for the
new-open reservation) undercounted the real gap. This fix's calculation
goes through the same `modelWeights`/`sizeSide` machinery the engine
actually uses, so it doesn't have that blind spot.

## What wasn't done

- Did not backfill `priorDecision` hydration for the new scarcity rows —
  they're pushed into `actionMoves` after the `priorMap` hydration loop
  runs (same as the pre-existing ETF/Crypto/Commodity unallocated rows,
  which have the same gap: their `symbol: null` keys would collide across
  different bucket labels anyway, so this wasn't a meaningfully working
  path to begin with). Not treated as in-scope for this fix.
- Did not touch the Allocation tab — this session's explicit instruction
  was Recommended Moves only, to avoid the two-views-disagree confusion
  that motivated the whole investigation.

## Files touched

- `server/routes/moves.js`
- `client/src/pages/PortfolioManager.jsx`

No schema/migration changes.
