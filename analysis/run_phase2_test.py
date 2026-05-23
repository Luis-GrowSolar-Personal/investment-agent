#!/usr/bin/env python3
"""
run_phase2_test.py — Paper test of Phase 2 allocator changes.

Runs all 4 scenarios with v1 (current) and v2 (Phase 2 sizing) allocators,
plus equal-weight buy-and-hold of the same universe. Prints a comparison
matrix and applies the pre-declared decision rule.

Decision rule (committed BEFORE seeing results):
  - v2 must close ≥ half the gap between v1 and equal-weight in 3 of 4
    scenarios → recommend continuing Phase 2.
  - Otherwise → recommend pausing Phase 2 and rethinking the architecture.

Runs entirely from local cache + price data. No DB or network required.
"""
from __future__ import annotations

import json
import sys
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator import decide as decide_v1
from analysis.simulator.allocator_v2 import decide as decide_v2
from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function


ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def equal_weight_value(tickers, start_date, end_date, capital, prices):
    """Equal-weight buy-and-hold value at end_date. Uses last-available
    price fallback for tickers whose price series ends before end_date."""
    per_ticker = capital / len(tickers)
    holdings = []
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p is None or p <= 0:
            continue
        holdings.append((t, per_ticker / p))
    final = 0.0
    for t, sh in holdings:
        ep = prices.price_on(t, end_date, max_lookback_days=120)
        if ep is None:
            continue
        final += sh * ep
    return final


def equal_weight_drawdown(tickers, start_date, end_date, capital, prices):
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p is None or p <= 0:
            continue
        holdings[t] = per_ticker / p
    # Daily values with last-known fallback
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
    peak = daily[0]; max_dd = 0.0
    for v in daily:
        if v > peak: peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd: max_dd = dd
    return max_dd


def cagr(initial, final, days):
    if initial <= 0 or days <= 0: return 0
    years = days / 365.25
    return (final / initial) ** (1 / years) - 1


def main():
    print("Loading data…")
    prices = PriceLookup.from_cache()
    all_events = load_events_from_cache()
    print(f"  {len(all_events)} events, "
          f"{len({e.ticker for e in all_events})} tickers")

    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )

    # Compute trend verdicts ONCE on the full event set, as both runs use
    # the same per-call recs and trend layer.
    print("Computing trend verdicts…")
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    SCENARIOS = [
        ("Run 1 — All 16, Aug '24→Apr '26", ALL16, date(2024,8,1), date(2026,4,30)),
        ("Run 2 — Established, Aug '24→Apr '26", ESTABLISHED, date(2024,8,1), date(2026,4,30)),
        ("Run 3 — Speculative, Aug '24→Apr '26", SPECULATIVE, date(2024,8,1), date(2026,4,30)),
        ("Run 4 — All 16, Jan '25→Apr '26", ALL16, date(2025,1,15), date(2026,4,30)),
    ]
    INITIAL_CAPITAL = 100_000

    print(f"\n{'='*112}")
    print(f"{'SCENARIO':<40} {'v1 Final':>11} {'v2 Final':>11} {'v3 Final':>11} {'EW Final':>11} {'v1 DD':>6} {'v2 DD':>6} {'v3 DD':>6} {'EW DD':>6}")
    print("="*112)

    rows = []
    for label, tickers, start, end in SCENARIOS:
        # Run v1
        r1 = run_simulation(
            start_date=start, end_date=end,
            taxable_cash=INITIAL_CAPITAL/2, tax_advantaged_cash=INITIAL_CAPITAL/2,
            universe_tickers=tickers,
            prices=prices, events=all_events,
            decide_fn=decide_v1, tier_for_ticker=None,  # v1 doesn't need tier
        )
        s1 = compute_summary(r1)

        # Run v2 with tier function
        r2 = run_simulation(
            start_date=start, end_date=end,
            taxable_cash=INITIAL_CAPITAL/2, tax_advantaged_cash=INITIAL_CAPITAL/2,
            universe_tickers=tickers,
            prices=prices, events=all_events,
            decide_fn=decide_v2, tier_for_ticker=tier_fn,
        )
        s2 = compute_summary(r2)

        # Run v3 (v2 + first-call starter)
        r3 = run_simulation(
            start_date=start, end_date=end,
            taxable_cash=INITIAL_CAPITAL/2, tax_advantaged_cash=INITIAL_CAPITAL/2,
            universe_tickers=tickers,
            prices=prices, events=all_events,
            decide_fn=decide_v3, tier_for_ticker=tier_fn,
        )
        s3 = compute_summary(r3)

        # Equal-weight
        ew_final = equal_weight_value(tickers, start, end, INITIAL_CAPITAL, prices)
        ew_dd = equal_weight_drawdown(tickers, start, end, INITIAL_CAPITAL, prices)

        days = (end - start).days
        rows.append({
            "label": label,
            "tickers": tickers,
            "v1_final": s1.final_portfolio_value,
            "v2_final": s2.final_portfolio_value,
            "v3_final": s3.final_portfolio_value,
            "ew_final": ew_final,
            "v1_dd": s1.max_drawdown_pct,
            "v2_dd": s2.max_drawdown_pct,
            "v3_dd": s3.max_drawdown_pct,
            "ew_dd": ew_dd,
            "v1_cagr": s1.portfolio_cagr,
            "v2_cagr": s2.portfolio_cagr,
            "v3_cagr": s3.portfolio_cagr,
            "ew_cagr": cagr(INITIAL_CAPITAL, ew_final, days),
            "v1_buys": s1.n_buys, "v2_buys": s2.n_buys, "v3_buys": s3.n_buys,
            "v1_sells": s1.n_sells, "v2_sells": s2.n_sells, "v3_sells": s3.n_sells,
            "days": days,
        })
        print(f"{label:<40} ${s1.final_portfolio_value:>10,.0f} "
              f"${s2.final_portfolio_value:>10,.0f} "
              f"${s3.final_portfolio_value:>10,.0f} ${ew_final:>10,.0f} "
              f"{s1.max_drawdown_pct*100:>5.1f}% "
              f"{s2.max_drawdown_pct*100:>5.1f}% "
              f"{s3.max_drawdown_pct*100:>5.1f}% {ew_dd*100:>5.1f}%")

    print("="*112)

    # Detail per scenario
    print("\nDetail (CAGR):")
    print(f"{'SCENARIO':<40} {'v1':>8} {'v2':>8} {'v3':>8} {'EW':>8}")
    for r in rows:
        print(f"{r['label']:<40} {r['v1_cagr']*100:>+7.1f}% "
              f"{r['v2_cagr']*100:>+7.1f}% {r['v3_cagr']*100:>+7.1f}% "
              f"{r['ew_cagr']*100:>+7.1f}%")

    # Pre-declared decision rule
    print("\n" + "="*88)
    print("DECISION RULE (committed before seeing results):")
    print("  v2 must close ≥ half the gap between v1 and equal-weight in 3 of 4")
    print("  scenarios. (gap_v1 = ew_final − v1_final; gap_v2 = ew_final − v2_final.")
    print("   v2 closes the gap if gap_v2 < 0.5 * gap_v1, i.e. v2 is at least")
    print("   halfway from v1 toward equal-weight.)")
    print("  If gap_v1 is negative — v1 already beats EW — v2 just needs to maintain.")
    print("="*88)

    print("Per scenario, gap closure (gap_vN / gap_v1 inverted = % of v1's gap to EW that vN closes):")
    print(f"{'SCENARIO':<40}  {'v2 closes':>11}  {'v3 closes':>11}")
    v2_closes = 0
    v3_closes = 0
    for r in rows:
        gap_v1 = r["ew_final"] - r["v1_final"]
        gap_v2 = r["ew_final"] - r["v2_final"]
        gap_v3 = r["ew_final"] - r["v3_final"]
        if gap_v1 <= 0:
            v2_close_pct = 0 if r["v2_final"] >= r["ew_final"] else -999
            v3_close_pct = 0 if r["v3_final"] >= r["ew_final"] else -999
            v2_closed = r["v2_final"] >= r["ew_final"]
            v3_closed = r["v3_final"] >= r["ew_final"]
        else:
            v2_close_pct = (1 - gap_v2 / gap_v1) * 100
            v3_close_pct = (1 - gap_v3 / gap_v1) * 100
            v2_closed = v2_close_pct >= 50
            v3_closed = v3_close_pct >= 50
        if v2_closed: v2_closes += 1
        if v3_closed: v3_closes += 1
        m2 = "✓" if v2_closed else "✗"
        m3 = "✓" if v3_closed else "✗"
        print(f"  {r['label']:<40}  [{m2}] {v2_close_pct:>+5.0f}%   [{m3}] {v3_close_pct:>+5.0f}%")

    print(f"\nv2 closes the gap in {v2_closes}/4 scenarios.")
    print(f"v3 closes the gap in {v3_closes}/4 scenarios.")
    best = max(v2_closes, v3_closes)
    if best >= 3:
        winner = "v3" if v3_closes >= v2_closes else "v2"
        print(f"→ VERDICT: PROCEED with Phase 2 ({winner}). Sizing fixes show real impact.")
    else:
        print("→ VERDICT: PAUSE Phase 2. Neither sizing variant closes the gap.")
        print("  Architecture-level questions (analyst ceiling, firewall) likely dominate.")
    print("="*112)


if __name__ == "__main__":
    main()
