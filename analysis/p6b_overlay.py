#!/usr/bin/env python3
"""
p6b_overlay.py -- prompts/P6B-end-to-end-check.md section 4. NEW module that FEEDS the harness; it modifies nothing in it.

Takes the event list from sweep_cadence_and_session_model.load_events_dedup_on() and returns COPIES with exactly the fields
of the section-4 table replaced:

  per_call_rec      = mapping of B's score (<= -2 Trim, >= +cut Add, else Hold)   [A0: v6's own archived per_call_rec]
  final_action      = per_call_rec           (trend layer bypassed, not simulated)
  final_confidence  = "confident"
  recommended_size  = None                   (BACKTEST_SIMULATOR.md fallback: target = tier cap)
  trajectory        = None

type / tier / driver_count are looked up by the harness from analyst-independent classifiers and are untouched. thesis_health
is left as loaded: it is read only by recompute_trend_layer (which is not called on overlaid copies), never by the allocator.
Events with no B score are dropped from that cell and COUNTED; more than 3% missing raises (prompt section 4).
"""
from dataclasses import replace

THRESHOLDS = {"trim_lte": -2, "add_gte_primary": 3, "add_gte_sensitivity": 2}
MAX_MISSING_FRAC = 0.03


def map_score(score, add_cut=3):
    if score is None:
        return None
    return "Trim" if score <= THRESHOLDS["trim_lte"] else "Add" if score >= add_cut else "Hold"


def _bypass(ev, rec):
    return replace(ev, per_call_rec=rec, final_action=rec, final_confidence="confident",
                   recommended_size=None, trajectory=None)


def overlay_a0(events, rec_override=None):
    """v6 per_call_rec only, through the same overlay B gets. rec_override: {(ticker, call_date): rec} for the noise cell."""
    rec_override = rec_override or {}
    return [_bypass(e, rec_override.get((e.ticker, e.call_date), e.per_call_rec)) for e in events]


def overlay_b(events, scores, add_cut=3):
    """scores: {(ticker, call_date): int}. Returns (events, dropped_keys)."""
    out, dropped = [], []
    for e in events:
        rec = map_score(scores.get((e.ticker, e.call_date)), add_cut)
        if rec is None:
            dropped.append((e.ticker, e.call_date))
            continue
        out.append(_bypass(e, rec))
    if events and len(dropped) / len(events) > MAX_MISSING_FRAC:
        raise SystemExit(f"STOP: {len(dropped)} of {len(events)} events have no B score ({100*len(dropped)/len(events):.1f}% > 3%)")
    return out, dropped
