# Fix: ADD rows double-count trim proceeds within an account

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-add-routing-trim-proceeds-double-counting-out.md`.

## Context

Confirmed live 2026-08-24 against Eduardo's Full Reset, both from the
app's own display and his actual executed trades (CSVs reconciled
outside this repo). Six different ROTH-routed ADD rows (AMD $1,410,
Commodities $753, AMPX $1,183, ENVX $1,663, ETF-unallocated $1,533,
Crypto-unallocated $1,533 — **$8,075 total**) each independently showed
their full amount as `expectedFromTrims`, citing "trims in this reset,
once executed." Eduardo's ROTH IRA only generates **$1,920** from trims
in that same batch (BTC trim $669 + EOSE exit $924 + SPWR exit $327).
The app effectively promised the same $1,920 to six different rows,
several of them for the row's *entire* requested amount. Eduardo's real
executed trades confirm the fallout exactly: he executed ROTH's three
sells plus one buy (QQQ, funding the ETF row, ~matching the $1,920
proceeds), then redirected every other ROTH-routed ADD (AMD, Commodities
via GLD, AMPX, ENVX, Crypto via SOLZ) into his Custodial account instead
once he ran out of real ROTH cash.

**This is a known, already-documented, previously-deferred gap** — see
`fix-add-routing-honest-funding-note-out.md` (commit `7a75576`):
*"`expectedFromTrims` is batch-level context, not an exclusive per-row
claim... I did not build a second ledger for trim proceeds because doing
so would re-open the funding-order question, which you hadn't decided."*
The funding-order question was decided immediately after
(`fix-add-routing-funding-priority-order`, commit `0021bcc`:
Established → Speculative → ETF → Commodities → Crypto). That was the
explicit blocker for this fix, and it's now resolved — this task closes
the deferred gap using that same order.

**Important distinction to preserve, not collapse:** there are two
genuinely different situations, and the fix needs to tell them apart,
not just cap one number:
1. **Double-counting** — multiple rows citing the same real trim
   proceeds without decrementing (the bug).
2. **Genuine self-funding shortfall** — an account's own trims/exits in
   this batch may never have been enough to cover its own adds, even
   with correct decrementing (e.g. ROTH holds different tickers than
   what's newly recommended there). This is not a bug; it's a real
   structural fact about the account, and should be surfaced honestly
   as such (money would need to come from elsewhere or a deposit), not
   hidden or conflated with #1.

## What to build

1. **A second, per-run, per-account ledger for trim proceeds**, parallel
   to the idle-cash ledger from `844e3c7`
   (`availableCash`/`commitCash`), but tracking trim/exit dollar
   proceeds (net of tax cost, as `annotateAddFunding` already computes
   per-account: `dollarAmount - taxCost`) instead of cash balance.
2. **Consume this ledger in the same priority order already decided**
   (Established → Speculative → ETF → Commodities → Crypto, using
   `scoreCandidate`/`barbellSide` as the previous fix did) — read
   `routeAddsInFundingOrder` (added in `0021bcc`) first; this is very
   likely the right place to also decrement trim proceeds, since it
   already runs as an ordered post-pass immediately before
   `annotateAddFunding`.
3. **`annotateAddFunding`'s `expectedFromTrims` should reflect what's
   actually left in that account's trim-proceeds ledger after earlier,
   higher-priority rows have claimed their share** — not the account's
   total trim proceeds recomputed fresh for every row (today's bug).
4. **Once an account's real trim proceeds (net of what idle cash
   already covers) are exhausted, later rows should show the shortfall
   as `unbacked`** (the existing category from `7a75576`, meaning "no
   plausible source in this batch — needs a deposit or money from
   elsewhere"), not as `expectedFromTrims` repeating a claim that's
   already spoken for. This is where the fix should visibly change
   Eduardo's numbers: several of his six ROTH ADD rows should show
   partial or full `unbacked` amounts once the $1,920 is honestly
   divided among them by priority, instead of all six showing full
   coverage.
5. Keep genuine self-funding shortfalls (situation #2 above) visible as
   `unbacked` with the existing wording from `7a75576` — don't invent a
   third category unless you find a real reason one is needed; report
   if you think one is.

## What NOT to do

- Do not change move sizing, which tickers get recommended, or dollar
  amounts — this is scoped entirely to the `expectedFromTrims`/`unbacked`
  split within `annotateAddFunding`.
- Do not add gating or disabled buttons — Accept/Decline stay fully
  independent on every row, consistent with every prior fix in this
  chain.
- Do not touch the idle-cash ledger (`availableCash`/`commitCash` from
  `844e3c7`) or the funding priority order (`0021bcc`) — reuse both
  as-is.
- Do not attempt to solve cross-account funding (e.g. suggesting money
  move from Custodial to cover a ROTH shortfall) — real accounts can't
  transfer between tax treatments this way; a ROTH shortfall is
  correctly `unbacked`, not reassigned to another account.

## Verify

1. **Live reconciliation against Eduardo's known-bad case.** Recompute
   his freshStart ROTH rows and confirm the $1,920 in real trim proceeds
   is now divided among the six competing ADD rows by priority order,
   not claimed in full by all six. Show the before/after split, the same
   way prior wrap-ups in this chain have.
2. **Invariant check**: for every account, sum of `expectedFromTrims`
   across ALL ADD rows routed to that account must never exceed that
   account's actual total trim/exit proceeds (net of tax) in the same
   batch. Check across all three owners, both modes — same rigor as the
   idle-cash invariant check in `844e3c7`'s wrap-up.
3. **Split arithmetic still holds**: `fromCash + expectedFromTrims +
   unbacked == requested` for every ADD row, re-verified after this
   change (same check `7a75576` and `0021bcc` both ran).
4. Confirm a genuine self-funding shortfall (situation #2) is
   distinguishable in the data from a resolved double-count — trace at
   least one live example if one exists.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` — no writes
   expected; confirm output matches the tracked task-#50 baseline.

## Commit and push

```bash
git add -A
git commit -m "Stop ADD rows from double-counting the same account's trim proceeds"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-add-routing-trim-proceeds-double-counting-out.md`
existing, with the before/after on Eduardo's ROTH rows shown explicitly.
