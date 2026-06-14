# Investment Agent — CoWork Handoff

**Date:** 2026-06-13
**Picks up from:** CoWork_handoff_2026-06-13b.md
**Session work:** Backlog item 5 — Phase 2 step 2, account reconciliation
(matching + position/lot sync). Code complete, not yet pushed/deployed —
needs `prisma db push` + git push from Luis's laptop (sandbox can't reach
Railway Postgres or run git here).

---

## Scope chosen this session

Luis selected:
- **Full sync (matching + positions + lots)** for matched accounts.
- **Surface for confirmation** (not auto-create) for unmatched Schwab accounts.

## Important constraint discovered this session

The Schwab Trader API's transaction-history endpoint only covers a **~60 day
window**, so historical lot-level cost basis / acquisition dates for
existing long-held positions **cannot** be reconstructed from Schwab data.
Given CLAUDE.md's tax-cost-calculation rules (15% LTCG/STCG, LT vs ST hinges
on acquisition date), "full sync" was implemented as:

- **Cash balance**: always synced from Schwab for matched accounts (no tax
  implication).
- **Positions that already have lots** (from CSV import or manual entry):
  **never touched**. If Schwab's share count disagrees with the local
  total, it's surfaced as a diff for manual review — lots are the source of
  truth for cost basis/dates.
- **Brand-new positions** (Schwab reports shares, no local position at all):
  a single lot is created, `source: 'schwab'`, cost basis = Schwab's
  `averagePrice`, acquisition date = **today (placeholder)** — flagged in
  the UI so Luis can correct the date for accurate LT/ST treatment.
- On resync, only `source: 'schwab'` lots are replaced (full-replace, same
  pattern as the existing `source: 'import'` CSV re-import).

This was a judgment call given the API limitation — worth confirming it
matches expectations before relying on it for tax decisions.

---

## What was built

1. **`server/prisma/schema.prisma`**
   - Added `Account.schwabAccountHash String? @unique` — links a local
     Account to a Schwab Trader API account hash.
   - Updated `Lot.source` comment to include `"schwab"` as a valid value
     (no migration needed — it's a plain String column).
   - **NOT YET PUSHED** — `npx prisma db push` failed in the sandbox (403
     fetching Prisma engine binaries; sandbox network is HTTP-proxy-only).
     Luis needs to run from `server/`:
     ```
     DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma db push
     ```
     (never `migrate reset` — see prisma_migration_drift memory)

2. **`server/lib/schwabAccounts.js`** — `previewAccounts()` now also selects
   `schwabAccountHash` on local accounts (needed for matching).

3. **`server/lib/schwabSync.js`** (new) —
   - `getReconciliation(prisma)` — matches Schwab accounts to local accounts
     by hash; returns `{ matched, unmatchedSchwab, unmatchedLocal }` with
     per-position share-count diffs for matched accounts. Read-only.
   - `matchAccount(prisma, accountId, schwabAccountHash)` — links an existing
     local Account to a Schwab hash.
   - `createAccountFromSchwab(prisma, { schwabAccountHash, name, type, owner,
     managed })` — creates a new local Account for an unmatched Schwab
     account, using Luis-confirmed name/type/owner (never guessed).
   - `syncAccount(prisma, accountId)` — syncs cash balance + new positions
     for a matched account, per the rules above.

4. **`server/routes/schwab.js`** — new routes, all `requireAuth()`:
   - `GET /api/schwab/reconcile`
   - `POST /api/schwab/match` `{ accountId, schwabAccountHash }`
   - `POST /api/schwab/accounts/create` `{ schwabAccountHash, name, type, owner, managed? }`
   - `POST /api/schwab/sync/:accountId`

5. **`client/src/pages/Portfolio.jsx`** —
   - New "⟳ Schwab sync" button in the page header (next to "+ Add account")
     opens `SchwabReconcileModal`.
   - `SchwabReconcileModal` — shows matched accounts (with Sync button +
     position diffs), unmatched Schwab accounts (link to existing local
     account, or create new via `CreateFromSchwabForm`), and unmatched local
     accounts (informational).
   - Removed the old disabled "Connect brokerage" placeholder button from
     `AccountPanel` (superseded by the new top-level Schwab sync modal).

---

## Verification done this session

- Schema and route files pass `node --check`.
- `Portfolio.jsx` parses cleanly via `@babel/parser` (jsx plugin) — 1966
  lines, no syntax errors.
- Not yet tested against live Railway dev (needs `db push` first, then
  deploy).

---

## Next steps for Luis

1. Pull this branch (`git pull origin dev` first per parallel git workflow
   — `client/src/App.jsx` is the high-conflict file, not touched this
   session so should be clean).
2. Run `npx prisma db push` from `server/` against the Railway dev DB.
3. Commit + push (pull again first in case of parallel commits).
4. Deploy to Railway dev, then test:
   - `/api/schwab/reconcile` should show all Schwab accounts; previously
     "unmatched" ones should now appear for linking/creation.
   - Try linking one existing account, then "Sync" — verify cash balance
     updates and any brand-new positions get a placeholder lot.
   - Spot-check the `positionDiffs` output against known share counts.

## Open questions / follow-ups

- Confirm the "placeholder acquisition date = today" approach for
  `source: 'schwab'` lots is acceptable, or whether Luis wants to enter real
  acquisition dates manually right after first sync for any newly-created
  positions (affects LTCG/STCG — see CLAUDE.md "Key Design Decisions" #4).
- Once reconciliation is live and accounts are matched, Phase 3 (live quotes
  via Schwab `marketdata`, replacing Polygon — backlog item 7) becomes more
  attractive since the same OAuth token covers it.

---

## Follow-up fix (same session): CSV import now clears Schwab placeholder lots

Discussed: Schwab's live API can't give per-lot history beyond ~60 days, so
CSV transaction exports remain the source of truth for historical lots.
Risk identified: if Schwab sync creates a `source: 'schwab'` placeholder lot
for a brand-new position (no local lots at sync time), and a CSV with real
transaction history is imported *later* for that same symbol, the old
import route would leave the placeholder lot in place alongside the new
`source: 'import'` lots — double-counting shares.

Fix (chosen over a "always import CSV first" workflow rule — Luis preferred
an enforced mechanism over remembering an ordering convention):
`server/routes/portfolio.js` `/accounts/:id/import` now also deletes any
`source: 'schwab'` lots for a position when it writes `source: 'import'`
lots for that same position. Added `results.clearedSchwabPlaceholders` to
the response and a corresponding note in the success message. Documented in
`server/lib/schwabSync.js`'s header comment. Verified with `node --check`.

No schema change, no new migration — just the import-route logic.

---

## Outstanding from prior sessions (untouched)

`docs/CoWork_handoff_2026-06-07c.md` modification and untracked
`server/scripts/backfill_domains.js` are still pending from before — left
as-is, Luis's call on bundling.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance.
