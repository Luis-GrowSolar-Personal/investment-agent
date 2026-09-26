#!/usr/bin/env python3
"""
p5_transcript_probe.py -- prompts/P5-phase0-probes.md Step 3 (<= 20 EarningsCall.biz vendor calls; no Claude calls).
3.1 on-disk coverage by split ($0). 3.2 vendor: ENPH, KLAC, ADI (not in corpus), NVDA, AMD (holdout): event list + one 2022 transcript each.
Pattern from baseline_v6_train_batch_driver.vendor_get_local (spacing, hard stop on 401/429, call counting in progress.json).
Transcripts go to analysis/data/run_state/p5-phase0/peer_probe/ (must be gitignored); metadata only to transcript_probe.json. Nothing is scored, digested or summarized.
"""
import sys, os, json, time, re, urllib.request, urllib.parse, urllib.error
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO / "analysis" / "ec_fidelity_benchmark_1"))
import driver as ecf  # noqa: E402  (EXCHANGES_IN_ORDER, MIN_SPACING_SECONDS, vendor_payload_to_text_and_turns)

STATE = REPO / "analysis/data/run_state/p5-phase0"
PROG = STATE / "progress.json"
CAP = 20
TDIR = REPO / "analysis/data/corpus_v2/transcripts"
SPLIT = json.loads((REPO / "analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json").read_text())
LOG = []


def vget(endpoint, params):
    p = json.loads(PROG.read_text())
    assert p.get("vendor_calls_used", 0) < CAP, "vendor cap reached"
    wait = ecf.MIN_SPACING_SECONDS - (time.time() - p.get("spacing_last_call_at", 0))
    if wait > 0: time.sleep(wait)
    t0 = time.time()
    url = f"https://v2.api.earningscall.biz/{endpoint}?" + urllib.parse.urlencode({**params, "apikey": os.environ["ECB_API_KEY"]})
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            status, body = r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", errors="replace")
    p = json.loads(PROG.read_text()); p["spacing_last_call_at"] = time.time(); p["vendor_calls_used"] = p.get("vendor_calls_used", 0) + 1; PROG.write_text(json.dumps(p, indent=2))
    LOG.append({"n": len(LOG) + 1, "endpoint": endpoint, "params": {k: v for k, v in params.items()}, "status": status, "bytes": len(body), "elapsed_s": round(time.time() - t0, 2)})
    if status in (401, 429): raise SystemExit(f"vendor HARD STOP status={status} endpoint={endpoint} body={body[:200]}")
    try: return status, json.loads(body)
    except json.JSONDecodeError: return status, body


def main():
    on_disk = {p.name for p in TDIR.iterdir() if p.is_dir()}
    out = {"on_disk": {"companies_with_transcripts": len(on_disk)}}
    for split in ("train", "tune", "holdout"):
        members = SPLIT[split]; out["on_disk"][split] = {"listed": len(members), "with_transcripts_on_disk": sorted(m for m in members if m in on_disk), "n_with": sum(m in on_disk for m in members)}
    out["on_disk"]["on_disk_not_in_any_split"] = sorted(on_disk - set(SPLIT["train"]) - set(SPLIT["tune"]) - set(SPLIT["holdout"]))
    st, sym = vget("symbols-v2.txt", {})
    symtab = {}
    for line in sym.splitlines() if isinstance(sym, str) else []:
        parts = line.split("\t")
        if len(parts) >= 2: symtab.setdefault(parts[1].upper(), []).append(parts[0])
    res = {}
    (STATE / "peer_probe").mkdir(exist_ok=True)
    for tk, why in (("ENPH", "not in corpus"), ("NVDA", "holdout"), ("AMD", "holdout"), ("KLAC", "not in corpus"), ("ADI", "not in corpus")):
        r = {"why": why, "on_disk": tk in on_disk, "in_split": [s for s in ("train", "tune", "holdout") if tk in SPLIT[s]]}
        idx = symtab.get(tk)
        if not idx: r["error"] = "not_in_symbol_list"; res[tk] = r; continue
        exch = ecf.EXCHANGES_IN_ORDER[int(idx[0])]; r["exchange"] = exch
        st, ev = vget("events", {"exchange": exch, "symbol": tk}); r["events_status"] = st
        evs = [{"year": e.get("year"), "quarter": e.get("quarter"), "conference_date": e.get("conference_date")} for e in (ev.get("events", []) if isinstance(ev, dict) else [])]
        e20 = sorted([e for e in evs if (e["year"] or 0) >= 2020], key=lambda e: (e["year"], e["quarter"]))
        r["events_total"] = len(evs); r["events_2020_on"] = len(e20); r["years_covered_2020_on"] = sorted({e["year"] for e in e20})
        r["quarters_2020_on"] = [f"{e['year']}Q{e['quarter']}" for e in e20]
        r["covers_2020_2025"] = {2020, 2021, 2022, 2023, 2024, 2025} <= set(r["years_covered_2020_on"])
        c22 = [e for e in e20 if e["year"] == 2022]
        if c22:
            e = c22[min(1, len(c22) - 1)]; r["transcript_call"] = f"{e['year']}Q{e['quarter']}"
            st, data = vget("transcript", {"exchange": exch, "symbol": tk, "year": e["year"], "quarter": e["quarter"], "level": 2})
            if st in (402, 403): r["level2_refused"] = st; st, data = vget("transcript", {"exchange": exch, "symbol": tk, "year": e["year"], "quarter": e["quarter"], "level": 1}); r["level_used"] = 1
            else: r["level_used"] = 2
            r["transcript_status"] = st
            if st == 200 and isinstance(data, dict):
                (STATE / "peer_probe" / f"{tk}_{e['year']}Q{e['quarter']}.json").write_text(json.dumps(data))
                text, turns = ecf.vendor_payload_to_text_and_turns(data)
                low = text.lower()
                ops = [i for i, t in enumerate(turns) if "operator" in (t["speaker"] or "").lower() or "operator" in (t["title"] or "").lower()]
                r["transcript"] = {"chars": len(text), "turns": len(turns), "distinct_speakers": len({t["speaker"] for t in turns}),
                                   "has_prepared_remarks_markers": bool(re.search(r"prepared remarks|turn (?:the call|it) over|thank you, operator", low)),
                                   "has_qa_markers": bool(re.search(r"question-and-answer|question and answer|first question|our next question|go ahead with your question", low)),
                                   "analyst_question_turns_after_first_qa_marker": None}
        res[tk] = r
    out["vendor"] = res
    ok = [t for t, r in res.items() if r.get("covers_2020_2025") and r.get("transcript", {}).get("chars", 0) > 20000]
    out["pass_at_least_4_of_5"] = len(ok) >= 4; out["passed"] = ok; out["vendor_calls"] = LOG; out["vendor_calls_used"] = len(LOG); out["cap"] = CAP
    (STATE / "transcript_probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"on_disk": {k: (v if not isinstance(v, dict) else {"listed": v["listed"], "n_with": v["n_with"]}) for k, v in out["on_disk"].items() if k != "on_disk_not_in_any_split"}, "not_in_split": out["on_disk"]["on_disk_not_in_any_split"][:10]}, indent=1))
    for t, r in res.items(): print(t, {k: v for k, v in r.items() if k not in ("quarters_2020_on",)})
    print("vendor calls", len(LOG), "pass", out["pass_at_least_4_of_5"], ok)


if __name__ == "__main__":
    main()
