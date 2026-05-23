#!/usr/bin/env python3
"""
verify_top20_2021_loaded.py — Confirm all 20 top-2021 tickers exist in
the DB with at least one transcript, and report the latest transcript
date per ticker.

Useful as you progressively load transcripts — re-run after each batch
to see what's still missing or under-loaded.

Usage:
    cd analysis && python3 verify_top20_2021_loaded.py
"""
from __future__ import annotations

import os
import sys
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

# Top 20 S&P 500 from Jan 2021, ADBE substituted for BRK.B.
EXPECTED = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "ADBE",
    "V", "JNJ", "WMT", "JPM", "PG", "UNH", "DIS", "NVDA",
    "MA", "HD", "PYPL", "BAC", "NFLX",
]


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT tk.symbol,
                       tk.status,
                       COUNT(t.id) AS n_transcripts,
                       MIN(t."callDate")::date AS earliest,
                       MAX(t."callDate")::date AS latest
                FROM "Ticker" tk
                LEFT JOIN "Transcript" t ON t."tickerId" = tk.id
                WHERE tk.symbol = ANY(%s)
                GROUP BY tk.symbol, tk.status
                ORDER BY tk.symbol
            """, (EXPECTED,))
            rows = cur.fetchall()
    finally:
        conn.close()

    found = {r["symbol"]: r for r in rows}
    missing = [s for s in EXPECTED if s not in found]

    print(f"Top 20 (2021) coverage check — expected {len(EXPECTED)} tickers\n")
    print(f"{'TICKER':<8} {'STATUS':<11} {'COUNT':>6}  {'EARLIEST':12}  {'LATEST':12}")
    print("-" * 60)
    for symbol in EXPECTED:
        if symbol in found:
            r = found[symbol]
            n = r["n_transcripts"] or 0
            earliest = r["earliest"] or "—"
            latest = r["latest"] or "—"
            status = r["status"] or "—"
            flag = "" if n > 0 else "  ⚠ no transcripts"
            print(f"{symbol:<8} {status:<11} {n:>6}  {earliest!s:12}  {latest!s:12}{flag}")
        else:
            print(f"{symbol:<8} {'—':<11} {'—':>6}  {'—':12}  {'—':12}  ⚠ ticker not in DB")

    print()
    if missing:
        print(f"⚠ Tickers MISSING from DB ({len(missing)}): {', '.join(missing)}")
    else:
        with_zero = [s for s in EXPECTED if found[s]["n_transcripts"] == 0]
        if with_zero:
            print(f"⚠ All tickers exist but {len(with_zero)} have zero transcripts: "
                  f"{', '.join(with_zero)}")
        else:
            print(f"✓ All {len(EXPECTED)} tickers present with at least 1 transcript.")

    # Summary of how loaded the universe is
    if not missing:
        total = sum((found[s]["n_transcripts"] or 0) for s in EXPECTED)
        avg = total / len(EXPECTED)
        print(f"\nTotal transcripts across universe: {total}")
        print(f"Average per ticker:                {avg:.1f}")
        target = 20  # ~16 quarters from Q1 2021 + ~4 from earlier or padding
        below = [s for s in EXPECTED if (found[s]["n_transcripts"] or 0) < 10]
        if below:
            print(f"\n{len(below)} ticker(s) have <10 transcripts (likely still loading):")
            for s in below:
                print(f"  {s}: {found[s]['n_transcripts']} transcript(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
