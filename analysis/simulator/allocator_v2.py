"""
allocator_v2.py — Phase 2 allocator decision rules (paper test).

Three rule changes vs. v1:

1. Tier-aware Type A cap. Speculative tickers (3-axis classifier) get a
   tighter Type A cap (15% instead of 35%). Established tickers keep 35%.
   This addresses the TTD-on-day-1 over-concentration that destroyed Run 1.

2. Profit-taking on grown-into positions. When a ticker's position exceeds
   25% of total portfolio value (regardless of original target), trim 5pp on
   the next call event for that ticker. Lets winners run while preventing
   uncontrolled concentration drift.

3. No-average-down on speculatives. If the current price is below the
   weighted-average cost basis on a speculative-tier ticker, skip the Add
   even if the analyst recommends it. Prevents the agent from doubling down
   on losers.

These are the changes most directly motivated by the Phase 1 diagnosis:
- TTD blow-up: rule 1 caps day-1 exposure.
- AMPX miss: rule 2 lets a position from a small starter grow without
  the agent capping it; rule 3 prevents capital being drained on losers.
- Speculative cohort flat-line: rules 1+3 keep small bets small.

Run module directly to exercise self-tests:
    python3 -m analysis.simulator.allocator_v2
"""
from __future__ import annotations

from datetime import date as D
from typing import Optional, Callable

from .accounts import Portfolio, Trade


TYPE_A_ESTABLISHED_CAP_PCT = 35.0
TYPE_A_SPECULATIVE_CAP_PCT = 15.0   # Phase 2 — much tighter
TYPE_B_CAP_PCT = 50.0               # Production: flat for all Type B (see note below)
PROFIT_TAKE_THRESHOLD_PCT = 25.0    # Phase 2 — trim if position grows past this
PROFIT_TAKE_REDUCTION_PCT = 5.0     # Phase 2 — trim by this percentage

# Variable cap experiment retired 2026-05-17.
#
# DESIGN_PRINCIPLES.md originally specified Type B with a variable 40-60%
# cap based on driver count (40% for 2-driver, scaling to 60% for 6+ driver
# platforms). Implementation was tested empirically against the full event
# corpus. Result: essentially zero impact on aggregate v3 returns and
# drawdowns. Mechanism: the 25% profit-take rule (PROFIT_TAKE_THRESHOLD_PCT)
# binds long before the Type B cap binds. Positions get trimmed at 25% on
# every call regardless of whether the upper cap is 40%, 50%, or 60%.
# The variable scheme is therefore vestigial in the presence of profit-take.
#
# The `driver_count` parameter remains in allocator signatures and is
# plumbed through the simulator for backward compatibility and possible
# future use (e.g., feeding the RADAR UI with metadata or supporting a
# tier-aware Type B cap refinement). It is currently a no-op in cap math.
# See PORTFOLIO_ANALYST_SPEC.md and DESIGN_PRINCIPLES.md for the formal
# retirement decision and the empirical basis.


def _type_cap(type_classification: Optional[str], tier: Optional[str],
              driver_count: Optional[int] = None) -> float:
    # driver_count is accepted but unused — see retirement note above.
    if type_classification == "B":
        return TYPE_B_CAP_PCT
    if tier == "speculative":
        return TYPE_A_SPECULATIVE_CAP_PCT
    return TYPE_A_ESTABLISHED_CAP_PCT


def _weighted_cost_basis(portfolio: Portfolio, ticker: str) -> Optional[float]:
    """Average cost basis per share across both accounts, weighted by shares.
    Returns None if no position."""
    total_shares = 0.0
    total_cost = 0.0
    for acc in portfolio.accounts.values():
        for lot in acc.lots.get(ticker, []):
            total_shares += lot.shares
            total_cost += lot.shares * lot.cost_basis_per_share
    if total_shares <= 1e-9:
        return None
    return total_cost / total_shares


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
    tier: Optional[str] = None,           # 'speculative' | 'established'
    driver_count: Optional[int] = None,   # 1-6+; used for variable Type B cap
) -> list[Trade]:
    """Phase 2 decide(). New `tier` parameter; rest of signature matches v1."""
    if day_price is None or day_price <= 0:
        return []

    # ---- Rule 2: profit-taking. Independent of final_action. -------------
    portfolio_value = portfolio.total_value(prices_today)
    pos_value = portfolio.position_value(ticker, day_price)
    if portfolio_value > 0:
        pos_pct = (pos_value / portfolio_value) * 100
        if pos_pct >= PROFIT_TAKE_THRESHOLD_PCT:
            target_pct = pos_pct - PROFIT_TAKE_REDUCTION_PCT
            target_dollars = (target_pct / 100.0) * portfolio_value
            shares_to_sell = (pos_value - target_dollars) / day_price
            if shares_to_sell > 0:
                trades = _build_sell_trades(
                    ticker, shares_to_sell, portfolio, day_price,
                    trade_date, reason="profit-take-25pct-trigger",
                )
                # Profit-take supersedes the call's action — return early.
                # (Trim/Exit on top would be redundant / over-trim.)
                return trades

    # ---- Rule 1+3: regular call-driven actions ----------------------------
    if final_action == "Hold":
        return []
    if final_action == "Add":
        return _decide_add(ticker, recommended_size_pct, type_classification,
                            tier, portfolio, day_price, trade_date, prices_today,
                            portfolio_value, driver_count)
    if final_action == "Trim":
        return _decide_trim(ticker, portfolio, day_price, trade_date)
    if final_action == "Exit":
        return _decide_exit(ticker, portfolio, day_price, trade_date)
    return []


def _decide_add(
    ticker, recommended_size_pct, type_classification, tier,
    portfolio, day_price, trade_date, prices_today, portfolio_value,
    driver_count=None,
):
    cap_pct = _type_cap(type_classification, tier, driver_count)
    target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct

    # Rule 3: skip Add on speculatives if current price < cost basis
    if tier == "speculative":
        cb = _weighted_cost_basis(portfolio, ticker)
        if cb is not None and day_price < cb:
            return []  # don't average down on speculative losers

    if portfolio_value <= 0:
        return []
    target_dollars = (target_pct / 100.0) * portfolio_value
    current_dollars = portfolio.position_value(ticker, day_price)
    delta_dollars = target_dollars - current_dollars
    if delta_dollars <= 0:
        return []

    trades = []
    remaining = delta_dollars
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
            reason="add-to-target",
        ))
        remaining -= spend
    return trades


def _decide_trim(ticker, portfolio, day_price, trade_date):
    total_shares = portfolio.position_shares(ticker)
    if total_shares <= 1e-9: return []
    return _build_sell_trades(ticker, total_shares * 0.25, portfolio,
                                day_price, trade_date, reason="trim-25pct")


def _decide_exit(ticker, portfolio, day_price, trade_date):
    trades = []
    for account_name in ("tax_advantaged", "taxable"):
        shares = portfolio.shares_in_account(account_name, ticker)
        if shares <= 1e-9: continue
        trades.append(Trade(
            account=account_name, ticker=ticker, side="sell",
            shares=shares, price=day_price, trade_date=trade_date,
            reason="exit",
        ))
    return trades


def _build_sell_trades(ticker, shares_to_sell, portfolio, day_price, trade_date, reason):
    trades = []
    remaining = shares_to_sell
    for account_name in ("tax_advantaged", "taxable"):
        if remaining <= 1e-9: break
        avail = portfolio.shares_in_account(account_name, ticker)
        if avail <= 1e-9: continue
        take = min(avail, remaining)
        trades.append(Trade(
            account=account_name, ticker=ticker, side="sell",
            shares=take, price=day_price, trade_date=trade_date,
            reason=reason,
        ))
        remaining -= take
    return trades


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _selftest():
    p = Portfolio.initialize(taxable_cash=50000, tax_advantaged_cash=50000)

    # Rule 1: speculative gets a 15% cap (not 35%)
    trades = decide(
        ticker="AMPX", final_action="Add", recommended_size_pct=45,
        type_classification="A", portfolio=p, day_price=10,
        trade_date=D(2024,8,1), prices_today={}, tier="speculative",
    )
    assert len(trades) == 1
    # 15% of $100k = $15k → 1500 shares
    assert abs(trades[0].shares * trades[0].price - 15000) < 1e-6

    # Established A still gets 35%
    trades = decide(
        ticker="AAPL", final_action="Add", recommended_size_pct=45,
        type_classification="A", portfolio=p, day_price=200,
        trade_date=D(2024,8,1), prices_today={}, tier="established",
    )
    assert abs(trades[0].shares * trades[0].price - 35000) < 1e-6

    # Rule 3: don't average down on speculative
    p.execute_buy(trades[0])  # AAPL bought at $200 (just to get cost basis on something)
    p.execute_buy(Trade(account="tax_advantaged", ticker="AMPX", side="buy",
                          shares=1000, price=10, trade_date=D(2024,8,1),
                          reason="initial"))
    # AMPX at $10 cost. Now price drops to $5; agent says Add.
    trades = decide(
        ticker="AMPX", final_action="Add", recommended_size_pct=15,
        type_classification="A", portfolio=p, day_price=5,
        trade_date=D(2024,11,1), prices_today={"AMPX": 5, "AAPL": 200},
        tier="speculative",
    )
    assert trades == []  # don't average down

    # Rule 2: profit-taking when position >25% of portfolio
    # Build a portfolio where MSFT is 70% of total
    p2 = Portfolio.initialize(taxable_cash=70000, tax_advantaged_cash=30000)
    p2.execute_buy(Trade(account="taxable", ticker="MSFT", side="buy",
                           shares=200, price=350, trade_date=D(2024,1,1),
                           reason="initial"))
    # taxable cash now $0; MSFT position $70k; tax_adv cash $30k → total $100k
    # MSFT position: 200 × 350 = $70k. tax_adv cash: $30k. Total: $100k.
    # MSFT is 70% of portfolio. Even on Hold, profit-taking should fire.
    trades = decide(
        ticker="MSFT", final_action="Hold", recommended_size_pct=None,
        type_classification="A", portfolio=p2, day_price=350,
        trade_date=D(2024,4,1), prices_today={"MSFT": 350}, tier="established",
    )
    assert len(trades) == 1
    assert trades[0].side == "sell"
    # MSFT at 70% should drop to 65% → trim 5pp = $5k = ~14.3 shares
    assert abs(trades[0].shares * trades[0].price - 5000) < 1e-3

    # Hold on a position under 25% → still no-op
    # AAPL = $20k of $100k portfolio (20%, below 25% threshold).
    p3 = Portfolio.initialize(taxable_cash=100000, tax_advantaged_cash=0)
    p3.execute_buy(Trade(account="taxable", ticker="AAPL", side="buy",
                          shares=100, price=200, trade_date=D(2024,1,1),
                          reason="initial"))
    # taxable cash now $80k; AAPL $20k; total $100k → AAPL is 20%
    trades = decide(
        ticker="AAPL", final_action="Hold", recommended_size_pct=None,
        type_classification="A", portfolio=p3, day_price=200,
        trade_date=D(2024,4,1), prices_today={"AAPL": 200}, tier="established",
    )
    assert trades == [], f"expected no trades, got {trades}"

    print("All allocator_v2.py self-tests passed.")


if __name__ == "__main__":
    _selftest()
