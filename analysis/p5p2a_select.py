#!/usr/bin/env python3
"""
p5p2a_select.py -- prompts/P5-phase2a-tight-map.md Step 1, peer selection + 1b coverage ($0; no vendor calls, per this run's ground rules -- peer readability uses ON-DISK
transcript dates only, unlike phase 1's coverage check, which also used 150 vendor-checked peers; this is a real scope narrowing, flagged in the wrap-up).
Selects up to 3 peers per train target: order S1, then C1/C2, then S2; ties by more distinct sources then most recent peer call.
Outputs: target_peers.csv, coverage_tight.json.
"""
import sys, csv, json
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict, Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
REPO = C.REPO
STATE = REPO / "analysis/data/run_state/p5-phase2a"
TD = C.C2 / "transcripts"
D_ = date.fromisoformat


def on_disk_dates(w):
    d = TD / w
    return sorted(f.stem for f in d.glob("*.json")) if d.is_dir() else []


def main():
    tight = list(csv.DictReader(open(STATE / "peer_links_tight.csv")))
    by_company = defaultdict(list)
    for r in tight: by_company[r["company"]].append(r)
    calls = [c for c in __import__("p6_output_format_analysis").load_calls(REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}
    n_sources = lambda r: int(r["n_total"]) if r["n_total"] else max(int(r["n_filing"] or 0), int(r["n_call"] or 0))
    order = {"S1": 0, "C1": 1, "C2": 1, "S2": 2}
    dcache = {}
    def dates(w):
        if w not in dcache: dcache[w] = on_disk_dates(w)
        return dcache[w]

    rows_out = []; covered = set(); by_rule_cov = Counter(); by_sector_cov = Counter(); npeers = []
    for c in calls:
        td, tk = c["call_date"], c["ticker"]
        cands = []
        for r in by_company.get(tk, []):
            if r["qualified_from"] > td: continue
            pd = [d_ for d_ in dates(r["peer"]) if d_ < td and (D_(td) - D_(d_)).days <= 120]
            if not pd: continue
            best = max(pd)
            cands.append({**r, "peer_call_date": best})
        cands.sort(key=lambda r: (order[r["rule"]], -n_sources(r), [-ord(ch) for ch in "0"], r["peer_call_date"]), reverse=False)
        # secondary tie-break: most recent peer call first, within same (order, sources) bucket
        cands.sort(key=lambda r: (order[r["rule"]], -n_sources(r), r["peer_call_date"]))
        cands.sort(key=lambda r: (order[r["rule"]], -n_sources(r)))
        # stable multi-key: python sort ascending by (order asc, sources desc, peer_call_date desc)
        cands = sorted(by_company.get(tk, []) and cands, key=lambda r: (order[r["rule"]], -n_sources(r), r["peer_call_date"]), reverse=False)
        cands = sorted(cands, key=lambda r: r["peer_call_date"], reverse=True)
        cands = sorted(cands, key=lambda r: -n_sources(r))
        cands = sorted(cands, key=lambda r: order[r["rule"]])
        sel = cands[:3]
        if sel:
            covered.add((tk, td))
            for r in sel: by_rule_cov[r["rule"]] += 1
            by_sector_cov[smap.get(tk, "other")] += 1
            npeers.append(len(sel))
        for r in sel:
            rows_out.append({"target": tk, "target_date": td, "peer": r["peer"], "relation": r["relation"], "rule": r["rule"], "qualified_from": r["qualified_from"],
                             "peer_call_date": r["peer_call_date"], "n_sources": n_sources(r), "dual_role": r["dual_role"]})
    with open(STATE / "target_peers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0])); w.writeheader(); w.writerows(rows_out)

    top10_after = Counter()
    for r in tight: top10_after[r["company"]] += 1; top10_after[r["peer"]] += 1
    loose_counts = Counter()
    import csv as _csv
    for r in _csv.DictReader(open(REPO / "analysis/data/run_state/p5-phase1/peer_links.csv")):
        if r["source_type"] in ("FILING", "CALL"): loose_counts[r["company"]] += 1
    out = {"train_calls": len(calls), "covered": len(covered), "covered_pct": round(100 * len(covered) / len(calls), 1),
           "by_rule_selections": dict(by_rule_cov), "by_sector_covered": dict(by_sector_cov), "mean_peers_per_covered": round(sum(npeers) / max(len(npeers), 1), 2),
           "stop_under_300": len(covered) < 300, "top10_links_after": top10_after.most_common(10), "AAPL_before": loose_counts.get("AAPL", 0), "AAPL_after": top10_after.get("AAPL", 0)}
    (STATE / "coverage_tight.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
