#!/usr/bin/env python3
"""
run_simulator.py — Run a backtest scenario end-to-end.

Loads call events from Railway DB and prices from analysis/data/price_cache.json,
runs the simulator, writes daily.csv + transactions.csv + summary.txt to an
output directory, and prints the summary.

Usage:
    cd analysis && python3 run_simulator.py \\
        --start 2024-08-01 --end 2026-04-26 \\
        --taxable 50000 --tax-advantaged 50000

    # Restrict universe to specific tickers:
    python3 run_simulator.py --start 2024-08-01 --end 2026-04-26 \\
        --taxable 50000 --tax-advantaged 50000 \\
        --tickers AAPL MSFT NVDA

    # Custom output dir (default: data/simulator_runs/<timestamp>):
    python3 run_simulator.py ... --output data/simulator_runs/my_scenario

Pre-reqs:
    - DATABASE_URL in ../.env  (psycopg2 connects to Railway)
    - SPY/QQQ/TMFC prices in price_cache.json (run fetch_prices_for_tickers.py)
    - Trend layer verdicts populated (run sync_trend_to_db.py)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

# When run as a script, allow the package import
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.report import write_all_artifacts
from analysis.simulator.simulator import run_simulation


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start", type=parse_date, required=True,
                    help="Backtest start date (YYYY-MM-DD)")
    ap.add_argument("--end", type=parse_date, required=True,
                    help="Backtest end date (YYYY-MM-DD)")
    ap.add_argument("--taxable", type=float, required=True,
                    help="Initial cash in taxable account ($)")
    ap.add_argument("--tax-advantaged", type=float, required=True,
                    help="Initial cash in tax-advantaged account ($)")
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="Optional: restrict universe to these symbols. "
                         "Default: every ticker in DB with events in the window.")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output directory (default: data/simulator_runs/<timestamp>)")
    ap.add_argument("--verbose", action="store_true",
                    help="Print yearly progress + tax events")
    args = ap.parse_args()

    if args.start >= args.end:
        ap.error("--start must be before --end")
    if args.taxable < 0 or args.tax_advantaged < 0:
        ap.error("cash amounts must be non-negative")
    if args.taxable + args.tax_advantaged <= 0:
        ap.error("must start with non-zero capital")

    output_dir = args.output
    if output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = SCRIPT_DIR / "data" / "simulator_runs" / ts

    print(f"\nBacktest configuration")
    print(f"  Window:           {args.start} → {args.end}")
    print(f"  Taxable:          ${args.taxable:,.0f}")
    print(f"  Tax-advantaged:   ${args.tax_advantaged:,.0f}")
    print(f"  Total:            ${args.taxable + args.tax_advantaged:,.0f}")
    print(f"  Universe:         {args.tickers or 'all in DB'}")
    print(f"  Output:           {output_dir}")
    print()

    print("Running simulation…")
    result = run_simulation(
        start_date=args.start,
        end_date=args.end,
        taxable_cash=args.taxable,
        tax_advantaged_cash=args.tax_advantaged,
        universe_tickers=args.tickers,
        verbose=args.verbose,
    )
    print(f"  Processed {len(result.daily_snapshots)} day(s)")
    print(f"  Universe ended up:  {result.universe_tickers}")
    print(f"  Trades:             {len(result.portfolio.transaction_log)}")
    print(f"  Skipped events:     {len(result.skipped_events)}")
    print()

    print(f"Writing artifacts to {output_dir}…")
    summary = write_all_artifacts(result, output_dir)
    print()

    # Print the summary file content
    summary_path = output_dir / "summary.txt"
    print(summary_path.read_text())

    return 0


if __name__ == "__main__":
    sys.exit(main())
