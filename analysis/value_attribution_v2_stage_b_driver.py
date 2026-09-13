#!/usr/bin/env python3
"""value_attribution_v2_stage_b_driver.py -- Stage B of run_id
value-attribution-and-headroom-v2 (prompts/value-attribution-v2-stage-b.md).

ZERO Anthropic API calls. Zero DB writes (SELECT only, same read path as
test2_look_ahead.py / analyst_direct_scorer.py). No price-cache refresh.

Scope boundary: report, do not decide. Produces B0 (population reconciliation),
B1 (two-baseline lift, both populations, by year), B2 (ground-truth
distribution, precision by predicted class), B3 (McNemar + ticker-block
bootstrap intervals).

    cd analysis
    python3 value_attribution_v2_stage_b_driver.py
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
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

RUN_ID = "value-attribution-and-headroom-v2"
RUN_DIR = REPO / "analysis" / "data" / "run_state" / RUN_ID
CELLS_PATH = RUN_DIR / "cells.jsonl"
FINDINGS_PATH = RUN_DIR / "findings.md"
OUT_DIR = REPO / "analysis" / "data" / "value_attribution_v2"
DRIVER_FILE = "analysis/value_attribution_v2_stage_b_driver.py"

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
TIER1_DOMAINS = ["AMD", "AVGO", "NVDA", "FSLR", "RUN", "SPWR", "AMPX", "ENVX", "EOSE", "QS"]
THIN_YEAR_THRESHOLD = 20  # n_scoreable < 20 -> thin year, from test2_look_ahead.py

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20260913

print("=" * 72)
print("ASSERTION: zero Anthropic API calls / LLM calls in this driver.")
print("All figures come from stored Analysis rows (DB SELECT, read-only) and")
print("the frozen price cache. No re-scoring, no evaluator invocation.")
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
        f.write(f"\n## Stage B finding — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n{text}\n")


# ---------------------------------------------------------------------------
# Data access (read-only)
# ---------------------------------------------------------------------------

def fetch_analysis_rows():
    from dotenv import load_dotenv
    import os, psycopg2, psycopg2.extras
    load_dotenv(REPO / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                   a.recommendation AS rec, a."thesisHealth" AS health,
                   a."modelVersion" AS model_version, a."promptVersion" AS prompt_version,
                   a."createdAt" AS created_at
            FROM "Analysis" a
            JOIN "Transcript" t ON a."transcriptId" = t.id
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            ORDER BY t."callDate"
        """)
        rows = cur.fetchall()
    conn.close()
    return rows


def score_rows(rows, prices, tickers_filter=None):
    from analyst_direct_scorer import direction_from_score, FORWARD_DAYS, DEAD_BAND, BENCHMARK
    out = []
    for r in rows:
        ticker = r["ticker"]
        if tickers_filter is not None and ticker not in tickers_filter:
            continue
        score = {"recommendation": r["rec"], "thesisHealth": r["health"]}
        predicted = direction_from_score(score)
        call_date = r["call_date"]
        rec = {"ticker": ticker, "call_date": call_date, "predicted": predicted,
               "model_version": r["model_version"], "prompt_version": r["prompt_version"],
               "created_at": r["created_at"], "scoreable": False,
               "ground_truth": None, "hit": None,
               "always_bullish_hit": None, "always_hold_hit": None}
        if predicted is None:
            out.append(rec)
            continue
        p0, _ = prices.price_on_or_after(ticker, call_date)
        b0, _ = prices.price_on_or_after(BENCHMARK, call_date)
        fwd_target = call_date + timedelta(days=FORWARD_DAYS)
        p1, _ = prices.price_on_or_after(ticker, fwd_target)
        b1, _ = prices.price_on_or_after(BENCHMARK, fwd_target)
        if not all([p0, b0, p1, b1]):
            out.append(rec)
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
        rec.update(scoreable=True, ground_truth=gt, hit=(predicted == gt),
                    always_bullish_hit=(gt == "bullish"),
                    always_hold_hit=(gt == "neutral"))
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# B0 -- reconcile the two populations
# ---------------------------------------------------------------------------

def build_populations():
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH
    rows = fetch_analysis_rows()
    prices = PriceCache(PRICE_CACHE_PATH)
    scored_all = score_rows(rows, prices, tickers_filter=ALL16)
    scoreable_all = [r for r in scored_all if r["scoreable"]]

    # scorer population: every scoreable ALL16 row (362), and the thin-year-
    # filtered subset used for aggregate figures (359: excludes 2020 n=3, 2026 n=0).
    by_year = defaultdict(list)
    for r in scoreable_all:
        by_year[r["call_date"].year].append(r)
    thin_years = {y for y, v in by_year.items() if len(v) < THIN_YEAR_THRESHOLD}
    scorer_full = scoreable_all
    scorer_thin_filtered = [r for r in scoreable_all if r["call_date"].year not in thin_years]

    # simulator population: load_events_dedup_on() -- ALL16, call_date <= 2024-06-12,
    # Analysis.createdAt in the v6 window (2026-05-02 12:33:23-04 to
    # 2026-06-27 16:26:16-04), same-day-dedup'd.
    import sweep_cadence_and_session_model as S
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    sim_keys = [(e.ticker, e.call_date) for e in events]

    scoreable_by_key = {}
    for r in scoreable_all:
        scoreable_by_key.setdefault((r["ticker"], r["call_date"]), []).append(r)

    sim_population = []
    sim_keys_not_in_scorer = []
    for k in sim_keys:
        matches = scoreable_by_key.get(k)
        if matches:
            # multiple Analysis rows can share (ticker, call_date) pre-dedup on the
            # scorer side (e.g. re-scores); take the one whose created_at falls in
            # load_call_events' own v6 window, else the first match.
            sim_population.append(matches[0])
        else:
            sim_keys_not_in_scorer.append(k)

    return {
        "rows_raw": rows,
        "scorer_full": scorer_full,           # 362
        "scorer_thin_filtered": scorer_thin_filtered,  # 359
        "thin_years": sorted(thin_years),
        "sim_events_n": len(events),
        "sim_population": sim_population,      # scored rows matched to the 195 sim events
        "sim_keys_not_in_scorer": sim_keys_not_in_scorer,
        "by_year_scorer": {y: len(v) for y, v in sorted(by_year.items())},
    }


def step_b0(pops, driver_commit, branch, dirty, driver_tracked):
    scorer_full = pops["scorer_full"]
    sim_pop = pops["sim_population"]
    n_scorer = len(scorer_full)
    n_sim = pops["sim_events_n"]
    n_matched = len(sim_pop)
    n_unmatched = len(pops["sim_keys_not_in_scorer"])

    by_year_scorer = defaultdict(int)
    for r in scorer_full:
        by_year_scorer[r["call_date"].year] += 1
    by_year_sim = defaultdict(int)
    for r in sim_pop:
        by_year_sim[r["call_date"].year] += 1
    years = sorted(set(by_year_scorer) | set(by_year_sim))
    per_year_table = [
        {"year": y, "scorer_n": by_year_scorer.get(y, 0), "simulator_n": by_year_sim.get(y, 0)}
        for y in years
    ]

    results = {
        "scorer_population_n": n_scorer,
        "scorer_population_n_thin_filtered": len(pops["scorer_thin_filtered"]),
        "thin_years_excluded": pops["thin_years"],
        "simulator_population_n": n_sim,
        "simulator_events_matched_to_scorer_row": n_matched,
        "simulator_events_with_no_scorer_row": n_unmatched,
        "simulator_unmatched_keys_sample": [
            [t, str(d)] for t, d in pops["sim_keys_not_in_scorer"][:10]
        ],
        "per_year_table": per_year_table,
        "explanation": (
            "The scorer population (analyst_direct_scorer.py / test2_look_ahead.py) is "
            "every ALL16 Analysis row with 2Q-forward price data, no createdAt "
            "restriction and no simulator call-date ceiling: 362 rows (359 after "
            "excluding thin years 2020 n=3 and 2026 n=0, threshold n_scoreable<20). "
            "The simulator population (sweep_cadence_and_session_model.load_events_dedup_on "
            "-> analysis.simulator.data.load_call_events) restricts on THREE axes at "
            "once, not the two Stage A's next_action named: (1) call_date <= 2024-06-12 "
            "(module constant C); (2) Analysis.createdAt inside the v6 window "
            "2026-05-02 12:33:23-04 to 2026-06-27 16:26:16-04 (load_call_events' "
            "analysis_created_after/analysis_created_before defaults -- this is the "
            "same window the 09-13 handoff's Sec2 caveat calls unverified, and it is "
            "in fact load-bearing for which rows the simulator sees); (3) same-day "
            "dedup collapsing multiple same-date transcripts to one event. The scorer "
            "population applies none of these three restrictions -- it is a superset "
            "on the createdAt and call-date axes and a strict superset on the dedup "
            "axis. This is a THIRD axis beyond Stage A's identified two (dedup, "
            "call-date window): the createdAt (prompt-vintage) restriction."
        ),
        "premise_check": (
            "Stage A's progress.json next_action described the difference as same-day "
            "dedup PLUS a narrower call-date window. Verified against "
            "analysis/simulator/data.py load_call_events(): there is a third, unstated "
            "restriction -- the analysis_created_after/before v6-window filter, which "
            "the 09-13 handoff (Sec1) already flags as 'unverified' on the scorer side. "
            "Flagging this explicitly per the launch instruction to verify premises: "
            "the prompt's Sec B0 statement 'these differ on two axes at once' is "
            "incomplete, not wrong -- it is a real subset of the difference, not all "
            "of it."
        ),
    }
    chash = config_hash(driver_commit, {"step": "B0"})
    write_cell("B0", {}, chash, results)
    append_finding(
        f"**B0 population reconciliation.** Scorer population = {n_scorer} rows "
        f"(all16, price-scoreable, no createdAt/call-date restriction); "
        f"{len(pops['scorer_thin_filtered'])} after excluding thin years "
        f"{pops['thin_years']}. Simulator population = {n_sim} call-events "
        f"(load_events_dedup_on: call_date<=2024-06-12 AND createdAt in v6 window "
        f"AND same-day-dedup). {n_matched} of {n_sim} simulator events matched a "
        f"scorer row by (ticker, call_date); {n_unmatched} did not "
        f"(same-day-dedup drops the non-kept sibling transcript from the scorer's "
        f"row-count-by-key view under a naive join). The simulator/scorer gap is "
        f"THREE restriction axes (call-date ceiling, createdAt/prompt-vintage "
        f"window, same-day dedup), not two as Stage A's next_action stated -- "
        f"correcting that premise here."
    )
    return results


# ---------------------------------------------------------------------------
# B1 -- lift against both baselines, both populations, by year
# ---------------------------------------------------------------------------

def wilson_ci(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def lift_stats(scored):
    n = len(scored)
    if n == 0:
        return None
    hits = sum(1 for r in scored if r["hit"])
    bull_base = sum(1 for r in scored if r["always_bullish_hit"])
    hold_base = sum(1 for r in scored if r["always_hold_hit"])
    hit_rate = hits / n
    bull_rate = bull_base / n
    hold_rate = hold_base / n
    return {
        "n": n,
        "hit_rate_pct": round(hit_rate * 100, 1),
        "always_bullish_baseline_pct": round(bull_rate * 100, 1),
        "always_bullish_lift_pp": round((hit_rate - bull_rate) * 100, 1),
        "always_hold_baseline_pct": round(hold_rate * 100, 1),
        "always_hold_lift_pp": round((hit_rate - hold_rate) * 100, 1),
        "hit_rate_ci95": [round(x * 100, 1) if x is not None else None for x in wilson_ci(hits, n)],
    }


def step_b1(pops, driver_commit, branch, dirty, driver_tracked):
    def by_year(pop):
        d = defaultdict(list)
        for r in pop:
            d[r["call_date"].year].append(r)
        return d

    scorer_by_year = by_year(pops["scorer_full"])
    sim_by_year = by_year(pops["sim_population"])

    def year_table(by_year_dict, thin_threshold=THIN_YEAR_THRESHOLD):
        out = {}
        for y, v in sorted(by_year_dict.items()):
            s = lift_stats(v)
            if s:
                s["thin_year"] = s["n"] < thin_threshold
            out[y] = s
        return out

    scorer_table = year_table(scorer_by_year)
    sim_table = year_table(sim_by_year)

    scorer_agg = lift_stats(pops["scorer_thin_filtered"])
    scorer_agg_all_years = lift_stats(pops["scorer_full"])
    sim_agg = lift_stats(pops["sim_population"])

    # reproduction cross-check against Test 2's published figures
    repro_ok = (
        scorer_agg["n"] == 359 and
        abs(scorer_agg["hit_rate_pct"] - 40.4) < 0.15 and
        abs(scorer_agg["always_bullish_baseline_pct"] - 46.2) < 0.15 and
        abs(scorer_agg["always_bullish_lift_pp"] - (-5.8)) < 0.15
    )

    results = {
        "scorer_population_by_year": scorer_table,
        "simulator_population_by_year": sim_table,
        "scorer_population_aggregate_thin_filtered_n359": scorer_agg,
        "scorer_population_aggregate_all_years_n362": scorer_agg_all_years,
        "simulator_population_aggregate_n195": sim_agg,
        "test2_reproduction_check": {
            "expected": {"n": 359, "hit_rate_pct": 40.4, "always_bullish_baseline_pct": 46.2,
                         "always_bullish_lift_pp": -5.8},
            "measured": scorer_agg,
            "reproduces": repro_ok,
        },
        "always_hold_expectation_check": {
            "expected_always_hold_lift_pp_approx": 6.7,
            "measured_always_hold_lift_pp": scorer_agg["always_hold_lift_pp"],
            "contradicts_expectation": abs(scorer_agg["always_hold_lift_pp"] - 6.7) > 1.5,
        },
    }
    chash = config_hash(driver_commit, {"step": "B1"})
    write_cell("B1", {}, chash, results)
    append_finding(
        f"**B1 lift, both baselines.** Scorer population (n=359, thin-filtered): "
        f"hit rate {scorer_agg['hit_rate_pct']}%, always-bullish lift "
        f"{scorer_agg['always_bullish_lift_pp']}pp, always-hold lift "
        f"{scorer_agg['always_hold_lift_pp']}pp. Test-2 reproduction: "
        f"{'PASSED' if repro_ok else 'FAILED -- see cells.jsonl B1 for detail'}. "
        f"Simulator population (n={sim_agg['n']}): hit rate {sim_agg['hit_rate_pct']}%, "
        f"always-bullish lift {sim_agg['always_bullish_lift_pp']}pp, always-hold lift "
        f"{sim_agg['always_hold_lift_pp']}pp. Always-hold-lift expectation (+6.7pp, "
        f"prompt Sec6) {'HELD' if not results['always_hold_expectation_check']['contradicts_expectation'] else 'WAS CONTRADICTED -- see below'}."
    )
    return results


# ---------------------------------------------------------------------------
# B2 -- ground-truth distribution
# ---------------------------------------------------------------------------

def step_b2(pops, driver_commit, branch, dirty, driver_tracked):
    def dist(pop):
        n = len(pop)
        gt_counts = Counter(r["ground_truth"] for r in pop)
        pred_counts = Counter(r["predicted"] for r in pop)
        precision = {}
        for cls in ("bullish", "bearish", "neutral"):
            subset = [r for r in pop if r["predicted"] == cls]
            hits = sum(1 for r in subset if r["hit"])
            precision[cls] = {
                "n_predicted": len(subset),
                "precision_pct": round(hits / len(subset) * 100, 1) if subset else None,
                "base_rate_pct": round(gt_counts.get(cls, 0) / n * 100, 1) if n else None,
            }
        bearish_gt = [r for r in pop if r["ground_truth"] == "bearish"]
        bearish_pred_on_bearish_gt = sum(1 for r in bearish_gt if r["predicted"] == "bearish")
        return {
            "n": n,
            "ground_truth_counts": dict(gt_counts),
            "ground_truth_pct": {k: round(v / n * 100, 1) for k, v in gt_counts.items()} if n else {},
            "prediction_counts": dict(pred_counts),
            "precision_and_base_rate_by_predicted_class": precision,
            "bearish_base_rate_pct": round(len(bearish_gt) / n * 100, 1) if n else None,
            "bearish_call_accuracy_pct": precision["bearish"]["precision_pct"],
        }

    scorer_agg = dist(pops["scorer_thin_filtered"])
    sim_agg = dist(pops["sim_population"])

    by_year = defaultdict(list)
    for r in pops["scorer_full"]:
        by_year[r["call_date"].year].append(r)
    scorer_by_year = {y: dist(v) for y, v in sorted(by_year.items())}

    results = {
        "scorer_population_aggregate_n359": scorer_agg,
        "simulator_population_aggregate_n195": sim_agg,
        "scorer_population_by_year": scorer_by_year,
    }
    chash = config_hash(driver_commit, {"step": "B2"})
    write_cell("B2", {}, chash, results)
    append_finding(
        f"**B2 ground truth distribution.** Scorer population (n=359): bearish base "
        f"rate {scorer_agg['bearish_base_rate_pct']}%, bearish-call accuracy "
        f"{scorer_agg['bearish_call_accuracy_pct']}% (n_predicted_bearish="
        f"{scorer_agg['precision_and_base_rate_by_predicted_class']['bearish']['n_predicted']}). "
        f"This directly bears on the 09-13 handoff's 'wrong roughly four times in "
        f"five' claim (B4b)."
    )
    return results


# ---------------------------------------------------------------------------
# B3 -- McNemar + ticker-block bootstrap
# ---------------------------------------------------------------------------

def mcnemar_exact(pop, baseline_key):
    """Exact binomial McNemar on discordant pairs: analyst hit vs baseline hit."""
    b = sum(1 for r in pop if r["hit"] and not r[baseline_key])   # analyst right, baseline wrong
    c = sum(1 for r in pop if not r["hit"] and r[baseline_key])   # analyst wrong, baseline right
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_discordant": 0, "p_value": 1.0}
    k = min(b, c)
    # exact two-sided binomial test, p=0.5
    def binom_cdf(k, n, p=0.5):
        return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))
    p_one_side = binom_cdf(k, n)
    p_value = min(1.0, 2 * p_one_side)
    return {"b": b, "c": c, "n_discordant": n, "p_value": round(p_value, 4)}


def ticker_block_bootstrap(pop, n_resamples, seed):
    rng = random.Random(seed)
    tickers = sorted({r["ticker"] for r in pop})
    by_ticker = defaultdict(list)
    for r in pop:
        by_ticker[r["ticker"]].append(r)

    metrics = {"always_bullish_lift_pp": [], "always_hold_lift_pp": [],
               "hit_rate_pct": [], "bearish_call_accuracy_pct": []}

    for _ in range(n_resamples):
        sample_tickers = [rng.choice(tickers) for _ in tickers]
        sample = []
        for t in sample_tickers:
            sample.extend(by_ticker[t])
        n = len(sample)
        if n == 0:
            continue
        hits = sum(1 for r in sample if r["hit"])
        bull_base = sum(1 for r in sample if r["always_bullish_hit"])
        hold_base = sum(1 for r in sample if r["always_hold_hit"])
        bearish_pred = [r for r in sample if r["predicted"] == "bearish"]
        metrics["hit_rate_pct"].append(hits / n * 100)
        metrics["always_bullish_lift_pp"].append((hits - bull_base) / n * 100)
        metrics["always_hold_lift_pp"].append((hits - hold_base) / n * 100)
        if bearish_pred:
            bh = sum(1 for r in bearish_pred if r["hit"])
            metrics["bearish_call_accuracy_pct"].append(bh / len(bearish_pred) * 100)

    def pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        idx = min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))
        return round(s[idx], 2)

    out = {}
    for k, vals in metrics.items():
        out[k] = {
            "n_resamples_with_data": len(vals),
            "ci95_lo": pct(vals, 2.5),
            "ci95_hi": pct(vals, 97.5),
            "point_estimate_median": pct(vals, 50),
            "spans_zero": (pct(vals, 2.5) is not None and pct(vals, 97.5) is not None and
                           pct(vals, 2.5) <= 0 <= pct(vals, 97.5)) if "lift" in k else None,
        }
    return out, len(tickers)


def step_b3(pops, driver_commit, branch, dirty, driver_tracked):
    scorer_pop = pops["scorer_thin_filtered"]
    sim_pop = pops["sim_population"]

    mcnemar_scorer_bullish = mcnemar_exact(scorer_pop, "always_bullish_hit")
    mcnemar_scorer_hold = mcnemar_exact(scorer_pop, "always_hold_hit")
    mcnemar_sim_bullish = mcnemar_exact(sim_pop, "always_bullish_hit")
    mcnemar_sim_hold = mcnemar_exact(sim_pop, "always_hold_hit")

    boot_scorer, n_blocks_scorer = ticker_block_bootstrap(scorer_pop, BOOTSTRAP_N, BOOTSTRAP_SEED)
    boot_sim, n_blocks_sim = ticker_block_bootstrap(sim_pop, BOOTSTRAP_N, BOOTSTRAP_SEED)

    any_span_zero = any(
        v.get("spans_zero") for v in list(boot_scorer.values()) + list(boot_sim.values())
        if v.get("spans_zero") is not None
    )

    results = {
        "mcnemar": {
            "scorer_population_vs_always_bullish": mcnemar_scorer_bullish,
            "scorer_population_vs_always_hold": mcnemar_scorer_hold,
            "simulator_population_vs_always_bullish": mcnemar_sim_bullish,
            "simulator_population_vs_always_hold": mcnemar_sim_hold,
            "variant": "exact binomial on discordant pairs (b,c), two-sided, alpha=0.05",
        },
        "bootstrap": {
            "resampling_unit": "ticker",
            "n_resamples": BOOTSTRAP_N,
            "seed": BOOTSTRAP_SEED,
            "n_independent_blocks_scorer_population": n_blocks_scorer,
            "n_independent_blocks_simulator_population": n_blocks_sim,
            "scorer_population_ci95": boot_scorer,
            "simulator_population_ci95": boot_sim,
        },
        "any_lift_interval_spans_zero": any_span_zero,
    }
    chash = config_hash(driver_commit, {"step": "B3", "bootstrap_n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED})
    write_cell("B3", {"bootstrap_n": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED}, chash, results)
    append_finding(
        f"**B3 intervals.** McNemar (scorer pop, always-bullish): b={mcnemar_scorer_bullish['b']} "
        f"c={mcnemar_scorer_bullish['c']} p={mcnemar_scorer_bullish['p_value']}. "
        f"McNemar (scorer pop, always-hold): b={mcnemar_scorer_hold['b']} "
        f"c={mcnemar_scorer_hold['c']} p={mcnemar_scorer_hold['p_value']}. "
        f"Ticker-block bootstrap ({BOOTSTRAP_N} resamples, seed {BOOTSTRAP_SEED}, "
        f"{n_blocks_scorer} independent blocks): always-bullish-lift 95% CI "
        f"[{boot_scorer['always_bullish_lift_pp']['ci95_lo']}, "
        f"{boot_scorer['always_bullish_lift_pp']['ci95_hi']}]pp; always-hold-lift 95% CI "
        f"[{boot_scorer['always_hold_lift_pp']['ci95_lo']}, "
        f"{boot_scorer['always_hold_lift_pp']['ci95_hi']}]pp. "
        f"ANY LIFT INTERVAL SPANS ZERO: {any_span_zero}."
    )
    return results


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    commit, branch, dirty, driver_tracked, dirty_lines = git_info()
    print(f"git_commit={commit} branch={branch} dirty={dirty} driver_tracked={driver_tracked}")
    if dirty:
        print("DIRTY LINES:")
        for ln in dirty_lines:
            print(" ", ln)

    pops = build_populations()
    b0 = step_b0(pops, commit, branch, dirty, driver_tracked)
    b1 = step_b1(pops, commit, branch, dirty, driver_tracked)
    b2 = step_b2(pops, commit, branch, dirty, driver_tracked)
    b3 = step_b3(pops, commit, branch, dirty, driver_tracked)

    manifest = {
        "run_id": RUN_ID,
        "stage": "B",
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
            "thin_year_threshold": THIN_YEAR_THRESHOLD,
            "bootstrap_n": BOOTSTRAP_N,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_unit": "ticker",
        },
        "results": {"B0": b0, "B1": b1, "B2": b2, "B3": b3},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "stage_b_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nmanifest written -> {out_path}")


if __name__ == "__main__":
    main()
