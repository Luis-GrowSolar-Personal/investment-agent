#!/usr/bin/env python3
"""
p5b_filings.py -- prompts/P5-phase0b-link-sources.md Step 1 (<= 15 SEC EDGAR requests, 1/s, User-Agent from .env SEC_USER_AGENT, never logged).
Fetches company_tickers.json once (saved, gitignored, for Step 2a) and the 2022-filed 10-K of MU (accession from phase 0's edgar_probe.json), INTC, ENPH, NOW.
For a company whose recent-filings list does not reach 2022, only the overflow page whose date range contains 2022 is fetched (phase 0 JPM lesson).
Output: analysis/data/run_state/p5-phase0b/filings_probe.json. The 10-K text is saved under gitignored analysis/data/evals/p5_phase0b/.
"""
import sys, json, re, time, html, urllib.request, urllib.error
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import p5b_names as N
STATE = REPO / "analysis/data/run_state/p5-phase0b"
EV = REPO / "analysis/data/evals/p5_phase0b"; EV.mkdir(parents=True, exist_ok=True)
CAP = 15
UA = next(l.split("=", 1)[1].strip().strip('"').strip("'") for l in (REPO / ".env").read_text().splitlines() if l.startswith("SEC_USER_AGENT="))
LOG, LAST = [], [0.0]


def get(url):
    assert len(LOG) < CAP, "request cap"
    w = 1.05 - (time.time() - LAST[0])
    if w > 0: time.sleep(w)
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"}), timeout=60) as r: st, b = r.status, r.read()
    except urllib.error.HTTPError as e: st, b = e.code, e.read()
    LAST[0] = time.time(); LOG.append({"n": len(LOG) + 1, "url": url, "status": st, "bytes": len(b), "elapsed_s": round(time.time() - t0, 2)})
    p = json.loads((STATE / "progress.json").read_text()); p["edgar_requests_used"] = len(LOG); (STATE / "progress.json").write_text(json.dumps(p, indent=2))
    if st in (403, 429): raise SystemExit(f"SEC HARD STOP {st} {url}")
    return st, b


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))))


HEADS = {"Customers": r"\bCustomers\b", "Suppliers/Supply Chain": r"\b(?:Suppliers|Supply Chain|Manufacturing|Raw Materials|Sources and Availability|Sole[- ]Source)\b", "Competition": r"\bCompetition\b"}
ANON = r"Customer [A-Z0-9]\b|one customer|two customers|three customers|customers? accounted for|largest customers?|no (?:single )?customer accounted|\d+% of (?:our )?(?:net |total )?(?:revenue|sales)"


def sentence(text, pos):
    a = text.rfind(". ", 0, pos); s = a + 2 if a >= 0 else max(0, pos - 200)
    e = text.find(". ", pos); e = e + 1 if e >= 0 else pos + 300
    return text[max(s, pos - 400): min(e, pos + 500)].strip()


def analyse(text, matcher, names, own, own_names):
    starts = [m.start() for m in re.finditer(r"Item\s*1\.?\s*Business", text, re.I)]
    ends = [m.start() for m in re.finditer(r"Item\s*1A\.?\s*Risk Factors", text, re.I)]
    span = max(((s, min([e for e in ends if e > s] or [len(text)])) for s in starts), key=lambda p: p[1] - p[0], default=(0, len(text)))
    biz = text[span[0]:span[1]]
    out = {"item1_chars": len(biz), "sections": {}, "anonymous_customer_evidence": [], "matches_in_sections": [], "matches_in_item1": []}
    covered = []
    for name, pat in HEADS.items():
        occ = [m.start() for m in re.finditer(pat, biz)]
        out["sections"][name] = {"heading_hits_in_item1": len(occ), "first_offsets": occ[:5]}
        for o in occ: covered.append((o, min(len(biz), o + 3500)))
    def hits(zone, base):
        res = []
        for m in matcher.finditer(zone):
            nm = m.group(1); tkr = names[nm][0]
            if tkr == own or tkr in own_names: continue
            res.append({"name": nm, "ticker": tkr, "src": names[nm][1], "offset": base + m.start(), "sentence": sentence(zone, m.start())[:500]})
        return res
    seen = set()
    for a, b in covered:
        for h in hits(biz[a:b], a):
            k = (h["name"], h["sentence"][:80])
            if k not in seen: seen.add(k); out["matches_in_sections"].append(h)
    seen = set()
    for h in hits(biz, 0):
        k = (h["name"], h["sentence"][:80])
        if k not in seen: seen.add(k); out["matches_in_item1"].append(h)
    for m in list(re.finditer(ANON, biz))[:6]: out["anonymous_customer_evidence"].append({"offset": m.start(), "sentence": sentence(biz, m.start())[:400]})
    return out


def main():
    out = {"requests": LOG, "companies": {}}
    st, b = get("https://www.sec.gov/files/company_tickers.json"); (EV / "company_tickers.json").write_bytes(b)
    tk = {v["ticker"]: v for v in json.loads(b).values()}
    names = N.build(); matcher = N.matcher(names)
    out["name_list"] = {"names": len(names), "from_sec": sum(1 for v in names.values() if v[1] == "sec"), "from_aliases": sum(1 for v in names.values() if v[1] == "alias")}
    p0 = json.loads((STATE.parent / "p5-phase0/edgar_probe.json").read_text())
    plan = {}
    mu = [r for r in p0["tickers"]["MU"]["tenk_2019_2025"] if r["filed"].startswith("2022")][0]
    plan["MU"] = {"cik": p0["tickers"]["MU"]["cik"], "filed": mu["filed"], "accession": mu["accession"], "primary": mu["primary"], "source": "phase 0 edgar_probe.json"}
    for t in ("INTC", "ENPH", "NOW"):
        cik = int(tk[t]["cik_str"])
        st, b = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"); sub = json.loads(b); rec = sub["filings"]["recent"]
        rows = list(zip(rec["form"], rec["filingDate"], rec["accessionNumber"], rec["primaryDocument"]))
        if not any(f == "10-K" and d.startswith("2022") for f, d, a, p in rows):
            for f in sub["filings"].get("files", []):
                if (f.get("filingFrom") or "") <= "2022-12-31" and (f.get("filingTo") or "9999") >= "2022-01-01":
                    st2, b2 = get(f"https://data.sec.gov/submissions/{f['name']}"); pg = json.loads(b2)
                    rows += list(zip(pg["form"], pg["filingDate"], pg["accessionNumber"], pg["primaryDocument"])); break
        c = [r for r in rows if r[0] == "10-K" and r[1].startswith("2022")]
        assert c, f"no 2022 10-K for {t}"
        plan[t] = {"cik": cik, "filed": c[0][1], "accession": c[0][2], "primary": c[0][3], "source": "submissions"}
    for t, pl in plan.items():
        acc = pl["accession"].replace("-", ""); url = f"https://www.sec.gov/Archives/edgar/data/{int(pl['cik'])}/{acc}/{pl['primary']}"
        st, b = get(url); raw = b.decode("utf-8", errors="replace"); (EV / f"{t}_10K_{pl['filed']}.html").write_text(raw)
        text = plain(raw)
        own_names = {t} | {v[0] for k, v in names.items() if k in (tk[t]["title"].title(), N.clean(tk[t]["title"]).title(), N.clean(tk[t]["title"]))} if t in tk else {t}
        r = analyse(text, matcher, names, t, own_names)
        r.update({"filed": pl["filed"], "accession": pl["accession"], "primary_document": pl["primary"], "status": st, "bytes": len(b), "text_chars": len(text), "plan_source": pl["source"]})
        out["companies"][t] = r
    out["requests_used"] = len(LOG); out["cap"] = CAP
    (STATE / "filings_probe.json").write_text(json.dumps(out, indent=1))
    print("requests", len(LOG), "names", out["name_list"])
    for t, r in out["companies"].items():
        print(f"\n=== {t} filed {r['filed']} chars {r['text_chars']} item1 {r['item1_chars']}")
        print(" sections:", {k: v["heading_hits_in_item1"] for k, v in r["sections"].items()})
        print(" anon evidence:", [e["sentence"][:140] for e in r["anonymous_customer_evidence"][:3]])
        for h in r["matches_in_sections"][:14]: print("  *", h["name"], h["ticker"], "|", h["sentence"][:260])
        print("  (item1-wide matches:", len(r["matches_in_item1"]), ")")


if __name__ == "__main__":
    main()
