# Investment Agent — CoWork Handoff

**Date:** 2026-06-14
**Picks up from:** CoWork_handoff_2026-06-13c.md
**Session work:** Schwab Sync follow-ups — stale-token fix confirmed live,
SPCX bucket-misclassification bug fixed (+ "accept as new lot" DRIP feature),
`Account.lastSyncedAt` + UI indicator, dismiss/ignore for unmatched Schwab
accounts. **Confirmed pushed, `db push`'d, deployed, and working — Luis
confirmed 2026-06-14.**

**Next session focus:** see "Next session priorities" at the bottom — (1)
auto-sync-on-login + Sync→Link redesign (item 4, deferred from this session),
and (2) Phase 3 — replace Polygon price refresh with Schwab `marketdata`,
keeping Polygon as fallback.

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

## Next steps for Luis — ✅ ALL DONE, confirmed 2026-06-14

1. ✅ `git pull origin dev`, `prisma db push`, commit/push, deploy.
2. ✅ Live test passed — Luis confirmed "Phase 2 was pushed and it works."

## Open questions / follow-ups

- Existing SPCX ticker may still need the one-time manual BucketPill
  correction if it wasn't picked up by re-sync — confirm in next session if
  not already done.

---

## Next session priorities (2 items)

### 1. Auto-sync-on-login + Sync→Link redesign (item 4, deferred)

Originally proposed: on login, auto-sync prices/positions for all *linked*
accounts with no user action; the "Sync" button becomes a "Link" button
focused only on unmatched accounts. Luis chose "foundations now, auto-sync
later" — the foundations (`lastSyncedAt`, ignore-list) are now live, so this
is unblocked.

Things to work out:
- Where to trigger auto-sync — on app mount (`Portfolio.jsx`), or a
  lightweight backend cron/route hit on first portfolio load per session?
  Avoid syncing on every page navigation — probably gate on `lastSyncedAt`
  age (e.g. only auto-sync if >X hours stale).
- Reuse `syncAccount()` from `server/lib/schwabSync.js` per matched account.
- UI: decide what "Sync" button becomes once auto-sync exists — likely
  "Link" (for unmatched accounts only), with a manual "Force sync" still
  available somewhere for matched accounts.

### 2. Phase 3 — Schwab `marketdata` for price refresh, Polygon as fallback

Replace (or augment) `server/lib/priceRefresh.js`'s Polygon-only
`refreshViaIndividualQuotes()` with Schwab's `marketdata` quote endpoint for
symbols held in Schwab-linked accounts, falling back to the existing Polygon
path for symbols Schwab can't quote (or if the Schwab call/token fails).

Relevant existing pieces:
- `server/lib/schwabAuth.js` already handles OAuth + token refresh — same
  token should cover `marketdata` quote calls (per the open question noted
  in `CoWork_handoff_2026-06-13c.md`).
- `server/lib/priceRefresh.js` — current Polygon flow: sequential per-symbol
  `/v2/aggs/ticker/{symbol}/prev` calls, 500ms sleep between, 15s+retry on
  429. CRYPTO_RAW set maps raw crypto symbols to `X:SYMBOLUSD`.

Design questions to resolve next session:
- Schwab `marketdata` quotes are real-time (vs. Polygon's 15-min-delayed
  free tier) — confirm this is desirable / doesn't conflict with anything.
- Fallback trigger: only on Schwab API error/token failure, or also for
  symbols Schwab doesn't cover (e.g. raw crypto)?
- Does this apply per-account (only accounts with a linked Schwab account)
  or globally (single shared OAuth app token can quote any symbol
  regardless of account linkage — needs verification)?
- Keep the existing rate-limit-friendly sequential pattern for the Polygon
  fallback path; Schwab path likely doesn't need the same throttling.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance.
