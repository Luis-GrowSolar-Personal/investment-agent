#!/usr/bin/env python3
"""
corpus_construction_stepF_v2.py -- Fix-pass Step F of corpus-construction.

THE DELIVERABLE. Re-runs analysis/scorecard_repair_driver.py's Step 3
methodology (step3_unpaired / step3_paired, ticker-block bootstrap detection
simulation) at the NEW corpus's train+tune block count, using
CORPUS_MANIFEST_V2.json / SPLIT_V2.json.

**Simulated, not a real prompt difference.** No Anthropic API call is made
here and none of the 78 v2 companies has ever been scored (the corpus is
selected, not scored -- CLAUDE.md standing rule). This driver therefore
CANNOT measure real per-call hit/miss data for the new corpus. Instead it
reuses scorecard-repair's own trick (its own data_volume_answer function
scales the REAL ALL16 scored population -- 359 calls, 16 tickers -- onto
synthetic additional tickers to answer "what MDE would N tickers buy").
This script does the same thing, sized to the v2 corpus's actual
train+tune block counts rather than an arbitrary multiplier sweep. The
per-ticker call-count structure and v6 baseline accuracy are the REAL,
already-scored ALL16 population's; only the TICKER COUNT is synthetic
(replicated blocks), representing what MDE would look like IF the new
corpus's companies were scored at ALL16's own accuracy/call-volume
pattern. This is explicitly a projection, not a measurement of the new
corpus -- flagged again in the wrap-up.

Three scenarios, all "paired" (same calls, single ticker set, matches how a
real prompt-version comparison would run) and "unpaired" (independent
samples) MDE at the default 15% disagreement rate:
  1. realistic       -- train+tune companies, all strata (n=54)
  2. half_survival    -- half of train+tune survive a future availability
                          re-check (n=27)
  3. in_scope_only     -- train+tune restricted to strata explicitly inside
                          DOMAIN.md's Tier 1/2 universe (S2, S4, S5 --
                          S1 and S3 are explicitly NOT domain-restricted
                          per PREREGISTRATION.json's own S1/S3 rule text)
"""
import json, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO))

from scorecard_repair_driver import step3_paired, step3_unpaired, X_SWEEP, BOOTSTRAP_SEED, DISAGREEMENT_DEFAULT
from value_attribution_v2_stage_b_driver import build_populations

MANIFEST_V2 = REPO / "analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json"
SPLIT_V2 = REPO / "analysis/data/corpus_v2/SPLIT_V2.json"
OUT = REPO / "analysis/data/corpus_v2/STEP_F_DETECTION_THRESHOLD.json"

N_TRIALS = 60  # reduced from the driver's default 150 for this run's budget -- stated explicitly


def build_expanded_pop(base_pop, stock_multiplier):
    tickers = sorted({r["ticker"] for r in base_pop})
    from collections import defaultdict
    by_ticker = defaultdict(list)
    for r in base_pop:
        by_ticker[r["ticker"]].append(r)
    expanded = []
    for i in range(stock_multiplier):
        for t in tickers:
            synth_ticker = f"{t}__x{i}"
            for r in by_ticker[t]:
                expanded.append({**r, "ticker": synth_ticker})
    return expanded


def mde_at_n_tickers(base_pop, base_n_tickers, target_n_tickers, seed):
    # Nearest integer multiplier of the base 16-ticker ALL16 population that
    # reaches (>=) target_n_tickers, since the underlying call-pattern can only
    # be replicated in whole ticker-blocks.
    import math
    mult = max(1, math.ceil(target_n_tickers / base_n_tickers))
    expanded = build_expanded_pop(base_pop, mult)
    n_tickers_actual = base_n_tickers * mult
    paired = step3_paired(expanded, X_SWEEP, N_TRIALS, None, seed, DISAGREEMENT_DEFAULT)
    unpaired = step3_unpaired(expanded, X_SWEEP, N_TRIALS, None, seed)
    return {
        "target_n_tickers": target_n_tickers,
        "multiplier_applied": mult,
        "actual_n_tickers_in_simulation": n_tickers_actual,
        "paired_mde_pp": paired["minimum_detectable_improvement_pp"],
        "unpaired_mde_pp": unpaired["minimum_detectable_improvement_pp"],
        "v6_accuracy_pct": paired["v6_accuracy_pct"],
    }


def main():
    manifest = json.loads(MANIFEST_V2.read_text())
    split = json.loads(SPLIT_V2.read_text())

    train_tune = sorted(set(split["train"]) | set(split["tune"]))
    n_realistic = len(train_tune)

    n_half = round(n_realistic / 2)

    in_scope_strata = {"S2", "S4", "S5"}
    per_stratum = split["per_stratum"]
    in_scope_train_tune = set()
    for s in in_scope_strata:
        in_scope_train_tune |= set(per_stratum[s]["train"]) | set(per_stratum[s]["tune"])
    n_in_scope = len(in_scope_train_tune)

    pops = build_populations()
    scorer_pop = pops["scorer_thin_filtered"]
    base_n_tickers = len(sorted({r["ticker"] for r in scorer_pop}))

    scenarios = {
        "realistic_train_tune_all_strata": mde_at_n_tickers(scorer_pop, base_n_tickers, n_realistic, BOOTSTRAP_SEED),
        "fallback_half_survival": mde_at_n_tickers(scorer_pop, base_n_tickers, n_half, BOOTSTRAP_SEED),
        "fallback_in_scope_strata_only": mde_at_n_tickers(scorer_pop, base_n_tickers, n_in_scope, BOOTSTRAP_SEED),
    }

    out = {
        "run_id": "corpus-construction",
        "pass": "fix (second pass), Step F -- THE DELIVERABLE",
        "method": "Reuses scorecard_repair_driver.py's step3_paired/step3_unpaired ticker-block-bootstrap detection simulation, applied to the REAL scored ALL16 population (n=359 calls, 16 tickers, source: value_attribution_v2_stage_b_driver.build_populations()['scorer_thin_filtered']) replicated onto synthetic ticker blocks to match each scenario's target company count. SIMULATED, not a real prompt difference on the new corpus (which has never been scored -- corpus is selected, not scored).",
        "n_trials_per_x": N_TRIALS,
        "note_on_n_trials": "Reduced from scorecard-repair's own default of 150 to 60 for this session's time budget -- may inflate variance in the reported detection rates slightly; direction of the finding (whether MDE clears 3pp) is not expected to flip from this alone, but the exact pp value carries more Monte Carlo noise than a 150-trial run would.",
        "disagreement_rate": DISAGREEMENT_DEFAULT,
        "today_baseline_paired_mde_pp_at_16_tickers": None,  # filled below
        "scenarios": {
            "realistic": {"n_tickers": n_realistic, **scenarios["realistic_train_tune_all_strata"]},
            "fallback_half_survival": {"n_tickers": n_half, **scenarios["fallback_half_survival"]},
            "fallback_in_scope_strata_only": {"n_tickers": n_in_scope, **scenarios["fallback_in_scope_strata_only"]},
        },
    }
    # today's baseline at 16 tickers (multiplier 1), for the "against 6 points today" framing
    baseline = mde_at_n_tickers(scorer_pop, base_n_tickers, base_n_tickers, BOOTSTRAP_SEED)
    out["today_baseline_paired_mde_pp_at_16_tickers"] = baseline["paired_mde_pp"]

    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
