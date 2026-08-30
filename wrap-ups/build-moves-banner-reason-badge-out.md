# Build: Moves tab banner, mandatory decline reason, pending-execution badge

**Commit `02c7c78`, pushed to `origin/dev`.** Four files: new
`client/src/components/CircledBangBadge.jsx`, plus
`client/src/pages/PortfolioManager.jsx`, `client/src/pages/Radar.jsx`,
`server/routes/moves.js`.

**Headline: Part 2 required no code — it was already fully built,
including the prefill.** Parts 1 and 3 are new. Details per part below.

**Chrome tools: NOT connected** (checked before starting). Per verify
item 4's instruction, the Radar refactor was validated by careful source
diff instead, and I say plainly which items went unverified at the end.

## Preconditions checked first

- **Sibling banner task** (`build-fullreset-frozen-24h-expiry.md`) has
  **not** landed — no wrap-up, no existing banner. So I built the
  mechanism, parameterized, for it to extend.
- **Sticky-column part 4** has **not** landed — no `position: 'sticky'`
  anywhere in either page. So no sticky background to fit the badge into
  yet; noted for whoever does that work.
- Neither `MovesBanner` nor `CircledBangBadge` previously existed.

---

## Part 1 — Banner — BUILT

New `MovesBanner({ mode })` in `PortfolioManager.jsx` (~line 428),
rendered above the move list (~line 1854), with the exact copy specified.

```jsx
function MovesBanner({ mode }) {
  if (mode !== 'everyday') return null;
  return ( /* card bg, blue left-rule, 12px muted text */ );
}
```

Called as:
```jsx
{displayMoves.length > 0 && (
  <MovesBanner mode={data.isFreshStart ? 'freshStart' : 'everyday'} />
)}
```

Design choices, both deliberate:
- **Returns `null` for non-everyday modes.** Today that means Full reset
  shows no banner — identical to current behaviour, so nothing regresses
  while the sibling task is outstanding. That task adds a `freshStart`
  branch here; an unhandled mode renders nothing rather than the *wrong*
  explanation.
- **Hidden when the list is empty.** A banner reading "these are today's
  recommended trades" above zero trades is noise. Gated on
  `displayMoves.length > 0`. Flagging because the prompt didn't specify.

Mode comes from `data.isFreshStart`, which the server already sets on the
payload (`moves.js:1908`) — no new plumbing.

---

## Part 2 — Mandatory decline reason — ALREADY IMPLEMENTED, no code written

The prompt asked me to *confirm whether* declining with an empty reason
is currently possible before blocking it. It is not. **Three independent
guards already exist**, all in `PortfolioManager.jsx`:

1. **Button disabled** — `disabled={submitting || !inputReason.trim()}`,
   with matching affordances (`cursor: … 'not-allowed'`, `opacity: … 0.5`).
2. **Enter key guarded** —
   `onKeyDown={e => e.key === 'Enter' && inputReason.trim() && confirmDecline()}`.
3. **Function-level guard** — `confirmDecline()` opens with
   `if (!inputReason.trim()) return;`.

`.trim()` throughout, so whitespace-only correctly does not count as
filled — exactly the requirement.

**Prefill on repeat decline is also already working**, via a path the
prompt didn't account for. `hydrateDecisions()` (~line 1493) rebuilds the
decisions map from `priorDecision`, storing
`declinedReason: m.priorDecision.reason`. Because any move with a prior
decision has `isDecided === true`, the fresh "✗ Decline" button (which
does `setInputReason('')`) is **not rendered** for it — the row shows
`✗ Declined` plus a `change` link, and that link prefills:

```js
setInputReason(decision.declinedReason ?? '');
```

Editable, not read-only. And `handleDecline` unconditionally POSTs a new
`/api/decisions` row, so every decline gets its own `decidedAt` — the
reaffirm-with-edit-option semantics the prompt specified, not a dedupe.

**I changed nothing here.** Re-implementing would have meant duplicating
working logic. Everything the prompt asked for in Part 2 already holds.

*Minor pre-existing quirk, not fixed:* `hydrateDecisions` treats any
non-`accepted` decision as declined
(`m.priorDecision.decision === 'accepted' ? … : { status: 'declined' … }`),
so a `deferred` row would render as "✗ Declined". The API accepts
`deferred` (`routes/decisions.js:26`) but this UI never sends it, so it's
currently unreachable. Noted for whoever adds a defer flow.

---

## Part 3 — Pending-execution badge — BUILT

### 3.1 Shared component extracted

New `client/src/components/CircledBangBadge.jsx` taking `color` and
`title`. `StaleTranscriptBadge` now wraps it, keeping its own thresholds
and copy (which are what the badge *means*, and are Radar-specific).

**Verified a true no-op by source diff**, since no browser:
- `diff` of the original style block against the new component's:
  **byte-identical** (all 14 properties, same values, same order).
- `git diff client/src/pages/Radar.jsx` touches only the import line and
  the `return` statement. The `daysSinceLastCall < 85` early return, the
  `isOverdue >= 100` threshold, the `color` selection and **both tooltip
  strings do not appear in the diff at all** — untouched.
- Same two props (`color`, `title`) reach a structurally identical
  `<span>`. There is no path by which rendering can differ.

### 3.2 Badge in the Decision cell

Added beside `✓ Accepted $X` (~line 573). No layout change needed — that
cell was already `display: flex, gap: 6`. Amber, so it reads as
"attention" against the green ✓ rather than as an error.

The condition is simply `decision.status === 'accepted'`, per the recon:
a rendered row always has a live diff, so an accepted move is by
definition not yet reflected in the position.

### 3.3 Historical amount — server change

`moves.js` `priorMap` (~line 1402) now also carries:

```js
snapshotAmount: d.systemSnapshot?.dollarAmount ?? null,
```

I lifted **only the amount** rather than shipping the whole
`systemSnapshot` blob — its other fields (`thesisHealth`, `trajectory`,
`ratchetTranche`, `currentPct`, `pricePerShare`) have no client consumer,
and `priorMap` is otherwise a tight, purpose-built object. One
construction site (1398-1417) feeds both attach points (1420, 1677), so
the single edit covers both code paths.

Tooltip resolution, in `MoveRow`:
```js
const acceptedFor = prior ? (prior.acceptedAmount ?? prior.snapshotAmount ?? null)
                          : (decision?.acceptedAmount ?? null);
```
`??` not `||`, so a legitimate `0` amount is preserved rather than
falling through (there is a real `acceptedAmount=0` row in the data).

Deliberately **not** using `decision.acceptedAmount` for the tooltip:
`hydrateDecisions` sets it to `acceptedAmount ?? m.dollarAmount`, i.e.
today's recomputed number — correct for the running totals
(`acceptedProceedsTotal`/`acceptedSpendTotal`, which should reflect what
you'd execute now), wrong for a statement about the past. That split is
the whole point of this sub-part. A decision made in the *current*
session has no `priorDecision` yet, but its `decision.acceptedAmount` is
the exact figure just typed, so that branch is sound too.

---

## Edge cases — decisions stated, as required

1. **Partial execution** — accept $500 of $1,000, execute exactly that,
   and the row persists, still badged. The data model genuinely cannot
   tell this from "did nothing." **Decision: keep the tooltip vague about
   whether the trade happened.** It says the move "is still listed because
   the position has not reached target yet; if you have already placed
   this trade it will drop off once a broker sync reflects it" — which is
   true in every case, and claims no precision the data doesn't support.
2. **Accepted-then-drifted-further** — **Decision: tooltip shows only the
   historical amount; today's number is not repeated there.** The row's
   own Amount column already shows the live figure, so both are visible
   without cramming two numbers into one tooltip. Tooltip = what you
   agreed to and when; row = where things stand now. Two numbers in one
   sentence would invite misreading which is which.
3. **Declined moves have the same staleness ambiguity** — a week-old
   `✗ Declined` looks like today's. Out of scope per the prompt; **not
   attempted**. Worth a future pass, and the same `decidedAt` is already
   on the payload if you want it.

---

## Verification

| # | Item | Result |
|---|---|---|
| 1 | Banner copy/placement | Source-verified; **not seen rendered** |
| 2 | Empty decline blocked | **Verified in source** — 3 guards, all `.trim()` |
| 3 | Repeat decline prefills, fresh `decidedAt` | **Verified in source** — hydrate + `change` path + unconditional POST |
| 4 | Radar badge identical | **Verified by diff** — style byte-identical, logic untouched |
| 5 | Badge shows on accepted/open move | Source-verified; **not seen rendered** |
| 6 | `snapshotAmount` present when `acceptedAmount` null | **Verified against live DB** |

**Item 6 detail** — read-only query over all 22 `OwnerDecision` rows,
applying the exact mapping `priorMap` now performs:
```
Luis Morales AMPX:ADD  decision=declined acceptedAmount=null snapshotAmount=591.44  <-- snapshot rescues it
Luis Morales EOSE:ADD  decision=declined acceptedAmount=null snapshotAmount=805.15  <-- snapshot rescues it
Luis Morales AMD:ADD   decision=accepted acceptedAmount=4785 snapshotAmount=7518    <-- real partial accept
Luis Morales AMZN:EXIT decision=accepted acceptedAmount=0    snapshotAmount=0
```
`snapshotAmount` populates in every case. The `AMD:ADD` row is a genuine
partial accept, where the tooltip will correctly cite **$4,785** (what
was agreed) rather than $7,518.

**Honest caveat on the impact of 3.3:** every *accepted* row in the
current data has a non-null `acceptedAmount`, because the accept form is
prefilled with the recommendation and always submits a number — the UI
never sends null on accept. So `snapshotAmount` is correctness insurance
for a contract the API permits (`decisions.js` allows null) rather than a
fix for a misreport you'd see today. Still right to add — the tooltip
should never guess — but I'd rather say so than overstate it.

Also: `node --check server/routes/moves.js` passes; `npx vite build`
clean at 112 modules (was 111, new component bundled); temp script and
`client/dist/` removed; exactly the four intended files staged.

## What was NOT verified

No browser, so **items 1 and 5 were not seen rendered** — the banner's
appearance, and the badge sitting correctly beside `✓ Accepted $X` with a
working tooltip. Items 2 and 3 are source-verified rather than clicked
through, though the logic there is unambiguous and pre-existing.

## What was deliberately NOT done

- **No changes for Part 2** — already complete; re-implementing would
  have duplicated working code.
- **Did not change `hydrateDecisions`' `?? m.dollarAmount` fallback** —
  it is correct for the running totals that consume it. The historical
  value is used only where history is being stated.
- **Did not add a Full-reset banner branch** — that's the sibling task's.
- **Did not touch declined-move staleness** (edge case 3).
- **Did not ship the whole `systemSnapshot`** to the client.

## Follow-up for Luis

1. **Visual check needed on two things:** the banner above Action
   Required in everyday mode, and the amber `!` beside a `✓ Accepted $X`
   row (hover it — expect e.g. *"Accepted on 8/21/2026 at $4,785 — still
   pending execution…"*).
2. **Regression check on Radar:** the stale-transcript `!` badge should
   look and behave exactly as before. The diff says it must, but it's the
   one thing this task refactored under someone else's feature.
3. **Confirm no suppression crept in** (verify item 5's second half): a
   move whose diff clears should still vanish entirely. Nothing in this
   change touches generation or filtering, so it should — worth an eye
   anyway.
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 02c7c78...
   ```
5. When the Full-reset banner task runs, it should add a `freshStart`
   branch inside `MovesBanner` — the wiring (`data.isFreshStart`) is
   already in place.

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.
