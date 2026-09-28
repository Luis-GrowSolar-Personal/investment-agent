# Allocator book test — design (registered 2026-09-28, top of the queue)

**Status:** registered, not yet written as a run prompt. $0 for arms 0–4.
**Owner of the decision:** Luis. **Writes the run prompt:** next CLI session, from this design.

---

## The idea in one paragraph

Cap-weighted index funds beat most managers because of one rule: they
never sell a winner and never add to a loser. They have no downside
skill at all. B has downside skill and no bullish skill. So the book
with the best chance of beating its own buy-and-hold is: hold the names,
let them drift, trim only what B flags, and send trim proceeds to the
index. The 55 train companies, with B, P9 and the raised-guidance flag
already scored on every call, let us test that rule on hundreds of
16-name books at no cost, instead of on ALL16 alone.

## What is measured

**The method owns the gap between "hold the book" and "hold the book
with trims."** It does not own whether the book beats QQQ; that is
decided by which names are in the book, and that choice stays with
Luis. QQQ is in every table as the reference line and as the home for
proceeds. It is not the yardstick.

Ruler: return per unit of maximum drawdown (`PROMOTION_GATE.md` §3.2),
daily-marked, phase-averaged over start phases 0/10/20. Final value and
drawdown reported beside it.

## Arms

| arm | rule | needs |
|---|---|---|
| 0 | buy the book at equal weight on day one, hold, never rebalance | prices |
| 1 | QQQ alone | prices |
| 2 | arm 0, plus: when B scores a call ≤ −2, trim that name by X = 2.5 points of the portfolio; proceeds to QQQ | B scores (mean of two draws) |
| 3 | arm 2, with the trim sized by P9's severity band instead of a fixed 2.5 | P9 scores (two draws) |
| 4 | arm 3, plus the raised-guidance veto: no trim on a call that raised guidance | guidance flag |
| M | the current production allocator (matrix, ratchet, trend layer) on the same book | existing simulator |

Arms 0–4 are one new script. Arm M reuses the existing simulator so the
cost of what is in production can be read on the same books.

**Never in any arm:** adding to a position on a bullish score;
spreading trim proceeds across the other names; rebalancing toward
target weights.

## Books

- **Random:** 200 books of 16 drawn from the 55 train companies, seed 11.
- **Stratified:** 200 books shaped like Luis's: 8 megacap, 2 mid, 6
  speculative, using the corpus strata.
- **ALL16:** run last, read against the two distributions, with the
  16-way leave-one-out.

Train companies only. Tune and holdout are held back to confirm the
finished allocator.

## Pre-registered readings (fixed before the run)

- **"Trims add value"** if arm 2 beats arm 0 on return per drawdown in
  at least **70%** of random books **and** the median gain's range
  (bootstrap over books) sits above zero. Same test on the stratified
  set, reported separately.
- **"Severity adds"** if arm 3 beats arm 2 by the same rule. **"Veto
  adds"** if arm 4 beats arm 3.
- **"The matrix costs money"** if arm 0 beats arm M in at least 70% of
  books. This is a finding about production, reported whatever the
  others say.
- **Prediction, not a gate:** arm 2 beats arm 0 on drawdown in nearly
  every book, on final value in about half. The 16-way leave-one-out on
  ALL16 showed that shape once already.

## Known limits, stated now

- Equal start, not cap weight: no shares-outstanding data. The drift is
  the property that matters and equal-start has it from day one.
- The 55 companies were chosen with sector strata in mind. Books are fair
  relative to one another; the level of return means nothing.
- B's scores on train are the same scores used to pick B. That is why
  tune and holdout stay locked.

## What each outcome changes

Trims add value across books → P6D is written against this base book.
Trims fail → the allocator rebuild leans on the veto and severity before
B, and the live forward test decides. Matrix costs money → production
changes before anything else does.
