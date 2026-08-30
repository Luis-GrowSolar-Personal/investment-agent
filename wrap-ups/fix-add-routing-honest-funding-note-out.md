# Fix: replace misleading ADD-row funding flags with an honest split note

**Commit `7a75576`, pushed to `origin/dev`.** Two files:
`server/routes/moves.js`, `client/src/pages/PortfolioManager.jsx`.

The reframing is done and verified numerically. **Two things beyond the
brief:** I found a real regression that my own previous commit
(`844e3c7`) introduced, which this change fixes; and item 4's
"no-plausible-coverage" case turns out to be real, occurring twice in
live data.

## Premise check — accurate

Everything described was confirmed: `insufficientCash` was set only in
the no-cash fallback, `partiallyFunded`/`unfundedAmount` came from
`844e3c7`, and the framing problem is exactly as stated — after the
ledger fix, 22 of 26 live ADD rows had $0 or near-$0 of idle-cash
backing, because the money genuinely comes from unexecuted trims.

## ⚠ Regression found in `844e3c7` — ADD rows were being hidden

Not mentioned in the prompt, and I missed it when I shipped the ledger
fix. Two frontend consumers keyed off `insufficientCash` for more than
display:

```js
// moveAppliesToBucket — decides which moves show when an account is selected
if (move.moveType === 'ADD') return rows.some(a => !a.insufficientCash);

// countsByType — the per-account-type ADD tallies in AccountBuckets
else if (move.moveType === 'ADD' && rows.some(a => !a.insufficientCash))
```

Before `844e3c7`, every row independently claimed the same cash, so
`insufficientCash` was rare and rows displayed normally. **After it, most
re-baseline ADDs carried the flag — so selecting an account bucket
silently hid them, and the bucket counts understated the work.** For
Eduardo's freshStart that meant all seven ticker ADDs vanishing from a
filtered view.

Both now count an ADD by whether it touches the account at all. This is
the opposite of gating — strictly more rows visible — so it stays within
the prompt's "no gating" constraint.

## What changed

### Server — a move-level funding split

`annotateAddFunding(actionMoves)` runs as a **post-pass**, after every
move exists, because it needs the batch's trims — which are generated
interleaved with the adds, so no per-row calculation during generation
could see them.

```js
m.funding = {
  requested,          // the row's dollar amount
  fromCash,           // what the 844e3c7 ledger actually allocated (reused, not recomputed)
  expectedFromTrims,  // remainder, capped by trim proceeds landing in accounts this add uses
  unbacked,           // remainder with no plausible source in this batch
};
```

Trim proceeds are summed **per account** as `dollarAmount - taxCost`,
and only counted toward an add that routes to that same account —
proceeds can't cross a tax boundary without a contribution, so crediting
a taxable trim toward a Roth add would be fiction.

`insufficientCash` → **`isPlaceholder`**, which is what that row always
actually meant: "here's where the buy goes", not "something is wrong".
`partiallyFunded`/`unfundedAmount` are gone.

### Frontend

The amber shortfall warning is replaced by:

> **$1,479.28 available now** · $2,443.07 expected from trims in this
> reset, once executed

with a distinct, more pointed clause only when `unbacked > 0`:

> $475.21 not covered by idle cash or any trim in this batch — needs a
> deposit

Per-row "⚠ fund account first" became a neutral "destination — see
funding below". The bucket-row hint now reports the split in its tooltip
and reserves its ⚠ for genuinely unbacked dollars.

## Item 4 — the no-plausible-coverage case is REAL

Traced as instructed, and it occurs. Two rows, both Andrea freshStart:

```
Crypto (unallocated)  req $1,624.56 = cash $0.00 + trims $1,149.35 + unbacked  $475.21
QS                    req $1,162.44 = cash $0.00 + trims $1,149.35 + unbacked   $13.09
```

Both route to Andrea's ROTH IRA, which holds $0.03 idle and is the
destination for only $1,149.35 of trim proceeds in this batch. The
remainder has no source anywhere in the reset — it genuinely requires a
deposit. That is a materially different situation from "funded by trims
you haven't done yet", so it gets its own amber wording rather than the
soft blue phrasing.

**One honest limitation, deliberately not fixed.** `expectedFromTrims`
is batch-level context, not an exclusive per-row claim — note that
Crypto and QS above both cite the same $1,149.35 of ROTH proceeds. I did
not build a second ledger for trim proceeds because doing so would
re-open the funding-order question (which row gets first claim), which
`844e3c7`'s wrap-up flagged and you haven't decided. It's documented in
the code comment so the next reader doesn't mistake it for an oversight.
Worth knowing this is the same *shape* as the cash bug, differing in
that "the rest comes from trims in this batch" is a true statement about
the batch rather than a specific routing instruction.

## Verification — all 6 items

1. **Warning language gone** ✔ — `grep` for
   `insufficientCash|partiallyFunded|unfundedAmount` across the frontend
   returns **0**; the server has 0 remaining references too.
2. **Split arithmetic is internally consistent** ✔ — across all three
   owners, both modes, **26 ADD rows checked, 0 sum mismatches**:
   `fromCash + expectedFromTrims + unbacked == requested` every time.
   Sample:
   ```
   Eduardo [normal]  GOOGL  req $1,316.00 = cash $159.57 + trims $1,156.43 + unbacked $0.00
   Eduardo [fresh]   AMD    req $1,408.00 = cash   $0.00 + trims $1,408.00 + unbacked $0.00
   Andrea  [normal]  NFLX   req $1,067.00 = cash $1,067.00 + trims  $0.00 + unbacked $0.00
   ```
3. **Accept/Decline unchanged and independent** ✔ — verified
   structurally: Accept is `disabled={submitting}`; Decline is
   `disabled={submitting || !inputReason.trim()}` (the pre-existing
   mandatory-reason rule, untouched); `funding` is referenced **only**
   inside `AddRoutingDetail` and `BucketFundingHint`, never in a handler
   or button-state expression; no cross-row reads were introduced.
   *The click-through spot-check the prompt suggested was not performed
   — Chrome tools are still not connected (seventh session).*
4. **Addressed above** ✔ — real, occurs twice, phrased distinctly.
5. `node --check server/routes/moves.js` ✔ · `npx vite build` clean at
   112 modules ✔.
6. **`verify-allocation-math.sh`** ✔ — byte-identical to the task-#50
   baseline from earlier today (Andrea `$736.69` / `-$350.06` /
   `-$140.61`, Luis `$1,766.07`, Eduardo `$5.28` / `$30.45` / `$30.61`).
   **No writes** — `computeMovesPayload` is pure compute; no `upsert` in
   any verification script.

## Deviations from the prompt

1. **Fixed the row-hiding/undercounting regression** (above). Not in the
   brief, but the two gates were built on the very flag being replaced,
   so leaving them would have meant `isPlaceholder` rows still silently
   disappearing — defeating the point of the reframing.
2. **Renamed rather than deleted the row flag.** The prompt said replace
   `insufficientCash`/`partiallyFunded`; `partiallyFunded`/
   `unfundedAmount` are gone outright, but the fallback row still needs
   *some* marker to distinguish "destination only" from "funded
   allocation" — that's `isPlaceholder`, and it no longer carries error
   semantics.

## What was deliberately NOT done

- **No gating of Accept/Decline** on any row, by funding or anything
  else.
- **No sequenced/staged UI mode.**
- **No changes to `availableCash`/`commitCash`** — reused exactly as-is
  for the `fromCash` figure.
- **No change to funding order** — still undecided, still flagged from
  `844e3c7`.
- **No trim-proceeds ledger** — see the limitation above.
- **No visual verification** — seventh session without Chrome tools.

## Follow-up for Luis

1. **Eyeball the new split note.** Best live examples right now:
   - Andrea → freshStart → *Crypto (unallocated)* — shows all three
     segments including the amber "needs a deposit" clause.
   - Eduardo → normal → *GOOGL* — a clean cash-plus-trims split
     ($159.57 + $1,156.43).
2. **Check the un-hiding.** Select an account bucket in Recommended
   Moves and confirm ADD rows now appear that were vanishing before —
   Eduardo's freshStart ADDs are the clearest case.
3. **Still open from `844e3c7`:** the funding-order question (bucket-level
   rows currently get first claim on idle cash, ahead of specific ticker
   ADDs; and ticker order is database order). Unchanged here by design.
4. Confirm the deployed commit:
   ```bash
   railway link -p investment-agent-DEV --service investment-agent-DEV
   railway status --json | grep -o '"commitHash":"[^"]*"' | head -1
   # expect 7a75576...
   ```

## Note on the commit trailer

Unchanged: `Co-Authored-By: Claude Opus 4.8 (1M context)` per your
`/execute-prompt` workflow, though this session runs **Opus 5**.
