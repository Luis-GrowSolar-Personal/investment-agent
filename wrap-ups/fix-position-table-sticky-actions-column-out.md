# Fix: standardize horizontal scroll across all data tables

## Chrome browser tools: NOT CONNECTED — third session running

`tabs_context_mcp` returned *"Browser extension is not connected"* again,
checked first thing as this prompt asked. So, stated plainly and not
buried: **nothing in this task has been verified visually.**

This is now the third consecutive Portfolio-table task shipping without
visual verification. The prompt said that "needs to either stop, or be
flagged loudly again." Given that, and given what I found while working,
**I stopped after part 3 of 4 rather than shipping the riskiest part
blind.** Reasoning in "Part 4" below.

**Shipped (commit `af48727`, pushed to `origin/dev`):** parts 1–3 —
the shared `DragScrollContainer`, applied to Portfolio's positions table
and the Recommended Moves grid.
**Not shipped:** part 4 — sticky identity/action columns.

## Premise check — two findings that changed the implementation

Both premises about *where* the code lives were accurate:
`DragScrollContainer` at `Radar.jsx:1601-1654`, `MOVE_GRID_COLS` at
`PortfolioManager.jsx:408` rendered at ~1803, Portfolio's
`overflowX: 'auto'` wrapper at ~377. No drift.

But two things about *what the code does* weren't as the prompt assumed:

**1. `DragScrollContainer` was not a generic scroll container.** It had
Radar's card chrome hardcoded inside it:

```js
background: '#090c12', border: '1px solid #1e2330', borderTop: 'none',
borderRadius: '0 0 10px 10px', padding: '12px 20px 16px',
```

`borderTop: none` + bottom-only corner radius — that's specifically the
bottom half of a Radar section card. Dropping it into Portfolio and
PortfolioManager as-is would have injected a stray bordered, padded,
round-bottomed panel into both layouts. So the extraction couldn't be a
pure copy: the shared component now takes a `style` prop merged over the
functional defaults, and Radar passes its chrome in as
`RADAR_SCROLL_CHROME`. Same seven computed properties, same values —
rendering unchanged.

**2. The 5px threshold does *not* prevent a click after a drag.** The
prompt states (verify item 4) that "the 5px-threshold logic already
handles this in Radar." Reading it, `drag.moved` gates whether *panning*
happens and triggers `preventDefault()` on mousemove — which stops text
selection, not the subsequent `click` event. After a drag, the browser
still fires `click` on the common ancestor of mousedown/mouseup.

That's latent-but-harmless in Radar (its content has no row-level click
handlers), but both new call sites do:
- `Portfolio.jsx` — `<tr onClick={() => setExpanded(e => !e)}>`
- `PortfolioManager.jsx:465,470` — MoveRow cells, `onClick={() => setExpanded(e => !e)}`

So applying the component as-is would have made panning either table
toggle open every row you dragged across — precisely the failure verify
item 4 is meant to catch. I added an **opt-in** `suppressClickAfterDrag`
prop (capture-phase click handler that swallows the click when `moved`
is set), defaulting to **off** so Radar stays a genuinely pure refactor
per step 1, and turned it on at both new call sites.

## What changed

**New — `client/src/components/DragScrollContainer.jsx`**
Handler bodies (`onMouseDown`/`onMouseMove`/`onMouseUp`) are byte-identical
to Radar's original. Added: the `style` prop, and `onClickCapture`:

```jsx
function onClickCapture(e) {
  if (!suppressClickAfterDrag) return;
  if (!drag.current.moved) return;
  drag.current.moved = false;
  e.stopPropagation();
  e.preventDefault();
}
```

**`Radar.jsx`** — local definition deleted, imported instead, chrome
passed via `RADAR_SCROLL_CHROME`. No other change.

**`Portfolio.jsx`** — `<div style={{ overflowX: 'auto' }}>` →
`<DragScrollContainer suppressClickAfterDrag>`. The `minWidth: '100%'`
table cap and the Symbol/Name `maxWidth` truncation from the two prior
fixes are all preserved, as instructed.

**`PortfolioManager.jsx`** — the `MOVE_GRID_COLS` grid wrapped in
`<DragScrollContainer suppressClickAfterDrag>`.

**Why part 3 should fix the "ugly cutoff":** `MOVE_GRID_COLS` is
`'18px minmax(150px,1.4fr) 100px 100px 100px 90px 34px 200px'`. The five
fixed-px tracks can't shrink and the Ticker track has a 150px floor, so
the grid's minimum width is ~792px + 24px padding. Below roughly 820px
of viewport it *must* overflow — and previously nothing was catching
that overflow. That matches the symptom exactly. Note the `fr` unit
means it still fills wider viewports as before.

## Part 4 (sticky columns) — not shipped, and why

The prompt's own step 3 sets a gate: *"confirm this alone fixes the 'ugly
cutoff on resize' symptom **before** adding sticky columns on top."* With
no browser I can't confirm it, so layering the finicky part on an
unconfirmed base would compound risk rather than reduce it.

More concretely, I read both call sites and each has a real blocker that
needs eyes, not analysis:

**Portfolio — hover is imperative.** Row hover is applied directly to the
DOM node:
```jsx
onMouseEnter={e => e.currentTarget.style.background = '#0d1018'}
onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
```
A sticky `<td>` needs its own opaque background or scrolled content
bleeds through it. But that background would be static, while the row's
flips on hover — so every hover would show a mismatched stripe under the
two sticky cells. Doing it right means converting this to React hover
state and threading the colour into the sticky cells: a real behavioural
refactor of `PositionRow`, unverifiable here.

**Recommended Moves — the row backgrounds are semi-transparent.**
```js
const rowBg = idx % 2 === 0 ? 'transparent' : C.card + '80';
```
Both states are see-through (`transparent`, and `80` = 50% alpha), which
is exactly what a sticky cell cannot use. Each needs an opaque equivalent
chosen to match how the current translucent colour resolves over the card
beneath — a colour-matching judgment that wants a screen.

Neither is hard with a browser open. Both are a coin-flip without one,
and this is the surface where you accept and decline trades. After three
prior blind CSS attempts on this same table that didn't fully land, a
fourth felt like the wrong call.

## Verification performed

- **`npx vite build`** — clean; module count 110 → 111, confirming the
  new component is actually bundled. (No linter configured;
  `node --check` doesn't handle JSX, so the build is the syntax gate.)
- **Radar refactor is inert** — verified by reading the diff: handler
  bodies unchanged; the seven style properties resolve to the same
  values; `onClickCapture` is a no-op when `suppressClickAfterDrag` is
  false (Radar's default). Also confirmed `useRef` is still used at
  `Radar.jsx:449` (`mountedRef`), so removing the local component didn't
  orphan the import.
- **Prior fixes preserved** — `minWidth: '100%'`, Symbol `maxWidth: 130`
  and Name `maxWidth: 200` all still present in `Portfolio.jsx`.
- **Scope** — exactly four files touched, all intended; `git status`
  shows nothing stray. Regenerated `client/dist/` removed.

## What I could NOT verify — all five of the prompt's visual checks

Items 1–5 of the Verify section were **not performed**: Radar
pixel-identity, Portfolio drag behaviour on Andrea→Commodities and
Eduardo→Equities, Recommended Moves narrow-viewport resize, the
drag-vs-click threshold in practice, and normal-width appearance.

The click-suppression logic in particular is *reasoned*, not observed. It
should be right, but "should" is doing real work in that sentence.

**Please confirm visually before treating this as closed.**

## Deviations from the prompt

1. **Stopped after part 3 of 4** — reasoning above. Parts 1–3 stand on
   their own and deliver the Moves-grid fix.
2. **`DragScrollContainer` gained two props** rather than moving
   verbatim. The `style` prop was forced by the hardcoded Radar chrome;
   `suppressClickAfterDrag` by the click-after-drag gap. Both default to
   preserving existing behaviour, so step 1 remains a pure refactor for
   Radar.
3. **Commit message differs from the one in the prompt.** The prompt's
   message advertises sticky columns; since those aren't in the commit,
   using it verbatim would have put a false claim in the git history. I
   described what actually landed and pointed at this wrap-up.

## What was deliberately NOT done

- **Sticky identity/action columns** on either table (part 4).
- **No second scrolling mechanism** — no arrow ribbon, no new gesture
  code, per the prompt's explicit instruction.
- **No sticky treatment on Radar** — correctly out of scope; it only
  received the extraction.
- **Did not "fix" the click-after-drag gap in Radar** — the new
  suppression is opt-in and off there, keeping step 1 a pure refactor. If
  you'd rather Radar have it too, it's a one-word change.
- **Did not touch the prior fixes'** `maxWidth` values.

## Follow-up for Luis

1. **Verify parts 1–3 before I do part 4.** Specifically:
   - **Radar** — drag-scroll a section; it should feel exactly as before,
     with no visual change to the card.
   - **Recommended Moves** — narrow the window below ~820px. Accept/
     Decline should now be reachable by dragging instead of falling off.
     This is the part most likely to be immediately visible.
   - **Portfolio** — drag a positions table horizontally and confirm
     rows do **not** pop open as you pan. That exercises the new
     click-suppression, the piece I'm least able to vouch for.
2. **Then tell me to do part 4** and I'll add the sticky columns —
   including the `PositionRow` hover-state refactor and opaque row
   colours for the Moves grid. If your Chrome extension is reconnected by
   then I can verify it properly; if not, at least it'll be layered on a
   confirmed-working base.
3. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect af48727...
   ```
4. Worth a look when convenient: reconnecting the Chrome extension
   (https://claude.ai/chrome, may need a Chrome restart). Four of these
   table tasks in a row have been analysis-only, and this one had to stop
   early because of it.

## Note on the commit trailer

Unchanged from the last three tasks: the commit says `Co-Authored-By:
Claude Opus 4.8 (1M context)` because that's what your `/execute-prompt`
workflow specifies verbatim, but this session is running **Opus 5**.
Flagging again for accuracy.
