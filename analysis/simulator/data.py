"""
data.py — Data loaders for the backtest simulator.

Two sources:
  - Railway Postgres: latest Analysis per Transcript, joined to Ticker
    (we want the trend-layer fields populated by sync_trend_to_db.py)
  - analysis/data/price_cache.json: daily Adj Close per ticker

Outputs:
  - CallEvent objects, indexed by date
  - PriceLookup with date-aware lookups (uses most-recent prior trading day
    when the requested date isn't a trading day, e.g. weekends)

Run module directly to exercise self-tests (against price cache only;
DB tests require live connection):
    python3 -m analysis.simulator.data
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SCRIPT_DIR.parent  # analysis/
PRICE_CACHE_PATH = ANALYSIS_DIR / "data" / "price_cache.json"
ENV_PATH = ANALYSIS_DIR.parent / ".env"


@dataclass
class CallEvent:
    """One earnings call, with the agent's verdict on it. The simulator
    iterates these in date order."""
    ticker: str
    call_date: date
    per_call_rec: Optional[str]        # 'Add' | 'Hold' | 'Trim' | 'Exit'
    recommended_size: Optional[float]   # 0-100 or None
    type_classification: Optional[str]  # 'A' | 'B' | None
    thesis_health: Optional[str]
    final_action: Optional[str]         # post-trend-layer action; falls back to per_call_rec
    final_confidence: Optional[str]
    trajectory: Optional[str]


@dataclass
class PriceLookup:
    """Price lookup with date-aware fallback to the most recent prior
    trading day. Holds the entire price_cache.json in memory."""
    by_ticker: dict[str, dict[date, float]]

    @classmethod
    def from_cache(cls, path: Path = PRICE_CACHE_PATH) -> "PriceLookup":
        if not path.exists():
            raise FileNotFoundError(f"Price cache not found: {path}")
        raw = json.loads(path.read_text())
        by_ticker: dict[str, dict[date, float]] = {}
        for ticker, series in raw.items():
            parsed: dict[date, float] = {}
            for date_str, price in series.items():
                try:
                    d = date.fromisoformat(date_str)
                except ValueError:
                    continue
                parsed[d] = float(price)
            by_ticker[ticker] = parsed
        return cls(by_ticker=by_ticker)

    def has_ticker(self, ticker: str) -> bool:
        return ticker in self.by_ticker

    def price_on(self, ticker: str, d: date, max_lookback_days: int = 7) -> Optional[float]:
        """Return the close price for `ticker` on date `d`, falling back
        to the most recent prior trading day within `max_lookback_days`.
        Returns None if no price available in the lookback window."""
        series = self.by_ticker.get(ticker)
        if series is None:
            return None
        # Try exact date first
        if d in series:
            return series[d]
        # Walk backward up to max_lookback_days
        for offset in range(1, max_lookback_days + 1):
            candidate = d - timedelta(days=offset)
            if candidate in series:
                return series[candidate]
        return None

    def all_prices_on(self, tickers: list[str], d: date) -> dict[str, float]:
        """Convenience: lookup all `tickers` on `d`, skipping any that don't
        resolve. Used by the simulator for daily mark-to-market."""
        result: dict[str, float] = {}
        for t in tickers:
            p = self.price_on(t, d)
            if p is not None:
                result[t] = p
        return result

    def first_date(self, ticker: str) -> Optional[date]:
        series = self.by_ticker.get(ticker)
        if not series:
            return None
        return min(series.keys())

    def last_date(self, ticker: str) -> Optional[date]:
        series = self.by_ticker.get(ticker)
        if not series:
            return None
        return max(series.keys())


# ---------------------------------------------------------------------------
# DB loader (psycopg2, Railway Postgres)
# ---------------------------------------------------------------------------

def load_call_events(
    tickers: Optional[list[str]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[CallEvent]:
    """Load latest Analysis-per-Transcript, joined with Ticker, optionally
    filtered to a ticker list and date range. Returns events in chronological
    order (oldest first).

    Requires DATABASE_URL in ../../.env. Reads from Railway Postgres directly.
    """
    try:
        from dotenv import load_dotenv
        import psycopg2
        import psycopg2.extras
    except ImportError as e:
        raise ImportError(
            f"data.py requires psycopg2 and python-dotenv: {e}"
        ) from e

    load_dotenv(ENV_PATH)
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(f"DATABASE_URL not in {ENV_PATH}")

    where_clauses = []
    params: list = []
    if tickers:
        where_clauses.append('tk.symbol = ANY(%s)')
        params.append(list(tickers))
    if start_date:
        where_clauses.append('t."callDate" >= %s')
        params.append(start_date)
    if end_date:
        where_clauses.append('t."callDate" <= %s')
        params.append(end_date)

    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    sql = f"""
        SELECT
            tk.symbol AS ticker,
            t."callDate"::date AS call_date,
            a.recommendation AS per_call_rec,
            a."recommendedSize" AS recommended_size,
            a."thesisHealth" AS thesis_health,
            a."finalAction" AS final_action,
            a."finalConfidence" AS final_confidence,
            a.trajectory AS trajectory
        FROM "Analysis" a
        JOIN "Transcript" t ON a."transcriptId" = t.id
        JOIN "Ticker" tk ON t."tickerId" = tk.id
        JOIN (
            SELECT a2."transcriptId", MAX(a2."createdAt") AS latest
            FROM "Analysis" a2
            GROUP BY a2."transcriptId"
        ) latest ON latest."transcriptId" = a."transcriptId"
                AND latest.latest = a."createdAt"
        {where_sql}
        ORDER BY t."callDate" ASC, tk.symbol ASC
    """

    # We also want typeClassification, which lives only in the structured
    # score JSON within rawOutput. For simplicity we extract it via a regex
    # on the rawOutput in Python, since we already have the rest of the data.
    # We'll do that as a second pass below.
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        # Second pass: fetch typeClassification per analysis from rawOutput
        # (only needed if downstream Add decisions care about Type A vs B)
        ids_by_key = {(r["ticker"], r["call_date"]): None for r in rows}
        # Easiest: query rawOutput for the same set of latest analyses.
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                       a."rawOutput" AS raw_output
                FROM "Analysis" a
                JOIN "Transcript" t ON a."transcriptId" = t.id
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                JOIN (
                    SELECT a2."transcriptId", MAX(a2."createdAt") AS latest
                    FROM "Analysis" a2
                    GROUP BY a2."transcriptId"
                ) latest ON latest."transcriptId" = a."transcriptId"
                        AND latest.latest = a."createdAt"
                {where_sql}
            """, params)
            for raw_row in cur.fetchall():
                key = (raw_row["ticker"], raw_row["call_date"])
                ids_by_key[key] = _extract_type_classification(raw_row["raw_output"])
    finally:
        conn.close()

    events: list[CallEvent] = []
    for r in rows:
        key = (r["ticker"], r["call_date"])
        events.append(CallEvent(
            ticker=r["ticker"],
            call_date=r["call_date"],
            per_call_rec=r["per_call_rec"],
            recommended_size=(float(r["recommended_size"])
                                if r["recommended_size"] is not None else None),
            type_classification=ids_by_key.get(key),
            thesis_health=r["thesis_health"],
            final_action=r["final_action"] or r["per_call_rec"],
            final_confidence=r["final_confidence"],
            trajectory=r["trajectory"],
        ))
    return events


def _extract_type_classification(raw_output: Optional[str]) -> Optional[str]:
    """Pull typeClassification from the STRUCTURED block of rawOutput. The
    block is JSON like `{"thesisHealth":"...","typeClassification":"A",...}`."""
    if not raw_output:
        return None
    import re
    m = re.search(r'---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---',
                  raw_output, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        v = d.get("typeClassification")
        if v in ("A", "B"):
            return v
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Convenience: index events by call_date for the simulator loop
# ---------------------------------------------------------------------------

def index_events_by_date(events: list[CallEvent]) -> dict[date, list[CallEvent]]:
    by_date: dict[date, list[CallEvent]] = {}
    for ev in events:
        by_date.setdefault(ev.call_date, []).append(ev)
    return by_date


# ---------------------------------------------------------------------------
# Self-tests (price cache only — no DB required)
# ---------------------------------------------------------------------------

def _selftest():
    if not PRICE_CACHE_PATH.exists():
        print(f"SKIP: {PRICE_CACHE_PATH} not present")
        return
    pl = PriceLookup.from_cache()
    # Exercise lookup on a known ticker if any exist
    sample = next(iter(pl.by_ticker.keys()), None)
    if sample is None:
        print("SKIP: empty price cache")
        return
    last = pl.last_date(sample)
    p = pl.price_on(sample, last)
    assert p is not None and p > 0
    # Lookback: a Sunday should resolve to the prior Friday
    if last:
        # Pick a date just past the last available
        beyond = last + timedelta(days=2)
        p2 = pl.price_on(sample, beyond)
        assert p2 is not None  # should fall back via lookback
    # Out-of-range lookback should return None
    way_old = date(1900, 1, 1)
    assert pl.price_on(sample, way_old) is None
    print(f"data.py self-tests passed (sample ticker: {sample}, last={last})")


if __name__ == "__main__":
    _selftest()
