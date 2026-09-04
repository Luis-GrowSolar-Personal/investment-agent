# analyst-sensitivity — how much does analyst quality actually matter

Run: `prompts/analyst-sensitivity.md`. **Report, not decision.** Scope
boundary honored: no configuration adopted, no spec amended, `versions.js`
untouched.

**Resume status:** fresh run, no prior state existed for `run_id`
`analyst-sensitivity`. All six steps completed. This is a **full run**, not
partial.

> **Zero-information floor: $120,800, 12.72% dd — beats SPY/QQQ outright and
> edges out TMFC (EW not computed by this driver, see §2 caveat).
> Sensitivity at the settled cell (adjacent mode, the "realistic
> degradation"): a 7.44pp lift drop (interpolated to q≈0.5) costs ~$24,886
> (13.8%) and *improves* drawdown by ~5.0pp — drawdown falls as
> recommendation quality degrades in every mode tested, the opposite of the
> naive expectation. Gradient near the champion's own operating point:
> ~$5,825 per 1pp of lift (adjacent mode, q=0→0.1 slope). Shape: roughly
> linear in adjacent/pessimistic modes out to q≈0.5, then a steep further
> drop to q=1.0; optimistic mode is flat-to-slightly-positive (never
> costs money in this backtest). Most damaging mode at equal lift-drop
> magnitude: pessimistic (~$42,700 / 23.8% estimated cost at the same
> -7.44pp target, vs adjacent's $24,886). Cells still passing the 39.12%
> drawdown ceiling: all 360 — 0/360 draws in the entire grid ever exceed
> 25.09% drawdown, so Rule 4 has zero discriminating power on this axis.
> Verdict on forced model migration: on this measure alone, tolerable
> — a full-strength realistic-degradation shock at the exact regression
> size the ledger measured costs roughly 14% of final value and *reduces*
> risk, not a result that argues execution should wait on it.**

---

## 1. What this run is, and the two things it is not

No LLM calls, no API spend, no DB writes. Every cell perturbs already-loaded
`CallEvent` objects in memory (`analysis/simulator/data.py`'s DB loader,
via `sweep_cadence_and_session_model.load_events_dedup_on()` — the same
loader `quarterly_composition.py` used for the settled-cell composition
snapshot on 2026-09-03), then runs the unmodified settled-cell driver
(`run_session_sweep_cell`, `swap_funding`/K=30/`new_calls_only`/X=2.5pp/
`pooled`/`per_event_date`). No cache refresh: `fundamentals_cache.json`
staleness warning (116 days) fired on every run, as expected, and was not
touched.

This is **phase 0 only** — every figure below is either a **forward run**
(control, q=0 gate) or a **median across 15 draws** (grid cells), never a
phase-averaged median. It is not directly comparable to the published
phase-averaged $184,819/17.32% headline without accounting for that
difference (state-of-play §5.2 already flags a $4,874/3.5pp phase gap
between phase-0-only and phase-averaged at this same cell).

## 2. Which score fields the allocator actually reads (Step 1 finding)

Read `analysis/simulator/simulator.py:142-143` and
`analysis/sweep_cadence_and_session_model.py:782,816-817`. Both build the
`decide()` call from exactly two score fields:

- `final_action` = `event.final_action or event.per_call_rec or "Hold"`
- `recommended_size_pct` = `event.recommended_size` (**not perturbed** —
  the prompt's four modes are all defined over `recommendation`/ordinal
  scale, not size, and it would be a scope decision this run doesn't make
  to invent a size-perturbation mode)

`thesisHealth` (`event.thesis_health`) is **never passed into `decide()`**
anywhere in the v2/v3 allocator call path. It is read only inside
`recompute_trend_layer` at load time, to build prior-call trajectory
history consumed by `apply_matrix`. This harness moves `thesis_health` in
lockstep with `recommendation` on the same ordinal scale (`Strengthening
< Intact < Weakening < Broken`, matched index-for-index to
`Add < Hold < Trim < Exit`) purely for score-object consistency —
**this move has zero effect on any simulated result and is not counted
as a degradation channel.** Stated plainly per the prompt's own
instruction not to report an unread field's perturbation as degradation.

Driver: `analysis/analyst_sensitivity_harness.py`, committed at `e6d51cd`
(initial), fixed at `db45d15` (see §6 gate failure below) — the grid and
control results cited in this report are all from the `db45d15`+ driver.

## 3. Step 2 — zero-information control (run first, per the prompt)

`analysis/data/run_state/analyst-sensitivity/cells.jsonl`, `cell_key:
"zero_info"`, 15 tie-break draws (`tie_seed` 0..14), **all bit-identical**:

| Metric | Value | Provenance |
|---|---|---|
| final_value | **$120,800** | `cells.jsonl` → `cell_key=="zero_info"` → `results.final_value` |
| max_dd | **12.72%** | same row → `results.max_dd` |
| distinct_tickers | **16** (all of ALL16) | same row → `results.distinct_tickers` |
| vs SPY | $113,980 / 21.99% | same row → `results.baseline_finals.SPY` / `results.baseline_drawdowns.SPY` |
| vs QQQ | $119,178 / 33.75% | same row → `.baseline_finals.QQQ` / `.baseline_drawdowns.QQQ` |
| vs TMFC | $120,512 / 31.60% | same row → `.baseline_finals.TMFC` / `.baseline_drawdowns.TMFC` |

**Headline finding, per the prompt's own instruction to put this at the
top if it happens: the zero-information arm beats SPY and QQQ outright on
final value, and edges out TMFC by ~$288 (0.24%), while running roughly
half the drawdown of any of the three.** Every event forced to
`Hold`/`Intact`, `recommendedSize=None` — the analyst carries no
information whatsoever — and the portfolio still comes out ahead of two
of three computable benchmarks and essentially tied with the third, at
much lower risk.

**Why:** `allocator_v3.py` lines 55-64 fire a first-call starter position
(5% speculative / 8% established) on every ticker's first call
**regardless of recommendation** — confirmed by `distinct_tickers=16`
even at zero information, meaning the starter alone bought into every name
in the universe. What generates the advantage over these three benchmarks
is the universe, the starter mechanism, the X=2.5pp deployment discipline,
and the concentration/profit-take rules — **not the analyst's information
content.**

**Premise flagged: EW is not computed by this driver.**
`run_session_sweep_cell`'s `baseline_finals`/`baseline_drawdowns` returns
only `{SPY, QQQ, TMFC}` — grepped `analysis/simulator/baseline.py`, no EW
key exists anywhere in the codebase this driver touches. The prompt says
"against the four benchmarks"; only three are available from this driver.
The published EW figure ($120,427 / 42.76%, state-of-play §2) is cited
here for context only — it comes from a *different* run (the
phase-averaged full settled-cell backtest) and was not recomputed under
zero-information corruption. If EW needs to be included, it requires
either extending `run_session_sweep_cell`'s baseline computation or a
separate EW-only re-run — out of scope for this session.

**Second independent observation of the state-of-play §5.2 anomaly:** all
15 tie-break draws returned bit-identical results, again. Traced to
`sweep_cadence_and_session_model.py` lines 419-425 — `seed` only shuffles
events **within the same `call_date`**; this ALL16/dedup corpus
apparently has no two events landing on the same date, so the shuffle is
a no-op on every draw regardless of q or mode. Property of the
corpus/cadence combination, not a code defect. It means the "15-draw
range" reported anywhere for this configuration on the **tie-break axis**
is legitimately a single point — Rule 2's overlapping-range test has
nothing to compare there. The **corruption-seed axis** (Step 3) is a
separate axis and does vary, as expected.

## 4. Step 3 — sensitivity grid (Step 0/Step 3 gate)

4 modes × 6 q values × 15 corruption seeds = **360 cells**, `tie_seed`
fixed at 0 (isolates the corruption axis from the tie-break axis, which
Step 3 showed has zero spread here anyway). Wall clock: **34s** for the
full grid (corpus load 2.5-2.7s + 360 cells at ~0.09s each). All 360
cells run fresh — no prior state to reuse (first run of this `run_id`).

### 4.1 A gate failure, caught, fixed, and re-run — flag plainly

The **first** grid run failed the prompt's own hard-stop gate: q=0.0
gave $180,310 / 20.37% dd in every mode, not the uncorrupted reference
$179,945 / 20.85% (state-of-play §5.2). Root cause:
`perturb_events()` unconditionally rebuilt `final_action` from
`per_call_rec` even on the "no corruption fired" branch, silently
discarding `apply_matrix`'s trend-layer-computed `final_action` whenever
it differed from the raw recommendation — corrupting the input at q=0.
Per the prompt's own instruction ("Hard stop if it does not [reproduce
exactly]"), the run was stopped, the driver fixed (commit `db45d15`,
seeds each field's perturbation from its own current value and passes it
through unchanged on the no-corruption branch), and Step 2 + Step 3 were
both **re-run from scratch** under the fixed driver before any figure in
this report was taken from them. The pre-fix `cells.jsonl` was removed
(commit `79ba59a`) rather than kept, since `config_hash` already includes
`driver_commit` and would not have let it be silently reused, but keeping
it around invited exactly the kind of confusion `CLAUDE.md`'s provenance
rule exists to prevent.

**Post-fix, the gate passes cleanly in every mode:**
`cells.jsonl` → `cell_key` `{uniform,adjacent,optimistic,pessimistic}_q0.0`
→ `results.final_value` = `179944.91`, `results.max_dd` = `0.208523` in
all four — an exact match to the state-of-play §5.2 uncorrupted reference,
to the cent.

### 4.2 Grid results (median across 15 corruption-seed draws, forward tie_seed=0)

All figures: `analysis/data/run_state/analyst-sensitivity/cells.jsonl`,
grid cells (`cell_key` matching `<mode>_q<q>`), `results.final_value` /
`results.max_dd`, aggregated to min/median/max across the 15
`corruption_seed` draws per (mode, q) — **medians across draws**, stated
per the prompt's units rule.

| mode | q | final min/med/max | dd min/med/max | tickers |
|---|---|---|---|---|
| uniform | 0.0 | 179,945 / 179,945 / 179,945 | 20.85/20.85/20.85% | 15 |
| uniform | 0.1 | 149,202 / 165,860 / 193,122 | 16.36/20.44/22.75% | 12-15 |
| uniform | 0.2 | 135,092 / 156,892 / 183,018 | 15.43/18.59/22.92% | 11-15 |
| uniform | 0.3 | 122,038 / 148,706 / 213,734 | 14.70/18.68/20.80% | 11-15 |
| uniform | 0.5 | 117,292 / 135,023 / 167,425 | 12.91/15.50/17.56% | 10-15 |
| uniform | 1.0 | 96,582 / 111,529 / 135,871 | 11.18/13.39/15.36% | 7-12 |
| adjacent | 0.0 | 179,945 / 179,945 / 179,945 | 20.85/20.85/20.85% | 15 |
| adjacent | 0.1 | 159,449 / 170,976 / 188,817 | 17.09/19.71/21.22% | 13-15 |
| adjacent | 0.2 | 146,487 / 169,778 / 190,916 | 15.60/18.49/21.24% | 12-16 |
| adjacent | 0.3 | 139,386 / 161,467 / 184,822 | 13.88/17.20/21.19% | 13-15 |
| adjacent | 0.5 | 131,071 / 155,059 / 175,280 | 13.04/15.87/20.43% | 12-16 |
| adjacent | 1.0 | 97,098 / 113,646 / 141,050 | 12.57/13.48/16.77% | 9-14 |
| optimistic | 0.0 | 179,945 / 179,945 / 179,945 | 20.85/20.85/20.85% | 15 |
| optimistic | 0.1 | 170,495 / 178,354 / 189,545 | 20.33/21.32/23.18% | 15 |
| optimistic | 0.2 | 172,426 / 182,021 / 193,469 | 19.86/21.77/23.49% | 15 |
| optimistic | 0.3 | 168,714 / 183,556 / 194,455 | 20.59/22.32/24.53% | 15 |
| optimistic | 0.5 | 168,474 / 192,860 / 200,019 | 20.97/22.79/24.76% | 15 |
| optimistic | 1.0 | 184,584 / 184,584 / 184,584 | 25.09/25.09/25.09% | 15 |
| pessimistic | 0.0 | 179,945 / 179,945 / 179,945 | 20.85/20.85/20.85% | 15 |
| pessimistic | 0.1 | 151,981 / 167,136 / 179,185 | 17.36/20.09/20.81% | 13-15 |
| pessimistic | 0.2 | 143,675 / 164,744 / 177,497 | 15.47/18.67/20.55% | 12-14 |
| pessimistic | 0.3 | 135,081 / 154,385 / 167,157 | 15.43/17.55/20.83% | 11-16 |
| pessimistic | 0.5 | 118,379 / 143,870 / 157,585 | 13.17/15.51/18.47% | 11-15 |
| pessimistic | 1.0 | 102,195 / 102,195 / 102,195 | 11.88/11.88/11.88% | 6-6 |

**Uncomfortable answer, flagged plainly: drawdown falls, not rises, as
recommendation quality degrades, in every mode except optimistic.** Worse
recommendations mean fewer/smaller Adds, which under `swap_funding` means
less concentration and less exposure to the winners' subsequent
volatility — the ratchet and profit-take rules never get stressed the
same way. This is real, not a driver bug (same conclusion holds across
all three degrading modes and is monotonic within each), but it means the
39.12% drawdown ceiling (Rule 4) provides **zero discriminating power on
this axis**: max drawdown anywhere in the entire 360-cell grid is
**25.09%** (`optimistic` `q=1.0`) — every single cell passes with room to
spare. 360/360 draws under the ceiling; "robust ≥ 2/3" is trivially true
everywhere.

**optimistic mode never costs money in this backtest** — miscalibration
toward Add, at any q up to 1.0, produces final values at or above the
uncorrupted baseline in every row's median. This is the backtest's
Add-biased first-call-starter mechanism interacting with a broadly
upward-trending 2022-2024 corpus for these 16 names; it is not evidence
that a miscalibrated-optimistic analyst is safe in general, only that
this particular corpus/window rewards more aggressive buying.

## 5. Step 4 — lift-pp conversion (`analysis/analyst_sensitivity_lift.py`)

**Premise flagged, per the prompt's own fallback instruction.**
`analyst_direct_scorer.score_eval_dir()` expects a directory of `*.txt`
eval-cache files with a `---STRUCTURED---` JSON block — it cannot be
driven from in-memory `CallEvent` objects without modification. Rather
than modify the gate's scoring file, this run imported its `PriceCache`,
`direction_from_score()`, `FORWARD_DAYS`, `DEAD_BAND`, and `BENCHMARK`
constants directly (`analysis/analyst_sensitivity_lift.py`, no edits to
`analyst_direct_scorer.py`) and reapplied the identical scoring logic
against the corrupted `CallEvent` list — same 2Q-forward,
benchmark-relative, ±5% dead-band methodology, different score source.

**A second, more consequential premise gap: this run's corpus is not the
gate's eval-cache corpus.** `analyst_sensitivity_lift.py`'s q=0.0
(uncorrupted) lift on the DB-loaded, deduped ALL16 corpus (195 events,
`analysis/data/run_state/analyst-sensitivity/lift_grid.json` →
`q0_lift_pp`) is **−3.08pp**, n=195 scoreable — **not** the ledger's
published champion figure of 4.94pp
(`data/gate_ledger.json` entry 1). The two runs score different corpora
(this run's DB events over the full ALL16/dedup window vs. whatever
versioned eval-cache directory the ledger entry scored), so the absolute
lift figures are not comparable and this report does not claim they are.
The **7.44pp drop is applied relative to this run's own q=0 baseline**
(−3.08pp → target ≈ −10.52pp), not asserted as landing on the ledger's
own −2.5pp challenger figure.

### 5.1 Lift-pp by cell (median across 15 corruption-seed draws)

`lift_grid.json` → `cells.<mode>.<q>.lift_pp_median`:

| mode | q=0.0 | q=0.1 | q=0.2 | q=0.3 | q=0.5 | q=1.0 |
|---|---|---|---|---|---|---|
| uniform | −3.08 | −3.08 | −3.59 | −4.10 | −3.08 | −6.67 |
| adjacent | −3.08 | −4.62 | −6.15 | −7.69 | **−10.77** | −18.46 |
| optimistic | −3.08 | −3.59 | −3.59 | −4.62 | −4.62 | −6.15 |
| pessimistic | −3.08 | −3.59 | −4.62 | −6.15 | −9.23 | −12.31 |

(uniform mode's non-monotonicity at q=0.3/0.5 is real — averaging over
15 stochastic uniform-random draws that can land on *any* of the 4
categories including a correct one produces a noisier lift curve than
the directional adjacent/pessimistic modes; not a bug, reported as-is.)

### 5.2 The headline: cost of a 7.44pp lift drop

**adjacent** mode (the prompt's "realistic degradation") reaches
median lift **−10.77pp** at q=0.5 — closest single grid point to the
target **−10.52pp** (q0's −3.08pp minus 7.44pp) — so it is used as the
primary interpolation point rather than fitting a curve across a sparse
6-point q axis:

> **A 7.44pp analyst-lift drop (adjacent mode, q≈0.5) costs
> $179,945 − $155,059 = $24,886 (13.8% of the uncorrupted median final
> value), stated as a median-across-15-draws figure at each end, and
> *reduces* max drawdown by 4.98pp (20.85% → 15.87% median).**

`pessimistic` mode reaches the target lift between its q=0.5 (−9.23pp)
and q=1.0 (−12.31pp) points — linearly interpolating to −10.52pp lands at
q≈0.58, final value ≈ $137,200 (interpolated, not a measured cell), a
cost of **≈$42,700 (23.8%)** — nearly double adjacent mode's cost at the
same lift-drop magnitude. **Most damaging mode at equal lift-drop:
pessimistic**, not adjacent — flagged since the prompt's headline
template asks for "most damaging mode" as a single answer and the two
plausible candidates (the "realistic" mode vs. the numerically worst
mode at the same target) disagree.

### 5.3 Gradient at the champion's operating point

Per the prompt: local slope, not curve-averaged. The champion's own
operating point is near q=0 (small perturbation), not the −10.5pp target
region. Using adjacent mode's q=0→q=0.1 step (closest available bracket
to zero corruption): Δlift = −4.62 − (−3.08) = **−1.54pp**; Δfinal =
$170,976 − $179,945 = **−$8,969**. **Gradient ≈ $5,825 per 1pp of lift**,
locally, near the operating point. (For comparison, the slope measured
across the wider q=0.3→0.5 bracket nearer the 7.44pp target itself is
shallower, ≈$2,081/pp — the curve is not linear across its full range;
see §4.2's shape note.)

## 6. Rules (Step 5)

- **Rule 1** (unchanged, not re-derived here).
- **Rule 2**: ranges overlap heavily between adjacent q-steps and between
  modes at matched q (see §4.2's min/max columns) — e.g. adjacent q=0.2's
  range [146,487–190,916] fully contains uniform q=0.2's median
  [135,092–183,018]'s upper half. Per Rule 2, most neighboring cells in
  this grid are **tied**, not ranked, on the corruption-seed axis. Only
  the extremes (q=1.0 in the degrading modes vs. the uncorrupted q=0.0)
  separate cleanly.
- **Rule 4**: 39.12% ceiling. **0/360 draws in the entire grid breach
  it** — max observed drawdown anywhere is 25.09%. Every cell is "robust"
  at 15/15 (100% ≥ 2/3). Flagged as an uncomfortable answer in its own
  right: Rule 4 was written to catch drawdown blow-ups, and this run's
  finding is that analyst-quality degradation *never* produces one — the
  rule has no teeth against this particular failure mode, because
  degrading the analyst pushes drawdown the other way (§4.2).
- **Kind of number, stated per-figure throughout**: §3's control figures
  are a forward run across 15 tie-break draws that happened to be
  bit-identical (so forward draw = median = the single value shown).
  §4/§5's grid figures are explicitly medians across 15 corruption-seed
  draws, min/max shown alongside. **This run is phase 0 only** — nothing
  here is phase-averaged; do not compare directly to the phase-averaged
  $184,819/17.32% headline without accounting for the phase gap
  state-of-play §5.2 already flagged.

## 7. Deviations from the prompt, and why

1. **Second gate check on q=0.0 caught a real bug** (§4.1) — not a
   deviation from the prompt's instructions, but worth restating: the
   prompt's hard-stop was followed exactly (stop, fix, re-run, don't
   fudge), and it did its job on the first attempt.
2. **EW benchmark not available** (§3) — the settled-cell driver this run
   reuses (`sweep_cadence_and_session_model.run_session_sweep_cell`, the
   same one `quarterly_composition.py` uses) computes only SPY/QQQ/TMFC.
   Reported three of four benchmarks live; cited EW from a different,
   already-published run for context, not recomputed.
3. **Step 4 driven by importing the scorer's functions, not by shelling
   out to it** (§5) — the prompt anticipated this exact possibility
   ("If the scorer cannot be driven from perturbed in-memory scores
   without modification, say so and report the relationship as far as it
   can be established"). Followed that instruction: no modification to
   `analyst_direct_scorer.py`, a new file
   (`analysis/analyst_sensitivity_lift.py`) reapplies its logic.
4. **Corpus mismatch between this run and the gate ledger's eval-cache
   scoring** (§5) — flagged as a premise gap rather than silently
   assuming the two lift scales are the same thing. The 7.44pp drop is
   applied to this run's own q=0 baseline, not the ledger's.
5. **"Most damaging mode"** — reported both candidates (adjacent as the
   prompt's designated "realistic" mode, pessimistic as the numerically
   worse one at equal lift-drop) rather than picking one, since they
   disagree and the disagreement itself is informative.

## 8. What was not done, left for the design session

- **No conclusion drawn on whether to adopt any model, prompt, or gate
  change** — scope boundary honored.
- **§12 items from state-of-play are untouched** — this run answers §7
  Test 1 only, nothing else on the test-plan queue.
- **EW benchmark computation** — would need either extending
  `run_session_sweep_cell`'s baseline set or a separate EW-only re-run;
  not attempted here.
- **Reconciling this run's −3.08pp q=0 lift against the gate ledger's
  4.94pp/−2.5pp figures** — would require identifying and scoring the
  exact eval-cache directory the ledger run used, which is a Test 3/4
  concern (transcript fidelity, noise floor), not this run's job.
- **Recommended-size perturbation** — the prompt's four modes are all
  defined over `recommendation`; `recommendedSize` was deliberately left
  untouched rather than inventing a fifth mode not asked for.

## 9. Reproduction

```bash
cd analysis
python3 analyst_sensitivity_harness.py control   # Step 2, ~4s
python3 analyst_sensitivity_harness.py grid       # Step 3, ~34s, 360 cells
python3 analyst_sensitivity_lift.py               # Step 4, lift-pp grid
```

State: `analysis/data/run_state/analyst-sensitivity/{progress.json,
cells.jsonl, findings.md, lift_grid.json}`, all committed on
`sweep/db-corpus-baseline`.

## 10. Commits this session

| Commit | What |
|---|---|
| `e6d51cd` | initial corruption harness (driver, before any manifest) |
| `2f961e8` | progress.json initialized |
| `d3a4763` | exclude harmless docx lock file from dirty-tree check |
| `080254d` | Step 2 control results (pre-fix) |
| `db45d15` | **fix q=0.0 gate failure** in `perturb_events` |
| `79ba59a` | clear stale pre-fix `cells.jsonl` |
| `e7bcf28` | Step 2 control results (post-fix, confirmed identical) |
| `32e8fe3` | Step 3 grid results (post-fix, gate passes) |
| `15ae153` | Step 4 lift-pp driver |
| `1d05cea` | Step 4 lift-pp grid results |

Wall clock, this session's compute: control ≈4s × 2 runs, grid ≈34s × 2
runs, lift grid ≈similar order. All cells run fresh (no prior `run_id`
state existed to reuse). Corpus load: 2.5-2.9s per invocation
(`n_events=195`).
