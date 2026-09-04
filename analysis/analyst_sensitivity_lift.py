#!/usr/bin/env python3
"""analyst_sensitivity_lift.py — Step 4 of prompts/analyst-sensitivity.md.

Converts the corruption axis (mode, q) into analyst-direct lift-pp, using
`analyst_direct_scorer.py`'s own scoring logic (imported, not modified).

Premise flagged in the wrap-up: analyst_direct_scorer.py's score_eval_dir()
expects a directory of *.txt eval-cache files with a ---STRUCTURED---
JSON block, not in-memory CallEvent objects, and the prompt anticipated
this ("If the scorer cannot be driven from perturbed in-memory scores
without modification, say so"). This driver does not modify that file --
it imports its PriceCache, direction_from_score(), FORWARD_DAYS, DEAD_BAND
and BENCHMARK constants directly and reapplies the identical scoring logic
(same direction mapping, same 2Q-forward benchmark-relative dead-band
ground truth) against the corrupted CallEvent list, so the methodology is
byte-for-byte the gate's, only the score's source differs (perturbed
in-memory events vs a versioned eval-cache directory).

Also flagged: this run's corpus is analysis/simulator/data.py's DB-loaded,
deduped ALL16 events (195 events, 2022-01-01..2024-06-12 window per the
settled cell), NOT the eval-cache directory the gate_ledger entry 1 scored
against. The two corpora are not guaranteed identical in size or window,
so the q=0.0 lift computed here is reported as this run's own reference
point, not asserted equal to the ledger's published 4.94pp/-2.5pp -- the
comparison is made explicitly in the wrap-up rather than assumed.

Usage: cd analysis && python3 analyst_sensitivity_lift.py
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup
from analyst_sensitivity_harness import perturb_events, MODES, Q_VALUES, N_DRAWS
from analyst_direct_scorer import (
    PriceCache, direction_from_score, PRICE_CACHE_PATH,
    FORWARD_DAYS, DEAD_BAND, BENCHMARK,
)

RUN_STATE = REPO / "analysis" / "data" / "run_state" / "analyst-sensitivity"
LIFT_OUT = RUN_STATE / "lift_grid.json"


def lift_for_events(events, prices: PriceCache) -> tuple[float, int]:
    """Same scoring logic as analyst_direct_scorer.score_eval_dir() /
    print_report(), applied directly to CallEvent objects instead of
    parsed eval-cache txt files. Returns (lift, n_scoreable)."""
    our_hits = 0
    base_hits = 0
    n = 0
    for e in events:
        score = {"recommendation": e.final_action or e.per_call_rec,
                  "thesisHealth": e.thesis_health}
        predicted = direction_from_score(score)
        if predicted is None:
            continue
        p0, _ = prices.price_on_or_after(e.ticker, e.call_date)
        b0, _ = prices.price_on_or_after(BENCHMARK, e.call_date)
        fwd_target = e.call_date + timedelta(days=FORWARD_DAYS)
        p1, _ = prices.price_on_or_after(e.ticker, fwd_target)
        b1, _ = prices.price_on_or_after(BENCHMARK, fwd_target)
        if not all([p0, b0, p1, b1]):
            continue
        stock_ret = (p1 - p0) / p0
        bench_ret = (b1 - b0) / b0
        rel = stock_ret - bench_ret
        if rel > DEAD_BAND:
            gt = "bullish"
        elif rel < -DEAD_BAND:
            gt = "bearish"
        else:
            gt = "neutral"
        hit = (predicted == gt)
        base_hit = (gt == "bullish")
        our_hits += int(hit)
        base_hits += int(base_hit)
        n += 1
    if n == 0:
        return 0.0, 0
    lift = (our_hits / n) - (base_hits / n)
    return lift, n


def main():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceCache(PRICE_CACHE_PATH)

    q0_lift, q0_n = lift_for_events(events, prices)
    print(f"q=0.0 (uncorrupted) analyst-direct lift: {q0_lift*100:+.2f}pp  (n={q0_n} scoreable)")

    out = {"q0_lift_pp": q0_lift * 100, "q0_n_scoreable": q0_n, "cells": {}}
    for mode in MODES:
        out["cells"][mode] = {}
        for q in Q_VALUES:
            lifts = []
            for corruption_seed in range(N_DRAWS):
                ev = perturb_events(events, mode, q, corruption_seed)
                lift, n = lift_for_events(ev, prices)
                lifts.append(lift * 100)
            lifts.sort()
            median = lifts[len(lifts)//2] if len(lifts) % 2 == 1 else (lifts[len(lifts)//2-1]+lifts[len(lifts)//2])/2
            out["cells"][mode][str(q)] = {
                "lift_pp_min": min(lifts), "lift_pp_median": median, "lift_pp_max": max(lifts),
            }
            print(f"  {mode:11s} q={q:.1f}  lift-pp min/med/max = {min(lifts):+6.2f} / {median:+6.2f} / {max(lifts):+6.2f}")

    LIFT_OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwritten -> {LIFT_OUT}")


if __name__ == "__main__":
    main()
