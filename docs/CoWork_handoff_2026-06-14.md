# Investment Agent — CoWork Handoff

**Date:** 2026-06-14
**Picks up from:** CoWork_handoff_2026-06-13c.md
**Session work:** Schwab Sync follow-ups — stale-token fix confirmed live,
SPCX bucket-misclassification bug fixed (+ "accept as new lot" DRIP feature),
`Account.lastSyncedAt` + UI indicator, dismiss/ignore for unmatched Schwab
accounts. All code-complete, **not yet pushed/deployed** — needs
`prisma db push` + git push from Luis's laptop.

---

## Confirmed from prior session

The stale-Clerk-token fix (CoWork_handoff_2026-06-13c.md, "stale Clerk token
in Schwab Sync modal") is deployed and confirmed working — Luis: "The error
has gone away."

---

## New issues reported this session (5 items)

1. NVDA share-count mismatch (Schwab 3.3307 vs local 3.3289999999999997) —
   likely a DRIP (dividend reinvestment). **Resolved** — see "Accept as new
   lot" below.
2. Sync button always renders blue/primary, even right after syncing — no
   confirmation a sync occurred. **Resolved** — see "lastSyncedAt" below.
3. Accounts the user doesn't want to link keep reappearing under "no local
   match" every time the Schwab Sync modal opens. **Resolved** — see
   "Ignore unmatched accounts" below.
4. Proposed redesign: on login, auto-sync prices/positions for all linked
   accounts (no user action); "Sync" button becomes a "Link" button focused
   only on unmatched accounts. **Deferred** — Luis chose "two-step:
   foundations now, auto-sync later." Items 2-3 above are the foundations;
   this item is for a future session.
5. After syncing Eduardo's Custodial account (correctly identified +2 SPCX
   shares), the account table still showed 7 equities — no SPCX, even after
   refresh. **Resolved** — see "Bucket-misclassification bug" below; SPCX
   was created correctly but filed under the wrong tab (ETFs instead of
   Equities).

---

## Bucket-misclassification bug (item 5 root cause)

`Position` has no `assetType` column. `enrichPosition()` in
`server/routes/portfolio.js` computes:

```js
effectiveBucket = pos.ticker.bucketOverride ?? smartDefaultBucket(pos.assetType || '', pos.ticker.symbol)
```

Since `pos.assetType` is always `undefined`, the fallback call is always
`smartDefaultBucket('', symbol)`, which defaults to `'etf'` for any symbol
not in the hardcoded ETF/crypto/commodity lists — **even genuine equities**.

Both auto-create paths used the pattern `bucketOverride: bucket !== 'equity'
? bucket : null`, which stores `null` for equities and relies on that broken
fallback — silently misfiling new equity positions into the ETFs tab.

**Fix** (both files now store the bucket explicitly, computed correctly at
creation time):
- `server/lib/schwabSync.js` — `syncAccount()`'s brand-new-position branch
  (~line 310): `bucketOverride: bucket` (was `bucket !== 'equity' ? bucket :
  null`).
- `server/routes/portfolio.js` — CSV-import ticker auto-create (~line 567):
  same change.

Both verified with `node --check`.

**One-time manual fix needed for existing SPCX ticker:** SPCX was created
*before* this fix, so it still has `bucketOverride: null`. Once deployed,
open the Portfolio page → ETFs tab → find SPCX → use the BucketPill control
to set its bucket to "Equity". This is a one-time correction; the underlying
bug won't recur for any future auto-created equity positions.

---

## "Accept as new lot" — DRIP / upward share-count mismatch (item 1)

New backend function `acceptShareDiff(prisma, accountId, symbol)` in
`server/lib/schwabSync.js`:
- Looks up the Schwab-reported share count for `symbol` in the linked
  account, compares to local lot total.
- If Schwab > local (the DRIP case), creates ONE new lot for the
  difference: `source: 'schwab'`, cost basis = Schwab's current
  `averagePrice`, acquisition date = **today (placeholder)**.
- Throws if Schwab <= local (nothing to accept — that direction needs
  manual review instead).
- Does not touch any existing lots.

New route: `POST /api/schwab/accept-diff` `{ accountId, symbol }` in
`server/routes/schwab.js`.

**UI** (`client/src/pages/Portfolio.jsx`, `SchwabReconcileModal`): for each
`positionDiffs` entry where `status === 'mismatch' && schwabShares >
localShares`, an "Accept +X as lot" button appears next to the diff line.
Click → calls the new endpoint, shows a confirmation message including the
placeholder-date caveat, refreshes the modal data.

Verified: `node --check` (server files), `@babel/parser` jsx parse (client
file).

---

## `Account.lastSyncedAt` (item 2)

**Schema** (`server/prisma/schema.prisma`): added
`Account.lastSyncedAt DateTime?` — **requires `npx prisma db push`** (see
below).

**`syncAccount()`** (`server/lib/schwabSync.js`): now stamps
`lastSyncedAt: new Date()` on every successful sync, regardless of whether
`cashBalance` was present. Included in the route's JSON response too.

**`previewAccounts()`** (`server/lib/schwabAccounts.js`): `localAccounts`
select now includes `lastSyncedAt` so reconciliation's `matched[].local` has
it.

**UI** (`Portfolio.jsx`): each matched account now shows "Synced Xm/h/d ago"
(or "Never synced") below the Sync button. The Sync button itself uses the
secondary (gray) style once `lastSyncedAt` is set, and only shows the
primary blue style for accounts that have never been synced — so a
just-synced account no longer looks like it still needs attention.

---

## Ignore unmatched Schwab accounts (item 3)

**New model** (`server/prisma/schema.prisma`): `IgnoredSchwabAccount { id,
schwabAccountHash @unique, createdAt }` — **requires `npx prisma db push`**.

**`server/lib/schwabSync.js`**:
- `getReconciliation()` now also returns `ignoredSchwab` (Schwab accounts
  whose hash is in `IgnoredSchwabAccount`), and excludes those from
  `unmatchedSchwab`.
- New `ignoreAccount(prisma, schwabAccountHash)` / `unignoreAccount(prisma,
  schwabAccountHash)`.

**New routes** (`server/routes/schwab.js`): `POST /api/schwab/ignore` and
`POST /api/schwab/unignore`, both `{ schwabAccountHash }`.

**UI** (`Portfolio.jsx`): each unmatched Schwab account now has an "Ignore"
button. A collapsible "Ignored accounts (N)" section (collapsed by default,
`showIgnored` state) lists ignored accounts with an "Un-ignore" button each.

---

## Verification done this session

- `node --check` on `server/lib/schwabSync.js`, `server/lib/
  schwabAccounts.js`, `server/routes/schwab.js`, `server/routes/
  portfolio.js` — all OK.
- `client/src/pages/Portfolio.jsx` parses cleanly via `@babel/parser` (jsx
  plugin) after all edits.
- Not yet tested against live Railway dev — needs `db push` + deploy first.

---

## Next steps for Luis

1. `git pull origin dev` (per parallel git workflow — `client/src/App.jsx`
   is the high-conflict file; not touched this session, should be clean).
2. From `server/`, run:
   ```
   DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) npx prisma db push
   ```
   (adds `Account.lastSyncedAt` and the new `IgnoredSchwabAccount` table —
   never `migrate reset`, see prisma_migration_drift memory)
3. Commit + push (pull again first in case of parallel commits):
   ```
   git add -A
   git commit -m "Schwab sync: fix bucket misclassification, add accept-diff/lastSyncedAt/ignore"
   git pull origin dev
   git push origin dev
   ```
4. Deploy to Railway dev, then test:
   - Open Schwab Sync modal for Eduardo's Custodial account — SPCX should
     now show in the Equities tab after a re-sync (or after the one-time
     manual BucketPill fix if it was already created).
   - Try the "Accept +X as lot" button on the NVDA DRIP diff.
   - Sync an account, confirm "Synced just now" appears and the button turns
     gray.
   - Click "Ignore" on an unmatched account, confirm it disappears and
     reappears under "Ignored accounts" with "Un-ignore" working.

## Open questions / follow-ups

- Item 4 (auto-sync-on-login + Sync→Link button redesign) — tackle in a
  future session once items 2-3 are tested live.
- Existing SPCX ticker needs the one-time manual BucketPill correction
  described above.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance.
