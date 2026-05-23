#!/usr/bin/env python3
"""
fetch_analyst_consensus.py — Pull analyst consensus data per ticker from yfinance.

Output: data/analyst_consensus_cache.json. Per ticker:
  {
    "ticker": "AAPL",
    "n_analysts": 35,
    "mean_target": 250.0,
    "median_target": 245.0,
    "high_target": 320.0,
    "low_target": 180.0,
    "current_price": 247.5,
    "upside_pct": 1.0,
    "target_dispersion_cv": 0.08,    # std/mean — relative dispersion
    "recommendation_mean": 1.8,       # 1=Strong Buy, 5=Strong Sell
    "recent_eps_revision_dir": +1,    # +1 up, -1 down, 0 flat (last 3 months)
    "fetched_at": "2026-05-02"
  }

Usage:
    cd analysis && python3 fetch_analyst_consensus.py
    cd analysis && python3 fetch_analyst_consensus.py --tickers AAPL MSFT NVDA

Notes on coverage:
  - Mega-caps (AAPL, MSFT, NVDA, etc.): ~25-50 analysts, comprehensive data
  - Small/specs (AMPX, ENVX, EOSE, etc.): often 3-8 analysts, sparser data
  - yfinance fields can vary by ticker; we extract what's available and
    record None for missing fields rather than failing hard.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance")

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_PATH = SCRIPT_DIR / "data" / "analyst_consensus_cache.json"
MANIFEST_PATH = SCRIPT_DIR / "data" / "transcripts" / "_manifest.json"


def fetch_one(symbol: str) -> dict:
    """Fetch consensus data for one ticker. Returns a dict with whatever
    fields yfinance exposes; missing fields are None."""
    out = {
        "ticker": symbol,
        "n_analysts": None,
        "mean_target": None,
        "median_target": None,
        "high_target": None,
        "low_target": None,
        "current_price": None,
        "upside_pct": None,
        "target_dispersion_cv": None,
        "recommendation_mean": None,
        "recent_eps_revision_dir": None,
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "error": None,
    }
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        # Price targets (older yfinance puts these in info)
        out["n_analysts"] = info.get("numberOfAnalystOpinions")
        out["mean_target"] = info.get("targetMeanPrice")
        out["median_target"] = info.get("targetMedianPrice")
        out["high_target"] = info.get("targetHighPrice")
        out["low_target"] = info.get("targetLowPrice")
        out["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        out["recommendation_mean"] = info.get("recommendationMean")  # 1-5 scale

        # Compute upside %
        if out["mean_target"] and out["current_price"]:
            out["upside_pct"] = (out["mean_target"] / out["current_price"] - 1) * 100

        # Compute dispersion (coefficient of variation = std / mean)
        if out["high_target"] and out["low_target"] and out["mean_target"]:
            # Approximation: sd ≈ (high - low) / 4 for normal-ish distributions
            est_sd = (out["high_target"] - out["low_target"]) / 4.0
            out["target_dispersion_cv"] = est_sd / out["mean_target"]

        # EPS revision direction: compare current quarter estimate to 90-day-old
        try:
            est = t.earnings_estimate
            # est is a DataFrame indexed by period; we want current-quarter (0q)
            # avg estimate trend over time
            if hasattr(est, "loc") and "0q" in est.index:
                row = est.loc["0q"]
                avg_now = row.get("avg")
                # The .earnings_history or eps_revisions API differs by version.
                # Try a few sources:
                rev = t.eps_revisions
                if hasattr(rev, "loc") and "0q" in rev.index:
                    rrow = rev.loc["0q"]
                    up = rrow.get("upLast30days") or 0
                    down = rrow.get("downLast30days") or 0
                    if up + down > 0:
                        if up > down + 1:
                            out["recent_eps_revision_dir"] = +1
                        elif down > up + 1:
                            out["recent_eps_revision_dir"] = -1
                        else:
                            out["recent_eps_revision_dir"] = 0
        except Exception:
            pass  # eps_revisions not always available; leave as None

    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def default_tickers() -> list[str]:
    """Tickers from the local transcripts manifest (skips missing files)."""
    if not MANIFEST_PATH.exists():
        return []
    return sorted(set(m["ticker"] for m in json.loads(MANIFEST_PATH.read_text())))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="Restrict to these symbols. Default: all in manifest.")
    args = ap.parse_args()

    tickers = args.tickers if args.tickers else default_tickers()
    if not tickers:
        sys.exit("No tickers to fetch (check --tickers or transcripts manifest)")

    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())

    print(f"Fetching analyst consensus for {len(tickers)} ticker(s):")
    print(f"{'TICKER':<8} {'#anal':>5} {'mean_tgt':>10} {'cur':>10} {'upside':>7} "
          f"{'disp':>6} {'rec':>5} {'rev':>5}")
    for t in tickers:
        d = fetch_one(t)
        cache[t] = d
        n = d["n_analysts"] or "?"
        mt = f"${d['mean_target']:.2f}" if d['mean_target'] else "—"
        cp = f"${d['current_price']:.2f}" if d['current_price'] else "—"
        up = f"{d['upside_pct']:+.1f}%" if d['upside_pct'] is not None else "—"
        dp = f"{d['target_dispersion_cv']:.2f}" if d['target_dispersion_cv'] else "—"
        rec = f"{d['recommendation_mean']:.1f}" if d['recommendation_mean'] else "—"
        rev = {1: "↑", -1: "↓", 0: "·", None: "—"}.get(d['recent_eps_revision_dir'])
        flag = " [ERROR]" if d.get("error") else ""
        print(f"{t:<8} {str(n):>5} {mt:>10} {cp:>10} {up:>7} {dp:>6} {rec:>5} {rev:>5}{flag}")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    print(f"\nWrote {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
