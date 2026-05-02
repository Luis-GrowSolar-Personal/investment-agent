#!/usr/bin/env python3
"""Pull daily closes for an arbitrary list of tickers from yfinance and
merge into data/price_cache.json. Run on your laptop where yfinance isn't
proxied.

Replaces the per-batch fetch_prices_*.py scripts (which only handled
specific ticker pairs) with a parameterized version. Fetches a generous
2020-01-01 → today window so trailing-σ classification has full coverage.

Usage:
    cd analysis && python3 fetch_prices_for_tickers.py AMD AVGO GOOGL ORCL
    cd analysis && python3 fetch_prices_for_tickers.py --start 2020-01-01 AMD
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance pandas")

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"


def fetch(sym: str, start: str, end: str | None) -> dict[str, float]:
    df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        print(f"  WARN: no rows returned for {sym}")
        return {}
    if hasattr(df.columns, "levels"):
        close = df[("Close", sym)] if ("Close", sym) in df.columns else df["Close"]
    else:
        close = df["Close"]
    out = {str(idx.date()): float(v) for idx, v in close.items() if v == v}
    print(f"  {sym}: {len(out)} daily closes, {min(out)} → {max(out)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="+", help="Ticker symbols to fetch.")
    ap.add_argument("--start", default="2020-01-01",
                    help="Start date (default 2020-01-01).")
    ap.add_argument("--end", default=None,
                    help="End date (default: today).")
    args = ap.parse_args()

    if not CACHE_PATH.exists():
        sys.exit(f"ERROR: {CACHE_PATH} missing.")
    cache = json.loads(CACHE_PATH.read_text())
    print(f"Fetching prices for {len(args.tickers)} ticker(s) from {args.start}:")
    for sym in args.tickers:
        cache[sym.upper()] = fetch(sym.upper(), args.start, args.end)
    CACHE_PATH.write_text(json.dumps(cache))
    print(f"\nWrote {CACHE_PATH}")
    print(f"Total tickers in cache: {len(cache)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
