#!/usr/bin/env python3
"""
p5p2a_gaps.py -- prompts/P5-phase2a-tight-map.md Step 4 ($0 + up to 20 SEC requests for XOM's pre-2025 10-Ks).
4a: regex pass over saved 10-K text for anonymised-customer disclosures ("one customer" / "a single customer" / "Customer A" + a revenue %). No model.
4b: fetch XOM's 2019-2025 10-Ks under its pre-2025 CIK; report Competition/Customer heading search only. No extraction re-run.
"""
import sys, re, json, html, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
REPO = C.REPO
DOCS = REPO / "analysis/data/evals/p5_filings/docs"
STATE = REPO / "analysis/data/run_state/p5-phase2a"
ANON = re.compile(r"(one customer|a single customer|Customer [A-Z0-9]\b)[^.]{0,200}?\b\d{1,3}(?:\.\d+)?\s*%", re.I)


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))))


def main4a():
    from collections import defaultdict
    by_year = defaultdict(set); quotes = []
    for f in sorted(glob.glob(str(DOCS / "*"))):
        name = Path(f).name
        m = re.match(r"([A-Z0-9]+)_([\w/]+?)_(\d{4})-\d\d-\d\d_", name)
        if not m: continue
        w, form, yr = m.groups()
        text = plain(open(f, errors="replace").read())
        hits = list(ANON.finditer(text))
        if hits:
            by_year[yr].add(w)
            if len(quotes) < 5: quotes.append({"company": w, "filed_year": yr, "quote": hits[0].group(0)[:300]})
    out = {"filers_by_year": {y: sorted(v) for y, v in sorted(by_year.items())}, "n_filers_by_year": {y: len(v) for y, v in sorted(by_year.items())},
           "n_distinct_filers_any_year": len({w for v in by_year.values() for w in v}), "sample_quotes": quotes}
    (STATE / "gaps_4a_anonymised.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))


def main4b():
    tk = C.tickers_json(); C.STATE = STATE; C.PROG = STATE / "progress.json"; C.SEC_CAP = 400
    # XOM's pre-2025 CIK: 0000034088 (Exxon Mobil Corporation, long-standing; the current-resolution CIK from company_tickers.json differs)
    cik = 34088
    st, b = C.sec_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    if st != 200:
        print("XOM submissions fetch failed", st); return
    d = json.loads(b); r = d["filings"]["recent"]
    tenk = [{"form": f, "filed": x, "accession": a, "primary": p} for f, x, a, p in zip(r["form"], r["filingDate"], r["accessionNumber"], r["primaryDocument"]) if f == "10-K" and "2019-01-01" <= x <= "2025-12-31"]
    print("XOM name", d.get("name"), "sic", d.get("sic"), d.get("sicDescription"), "10-Ks found", len(tenk))
    out = {"name": d.get("name"), "sic": d.get("sic"), "cik": cik, "tenk_filed": [x["filed"] for x in tenk]}
    if tenk:
        latest = max(tenk, key=lambda x: x["filed"])
        st2, b2 = C.sec_get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{latest['accession'].replace('-', '')}/{latest['primary']}")
        if st2 == 200:
            text = plain(b2.decode("utf-8", "replace"))
            heads = {name: len(re.findall(pat, text)) for name, pat in {"Customers": r"\bCustomers\b", "Competition": r"\bCompetition\b", "Supply/Manufacturing": r"\b(?:Suppliers|Supply Chain|Manufacturing)\b"}.items()}
            out["latest_10k"] = {"filed": latest["filed"], "heading_hits": heads}
            print("latest 10-K", latest["filed"], "heading hits", heads)
    (STATE / "gaps_4b_xom.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main4a(); main4b()
