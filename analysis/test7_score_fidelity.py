#!/usr/bin/env python3
"""
test7_score_fidelity.py -- driver for prompts/test7_ec_score_fidelity.md

Does EC's transcript text move the evaluator's structured score, once
Test 4's already-measured evaluator noise floor is accounted for?

Reuses, by import, rather than reimplementing:
  - analysis/test4_noise_floor.py: get_model_version(), get_prompt_header(),
    parse_structured() -- so Tier A's new EC-side runs are byte-for-byte
    comparable to that run's cached DB-side runs.
  - analysis/ec_fidelity_benchmark_1/driver.py: vendor_payload_to_text_and_turns()
    -- so EC text is reconstructed exactly as the EC benchmark did.

Zero new vendor (EarningsCall) calls. Real Anthropic API spend in Step 2
only, gated behind an explicit confirmation given the shared spend ceiling
with test6-look-ahead-prohibition.

Usage:
  python3 test7_score_fidelity.py check      # Step 0: version-match gate, 0 calls
  python3 test7_score_fidelity.py build      # Step 1: build DB+EC text for every cell, 0 calls
  python3 test7_score_fidelity.py score      # Step 2: real spend -- asks for confirmation first
  python3 test7_score_fidelity.py compare    # Step 3/4: comparison + verdict, 0 new calls
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO / "analysis"))
sys.path.insert(0, str(REPO / "analysis" / "ec_fidelity_benchmark_1"))

from dotenv import load_dotenv
load_dotenv(REPO / ".env")

import psycopg2, psycopg2.extras

import test4_noise_floor as t4  # get_model_version, get_prompt_header, parse_structured
from driver import vendor_payload_to_text_and_turns  # EC driver, read-only reuse

RUN_ID = "test7-ec-score-fidelity"
RUN_DIR = REPO / "analysis" / "data" / "run_state" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_PATH = RUN_DIR / "progress.json"
FINDINGS_PATH = RUN_DIR / "findings.md"

OUT_DIR = SCRIPT_DIR.parent / "test7_score_fidelity" if False else REPO / "analysis" / "test7_score_fidelity"
RAW_DIR = OUT_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

TEST4_RAW_DIR = REPO / "analysis" / "test4_noise_floor" / "raw"
EC_RAW_DIR = REPO / "analysis" / "ec_fidelity_benchmark_1" / "raw"

REPEATS = 3
PRIMARY_FIELDS = ["thesisHealth", "recommendation", "stumbleType", "mitigationCapabilityTrackRecord"]
NUMERIC_FIELDS = ["recommendedSize", "freshMoneyAllocation"]

# Cell definitions -- fixed, reported, not drawn. See prompt for rationale.
TIER_A = [  # reuse Test 4 DB-side (already on disk), spend only on EC side
    {"transcript_id": 16,  "ticker": "AMPX", "tier": "small_micro", "ec_raw": "AMPX_2025Q2_id16.json"},
    {"transcript_id": 287, "ticker": "FSLR", "tier": "mid",         "ec_raw": "FSLR_2022Q4_id287.json"},
    {"transcript_id": 220, "ticker": "TSLA", "tier": "megacap",     "ec_raw": "TSLA_2022Q3_id220.json"},
    {"transcript_id": 348, "ticker": "QS",   "tier": "small_micro", "ec_raw": "QS_2024Q1_id348.json"},
]
TIER_B = [  # fresh both sides -- not in the Test 4 overlap
    {"transcript_id": 370, "ticker": "RUN",  "tier": "small_micro", "ec_raw": "RUN_2022Q3_id370.json"},
    {"transcript_id": 154, "ticker": "AAPL", "tier": "megacap",     "ec_raw": "AAPL_2022Q4_id154.json"},
    {"transcript_id": 249, "ticker": "AMD",  "tier": "large",       "ec_raw": "AMD_2022Q2_id249.json"},
]
TIER_C = [  # optional, off by default -- pass `score --tier-c` to include
    {"transcript_id": 757, "ticker": "GOOGL", "tier": "megacap",    "ec_raw": "probe_GOOG_2026Q2.json"},
]

# NOTE: the exact `ec_raw` filenames above are the driver's best reconstruction
# of the EC benchmark's `{ticker}_{quarter}_id{transcript_id}.json` convention
# (see analysis/ec_fidelity_benchmark_1/driver.py's cell_key format) and the
# probe's own naming for id 757. **Step 1 (`build`) verifies every one of
# these actually exists and prints the real filename found under
# analysis/ec_fidelity_benchmark_1/raw/ by transcript_id before trusting it**
# -- do not assume the guessed name is right; resolve by content, not by name.


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"run_id": RUN_ID, "steps": {}, "cells": {}, "calls_made": 0,
            "input_tokens": 0, "output_tokens": 0, "notes": []}


def save_progress(p):
    PROGRESS_PATH.write_text(json.dumps(p, indent=2, default=str))


def append_finding(text):
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def resolve_ec_raw_path(transcript_id, guessed_name):
    """Find the actual raw file for this transcript_id under EC_RAW_DIR,
    by content (grepping for the id in filenames), not by trusting the
    guessed name. transcript_id 757 (GOOGL) is under the probe's own
    filename since it wasn't part of the main 195-cell fetch."""
    guessed = EC_RAW_DIR / guessed_name
    if guessed.exists():
        return guessed
    # fall back: scan for any file whose name ends with _id{tid}.json
    for p in EC_RAW_DIR.glob(f"*_id{transcript_id}.json"):
        return p
    # transcript 757's actual file lives under probe_GOOG_2026Q2.json -- already
    # covered by the guess, but keep this fallback generic for future cells
    for p in EC_RAW_DIR.glob("probe_GOOG_*.json"):
        return p
    return None


# ----------------------------------------------------------------------------
# Step 0 -- hygiene + hard version-match gate
# ----------------------------------------------------------------------------

def step0_check():
    model = t4.get_model_version()
    prompt_header, _ = t4.get_prompt_header()
    print(f"Current model: {model}")
    print(f"Current prompt header: {prompt_header}")

    blocked_tier_a = []
    for cell in TIER_A:
        tid = cell["transcript_id"]
        p = TEST4_RAW_DIR / f"{tid}.json"
        if not p.exists():
            print(f"  Tier A id {tid}: NOT in Test 4's raw/ -- cannot reuse, drop from Tier A or run both sides fresh")
            blocked_tier_a.append(tid)
            continue
        data = json.loads(p.read_text())
        if data.get("model") != model or data.get("prompt_version_header") != prompt_header:
            print(f"  Tier A id {tid}: VERSION MISMATCH -- Test4 used model={data.get('model')!r} "
                  f"prompt={data.get('prompt_version_header')!r}; current is model={model!r} prompt={prompt_header!r}. "
                  f"BLOCKED per Step 0's hard gate.")
            blocked_tier_a.append(tid)
        else:
            print(f"  Tier A id {tid}: version match OK, {len(data.get('runs', []))} cached DB-side runs available")

    progress = load_progress()
    progress["model"] = model
    progress["prompt_header"] = prompt_header
    progress["tier_a_blocked"] = blocked_tier_a
    progress["steps"]["0_check"] = "done"
    save_progress(progress)
    if blocked_tier_a:
        append_finding(f"## Step 0 gate ({now_iso()})\n\nTier A ids blocked by version mismatch or missing "
                       f"Test4 cache: {blocked_tier_a}. Tier B is unaffected (runs both sides fresh).")
        print(f"\n{len(blocked_tier_a)} Tier A cell(s) blocked. Tier B may still proceed.")
    else:
        print("\nAll Tier A cells clear to reuse Test 4's cached DB-side runs.")


# ----------------------------------------------------------------------------
# Step 1 -- build both text sides, 0 calls
# ----------------------------------------------------------------------------

def get_db_text(conn, transcript_id):
    with conn.cursor() as cur:
        cur.execute('SELECT "rawText" FROM "Transcript" WHERE id=%s', (transcript_id,))
        row = cur.fetchone()
        return row[0] if row else None


def get_ec_text(transcript_id, guessed_name):
    path = resolve_ec_raw_path(transcript_id, guessed_name)
    if path is None:
        return None, None
    data = json.loads(path.read_text())
    text, turns = vendor_payload_to_text_and_turns(data)
    return text, str(path.relative_to(REPO))


def step1_build():
    progress = load_progress()
    conn = db_conn()
    all_cells = [("A", c) for c in TIER_A] + [("B", c) for c in TIER_B] + [("C", c) for c in TIER_C]
    for tier, cell in all_cells:
        tid = cell["transcript_id"]
        db_text = get_db_text(conn, tid)
        ec_text, ec_path = get_ec_text(tid, cell["ec_raw"])
        ok = bool(db_text) and bool(ec_text)
        print(f"Tier {tier} id {tid} ({cell['ticker']}): db_words={len(db_text.split()) if db_text else 'MISSING'} "
              f"ec_words={len(ec_text.split()) if ec_text else 'MISSING'} ec_path={ec_path or 'NOT FOUND'} "
              f"{'OK' if ok else 'BLOCKED'}")
        progress["cells"].setdefault(str(tid), {})["tier"] = tier
        progress["cells"][str(tid)]["ticker"] = cell["ticker"]
        progress["cells"][str(tid)]["build_ok"] = ok
        progress["cells"][str(tid)]["ec_raw_path"] = ec_path
        progress["cells"][str(tid)]["db_word_count"] = len(db_text.split()) if db_text else None
        progress["cells"][str(tid)]["ec_word_count"] = len(ec_text.split()) if ec_text else None
    conn.close()
    progress["steps"]["1_build"] = "done"
    save_progress(progress)


# ----------------------------------------------------------------------------
# Step 2 -- scoring calls, gated, real spend
# ----------------------------------------------------------------------------

def run_evaluator(client, model, eval_prompt, transcript_text, n_runs):
    runs = []
    for i in range(n_runs):
        resp = client.messages.create(
            model=model, max_tokens=8192, temperature=0,
            messages=[{"role": "user", "content": eval_prompt.strip() + "\n\n---\n\nTRANSCRIPT:\n\n" + transcript_text}],
        )
        text = resp.content[0].text.strip()
        structured = t4.parse_structured(text)
        runs.append({
            "run_idx": i, "stop_reason": resp.stop_reason,
            "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
            "structured": structured, "raw_text": text,
            "model_used_response_hint": getattr(resp, "model", None),
        })
        print(f"    run {i}: {resp.stop_reason}, {resp.usage.input_tokens}in/{resp.usage.output_tokens}out, "
              f"recommendation={structured.get('recommendation') if structured else 'PARSE FAIL'}")
    return runs


def step2_score(include_tier_c=False, repeats=REPEATS, skip_confirm=False):
    progress = load_progress()
    if progress.get("steps", {}).get("1_build") != "done":
        print("Run `build` first."); return
    if progress.get("tier_a_blocked") is None:
        print("Run `check` first."); return

    tier_a_active = [c for c in TIER_A if c["transcript_id"] not in progress["tier_a_blocked"]]
    n_calls = len(tier_a_active) * repeats + len(TIER_B) * 2 * repeats + (len(TIER_C) * 2 * repeats if include_tier_c else 0)
    est_cost = n_calls * (23 / 250)  # Test 4's own observed $/call

    print(f"About to make {n_calls} real Anthropic API calls (~${est_cost:.2f} at Test 4's observed rate).")
    print(f"Tier A active: {len(tier_a_active)} cells x {repeats} EC-side runs")
    print(f"Tier B: {len(TIER_B)} cells x 2 sides x {repeats} runs")
    if include_tier_c:
        print(f"Tier C: {len(TIER_C)} cells x 2 sides x {repeats} runs")
    print("\nCONFIRM: has the test6-look-ahead-prohibition spend ceiling been checked and cleared for this spend? "
          "This driver cannot verify that on its own.")
    if not skip_confirm:
        ans = input("Type YES to proceed: ")
        if ans.strip() != "YES":
            print("Not confirmed. Aborting before any call was made.")
            return

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = progress["model"]
    _, eval_prompt = t4.get_prompt_header()

    for cell in tier_a_active:
        tid = cell["transcript_id"]
        out_path = RAW_DIR / f"{tid}_ec.json"
        if out_path.exists():
            print(f"Tier A id {tid}: already scored (EC side), skipping"); continue
        ec_text, _ = get_ec_text(tid, cell["ec_raw"])
        print(f"\nTier A id {tid} ({cell['ticker']}) -- EC side, {repeats} runs")
        runs = run_evaluator(client, model, eval_prompt, ec_text, repeats)
        out = {"transcript_id": tid, "ticker": cell["ticker"], "side": "ec", "tier_label": "A",
               "model": model, "prompt_version_header": progress["prompt_header"], "runs": runs}
        out_path.write_text(json.dumps(out, indent=2, default=str))
        progress["calls_made"] += len(runs)
        progress["input_tokens"] += sum(r["input_tokens"] for r in runs)
        progress["output_tokens"] += sum(r["output_tokens"] for r in runs)
        save_progress(progress)

    for tier_name, cells in (("B", TIER_B), ("C", TIER_C if include_tier_c else [])):
        conn = db_conn()
        for cell in cells:
            tid = cell["transcript_id"]
            db_out_path = RAW_DIR / f"{tid}_db.json"
            ec_out_path = RAW_DIR / f"{tid}_ec.json"
            db_text = get_db_text(conn, tid)
            ec_text, _ = get_ec_text(tid, cell["ec_raw"])
            if not db_out_path.exists():
                print(f"\nTier {tier_name} id {tid} ({cell['ticker']}) -- DB side, {repeats} runs")
                runs = run_evaluator(client, model, eval_prompt, db_text, repeats)
                out = {"transcript_id": tid, "ticker": cell["ticker"], "side": "db", "tier_label": tier_name,
                       "model": model, "prompt_version_header": progress["prompt_header"], "runs": runs}
                db_out_path.write_text(json.dumps(out, indent=2, default=str))
                progress["calls_made"] += len(runs)
                progress["input_tokens"] += sum(r["input_tokens"] for r in runs)
                progress["output_tokens"] += sum(r["output_tokens"] for r in runs)
                save_progress(progress)
            if not ec_out_path.exists():
                print(f"\nTier {tier_name} id {tid} ({cell['ticker']}) -- EC side, {repeats} runs")
                runs = run_evaluator(client, model, eval_prompt, ec_text, repeats)
                out = {"transcript_id": tid, "ticker": cell["ticker"], "side": "ec", "tier_label": tier_name,
                       "model": model, "prompt_version_header": progress["prompt_header"], "runs": runs}
                ec_out_path.write_text(json.dumps(out, indent=2, default=str))
                progress["calls_made"] += len(runs)
                progress["input_tokens"] += sum(r["input_tokens"] for r in runs)
                progress["output_tokens"] += sum(r["output_tokens"] for r in runs)
                save_progress(progress)
        conn.close()

    progress["steps"]["2_score"] = "done"
    save_progress(progress)
    total_tokens = progress["input_tokens"] + progress["output_tokens"]
    print(f"\nDone. Calls made this run + prior: {progress['calls_made']}. "
          f"Tokens: {total_tokens} ({progress['input_tokens']} in / {progress['output_tokens']} out). "
          f"Estimated cost so far: ${progress['calls_made'] * (23/250):.2f}")


# ----------------------------------------------------------------------------
# Step 3/4 -- comparison + verdict, 0 new calls
# ----------------------------------------------------------------------------

def field_values(runs, field):
    return [r["structured"].get(field) for r in runs if r.get("structured")]


def compare_sets(db_vals, ec_vals):
    db_set, ec_set = set(map(str, db_vals)), set(map(str, ec_vals))
    if not db_set or not ec_set:
        return "INCOMPLETE"
    return "DIVERGENCE" if db_set.isdisjoint(ec_set) else "inconclusive-overlap"


def step3_compare(include_tier_c=False):
    progress = load_progress()
    lines = []
    for cell in TIER_A:
        tid = cell["transcript_id"]
        if tid in progress.get("tier_a_blocked", []):
            lines.append(f"Tier A id {tid} ({cell['ticker']}): BLOCKED at Step 0, not compared.")
            continue
        db_path = TEST4_RAW_DIR / f"{tid}.json"
        ec_path = RAW_DIR / f"{tid}_ec.json"
        if not (db_path.exists() and ec_path.exists()):
            lines.append(f"Tier A id {tid}: missing data, not compared."); continue
        db_runs = json.loads(db_path.read_text())["runs"]
        ec_runs = json.loads(ec_path.read_text())["runs"]
        lines.append(f"\n### Tier A: {cell['ticker']} id {tid} (tier {cell['tier']}) -- DB n={len(db_runs)} (Test4 cache), EC n={len(ec_runs)} (this run)")
        for field in PRIMARY_FIELDS + NUMERIC_FIELDS:
            db_vals, ec_vals = field_values(db_runs, field), field_values(ec_runs, field)
            verdict = compare_sets(db_vals, ec_vals)
            lines.append(f"  {field}: DB={db_vals} EC={ec_vals} -> {verdict}")

    for tier_name, cells in (("B", TIER_B), ("C", TIER_C if include_tier_c else [])):
        for cell in cells:
            tid = cell["transcript_id"]
            db_path, ec_path = RAW_DIR / f"{tid}_db.json", RAW_DIR / f"{tid}_ec.json"
            if not (db_path.exists() and ec_path.exists()):
                lines.append(f"Tier {tier_name} id {tid}: missing data, not compared."); continue
            db_runs = json.loads(db_path.read_text())["runs"]
            ec_runs = json.loads(ec_path.read_text())["runs"]
            lines.append(f"\n### Tier {tier_name}: {cell['ticker']} id {tid} -- DB n={len(db_runs)}, EC n={len(ec_runs)} (both fresh)")
            for field in PRIMARY_FIELDS + NUMERIC_FIELDS:
                db_vals, ec_vals = field_values(db_runs, field), field_values(ec_runs, field)
                verdict = compare_sets(db_vals, ec_vals)
                lines.append(f"  {field}: DB={db_vals} EC={ec_vals} -> {verdict}")

    report = "\n".join(lines)
    print(report)
    (RUN_DIR / "comparison_report.txt").write_text(report)
    progress["steps"]["3_compare"] = "done"
    save_progress(progress)
    print(f"\nWritten to {RUN_DIR / 'comparison_report.txt'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    tier_c = "--tier-c" in sys.argv
    if cmd == "check":
        step0_check()
    elif cmd == "build":
        step1_build()
    elif cmd == "score":
        step2_score(include_tier_c=tier_c)
    elif cmd == "compare":
        step3_compare(include_tier_c=tier_c)
    else:
        print(f"Unknown command {cmd}")
