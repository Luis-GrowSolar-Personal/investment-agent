# Findings — test4-analyst-noise-floor-v6

## Reconciliation (this invocation, before Step 2)

Per the user's explicit note: this run's own `progress.json` said
`step1_reuse_sample: pending` and `step2_model_drift_check: pending`, but
disk was ahead of the checkpoint on both:

- `sample.json` already existed (50 rows, correct tier counts: megacap 13,
  large 13, mid 12, small_micro 12) — Step 1 was already done in a prior
  invocation that was interrupted before it could update `progress.json`.
- `analysis/test4_noise_floor_v6/driftcheck/raw/{23,132,141,212,230}.json`
  all exist, each with exactly 5 runs, each run carrying valid `structured`
  output, `prompt_candidate_used: "v10+auto1"`, `concurrency: "5-way
  concurrent"`. `run_state/test4-analyst-noise-floor-v6-driftcheck/progress.json`
  independently confirms `step2_250_scoring_calls: "done"`,
  `transcripts_completed: [23, 132, 141, 212, 230]`.

**Verified complete. No calls re-issued.** Marked both steps `done` in this
run's own `progress.json` without spending anything. This is the second
time this project's checkpointing has correctly protected spend across an
interrupted invocation (first was the original Test 4 run's OS-kill
resumes) — this time the interruption was a user-directed stop mid-session
rather than a crash, and the same discipline applied.

## Step 2 — model-drift check result, reframed per the user's note

**The drift check itself is now known-moot as drift detection.**
`PROMOTION_GATE.md` §8 (corrected 2026-09-12): from Claude 4.6 onward, a
dateless model ID is a pinned, immutable snapshot — Anthropic does not
repoint existing IDs. So `claude-sonnet-4-6` cannot have silently changed
underneath this project between the original Test 4 run and today. This
25-call exercise is reported below as **a candidate-hatch functional test
and a bridge sample**, not as evidence bearing on drift.

**Candidate hatch: worked exactly as specified.** All 5 output files record
`"prompt_candidate_used": "v10+auto1"` and `"concurrency": "5-way
concurrent"` — confirming `PROMPT_CANDIDATE=v10+auto1` correctly overrode
the promoted-prompt guard and every row is traceable to the candidate, not
silently mislabeled as the promoted version (the exact failure mode
`2026-09-03-prompt-version-drift.md` documents).

**Reproduction against the original Test 4 run's saved output for the same
5 transcripts** (`analysis/test4_noise_floor/raw/{id}.json`, both scored
under v10+auto1 / claude-sonnet-4-6, comparing the set of `recommendation`
values across the 5 runs):

| transcript | ticker | tier | original recs | new (bridge) recs | match |
|---|---|---|---|---|---|
| 132 | ORCL | large | Add,Add,Add,Add,Add | Add,Add,Add,Add,Add | YES |
| 141 | MSFT | megacap | Add,Add,Add,Add,Add | Add,Add,Add,Add,Add | YES |
| 212 | MSFT | megacap | Add,Add,Add,Add,Add | Add,Add,Add,Add,Add | YES |
| 230 | TTD | mid | Add,Add,Add,Add,Add | Add,Add,Add,Add,Add | YES |
| **23** | **EOSE** | **small_micro** | **Add,Add,Add,Add,Hold** | **Hold,Hold,Hold,Hold,Hold** | **NO** |

**4/5 reproduce exactly; transcript 23 (EOSE, small_micro) does not** — a
full flip from 4-Add/1-Hold to unanimous 5-Hold.

**Reading, per the corrected understanding (not drift):** since a pinned
post-4.6 model ID cannot silently change, this is not evidence the
`claude-sonnet-4-6` alias moved. The more likely explanation is ordinary
LLM sampling variance at temperature 0 -- temperature 0 sharply reduces but
does not fully eliminate run-to-run variance (routing/batching effects can
still produce different completions for a borderline case), and this is
consistent with Test 4's own original finding that small/micro-tier names
carry by far the highest instability (58% flip rate, 14.34pp noise-floor
std -- `wrap-ups/test4-analyst-noise-floor-out.md`). EOSE landing on the
unstable side of a borderline call is exactly the kind of transcript Test
4 already characterized as noisy, not a new mechanism.

**Consequence for Step 4's v6-vs-v10+auto1 comparison:** flagged, not
adjudicated. This one data point does not on its own establish anything
about the v6 arm (it is a v10+auto1-vs-v10+auto1 same-model comparison,
orthogonal to the v6 question), but it is reported here because it bears on
how much weight any single-transcript disagreement should carry later in
this run.

## Step 3 — v6 arm, 250 calls

Completed cleanly across two background invocations of the same command
(the monitoring loop was killed twice for system low memory; the scoring
process itself was never interrupted and ran to completion both times it
was checked). **50/50 transcripts, 250/250 calls, zero calls lost or
re-run.** 5-way concurrent throughout — `concurrency_notes_seen: ["5-way
concurrent"]`, no serial fallback triggered (no rate limits hit).

Verified before analysis: all 50 raw files carry
`prompt_version_header: "v6 (stable best after v5→v8 iteration)"`,
`prompt_candidate_used: null`, `model: "claude-sonnet-4-6"` — the promoted
prompt, no candidate override, exactly as Step 3 required. Token spend:
**4,147,250 tokens** (3,464,905 in / 682,345 out).

## Step 4 — results and the three comparisons

**(a) v6 per-tier noise floors** (`analyst_direct_scorer.py` methodology,
imported not reimplemented):

| tier | hit rates across 5 runs | std (pp) | range (pp) | n |
|---|---|---|---|---|
| megacap | 23.1/15.4/23.1/30.8/23.1% | **4.87** | 15.38 | 13 |
| large | 76.9/69.2/76.9/76.9/76.9% | **3.08** | 7.69 | 13 |
| mid | 41.7/41.7/50.0/41.7/41.7% | **3.33** | 8.33 | 12 |
| small_micro | 33.3/36.4/36.4/33.3/25.0% | **4.17** | 11.36 | 12 |

Aggregate: std **2.31pp**, range 6.12pp.

Primary (thesisHealth/recommendation/stumbleType/mitigationCapabilityTrackRecord)
4-field instability: **60/200 = 30.0%**. Recommendation flips: **14/50 =
28.0%**, including **3 three-way-or-more splits**: id 175 (ENVX:
Add,Trim,Hold,Hold,Hold), id 204 (MSFT: Trim,Hold,Hold,Add,Trim), id 355
(QS: Hold,null,Trim,Trim,Trim — one run's output failed to parse, itself a
form of instability, flagged separately).

Recommendation-flip concentration by tier (direct per-sample inspection):
**megacap 5/13 (38.5%)**, large 1/13 (7.7%), mid 2/12 (16.7%), **small_micro
6/12 (50.0%)**.

**(b) v6 vs v10+auto1, paired on the identical 50-transcript sample**:

| metric | v10+auto1 (original) | v6 (this run) |
|---|---|---|
| primary 4-field instability | 39/200 (19.5%) | **60/200 (30.0%)** |
| recommendation flips | 11/50 (22.0%) | **14/50 (28.0%)** |
| noise floor, aggregate std/range | 2.65pp / 8.0pp | 2.31pp / 6.12pp |
| noise floor, megacap std/range | 3.77pp / 7.69pp | **4.87pp / 15.38pp** |
| noise floor, large std/range | 0.0pp / 0.0pp | **3.08pp / 7.69pp** |
| noise floor, mid std/range | 0.0pp / 0.0pp | **3.33pp / 8.33pp** |
| noise floor, small_micro std/range | 14.34pp / 41.67pp | **4.17pp / 11.36pp** |
| flip rate, megacap | 2/13 (15%) | **5/13 (38.5%)** |
| flip rate, large | 0/13 (0%) | 1/13 (7.7%) |
| flip rate, mid | 1/12 (8%) | 2/12 (16.7%) |
| flip rate, small_micro | 7/12 (58%) | 6/12 (50.0%) |

**FINDING, load-bearing: v6 is NOT a cleaner-behaving prompt than
v10+auto1 on this sample — it is noisier in aggregate (30.0% vs 19.5%
primary instability, 28.0% vs 22.0% flips), and the *shape* of that noise
is different, not just its magnitude.** v10+auto1 had a striking
large/mid-tier floor of exactly 0.0pp (perfectly stable) with all the noise
concentrated in small_micro (14.34pp). **v6 spreads noise across every
tier** (3.08–4.87pp each) with no tier reading anywhere near zero, and its
*highest* single-tier std is now **megacap** (4.87pp), not small_micro.
This directly contradicts the intuitive expectation that the promoted,
presumably-more-mature prompt would show less noise, or the same
noise concentrated the same way — reported as a diagnostic finding per
this project's own rule that a diagnostic contradicting an expectation is
a finding, not a reason to stop.

**Per the prompt's own scope boundary: this is informative, NOT a §2.2a
gate.** 50 transcripts is not a full-sample comparison, there is no
holdout, and no forward-return regression gate is computed. No
`gate_ledger.json` entry opened. No recommendation to promote or condemn
either prompt is made here. **The §2.2a gate for every prompt version from
v7 onward has still never been run** — this run does not change that.

**(c) v6 here vs v6's historical figure.** `EVALUATION_PROMPT.md`'s own
changelog records v6 at 18/84 (21.4%) unstable — ENPH-only, 3 runs, on
whichever model was live in July 2026 (not confirmed to be
`claude-sonnet-4-6`, which per `PROMOTION_GATE.md` §8.1 was only forced in
starting late June). This run's **30.0% (60/200)** differs from that figure
on every axis simultaneously: sample (50 transcripts across 15 tickers vs
ENPH only), run count (5 vs 3), and very possibly model. **This is the
first measurement of v6's stability on the actual portfolio corpus at 5
runs** — it is not a clean like-for-like comparison to the historical
21.4% figure, and is not treated as one.

## Step 5 — gate reading vs `gate_ledger.json` entry 1 (-7.44pp, noise_std_pp 4.2)

**The prompt-version mismatch is now resolved**: both the regression
(gate_ledger entry 1, 2026-05-23) and this floor are measured under v6.
That was the whole point of this re-run.

**The tier-scope mismatch remains, and this run does not fix it** — entry
1's 7 tickers (ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR) are overwhelmingly
small/micro-cap, so the small_micro tier-matched floor is the more relevant
comparison than the aggregate.

- **Aggregate reading:** -7.44pp against 2.31pp aggregate std = **~3.2
  standard deviations**. Clearly exceeds noise.
- **Tier-matched reading (small_micro, the relevant tier for entry 1's
  actual scope):** -7.44pp against **4.17pp** std = **~1.78 standard
  deviations**.

**This is a materially different tier-matched reading than the original
(v10+auto1-measured) Test 4 found.** The original run's small_micro floor
was 14.34pp, putting the -7.44pp regression at only ~0.52 SD — comfortably
inside noise, the basis for reading the HOLD verdict's substance as
questionable. **Under v6, the small_micro floor is much tighter (4.17pp),
and the same regression now sits at ~1.78 SD — no longer comfortably
inside noise, though still short of the conventional ~2 SD threshold used
elsewhere in this project.** Both readings (aggregate and tier-matched) now
point in the same rough direction — the regression is not clearly absorbed
by noise — where the original v10+auto1-measured run had the two readings
disagreeing sharply.

**Report, not adjudicate, per this run's scope boundary.** Do not re-run
or amend the model gate here. What would settle it, unchanged from the
original run's own conclusion: the paired champion-vs-challenger
re-scoring (state-of-play §5.5's open question), now additionally
requiring the prompt version be pinned to v6 as well as the model — which
this run's own result suggests may change the answer, not just tighten the
measurement.

- Checkpoint: transcript 212 (MSFT 2020-10-27, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 1/50 transcripts, 84680 tokens so far.

- Checkpoint: transcript 141 (MSFT 2024-10-30, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 2/50 transcripts, 175872 tokens so far.

- Checkpoint: transcript 204 (MSFT 2023-01-24, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 3/50 transcripts, 265361 tokens so far.

- Checkpoint: transcript 156 (AAPL 2022-01-27, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 4/50 transcripts, 342283 tokens so far.

- Checkpoint: transcript 297 (GOOGL 2024-01-30, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 5/50 transcripts, 423811 tokens so far.

- Checkpoint: transcript 113 (GOOGL 2025-04-24, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 6/50 transcripts, 506348 tokens so far.

- Checkpoint: transcript 220 (TSLA 2022-10-19, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 7/50 transcripts, 590433 tokens so far.

- Checkpoint: transcript 224 (TSLA 2021-10-20, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 8/50 transcripts, 677101 tokens so far.

- Checkpoint: transcript 303 (GOOGL 2022-10-25, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 9/50 transcripts, 758865 tokens so far.

- Checkpoint: transcript 52 (AAPL 2025-01-30, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 10/50 transcripts, 838593 tokens so far.

- Checkpoint: transcript 46 (TSLA 2025-10-22, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 11/50 transcripts, 928759 tokens so far.

- Checkpoint: transcript 315 (NVDA 2022-05-25, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 12/50 transcripts, 1012314 tokens so far.

- Checkpoint: transcript 114 (GOOGL 2025-02-04, tier megacap) 5/5 runs complete (5-way concurrent). Running total: 13/50 transcripts, 1098685 tokens so far.

- Checkpoint: transcript 132 (ORCL 2025-06-10, tier large) 5/5 runs complete (5-way concurrent). Running total: 14/50 transcripts, 1166495 tokens so far.

- Checkpoint: transcript 336 (ORCL 2023-03-09, tier large) 5/5 runs complete (5-way concurrent). Running total: 15/50 transcripts, 1237389 tokens so far.

- Checkpoint: transcript 240 (AMD 2023-10-31, tier large) 5/5 runs complete (5-way concurrent). Running total: 16/50 transcripts, 1326574 tokens so far.

- Checkpoint: transcript 331 (ORCL 2024-06-11, tier large) 5/5 runs complete (5-way concurrent). Running total: 17/50 transcripts, 1395262 tokens so far.

- Checkpoint: transcript 266 (AVGO 2021-09-02, tier large) 5/5 runs complete (5-way concurrent). Running total: 18/50 transcripts, 1462937 tokens so far.

- Checkpoint: transcript 120 (AMD 2025-02-04, tier large) 5/5 runs complete (5-way concurrent). Running total: 19/50 transcripts, 1550397 tokens so far.

- Checkpoint: transcript 131 (ORCL 2025-09-09, tier large) 5/5 runs complete (5-way concurrent). Running total: 20/50 transcripts, 1618308 tokens so far.

- Checkpoint: transcript 258 (AVGO 2023-06-01, tier large) 5/5 runs complete (5-way concurrent). Running total: 21/50 transcripts, 1689785 tokens so far.

- Checkpoint: transcript 264 (AVGO 2022-03-03, tier large) 5/5 runs complete (5-way concurrent). Running total: 22/50 transcripts, 1764356 tokens so far.

- Checkpoint: transcript 343 (ORCL 2021-09-13, tier large) 5/5 runs complete (5-way concurrent). Running total: 23/50 transcripts, 1823858 tokens so far.

- Checkpoint: transcript 255 (AVGO 2024-06-12, tier large) 5/5 runs complete (5-way concurrent). Running total: 24/50 transcripts, 1901443 tokens so far.

- Checkpoint: transcript 344 (ORCL 2021-03-10, tier large) 5/5 runs complete (5-way concurrent). Running total: 25/50 transcripts, 1966901 tokens so far.

- Checkpoint: transcript 338 (ORCL 2022-09-12, tier large) 5/5 runs complete (5-way concurrent). Running total: 26/50 transcripts, 2035732 tokens so far.

- Checkpoint: transcript 230 (TTD 2023-08-09, tier mid) 5/5 runs complete (5-way concurrent). Running total: 27/50 transcripts, 2132596 tokens so far.

- Checkpoint: transcript 292 (FSLR 2022-03-01, tier mid) 5/5 runs complete (5-way concurrent). Running total: 28/50 transcripts, 2240559 tokens so far.

- Checkpoint: transcript 284 (FSLR 2024-02-27, tier mid) 5/5 runs complete (5-way concurrent). Running total: 29/50 transcripts, 2333523 tokens so far.

- Checkpoint: transcript 238 (TTD 2021-05-10, tier mid) 5/5 runs complete (5-way concurrent). Running total: 30/50 transcripts, 2432533 tokens so far.

- Checkpoint: transcript 287 (FSLR 2023-02-28, tier mid) 5/5 runs complete (5-way concurrent). Running total: 31/50 transcripts, 2528413 tokens so far.

- Checkpoint: transcript 100 (FSLR 2025-02-25, tier mid) 5/5 runs complete (5-way concurrent). Running total: 32/50 transcripts, 2633540 tokens so far.

- Checkpoint: transcript 36 (TTD 2025-02-12, tier mid) 5/5 runs complete (5-way concurrent). Running total: 33/50 transcripts, 2731863 tokens so far.

- Checkpoint: transcript 285 (FSLR 2023-07-27, tier mid) 5/5 runs complete (5-way concurrent). Running total: 34/50 transcripts, 2816699 tokens so far.

- Checkpoint: transcript 233 (TTD 2022-08-09, tier mid) 5/5 runs complete (5-way concurrent). Running total: 35/50 transcripts, 2914201 tokens so far.

- Checkpoint: transcript 34 (TTD 2024-08-08, tier mid) 5/5 runs complete (5-way concurrent). Running total: 36/50 transcripts, 3002570 tokens so far.

- Checkpoint: transcript 234 (TTD 2021-08-09, tier mid) 5/5 runs complete (5-way concurrent). Running total: 37/50 transcripts, 3101231 tokens so far.

- Checkpoint: transcript 239 (TTD 2022-11-09, tier mid) 5/5 runs complete (5-way concurrent). Running total: 38/50 transcripts, 3200860 tokens so far.

- Checkpoint: transcript 23 (EOSE 2025-07-31, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 39/50 transcripts, 3286332 tokens so far.

- Checkpoint: transcript 348 (QS 2024-04-24, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 40/50 transcripts, 3341254 tokens so far.

- Checkpoint: transcript 193 (EOSE 2022-02-25, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 41/50 transcripts, 3435264 tokens so far.

- Checkpoint: transcript 355 (QS 2022-10-26, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 42/50 transcripts, 3493547 tokens so far.

- Checkpoint: transcript 172 (ENVX 2023-11-07, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 43/50 transcripts, 3569695 tokens so far.

- Checkpoint: transcript 170 (ENVX 2024-05-01, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 44/50 transcripts, 3654511 tokens so far.

- Checkpoint: transcript 16 (AMPX 2025-08-07, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 45/50 transcripts, 3727463 tokens so far.

- Checkpoint: transcript 169 (AMPX 2023-03-23, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 46/50 transcripts, 3785821 tokens so far.

- Checkpoint: transcript 173 (ENVX 2023-07-26, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 47/50 transcripts, 3885395 tokens so far.

- Checkpoint: transcript 168 (AMPX 2023-05-10, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 48/50 transcripts, 3945425 tokens so far.

- Checkpoint: transcript 175 (ENVX 2023-02-22, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 49/50 transcripts, 4037711 tokens so far.

- Checkpoint: transcript 186 (EOSE 2023-11-07, tier small_micro) 5/5 runs complete (5-way concurrent). Running total: 50/50 transcripts, 4147250 tokens so far.
