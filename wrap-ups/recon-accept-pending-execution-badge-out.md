# Recon: what happens today to an accepted-but-unexecuted move?

**Verdict: PARTIAL — and substantially more already works than the
prompt assumed.** The prompt's central suspicion — that `priorDecision`
is "attached to the payload but never surfaced visually" — is **wrong**.
It is surfaced in three distinct ways. The live-recompute half of the
design is fully working with no new code needed. What's genuinely
missing is narrow: a visual distinction between "accepted" and "accepted
but the trade hasn't happened yet," plus one small server-side data gap
if the tooltip needs a historically accurate dollar figure.

Recon only — **nothing was implemented, nothing committed.**

---

## Q1 — What `priorDecision` actually does on the frontend

It is consumed in three places, not zero:

**a. Rehydrates decision state** (`PortfolioManager.jsx:1487-1500`).
Rebuilds the `decisions` map from each move's `priorDecision`, so
accept/decline survives a reload:
```js
next[key] = m.priorDecision.decision === 'accepted'
  ? { status: 'accepted', acceptedAmount: m.priorDecision.acceptedAmount ?? m.dollarAmount }
  : { status: 'declined', declinedReason: m.priorDecision.reason };
```

**b. Collapsed row — the Decision cell already shows an accepted state**
(`:527-541`). This is the important one the prompt didn't account for:
```jsx
{decision.status === 'accepted' ? (
  <span style={{ color: C.green, fontWeight: 700, fontSize: 11 }}>✓ Accepted {money(decision.acceptedAmount)}</span>
) : (
  <span style={{ color: C.muted, fontWeight: 700, fontSize: 11 }}>✗ Declined</span>
)}
<button …>change</button>
```
So an already-accepted move renders `✓ Accepted $2,000` in green, with a
`change` link, instead of the Accept/Decline buttons.

**c. Expanded detail — a "LAST DECISION" line** (`:586-596`): decision,
optional reason, and `timeAgo(decidedAt)`. **But this is gated behind
`{showDetail && (…)}` at `:561`**, so it is only visible after clicking
the row open. In the collapsed view — the one you actually scan — the
decision date is not shown anywhere.

---

## Q2 — Does the "diff naturally clears" case need new code? **No. Confirmed.**

Move generation is completely independent of decision history:

- `generateMovesForTicker` (`moves.js:530-534`) takes
  `ticker, positions, totalPortfolioValue, latestAnalysis, modelWeightPct, profile, ownerTaxRates, bypassWinnerProtection`
  — **no decision data is passed in at all.**
- Decisions are attached *after* generation, onto already-built moves
  (`moves.js:1409-1412`): `for (const m of allMoves) { … if (prior) m.priorDecision = prior; }`
- The existing comment states the intent outright (`:1387-1392`): *"the
  move itself still regenerates live from current portfolio state (it's a
  diff, not a suppressible event)."*
- On the frontend, `displayMoves` (`:1669-1671`) filters **only** by
  selected bucket — never by decision status.

So if a ticker drifts back under target, no move is generated, and the
row disappears regardless of any `OwnerDecision` history. **This half of
the design already works end-to-end.**

The corollary matters for Q3: because generation is live, **a move that
is still on screen is by definition one whose diff still exists.**

---

## Q3 — What's actually missing, and what a fix would need

### The real gap: the app has no concept of execution

Repo-wide grep for `executedAt` / `executed` / `pendingExecution` across
the schema, `moves.js`, and `PortfolioManager.jsx` returns **nothing**.
`OwnerDecision` records the *decision*, never the *trade*. So in the data
model, "accepted" and "accepted but not yet executed" are the same state.

### But the condition needs no new data

Combining that with Q2: a rendered move always has a live diff. Therefore

> `decision.status === 'accepted'` on a row that is still being rendered
> **already means** "accepted, and the position still isn't where you
> said you'd put it."

That is precisely the "pending execution" condition. **No new field, no
new query, no execution tracking is required to drive the badge** — which
makes this a much smaller change than it might first appear.

### Why the badge is still worth adding

Today that state renders as a green `✓ Accepted $2,000`. A green
checkmark reads as *done* — settled, complete. In reality it may mean
"you said yes three days ago and never placed the order." The badge's
job is to correct that false impression. That's the actual design value,
and it's worth stating plainly in the fix prompt.

### Where it slots in

The Decision cell at `:508` is the natural home:
```jsx
<div style={{ ...cellBase, display: 'flex', alignItems: 'center', gap: 6 }} onClick={e => e.stopPropagation()}>
```
Already a flex row with `gap: 6`, already containing the `✓ Accepted $X`
span and the `change` button — dropping a 14×14 inline-flex badge in
beside them needs no layout change.

One caveat: the Decision column is the same one the outstanding sticky-
column work (`fix-position-table-sticky-actions-column-out.md`, part 4,
still unshipped) would pin. Doing both means the badge must sit inside
whatever background treatment the sticky cell ends up with.

### Shared component: extract, per the prompt's own criterion

There is currently exactly **one** circled-bang instance:
`StaleTranscriptBadge` (`Radar.jsx:162-192`) — 14×14, `borderRadius:'50%'`,
`1.5px solid ${color}`, `fontSize:9`, `fontWeight:800`, `cursor:'help'`,
`flexShrink:0`, tooltip via `title`. Its logic is Radar-specific (the
`daysSinceLastCall < 85` early return and its two tooltip strings), but
the *visual* is fully generic.

Adding a second use makes extraction justified. Recommend
`client/src/components/CircledBangBadge.jsx` taking `color` and `title`,
with `StaleTranscriptBadge` refactored to wrap it. `components/` already
exists and holds `NavBar.jsx` and `DragScrollContainer.jsx`.

*Unrelated but noted while looking:* a separate `Badge` (pill-style
label/color) is duplicated four times — `Radar.jsx:58`,
`DecisionAnalytics.jsx:81`, `PortfolioManager.jsx:93`,
`AdvisoryFeed.jsx:52`. Pre-existing, out of scope here, but the same
`components/` extraction would tidy it.

---

## Q4 — Tooltip data: mostly available, with one real gap

`OwnerDecision` (`schema.prisma:312-323`) stores:
- `decidedAt DateTime @default(now())` ✔
- `acceptedAmount Float?` ✔ — **nullable**, and the schema comment says
  `null = full recommendation`
- `systemSnapshot Json` — *"snapshot at decision time: thesisHealth,
  trajectory, ratchetTranche, currentPct, dollarAmount"*

Both `decidedAt` and `acceptedAmount` are already included in the
payload the client receives (`moves.js:1403-1407`).

**The gap.** For a tooltip reading *"Accepted on [date] at $[X], still
pending execution"*, `$[X]` is wrong whenever the user accepted the full
recommendation. `acceptedAmount` is `null` in that case, and the existing
frontend fallback is `m.priorDecision.acceptedAmount ?? m.dollarAmount`
(`:1499`) — which falls back to the **freshly recomputed** amount, not
the amount at the time of the decision. A tooltip built on that would
present today's number as if it were the historical one, which is exactly
the kind of quiet inaccuracy this feature exists to prevent.

The historically correct value **is** stored, in
`systemSnapshot.dollarAmount` — but `systemSnapshot` is **not** included
in the `priorMap` payload built at `moves.js:1403-1407`. Exposing it is a
one-line server change; a fix prompt should call that out explicitly
rather than letting the fallback quietly misreport.

---

## Edge cases a fix prompt should decide on

1. **Partial execution.** Accept $500 of a $1,000 trim, execute exactly
   that $500 → the diff shrinks but doesn't vanish, so the move keeps
   showing and would still be badged "pending execution" even though the
   user did precisely what they committed to. The current data model
   can't distinguish this from "did nothing."
2. **Accepted-then-drifted-further.** Price moves the wrong way after
   acceptance; the recomputed number is now *larger* than what was
   accepted. The badge is correct, but the tooltip's "at $[X]" and the
   row's current figure will disagree — worth deciding whether the
   tooltip should surface both.
3. **Declined moves.** They keep reappearing every visit too (same
   live-recompute logic). Out of scope for this design, but the same
   "why is this still here" question applies, and `✗ Declined` has the
   same staleness ambiguity.

---

## Summary for a fix prompt

| Piece | Status |
|---|---|
| Move disappears when diff resolves | ✅ Works, no code needed |
| Move re-shows at fresh numbers if diff persists | ✅ Works |
| Accept/decline state survives reload | ✅ Works (`:1487-1500`) |
| Collapsed row shows accepted state | ✅ Works (`✓ Accepted $X`, `:527-541`) |
| Decision date visible without expanding | ❌ Only in expanded detail (`:586-596`, gated at `:561`) |
| Visual "pending execution" distinction | ❌ Missing — this is the actual ask |
| Data to *drive* the badge | ✅ Already sufficient (`decision.status === 'accepted'` on a rendered row) |
| Historically accurate `$X` for the tooltip | ⚠️ Stored in `systemSnapshot.dollarAmount` but not sent to client |
| Shared circled-bang component | ❌ Doesn't exist; one instance in Radar; extraction now justified |

**Scope of the eventual fix:** one small new shared component, one badge
insertion in the Decision cell, a `StaleTranscriptBadge` refactor to use
it, and (if the tooltip quotes a dollar figure) one added field in the
server's `priorMap` payload. No schema migration, no execution tracking,
no changes to the moves engine.

## What was deliberately NOT done

- **No implementation** — recon only, per the prompt. No files changed,
  nothing committed.
- Did not extract `CircledBangBadge` or touch `StaleTranscriptBadge`.
- Did not add `systemSnapshot` to the payload.
- Did not resolve the three edge cases above — they're design calls.

## Note on a referenced file

The prompt cites `memory/freshstart_mode_sticky_ux_question.md` for full
design context. I did not locate or read that file; this recon is based
entirely on the code. If it contains constraints that contradict anything
above, the code findings should still hold, but the recommendations may
need adjusting.
