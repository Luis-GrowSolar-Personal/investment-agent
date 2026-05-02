#!/usr/bin/env python3
"""
rebackfill_v6_analyses.py — Append a v6-consistent Analysis row per
Transcript in the Railway DB, using the cached v6 evaluator outputs.

Why this exists: the live DB accumulated analyses across multiple prompt
versions (v3/v5/v6). For backtest baselines and live RADAR coherence we
want every transcript to have at least one v6-evaluated analysis. The
schema's 1:N Transcript→Analysis relation lets us *append* without
overwriting history — RADAR shows the most recent (latest createdAt)
analysis automatically, while older prompt-version verdicts remain in
the DB for historical/auditing reference.

Pre-reqs:
- DATABASE_URL in ../.env
- Cached v6 evals in data/evals/v6/<SYMBOL>_<CALL_DATE>.txt for each
  Transcript that needs backfilling. Run `eval_cache_warmer.py` first
  for any tickers not yet warmed.

Idempotency: detects existing v6 analyses by exact rawOutput match and
skips them. Safe to re-run.

Usage:
    cd analysis && python3 rebackfill_v6_analyses.py             # all tickers
    cd analysis && python3 rebackfill_v6_analyses.py --ticker ENPH
    cd analysis && python3 rebackfill_v6_analyses.py --dry-run   # preview, no writes

After this runs, re-run sync_trend_to_db.py — trend verdicts will be
recomputed against v6-consistent inputs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

EVALS_DIR = SCRIPT_DIR / "data" / "evals" / "v6"


# ---------------------------------------------------------------------------
# Parsers — must match server/routes/save.js logic so live and backfilled
# rows are populated the same way.
# ---------------------------------------------------------------------------

def extract_section(text: str, section_name: str) -> str:
    pattern = rf"##\s+{re.escape(section_name)}[\s\S]*?(?=\n##|$)"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(0) if m else ""


def parse_first_line(section: str, candidates: list[str]) -> str | None:
    first_line = next(
        (l for l in section.split("\n") if l.strip() and not l.startswith("#")),
        "",
    )
    # Anchor to start of line — verdict always leads
    for v in candidates:
        if re.match(rf"\s*(score:\s*)?{v}\b", first_line, re.IGNORECASE):
            return v
    # Fallback: whole-word anywhere in section
    for v in candidates:
        if re.search(rf"\b{v}\b", section, re.IGNORECASE):
            return v
    return None


def parse_thesis_health(text: str) -> str:
    section = extract_section(text, "THESIS HEALTH")
    return parse_first_line(
        section, ["Strengthening", "Intact", "Weakening", "Broken"]
    ) or "Unknown"


def parse_recommendation(text: str) -> str:
    section = extract_section(text, "RECOMMENDATION")
    return parse_first_line(section, ["Exit", "Trim", "Add", "Hold"]) or "Unknown"


def parse_recommended_size(text: str) -> float | None:
    section = extract_section(text, "RECOMMENDATION")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", section)
    return float(m.group(1)) if m else None


def parse_structured(raw: str) -> dict:
    m = re.search(
        r"---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---", raw, re.DOTALL
    )
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"  WARN: structured JSON parse error: {e}")
        return {}


def strip_structured(raw: str) -> str:
    return re.sub(
        r"\n*---STRUCTURED---[\s\S]*?---END STRUCTURED---\s*",
        "",
        raw,
    ).strip()


def strip_metadata(raw: str) -> str:
    return re.sub(
        r"\n*---METADATA---[\s\S]*?---END METADATA---\s*$",
        "",
        raw,
    ).strip()


# ---------------------------------------------------------------------------
# DB I/O
# ---------------------------------------------------------------------------

def fetch_transcripts(conn, tickers: set[str] | None):
    where = ""
    params: list = []
    if tickers:
        where = "WHERE tk.symbol = ANY(%s)"
        params = [list(tickers)]
    sql = f"""
        SELECT
            t.id          AS transcript_id,
            t."callDate"::date AS call_date,
            tk.symbol     AS symbol
        FROM "Transcript" t
        JOIN "Ticker" tk ON t."tickerId" = tk.id
        {where}
        ORDER BY tk.symbol ASC, t."callDate" ASC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def existing_v6_analysis_exists(conn, transcript_id: int, raw_output_clean: str) -> bool:
    """Check if any Analysis on this transcript has rawOutput equal to the
    v6 cached output (after stripping STRUCTURED + METADATA blocks, since
    that's how rawOutput is stored by save.js)."""
    sql = """
        SELECT id, "rawOutput"
        FROM "Analysis"
        WHERE "transcriptId" = %s
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (transcript_id,))
        for row in cur.fetchall():
            if (row["rawOutput"] or "").strip() == raw_output_clean.strip():
                return True
    return False


def insert_v6_analysis(conn, transcript_id: int, raw_clean: str,
                         narrative_fields: dict, structured: dict) -> int:
    """Insert one Analysis row matching the schema written by save.js.
    Returns the new id."""
    sql = """
        INSERT INTO "Analysis" (
            "transcriptId", "rawOutput", "thesisHealth", "recommendation",
            "recommendedSize",
            "thesisDelta", "freshMoneyAllocation", "stumbleType",
            "threatMechanismImpaired", "credibilityDelta",
            "activeDriverCount", "ratchetTranche", "blindSpotsTriggered",
            "capPercent", "mitigationArgumentPresent",
            "mitigationCapabilityTrackRecord"
        )
        VALUES (
            %s, %s, %s, %s,
            %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s::jsonb,
            %s, %s,
            %s
        )
        RETURNING id
    """
    blind_spots = structured.get("blindSpotsTriggered")
    blind_spots_json = json.dumps(blind_spots) if blind_spots is not None else None
    with conn.cursor() as cur:
        cur.execute(sql, (
            transcript_id,
            raw_clean,
            narrative_fields["thesisHealth"],
            narrative_fields["recommendation"],
            narrative_fields["recommendedSize"],
            structured.get("thesisDelta"),
            structured.get("freshMoneyAllocation"),
            structured.get("stumbleType"),
            structured.get("threatMechanismImpaired"),
            structured.get("credibilityDelta"),
            structured.get("activeDriverCount"),
            structured.get("ratchetTranche"),
            blind_spots_json,
            structured.get("capPercent"),
            structured.get("mitigationArgumentPresent"),
            structured.get("mitigationCapabilityTrackRecord"),
        ))
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", action="append", default=[],
                    help="Restrict to these symbols (repeatable). Default: all.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would happen, don't write.")
    args = ap.parse_args()

    if not EVALS_DIR.exists():
        sys.exit(f"ERROR: {EVALS_DIR} not found. Run eval_cache_warmer.py first.")

    wanted = {t.upper() for t in args.ticker} if args.ticker else None

    conn = psycopg2.connect(DATABASE_URL)
    try:
        transcripts = fetch_transcripts(conn, wanted)
        if not transcripts:
            print("No transcripts in DB matching filter.")
            return 0

        n_inserted = n_skipped_existing = n_skipped_no_cache = 0
        missing: list[tuple[str, str]] = []
        for t in transcripts:
            sym = t["symbol"]
            date_str = t["call_date"].strftime("%Y-%m-%d")
            cache_path = EVALS_DIR / f"{sym}_{date_str}.txt"

            if not cache_path.exists():
                missing.append((sym, date_str))
                n_skipped_no_cache += 1
                continue

            raw_full = cache_path.read_text()
            structured = parse_structured(raw_full)
            raw_clean = strip_structured(strip_metadata(raw_full))

            # The structured score block is authoritative for these three
            # fields when present — the v6 prompt emits them deterministically
            # in JSON. Narrative parsing is the fallback. This is more reliable
            # than save.js's narrative-only logic; save.js should adopt the
            # same pattern in a follow-up. Concrete case: ENPH 2024-04-23 has
            # no percentage in the RECOMMENDATION narrative ("Hold with
            # specific watch condition..."), but the structured block has
            # recommendedSize=28.
            narr_size = parse_recommended_size(raw_clean)
            narrative_fields = {
                "thesisHealth": (structured.get("thesisHealth")
                                  or parse_thesis_health(raw_clean) or "Unknown"),
                "recommendation": (structured.get("recommendation")
                                    or parse_recommendation(raw_clean) or "Unknown"),
                "recommendedSize": (structured.get("recommendedSize")
                                     if structured.get("recommendedSize") is not None
                                     else narr_size),
            }

            if existing_v6_analysis_exists(conn, t["transcript_id"], raw_clean):
                n_skipped_existing += 1
                print(f"  [{sym} {date_str}] v6 analysis already present, skip")
                continue

            if args.dry_run:
                print(f"  [{sym} {date_str}] would insert: "
                      f"{narrative_fields['thesisHealth']} / "
                      f"{narrative_fields['recommendation']} / "
                      f"size={narrative_fields['recommendedSize']}")
                n_inserted += 1
                continue

            new_id = insert_v6_analysis(
                conn, t["transcript_id"], raw_clean, narrative_fields, structured
            )
            print(f"  [{sym} {date_str}] inserted Analysis id={new_id}: "
                  f"{narrative_fields['thesisHealth']} / "
                  f"{narrative_fields['recommendation']} / "
                  f"size={narrative_fields['recommendedSize']}")
            n_inserted += 1

        if not args.dry_run:
            conn.commit()

        print(f"\nDone. inserted={n_inserted}  "
              f"skipped_existing={n_skipped_existing}  "
              f"skipped_no_cache={n_skipped_no_cache}  "
              f"total={len(transcripts)}")
        if missing:
            print("\nMissing v6 cache (warm with eval_cache_warmer.py):")
            by_ticker: dict[str, list[str]] = {}
            for sym, d in missing:
                by_ticker.setdefault(sym, []).append(d)
            for sym in sorted(by_ticker):
                print(f"  {sym}: {len(by_ticker[sym])} missing — "
                      f"{', '.join(by_ticker[sym])}")
            print("\nWarm them like:")
            sym_args = " ".join(f"--ticker {s}" for s in sorted(by_ticker))
            print(f"  python3 eval_cache_warmer.py {sym_args} --parallel 15")
            print("Then re-run rebackfill_v6_analyses.py.")
        if args.dry_run:
            print("\n[--dry-run] — no DB writes performed.")
        else:
            print("\nNext: python3 sync_trend_to_db.py")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
