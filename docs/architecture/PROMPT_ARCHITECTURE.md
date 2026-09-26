# Prompt Architecture — analyst prompt shape, and the queue of candidates

**Created 2026-09-17.** Scope: **Layer 2 only** — the analyst prompt that reads a
single earnings-call transcript and emits `per_call_rec`. Nothing here concerns
the trend layer or the allocator.

**What belongs where.** This file holds (§1) closed decisions about the prompt's
shape and (§2) the ranked queue of candidate changes with their pre-registration.
It deliberately does **not** hold:

| Topic | Lives in |
|---|---|
| What the scorer measures, dead band, weighting, windows | `PROMOTION_GATE.md` §3.1 / §3.1a |
| Whether a candidate passed and may be promoted | `PROMOTION_GATE.md` §5, `VERSION_REGISTRY.json` |
| The prompt text itself | `docs/EVALUATION_PROMPT.md` |
| Exit-timing and allocator signal design | `docs/handoffs/2026-09-05-exit-latency-framework.md` |

---

## 1. Closed decisions about the prompt's shape

Do not re-derive these. Each was settled against measured data; the evidence is
named so a future session can overturn one with better evidence rather than with
an argument.

### 1.1 One prompt. Per-ticker **inputs**, never per-ticker **prompts**

A prompt fitted to a single company's own track record cannot be measured.
Median calls per company is 24. At n=24 a single ticker's hit rate carries a
**±18-point** 95% range; the observed best-minus-worst spread across 56 tickers
is 60 points, of which **47 points appear from luck alone** if every company is
identically average. Detecting a 5-point change on one ticker needs **662 calls**
for that ticker — 165 years of quarterly earnings. It also destroys the gate:
56 prompts at n=24 produce no pooled figure to grade.

**Permitted:** one prompt whose *inputs* vary by ticker — tier, cohort, the
company's own prior thesis, its own trailing ratios. n stays at 1,184 (1,240
train calls minus the first call of each company, which has no predecessor).

**Forbidden:** any feedback from realized **outcomes** into the prompt that is
not strictly forward-only (only calls before date T may inform the call at T).
Note that per-call prompt variation also defeats the cached system block that
makes a ~$47 scoring round possible.

Per-ticker *memory* — what management promised last quarter — is inputs, not
fitting, and is permitted.

### 1.2 Conditioning happens on tier/cohort, because a class has enough members

"Inventory up 50%" means different things for a pre-revenue speculative with
few customers and an established company with a forecasting record. That is a
property of the class, not of the ticker, and classes have enough members to
measure. The 3-axis speculative/established classifier already exists and `tier`
is already threaded through the pipeline. Same conclusion the two-template fact
sheet design reached independently
(`2026-09-05-exit-latency-framework.md` §4).

### 1.3 Grading field is `per_call_rec`

The analyst's own call, never `final_action`. Grading the post-trend-layer
action lets a trend-layer change read as a prompt improvement; Stage D hit
exactly this.

### 1.4 Firewall

No portfolio or position data reaches this layer. Non-transcript data *about the
company* — filings, XBRL facts, its own price history — is not portfolio data and
does not breach the firewall.

---

## 2. Candidate queue

### 2.1 What the baselines say is broken

Pooled train (56 companies, 1,236 calls) and tune (51 companies, 1,168 calls),
both `claude-sonnet-4-6`:

| | train | tune (fresh companies) |
|---|---|---|
| v6 accuracy | 30.3% | 28.3% |
| luck-corrected gap | +2.48pp (95% −0.06 to +5.08) | +2.64pp (95% 0.21 to 5.00) |
| times v6 said bearish | 103 (8.3%) | 84 (7.2%) |
| …and was right | 60.2% | 59.5% |
| base rate for bearish | 44.9% | 48.4% |
| times v6 said neutral | 57.3% | 58.8% |
| always-bearish guesser | 44.9% | 48.4% |

**The finding that drives the queue, and it replicated on companies it was not
derived from: v6's bearish calls are right ~60% against base rates of 45–48%,
and it makes them 7–8% of the time.** Its rarest answer is its best one.

**State it in the band-independent form, because the other form is a trap.**
"v6 over-calls neutral" depends on where the dead band sits: at ±15% the outcome
distribution (56.1% neutral) nearly matches v6's own (58.1%), and the criticism
evaporates. That framing was briefly used to block P1 and should not be used
again.

What survives at every band is this: **v6 under-uses its single best signal.**
Its bearish calls beat the base rate by 13 to 18 points at ±5%, ±10%, ±15% and
±20% alike, and it deploys them on 7.8% of calls. Evidence and the retraction:
`PROMOTION_GATE.md` §3.1a R1, which remains open but blocks nothing.

**Pooled across both baselines** (2,404 calls, 107 companies): gap **+2.53pp,
95% +0.79 to +4.19 — excludes zero.** Legitimate for v6 only; v6 was never
selected using train. No candidate may be reported this way.

Not a corpus artifact: the bearish skew holds in every stratum (S1 megacap
43.9%, S2 48.0%, S3 47.0%), and excluding the failures stratum moves the pooled
figure from 46.6% to 46.2%. It is the ordinary right-skew of stock returns.

### 2.2 Queue

Ranked by expected value per dollar, not by ambition. A round is ~$47 and
several hours.

| # | Candidate | New data? | Blocked by | Status |
|---|---|---|---|---|
| P1 | **Commit to bearish when the evidence supports it** | none | — | **closed 2026-09-25 — superseded by B** |
| P2 | Post-call reaction at K≥1, three arms | none (price cache) | §3.1a R3 | blocked |
| P3 | Thesis / guidance ledger — score QN−1's promises at QN | none (transcripts on disk) | — | ready (unchanged by this edit) |
| P4 | Tier-conditioned reading of financial facts | XBRL build | P3 | not started |
| P5 | Peer read-through across cohort members | none (transcripts) | — | not started |
| **P6** | **Output-format round: v6 vs minimal prompt vs continuous score** — three arms, one round | none | flip-count rules corrected (2026-09-23 state of play §4.2) | **done — B held on tune (2026-09-25); research champion.** Arm C **closed** (same signal, 66% more cost) |
| P7 | Three-voices rubric (CFO numbers / CEO claims / what analysts pressed), **from B** | none | B's noise floor (b-champion-and-noise-floor step 2) | **falsified 2026-09-26 (train; gate 1 31.5% vs 47%)** |
| P9 | Expected return in percent (with a range) instead of a −5..+5 label, **from B** | none | B's noise floor; §2.3a rule 5 | **falsified 2026-09-26 (train, two draws; ranking non-inferiority failed on draw 2; severity confirmed on both)** |
| — | Model gate on B: newer or larger model on the unchanged minimal prompt (`PROMOTION_GATE.md` §2.2b equivalence hurdle) | none | P7 and P9 | named, **last** |
| P8 | Auto-iterate loop as hypothesis generator (§2.6, with the 2026-09-24 constraints) | none (eval files) | after P7/P9 | named, not built |
| P6D | B plus the structured fields the allocator needs | none | allocator rebuild | **deferred to the allocator rebuild** |

P2 is blocked on a free decision (R3's grading-window rule), not on work. P3
can run today against the existing corpus — no vendor fetching, no new
transcripts. **The incumbent for every new candidate is B (`P6B-minimal`), the
research champion since 2026-09-25 (`VERSION_REGISTRY.json` →
`artifacts.evaluation_prompt.research_champion`). Production stays on v6.**

**P1 — pre-registration, registered 2026-09-17**

- **Change.** Push the prompt to issue a bearish call whenever its own evidence
  supports one, rather than defaulting to a non-committal answer. Aimed at
  deployment frequency, not at the discrimination the analyst already has.
- **Why this and not "say neutral less."** The neutral framing is an artifact of
  the dead band (§2.1). The under-deployment is not: 13–18 points of edge on
  7.8% of calls at every band tested.
- **Expected to move.** Bearish call rate up from 7.8%; overall accuracy and the
  luck-corrected gap up. Bearish *precision* down — from 59.9% toward the 46.6%
  base rate, because new calls come from weaker evidence.
- **Predicted flip count.** >200 of ~1,200 on train.
- **Falsified if.** Bearish precision falls to or below the base rate (46.6% at
  ±5%) — that means the prompt is guessing, not committing. Also falsified if
  the flip count is under ~100, which means the instruction did not take.
- **Runs on.** Train first. Tune only if it clears, and only once.
- **Pre-flight.** §2.5 screen on ~150 calls before the full round.

**P3a — guidance ledger, registered 2026-09-19** (before any spend;
`prompts/P3-guidance-ledger.md` §7, run `p3-guidance-ledger`)

- **Change.** Prepend to each call a mechanically graded table of the promises
  the prior call made and what this call reported against them; point the
  stumble test at it; ask which promise the thesis rests on. No change to the
  decision matrix.
- **Expected to move.** Bearish call rate up, concentrated on calls whose
  ledger shows `missed`, `unreported` or `withdrawn` on a guided metric.
  Bearish precision holds above the 46.6% base rate. Gap over luck up.
- **Expected concentration.** Flips concentrate in the ~73% of calls that do
  not already discuss their own prior guidance. *Diagnostic, not a gate.*
- **Expected of the neutral pile.** v6's neutral calls carry zero edge over
  their base rate (20.6%) on both splits, on 58% of calls. The ledger should
  convert some into committed answers that beat their base rate. Report the
  neutral share before and after. *Diagnostic, not a gate.*
- **Measured but not instructed: the bullish side.** 5d-ii, `N_eligible_bull`,
  bullish precision against 32.8%, bullish movement in the clean-beats group.
  This candidate's text does not address beats; bullish movement falsifies
  nothing here and pre-registers nothing for later.
- **Predicted flip count: 150-300 net** of the pure-noise rate (arm 21a), raw
  count reported beside it.
- **Falsified if** (all net): fewer than ~100 flips net of noise; **or**
  bearish precision at or below 46.6% (bearish-only by design); **or** flips
  concentrate in calls whose ledger shows no miss; **or** the instruction-effect
  arm (21b) exceeds the pure-noise arm (21a) by more than its own range (a
  confound on the headline, reported prominently).
- **Runs on.** Train. Tune only if it clears, and only once.
- **Pass A standalone success.** Fidelity drop rate under 5% and ledger
  coverage >= 90% of resolved predecessor-bearing train calls, whether or not
  Pass B runs.

**P3b — the analyst's own prior watch condition as a second ledger input.
Named, NOT run.** Add the analyst's own "measurable condition that would change
this recommendation" from call N to the ledger at N+1. Sequential by
construction, so it cannot batch. **Why it is named now:** naming the follow-on
before P3a's per-call diffs exist commits it in advance, so no later session
can back its next candidate out of those diffs and call it design. Same
discipline section 2.6 imposes on the auto-iterate loop. **Prohibition:** any
candidate other than P3b derived from reading P3a's diffs must go through the
section 2.6 split-half screen before it may touch tune.

**P6 — output-format round, registered 2026-09-24.** Three arms, one round,
named before any runs. Decided in conversation 2026-09-24 against the
2026-09-23 state of play; the reasoning is recorded here so it is not
re-derived.

*Why this and not another input.* Every candidate to date added information
to the prompt (prior-call ledger, market reaction) and none paid. The one
lever never pulled is the prompt's own shape. Two observations drive the
round: (1) the neutral pile — 58% of answers, zero edge on both halves — is a
**rule artifact**: the decision matrix maps *Intact + no stumble → Hold* after
the model has read the call, so whatever it read is compressed to nothing
before it reaches the score; (2) the v6 rubric was built to encode investing
discipline and cut run-to-run variance, never because any section improved
the six-month call, and it has never had a control.

- **Arm A — v6 incumbent.** Unchanged.
- **Arm B — minimal prompt (the control).** No rubric. Carries only: the
  objective (beat or lag the S&P over the next two quarters), the constraint
  (this transcript only), the output (score −5..+5, an explicit `no read`
  option, three-sentence rationale citing evidence), and one framing question
  — *what in this call should change what a well-informed holder believes?*
  Expected to lose to v6. If it matches v6, the rubric is not where the signal
  is and future iteration starts from the minimal prompt.
- **Arm C — v6 with the decision matrix replaced by a continuous score.** The
  rubric is kept; the matrix is removed as the output. The analyst emits the
  −5..+5 score plus `no read`; Add/Hold/Trim/Exit become thresholds applied
  allocator-side, tunable without re-scoring. Firewall preserved.
- **Ruler.** Money (2026-09-20 state of play), with accuracy alongside. For
  arms B and C the primary test is **rank-ordering across all ~2,385 calls**
  — do the +5s beat the +2s, do the −4s lag the −1s — which uses every call
  rather than 177 bearish ones and sidesteps the resolution limit in the
  2026-09-23 state of play §4.4. Severity grading (§3.3 there) is subsumed.
- **Expected to move.** Arm C: neutral share falls well below 58%; the calls
  that leave neutral show a non-zero edge; score deciles order forward
  returns monotonically. Arm B: unknown — that is the point of a control.
- **Predicted.** Arm C beats arm A on rank-ordering. Arm B lands between them
  or matches A. Written down so it can be wrong.
- **Falsified if.** Arm C's score deciles do not order forward returns (rank
  correlation indistinguishable from zero on train); **or** the neutral share
  does not fall; **or** the net flip count sits below the corrected noise
  floor. Arm B cannot be falsified — it is a control — but a B ≥ A result is
  the finding that redirects the queue.
- **Noise.** Every arm carries the paired v6 re-score noise arm from
  `prompts/P3-guidance-ledger.md` §5f (21a), per stratum, and the corrected
  flip-count rules from the 2026-09-23 state of play §4.2 **must land before
  this round runs.**
- **Runs on.** Train. Tune only for an arm that clears, and only once.
- **Cost.** ~$45 per arm plus the noise arm; ~$100–110 total.

**P7 — three-voices rubric. Named, NOT run.** A short rubric with a mechanism:
tabulate what the CFO's numbers say, what the CEO claims beyond them, and what
the analysts actually pressed on (not the pleasantries — the question asked
three ways, the deflected answer), then score the gap between the first and
the other two. This is the expectations-gap question asked of the transcript
alone, without consensus data. Named now so it is committed before P6's diffs
exist. Runs only after P6, and starts from B.

**P7 — pre-registration, registered 2026-09-26** (copied from `prompts/P7-three-voices.md` §4 before any scoring; candidate `docs/prompts/candidates/EVALUATION_PROMPT_P7_three_voices.md`, sha256 `0a34f5a9…bcaf`, parent P6B-minimal)

- **Change.** Add a three-voices section (numbers / claims / pressure / gap) to B before its READ, plus structured fields `gap` and `pressure`. Everything else is unchanged.
- **Expected to move.** The bullish side: the top 235 by score get more hits and a higher median return. Ranking strength rises slightly. The bearish side is roughly unchanged.
- **Predicted flip count.** P7 against B draw 1, direction under ≤ −2 / ≥ +3: **250–400 raw**, i.e. **~100–250 net** of B's 152 noise changes.
- **Pre-flight stop rule (§2.5).** 150 train calls, stratified by `stratum_map()` (S1–S5, proportional, at least one S4 call). If P7 and B draw 1 disagree on direction on **under 20% of them**, **stop.** Also stop on any parse failure, `max_tokens` stop, `gap` or `pressure` value outside its three allowed values, or a projected full cost over $40.
- **Gates (all three on train, each against BOTH B draws, §2.3a rule 3) for P7 to earn one look at tune.** (1) Top 235 by score (ties by the seeded rule, seed 11) right on **at least 47.0%** (B: 39.6% / 36.2%). (2) Paired rank-correlation difference (P7 minus B, ticker-block bootstrap, 2,000 draws, seed 11) has its range's lower end **no worse than −0.03**. (3) Bottom 191 by score right on **at least 57.0%**.
- **Falsified** if gate 1 fails. If gate 1 holds and gate 2 or 3 fails, the bullish gain was bought elsewhere; P7 does not go to tune.
- **Ambiguity rule.** Gate 1 within 43.6–50.4%, or gate 2's lower end within −0.06 to 0.00: a single draw cannot settle it. Report as ambiguous; a second P7 draw (~$33) is recommended but NOT approved and NOT run.
- **Predictions, not gates.** Top-235 median return above +1.28 on both comparisons. Rank correlation 0.12–0.17. `gap` shares: claims_ahead 30–45%, aligned 35–50%, numbers_ahead 10–25%. `pressure` `answered` 40–60%. P7 costs 10–25% more per call than B. `numbers_ahead` + `answered` is the cell that carries the bullish edge.
- **Runs on.** Train only. Cost ~$38, hard cap $45.

**P7 — Result, 2026-09-26 (train; `wrap-ups/P7-three-voices-train-out.md`, `p7-three-voices-train/results.json`).** Gate 1 failed: top 235 right 31.5% vs the 47.0% target and B's 39.6% / 36.2% (`matched_coverage.P7.top235`); gate 2 failed against draw 1 (−0.017, range −0.050 to +0.016) and held against draw 2; gate 3 held (58.6% vs 57.0%). The model labelled 78.8% of calls `claims_ahead` and 79.7% `avoided` (`shares_pct`), so the labels could not separate companies; the predicted carrier cell (`numbers_ahead` + `answered`, 55 calls) was right 25.5% against a 33.2% base rate (`gap_x_pressure`). Gate ledger entry 3, cost $34.07.
**A reworded three-voices prompt is not queued: the groups the labels did form showed no bullish edge.**

**P9 — pre-registration, registered 2026-09-26** (copied from `prompts/P9-expected-return.md` §4 before any scoring; candidate `docs/prompts/candidates/EVALUATION_PROMPT_P9_expected_return.md`, sha256 `a752e6b1…06a5`, parent P6B-minimal)

- **Change.** B's final answer, a −5..+5 score, becomes an expected six-month return versus the S&P in points, with a low–high range. The reading (B's text through READ) is unchanged.
- **Groups.** P9 has no thresholds. Its **bottom 191** by `expectedReturn` are "bearish", its **top 235** "bullish", the rest "neutral" (§2.3a rule 1, matched to B draw 1's counts); ties by the seeded rule, seed 11. Every comparison with B uses these groups.
- **Pre-flight stop rules (150 train calls, stratified by `stratum_map()`, at least one S4).** Stop if any: parse failure or `max_tokens` stop; `rangeLow ≤ expectedReturn ≤ rangeHigh` broken on more than 3 calls; **bunched** (middle half of `expectedReturn` spans under 4 points, or fewer than 8 distinct values); **one-sided** (more than 85% on the same side of 0); `noRead` on more than 10% of calls; projected full cost over $36.
- **No disagreement threshold.** §2.5's "fewer than ~100 flips, stop" rule does not apply: P9's value can come from its units even if it orders calls exactly as B does (arm C is the precedent).
- **Gates (all three on train for one look at tune; 2 and 3 against both B draws).** (1) **Calibration sign:** slope of realized return on `expectedReturn`, realized clipped at ±50 (set to ±50, not dropped), ticker-block range (2,000 draws, seed 11) entirely above zero; unclipped slope reported beside it; clip level fixed. (2) **Ranking non-inferiority:** paired rank-correlation difference (P9 minus B) lower end no worse than −0.03 against each draw. (3) **Bearish hits:** P9's bottom 191 right on at least 57.0%.
- **Falsified** if gate 1 fails. If gate 1 holds and gate 2 or 3 fails, the new unit cost information B had. P9 does not go to tune.
- **Ambiguity rule.** If gates 1 and 3 hold and gate 2's lower end lands between −0.06 and 0.00 against either draw: report ambiguous, recommend a second draw (~$30), do not run it.
- **Severity, reported not gated.** (a) rank correlation of predicted vs realized inside P9's bottom 191, ticker-block range, beside B's on each draw; (b) realized median return by fifth of `expectedReturn`, beside B's by fifth of `score`. **Reading:** P9 grades severity if (a)'s range excludes zero **and** the lowest fifth's median is below the second fifth's; if neither, "same information, better units"; if only one, say so and do not characterize further.
- **Predictions, not gates.** Median `expectedReturn` +2 to +8, 55–75% positive; middle half spans 6–15 points (realized 24); clipped slope 0.2–0.6; 50–70% of outcomes inside the stated range; rank correlation 0.10–0.15; cost within ±15% of B's per call.
- **Runs on.** Train only. Cost ~$32, hard cap $40; a second draw is not approved.

**P9 — Result, 2026-09-26 (train, two draws; `wrap-ups/P9-expected-return-train-out.md`, `wrap-ups/P9-second-draw-out.md`).** **Falsified:** draw 1 held all three gates but was ambiguous (gate 2 lower end −0.016 vs B draw 1); on draw 2 gate 2 failed against both B draws (−0.020, range −0.071 to +0.032; +0.011, range −0.039 to +0.059), so 5 of 6 checks held. **Severity is confirmed on two draws**: rank correlation inside the bottom 191 was 0.257 and 0.184, both ranges above zero, and the lowest fifth's median was below the second's on both; B's within-bearish ranges include zero. Cause: P9 wobbles more than B between identical runs (17.0% group changes vs 12.5%; rank difference 0.060 vs 0.031; ledger entry 4, cost $60.31). Averaged B vs averaged P9 is in `wrap-ups/P9-close-and-averaged-comparison-out.md` (Step 2).

**P8 — auto-iterate loop. Named, NOT built. Generator, never judge (§2.6),
with four constraints added 2026-09-24:**

1. **The iterating model already knows how these stocks did.** Trained on
   2020–2025, it knows the outcomes; shown wrong calls plus outcomes, its path
   of least resistance is a rule that proxies memorized results. Therefore:
   **every proposed rule must be stated as a mechanism a human can read and
   reject** — "companies giving segment-level guidance are more credible" is
   admissible; "weight paragraph 4 sentiment" is not. Luis vets the list. A
   rule that cannot be explained is treated as recall, not insight. Ticker
   names and dates are stripped from what the generator sees; this reduces
   the easiest route and removes none of the rest (`DESIGN_PRINCIPLES.md` §4).
2. **Split time-forward, not company-wise.** More tickers in one window are
   correlated draws from one regime, not independent evidence. Iterate on
   2020–2022, screen on 2023–2024, holdout 2025 locked. The question is
   regime transfer, and only a time split asks it.
3. **Fixed candidate budget per round, all logged in the ledger, survivors or
   not.** The stopping rule is the budget, never a target accuracy — "continue
   until X%" guarantees that noise eventually delivers X%. The honest result
   of a round may be that nothing survived.
4. **Screen on the P6 continuous ruler and require the survivor to beat the
   noise floor on the screening period**, not the iteration period. A 300-call
   subset carries a ±4-point noise band; greedy iteration on it climbs noise.

Cost: the generator is nearly free (eval files on disk, no scoring); each
surviving candidate costs one scoring round (~$45) to screen. Budget three
survivors per cycle. Sequenced after P6 because P6 decides whether the loop
iterates on the rubric or on the minimal prompt.

### 2.3 Pre-registration — required before any candidate is run

Fill this in, in this file, **before** the round. Six candidates screened on one
sample hand back a winner that looks about 1.5 points better than it is; twenty
candidates about 2.45 points — the size of the effect currently under
investigation.

For each candidate: the change in one sentence · what it is expected to move and
in which direction · **predicted flip count** (see 2.4) · what result would
falsify it · which split it runs on · the date it was registered.

Name the two or three candidates to be tried **before running any of them.**

### 2.3a Rules every B-derived pre-registration follows

Decided 2026-09-26 (`docs/handoffs/2026-09-26-next-steps-review-reply.md` is the
source). Every P7 / P9 / model-gate pre-registration written into §2.3 carries
these, stated in its own words with its own numbers.

1. **Matched coverage, both sides.** Bullish: the candidate's top N calls by
   score against B's top N, N = B's bullish count at ≥ +3 on the same split
   (train 235, tune 242). Bearish: the bottom N, N = B's bearish count at ≤ −2
   (train 191, tune 161). Ties broken by the seeded rule. The fixed cuts are
   reported, labelled secondary.
2. **Ranking tolerance.** The paired difference in rank correlation (candidate
   minus B, same calls) must have its range's lower end no worse than
   **−0.03**. Measured 2026-09-26: B asked the same 1,217 train calls twice
   ranked at 0.130 and 0.099, a paired difference (original minus re-run) of
   +0.031 with a ticker-block range of 0.005 to 0.058; half-width 0.027, rounded
   out to two decimals = 0.03, so the tolerance is −0.03 (the earlier
   placeholder happens to equal it). Source:
   `analysis/data/run_state/b-champion-and-noise-floor/results.json` →
   `rank`; `findings.md`. Note the two identical runs already differ with a
   range that excludes zero, so a candidate's range is read against B's spread,
   not against zero.
3. **Two baseline draws.** Every candidate is compared with **both** B runs
   (original and re-run) and both differences are reported. Beating one and not
   the other is a tie.
4. **The end-to-end check vetoes, never picks.**
5. **For P9 (expected return):** the gate is a positive slope of realized on
   predicted return, with its range excluding zero. The slope's value (the
   allocator-side scale factor) and realized medians by fifths are reported,
   not gated. Predicted slope 0.2–0.6, written as a prediction.
6. **The most-recent-year result** for the model gate is a diagnostic, not a
   gate (~170 calls).

### 2.4 Required diagnostics after every round — all free, no model calls

A round that reports only a headline has wasted most of what it bought.

1. **Flip count** against the incumbent on the shared calls, and the win rate
   among flips. **The count that is read is the NET count: raw flips minus the
   incumbent's own noise flips (amended 2026-09-26), never raw.** v6's noise
   floor is ~17% (tune 17.7%, train 16.7%). For a B-derived candidate the
   incumbent is B, and its floor is B's own, measured in
   `b-champion-and-noise-floor` step 2: **direction changes under ≤ −2 / ≥ +3
   on 1,217 train calls: 12.5% pooled (Wilson 10.8–14.5%); S1 16.6%, S2 12.0%,
   S3 10.5%, S4 0.0% (n=16, too few), S5 11.6%** (rates across calls; source
   `results.json` → `pooled.direction_change`, `per_stratum.*.direction_change`).
   Score moved by ≥ 1 on 30.9% and by ≥ 2 on 8.9%. B's second draw is
   `analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl`. A paired comparison lives entirely on the disagreements.
2. **The confusion table** — did the neutral pile shrink, and did new bearish
   calls hold precision above the 45–48% base rate?
3. **Per-call diffs written to disk**, so a later round can re-read them.

A change that flips few calls has a hard ceiling regardless of how good it is:

| calls flipped (of ~1,200) | most it could possibly gain | flips that must be won | smallest visible gain |
|---|---|---|---|
| 40 | 3.2 pts | 29 of 40 | 1.4 pts |
| 100 | 8.1 pts | 64 of 100 | 2.3 pts |
| 200 | 16.2 pts | 120 of 200 | 3.2 pts |
| 400 | 32.4 pts | 228 of 400 | 4.5 pts |

Binomial, therefore optimistic — the ticker-block bootstrap gives wider ranges.
**"The idea failed" and "the idea barely fired" are different conclusions and
the headline cannot tell them apart.**

### 2.5 Pre-flight screen — run before committing a full round

Score ~150 calls (~$6) and count disagreements with the incumbent. If the
implied corpus-wide **net** flip count (raw minus the incumbent's own noise
flips; amended 2026-09-26) is under ~100, **do not run the full round.** The
change cannot clear the noise floor whatever the reasoning behind it.

P7 passed its pre-flight at 20.7% disagreement against a 20% threshold and then failed; disagreement is not improvement. Pre-flights for candidates with new output fields also stop when those fields behave far outside their predictions (see the P9 draft). *(added 2026-09-26)*

### 2.6 Automated iteration — generator, never judge

Feeding the model its own wrong calls plus the realized outcome and asking what
pattern it missed is nearly free (existing eval files, no re-scoring) and is
worth building as a source of hypotheses.

**Such a loop must never also select.** It will not try twenty candidates, it
will try two hundred, and the winner of two hundred is noise with a good story.
Design that keeps it honest: **split train in half** — the loop iterates freely
on train-A, survivors are screened on train-B, and only what survives both
reaches tune. Tune evaluations stay hand-counted and pre-registered. Holdout
stays locked.

**Amended 2026-09-26.** The time split (iterate 2020–2022, screen 2023–2024, on
train companies only) constrains P8's generator. The company split is the
promotion gate for its survivors. "Holdout 2025" is dropped; the 53-company
holdout is the holdout.

---

## 3. Standing limits that apply to every candidate

- **Model confound.** All current figures are `claude-sonnet-4-6`. v6's original
  40.4%/39.6% came from `claude-sonnet-4-20250514`, retired 2026-06-15. Any
  weakness *or* the positive gap may be the model rather than the prompt, and
  available data cannot separate them. Both baselines share the model, so
  train-vs-tune is paired; anything compared against the legacy figures is not.
- **The gap is a cheap proxy for dollars, and an imperfect one.** It counts every
  call equally; the portfolio does not. See §3.1a R2.
- Sector-relative grading (F2) unresolved — everything is benchmarked against SPY.
- Holdout is locked and unscored.
