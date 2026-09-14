#!/usr/bin/env python3
"""
corpus_construction_stepC_independent_v3.py -- corpus-fix-4, Step C (THE DELIVERABLE).

Fixes corpus_construction_stepF_v2.py's flawed replication method. That
driver built "n companies" by copying the real 16-ticker population whole
(stock_multiplier times), so 64 synthetic blocks contained only 16 distinct
per-call outcome sequences -- badly understating true between-company
sampling variance. This driver instead:

  1. Estimates, from the REAL 16-ticker scored population
     (value_attribution_v2_stage_b_driver.build_populations()
     ['scorer_thin_filtered'], n=359 calls), each company's own accuracy and
     the MEAN and SPREAD (stdev, sample, ddof=1) of accuracy ACROSS the 16
     companies.
  2. Simulates n INDEPENDENT synthetic companies for a target n: each
     company's own accuracy is drawn from Normal(mean, spread) (clipped to
     [0.05, 0.95]), its call count is drawn (with replacement) from the real
     16 companies' call-count distribution, and its per-call hit/miss
     outcomes are drawn i.i.d. Bernoulli(that company's own drawn accuracy).
     No company is a literal copy of any other; every synthetic company has
     its own accuracy draw AND its own coin flips.
  3. Feeds the resulting synthetic population into
     scorecard_repair_driver.py's own step3_paired / step3_unpaired
     (unchanged, reused verbatim) at the driver's default N_SYNTH_TRIALS=150
     (not the 60 used by the flawed stepF_v2 run).

Three spread brackets (see PREREGISTRATION_FIX.json A6 sibling note in the
wrap-up for full assumption text):
  - observed: spread as measured across the real 16 (sample stdev).
  - lower:    0.5x observed. Assumption: today's 16 are 4 solar/4 battery/3
              semiconductor names that move together (sector-correlated
              accuracy), so their observed cross-company spread is inflated
              by that clustering; a corpus diversified across more/less
              correlated sub-domains should show less true between-company
              spread. 0.5x is a stated, not derived, illustrative halving.
  - higher:   1.5x observed. Assumption: a corpus that deliberately included
              MORE variable/idiosyncratic companies (e.g. more of the
              failures stratum, more small-caps) than today's would show
              higher between-company spread. 1.5x is a stated, not derived,
              illustrative 50% increase.

This is a projection over a simulated population, not a measurement of the
new (unscored) 78/77-company corpus. Flagged again in the wrap-up.
"""
import json, sys, statistics, random, time
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO))

from scorecard_repair_driver import step3_paired, step3_unpaired, X_SWEEP, BOOTSTRAP_SEED, DISAGREEMENT_DEFAULT, N_SYNTH_TRIALS
from value_attribution_v2_stage_b_driver import build_populations

OUT = REPO / "analysis/data/corpus_v2/STEP_C_INDEPENDENT_THRESHOLD.json"

N_LIST = [16, 30, 54, 78, 100, 120, 150, 200]
SEED = BOOTSTRAP_SEED
SPREAD_MULT = {"observed": 1.0, "lower": 0.5, "higher": 1.5}


def real_company_stats():
    pops = build_populations()
    base_pop = pops["scorer_thin_filtered"]
    by_t = defaultdict(list)
    for r in base_pop:
        by_t[r["ticker"]].append(r)
    accs, counts = {}, {}
    for t, recs in by_t.items():
        accs[t] = sum(1 for r in recs if r["hit"]) / len(recs)
        counts[t] = len(recs)
    mean_acc = statistics.mean(accs.values())
    spread = statistics.stdev(accs.values())  # sample stdev, ddof=1, n=16
    return {
        "n_real_companies": len(accs),
        "n_real_calls": len(base_pop),
        "mean_accuracy": mean_acc,
        "spread_stdev_observed": spread,
        "per_company_accuracy": accs,
        "per_company_call_count": counts,
    }


def build_independent_pop(n_companies, mean_acc, spread, call_counts, seed):
    rng = random.Random(seed)
    counts_pool = list(call_counts.values())
    pop = []
    for i in range(n_companies):
        acc = rng.gauss(mean_acc, spread)
        acc = min(0.95, max(0.05, acc))
        ncalls = rng.choice(counts_pool)
        ticker = f"SYN{i:04d}"
        for _ in range(ncalls):
            pop.append({"ticker": ticker, "hit": rng.random() < acc})
    return pop


def run_bracket(bracket, mean_acc, spread, call_counts):
    results = {}
    for n in N_LIST:
        t0 = time.time()
        synth_pop = build_independent_pop(n, mean_acc, spread, call_counts, seed=SEED + n)
        paired = step3_paired(synth_pop, X_SWEEP, N_SYNTH_TRIALS, None, SEED, DISAGREEMENT_DEFAULT)
        unpaired = step3_unpaired(synth_pop, X_SWEEP, N_SYNTH_TRIALS, None, SEED)
        dt = time.time() - t0
        results[n] = {
            "n_companies": n,
            "paired_mde_pp": paired["minimum_detectable_improvement_pp"],
            "unpaired_mde_pp": unpaired["minimum_detectable_improvement_pp"],
            "v6_accuracy_pct_in_synth_pop": paired["v6_accuracy_pct"],
            "wall_seconds": round(dt, 1),
        }
        # flush progress incrementally
        print(f"[{bracket}] n={n} paired_mde={results[n]['paired_mde_pp']} unpaired_mde={results[n]['unpaired_mde_pp']} ({dt:.1f}s)", flush=True)
        # write partial output every step so a killed run loses at most one cell
        _write_partial(bracket, results)
    return results


PARTIAL = {}


def _write_partial(bracket, results):
    PARTIAL[bracket] = results
    OUT.write_text(json.dumps({"partial": True, "brackets_done": PARTIAL}, indent=2))


def main():
    stats = real_company_stats()
    mean_acc = stats["mean_accuracy"]
    observed_spread = stats["spread_stdev_observed"]
    call_counts = stats["per_company_call_count"]

    out = {
        "run_id": "corpus-construction",
        "pass": "fix (corpus-fix-4), Step C -- honest threshold projection, independent blocks",
        "method": "Each synthetic company draws its OWN accuracy from Normal(mean, spread) "
                   "and its OWN i.i.d. Bernoulli(accuracy) per-call outcomes -- no company is a "
                   "literal copy of another. Mean/spread and call-count distribution estimated "
                   "from the real 16-ticker scored ALL16 population "
                   "(value_attribution_v2_stage_b_driver.build_populations()['scorer_thin_filtered'], "
                   "n=359 calls).",
        "seed": SEED,
        "n_trials": N_SYNTH_TRIALS,
        "disagreement_rate": DISAGREEMENT_DEFAULT,
        "real_population_stats": {
            "n_real_companies": stats["n_real_companies"],
            "n_real_calls": stats["n_real_calls"],
            "mean_accuracy_pct": round(mean_acc * 100, 1),
            "spread_stdev_pp_observed": round(observed_spread * 100, 1),
        },
        "spread_brackets": {},
        "n_list": N_LIST,
        "sqrt_estimates": {
            "published_baseline_24_over_sqrt_n": {n: round(24 / (n ** 0.5), 1) for n in N_LIST},
            "this_run_recheck_20_over_sqrt_n": {n: round(20 / (n ** 0.5), 1) for n in N_LIST},
        },
    }

    for bracket, mult in SPREAD_MULT.items():
        spread = observed_spread * mult
        out["spread_brackets"][bracket] = {
            "multiplier_on_observed": mult,
            "spread_stdev_pp": round(spread * 100, 1),
            "results_by_n": run_bracket(bracket, mean_acc, spread, call_counts),
        }

    OUT.write_text(json.dumps(out, indent=2))
    print("DONE")
    print(json.dumps({k: v for k, v in out.items() if k != "spread_brackets"}, indent=2))


if __name__ == "__main__":
    main()
