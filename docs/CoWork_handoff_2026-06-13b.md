# Investment Agent — CoWork Handoff

**Date:** 2026-06-13
**Picks up from:** CoWork_handoff_2026-06-13.md
**Session work:** Backlog item 5 — Phase 1 (Schwab OAuth scaffolding) AND Phase 2
step 1 (read-only accounts/positions preview). Both built, deployed, and
**confirmed working live** against Luis's real Schwab accounts.
**Next session focus:** Phase 2 account-mapping/reconciliation (see below).

---

## ✅ Confirmed working this session (live test)

- Registered new Schwab developer app ("AI Powered Portfolio Manager"),
  selected both **Accounts and Trading Production** and **Market Data
  Production** API products, callback URL set to
  `https://investment-agent-dev-production.up.railway.app/api/schwab/callback`.
- `npx prisma db push` ran clean — `SchwabToken` table live in Railway Postgres.
- Set `SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` / `SCHWAB_REDIRECT_URI` on
  Railway, code committed + pushed + deployed.
- `/api/schwab/connect` → Schwab login → consent → redirected back to
  `/?schwab=connected`. Token exchange succeeded.
- `/api/schwab/accounts` (new this session, see below) returned real,
  correctly-shaped data: multiple accounts with masked numbers, hash values,
  cash/liquidation balances, and full position lists (symbols, asset types,
  quantities, market values, average prices) — e.g. SIVR, BYDDY, AMPX, NVDA, etc.

**Important finding:** Luis authorized *every* Schwab account he controls
during the consent step — including accounts that have never been uploaded
via CSV and don't exist in the local `Account` table yet. See "Phase 2 next
steps" below.

---

## What shipped this session (Phase 1 + Phase 2 step 1)

CSV import + Polygon pricing are untouched and still the active data path —
the new endpoints are read-only and additive.

1. **`server/prisma/schema.prisma`** — new `SchwabToken` model (singleton row,
   id: 1). Holds `accessToken`, `refreshToken`, `expiresAt`. One Schwab login
   is account-holder level and covers all linked accounts, so this is a
   single shared row, not per-OwnerProfile (per Luis's confirmation last
   session).

2. **`server/lib/schwabAuth.js`** (new) —
   - `getAuthUrl()` — builds `https://api.schwabapi.com/v1/oauth/authorize?...`
   - `exchangeCodeForTokens(prisma, code)` — POSTs to
     `https://api.schwabapi.com/v1/oauth/token` with Basic auth
     (`base64(client_id:client_secret)`), persists tokens.
   - `refreshAccessToken(prisma)` — refresh-token grant; Schwab rotates the
     refresh_token on every call, new one is persisted each time.
   - `getValidAccessToken(prisma)` — returns a live access_token, refreshing
     automatically if expired/near-expiry (60s buffer). **This is the
     function Phase 2 should call** before any Trader API request.
   - `getStatus(prisma)` — connection status only, never returns token values.

3. **`server/routes/schwab.js`** (new) —
   - `GET /api/schwab/connect` (auth required) → redirects to Schwab's
     authorization page.
   - `GET /api/schwab/callback` (no auth — see code comment for why) →
     exchanges `?code=` for tokens, persists them, redirects to
     `/?schwab=connected`.
   - `GET /api/schwab/status` (auth required) → `{ connected, expiresAt,
     accessTokenExpired, updatedAt }`.

4. **`server/index.js`** — registered `schwabRouter` at `/api/schwab`.

5. **`.env.example`** — added `SCHWAB_REDIRECT_URI` (must exactly match the
   callback URL registered in the Schwab developer app).

6. **`server/lib/schwabAccounts.js`** (new, Phase 2 step 1) — `previewAccounts(prisma)`:
   - Calls `GET /trader/v1/accounts/accountNumbers` to map raw account numbers
     to the `hashValue`s the Trader API requires for account-scoped calls.
   - Calls `GET /trader/v1/accounts?fields=positions` for full balances + positions.
   - Returns `{ schwabAccounts, localAccounts }` — `schwabAccounts` masked
     (`***1234`) with `hashValue`, type, cashBalance, liquidationValue, and
     position list (symbol, assetType, quantities, marketValue, averagePrice);
     `localAccounts` is the existing `Account` table (id, name, type, owner,
     cashBalance) for side-by-side comparison. No DB writes.

7. **`server/routes/schwab.js`** — added `GET /api/schwab/accounts`
   (auth required) → `previewAccounts(prisma)`.

OAuth endpoint details (auth URL, token URL, Basic-auth header, grant types,
~30 min access token / ~7 day rotating refresh token) verified against
current Schwab Trader API documentation via web search this session.

---

## Outstanding from prior session (uncommitted, not touched this session)

`git status` shows a pending modification to `docs/CoWork_handoff_2026-06-07c.md`
and an untracked `server/scripts/backfill_domains.js` from before this
session started. Left as-is — bundle with this session's commit or handle
separately, Luis's call.

---

## Phase 2 next steps (account reconciliation — not started)

Phase 2 step 1 (read-only preview) is done. The live test surfaced the core
design problem for step 2:

**Problem:** Luis authorized every Schwab account he controls during OAuth
consent. `/api/schwab/accounts` returns all of them (e.g. `***8439` CASH with
12 positions incl. SIVR, BYDDY, AMPX, NVDA). But the local `Account` table
only has the subset populated via CSV upload historically — some
Schwab-reported accounts have no corresponding local row at all.

**Proposed approach:**
1. Add `schwabAccountHash String?` (unique, nullable) to the `Account` model
   — links a local account row to a Schwab `hashValue`.
2. Matching logic (new sync endpoint, e.g. `GET/POST /api/schwab/sync`):
   - For each `schwabAccounts[]` entry, check if any local `Account` already
     has that `hashValue` → update balances/positions.
   - For Schwab accounts with no match: either (a) surface them in the UI for
     Luis to confirm before creating a local row, or (b) auto-create with a
     sensible default name/type/owner and let Luis edit after. Leaning toward
     (a) — account creation has owner/type implications (tax treatment,
     allocator scoping) that shouldn't be guessed.
   - For local accounts with no Schwab match (e.g. manually-tracked or
     non-Schwab accounts like Kraken — see backlog item 10): leave untouched.
3. UI: likely lands in the existing "+Add Account" flow / Portfolio page —
   show a reconciliation view (Schwab account ↔ local account, or "new")
   before committing any writes.
4. Once matching exists, decide how positions/lots get written: full
   replace vs. diff-and-update (affects cost-basis/lot history — check
   against `Lot` model and `DESIGN_PRINCIPLES.md` before landing, since this
   starts touching data the allocator consumes).

Quick check before landing: confirm this still doesn't touch
`DESIGN_PRINCIPLES.md`-governed areas (expectation: pure data ingestion into
the same Account/Position/Lot shape the allocator already consumes — but the
lot-history question in (4) above needs a deliberate look).

Phase 3 (quotes via Schwab `marketdata`, replacing Polygon) — unchanged, still
backlog item 7 territory.

---

## Key constraints (unchanged, carry forward)

- Analyst/Allocator firewall: analyst never receives portfolio data; allocator
  never receives transcripts.
- Tax: 15% federal LTCG/STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour wait: any position above 30% of portfolio before confirming hold.
- Git: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in
  sandbox. Pull before any changes, pull before push (`App.jsx` is high-conflict).
- Never paste `.env` contents.
- Prisma: stay on v6.19.3, schema changes via `db push` from `server/`, never
  `migrate reset` — see [[prisma_migration_drift]].
- Testing: Luis tests on live Railway dev deployment only — no localhost env.

---

## Backlog (updated priority order)

1. ✅ Dashboard cap flags use OwnerTickerConfig override — DONE 2026-06-13.
2. ✅ Domain tag on Ticker — DONE 2026-06-13.
3. **Owner assignment per ticker** — `users String[]` on Ticker; filter Radar per user.
4. **MovesCache** — OwnerProfile-scoped JSON cache; invalidate on new Analysis or price refresh.
5. **Schwab API integration** — Phase 1 ✅ + Phase 2 step 1 ✅ (both confirmed
   working live against real Schwab accounts, 2026-06-13). Next: Phase 2
   account reconciliation (see "Phase 2 next steps" above).
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
