# Fix: three small, unrelated cleanups (Moves grid chrome, swallowed click, stale Schwab reconnect message)

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-moves-chrome-swallowed-click-schwab-message-out.md`.
Three independent, small, low-risk fixes bundled into one task — treat
each as its own section in the wrap-up, verify each separately. Write
for someone reading cold later.

## Fix 1 — Recommended Moves grid card chrome doesn't cover overflow

Found in `wrap-ups/verify-drag-scroll-standardization-out.md`, check 2.
`PortfolioManager.jsx:1809`'s grid div carries the card's `background`,
`border`, and `borderRadius: 10`, but has no `width: max-content` or
`minWidth` — so at narrow viewports the painted card box stays at
container width while `MOVE_GRID_COLS`' 792px floor of content overflows
past it. Measured live: 68px of content outside the card at 800px
viewport, 368px outside at 500px — Amount/Tax/Decision columns render on
bare page background with no border/rounded corner once scrolled to.

Fix: add `width: 'max-content'` (or an equivalent `minWidth` matching
the grid's actual content floor) to that div, same pattern already used
correctly on Portfolio's `<table>` (`Portfolio.jsx:407`,
`minWidth: '100%'`). Read the current file first — line numbers may
have shifted.

Verify: at 500px and 800px viewports, confirm the card's background/
border now extends to cover the Decision column when scrolled fully
right. Confirm normal (wide) viewport rendering is unchanged.

## Fix 2 — One click swallowed after a drag that ends outside the container

Found in the same verify wrap-up, check 3. In
`client/src/components/DragScrollContainer.jsx`, `drag.current.moved`
is only ever cleared in two places: a fresh `onMouseDown` on a
non-interactive target, and inside `onClickCapture`. The interactive-tag
early return in `onMouseDown` skips the reset:

```js
const tag = e.target.tagName.toLowerCase();
if (['button','a','input','select','textarea'].includes(tag)) return;  // moved NOT reset
```

If a drag ends via `onMouseLeave` (pointer leaves the container before
release) rather than a normal `mouseup` inside it, `moved` stays `true`
with no click having fired to reset it — so the next click on a
`<button>`/`<a>`/`<input>`/`<select>`/`<textarea>` inside the container
is silently swallowed by `onClickCapture`. Confirmed live: one lost
click on Portfolio's Edit-lots (✎) button following an outside-drag-end,
the click after that works normally. Row clicks are unaffected (a row's
`mousedown` lands on a `<td>`, which takes the normal reset path).

Fix: clear `drag.current.moved = false` in the interactive-tag early
return (simplest), OR reset it in `onMouseUp`/`onMouseLeave` via
`setTimeout(..., 0)` so a pending click still observes the correct
value before the reset. Pick whichever is simpler once you're looking
at the actual current code — both were suggested in the verify wrap-up
as viable directions, neither was implemented yet.

Also worth a look while in this file (found during verification, not
a blocker): Portfolio's rename button is built from an `<svg>`, so
`e.target.tagName` for a press on it resolves to `svg`/`path`, not
`button` — meaning it does NOT hit the interactive-tag exclusion and
therefore DOES initiate a drag on mousedown. This happens to make it
immune to the bug above (its own mousedown resets the flag), but it's a
latent trap: if `✎` or `×` are ever swapped from text glyphs to SVG
icons, they'd silently start taking this same path. Consider checking
`e.target.closest('button, a, input, select, textarea')` instead of a
bare `tagName` check, which would correctly cover icon-content buttons
too — implement only if it's a clean, low-risk change; otherwise leave
as a documented note in the wrap-up for later.

Verify: reproduce the original bug on the current code first (drag,
release outside the container, then click ✎ or × — confirm it currently
does nothing), then confirm the fix makes that same sequence work
correctly. Confirm normal drag-and-release-inside behavior, and normal
single clicks with no preceding drag, are both unaffected.

## Fix 3 — Stale/misleading Schwab reconnect message

Found in `wrap-ups/fix-keepalive-unconditional-refresh-out.md`,
"What was deliberately NOT done." `server/routes/schwab.js:139-145` has
a comment asserting Schwab's refresh_token "has a hard 7-day expiration
from the original authorization — rotating it on refresh does not reset
that clock," and shows the user a message on `SCHWAB_TOKEN_EXPIRED`:
"Broker connection needs reconnecting — Schwab requires manual
reconnection at least every 7 days."

This was empirically contradicted the same day: a token from the
original 2026-06-13 authorization was still refreshing successfully
~70 days later (see `wrap-ups/fix-keepalive-unconditional-refresh-out.md`,
"Premise correction" section) — access_token rotates, refresh_token does
not appear to. The most likely real explanation is a 7-day *inactivity*
window that the keep-alive job already resets, not an absolute clock
from original authorization — but that wrap-up is honest that four
observations isn't proof of the mechanism, only proof the "hard 7-day
from auth" claim as currently worded is wrong.

This message was also actively misleading during last week's real
incident: it would have told Luis to manually reconnect when the actual
cause was a Schwab-side outage unrelated to token age.

Fix: update both the comment and the user-facing message. Keep the
comment honest about what's actually known (rotates on access_token,
refresh_token behavior doesn't match the documented 7-day-from-auth
claim, real mechanism unconfirmed) rather than asserting a new unproven
theory as fact. For the user-facing message, keep the actionable part
(reconnecting via `/api/schwab/connect` is the correct response to a
genuine `SCHWAB_TOKEN_EXPIRED`) but drop or soften the specific,
disproven "at least every 7 days" framing — don't invent a replacement
number without evidence. Read the current file before editing.

Verify: `node --check server/routes/schwab.js`. Confirm the message
still renders sensibly in whatever UI surfaces it (check where this
error message is actually displayed to the user — grep for how the
frontend consumes this error — and confirm the wording change doesn't
break any string-matching logic elsewhere in the codebase, e.g. anything
checking for "7 days" in the response text).

## Commit and push

One commit is fine for all three, or three separate commits — your
call, but make the commit message(s) accurately describe what's in
them (don't claim more than what's included, per this session's
established convention).

```bash
git add -A
git commit -m "Fix Moves grid overflow chrome, swallowed post-drag click, and stale Schwab reconnect message"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-moves-chrome-swallowed-click-schwab-message-out.md`
existing, with each of the three fixes verified and reported separately.
