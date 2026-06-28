# Track Record — Decision Analytics Feature Spec

**Status: Scaffolding shipped. Full UI blocked on current-price feed.**
_Last updated: 2026-06-27_

---

## Why this exists

The agent can recommend a trim. The user can decline it. There is currently no feedback loop that shows whether that decision was correct.

The canonical use case: "You declined to trim SPWR at $24. Declined again at $20. Declined again at $16. SPWR is now at $8." That single sentence — if surfaced automatically — makes cognitive bias visible in a way that's hard to argue with. This feature is designed to surface exactly that.

---

## Core value proposition

**Pattern detection without a price feed (available now):**
- Trim avoidance rate: X% of trim recommendations not acted on
- Add acceptance rate: X% of add recommendations accepted
- Repeated pass pattern: any ticker where every logged decision was a pass (flagged "ALL PASSED")
- Top decline reasons: frequency-ranked list of verbatim reasons the user gave

**Outcome reconciliation (needs current price):**
- Per-decision Δ: price at decision time vs. current price
- Directional validation: was the recommendation right? (trim declined + price fell = missed trim)
- P&L attribution: if you had trimmed $X at $24, tax-adjusted gain vs. holding

---

## What was shipped (2026-06-27)

### 1. Price capture at decision time

`server/routes/moves.js`:
- `pricePerShare` added to the return objects of `makeTrimMove`, `makeAddMove`, and the EXIT inline builder
- Sourced from `lastPrice` on Position rows (already available from Schwab sync)

`client/src/pages/PortfolioManager.jsx`:
- `pricePerShare: move.pricePerShare ?? null` added to `systemSnapshot` in both `handleAccept` and `handleDecline`
- Stored in `OwnerDecision.systemSnapshot` (JSON field) at decision time

**All decisions from 2026-06-27 forward have a price stamp. Earlier decisions do not.**

### 2. Track Record tab (scaffolding)

Route: `/track-record`
Component: `client/src/pages/DecisionAnalytics.jsx`
Wired into: `InvestmentIdeas.jsx` (4th tab), `App.jsx` (IDEAS_PATHS)

**What renders today:**
- Bias summary bar (total decisions, trim avoidance %, add acceptance %, top decline reasons)
- Per-ticker expandable groups with decision rows showing:
  - Date, move type, decision badge
  - $ recommended amount (and actual if partial accept)
  - Price at decision (from systemSnapshot.pricePerShare)
  - Current price column → **"—" placeholder**
  - Δ column → **"awaiting price feed" placeholder**
  - Context: thesisHealth, trajectory, currentPct at decision time
  - Decline reason (verbatim)
- "ALL PASSED" badge on tickers where every decision was a pass

**What does NOT render yet:**
- Current price (Δ column is all placeholders)
- The price timeline narrative ("declined at $24 → $20 → $16")
- P&L outcome attribution

---

## Architecture decisions

### systemSnapshot is the source of truth for decision-time state

`OwnerDecision.systemSnapshot` (Prisma JSON field) stores a snapshot at the moment of decision:
```json
{
  "thesisHealth": "Weakening",
  "trajectory": "deteriorating",
  "ratchetTranche": 1,
  "currentPct": 31.4,
  "dollarAmount": 11938,
  "pricePerShare": 6.42
}
```
This is intentional — the live position data changes, so the snapshot is the only reliable record of what the model saw when the user decided.

### Current price: two tiers

**Tier 1 — positions still held (no external API needed):**
For any ticker still in the portfolio, `lastPrice` is already available on `Position` rows (populated by the Schwab sync). The `GET /api/decisions` route can join against this and return `currentPrice` alongside each decision row. This lights up the Δ column for ongoing holds immediately.

**Tier 2 — exited positions and watchlist tickers:**
Requires an external price feed. Polygon.io is the planned source (already referenced in CLAUDE.md for transcript ingestion). Until then, those rows show "—".

### Where the Δ logic lives

Server-side enrichment is preferred over client-side fetching. The `GET /api/decisions` route should return `currentPrice` alongside each decision row, and compute `pctChange` there. This keeps the frontend dumb — it just renders what the API returns.

---

## Backlog: what to build next

### Step 1 — Light up Tier 1 current prices (no new dependencies)
Enrich `GET /api/decisions` server-side: for each decision row, join against `Position` where `ticker.symbol` matches and return `lastPrice` as `currentPrice`. This immediately populates the Δ column for any position still held.

_Effort: ~30 min. Unblocked._

### Step 2 — The price timeline narrative view
Instead of (or alongside) the table, render a per-ticker visual timeline:
```
SPWR  [declined TRIM at $24.10]──[declined TRIM at $19.80]──[declined TRIM at $16.20]──● now: $8.40
```
Each node is a decision; color-coded by decision type. Makes the pattern visceral.

_Effort: medium. Requires Step 1 for the "now" anchor point._

### Step 3 — Outcome P&L attribution
For each declined trim: "If you had trimmed $11,938 at $24.10, the tax-adjusted net proceeds would have been $X. At today's price, the same shares are worth $Y (Δ = $Z)."

_Effort: medium-high. Requires tax-lot data from the Position/Lot model._

### Step 4 — Polygon.io current price feed
Wire up Polygon.io for tickers not currently held. Required for watchlist tickers and fully exited positions.

_Effort: depends on Polygon.io integration scope (already planned for transcript ingestion)._

### Step 5 — Bias alerts
If trim avoidance rate exceeds a threshold (e.g., >60% over trailing 90 days), surface a warning on the Portfolio Manager. Make the bias visible where decisions are being made, not just in a separate analytics tab.

_Effort: small once Steps 1–2 are done._

---

## Files changed in the initial scaffold

| File | Change |
|------|--------|
| `server/routes/moves.js` | Added `pricePerShare` to makeTrimMove, makeAddMove, EXIT builder |
| `client/src/pages/PortfolioManager.jsx` | Added `pricePerShare` to systemSnapshot in handleAccept + handleDecline |
| `client/src/pages/DecisionAnalytics.jsx` | New — Track Record tab component |
| `client/src/pages/InvestmentIdeas.jsx` | Added "Track Record" tab wired to `/track-record` |
| `client/src/App.jsx` | Added `/track-record` to IDEAS_PATHS |

---

## Related features

- `OwnerDecision` model: `server/prisma/schema.prisma` — the source table
- Advisory Feed "User Actions" column: `client/src/pages/AdvisoryFeed.jsx` — shows decisions inline with call rows
- Moves engine: `server/routes/moves.js` — generates the recommendations that become decisions
- Portfolio Manager move cards: `client/src/pages/PortfolioManager.jsx` — where decisions are recorded
