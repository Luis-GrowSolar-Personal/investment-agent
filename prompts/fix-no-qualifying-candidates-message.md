# Fix: surface "no qualifying candidates" for Established/Speculative, not just ETF/Crypto/Commodities

## Report your findings

When done, write a wrap-up to
`./wrap-ups/fix-no-qualifying-candidates-message-out.md`. State up front
what you changed and where, then confirm (with real numbers from
production data, not just "it compiles") that it fires correctly for
Andrea's Speculative bucket and does NOT fire for buckets that have
genuine headroom (e.g. Andrea's/Eduardo's Established buckets, which
recon already confirmed balance correctly). Write it for someone reading
cold in a later session.

## Context

A recon pass this session (`wrap-ups/recon-established-spec-shortfall-out.md`)
confirmed Andrea Morales's Speculative bucket has a real, legitimate
~$4,618 shortfall — not a bug. Her Speculative target is $7,077.22, but
SPWR+AMPX+EOSE only total $2,458.75, and there are zero eligible new
speculative watchlist candidates to fill the rest (every candidate is
either `finalAction: 'Unknown'` or `'Exit'`, both of which fail the
`['Add','Hold']` eligibility filter in `computeMovesPayload`'s
watchlist-candidate loop, `server/routes/moves.js` ~line 1103-1105).
`sizeSide()` correctly returns `[]` — there's nothing wrong with the
math, the shortfall is just invisible in the UI. Right now a user looking
at the Allocation tab or Recommended Moves has no way to tell "this
bucket is short because nothing qualifies yet" apart from noticing the
delta and going hunting for an explanation (which is how this session
ended up spending a whole recon pass confirming there wasn't a bug).

The app already has a working pattern for exactly this situation, just
for the fixed-target buckets (ETF/Crypto/Commodities): when a bucket's
target exceeds what currently-held tickers can reach (even after
`splitBucketTarget` caps each at its own limit), a synthetic bucket-level
`ADD` move is generated with `symbol: null`, `isBucketLevel: true`,
labeled e.g. "ETF (unallocated)" — see the `if (bypassWinnerProtection) {
const fixedBuckets = [...] }` block in `computeMovesPayload`
(`server/routes/moves.js`, search for `(unallocated)`). The frontend
renders these with an "Outside agent scope" label instead of Accept/
Decline buttons (`MoveRow` in `client/src/pages/PortfolioManager.jsx`,
the `move.isBucketLevel` branch).

**This fix extends that same pattern to Established and Speculative**,
but the wording needs to be different: "Outside agent scope" means "pick
a ticker yourself, that's your call" (true for ETF/Crypto/Commodities —
ticker selection there is explicitly out of scope per design). For
Established/Speculative, the reason is different: no ticker exists yet
that clears the conviction bar. That's a Radar/sourcing gap, not a
user-choice gap, and should read that way.

## What to build

### Backend — `server/routes/moves.js`

Find where the Established/Speculative candidate sizing happens —
`remainingEstPoolPct`/`remainingSpecPoolPct` and the `sizeSide(eligible.est, ...)`
/ `sizeSide(eligible.spec, ...)` calls (~line 1187-1192 as of this
session, may have shifted). After that computation, for each side
(established, speculative) work out:

- `heldValue` — sum of current market value of held tickers on that side
  (you likely already have this from the individual-stock move
  generation loop, or can derive it the same way the fixed-bucket block
  does with `positionMetrics`).
- `heldTargetSum` — sum of the `modelWeightPct`-derived dollar target
  already assigned to each held ticker on that side (from
  `computeIndividualModelWeights`'s output).
- `newOpenSum` — sum of dollar amounts from whatever `sizeSide()` actually
  returned for that side (could be `0` if no eligible candidates).
- `bucketTargetValue` — the side's full pool target in dollars (established:
  `estPoolPct`, speculative: `specPoolPct`, both already expressed as % of
  total portfolio value post this session's cash-peer-bucket redesign —
  don't reintroduce `investedScale`, it's gone).
- `achievableValue = heldTargetSum + newOpenSum`.
- `shortfall = bucketTargetValue - achievableValue`.

If `shortfall > minPositionDollar` AND the eligible candidate list for
that side (`eligible.est` / `eligible.spec`) is empty (or, more
precisely, `sizeSide` returned nothing usable — check however that
function signals "nothing qualified" today), push a synthetic move
mirroring the fixed-bucket pattern:

```js
{
  moveType: 'ADD', priority: 5, symbol: null,
  shortName: `${label} (unallocated)`,   // "Established Equities (unallocated)" / "Speculative Equities (unallocated)"
  bucket: side,                           // 'established' / 'speculative' — check what key the Allocation tab expects
  tier: side, thesisHealth: '—', finalAction: '—', trajectory: null,
  ratchetTranche: 0,
  currentPct: ..., targetPct: ...,
  hardCapPct: ...,
  currentMktValue: +heldValue.toFixed(2),
  dollarAmount: +shortfall.toFixed(2),
  sharesApprox: 0, taxCost: 0, netProceeds: 0, accounts: [],
  requires48h: false,
  isBucketLevel: true,
  isScarcityGap: true,   // NEW flag — distinguishes this from the ETF/Crypto/Commodity "pick a ticker" case
  reason: `${label} at ${currentPct.toFixed(1)}% — below target of ${targetPct.toFixed(1)}%, but no ${side === 'established' ? 'established' : 'speculative'} watchlist candidate currently clears the conviction bar to fill the gap. Needs new names sourced (Layer 3 / Opportunity Scanner), not a bigger allocation to what's already held.`,
}
```

Only generate this inside the same `if (bypassWinnerProtection)` gate the
ETF/Crypto/Commodity block already uses — this is a re-baseline-review
concept (full current-vs-target reconciliation), not something that
should appear in the everyday Moves tab. Confirm this placement makes
sense by re-reading how `isRebaseline`/`bypassWinnerProtection` flows
through before assuming — don't just copy-paste the fixed-bucket block's
gating without checking it still applies the same way post the
cash-peer-bucket redesign.

### Frontend — `client/src/pages/PortfolioManager.jsx`

In `MoveRow`, the `move.isBucketLevel` branch currently always renders
"Outside agent scope". Branch on the new `isScarcityGap` flag instead:

- `isBucketLevel && isScarcityGap` → different label/tag, e.g. "No
  qualifying candidates" with a distinct visual treatment (Luis's
  preference, stated this session: not the same look as "Outside agent
  scope" — something like an amber/gray "SCARCE" tag, since the meaning
  is different: this is a sourcing gap, not a user-choice gap).
- `isBucketLevel && !isScarcityGap` → existing "Outside agent scope"
  behavior, unchanged.

Keep this to the Recommended Moves tab only — per this session's
decision, don't duplicate the message into the Allocation tab as well;
one place to look for "what needs attention" avoids the two-views-
disagree confusion this whole session has been chasing out of the app.

## Verify against real data before calling this done

Run `computeMovesPayload(owner, { bypassWinnerProtection: true })`
directly (exported from `server/routes/moves.js`, no HTTP/auth needed —
recon already did this successfully this session) for:

- **Andrea Morales** — Speculative should now show a scarcity-gap row
  with `dollarAmount` ≈ $4,618 (recompute the exact figure fresh, don't
  hardcode this estimate).
- **Andrea Morales** — Established should NOT show one (recon confirmed
  this balances once held "no action needed" tickers are counted).
- **Eduardo Morales** — neither Established nor Speculative should show
  one (recon confirmed both balance).

If any of these don't match, the eligibility/shortfall logic needs
another look before shipping — don't rely on "it compiles and renders."

## Commit and push

You have real local git access and Luis doesn't want to hand-run git
commands — commit and push this yourself when it's verified:

```bash
git add -A
git commit -m "Surface 'no qualifying candidates' scarcity gap for Established/Speculative, distinct from ETF/Crypto/Commodity 'outside agent scope'"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.
