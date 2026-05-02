#!/usr/bin/env python3
"""One-time: pull AMPX + ENVX daily closes from yfinance and merge into
data/price_cache.json. Run this on your laptop where yfinance isn't proxied.

Usage:
    cd analysis && python3 fetch_prices_AMPX_ENVX.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance pandas")

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"

TICKERS = ["AMPX", "ENVX"]
START = "2022-01-01"   # buffer before earliest transcript
END = None             # today


def fetch(sym: str) -> dict[str, float]:
    df = yf.download(sym, start=START, end=END, progress=False, auto_adjust=False)
    if df.empty:
        print(f"WARN: no rows returned for {sym}")
        return {}
    # Handle MultiIndex columns in newer yfinance versions.
    if hasattr(df.columns, "levels"):
        close = df[("Close", sym)] if ("Close", sym) in df.columns else df["Close"]
    else:
        close = df["Close"]
    out = {str(idx.date()): float(v) for idx, v in close.items() if v == v}  # filter NaN
    print(f"  {sym}: {len(out)} daily closes, {min(out)} -> {max(out)}")
    return out


def main() -> int:
    if not CACHE_PATH.exists():
        sys.exit(f"ERROR: {CACHE_PATH} missing.")
    cache = json.loads(CACHE_PATH.read_text())
    for sym in TICKERS:
        cache[sym] = fetch(sym)
    # Pretty print would bloat the file; keep compact like the original.
    CACHE_PATH.write_text(json.dumps(cache))
    print(f"\nWrote {CACHE_PATH}")
    print(f"Total tickers now in cache: {len(cache)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
