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
