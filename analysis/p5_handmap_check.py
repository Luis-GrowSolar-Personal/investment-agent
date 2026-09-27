#!/usr/bin/env python3
"""p5_handmap_check.py -- prompts/P5-phase1-peer-map.md Step 0 hand-map check ($0, no network). Reads only the first seven columns of docs/peers/HAND_MAP.csv,
keeps rows with linked_company filled, validates, splits multi-ticker cells into one link per ticker. Writes p5-phase1/hand_links.json. Never edits the CSV."""
import csv, json, re
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
rows = list(csv.reader(open(REPO / "docs/peers/HAND_MAP.csv", newline="")))
hdr = rows[0][:7]; assert hdr == ["company", "linked_company", "link_type", "valid_from_year", "valid_to_year", "confidence", "note"], hdr
kept, bad, links = [], [], []
for i, r in enumerate(rows[1:], start=2):
    r = (r + [""] * 7)[:7]
    if not r[1].strip(): continue
    co, lk, ty, vf, vt, cf, note = [x.strip() for x in r]
    kept.append(i); errs = []
    if ty not in ("CUSTOMER", "SUPPLIER", "COMPETITOR"): errs.append(f"link_type '{ty}'")
    if not re.fullmatch(r"\d{4}", vf) or not (1990 <= int(vf) <= 2026): errs.append(f"valid_from_year '{vf}'")
    if vt and (not re.fullmatch(r"\d{4}", vt) or (vf.isdigit() and int(vt) < int(vf))): errs.append(f"valid_to_year '{vt}'")
    if cf not in ("high", "medium", "low"): errs.append(f"confidence '{cf}'")
    tks = [t for t in re.split(r"[,;\s]+", lk) if t]
    if not tks: errs.append("no tickers")
    if co in tks: errs.append("links to itself")
    if not co: errs.append("company blank")
    if errs: bad.append({"csv_line": i, "company": co, "linked_company": lk, "errors": errs})
    else:
        for t in tks: links.append({"company": co, "linked": t, "link_type": ty, "valid_from_year": int(vf), "valid_to_year": int(vt) if vt else None, "confidence": cf, "note": note, "csv_line": i})
out = {"rows_total": len(rows) - 1, "rows_kept": len(kept), "invalid_rows": bad, "split_links": len(links), "links": links}
(REPO / "analysis/data/run_state/p5-phase1/hand_links.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("rows_total", "rows_kept", "split_links")}), "invalid", len(bad))
for b in bad: print(b)
