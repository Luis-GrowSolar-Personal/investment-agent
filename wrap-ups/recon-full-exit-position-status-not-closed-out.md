# Recon: full-exit auto-close leaves Position.status stuck 'active' with 0 shares

**Confirmed, fixed, and backfilled.** The theory was exactly right, and
the impact was more than cosmetic: this ghost-position bug was silently
excluding fully-exited tickers from RADAR/allocator candidate
eligibility, treating them as "already held" when they had zero real
shares. Fixed at the source (`server/lib/schwabSync.js`, commit
`3120695`, pushed to `origin/dev`) and backfilled the three known ghost
rows to the correct end state.

## 1. Mechanism confirmed directly

Read-only query of the three positions named in the context, before
any changes:

```
SPWR (Andrea Custodial, id=7)     positionId=75  status=active  closedAt=null  openLots=0  totalOpenShares=0
BTC  (Andrea ROTH IRA, id=11)     positionId=90  status=active  closedAt=null  openLots=0  totalOpenShares=0
SPWR (Andrea ROTH IRA, id=11)     positionId=89  status=active  closedAt=null  openLots=0  totalOpenShares=0
```

All three: every lot closed (`closedDate` set, dated Jun 14 / Aug 16 /
Aug 21 2026 — real historical auto-close events from the full-exit fix
landing last week), but `Position.status` still `'active'`,
`closedAt` still `null`. Exactly matches the theory: `schwabSync.js`'s
full-exit block (confirmed current location, ~line 541-583) closes
every `Lot` via `prisma.$transaction([...openLots.map(lot =>
prisma.lot.update(...))])` but never touched `Position.status` at all.

## 2. Does this affect what the UI shows?

Checked both list routes (`GET /api/portfolio/accounts`'s nested
`positions` include, `GET /api/portfolio/accounts/:id/positions`) and
the frontend render path (`PositionRow` in
`client/src/pages/Portfolio.jsx`) — **neither filters on share count or
market value anywhere.** Both routes filter only `status: 'active'`;
`PositionRow` renders unconditionally for every position in its bucket
tab's filtered list, with `fmtShares(pos.totalShares)` and
`fmtDollars(mktVal)` simply showing `0`/`$0.00` for a ghost row — no
suppression logic exists. **These WOULD render as visible "0 shares,
$0.00" rows** in the Equities/Crypto tabs. Luis's screenshots not
showing them is most plausibly just easy-to-miss zero-value rows in a
longer list, not any code path hiding them — consistent with the
prompt's own suspicion ("or he simply didn't scroll/notice").

## 3. Does this affect RADAR/allocator "already held" logic? — **Yes, confirmed, this was the real impact.**

`server/routes/radar.js` itself doesn't reference `Position.status` at
all (grepped, zero matches) — the actual "is this ticker currently
held by this owner" gate lives in `server/routes/moves.js`, exactly
where the earlier `freshStart`/normal-path global-status eligibility
fixes also live (same family of bug, different mechanism, as the
prompt suspected):

- `moves.js:865-873` — loads each owner's accounts with
  `positions: { where: { status: 'active' }, ... }` (no share-count
  filter).
- `moves.js:896-904` — builds `byTicker` from those positions, keyed by
  `tickerId`, with **no check on `totalShares`/open-lot-count** — any
  `'active'` position, ghost or real, makes `byTicker.has(tickerId)`
  true.
- `moves.js:1177` and `moves.js:1449` — both the `freshStart` candidate
  universe and the normal watchlist-candidate path gate eligibility via
  `.filter(wt => !byTicker.has(wt.id))` — **this is the actual
  per-owner "currently held" check**, and it inherits the ghost-position
  bug directly.

**Confirmed empirically, before the fix:** simulated `byTicker` for
owner "Andrea Morales" — `SPWR` incorrectly appeared in the "currently
held" set (would be excluded from watchlist reconsideration / Layer 3
opportunity-scanner candidacy) despite Andrea holding zero actual SPWR
shares anywhere. This is a real, previously-invisible bug with genuine
candidate-eligibility consequences, not just a cosmetic ghost row.

**After the fix + backfill:** re-ran the same simulation —
`SPWR` correctly no longer appears in Andrea's held-ticker set. (`BTC`
still correctly appears as held for Andrea — she genuinely holds real
BTC shares in a *different* account, Andrea Custodial; the ROTH IRA
ghost BTC position closing doesn't and shouldn't change that. Verified
this is correct, not a leftover bug.)

## 4. Does this affect dashboard/allocation math?

Checked every place lots get aggregated for dollar/share totals
(`dashboard.js:237,287`, `moves.js:865-873`, `positionMetrics()`
~`moves.js:155-165`) — all correctly derive `shares`/`cost` from
`lots.filter(l => !l.closedDate)`, which is empty for a ghost position,
so dollar/share contributions are correctly `$0`/`0` either way,
confirming the prompt's own suspicion that this part is harmless.

**However, per-ticker headcount/split logic is a different matter** —
`moves.js` splits each bucket's top-level target "evenly across its
currently-held tickers" using `byTicker`'s keys, which (before the fix)
incorrectly counted a $0 ghost ticker as one of the "held" slots in
that split. This was tested directly and empirically ruled out as a
new-regression concern (see verification below) — but it's worth
noting *why* it isn't a regression: this exact reconciliation gap
already existed in Andrea's numbers **before** this fix, for reasons
unrelated to these three positions.

## The fix

`server/lib/schwabSync.js`, full-exit auto-close block (same location,
only the partial-trim path was left untouched per the prompt's
instruction):

```diff
-    await prisma.$transaction(
-      openLots.map(lot => prisma.lot.update({
-        where: { id: lot.id },
-        data: {
-          closedDate: closingDate,
-          notes: (lot.notes ? lot.notes + ' ' : '') + noteSuffix,
-        },
-      }))
-    );
+    await prisma.$transaction([
+      ...openLots.map(lot => prisma.lot.update({
+        where: { id: lot.id },
+        data: {
+          closedDate: closingDate,
+          notes: (lot.notes ? lot.notes + ' ' : '') + noteSuffix,
+        },
+      })),
+      // Every open lot just closed above — close the Position itself too
+      // (same status/closedAt pattern as the manual DELETE route in
+      // portfolio.js), so it stops showing as a zero-share 'active' ghost
+      // and stops being counted as "currently held" by the allocator/RADAR
+      // eligibility gate (both filter on Position.status === 'active').
+      prisma.position.update({
+        where: { id: localPos.positionId },
+        data: { status: 'closed', closedAt: closingDate },
+      }),
+    ]);
```

Same `$transaction` (now an array literal instead of a mapped array,
to include the extra `position.update` call alongside the lot
updates), same atomicity guarantee. Uses `closingDate` — the same value
already computed for the lots (either the matched Schwab closing
transaction date, or today's date as a placeholder) — for
`Position.closedAt`, keeping the lot and position timestamps
consistent with each other.

**Why this alone fixes the RADAR/allocator eligibility gap too, with
no separate `moves.js` change needed:** `moves.js:869`'s account query
already filters `positions: { where: { status: 'active' } }` before
building `byTicker`. Once a position's `status` becomes `'closed'`, it
is excluded from that query entirely — `byTicker` never sees it, and
the `!byTicker.has(wt.id)` eligibility check is automatically correct.
Fixing the root cause (the missing `Position.status` update) closes
both the ghost-row *and* the eligibility bug in one place — confirmed
by direct simulation (below), not just inferred from reading the code.

## Backfill

Backfilled the three known ghost positions (temporary script, deleted
after use) to `status: 'closed'`, with `closedAt` set to **the lot's
own historical `closedDate`** (Aug 16 / Jun 14 / Aug 21 2026
respectively) rather than "now" — so the backfilled records reflect
when the position actually closed, matching what the fixed code would
have recorded had it been in place at the time, not a fabricated
"just discovered today" timestamp:

```
CLOSED SPWR account=7  positionId=75 -> status=closed closedAt=2026-08-16
CLOSED BTC  account=11 positionId=90 -> status=closed closedAt=2026-06-14
CLOSED SPWR account=11 positionId=89 -> status=closed closedAt=2026-08-21
```

## Verify

1. **End state matches the manual Remove flow exactly** — re-queried
   all three after the backfill: `status: 'closed'`, `closedAt` set,
   `openLots: 0` — identical shape to what `DELETE
   /api/portfolio/positions/:id` produces (confirmed against
   `server/routes/portfolio.js:410-422`'s own
   `{ status: 'closed', closedAt: new Date() }` pattern).
2. **CSV-vs-DB reconciliation** — the prompt's step 2 refers to
   re-running "the same CSV-vs-DB check" via Luis's own throwaway
   script; that script (`server/scripts/reconcile-from-csv.js`,
   confirmed present in the working tree as Luis's own tool, untouched
   by this task) requires the actual CSV export file as input, which
   wasn't available in this environment — **not re-run**, flagged as a
   deviation below. The underlying mechanism this check would confirm
   (DB no longer disagrees with Schwab about these three symbols) is
   already established by the read-only Position/Lot queries above:
   Schwab reports 0 shares for all three (per the original recon), and
   the DB now correctly reflects that via `status: 'closed'` instead of
   a phantom active position.
3. **`verify-allocation-math.sh`, run after the writes, with a
   before/after empirical check to rule out a regression:** ran the
   script after the backfill — Andrea Morales shows `[FAIL] Established
   Equities target=$8488.29 reconstructed=$8888.32 diff=$400.03` (and
   two `freshStart` FAILs). To confirm this wasn't caused by this
   session's changes, **temporarily reverted the three positions back
   to `status: 'active', closedAt: null`** (the exact pre-fix state)
   and re-ran the script: **identical failures, identical dollar
   amounts, in both states.** This proves the Established/Speculative
   Equities reconciliation gaps for Andrea (and the pre-existing,
   already-flagged gaps for Luis and Eduardo — Luis's Speculative
   Equities, Eduardo's Established Equities, both present since before
   this session started, per earlier wrap-ups this session) are
   **entirely unrelated to this fix** — re-restored the backfill to the
   correct closed state immediately after this test (confirmed via a
   final read-only query matching the intended end state exactly).
4. **RADAR/allocator eligibility gap** — confirmed the same gap exists
   (see section 3 above) and confirmed it is fixed by this change:
   simulated `byTicker` for owner "Andrea Morales" before and after —
   `SPWR` moves from incorrectly-held to correctly-not-held; `BTC`
   correctly remains held (she holds real BTC elsewhere). This is a
   **simple, low-risk fix that also happens to resolve the eligibility
   gap** — no separate `moves.js` change was needed or made.
5. `node --check server/lib/schwabSync.js` — passes.
6. Re-grepped after editing to confirm the `prisma.position.update`
   call landed inside the `$transaction` array exactly as written.
7. `git diff --stat server/lib/schwabSync.js` — 13 insertions, 4
   deletions, confined to the full-exit block; the partial-trim path
   (main loop, `diffDirection: 'trim'`) is untouched — confirmed via
   `git diff` showing no changes near that branch.

## Deviations from the prompt

1. **Did not re-run Luis's CSV-vs-DB reconciliation script** (step 2 of
   Verify) — it requires a real Schwab CSV export file as input, not
   available in this environment. Substituted the read-only Position/
   Lot state check (already confirms the DB no longer disagrees with
   the "0 shares" fact established in the original recon) as the
   closest available proxy. Flagging this explicitly rather than
   claiming it was run.
2. **Found a pre-existing, unrelated reconciliation gap while running
   `verify-allocation-math.sh`** (Andrea Morales's Established
   Equities) — proved via a temporary revert/re-close test that it is
   NOT caused by this fix, so did not attempt to diagnose or fix it
   (out of scope for this recon; matches the same category of
   already-flagged, still-open gaps for Luis and Eduardo from earlier
   in this session).

## What was deliberately NOT done

- Did not touch the partial-trim path in `schwabSync.js` (main loop,
  `diffDirection: 'trim'`) — per the prompt's explicit instruction.
- Did not add a share-count check to `moves.js`'s `byTicker`
  construction — confirmed unnecessary, since fixing `Position.status`
  at the source makes the existing `status: 'active'` filter in
  `moves.js:869` correctly exclude ghost positions with no further
  change needed.
- Did not investigate or fix the pre-existing Andrea/Luis/Eduardo
  Established/Speculative Equities reconciliation failures — confirmed
  unrelated to this fix (see verification #3), left open for separate
  investigation.
- Did not re-run Luis's CSV-vs-DB script — no CSV file available in
  this environment (see deviation #1).

## Follow-up for Luis

1. Reload the Portfolio page for Andrea Custodial and Andrea ROTH IRA —
   the three ghost rows (SPWR, BTC, SPWR) should now be gone from their
   respective tabs.
2. Any *future* full-exit sync will now correctly close the `Position`
   row too — no more zero-share ghosts, and fully-exited tickers become
   correctly eligible for watchlist/candidate reconsideration again.
3. When you have your Schwab CSV export handy, re-run your own
   `server/scripts/reconcile-from-csv.js` check against Andrea's
   accounts to confirm 0 discrepancies now (not re-run here — no CSV
   file was available in this environment).
4. The Established/Speculative Equities reconciliation `[FAIL]` rows
   for Andrea, Luis, and Eduardo are pre-existing and unrelated to this
   fix (proven via a live before/after test) — still open, worth a
   dedicated look separately.
5. To verify the three positions' end state directly at any time
   (read-only):
   ```bash
   cd server && export DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) && node -e "
   const {PrismaClient}=require('@prisma/client');const p=new PrismaClient();
   (async()=>{
     for (const [accountId, symbol] of [[7,'SPWR'],[11,'BTC'],[11,'SPWR']]) {
       const t = await p.ticker.findUnique({ where: { symbol } });
       const pos = await p.position.findUnique({ where: { tickerId_accountId: { tickerId: t.id, accountId } } });
       console.log(symbol, accountId, pos.status, pos.closedAt);
     }
     await p.\$disconnect();
   })();"
   ```
