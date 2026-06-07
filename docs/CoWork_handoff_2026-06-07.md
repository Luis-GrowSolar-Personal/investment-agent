# Investment Agent — CoWork Handoff
**Date:** 2026-06-07
**Picks up from:** CoWork_handoff_2026-06-06.md
**Session work:** Admin tab bugs, Users merge, domain expansion, nav restructure, /analyst direct route

---

## What was completed this session

### Admin tab bug fixes
- **"Effective max: 0 positions" badge** — `toUI()` wasn't converting null numerics to `''`, so `Number(null) = 0`. Fixed by normalizing all numeric fields to `''` in `toUI()`.
- **Partial draft on accidental field touch** — `set()` spread `null` onto a partial object. Fixed with `d ?? toUI(profile)` as base in `set()`.

### Users tab merged into Admin tab
Users tab removed as standalone nav item. Admin now hosts both owner management (New Owner modal, delete per card, goal progress bar, account count) and per-owner config. nav reduced to 6 → 5 tabs.

### Domain catalog expanded (5 → 31 industries)
Replaced 5-item flat checkbox list with 31 industries in 9 groups:
- Energy Production, Energy Infrastructure, Energy Technology, Energy Materials, Energy Finance
- Technology, Healthcare, Consumer, Financial Services (future expansion)

Rendered as a grouped, scrollable picker (max-height 280px, 2-column grid). IDs are stable strings safe for DB storage.

### OwnerProfile auth fields
Added `clerkUserId String? @unique` and `role String @default("user")` to OwnerProfile schema. Migration file: `20260606000002_add_owner_profile_auth_fields/migration.sql`. Fields wired into Admin UI (text field + segmented control) and users.js route. Luis's row manually updated to `role = 'admin'` via Railway Console.

### Railway auto-migration fixed
`nixpacks.toml` build phase now runs both `prisma generate` and `prisma migrate deploy` — previously only `generate` ran, requiring all migrations to be applied manually.

### Nav restructure
**Before:** Stock Analyst | Stock Radar | Advisory Feed | Portfolio | Users | Dashboard | Admin  
**After:** Portfolio Manager | At a Glance | Accounts | Investment Ideas | Admin

New pages:
- `PortfolioManager.jsx` — placeholder for Recommended Moves engine
- `InvestmentIdeas.jsx` — sub-tab wrapper (Ideas | Analyst | Commentary) with display:none pattern

Stock Analyst (Evaluator), Stock Radar, and Advisory Feed folded into Investment Ideas sub-tabs.

### /analyst direct-access route
Added `/analyst` as a hidden (not in nav) direct URL that renders Evaluator standalone — no sub-tab chrome. Enables opening multiple browser tabs in parallel for bulk transcript uploads.

To use: navigate to `<your-railway-url>/analyst` and open as many tabs as needed.

---

## Architecture notes

### OwnerProfile auth fields (backlog #9)
Schema is seeded. When multi-user login is built:
- Backend: `resolveOwner(req)` middleware — Clerk JWT → OwnerProfile lookup by clerkUserId
- Frontend: `useOwnerContext()` hook — components filter to logged-in owner
- Analyst layer (Radar/transcripts) stays global; allocator layer (Portfolio, Moves, Admin) is per-owner
- Biggest lift: Ticker has no `owner` column; analyst side intentionally stays global

### Domain tag on Ticker (backlog)
Domain assignment should live in Investment Ideas (Radar), admin-only, one canonical assignment per ticker. Prevents per-user "ping-pong" on classifications like TSLA (EV vs. energy). Schema change needed: `domain String?` on Ticker.

### Owner assignment per ticker (backlog)
`users String[]` on Ticker — "AVGO is semis, but only Luis is focused on it." Enables per-user radar filtering. Schema change needed alongside domain tag.

---

## Key constraints (unchanged)
- Analyst/Allocator firewall: analyst never receives portfolio data; allocator never receives transcripts
- Tax: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour wait: any position above 30% of portfolio before confirming hold
- Git: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- Never paste `.env` contents
- Transcript cap: watchlist = 50; portfolio = unlimited
- Prisma: stay on v6.19.3 — v7 is a breaking upgrade, defer to its own session
- Testing: Luis tests on live Railway dev deployment only — no localhost env
- Cap% rule: MIN(ticker.capPercent, analyst.capPercent) — user wins
- Type B cap: flat 50% (variable cap experiment retired 2026-05-17)

---

## Backlog (priority order)

1. **Recommended Moves engine** — next build priority. Per-account action plan:
   - Specific trim amounts: `(currentPct − targetPct) × portfolioValue` in $ and shares
   - Specific add amounts: `(recommendedSize − currentPct) × portfolioValue`
   - Watchlist promotion candidates ranked by: trajectory score + thesis health + type
   - Capital flow plan: "Trim SPWR → $X freed → buy META (Add, improving, Type B)"
   - "Sell everything" scenario: compute net tax position, propose new allocation from scratch
   - Read OwnerProfile params (barbell ratio, specExitSpeed, maxPositions, etc.)

2. **Wire OwnerProfile params into allocator** — dashboard route ignores Admin settings. estSpecRatio, maxPositions, minPositionDollar, taxSensitivity, specExitSpeed should all gate allocator output.

3. **Domain tag on Ticker** — add `domain String?` to Ticker schema; assign in Investment Ideas/Radar with an admin-only modal.

4. **Owner assignment per ticker** — add `users String[]` to Ticker; filter Radar view per user.

5. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing.

6. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity.

7. **Wire Polygon into 3-axis classifier** — replace manual price_cache.json with live Polygon calls.

8. **Reinvested dividends (DRIP)** — `Qual Div Reinvest` cash dividends currently ignored.

9. **ADR cost basis normalization** — BYDDY and similar: transaction JSON price ≠ Schwab USD cost basis.

10. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`.

11. **Per-user access control** — allow non-admin owners to log in and see only their own data.
    - Schema ready: `OwnerProfile.clerkUserId` + `OwnerProfile.role` added 2026-06-06.
    - See architecture notes above for full implementation plan.
