# Session Handoff — 2026-06-27

## Context

We're building an investment agent (React + Node/Express + PostgreSQL/Prisma + Railway).
Previous sessions completed the Portfolio Manager account-bucket UI. The page now shows
per-account buckets (ROTH IRA / Taxable / IRA) with actionable Exit/Trim/Add counts.
Clicking a bucket filters the Action Required move cards.

## What was completed this session

- Per-owner access enforcement (non-admins see only their own data)
- Access revoked screen for unlinked Clerk accounts
- `Analysis.summary` field — plain-English one-liner populated at eval time, stored in DB
- Model updated to `claude-sonnet-4-6` (dated snapshot `claude-sonnet-4-20250514` retired)
- Portfolio Manager: cash floor display (`$1,602 floor · $8 available`)
- Portfolio Manager: account-bucket nav (ROTH IRA / Taxable / IRA cards with move counts)
- Unfundable ADD moves hidden from bucket view (`insufficientCash` filter)
- Capital Flow card removed (redundant with bucket view)

## Next step: accept/decline workflow (step 3 of UX redesign)

Each move card needs **Accept / Decline** buttons. Behavior:

- **Accept**: records the decision, optionally lets user override the dollar amount
  (e.g. accept $2K of a $3K recommendation). Accepted trim/exit proceeds are added to
  a running "available to deploy" total shown at the top of the page.
- **Decline**: requires a short reason ("I think SPWR will turn the corner").
- The running total depletes as the user accepts add/initiate recommendations.
- Two buckets in the running total:
  - **Available**: free cash + accepted trim/exit proceeds
  - **Reserve**: the 5% floor — user sees it declining if they choose to draw from it

## Step 4 (same session if time): persist decisions

New `OwnerDecision` DB table:

```prisma
model OwnerDecision {
  id             Int      @id @default(autoincrement())
  owner          String
  tickerId       Int
  moveType       String   // EXIT | TRIM_* | ADD | INITIATE
  decidedAt      DateTime @default(now())
  decision       String   // "accepted" | "declined" | "deferred"
  acceptedAmount Float?   // user-overridden amount on accept
  declinedReason String?  // free text on decline
  systemSnapshot Json     // snapshot: thesisHealth, trajectory, ratchetTranche, price
}
```

## Portfolio construction spec

Full design is in `docs/architecture/PER_ACCOUNT_PORTFOLIO_CONSTRUCTION.md`.
Read that before implementing Task #20 or #21.

## Backlog (do not start yet)

- **Task #20**: Per-account position count warnings in moves engine
  - Too-few-positions warning: fires when accountPositionCount < floor(accountValue / minPositionDollar)
  - Over-concentrated account warning: fires when accountValue / totalPortfolioValue > 0.40
  - Accept button on warning card updates owner profile N/M without going to Admin

- **Task #21**: Per-account model weights engine refactor (Tier 2/3)
  - targetPositions(account) = min(M, max(N, floor(accountValue / minPositionDollar)))
  - Each account holds top-N from global conviction list, weighted within the account
  - Whole-portfolio caps (35%/50%) still enforced at aggregate level

- **Benchmark & promotion UI** in Admin tab (gate runner, ledger, model challenger runs)

## Key files

- `client/src/pages/PortfolioManager.jsx` — main page to modify for step 3
- `server/routes/moves.js` — moves engine
- `server/prisma/schema.prisma` — DB schema (use `db push`, never `migrate reset`)
- `server/lib/authMiddleware.js` — `enforceOwner` helper
- `docs/architecture/DESIGN_PRINCIPLES.md` — read before touching analyst/allocator logic
- `docs/architecture/DOMAIN.md` — read before touching investment universe logic

## Rules

- `git pull origin dev` before making any changes
- `git pull origin dev` before pushing (parallel session risk)
- `client/src/App.jsx` is the high-conflict file — resolve merge conflicts manually
- Never run `prisma migrate reset` — use `db push`
- Never store credentials in committed files
