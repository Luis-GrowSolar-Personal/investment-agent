#!/usr/bin/env python3
"""
rule3_disposition_driver.py -- run_id 'rule3-disposition' (prompts/rule3-disposition.md).

Measures three dispositions of the allocator's Rule 3 ("don't average down on
a speculative loser trading below cost basis"):

  R3-keep    -- status quo. Guard live, but (per Stage C3's finding) does not
                actually block the add in the settled swap_funding/pooled
                path -- a blocked add is displacement-funded (another
                position is sold to cover it).
  R3-remove  -- guard disabled entirely (identical technique to Stage C3's
                ablation_B2_disable_rule3: monkeypatch
                allocator_v2._weighted_cost_basis to always return None).
  R3-enforce -- guard live AND made to actually enforce: a blocked add's
                dollar target is never created in the first place, so no
                shortfall/displacement is ever generated to cover it. See
                PREREGISTRATION.json -> three_configurations.R3_enforce for
                the mechanics and the considered-and-resolved ambiguity.

R3-enforce cannot be built with a simple attribute monkeypatch because the
session driver's `intended` (target-dollar) computation for an Add is INLINE
inside run_session_sweep_cell (analysis/sweep_cadence_and_session_model.py),
not a separately-patchable helper -- this is exactly what Stage C3's B2
finding established. This driver therefore builds a patched IN-MEMORY COPY
of that one function (via inspect.getsource + a single, narrow, documented
string replacement + exec into a namespace that is a shallow copy of the
real module's own globals) and calls that copy only for the R3-enforce arm.
The on-disk file analysis/sweep_cadence_and_session_model.py is never
written to, at any point, by this driver -- confirmed by hash comparison
before and after every run in main().

ZERO Anthropic API calls. ZERO DB writes to any stored Analysis row. No
production/spec file touched (asserted via before/after sha256 checks in
main()).

Usage:
    cd analysis && python3 rule3_disposition_driver.py
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

import analysis.sweep_cadence_and_session_model as S  # noqa: E402
from analysis.simulator.data import PriceLookup  # noqa: E402
import analysis.simulator.allocator_v2 as AV2  # noqa: E402
import analysis.simulator.allocator_v3 as AV3  # noqa: E402
from analysis.value_attribution_v2_stage_d_driver import (  # noqa: E402
    build_oracle_labels, apply_oracle, ORACLE_SYNTHESIS,
)

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
INITIAL_CAPITAL = 100_000.0
EXPECTED_CONTROL = 179_944.91          # R3-keep -- Stage C3 control
EXPECTED_R3_REMOVE = 189_362.81        # Stage C3's B2_disable_rule3
BUY_AND_HOLD = 195_584.28
ALL16 = S.ALL16
WINDOW_END = S.C
PROTECTED_FILES = [
    SCRIPT_DIR / "sweep_cadence_and_session_model.py",
    SCRIPT_DIR / "simulator" / "allocator_v2.py",
    SCRIPT_DIR / "simulator" / "allocator_v3.py",
    REPO_ROOT / "server" / "lib" / "versions.js",
    REPO_ROOT / "docs" / "architecture" / "VERSION_REGISTRY.json",
    REPO_ROOT / "PROMOTION_GATE.md" if (REPO_ROOT / "PROMOTION_GATE.md").exists()
        else REPO_ROOT / "docs" / "architecture" / "PROMOTION_GATE.md",
    REPO_ROOT / "docs" / "EVALUATION_PROMPT.md",
]

RUN_STATE_DIR = SCRIPT_DIR / "data" / "run_state" / "rule3-disposition"
MANIFEST_DIR = SCRIPT_DIR / "data" / "run_manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = MANIFEST_DIR / "rule3_disposition_manifest.json"


def git_commit_and_dirty():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT).decode().strip())
    return commit, dirty


def sha256_file(p: Path) -> str:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def protected_file_hashes():
    return {str(p.relative_to(REPO_ROOT)): sha256_file(p) for p in PROTECTED_FILES}


# ---------------------------------------------------------------------------
# R3-remove: identical technique to Stage C3's ablation_B2_disable_rule3.
# ---------------------------------------------------------------------------
@contextmanager
def r3_remove():
    orig = AV2._weighted_cost_basis
    AV2._weighted_cost_basis = lambda *a, **k: None
    try:
        yield
    finally:
        AV2._weighted_cost_basis = orig


@contextmanager
def r3_keep():
    yield


# ---------------------------------------------------------------------------
# R3-enforce: build an in-memory PATCHED COPY of run_session_sweep_cell.
# See PREREGISTRATION.json -> three_configurations.R3_enforce for the
# mechanics and the considered-and-resolved ambiguity. The on-disk file is
# never written to -- verified by hash comparison in main().
# ---------------------------------------------------------------------------
_ORIG_SNIPPET = '''                target_dollars = (target_pct / 100.0) * portfolio_value_before
                delta = target_dollars - current_dollars_before
                if delta > 0:
                    intended += delta'''

_PATCHED_SNIPPET = '''                target_dollars = (target_pct / 100.0) * portfolio_value_before
                delta = target_dollars - current_dollars_before
                r3_blocked = False
                if _R3_ENFORCE_ACTIVE and tier == "speculative":
                    _cb = _weighted_cost_basis(portfolio, event.ticker)
                    if _cb is not None and price < _cb:
                        r3_blocked = True
                        _r3_enforce_blocked_log.append({
                            "date": sd, "ticker": event.ticker,
                            "delta_suppressed": delta,
                        })
                if delta > 0 and not r3_blocked:
                    intended += delta'''


def _build_r3_enforce_function():
    src = inspect.getsource(S.run_session_sweep_cell)
    assert src.count(_ORIG_SNIPPET) == 1, (
        "R3-enforce patch target not found exactly once -- "
        "sweep_cadence_and_session_model.py has changed since this driver "
        "was written; ABORT rather than patch the wrong thing."
    )
    patched_src = src.replace(_ORIG_SNIPPET, _PATCHED_SNIPPET, 1)
    patched_src = patched_src.replace(
        "def run_session_sweep_cell(", "def run_session_sweep_cell_r3_enforce(", 1
    )
    ns = dict(vars(S))  # shallow copy of the real module's globals
    ns["_weighted_cost_basis"] = AV2._weighted_cost_basis
    ns["_R3_ENFORCE_ACTIVE"] = True
    blocked_log = []
    ns["_r3_enforce_blocked_log"] = blocked_log
    code = compile(patched_src, "<rule3_disposition_r3_enforce_patch>", "exec")
    exec(code, ns)
    return ns["run_session_sweep_cell_r3_enforce"], blocked_log


R3_ENFORCE_FN, R3_ENFORCE_BLOCKED_LOG = _build_r3_enforce_function()


@contextmanager
def r3_enforce():
    R3_ENFORCE_BLOCKED_LOG.clear()
    try:
        yield
    finally:
        pass


CONFIGS = {
    "R3_keep": (r3_keep, S.run_session_sweep_cell),
    "R3_remove": (r3_remove, S.run_session_sweep_cell),
    "R3_enforce": (r3_enforce, R3_ENFORCE_FN),
}


def run_cell(events, prices, type_fn, driver_fn, tier_fn, arm_key, cell_overrides=None):
    ctx, fn = CONFIGS[arm_key]
    cell = dict(CELL)
    if cell_overrides:
        cell.update(cell_overrides)
    with ctx():
        r = fn(events, prices, type_fn, driver_fn, tier_fn, phase_offset=0, seed=0, **cell)
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
    return {
        "max_drawdown_dollars": max_dd_dollar,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_date_range": [str(dd_peak_date), str(dd_trough_date)],
    }


def trade_counts(r):
    funding_log = r.get("funding_log", [])
    displacement_log = r.get("displacement_log", [])
    n_buys = sum(1 for f in funding_log if f["actual_dollars"] > 1e-6)
    n_displacement_sells = len(displacement_log)
    binding_counts = {}
    for f in funding_log:
        binding_counts[f["binding"]] = binding_counts.get(f["binding"], 0) + 1
    total_binding = sum(binding_counts.values())
    binding_share = {k: v / total_binding for k, v in binding_counts.items()} if total_binding else {}
    return {
        "n_funding_events": len(funding_log),
        "n_buys_funded": n_buys,
        "n_displacement_funded_sells": n_displacement_sells,
        "binding_reason_counts": binding_counts,
        "binding_reason_share": binding_share,
    }


def by_calendar_year(dates, values, control_dates, control_values):
    """Difference vs control, bucketed by calendar year (last snapshot value
    observed in each year), and the largest single-quarter contributing
    difference change."""
    def last_per_year(dates_, values_):
        out = {}
        for d, v in zip(dates_, values_):
            out[d.year] = v
        return out

    def last_per_quarter(dates_, values_):
        out = {}
        for d, v in zip(dates_, values_):
            out[(d.year, (d.month - 1) // 3 + 1)] = v
        return out

    y_arm = last_per_year(dates, values)
    y_ctl = last_per_year(control_dates, control_values)
    by_year = {}
    for y in sorted(set(y_arm) & set(y_ctl)):
        by_year[y] = y_arm[y] - y_ctl[y]

    q_arm = last_per_quarter(dates, values)
    q_ctl = last_per_quarter(control_dates, control_values)
    common_q = sorted(set(q_arm) & set(q_ctl))
    q_diffs = {q: q_arm[q] - q_ctl[q] for q in common_q}
    largest_q = None
    largest_q_contrib = 0.0
    prev_diff = 0.0
    for q in common_q:
        contrib = q_diffs[q] - prev_diff
        if abs(contrib) > abs(largest_q_contrib):
            largest_q_contrib = contrib
            largest_q = q
        prev_diff = q_diffs[q]
    return {
        "diff_by_calendar_year": {str(y): v for y, v in by_year.items()},
        "largest_contributing_quarter": (f"{largest_q[0]}Q{largest_q[1]}" if largest_q else None),
        "largest_contributing_quarter_dollars": largest_q_contrib,
    }


def main() -> int:
    print("=== rule3_disposition_driver.py -- run_id 'rule3-disposition' ===")
    print("ASSERTION: zero Anthropic API calls. One read-only DB SELECT via "
          "S.load_events_dedup_on(), reused for every arm below. No stored "
          "Analysis row modified. No price-cache refresh. No production file "
          "written (verified by hash before/after).")

    hashes_before = protected_file_hashes()

    commit, dirty = git_commit_and_dirty()
    print(f"git commit: {commit}  dirty: {dirty}")
    if dirty:
        print("HARD STOP: git tree is dirty. Aborting per Step 0a.")
        return 1

    print("\n--- Loading events once ---")
    events_full, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    print(f"  {len(events_full)} events loaded.")

    manifest = {
        "run_id": "rule3-disposition",
        "git_commit": commit,
        "git_dirty": dirty,
        "driver_file": "analysis/rule3_disposition_driver.py",
        "cell": CELL,
        "seed": 0,
        "phase_offset": 0,
    }

    # =======================================================================
    # Step 0c -- reproduce control and R3-remove to the cent
    # =======================================================================
    print("\n--- Step 0c: reproduction check ---")
    r_control = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, "R3_keep")
    r_remove = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, "R3_remove")
    control_val = r_control["final_value"]
    remove_val = r_remove["final_value"]
    control_match = abs(control_val - EXPECTED_CONTROL) < 0.01
    remove_match = abs(remove_val - EXPECTED_R3_REMOVE) < 0.01
    print(f"  R3_keep:   got=${control_val:,.2f}  expected=${EXPECTED_CONTROL:,.2f}  "
          f"{'MATCH' if control_match else 'MISMATCH -- STOP'}")
    print(f"  R3_remove: got=${remove_val:,.2f}  expected=${EXPECTED_R3_REMOVE:,.2f}  "
          f"{'MATCH' if remove_match else 'MISMATCH -- STOP'}")
    manifest["step0c_reproduction"] = {
        "R3_keep": {"got": control_val, "expected": EXPECTED_CONTROL, "match": control_match},
        "R3_remove": {"got": remove_val, "expected": EXPECTED_R3_REMOVE, "match": remove_match},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    if not (control_match and remove_match):
        print("\nHARD STOP per prompt Step 0c: reproduction failed. Reporting and stopping.")
        return 1

    # =======================================================================
    # Step 1 -- three configurations, full universe
    # =======================================================================
    print("\n--- Step 1: three configurations (full universe) ---")
    step1 = {}
    full_runs = {}
    r3_enforce_blocked_full = None
    for arm_key in ("R3_keep", "R3_remove", "R3_enforce"):
        r = run_cell(events_full, prices, type_fn, driver_fn, tier_fn, arm_key)
        if arm_key == "R3_enforce":
            r3_enforce_blocked_full = list(R3_ENFORCE_BLOCKED_LOG)
        final_value = r["final_value"]
        avg_cash_share, dyi = cash_share_and_dollar_years(r)
        snaps = r["daily_snapshots"]
        dates = [s.date for s in snaps]
        values = [s.total_value for s in snaps]
        full_runs[arm_key] = (r, dates, values)
        dd = drawdown_stats(dates, values)
        tc = trade_counts(r)
        step1[arm_key] = {
            "final_value": final_value,
            "delta_vs_control": final_value - control_val,
            "delta_vs_buy_and_hold": final_value - BUY_AND_HOLD,
            "avg_cash_share": avg_cash_share,
            "dollar_years_invested": dyi,
            "drawdown": dd,
            "trade_counts": tc,
        }
        print(f"  {arm_key}: final=${final_value:,.2f}  Δcontrol=${final_value - control_val:,.2f}  "
              f"max_dd={dd['max_drawdown_pct']:.2%}  buys={tc['n_buys_funded']}  "
              f"displacement_sells={tc['n_displacement_funded_sells']}")

    step1["R3_enforce"]["n_events_blocked"] = len(r3_enforce_blocked_full)
    step1["R3_enforce"]["dollars_suppressed_total"] = sum(
        e["delta_suppressed"] for e in r3_enforce_blocked_full
    )
    step1["tax_note"] = (
        "The simulator models NO taxes anywhere -- no federal/state, no LTCG/"
        "STCG distinction is computed in any figure in this report. All final "
        "values above are pre-tax. The three arms differ materially in trade "
        "count (see trade_counts.n_buys_funded / n_displacement_funded_sells "
        "per arm above), so a real-world after-tax ranking of the three could "
        "differ from this pre-tax ranking -- more trades generally means more "
        "realized gains/losses. This exposure is flagged, not estimated."
    )
    manifest["step1_three_configs"] = step1
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print("\nStep 1 written to manifest (interim save).")

    with open(RUN_STATE_DIR / "cells.jsonl", "a") as f:
        for arm_key in ("R3_keep", "R3_remove", "R3_enforce"):
            f.write(json.dumps({
                "cell_key": f"step1__{arm_key}",
                "params": {**CELL, "arm": arm_key},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "arm": arm_key}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": {"final_value": step1[arm_key]["final_value"]},
            }) + "\n")

    # =======================================================================
    # Step 2 -- leave-one-company-out for R3-enforce (16 runs), each vs. a
    # FRESH R3-keep run in the SAME reduced universe (16 more runs).
    # =======================================================================
    print("\n--- Step 2: leave-one-company-out for R3-enforce (32 runs) ---")
    step2 = {"R3_enforce": {"effect_by_ticker_dropped": {}}}
    full_effect_r3_enforce = step1["R3_enforce"]["delta_vs_control"]
    n_same_sign = 0
    biggest_mover = None
    biggest_mover_delta = 0.0
    for dropped in ALL16:
        events_sub = [e for e in events_full if e.ticker != dropped]
        r_ctl_sub = run_cell(events_sub, prices, type_fn, driver_fn, tier_fn, "R3_keep")
        r_enf_sub = run_cell(events_sub, prices, type_fn, driver_fn, tier_fn, "R3_enforce")
        effect = r_enf_sub["final_value"] - r_ctl_sub["final_value"]
        step2["R3_enforce"]["effect_by_ticker_dropped"][dropped] = effect
        same_sign = (effect >= 0) == (full_effect_r3_enforce >= 0)
        if same_sign:
            n_same_sign += 1
        change = abs(effect - full_effect_r3_enforce)
        if change > biggest_mover_delta:
            biggest_mover_delta = change
            biggest_mover = dropped
        print(f"  drop={dropped}: R3_keep=${r_ctl_sub['final_value']:,.2f}  "
              f"R3_enforce=${r_enf_sub['final_value']:,.2f}  effect=${effect:,.2f}")
        with open(RUN_STATE_DIR / "cells.jsonl", "a") as f:
            f.write(json.dumps({
                "cell_key": f"step2_leave_one_out__drop_{dropped}",
                "params": {**CELL, "dropped": dropped},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "dropped": dropped}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": {"R3_keep": r_ctl_sub["final_value"], "R3_enforce": r_enf_sub["final_value"],
                            "effect": effect},
            }) + "\n")

    step2["R3_enforce"]["full_universe_effect"] = full_effect_r3_enforce
    step2["R3_enforce"]["n_of_16_preserving_sign"] = n_same_sign
    step2["R3_enforce"]["company_changing_effect_most"] = biggest_mover
    step2["R3_enforce"]["change_in_effect_dollars"] = biggest_mover_delta

    # Restate (not re-run) R3-remove's leave-one-out from Stage C3.
    stage_c3_manifest_path = SCRIPT_DIR / "data" / "value_attribution_v2" / "stage_c3_manifest.json"
    stage_c3_manifest = json.loads(stage_c3_manifest_path.read_text())
    b2_stability = stage_c3_manifest["step3_leave_one_company_out"]["sign_stability"]["B2_disable_rule3"]
    step2["R3_remove_restated_from_stage_c3"] = {
        "source": "analysis/data/value_attribution_v2/stage_c3_manifest.json -> "
                   "step3_leave_one_company_out.sign_stability.B2_disable_rule3",
        "full_universe_effect": b2_stability["full_universe_effect"],
        "n_of_16_preserving_sign": b2_stability["n_of_16_preserving_sign"],
        "company_changing_effect_most": b2_stability["company_changing_effect_most"],
        "change_in_effect_dollars": b2_stability["change_in_effect_dollars"],
        "not_rerun": True,
    }
    print(f"\n  R3_enforce: full_effect=${full_effect_r3_enforce:,.2f}  "
          f"sign preserved {n_same_sign}/16  biggest mover={biggest_mover}")
    print(f"  R3_remove (restated from Stage C3): full_effect="
          f"${b2_stability['full_universe_effect']:,.2f}  "
          f"sign preserved {b2_stability['n_of_16_preserving_sign']}/16")

    manifest["step2_leave_one_out"] = step2
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print("\nStep 2 written to manifest (interim save).")

    # =======================================================================
    # Step 3 -- perfect-analyst ceiling under each configuration (D-both)
    # =======================================================================
    print("\n--- Step 3: perfect-analyst ceiling (D-both) under each configuration ---")
    oracle_labels, label_report = build_oracle_labels(events_full)
    events_oracle, extra_fields, n_overridden = apply_oracle(events_full, oracle_labels, "D-both")
    S.recompute_trend_layer(events_oracle, tier_fn, extra_fields)

    step3 = {"label_report": label_report, "n_overridden": n_overridden}
    for arm_key in ("R3_keep", "R3_remove", "R3_enforce"):
        events_oracle_copy = copy.deepcopy(events_oracle)
        r = run_cell(events_oracle_copy, prices, type_fn, driver_fn, tier_fn, arm_key)
        step3[arm_key] = {
            "final_value_LOOKAHEAD_CEILING_NOT_A_RESULT": r["final_value"],
        }
        print(f"  {arm_key} @ D-both (LOOK-AHEAD CEILING): ${r['final_value']:,.2f}")
        with open(RUN_STATE_DIR / "cells.jsonl", "a") as f:
            f.write(json.dumps({
                "cell_key": f"step3_ceiling_D_both__{arm_key}",
                "params": {**CELL, "arm": arm_key, "oracle_mode": "D-both"},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "arm": arm_key, "oracle_mode": "D-both"},
                                          sort_keys=True)).encode()
                ).hexdigest(),
                "results": {"final_value": r["final_value"]},
            }) + "\n")

    manifest["step3_ceiling"] = step3
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print("\nStep 3 written to manifest (interim save).")

    # =======================================================================
    # Step 4 -- timing: difference by calendar year, R3-remove and R3-enforce
    # vs. control
    # =======================================================================
    print("\n--- Step 4: timing (calendar-year breakdown) ---")
    r_ctl, dates_ctl, values_ctl = full_runs["R3_keep"]
    step4 = {}
    for arm_key in ("R3_remove", "R3_enforce"):
        r_arm, dates_arm, values_arm = full_runs[arm_key]
        step4[arm_key] = by_calendar_year(dates_arm, values_arm, dates_ctl, values_ctl)
        print(f"  {arm_key}: {step4[arm_key]['diff_by_calendar_year']}  "
              f"largest quarter={step4[arm_key]['largest_contributing_quarter']} "
              f"(${step4[arm_key]['largest_contributing_quarter_dollars']:,.2f})")

    manifest["step4_timing"] = step4
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print("\nStep 4 written to manifest.")

    # =======================================================================
    # Final protected-file integrity check
    # =======================================================================
    hashes_after = protected_file_hashes()
    unchanged = all(hashes_before[k] == hashes_after[k] for k in hashes_before)
    manifest["protected_files_unchanged"] = unchanged
    manifest["protected_file_hashes_before"] = hashes_before
    manifest["protected_file_hashes_after"] = hashes_after
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nProtected production files unchanged on disk: {unchanged}")
    if not unchanged:
        print("HARD STOP: a protected file changed on disk during this run.")
        return 1

    print(f"\nManifest written to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
