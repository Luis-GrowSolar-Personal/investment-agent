#!/usr/bin/env python3
"""
check_db_integrity.py — Quick referential-integrity audit of the Railway DB.

Verifies:
- No orphaned Analysis rows (rows pointing at non-existent Transcripts).
  RESTRICT FK should make this impossible, but the schema can drift over
  time; cheap defense-in-depth.
- No orphaned Transcript rows (rows pointing at non-existent Tickers).
- Reports duplicate (tickerId, callDate) pairs — same call uploaded twice,
  which produces visually-confusing RADAR rows.
- Reports Transcripts with >1 Analysis (normal after rebackfill — there
  should be one v3/v5-era and one v6 row), and Transcripts with 0 Analyses
  (might indicate a failed evaluate run).

Usage:
    cd analysis && python3 check_db_integrity.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg2

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(ENV_PATH)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit(f"ERROR: DATABASE_URL not in {ENV_PATH}")


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    issues = 0
    try:
        with conn.cursor() as cur:
            # Total counts
            cur.execute('SELECT COUNT(*) FROM "Ticker"')
            n_tickers = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM "Transcript"')
            n_transcripts = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM "Analysis"')
            n_analyses = cur.fetchone()[0]
            print(f"Counts: {n_tickers} tickers, {n_transcripts} transcripts, "
                  f"{n_analyses} analyses\n")

            # 1. Orphan Analysis (transcriptId -> nothing)
            cur.execute("""
                SELECT a.id, a."transcriptId"
                FROM "Analysis" a
                LEFT JOIN "Transcript" t ON a."transcriptId" = t.id
                WHERE t.id IS NULL
            """)
            orphans_a = cur.fetchall()
            if orphans_a:
                issues += 1
                print(f"FAIL: {len(orphans_a)} orphaned Analysis row(s):")
                for aid, tid in orphans_a:
                    print(f"  Analysis id={aid} -> non-existent transcriptId={tid}")
            else:
                print("OK: no orphaned Analysis rows.")

            # 2. Orphan Transcript (tickerId -> nothing)
            cur.execute("""
                SELECT t.id, t."tickerId"
                FROM "Transcript" t
                LEFT JOIN "Ticker" tk ON t."tickerId" = tk.id
                WHERE tk.id IS NULL
            """)
            orphans_t = cur.fetchall()
            if orphans_t:
                issues += 1
                print(f"FAIL: {len(orphans_t)} orphaned Transcript row(s):")
                for tid, tkid in orphans_t:
                    print(f"  Transcript id={tid} -> non-existent tickerId={tkid}")
            else:
                print("OK: no orphaned Transcript rows.")

            # 3. Duplicate (tickerId, callDate) pairs — same call uploaded twice
            cur.execute("""
                SELECT tk.symbol, t."callDate"::date, COUNT(*) AS n,
                       array_agg(t.id ORDER BY t.id) AS transcript_ids
                FROM "Transcript" t
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                GROUP BY tk.symbol, t."callDate"
                HAVING COUNT(*) > 1
                ORDER BY tk.symbol, t."callDate"
            """)
            dupes = cur.fetchall()
            if dupes:
                issues += 1
                print(f"\nFAIL: {len(dupes)} duplicate (ticker, callDate) pair(s):")
                for sym, dt, n, ids in dupes:
                    print(f"  {sym} {dt}: {n} transcripts, ids={ids}")
            else:
                print("OK: no duplicate (ticker, callDate) pairs.")

            # 4. Transcripts with no analyses (could indicate failed evaluate run,
            #    or a transcript that was uploaded but never evaluated)
            cur.execute("""
                SELECT tk.symbol, t."callDate"::date, t.id
                FROM "Transcript" t
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                LEFT JOIN "Analysis" a ON a."transcriptId" = t.id
                WHERE a.id IS NULL
                ORDER BY tk.symbol, t."callDate"
            """)
            no_analyses = cur.fetchall()
            if no_analyses:
                print(f"\nWARN: {len(no_analyses)} transcript(s) with no analysis "
                      f"(may need manual evaluate or rebackfill):")
                for sym, dt, tid in no_analyses:
                    print(f"  {sym} {dt} (transcript id={tid})")

            # 5. Per-transcript analysis counts (info only — useful for spotting
            #    rebackfill state)
            cur.execute("""
                SELECT n_analyses, COUNT(*) AS n_transcripts
                FROM (
                    SELECT t.id, COUNT(a.id) AS n_analyses
                    FROM "Transcript" t
                    LEFT JOIN "Analysis" a ON a."transcriptId" = t.id
                    GROUP BY t.id
                ) sub
                GROUP BY n_analyses
                ORDER BY n_analyses
            """)
            print("\nAnalysis-per-transcript distribution:")
            for n_a, n_t in cur.fetchall():
                label = ""
                if n_a == 0:
                    label = "  (no analysis yet)"
                elif n_a == 1:
                    label = "  (single analysis — pre-rebackfill)"
                elif n_a == 2:
                    label = "  (two analyses — typical post-rebackfill: original + v6)"
                elif n_a > 2:
                    label = "  (3+ analyses — multiple re-evaluations)"
                print(f"  {n_a} analyses: {n_t} transcripts{label}")

        if issues == 0:
            print("\nAll integrity checks passed.")
            return 0
        else:
            print(f"\n{issues} integrity issue(s) found.")
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
