#!/usr/bin/env python3
"""
run_expanded_test.py — Re-run the simulator on expanded historical data.

Goal: with transcripts loaded back to 2021, re-test the agent (v1, v3, v4)
against equal-weight baselines across multiple time windows that span
distinct market regimes.

Designed to be re-runnable: reads whatever's in the local v6 cache + price
cache. As you load more historical data and run dump_transcripts +
eval_cache_warmer + sync_trend_to_db, this script picks up the new events
automatically.

Usage:
    cd analysis && python3 run_expanded_test.py
    cd analysis && python3 run_expanded_test.py --include-v4   # if consensus data fetched
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator import decide as decide_v1
from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.allocator_v4 import decide as decide_v4
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function
from type_classifier import build_type_function, build_driver_count_function


ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def cagr(initial, final, days):
    if initial <= 0 or days <= 0: return 0
    return (final / initial) ** (1 / (days / 365.25)) - 1


def equal_weight_value(tickers, start_date, end_date, capital, prices, rebalance=None):
    """Equal-weight buy-and-hold by default, or with periodic rebalancing.
    rebalance: None (buy-and-hold), 'quarterly' (rebalance every ~91 days)."""
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p

    if rebalance is None:
        # Pure buy-and-hold
        total = 0.0
        for t, sh in holdings.items():
            ep = prices.price_on(t, end_date, max_lookback_days=120)
            if ep:
                total += sh * ep
        return total

    # Quarterly rebalance: every 91 days, sell everything and re-buy equal weight
    cur = start_date
    next_rebal = start_date + timedelta(days=91)
    while cur < end_date:
        if cur >= next_rebal:
            # Mark to market, redistribute
            total = 0.0
            for t, sh in holdings.items():
                p = prices.price_on(t, cur, max_lookback_days=10)
                if p:
                    total += sh * p
            per = total / len(holdings) if holdings else 0
            for t in list(holdings.keys()):
                p = prices.price_on(t, cur, max_lookback_days=10)
                if p and p > 0:
                    holdings[t] = per / p
            next_rebal = cur + timedelta(days=91)
        cur += timedelta(days=1)
    final = 0.0
    for t, sh in holdings.items():
        ep = prices.price_on(t, end_date, max_lookback_days=120)
        if ep:
            final += sh * ep
    return final


def equal_weight_drawdown(tickers, start_date, end_date, capital, prices):
    per = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per / p
    last = {t: 0.0 for t in holdings}
    daily = []
    cur = start_date
    while cur <= end_date:
        total = 0
        for t, sh in holdings.items():
            p = prices.price_on(t, cur, max_lookback_days=5)
            if p is not None:
                last[t] = sh * p
            total += last[t]
        daily.append(total)
        cur += timedelta(days=1)
    if not daily: return 0.0
    peak = daily[0]; dd = 0
    for v in daily:
        if v > peak: peak = v
        if peak > 0:
            d = (peak - v) / peak
            if d > dd: dd = d
    return dd


def detect_data_span(events) -> tuple[date, date, dict]:
    """Find the date range of the loaded events and what tickers cover what."""
    by_ticker = {}
    for e in events:
        by_ticker.setdefault(e.ticker, []).append(e.call_date)
    summary = {}
    for t, dates in by_ticker.items():
        summary[t] = (min(dates), max(dates), len(dates))
    earliest = min(min(d) for d in by_ticker.values())
    latest = max(max(d) for d in by_ticker.values())
    return earliest, latest, summary


def _build_default_scenarios(earliest, latest):
    """Auto-generate scenario list based on data span. As more data loads,
    additional windows become testable."""
    scenarios = []

    # Full-data window (1 year buffer at start so universe gate is met)
    full_start = max(earliest + timedelta(days=365), date(2022, 1, 1))
    if full_start < latest:
        scenarios.append((f"Full window: {full_start} → {latest}", ALL16, full_start, latest))
        scenarios.append((f"Established only: {full_start} → {latest}",
                            ESTABLISHED, full_start, latest))
        scenarios.append((f"Speculative only: {full_start} → {latest}",
                            SPECULATIVE, full_start, latest))

    # Year-by-year windows, last 4 years
    for yr in range(latest.year - 3, latest.year + 1):
        s = date(yr, 1, 15)
        e = min(date(yr + 1, 1, 14), latest)
        if s >= earliest and e > s and (e - s).days > 60:
            scenarios.append((f"{yr} year: {s} → {e}", ALL16, s, e))

    # The original 21-month window for continuity
    if date(2024, 8, 1) >= earliest and date(2026, 4, 30) <= latest + timedelta(days=30):
        scenarios.append((f"Original Run 1 window (21mo)", ALL16,
                          date(2024, 8, 1), min(date(2026, 4, 30), latest)))

    return scenarios


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-v4", action="store_true",
                    help="Also test allocator_v4 (consensus overlay). "
                         "Requires data/analyst_consensus_cache.json — run "
                         "fetch_analyst_consensus.py first.")
    args = ap.parse_args()

    print("Loading data…")
    prices = PriceLookup.from_cache()
    all_events = load_events_from_cache()
    earliest, latest, span_summary = detect_data_span(all_events)
    print(f"  {len(all_events)} events, {len(span_summary)} tickers")
    print(f"  Span: {earliest} → {latest}")

    # Per-ticker coverage diagnostic
    print(f"\nPer-ticker coverage:")
    for t in sorted(span_summary.keys()):
        first, last, n = span_summary[t]
        print(f"  {t:<6}  {first} → {last}  ({n} calls)")

    # Compute trend verdicts ONCE
    print("\nComputing trend verdicts…")
    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    # Load ticker-level Type A/B classifications. Allocator uses these
    # instead of the (mostly empty) per-event classifications from the cache.
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    n_b = sum(1 for t in {e.ticker for e in all_events} if type_fn(t) == "B")
    n_a = sum(1 for t in {e.ticker for e in all_events} if type_fn(t) == "A")
    print(f"  Type classifications: {n_a} Type A, {n_b} Type B (flat 50% Type B cap — production)")

    # Check v4 prerequisites
    if args.include_v4:
        consensus_path = SCRIPT_DIR / "data" / "analyst_consensus_cache.json"
        if not consensus_path.exists():
            print(f"\nERROR: --include-v4 requires {consensus_path}.")
            print(f"Run: python3 fetch_analyst_consensus.py")
            return 1

    scenarios = _build_default_scenarios(earliest, latest)
    if not scenarios:
        print("No scenarios fit the data window. Need at least 1 year of buffer "
              "from earliest event to start the simulator.")
        return 1

    INITIAL = 100_000
    print(f"\nRunning {len(scenarios)} scenario(s) with $100k initial capital, 50/50 split:")
    print()

    cols = ["v1", "v3"] + (["v4"] if args.include_v4 else []) + ["EW(BH)", "EW(quarterly)"]
    header = f"{'SCENARIO':<48}" + "".join(f"{c:>13}" for c in cols)
    print(header)
    print("-" * len(header))

    rows = []
    for label, tickers, s, e in scenarios:
        # v1 — no type function (v1 only uses analyst's per-event type, which
        # is mostly None → defaults to Type A everywhere)
        r1 = run_simulation(
            start_date=s, end_date=e,
            taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
            universe_tickers=tickers, prices=prices, events=all_events,
            decide_fn=decide_v1, tier_for_ticker=None,
            type_for_ticker=type_fn,
            driver_count_for_ticker=driver_fn,
        )
        s1 = compute_summary(r1)

        # v3 with proper Type A/B classifications
        r3 = run_simulation(
            start_date=s, end_date=e,
            taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
            universe_tickers=tickers, prices=prices, events=all_events,
            decide_fn=decide_v3, tier_for_ticker=tier_fn,
            type_for_ticker=type_fn,
            driver_count_for_ticker=driver_fn,
        )
        s3 = compute_summary(r3)

        s4 = None
        if args.include_v4:
            r4 = run_simulation(
                start_date=s, end_date=e,
                taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
                universe_tickers=tickers, prices=prices, events=all_events,
                decide_fn=decide_v4, tier_for_ticker=tier_fn,
                type_for_ticker=type_fn,
                driver_count_for_ticker=driver_fn,
            )
            s4 = compute_summary(r4)

        ew_bh = equal_weight_value(tickers, s, e, INITIAL, prices, rebalance=None)
        ew_q = equal_weight_value(tickers, s, e, INITIAL, prices, rebalance="quarterly")
        ew_dd = equal_weight_drawdown(tickers, s, e, INITIAL, prices)

        days = (e - s).days
        row = {
            "label": label, "tickers": tickers, "days": days,
            "v1_final": s1.final_portfolio_value,
            "v3_final": s3.final_portfolio_value,
            "v4_final": s4.final_portfolio_value if s4 else None,
            "ew_bh_final": ew_bh, "ew_q_final": ew_q,
            "v1_dd": s1.max_drawdown_pct,
            "v3_dd": s3.max_drawdown_pct,
            "v4_dd": s4.max_drawdown_pct if s4 else None,
            "ew_dd": ew_dd,
            "v1_cagr": s1.portfolio_cagr,
            "v3_cagr": s3.portfolio_cagr,
            "v4_cagr": s4.portfolio_cagr if s4 else None,
            "ew_bh_cagr": cagr(INITIAL, ew_bh, days),
            "ew_q_cagr": cagr(INITIAL, ew_q, days),
        }
        rows.append(row)

        cells = [s1.final_portfolio_value, s3.final_portfolio_value]
        if args.include_v4:
            cells.append(s4.final_portfolio_value)
        cells.extend([ew_bh, ew_q])
        cell_strs = "".join(f"${c:>11,.0f}" for c in cells)
        print(f"{label:<48}{cell_strs}")

    print()
    print("CAGR table:")
    cagr_header = f"{'SCENARIO':<48}" + "".join(f"{c:>10}" for c in cols)
    print(cagr_header)
    print("-" * len(cagr_header))
    for r in rows:
        cells = [r["v1_cagr"], r["v3_cagr"]]
        if args.include_v4:
            cells.append(r["v4_cagr"])
        cells.extend([r["ew_bh_cagr"], r["ew_q_cagr"]])
        cell_strs = "".join(f"{c*100:>+9.1f}%" for c in cells)
        print(f"{r['label']:<48}{cell_strs}")

    print()
    print("Drawdown table:")
    dd_header = f"{'SCENARIO':<48}" + f"{'v1':>8}{'v3':>8}"
    if args.include_v4: dd_header += f"{'v4':>8}"
    dd_header += f"{'EW':>8}"
    print(dd_header)
    print("-" * len(dd_header))
    for r in rows:
        cells = [r["v1_dd"], r["v3_dd"]]
        if args.include_v4: cells.append(r["v4_dd"])
        cells.append(r["ew_dd"])
        cell_strs = "".join(f"{c*100:>7.1f}%" for c in cells)
        print(f"{r['label']:<48}{cell_strs}")

    # Verdict: how often does each strategy beat EW (buy-and-hold) on absolute return?
    print()
    print("Verdict — wins vs EW(BH):")
    for v in cols[:-2]:  # skip the EW columns themselves
        wins = sum(1 for r in rows
                   if (r[f"{v}_final"] or 0) > r["ew_bh_final"])
        soft_wins = sum(1 for r in rows
                        if (r[f"{v}_final"] or 0) >= r["ew_bh_final"] * 0.95)
        print(f"  {v}: {wins}/{len(rows)} hard wins, {soft_wins}/{len(rows)} within 5%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
