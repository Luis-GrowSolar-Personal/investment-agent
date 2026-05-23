#!/usr/bin/env python3
"""
dump_transcripts.py — One-time dump of portfolio transcripts from
Postgres to local files.

This decouples the prompt-iteration loop from the Railway database.
After running this once, backtest_from_files.py can drive the full
backtest without any DB dependency.

Usage:
    cd analysis && python3 dump_transcripts.py
    cd analysis && python3 dump_transcripts.py --ticker ENPH

Output:
    analysis/data/transcripts/<TICKER>_<YYYY-MM-DD>.txt   (one per transcript)
    analysis/data/transcripts/_manifest.json              (index of files)

The .txt files contain raw transcript text only, one transcript per file.
The manifest preserves the title and ticker id so the file-mode runner
can reconstruct the exact rows the DB-backed runner produces.

Requirements:
    python3 -m pip install psycopg2-binary python-dotenv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(ENV_PATH)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print(f"ERROR: DATABASE_URL not found. Checked {ENV_PATH}")
    sys.exit(1)

OUT_DIR = SCRIPT_DIR / "data" / "transcripts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def fetch_portfolio_tickers(conn, symbols: list[str] | None):
    """Fetch tickers. If symbols is given, pulls any status (portfolio OR
    watchlist) matching those symbols. If not given, defaults to portfolio
    only — preserves the original behavior for full-dump runs."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if symbols:
            upper = [s.upper() for s in symbols]
            cur.execute(
                'SELECT id, symbol, name, status FROM "Ticker" '
                'WHERE symbol = ANY(%s) ORDER BY symbol',
                (upper,),
            )
        else:
            cur.execute(
                'SELECT id, symbol, name, status FROM "Ticker" '
                'WHERE status = %s ORDER BY symbol',
                ("portfolio",),
            )
        return cur.fetchall()


def fetch_transcripts(conn, ticker_id: int):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            'SELECT id, "callDate", title, "rawText" '
            'FROM "Transcript" WHERE "tickerId" = %s '
            'ORDER BY "callDate" ASC',
            (ticker_id,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ticker",
        action="append",
        default=[],
        help="Dump only these ticker symbols (repeatable). When set, includes "
             "watchlist tickers too. Default (no --ticker): all portfolio tickers.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge into existing _manifest.json instead of overwriting it. "
             "Use when adding tickers without losing the existing ENPH/TTD entries.",
    )
    args = parser.parse_args()

    print(f"Dumping transcripts to {OUT_DIR}")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        tickers = fetch_portfolio_tickers(conn, args.ticker or None)
        if not tickers:
            print("ERROR: no portfolio tickers matched.")
            return 1

        manifest: list[dict] = []
        if args.merge:
            existing_path = OUT_DIR / "_manifest.json"
            if existing_path.exists():
                manifest = json.loads(existing_path.read_text())
                print(f"Merging into existing manifest ({len(manifest)} entries)")

        touched_symbols = {t["symbol"] for t in tickers}
        # Drop prior entries for symbols we're re-dumping; keep the rest.
        manifest = [m for m in manifest if m["ticker"] not in touched_symbols]

        total_files = 0
        for t in tickers:
            symbol = t["symbol"]
            transcripts = fetch_transcripts(conn, t["id"])
            print(f"  {symbol} ({t.get('status','?')}): {len(transcripts)} transcript(s)")
            for tr in transcripts:
                call_date = tr["callDate"]
                date_str = call_date.strftime("%Y-%m-%d")
                filename = f"{symbol}_{date_str}.txt"
                path = OUT_DIR / filename
                path.write_text(tr["rawText"])
                manifest.append({
                    "ticker": symbol,
                    "company": t["name"],
                    "call_date": date_str,
                    "title": tr["title"],
                    "filename": filename,
                })
                total_files += 1

        # Sort for stable diffs.
        manifest.sort(key=lambda m: (m["ticker"], m["call_date"]))
        manifest_path = OUT_DIR / "_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"\nWrote {total_files} transcript file(s)")
        print(f"Wrote manifest: {manifest_path}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
