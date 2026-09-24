#!/usr/bin/env python3
"""p6 post-hoc comparators ($0). NOT pre-registered; labelled post-hoc in the wrap-up.
A's answers coded bearish -1 / neutral 0 / bullish +1 for a rank correlation; spreads on >=+3 vs <=-2 for B and C."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p6_output_format_analysis as a
rows = [r for r in a.load_calls() if r["fwd_rel_ret_tradeable"] is not None]
code = {"bearish": -1, "neutral": 0, "bullish": 1}
def rho_a(rs): return a.spearman([code[r["v6_dir"]] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs])
def spread(arm, lo):
    def f(rs):
        h = [r["fwd_rel_ret_tradeable"] for r in rs if r[f"{arm}_score"] >= 3]
        l = [r["fwd_rel_ret_tradeable"] for r in rs if r[f"{arm}_score"] <= lo]
        return a.med(h) - a.med(l)
    return f
out = {"A_ordinal_rho": [rho_a(rows), *a.boot(rows, rho_a)[:2]]}
for arm in "bc":
    f = spread(arm, -2)
    l = [r for r in rows if r[f"{arm}_score"] <= -2]
    out[f"{arm}_spread_ge3_vs_le-2"] = {"point": f(rows), "range": a.boot(rows, f)[:2], "n_le_-2": len(l), "median_le_-2": a.med([r["fwd_rel_ret_tradeable"] for r in l])}
def rho_diff(rs):
    x = [r for r in rs]
    return a.spearman([r["c_score"] for r in x], [r["fwd_rel_ret_tradeable"] for r in x]) - a.spearman([r["b_score"] for r in x], [r["fwd_rel_ret_tradeable"] for r in x])
out["C_minus_B_rho_paired"] = [rho_diff(rows), *a.boot(rows, rho_diff)[:2]]
def rho_ca(rs): return a.spearman([r["c_score"] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs]) - rho_a(rs)
def rho_ba(rs): return a.spearman([r["b_score"] for r in rs], [r["fwd_rel_ret_tradeable"] for r in rs]) - rho_a(rs)
out["C_minus_A_rho_paired"] = [rho_ca(rows), *a.boot(rows, rho_ca)[:2]]
out["B_minus_A_rho_paired"] = [rho_ba(rows), *a.boot(rows, rho_ba)[:2]]
(a.STATE / "posthoc.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
