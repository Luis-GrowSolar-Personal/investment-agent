# Fix: mobile nav tabs unreachable — right-hand clutter squeezes the tab strip

## Report your findings

Write a wrap-up to `./wrap-ups/fix-mobile-nav-tabs-unreachable-out.md`.

## Context

`NavBar.jsx` has five tabs (Portfolio Manager, At a Glance, Accounts,
Investment Ideas, Admin) in a flex tab strip (`className="navbar-tabs"`,
~line 128, `flex: 1, minWidth: 0`), alongside a right-hand group
(~line 149, `flexShrink: 0`) holding the Schwab sync status text, the
full user email, and a Sign Out button — none of which shrink or hide on
narrow viewports.

A prior fix (commit `5011d49`, "Fix mobile nav: tab strip wasn't
scrollable") made `.navbar-tabs` horizontally scrollable
(`overflow-x: auto`, `-webkit-overflow-scrolling: touch`) with the
scrollbar hidden (`scrollbar-width: none`, `index.css` ~lines 10-21).
**That fix was never verified on an actual mobile device or touch
emulation** — no wrap-up exists for it, unlike other UI fixes this
project (compare to the table drag-scroll work, which got an explicit
Chrome-verification pass).

**Confirmed live on a real phone by Luis 2026-08-25:** the right-hand
group consumes most of the width on a narrow screen, squeezing
`.navbar-tabs` down to showing roughly one tab ("Portfolio Manager").
The strip is technically still scrollable, but with the scrollbar
hidden there's no visual hint more tabs exist, and in that cramped a
space, taps register as micro-scrolls instead of clicks. **This is worse
than the original bug** ("visible but unreachable off-screen") — the
original bug at least showed multiple tabs; this one shows barely one
and makes even scrolling-then-tapping unreliable.

## What to build

1. On narrow viewports, reduce or hide the right-hand group's footprint
   so the tab strip actually gets usable width. Reasonable options,
   pick what fits the existing visual style — don't over-engineer:
   - Hide or truncate the full email (e.g. just the Schwab sync icon/
     status, drop the email text) below some breakpoint.
   - Consider whether Sign Out needs to stay inline at all widths, or
     could move somewhere less space-hungry on mobile (e.g. behind a
     small menu) — your call, but the tab strip must win the width
     fight on a phone-sized screen.
2. Add a visible affordance that more tabs exist and are reachable by
   scrolling — a subtle edge fade/gradient on the tab strip is a common,
   low-effort pattern; anything that makes "there's more here, swipe" a
   visible fact rather than a hidden behavior is acceptable.
3. Confirm tap targets inside the scrollable strip are large enough and
   that a simple tap (no drag) reliably activates a `NavLink` rather
   than being swallowed as a scroll gesture — this is the core of what's
   broken, not just cosmetic.
4. Do not remove the horizontal scroll — with 5 tabs there may still not
   be room for all of them fully expanded on the narrowest phones, so
   scrolling should remain available, just discoverable and reliable
   alongside the extra width freed up in step 1.

## What NOT to do

- Do not touch `DragScrollContainer` or any table-related scroll
  component — this is a separate, simpler nav element, not a shared
  component, and no table scroll behavior should change.
- Do not redesign the desktop nav — this is scoped to narrow/mobile
  viewports via a breakpoint; desktop layout (where all 5 tabs already
  fit) should be visually unchanged.
- Do not silently drop the Schwab sync status or Sign Out entirely on
  mobile — reduce/relocate them, don't remove functionality.

## Verify — this is the part that was skipped last time, do not skip it again

1. **Test at a real narrow width, not just by reading the CSS.** Use
   Chrome device emulation (or equivalent) at a common phone width
   (e.g. 375-414px) — confirm all 5 tabs are visible-or-reachable and
   that a **tap** (not a drag) on a non-active tab actually navigates.
2. Confirm the scroll affordance from item 2 is visually present at
   that width.
3. Confirm desktop width (e.g. 1200px+) is visually unchanged from
   before this fix — compare a screenshot or DOM/style snapshot if
   Chrome tools are connected.
4. If Chrome tools are not connected this session, say so explicitly and
   note that Luis should verify on his actual phone before this is
   considered closed — do not mark this fix confirmed-working based on
   source-reading alone, since that's exactly what went wrong last time.

## Commit and push

```bash
git add -A
git commit -m "Fix mobile nav: right-hand clutter was squeezing tab strip to ~1 visible tab"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-mobile-nav-tabs-unreachable-out.md` existing, with an
explicit statement of whether this was verified live on a narrow
viewport/touch emulation or not.
