# Fix: three small, unrelated cleanups

All three shipped in one commit, `67c91b4`, pushed to `origin/dev`.
Four files: `client/src/pages/PortfolioManager.jsx`,
`client/src/components/DragScrollContainer.jsx`,
`server/routes/schwab.js`, `client/src/pages/Admin.jsx`.

**Chrome browser tools: NOT connected this session.** Checked before
starting. This matters differently than in the last few tasks, though:
Fixes 1 and 2 were *diagnosed* with live measurements by the session that
wrote `verify-drag-scroll-standardization-out.md`, so the problems are
empirically established — it's only the confirmation that my fixes
resolve them that's unverified. Fix 3 is server-side text and is fully
verified. Per-fix status is called out in each section.

All three premises checked out against current code: the Moves grid div
(now L1809 + the comment I added), `DragScrollContainer`'s early return,
and `schwab.js:139-145`. No line drift beyond the offsets noted.

---

## Fix 1 — Moves grid card chrome — SHIPPED, visually unverified

**Problem** (measured live in the prior verify session): the card styling
sits on the inner grid div, which had no width constraint. A block-level
grid sizes to its container, so the painted box stayed at container width
while `MOVE_GRID_COLS`' fixed tracks overflowed past it — 68px of content
outside the card at an 800px viewport, 368px at 500px, with Amount/Tax/
Decision rendering on bare page background.

**Change** — `PortfolioManager.jsx:1809`:

```diff
-<div style={{ display: 'grid', gridTemplateColumns: MOVE_GRID_COLS, background: C.card, ... }}>
+<div style={{ display: 'grid', gridTemplateColumns: MOVE_GRID_COLS, minWidth: 'max-content', background: C.card, ... }}>
```

**Why `minWidth: 'max-content'` and not `width: 'max-content'`** — the
prompt offered either. `width: max-content` would make the card shrink to
its content on *wide* viewports too, so it would stop filling the
container: a visible regression on desktop, which is the common case.
`minWidth` gives "at least as wide as my content, but still fill the
container when it's wider" — wide viewports unchanged, narrow viewports
covered. That's the same semantics as Portfolio's `minWidth: '100%'` on a
`<table>`, which is what the prompt pointed at as the correct precedent.

I also considered a fixed pixel `minWidth` (the tracks floor at
18+150+100+100+100+90+34+200 = 792px, +24px padding = 816px). Rejected:
it's a magic number that silently goes stale the moment anyone edits
`MOVE_GRID_COLS`. `max-content` derives the same floor automatically.

**Caveat worth knowing:** `max-content` measures the grid's *unwrapped*
content. The Ticker cell uses `flexWrap: 'wrap'`, so if a ticker's badges
+ text are wide, `max-content` could resolve wider than the 792px track
floor — meaning slightly more horizontal scroll extent at narrow widths
than strictly necessary. That's still correct behaviour (the card covers
its content either way), just worth recognising if the scroll range looks
longer than expected.

**Verification:** build passes. **Not visually confirmed** — the prompt
asked for 500px and 800px viewport checks, which need a browser.

---

## Fix 2 — Swallowed click after an outside-ending drag — SHIPPED, logic-verified only

**Problem:** `drag.current.moved` was cleared in only two places — a
fresh `onMouseDown` on a non-interactive target, and `onClickCapture`.
The interactive-tag guard `return`ed *before* the reset. So a drag ending
via `onMouseLeave` (released outside the container) left `moved === true`
with no click to clear it, and the next click on a
`button/a/input/select/textarea` inside the container got eaten. The
prior session confirmed this empirically on Portfolio's ✎ button.

**Change** — `DragScrollContainer.jsx`, `onMouseDown`:

```diff
-    const tag = e.target.tagName.toLowerCase();
-    if (['button', 'a', 'input', 'select', 'textarea'].includes(tag)) return;
+    if (e.target.closest?.('button, a, input, select, textarea')) {
+      drag.current.moved = false;
+      return;
+    }
```

I took the prompt's "simplest" option (clear the flag in the early
return) rather than the `setTimeout(...,0)` alternative — no async
ordering to reason about, and it clears the flag at exactly the moment a
genuine new click begins.

**I also took the optional `closest()` hardening**, which the prompt said
to implement only if clean and low-risk. It is: a one-line swap that
correctly treats icon-content buttons as interactive. It removes the
documented trap where Portfolio's rename `<svg>` button reports
`tagName === 'svg'` and therefore initiated a drag.

**Traced the logic for correctness** (this is reasoning, not observation):

| Sequence | `moved` at click | Outcome |
|---|---|---|
| Drag on `<td>`, release outside, then click ✎ | reset to false by ✎'s own mousedown | click works ← **the bug, fixed** |
| Drag on `<td>`, release inside, click fires | true | suppressed ← correct, unchanged |
| Plain click on ✎, no prior drag | false | click works ← unchanged |
| Plain click on a row, no prior drag | false | row toggles ← unchanged |

The key property: `active` only ever becomes true from a mousedown on a
*non-interactive* target, so the early return can never fire mid-pan. It
only runs when a genuine new click is starting, which is exactly when
clearing the flag is right. Drag-suppression is therefore intact.

**One behavioural side effect to note:** the `closest()` change also
applies to Radar, which shares this component. Radar has SVG-content
buttons; a press on one there previously initiated a drag and now won't.
That's the intended behaviour (buttons shouldn't pan a table) and Radar
doesn't use `suppressClickAfterDrag`, so no click can be swallowed there
— but it is a small change to Radar, which the *previous* task had held
to a strict "pure refactor, don't touch" rule. This task's prompt
explicitly sanctioned the `closest()` change, so I treated that earlier
constraint as superseded. Flagging it so it isn't a surprise.

**Verification:** build passes; logic traced above. **The repro the
prompt asked for — drag, release outside, click ✎ — was not performed**;
it needs a browser.

---

## Fix 3 — Stale Schwab reconnect message — SHIPPED and fully verified

**Problem:** `schwab.js` asserted in comment and user-facing copy that
Schwab's refresh_token has "a hard 7-day expiration from the original
authorization." Disproven on 2026-08-22: a token from the 2026-06-13
authorization was still refreshing ~70 days later, and the refresh_token
did not rotate across four measured refreshes. The message also misfired
during the real incident, telling Luis to reconnect when the actual cause
was a Schwab-side outage.

**Change 1** — `server/routes/schwab.js`. The comment now records what
was actually measured and explicitly declines to assert the replacement
theory as fact:

> This used to assert a hard 7-day refresh_token expiry […] That claim is
> wrong: measured 2026-08-22, a token from the 2026-06-13 authorization
> was still refreshing ~70 days later […] The real lifetime rule is NOT
> established — a 7-day *inactivity* window that the keep-alive job keeps
> resetting fits the evidence, but that's a hypothesis, not a
> measurement. So: don't quote a number here.

New user-facing message:

> "Schwab rejected the stored credentials. If Schwab is reachable and you
> can log in there normally, reconnect via "Reconnect" in Admin > Broker
> Connections; if Schwab itself is down or erroring, this usually clears
> on its own once their service recovers."

Keeps the actionable path, drops the disproven number, and names the
outage case that actually bit last time.

**Change 2 — beyond the prompt's stated scope, flagged deliberately.**
While checking for string-matching consumers I found the *same disproven
claim* in a second place the prompt didn't mention —
`client/src/pages/Admin.jsx:1553`, in the Broker Connections panel that
the server message tells users to go to:

```diff
-{tokenExpired && ' — access token expired, will auto-refresh on next use. Broker requires manual reconnection at least every 7 days.'}
+{tokenExpired && ' — access token expired, will auto-refresh on next use.'}
```

Worth noting this one was *doubly* misleading: `tokenExpired` only means
the short-lived **access** token is past expiry, which is a routine state
that auto-refreshes — so it advertised a non-existent 7-day chore during
normal operation. I fixed it because leaving it would have made Fix 3
cosmetic: the user would still read the false claim in the panel they
were just directed to. Small, text-only, no logic touched.

**Verification — this fix is fully verified:**
- `node --check server/routes/schwab.js` — passes.
- **No string-matching breakage.** Traced the consumer: `Portfolio.jsx`
  does `if (!res.ok) throw new Error(json.error …)` → `setError(err.message)`,
  rendered verbatim as text. Nothing parses or matches the string.
- Repo-wide grep for `SCHWAB_TOKEN_EXPIRED` returns only the throw site
  (`schwabAuth.js:172`) and the comparison here (`schwab.js:143`) — both
  compare the *error code*, not the message, so rewording is safe.
- Grep for `every 7 days` / `7-day expiration` across `client/src`,
  `server/routes`, `server/lib`: **no matches remain.**

---

## Deviations from the prompt

1. **`minWidth: 'max-content'` rather than `width: 'max-content'`** —
   explicitly one of the two options offered; reasoning above (`width`
   would regress wide viewports).
2. **Implemented the optional `closest()` hardening** — the prompt
   allowed it if clean and low-risk; it is. Note the small knock-on to
   Radar, described in Fix 2.
3. **Also fixed `Admin.jsx:1553`**, which the prompt didn't name. Same
   disproven claim, in the panel the server message points users toward;
   leaving it would have defeated the purpose of Fix 3.

## What was deliberately NOT done

- **No visual verification of Fixes 1 and 2** — browser extension not
  connected. The underlying defects are empirically established from the
  prior session's live measurements; my *fixes* are not confirmed.
- **Did not quote a replacement lifetime number** in the Schwab message.
  The evidence rules out the old claim but does not establish the real
  rule, and the prompt was explicit about not inventing one.
- **Did not touch the accurate Admin subtitle** at `Admin.jsx:1513`
  ("Kept alive automatically — reconnect here only if the connection
  lapses"), which is already correct and consistent with the new wording.
- **Did not revisit sticky columns** (still outstanding from
  `fix-position-table-sticky-actions-column-out.md`).

## Follow-up for Luis

1. **Fix 1** — narrow the window to ~500px on Recommended Moves, scroll
   fully right, and confirm the card's border and rounded corner now
   enclose the Decision column instead of it sitting on bare background.
   Then confirm a normal wide window looks exactly as before.
2. **Fix 2** — drag-pan the Portfolio positions table, release the mouse
   *outside* the table, then click ✎ or × on a row. It should act on the
   first click. Also confirm a normal drag-release-inside still doesn't
   open rows, and that plain clicks still work.
3. **Fix 2 side effect** — in Radar, confirm its icon buttons still click
   normally (they should; they just no longer start a drag).
4. **Fix 3** — nothing to check functionally; if you want to see the new
   copy, it appears on a genuine `SCHWAB_TOKEN_EXPIRED` from
   `/api/schwab/reconcile`.
5. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 67c91b4...
   ```
6. Still worth reconnecting the Chrome extension when convenient — the
   one session that had it produced far better findings than the
   analysis-only ones, including both bugs fixed here.

## Note on the commit trailer

Unchanged: the commit says `Co-Authored-By: Claude Opus 4.8 (1M context)`
per your `/execute-prompt` workflow, but this session runs **Opus 5**.
Flagging again for accuracy.
