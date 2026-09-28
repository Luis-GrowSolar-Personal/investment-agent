# Allocator book test — severity-sized trims on hundreds of train books — $0

**Run ID:** `allocator-book-test`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/allocator-book-test-out.md`
**Cost: $0.** No API calls, no DB writes, no scoring, no cache refresh.
**Design:** `docs/handoffs/2026-09-28-allocator-book-test-design.md`,
**including Amendments 1 and 1a**, and its review
`docs/handoffs/2026-09-28-book-test-amendment-1-review.md`.

---

## Settled with review

Reviewed in `docs/handoffs/2026-09-28-allocator-book-test-prompt-review.md`.
R1–R3 agreed (R1's reason corrected below). R4 changed to 8 / 4 / 4.
**Added: no-skill control arms 3R and 2R**, and the headline now needs
arm 3 to beat both holding the book **and** random trims. Each point is
marked **[R1]–[R4]** where it applies below.

- **[R1] ALL16 cannot run on train data.** Only 6 of the 16 names are
  train companies (MSFT, AMPX, EOSE, QS, RUN, TTD). Five are tune
  (GOOGL, ORCL, TSLA, ENVX, SPWR) and five are **holdout** (AAPL, AMD,
  AVGO, NVDA, FSLR) (`SPLIT_V7_RESERVE_REPLACEMENTS.json`). B's scores
  on all 195 ALL16 calls already exist from the end-to-end run, so the
  lock is not the blocker. **P9 has no ALL16 scores**, and making them is
  about $10 of new spend outside a $0 run. ALL16 with P9 scored is the
  tune/holdout confirmation of the finished allocator. **This prompt
  drops ALL16** and runs a **TRAIN6** book (the six train names),
  reported only. ALL16 belongs with the tune/holdout confirmation of the
  finished allocator.
- **[R2] Timing.** The design's ruler is phase-averaged over monthly
  sessions (K = 30, phases 0/10/20). Amendment 1 said a 5-point trim
  executes at the call's tradeable entry and again 21 trading days
  later. These are reconciled as follows: **every arm acts at monthly
  sessions**, which matches production. A call acts at the first session
  on or after its tradeable entry. The second half of a 5-point trim
  executes at the next session.
- **[R3] Resampling books overstates certainty.** The 400 books are
  built from 55 companies, so the same few names drive many books. The
  ALL16 result once flipped on FSLR alone. **Added to the pass rule:**
  the win share must stay at 70% or above when each single company is
  removed (dropping every book that contains it).
- **[R4] Stratified pools, 8 / 4 / 4.** Megacap = S1 + MSFT (16 names);
  mid = S2 (9); speculative = S4 + AMPX, EOSE, QS, RUN, TTD (7). S3 (out
  of domain) is not used. Luis's shape is 8 / 2 / 6, but with 7
  speculative names there are only 7 ways to pick 6, so every book would
  hold nearly the same speculative names, and that is where the trims
  land. **8 megacap, 4 mid, 4 speculative** gives 35 speculative
  combinations instead of 7. The wrap-up states the change and the reason.

---

## Framing

**The question.** On a book that is bought once and then left alone,
does trimming the names B flags **and** P9 rates severe, with the money
sent to QQQ, beat simply holding the book? And does it beat the same
number of trims on calls picked at random? The measure is return per
unit of maximum drawdown.

**Why the second part.** Moving money from single names into QQQ lowers
drawdown almost by itself: QQQ swings less than any single name and beat
most of the corpus over the period. So arm 3 could beat arm 0 whatever B
and P9 say. Arm 3R keeps everything about arm 3 except the analyst's
choice of which call to trim. Only arm 3 vs arm 3R measures that choice.

**What earlier runs settled; do not rediscover.**
- Trimming every name B flags does not pay, into either index
  (`wrap-ups/per-trim-value-out.md`, `…-qqq-out.md`). Arm 2 is expected to
  fail.
- Trimming only the two most severe P9 fifths earns $342–344 more per
  flagged call than a random trim, into either index, on both draws. That
  is on these same train calls, so it is a lead.

**What this run can and cannot show (the wrap-up must say this).** The
flags, t1 and t2 all come from the same train calls the books are drawn
from. So this is **not a second look at the signal.** It tests whether
the signal survives the mechanics: position sizes, drift, sequencing,
compounding, drawdown, and two-step execution. A pass means the
mechanics don't eat it. Only tune can confirm the signal.

---

## Ground rules

1. $0. No API calls, no DB writes, no cache refresh, no fetches. Train
   companies only; **no tune or holdout company appears in any book.**
2. **Every reading, threshold, pool and seed below is fixed before any
   book runs.** t1 and t2 are written to `results.json` before any arm
   runs. Do not add conditions after seeing results. Diagnostics you add
   must be labelled diagnostic-only.
3. Do not change any registry, gate, promoted version or production code.
4. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/allocator-book-test/`. `progress.json`
first. Commit this prompt on its own (`prompt: allocator book test`).
Clean tree; hard stop if `git_dirty` cannot be recorded `false`. The new
script is committed before any output, as its own commit.

## Step 0.5 — inputs and preflight (any failure → stop and report)

- **Companies:** the 55 in `analysis/data/run_state/p6-output-format-round/calls.csv`
  (1,217 calls). Assert none is in tune or holdout.
- **Scores:** B draws 1 and 2 and P9 draws 1 and 2 (paths as in
  `prompts/per-trim-value.md`). Per call: `b_mean` = the mean of B's two
  scores; `p9_avg` = the mean of P9's two `expectedReturn` values.
- **Prices:** `analysis/data/corpus_v2/scorer_price_cache_v1.json`, now
  with QQQ and SPY. **Assert QQQ is present**, or stop.
- **Window.** Start **2020-01-02**. End = the first trading day on or
  after (last train call + 182 days). Record both.
- **Late listings.** AMPX (first price 2022-09-15), EOSE (2020-11-02) and
  QS (2020-08-17) have no price at the start. In **every** arm, the slice
  of such a name sits in QQQ from the start. It moves into the name at the
  first session on or after its first price. It is identical across arms,
  so it cannot favour one.
- **Script:** `analysis/allocator_book_test.py`, new. Import `maxdd` and
  the daily-NAV method from `analysis/resolve_open_four.py`, the gate
  metric from `analysis/e2e_scorer.py` (CAGR ÷ max drawdown), and the
  ticker-block bootstrap from `analysis/p6_output_format_analysis.py`.
  Do not fork them.

## Step 1 — freeze t1 and t2 (before any arm runs)

- Flag = `b_mean` ≤ −2. Report how many train calls are flagged.
- Among flagged calls, rank `p9_avg` from most negative. **t1** = the
  value at the 20% mark and **t2** = the value at the 40% mark, by
  nearest rank, ties by seed 11.
- Write t1, t2 and the flagged count to `results.json`, commit
  (`book test: t1/t2 frozen`), **then** run the arms. These two numbers
  carry unchanged to tune.
- Expected, not a condition: the flagged count and per-trim figures will
  not match the per-trim run's 374 rows, which flagged each draw
  separately.

## Step 2 — the arms

Common to all arms: $100,000; K = 30-day sessions; phases 0/10/20 and
phase-averaged **[R2]**; a call acts at the first session on or after its
tradeable entry; trims are measured in points of the book's value at
that session; a trim larger than the position sells all of it; trim
proceeds buy QQQ (SPY in arm 3S) at that session and are held to the end;
a position sold to zero stays at zero. **Never** in any arm: adding on a
bullish score; spreading proceeds across other names; rebalancing toward
targets.

| arm | rule |
|---|---|
| **0** | buy 16 names at equal weight ($6,250 each) at the start; hold; never trade |
| **1** | QQQ alone |
| **2** | arm 0, plus: a flagged call trims 2.5 points |
| **3** | arm 0, plus: a flagged call with `p9_avg` ≤ t1 trims 5 points (2.5 at that session, 2.5 at the next); ≤ t2 trims 2.5; otherwise nothing. If a newer call on the name acts before the second half, the second half is cancelled and the newer call's rule applies |
| **3F** | as arm 3, but trims are **fractions of the position** at the first session: band 1 sells 40% of that position, then another 40% of **that same starting position** at the next session (20% left); band 2 sells 40% in one step. Reported only |
| **3R** | **no-skill control for arm 3.** For each trim arm 3 makes on this book (session, size, one or two steps), trim instead a call picked at random from the book's calls whose action session falls in the **same calendar quarter**, among names still held at that session (any call, flagged or not; seed 11, one draw per book). If no such call exists, no trim. Same sizes, same two-step execution, proceeds to QQQ |
| **2R** | the same control for arm 2 |
| **3S** | arm 3 with proceeds to SPY. Reported only |
| **M** | the production allocator. See Step 2b |

Per book and arm: final value, CAGR, **daily-marked** max drawdown,
**return per drawdown** (CAGR ÷ max drawdown), number of trims, points
moved. For arm 3, also: the share of trims that sold the whole position,
and the median position size (points of the book) at flag time.

### Step 2b — arm M, feasibility-gated

Arm M runs v6's verdicts through the settled production configuration
(`swap_funding`, K = 30, `new_calls_only`, X = 2.5, `pooled`,
`per_event_date`; see `analysis/resolve_open_four.py` `CELL`). The
existing event loader (`load_events_dedup_on`) is built for ALL16 and
reads extra fields from the DB. **Before building anything:** check
whether v6's train evaluations (`d.V6_EVAL_DIR`), the trend layer's
inputs and the type functions exist for the 55 train companies **without
the DB**.
- If yes: run arm M on every book, same window and phases.
- If no: **do not build a workaround.** Record exactly what is missing,
  mark arm M "not run," and continue. The "matrix costs money" reading is
  then deferred.

## Step 3 — the books

- **Random:** 200 books of 16 drawn from the 55 companies, seed 11.
- **Stratified [R4]:** 200 books of 8 megacap (S1 + MSFT), 4 mid (S2) and
  4 speculative (S4 + AMPX, EOSE, QS, RUN, TTD), seed 11.
- **TRAIN6 [R1]:** MSFT, AMPX, EOSE, QS, RUN, TTD at equal weight.
  Reported only, with a 6-way leave-one-out.

---

## Pre-registered readings (fixed now)

**Gain** = arm X's return per drawdown minus arm 0's, on the same book.
**Win share** = the share of books where the gain is above zero. **Range
on the median gain** = 2,000 resamples of books, seed 11.

**The pass rule**, for "arm X beats arm Y": in the random books, X beats
Y in **at least 70%** of books, **and** the median gain's range is above
zero, **and [R3]** the win share stays at or above 70% when each single
company is removed in turn (report the lowest share and the company that
caused it). The same test runs on the stratified books, reported
separately.

1. **Headline — "Severity-sized trims add value"** requires **both**:
   - **1a. "Beat holding":** arm 3 beats arm 0. The practical question.
   - **1b. "The analyst chose the trims":** arm 3 beats arm 3R. The
     skill question.
   If 1a passes and 1b does not, the reading is **"own more QQQ"**: a
   real result, but a different allocator, and it goes to the
   sleeve/index decision, not to P6D.
2. **"Plain trims add value"** — arm 2 vs arm 0, and arm 2 vs arm 2R,
   same rule. Expected to fail. A prediction, not a gate.
3. **"Severity adds over plain"** — arm 3 vs arm 2, same rule.
4. **"The matrix costs money"** — arm 0 beats arm M in at least 70% of
   books. Reported whatever the others say, if arm M ran.
5. **Units (Amendment 1a):** if arm 3F's win share against arm 0 is
   within 10 points of arm 3's, "the units do not matter." Otherwise,
   "the units matter," and position sizing is settled in the sleeve/index
   decision before P6D.
6. **Arm 3S:** reported beside arm 3. No reading.
7. **Prediction, not a gate:** arms 2 and 3 beat arm 0 on drawdown in
   nearly every book, and on final value in about half.

Report final value and drawdown beside the gate metric for every arm, so
a pass on return per drawdown that loses money is visible.

## Step 4 — band 5 lead, $0, reported only (Amendment 1a)

From the per-trim data (`run_state/per-trim-value-qqq/results.json`
inputs): for the mildest P9 fifth of flagged calls, pooled, both
destinations, report the median value per point, the mean with its range,
and the three companies contributing most to the mean. No reading. It
feeds the live forward test only.

---

## Report step

`wrap-ups/allocator-book-test-out.md`, `.md` only. Open with:

> Frozen before any arm ran: t1 = ___, t2 = ___ (___ flagged train calls).
> In ___ random 16-name books, trimming the names B flags and P9 rates
> severe (arm 3) beat holding the book (arm 0) on return per drawdown in
> ___% of books (median gain ___, range ___ to ___; lowest with one
> company removed ___%, ___). It beat the same trims on random calls
> (arm 3R) in ___% of books (median gain ___, range ___ to ___; lowest
> with one company removed ___%, ___). **Headline: [severity-sized trims
> add value / own more QQQ / do not add value].** Plain
> trims (arm 2): ___%. Stratified books: arm 3 ___%. Final value, arm 3
> vs arm 0, median across random books: $___ vs $___. Daily drawdown:
> ___% vs ___%. Arm M: [ran — the matrix ___ / not run — ___ missing].
> Units: [do / do not] matter (arm 3F ___% vs arm 3 ___%).

Then: one table per book set (arms as rows; median final value, median
CAGR, median daily drawdown, median return per drawdown, win share vs arm
0, median gain with range); the company-removal table; the arm 3 sizing
diagnostics; TRAIN6 with its leave-one-out; arm 3S; the band 5 lead;
deviations.

**State plainly** what this cannot show (the block under Framing), and
that ALL16 was not run and why **[R1]**.

**Close with what it means**, in plain words:
- 1a passes, 1b fails → "own more QQQ." The analyst did not choose the
  trims; the index did the work. This goes to the sleeve/index decision,
  not P6D.
- Headline passes and units don't matter → P6D is written against
  "flagged and severe, trimmed into the index," with t1/t2 frozen. The
  tune look goes to that allocator on tune-company books, with ALL16's
  tune names in it.
- Headline passes but units matter → the sleeve/index decision settles
  position sizing before P6D.
- Headline fails → the mechanics eat the per-trim edge. The rebuild does
  not proceed on these trims. The analyst stays a reading aid, and the
  live forward test is the remaining evidence.

Plain-language discipline is binding. Anchor every percentage to what it
is a percentage of.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure (file and key). One prompt in, one wrap-up out. **Finish
with `git push`** after the wrap-up commit and report the pushed hash.
If the push fails, say so and never force.
