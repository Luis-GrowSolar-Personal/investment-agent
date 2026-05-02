#!/usr/bin/env python3
"""
extract_db_baseline.py — Export stored Analysis records from the DB as a
baseline CSV in the same column format as backtest_runner.py output.

Use this to compare v1 (app-evaluated, stored in DB) against v2 (backtest
runner with updated prompt) without re-running the old prompt.

Usage:
    python3 analysis/extract_db_baseline.py --tickers TTD ENPH
    python3 analysis/extract_db_baseline.py --tickers TTD ENPH --out analysis/data/baseline_db.csv

Output:
    CSV with same columns as backtest_runner output.
    Price and return columns will be populated via yfinance.
    Columns not available from DB (e.g. fresh_money_allocation) will be null
    if not stored in the Analysis table.

Requirements:
    python3 -m pip install psycopg2-binary python-dotenv pandas yfinance
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────

script_dir = Path(__file__).parent.resolve()
env_path = script_dir.parent / ".env"
if not env_path.exists():
    env_path = script_dir / ".env"
load_dotenv(env_path)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("❌  DATABASE_URL not found. Check your .env path.")
    sys.exit(1)

import psycopg2
import psycopg2.extras
import pandas as pd
import yfinance as yf

FORWARD_DAYS = 90
OUTPUT_DIR = script_dir / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── DB extraction ──────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(DATABASE_URL)


def fetch_analyses_for_tickers(conn, symbols):
    """
    Pull all Analysis records for the given ticker symbols,
    joined to Transcript and Ticker.
    Returns list of dicts.
    """
    placeholders = ','.join(['%s'] * len(symbols))
    upper_symbols = [s.upper() for s in symbols]

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"""
            SELECT
                tk.symbol,
                tk.name,
                t."callDate",
                t.title,
                a."thesisHealth",
                a."thesisDelta",
                a."recommendation",
                a."recommendedSize",
                a."freshMoneyAllocation",
                a."stumbleType",
                a."threatMechanismImpaired",
                a."credibilityDelta",
                a."ratchetTranche",
                a."capPercent",
                a."mitigationArgumentPresent",
                a."mitigationCapabilityTrackRecord",
                a."blindSpotsTriggered",
                a."activeDriverCount"
            FROM "Analysis" a
            JOIN "Transcript" t ON a."transcriptId" = t.id
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE tk.symbol IN ({placeholders})
            ORDER BY tk.symbol ASC, t."callDate" ASC
        """, upper_symbols)
        return cur.fetchall()


# ── Price data (same helpers as backtest_runner) ───────────────────────────

def next_trading_day(date, prices_index):
    if hasattr(date, 'date'):
        date = date.date()
    target = pd.Timestamp(date)
    candidates = prices_index[prices_index >= target]
    return candidates[0] if len(candidates) > 0 else None


def fetch_prices(ticker, start_date, end_date):
    start = (pd.Timestamp(start_date) - pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    end = (pd.Timestamp(end_date) + pd.Timedelta(days=10)).strftime('%Y-%m-%d')
    data = yf.download(
        [ticker, 'SPY'],
        start=start,
        end=end,
        auto_adjust=True,
        progress=False
    )['Close']
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1) if data.columns.nlevels > 1 else data.columns
    return data


def get_price_on_date(prices_df, ticker, target_date):
    col = ticker if ticker in prices_df.columns else None
    if col is None:
        return None
    trading_day = next_trading_day(target_date, prices_df.index)
    if trading_day is None:
        return None
    try:
        return float(prices_df.loc[trading_day, col])
    except (KeyError, TypeError):
        return None


# ── Signal correctness (same logic as backtest_runner) ────────────────────

def compute_signal_correct(recommendation, relative_return):
    if relative_return is None or not recommendation:
        return None
    if recommendation == 'Add':
        return relative_return > 0
    elif recommendation == 'Hold':
        return abs(relative_return) <= 5
    elif recommendation in ('Trim', 'Exit'):
        return relative_return < 0
    return None


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Export DB analyses as baseline CSV for backtest diffing."
    )
    parser.add_argument(
        '--tickers', nargs='+', required=True,
        help='Ticker symbols to export (e.g. TTD ENPH)'
    )
    parser.add_argument(
        '--out', default=None,
        help='Output CSV path (default: analysis/data/baseline_db_<tickers>_<date>.csv)'
    )
    args = parser.parse_args()

    symbols = [s.upper() for s in args.tickers]
    print(f"\nExtracting DB analyses for: {', '.join(symbols)}\n")

    conn = get_connection()
    rows = fetch_analyses_for_tickers(conn, symbols)
    conn.close()

    if not rows:
        print("❌  No analyses found for the specified tickers.")
        sys.exit(1)

    print(f"  Found {len(rows)} analysis record(s)")

    # Group by ticker for price fetching
    by_ticker = {}
    for row in rows:
        sym = row['symbol']
        by_ticker.setdefault(sym, []).append(row)

    all_output_rows = []

    for sym, ticker_rows in by_ticker.items():
        print(f"\n  {sym} — {ticker_rows[0]['name']} ({len(ticker_rows)} records)")

        earliest = ticker_rows[0]['callDate']
        latest = ticker_rows[-1]['callDate']
        forward_end = pd.Timestamp(latest) + pd.Timedelta(days=FORWARD_DAYS + 15)

        print(f"    Fetching prices {earliest.date()} → {forward_end.date()}...", end=" ", flush=True)
        try:
            prices = fetch_prices(sym, earliest, forward_end)
            print("done")
        except Exception as e:
            print(f"❌  Price fetch failed: {e}")
            continue

        for row in ticker_rows:
            call_date = row['callDate']

            price_at_call = get_price_on_date(prices, sym, call_date)
            spy_at_call = get_price_on_date(prices, 'SPY', call_date)

            forward_date = pd.Timestamp(call_date) + pd.Timedelta(days=FORWARD_DAYS)
            price_forward = get_price_on_date(prices, sym, forward_date)
            spy_forward = get_price_on_date(prices, 'SPY', forward_date)

            ticker_return = None
            spy_return = None
            relative_return = None

            if price_at_call and price_forward:
                ticker_return = round((price_forward - price_at_call) / price_at_call * 100, 2)
            if spy_at_call and spy_forward:
                spy_return = round((spy_forward - spy_at_call) / spy_at_call * 100, 2)
            if ticker_return is not None and spy_return is not None:
                relative_return = round(ticker_return - spy_return, 2)

            signal_correct = compute_signal_correct(
                row['recommendation'], relative_return
            )

            # Normalize blindSpotsTriggered — may be stored as list or JSON string
            blind_spots = row.get('blindSpotsTriggered') or []
            if isinstance(blind_spots, str):
                try:
                    blind_spots = json.loads(blind_spots)
                except Exception:
                    blind_spots = []

            all_output_rows.append({
                'ticker': sym,
                'call_date': call_date.date(),
                'transcript_title': row['title'],
                'recommendation': row['recommendation'],
                'thesis_health': row['thesisHealth'],
                'thesis_delta': row['thesisDelta'],
                'type_classification': None,
                'stumble_type': row['stumbleType'],
                'threat_mechanism_impaired': row['threatMechanismImpaired'],
                'credibility_delta': row['credibilityDelta'],
                'ratchet_tranche': row['ratchetTranche'],
                'fresh_money_allocation': row['freshMoneyAllocation'],
                'recommended_size': row['recommendedSize'],
                'cap_percent': row['capPercent'],
                'mitigation_argument_present': row['mitigationArgumentPresent'],
                'mitigation_track_record': row['mitigationCapabilityTrackRecord'],
                'blind_spots_triggered': json.dumps(blind_spots),
                'active_driver_count': row['activeDriverCount'],
                'price_at_call': price_at_call,
                'spy_at_call': spy_at_call,
                'price_forward_90d': price_forward,
                'spy_forward_90d': spy_forward,
                'forward_date': forward_date.date(),
                'ticker_return_pct': ticker_return,
                'spy_return_pct': spy_return,
                'relative_return_pct': relative_return,
                'signal_correct': signal_correct,
            })

    if not all_output_rows:
        print("\n❌  No rows produced.")
        sys.exit(1)

    df = pd.DataFrame(all_output_rows)
    df = df.sort_values(['ticker', 'call_date'])

    if args.out:
        output_path = Path(args.out)
    else:
        today = datetime.date.today().isoformat()
        ticker_str = '_'.join(symbols)
        output_path = OUTPUT_DIR / f"baseline_db_{ticker_str}_{today}.csv"

    df.to_csv(output_path, index=False)
    print(f"\n✅  Wrote {len(df)} rows → {output_path}")

    # Quick accuracy summary
    scored = df[df['signal_correct'].notna()].copy()
    scored['signal_correct'] = scored['signal_correct'].astype(float)
    if not scored.empty:
        print("\nSignal accuracy (DB baseline):")
        summary = scored.groupby('ticker')['signal_correct'].agg(correct='sum', total='count')
        summary['accuracy_pct'] = (summary['correct'] / summary['total'] * 100).round(1)
        print(summary.to_string())
        overall = scored['signal_correct'].sum()
        print(f"\nOverall: {overall:.0f}/{len(scored)} = {overall/len(scored)*100:.1f}%")

    print(f"\nNext step:")
    print(f"  python3 analysis/backtest_diff.py --baseline {output_path} \\")
    print(f"      --new analysis/data/backtest_<date>_TTD.csv  (or merged)")


if __name__ == '__main__':
    main()
