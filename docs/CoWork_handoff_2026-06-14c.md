# Investment Agent — CoWork Handoff

**Date:** 2026-06-14 (c)
**Picks up from:** CoWork_handoff_2026-06-14b.md
**Session work:** Relocate Schwab auto-sync status indicator from
Portfolio.jsx to NavBar.jsx — code-complete, not yet pushed/deployed.

---

## Why

Commit `6b40753` (Phase 1 auto-sync) was deployed to the OLD build and
tested by Luis via HAR capture. Findings:

- Landing page is `PortfolioManager.jsx` (`/`), not `Portfolio.jsx`
  (`/accounts`). Since `App.jsx` mounts all pages simultaneously and hides
  inactive ones with `display: none`, the auto-sync banner in
  `Portfolio.jsx` was invisible unless the user was on the Accounts tab.
- "Did we miss a commit?" — No. The HAR files were captured against the
  pre-`6b40753` deploy, so `/api/schwab/auto-sync` legitimately didn't exist
  yet at test time.
- Slow refresh/switch-user is a separate, pre-existing issue: `GET
  /api/moves/:owner` takes ~8.9s due to an N+1 `prisma.analysis.findFirst()`
  loop in `server/routes/moves.js`. Not Polygon-related (verified
  `/api/portfolio/accounts` and `/api/dashboard` don't call Polygon).
  **Deferred to a future session.**

Fix: move the auto-sync trigger + status indicator into `NavBar.jsx`, which
is always rendered regardless of active tab.

---

## What changed

### `client/src/components/NavBar.jsx`

- New imports: `useState`, `useEffect` from React; `useAuth` from
  `@clerk/clerk-react`; added `API` constant and `timeAgo(timestampMs)`
  helper (`"just now"` / `"Nm ago"` / `"Nh ago"` / `"Nd ago"`).
- New `schwabStatus` state (`{ label, justSynced } | null`).
- New `useEffect`, gated by `sessionStorage.schwabAutoSyncDone` (same key as
  before — fires at most once per browser tab session, runs whichever of
  NavBar/Portfolio mounts the effect first):
  - `POST /api/schwab/auto-sync` with a fresh Clerk token via `getToken()`.
  - If `synced.length > 0`: `"Schwab synced just now (N)"`, green.
  - Else if any account has `lastSyncedAt`: `"Schwab synced Xm/h/d ago"`
    (computed from the most recent `lastSyncedAt` across `synced` +
    `skipped`), gray.
  - No linked accounts at all → no indicator shown.
  - Errors logged to console only.
- Indicator rendered in the top-right nav cluster, before the user email.

### `client/src/pages/Portfolio.jsx`

- Removed: `syncBanner` state, the auto-sync `useEffect` (lines ~2018–2048
  in the prior version), and the banner JSX block. This logic now lives
  solely in NavBar. `fetchAccounts` and `token` remain — still used
  elsewhere in the file.

No schema changes, no `prisma db push` needed.

---

## Verification done this session

- `@babel/parser` (jsx plugin) parses both `NavBar.jsx` and `Portfolio.jsx`
  cleanly.
- Not yet tested against live Railway dev.

---

## Next steps for Luis

1. `git pull origin dev` (per parallel git workflow — `client/src/App.jsx`
   is the high-conflict file; **not touched** this session).
2. Commit + push (pull again first in case of parallel commits):
   ```
   git add -A
   git commit -m "Schwab: move auto-sync status indicator to NavBar"
   git pull origin dev
   git push origin dev
   ```
3. Deploy to Railway dev.
4. Test from any tab (not just Accounts): on first load in a tab, you should
   see "⟳ Schwab synced just now (N)" in green near your email if any linked
   account was stale (>4h or never synced). On reload in the same tab, it
   should show "⟳ Schwab synced Xm ago" in gray (no new API calls if nothing
   is stale). If there are no Schwab-linked accounts at all, no indicator —
   expected.

---

## Open / deferred

- **`/api/moves/:owner` ~8.9s latency** (N+1 query in `server/routes/moves.js`)
  — separate perf issue, not part of this fix. Future session.
- Sync→Link button redesign — still deferred (per 2026-06-14b).
- SPCX BucketPill one-time fix — still unconfirmed from earlier session.

---

## Next session priorities

### Phase 3 — Schwab `marketdata` for price refresh, Polygon as fallback

(unchanged — see `CoWork_handoff_2026-06-14.md` for full detail.)

### Then: `/api/moves/:owner` N+1 query fix

Replace the per-ticker `prisma.analysis.findFirst()` loop in
`server/routes/moves.js` with a single batched query (e.g. group by
`tickerId`, take latest via `orderBy` + `distinct`, or one raw query with a
window function).

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance. **Current session is around 80-85% —
flagging now.**
