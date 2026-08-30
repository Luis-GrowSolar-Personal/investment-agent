# Recon: full-exit auto-close leaves Position.status stuck 'active' with 0 shares

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-full-exit-position-status-not-closed-out.md`. Find the
definitive impact before proposing a fix. If it's an obvious, low-risk
fix once found, implement it (say so up front, follow the commit/push
convention below); if not, stop and report. Write for someone reading
cold later.

## Context

A manual whole-account reconciliation (Schwab CSV export vs. live DB,
via a throwaway script, not the app's own reconcile path) found two
"ghost" positions in Andrea's accounts:

- Andrea Custodial (account id 7): `SPWR` — `Position.status` presumably
  `'active'`, 0 open lots, 0 total shares. Not in Schwab's export at all.
- Andrea ROTH IRA (account id 11): `BTC` and `SPWR` — same pattern.

Root cause, already traced (not the question here): `syncAccount()`'s
full-exit auto-close logic (`server/lib/schwabSync.js`, ~line 540-583,
landed last week per `wrap-ups/fix-auto-accept-full-exit-trim-out.md`)
closes every open `Lot` (`closedDate` set) when Schwab reports 0 shares
for a symbol, but **never updates `Position.status` to `'closed'`**.
The `Position` row is left `'active'` indefinitely with zero open lots.

## What to check — trace actual impact, don't guess

1. **Confirm the mechanism directly**: read-only query these exact rows
   (SPWR on account 7, BTC and SPWR on account 11) and confirm
   `Position.status` is indeed still `'active'` with 0 non-closed lots,
   matching the theory above.
2. **Does this affect what the UI shows?** Check the Portfolio page's
   list route/frontend — does a 0-share `'active'` position actually
   render as a visible row (a "SPWR: 0 shares" ghost line), or is there
   some existing filter (e.g. `totalShares > 0`) that already hides it?
   Luis's own screenshots from last week didn't show these rows, so
   check whether something is already suppressing them, or whether he
   simply didn't scroll/notice.
3. **Does this affect RADAR/allocator "already held" logic?** This is
   the important one. Grep for every place `Position.status === 'active'`
   (or equivalent Prisma filter) is used to decide whether a ticker is
   "currently held" — particularly in RADAR candidate-pool logic
   (`server/routes/radar.js` and wherever Layer 3 candidate surfacing
   lives) and the allocator (`server/routes/moves.js`,
   `server/lib/` wherever fresh-money/candidate eligibility is computed,
   per the recent `freshStart`/global-status eligibility fixes in
   `wrap-ups/fix-freshstart-global-status-eligibility-out.md` and
   `wrap-ups/fix-normal-path-global-status-eligibility-out.md` — this
   recon may be hitting the same family of bug from a different angle).
   Does any of that code check `Position.status` without also checking
   share count > 0? If so, SPWR (and any future full-exit) would be
   wrongly treated as "already held" and excluded from candidate
   consideration even though Luis has zero actual shares.
4. **Does this affect dashboard/allocation math?** Per the earlier
   `recon-position-remove-not-working` finding, dashboard/moves
   aggregation filters `Position.status === 'active'` first, then sums
   lots — a 0-lot position contributes $0 and 0 shares either way, so
   this is probably harmless for math purposes, but confirm rather than
   assume, since that recon was about a *closed* position, not an
   *active-with-zero-lots* one — check if there's any per-position-count
   logic (e.g. counting "how many positions does this account hold")
   that would be thrown off by counting a zero-share ghost.

## The fix (if impact is confirmed and low-risk)

In the full-exit auto-close block (`schwabSync.js`, same location as the
lot-closing transaction), also set `Position.status = 'closed'` (and
`closedAt`, matching the pattern used by the manual DELETE route in
`server/routes/portfolio.js`) once all lots for that position are
closed. Then backfill the two/three existing ghost rows found above to
the same end state (read-only-confirmed correct values first).

Don't touch the partial-trim path — only the full-exit branch.

## Verify

1. Confirm SPWR (account 7) and BTC/SPWR (account 11) end up with
   `Position.status: 'closed'`, `closedAt` set, matching the manual
   Remove flow's end state exactly.
2. Confirm both accounts still reconcile cleanly against their CSVs
   after the backfill (re-run the same CSV-vs-DB check, expect 0
   discrepancies now).
3. Run `./server/scripts/verify-allocation-math.sh` after any writes.
4. If RADAR/allocator eligibility logic is found to have the same
   "status without share-count" gap, confirm SPWR becomes eligible for
   candidate consideration again (or report the gap without fixing it,
   if it's not a simple, low-risk change).

## Commit and push (only if you made a fix)

```bash
git add -A
git commit -m "Close Position status on full-exit auto-close instead of leaving zero-share ghost rows"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-full-exit-position-status-not-closed-out.md` existing.
