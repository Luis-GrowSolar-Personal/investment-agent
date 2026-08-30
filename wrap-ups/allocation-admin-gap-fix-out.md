# Cash-in-allocation-model fix — session report

Date: 2026-08-09
Branch: `dev` (pushed to `origin/dev`)
Commits: `2a7c628`, `963869c`, `e184776`

## Starting problem

Luis reported cash reserve wasn't visible as part of the target allocation model:
- Admin pane showed Cash Reserve in "Identity & Capital," disconnected from the
  Target Allocation Model section (Equities/ETF/Crypto/Commodities).
- Re-baseline modal showed the four buckets summing to "100% total" with no
  cash field visible at all.

## Iteration 1 (`2a7c628`) — display-only fix, later superseded

First pass moved a "Cash" field into both UI sections for visibility, but kept
the underlying math unchanged: Equities/ETF/Crypto/Commodities were stored and
interpreted as % of *deployable* (post-cash) capital, then scaled down
server-side by `investedScale = 1 - cashReservePct` so all five effectively
summed to 100% of total portfolio. The UI showed a computed "effective %"
so the display summed to 100.

Luis flagged this was still confusing: the raw numbers on screen (e.g.
50+30+10+10+5=105) didn't sum to 100 as typed — cash was still being "taken
off the top" underneath a display that papered over it.

## Iteration 2 (`963869c`) — real fix: cash as a peer bucket

Changed the semantics so Equities/ETF/Crypto/Commodities/Cash are each a
**direct percentage of total portfolio value**, all five entered and
validated to literally sum to 100 — no hidden scaling.

Changes:
- **`server/routes/moves.js`**: removed the `investedScale` variable and its
  multiplication into `equitiesTargetPct`/`etfTargetPct`/`cryptoTargetPct`/
  `commodityTargetPct`. These are now used as entered (× 100, no scaling).
  Updated the surrounding comments, which had documented the old
  double-counting bug fix from 2026-08-08 — that fix is now moot since the
  scaling step it guarded no longer exists.
- **`client/src/pages/Admin.jsx`**: `bucketPct` now includes `cash`, and
  `bucketTotal` is the literal sum of all five fields. Removed the
  `effPct`/`effTotal` scaling logic from iteration 1. The progress bar and
  "must sum to 100%" warning now cover all five fields directly.
- **`client/src/pages/PortfolioManager.jsx`** (re-baseline modal):
  `liveTargets()` no longer applies `investedScale` to the four editable
  buckets. `totalOk` now requires `equities + etf + crypto + commodities +
  cash === 100` (cash itself isn't editable in this modal — it's fixed in
  Admin — but it counts toward the required total, and the modal blocks
  confirm until the full five-way split is valid).

**Data-migration note surfaced to Luis**: existing stored per-owner targets
(e.g. 50/30/10/10 + 5% cash = 105%) needed manual adjustment in Admin to sum
to 100 including cash. Not auto-migrated — this was a deliberate choice to
avoid silently rewriting an owner's stated allocation intent.

## Iteration 3 (`e184776`) — stale copy cleanup

During the verification pass (below), found the Allocation tab's footnote
text still read: *"Cash target reflects the 5% reserve floor — the other
five buckets' targets are scaled down so all six sum to 100%..."* — leftover
from the pre-iteration-2 design. The numbers displayed were already correct
(iteration 2 fixed the math), only this explanatory sentence was stale.
Reworded to describe cash as a peer target, not a scaled-down floor.

## Verification pass (after Luis set Admin to 45/30/10/10/5)

Checked five artifacts against each other for a single owner (Andrea
Morales, $31,454 portfolio):

1. **Admin → Target Allocation Model**: 45+30+10+10+5 = 100%. ✓
2. **Allocation tab target $**: total portfolio × each target % reproduces
   the displayed target dollars exactly (Established+Speculative $7,077 each
   from 45%÷2, ETF $9,436 from 30%, Crypto/Commodities $3,145 each from 10%,
   Cash $1,573 from 5%); bucket dollars sum to $31,453 ≈ total portfolio. ✓
3. **Re-baseline modal**: identical 45/30/10/10/5 split and identical
   current-vs-target table to the Allocation tab. ✓
4. **Bucket-level deltas net to zero**: (-6025, -2268, +3161, +2053, +2411,
   +668) sum to $0 — confirms this is a pure reallocation with no phantom
   money created or lost at the bucket level. ✓

## Open item — not resolved this session

While checking the Recommended Moves list against bucket targets, the
individual per-ticker trim amounts inside Established/Speculative Equities
summed to noticeably more than those two buckets' net target deltas:

- Established + Speculative combined bucket delta: -$6,025 + -$2,268 =
  **-$8,293** needed.
- Individual trims shown in Established/Speculative (AMPX -$3,530, EOSE
  -$3,064, AMD -$3,451, NVDA -$2,372, AMZN -$1,575, QS -$1,197, SPWR -$293):
  **-$15,482** total.

That ~$7,200 gap is plausibly explained by thesis-driven exits (the
graduated exit ratchet in `CLAUDE.md` — "Weakening → trim to cap. No
improvement after one quarter → trim 40% more...") and redistribution into
new established slots (ORCL, GOOGL, each +$1,321) rather than a pure
proportional rebalance to the bucket total. This was **not verified against
the live `/api/moves` payload or the allocator source** — only eyeballed
from UI screenshots — so it should be treated as a hypothesis, not a
confirmed explanation. Luis is taking this to Claude/Cowork for a deeper
look at the per-ticker weighting logic in `server/routes/moves.js`
(`splitBucketTarget`, `computeIndividualModelWeights`, and the ratchet/exit
code path).

## Files touched this session

- `client/src/pages/Admin.jsx`
- `client/src/pages/PortfolioManager.jsx`
- `server/routes/moves.js`

No schema/migration changes. No new dependencies.
