#!/usr/bin/env python3
"""run_autonomy_cadence_and_veto.py — prompts/autonomy-cadence-floor-and-veto.md

Step 1 (the cadence floor: K=1,3 plus K=7/30 re-run as anchors) and Step 2
(the §8 capitulation/veto sweep) against the bit-exact session model.

Resumable per CLAUDE.md: every completed cell is flushed to
analysis/data/run_state/autonomy-cadence-floor-and-veto/cells.jsonl and
skipped on a rerun whose config_hash matches. config_hash is sha256 over the
driver commit plus the full sorted parameter set.

In-memory only. No DB writes (reads the frozen v6 corpus from Postgres). No
LLM calls. No cache refreshes.

Usage:
    python3 analysis/run_autonomy_cadence_and_veto.py <step>
      step in {1scan, 1refine, 1analyze, 2, 2analyze}
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis"))

import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup

RUN_ID = "autonomy-cadence-floor-and-veto"
STATE = REPO / "analysis" / "data" / "run_state" / RUN_ID
CELLS = STATE / "cells.jsonl"

DRIVER_COMMIT = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout.strip()

# Limit axis extended DOWN to 0.1pp so cash_deployment's optimum stays
# bracketed at fast cadences (Rule 3b's boundary condition). `off` (None)
# belongs at the LOOSE end.
LIMITS = [0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, None]
REFINE_LIMITS = [1.0, 1.5, 2.0, 2.5, 3.0]
SCOPES = ["new_calls_only", "cash_deployment"]
K_STEP1 = [1, 3, 7, 30]
DRAWS_SCAN = 7
DRAWS_REFINE = 15

# Step 2 axes.
VETO_PS = [0.0, 0.10, 0.20, 0.30]
K_STEP2 = [1, 7, 30, 90]
DRAWS_VETO = 15

# Rule 4: adopted ceiling on MEDIAN max drawdown across draws (§10, corrected
# 2026-09-01). Robust requires the ceiling to hold on >= 2/3 of draws too.
DD_CEILING = 0.3912

# K=90's best cell is not in Step 1's grid; it comes from the prior grid.
# Provenance: wrap-ups/close-equivalence-corrected-targets-out.md Step 5
# ranking table, row 8 -- K=90 / cash_deployment / 3pp, $185,795
# phase-averaged median across 15 draws.
PRIOR_GRID_BEST = {90: ("cash_deployment", 3.0)}

# Anchor-check targets: the prior grid's PHASE-AVERAGED MEDIANS.
# Provenance: wrap-ups/close-equivalence-corrected-targets-out.md Step 5
# ranking table (15-draw refine band).
ANCHORS = {
    (7, "new_calls_only", 3.0): 189538.0,
    (30, "new_calls_only", 3.0): 189425.0,
    (30, "cash_deployment", 1.5): 194171.0,
    (30, "cash_deployment", 2.0): 192197.0,
}


def config_hash(params):
    return hashlib.sha256(
        (DRIVER_COMMIT + json.dumps(params, sort_keys=True, default=str)).encode()
    ).hexdigest()


def load_done():
    done = {}
    if CELLS.exists():
        for line in CELLS.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("config_hash"):
                done[rec["config_hash"]] = rec
    return done


def flush(cell_key, params, results):
    with open(CELLS, "a") as f:
        f.write(json.dumps({
            "cell_key": cell_key, "params": params,
            "config_hash": config_hash(params), "results": results,
        }, default=str) + "\n")


def summarize(r):
    """The reportable slice of one run, JSON-safe."""
    return {
        "final_value": r["final_value"], "max_dd": r["max_dd"],
        "n_displacements": r["n_displacements"], "add_total": r["add_total"],
        "fully_funded": r["fully_funded"], "partial": r["partial"],
        "unfunded": r["unfunded"], "total_shortfall": r["total_shortfall"],
        "distinct_tickers": r["distinct_tickers"],
        "below_1pct_days": r["below_1pct_days"], "pct_below_1pct": r["pct_below_1pct"],
        "n_days": r["n_days"], "n_sessions": r["n_sessions"],
        "mean_staleness": r["mean_staleness"],
        "max_session_pp_change": r["max_session_pp_change"],
        "realized_gains": r["realized_gains"],
        "n_pets": r["n_pets"], "n_capitulations": r["n_capitulations"],
        "n_declined": r["n_declined"], "declined_dollars": r["declined_dollars"],
        "capitulation_loss_from_peak": r["capitulation_loss_from_peak"],
        "capitulation_realized_gain": r["capitulation_realized_gain"],
        "capitulation_log": [{**c, "date": str(c["date"])} for c in r["capitulation_log"]],
        "pet_log": [{**p, "date": str(p["date"])} for p in r["pet_log"]],
        "add_proximity": r["add_proximity"],
        "n_skipped": len(r["skipped_events"]),
    }


def run(ctx, cell_key, done, **params):
    h = config_hash(params)
    if h in done:
        ctx["reused"] += 1
        return done[h]["results"]
    r = S.run_session_sweep_cell(ctx["events"], ctx["prices"], ctx["type_fn"],
                                 ctx["driver_fn"], ctx["tier_fn"], **params)
    res = summarize(r)
    flush(cell_key, params, res)
    done[h] = {"results": res}
    ctx["ran"] += 1
    return res


def draw_stats(values):
    med = statistics.median(values)
    return {"min": min(values), "median": med, "max": max(values),
            "spread_pct_of_median": (100 * (max(values) - min(values)) / med) if med else 0.0}


def make_ctx():
    t0 = time.time()
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    print(f"corpus loaded: n_events={len(events)} in {time.time()-t0:.1f}s", flush=True)
    return {"events": events, "prices": prices, "type_fn": type_fn,
            "driver_fn": driver_fn, "tier_fn": tier_fn, "ran": 0, "reused": 0, "t0": t0}


def phases_for(k):
    """3 phase offsets per K. For K=1 the phase is DEGENERATE -- every
    calendar day is a session date regardless of the offset -- so one phase
    is run and that is said explicitly."""
    if k == 1:
        return [0]
    return sorted({0, k // 3, (2 * k) // 3})


# ---------------------------------------------------------------------------
# Step 1 — the cadence floor
# ---------------------------------------------------------------------------

def step1(ctx, done, limits, draws, tag):
    out = {}
    for k in K_STEP1:
        for scope in SCOPES:
            for lim in limits:
                per_phase = []
                for ph in phases_for(k):
                    finals, dds, prox = [], [], []
                    for seed in range(draws):
                        p = dict(cadence=str(k), phase_offset=ph, scope=scope,
                                 funding_mode="swap_funding", limit_pp=lim,
                                 seed=seed, execution_order="pooled",
                                 trim_budget_scope="per_event_date")
                        res = run(ctx, f"step1-{tag}", done, **p)
                        finals.append(res["final_value"])
                        dds.append(res["max_dd"])
                        prox.append(res["add_proximity"])
                    per_phase.append({
                        "phase": ph, "final": draw_stats(finals), "dd": draw_stats(dds),
                        "dd_share_pass": sum(1 for d in dds if d <= DD_CEILING) / len(dds),
                        "proximity": prox[0],
                    })
                key = f"K{k}|{scope}|{'off' if lim is None else lim}"
                pav = statistics.mean([p["final"]["median"] for p in per_phase])
                pdd = statistics.mean([p["dd"]["median"] for p in per_phase])
                out[key] = {
                    "k": k, "scope": scope, "limit": lim,
                    "phase_avg_median_final": pav,
                    "phase_avg_median_dd": pdd,
                    "phase_spread_pct": (100 * (max(p["final"]["median"] for p in per_phase)
                                                - min(p["final"]["median"] for p in per_phase))
                                         / pav) if pav else 0.0,
                    "dd_share_pass": statistics.mean([p["dd_share_pass"] for p in per_phase]),
                    "rule4_pass": pdd <= DD_CEILING,
                    "draw_range_all_phases": [
                        min(p["final"]["min"] for p in per_phase),
                        max(p["final"]["max"] for p in per_phase)],
                    "n_sessions": None,
                    "per_phase": per_phase,
                }
                print(f"  {key:38s} {pav:12,.0f} dd={pdd*100:5.2f}% "
                      f"{'PASS' if pdd <= DD_CEILING else 'FAIL'} "
                      f"(ran {ctx['ran']} reuse {ctx['reused']} {time.time()-ctx['t0']:.0f}s)",
                      flush=True)
        (STATE / f"step1{tag}-results.json").write_text(json.dumps(out, indent=2, default=str))
    return out


# ---------------------------------------------------------------------------
# Step 2 — the veto sweep (§8)
# ---------------------------------------------------------------------------

def best_cell_for(k, step1_results):
    """Each cadence's own best RULE-4-VIABLE cell from Step 1; K=90 from the
    prior grid."""
    if k in PRIOR_GRID_BEST:
        return PRIOR_GRID_BEST[k]
    cands = [v for v in step1_results.values() if v["k"] == k and v["rule4_pass"]]
    if not cands:
        cands = [v for v in step1_results.values() if v["k"] == k]
    b = max(cands, key=lambda v: v["phase_avg_median_final"])
    return b["scope"], b["limit"]


def step2(ctx, done, step1_results, force_cell=None, tag="step2"):
    """force_cell=(scope, limit) overrides each cadence's best cell. Used for
    the supplementary LOOSE-limit sweep: at the best cells the per-session
    change limit keeps positions away from the 25% profit-take threshold, so
    §8's trigger almost never arms and the model is unmeasurable there. The
    loose sweep measures the same model in the regime it was written for."""
    out = {}
    for k in K_STEP2:
        scope, lim = force_cell if force_cell else best_cell_for(k, step1_results)
        ph = phases_for(k)[0]
        for p_veto in VETO_PS:
            finals, dds, pets, caps, cap_loss, declined = [], [], [], [], [], []
            for d in range(DRAWS_VETO):
                params = dict(cadence=str(k), phase_offset=ph, scope=scope,
                              funding_mode="swap_funding", limit_pp=lim,
                              seed=d, execution_order="pooled",
                              trim_budget_scope="per_event_date",
                              veto_p=p_veto, veto_seed=100000 + d)
                res = run(ctx, f"{tag}-veto", done, **params)
                finals.append(res["final_value"])
                dds.append(res["max_dd"])
                pets.append(res["n_pets"])
                caps.append(res["n_capitulations"])
                cap_loss.append(res["capitulation_realized_gain"])
                declined.append(res["n_declined"])
            key = f"K{k}|p{int(p_veto*100)}"
            out[key] = {
                "k": k, "scope": scope, "limit": lim, "phase": ph, "p": p_veto,
                "final": draw_stats(finals), "dd": draw_stats(dds),
                "dd_share_pass": sum(1 for x in dds if x <= DD_CEILING) / len(dds),
                "rule4_pass": statistics.median(dds) <= DD_CEILING,
                "pets_total": sum(pets), "pets_median": statistics.median(pets),
                "capitulations_total": sum(caps),
                "capitulations_median": statistics.median(caps),
                "capitulation_realized_gain_median": statistics.median(cap_loss),
                "declined_median": statistics.median(declined),
                "finals": finals, "dds": dds,
            }
            print(f"  {key:14s} {scope}/{lim}pp  med={statistics.median(finals):12,.0f} "
                  f"[{min(finals):,.0f}..{max(finals):,.0f}] dd={statistics.median(dds)*100:5.2f}% "
                  f"pets={sum(pets)} caps={sum(caps)} "
                  f"({ctx['ran']} ran, {time.time()-ctx['t0']:.0f}s)", flush=True)
        (STATE / f"{tag}-results.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def main():
    step = sys.argv[1]
    ctx = make_ctx()
    done = load_done()
    print(f"resume: {len(done)} cells already recorded at driver {DRIVER_COMMIT[:7]}", flush=True)
    if step == "1scan":
        step1(ctx, done, LIMITS, DRAWS_SCAN, "scan")
    elif step == "1refine":
        step1(ctx, done, REFINE_LIMITS, DRAWS_REFINE, "refine")
    elif step == "2":
        s1 = json.loads((STATE / "step1refine-results.json").read_text())
        step2(ctx, done, s1)
    elif step == "2loose":
        s1 = json.loads((STATE / "step1refine-results.json").read_text())
        step2(ctx, done, s1, force_cell=("cash_deployment", None), tag="step2loose")
    else:
        raise SystemExit(f"unknown step {step!r}")
    print(f"DONE step={step} ran={ctx['ran']} reused={ctx['reused']} "
          f"wall={time.time()-ctx['t0']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
