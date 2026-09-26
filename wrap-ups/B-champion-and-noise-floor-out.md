# B as research champion, and B's own noise floor. Wrap-up

**Run ID:** `b-champion-and-noise-floor`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial:** Step 1 and every part of Step 2 ran.
**Real spend: $28.74** (1,217 re-scored calls, of which 30 were the pre-flight; `cost_usd` summed over `scores_b_rerun1.jsonl`), against the $35 cap Luis approved (recorded in `progress.json` as `luis_approved_usd`). Committed estimate peaked at $30.46. Step 1 was $0.
**Scope boundary: report, do not decide.** Nothing promoted; `promoted_version` untouched; no holdout, no tune, no DB writes; P7's and P9's pre-registrations not written.

> Asked the same 1,217 train calls twice, the minimal prompt changed its direction (bearish / neutral / bullish) on **12.5%** of them (range **10.8–14.5%**), against v6's ~17%; its score moved by at least one point on **30.9%** and by two or more on **8.9%**. Its ranking strength was **0.130** and **0.099** on the two runs, a paired difference of **+0.031** (range **0.005 to 0.058**), so a candidate must not rank worse than B by more than **0.03**. Step 1's bookkeeping landed in commit **`de215db`**.

All figures below: rates across calls (Wilson range), or Spearman rank correlations against the 182-day tradeable-entry return vs SPY with a 95% ticker-block bootstrap (2,000 draws, seed 11). Source for every Step 2 number: `analysis/data/run_state/b-champion-and-noise-floor/results.json` (keys named below), from `analysis/b_noise_floor_analysis.py`.

## Step 2 results

**Reproduction check.** The original run's rank correlation recomputed here is 0.130 (0.051 to 0.208) → `rank.original`, identical to `wrap-ups/P6-output-format-round-out.md` §6.1. The 1,217 calls equal `p6-output-format-round/scores_b.jsonl` exactly (asserted). Re-run: 1,217 of 1,217 parsed, 0 stopped at `max_tokens`, median completion 517 tokens.

### Per stratum and pooled (rate across calls; Wilson range)

| stratum | calls | score moved ≥ 1 | score moved ≥ 2 | direction changed (≤ −2 / ≥ +3) |
|---|---|---|---|---|
| S1 | 356 | 34.0% (29.3–39.1) | 4.8% (3.0–7.5) | **16.6%** (13.1–20.8) |
| S2 | 192 | 31.3% (25.1–38.1) | 11.5% (7.7–16.7) | **12.0%** (8.1–17.3) |
| S3 | 541 | 29.0% (25.4–33.0) | 11.5% (9.0–14.4) | **10.5%** (8.2–13.4) |
| S4 | 16 | 12.5% (3.5–36.0) | 0.0% (0–19.4) | 0.0% (0–19.4) — too few calls to read |
| S5 | 112 | 32.1% (24.2–41.3) | 6.3% (3.1–12.3) | **11.6%** (6.9–18.9) |
| **pooled** | **1,217** | **30.9%** (28.4–33.6) | **8.9%** (7.4–10.6) | **12.5%** (10.8–14.5) |

Keys: `pooled.*`, `per_stratum.S*.{move_ge1,move_ge2,direction_change}`.

### Direction table, original (rows) by re-run (columns)

| | bearish | neutral | bullish | total |
|---|---|---|---|---|
| **bearish** | 160 | 31 | 0 | 191 |
| **neutral** | 23 | 719 | 49 | 791 |
| **bullish** | 0 | 49 | 186 | 235 |
| total | 183 | 799 | 235 | 1,217 |

Key `table_3x3_original_by_rerun`. Every change is to or from neutral; **no call crossed from bearish to bullish or back.** 152 changes = 31 + 49 + 23 + 49.

### Noise win rate (P3 §7 netting rule, unchanged)

Among direction changes where exactly one of the two answers matched the tradeable-entry truth: the original was right on **56 of 101 = 55.4% (45.7–64.8)**. Per stratum: S1 24 of 44 (54.5%), S2 7 of 13 (53.8%), S3 18 of 34 (52.9%), S5 7 of 10 (70%), S4 none. So on direction hits the original draw was **not** measurably luckier than the re-run (v6's cached draw was, at 20.5% for the fresh call in the tune noise arm). Key `pooled.noise_win_rate`. Use ~55% (range spans 50%) as the win rate of noise flips when netting B-derived candidates.

### Rank correlation, run against run (kind: Spearman, ticker-block range)

| | value | range |
|---|---|---|
| original | 0.130 | 0.051 to 0.208 |
| re-run | 0.099 | 0.025 to 0.170 |
| **paired difference, original minus re-run** | **+0.031** | **0.005 to 0.058** |

Key `rank`. Half-width of the paired range **0.0268**; rounded out to two decimals **0.03**, so the §2.3a rule 2 tolerance is **−0.03**, the same number as the placeholder. **Flag:** the paired range **excludes zero**. Two runs of the identical prompt, model and settings ranked measurably differently, and the original (the draw every earlier result used) is the higher one. Read plainly: the 0.130 that made B the champion is on the good side of B's own run-to-run spread; a second draw gives 0.099. Both are inside each other's ranges, and both are above v6's coded 0.070 (train), but a candidate's paired range should be read against this spread, not against zero.

### Matched-coverage hit rates, both runs (top 235 by score, bottom 191)

Ties broken by a seeded shuffle (seed 11), identical for both runs. "Hit" = the call's tradeable-entry truth matched (bullish for the top cut, bearish for the bottom).

| | top 235: hit | top 235: median return | bottom 191: hit | bottom 191: median return |
|---|---|---|---|---|
| original | 39.6% | +1.28 | 62.3% | −10.39 |
| re-run | 36.2% | −1.79 | 61.3% | −9.59 |

Key `matched_coverage`. Spread between the runs: **3.4 points** of hit rate and **3.1 points** of median return on the bullish side; **1.0 point** and **0.8 points** on the bearish side. That bullish movement is what a P7 bullish-side comparison inherits from B alone. The re-run has 183 calls at ≤ −2 (original 191), so its bottom 191 includes 8 calls scored −1; both runs have exactly 235 at ≥ +3. Overlap of the two runs' sets: 186 of 235 top, 160 of 191 bottom.

### noRead

Original 3 of 1,217 (0.25%, 0.08–0.72); re-run 4 (0.33%, 0.13–0.84); changed on 7 calls (0.58%). Key `noRead`. Negligible.

### Predictions, written before the run

| prediction | result |
|---|---|
| direction changes 10–18% | **held** (12.5%) |
| score moves ≥ 1 on 35–55% | **did not hold: 30.9%, below the range** (finding) |
| paired rank half-width 0.02–0.04 | **held** (0.027) |

## Step 1 — files changed (commit `de215db`)

- `docs/architecture/VERSION_REGISTRY.json`: `research_champion` block under `artifacts.evaluation_prompt`; P6B-minimal status `candidate` → `research_champion`; A0′ recorded with manifest `analysis/data/run_state/p6b-confound-and-concentration/cells.jsonl` (`A0p-full-s0-ph*`) and `summary.json` → `cells.A0p`. `promoted_version` unchanged (v6). Later (step 2d, commit `7ba33b5`) the re-run registered as `baseline_draws[1]`.
- `analysis/data/gate_ledger.json`: entry 2 appended by `append_to_ledger()`, `final_verdict: RESEARCH_CHAMPION`, both qualifiers, `holdout: locked`, every figure cited to its wrap-up and key. **See flag 1: this file is not tracked by git.**
- `docs/architecture/PROMPT_ARCHITECTURE.md`: §2.2 table (P1 closed, C closed, P6 done, P7 next from B, P9 and model-gate rows added, P8 after, P6D deferred, "from B" wording); §2.4 net-flip rule and §2.5 net-flip threshold; new §2.3a (six rules); §2.6 time-split sentence.
- `docs/handoffs/2026-09-24-state-of-play.md`: the §5.4 sentence and the §7 lucky-cached-draw item moved to closed, each marked `(amended 2026-09-26)`.

`python3 analysis/whats_live.py` exits 0. For the evaluation prompt it prints `MATCH evaluation_prompt promoted=357b6b0b…` (v6, unchanged). **It prints nothing about the research champion**; the script only checks promoted hashes.

**Step 2d** (commit `7ba33b5`): §2.3a rule 2 (−0.03, now measured), §2.4 placeholder (12.5% pooled and per stratum), ledger entry 2 `amend_after` filled, registry second draw.

### 1e propagation check

`git grep` over `docs/` and `CLAUDE.md` for P1 "run first / next" and v6 as incumbent found only three hits, all in superseded or descriptive documents, not fixed: `docs/handoffs/2026-09-19-state-of-play.md:9` (superseded state of play), `docs/handoffs/2026-09-25-next-steps-proposal.md:63` and `2026-09-26-next-steps-review.md:18` (both quote the stale queue in order to correct it). Not checked: `wrap-ups/` and `prompts/` (historical records by design).

## Flags, deviations, premises

1. **`analysis/data/gate_ledger.json` is gitignored and has never been tracked** (`.gitignore:15`, `analysis/data/*`). Entry 1 is likewise uncommitted. Entry 2 exists on disk only and is not in commit `de215db`; a fresh clone has no ledger. I did not `git add -f` it. Decision for Luis: force-track the ledger, or keep it local.
2. **The state-of-play `.docx` and the published artifact were not updated** for the two amended lines (the prompt said no republish). The `.md` now differs from its `.docx` and the artifact `CW96Nyoxsx4kM4B2JF1Q8r` by those two amendments.
3. **Prompt says pre-flight strata S1–S4; train has S1–S5** (`universe_counts` S1 356, S2 192, S3 541, S4 16, S5 112). Proportional allocation of 30 gave S4 zero calls, so I moved one call from S3 to S4 (S1 9, S2 5, S3 12, S4 1, S5 3). Recorded in `progress.json` notes.
4. **Request-shape equality could not be checked against `raw_arm_b.jsonl` literally**: it stores responses, not request parameters. Instead the driver's `rerun-check` asserted, on 25 sampled calls, model, `max_tokens` 4096, no `temperature` key, exact system text and `cache_control`, the exact user message, and that each call's original custom id exists in `raw_arm_b.jsonl` or `raw_preflight.jsonl` (`request_shape_check.json`). The request builder `make_request()` is unchanged code.
5. The prompt's "pre-flight threshold" cost check used the measured $0.02506/call from 30 calls (projected $30.50, under $32); the full batch then billed $0.0236/call on average. Reused the 30 pre-flight rows, so no call was scored twice.
6. Gain-per-point-of-drawdown figures in ledger entry 2 ($6,503 B3, $4,981 A0′) are quoted from `docs/handoffs/2026-09-24-state-of-play.md` §2.4, not re-derived; the confound wrap-up does not print them.
7. The pooled paired difference over v6 is not in the ledger: no prior run computed it (train +0.061, tune +0.059 are recorded instead).
8. Batch ids: preflight `msgbatch_01XyhxAYRuZNVk4yZgtq9vxC`, full `msgbatch_01HFxfxbiJVkCq9cnP6i4yuC`, both committed in `progress.json`. One process throughout, no piped poller.

## What this means for P7

B's direction changes (12.5%, range 10.8–14.5%) sit **below v6's ~17%, but the ranges overlap** (v6's train noise arm was 16.7%, 11.1–24.3%), so "well under" is not established; "modestly under" is. In numbers, B disagrees with itself on about **152 of 1,217 calls**. Two consequences:

- **Flip counts.** A P7 round that changes fewer than roughly 150 calls against B cannot be told apart from B re-running itself; the ~200 figure in the prompt is a safe upper edge. Net flips (raw minus ~152) are what count. Noise flips are fairly even between the two draws (55% original right), so netting does not need to correct a lean.
- **Ranking is the tighter constraint.** B's own two runs differ by 0.031 in rank correlation with a range that excludes zero, and the top-235 bullish cut moved 3.4 hit-rate points. A candidate has to beat **both** draws (§2.3a rule 3) by more than that spread before its bullish-side gain means anything. The ~150-call P7 pre-flight is enough to decide whether a full ~$45 round is worth running on the flip-count test; it is not enough to say anything about ranking, which needs the full round.

## Not done

No P7/P9 pre-registration, no scoring beyond the train re-run, no promotion, no mapping or threshold change, no cache refresh, no DB writes, no republish of the state of play.

## Provenance

Driver `analysis/p6_output_format_driver.py --rerun` (own commit before any output; sha in `progress.json` → `driver_commit`), analysis `analysis/b_noise_floor_analysis.py` (own commit before `results.json`). State: `analysis/data/run_state/b-champion-and-noise-floor/` (`progress.json`, `findings.md`, `selection.json`, `request_shape_check.json`, `preflight_report.json`, `raw_preflight.jsonl`, `raw_rerun.jsonl`, `scores_b_rerun1.jsonl`, `results.json`). Model cache in gitignored `analysis/data/evals/P6B-minimal_claude-sonnet-4-6_rerun1/`. Guard: `PROMPT_CANDIDATE=P6B-minimal` recorded in `progress.json` → `guards`.

```bash
python3 analysis/p6_output_format_driver.py --rerun rerun-check
python3 analysis/b_noise_floor_analysis.py
```
