#!/usr/bin/env python3
"""
audit_top20_2021.py — Comprehensive audit of the top-20 (2021) universe.

Three checks:
  1. Coverage     — every expected ticker present with at least one transcript
  2. Duplicates   — any (ticker, callDate) appearing more than once
  3. Missing      — gaps > N days between consecutive transcripts (likely
                    skipped quarters worth re-loading)

Plus expected-count check: each ticker should have ~21 calls (Q1 2021 →
Q1 2026 = 17 quarters with quarterly cadence). Anyone substantially below
that gets flagged.

Usage:
    cd analysis && python3 audit_top20_2021.py
    cd analysis && python3 audit_top20_2021.py --gap-days 120
    cd analysis && python3 audit_top20_2021.py --target-start 2021-01-01
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(ENV_PATH)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit(f"ERROR: DATABASE_URL not in {ENV_PATH}")

EXPECTED = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "ADBE",
    "V", "JNJ", "WMT", "JPM", "PG", "UNH", "DIS", "NVDA",
    "MA", "HD", "PYPL", "BAC", "NFLX",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-start", default="2021-01-01",
                    help="Earliest expected call date (default 2021-01-01).")
    ap.add_argument("--gap-days", type=int, default=120,
                    help="Flag a gap if consecutive calls are this many days apart "
                         "or more (default 120 — filters out annual Q4→Q1 noise).")
    args = ap.parse_args()

    target = date.fromisoformat(args.target_start)
    today = date.today()
    expected_calls = ((today - target).days // 91) + 1

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Pull all transcripts for the 20 expected tickers
            cur.execute("""
                SELECT tk.symbol, tk.status, t."callDate"::date AS call_date, t.id AS transcript_id
                FROM "Ticker" tk
                LEFT JOIN "Transcript" t ON t."tickerId" = tk.id
                WHERE tk.symbol = ANY(%s)
                ORDER BY tk.symbol, t."callDate"
            """, (EXPECTED,))
            rows = cur.fetchall()
    finally:
        conn.close()

    by_ticker: dict[str, dict] = {}
    for r in rows:
        sym = r["symbol"]
        if sym not in by_ticker:
            by_ticker[sym] = {"status": r["status"], "calls": []}
        if r["call_date"] is not None:
            by_ticker[sym]["calls"].append((r["call_date"], r["transcript_id"]))

    missing_tickers = [s for s in EXPECTED if s not in by_ticker]
    ticker_summary = []   # rows for the main table
    duplicates = []       # (ticker, date, count, ids)
    gaps = []             # (ticker, from_date, to_date, days)
    under_loaded = []     # (ticker, count, expected)
    early_issues = []     # ticker whose earliest > target + grace

    grace_days = 120

    for sym in EXPECTED:
        if sym not in by_ticker:
            continue
        info = by_ticker[sym]
        calls = sorted(info["calls"])
        dates = [c[0] for c in calls]

        # Duplicate detection
        seen: dict[date, list[int]] = defaultdict(list)
        for d, tid in calls:
            seen[d].append(tid)
        for d, ids in seen.items():
            if len(ids) > 1:
                duplicates.append((sym, d, len(ids), ids))

        # Gap detection (on unique dates)
        unique_dates = sorted(set(dates))
        for i in range(1, len(unique_dates)):
            delta = (unique_dates[i] - unique_dates[i - 1]).days
            if delta >= args.gap_days:
                gaps.append((sym, unique_dates[i - 1], unique_dates[i], delta))

        # Earliness check
        if unique_dates and unique_dates[0] > target + timedelta(days=grace_days):
            early_issues.append((sym, unique_dates[0]))

        # Under-loaded
        n_unique = len(unique_dates)
        if n_unique < expected_calls - 4:  # tolerate a few missing
            under_loaded.append((sym, n_unique, expected_calls))

        ticker_summary.append({
            "symbol": sym,
            "status": info["status"],
            "n_all": len(calls),
            "n_unique": n_unique,
            "earliest": unique_dates[0] if unique_dates else None,
            "latest": unique_dates[-1] if unique_dates else None,
        })

    # --- Output ----------------------------------------------------------

    print(f"\nAudit — top-20 2021 universe — target start {target}, today {today}")
    print(f"Expected ~{expected_calls} calls per ticker since target.")
    print(f"Gap threshold: {args.gap_days} days.\n")

    print(f"{'TICKER':<8} {'STATUS':<11} {'N':>4} {'UNIQ':>5}  {'EARLIEST':12}  {'LATEST':12}")
    print("-" * 60)
    for r in ticker_summary:
        n = r["n_all"]; u = r["n_unique"]
        dup_flag = " ⚠ dups" if n != u else ""
        early_flag = ""
        if r["earliest"] is None:
            early_flag = "  ⚠ no transcripts"
        elif r["earliest"] > target + timedelta(days=grace_days):
            early_flag = f"  ⚠ late start"
        print(f"{r['symbol']:<8} {r['status'] or '—':<11} {n:>4} {u:>5}  "
              f"{r['earliest']!s:12}  {r['latest']!s:12}{dup_flag}{early_flag}")

    print()
    if missing_tickers:
        print(f"⚠ MISSING tickers (not in DB at all, {len(missing_tickers)}):")
        for t in missing_tickers:
            print(f"  {t}")
        print()

    # Duplicates
    print(f"--- Duplicate check ---")
    if not duplicates:
        print("✓ No duplicate (ticker, call_date) rows.\n")
    else:
        print(f"⚠ {len(duplicates)} duplicate (ticker, call_date) combination(s):")
        for sym, d, n, ids in duplicates:
            print(f"  {sym} {d}: {n} transcripts (ids: {ids})")
        print()
        print("  Note: Schema has no unique constraint on (tickerId, callDate), so")
        print("  duplicates can exist. To delete: connect via Prisma Studio or")
        print("  psql, identify which row to keep (usually the one with analysis"
              " rows attached), and delete the others. Keep the one with the most"
              " recent createdAt if both are bare.")
        print()

    # Gaps
    print(f"--- Gap check (≥{args.gap_days} days between consecutive calls) ---")
    if not gaps:
        print(f"✓ No gaps ≥ {args.gap_days} days.\n")
    else:
        # Group by ticker for readability
        gaps_by_ticker: dict[str, list] = defaultdict(list)
        for sym, a, b, n in gaps:
            gaps_by_ticker[sym].append((a, b, n))
        print(f"⚠ {len(gaps)} gap(s) across {len(gaps_by_ticker)} ticker(s):")
        for sym in sorted(gaps_by_ticker):
            for a, b, n in gaps_by_ticker[sym]:
                print(f"  {sym}: {a} → {b} ({n}d)")
        print()
        print("  Note: gaps may indicate skipped quarters. Annual Q4→Q1 reporting")
        print("  cadence naturally produces 100-120d gaps; use --gap-days 100 to")
        print("  see those too. Real misses are typically >130d.")
        print()

    # Under-loaded
    print(f"--- Coverage check (expected ~{expected_calls} calls) ---")
    if not under_loaded and not missing_tickers:
        print(f"✓ All {len(EXPECTED)} tickers have substantial coverage.\n")
    else:
        if under_loaded:
            print(f"⚠ {len(under_loaded)} ticker(s) significantly under-loaded:")
            for sym, n, expected in under_loaded:
                print(f"  {sym}: {n} transcripts (expected ~{expected})")
            print()

    # Late-start tickers
    if early_issues:
        print(f"--- Late-start tickers ---")
        print(f"{len(early_issues)} ticker(s) start after {target + timedelta(days=grace_days)}:")
        for sym, earliest in early_issues:
            print(f"  {sym}: earliest is {earliest}")
        print("  May reflect IPO date (e.g., post-2021 listing) or just missing"
              " early loads.")
        print()

    # Totals
    total_unique = sum(r["n_unique"] for r in ticker_summary)
    print(f"Total unique transcripts across universe: {total_unique}")
    print(f"Average per ticker:                       "
          f"{total_unique / max(1, len(ticker_summary)):.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
