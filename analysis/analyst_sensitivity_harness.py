#!/usr/bin/env python3
"""analyst_sensitivity_harness.py — prompts/analyst-sensitivity.md

In-memory corruption harness for the analyst-quality sensitivity run
(Test 1, docs/handoffs/2026-09-03-state-of-play.md §7). Perturbs the
already-loaded structured score (CallEvent.per_call_rec / .final_action /
.thesis_health) after load, before the allocator sees it. No LLM calls,
no API spend, no DB writes -- the corpus is loaded once via
sweep_cadence_and_session_model.load_events_dedup_on() (same loader
quarterly_composition.py uses for the settled cell) and mutated only in
a deep-copied list of CallEvent objects per cell.

Settled configuration (ALLOCATOR_OPERATING_MODEL.md, unchanged):
    swap_funding, K=30, new_calls_only, X=2.5pp, pooled, per_event_date

Field consumption (verified by reading simulator/simulator.py and
sweep_cadence_and_session_model.py line 782/816-817):
    - decide_v3() reads `final_action` (= event.final_action or
      event.per_call_rec or "Hold") and `recommended_size_pct`
      (= event.recommended_size, untouched by this harness).
    - `thesis_health` is NOT read by decide() anywhere in the v2/v3
      allocator call. It is perturbed here anyway, in lockstep with
      recommendation, purely for score-object consistency -- and this
      file states plainly that doing so has zero effect on the
      simulation, so it must not be reported as a degradation channel.

Corruption modes, parameterised by q in [0,1], ordinal scale
Add(0) < Hold(1) < Trim(2) < Exit(3):
    uniform      -- w.p. q, replace with a uniform-random draw from the 4
    adjacent     -- w.p. q, move one step, direction random (clamped at
                    the ends: Add can only move to Hold, Exit only to Trim)
    optimistic   -- w.p. q, move one step toward Add (clamped at 0)
    pessimistic  -- w.p. q, move one step toward Exit (clamped at 3)

Two independent RNG streams, per the prompt's requirement:
    - corruption_seed: which calls get corrupted and to what (varies
      0..14, this axis's own variance)
    - tie_seed: the pre-existing same-day-event shuffle inside
      run_session_sweep_cell (held fixed at 0 for the grid, so the
      corruption axis is isolated from ordering variance)

Usage:
    cd analysis
    python3 analyst_sensitivity_harness.py control       # Step 2
    python3 analyst_sensitivity_harness.py grid           # Step 3
    python3 analyst_sensitivity_harness.py lift           # Step 4
"""
from __future__ import annotations

import copy
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
from analysis.simulator.data import PriceLookup

RUN_ID = "analyst-sensitivity"
RUN_STATE = REPO / "analysis" / "data" / "run_state" / RUN_ID
RUN_STATE.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_STATE / "cells.jsonl"

ORDER = ["Add", "Hold", "Trim", "Exit"]
HEALTH = ["Strengthening", "Intact", "Weakening", "Broken"]

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)

Q_VALUES = [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]
MODES = ["uniform", "adjacent", "optimistic", "pessimistic"]
N_DRAWS = 15
TIE_SEED_FIXED = 0

DD_CEILING = 0.3912  # 39.12% adopted ceiling, Rule 4


def _git_state():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    # Ignore the harmless Word lock file (~$*.docx) -- not our working-tree
    # change, never staged, never committed.
    meaningful = [l for l in status.splitlines() if l.strip() and "~$" not in l]
    dirty = bool(meaningful)
    return commit, dirty


def perturb_events(events, mode: str, q: float, corruption_seed: int):
    """The real corruption pass: single RNG stream, one draw per event,
    applied identically to per_call_rec, final_action, and thesis_health
    (moved in lockstep on the ordinal scale; NOT consumed by decide())."""
    rng = random.Random(corruption_seed * 1_000_003 + (hash(mode) % 97) + int(q * 10007))
    out = []
    for e in events:
        rec = e.per_call_rec or "Hold"
        health = e.thesis_health if e.thesis_health in HEALTH else "Intact"
        u = rng.random()
        if u < q:
            idx = ORDER.index(rec)
            hidx = HEALTH.index(health)
            if mode == "uniform":
                new_idx = rng.randrange(4)
                new_hidx = rng.randrange(4)
            else:
                if mode == "adjacent":
                    if idx == 0: d = 1
                    elif idx == 3: d = -1
                    else: d = rng.choice([-1, 1])
                elif mode == "optimistic":
                    d = -1 if idx > 0 else 0
                elif mode == "pessimistic":
                    d = 1 if idx < 3 else 0
                else:
                    raise ValueError(mode)
                new_idx = min(3, max(0, idx + d))
                new_hidx = min(3, max(0, hidx + d))
            new_rec = ORDER[new_idx]
            new_health = HEALTH[new_hidx]
        else:
            new_rec = rec
            new_health = health
        out.append(replace(e, per_call_rec=new_rec, final_action=new_rec, thesis_health=new_health))
    return out


def zero_information_events(events):
    return [replace(e, per_call_rec="Hold", final_action="Hold",
                     thesis_health="Intact", recommended_size=None)
            for e in events]


def run_cell(events_variant, prices, type_fn, driver_fn, tier_fn, tie_seed=TIE_SEED_FIXED):
    r = S.run_session_sweep_cell(events_variant, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=tie_seed, **CELL)
    return {
        "final_value": r["final_value"],
        "max_dd": r["max_dd"],
        "distinct_tickers": r["distinct_tickers"],
        "baseline_finals": r["baseline_finals"],
        "baseline_drawdowns": r["baseline_drawdowns"],
    }


def append_cell(record: dict):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def config_hash(commit, mode, q, corruption_seed, tie_seed, control=False):
    import hashlib
    payload = json.dumps({
        "driver_commit": commit, "mode": mode, "q": q,
        "corruption_seed": corruption_seed, "tie_seed": tie_seed,
        "control": control, "cell": CELL,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def already_done() -> set:
    done = set()
    if CELLS_PATH.exists():
        for line in CELLS_PATH.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                done.add(rec["config_hash"])
            except Exception:
                continue
    return done


def load_corpus():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    return events, type_fn, driver_fn, tier_fn, prices


def main():
    if len(sys.argv) < 2:
        print("usage: analyst_sensitivity_harness.py [control|grid]")
        return 1
    mode_arg = sys.argv[1]
    commit, dirty = _git_state()
    if dirty:
        print("FATAL: git tree dirty, refusing to run"); return 1

    t0 = time.time()
    events, type_fn, driver_fn, tier_fn, prices = load_corpus()
    print(f"corpus loaded: n_events={len(events)} in {time.time()-t0:.1f}s", flush=True)
    done = already_done()

    if mode_arg == "control":
        # Step 2: zero-information control, 15 tie-break draws (no
        # corruption seed axis -- the score is a constant, only ordering
        # can vary it).
        for tie_seed in range(N_DRAWS):
            ch = config_hash(commit, "zero_info", None, None, tie_seed, control=True)
            if ch in done:
                print(f"  [reuse] zero_info tie_seed={tie_seed}")
                continue
            zi_events = zero_information_events(events)
            res = run_cell(zi_events, prices, type_fn, driver_fn, tier_fn, tie_seed=tie_seed)
            rec = {"cell_key": "zero_info", "params": {"tie_seed": tie_seed},
                   "config_hash": ch, "driver_commit": commit, "results": res}
            append_cell(rec)
            print(f"  zero_info tie_seed={tie_seed} final={res['final_value']:,.0f} dd={res['max_dd']*100:.2f}%")

    elif mode_arg == "grid":
        # Step 3: full sensitivity grid, tie_seed fixed at 0, corruption
        # seed 0..14 is the run's own variance axis.
        for mode in MODES:
            for q in Q_VALUES:
                for corruption_seed in range(N_DRAWS):
                    ch = config_hash(commit, mode, q, corruption_seed, TIE_SEED_FIXED)
                    if ch in done:
                        continue
                    ev = perturb_events(events, mode, q, corruption_seed)
                    res = run_cell(ev, prices, type_fn, driver_fn, tier_fn, tie_seed=TIE_SEED_FIXED)
                    rec = {"cell_key": f"{mode}_q{q}", "params": {
                               "mode": mode, "q": q, "corruption_seed": corruption_seed,
                               "tie_seed": TIE_SEED_FIXED},
                           "config_hash": ch, "driver_commit": commit, "results": res}
                    append_cell(rec)
                print(f"  {mode} q={q} done ({time.time()-t0:.0f}s total)", flush=True)
    else:
        print("unknown arg"); return 1

    print(f"DONE in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
