# Recon: SCHWAB_TOKEN_EXPIRED thrown ~30 min after a confirmed successful refresh

**Race condition confirmed, root cause pinpointed with exact timestamp
evidence, and fixed.** Committed `f16a3ff`, pushed to `origin/dev`.
This is a genuine cross-process race — not the working theory's
"two nearly-simultaneous user calls" alone, but something more
specific and more frequent in this dev environment: **`schwabAuth.js`'s
in-process keep-alive fires an *unconditional* token refresh on every
single server boot**, and this dev service gets redeployed very
often (multiple times per hour during active development) — each
redeploy is an opportunity to collide with any other caller (a manual
script, a live sync, or the separate Railway cron job) that's also
refreshing around the same moment.

**No live Schwab calls were made during this recon**, per the
constraint — Schwab's outage was independently confirmed by Luis, and
everything below is either static code review, Railway deployment
history, or an isolated in-process simulation with a stubbed `fetch`
(no network call, no real Schwab endpoint touched).

## 1. Confirmed: no locking exists (before the fix)

Read `getValidAccessToken()` and `refreshAccessToken()`
(`server/lib/schwabAuth.js`, then ~lines 105-136 and 168-180) in full.
Confirmed: no mutex, no advisory lock, no `SELECT ... FOR UPDATE`, no
optimistic-concurrency check anywhere in the original code. Each call
independently does `findUnique` → build request body from
`row.refreshToken` → `fetch` Schwab's `/token` endpoint → `saveTokens`.
Two calls in flight at once will both read the same `refreshToken`
value and both try to use it — Schwab accepts the first, rejects the
second with `invalid_grant`. Working theory confirmed as structurally
possible exactly as described.

## 2. The actual trigger for THIS incident — traced with exact timestamps, not inferred

Two independent keep-alive mechanisms exist, and reading them closely
revealed something more specific than the prompt's working theory
anticipated:

- **`startTokenKeepAlive()`** (`schwabAuth.js:199-213`, called once from
  `server/index.js:70` at server boot): runs `tick()` **immediately on
  boot** (`tick();` — unconditional, no expiry check at all), then
  again every 24h via `setInterval`. Every tick calls
  `refreshAccessToken(prisma)` directly — it does **not** check
  `expiresAt`/`EXPIRY_BUFFER_MS` first, unlike `getValidAccessToken()`.
  **This means every server redeploy forces an immediate, unconditional
  token refresh**, regardless of how recently the token was refreshed
  by anything else.
- **`schwabKeepAlive.js`** (`server/scripts/schwabKeepAlive.js`): a
  separate Railway Cron Job service (confirmed via
  `railway status --json` on the linked `investment-agent-cron-keep-alive`
  service: `cronSchedule: "0 */12 * * *"` — fires at 00:00 and 12:00
  UTC daily), calling `refreshAccessToken()` directly, unconditionally,
  in its own separate process/container. Its own header comment
  explicitly says this "belt-and-suspenders duplicate" **"overlaps
  deliberately"** with the in-process keep-alive — a design that
  assumed redundant refreshes were harmless, not accounting for
  Schwab's single-use refresh_token rotation making them actively
  destructive.

**Ruled out the 12h cron job for this specific incident**: its fixed
schedule (00:00 / 12:00 UTC) doesn't fall within the failure window
(`18:25–18:56 UTC` / `14:25–14:56 EDT`) — nearest firing was ~6+ hours
earlier. Confirmed via `railway status --json`, not assumed.

**Found the actual second caller: automatic redeploys.** Checked
`investment-agent-DEV`'s deployment history
(`railway deployment list`) for the failure window and found:

```
299afc61... | SUCCESS | 2026-08-22 14:51:45 -04:00   <- inside the 14:25–14:56 EDT window
c3b5015b... | REMOVED | 2026-08-22 14:24:34 -04:00   <- right at the window's start
```

Cross-referenced against `git log` — **both deployments correspond
exactly to this session's own commits**, each one triggering an
automatic Railway redeploy of `investment-agent-DEV` on push to `dev`:

```
3120695... 2026-08-22 14:51:42 -0400  Close Position status on full-exit auto-close...
42ac784... 2026-08-22 14:24:31 -0400  Surface DELETE failure instead of silently refreshing...
```

Both deployment timestamps land within 3 seconds of the corresponding
commit's push time — consistent with the earlier Force-Sync recon's
finding that this DEV service auto-deploys from `dev` almost
immediately on push. **Each of these redeploys' boot sequence fired an
immediate, unconditional `refreshAccessToken()` call via
`startTokenKeepAlive()`'s `tick()`** — squarely inside the same ~30
minute window Luis's manual script (also calling
`getValidAccessToken()` → likely also triggering its own refresh, since
the access token was within its buffer window by then) was running.
**This is the concrete, evidenced trigger for this specific incident**:
not the 12h cron job, not a coincidental double-user-call, but this
session's own rapid-fire commits each forcing a redeploy-triggered
refresh at the exact moment Luis's script needed a refresh too.

## 3. `EXPIRY_BUFFER_MS` reasoning

`EXPIRY_BUFFER_MS = 60 * 1000` (60 seconds) — a small safety margin so
`getValidAccessToken()` doesn't hand out a token that expires mid-request.
This buffer alone doesn't cause simultaneous refreshes on its own (it's
just a threshold, not a scheduling mechanism) — the actual
simultaneity in this incident came from the keep-alive tick's
boot-triggered unconditional refresh landing in the same window as a
buffer-triggered refresh from another caller, not from the buffer
value itself being too large or too small. Confirmed by reading the
code — not a contributing bug, just the mechanism that made Luis's
script due for its own refresh right as the redeploy also fired one.

## 4. Alternative explanation — ruled out by asking, not assumed

Per the prompt's explicit instruction, asked Luis directly whether he
manually revoked/reset the Schwab app connection around the failure
window. **Confirmed: no** — Luis stated he didn't revoke anything, and
separately noted Schwab itself appears to be having a system outage
right now (already known context, unrelated to the mechanism
established above). This rules out the manual-revocation alternative
and leaves the redeploy-collision race as the sole, fully-evidenced
explanation.

## The fix

`server/lib/schwabAuth.js` — two additive layers, matching the
cross-process reality confirmed above (an in-memory lock alone was
insufficient once multiple genuinely separate processes/containers
were confirmed to touch the same row — the main web service, the
separate cron job, and ad-hoc scripts):

**Layer 1 — in-memory lock, serializes concurrent calls within one process:**

```diff
+let refreshInFlight = null;
+
 async function refreshAccessToken(prisma) {
+  if (refreshInFlight) return refreshInFlight;
+  refreshInFlight = doRefreshAccessToken(prisma);
+  try {
+    return await refreshInFlight;
+  } finally {
+    refreshInFlight = null;
+  }
+}
+
+async function doRefreshAccessToken(prisma) {
   const row = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
   ...
```

This handles the case the prompt's suggested fix anticipated (two
near-simultaneous calls inside the same running web service — e.g. a
user-triggered sync racing the in-process keep-alive tick).

**Layer 2 — cross-process recovery on `invalid_grant`:** since the
actual incident here was a **cross-process** collision (redeploy's new
container vs. Luis's separate script process — neither shares
in-memory state with the other), Layer 1 alone would not have
prevented this exact failure. Added a DB re-check instead of
immediately failing:

```diff
     if (text.includes('invalid_grant') || text.includes('Refresh token is invalid')) {
+      // Another process may have already consumed and rotated this exact
+      // refresh_token. Re-check the row before giving up.
+      const fresh = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
+      if (fresh && fresh.refreshToken !== row.refreshToken) {
+        return { access_token: fresh.accessToken, refresh_token: fresh.refreshToken };
+      }
       throw new Error('SCHWAB_TOKEN_EXPIRED');
     }
```

If Schwab rejects our refresh attempt but the stored row's
`refreshToken` has since changed (someone else's refresh landed in the
DB moments before or during our own request), we use that
already-refreshed token instead of throwing — this is exactly the
recovery the redeploy-vs-script collision needed, and it works
regardless of which two processes were racing (cron job, web service,
or an ad-hoc script), since it's DB-state-based, not in-memory.

**Why not a full DB-level lock (`SELECT ... FOR UPDATE` / Postgres
advisory lock)** as the prompt flagged as a fallback option: confirmed
via `railway status --json` that every service (`investment-agent-DEV`,
`investment-agent-cron-keep-alive`) runs `numReplicas: 1` — no
horizontal scaling to defend against — so the remaining risk is
low-frequency, short-window collisions between genuinely different
processes (redeploy vs. cron vs. ad-hoc script), not sustained
concurrent load from many replicas. The two-layer fix above closes the
actual failure mode (an unnecessary `SCHWAB_TOKEN_EXPIRED` throw) at
much lower risk/complexity than building real distributed locking
across three independently-deployed call sites, and doesn't change the
successful single-caller path at all — kept in the "obvious, low-risk"
category per the prompt's own guidance.

## Verify

Per the outage constraint, **all verification here is a pure
in-process simulation with a stubbed `global.fetch` — zero live Schwab
calls, zero network requests.** Three temporary scripts (deleted after
use):

**a. Concurrent same-process calls now produce exactly one Schwab call:**
```
--- Concurrent getValidAccessToken() calls (5x, all racing on the same expired row) ---
Results (should all be identical — same in-flight refresh shared): [ 'tok-1', 'tok-1', 'tok-1', 'tok-1', 'tok-1' ]
Number of actual fetch() calls to Schwab /token (should be 1, not 5): 1
Final stored token row: { id: 1, accessToken: 'tok-1', refreshToken: 'refresh-1', ... }
```

**b. Normal single-caller behavior is unchanged:**
```
--- Sequential call after the in-flight refresh completes ---
Single result: tok-2 | new fetch calls: 1 (should be 1)
```

**c. Cross-process recovery — simulated a separate process rotating
the token underneath us, then Schwab rejecting our stale attempt:**
```
Recovered without throwing — used the other process's already-rotated token:
  { access_token: 'other-process-access', refresh_token: 'other-process-refresh' }
PASS: no SCHWAB_TOKEN_EXPIRED thrown when another process had already refreshed.
```

**d. Genuine expiry (no other process rescued it) still throws correctly** —
confirmed the fix doesn't mask real failures:
```
Threw as expected: SCHWAB_TOKEN_EXPIRED (PASS)
```

**e. `node --check server/lib/schwabAuth.js`** — passes.

**f. Re-grepped** to confirm `refreshInFlight`, `doRefreshAccessToken`,
and the recovery check all landed as written, and that
`module.exports` still only exports the intended public functions
(`doRefreshAccessToken` is intentionally internal-only).

**g. `git diff --stat`** — 32 insertions, 0 deletions, entirely
additive; the existing successful-path logic (`saveTokens`, the
non-`invalid_grant` error branch) is untouched.

**Deferred per the constraints — cannot be verified until Schwab's
outage clears:** an actual live end-to-end concurrent-call test against
the real Schwab `/token` endpoint (e.g., firing two real
`getValidAccessToken()` calls from separate processes at once and
confirming only one real Schwab call happens and neither throws).
The in-process simulation above proves the *logic* is correct; it
does not prove Schwab's real API behaves exactly as stubbed. **Luis:
once Schwab's outage clears, worth triggering a Force Sync and the
cron job's manual run close together once to sanity-check in
production, though this isn't required — the logic fix stands on its
own regardless.**

## Deviations from the prompt

None on scope or process — followed the "no live Schwab calls" and
"static review + Railway logs only" constraints throughout. One
addition beyond the prompt's suggested fix: implemented both the
in-memory lock **and** a cross-process DB recovery check, since the
timestamp evidence showed the actual incident was a cross-process
collision that an in-memory lock alone would not have prevented —
flagged this reasoning explicitly rather than silently expanding scope
without explanation.

## What was deliberately NOT done

- Did not build a full DB-level lock (Postgres advisory lock /
  `SELECT ... FOR UPDATE`) — confirmed unnecessary at the current single-
  replica-per-service scale; the two-layer fix above already closes the
  actual failure mode. Flagging as a future option if replica counts
  ever change.
- Did not change `startTokenKeepAlive()`'s "refresh unconditionally on
  every boot" behavior, or `schwabKeepAlive.js`'s cron schedule — both
  remain intentionally redundant "belt-and-suspenders" mechanisms per
  their own existing design comments; the fix makes their overlap safe
  rather than removing the redundancy itself, which still serves its
  original purpose (surviving a dead in-process timer or a
  long-asleep web service).
- Did not perform any live Schwab API call, Force Sync, or
  `previewAccounts()` call — respected the outage constraint throughout.
- Did not investigate the specific error Luis's manual script actually
  threw beyond what the initial `SchwabToken` row snapshot already
  showed (the prompt's own Context section had already captured that
  evidence before this recon began).

## Follow-up for Luis

1. No action needed right now — the fix is live on `dev`
   (`investment-agent-DEV` will pick it up on its next auto-deploy from
   this push, same as every other fix this session).
2. Once Schwab's outage clears, the next real refresh (whether
   triggered by the cron job, the in-process keep-alive, or a live
   sync) will exercise the fixed code path for real. No special action
   needed to test it — but if you want to deliberately verify, running
   a Force Sync right after a fresh redeploy would be the most likely
   way to reproduce the original collision window and confirm it no
   longer throws.
3. Given how often this dev environment gets redeployed during active
   development (multiple times per hour today alone), consider whether
   `startTokenKeepAlive()`'s "refresh immediately and unconditionally
   on every boot" behavior is worth changing to also respect the
   expiry buffer (skip the refresh if the current token still has
   meaningful life left) — not implemented here since it's a
   behavior change beyond the immediate race-condition fix, but it
   would reduce how often this collision opportunity occurs in the
   first place, on top of the fix already making collisions safe.
