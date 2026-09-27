#!/usr/bin/env python3
"""
p5p1_prefilter.py -- Step 2b ($0). Mechanical pre-filter of the saved 10-K text: keep a paragraph only if it names a listed company (name list = SEC company_tickers names + hand aliases, minus a
stop-list of word collisions, minus the filer's own names) AND contains a relation keyword. Whole document searched (not just Item 1). Identical paragraphs repeated across a filer's
annual reports (and across filers) are deduplicated: one extraction per unique paragraph, applied to every filing that contains it, with the earliest filing date recorded.
Output (gitignored): analysis/data/evals/p5_filings/filing_paras.jsonl ; counts -> run_state/p5-phase1/prefilter_filings.json
"""
import sys, re, json, csv, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p5b_names as N
REPO = C.REPO
KW = re.compile(r"\b(?:customers?|clients?|competitors?|compete[sd]?|competing|competition|suppliers?|supply|supplied|vendors?|sole source|single source|single-source|sole-source|manufacturers?|foundry|foundries|distributors?|partner(?:s|ship)?|resellers?)\b|%\s+of\s+(?:our\s+|total\s+|net\s+)?(?:revenues?|sales)|of\s+(?:our\s+)?(?:net\s+|total\s+)?(?:revenues?|sales)", re.I)
REL_STRICT = re.compile(r"\b(?:customers?|clients?|competitors?|compete[sd]?|competing|suppliers?|vendors?|partner(?:s|ship)?|distributors?|manufacturers?)\b", re.I)
BLOCK = re.compile(r"(?i)</?(?:p|div|tr|li|br|h[1-6]|table|section)\b[^>]*>")


def firms():
    return {r["firm"] for r in csv.DictReader(open(REPO / "docs/peers/ANALYST_FIRMS.csv"))}


def stoplist():
    return {r["name"] for r in csv.DictReader(open(REPO / "docs/peers/NAME_STOPLIST.csv"))}


def build():
    names = N.build()
    for s in stoplist(): names.pop(s, None)
    return names, N.matcher(names)


def paragraphs(raw):
    t = BLOCK.sub("\n", re.sub(r"(?is)<(script|style|ix:header).*?</\1>", " ", raw))
    t = re.sub(r"<[^>]+>", " ", t)
    import html
    t = html.unescape(t)
    out = []
    for p in t.split("\n"):
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= 60 and "us-gaap:" not in p and "xbrli:" not in p: out.append(p)
    return out


def norm(p): return re.sub(r"[^a-z]+", " ", p.lower()).strip()


def window(p, pos, w=1500):
    if len(p) <= w: return p
    a = max(0, pos - w // 2); return p[a:a + w]


def own_tickers(w):
    am = C.alias_map(); return {w} | {o for o, ww in am.items() if ww == w} | {w}


def main():
    names, matcher = build(); F = firms()
    idx = json.loads((C.STATE / "filings_index.json").read_text())
    tk = C.tickers_json()
    uniq = {}; n_paras = n_docs = 0; per_form = {}
    for w, v in idx.items():
        own = own_tickers(w)
        for x in v["filings"]:
            fn = C.EV / "docs" / f"{w}_{x['form'].replace('/', '')}_{x['filed']}_{x['accession']}.htm"
            if not fn.exists(): continue
            n_docs += 1
            for p in paragraphs(fn.read_text(errors="replace")):
                if not KW.search(p): continue
                ms = [(m.group(1), m.start()) for m in matcher.finditer(p) if names[m.group(1)][0] not in own]
                if not ms: continue
                nm = {a for a, _ in ms}
                if nm <= F and not REL_STRICT.search(p): continue          # only sell-side/bank names and no explicit business-relation word
                key = hashlib.sha1(norm(window(p, ms[0][1])).encode()).hexdigest()[:16]
                e = uniq.setdefault(key, {"para_id": key, "text": window(p, ms[0][1]), "names": sorted(nm), "sources": []})
                e["sources"].append({"company": w, "filed": x["filed"], "accession": x["accession"], "form": x["form"]})
    with open(C.EV / "filing_paras.jsonl", "w") as f:
        for e in uniq.values(): f.write(json.dumps(e) + "\n")
    from collections import Counter
    c = Counter(nm for e in uniq.values() for nm in e["names"])
    tot_src = sum(len(e["sources"]) for e in uniq.values())
    out = {"docs_read": n_docs, "unique_paragraphs": len(uniq), "paragraph_occurrences": tot_src, "median_chars": sorted(len(e["text"]) for e in uniq.values())[len(uniq) // 2],
           "top_names": c.most_common(60), "name_list_size": len(names)}
    (C.STATE / "prefilter_filings.json").write_text(json.dumps(out, indent=1)); print(json.dumps({k: out[k] for k in ("docs_read", "unique_paragraphs", "paragraph_occurrences", "median_chars")}), c.most_common(45))


if __name__ == "__main__":
    main()
