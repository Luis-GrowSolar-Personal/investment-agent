# Recon: SCHWAB_TOKEN_EXPIRED thrown ~30 min after a confirmed successful refresh

## Report your findings

Write a wrap-up to
`./wrap-ups/recon-schwab-token-refresh-race-out.md`. Find the definitive
mechanism before proposing a fix. If it's an obvious, low-risk fix once
found, implement it (say so up front, follow the commit/push convention
below); if not, stop and report. Write for someone reading cold later.

## Context

Luis hit `SCHWAB_TOKEN_EXPIRED` (`server/lib/schwabAuth.js:128`) while
running a one-off read-only script (`previewAccounts()` via
`getReconciliation()`). This error only fires when Schwab's `/token`
endpoint responds with a body containing `invalid_grant` or
"Refresh token is invalid" (`schwabAuth.js:125-130`) — i.e. Schwab
actively rejected the specific stored refresh token, not a network
failure or outage.

Live evidence (read-only query of the singleton `SchwabToken` row, id
1, right after the error):

```
createdAt (original authorization): 2026-06-13T21:26:48.313Z   (69.9 days old)
updatedAt (last successful refresh): 2026-08-22T18:25:27.080Z
expiresAt (current access token):    2026-08-22T18:55:27.079Z
```

The token was successfully refreshed only ~30 minutes before the
failure, and has been alive and refreshing correctly for ~70 days — so
this isn't the documented 7-day-from-original-authorization hard
expiry (that theory is now ruled out by this data). Something more
specific happened in that ~30 minute window.

## Known concurrent context — Schwab is independently down right now

Luis has confirmed, separately from the app, that he currently cannot
log into Schwab at all via a plain browser — neither the developer/API
portal nor the regular customer portal. That's a Schwab-side outage,
unrelated to this recon, and not something to investigate or wait on.
**Do not attempt any live Schwab call** (no Force Sync, no
`previewAccounts()`, no live token refresh) until Schwab's outage
clears — those calls will fail regardless of whether the race-condition
theory below is correct, and a failure right now proves nothing either
way. Do all of steps 1-4 below using static code review and existing
Railway logs only. If a fix is identified and implemented, the "Verify"
section's concurrent-call simulation must wait for Schwab to be back up
— note this explicitly in the wrap-up as a deferred verification step
rather than skipping or faking it.

## Working theory — confirm or rule out with evidence, don't just accept it

Schwab rotates the refresh_token on every use (single-use — comment at
`schwabAuth.js:155-156` confirms this). `refreshAccessToken()`
(~line 105-136) has **no locking/mutex**: it reads the current
`SchwabToken` row, then calls Schwab's `/token` endpoint with that
row's `refreshToken`. If two processes do this concurrently using the
same (soon-to-be-stale) refresh token value, the first call succeeds
and rotates it; the second call's refresh token has already been
consumed and gets `invalid_grant` from Schwab — indistinguishable from
"expired" but actually a race.

Known concurrent consumers of this single shared `SchwabToken` row:
- `server/scripts/schwabKeepAlive.js` — read it; confirm what schedule
  it runs on in production (check Railway's cron/scheduled-job config,
  or however this is invoked — grep for how it's triggered, don't
  assume).
- Any user-triggered sync/Force Sync from the live app (`syncAccount()`
  → `getValidAccessToken()`).
- The one-off script Luis ran manually at the time of the failure.

## What to check

1. **Confirm no locking exists**: read `getValidAccessToken()` and
   `refreshAccessToken()` in full — confirm there's genuinely no
   mutex/advisory-lock/`SELECT ... FOR UPDATE` around the read-refresh-
   write sequence.
2. **Confirm the keep-alive job's schedule** and whether it could
   plausibly have fired in the same ~30-minute window as Luis's Agent
   sync and his manual script run. Check Railway logs
   (`railway logs --service investment-agent-DEV`) around
   `2026-08-22T18:25:00Z`–`18:56:00Z` for multiple refresh attempts /
   multiple `SchwabToken` writes in quick succession, or any other
   evidence of overlapping calls.
3. **Check whether `getValidAccessToken()`'s buffer logic
   (`EXPIRY_BUFFER_MS`) could cause two nearly-simultaneous callers to
   both decide a refresh is needed** at the same moment even without a
   true race on the same in-flight refresh token — read the actual
   buffer value and reasoning.
4. Rule out alternative explanations before committing to the race
   theory: could Luis have revoked/reset the Schwab app connection
   himself (e.g. via Schwab's own developer portal or account security
   settings) around that time? Ask if unclear rather than assuming.

## The fix (if race condition is confirmed)

Serialize refresh attempts so only one in-flight refresh happens at a
time — e.g. an in-memory promise lock in `schwabAuth.js` (a module-level
`let refreshInFlight = null;` that concurrent callers await instead of
each independently calling Schwab) is likely sufficient for a single-
server deployment; if multiple server instances/processes are possible
in production, consider whether a DB-level lock is needed instead —
check Railway's deployment config for replica count before assuming
single-instance is safe.

## Verify

- If a fix is made, confirm concurrent calls to `getValidAccessToken()`
  (simulate with `Promise.all([...])` calling it multiple times at once
  in a throwaway script) result in exactly one Schwab `/token` call, not
  N.
- Confirm normal single-caller refresh behavior is unchanged.

## Commit and push (only if you made a fix)

```bash
git add -A
git commit -m "Serialize Schwab token refresh to prevent concurrent-refresh race invalidating the refresh token"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/recon-schwab-token-refresh-race-out.md` existing.
