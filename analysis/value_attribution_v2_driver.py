#!/usr/bin/env python3
"""
value_attribution_v2_driver.py -- Stage A of value-attribution-and-headroom-v2.

Arm 0b (universe only, starter-only buy-and-hold) and Arm 0 (always-bullish
through the real allocator).

PREMISE CORRECTION vs. the first draft of this driver: the settled control
figure ($179,944.91) is NOT reproduced by sweep_funding_modes.py's main()
grid (its cells use no_reserve/cash_reserve/swap_funding at 0/5/10/20pp
limits, none of which is the settled X=2.5pp session limit). The actual
settled-configuration driver is `tier_return_attribution.py`'s CELL dict,
which calls into `sweep_cadence_and_session_model.py`:

    CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
                limit_pp=2.5, execution_order="pooled",
                trim_budget_scope="per_event_date", veto_p=0.0)
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=0, **CELL)

This driver reuses that exact path and asserts it reproduces $179,944.91
before running Arms 0b/0, so a broken premise fails loudly rather than
silently producing an uncomparable number.

Override mechanism: `run_session_sweep_cell` (sweep_cadence_and_session_model.py
line 782) computes `final_action = event.final_action or event.per_call_rec or
"Hold"` from each event at simulation time -- it does not take a final_action
override as a parameter. So this driver sets `event.final_action` on every
event AFTER load_events_dedup_on()'s recompute_trend_layer() has already run
and set it from the real trend verdict, overwriting it in-memory before the
session-sweep call. This is a direct final_action substitution -- real
allocator, real caps, real starter sizing -- not a trend-verdict corruption
(distinguishing it from test1_zero_info_floor, which forces every trend
VERDICT to Hold; see PREREGISTRATION.json's window_and_control note).

Zero Anthropic API calls. Zero DB writes -- load_events_dedup_on() /
fetch_extra_fields() are read-only SELECTs, the same loader path Test 1,
tier_return_attribution.py and every prior sweep in this project use. No
stored Analysis row is modified: events are simulator-side dataclasses built
fresh from the DB read each invocation, and final_action is overwritten only
on this in-memory copy, never written back.

Usage:
    cd analysis && python3 value_attribution_v2_driver.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import analysis.sweep_cadence_and_session_model as S  # noqa: E402
from analysis.simulator.data import PriceLookup  # noqa: E402

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
EXPECTED_CONTROL = 179_944.91


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


def run_arm(label: str, forced_final_action: str | None):
    """forced_final_action=None runs the unmodified control (for the
    reproduction assertion). Otherwise every event's final_action is
    overwritten before the session-sweep call."""
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")

    n_overridden = 0
    n_add_natural = sum(1 for e in events if e.final_action == "Add")
    if forced_final_action is not None:
        for e in events:
            e.final_action = forced_final_action
            n_overridden += 1

    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=0, **CELL)
    return r, n_overridden, n_add_natural, len(events)


def main() -> int:
    print("=== value_attribution_v2_driver.py -- Stage A ===")
    print("ASSERTION: zero Anthropic API calls will be made by this driver. "
          "It reads stored Analysis rows via the existing DB SELECT path and "
          "the frozen price_cache.json only.")

    commit, dirty = git_commit_and_dirty()
    print(f"git commit: {commit}  dirty: {dirty}")

    print("\n--- Reproduction check: unmodified control cell ---")
    r_control, _, _, n_events = run_arm("control", None)
    final_control = r_control["final_value"]
    ok = abs(final_control - EXPECTED_CONTROL) < 0.01
    print(f"final_value=${final_control:,.2f}  n_events={n_events}  "
          f"({'MATCHES' if ok else 'DOES NOT MATCH'} ${EXPECTED_CONTROL:,.2f})")
    if not ok:
        print("STOP: control cell does not reproduce settled_control. "
              "Refusing to run Arms 0b/0 against a broken premise.")
        return 1

    results = {}

    print("\n--- Arm 0b: universe only (final_action forced to Hold) ---")
    r_0b, n_over_0b, n_add_nat, n_events_0b = run_arm("arm-0b-universe-only", "Hold")
    print(f"final_value=${r_0b['final_value']:,.2f}  events_overridden={n_over_0b}  "
          f"of which naturally-Add-under-real-trend-layer={n_add_nat}")
    results["arm_0b_universe_only"] = {
        "final_value": r_0b["final_value"],
        "max_dd": r_0b.get("max_dd"),
        "n_events_total": n_events_0b,
        "n_events_overridden_to_Hold": n_over_0b,
        "n_events_naturally_Add_under_real_trend_layer": n_add_nat,
    }

    print("\n--- Arm 0: always-bullish (final_action forced to Add) ---")
    r_0, n_over_0, n_add_nat_0, n_events_0 = run_arm("arm-0-always-bullish", "Add")
    print(f"final_value=${r_0['final_value']:,.2f}  events_overridden={n_over_0}")
    results["arm_0_always_bullish"] = {
        "final_value": r_0["final_value"],
        "max_dd": r_0.get("max_dd"),
        "n_events_total": n_events_0,
        "n_events_overridden_to_Add": n_over_0,
    }

    control = EXPECTED_CONTROL
    floor_test1 = 120_800.00
    print(f"\n--- Comparison ---")
    print(f"Arm 0b (universe only):    ${r_0b['final_value']:,.2f}")
    print(f"Test 1 (zero-info floor):  ${floor_test1:,.2f}")
    print(f"Arm 0 (always-bullish):    ${r_0['final_value']:,.2f}")
    print(f"Actual (settled_control):  ${control:,.2f}")
    print(f"Total added by all three layers (actual - Arm 0b): "
          f"${control - r_0b['final_value']:,.2f}")
    if r_0["final_value"] > control:
        print("Arm 0 > control: always-bullish beats the real system in dollars.")
    else:
        print("Arm 0 <= control: real system beats always-bullish -- "
              "always-bullish-relative lift is NOT grading something unmonetized here.")

    manifest = {
        "run_id": "value-attribution-and-headroom-v2",
        "stage": "A",
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "driver_file": "analysis/value_attribution_v2_driver.py",
        "reproduction_check": {"final_value": final_control, "expected": EXPECTED_CONTROL, "match": ok},
        "cell_params": CELL,
        "phase_offset": 0,
        "seed": 0,
        "event_count": n_events,
        "checksums": {
            "type_classifications.json": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
            "price_cache.json": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache.json": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
        },
        "reference_lines": {
            "arm_0b_final_value": r_0b["final_value"],
            "test1_zero_info_floor": {"value": floor_test1,
                                       "provenance": "docs/architecture/VERSION_REGISTRY.json -> benchmarks.test1_zero_info_floor.figures.final_value"},
            "arm_0_final_value": r_0["final_value"],
            "settled_control": {"value": control,
                                 "provenance": "docs/architecture/VERSION_REGISTRY.json -> benchmarks.settled_control.figures.final_value"},
            "total_added_by_three_layers": control - r_0b["final_value"],
        },
        "results": results,
    }

    out_path = SCRIPT_DIR / "data" / "value_attribution_v2" / "stage_a_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nWrote manifest: {out_path}")

    run_state_dir = SCRIPT_DIR / "data" / "run_state" / "value-attribution-and-headroom-v2"
    with open(run_state_dir / "cells.jsonl", "a") as f:
        for cell_key in ("arm_0b_universe_only", "arm_0_always_bullish"):
            f.write(json.dumps({
                "cell_key": cell_key,
                "params": {**CELL, "phase_offset": 0, "seed": 0},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "phase_offset": 0, "seed": 0}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": results[cell_key],
            }) + "\n")
    print(f"Appended to {run_state_dir / 'cells.jsonl'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
