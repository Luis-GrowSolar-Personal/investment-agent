"""
allocator_v3.py — Phase 2 + first-call auto-starter rule.

Inherits all v2 rules (tighter spec cap, profit-taking, no-average-down)
PLUS: when a ticker has its first call in the simulator window, take a
small starter position regardless of recommendation. Rationale: this
addresses the diagnosed AMPX miss — analyst said Hold on AMPX's first
public call, so v1/v2 never bought; equal-weight got AMPX automatically
by holding 1/N of every name. The starter is the agent's equivalent of
"I'll always have at least a small bet on every name in the universe,
even if I'm not yet convicted."

Starter sizes:
  Speculative: 5% of portfolio on first call
  Established: 8% of portfolio on first call
  (Established gets a slightly bigger starter because higher conviction
  baseline; both are small enough to be cheap to be wrong.)
"""
from __future__ import annotations

from datetime import date as D
from typing import Optional

from .accounts import Portfolio, Trade
from .allocator_v2 import (
    decide as decide_v2,
    _build_sell_trades,
    PROFIT_TAKE_THRESHOLD_PCT, PROFIT_TAKE_REDUCTION_PCT,
    TYPE_A_SPECULATIVE_CAP_PCT, TYPE_A_ESTABLISHED_CAP_PCT, TYPE_B_CAP_PCT,
    _type_cap, _weighted_cost_basis,
)


STARTER_PCT_SPECULATIVE = 5.0
STARTER_PCT_ESTABLISHED = 8.0


def decide(
    *,
    ticker: str,
    final_action: str,
    recommended_size_pct: Optional[float],
    type_classification: Optional[str],
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
    prices_today: dict[str, float],
    tier: Optional[str] = None,
    is_first_call: bool = False,  # set by caller; True only for first event of a ticker
    driver_count: Optional[int] = None,  # forwarded to v2 for variable Type B cap
) -> list[Trade]:
    """v3 decide() — same as v2 plus first-call starter."""
    if day_price is None or day_price <= 0:
        return []

    # First-call starter: only fires when no position exists in the portfolio.
    # If position already exists (e.g., re-entry after exit), no starter.
    if is_first_call and portfolio.position_shares(ticker) <= 1e-9:
        starter_pct = (STARTER_PCT_SPECULATIVE if tier == "speculative"
                        else STARTER_PCT_ESTABLISHED)
        portfolio_value = portfolio.total_value(prices_today)
        if portfolio_value > 0:
            starter_dollars = (starter_pct / 100.0) * portfolio_value
            trades = []
            remaining = starter_dollars
            for account_name in ("tax_advantaged", "taxable"):
                if remaining <= 1e-6: break
                cash_avail = portfolio.accounts[account_name].cash
                if cash_avail <= 1e-6: continue
                spend = min(remaining, cash_avail)
                shares = spend / day_price
                if shares < 1e-9: continue
                trades.append(Trade(
                    account=account_name, ticker=ticker, side="buy",
                    shares=shares, price=day_price, trade_date=trade_date,
                    reason="first-call-starter",
                ))
                remaining -= spend
            # Don't return yet — also evaluate the regular v2 rules for this
            # call (e.g., if rec=Add at 35%, we want to scale up beyond
            # starter). Apply trades to a temporary state? Simpler: emit
            # starter trades + continue to v2 logic which will see the now-
            # existing position and add ON TOP of starter.
            # But Portfolio is mutable — applying trades here would change
            # the simulator's processing. Easier: just emit starter only
            # for first call when rec is Hold (where v2 wouldn't act),
            # and let v2 handle Add/Trim/Exit normally (where v2 would).
            if final_action in ("Hold", None):
                return trades
            # Otherwise fall through to v2 with starter ALREADY queued. The
            # simulator will execute starter trades first, then v2 trades.
            # Caller must execute these trades in order. Concatenate below.
            v2_trades = decide_v2(
                ticker=ticker, final_action=final_action,
                recommended_size_pct=recommended_size_pct,
                type_classification=type_classification,
                portfolio=portfolio, day_price=day_price,
                trade_date=trade_date, prices_today=prices_today,
                tier=tier, driver_count=driver_count,
            )
            return trades + v2_trades

    # Not first call (or already have a position): defer entirely to v2
    return decide_v2(
        ticker=ticker, final_action=final_action,
        recommended_size_pct=recommended_size_pct,
        type_classification=type_classification,
        portfolio=portfolio, day_price=day_price,
        trade_date=trade_date, prices_today=prices_today,
        tier=tier,
    )
