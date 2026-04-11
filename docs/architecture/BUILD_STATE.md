# Portfolio Analyst — Build State
*Last updated: April 11, 2026*

## What Has Been Built

### Step 1: Earnings Call Evaluator ✅
- Single Express route POST /api/evaluate
- Accepts pasted transcript, calls claude-sonnet-4-20250514
- Returns structured 10-section narrative analysis
- Structured score block (---STRUCTURED---) appended to every 
  evaluation and parsed server-side
- Auto-extracts ticker symbol, company name, short name, call date 
  from transcript using Claude
- Separate Analyze and Save steps (review before committing to DB)
- Clear button resets all fields
- React frontend: textarea, analyze button, results panel,
  editable metadata fields, save button, confirmation message

### Step 2: Infrastructure ✅

**Authentication (Clerk)**
- Email + password login
- Public sign-up disabled — invite only via Clerk dashboard
- Session token validated on every API request
- client/.env holds VITE_CLERK_PUBLISHABLE_KEY
- Root .env holds CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY

**Database (PostgreSQL on Railway)**
- Prisma ORM
- Three models: Ticker, Transcript, Analysis
- Full structured score fields on Analysis model
- Ticker has status: watchlist | portfolio
- Ticker has shortName for display
- Transcript has standardized title format:
  "{shortName} ({symbol}) Q{n} {year} Earnings Call Transcript"
- Migrations applied to Railway dev database

**RADAR Module**
- React Router installed, nav bar with Evaluator | RADAR tabs
- Two sections: Portfolio tickers and Watchlist tickers
- Color-coded thesis health badges:
  Strengthening=green, Intact=blue, Weakening=amber, Broken=red
- Color-coded recommendation badges:
  Add=green, Hold=blue, Trim=amber, Exit=red
- Expandable thesis trajectory rows (chronological history)
- Promote watchlist → portfolio (preserves all transcripts)
- Demote portfolio → watchlist
- Delete ticker (cascades to transcripts and analyses)
- Delete individual transcripts from trajectory view
- Watchlist cap: 6 transcripts max, oldest auto-discarded on 7th
- Portfolio tickers: unlimited transcript history
- Re-score Radar button

## Current Data State (as of last session)
Portfolio tickers: AAPL, AMPX, EOSE, SPWR, TSLA, TTD
Watchlist tickers: none
All transcripts loaded manually from Seeking Alpha / Motley Fool

## What Is Next

### Step 3: Portfolio Module
- Upload Schwab CSV export or manual position entry
- Store: ticker, shares, account type (taxable/IRA/Roth), 
  cost basis, current % of portfolio
- ETF tracking (separate from RADAR — no transcript evaluation)
- ETF role classification: defensive / growth / commodity

### Step 4: Dashboard / Allocator (Layer 1)
- All positions with latest recommendation and thesis health
- Concentration cap enforcement (Type A: 35%, Type B: 40-60%)
- Tax-aware trim sequencing (tax-advantaged accounts first)
- Explicit tax cost calculation on every trim recommendation
- 48-hour waiting period flag for positions above 30%
- Enough Number module: check portfolio value vs $6M threshold
- Graduated exit ratchet status per ticker

### Step 5: Alerts Module
- Press release / 8-K classification
- Three outputs: Thesis-positive / Thesis-negative / Noise
- Only thesis-relevant items surface as notifications

### Step 6: Automated Transcript Ingestion
- Periodic scraping of Seeking Alpha for tracked tickers
- Chronological ingestion, auto-trigger evaluation
- Possibly upgrade to Polygon.io for reliability

### Step 7: Backtesting Module
- Load historical positions and transcripts
- Run evaluator in chronological order
- Compare recommended actions to actual outcomes
- Use anonymization prompt to prevent look-ahead bias

## Open Questions / Pending Decisions
- ETF evaluation approach: confirmed as Portfolio module only,
  no RADAR, manual review, role classification
- thesisDelta is currently self-reported by Claude at eval time.
  Future improvement: compute from database by comparing current
  analysis against prior stored analysis.
- Automated transcript ingestion: deferred to Step 6.
  Manual copy-paste from Seeking Alpha for now.

## Known Issues / Technical Debt
- thesisDelta computed by Claude, not from DB comparison
- No test suite yet
- No production deployment yet (Railway prod service exists 
  but not yet deployed to)

## Architecture Reminders
- Analyst / Allocator firewall is sacred — analyst never sees
  portfolio data, allocator never sees transcripts
- Layer ordering is 3→2→1, never 1→2→3
- Trim proceeds must have a destination before trim executes
- Read DESIGN_PRINCIPLES.md before building any new module

## Repository
GitHub: Luis-GrowSolar-Personal/investment-agent
Active branch: dev
Railway: dev service watches dev branch
