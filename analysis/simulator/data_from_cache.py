"""
data_from_cache.py — Load CallEvents from local v6 eval cache (no DB required).

The DB-backed loader (`data.py:load_call_events`) requires Railway access. This
loader uses the v6 cached eval text files at `data/evals/v6/<TICKER>_<DATE>.txt`
and computes trend verdicts in-memory using `trend_analyst.py`. Behavior should
match the DB-backed path because `sync_trend_to_db.py` is the same logic.

Why bother: lets the simulator run in the sandbox where DB connectivity is blocked.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .data import CallEvent

EVALS_DIR = Path(__file__).resolve().parent.parent / "data" / "evals" / "v6"
STRUCTURED_RE = re.compile(
    r"---STRUCTURED---\s*(\{.*?\})\s*---END STRUCTURED---", re.DOTALL
)


def _parse_structured(text: str) -> dict:
    m = STRUCTURED_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def load_events_from_cache() -> list[CallEvent]:
    """Walk data/evals/v6/, parse each file, return CallEvents in chronological
    order. final_action is set later by `attach_trend_verdicts`."""
    events: list[CallEvent] = []
    for f in sorted(EVALS_DIR.glob("*.txt")):
        # Filename: TICKER_YYYY-MM-DD.txt
        stem = f.stem
        try:
            ticker, date_str = stem.split("_", 1)
            d = date.fromisoformat(date_str)
        except ValueError:
            continue
        s = _parse_structured(f.read_text())
        events.append(CallEvent(
            ticker=ticker,
            call_date=d,
            per_call_rec=s.get("recommendation"),
            recommended_size=(float(s["recommendedSize"])
                                if s.get("recommendedSize") is not None else None),
            type_classification=s.get("typeClassification"),
            thesis_health=s.get("thesisHealth"),
            final_action=None,             # filled by attach_trend_verdicts()
            final_confidence=None,
            trajectory=None,
        ))
    events.sort(key=lambda e: (e.ticker, e.call_date))
    return events


def attach_trend_verdicts(
    events: list[CallEvent],
    tier_for_ticker=None,
) -> None:
    """For each event, compute trend verdict using prior history of the same
    ticker, then set final_action/trajectory/final_confidence in place.

    Mirrors what sync_trend_to_db.py does but in-memory.
    """
    # Lazy imports to avoid circular dependencies
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from trend_analyst import (
        compute_trend_verdict, apply_matrix, compute_final_confidence,
    )

    by_ticker: dict[str, list[CallEvent]] = {}
    for e in events:
        by_ticker.setdefault(e.ticker, []).append(e)

    for ticker, ticker_events in by_ticker.items():
        ticker_events.sort(key=lambda e: e.call_date)
        tier = (tier_for_ticker(ticker) if tier_for_ticker else "established") or "established"

        for i, ev in enumerate(ticker_events):
            # Build history dicts in trend_analyst's expected shape
            history = []
            for prior in ticker_events[: i + 1]:
                history.append({
                    "thesis_health": prior.thesis_health,
                    "recommendation": prior.per_call_rec,
                    "recommended_size": prior.recommended_size,
                    # The cached eval files don't have these directly accessible
                    # without a second parse. For trend verdict logic, the most
                    # important fields are size, fresh_money, credibility, mtr.
                    # We read these on demand from the eval file:
                    "fresh_money_allocation": _read_field(prior.ticker, prior.call_date,
                                                            "freshMoneyAllocation"),
                    "credibility_delta": _read_field(prior.ticker, prior.call_date,
                                                       "credibilityDelta"),
                    "mitigation_track_record": _read_field(prior.ticker, prior.call_date,
                                                             "mitigationCapabilityTrackRecord"),
                    "stumble_type": _read_field(prior.ticker, prior.call_date,
                                                  "stumbleType"),
                })

            verdict = compute_trend_verdict(history, tier=tier)
            per_call_rec = ev.per_call_rec or ""
            final_action, final_rationale = apply_matrix(per_call_rec, verdict)
            final_confidence = compute_final_confidence(verdict, per_call_rec, final_action)
            ev.final_action = final_action
            ev.final_confidence = final_confidence
            ev.trajectory = (verdict or {}).get("trajectory")


_field_cache: dict[tuple[str, date], dict] = {}


def _read_field(ticker: str, d: date, field: str):
    """Cached lookup of a single structured-score field for one eval file."""
    key = (ticker, d)
    if key not in _field_cache:
        f = EVALS_DIR / f"{ticker}_{d.isoformat()}.txt"
        if not f.exists():
            _field_cache[key] = {}
        else:
            _field_cache[key] = _parse_structured(f.read_text())
    return _field_cache[key].get(field)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    events = load_events_from_cache()
    print(f"Loaded {len(events)} events from {EVALS_DIR}")
    print(f"Tickers: {sorted({e.ticker for e in events})}")
    print(f"Date range: {min(e.call_date for e in events)} → "
          f"{max(e.call_date for e in events)}")
    # Spot-check one
    sample = events[0]
    print(f"\nSample: {sample.ticker} {sample.call_date}: "
          f"per_call={sample.per_call_rec} size={sample.recommended_size} "
          f"type={sample.type_classification}")
