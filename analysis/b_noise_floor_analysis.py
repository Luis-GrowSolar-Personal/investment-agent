#!/usr/bin/env python3
"""
b_noise_floor_analysis.py -- prompts/B-champion-and-noise-floor.md step 2c ($0, no model calls).

Pairs each train call's original arm-B score (p6-output-format-round/calls.csv, b_score) with its re-run score
(b-champion-and-noise-floor/scores_b_rerun1.jsonl). Reuses the P6 analysis helpers (spearman, ticker-block boot, wilson).
Direction mapping: score <= -2 bearish, >= +3 bullish, else neutral (pre-registered). 'Right' = direction equals gt_old_ruler
(the tradeable-entry 182-day ruler used throughout P6). Ranges: Wilson on rates; 95% ticker-block bootstrap, 2,000 draws, seed 11.
Output: analysis/data/run_state/b-champion-and-noise-floor/results.json
"""
import sys, json, math, random
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402

ORIG = REPO / "analysis/data/run_state/p6-output-format-round"
STATE = REPO / "analysis/data/run_state/b-champion-and-noise-floor"
N_BULL, N_BEAR = 235, 191          # B's original counts at >=+3 and <=-2 on train (P6 wrap-up 6.1 / posthoc.json n_le_-2)


def d3(s):
    return None if s is None else "bearish" if s <= -2 else "bullish" if s >= 3 else "neutral"


def wil(k, n):
    lo, hi = p3.wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson": [round(lo, 2), round(hi, 2)]}


def main():
    calls = A.load_calls(ORIG / "calls.csv")
    rr = {}
    for r in p3.read_jsonl(STATE / "scores_b_rerun1.jsonl"):
        sc, s, nr = A.parse_score(r["content"])
        rr[(r["ticker"], r["date"])] = (s, nr, r["stop_reason"], r["usage"]["output_tokens"])
    assert len(rr) == 1217, len(rr)
    rows = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        assert k in rr, k
        s2, nr2, stop2, tok2 = rr[k]
        rows.append({**c, "s1": c["b_score"], "s2": s2, "nr1": c["b_noRead"], "nr2": nr2, "stop2": stop2, "tok2": tok2})
    assert len(rows) == 1217
    ok = [r for r in rows if r["s1"] is not None and r["s2"] is not None]
    out = {"n_calls": len(rows), "n_paired": len(ok), "unparsed_rerun": sum(r["s2"] is None for r in rows),
           "max_tokens_rerun": sum(r["stop2"] == "max_tokens" for r in rows)}

    def block(rs):
        n = len(rs)
        b = {"n": n}
        b["move_ge1"] = wil(sum(abs(r["s1"] - r["s2"]) >= 1 for r in rs), n)
        b["move_ge2"] = wil(sum(abs(r["s1"] - r["s2"]) >= 2 for r in rs), n)
        ch = [r for r in rs if d3(r["s1"]) != d3(r["s2"])]
        b["direction_change"] = wil(len(ch), n)
        g = [r for r in ch if r["gt_old_ruler"] and ((d3(r["s1"]) == r["gt_old_ruler"]) != (d3(r["s2"]) == r["gt_old_ruler"]))]
        w = sum(d3(r["s1"]) == r["gt_old_ruler"] for r in g)
        b["noise_win_rate"] = {"decisive_changes": len(g), "original_right": w,
                               "pct": round(100 * w / len(g), 1) if g else None,
                               "wilson": [round(x, 1) for x in p3.wilson(w, len(g))] if g else None,
                               "changes_with_truth": sum(1 for r in ch if r["gt_old_ruler"])}
        return b
    out["pooled"] = block(ok)
    out["per_stratum"] = {s: block([r for r in ok if r["stratum"] == s]) for s in sorted({r["stratum"] for r in ok})}

    cats = ["bearish", "neutral", "bullish"]
    out["table_3x3_original_by_rerun"] = {a: {b: sum(d3(r["s1"]) == a and d3(r["s2"]) == b for r in ok) for b in cats} for a in cats}
    out["direction_counts"] = {"original": {c: sum(d3(r["s1"]) == c for r in ok) for c in cats},
                               "rerun": {c: sum(d3(r["s2"]) == c for r in ok) for c in cats}}

    # rank correlation, each run and paired difference (ticker-block bootstrap)
    priced = [r for r in ok if r["fwd_rel_ret_tradeable"] is not None]
    def rho(rs, key):
        return A.spearman([r[key] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs])
    def diff(rs):
        return rho(rs, "s1") - rho(rs, "s2")
    r1, r2 = rho(priced, "s1"), rho(priced, "s2")
    lo1, hi1, _ = A.boot(priced, lambda s: rho(s, "s1"))
    lo2, hi2, _ = A.boot(priced, lambda s: rho(s, "s2"))
    dl, dh, nv = A.boot(priced, diff)
    half = (dh - dl) / 2
    tol = -math.ceil(round(half, 6) * 100) / 100
    out["rank"] = {"n": len(priced), "original": {"rho": r1, "range": [lo1, hi1]}, "rerun": {"rho": r2, "range": [lo2, hi2]},
                   "paired_diff_original_minus_rerun": {"value": r1 - r2, "range": [dl, dh], "valid_draws": nv},
                   "half_width": half, "tolerance_replacing_minus_0.03": tol}

    # matched coverage, both runs. Ties broken by a seeded shuffle (seed 11), identical for both runs.
    rng = random.Random(11)
    order = list(range(len(priced))); rng.shuffle(order)
    tb = {i: order[i] for i in range(len(priced))}
    def top(key, n, sign):
        idx = sorted(range(len(priced)), key=lambda i: (sign * priced[i][key], tb[i]))[:n]
        return [priced[i] for i in idx]
    def hit(rs, want):
        g = [r for r in rs if r["gt_old_ruler"]]
        return {"n": len(rs), "graded": len(g), "hit_pct": round(100 * sum(r["gt_old_ruler"] == want for r in g) / len(g), 1) if g else None,
                "median_ret": round(float(np.median([r["fwd_rel_ret_tradeable"] for r in rs])), 2),
                "min_score_in_cut": min(r[key] for r in rs) if rs else None}
    mc = {}
    for name, key in (("original", "s1"), ("rerun", "s2")):
        t, b = top(key, N_BULL, -1), top(key, N_BEAR, 1)
        for x in (t, b):
            pass
        mc[name] = {"top_235_bullish": {**hit(t, "bullish"), "score_cut": min(r[key] for r in t)},
                    "bottom_191_bearish": {**hit(b, "bearish"), "score_cut": max(r[key] for r in b)},
                    "fixed_cut_ge3_n": sum(r[key] >= 3 for r in priced), "fixed_cut_le-2_n": sum(r[key] <= -2 for r in priced)}
    # overlap of the two runs' matched sets
    def ids(rs): return {(r["ticker"], r["call_date"]) for r in rs}
    mc["overlap"] = {"top_235_shared": len(ids(top("s1", N_BULL, -1)) & ids(top("s2", N_BULL, -1))),
                     "bottom_191_shared": len(ids(top("s1", N_BEAR, 1)) & ids(top("s2", N_BEAR, 1)))}
    out["matched_coverage"] = mc

    nr1, nr2 = sum(bool(r["nr1"]) for r in ok), sum(bool(r["nr2"]) for r in ok)
    out["noRead"] = {"original": wil(nr1, len(ok)), "rerun": wil(nr2, len(ok)),
                     "changed": wil(sum(bool(r["nr1"]) != bool(r["nr2"]) for r in ok), len(ok))}
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
