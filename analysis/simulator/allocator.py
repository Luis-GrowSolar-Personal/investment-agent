"""
allocator.py — Decision rules for the backtest simulator (Phase 1).

Pure function: given (call_data, portfolio_state, day_price), returns a
list of Trade objects to execute. Stateless. No I/O.

Rule summary (from BACKTEST_SIMULATOR.md):
  Add  → buy up to min(recommended_size, type_cap) of total portfolio value
  Hold → no-op
  Trim → sell 25% of position shares (FIFO across accounts, tax_advantaged first)
  Exit → sell all shares (across accounts)

Buy routing: tax_advantaged first (shelter gains), fall back to taxable.
Sell routing: tax_advantaged first (zero tax cost on realized gains).

Run module directly to exercise self-tests:
    python3 -m analysis.simulator.allocator
"""
from __future__ import annotations

from datetime import date as D
from typing import Optional

from .accounts import Portfolio, Trade


# Type caps from CLAUDE.md
TYPE_A_CAP_PCT = 35.0   # single-driver
TYPE_B_CAP_PCT = 50.0   # multi-driver platform
DEFAULT_TYPE_CAP_PCT = TYPE_A_CAP_PCT  # conservative default


def _type_cap(type_classification: Optional[str]) -> float:
    if type_classification == "B":
        return TYPE_B_CAP_PCT
    # "A", None, or anything unknown → treat as Type A
    return TYPE_A_CAP_PCT


def decide(
    *,
    ticker: str,
    final_action: str,            # 'Add' | 'Hold' | 'Trim' | 'Exit'
    recommended_size_pct: Optional[float],  # 0-100, or None
    type_classification: Optional[str],     # 'A' | 'B' | None
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
    prices_today: dict[str, float],  # for full-portfolio mark-to-market
) -> list[Trade]:
    """Translate one (ticker, final_action) decision into 0+ Trades.

    The simulator calls this once per call event, then executes the trades
    against the portfolio.
    """
    if day_price is None or day_price <= 0:
        # Can't act without a price.
        return []

    if final_action == "Hold":
        return []

    if final_action == "Add":
        return _decide_add(ticker, recommended_size_pct, type_classification,
                           portfolio, day_price, trade_date, prices_today)
    if final_action == "Trim":
        return _decide_trim(ticker, portfolio, day_price, trade_date)
    if final_action == "Exit":
        return _decide_exit(ticker, portfolio, day_price, trade_date)

    # Unknown action: no-op
    return []


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

def _decide_add(
    ticker: str,
    recommended_size_pct: Optional[float],
    type_classification: Optional[str],
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
    prices_today: dict[str, float],
) -> list[Trade]:
    cap_pct = _type_cap(type_classification)
    target_pct = min(recommended_size_pct, cap_pct) if recommended_size_pct else cap_pct

    portfolio_value = portfolio.total_value(prices_today)
    if portfolio_value <= 0:
        return []

    target_dollars = (target_pct / 100.0) * portfolio_value
    current_dollars = portfolio.position_value(ticker, day_price)
    delta_dollars = target_dollars - current_dollars

    if delta_dollars <= 0:
        # Already at or above target — do nothing
        return []

    # Route to tax_advantaged first, then taxable
    trades: list[Trade] = []
    remaining = delta_dollars
    for account_name in ("tax_advantaged", "taxable"):
        if remaining <= 1e-6:
            break
        cash_avail = portfolio.accounts[account_name].cash
        if cash_avail <= 1e-6:
            continue
        spend = min(remaining, cash_avail)
        shares = spend / day_price
        if shares < 1e-9:
            continue
        trades.append(Trade(
            account=account_name,
            ticker=ticker,
            side="buy",
            shares=shares,
            price=day_price,
            trade_date=trade_date,
            reason="add-to-target",
        ))
        remaining -= spend
    return trades


# ---------------------------------------------------------------------------
# Trim
# ---------------------------------------------------------------------------

def _decide_trim(
    ticker: str,
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
) -> list[Trade]:
    """Sell 25% of total shares of `ticker`. Drain tax_advantaged first."""
    total_shares = portfolio.position_shares(ticker)
    if total_shares <= 1e-9:
        return []
    shares_to_sell = total_shares * 0.25

    return _build_sell_trades(ticker, shares_to_sell, portfolio, day_price,
                                trade_date, reason="trim-25pct")


# ---------------------------------------------------------------------------
# Exit
# ---------------------------------------------------------------------------

def _decide_exit(
    ticker: str,
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
) -> list[Trade]:
    """Sell all shares of `ticker` across both accounts."""
    trades: list[Trade] = []
    for account_name in ("tax_advantaged", "taxable"):
        shares = portfolio.shares_in_account(account_name, ticker)
        if shares <= 1e-9:
            continue
        trades.append(Trade(
            account=account_name,
            ticker=ticker,
            side="sell",
            shares=shares,
            price=day_price,
            trade_date=trade_date,
            reason="exit",
        ))
    return trades


# ---------------------------------------------------------------------------
# Shared sell builder (drains tax_advantaged first)
# ---------------------------------------------------------------------------

def _build_sell_trades(
    ticker: str,
    shares_to_sell: float,
    portfolio: Portfolio,
    day_price: float,
    trade_date: D,
    reason: str,
) -> list[Trade]:
    trades: list[Trade] = []
    remaining = shares_to_sell
    for account_name in ("tax_advantaged", "taxable"):
        if remaining <= 1e-9:
            break
        avail = portfolio.shares_in_account(account_name, ticker)
        if avail <= 1e-9:
            continue
        take = min(avail, remaining)
        trades.append(Trade(
            account=account_name,
            ticker=ticker,
            side="sell",
            shares=take,
            price=day_price,
            trade_date=trade_date,
            reason=reason,
        ))
        remaining -= take
    return trades


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _selftest():
    # Setup: $100k total ($60k taxable, $40k tax_advantaged)
    p = Portfolio.initialize(taxable_cash=60000, tax_advantaged_cash=40000)

    # ------- Test 1: fresh Add at 35% (Type A default), target ticker MSFT
    # Total portfolio value = 100k cash. Target = 35% = $35k.
    # Routing: tax_advantaged first ($40k available, takes full $35k there)
    trades = decide(
        ticker="MSFT", final_action="Add",
        recommended_size_pct=45,  # gets capped to 35 (Type A)
        type_classification="A",
        portfolio=p, day_price=350,
        trade_date=D(2023, 1, 15),
        prices_today={},
    )
    assert len(trades) == 1
    assert trades[0].account == "tax_advantaged"
    assert abs(trades[0].shares - 35000 / 350) < 1e-6  # 100 sh
    # Apply the trade
    p.execute_buy(trades[0])

    # ------- Test 2: Add NVDA at 50% Type B — needs $50k. tax_advantaged
    # has $5k left; remainder ($45k) comes from taxable.
    prices = {"MSFT": 350}
    # Portfolio value now: tax_adv 5k cash + 100 sh MSFT × 350 = 5k + 35k = 40k
    #                    + taxable 60k cash = 100k total still
    # Target NVDA at 50% = 50k. tax_adv has 5k cash → buy 5k there;
    # remaining 45k comes from taxable.
    trades = decide(
        ticker="NVDA", final_action="Add",
        recommended_size_pct=55,  # capped to 50
        type_classification="B",
        portfolio=p, day_price=500,
        trade_date=D(2023, 4, 15),
        prices_today=prices,
    )
    assert len(trades) == 2
    assert trades[0].account == "tax_advantaged"
    assert trades[1].account == "taxable"
    assert abs(trades[0].shares * trades[0].price - 5000) < 1e-6
    assert abs(trades[1].shares * trades[1].price - 45000) < 1e-6
    p.execute_buy(trades[0])
    p.execute_buy(trades[1])

    # ------- Test 3: Hold is a no-op
    trades = decide(
        ticker="MSFT", final_action="Hold",
        recommended_size_pct=35, type_classification="A",
        portfolio=p, day_price=350,
        trade_date=D(2023, 7, 15),
        prices_today={"MSFT": 350, "NVDA": 500},
    )
    assert trades == []

    # ------- Test 4: Add when already at target — no-op
    # MSFT is at $35k (35% of $100k portfolio). Recommend 35% Type A. Should be no-op.
    trades = decide(
        ticker="MSFT", final_action="Add",
        recommended_size_pct=35, type_classification="A",
        portfolio=p, day_price=350,
        trade_date=D(2023, 7, 15),
        prices_today={"MSFT": 350, "NVDA": 500},
    )
    assert trades == []

    # ------- Test 5: Trim 25% of MSFT (100 sh in tax_advantaged → trim 25 sh)
    trades = decide(
        ticker="MSFT", final_action="Trim",
        recommended_size_pct=None, type_classification="A",
        portfolio=p, day_price=400,
        trade_date=D(2023, 10, 15),
        prices_today={"MSFT": 400, "NVDA": 500},
    )
    assert len(trades) == 1
    assert trades[0].side == "sell"
    assert trades[0].account == "tax_advantaged"  # drains tax_adv first
    assert abs(trades[0].shares - 25) < 1e-6  # 25% of 100 sh

    # ------- Test 6: Exit sells everything across both accounts
    # NVDA: 10 sh in tax_advantaged ($5k/$500), 90 sh in taxable ($45k/$500)
    trades = decide(
        ticker="NVDA", final_action="Exit",
        recommended_size_pct=None, type_classification="B",
        portfolio=p, day_price=600,
        trade_date=D(2023, 11, 15),
        prices_today={"MSFT": 400, "NVDA": 600},
    )
    assert len(trades) == 2
    assert {t.account for t in trades} == {"tax_advantaged", "taxable"}
    assert abs(sum(t.shares for t in trades) - 100) < 1e-6  # all 100 sh

    # ------- Test 7: Trim a position not held → no trades
    trades = decide(
        ticker="GHOST", final_action="Trim",
        recommended_size_pct=None, type_classification="A",
        portfolio=p, day_price=100,
        trade_date=D(2023, 12, 15),
        prices_today={},
    )
    assert trades == []

    # ------- Test 8: Add when both accounts are out of cash → no trades
    # (After all the buys above, cash should be near zero — let's make a fresh
    # zero-cash portfolio to check)
    p_empty = Portfolio.initialize(taxable_cash=0, tax_advantaged_cash=0)
    trades = decide(
        ticker="AAPL", final_action="Add",
        recommended_size_pct=35, type_classification="A",
        portfolio=p_empty, day_price=200,
        trade_date=D(2023, 1, 1),
        prices_today={},
    )
    assert trades == []

    # ------- Test 9: missing recommended_size on Add uses default 35% cap
    p2 = Portfolio.initialize(taxable_cash=0, tax_advantaged_cash=10000)
    trades = decide(
        ticker="AMD", final_action="Add",
        recommended_size_pct=None, type_classification=None,  # → Type A default
        portfolio=p2, day_price=100,
        trade_date=D(2023, 1, 1),
        prices_today={},
    )
    assert len(trades) == 1
    # 35% of $10k = $3500
    assert abs(trades[0].shares * trades[0].price - 3500) < 1e-6

    print("All allocator.py self-tests passed.")


if __name__ == "__main__":
    _selftest()
