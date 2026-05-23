#!/usr/bin/env python3
"""
run_v3_established_per_year.py — Compare v3-on-established vs v3-on-all-16
across each year of the dataset. Tests whether the "drop the specs"
conclusion holds in EVERY regime, or only in aggregate.

If v3-established beats v3-all-16 in every year → the conclusion is robust.
If there's a year where specs would have helped → understand why before
committing.

Usage:
    cd analysis && python3 run_v3_established_per_year.py
"""
from __future__ import annotations

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

ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def cagr(initial, final, days):
    if initial <= 0 or days <= 0:
        return 0
    return (final / initial) ** (1 / (days / 365.25)) - 1


def equal_weight_value(tickers, start_date, end_date, capital, prices):
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p
    total = 0.0
    for t, sh in holdings.items():
        ep = prices.price_on(t, end_date, max_lookback_days=120)
        if ep:
            total += sh * ep
    return total


def main():
    print("Loading data…")
    prices = PriceLookup.from_cache()
    all_events = load_events_from_cache()

    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    print("Computing trend verdicts…")
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    INITIAL = 100_000

    # Define windows: full + each year
    latest = max(e.call_date for e in all_events)
    windows = [
        ("Full window", date(2022, 1, 1), latest),
        ("2022 year",   date(2022, 1, 15), date(2023, 1, 14)),
        ("2023 year",   date(2023, 1, 15), date(2024, 1, 14)),
        ("2024 year",   date(2024, 1, 15), date(2025, 1, 14)),
        ("2025 year",   date(2025, 1, 15), date(2026, 1, 14)),
        ("2026 YTD",    date(2026, 1, 15), latest),
    ]

    print(f"\n{'WINDOW':<14} {'v3-Estab':>11} {'v3-ALL16':>11} {'EW-Estab':>11} {'EW-ALL16':>11} {'Δ ESTAB':>9}")
    print(f"{'':14} {'$ / CAGR':>11} {'$ / CAGR':>11} {'$ / CAGR':>11} {'$ / CAGR':>11} {'pp/CAGR':>9}")
    print("-" * 80)

    rows = []
    for label, s, e in windows:
        if s >= e:
            continue
        days = (e - s).days

        # v3 on Established only
        r_est = run_simulation(
            start_date=s, end_date=e,
            taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
            universe_tickers=ESTABLISHED, prices=prices, events=all_events,
            decide_fn=decide_v3, tier_for_ticker=tier_fn,
        )
        s_est = compute_summary(r_est)
        c_est = cagr(INITIAL, s_est.final_portfolio_value, days)

        # v3 on All 16
        r_all = run_simulation(
            start_date=s, end_date=e,
            taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
            universe_tickers=ALL16, prices=prices, events=all_events,
            decide_fn=decide_v3, tier_for_ticker=tier_fn,
        )
        s_all = compute_summary(r_all)
        c_all = cagr(INITIAL, s_all.final_portfolio_value, days)

        # Equal-weight baselines (BH)
        ew_est = equal_weight_value(ESTABLISHED, s, e, INITIAL, prices)
        ew_all = equal_weight_value(ALL16, s, e, INITIAL, prices)
        c_ew_est = cagr(INITIAL, ew_est, days)
        c_ew_all = cagr(INITIAL, ew_all, days)

        delta = c_est - c_all
        rows.append({
            "label": label,
            "est_final": s_est.final_portfolio_value, "est_cagr": c_est,
            "all_final": s_all.final_portfolio_value, "all_cagr": c_all,
            "ew_est_final": ew_est, "ew_est_cagr": c_ew_est,
            "ew_all_final": ew_all, "ew_all_cagr": c_ew_all,
            "delta": delta,
        })

        marker = "✓" if delta > 0 else "✗"
        print(f"{label:<14} ${s_est.final_portfolio_value/1000:>4.0f}k/{c_est*100:>+5.1f}% "
              f"${s_all.final_portfolio_value/1000:>4.0f}k/{c_all*100:>+5.1f}% "
              f"${ew_est/1000:>4.0f}k/{c_ew_est*100:>+5.1f}% "
              f"${ew_all/1000:>4.0f}k/{c_ew_all*100:>+5.1f}% "
              f"{delta*100:>+6.1f}pp {marker}")

    print()
    n_wins = sum(1 for r in rows[1:] if r["delta"] > 0)
    print(f"v3-Established beat v3-ALL16 in {n_wins}/{len(rows)-1} per-year windows.")
    if n_wins == len(rows) - 1:
        print("→ Conclusion is robust across every regime. 'Drop the specs' is a sound rule.")
    elif n_wins >= len(rows) - 2:
        print("→ Conclusion holds in most years. Examine the exception(s) for what went different.")
    else:
        print("→ Conclusion may be a full-window aggregate effect. Examine year-by-year drivers.")

    # Detailed maxDD comparison on full window
    print(f"\nMax DD comparison (full window):")
    full = rows[0]
    # Re-run to get DD (compute_summary already had it)
    r_est_full = run_simulation(
        start_date=date(2022,1,1), end_date=latest,
        taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
        universe_tickers=ESTABLISHED, prices=prices, events=all_events,
        decide_fn=decide_v3, tier_for_ticker=tier_fn,
    )
    r_all_full = run_simulation(
        start_date=date(2022,1,1), end_date=latest,
        taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
        universe_tickers=ALL16, prices=prices, events=all_events,
        decide_fn=decide_v3, tier_for_ticker=tier_fn,
    )
    print(f"  v3-Established max DD: {compute_summary(r_est_full).max_drawdown_pct*100:.1f}%")
    print(f"  v3-ALL16 max DD:       {compute_summary(r_all_full).max_drawdown_pct*100:.1f}%")


if __name__ == "__main__":
    main()
