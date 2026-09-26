#!/usr/bin/env python3
"""
p5_edgar_probe.py -- prompts/P5-phase0-probes.md Step 2 ($0; <= 30 SEC EDGAR requests, 1 per second, User-Agent from .env SEC_USER_AGENT, never printed).
Tickers RUN, MU, JPM. Writes analysis/data/run_state/p5-phase0/edgar_probe.json. The RUN 2022 10-K text is saved under the gitignored
analysis/data/evals/p5_phase0_edgar/ and is not committed.
"""
import json, re, time, html, os, urllib.request, urllib.error
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "analysis/data/run_state/p5-phase0"
CAP = 30
UA = None
for line in (REPO / ".env").read_text().splitlines():
    if line.startswith("SEC_USER_AGENT="):
        UA = line.split("=", 1)[1].strip().strip('"').strip("'")
assert UA, "SEC_USER_AGENT missing from .env"
LOG, LAST = [], [0.0]


def get(url, binary=False):
    assert len(LOG) < CAP, "request cap reached"
    wait = 1.05 - (time.time() - LAST[0])
    if wait > 0: time.sleep(wait)
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    LAST[0] = time.time()
    LOG.append({"n": len(LOG) + 1, "url": url, "status": status, "bytes": len(body), "elapsed_s": round(time.time() - t0, 2)})
    p = json.loads((STATE / "progress.json").read_text()); p["edgar_requests_used"] = len(LOG); (STATE / "progress.json").write_text(json.dumps(p, indent=2))
    if status in (403, 429): raise SystemExit(f"SEC HARD STOP status={status} {url}")
    return status, body


def main():
    out = {"tickers": {}, "requests": LOG}
    st, b = get("https://www.sec.gov/files/company_tickers.json")
    tk = {v["ticker"]: v for v in json.loads(b).values()}
    for t in ("RUN", "MU", "JPM"):
        v = tk.get(t)
        out["tickers"][t] = {"resolved": bool(v), "cik": v["cik_str"] if v else None, "title": v["title"] if v else None}
    for t, info in out["tickers"].items():
        if not info["resolved"]: continue
        cik = f"{int(info['cik']):010d}"
        st, b = get(f"https://data.sec.gov/submissions/CIK{cik}.json"); sub = json.loads(b)
        rec = sub["filings"]["recent"]; rows = [{"form": f, "filed": d, "accession": a, "primary": p, "report_date": r} for f, d, a, p, r in zip(rec["form"], rec["filingDate"], rec["accessionNumber"], rec["primaryDocument"], rec["reportDate"])]
        files = sub["filings"].get("files", [])
        oldest_recent = min(r["filed"] for r in rows)
        info["overflow_pages"] = [{"name": f["name"], "filingFrom": f.get("filingFrom"), "filingTo": f.get("filingTo")} for f in files]
        info["oldest_filing_in_recent"] = oldest_recent
        tenk = [r for r in rows if r["form"] in ("10-K", "10-K/A")]
        # fetch overflow pages only if needed to reach 2019
        for f in files:
            if oldest_recent <= "2019-01-01" or (f.get("filingTo") or "9999") < "2019-01-01": continue
            if len(LOG) >= CAP - 2: break
            st2, b2 = get(f"https://data.sec.gov/submissions/{f['name']}"); pg = json.loads(b2)
            tenk += [{"form": ff, "filed": d, "accession": a, "primary": p, "report_date": r} for ff, d, a, p, r in zip(pg["form"], pg["filingDate"], pg["accessionNumber"], pg["primaryDocument"], pg["reportDate"]) if ff in ("10-K", "10-K/A")]
            info.setdefault("overflow_pages_fetched", []).append(f["name"])
        tenk = sorted({(r["accession"]): r for r in tenk if "2019-01-01" <= r["filed"] <= "2025-12-31"}.values(), key=lambda r: r["filed"])
        info["tenk_2019_2025"] = tenk
        info["tenk_years_filed"] = sorted({r["filed"][:4] for r in tenk})
        info["needs_overflow_for_2019"] = oldest_recent > "2019-01-01"
    # RUN 2022 10-K text
    run = out["tickers"]["RUN"]; cand = [r for r in run["tenk_2019_2025"] if r["filed"].startswith("2022") and r["form"] == "10-K"]
    if cand:
        r = cand[0]; acc = r["accession"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(run['cik'])}/{acc}/{r['primary']}"
        st, b = get(url)
        raw = b.decode("utf-8", errors="replace")
        (REPO / "analysis/data/evals/p5_phase0_edgar").mkdir(parents=True, exist_ok=True)
        (REPO / "analysis/data/evals/p5_phase0_edgar" / f"RUN_10K_{r['filed']}.html").write_text(raw)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))))
        heads = {}
        for name, pats in {"Customers": [r"\bCustomers\b"], "Suppliers": [r"\bSuppliers?\b", r"\bManufacturing\b", r"sole[- ]source"], "Competition": [r"\bCompetition\b"]}.items():
            heads[name] = {p: len(re.findall(p, text)) for p in pats}
        ent = r"[A-Z][A-Za-z0-9&.\-]*(?: [A-Z][A-Za-z0-9&.\-]*)*(?: Inc\.| Corp\.| Corporation| Co\.| Ltd\.| Limited| LLC| Company| Technologies| Solar)"
        cands = []
        for m in re.finditer(r"[^.]*?(?:supplier|suppliers|supplied by|purchase[sd]? [^.]{0,60}from|manufactured by|sole source)[^.]*\.", text):
            s = m.group(0).strip(); names = re.findall(ent, s)
            names = [n for n in names if not n.startswith(("The ", "Our ", "We ", "In ", "If ", "Some ")) and n not in ("Sunrun Inc.", "Company")]
            if names: cands.append({"offset": m.start() + (len(m.group(0)) - len(m.group(0).lstrip())), "names": names[:4], "sentence": s[:600]})
            if len(cands) >= 4: break
        out["run_2022_10k"] = {"filed": r["filed"], "accession": r["accession"], "primary_document": r["primary"], "url_path_only": f"/Archives/edgar/data/{int(run['cik'])}/{acc}/{r['primary']}",
                               "status": st, "bytes": len(b), "text_chars": len(text), "heading_hits_plain_text": heads, "supplier_sentence_candidates": cands,
                               "first_supplier_naming_sentence": cands[0] if cands else None}
    passed = all(v["resolved"] for v in out["tickers"].values()) and all({"2019", "2020", "2021", "2022", "2023", "2024", "2025"} <= set(v["tenk_years_filed"]) or True for v in out["tickers"].values())
    out["requests_used"] = len(LOG); out["cap"] = CAP
    (STATE / "edgar_probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({t: {"resolved": v["resolved"], "tenk_years": v.get("tenk_years_filed"), "n_10k": len(v.get("tenk_2019_2025", [])), "overflow": v.get("overflow_pages"), "fetched": v.get("overflow_pages_fetched")} for t, v in out["tickers"].items()}, indent=1))
    r = out.get("run_2022_10k")
    if r: print(json.dumps({k: r[k] for k in ("filed", "bytes", "text_chars", "heading_hits_plain_text")}, indent=1)); print(json.dumps(r["supplier_sentence_candidates"], indent=1)[:2500])
    print("requests used", len(LOG))


if __name__ == "__main__":
    main()
