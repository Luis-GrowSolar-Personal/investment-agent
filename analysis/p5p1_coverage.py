#!/usr/bin/env python3
"""
p5p1_coverage.py -- prompts/P5-phase1-peer-map.md Step 5 ($0 model; up to 150 vendor event-list calls). For each of the 1,217 train targets, find eligible peers (a
FILING/CALL/HAND link valid on the target's date) with a call dated strictly before the target and within 120 days. On-disk peers use their saved transcript dates.
Peers not on disk (holdout, non-corpus) get ONE vendor events call each (no transcripts), prioritised by how many train targets they would cover, capped at 150.
Coverage counted on FILING+CALL only (headline); HAND reported separately, never mixed in.
"""
import sys, json, csv
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict, Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p5p1_step1 as S1

D_ = date.fromisoformat
TD = C.C2 / "transcripts"


def load_links():
    rows = list(csv.DictReader(open(C.STATE / "peer_links.csv")))
    for r in rows: r["single_source"] = r["single_source"] == "True"
    return rows


def valid_on(r, target_date):
    if r["source_date"] > target_date: return False
    if r["source_valid_until"] and r["source_valid_until"] <= target_date: return False
    return True


def on_disk_dates(w):
    d = TD / w
    return sorted(f.stem for f in d.glob("*.json")) if d.is_dir() else []


def main():
    links = load_links()
    calls = [c for c in __import__("p6_output_format_analysis").load_calls(C.REPO / "analysis/data/run_state/p6-output-format-round/calls.csv") if c["fwd_rel_ret_tradeable"] is not None and c["b_score"] is not None]
    smap = {r["symbol"]: r["final_group"] for r in csv.DictReader(open(C.REPO / "docs/peers/SECTOR_MAP.csv"))}
    by_company = defaultdict(list)
    for r in links: by_company[r["company"]].append(r)

    # peer candidates and how many targets they'd help, per source_type kind (excluding HAND for the priority count)
    on_disk_cache = {}
    def dates_of(w):
        if w not in on_disk_cache: on_disk_cache[w] = on_disk_dates(w)
        return on_disk_cache[w]

    peer_demand = Counter()
    for c in calls:
        for r in by_company.get(c["ticker"], []):
            if r["source_type"] == "HAND": continue
            if valid_on(r, c["call_date"]) and not dates_of(r["peer"]):
                peer_demand[r["peer"]] += 1
    prioritized = [p for p, _ in peer_demand.most_common()]
    fetched, unchecked = {}, []
    for p in prioritized:
        if len(fetched) >= 150: unchecked.append(p); continue
        fetched[p] = None  # placeholder; filled by vendor call below

    # vendor calls (events only)
    from dotenv import load_dotenv
    load_dotenv(C.REPO / ".env")
    sys.path.insert(0, str(C.REPO / "analysis" / "ec_fidelity_benchmark_1"))
    import driver as ecf
    prog_path = C.STATE / "vendor_progress.json"
    if not prog_path.exists(): prog_path.write_text(json.dumps({"calls_used_total": 0}))
    vp = json.loads(prog_path.read_text())

    def vget(endpoint, params):
        import time, os, urllib.request, urllib.parse, urllib.error
        nonlocal vp
        wait = ecf.MIN_SPACING_SECONDS - (time.time() - vp.get("last_ts", 0))
        if wait > 0: time.sleep(wait)
        url = f"https://v2.api.earningscall.biz/{endpoint}?" + urllib.parse.urlencode({**params, "apikey": os.environ["ECB_API_KEY"]})
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r: st, b = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e: st, b = e.code, e.read().decode("utf-8", "replace")
        vp["last_ts"] = time.time(); vp["calls_used_total"] = vp.get("calls_used_total", 0) + 1; prog_path.write_text(json.dumps(vp))
        if st in (401, 429): raise SystemExit(f"vendor HARD STOP {st} {endpoint}")
        try: return st, json.loads(b)
        except json.JSONDecodeError: return st, b

    st, symtxt = vget("symbols-v2.txt", {}); symtab = {}
    for line in symtxt.splitlines() if isinstance(symtxt, str) else []:
        parts = line.split("\t")
        if len(parts) >= 2: symtab.setdefault(parts[1].upper(), []).append(parts[0])
    am = C.alias_map(); rev_alias = {v: k for k, v in am.items()}
    checked_dates = {}
    for p in list(fetched):
        if vp.get("calls_used_total", 0) >= 150: unchecked.append(p); del fetched[p]; continue
        idx = symtab.get(p) or symtab.get(rev_alias.get(p, p))
        if not idx: fetched[p] = []; continue
        exch = ecf.EXCHANGES_IN_ORDER[int(idx[0])]
        st, ev = vget("events", {"exchange": exch, "symbol": p})
        evs = [f"{e.get('year')}-{e.get('conference_date', '')[:10]}" for e in (ev.get("events", []) if isinstance(ev, dict) else [])]
        dts = sorted(e.get("conference_date", "")[:10] for e in (ev.get("events", []) if isinstance(ev, dict) else []) if e.get("conference_date"))
        fetched[p] = dts

    def peer_dates(w):
        if dates_of(w): return dates_of(w)
        return fetched.get(w, checked_dates.get(w, []))

    def eligible(target_ticker, target_date, kinds):
        out = []
        td = D_(target_date)
        for r in by_company.get(target_ticker, []):
            if r["source_type"] not in kinds or not valid_on(r, target_date): continue
            pd = peer_dates(r["peer"])
            best = None
            for d_ in pd:
                if d_ and d_ < target_date and (td - D_(d_)).days <= 120:
                    if best is None or d_ > best: best = d_
            if best: out.append({**r, "peer_call_date": best})
        return out

    out = {"vendor_calls_used": vp.get("calls_used_total", 0), "peers_fetched": len([p for p in fetched if fetched[p] is not None]), "peers_unchecked_at_cap": len(unchecked),
           "peer_priority_top10": prioritized[:10]}
    def cov(kinds, exclude_single=False, group_filter=None):
        n = 0; by_group = Counter(); by_lt = Counter()
        for c in calls:
            if group_filter and smap.get(c["ticker"], "other") != group_filter: continue
            el = eligible(c["ticker"], c["call_date"], kinds)
            if exclude_single: el = [e for e in el if not e["single_source"]]
            if el:
                n += 1; by_group[smap.get(c["ticker"], "other")] += 1
                if any(e["relation_from_company_view"] in ("CUSTOMER", "SUPPLIER") for e in el): by_lt["supply_chain"] += 1
                if any(e["relation_from_company_view"] == "COMPETITOR" for e in el): by_lt["shared_customer_competitor"] += 1
                if any(e["relation_from_company_view"] == "PARTNER" for e in el): by_lt["partner"] += 1
        return n, dict(by_group), dict(by_lt)

    n, bg, bl = cov(("FILING", "CALL")); out["headline_covered"] = n; out["headline_by_sector"] = bg; out["headline_by_link_type"] = bl
    n2, bg2, bl2 = cov(("FILING", "CALL"), exclude_single=True); out["excl_single_source"] = n2
    n3, bg3, bl3 = cov(("FILING", "CALL", "HAND")); out["with_hand_added"] = n3
    n4, _, _ = cov(("FILING",)); out["filing_only"] = n4
    n5, _, _ = cov(("CALL",)); out["call_only"] = n5
    def cov_sc():
        n = 0
        for c in calls:
            el = eligible(c["ticker"], c["call_date"], ("FILING", "CALL"))
            if any(e["relation_from_company_view"] in ("CUSTOMER", "SUPPLIER") for e in el): n += 1
        return n
    out["supply_chain_alone_covers"] = cov_sc()
    out["stop_rule_under_300"] = out["headline_covered"] < 300
    (C.STATE / "coverage_report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
