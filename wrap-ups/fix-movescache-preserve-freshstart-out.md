# Fix: refreshMovesCache silently drops isFreshStart

**Fixed and pushed — commit `9ac0c20`, one file
(`server/lib/movesCache.js`).** The regression was reproduced against
the live database *before* the fix and proven resolved *after*, so this
one isn't resting on analysis.

## Premise check — accurate in every particular

Both halves of the prompt's diagnosis verified against current code:

- `server/routes/moves.js:1958-1962` (`GET /:owner`) reads and preserves
  **both** flags — exactly the pattern to copy.
- `server/lib/movesCache.js:36-37` read only `isRebaseline`.
- `computeMovesPayload` accepts and honours `freshStart`
  (`moves.js:834-835`) and writes both flags back into the payload
  (`:1907-1908`), so the round-trip is sound.
- Callers confirmed: `routes/users.js:302` (profile PATCH),
  `routes/schwab.js:203` (account sync), `routes/schwab.js:357`
  (`refreshAllMovesCache`).

Line numbers had drifted by ~1-2 from the prompt's estimates; nothing
material.

## What changed

```diff
     const bypassWinnerProtection = existing?.payload?.isRebaseline === true;
-    const payload    = await computeMovesPayload(owner, { bypassWinnerProtection });
+    const freshStart             = existing?.payload?.isFreshStart === true;
+    const payload    = await computeMovesPayload(owner, { bypassWinnerProtection, freshStart });
```

Plus two small additions beyond the literal ask, both flagged below:

**The log line.** Inside `computeMovesPayload`,
`bypassWinnerProtection = options.bypassWinnerProtection === true || freshStart`
(`moves.js:835`), and the payload stores `isRebaseline: bypassWinnerProtection`
(`:1907`). So a **Full-reset entry carries *both* flags true** — meaning
the old log line would have reported it as merely
`(preserved re-baseline mode)`, understating what was preserved and
making exactly this class of bug harder to spot in Railway logs. Now:

```js
const preserved = freshStart ? ' (preserved full-reset mode)'
  : bypassWinnerProtection ? ' (preserved re-baseline mode)'
  : '';
```

**A header-comment note** recording the 2026-08-23 extension, matching
the existing 2026-08-08 `isRebaseline` entry directly above it — that
comment is the reason this file's history is legible, and the same
omission recurring is precisely what it exists to prevent.

## Verify

### 1 + 2 — the regression, reproduced and fixed (live DB)

No account was in Full reset (`isFreshStart=false` for all three owners),
so I set one up as the prompt allowed, using `Luis Morales`. A throwaway
script seeded each mode via `computeMovesPayload`, called the real
`refreshMovesCache()` — the same function `users.js`/`schwab.js` call —
then read the cache back, and finally restored the original state.

**With the fix:**
```
ORIGINAL   Luis Morales: isRebaseline=true isFreshStart=false

--- Case 1: seed Full-reset mode, then call refreshMovesCache() ---
seeded     : isRebaseline=true isFreshStart=true
[movesCache] refreshed for Luis Morales (preserved full-reset mode)
after call : isRebaseline=true isFreshStart=true
PASS — isFreshStart survived the refresh

--- Case 2: seed isFreshStart=false, then call refreshMovesCache() ---
seeded     : isRebaseline=true isFreshStart=false
[movesCache] refreshed for Luis Morales (preserved re-baseline mode)
after call : isRebaseline=true isFreshStart=false
PASS — stayed false, no spurious promotion into Full-reset

--- Restoring original state ---
RESTORED   Luis Morales: isRebaseline=true isFreshStart=false
```

**Proof the test isn't vacuous.** I then `git stash`-ed the fix and re-ran
Case 1 against the unfixed code:

```
seeded     : isRebaseline=true isFreshStart=true
[movesCache] refreshed for Luis Morales (preserved re-baseline mode)
after call : isRebaseline=true isFreshStart=false
FAIL — isFreshStart was dropped
```

That is the reported bug, reproduced exactly: one background refresh,
silently out of Full reset. Fix restored immediately after
(`git stash pop`).

### 3 — `moves.js` untouched
`git diff --stat server/routes/moves.js` → no changes. `git status` shows
exactly one modified file, `server/lib/movesCache.js`.

### 4 — `node --check server/lib/movesCache.js` — passes.

### 5 — `verify-allocation-math.sh` — run, no change

Same failures as before this fix, to the cent: Andrea Established
`$400.03` (and freshStart `-$71.87` / `-$245.50`), Luis Speculative
`$1,920.66`, Eduardo Established `$5.85` (freshStart `$31.50` / `$31.28`).

These are **pre-existing and unrelated** — the same figures I documented
earlier this session in
`wrap-ups/recon-full-exit-position-status-not-closed-out.md`, where a
revert/re-run test proved they predate that work too. Confirmed rather
than assumed, as the prompt asked. Still open, still worth a dedicated
look.

### 6 — Database left clean

`MovesCache` for all three owners is back to `isRebaseline=true,
isFreshStart=false` — the state found at the start. Only `computedAt`
for Luis Morales differs (naturally, having been recomputed). No
`Lot`/`Position`/`Account`/`OwnerDecision` rows were touched; `MovesCache`
is a derived cache that any page load recomputes.

Both temporary scripts deleted.

## Deviations from the prompt

1. **Improved the log line** — not requested. Justified because a
   full-reset entry sets both flags, so the existing message actively
   under-reported the preserved mode, which would have made this bug
   harder to catch from logs.
2. **Added a header-comment note** dating the extension, mirroring the
   existing 2026-08-08 entry.
3. **Seeded Full-reset mode on `Luis Morales`** to run the test, since
   no account was in that mode — explicitly permitted ("or set up, if
   none currently exists"). Original state restored and verified.

Neither addition changes control flow beyond the one-line fix.

## What was deliberately NOT done

- **Did not touch `moves.js`'s `GET /:owner` path** — already correct;
  this fix brings the other path in line with it.
- **Did not investigate the `verify-allocation-math.sh` failures** —
  pre-existing and out of scope.
- **Did not audit other flags** for the same drop-through pattern.
  `isRebaseline` and `isFreshStart` are the only two mode flags in the
  payload today, and both are now handled — but the underlying hazard
  (a new mode flag added to `computeMovesPayload` and wired into
  `moves.js` but not `movesCache.js`) remains structural. Worth a note
  for whoever adds a third.

## Follow-up for Luis

1. **Nothing required.** The path that was silently reverting Full reset
   is fixed and verified end-to-end.
2. To see it working in production: put an account into Full reset, then
   trigger a Schwab sync or save any Admin profile change. Railway logs
   should now read:
   ```bash
   railway logs --service investment-agent-DEV | grep movesCache
   # expect: [movesCache] refreshed for <owner> (preserved full-reset mode)
   ```
   Previously that same event logged `(preserved re-baseline mode)` while
   dropping the flag.
3. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 9ac0c20...
   ```
4. Structural note for later: if a third mode flag is ever added to the
   moves payload, it has to be wired into **both** `movesCache.js` and
   `moves.js`. This is the second time that pairing has been missed.

## Note on the commit trailer

Unchanged: the commit says `Co-Authored-By: Claude Opus 4.8 (1M context)`
per your `/execute-prompt` workflow, but this session runs **Opus 5**.
