"""
type_classifier.py — Ticker-level Type A/B classification loader.

The simulator's allocator wants to know whether each ticker is Type A
(single-driver, lower cap) or Type B (multi-driver platform, higher cap).
Historically this came per-call from the analyst's structured score, but
that field has always been None/"A" since the v6 prompt doesn't output it
explicitly.

This module reads the curated ticker-level classifications from
data/type_classifications.json and returns a lookup function that the
simulator threads into the allocator.

Usage:
    from type_classifier import build_type_function
    type_fn = build_type_function()
    type_fn("AAPL")  # → "B"
    type_fn("AMPX")  # → "A"
    type_fn("ZZZZ")  # → None (unknown)

The simulator should call this once and pass the resulting function
through to each allocator invocation. When passed, it takes precedence
over the per-event type_classification from the cached evals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PATH = SCRIPT_DIR / "data" / "type_classifications.json"


def build_type_function(path: Optional[Path] = None) -> Callable[[str], Optional[str]]:
    """Return a function (ticker → 'A' | 'B' | None) reading the JSON file."""
    path = path or DEFAULT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Type classifications not found at {path}. "
            f"Run the classifier or check data/ directory."
        )
    data = json.loads(path.read_text())
    classifications = data.get("classifications", {})

    type_by_ticker: dict[str, str] = {}
    for ticker, info in classifications.items():
        t = info.get("type")
        if t in ("A", "B"):
            type_by_ticker[ticker] = t

    def lookup(ticker: str) -> Optional[str]:
        return type_by_ticker.get(ticker)

    return lookup


def get_driver_count(ticker: str, path: Optional[Path] = None) -> Optional[int]:
    """Return the analyst's active driver count for the ticker, or None.
    Reserved for variable-cap Type B implementation (40-60% based on driver count)."""
    path = path or DEFAULT_PATH
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    info = data.get("classifications", {}).get(ticker, {})
    return info.get("drivers")


def build_driver_count_function(path: Optional[Path] = None) -> Callable[[str], Optional[int]]:
    """Return a function (ticker → driver count int or None) reading the JSON.
    Pass into run_simulation's driver_count_for_ticker parameter to enable
    variable Type B cap (40-60% based on driver count) in allocator_v2/v3/v4."""
    path = path or DEFAULT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Type classifications not found at {path}. "
            f"Run the classifier or check data/ directory."
        )
    data = json.loads(path.read_text())
    classifications = data.get("classifications", {})

    driver_by_ticker: dict[str, int] = {}
    for ticker, info in classifications.items():
        d = info.get("drivers")
        if isinstance(d, int) and d > 0:
            driver_by_ticker[ticker] = d

    def lookup(ticker: str) -> Optional[int]:
        return driver_by_ticker.get(ticker)

    return lookup


if __name__ == "__main__":
    fn = build_type_function()
    # Quick self-test on a few known tickers
    samples = [("AAPL", "B"), ("AMPX", "A"), ("TSLA", "B"), ("META", "B"),
               ("NFLX", "A"), ("PYPL", "A"), ("UNKNOWN", None)]
    for ticker, expected in samples:
        actual = fn(ticker)
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {ticker:<10} expected={expected!s:<6} actual={actual!s}")
