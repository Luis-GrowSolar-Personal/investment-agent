# Recon: "Remove" doesn't actually remove a position (29415C127 example)

**No code defect found — the Remove flow works correctly, and
29415C127 is already correctly removed in the database.** No fix was
made (there was nothing broken to fix). This is a recon-only outcome;
Luis should reload the Portfolio page to confirm the row is now gone.

## Definitive finding

Queried Andrea Custodial's `29415C127` position directly (read-only,
before making any changes):

```
Ticker: { id: 774, symbol: "29415C127", status: "portfolio", bucketOverride: "equity", ... }
Position id=111, accountId=7 (Andrea Custodial):
  status: "closed"
  closedAt: "2026-08-22T18:09:12.952Z"
  lots: [{ id: 421, shares: 902, costBasis: 0, source: "schwab", closedDate: null, notes: "Estimated from Schwab sync..." }]
```

`current time at start of this recon: 2026-08-22T18:12:06Z` — **the
position was already closed, ~3 minutes before this recon began.**
This is almost certainly the result of Luis's actual "Remove" click
that prompted this task — the DELETE request **did** fire and **did**
succeed. `closedAt` is only ever set by
`DELETE /api/portfolio/positions/:id`
(`server/routes/portfolio.js:410-422`):

```js
router.delete('/positions/:id', async (req, res) => {
  const id = parseInt(req.params.id);
  try {
    const position = await prisma.position.update({
      where: { id },
      data: { status: 'closed', closedAt: new Date() },
    });
    res.json(position);
  } catch (err) { ... }
});
```

No other code path in the repo sets `Position.closedAt` — confirmed by
grepping the whole codebase. So this timestamp is direct proof the real
"Remove" button flow executed correctly for this exact position.

Re-simulated the exact query both list routes use, against the live DB,
right now:

```
GET /api/portfolio/accounts (nested positions include, status:'active' filter):
  Account 7 active positions count: 14
  Includes 29415C127? false

GET /api/portfolio/accounts/7/positions (status:'active' filter):
  Includes 29415C127? false
```

**29415C127 is correctly excluded from both list routes right now.**
If Luis reloads the Portfolio page for Andrea Custodial, it will not
show — the underlying data is already in the correct, expected end
state.

## Working through the prompt's checklist

**1. Does the DELETE request actually fire and succeed?** Yes —
confirmed directly: `status: 'closed'`, `closedAt` set to a real,
recent timestamp. No further live DELETE call was needed (per the
constraints, reproducing via a real DELETE was expected/fine, but since
the position was already closed by what appears to be Luis's own
click, re-issuing it wasn't useful — see "what was NOT done" below).

**2. If it persisted but the UI still showed the row — stale fetch or
a reactivation?**

- **Reactivation, checked and ruled out by code trace, not
  inference:** `schwabSync.js`'s `loadLocalPositions()`
  (~line 77-93) queries `prisma.position.findMany({ where: {
  accountId, status: 'active' }, ... })` — a **`'closed'` position is
  never even loaded into `localPositions`** on any subsequent sync.
  Since 29415C127 doesn't appear in Schwab's feed at all (per the
  reconcile view — it's "Local-only"), the main per-position loop
  never iterates it either. Both the "brand-new position" upsert
  (`status: 'active'`, ~line 513-517) and the full-exit auto-close
  loop from this session's earlier fix
  (`wrap-ups/fix-auto-accept-full-exit-trim-out.md`) only ever operate
  on positions already present in `localPositions` — a `'closed'`
  position is structurally invisible to `syncAccount()` from the
  moment it's closed. **There is no code path anywhere in the repo
  that can flip a `'closed'` position back to `'active'`** — grepped
  every `status: 'active'` write (`schwabSync.js` new-position upsert,
  `portfolio.js`'s CSV-import upsert, `portfolio.js`'s account-update)
  and each one only fires for a symbol Schwab is actively reporting
  (which 29415C127 isn't) or during ticker/position **creation**, not
  reactivation of an existing closed row. Confirmed by re-reading the
  code, not assumed.
- **Stale client fetch:** traced the full chain —
  `PositionRow`'s "Remove" confirm button
  (`client/src/pages/Portfolio.jsx:250`) calls `onDelete(pos.id)` →
  `AccountPanel.handleDeletePosition` (~line 449-455):
  ```js
  async function handleDeletePosition(positionId) {
    await fetch(`${API}/api/portfolio/positions/${positionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    onRefresh();
  }
  ```
  `await fetch(...)` only resolves **after** the server has already
  processed and responded to the DELETE (Express doesn't send a
  response until `prisma.position.update()` has committed) — so
  there's no race between the DELETE committing and `onRefresh()`
  firing; the write is guaranteed durable before the refetch starts.
  `onRefresh` traces cleanly up through `AccountCard` → the top-level
  `Portfolio` component's `fetchAccounts` (~line 2409-2416), which
  refetches `GET /api/portfolio/accounts` and calls `setAccounts()`
  with the fresh, filtered result — no caching layer, no stale
  closure, nothing scoped incorrectly. **No wiring bug found.**

**3. Did the DELETE call never fire at all (frontend bug)?** No — ruled
out directly by the `closedAt` timestamp being a real, fresh value in
the DB. The call did fire and did succeed.

**4. Should "local-only, source: schwab" positions get the same
auto-close-lots treatment as the full-exit sync fix?** Checked whether
leaving `Lot.closedDate: null` on this position's one lot (true here —
the manual "Remove" flow only ever sets `Position.status`/`closedAt`,
never touches `Lot.closedDate`) causes any downstream inconsistency.
Grepped every place lots get aggregated for allocation/dashboard/moves
math (`dashboard.js:237,287`, `moves.js:869`) — **all of them filter
`Position.status === 'active'` first**, before ever looking at lots.
A `'closed'` position's lots (regardless of their own `closedDate`)
are never read by any of these paths. **No correctness gap** — the
mismatch (position closed, lot still shows `closedDate: null`) is
cosmetic/inconsequential, not a bug, since nothing downstream reads
lots independently of their parent position's status. Not applying the
full-exit auto-close-lots pattern here, since there's no defect it
would fix.

## Why this looked broken to Luis

Best explanation, given the evidence: the DELETE call and its refetch
both completed correctly and quickly (this is a plain synchronous
Express handler + a single Prisma update, no batching, no queue), but
Luis likely looked at the page in the brief window before the
`onRefresh()`-triggered `setAccounts()` re-render landed, or the row
briefly remained visible during that in-flight moment and he didn't
see it disappear before navigating away/reporting the issue. **This is
consistent with a normal, expected round-trip delay, not a
reproducible defect** — there is no code path that would make the row
"stick" indefinitely, and the live data confirms it's already gone.

One minor, non-causal style note (not fixed, since it isn't the actual
defect and isn't strictly wrong): `handleDeletePosition` doesn't check
`res.ok` before calling `onRefresh()` — if the DELETE ever genuinely
failed (e.g., a 500), the UI would still silently attempt a refresh and
the row would correctly still show (since the position wasn't actually
closed), which would look identical to "Remove doesn't work" to a user
without an error message. This wasn't what happened here (the DELETE
did succeed), but if this complaint recurs, checking `res.ok` and
surfacing a toast/error would help diagnose a *future* real failure
faster. Flagging as a possible small UX improvement, not implementing
it — no discovered bug in this case to justify a "fix."

## Verification performed

- Read-only Prisma queries against the live DB confirming: (a)
  `Position.status = 'closed'`, `closedAt` set (~3 min before this
  recon started), (b) both list-route queries
  (`GET /accounts`'s nested include and `GET /accounts/:id/positions`)
  correctly exclude this position right now.
- Grepped the entire repo for every `Position` `status: 'active'`
  write and confirmed none can fire for a closed, Schwab-absent
  position.
- Grepped the entire repo for every place lots are aggregated
  independent of position status — none exist; all filter
  `status: 'active'` at the position level first.
- Traced the full frontend call chain (`PositionRow` → `AccountPanel`
  → `AccountCard` → top-level `Portfolio`) confirming `onRefresh` is
  correctly wired with no stale closures or caching.

## Deviations from the prompt

- **Did not issue a fresh `DELETE` call against 29415C127** as the
  constraints anticipated ("if reproducing requires actually calling
  DELETE... that's fine and expected") — by the time this recon began,
  the position was already closed (evidently from Luis's own prior
  click), so re-issuing the call would have been redundant (it's
  already in the target end state) rather than informative.
- **No fix was implemented or committed** — found no code defect to
  fix. The prompt's commit/push section is conditioned on "only if you
  made a fix," so nothing was committed or pushed for this task.

## What was deliberately NOT done

- Did not change `handleDeletePosition` to check `res.ok` — flagged as
  a minor, non-causal UX improvement above, not a fix for a found bug.
- Did not touch the full-exit auto-close-lots logic to also apply to
  manually-removed positions — confirmed (step 4 above) there's no
  correctness gap this would close.
- Did not run `verify-allocation-math.sh` — this task made no database
  writes and touched no allocation-relevant code path, so there's
  nothing for it to catch here.

## Follow-up for Luis

1. Reload the Portfolio page for Andrea Custodial — 29415C127 should
   already be gone from the Equities tab (confirmed via direct DB
   query above).
2. If "Remove" ever appears stuck again on a *different* position,
   the most useful thing to check first is whether the DELETE actually
   succeeded server-side (same query pattern used here), since this
   recon found the underlying mechanism to be sound — a repeat
   occurrence would point at something new, not this same cause.
3. To verify directly at any time (read-only):
   ```bash
   cd server && export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) && node -e "
   const {PrismaClient}=require('@prisma/client');const p=new PrismaClient();
   (async()=>{ const t = await p.ticker.findUnique({ where: { symbol: '29415C127' } });
     const pos = await p.position.findFirst({ where: { tickerId: t.id, accountId: 7 } });
     console.log('status:', pos.status, 'closedAt:', pos.closedAt);
     await p.\$disconnect(); })();"
   ```
