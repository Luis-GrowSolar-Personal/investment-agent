#!/usr/bin/env python3
"""
run_clean_window_baseline.py — task #77, Option A (clean-window baseline),
v2: full pre-window history fed to the trend recompute, per
wrap-ups/clean-window-baseline-v2-out.md.

v1 of this script (see clean-window-baseline-out.md) truncated each ticker's
history to the simulation window before recomputing the trend layer, which
starved compute_trend_verdict of context. This version loads full history
through the window end, recomputes over that, then lets run_simulation's own
date filter (simulator.py: `events = [e for e in events if start_date <=
e.call_date <= end_date]`) restrict to the actual trading window.

In-memory only. No DB writes, no LLM calls.

Usage:
    cd analysis && python3 run_clean_window_baseline.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator import decide as decide_v1
from analysis.simulator.allocator_v2 import decide as decide_v2
from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import PriceLookup, load_call_events
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function, compute_trend_verdict, apply_matrix, compute_final_confidence
from type_classifier import build_type_function, build_driver_count_function

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ALL15 = [t for t in ALL16 if t != "SPWR"]

START = date(2022, 1, 1)
C = date(2024, 6, 12)
INITIAL = 100_000


def equal_weight_value(tickers, start_date, end_date, capital, prices):
    per_ticker = capital / len(tickers)
    holdings = {}
    for t in tickers:
        p = prices.price_on(t, start_date, max_lookback_days=10)
        if p and p > 0:
            holdings[t] = per_ticker / p
    total = 0.0
    for t, shares in holdings.items():
        ep = prices.price_on(t, end_date, max_lookback_days=120)
        if ep:
            total += shares * ep
    return total


def fetch_extra_fields(all16, end):
    """freshMoneyAllocation / credibilityDelta / mitigationCapabilityTrackRecord /
    stumbleType per (ticker, call_date), v6 window, no start bound -- full
    history through `end`. Read-only."""
    import psycopg2
    import psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR.parent / ".env")
    db_url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                       a."freshMoneyAllocation" AS fresh_money_allocation,
                       a."credibilityDelta" AS credibility_delta,
                       a."mitigationCapabilityTrackRecord" AS mitigation_track_record,
                       a."stumbleType" AS stumble_type
                FROM "Analysis" a
                JOIN "Transcript" t ON a."transcriptId" = t.id
                JOIN "Ticker" tk ON t."tickerId" = tk.id
                JOIN (
                    SELECT a2."transcriptId", MAX(a2."createdAt") AS latest
                    FROM "Analysis" a2
                    GROUP BY a2."transcriptId"
                ) latest ON latest."transcriptId" = a."transcriptId"
                        AND latest.latest = a."createdAt"
                WHERE tk.symbol = ANY(%s)
                  AND t."callDate" <= %s
                  AND a."createdAt" >= %s AND a."createdAt" < %s
            """, (all16, end, "2026-05-02 12:33:23-04", "2026-06-27 16:26:16-04"))
            rows = cur.fetchall()
    finally:
        conn.close()
    return {(r["ticker"], r["call_date"]): r for r in rows}


def recompute_trend_layer(events, tier_for_ticker, extra_fields):
    """Mirrors data_from_cache.py::attach_trend_verdicts() over FULL
    per-ticker history. Mutates events in place."""
    by_ticker: dict[str, list] = {}
    for e in events:
        by_ticker.setdefault(e.ticker, []).append(e)

    for ticker, ticker_events in by_ticker.items():
        ticker_events.sort(key=lambda e: e.call_date)
        tier = (tier_for_ticker(ticker) if tier_for_ticker else "established") or "established"

        for i, ev in enumerate(ticker_events):
            history = []
            for prior in ticker_events[: i + 1]:
                extra = extra_fields.get((prior.ticker, prior.call_date), {})
                history.append({
                    "thesis_health": prior.thesis_health,
                    "recommendation": prior.per_call_rec,
                    "recommended_size": prior.recommended_size,
                    "fresh_money_allocation": extra.get("fresh_money_allocation"),
                    "credibility_delta": extra.get("credibility_delta"),
                    "mitigation_track_record": extra.get("mitigation_track_record"),
                    "stumble_type": extra.get("stumble_type"),
                })

            verdict = compute_trend_verdict(history, tier=tier)
            per_call_rec = ev.per_call_rec or ""
            final_action, _rationale = apply_matrix(per_call_rec, verdict)
            final_confidence = compute_final_confidence(verdict, per_call_rec, final_action)

            ev.final_action = final_action
            ev.final_confidence = final_confidence
            ev.trajectory = (verdict or {}).get("trajectory")


def run_universe(label, universe, events, prices, type_fn, driver_fn, tier_fn):
    results = {}
    for name, fn in [("v1", decide_v1), ("v2", decide_v2), ("v3", decide_v3)]:
        kwargs = dict(
            start_date=START, end_date=C,
            taxable_cash=INITIAL / 2, tax_advantaged_cash=INITIAL / 2,
            universe_tickers=universe, prices=prices, events=events,
            decide_fn=fn, type_for_ticker=type_fn,
            driver_count_for_ticker=driver_fn,
        )
        if name != "v1":
            kwargs["tier_for_ticker"] = tier_fn
        r = run_simulation(**kwargs)
        results[name] = compute_summary(r)
    return results


def main() -> int:
    print(f"Clean window: {START} -> {C}\n")

    # Step 1: load FULL history (no start_date) through C, so each ticker's
    # trend recompute has its true prior calls available.
    events_full = load_call_events(tickers=ALL16, end_date=C)
    print(f"Full-history events loaded (end_date={C}, no start_date): {len(events_full)}")

    events_window = [e for e in events_full if START <= e.call_date <= C]
    print(f"Of those, events that survive into the simulation window "
          f"[{START}, {C}]: {len(events_window)}")
    print(f"Difference (pre-window history available to the recompute only): "
          f"{len(events_full) - len(events_window)}")

    from collections import Counter
    per_ticker = Counter(e.ticker for e in events_window)
    print("\nPer-ticker window coverage (Gate 1, carried forward):")
    all_present = True
    for t in ALL16:
        n = per_ticker.get(t, 0)
        print(f"  {t:6} {n}")
        if n == 0:
            all_present = False
    if not all_present:
        print("FATAL: at least one ALL16 ticker has zero events in the window.")
        return 1

    print(f"\nGate 2 (carried forward): window event count == 148 -> "
          f"{'PASS' if len(events_window) == 148 else 'FAIL, got ' + str(len(events_window))}")

    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )

    missing_type = [t for t in ALL16 if type_fn(t) not in ("A", "B")]
    if missing_type:
        print(f"FATAL: type_for_ticker missing for: {missing_type}")
        return 1
    print(f"Gate 4 (carried forward): type_for_ticker resolves for all {len(ALL16)} tickers.")

    # Snapshot stored values (window slice) BEFORE mutating via recompute.
    stored_by_key = {(e.ticker, e.call_date): (e.final_action, e.trajectory) for e in events_window}

    extra_fields = fetch_extra_fields(ALL16, C)
    print(f"\nFetched extra fields for {len(extra_fields)} (ticker, call_date) pairs "
          f"(full history through {C})")

    recompute_trend_layer(events_full, tier_fn, extra_fields)

    # Step 2, check 1: null trajectory count, window slice only.
    n_null_traj_after = sum(1 for e in events_window if e.trajectory is None)
    print(f"\nStep 2, check 1 -- null trajectory in window after recompute "
          f"(full history): {n_null_traj_after}/{len(events_window)} "
          f"(v1 truncated-history run: 31/148; stored baseline: ~3)")

    if n_null_traj_after > 10:
        print(f"\nSTOP: null trajectory ({n_null_traj_after}) has not returned "
              f"to roughly the stored level (~3). The history-scoping fix did "
              f"not take. Not proceeding.")
        return 1

    # Step 2, check 2: recomputed vs stored final_action, window slice.
    disagreements = []
    for e in events_window:
        stored_action, stored_traj = stored_by_key[(e.ticker, e.call_date)]
        if e.final_action != stored_action:
            disagreements.append((e.ticker, e.call_date, stored_action, e.final_action))

    agreement_rate = 100 * (len(events_window) - len(disagreements)) / len(events_window)
    print(f"\nStep 2, check 2 -- recomputed vs stored final_action agreement: "
          f"{agreement_rate:.1f}% ({len(events_window) - len(disagreements)}/{len(events_window)})")
    if disagreements:
        print("Disagreements (ticker, call_date, stored, recomputed):")
        for d in disagreements:
            print(f"  {d[0]:6} {d[1]}  stored={d[2]!r:10}  recomputed={d[3]!r}")

    print("\nProceeding to Step 3 (identity validation) and Step 4 (simulation).")

    # --- Step 3: ticker identity validation -----------------------------
    prices = PriceLookup.from_cache()
    print("\n--- Step 3: ticker identity validation ---")
    print(f"{'TICKER':6}  {'PRICE FIRST':12}  {'TRANSCRIPT FIRST':16}")
    for t in ALL16:
        pf = prices.first_date(t)
        tx_dates = sorted(e.call_date for e in events_full if e.ticker == t)
        tf = tx_dates[0] if tx_dates else None
        print(f"  {t:6}  {str(pf):12}  {str(tf):16}")

    # --- Step 4: simulation ----------------------------------------------
    print("\n--- Step 4: v1/v2/v3 + benchmarks, ALL16 ---")
    r16 = run_universe("ALL16", ALL16, events_full, prices, type_fn, driver_fn, tier_fn)
    for name in ("v1", "v2", "v3"):
        s = r16[name]
        print(f"{name}: final=${s.final_portfolio_value:,.0f}  maxDD={s.max_drawdown_pct*100:.1f}%")

    print()
    for etf, val in r16["v3"].baseline_finals.items():
        dd = r16["v3"].baseline_drawdowns.get(etf, 0)
        print(f"{etf}: final=${val:,.0f}  maxDD={dd*100:.1f}%")
    ew16 = equal_weight_value(ALL16, START, C, INITIAL, prices)
    print(f"Equal-weight (ALL16): final=${ew16:,.0f}")

    v1v, v2v, v3v = (r16[k].final_portfolio_value for k in ("v1", "v2", "v3"))
    ordering_holds = v3v >= v2v >= v1v
    print(f"\nOrdering v3>=v2>=v1: {v3v:,.0f} >= {v2v:,.0f} >= {v1v:,.0f} -> "
          f"{'HOLDS' if ordering_holds else 'DOES NOT HOLD'}")

    print("\n--- Step 4b: v3, ALL15 (SPWR excluded) ---")
    events_full_15 = [e for e in events_full if e.ticker != "SPWR"]
    r15 = run_universe("ALL15", ALL15, events_full_15, prices, type_fn, driver_fn, tier_fn)
    s15 = r15["v3"]
    print(f"v3 (ALL15): final=${s15.final_portfolio_value:,.0f}  maxDD={s15.max_drawdown_pct*100:.1f}%")
    print(f"v3 (ALL16) - v3 (ALL15) final value delta: "
          f"${r16['v3'].final_portfolio_value - s15.final_portfolio_value:,.0f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
