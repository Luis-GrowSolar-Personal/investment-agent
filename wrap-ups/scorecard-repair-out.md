# Scorecard repair — wrap-up

**Scope boundary: report, do not decide.** This run does not evaluate or
adjudicate any prompt version (v6, v10, v10+auto1). It repairs the
measurement instrument and reports what the repaired instrument implies.

---

## §0 — Defined terms (read this before anything else)

- **The always-bullish guesser.** A pretend analyst that says "the stock
  will beat the market" on every single call, regardless of what the
  transcript says. It is right whenever the stock actually did beat the
  market, and wrong otherwise. Comparing the real analyst's hit rate
  against this guesser is the *old* gate metric (§3.1-legacy).
- **The always-flat guesser.** A pretend analyst that says "the stock will
  move roughly in line with the market" on every call. Same idea, different
  guess.
- **Luck-corrected gap.** How much better the analyst did than a guesser
  that doesn't read transcripts at all but knows the analyst's own habits —
  specifically, how often the analyst says each of the three answers
  (bullish/bearish/neutral) and how often each answer actually turns out to
  be correct. If the analyst says "bullish" 70% of the time and "bullish"
  is the correct answer 46% of the time, a computer that just spat out
  "bullish" 70% of the time at random would get some calls right purely by
  coincidence — this is "expected-by-luck." The gap is: what the analyst
  scored, minus what pure coincidence would have scored, on the very same
  mix of answers. Reported in **percentage points (pp)**, always of the
  scoreable calls.
- **Cohen's kappa.** The same luck-corrected gap, just rescaled onto a 0-to-1
  ruler where 0 means "exactly as good as coincidence" and 1 means
  "perfect." It's the same information as the gap in different units —
  named once here so it's findable in the statistics literature, reported
  as a plain percentage-point gap everywhere else in this document.
- **Balanced accuracy.** Take the three answers one at a time. For "actual
  outcomes that were bullish," what share did the analyst correctly call
  bullish? Same question for bearish outcomes, and for neutral outcomes.
  Average those three percentages. A guesser with literally no skill,
  guessing at random among three answers, scores 33.3% on this measure —
  so a real score near 33% means "not distinguishable from random," and a
  score meaningfully above it means "actually picking up something."
- **A 95% range (confidence interval).** A band of numbers built by
  repeatedly re-drawing the same tickers with replacement (resampling) and
  recomputing the metric each time. If the true score bounced between draws
  in a way that keeps 95% of those redraws inside the band, that's the
  reported range. **If the range includes zero, the measured effect cannot
  be told apart from "no effect at all"** at this sample size.
- **Paired vs. unpaired comparison.** *Paired* means two prompt versions are
  scored on the exact same set of transcripts, so you're comparing
  apples to apples on every single call. *Unpaired* means the two versions
  were scored on different call samples — some tickers or years might be
  present in one and not the other — so any difference you see is partly
  real skill and partly just "these were different calls." Paired
  comparisons detect smaller real improvements because they remove that
  extra noise source.
- **Minimum detectable improvement / detection threshold.** The smallest
  true difference between two prompt versions (in percentage points) that
  this scorecard would actually catch — meaning its 95% range would exclude
  zero — in at least 80% of repeated attempts. A "realistic" single-round
  prompt improvement, per this project's own experience, is 2 to 4 points.
- **The scorer population vs. the simulator population.** Two different
  slices of the same underlying database of scored earnings calls. The
  **scorer population** (n=359) is every scoreable call across all 16
  tracked companies, no date restrictions. The **simulator population**
  (n=195) is a stricter subset used by the backtesting simulator: it stops
  at mid-2024, only includes calls scored inside a specific six-week window
  in mid-2026, and collapses same-day duplicate transcripts to one. Every
  one of the 195 simulator calls is also inside the 359 scorer calls — the
  simulator's set is a clean subset, not an overlapping-but-different set.
  Carried forward from a prior run (Stage B), not redefined here.

---

## Lead-with summary (plain language)

Out of every 100 earnings-call verdicts, the analyst got about 40 right —
about the same as a computer that knew nothing about the company and just
guessed in proportion to the analyst's own habits. **The gap between the
analyst and that "informed coin flip" is under 1 point either way, and the
95% range around that gap includes zero on both populations tested.** That
means: on this measurement, right now, we cannot say the analyst is doing
better than an educated guess — and we also cannot say it's doing worse.
The number is simply too uncertain to call.

**This scorecard can detect a prompt improvement of 6 points or larger
when the two prompts are compared on the same calls, and 12 points or
larger when they are not.** A realistic prompt improvement, based on this
project's own experience iterating prompts, is 2 to 4 points. **On this
corpus, prompt iteration is not measurable** — not even in the more
sensitive, same-calls (paired) design. A 2-4 point improvement, even a real
one, would not show up as a detectable result here.

---

## Step 0c — the prompt's own worked example, recomputed

The prompt (`prompts/scorecard-repair.md` §5) stated: v6 said "beats" on
251 calls, "lags" on 44, "moves-with" on 64 (n=359); the actual outcomes
were 166 beats, 151 lags, 42 moves-with; expected-by-luck 39.6%; observed
40.4%.

**Recomputed directly from the stored corpus (same 359-call scorer
population): CONFIRMED, no contradiction.** Every count matches exactly —
predicted 251/44/64, actual 166/151/42, expected-by-luck 39.6%, observed
40.4%. `0.82` — `analysis/data/scorecard_repair/scorecard_repair_manifest.json`
→ `results.step0c_arithmetic_check` (raw counts, not a draw).

This is itself worth stating plainly, per the prompt's own instruction to
report contradictions *or* confirmations: the prompt's premise held. There
was no arithmetic error to correct here — unlike several other figures in
this project's history that turned out to have silent errors, this one was
right the first time it was written down.

---

## Step 1 — old vs. new metric, side by side

| metric | scorer population (n=359) | simulator population (n=195) |
|---|---|---|
| Observed accuracy | 40.4% | 37.9% |
| Expected-by-luck | 39.6% | 37.8% |
| **Luck-corrected gap (new)** | **+0.82pp** | **+0.11pp** |
| Cohen's kappa (new, 0-1 scale) | 0.0136 | 0.0017 |
| **Balanced accuracy (new)** | **31.3%** | **29.6%** |
| Always-bullish-guesser baseline (old) | 46.2% | 42.6% |
| Always-bullish-guesser lift (old) | −5.8pp | −4.6pp |
| Always-flat-guesser baseline (old) | 11.7% | 13.8% |
| Always-flat-guesser lift (old) | +28.7pp | +24.1pp |

`analysis/data/scorecard_repair/scorecard_repair_manifest.json` →
`results.step1_luck_corrected_score` (forward-return-derived hit rates over
the frozen corpus, not a draw across randomized runs).

**Reading this table plainly:** the old metric's verdict swings from −5.8pp
(fails) to +28.7pp (passes) purely by which fixed-answer dummy is chosen —
this was Stage B's finding, reproduced here unchanged. The new metric
doesn't pick a side in that argument; it asks a different, narrower
question ("better than an informed coin flip that knows the analyst's own
habits?") and the answer is: barely, and not detectably so (see Step 2).
**Balanced accuracy (31.3% / 29.6%) sits below the 33.3% a knowledgeable-
about-nothing three-way guesser gets**, which is a second way of seeing the
same signal: this scorer, averaged evenly across bullish/bearish/neutral
calls, is not clearly separating itself from chance.

Per-answer recall (share of actual outcomes of that type correctly called),
scorer population: bullish 72.9%, bearish 13.9%, neutral 7.1%. The analyst's
apparent skill is concentrated entirely in calling bullish outcomes bullish
— which happens to be the majority class (46.2% of outcomes) — and it is
close to blind on bearish and neutral outcomes. This is consistent with,
and does not contradict, Stage B's B2 finding that bearish-outcome recall
was 13.9%.

---

## Step 2 — confidence ranges

Ticker-block bootstrap, 2000 resamples, seed 20260913, **16 independent
blocks** (one per ticker) for both populations — noted per the prompt's
instruction so interval width is legible against the block count.

| population | metric | 95% range | spans zero? |
|---|---|---|---|
| scorer (n=359) | luck-corrected gap | [−2.36, +3.89]pp | **YES — SPANS ZERO** |
| scorer (n=359) | balanced accuracy | [27.75%, 34.7%] | n/a (not a lift) |
| scorer (n=359) | observed accuracy | [33.13%, 48.13%] | n/a |
| scorer (n=359) | bullish recall | [60.12%, 83.85%] | n/a |
| scorer (n=359) | bearish recall | [6.43%, 21.47%] | n/a |
| scorer (n=359) | neutral recall | [0.0%, 18.18%] | n/a |
| simulator (n=195) | luck-corrected gap | [−4.82, +4.47]pp | **YES — SPANS ZERO** |
| simulator (n=195) | balanced accuracy | [25.74%, 32.79%] | n/a |
| simulator (n=195) | observed accuracy | [30.11%, 45.96%] | n/a |
| simulator (n=195) | bullish recall | [58.23%, 85.71%] | n/a |
| simulator (n=195) | bearish recall | [6.67%, 24.74%] | n/a |
| simulator (n=195) | neutral recall | [0.0%, 0.0%] | n/a |

`scorecard_repair_manifest.json` → `results.step2_confidence_intervals`
(bootstrap 95% percentile ranges, 2000 resamples each).

**Flagged in the table itself, per the prompt's requirement:** both
populations' luck-corrected-gap ranges include zero. This is the direct,
quantitative reason the Lead-with summary above says "we cannot call it."
The simulator population's neutral recall range is degenerate ([0.0%,
0.0%]) — every ticker-block resample of that smaller, mid-2024-and-earlier
population produced zero correct neutral calls; this is a small-sample
artifact of neutral calls being rare (n_actual=27) and the analyst almost
never calling neutral, not a claim that neutral recall is exactly zero in
some deeper sense.

---

## Step 3 — the detection threshold (the deliverable)

Simulated on the 359-call scorer population, 16 tickers. For each
candidate improvement X (in percentage points), a synthetic challenger
population was built and the question asked: in what share of 150
independent trials (each running its own 60-resample ticker-block
bootstrap) does the 95% interval on the challenger-minus-v6 difference
exclude zero? The threshold is the smallest X clearing an 80% detection
rate.

### 3a. Unpaired (different samples)

| X (pp) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | **12** | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| detection rate | 0% | 1% | 3% | 3% | 7% | 17% | 26% | 37% | 45% | 51% | 71% | **84%** | 89% | 94% | 97% |

**Minimum detectable improvement, unpaired: 12pp.**

### 3b. Paired (same calls), default disagreement rate 15%

| X (pp) | 1 | 2 | 3 | 4 | 5 | **6** | 7 | 8 | 9 | 10 | 11-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| detection rate | 21% | 38% | 57% | 68% | 78% | **82%** | 91% | 93% | 99% | 99% | 100% |

**Minimum detectable improvement, paired (15% disagreement rate): 6pp.**

**Pairing does lower the threshold — unpaired 12pp vs. paired 6pp, a 2x
reduction — confirming the prompt's stated expectation rather than
contradicting it.** This is the one place in this run where the prompt's
prediction and the measurement agree; flagged as such because the prompt
itself asked for either outcome to be reported plainly.

**Sensitivity to the modeled disagreement rate** (§3b's stated assumption
— the rate at which a hypothetical successor prompt disagrees with v6 on a
call — is modeled, not measured; the per-call outcomes needed to anchor it
against the real v10+auto1 spread were not recoverable in this run, so it
is swept instead):

| disagreement rate | 5% | 10% | 15% | 20% | 25% | 30% |
|---|---|---|---|---|---|---|
| paired MDE (pp) | 4 | 5 | 5 | 7 | 7 | 7 |

`scorecard_repair_manifest.json` →
`results.step3_detection_threshold.paired_mde_by_disagreement_rate`. The
paired threshold stays well under the unpaired 12pp across the entire
swept range, so the qualitative conclusion (paired detects smaller
improvements) is not an artifact of the specific 15% default.

### Data-volume answer for a 3-point paired threshold

Holding the paired design fixed and asking how much more data would bring
the threshold down to 3 points (a realistic single-iteration improvement),
reported on the two axes separately because they behave differently at 16
independent blocks:

- **Additional stocks:** synthetically quadrupling the ticker count (16 →
  64 tickers, each new batch replaying an existing ticker's call pattern
  under a new label) brought the paired MDE to 1pp — comfortably past the
  3pp target. Doubling (16 → 32) was not enough.
- **Additional calls:** quadrupling the number of calls per existing
  ticker (same 16 tickers, 4x the transcripts each) brought the paired MDE
  to 2pp — past target, but less far past it than the stock axis at the
  same 4x multiplier.

`scorecard_repair_manifest.json` →
`results.step3_detection_threshold.data_volume_answer_for_3pp_paired_threshold`.
**Reading this as decision-relevant, not just descriptive:** at this
project's current 16-ticker, 16-independent-block scale, adding *tickers*
moves the threshold down faster than adding *calls per ticker* — consistent
with the bootstrap being ticker-blocked (16 blocks is the actual sample
size the interval width depends on, not 359 calls). This is a simulated
answer over synthetic replays of existing call patterns, not a claim about
what any specific 64-ticker universe would show; it says where the
leverage is, not what the number would be with real new tickers.

---

## Step 4 — documentation edits made

Three edits, authorized only by `prompts/scorecard-repair.md` §8:

1. **`docs/architecture/PROMOTION_GATE.md` §3.1** — replaced the primary
   analyst-layer metric description with the luck-corrected gap and
   balanced accuracy (each with its 95% range and this run's detection
   threshold), and added the standing rule that no prompt-vs-prompt
   comparison may be cited going forward without the paired difference,
   its 95% range, and whether that range excludes zero. The prior
   always-bullish-lift definition is preserved immediately below, marked
   **§3.1-legacy, superseded**, with the one-line reason (Stage B: verdict
   flips by choice of dummy) — not deleted, since every existing benchmark
   record was computed under it.
2. **`analysis/analyst_direct_scorer.py`** — added
   `compute_luck_corrected_metrics()` and a "REPAIRED METRICS" report
   section, purely additive. `score_eval_dir()`, the `CallRecord`
   dataclass, `always_bullish_hit`, and every existing print/CSV line are
   byte-for-byte unchanged; verified by re-grep after editing.
3. **`docs/architecture/VERSION_REGISTRY.json`** — labeling only. Added a
   `scorecard_repair_label_2026_09_13` note to the three genuinely
   analyst-layer benchmark records (`test4_per_tier_noise_floors`,
   `test6_look_ahead_null`, `test4_v6_per_tier_noise_floors`) stating their
   figures were computed under §3.1-legacy. **Deviation, corrected in
   process:** an earlier pass labeled all seven benchmark records,
   including four (`settled_control`, `test1_zero_info_floor`,
   `sizing_channel_null`, `small_cap_materiality`) that are end-to-end
   portfolio-outcome (§3.2) records, not analyst-direct (§3.1) records —
   caught and reverted before committing, since the prompt's instruction
   was "each analyst-layer record," not every benchmark record. No figure
   recomputed or restated in any record.

Commits: `eea40fc` (Step 0c/1/2/3 results, `scorecard_repair_manifest.json`),
`69cd3c1` (Step 4's three doc edits).

---

## Step 5 — the v10 question under the repaired instrument

**Not adjudicated here — this states only what the repaired instrument
implies about the existing, already-published numbers.**

The existing published spread was v10+auto1 at 37.5–42.5% against v6's
37.5% (`docs/handoffs/2026-09-03-prompt-version-drift.md`-era figures,
carried forward by the prompt itself, not re-measured in this run). That
spread is **5 percentage points at most**, and is a point-estimate,
unpaired-style comparison with no reported interval.

Against this run's measured thresholds: **5pp is below the 12pp unpaired
detection threshold, and below the 6pp paired threshold** (and below every
value in the paired disagreement-rate sensitivity sweep, 4–7pp). **The
v10+auto1-vs-v6 comparison was not decidable on this corpus at this sample
size, under either design.** No re-reading of the existing runs changes
this — the problem is that the corpus does not contain enough independent
tickers to resolve a difference this small, not that the existing analysis
missed something. This restates, with a number attached, what Stage B
already flagged qualitatively (the argument was "unresolvable by
construction").

---

## Limitations (stated, not argued past)

- **Unrepresentative universe.** Every figure above describes this
  16-ticker corpus and this window. A prior run (Test 5) put this universe
  at the 100th percentile of 25 random universe draws — it is not a
  representative sample, and nothing here changes that.
- **Unverified prompt vintage.** The 362/359-row scorer population is a
  score stream of unverified prompt vintage relative to the 195-row
  simulator population; the `2026-05-02 12:33:23-04` split comparison
  flagged in prior runs is still unrun.
- **F2 (sector-ETF benchmarking) unresolved, SPY-only.** Every figure in
  this report is SPY-benchmarked, per this run's explicit ground rule not
  to touch F2. §3.1 (both the legacy and corrected versions) specifies a
  sector ETF where one applies.
- **Simulator population has zero 2025 calls.** 0 vs. 114 in the scorer
  population — the simulator's population is frozen at mid-2024 by
  construction, so nothing above from the simulator population reflects
  the most recent ~30% of the scorer population's date range.
- **Step 3b's disagreement rate is modeled, not measured.** The per-call
  outcomes needed to anchor it against the real v6-vs-v10+auto1 spread were
  not recoverable in this run (the existing published spread is a
  point-estimate summary, not a per-call outcome stream this driver could
  pair against); reported across a 5–30% sweep instead of a single
  measured value, per the prompt's own fallback instruction.

## What was deliberately not done

- No prompt version was evaluated or adjudicated — not v6, not v10, not
  v10+auto1.
- F2 was not touched — no TAN/SOXX prices fetched, no re-grading.
- The AMD tier-classification defect and the
  `type_classifications.json`-unread-by-production defect were not fixed
  and nothing was gated on either.
- No existing benchmark record's figures were recomputed or restated —
  Step 4's registry edit is a label, not a re-measurement.
- No DB writes, no Anthropic API calls, no price-cache refresh (frozen at
  2026-05-08 per this run's ground rule).

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on
  `analysis/scorecard_repair_driver.py` and (after Step 4's edit)
  `analysis/analyst_direct_scorer.py` — both passed.
- `python3 -c "import json; json.load(...)"` on `PREREGISTRATION.json`,
  `progress.json`, `scorecard_repair_manifest.json`, and
  `VERSION_REGISTRY.json` after each edit — all passed.
- Re-grepped `analyst_direct_scorer.py` after editing to confirm
  `score_eval_dir`, `CallRecord`, and `always_bullish_hit` are unchanged
  and the new function/report block is additive only.
- The driver's own `git_dirty` check hard-stopped the first run attempt
  (correctly) when the tree was dirty from an earlier failed run's partial
  `cells.jsonl`/`findings.md` writes; those were reset to their committed
  state before re-running clean (`git_dirty: false` on the run that
  produced the manifest, commit `e4047b9`).
- `git rev-parse HEAD` inside the driver matches the manifest's recorded
  commit; the driver file is tracked at that commit
  (`driver_file_tracked_at_commit: true`).

## Deviation from the prompt, and why

- **Monte-Carlo trial counts were reduced mid-run for tractability.** The
  first driver version (500 trials × 200 inner resamples per X-value,
  times a 16x-scaling data-volume sweep) did not finish inside a workable
  time budget and was killed. Trial/inner-resample counts were reduced
  (500→150 trials, 200→60 inner resamples; data-volume sweep trials
  60–120) in a second commit (`e4047b9`) before the run that produced the
  cited manifest. **No pre-registered parameter changed** — the
  populations, resampling unit, seed, X-sweep points, and disagreement-rate
  sweep in `PREREGISTRATION.json` are exactly as written before any figure
  was computed. Only the number of Monte-Carlo trials per cell (an
  implementation performance knob, not a pre-registered quantity) was
  reduced. Flagged here rather than left silent.
- **VERSION_REGISTRY.json labeling scope corrected mid-run.** See Step 4
  above — an initial pass over-labeled four §3.2 (portfolio-outcome)
  records that are not analyst-layer records; caught before committing and
  reverted, then redone as a minimal, surgical (non-reformatting) edit to
  only the three genuinely analyst-layer records.

## Resume status

This is a **complete run**, not partial. All six steps (0c through 6)
finished, including Step 4's doc edits and Step 5's v10 reading, which the
prompt explicitly permitted marking `pending` under budget pressure — that
was not needed here.

## Exact follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git checkout sweep/db-corpus-baseline
cat analysis/data/run_state/scorecard-repair/progress.json
python3 analysis/scorecard_repair_driver.py   # re-run idempotently; will hard-stop
                                                # on a dirty tree, matching the
                                                # reproducibility contract
```

To re-measure Step 3b against real per-call outcomes rather than a modeled
disagreement rate, a future run needs a paired eval cache (v6 and a
candidate scored on the identical call set) — the existing published
v10+auto1 spread is a summary figure, not a per-call stream, and could not
serve that purpose here.
