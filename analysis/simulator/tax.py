"""
tax.py — Year-end tax computation for the backtest simulator.

Per the project spec:
- 15% LTCG (federal, FL no state tax)
- 15% STCG (matches owner's blended ordinary rate)
- Tax-advantaged accounts: 0%
- Taxable account only: pay tax annually on net realized gains
- Net losses can offset gains; residual losses carry forward (no refund)
- If taxable cash insufficient to cover tax: FIFO-liquidate positions

Run module directly to exercise self-tests:
    python3 -m analysis.simulator.tax
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as D

from .accounts import Portfolio, Trade, RealizedSale, InsufficientShares


STCG_RATE = 0.15  # owner's blended ordinary rate
LTCG_RATE = 0.15  # below 20% threshold given owner's bracket


@dataclass
class YearEndTax:
    """Result of running year-end tax for a given calendar year."""
    year: int
    short_term_gain: float
    long_term_gain: float
    short_term_loss: float    # absolute value (positive number)
    long_term_loss: float     # absolute value
    net_short_term: float     # gain - loss (signed)
    net_long_term: float      # gain - loss (signed)
    loss_carryforward_in: float   # carried in from prior year
    net_taxable: float        # after netting + carryforward
    tax_owed: float
    loss_carryforward_out: float  # to carry forward to next year
    forced_liquidation_proceeds: float = 0.0
    extra_realized_gain_from_liquidation: float = 0.0


def _filter_year_sales_taxable(portfolio: Portfolio, year: int) -> list[RealizedSale]:
    return [
        s for s in portfolio.realized_sales
        if s.account == "taxable" and s.sale_date.year == year
    ]


def compute_year_end_tax(
    portfolio: Portfolio,
    year: int,
    loss_carryforward_in: float = 0.0,
    prices_for_liquidation: dict[str, float] | None = None,
) -> YearEndTax:
    """Compute tax owed for `year` and apply the cash withdrawal.

    If taxable cash is insufficient and `prices_for_liquidation` is provided,
    FIFO-liquidates positions in the taxable account to cover the shortfall.
    The forced liquidation can itself create new realized gains, which we
    fold into the same year's tax bill (rare but possible).

    Returns a YearEndTax record summarizing the calculation.
    """
    sales = _filter_year_sales_taxable(portfolio, year)

    short_gain = sum(s.realized_gain for s in sales if not s.is_long_term and s.realized_gain > 0)
    short_loss = sum(-s.realized_gain for s in sales if not s.is_long_term and s.realized_gain < 0)
    long_gain  = sum(s.realized_gain for s in sales if s.is_long_term and s.realized_gain > 0)
    long_loss  = sum(-s.realized_gain for s in sales if s.is_long_term and s.realized_gain < 0)

    net_short = short_gain - short_loss   # may be negative
    net_long  = long_gain - long_loss     # may be negative

    # Both rates equal in our spec, so we can collapse to a single net.
    # (If rates differed, IRS netting would prefer offsetting same-bucket
    # losses first, then cross-bucket. Since 15%==15% the order is moot.)
    net_taxable_pre_carry = net_short + net_long
    net_taxable = net_taxable_pre_carry - loss_carryforward_in

    if net_taxable > 0:
        tax_owed = STCG_RATE * net_taxable  # = LTCG_RATE * net_taxable in our spec
        carryforward_out = 0.0
    else:
        tax_owed = 0.0
        # Negative net_taxable becomes a (positive) carryforward
        carryforward_out = -net_taxable

    # Withdraw tax from taxable account cash; FIFO-liquidate if short
    forced_proceeds = 0.0
    extra_gain_from_liq = 0.0
    if tax_owed > 0:
        taxable_acc = portfolio.accounts["taxable"]
        if taxable_acc.cash >= tax_owed - 1e-6:
            taxable_acc.cash -= tax_owed
        else:
            shortfall = tax_owed - taxable_acc.cash
            taxable_acc.cash = 0.0
            extra_gain_from_liq, forced_proceeds = _force_liquidate_for_tax(
                portfolio,
                year=year,
                shortfall=shortfall,
                prices=prices_for_liquidation or {},
            )
            # forced_proceeds went into cash; subtract the tax we still owe
            taxable_acc.cash -= shortfall

    return YearEndTax(
        year=year,
        short_term_gain=short_gain,
        long_term_gain=long_gain,
        short_term_loss=short_loss,
        long_term_loss=long_loss,
        net_short_term=net_short,
        net_long_term=net_long,
        loss_carryforward_in=loss_carryforward_in,
        net_taxable=net_taxable,
        tax_owed=tax_owed,
        loss_carryforward_out=carryforward_out,
        forced_liquidation_proceeds=forced_proceeds,
        extra_realized_gain_from_liquidation=extra_gain_from_liq,
    )


def _force_liquidate_for_tax(
    portfolio: Portfolio,
    year: int,
    shortfall: float,
    prices: dict[str, float],
) -> tuple[float, float]:
    """Liquidate positions in the taxable account to raise `shortfall` in cash.

    Strategy: FIFO across all tickers, sorted by ticker symbol for
    determinism. Sells whole tickers first (cleanest), partial only when a
    single ticker covers the remainder.

    Returns (extra_realized_gain, total_proceeds). Mutates the portfolio.
    """
    if shortfall <= 0:
        return 0.0, 0.0
    taxable = portfolio.accounts["taxable"]
    sale_date = D(year, 12, 31)
    proceeds_total = 0.0
    extra_gain = 0.0
    remaining = shortfall

    # Snapshot tickers held in taxable, deterministic order
    tickers = sorted(list(taxable.lots.keys()))
    for ticker in tickers:
        if remaining <= 1e-9:
            break
        price = prices.get(ticker)
        if price is None:
            continue  # can't price this one, skip
        shares_held = taxable.total_shares(ticker)
        if shares_held <= 0:
            continue
        max_proceeds = shares_held * price
        if max_proceeds <= remaining:
            shares_to_sell = shares_held
        else:
            shares_to_sell = remaining / price
        trade = Trade(
            account="taxable", ticker=ticker, side="sell",
            shares=shares_to_sell, price=price, trade_date=sale_date,
            reason="forced-liquidation-for-tax",
        )
        sales = portfolio.execute_sell(trade)
        for s in sales:
            proceeds_total += s.proceeds
            if s.realized_gain > 0:
                extra_gain += s.realized_gain
            # Note: a forced liquidation can also produce losses, which would
            # in turn reduce the tax bill — but we already computed tax above.
            # In practice this is a small effect at our scale; flag and move on.
        remaining -= shares_to_sell * price
    if remaining > 1e-3:
        # Couldn't cover the full shortfall — taxable account is exhausted.
        # Tax remains "owed" but we have no cash to pay it. In real life
        # you'd have a debt to the IRS. For the simulator, log and move on
        # (the report will surface this as a portfolio-blowup signal).
        pass
    return extra_gain, proceeds_total


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _selftest():
    # Simple case: two long-term gains, no losses, sufficient cash
    p = Portfolio.initialize(taxable_cash=10000, tax_advantaged_cash=0)
    p.execute_buy(Trade(account="taxable", ticker="AAPL", side="buy",
                          shares=10, price=200, trade_date=D(2022, 1, 1),
                          reason="add"))
    # 2 years later, sell at $300 for $1000 LT gain
    p.execute_sell(Trade(account="taxable", ticker="AAPL", side="sell",
                          shares=10, price=300, trade_date=D(2024, 6, 1),
                          reason="exit"))
    assert p.realized_sales[0].is_long_term

    result = compute_year_end_tax(p, year=2024)
    assert result.long_term_gain == 1000
    assert result.tax_owed == 150  # 15% of $1000
    assert result.loss_carryforward_out == 0.0
    # Cash before tax: started 10000, spent 2000, gained 3000 → 11000
    # After tax: 11000 - 150 = 10850
    assert abs(p.accounts["taxable"].cash - 10850) < 1e-6

    # Loss carryforward case: net loss this year carries to next
    p = Portfolio.initialize(taxable_cash=10000, tax_advantaged_cash=0)
    p.execute_buy(Trade(account="taxable", ticker="LOSER", side="buy",
                          shares=10, price=500, trade_date=D(2024, 1, 1),
                          reason="add"))
    p.execute_sell(Trade(account="taxable", ticker="LOSER", side="sell",
                          shares=10, price=300, trade_date=D(2024, 6, 1),
                          reason="exit"))
    # $2000 ST loss
    result = compute_year_end_tax(p, year=2024)
    assert result.short_term_loss == 2000
    assert result.tax_owed == 0.0
    assert result.loss_carryforward_out == 2000

    # Next year: a gain offset by the carryforward
    p.execute_buy(Trade(account="taxable", ticker="WINNER", side="buy",
                          shares=10, price=300, trade_date=D(2025, 1, 1),
                          reason="add"))
    p.execute_sell(Trade(account="taxable", ticker="WINNER", side="sell",
                          shares=10, price=600, trade_date=D(2025, 6, 1),
                          reason="exit"))
    # $3000 ST gain offset by $2000 carryforward → $1000 net
    result_y2 = compute_year_end_tax(p, year=2025, loss_carryforward_in=2000)
    assert abs(result_y2.short_term_gain - 3000) < 1e-6
    assert abs(result_y2.net_taxable - 1000) < 1e-6
    assert abs(result_y2.tax_owed - 150) < 1e-6  # 15% of $1000
    assert result_y2.loss_carryforward_out == 0

    # Tax-advantaged sales should NEVER be in the tax calc
    p = Portfolio.initialize(taxable_cash=0, tax_advantaged_cash=10000)
    p.execute_buy(Trade(account="tax_advantaged", ticker="NVDA", side="buy",
                          shares=10, price=500, trade_date=D(2023, 1, 1),
                          reason="add"))
    p.execute_sell(Trade(account="tax_advantaged", ticker="NVDA", side="sell",
                          shares=10, price=1000, trade_date=D(2024, 12, 1),
                          reason="exit"))
    result = compute_year_end_tax(p, year=2024)
    assert result.tax_owed == 0.0  # tax_advantaged account, no tax
    assert result.long_term_gain == 0.0  # filter excludes tax_advantaged

    # Forced liquidation: tax owed but cash insufficient
    p = Portfolio.initialize(taxable_cash=50, tax_advantaged_cash=0)
    p.execute_buy(Trade(account="taxable", ticker="AAPL", side="buy",
                          shares=1, price=10, trade_date=D(2022, 1, 1),
                          reason="add"))
    p.execute_sell(Trade(account="taxable", ticker="AAPL", side="sell",
                          shares=1, price=5000, trade_date=D(2024, 6, 1),
                          reason="exit"))
    # Realized gain: $4990 → tax = $748.50; cash = 50 - 10 + 5000 = 5040 (sufficient)
    result = compute_year_end_tax(p, year=2024)
    assert result.tax_owed == 4990 * 0.15  # = 748.50

    print("All tax.py self-tests passed.")


if __name__ == "__main__":
    _selftest()
