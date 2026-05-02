#!/usr/bin/env python3
"""
onboard_new_tickers.py — End-to-end runner for adding new tickers to the
analytical universe. Run on your laptop where DB and yfinance are reachable.

Chains 6 steps for the listed ticker symbols:
  1. dump_transcripts.py    — pull transcripts from Railway DB to local files
  2. fetch_prices_for_tickers.py — pull daily closes from yfinance
  3. fetch_fundamentals.py  — pull market cap + P/E for the union of symbols
  4. eval_cache_warmer.py   — run v6 evaluator on each transcript (Anthropic API)
  5. rebackfill_v6_analyses.py — write a v6 Analysis row per Transcript
  6. sync_trend_to_db.py    — compute trend verdicts on v6-consistent timeline

Each step is idempotent (skip-if-cached / skip-if-exists). Safe to re-run
if anything fails partway.

Usage:
    cd analysis && python3 onboard_new_tickers.py AMD AVGO GOOGL
    cd analysis && python3 onboard_new_tickers.py ORCL          # later, when ready

If a step fails, it prints the error and stops; subsequent steps don't run.
You can re-invoke after fixing the underlying issue (e.g. cache warming
budget exhausted → just re-run; it'll skip already-cached evals).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def run(label: str, cmd: list[str]) -> bool:
    """Run a subprocess command. Print a header, stream stdout/stderr, return True on success."""
    print(f"\n━━━ {label} ━━━")
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=SCRIPT_DIR, check=False)
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return False
    if result.returncode != 0:
        print(f"  ✗ Step failed (exit {result.returncode}). Stopping.")
        return False
    print(f"  ✓ {label} — done")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="+",
                    help="New ticker symbols to onboard (e.g. AMD AVGO GOOGL).")
    ap.add_argument("--cache-warm-passes", type=int, default=3,
                    help="How many times to invoke eval_cache_warmer.py "
                         "(each pass has a 38s budget; default 3 covers ~45 "
                         "evals at parallel=15).")
    ap.add_argument("--skip-prices", action="store_true",
                    help="Skip the price fetch step (use if already populated).")
    args = ap.parse_args()

    tickers = [t.upper() for t in args.tickers]
    ticker_args = sum([["--ticker", t] for t in tickers], [])
    py = sys.executable

    print(f"Onboarding {len(tickers)} ticker(s): {', '.join(tickers)}")

    # Step 1 — dump transcripts (merge to preserve existing manifest)
    if not run("Step 1/6: Pull transcripts from Railway",
                [py, "dump_transcripts.py", *ticker_args, "--merge"]):
        return 1

    # Step 2 — fetch prices
    if not args.skip_prices:
        if not run("Step 2/6: Fetch prices from yfinance",
                    [py, "fetch_prices_for_tickers.py", *tickers]):
            return 2
    else:
        print("\n━━━ Step 2/6: Fetch prices — SKIPPED (--skip-prices) ━━━")

    # Step 3 — fetch fundamentals (does all tickers in cache; new ones get added)
    if not run("Step 3/6: Fetch fundamentals (market cap + P/E)",
                [py, "fetch_fundamentals.py", *ticker_args]):
        return 3

    # Step 4 — warm v6 eval cache (may need multiple passes under the budget)
    for i in range(args.cache_warm_passes):
        print(f"\n━━━ Step 4/6: Warm v6 eval cache (pass {i+1}/{args.cache_warm_passes}) ━━━")
        result = subprocess.run(
            [py, "eval_cache_warmer.py", *ticker_args, "--parallel", "15"],
            cwd=SCRIPT_DIR, check=False
        )
        if result.returncode == 0:
            # Successful pass with all cached — done
            print(f"  ✓ pass {i+1} — all cached")
            break
        if i == args.cache_warm_passes - 1:
            print(f"  ✗ pass {i+1} — still incomplete after "
                  f"{args.cache_warm_passes} passes. Re-run this script "
                  f"with --skip-prices to continue from cache warming.")
            return 4

    # Step 5 — append v6 Analysis rows for the new tickers
    if not run("Step 5/6: Rebackfill v6 analyses",
                [py, "rebackfill_v6_analyses.py", *ticker_args]):
        return 5

    # Step 6 — recompute trend verdicts on v6-consistent timeline (whole DB)
    if not run("Step 6/6: Sync trend verdicts to DB", [py, "sync_trend_to_db.py"]):
        return 6

    # Verification
    print("\n━━━ Verification ━━━")
    subprocess.run(
        [py, "inspect_trend_db.py", *ticker_args],
        cwd=SCRIPT_DIR, check=False,
    )

    print(f"\n✓ All steps complete for {', '.join(tickers)}.")
    print("  Refresh the RADAR page in the browser to see the new tickers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
