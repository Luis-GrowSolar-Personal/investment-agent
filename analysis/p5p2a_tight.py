#!/usr/bin/env python3
"""
p5p2a_tight.py -- prompts/P5-phase2a-tight-map.md Step 1 ($0 + up to 400 SEC requests for non-corpus peers' SIC codes).

Interpretation notes (documented, not guessed silently):
- peer_links.csv already contains both "direct" rows (a company's own filing/call naming a peer) and their algebraic
  mirror ("reversed") rows, generated in phase 1. A mirror row's source_date/source_valid_until/source_id still refer
  to the ORIGINAL document, so "either company's filing counts" (S1/S2) is answered by grouping ALL rows -- direct and
  mirrored -- by (company, peer, relation) and asking whether a FILING source exists / 3+ distinct calls exist.
- For C1/C2, "who named it" cannot be read off relation alone (COMPETITOR mirrors to COMPETITOR), so source ownership
  is recovered per row from source_id: FILING owner = the filer of that accession (filings_index.json); CALL owner =
  the ticker prefix of the source_id (TICKER_date). is_direct = (owner == row.company).
- "Total sources" for C1's >=2 test and C2's 2-per-side test are counted as distinct source_id (a call or a filing
  counted once even if it produced more than one matching passage).
- qualified_from is the date the relevant count threshold was FIRST met, computed from the sorted sequence of
  distinct qualifying source dates -- never an earlier date.

Outputs: peer_links_tight.csv, target_peers.csv, tight_report.json (all in run_state/p5-phase2a/).
"""
import sys, json, csv
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
REPO = C.REPO
P1 = REPO / "analysis/data/run_state/p5-phase1"
STATE = C.STATE.parent / "p5-phase2a"
C.STATE = STATE          # override the shared helper module's STATE/PROG so sec_get() counts against THIS run's cap (400), not phase 1's
C.PROG = STATE / "progress.json"
C.SEC_CAP = 400
RELS = {"CUSTOMER", "SUPPLIER", "COMPETITOR"}   # PARTNER/OTHER/HAND excluded


def load_owner_maps():
    idx = json.loads((P1 / "filings_index.json").read_text())
    acc2owner = {}
    for w, v in idx.items():
        for x in v["filings"]:
            acc2owner[x["accession"]] = w
    return acc2owner


def source_owner(row, acc2owner):
    sid = row["source_id"][:-5] if row["source_id"].endswith("#rev") else row["source_id"]
    if row["source_type"] == "FILING":
        acc = sid.split(":", 1)[1]
        return acc2owner.get(acc)
    if row["source_type"] == "CALL":
        return sid.split("_", 1)[0]
    return None


def load_rows():
    am = C.alias_map(); rows = []
    for r in csv.DictReader(open(P1 / "peer_links.csv")):
        if r["relation_from_company_view"] not in RELS: continue
        r["company"], r["peer"] = am.get(r["company"], r["company"]), am.get(r["peer"], r["peer"])
        rows.append(r)
    return rows


def sector_map():
    return {r["symbol"]: r["final_group"] for r in csv.DictReader(open(REPO / "docs/peers/SECTOR_MAP.csv"))}


def fetch_peer_sics(need):
    """SIC group for non-corpus peers that survive the OTHER rules (COMPETITOR candidates). Up to len(need) requests."""
    tk = C.tickers_json(); out = {}
    for w in sorted(need):
        if w.endswith("-none"): out[w] = "unknown"; continue          # already flagged not-US-listed in NAME_ALIASES
        if w not in tk: out[w] = "unknown"; continue
        cik = int(tk[w]["cik_str"])
        st, b = C.sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        if st != 200: out[w] = "unknown"; continue
        d = json.loads(b)
        out[w] = C.sic_group(d["sic"]) if d.get("sic") else "unknown"
    return out


def main():
    acc2owner = load_owner_maps(); rows = load_rows(); smap = sector_map()
    own_ticker_set = set(smap)  # corpus companies

    # group S1/S2 candidates
    sc = defaultdict(lambda: {"filing_ids": set(), "call_ids": set(), "filing_dates": [], "call_dates": [], "quotes": []})
    comp = defaultdict(lambda: {"owner_dates": defaultdict(set), "quote": None})   # key (company,peer) -> owner -> set of (source_id,date)
    for r in rows:
        key = (r["company"], r["peer"])
        if r["relation_from_company_view"] in ("CUSTOMER", "SUPPLIER"):
            e = sc[(r["company"], r["peer"], r["relation_from_company_view"])]
            if r["source_type"] == "FILING":
                e["filing_ids"].add(r["source_id"]); e["filing_dates"].append(r["source_date"])
            elif r["source_type"] == "CALL":
                e["call_ids"].add(r["source_id"]); e["call_dates"].append(r["source_date"])
            if not e["quotes"] or len(r["quote"]) < len(e["quotes"][0]): e["quotes"] = [r["quote"]]
        elif r["relation_from_company_view"] == "COMPETITOR":
            owner = source_owner(r, acc2owner)
            e = comp[key]
            e["owner_dates"][owner].add((r["source_id"], r["source_date"]))
            if e["quote"] is None: e["quote"] = r["quote"]

    # which non-corpus peers might survive C1/C2 (i.e. appear as `peer` in a COMPETITOR key)? fetch their SIC, cap 400
    need = {p for (co, p) in comp if p not in own_ticker_set and not p.endswith("-none")}
    fetched_sic = fetch_peer_sics(need) if need else {}
    def group_of(t): return smap.get(t) or fetched_sic.get(t) or ("unknown" if t.endswith("-none") else "unknown")

    tight = []
    # S1/S2
    for (co, pe, rel), e in sc.items():
        if e["filing_ids"]:
            qf = min(e["filing_dates"]); tight.append({"company": co, "peer": pe, "relation": rel, "rule": "S1", "source_type": "FILING+CALL(pooled)",
                                                       "qualified_from": qf, "n_filing": len(e["filing_ids"]), "n_call": len(e["call_ids"]), "quote": e["quotes"][0]})
        elif len(e["call_ids"]) >= 3:
            qf = sorted(e["call_dates"])[2]; tight.append({"company": co, "peer": pe, "relation": rel, "rule": "S2", "source_type": "CALL",
                                                            "qualified_from": qf, "n_filing": 0, "n_call": len(e["call_ids"]), "quote": e["quotes"][0]})
    # C1/C2
    for (co, pe), e in comp.items():
        n_self = len(e["owner_dates"].get(co, set())); n_peer = len(e["owner_dates"].get(pe, set()))
        total_ids = set().union(*e["owner_dates"].values()) if e["owner_dates"] else set()
        n_total = len(total_ids)
        same_sector = group_of(co) != "unknown" and group_of(co) == group_of(pe)
        c1 = same_sector and (n_self >= 1 or (n_self >= 1 and n_peer >= 1) or (n_peer >= 1 and n_self == 0 and False)) and n_total >= 2
        # "target named it, OR both named each other": self>=1  OR (self>=1 and peer>=1) -- the second is a subset of the first, so really just self>=1 (target's own doc names peer)
        c1 = same_sector and n_self >= 1 and n_total >= 2
        c2 = n_self >= 2 and n_peer >= 2
        if c1 or c2:
            dts_self = sorted(d for _, d in e["owner_dates"].get(co, set())); dts_peer = sorted(d for _, d in e["owner_dates"].get(pe, set()))
            dts_all = sorted(d for _, d in total_ids)
            if c2:
                qf = max(dts_self[1], dts_peer[1]); rule = "C2"
            else:
                qf = dts_all[1]; rule = "C1"
            tight.append({"company": co, "peer": pe, "relation": "COMPETITOR", "rule": rule, "source_type": "COMPETITOR",
                         "qualified_from": qf, "n_filing": None, "n_call": None, "n_self_named": n_self, "n_peer_named": n_peer, "n_total": n_total,
                         "sector_company": group_of(co), "sector_peer": group_of(pe), "quote": e["quote"]})

    # dual_role: pair also qualifies S1/S2 -> keep as supply chain, flag dual_role
    sc_pairs = {(t["company"], t["peer"]) for t in tight if t["rule"] in ("S1", "S2")}
    final = []
    for t in tight:
        if t["rule"] in ("C1", "C2") and (t["company"], t["peer"]) in sc_pairs: continue   # superseded by supply chain entry for this pair
        t["dual_role"] = (t["company"], t["peer"]) in {(x["company"], x["peer"]) for x in tight if x["rule"] in ("C1", "C2")} if t["rule"] in ("S1", "S2") else False
        final.append(t)

    fields = ["company", "peer", "relation", "rule", "qualified_from", "dual_role", "n_filing", "n_call", "n_self_named", "n_peer_named", "n_total", "sector_company", "sector_peer", "quote"]
    with open(STATE / "peer_links_tight.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(final)

    out = {"input_rows": len(rows), "tight_links": len(final), "by_rule": {r: sum(1 for t in final if t["rule"] == r) for r in ("S1", "S2", "C1", "C2")},
           "non_corpus_peers_sic_fetched": len(need), "sec_requests_used": C.prog().get("edgar_requests_used", 0)}
    (STATE / "tight_report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
