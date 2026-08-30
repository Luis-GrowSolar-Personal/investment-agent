# Fix: fixed-target bucket "(unallocated)" shortfall overstates achievable value for under-cap tickers

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-fixed-bucket-undercap-achievable-out.md`. State the fix
up front, then paste the reconciliation script's before/after output for
the affected buckets. Write for someone reading cold later.

## Context

`server/scripts/verify-allocation-math.js` (built last session — see
`wrap-ups/fix-build-allocation-reconciliation-script-out.md`) found a
real bug on its first production run: Andrea's Crypto (-$479.87) and
Commodities (-$838.31), and Eduardo's Commodities (-$871.91), fail
reconciliation.

**Root cause, already diagnosed in that wrap-up:** `generateFixedTargetMove`
(`server/routes/moves.js`) has no `ADD` branch — a fixed-target ticker
(ETF/commodity/crypto) only ever gets `TRIM` (if over its own per-ticker
cap) or `HOLD` (otherwise). Nothing ever moves it *up* toward its cap.
But the "(unallocated)" bucket shortfall calculation (the `fixedBuckets`
block inside `computeMovesPayload`, fixed two sessions ago in
`wrap-ups/allocation-admin-gap-fix-out.md`) computes `achievableValue` by
summing `fixedTargetMap.get(ticker.id)` — each held ticker's **capped**
target — unconditionally. That's correct when a ticker is over cap (a
real `TRIM` will land it exactly there), but wrong when a ticker is under
cap: nothing will ever move it up, so assuming it contributes its full
capped amount overstates what's actually achievable and understates the
"(unallocated)" gap shown to the user.

Concrete example: Andrea's BTC sits at 3.47% against a 5% cap. Today's
calculation assumes BTC contributes the full 5% ($1,572.72) toward the
Crypto bucket and only flags the *remaining* gap to the 10% bucket target.
The true achievable contribution from BTC is its actual current value
($1,092.84, since nothing will move it), so the real gap is bigger than
what's currently shown.

## The fix

In the `fixedBuckets` loop's `achievableValue` computation, change each
held ticker's contribution from `fixedTargetMap.get(ticker.id)`
(unconditional capped target) to `Math.min(currentValue, fixedTargetMap.get(ticker.id))`
— i.e. a ticker contributes the smaller of "what it's actually worth
today" and "its own cap," since:
- If it's over cap, a `TRIM` move will land it exactly at the cap → cap
  is correct (and `currentValue` would overstate it, since currentValue
  is higher — `Math.min` picks the cap here, correctly).
- If it's under cap, nothing moves it → its actual current value is
  correct (and `Math.min` picks currentValue here, correctly, since
  currentValue < cap).

This should increase the `dollarAmount` on the existing "(unallocated)"
rows for the affected buckets (Andrea's Crypto/Commodities, Eduardo's
Commodities) — it's a correction to an existing number, not a new code
path or new row type.

Read the actual current code around the `fixedBuckets` loop / wherever
`achievableValue` and `fixedTargetMap` are used before assuming exact
variable names — this document describes intent, confirm against the
real source.

## Verify with the reconciliation script — this is the whole point of having built it

Run `./server/scripts/verify-allocation-math.sh` before and after the
fix. Before: Andrea's Crypto/Commodities and Eduardo's Commodities should
show the same FAILs as the last run. After: they should PASS (within the
script's existing $2 tolerance) — that's the acceptance criterion, not
"it compiles." Also confirm no previously-passing bucket regresses
(rerun the full script, not just the three affected buckets) — the other
sessions' fixes (ETF, established, cash) should stay green, and the
tolerance-band-driven "expected" FAILs (Established/ETF's small drifts,
Luis's Speculative/Crypto/Commodities) should remain exactly as
explained in `wrap-ups/fix-build-allocation-reconciliation-script-out.md`,
not newly change in size — if any of those shift meaningfully, that's a
sign this fix touched something broader than intended and needs another
look before shipping.

## Commit and push

You have real local git access — commit and push this yourself, Luis
doesn't want to hand-run git commands:

```bash
git add -A
git commit -m "Fix fixed-target-bucket achievable-value calc to not assume under-cap tickers self-heal to their cap"
git push origin dev
```

If `git push` fails or the branch is behind, resolve it yourself
(`git pull --rebase origin dev` then retry) and report what happened in
the wrap-up.

## Reminder: write the wrap-up

Don't finish without `./wrap-ups/fix-fixed-bucket-undercap-achievable-out.md`
existing, with the script's real before/after output included.
