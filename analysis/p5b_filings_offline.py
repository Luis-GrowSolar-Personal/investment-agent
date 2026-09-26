#!/usr/bin/env python3
"""p5b_filings_offline.py -- $0, NO network. Second pass on the saved 10-Ks: (1) INTC, whose Item 1 span was 159 characters (the 10-K is organised differently), is analysed over the
whole document; (2) the Customers passages of all four are printed for by-eye reading. Adds `offline_second_pass` to filings_probe.json."""
import sys, json, re, glob
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import p5b_names as N, p5b_filings as F
names = N.build(); matcher = N.matcher(names)
P = REPO / "analysis/data/run_state/p5-phase0b/filings_probe.json"
d = json.loads(P.read_text()); out = {}
for t in ("MU", "INTC", "ENPH", "NOW"):
    raw = open(glob.glob(str(REPO / f"analysis/data/evals/p5_phase0b/{t}_10K_*.html"))[0]).read(); text = F.plain(raw)
    r = {"whole_doc_chars": len(text)}
    r["customers_passages"] = []
    for m in list(re.finditer(r"\bCustomers\b", text))[:40]:
        w = text[m.start(): m.start() + 500]
        if re.search(r"accounted|largest|distribut|named|Customer [A-Z]|OEM|direct customers|sell (?:our|to)|top ", w): r["customers_passages"].append({"offset": m.start(), "text": w})
        if len(r["customers_passages"]) >= 4: break
    if t == "INTC":
        heads = {}
        for name, pat in F.HEADS.items(): heads[name] = [m.start() for m in re.finditer(pat, text)][:8]
        r["heading_offsets_whole_doc"] = heads
        found, seen = [], set()
        for name, occ in heads.items():
            for o in occ:
                zone = text[o:o + 3500]
                for m in matcher.finditer(zone):
                    nm = m.group(1); tkr = names[nm][0]
                    if tkr == "INTC": continue
                    k = (nm, F.sentence(zone, m.start())[:80])
                    if k in seen: continue
                    seen.add(k); found.append({"name": nm, "ticker": tkr, "heading": name, "sentence": F.sentence(zone, m.start())[:500]})
        r["matches_near_headings_whole_doc"] = found[:20]
    out[t] = r
d["offline_second_pass"] = out; P.write_text(json.dumps(d, indent=1))
for t, r in out.items():
    print("\n===", t, r["whole_doc_chars"])
    for p in r["customers_passages"][:3]: print("  cust@", p["offset"], "|", p["text"][:380])
    for h in r.get("matches_near_headings_whole_doc", [])[:12]: print("  *", h["heading"], h["name"], h["ticker"], "|", h["sentence"][:240])
    if t == "INTC": print("  heads", r["heading_offsets_whole_doc"])
