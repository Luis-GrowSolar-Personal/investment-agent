# Build: Full Reset becomes a frozen snapshot with a 24-hour expiry

**Commit `2853f91`, pushed to `origin/dev`.** Three files:
`server/routes/moves.js`, `server/lib/movesCache.js`,
`client/src/pages/PortfolioManager.jsx`.

Two things to read before the rest: **the prompt's core premise about
`GET /:owner` was wrong**, which changed where the work had to happen;
and **the open question is real and I am reporting rather than fixing
it**, with a concrete example from live data.

## Sequencing

Both dependencies had landed, so I extended rather than duplicated:
- `fix-movescache-preserve-freshstart-out.md` ✔ — its fix is still in
  place; I extended that same code path (see "Sliding-window hole").
- `build-moves-banner-reason-badge-out.md` ✔ — added the `freshStart`
  branch to the existing `MovesBanner`, no second mechanism.

---

## Premise correction — `GET /:owner` was already frozen

The prompt states:

> Today, `GET /:owner` (~line 1915) does NOT freeze anything: it reads
> `isFreshStart` from the cached payload and **recomputes live** via
> `computeMovesPayload(owner, { bypassWinnerProtection, freshStart })`
> on every single view.

**That is not what the code did.** `GET /:owner` was cache-first and
served the stored payload verbatim:

```js
const cached = await prisma.movesCache.findUnique({ where: { owner } });
if (cached) {
  return res.json({ ...cached.payload, fromCache: true, computedAt: cached.computedAt });
}
```

It never called `computeMovesPayload` for a cache hit and never
referenced `isFreshStart`. The code the prompt describes is
**`POST /:owner/refresh`** — the force-recompute endpoint — not `GET`.

This mattered, because it inverts the problem:

- Full Reset was **already** effectively frozen on view. What it lacked
  was an **expiry** — it stayed frozen indefinitely, which is the
  "indefinite stickiness" being removed.
- What actually broke the freeze was the **recompute triggers**:
  `POST /:owner/refresh`, and `refreshMovesCache()` (fired by profile
  PATCH, Schwab sync, price refresh).

So the work was: add the expiry to `GET`, and stop the recompute
triggers from overwriting a frozen snapshot. The prompt's "What to
build" pointed only at `GET`.

**Why I extended to the triggers anyway.** Requirement 1 says the
payload is "served as a frozen snapshot, not recomputed." Without
guarding those triggers, any background price refresh mid-window
replaces the numbers while the banner still says *"generated on
[date]"* — the banner would be actively lying about trade-affecting
figures. A snapshot a background job can silently swap out is not
frozen. Flagged as scope expansion, but I judged it required for the
feature to mean what it claims.

---

## What was built

### 1. Expiry + frozen serve — `GET /:owner`

```js
if (cached.payload?.isFreshStart === true && !isFrozenFullReset(cached)) {
  const payload = await computeMovesPayload(owner, { bypassWinnerProtection: false, freshStart: false });
  // persist -> isFreshStart clears itself going forward
}
// otherwise: serve stored payload, with CURRENT decisions overlaid
const payload  = { ...cached.payload };
applyPriorDecisions(payload.moves, await buildPriorDecisionMap(owner));
```

New `FULL_RESET_TTL_MS = 24h` and `isFrozenFullReset(cacheRow)`,
measured from `computedAt`. No persisted "expired" state — an expired
account just becomes a normal account, per requirement 3.

**The decision overlay is load-bearing, not incidental.** A frozen
payload is never recomputed, and `priorDecision` was previously only
attached *during* computation. Freezing without re-applying it would
mean a move you accepted inside the window silently reverts to
"undecided" on your next reload. To avoid a second copy of that logic
drifting from the first — the exact bug class fixed earlier today in
`movesCache.js` — I extracted `buildPriorDecisionMap(owner)` and
`applyPriorDecisions(moves, map)` from inside `computeMovesPayload` and
call them from both places.

### 2. Freeze guards on the recompute triggers

`POST /:owner/refresh` returns the frozen payload untouched (decisions
overlaid, original `computedAt` preserved). `refreshMovesCache()`
returns early without writing. Leaving the row alone also leaves
`computedAt` alone, so no background activity can extend the clock.

### 3. Sliding-window hole — found while testing, closed

Once past the frozen check, an `isFreshStart` entry is an **expired**
full reset. Both recompute paths previously preserved `isFreshStart`
(correctly, per the earlier fix) — but under this design that would
recompute in full-reset mode **and stamp a fresh `computedAt`,
restarting the 24h window**. A background sync firing at hour 25, before
the user next opened the tab, would silently renew the snapshot forever:
a sliding expiry through the back door, which requirement 2 explicitly
forbids.

Both paths now drop an expired full reset to normal mode (both flags
off). This **extends** the earlier `refreshMovesCache` fix rather than
undoing it: mode preservation still applies to plain re-baseline (which
has no expiry) and within the frozen window.

### 4. Banner — `freshStart` branch

Added to the existing `MovesBanner({ mode, computedAt })` with the
specified copy and the real generation date (`data.computedAt`, already
on the payload and already used elsewhere in the page). Amber left-rule
rather than blue, so the mode reads as distinct at a glance.

---

## The open question — traced, reproduced, and NOT fixed

**Answer: the accepted move disappears entirely from the UI.** The
`OwnerDecision` row survives (permanent, per requirement 4), but nothing
surfaces it.

**Mechanism, precisely:**
1. Full Reset sets `bypassWinnerProtection` (`moves.js:835`:
   `options.bypassWinnerProtection === true || freshStart`).
2. In normal mode, `isWinnerRunning` (`:625`) is true for a
   Strengthening/Add position under its cap, and the generator pushes a
   **`HOLD_ADVISORY`** instead of a trim/exit.
3. `HOLD_ADVISORY` is filtered out of `actionMoves` entirely.
4. Decisions key on `SYMBOL:MOVETYPE`. The decision was recorded as
   `ENVX:EXIT`; the surviving object is `ENVX:HOLD_ADVISORY`. **Even the
   advisory would not carry it** — different key.

**Concrete example, from live data (`Luis Morales`, read-only compare of
both modes):**

```
FULL RESET moves: SPWR:EXIT, ENVX:EXIT, NVDA:ADD, +5 bucket-level ADDs
NORMAL    moves: SPWR:TRIM_CAP, NVDA:ADD

Orphaned on expiry (7), including:
  ENVX:EXIT  $1,292  thesisHealth=Strengthening  finalAction=Add
Normal-mode advisories (winner-protected instead of trimmed):
  ENVX  thesisHealth=Strengthening  finalAction=Add
```

`ENVX` is exactly the hypothesised case. Accept that $1,292 exit during
the window, don't execute, wait 24h — and it vanishes.

**Why I did not fix it.** Beyond needing a new rendering path
(synthesising rows from `OwnerDecision` + `systemSnapshot`, which the
prompt calls out as a deeper pipeline change), there is a genuine design
conflict: **normal-mode logic is actively asserting "do not exit ENVX,
it's a strengthening winner."** Auto-resurfacing the accepted exit would
push you toward a trade the current logic disagrees with. Suppressing it
loses an unexecuted commitment. Which is right is a judgement about what
an expired acceptance *means* — not something to guess at inside a build
task. Per the prompt's instruction, reported rather than guessed.

**Options, if you want it addressed:** (a) surface orphaned accepted
decisions in a separate "committed but not executed" list, sidestepping
the disagreement by not re-asserting the recommendation; (b) re-generate
moves for tickers with unexecuted accepted decisions regardless of
winner protection; (c) accept the loss and rely on the 24h window being
short. I'd lean (a) — it preserves the record without overriding current
logic.

*Also noted:* bucket-level moves key as `null:ADD` (no symbol), so
several share one key. Harmless today since they can't carry decisions
meaningfully, but it would collide if that ever changed.

---

## Verification — 12/12 assertions passed against the live DB

Throwaway script using the **real** exported `isFrozenFullReset`,
`computeMovesPayload` and `refreshMovesCache`; original state saved and
restored.

```
--- A. isFrozenFullReset() boundary ---
PASS — full reset 1h old  -> frozen
PASS — full reset 23h old -> frozen
PASS — full reset 25h old -> expired
PASS — non-full-reset     -> never frozen
PASS — no cache row       -> not frozen

--- B. Frozen window: background refresh must be a no-op (verify 1 + 4) ---
[movesCache] refresh skipped for Luis Morales — full-reset snapshot still frozen
PASS — computedAt UNCHANGED — viewing/refreshing does not extend the expiry clock
PASS — payload UNCHANGED — snapshot genuinely frozen, numbers not recomputed

--- C. Decision overlay on a frozen payload (verify 3) ---
existing decisions: 22; frozen moves: 8; overlapping: 1
PASS — all 1 overlapping move(s) carry priorDecision
   e.g. SPWR:EXIT -> accepted

--- D. Expired window reverts to normal mode (verify 2) ---
PASS — backdated 25h -> no longer frozen
[movesCache] refreshed for Luis Morales (full-reset window expired — reverted to normal mode)
PASS — isFreshStart CLEARED — expired full reset reverted to normal mode
PASS — isRebaseline also false — pure normal mode, not re-baseline
PASS — computedAt advanced only on the real recompute (not while frozen)
```

Mapping to the prompt's list: **1** ✔ (B — payload byte-identical after
a refresh), **2** ✔ (D — backdated 25h, reverted and persisted), **3**
✔ partially (C — overlay proven on a real accepted decision, `SPWR:EXIT`;
decision *permanence* across expiry follows from `OwnerDecision` never
being touched by any of this), **4** ✔ (B — `computedAt` unchanged),
**5** ✘ (banner not seen rendered — no browser), **6** ✔ (below).

Also: `node --check` on both server files; `npx vite build` clean at 112
modules; final cache state confirmed restored for all three owners; temp
scripts and `client/dist/` removed.

**Verify 6 — `verify-allocation-math.sh`** run after the writes. Same
pre-existing failures, identical figures to earlier today (Andrea
`$400.03` / `-$71.87` / `-$245.50`, Luis `$1,920.66`, Eduardo `$5.85` /
`$31.50` / `$31.28`). Unrelated to this change and still open.

## What was NOT verified

**Verify item 5 — the banner was not seen rendered.** Chrome tools are
not connected (fourth session running). The copy, the date substitution
and the `data.computedAt` wiring are source-verified only.

## Deviations from the prompt

1. **Premise correction on `GET /:owner`** (above) — the described
   recompute lives in `POST /:owner/refresh`.
2. **Extended the freeze to the recompute triggers**, which the prompt
   scoped only to `GET`. Without it the "frozen snapshot" is not frozen
   and the banner misstates the generation date.
3. **Closed the sliding-window hole** at expiry in both recompute paths
   — required by requirement 2, not something the prompt anticipated
   because it assumed `GET` was the recomputing path.
4. **Extracted two helpers** from `computeMovesPayload` so the frozen
   path reuses decision-attachment rather than copying it.
5. **Open question reported, not fixed**, per the prompt's own
   instruction for the ambiguous/deep case.

## What was deliberately NOT done

- **Winner-protection / Strengthening exception** — untouched, as
  instructed.
- **No sliding window** — fixed 24h from `computedAt` only.
- **`RebaselineModal` preview-fidelity bug and header-copy overlap** —
  untouched, explicitly out of scope.
- **No orphaned-decision resurfacing** — see open question.
- **No changes to `OwnerDecision`** — decisions remain permanent and
  entirely unaffected by mode expiry.

## Follow-up for Luis

1. **Decide the open question.** It is the one thing here that needs
   your judgement rather than more code. My suggestion is a separate
   "committed but not executed" surface, so an unexecuted acceptance
   isn't lost without re-asserting a recommendation current logic
   disagrees with.
2. **Eyeball the Full Reset banner** — confirm the amber banner appears
   with the correct generation date after confirming a full reset.
3. **Expect a real behavioural change:** during a 24h full-reset window,
   a Schwab sync or price refresh will *not* update the Moves numbers,
   and the log will say so:
   ```bash
   railway logs --service investment-agent-DEV | grep -E "frozen|window expired"
   ```
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 2853f91...
   ```

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.
