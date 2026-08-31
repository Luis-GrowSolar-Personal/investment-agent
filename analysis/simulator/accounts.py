"""
accounts.py — Portfolio data model for the backtest simulator.

Two account types: 'taxable' and 'tax_advantaged'. Each holds cash plus
a dict of ticker → list[Lot]. Lots are tracked individually for FIFO
sales and tax-lot accounting (cost basis, holding period).

Run module directly to exercise self-tests:
    python3 -m analysis.simulator.accounts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Lot:
    """One purchase tranche. FIFO sales drain lots in acquired_date order."""
    ticker: str
    shares: float
    cost_basis_per_share: float
    acquired_date: date

    @property
    def total_cost_basis(self) -> float:
        return self.shares * self.cost_basis_per_share

    def market_value(self, price: float) -> float:
        return self.shares * price


@dataclass
class Account:
    """Single account (taxable or tax_advantaged) with cash + per-ticker lots."""
    name: str  # 'taxable' or 'tax_advantaged'
    cash: float = 0.0
    # ticker → list of lots (oldest first; we keep this invariant on insert)
    lots: dict[str, list[Lot]] = field(default_factory=dict)

    def total_shares(self, ticker: str) -> float:
        return sum(lot.shares for lot in self.lots.get(ticker, []))

    def position_value(self, ticker: str, price: float) -> float:
        return self.total_shares(ticker) * price

    def cost_basis(self, ticker: str) -> float:
        return sum(lot.total_cost_basis for lot in self.lots.get(ticker, []))

    def add_lot(self, lot: Lot) -> None:
        bucket = self.lots.setdefault(lot.ticker, [])
        bucket.append(lot)
        # Keep lots sorted oldest-first so FIFO is just an iteration
        bucket.sort(key=lambda l: l.acquired_date)


@dataclass
class RealizedSale:
    """One closed sale, used for tax accounting and the transaction log."""
    ticker: str
    account: str
    sale_date: date
    sale_price: float
    shares_sold: float
    cost_basis_total: float
    proceeds: float
    realized_gain: float
    is_long_term: bool  # holding ≥ 365 days
    holding_days: int
    reason: Optional[str] = None  # e.g. "swap-funding-displacement"; from Trade.reason


@dataclass
class Trade:
    """One executed buy or sell. The allocator emits these; the simulator
    applies them to the Portfolio. Buys produce a new Lot; sells produce
    one or more RealizedSale rows (FIFO across lots)."""
    account: str  # 'taxable' or 'tax_advantaged'
    ticker: str
    side: str     # 'buy' or 'sell'
    shares: float
    price: float
    trade_date: date
    reason: str   # short label e.g. 'add-to-target', 'trim-25pct', 'exit'


class InsufficientCash(Exception):
    pass


class InsufficientShares(Exception):
    pass


@dataclass
class Portfolio:
    """Two-account portfolio with cash + lots. Owns the FIFO sale logic and
    cost-basis math; year-end tax computation lives in tax.py."""
    accounts: dict[str, Account] = field(default_factory=dict)
    realized_sales: list[RealizedSale] = field(default_factory=list)
    transaction_log: list[Trade] = field(default_factory=list)

    @classmethod
    def initialize(cls, taxable_cash: float, tax_advantaged_cash: float) -> "Portfolio":
        return cls(accounts={
            "taxable": Account(name="taxable", cash=taxable_cash),
            "tax_advantaged": Account(name="tax_advantaged", cash=tax_advantaged_cash),
        })

    # --- valuation -------------------------------------------------------

    def total_cash(self) -> float:
        return sum(a.cash for a in self.accounts.values())

    def total_position_value(self, prices: dict[str, float]) -> float:
        total = 0.0
        for acc in self.accounts.values():
            for ticker, lots in acc.lots.items():
                price = prices.get(ticker)
                if price is None:
                    # No price for this ticker today — use cost basis as a
                    # fallback so portfolio_value doesn't undercount.
                    total += sum(l.total_cost_basis for l in lots)
                else:
                    total += sum(l.shares * price for l in lots)
        return total

    def total_value(self, prices: dict[str, float]) -> float:
        return self.total_cash() + self.total_position_value(prices)

    def position_shares(self, ticker: str) -> float:
        return sum(a.total_shares(ticker) for a in self.accounts.values())

    def position_value(self, ticker: str, price: float) -> float:
        return sum(a.position_value(ticker, price) for a in self.accounts.values())

    # --- buys ------------------------------------------------------------

    def execute_buy(self, trade: Trade) -> Lot:
        """Apply a buy: deduct cash from `account`, create a new Lot."""
        if trade.side != "buy":
            raise ValueError(f"execute_buy got side={trade.side}")
        acc = self.accounts[trade.account]
        cost = trade.shares * trade.price
        if cost > acc.cash + 1e-6:
            raise InsufficientCash(
                f"{trade.account} has ${acc.cash:.2f}, needs ${cost:.2f} for "
                f"{trade.shares} sh of {trade.ticker} @ {trade.price:.2f}"
            )
        acc.cash -= cost
        lot = Lot(
            ticker=trade.ticker,
            shares=trade.shares,
            cost_basis_per_share=trade.price,
            acquired_date=trade.trade_date,
        )
        acc.add_lot(lot)
        self.transaction_log.append(trade)
        return lot

    # --- sells (FIFO) ----------------------------------------------------

    def execute_sell(self, trade: Trade) -> list[RealizedSale]:
        """Apply a FIFO sell within `account`. Drains oldest lots first.
        Returns the list of RealizedSale rows produced (may span multiple
        lots if the sale crosses lot boundaries)."""
        if trade.side != "sell":
            raise ValueError(f"execute_sell got side={trade.side}")
        acc = self.accounts[trade.account]
        bucket = acc.lots.get(trade.ticker, [])
        avail = sum(l.shares for l in bucket)
        if trade.shares > avail + 1e-6:
            raise InsufficientShares(
                f"{trade.account} has {avail:.4f} sh of {trade.ticker}, "
                f"trade requests {trade.shares:.4f}"
            )

        remaining = trade.shares
        sales: list[RealizedSale] = []
        i = 0
        while remaining > 1e-9 and i < len(bucket):
            lot = bucket[i]
            take = min(lot.shares, remaining)
            cost_basis_total = take * lot.cost_basis_per_share
            proceeds = take * trade.price
            holding_days = (trade.trade_date - lot.acquired_date).days
            sales.append(RealizedSale(
                ticker=trade.ticker,
                account=trade.account,
                sale_date=trade.trade_date,
                sale_price=trade.price,
                shares_sold=take,
                cost_basis_total=cost_basis_total,
                proceeds=proceeds,
                realized_gain=proceeds - cost_basis_total,
                reason=trade.reason,
                is_long_term=holding_days >= 365,
                holding_days=holding_days,
            ))
            lot.shares -= take
            remaining -= take
            i += 1

        # Drop any fully-drained lots
        acc.lots[trade.ticker] = [l for l in bucket if l.shares > 1e-9]
        if not acc.lots[trade.ticker]:
            del acc.lots[trade.ticker]

        # Cash credited
        acc.cash += trade.shares * trade.price
        self.realized_sales.extend(sales)
        self.transaction_log.append(trade)
        return sales

    # --- account routing for sells ---------------------------------------

    def shares_in_account(self, account: str, ticker: str) -> float:
        return self.accounts[account].total_shares(ticker)


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _selftest():
    from datetime import date as D

    p = Portfolio.initialize(taxable_cash=50000, tax_advantaged_cash=50000)
    assert p.total_cash() == 100000
    assert p.total_position_value({}) == 0.0

    # Buy 100 sh AAPL @ $200 in taxable
    t1 = Trade(account="taxable", ticker="AAPL", side="buy",
               shares=100, price=200, trade_date=D(2023, 1, 15),
               reason="add-to-target")
    p.execute_buy(t1)
    assert p.accounts["taxable"].cash == 50000 - 20000
    assert p.position_shares("AAPL") == 100

    # Buy 50 more sh AAPL @ $250 in taxable, 6 months later
    t2 = Trade(account="taxable", ticker="AAPL", side="buy",
               shares=50, price=250, trade_date=D(2023, 7, 15),
               reason="add-to-target")
    p.execute_buy(t2)
    assert p.position_shares("AAPL") == 150
    assert len(p.accounts["taxable"].lots["AAPL"]) == 2

    # Sell 80 sh @ $300 — FIFO drains the first lot fully (100→20 left
    # actually 100-80=20 left), no second-lot draw
    t3 = Trade(account="taxable", ticker="AAPL", side="sell",
               shares=80, price=300, trade_date=D(2024, 6, 15),
               reason="trim-25pct")
    sales = p.execute_sell(t3)
    assert len(sales) == 1
    assert sales[0].shares_sold == 80
    # Holding days from 2023-01-15 → 2024-06-15 = 517 days → long-term
    assert sales[0].is_long_term is True
    assert abs(sales[0].realized_gain - (80 * 300 - 80 * 200)) < 1e-6
    assert p.position_shares("AAPL") == 70  # 20 from lot1 + 50 from lot2

    # Sell another 40 sh — drains lot1 (20 remaining) + 20 from lot2
    t4 = Trade(account="taxable", ticker="AAPL", side="sell",
               shares=40, price=350, trade_date=D(2024, 12, 15),
               reason="trim-25pct")
    sales = p.execute_sell(t4)
    assert len(sales) == 2  # spans two lots
    # First: 20 sh from lot1 (cost 200) — long-term (>365 days)
    assert sales[0].shares_sold == 20
    assert sales[0].cost_basis_total == 20 * 200
    assert sales[0].is_long_term is True
    # Second: 20 sh from lot2 (cost 250) — also long-term (2023-07-15 → 2024-12-15)
    assert sales[1].shares_sold == 20
    assert sales[1].cost_basis_total == 20 * 250
    assert sales[1].is_long_term is True

    # Cash check: started 50000, spent 20000 + 12500, gained 24000 + 14000
    expected_cash = 50000 - 20000 - 12500 + 80 * 300 + 40 * 350
    assert abs(p.accounts["taxable"].cash - expected_cash) < 1e-6, \
        f"cash {p.accounts['taxable'].cash} != {expected_cash}"

    # Insufficient shares should raise
    try:
        p.execute_sell(Trade(account="taxable", ticker="AAPL", side="sell",
                              shares=999, price=400, trade_date=D(2024, 12, 31),
                              reason="exit"))
        assert False, "should have raised InsufficientShares"
    except InsufficientShares:
        pass

    # Insufficient cash should raise
    try:
        p.execute_buy(Trade(account="taxable", ticker="AAPL", side="buy",
                             shares=1000, price=1000, trade_date=D(2024, 12, 31),
                             reason="add-to-target"))
        assert False, "should have raised InsufficientCash"
    except InsufficientCash:
        pass

    # Short-term lot test
    p2 = Portfolio.initialize(taxable_cash=10000, tax_advantaged_cash=0)
    p2.execute_buy(Trade(account="taxable", ticker="NVDA", side="buy",
                          shares=10, price=500, trade_date=D(2024, 6, 1),
                          reason="add"))
    sales = p2.execute_sell(Trade(account="taxable", ticker="NVDA", side="sell",
                                    shares=5, price=600, trade_date=D(2024, 12, 1),
                                    reason="trim"))
    assert sales[0].is_long_term is False  # 183 days < 365

    print("All accounts.py self-tests passed.")


if __name__ == "__main__":
    _selftest()
