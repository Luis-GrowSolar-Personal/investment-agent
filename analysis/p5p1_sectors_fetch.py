#!/usr/bin/env python3
"""p5p1_sectors_fetch.py -- Step 1a: EDGAR submissions JSON (SIC code) for the 164 corpus companies (+ELV, GOOG, PARA if in train; they resolve via the alias file). Resume-safe:
skips files already saved under analysis/data/evals/p5_filings/submissions/. Records unresolved tickers. Submissions files are reused by Step 2a (10-K lists)."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import p5p1_common as C
KNOWN_CIK = {"NOVA": 1772695, "SUNW": 1172631}     # SUNW=Sunworks (CIK found via EDGAR company browse; the first guess 1120970 was Comstock Inc., discarded)     
tk = C.tickers_json(); done = 0; unresolved = []; names = {}
for orig, work, sp in C.universe():
    cik = int(tk[work]["cik_str"]) if work in tk else KNOWN_CIK.get(work)
    if cik is None: unresolved.append({"symbol": orig, "working": work, "split": sp, "why": "not in SEC company_tickers.json"}); continue
    f = C.EV / "submissions" / f"CIK{cik:010d}.json"
    if not f.exists():
        st, b = C.sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        if st != 200: unresolved.append({"symbol": orig, "working": work, "split": sp, "why": f"submissions HTTP {st}"}); continue
        f.write_bytes(b); done += 1
    d = json.loads(f.read_text()); names[work] = (d.get("name"), d.get("sic"), d.get("sicDescription"))
print("fetched", done, "unresolved", unresolved, "requests used", C.prog()["edgar_requests_used"])
for w in ("NOVA", "SUNW"): print(w, names.get(w))
