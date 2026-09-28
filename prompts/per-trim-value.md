# Per-trim value of B's bearish flags, against a no-skill control — $0

**Run ID:** `per-trim-value`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/per-trim-value-out.md`
**Cost: $0.** No API calls, no DB writes, no scoring, no cache refresh.
Reads existing score, label and price files only.

**Agreed design:** `docs/handoffs/2026-09-28-per-trim-value-reply.md`,
`…-counter.md`, `…-reply-2.md`. This prompt implements all three. One
change from reply 2, stated here so the review session sees it: the
time-matched control uses **the average over every train call in the
same calendar quarter**, not one randomly drawn call per flagged call.
Both have the same expected value. The average removes a layer of
randomness that would widen the range and make the answer depend on the
seed (the P9 averaged reading passed by 0.0002 and flipped on three of
four alternate seeds).

---

## Framing

**The question.** When B flags a name (score ≤ −2) and 2.5 points of the
book move from that name into the index, does that trim make money
**beyond what the same trim on a name picked at random would make?**

**Why the control matters.** About 47% of train calls lagged the S&P by
more than 5 points whatever B said, and QQQ beat the S&P over most of the
period. A trim of a random name into QQQ may pay by itself. If it does,
a positive result for B's flags alone would say "own QQQ," not "the
analyst helps."

**Already established; do not rediscover.**
- B's bearish skill: bottom 191 right 62.3% / 61.3% on two train draws;
  confirmed on tune (ranking 0.140).
- P9 severity: within B's bottom 191, averaged P9 ranks outcomes at 0.222
  (0.067 to 0.345). `wrap-ups/P9-close-and-averaged-comparison-out.md`.
- Beat-and-raise tag: 116 of 1,217 calls.
  `wrap-ups/winners-missed-v3-out.md`, labels in
  `analysis/data/run_state/winners-missed-v3/read_labels_v3.jsonl`.

**Files.**
- B: `analysis/data/run_state/p6-output-format-round/scores_b.jsonl`,
  `analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl`
- P9: `analysis/data/run_state/p9-expected-return-train/scores_p9.jsonl`,
  `analysis/data/run_state/p9-second-draw/scores_p9_rerun1.jsonl`
- Prices and the tradeable-entry 182-day ruler: `PriceCache` and
  `rel_ret(..., "B", 182)` as used in `analysis/p6_output_format_analysis.py`.
  Helpers (`spearman`, ticker-block `boot`, `wilson`) from the same module.

**Read first:** the three handoff notes above; the two wrap-ups above;
`analysis/b_noise_floor_analysis.py` (pattern to follow). Write a new
script `analysis/per_trim_value.py` that imports those helpers; do not
fork them.

---

## Ground rules

1. **$0.** No API calls, no DB writes, no cache refresh, no price fetches.
2. **Do not change** B's incumbent status, any registry entry, gate,
   tolerance or rule. This run writes no bookkeeping.
3. **Every reading in this prompt is fixed before any number is
   computed.** Do not add conditions after seeing results. Diagnostics you
   add must be labelled diagnostic-only.
4. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/per-trim-value/`. `progress.json` is the
very first action. Commit this prompt file as its own commit
(`prompt: per-trim value of B's flags with no-skill control`). Then clean
tree; hard stop if `git_dirty` cannot be recorded `false`. The analysis
script is committed before any output, as its own commit.

## Step 0.5 — preflight (stop and report on any failure)

- **QQQ and SPY must both be in the price cache** over the full span of
  train call dates + 182 days. If QQQ is missing or has gaps, **stop and
  report.** Do not fetch.
- Build one row per train call (assert 1,217): ticker, call date,
  calendar quarter of the call date, B score draw 1 and 2, P9
  `expectedReturn` draw 1 and 2, beat-and-raise tag, and, over the same
  tradeable-entry 182-day window: the name's return, SPY's return, QQQ's
  return. Report how many calls are priced. Unpriced calls are dropped
  everywhere and counted.
- Sanity check: name return minus SPY return must reproduce
  `fwd_rel_ret_tradeable` to 4 decimals on every priced call. Report the
  largest mismatch.

---

## Definitions (fixed)

**Per-trim value**, for one call, destination D ∈ {QQQ, SPY}, size s
points of the book:

  value = s × (D's return − name's return), in points of the book.

Worked: s = 2.5, name −15%, QQQ +1% → 2.5 × 0.16 = **+0.40 points**
($400 on $100,000). Name +30%, QQQ +1% → 2.5 × (−0.29) = **−0.725 points**.

Because value is proportional to s, all results are also reported **per
point moved** (value ÷ s).

**Row A** — B's flagged calls: score ≤ −2. Reported for draw 1, draw 2,
and **pooled** (both draws' flagged calls stacked; a call flagged on both
draws appears twice).

**Row B, matched (the control the reading uses)** — for each call in A,
the **average per-trim value over every priced train call in the same
calendar quarter** (flagged or not), same destination, same s. Row B's
mean is the mean of those averages over A's calls. This is what a trim
rule with no skill earns at the same moments in time.

**Row B, unmatched (reference only)** — the average per-trim value over
every priced train call.

**A − B** — Row A mean minus Row B matched mean.

**Ranges.** 95% ticker-block bootstrap, 2,000 draws, seed 11. In each
draw, resample companies; recompute A, the quarter averages behind B
(from the resampled calls), and A − B together. Pooled rows resample
companies once and carry both draws' flags.

---

## Step 1 — the base result: fixed 2.5-point trims

For each destination (QQQ, SPY) and each of draw 1 / draw 2 / pooled:

1. n trims in A.
2. **Mean per-trim value of A**, in points and in $ on $100,000, with range.
3. Row B matched mean; Row B unmatched mean.
4. **A − B**, with range. **The reading rests on the pooled QQQ row and
   the pooled SPY row.**
5. **Where the total comes from.** Sort A's trims by value. Report the
   share of A's total (sum) that comes from the best 10% of trims (avoided
   disasters) and from the worst 10% (clipped winners), and the sum of the
   middle 80%. Report how many of A's trims were future big winners (beat
   the S&P by 20+ points) and their total value.
6. Median per-trim value beside the mean, labelled reference only.

## Step 2 — the P9 layer: trims sized by severity

**Severity measure:** averaged P9 (the mean of P9's two `expectedReturn`
values per call), chosen because it is the version whose severity range
is above zero (0.222) and "score twice and average" costs pennies live.

**Bands (fixed):** within each A set, rank calls by averaged P9 (most
negative first; ties by the seeded rule, seed 11) and cut into fifths.

| band | trim size |
|---|---|
| most negative fifth | 5 points |
| next fifth | 2.5 points |
| remaining three fifths | 0 |

Report, pooled and per draw, for both destinations:

1. **Value per point moved, by band** (all five fifths, not only the two
   that trade), with ranges. This is the clearest form of the question:
   is the per-point value in the worst fifth larger than in the next, and
   that larger than in the rest?
2. **Sized total**: mean value per flagged call under the 5 / 2.5 / 0
   sizing, and its control: each call's quarter-matched per-point value
   times the same size. **Sized A − B**, with range.
3. Sized A − B **per point moved in total**, set beside Step 1's A − B per
   point, so the two are comparable.

**Note for the wrap-up, not a change to the sizes.** The settled allocator
moves one position at most 2.5 points per session. A 5-point trim would
execute over two monthly sessions, and its second half would see one more
month of price. Say this where the P9 result is reported.

## Step 3 — the guidance-veto layer (reported only)

Remove calls tagged beat-and-raise from A. Report n removed per draw,
the veto'd A mean, its A − B, and the mean per-trim value **of the
removed calls alone**. The veto was found after the fact (15 calls on
the original count) and **cannot pass the reading by itself.**

---

## Pre-registered reading (fixed now)

Applied to the **pooled** rows of Step 1, fixed 2.5-point trims:

- **The analyst pays** if **A − B has its range above zero for QQQ and
  for SPY.** If it holds for one destination only, say "the analyst pays
  against [that index] only," and say which.
- **The index does the work** if A's own range is above zero but A − B's
  range includes zero. The flags add nothing beyond a trim of a random
  name at the same time.
- **Protection does not pay** if A's own range includes or is below zero.
  The allocator rebuild does not proceed on B's trims.

**The P9 layer adds value** if sized A − B per point moved is above Step
1's A − B per point, **and** the worst fifth's per-point value is above
the next fifth's, which is above the rest's. Report whether each part
holds. This cannot change the Step 1 verdict.

**The veto** is reported only.

**Say plainly what this cannot show.** It is train data, already seen.
Trims are measured one at a time. It says nothing about a book's
drawdown, turnover, taxes, or what happens when many names are flagged
in the same month. That is the book test, which comes next.

---

## Report step

`wrap-ups/per-trim-value-out.md`, `.md` only. Open with:

> Over the ___ calls B flagged on train (pooled over both draws), moving
> 2.5 points of the book into QQQ made ___ points per trim ($___ on
> $100,000); a trim of a random name in the same quarter made ___. The
> analyst's contribution is ___ points per trim (range ___ to ___).
> Into SPY: ___ against ___, contribution ___ (range ___ to ___). Under
> the reading fixed before the run: **[the analyst pays / pays against
> ___ only / the index does the work / protection does not pay]**. The
> best 10% of trims supplied ___% of the total; the worst 10% cost ___%.
> Sized by P9 severity, the contribution per point moved is ___ against
> ___ unsized: **[adds value / does not]**.

Then: a table for Step 1 (rows: A, B matched, B unmatched, A − B;
columns: draw 1, draw 2, pooled; one table per destination), the tail
breakdown, the Step 2 per-band table, Step 3, and deviations.

**Close with what it means, both ways**, in plain words: which result
sends the book test ahead with B's trims, which sends the sleeve/index
decision ahead with "index by default, flags optional," and which stops
the rebuild on B's trims.

Plain-language discipline is binding (project instructions). Anchor
every percentage to what it is a percentage of.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Finish with `git push`** of `sweep/db-corpus-baseline` after the
wrap-up commit, and report the pushed hash. If the push fails, say so and
never force.
