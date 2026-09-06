#!/usr/bin/env python3
"""
test5_universe_substitution.py -- prompts/test5-universe-substitution.md

Test 5 (docs/handoffs/2026-09-03-state-of-play.md §7): does the portfolio's
performance come from the analyst's specific stock selections, or from
generic exposure to a large-cap growth basket? Swap the ESTABLISHED half of
ALL16 for a different 8-name set chosen by an explicit rule (top-8 by
year-end-2020 S&P market cap, excluding BRK.B), hold the SPECULATIVE 8
fixed, and compare final_value/max_drawdown under the identical settled
configuration.

Reuses Test 1's exact pipeline (sweep_cadence_and_session_model.py's
load_events_dedup_on() pattern -> run_session_sweep_cell), generalized here
to take an arbitrary established-ticker list instead of the hardcoded
ALL16 (that file is not modified). No LLM calls, no API spend, no DB
writes -- SELECT only.

Usage:
    cd analysis
    python3 test5_universe_substitution.py step1   # Arm A reproduction
    python3 test5_universe_substitution.py step2   # Arm B run
    python3 test5_universe_substitution.py step5   # optional resampling distribution
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup, load_call_events
from trend_analyst import build_tier_function
from type_classifier import build_type_function, build_driver_count_function

RUN_ID = "test5-universe-substitution"
RUN_STATE = REPO / "analysis" / "data" / "run_state" / RUN_ID
RUN_STATE.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_STATE / "cells.jsonl"
FINDINGS_PATH = RUN_STATE / "findings.md"
PROGRESS_PATH = RUN_STATE / "progress.json"

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)

SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ARM_A_ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
ARM_B_ESTABLISHED = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "V", "JNJ"]
TOP20_2021_POOL = [  # analysis/audit_top20_2021.py EXPECTED, BRK.B excluded
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "ADBE",
    "V", "JNJ", "WMT", "JPM", "PG", "UNH", "DIS", "NVDA",
    "MA", "HD", "PYPL", "BAC", "NFLX",
]

EXPECTED_REFERENCE_FINAL = 179944.90608455567  # cells.jsonl (analyst-sensitivity) -> *_q0.0 -> results.final_value
EXPECTED_REFERENCE_DD = 0.20852310359539084
ZERO_INFO_FLOOR = 120799.8165376159  # the prompt's OWN cited figure -- see Step 0 flag


def sha256_file(path: Path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                           text=True, check=True).stdout.strip()


def git_state():
    """Dirty means a TRACKED file has local modifications -- untracked files
    from other concurrent sessions on this shared branch (confirmed present:
    other in-flight prompts/run_state under different run_ids) are not this
    run's business and do not block it, consistent with prior drivers on
    this branch treating known-unrelated untracked noise as non-blocking."""
    commit = git("rev-parse", "HEAD")
    status_lines = git("status", "--porcelain").splitlines()
    tracked_dirty = [l for l in status_lines if not l.startswith("??")]
    return commit, bool(tracked_dirty), tracked_dirty


def load_universe(established, speculative, label):
    """Generalizes sweep_cadence_and_session_model.load_events_dedup_on()
    for an arbitrary established-ticker list. Body mirrors that function
    exactly; only the ticker list is parameterized."""
    universe = list(established) + list(speculative)
    events_full = load_call_events(tickers=universe, end_date=S.C, dedupe_same_day_calls=True)
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(SCRIPT_DIR / "data" / "price_cache.json",
                                   SCRIPT_DIR / "data" / "fundamentals_cache.json")
    extra_fields = S.fetch_extra_fields(universe, S.C)
    S.recompute_trend_layer(events_full, tier_fn, extra_fields)
    prices = PriceLookup.from_cache(SCRIPT_DIR / "data" / "price_cache.json")
    print(f"  [{label}] universe={universe}")
    print(f"  [{label}] n_events={len(events_full)}")
    return events_full, type_fn, driver_fn, tier_fn, prices


def run_arm(events, prices, type_fn, driver_fn, tier_fn, tie_seed=0):
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=tie_seed, **CELL)
    return r


def append_cell(record):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def append_finding(text):
    with FINDINGS_PATH.open("a") as f:
        f.write(text.rstrip() + "\n\n")


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"run_id": RUN_ID, "steps": {}, "notes": []}


def save_progress(p):
    PROGRESS_PATH.write_text(json.dumps(p, indent=2, default=str))


def config_hash(commit, arm, established, tie_seed):
    payload = json.dumps({"driver_commit": commit, "arm": arm,
                           "established": sorted(established), "tie_seed": tie_seed,
                           "cell": CELL}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def already_done():
    done = {}
    if CELLS_PATH.exists():
        for line in CELLS_PATH.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                done[rec["config_hash"]] = rec
            except Exception:
                continue
    return done


def compute_summary_extras(r):
    keys = ["final_value", "max_dd", "distinct_tickers", "baseline_finals", "baseline_drawdowns"]
    return {k: r.get(k) for k in keys if k in r}


def step0_hygiene_and_premises():
    commit, dirty, tracked_dirty = git_state()
    if dirty:
        print(f"FATAL: tracked files dirty: {tracked_dirty}")
        return None
    print(f"git commit: {commit}, tracked-dirty: {dirty}")

    # Premise check 2: ESTABLISHED/SPECULATIVE constant consistency across
    # its ~15 copies in analysis/*.py
    import subprocess as sp
    grep = sp.run(["grep", "-rn", r"^ESTABLISHED\s*=\|^SPECULATIVE\s*=",
                   *[str(p) for p in SCRIPT_DIR.glob("*.py")]],
                  capture_output=True, text=True)
    lines = [l for l in grep.stdout.splitlines() if l.strip()]
    est_lists = set()
    spec_lists = set()
    for l in lines:
        if "ESTABLISHED" in l.split(":")[-1].split("=")[0]:
            est_lists.add(l.split("=", 1)[1].strip())
        else:
            spec_lists.add(l.split("=", 1)[1].strip())
    print(f"ESTABLISHED constant copies found: {len(est_lists)} distinct value(s) across "
          f"{sum(1 for l in lines if 'ESTABLISHED' in l.split(':')[-1].split('=')[0])} files")
    print(f"SPECULATIVE constant copies found: {len(spec_lists)} distinct value(s)")
    drift = len(est_lists) > 1 or len(spec_lists) > 1
    if drift:
        print("DRIFT DETECTED:", est_lists, spec_lists)
    else:
        print("No drift: all copies identical.")
    print("NOTE: analysis/sweep_cadence_and_session_model.py (named in the prompt as "
          "'the file Test 1's harness actually imports' / source of truth) does NOT "
          "itself define an ESTABLISHED/SPECULATIVE constant -- only ALL16 (the flat "
          "16-ticker list) and a dynamically-computed tier_fn. See findings.md.")

    return {"commit": commit, "est_drift": drift, "est_lists": list(est_lists),
            "spec_lists": list(spec_lists)}


def cmd_step0():
    result = step0_hygiene_and_premises()
    if result is None:
        return 1
    progress = load_progress()
    progress["steps"]["0_premises"] = "done"
    progress["premise_check_2"] = result
    save_progress(progress)
    print(json.dumps(result, indent=2))
    return 0


def cmd_step1():
    """Arm A reproduction, uncorrupted (no perturbation), tie_seed=0."""
    commit, dirty, _ = git_state()
    if dirty:
        print("FATAL: tracked files dirty"); return 1
    events, type_fn, driver_fn, tier_fn, prices = load_universe(
        ARM_A_ESTABLISHED, SPECULATIVE, "Arm A")
    r = run_arm(events, prices, type_fn, driver_fn, tier_fn, tie_seed=0)
    ch = config_hash(commit, "A", ARM_A_ESTABLISHED, 0)
    rec = {"cell_key": "arm_a", "params": {"established": ARM_A_ESTABLISHED, "tie_seed": 0},
           "config_hash": ch, "driver_commit": commit, "results": compute_summary_extras(r)}
    append_cell(rec)
    fv, dd = r["final_value"], r["max_dd"]
    print(f"Arm A: final_value={fv:,.2f}  max_dd={dd*100:.4f}%")
    print(f"Expected reference (analyst-sensitivity cells.jsonl *_q0.0): "
          f"{EXPECTED_REFERENCE_FINAL:,.2f} / {EXPECTED_REFERENCE_DD*100:.4f}%")
    match = abs(fv - EXPECTED_REFERENCE_FINAL) < 0.01 and abs(dd - EXPECTED_REFERENCE_DD) < 1e-9
    print(f"Matches uncorrupted q=0.0 reference: {match}")
    print(f"Matches prompt's cited $120,800 zero-info figure: {abs(fv - ZERO_INFO_FLOOR) < 0.01}")
    progress = load_progress()
    progress["steps"]["1_arm_a"] = "done"
    progress["arm_a_result"] = {"final_value": fv, "max_dd": dd, "matches_q0_reference": match}
    save_progress(progress)
    return 0


def cmd_step2():
    """Arm B run, identical config, swapped established set."""
    commit, dirty, _ = git_state()
    if dirty:
        print("FATAL: tracked files dirty"); return 1
    events, type_fn, driver_fn, tier_fn, prices = load_universe(
        ARM_B_ESTABLISHED, SPECULATIVE, "Arm B")
    if len(events) == 0:
        print("FATAL: zero events loaded for Arm B universe -- stop, per prompt's own gate.")
        return 1
    r = run_arm(events, prices, type_fn, driver_fn, tier_fn, tie_seed=0)
    ch = config_hash(commit, "B", ARM_B_ESTABLISHED, 0)
    rec = {"cell_key": "arm_b", "params": {"established": ARM_B_ESTABLISHED, "tie_seed": 0},
           "config_hash": ch, "driver_commit": commit, "results": compute_summary_extras(r)}
    append_cell(rec)
    print(f"Arm B: final_value={r['final_value']:,.2f}  max_dd={r['max_dd']*100:.4f}%")
    print(f"Arm B distinct_tickers={r['distinct_tickers']}")
    progress = load_progress()
    progress["steps"]["2_arm_b"] = "done"
    progress["arm_b_result"] = {"final_value": r["final_value"], "max_dd": r["max_dd"]}
    save_progress(progress)
    return 0


def cmd_step5(n_draws=25, seed=20260906):
    """Optional resampling: 8 established names drawn at random from
    TOP20_2021_POOL, n_draws times, speculative fixed. Arm A's real result
    is compared as a percentile against this distribution."""
    commit, dirty, _ = git_state()
    if dirty:
        print("FATAL: tracked files dirty"); return 1
    rng = random.Random(seed)
    done = already_done()
    finals = []
    for i in range(n_draws):
        drawn = rng.sample(TOP20_2021_POOL, 8)
        ch = config_hash(commit, f"resample_{i}", drawn, 0)
        if ch in done:
            r_results = done[ch]["results"]
            print(f"  [reuse] draw {i}: {drawn} -> {r_results['final_value']:,.2f}")
            finals.append(r_results["final_value"])
            continue
        events, type_fn, driver_fn, tier_fn, prices = load_universe(drawn, SPECULATIVE, f"resample_{i}")
        if len(events) == 0:
            print(f"  draw {i}: 0 events, skipping"); continue
        r = run_arm(events, prices, type_fn, driver_fn, tier_fn, tie_seed=0)
        rec = {"cell_key": f"resample_{i}", "params": {"established": drawn, "seed": seed, "draw_index": i},
               "config_hash": ch, "driver_commit": commit, "results": compute_summary_extras(r)}
        append_cell(rec)
        finals.append(r["final_value"])
        print(f"  draw {i}: {drawn} -> final={r['final_value']:,.2f}")

    finals_sorted = sorted(finals)
    n = len(finals_sorted)
    mean = sum(finals_sorted) / n
    var = sum((x - mean) ** 2 for x in finals_sorted) / n
    std = var ** 0.5
    progress = load_progress()
    arm_a_final = progress.get("arm_a_result", {}).get("final_value")
    percentile = None
    if arm_a_final is not None:
        below = sum(1 for x in finals_sorted if x < arm_a_final)
        percentile = 100.0 * below / n
    result = {"n_draws": n, "seed": seed, "mean": mean, "std": std,
              "min": finals_sorted[0], "max": finals_sorted[-1],
              "arm_a_final": arm_a_final, "arm_a_percentile": percentile,
              "finals": finals_sorted}
    print(json.dumps(result, indent=2))
    progress["steps"]["5_resample"] = "done"
    progress["step5_result"] = result
    save_progress(progress)
    append_finding(
        f"## Step 5 -- resampling distribution ({n} draws, seed {seed})\n\n"
        f"mean={mean:,.2f}, std={std:,.2f}, min={finals_sorted[0]:,.2f}, max={finals_sorted[-1]:,.2f}. "
        f"Arm A's real final_value ({arm_a_final:,.2f}) falls at the {percentile:.1f}th percentile "
        f"of this distribution."
    )
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"step0": cmd_step0, "step1": cmd_step1, "step2": cmd_step2, "step5": cmd_step5}.get(cmd)
    if fn is None:
        print("usage: test5_universe_substitution.py [step0|step1|step2|step5]")
        sys.exit(1)
    sys.exit(fn())
