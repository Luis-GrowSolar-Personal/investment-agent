# Investment Agent — CoWork Handoff

**Date:** 2026-06-14 (b)
**Picks up from:** CoWork_handoff_2026-06-14.md
**Session work:** Auto-sync-on-login (next session priority item 1) —
code-complete, not yet pushed/deployed.

---

## What changed

### 1. `server/lib/schwabSync.js` — new `autoSyncStaleAccounts(prisma, maxAgeHours = 4)`

- Queries local `Account` rows with `schwabAccountHash` set.
- Splits into `stale` (lastSyncedAt null or older than `maxAgeHours`) and
  `fresh`.
- Calls `syncAccount()` (existing function, unchanged) only for `stale`
  accounts.
- **No Schwab API calls at all if nothing is stale** — the staleness check
  is a local Prisma query only.
- Returns `{ maxAgeHours, synced: [...], skipped: [...], errors: [...] }`.

### 2. `server/routes/schwab.js` — new `POST /api/schwab/auto-sync`

- `requireAuth()`, optional body `{ maxAgeHours }` (defaults to 4).
- Calls `autoSyncStaleAccounts` and returns its result as JSON.

### 3. `client/src/pages/Portfolio.jsx` — auto-sync on mount

- New `useEffect` (after `fetchAccounts` is defined): on mount, if
  `sessionStorage.schwabAutoSyncDone` is not set, sets it and calls
  `POST /api/schwab/auto-sync`.
- If `synced.length > 0`, calls `fetchAccounts()` to refresh the page and
  shows a dismissible banner: "⟳ Auto-synced N Schwab account(s) on login:
  <names>."
- If nothing was stale, no banner, no extra API calls — silent.
- Errors are logged to console only (no banner), matching the existing
  error-logging pattern.
- Gated by `sessionStorage` (per-tab, resets on tab close) rather than
  `lastSyncedAt` alone, so it runs at most once per browser session even if
  the user navigates away from and back to Portfolio repeatedly.

### Scope decisions (per Luis, this session)

- **Staleness window: 4 hours** (server default, configurable via
  `maxAgeHours` body param if ever needed).
- **"Sync" button unchanged** — stays as a manual force-sync option in the
  Schwab Sync modal, regardless of `lastSyncedAt`. The Sync→Link redesign
  from the prior handoff's "next session priorities" is **deferred again** —
  Luis chose to keep this session's change minimal (auto-sync only, no
  button/UI restructuring beyond the new banner).

---

## Verification done this session

- `node --check` on `server/lib/schwabSync.js` and `server/routes/schwab.js`
  — OK.
- `client/src/pages/Portfolio.jsx` parses cleanly via `@babel/parser` (jsx
  plugin) — OK.
- Not yet tested against live Railway dev.

No schema changes — **no `prisma db push` needed** for this change.

---

## Next steps for Luis

1. `git pull origin dev` (per parallel git workflow — `client/src/App.jsx`
   is the high-conflict file; not touched this session).
2. Commit + push (pull again first in case of parallel commits):
   ```
   git add -A
   git commit -m "Schwab: auto-sync stale accounts on login"
   git pull origin dev
   git push origin dev
   ```
   Note: `docs/CoWork_handoff_2026-06-14.md` has unrelated uncommitted
   changes from the prior session (marking that session's items as
   confirmed-done) — fine to include in the same commit, or split into a
   separate "docs" commit if preferred.
3. Deploy to Railway dev.
4. Test: load the Portfolio page. If any linked account's `lastSyncedAt` is
   null or >4h old, you should see the "⟳ Auto-synced..." banner and the
   account(s) should refresh (cash balance, any new positions). On a second
   page load in the same tab, no banner (already synced this session, and/or
   within the 4h window).

---

## Open questions / follow-ups (unchanged from prior handoff)

- Existing SPCX ticker may still need the one-time manual BucketPill
  correction if it wasn't picked up by re-sync.
- Sync→Link button redesign — still deferred, no new info this session.

---

## Next session priorities

### Phase 3 — Schwab `marketdata` for price refresh, Polygon as fallback

(unchanged from `CoWork_handoff_2026-06-14.md` — see that doc for full
detail: replace/augment `server/lib/priceRefresh.js`'s Polygon-only path with
Schwab `marketdata` quotes for Schwab-linked symbols, Polygon as fallback.)

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance.
