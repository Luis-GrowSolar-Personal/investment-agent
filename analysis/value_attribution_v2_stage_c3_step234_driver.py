#!/usr/bin/env python3
"""
value_attribution_v2_stage_c3_step234_driver.py -- Stage C3 Steps 2-4 of
value-attribution-and-headroom-v2. RESUME session: Steps 0c and 1 were
already done by value_attribution_v2_stage_c3_driver.py (see that file and
stage_c3_manifest.json's step_0c_arm_0c_cash_share / step1_cash_parked_arm
keys, both left untouched -- this driver only ADDS keys to the same
manifest).

Implements:
  Step 2 -- four ablations (B1 disable Type A/B caps, B2 disable Rule 3
        averaging-down-on-speculative-losers, B3 disable profit-take,
        B4 uniform starter sizing), each a full 195-event re-run against
        the settled cell, against the control and buy-and-hold references.
  Step 3 -- leave-one-company-out: control + 4 ablations, each re-run 16
        times (one company excluded from the universe each time) = 80 runs.
  Step 4 -- drawdown (max peak-to-trough $ and %, date range, largest
        single-quarter decline) for every arm in this run and in C1's
        ladder (Arm 0b, Arm 0c, Arm 0, control, cash-parked, 4 ablations).

Ablation mechanism: module-global monkeypatch on analysis.simulator.
allocator_v2 / allocator_v3, restored after each run. Confirmed against
allocator_v2.py before this driver was written -- see B2 confirmation note
below; NOT ambiguous on inspection, contra the flag in PREREGISTRATION.json.

Zero Anthropic API calls. Zero DB writes (one read-only DB SELECT via
S.load_events_dedup_on(), same as every other driver in this run, done
ONCE and reused -- filtering the returned event list per leave-one-out arm
does not re-query). No stored Analysis row modified. No price-cache
refresh.

Usage:
    cd analysis && python3 value_attribution_v2_stage_c3_step234_driver.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import analysis.sweep_cadence_and_session_model as S  # noqa: E402
from analysis.simulator.data import PriceLookup  # noqa: E402
import analysis.simulator.allocator_v2 as AV2  # noqa: E402
import analysis.simulator.allocator_v3 as AV3  # noqa: E402
from analysis.value_attribution_v2_stage_c3_driver import (  # noqa: E402
    cash_parked_overlay, build_arm_0c_with_cash, arm_0c_cash_share_series,
)

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
INITIAL_CAPITAL = 100_000.0
EXPECTED_CONTROL = 179_944.91
BUY_AND_HOLD = 195_584.28
EXPECTED_ARM_0B = 120_799.82
EXPECTED_ARM_0 = 173_102.24
ALL16 = S.ALL16
WINDOW_END = S.C
MANIFEST_PATH = SCRIPT_DIR / "data" / "value_attribution_v2" / "stage_c3_manifest.json"
RUN_STATE_DIR = SCRIPT_DIR / "data" / "run_state" / "value-attribution-and-headroom-v2"

B4_UNIFORM_STARTER_PCT = 6.5  # blended midpoint of 5.0/8.0, per PREREGISTRATION.json
                               # stage_c.ablations_c3.B4 candidate list -- fixed here,
                               # recorded in the manifest, not silently chosen.


def git_commit_and_dirty():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SCRIPT_DIR.parent
    ).decode().strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=SCRIPT_DIR.parent
    ).decode().strip())
    return commit, dirty


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Ablation mechanics -- module-global monkeypatch, restored in `finally`.
#
# B2 confirmation (per prompt Sec 0b / this run's obligation to confirm
# against allocator_v3.py before running): Rule 3 lives at EXACTLY ONE
# location, analysis/simulator/allocator_v2.py:143-147, inside _decide_add():
#
#     if tier == "speculative":
#         cb = _weighted_cost_basis(portfolio, ticker)
#         if cb is not None and day_price < cb:
#             return []  # don't average down on speculative losers
#
# This is a single, unconditional guard clause with one caller (_decide_add,
# itself called only from decide_v2, itself called from allocator_v3.decide
# for every non-starter Add). There is no second code path that implements
# averaging-down avoidance elsewhere (grepped: "average" / "Rule 3" /
# "speculative.*loser" across analysis/simulator/*.py). PREREGISTRATION.json's
# flag ("the one ablation most likely to have an ambiguous disable
# mechanic") does NOT hold up on inspection -- there is nothing ambiguous
# about where or how to disable it. Disabling it by making
# _weighted_cost_basis always return None (so `cb is not None` is always
# False) is a clean, minimal patch: it disables exactly this guard and
# nothing else (the same function is not called anywhere except this one
# guard, per grep). This is reported as a finding, not silently assumed.
# ---------------------------------------------------------------------------

@contextmanager
def ablation_B1_disable_caps():
    orig = (AV2.TYPE_A_SPECULATIVE_CAP_PCT, AV2.TYPE_A_ESTABLISHED_CAP_PCT, AV2.TYPE_B_CAP_PCT)
    AV2.TYPE_A_SPECULATIVE_CAP_PCT = 100.0
    AV2.TYPE_A_ESTABLISHED_CAP_PCT = 100.0
    AV2.TYPE_B_CAP_PCT = 100.0
    try:
        yield
    finally:
        (AV2.TYPE_A_SPECULATIVE_CAP_PCT, AV2.TYPE_A_ESTABLISHED_CAP_PCT,
         AV2.TYPE_B_CAP_PCT) = orig


@contextmanager
def ablation_B2_disable_rule3():
    orig = AV2._weighted_cost_basis
    AV2._weighted_cost_basis = lambda *a, **k: None
    try:
        yield
    finally:
        AV2._weighted_cost_basis = orig


@contextmanager
def ablation_B3_disable_profit_take():
    orig = AV2.PROFIT_TAKE_THRESHOLD_PCT
    AV2.PROFIT_TAKE_THRESHOLD_PCT = 10_000.0
    try:
        yield
    finally:
        AV2.PROFIT_TAKE_THRESHOLD_PCT = orig


@contextmanager
def ablation_B4_uniform_starter():
    orig = (AV3.STARTER_PCT_SPECULATIVE, AV3.STARTER_PCT_ESTABLISHED)
    AV3.STARTER_PCT_SPECULATIVE = B4_UNIFORM_STARTER_PCT
    AV3.STARTER_PCT_ESTABLISHED = B4_UNIFORM_STARTER_PCT
    try:
        yield
    finally:
        AV3.STARTER_PCT_SPECULATIVE, AV3.STARTER_PCT_ESTABLISHED = orig


@contextmanager
def no_ablation():
    yield


ABLATIONS = {
    "control": no_ablation,
    "B1_disable_caps": ablation_B1_disable_caps,
    "B2_disable_rule3": ablation_B2_disable_rule3,
    "B3_disable_profit_take": ablation_B3_disable_profit_take,
    "B4_uniform_starter": ablation_B4_uniform_starter,
}


def run_cell(events, prices, type_fn, driver_fn, tier_fn, ctx_mgr):
    with ctx_mgr():
        r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                      phase_offset=0, seed=0, **CELL)
    return r


def cash_share_and_dollar_years(r):
    snaps = r["daily_snapshots"]
    shares = [s.cash_total / s.total_value for s in snaps if s.total_value]
    avg_cash_share = sum(shares) / len(shares) if shares else None
    dyi = 0.0
    for i in range(1, len(snaps)):
        gap_days = (snaps[i].date - snaps[i - 1].date).days
        inv_prev = snaps[i - 1].total_value - snaps[i - 1].cash_total
        inv_cur = snaps[i].total_value - snaps[i].cash_total
        dyi += (inv_prev + inv_cur) / 2.0 * gap_days / 365.25
    return avg_cash_share, dyi


def drawdown_stats(dates, values):
    """Max peak-to-trough decline in $ and %, date range, and largest
    single-quarter decline (bucketing by calendar quarter, last-observed
    snapshot value per quarter as the quarter mark, most negative
    consecutive difference)."""
    if not dates or not values:
        return None
    peak = values[0]
    peak_date = dates[0]
    max_dd_dollar = 0.0
    max_dd_pct = 0.0
    dd_peak_date = dd_trough_date = dates[0]
    for d, v in zip(dates, values):
        if v > peak:
            peak = v
            peak_date = d
        dd = peak - v
        if dd > max_dd_dollar:
            max_dd_dollar = dd
            max_dd_pct = (dd / peak) if peak else 0.0
            dd_peak_date, dd_trough_date = peak_date, d

    # Quarter marks: last snapshot value observed in each (year, quarter).
    quarter_marks = {}
    for d, v in zip(dates, values):
        q = (d.year, (d.month - 1) // 3 + 1)
        quarter_marks[q] = (d, v)  # overwritten -> keeps latest in that quarter
    ordered_quarters = sorted(quarter_marks.keys())
    largest_q_decline_dollar = 0.0
    largest_q_decline_pct = 0.0
    largest_q_range = None
    for i in range(1, len(ordered_quarters)):
        d0, v0 = quarter_marks[ordered_quarters[i - 1]]
        d1, v1 = quarter_marks[ordered_quarters[i]]
        decline = v0 - v1
        if decline > largest_q_decline_dollar:
            largest_q_decline_dollar = decline
            largest_q_decline_pct = (decline / v0) if v0 else 0.0
            largest_q_range = (str(d0), str(d1))

    return {
        "max_drawdown_dollars": max_dd_dollar,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_date_range": [str(dd_peak_date), str(dd_trough_date)],
        "largest_single_quarter_decline_dollars": largest_q_decline_dollar,
        "largest_single_quarter_decline_pct": largest_q_decline_pct,
        "largest_single_quarter_decline_date_range": (
            list(largest_q_range) if largest_q_range else None
        ),
    }


def main() -> int:
    print("=== value_attribution_v2_stage_c3_step234_driver.py -- Steps 2-4 ===")
    print("ASSERTION: zero Anthropic API calls. One read-only DB SELECT via "
          "S.load_events_dedup_on() (same pattern as every prior driver in "
          "this run), reused for every arm below -- no re-query per arm. "
          "No stored Analysis row modified. No price-cache refresh.")
    commit, dirty = git_commit_and_dirty()
    print(f"git commit: {commit}  dirty: {dirty}")

    print("\n--- Loading events once, reused for all 85 runs below ---")
    events_full, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    print(f"  {len(events_full)} events loaded.")

    manifest = json.loads(MANIFEST_PATH.read_text())

    # =======================================================================
    # Step 2 -- four ablations, full universe
    # =======================================================================
    print("\n--- Step 2: four ablations (full universe) ---")
    step2 = {}
    full_universe_runs = {}  # arm_key -> (r, dates, values) for Step 4 reuse
    for arm_key, ctx in ABLATIONS.items():
        r = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, ctx)
        final_value = r["final_value"]
        avg_cash_share, dyi = cash_share_and_dollar_years(r)
        snaps = r["daily_snapshots"]
        dates = [s.date for s in snaps]
        values = [s.total_value for s in snaps]
        full_universe_runs[arm_key] = (r, dates, values)
        step2[arm_key] = {
            "final_value": final_value,
            "avg_cash_share": avg_cash_share,
            "dollar_years_invested": dyi,
            "delta_vs_control": final_value - EXPECTED_CONTROL,
            "delta_vs_buy_and_hold": final_value - BUY_AND_HOLD,
        }
        print(f"  {arm_key}: final=${final_value:,.2f}  "
              f"avg_cash_share={avg_cash_share:.4f}  "
              f"delta_vs_control=${final_value - EXPECTED_CONTROL:,.2f}")

    control_avg_cash_share = step2["control"]["avg_cash_share"]
    for arm_key in ("B1_disable_caps", "B2_disable_rule3",
                    "B3_disable_profit_take", "B4_uniform_starter"):
        step2[arm_key]["delta_avg_cash_share_vs_control"] = (
            step2[arm_key]["avg_cash_share"] - control_avg_cash_share
        )

    manifest["step2_ablations"] = {
        "b4_uniform_starter_pct_chosen": B4_UNIFORM_STARTER_PCT,
        "b2_confirmation": (
            "Confirmed NOT ambiguous: single guard clause, "
            "analysis/simulator/allocator_v2.py lines 143-147 inside "
            "_decide_add(), gated on tier=='speculative' and "
            "_weighted_cost_basis(portfolio, ticker) < day_price. Disabled "
            "by monkeypatching _weighted_cost_basis to always return None."
        ),
        "arms": step2,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nStep 2 written to manifest (interim save).")

    # =======================================================================
    # Step 3 -- leave-one-company-out: control + 4 ablations x 16 tickers
    # =======================================================================
    print("\n--- Step 3: leave-one-company-out (80 runs) ---")
    step3 = {}
    for arm_key, ctx in ABLATIONS.items():
        per_ticker = {}
        for dropped in ALL16:
            events_sub = [e for e in events_full if e.ticker != dropped]
            r = run_cell(events_sub, prices, type_fn, driver_fn, tier_fn, ctx)
            per_ticker[dropped] = r["final_value"]
            print(f"  {arm_key} / drop={dropped}: final=${r['final_value']:,.2f}")
        step3[arm_key] = {"final_value_leaving_out": per_ticker}
        # Append every completed cell immediately (flush-per-cell rule).
        with open(RUN_STATE_DIR / "cells.jsonl", "a") as f:
            f.write(json.dumps({
                "cell_key": f"stage_c3_step3_leave_one_out__{arm_key}",
                "params": {**CELL, "arm": arm_key},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "arm": arm_key}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": per_ticker,
            }) + "\n")

    # Ablation dollar EFFECT in each leave-out world = ablation_final - control_final,
    # both measured WITH the same ticker dropped (apples-to-apples: the
    # effect of the rule change within that reduced universe, not a mix of
    # full-universe control against reduced-universe ablation).
    full_universe_effect = {}
    for arm_key in ("B1_disable_caps", "B2_disable_rule3",
                    "B3_disable_profit_take", "B4_uniform_starter"):
        full_universe_effect[arm_key] = (
            step2[arm_key]["final_value"] - step2["control"]["final_value"]
        )

    sign_stability = {}
    for arm_key in ("B1_disable_caps", "B2_disable_rule3",
                    "B3_disable_profit_take", "B4_uniform_starter"):
        full_sign = full_universe_effect[arm_key] >= 0
        effects_by_ticker = {}
        n_same_sign = 0
        biggest_mover = None
        biggest_mover_delta = 0.0
        for t in ALL16:
            ablation_val = step3[arm_key]["final_value_leaving_out"][t]
            control_val = step3["control"]["final_value_leaving_out"][t]
            effect = ablation_val - control_val
            effects_by_ticker[t] = effect
            same_sign = (effect >= 0) == full_sign
            if same_sign:
                n_same_sign += 1
            change_from_full = abs(effect - full_universe_effect[arm_key])
            if change_from_full > biggest_mover_delta:
                biggest_mover_delta = change_from_full
                biggest_mover = t
        sign_stability[arm_key] = {
            "full_universe_effect": full_universe_effect[arm_key],
            "effect_by_ticker_dropped": effects_by_ticker,
            "n_of_16_preserving_sign": n_same_sign,
            "company_changing_effect_most": biggest_mover,
            "change_in_effect_dollars": biggest_mover_delta,
        }
        print(f"  {arm_key}: full_effect=${full_universe_effect[arm_key]:,.2f}  "
              f"sign preserved in {n_same_sign}/16  "
              f"biggest mover={biggest_mover} (Δ${biggest_mover_delta:,.2f})")

    manifest["step3_leave_one_company_out"] = {
        "design": "PREREGISTRATION.json -> stage_c3.leave_one_company_out_design",
        "n_runs": 80,
        "raw": step3,
        "sign_stability": sign_stability,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nStep 3 written to manifest (interim save).")

    # =======================================================================
    # Step 4 -- drawdowns for every arm in this run and C1's ladder
    # =======================================================================
    print("\n--- Step 4: drawdowns ---")
    step4 = {}

    # Control + 4 ablations: reuse full_universe_runs from Step 2.
    for arm_key, (r, dates, values) in full_universe_runs.items():
        step4[arm_key] = drawdown_stats(dates, values)
        print(f"  {arm_key}: max_dd=${step4[arm_key]['max_drawdown_dollars']:,.2f} "
              f"({step4[arm_key]['max_drawdown_pct']:.2%})")

    # Arm 0b (forced Hold) and Arm 0 (forced Add): re-run fresh with a
    # deep-copied event list so final_action forcing does not mutate the
    # shared events_full used above.
    for label, forced_action, expected in (
        ("arm_0b_universe_only", "Hold", EXPECTED_ARM_0B),
        ("arm_0_always_bullish", "Add", EXPECTED_ARM_0),
    ):
        events_forced = copy.deepcopy(events_full)
        for e in events_forced:
            e.final_action = forced_action
        r = run_cell(events_forced, prices, type_fn, driver_fn, tier_fn, no_ablation)
        got = r["final_value"]
        match = abs(got - expected) < 1.0
        print(f"  {label}: got=${got:,.2f} expected=${expected:,.2f} "
              f"{'MATCH' if match else 'MISMATCH (flagged)'}")
        snaps = r["daily_snapshots"]
        dates = [s.date for s in snaps]
        values = [s.total_value for s in snaps]
        step4[label] = drawdown_stats(dates, values)
        step4[label]["reproduction_check"] = {"got": got, "expected": expected, "match": match}

    # Arm 0c (buy-and-hold): reuse the full (non-downsampled) per-snapshot
    # series computed the same way as Step 0c, using the control run's own
    # snapshot dates (already the case for that function).
    r_control, _, _ = full_universe_runs["control"]
    snapshot_dates = [s.date for s in r_control["daily_snapshots"]]
    arm_0c = build_arm_0c_with_cash(events_full, prices)
    full_series = []
    for sd in snapshot_dates:
        idle_cash = 0.0
        invested_value = 0.0
        for t, h in arm_0c["holdings"].items():
            if h["shares"] <= 0 or h["buy_date"] is None:
                idle_cash += arm_0c["slice_dollars_per_ticker"]
                continue
            if h["buy_date"] > sd:
                idle_cash += arm_0c["slice_dollars_per_ticker"]
            else:
                p = prices.price_on(t, sd)
                invested_value += h["shares"] * p if p else 0.0
        full_series.append((sd, idle_cash + invested_value))
    dates_0c = [x[0] for x in full_series]
    values_0c = [x[1] for x in full_series]
    step4["arm_0c_equal_weight_never_traded"] = drawdown_stats(dates_0c, values_0c)
    print(f"  arm_0c: max_dd=${step4['arm_0c_equal_weight_never_traded']['max_drawdown_dollars']:,.2f} "
          f"({step4['arm_0c_equal_weight_never_traded']['max_drawdown_pct']:.2%})")

    # Cash-parked arm: reconstruct a conservative per-snapshot value series
    # (shortfalls NOT backfilled -- consistent with Step 1's honest reading)
    # using the same overlay mechanics as cash_parked_overlay(), but keeping
    # the running series instead of only the final number.
    snaps = r_control["daily_snapshots"]
    spy_shares = 0.0
    prev_cash = 0.0
    parked_dates = []
    parked_values = []
    for s in snaps:
        cash_i = s.cash_total
        delta = cash_i - prev_cash
        spy_px = prices.price_on("SPY", s.date)
        if spy_px and spy_px > 0:
            if delta > 0:
                spy_shares += delta / spy_px
            elif delta < 0:
                need = -delta
                avail = spy_shares * spy_px
                covered = min(need, avail)
                spy_shares -= covered / spy_px
                # shortfall (need - covered) NOT backfilled -- conservative.
        prev_cash = cash_i
        spy_val = spy_shares * (spy_px or 0.0)
        invested_positions = s.total_value - s.cash_total
        parked_dates.append(s.date)
        parked_values.append(invested_positions + spy_val)
    step4["cash_parked_arm_conservative"] = drawdown_stats(parked_dates, parked_values)
    print(f"  cash_parked (conservative): max_dd="
          f"${step4['cash_parked_arm_conservative']['max_drawdown_dollars']:,.2f} "
          f"({step4['cash_parked_arm_conservative']['max_drawdown_pct']:.2%})")

    manifest["step4_drawdowns"] = step4
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nStep 4 written to manifest.")

    # Append summary cells for Step 2 and Step 4 (Step 3 already flushed per-arm above)
    with open(RUN_STATE_DIR / "cells.jsonl", "a") as f:
        f.write(json.dumps({
            "cell_key": "stage_c3_step2_ablations",
            "params": CELL,
            "config_hash": hashlib.sha256(
                (commit + json.dumps({**CELL, "cell_key": "stage_c3_step2_ablations"},
                                       sort_keys=True)).encode()
            ).hexdigest(),
            "results": {k: v["final_value"] for k, v in step2.items()},
        }) + "\n")
        f.write(json.dumps({
            "cell_key": "stage_c3_step4_drawdowns",
            "params": CELL,
            "config_hash": hashlib.sha256(
                (commit + json.dumps({**CELL, "cell_key": "stage_c3_step4_drawdowns"},
                                       sort_keys=True)).encode()
            ).hexdigest(),
            "results": {k: v["max_drawdown_dollars"] for k, v in step4.items()},
        }) + "\n")
    print(f"Appended Step 2/4 summary cells to {RUN_STATE_DIR / 'cells.jsonl'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
