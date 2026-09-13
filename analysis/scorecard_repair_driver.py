#!/usr/bin/env python3
"""scorecard_repair_driver.py -- run_id scorecard-repair
(prompts/scorecard-repair.md).

ZERO Anthropic API calls. Zero DB writes -- one read-only SELECT, the same
path value_attribution_v2_stage_b_driver.py already uses. No price-cache
refresh. Scope boundary: report, do not decide -- does not adjudicate any
prompt version.

Steps implemented: 0c (arithmetic check), 1 (luck-corrected score), 2
(confidence intervals), 3 (detection-threshold simulation, both populations).

    cd analysis
    python3 scorecard_repair_driver.py
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

RUN_ID = "scorecard-repair"
RUN_DIR = REPO / "analysis" / "data" / "run_state" / RUN_ID
CELLS_PATH = RUN_DIR / "cells.jsonl"
FINDINGS_PATH = RUN_DIR / "findings.md"
OUT_DIR = REPO / "analysis" / "data" / "scorecard_repair"
DRIVER_FILE = "analysis/scorecard_repair_driver.py"

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260913
X_SWEEP = list(range(1, 16))
N_SYNTH_TRIALS = 150
INNER_RESAMPLES = 60
DISAGREEMENT_DEFAULT = 0.15
DISAGREEMENT_SWEEP = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
DATA_VOLUME_TARGET_PP = 3

print("=" * 72)
print("ASSERTION: zero Anthropic API calls / LLM calls in this driver.")
print("All figures are arithmetic over already-stored Analysis rows (DB")
print("SELECT, read-only, reused from Stage B's build_populations()) and a")
print("Monte-Carlo simulation over those stored per-call outcomes. No")
print("re-scoring, no evaluator invocation, no API spend.")
print("=" * 72)


def sha256_file(p):
    p = Path(p)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_info():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO).decode().strip()
    dirty_out = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"], cwd=REPO).decode()
    dirty_lines = [ln for ln in dirty_out.splitlines() if ln.strip()]
    dirty = bool(dirty_lines)
    ls = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO).decode()
    driver_tracked = DRIVER_FILE in ls
    return commit, branch, dirty, driver_tracked, dirty_lines


def config_hash(driver_commit, params):
    blob = driver_commit + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def write_cell(cell_key, params, chash, results):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps({"cell_key": cell_key, "params": params,
                             "config_hash": chash, "results": results}, default=str) + "\n")


def append_finding(text):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with FINDINGS_PATH.open("a") as f:
        f.write(f"\n## Finding -- {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n{text}\n")


# ---------------------------------------------------------------------------
# Step 0c -- recompute the prompt's own worked example
# ---------------------------------------------------------------------------

def step0c(scorer_pop):
    """Recompute predicted/outcome distribution and expected-by-luck from
    the stored corpus, and compare to the prompt's Sec 5 claim (251/44/64
    predicted, 166/151/42 outcome, expected-by-luck 39.6%, observed 40.4%)."""
    n = len(scorer_pop)
    pred_counts = Counter(r["predicted"] for r in scorer_pop)
    gt_counts = Counter(r["ground_truth"] for r in scorer_pop)
    hits = sum(1 for r in scorer_pop if r["hit"])
    observed_pct = round(hits / n * 100, 1)

    expected_by_luck = 0.0
    per_class = {}
    for cls in ("bullish", "bearish", "neutral"):
        p_pred = pred_counts.get(cls, 0) / n
        p_gt = gt_counts.get(cls, 0) / n
        contrib = p_pred * p_gt
        expected_by_luck += contrib
        per_class[cls] = {"p_pred": round(p_pred, 4), "p_gt": round(p_gt, 4),
                           "contribution": round(contrib, 4)}
    expected_by_luck_pct = round(expected_by_luck * 100, 1)

    claimed = {
        "pred_bullish": 251, "pred_bearish": 44, "pred_neutral": 64,
        "gt_bullish": 166, "gt_bearish": 151, "gt_neutral": 42,
        "expected_by_luck_pct": 39.6, "observed_pct": 40.4,
    }
    measured = {
        "pred_bullish": pred_counts.get("bullish", 0),
        "pred_bearish": pred_counts.get("bearish", 0),
        "pred_neutral": pred_counts.get("neutral", 0),
        "gt_bullish": gt_counts.get("bullish", 0),
        "gt_bearish": gt_counts.get("bearish", 0),
        "gt_neutral": gt_counts.get("neutral", 0),
        "expected_by_luck_pct": expected_by_luck_pct,
        "observed_pct": observed_pct,
    }
    contradiction = any(claimed[k] != measured[k] for k in
                         ("pred_bullish", "pred_bearish", "pred_neutral",
                          "gt_bullish", "gt_bearish", "gt_neutral")) or \
        abs(claimed["expected_by_luck_pct"] - measured["expected_by_luck_pct"]) > 0.15 or \
        abs(claimed["observed_pct"] - measured["observed_pct"]) > 0.15

    results = {
        "n": n,
        "claimed_by_prompt_sec5": claimed,
        "measured_from_corpus": measured,
        "per_class_luck_contribution": per_class,
        "contradiction": contradiction,
    }
    return results


# ---------------------------------------------------------------------------
# Step 1 -- luck-corrected score
# ---------------------------------------------------------------------------

def step1_luck_corrected(pop, label):
    n = len(pop)
    pred_counts = Counter(r["predicted"] for r in pop)
    gt_counts = Counter(r["ground_truth"] for r in pop)
    hits = sum(1 for r in pop if r["hit"])
    observed = hits / n

    expected_by_luck = sum(
        (pred_counts.get(cls, 0) / n) * (gt_counts.get(cls, 0) / n)
        for cls in ("bullish", "bearish", "neutral")
    )

    gap_pp = round((observed - expected_by_luck) * 100, 2)
    kappa = (observed - expected_by_luck) / (1 - expected_by_luck) if expected_by_luck < 1 else None

    per_class_recall = {}
    for cls in ("bullish", "bearish", "neutral"):
        actual_subset = [r for r in pop if r["ground_truth"] == cls]
        if actual_subset:
            rc = sum(1 for r in actual_subset if r["predicted"] == cls) / len(actual_subset)
        else:
            rc = None
        per_class_recall[cls] = {
            "n_actual": len(actual_subset),
            "recall_pct": round(rc * 100, 1) if rc is not None else None,
        }
    balanced_accuracy = sum(
        v["recall_pct"] for v in per_class_recall.values() if v["recall_pct"] is not None
    ) / sum(1 for v in per_class_recall.values() if v["recall_pct"] is not None)

    always_bullish_base = gt_counts.get("bullish", 0) / n
    always_flat_base = gt_counts.get("neutral", 0) / n

    return {
        "population": label,
        "n": n,
        "observed_accuracy_pct": round(observed * 100, 1),
        "expected_by_luck_pct": round(expected_by_luck * 100, 1),
        "luck_corrected_gap_pp": gap_pp,
        "cohens_kappa_0to1": round(kappa, 4) if kappa is not None else None,
        "balanced_accuracy_pct": round(balanced_accuracy, 1),
        "per_class_recall": per_class_recall,
        "always_bullish_guesser_baseline_pct": round(always_bullish_base * 100, 1),
        "always_bullish_guesser_lift_pp": round((observed - always_bullish_base) * 100, 1),
        "always_flat_guesser_baseline_pct": round(always_flat_base * 100, 1),
        "always_flat_guesser_lift_pp": round((observed - always_flat_base) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Step 2 -- ticker-block bootstrap CIs on the new metrics
# ---------------------------------------------------------------------------

def ticker_block_bootstrap_new_metrics(pop, n_resamples, seed):
    rng = random.Random(seed)
    tickers = sorted({r["ticker"] for r in pop})
    by_ticker = defaultdict(list)
    for r in pop:
        by_ticker[r["ticker"]].append(r)

    metrics = {"luck_corrected_gap_pp": [], "balanced_accuracy_pct": [],
               "observed_accuracy_pct": [], "recall_bullish_pct": [],
               "recall_bearish_pct": [], "recall_neutral_pct": []}

    for _ in range(n_resamples):
        sample_tickers = [rng.choice(tickers) for _ in tickers]
        sample = []
        for t in sample_tickers:
            sample.extend(by_ticker[t])
        n = len(sample)
        if n == 0:
            continue
        pred_counts = Counter(r["predicted"] for r in sample)
        gt_counts = Counter(r["ground_truth"] for r in sample)
        hits = sum(1 for r in sample if r["hit"])
        observed = hits / n
        expected_by_luck = sum(
            (pred_counts.get(cls, 0) / n) * (gt_counts.get(cls, 0) / n)
            for cls in ("bullish", "bearish", "neutral")
        )
        metrics["observed_accuracy_pct"].append(observed * 100)
        metrics["luck_corrected_gap_pp"].append((observed - expected_by_luck) * 100)

        recalls = []
        for cls, key in (("bullish", "recall_bullish_pct"), ("bearish", "recall_bearish_pct"),
                          ("neutral", "recall_neutral_pct")):
            actual_subset = [r for r in sample if r["ground_truth"] == cls]
            if actual_subset:
                rc = sum(1 for r in actual_subset if r["predicted"] == cls) / len(actual_subset) * 100
                metrics[key].append(rc)
                recalls.append(rc)
        if recalls:
            metrics["balanced_accuracy_pct"].append(sum(recalls) / len(recalls))

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        idx = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
        return round(s[idx], 2)

    out = {}
    for k, vals in metrics.items():
        lo, hi = pct(vals, 2.5), pct(vals, 97.5)
        out[k] = {
            "n_resamples_with_data": len(vals),
            "ci95_lo": lo,
            "ci95_hi": hi,
            "median": pct(vals, 50),
            "spans_zero": (lo is not None and hi is not None and lo <= 0 <= hi) if "gap" in k else None,
        }
    return out, len(tickers)


# ---------------------------------------------------------------------------
# Step 3 -- detection threshold simulation
# ---------------------------------------------------------------------------

def resample_hit_rate(pop_bool_list, tickers_by_pos, rng, tickers):
    """One ticker-block resample; returns the resampled mean of pop_bool_list."""
    sample_tickers = [rng.choice(tickers) for _ in tickers]
    vals = []
    for t in sample_tickers:
        vals.extend(tickers_by_pos[t])
    if not vals:
        return None
    return sum(vals) / len(vals)


def step3_unpaired(pop, x_sweep, n_trials, n_resamples, seed):
    """3a. Two independent samples. For each X, synthesize a challenger with
    accuracy = v6_accuracy + X (per trial, a coin over the SAME ticker
    labels but independently redrawn hit/miss), then for each trial do a
    ticker-block bootstrap comparison and check whether the resampled
    difference's 95% interval excludes zero."""
    tickers = sorted({r["ticker"] for r in pop})
    by_ticker = defaultdict(list)
    for r in pop:
        by_ticker[r["ticker"]].append(r)
    n = len(pop)
    v6_acc = sum(1 for r in pop if r["hit"]) / n

    results = {}
    for x in x_sweep:
        challenger_acc = min(0.999, v6_acc + x / 100.0)
        detections = 0
        for trial in range(n_trials):
            rng = random.Random(seed + trial * 97 + x)
            # synthesize challenger hit/miss per call at same ticker labels
            v6_hits_by_ticker = {t: [1 if r["hit"] else 0 for r in by_ticker[t]] for t in tickers}
            chal_hits_by_ticker = {
                t: [1 if rng.random() < challenger_acc else 0 for _ in by_ticker[t]]
                for t in tickers
            }
            # inner ticker-block bootstrap for this trial's paired resample of the difference
            diffs = []
            inner_n = INNER_RESAMPLES
            for _ in range(inner_n):
                samp_tickers_v6 = [rng.choice(tickers) for _ in tickers]
                samp_tickers_c = [rng.choice(tickers) for _ in tickers]
                v6_vals = [v for t in samp_tickers_v6 for v in v6_hits_by_ticker[t]]
                c_vals = [v for t in samp_tickers_c for v in chal_hits_by_ticker[t]]
                if not v6_vals or not c_vals:
                    continue
                diffs.append(sum(c_vals) / len(c_vals) - sum(v6_vals) / len(v6_vals))
            if not diffs:
                continue
            diffs.sort()
            lo = diffs[max(0, round(0.025 * (len(diffs) - 1)))]
            hi = diffs[max(0, round(0.975 * (len(diffs) - 1)))]
            if lo > 0 or hi < 0:
                detections += 1
        results[x] = round(detections / n_trials, 3)
    mde = next((x for x in x_sweep if results[x] >= 0.80), None)
    return {"detection_rate_by_x": results, "minimum_detectable_improvement_pp": mde,
            "v6_accuracy_pct": round(v6_acc * 100, 1)}


def step3_paired(pop, x_sweep, n_trials, n_resamples, seed, disagreement_rate):
    """3b. Same calls. Model challenger as agreeing with v6 on
    (1 - disagreement_rate) of calls and, on the remainder, assigning
    right/wrong so net accuracy = v6 + X. Ticker-block bootstrap on the
    PAIRED per-call difference (challenger_hit - v6_hit)."""
    tickers = sorted({r["ticker"] for r in pop})
    by_ticker = defaultdict(list)
    for r in pop:
        by_ticker[r["ticker"]].append(r)
    n = len(pop)
    v6_hits = [1 if r["hit"] else 0 for r in pop]
    v6_acc = sum(v6_hits) / n

    results = {}
    for x in x_sweep:
        detections = 0
        for trial in range(n_trials):
            rng = random.Random(seed + trial * 131 + x)
            # build challenger per-call outcome: disagree on disagreement_rate share of
            # calls; among disagreements, set challenger right more often so net gain = X pp
            chal_by_ticker = {}
            v6_by_ticker = {}
            for t in tickers:
                recs = by_ticker[t]
                chal_vals = []
                v6_vals = []
                for r in recs:
                    v6h = 1 if r["hit"] else 0
                    v6_vals.append(v6h)
                    if rng.random() < disagreement_rate:
                        # flip: on a disagreement, challenger is right with probability
                        # tuned so the net accuracy gain across the population is ~X pp
                        p_right_on_disagreement = min(1.0, max(0.0, 0.5 + (x / 100.0) / max(disagreement_rate, 1e-6) / 2))
                        chal_vals.append(1 if rng.random() < p_right_on_disagreement else 0)
                    else:
                        chal_vals.append(v6h)
                chal_by_ticker[t] = chal_vals
                v6_by_ticker[t] = v6_vals

            diffs = []
            inner_n = INNER_RESAMPLES
            for _ in range(inner_n):
                samp_tickers = [rng.choice(tickers) for _ in tickers]
                v6_vals = [v for t in samp_tickers for v in v6_by_ticker[t]]
                c_vals = [v for t in samp_tickers for v in chal_by_ticker[t]]
                pairs = list(zip(v6_vals, c_vals))
                if not pairs:
                    continue
                d = sum(c - v for v, c in pairs) / len(pairs)
                diffs.append(d)
            if not diffs:
                continue
            diffs.sort()
            lo = diffs[max(0, round(0.025 * (len(diffs) - 1)))]
            hi = diffs[max(0, round(0.975 * (len(diffs) - 1)))]
            if lo > 0 or hi < 0:
                detections += 1
        results[x] = round(detections / n_trials, 3)
    mde = next((x for x in x_sweep if results[x] >= 0.80), None)
    return {"detection_rate_by_x": results, "minimum_detectable_improvement_pp": mde,
            "v6_accuracy_pct": round(v6_acc * 100, 1), "disagreement_rate": disagreement_rate}


def data_volume_answer(pop, target_pp, seed, disagreement_rate):
    """How many additional stocks, or additional calls, bring the paired MDE
    to target_pp? Sweep multipliers on (a) ticker count (replicate each
    ticker's call pattern onto synthetic new tickers) and (b) per-ticker call
    count (replicate each ticker's calls), holding the other fixed, and find
    the smallest multiplier whose paired MDE <= target_pp."""
    tickers = sorted({r["ticker"] for r in pop})
    by_ticker = defaultdict(list)
    for r in pop:
        by_ticker[r["ticker"]].append(r)

    def build_expanded_pop(stock_multiplier, call_multiplier):
        expanded = []
        for i in range(stock_multiplier):
            for t in tickers:
                synth_ticker = f"{t}__x{i}"
                base_recs = by_ticker[t] * call_multiplier
                for r in base_recs:
                    expanded.append({**r, "ticker": synth_ticker})
        return expanded

    def paired_mde_for(stock_multiplier, call_multiplier):
        expanded = build_expanded_pop(stock_multiplier, call_multiplier)
        res = step3_paired(expanded, X_SWEEP, n_trials=60, n_resamples=None,
                            seed=seed, disagreement_rate=disagreement_rate)
        return res["minimum_detectable_improvement_pp"]

    stock_answer = None
    for mult in [1, 2, 4, 8, 16]:
        mde = paired_mde_for(mult, 1)
        if mde is not None and mde <= target_pp:
            stock_answer = {"stock_multiplier": mult, "n_tickers": len(tickers) * mult,
                             "mde_at_multiplier": mde}
            break
    call_answer = None
    for mult in [1, 2, 4, 8, 16]:
        mde = paired_mde_for(1, mult)
        if mde is not None and mde <= target_pp:
            call_answer = {"call_multiplier": mult, "n_calls_per_ticker_scaled": mult,
                            "mde_at_multiplier": mde}
            break
    return {
        "target_pp": target_pp,
        "stock_axis": stock_answer or {"note": f"not reached by multiplier<=16"},
        "call_axis": call_answer or {"note": f"not reached by multiplier<=16"},
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    commit, branch, dirty, driver_tracked, dirty_lines = git_info()
    print(f"git_commit={commit} branch={branch} dirty={dirty} driver_tracked={driver_tracked}")
    if dirty:
        print("DIRTY LINES (hard stop -- run must be on a clean tree):")
        for ln in dirty_lines:
            print(" ", ln)
        sys.exit(1)

    from value_attribution_v2_stage_b_driver import build_populations
    pops = build_populations()
    scorer_pop = pops["scorer_thin_filtered"]   # n=359
    sim_pop = pops["sim_population"]            # n=195

    # --- Step 0c ---
    s0c = step0c(scorer_pop)
    chash = config_hash(commit, {"step": "0c"})
    write_cell("0c", {}, chash, s0c)
    if s0c["contradiction"]:
        append_finding(
            f"**Step 0c CONTRADICTION.** Prompt's Sec5 claimed figures do not match "
            f"the recomputed corpus. Claimed={s0c['claimed_by_prompt_sec5']}, "
            f"measured={s0c['measured_from_corpus']}. Carrying corrected figures "
            f"forward through the rest of this run."
        )
    else:
        append_finding(
            f"**Step 0c CONFIRMED.** Prompt's Sec5 worked example "
            f"(pred 251/44/64, outcome 166/151/42, expected-by-luck "
            f"{s0c['measured_from_corpus']['expected_by_luck_pct']}%, observed "
            f"{s0c['measured_from_corpus']['observed_pct']}%) reproduces exactly "
            f"from the stored corpus. No contradiction to carry forward."
        )

    # --- Step 1 ---
    s1_scorer = step1_luck_corrected(scorer_pop, "scorer_n359")
    s1_sim = step1_luck_corrected(sim_pop, "simulator_n195")
    chash = config_hash(commit, {"step": "1"})
    write_cell("1", {}, chash, {"scorer": s1_scorer, "simulator": s1_sim})
    append_finding(
        f"**Step 1 luck-corrected score.** Scorer pop (n=359): observed "
        f"{s1_scorer['observed_accuracy_pct']}%, expected-by-luck "
        f"{s1_scorer['expected_by_luck_pct']}%, gap {s1_scorer['luck_corrected_gap_pp']}pp, "
        f"kappa {s1_scorer['cohens_kappa_0to1']}, balanced accuracy "
        f"{s1_scorer['balanced_accuracy_pct']}%. Simulator pop (n=195): gap "
        f"{s1_sim['luck_corrected_gap_pp']}pp, balanced accuracy "
        f"{s1_sim['balanced_accuracy_pct']}%."
    )

    # --- Step 2 ---
    boot_scorer, n_blocks_scorer = ticker_block_bootstrap_new_metrics(scorer_pop, BOOTSTRAP_N, BOOTSTRAP_SEED)
    boot_sim, n_blocks_sim = ticker_block_bootstrap_new_metrics(sim_pop, BOOTSTRAP_N, BOOTSTRAP_SEED)
    chash = config_hash(commit, {"step": "2", "bootstrap_n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED})
    write_cell("2", {"bootstrap_n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED}, chash,
               {"scorer": boot_scorer, "n_blocks_scorer": n_blocks_scorer,
                "simulator": boot_sim, "n_blocks_sim": n_blocks_sim})
    any_span_zero = any(
        v.get("spans_zero") for v in list(boot_scorer.values()) + list(boot_sim.values())
        if v.get("spans_zero") is not None
    )
    append_finding(
        f"**Step 2 intervals.** ({BOOTSTRAP_N} resamples, seed {BOOTSTRAP_SEED}, "
        f"{n_blocks_scorer} independent ticker blocks scorer pop / {n_blocks_sim} "
        f"simulator pop). Scorer luck-corrected-gap 95% CI "
        f"[{boot_scorer['luck_corrected_gap_pp']['ci95_lo']}, "
        f"{boot_scorer['luck_corrected_gap_pp']['ci95_hi']}]pp "
        f"(spans zero: {boot_scorer['luck_corrected_gap_pp']['spans_zero']}). "
        f"Simulator luck-corrected-gap 95% CI "
        f"[{boot_sim['luck_corrected_gap_pp']['ci95_lo']}, "
        f"{boot_sim['luck_corrected_gap_pp']['ci95_hi']}]pp "
        f"(spans zero: {boot_sim['luck_corrected_gap_pp']['spans_zero']}). "
        f"ANY interval spans zero: {any_span_zero}."
    )

    # --- Step 3 ---
    unpaired_scorer = step3_unpaired(scorer_pop, X_SWEEP, N_SYNTH_TRIALS, None, BOOTSTRAP_SEED)
    paired_scorer = step3_paired(scorer_pop, X_SWEEP, N_SYNTH_TRIALS, None, BOOTSTRAP_SEED, DISAGREEMENT_DEFAULT)
    paired_scorer_sweep = {
        d: step3_paired(scorer_pop, X_SWEEP, 60, None, BOOTSTRAP_SEED, d)["minimum_detectable_improvement_pp"]
        for d in DISAGREEMENT_SWEEP
    }
    dv = data_volume_answer(scorer_pop, DATA_VOLUME_TARGET_PP, BOOTSTRAP_SEED, DISAGREEMENT_DEFAULT)

    pairing_helps_as_expected = (
        paired_scorer["minimum_detectable_improvement_pp"] is not None and
        unpaired_scorer["minimum_detectable_improvement_pp"] is not None and
        paired_scorer["minimum_detectable_improvement_pp"] < unpaired_scorer["minimum_detectable_improvement_pp"]
    )

    s3 = {
        "unpaired": unpaired_scorer,
        "paired_default_disagreement": paired_scorer,
        "paired_mde_by_disagreement_rate": paired_scorer_sweep,
        "data_volume_answer_for_3pp_paired_threshold": dv,
        "pairing_reduces_threshold_vs_unpaired": pairing_helps_as_expected,
    }
    chash = config_hash(commit, {"step": "3", "x_sweep": X_SWEEP, "n_trials": N_SYNTH_TRIALS})
    write_cell("3", {"x_sweep": X_SWEEP, "n_trials": N_SYNTH_TRIALS,
                      "disagreement_default": DISAGREEMENT_DEFAULT}, chash, s3)
    if not pairing_helps_as_expected:
        append_finding(
            "**Step 3 CONTRADICTS the prompt's stated expectation.** The prompt "
            "expects pairing to substantially lower the detection threshold "
            f"(Sec 7). Measured: unpaired MDE={unpaired_scorer['minimum_detectable_improvement_pp']}pp, "
            f"paired MDE={paired_scorer['minimum_detectable_improvement_pp']}pp "
            f"(disagreement rate {DISAGREEMENT_DEFAULT}). This is reported as a "
            "finding, not treated as a reason to stop, per the prompt's own rule."
        )
    else:
        append_finding(
            f"**Step 3 confirms the prompt's expectation.** Unpaired MDE="
            f"{unpaired_scorer['minimum_detectable_improvement_pp']}pp, paired MDE="
            f"{paired_scorer['minimum_detectable_improvement_pp']}pp (disagreement rate "
            f"{DISAGREEMENT_DEFAULT}) -- pairing lowers the threshold as expected. "
            f"Data-volume answer for a 3pp paired threshold: {dv}."
        )

    manifest = {
        "run_id": RUN_ID,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": dirty,
        "driver_file": DRIVER_FILE,
        "driver_file_tracked_at_commit": driver_tracked,
        "corpus": {
            "price_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
            "type_json_sha256": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
        },
        "params": {
            "bootstrap_n": BOOTSTRAP_N,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_unit": "ticker",
            "x_sweep": X_SWEEP,
            "n_synth_trials": N_SYNTH_TRIALS,
            "disagreement_rate_default": DISAGREEMENT_DEFAULT,
            "disagreement_rate_sweep": DISAGREEMENT_SWEEP,
            "data_volume_target_pp": DATA_VOLUME_TARGET_PP,
        },
        "results": {
            "step0c_arithmetic_check": s0c,
            "step1_luck_corrected_score": {"scorer": s1_scorer, "simulator": s1_sim},
            "step2_confidence_intervals": {
                "scorer": boot_scorer, "n_independent_blocks_scorer": n_blocks_scorer,
                "simulator": boot_sim, "n_independent_blocks_simulator": n_blocks_sim,
            },
            "step3_detection_threshold": s3,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "scorecard_repair_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nmanifest written -> {out_path}")


if __name__ == "__main__":
    main()
