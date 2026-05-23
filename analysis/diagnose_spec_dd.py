#!/usr/bin/env python3
"""
diagnose_spec_dd.py — Isolate why v3 speculative-only max DD dropped from
60.9% to 37.1% between the pre-Type-A/B and post-Type-A/B runs.

Three sub-experiments:
  A. v3 with type_for_ticker=None (mimics the OLD pre-wiring run)
  B. v3 with type_for_ticker=type_fn (mimics the NEW run)
  C. v3 with type_for_ticker=None AND end_date=2026-04-30 (mimics OLD window)

If A and C produce 60.9% DD → my wiring + window extension fully explain it
If A produces something different from 60.9% → something else changed
  (eval cache, trend verdicts, tier classifications) between runs

Also dumps daily portfolio values to CSV so we can see WHEN the DD happened
in each scenario, then visually compare.

Usage:
    cd analysis && python3 diagnose_spec_dd.py
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup
from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function
from type_classifier import build_type_function

SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]


def run_and_summarize(label, start, end, prices, all_events, decide_fn,
                       tier_fn, type_fn, initial):
    print(f"\n--- {label} ---")
    r = run_simulation(
        start_date=start, end_date=end,
        taxable_cash=initial/2, tax_advantaged_cash=initial/2,
        universe_tickers=SPECULATIVE, prices=prices, events=all_events,
        decide_fn=decide_fn, tier_for_ticker=tier_fn,
        type_for_ticker=type_fn,
    )
    s = compute_summary(r)
    print(f"  Window:    {start} → {end}")
    print(f"  type_fn:   {'YES' if type_fn else 'NO (passes None)'}")
    print(f"  Final $:   ${s.final_portfolio_value:,.0f}")
    print(f"  CAGR:      {s.portfolio_cagr*100:+.2f}%")
    print(f"  Max DD:    {s.max_drawdown_pct*100:.2f}%")
    print(f"  # buys:    {s.n_buys}")
    print(f"  # sells:   {s.n_sells}")

    # Compute peak/trough dates from daily snapshots
    daily = r.daily_snapshots
    if daily:
        peak = daily[0].total_value
        peak_date = daily[0].date
        max_dd = 0.0
        trough_date = daily[0].date
        trough_val = peak
        running_peak = peak
        running_peak_date = peak_date
        for snap in daily:
            v = snap.total_value
            if v > running_peak:
                running_peak = v
                running_peak_date = snap.date
            if running_peak > 0:
                dd = (running_peak - v) / running_peak
                if dd > max_dd:
                    max_dd = dd
                    peak = running_peak
                    peak_date = running_peak_date
                    trough_val = v
                    trough_date = snap.date
        print(f"  DD detail: peak ${peak:,.0f} on {peak_date}, "
              f"trough ${trough_val:,.0f} on {trough_date}")

    return r, s


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
    print("Computing trend verdicts…")
    attach_trend_verdicts(all_events, tier_for_ticker=tier_fn)

    type_fn = build_type_function()

    INITIAL = 100_000
    start = date(2022, 1, 1)
    end_old = date(2026, 4, 30)
    end_new = date(2026, 5, 6)

    # Print tier classifications for spec cohort (should all be "speculative")
    print("\nSpec cohort tier classifications:")
    for t in SPECULATIVE:
        tier = tier_fn(t)
        ttype = type_fn(t)
        print(f"  {t:<8} tier={tier:<14} type={ttype}")

    # Experiment A: OLD wiring (no type_fn), OLD end date
    rA, sA = run_and_summarize(
        "A: OLD wiring (type_fn=None), OLD end date (2026-04-30)",
        start, end_old, prices, all_events, decide_v3,
        tier_fn, None, INITIAL,
    )

    # Experiment B: NEW wiring (type_fn), NEW end date
    rB, sB = run_and_summarize(
        "B: NEW wiring (type_fn=set), NEW end date (2026-05-06)",
        start, end_new, prices, all_events, decide_v3,
        tier_fn, type_fn, INITIAL,
    )

    # Experiment C: OLD wiring, NEW end date (isolate end-date effect)
    rC, sC = run_and_summarize(
        "C: OLD wiring (type_fn=None), NEW end date (2026-05-06)",
        start, end_new, prices, all_events, decide_v3,
        tier_fn, None, INITIAL,
    )

    # Experiment D: NEW wiring, OLD end date (isolate type_fn effect)
    rD, sD = run_and_summarize(
        "D: NEW wiring (type_fn=set), OLD end date (2026-04-30)",
        start, end_old, prices, all_events, decide_v3,
        tier_fn, type_fn, INITIAL,
    )

    print("\n" + "="*72)
    print("SUMMARY:")
    print(f"  Expected from PREVIOUS run: $99,817 final, 60.9% DD")
    print(f"  Expected from CURRENT run:  $119,963 final, 37.1% DD")
    print()
    print(f"  A (old wiring, old end):  ${sA.final_portfolio_value:>8,.0f}  DD={sA.max_drawdown_pct*100:.1f}%")
    print(f"  B (new wiring, new end):  ${sB.final_portfolio_value:>8,.0f}  DD={sB.max_drawdown_pct*100:.1f}%")
    print(f"  C (old wiring, new end):  ${sC.final_portfolio_value:>8,.0f}  DD={sC.max_drawdown_pct*100:.1f}%")
    print(f"  D (new wiring, old end):  ${sD.final_portfolio_value:>8,.0f}  DD={sD.max_drawdown_pct*100:.1f}%")
    print()
    print("Interpretation guide:")
    print("  - If A ≈ previous (60.9%) → eval cache/trend verdicts unchanged")
    print("  - If A ≠ previous → something in cache or trend layer changed since prior run")
    print("  - If C ≈ B → end date extension is the cause")
    print("  - If D ≈ A → type wiring has no effect on specs (as expected)")
    print("="*72)

    # Dump daily values for B (current best estimate of current behavior)
    # so we can plot/inspect WHEN the drawdown happened
    csv_path = SCRIPT_DIR / "data" / "diagnose_spec_dd_daily.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "A_value", "B_value", "C_value", "D_value"])
        # Align dates across all four runs
        dates = set()
        for r in [rA, rB, rC, rD]:
            for s_snap in r.daily_snapshots:
                dates.add(s_snap.date)
        dates = sorted(dates)
        # Index each run's snapshots by date
        idx = {label: {s.date: s.total_value for s in r.daily_snapshots}
               for label, r in [("A", rA), ("B", rB), ("C", rC), ("D", rD)]}
        for d in dates:
            w.writerow([d.isoformat()] + [idx[k].get(d, "") for k in "ABCD"])
    print(f"\nDaily values saved to: {csv_path}")
    print("Open in a spreadsheet to see WHEN the drawdown happened in each variant.")


if __name__ == "__main__":
    main()
