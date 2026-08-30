#!/usr/bin/env python3
"""
sweep_funding_modes.py — task #77, funding mode sweep.

Implements the three funding modes from ALLOCATOR_OPERATING_MODEL.md §5
(no_reserve / cash_reserve / swap_funding) as a decide_fn wrapper around
decide_v3, plus reusable funding diagnostics, and runs the 8-cell grid plus
a retrospective ordering probe on cell 1.

In-memory only. No DB writes, no LLM calls. Signature of the wrapper
mirrors decide_v3's exactly (a prior session's instrumentation bug --
see diagnose-spwr-and-cash-instrumentation-out.md -- came from a **kwargs
wrapper silently dropping tier/is_first_call/driver_count).

Usage:
    cd analysis && python3 sweep_funding_modes.py
"""
from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.allocator_v3 import (
    decide as decide_v3, STARTER_PCT_SPECULATIVE, STARTER_PCT_ESTABLISHED,
)
from analysis.simulator.allocator_v2 import _type_cap, _build_sell_trades
from analysis.simulator.accounts import Trade
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
EXPECTED_NO_RESERVE = 141_837

CONFIDENCE_RANK = {"confident": 2, "advisory": 1, "unknown": 0, None: 0}


# ---------------------------------------------------------------------------
# Data loading + trend recompute (carried forward from clean-window-baseline-v2 /
# diagnose-spwr-and-cash-instrumentation, unchanged in method)
# ---------------------------------------------------------------------------

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


def load_events(dedupe: bool):
    events_full = load_call_events(tickers=ALL16, end_date=C, dedupe_same_day_calls=dedupe)
    type_fn = build_type_function()
    driver_fn = build_driver_count_function()
    tier_fn = build_tier_function(
        SCRIPT_DIR / "data" / "price_cache.json",
        SCRIPT_DIR / "data" / "fundamentals_cache.json",
    )
    extra_fields = fetch_extra_fields(ALL16, C)
    recompute_trend_layer(events_full, tier_fn, extra_fields)
    return events_full, type_fn, driver_fn, tier_fn


# ---------------------------------------------------------------------------
# Funding-mode decide_fn factory
# ---------------------------------------------------------------------------

def make_funding_decide_fn(
    funding_mode: str,           # "no_reserve" | "cash_reserve" | "swap_funding"
    reserve_pct: float = 0.0,    # for cash_reserve
    session_change_limit_pp: float | None = None,
    ticker_state: dict | None = None,   # shared, updated on every call
    funding_log: list | None = None,    # shared, appended per Add-shaped decision
    displacement_log: list | None = None,  # shared, appended per swap-funding sale
):
    ticker_state = ticker_state if ticker_state is not None else {}
    funding_log = funding_log if funding_log is not None else []
    displacement_log = displacement_log if displacement_log is not None else []

    def rank_key(ticker, state_entry, portfolio, prices_today, trade_date):
        """§4 ranking key: higher tuple = higher candidate priority (gets
        cash first). Used for candidates AND, sorted ascending, for donor
        selection (lowest-ranked = worst per this same key = best donor)."""
        if state_entry is None:
            return (0, -10**9, -1.0)
        conf = CONFIDENCE_RANK.get(state_entry.get("final_confidence"), 0)
        days_since = (trade_date - state_entry["call_date"]).days
        recency_score = -days_since  # fresher (smaller days_since) = higher
        price = prices_today.get(ticker)
        if price is None:
            gap = -1.0
        else:
            cap_pct = _type_cap(state_entry.get("type_classification"),
                                 state_entry.get("tier"), state_entry.get("driver_count"))
            rsp = state_entry.get("recommended_size_pct")
            target_pct = min(rsp, cap_pct) if rsp else cap_pct
            portfolio_value = portfolio.total_value(prices_today)
            target_dollars = (target_pct / 100.0) * portfolio_value if portfolio_value > 0 else 0
            current_dollars = portfolio.position_value(ticker, price)
            gap = ((target_dollars - current_dollars) / target_dollars
                   if target_dollars > 0 else -1.0)
        return (conf, recency_score, gap)

    def decide_fn(
        *,
        ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        portfolio_value_before = portfolio.total_value(prices_today)
        current_dollars_before = portfolio.position_value(ticker, day_price)
        had_position = portfolio.position_shares(ticker) > 1e-9

        trades = decide_v3(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call, driver_count=driver_count,
        )

        # Update ticker_state for every ticker we see, regardless of mode --
        # this is what makes donor ranking possible for OTHER tickers later.
        ticker_state[ticker] = {
            "final_action": final_action, "call_date": trade_date,
            "recommended_size_pct": recommended_size_pct,
            "type_classification": type_classification, "tier": tier,
            "driver_count": driver_count,
            "final_confidence": getattr(decide_fn, "_last_confidence", None),
        }

        # ---- Reconstruct intended vs. natural-actual dollars (diagnostics,
        # and the trigger for swap_funding) ----
        starter_fired = is_first_call and not had_position
        intended = 0.0
        if starter_fired:
            starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                            else STARTER_PCT_ESTABLISHED)
            if portfolio_value_before > 0:
                intended += (starter_pct / 100.0) * portfolio_value_before
        v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
        if v2_leg_applies and final_action == "Add" and portfolio_value_before > 0:
            cap_pct = _type_cap(type_classification, tier, driver_count)
            target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct
            target_dollars = (target_pct / 100.0) * portfolio_value_before
            delta = target_dollars - current_dollars_before
            if delta > 0:
                intended += delta

        if intended <= 1e-6:
            return trades  # not an Add-shaped decision; nothing to fund/log

        # Apply session_change_limit as a cap on intended (per §5's formula:
        # buy_$ = min(delta_$, cash_available, session_change_limit)).
        target_buy_dollars = intended
        if session_change_limit_pp is not None and portfolio_value_before > 0:
            limit_dollars = (session_change_limit_pp / 100.0) * portfolio_value_before
            target_buy_dollars = min(target_buy_dollars, limit_dollars)

        natural_buy_dollars = sum(t.shares * t.price for t in trades if t.side == "buy")

        if funding_mode == "no_reserve" and session_change_limit_pp is None:
            actual = natural_buy_dollars
            final_trades = trades
        elif funding_mode in ("no_reserve", "cash_reserve"):
            # Both are post-hoc caps on total buy $: no_reserve+limit caps at
            # target_buy_dollars (session limit only); cash_reserve additionally
            # caps at (current combined cash - reserve floor).
            cap = target_buy_dollars
            if funding_mode == "cash_reserve":
                combined_cash = sum(a.cash for a in portfolio.accounts.values())
                floor_dollars = (reserve_pct / 100.0) * portfolio_value_before
                spendable = max(0.0, combined_cash - floor_dollars)
                cap = min(cap, spendable)
            if natural_buy_dollars <= cap + 1e-6:
                actual = natural_buy_dollars
                final_trades = trades
            else:
                scale = cap / natural_buy_dollars if natural_buy_dollars > 0 else 0.0
                final_trades = []
                for t in trades:
                    if t.side == "buy":
                        scaled_shares = t.shares * scale
                        if scaled_shares > 1e-9:
                            final_trades.append(Trade(
                                account=t.account, ticker=t.ticker, side="buy",
                                shares=scaled_shares, price=t.price,
                                trade_date=t.trade_date, reason=t.reason + "-capped",
                            ))
                    else:
                        final_trades.append(t)
                actual = sum(t.shares * t.price for t in final_trades if t.side == "buy")
        elif funding_mode == "swap_funding":
            non_buy_trades = [t for t in trades if t.side != "buy"]
            shortfall = target_buy_dollars - natural_buy_dollars
            raised_by_account = {"tax_advantaged": 0.0, "taxable": 0.0}
            sell_trades = []
            if shortfall > 1e-6:
                # Eligible donors: currently held, not this ticker, latest
                # verdict in (Hold, Trim, Exit) -- never Add.
                donors = []
                for other, state in ticker_state.items():
                    if other == ticker:
                        continue
                    if portfolio.position_shares(other) <= 1e-9:
                        continue
                    if state.get("final_action") not in ("Hold", "Trim", "Exit"):
                        continue
                    donors.append(other)
                donors.sort(key=lambda t: rank_key(
                    t, ticker_state.get(t), portfolio, prices_today, trade_date))
                remaining = shortfall
                for donor in donors:
                    if remaining <= 1e-6:
                        break
                    donor_price = prices_today.get(donor)
                    if donor_price is None:
                        continue
                    donor_value = portfolio.position_value(donor, donor_price)
                    if donor_value <= 1e-6:
                        continue
                    max_trim_dollars = 0.25 * donor_value
                    raise_amount = min(max_trim_dollars, remaining)
                    shares_to_sell = raise_amount / donor_price
                    if shares_to_sell < 1e-9:
                        continue
                    donor_sells = _build_sell_trades(
                        donor, shares_to_sell, portfolio, donor_price,
                        trade_date, reason="swap-funding-displacement",
                    )
                    for st in donor_sells:
                        raised_by_account[st.account] += st.shares * st.price
                    sell_trades.extend(donor_sells)
                    actually_raised = sum(st.shares * st.price for st in donor_sells)
                    remaining -= actually_raised
                    displacement_log.append({
                        "date": trade_date, "donor": donor, "candidate": ticker,
                        "raised": actually_raised,
                    })

            # Rebuild the buy leg against (current cash + this-event's
            # donor proceeds), draining tax_advantaged then taxable -- same
            # order _decide_add uses. Sells above are returned FIRST in the
            # trade list, so by the time the simulator executes the buy
            # trades below, this projection is exactly what will be true.
            remaining_to_buy = target_buy_dollars
            new_buy_trades = []
            for account_name in ("tax_advantaged", "taxable"):
                if remaining_to_buy <= 1e-6:
                    break
                avail = portfolio.accounts[account_name].cash + raised_by_account[account_name]
                if avail <= 1e-6:
                    continue
                spend = min(remaining_to_buy, avail)
                shares = spend / day_price
                if shares < 1e-9:
                    continue
                new_buy_trades.append(Trade(
                    account=account_name, ticker=ticker, side="buy",
                    shares=shares, price=day_price, trade_date=trade_date,
                    reason="add-to-target-swap-funded",
                ))
                remaining_to_buy -= spend

            final_trades = sell_trades + non_buy_trades + new_buy_trades
            actual = sum(t.shares * t.price for t in new_buy_trades)
        else:
            raise ValueError(f"unknown funding_mode {funding_mode!r}")

        funding_log.append({
            "date": trade_date, "ticker": ticker,
            "intended_dollars": intended,
            "target_buy_dollars": target_buy_dollars,
            "actual_dollars": actual,
            "shortfall": max(target_buy_dollars - actual, 0.0),
            "starter_fired": starter_fired,
        })
        return final_trades

    return decide_fn


# ---------------------------------------------------------------------------
# We need final_confidence available to rank_key/ticker_state. It isn't a
# decide_fn kwarg (decide_v3 doesn't take it), so pull it from the event
# stream directly rather than the decide() call. Patched in by run_cell().
# ---------------------------------------------------------------------------

def run_cell(label, events_full, prices, type_fn, driver_fn, tier_fn,
             funding_mode, reserve_pct=0.0, session_change_limit_pp=None,
             reverse_order=False, seed=None):
    events = list(events_full)
    if reverse_order:
        events = list(reversed(events))  # simulator re-sorts by date via index_events_by_date;
        # same-day order comes from list order within index_events_by_date's
        # per-date bucket, which preserves input order -- reversing the
        # input list reverses same-day tie order without touching cross-day order.
    if seed is not None:
        rng = random.Random(seed)
        by_date: dict = {}
        for e in events:
            by_date.setdefault(e.call_date, []).append(e)
        events = []
        for d in sorted(by_date):
            bucket = by_date[d]
            rng.shuffle(bucket)
            events.extend(bucket)

    ticker_state: dict = {}
    funding_log: list = []
    displacement_log: list = []

    confidence_by_key = {(e.ticker, e.call_date): e.final_confidence for e in events_full}

    base_decide = make_funding_decide_fn(
        funding_mode, reserve_pct, session_change_limit_pp,
        ticker_state, funding_log, displacement_log,
    )

    def decide_fn(
        *,
        ticker, final_action, recommended_size_pct, type_classification,
        portfolio, day_price, trade_date, prices_today,
        tier=None, is_first_call=False, driver_count=None,
    ):
        # NOTE: signature must mirror decide_v3's exactly, same reason as
        # make_funding_decide_fn's inner decide_fn -- see the comment there.
        # This wrapper-of-a-wrapper is exactly the shape that bit the prior
        # session; caught immediately here by the standing $141,837 assertion.
        base_decide._last_confidence = confidence_by_key.get((ticker, trade_date))
        return base_decide(
            ticker=ticker, final_action=final_action,
            recommended_size_pct=recommended_size_pct,
            type_classification=type_classification,
            portfolio=portfolio, day_price=day_price,
            trade_date=trade_date, prices_today=prices_today,
            tier=tier, is_first_call=is_first_call, driver_count=driver_count,
        )

    r = run_simulation(
        start_date=START, end_date=C,
        taxable_cash=INITIAL / 2, tax_advantaged_cash=INITIAL / 2,
        universe_tickers=ALL16, prices=prices, events=events,
        decide_fn=decide_fn, type_for_ticker=type_fn,
        driver_count_for_ticker=driver_fn, tier_for_ticker=tier_fn,
    )
    s = compute_summary(r)

    n_days = len(r.daily_snapshots)
    below_1pct = sum(1 for snap in r.daily_snapshots
                      if snap.total_value > 0 and snap.cash_total / snap.total_value < 0.01)
    total = len(funding_log)
    fully_funded = sum(1 for f in funding_log if f["shortfall"] < 1.0)
    partial = sum(1 for f in funding_log if 1.0 <= f["shortfall"] and f["actual_dollars"] >= 1.0)
    unfunded = sum(1 for f in funding_log if f["actual_dollars"] < 1.0 and f["intended_dollars"] >= 1.0)
    total_shortfall = sum(f["shortfall"] for f in funding_log)
    distinct_tickers = len({t for acc in r.portfolio.accounts.values() for t in acc.lots
                             if any(l.shares > 1e-9 for l in acc.lots[t])})
    displacement_gains = sum(
        rs.realized_gain for rs in r.portfolio.realized_sales
        if rs.ticker in {d["donor"] for d in displacement_log}
    )

    return {
        "label": label, "final_value": s.final_portfolio_value,
        "max_dd": s.max_drawdown_pct, "n_days": n_days,
        "below_1pct_days": below_1pct, "pct_below_1pct": 100 * below_1pct / n_days if n_days else 0,
        "add_total": total, "fully_funded": fully_funded, "partial": partial,
        "unfunded": unfunded, "total_shortfall": total_shortfall,
        "distinct_tickers": distinct_tickers,
        "n_displacements": len(displacement_log),
        "displacement_realized_gain": displacement_gains,
        "displacement_log": displacement_log,
    }


def print_cell(c):
    print(f"\n--- {c['label']} ---")
    print(f"final=${c['final_value']:,.0f}  maxDD={c['max_dd']*100:.1f}%")
    print(f"cash<1% days: {c['below_1pct_days']}/{c['n_days']} ({c['pct_below_1pct']:.1f}%)")
    print(f"Adds: total={c['add_total']}  fully_funded={c['fully_funded']}"
          f" ({100*c['fully_funded']/c['add_total']:.1f}%)  "
          f"partial={c['partial']} ({100*c['partial']/c['add_total']:.1f}%)  "
          f"unfunded={c['unfunded']} ({100*c['unfunded']/c['add_total']:.1f}%)")
    print(f"cumulative shortfall: ${c['total_shortfall']:,.0f}")
    print(f"distinct tickers held at window end: {c['distinct_tickers']}")
    if c["n_displacements"]:
        print(f"displacements: {c['n_displacements']}  "
              f"realized gain from displacement: ${c['displacement_realized_gain']:,.0f}")


def main() -> int:
    print(f"Clean window: {START} -> {C}\n")

    events_nodedup, type_fn, driver_fn, tier_fn = load_events(dedupe=False)
    events_dedup, _, _, _ = load_events(dedupe=True)
    prices = PriceLookup.from_cache()

    w_nodedup = [e for e in events_nodedup if START <= e.call_date <= C]
    w_dedup = [e for e in events_dedup if START <= e.call_date <= C]
    print(f"Window event count, dedup OFF: {len(w_nodedup)}")
    print(f"Window event count, dedup ON:  {len(w_dedup)} (expect 147)")

    import psycopg2, psycopg2.extras, os
    from dotenv import load_dotenv
    load_dotenv(SCRIPT_DIR.parent / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tk.symbol, t."callDate"::date, count(*)
            FROM "Transcript" t JOIN "Ticker" tk ON tk.id=t."tickerId"
            GROUP BY tk.symbol, t."callDate" HAVING count(*) > 1
        """)
        dupes = cur.fetchall()
    conn.close()
    print(f"Other duplicated (ticker, callDate) pairs in the whole DB: "
          f"{[d for d in dupes if d[0] != 'FSLR' or d[1] != date(2024,2,27)]}")
    print(f"(All duplicates found, DB-wide: {dupes})")

    cells = []

    print("\n=== Cell 1: no_reserve, dedup OFF, no limit (control) ===")
    c1 = run_cell("1: no_reserve dedup=off", events_nodedup, prices, type_fn, driver_fn, tier_fn,
                  "no_reserve")
    print_cell(c1)
    assert abs(c1["final_value"] - EXPECTED_NO_RESERVE) < 1.0, (
        f"STANDING ASSERTION FAILED: {c1['final_value']} != {EXPECTED_NO_RESERVE}")
    print(f"\nAssertion PASSED: cell 1 reproduces ${EXPECTED_NO_RESERVE:,} exactly.")
    cells.append(c1)

    print("\n=== Cell 2: no_reserve, dedup ON, no limit ===")
    c2 = run_cell("2: no_reserve dedup=on", events_dedup, prices, type_fn, driver_fn, tier_fn,
                  "no_reserve")
    print_cell(c2)
    cells.append(c2)

    for pct in (5, 10, 20):
        print(f"\n=== Cell: cash_reserve {pct}% ===")
        c = run_cell(f"cash_reserve {pct}%", events_dedup, prices, type_fn, driver_fn, tier_fn,
                     "cash_reserve", reserve_pct=pct)
        print_cell(c)
        cells.append(c)

    print("\n=== Cell 6: swap_funding, no limit ===")
    c6 = run_cell("6: swap_funding", events_dedup, prices, type_fn, driver_fn, tier_fn,
                  "swap_funding")
    print_cell(c6)
    cells.append(c6)

    print("\n=== Cell 7: swap_funding, 10pp session limit ===")
    c7 = run_cell("7: swap_funding + 10pp limit", events_dedup, prices, type_fn, driver_fn, tier_fn,
                  "swap_funding", session_change_limit_pp=10.0)
    print_cell(c7)
    cells.append(c7)

    print("\n=== Cell 8: no_reserve, 10pp session limit ===")
    c8 = run_cell("8: no_reserve + 10pp limit", events_dedup, prices, type_fn, driver_fn, tier_fn,
                  "no_reserve", session_change_limit_pp=10.0)
    print_cell(c8)
    cells.append(c8)

    print("\n=== Displacement log (cell 6, swap_funding no limit) ===")
    for d in c6["displacement_log"]:
        print(f"  {d['date']}  donor={d['donor']:6}  candidate={d['candidate']:6}  "
              f"raised=${d['raised']:,.0f}")

    print("\n=== Step 3: retrospective ordering probe (cell 1 only) ===")
    probe_results = [c1["final_value"]]
    print(f"forward (as-loaded): ${c1['final_value']:,.0f}")
    c_rev = run_cell("1-reversed", events_nodedup, prices, type_fn, driver_fn, tier_fn,
                      "no_reserve", reverse_order=True)
    print(f"reversed same-day order: ${c_rev['final_value']:,.0f}")
    probe_results.append(c_rev["final_value"])
    for seed in (1, 2, 3):
        c_seed = run_cell(f"1-seed{seed}", events_nodedup, prices, type_fn, driver_fn, tier_fn,
                           "no_reserve", seed=seed)
        print(f"seed {seed}: ${c_seed['final_value']:,.0f}")
        probe_results.append(c_seed["final_value"])

    print(f"\nRetrospective ordering spread: ${min(probe_results):,.0f} - ${max(probe_results):,.0f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
