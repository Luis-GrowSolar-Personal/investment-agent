#!/usr/bin/env python3
"""
run_v2_full_window.py — Compute v2's CAGR and Max DD for the full-window
scenario only, so we can drop the row into the v1/v3/v4/EW comparison table.

Window: 2022-01-01 → latest event date (2026-04-30 currently).
Universe: ALL16 (same as run_expanded_test.py's "Full window" row).

Usage:
    cd analysis && python3 run_v2_full_window.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v2 import decide as decide_v2
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function

ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def cagr(initial, final, days):
    if initial <= 0 or days <= 0:
        return 0
    return (final / initial) ** (1 / (days / 365.25)) - 1


def main():
    print("Loading data…")
    prices = PriceLookup.from_cache()
    all_events = load_events_from_cache()
    latest = max(e.call_date for e in all_events)

    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    print("Computing trend verdicts…")
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    start = date(2022, 1, 1)
    end = latest
    INITIAL = 100_000

    print(f"\nRunning v2 on full window: {start} → {end}")
    r2 = run_simulation(
        start_date=start, end_date=end,
        taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
        universe_tickers=ALL16, prices=prices, events=all_events,
        decide_fn=decide_v2, tier_for_ticker=tier_fn,
    )
    s2 = compute_summary(r2)
    days = (end - start).days
    c = cagr(INITIAL, s2.final_portfolio_value, days)

    print()
    print(f"v2 final value:  ${s2.final_portfolio_value:>11,.0f}")
    print(f"v2 CAGR:         {c*100:>+7.1f}%")
    print(f"v2 Max DD:       {s2.max_drawdown_pct*100:>7.1f}%")
    print(f"v2 # buys:       {s2.n_buys}")
    print(f"v2 # sells:      {s2.n_sells}")


if __name__ == "__main__":
    main()
