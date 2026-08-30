# Fix: startTokenKeepAlive() refreshes unconditionally on every boot

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-keepalive-unconditional-refresh-out.md`. Schwab's
outage (noted in the prior recon) has cleared — live verification is
expected and fine for this task, not deferred. Write for someone
reading cold later.

## Context

Follow-up from `wrap-ups/recon-schwab-token-refresh-race-out.md`, which
fixed the actual `SCHWAB_TOKEN_EXPIRED` race (in-memory lock +
cross-process DB recovery, already live on `dev`, commit `f16a3ff`).
That recon identified the *frequency* driver, not yet fixed:

`startTokenKeepAlive()` (`server/lib/schwabAuth.js:199-213`, called
once from `server/index.js:70` at server boot) calls `tick()`
**immediately and unconditionally on boot** — no check of
`expiresAt`/`EXPIRY_BUFFER_MS` first — then every 24h after. Since
`investment-agent-DEV` auto-redeploys on every push to `dev` (confirmed
in the prior recon — multiple redeploys per hour during active
development), every single redeploy forces a real Schwab token refresh
regardless of how much life the current token has left. This is what
created the collision opportunity the prior fix now handles safely —
but reducing how often it happens at all is still worth doing.

## The fix

In `startTokenKeepAlive()`'s `tick()`, check the current token's
`expiresAt` against the existing `EXPIRY_BUFFER_MS` (same constant
`getValidAccessToken()` already uses) before calling
`refreshAccessToken()` — skip the refresh if the current token still
has meaningful life left, same logic `getValidAccessToken()` already
applies. Read the current code before editing; don't assume the exact
line numbers above are still accurate after the prior fix landed.

Keep the 24h `setInterval` cadence unchanged — only change whether each
tick (including the boot-time one) actually performs a refresh or
no-ops when unnecessary. Don't change `schwabKeepAlive.js`'s (the
separate cron job's) behavior — out of scope, per the prior wrap-up's
"what was deliberately not done."

## Verify

Schwab is confirmed reachable again — live verification expected:

1. Confirm a normal boot with a fresh/valid token does NOT trigger a
   live Schwab `/token` call (add a temporary log line or check via
   `railway logs` after a deploy; remove the temporary log before
   committing).
2. Confirm a boot with a near-expired or already-expired token still
   DOES refresh correctly (the safety behavior must be preserved).
3. Trigger a real Force Sync (or equivalent) on any account to confirm
   the previous race-condition fix and this frequency-reduction change
   coexist correctly — no regressions to normal sync behavior.
4. `node --check server/lib/schwabAuth.js`.
5. Run `./server/scripts/verify-allocation-math.sh` only if this touches
   anything beyond `schwabAuth.js` (it shouldn't) — confirm scope stayed
   contained.

## Commit and push

```bash
git add -A
git commit -m "Skip unconditional token refresh on boot when current token still has meaningful life left"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-keepalive-unconditional-refresh-out.md` existing.
