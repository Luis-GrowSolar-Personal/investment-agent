# Fix: auto-accept a trim when the Schwab target is exactly zero (full exit)

## Report your findings

Write a wrap-up to `./wrap-ups/fix-auto-accept-full-exit-trim-out.md`.
State the fix up front, then verify against a live full-exit case if one
currently exists on any account (read-only check first — see
verification section). Write for someone reading cold later.

## Context

`server/lib/schwabSync.js`'s `syncAccount()` currently routes EVERY trim
(any diff where Schwab shows fewer shares than local) into
`positionDiffs` for manual "Accept trim → pick lot(s)" resolution,
regardless of size. The stated reason (in the code's own comments) is
sound for a PARTIAL trim: the app can't know which specific lot(s)
Schwab sold, and that choice affects cost basis / holding period for tax
purposes — so a human has to pick.

But when Schwab now shows **zero** shares of a position (a full exit),
there's no actual ambiguity: every open lot for that position closed.
Luis's request: auto-accept this case rather than making him click
through a manual confirmation that has no real decision behind it. His
exact framing: "when a position is exited, let's accept automatically."

Confirmed example that prompted this: Andrea's ROTH IRA showed
`SPWR: Schwab 0 vs local 1347 (trim — select which lot(s) to close)` —
there's only one possible outcome (close all SPWR lots), yet the app
required a manual click to confirm it.

## The fix

In `syncAccount()`'s trim-detection branch (`server/lib/schwabSync.js`,
same area involved in the recent multi-fill fix — read the current code
before editing, don't assume exact line numbers), split the trim case:

- **`schwabShares === 0` (or within the existing `0.0001` tolerance of
  zero) → full exit.** Auto-close every open lot for this position
  (`Lot.closedDate`) rather than pushing to `positionDiffs`.
- **`schwabShares > 0` but less than local → partial trim.** Unchanged
  — still requires the manual lot-picker, exactly as today. Don't touch
  this path.

**Do this properly, not just by blindly zeroing.** Mirror the spirit of
the multi-fill buy-side fix: before just marking lots closed with no
data, try to find the real Schwab CLOSING transaction(s) for this symbol
in the transaction history (`ensureRecentTrades()`-style lookup, but for
`positionEffect === 'CLOSING'` legs instead of `'OPENING'`) to capture
the actual sale price and date per lot — this feeds directly into
realized gain/loss and tax-cost accuracy (Principle 5 in
`docs/architecture/DESIGN_PRINCIPLES.md`: every trim needs an accurate
tax cost calculation). If a matching closing transaction can't be found
(predates the 60-day window, or doesn't cleanly resolve), still auto-close
the lots (there's no ambiguity about WHICH lots close — that part is
certain regardless) but be honest in a note/field that the exact sale
price/date is a placeholder, same pattern as the existing "Estimated
from Schwab sync" language elsewhere in this file.

Check whether `Lot.closedDate` alone is sufficient for however realized
gain/loss gets computed elsewhere in the app (search for where
`closedDate` is read), or whether closing a lot also needs a sale
price/date field recorded somewhere for that calculation to work
correctly — read the current schema and usage before assuming.

## Verify

1. Read-only first: check whether any account currently has a live
   `schwabShares === 0` trim diff (like Andrea's ROTH IRA SPWR case) to
   test against. If SPWR's already been manually accepted by the time
   you run this, look for another example, or note that live
   verification wasn't possible and rely on the dry-run/unit-level check
   below instead.
2. If a live case exists, dry-run the new logic against it first
   (read-only, no writes — same convention as the last two fixes) before
   actually running a real sync that writes.
3. Confirm partial trims are completely unaffected — still go to
   `positionDiffs`, still require manual lot selection.
4. Run `./server/scripts/verify-allocation-math.sh` after any real sync
   to confirm nothing regressed (this fix only affects Schwab sync/lot
   data, not the moves engine, so expect no change — but confirm rather
   than assume).

## Commit and push

```bash
git add -A
git commit -m "Auto-accept full-exit trims (Schwab shows 0 shares) instead of requiring manual lot selection with no real ambiguity"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-auto-accept-full-exit-trim-out.md` existing.
