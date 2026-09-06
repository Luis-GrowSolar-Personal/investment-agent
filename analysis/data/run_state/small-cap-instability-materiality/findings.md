# findings — small-cap-instability-materiality

## Step 1a — control gate
control_1a reproduced reference exactly: final_value=179944.90608455567,
max_dd=0.20852310359539084 ($179,944.91 / 20.8523%). Gate passes.

## Step 1b — census
n_total_events=195. Per cap tier: megacap 69 (35.38%), large 42 (21.54%),
mid 26 (13.33%), small_micro 58 (29.74%, includes SPWR's 1 event).
small_micro's ceiling on this channel is under 30% of events, not the
headline flip-rate percentage.

Simulator's own tier_fn/type_fn mapping for the small_micro cohort:
QS/AMPX/ENVX/EOSE/SPWR are ALL Type-A-speculative (cap 15%, Rule 3
no-average-down applies); RUN also Type-A-speculative. So small_micro is
100% Type-A-speculative in this corpus's sim-tier terms — the same cohort
the sizing-channel run found absorbs almost all sizing-channel noise via
its 15% cap. Consistent with, not contradicting, that finding.

SPWR: 1 event, verified directly via funding_log — `binding: cash
available`, `actual_dollars: 0`. Confirmed immaterial regardless of
assigned flip rate, as the prompt anticipated.

## Step 1c — flip-rate reconciliation
Re-derived directly from analysis/test4_noise_floor/raw/*.json (50
transcripts, 5 runs each). Definition used: a transcript "flips" if 2+ of
its 5 `recommendation` values differ (checked both counting None as its
own distinct value and excluding None entirely — identical result under
both definitions in this corpus, so the None-ambiguity hypothesized in
the prompt does not explain the discrepancy).

Reconciled rates: megacap 2/13 (15.38%), large 0/13 (0%), mid 1/12
(8.33%), small_micro **8/12 (66.67%)**.

**Previously published number corrected: Test 4's wrap-up
(wrap-ups/test4-analyst-noise-floor-out.md) reports small_micro flips as
7/12 (58%). Direct re-count over the same raw files gives 8/12 (67%) under
both flip definitions tried.** This matches the design session's own
independent recount (stated in this prompt as the alternative figure),
not the originally published one. The 8th flipping transcript
(id 355, QS: Trim/Hold/Trim/Hold/Hold) was apparently missed in the
original manual count. **The reconciled 8/12 (67%) is used as this run's
q value for small_micro** — the corrected figure supersedes 7/12 (58%)
wherever this project cites small_micro's flip rate going forward.

## Step 2 — grid parameters
q_per_tier = {megacap: 0.15385, large: 0.0, mid: 0.08333,
small_micro: 0.66667}. uniform_equivalent_q = 0.263840, chosen so
expected corrupted-event count (51.45 of 195) matches observed_pattern's
expected count exactly by construction.

Realized corrupted-event counts (median across 15 seeds, matching the
intended expectation closely):
- observed_pattern: 42/51/60 (min/median/max) — median 51, vs expected 51.45. Matched.
- uniform_equivalent: 43/52/64 — median 52, vs expected 51.45. Matched.
- small_micro_only: 29/39/43 (out of 58 small_micro events at q=0.667, expected 38.67). Matched.
- small_micro_q1: 58/58/58 (all 58 small_micro events, deterministic since q=1.0). Matched exactly.
- small_micro_zero_info: 58/58/58 (deterministic, all small_micro events forced Hold).
- observed_pattern_uniform_mode: 43/49/54 — median 49, close to 51.45 (uniform mode's own RNG draws differ slightly from adjacent's but the accept/reject draw uses the same q_fn, so this is seed noise, not a mismatch).

**observed_pattern and uniform_equivalent achieved matched corruption
volumes (51 vs 52 median, both close to the shared 51.45 expectation) —
the headline comparison in Step 3/4 is valid.**

## Step 3/4 — headline results (median across 15 seeds, final_value / cost vs control $179,944.91)

- control: $179,944.91 (0 corrupted events)
- observed_pattern: $179,411.62, **cost $533.29 (0.30%)**, dd 19.19% (session-sampled; control 20.85%, improves 1.66pp)
- small_micro_only: $179,003.07, cost $941.84 (0.52%), dd 19.35%
- uniform_equivalent: $163,262.60, **cost $16,682.31 (9.27%)**, dd 18.71%
- small_micro_q1: $180,623.70, cost **−$678.79 (IMPROVES 0.38%)**, dd 19.04%
- small_micro_zero_info: $185,021.17 (deterministic), cost **−$5,076.26 (IMPROVES 2.82%)**, dd 17.97%
- observed_pattern_uniform_mode: $177,461.60, cost $2,483.31 (1.38%), dd 17.24% (wider seed spread: min $154,337/max $218,303 — flagged, see report)

**uniform_equivalent costs 31.3x more than observed_pattern at matched
corruption volume** (16,682.31 / 533.29). Small-cap-concentrated noise is
structurally far cheaper than the same volume of noise spread evenly
across the corpus.

**Ceiling test: even fully randomizing every small-cap verdict
(small_micro_q1) or deleting all small-cap information entirely
(small_micro_zero_info) does not cost money — both cells beat control's
median.** small_micro_zero_info in particular is deterministic (no RNG,
forced Hold on all 58 events) and beats control by $5,076 (2.82%) with
lower drawdown (17.97% vs 20.85%).

## Mechanism, visible in the data
Small_micro is 100% Type-A-speculative (15% cap) with Rule 3's
no-average-down rule active. uniform_equivalent's matched corruption
volume lands mostly in megacap/large/mid — which are overwhelmingly Type
B (cap 50%, more capital-weighted, no averaging-down restriction) — so the
same *count* of corrupted events costs far more dollars when it lands on
higher-cap-headroom, higher-capital-weight names. This is the same
cap-headroom mechanism the sizing-channel run identified, now shown to
apply to the categorical (recommendation) channel too, and pointing the
same direction: noise concentrated in the 15%-capped speculative cohort
is cheap; noise anywhere in the 50%-capped Type-B cohort is not.
