#!/usr/bin/env python3
"""
consensus_screen_test.py -- consensus-surprise-screen.md Steps 2-3 ($0). Matches train calls (20 winner-rich companies) to AV EARNINGS quarters (+-3 days
on reportedDate), computes SUE_p = (reportedEPS - estimatedEPS) / last close before the call, quarter-adjusted SUE_p (minus the median SUE_p of all
matched calls reported in the same calendar quarter), beat/miss, persistence (beat this AND previous fetched quarter), and runs the pre-registered test
items plus the screen's case-control comparison. Reused unchanged by the full test (different selection.json / company set).
"""
import sys, json, csv, re
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
D_ = date.fromisoformat


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


def run(run_dir):
    STATE = REPO / "analysis/data/run_state" / run_dir
    sel = json.loads((STATE / "selection.json").read_text())
    companies = [x["ticker"] for x in sel["selected"]]
    prices = PriceCache(REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json")
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["ticker"] in companies and c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(REPO / "analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl")}

    aq = {}
    for tk in companies:
        d = json.loads((EV / f"{tk}.json").read_text())
        rows = sorted(d.get("quarterlyEarnings", []), key=lambda r: r.get("fiscalDateEnding", ""))
        aq[tk] = rows

    matched, unmatched = [], []
    for c in calls:
        tk, td = c["ticker"], c["call_date"]
        cd = D_(td)
        best = None; best_dist = 4
        for i, q in enumerate(aq[tk]):
            rd = q.get("reportedDate")
            if not rd: continue
            dist = abs((D_(rd) - cd).days)
            if dist <= 3 and dist < best_dist:
                best, best_dist, best_i = q, dist, i
        if best is None: unmatched.append({"ticker": tk, "date": td}); continue
        rep, est = num(best.get("reportedEPS")), num(best.get("estimatedEPS"))
        if rep is None or est is None: unmatched.append({"ticker": tk, "date": td, "reason": "no EPS"}); continue
        p0, dd0 = prev_close(prices, tk, cd)
        if p0 is None or p0 == 0: unmatched.append({"ticker": tk, "date": td, "reason": "no price"}); continue
        entry, entry_d = prices.price_on_or_after(tk, cd + timedelta(days=1))
        if entry_d and entry_d <= dd0: unmatched.append({"ticker": tk, "date": td, "reason": "overlap"}); continue
        sue_p = 100 * (rep - est) / p0
        prev_q = aq[tk][best_i - 1] if best_i > 0 else None
        pers = None
        if prev_q:
            pr, pe = num(prev_q.get("reportedEPS")), num(prev_q.get("estimatedEPS"))
            if pr is not None and pe is not None: pers = (rep > est) and (pr > pe)
        matched.append({"ticker": tk, "date": td, "group": smap.get(tk, "other"), "year": td[:4], "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"],
                        "own": (c["b_score"] + b2[(tk, td)]) / 2, "sue_p": sue_p, "beat": rep > est, "surprise_pct": num(best.get("surprisePercentage")),
                        "reportedDate": best.get("reportedDate"), "quarter": qtr(best.get("fiscalDateEnding", "1970-01")), "persistence": pers})

    # quarter-adjusted SUE_p
    byq = defaultdict(list)
    for r in matched: byq[r["quarter"]].append(r["sue_p"])
    qmed = {q: float(np.median(v)) for q, v in byq.items()}
    for r in matched: r["sue_p_adj"] = r["sue_p"] - qmed[r["quarter"]]; r["n_in_quarter"] = len(byq[r["quarter"]])

    out = {"n_train_calls_in_selection": len(calls), "n_matched": len(matched), "match_rate_pct": round(100 * len(matched) / len(calls), 1),
           "unmatched": unmatched, "n_unmatched": len(unmatched), "quarter_medians_n": {q: len(v) for q, v in byq.items()}}

    def cl(x): return max(-20, min(20, x)) if x is not None else None  # not used; placeholder removed below

    # three groups
    for r in matched: r["cls"] = "winner" if r["ret"] >= 20 else ("loser" if r["ret"] <= -20 else "middle")
    def rho(rs, k): return A.spearman([r[k] for r in rs], [r["ret"] for r in rs])

    def group_diff(key):
        w = [r for r in matched if r["cls"] == "winner"]; m = [r for r in matched if r["cls"] == "middle"]; l = [r for r in matched if r["cls"] == "loser"]
        def med(rs): return float(np.median([r[key] for r in rs])) if rs else None
        dwm = med(w) - med(m) if w and m else None
        dlm = med(l) - med(m) if l and m else None
        def diffboot(sel_a, sel_b):
            rs = [r for r in matched if r["cls"] in (sel_a, sel_b)]
            def stat(s):
                a_ = [r[key] for r in s if r["cls"] == sel_a]; b_ = [r[key] for r in s if r["cls"] == sel_b]
                return (float(np.median(a_)) - float(np.median(b_))) if a_ and b_ else float("nan")
            lo, hi, _ = A.boot(rs, stat); return [lo, hi]
        return {"winner_median": med(w), "middle_median": med(m), "loser_median": med(l), "n_winner": len(w), "n_middle": len(m), "n_loser": len(l),
               "winner_minus_middle": dwm, "winner_minus_middle_range": diffboot("winner", "middle"),
               "loser_minus_middle": dlm, "loser_minus_middle_range": diffboot("loser", "middle")}
    out["screen_3groups_sue_p_adj"] = group_diff("sue_p_adj"); out["screen_3groups_sue_p_raw"] = group_diff("sue_p")

    # beat rate winner vs other (as originally-worded case-control), company-block
    other = [r for r in matched if r["cls"] != "winner"]; winner = [r for r in matched if r["cls"] == "winner"]
    br_w = round(100 * sum(r["beat"] for r in winner) / len(winner), 1) if winner else None
    br_o = round(100 * sum(r["beat"] for r in other) / len(other), 1) if other else None
    def blockboot(stat):
        return A.boot(matched, stat)[:2]
    def med_diff_wo(s):
        w_ = [r["sue_p_adj"] for r in s if r["cls"] == "winner"]; o_ = [r["sue_p_adj"] for r in s if r["cls"] != "winner"]
        return (float(np.median(w_)) - float(np.median(o_))) if w_ and o_ else float("nan")
    lo, hi = blockboot(med_diff_wo)
    out["case_control_winner_vs_other"] = {"beat_rate_winner_pct": br_w, "beat_rate_other_pct": br_o, "median_sue_p_adj_winner": float(np.median([r["sue_p_adj"] for r in winner])),
                                           "median_sue_p_adj_other": float(np.median([r["sue_p_adj"] for r in other])), "diff": med_diff_wo(matched), "diff_range": [lo, hi]}
    # within-company: share of companies where winner mean SUE_p_adj > other mean
    byco = defaultdict(list)
    for r in matched: byco[r["ticker"]].append(r)
    wins_co = 0; n_co_testable = 0
    for tk, rs in byco.items():
        w_ = [r["sue_p_adj"] for r in rs if r["cls"] == "winner"]; o_ = [r["sue_p_adj"] for r in rs if r["cls"] != "winner"]
        if w_ and o_: n_co_testable += 1; wins_co += float(np.mean(w_)) > float(np.mean(o_))
    out["within_company_share_winner_higher"] = {"n_testable": n_co_testable, "n_higher": wins_co, "pct": round(100 * wins_co / n_co_testable, 1) if n_co_testable else None, "expected_pct": 50}

    # flagged companies: share of matched quarters with |surprisePercentage| > 100
    flag = {}
    for tk, rs in byco.items():
        n_ext = sum(1 for r in rs if r["surprise_pct"] is not None and abs(r["surprise_pct"]) > 100)
        flag[tk] = {"n": len(rs), "n_extreme_pct": n_ext, "share_pct": round(100 * n_ext / len(rs), 1)}
    flagged_companies = sorted([tk for tk, v in flag.items() if v["share_pct"] >= 50])
    out["surprisePercentage_extreme_flag"] = {"by_company": flag, "flagged_ge50pct": flagged_companies}
    matched_excl = [r for r in matched if r["ticker"] not in flagged_companies]

    # test item 1: rank correlations, with and without flagged
    def block1(rs, label):
        b = {}
        for name, key in (("sue_p_adj", "sue_p_adj"), ("own", "own")):
            v = rho(rs, key); lo_, hi_, _ = A.boot(rs, lambda s, k=key: rho(s, k)); b[name] = {"value": v, "range": [lo_, hi_]}
        def pct_rank(vals):
            order = np.argsort(np.argsort(vals)); return order / (len(vals) - 1) if len(vals) > 1 else np.zeros(len(vals))
        pr_s = pct_rank([r["sue_p_adj"] for r in rs]); pr_o = pct_rank([r["own"] for r in rs])
        for i, r in enumerate(rs): r["combined"] = (pr_s[i] + pr_o[i]) / 2
        vc = rho(rs, "combined"); loc, hic, _ = A.boot(rs, lambda s: rho(s, "combined")); b["combined"] = {"value": vc, "range": [loc, hic]}
        dm = vc - b["own"]["value"]; lod, hid, _ = A.boot(rs, lambda s: rho(s, "combined") - rho(s, "own")); b["combined_minus_own"] = {"value": dm, "range": [lod, hid]}
        b["n"] = len(rs)
        return b
    out["item1_with_flagged"] = block1(matched, "all"); out["item1_excl_flagged"] = block1(matched_excl, "excl") if matched_excl else None

    n = len(matched); n19 = max(1, round(0.19 * n)); n16 = max(1, round(0.16 * n))
    def wil(k, n_): lo_, hi_ = p3.wilson(k, n_); return [round(lo_, 1), round(hi_, 1)]
    def top(rs, key, n_):
        srt = sorted(rs, key=lambda r: -r[key])[:n_]; g = [r for r in srt if r["gt"]]; right = sum(r["gt"] == "bullish" for r in g); win = sum(r["ret"] >= 20 for r in srt)
        return {"n": len(srt), "hit_pct": round(100 * right / len(g), 1) if g else None, "big_winner_pct": round(100 * win / len(srt), 1), "big_winner_wilson": wil(win, len(srt))}
    out["item2_top19_by_sue_p_adj"] = top(matched, "sue_p_adj", n19)
    out["item2_top19_by_combined"] = top(matched, "combined", n19)
    srt = sorted(matched, key=lambda r: r["sue_p_adj"])[:n16]; g = [r for r in srt if r["gt"]]
    out["item3_bottom16_by_sue_p_adj"] = {"n": len(srt), "hit_pct": round(100 * sum(r["gt"] == "bearish" for r in g) / len(g), 1) if g else None}

    pers_yes = [r for r in matched if r["persistence"]]; pers_no = [r for r in matched if r["persistence"] is False]
    out["item4_persistence"] = {"n_beat_twice": len(pers_yes), "n_not": len(pers_no), "big_winner_pct_beat_twice": round(100 * sum(r["ret"] >= 20 for r in pers_yes) / len(pers_yes), 1) if pers_yes else None,
                                "big_winner_pct_others": round(100 * sum(r["ret"] >= 20 for r in pers_no) / len(pers_no), 1) if pers_no else None,
                                "rho_beat_twice": rho(pers_yes, "sue_p_adj") if len(pers_yes) >= 5 else None}
    out["item5_by_year"] = {y: {"n": len(x), "rho": rho(x, "sue_p_adj")} for y in sorted({r["year"] for r in matched}) for x in [[r for r in matched if r["year"] == y]]}
    cells = defaultdict(list)
    for r in matched: cells[(r["group"], r["year"])].append(r)
    big = [v for v in cells.values() if len(v) >= 12]
    num_ = sum(rho(v, "sue_p_adj") * len(v) for v in big if rho(v, "sue_p_adj") == rho(v, "sue_p_adj")); den = sum(len(v) for v in big if rho(v, "sue_p_adj") == rho(v, "sue_p_adj"))
    out["item5_within_sector_year"] = {"weighted_rho": num_ / den if den else None, "n_cells_ge12": len(big), "n_in_cells": den}

    # item 6: relation with r0 from drift.json
    drift = json.loads((REPO / "analysis/data/run_state/p5-close-sector-drift/drift.json").read_text())
    r0map = {}  # need r0 per call; drift.json doesn't store per-call rows, recompute via same method
    from p5close_drift import prev_close as pc2
    r0_rows = []
    for r in matched:
        tk, td = r["ticker"], r["date"]; cd = D_(td)
        p0, dd0 = pc2(prices, tk, cd); b0, bd0 = pc2(prices, "SPY", cd)
        entry, entry_d = prices.price_on_or_after(tk, cd + timedelta(days=1)); bentry, bentry_d = prices.price_on_or_after("SPY", cd + timedelta(days=1))
        if None in (p0, b0, entry, bentry): continue
        r0 = 100 * ((entry - p0) / p0 - (bentry - b0) / b0)
        r0_rows.append({"ticker": tk, "sue_p_adj": r["sue_p_adj"], "r0": r0, "ret": r["ret"]})
    rho_sue_r0 = A.spearman([r["sue_p_adj"] for r in r0_rows], [r["r0"] for r in r0_rows])
    out["item6_sue_vs_r0"] = {"n": len(r0_rows), "rho": rho_sue_r0}

    # smallest detectable effect: half-width of SUE_p_adj rank-corr range
    hw = (out["item1_with_flagged"]["sue_p_adj"]["range"][1] - out["item1_with_flagged"]["sue_p_adj"]["range"][0]) / 2
    out["smallest_detectable_rho"] = round(hw, 3)

    # spot-check rows: top/bottom 5% of sue_p_adj
    srt2 = sorted(matched, key=lambda r: r["sue_p_adj"]); k5 = max(1, round(0.05 * len(srt2)))
    bottom5, top5 = srt2[:k5], srt2[-k5:]
    import random
    rng = random.Random(11)
    pick_top = rng.sample(top5, min(3, len(top5))); pick_bot = rng.sample(bottom5, min(2, len(bottom5)))
    out["spotcheck_rows"] = [{"ticker": r["ticker"], "date": r["date"], "reportedDate": r["reportedDate"], "sue_p_adj": round(r["sue_p_adj"], 3), "sue_p": round(r["sue_p"], 3), "band": "top5%"} for r in pick_top] + \
                            [{"ticker": r["ticker"], "date": r["date"], "reportedDate": r["reportedDate"], "sue_p_adj": round(r["sue_p_adj"], 3), "sue_p": round(r["sue_p"], 3), "band": "bottom5%"} for r in pick_bot]

    # closing rule check: screen negative AND |rho(sue_adj,r0)| >= 0.5?
    g3 = out["screen_3groups_sue_p_adj"]
    screen_negative = not (g3["winner_minus_middle_range"][0] > 0)
    out["closing_rule"] = {"screen_negative": screen_negative, "rho_sue_r0": rho_sue_r0, "lead_closed": screen_negative and abs(rho_sue_r0) >= 0.5}

    lo_wm = g3["winner_minus_middle_range"][0]
    out["screen_reading"] = "surprise separates winners" if lo_wm is not None and lo_wm > 0 else "does not"
    (STATE / "screen_results.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    out = run(sys.argv[1])
    print(json.dumps({k: v for k, v in out.items() if k not in ("unmatched",)}, indent=1, default=float)[:6000])
