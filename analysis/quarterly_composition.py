#!/usr/bin/env python3
"""quarterly_composition.py — portfolio composition of the settled cell over time.

Re-runs the settled configuration recorded in ALLOCATOR_OPERATING_MODEL.md §0
(swap_funding, K=30, new_calls_only, X=2.5pp, pooled, per_event_date) and
snapshots holdings at each quarter end: distinct tickers held, per-ticker
percent of total portfolio value, cash percent, and concentration statistics.

Composition is PATH-DEPENDENT, so this runs every draw (seeds 0..N-1) rather
than one, and reports the median and the across-draw range for each statistic.
A single draw's composition is not a property of the configuration.

Reads only. No DB writes, no LLM calls, no cache refreshes.

Usage:
    python3 analysis/quarterly_composition.py [n_draws] [phase ...]
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "analysis"))

import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup

OUT = REPO / "analysis" / "data" / "quarterly_composition"
OUT.mkdir(parents=True, exist_ok=True)

# ALLOCATOR_OPERATING_MODEL.md §0 — settled configuration.
CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
WINDOW_END = date(2024, 6, 12)


def quarter_ends(start: date, end: date) -> list[date]:
    out = []
    for yr in range(start.year, end.year + 1):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            qe = date(yr, m, d)
            if start <= qe <= end:
                out.append(qe)
    if out and out[-1] != end:
        out.append(end)          # final partial quarter
    return out


def snapshot_at(snaps_by_date, dates_sorted, target):
    """Last daily snapshot on or before `target`."""
    lo, hi, best = 0, len(dates_sorted) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if dates_sorted[mid] <= target:
            best = dates_sorted[mid]; lo = mid + 1
        else:
            hi = mid - 1
    return snaps_by_date[best] if best is not None else None


def compose(r):
    """Quarter-end composition for one completed run."""
    snaps = r["daily_snapshots"]
    by_date = {s.date: s for s in snaps}
    dates_sorted = sorted(by_date)
    qes = quarter_ends(dates_sorted[0], min(dates_sorted[-1], WINDOW_END))
    rows = []
    for qe in qes:
        s = snapshot_at(by_date, dates_sorted, qe)
        if s is None:
            continue
        tv = s.total_value
        pv = {t: v for t, v in (s.position_values or {}).items() if v > 1e-6}
        weights = {t: 100.0 * v / tv for t, v in pv.items()} if tv else {}
        ordered = sorted(weights.values(), reverse=True)
        rows.append({
            "quarter_end": str(qe),
            "as_of": str(s.date),
            "total_value": tv,
            "cash_pct": 100.0 * s.cash_total / tv if tv else 0.0,
            "n_tickers": len(pv),
            "weights": weights,
            "max_weight": ordered[0] if ordered else 0.0,
            "top3_pct": sum(ordered[:3]),
            "top5_pct": sum(ordered[:5]),
            "hhi": sum(w * w for w in weights.values()),   # 0..10000, invested only
        })
    return rows


def main():
    n_draws = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    phases = [int(a) for a in sys.argv[2:]] or [0]

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout.strip())

    t0 = time.time()
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    print(f"corpus loaded: n_events={len(events)} in {time.time()-t0:.1f}s", flush=True)

    runs = []
    for ph in phases:
        for seed in range(n_draws):
            t1 = time.time()
            r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                         phase_offset=ph, seed=seed, **CELL)
            rows = compose(r)
            runs.append({"phase": ph, "seed": seed,
                         "final_value": r["final_value"], "max_dd": r["max_dd"],
                         "distinct_tickers_ever": r["distinct_tickers"],
                         "quarters": rows})
            (OUT / "runs.json").write_text(json.dumps(
                {"git_commit": commit, "git_dirty": dirty, "cell": CELL,
                 "n_draws": n_draws, "phases": phases, "runs": runs},
                indent=2, default=str))
            print(f"  phase={ph} seed={seed:2d} final={r['final_value']:12,.0f} "
                  f"dd={r['max_dd']*100:5.2f}% quarters={len(rows)} "
                  f"({time.time()-t1:.1f}s, {time.time()-t0:.0f}s total)", flush=True)

    print(f"\nDONE {len(runs)} runs in {time.time()-t0:.0f}s -> {OUT/'runs.json'}", flush=True)


if __name__ == "__main__":
    main()
