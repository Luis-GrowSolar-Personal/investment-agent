#!/usr/bin/env python3
"""Fetch market cap + P/E snapshots from yfinance and merge into
data/fundamentals_cache.json. Run on your laptop where yfinance isn't proxied.

This is a *snapshot* — current values, not a time series. The classifier
treats classification as stable across the backtest window (companies rarely
flip between earnings/no-earnings mid-stream).

Usage:
    cd analysis && python3 fetch_fundamentals.py
    cd analysis && python3 fetch_fundamentals.py --ticker AMPX --ticker FSLR
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance")

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "data" / "fundamentals_cache.json"
MANIFEST_PATH = SCRIPT_DIR / "data" / "transcripts" / "_manifest.json"
PRICE_CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"


def default_tickers() -> list[str]:
    """All tickers that have either transcripts or prices."""
    syms: set[str] = set()
    if MANIFEST_PATH.exists():
        for m in json.loads(MANIFEST_PATH.read_text()):
            syms.add(m["ticker"])
    if PRICE_CACHE_PATH.exists():
        # Skip SPY (benchmark, not a holding)
        for s in json.loads(PRICE_CACHE_PATH.read_text()).keys():
            if s != "SPY":
                syms.add(s)
    return sorted(syms)


def fetch_one(sym: str) -> dict:
    t = yf.Ticker(sym)
    info = t.info or {}
    return {
        "marketCap": info.get("marketCap"),
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "trailingEps": info.get("trailingEps"),
        "shortName": info.get("shortName") or info.get("longName"),
        "fetchedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", default=[],
                    help="Restrict to these symbols (repeatable). Default: all "
                         "tickers in transcripts manifest + price cache.")
    args = ap.parse_args()

    tickers = [t.upper() for t in args.ticker] if args.ticker else default_tickers()

    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())

    print(f"Fetching fundamentals for {len(tickers)} ticker(s):")
    for sym in tickers:
        try:
            d = fetch_one(sym)
        except Exception as e:
            print(f"  {sym}: ERROR {e}")
            continue
        mc = d["marketCap"]
        pe = d["trailingPE"]
        fp = d["forwardPE"]
        mc_str = f"${mc/1e9:.1f}B" if mc else "n/a"
        pe_str = f"{pe:.1f}" if pe else "n/a"
        fp_str = f"{fp:.1f}" if fp else "n/a"
        print(f"  {sym:6}  mcap={mc_str:>9}  trailingPE={pe_str:>6}  forwardPE={fp_str:>6}")
        cache[sym] = d

    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    print(f"\nWrote {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
