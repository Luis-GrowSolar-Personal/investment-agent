#!/usr/bin/env python3
"""run_corrected_targets_sweeps.py — prompts/close-equivalence-corrected-targets.md

Steps 4-6 driver: pooling re-derivation, the cadence grid, and the fold-in
sweeps, all against the now-bit-exact session model.

Resumable per CLAUDE.md: every completed cell is flushed to
analysis/data/run_state/close-equivalence-corrected-targets/cells.jsonl and
skipped on a rerun whose config_hash matches.

In-memory only. No DB writes (reads the frozen v6 corpus from Postgres). No
LLM calls. No cache refreshes.

Usage:
    python3 analysis/run_corrected_targets_sweeps.py <step>
      step in {4, 5scan, 5refine, 6a, 6b}
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

RUN_ID = "close-equivalence-corrected-targets"
STATE = REPO / "analysis" / "data" / "run_state" / RUN_ID
CELLS = STATE / "cells.jsonl"

DRIVER_COMMIT = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout.strip()

LIMITS = [None, 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]
POOLING_LIMITS = [None, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]
DRAWS_SCAN = 7
DRAWS_REFINE = 15


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


def _quantiles(vals):
    if not vals:
        return None
    v = sorted(vals)
    n = len(v)
    def q(p):
        return v[min(n - 1, int(p * n))]
    return {"n": n, "min": v[0], "p25": q(0.25), "median": statistics.median(v),
            "p75": q(0.75), "max": v[-1], "mean": statistics.mean(v)}


def summarize(r):
    """The reportable slice of one run, JSON-safe (drops portfolio/snapshots)."""
    return {
        "final_value": r["final_value"], "max_dd": r["max_dd"],
        "n_displacements": r["n_displacements"], "add_total": r["add_total"],
        "fully_funded": r["fully_funded"], "partial": r["partial"],
        "unfunded": r["unfunded"], "total_shortfall": r["total_shortfall"],
        "distinct_tickers": r["distinct_tickers"],
        "below_1pct_days": r["below_1pct_days"], "pct_below_1pct": r["pct_below_1pct"],
        "n_days": r["n_days"], "n_sessions": r["n_sessions"],
        "mean_staleness": r["mean_staleness"],
        "per_ticker_mean_staleness": r["per_ticker_mean_staleness"],
        "max_session_pp_change": r["max_session_pp_change"],
        "realized_gains": r["realized_gains"],
        # §5 donor size distribution: dollars raised per displacement.
        "donor_size_quantiles": _quantiles([d["raised"] for d in r["displacement_log"]]),
        "n_skipped": len(r["skipped_events"]),
        "skipped_events": [(str(d), t, why) for d, t, why in r["skipped_events"]],
    }


def run(ctx, cell_key, done, **params):
    h = config_hash(params)
    if h in done:
        ctx["reused"] += 1
        return done[h]["results"]
    kw = dict(params)
    r = S.run_session_sweep_cell(ctx["events"], ctx["prices"], ctx["type_fn"],
                                 ctx["driver_fn"], ctx["tier_fn"], **kw)
    res = summarize(r)
    flush(cell_key, params, res)
    done[config_hash(params)] = {"results": res}
    ctx["ran"] += 1
    return res


def draw_stats(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values),
            "spread_pct_of_median": (100 * (max(values) - min(values)) / statistics.median(values))
                                     if statistics.median(values) else 0.0}


def make_ctx():
    t0 = time.time()
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    print(f"corpus loaded: n_events={len(events)} in {time.time()-t0:.1f}s", flush=True)
    return {"events": events, "prices": prices, "type_fn": type_fn,
            "driver_fn": driver_fn, "tier_fn": tier_fn, "ran": 0, "reused": 0, "t0": t0}


# ---------------------------------------------------------------------------
# Step 4 — pooling re-derived: sequential vs pooled, per_call cadence
# ---------------------------------------------------------------------------

def step4(ctx, done):
    out = {}
    for order in ("sequential", "pooled"):
        for lim in POOLING_LIMITS:
            fvs, dds = [], []
            for seed in range(DRAWS_SCAN):
                key = f"step4/{order}/{lim}/seed{seed}"
                res = run(ctx, key, done, cadence="per_call", phase_offset=0,
                          scope="new_calls_only", funding_mode="swap_funding",
                          limit_pp=lim, seed=seed, execution_order=order)
                fvs.append(res["final_value"]); dds.append(res["max_dd"])
            out[f"{order}|{lim}"] = {"final": draw_stats(fvs), "dd": draw_stats(dds)}
            print(f"  step4 {order:10s} lim={str(lim):5s} "
                  f"median=${out[f'{order}|{lim}']['final']['median']:,.2f} "
                  f"dd={out[f'{order}|{lim}']['dd']['median']*100:.2f}%", flush=True)
    return out


# ---------------------------------------------------------------------------
# Step 5 — the cadence grid
# ---------------------------------------------------------------------------

CADENCES = [("k7", 7), ("k14", 14), ("k30", 30), ("k60", 60), ("k90", 90), ("seasonal", None)]


def phases_for(k):
    if k is None:
        return [0, 10, 20]
    return [0, k // 3, (2 * k) // 3]


def step5(ctx, done, limits, draws, tag):
    out = {}
    for cname, k in CADENCES:
        cadence = "seasonal" if k is None else str(k)
        for scope in ("new_calls_only", "cash_deployment"):
            for lim in limits:
                per_phase = []
                for ph in phases_for(k):
                    fvs, dds, stales = [], [], []
                    agg = None
                    for seed in range(draws):
                        key = f"step5/{cname}/{scope}/{lim}/ph{ph}/seed{seed}"
                        res = run(ctx, key, done, cadence=cadence, phase_offset=ph,
                                  scope=scope, funding_mode="swap_funding",
                                  limit_pp=lim, seed=seed, execution_order="pooled")
                        fvs.append(res["final_value"]); dds.append(res["max_dd"])
                        stales.append(res["mean_staleness"])
                        if seed == 0:
                            agg = {k2: res[k2] for k2 in
                                   ("below_1pct_days", "pct_below_1pct", "add_total",
                                    "fully_funded", "partial", "unfunded",
                                    "total_shortfall", "distinct_tickers",
                                    "n_displacements", "n_sessions",
                                    "per_ticker_mean_staleness")}
                    per_phase.append({"phase": ph, "final": draw_stats(fvs),
                                       "dd": draw_stats(dds),
                                       "mean_staleness": statistics.mean(stales),
                                       "forward_diag": agg})
                meds = [p["final"]["median"] for p in per_phase]
                dmeds = [p["dd"]["median"] for p in per_phase]
                out[f"{cname}|{scope}|{lim}"] = {
                    "per_phase": per_phase,
                    "phase_avg_final_median": statistics.mean(meds),
                    "phase_spread_pct": (100 * (max(meds) - min(meds)) / statistics.mean(meds))
                                         if statistics.mean(meds) else 0.0,
                    "phase_avg_dd_median": statistics.mean(dmeds),
                    "mean_staleness": statistics.mean(p["mean_staleness"] for p in per_phase),
                }
                o = out[f"{cname}|{scope}|{lim}"]
                print(f"  step5[{tag}] {cname:9s} {scope:16s} lim={str(lim):5s} "
                      f"phaseavg_median=${o['phase_avg_final_median']:,.2f} "
                      f"spread={o['phase_spread_pct']:.2f}% "
                      f"dd={o['phase_avg_dd_median']*100:.2f}% "
                      f"stale={o['mean_staleness']:.1f}d", flush=True)
    return out


# ---------------------------------------------------------------------------
# Step 6
# ---------------------------------------------------------------------------

def step6a(ctx, done, cadence, k, scope, lim):
    out = {}
    for mpp in (0.0, 0.25, 0.5, 1.0):
        fvs, dds, disp, rg, dt = [], [], [], [], []
        for ph in phases_for(k):
            for seed in range(DRAWS_SCAN):
                key = f"step6a/{cadence}/{scope}/{lim}/mpp{mpp}/ph{ph}/seed{seed}"
                res = run(ctx, key, done, cadence=cadence, phase_offset=ph, scope=scope,
                          funding_mode="swap_funding", limit_pp=lim, seed=seed,
                          execution_order="pooled", min_position_pct=mpp,
                          sub_floor_dollars=100.0)
                fvs.append(res["final_value"]); dds.append(res["max_dd"])
                disp.append(res["n_displacements"]); rg.append(res["realized_gains"])
                dt.append(res["distinct_tickers"])
        out[str(mpp)] = {"final": draw_stats(fvs), "dd": draw_stats(dds),
                          "median_displacements": statistics.median(disp),
                          "median_realized_gains": statistics.median(rg),
                          "median_distinct_tickers": statistics.median(dt)}
        print(f"  step6a minPositionPct={mpp}: median=${out[str(mpp)]['final']['median']:,.2f} "
              f"dd={out[str(mpp)]['dd']['median']*100:.2f}% "
              f"disp={out[str(mpp)]['median_displacements']}", flush=True)
    return out


def step6b(ctx, done, cadence, k, scope, lim):
    vals = {}
    ph = phases_for(k)[0]
    for label, kw in (("forward", {}), ("reversed", {"reverse_order": True}),
                       ("seed1", {"seed": 1}), ("seed2", {"seed": 2}), ("seed3", {"seed": 3})):
        key = f"step6b/{cadence}/{scope}/{lim}/{label}"
        res = run(ctx, key, done, cadence=cadence, phase_offset=ph, scope=scope,
                  funding_mode="swap_funding", limit_pp=lim, execution_order="pooled", **kw)
        vals[label] = res["final_value"]
        print(f"  step6b {label:9s} ${res['final_value']:,.2f}", flush=True)
    v = list(vals.values())
    spread = 100 * (max(v) - min(v)) / statistics.median(v)
    return {"values": vals, "spread_pct": spread}


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "4"
    done = load_done()
    print(f"driver_commit={DRIVER_COMMIT[:12]}  cells already recorded={len(done)}", flush=True)
    ctx = make_ctx()
    if step == "4":
        out = step4(ctx, done)
    elif step == "5scan":
        out = step5(ctx, done, LIMITS, DRAWS_SCAN, "scan")
    elif step == "5refine":
        out = step5(ctx, done, json.loads(sys.argv[2]), DRAWS_REFINE, "refine")
    elif step == "6a":
        cad, k, scope, lim = sys.argv[2], json.loads(sys.argv[3]), sys.argv[4], json.loads(sys.argv[5])
        out = step6a(ctx, done, cad, k, scope, lim)
    elif step == "6b":
        cad, k, scope, lim = sys.argv[2], json.loads(sys.argv[3]), sys.argv[4], json.loads(sys.argv[5])
        out = step6b(ctx, done, cad, k, scope, lim)
    else:
        raise SystemExit(f"unknown step {step!r}")
    outpath = STATE / f"step{step}-results.json"
    outpath.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nran={ctx['ran']} reused={ctx['reused']} "
          f"wall={time.time()-ctx['t0']:.1f}s -> {outpath}", flush=True)


if __name__ == "__main__":
    main()
