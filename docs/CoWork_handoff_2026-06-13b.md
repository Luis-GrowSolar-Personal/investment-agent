# Investment Agent — CoWork Handoff

**Date:** 2026-06-13
**Picks up from:** CoWork_handoff_2026-06-13.md
**Session work:** Backlog item 5, Phase 1 — Schwab OAuth scaffolding. DONE (code only — not yet run/tested).
**Next session focus:** Luis runs `db push` + sets env vars + tests the OAuth round-trip, then Phase 2 (account/position fetch).

---

## What shipped this session (Phase 1)

Pure scaffolding — no account/position data is fetched yet, and CSV import +
Polygon pricing are untouched and still the active data path.

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

OAuth endpoint details (auth URL, token URL, Basic-auth header, grant types,
~30 min access token / ~7 day rotating refresh token) verified against
current Schwab Trader API documentation via web search this session.

---

## Before this works — Luis to do

1. **Run schema migration** from `server/`:
   ```
   DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma db push
   ```
   (per [[prisma_migration_drift]] — `db push`, never `migrate reset`)

2. **Set env vars** (Railway dev service, and local `.env` if used):
   - `SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` — already registered per
     Luis (confirmed this session).
   - `SCHWAB_REDIRECT_URI` — set to `https://<railway-dev-app>/api/schwab/callback`
     and make sure this **exact** URL is also registered as the callback in
     the Schwab developer app dashboard.

3. **Test the round-trip**: visit `/api/schwab/connect` while logged in →
   log into Schwab → approve → should land back on `/?schwab=connected`.
   Then check `/api/schwab/status` shows `connected: true`.

---

## Outstanding from prior session (uncommitted, not touched this session)

`git status` shows a pending modification to `docs/CoWork_handoff_2026-06-07c.md`
and an untracked `server/scripts/backfill_domains.js` from before this
session started. Left as-is — bundle with this session's commit or handle
separately, Luis's call.

---

## Phase 2 (next up, not started)

Read-only account/position fetch:
- New endpoint (e.g. `GET /api/schwab/sync` or similar) that calls
  `getValidAccessToken()`, hits `/trader/v1/accounts` (with the
  `accountNumbers` → hash-value lookup Schwab requires), and maps the result
  into the existing `Account`/`Position`/`Lot` shape — reusing
  `smartDefaultBucket()` from `portfolioImport.js`.
- Runs alongside CSV import initially (not a hard cutover — confirmed last
  session).
- Quick check before landing: confirm this still doesn't touch
  `DESIGN_PRINCIPLES.md`-governed areas (expectation: no, pure data
  ingestion into the same Position/Lot shape the allocator already consumes).

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
5. **Schwab API integration** — Phase 1 ✅ (code, this session, untested). Phase 2
   (account/position fetch) next.
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
