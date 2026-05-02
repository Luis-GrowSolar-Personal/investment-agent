#!/usr/bin/env python3
"""One-shot unblock: pulls transcripts (from Railway Postgres, if available)
and daily prices (from Yahoo Finance) for the tickers passed on the command
line, merging both into the local file cache. Run on your laptop where both
the DB and yfinance are reachable.

Usage:
    cd analysis && python3 unblock_AMPX_ENVX.py AMPX ENVX
    cd analysis && python3 unblock_AMPX_ENVX.py EOSE             # prices only
    cd analysis && python3 unblock_AMPX_ENVX.py --prices-only EOSE

Reads DATABASE_URL from ../.env; writes to:
    data/transcripts/<TICKER>_<DATE>.txt
    data/transcripts/_manifest.json  (merges, preserves existing entries)
    data/price_cache.json            (merges, preserves existing tickers)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"
PRICE_START = "2022-01-01"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("tickers", nargs="+", help="Ticker symbols to unblock.")
parser.add_argument("--prices-only", action="store_true",
                    help="Skip the DB transcript dump; only refresh prices.")
args = parser.parse_args()
TICKERS = [t.upper() for t in args.tickers]


def step_transcripts() -> None:
    print("=" * 60)
    print("Step 1/2: Pulling transcripts from Railway Postgres")
    print("=" * 60)
    cmd = [
        sys.executable, str(SCRIPT_DIR / "dump_transcripts.py"),
        "--merge",
    ]
    for t in TICKERS:
        cmd += ["--ticker", t]
    print("  ", " ".join(cmd))
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        sys.exit(f"dump_transcripts.py failed with exit {result.returncode}")


def step_prices() -> None:
    print()
    print("=" * 60)
    print("Step 2/2: Fetching prices via yfinance")
    print("=" * 60)
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("Missing yfinance. Run: pip install yfinance pandas")

    if not CACHE_PATH.exists():
        sys.exit(f"ERROR: {CACHE_PATH} missing.")

    cache = json.loads(CACHE_PATH.read_text())
    for sym in TICKERS:
        df = yf.download(sym, start=PRICE_START, progress=False, auto_adjust=False)
        if df.empty:
            print(f"  WARN: no rows for {sym}")
            continue
        if hasattr(df.columns, "levels"):
            close = df[("Close", sym)] if ("Close", sym) in df.columns else df["Close"]
        else:
            close = df["Close"]
        out = {str(idx.date()): float(v) for idx, v in close.items() if v == v}
        cache[sym] = out
        print(f"  {sym}: {len(out)} daily closes, {min(out)} -> {max(out)}")

    CACHE_PATH.write_text(json.dumps(cache))
    print(f"\nWrote {CACHE_PATH}")
    print(f"Tickers in cache now: {len(cache)}")


def main() -> int:
    if not args.prices_only:
        step_transcripts()
    else:
        print("Skipping transcript dump (--prices-only).")
    step_prices()
    print("\nDone. Claude can now re-cache v6 evals and run the trend layer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
