# Fix: refreshMovesCache silently drops isFreshStart

## Report your findings

Write a wrap-up to `./wrap-ups/fix-movescache-preserve-freshstart-out.md`.
Small, isolated, low-risk fix — implement directly. Write for someone
reading cold later.

## Context

Found in `wrap-ups/recon-rebaseline-modal-choices-out.md`. Two code
paths recompute an owner's `MovesCache` entry while preserving whatever
mode it was already in, and they disagree:

- `server/routes/moves.js` (`GET /:owner`, ~line 1959-1962) reads and
  preserves BOTH `isRebaseline` and `isFreshStart` from the existing
  cached payload before recomputing.
- `server/lib/movesCache.js`'s `refreshMovesCache()` (~line 37-38) only
  preserves `isRebaseline` — `isFreshStart` is silently dropped:
  ```js
  const bypassWinnerProtection = existing?.payload?.isRebaseline === true;
  const payload = await computeMovesPayload(owner, { bypassWinnerProtection });
  //                                                 ^ no freshStart passed through
  ```

`refreshMovesCache()` fires after a profile PATCH (`routes/users.js:302`)
and after a Schwab account sync (`routes/schwab.js:203`,
`refreshAllMovesCache` at `routes/schwab.js:357`). Any of those silently
reverts an account out of Full Reset mode back to plain re-baseline mode,
with zero user action and zero notice — the same class of bug the file's
own header comment documents having already fixed for `isRebaseline` on
2026-08-08, just never extended to `isFreshStart` when that flag was
added later.

## The fix

In `refreshMovesCache()`, also read and pass through `isFreshStart`,
matching the pattern already used in `moves.js`:

```js
const bypassWinnerProtection = existing?.payload?.isRebaseline === true;
const freshStart              = existing?.payload?.isFreshStart === true;
const payload = await computeMovesPayload(owner, { bypassWinnerProtection, freshStart });
```

Read the current file before editing — confirm exact line numbers.

## Verify

1. Read-only: find (or set up, if none currently exists) an account
   whose `MovesCache.payload.isFreshStart` is `true`. Trigger whatever
   calls `refreshMovesCache()` (a profile PATCH is safest/easiest to
   trigger deliberately; a Schwab sync also works if one is convenient)
   and confirm, via a read-only query immediately after, that
   `isFreshStart` is still `true` in the resulting cache entry — this is
   the exact regression to prove fixed.
2. Confirm the reverse isn't broken: an account with `isFreshStart:
   false` stays `false` after the same trigger.
3. Confirm `moves.js`'s own refresh path (`GET /:owner`) is untouched
   and still behaves as before — this fix only touches
   `lib/movesCache.js`.
4. `node --check server/lib/movesCache.js`.
5. Run `./server/scripts/verify-allocation-math.sh` if convenient —
   this fix only affects which computation mode gets used on cache
   refresh, not the math itself, so no change expected, but confirm
   rather than assume.

## Commit and push

```bash
git add -A
git commit -m "Preserve isFreshStart in refreshMovesCache, matching the existing isRebaseline preservation"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-movescache-preserve-freshstart-out.md` existing.
