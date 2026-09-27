#!/usr/bin/env python3
"""
p5p1_prefilter_calls.py -- Step 3b ($0). Every transcript on disk (train + tune): name-list matches after exclusions, kept with the sentence plus two either side, tagged prepared remarks / Q&A.
Exclusions: matches inside Operator turns; speaker headers are never searched (analyst self-introductions live there); analyst firms (docs/peers/ANALYST_FIRMS.csv) unless the passage has an
explicit business-relation word; stop-list word collisions; the calling company's own names. Output (gitignored): analysis/data/evals/p5_filings/call_passages.jsonl ; counts -> prefilter_calls.json
"""
import sys, re, json, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p5p1_common as C
import p5p1_prefilter as P
TD = C.C2 / "transcripts"
QA = re.compile(r"question-and-answer|question and answer|first question|open (?:it|the line|up the line|the call) (?:up )?(?:for|to) questions|take (?:your |some )?questions|Q&A|open (?:it )?up for questions", re.I)
SENT = re.compile(r"(?<=[.?!])\s+")


def main():
    names, matcher = P.build(); F = P.firms()
    uniq = {}; n_calls = 0; per_call = {}
    for d in sorted(TD.iterdir()):
        if not d.is_dir(): continue
        own = P.own_tickers(d.name)
        for f in sorted(d.glob("*.json")):
            text = json.loads(f.read_text())["text"]; n_calls += 1
            turns = text.split("\n\n"); qa_idx = next((i for i, t in enumerate(turns) if i >= 2 and QA.search(t)), None); cnt = 0
            for i, tn in enumerate(turns):
                h = re.match(r"([^:\n]{1,160}?\)):\s", tn); body = tn[h.end():] if h else tn
                if h and "operator" in h.group(1).lower(): continue
                ss = SENT.split(body)
                for si, s in enumerate(ss):
                    for m in matcher.finditer(s):
                        nm = m.group(1)
                        if names[nm][0] in own: continue
                        ctx = " ".join(ss[max(0, si - 2): si + 3])
                        if nm in F and not P.REL_STRICT.search(ctx): continue
                        key = hashlib.sha1(f"{d.name}|{f.stem}|{nm}|{ctx[:120]}".encode()).hexdigest()[:16]
                        if key in uniq: continue
                        uniq[key] = {"passage_id": key, "call": d.name, "date": f.stem, "name": nm, "in": "Q&A" if qa_idx is not None and i >= qa_idx else "prepared", "text": ctx[:1600]}
                        cnt += 1
            per_call[f"{d.name}_{f.stem}"] = cnt
    with open(C.EV / "call_passages.jsonl", "w") as o:
        for e in uniq.values(): o.write(json.dumps(e) + "\n")
    from collections import Counter
    c = Counter(e["name"] for e in uniq.values())
    out = {"calls_read": n_calls, "passages": len(uniq), "calls_with_>=1": sum(1 for v in per_call.values() if v), "median_chars": sorted(len(e["text"]) for e in uniq.values())[len(uniq) // 2], "top_names": c.most_common(50)}
    (C.STATE / "prefilter_calls.json").write_text(json.dumps(out, indent=1)); print(json.dumps({k: out[k] for k in out if k != "top_names"}), c.most_common(40))


if __name__ == "__main__":
    main()
