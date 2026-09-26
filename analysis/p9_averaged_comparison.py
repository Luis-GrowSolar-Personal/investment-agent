#!/usr/bin/env python3
"""
p9_averaged_comparison.py -- prompts/P9-close-and-averaged-comparison.md Step 2 ($0, no model calls).
Averaged B = mean of B's two `score` per call (draw 1: p6-output-format-round/calls.csv b_score; draw 2: b-champion-and-noise-floor/scores_b_rerun1.jsonl).
Averaged P9 = mean of P9's two `expectedReturn` per call (per_call_diffs.csv of p9-expected-return-train and p9-second-draw/per_call_diffs_draw2.csv).
Groups bottom 191 / top 235 by the averaged number, ties by the seeded shuffle (seed 11) over calls in calls.csv order; ranges are 95% ticker-block
bootstrap, 2,000 draws, seed 11; clip +/-50 for the P9 slope. Output: analysis/data/run_state/p9-close-and-averaged/results.json
"""
import sys, json, csv, random
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402

RS = REPO / "analysis/data/run_state"
OUT = RS / "p9-close-and-averaged"
NB, NL, CLIP = 235, 191, 50.0


def slope(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()) if len(x) > 2 and x.std() else float("nan")


def main():
    calls = A.load_calls(RS / "p6-output-format-round/calls.csv")
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    def per(path):
        return {(r["ticker"], r["call_date"]): float(r["expectedReturn"]) for r in csv.DictReader(open(path))}
    p1, p2 = per(RS / "p9-expected-return-train/per_call_diffs.csv"), per(RS / "p9-second-draw/per_call_diffs_draw2.csv")
    rows = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        if c["fwd_rel_ret_tradeable"] is None: continue
        rows.append({"ticker": c["ticker"], "k": k, "stratum": c["stratum"], "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"],
                     "b1": c["b_score"], "b2": b2[k], "p1": p1[k], "p2": p2[k]})
    assert len(rows) == 1217 == len(p1) == len(p2) == len(b2)
    for r in rows:
        r["bavg"], r["pavg"], r["c"] = (r["b1"] + r["b2"]) / 2, (r["p1"] + r["p2"]) / 2, max(-CLIP, min(CLIP, r["ret"]))
    rng = random.Random(11); order = list(range(len(rows))); rng.shuffle(order)
    rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
    def pick(key, n, sign):
        return [rows[i] for i in sorted(range(len(rows)), key=lambda i: (sign * rows[i][key], order[i]))[:n]]
    def hit(rs, want):
        g = [r for r in rs if r["gt"]]; k = sum(r["gt"] == want for r in g)
        return {"n": len(rs), "hit_pct": round(100 * k / len(g), 1), "wilson": [round(x, 1) for x in p3.wilson(k, len(g))], "median_ret": round(float(np.median([r["ret"] for r in rs])), 2)}
    def fifths(key):
        idx = sorted(range(len(rows)), key=lambda i: (rows[i][key], order[i]))
        return [round(float(np.median([rows[i]["ret"] for i in ch])), 2) for ch in np.array_split(idx, 5)]
    out = {"n": len(rows), "distinct_values": {"avg_B": len({r["bavg"] for r in rows}), "avg_P9": len({r["pavg"] for r in rows})}}
    for name, key, sg, want in (("avg_B", "bavg", 1, "bearish"), ("avg_P9", "pavg", 1, "bearish")):
        bot = pick(key, NL, 1); top = pick(key, NB, -1)
        w = lambda s, kk=key: A.spearman([r[kk] for r in s], [r["ret"] for r in s])
        blo, bhi, _ = A.boot(rows, lambda s, kk=key: A.spearman([r[kk] for r in s], [r["ret"] for r in s]))
        wl, wh, _ = A.boot(bot, w)
        out[name] = {"rho": rho(rows, key), "rho_range": [blo, bhi], "bottom191": hit(bot, "bearish"), "top235": hit(top, "bullish"),
                     "severity_rho_within_bottom191": w(bot), "severity_range": [wl, wh], "fifths_realized_median": fifths(key),
                     "distinct_scores_in_bottom191": len({r[key] for r in bot})}
    out["avg_P9"]["clipped_slope"] = slope([r["pavg"] for r in rows], [r["c"] for r in rows])
    out["avg_P9"]["clipped_slope_range"] = A.boot(rows, lambda s: slope([r["pavg"] for r in s], [r["c"] for r in s]))[:2]
    out["avg_B"]["slope_on_avg_score_clipped_NOT_COMPARABLE_IN_UNITS"] = slope([r["bavg"] for r in rows], [r["c"] for r in rows])
    dlo, dhi, nv = A.boot(rows, lambda s: rho(s, "pavg") - rho(s, "bavg"))
    d = rho(rows, "pavg") - rho(rows, "bavg")
    out["paired_avgP9_minus_avgB"] = {"value": d, "range": [dlo, dhi], "valid_draws": nv, "lower_end_ge_-0.03": dlo >= -0.03, "excludes_zero": dlo > 0 or dhi < 0}
    out["reading"] = ("closed" if dlo < -0.03 else "worth a tune test — better ranking too" if dlo > 0 else "worth a tune test — equal ranking, plus severity")
    single = {k: rho(rows, k) for k in ("b1", "b2", "p1", "p2")}
    out["single_draw_rho"] = single
    out["averaging_help"] = {"B": out["avg_B"]["rho"] - (single["b1"] + single["b2"]) / 2, "P9": out["avg_P9"]["rho"] - (single["p1"] + single["p2"]) / 2}
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
