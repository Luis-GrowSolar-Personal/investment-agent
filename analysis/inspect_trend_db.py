#!/usr/bin/env python3
"""
inspect_trend_db.py — Print joined Analysis + Transcript + Ticker rows
for a given symbol, including the new trend-layer fields. Useful for
verifying a sync_trend_to_db.py run landed correctly without squinting
through Prisma Studio's two-hop joins.

Usage:
    cd analysis && python3 inspect_trend_db.py --ticker ENPH
    cd analysis && python3 inspect_trend_db.py --ticker ENPH --ticker TTD
    cd analysis && python3 inspect_trend_db.py             # every ticker, summary
"""
from __future__ import annotations

import argparse
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


def fetch(conn, tickers: list[str] | None):
    where = ""
    params: list = []
    if tickers:
        where = "WHERE tk.symbol = ANY(%s)"
        params = [tickers]
    sql = f"""
        SELECT
            tk.symbol,
            t."callDate"::date AS call_date,
            a.id AS analysis_id,
            a."thesisHealth" AS thesis_health,
            a.recommendation AS per_call,
            a."recommendedSize" AS size,
            a."freshMoneyAllocation" AS fresh,
            a.tier,
            a.trajectory,
            a."suggestedOverride" AS override,
            a."finalAction" AS final_action,
            a."finalConfidence" AS final_confidence
        FROM "Analysis" a
        JOIN "Transcript" t ON a."transcriptId" = t.id
        JOIN "Ticker" tk ON t."tickerId" = tk.id
        {where}
        ORDER BY tk.symbol ASC, t."callDate" ASC, a."createdAt" ASC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", action="append", default=[],
                    help="Restrict to these symbols (repeatable). Default: all.")
    args = ap.parse_args()
    tickers = [t.upper() for t in args.ticker] if args.ticker else None

    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = fetch(conn, tickers)
        if not rows:
            print("No analyses found.")
            return 0

        # Print full per-row table
        print(f"\n{len(rows)} analyses:\n")
        cols = ["symbol", "call_date", "analysis_id", "thesis_health", "per_call",
                "size", "fresh", "tier", "trajectory", "override",
                "final_action", "final_confidence"]
        labels = {c: c.upper() for c in cols}
        labels.update({
            "call_date": "DATE", "analysis_id": "AID",
            "thesis_health": "HEALTH", "per_call": "REC",
            "final_confidence": "CONF",
        })
        widths = {c: max(len(labels[c]),
                          max((len(str(r[c] if r[c] is not None else "—")) for r in rows), default=1))
                  for c in cols}
        print("  ".join(labels[c].ljust(widths[c]) for c in cols))
        print("  ".join("-" * widths[c] for c in cols))
        for r in rows:
            print("  ".join(
                str(r[c] if r[c] is not None else "—").ljust(widths[c])
                for c in cols
            ))

        # Per-ticker summary of confidence buckets
        print("\nConfidence summary by ticker:")
        from collections import Counter
        by_tk: dict[str, list[dict]] = {}
        for r in rows:
            by_tk.setdefault(r["symbol"], []).append(r)
        print(f"  {'TICKER':6}  {'TIER':12}  {'N':>3}  "
              f"{'CONF':>4}  {'ADV':>3}  {'UNK':>3}  {'NULL':>4}")
        for sym in sorted(by_tk.keys()):
            trs = by_tk[sym]
            tier = next((r["tier"] for r in trs if r["tier"]), "—")
            confs = Counter(r["final_confidence"] for r in trs)
            n = len(trs)
            null_count = sum(1 for r in trs if r["final_confidence"] is None)
            print(f"  {sym:6}  {tier:12}  {n:>3}  "
                  f"{confs.get('confident', 0):>4}  "
                  f"{confs.get('advisory', 0):>3}  "
                  f"{confs.get('unknown', 0):>3}  "
                  f"{null_count:>4}")
        print("  CONF=confident, ADV=advisory, UNK=unknown (insufficient history),")
        print("  NULL=trend fields not populated (sync didn't touch this row)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
