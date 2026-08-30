# Fix: long Symbol values wrap across multiple lines, blowing out row height

**The fix:** the Symbol cell now uses the same truncate-with-tooltip
pattern already applied to the Name cell — `maxWidth: 130`, ellipsis,
`nowrap`, full value on hover. One file, one cell.
`client/src/pages/Portfolio.jsx` ~lines 185-207. Commit `14076fd`,
pushed to `origin/dev`.

**Verification status, stated plainly (per verify item 4):** the Chrome
extension is **still not connected** this session — `tabs_context_mcp`
returned *"Browser extension is not connected."* again. So, as with the
prior fix, **I have not seen this render.** I am not going to claim
confidence I don't have. What makes me more comfortable here than last
time is that the sizing margin is wide rather than narrow — see
"Why 130px" below.

## Premise check — confirmed, with one detail the prompt missed

The mechanism was as described. Symbol cell at lines 185-196 (the first
`<td>` after the expand chevron), symbol text rendered in a plain
`<span>` with no `whiteSpace`, no width cap — so a long value wraps
freely.

Confirmed from the live DB that the symbol really is the long string
(not a long *name* on a short symbol):

```
=== distinct symbols across all 5 accounts, longest first ===
   34  "EOS ENERGY ENTERP 26 XXX *MATURED*"  [legacy badge]
    5  "BYDDY"  [legacy badge]
    5  "GOOGL"
    4  ORCL AMPX TMFC EOSE AMZN ENVX SIVR SPWR NVDA MSFT AVGO
    3  QQQ  BTC  AMD
    2  QS

longest NORMAL ticker code: 5 chars ("BYDDY" / "GOOGL")
outliers (>10 chars): "EOS ENERGY ENTERP 26 XXX *MATURED*" = 34
```

Exactly **one** outlier across every account, and it's on Eduardo
Custodial — matching your screenshot.

**Detail the prompt didn't mention, which changed how I wrote the fix:**
the Symbol cell isn't a bare text cell. It contains an `inline-flex`
wrapper holding *two* children — the symbol text **and** a conditional
red `legacy` badge (rendered when `ticker.inScope === false`). The
`*MATURED*` row carries that badge, so it was competing for width too.

That meant I could not follow the prompt's instruction literally
("wrap the symbol text in a `display:block` inner span") by adding a new
nesting level — that would have put a block element inside the flex row.
Instead I applied the constraint **to the existing symbol span**, which
is already a flex item. Same effect, one less wrapper, and the badge
still sits beside it untouched.

**On the prompt's secondary hypothesis** — that the prior fix's Name
truncation *worsened* this by freeing space for `table-layout: auto` to
redistribute: plausible but I could not confirm it, and it doesn't
change the fix. Worth noting the row would have wrapped regardless once
that 34-char symbol existed; the prior fix at most changed how badly.

## What changed

```diff
         <td style={{ padding: '9px 12px' }}>
           <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap' }}>
-            <span style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 13 }}>{pos.ticker.symbol}</span>
+            <span
+              title={pos.ticker.symbol}
+              style={{ display: 'block', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 700, color: '#f1f5f9', fontSize: 13 }}
+            >
+              {pos.ticker.symbol}
+            </span>
             {!pos.ticker.inScope && (
```
(explanatory comment omitted here; it's in the file)

`display: 'block'` is set explicitly even though flex items are
blockified automatically — relying on that implicit behaviour is exactly
the kind of subtlety that undercut the previous fix, so I made it
explicit.

## Why 130px — and why I'm more confident in this number than the last one

At `fontSize: 13` / `fontWeight: 700`, uppercase alphanumerics average
roughly 8–9px, so 130px fits about 15 characters.

- **Must stay uncut:** longest real symbol in the data is 5 chars
  (~45px). A CUSIP like `29415C127` is 9 (~78px); an ISIN is 12
  (~104px). All well inside 130px.
- **Must truncate:** the 34-char outlier is ~290px — more than double
  the cap.

That's a wide margin on *both* sides, so the fix holds even if my
px-per-character estimate is off by 30%. Contrast the prior fix's Name
cap (`maxWidth: 200`), which had to discriminate between 32 and 40
characters — an 8-char window where estimate error genuinely matters.
**That earlier number is the one worth eyeballing when you look at the
UI** (see follow-up 3).

Note `29415C127` no longer appears in any active position — you appear
to have removed those since the earlier task. I still sized the cap to
fit CUSIP-length identifiers as the prompt asked, since they can
reappear from the broker feed.

## Verification performed

- **Symbol lengths across all 5 accounts** — live read-only DB query
  (results above); the `maxWidth` is chosen from that data, not guessed.
  Verify item 1 ✔
- **`npx vite build`** — clean, no errors. (No linter configured;
  `node --check` doesn't apply to JSX, so the build is the syntax gate.)
- **Change landed** — re-grepped: `title={pos.ticker.symbol}` at line
  194, `maxWidth: 130` at line 195.
- **Scope contained** — `git status` shows exactly one modified file.
- **All bucket tabs covered** — `PositionRow` is defined once and used
  once, inside the shared `BucketTabContent`; per verify item 5 this was
  already established by the prior fix and re-reading confirms it still
  holds. Equities / ETFs / Crypto / Commodities all get this; the Cash
  tab returns earlier and never renders this table. Verify item 5 ✔
- **Cleanup** — temporary DB script deleted; regenerated `client/dist/`
  removed.

## What I could NOT verify

**Verify items 2, 3 and 4 — not performed.** They need a rendered page,
and the Chrome extension is not connected (retried once this session,
same result; I didn't keep hammering it).

Unverified specifically:
2. That the `EOS ENERGY ENTERP 26 XXX *MATURED*` row is now a single
   line with normal height, tooltip working.
3. That short symbols (`AMZN`, `BYDDY`, `NVDA`, `GOOGL`) are visually
   untouched.
4. Anything visual at all.

The analysis above is sound as far as it goes, but it is analysis.
**Please eyeball it before calling this closed.**

## Deviations from the prompt

1. **Constrained the existing symbol span rather than adding a new inner
   span**, because the cell is a flex row shared with the `legacy`
   badge — see the premise section. Same pattern, same result, no extra
   wrapper.
2. **Could not do the visual verification** the prompt asked for
   (item 4), and said so plainly rather than papering over it — which is
   what item 4 explicitly requested if the extension was still down.

## What was deliberately NOT done

- **Did not add `flexShrink: 0` to the `legacy` badge.** With the symbol
  now capped the badge shouldn't get squeezed, and "legacy" is a single
  unbreakable word so it can't wrap internally. Left it alone to keep
  the diff surgical; mentioning it in case you ever see that badge
  compressed.
- **Did not touch the Name cell's `maxWidth: 200`** from the prior fix —
  out of scope here, but flagged below as the number most worth
  checking.
- **Did not rename or clean up the `EOS ENERGY ENTERP 26 XXX *MATURED*`
  ticker itself.** That's data cleanup and your call — though it's
  arguably the better long-term fix (see follow-up 4).
- **Did not re-derive the shared-component finding** — the prompt said
  reading the code was sufficient.

## Follow-up for Luis

1. Once `investment-agent-DEV` picks up the push, open **Eduardo
   Custodial → Equities** and confirm the `*MATURED*` row is back to a
   single-line height, showing something like `EOS ENERGY ENT…` with the
   full string on hover.
2. Confirm the short symbols on the same table (`AMZN`, `BYDDY`, `NVDA`)
   look exactly as before — they should be nowhere near the 130px cap.
3. **Also worth a look while you're there:** the *previous* fix capped
   the Name column at `maxWidth: 200`, sized to keep Andrea's 32-char
   `ABRDN PHYSICAL SILVER SHARES ETF` intact while truncating Eduardo's
   40-char BYDDY name. That's a narrow margin resting on an unverified
   px estimate. If Andrea's SIVR name is truncating when you'd rather it
   didn't, raise that 200 (line ~205 area) — tell me and I'll adjust.
4. The cleanest permanent fix for this row is the data itself: use the
   rename (✎) button to set a real symbol/short name for the `*MATURED*`
   position, or remove it once you've confirmed it's worthless — which
   you were already planning. The CSS cap just stops any future
   broker-supplied junk string from wrecking the layout.
5. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 14076fd...
   ```

## Note on the commit trailer

Unchanged from the last two tasks: the commit says `Co-Authored-By:
Claude Opus 4.8 (1M context)` because that's what your `/execute-prompt`
workflow specifies verbatim, but this session is running **Opus 5**.
Flagging for accuracy; update the workflow file if you'd prefer it track
the real model.
