#!/usr/bin/env python3
"""
p5p1_filings_fetch.py -- Step 2a. For each of the 164 corpus companies list every 10-K and 10-K/A filed 2019-01-01..2025-12-31 (recent list + only the overflow pages whose date range
overlaps a window where a 10-K is expected: +/-45 days around the company's known 10-K month-day, default Jan 15..Mar 31), then fetch the documents.
10-K first for all companies, then 10-K/A while budget remains (cap 1,600 requests overall). Resume-safe (skips saved files). Text saved gitignored under analysis/data/evals/p5_filings/docs/.
Index: run_state/p5-phase1/filings_index.json (company, form, filed, accession, primary document, saved-or-not). Foreign filers (20-F/40-F) have no 10-K and are reported, not fetched.
"""
import sys, json, glob, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
D = lambda s: dt.date.fromisoformat(s)
KN = {"NOVA": 1772695, "SUNW": 1172631}
IDX = C.STATE / "filings_index.json"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9        # max requests this invocation


def cik_of(w, tk): return int(tk[w]["cik_str"]) if w in tk else KN.get(w)


def list_filings(w, cik):
    d = json.loads((C.EV / "submissions" / f"CIK{cik:010d}.json").read_text()); r = d["filings"]["recent"]
    rows = [{"form": f, "filed": x, "accession": a, "primary": p} for f, x, a, p in zip(r["form"], r["filingDate"], r["accessionNumber"], r["primaryDocument"]) if f in ("10-K", "10-K/A")]
    oldest = min(r["filingDate"]); files = d["filings"].get("files", [])
    if oldest > "2019-01-01" and files:
        known = [D(x["filed"]) for x in rows if x["form"] == "10-K"]
        md = sorted((k.month, k.day) for k in known)[len(known) // 2] if known else (2, 25)
        pages = []
        for y in range(2019, int(oldest[:4]) + 1):
            c = dt.date(y, *md) if not known else dt.date(y, md[0], min(md[1], 28))
            lo, hi = (c - dt.timedelta(days=45), c + dt.timedelta(days=45)) if known else (dt.date(y, 1, 15), dt.date(y, 3, 31))
            for f in files:
                a, b = D(f["filingFrom"]), D(f["filingTo"])
                if a <= hi and b >= lo and f["name"] not in pages and b.isoformat() < oldest: pages.append(f["name"])
        for name in pages:
            fn = C.EV / "submissions" / name
            if not fn.exists():
                if C.prog()["edgar_requests_used"] >= C.SEC_CAP - 5: break
                st, b = C.sec_get(f"https://data.sec.gov/submissions/{name}")
                if st != 200: continue
                fn.write_bytes(b)
            pg = json.loads(fn.read_text())
            rows += [{"form": f, "filed": x, "accession": a, "primary": p} for f, x, a, p in zip(pg["form"], pg["filingDate"], pg["accessionNumber"], pg["primaryDocument"]) if f in ("10-K", "10-K/A")]
    seen, out = set(), []
    for x in sorted(rows, key=lambda x: x["filed"]):
        if "2019-01-01" <= x["filed"] <= "2025-12-31" and x["accession"] not in seen: seen.add(x["accession"]); out.append(x)
    return out, d.get("name")


def main():
    tk = C.tickers_json(); index = {}
    for orig, w, sp in C.universe():
        cik = cik_of(w, tk)
        if cik is None: index[w] = {"split": sp, "cik": None, "filings": [], "note": "unresolved"}; continue
        fl, name = list_filings(w, cik); index[w] = {"split": sp, "cik": cik, "name": name, "filings": fl}
    tot = sum(len(v["filings"]) for v in index.values())
    print("companies", len(index), "10-K+10-K/A listed", tot, "10-K only", sum(1 for v in index.values() for x in v["filings"] if x["form"] == "10-K"), "requests used", C.prog()["edgar_requests_used"])
    # fetch: 10-K first, then 10-K/A
    used0 = C.prog()["edgar_requests_used"]
    for form in ("10-K", "10-K/A"):
        for w, v in index.items():
            for x in v["filings"]:
                if x["form"] != form: continue
                fn = C.EV / "docs" / f"{w}_{form.replace('/', '')}_{x['filed']}_{x['accession']}.htm"
                x["saved"] = fn.name if fn.exists() else None
                if fn.exists(): continue
                if C.prog()["edgar_requests_used"] - used0 >= LIMIT or C.prog()["edgar_requests_used"] >= C.SEC_CAP - 5: break
                st, b = C.sec_get(f"https://www.sec.gov/Archives/edgar/data/{v['cik']}/{x['accession'].replace('-', '')}/{x['primary']}")
                x["status"] = st
                if st == 200: fn.write_bytes(b); x["saved"] = fn.name
    for v in index.values():
        for x in v["filings"]:
            if not x.get("saved"):
                fn = C.EV / "docs" / f"{'x'}"
    IDX.write_text(json.dumps(index, indent=1))
    saved = sum(1 for v in index.values() for x in v["filings"] if x.get("saved"))
    print("saved", saved, "of", tot, "requests used", C.prog()["edgar_requests_used"])


if __name__ == "__main__":
    main()
