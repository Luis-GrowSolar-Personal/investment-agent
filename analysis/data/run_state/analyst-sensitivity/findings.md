# analyst-sensitivity — findings (append-only)

## Finding 1 — thesisHealth is not consumed by the allocator
`simulator/simulator.py:142-143` and `sweep_cadence_and_session_model.py:782,816-817`
build the decide() call from only `final_action` (= event.final_action or
event.per_call_rec or "Hold") and `recommended_size_pct` (= event.recommended_size).
`thesis_health` is read only inside `recompute_trend_layer` (trajectory history
fed to apply_matrix) at load time -- never passed into decide(). This harness
perturbs thesis_health in lockstep with per_call_rec/final_action for
score-object consistency, but that move has ZERO effect on the simulation
and must not be counted as a degradation channel.

## Finding 2 — Step 2 zero-information control: floor matches/beats all three computable benchmarks
cells.jsonl -> cell_key="zero_info" -> results:
- final_value: $120,800 (results.final_value)
- max_dd: 12.72% (results.max_dd)
- vs SPY: $113,980 / 21.99% (results.baseline_finals.SPY / results.baseline_drawdowns.SPY)
- vs QQQ: $119,178 / 33.75%
- vs TMFC: $120,512 / 31.60%

Zero-information beats SPY and QQQ outright on final value, edges out TMFC by
~$288 (0.24%), while posting roughly half the drawdown of any of the three.
Essentially none of the settled cell's return/drawdown advantage over these
three benchmarks comes from the analyst's information content -- it comes
from the universe, the first-call starter (buys 5%/8% on a ticker's first
call REGARDLESS of recommendation, allocator_v3.py lines 55-64), the
X=2.5pp deployment cadence, and the concentration/profit-take rules.

Caveat: EW benchmark not computed by this driver (run_session_sweep_cell
returns only SPY/QQQ/TMFC in baseline_finals/baseline_drawdowns; grepped
simulator/baseline.py, no EW anywhere). Published EW ($120,427/42.76%,
2026-09-03 state-of-play §2) is a different run and cited for context only.

distinct_tickers held even at zero information: 16 (all of ALL16) -- confirms
the starter fires on every ticker's first call independent of recommendation.

## Finding 3 — zero tie-break spread confirmed a second time
All 15 zero-info tie-break draws (tie_seed 0..14) returned bit-identical
final_value=$120,800 and max_dd=12.72%. Second independent observation of
the state-of-play §5.2 anomaly. Traced to sweep_cadence_and_session_model.py
lines 419-425: seed only shuffles events within the SAME call_date before
building sessions; if no two ALL16 events land on the same date post-dedup,
the shuffle is a no-op regardless of draw/mode/q. Property of the
corpus/cadence combination, not a code defect.

## Finding 4 — q=0.0 gate (filled after Step 3)

## Finding 4 — q=0.0 gate FAILED on first attempt, fixed, re-run
First grid run: q=0.0 gave $180,310/20.37% dd in every mode vs the
uncorrupted reference $179,945/20.85% (state-of-play §5.2). Root cause:
perturb_events() rebuilt final_action from per_call_rec unconditionally,
even on the no-corruption branch, discarding apply_matrix's trend-layer
final_action whenever it differed from the raw recommendation. Fixed at
commit db45d15 (seed each field's perturbation from its own current value;
pass through unchanged when the accept draw misses). Post-fix, q=0.0
reproduces $179,944.91/20.8523% dd exactly in all 4 modes -- gate passes.
Step 2 and Step 3 were both re-run from scratch under the fixed driver
before any figure in the wrap-up was taken from them.

## Finding 5 — drawdown falls, not rises, as analyst quality degrades
Across the entire 360-cell grid, max drawdown anywhere is 25.09%
(optimistic q=1.0) -- well under the 39.12% ceiling. In uniform/adjacent/
pessimistic modes, drawdown decreases monotonically as q increases: worse
recommendations mean fewer/smaller Adds, less concentration, and less
ratchet/profit-take stress. Rule 4's 39.12% ceiling has zero discriminating
power against analyst-quality degradation on this corpus/cell -- it was
built to catch a different failure mode.

## Finding 6 — this run's q=0 analyst-direct lift (-3.08pp) is not the ledger's champion figure (4.94pp)
analysis/data/run_state/analyst-sensitivity/lift_grid.json -> q0_lift_pp =
-3.08 (n=195 scoreable), computed on the DB-loaded ALL16/dedup corpus this
run uses. gate_ledger.json entry 1's champion figure (4.94pp) was scored
against a different, versioned eval-cache directory. The two are not the
same corpus and this run does not assert they are comparable in absolute
terms -- the 7.44pp drop is applied relative to THIS run's own q=0
baseline (target lift ~= -10.52pp), reached at adjacent mode q~=0.5
(median lift -10.77pp).

## Finding 7 — headline: 7.44pp lift drop costs ~$24,886 (13.8%) in adjacent mode, and IMPROVES drawdown by ~5pp
See wrap-ups/analyst-sensitivity-out.md §5.2 for full derivation. Most
damaging mode at the SAME lift-drop magnitude is pessimistic (~$42,700,
23.8%, interpolated), not adjacent -- flagged since the two candidates for
"most damaging mode" disagree.
