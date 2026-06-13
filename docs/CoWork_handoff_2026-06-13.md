# Investment Agent — CoWork Handoff
**Date:** 2026-06-13
**Picks up from:** CoWork_handoff_2026-06-07c.md
**Session work:** Dashboard cap fix (item 1) + Domain tags (item 2), both DONE.
**Next session focus:** Backlog item 5 — Schwab API integration (3-legged OAuth)

---

## Starting point: Schwab API integration (item 5)

Goal: replace manual Schwab CSV/JSON upload + Polygon.io pricing with a live
Schwab API connection (read-only — account positions, balances, quotes).

### Current state (what it replaces)

**CSV/JSON import** — `server/lib/portfolioImport.js`
- `parsePositionsCSV(csvText)` — sends raw CSV to Claude (Haiku) to extract
  positions in a fixed JSON shape (format-agnostic AI parser).
- `parseTransactionsJSON(jsonText)` — parses Schwab's `BrokerageTransactions`
  JSON export for Buy/Sell/Reverse Split/Reinvest Shares.
- `reconstructLots()` / `reconstructPositionsFromTransactions()` — FIFO lot
  reconstruction for cost-basis/holding-period tracking.
- `smartDefaultBucket(assetType, symbol)` — classifies into equity/etf/crypto/commodity.
- Wired into `POST /api/portfolio/accounts/:id/import` (`server/routes/portfolio.js:502`).
  Upserts Ticker (auto-creates with `inScope: false` if new), Position, and
  replaces `source: 'import'` Lots on each run.

**Price refresh** — `server/lib/priceRefresh.js`
- `refreshPrices()` / `refreshAccountPrices()` — calls Polygon.io prev-close
  endpoint per symbol (sequential, 500ms spacing, free tier).
- Wired into `POST /api/portfolio/accounts/:id/refresh-prices` (`portfolio.js:635`).
- Env: `POLYGON_API_KEY`.

**Schema (relevant models)** — `server/prisma/schema.prisma`
- `Account` (id, name, type, owner, managed, ltcgRate/stcgRate, cashBalance,
  cashAsOfDate, marginBalance/marginRate/marginRateLog) — one per named brokerage account.
- `Position` (tickerId, accountId, status, lastPrice, lastPriceAsOf,
  dayChangePct, dayChangeDollar) — unique on (tickerId, accountId).
- `Lot` (positionId, shares, costBasis, acquiredDate, source: "manual"|"import", closedDate).
- `Ticker.bucketOverride` — equity/etf/crypto/commodity bucket.

### Already provisioned

`.env.example` already lists `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET` —
these were anticipated but **not yet filled in or used anywhere in code**. No
`server/lib/schwab*.js`, no OAuth routes, no token storage exist yet.

### What 3-legged OAuth requires (Schwab Trader API)

1. **Developer app registration** (Luis, outside this session) — register an
   app at developer.schwab.com, get Client ID/Secret, register a callback
   redirect URI (e.g. `https://<railway-app>/api/schwab/callback`).
2. **Authorization step** — user visits Schwab's auth URL, logs in, grants
   access; Schwab redirects back to our callback with a `code`.
3. **Token exchange** — server exchanges `code` for `access_token` (~30 min
   life) + `refresh_token` (~7 day life, single-use-ish — must be re-saved
   every refresh).
4. **Token storage** — needs a new table (e.g. `SchwabToken`: owner-scoped or
   single-tenant, access_token, refresh_token, expiresAt). Must NOT live in
   `.env` (tokens rotate constantly).
5. **Refresh flow** — background or on-demand refresh before each API call
   when `access_token` is near/at expiry; persist new `refresh_token` every time.
6. **Data endpoints** (read-only, once authenticated):
   - Accounts + positions (`/trader/v1/accounts`) — would replace CSV import.
   - Quotes (`/marketdata/v1/quotes`) — would replace Polygon price refresh.

### Proposed phasing (not yet started — confirm with Luis before coding)

- **Phase 1**: OAuth scaffolding — `server/lib/schwabAuth.js` (auth URL builder,
  token exchange, refresh), new `SchwabToken` table/migration (use `db push`
  per [[prisma_migration_drift]]), `/api/schwab/connect` + `/api/schwab/callback`
  routes. No data sync yet — just prove the OAuth round-trip and token persistence.
- **Phase 2**: Read-only account/position fetch — new endpoint to pull Schwab
  account positions and map into existing `Account`/`Position`/`Lot` shape,
  reusing the bucket-classification logic from `portfolioImport.js`. Likely
  runs alongside CSV import initially (not a hard cutover).
- **Phase 3**: Quotes via Schwab `marketdata` endpoint, replacing/supplementing
  `priceRefresh.js`'s Polygon calls.

### Open decisions for Luis

- Confirm Schwab developer app is registered (or whether that's step 1 of next session).
- Token storage: one shared `SchwabToken` row (single brokerage login covers
  all linked accounts) vs. per-owner — likely single, since Schwab login is
  account-holder-level, not per-`OwnerProfile`.
- Cutover strategy: keep CSV import as fallback/manual override, or fully
  replace once Phase 2 is validated?
- Does this touch `DESIGN_PRINCIPLES.md`-governed areas (allocator/concentration/backtest)?
  Likely **no** for Phases 1-2 (pure data ingestion, same Position/Lot shape
  the allocator already consumes) — but worth a quick check before Phase 2 lands.

---

## Key constraints (unchanged, carry forward)

- Analyst/Allocator firewall: analyst never receives portfolio data; allocator
  never receives transcripts.
- Tax: 15% federal LTCG/STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour wait: any position above 30% of portfolio before confirming hold.
- Git: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in
  sandbox. Pull before any changes, pull before push (`App.jsx` is high-conflict).
- Never paste `.env` contents.
- Prisma: stay on v6.19.3 (ignore v7 upgrade prompt). Schema changes via
  `npx prisma db push` from `server/`, never `migrate reset` — see [[prisma_migration_drift]].
- Testing: Luis tests on live Railway dev deployment only — no localhost env.
- Read `docs/architecture/DESIGN_PRINCIPLES.md` before touching analyst/allocator/
  concentration/backtest. Read `docs/architecture/DOMAIN.md` before touching
  candidate sourcing/filtering/evaluation.

---

## Backlog (updated priority order)

1. ✅ Dashboard cap flags use OwnerTickerConfig override — DONE 2026-06-13.
2. ✅ Domain tag on Ticker (multi-select, `domains String[]`) — DONE 2026-06-13.
3. **Owner assignment per ticker** — `users String[]` on Ticker; filter Radar per user.
4. **MovesCache** — OwnerProfile-scoped JSON cache; invalidate on new Analysis or price refresh.
5. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing. *(next up — see above)*
6. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity.
7. **Wire Polygon into 3-axis classifier** — replace manual price_cache.json with live calls.
8. **Reinvested dividends (DRIP)** — `Qual Div Reinvest` cash dividends currently ignored.
9. **ADR cost basis normalization** — BYDDY and similar.
10. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`.
11. **Per-user access control** — non-admin owners see only their own data. Schema ready
    (`OwnerProfile.clerkUserId` + `role`).
12. **New fixed-target position cap prompt (Option 3)** — surface "no cap set" row in
    Admin Position Caps table for ETF/commodity/crypto with no `OwnerTickerConfig` row.
13. **Third Investment Ideas sub-tab: "Out of scope"** — filtered Radar view, `inScope === false`.
14. **Rename "Type" → "Drivers" in UI labels** — header "Type"→"Drivers", "A"→"Single", "B"→"Multi". Cosmetic only.
15. **Model regression / migration tool** — shell script wrapping `dump_transcripts.py` +
    `backtest_from_files.py`, parameterized by model, diffed against saved baseline.
    Open: confirm shell-script approach; define "significant regression" threshold.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance.
