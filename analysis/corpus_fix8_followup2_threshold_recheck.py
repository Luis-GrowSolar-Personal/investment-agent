#!/usr/bin/env python3
"""
corpus_fix8_threshold_recheck.py -- corpus-fix-8, Step E (threshold half).

Re-runs the registered independent-block simulation (imported verbatim from
corpus_construction_stepC_independent_v3.py) at the corpus-fix-8 corrected
count (107 gradable-and-available companies), alongside the square-root
check.
"""
import json, sys, math
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import corpus_construction_stepC_independent_v3 as stepc

OUT = REPO / "analysis/data/corpus_v2/STEP_C_AT_FIX8_FOLLOWUP2_COUNT.json"
N_LIST = [109]


def main():
    stats = stepc.real_company_stats()
    mean_acc = stats["mean_accuracy"]
    observed_spread = stats["spread_stdev_observed"]
    call_counts = stats["per_company_call_count"]

    out = {
        "run_id": "corpus-construction",
        "pass": "corpus-fix-8-followup2 -- threshold at the reserve-replacement-corrected count",
        "n": 109,
        "n_note": "109 = train+tune tickers in SPLIT_V7_RESERVE_REPLACEMENTS.json (111), minus WOLF and SPWR "
                  "(carve-out exclusions). 164 companies total (161 + BLK/WEC/SIRI, reserve replacements "
                  "for SCHW/ED/IPG), 161 gradable, 52 gradable in the 53-company holdout.",
        "sqrt_estimates": {
            "published_baseline_24_over_sqrt_n": round(24 / math.sqrt(109), 2),
            "this_run_recheck_20_over_sqrt_n": round(20 / math.sqrt(109), 2),
        },
        "real_population_stats": {
            "n_real_companies": stats["n_real_companies"],
            "n_real_calls": stats["n_real_calls"],
            "mean_accuracy": mean_acc,
            "spread_stdev_pp_observed": round(observed_spread * 100, 2),
        },
        "spread_brackets": {},
    }
    for bracket, mult in stepc.SPREAD_MULT.items():
        spread = observed_spread * mult
        results = {}
        for n in N_LIST:
            synth_pop = stepc.build_independent_pop(n, mean_acc, spread, call_counts, seed=stepc.SEED + n)
            paired = stepc.step3_paired(synth_pop, stepc.X_SWEEP, stepc.N_SYNTH_TRIALS, None, stepc.SEED, stepc.DISAGREEMENT_DEFAULT)
            unpaired = stepc.step3_unpaired(synth_pop, stepc.X_SWEEP, stepc.N_SYNTH_TRIALS, None, stepc.SEED)
            results[str(n)] = {
                "paired_mde_pp": paired["minimum_detectable_improvement_pp"],
                "unpaired_mde_pp": unpaired["minimum_detectable_improvement_pp"],
            }
            print(f"[{bracket}] n={n} paired={results[str(n)]['paired_mde_pp']} unpaired={results[str(n)]['unpaired_mde_pp']}", flush=True)
        out["spread_brackets"][bracket] = {"spread_pp": round(spread * 100, 2), "results_by_n": results}
        OUT.write_text(json.dumps(out, indent=2))

    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
