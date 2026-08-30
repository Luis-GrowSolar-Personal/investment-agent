#!/usr/bin/env python3
"""
diagnose_spwr_and_cash.py — task #77, SPWR root cause + cash instrumentation.

Wraps decide_v3 to log, per Add-shaped decision (including first-call
starters), the intended target dollars vs the dollars actually funded --
without changing what gets returned or executed. Reuses the simulator's own
functions (_type_cap, STARTER_PCT_*) rather than re-deriving constants.

In-memory only. No DB writes, no LLM calls, no behavior change to any
allocation decision (the wrapped decide_fn returns exactly what decide_v3
would have returned).

Usage:
    cd analysis && python3 diagnose_spwr_and_cash.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import (
    decide as decide_v3, STARTER_PCT_SPECULATIVE, STARTER_PCT_ESTABLISHED,
)
from analysis.simulator.allocator_v2 import _type_cap
from analysis.simulator.data import PriceLookup, load_call_events
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from trend_analyst import build_tier_function, compute_trend_verdict, apply_matrix, compute_final_confidence
from type_classifier import build_type_function, build_driver_count_function

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]

START = date(2022, 1, 1)
C = date(2024, 6, 12)
INITIAL = 100_000
EXPECTED_ALL16_V3 = 141_837


def fetch_extra_fields(all16, end):
    import os
    import psycopg2
    import psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR.parent / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
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
                    FROM "Analysis" a2 GROUP BY a2."transcriptId"
                ) latest ON latest."transcriptId" = a."transcriptId"
                        AND latest.latest = a."createdAt"
                WHERE tk.symbol = ANY(%s) AND t."callDate" <= %s
                  AND a."createdAt" >= %s AND a."createdAt" < %s
            """, (all16, end, "2026-05-02 12:33:23-04", "2026-06-27 16:26:16-04"))
            rows = cur.fetchall()
    finally:
        conn.close()
    return {(r["ticker"], r["call_date"]): r for r in rows}


def recompute_trend_layer(events, tier_for_ticker, extra_fields):
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
            final_action, _r = apply_matrix(per_call_rec, verdict)
            ev.final_action = final_action
            ev.final_confidence = compute_final_confidence(verdict, per_call_rec, final_action)
            ev.trajectory = (verdict or {}).get("trajectory")


def make_instrumented_decide(funding_log, event_log):
    """Wraps decide_v3. Returns EXACTLY what decide_v3 returns -- no
    modification -- and additionally records, for Add-shaped decisions,
    the intended target dollars (recomputed via the allocator's own
    _type_cap / starter-pct constants) vs. dollars actually bought."""

    def instrumented(
        *,
        ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        # NOTE: this signature must mirror decide_v3's exactly -- simulator.py
        # introspects decide_fn's signature (inspect.signature) to decide
        # whether to pass tier/is_first_call/driver_count at all. A **kwargs
        # wrapper erases those parameter names and silently drops them,
        # which was caught here by the $141,837 assertion failing loudly.
        portfolio_value = portfolio.total_value(prices_today)
        current_dollars = portfolio.position_value(ticker, day_price)
        had_position = portfolio.position_shares(ticker) > 1e-9

        trades = decide_v3(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call, driver_count=driver_count,
        )

        event_log.append({
            "date": trade_date, "ticker": ticker, "final_action": final_action,
            "is_first_call": is_first_call, "n_trades": len(trades),
        })

        # Reconstruct intended dollars, mirroring the actual code paths.
        intended = 0.0
        starter_fired = is_first_call and not had_position
        if starter_fired:
            starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                            else STARTER_PCT_ESTABLISHED)
            if portfolio_value > 0:
                intended += (starter_pct / 100.0) * portfolio_value

        v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
        if v2_leg_applies and final_action == "Add" and portfolio_value > 0:
            cap_pct = _type_cap(type_classification, tier, driver_count)
            target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct
            target_dollars = (target_pct / 100.0) * portfolio_value
            # v2's own view of current_dollars is the pre-call portfolio,
            # same as what we captured above -- it does not see the
            # starter trade (still unexecuted at decide()-call time; this
            # mirrors the actual §11 defect, not our error).
            delta = target_dollars - current_dollars
            if delta > 0:
                intended += delta

        if intended > 1e-6:
            actual = sum(t.shares * t.price for t in trades if t.side == "buy")
            funding_log.append({
                "date": trade_date, "ticker": ticker,
                "intended_dollars": intended, "actual_dollars": actual,
                "shortfall": max(intended - actual, 0.0),
                "starter_fired": starter_fired,
            })

        return trades

    return instrumented


def main() -> int:
    print(f"Clean window: {START} -> {C}\n")

    events_full = load_call_events(tickers=ALL16, end_date=C)
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    extra_fields = fetch_extra_fields(ALL16, C)
    recompute_trend_layer(events_full, tier_fn, extra_fields)

    events_window = [e for e in events_full if START <= e.call_date <= C]
    print(f"ALL16: {len(events_window)} events in window")
    events_window_15 = [e for e in events_window if e.ticker != "SPWR"]
    print(f"ALL15 (SPWR excluded): {len(events_window_15)} events in window\n")

    prices = PriceLookup.from_cache()

    # ---- Step 1: SPWR root cause ----
    funding_log, event_log = [], []
    instrumented = make_instrumented_decide(funding_log, event_log)

    r16 = run_simulation(
        start_date=START, end_date=C,
        taxable_cash=INITIAL / 2, tax_advantaged_cash=INITIAL / 2,
        universe_tickers=ALL16, prices=prices, events=events_full,
        decide_fn=instrumented, type_for_ticker=type_fn,
        driver_count_for_ticker=driver_fn, tier_for_ticker=tier_fn,
    )
    s16 = compute_summary(r16)
    print(f"ALL16 v3 (instrumented): final=${s16.final_portfolio_value:,.0f}  "
          f"(expected ${EXPECTED_ALL16_V3:,.0f})")
    assert abs(s16.final_portfolio_value - EXPECTED_ALL16_V3) < 1.0, (
        "INSTRUMENTATION CHANGED BEHAVIOR -- final value moved from expected")
    print("Assertion PASSED: instrumented run reproduces the uninstrumented result exactly.\n")

    print("=== Step 1: SPWR root cause ===")
    spwr_events = [e for e in event_log if e["ticker"] == "SPWR"]
    print(f"SPWR events processed by decide(): {len(spwr_events)}")
    for e in spwr_events:
        print(f"  {e}")

    spwr_skipped = [s for s in r16.skipped_events if s[1] == "SPWR"]
    print(f"SPWR entries in skipped_events: {len(spwr_skipped)}")
    for s in spwr_skipped:
        print(f"  {s}")

    spwr_shares = r16.portfolio.position_shares("SPWR")
    spwr_price_end = prices.price_on("SPWR", C)
    spwr_value = r16.portfolio.position_value("SPWR", spwr_price_end) if spwr_price_end else None
    print(f"SPWR shares at window end ({C}): {spwr_shares}")
    print(f"SPWR position value at window end: {spwr_value}")

    print("\nCash balances around 2024-05-02:")
    target_dates = [date(2024, 5, 1) + timedelta(days=i) for i in range(-2, 5)]
    by_date = {snap.date: snap for snap in r16.daily_snapshots}
    for d in target_dates:
        snap = by_date.get(d)
        if snap:
            print(f"  {d}: taxable=${snap.cash_taxable:,.2f}  "
                  f"tax_adv=${snap.cash_tax_advantaged:,.2f}  "
                  f"combined=${snap.cash_total:,.2f}")

    spwr_funding = [f for f in funding_log if f["ticker"] == "SPWR"]
    print(f"\nSPWR funding_log entries: {len(spwr_funding)}")
    for f in spwr_funding:
        print(f"  {f}")

    # ---- Prove ALL15 actually excludes SPWR ----
    funding_log_15, event_log_15 = [], []
    instrumented_15 = make_instrumented_decide(funding_log_15, event_log_15)
    all15_universe = [t for t in ALL16 if t != "SPWR"]
    events_full_15 = [e for e in events_full if e.ticker != "SPWR"]
    r15 = run_simulation(
        start_date=START, end_date=C,
        taxable_cash=INITIAL / 2, tax_advantaged_cash=INITIAL / 2,
        universe_tickers=all15_universe, prices=prices, events=events_full_15,
        decide_fn=instrumented_15, type_for_ticker=type_fn,
        driver_count_for_ticker=driver_fn, tier_for_ticker=tier_fn,
    )
    s15 = compute_summary(r15)
    print(f"\nALL16 universe list ({len(ALL16)}): {ALL16}")
    print(f"ALL16 event count (window): {len(events_window)}")
    print(f"ALL15 universe list ({len(all15_universe)}): {all15_universe}")
    print(f"ALL15 event count (window): {len(events_window_15)}")
    print(f"ALL16 v3 final: ${s16.final_portfolio_value:,.2f}")
    print(f"ALL15 v3 final: ${s15.final_portfolio_value:,.2f}")
    print(f"Delta: ${s16.final_portfolio_value - s15.final_portfolio_value:,.4f}")

    # ---- Step 2: cash over the whole run ----
    print("\n=== Step 2: cash over the whole run (ALL16 v3) ===")
    snaps = r16.daily_snapshots
    below_1pct_days = sum(1 for s in snaps if s.total_value > 0 and s.cash_total / s.total_value < 0.01)
    pct_below = 100 * below_1pct_days / len(snaps)
    print(f"Trading days: {len(snaps)}")
    print(f"Days with combined cash < 1% of portfolio value: {below_1pct_days} ({pct_below:.1f}%)")

    first_floor_date = None
    for i, s in enumerate(snaps):
        if s.total_value > 0 and s.cash_total / s.total_value < 0.01:
            # check it stays there for the rest of the run (or at least doesn't
            # recover above 1% for a long stretch)
            rest = snaps[i:]
            stays = sum(1 for r in rest if r.total_value > 0 and r.cash_total / r.total_value < 0.01)
            if stays / len(rest) > 0.9:
                first_floor_date = s.date
                break
    print(f"First date cash hits the floor and stays there (>90% of remaining days): {first_floor_date}")

    ratios = [s.cash_total / s.total_value for s in snaps if s.total_value > 0]
    print(f"Cash as % of portfolio value -- min: {min(ratios)*100:.2f}%  "
          f"median: {sorted(ratios)[len(ratios)//2]*100:.2f}%  max: {max(ratios)*100:.2f}%")

    # ---- Step 3: rationing ----
    print("\n=== Step 3: allocator rationing (ALL16 v3) ===")
    fully_funded = [f for f in funding_log if f["shortfall"] < 1.0]
    cash_limited = [f for f in funding_log if 1.0 <= f["shortfall"] < f["intended_dollars"] - 1.0]
    unfunded = [f for f in funding_log if f["actual_dollars"] < 1.0 and f["intended_dollars"] >= 1.0]
    # cash_limited above double counts unfunded (actual=0 has shortfall==intended);
    # redefine cleanly:
    fully_funded = [f for f in funding_log if f["shortfall"] < 1.0]
    partially_or_unfunded = [f for f in funding_log if f["shortfall"] >= 1.0]
    unfunded_only = [f for f in partially_or_unfunded if f["actual_dollars"] < 1.0]
    partial_only = [f for f in partially_or_unfunded if f["actual_dollars"] >= 1.0]

    total = len(funding_log)
    print(f"Total Add-shaped decisions (incl. first-call starters) with intended $>0: {total}")
    print(f"  Fully funded:      {len(fully_funded)} ({100*len(fully_funded)/total:.1f}%)")
    print(f"  Cash-limited (partial): {len(partial_only)} ({100*len(partial_only)/total:.1f}%)")
    print(f"  Entirely unfunded: {len(unfunded_only)} ({100*len(unfunded_only)/total:.1f}%)")

    total_shortfall = sum(f["shortfall"] for f in funding_log)
    print(f"\nTotal dollar shortfall (sum of intended - actual across all "
          f"cash-limited/unfunded): ${total_shortfall:,.2f}")

    print("\nUnfunded / partially-funded list (date, ticker, intended $, actual $, shortfall $):")
    for f in sorted(partially_or_unfunded, key=lambda x: x["date"]):
        print(f"  {f['date']}  {f['ticker']:6}  intended=${f['intended_dollars']:>10,.0f}  "
              f"actual=${f['actual_dollars']:>10,.0f}  shortfall=${f['shortfall']:>10,.0f}"
              f"{'  [starter]' if f['starter_fired'] else ''}")

    if partially_or_unfunded:
        dates = [f["date"] for f in partially_or_unfunded]
        span_start, span_end = min(dates), max(dates)
        early_cut = START + (C - START) // 3
        late_cut = START + 2 * (C - START) // 3
        n_early = sum(1 for d in dates if d <= early_cut)
        n_mid = sum(1 for d in dates if early_cut < d <= late_cut)
        n_late = sum(1 for d in dates if d > late_cut)
        print(f"\nShortfall timing -- window thirds: early(<= {early_cut})={n_early}  "
              f"mid={n_mid}  late(> {late_cut})={n_late}")
        print(f"First shortfall event: {span_start}   Last shortfall event: {span_end}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
