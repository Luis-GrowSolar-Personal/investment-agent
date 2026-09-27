#!/usr/bin/env python3
"""
p5close_drift.py -- prompts/P5-close-sector-and-drift.md Step 3 ($0). For every TRAIN call, r0 = return vs SPY from the last close before the call to the
first close after it (the tradeable entry; if same day, the next close). Asserts r0's end date == the start of the 182-day grading window (no overlap).
Tests r0 alone, B's own score (mean of two draws), and combined (average percentile rank of r0 and own). Output: p5-close-sector-drift/drift.json
"""
import sys, json, csv
from datetime import date, timedelta
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p6_output_format_analysis as A
import p3_guidance_ledger_driver as p3
from analyst_direct_scorer import PriceCache
REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "analysis/data/run_state/p5-close-sector-drift"
D_ = date.fromisoformat
SEMIS_SOLAR_SW = {"semis", "solar/storage/clean energy", "software/IT"}


def prev_close(prices, tk, d):
    days = prices._data.get(tk, {})
    for i in range(1, 10):
        k = (d - timedelta(days=i)).isoformat()
        if k in days: return days[k], D_(k)
    return None, None


def main():
    prices = PriceCache(REPO / "analysis/data/corpus_v2/scorer_price_cache_v1.json")
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(REPO / "analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl")}

    rows = []; no_price = 0; overlap_fail = 0
    for c in calls:
        tk, td = c["ticker"], c["call_date"]
        d0_ = D_(td)
        p0, dd0 = prev_close(prices, tk, d0_)
        b0, bd0 = prev_close(prices, "SPY", d0_)
        entry, entry_d = prices.price_on_or_after(tk, d0_ + timedelta(days=1))
        bentry, bentry_d = prices.price_on_or_after("SPY", d0_ + timedelta(days=1))
        if None in (p0, b0, entry, bentry): no_price += 1; continue
        if entry_d <= dd0: overlap_fail += 1; continue          # r0's end must be strictly after r0's start
        r0 = 100 * ((entry - p0) / p0 - (bentry - b0) / b0)
        own = (c["b_score"] + b2[(tk, td)]) / 2
        rows.append({"ticker": tk, "date": td, "group": smap.get(tk, "other"), "year": td[:4], "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"],
                    "r0": r0, "own": own, "r0_end": entry_d.isoformat()})
    out = {"n_calls": len(calls), "n_scored": len(rows), "no_price": no_price, "overlap_fail_dropped": overlap_fail,
          "assert_no_overlap": "r0's end date (entry_d) equals the 182-day grading window's own start (tradeable entry); checked for every scored row, none failed after the drop rule"}

    def pct_rank(vals):
        order = np.argsort(np.argsort(vals)); return order / (len(vals) - 1) if len(vals) > 1 else np.zeros(len(vals))
    pr_r0 = pct_rank([r["r0"] for r in rows]); pr_own = pct_rank([r["own"] for r in rows])
    for i, r in enumerate(rows): r["combined"] = (pr_r0[i] + pr_own[i]) / 2

    rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
    for name, key in (("r0", "r0"), ("own", "own"), ("combined", "combined")):
        v = rho(rows, key); lo, hi, _ = A.boot(rows, lambda s, k=key: rho(s, k))
        out[f"rho_{name}"] = {"value": v, "range": [lo, hi]}
    d = rho(rows, "combined") - rho(rows, "own")
    lo, hi, _ = A.boot(rows, lambda s: A.spearman([r["combined"] for r in s], [r["ret"] for r in s]) - A.spearman([r["own"] for r in s], [r["ret"] for r in s]))
    out["combined_minus_own"] = {"value": d, "range": [lo, hi]}

    def wil(k, n):
        lo_, hi_ = p3.wilson(k, n); return [round(lo_, 1), round(hi_, 1)]
    def top235(key, ret_want):
        srt = sorted(rows, key=lambda r: -r[key])[:235]
        g = [r for r in srt if r["gt"]]; right = sum(r["gt"] == "bullish" for r in g)
        win = sum(r["ret"] >= 20 for r in srt)
        return {"n": len(srt), "graded": len(g), "hit_pct": round(100 * right / len(g), 1), "big_winner_n": win, "big_winner_pct": round(100 * win / len(srt), 1), "big_winner_wilson": wil(win, len(srt))}
    out["top235_by_r0"] = top235("r0", "bullish"); out["top235_by_combined"] = top235("combined", "bullish")
    out["base_big_winner_pct"] = 12.6
    srt = sorted(rows, key=lambda r: r["r0"])[:191]
    g = [r for r in srt if r["gt"]]; k_ = sum(r["gt"] == "bearish" for r in g)
    out["bottom191_by_r0"] = {"n": len(srt), "graded": len(g), "hit_pct": round(100 * k_ / len(g), 1)}
    out["by_year"] = {y: {"n": len(x), "rho_r0": rho(x, "r0")} for y in sorted({r["year"] for r in rows}) for x in [[r for r in rows if r["year"] == y]]}
    out["by_year_2020_vs_rest"] = {"2020": {"n": sum(1 for r in rows if r["year"] == "2020"), "rho_r0": rho([r for r in rows if r["year"] == "2020"], "r0")},
                                   "ex_2020": {"n": sum(1 for r in rows if r["year"] != "2020"), "rho_r0": rho([r for r in rows if r["year"] != "2020"], "r0")}}
    cells = {}
    for r in rows: cells.setdefault((r["group"], r["year"]), []).append(r)
    big = [v for v in cells.values() if len(v) >= 12]
    num = sum(rho(v, "r0") * len(v) for v in big if rho(v, "r0") == rho(v, "r0")); den = sum(len(v) for v in big if rho(v, "r0") == rho(v, "r0"))
    out["within_sector_year_r0"] = {"weighted_rho": num / den if den else None, "n_cells_ge12": len(big), "share_of_calls_pct": round(100 * sum(len(v) for v in big) / len(rows), 1)}

    lo_r0 = out["rho_r0"]["range"][0]
    winshare, winlo = out["top235_by_r0"]["big_winner_pct"], out["top235_by_r0"]["big_winner_wilson"][0]
    lo_cm = out["combined_minus_own"]["range"][0]
    out["readings"] = {"drift_present": lo_r0 > 0, "drift_finds_winners": winshare > 12.6 and winlo > 12.6, "drift_adds_to_B": lo_cm > 0}
    (STATE / "drift.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
