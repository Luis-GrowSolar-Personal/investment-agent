# Fix: startTokenKeepAlive() refreshes unconditionally on every boot

**The fix, applied:** `startTokenKeepAlive()`'s `tick()` now checks the
stored token's `expiresAt` against the existing `EXPIRY_BUFFER_MS`
before refreshing — the same check `getValidAccessToken()` already
applies — and returns early when the token still has meaningful life
left. The 24h `setInterval` cadence is unchanged; only whether a given
tick (including the boot-time one) actually calls Schwab changed.
Committed `68a342f`, pushed to `origin/dev`.

**Read this part even if you skip the rest — a premise correction.**
While doing the live verification this prompt asked for, I measured
something that contradicts a belief baked into this codebase's comments,
the prior recon (`recon-schwab-token-refresh-race-out.md`), and this
prompt's own Context section: **Schwab does not appear to rotate the
refresh_token on refresh.** Details and consequences in the "Premise
correction" section below. It does not undermine this fix (which stands
on its own merits), but it does mean the prior fix's stated rationale
was wrong, and there is a user-facing message elsewhere in the app that
is likely telling you something false. Flagged, not changed — see
"What was deliberately NOT done".

## What changed

`server/lib/schwabAuth.js`, inside `startTokenKeepAlive()`'s `tick()`
(the prompt's cited line numbers 199-213 had shifted to ~240-255 after
the prior fix landed — re-read before editing, as instructed):

```diff
       const row = await prisma.schwabToken.findUnique({ where: { id: TOKEN_ROW_ID } });
       if (!row) return; // not connected yet — nothing to keep alive
+      // Same buffer check getValidAccessToken() already applies — skip the
+      // refresh if the current token still has meaningful life left. Without
+      // this, every tick (including the boot-time one) forced a real Schwab
+      // refresh regardless of need, which on a frequently-redeployed service
+      // meant far more refreshes — and far more chances to collide with a
+      // concurrent refresh from elsewhere — than the 24h cadence implies.
+      if (row.expiresAt.getTime() - EXPIRY_BUFFER_MS > Date.now()) return;
       await refreshAccessToken(prisma);
       console.log('[schwabAuth] keep-alive refresh succeeded');
```

Reuses the existing `EXPIRY_BUFFER_MS` constant (60s) rather than
introducing a second threshold, so keep-alive and `getValidAccessToken()`
now agree on what "needs refreshing" means.

Three comment blocks in the same file were also corrected — see the
premise-correction section for why. No logic other than the one-line
buffer check was altered.

## Premise correction: Schwab did not rotate the refresh_token

The prompt's Context (and the prior recon it builds on) treats Schwab's
refresh_token as single-use/rotating. Live measurement on 2026-08-22
says otherwise:

- **Four real refreshes** were performed during this task's verification.
  On the three where I compared before/after, the **stored
  `refreshToken` value never changed**.
- Inspecting one `/token` response body directly showed Schwab **does**
  return a `refresh_token` field (response keys: `expires_in`,
  `token_type`, `scope`, `refresh_token`, `access_token`, `id_token`) —
  it is simply **the same value**, not a rotated one. The `access_token`
  *did* change each time, as expected.
- Corroborating: that same refresh_token dates from the original
  authorization on **2026-06-13** and has been refreshing successfully
  for ~70 days — well past the documented 7-day refresh_token lifetime.

**Consequence for the prior fix (`f16a3ff`):** its stated rationale —
"two concurrent callers race, the first consumes the token, the second
gets `invalid_grant`" — does not hold if the token is never consumed.
Both concurrent callers would simply succeed. So the concurrent-refresh
race is **not** a demonstrated explanation for the original
`SCHWAB_TOKEN_EXPIRED`.

**What most likely did cause it:** Luis independently confirmed (in the
prior recon) that he could not log into Schwab at all via a plain
browser at that time — a Schwab-side outage. The strongest evidence is
that **the very refresh_token supposedly invalidated by that race is
still working right now** — I used it for four successful refreshes
today. A genuinely consumed or expired token would be dead; it isn't.
An outage returning `invalid_grant` spuriously fits every fact:
healthy token, successful refresh 30 minutes prior, confirmed
Schwab-wide unavailability, and full recovery with the same token once
the outage cleared.

**I did not revert the prior fix.** The in-memory lock still prevents
genuinely pointless duplicate API calls (verified below: 5 concurrent
callers → 1 Schwab request), and the cross-process recovery check is a
harmless no-op when tokens don't rotate (its
`fresh.refreshToken !== row.refreshToken` condition is simply false, so
it falls through to the original throw). Both also remain correct
insurance if Schwab's behavior matches its docs at some point. What I
did change is the **comments** asserting the false premise, in three
places — the file header, the `refreshAccessToken` doc block, and
`saveTokens` — since leaving them would mislead the next reader into
trusting a claim I had just disproven. The replacements state only what
was measured, note that the docs say otherwise, and avoid over-claiming
(four observations is not proof Schwab *never* rotates).

The header comment also notes a plausible reconciliation of the 7-day
documented lifetime with a 70-day-old token: the 7 days may be an
**inactivity** window that the keep-alive keeps resetting, rather than
an absolute clock from original authorization.

## Verify

Schwab confirmed reachable again, so all verification below is **live**,
not simulated. All four cases were re-run against the **final** code
after the comment edits.

**1. Fresh token → boot tick must NOT call Schwab.** (Verified first
with a temporary log line inside the new early-return branch; the log
was removed before committing — confirmed via `grep -n "TEMP"` returning
no matches.) Final assertion is on the DB row itself:
```
=== Case 1: fresh token — startTokenKeepAlive() tick should SKIP the refresh ===
token secondsUntilExpiry before: 1733.762
updatedAt unchanged (no refresh happened)? true
```

**2. Expired token → must still refresh (safety behavior preserved).**
Driven through a proxy that reports the *real* row with `expiresAt`
forced into the past, so the only DB write is the legitimate one from a
genuine refresh — no bogus expiry was written to the live row first:
```
=== Case 2: expired token — keep-alive tick should perform a REAL refresh ===
real secondsUntilExpiry: 1785.9 (tick will see it as -600, i.e. expired)
[schwabAuth] keep-alive refresh succeeded
updatedAt changed (real refresh happened)? true
refreshToken rotated by Schwab? false
new expiresAt: 2026-08-22T20:34:07.073Z | secondsUntilExpiry: 1794.7
```

**3. No regression to normal sync behavior**, and the prior fix's
deferred live concurrency check now completed. For 3b I used
`getReconciliation()` — the *exact* call that originally threw
`SCHWAB_TOKEN_EXPIRED` — rather than a full `syncAccount()`, because it
exercises the identical auth path while staying read-only (no
`Lot`/`Position` writes needed to prove the point):
```
=== Case 3a: live concurrency — 5 simultaneous getValidAccessToken() calls ===
all 5 callers got the same access token? true
real Schwab /token calls made (should be 1, not 5): 1

=== Case 3b: the exact call that originally threw SCHWAB_TOKEN_EXPIRED (read-only) ===
getReconciliation() succeeded — matched accounts: 4 | unmatchedSchwab: 0
positions returned per matched account: Andrea ROTH IRA: 4, Eduardo ROTH IRA: 5,
                                        Andrea Custodial: 13, Eduardo Custodial: 13
extra /token calls during this read (0 expected — token already fresh): 0
```
That last line is the fix's value shown directly: a normal read on a
fresh token now costs **zero** Schwab `/token` calls.

**4. `node --check server/lib/schwabAuth.js`** — passes. (It caught a
real mistake mid-task: my first comment edit accidentally closed the
block comment early with a stray `*/`, which would have been a syntax
error. Found and fixed before committing.)

**5. `verify-allocation-math.sh` — deliberately not run.** The prompt
scoped this to "only if this touches anything beyond `schwabAuth.js`".
`git status` confirms exactly one modified file,
`server/lib/schwabAuth.js`, so scope stayed contained and the script
was not applicable.

**6. Cleanup** — all five temporary verification scripts deleted;
`ls server/scripts/_*.js` returns no matches, and `git status` shows
only the one intended file.

## Deviations from the prompt

1. **The prompt's Context restates the single-use/rotation premise as
   settled fact; measurement contradicted it.** Flagged prominently
   rather than quietly implementing on top of it. The requested fix was
   still implemented as specified — it is independently justified
   (fewer pointless API calls on a service that redeploys constantly)
   and does not depend on the race theory being true.
2. **Corrected three comment blocks in `schwabAuth.js` beyond the
   one-line functional change.** Not requested, but leaving comments
   that assert something I had just empirically disproven would
   actively mislead. Confined to the file already being edited; no
   logic changed.
3. **Used `getReconciliation()` instead of a literal Force Sync** for
   verification item 3 (the prompt allowed "or equivalent") — it is the
   exact call that originally failed and is read-only, so it is a
   tighter regression test with fewer side effects than a full sync.

## What was deliberately NOT done

- **Did not change `server/routes/schwab.js:139-145`, though it is
  likely wrong.** Its comment asserts *"Schwab's refresh_token has a
  hard 7-day expiration from the original authorization — rotating it
  on refresh does not reset that clock"*, and on `SCHWAB_TOKEN_EXPIRED`
  it shows the user: *"Broker connection needs reconnecting — Schwab
  requires manual reconnection at least every 7 days."* A 70-day-old
  token that still refreshes fine contradicts the "hard 7-day from
  authorization" claim. This message would also have been actively
  misleading during the outage — telling you to reconnect when the real
  problem was Schwab being down. **Left alone because** (a) it is
  outside this prompt's stated scope (which explicitly expected changes
  confined to `schwabAuth.js`), (b) it is user-facing copy whose
  replacement wording is your call, and (c) you may have information
  from Schwab's developer portal that four observations don't capture.
  Recommend a follow-up prompt for this.
- **Did not revert or weaken the prior fix's lock/recovery logic** —
  see the premise-correction section for the reasoning; that is a
  judgment call for you now that the rationale has changed.
- **Did not touch `schwabKeepAlive.js`** (the separate Railway cron
  job) — explicitly out of scope per the prompt.
- **Did not change the 24h `KEEP_ALIVE_INTERVAL_MS` cadence** — only
  whether a tick acts, as instructed.

## Follow-up for Luis

1. Nothing required — the fix is live on `dev` and
   `investment-agent-DEV` will pick it up on its next auto-deploy from
   this push. Redeploys will now stop forcing a Schwab refresh unless
   the token is actually within 60s of expiry.
2. **Worth a follow-up prompt:** the `schwab.js` "reconnect every 7
   days" message described above. If the 7 days is really an inactivity
   window (which the keep-alive already resets), that message is telling
   you to do manual work you don't need to do.
3. **Worth your judgment:** whether to keep the prior fix's lock +
   recovery logic now that its stated rationale is disproven. My
   recommendation is keep it — it costs nothing and still prevents
   duplicate API calls — but the choice is informed differently now.
4. To confirm the deployed service picked up this commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 68a342f...
   ```
5. To watch the fix working in production — after a deploy, the boot
   log should **no longer** show `[schwabAuth] keep-alive refresh
   succeeded` unless the token was genuinely near expiry:
   ```bash
   railway logs --service investment-agent-DEV | grep schwabAuth
   ```

## Note on the commit trailer

The commit uses `Co-Authored-By: Claude Opus 4.8 (1M context)` because
that is the trailer your `/execute-prompt` workflow specifies verbatim,
and every other commit this session used it. Flagging for accuracy: you
switched the session to **Opus 5** immediately before this task, so this
commit was actually authored by Opus 5. Left as-is to keep your git
history internally consistent rather than silently changing your
convention — update the workflow file if you'd prefer the trailer track
the real model.
