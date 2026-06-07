# Investment Agent — CoWork Handoff
**Date:** 2026-06-06
**Picks up from:** CoWork_handoff_2026-05-31.md
**Session work:** Dashboard, Users tab, Admin tab, portfolio analyst architecture

---

## What was completed this session

### Portfolio Analyst foundation (Steps 3→4 bridge)

**New DB table: OwnerProfile** (two migrations applied to Railway)
- `20260531000001_add_owner_profile` — creates OwnerProfile with owner (PK), displayName, enoughNumber
- `20260606000001_add_owner_profile_admin_fields` — adds 12 admin/config fields (see below)
- Back-fill: existing account owners auto-inserted into OwnerProfile on migration

**OwnerProfile fields (full set):**
```
owner             String @id    — matches Account.owner exactly
displayName       String?       — friendly display override
enoughNumber      Float?        — investment goal in dollars
minPositionDollar Float?        — smallest position worth holding (default $1,500)
maxPositions      Int?          — hard cap on ticker count (default 15)
cashReservePct    Float?        — % of portfolio as dry powder (default 0.05)
yearsToGoal       Int?          — drives speculative ceiling formula
estSpecRatio      Float?        — barbell split 0.0–1.0; 0.60 = 60% established
riskTolerance     String?       — "conservative" | "moderate" | "aggressive"
taxSensitivity    String?       — "aggressive" | "moderate" | "conservative"
accountPurpose    String?       — "growth" | "income" | "preservation"
domainsOfInterest Json?         — string[] of domain IDs
benchmarkBaseline String?       — "SPY" | "QQQ" | "TMFC"
specExitSpeed     String?       — "fast" | "normal" | "patient"
newMoneyBehavior  String?       — "highest_conviction" | "distribute"
```

**Auto-wiring:** `ensureOwnerProfile(owner)` called in `POST /accounts` and `POST /accounts/:id/import` — new owner string auto-creates an OwnerProfile row.

### New routes

- `GET/POST/PATCH/DELETE /api/users` — OwnerProfile CRUD (server/routes/users.js)
- `GET /api/dashboard` — summary list of all owners with portfolio value
- `GET /api/dashboard/:owner` — full allocator output for one owner:
  - Latest Analysis score per ticker (firewall preserved — no transcript text)
  - Cap enforcement: MIN(ticker.capPercent, analyst.capPercent)
  - Tax-aware trim routing (tax-advantaged accounts first, FIFO lots)
  - Flags: over_cap, near_cap, 48h_wait, ratchet, out_scope
  - Enough-number check vs enoughNumber
- `GET/POST/PATCH/DELETE /api/dashboard` — registered in server/index.js

### New frontend pages

**Users tab** (`/users`) — owner management: list all OwnerProfile rows, edit displayName + enoughNumber, + New Owner button, delete (blocked if accounts exist), progress bar vs goal.

**Dashboard tab** (`/dashboard`) — per-owner collapsible allocator cards:
- Portfolio total vs investment goal (progress bar)
- Per-ticker: weight vs cap, thesis health, final action, trend trajectory, flags
- Expandable tax routing for Trim/Exit recommendations
- Flag summary chips in card header (red/amber counts)
- Account summary footer (cash + margin per account)

**Admin tab** (`/admin`) — per-owner portfolio configuration, 4 sections:
1. Capital & Sizing: min position $, max positions, cash reserve %, investment goal
2. Risk Profile: years to goal, barbell ratio (with visual bar), risk tolerance
   - Computed: spec ceiling from years-to-goal (formula: 30+y→50%, 20-30y→40%, 10-20y→25%, 5-10y→15%, <5y→5%)
   - Warning if requested spec % exceeds time-horizon ceiling
3. Tax & Account: tax sensitivity, account purpose (growth/income/preservation), benchmark
4. Domain & Universe: domain checkboxes (T1: Solar, Storage, Semis; T2: IT/Cloud, Crypto), spec exit speed, new money behavior

### Nav order (current)
Stock Analyst | Stock Radar | Advisory Feed | Portfolio | Users | Dashboard | Admin

---

## Key architectural decisions made this session

### Owner-scoped concentration caps
Concentration caps (35%/50%) apply **per owner**, not across the household. Eduardo's 30% position in X does not block Luis's ability to buy X. The allocator aggregates positions within one owner's accounts only.

### Cap% source of truth
`MIN(Ticker.capPercent, latestAnalysis.capPercent)` — user's ticker-level value is the ceiling. Analyst can only recommend equal or lower.

### OwnerProfile is the source of truth for "who exists"
Account.owner is a soft foreign key (string match). Dashboard and Admin iterate over OwnerProfile rows — adding a new account owner auto-creates their profile and Dashboard card.

### Barbell portfolio design
- Established (EST tier) = safe side; Speculative (SPEC tier) = risky side
- Default 60/40 split, configurable per owner
- Speculative ceiling auto-computed from yearsToGoal (mechanical formula)
- specExitSpeed = "fast" enforces barbell discipline: specs cut after 1 quarter weakening

### Tax-loss harvest insight (Eduardo Custodial)
As of this session, Eduardo Custodial has:
- Gains: AMPX +$677, NVDA +$608 = +$1,285
- Losses: BYDDY -$119, ENVX -$907, EOSE -$279, ORCL -$278, SPWR -$974 = -$2,557
- Net: **-$1,272 loss** → selling everything costs zero tax, generates loss carryforward
- This is an ideal window to reset the portfolio

### Backtest universe (what actually drove the returns)
- Best result: established-only subset of 16-ticker universe → +27.8% CAGR, beats all baselines
- Universe: AAPL, AMD, AMPX, AVGO, ENVX, EOSE, FSLR, GOOGL, MSFT, NVDA, ORCL, QS, RUN, SPWR, TSLA, TTD
- Top-20-2021 (AAPL/MSFT/AMZN/GOOGL/META/TSLA/ADBE/V/JNJ/WMT/JPM/PG/UNH/DIS/NVDA/MA/HD/PYPL/BAC/NFLX) is a separate hypothesis — transcripts exist in RADAR for most of these
- Speculative-only run: +0.8% CAGR → catastrophic. The barbell needs the established core.

### Current RADAR state (as of session end)
**Portfolio (8 tickers):** AAPL, AMPX, ENVX, EOSE, MSFT, SPWR, TSLA, TTD
**Watchlist (32 tickers, most scored):** Full top-20-2021 universe plus speculative names. Key signals:
- Strong Add: META (improving!), NVDA, AMZN, AVGO, ORCL, WMT, JPM, V, FSLR, QS, RUN
- Hold: DIS, HD, PG, UNH
- Trim: ENPH (deteriorating), PYPL (deteriorating), SPWR (portfolio, weakening), TTD (portfolio, trim)
- No signal (ETFs): BTC, GLD, IAU, IBIT, QQQ, SIVR, TMFC

---

## Backlog (priority order)

1. **Recommended Moves engine** — next build priority. Per-account action plan:
   - Specific trim amounts: `(currentPct − targetPct) × portfolioValue` in $ and shares
   - Specific add amounts: `(recommendedSize − currentPct) × portfolioValue`
   - Watchlist promotion candidates ranked by: trajectory score + thesis health + type
   - Capital flow plan: "Trim SPWR → $X freed → buy META (Add, improving, Type B)"
   - "Sell everything" scenario: compute net tax position, propose new allocation from scratch
   - Read OwnerProfile params (barbell ratio, specExitSpeed, maxPositions, etc.)

2. **Wire OwnerProfile params into allocator** — dashboard route currently ignores Admin settings. estSpecRatio, maxPositions, minPositionDollar, taxSensitivity, specExitSpeed should all gate allocator output.

3. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing.

4. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity.

5. **Wire Polygon into 3-axis classifier** — replace manual price_cache.json with live Polygon calls.

6. **Reinvested dividends (DRIP)** — `Qual Div Reinvest` cash dividends currently ignored.

7. **ADR cost basis normalization** — BYDDY and similar: transaction JSON price ≠ Schwab USD cost basis.

8. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`.

9. **Per-user access control** — allow non-admin owners to log in and see only their own data.
   - Schema is ready: `OwnerProfile.clerkUserId` + `OwnerProfile.role` added 2026-06-06.
   - Luis's row needs `role = "admin"` and his `clerkUserId` set manually after migration.
   - **What's needed when the time comes:**
     - Backend: `resolveOwner(req)` middleware that reads Clerk JWT → looks up OwnerProfile by clerkUserId → attaches `req.ownerProfile`. All routes check `role === "admin"` or enforce `owner === req.ownerProfile.owner`.
     - Frontend: `useOwnerContext()` hook returning the logged-in owner string; components that today show all owners filter to just theirs.
     - **Biggest lift**: Ticker/Radar is currently global (no `owner` column). The right split is analyst layer (Radar/transcripts) stays global; allocator layer (Portfolio, Moves, Admin) is per-owner. Radar stays read-only for non-admin users.
   - **Architectural seam to respect now**: any new allocator-side feature (Moves engine, Dashboard) should be `owner`-scoped from day one. Analyst-side features (Radar, transcripts) stay global. This is already consistent with the analyst/allocator firewall.

---

## Key constraints (do not re-derive)

- **Analyst/Allocator firewall**: analyst never receives portfolio data; allocator never receives transcripts
- **Tax**: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- **48-hour wait**: any position above 30% of portfolio before confirming hold
- **Git**: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- **Never paste `.env` contents**
- **Transcript cap**: watchlist = 50; portfolio = unlimited
- **Polygon free tier**: prev-close only; snapshot endpoint requires paid plan
- **Prisma**: stay on v6.19.3 — v7 is a breaking upgrade, defer to its own session
- **Testing**: Luis tests on live Railway dev deployment only — no localhost env. Always close sessions with a git commit + push block.
- **Cap% rule**: MIN(ticker.capPercent, analyst.capPercent) — user wins
- **Type B cap**: flat 50% (variable cap experiment retired 2026-05-17)
