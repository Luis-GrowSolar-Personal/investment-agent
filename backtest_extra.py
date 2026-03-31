#!/usr/bin/env python3
"""
Extended backtest scenarios:
  Scenario 3: No ENPH — redistribute ENPH value equally across other positions
  Scenario 4: 50% ENPH cap — hold ENPH with conviction but with a ceiling
"""

import json, sys, os
from datetime import datetime, date, timedelta
from collections import defaultdict
import copy

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ── LOAD SHARED DATA ──────────────────────────────────────────────────────────

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

CORPORATE_ACTIONS = {
    'COUP': ('cash_acquired', '2022-12-12', 81.00),
    'WIFI': ('cash_acquired', '2021-04-05', 14.00),
    'HMTV': ('delisted',      '2022-01-01', 0.0),
    'NVTA': ('delisted',      '2023-09-01', 0.0),
    'RUBI': ('stock_merger',  '2020-04-08', None),
}

LTCG_RATE = 0.20
START_DATE = date(2020, 3, 24)

# ── PRICE LOADING ─────────────────────────────────────────────────────────────

def load_prices(cache_file='price_cache.json'):
    if not os.path.exists(cache_file):
        print(f"ERROR: {cache_file} not found. Run backtest.py first to build the cache.")
        sys.exit(1)
    print(f"Loading prices from cache: {cache_file}")
    with open(cache_file) as f:
        raw = json.load(f)
    prices = {}
    for ticker, data in raw.items():
        prices[ticker] = {date.fromisoformat(k): v for k, v in data.items()}
    return prices

def get_price(prices, ticker, target_date):
    if ticker not in prices:
        return None
    data = prices[ticker]
    for delta in range(6):
        d = target_date - timedelta(days=delta)
        if d in data:
            return data[d]
    return None

# ── REBALANCE DATES ───────────────────────────────────────────────────────────

def get_rebalance_dates():
    dates = []
    current = date(2020, 4, 1)
    today = date.today()
    while current <= today:
        dates.append(current)
        m, y = current.month, current.year
        if m == 1:   current = date(y, 4, 1)
        elif m == 4: current = date(y, 7, 1)
        elif m == 7: current = date(y, 10, 1)
        else:        current = date(y+1, 1, 1)
    return dates

# ── BUILD SCENARIO 3: NO ENPH ─────────────────────────────────────────────────

def build_no_enph_accounts():
    """
    Remove all ENPH shares. Redistribute the dollar value of ENPH
    equally across all other positions in each account.
    """
    accounts_no_enph = {}

    for acct_name, acct_data in ACCOUNTS.items():
        new_positions = {}
        enph_shares = acct_data['positions'].get('ENPH', 0)
        enph_value = enph_shares * STARTING_PRICES['ENPH']

        # All non-ENPH positions
        other_tickers = {k: v for k, v in acct_data['positions'].items() if k != 'ENPH'}

        if enph_value > 0 and other_tickers:
            # Distribute ENPH value equally across other positions
            value_per_ticker = enph_value / len(other_tickers)
            for ticker, shares in other_tickers.items():
                extra_shares = value_per_ticker / STARTING_PRICES[ticker]
                new_positions[ticker] = shares + extra_shares
        else:
            new_positions = dict(other_tickers)

        accounts_no_enph[acct_name] = {
            'taxable': acct_data['taxable'],
            'positions': new_positions
        }

    return accounts_no_enph

# ── PORTFOLIO STATE ───────────────────────────────────────────────────────────

class PortfolioState:
    def __init__(self, accounts_override=None):
        self.accounts_def = accounts_override or ACCOUNTS
        self.shares = {}
        self.cost_basis = {}
        self.cash = {}
        self.taxes_paid = 0.0

    def initialize(self):
        for acct, data in self.accounts_def.items():
            self.shares[acct] = {}
            self.cost_basis[acct] = {}
            self.cash[acct] = 0.0
            for ticker, shares in data['positions'].items():
                self.shares[acct][ticker] = float(shares)
                self.cost_basis[acct][ticker] = STARTING_PRICES.get(ticker, 0.0)

    def is_taxable(self, acct):
        return self.accounts_def[acct]['taxable']

    def portfolio_value(self, prices, target_date):
        total = 0.0
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                price = get_price(prices, ticker, target_date)
                if price:
                    total += shares * price
            total += self.cash[acct]
        return total

    def position_values(self, prices, target_date):
        vals = defaultdict(float)
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                price = get_price(prices, ticker, target_date)
                if price and shares > 0:
                    vals[ticker] += shares * price
        return dict(vals)

    def apply_corporate_actions(self, prev_date, rebal_date, actions_applied):
        for ticker, (action, action_date_str, cash_per_share) in CORPORATE_ACTIONS.items():
            action_date = date.fromisoformat(action_date_str)
            if prev_date < action_date <= rebal_date and ticker not in actions_applied:
                for acct in self.shares:
                    sh = self.shares[acct].get(ticker, 0)
                    if sh > 0:
                        if action == 'cash_acquired':
                            proceeds = sh * cash_per_share
                            gain = sh * max(0, cash_per_share - self.cost_basis[acct].get(ticker, 0))
                            if self.is_taxable(acct):
                                tax = gain * LTCG_RATE
                                self.taxes_paid += tax
                                proceeds -= tax
                            self.cash[acct] += proceeds
                            self.shares[acct][ticker] = 0.0
                        elif action == 'delisted':
                            self.shares[acct][ticker] = 0.0
                        elif action == 'stock_merger' and ticker == 'RUBI':
                            mgni = sh * 0.22
                            self.shares[acct]['MGNI'] = self.shares[acct].get('MGNI', 0) + mgni
                            self.cost_basis[acct]['MGNI'] = self.cost_basis[acct].get('RUBI', 0) / 0.22
                            self.shares[acct][ticker] = 0.0
                actions_applied.add(ticker)

    def trim_and_redeploy(self, prices, rebal_date, cap_pct,
                          enph_special_cap=None):
        """
        Trim positions exceeding cap_pct of total portfolio.
        If enph_special_cap is set, ENPH uses that cap instead.
        Redeploy proceeds proportionally within each account.
        Tax-advantaged accounts trimmed first to minimize tax.
        """
        total_value = self.portfolio_value(prices, rebal_date)
        if total_value <= 0:
            return

        pos_vals = self.position_values(prices, rebal_date)

        # Determine cap for each ticker
        trims = {}
        for ticker, val in pos_vals.items():
            if ticker == 'ENPH' and enph_special_cap is not None:
                this_cap = total_value * enph_special_cap
            else:
                this_cap = total_value * cap_pct
            if val > this_cap:
                trims[ticker] = val - this_cap

        for ticker, trim_amount in trims.items():
            price = get_price(prices, ticker, rebal_date)
            if not price:
                continue
            shares_to_sell = trim_amount / price

            # Collect accounts holding this ticker, tax-advantaged first
            acct_holdings = []
            for acct in self.shares:
                sh = self.shares[acct].get(ticker, 0)
                if sh > 0:
                    acct_holdings.append((acct, sh, self.is_taxable(acct)))
            acct_holdings.sort(key=lambda x: x[2])  # False (tax-adv) first

            shares_remaining = shares_to_sell
            for acct, avail, is_taxable in acct_holdings:
                if shares_remaining <= 0:
                    break
                sell = min(shares_remaining, avail)
                proceeds = sell * price
                if is_taxable:
                    basis = self.cost_basis[acct].get(ticker, 0)
                    gain = sell * max(0, price - basis)
                    tax = gain * LTCG_RATE
                    self.taxes_paid += tax
                    proceeds -= tax
                self.shares[acct][ticker] = self.shares[acct].get(ticker, 0) - sell
                self.cash[acct] += proceeds
                shares_remaining -= sell

        # Redeploy cash in each account proportionally
        for acct in self.shares:
            if self.cash[acct] <= 0:
                continue
            acct_vals = {}
            for ticker, sh in self.shares[acct].items():
                if sh > 0:
                    p = get_price(prices, ticker, rebal_date)
                    if p:
                        acct_vals[ticker] = sh * p
            total_acct = sum(acct_vals.values())
            if total_acct <= 0:
                continue
            cash = self.cash[acct]
            for ticker, val in acct_vals.items():
                weight = val / total_acct
                buy_amt = cash * weight
                p = get_price(prices, ticker, rebal_date)
                if p and p > 0:
                    new_sh = buy_amt / p
                    old_sh = self.shares[acct].get(ticker, 0)
                    old_b = self.cost_basis[acct].get(ticker, 0)
                    if old_sh + new_sh > 0:
                        self.cost_basis[acct][ticker] = (
                            (old_sh * old_b + new_sh * p) / (old_sh + new_sh)
                        )
                    self.shares[acct][ticker] = old_sh + new_sh
            self.cash[acct] = 0.0

# ── GENERIC BACKTEST RUNNER ───────────────────────────────────────────────────

def run_scenario(label, prices, cap_pct,
                 accounts_override=None, enph_special_cap=None):
    state = PortfolioState(accounts_override=accounts_override)
    state.initialize()

    rebal_dates = get_rebalance_dates()

    # Compute starting value directly from STARTING_PRICES to avoid
    # cache lookup gaps on the exact start date
    start_val = sum(
        float(shares) * STARTING_PRICES.get(ticker, 0.0)
        for acct_data in state.accounts_def.values()
        for ticker, shares in acct_data['positions'].items()
    )
    history = [(START_DATE, start_val, 0.0)]
    actions_applied = set()
    prev_date = START_DATE

    for rebal_date in rebal_dates:
        state.apply_corporate_actions(prev_date, rebal_date, actions_applied)
        state.trim_and_redeploy(prices, rebal_date, cap_pct,
                                enph_special_cap=enph_special_cap)
        val = state.portfolio_value(prices, rebal_date)
        history.append((rebal_date, val, state.taxes_paid))
        prev_date = rebal_date

    today = date.today()
    final = state.portfolio_value(prices, today)
    history.append((today, final, state.taxes_paid))

    gain = (final / start_val - 1) * 100
    print(f"  {label}: Final=${final:,.0f} | Start=${start_val:,.0f} | "
          f"Gain={gain:.1f}% | Tax=${state.taxes_paid:,.0f}")
    return history, state.taxes_paid, start_val

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("EXTENDED BACKTEST — SCENARIOS 3 & 4")
    print("=" * 65)

    prices = load_prices()

    # Verify
    enph_start = get_price(prices, 'ENPH', START_DATE)
    print(f"Verification: ENPH on {START_DATE} = ${enph_start:.2f} (expected $34.34)\n")

    # ── SCENARIO 3: No ENPH ───────────────────────────────────────────────────
    print("SCENARIO 3: No ENPH (value redistributed equally to other positions)")
    print("  Simulates: never having worked at / invested in ENPH")
    print("  Cap: 25% (best performing from Test 1 for fair comparison)")
    print()

    no_enph_accounts = build_no_enph_accounts()

    # Verify starting value is same
    total_no_enph = sum(
        shares * STARTING_PRICES.get(t, 0)
        for acct_data in no_enph_accounts.values()
        for t, shares in acct_data['positions'].items()
    )
    print(f"  Starting value (no ENPH): ${total_no_enph:,.0f} "
          f"(original: $2,191,066 — diff from rounding: "
          f"${abs(total_no_enph - 2191066):,.0f})")

    # Run at 15%, 20%, 25% caps for full comparison
    print("\n  Running three cap levels for No-ENPH portfolio:")
    no_enph_results = {}
    for cap, label in [(0.15,'No-ENPH 15%'), (0.20,'No-ENPH 20%'), (0.25,'No-ENPH 25%')]:
        hist, tax, sv = run_scenario(label, prices, cap,
                                     accounts_override=no_enph_accounts)
        no_enph_results[label] = {'history': hist, 'tax': tax, 'start': sv}

    # ── SCENARIO 4: 50% ENPH cap ──────────────────────────────────────────────
    print()
    print("SCENARIO 4: ENPH capped at 50%, all other positions capped at 25%")
    print("  Simulates: high conviction informed bet with a hard ceiling")
    print("  ENPH starts at 62.3% — agent trims to 50% at first rebalance")
    print()

    hist_50, tax_50, sv_50 = run_scenario(
        'ENPH 50% cap (others 25%)', prices,
        cap_pct=0.25, enph_special_cap=0.50
    )

    # Also run ENPH at 40% for comparison
    hist_40, tax_40, sv_40 = run_scenario(
        'ENPH 40% cap (others 25%)', prices,
        cap_pct=0.25, enph_special_cap=0.40
    )

    # ── FULL COMPARISON TABLE ─────────────────────────────────────────────────
    actual_value     = 3_225_224
    actual_adjusted  = 3_925_000   # midpoint of 3.8–4.0M adjusted estimate
    starting_value   = 2_191_066
    spy_final        = 6_357_823

    print()
    print("=" * 75)
    print("FULL COMPARISON TABLE")
    print("=" * 75)
    print(f"{'Scenario':<35} {'Final Value':>13} {'Gain':>8} {'Tax Paid':>12} {'vs Actual':>12}")
    print("-" * 75)

    def row(label, final, gain, tax, baseline=actual_value):
        diff = final - baseline
        sign = '+' if diff >= 0 else ''
        print(f"{label:<35} ${final:>12,.0f} {gain:>7.1f}% ${tax:>10,.0f} {sign}${diff:>10,.0f}")

    # Reference points
    print(f"{'YOUR ACTUAL (raw)':<35} ${actual_value:>12,.0f} {'47.2%':>8} {'unknown':>12} {'—':>12}")
    print(f"{'YOUR ACTUAL (adj. ~$700K out)':<35} ${actual_adjusted:>12,.0f} {'79.2%':>8} {'unknown':>12} {'—':>12}")
    print()

    # Test 1 results (from previous run)
    row('Buy & Hold (no rules)',       2_335_034,  6.6,       0)
    row('Test 1: 15% flat cap',        3_520_042, 60.7,  659_651)
    row('Test 1: 20% flat cap',        3_815_079, 74.1,  795_578)
    row('Test 1: 25% flat cap',        3_984_881, 81.9,  866_003)
    print()

    # Scenario 3: No ENPH
    for label, data in no_enph_results.items():
        final = data['history'][-1][1]
        gain = (final / data['start'] - 1) * 100
        row(f"Sc3: {label}", final, gain, data['tax'])
    print()

    # Scenario 4: ENPH special cap
    for hist, tax, sv, label in [
        (hist_50, tax_50, sv_50, 'Sc4: ENPH 50% cap (others 25%)'),
        (hist_40, tax_40, sv_40, 'Sc4: ENPH 40% cap (others 25%)')
    ]:
        final = hist[-1][1]
        gain = (final / sv - 1) * 100
        row(label, final, gain, tax)

    print()
    row('SPY benchmark', spy_final, 190.2, 0)

    # ── SAVE CSV ──────────────────────────────────────────────────────────────
    print()
    print("Saving to extended_backtest_results.csv...")

    all_histories = {
        'No-ENPH 15%': no_enph_results['No-ENPH 15%']['history'],
        'No-ENPH 20%': no_enph_results['No-ENPH 20%']['history'],
        'No-ENPH 25%': no_enph_results['No-ENPH 25%']['history'],
        'ENPH 50% cap': hist_50,
        'ENPH 40% cap': hist_40,
    }

    all_dates = set()
    for h in all_histories.values():
        for d, v, t in h:
            all_dates.add(d)

    dicts = {k: {d: v for d, v, t in h} for k, h in all_histories.items()}

    with open('extended_backtest_results.csv', 'w') as f:
        cols = ['date'] + list(all_histories.keys())
        f.write(','.join(cols) + '\n')
        for d in sorted(all_dates):
            vals = [str(d)] + [str(dicts[k].get(d, '')) for k in all_histories]
            f.write(','.join(vals) + '\n')

    print("Saved to extended_backtest_results.csv")
    print()
    print("KEY INSIGHT QUESTIONS:")
    print("  1. Does the No-ENPH portfolio beat or trail the capped ENPH portfolios?")
    print("     → Tells you how much of your return was ENPH vs. everything else")
    print("  2. Does ENPH at 50% cap beat your actual adjusted result?")
    print("     → Tells you the value of conviction + discipline vs. conviction alone")
    print("  3. How far are all scenarios from SPY?")
    print("     → Sets the bar for Layer 2 (thesis-driven) to clear")

if __name__ == '__main__':
    main()
