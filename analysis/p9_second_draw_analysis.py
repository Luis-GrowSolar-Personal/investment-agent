#!/usr/bin/env python3
"""
p9_second_draw_analysis.py -- prompts/P9-second-draw.md steps 2 and 3 ($0, no model calls).
Inputs: p9-expected-return-train/{results.json, per_call_diffs.csv} (draw 1) and p9-second-draw/{results_draw2.json, per_call_diffs_draw2.csv}
(draw 2, from `p9_expected_return_analysis.py --draw2`). Output: p9-second-draw/results_verdict.json.
Conventions as p9_expected_return_analysis.py: groups bottom 191 / top 235, seeded ties (seed 11), clip +/-50, 2,000-draw ticker-block bootstrap seed 11.
"""
import sys, json, csv, random
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402

RS = REPO / "analysis/data/run_state"
S1, S2 = RS / "p9-expected-return-train", RS / "p9-second-draw"
NB, NL, CLIP = 235, 191, 50.0
B_REF = {"group_change_pct": 12.5, "rank_diff": 0.031, "half_width": 0.027}   # wrap-ups/B-champion-and-noise-floor-out.md


def slope(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()) if len(x) > 2 and x.std() else float("nan")


def load(path):
    out = []
    for r in csv.DictReader(open(path)):
        out.append({"ticker": r["ticker"], "call_date": r["call_date"], "stratum": r["stratum"], "ret": float(r["ret"]), "gt": r["gt"],
                    "er": float(r["expectedReturn"]), "lo": float(r["rangeLow"]), "hi": float(r["rangeHigh"]), "grp": r["p9_group"]})
    return out


def wil(k, n):
    lo, hi = p3.wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 2) if n else None, "wilson": [round(lo, 2), round(hi, 2)]}


def main():
    r1, r2 = load(S1 / "per_call_diffs.csv"), load(S2 / "per_call_diffs_draw2.csv")
    assert len(r1) == len(r2) == 1217 and all((a["ticker"], a["call_date"]) == (b["ticker"], b["call_date"]) for a, b in zip(r1, r2))
    res1, res2 = json.loads((S1 / "results.json").read_text()), json.loads((S2 / "results_draw2.json").read_text())
    out = {"draw2_parse": {k: res2[k] for k in ("unparsed", "max_tokens", "range_order_broken")}}

    # ---- step 2: 2x3 gate table and severity
    def gates(res):
        g = res["gates"]; c = res["calibration"]
        return {"gate1": {"clipped_slope": c["slope_clipped"], "range": c["range_clipped"], "held": c["gate1_holds"]},
                "gate2": {d: {"value": v["paired_rho_diff"], "range": v["range"], "held": v["gate2_holds"]} for d, v in g["gate2"].items()},
                "gate3": {"bottom191_hit_pct": g["gate3_bottom191_hit_pct"], "held": g["gate3_holds"]},
                "rank": res["rank"]["P9"], "bottom191": res["bottom191"]["P9"], "severity": res["severity"]}
    G = {"draw1": gates(res1), "draw2": gates(res2)}
    checks = 0
    for d in G.values():
        checks += int(d["gate1"]["held"]) + sum(int(v["held"]) for v in d["gate2"].values()) + int(d["gate3"]["held"])
    # 6 gate checks in the prompt's opening sentence = 2 draws x 3 gates (gate 2 counted held only if it holds against both B draws)
    per_draw = {k: [d["gate1"]["held"], all(v["held"] for v in d["gate2"].values()), d["gate3"]["held"]] for k, d in G.items()}
    n_held = sum(sum(v) for v in per_draw.values())
    out["gates"] = G; out["gates_held_per_draw_[g1,g2_both_B,g3]"] = per_draw; out["n_of_6_held"] = n_held
    out["verdict"] = "HOLDS" if n_held == 6 else "FALSIFIED"
    sev = {}
    for k, res in (("draw1", res1), ("draw2", res2)):
        s = res["severity"]
        sev[k] = {"a_rho": s["a_within_bottom191"]["P9"]["rho"], "a_range": s["a_within_bottom191"]["P9"]["range"], "a_holds": s["a_range_excludes_zero"],
                  "fifths": s["b_fifths_realized_median_lowest_to_highest"]["P9_expectedReturn"], "b_holds": s["b_lowest_fifth_below_second"]}
    sev["reading"] = ("better information" if all(v["a_holds"] and v["b_holds"] for v in sev.values() if isinstance(v, dict))
                      else "same information, better units" if not any(v["a_holds"] or v["b_holds"] for v in sev.values() if isinstance(v, dict)) else "mixed")
    out["severity"] = sev

    # ---- step 3: P9's own noise floor
    def block(rs):
        n = len(rs)
        ch = [i for i in rs if i[0]["grp"] != i[1]["grp"]]
        dec = [i for i in ch if i[0]["gt"] and ((i[0]["grp"] == i[0]["gt"]) != (i[1]["grp"] == i[1]["gt"]))]
        w = sum(i[0]["grp"] == i[0]["gt"] for i in dec)
        return {"n": n, "group_change": wil(len(ch), n),
                "er_move_ge3": wil(sum(abs(a["er"] - b["er"]) >= 3 for a, b in rs), n), "er_move_ge5": wil(sum(abs(a["er"] - b["er"]) >= 5 for a, b in rs), n),
                "noise_win_rate": {"decisive": len(dec), "draw1_right": w, "pct": round(100 * w / len(dec), 1) if dec else None,
                                   "wilson": [round(x, 1) for x in p3.wilson(w, len(dec))] if dec else None}}
    pairs = list(zip(r1, r2))
    noise = {"pooled": block(pairs), "per_stratum": {s: block([p for p in pairs if p[0]["stratum"] == s]) for s in sorted({p[0]["stratum"] for p in pairs})}}
    cats = ["bearish", "neutral", "bullish"]
    noise["table_3x3_draw1_by_draw2"] = {a: {b: sum(p[0]["grp"] == a and p[1]["grp"] == b for p in pairs) for b in cats} for a in cats}
    rows = [{"ticker": a["ticker"], "ret": a["ret"], "e1": a["er"], "e2": b["er"], "c": max(-CLIP, min(CLIP, a["ret"]))} for a, b in pairs]
    rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
    d1, d2 = rho(rows, "e1"), rho(rows, "e2")
    lo, hi, nv = A.boot(rows, lambda s: rho(s, "e1") - rho(s, "e2"))
    half = (hi - lo) / 2
    import math
    noise["rank"] = {"draw1": d1, "draw2": d2, "paired_diff_draw1_minus_draw2": d1 - d2, "range": [lo, hi], "half_width": half,
                     "inherited_tolerance": -math.ceil(round(half, 6) * 100) / 100}
    sl1, sl2 = slope([r["e1"] for r in rows], [r["c"] for r in rows]), slope([r["e2"] for r in rows], [r["c"] for r in rows])
    sdlo, sdhi, _ = A.boot(rows, lambda s: slope([r["e1"] for r in s], [r["c"] for r in s]) - slope([r["e2"] for r in s], [r["c"] for r in s]))
    noise["clipped_slope"] = {"draw1": sl1, "draw2": sl2, "diff": sl1 - sl2, "diff_range": [sdlo, sdhi]}
    noise["B_reference"] = B_REF
    out["noise_floor"] = noise
    pc, rp = noise["pooled"]["group_change"]["pct"], noise["rank"]
    out["steadier_or_shakier_than_B"] = {"group_change_pct": [pc, B_REF["group_change_pct"]], "rank_diff": [abs(rp["paired_diff_draw1_minus_draw2"]), B_REF["rank_diff"]],
                                         "half_width": [rp["half_width"], B_REF["half_width"]]}

    # ---- averaged-draw diagnostic (not a gate, not a candidate)
    rng = random.Random(11); order = list(range(1217)); rng.shuffle(order)
    avg = [{"ticker": a["ticker"], "ret": a["ret"], "gt": a["gt"], "er": (a["er"] + b["er"]) / 2, "c": max(-CLIP, min(CLIP, a["ret"]))} for a, b in pairs]
    idx = sorted(range(1217), key=lambda i: (avg[i]["er"], order[i]))[:NL]
    hitk = sum(avg[i]["gt"] == "bearish" for i in idx)
    ra = rho(avg, "er"); rlo, rhi, _ = A.boot(avg, lambda s: rho(s, "er"))
    sa = slope([r["er"] for r in avg], [r["c"] for r in avg]); slo, shi, _ = A.boot(avg, lambda s: slope([r["er"] for r in s], [r["c"] for r in s]))
    out["averaged_draw_diagnostic"] = {"label": "diagnostic — not a gate, not a candidate", "rho": ra, "rho_range": [rlo, rhi],
                                       "clipped_slope": sa, "clipped_slope_range": [slo, shi], "bottom191_hit": wil(hitk, NL),
                                       "bottom191_median_ret": round(float(np.median([avg[i]["ret"] for i in idx])), 2)}
    (S2 / "results_verdict.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
