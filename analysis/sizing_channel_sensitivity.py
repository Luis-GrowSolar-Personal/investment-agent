#!/usr/bin/env python3
"""sizing_channel_sensitivity.py — prompts/sizing-channel-sensitivity.md

Perturbs CallEvent.recommended_size (the sizing channel, consumed on the
Add branch only via decide_v3 -> _decide_add's
`min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct`
clamp) rather than the recommendation/action channel Test 1
(analyst_sensitivity_harness.py, untouched by this file) already measured.
No LLM calls, no API spend, no DB writes -- same loader
(sweep_cadence_and_session_model.load_events_dedup_on()) and settled cell
(swap_funding, K=30, new_calls_only, X=2.5pp, pooled, per_event_date) as
Test 1, plus a read of Test 4's already-saved raw/*.json to derive the
calibration std.

Usage:
    cd analysis
    python3 sizing_channel_sensitivity.py census    # Step 1
    python3 sizing_channel_sensitivity.py control   # Step 2 control cell
    python3 sizing_channel_sensitivity.py grid      # Step 2 full grid
"""
from __future__ import annotations

import glob
import json
import random
import statistics as st
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
from analysis.simulator.data import PriceLookup
from analysis.simulator.allocator_v2 import (
    TYPE_A_ESTABLISHED_CAP_PCT, TYPE_A_SPECULATIVE_CAP_PCT, TYPE_B_CAP_PCT,
)

RUN_ID = "sizing-channel-sensitivity"
RUN_STATE = REPO / "analysis" / "data" / "run_state" / RUN_ID
RUN_STATE.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_STATE / "cells.jsonl"
FINDINGS_PATH = RUN_STATE / "findings.md"
CENSUS_PATH = RUN_STATE / "census.json"

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)

N_SEEDS = 15
TIE_SEED_FIXED = 0

# Sane domain clamp for corrupted recommended_size (a size can't be
# negative or absurdly above the largest cap in the system).
SIZE_MIN, SIZE_MAX = 0.0, 100.0


def _git_state():
    """Follows test5_universe_substitution.py's precedent: only tracked
    (non-'??') lines count as dirty. This session's working tree carries
    several untracked files from other, unrelated sessions (handoff docs,
    other prompt files) that are not this run's to stage or touch."""
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    tracked_dirty = [l for l in status.splitlines() if l.strip() and not l.startswith("??")]
    return commit, bool(tracked_dirty), tracked_dirty


def append_cell(record: dict):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def append_finding(text: str):
    with FINDINGS_PATH.open("a") as f:
        f.write(text.rstrip() + "\n\n")


def already_done() -> set:
    done = set()
    if CELLS_PATH.exists():
        for line in CELLS_PATH.read_text().splitlines():
            if not line.strip():
                continue
            try:
                done.add(json.loads(line)["config_hash"])
            except Exception:
                continue
    return done


def config_hash(commit, cell_key, seed, tie_seed):
    import hashlib
    payload = json.dumps({"driver_commit": commit, "cell_key": cell_key,
                           "seed": seed, "tie_seed": tie_seed, "cell": CELL},
                          sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_corpus():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    return events, type_fn, driver_fn, tier_fn, prices


def run_cell(events_variant, prices, type_fn, driver_fn, tier_fn, tie_seed=TIE_SEED_FIXED):
    r = S.run_session_sweep_cell(events_variant, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=tie_seed, **CELL)
    return {
        "final_value": r["final_value"],
        "max_dd": r["max_dd"],
        "distinct_tickers": r["distinct_tickers"],
    }


# --------------------------------------------------------------------------
# Step 1: measured-noise derivation from Test 4's raw output
# --------------------------------------------------------------------------

def derive_measured_std():
    files = sorted(glob.glob(str(REPO / "analysis" / "test4_noise_floor" / "raw" / "*.json")))
    per_std, per_spread = [], []
    for f in files:
        d = json.load(open(f))
        vals = [r["structured"].get("recommendedSize") for r in d["runs"] if r.get("structured")]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            per_std.append(st.pstdev(vals))
            per_spread.append(max(vals) - min(vals))
    return {
        "n_transcripts": len(per_std),
        "median_std": st.median(per_std),
        "mean_std": st.mean(per_std),
        "max_std": max(per_std),
        "median_spread": st.median(per_spread),
        "max_spread": max(per_spread),
    }


def step_census(events, type_fn, driver_fn, tier_fn):
    from collections import Counter
    action_counts = Counter()
    add_events = []
    for e in events:
        fa = e.final_action or e.per_call_rec or "Hold"
        action_counts[fa] += 1
        if fa == "Add":
            add_events.append(e)

    n_total = len(events)
    n_add = len(add_events)

    sizes = [e.recommended_size for e in add_events if e.recommended_size is not None]
    n_null = sum(1 for e in add_events if e.recommended_size is None)
    n_zero = sum(1 for e in add_events if e.recommended_size == 0.0)

    clamp_rows = []
    n_spec_over_cap = 0
    n_estab_over_cap = 0
    n_spec = 0
    n_estab = 0
    for e in add_events:
        if e.recommended_size is None:
            continue
        tier = tier_fn(e.ticker) if tier_fn else None
        type_c = type_fn(e.ticker) if type_fn else None
        if type_c == "B":
            cap = TYPE_B_CAP_PCT
        elif tier == "speculative":
            cap = TYPE_A_SPECULATIVE_CAP_PCT
            n_spec += 1
        else:
            cap = TYPE_A_ESTABLISHED_CAP_PCT
            n_estab += 1
        over = e.recommended_size > cap
        if over:
            if tier == "speculative":
                n_spec_over_cap += 1
            elif type_c != "B":
                n_estab_over_cap += 1
        clamp_rows.append({"ticker": e.ticker, "recommended_size": e.recommended_size,
                            "tier": tier, "type": type_c, "cap": cap, "clamped": over})

    hist_bins = list(range(0, 105, 10))
    hist = Counter()
    for v in sizes:
        b = min(int(v // 10) * 10, 90)
        hist[b] += 1

    measured = derive_measured_std()

    census = {
        "n_total_events": n_total,
        "action_counts": dict(action_counts),
        "n_add": n_add,
        "add_share_pct": round(100 * n_add / n_total, 2) if n_total else None,
        "n_add_with_size": len(sizes),
        "n_add_null_size": n_null,
        "n_add_zero_size": n_zero,
        "size_min": min(sizes) if sizes else None,
        "size_median": st.median(sizes) if sizes else None,
        "size_max": max(sizes) if sizes else None,
        "size_histogram_by_decade": dict(sorted(hist.items())),
        "n_speculative_add_over_15cap": n_spec_over_cap,
        "n_established_add_over_35cap": n_estab_over_cap,
        "n_speculative_add_events": n_spec,
        "n_established_add_events": n_estab,
        "measured_recommendedSize_std_from_test4": measured,
    }
    CENSUS_PATH.write_text(json.dumps(census, indent=2, default=str))
    print(json.dumps(census, indent=2, default=str))
    return census


# --------------------------------------------------------------------------
# Step 2: perturbation cells
# --------------------------------------------------------------------------

def clamp_size(v):
    return max(SIZE_MIN, min(SIZE_MAX, v))


def make_variant(events, cell_key, seed, corpus_median_size):
    """Returns a new list of CallEvents with recommended_size perturbed
    per cell_key. Only Add events with non-null recommended_size are
    touched by jitter/biased cells (Hold/Trim/Exit never consume the
    field; leaving them untouched changes nothing downstream)."""
    if cell_key == "control":
        return events
    if cell_key == "size_ignored":
        return [replace(e, recommended_size=None) for e in events]
    if cell_key == "size_fixed":
        return [replace(e, recommended_size=corpus_median_size)
                if (e.final_action or e.per_call_rec or "Hold") == "Add" else e
                for e in events]

    rng = random.Random(seed * 1_000_003 + (hash(cell_key) % 97))
    out = []
    for e in events:
        fa = e.final_action or e.per_call_rec or "Hold"
        if fa != "Add" or e.recommended_size is None:
            out.append(e)
            continue
        v = e.recommended_size
        if cell_key.startswith("jitter_"):
            mult = float(cell_key.split("_")[1].rstrip("x"))
            v = v + rng.gauss(0, mult * corpus_median_size_std)
        elif cell_key == "biased_high":
            v = v + corpus_median_size_std
        elif cell_key == "biased_low":
            v = v - corpus_median_size_std
        out.append(replace(e, recommended_size=clamp_size(v)))
    return out


corpus_median_size_std = None  # set in main() after Step 1


def main():
    if len(sys.argv) < 2:
        print("usage: sizing_channel_sensitivity.py [census|control|grid]")
        return 1
    mode_arg = sys.argv[1]
    commit, dirty, tracked_dirty = _git_state()
    if dirty:
        print(f"FATAL: tracked files dirty, refusing to run: {tracked_dirty}")
        return 1

    t0 = time.time()
    events, type_fn, driver_fn, tier_fn, prices = load_corpus()
    print(f"corpus loaded: n_events={len(events)} in {time.time()-t0:.1f}s", flush=True)
    done = already_done()

    if mode_arg == "census":
        step_census(events, type_fn, driver_fn, tier_fn)
        return 0

    if not CENSUS_PATH.exists():
        step_census(events, type_fn, driver_fn, tier_fn)
    census = json.loads(CENSUS_PATH.read_text())
    global corpus_median_size_std
    corpus_median_size_std = census["measured_recommendedSize_std_from_test4"]["median_std"]
    corpus_median_size = census["size_median"]

    if mode_arg == "control":
        ch = config_hash(commit, "control_1a", None, None)
        if ch in done:
            print("[reuse] control_1a")
        else:
            res = run_cell(events, prices, type_fn, driver_fn, tier_fn, tie_seed=0)
            rec = {"cell_key": "control_1a", "params": {}, "config_hash": ch,
                   "driver_commit": commit, "results": res}
            append_cell(rec)
            print(f"control_1a final={res['final_value']:,.2f} dd={res['max_dd']*100:.4f}%")
            expected = 179944.91
            if abs(res["final_value"] - expected) > 0.01:
                append_finding(
                    f"STOP: control_1a final_value={res['final_value']} does not "
                    f"match Test 1's phase-0 uncorrupted reference {expected} — "
                    f"hard-stop gate per prompt Step 1a.")
                print(f"FATAL: control did not reproduce Test 1's {expected}")
                return 1
            append_finding(f"control_1a reproduced Test 1's reference exactly: "
                            f"final_value={res['final_value']}, max_dd={res['max_dd']}")
        return 0

    if mode_arg == "grid":
        cell_keys = ["control", "jitter_0.5x", "jitter_1x", "jitter_2x", "jitter_3x",
                     "biased_high", "biased_low", "size_ignored", "size_fixed"]
        for cell_key in cell_keys:
            for seed in range(N_SEEDS):
                ch = config_hash(commit, cell_key, seed, TIE_SEED_FIXED)
                if ch in done:
                    continue
                variant = make_variant(events, cell_key, seed, corpus_median_size)
                res = run_cell(variant, prices, type_fn, driver_fn, tier_fn, tie_seed=TIE_SEED_FIXED)
                rec = {"cell_key": cell_key, "params": {"seed": seed, "tie_seed": TIE_SEED_FIXED},
                       "config_hash": ch, "driver_commit": commit, "results": res}
                append_cell(rec)
            print(f"  {cell_key} done ({time.time()-t0:.0f}s total)", flush=True)
        print(f"DONE in {time.time()-t0:.0f}s")
        return 0

    print("unknown arg")
    return 1


if __name__ == "__main__":
    sys.exit(main())
