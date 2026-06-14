# Investment Agent — CoWork Handoff

**Date:** 2026-06-14 (d)
**Picks up from:** CoWork_handoff_2026-06-14c.md
**Session work:** Sync→Link button redesign (deferred since 2026-06-14) —
code-complete, not yet pushed/deployed.

---

## Why

With auto-sync-on-login confirmed working (NavBar indicator, persistence fix
from earlier this session), the per-account "Sync" button in the Schwab Sync
modal is no longer the primary action for matched accounts. The remaining
manual-attention case is **new Schwab accounts that show up unmatched** —
those need linking/creation. Confirmed with Luis: "unmatched accounts" =
new/unclassified Schwab accounts not yet linked to a local account.

---

## What changed — `client/src/pages/Portfolio.jsx`

### 1. Header button is now dynamic

- New state `unmatchedSchwabCount`, checked once on mount via
  `GET /api/schwab/reconcile` (page stays mounted for the app's lifetime,
  like NavBar — so this is one extra read per page load, not per
  navigation).
- If `unmatchedSchwabCount > 0`: button reads **"🔗 Link Schwab accounts
  (N)"**, blue/primary styling.
- Else: button reads **"⟳ Schwab sync"**, neutral/secondary styling (as
  before).
- Tooltip differs accordingly.

### 2. `SchwabReconcileModal` keeps the count in sync

- New `onReconcileData` prop, called with the full reconcile JSON every time
  `fetchData()` succeeds (initial load + after match/create/ignore/sync
  actions).
- Portfolio passes `onReconcileData={json => setUnmatchedSchwabCount(json.unmatchedSchwab?.length ?? 0)}`
  — so linking an account immediately updates the header button without an
  extra fetch.

### 3. Per-account "Sync" → "Force sync"

- Matched-accounts section: button always uses `secondaryBtnStyle` (was
  blue/primary until first sync), label changed from "Sync"/"Syncing…" to
  "Force sync"/"Syncing…".
- New tooltip: "Matched accounts auto-sync on login if last synced >4h ago.
  Force sync now for an immediate refresh."
- No change to `handleSync` / `POST /api/schwab/sync/:accountId` — same
  endpoint, just reframed as a manual override.

### 4. Modal intro copy updated

Now leads with the auto-sync-on-login behavior and points to "Force sync"
for immediate refresh, instead of implying sync is the primary action.

No backend changes, no schema changes, no `prisma db push` needed.

---

## Verification done this session

- `client/src/pages/Portfolio.jsx` parses cleanly via `@babel/parser` (jsx
  plugin).
- Not yet tested against live Railway dev.

---

## Next steps for Luis

1. `git pull origin dev` (per parallel git workflow — `client/src/App.jsx`
   is the high-conflict file; **not touched** this session).
2. Commit + push (pull again first in case of parallel commits):
   ```
   git add -A
   git commit -m "Schwab: Sync->Link button redesign (dynamic header button, Force sync rename)"
   git pull origin dev
   git push origin dev
   ```
3. Deploy to Railway dev.
4. Test:
   - Open Accounts tab. If all Schwab accounts are linked, header button
     should read "⟳ Schwab sync" (gray/secondary), same as before.
   - If a new/unmatched Schwab account exists, header button should read
     "🔗 Link Schwab accounts (N)" in blue.
   - Open the modal — matched accounts should show "Force sync" buttons
     (gray, even for never-synced accounts).
   - Link or create an account for an unmatched Schwab account, confirm the
     header button's count decrements (or disappears/reverts to "⟳ Schwab
     sync" if it was the last one) without closing/reopening the modal.

---

## Open / deferred (unchanged)

- **`/api/moves/:owner` ~8.9s latency** (N+1 query in `server/routes/moves.js`)
  — separate perf issue. Future session.
- SPCX BucketPill one-time fix — Luis confirmed SPCX is currently in the
  Equities bucket; appears resolved.

---

## Next session priorities

### Phase 3 — Schwab `marketdata` for price refresh, Polygon as fallback

(unchanged — see `CoWork_handoff_2026-06-14.md` for full detail.)

### Then: `/api/moves/:owner` N+1 query fix

Replace the per-ticker `prisma.analysis.findFirst()` loop in
`server/routes/moves.js` (~line 620) with a single batched query.

---

## Project-wide note

Per project instructions: track token usage each session and alert Luis at
~85% of the chat's token allowance. Current session usage: moderate, not yet
near 85%.
