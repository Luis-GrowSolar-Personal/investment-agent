# Promotion Gate — Evaluation & Change-Control Methodology

**Status:** Locked 2026-05-23; two-hurdle extension 2026-05-23b.
**Purpose:** Nothing in the analyst/allocator stack goes live until a candidate
beats the incumbent on a *pre-registered* metric, *out-of-sample*, by *more than
measured noise*. The gate is the disciplined, repeatable version of what has so far
been done by hand (allocator v1→v4, prompt v5→v8, the classifier sweeps).

This document is the single source of truth for how infrastructure changes are
evaluated and promoted. Read `DESIGN_PRINCIPLES.md` (backtest integrity, firewall)
before touching it.

---

## 1. When it runs

Manual, on-demand. Luis invokes the gate when he has a candidate; it returns a
verdict report. Nothing auto-promotes. (CI-style automation is a deferred upgrade,
not the MVP — see Open items.)

A gate run is warranted whenever "something important" changes in the
infrastructure layer:
- a new candidate prompt version (analyst)
- a new Claude model version (analyst)
- a new combination of existing parameters (allocator: caps, max-per-type, profit-take, etc.)
- a new candidate parameter being introduced (allocator)

---

## 2. Change taxonomy — and the rigor each gets

The two classes need different machinery because they differ in cost, determinism,
and overfitting risk.

### 2.1 Allocator-layer changes
Cap %, max-per-type, profit-take threshold, a new sizing parameter, etc.
- Run against the **frozen evaluation cache** — no API calls, deterministic, cheap.
- Hundreds of combinations testable in seconds. **That cheapness is exactly why this
  layer carries the highest overfitting risk** (it invites a parameter search).
- **Rigor:** strict recent holdout (§7) + complexity penalty (a new knob must earn
  its keep; ties go to the simpler config — as when the variable Type B cap was
  retired 2026-05-17).

### 2.2 Analyst-layer changes — two sub-classes

Both require **re-evaluating transcripts through the LLM** against a version-stamped
cache. Costly, non-deterministic, and they change the *inputs* to everything
downstream.

#### 2.2a  Prompt / eval-logic changes
A new prompt version, revised scoring criteria.
- Few candidates; not a parameter search (one fixed thing vs another),
  so multiple-comparison risk is low.
- **Hurdle: improvement.** Promote only if the challenger clearly beats the
  champion — lift must exceed the noise threshold (§6). Ties keep the incumbent.
- **Rigor:** full-sample comparison + effect-size threshold + robustness checks.

#### 2.2b  Claude model-version changes
Adopting a newer Claude release (e.g. sonnet-4-20250514 → sonnet-4-6).
- **Hurdle: equivalence.** Promote unless the challenger clearly *regresses* —
  i.e., the lift falls more than 1 bootstrap SD *below* the champion.
- **Rationale:** the incumbent model will eventually be deprecated by Anthropic.
  A forced, unvalidated migration under time pressure is worse than adopting a
  statistically equivalent newer model on a known schedule. An equivalent result
  is sufficient grounds for adoption; only a clear regression blocks it.
- **Holdout:** skipped for EQUIVALENT results — there is no improvement claim to
  validate out-of-sample. Holdout is consumed only if the challenger is clearly
  *better* (PROMOTE verdict on the training window).
- **Rigor:** same noise threshold and per-ticker robustness as 2.2a, but applied
  symmetrically (regression detection rather than improvement confirmation).

---

### 2.3 Implementation-layer changes

Production code that implements a design the gate has already adopted — the
allocator running inside the app, rather than the simulator that validated it.

The question is different in kind from 2.1 and 2.2. Those ask *should we adopt
this design?* This one asks **did we build the design we adopted?** That is a
question about fidelity, not performance, and statistics do not apply to it:
there is no noise band, no bootstrap SD, no champion lift to beat. The validated
simulator is not a benchmark to outperform — it is a **specification to
reproduce**.

**Nothing in 2.1 catches a failure here.** An allocator-parameter gate run
replays the *simulator* against the frozen evaluation cache and never executes
production code, so it cannot notice that production disagrees with it. Task #77
sized positions roughly 11x away from the validated model and would have passed
2.1 unchanged.

**Hurdle: fidelity.** Two verdicts, not three — see 5d.

**What is compared: the decision stream, not the dollars.**
The unit of comparison is the ordered list of trade decisions:

    (session date, ticker, side, shares, account)

Every field must match exactly. Dollar values, portfolio totals and returns are
**reported as diagnostics and are not gated.** Two reasons, and the second
matters more:

1. Bit-exactness between the Python simulator and a JavaScript production path is
   not achievable and not worth chasing. Float accumulation order differs; a
   dollar-level gate would fail for reasons unrelated to correctness, and the
   standing response to a nuisance failure is to widen the tolerance until it
   stops meaning anything.
2. **A decision-stream diff is diagnostic; a dollar gap is not.** A dollar gap
   says only that something, somewhere, is wrong. This project has already paid
   for that lesson: two CLI sessions were spent chasing a $626 gap that turned
   out to be an artifact of comparing a median against a forward draw, while a
   `funding_log` diff in the same window localized a real defect in one reading —
   *entries 0 through 75 match, entry 76 does not.* The gate should produce the
   second kind of output.

Dollars still earn a **reported** band: agreement within 0.01% of final portfolio
value is expected, and a larger gap on an otherwise-identical decision stream is
a finding worth investigating — it means the two paths priced or accounted the
same trades differently — but it does not block promotion on its own.

**What this gate does not test.** It is a conformance check on the decision
layer and nothing else:
- **execution** — slippage, partial fills, rejections, order routing. The
  simulator models none of these, so a passing gate says nothing about whether
  the order leaving the app fills at the price the model assumed. That is the
  safety scaffolding `CLAUDE.md` Step 8(a) calls for, and a separate problem.
- **the analyst** — fixtures carry stored scores as inputs; analyst quality is
  2.2's business.
- **the UI** — a correct decision stream reaching a broken screen still passes.
- **input assembly** — and this is the important omission. A fixture hands the
  allocator a *given* state and checks the trades that come out. It does not
  check that the app assembles that state correctly from the database and the
  broker. `ALLOCATOR_OPERATING_MODEL.md` §9 invariant #5 (no trade set sized
  against stale state) and §11 defect #2 (starter and Add sized against the same
  stale cash snapshot) are precisely input-assembly failures, and fixtures are
  blind to them by construction. Tier 2 below exists for this.
- **anything outside the fixture window** — conformance over
  2022-01-01 to 2024-06-12 is evidence, not proof, that the two implementations
  agree everywhere.

**Input pinning is a release dependency.** The comparison is meaningful only if
both sides receive identical inputs, which makes these release artifacts rather
than working files: the frozen caches (`price_cache.json`,
`fundamentals_cache.json`, both at 2026-05-11), the stored `Analysis` rows for
the fixture window, and `type_classifications.json`. Per 10b of
`ALLOCATOR_OPERATING_MODEL.md` they are archived alongside the fixtures and
referenced by hash. **The corpus dump is therefore a release dependency, not just
a backup** — the model that produced it is retired, so an unbacked corpus is an
unreproducible gate.

**How it is run: two tiers, both required, neither of them a UI.**

| Tier | What it feeds the allocator | What it catches | Cadence |
|---|---|---|---|
| **1 — golden fixtures** | State supplied by the fixture | The decision function diverging from the validated model | CI, every commit |
| **2 — headless replay** | State the app assembles itself, from a seeded database, advanced date by date | Input assembly: stale cash, mis-aggregated per-account state, drift accumulating across sessions | Per release |

Tier 1 is `CONFORMANCE_FIXTURES.md`: `(event, portfolio state, expected trade
list)` triples dumped by the simulator, asserted by production's own test suite.
It is cheap, it fails with a line number, and it isolates the decision layer.

Tier 2 closes tier 1's blind spot. It is a **driver, not a screen**: seed a test
database at the window's start, then run the app's real session entry point
forward over the window — the same code path the scheduler will call — and
compare the whole emitted decision stream against the simulator's. Nothing is
rendered and no user is present. It is meaningfully cheaper than an in-app replay
because it needs no simulation clock in the UI, no resettable account model
exposed to a user, and no historical prices in the front end; it needs a seeded
database, a date loop, and the trade stream the app already has to produce.

**Neither tier requires a user interface.** An instrumentation UI is a product
feature with its own justification, deliberately not the release gate — see
§10.

---

## 3. Metrics — two layers, both always reported

### 3.1 Analyst-direct metric (Layer 2 quality)

**CORRECTED 2026-09-13 (`prompts/scorecard-repair.md`, `wrap-ups/scorecard-repair-out.md`).**
Stage B (`value-attribution-and-headroom-v2`) established that the metric below
(lift over a fixed-answer guesser) grades against whichever dummy is chosen, and
attaches no margin of error to anything — the same 359 calls score −5.8pp
against an always-bullish guesser and +28.7pp against an always-flat guesser,
and neither figure carries a confidence interval. `scorecard-repair` replaced it
with two metrics that correct for how often each answer happens purely by base
rate, and both are reported with a 95% range and this section's detection
threshold:

- **Luck-corrected gap** — observed accuracy minus the accuracy expected from
  guessing in proportion to how often the analyst says each answer and how
  often each outcome actually occurs ("expected-by-luck"). On the 359-call
  scorer population: **0.82pp** (95% range **−2.36 to +3.89pp — spans zero**).
  On the 195-call simulator population: **0.11pp** (95% range **−4.82 to
  +4.47pp — spans zero**). Neither population currently shows a detectable
  edge over chance by this measure.
- **Balanced accuracy** — the average of the three per-answer hit rates
  (recall on bullish, bearish, and neutral outcomes), which does not reward
  always guessing the common answer. Scorer population: **31.3%** (95% range
  27.75–34.7%). Simulator population: **29.6%** (95% range 25.74–32.79%).
  (A three-way guesser with no skill scores 33.3% on this measure.)

**Detection threshold, on the scorer population (n=359, 16 tickers):** the
smallest prompt-accuracy improvement this scorecard detects in at least 80% of
resamples is **12 points when two prompts are scored on different samples
(unpaired)**, and **6 points when scored on the same calls (paired)** — full
curves and the disagreement-rate sensitivity in
`analysis/data/scorecard_repair/scorecard_repair_manifest.json` →
`results.step3_detection_threshold`. A realistic single-iteration prompt
improvement is 2–4 points. **On this corpus, at this sample size, ordinary
prompt iteration is not reliably measurable even in the paired design**, and is
far out of reach unpaired.

**Standing rule, binding immediately: no prompt-versus-prompt comparison may be
cited going forward unless it reports the paired difference, its 95% range, and
whether that range excludes zero.** A point-estimate comparison (e.g.
"37.5–42.5% vs 37.5%") is not a citable result under this section.

**§3.1-legacy (superseded, preserved below — do not delete).** Every existing
benchmark record in `VERSION_REGISTRY.json` was computed under the always-
bullish-lift definition below, and those records remain readable only under
that legacy definition; this correction does not retroactively recompute them.
Superseded because Stage B showed the verdict flips depending on which fixed-
answer dummy is chosen, with no interval attached to distinguish a real
difference from noise.

Isolates analyst quality from allocator behavior. **Primary gate for analyst-layer
changes.**

**Predictand.** Every call collapses to a direction:
- bullish = buy / add / "strengthening"
- bearish = trim / exit / "weakening"
- neutral = hold / monitor / "stable"

**Ground truth.** Benchmark-relative forward return — the stock's return *minus* its
benchmark over the horizon. Benchmark = the stock's sector ETF where one applies
(e.g. TAN for solar), else SPY. Benchmark-relative (not absolute) so a bull-market
beta doesn't masquerade as skill; this measures *selection*.

**Horizon.** 2 quarters (~6 months) forward from the call date. (1Q is mostly noise;
4Q blurs attribution as later calls overlap.)

**Dead-band.** ±5% benchmark-relative = "flat." A correct neutral call is one where
the stock genuinely went sideways. Without the band, neutral calls are unscorable.

**Hit rule.**
- bullish → hit if benchmark-relative 2Q return > +5%
- bearish → hit if benchmark-relative 2Q return < −5%
- neutral → hit if within ±5%

**Scoring.** Report as **lift over an always-hold baseline**, broken out by call
type (bullish / bearish / neutral). Rationale: an always-"bullish" coin scores
~55–60% in a bull sample, so raw accuracy is misleading; and trim/exit calls are
rarer and more consequential than holds, so they must be graded separately or a
"hold-forever" model scores deceptively well.

**Worked example.** An ENPH call grades "weakening/trim" in Qx → compare ENPH vs TAN
over the next ~6 months. ENPH lagged TAN by >5% → hit. Beat TAN by >5% → miss.
Within ±5% → it should have been "hold," so it's a wash.

### 3.1a Open ruler-design questions (raised 2026-09-17 — NOT adopted)

**Status: OPEN. Nothing in this subsection changes the gate metric.** These are
three decisions about what §3.1 should measure, surfaced while reading the
train and tune baselines. Each is free to settle (scorer-only, no model calls).
They are filed here rather than in a handoff doc because §3.1 is where the code
and any future session look for the metric's definition.

Evidence throughout is the pooled train + tune eval caches
(`analysis/data/evals/v6_claude-sonnet-4-6{,_tune}`, 2,404 gradable calls,
WOLF/SPWR excluded per `wrap-ups/baseline-v6-tune-batch-out.md` §2c) graded via
`analysis/analyst_direct_scorer.py`.

#### R1 — Is the ±5% dead band the right width?

**Open, but it blocks nothing. Demoted from blocker 2026-09-17, same day it was
raised.** R1 was briefly recorded as gating the first prompt candidate, on the
reasoning that "v6 over-calls neutral" might be a ruler artifact rather than a
prompt flaw. Two checks retired that reasoning:

1. **v6's bearish-call edge is band-independent.** It says bearish on 187 of
   2,404 pooled calls (7.8%) and beats the base rate by 13 to 18 points at every
   width — ±5%: 59.9% vs 46.6%; ±10%: 52.4% vs 35.8%; ±15%: 40.6% vs 25.8%;
   ±20%: 35.3% vs 17.7%. The actionable finding survives any answer to R1.
2. **A wider band does not make improvements easier to detect.** Ticker-block
   bootstrap on the gap, 2,000 resamples, seed 20201231: 95% width is 3.40
   points at ±5%, 3.63 at ±10%, 3.80 at ±15%, 4.07 at ±20%. Wider bands give
   slightly *wider* intervals, not tighter ones.

So R1 changes how flattering the scoreboard looks and whether "v6 over-calls
neutral" is a fair criticism. It does not change what to build, and it does not
change detection power. Settle it for honesty about what the metric means, not
as a prerequisite for anything.

§3.1 fixes the band at ±5% benchmark-relative over 2 quarters. That choice
determines the label for **all three** answers, not only neutral, and it is
currently unexamined.

Outcome distribution and v6's score at several widths (v6 pooled says bullish
33.5% / neutral 58.1% / bearish 7.8%):

| dead band | lagged | beat | tracked | v6 accuracy | expected by luck | luck-corrected gap |
|---|---|---|---|---|---|---|
| ±5% (today) | 46.6% | 32.8% | 20.6% | 29.3% | 26.8% | +2.53 |
| ±7.5% | 40.9% | 28.5% | 30.6% | 32.8% | 30.7% | +2.10 |
| ±10% | 35.8% | 24.6% | 39.6% | 36.7% | 34.2% | +2.50 |
| ±15% | 25.8% | 18.1% | 56.1% | 43.5% | 40.7% | +2.78 |
| ±20% | 17.7% | 13.3% | 69.0% | 48.4% | 46.0% | +2.45 |
| ±25% | 12.3% | 9.9% | 77.8% | 52.1% | 49.5% | +2.58 |

Two readings, both load-bearing:

1. **The gap is flat at +2.1 to +2.8 across every width.** Widening the band
   raises v6's apparent accuracy from 29% to 52% and leaves its measured edge
   unchanged. **Widening is therefore not an improvement and must never be
   adopted on the grounds that the scoreboard looks better.** Any future
   proposal to move the band states this row explicitly.
2. At ±15%, "tracked the market" is 56.1% of outcomes against v6's 58.1%
   neutral rate. v6 behaves as though calibrated to roughly ±15%, not ±5%.
   Whether that is v6 being miscalibrated or the ruler being too tight is a
   judgment about the portfolio, not a statistic: **how far must a position
   diverge from the benchmark before the allocator would act differently?**
   That question, not the table, settles R1.

**Pooled figure, recorded here because §3.1a is where it will be looked for.**
Across both baselines (2,404 gradable calls, 107 companies), the luck-corrected
gap is **+2.53pp, 95% range +0.79 to +4.19 — excludes zero** (ticker-block
bootstrap, 2,000 resamples, seed 20201231). Pooling train with tune is
legitimate *for v6 specifically*, because v6 was never selected using train; the
split exists to protect future candidates, not the incumbent. **No future
candidate may be reported on a pooled population** — §11 comparison protocol
still governs, and a candidate screened on train has used it.

Related, and unresolved since 2026-09-13: this section's corrected metric at
the top and the **"Scoring"** paragraph below disagree. The paragraph still
specifies "lift over an always-hold baseline"; `analyst_direct_scorer.py`
implements an always-**bullish** comparator (F1, §10). The luck-corrected gap
supersedes both, but the stale paragraph remains in the file and should be
resolved when R1 is.

#### R2 — Should calls be weighted by how much the stock actually moved?

§3.1 counts every call equally. A 6% relative miss on a call scores the same as
a 60% relative collapse. The end-to-end metric (§3.2) does not work that way,
so the two layers' metrics disagree about what matters, and §4 maps analyst
changes to §3.1 as the primary gate.

Proposal to evaluate: report a magnitude-weighted variant alongside the
unweighted one, weighting each call by |benchmark-relative return|. Scorer-only
change, no model calls. Expected to track dollar outcomes more closely than
equal weighting; the Test 1 gradient (~$5,825 per point of analyst-direct lift,
three-event basis, explicitly fragile) is currently the only bridge between
§3.1 and §3.2 and is too thin to carry promotion decisions.

**Do not replace the unweighted metric.** Report both, or a weighted metric
becomes a second free parameter to select on.

#### R3 — Grading window placement when the analyst sees post-call information

If the analyst is ever given information dated after the call — the case under
consideration is the post-call price reaction at K≥1 — the §3.1 window must
start after whatever the analyst saw. Today it starts at the call date, so
post-call inputs sit inside the window being graded.

Measured on train: a rule with no analyst in it at all, "predict the direction
of the first few days' move," scores

| graded from | score | expected by luck | gap |
|---|---|---|---|
| the call date (today's §3.1) | 32.9% | 26.7% | **+6.23pp** |
| after the reaction | 28.3% | 26.3% | **+2.00pp** |

(5-trading-day proxy for the reaction; a real implementation needs per-call
windows keyed to before-open vs after-close.) 336 of 1,236 train calls (27.2%)
have a first-week move large enough to clear the ±5% band on its own.

**Rule proposed for adoption at the time any post-call input is introduced, not
before:** the forward window starts at the last date whose information the
analyst was permitted to see. Re-grading the existing v6 baselines under a
shifted window costs $0 and should be done as part of settling R3, so the
comparison stays paired.

Any candidate using a post-call input is tested in **three** arms — prompt
alone, the mechanical rule alone, prompt plus input — because the mechanical
rule scores +2.00 clean against v6's +2.48, and a candidate that fails to beat
both is adding nothing over a number computable without a model.

### 3.2 End-to-end metric (portfolio outcome)
**Primary gate for allocator-layer changes.** Risk-adjusted portfolio outcome:
**return per unit of max drawdown** (consistent with Luis's stated goal of compounding
with controllable drawdowns, not chasing absolute return). Raw CAGR reported
alongside but is not the gate.

---

## 4. Metric → change mapping

| Change class | Primary gate | Secondary (no-regress) check |
|---|---|---|
| Analyst (prompt, model) | Analyst-direct hit-rate (§3.1) | End-to-end portfolio metric (§3.2) |
| Allocator (params) | End-to-end portfolio metric (§3.2) | n/a (allocator does not change scores) |
| Implementation (production code) | Decision-stream conformance (§2.3) | Dollar agreement — reported, not gated |

A change can lift one metric and hurt the other; both are always shown so that
trade-off is visible.

---

## 5. Promotion rule

The decision rule and the primary metric are **pre-registered** — declared before the
run — so the flattering metric cannot be selected after the fact.

### 5a. Three-verdict system

Every gate run produces one of three training-window verdicts, determined by how far
the challenger's lift falls from the champion's, measured in bootstrap SDs (§6):

| Δ = challenger lift − champion lift | Verdict | Meaning |
|---|---|---|
| Δ > +1 SD | **PROMOTE** | Challenger clearly better |
| −1 SD ≤ Δ ≤ +1 SD | **EQUIVALENT** | Statistically indistinguishable |
| Δ < −1 SD | **HOLD** | Challenger clearly worse — regression |

### 5b. Verdict → action mapping (by hurdle type)

The same three verdicts map to different actions depending on *why* the change
is being made:

| Verdict | Prompt / eval-logic change | Claude model-version change |
|---|---|---|
| PROMOTE | **Adopt** | **Adopt** |
| EQUIVALENT | Hold (no reason to change) | **Adopt** (avoid deprecation risk) |
| HOLD | Hold | Hold |

**Prompt changes (improvement hurdle):** promote only if clearly better.
Ties and regressions both keep the incumbent; complexity penalty applies.

**Model-version changes (equivalence hurdle):** promote unless clearly worse.
EQUIVALENT is sufficient for adoption. Holdout is not consumed for EQUIVALENT
results — there is no improvement claim to validate.

### 5c. Additional conditions for PROMOTE (both hurdle types)

1. The **secondary** metric does not materially regress (§4).
2. The gain is **not driven by a single ticker or sub-period** (robustness — §7).
   For EQUIVALENT model-version results, robustness is checked but not blocking
   (there is no concentrated gain to worry about).
3. On ties within the noise band, keep the **simpler incumbent** for prompt changes.

---

### 5d. Fidelity verdict (implementation changes, §2.3)

Implementation changes do not use the three-verdict system. Fidelity is binary:

| Decision stream vs. reference | Verdict | Action |
|---|---|---|
| Every gated field matches on every trade | **CONFORM** | Promotion permitted |
| Any gated field differs on any trade | **DIVERGE** | **Blocked** |

There is no EQUIVALENT for fidelity. A near-miss is a defect that has not been
identified yet, and "close enough" is how an 11x sizing error ships. A DIVERGE is
resolved by fixing the implementation, or by amending the design and re-running
§2.1 — **never** by adjusting the fixture to match the code.

The report on DIVERGE names the **first** diverging trade, with both sides'
`(date, ticker, side, shares, account)` and the count of trades that matched
before it. That first divergence is the finding; everything after it is
downstream noise.

---

## 6. Noise threshold — measured, not guessed

A candidate must clear the spread attributable to chance.
- **Allocator (deterministic):** bootstrap across tickers / sub-periods to estimate
  the metric's sampling spread; the improvement must exceed it.
- **Analyst (non-deterministic LLM):** re-run the evaluation N times at the chosen
  temperature and take the spread of the metric. The candidate must clear it. (This
  is the discipline behind the earlier `variance_check.py` work; temperature should
  be fixed — ideally 0 — for analyst gate runs.)

---

## 7. Out-of-sample protocol — recent holdout + scaled rigor

- **Recent holdout (default):** freeze the most recent ~12–18 months as an untouched
  test set. Tune / search on everything before it. The *final* candidate gets **one**
  look at the holdout; wins there → eligible to promote. Iterating against the holdout
  destroys it.
- **Robustness checks (always):** within the training window, confirm the gain holds
  across sub-periods and is not concentrated in one ticker (the AMPX-contribution /
  per-year slicing already done by hand).
- **Scaled rigor:** strictness scales with how much *searching* a change involves.
  A parameter sweep (high search) gets the strict holdout. A single model/prompt swap
  (no search) may use full-sample + effect-size + robustness (§2.2).
- **Walk-forward** (rolling train/test folds) is the textbook ideal but is parked: the
  ~5-year quarterly corpus yields only ~3 thin, noisy folds. Revisit once the corpus
  is materially larger.

---

## 8. Version discipline (prerequisites for the gate to mean anything)

- **Pin Claude to an immutable model ID.** You cannot run a clean before/after on a
  model change if the model drifts underneath you. (See the accidental
  `claude-sonnet-4-20250514` → `claude-sonnet-4-6` bump caught 2026-05-23 — exactly
  the event this gate exists to control.)

  **CORRECTED 2026-09-12 — this rule previously read "pin to a dated snapshot (e.g.
  `claude-sonnet-4-YYYYMMDD`), never a bare / `-latest` alias." That wording is now
  wrong and was mis-firing.** It was written under Anthropic's **pre-4.6** naming
  convention, where a dateless ID such as `claude-sonnet-4-5` was a floating alias
  that resolved to the newest 4-5 snapshot.

  **From Claude 4.6 onward the convention changed: the dateless ID *is* the pinned
  snapshot.** Per Anthropic's model-ID documentation, post-4.6 IDs
  (`claude-sonnet-4-6`, `claude-opus-4-8`, …) "are **not aliases** — they are the
  canonical, pinned snapshots themselves. Anthropic does not update existing model
  IDs; new versions ship under new IDs," and "when you use a model ID in an API
  request, the underlying model remains constant for the lifetime of that ID."

  **Consequence: `claude-sonnet-4-6` is correctly pinned and always was.** Every
  place this project flagged it as "a bare, undated alias — violates §8 — known
  forced exception" was mistaken, including `VERSION_REGISTRY.json`'s `model` note
  and the "reproducibility risk: bare alias, flagged" caveats in
  `wrap-ups/test4-analyst-noise-floor-out.md` and
  `wrap-ups/test6-look-ahead-prohibition-out.md`. **Recording the model ID string is
  sufficient provenance for a post-4.6 model.** No behavioural fingerprint is needed
  to detect silent drift, because silent drift of a pinned ID cannot occur.

  **Also verified 2026-09-12, closing an open question:** the 2026-06-27 commit
  message claimed the dated snapshot had been retired by Anthropic, and this project
  recorded that the claim was never independently checked. It is now confirmed —
  `claude-sonnet-4-20250514` **retired 2026-06-15**, with `claude-sonnet-4-6` named
  as its replacement. The June bump was forced, not careless.

  **The rule, restated:** pin an immutable ID. Pre-4.6, that means a dated snapshot.
  Post-4.6, the dateless canonical ID already is one. Never use a `-latest`-style
  floating pointer. Record the exact ID string sent to the API on every stored row
  and in every benchmark record.

- **Model retirement is a scheduled event, not a risk — plan against the date.**
  Pinning protects against silent change; it does **not** protect against the ID
  ceasing to exist. Anthropic gives **at least 60 days' notice** and publishes
  tentative retirement dates. Current position for this project:

  | model ID | role here | status |
  |---|---|---|
  | `claude-sonnet-4-20250514` | scored the corpus | **RETIRED 2026-06-15** — unregenerable |
  | `claude-sonnet-4-6` | current promoted model | Active, retirement **not sooner than 2027-02-17** |

  See §8.1.
- **Stamp every stored `Analysis` row** with `(promptVersion, modelVersion)`. The
  schema does not record this today — only `createdAt`. Add the columns so analyst
  drift is auditable forever instead of reconstructed from deploy history.
- **Version-key the evaluation cache** by `(transcriptId, promptVersion, modelVersion)`
  so analyst versions never mix and any result is reproducible.
- **Experiment ledger:** log every gate run — champion, challenger, change class,
  pre-registered metric, verdict, date. The ledger itself guards against quietly
  re-testing the same idea until it wins by luck.
- **Version the conformance fixtures** (§2.3). Each set is stamped with the
  simulator commit, the driver file, the `config_hash`, and the hash of every
  pinned input. A fixture set whose provenance cannot be established is not a
  gate, it is a guess.
- **Never regenerate fixtures to make a failing test pass.** Regeneration is a
  deliberate act, tied to a design change that has already passed §2.1, and
  recorded in the experiment ledger like any other promotion.

### 8.1 Forced-migration protocol — what a gate verdict means when declining is not an option

**Added 2026-09-12.** Everything else in this document assumes the gate can say no.
Model retirement is the case where it cannot, and this project has already lived
through it once without a procedure.

**The precedent, on record:** `gate_ledger.json` entry 1 (2026-05-23) tested exactly
the `claude-sonnet-4-20250514` → `claude-sonnet-4-6` substitution and returned
**HOLD** (`delta_pp` −7.44 against `noise_std_pp` 4.2). Three weeks later the champion
was **retired** (2026-06-15) and the migration happened anyway. The project shipped a
model its own gate had rejected, because the alternative was shipping nothing.

That is not a failure of the gate. It is a case the gate does not cover, and the
absence of a procedure for it is why the June change went in with no ledger entry and
no explicit exception recorded — still an open item in the 09-05 state of play.

**Cadence, so this is planned rather than survived.** Retirements run roughly 6–12
months per model with ≥60 days' notice. The runway that matters now:
**`claude-sonnet-4-6` retires not sooner than 2027-02-17.**

**The protocol:**

1. **Pin, and record the retirement date** alongside the ID in
   `VERSION_REGISTRY.json`. A pinned ID with an unknown expiry is only half-tracked.
   `whats_live.py` should surface days-to-retirement, so the deadline arrives as a
   countdown rather than an email.

2. **Capture the migration bridge BEFORE the retirement date.** This is the one step
   that cannot be recovered afterward, and this project has already paid for missing
   it: the corpus was scored by `claude-sonnet-4-20250514` and **cannot be
   regenerated at any price**, so no paired comparison against it is possible ever
   again. Before a model retires, score a fixed sample under **both** the outgoing
   model and its replacement, same prompt, same transcripts, same temperature. That
   paired set is what carries comparability across the gap. §11.7 already requires
   paired rows for any cross-model comparison; after retirement, pairing becomes
   impossible, so the window to satisfy §11.7 closes on the retirement date.

3. **Run the gate anyway — but as characterisation, not decision.** When migration is
   compelled, the gate is no longer asking "should we adopt this." It is asking "what
   changed, and what does that invalidate." Report the metrics exactly as §3 requires,
   and record the verdict, but state explicitly that the verdict was **not
   actionable**.

4. **Record a forced exception in the ledger,** distinct from an ordinary verdict:
   the metrics, the verdict the gate *would* have returned, the retirement date that
   overrode it, and the bridge sample that supports future comparison. A HOLD that
   shipped must be visibly a HOLD that shipped — never quietly reclassified as a pass.

5. **Mark every dependent benchmark stale on the migration date.** Any figure measured
   under the outgoing model is no longer describes the running system. This is
   mechanical if benchmark records carry the model ID (see §11.5); it is guesswork if
   they do not.

6. **Do not treat a forced migration as a promotion.** The new model is *in use*, not
   *validated*. It carries whatever the characterisation run found, including an
   unresolved regression, until a real gate can be run on a representative scope.

**Open, as of 2026-09-12:** entry 1's −7.44pp HOLD has still never been re-adjudicated
on a representative scope, and the June 2026 forced exception has still never been
written to the ledger.

---

## 9. Build sequence

1. **Version plumbing** — add `promptVersion` / `modelVersion` to `Analysis`; pin the
   model in `evaluate.js`; version-key the eval cache. (Unblocks everything below.)
2. **Analyst-direct scorer** — given cached evals + the price cache, compute the §3.1
   hit-rate (benchmark-relative, 2Q, ±5%, lift-over-baseline, by call type). Terminal
   script first.
3. **End-to-end scorer** — wrap the existing simulator to emit the §3.2 return-per-DD
   metric for a given config. (Largely exists; standardize the output.)
4. **Holdout + robustness harness** — recent-holdout split, bootstrap/variance noise
   threshold, per-ticker / per-period slicing.
5. **Gate runner + ledger** — champion-vs-challenger driver that applies §5 and writes
   the experiment ledger; prints a verdict report.
6. **Conformance fixtures (§2.3, tier 1)** — the simulator dumps golden
   `(event, state, expected trades)` triples; production asserts against them in
   CI. See `CONFORMANCE_FIXTURES.md`. **Required before `CLAUDE.md` Step 8(a)
   ships** — in-app trading places real orders, and this is what establishes that
   the code placing them is the code that was validated.
7. **Headless replay driver (§2.3, tier 2)** — seed a test database, advance the
   app's own session entry point date by date across the fixture window, diff the
   full decision stream. Catches the input-assembly failures fixtures cannot.
   Also required before Step 8(a), and the natural place §11 defect #2 gets
   proved fixed.
8. **(Deferred) CI-style automation** — run on infra change, block on regression. Only
   after the manual tool has proven itself on real candidates.

Each step ships and is usable on its own; resist building all at once.

---

## 10. Open items / deferred decisions

- **corpus-construction holdout lock (added 2026-09-14, the ONE authorized
  edit to this file made by the `corpus-construction-fix` prompt's Step E;
  updated 2026-09-14 by `corpus-fix-4-threshold-and-terminal-value`'s Step D;
  updated again 2026-09-14 by `corpus-fix-7-manifest-corrections`'s Step E;
  updated again 2026-09-14 by `corpus-fix-8-expand-to-150`'s Step E; updated
  twice more the same day by two `corpus-fix-8` follow-ups, each the ONE
  authorized edit it makes).**
  `analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json`'s holdout is now the
  164-company corpus's holdout. corpus-fix-8 added 84 companies via A10's
  registered expansion (25 S1 candidates minus 1 drop, 50 S3 candidates
  minus 3 drops, 12+1-from-reserve S2 candidates minus 1 drop; no S4
  candidate found); a first follow-up corrected a wrong finding in that
  run's own wrap-up (BK renamed/re-ticked to BNY, MAXN delisted to the OTC
  Pink form MAXNQ — both resolve cleanly and were added; IPG stays dropped
  for a corrected reason, a real merger-driven delisting by Omnicom, not
  the "provider anomaly" first claimed); a second follow-up drafted one
  reserve replacement each for the three remaining unresolved drops with no
  reserve at selection time — BLK for SCHW, WEC for ED, SIRI for IPG, all
  tested against A1/A9 before adding. No company was added or removed on
  outcome grounds at any step — see
  `wrap-ups/corpus-fix-8-expand-to-150-out.md`.
  **53 companies, stratified across S1-S5 including S4; sha256
  `909f68ccb7754384bbb9f6d5882afb1afd9cdfa317b69654eef22127e3dc1e0b`, seed
  20201231 (same seed, re-run over the 164-company corpus) — see
  `analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json`.**
  Superseded values, kept for audit trail: the 161-company (BK/MAXN
  follow-up) holdout sha256 was
  `a281a7b406f64b1af895ae5c50d730a632f26cf4ec975ef4903ff6f362edfba5`
  (`analysis/data/corpus_v2/SPLIT_V6_BK_MAXN_FOLLOWUP.json`); the
  159-company (pre-followup) holdout sha256 was
  `019eeee338e00b23d8a4c0c8e42bf032a595b374e8ebfbbf36228fe10f39a310`
  (`analysis/data/corpus_v2/SPLIT_V5_EXPANSION.json`); the 75-company (manifest-corrected)
  holdout sha256 was
  `1d05ee0496842e2dd033924ce82d387213b80f20c3e36582eabb66d33de87569`
  (`analysis/data/corpus_v2/SPLIT_V4_MANIFEST_CORRECTIONS.json`); the
  77-company (RMO-removed, pre-manifest-correction) holdout sha256 was
  `5ab7ef18c3e3f22160f6b6ae60a82c99638b70c26b1c17d6477e6b5615795c84`
  (`analysis/data/corpus_v2/SPLIT_V3_RMO_REMOVED.json`); the prior 78-company
  (RMO-included) holdout sha256 was
  `d4e40fe0b5f1234b34c3fe7ccd5e704afff4e5aaf4e17dbc0e53c2223e412a23`
  (`analysis/data/corpus_v2/SPLIT_V2.json`). Re-locking was safe and cost
  nothing each time: no company in any of these corpora has ever been scored,
  and the holdout had never been used for any measurement — see
  `wrap-ups/corpus-fix-4-threshold-and-terminal-value-out.md` Step D for the
  full argument. This note must not be scored during iteration. Any run —
  sweep, prompt-candidate comparison, allocator gate — that touches any
  company in this holdout list must say so prominently in its own manifest
  and wrap-up. This note does not itself gate anything; it exists so a
  future run does not silently spend the holdout.
- **Model-pin decision (resolved 2026-05-23):** gate run for sonnet-4-20250514
  vs sonnet-4-6 under `--hurdle model_version` (equivalence hurdle). Verdict:
  **HOLD** — challenger regressed by 7.4pp (noise floor 4.2pp); 29% of tickers
  improved (below 50% robustness threshold). Champion `claude-sonnet-4-20250514`
  retained. See `data/gate_ledger.json` entry 1. Re-run when sonnet-4-7 or later
  snapshot is available.
- **Validation corpus expansion (pre-next-model-gate):** the current 7-ticker set
  (ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR) was the original backtest set, not
  deliberately designed for balance. It skews heavily speculative/small-cap (5 of 7)
  and both large-cap names (ENPH, TTD) had significant price drawdowns during the
  evaluation window. This biases the gate toward measuring speculative-thesis
  evaluation quality only.
  Before the next model gate run, lock an expanded corpus with deliberate balance
  across: large-cap established vs. small-cap speculative; Type A (single-driver)
  vs. Type B (multi-driver platform); and sector coverage within the circle of
  competence (solar, storage, semiconductors, software/cloud).
  **Constraint:** the expanded ticker list must be finalized and locked *before*
  any challenger eval cache is generated. Post-hoc selection after seeing champion
  performance would introduce bias the gate is designed to prevent.
- **Analyst ground-truth alternative:** forward *fundamental* confirmation (vs
  forward return) was considered and deferred — more faithful to the thesis claim but
  needs an independent label and is slower. Revisit if return-based grading proves too
  noisy.
- **Instrumentation UI (deferred — product feature, explicitly not the gate):**
  a screen exposing the allocator's knobs (`K`, the per-session limit `X`, scope,
  funding mode) over a replayable historical window, so a developer or a future
  licensee can see the risk/return consequence of moving them. Fidelity is
  already covered by §2.3's two headless tiers, so this is not load-bearing for
  correctness and must not become the release gate: it would put every release
  behind a code path that ships to no user, must itself be correct, and runs on
  demand at release time — the worst moment to discover a sizing defect.
  **Two conditions if it is built.** First, it comes after Step 8(a): an agent
  that trades faithfully is worth more than a knob panel over a simulation.
  Second — and this is the real hazard — a knob panel is an overfitting machine,
  handing the user exactly the cheap parameter search that §2.1 was written to
  constrain. It must therefore emit a **gate run** and not a leaderboard: any
  setting explored in it reaches production only through §2.1, with the metric
  pre-registered, the recent holdout intact, the complexity penalty applied, and
  the run written to the experiment ledger. A screen that lets someone sweep `X`
  and keep the best-looking number has inverted the whole methodology.
- **Fixture window vs. live universe drift:** the fixture set is pinned to
  2022-01-01 – 2024-06-12 and to the 16-ticker corpus. It will not exercise
  tickers added later. Decide, before the window goes stale, whether to extend
  the corpus (requires re-running the retired analyst model — see §2.3 input
  pinning) or to accept the window as a fixed regression suite.
- **Walk-forward** upgrade once corpus grows (§7).
- **CI automation** (§9.8).
- **F1 — baseline divergence (open).** §3.1 specifies "lift over an
  always-hold baseline" and justifies it explicitly ("an always-'bullish'
  coin scores ~55–60% in a bull sample"). `analysis/analyst_direct_scorer.py`
  (lines 18, 207) implements always-**bullish**, not always-hold, and has
  since the file was written. Measured on the scorer's 359-row thin-filtered
  ALL16 corpus (`analysis/data/value_attribution_v2/stage_b_manifest.json` →
  `results.B1.scorer_population_aggregate_thin_filtered_n359`, forward-return
  hit rates, not a median across draws):
  - always-bullish baseline 46.2%, hit rate 40.4%, lift **−5.8pp** (fails)
  - always-hold baseline 11.7%, hit rate 40.4%, lift **+28.7pp** (passes)
  Same 359 calls, opposite verdict depending on which baseline is used. Both
  intervals are non-trivial: the scorer population's always-bullish-lift 95%
  ticker-block bootstrap CI is [−9.55, −1.98]pp (2000 resamples, seed
  20260913, `stage_b_manifest.json` → `results.B3.bootstrap.scorer_population_ci95.always_bullish_lift_pp`)
  and does not span zero on this population — but the **simulator's** 195-event
  population's always-bullish-lift CI is [−9.72, +0.62]pp
  (`results.B3.bootstrap.simulator_population_ci95.always_bullish_lift_pp`)
  and **does** span zero, consistent with McNemar p=0.1755 on that same
  comparison (`results.B3.mcnemar.simulator_population_vs_always_bullish`).
  **Until F1 is resolved, no lift figure from this scorer may be cited as
  §3.1's metric.** Cite it as "always-bullish-relative" or
  "always-hold-relative," SPY-benchmarked (see F2), naming the baseline, the
  population (scorer's 359/362 vs. simulator's 195 — they are not the same
  denominator, see `stage_b_manifest.json` → `results.B0`), and whether the
  interval spans zero.
- **F2 — benchmark divergence (open, deferred; not resolved by this
  measurement).** §3.1 specifies the stock's sector ETF where one applies
  (worked ENPH-vs-TAN example), else SPY. `analyst_direct_scorer.py` line 55
  uses SPY for every ticker ("sector ETFs not yet in price cache"). Not
  resolved here — TAN/SOXX history is absent from `price_cache.json` and this
  measurement does not fetch prices or re-grade. Size only: of the scorer's
  359-row thin-filtered ALL16 corpus, 10 of 16 tickers (AMD, AVGO, NVDA —
  semiconductors; FSLR, RUN, SPWR — solar; AMPX, ENVX, EOSE, QS — storage)
  sit in a Tier 1 domain (`docs/architecture/DOMAIN.md` §Tier 1) where a
  sector ETF applies and SPY-relative grading is expected to diverge most
  from sector-relative grading; the remaining 6 (AAPL, GOOGL, MSFT, ORCL,
  TSLA, TTD) do not have an obvious sector-ETF alternative under §3.1's
  worked example. This is a lower bound on affected rows, not a resolution.
- **Arm 0 ≤ control (recorded here per Stage A's flag).** Always-bullish run
  end to end through the real allocator returns **$173,102.24**, against the
  real system's **$179,944.91** — it loses by $6,842.67
  (`analysis/data/value_attribution_v2/stage_a_manifest.json` →
  `results.arm_0_always_bullish.final_value` and
  `docs/architecture/VERSION_REGISTRY.json` →
  `benchmarks.settled_control.figures.final_value`, both forward draws, not
  medians). A comparator that reads as superior in §3.1's percentage-point
  terms (F1's always-bullish framing scores 46.2%, well above the real
  system's constituent analyst hit rate) loses money in dollars relative to
  the real system. This is the empirical case that §3.1's current metric, as
  implemented, can grade something the system does not monetize. See
  `wrap-ups/value-attribution-and-headroom-v2-out.md` and
  `wrap-ups/value-attribution-v2-stage-b-out.md`.

---

## 11. Comparison protocol — what may be compared to what

Ported verbatim in substance from `ALLOCATOR_PORTING_METHODOLOGY.md`'s final
section (2026-09-12). Referenced, not duplicated, from
`VERSION_REGISTRY.json`'s `comparison_protocol` record.

**Why this is here:** a version registry makes the *machinery* unambiguous.
It does not make a *comparison* legitimate. A session can read two
correctly-recorded figures, subtract them, and produce a number that looks
authoritative and is meaningless. These rules make the illegal subtraction
illegal rather than merely visible.

### 11.1 Absolute figures are tuple-scoped

Final value, absolute return and absolute drawdown are comparable **only
within an identical tuple**: (corpus tickers, window, prompt version+hash,
model, allocator version, settled configuration).

Across any difference in that tuple they are **not comparable** — not
"comparable with an adjustment," not comparable. There is no
"improved 2pp over corpus" measurement to get right when the tickers or the
window differ.

Live example of why: the existing corpus was scored by
`claude-sonnet-4-20250514`, which is **retired and cannot be regenerated at
any price**. Any new corpus is scored by a different model, so absolute
comparison against $179,944.91 / $184,819 is confounded before anyone even
changes the tickers.

### 11.2 Across tuples, only benchmark-relative metrics travel

And each must be computed over the run's **own** window:

- portfolio return vs SPY / QQQ / TMFC over that same window;
- analyst-direct hit rate vs the always-bullish baseline (lift).

Caveat that must travel with lift: it is mechanically capped at
(1 − baseline). With a baseline near 0.85, a *perfect* analyst scores at
most +15pp, and a declining lift series across a bullish stretch is the
**null expectation, not a signal**.

**So a new corpus is compared against market benchmarks over its own
window — never against a prior run's absolute figures.**

### 11.3 Every drawdown names its ruler, on BOTH sides

Session-sampled and daily-marked drawdowns differ by 1.9–8.3pp on this
project's own data. The published "8.04pp advantage over SPY" was portfolio
session-sampled against SPY daily-marked; like-for-like on the daily ruler
it is **1.90pp**.

A drawdown pair without two rulers named is not a result. Reject it in
review.

### 11.4 EW is not a measured benchmark

`$120,427 / 42.76%` was never reproduced and its ruler is unknown
(`baseline.py` computes SPY/QQQ/TMFC only). **Do not quote it as measured.**
Either reproduce it or remove it from the tables it sits in — it currently
looks legitimate because three real figures surround it.

### 11.5 Validity is computed, not remembered — and it is three states, not a boolean

**CORRECTED 2026-09-12 (`prompts/benchmark-validity-taxonomy.md`).** This
rule previously read: *"A benchmark figure is stale the moment any artifact
hash it was measured under changes."* **That boolean framing is now known
to conflate two different facts and is superseded below — kept here,
visibly, per this project's standing rule that a correction supersedes
explicitly and is never quietly replaced.**

The boolean was applied literally in `model-provenance-corrections`
(2026-09-12): adding a per-record `model` field and extending each
record's `valid_while` made **6 of the project's 7 benchmark records read
STALE** — four of them *permanently*, with no possible remediation. The
only unflagged record, `ew_baseline`, was the one that actually deserved a
warning (never reproduced, ruler unknown). A flag that fires on nearly
everything, while missing the one real problem, stops carrying
information — the exact alert-fatigue failure `allocator_live`'s handling
in the registry's `decisions` already avoided for the app/backtest
divergence, reintroduced here via the model axis.

**Why one boolean cannot represent this:** `settled_control` replays to the
cent from frozen `Analysis` rows under a deterministic simulator — it is
not stale in any reproducibility sense; every run this project has made
this week hit `$179,944.91` exactly. But it describes a system driven by an
analyst model (`claude-sonnet-4-20250514`) that is now retired and can
never be re-invoked — permanently, not pending a fix. Those two facts
demand opposite reader responses: "cannot reproduce" is a data-integrity
alarm; "reproducible, but describes a retired configuration" is a
don't-extrapolate warning, which is exactly this document's own §11.1
tuple rule restated as a registry field rather than left as prose a reader
has to recall.

**The three states, replacing the boolean:**

| state | meaning | how to cite |
|---|---|---|
| **VALID** | every `valid_while` artifact unchanged | freely |
| **SUPERSEDED** | a `valid_while` artifact moved, but the figure can still be regenerated from surviving inputs (deterministic replay of frozen rows, or a recoverable prompt/model combination) | **only within its own tuple** (§11.1) — never extrapolate it to describe the currently-promoted system |
| **UNREPRODUCIBLE** | the inputs, or the method, no longer exist or were never established; the figure can never be re-verified | historical record only |

**The state cannot be inferred from a hash comparison — it must be
declared**, per benchmark record, as a `reproducibility` field
(`VERSION_REGISTRY.json`). A hash mismatch alone only tells you *that*
something moved; whether the figure is still regenerable (SUPERSEDED) or
irretrievably lost (UNREPRODUCIBLE) is a fact about the world a session has
to establish and record, the same way `reproducibility_note` explains *why*.

**Corpus-anchored records carry a permanent, non-actionable SUPERSEDED on
the model axis.** `settled_control`, `test1_zero_info_floor`,
`sizing_channel_null`, and `small_cap_materiality` all derive from the one
frozen corpus scored under `claude-sonnet-4-20250514`. They will read
SUPERSEDED on the model axis under every future promoted model, forever —
that is a permanent property of what they are, not a defect awaiting a
fix, and a reader must not go looking for one. Contrast
`test4_per_tier_noise_floors` and `test6_look_ahead_null`, whose prompt
(`v10+auto1`) survives at commit `87bcfaa` as a registered candidate — those
genuinely can be re-measured by deliberately invoking that candidate, so
their SUPERSEDED is actionable in a way the corpus four's is not.

`whats_live.py` groups by state, prints counts, and orders UNREPRODUCIBLE
first specifically so it is not buried under the (expected, larger) count
of SUPERSEDED records. Exit-code behavior is unchanged by this section: a
validity state is informational, never a non-zero exit; only a
promoted-artifact hash mismatch (§1's registered artifacts) does that.

### 11.6 Noise floors are sample-scoped

A hit-rate noise floor depends on n **and on the specific transcripts**.
Test 4's per-tier floors (0.0 / 0.0 / 3.77 / 14.34pp) transfer only to runs
on the identical 50-transcript sample — which is exactly why Test 6 was
designed as a paired reuse of it rather than a fresh draw. **A new corpus
needs its own floor before any effect on it can be called detectable.**

### 11.7 Cross-model comparison requires paired rows

`gate_ledger.json` entry 1 had **zero paired rows** (champion n=6, all
`Add`; challenger n=36). A model comparison without overlapping scored
transcripts is **confounded, not merely weak**. Pair, or do not compare.

### 11.8 State the minimum detectable effect before calling anything significant

And derive it correctly. Test 6 computed its MDE by dividing a binomial CI
by √5 on the grounds that each arm averaged 5 runs — **not defensible**:
the 5 runs re-score the *same* transcripts, so averaging reduces scoring
noise, not sampling uncertainty about which transcripts were drawn.
Separately, an unpaired binomial is too conservative for a paired design;
the natural test is on **discordant pairs** (McNemar). Fix before reuse.

---

## Changelog

- **2026-09-12** — §8 **corrected**: the "pin to a dated snapshot, never a bare alias"
  rule was written under Anthropic's pre-4.6 naming convention and mis-fires on
  post-4.6 IDs, where the dateless ID *is* the pinned snapshot. `claude-sonnet-4-6`
  is correctly pinned; every "bare alias / forced exception" flag against it in this
  repo is withdrawn. Also verified that `claude-sonnet-4-20250514` genuinely retired
  2026-06-15 (previously an unverified commit-message claim). **§8.1 added**: forced-
  migration protocol, for the case the rest of this document does not cover — when a
  retirement compels a change the gate would have declined, as happened in June 2026.
  Sources: platform.claude.com model-ids-and-versions, model-deprecations.

| Date | Change | Rationale |
|---|---|---|
| 2026-09-17 | §3.1a added: three OPEN ruler-design questions — dead-band width (R1), magnitude weighting (R2), grading-window placement for post-call inputs (R3). Nothing adopted; the gate metric is unchanged. | Reading the train and tune baselines showed the luck-corrected gap is flat (+2.1 to +2.8) across dead bands from ±5% to ±25% while apparent accuracy moves 29%→52%, so the band is a presentation choice masquerading as a measurement one and needed pinning down before it could be moved for the wrong reason. R2 records that §3.1 and §3.2 disagree about what matters — equal-weighted calls vs dollars — with only a three-event gradient bridging them. R3 pre-empts a measurement error the post-call-reaction candidate would otherwise ship: a rule with no analyst in it scores +6.23pp graded from the call date and +2.00pp graded honestly. |
| 2026-09-17b | R1 demoted from blocker to open-but-not-blocking, same day it was raised; pooled v6 figure (+2.53pp, 95% +0.79 to +4.19, excludes zero) recorded in §3.1a. | R1 was recorded as gating the first prompt candidate. It does not: v6's bearish-call edge over the base rate is 13–18 points at every band from ±5% to ±20%, and bootstrap interval width does not shrink as the band widens (3.40 → 4.07 points). The band decides how flattering the scoreboard looks, not what to build or how well anything can be detected. Left open for honesty about the metric; removed from the critical path. |
| 2026-05-23 | Initial methodology drafted and locked | Generalizes manual change-testing into a disciplined champion/challenger gate. Triggered by the accidental model bump (4→4.6) exposing un-version-controlled analyst drift. Decisions: manual/on-demand trigger; benchmark-relative 2Q ±5% lift-over-hold analyst metric; return-per-drawdown portfolio metric; recent-holdout + scaled-rigor OOS; metric-to-change mapping per §4. |
| 2026-05-23b | Two-hurdle extension: split analyst changes into improvement vs equivalence hurdle | If every model version update must clearly beat the incumbent to be adopted, and none ever does, the system would eventually be stranded on a deprecated model with no validated fallback. Model-version changes now use an equivalence hurdle: adopt unless the challenger clearly regresses (Δ < −1 SD). Prompt / eval-logic changes retain the improvement hurdle (Δ > +1 SD to adopt). Three-verdict system (PROMOTE / EQUIVALENT / HOLD) added to §5; holdout skipped for EQUIVALENT results. Implemented in gate_runner.py via --change-class flag. |
| 2026-09-02 | Third change class: implementation-layer changes (§2.3), fidelity hurdle, binary CONFORM / DIVERGE verdict (§5d); fixture version discipline (§8); conformance fixtures added to the build sequence (§9.6) as a prerequisite for `CLAUDE.md` Step 8(a); in-app replay recorded as a deferred product feature (§10). Mechanics in `CONFORMANCE_FIXTURES.md`. | The gate as locked answers “should we adopt this design?” and never asks “did we build the design we adopted?” §2.1 runs the simulator against the frozen evaluation cache and never executes production code, so a production defect passes silently — as task #77’s 11x sizing divergence would have. Comparison is on the decision stream rather than dollars: Python↔JS bit-exactness is unachievable, and a trade-list diff localizes a defect where a dollar gap does not. Fixtures rather than in-app replay because they run in CI on every commit at a fraction of the build. |
| 2026-09-02b | §2.3 restructured into two headless tiers — golden fixtures (decision function, CI) and a headless replay driver (input assembly, per release); build sequence gains §9.7; instrumentation UI reframed in §10 with an overfitting condition | Fixtures alone are blind to input assembly: they hand the allocator a given state, so §9 invariant #5 and §11 defect #2 — both state-assembly failures — could not fail a tier-1 gate. Tier 2 closes that without a user interface. Separately, an instrumentation UI is a legitimate product feature but a cheap parameter search by another name; it is bound to §2.1's pre-registration and holdout discipline rather than allowed to select settings on its own. |
| 2026-09-12 | Section 11 added: comparison protocol (8 rules) ported verbatim in substance from `ALLOCATOR_PORTING_METHODOLOGY.md`'s final section, referenced from `VERSION_REGISTRY.json`'s new `comparison_protocol` record. | Part of the version-registry-and-drift-guards build: a registry makes artifact identity unambiguous but not comparison legitimacy — these 8 rules make an illegal subtraction (mismatched tuple, unpaired model comparison, unruled drawdown, a bad MDE recipe) illegal rather than merely visible. |
| 2026-09-12b | §11.5 refined from a stale/not-stale boolean into three states (VALID / SUPERSEDED / UNREPRODUCIBLE), declared per benchmark record via a new `reproducibility` field rather than inferred from a hash comparison; old boolean wording kept visible as superseded. | Applying the boolean literally (`model-provenance-corrections`, same day) made 6 of 7 benchmark records read STALE — 4 of them permanently, with no possible remediation — while `ew_baseline`, the one record that actually needed a warning, stayed unflagged. A flag that fires on nearly everything and misses the real problem stops carrying information. The three states separate "cannot reproduce" (data-integrity alarm) from "reproducible, but describes a retired configuration" (a don't-extrapolate warning, i.e. §11.1's tuple rule mechanized). |
