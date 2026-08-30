#!/usr/bin/env python3
"""
run_db_corpus_baseline.py — Reproduce the $287k full-window v3 reference,
sourcing events from the Railway "Analysis" table instead of the missing
file-based v6 eval cache.

Scratch script for task #77's measurement plan
(prompts/run-allocator-sweep-db-corpus.md, Step 1). Same universe, capital,
and allocator call as run_expanded_test.py's "Full window" scenario; only
the event source differs (data.load_call_events() vs
data_from_cache.load_events_from_cache()).

Usage:
    cd analysis && python3 run_db_corpus_baseline.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup, load_call_events
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function
from type_classifier import build_type_function, build_driver_count_function

ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def main() -> int:
    print("Loading events from DB (pre-cutoff only, default cutoff)...")
    events = load_call_events(tickers=ALL16)
    print(f"  {len(events)} events loaded for ALL16")

    dates = [e.call_date for e in events]
    earliest, latest = min(dates), max(dates)
    print(f"  Span: {earliest} -> {latest}")

    prices = PriceLookup.from_cache()

    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )

    # Step 0e: assert type_for_ticker resolves for every ticker in this
    # universe -- a run without it silently falls back to per-event
    # classification (usually None -> Type A default), which is the
    # precedence-rank-2 path PORTFOLIO_ANALYST_SPEC.md warns inflates
    # drawdown (60.9% vs 37.1%).
    missing_type = [t for t in ALL16 if type_fn(t) not in ("A", "B")]
    if missing_type:
        print(f"FATAL: type_for_ticker has no A/B classification for: {missing_type}")
        return 1
    print(f"  type_for_ticker OK for all {len(ALL16)} tickers")

    full_start = max(earliest + timedelta(days=365), date(2022, 1, 1))
    full_end = latest
    print(f"\nFull window: {full_start} -> {full_end}")

    INITIAL = 100_000
    result = run_simulation(
        start_date=full_start,
        end_date=full_end,
        taxable_cash=INITIAL / 2,
        tax_advantaged_cash=INITIAL / 2,
        universe_tickers=ALL16,
        prices=prices,
        events=events,
        decide_fn=decide_v3,
        tier_for_ticker=tier_fn,
        type_for_ticker=type_fn,
        driver_count_for_ticker=driver_fn,
    )
    summary = compute_summary(result)
    print(f"\nFinal value: ${summary.final_portfolio_value:,.0f}")
    print(f"Max drawdown: {summary.max_drawdown_pct*100:.1f}%")
    print(f"Reference (file-cache, pre-cutoff production): $287k full-window v3 flat-50% Type B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
