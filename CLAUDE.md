# Investment Agent — Claude Code Configuration

## Important Notes
- Never paste .env contents directly — contains API keys
- Always read docs/architecture/DESIGN_PRINCIPLES.md before 
  building any new module that touches the analyst, allocator, 
  concentration rules, or backtest integrity
- Always read docs/architecture/DOMAIN.md before building any
  module that sources, filters, or evaluates investment candidates

## Project Overview
Personal investment analysis and portfolio management tool.
React frontend, Node.js/Express backend, PostgreSQL database,
Clerk auth, Anthropic API for AI analysis. Hosted on Railway.

## Owner
Personal account — Luis. Separate from Windmar Energy entirely.

## Tech Stack
- Frontend: React + Tailwind CSS (Vite)
- Backend: Node.js + Express
- Database: PostgreSQL (Railway) via Prisma ORM
- Auth: Clerk (email + password, no SMS)
- AI: Anthropic API (claude-sonnet-4-20250514)
- Hosting: Railway (dev and prod services)
- Transcript source: Manual copy-paste (EDGAR/Polygon.io planned)

## Repository Structure
investment-agent/
├── analysis/          — Python backtesting scripts and data
│   └── data/          — price_cache.json, backtest CSVs
├── client/            — React frontend (Vite)
│   └── src/
│       ├── components/ — NavBar
│       └── pages/     — Evaluator, Radar
├── server/            — Node.js/Express backend
│   ├── routes/        — evaluate, save, radar
│   ├── lib/           — prisma singleton
│   └── prisma/        — schema, migrations
└── docs/
    ├── EVALUATION_PROMPT.md
    ├── Investment_Agent_Handoff_Brief.docx
    └── architecture/
        ├── DESIGN_PRINCIPLES.md
        └── DOMAIN.md

## Environment Variables
All credentials in root .env — never committed to GitHub.
client/.env — contains VITE_CLERK_PUBLISHABLE_KEY only.
Root .env contains:
  ANTHROPIC_API_KEY
  DATABASE_URL
  CLERK_PUBLISHABLE_KEY
  CLERK_SECRET_KEY
  VITE_CLERK_PUBLISHABLE_KEY
  PORT
  NODE_ENV

## Database Schema (Prisma)
- Ticker: id, symbol, name, shortName, type, capPercent, 
  status (watchlist|portfolio), notes, createdAt
- Transcript: id, tickerId, callDate, title, rawText, createdAt
- Analysis: id, transcriptId, rawOutput, thesisHealth, 
  recommendation, recommendedSize, thesisDelta, 
  freshMoneyAllocation, stumbleType, threatMechanismImpaired,
  credibilityDelta, activeDriverCount, ratchetTranche,
  blindSpotsTriggered, capPercent, mitigationArgumentPresent,
  mitigationCapabilityTrackRecord, createdAt

## Key Design Decisions — Do Not Re-Derive
1. Agent operates in Layer 3→2→1 sequence (find → classify
   → enforce). Not 1→2→3.
2. Two position types: Type A (single-driver, fixed ~35% cap)
   and Type B (multi-driver platform, variable 40-60% cap).
3. Graduated exit ratchet: Weakening → trim to cap. No
   improvement after one quarter → trim 40% more. Second
   quarter deterioration → 3%. Third → exit.
4. Tax: 15% federal LTCG and 15% STCG (matches owner's
   blended ordinary marginal rate), Florida (no state tax).
   Trim tax-advantaged accounts first — even though LTCG and
   STCG rates are equal, tax-advantaged accounts are 0% so
   the ordering preference still holds.
5. 48-hour waiting period for any position above 30% of
   total portfolio before confirming hold decision.
6. Mitigation argument discount: when management claims
   capability X will offset headwind Y, check X's own
   track record specifically — not overall management 
   credibility.
7. Analyst / Allocator firewall: analyst never receives 
   portfolio data. Allocator never receives transcripts.
   They communicate only through the structured score.
8. Watchlist tickers: max 50 transcripts, oldest auto-discarded
   (raised from 6 to support historical backtest loading).
   Portfolio tickers: unlimited history.
9. Enough number: $10M. Active management justified only 
   below $6M portfolio value.

## Investment Universe (Circle of Competence)
Defined in full in docs/architecture/DOMAIN.md — that file
is the single authoritative source. Do not re-derive or
summarize the domain definition here.

Summary: Tier 1 (solar, energy storage, semiconductors),
Tier 2 (IT/software/cloud, crypto scoped to mass-adoption
use cases). Defense technology removed as a standalone domain.
Agent never recommends outside this universe.

## ETF Tracking
ETFs (SPY, QQQ, GLD, SLV, IBIT) tracked in Portfolio module
only — not in RADAR. No transcript evaluation. Role 
classification: defensive / growth / commodity.
Note: Bitcoin ETF and NASDAQ ETF are risk-on and correlated
to active positions. Gold is the only true defensive hedge.

## Build Sequence
Step 1: ✅ Earnings call evaluator (POC) — COMPLETE
Step 2: ✅ Clerk auth, PostgreSQL, Prisma, RADAR module — COMPLETE
Step 3: Portfolio module (Schwab CSV upload, position tracking)
Step 4: Dashboard (allocator, concentration rules, Layer 1)
Step 5: Alerts module (press releases, thesis classification)
Step 6: Automated transcript ingestion (EDGAR/Seeking Alpha)
Step 7: Backtesting module (historical dry run)
Step 8: Opportunity Scanner (Layer 3 — trend monitoring, 
        candidate surfacing, Radar Inbox)

## Current Build State
- Evaluator: working, structured score output, auto-extract metadata
- RADAR: working, watchlist/portfolio sections, thesis trajectory,
  color-coded health/recommendation badges, promote/demote/delete
- Auth: Clerk, email+password, sign-up disabled, invite-only
- Database: Railway PostgreSQL, all three tables live with data
- Nav: React Router, Evaluator and RADAR tabs

## Commands
cd server && npm run dev    — start backend (port 3001)
cd client && npm run dev    — start frontend (port 5173)
DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma studio
                           — open database browser
DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma migrate dev --name <n>
                           — run schema migration

## Never Do
- Store credentials in any committed file
- Recommend positions outside the circle of competence
  (see docs/architecture/DOMAIN.md for authoritative definition)
- Redeploy trim proceeds proportionally into existing positions
  without first checking Layer 3 for a higher-conviction alternative
- Skip the tax cost calculation before any trim recommendation
- Pass portfolio data to the analyst (breaks the firewall)
- Pass transcript data to the allocator (breaks the firewall)
