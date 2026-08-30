# Fix: ADD routing double-counts cash across rows in the same run

## Report your findings

Write a wrap-up to
`./wrap-ups/fix-add-routing-cash-double-counting-out.md`.

## Context

Confirmed via two separate recon passes (2026-08-24) that **both**
account-routing functions in `server/routes/moves.js` have the same
bug: they compute "which account funds this ADD" independently per row,
using each account's raw `cashBalance`, with no memory of what other
rows in the *same* `computeMovesPayload` run already claimed against
that same cash.

- `buildNewPositionRouting(accounts, dollarAmount)` (~line 402) — used
  for the three bucket-level "unallocated"/"below minimum" rows
  (ETF/Crypto/Commodities) added in `fix-outofscope-add-account-routing`
  (commit `ce1e725`). Confirmed live: Andrea's account has $1,479.28
  total cash, but her ETF ($3,922 gap), Crypto ($1,625 gap), and
  Commodities ($136 gap) rows were each independently told "fund
  yourself from Andrea Custodial" — collectively needing ~$5,700 against
  $1,479 actually available. Also: `insufficientCash` only fires when an
  account has **zero** room, so a row 38% funded looks identical to one
  100% funded — no partial-coverage signal at all.
- `buildAddRouting(positions, addValue, price)` (~line 299) — used for
  real ticker-specific ADD rows (e.g. "ADD QS $1,066", "ADD AVGO $515").
  Same flaw, confirmed by code trace: reads `pos.account?.cashBalance`
  directly (line ~330), called once per ticker inside the per-ticker
  loop (`generateMovesForTicker`, called from a `for (const g of
  individualGroups)` loop, ~line 1408), with zero accumulator threaded
  between iterations. Two real ADD rows landing on the same account can
  each independently claim up to that account's full cash balance.

**`accounts`/`cashBalance` is a single per-run snapshot** — fetched once
near the top of `computeMovesPayload` (`prisma.account.findMany(...)`,
~line 937) and reused unmodified for the entire run. This matters: the
fix is a per-run, per-account committed-dollars tracker, not a change to
how/when cash balances are fetched.

**Not the cause of the AVGO-in-wrong-account incident** — that was
independently diagnosed and explained by an unplanned manual SIVR
purchase consuming the ROTH's cash headroom ahead of AVGO, unrelated to
this bug. This fix is about the *displayed* routing recommendations
being internally consistent with each other, not about the manual
execution-sequencing problem (tracked separately, backlogged — see
`memory/accept_triggers_trade_ticket_backlog.md`).

## What to build

Introduce a single per-run, per-account "committed dollars" tracker
(e.g. a `Map<accountId, number>` created once near where `accounts` is
fetched, ~line 937) that both `buildAddRouting` and
`buildNewPositionRouting` read from and write to:

1. When either function decides to route `$X` of an ADD to account `A`,
   it should check `A.cashBalance - alreadyCommitted(A)`, not raw
   `A.cashBalance`, when deciding how much room is actually left.
2. After computing a row's routing, add the committed amount(s) to the
   tracker for each account used, so the *next* routing call in the same
   run sees the reduced, real remaining room.
3. **Ordering matters and needs a decision, not an assumption — trace
   and report which is actually happening, don't guess:** moves are
   generated in some fixed order (currently: fixed buckets, then
   individual ticker groups, then freshStart/scarcity-gap rows — confirm
   exact order by reading the run top-to-bottom). Since the tracker
   depletes as it goes, whichever row happens to be processed first gets
   first claim on real cash, and later rows in the same account
   increasingly show `insufficientCash` or reduced routed amounts even
   though nothing about their own recommendation changed. **This is a
   real, unavoidable consequence of a limited, shared resource — the
   question is whether the current processing order produces sensible,
   defensible results (e.g. bigger/higher-priority gaps get funded
   first) or an arbitrary one (e.g. alphabetical-by-ticker) that would
   look confusing to a user.** Report what you find; if the order looks
   arbitrary, flag it rather than silently reordering — that's a product
   decision, not a bug fix.
4. **Fix the silent partial-coverage gap too** (noted in the original
   recon, not yet fixed): `insufficientCash` currently only fires when
   an account has zero room. Change the flag/threshold so a row that's
   only partially funded (routed amount < requested amount, across all
   available accounts) is also flagged — distinctly from full
   insufficiency if that distinction is useful, but at minimum, visibly
   different from "fully funded."

## What NOT to do

- Do not touch the underlying moves-generation logic (which
  tickers/buckets get ADD/TRIM recommendations, or for how much) — this
  is scoped entirely to the routing/funding-source layer.
- Do not attempt to fix the manual execution-sequencing problem that
  actually caused the AVGO incident — that's separately backlogged.
- Do not silently reorder move generation to "optimize" funding
  fairness — if the current order produces a bad result, report it and
  let Luis decide; don't make that call unilaterally.

## Verify

1. Live-data check for at least one owner with multiple ADD rows
   pointing at the same account (Andrea's bucket rows are a known
   example, if still present within the 24h freshStart window — check
   first, generate a fresh comparable scenario if it's expired): confirm
   the sum of routed dollars to any single account across ALL rows in
   one run never exceeds that account's actual `cashBalance`.
2. Confirm partial coverage is now visibly flagged, not just full
   insufficiency (re-test the Andrea ETF-row case: $1,479 routed against
   a $3,922 gap should now show as under-funded, not silently accepted).
3. Confirm the processing-order finding from item 3 above is explicitly
   reported, with a concrete example if the order is non-obvious.
4. Confirm no regression on rows that don't share an account with
   anything else in the same run — their routed amounts should be
   unchanged from before this fix.
5. `node --check server/routes/moves.js` and `npx vite build` clean.
6. Run `./server/scripts/verify-allocation-math.sh` — this is a
   read-only display-layer change (no `OwnerDecision`/position writes
   expected); confirm output unchanged from the pre-existing baseline
   (task #50).

## Commit and push

```bash
git add -A
git commit -m "Fix ADD routing double-counting cash across rows in the same moves-generation run"
git push origin dev
```

## Reminder: write the wrap-up

Don't finish without
`./wrap-ups/fix-add-routing-cash-double-counting-out.md` existing, with
the ordering question (item 3) explicitly addressed.
