#!/usr/bin/env python3
"""Cache-only eval runner.

Loops over the ENPH + TTD transcripts (or tickers passed via --ticker) and
populates data/evals/<prompt_version>/<TICKER>_<DATE>.txt for every transcript
that isn't already cached. Designed to run under the sandbox's 45s bash
timeout: each invocation makes progress on whatever is still missing, and
the cache survives across calls.

Usage:
    python3 eval_cache_warmer.py --ticker ENPH --ticker TTD --parallel 15
    # rerun until "all cached" message appears.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    sys.exit("ERROR: ANTHROPIC_API_KEY not found in env.")

MODEL = "claude-sonnet-4-20250514"
TRANSCRIPT_DIR = SCRIPT_DIR / "data" / "transcripts"
MANIFEST_PATH = TRANSCRIPT_DIR / "_manifest.json"
EVALS_DIR = SCRIPT_DIR / "data" / "evals"


def load_prompt() -> tuple[str, str]:
    path = SCRIPT_DIR.parent / "docs" / "EVALUATION_PROMPT.md"
    text = path.read_text()
    version = "unknown"
    for line in text.splitlines()[:20]:
        if line.startswith("# Version:"):
            # "# Version: v6 (stable best after v5→v8 iteration)" -> "v6"
            rest = line.split("Version:", 1)[1].strip()
            version = rest.split()[0]
            break
    return text, version


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", default=[], required=True)
    ap.add_argument("--parallel", type=int, default=10)
    ap.add_argument("--budget-seconds", type=int, default=38,
                    help="Stop dispatching new work after this many seconds.")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text())
    wanted = {t.upper() for t in args.ticker}
    manifest = [m for m in manifest if m["ticker"].upper() in wanted]
    manifest.sort(key=lambda m: (m["ticker"], m["call_date"]))
    if not manifest:
        sys.exit(f"ERROR: no manifest entries for {sorted(wanted)}")

    prompt_text, prompt_version = load_prompt()
    cache_dir = EVALS_DIR / prompt_version
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Figure out what's missing.
    missing = []
    for entry in manifest:
        cache_path = cache_dir / f"{entry['ticker']}_{entry['call_date']}.txt"
        if not cache_path.exists():
            missing.append(entry)

    print(f"Prompt version: {prompt_version}")
    print(f"Cache dir:      {cache_dir}")
    print(f"Manifest size:  {len(manifest)}")
    print(f"Already cached: {len(manifest) - len(missing)}")
    print(f"Missing:        {len(missing)}")
    if not missing:
        print("All cached.")
        return 0

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    start = time.time()

    def worker(entry: dict) -> tuple[str, bool, str]:
        sym = entry["ticker"]
        dt_str = entry["call_date"]
        tx_path = TRANSCRIPT_DIR / entry["filename"]
        transcript = tx_path.read_text()
        full_prompt = (
            prompt_text.strip()
            + "\n\n---\n\nTRANSCRIPT:\n\n"
            + transcript
        )
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": full_prompt}],
            )
            text = resp.content[0].text.strip()
            (cache_dir / f"{sym}_{dt_str}.txt").write_text(text)
            return (f"{sym}_{dt_str}", True, "")
        except Exception as e:
            return (f"{sym}_{dt_str}", False, str(e))

    done = 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(worker, e) for e in missing]
        for fut in as_completed(futures):
            tag, ok, err = fut.result()
            done += 1
            if ok:
                elapsed = time.time() - start
                print(f"  [{elapsed:5.1f}s] cached {tag}")
            else:
                failures.append((tag, err))
                print(f"  FAIL {tag}: {err[:120]}")
            if time.time() - start > args.budget_seconds:
                print(f"  Budget exhausted at {done}/{len(missing)}.")
                break

    print(f"\nDone: {done}/{len(missing)} processed in {time.time()-start:.1f}s")
    if failures:
        print(f"Failures: {len(failures)}")
        for tag, err in failures:
            print(f"  {tag}: {err[:80]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
