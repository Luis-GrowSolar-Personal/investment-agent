#!/usr/bin/env python3
"""
p5b_calls.py -- prompts/P5-phase0b-link-sources.md Step 2 ($0, no network, no model). 30 TRAIN transcripts from the corpus on disk (seed p5-0b-11):
the 2022 calls of RUN, MU, INTC, JKS, QCOM, NXPI (one 2022 call each, seeded) plus 24 more train companies, one call each, 2021-2023.
Counts other listed companies named (names from p5b_names: SEC company_tickers + hand aliases in docs/peers/NAME_ALIASES.csv), prepared remarks vs Q&A
(heuristic: first turn after the opening that announces questions), and the sentence around each mention. Output: p5-phase0b/calls_probe.json
"""
import sys, json, re, random, os
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis"))
import p5b_names as N, p3_guidance_ledger_driver as p3
STATE = REPO / "analysis/data/run_state/p5-phase0b"
TD = REPO / "analysis/data/corpus_v2/transcripts"
REQ = ["RUN", "MU", "INTC", "JKS", "QCOM", "NXPI"]
SEMIS, SOLAR = {"MU", "INTC", "QCOM", "NXPI", "SLAB", "DIOD"}, {"RUN", "JKS", "EOSE", "QS", "AMPX", "SUNW"}
QA = re.compile(r"question-and-answer|question and answer|first question|open (?:it|the line|up the line|the call) (?:up )?(?:for|to) questions|take (?:your |some )?questions|Q&A|open (?:it )?up for questions", re.I)
FIRM = re.compile(r"(?:question|line)s? (?:comes?|is) from|from the line of|next question|go ahead|line of ", re.I)
CORP = {"Samsung-none", "Panasonic-none", "BYD-none", "CATL-none", "LGES-none", "LONGi-none", "Hanwha-none", "Trina-none"}


def sector(t): return "semis" if t in SEMIS else "solar" if t in SOLAR else "other"


def sentence(text, pos):
    a = text.rfind(". ", 0, pos); s = a + 2 if a >= 0 else max(0, pos - 200)
    e = text.find(". ", pos); e = e + 1 if e >= 0 else pos + 300
    return text[max(s, pos - 350): min(e, pos + 400)].strip()


def main():
    tr = sorted(w for o, w in p3.resolved_train() if w not in {"WOLF", "SPWR", "PARA"} and (TD / w).is_dir())
    rng = random.Random("p5-0b-11")
    calls = {t: sorted(f[:-5] for f in os.listdir(TD / t)) for t in tr}
    sample = [(t, rng.choice([d for d in calls[t] if d.startswith("2022")])) for t in REQ]
    pool = [t for t in tr if t not in REQ and any(d[:4] in ("2021", "2022", "2023") for d in calls[t])]
    for t in sorted(rng.sample(pool, 24)): sample.append((t, rng.choice([d for d in calls[t] if d[:4] in ("2021", "2022", "2023")])))
    assert len(sample) == 30 and len(set(t for t, _ in sample)) == 30
    names = N.build(); matcher = N.matcher(names)
    res = []
    for t, d in sample:
        text = json.loads((TD / t / f"{d}.json").read_text())["text"]
        turns = text.split("\n\n"); qa_idx = next((i for i, tn in enumerate(turns) if i >= 2 and QA.search(tn)), None)
        qa_pos = sum(len(x) + 2 for x in turns[:qa_idx]) if qa_idx is not None else None
        ms, seen = [], set()
        for m in matcher.finditer(text):
            nm = m.group(1); tk = names[nm][0]
            if tk == t or tk in {t}: continue
            k = (nm, m.start() // 400)
            if k in seen: continue
            seen.add(k)
            sent = sentence(text, m.start())
            ms.append({"name": nm, "ticker": tk, "in": ("Q&A" if qa_pos is not None and m.start() >= qa_pos else "prepared"), "analyst_firm_like": bool(FIRM.search(text[max(0, m.start() - 160): m.start() + 60])), "sentence": sent[:420]})
        distinct = sorted({(x["ticker"] if x["ticker"] not in CORP else x["name"]) for x in ms})
        res.append({"ticker": t, "date": d, "sector": sector(t), "required": t in REQ, "chars": len(text), "qa_found": qa_idx is not None, "mentions": len(ms), "distinct_companies": distinct, "n_distinct": len(distinct), "matches": ms})
    def block(rs): return {"calls": len(rs), "name_at_least_one_pct": round(100 * sum(r["n_distinct"] > 0 for r in rs) / len(rs), 1) if rs else None, "mean_distinct_per_call": round(sum(r["n_distinct"] for r in rs) / len(rs), 2) if rs else None}
    # sensitivity: exclude mentions that look like an analyst's firm (operator introducing a question)
    for r in res:
        core = [x for x in r["matches"] if not x["analyst_firm_like"]]
        r["n_distinct_excluding_firm_like"] = len({(x["ticker"] if x["ticker"] not in CORP else x["name"]) for x in core})
    out = {"seed": "p5-0b-11", "n_calls": 30, "pooled": block(res), "by_sector": {s: block([r for r in res if r["sector"] == s]) for s in ("semis", "solar", "other")},
           "pooled_excluding_firm_like_mentions": {"name_at_least_one_pct": round(100 * sum(r["n_distinct_excluding_firm_like"] > 0 for r in res) / 30, 1), "mean_distinct_per_call": round(sum(r["n_distinct_excluding_firm_like"] for r in res) / 30, 2)},
           "sector_lists": {"semis": sorted(SEMIS), "solar": sorted(SOLAR)}, "name_list": {"total": len(names)}, "calls": res}
    # required-six: in corpus? fetchable?
    split = json.loads((REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text()); on_disk = {p.name for p in TD.iterdir() if p.is_dir()}
    fetched_ok = {"ENPH", "NVDA", "AMD", "KLAC", "ADI"}
    where = lambda tk: [s for s in ("train", "tune", "holdout") if tk in split[s]]
    rq = []
    for r in res:
        if not r["required"]: continue
        peers = {}
        for x in r["matches"]:
            tk = x["ticker"]
            if tk in CORP: peers[x["name"]] = {"ticker": tk, "in_corpus": False, "note": "not US-listed / no ticker", "fetchable_verified_phase0": False}; continue
            peers[tk] = {"in_corpus_on_disk": tk in on_disk, "splits": where(tk), "fetchable_verified_phase0": tk in fetched_ok}
        rq.append({"call": f"{r['ticker']} {r['date']}", "peers": peers})
    out["required_six_peer_usability"] = rq
    out["vendor_symbol_list_saved_in_phase0"] = False
    (STATE / "calls_probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("pooled", "by_sector", "pooled_excluding_firm_like_mentions")}, indent=1))
    for r in res: print(r["ticker"], r["date"], r["sector"], "distinct", r["n_distinct"], "excl_firm", r["n_distinct_excluding_firm_like"], r["distinct_companies"][:8])


if __name__ == "__main__":
    main()
