# Investment Agent — CoWork Handoff
**Date:** 2026-06-07 (session c)
**Picks up from:** CoWork_handoff_2026-06-07b.md
**Session work:** Model portfolio weight engine (moves.js v2) + frontend capital flow split

---

## What was completed this session

### moves.js v2 — Model portfolio weight engine

**Core change:** replaced analyst `recommendedSize` as the position target with a pool-based
model weight. Every individual stock is now measured against a computed "model weight" derived
from the portfolio's two-pool barbell architecture — not an analyst ceiling.

#### Bucket classification

Three asset classes, two barbell sides:
- `etf` bucket → **EST pool** (fixed target = `capPercent` as configured)
- `commodity` / `crypto` buckets → **SPEC pool** (fixed target = `capPercent`)
- `equity` bucket → **individual stocks**, shares remaining pool by type multiplier

#### Pool computation (after fixed-target reservations)

```
estPool%  = estRatio × 100 − sum(ETF capPercents)
specPool% = specRatio × 100 − sum(Commodity/Crypto capPercents)
```

#### Model weight formula for individual stocks

```
denom         = max(currentPositionCount, targetPositionCount)
baseWeight    = poolPct ÷ denom
rawWeight     = baseWeight × (type B → 1.5×, type A → 1.0×)
normalised    = rawWeight × (poolPct ÷ sum(rawWeights))
modelWeight   = min(normalised, hardCapPct)
```

#### Move generation (same logic for initial build and ongoing management)

| Priority | Move type      | Condition                                              |
|----------|----------------|--------------------------------------------------------|
| 1        | EXIT           | ratchetTranche ≥ 3, thesisHealth = Broken, or Exit signal |
| 2        | TRIM_CAP       | currentPct > hardCapPct + 0.5% (always enforced)       |
| 3        | TRIM_RATCHET   | ratchetTranche 1–2, trim to model weight or −40%       |
| 4        | TRIM_MODEL     | currentPct > modelWeight + 1% tolerance                |
|          | HOLD_ADVISORY  | Strengthening + Add signal above model but below cap   |
| 5        | ADD            | currentPct < modelWeight − 1%, thesis ≥ Intact         |
| 99       | HOLD           | within tolerance                                       |

The **HOLD_ADVISORY** ("Let Run") case: when thesis is Strengthening and analyst says Add,
the engine lets a position run between model weight and hard cap — no trim, just surfaces
it as advisory.

#### Fixed-target assets (ETF, commodity, crypto)
- Model weight = `ticker.capPercent` — no pool calculation needed.
- Same trim logic (if drift above target + 1% tolerance → TRIM_MODEL).

#### Capital-constrained flow (funded now / queue split)
Sources: net proceeds from trims/exits + free cash above reserve floor.
Uses ranked by priority: ADD existing positions first, then watchlist promotions.

- **fundedNow**: uses that fit within `totalAvailable`, in rank order (includes partial fills)
- **queue**: uses that couldn't be funded — labelled "needs new capital"
- No more misleading "$275K shortfall" — queue represents genuine new-money requirement

#### specExitSpeed modifier
- `"fast"`: spec tickers with ratchetTranche ≥ 1 or deteriorating trajectory → EXIT immediately
- `"patient"`: spec tickers ratchet 1–2 → downgrade Trim → Hold (only exits at tranche 3)

#### Key constraints preserved
- Analyst/Allocator firewall: route receives only structured scores, no transcript text
- Tax-advantaged accounts trimmed first (0% rate)
- 48h warning for any position > 30% of portfolio
- Barbell imbalance warning (±7% tolerance on SPEC target)

---

### PortfolioManager.jsx — frontend updates

1. **MOVE_META** extended: `TRIM_MODEL` (amber), `HOLD_ADVISORY` (slate)
2. **Move card signal row**: shows "X.X% model" instead of "cap" for TRIM_MODEL/ADD moves
3. **Let Run section**: compact chips for HOLD_ADVISORY positions (Strengthening + above model, below cap)
4. **Capital Flow rewritten** with three columns:
   - SOURCES (trim proceeds + free cash)
   - FUNDED NOW (green — executable today)
   - QUEUE (amber — needs new contribution)
   - Partial fills shown with "PARTIAL" badge and original vs partial amount
5. **Barbell bar**: now shows `estPoolPct`/`specPoolPct` (available % for individual names)
   in addition to EST/SPEC actual split

---

## Architecture notes

### What changed conceptually (Phase 1 = Phase 2)
The user confirmed: initial portfolio build and ongoing rebalance use the **same heuristic**.
The only expected difference is that initial state is more misaligned — but the engine
runs the same model weight comparison either way. No separate "Phase 1 logic" needed.

### Two-pool barbell is now enforced
ETFs count against the EST pool. Commodities and crypto count against the SPEC pool.
Individual names share only what remains after fixed-target reservations.
- If ETF allocations exhaust the EST pool → warning emitted
- If commodity/crypto exhaust SPEC pool → warning emitted

### Fixed-target assets (Andrea's / Eduardo's small commodity/crypto positions)
`capPercent` on the Ticker record is the target. No analyst signal required.
Engine just checks: is currentPct above capPercent? If yes → trim back.
Small positions (gold, silver, bitcoin) are preserved this way per user preference.

---

## Key constraints (unchanged)

- Analyst/Allocator firewall: analyst never receives portfolio data; allocator never receives transcripts
- Tax: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour wait: any position above 30% of portfolio before confirming hold
- Git: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- Never paste `.env` contents
- Prisma: stay on v6.19.3 — v7 is a breaking upgrade
- Testing: Luis tests on live Railway dev deployment only
- Pull before any changes; pull before push (`App.jsx` is high-conflict)

---

## Backlog (updated priority order)

1. **Wire OwnerProfile params into Dashboard allocator (At a Glance tab)** — Dashboard route
   ignores Admin settings. estSpecRatio, maxPositions, minPositionDollar, taxSensitivity,
   specExitSpeed should gate Dashboard output too (Moves already consumes them).

2. **Domain tag on Ticker** — add `domain String?` to Ticker schema; assign in Radar.

3. **Owner assignment per ticker** — `users String[]` on Ticker; filter Radar per user.

4. **MovesCache** — `OwnerProfile`-scoped JSON cache; invalidate on new Analysis or price refresh.
   Performance fix so clicking owners doesn't re-derive everything each time.

5. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing.

6. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity.

7. **Wire Polygon into 3-axis classifier** — replace manual price_cache.json with live calls.

8. **Reinvested dividends (DRIP)** — `Qual Div Reinvest` cash dividends currently ignored.

9. **ADR cost basis normalization** — BYDDY and similar.

10. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`.

11. **Per-user access control** — non-admin owners see only their own data.
    Schema ready: `OwnerProfile.clerkUserId` + `OwnerProfile.role` added 2026-06-06.

12. **New fixed-target position cap prompt (Option 3)** — when a fixed-target asset (ETF/commodity/crypto)
    is first detected in an owner's portfolio with no `OwnerTickerConfig` row, surface a highlighted
    "no cap set" row in the Admin Position Caps table, prompting the user to set one before the
    Portfolio Manager can generate a meaningful recommendation. Tax-loss harvest scenario (e.g. GLD → IAU)
    is the primary trigger.

13. **Third Investment Ideas sub-tab: "Out of scope"** — Investment Ideas currently has two views
    (Portfolio, Watchlist). Add a third: "Out of scope" — tickers with `inScope: false`. These are
    the regression/test tickers (BAC, JPM, JNJ, V, META, AMZN, ADBE, AMD, QS, etc.) used to validate
    the evaluator prompt. Their transcripts and analyses stay in the DB for backtesting/regression
    purposes — they're excluded from `moves.js` (see `inScope` guard added 2026-06-13) but still
    need a home in the UI so they're not just hidden/orphaned. Likely just a filtered view of the
    existing Radar table (`status` unchanged, filter on `inScope === false`), not a new data model.
