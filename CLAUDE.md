# Investment Agent — Claude Code Configuration

## Project Overview
Personal investment analysis and portfolio management tool.
React frontend, Node.js/Express backend, PostgreSQL database,
Clerk auth, Anthropic API for AI analysis. Hosted on Railway.

## Owner
Personal account — Luis. Separate from Windmar Energy entirely.

## Tech Stack
- Frontend: React + Tailwind CSS
- Backend: Node.js + Express
- Database: PostgreSQL (Railway)
- Auth: Clerk (password + 2FA)
- AI: Anthropic API (Claude Sonnet)
- Hosting: Railway (dev and prod services)
- Transcript source: SEC EDGAR API, copy-paste fallback

## Repository Structure
/backtest          — Python backtesting scripts (historical)
/client            — React frontend
/server            — Node.js/Express backend
/server/routes     — API routes
/server/services   — AI analyst, transcript fetcher, portfolio sync
/server/db         — Database models and migrations

## Environment Variables
All credentials live in .env — never committed to GitHub.
See .env.example for required variable names.
Railway dev and prod each have environment variables
set in the Railway dashboard.

## Key Design Decisions — Do Not Re-Derive
1. Agent operates in Layer 3→2→1 sequence (find → classify
   → enforce). Not 1→2→3.
2. Two position types: Type A (single-driver, fixed ~35% cap)
   and Type B (multi-driver platform, variable 40-60% cap).
3. Graduated exit ratchet: Weakening → trim to cap. No
   improvement after one quarter → trim 40% more. Second
   quarter deterioration → 3%. Third → exit.
4. Tax: 20% federal LTCG, Florida (no state tax). Trim
   tax-advantaged accounts first.
5. 48-hour waiting period for any position above 30% of
   total portfolio before confirming hold decision.
6. Mitigation argument discount: when management claims
   capability X will offset headwind Y, check X's own
   track record specifically — do not inherit from overall
   management credibility.

## Investment Universe (Circle of Competence)
Renewable energy, energy storage, defense technology,
semiconductors, IT/software/cloud, cryptocurrencies.
Agent never recommends outside this universe.

## Current Portfolio — Urgent Action
AMPX at ~33% of portfolio requires systematic trim to 15%.
This is the first action item.

## Build Sequence
1. Earnings call evaluator (proof of concept)
2. Database + RADAR + dashboard + Clerk auth (v1)
3. Schwab API + SEC EDGAR + press release monitoring

## Commands
npm run dev        — start development server
npm run build      — production build
npm test           — run tests
python3 backtest.py — run historical backtest

## Never Do
- Store credentials in CLAUDE.md or any committed file
- Recommend positions outside the circle of competence
- Redeploy trim proceeds proportionally into existing
  positions without first checking Layer 3 for a
  higher-conviction alternative
- Skip the tax cost calculation before any trim recommendation
