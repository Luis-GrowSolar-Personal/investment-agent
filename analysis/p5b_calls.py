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
# Second pass (added after reading the first-pass matches by eye, as the prompt asks): analyst firms named by the operator or in speaker headers, and
# words that collide with company names. Documented here so the reading is reproducible; the RAW counts (no exclusions) are reported beside the cleaned ones.
ANALYST_FIRMS = {"Morgan Stanley", "Evercore", "Credit Suisse", "Barclays", "Oppenheimer", "Citigroup", "Citi", "Goldman Sachs", "Bank of America", "Wells Fargo", "UBS", "Jefferies", "Northern Trust", "Samsara Capital", "BMO Capital", "Wolfe Research", "Bernstein", "Piper Sandler", "Raymond James", "Stifel", "KeyBanc", "RBC Capital", "Mizuho", "Cowen", "Truist", "Deutsche Bank", "Nomura", "Needham"}
WORD_COLLISIONS = {"Perfect", "Eastern", "Celsius", "Amplitude", "Verizon"}       # 'Perfect.' as an acknowledgement, 'Eastern Europe', battery 'Celsius', a product name, 'using Verizon Conferencing'
# Third layer, by-eye (read from calls_probe.json after the second pass): matches that are not a company reference at all. (call ticker, matched name)
BY_EYE_FALSE = {("ABBV", "AMD"), ("DD", "Dell"), ("PSX", "Northern"), ("QS", "Exponent"), ("QS", "Lithium")}    # wet AMD (an eye disease); Delrin/'Dell Rent'; Northern California; Exponent (a firm mentioned as a speaker's past employer); Lithium (the element)
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
        off = 0
        for tn in turns:
            hdr = re.match(r"([^:\n]{1,160}?\)):\s", tn)          # "Name (Title): content"
            head_len = hdr.end() if hdr else 0
            is_operator = bool(hdr and "operator" in hdr.group(1).lower())
            for m in matcher.finditer(tn[head_len:]):
                nm = m.group(1); tk = names[nm][0]
                if tk == t: continue
                pos = off + head_len + m.start()
                k = (nm, pos // 400)
                if k in seen: continue
                seen.add(k)
                cleaned_out = is_operator or nm in ANALYST_FIRMS or nm in WORD_COLLISIONS
                ms.append({"name": nm, "ticker": tk, "in": ("Q&A" if qa_pos is not None and pos >= qa_pos else "prepared"), "operator_turn": is_operator, "excluded_second_pass": cleaned_out,
                           "analyst_firm_like": is_operator or nm in ANALYST_FIRMS, "sentence": sentence(tn, head_len + m.start())[:420]})
            off += len(tn) + 2
        key = lambda x: x["ticker"] if x["ticker"] not in CORP else x["name"]
        for x in ms: x["by_eye_false_positive"] = (t, x["name"]) in BY_EYE_FALSE
        distinct_raw = sorted({key(x) for x in ms}); distinct = sorted({key(x) for x in ms if not x["excluded_second_pass"]})
        distinct_eye = sorted({key(x) for x in ms if not x["excluded_second_pass"] and not x["by_eye_false_positive"]})
        res.append({"ticker": t, "date": d, "sector": sector(t), "required": t in REQ, "chars": len(text), "qa_found": qa_idx is not None, "mentions_raw": len(ms), "distinct_raw": distinct_raw, "n_distinct_raw": len(distinct_raw),
                    "distinct_companies": distinct, "n_distinct": len(distinct), "distinct_by_eye": distinct_eye, "n_distinct_by_eye": len(distinct_eye), "n_prepared": sum(1 for x in ms if not x["excluded_second_pass"] and x["in"] == "prepared"), "n_qa": sum(1 for x in ms if not x["excluded_second_pass"] and x["in"] == "Q&A"), "matches": ms})
    def block(rs, f="n_distinct"): return {"calls": len(rs), "name_at_least_one": sum(r[f] > 0 for r in rs), "name_at_least_one_pct": round(100 * sum(r[f] > 0 for r in rs) / len(rs), 1) if rs else None, "mean_distinct_per_call": round(sum(r[f] for r in rs) / len(rs), 2) if rs else None}
    out = {"seed": "p5-0b-11", "n_calls": 30, "RAW_no_exclusions": {"pooled": block(res, "n_distinct_raw"), "note": "raw = every match, including analyst firms named by the operator (speaker headers are not searched); the first-pass version that also searched headers gave the same 100% and 4.37 per call"},
           "pooled": block(res), "by_sector": {s: block([r for r in res if r["sector"] == s]) for s in ("semis", "solar", "other")},
           "by_eye": {"pooled": block(res, "n_distinct_by_eye"), "by_sector": {s: block([r for r in res if r["sector"] == s], "n_distinct_by_eye") for s in ("semis", "solar", "other")}, "false_positives_removed": sorted(f"{a}:{b}" for a, b in BY_EYE_FALSE),
                      "mentions_prepared_vs_qa_second_pass": {"prepared": sum(r["n_prepared"] for r in res), "qa": sum(r["n_qa"] for r in res)}},
           "second_pass_exclusions": {"analyst_firms": sorted(ANALYST_FIRMS), "word_collisions": sorted(WORD_COLLISIONS), "operator_turns": "all matches inside Operator turns"},
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
            if x["excluded_second_pass"] or x["by_eye_false_positive"]: continue      # by-eye company mentions only
            tk = x["ticker"]
            if tk in CORP: peers[x["name"]] = {"ticker": tk, "in_corpus": False, "note": "not US-listed / no ticker", "fetchable_verified_phase0": False}; continue
            peers[tk] = {"in_corpus_on_disk": tk in on_disk, "splits": where(tk), "fetchable_verified_phase0": tk in fetched_ok}
        rq.append({"call": f"{r['ticker']} {r['date']}", "peers": peers})
    out["required_six_peer_usability"] = rq
    out["vendor_symbol_list_saved_in_phase0"] = False
    (STATE / "calls_probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("RAW_no_exclusions", "pooled", "by_sector", "by_eye")}, indent=1))
    for r in res: print(r["ticker"], r["date"], r["sector"], "raw", r["n_distinct_raw"], "clean", r["n_distinct"], "eye", r["n_distinct_by_eye"], "prep/qa", r["n_prepared"], r["n_qa"], r["distinct_companies"][:8])


if __name__ == "__main__":
    main()
