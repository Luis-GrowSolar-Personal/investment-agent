# Value attribution v2 — Stage B: uncertainty and the gate's baseline

**Scope boundary: report, do not decide.**

**Run ID:** `value-attribution-and-headroom-v2` (continuation of Stage A, not a
new run). **Result:** Stage B (B0–B4) ran to completion. Stages C, D, E remain
**pending**, unchanged from Stage A's wrap-up.

---

## Lead-with summary

On the scorer's population of **359** calls across **16** tickers (thin-year
filtered; 362 before filtering), v6-era scores hit **40.4%**, against an
always-bullish baseline of **46.2%** (lift **−5.8pp**, 95% CI **−9.55 to
−1.98**) and an always-hold baseline of **11.7%** (lift **+28.7pp**, 95% CI
**+18.66 to +38.69**). The bearish base rate is **42.1%**, against
bearish-**outcome** accuracy (recall on true bearish outcomes) of **13.9%** —
a different quantity from bearish-**prediction** precision, which is 47.7%
(see B2, and the correction in B4b). On §3.1's specified baseline
(always-hold) the lift is **positive**, and its interval **does not** span
zero on the scorer population.

**Flagged prominently, not in a footnote, per the prompt's own instruction:**
on the **simulator's** 195-event population, the always-bullish-lift 95% CI
is **[−9.72, +0.62]pp — it spans zero.** McNemar on that same comparison
(simulator population vs. always-bullish) returns p=0.1755, not significant.
This means the gate's always-bullish-relative verdict on the *simulator's*
narrower population cannot currently distinguish this scorer from a fair
coin. The scorer population's always-bullish CI does **not** span zero
([−9.55, −1.98]pp) — the two populations disagree on statistical
significance, not only on point estimate. This applies retroactively: any
past argument (including the v10+auto1 discussion) that treated a
point-estimate lift as decisive did so without an interval, and the interval
matters.

**A second contradiction, stated as the prompt requires:** the prompt's own
Sec6 expectation was an always-hold lift near **+6.7pp**. Measured: **+28.7pp**
— more than four times larger. This is a finding, not a failure: it happened
because the bearish base rate (42.1%) is roughly double the ~20% the
expectation assumed, which mechanically shrinks the always-hold baseline
(11.7%, not ~33.7%) and inflates the lift against it.

---

## B0 — population reconciliation

| | Scorer population | Simulator population |
|---|---|---|
| Definition | Every ALL16, price-scoreable Analysis row; no createdAt restriction, no call-date ceiling, no dedup | `sweep_cadence_and_session_model.load_events_dedup_on()`: ALL16, call_date ≤ 2024-06-12, `Analysis.createdAt` inside the v6 window (2026-05-02 12:33:23-04 to 2026-06-27 16:26:16-04), same-day-deduped |
| n | 362 (359 thin-year-filtered) | 195 |
| Relationship | Superset | **Strict subset** — all 195 simulator events matched a scorer row by (ticker, call_date); 0 unmatched |

`<362, 359, 195, 0>` — `analysis/data/value_attribution_v2/stage_b_manifest.json` → `results.B0` (counts, not a draw).

**Per-year table** (scorer_n / simulator_n):

| year | scorer n | simulator n |
|---|---|---|
| 2020 | 3 | 3 |
| 2021 | 45 | 45 |
| 2022 | 56 | 56 |
| 2023 | 60 | 60 |
| 2024 | 84 | 31 |
| 2025 | 114 | 0 |

**Premise correction (flagged, not silently worked around).** Stage A's
`next_action` described the scorer/simulator gap as two axes: same-day dedup
and a narrower call-date window. Verified against
`analysis/simulator/data.py`'s `load_call_events()`: there is a **third**
restriction, `analysis_created_after`/`analysis_created_before` (the v6
createdAt window), which is also load-bearing — it is the same window the
09-13 handoff's §1 already flagged as "unverified." The three-axis picture,
not two, is the correct one. Because the simulator population turns out to
be a strict subset (not a partially-overlapping set), the reconciliation is
simpler in practice than the "residual, if any" language in the prompt
anticipated: there is no residual — every 2024–2025 gap is explained
entirely by the call-date ceiling, and the 2020–2023 agreement is exact
(dedup removed nothing across ALL16 in these years, given zero unmatched
keys overall).

---

## B1 — lift against both baselines

**No number below appears as a bare "lift" — every figure names its baseline
and its population.**

### Scorer population, by year (n, thin years flagged)

| year | n | hit rate | always-bullish baseline | always-bullish lift | always-hold baseline | always-hold lift |
|---|---|---|---|---|---|---|
| 2020 (thin, n<20) | 3 | 33.3% | 33.3% | 0.0pp | 66.7% | −33.3pp |
| 2021 | 45 | 55.6% | 51.1% | +4.4pp | 8.9% | +46.7pp |
| 2022 | 56 | 26.8% | 32.1% | −5.4pp | 23.2% | +3.6pp |
| 2023 | 60 | 38.3% | 41.7% | −3.3pp | 8.3% | +30.0pp |
| 2024 | 84 | 29.8% | 39.3% | −9.5pp | 17.9% | +11.9pp |
| 2025 | 114 | 50.0% | 58.8% | −8.8pp | 4.4% | +45.6pp |

Per-year figures — `stage_b_manifest.json` → `results.B1.scorer_population_by_year`.

**Scorer population aggregate (n=359, thin-filtered):**

| baseline | baseline rate | our hit rate | lift |
|---|---|---|---|
| always-bullish | 46.2% | 40.4% | **−5.8pp** |
| always-hold | 11.7% | 40.4% | **+28.7pp** |

`stage_b_manifest.json` → `results.B1.scorer_population_aggregate_thin_filtered_n359` (all counts, not draws).

**Reproduction cross-check: PASSED.** The always-bullish aggregate
(46.2% / 40.4% / −5.8pp, n=359) reproduces
`wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`'s published figures
exactly. `stage_b_manifest.json` → `results.B1.test2_reproduction_check.reproduces` = `true`.

**Simulator population aggregate (n=195):**

| baseline | baseline rate | our hit rate | lift |
|---|---|---|---|
| always-bullish | 42.6% | 37.9% | **−4.6pp** |
| always-hold | 13.8% | 37.9% | **+24.1pp** |

`stage_b_manifest.json` → `results.B1.simulator_population_aggregate_n195`.

**Expectation check (diagnostic, not a gate):** the prompt's stated
expectation was always-hold lift near +6.7pp. Measured: **+28.7pp** on the
scorer population, **+24.1pp** on the simulator population. **Contradicted
on both populations** — reported as a finding per the prompt's own rule.

---

## B2 — ground-truth distribution

**Scorer population aggregate (n=359):**

| class | ground-truth count | ground-truth share | predicted count | precision (of predictions in this class) |
|---|---|---|---|---|
| bullish | 166 | 46.2% | 251 | 48.2% |
| bearish | 151 | 42.1% | 44 | 47.7% |
| neutral | 42 | 11.7% | 64 | 4.7% |

`stage_b_manifest.json` → `results.B2.scorer_population_aggregate_n359`.

**The bearish base rate is 42.1%**, not the ~20% the prompt's B1 expectation
assumed — this is the mechanical cause of the always-hold-lift contradiction
above (a higher bearish base rate pushes the always-hold baseline down,
which inflates lift against it).

**Neutral precision is mechanically low (4.7%)** with three classes and a
non-neutral-skewed tape (88.3% of outcomes are bullish or bearish) — visible
directly in the base-rate column next to it, per the prompt's instruction,
rather than asserted.

**Two different "bearish accuracy" quantities — do not conflate them
(finding surfaced mid-run, corrected in B4b):**
- **Bearish-prediction precision** (of predictions labeled bearish, how many
  were right): **47.7%**, n=44.
- **Bearish-outcome recall** (of calls that actually turned out bearish, how
  many did v6 flag as bearish): **13.9% aggregate**, n=151. By year: 2021
  11.1% (n=18), 2022 24.0% (n=25), 2023 16.7% (n=30), 2024 8.3% (n=36), 2025
  11.9% (n=42) — this reproduces
  `wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`'s cited 8.3%–24.0%
  range exactly.

The 09-13 handoff's §1 "wrong roughly four times in five" language described
the second quantity (recall) using precision-shaped wording ("when v6 says
trim"). Corrected in B4b below: the number the handoff actually cited
(recall) is **13.9% right → 86.1% wrong**, worse than "four times in five"
(80% wrong), not better.

---

## B3 — intervals

**McNemar (exact binomial on discordant pairs, two-sided, α=0.05):**

| comparison | b | c | n discordant | p |
|---|---|---|---|---|
| scorer pop vs always-bullish | 24 | 45 | 69 | 0.0154 |
| scorer pop vs always-hold | 142 | 39 | 181 | <0.0001 |
| simulator pop vs always-bullish | 13 | 22 | 35 | **0.1755** |
| simulator pop vs always-hold | 74 | 27 | 101 | <0.0001 |

`stage_b_manifest.json` → `results.B3.mcnemar`. b = analyst right/baseline
wrong; c = analyst wrong/baseline right. b<c in every row against
always-bullish (the analyst loses more disagreements to the bullish coin
than it wins) and b>c against always-hold (opposite pattern).

**Ticker-block bootstrap** (resample unit: ticker, 2000 resamples, fixed seed
20260913, **16 independent blocks** — noted per the prompt's instruction so
the interval width relative to n is legible):

| population | metric | 95% CI |
|---|---|---|
| scorer (n=359) | always-bullish lift | [−9.55, −1.98]pp — does not span zero |
| scorer (n=359) | always-hold lift | [+18.66, +38.69]pp — does not span zero |
| scorer (n=359) | overall hit rate | [33.1%, 48.1%] |
| scorer (n=359) | bearish-call (prediction) accuracy | [33.3%, 66.7%] |
| simulator (n=195) | always-bullish lift | **[−9.72, +0.62]pp — SPANS ZERO** |
| simulator (n=195) | always-hold lift | [+12.29, +34.92]pp — does not span zero |
| simulator (n=195) | overall hit rate | [30.1%, 46.0%] |
| simulator (n=195) | bearish-call (prediction) accuracy | [30.4%, 64.5%] |

`stage_b_manifest.json` → `results.B3.bootstrap`.

**The single most consequential finding in this stage:** the simulator
population's always-bullish-lift interval spans zero, consistent with its
McNemar p=0.1755. On the population that matters for dollar comparisons
(Stage A's Arm 0/0b ran on this same 195-event population), the gate's
always-bullish-relative verdict is **not statistically distinguishable from
a coin flip** at this sample size. The scorer's larger 359-row population
does not have this problem for either baseline.

---

## B4 — documentation edits made

Three edits, authorized only here, committed as `0462ae0`
(`docs: value-attribution-v2 Stage B -- record F1/F2/Arm-0 in gate, correct bearish-accuracy language`):

1. **`docs/architecture/PROMOTION_GATE.md` §10** — added F1 (baseline
   divergence, both baselines' measured figures and both populations' CIs),
   F2 (benchmark divergence — sized, not resolved: 10/16 ALL16 tickers sit in
   a Tier 1 sector-ETF domain per `docs/architecture/DOMAIN.md`), and the
   Arm 0 ≤ control finding ($173,102.24 vs $179,944.91) with citations.
2. **`docs/handoffs/2026-09-13-analyst-value-question.md` §1** — corrected
   "wrong roughly four times in five" to state the measured bearish-outcome
   recall (13.9% aggregate → wrong 86.1% of the time) and to flag that the
   original phrasing conflated recall with precision. Not softened — the
   corrected number is worse than the original claim, not better. Nothing
   else in the document was touched.
3. **`analysis/analyst_direct_scorer.py`** — comment block at the
   `always_bullish_hit` computation (now at the assignment inside
   `score_eval_dir`) recording the F1 divergence and pointing at
   `PROMOTION_GATE.md` §10. **No behavior change** — the baseline
   implementation is unchanged; adopting an always-hold baseline is Luis's
   decision, not this run's.

Driver commit for B0–B3: `9646e13` (driver + pre-registration extension),
results commit `aa8bae3`. Doc-edit commit: `0462ae0`.

---

## Resume status

Stage A (`stage_a_arm_0b`, `stage_a_arm_0`) left `done`, unmodified. Stage B
(`stage_b_uncertainty`) is now `done`. `prompt_sha256_stage_b` recorded
alongside the original `prompt_sha256` in `progress.json`, per the prompt's
explicit resume-protocol waiver — Stage A's state was not archived or
cleared. `cells.jsonl` and `findings.md` were appended, never rewritten.
Stages C (contribution), D (headroom/oracle ceiling), E (deliverable table)
remain `pending`, unstarted, per this stage's own scope boundary — Stage B
does not decide contribution or headroom.

---

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on
  `analysis/value_attribution_v2_stage_b_driver.py` and (after B4c's edit)
  `analysis/analyst_direct_scorer.py` — both passed.
- `python3 -c "import json; json.load(...)"` on `PREREGISTRATION.json` and
  `progress.json` after each edit — both passed.
- The driver's own `git_dirty` check printed `False` at run time (tree was
  stashed clean before the driver was committed and before it ran).
- B1's always-bullish aggregate reproduces Test 2's published −5.8pp exactly
  (`results.B1.test2_reproduction_check.reproduces = true`) — the required
  cross-check, and it passed, so B1 was not stopped.
- B2's bearish-outcome recall by year (11.1/24.0/16.7/8.3/11.9%) reproduces
  `wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`'s cited 8.3%–24.0% range
  exactly, cross-validating both the corpus and the scoring logic
  independently of the B1 cross-check.
- `git rev-parse HEAD` inside the driver matches the manifest's recorded
  commit; `git ls-tree` confirms the driver file is present at that commit.

---

## Deviations from the prompt, and why

- **B0's "residual, if any" turned out to be zero, not a partial overlap.**
  The prompt anticipated needing to explain a residual after accounting for
  dedup and window differences. The actual relationship is a clean strict
  subset (195 of 195 simulator events match a scorer row); the reconciliation
  table is simpler than the prompt's framing implied. Reported as found, not
  forced to look more complicated.
- **A third restriction axis, not two, drives the scorer/simulator gap.**
  Stage A's `next_action` named same-day dedup and the call-date window.
  Verified against `analysis/simulator/data.py`: `load_call_events()`'s
  `analysis_created_after`/`analysis_created_before` defaults (the v6
  createdAt window) are a third, independently load-bearing restriction.
  Flagged in B0 rather than silently omitted.
- **Two distinct "bearish accuracy" quantities were in circulation and not
  distinguished in the launch prompt.** The prompt's B2 instruction ("report
  bearish-call accuracy beside the bearish base rate") is satisfied literally
  by bearish-prediction precision (47.7%), but the 09-13 handoff's language
  Step B4b is supposed to correct is actually about bearish-*outcome* recall
  (13.9%). Both are reported; the correction targets the quantity the
  handoff actually cited, confirmed by reproducing its per-year figures
  exactly.
- Line numbers in `analyst_direct_scorer.py` shifted after the B4c comment
  insertion (the prompt cited "lines ~18, ~207" for the original file; the
  comment now sits at the `always_bullish_hit` assignment inside
  `score_eval_dir`, verified by re-grep after editing, not by line number).

## What was deliberately not done

- F2 was not resolved — no TAN/SOXX prices fetched, no re-grading. Only its
  likely size was measured (Tier 1 domain share), per the prompt's explicit
  ground rule.
- The AMD tier-classification defect and the `type_classifications.json`-unread
  defect were not touched and nothing was gated on either.
- No new baseline was implemented in `analyst_direct_scorer.py` — B4c is
  comment-only.
- Stages C, D, E — contribution, headroom, the oracle-ceiling arm, the
  deliverable table — remain entirely unstarted. This wrap-up does not use
  the word "headroom" as a decided quantity anywhere above; where it appears
  it names a field in existing (Test-2-era) data, not a Stage-B computation.

## Limitations (stated, not argued past)

- Every figure above describes `corpus_2026-04-06_to_2026-05-10`, this
  16-ticker universe, this window. Test 5 (per the launch prompt) put Arm A
  at the 100th percentile of 25 random universe draws — this universe is not
  representative, and nothing here changes that.
- The scorer's 362-row population is a score stream of **unverified prompt
  vintage** relative to the simulator's population: 362 − 195 = 167 rows
  (46%) fall outside the `analysis_created_after`/`analysis_created_before`
  v6 window the simulator enforces. The `2026-05-02 12:33:23-04` split
  comparison referenced in the 09-13 handoff is still unrun — B0 measured the
  *size* of this gap but did not verify which of the 362 rows are true v6
  scores versus a different prompt vintage beyond what the simulator's window
  already excludes.
- F2 (sector-ETF benchmarking) is unresolved — every figure in this report is
  SPY-benchmarked, which §3.1 does not specify for Tier 1 tickers.
- Stage B says nothing about contribution or headroom. Stages C, D, E remain
  pending and are where the layer-attribution question is answered.

## Exact follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git checkout sweep/db-corpus-baseline
cat analysis/data/run_state/value-attribution-and-headroom-v2/progress.json
python3 analysis/value_attribution_v2_stage_b_driver.py   # re-run Stage B idempotently;
                                                           # re-appends to cells.jsonl --
                                                           # dedupe on config_hash if
                                                           # re-running for a fresh result
```

To resume this run and start Stage C: read this file and `progress.json`'s
`next_action`, add Stage C's arm/ablation definitions to
`PREREGISTRATION.json` before computing anything (per the standing
pre-registration rule), and note that Stage C is scoped to answer
contribution — which this stage explicitly did not.
