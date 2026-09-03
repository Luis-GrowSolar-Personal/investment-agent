#!/usr/bin/env python3
"""
driver.py -- AV transcript fidelity benchmark driver.
See prompts/av_transcript_fidelity_benchmark_1.md for the full spec.
No AV calls here -- raw AV JSON already fetched to raw/. This script only
makes Anthropic API calls (determinism control + DB/AV evaluation runs).
"""
import os, re, sys, json, time, difflib
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent.parent
load_dotenv(repo_root / ".env")

import anthropic
import psycopg2
import psycopg2.extras

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
MODEL = "claude-sonnet-4-6"  # matches server/lib/versions.js MODEL_VERSION (production, 2026-06-27+)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROMPT_PATH = repo_root / "docs" / "EVALUATION_PROMPT.md"
EVAL_PROMPT = PROMPT_PATH.read_text()

RAW_DIR = script_dir / "raw"
SCORED_DIR = script_dir / "scored"
SCORED_DIR.mkdir(exist_ok=True)

SAMPLES = [
    ("AMPX", "2025Q1", 15),
    ("AMPX", "2025Q2", 16),
    ("AMPX", "2025Q3", 17),
    ("EOSE", "2025Q1", 22),
    ("EOSE", "2025Q2", 23),
    ("SPWR", "2025Q1", 32),
    ("SPWR", "2025Q3", 31),
]

FIELDS = [
    "thesisHealth","thesisDelta","recommendation","recommendedSize",
    "freshMoneyAllocation","typeClassification","stumbleType",
    "threatMechanismImpaired","credibilityDelta","activeDriverCount",
    "ratchetTranche","blindSpotsTriggered","capPercent",
    "mitigationArgumentPresent","mitigationCapabilityTrackRecord",
]

def av_transcript_to_text(av_json):
    entries = av_json.get("transcript", [])
    lines = []
    for e in entries:
        speaker = e.get("speaker", "Unknown")
        title = e.get("title", "")
        content = e.get("content", "")
        lines.append(f"{speaker} ({title}): {content}")
    return "\n\n".join(lines)

def get_db_transcript(conn, transcript_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT "rawText" FROM "Transcript" WHERE id = %s', (transcript_id,))
        row = cur.fetchone()
        return row["rawText"] if row else None

def evaluate(transcript_text):
    full_prompt = EVAL_PROMPT.strip() + "\n\n---\n\nTRANSCRIPT:\n\n" + transcript_text
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=0,
        messages=[{"role": "user", "content": full_prompt}],
    )
    text = response.content[0].text.strip()
    return text, response.stop_reason, response.usage.output_tokens

def parse_structured(raw_output):
    match = re.search(r'---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---', raw_output, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

def diff_fields(a, b):
    diffs = {}
    for f in FIELDS:
        va = a.get(f) if a else None
        vb = b.get(f) if b else None
        diffs[f] = ("MATCH" if va == vb else "DIFFER", va, vb)
    return diffs

def similarity_ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def main():
    conn = psycopg2.connect(DATABASE_URL)
    results = []

    for ticker, quarter, tid in SAMPLES:
        print(f"\n=== {ticker} {quarter} (transcript id {tid}) ===")
        sample = {"ticker": ticker, "quarter": quarter, "transcript_id": tid}

        db_text = get_db_transcript(conn, tid)
        if not db_text:
            print("  DB transcript missing -- dropping sample")
            sample["status"] = "dropped_missing_db_text"
            results.append(sample)
            continue

        raw_path = RAW_DIR / f"{ticker}_{quarter}.json"
        av_json = json.loads(raw_path.read_text())
        av_text = av_transcript_to_text(av_json)

        # Step 3: diagnostics
        db_words = len(db_text.split())
        av_words = len(av_text.split())
        ratio = similarity_ratio(db_text, av_text)
        sample["diagnostics"] = {"db_word_count": db_words, "av_word_count": av_words, "seqmatcher_ratio": round(ratio, 4)}
        print(f"  words: DB={db_words} AV={av_words}  seqmatcher_ratio={ratio:.4f}")

        # Step 4: determinism control (DB transcript, twice)
        print("  Determinism run 1...", end=" ", flush=True)
        raw1, stop1, tok1 = evaluate(db_text)
        print(f"stop_reason={stop1}")
        struct1 = parse_structured(raw1)

        print("  Determinism run 2...", end=" ", flush=True)
        raw2, stop2, tok2 = evaluate(db_text)
        print(f"stop_reason={stop2}")
        struct2 = parse_structured(raw2)

        det_diffs = diff_fields(struct1, struct2)
        det_clean = all(v[0] == "MATCH" for v in det_diffs.values())
        sample["determinism"] = {
            "run1_stop_reason": stop1, "run1_output_tokens": tok1,
            "run2_stop_reason": stop2, "run2_output_tokens": tok2,
            "clean": det_clean,
            "field_diffs": {k: v for k, v in det_diffs.items()},
        }
        print(f"  Determinism check: {'CLEAN' if det_clean else 'FAILED -- fields differ'}")

        if not det_clean:
            sample["status"] = "determinism_failed_skipped_step5"
            (SCORED_DIR / f"{ticker}_{quarter}_det_run1.json").write_text(raw1)
            (SCORED_DIR / f"{ticker}_{quarter}_det_run2.json").write_text(raw2)
            results.append(sample)
            continue

        # Step 5: DB vs AV, same model, temp=0
        print("  Evaluating DB version (final)...", end=" ", flush=True)
        db_raw, db_stop, db_tok = evaluate(db_text)
        print(f"stop_reason={db_stop}")
        db_struct = parse_structured(db_raw)
        (SCORED_DIR / f"{ticker}_{quarter}_db.json").write_text(db_raw)

        print("  Evaluating AV version...", end=" ", flush=True)
        av_raw, av_stop, av_tok = evaluate(av_text)
        print(f"stop_reason={av_stop}")
        av_struct = parse_structured(av_raw)
        (SCORED_DIR / f"{ticker}_{quarter}_av.json").write_text(av_raw)

        sample["db_stop_reason"] = db_stop
        sample["av_stop_reason"] = av_stop

        # Step 6: field diff
        field_diffs = diff_fields(db_struct, av_struct)
        sample["field_diffs"] = field_diffs
        sample["status"] = "complete"
        results.append(sample)

        n_differ = sum(1 for v in field_diffs.values() if v[0] == "DIFFER")
        print(f"  Field diff: {n_differ}/{len(FIELDS)} fields differ")

    conn.close()
    (script_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print("\nDone. Results written to analysis/av_fidelity_test/results.json")

if __name__ == "__main__":
    main()
