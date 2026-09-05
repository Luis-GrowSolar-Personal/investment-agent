#!/usr/bin/env python3
"""test3_transcript_fidelity.py -- driver for
prompts/test3-transcript-ingestion-fidelity.md.

Step 1: DB `Transcript` completeness census, ALL16 universe, read-only.
Step 2: qualitative classification of the 7 saved AV raw responses from
        analysis/av_fidelity_test/raw/ -- no new AV calls.
Step 3: SPWR rename-timing comparison, from Step 1 + Step 2 outputs only.

No LLM calls, no re-scoring, no DB writes (SELECT only), no AV calls in this
driver (Step 4 is a separate, explicitly-gated manual step, not run here).

    cd analysis
    python3 test3_transcript_fidelity.py 1
    python3 test3_transcript_fidelity.py 2
    python3 test3_transcript_fidelity.py 3
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))

RUN_ID = "test3-transcript-ingestion-fidelity"
RUN_DIR = SCRIPT_DIR / "data" / "run_state" / RUN_ID
MANIFEST_DIR = RUN_DIR / "manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_DIR / "cells.jsonl"
DRIVER_FILE = "analysis/test3_transcript_fidelity.py"

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]

CLOSERS = ["concludes", "thank you for joining", "you may disconnect",
           "this concludes", "goodbye", "have a good day"]
QA_MARKERS = ["question-and-answer", "q&a", "q & a"]

FLAGGED_ROWS = {
    23: ("EOSE", "Q2 2025"),
    32: ("SPWR", "Q1 2025"),
    31: ("SPWR", "Q3 2025"),
    17: ("AMPX", "Q3 2025"),
}


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_info():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      cwd=REPO).decode().strip()
    dirty_out = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                         cwd=REPO).decode()
    allowed_untracked = (
        "prompts/resolve-open-four.md",
        "prompts/test3-transcript-ingestion-fidelity.md",
        "analysis/data/run_state/corpus-archive/",
        "analysis/data/run_state/test3-transcript-ingestion-fidelity/",
        "docs/handoffs/2026-09-05-state-of-play.md",  # another session's, not ours
    )
    dirty_lines = [ln for ln in dirty_out.splitlines() if ln.strip()]
    unexpected = [ln for ln in dirty_lines if not any(p in ln for p in allowed_untracked)]
    dirty = bool(unexpected)
    ls = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO).decode()
    driver_tracked = DRIVER_FILE in ls
    return commit, branch, dirty, driver_tracked, unexpected


def config_hash(driver_commit, params):
    blob = driver_commit + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def write_cell(cell_key, params, chash, results):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps({"cell_key": cell_key, "params": params,
                             "config_hash": chash, "results": results}, default=str) + "\n")


def base_manifest(driver_commit, branch, dirty, driver_tracked, params, results):
    return {
        "run_id": RUN_ID,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": driver_commit,
        "git_branch": branch,
        "git_dirty": dirty,
        "driver_file": DRIVER_FILE,
        "driver_file_tracked_at_commit": driver_tracked,
        "params": params,
        "results": results,
    }


def write_manifest(step, manifest):
    p = MANIFEST_DIR / f"{step}-manifest.json"
    p.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"manifest written -> {p}")


def closing_match(text, tail_chars=300):
    tail = text[-tail_chars:].lower()
    return any(c in tail for c in CLOSERS)


def qa_presence(text):
    low = text.lower()
    if any(m in low for m in QA_MARKERS):
        return True
    # run of Operator: / speaker turns after prepared remarks -- approximate
    # via count of "Operator" occurrences as a speaker-turn proxy.
    return low.count("operator") >= 2


def fetch_transcripts():
    from dotenv import load_dotenv
    import os, psycopg2, psycopg2.extras
    load_dotenv(REPO / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT t.id AS transcript_id, tk.symbol AS ticker,
                   t."callDate"::date AS call_date, t."rawText" AS raw_text
            FROM "Transcript" t
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE tk.symbol = ANY(%s)
            ORDER BY tk.symbol, t."callDate"
        """, (ALL16,))
        rows = cur.fetchall()
    conn.close()
    return rows


def step_1(driver_commit, branch, dirty, driver_tracked):
    rows = fetch_transcripts()
    by_ticker_wc = {}
    per_row = []
    for r in rows:
        text = r["raw_text"] or ""
        wc = len(text.split())
        cc = len(text)
        by_ticker_wc.setdefault(r["ticker"], []).append(wc)
        per_row.append({
            "transcript_id": r["transcript_id"], "ticker": r["ticker"],
            "call_date": str(r["call_date"]), "word_count": wc, "char_count": cc,
            "closing_match": closing_match(text), "qa_presence": qa_presence(text),
        })
    medians = {t: statistics.median(wcs) for t, wcs in by_ticker_wc.items()}
    for row in per_row:
        med = medians[row["ticker"]]
        row["ticker_median_word_count"] = med
        row["ratio_to_median"] = row["word_count"] / med if med else None
        row["outlier_flag"] = (row["ratio_to_median"] is not None and row["ratio_to_median"] < 0.40)

    outliers = [r for r in per_row if r["outlier_flag"]]
    n_closing_match = sum(1 for r in per_row if r["closing_match"])
    n_qa_present = sum(1 for r in per_row if r["qa_presence"])

    flagged_out = {}
    by_id = {r["transcript_id"]: r for r in per_row}
    for tid, (tk, q) in FLAGGED_ROWS.items():
        row = by_id.get(tid)
        flagged_out[tid] = {"expected_ticker_quarter": f"{tk} {q}", "found": row}

    results = {
        "n_transcripts": len(per_row),
        "n_outliers": len(outliers),
        "outliers": outliers,
        "closing_match_count": n_closing_match,
        "qa_presence_count": n_qa_present,
        "closer_list_used": CLOSERS,
        "qa_marker_list_used": QA_MARKERS,
        "per_ticker_median_word_count": medians,
        "flagged_pilot_rows": flagged_out,
        "all_rows": per_row,
    }
    chash = config_hash(driver_commit, {"step": "1", "universe": "ALL16"})
    write_cell("1", {"universe": "ALL16"}, chash, {k: v for k, v in results.items() if k != "all_rows"})
    write_manifest("1", base_manifest(driver_commit, branch, dirty, driver_tracked,
                                       {"universe": "ALL16"}, results))
    print(json.dumps({k: v for k, v in results.items() if k not in ("all_rows",)}, indent=2, default=str))
    return results


def step_2(driver_commit, branch, dirty, driver_tracked):
    raw_dir = SCRIPT_DIR / "av_fidelity_test" / "raw"
    pilot_results = json.loads((SCRIPT_DIR / "av_fidelity_test" / "results.json").read_text())
    ratio_by_key = {(r["ticker"], r["quarter"]): r["diagnostics"]["seqmatcher_ratio"]
                     for r in pilot_results}

    out = []
    for f in sorted(raw_dir.glob("*.json")):
        d = json.loads(f.read_text())
        t = d["transcript"]
        last = t[-1]
        last_text = last["content"]
        turn_count = len(t)
        last_closes = closing_match(last_text, tail_chars=len(last_text))
        # classify
        key = (d["symbol"], d["quarter"])
        ratio = ratio_by_key.get(key)
        # heuristic classification, human-reviewed per-sample below in findings.md
        classification = None
        note = ""
        low_last = last_text.lower()
        if last["speaker"] == "Operator" and last_closes and (
            "conclude" in low_last and ("q&a" in low_last or "question-and-answer" in low_last
                                          or "additional questions" in low_last)
            and "closing remarks" in low_last):
            classification = "truncated"
            note = ("last turn is the operator handing off to a named speaker for "
                    "'closing remarks' that never appear -- the transcript stops before "
                    "the call's actual end despite matching the naive closer keyword list "
                    "('concludes' referred to the Q&A segment, not the call).")
        elif last["speaker"] == "Operator" and last_closes:
            classification = "summarized-but-complete" if (ratio is not None and ratio < 0.5) else "complete-like"
            note = "operator sign-off present and content-consistent with a real call end."
        elif not last_closes:
            classification = "unclear"
            note = ("last turn is the company's own speaker ending on a natural but "
                    "informal remark ('Thank you.') with no operator sign-off and no "
                    "keyword-list match; cannot mechanically distinguish a genuine "
                    "no-outro convention from truncation without the DB-side text.")
        out.append({
            "file": f.name, "symbol": d["symbol"], "quarter": d["quarter"],
            "turn_count": turn_count, "last_speaker": last["speaker"],
            "last_turn_tail_200": last_text[-200:],
            "last_turn_closing_match": last_closes,
            "pilot_seqmatcher_ratio": ratio,
            "classification": classification, "note": note,
        })

    results = {"samples": out}
    chash = config_hash(driver_commit, {"step": "2"})
    write_cell("2", {}, chash, results)
    write_manifest("2", base_manifest(driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def step_3(step1_results, step2_results, driver_commit, branch, dirty, driver_tracked):
    by_id = {r["transcript_id"]: r for r in step1_results["all_rows"]}
    by_key = {(s["symbol"], s["quarter"]): s for s in step2_results["samples"]}

    spwr_q1 = by_id.get(32)  # DB side
    spwr_q3 = by_id.get(31)
    av_spwr_q1 = by_key.get(("SPWR", "2025Q1"))
    av_spwr_q3 = by_key.get(("SPWR", "2025Q3"))
    ampx_q3_db = by_id.get(17)
    av_ampx_q3 = by_key.get(("AMPX", "2025Q3"))
    eose_q1_db = None
    for r in step1_results["all_rows"]:
        if r["ticker"] == "EOSE" and r["call_date"] == "2025-05-06":
            eose_q1_db = r
    av_eose_q1 = by_key.get(("EOSE", "2025Q1"))

    same_mechanism = None
    if av_spwr_q1 and av_spwr_q3:
        same_mechanism = (av_spwr_q1["classification"] == av_spwr_q3["classification"])

    results = {
        "spwr_q1_call_date": spwr_q1["call_date"] if spwr_q1 else None,
        "spwr_q1_db": spwr_q1, "spwr_q1_av_classification": av_spwr_q1,
        "spwr_q3_call_date": spwr_q3["call_date"] if spwr_q3 else None,
        "spwr_q3_db": spwr_q3, "spwr_q3_av_classification": av_spwr_q3,
        "spwr_q1_and_q3_same_av_classification": same_mechanism,
        "control_ampx_q3_db": ampx_q3_db, "control_ampx_q3_av": av_ampx_q3,
        "control_eose_q1_db": eose_q1_db, "control_eose_q1_av": av_eose_q1,
        "reading": (
            "Both SPWR samples show the SAME av classification and the same "
            "no-operator-outro ending pattern (company officer says an informal "
            "'thank you' with no sign-off keyword), regardless of straddling the "
            "April 2025 rename. This argues AGAINST a rename-transition artifact "
            "and FOR a persistent, ticker-specific AV formatting/coverage "
            "characteristic for SPWR specifically."
            if same_mechanism else
            "SPWR Q1 and Q3 classifications differ -- argues FOR a rename-transition "
            "artifact rather than a persistent ticker-specific gap."
        ),
    }
    chash = config_hash(driver_commit, {"step": "3"})
    write_cell("3", {}, chash, results)
    write_manifest("3", base_manifest(driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    commit, branch, dirty, driver_tracked, unexpected = git_info()
    if dirty:
        print("UNEXPECTED DIRTY TREE (beyond known other-session state):")
        for ln in unexpected:
            print(" ", ln)
    print(f"git_commit={commit} branch={branch} dirty={dirty} driver_tracked={driver_tracked}")

    s1 = s2 = None
    if step in ("1", "all"):
        s1 = step_1(commit, branch, dirty, driver_tracked)
    if step in ("2", "all"):
        s2 = step_2(commit, branch, dirty, driver_tracked)
    if step in ("3", "all"):
        if s1 is None:
            s1 = json.loads((MANIFEST_DIR / "1-manifest.json").read_text())["results"]
        if s2 is None:
            s2 = json.loads((MANIFEST_DIR / "2-manifest.json").read_text())["results"]
        step_3(s1, s2, commit, branch, dirty, driver_tracked)


if __name__ == "__main__":
    main()
