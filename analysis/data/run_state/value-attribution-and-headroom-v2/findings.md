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
