#!/usr/bin/env python3
"""
opus_screen_analysis.py -- prompts/opus-screen.md Step 3 ($0, no model calls).
300 train calls (opus-screen/selection.json): B on claude-opus-5-5 (scores_b_opus.jsonl) vs B draw 1 (p6 calls.csv b_score) and draw 2
(b-champion-and-noise-floor/scores_b_rerun1.jsonl). Mapping <= -2 bearish, >= +3 bullish, else neutral. Ranges: Wilson (rates), 95% ticker-block bootstrap
(2,000 draws, seed 11; all three disagreement rates recomputed on each resample). Output: opus-screen/results.json
"""
import sys, json
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402
import random

RS = REPO / "analysis/data/run_state"
S = RS / "opus-screen"


def d3(s):
    return None if s is None else "bearish" if s <= -2 else "bullish" if s >= 3 else "neutral"


def wil(k, n):
    lo, hi = p3.wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1), "wilson": [round(lo, 1), round(hi, 1)]}


def main():
    sel = {tuple(x) for x in json.loads((S / "selection.json").read_text())["selection"]}
    calls = {(c["ticker"], c["call_date"]): c for c in A.load_calls(RS / "p6-output-format-round/calls.csv")}
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    op = {}
    for r in p3.read_jsonl(S / "scores_b_opus.jsonl"):
        sc, s, nr = A.parse_score(r["content"])
        op[(r["ticker"], r["date"])] = {"s": s, "nr": nr, "tok": r["usage"]["output_tokens"], "cost": r["cost_usd"], "stop": r["stop_reason"], "model": r["model"]}
    assert len(op) == 300 and set(op) == sel
    rows = []
    for k in sorted(sel):
        c = calls[k]
        rows.append({"ticker": k[0], "date": k[1], "stratum": c["stratum"], "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"], "b1": c["b_score"], "b2": b2[k],
                     "o": op[k]["s"], "onr": op[k]["nr"], "b1nr": c["b_noRead"], "tok": op[k]["tok"], "cost": op[k]["cost"]})
    ok = [r for r in rows if None not in (r["b1"], r["b2"], r["o"])]
    out = {"n": len(rows), "n_all_three_scores": len(ok), "unparsed_opus": sum(r["o"] is None for r in rows), "max_tokens_opus": sum(op[k]["stop"] == "max_tokens" for k in op),
           "opus_models": sorted({v["model"] for v in op.values()})}

    def rate(rs, a, b): return 100 * sum(d3(r[a]) != d3(r[b]) for r in rs) / len(rs)
    r1, r2, rs_ = rate(ok, "o", "b1"), rate(ok, "o", "b2"), rate(ok, "b1", "b2")
    out["1_direction_disagreement"] = {"opus_vs_B1": wil(sum(d3(r["o"]) != d3(r["b1"]) for r in ok), len(ok)), "opus_vs_B2": wil(sum(d3(r["o"]) != d3(r["b2"]) for r in ok), len(ok)),
                                       "B1_vs_B2": wil(sum(d3(r["b1"]) != d3(r["b2"]) for r in ok), len(ok))}
    fig = lambda rs: (rate(rs, "o", "b1") + rate(rs, "o", "b2")) / 2 - rate(rs, "b1", "b2")
    lo, hi, nv = A.boot(ok, fig)
    out["2_screen_figure"] = {"mean_opus_vs_sonnet_pct": round((r1 + r2) / 2, 2), "sonnet_vs_sonnet_pct": round(rs_, 2), "difference_pts": round(fig(ok), 2), "range": [round(lo, 2), round(hi, 2)], "valid_draws": nv,
                              "reading": "reads differently — worth a full test" if lo > 0 else "nothing new", "within_3_points_prediction": abs(fig(ok)) <= 3}
    mv = lambda a, b: {"moved_ge1": wil(sum(abs(r[a] - r[b]) >= 1 for r in ok), len(ok)), "moved_ge2": wil(sum(abs(r[a] - r[b]) >= 2 for r in ok), len(ok))}
    out["3_score_moves"] = {"opus_vs_B1": mv("o", "b1"), "opus_vs_B2": mv("o", "b2"), "B1_vs_B2": mv("b1", "b2")}
    cats = ["bearish", "neutral", "bullish"]
    tab = lambda x: {a: {b: sum(d3(r[x]) == a and d3(r["o"]) == b for r in ok) for b in cats} for a in cats}
    out["4_tables_rows_B_cols_opus"] = {"B1": tab("b1"), "B2": tab("b2")}
    # 5 reported, not evidence
    rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
    out["5_rank_correlation"] = {k: {"rho": rho(ok, kk), "range": A.boot(ok, lambda s, q=kk: rho(s, q))[:2]} for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))}
    rng = random.Random(11); order = list(range(len(ok))); rng.shuffle(order)
    def pick(key, n, sign): return [ok[i] for i in sorted(range(len(ok)), key=lambda i: (sign * ok[i][key], order[i]))[:n]]
    def hit(rs, want):
        g = [r for r in rs if r["gt"]]; k = sum(r["gt"] == want for r in g)
        return {"n": len(rs), "hit_pct": round(100 * k / len(g), 1), "wilson": [round(x, 1) for x in p3.wilson(k, len(g))], "median_ret": round(float(np.median([r["ret"] for r in rs])), 2)}
    out["5_matched_hits_bottom47_top58"] = {k: {"bottom47_bearish": hit(pick(kk, 47, 1), "bearish"), "top58_bullish": hit(pick(kk, 58, -1), "bullish")} for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))}
    W = [r for r in ok if r["ret"] >= 20]
    from collections import Counter
    out["5_big_winners"] = {"n": len(W), "mean_score": {k: round(float(np.mean([r[kk] for r in W])), 2) for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))},
                            "bullish_ge3": {k: sum(r[kk] >= 3 for r in W) for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))},
                            "bearish_le-2": {k: sum(r[kk] <= -2 for r in W) for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))},
                            "score_dist": {k: {str(s): v for s, v in sorted(Counter(r[kk] for r in W).items())} for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))}}
    out["5_direction_counts_all_300"] = {k: {c: sum(d3(r[kk]) == c for r in ok) for c in cats} for k, kk in (("opus", "o"), ("B1", "b1"), ("B2", "b2"))}
    out["6_cost_tokens"] = {"opus_cost_per_call": round(sum(r["cost"] for r in rows) / len(rows), 5), "opus_total_usd": round(sum(r["cost"] for r in rows), 2), "sonnet_B_cost_per_call": 0.0236,
                            "opus_median_output_tokens": float(np.median([r["tok"] for r in rows])), "noRead_opus": wil(sum(bool(r["onr"]) for r in ok), len(ok)),
                            "noRead_B1": wil(sum(bool(r["b1nr"]) for r in ok), len(ok))}
    (S / "results.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
