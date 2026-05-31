# Investment Agent — CoWork Handoff
**Date:** 2026-05-30  
**Picks up from:** CoWork_handoff_2026-04-21.md  
**Session work:** Portfolio Phase 2 — Account model, schema migrations, UI design

---

## What was completed this session

### 1. Schema migrations (both applied to Railway)

**Migration 1: `20260525125118_phase2_account_model`** — applied ✅
- Added `Account` model (see schema below)
- Replaced `Position.account String` with `Position.accountId Int` (FK to Account)
- Added `Lot.source String @default("manual")` — values: `"manual"` | `"import"`
- Dropped `CashBalance` table entirely (cash/margin folded into Account)
- Updated unique constraint: `Position @@unique([tickerId, accountId])`
- Backfilled 3 existing Position rows to a seeded "Schwab Taxable 1" account

**Migration 2: `add_bucket_override`** — schema written, **NOT YET RUN**
- Adds `Ticker.bucketOverride String?` — values: `"equity"` | `"etf"` | `"crypto"` | `"commodity"` | null
- null = fall back to `smartDefault(assetType, symbol)` at display time
- Run this before starting any Phase 2 backend work:
  ```bash
  export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-)
  npx prisma migrate dev --name add_bucket_override
  ```

### 2. Portfolio UI — fully designed and mockup approved

See mockup notes below. Design is locked; next step is building `Portfolio.jsx`.

---

## Current schema (full, as of this session)

```prisma
model Account {
  id             Int        @id @default(autoincrement())
  name           String                   // e.g. "Schwab Taxable 1"
  type           String                   // "taxable" | "ira" | "roth" | "custodial"
  owner          String                   // "Luis" | "Sofia" | "Kids"
  managed        Boolean    @default(false)
  ltcgRate       Float?                   // null → default 0.15
  stcgRate       Float?                   // null → default 0.15
  cashBalance    Float?
  cashAsOfDate   DateTime?
  marginBalance  Float?                   // positive = amount borrowed
  marginRate     Float?                   // annualised rate e.g. 0.0825
  marginRateAsOf DateTime?
  marginRateLog  Json?                    // [{rate: Float, effectiveDate: String}]
  marginAsOfDate DateTime?
  notes          String?
  createdAt      DateTime   @default(now())
  positions      Position[]
  @@unique([name, owner])
}

model Position {
  id         Int       @id @default(autoincrement())
  tickerId   Int
  ticker     Ticker    @relation(fields: [tickerId], references: [id])
  accountId  Int
  account    Account   @relation(fields: [accountId], references: [id])
  status     String    @default("active")  // "active" | "closed"
  notes      String?
  createdAt  DateTime  @default(now())
  closedAt   DateTime?
  lots       Lot[]
  @@unique([tickerId, accountId])
}

model Lot {
  id           Int       @id @default(autoincrement())
  positionId   Int
  position     Position  @relation(fields: [positionId], references: [id])
  shares       Float
  costBasis    Float     // per share
  acquiredDate DateTime
  source       String    @default("manual") // "manual" | "import"
  closedDate   DateTime?
  notes        String?
  createdAt    DateTime  @default(now())
}
```

`Ticker` additions (already in schema, `add_bucket_override` migration pending):
```prisma
bucketOverride String?  // "equity" | "etf" | "crypto" | "commodity" | null
```

---

## Portfolio UI design — locked spec

### Navigation: Option C — account card grid

- Top-level page shows a **summary banner** (4 metrics) + **account cards grid**
- Each account card is clickable; clicking opens an **inline expand panel** below the card (not a modal, not a tooltip — inline, to avoid iframe fixed-position issues)
- Card collapses if clicked again

### Summary banner (4 metrics)
1. Total portfolio (market value across all accounts)
2. Unrealised gain ($ and %)
3. Today's change ($ and %)
4. Net value (after margin debt)

### Account card contents
- Account name, type, owner, last-4 of account number
- "agent-managed" or "manual" badge
- Total market value
- Today's gain + all-time gain on one line
- Mini bucket pills: Equities $X · ETFs $X · Crypto $X · Commodities $X · Cash −$X

### Inline expand panel
- Header: account name + **3 action buttons** (see below)
- **5 bucket tabs** + Cash & margin tab
- Tabs show position count badge
- Each position row: Symbol, Name, Shares, Price, Mkt Value, **Total G/L** ($ + %), **Day G/L** ($ + %), % of acct, **Bucket pill**
- Bucket pill is clickable dropdown (equity / etf / crypto / commodity) — saves to `Ticker.bucketOverride`

### 3 action buttons (top-right of expand panel)

| Button | Icon | Behaviour |
|--------|------|-----------|
| **Import file** | upload | File picker accepting `.csv` (positions) and `.json` (transactions). Auto-detects format. |
| **Refresh prices** | refresh/sync | Hits Yahoo Finance API for all symbols in the account; updates market values. |
| **Connect brokerage** | link/plug | Greyed out initially. Future: Schwab API direct sync. Becomes "Sync now" once connected. |

### Bucket tabs and smart defaults

5 content tabs + 1 cash tab:
- **Equities** — direct stocks
- **ETFs** — generic ETFs with no override
- **Crypto** — override applied (e.g. IBIT)
- **Commodities** — override applied (e.g. IAU, SIVR, GLD)
- **Cash & margin** — cash balance, margin balance, margin rate, last-updated date

**`smartDefault(assetType, symbol)` logic** (computed at display time, not stored):
```javascript
const CRYPTO_SYMBOLS  = ['IBIT','GBTC','ETHE','BTC','ETH'];
const COMMODITY_SYMS  = ['GLD','IAU','SLV','SIVR','GDX','GDXJ','PPLT','PALL'];
const EQUITY_ETF_SYMS = ['QQQ','SPY','IVV','VTI','VOO','IWM','DIA','VGT','XLK'];

function smartDefault(schwabAssetType, symbol) {
  if (CRYPTO_SYMBOLS.includes(symbol))   return 'crypto';
  if (COMMODITY_SYMS.includes(symbol))   return 'commodity';
  if (EQUITY_ETF_SYMS.includes(symbol))  return 'equity';
  if (schwabAssetType === 'Equity')       return 'equity';
  return 'etf'; // default for "ETFs & Closed End Funds"
}

// Effective bucket = Ticker.bucketOverride ?? smartDefault(assetType, symbol)
```

Note: ETF tab shows holdings whose *structural* type is ETF regardless of bucket override, with an info note explaining the economic bucket. This keeps Schwab's classification visible while surfacing the economic meaning.

### Cash & margin tab contents
- Cash & money market balance (sourced from import; negative = margin debit)
- Margin rate (current)
- Balance as-of date
- Net cash position
- "Update manually" link → sendPrompt

---

## Portfolio manager suggestions — badge system (DESIGNED, NOT YET BUILT)

Agreed design (to be built after core Portfolio.jsx):

**Three signal types:**
- 🔴 Red dot = Trim or Exit on an existing position
- 🟢 Green dot = Add more to an existing position
- 🔵 Blue dot = New position suggested (not yet held)

**Flow:**
1. Account card shows a coloured dot in the top-right corner if any pending recommendations exist
2. Expand the panel → affected position rows show their badge
3. At bottom of the relevant tab: **"Suggested additions"** section shows new-position candidates (blue badge, "not held" styling)
4. Click any badge → side panel slides in with allocator reasoning, tax impact estimate, and "Review in RADAR" link

**Source:** Allocator layer output. Analyst/Allocator firewall still applies — analyst never receives portfolio data.

This feature is **not in scope for the next session** — build core Portfolio.jsx first.

---

## Brokerage file formats (Schwab)

### Positions CSV
- Line 1: metadata header — `"Positions for account {name} ...{last4} as of {time}, {date}"`
- Line 2: blank
- Line 3: column headers
- Lines 4–N: position rows
- Second-to-last row: `"Cash & Cash Investments"` — maps to `Account.cashBalance` (negative = margin debit)
- Last row: `"Positions Total"` — discard

**Columns used:** Symbol, Description, Qty, Price, Price Chng $, Price Chng %, Mkt Val, Day Chng $, Day Chng %, Cost Basis, Gain $, Gain %, % of Acct, Asset Type

**Asset Type values:** `"Equity"`, `"ETFs & Closed End Funds"`, `"Cash and Money Market"`

### Transactions JSON
- Structure: `{ FromDate, ToDate, TotalTransactionsAmount, TotalFeesAndCommAmount, BrokerageTransactions: [...] }`
- Each transaction: `{ Date, Action, Symbol, Description, Quantity, Price, "Fees & Comm", Amount, AcctgRuleCd }`
- Amounts are formatted strings: `"$106,334.06"`, `"-$143.64"` — strip `$`, `,`, handle negative prefix
- Some dates include settlement qualifier: `"11/17/2025 as of 11/14/2025"` — use the `as of` date (trade date) for LTCG/STCG holding period
- Max history: 4 years

**Action types for lot reconstruction (include):**
- `Buy` — opens a lot (includes assignment-triggered buys, already tagged as "Buy" by Schwab)
- `Sell` — closes/reduces lots (FIFO)
- `Reverse Split` — adjusts share count on existing lots

**Action types to ignore:**
- `Buy to Open`, `Sell to Open`, `Buy to Close`, `Sell to Close`, `Assigned`, `Expired` (options)
- `Journal`, `Bank Transfer`, `MoneyLink Transfer`, `Funds Received` (cash movements)
- `Margin Interest`, `Credit Interest`, `Qualified Dividend`, `Cash In Lieu` (income)

### Lot reconstruction algorithm
1. Upload positions CSV → seed current holdings (symbol, qty, total cost basis, asset type) as ground truth
2. Upload transactions JSON (4-year) → replay `Buy`/`Sell`/`Reverse Split` to get individual lot dates
3. Reconcile: lot quantities must sum to match positions CSV; flag discrepancy for manual review
4. **Trust Schwab's cost basis** from positions CSV as authoritative; use transactions only for lot *dates* and *quantities*
5. For `Reverse Split`: adjust all prior lots' share counts proportionally; per-share cost basis adjusts inversely

**Note:** Options-related transactions are out of scope. The agent manages a long-term equity portfolio; options writing/buying is opportunistic and not tracked by the agent.

---

## Build sequence for next session

### Step 0 — run pending migration (2 minutes)
```bash
cd server
export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-)
npx prisma migrate dev --name add_bucket_override
```

### Step 1 — backend routes for Account CRUD
File: `server/routes/portfolio.js` (full rewrite from Phase 1)

New endpoints needed:
```
GET    /api/portfolio/accounts              — list all accounts with position summary
POST   /api/portfolio/accounts              — create account
PATCH  /api/portfolio/accounts/:id          — update account (cash, margin, settings)
DELETE /api/portfolio/accounts/:id          — delete account (only if no positions)

GET    /api/portfolio/accounts/:id/positions — list positions with lots for one account
POST   /api/portfolio/positions             — create position (body: tickerId, accountId, lots[])
PATCH  /api/portfolio/positions/:id         — update position
DELETE /api/portfolio/positions/:id         — soft-delete (set status=closed)

POST   /api/portfolio/lots                  — add lot to existing position
DELETE /api/portfolio/lots/:id              — remove lot

PATCH  /api/portfolio/tickers/:id/bucket    — set bucketOverride

POST   /api/portfolio/accounts/:id/import   — import positions CSV + transactions JSON
POST   /api/portfolio/accounts/:id/refresh-prices — refresh market prices via Yahoo Finance
```

### Step 2 — import parser (`server/lib/portfolioImport.js`)
- `parsePositionsCSV(csvText)` → array of position objects
- `parseTransactionsJSON(jsonText)` → array of lot objects
- `reconstructLots(positions, transactions)` → merged lot array with dates
- `smartDefaultBucket(assetType, symbol)` → bucket string

### Step 3 — price refresh (`server/lib/priceRefresh.js`)
- Use `yahoo-finance2` npm package
- `refreshPrices(symbols[])` → `{ symbol: { price, dayChange, dayChangePct, asOf } }`
- Store last-known price on Position or return live (decide: store vs live)
- Recommendation: store `lastPrice`, `lastPriceAsOf`, `dayChangePct` on Position to avoid hitting Yahoo on every page load

### Step 4 — Portfolio.jsx
Build the approved mockup as a real React component. Key implementation notes:
- Inline expand: toggle state per account card, not a global modal
- Bucket pill dropdown: call `PATCH /api/portfolio/tickers/:id/bucket` on selection
- Import button: `<input type="file" accept=".csv,.json">` hidden, triggered by button click
- File type detection: check extension + sniff first character (`{` = JSON, else CSV)
- Refresh prices: POST to refresh endpoint, then re-fetch positions

### Step 5 — wire up to existing backend
- `server/index.js` already has `portfolioRouter` mounted at `/api/portfolio`
- Update import in portfolio.js to use new Prisma Account/Position/Lot models

---

## Existing Phase 1 routes to deprecate
Old routes in `server/routes/portfolio.js` used `account String` enum and `CashBalance` table:
- `GET /api/portfolio/cash` — deprecated (cash now on Account)
- `POST /api/portfolio/cash` — deprecated
- `POST /api/portfolio/positions` body field `account: String` — now `accountId: Int`

---

## Backlog (future sessions)

- **Position ticker rename/merge** — In the Edit Position modal, allow changing the ticker symbol while preserving all lots, gains, and loss history. Use case: corporate actions (spin-offs, conversions, renames) where a position appears under the wrong symbol (e.g. CSLR lots that should be under SPWR). Implementation: add a "Symbol" field to the edit modal; on save, look up or create the target ticker, update the position's tickerId, and if a position already exists for that ticker in the same account, merge the lots into it (same pattern as RADAR's symbol rename which merges transcripts). Handle the tickerId_accountId unique constraint carefully.

- **ADR cost basis normalization** — For ADR securities like BYDDY, the Schwab transaction JSON records execution price in the foreign underlying's terms, not the USD/ADR cost basis that Schwab uses authoritatively. Result: imported cost basis per share is wrong for ADRs. Fix: after JSON import, if the computed total cost basis differs significantly from the CSV cost basis for the same symbol, flag it for user review. Permanent fix: Schwab API integration, which provides authoritative cost basis directly.

- **Sortable lot detail rows** — within an expanded position row, allow sorting the lot sub-table by Acquired date (asc/desc) or Cost/sh (asc/desc). Currently lots render in whatever order they come from the DB. Clickable column headers, same pattern as the main position table.

- **Asset type dropdown in Add Position modal** — currently all manually-added positions land in Equities by default. Add a "Bucket" dropdown (Equity / ETF / Crypto / Commodity) to the Add Position modal that sets `Ticker.bucketOverride` on save. Pre-populate using `smartDefaultBucket(assetType, symbol)` so common symbols (GLD, QQQ, IBIT) auto-select the right bucket.

- **Add ticker without transcript (RADAR)** — ETFs, commodities, and crypto don't have earnings calls but need to exist as Ticker records so they can be held in Portfolio. Add a simple "Add ticker" button in RADAR that creates a minimal entry (symbol, name, shortName, type, status, inScope) without requiring a transcript. These tickers should be visually distinct in RADAR (e.g. "tracking only" badge) and excluded from thesis/recommendation views.

- **Schwab API integration** — replace CSV import and Polygon price refresh with live Schwab data. Schwab uses 3-legged OAuth (user authorizes via Schwab login). This becomes the "Connect brokerage" button already stubbed in the UI. Covers: real-time quotes, live positions, account balances. Polygon stays as fallback until Schwab is connected. See Schwab Individual Developer API docs at developer.schwab.com.

- **Wire Polygon into 3-axis classifier** — currently the classifier (`analysis/`) reads market data from `price_cache.json` built manually. Replace with live Polygon calls for market cap and P/E so the classifier can run without manual data prep. `POLYGON_API_KEY` is already in Railway env. Relevant endpoints: Ticker Details v3 (market cap), Financials (EPS/revenue for P/E and P/S).

---

## Key constraints (do not re-derive)
- Analyst/Allocator firewall: analyst never receives portfolio data; allocator never receives transcripts
- Tax: 15% federal LTCG and STCG, Florida (no state). Trim tax-advantaged accounts first.
- 48-hour waiting period for any position above 30% before confirming hold decision
- Git must be run on Luis's laptop — Dropbox mount strands `.git/index.lock` in sandbox
- Never paste `.env` contents

## Git push still pending
Phase 1 code + Phase 2 schema changes need to be pushed to Railway for auto-redeploy. Run from `investment-agent/`:
```bash
git add -A
git commit -m "Phase 2: Account model, bucket override, portfolio UI design"
git push
```
