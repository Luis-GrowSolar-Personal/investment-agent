# Verify: Moves grid chrome overflow + swallowed-click fixes

## Report your findings

Write a wrap-up to
`./wrap-ups/verify-moves-chrome-swallowed-click-out.md`. This is a
**verification-only task — no code changes.** Report defects clearly
rather than fixing them. Write for someone reading cold later.

## Context

`prompts/fix-moves-chrome-swallowed-click-schwab-message.md` addressed
three issues found in `wrap-ups/verify-drag-scroll-standardization-out.md`:
1. Recommended Moves grid card chrome not covering overflow content.
2. A click swallowed on `<button>`/`<a>`/`<input>`/`<select>`/`<textarea>`
   targets after a drag ends outside `DragScrollContainer`.
3. A stale/misleading Schwab reconnect message (`server/routes/schwab.js`)
   — **not visually testable** without forcing a real token expiry; skip
   this one in the browser and instead just confirm via source read that
   the message/comment text was actually changed as described in that
   fix's wrap-up.

## Before testing — confirm fresh deploy, not a cached view

1. Check `investment-agent-DEV`'s deployed commit hash matches the fix
   commit from `wrap-ups/fix-moves-chrome-swallowed-click-schwab-message-out.md`
   (read that wrap-up first for the exact commit hash — don't assume
   `af48727`, that's the *prior* fix's commit and will be stale by now).
   ```
   railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(n['node']['serviceName'], (((n['node'].get('latestDeployment') or {}).get('meta') or {}).get('commitHash') or '')[:8]) for e in d['environments']['edges'] for n in e['node']['serviceInstances']['edges']]"
   ```
   If it doesn't match, stop and report — don't test stale code.
2. **Hard-refresh the actual browser tab before testing anything.** A
   normal navigate can serve a cached bundle even after a new deploy.
   Use whatever the Chrome tools support for a cache-busting reload —
   e.g. navigate to the URL with a `?_=<timestamp>` query param appended,
   or use the JS tool to run `location.reload(true)` / a hard reload
   equivalent, or close and reopen the tab fresh. State explicitly in
   the wrap-up which method you used and that you confirmed the loaded
   JS bundle is the new one (e.g. check a network request's response
   timestamp/hash, or confirm behavior actually changed from the known
   pre-fix state) — don't just assume a normal reload picked up new code.

## What to check

**1. Recommended Moves grid chrome (was: content overflowing outside the
card's background/border).**
- Navigate to an owner's Moves/Action Required view with the grid
  actually overflowing (per the prior verify wrap-up, this needs
  roughly ≤800px viewport width; Chrome's own minimum is ~500px — use
  that as the narrow case, same as before).
- Scroll/drag the grid fully right to reveal the Decision column.
- Confirm the card's background and border now extend to fully cover
  the Decision column — no content rendering on bare page background,
  no missing border, correct rounded corner in the right place.
- If possible, measure this concretely the way the prior verification
  did (computed style / bounding box of the card vs. the content), not
  just an eyeball — reuse that approach if the tools support it.

**2. Swallowed click after outside-drag-end.**
- On a Portfolio positions table with enough columns to overflow
  (Eduardo Custodial, per prior verification), drag-pan the table and
  release the mouse **outside** the table's bounds (drag off the edge)
  rather than releasing inside it.
- Immediately click the Edit-lots (✎) or Remove (×) icon on any row.
- **Before this fix, this click did nothing.** Confirm it now correctly
  reaches the button (same capture-phase-detector technique the prior
  verification used to prove a click "reached the button" without
  actually invoking a real edit/delete on live data — don't trigger a
  real edit or delete).
- Confirm the click immediately after that one also still works
  (make sure the fix didn't just shift which click gets swallowed).
- Confirm normal behavior is unaffected: a plain click with no
  preceding drag still works; dragging fully inside the container and
  releasing inside it still works and doesn't toggle rows.

**3. Schwab message — source-only, not browser-testable.**
Read `server/routes/schwab.js` directly (via the repo, not the browser)
and confirm the comment and user-facing message text were actually
changed from what's quoted in the original fix prompt. Report what the
new text says. Do not attempt to force a real `SCHWAB_TOKEN_EXPIRED` to
see it live — that requires an actual broken token, which isn't
something to manufacture for a UI check.

## What NOT to do

- Do not click Accept/Decline on any real move, or Remove/Edit on any
  real position — verification only, look don't act (same as before).
- Do not trigger a Force Sync or any Schwab API call.
- Do not attempt to intentionally break Schwab's stored token to test
  fix 3 live.

## Report format

For each of the three checks, state **PASS**, **FAIL**, or **COULD NOT
TEST** (with why), plus what was actually observed. If anything fails,
describe it precisely enough that a follow-up fix could be scoped
without re-investigating from scratch.

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/verify-moves-chrome-swallowed-click-out.md` existing, with a
clear verdict for each of the three checks.
