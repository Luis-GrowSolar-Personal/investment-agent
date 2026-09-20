# Ask it twice — does a repeated bearish call predict worse money, not just better accuracy?

**Run ID:** `repeat-the-bearish-call`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/repeat-the-bearish-call-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $14.** 187 calls re-scored twice
at the batch rate ($0.0380/call measured). **Hard cap $20.** Money commits at
batch submission; the cap is checked before `create()`.

**Read first:** `wrap-ups/confirmation-rule-test-out.md` (the money result
this run exists to revisit, and the Paramount defect),
`wrap-ups/q2-bearish-strength-separation-out.md` (six failed attempts at the
same question, from a different angle),
`wrap-ups/R4b-tradeable-entry-out.md` (the entry-price rule),
`wrap-ups/test4-noise-floor-v6-rerun-out.md` (the analyst's run-to-run
instability), and `docs/handoffs/2026-09-19-state-of-play.md` §0.

---

## 1. What this run is for, and why it measures money

**The problem with everything measured so far.** Almost every test in this
project reports whether the analyst was *right* — a call counted as a hit if
the stock moved more than 5% the way it said. Money was measured **once**, and
the answer was **zero**: selling the day after a bearish call, from a price you
could actually trade at, returned the same as holding (0.0%, range −8.7 to
+8.7, once the corrupt Paramount series was removed).

Those two things come apart because a hit counts a stock that drifted down 6%
identically to one that collapsed 60%, and counts a miss identically whether
the stock rose 6% or 60%. **An accuracy improvement is therefore not evidence
of a money improvement, and this project has been optimising the wrong
quantity.**

**The one lead worth spending on.** The analyst does not reproduce itself: on
the same transcript, two runs of the same prompt disagree on about 13% of
calls. On a 48-call sample where the analyst was run five times, calls where
every run agreed were right 50% of the time and calls where the runs split
were right 25% of the time. **That is a lead and not a finding** — 12 calls in
the disagreement group, drawn from a 15-ticker technology and solar universe
that is not this corpus, and found by inspecting existing data rather than by
a declared test. On the money question the same sample offered **two**
unanimous bearish calls, averaging −56%. **Two. That is not evidence of
anything and must not be repeated as though it were.**

**So: ask the analyst again, on the calls it already called bearish, and look
at what happened to the money.**

**Why only the bearish calls.** The tail lives there — the worst quarter of
bearish calls averaged about −51% against the market. Re-scoring the whole
corpus would cost $94 and answer a broader question nobody needs yet. 187
calls twice is $14.

**What this run is NOT.** Not a prompt candidate — the prompt text does not
change. Not a promotion. It does not touch the allocator, the trend layer, the
ledger, or the holdout. It reports and stops.

## 2. Ground rules

1. **The prompt text is unchanged v6.** This is the *same* prompt run again,
   not a candidate. Guard every request against the **promoted v6 hash**. Do
   not register a candidate; there isn't one.
2. **Same model as every baseline: `claude-sonnet-4-6`, pinned.** If it is
   unavailable, **stop and report** — do not substitute. The entire run
   compares the analyst against itself, so the model must match.
3. **Scope: only the 187 calls where v6's cached call was bearish**
   (`per_call_rec` maps to Trim or Exit). Re-derive that list; do not copy it.
4. **Two extra runs per call.** With the cached original that gives three
   independent readings. 374 requests. **Count before `create()`; over 400 →
   stop and report.**
5. **`PARA` is excluded from this project** (corrupt price series, decided
   2026-09-20). **`WOLF` and `SPWR` remain excluded.** Re-derive the bearish
   list after exclusions and report the count — it will be **below 187**,
   which was the pre-exclusion figure.
6. **Price cache `analysis/data/corpus_v2/scorer_price_cache_v1.json`.** Never
   `analysis/data/price_cache.json`.
7. **Resolve symbols through `TICKER_ALIASES.json`** (`ANTM`→`ELV`,
   `GOOGL`→`GOOG`).
8. **Tradeable entry: the close of the first trading day STRICTLY AFTER the
   call date**, for every return. Using the call-date close credits the
   strategy with an announcement move nobody can trade.
9. **No DB writes, no cache refresh, no trend layer, no `final_action`.**
10. **Do not modify `analysis/analyst_direct_scorer.py`.**
11. **macOS Tahoe, zsh.** `python3`. No `--break-system-packages`. No `apt`.
12. **A result that contradicts an expectation here is a finding.**

## 3. Steps −1 and 0

State in `analysis/data/run_state/repeat-the-bearish-call/`. `progress.json`
written first, and **the batch id committed the instant `create()` returns**,
before polling — results persist 29 days and the id is the recovery key.
`scores.jsonl` keyed by `custom_id`, skipping ids already present.
`findings.md` append-only, carrying §5's pre-registration **before any outcome
is computed**. Clean tree, hard stop on `git_dirty`. Driver
`analysis/repeat_bearish_driver.py` committed as its own commit before output.
Version guard against the promoted v6 hash, recorded.

## 4. The work

### 4a. Build the groups

Each call now has three readings: the cached original (bearish by
construction) plus two fresh ones. Group by how many of the three are bearish:

| group | meaning |
|---|---|
| **3 of 3** | it said bearish every time |
| **2 of 3** | it repeated once |
| **1 of 3** | neither re-run agreed |

**Expected split, so you can tell if something is wrong.** v6's measured
pairwise disagreement is 12.8%, so roughly 87% of re-runs should come back
bearish, putting about three-quarters in the 3-of-3 group and about a quarter
across the other two. **If almost everything lands in 3 of 3, or almost
nothing does, stop and check the driver before computing outcomes** — the most
likely cause is caching or a temperature setting, not a discovery.

### 4b. Measure money first, accuracy second

For each group, each split (train, tune) and pooled, on the 182-day
benchmark-relative return from a tradeable entry:

**Primary — the tail.** The share of calls that lagged the S&P by more than
**25%**. This is the question the whole exercise is for: does repeating the
call pick out the disasters?

**Secondary.** The average of the worst quarter of each group. The median. The
mean. The single worst call.

**Tertiary, reported but not the point.** Accuracy — the share that lagged by
more than 5% — so the result can be compared with the earlier work, and so we
can see whether money and accuracy move together or apart **in this run too**.

**Every figure with a 95% range from a ticker-block bootstrap** (resample
whole companies, seed recorded), and **the number of distinct companies each
group rests on**. The disaster work found the tail concentrated in a handful
of names; a group resting on four companies is a description of those
companies.

**And the decision quantity, stated in money:** for each group, what selling
the day after the call would have saved against holding, with a paired range.

### 4c. The concentration check

Recompute the primary result with each of the largest contributing companies
dropped in turn. **If dropping one company moves the answer materially, say so
in the headline.**

## 5. Pre-registration — write to `findings.md` and commit BEFORE any outcome

Three groups × two splits × several money measures is enough to find a
flattering cut. **Predictions committed first; every group and measure
reported; train discovers, tune confirms.** A pattern on train that does not
appear on tune has not been shown.

**Registered predictions, 2026-09-20:**

- **Primary.** The 3-of-3 group has a higher share of calls lagging by more
  than 25% than the 1-of-3 group. Direction predicted; size not.
- **The money gap will be larger than the accuracy gap.** If repetition is
  picking out conviction, it should show up more in how far the losers fell
  than in how often the call was technically right.
- **Falsified if** the 3-of-3 group's tail share is at or below the 1-of-3
  group's, on either split. **Then repetition carries no information about
  money, the lead is closed, and the $14 has bought a clean retirement of
  it.**
- **Also falsified in practice if** the groups' ranges overlap so heavily that
  no group can be told from the whole. Say that plainly rather than reporting
  a point estimate as though it decided something.
- **Not predicted, reported either way:** whether the accuracy result from the
  48-call sample (50% unanimous against 25% split) reproduces here. That
  sample was a different universe and may not transfer.

## 6. Report step

**Scope boundary: report, do not decide.** Do not change the exit ratchet, any
allocator or sizing rule, or the candidate queue. Do not propose a prompt
candidate.

Write `wrap-ups/repeat-the-bearish-call-out.md`, three forms (`.md`, `.docx`
with real Word tables, published artifact page). **Open with §0, defined
terms** — at minimum: bearish call, tradeable entry, benchmark-relative
return, the three groups, tail, worst quartile, accuracy versus money,
ticker-block bootstrap.

Open the body with this sentence, filled in:

> The analyst was asked twice more about the ___ calls it had already called
> bearish. It repeated the call both times on ___ of them, once on ___, and
> not at all on ___. Of the calls it repeated every time, ___% went on to lag
> the S&P by more than 25%, against ___% of the calls it did not repeat. The
> worst quarter of the repeated group averaged ___% against ___% for the
> rest. Selling the day after a repeated bearish call would have saved ___%
> against holding; for an unrepeated one, ___%.

Then the group table for money, the same for accuracy, the concentration
check, and one plain paragraph per finding.

**Close with what Luis would do differently, three ways.** If repetition picks
out the tail: what a rule that acts only on repeated bearish calls would look
like, what it would cost to run in production (the analyst must be called
twice), and what would have to be true before trusting it. If it does not: say
plainly that the lead is closed and that the bearish signal cannot be graded
by asking again. If the ranges are too wide to tell: say how many calls would
be needed to tell, so the next decision is informed rather than repeated.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of — not "24% tail rate" but "12 of the 50 repeated calls fell
more than 25% behind the market." Write "points," never "pp." Short sentences,
one idea each. Lead with the finding. **Luis is an experienced investor and
not a statistician; an explanation that needs a statistics background is a
failed explanation.**

## 7. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. Work on
`sweep/db-corpus-baseline`. Provenance for every figure — file path plus key
or column. Never quote a figure from this prompt as a result; re-derive it.
One prompt in, one wrap-up out. Commit the driver, the scores and the outputs.
**Running low on budget is a reason to stop cleanly, not to rush** — one extra
run per call instead of two still answers a weaker version of the question,
and a partial run that says so is worth more than a complete one that hides
it.
