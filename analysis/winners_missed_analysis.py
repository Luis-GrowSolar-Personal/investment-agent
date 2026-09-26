#!/usr/bin/env python3
"""
winners_missed_analysis.py -- prompts/winners-missed-analysis.md (run_id winners-missed).
Subcommands: step1 ($0), step2d (after read_labels.jsonl), step3 (after pair results). Outputs in analysis/data/run_state/winners-missed/.
Big winner: fwd_rel_ret_tradeable >= +20; big loser <= -20; else middle. Ranges: Wilson (rates), 95% ticker-block bootstrap (2,000 draws, seed 11).
Prior return (1d): stock vs SPY from the first close on/after (call date - 182 days) to the last close strictly before the call date.
"""
import sys, json
from datetime import date, timedelta
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402
from analyst_direct_scorer import PriceCache  # noqa: E402

RS = REPO / "analysis/data/run_state"
S = RS / "winners-missed"
W, L = 20.0, -20.0


def outcome(r):
    return "winner" if r >= W else "loser" if r <= L else "middle"


def wil(k, n):
    lo, hi = p3.wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "wilson": [round(lo, 1), round(hi, 1)]}


def pile(s):
    return "bearish(<=-2)" if s <= -2 else "bullish(>=+3)" if s >= 3 else "neutral(-1..+2)"


def load_rows():
    calls = A.load_calls(RS / "p6-output-format-round/calls.csv")
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    rows = []
    for c in calls:
        if c["fwd_rel_ret_tradeable"] is None or c["b_score"] is None:
            continue
        k = (c["ticker"], c["call_date"])
        rows.append({"ticker": c["ticker"], "date": c["call_date"], "stratum": c["stratum"], "tier": c["tier"], "ret": c["fwd_rel_ret_tradeable"],
                     "b1": c["b_score"], "b2": b2[k], "out": outcome(c["fwd_rel_ret_tradeable"]), "year": c["call_date"][:4]})
    return rows


def prior_ret(prices, tk, d0):
    def last_before(t):
        days = prices._data.get(t, {})
        for i in range(1, 8):
            v = days.get((d0 - timedelta(days=i)).isoformat())
            if v: return v
        return None
    p0, _ = prices.price_on_or_after(tk, d0 - timedelta(days=182))
    b0, _ = prices.price_on_or_after("SPY", d0 - timedelta(days=182))
    p1, b1 = last_before(tk), last_before("SPY")
    if not all([p0, b0, p1, b1]): return None
    return round(100 * ((p1 - p0) / p0 - (b1 - b0) / b0), 4)


def boot_median(rows, key, seed=11, B=2000):
    lo, hi, _ = A.boot(rows, lambda s: float(np.median([r[key] for r in s])), B=B, seed=seed)
    return [round(lo, 2), round(hi, 2)]


def qs(x):
    return {"n": len(x), "median": round(float(np.median(x)), 2), "middle_half": [round(float(np.percentile(x, 25)), 2), round(float(np.percentile(x, 75)), 2)]}


def step1():
    rows = load_rows()
    out = {"n": len(rows), "big_winners": sum(r["out"] == "winner" for r in rows), "big_losers": sum(r["out"] == "loser" for r in rows),
           "winner_share_of_all_calls": wil(sum(r["out"] == "winner" for r in rows), len(rows))}
    outs = ["winner", "middle", "loser"]
    for name, key in (("draw1", "b1"), ("draw2", "b2")):
        tab = {}
        for s in range(-5, 6):
            x = [r for r in rows if r[key] == s]
            if not x: continue
            tab[str(s)] = {"n": len(x), **{o: sum(r["out"] == o for r in x) for o in outs}, **{o + "_row_pct": round(100 * sum(r["out"] == o for r in x) / len(x), 1) for o in outs}}
        piles = {}
        wins = [r for r in rows if r["out"] == "winner"]
        for p in ("bearish(<=-2)", "neutral(-1..+2)", "bullish(>=+3)"):
            x = [r for r in rows if pile(r[key]) == p]
            piles[p] = {"pile_n": len(x), "winners_in_pile": wil(sum(r["out"] == "winner" for r in x), len(x)),
                        "share_of_all_winners": wil(sum(pile(r[key]) == p for r in wins), len(wins))}
        out["1a_cross_" + name] = tab; out["1b_piles_" + name] = piles
    # 1c
    def grp(rs):
        w = [r for r in rs if r["out"] == "winner"]
        return {"calls": len(rs), "winners": len(w), "winners_scored_bullish_b1": sum(r["b1"] >= 3 for r in w),
                "bullish_hit_rate_on_winners_pct": round(100 * sum(r["b1"] >= 3 for r in w) / len(w), 1) if w else None}
    out["1c_by_stratum"] = {s: grp([r for r in rows if r["stratum"] == s]) for s in sorted({r["stratum"] for r in rows})}
    out["1c_by_tier"] = {t: grp([r for r in rows if r["tier"] == t]) for t in sorted({str(r["tier"]) for r in rows})}
    out["1c_by_year"] = {y: grp([r for r in rows if r["year"] == y]) for y in sorted({r["year"] for r in rows})}
    # 1d
    prices = PriceCache(REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json")
    for r in rows:
        r["prior"] = prior_ret(prices, r["ticker"], date.fromisoformat(r["date"]))
    have = [r for r in rows if r["prior"] is not None]
    out["1d_coverage"] = {"with_prior": len(have), "missing": len(rows) - len(have), "winners_with_prior": sum(r["out"] == "winner" for r in have)}
    g = {o: [r for r in have if r["out"] == o] for o in outs}
    out["1d_prior_by_outcome"] = {o: {**qs([r["prior"] for r in g[o]]), "median_range": boot_median(g[o], "prior")} for o in outs}
    diff = out["1d_prior_by_outcome"]["winner"]["median"] - out["1d_prior_by_outcome"]["middle"]["median"]
    wr, mr = out["1d_prior_by_outcome"]["winner"]["median_range"], out["1d_prior_by_outcome"]["middle"]["median_range"]
    overlap = not (wr[1] < mr[0] or mr[1] < wr[0])
    out["1d_reading"] = {"winner_minus_middle_median": round(diff, 2), "ranges_overlap": overlap,
                         "verdict": "winners are disproportionately rebounds" if (diff <= -15 and not overlap) else "no rebound pattern"}
    bear = [r for r in have if r["b1"] <= -2]
    bw, bn = [r for r in bear if r["out"] == "winner"], [r for r in bear if r["out"] != "winner"]
    out["1d_bearish_calls"] = {"became_big_winner": {**qs([r["prior"] for r in bw]), "median_range": boot_median(bw, "prior") if len(bw) > 2 else None},
                               "did_not": {**qs([r["prior"] for r in bn]), "median_range": boot_median(bn, "prior")}}
    (S / "results_step1.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


def step3(state="winners-missed-v2"):
    """Combine first pass (raw_pairs.jsonl) and the max_tokens retry (raw_pairs_retry.jsonl); a pair's retry row replaces an unparsed first-pass row."""
    from collections import Counter
    from analyst_direct_scorer import parse_structured
    D = RS / state
    P = {p["pair"]: p for p in json.loads((D / "pairs.json").read_text())["pairs"]}
    got, cost, src = {}, 0.0, {}
    for fn in ("raw_pairs.jsonl", "raw_pairs_retry.jsonl"):
        f = D / fn
        if not f.exists(): continue
        for r in p3.read_jsonl(f):
            i = int(r["custom_id"].split("__")[1]); cost += r["cost_usd"]
            st = parse_structured(r["content"])
            if st.get("pick") in ("A", "B"):
                got[i] = st; src[i] = fn
    rows = []
    for i in sorted(P):
        if i not in got: continue
        st, p = got[i], P[i]
        rows.append({"pair": i, "ticker": p["ticker"], "days_apart": p["days_apart"], "pick": st["pick"], "A_is_winner": p["A_is_winner"],
                     "right": (st["pick"] == "A") == p["A_is_winner"], "kind": st.get("kind"), "raiseOrBeat": st.get("raiseOrBeat"), "mechanism": st.get("mechanism"), "source": src[i]})
    k = sum(r["right"] for r in rows)
    out = {"n_pairs_selected": len(P), "n_parsed": len(rows), "unparsed_pairs": sorted(set(P) - set(got)), "right": k, "chance": len(rows) / 2,
           "right_wilson": [round(x, 3) for x in p3.wilson(k, len(rows))], "cost_usd": round(cost, 4),
           "picked_A": sum(r["pick"] == "A" for r in rows), "A_was_winner": sum(r["A_is_winner"] for r in rows),
           "kinds_all": dict(Counter(r["kind"] for r in rows)), "kinds_right": dict(Counter(r["kind"] for r in rows if r["right"])),
           "kinds_wrong": dict(Counter(r["kind"] for r in rows if not r["right"])),
           "raiseOrBeat_all": dict(Counter(r["raiseOrBeat"] for r in rows)), "raiseOrBeat_right": dict(Counter(r["raiseOrBeat"] for r in rows if r["right"])),
           "right_picks_raise_beat_or_both": sum(1 for r in rows if r["right"] and r["raiseOrBeat"] in ("raise", "beat", "both")),
           "recall_flagged": sum(1 for r in rows if r["kind"] == "recall_not_in_text"), "rows": rows}
    (D / "results_step3.json").write_text(json.dumps(out, indent=1)); print(json.dumps({k_: v for k_, v in out.items() if k_ != "rows"}, indent=1))
    for r in rows: print(r["pair"], r["ticker"], "RIGHT" if r["right"] else "wrong", r["kind"], r["raiseOrBeat"], "|", r["mechanism"])


def v3():
    """winners-missed-v3 steps 2a-2d ($0). Labels: winners-missed-v3/read_labels_v3.jsonl (balance, raised, beat)."""
    from collections import Counter
    D = RS / "winners-missed-v3"
    rows = load_rows()
    lab = {(r["ticker"], r["date"]): r["parsed"] for r in p3.read_jsonl(D / "read_labels_v3.jsonl")}
    assert len(lab) == 1217
    for r in rows:
        q = lab[(r["ticker"], r["date"])]
        r["balance"], r["raised"], r["beat"] = q.get("balance"), q.get("raised"), q.get("beat")
        r["br"] = r["raised"] == "yes" and r["beat"] == "yes"
        r["grp"] = "beat_and_raise" if r["br"] else "raised_only" if r["raised"] == "yes" else "beat_only" if r["beat"] == "yes" else "neither"
    n = len(rows)
    out = {"n": n}
    dist = {f: dict(Counter(r[f] for r in rows)) for f in ("balance", "raised", "beat")}
    mx = {f: round(100 * max(v.values()) / n, 1) for f, v in dist.items()}
    stop = [f for f, v in mx.items() if v > 85]
    out["2a"] = {"distribution": dist, "max_single_value_share_pct": mx, "fields_over_85": stop, "STOP": bool(stop),
                 "v2_preflight_60": {"balance": {"outweighs": 32, "balanced": 7, "outweighed": 21}, "raised": {"yes": 16, "no": 44}, "beat": {"yes": 10, "no": 50}}}
    if stop:
        (D / "results.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1)); return
    # 2b
    nb = [r for r in rows if r["b1"] <= 2]
    W_ = [r for r in nb if r["out"] == "winner"]; R_ = [r for r in nb if r["out"] != "winner"]
    fx = {"i_balance_outweighs": lambda r: r["balance"] == "outweighs", "ii_raised_yes": lambda r: r["raised"] == "yes",
          "iii_beat_yes": lambda r: r["beat"] == "yes", "iv_beat_and_raise": lambda r: r["br"]}
    b2 = {"n_nonbullish": len(nb), "winners": len(W_), "others": len(R_)}
    for k, f in fx.items():
        def d(smp, f=f):
            w = [r for r in smp if r["out"] == "winner"]; o_ = [r for r in smp if r["out"] != "winner"]
            return 100 * (sum(map(f, w)) / len(w) - sum(map(f, o_)) / len(o_))
        lo, hi, _ = A.boot(nb, d)
        b2[k] = {"winners": wil(sum(map(f, W_)), len(W_)), "others": wil(sum(map(f, R_)), len(R_)), "diff_pts": round(d(nb), 2), "diff_range": [round(lo, 2), round(hi, 2)],
                 "excludes_zero_higher_for_winners": lo > 0}
    hits = [k for k in ("i_balance_outweighs", "ii_raised_yes", "iii_beat_yes") if b2[k]["excludes_zero_higher_for_winners"]]
    b2["reading"] = "seen and not committed" if len(hits) >= 2 else f"suggestive: {hits[0]}" if len(hits) == 1 else "not seen"
    out["2b"] = b2
    # 2c
    def gstats(g):
        if not g: return {"n": 0}
        return {"n": len(g), "big_winner": wil(sum(r["out"] == "winner" for r in g), len(g)), "big_loser": wil(sum(r["out"] == "loser" for r in g), len(g)),
                "median_ret": round(float(np.median([r["ret"] for r in g])), 2), "median_range": boot_median(g, "ret") if len(g) > 2 else None,
                "B1_score_dist": {str(k): v for k, v in sorted(Counter(r["b1"] for r in g).items())}, "B2_score_dist": {str(k): v for k, v in sorted(Counter(r["b2"] for r in g).items())},
                "B1_below_plus3": wil(sum(r["b1"] < 3 for r in g), len(g)), "B2_below_plus3": wil(sum(r["b2"] < 3 for r in g), len(g))}
    c = {gname: gstats([r for r in rows if r["grp"] == gname]) for gname in ("beat_and_raise", "raised_only", "beat_only", "neither")}
    c["all_calls"] = {"B1_below_plus3_pct": round(100 * sum(r["b1"] < 3 for r in rows) / n, 1), "B2_below_plus3_pct": round(100 * sum(r["b2"] < 3 for r in rows) / n, 1),
                      "big_winner_pct": round(100 * sum(r["out"] == "winner" for r in rows) / n, 1)}
    def dgap(smp):
        a = [r for r in smp if r["grp"] == "beat_and_raise"]; b = [r for r in smp if r["grp"] == "neither"]
        return 100 * (sum(r["out"] == "winner" for r in a) / len(a) - sum(r["out"] == "winner" for r in b) / len(b))
    lo, hi, nv = A.boot(rows, dgap)
    c["beat_and_raise_minus_neither_big_winner_rate"] = {"diff_pts": round(dgap(rows), 2), "range": [round(lo, 2), round(hi, 2)], "valid_draws": nv, "excludes_zero_higher": lo > 0}
    def dmed(smp):
        a = [r["ret"] for r in smp if r["grp"] == "beat_and_raise"]; b = [r["ret"] for r in smp if r["grp"] == "neither"]
        return float(np.median(a) - np.median(b))
    mlo, mhi, _ = A.boot(rows, dmed)
    c["median_return_beat_and_raise_minus_neither"] = {"diff": round(dmed(rows), 2), "range": [round(mlo, 2), round(mhi, 2)]}
    br = c["beat_and_raise"]
    c["B_held_back_on_beat_and_raise"] = {"B1_below_plus3_pct": br["B1_below_plus3"]["pct"], "all_calls_pct": c["all_calls"]["B1_below_plus3_pct"],
                                          "more_often_than_overall": br["B1_below_plus3"]["pct"] > c["all_calls"]["B1_below_plus3_pct"]}
    c["reading"] = "worth building" if c["beat_and_raise_minus_neither_big_winner_rate"]["excludes_zero_higher"] else "not worth building on this evidence"
    out["2c"] = c
    # 2d: v2 pairs
    P = json.loads((RS / "winners-missed-v2/pairs.json").read_text())["pairs"]
    R3 = {r["pair"]: r for r in json.loads((RS / "winners-missed-v2/results_step3.json").read_text())["rows"]}
    tag = lambda t, d_: ("raised" if lab[(t, d_)].get("raised") == "yes" else None, "beat" if lab[(t, d_)].get("beat") == "yes" else None)
    right, wrong = {"n": 0, "winner_side_raised_or_beat": 0, "raised": 0, "beat": 0}, {"n": 0, "chosen_raised_or_beat": 0, "raised": 0, "beat": 0}
    for p in P:
        if p["pair"] not in R3: continue
        if R3[p["pair"]]["right"]:
            t = tag(p["ticker"], p["winner"]["date"]); right["n"] += 1
            right["raised"] += t[0] is not None; right["beat"] += t[1] is not None; right["winner_side_raised_or_beat"] += any(t)
        else:
            t = tag(p["ticker"], p["middle"]["date"]); wrong["n"] += 1      # the chosen call in a wrong pick is the middle call
            wrong["raised"] += t[0] is not None; wrong["beat"] += t[1] is not None; wrong["chosen_raised_or_beat"] += any(t)
    out["2d"] = {"right_pick_pairs_winner_side": right, "wrong_pick_pairs_chosen_call": wrong}
    (D / "results.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    {"step1": step1, "step3": step3, "v3": v3}[sys.argv[1]]()
