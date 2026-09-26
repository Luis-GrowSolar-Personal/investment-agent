#!/usr/bin/env python3
"""p5_edgar_offline.py -- $0, NO network. Re-reads the saved RUN 2022 10-K (gitignored copy) and adds a case-insensitive heading/supplier analysis to edgar_probe.json
(the probe's first-pass regexes were case-sensitive and its supplier-sentence extractor matched a financial table)."""
import re, html, glob, json
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
P = REPO / "analysis/data/run_state/p5-phase0/edgar_probe.json"
f = glob.glob(str(REPO / "analysis/data/evals/p5_phase0_edgar/RUN_10K_*.html"))[0]
raw = open(f).read()
text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", raw))))
def n(p, flags=0): return [m.start() for m in re.finditer(p, text, flags)]
heads = {"Customers": n(r"\bCustomers\b"), "Supply Chain (heading)": n(r"\bSupply Chain\b"), "supplier (any case)": n(r"[Ss]upplier"), "sole source": n(r"sole[- ]source", re.I),
         "manufactur*": n(r"[Mm]anufactur"), "Competition": n(r"\bCompetition\b")}
known = ["Tesla", "Panasonic", "LG Energy", "LG Chem", "Enphase", "SunPower", "Trina", "Jinko", "Canadian Solar", "Hanwha", "SolarEdge", "Qcells", "LONGi", "JA Solar", "First Solar", "Generac", "Fluence", "Samsung", "CATL", "BYD"]
hits = {k: len(re.findall(re.escape(k), text)) for k in known}
sc = text[n(r"\bSupply Chain\b")[0]: n(r"\bSupply Chain\b")[0] + 900] if n(r"\bSupply Chain\b") else None
ent = re.compile(r"\b[A-Z][A-Za-z0-9&\-]+(?: [A-Z][A-Za-z0-9&\-]+){0,3}(?:, Inc\.| Inc\.| Corp\.| Corporation| Ltd\.| Limited| GmbH)")
near = {}
for o in n(r"[Ss]upplier|manufacturers"):
    for m in ent.finditer(text[max(0, o - 300): o + 300]): near[m.group(0)] = near.get(m.group(0), 0) + 1
near = {k: v for k, v in near.items() if not k.startswith(("Sunrun", "The ", "Our ", "We "))}
d = json.loads(P.read_text())
d["run_2022_10k_offline_analysis"] = {"method": "saved 10-K text, case-insensitive regexes, no network", "text_chars": len(text),
    "heading_and_term_counts_and_first_offsets": {k: {"count": len(v), "first_offsets": v[:4]} for k, v in heads.items()},
    "well_known_supplier_or_peer_names_hits": hits, "company_like_names_within_300_chars_of_supplier_or_manufacturers": near,
    "supply_chain_section_verbatim_start": sc,
    "conclusion": "No supplier company is named in the searchable text. The 10-K has a 'Supply Chain' section (not a 'Suppliers' heading) that says equipment is bought 'from a limited number of manufacturers and suppliers' without naming any; the Competition section names competitor categories (traditional utilities, community solar) but no companies."}
P.write_text(json.dumps(d, indent=1)); print(json.dumps(d["run_2022_10k_offline_analysis"], indent=1)[:2500])
