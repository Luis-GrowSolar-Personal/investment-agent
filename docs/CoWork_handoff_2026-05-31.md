# Investment Agent — CoWork Handoff
**Date:** 2026-05-31  
**Picks up from:** CoWork_handoff_2026-05-30.md  
**Session work:** Portfolio Phase 2 build-out, UI standardization, RADAR overhaul

---

## What was completed this session

### Portfolio — full Phase 2 build

**Schema migrations applied to Railway:**
- `20260530140320_add_bucket_override` — adds `Ticker.bucketOverride`
- `20260530141406_add_position_price_fields` — adds `lastPrice`, `lastPriceAsOf`, `dayChangePct`, `dayChangeDollar` on Position

**Backend (`server/routes/portfolio.js` — full rewrite):**
- Account CRUD: GET list, POST create, PATCH edit (name/type/owner/managed/cash/margin), DELETE cascade
- Positions: GET by account, POST create (auto-creates ticker if not in RADAR), PATCH, DELETE soft
- Lots: POST add, DELETE remove
- Bucket override: PATCH `/tickers/:id/bucket`
- Import: `POST /accounts/:id/import` — accepts CSV (AI-parsed via Claude Haiku) or JSON (transaction lot reconstruction), or both
- Price refresh: `POST /accounts/:id/refresh-prices` — uses Polygon.io prev-close endpoint
- Position rename/merge: `POST /positions/:id/rename`

**New libs:**
- `server/lib/portfolioImport.js` — AI CSV parser, transaction JSON parser, FIFO lot reconstructor, `smartDefaultBucket()`
- `server/lib/priceRefresh.js` — Polygon.io price refresh with 429 retry, crypto symbol mapping

**Frontend (`client/src/pages/Portfolio.jsx` — full rewrite):**
- Summary banner: total portfolio, unrealised gain, today's change, net value (cash + positions − margin)
- Account card grid: collapsible cards, bucket pills, today/all-time gain
- Inline expand panel: 5 bucket tabs (Equity/ETF/Crypto/Commodity/Cash&Margin) + position table
- Position table: sortable columns, drill-down lots, bucket dropdown, edit lots, rename ticker, delete
- Action buttons: + Add position, $ Set cash, ⬆ Import file, ↻ Refresh prices
- Modals: Add account (with agent-managed), Edit account (with type-change 2-step warning), Add position, Edit lots, Rename ticker/merge, Update cash, Delete account (type-to-confirm 2-step)

### RADAR overhaul

- **Collapsible frames** — Portfolio and Watchlist sections now live in bordered cards matching Portfolio style; ▶/▼ expand/collapse
- **Drag-to-pan** — grab cursor on table background; drag left/right to scroll wide tables
- **Full edit modal** — ✎ opens modal with: Symbol (merge-aware), Company name, Type A/B, Cap%, Status (watchlist↔portfolio), In-scope toggle. Replaces inline rename row + separate promote/demote buttons.
- **Sortable columns** — Symbol, Company, Type, Cap%, Calls, Last Updated (all with ↕/↑/↓)
- **+ New Ticker** — blue button upper-right matching Portfolio style; opens modal for ETF/commodity/crypto without transcript
- **⟳ Re-score** — grey icon left of + New Ticker; rescores all calls
- **Stale transcript badge** — ⏰ replaced with outlined `!` circle (stroke style matching other icons)

### UI standardisation (per UI_SPEC.md)

- **Icons for actions, labels for information** — rule applied across RADAR and Portfolio
- **Icon set**: ✎ edit, × remove, 👁 view, ⟳ resync — all stroke style, grey default, coloured hover
- **Drill-down triangles** — ▶/▼ left of symbol everywhere (Advisory Feed pattern)
- **Expand/collapse** — ▶/▼ throughout; sort columns use ↑/↓/↕
- **Advisory Feed sort** — Symbol and Date bidirectional (↕ shown on inactive columns)
- **Bucket pill** — white-space: nowrap fixed (▾ no longer wraps)
- **"legacy" badge** — box-enclosed style matching RADAR's SPEC/EST chips
- **RADAR rename → modal** — matches Portfolio's modal pattern
- `docs/UI_SPEC.md` created — covers icons, badges, tables, modals, colour palette

### Price data

- Switched from yahoo-finance2 (broken on Railway) to Polygon.io (Massive)
- `POLYGON_API_KEY` in Railway DEV env
- Free tier uses prev-close endpoint; 429 retry with 15s wait; 500ms between calls
- `BTC` removed from crypto raw list (it's the Grayscale ETF on NYSE, not raw crypto)

### Import pipeline

- AI-powered CSV parser (Claude Haiku) — format-agnostic, works across brokerages
- Transaction JSON import — FIFO lot reconstruction from Buy/Sell/Reverse Split/Reinvest Shares
- Qty parser fixed: strips commas (`"20,115"` → `20115`)
- Auto-creates ticker records for unknown symbols on import (inScope: false)

---

## Current state

**Accounts loaded and reconciled:**
- Eduardo Custodial (taxable) — ~$29.8K, 7 equities + 3 ETFs + 1 commodity + $4,884 cash
- Andrea Custodial (taxable) — similar profile
- Luis ROTH IRA — ~$24.5K, ENVX (4 lots, pre-2022) + SPWR

**Known data issues (manual correction needed):**
- BYDDY cost basis is wrong (ADR pricing in transaction JSON ≠ Schwab USD cost basis) — edit via ✎ lots
- CSLR/SPWR relationship: use the rename/merge icon on CSLR positions to reassign to SPWR

**Dev workflow:**
- Dev branch → `investment-agent-dev-production.up.railway.app`
- Main branch → prod (not yet promoted this session)
- Git must run on Luis's laptop (Dropbox mount issue in sandbox)

---

## Backlog (priority order)

1. **Schwab API integration** — 3-legged OAuth; replaces CSV import + Polygon pricing; activates "Connect brokerage" button. See developer.schwab.com. `POLYGON_API_KEY` stays as fallback.

2. **Asset type dropdown in Add Position modal** — manually-added positions default to Equity. Add Bucket dropdown (Equity/ETF/Crypto/Commodity) pre-populated via `smartDefaultBucket()`.

3. **Sortable lot detail rows** — clickable Acquired/Cost/sh column headers in the lot sub-table.

4. **Reinvested dividends (DRIP)** — `Reinvest Shares` already creates lots but `Qual Div Reinvest` (cash) is ignored. Full support: pair cash dividend with resulting share purchase, add DRIP source badge, correct cost basis.

5. **ADR cost basis normalization** — BYDDY and similar: transaction JSON price ≠ Schwab USD cost basis. Post-import, flag positions where computed cost basis differs significantly from CSV ground truth.

6. **Crypto exchange accounts (Kraken)** — new account type `"crypto_exchange"`: taxable, exchange-specific API, staking support (treated as DRIP). Display as "Crypto Exchange" badge.

7. **Wire Polygon into 3-axis classifier** — replace manual `price_cache.json` with live Polygon calls for market cap, P/E, P/S. `POLYGON_API_KEY` already in Railway env.

---

## UI style guide

**`docs/UI_SPEC.md` is the authoritative style reference. Read it before building any new UI component.**

Key rules (full detail in the spec):
- **Icons for actions, labels for information** — ✎ edit, × remove, 👁 view, ⟳ resync; all stroke style, 13–15px, grey default, coloured hover
- **Badges/pills** — text labels with background tint + border; use spec colours for thesis health, recommendation, trajectory
- **Drill-down** — ▶/▼ left of symbol/name; sort columns use ↑/↓/↕
- **Tables** — 10–11px uppercase headers, `#1e2330` row borders, `#0d1018` hover, primary data `#f1f5f9`, secondary `#94a3b8`
- **Modals** — `#0f1117` background, `border-radius: 10px`, cancel + primary button pattern; destructive = red with type-to-confirm
- **Frames** — collapsible bordered cards (`border: 1px solid #1e2330`, `border-radius: 10px`) for both Portfolio accounts and RADAR sections

---

## Key constraints (do not re-derive)

- **Analyst/Allocator firewall**: analyst never receives portfolio data; allocator never receives transcripts
- **Tax**: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- **48-hour wait**: any position above 30% of portfolio before confirming hold
- **Git**: must run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- **Never paste `.env` contents**
- **Transcript cap**: watchlist = 50 (raised from 6); portfolio = unlimited
- **Polygon free tier**: prev-close only (15-min delayed); snapshot endpoint requires paid plan
- **Import ground truth**: CSV is authoritative for share counts and cost basis; transaction JSON provides lot dates only. Never trust JSON-only import for positions with corporate actions.
