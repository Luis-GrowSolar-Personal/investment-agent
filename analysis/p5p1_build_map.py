#!/usr/bin/env python3
"""
p5p1_build_map.py -- prompts/P5-phase1-peer-map.md Step 4 ($0). Resolves each extraction's named_company text to a ticker via the name list, normalises every ticker (own and peer)
through TICKER_ALIASES.json, applies HAND_MAP.csv links (tagged HAND, from p5_handmap_check.py's hand_links.json), and writes the directional peer_links.csv.
A filing link is valid from its filing date until that company's NEXT 10-K filing date (open-ended if none). A call link is valid from the call date onward. Both are also
stored reversed (the peer's view of the filer/caller) so lookups work either direction, per the prompt. Recurrence = distinct (company, peer, relation, source_type) count.
"""
import sys, json, csv, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p5p1_prefilter as P
import p5p1_extract as X
REPO = C.REPO
INVERSE = {"CUSTOMER": "SUPPLIER", "SUPPLIER": "CUSTOMER", "COMPETITOR": "COMPETITOR", "PARTNER": "PARTNER"}


def resolve(named, names_map, own_set):
    best = None
    for nm, (tk, src) in names_map.items():
        if nm == named or nm.rstrip(".") == named.rstrip("."):
            if tk not in own_set: return tk, nm
    # fallback: named text contains a known name (extraction sometimes adds Inc./Corp.)
    for nm, (tk, src) in sorted(names_map.items(), key=lambda x: -len(x[0])):
        if nm in named and tk not in own_set:
            return tk, nm
    return None, None


def next_10k_date(idx, w):
    ds = sorted(x["filed"] for x in idx.get(w, {}).get("filings", []) if x["form"] == "10-K")
    return ds


def main():
    names_map, _ = P.build()
    am = C.alias_map()
    norm = lambda t: am.get(t, t)
    idx = json.loads((C.STATE / "filings_index.json").read_text())
    paras = {json.loads(l)["para_id"]: json.loads(l) for l in open(C.EV / "filing_paras.jsonl")}
    passages = {json.loads(l)["passage_id"]: json.loads(l) for l in open(C.EV / "call_passages.jsonl")}
    full_F = {json.loads(l)["custom_id"]: json.loads(l) for l in open(C.STATE / "raw_F_full.jsonl")}
    for l in open(C.STATE / "raw_F_retry.jsonl") if (C.STATE / "raw_F_retry.jsonl").exists() else []:
        r = json.loads(l); full_F[r["custom_id"]] = r
    full_C = {json.loads(l)["custom_id"]: json.loads(l) for l in open(C.STATE / "raw_C_full.jsonl")}
    for l in open(C.STATE / "raw_C_retry.jsonl") if (C.STATE / "raw_C_retry.jsonl").exists() else []:
        r = json.loads(l); full_C[r["custom_id"]] = r

    rows = []
    unresolved = set()
    # --- filings
    for cid, r in full_F.items():
        if "error" in r or r.get("stop") == "max_tokens": continue
        L = X.parse(r.get("content", ""))
        if L is None: continue
        _, para_id, co = cid.split("__")
        e = paras[para_id]; own = P.own_tickers(co)
        for x in L:
            rel = x.get("relation")
            if rel not in ("CUSTOMER", "SUPPLIER", "COMPETITOR", "PARTNER") or not X.quote_ok(x.get("quote"), e["text"]): continue
            tk, matched = resolve(x.get("named_company", ""), names_map, own)
            if tk is None: unresolved.add(x.get("named_company", "")); continue
            peer = norm(tk); company = norm(co)
            if peer == company: continue
            for src in e["sources"]:
                if src["company"] != co: continue
                nxt = [d for d in next_10k_date(idx, co) if d > src["filed"]]
                rows.append({"company": company, "peer": peer, "relation_from_company_view": rel, "source_type": "FILING", "source_date": src["filed"],
                            "source_valid_until": min(nxt) if nxt else "", "source_id": f"{src['form']}:{src['accession']}", "quote": x["quote"]})
    # --- calls
    for cid, r in full_C.items():
        if "error" in r or r.get("stop") == "max_tokens": continue
        L = X.parse(r.get("content", ""))
        if L is None: continue
        pid = cid.split("__", 1)[1]; e = passages[pid]; co = e["call"]; own = P.own_tickers(co)
        for x in L:
            rel = x.get("relation")
            if rel not in ("CUSTOMER", "SUPPLIER", "COMPETITOR", "PARTNER") or not X.quote_ok(x.get("quote"), e["text"]): continue
            tk, matched = resolve(x.get("named_company", ""), names_map, own)
            if tk is None: unresolved.add(x.get("named_company", "")); continue
            peer = norm(tk); company = norm(co)
            if peer == company: continue
            rows.append({"company": company, "peer": peer, "relation_from_company_view": rel, "source_type": "CALL", "source_date": e["date"],
                        "source_valid_until": "", "source_id": f"{co}_{e['date']}", "quote": x["quote"]})
    # recurrence + single_source, before reversing/hand
    key = lambda r: (r["company"], r["peer"], r["relation_from_company_view"], r["source_type"])
    from collections import defaultdict
    recur = defaultdict(set)
    for r in rows: recur[key(r)].add((r["source_id"], r["source_date"]))
    for r in rows: r["recurrence"] = len(recur[key(r)]); r["single_source"] = r["recurrence"] <= 1

    # reversed rows for lookups
    rev = []
    for r in rows:
        if r["relation_from_company_view"] not in INVERSE: continue
        rev.append({"company": r["peer"], "peer": r["company"], "relation_from_company_view": INVERSE[r["relation_from_company_view"]], "source_type": r["source_type"],
                   "source_date": r["source_date"], "source_valid_until": r["source_valid_until"], "source_id": r["source_id"] + "#rev", "quote": r["quote"],
                   "recurrence": r["recurrence"], "single_source": r["single_source"], "reversed_of": key(r)})
    for r in rows: r["reversed_of"] = None

    # hand links
    hand = json.load(open(C.STATE / "hand_links.json"))["links"]
    hand_rows = []
    for h in hand:
        co, peer = norm(h["company"]), norm(h["linked"])
        if peer == co: continue
        hand_rows.append({"company": co, "peer": peer, "relation_from_company_view": h["link_type"], "source_type": "HAND", "source_date": f"{h['valid_from_year']}-01-01",
                          "source_valid_until": f"{h['valid_to_year']}-12-31" if h["valid_to_year"] else "", "source_id": f"hand_map_line_{h['csv_line']}", "quote": h.get("note", ""),
                          "recurrence": 1, "single_source": True, "reversed_of": None})
        if h["link_type"] in INVERSE:
            hand_rows.append({"company": peer, "peer": co, "relation_from_company_view": INVERSE[h["link_type"]], "source_type": "HAND", "source_date": f"{h['valid_from_year']}-01-01",
                              "source_valid_until": f"{h['valid_to_year']}-12-31" if h["valid_to_year"] else "", "source_id": f"hand_map_line_{h['csv_line']}#rev", "quote": h.get("note", ""),
                              "recurrence": 1, "single_source": True, "reversed_of": None})

    allr = rows + rev + hand_rows
    fields = ["company", "peer", "relation_from_company_view", "source_type", "source_date", "source_valid_until", "source_id", "quote", "recurrence", "single_source"]
    with open(C.STATE / "peer_links.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(allr)
    out = {"filing_links": len(rows) - sum(1 for r in rows if False), "n_filing_direct": sum(1 for r in rows if r["source_type"] == "FILING"),
           "n_call_direct": sum(1 for r in rows if r["source_type"] == "CALL"), "n_reversed": len(rev), "n_hand": len(hand_rows), "n_total_rows": len(allr),
           "unresolved_named_companies_sample": sorted(unresolved)[:60], "unresolved_count": len(unresolved)}
    (C.STATE / "build_map_report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
