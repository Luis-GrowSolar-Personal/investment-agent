# Fix: long Symbol values wrap across multiple lines, blowing out row height

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-position-symbol-cell-wrapping-out.md`. Small, low-risk
fix — implement directly. Write for someone reading cold later.

## Context

Follow-up regression from `fix-position-table-actions-cut-off`
(commit `b3a49f9`). Luis confirmed via screenshot: on Eduardo Custodial,
the position with `Ticker.symbol = "EOS ENERGY ENTERP 26 XXX *MATURED*"`
(a long descriptive string used as the symbol, not a short ticker code —
same category as the `29415C127` CUSIP-style placeholder) now renders
its Symbol cell wrapped across ~5 lines, massively inflating that row's
height. This looks worse than before the prior fix, not better.

**Likely mechanism (confirm, don't just assume):** the prior fix
truncated the Name column (`PositionRow`, ~line 197-208) with a fixed
`maxWidth: 200` + ellipsis, but did nothing to the Symbol cell
(~line 185-196, the first `<td>` after the expand chevron). That cell
has no `whiteSpace: nowrap` and no width constraint, so a long symbol
string wraps freely. Freeing up horizontal space in the Name column may
also have caused `table-layout: auto` to redistribute more of the
squeeze onto the Symbol column than existed before, making this
specific row's wrapping worse post-fix, not just equally bad.

## The fix

Apply the same truncate-with-tooltip pattern already used for the Name
cell to the Symbol cell: wrap the symbol text in a `display:block`
inner span with `whiteSpace: nowrap`, `overflow: hidden`,
`textOverflow: ellipsis`, a `title` attribute with the full symbol, and
an appropriate `maxWidth` (the symbol cell is narrower than the Name
cell in normal use — pick a value that doesn't truncate short real
ticker symbols like `AMZN`, `BYDDY`, `29415C127`, only unusually long
ones like this "MATURED" placeholder; check actual symbol lengths
across all 5 accounts' live data the same way the prior fix did, don't
guess).

Read the current file before editing — confirm exact line numbers,
since the prior two fixes both touched this file recently.

## Verify

1. Query live DB for `Ticker.symbol` length across all positions in all
   5 accounts (same style check the prior fix did for names) — confirm
   which symbols are long outliers vs. normal short ticker codes, to
   pick a sane `maxWidth`.
2. Confirm this specific row (`EOS ENERGY ENTERP 26 XXX *MATURED*`,
   Eduardo Custodial) no longer wraps to multiple lines — single-line
   row height restored, full text available via hover tooltip.
3. Confirm normal short symbols (`AMZN`, `BYDDY`, `NVDA`, etc.) are
   completely unaffected — no truncation, no visual change.
4. If Chrome browser tools are available this session, actually verify
   visually rather than by analysis alone — the prior fix's wrap-up was
   explicit that it could NOT do this due to the extension being
   disconnected; if it's still disconnected, say so plainly again rather
   than re-asserting confidence you don't have.
5. Confirm this applies to all bucket tabs (same shared component,
   per the prior fix's already-established finding) — reading the code
   is sufficient here, no need to re-derive.

## Commit and push

```bash
git add -A
git commit -m "Truncate long Symbol values instead of wrapping across multiple lines"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-position-symbol-cell-wrapping-out.md` existing.
