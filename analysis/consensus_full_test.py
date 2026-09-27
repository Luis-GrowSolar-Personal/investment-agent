#!/usr/bin/env python3
"""
consensus_full_test.py -- prompts/consensus-surprise-test.md Steps 2-3 + full-test review amendments A-F ($0). Matches all 57 train companies' calls
(excluding FRC/MAXNQ/SUNW/PARA -- empty or corrupt-price-excluded) to AV EARNINGS quarters (+-3 days), computes SUE_p, quarter-adjusted SUE_p (median
across ALL matched calls in that calendar quarter, corpus-wide), and sector-quarter-adjusted SUE_p (>=5 calls else fall back to quarter median).
PRIMARY (review amendment A): among calls B scored >=0 (mean of two draws), rank correlation of quarter-adjusted surprise with the 182-day return.
Conditions B(a) unscreened-companies check, B(b) leave-one-year-out. Everything else (items 1-6, screen amendments 1-6) reported only.
"""
import sys, json, csv
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p6_output_format_analysis as A
import p3_guidance_ledger_driver as p3
from analyst_direct_scorer import PriceCache
REPO = Path(__file__).resolve().parent.parent
EV = REPO / "analysis/data/evals/consensus_av"
STATE = REPO / "analysis/data/run_state/consensus-surprise"
D_ = date.fromisoformat
EXCLUDE = {"FRC", "MAXN", "MAXNQ", "SUNW", "VIAC", "PARA"}
SCREENED_20 = {"LLY", "MU", "EOSE", "NEM", "PSX", "OXY", "COF", "HCA", "NOW", "AMPX", "MRK", "QCOM", "TMO", "INTC", "JKS", "TTD", "RUN", "DD", "JPM", "WMB"}
FLAGGED = {"EOSE", "JKS", "RUN"}


def prev_close(prices, tk, d):
    days = prices._data.get(tk, {})
    for i in range(1, 10):
        k = (d - timedelta(days=i)).isoformat()
        if k in days: return days[k], D_(k)
    return None, None


def qtr(dstr):
    y, m = int(dstr[:4]), int(dstr[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def rho(rs, k, ret="ret"): return A.spearman([r[k] for r in rs], [r[ret] for r in rs])


def main():
    prices = PriceCache(REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json")
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    am = p3.alias_map()
    companies = sorted({am.get(t, t) for t in json.loads((REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text())["train"]} - EXCLUDE)
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["ticker"] in companies and c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(REPO / "analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl")}

    aq = {}
    for tk in companies:
        f = EV / f"{tk}.json"
        d = json.loads(f.read_text()) if f.exists() else {}
        aq[tk] = sorted(d.get("quarterlyEarnings", []), key=lambda r: r.get("fiscalDateEnding", ""))

    matched, unmatched = [], []
    for c in calls:
        tk, td = c["ticker"], c["call_date"]; cd = D_(td)
        best = None; best_dist = 4; best_i = None
        for i, q in enumerate(aq[tk]):
            rd = q.get("reportedDate")
            if not rd: continue
            dist = abs((D_(rd) - cd).days)
            if dist <= 3 and dist < best_dist: best, best_dist, best_i = q, dist, i
        if best is None: unmatched.append({"ticker": tk, "date": td, "reason": "no AV quarter within 3 days"}); continue
        rep, est = num(best.get("reportedEPS")), num(best.get("estimatedEPS"))
        if rep is None or est is None: unmatched.append({"ticker": tk, "date": td, "reason": "missing EPS"}); continue
        p0, dd0 = prev_close(prices, tk, cd)
        if p0 is None or p0 == 0: unmatched.append({"ticker": tk, "date": td, "reason": "no price"}); continue
        entry, entry_d = prices.price_on_or_after(tk, cd + timedelta(days=1))
        if entry_d is None or entry_d <= dd0: unmatched.append({"ticker": tk, "date": td, "reason": "overlap or no entry"}); continue
        sue_p = 100 * (rep - est) / p0
        prev_q = aq[tk][best_i - 1] if best_i > 0 else None
        pers = None
        if prev_q:
            pr, pe = num(prev_q.get("reportedEPS")), num(prev_q.get("estimatedEPS"))
            if pr is not None and pe is not None: pers = (rep > est) and (pr > pe)
        matched.append({"ticker": tk, "date": td, "group": smap.get(tk, "other"), "year": td[:4], "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"],
                        "own": (c["b_score"] + b2[(tk, td)]) / 2, "sue_p": sue_p, "beat": rep > est, "surprise_pct": num(best.get("surprisePercentage")),
                        "reportedDate": best.get("reportedDate"), "quarter": qtr(best.get("fiscalDateEnding", "1970-01")), "persistence": pers,
                        "screened": tk in SCREENED_20, "flagged": tk in FLAGGED, "price": p0, "est_pct_of_price": abs(est) / p0 * 100 if p0 else None})

    byq = defaultdict(list)
    for r in matched: byq[r["quarter"]].append(r["sue_p"])
    qmed = {q: float(np.median(v)) for q, v in byq.items()}
    for r in matched: r["sue_p_adj"] = r["sue_p"] - qmed[r["quarter"]]; r["n_in_quarter"] = len(byq[r["quarter"]])

    bysq = defaultdict(list)
    for r in matched: bysq[(r["group"], r["quarter"])].append(r["sue_p"])
    fallback_count = 0
    for r in matched:
        key = (r["group"], r["quarter"])
        if len(bysq[key]) >= 5: r["sue_p_sector_adj"] = r["sue_p"] - float(np.median(bysq[key])); r["sector_fallback"] = False
        else: r["sue_p_sector_adj"] = r["sue_p_adj"]; r["sector_fallback"] = True; fallback_count += 1

    out = {"n_train_calls_57co": len(calls), "n_matched": len(matched), "match_rate_pct": round(100 * len(matched) / len(calls), 1), "n_unmatched": len(unmatched),
           "unmatched_sample": unmatched[:20], "n_companies": len(companies), "n_screened_reused": sum(1 for r in matched if r["screened"]),
           "sector_quarter_fallback_count": fallback_count, "sector_quarter_fallback_pct": round(100 * fallback_count / len(matched), 1)}

    # PRIMARY: among B >= 0 calls
    prim = [r for r in matched if r["own"] >= 0]
    v = rho(prim, "sue_p_adj"); lo, hi, _ = A.boot(prim, lambda s: rho(s, "sue_p_adj"))
    out["primary"] = {"n": len(prim), "rho": v, "range": [lo, hi], "n_B_ge0_of_matched": len(prim)}
    passes_primary = lo > 0
    out["primary"]["passes"] = passes_primary

    # direction check: top19% by combined vs top19% by B alone, within B>=0, paired big-winner share
    def pct_rank(vals):
        order = np.argsort(np.argsort(vals)); return order / (len(vals) - 1) if len(vals) > 1 else np.zeros(len(vals))
    pr_s = pct_rank([r["sue_p_adj"] for r in prim]); pr_o = pct_rank([r["own"] for r in prim])
    for i, r in enumerate(prim): r["combined"] = (pr_s[i] + pr_o[i]) / 2
    n19 = max(1, round(0.19 * len(prim)))
    top_c = sorted(prim, key=lambda r: -r["combined"])[:n19]; top_b = sorted(prim, key=lambda r: -r["own"])[:n19]
    wc = round(100 * sum(r["ret"] >= 20 for r in top_c) / n19, 1); wb = round(100 * sum(r["ret"] >= 20 for r in top_b) / n19, 1)
    def diffstat(s):
        sp = pct_rank([r["sue_p_adj"] for r in s]); op = pct_rank([r["own"] for r in s])
        for i, r in enumerate(s): r["_c"] = (sp[i] + op[i]) / 2
        n_ = max(1, round(0.19 * len(s)))
        tc = sorted(s, key=lambda r: -r["_c"])[:n_]; tb = sorted(s, key=lambda r: -r["own"])[:n_]
        return 100 * sum(r["ret"] >= 20 for r in tc) / n_ - 100 * sum(r["ret"] >= 20 for r in tb) / n_
    lo_d, hi_d, _ = A.boot(prim, diffstat)
    out["direction_check"] = {"top19_combined_winner_pct": wc, "top19_B_winner_pct": wb, "diff": wc - wb, "diff_range": [lo_d, hi_d], "n19": n19}

    # B(a) unscreened check
    unscreened = [r for r in prim if not r["screened"]]
    if unscreened:
        vu = rho(unscreened, "sue_p_adj"); lou, hiu, _ = A.boot(unscreened, lambda s: rho(s, "sue_p_adj"))
        out["condition_a_unscreened"] = {"n": len(unscreened), "rho": vu, "range": [lou, hiu], "positive_point_estimate": vu > 0}
    else:
        out["condition_a_unscreened"] = None
    cond_a = out["condition_a_unscreened"] and out["condition_a_unscreened"]["positive_point_estimate"]

    # B(b) leave-one-year-out
    years = sorted({r["year"] for r in prim})
    loyo = {}
    for y in years:
        s = [r for r in prim if r["year"] != y]
        loyo[y] = rho(s, "sue_p_adj") if len(s) > 10 else None
    vals = [v_ for v_ in loyo.values() if v_ is not None]
    cond_b = all(v_ > 0 for v_ in vals) if vals else False
    out["condition_b_leave_one_year_out"] = {"by_year_dropped": loyo, "all_positive": cond_b, "min_value": min(vals) if vals else None, "min_year_dropped": min(loyo, key=lambda y: (loyo[y] if loyo[y] is not None else 999))}

    clean = passes_primary and cond_a and cond_b and (lo - 0.02) > 0
    borderline = passes_primary and cond_a and cond_b and not clean
    if passes_primary and cond_a and cond_b:
        verdict = "pass, clean" if clean else "pass, borderline"
    elif passes_primary and not cond_b:
        verdict = "pass on primary; fails leave-one-year-out — one year's effect"
    elif passes_primary and not cond_a:
        verdict = "pass on primary; fails unscreened check"
    else:
        verdict = "fail"
    out["verdict"] = {"passes_primary": passes_primary, "condition_a": bool(cond_a), "condition_b": cond_b, "clean": clean, "borderline": borderline, "reading": verdict}

    # C: sector label (only meaningful if primary passes)
    vsec = rho(prim, "sue_p_sector_adj"); losec, hisec, _ = A.boot(prim, lambda s: rho(s, "sue_p_sector_adj"))
    out["sector_quarter_adjusted_primary"] = {"rho": vsec, "range": [losec, hisec]}
    if passes_primary:
        out["sector_label"] = "company-picking signal; candidate for the analyst" if losec > 0 else "sector-level signal; allocator input for sector tilt"
    else:
        out["sector_label"] = "n/a (primary did not pass)"

    # F guards
    other = [r for r in matched if r["own"] < 0]
    beat_rate_prim = round(100 * sum(r["beat"] for r in prim) / len(prim), 1)
    out["guard_beat_rate"] = {"B_ge0_beat_rate_pct": beat_rate_prim, "flag_near_75": 70 <= beat_rate_prim <= 80}
    scale_hi = [r for r in prim if r["est_pct_of_price"] is not None and r["est_pct_of_price"] >= 1]
    scale_lo = [r for r in prim if r["est_pct_of_price"] is not None and r["est_pct_of_price"] < 1]
    def scaleblock(rs):
        if len(rs) < 20: return {"n": len(rs), "rho": None, "range": None}
        vv = rho(rs, "sue_p_adj"); lo_, hi_, _ = A.boot(rs, lambda s: rho(s, "sue_p_adj")); return {"n": len(rs), "rho": vv, "range": [lo_, hi_]}
    out["eps_scale_split"] = {"estimate_ge1pct_price": scaleblock(scale_hi), "estimate_lt1pct_price": scaleblock(scale_lo)}

    # items 1-6 reported only (reuse screen-style computations, scoped to all matched calls, unrestricted by B>=0, for completeness)
    def pct_rank_all(vals):
        order = np.argsort(np.argsort(vals)); return order / (len(vals) - 1) if len(vals) > 1 else np.zeros(len(vals))
    pr_s_all = pct_rank_all([r["sue_p_adj"] for r in matched]); pr_o_all = pct_rank_all([r["own"] for r in matched])
    for i, r in enumerate(matched): r["combined_all"] = (pr_s_all[i] + pr_o_all[i]) / 2
    v1 = rho(matched, "sue_p_adj"); lo1, hi1, _ = A.boot(matched, lambda s: rho(s, "sue_p_adj"))
    vco = rho(matched, "own"); loco, hico, _ = A.boot(matched, lambda s: rho(s, "own"))
    vcb = rho(matched, "combined_all"); locb, hicb, _ = A.boot(matched, lambda s: rho(s, "combined_all"))
    out["item1_all_matched_reported_only"] = {"sue_p_adj": {"value": v1, "range": [lo1, hi1]}, "own": {"value": vco, "range": [loco, hico]}, "combined": {"value": vcb, "range": [locb, hicb]}, "n": len(matched)}

    n = len(matched); n19a = max(1, round(0.19 * n)); n16 = max(1, round(0.16 * n))
    def wil(k, n_): lo_, hi_ = p3.wilson(k, n_); return [round(lo_, 1), round(hi_, 1)]
    srt = sorted(matched, key=lambda r: -r["sue_p_adj"])[:n19a]; g = [r for r in srt if r["gt"]]
    win = sum(r["ret"] >= 20 for r in srt)
    out["item2_top19_all"] = {"n": len(srt), "hit_pct": round(100 * sum(r["gt"] == "bullish" for r in g) / len(g), 1) if g else None, "big_winner_pct": round(100 * win / len(srt), 1), "big_winner_wilson": wil(win, len(srt))}
    srtb = sorted(matched, key=lambda r: r["sue_p_adj"])[:n16]; gb = [r for r in srtb if r["gt"]]
    out["item3_bottom16_all"] = {"n": len(srtb), "hit_pct": round(100 * sum(r["gt"] == "bearish" for r in gb) / len(gb), 1) if gb else None}
    pers_yes = [r for r in matched if r["persistence"]]; pers_no = [r for r in matched if r["persistence"] is False]
    out["item4_persistence"] = {"n_beat_twice": len(pers_yes), "big_winner_pct_beat_twice": round(100 * sum(r["ret"] >= 20 for r in pers_yes) / len(pers_yes), 1) if pers_yes else None,
                                "big_winner_pct_others": round(100 * sum(r["ret"] >= 20 for r in pers_no) / len(pers_no), 1) if pers_no else None}
    out["item5_by_year_all"] = {y: {"n": len(x), "rho": rho(x, "sue_p_adj")} for y in sorted({r["year"] for r in matched}) for x in [[r for r in matched if r["year"] == y]]}
    cells = defaultdict(list)
    for r in matched: cells[(r["group"], r["year"])].append(r)
    big = [v_ for v_ in cells.values() if len(v_) >= 12]
    num_ = sum(rho(v_, "sue_p_adj") * len(v_) for v_ in big if rho(v_, "sue_p_adj") == rho(v_, "sue_p_adj")); den = sum(len(v_) for v_ in big if rho(v_, "sue_p_adj") == rho(v_, "sue_p_adj"))
    out["item5_within_sector_year_all"] = {"weighted_rho": num_ / den if den else None, "n_cells_ge12": len(big), "n_in_cells": den}

    # item6: relation with r0
    from p5close_drift import prev_close as pc2
    r0_rows = []
    for r in matched:
        tk, td = r["ticker"], r["date"]; cd = D_(td)
        p0, dd0 = pc2(prices, tk, cd); b0, bd0 = pc2(prices, "SPY", cd)
        entry, entry_d = prices.price_on_or_after(tk, cd + timedelta(days=1)); bentry, bentry_d = prices.price_on_or_after("SPY", cd + timedelta(days=1))
        if None in (p0, b0, entry, bentry): continue
        r0 = 100 * ((entry - p0) / p0 - (bentry - b0) / b0)
        r0_rows.append({"sue_p_adj": r["sue_p_adj"], "r0": r0})
    out["item6_sue_vs_r0_all"] = {"n": len(r0_rows), "rho": A.spearman([r["sue_p_adj"] for r in r0_rows], [r["r0"] for r in r0_rows])}

    # three-group (screen-style), all matched
    for r in matched: r["cls"] = "winner" if r["ret"] >= 20 else ("loser" if r["ret"] <= -20 else "middle")
    w_ = [r["sue_p_adj"] for r in matched if r["cls"] == "winner"]; m_ = [r["sue_p_adj"] for r in matched if r["cls"] == "middle"]; l_ = [r["sue_p_adj"] for r in matched if r["cls"] == "loser"]
    out["three_group_all_matched"] = {"winner_median": float(np.median(w_)) if w_ else None, "middle_median": float(np.median(m_)) if m_ else None, "loser_median": float(np.median(l_)) if l_ else None,
                                      "n_winner": len(w_), "n_middle": len(m_), "n_loser": len(l_)}

    # D: spot-check rows -- 5 unflagged from top/bottom 5% among B>=0 (3 top, 2 bottom, seed 11); 3 from flagged companies' extremes
    import random
    unflagged_prim = [r for r in prim if not r["flagged"]]
    srt3 = sorted(unflagged_prim, key=lambda r: r["sue_p_adj"]); k5 = max(1, round(0.05 * len(srt3)))
    bot5, top5 = srt3[:k5], srt3[-k5:]
    rng = random.Random(11)
    pick_top = rng.sample(top5, min(3, len(top5))); pick_bot = rng.sample(bot5, min(2, len(bot5)))
    flagged_rows = sorted([r for r in matched if r["flagged"]], key=lambda r: abs(r["sue_p_adj"]), reverse=True)[:3]
    out["spotcheck_5_unflagged"] = [{"ticker": r["ticker"], "date": r["date"], "reportedDate": r["reportedDate"], "sue_p_adj": round(r["sue_p_adj"], 3), "band": "top5%_among_Bge0"} for r in pick_top] + \
                                   [{"ticker": r["ticker"], "date": r["date"], "reportedDate": r["reportedDate"], "sue_p_adj": round(r["sue_p_adj"], 3), "band": "bottom5%_among_Bge0"} for r in pick_bot]
    out["spotcheck_3_flagged"] = [{"ticker": r["ticker"], "date": r["date"], "reportedDate": r["reportedDate"], "sue_p_adj": round(r["sue_p_adj"], 3)} for r in flagged_rows]
    out["verdict_string"] = f"PROVISIONAL — pending 8 point-in-time checks. {verdict}"

    (STATE / "full_results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if "spotcheck" not in k and k != "unmatched_sample"}, indent=1, default=float)[:8000])


if __name__ == "__main__":
    main()
