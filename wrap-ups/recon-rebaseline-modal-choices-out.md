# Recon: does RebaselineModal distinguish "plain re-baseline" from "full reset"?

**Task type:** recon only. Nothing modified, nothing committed, no
rebaseline or reset executed.
**Date:** 2026-08-23
**Component:** `RebaselineModal`, `client/src/pages/PortfolioManager.jsx:1145–1441`
**Route:** `POST /api/moves/:owner/rebaseline`, `server/routes/moves.js:1988`
**Method:** source read + rendered modal inspected live on
`investment-agent-dev-production` (Andrea Morales) without submitting.

---

## Bottom line

**The UI does offer two distinct, clearly-labeled choices.** The prompt's
suspicion — that the frontend might collapse them into one flow while the
backend silently picks a mode — is **not** what's happening. There is an
explicit two-button mode selector, Full reset carries a red warning plus a
mandatory acknowledgement checkbox, and the confirm button relabels itself.

**But the prompt's underlying concern is right, just displaced.** The
*choice* is explicit; the *resulting state* is invisible and inconsistently
preserved. Three findings matter for the sticky-mode discussion:

1. Full Reset **is already de facto sticky** — via
   `MovesCache.payload.isFreshStart`, not via any user-visible setting.
2. That stickiness is **preserved by one refresh path and silently dropped
   by another** (see Q4). This looks like a genuine bug.
3. Nothing anywhere tells the user which mode the current Moves list came
   from. `isFreshStart` never reaches the client.

---

## Q1 — What choices is the user presented with?

**Two mutually-exclusive buttons in a segmented toggle**, rendered at
`PortfolioManager.jsx:1330–1347`:

```jsx
{[
  ['rebalance',  'Rebalance existing'],
  ['freshStart', 'Full reset — sell all, rebuild from best ideas'],
].map(([key, label]) => (
  <button key={key} onClick={() => setMode(key)} …>{label}</button>
))}
```

Backed by `const [mode, setMode] = useState('rebalance')` (line 1155).
Default is **Rebalance existing** — confirmed visually, it renders
selected/blue on open.

Deliberately non-sticky per the comment at lines 1150–1155: *"Deliberately
NOT persisted/sticky across modal opens given how consequential freshStart
is — always defaults back to 'rebalance'."* The component remounts on each
open (`{rebaselineOpen && <RebaselineModal …>}`, line 1744), so the
`useState` default achieves this.

Plain re-baseline is therefore fully reachable from the UI — it is in fact
the default.

## Q2 — What does each control actually send?

Single call site, `handleConfirm` at line 1232:

```js
const fresh = await loadPreview(true, mode === 'freshStart'); // persist
```

`loadPreview(persist, freshStart)` (line 1167) POSTs
`{ persist, freshStart }` to `/api/moves/:owner/rebaseline`. So:

| UI selection | Request body | Server call |
|---|---|---|
| Rebalance existing | `{persist:true, freshStart:false}` | `computeMovesPayload(owner, {bypassWinnerProtection:true, freshStart:false})` |
| Full reset | `{persist:true, freshStart:true}` | `…{bypassWinnerProtection:true, freshStart:true}` |

Server side (`moves.js:1995–1996`) reads `req.body?.freshStart === true`
and passes it straight through. The mapping is correct and unambiguous.

**Side finding — the preview does not reflect the selected mode.**
`loadPreview()` is called in exactly two places: once on mount with
defaults (`persist=false, freshStart=false`, line 1186) and once in
`handleConfirm`. Switching to Full reset does **not** recompute. The
"Current vs. target" table therefore always shows the *plain re-baseline*
projection, even with Full reset selected.

Confirmed empirically: the deltas were byte-identical in both modes
(−$476 / −$485 / — / −$728 / +$116 / +$1,543). Given Full reset uses a
different candidate pool and sells everything not re-selected, the numbers a
user reviews before confirming a Full reset are not the numbers they'll get.

## Q3 — Is the copy clear about consequences?

**Full reset: yes, clearly.** Red warning box (lines 1350–1360):

> This will generate a SELL for every currently held equity position not
> selected in the fresh build, and rebuild your equity holdings from your
> highest-conviction watchlist names. All gains and losses on sold positions
> will be realized. ETF, Crypto, Commodities, and Cash are unaffected.

Plus a required checkbox (lines 1413–1421) — *"This will likely trigger a
full sell of many existing positions"* — gating the confirm button
(`confirmDisabled = … || (mode === 'freshStart' && !ackFreshStart)`,
line 1425), and the button relabels to **"Confirm & generate full reset"**.
Verified live: unchecked ⇒ button greyed and disabled.

**Rebalance: no explanatory copy at all.** Beyond the button label, nothing
states what it does or how it differs. There is no counterpart to the red
box — no "closes the gap without liquidating existing positions."

**The modal header actively works against the distinction** (lines 1315–1318),
shown above the selector in *both* modes:

> Re-baseline — {owner}
> **Full reset to your target allocation**, including trims on positions that
> would otherwise be protected while their thesis strengthens.

So a user in Rebalance mode reads "Full reset" in the subtitle while the
"Full reset" button sits unselected beside it. "Full reset" is being used for
two different things — the whole feature, and one of its two modes.

## Q4 — Is the chosen mode indicated afterward?

**No. Nothing, anywhere.**

`onApplied` (lines 1749–1756) closes the modal and calls `loadMoves()`.
No banner, no badge, no state change.

The flag *does* exist server-side. `computeMovesPayload` stamps the payload
(`moves.js:1907–1908`):

```js
isRebaseline: bypassWinnerProtection,
isFreshStart: freshStart,
```

But `grep -rn "isFreshStart\|isRebaseline" client/src/` returns **nothing**.
It is persisted and read back by the server, never surfaced.

### The stickiness inconsistency — likely a bug

`isFreshStart` in the cached payload is what makes Full Reset persist across
recomputes. Two code paths do this, and they disagree:

| Path | Preserves `isRebaseline` | Preserves `isFreshStart` |
|---|---|---|
| `POST /:owner/refresh` — `moves.js:1959–1962` | yes | **yes** |
| `lib/movesCache.js` `refreshMovesCache()` — lines 37–38 | yes | **no** |

```js
// lib/movesCache.js:37-38
const bypassWinnerProtection = existing?.payload?.isRebaseline === true;
const payload = await computeMovesPayload(owner, { bypassWinnerProtection });
//                                                 ^ no freshStart
```

`refreshMovesCache` is called from `routes/users.js:302` (after a
moves-affecting profile PATCH) and `routes/schwab.js:203` (after a Schwab
account sync); `refreshAllMovesCache` from `routes/schwab.js:357`. **Any of
those silently downgrades a Full-Reset account back to plain re-baseline**,
with no user-visible signal — the same class of bug the file's own header
comment documents fixing for `isRebaseline` on 2026-08-08, just not extended
to `isFreshStart` when that flag was added.

The confirm flow itself is protected: the modal sends `skipMovesRefresh:true`
on its PATCH (lines 1221–1226) precisely to stop `users.js:302` clobbering the
result. That guard covers the confirm, not the next Schwab sync.

Not fixing it — recon only — but it is directly load-bearing for the sticky-mode
question, because "is Full Reset sticky today?" currently answers *"yes, unless
a sync happens to fire."*

## Q5 — Can a user get back to plain re-baseline from the UI?

**Yes, mechanically.** Reopen the modal (remounts, `mode` defaults to
`'rebalance'`), confirm, and it POSTs `freshStart:false` and persists a payload
with `isFreshStart:false`. There is no one-way door and no backend-only mode.

**But it is not discoverable, because nothing says the account is in Full
Reset.** No indicator (Q4), and the mode selector always opens on Rebalance
regardless of what was last applied — so the control that would reveal current
state deliberately shows the default instead. A user has no way to know they're
in Full Reset, and therefore no reason to know they should re-run in Rebalance
to leave it.

So "go back to normal" is *reachable* but not *findable* — and, per Q4, a
Schwab sync may perform that exit on its own without anyone asking.

---

## Summary answer to the prompt's closing question

The current UI offers **two genuinely distinct, well-labeled choices**, with
the more dangerous one properly gated behind a warning, a checkbox, and a
distinct confirm label. It does *not* functionally offer only Full Reset, and
plain re-baseline is the default rather than the hidden option.

What's missing is everything *after* the choice: no persistent indication of
which mode produced the current Moves list, one refresh path that silently
discards Full Reset mode, and a preview table that shows plain-rebaseline
numbers even when Full reset is selected.

Framed for the sticky-mode discussion: **Full Reset is already a sticky mode
today — it just isn't an acknowledged one.** The state exists
(`payload.isFreshStart`), persists across recomputes, is invisible to the user,
and leaks away on some events. The design question is less "should it become
sticky" than "should the stickiness it already has be made explicit, reliable,
and exitable."

## Deviations from the prompt

- **Premise corrected.** The prompt framed the open question as whether the UI
  collapses the two modes into one flow. It does not. Reported what is actually
  ambiguous instead — post-choice state, not the choice itself.
- **Scope widened slightly, deliberately.** Q4/Q5 could not be answered
  truthfully without tracing where `isFreshStart` is persisted and re-read, which
  led into `lib/movesCache.js` and the refresh routes. That is where the
  `refreshMovesCache` inconsistency surfaced. Reported, not fixed.
- **Live inspection stayed read-only.** Opening the modal fires
  `loadPreview()` with `persist:false`; the route only writes to MovesCache when
  `persist === true` (`moves.js:2005`), so nothing was mutated. I selected Full
  reset to read its copy, left the acknowledgement unchecked, and hit Cancel.
  The Moves count was 10 before and after.

## Deliberately NOT done

No changes to `RebaselineModal`, the rebaseline route, `lib/movesCache.js`, or
any copy. No rebaseline or full reset executed against live account data. No
build or design decisions made — this is fact-finding for
`memory/freshstart_mode_sticky_ux_question.md`.

## Suggested follow-ups (for Luis to scope, not started)

1. **Bug:** extend `lib/movesCache.js:37–38` to preserve `isFreshStart` the way
   `moves.js:1959–1962` already does. Smallest, highest-confidence item here.
2. **Preview fidelity:** recompute the preview when `mode` changes, so the
   comparison table matches what confirming will actually do.
3. **State visibility:** surface `payload.isFreshStart` in the Moves tab —
   prerequisite for any sticky-mode UX.
4. **Copy:** the header subtitle says "Full reset" in both modes; consider
   reserving that phrase for the mode.

Verify the two refresh paths still diverge:

```
grep -n "isFreshStart\|isRebaseline" server/lib/movesCache.js server/routes/moves.js
```
