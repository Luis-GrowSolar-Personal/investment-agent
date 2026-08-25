# Wrap-up: fix-mobile-nav-tabs-unreachable

**Verified live in Chrome at narrow width: YES** (see Verification). Not verified on
Luis's actual phone hardware — see "Left for the user".

## Premise check

The prompt's premise was accurate and is now quantified. `NavBar.jsx` had the tab strip
at `flex: 1, minWidth: 0` (line 128) beside a `flexShrink: 0` right-hand group (line 149)
holding Schwab status + full email + Sign out. Measured in Chrome with the pre-fix styles
restored, at a 390px-wide nav:

| | right-hand group | tab strip | fully visible tabs |
|---|---|---|---|
| before fix | **397.7px** | **0px** | **0** |
| after fix | 82.2px | 280px | 2 (+3 by scroll) |

The right group was *wider than the whole viewport*, so the strip collapsed to zero and
only the overflowing first tab painted. Worse than the prompt described.

## Changes

**`client/src/index.css`** — added a `@media (max-width: 768px)` block after the existing
`.navbar-tabs` rules (which are unchanged; horizontal scroll is retained per item 4):
- `.navbar-email { display: none }` — email isn't actionable, dropped on mobile.
- `.navbar-schwab-text { display: none }` — Schwab status reduced to its `⟳` icon; the
  full label survives as the `title` tooltip. Status not removed, just shrunk.
- `.navbar-right { gap: 8px }` and `.navbar-root { padding: 0 12px }` — tighter chrome.
- `.navbar-tabs` gets a right-edge `mask-image` fade (`calc(100% - 28px)` → transparent):
  the visible "there's more, swipe" affordance (item 2).
- `.navbar-tabs { touch-action: pan-x }` + `.navbar-tabs a { min-height: 36px;
  display: inline-flex; align-items: center; touch-action: manipulation }` — bigger tap
  targets (36px vs the previous ~23px) and `manipulation` tells the browser not to hold a
  tap waiting to see if it becomes a gesture (item 3).

Sign out stays inline at all widths — at 82px total the right group no longer starves the
strip, so hiding it behind a menu would have been over-engineering.

**`client/src/components/NavBar.jsx`** — hooks for those rules only, no logic change:
- L114 `<nav className="navbar-root" …>`
- L149 right-hand group gets `className="navbar-right"`
- L150-156 Schwab span gets `title={schwabStatus.label}`, `whiteSpace: 'nowrap'`, and the
  label text wrapped in `<span className="navbar-schwab-text">`
- L158 email span gets `className="navbar-email"`

## Verification

Chrome tools were connected. Verified against the running Vite dev server
(`localhost:5173`) with the real `index.css` loaded.

1. **Narrow width, 390px** — 2 tabs fully visible, `scrollWidth` 536 vs `clientWidth` 280,
   remaining 3 reachable by scroll. `emailShown: none`, `schwabTextShown: none`,
   mask applied.
2. **Fade affordance present** — screenshot at 390px shows "Portfolio Manager",
   "At a Glance", and "Acc…" softly fading at the right edge. Visually confirmed.
3. **Tap, not drag, navigates** — scrolled the strip to its end, then issued a real single
   `left_click` (no drag) on the "Admin" tab at its center. URL changed to `#/admin`.
   The tap was not swallowed as a scroll.
4. **Desktop unchanged, 1300px** — `maskImage: none`, email `block`, Schwab label
   `inline`, nav padding `0px 24px`, `minHeight: auto`, no overflow. Every mobile rule is
   inert above the breakpoint.
5. `npx esbuild src/components/NavBar.jsx` parses clean.

**Verification caveats (stated plainly rather than glossed):**
- Chrome refuses to size a window below **500 CSS px**, so the 390px case was measured by
  constraining the harness nav element to `width: 390px` while the 768px media query was
  already active at the 500px window. Layout measurements are real; the viewport itself
  was 500px.
- The app requires Clerk sign-in and I am not permitted to enter credentials, so the
  signed-in `NavBar` could not be reached. Verification used a harness that reproduces the
  NavBar DOM **verbatim** (same classes, same inline styles, same 5 tabs) injected into the
  running app page, so the real `index.css` applied. Everything tested here is CSS/DOM
  behavior, which the harness reproduces faithfully — but it is not the live component.
- Emulated mouse click, not a real touchscreen touch. `touch-action: manipulation` and the
  36px targets are the standard remedy but were not exercised by a finger.

## Deviations from the prompt

- The prompt's commit block says `git add -A`. The project's standing convention (and the
  repo state — ~35 untracked wrap-ups, `prompts/`, `testing/`, `client/dist/`) makes that
  wrong, so I staged only the two changed source files plus this wrap-up.

## Not done / left for the user

- `DragScrollContainer` and table scroll: untouched, as instructed.
- Desktop nav: not redesigned.
- **Luis should tap through all 5 tabs on his actual phone before calling this closed.**
  Given caveats above, this is verified-in-emulation, not verified-on-hardware.

## Follow-up

```bash
cd client && npm run dev
# then open http://localhost:5173 in Chrome DevTools device mode at iPhone 14 (390x844)
```
