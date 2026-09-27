#!/usr/bin/env python3
"""p5p1_solar_check.py -- Step 1a: for companies whose SIC hides a solar/storage business, fetch the latest annual report from EDGAR (10-K; 20-F/40-F for foreign filers)
and quote the first sentence that says solar or storage. Output: p5-phase1/solar_candidates.json. Reused docs are saved under analysis/data/evals/p5_filings/docs/."""
import sys, json, re
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import p5p1_common as C
CAND = ["RUN", "NOVA", "SPWR", "AMPX", "EOSE", "QS", "ENVX", "SUNW", "SEDG", "FSLR", "ARRY", "SHLS", "JKS", "CSIQ", "MAXNQ", "BLDP", "AMSC"]
tk = C.tickers_json(); KNOWN = {"NOVA": 1772695, "SUNW": 1172631}
KW = re.compile(r"\bsolar\b|energy storage|battery storage|storage system|lithium-ion|lithium-metal|battery|batteries", re.I)
out = {}
for orig, w, sp in C.universe():
    if w not in CAND: continue
    cik = int(tk[w]["cik_str"]) if w in tk else KNOWN[w]
    d = json.loads((C.EV / "submissions" / f"CIK{cik:010d}.json").read_text()); r = d["filings"]["recent"]
    rows = [(f, dt, a, p) for f, dt, a, p in zip(r["form"], r["filingDate"], r["accessionNumber"], r["primaryDocument"]) if f in ("10-K", "20-F", "40-F")]
    if not rows: out[w] = {"sic": d.get("sic"), "note": "no annual report in recent list"}; continue
    f, dt, acc, prim = max(rows, key=lambda x: x[1])
    fn = C.EV / "docs" / f"{w}_{f}_{dt}.htm"
    if not fn.exists():
        st, b = C.sec_get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{prim}")
        if st != 200: out[w] = {"sic": d.get("sic"), "note": f"HTTP {st}"}; continue
        fn.write_bytes(b)
    text = C.plain(fn.read_text(errors="replace"))
    m0 = [m.start() for m in re.finditer(r"Item\s*1\.?\s*(?:Description of )?Business|Business Overview|Overview", text)]
    start = m0[1] if len(m0) > 1 else (m0[0] if m0 else 0)
    zone = text[start: start + 60000]
    sents = re.split(r"(?<=[.!?])\s+", zone)
    q = next((s for s in sents if KW.search(s) and 40 < len(s) < 500), None)
    out[w] = {"name": d.get("name"), "sic": d.get("sic"), "sic_description": d.get("sicDescription"), "form": f, "filed": dt, "quote": q, "quote_verbatim_in_text": bool(q and q in text)}
    print(w, d.get("sic"), f, dt, "|", (q or "")[:230])
(C.STATE / "solar_candidates.json").write_text(json.dumps(out, indent=1)); print("requests used", C.prog()["edgar_requests_used"])
