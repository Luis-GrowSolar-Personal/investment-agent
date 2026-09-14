#!/usr/bin/env python3
"""
corpus_fix7_threshold_recheck.py -- corpus-fix-7, Step D.

Re-runs the registered independent-block simulation (imported verbatim from
corpus_construction_stepC_independent_v3.py) at the corrected count (48
gradable-and-available companies, per this run's Step C), alongside the
square-root sanity check every prior run has reported beside it.

Does NOT modify or overwrite STEP_C_INDEPENDENT_THRESHOLD.json or
STEP_C_AT_CORRECTED_COUNT.json (fix-4's and fix-6's outputs) -- writes a
new file.
"""
import json, sys, math
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import corpus_construction_stepC_independent_v3 as stepc

OUT = REPO / "analysis/data/corpus_v2/STEP_C_AT_FIX7_CORRECTED_COUNT.json"
N_LIST = [48]


def main():
    stats = stepc.real_company_stats()
    mean_acc = stats["mean_accuracy"]
    observed_spread = stats["spread_stdev_observed"]
    call_counts = stats["per_company_call_count"]

    sqrt_published = 24 / math.sqrt(48)
    sqrt_recheck = 20 / math.sqrt(48)

    out = {
        "run_id": "corpus-construction",
        "pass": "corpus-fix-7, Step D -- threshold at the fully-corrected gradable-and-available count",
        "n": 48,
        "n_note": "48 = train+tune tickers from SPLIT_V3_RMO_REMOVED.json (53), minus HON/UPS "
                  "(B1 correction, never real S1 members), minus NOVA/WOLF (A9-corrected S4 gate "
                  "failures, unrecoverable price gaps, no reserve), minus SPWR (S5 carve-out, "
                  "excluded from the count per A8, stays in the corpus). SUNW and FRC, which failed "
                  "the flat-12 A8 gate, now PASS under A9's S4 floor of 4 and count toward this 48.",
        "sqrt_estimates": {
            "published_baseline_24_over_sqrt_n": round(sqrt_published, 2),
            "this_run_recheck_20_over_sqrt_n": round(sqrt_recheck, 2),
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
