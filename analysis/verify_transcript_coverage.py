#!/usr/bin/env python3
"""
verify_transcript_coverage.py — Audit whether all expected quarterly
earnings calls are in the Railway DB.

For each ticker:
  1. Lists every callDate in the DB
  2. Detects gaps > 120 days between consecutive calls (likely missed quarter)
  3. Compares earliest call to a target (default 2021-Q1) and reports if early calls are missing

Run on your laptop:
    cd analysis && python3 verify_transcript_coverage.py
    cd analysis && python3 verify_transcript_coverage.py --target-start 2021-01-01
"""
from __future__ import annotations

import argparse
import os
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-start", default="2021-01-01",
                    help="Earliest expected call date (default 2021-01-01).")
    ap.add_argument("--gap-days", type=int, default=120,
                    help="Flag a gap if consecutive calls are this many days "
                         "apart or more (default 120).")
    args = ap.parse_args()

    target = date.fromisoformat(args.target_start)
    today = date.today()

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT tk.symbol, t."callDate"::date AS call_date
                FROM "Transcript" t
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                ORDER BY tk.symbol, t."callDate"
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    by_ticker: dict[str, list[date]] = {}
    for r in rows:
        by_ticker.setdefault(r["symbol"], []).append(r["call_date"])

    print(f"\nTranscript coverage audit — target start: {target}, today: {today}")
    print(f"Expected: ~{((today - target).days // 91) + 1} calls per ticker since target.")
    print(f"Gap threshold: {args.gap_days} days between consecutive calls.\n")

    print(f"{'TICKER':<8} {'COUNT':>5}  {'FIRST':12}  {'LAST':12}  {'STATUS'}")
    print("-" * 80)

    issues = []
    for ticker in sorted(by_ticker.keys()):
        dates = sorted(by_ticker[ticker])
        first, last = dates[0], dates[-1]

        # Check earliest
        early_issue = None
        if first > target + timedelta(days=120):
            # Could be the ticker simply didn't exist before its first call.
            # We don't know IPO dates here, so flag as informational.
            early_issue = f"earliest is {first} (target {target})"

        # Check gaps
        gap_issues = []
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i-1]).days
            if gap >= args.gap_days:
                gap_issues.append(f"{dates[i-1]}→{dates[i]} ({gap}d)")

        # Check tail (most recent call should be within ~120d of today)
        tail_issue = None
        if (today - last).days > args.gap_days:
            tail_issue = f"last call {last} is {(today-last).days}d ago"

        status_parts = []
        if early_issue: status_parts.append(early_issue)
        if gap_issues: status_parts.append(f"{len(gap_issues)} gap(s): {'; '.join(gap_issues)}")
        if tail_issue: status_parts.append(tail_issue)
        status = " | ".join(status_parts) if status_parts else "OK"

        print(f"{ticker:<8} {len(dates):>5}  {first}  {last}  {status}")

        if status_parts:
            issues.append((ticker, status_parts))

    print()
    if not issues:
        print("✓ No coverage issues detected. All tickers have continuous quarterly history.")
    else:
        print(f"⚠  Issues detected on {len(issues)} ticker(s):")
        for t, parts in issues:
            print(f"   {t}: {' | '.join(parts)}")
        print()
        print("Notes:")
        print("  - 'earliest is X' may just mean the ticker IPO'd later — check IPO date.")
        print("  - gap entries are likely missed quarters worth re-loading.")
        print("  - 'last call N days ago' may mean the next earnings hasn't been called yet (most")
        print("    big-cap companies report ~45-90 days after quarter end).")

    print()
    print(f"Total: {len(rows)} transcripts across {len(by_ticker)} ticker(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
