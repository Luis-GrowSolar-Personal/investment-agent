#!/usr/bin/env python3
"""
corpus_fix6_threshold_recheck.py -- corpus-fix-6, Step D.

Re-runs analysis/corpus_construction_stepC_independent_v3.py's exact method
(same functions, imported verbatim -- not reimplemented) at the CORRECTED
count of gradable companies available for iteration (46, per
COVERAGE_GATE_SWEEP.json), alongside the previous 53 and the registered 54
for direct comparison. All three spread brackets, N_SYNTH_TRIALS=150 (the
module default -- unchanged).

Does NOT modify or overwrite STEP_C_INDEPENDENT_THRESHOLD.json (fix-4's
canonical output) -- writes a new file instead.
"""
import json, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import corpus_construction_stepC_independent_v3 as stepc

OUT = REPO / "analysis/data/corpus_v2/STEP_C_AT_CORRECTED_COUNT.json"
N_LIST = [46, 53, 54]


def main():
    stats = stepc.real_company_stats()
    mean_acc = stats["mean_accuracy"]
    observed_spread = stats["spread_stdev_observed"]
    call_counts = stats["per_company_call_count"]

    out = {
        "run_id": "corpus-construction",
        "pass": "corpus-fix-6, Step D -- threshold re-check at the corrected gradable-and-available count",
        "method": "Identical to corpus_construction_stepC_independent_v3.py (imported, not reimplemented): "
                  "each synthetic company draws its own accuracy from Normal(mean, spread) and its own "
                  "i.i.d. per-call outcomes; fed through scorecard_repair_driver.py's unchanged step3_paired "
                  "/ step3_unpaired at N_SYNTH_TRIALS=150.",
        "n_list_checked": N_LIST,
        "n_list_note": "46 = corrected gradable-and-available count under the A8 price-coverage gate "
                       "(53 previously counted minus HON/UPS [S1 bookkeeping defect, see wrap-up] minus "
                       "FRC/NOVA/WOLF [S4, no reserve to replace] minus GOOGL/SPWR [S5 carve-out, excluded "
                       "from the count per the prompt, not dropped]). 53 = the count used going into this "
                       "run. 54 = STEP_C_INDEPENDENT_THRESHOLD.json's registered bare-minimum n.",
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
