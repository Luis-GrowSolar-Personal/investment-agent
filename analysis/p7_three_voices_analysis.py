#!/usr/bin/env python3
"""
p7_three_voices_analysis.py -- prompts/P7-three-voices.md sections 5c and 5e ($0, no model calls).
P7 scores (run p7-three-voices-train/scores_p7.jsonl) against B draw 1 (p6-output-format-round calls.csv b_score) and
B draw 2 (b-champion-and-noise-floor/scores_b_rerun1.jsonl). Helpers reused from p6_output_format_analysis.
Mapping <= -2 bearish, >= +3 bullish. 'Right'/hit = direction equals gt_old_ruler (tradeable-entry 182-day ruler).
Top-235 / bottom-191 ties broken by a seeded shuffle (seed 11) over the priced calls in calls.csv order, as in b_noise_floor_analysis.py.
Ranges: Wilson (rates), 95% ticker-block bootstrap 2,000 draws seed 11.
"""
import sys, json, csv, random
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402

RS = REPO / "analysis/data/run_state"
ORIG, B2, STATE = RS / "p6-output-format-round", RS / "b-champion-and-noise-floor", RS / "p7-three-voices-train"
NB, NL = 235, 191
B_NOISE_WIN = 0.554        # b-champion-and-noise-floor results.json pooled.noise_win_rate.pct
D = {"bearish": -1, "neutral": 0, "bullish": 1}


def d3(s):
    return None if s is None else "bearish" if s <= -2 else "bullish" if s >= 3 else "neutral"


def med(x):
    return round(float(np.median(x)), 2) if len(x) else None


def wil(k, n):
    lo, hi = p3.wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "wilson": [round(lo, 1), round(hi, 1)]}


def main():
    calls = A.load_calls(ORIG / "calls.csv")
    b2 = {}
    for r in p3.read_jsonl(B2 / "scores_b_rerun1.jsonl"):
        b2[(r["ticker"], r["date"])] = A.parse_score(r["content"])[1]
    p7 = {}
    for r in p3.read_jsonl(STATE / "scores_p7.jsonl"):
        st = A.parse_structured(r["content"])
        s = st.get("score")
        s = s if isinstance(s, int) and not isinstance(s, bool) and -5 <= s <= 5 else None
        p7[(r["ticker"], r["date"])] = {"s": s, "nr": st.get("noRead"), "gap": st.get("gap"), "pr": st.get("pressure"),
                                        "tok": r["usage"]["output_tokens"], "cost": r["cost_usd"], "stop": r["stop_reason"]}
    assert len(p7) == 1217, len(p7)
    rows = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        q = p7[k]
        rows.append({**c, "b1": c["b_score"], "b2": b2[k], "p7": q["s"], "gap": q["gap"], "pr": q["pr"], "nr7": q["nr"],
                     "tok": q["tok"], "cost": q["cost"], "stop": q["stop"], "year": c["call_date"][:4]})
    out = {"n": len(rows), "unparsed": sum(r["p7"] is None for r in rows), "max_tokens": sum(r["stop"] == "max_tokens" for r in rows),
           "bad_gap": sum(r["gap"] not in ("numbers_ahead", "aligned", "claims_ahead") for r in rows),
           "bad_pressure": sum(r["pr"] not in ("answered", "avoided", "none") for r in rows)}
    ok = [r for r in rows if None not in (r["p7"], r["b1"], r["b2"])]
    priced = [r for r in ok if r["fwd_rel_ret_tradeable"] is not None]
    assert len(priced) == 1217, len(priced)
    rng = random.Random(11)
    order = list(range(len(priced))); rng.shuffle(order)

    def pick(key, n, sign):
        idx = sorted(range(len(priced)), key=lambda i: (sign * priced[i][key], order[i]))[:n]
        return [priced[i] for i in idx]

    def hit(rs, want):
        g = [r for r in rs if r["gt_old_ruler"]]
        return {"n": len(rs), "graded": len(g), "hit_pct": round(100 * sum(r["gt_old_ruler"] == want for r in g) / len(g), 1) if g else None,
                "hit_wilson": [round(x, 1) for x in p3.wilson(sum(r["gt_old_ruler"] == want for r in g), len(g))] if g else None,
                "median_ret": med([r["fwd_rel_ret_tradeable"] for r in rs])}
    base_bull = round(100 * sum(r["gt_old_ruler"] == "bullish" for r in priced) / sum(1 for r in priced if r["gt_old_ruler"]), 1)
    base_bear = round(100 * sum(r["gt_old_ruler"] == "bearish" for r in priced) / sum(1 for r in priced if r["gt_old_ruler"]), 1)
    out["base_rates_pct"] = {"bullish": base_bull, "bearish": base_bear}

    def rho(rs, k):
        return A.spearman([r[k] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs])
    gates, cov = {}, {}
    for name, key in (("P7", "p7"), ("B_draw1", "b1"), ("B_draw2", "b2")):
        cov[name] = {"top235": hit(pick(key, NB, -1), "bullish"), "bottom191": hit(pick(key, NL, 1), "bearish"),
                     "rho": rho(priced, key), "rho_range": A.boot(priced, lambda s, k=key: rho(s, k))[:2]}
    out["matched_coverage"] = cov
    for name, key in (("draw1", "b1"), ("draw2", "b2")):
        lo, hi, _ = A.boot(priced, lambda s, k=key: rho(s, "p7") - rho(s, k))
        gates[name] = {"paired_rho_diff": rho(priced, "p7") - rho(priced, key), "range": [lo, hi],
                       "gate2_holds": lo >= -0.03}
    g1, g3 = cov["P7"]["top235"]["hit_pct"], cov["P7"]["bottom191"]["hit_pct"]
    out["gates"] = {"gate1_top235_hit_pct": g1, "gate1_holds_both_draws": g1 >= 47.0,
                    "gate1_note": "absolute target, so identical against both draws; B's own: draw1 %s, draw2 %s" % (cov["B_draw1"]["top235"]["hit_pct"], cov["B_draw2"]["top235"]["hit_pct"]),
                    "gate2": gates, "gate2_holds_both_draws": all(v["gate2_holds"] for v in gates.values()),
                    "gate3_bottom191_hit_pct": g3, "gate3_holds_both_draws": g3 >= 57.0}
    out["gates"]["n_gates_held_against_both"] = sum([out["gates"]["gate1_holds_both_draws"], out["gates"]["gate2_holds_both_draws"], out["gates"]["gate3_holds_both_draws"]])
    out["ambiguity_5d"] = {"gate1_in_43.6_50.4": 43.6 <= g1 <= 50.4,
                           "gate2_lower_end_in_-0.06_0.00": [round(v["range"][0], 4) for v in gates.values()],
                           "gate2_any_in_band": any(-0.06 <= v["range"][0] <= 0.0 for v in gates.values())}

    # flips vs each B draw, raw and net of B's per-stratum noise rate
    nres = json.loads((B2 / "results.json").read_text())
    def flips(key):
        fl = [r for r in ok if d3(r["p7"]) != d3(r[key])]
        n_s = {}
        for r in ok: n_s[r["stratum"]] = n_s.get(r["stratum"], 0) + 1
        exp = sum(n * nres["per_stratum"][s]["direction_change"]["pct"] / 100 for s, n in n_s.items())
        hi = nres["pooled"]["direction_change"]["wilson"][1] / 100 * len(ok)
        gr = [r for r in fl if r["gt_old_ruler"] and ((d3(r["p7"]) == r["gt_old_ruler"]) != (d3(r[key]) == r["gt_old_ruler"]))]
        wins = sum(d3(r["p7"]) == r["gt_old_ruler"] for r in gr)
        net = len(fl) - exp
        guard = net > 100 and net > hi
        ng = len(fl) and exp * len(gr) / len(fl)
        netted = (wins - ng * B_NOISE_WIN) / (len(gr) - ng) * 100 if len(gr) - ng > 0 else None
        return {"raw": len(fl), "raw_pct": round(100 * len(fl) / len(ok), 1), "expected_noise_flips": round(exp, 1), "noise_upper": round(hi, 1),
                "net": round(net, 1), "decisive_flips": len(gr), "p7_wins": wins, "raw_win_rate_pct": round(100 * wins / max(len(gr), 1), 1),
                "guard_passed": guard, "netted_win_rate_pct": None if netted is None else round(netted, 1),
                "netted_label": "reportable" if guard else "UNSTABLE, not a headline"}
    out["flips"] = {"vs_B_draw1": flips("b1"), "vs_B_draw2": flips("b2")}
    cats = ["bearish", "neutral", "bullish"]
    out["table_3x3_B1_by_P7"] = {a: {b: sum(d3(r["b1"]) == a and d3(r["p7"]) == b for r in ok) for b in cats} for a in cats}
    out["table_3x3_B2_by_P7"] = {a: {b: sum(d3(r["b2"]) == a and d3(r["p7"]) == b for r in ok) for b in cats} for a in cats}

    # the group that matters
    top7 = {(r["ticker"], r["call_date"]) for r in pick("p7", NB, -1)}
    for name, key in (("draw1", "b1"), ("draw2", "b2")):
        topb = {(r["ticker"], r["call_date"]) for r in pick(key, NB, -1)}
        neu = [r for r in priced if -1 <= r[key] <= 2 and (r["ticker"], r["call_date"]) in top7]
        drop = [r for r in priced if (r["ticker"], r["call_date"]) in topb and (r["ticker"], r["call_date"]) not in top7]
        out.setdefault("neutral_to_top235", {})[name] = {"B_neutral_-1_to_+2_that_P7_put_in_top235": hit(neu, "bullish"),
                                                        "B_top235_that_P7_dropped": hit(drop, "bullish"), "bullish_base_rate_pct": base_bull,
                                                        "top235_shared": len(top7 & topb)}
    # gap and gap x pressure (hit = bullish truth; also bearish truth rate); over all calls
    def cell(rs):
        g = [r for r in rs if r["gt_old_ruler"]]
        return {"n": len(rs), "bullish_hit_pct": round(100 * sum(r["gt_old_ruler"] == "bullish" for r in g) / len(g), 1) if g else None,
                "bearish_rate_pct": round(100 * sum(r["gt_old_ruler"] == "bearish" for r in g) / len(g), 1) if g else None,
                "median_ret": med([r["fwd_rel_ret_tradeable"] for r in rs if r["fwd_rel_ret_tradeable"] is not None]),
                "mean_score": round(float(np.mean([r["p7"] for r in rs])), 2) if rs else None}
    gv, pv = ["numbers_ahead", "aligned", "claims_ahead"], ["answered", "avoided", "none"]
    out["by_gap"] = {g: cell([r for r in ok if r["gap"] == g]) for g in gv}
    out["by_pressure"] = {p: cell([r for r in ok if r["pr"] == p]) for p in pv}
    out["gap_x_pressure"] = {g: {p: cell([r for r in ok if r["gap"] == g and r["pr"] == p]) for p in pv} for g in gv}
    out["shares_pct"] = {"gap": {g: round(100 * sum(r["gap"] == g for r in ok) / len(ok), 1) for g in gv},
                         "pressure": {p: round(100 * sum(r["pr"] == p for r in ok) / len(ok), 1) for p in pv}}
    # secondary fixed cuts, buckets
    out["fixed_cuts_secondary"] = {"ge3": {**hit([r for r in priced if r["p7"] >= 3], "bullish"), "n_calls": sum(r["p7"] >= 3 for r in priced)},
                                   "le-2": {**hit([r for r in priced if r["p7"] <= -2], "bearish"), "n_calls": sum(r["p7"] <= -2 for r in priced)}}
    out["buckets"] = {str(s): {"n": len(x), "median": med([r["fwd_rel_ret_tradeable"] for r in x]),
                               "mean": round(float(np.mean([r["fwd_rel_ret_tradeable"] for r in x])), 2)}
                      for s in range(-5, 6) for x in [[r for r in priced if r["p7"] == s]] if x}
    out["per_stratum"] = {s: {"n": len(x), "rho": rho(x, "p7"), "rho_B1": rho(x, "b1"), "direction_change_vs_B1_pct": round(100 * sum(d3(r["p7"]) != d3(r["b1"]) for r in x) / len(x), 1)}
                          for s in sorted({r["stratum"] for r in priced}) for x in [[r for r in priced if r["stratum"] == s]]}
    yr = lambda r: r["year"] if r["year"] == "2020" else "ex-2020"
    out["by_year"] = {y: {"n": len(x), "rho_P7": rho(x, "p7"), "rho_B1": rho(x, "b1"), "rho_B2": rho(x, "b2")}
                      for y in ("2020", "ex-2020") for x in [[r for r in priced if yr(r) == y]]}
    out["noRead"] = {"P7": wil(sum(bool(r["nr7"]) for r in ok), len(ok)), "B_draw1": wil(sum(bool(r["b_noRead"]) for r in ok), len(ok))}
    out["tokens_cost"] = {"P7_median_tokens": float(np.median([r["tok"] for r in rows])), "P7_cost_per_call": round(sum(r["cost"] for r in rows) / len(rows), 5),
                          "P7_total_usd": round(sum(r["cost"] for r in rows), 2), "B_cost_per_call_rerun": 0.0236}
    out["predictions"] = {"top235_median_above_+1.28_both": [cov["P7"]["top235"]["median_ret"], cov["P7"]["top235"]["median_ret"] > 1.28],
                          "rho_0.12_0.17": [cov["P7"]["rho"], 0.12 <= cov["P7"]["rho"] <= 0.17]}
    with (STATE / "per_call_diffs.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["ticker", "call_date", "stratum", "ret", "gt", "b1", "b2", "p7", "gap", "pressure", "b1_dir", "b2_dir", "p7_dir"])
        for r in rows:
            w.writerow([r["ticker"], r["call_date"], r["stratum"], r["fwd_rel_ret_tradeable"], r["gt_old_ruler"], r["b1"], r["b2"], r["p7"], r["gap"], r["pr"], d3(r["b1"]), d3(r["b2"]), d3(r["p7"])])
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
