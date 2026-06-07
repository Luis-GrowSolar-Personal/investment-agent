# Investment Agent — CoWork Handoff
**Date:** 2026-06-07 (session b)
**Picks up from:** CoWork_handoff_2026-06-07.md
**Session work:** Recommended Moves engine — backend + frontend

---

## What was completed this session

### Recommended Moves engine (Backlog #1 — DONE)

**New backend route: `server/routes/moves.js`**
- `GET /api/moves` — list all owners (for owner selector)
- `GET /api/moves/:owner` — full recommended moves for one owner

Move types generated (in priority order):
1. **EXIT** — ratchetTranche ≥ 3 or finalAction = Exit
2. **TRIM_CAP** — position over concentration cap (hard rule)
3. **TRIM_RATCHET** — graduated exit ratchet (tranche 1 = trim to cap, tranche 2 = trim 40%)
4. **TRIM_SIGNAL** — analyst says Trim, no cap violation, no ratchet
5. **ADD** — existing portfolio position with Add signal, under target %
6. **HOLD** — no action; surfaces in holds section

**`specExitSpeed` wired in:**
- `"fast"`: speculative tickers with ratchet ≥ 1 or deteriorating trajectory → EXIT immediately
- `"normal"`: default graduated ratchet
- `"patient"`: ratchet 1-2 on spec tickers → HOLD with warning (only exits at tranche 3)

**Tax routing:** FIFO lots, tax-advantaged accounts (IRA/Roth) trimmed first, 0% tax.

**Watchlist candidates:**
- Scored: trajectory (0-5) + thesisHealth (0-4) + action (−5 to +3) + type (A=1, B=2)
- Filtered: Add or Hold signal, not Broken or Weakening (unless Add)
- `newMoneyBehavior = "highest_conviction"` → top 2 only
- `minPositionDollar` threshold applied

**Capital flow plan:**
- Sources: net proceeds from all trim/exit moves
- Plus free cash (totalCash − cashReservePct × portfolioValue)
- Uses: ADD moves for existing positions, then watchlist promotions
- Surplus/shortfall reported

**Warnings generated:**
- 48h hold required (position > 30%)
- Barbell imbalance (SPEC% vs target from estSpecRatio, ±7% tolerance)
- Max positions would be exceeded by promotions
- Enough number reached → transition to passive suggested

**Registered:** `app.use('/api/moves', movesRouter)` in `server/index.js`

**New frontend: `client/src/pages/PortfolioManager.jsx`**
- Replaced placeholder with full Moves UI
- Portfolio summary bar: total value, cash (free/reserved), position count, barbell status with visual bar + target marker
- Action Required section: move cards with type badge, symbol, reason, dollar amount, tax cost, signal badges (health/trajectory/ratchet), expandable tax routing per account
- Capital flow: sources vs uses table with totals, surplus/shortfall
- Watchlist Candidates: ranked table with score, suggested dollar + %, signal badges
- Holds: compact chips for no-action positions
- Structural flags: warnings with severity styling
- Owner selector (multi-owner support)
- Refresh button

---

## Architecture notes

### OwnerProfile params now consumed by Moves engine
All allocator-side params are wired:
- `cashReservePct` → floor for free cash computation
- `estSpecRatio` → barbell target and imbalance warning
- `maxPositions` → position count warning
- `minPositionDollar` → promotion threshold filter
- `specExitSpeed` → modifies effective action for speculative tickers
- `newMoneyBehavior` → limits candidates to top 2 when "highest_conviction"

### What's NOT yet wired (backlog)
- `taxSensitivity` — "conservative" should further deprioritize taxable trims (tax-advantaged already goes first, but conservative could add a warning)
- `yearsToGoal` / spec ceiling formula — not yet enforced as a hard gate in the Moves engine
- `enoughNumber` — generates a warning but doesn't gate recommendations

---

## Key constraints (unchanged)
- Analyst/Allocator firewall: analyst never receives portfolio data; allocator never receives transcripts
- Tax: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour wait: any position above 30% of portfolio before confirming hold
- Git: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- Never paste `.env` contents
- Prisma: stay on v6.19.3 — v7 is a breaking upgrade, defer to its own session
- Testing: Luis tests on live Railway dev deployment only

---

## Backlog (updated priority order)

1. **Wire OwnerProfile params into allocator (At a Glance tab)** — Dashboard route currently ignores Admin settings. estSpecRatio, maxPositions, minPositionDollar, taxSensitivity, specExitSpeed should gate Dashboard allocator output too (Moves already consumes them).

2. **Domain tag on Ticker** — add `domain String?` to Ticker schema; assign in Investment Ideas/Radar with admin-only modal.

3. **Owner assignment per ticker** — add `users String[]` to Ticker; filter Radar view per user.

4. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing.

5. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity.

6. **Wire Polygon into 3-axis classifier** — replace manual price_cache.json with live Polygon calls.

7. **Reinvested dividends (DRIP)** — `Qual Div Reinvest` cash dividends currently ignored.

8. **ADR cost basis normalization** — BYDDY and similar: transaction JSON price ≠ Schwab USD cost basis.

9. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`.

10. **Per-user access control** — allow non-admin owners to log in and see only their own data.
    - Schema ready: `OwnerProfile.clerkUserId` + `OwnerProfile.role` added 2026-06-06.
    - See 2026-06-07.md architecture notes for full implementation plan.
