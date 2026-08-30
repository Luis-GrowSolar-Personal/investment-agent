# Fix: long ticker names push Rename/Edit/Remove icons off-screen

**Two changes, both in `client/src/pages/Portfolio.jsx`** (commit
`b3a49f9`, pushed to `origin/dev`):

1. The requested one: the positions table's `width: '100%'` → `minWidth:
   '100%'`, so it can exceed its container and let the existing
   `overflowX: 'auto'` wrapper produce a real horizontal scrollbar.
2. The prompt's "secondary, optional" item: the Name column is now
   capped with an ellipsis + full-name-on-hover tooltip.

**Read this before trusting it:** I could **not** perform the visual
verification steps this prompt asks for (items 1–3) — the Chrome
extension isn't connected in this session. And on close analysis, I do
not think change #1 alone reliably fixes the reported symptom. That's
why I also implemented #2, which removes the *cause* rather than
mitigating the effect. Reasoning and what you still need to confirm are
below.

## Premise check

The prompt's traced root cause matched the file exactly — `overflowX:
'auto'` on line 377, `width: '100%'` on line 378, actions cell at
~223-241. No drift despite recent commits to this file.

The data premise also holds. Longest *displayed* name (`shortName ||
name`) per account, from the live DB:

```
Eduardo Custodial (id=6)  — 15 positions | longest: 40 chars  "BYD CO LTD FUNSPONSORED ADR 1 ADR REPS 1" [BYDDY]
                                            next: EOSE=34, SIVR=32, TMFC=19
Andrea Custodial  (id=7)  — 13 positions | longest: 32 chars  "ABRDN PHYSICAL SILVER SHARES ETF" [SIVR]
Luis ROTH IRA     (id=10) —  2 positions | longest:  8 chars  "SunPower"
Andrea ROTH IRA   (id=11) —  4 positions | longest: 12 chars  "QuantumScape"
Eduardo ROTH IRA  (id=12) —  5 positions | longest: 11 chars  "Bitcoin ETF"
```

Eduardo Custodial is indeed the outlier — the only account with a name
past ~32 chars, and it has *two* long ones (40 and 34). That matches
"Eduardo breaks, Andrea doesn't."

**Verify item 4 (does this apply to all bucket tabs?) — answered by
reading code, as instructed.** `BucketTabContent` is a single component
rendered once for whichever tab is active (`BUCKET_TABS = ['equity',
'etf', 'crypto', 'commodity', 'cash']`), and `PositionRow` is defined
once and used once, inside it. So both fixes apply uniformly to
Equities, ETFs, Crypto and Commodities. The `cash` tab returns its own
UI earlier in the component and never reaches this table, so it's
unaffected.

## Why I didn't stop at the requested one-liner

Working through the CSS carefully, the `width: '100%'` → `minWidth:
'100%'` change is directionally right but probably **not sufficient** on
its own:

- Under `table-layout: auto`, CSS 2.1 §17.5.2.2 says the table's used
  width is `max(specified width, minimum content width)`. So `width:
  100%` does *not* actually forbid overflow — a table already grows past
  100% when its columns' **minimum** widths demand it.
- But the Name cell had no `nowrap`, so its text could wrap, making its
  *minimum* content width the longest single **word** — for BYDDY that's
  `FUNSPONSORED`, only 12 characters (~70px). Nowhere near enough to
  push the table's total minimum past the container.
- So the table almost certainly stayed exactly at container width, the
  scroll container never engaged, and the columns were instead
  distributed between their min and preferred widths — with the 40-char
  Name column claiming a large preferred share and squeezing the
  `nowrap` actions cell until its icons rendered past the visible edge
  with no scrollbar available to reach them. That matches your
  screenshot precisely.
- Swapping to `minWidth: 100%` leaves `width: auto`, and an auto-width
  table in a constrained container still shrink-to-fits to the available
  width. So the same squeeze can recur; the change mainly helps once
  something *else* raises the table's minimum width.

Hence change #2, which attacks the actual cause: cap the Name column so
it can't claim that space in the first place. I kept change #1 anyway —
it's harmless, it's what you asked for, and it's the correct safety net
for any future row whose content genuinely can't fit.

I want to be straight that this reasoning is analytical, not measured —
see the verification gap below.

## What changed

**Table (was line 378, now ~392):**
```diff
     <div style={{ overflowX: 'auto' }}>
-      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
+      {/* minWidth (not width) so the table can exceed the container when a row's
+          content genuinely demands it — the overflowX:'auto' wrapper above then
+          gives a real horizontal scrollbar instead of the last column being
+          squeezed/clipped out of reach. Normal-width tables still fill 100%. */}
+      <table style={{ minWidth: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
```

**Name cell (was ~line 197-199, now ~197-208):**
```diff
         <td style={{ padding: '9px 12px', color: '#94a3b8', fontSize: 12 }}>
-          {pos.ticker.shortName || pos.ticker.name}
+          <span
+            title={pos.ticker.shortName || pos.ticker.name}
+            style={{ display: 'block', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
+          >
+            {pos.ticker.shortName || pos.ticker.name}
+          </span>
         </td>
```
(comment omitted here for brevity; it's in the file)

Two deliberate details:
- **The cap is on an inner `<span>`, not the `<td>`.** `max-width` on a
  table cell is widely ignored under `table-layout: auto`; putting it on
  a `display:block` child is the pattern that actually works.
- **`maxWidth: 200`** at this cell's `fontSize: 12` is roughly 34
  characters. That's chosen to sit between Andrea's longest (32 chars —
  should still render in full, unchanged) and Eduardo's (40 and 34 —
  these truncate). So the visible change should be confined to the rows
  actually causing the problem. **This is an estimate from average
  character width, not a measurement** — if it truncates more than you
  want, raise the 200.

## Verification performed

- **Data premise** — confirmed against the live DB (table above),
  read-only.
- **All bucket tabs covered** — confirmed by reading the component
  structure, per verify item 4.
- **`npx vite build`** — builds clean, no errors (the project has no
  linter configured; `node --check` doesn't apply to JSX, so the real
  build is the syntax gate).
- **Change landed** — re-grepped: `minWidth: '100%'` at line 392,
  `textOverflow: 'ellipsis'` at line 205.
- **Scope contained** — `git status` shows exactly one modified file.
  Other `width: '100%'` tables in this file (the Edit-lots and
  rename modals, ~lines 742/872 pre-edit) were deliberately left alone.
- **Cleanup** — temporary DB script deleted; regenerated `client/dist/`
  build output removed.

## The verification gap — what I could NOT do

**Verify items 1, 2 and 3 were not performed.** They require rendering
the app in a browser, and `tabs_context_mcp` returned *"Browser
extension is not connected."* Per the session guidance I didn't retry
repeatedly or go hunting for workarounds.

Specifically unverified:
1. **Reproduction** — I did not confirm first-hand that the icons are
   genuinely unreachable (vs. merely cramped) on Eduardo Custodial. I'm
   relying on your screenshot.
2. **The fix works** — I have not seen the actions column become
   reachable on Eduardo Custodial.
3. **No regression** — I have not confirmed Andrea Custodial / Luis ROTH
   IRA look unchanged, or that no unwanted scrollbar appeared.

I built an isolated HTML harness to measure `scrollWidth` vs
`clientWidth` and the actions cell's clipping under both variants using
each account's real names — it's at
`<scratchpad>/table-test.html` if you want to open it in a browser
yourself. It never ran, for the reason above.

**So: please confirm in the UI before considering this closed.** If the
icons are still unreachable on Eduardo Custodial after this deploys,
the next lever is a pixel floor on the table (e.g. `minWidth: 900`)
which would force the scroll container to engage unconditionally — say
the word and I'll do that.

## What was deliberately NOT done

- **Did not remove the `29415C127` or `EOS ENERGY ENTERP 26 XXX
  *MATURED*` positions** on Eduardo's account — explicitly your call per
  verify item 5, pending your worthless/non-taxable confirmation.
- **Did not add a pixel `minWidth`** to the table. It would make the fix
  deterministic, but it forces a horizontal scrollbar on every account
  including the narrow ones — a visible regression for Luis ROTH IRA
  (2 short rows). Held back pending your confirmation that the current,
  lighter-touch fix is insufficient.
- **Did not touch the other tables** in this file (modals) — out of
  scope and not implicated.
- **Did not implement drag-to-pan** — the prompt correctly notes native
  scrolling suffices.

## Follow-up for Luis

1. Once `investment-agent-DEV` picks up this push, open **Eduardo
   Custodial → Equities** and confirm all three icons (rename ✎, edit,
   remove ×) are visible and clickable — either directly, or after a
   trackpad swipe / horizontal scroll.
2. Then check **Andrea Custodial** and **Luis ROTH IRA** look unchanged,
   and spot-check one other tab (ETFs or Commodities) — they share the
   same component, so they should behave identically.
3. Check whether the truncated names read acceptably. `BYDDY` will now
   show something like `BYD CO LTD FUNSPONSORED ADR…` with the full text
   on hover. Raise `maxWidth: 200` (line ~205) if you'd prefer more
   text visible.
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect b3a49f9...
   ```
5. Separately, `BYDDY`'s and `EOSE`'s names come from the broker feed
   verbatim. The rename (✎) button lets you set a clean `shortName`
   (e.g. "BYD Co") — which would sidestep the width problem at the
   source for those two rows, independent of this CSS fix.

## Note on the commit trailer

Same as the previous task: the commit uses `Co-Authored-By: Claude Opus
4.8 (1M context)` because that's what your `/execute-prompt` workflow
specifies verbatim, but this session is running **Opus 5**. Flagging for
accuracy; update the workflow file if you'd rather the trailer track the
actual model.
