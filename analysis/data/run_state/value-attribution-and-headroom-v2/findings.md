# Findings — value-attribution-and-headroom-v2

Append-only. Each entry timestamped at the moment established.

## 2026-09-13 — Stage A complete

1. **Arm 0b (universe only) approx equals test1_zero_info_floor to within 18 cents**:
   $120,799.82 vs $120,800.00. These are two independently-constructed
   corruptions (Arm 0b forces `final_action` directly to Hold after the real
   trend layer runs; test1_zero_info_floor forces every trend *verdict* to
   Hold, a different injection point) landing on the same number to four
   significant figures. This is a finding, not an assumption to smooth over:
   either (a) with every call forced to Hold, the two injection points are
   mechanically equivalent for this corpus because apply_matrix on a
   Hold-verdict input converges to the same final_action regardless of which
   layer the Hold is injected at, or (b) it is coincidence. Not investigated
   further this session (Stage A only, per budget). Flag for the design
   session: both remain conceptually distinct (starter-only buy-and-hold vs.
   corrupted-verdict replay) and both should still be reported per the
   prompt's table.

2. **Arm 0 (always-bullish, $173,102.24) is less than or equal to control ($179,944.91)**.
   Per the prompt's Sec5 branch: "the always-bullish-relative lift figure is
   grading something this system does not monetize... a finding about the
   promotion gate itself, larger than this test's original scope." The real
   analyst+trend+allocator system beats permanent maximum-conviction Add on
   every call by $6,842.67 on this corpus. This should be carried into
   PROMOTION_GATE.md Sec10 as an open item: Test 2's -5.8pp always-bullish-
   relative lift figure describes a comparator that, when actually run
   through the real allocator end to end, loses money relative to the real
   system -- so the -5.8pp lift is not evidence the system underperforms a
   viable alternative strategy in dollars. NOT recorded in PROMOTION_GATE.md
   this session -- that edit is scoped to a future pass.

3. **Total added by all three layers together (actual - Arm 0b) = $59,145.09**
   ($179,944.91 - $120,799.82). Not small relative to the $100,000 starting
   capital -- the three layers roughly doubled the universe-only floor's
   gain (floor gained $20,799.82 over $100k; the full system gained
   $79,944.91). The honest reading is NOT "none of them, the universe did
   it" -- the layers collectively add real value on this corpus. Stage C
   (not run this session) is required to say which layer.

4. **Premise correction**: sweep_funding_modes.py's main() grid does not
   contain the settled X=2.5pp session-limit cell used to produce
   settled_control. The actual production driver for the settled
   configuration is sweep_cadence_and_session_model.py's
   run_session_sweep_cell(), invoked with the CELL dict defined in
   tier_return_attribution.py (cadence=30, scope=new_calls_only,
   funding_mode=swap_funding, limit_pp=2.5, execution_order=pooled,
   trim_budget_scope=per_event_date, veto_p=0.0), phase_offset=0, seed=0.
   value_attribution_v2_driver.py uses this path and asserts reproduction
   of $179,944.91 to the cent before running Arms 0b/0 (confirmed: exact
   match). Flagged rather than silently worked around, per Step 4 of the
   execute-prompt skill.

## Stage B finding — 2026-09-13T16:02:14Z

**B0 population reconciliation.** Scorer population = 362 rows (all16, price-scoreable, no createdAt/call-date restriction); 359 after excluding thin years [2020]. Simulator population = 195 call-events (load_events_dedup_on: call_date<=2024-06-12 AND createdAt in v6 window AND same-day-dedup). 195 of 195 simulator events matched a scorer row by (ticker, call_date); 0 did not (same-day-dedup drops the non-kept sibling transcript from the scorer's row-count-by-key view under a naive join). The simulator/scorer gap is THREE restriction axes (call-date ceiling, createdAt/prompt-vintage window, same-day dedup), not two as Stage A's next_action stated -- correcting that premise here.

## Stage B finding — 2026-09-13T16:02:14Z

**B1 lift, both baselines.** Scorer population (n=359, thin-filtered): hit rate 40.4%, always-bullish lift -5.8pp, always-hold lift 28.7pp. Test-2 reproduction: PASSED. Simulator population (n=195): hit rate 37.9%, always-bullish lift -4.6pp, always-hold lift 24.1pp. Always-hold-lift expectation (+6.7pp, prompt Sec6) WAS CONTRADICTED -- see below.

## Stage B finding — 2026-09-13T16:02:14Z

**B2 ground truth distribution.** Scorer population (n=359): bearish base rate 42.1%, bearish-call accuracy 47.7% (n_predicted_bearish=44). This directly bears on the 09-13 handoff's 'wrong roughly four times in five' claim (B4b).

## Stage B finding — 2026-09-13T16:02:15Z

**B3 intervals.** McNemar (scorer pop, always-bullish): b=24 c=45 p=0.0154. McNemar (scorer pop, always-hold): b=142 c=39 p=0.0. Ticker-block bootstrap (2000 resamples, seed 20260913, 16 independent blocks): always-bullish-lift 95% CI [-9.55, -1.98]pp; always-hold-lift 95% CI [18.66, 38.69]pp. ANY LIFT INTERVAL SPANS ZERO: True.

## Stage B finding — 2026-09-13T16:10:00Z

**B2 addendum -- two different "bearish accuracy" quantities, not to be conflated.** The driver's `bearish_call_accuracy_pct` (47.7%, n=44 bearish predictions) is PRECISION on predicted-bearish calls: of the times v6 predicted bearish, 47.7% were right. This is NOT the quantity `wrap-ups/test2-look-ahead-hit-rate-by-year-out.md` and the 09-13 handoff's Sec1 call "bearish-outcome accuracy" (8.3%-24.0% by year) -- that is RECALL on bearish ground truth: of the times a stock actually underperformed benchmark by >5% (a true bearish outcome, n=151), how often v6's call correctly flagged it. Recomputed directly against the same 359-row scorer population: aggregate bearish-outcome recall = 21/151 = 13.9%; by year 2021=11.1% (n=18), 2022=24.0% (n=25), 2023=16.7% (n=30), 2024=8.3% (n=36), 2025=11.9% (n=42) -- reproduces the wrap-up's cited per-year figures exactly. The 09-13 handoff's "wrong roughly four times in five" (implying ~80% wrong / 20% right) UNDERSTATES this: aggregate recall is 13.9% right, i.e. wrong 86.1% of the time (roughly six times in seven, not four in five). B4b corrects this without softening -- the number is worse than stated, not better.

## Stage C finding — 2026-09-13T00:00:00Z

**C1 headline: Arm 0c (equal-weight, fully invested, never traded) is $195,584.28
— above the control ($179,944.91), above Arm 0 ($173,102.24), and above Arm 0b
($120,799.82).** This exceeds the prompt's own expected outcome: it does not
merely say "most of Arm 0's advantage is deployment, not skill" — it says the
entire allocator+analyst+trend-layer machinery, run on this 195-event
population/window, UNDERPERFORMS simply buying all 16 names equally and never
touching them again, by $15,639.37. Cash-share diagnostics support the
deployment story: Arm 0b averages 65.5% cash, Arm 0 averages 15.3% cash,
control averages 26.0% cash — the ranking of average-cash-share is the exact
inverse of the ranking of final value among the three simulator-side arms
(0b < control < 0 in value; 0b > control > 0 in idle cash). Manifest:
analysis/data/value_attribution_v2/stage_c_manifest.json ->
c1_deployment_ladder.

## Stage C finding — 2026-09-13T00:00:00Z

**C2 attempted; per-ticker decomposition does not reconcile — reported as a
methodological failure, not a result.** The point difference
control-minus-Arm-0 reproduces the prompt's $6,842.67 exactly
(stage_c_manifest.json -> c2_bootstrap.actual_point_diff_control_minus_arm0).
But the per-ticker attribution built from realized_sales.realized_gain +
final position_values (grouped by ticker) sums to -$6,168.18 — opposite sign
from the actual +$6,842.67 difference it's supposed to decompose — because it
ignores differing cash balances, trade timing/tax lots, and pooled/compounding
funding order between the two arms (the same non-additivity the prompt
flags for C6). The bootstrap 95% range computed on this broken decomposition
([-$81,686.55, $74,499.01]) is reported in the manifest but explicitly labeled
UNRELIABLE and must not be cited as a confidence interval on $6,842.67. A
methodologically sound version would resample the universe and re-run both
arms' full simulation per resample (~2000 full simulator runs) — not
attempted this session for cost reasons. C2 as specified (a valid bootstrap
range on the $6,842.67 figure) is NOT reached this session.

## Stage C3 (Step 0c + Step 1) -- 2026-09-13

- **0c corrected:** Arm 0c's average idle-cash share, previously reported "not
  applicable" in Stage C, is **8.31%** (`stage_c3_manifest.json` ->
  `step_0c_arm_0c_cash_share.avg_cash_share`, measured on the control run's own
  session-snapshot dates). Corrected ladder: Arm 0b (universe-only, forced
  Hold) cash share previously reported ~1.0 (never deploys); Arm 0c 8.31%; Arm
  0 (always-bullish) and control's shares carry over from Stage C
  (control recomputed here for reference: 26.02%, matching Stage C's 26.0% to
  rounding). Arm 0c is NOT a zero-idle-cash construction -- finding, not a
  quiet correction, per the prompt's Sec4/0c instruction.

- **Step 1, cash-parked arm -- finding, not the expected clean result.** The
  literal overlay value is $192,679.64 (`stage_c3_manifest.json` ->
  `step1_cash_parked_arm.final_value`), but this treats every dollar of
  funding shortfall (times the arm needed to sell parked SPY back for a real
  trade but the SPY position's market value had fallen below the dollar
  amount originally parked) as costlessly covered. That shortfall totals
  $12,734.74 (`shortfall_total`) and is EXACTLY the gap between $192,679.64
  and the control's own $179,944.91 (to the cent, after rounding). A
  conservative reading that does not backfill the shortfall
  (`final_value_conservative_no_shortfall_addback`) lands at $179,944.91 --
  statistically indistinguishable from control. BOTH readings land well below
  buy-and-hold's $195,584.28. This directly contradicts the prompt's Sec5
  framing of a clean "at/above -> idle capital, well below -> strategy problem"
  test outcome by surfacing a THIRD possibility this session did not
  anticipate: the honest answer is closer to "idle cash parked in SPY doesn't
  even beat leaving it at zero, on this corpus and window," because the
  2022 SPY drawdown coincided with when cash needed to be pulled back for
  real trades. Reported here as a finding per the prompt's standing rule that
  a diagnostic contradicting a stated expectation is a finding, not a reason
  to stop.

## Stage C3 (Steps 2-4) -- 2026-09-13, continuation session

- **B2's disable mechanic is NOT ambiguous as a code location** (contra the
  flag in `PREREGISTRATION.json` -> `stage_c.ablations_c3.B2_disable_rule3`):
  it is a single guard clause, `analysis/simulator/allocator_v2.py` lines
  143-147 inside `_decide_add()`. But confirming that location surfaced a
  real, unregistered finding: **in the settled `swap_funding` pooled cell
  this run actually executes, Rule 3 does not block the Add at all.** The
  session driver's own buy-dollar target for an Add
  (`sweep_cadence_and_session_model.py` lines ~866-877) is sized from
  `recommended_size`/cap only and never reads cost basis; when Rule 3 makes
  `decide_v2`'s natural buy return `[]`, the swap-funding shortfall
  calculation (`target - natural`) just treats the entire target as a
  shortfall and funds it by selling another position instead. So "B2" as
  measured here is really "fund adds to speculative losers from free cash
  vs. by displacing another position" -- not "allow vs. block averaging
  down." This plausibly explains why it is the single largest-moving
  ablation ($9,417.91 vs. control, sign-stable 16/16 leave-one-out worlds):
  it changes which positions get displaced and when, not whether the
  speculative loser gets added to.

- **B4 (uniform starter sizing) first implementation attempt was a driver
  bug, caught before reporting.** The first run patched
  `allocator_v3.STARTER_PCT_SPECULATIVE`/`STARTER_PCT_ESTABLISHED`, which
  landed at EXACTLY zero effect on the full universe AND on all 16
  leave-one-out worlds -- too clean to trust without checking. Traced the
  actual code path: `sweep_cadence_and_session_model.py` imported those two
  names BY VALUE at its own module-load time (`from ... import NAME`), so
  patching `allocator_v3`'s attribute afterward never reached the function
  that actually computes starter dollars in the executed
  `scope=new_calls_only, execution_order=pooled` path. Fixed by patching
  `sweep_cadence_and_session_model`'s own module attributes instead
  (`analysis/value_attribution_v2_stage_c3_step234_driver.py`, committed at
  `0d65718`). **Re-running with the corrected patch target produced the
  identical zero-effect result** -- so the zero IS genuine, not the bug.
  Verified independently via `funding_log`: every first-call funding event
  in the control run shows `binding: "session limit"` -- the 2.5pp
  per-session speed limit (X) clips the buy far below both the starter
  target (5%/8%/6.5%) and the cap, so differences between starter
  percentages never reach the executed trade. **This is a genuine,
  verified finding: under the settled X=2.5pp configuration, starter sizing
  cannot matter, because the session speed limit is always the binding
  constraint on a first-call buy.**

- **B3 (disable profit-take) is also a genuine, verified zero.** Confirmed
  by direct trade-log inspection of the control run: `Counter(t.reason for
  t in portfolio.transaction_log)` shows ZERO trades with reason
  `"profit-take-25pct-trigger"` across the entire 195-event, ~2.4-year
  simulation. The rule never fires under this corpus and configuration, so
  disabling it changes nothing. (Distinct from the separate
  `PROFIT_TAKE_PCT = 25.0` local constant inside
  `run_session_sweep_cell`, which gates the §8 pet-formation model and is
  moot here since `veto_p=0.0` in the settled cell.)

- **B1 (disable Type A/B caps) costs the system money** (-$812.60 vs.
  control) but is the LEAST sign-stable of the four under leave-one-out
  (13/16 preserve sign; dropping NVDA, ENVX, or TTD flips or zeroes it) --
  the smallest and least robust of the four ablation effects.

- **Ranking by size, no significance claimed (no C4 range exists yet):**
  B2 (+$9,417.91, earns) > B4 (=$0.00) = B3 (=$0.00) > B1 (-$812.60, costs).
  Every ablation arm still trails buy-and-hold ($195,584.28) by a wide
  margin ($6,221.47 to $16,451.97 short) -- none of the four rules,
  individually disabled, closes the gap.

- **Drawdowns (Step 4), raw figures, no ratio computed or ranked:** control
  and all four ablations cluster tightly (~$21.5-22.4K peak-to-trough,
  ~20.9-21.7%, same 2022-04-01 to 2022-12-27 window) except B2, whose
  larger deployed capital (lower avg cash share, 22.76% vs 26.02%) produces
  a slightly deeper drawdown ($22,402.72, 21.73%). Buy-and-hold (Arm 0c) has
  by far the worst drawdown of any arm in the whole ladder: $48,320.98
  (36.53%), Jan-Jun 2022 -- the corpus's highest-return arm also carries the
  most risk by this raw measure, and nothing in Stage C looked at this
  until now. The cash-parked arm (conservative reading) sits between:
  $31,694.60 (31.69%).

## Stage D (prompts/value-attribution-v2-stage-d.md), 2026-09-13/14

- **Step 0d, no-unlabelable-tail check: CONFIRMED, 0 of 195 events unlabelable.**
  price_cache.json frozen at 2026-05-08 gives a labelability cutoff near
  2025-11-07; the locked population's last call_date is 2024-06-12, well
  inside it. Matches the prompt's expectation -- not a contradiction here.

- **Step 1 oracle label split (195 events, `analysis/data/run_manifests/
  value_attribution_v2_stage_d_manifest.json` -> `results.label_report`):
  bullish 83 (42.6%), bearish 85 (43.6%), neutral 27 (13.8%).** Directionally
  close to but not identical to Stage B's ground-truth distribution (bearish
  named at 42.1% of events in the Stage D prompt itself, sourced from Stage
  B); the ~1.5pp difference is consistent with Stage B's scorer population
  (n=359, thin-year-filtered) differing from this run's simulator population
  (n=195, the dedup'd call-date-windowed subset) -- not a discrepancy in the
  label logic, which reuses analyst_direct_scorer.py's constants unmodified.

- **Step 2, D-both @ X=2.5pp ceiling: $263,073.65** (`...manifest.json` ->
  `results.step2_ceiling_x2_5.final_value`, single deterministic replay, not
  a median), a LOOK-AHEAD CEILING, +$83,128.74 vs control ($179,944.91) and
  +$67,489.37 vs buy-and-hold ($195,584.28). Two-level sanity check: call-level
  and final_action-level hit rate are BOTH 100% (195/195) -- the trend-layer
  override gap the prompt expected (call-level ~100%, final_action-level
  below it) did NOT materialize here. This is because the non-direction
  field synthesis (pre-registered as bound-loosening) was deliberately built
  to never conflict with the oracle's own direction, so the trend layer's
  override machinery has nothing to override. Reported as a finding, not a
  failure: it is a direct, expected consequence of the pre-registered
  synthesis choice, not evidence the label derivation disagrees with the
  scorer. Binding: 97.2% of the 71 funding events bind on "session limit",
  2.8% on "target gap", 0% on "cash available" -- the SAME dominant binding
  reason Stage C3 found on the real control, so even a perfect analyst is
  overwhelmingly throttle-bound at X=2.5. The ceiling nonetheless sits far
  ABOVE control, not at or below it -- the pre-registered "landing at/below
  control" finding did NOT occur.

- **Step 3 directional split (X=2.5pp):** D-up (perfect bullish only, real
  calls elsewhere) = $243,917.54, changed 22 of 195 final calls vs. the real
  run despite overriding 83 events (most bullish oracle overrides coincided
  with what the real analyst already called correctly there). D-down
  (perfect bearish only) = $201,898.84, changed all 85 overridden events'
  final action (0 coincided with the real analyst's actual call on those same
  events) -- consistent with Stage B's finding that the real analyst catches
  very few of the true bearish events. D-down's funding events are 100%
  session-limit-bound (67/67); D-up's binding mix is much more mixed (48.2%
  session limit, 50.0% cash available, 1.8% target gap) because Exit actions
  on the bearish leg are absent in D-up, leaving more natural cash from
  normal trims. D-down lands well above control (+$21,953.93), NOT near it --
  the prompt's "D-down near control would mean downside calls are worth
  nothing here" scenario did not occur; downside-only perfect calls ARE
  worth something even under today's allocator, though less than upside-only
  ($21,953.93 vs $63,972.63 vs control).

- **Step 4, the 6-cell grid (`...manifest.json` -> `results.step4_grid`,
  each a single deterministic replay):**

  | X | real analyst | D-both |
  |---|---|---|
  | 2.5pp (settled) | $179,944.91 | $263,073.65 |
  | 10pp | $145,059.93 | $423,293.79 |
  | unlimited | $150,997.56 | $510,894.01 |

  **Finding that contradicts the prompt's stated Step-4 expectation:**
  raising X *lowers* the real analyst's final value (179,944.91 ->
  145,059.93 -> 150,997.56 -- a real, not noise-level, decline of
  -$28,947.35 from settled to unlimited), while it sharply *raises* D-both's
  ($263,073.65 -> $510,894.01, +$247,820.37). None of the prompt's three
  pre-registered readings fits cleanly: D-both@2.5 is NOT near control (46%
  above it), so "limited by plumbing" doesn't apply as stated; D-both@unlimited
  is NOT near control either, so "limited by neither" doesn't apply; and the
  real analyst does not track D-both's gain from loosening X -- it moves the
  OPPOSITE direction. **Best-supported reading, stated plainly rather than
  forced into one of the three: the ceiling is limited mainly by PREDICTION,
  not plumbing.** Even fully throttled at today's X=2.5pp, a perfect analyst
  already earns $83,128.74 more than the real system -- most of the
  achievable headroom exists WITHOUT touching the throttle at all. The real
  analyst's calls are wrong often enough that giving them more room to act
  (raising X) makes results WORSE, not better -- the analyst is not
  throttle-starved, it is prediction-starved. The additional ceiling
  available by also loosening X ($263,073.65 -> $510,894.01 for a perfect
  analyst) is real but is a headroom source the real analyst cannot reach
  regardless of X, because its direction calls are the binding constraint,
  not the session limit.

- **Step 5 drawdowns (dollars/percent, `...manifest.json` ->
  `results.step5_drawdowns`):** D-both@2.5 has the SMALLEST drawdown of any
  arm in this stage ($18,167.38, 8.17%, 2024-03-21 to 2024-04-20) despite the
  highest final value at that X -- consistent with Stage C3's finding that
  drawdown tracks how invested an arm is, not how well it calls direction;
  D-both is only ~49% invested on average (avg_cash_share = 0.508) at X=2.5.
  The real analyst's drawdown WORSENS sharply as X rises (20.85% at X=2.5 ->
  43.73% at X=10 -> 46.80% unlimited) while D-both's drawdown stays modest
  and roughly flat (8.17% -> 14.23% -> 12.65%) -- raising X lets the real
  analyst's wrong calls compound losses faster, while a perfect analyst's
  gains are structurally protected by being correct. No risk-adjusted ratio
  computed, per the prompt's instruction.
