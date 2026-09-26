#!/usr/bin/env python3
"""
p9_expected_return_analysis.py -- prompts/P9-expected-return.md sections 5c and 5d ($0, no model calls).
P9 groups: bottom 191 by expectedReturn = bearish, top 235 = bullish, rest neutral; ties by a seeded shuffle (seed 11) over the
priced calls in calls.csv order (same convention as b_noise_floor_analysis.py / p7_three_voices_analysis.py).
'Right' = direction equals gt_old_ruler (tradeable-entry 182-day ruler). Ranges: Wilson (rates), 95% ticker-block bootstrap (2,000 draws, seed 11).
Slope = OLS slope of realized return (clipped at +/-50 for the gate; unclipped beside it) on expectedReturn.
"""
import sys, json, csv, random
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402

RS = REPO / "analysis/data/run_state"
ORIG, B2, STATE = RS / "p6-output-format-round", RS / "b-champion-and-noise-floor", RS / "p9-expected-return-train"
NB, NL = 235, 191
B_NOISE_WIN = 0.554        # b-champion-and-noise-floor results.json pooled.noise_win_rate.pct
CLIP = 50.0


def d3(s):
    return None if s is None else "bearish" if s <= -2 else "bullish" if s >= 3 else "neutral"


def med(x):
    return round(float(np.median(x)), 2) if len(x) else None


def num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def slope(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or x.std() == 0:
        return float("nan")
    return float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())


def main():
    calls = A.load_calls(ORIG / "calls.csv")
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(B2 / "scores_rerun1.jsonl".replace("scores_rerun1", "scores_b_rerun1"))}
    p9 = {}
    for r in p3.read_jsonl(STATE / "scores_p9.jsonl"):
        st = A.parse_structured(r["content"])
        p9[(r["ticker"], r["date"])] = {"er": num(st.get("expectedReturn")), "lo": num(st.get("rangeLow")), "hi": num(st.get("rangeHigh")),
                                        "nr": st.get("noRead"), "tok": r["usage"]["output_tokens"], "cost": r["cost_usd"], "stop": r["stop_reason"]}
    assert len(p9) == 1217, len(p9)
    rows = []
    for c in calls:
        k = (c["ticker"], c["call_date"]); q = p9[k]
        rows.append({**c, "b1": c["b_score"], "b2": b2[k], "er": q["er"], "lo": q["lo"], "hi": q["hi"], "nr9": q["nr"], "tok": q["tok"],
                     "cost": q["cost"], "stop": q["stop"], "year": c["call_date"][:4]})
    out = {"n": len(rows), "unparsed": sum(r["er"] is None for r in rows), "max_tokens": sum(r["stop"] == "max_tokens" for r in rows),
           "range_order_broken": sum(1 for r in rows if None in (r["er"], r["lo"], r["hi"]) or not (r["lo"] <= r["er"] <= r["hi"]))}
    priced = [r for r in rows if None not in (r["er"], r["b1"], r["b2"], r["fwd_rel_ret_tradeable"])]
    assert len(priced) == 1217, len(priced)
    ret = lambda r: r["fwd_rel_ret_tradeable"]
    rng = random.Random(11); order = list(range(len(priced))); rng.shuffle(order)

    def pick(key, n, sign, rs=None, od=None):
        rs = priced if rs is None else rs
        idx = sorted(range(len(rs)), key=lambda i: (sign * rs[i][key], order[i] if od is None else od[i]))[:n]
        return [rs[i] for i in idx]

    def hit(rs, want):
        g = [r for r in rs if r["gt_old_ruler"]]
        k = sum(r["gt_old_ruler"] == want for r in g)
        return {"n": len(rs), "graded": len(g), "hit_pct": round(100 * k / len(g), 1) if g else None,
                "hit_wilson": [round(x, 1) for x in p3.wilson(k, len(g))] if g else None, "median_ret": med([ret(r) for r in rs])}
    rho = lambda rs, k: A.spearman([r[k] for r in rs], [ret(r) for r in rs])

    # groups
    bot9, top9 = pick("er", NL, 1), pick("er", NB, -1)
    key = lambda rs: {(r["ticker"], r["call_date"]) for r in rs}
    bset, tset = key(bot9), key(top9)
    grp9 = {(r["ticker"], r["call_date"]): ("bearish" if (r["ticker"], r["call_date"]) in bset else "bullish" if (r["ticker"], r["call_date"]) in tset else "neutral") for r in priced}

    # gate 1: calibration sign
    cl = lambda v: max(-CLIP, min(CLIP, v))
    for r in priced: r["retc"] = cl(ret(r))
    sl_c = slope([r["er"] for r in priced], [r["retc"] for r in priced])
    sl_u = slope([r["er"] for r in priced], [ret(r) for r in priced])
    lo_c, hi_c, _ = A.boot(priced, lambda s: slope([r["er"] for r in s], [r["retc"] for r in s]))
    lo_u, hi_u, _ = A.boot(priced, lambda s: slope([r["er"] for r in s], [ret(r) for r in s]))
    out["calibration"] = {"slope_clipped": sl_c, "range_clipped": [lo_c, hi_c], "slope_unclipped": sl_u, "range_unclipped": [lo_u, hi_u], "clip": CLIP,
                          "n_clipped": sum(abs(ret(r)) > CLIP for r in priced), "gate1_holds": lo_c > 0}
    # gate 2 / rank
    cov = {}
    for name, k in (("P9", "er"), ("B_draw1", "b1"), ("B_draw2", "b2")):
        cov[name] = {"rho": rho(priced, k), "rho_range": A.boot(priced, lambda s, kk=k: rho(s, kk))[:2]}
    g2 = {}
    for name, k in (("draw1", "b1"), ("draw2", "b2")):
        lo, hi, _ = A.boot(priced, lambda s, kk=k: rho(s, "er") - rho(s, kk))
        g2[name] = {"paired_rho_diff": rho(priced, "er") - rho(priced, k), "range": [lo, hi], "gate2_holds": lo >= -0.03}
    bt = {"P9": hit(bot9, "bearish"), "B_draw1": hit(pick("b1", NL, 1), "bearish"), "B_draw2": hit(pick("b2", NL, 1), "bearish")}
    tp = {"P9": hit(top9, "bullish"), "B_draw1": hit(pick("b1", NB, -1), "bullish"), "B_draw2": hit(pick("b2", NB, -1), "bullish")}
    g3 = bt["P9"]["hit_pct"]
    out["rank"] = cov; out["bottom191"] = bt; out["top235_not_gated"] = tp
    out["gates"] = {"gate1_calibration_sign_holds": out["calibration"]["gate1_holds"], "gate2": g2,
                    "gate2_holds_both_draws": all(v["gate2_holds"] for v in g2.values()),
                    "gate3_bottom191_hit_pct": g3, "gate3_holds": g3 >= 57.0}
    out["gates"]["n_gates_held_against_both"] = sum([out["gates"]["gate1_calibration_sign_holds"], out["gates"]["gate2_holds_both_draws"], out["gates"]["gate3_holds"]])
    out["ambiguity"] = {"gates_1_and_3_hold": out["calibration"]["gate1_holds"] and g3 >= 57.0,
                        "gate2_lower_ends": [round(v["range"][0], 4) for v in g2.values()],
                        "any_lower_end_in_-0.06_0.00": any(-0.06 <= v["range"][0] <= 0.0 for v in g2.values())}
    out["ambiguity"]["triggered"] = out["ambiguity"]["gates_1_and_3_hold"] and out["ambiguity"]["any_lower_end_in_-0.06_0.00"]

    # severity (a): rank correlation inside the bottom 191
    def within(rs, k): return A.spearman([r[k] for r in rs], [ret(r) for r in rs])
    sev = {}
    sev["P9"] = {"rho": within(bot9, "er"), "range": A.boot(bot9, lambda s: within(s, "er"))[:2]}
    for name, k in (("B_draw1", "b1"), ("B_draw2", "b2")):
        bb = pick(k, NL, 1)
        sev[name] = {"rho": within(bb, k), "range": A.boot(bb, lambda s, kk=k: within(s, kk))[:2], "distinct_scores_in_group": len({r[k] for r in bb})}
    # (b) fifths, ties broken by the same seeded order
    def fifths(key):
        idx = sorted(range(len(priced)), key=lambda i: (priced[i][key], order[i]))
        return [med([ret(priced[i]) for i in ch]) for ch in np.array_split(idx, 5)]
    fif = {"P9_expectedReturn": fifths("er"), "B_draw1_score": fifths("b1"), "B_draw2_score": fifths("b2")}
    a_ok = sev["P9"]["range"][0] > 0 or sev["P9"]["range"][1] < 0
    b_ok = fif["P9_expectedReturn"][0] < fif["P9_expectedReturn"][1]
    out["severity"] = {"a_within_bottom191": sev, "b_fifths_realized_median_lowest_to_highest": fif,
                       "a_range_excludes_zero": bool(a_ok), "b_lowest_fifth_below_second": bool(b_ok),
                       "reading": "grades severity" if a_ok and b_ok else "same information, better units" if not a_ok and not b_ok else "mixed (only one holds)"}

    # range coverage and width vs error
    cov_in = [r["lo"] <= ret(r) <= r["hi"] for r in priced]
    out["range_coverage"] = {"inside_pct": round(100 * sum(cov_in) / len(cov_in), 1), "asked_pct": 80,
                             "width_vs_abs_error_rho": A.spearman([r["hi"] - r["lo"] for r in priced], [abs(ret(r) - r["er"]) for r in priced]),
                             "median_width": med([r["hi"] - r["lo"] for r in priced])}
    # flips vs B (direction from P9 groups), raw and net
    nres = json.loads((B2 / "results.json").read_text())
    def flips(key):
        d = lambda r: grp9[(r["ticker"], r["call_date"])]
        fl = [r for r in priced if d(r) != d3(r[key])]
        n_s = {}
        for r in priced: n_s[r["stratum"]] = n_s.get(r["stratum"], 0) + 1
        exp = sum(n * nres["per_stratum"][s]["direction_change"]["pct"] / 100 for s, n in n_s.items())
        hi = nres["pooled"]["direction_change"]["wilson"][1] / 100 * len(priced)
        gr = [r for r in fl if r["gt_old_ruler"] and ((d(r) == r["gt_old_ruler"]) != (d3(r[key]) == r["gt_old_ruler"]))]
        wins = sum(d(r) == r["gt_old_ruler"] for r in gr)
        net = len(fl) - exp; guard = net > 100 and net > hi
        ng = exp * len(gr) / max(len(fl), 1)
        netted = (wins - ng * B_NOISE_WIN) / (len(gr) - ng) * 100 if len(gr) - ng > 0 else None
        return {"raw": len(fl), "raw_pct": round(100 * len(fl) / len(priced), 1), "expected_noise_flips": round(exp, 1), "noise_upper": round(hi, 1),
                "net": round(net, 1), "decisive_flips": len(gr), "p9_wins": wins, "raw_win_rate_pct": round(100 * wins / max(len(gr), 1), 1),
                "guard_passed": guard, "netted_win_rate_pct": None if netted is None else round(netted, 1),
                "netted_label": "reportable" if guard else "UNSTABLE, not a headline"}
    out["flips"] = {"vs_B_draw1": flips("b1"), "vs_B_draw2": flips("b2")}
    cats = ["bearish", "neutral", "bullish"]
    out["table_3x3_B1_by_P9_groups"] = {a: {b: sum(d3(r["b1"]) == a and grp9[(r["ticker"], r["call_date"])] == b for r in priced) for b in cats} for a in cats}
    out["table_3x3_B2_by_P9_groups"] = {a: {b: sum(d3(r["b2"]) == a and grp9[(r["ticker"], r["call_date"])] == b for r in priced) for b in cats} for a in cats}
    # distribution
    ers = np.array([r["er"] for r in priced]); rets = np.array([ret(r) for r in priced])
    from collections import Counter
    out["distribution"] = {"median": float(np.median(ers)), "middle_half": [float(np.percentile(ers, 25)), float(np.percentile(ers, 75))],
                           "middle_half_span": float(np.percentile(ers, 75) - np.percentile(ers, 25)), "share_positive_pct": round(100 * float((ers > 0).mean()), 1),
                           "share_negative_pct": round(100 * float((ers < 0).mean()), 1), "top10_values": Counter(ers.tolist()).most_common(10),
                           "distinct": len(set(ers.tolist())), "realized_middle_half_span": float(np.percentile(rets, 75) - np.percentile(rets, 25)),
                           "realized_median": float(np.median(rets))}
    out["per_stratum"] = {s: {"n": len(x), "rho": rho(x, "er"), "rho_B1": rho(x, "b1"), "median_er": float(np.median([r["er"] for r in x]))}
                          for s in sorted({r["stratum"] for r in priced}) for x in [[r for r in priced if r["stratum"] == s]]}
    yr = lambda r: "2020" if r["year"] == "2020" else "ex-2020"
    out["by_year"] = {y: {"n": len(x), "rho_P9": rho(x, "er"), "rho_B1": rho(x, "b1"), "rho_B2": rho(x, "b2")} for y in ("2020", "ex-2020") for x in [[r for r in priced if yr(r) == y]]}
    nr = lambda k: sum(bool(r[k]) for r in priced)
    out["noRead"] = {"P9": nr("nr9"), "B_draw1": nr("b_noRead"), "n": len(priced)}
    out["tokens_cost"] = {"P9_median_tokens": float(np.median([r["tok"] for r in rows])), "P9_cost_per_call": round(sum(r["cost"] for r in rows) / len(rows), 5),
                          "P9_total_usd": round(sum(r["cost"] for r in rows), 2), "B_cost_per_call_rerun": 0.0236}
    d = out["distribution"]
    out["predictions"] = {"median_er_2_to_8": [d["median"], 2 <= d["median"] <= 8], "share_positive_55_75": [d["share_positive_pct"], 55 <= d["share_positive_pct"] <= 75],
                          "middle_half_6_15": [d["middle_half_span"], 6 <= d["middle_half_span"] <= 15],
                          "slope_clipped_0.2_0.6": [sl_c, 0.2 <= sl_c <= 0.6], "coverage_50_70": [out["range_coverage"]["inside_pct"], 50 <= out["range_coverage"]["inside_pct"] <= 70],
                          "rho_0.10_0.15": [cov["P9"]["rho"], 0.10 <= cov["P9"]["rho"] <= 0.15],
                          "cost_within_15pct_of_B": [out["tokens_cost"]["P9_cost_per_call"], abs(out["tokens_cost"]["P9_cost_per_call"] / 0.0236 - 1) <= 0.15]}
    with (STATE / "per_call_diffs.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["ticker", "call_date", "stratum", "ret", "gt", "b1", "b2", "expectedReturn", "rangeLow", "rangeHigh", "p9_group", "b1_dir", "b2_dir"])
        for r in priced:
            w.writerow([r["ticker"], r["call_date"], r["stratum"], ret(r), r["gt_old_ruler"], r["b1"], r["b2"], r["er"], r["lo"], r["hi"], grp9[(r["ticker"], r["call_date"])], d3(r["b1"]), d3(r["b2"])])
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
