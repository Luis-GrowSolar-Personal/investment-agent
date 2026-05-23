#!/usr/bin/env python3
"""
v3_quarterly_concentration.py — Run v3 on the full window, then snapshot
position values at each quarter end. Shows how much capital is tied up in
each ticker over time and reveals which positions drove v3's outperformance.

Output: CSV + console table. Each row is a ticker (+ CASH); each column is
a quarter end. Cells are % of total portfolio value at that date.

Usage:
    cd analysis && python3 v3_quarterly_concentration.py
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from trend_analyst import build_tier_function

ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL16 = ESTABLISHED + SPECULATIVE


def quarter_ends(start: date, end: date) -> list[date]:
    """All quarter-end dates strictly within [start, end]."""
    out = []
    for yr in range(start.year, end.year + 2):
        for m, d in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            qe = date(yr, m, d)
            if start <= qe <= end:
                out.append(qe)
    return sorted(out)


def reconstruct_holdings(transaction_log, snapshot_date) -> dict[str, float]:
    """Replay the transaction log to determine net shares held per ticker
    on snapshot_date (inclusive of trades made on that date)."""
    holdings: dict[str, float] = defaultdict(float)
    for trade in transaction_log:
        if trade.trade_date > snapshot_date:
            break
        if trade.side == "buy":
            holdings[trade.ticker] += trade.shares
        else:
            holdings[trade.ticker] -= trade.shares
    # Drop any near-zero positions (numerical noise)
    return {t: s for t, s in holdings.items() if s > 1e-6}


def cash_at(transaction_log, initial_cash, snapshot_date) -> float:
    """Track cash balance up to snapshot_date by replaying trades."""
    cash = initial_cash
    for trade in transaction_log:
        if trade.trade_date > snapshot_date:
            break
        flow = trade.shares * trade.price
        cash += flow if trade.side == "sell" else -flow
    return cash


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

    start = date(2022, 1, 1)
    end = date(2026, 4, 30)
    INITIAL = 100_000

    print(f"\nRunning v3 on {start} → {end}…")
    res = run_simulation(
        start_date=start, end_date=end,
        taxable_cash=INITIAL/2, tax_advantaged_cash=INITIAL/2,
        universe_tickers=ALL16, prices=prices, events=all_events,
        decide_fn=decide_v3, tier_for_ticker=tier_fn,
    )

    qends = [start] + quarter_ends(start, end) + [end]
    print(f"Snapshots: {len(qends)} dates from {qends[0]} to {qends[-1]}")

    # For each quarter-end, get holdings + cash + prices
    rows = []  # list of (date, total_value, per_ticker_value_pct dict, cash_pct)
    for qe in qends:
        holdings = reconstruct_holdings(res.portfolio.transaction_log, qe)
        cash = cash_at(res.portfolio.transaction_log, INITIAL, qe)
        # Note: doesn't include year-end tax adjustments, slight drift OK
        position_values = {}
        total_pos = 0.0
        for t, sh in holdings.items():
            p = prices.price_on(t, qe, max_lookback_days=10)
            if p is None or p <= 0:
                continue
            v = sh * p
            position_values[t] = v
            total_pos += v
        total = cash + total_pos
        rows.append((qe, total, position_values, cash))

    # ---- Print wide table ----
    all_tickers_seen = sorted({t for _, _, pv, _ in rows for t in pv})
    headers = ["TICKER"] + [r[0].strftime("%y-%m") for r in rows]

    print(f"\nv3 Quarterly Concentration (% of total portfolio)\n")
    print(f"{'TICKER':<8}" + "".join(f"{h:>7}" for h in headers[1:]))
    print("-" * (8 + 7 * len(rows)))

    # Total portfolio value row
    print(f"{'TOTAL$k':<8}" + "".join(f"{int(r[1]/1000):>6}k" for r in rows))

    # Cash row
    cash_pcts = [(100 * r[3] / r[1]) if r[1] > 0 else 0 for r in rows]
    print(f"{'CASH%':<8}" + "".join(f"{p:>6.0f}%" for p in cash_pcts))
    print()

    # Per-ticker rows
    for t in all_tickers_seen:
        cells = []
        for _, total, pv, _ in rows:
            v = pv.get(t, 0)
            pct = 100 * v / total if total > 0 else 0
            cells.append(pct)
        if max(cells) < 0.5:  # never reached 0.5% — skip
            continue
        cell_strs = [f"{c:>6.1f}%" if c >= 0.05 else f"{'·':>7}" for c in cells]
        print(f"{t:<8}" + "".join(cell_strs))

    # ---- AMPX-specific drilldown ----
    print(f"\nAMPX drilldown (the +1686% rocket):")
    print(f"{'DATE':<12} {'SHARES':>10} {'PRICE':>8} {'VALUE':>10} {'%PORT':>7}")
    print("-" * 50)
    for qe, total, pv, _ in rows:
        holdings = reconstruct_holdings(res.portfolio.transaction_log, qe)
        ampx_sh = holdings.get("AMPX", 0)
        if ampx_sh < 1e-6:
            continue
        p = prices.price_on("AMPX", qe, max_lookback_days=10) or 0
        v = ampx_sh * p
        pct = 100 * v / total if total > 0 else 0
        print(f"{qe}   {ampx_sh:>10.0f} {p:>7.2f}  ${v:>8,.0f}  {pct:>6.1f}%")

    # ---- Top-3 concentration over time ----
    print(f"\nTop-3 ticker concentration (% of portfolio in 3 biggest names):")
    print(f"{'DATE':<12} {'TOP3 %':>7}  {'NAMES'}")
    print("-" * 60)
    for qe, total, pv, _ in rows:
        if total <= 0 or not pv:
            continue
        ranked = sorted(pv.items(), key=lambda kv: -kv[1])
        top3 = ranked[:3]
        top3_pct = 100 * sum(v for _, v in top3) / total
        names = ", ".join(f"{t}({100*v/total:.0f}%)" for t, v in top3)
        print(f"{qe}   {top3_pct:>6.1f}%   {names}")

    # ---- Save CSV ----
    csv_path = SCRIPT_DIR / "data" / "v3_quarterly_concentration.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker"] + [r[0].isoformat() for r in rows])
        w.writerow(["TOTAL_VALUE"] + [f"{r[1]:.0f}" for r in rows])
        w.writerow(["CASH_PCT"] + [f"{100*r[3]/r[1] if r[1]>0 else 0:.2f}" for r in rows])
        for t in all_tickers_seen:
            row_vals = []
            for _, total, pv, _ in rows:
                v = pv.get(t, 0)
                row_vals.append(f"{100*v/total if total>0 else 0:.2f}")
            w.writerow([t] + row_vals)
    print(f"\nWrote {csv_path}")


if __name__ == "__main__":
    main()
