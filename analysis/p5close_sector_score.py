#!/usr/bin/env python3
"""
p5close_sector_score.py -- prompts/P5-close-sector-and-drift.md Step 2 ($0). Point-in-time sector score for every TRAIN call: mean B score of other companies'
calls in the same sector group (SECTOR_MAP.csv), dated strictly before and within the prior 45 days, pooled from train (mean of B's two draws) and tune
(scores_b_tune.jsonl, single draw). Requires >=3 such calls from >=2 companies. Own score = train call's mean of two draws. Combined = average of
percentile ranks (own, sector) across the eligible-call set. Output: p5-close-sector-drift/sector_score.json
"""
import sys, json, csv
from datetime import date, timedelta
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p6_output_format_analysis as A
import p3_guidance_ledger_driver as p3
REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "analysis/data/run_state/p5-close-sector-drift"
D_ = date.fromisoformat
SEMIS_SOLAR_SW = {"semis", "solar/storage/clean energy", "software/IT"}


def main():
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    am = p3.alias_map()
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(REPO / "analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    tune_scores = {}
    for r in p3.read_jsonl(REPO / "analysis/data/run_state/p6b-tune-confirmation/scores_b_tune.jsonl"):
        s = A.parse_score(r["content"])[1]
        if s is not None: tune_scores[(r["ticker"], r["date"])] = s
    split = json.loads((REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text())

    # pool of scored calls with sector group and date, for sector-mean lookups (train mean-of-two-draws + tune single draw)
    pool = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        pool.append({"ticker": c["ticker"], "date": c["call_date"], "score": (c["b_score"] + b2[k]) / 2, "group": smap.get(c["ticker"], "other")})
    for (tk, dt), s in tune_scores.items():
        pool.append({"ticker": tk, "date": dt, "score": s, "group": smap.get(tk, "other")})
    pool.sort(key=lambda r: r["date"])
    by_group = {}
    for r in pool: by_group.setdefault(r["group"], []).append(r)

    rows = []
    for c in calls:
        td, tk = c["call_date"], c["ticker"]
        g = smap.get(tk, "other"); cutoff = (D_(td) - timedelta(days=45)).isoformat()
        elig = [r for r in by_group.get(g, []) if r["ticker"] != tk and cutoff <= r["date"] < td]
        n_co = len({r["ticker"] for r in elig})
        if len(elig) < 3 or n_co < 2: continue
        sec = float(np.mean([r["score"] for r in elig]))
        own = (c["b_score"] + b2[(tk, td)]) / 2
        rows.append({"ticker": tk, "date": td, "group": g, "ret": c["fwd_rel_ret_tradeable"], "gt": c["gt_old_ruler"], "sector": sec, "own": own, "n_elig": len(elig), "n_companies": n_co})
    if not rows:
        print("NO ROWS with a sector score"); return

    def pct_rank(vals):
        order = np.argsort(np.argsort(vals)); return order / (len(vals) - 1) if len(vals) > 1 else np.zeros(len(vals))
    pr_sec = pct_rank([r["sector"] for r in rows]); pr_own = pct_rank([r["own"] for r in rows])
    for i, r in enumerate(rows): r["combined"] = (pr_sec[i] + pr_own[i]) / 2

    rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
    out = {"n_calls_with_sector_score": len(rows), "n_train_calls": len(calls), "coverage_pct": round(100 * len(rows) / len(calls), 1),
           "by_sector_coverage": {g: sum(1 for r in rows if r["group"] == g) for g in sorted({r["group"] for r in rows})}}
    for name, key in (("sector", "sector"), ("own", "own"), ("combined", "combined")):
        v = rho(rows, key); lo, hi, _ = A.boot(rows, lambda s, k=key: rho(s, k))
        out[f"rho_{name}"] = {"value": v, "range": [lo, hi]}
    for name, ka, kb in (("combined_minus_own", "combined", "own"), ("sector_minus_own", "sector", "own")):
        d = rho(rows, ka) - rho(rows, kb)
        lo, hi, _ = A.boot(rows, lambda s, a=ka, b=kb: A.spearman([r[a] for r in s], [r["ret"] for r in s]) - A.spearman([r[b] for r in s], [r["ret"] for r in s]))
        out[name] = {"value": d, "range": [lo, hi]}
    n = len(rows)
    n_bot, n_top = max(1, round(0.15 * n)), max(1, round(0.20 * n))
    def hit_median(rs, want):
        g = [r for r in rs if r["gt"]]; k = sum(r["gt"] == want for r in g)
        return {"n": len(rs), "graded": len(g), "hit_pct": round(100 * k / len(g), 1) if g else None, "median_ret": round(float(np.median([r["ret"] for r in rs])), 2)}
    for name, key in (("sector", "sector"), ("own", "own"), ("combined", "combined")):
        srt = sorted(rows, key=lambda r: r[key])
        out[f"bottom15_{name}"] = hit_median(srt[:n_bot], "bearish"); out[f"top20_{name}"] = hit_median(srt[-n_top:], "bullish")
    out["shares"] = {"n": n, "n_bottom15": n_bot, "n_top20": n_top}
    focus = [r for r in rows if r["group"] in SEMIS_SOLAR_SW]
    out["focus_sectors_pooled"] = {"n": len(focus)}
    for name, key in (("sector", "sector"), ("own", "own"), ("combined", "combined")):
        if len(focus) >= 3:
            v = rho(focus, key); lo, hi, _ = A.boot(focus, lambda s, k=key: rho(s, k))
            out["focus_sectors_pooled"][name] = {"value": v, "range": [lo, hi]}
    lo_sec = out["rho_sector"]["range"][0]; lo_cm = out["combined_minus_own"]["range"][0]
    out["reading"] = "sector score carries B's edge" if lo_sec > 0 else ("sector score adds to B" if lo_cm > 0 else "no sector gain")
    (STATE / "sector_score.json").write_text(json.dumps(out, indent=1, default=float)); print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
