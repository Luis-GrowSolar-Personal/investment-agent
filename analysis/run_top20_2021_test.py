#!/usr/bin/env python3
"""
run_top20_2021_test.py — Test the "use index to pick universe, use algorithm
to improve returns" hypothesis.

Universe: top 20 S&P 500 names by market cap as of January 2021 (with
ADBE substituted for BRK.B since Berkshire doesn't host quarterly calls).

Tests:
- v3 on this universe vs SPY/QQQ/TMFC over 2022-01-01 → latest
- v3 on this universe vs equal-weight (BH and quarterly-rebalanced)
- Per-year breakdown to check robustness across regimes

Pre-reqs (the script will fail loudly if these aren't ready):
- Transcripts in DB and dumped to data/transcripts/ for all 20 tickers
- Eval cache warmed under data/evals/v6/ for every transcript
- Trend verdicts synced (run sync_trend_to_db.py)
- Price cache covering all 20 tickers + SPY/QQQ/TMFC through end date
- Fundamentals cache covering all 20 tickers (for the 3-axis tier classifier)

Usage:
    cd analysis && python3 run_top20_2021_test.py
    cd analysis && python3 run_top20_2021_test.py --keep-brk    # use BRK.B even though it has no calls
    cd analysis && python3 run_top20_2021_test.py --start 2022-04-01    # custom start
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function
from type_classifier import build_type_function, build_driver_count_function


# Top 20 S&P 500 by market cap as of Jan 2021. ADBE substituted for BRK.B
# (Berkshire doesn't host quarterly conference calls, breaking the methodology).
TOP20_2021 = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA",
    "ADBE",  # substitute for BRK.B
    "V", "JNJ", "WMT", "JPM", "PG", "UNH", "DIS", "NVDA",
    "MA", "HD", "PYPL", "BAC", "NFLX",
]
TOP20_2021_KEEP_BRK = TOP20_2021[:6] + ["BRK.B"] + TOP20_2021[7:]


def cagr(initial, final, days):
    if initial <= 0 or days <= 0:
        return 0
    return (final / initial) ** (1 / (days / 365.25)) - 1


def equal_weight_value(tickers, start_date, end_date, capital, prices, rebalance=None):
    """Buy-and-hold by default; quarterly rebalance if rebalance='quarterly'."""
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p

    if rebalance is None:
        total = 0.0
        for t, sh in holdings.items():
            ep = prices.price_on(t, end_date, max_lookback_days=120)
            if ep:
                total += sh * ep
        return total

    cur = start_date
    next_rebal = start_date + timedelta(days=91)
    while cur < end_date:
        if cur >= next_rebal:
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
        total = 0.0
        for t, sh in holdings.items():
            p = prices.price_on(t, cur, max_lookback_days=5)
            if p is not None:
                last[t] = sh * p
            total += last[t]
        daily.append(total)
        cur += timedelta(days=1)
    if not daily:
        return 0.0
    peak = daily[0]
    dd = 0.0
    for v in daily:
        if v > peak:
            peak = v
        if peak > 0:
            d = (peak - v) / peak
            if d > dd:
                dd = d
    return dd


def index_buy_and_hold(ticker, start, end, initial, prices):
    p_start = prices.price_on(ticker, start, max_lookback_days=10)
    p_end = prices.price_on(ticker, end, max_lookback_days=120)
    if not p_start or not p_end:
        return None, None, None
    shares = initial / p_start
    final = shares * p_end
    cur = start
    last_p = p_start
    daily = []
    while cur <= end:
        p = prices.price_on(ticker, cur, max_lookback_days=5)
        if p is not None:
            last_p = p
        daily.append(shares * last_p)
        cur += timedelta(days=1)
    peak = daily[0]
    dd = 0.0
    for v in daily:
        if v > peak:
            peak = v
        if peak > 0:
            d = (peak - v) / peak
            if d > dd:
                dd = d
    return final, cagr(initial, final, (end - start).days), dd


def check_data_ready(tickers, prices, all_events) -> list[str]:
    """Return list of issues, empty if everything is ready."""
    issues = []
    event_tickers = {e.ticker for e in all_events}
    for t in tickers:
        if t not in event_tickers:
            issues.append(f"  missing transcripts: {t}")
        # Spot-check price coverage
        p = prices.price_on(t, date(2022, 1, 1), max_lookback_days=10)
        if p is None:
            issues.append(f"  missing price data near 2022-01-01: {t}")
    for idx in ["SPY", "QQQ", "TMFC"]:
        p = prices.price_on(idx, date(2022, 1, 1), max_lookback_days=10)
        if p is None:
            issues.append(f"  missing index price data: {idx}")
    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep-brk", action="store_true",
                    help="Use BRK.B instead of substituting ADBE (BRK has no quarterly calls).")
    ap.add_argument("--start", default="2022-01-01",
                    help="Simulator start date (default 2022-01-01, gives 1 year of trend-layer history).")
    args = ap.parse_args()

    universe = TOP20_2021_KEEP_BRK if args.keep_brk else TOP20_2021
    print(f"Universe ({len(universe)} names): {', '.join(universe)}")

    print("\nLoading data…")
    prices = PriceLookup.from_cache()
    all_events = load_events_from_cache()

    issues = check_data_ready(universe, prices, all_events)
    if issues:
        print("\nERROR: data not ready for this test. Issues:")
        for s in issues:
            print(s)
        print("\nFix the data first, then re-run.")
        return 1

    print(f"  {len(all_events)} total events loaded")
    print(f"  Universe coverage:")
    for t in universe:
        events = [e for e in all_events if e.ticker == t]
        if events:
            print(f"    {t:<6}  {min(e.call_date for e in events)} → "
                  f"{max(e.call_date for e in events)}  ({len(events)} calls)")

    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    print("\nComputing trend verdicts…")
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    # Load Type A/B classifications
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    n_b = sum(1 for t in universe if type_fn(t) == "B")
    n_a = sum(1 for t in universe if type_fn(t) == "A")
    print(f"  Type classifications: {n_a} Type A, {n_b} Type B (flat 50% Type B cap — production)")

    INITIAL = 100_000
    start = date.fromisoformat(args.start)
    latest = max(e.call_date for e in all_events if e.ticker in universe)
    end = latest

    # Define windows
    windows = [
        ("Full window", start, end),
        ("2022 year",   max(start, date(2022, 1, 15)), date(2023, 1, 14)),
        ("2023 year",   date(2023, 1, 15), date(2024, 1, 14)),
        ("2024 year",   date(2024, 1, 15), date(2025, 1, 14)),
        ("2025 year",   date(2025, 1, 15), date(2026, 1, 14)),
        ("2026 YTD",    date(2026, 1, 15), end),
    ]

    print(f"\n{'WINDOW':<14} {'v3':>11} {'EW(BH)':>11} {'EW(qtr)':>11} {'SPY':>11} {'QQQ':>11} {'TMFC':>11}")
    print(f"{'':14} {'$/CAGR':>11} {'$/CAGR':>11} {'$/CAGR':>11} {'$/CAGR':>11} {'$/CAGR':>11} {'$/CAGR':>11}")
    print("-" * 92)

    rows = []
    for label, s, e in windows:
        if s >= e:
            continue
        days = (e - s).days

        # v3 on top-20-2021 with proper Type A/B
        r = run_simulation(
            start_date=s, end_date=e,
            taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
            universe_tickers=universe, prices=prices, events=all_events,
            decide_fn=decide_v3, tier_for_ticker=tier_fn,
            type_for_ticker=type_fn,
            driver_count_for_ticker=driver_fn,
        )
        sm = compute_summary(r)
        c_v3 = cagr(INITIAL, sm.final_portfolio_value, days)

        ew_bh = equal_weight_value(universe, s, e, INITIAL, prices)
        ew_q  = equal_weight_value(universe, s, e, INITIAL, prices, rebalance="quarterly")
        c_ew_bh = cagr(INITIAL, ew_bh, days)
        c_ew_q  = cagr(INITIAL, ew_q, days)

        spy_f, c_spy, _   = index_buy_and_hold("SPY",  s, e, INITIAL, prices)
        qqq_f, c_qqq, _   = index_buy_and_hold("QQQ",  s, e, INITIAL, prices)
        tmfc_f, c_tmfc, _ = index_buy_and_hold("TMFC", s, e, INITIAL, prices)

        rows.append({
            "label": label,
            "v3_final": sm.final_portfolio_value, "v3_cagr": c_v3, "v3_dd": sm.max_drawdown_pct,
            "ew_bh": ew_bh, "c_ew_bh": c_ew_bh,
            "ew_q":  ew_q,  "c_ew_q":  c_ew_q,
            "spy": spy_f, "c_spy": c_spy,
            "qqq": qqq_f, "c_qqq": c_qqq,
            "tmfc": tmfc_f, "c_tmfc": c_tmfc,
        })

        print(f"{label:<14} ${sm.final_portfolio_value/1000:>4.0f}k/{c_v3*100:>+5.1f}% "
              f"${ew_bh/1000:>4.0f}k/{c_ew_bh*100:>+5.1f}% "
              f"${ew_q/1000:>4.0f}k/{c_ew_q*100:>+5.1f}% "
              f"${spy_f/1000:>4.0f}k/{c_spy*100:>+5.1f}% "
              f"${qqq_f/1000:>4.0f}k/{c_qqq*100:>+5.1f}% "
              f"${tmfc_f/1000:>4.0f}k/{c_tmfc*100:>+5.1f}%")

    # Drawdown comparison on full window
    print(f"\nMax DD comparison (full window):")
    full = rows[0]
    full_s, full_e = windows[0][1], windows[0][2]
    print(f"  v3:        {full['v3_dd']*100:.1f}%")
    print(f"  EW(BH):    {equal_weight_drawdown(universe, full_s, full_e, INITIAL, prices)*100:.1f}%")
    for idx in ["SPY", "QQQ", "TMFC"]:
        _, _, dd = index_buy_and_hold(idx, full_s, full_e, INITIAL, prices)
        print(f"  {idx:<10} {dd*100:.1f}%")

    # Verdict — does v3 beat each baseline on the full window?
    print(f"\nFull-window verdict:")
    full = rows[0]
    for label, key in [("EW(BH)", "ew_bh"), ("EW(quarterly)", "ew_q"),
                       ("SPY", "spy"), ("QQQ", "qqq"), ("TMFC", "tmfc")]:
        delta = full["v3_final"] - full[key]
        marker = "✓ v3 wins" if delta > 0 else "✗ v3 loses"
        print(f"  v3 vs {label:<14}: ${delta:>+9,.0f}  {marker}")

    print(f"\nPer-year wins for v3 vs each baseline:")
    for label, key in [("EW(BH)", "ew_bh"), ("EW(quarterly)", "ew_q"),
                       ("SPY", "spy"), ("QQQ", "qqq"), ("TMFC", "tmfc")]:
        wins = sum(1 for r in rows[1:] if r["v3_final"] > r[key])
        total = len(rows) - 1
        print(f"  v3 vs {label:<14}: {wins}/{total} years")

    # Hypothesis verdict
    n_baselines_beat = sum(1 for key in ["spy", "qqq", "tmfc"] if full["v3_final"] > full[key])
    print(f"\nHypothesis: 'use index to pick universe, use v3 to allocate' beats passive indexes")
    if n_baselines_beat == 3:
        print("→ STRONG SUPPORT. v3 beats SPY, QQQ, AND TMFC on the index-derived universe.")
    elif n_baselines_beat >= 1:
        print(f"→ MIXED. v3 beats {n_baselines_beat}/3 indexes. Examine which it lost to and why.")
    else:
        print("→ HYPOTHESIS REJECTED. v3 does not beat any of the major indexes on this universe.")

    print()


if __name__ == "__main__":
    main()
