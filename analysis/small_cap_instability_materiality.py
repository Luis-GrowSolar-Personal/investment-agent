#!/usr/bin/env python3
"""small_cap_instability_materiality.py — prompts/small-cap-instability-materiality.md

Per-cap-tier corruption harness. Extends Test 1's perturb_events pattern
(analysis/analyst_sensitivity_harness.py, NOT modified) to accept a
per-cap-tier q instead of one global q, so the observed small/micro-cap
flip-rate concentration (Test 4) can be applied at its own measured rate
per tier rather than uniformly. recommended_size is left untouched (the
sizing-channel run, analysis/sizing_channel_sensitivity.py, established
that channel is inert; this run isolates the categorical channel only).

No LLM calls, no API spend, no DB writes. Same loader
(sweep_cadence_and_session_model.load_events_dedup_on()) and settled cell
as Test 1 and the sizing-channel run.

Usage:
    cd analysis
    python3 small_cap_instability_materiality.py census
    python3 small_cap_instability_materiality.py control
    python3 small_cap_instability_materiality.py grid
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

RUN_ID = "small-cap-instability-materiality"
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

ORDER = ["Add", "Hold", "Trim", "Exit"]
HEALTH = ["Strengthening", "Intact", "Weakening", "Broken"]

# Prompt's own cap-tier sampling mapping (Test 4's universe, Step 1b) --
# NOT the simulator's own tier_fn (speculative/established) or type_fn
# (A/B). SPWR was excluded from Test 4's universe; assigned small_micro's
# rate per the prompt (§1b), verified immaterial in Step 1 (see findings).
CAP_TIER_MAP = {
    "AAPL": "megacap", "GOOGL": "megacap", "NVDA": "megacap", "MSFT": "megacap", "TSLA": "megacap",
    "AVGO": "large", "AMD": "large", "ORCL": "large",
    "FSLR": "mid", "TTD": "mid",
    "QS": "small_micro", "AMPX": "small_micro", "ENVX": "small_micro",
    "EOSE": "small_micro", "RUN": "small_micro", "SPWR": "small_micro",
}


def cap_tier(ticker):
    return CAP_TIER_MAP.get(ticker, "UNMAPPED")


def _git_state():
    """Only tracked (non-'??') lines count as dirty -- same precedent as
    test5_universe_substitution.py and sizing_channel_sensitivity.py. This
    working tree carries several untracked files from other, unrelated
    sessions that are not this run's to stage or touch."""
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


def config_hash(commit, cell_key, seed, tie_seed, q_desc):
    import hashlib
    payload = json.dumps({"driver_commit": commit, "cell_key": cell_key,
                           "seed": seed, "tie_seed": tie_seed, "cell": CELL,
                           "q_desc": q_desc}, sort_keys=True)
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
# Step 1c: reconcile the flip rate directly from Test 4's raw output
# --------------------------------------------------------------------------

def reconcile_flip_rates():
    files = sorted(glob.glob(str(REPO / "analysis" / "test4_noise_floor" / "raw" / "*.json")))
    by_tier = {}
    for f in files:
        d = json.load(open(f))
        t = d["tier"]
        recs = [r["structured"].get("recommendation") for r in d["runs"] if r.get("structured")]
        by_tier.setdefault(t, []).append({"transcript_id": d["transcript_id"],
                                           "ticker": d["ticker"], "recs": recs})
    out = {}
    for tier, items in by_tier.items():
        n = len(items)
        # Definition used here: a transcript "flips" if two or more of its
        # 5 runs' `recommendation` values differ (None counted as its own
        # distinct value if present -- checked separately below to confirm
        # it changes nothing in this corpus).
        flip_incl_none = [it for it in items if len(set(it["recs"])) > 1]
        flip_non_null = [it for it in items
                          if len(set(x for x in it["recs"] if x is not None)) > 1]
        out[tier] = {
            "n": n,
            "flip_count_incl_none_as_distinct": len(flip_incl_none),
            "flip_count_non_null_only": len(flip_non_null),
            "flip_rate": len(flip_incl_none) / n if n else 0.0,
            "flipped_transcripts": [it["transcript_id"] for it in flip_incl_none],
        }
    return out


# --------------------------------------------------------------------------
# Step 1 census + reconciliation
# --------------------------------------------------------------------------

def step_census(events):
    from collections import Counter
    counts = Counter(cap_tier(e.ticker) for e in events)
    total = len(events)
    reconciled = reconcile_flip_rates()

    census = {
        "n_total_events": total,
        "events_per_cap_tier": dict(counts),
        "share_per_cap_tier_pct": {k: round(100 * v / total, 2) for k, v in counts.items()},
        "reconciled_flip_rates": reconciled,
    }
    CENSUS_PATH.write_text(json.dumps(census, indent=2, default=str))
    print(json.dumps(census, indent=2, default=str))
    return census


def reconciled_q_per_tier(census):
    r = census["reconciled_flip_rates"]
    return {
        "megacap": r["megacap"]["flip_rate"],
        "large": r["large"]["flip_rate"],
        "mid": r["mid"]["flip_rate"],
        "small_micro": r["small_micro"]["flip_rate"],  # SPWR assigned this rate too, per §1b
    }


def uniform_equivalent_q(events, q_per_tier):
    from collections import Counter
    counts = Counter(cap_tier(e.ticker) for e in events)
    total = len(events)
    expected_corrupted = sum(counts[t] * q_per_tier[t] for t in counts)
    return expected_corrupted / total, expected_corrupted


# --------------------------------------------------------------------------
# Step 2: per-tier perturbation
# --------------------------------------------------------------------------

def perturb_events_per_tier(events, mode: str, q_fn, corruption_seed: int):
    """q_fn(ticker) -> q in [0,1]. Same corruption logic as Test 1's
    perturb_events (adjacent/uniform modes over final_action/per_call_rec/
    thesis_health in lockstep), but the accept-probability q varies by
    event via q_fn instead of being one global constant. Returns
    (new_events, n_corrupted)."""
    rng = random.Random(corruption_seed * 1_000_003 + (hash(mode) % 97))
    out = []
    n_corrupted = 0
    for e in events:
        fa = e.final_action or e.per_call_rec or "Hold"
        rec = e.per_call_rec or "Hold"
        health = e.thesis_health if e.thesis_health in HEALTH else "Intact"
        q = q_fn(e.ticker)
        u = rng.random()
        if u < q:
            n_corrupted += 1
            fa_idx = ORDER.index(fa)
            rec_idx = ORDER.index(rec)
            hidx = HEALTH.index(health)
            if mode == "uniform":
                new_fa = ORDER[rng.randrange(4)]
                new_rec = ORDER[rng.randrange(4)]
                new_health = HEALTH[rng.randrange(4)]
            elif mode == "adjacent":
                d_pick = rng.choice([-1, 1])
                def _apply(idx):
                    if idx == 0: d = 1
                    elif idx == 3: d = -1
                    else: d = d_pick
                    return min(3, max(0, idx + d))
                new_fa = ORDER[_apply(fa_idx)]
                new_rec = ORDER[_apply(rec_idx)]
                new_health = HEALTH[_apply(hidx)]
            else:
                raise ValueError(mode)
        else:
            new_fa, new_rec, new_health = fa, rec, health
        out.append(replace(e, final_action=new_fa, per_call_rec=new_rec, thesis_health=new_health))
    return out, n_corrupted


def force_hold(events, ticker_pred):
    n = 0
    out = []
    for e in events:
        if ticker_pred(e.ticker):
            n += 1
            out.append(replace(e, final_action="Hold", per_call_rec="Hold", thesis_health="Intact"))
        else:
            out.append(e)
    return out, n


def main():
    if len(sys.argv) < 2:
        print("usage: small_cap_instability_materiality.py [census|control|grid]")
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
        step_census(events)
        return 0

    if not CENSUS_PATH.exists():
        step_census(events)
    census = json.loads(CENSUS_PATH.read_text())
    q_per_tier = reconciled_q_per_tier(census)
    uniform_q, expected_corrupted = uniform_equivalent_q(events, q_per_tier)

    if mode_arg == "control":
        ch = config_hash(commit, "control_1a", None, None, "control")
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
                append_finding(f"STOP: control_1a final_value={res['final_value']} "
                                f"does not match {expected} — hard-stop gate.")
                print(f"FATAL: control did not reproduce {expected}")
                return 1
            append_finding(f"control_1a reproduced reference exactly: "
                            f"final_value={res['final_value']}, max_dd={res['max_dd']}")
        return 0

    if mode_arg == "grid":
        print(f"q_per_tier={q_per_tier}")
        print(f"uniform_equivalent_q={uniform_q:.6f} (expected_corrupted={expected_corrupted:.2f} "
              f"of {len(events)} events)")
        append_finding(f"Step 2 grid params: q_per_tier={q_per_tier}, "
                        f"uniform_equivalent_q={uniform_q}, expected_corrupted={expected_corrupted}")

        cell_defs = ["control", "observed_pattern", "small_micro_only",
                     "uniform_equivalent", "small_micro_q1", "small_micro_zero_info",
                     "observed_pattern_uniform_mode"]

        for cell_key in cell_defs:
            for seed in range(N_SEEDS):
                q_desc = {"cell": cell_key, "q_per_tier": q_per_tier, "uniform_q": uniform_q}
                ch = config_hash(commit, cell_key, seed, TIE_SEED_FIXED, q_desc)
                if ch in done:
                    continue

                n_corrupted = 0
                if cell_key == "control":
                    variant = events
                elif cell_key == "observed_pattern":
                    variant, n_corrupted = perturb_events_per_tier(
                        events, "adjacent", lambda t: q_per_tier[cap_tier(t)], seed)
                elif cell_key == "small_micro_only":
                    variant, n_corrupted = perturb_events_per_tier(
                        events, "adjacent",
                        lambda t: q_per_tier["small_micro"] if cap_tier(t) == "small_micro" else 0.0,
                        seed)
                elif cell_key == "uniform_equivalent":
                    variant, n_corrupted = perturb_events_per_tier(
                        events, "adjacent", lambda t: uniform_q, seed)
                elif cell_key == "small_micro_q1":
                    variant, n_corrupted = perturb_events_per_tier(
                        events, "adjacent",
                        lambda t: 1.0 if cap_tier(t) == "small_micro" else 0.0, seed)
                elif cell_key == "small_micro_zero_info":
                    variant, n_corrupted = force_hold(events, lambda t: cap_tier(t) == "small_micro")
                elif cell_key == "observed_pattern_uniform_mode":
                    variant, n_corrupted = perturb_events_per_tier(
                        events, "uniform", lambda t: q_per_tier[cap_tier(t)], seed)
                else:
                    raise ValueError(cell_key)

                res = run_cell(variant, prices, type_fn, driver_fn, tier_fn, tie_seed=TIE_SEED_FIXED)
                rec = {"cell_key": cell_key, "params": {"seed": seed, "tie_seed": TIE_SEED_FIXED},
                       "n_corrupted": n_corrupted, "config_hash": ch,
                       "driver_commit": commit, "results": res}
                append_cell(rec)
            print(f"  {cell_key} done ({time.time()-t0:.0f}s total)", flush=True)
        print(f"DONE in {time.time()-t0:.0f}s")
        return 0

    print("unknown arg")
    return 1


if __name__ == "__main__":
    sys.exit(main())
