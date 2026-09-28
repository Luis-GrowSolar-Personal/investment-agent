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

---

## Amendment 1 — 2026-09-28, after the per-trim value run

**Why.** `wrap-ups/per-trim-value-out.md` (SPY leg) found that trimming
every name B flags does not clearly pay: +$138 per trim on $100,000,
range −$129 to +$387, and only +$110 more than a random trim in the same
quarter (range −$100 to +$304). The losses are clipped winners: 52 of 374
flagged calls went on to beat the S&P by 20+ points. Sizing the trim by
P9's severity turned it around: trims only on the two most severe fifths
of flagged calls earned +$342 per flagged call more than random trims
(range +$146 to +$516), the same on both draws. The flagged calls P9
rates mildest beat the S&P by 28 points on average.

That P9 result is on the same train calls where P9's severity was first
found. It is a strong lead, not a confirmation. The confirmation is the
tune look at the finished allocator (decision 5, as rewritten).

**Changes, all fixed before the run:**

1. **Arm 3 is the candidate.** The headline reading becomes
   **"Severity-sized trims add value"**: arm 3 beats arm 0 by the existing
   rule (at least 70% of random books, and the median gain's range above
   zero; stratified reported separately). Arm 2 vs arm 0 and arm 3 vs
   arm 2 stay in, reported with their own readings. On the per-trim
   evidence, arm 2 is expected to fail or be mixed. That is a prediction,
   not a gate.

2. **Arm 3's sizing must not look ahead.** The per-trim run cut flagged
   calls into fifths *after* seeing all of them. A book cannot do that at
   trim time. So, before any arm runs:
   - Flag = the mean of B's two draws ≤ −2 (as in the design).
   - Among the flagged train calls, take averaged P9 (mean of P9's two
     `expectedReturn` draws). Record the value at the 20% mark and the
     40% mark, counting from most negative: **t1** and **t2**.
   - Rule: averaged P9 ≤ t1 → trim 5 points; ≤ t2 → 2.5 points; else 0.
   - Write t1 and t2 to `results.json` before any arm runs. **These two
     numbers carry unchanged to the tune look.**

3. **Speed limit.** No trim moves more than 2.5 points at once (X). A
   5-point trim executes as 2.5 points at the call's tradeable entry and
   2.5 points 21 trading days later, unless a newer call on that name
   arrives first, in which case the newer call's rule governs and the
   second half is cancelled. A trim larger than the position sells the
   whole position.

4. **Arm 4 (the guidance veto) is dropped.** Only one flagged train call
   carries the beat-and-raise tag, so arm 4 would equal arm 3. The veto
   is closed. (The earlier "15 calls" counted a raise *or* a beat; that
   wider tag was found after the fact and is not being tested.)

5. **One reported-only variant, arm 3S:** arm 3 with proceeds to SPY
   instead of QQQ. It separates the rule's value from QQQ's lead over the
   S&P in this period. Not gated.

6. **Prerequisite.** QQQ must be in
   `analysis/data/corpus_v2/scorer_price_cache_v1.json`
   (`prompts/per-trim-value-qqq.md` adds it). If it is absent, the book
   test stops before running any arm.

Unchanged: the ruler, the books (200 random, 200 stratified, ALL16 last
with leave-one-out), arm M, the "never" list, train companies only.

---

## Amendment 1a — 2026-09-28, adopted from review

Source: `docs/handoffs/2026-09-28-book-test-amendment-1-review.md`.
Amendment 1 items 1–6 stand. Added, all fixed before the run:

1. **Arm 3F, reported only.** Same flag, same t1/t2, but the trim is a
   **fraction of the position at the call's tradeable entry**: band 1
   sells 80% of it, band 2 sells 40%. **Speed limit in fractions:** band 1
   executes as 40% of that starting position at entry and another 40% of
   the same starting position 21 trading days later (leaving 20%), with
   the same newer-call cancellation as arm 3. Band 2 executes in one step.
   Proceeds to QQQ. Not gated.

2. **Per book, under arm 3:** the share of trims that sold the whole
   position, and the median position size (points of the book) at flag
   time.

3. **Reading of 3 vs 3F (fixed now, reported only):** if arm 3F beats
   arm 0 in the random books at a rate within 10 points of arm 3's, "the
   units do not matter." Otherwise, "the units matter," and position
   sizing is settled in the sleeve/index decision before P6D.

4. **Band 5 lead, $0, reported only.** From the per-trim data, for the
   mildest P9 fifth of flagged calls (SPY and QQQ legs): median value per
   point, mean with its range, and the three companies that contribute
   most to the mean. Note that the SPY-leg range on the mean was −0.63 to
   +0.01 per point: it just includes zero, so the "rose 28 points" figure
   is not yet established. Whatever it shows, the lead earns no train
   candidate and no tune look. It earns a line in the live forward test:
   score B and P9 live and grade the cases where B flags and P9 rates
   mild.

5. **Wrap-up must say** what the book test can show for arm 3: t1/t2 and
   the flags come from the same train calls the books are drawn from. The
   test checks whether the signal survives the mechanics (sizes, drift,
   sequencing, compounding, drawdown, two-step execution). It is not a
   second look at the signal. Tune is.

6. **Expected mismatch, stated now:** the book test flags on the mean of
   B's two draws, not each draw separately, so its flagged count and
   per-trim figures will not match the per-trim run's 374 rows and $342.
   They should point the same way.
