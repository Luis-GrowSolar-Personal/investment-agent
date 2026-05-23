"""
baseline.py — Buy-and-hold ETF baselines for the backtest comparison.

Computes the value over time of $X buy-and-hold of SPY, QQQ, TMFC starting
on `start_date`. Uses prices from price_cache.json; expects Adj Close
(dividend-reinvested total return) for honest comparison.

The simulator queries this via `BaselineComputer.value_on(date)`.

No taxes are applied to baselines — the agent has to overcome that handicap
by definition. (A real long-term hold of SPY with no rebalancing also has
near-zero tax friction in practice, so this isn't an unreasonable assumption.)

Run module directly to exercise self-tests:
    python3 -m analysis.simulator.baseline
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .data import PriceLookup


BASELINE_TICKERS = ["SPY", "QQQ", "TMFC"]


@dataclass
class BaselineResult:
    """The buy-and-hold path of one ETF: $X at start, marked daily."""
    ticker: str
    start_date: date
    start_price: float
    initial_capital: float
    shares: float

    def value_on(self, prices: PriceLookup, d: date) -> float:
        """Mark-to-market value on date `d`. Returns 0 if no price available."""
        p = prices.price_on(self.ticker, d)
        if p is None:
            return 0.0
        return self.shares * p


def initialize_baselines(
    initial_capital: float,
    start_date: date,
    prices: PriceLookup,
) -> dict[str, BaselineResult]:
    """For each baseline ticker (SPY/QQQ/TMFC), buy `initial_capital` worth
    of shares at the close on `start_date`. Returns a dict keyed by ticker.

    Skips any baseline ticker not present in the price cache (logs a warning
    and excludes it). Use that to gracefully handle missing TMFC data, etc.
    """
    results: dict[str, BaselineResult] = {}
    for ticker in BASELINE_TICKERS:
        if not prices.has_ticker(ticker):
            print(f"WARNING: {ticker} not in price cache — baseline excluded. "
                  f"Run fetch_prices_for_tickers.py {ticker} on the laptop.")
            continue
        start_price = prices.price_on(ticker, start_date)
        if start_price is None or start_price <= 0:
            print(f"WARNING: no {ticker} price near {start_date} — baseline excluded.")
            continue
        shares = initial_capital / start_price
        results[ticker] = BaselineResult(
            ticker=ticker,
            start_date=start_date,
            start_price=start_price,
            initial_capital=initial_capital,
            shares=shares,
        )
    return results


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _selftest():
    from datetime import timedelta
    pl = PriceLookup.from_cache()
    # Find a baseline ticker present in cache
    available = [t for t in BASELINE_TICKERS if pl.has_ticker(t)]
    if not available:
        print("SKIP: no baseline ETFs in price cache. "
              "Run fetch_prices_for_tickers.py SPY QQQ TMFC.")
        return
    # Use SPY first (always present in our cache historically)
    sample = available[0]
    first = pl.first_date(sample)
    last = pl.last_date(sample)
    if first is None or last is None or last - first < timedelta(days=30):
        print(f"SKIP: insufficient {sample} history.")
        return
    # Initialize $100k buy of `sample` near a real start date
    start = first + timedelta(days=10)
    while pl.price_on(sample, start) is None and start < last:
        start = start + timedelta(days=1)
    baselines = initialize_baselines(100_000, start, pl)
    assert sample in baselines
    b = baselines[sample]
    assert abs(b.value_on(pl, start) - 100_000) < 1.0  # close to capital at start
    # Value at the last available date should be > 0
    v_end = b.value_on(pl, last)
    assert v_end > 0
    print(f"baseline.py self-tests passed "
          f"({sample}: ${100_000:.0f} on {start} → ${v_end:,.0f} on {last})")


if __name__ == "__main__":
    _selftest()
