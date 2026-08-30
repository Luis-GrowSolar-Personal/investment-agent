"""
simulator.py — Main backtest loop.

Walks day-by-day from `start_date` to `end_date`. On each day:
  1. Process any earnings calls on this date (allocator → trades → portfolio)
  2. If December 31, run year-end tax
  3. Mark portfolio + baselines to market and record the snapshot

Returns a SimulationResult with the daily time series, transaction log,
and summary metrics for the report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .accounts import Portfolio, Trade, InsufficientCash, InsufficientShares
from .allocator import decide as decide_v1
from .baseline import BaselineResult, initialize_baselines
from .data import CallEvent, PriceLookup, index_events_by_date, load_call_events
from .tax import YearEndTax, compute_year_end_tax


@dataclass
class DailySnapshot:
    """One day's mark-to-market record."""
    date: date
    total_value: float
    taxable_value: float
    tax_advantaged_value: float
    cash_total: float
    n_positions: int   # distinct tickers with shares > 0
    cash_taxable: float = 0.0          # diagnostic only, see ALLOCATOR_OPERATING_MODEL.md
    cash_tax_advantaged: float = 0.0   # diagnostic only, see ALLOCATOR_OPERATING_MODEL.md
    baseline_values: dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Everything the report needs."""
    start_date: date
    end_date: date
    initial_capital: float
    daily_snapshots: list[DailySnapshot]
    portfolio: Portfolio   # final state (positions, lots, transaction_log, realized_sales)
    baselines: dict[str, BaselineResult]
    year_end_taxes: list[YearEndTax]
    universe_tickers: list[str]
    skipped_events: list[tuple[date, str, str]]  # (date, ticker, reason)


def run_simulation(
    *,
    start_date: date,
    end_date: date,
    taxable_cash: float,
    tax_advantaged_cash: float,
    universe_tickers: Optional[list[str]] = None,
    prices: Optional[PriceLookup] = None,
    events: Optional[list[CallEvent]] = None,
    verbose: bool = False,
    decide_fn=None,        # allocator.decide function; defaults to v1
    tier_for_ticker=None,  # ticker → 'speculative'|'established'; required for v2 allocator
    type_for_ticker=None,  # ticker → 'A'|'B'|None; overrides event.type_classification when set
    driver_count_for_ticker=None,  # ticker → int|None; enables variable Type B cap (40-60%) in allocator_v2/v3/v4
) -> SimulationResult:
    """Run a single backtest scenario.

    `universe_tickers`: if None, includes every ticker that appears in
    the loaded events. Pass a list to restrict to a subset.

    `prices` / `events`: pass pre-loaded if you want to skip the DB/cache
    fetch (useful for testing). If omitted, loads from the live sources.
    """
    if prices is None:
        prices = PriceLookup.from_cache()
    if events is None:
        events = load_call_events(
            tickers=universe_tickers,
            start_date=start_date,
            end_date=end_date,
        )
    if decide_fn is None:
        decide_fn = decide_v1

    # Filter events to the requested window and universe
    events = [
        e for e in events
        if start_date <= e.call_date <= end_date
        and (universe_tickers is None or e.ticker in universe_tickers)
    ]
    events_by_date = index_events_by_date(events)
    if verbose:
        print(f"Loaded {len(events)} events across "
              f"{len({e.ticker for e in events})} ticker(s)")

    # Initialize state
    portfolio = Portfolio.initialize(
        taxable_cash=taxable_cash,
        tax_advantaged_cash=tax_advantaged_cash,
    )
    initial_capital = taxable_cash + tax_advantaged_cash
    baselines = initialize_baselines(initial_capital, start_date, prices)

    # Track tickers we'll need to mark-to-market each day. Starts empty;
    # grows as positions are bought.
    held_tickers: set[str] = set()
    seen_event_tickers: set[str] = set()  # for v3 first-call tracking
    skipped_events: list[tuple[date, str, str]] = []
    year_end_taxes: list[YearEndTax] = []
    daily_snapshots: list[DailySnapshot] = []
    loss_carryforward = 0.0

    current = start_date
    last_logged_year = None
    while current <= end_date:
        # 1. Process events for this date
        for event in events_by_date.get(current, []):
            price = prices.price_on(event.ticker, current)
            if price is None:
                skipped_events.append(
                    (current, event.ticker, "no price near call_date")
                )
                continue
            prices_for_decision = prices.all_prices_on(
                list(held_tickers | {event.ticker}), current
            )
            is_first_call = event.ticker not in seen_event_tickers
            seen_event_tickers.add(event.ticker)
            # Type A/B: prefer the curated ticker-level classification (from
            # type_for_ticker) over the per-event classification (which is
            # usually None since the v6 prompt doesn't output it explicitly).
            effective_type = (
                type_for_ticker(event.ticker)
                if type_for_ticker is not None
                else event.type_classification
            )
            decide_kwargs = dict(
                ticker=event.ticker,
                final_action=event.final_action or event.per_call_rec or "Hold",
                recommended_size_pct=event.recommended_size,
                type_classification=effective_type,
                portfolio=portfolio,
                day_price=price,
                trade_date=current,
                prices_today=prices_for_decision,
            )
            # v2/v3 allocators take a `tier` kwarg; v3 also takes is_first_call.
            # We pass both opportunistically — decide_fn ignores unknown kwargs
            # via **kwargs would be ideal, but our concrete fns don't have that.
            # So introspect the function signature.
            import inspect
            sig = inspect.signature(decide_fn)
            # Hard guard (added 2026-08-30, see
            # wrap-ups/diagnose-session-limit-and-donor-rule-out.md): a
            # decide_fn wrapper that accepts **kwargs without ALSO naming
            # tier/is_first_call/driver_count explicitly silently swallows
            # them here (`"tier" in sig.parameters` is False for a bare
            # **kwargs catchall), which has produced a wrong, unflagged
            # result twice. A decide_fn that simply doesn't declare these
            # params at all (e.g. allocator.py's v1, by design) is fine --
            # the checks below correctly no-op for it. Only a **kwargs
            # catchall masking them is the failure shape being guarded here.
            has_var_keyword = any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            if has_var_keyword:
                missing = [n for n in ("tier", "is_first_call", "driver_count")
                           if n not in sig.parameters]
                if missing:
                    raise TypeError(
                        f"decide_fn {getattr(decide_fn, '__name__', decide_fn)!r} "
                        f"accepts **kwargs but does not explicitly declare "
                        f"{missing} -- this silently drops them (see "
                        f"diagnose-spwr-and-cash-instrumentation-out.md and "
                        f"sweep-funding-modes-out.md, both bitten by exactly "
                        f"this). Declare all three parameters explicitly."
                    )
            if tier_for_ticker is not None and "tier" in sig.parameters:
                decide_kwargs["tier"] = tier_for_ticker(event.ticker)
            if driver_count_for_ticker is not None and "driver_count" in sig.parameters:
                decide_kwargs["driver_count"] = driver_count_for_ticker(event.ticker)
            if "is_first_call" in sig.parameters:
                decide_kwargs["is_first_call"] = is_first_call
            trades = decide_fn(**decide_kwargs)
            for trade in trades:
                try:
                    if trade.side == "buy":
                        portfolio.execute_buy(trade)
                        held_tickers.add(trade.ticker)
                    else:  # sell
                        portfolio.execute_sell(trade)
                except InsufficientCash:
                    skipped_events.append(
                        (current, trade.ticker, f"insufficient cash in {trade.account}")
                    )
                except InsufficientShares:
                    skipped_events.append(
                        (current, trade.ticker, f"insufficient shares in {trade.account}")
                    )
            # If we exited a position completely, we don't need to mark it
            # daily anymore — but leaving it in held_tickers is harmless.

        # 2. Year-end tax (Dec 31, or last day of the simulation)
        is_eoy = (current.month == 12 and current.day == 31)
        is_last_day = (current == end_date)
        # If end_date is mid-year, we still want to settle taxes for
        # the partial year on the final day. But avoid double-counting
        # if end_date happens to be Dec 31.
        if is_eoy or (is_last_day and current != date(current.year, 12, 31)):
            mark_prices = prices.all_prices_on(list(held_tickers), current)
            tax_result = compute_year_end_tax(
                portfolio,
                year=current.year,
                loss_carryforward_in=loss_carryforward,
                prices_for_liquidation=mark_prices,
            )
            year_end_taxes.append(tax_result)
            loss_carryforward = tax_result.loss_carryforward_out
            if verbose and (tax_result.tax_owed > 0 or tax_result.net_taxable != 0):
                print(f"  [{current}] year-end tax {current.year}: "
                      f"net=${tax_result.net_taxable:,.0f}  "
                      f"owed=${tax_result.tax_owed:,.0f}  "
                      f"carryforward=${tax_result.loss_carryforward_out:,.0f}")

        # 3. Daily mark-to-market
        mark_prices = prices.all_prices_on(list(held_tickers), current)
        taxable_acc = portfolio.accounts["taxable"]
        tax_adv_acc = portfolio.accounts["tax_advantaged"]
        taxable_value = taxable_acc.cash + sum(
            sum(l.shares * mark_prices.get(t, l.cost_basis_per_share)
                for l in lots)
            for t, lots in taxable_acc.lots.items()
        )
        tax_adv_value = tax_adv_acc.cash + sum(
            sum(l.shares * mark_prices.get(t, l.cost_basis_per_share)
                for l in lots)
            for t, lots in tax_adv_acc.lots.items()
        )
        n_positions = len({
            t for acc in portfolio.accounts.values()
            for t, lots in acc.lots.items()
            if any(l.shares > 1e-9 for l in lots)
        })
        baseline_values = {
            t: b.value_on(prices, current) for t, b in baselines.items()
        }
        daily_snapshots.append(DailySnapshot(
            date=current,
            total_value=taxable_value + tax_adv_value,
            taxable_value=taxable_value,
            tax_advantaged_value=tax_adv_value,
            cash_total=taxable_acc.cash + tax_adv_acc.cash,
            n_positions=n_positions,
            baseline_values=baseline_values,
            cash_taxable=taxable_acc.cash,
            cash_tax_advantaged=tax_adv_acc.cash,
        ))

        if verbose and current.year != last_logged_year:
            print(f"  [{current}] portfolio ${taxable_value + tax_adv_value:,.0f}, "
                  f"{n_positions} positions")
            last_logged_year = current.year

        current += timedelta(days=1)

    universe = sorted({e.ticker for e in events})
    return SimulationResult(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        daily_snapshots=daily_snapshots,
        portfolio=portfolio,
        baselines=baselines,
        year_end_taxes=year_end_taxes,
        universe_tickers=universe,
        skipped_events=skipped_events,
    )
