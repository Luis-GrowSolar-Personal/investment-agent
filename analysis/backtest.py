#!/usr/bin/env python3
"""
Portfolio Concentration Backtest
Starting portfolio: March 24, 2020 | $2,191,066 across 7 accounts
Rules: Quarterly rebalancing, flat concentration cap (3 scenarios: 15/20/25%)
Tax: 20% federal LTCG on gains in taxable accounts, 0% in tax-advantaged
Author: Generated for investment backtest analysis
"""

import json, sys, os
from datetime import datetime, date, timedelta
from collections import defaultdict

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

# ── PORTFOLIO DATA ────────────────────────────────────────────────────────────

ACCOUNTS = {
    'Taxable_AL2': {'taxable': True, 'positions': {
        'AAPL':60,'AMZN':15,'APPN':397,'BYND':200,'COUP':111,
        'ENPH':829,'FIVN':207,'FLGT':2698,'GOOGL':13,'MDB':216,
        'MSFT':102,'NFLX':42,'NVTA':1094,'RUBI':4865,'SEDG':321,
        'SHOP':66,'TSLA':55,'TTD':157,'ZM':202
    }},
    'Taxable_AL1': {'taxable': True, 'positions': {
        'APPN':80,'BLX':44,'CARE':72,'COUP':30,'CWGL':126,
        'ENPH':35250,'FIVN':40,'HMTV':109,'ICBK':41,'KNSL':33,
        'MDB':6,'NRC':40,'NRIM':34,'NVEE':27,'OTCM':46,'PJT':46,
        'QTWO':26,'SHOP':4,'TCX':22,'TRUP':71,'TTD':43,'VRNS':38,
        'WIFI':46,'WINA':9
    }},
    'Roth_IRA_L': {'taxable': False, 'positions': {
        'AMZN':2,'ENPH':117,'SHOP':8,'TTD':18,'ZM':25
    }},
    'Roth_IRA_A': {'taxable': False, 'positions': {
        'AMZN':2,'ENPH':87,'SHOP':8,'TTD':18,'ZM':26
    }},
    'IRA_L': {'taxable': False, 'positions': {
        'AAPL':33,'AMZN':4,'APPN':29,'BZUN':128,'CBZ':80,'COUP':16,
        'CRSP':133,'ENPH':2680,'ETSY':51,'FIVN':24,'HUBS':13,'KNSL':20,
        'MDB':102,'MMYT':221,'NFLX':20,'NVEE':12,'PJT':17,'QTWO':17,
        'RUBI':274,'SFIX':189,'SHOP':11,'TRUP':27,'TSLA':67,'TTD':10,
        'VBK':10,'VRNS':15,'WD':113
    }},
    'IRA_L2': {'taxable': False, 'positions': {
        'AAPL':32,'AMZN':8,'APPN':202,'BYND':108,'COUP':59,'ENPH':512,
        'FIVN':112,'FLGT':1688,'GOOGL':7,'MDB':132,'MSFT':55,'NFLX':23,
        'NVTA':566,'RUBI':2918,'SEDG':193,'SHOP':43,'TSLA':34,'TTD':88,'ZM':120
    }},
    'IRA_A': {'taxable': False, 'positions': {
        'AMZN':3,'ENPH':281,'SHOP':21,'TTD':46,'ZM':62
    }}
}

STARTING_PRICES = {
    'AAPL':246.88,'AMZN':1940.10,'APPN':38.00,'BLX':12.56,'BYND':67.43,
    'BZUN':26.00,'CARE':8.55,'CBZ':18.97,'COUP':139.76,'CRSP':42.66,
    'CWGL':5.10,'ENPH':34.34,'ETSY':38.13,'FIVN':71.00,'FLGT':9.91,
    'GOOGL':1130.01,'HMTV':8.98,'HUBS':129.36,'ICBK':14.54,'KNSL':94.87,
    'MDB':136.43,'MMYT':12.35,'MSFT':148.34,'NFLX':357.32,'NRC':45.09,
    'NRIM':24.98,'NVEE':32.70,'NVTA':12.15,'OTCM':24.50,'PJT':32.76,
    'QTWO':56.60,'RUBI':5.63,'SEDG':85.31,'SFIX':14.48,'SHOP':430.00,
    'TCX':50.17,'TRUP':28.92,'TSLA':505.00,'TTD':194.00,'VBK':142.00,
    'VRNS':60.11,'WD':38.90,'WIFI':9.36,'WINA':129.78,'ZM':135.18
}

# Corporate actions: ticker -> (action_type, date, cash_per_share)
# RUBI: merged into MGNI April 2020. Exchange ratio ~0.22 MGNI per RUBI share
# COUP: taken private Dec 2022 at $81/share
# WIFI: acquired April 2021 at $14/share
# HMTV: went dark / delisted ~2022, treat as $0 from 2022-01-01
# NVTA: bankrupt 2023, treat as $0 from 2023-09-01
# CWGL: acquired ~2021 by Entergy, very small
# CARE: tiny illiquid stock, treat as last traded price
CORPORATE_ACTIONS = {
    'COUP': ('cash_acquired', '2022-12-12', 81.00),
    'WIFI': ('cash_acquired', '2021-04-05', 14.00),
    'HMTV': ('delisted',      '2022-01-01', 0.0),
    'NVTA': ('delisted',      '2023-09-01', 0.0),
    'RUBI': ('stock_merger',  '2020-04-08', None),  # became MGNI at 0.22 ratio
}

LTCG_RATE = 0.20
START_DATE = date(2020, 3, 24)

# ── PRICE FETCHING ────────────────────────────────────────────────────────────

def fetch_prices(cache_file='price_cache.json'):
    """Fetch all required prices. Uses cache if available."""
    if os.path.exists(cache_file):
        print(f"Loading prices from cache: {cache_file}")
        with open(cache_file) as f:
            raw = json.load(f)
        prices = {}
        for ticker, data in raw.items():
            prices[ticker] = {date.fromisoformat(k): v for k, v in data.items()}
        return prices

    if not HAS_YFINANCE:
        print("ERROR: yfinance not installed. Run: pip install yfinance pandas numpy")
        sys.exit(1)

    tickers = list(STARTING_PRICES.keys()) + ['MGNI', 'SPY']
    print(f"Fetching prices for {len(tickers)} tickers from 2020-03-20 to today...")
    print("This will take 1-2 minutes...")

    prices = {}
    end = datetime.today().strftime('%Y-%m-%d')

    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}", end='', flush=True)
        try:
            df = yf.download(ticker, start='2020-03-20', end=end,
                           progress=False, auto_adjust=True)
            if df is None or len(df) == 0:
                print(" ✗ no data")
                continue

            # Handle MultiIndex columns: ('Close', 'AAPL') in newer yfinance
            if isinstance(df.columns, pd.MultiIndex):
                # Get the Close column for this ticker
                try:
                    closes = df[('Close', ticker)].dropna()
                except KeyError:
                    # Try Adj Close
                    try:
                        closes = df[('Adj Close', ticker)].dropna()
                    except KeyError:
                        print(" ✗ no Close column")
                        continue
            else:
                # Single-level columns (older yfinance)
                closes = df['Close'].dropna()

            price_dict = {}
            for idx in closes.index:
                # Convert DatetimeIndex entry to date
                try:
                    d = pd.Timestamp(idx).date()
                except Exception:
                    try:
                        d = idx.date()
                    except Exception:
                        continue
                # Get scalar value
                v = closes.loc[idx]
                try:
                    v = float(v)
                except Exception:
                    continue
                price_dict[d] = v

            if price_dict:
                prices[ticker] = price_dict
                print(f" ✓ {len(price_dict)} days")
            else:
                print(" ✗ no usable data")
        except Exception as e:
            print(f" ✗ {str(e)[:50]}")

    # Cache for future runs
    raw = {t: {str(d): v for d, v in data.items()} for t, data in prices.items()}
    with open(cache_file, 'w') as f:
        json.dump(raw, f)
    print(f"\nPrices cached to {cache_file}")
    return prices

def get_price(prices, ticker, target_date):
    """Get closing price on or before target_date."""
    if ticker not in prices:
        return None
    data = prices[ticker]
    # Walk back up to 5 trading days to find a price
    for delta in range(6):
        d = target_date - timedelta(days=delta)
        if d in data:
            return data[d]
    return None

# ── REBALANCING DATES ─────────────────────────────────────────────────────────

def get_rebalance_dates():
    """Generate quarterly rebalance dates from Q2 2020 through today."""
    dates = []
    # First rebalance: start of Q2 2020
    quarters = []
    year = 2020
    quarter_starts = [(4,1),(7,1),(10,1),(1,1)]
    q_idx = 0  # start at April 2020
    current = date(2020, 4, 1)
    today = date.today()
    while current <= today:
        dates.append(current)
        # Next quarter
        m = current.month
        y = current.year
        if m == 1:   next_d = date(y, 4, 1)
        elif m == 4: next_d = date(y, 7, 1)
        elif m == 7: next_d = date(y, 10, 1)
        else:        next_d = date(y+1, 1, 1)
        current = next_d
    return dates

# ── PORTFOLIO STATE ───────────────────────────────────────────────────────────

class PortfolioState:
    def __init__(self):
        # shares[account][ticker] = fractional shares
        self.shares = {}
        # cost_basis[account][ticker] = avg cost per share
        self.cost_basis = {}
        # cash[account] = available cash (from trims, after tax)
        self.cash = {}
        # total_taxes_paid
        self.taxes_paid = 0.0
        # log of all rebalance events
        self.rebalance_log = []

    def initialize(self):
        for acct, data in ACCOUNTS.items():
            self.shares[acct] = {}
            self.cost_basis[acct] = {}
            self.cash[acct] = 0.0
            for ticker, shares in data['positions'].items():
                self.shares[acct][ticker] = float(shares)
                self.cost_basis[acct][ticker] = STARTING_PRICES.get(ticker, 0.0)

    def portfolio_value(self, prices, target_date):
        """Total portfolio value across all accounts."""
        total = 0.0
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                price = get_price(prices, ticker, target_date)
                if price:
                    total += shares * price
            total += self.cash[acct]
        return total

    def position_values(self, prices, target_date):
        """Dict of ticker -> total value across all accounts."""
        vals = defaultdict(float)
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                price = get_price(prices, ticker, target_date)
                if price and shares > 0:
                    vals[ticker] += shares * price
        return dict(vals)

    def apply_corporate_action(self, ticker, action, action_date, cash_per_share, prices):
        """Handle acquisitions, delistings, mergers."""
        for acct in self.shares:
            if ticker in self.shares[acct] and self.shares[acct][ticker] > 0:
                shares = self.shares[acct][ticker]
                if action == 'cash_acquired':
                    proceeds = shares * cash_per_share
                    gain = shares * max(0, cash_per_share - self.cost_basis[acct].get(ticker, 0))
                    if ACCOUNTS[acct]['taxable']:
                        tax = gain * LTCG_RATE
                        self.taxes_paid += tax
                        proceeds -= tax
                    self.cash[acct] += proceeds
                    self.shares[acct][ticker] = 0.0
                elif action == 'delisted':
                    self.shares[acct][ticker] = 0.0
                elif action == 'stock_merger' and ticker == 'RUBI':
                    # RUBI -> MGNI at 0.22 ratio
                    mgni_shares = shares * 0.22
                    self.shares[acct]['MGNI'] = self.shares[acct].get('MGNI', 0) + mgni_shares
                    rubi_basis = self.cost_basis[acct].get('RUBI', 0)
                    self.cost_basis[acct]['MGNI'] = rubi_basis / 0.22
                    self.shares[acct][ticker] = 0.0

# ── BACKTEST ENGINE ───────────────────────────────────────────────────────────

def run_backtest(cap_pct, prices, verbose=False):
    """
    Run a single backtest scenario.
    cap_pct: maximum single position as fraction of total portfolio (e.g. 0.15)
    Returns: list of (date, portfolio_value, taxes_paid_cumulative)
    """
    state = PortfolioState()
    state.initialize()

    rebalance_dates = get_rebalance_dates()
    history = [(START_DATE, state.portfolio_value(prices, START_DATE), 0.0)]

    # Track which corporate actions have been applied
    actions_applied = set()

    prev_date = START_DATE

    for rebal_date in rebalance_dates:

        # Apply any corporate actions that occurred since last rebalance
        for ticker, (action, action_date_str, cash_per_share) in CORPORATE_ACTIONS.items():
            action_date = date.fromisoformat(action_date_str)
            if prev_date < action_date <= rebal_date and ticker not in actions_applied:
                state.apply_corporate_action(ticker, action, action_date, cash_per_share, prices)
                actions_applied.add(ticker)
                if verbose:
                    print(f"  Corporate action: {ticker} {action} on {action_date_str}")

        # Get current portfolio value
        total_value = state.portfolio_value(prices, rebal_date)
        if total_value <= 0:
            continue

        # Get position values
        pos_vals = state.position_values(prices, rebal_date)
        # Add cash as part of total but don't trim cash
        total_invested = sum(pos_vals.values())

        # Find positions exceeding cap
        cap_value = total_value * cap_pct
        trims = {}
        for ticker, val in pos_vals.items():
            if val > cap_value:
                trims[ticker] = val - cap_value  # amount to trim in dollars

        if trims and verbose:
            print(f"\nRebalance {rebal_date}: total=${total_value:,.0f}, cap={cap_pct*100:.0f}%")
            for t, v in trims.items():
                print(f"  Trim {t}: sell ${v:,.0f} ({pos_vals[t]/total_value*100:.1f}% -> {cap_pct*100:.0f}%)")

        # Execute trims
        total_proceeds_after_tax = 0.0
        trim_log = []

        for ticker, trim_amount in trims.items():
            price = get_price(prices, ticker, rebal_date)
            if not price:
                continue

            shares_to_sell = trim_amount / price

            # Distribute sells proportionally across accounts that hold this ticker
            # Prioritize tax-advantaged accounts first to minimize tax
            acct_holdings = []
            for acct in state.shares:
                sh = state.shares[acct].get(ticker, 0)
                if sh > 0:
                    acct_holdings.append((acct, sh, ACCOUNTS[acct]['taxable']))

            # Sort: tax-advantaged first (taxable=False first)
            acct_holdings.sort(key=lambda x: x[2])

            shares_remaining = shares_to_sell
            for acct, avail_shares, is_taxable in acct_holdings:
                if shares_remaining <= 0:
                    break
                sell_shares = min(shares_remaining, avail_shares)
                proceeds = sell_shares * price

                if is_taxable:
                    basis = state.cost_basis[acct].get(ticker, 0)
                    gain = sell_shares * max(0, price - basis)
                    tax = gain * LTCG_RATE
                    state.taxes_paid += tax
                    net_proceeds = proceeds - tax
                else:
                    net_proceeds = proceeds

                state.shares[acct][ticker] = state.shares[acct].get(ticker, 0) - sell_shares
                state.cash[acct] += net_proceeds
                total_proceeds_after_tax += net_proceeds
                shares_remaining -= sell_shares

            trim_log.append({'ticker': ticker, 'amount': trim_amount,
                            'proceeds_after_tax': total_proceeds_after_tax})

        # Redeploy cash: proportional to current holdings in each account
        for acct in state.shares:
            if state.cash[acct] <= 0:
                continue

            cash_to_deploy = state.cash[acct]
            # Get current values of positions in this account
            acct_vals = {}
            for ticker, shares in state.shares[acct].items():
                if shares > 0:
                    price = get_price(prices, ticker, rebal_date)
                    if price:
                        acct_vals[ticker] = shares * price

            total_acct_val = sum(acct_vals.values())
            if total_acct_val <= 0:
                continue

            # Buy proportionally
            for ticker, val in acct_vals.items():
                weight = val / total_acct_val
                buy_amount = cash_to_deploy * weight
                price = get_price(prices, ticker, rebal_date)
                if price and price > 0:
                    new_shares = buy_amount / price
                    old_shares = state.shares[acct].get(ticker, 0)
                    old_basis = state.cost_basis[acct].get(ticker, 0)
                    # Update average cost basis
                    if old_shares + new_shares > 0:
                        state.cost_basis[acct][ticker] = (
                            (old_shares * old_basis + new_shares * price) /
                            (old_shares + new_shares)
                        )
                    state.shares[acct][ticker] = old_shares + new_shares

            state.cash[acct] = 0.0

        # Record history
        new_total = state.portfolio_value(prices, rebal_date)
        history.append((rebal_date, new_total, state.taxes_paid))
        prev_date = rebal_date

    # Final value at today
    today = date.today()
    final_value = state.portfolio_value(prices, today)
    history.append((today, final_value, state.taxes_paid))

    return history, state.taxes_paid

# ── BUY AND HOLD BENCHMARK ────────────────────────────────────────────────────

def run_buy_and_hold(prices):
    """No rebalancing, no trimming. Just hold the starting portfolio."""
    state = PortfolioState()
    state.initialize()

    # Apply corporate actions at their dates
    all_dates = get_rebalance_dates() + [date.today()]
    actions_applied = set()
    prev_date = START_DATE
    history = [(START_DATE, state.portfolio_value(prices, START_DATE), 0.0)]

    for d in all_dates:
        for ticker, (action, action_date_str, cash_per_share) in CORPORATE_ACTIONS.items():
            action_date = date.fromisoformat(action_date_str)
            if prev_date < action_date <= d and ticker not in actions_applied:
                state.apply_corporate_action(ticker, action, action_date, cash_per_share, prices)
                actions_applied.add(ticker)
        val = state.portfolio_value(prices, d)
        history.append((d, val, state.taxes_paid))
        prev_date = d

    return history

# ── SPY BENCHMARK ─────────────────────────────────────────────────────────────

def spy_benchmark(prices, starting_value):
    """What would $2.19M in SPY have grown to?"""
    spy_start = get_price(prices, 'SPY', START_DATE)
    if not spy_start:
        return None

    history = []
    all_dates = [START_DATE] + get_rebalance_dates() + [date.today()]
    shares = starting_value / spy_start

    for d in all_dates:
        price = get_price(prices, 'SPY', d)
        if price:
            history.append((d, shares * price))

    return history

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("PORTFOLIO CONCENTRATION BACKTEST")
    print("Starting: March 24, 2020 | $2,191,066")
    print("Rule: Quarterly rebalancing, LTCG tax 20%, FL resident")
    print("=" * 60)

    # Load prices
    prices = fetch_prices()

    # Verify starting date price
    enph_start = get_price(prices, 'ENPH', START_DATE)
    print(f"\nVerification: ENPH on {START_DATE} = ${enph_start:.2f} (expected $34.34)")

    starting_value = 2_191_066.0

    # Run three cap scenarios
    results = {}
    caps = [0.15, 0.20, 0.25]
    cap_labels = ['15% cap', '20% cap', '25% cap']

    for cap, label in zip(caps, cap_labels):
        print(f"\nRunning scenario: {label}...")
        history, total_tax = run_backtest(cap, prices, verbose=False)
        results[label] = {'history': history, 'total_tax': total_tax}
        final = history[-1][1]
        gain = (final / starting_value - 1) * 100
        print(f"  Final value: ${final:,.0f} | Gain: {gain:.1f}% | Tax paid: ${total_tax:,.0f}")

    # Buy and hold (no rebalancing)
    print("\nRunning: Buy and Hold (no rebalancing)...")
    bh_history = run_buy_and_hold(prices)
    bh_final = bh_history[-1][1]
    bh_gain = (bh_final / starting_value - 1) * 100
    print(f"  Final value: ${bh_final:,.0f} | Gain: {bh_gain:.1f}%")

    # SPY benchmark
    spy_hist = spy_benchmark(prices, starting_value)
    if spy_hist:
        spy_final = spy_hist[-1][1]
        spy_gain = (spy_final / starting_value - 1) * 100
        print(f"\nSPY benchmark: ${spy_final:,.0f} | Gain: {spy_gain:.1f}%")

    # Print full results table
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)
    print(f"{'Scenario':<25} {'Final Value':>14} {'Total Return':>13} {'Tax Paid':>12}")
    print("-" * 65)
    print(f"{'Buy & Hold (actual proxy)':<25} ${bh_final:>12,.0f} {bh_gain:>11.1f}%  {'$0':>12}")
    for label in cap_labels:
        r = results[label]
        final = r['history'][-1][1]
        gain = (final / starting_value - 1) * 100
        tax = r['total_tax']
        print(f"{label:<25} ${final:>12,.0f} {gain:>11.1f}%  ${tax:>10,.0f}")
    if spy_hist:
        print(f"{'SPY benchmark':<25} ${spy_final:>12,.0f} {spy_gain:>11.1f}%  {'N/A':>12}")

    # Save detailed results to CSV
    print("\nSaving detailed history to backtest_results.csv...")
    rows = []
    # Build combined timeline
    all_dates_set = set()
    for label in cap_labels:
        for d, v, t in results[label]['history']:
            all_dates_set.add(d)
    for d, v in (spy_hist or []):
        all_dates_set.add(d)
    for d, v, t in bh_history:
        all_dates_set.add(d)

    # Convert histories to dicts
    bh_dict = {d: v for d, v, t in bh_history}
    cap_dicts = {label: {d: v for d, v, t in results[label]['history']} for label in cap_labels}
    spy_dict = {d: v for d, v in (spy_hist or [])}

    for d in sorted(all_dates_set):
        row = {'date': str(d)}
        row['buy_hold'] = bh_dict.get(d, '')
        for label in cap_labels:
            key = label.replace(' ', '_').replace('%', 'pct')
            row[key] = cap_dicts[label].get(d, '')
        row['spy'] = spy_dict.get(d, '')
        rows.append(row)

    with open('backtest_results.csv', 'w') as f:
        headers = ['date', 'buy_hold', '15pct_cap', '20pct_cap', '25pct_cap', 'spy']
        f.write(','.join(headers) + '\n')
        for row in rows:
            vals = [str(row.get(h, '')) for h in headers]
            f.write(','.join(vals) + '\n')

    print("Results saved to backtest_results.csv")
    print("\nNow reveal your actual portfolio value to complete the comparison.")

if __name__ == '__main__':
    main()
