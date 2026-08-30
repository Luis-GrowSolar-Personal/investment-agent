# Verify: shared drag-scroll standardization — OUT

**Task type:** verification only. No code changed, nothing committed.
**Date:** 2026-08-23
**Commit under test:** `af48727`
**Environment:** `https://investment-agent-dev-production.up.railway.app`
(Andrea Morales / Eduardo Custodial / Luis ROTH IRA), Chrome via
Claude in Chrome.

---

## Verdict summary

| # | Check | Verdict |
|---|---|---|
| 1 | Radar extraction is a true no-op | **PASS** |
| 2 | Recommended Moves "ugly cutoff" fixed | **PASS on the symptom / FAIL on card chrome** |
| 3 | Portfolio click-suppression | **PASS on all three asked bullets**, plus one real edge-case bug found |
| 4 | General regression + console | **PASS** |

Two defects found, neither a blocker, both described below precisely
enough to scope a fix prompt without re-investigating.

---

## Pre-flight gate — PASSED

| Item | Result |
|---|---|
| `investment-agent-DEV` deployed commit | `af48727b` — matches, status `SUCCESS` |
| Branch | `dev` |
| Live URL (from `docs/CoWork_handoff_2026-06-13b.md`) | still correct, HTTP **200** |

Not stale. The months-old URL in the handoff doc is current.

---

## Check 1 — Radar extraction a true no-op — **PASS**

Verified two ways.

**Source:** diffed the pre-extraction inline component
(`14076fd:Radar.jsx` L1601–1652) against the extracted component plus
`RADAR_SCROLL_CHROME`. Handlers are character-identical (same 5px
threshold, same interactive-tag guard). The five style properties moved
into the prop are exactly the five that were hardcoded, and they are
disjoint from the component's two defaults, so the spread cannot clobber
anything. `suppressClickAfterDrag` defaults `false` and Radar does not
pass it, so `onClickCapture` returns immediately — Radar gains one no-op
listener and nothing else.

**Live, computed styles on both Radar section containers:**

```
background      rgb(9, 12, 18)      = #090c12      ✓
border          0px / 1px / 1px / 1px  (borderTop: none) ✓
border-radius   0px 0px 10px 10px                  ✓
padding         12px 20px 16px                     ✓
overflow-x      auto      cursor    grab           ✓
```

Byte-for-byte the pre-extraction values. Drag-panned the Portfolio
section (935px visible / 1221px content) — cursor changes to grabbing,
table pans smoothly, Actions column revealed. Card chrome is intact:
header card's rounded top joins the scroll container's rounded bottom
seamlessly, no double border, no mismatched background, no stray
artifacts.

The wrap-up's specific worry — chrome regressing because it moved to a
prop — is unfounded. This check is closed.

## Check 2 — Recommended Moves — **PASS on the symptom, FAIL on card chrome**

**The original complaint is genuinely fixed.** At 820px the grid
scrolls, drag-to-pan works (a real drag panned it to its 48px maximum),
and Accept/Decline plus the whole Decision column become reachable. No
abrupt cutoff, no overlap. Panning did not expand any row.

**But a new visual defect ships with it.** The card styling
(`background`, `border`, `borderRadius: 10`) sits on the *inner grid*
at `PortfolioManager.jsx:1809`, and that div has **no `width:max-content`
and no `minWidth`**. A block-level grid sizes to its container, so its
painted box stays at container width while its fixed-px tracks overflow
past it. `MOVE_GRID_COLS` (L409) resolves to a 792px floor.

Measured live:

| Viewport | Card box width | Content width | Content painted **outside** the card |
|---|---|---|---|
| 800px | 737px | 804px | **68px** |
| 500px | 437px | 804px | **368px** |

At 500px the card's right edge is at x=93 while content runs to x=461 —
the Amount, Tax and Decision columns render on bare page background with
no right border and no rounded corner. Visually confirmed in both cases.

Contrast Portfolio (`Portfolio.jsx:407`), which does this correctly:
`minWidth:'100%'` on a `<table>`, and tables auto-size to their content,
so the box always covers what's inside it. The grid needed the
equivalent and didn't get it.

Note: Chrome clamps its own window to a 500px minimum viewport, so the
375px phone width the prompt asked about could not be set directly. 500px
is the narrowest tested; the defect grows linearly as the viewport
narrows, so 375px would be worse, not better. The page itself does *not*
scroll horizontally at any width — overflow stays contained.

## Check 3 — Portfolio click-suppression — **PASS on all three bullets**

Tested on Eduardo Custodial (10 equity rows, 879px visible / 1181px
content).

- **Drag does not toggle rows — PASS.** Dragged across rows: `scrollLeft`
  0 → 302, row count stayed 10. No accidental expand.
- **Deliberate click still expands — PASS.** Single click on a row:
  10 → 27 rows (lot detail). Click again: back to 10.
- **Action-icon click still fires and does not toggle the row — PASS.**
  Real click on ✎ (Edit lots) on the NVDA row reached the button's
  handler (verified with a capture-phase detector that also blocked the
  real side effect), and the row did not toggle.

### Bug found: one click swallowed after a drag that ends outside the container

`DragScrollContainer.jsx` never clears `drag.current.moved` on mouse-up.
It is cleared in only two places: a fresh `onMouseDown` on a
non-interactive target, and inside `onClickCapture` itself. The
interactive-tag guard `return`s **before** the reset:

```js
const tag = e.target.tagName.toLowerCase();
if (['button','a','input','select','textarea'].includes(tag)) return;  // moved NOT reset
drag.current = { ..., moved: false };
```

**Repro:** drag-pan the positions table and let the pointer leave the
container before releasing (`onMouseLeave` → `onMouseUp`: clears
`active`, leaves `moved === true`). No click fires, so nothing clears the
flag. The **next click on a `<button>`** inside that container is
swallowed — its `mousedown` takes the early return and never resets the
flag, so `onClickCapture` eats the click. In Portfolio that means one
lost click on ✎ or ×.

Confirmed empirically, not just from source:

```
baseline click on ✎  → reached the button   (true)
after drag-ends-outside → reached the button (false)   ← swallowed
```

**Scope is narrower than it first looks.** A click on a *row* is immune,
because the row's own `mousedown` lands on a `<td>`, which takes the
normal path and resets the flag. Only `button/a/input/select/textarea`
targets are affected, and only for a single click. That's why the
end-user impact is "one action icon click occasionally does nothing,"
not a broken table.

**Fix direction (NOT applied):** clear `drag.current.moved = false` in
the interactive-tag early return, or reset it in `onMouseUp` on a
`setTimeout(...,0)` so the pending click still observes the true value.

### Correction to my previous static-only report

That report claimed both new call sites use text-glyph buttons, so the
`e.target.tagName` guard always sees the `<button>` itself. **That was
wrong** — I missed a third action button. Portfolio's row also has a
**"Rename ticker symbol"** button whose content is an `<svg>`
(confirmed in the live DOM). For that one, `e.target` is the `svg`/`path`,
which is *not* in the exclusion list, so a press on the rename icon does
initiate a drag. Minor in practice — and it makes rename the one action
button *immune* to the bug above, since its `mousedown` resets the flag.
It remains a trap for whoever swaps ✎ or × to an SVG icon later, as that
would silently change which code path they take.

Also worth recording: my earlier predicted repro (drag out, then click a
**row**) does not reproduce, for the `<td>` reason above. The prediction
was right about the stuck flag and wrong about which targets it hits.

## Check 4 — General regression + console — **PASS**

- **Normal-width table (Luis ROTH IRA, ENVX/SPWR):** renders cleanly.
  All columns and the BUCKET control present, no artifacts, no double
  borders, scrollbar contained inside the account card. Portfolio's
  container carries no chrome of its own (the card is a parent spanning
  full width), so the Check 2 defect does not apply here.
- **Console:** one message across the whole session —
  `[priceRefresh] updated=37 schwab=17 polygon=0 errors=1`. An
  application data-fetch counter, unrelated to drag-scroll. **No JS
  exceptions and no React warnings** during any drag, click, or resize.

---

## Deviations from the prompt

1. **375px could not be set** — Chrome clamps the window to a 500px
   minimum viewport. Reported 500px measurements instead and noted the
   defect scales worse, not better, below that.
2. **Used a capture-phase detector** for the action-button tests instead
   of letting handlers actually run, so the click could be proven to
   reach the button without invoking `onEdit`/`onDelete` on real data.
3. **Nothing fixed**, per the verification-only constraint.
4. Never clicked Accept, Decline, or Remove on any real move or
   position. No Force Sync, no Schwab API call triggered.

## Left for Luis

Two fix prompts are now scopeable, neither urgent:

- **Moves grid card chrome** — add `width:max-content` (or an explicit
  `minWidth`) to the grid div at `PortfolioManager.jsx:1809` so the
  background and border cover the overflowing columns.
- **Swallowed click** — reset `drag.current.moved` in the interactive-tag
  early return in `DragScrollContainer.jsx`.

Re-check the deploy gate before any future run, as it will have moved
past `af48727`:

```
railway status --json | python3 -c "import json,sys; d=json.load(sys.stdin); [print(n['node']['serviceName'], (((n['node'].get('latestDeployment') or {}).get('meta') or {}).get('commitHash') or '')[:8]) for e in d['environments']['edges'] for n in e['node']['serviceInstances']['edges']]"
curl -sI https://investment-agent-dev-production.up.railway.app | head -1
```
