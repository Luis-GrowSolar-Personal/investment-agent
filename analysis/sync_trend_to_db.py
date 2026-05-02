#!/usr/bin/env python3
"""
sync_trend_to_db.py — Run the trend layer over Railway DB Analysis rows
and write verdicts back to the DB.

Single source of truth for trend verdicts: imports compute_trend_verdict,
apply_matrix, compute_final_confidence, and build_tier_function from
trend_analyst.py. Backtest CSV output and live RADAR data are identical
by construction.

Pre-reqs:
- DATABASE_URL in ../.env
- analysis/data/price_cache.json (refreshed via fetch_prices_*.py)
- analysis/data/fundamentals_cache.json (refreshed via fetch_fundamentals.py)
- Prisma migration `add_trend_fields` applied (six new Analysis columns)

Usage:
    cd analysis && python3 sync_trend_to_db.py             # all tickers
    cd analysis && python3 sync_trend_to_db.py --ticker AMPX --ticker ENVX
    cd analysis && python3 sync_trend_to_db.py --dry-run   # compute, don't write

Run after every new transcript evaluation until Stage 3 wires the
trigger-on-evaluate path into the Express backend. Idempotent — rerunning
just overwrites the same fields with the same values.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

from trend_analyst import (
    compute_trend_verdict,
    apply_matrix,
    compute_final_confidence,
    build_tier_function,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"
load_dotenv(ENV_PATH)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit(f"ERROR: DATABASE_URL not found in {ENV_PATH}")

PRICE_CACHE_PATH = SCRIPT_DIR / "data" / "price_cache.json"
FUNDAMENTALS_CACHE_PATH = SCRIPT_DIR / "data" / "fundamentals_cache.json"


def fetch_all_analyses(conn, tickers: set[str] | None):
    """Latest Analysis per Transcript, joined with Ticker. Older analyses
    (rebackfilled v6 superseding originals, or any prior re-eval) are
    excluded — using them in the timeline would double-count call dates.
    Mirrors the radar.js logic: `analyses[0]` after `orderBy createdAt desc`.

    Snake_case-aliased to match trend_analyst's expected input schema.
    Ordered by ticker symbol then callDate ascending."""
    where_clause = ""
    params: list = []
    if tickers:
        where_clause = "WHERE tk.symbol = ANY(%s)"
        params = [list(tickers)]
    sql = f"""
        SELECT
            sub.analysis_id,
            sub.ticker,
            sub.call_date,
            sub.thesis_health,
            sub.recommendation,
            sub.recommended_size,
            sub.fresh_money_allocation,
            sub.credibility_delta,
            sub.mitigation_track_record,
            sub.thesis_delta,
            sub.stumble_type
        FROM (
            SELECT
                a.id                                AS analysis_id,
                tk.symbol                           AS ticker,
                t."callDate"                        AS call_date,
                a."thesisHealth"                    AS thesis_health,
                a.recommendation                    AS recommendation,
                a."recommendedSize"                 AS recommended_size,
                a."freshMoneyAllocation"            AS fresh_money_allocation,
                a."credibilityDelta"                AS credibility_delta,
                a."mitigationCapabilityTrackRecord" AS mitigation_track_record,
                a."thesisDelta"                     AS thesis_delta,
                a."stumbleType"                     AS stumble_type,
                ROW_NUMBER() OVER (
                    PARTITION BY a."transcriptId"
                    ORDER BY a."createdAt" DESC, a.id DESC
                ) AS rn
            FROM "Analysis" a
            JOIN "Transcript" t ON a."transcriptId" = t.id
            JOIN "Ticker"     tk ON t."tickerId"    = tk.id
            {where_clause}
        ) sub
        WHERE sub.rn = 1
        ORDER BY sub.ticker ASC, sub.call_date ASC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def null_stale_trend_fields(conn, tickers: set[str] | None) -> int:
    """Clear trend fields on every non-latest Analysis. Idempotent.
    Older analyses are historical artifacts — they should have null trend
    fields so the UI doesn't display contradictory verdicts. Returns the
    number of rows affected."""
    where_clause = ""
    params: list = []
    if tickers:
        where_clause = "AND tk.symbol = ANY(%s)"
        params = [list(tickers)]
    sql = f"""
        UPDATE "Analysis" target
        SET tier = NULL,
            trajectory = NULL,
            "suggestedOverride" = NULL,
            "finalAction" = NULL,
            "finalConfidence" = NULL,
            "trendRationale" = NULL
        FROM "Transcript" t
        JOIN "Ticker" tk ON t."tickerId" = tk.id
        WHERE target."transcriptId" = t.id
          {where_clause}
          AND target.id NOT IN (
              SELECT a2.id FROM "Analysis" a2
              WHERE a2."transcriptId" = t.id
              ORDER BY a2."createdAt" DESC, a2.id DESC
              LIMIT 1
          )
          AND (target.tier IS NOT NULL
               OR target.trajectory IS NOT NULL
               OR target."finalAction" IS NOT NULL)
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def warn_if_classifier_data_missing(tickers: list[str], price_cache, fundamentals_cache):
    """The 3-axis classifier needs both price (for σ) and fundamentals
    (cap, P/E). If either is missing for a ticker, log it so the user can
    refresh the local caches before proceeding."""
    import json
    prices = json.loads(price_cache.read_text()) if price_cache.exists() else {}
    fundamentals = json.loads(fundamentals_cache.read_text()) if fundamentals_cache.exists() else {}
    missing = []
    for t in tickers:
        no_prices = not prices.get(t)
        no_funds = not fundamentals.get(t)
        if no_prices or no_funds:
            missing.append((t, no_prices, no_funds))
    if missing:
        print("WARNING: classifier data missing for some tickers — they will "
              "default to 'established' until refreshed:")
        for t, np, nf in missing:
            bits = []
            if np: bits.append("prices")
            if nf: bits.append("fundamentals")
            print(f"  {t}: missing {', '.join(bits)}")
        print("Refresh on the laptop:")
        if any(np for _, np, _ in missing):
            print("  python3 fetch_prices_<TICKER>.py   (or your usual fetcher)")
        if any(nf for _, _, nf in missing):
            print("  python3 fetch_fundamentals.py")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", action="append", default=[],
                    help="Restrict to these symbols (repeatable). Default: all "
                         "tickers in DB.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute verdicts and print a summary, don't write.")
    args = ap.parse_args()

    tier_fn = build_tier_function(PRICE_CACHE_PATH, FUNDAMENTALS_CACHE_PATH)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        wanted = {t.upper() for t in args.ticker} if args.ticker else None
        rows = fetch_all_analyses(conn, wanted)
        if not rows:
            print("No analyses found in DB. Nothing to do.")
            return 0

        # Group by ticker (rows already sorted ticker, callDate, createdAt)
        by_ticker: OrderedDict[str, list[dict]] = OrderedDict()
        for r in rows:
            by_ticker.setdefault(r["ticker"], []).append(dict(r))

        warn_if_classifier_data_missing(list(by_ticker.keys()),
                                          PRICE_CACHE_PATH,
                                          FUNDAMENTALS_CACHE_PATH)

        # Compute verdicts and accumulate updates.
        updates: list[tuple] = []
        per_ticker_rows: list[tuple] = []
        for ticker, history in by_ticker.items():
            tier = tier_fn(ticker) or "established"
            n_rows = len(history)
            n_advisory = n_override = n_unknown = 0
            for i in range(n_rows):
                curr = history[i]
                prior = history[: i + 1]
                verdict = compute_trend_verdict(prior, tier=tier)
                per_call_rec = curr.get("recommendation") or ""
                final_action, final_rationale = apply_matrix(per_call_rec, verdict)
                final_confidence = compute_final_confidence(
                    verdict, per_call_rec, final_action
                )
                trajectory = (verdict or {}).get("trajectory")
                override = (verdict or {}).get("suggested_override")

                if final_confidence == "advisory":
                    n_advisory += 1
                elif final_confidence == "unknown":
                    n_unknown += 1
                if override is not None and final_action != per_call_rec:
                    n_override += 1

                updates.append((
                    tier, trajectory, override, final_action,
                    final_confidence, final_rationale,
                    curr["analysis_id"],
                ))
            per_ticker_rows.append(
                (ticker, tier, n_rows, n_advisory, n_override, n_unknown)
            )

        # Print per-ticker summary
        print(f"\nVerdict summary ({len(updates)} analyses, "
              f"{len(by_ticker)} ticker(s)):")
        print(f"  {'TICKER':6}  {'TIER':12}  {'N':>3}  "
              f"{'ADV':>3}  {'OVR':>3}  {'UNK':>3}")
        for t, tier, n, na, nv, nu in per_ticker_rows:
            print(f"  {t:6}  {tier:12}  {n:>3}  {na:>3}  {nv:>3}  {nu:>3}")
        print("  ADV=advisory (trend noticed, didn't act). "
              "OVR=override fired and changed action. "
              "UNK=insufficient history.")

        if args.dry_run:
            print("\n[--dry-run] — no DB writes performed.")
            return 0

        # Step 1 — clear trend fields on non-latest analyses. Older analyses
        # are historical artifacts; they should not display contradictory
        # verdicts in RADAR. This also cleans up any stale data from a sync
        # run that predated the latest-per-transcript fix.
        n_nulled = null_stale_trend_fields(conn, wanted)

        # Step 2 — write fresh verdicts to the latest analysis per transcript.
        # Single transaction. Either all updates land or none.
        with conn.cursor() as cur:
            cur.executemany("""
                UPDATE "Analysis"
                SET tier               = %s,
                    trajectory         = %s,
                    "suggestedOverride" = %s,
                    "finalAction"       = %s,
                    "finalConfidence"   = %s,
                    "trendRationale"    = %s
                WHERE id = %s
            """, updates)
            conn.commit()
        print(f"\nCleared trend fields on {n_nulled} stale (non-latest) row(s).")
        print(f"Wrote {len(updates)} verdict updates to latest analyses.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
