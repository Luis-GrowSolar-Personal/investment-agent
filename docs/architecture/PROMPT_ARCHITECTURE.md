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
| P1 | **Commit to bearish when the evidence supports it** | none | — | **ready — run first** |
| P2 | Post-call reaction at K≥1, three arms | none (price cache) | §3.1a R3 | blocked |
| P3 | Thesis / guidance ledger — score QN−1's promises at QN | none (transcripts on disk) | — | ready |
| P4 | Tier-conditioned reading of financial facts | XBRL build | P3 | not started |
| P5 | Peer read-through across cohort members | none (transcripts) | — | not started |
| **P6** | **Output-format round: v6 vs minimal prompt vs continuous score** — three arms, one round | none | flip-count rules corrected (2026-09-23 state of play §4.2) | **registered 2026-09-24 — run next** |
| P7 | Three-voices rubric (CFO numbers / CEO claims / what analysts pressed) | none | P6 | named, not run |
| P8 | Auto-iterate loop as hypothesis generator (§2.6, with the 2026-09-24 constraints) | none (eval files) | P6 | named, not built |

P2 is blocked on a free decision (R3's grading-window rule), not on work. P1 and
P3 can both run today against the existing corpus — no vendor fetching, no new
transcripts.

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
exist. Runs only after P6, and starts from whichever of arm B or arm C P6
favours.

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

### 2.4 Required diagnostics after every round — all free, no model calls

A round that reports only a headline has wasted most of what it bought.

1. **Flip count** against the incumbent on the shared calls, and the win rate
   among flips. A paired comparison lives entirely on the disagreements.
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
implied corpus-wide flip count is under ~100, **do not run the full round.** The
change cannot clear the noise floor whatever the reasoning behind it.

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
