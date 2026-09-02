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

- **Pin Claude to a dated snapshot** (e.g. `claude-sonnet-4-YYYYMMDD`), never a bare /
  `-latest` alias. You cannot run a clean before/after on a model change if the model
  drifts underneath you. (See the accidental `claude-sonnet-4-20250514` →
  `claude-sonnet-4-6` bump caught 2026-05-23 — exactly the event this gate exists to
  control. Open decision: revert to pinned old model vs adopt 4-6 via a gate run.)
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

---

## Changelog
| Date | Change | Rationale |
|---|---|---|
| 2026-05-23 | Initial methodology drafted and locked | Generalizes manual change-testing into a disciplined champion/challenger gate. Triggered by the accidental model bump (4→4.6) exposing un-version-controlled analyst drift. Decisions: manual/on-demand trigger; benchmark-relative 2Q ±5% lift-over-hold analyst metric; return-per-drawdown portfolio metric; recent-holdout + scaled-rigor OOS; metric-to-change mapping per §4. |
| 2026-05-23b | Two-hurdle extension: split analyst changes into improvement vs equivalence hurdle | If every model version update must clearly beat the incumbent to be adopted, and none ever does, the system would eventually be stranded on a deprecated model with no validated fallback. Model-version changes now use an equivalence hurdle: adopt unless the challenger clearly regresses (Δ < −1 SD). Prompt / eval-logic changes retain the improvement hurdle (Δ > +1 SD to adopt). Three-verdict system (PROMOTE / EQUIVALENT / HOLD) added to §5; holdout skipped for EQUIVALENT results. Implemented in gate_runner.py via --change-class flag. |
| 2026-09-02 | Third change class: implementation-layer changes (§2.3), fidelity hurdle, binary CONFORM / DIVERGE verdict (§5d); fixture version discipline (§8); conformance fixtures added to the build sequence (§9.6) as a prerequisite for `CLAUDE.md` Step 8(a); in-app replay recorded as a deferred product feature (§10). Mechanics in `CONFORMANCE_FIXTURES.md`. | The gate as locked answers “should we adopt this design?” and never asks “did we build the design we adopted?” §2.1 runs the simulator against the frozen evaluation cache and never executes production code, so a production defect passes silently — as task #77’s 11x sizing divergence would have. Comparison is on the decision stream rather than dollars: Python↔JS bit-exactness is unachievable, and a trade-list diff localizes a defect where a dollar gap does not. Fixtures rather than in-app replay because they run in CI on every commit at a fraction of the build. |
| 2026-09-02b | §2.3 restructured into two headless tiers — golden fixtures (decision function, CI) and a headless replay driver (input assembly, per release); build sequence gains §9.7; instrumentation UI reframed in §10 with an overfitting condition | Fixtures alone are blind to input assembly: they hand the allocator a given state, so §9 invariant #5 and §11 defect #2 — both state-assembly failures — could not fail a tier-1 gate. Tier 2 closes that without a user interface. Separately, an instrumentation UI is a legitimate product feature but a cheap parameter search by another name; it is bound to §2.1's pre-registration and holdout discipline rather than allowed to select settings on its own. |
