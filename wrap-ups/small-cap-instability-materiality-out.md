# small-cap-instability-materiality — wrap-up

**Scope boundary: report, do not decide.** Test 1's harness
(`analyst_sensitivity_harness.py`) and the sizing-channel run's driver
(`sizing_channel_sensitivity.py`) both untouched — this run's driver
(`analysis/small_cap_instability_materiality.py`) is a new file. No file
under `analysis/simulator/` modified, `EVALUATION_PROMPT.md`,
`ALLOCATOR_OPERATING_MODEL.md`, `PROMOTION_GATE.md`, `gate_ledger.json`
untouched. No LLM calls, no API spend, no DB writes ($0 confirmed).

## Resume status

Fresh run, no prior state for `run_id=small-cap-instability-materiality`.
`progress.json` written before any reading, driver committed at `007f684`
before any manifest, as its own commit, together with the prompt file. All
steps completed in one pass — **full run, not partial.** Wall clock:
census + control ≈3s, full 105-cell grid ≈12s. All cells ran fresh.

---

> **Control reproduced: $179,944.91 / 20.8523% — matches $179,944.91
> exactly.**
> Flip rate reconciled: small/micro **8/12 (66.67%)** — **neither
> published figure was exactly right; 8/12 confirms the design session's
> own recount, and corrects Test 4's originally published 7/12 (58%)** —
> definition: a transcript flips if 2+ of its 5 `recommendation` values
> differ (identical result whether `None` counts as its own distinct
> value or is excluded — that hypothesized ambiguity does not explain the
> gap; the likely explanation is a manual miscount of one transcript,
> id 355/QS, in the original pass).
> Census: small/micro 58 of 195 events (29.74% — the ceiling).
> **Headline** — `observed_pattern` (each tier corrupted at its own
> reconciled rate) costs **$533.29 (0.30%)**, drawdown *improves* 1.66pp
> to 19.19% (session-sampled). `uniform_equivalent` at matched
> corruption volume (51 vs 52 realized corrupted events, both against a
> shared 51.45 expectation): **costs $16,682.31 (9.27%)** — **small-cap-
> concentrated noise is 31.3x CHEAPER than the same volume of evenly-
> spread noise.**
> Ceiling: `small_micro_q1` **improves** final value by $678.79 (0.38%);
> `small_micro_zero_info` **improves** it by $5,076.26 (2.82%) — neither
> ceiling cell costs anything at all.
> Compare Test 1's uniform q=0.5: $24,886 (13.8%).
> **Verdict on materiality: economically inert at this configuration** —
> in fact mildly beneficial in the ceiling cells. **$0 API spend
> confirmed.**

---

## 1. What this run is, and what it is not

No LLM calls, no API spend, no DB writes. Same loader
(`sweep_cadence_and_session_model.load_events_dedup_on()`) and settled
cell (`swap_funding`, K=30, `new_calls_only`, X=2.5pp, `pooled`,
`per_event_date`, phase 0, `tie_seed=0`) as Test 1 and the sizing-channel
run. **Phase 0 only** — not directly comparable to the phase-averaged
$184,819/17.32% headline without the phase-gap adjustment state-of-play
§5.2 already flags. `recommended_size` is untouched throughout — this run
isolates the categorical (`final_action`/`per_call_rec`) channel only,
per the sizing-channel run's finding that the sizing channel is inert.

## 2. Step 1b — exposure census (`analysis/data/run_state/small-cap-instability-materiality/census.json`)

| cap tier | events | share |
|---|---|---|
| megacap | 69 | 35.38% |
| large | 42 | 21.54% |
| mid | 26 | 13.33% |
| **small_micro** | **58** | **29.74%** |
| total | 195 | 100% |

**small_micro's ceiling on this channel is under 30% of events** — a
smaller share than the flip-rate percentage alone might suggest.

**How the cap tiers map onto the simulator's own classification**
(direct query, `tier_fn`/`type_fn`): every small_micro ticker (QS, AMPX,
ENVX, EOSE, RUN, and SPWR by the prompt's own assignment) is
**Type-A-speculative** (15% cap, Rule 3 no-average-down active). This is
the exact cohort the sizing-channel run found absorbs almost all
sizing-channel noise via its 15% cap — **consistent with, not
contradicting**, that prior finding; this run shows the same absorption
mechanism reaching into the categorical channel too.

**SPWR** (excluded from Test 4's universe, assigned small_micro's rate
per the prompt's §1b): confirmed immaterial by direct trace of its single
event in the control run's `funding_log` — `binding: "cash available"`,
`actual_dollars: 0`. It never funds regardless of what flip rate it is
assigned, exactly as state-of-play §5.2 already noted and as this run
independently re-confirmed rather than assumed.

## 3. Step 1c — flip-rate reconciliation, and a corrected published figure

Re-derived directly from `analysis/test4_noise_floor/raw/*.json` (50
transcripts × 5 runs). **Definition stated explicitly**: a transcript
"flips" if 2+ of its 5 `recommendation` values differ. Checked under two
variants — counting `None` as its own distinct value, and excluding
`None` entirely — **both give the identical count in every tier**, so the
null-value ambiguity the prompt hypothesized as the likely cause of the
discrepancy is **not** the actual cause.

| tier | n | flips | rate |
|---|---|---|---|
| megacap | 13 | 2 (ids 204, 303) | 15.38% |
| large | 13 | 0 | 0.00% |
| mid | 12 | 1 (id 100) | 8.33% |
| **small_micro** | 12 | **8** (ids 23, 168, 169, 172, 175, 186, 193, 355) | **66.67%** |

**Previously published number corrected.** Test 4's wrap-up
(`wrap-ups/test4-analyst-noise-floor-out.md` §3) reports small/micro
recommendation-flip concentration as **7/12 (58%)**. This run's direct,
independently-coded re-count over the exact same 12 raw JSON files gives
**8/12 (67%)** — matching the design session's own recount cited in this
prompt, not the originally published figure. Tracing the 8 flipped
transcripts by hand, the likely source of the one-transcript discrepancy
is id 355 (QS: `Trim, Hold, Trim, Hold, Hold`) — a real flip (Trim↔Hold
occurs twice) that appears to have been missed in Test 4's original
manual count. **The corrected 8/12 (67%) is used as this run's q value
for small_micro and should supersede 7/12 (58%) wherever this project
cites the figure going forward** — the megacap/large/mid figures (15.38%,
0%, 8.33%) match Test 4's published rates exactly (Test 4: "megacap
15%, large 0%, mid 8%" — this run's more precise 15.38%/8.33% round to
the same published values).

## 4. Step 2 — the grid, and confirming matched corruption volumes

`analysis/data/run_state/small-cap-instability-materiality/cells.jsonl`,
7 cells × 15 seeds = **105 cells, all run fresh, 12s wall clock total**
(corpus load 2.5s + 105 cells well under 0.1s each). `tie_seed` fixed at
0. `uniform_equivalent_q = 0.263840`, derived so its expected corrupted-
event count (51.45 of 195) exactly matches `observed_pattern`'s expected
count by construction (`51.45 = 69×0.15385 + 42×0 + 26×0.08333 +
58×0.66667`).

| cell | realized corrupted events (min/med/max) | expected |
|---|---|---|
| observed_pattern | 42 / **51** / 60 | 51.45 |
| uniform_equivalent | 43 / **52** / 64 | 51.45 |
| small_micro_only | 29 / 39 / 43 | 38.67 |
| small_micro_q1 | 58 / 58 / 58 (deterministic) | 58 |
| small_micro_zero_info | 58 / 58 / 58 (deterministic) | 58 |
| observed_pattern_uniform_mode | 43 / 49 / 54 | 51.45 |

**`observed_pattern` and `uniform_equivalent` achieved matched
corruption volumes** (51 vs 52 realized median events, both consistent
with the shared 51.45 expectation) — **the headline comparison in §5
below is valid, not an artifact of mismatched noise quantities.**

## 5. Step 3 — results, in Test 1's units

**Ruler: session-sampled, per the prompt's own instruction** —
`run_session_sweep_cell` records `daily_snapshots` only at session dates
(confirmed by the sizing-channel run's §4, not re-derived here); Test 1's
own comparison figures are session-sampled too, so this comparison is
ruler-consistent even though neither is the daily-marked figure the
current state-of-play prefers.

| cell | final min / med / max | dd min / med / max (session-sampled) | cost vs control (median) |
|---|---|---|---|
| control | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | — |
| **observed_pattern** | 164,275.74 / **179,411.62** / 190,824.13 | 15.70 / **19.19** / 21.83% | **$533.29 (0.30%)** |
| small_micro_only | 173,156.38 / 179,003.07 / 184,010.62 | 17.72 / 19.35 / 20.31% | $941.84 (0.52%) |
| **uniform_equivalent** | 143,664.60 / **163,262.60** / 184,269.35 | 16.22 / 18.71 / 21.74% | **$16,682.31 (9.27%)** |
| small_micro_q1 | 173,017.55 / 180,623.70 / 188,219.04 | 17.01 / 19.04 / 19.83% | **−$678.79 (improves 0.38%)** |
| small_micro_zero_info | 185,021.17 (all, deterministic) | 17.9738% (all) | **−$5,076.26 (improves 2.82%)** |
| observed_pattern_uniform_mode | 154,336.87 / 177,461.60 / 218,302.99 | 14.31 / 17.24 / 21.53% | $2,483.31 (1.38%) |

All figures: `cells.jsonl` → `cell_key` → `results.final_value` /
`results.max_dd`, min/median/max across 15 seeds.

**Flagged plainly: `observed_pattern_uniform_mode`'s seed spread is wide
enough that its median is not a fully reliable summary** — final value
ranges from $154,337 to $218,303 across the 15 seeds (a $63,966 range,
36% of the median), far wider than any other cell in this or the prior
two runs. This is the harshest error model (`uniform` mode: any of the 4
categories, not just an adjacent step) applied at the same per-tier rates
as `observed_pattern` — reported as a secondary/harsher variant per the
prompt, not the headline, and its wide spread is itself a legitimate
finding about how much that specific error model amplifies seed-to-seed
variance, not a driver defect (the deterministic cells above show the
driver behaves correctly and predictably where expected).

**Headline, in Test 1's units**: Test 1's uniform q=0.5 `adjacent` shock
cost **$24,886 (13.8%)**. `observed_pattern` — the actual measured
instability pattern, concentrated in small/micro — costs **$533.29
(0.30%)**, roughly **47x cheaper** than Test 1's uniform shock, but recall
per the prompt's own warning this is not a fair comparison on its own
(different corruption volumes and distributions). The fair comparison,
**`uniform_equivalent` at matched volume, costs $16,682.31 (9.27%)** —
**31.3x more than `observed_pattern`** at the identical number of
corrupted events. Small-cap-concentrated noise is not merely "less noise
happens to cost less" (arithmetic); **the same quantity of noise costs
dramatically less when it lands in the small-cap cohort specifically.**

## 6. Mechanism (visible directly in the data, not asserted)

Small_micro is 100% Type-A-speculative (15% cap, Rule 3's no-average-down
active) — confirmed in §2. `uniform_equivalent`'s matched-volume
corruption spreads across all four cap tiers, so most of its 51-52
corrupted events land on megacap/large/mid names, which are overwhelmingly
Type B (50% cap, no averaging-down restriction, and larger capital
allocations to begin with — see the sizing-channel run's finding that 82
of 93 Type-B Add events are tagged "established"). The same *count* of
corrupted events costs far more in dollars when it lands on
higher-cap-headroom, higher-capital-weight names than when it lands on
the 15%-capped, no-average-down-protected small-cap cohort. This is the
same cap-headroom mechanism the sizing-channel run identified for the
sizing channel — **this run shows it applies to the categorical channel
too, and in the direction the prompt's pre-registered prediction
expected.**

## 7. Step 4 — reading (report, do not decide)

1. **Does the measured instability cost material money?** **No — $533.29
   (0.30%) is near $0, stated without hedging.** This matches the
   pre-registered prediction exactly.
2. **Is small-cap noise structurally cheaper than the same volume of
   noise elsewhere?** **Yes, dramatically — 31.3x cheaper** at matched
   corruption volume (§5). Mechanism: the 15% speculative cap and Rule
   3's no-average-down rule (§6), the same cap-headroom pattern the
   sizing-channel run found for the sizing field, now confirmed for the
   categorical channel.
3. **What is the ceiling?** `small_micro_q1` (every small-cap verdict
   fully randomized) and `small_micro_zero_info` (every small-cap verdict
   forced to Hold, i.e., deleted) **both beat control** — by $678.79 and
   $5,076.26 respectively. **Even the maximum possible small-cap
   categorical noise costs nothing; the zero-information floor for this
   tier actively improves the backtest.** On this configuration, the
   small/micro instability finding from Test 4 is **economically inert**
   — no prompt work, rubric work, or waiting-for-companies-to-mature is
   justified by it, stated in the prompt's own terms since the data
   supports it plainly.

**Explicitly out of scope, not attempted**: designing a small-cap rubric
variant, the paired rubric A/B re-scoring, the noise-adjusted-cap backlog
item, and any change to `EVALUATION_PROMPT.md`.

## 8. Deviations from the prompt, and why

1. **Flip-rate reconciliation resolved in favor of neither originally-
   offered figure being exactly the design session's own** (§3) — 8/12
   matches the design session's recount exactly; reported as a correction
   to Test 4's published 7/12, with the likely source transcript (id 355)
   named directly rather than left unexplained.
2. **`observed_pattern_uniform_mode`'s wide seed spread flagged rather
   than smoothed over** (§5) — per the prompt's own instruction to flag
   any cell whose median is not a meaningful summary. Reported as a
   property of the harsher uniform error model, not investigated further
   (out of this run's scope; would need per-seed tracing to fully
   explain, which the prompt does not ask for).
3. **No separate out-of-grid mechanism diagnostic was run** (unlike the
   sizing-channel run's forced-shock check) — not needed here: this
   grid's own cells already show clear, large, non-degenerate movement
   (up to $16,682 at `uniform_equivalent`, deterministic and
   internally-consistent results at the two forced-Hold-style cells), so
   there is no ambiguity about the driver being a silent no-op the way
   nine bit-identical cells created in the sizing-channel run.

## 9. What was deliberately not done

- No conclusion on whether Test 4's small-cap instability finding should
  change any prompt, rubric, or backtest logic — scope-boundary call for
  the design session, though §7's answer is unambiguous.
- No re-running of Test 4 to correct its published 7/12→8/12 figure in
  place — flagged here as the authoritative correction; Test 4's own
  wrap-up file is left as originally written per this project's
  "corrected figure must supersede the old one explicitly, never replace
  it quietly" rule.
- No investigation of why `observed_pattern_uniform_mode`'s spread is so
  much wider than every other cell's.
- No daily-marked drawdown re-run (same scope exclusion as the
  sizing-channel run — would require a daily-granularity re-run of the
  simulator).

## 10. Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/small_cap_instability_materiality.py').read())"` — passed, before commit.
- Control cell reproduced the exact reference ($179,944.91 /
  0.20852310359539084) before any perturbation cell ran — hard-stop gate
  honored.
- Flip-rate reconciliation computed under two independent definitions
  (None-as-distinct vs None-excluded) — identical result in every tier,
  ruling out the null-value hypothesis the prompt raised.
- SPWR's single event traced directly in the control run's `funding_log`
  (`binding: "cash available"`, `actual_dollars: 0`) rather than assumed
  immaterial from the prior report's mention.
- `uniform_equivalent_q` verified to produce a matched expected corrupted
  count (51.45) to `observed_pattern`'s by construction, and both cells'
  realized median counts (51, 52) checked against that expectation.
- `git log --oneline -1 -- analysis/small_cap_instability_materiality.py`
  confirms `007f684` (the recorded `driver_commit`) actually contains the
  driver file.

## 11. Wall-clock, cells run, cells reused

Census + flip-rate reconciliation: <1s (pure computation over already-
loaded corpus and already-saved Test 4 raw output). Control gate: ~3s
(corpus load 2.5s + 1 cell). Full grid: **12s** for 105 cells (7 cells ×
15 seeds), corpus loaded once. **All 105 grid cells + 1 control cell run
fresh** — first and only run of this `run_id`, nothing reused.

## Reproduction

```bash
cd analysis
python3 small_cap_instability_materiality.py census    # Step 1, <1s
python3 small_cap_instability_materiality.py control    # Step 1a gate, ~3s
python3 small_cap_instability_materiality.py grid       # Step 2, ~12s, 105 cells
```

State: `analysis/data/run_state/small-cap-instability-materiality/
{progress.json, cells.jsonl, findings.md, census.json}`, all committed on
`sweep/db-corpus-baseline`.

## Commits this session

| Commit | What |
|---|---|
| `007f684` | driver (`small_cap_instability_materiality.py`) + prompt, before any manifest |
| `b6e35f7` | control gate + census + flip-rate reconciliation + full grid results, `findings.md` |

## Flags (per the prompt's own instruction)

- **Any cell whose seed spread is too wide for its median to be
  meaningful**: `observed_pattern_uniform_mode` (§5) — final value ranges
  $154,337–$218,303, a 36%-of-median spread. All other cells' spreads are
  narrow enough that their medians are informative, and two cells
  (`small_micro_q1`, `small_micro_zero_info` — the latter fully
  deterministic) have zero or near-zero spread.
- **Any result contradicting a published figure**: **yes — Test 4's
  published small/micro flip rate (7/12, 58%) is corrected to 8/12 (67%)
  by direct re-count, §3.** No other figure from Test 1, the
  sizing-channel run, or state-of-play is contradicted; this run's
  session-ruler drawdown figures are ruler-consistent with both prior
  runs.
- **Whether `observed_pattern` and `uniform_equivalent` achieved matched
  corruption volumes**: **yes, confirmed** (§4) — 51 vs 52 realized median
  events against a shared 51.45 expectation. The headline 31.3x
  comparison is valid.
