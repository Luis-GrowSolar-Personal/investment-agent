#!/usr/bin/env python3
"""
p5p1_step1.py -- prompts/P5-phase1-peer-map.md Step 1 ($0 in model calls; reads saved EDGAR submissions and saved annual reports, NO new requests).
1a SECTOR_MAP.csv (SIC -> group; documented overrides; solar/storage moves only with a verbatim quote from the company's own annual report).
1b winners by sector x year (train). 1c B's rank correlation inside sector-year cells with >= 12 calls, both draws, ticker-block range. 1d call-over-call change in B's score.
Outputs: docs/peers/SECTOR_MAP.csv, p5-phase1/sector_diagnostics.json. Big winner: fwd_rel_ret_tradeable >= +20 (tradeable-entry 182-day return vs SPY, points).
"""
import sys, json, csv, glob, re
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p6_output_format_analysis as A
import p3_guidance_ledger_driver as p3
REPO = C.REPO
SOLAR = "solar/storage/clean energy"
# Moves to solar/storage, each with a verbatim quote from the company's own latest annual report (checked below). AMPX, ENVX (batteries for mobility/devices), AMSC (grid equipment),
# BLDP (hydrogen fuel cells) are NOT moved: their opening business text does not describe the company's own business as solar or energy storage.
MOVE = {
    "RUN": "Sunrun transformed the solar industry in 2007 by removing financial barriers and democratizing access to locally-generated, renewable energy.",
    "NOVA": "We offer customers products to power and improve the energy efficiency and sustainability of their homes and businesses with affordable solar energy and related products and services.",
    "SPWR": "Ambia is a residential solar energy system installer which operates in various markets throughout the United States.",
    "SUNW": "Commercial Solar Energy Inc.",
    "SEDG": "Our solutions address a broad range of solar market segments, from residential solar installations to commercial and small utility scale solar installations.",
    "FSLR": "We are America’s leading PV solar technology and manufacturing company.",
    "ARRY": "We are a leading global provider of solar tracking technology and fixed-tilt systems to utility-scale and distributed generation customers who construct, develop, and operate solar photovoltaic (“PV”) sites.",
    "SHLS": "Shoals Technologies Group is a leading design-engineering company and manufacturer of advanced electrical infrastructure solutions for mission‑critical applications across solar photovoltaic (PV), BESS, and data center power systems.",
    "CSIQ": "We are one of the world’s largest solar technology and renewable energy companies, a leading manufacturer of solar photovoltaic modules, a provider of battery energy storage solutions, and a developer of utilit",
    "EOSE": "We believe the energy storage industry has become a critical component of modern electricity infrastructure.",
    "QS": "was founded in 2010 with the mission to revolutionize energy storage to enable a sustainable future.",
    "MAXNQ": "If the demand for our solar products decreases as a result of a deteriorating market environment or as a result of intensifying competition or global trade conflicts",
    "JKS": "our ingot wafer, solar cell and solar module production",
}


def main():
    tk = C.tickers_json(); KN = {"NOVA": 1772695, "SUNW": 1172631}; rows = []
    for orig, w, sp in C.universe():
        cik = int(tk[w]["cik_str"]) if w in tk else KN.get(w)
        r = {"symbol": orig, "working": w, "split": sp, "name": "", "sic": "", "sic_description": "", "sic_group": "", "final_group": "", "basis": "", "quote": ""}
        if cik is None: r.update(final_group="other", basis="unresolved (not on EDGAR: First Republic filed with the FDIC)"); rows.append(r); continue
        d = json.loads((C.EV / "submissions" / f"CIK{cik:010d}.json").read_text())
        r.update(name=d.get("name"), sic=d.get("sic"), sic_description=d.get("sicDescription"), sic_group=C.sic_group(d["sic"]))
        r["final_group"], r["basis"] = r["sic_group"], "sic"
        if w in C.OVERRIDE: r["final_group"], r["basis"] = C.OVERRIDE[w][0], "override: " + C.OVERRIDE[w][1]
        if w in MOVE:
            doc = glob.glob(str(C.EV / f"docs/{w}_*"))[0]; text = C.plain(open(doc, errors="replace").read())
            assert MOVE[w] in text, f"quote not found for {w}"
            r["final_group"], r["basis"], r["quote"] = SOLAR, "solar/storage: own annual report quote", MOVE[w]
        if w == "PARA": r["basis"] += "; NOTE: 'PARA' now resolves to Banzai International on EDGAR, not Paramount; Paramount is excluded from train analysis (corrupt prices)"
        rows.append(r)
    with open(REPO / "docs/peers/SECTOR_MAP.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    grp = {r["working"]: r["final_group"] for r in rows}
    out = {"sector_map_counts": {g: sum(1 for r in rows if r["final_group"] == g) for g in C.GROUPS}, "solar_moved": sorted(MOVE), "solar_not_moved_flagged": ["AMPX", "ENVX", "AMSC", "BLDP"]}

    # train calls
    calls = [c for c in A.load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    b2 = {(r["ticker"], r["date"]): A.parse_score(r["content"])[1] for r in p3.read_jsonl(REPO / "analysis/data/run_state/b-champion-and-noise-floor/scores_b_rerun1.jsonl")}
    rows_c = []
    for c in calls:
        k = (c["ticker"], c["call_date"])
        rows_c.append({"ticker": c["ticker"], "date": c["call_date"], "year": c["call_date"][:4], "group": grp.get(c["ticker"], "other"), "ret": c["fwd_rel_ret_tradeable"], "b1": c["b_score"], "b2": b2[k]})
    assert len(rows_c) == 1217
    for r in rows_c: r["win"] = r["ret"] >= 20
    years = sorted({r["year"] for r in rows_c})
    # 1b
    tab = {}
    for g in C.GROUPS:
        tab[g] = {}
        for y in years:
            x = [r for r in rows_c if r["group"] == g and r["year"] == y]
            if x: tab[g][y] = {"calls": len(x), "big_winner_share_pct": round(100 * sum(r["win"] for r in x) / len(x), 1), "winners": sum(r["win"] for r in x)}
    out["1b_winners_by_sector_year"] = {"table": {g: v for g, v in tab.items() if v}, "overall_winner_share_pct": round(100 * sum(r["win"] for r in rows_c) / 1217, 1)}
    cells = [(g, y, v["calls"], v["big_winner_share_pct"]) for g, vv in tab.items() for y, v in vv.items() if v["calls"] >= 12]
    top = sorted(cells, key=lambda c: -c[3])[:6]
    out["1b_top_cells_by_winner_share_min12"] = [{"sector": g, "year": y, "calls": n, "winner_share_pct": s} for g, y, n, s in top]
    # 1c
    def cell_rho(rs, key):
        cells_ = {}
        for r in rs: cells_.setdefault((r["group"], r["year"]), []).append(r)
        num = den = 0.0
        for v in cells_.values():
            if len(v) >= 12:
                rho = A.spearman([x[key] for x in v], [x["ret"] for x in v])
                if rho == rho: num += rho * len(v); den += len(v)
        return num / den if den else float("nan")
    share_in_cells = sum(len(v) for v in {(g, y): [r for r in rows_c if r["group"] == g and r["year"] == y] for g in C.GROUPS for y in years}.values() if len(v) >= 12) / 1217
    out["1c_within_sector_year"] = {"share_of_calls_in_cells_ge12_pct": round(100 * share_in_cells, 1), "n_cells_ge12": len(cells)}
    for name, key in (("draw1", "b1"), ("draw2", "b2")):
        v = cell_rho(rows_c, key); lo, hi, nv = A.boot(rows_c, lambda s, k=key: cell_rho(s, k))
        overall = A.spearman([r[key] for r in rows_c], [r["ret"] for r in rows_c])
        out["1c_within_sector_year"][name] = {"weighted_within_cell_rho": v, "range": [lo, hi], "valid_draws": nv, "overall_rho": overall}
    c1, c2 = out["1c_within_sector_year"]["draw1"], out["1c_within_sector_year"]["draw2"]
    ok = all(c["weighted_within_cell_rho"] >= 0.08 and c["range"][0] > 0 for c in (c1, c2))
    out["1c_reading"] = "B already ranks within sector-year" if ok else "B's ranking is mostly across sectors"
    # 1d
    by = {}
    for r in sorted(rows_c, key=lambda r: (r["ticker"], r["date"])): by.setdefault(r["ticker"], []).append(r)
    chg = []
    for t, xs in by.items():
        for prev, cur in zip(xs, xs[1:]): chg.append({"ticker": t, "ret": cur["ret"], "d1": cur["b1"] - prev["b1"], "d2": cur["b2"] - prev["b2"]})
    out["1d_call_over_call"] = {"n": len(chg)}
    for name, key in (("draw1", "d1"), ("draw2", "d2")):
        rho = lambda s, k=key: A.spearman([x[k] for x in s], [x["ret"] for x in s])
        lo, hi, _ = A.boot(chg, rho); out["1d_call_over_call"][name] = {"rho": rho(chg), "range": [lo, hi]}
    (C.STATE / "sector_diagnostics.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("sector_map_counts", "1b_top_cells_by_winner_share_min12", "1c_within_sector_year", "1c_reading", "1d_call_over_call")}, indent=1, default=float))


if __name__ == "__main__":
    main()
