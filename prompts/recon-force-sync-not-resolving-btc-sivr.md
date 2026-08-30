# Recon: Force Sync didn't resolve BTC/SIVR even after Fix 1 landed

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-force-sync-not-resolving-btc-sivr-out.md`. State the
answer up front. This is primarily recon, but if the answer is
"deployment lag" or a similarly mechanical non-code issue, say so
clearly rather than making unnecessary code changes. If you do find and
fix a real code bug, follow the normal commit/push convention (see
bottom) — but don't fix anything speculative, confirm the cause first.

## Context

`wrap-ups/fix-schwab-sync-multifill-matching-out.md` (commit `b5a93f1`,
pushed to `origin/dev`) fixed `server/lib/schwabSync.js`'s
`syncAccount()` to sum multiple same-symbol Schwab transaction fills
when resolving a position diff — verified via a read-only dry run
against Andrea Morales's real, live BTC/SIVR data, which showed the fix
would create exactly the right lots (2 for BTC summing to 71.9957, 2 for
SIVR summing to 9.876).

Luis then clicked "Force sync" on Andrea's Custodial account in the live
app (this hits `POST /api/schwab/sync/:accountId` → `syncAccount()` —
confirmed this is the correct, fixed code path, not a different button).
The warning banner ("no matching transaction in the last 60 days... enter
manually") for both BTC and SIVR is still showing, unchanged, after
logging out/in, hard-refreshing, and disabling cache. This means either
the fix isn't actually running in whatever environment Force Sync hits,
or `syncAccount()` ran but failed to create the lots for some reason the
dry run didn't surface.

## What to check, in order

1. **Is the deployed code actually the fixed version?** Check what
   Railway is actually running. This repo has both a `dev` and `main`
   branch — confirm which branch Railway's production service (the one
   Luis's browser hits) is configured to deploy from. If there's a
   `railway.json`/`railway.toml`, Railway CLI config, or GitHub Actions
   workflow specifying the deploy branch, check it directly. If Railway
   CLI is available and authenticated locally, check the currently
   deployed commit/build (`railway status`, `railway logs`, or whatever
   the setup supports) and compare against `b5a93f1`. If there's no way
   to check this programmatically, say so plainly and tell Luis exactly
   what to look at in the Railway dashboard (which service, which
   branch, latest deploy timestamp vs. the commit's push time).
2. **If the deployed code IS current**, query Andrea's LIVE `Lot` rows
   for BTC and SIVR directly via Prisma (read-only `findMany`) — did
   `syncAccount()` actually attempt anything? Compare against the
   pre-sync state captured in the dry-run wrap-up. If new `schwab`-source
   lots exist now but don't sum correctly, or if nothing changed at all,
   that tells us where it broke.
3. **Check for a thrown/caught error.** `ensureRecentTrades()` has a
   try/catch that silently falls back to an empty `Map` on any fetch
   failure (`server/lib/schwabSync.js`, logs a `console.warn` on
   failure) — if the live Schwab token needed a refresh, rate-limited,
   or the transaction fetch failed for any other live-environment reason
   during Luis's actual click (not present during the earlier dry run,
   which used a separately-authed script), the fix would silently no-op
   and fall through to the exact same manual-entry path as before. Check
   Railway's server logs around the time of Luis's Force Sync click for
   this warning or any other thrown error from the sync route. If
   Railway logs aren't accessible from here, say so and tell Luis how to
   pull them himself.
4. **Re-run the same dry-run check from the Fix 1 wrap-up, live, right
   now** (read-only — same approach: fetch transactions + read current
   Lot rows, no writes) to confirm the underlying data still supports an
   exact match (i.e., rule out "the transaction fell out of the 60-day
   window" or "Schwab data changed" as an explanation — unlikely this
   soon, but rule it out explicitly).
5. Only if you find a genuine code defect (not deployment lag, not a
   transient live-environment fetch failure) should you fix it — in that
   case, follow the same rigor as Fix 1 (read current source first,
   don't guess, verify before committing).

## Constraints

- If step 2 requires writing to confirm something, don't — read-only
  only, same as the prior recon and the Fix 1 dry run. Luis has already
  attempted a real Force Sync himself (so the "preserve evidence"
  constraint from the original recon is less strict now — he's actively
  testing — but don't go further than he already has; don't trigger
  additional syncs yourself without explaining first in the wrap-up why
  it's needed).
- Be precise about which of the following this is, because the fix is
  different for each: (a) deployment hasn't caught up yet — tell Luis to
  wait/redeploy, no code change; (b) a live-environment-only failure mode
  (token/rate-limit/etc.) that the dry run didn't hit — explain and
  propose a fix if one is warranted; (c) an actual remaining defect in
  the Fix 1 code itself that the dry run didn't catch — fix it properly.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-force-sync-not-resolving-btc-sivr-out.md` existing,
with a definitive, evidence-backed answer to "why didn't Force Sync
resolve this after Fix 1 landed."
