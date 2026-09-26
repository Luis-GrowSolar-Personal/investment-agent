#!/usr/bin/env python3
"""opus_posthoc_repro.py -- sop-2026-09-26-bookkeeping Step 2a ($0). Tries to reproduce the state of play 2.4 post-hoc Opus figures from committed score files.
Paired gain = rho(Opus) - mean(rho(B draw1), rho(B draw2)) on the same calls; ticker-block bootstrap 2,000 draws seed 11. Megacap = stratum S1 (assumption; the state of
play does not define it). Mean-score differences are Opus minus mean(B1,B2) per call."""
import sys, json
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import p6_output_format_analysis as A  # noqa: E402
import p3_guidance_ledger_driver as p3  # noqa: E402
RS = REPO / "analysis/data/run_state"
calls = {(c["ticker"], c["call_date"]): c for c in A.load_calls(RS / "p6-output-format-round/calls.csv")}
b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(RS / "b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
rows = []
for r in p3.read_jsonl(RS / "opus-screen/scores_b_opus.jsonl"):
    k = (r["ticker"], r["date"]); c = calls[k]
    rows.append({"ticker": k[0], "stratum": c["stratum"], "ret": c["fwd_rel_ret_tradeable"], "b1": c["b_score"], "b2": b2[k], "o": A.parse_score(r["content"])[1]})
assert len(rows) == 300
rho = lambda rs, k: A.spearman([r[k] for r in rs], [r["ret"] for r in rs])
gain = lambda rs: rho(rs, "o") - (rho(rs, "b1") + rho(rs, "b2")) / 2
def g(rs):
    lo, hi, _ = A.boot(rs, gain); return {"n": len(rs), "gain": round(gain(rs), 3), "range": [round(lo, 3), round(hi, 3)]}
out = {"B_mean_rho": round((rho(rows, "b1") + rho(rows, "b2")) / 2, 3), "opus_rho": round(rho(rows, "o"), 3),
       "paired_gain_all": g(rows), "megacap_S1": g([r for r in rows if r["stratum"] == "S1"]), "rest_not_S1": g([r for r in rows if r["stratum"] != "S1"]),
       "excluding_abs20": g([r for r in rows if abs(r["ret"]) < 20])}
dm = lambda rs: round(float(np.mean([r["o"] - (r["b1"] + r["b2"]) / 2 for r in rs])), 2)
dm1 = lambda rs: round(float(np.mean([r["o"] - r["b1"] for r in rs])), 2)
L = [r for r in rows if r["ret"] <= -20]; W = [r for r in rows if r["ret"] >= 20]
out["mean_score_opus_minus_B"] = {"big_losers_n": len(L), "vs_mean_of_B1B2": dm(L), "vs_B1": dm1(L), "big_winners_n": len(W), "winners_vs_mean_of_B1B2": dm(W), "winners_vs_B1": dm1(W)}
(RS / "sop-2026-09-26-bookkeeping/posthoc_repro.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
