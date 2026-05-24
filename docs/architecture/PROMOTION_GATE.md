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
6. **(Deferred) CI-style automation** — run on infra change, block on regression. Only
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
- **Walk-forward** upgrade once corpus grows (§7).
- **CI automation** (§9.6).

---

## Changelog
| Date | Change | Rationale |
|---|---|---|
| 2026-05-23 | Initial methodology drafted and locked | Generalizes manual change-testing into a disciplined champion/challenger gate. Triggered by the accidental model bump (4→4.6) exposing un-version-controlled analyst drift. Decisions: manual/on-demand trigger; benchmark-relative 2Q ±5% lift-over-hold analyst metric; return-per-drawdown portfolio metric; recent-holdout + scaled-rigor OOS; metric-to-change mapping per §4. |
| 2026-05-23b | Two-hurdle extension: split analyst changes into improvement vs equivalence hurdle | If every model version update must clearly beat the incumbent to be adopted, and none ever does, the system would eventually be stranded on a deprecated model with no validated fallback. Model-version changes now use an equivalence hurdle: adopt unless the challenger clearly regresses (Δ < −1 SD). Prompt / eval-logic changes retain the improvement hurdle (Δ > +1 SD to adopt). Three-verdict system (PROMOTE / EQUIVALENT / HOLD) added to §5; holdout skipped for EQUIVALENT results. Implemented in gate_runner.py via --change-class flag. |
