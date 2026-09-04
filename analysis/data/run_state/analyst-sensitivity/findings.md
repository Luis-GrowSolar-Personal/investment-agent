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
