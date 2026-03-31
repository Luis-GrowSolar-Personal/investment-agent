#!/usr/bin/env python3
"""
Scenarios 5 & 6:
  Scenario 5: Substitute ENPH with NVDA or MSFT or SPY at same starting value
              Tests: luck vs skill — what if domain expertise pointed elsewhere?
  Scenario 6: Variable cap based on guidance accuracy signal
              Tests: does a simple thesis signal beat a fixed cap?
"""

import json, sys, os
from datetime import datetime, date, timedelta
from collections import defaultdict

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ── SHARED DATA ───────────────────────────────────────────────────────────────

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
    'VRNS':60.11,'WD':38.90,'WIFI':9.36,'WINA':129.78,'ZM':135.18,
    # Substitutes - prices on 2020-03-24
    'NVDA': 54.19,   # pre-split adjusted
    'SPY':  234.27,
}

CORPORATE_ACTIONS = {
    'COUP': ('cash_acquired', '2022-12-12', 81.00),
    'WIFI': ('cash_acquired', '2021-04-05', 14.00),
    'HMTV': ('delisted',      '2022-01-01', 0.0),
    'NVTA': ('delisted',      '2023-09-01', 0.0),
    'RUBI': ('stock_merger',  '2020-04-08', None),
}

LTCG_RATE  = 0.20
START_DATE = date(2020, 3, 24)
ENPH_TOTAL_SHARES = 39756
ENPH_START_VALUE  = ENPH_TOTAL_SHARES * 34.34  # $1,365,221

# ── ENPH GUIDANCE ACCURACY HISTORY ───────────────────────────────────────────
# Quarterly events that affect the variable cap
# Format: (date, event_type, cap_after)
# cap_after = new ENPH cap effective from this date forward
# Guidance met/beat -> hold at current cap
# First miss -> drop to 20%
# Second miss -> drop to 10%
# We model management credibility as detectable from public earnings data

ENPH_CAP_SCHEDULE = [
    # Phase 1: Strong execution, thesis intact — hold at 40%
    (date(2020,  4,  1), 'thesis_intact',    0.40),
    (date(2020,  7,  1), 'guidance_beat',    0.40),
    (date(2020, 10,  1), 'guidance_beat',    0.40),
    (date(2021,  1,  1), 'guidance_beat',    0.40),
    (date(2021,  4,  1), 'guidance_beat',    0.40),
    (date(2021,  7,  1), 'guidance_beat',    0.40),
    (date(2021, 10,  1), 'guidance_beat',    0.40),
    (date(2022,  1,  1), 'guidance_beat',    0.40),
    (date(2022,  4,  1), 'guidance_beat',    0.40),
    (date(2022,  7,  1), 'guidance_beat',    0.40),
    # Q4 2022: NEM3.0 announced, language shifts to qualitative
    # Amber signal — reduce cap modestly
    (date(2022, 10,  1), 'language_shift',   0.30),
    # Q1 2023: First guidance miss
    # Red signal — mandatory reduction
    (date(2023,  4,  1), 'first_miss',       0.20),
    # Q2 2023: Second consecutive miss
    # Exit signal — reduce to minimal holding
    (date(2023,  7,  1), 'second_miss',      0.10),
    # Q3 2023 onward: thesis broken
    (date(2023, 10,  1), 'thesis_broken',    0.05),
]

def get_enph_cap(rebal_date):
    """Return the ENPH-specific cap for a given rebalance date."""
    cap = 0.40  # default starting cap
    for d, event, new_cap in ENPH_CAP_SCHEDULE:
        if rebal_date >= d:
            cap = new_cap
        else:
            break
    return cap

# ── PRICE LOADING ─────────────────────────────────────────────────────────────

def load_prices(cache_file='price_cache.json'):
    if not os.path.exists(cache_file):
        print(f"ERROR: {cache_file} not found. Run backtest.py first.")
        sys.exit(1)
    print(f"Loading prices from cache: {cache_file}")
    with open(cache_file) as f:
        raw = json.load(f)
    prices = {}
    for ticker, data in raw.items():
        prices[ticker] = {date.fromisoformat(k): v for k, v in data.items()}
    return prices

def fetch_missing(prices, tickers):
    """Fetch any tickers not in cache."""
    missing = [t for t in tickers if t not in prices]
    if not missing:
        return prices
    try:
        import yfinance as yf
        end = datetime.today().strftime('%Y-%m-%d')
        for ticker in missing:
            print(f"  Fetching {ticker}...", end='', flush=True)
            try:
                df = yf.download(ticker, start='2020-03-20', end=end,
                               progress=False, auto_adjust=True)
                if df is not None and len(df) > 0:
                    if isinstance(df.columns, pd.MultiIndex):
                        closes = df[('Close', ticker)].dropna()
                    else:
                        closes = df['Close'].dropna()
                    price_dict = {}
                    for idx in closes.index:
                        try:
                            d = pd.Timestamp(idx).date()
                        except:
                            d = idx.date()
                        v = closes.loc[idx]
                        try:
                            v = float(v)
                        except:
                            continue
                        price_dict[d] = v
                    if price_dict:
                        prices[ticker] = price_dict
                        print(f" ✓ {len(price_dict)} days")
                    else:
                        print(" ✗ no data")
                else:
                    print(" ✗ no data")
            except Exception as e:
                print(f" ✗ {str(e)[:40]}")
    except ImportError:
        print("yfinance not available for fetching missing tickers")
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

# ── BUILD SUBSTITUTION ACCOUNTS ───────────────────────────────────────────────

def build_substitution_accounts(substitute_ticker, sub_start_price):
    """
    Replace all ENPH shares with equivalent dollar value in substitute_ticker.
    Non-ENPH positions unchanged.
    """
    accounts_sub = {}
    for acct_name, acct_data in ACCOUNTS.items():
        new_positions = {}
        for ticker, shares in acct_data['positions'].items():
            if ticker == 'ENPH':
                # Convert ENPH dollar value to substitute shares
                enph_value = shares * STARTING_PRICES['ENPH']
                sub_shares = enph_value / sub_start_price
                new_positions[substitute_ticker] = \
                    new_positions.get(substitute_ticker, 0) + sub_shares
            else:
                new_positions[ticker] = new_positions.get(ticker, 0) + shares
        accounts_sub[acct_name] = {
            'taxable': acct_data['taxable'],
            'positions': new_positions
        }
    return accounts_sub

# ── PORTFOLIO STATE ───────────────────────────────────────────────────────────

class PortfolioState:
    def __init__(self, accounts_def):
        self.accounts_def = accounts_def
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
                price = STARTING_PRICES.get(ticker, 0.0)
                self.cost_basis[acct][ticker] = price

    def is_taxable(self, acct):
        return self.accounts_def[acct]['taxable']

    def portfolio_value(self, prices, target_date):
        total = 0.0
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                p = get_price(prices, ticker, target_date)
                if p:
                    total += shares * p
            total += self.cash[acct]
        return total

    def position_values(self, prices, target_date):
        vals = defaultdict(float)
        for acct in self.shares:
            for ticker, shares in self.shares[acct].items():
                p = get_price(prices, ticker, target_date)
                if p and shares > 0:
                    vals[ticker] += shares * p
        return dict(vals)

    def apply_corporate_actions(self, prev_date, rebal_date, actions_applied):
        for ticker, (action, action_date_str, cash_ps) in CORPORATE_ACTIONS.items():
            action_date = date.fromisoformat(action_date_str)
            if prev_date < action_date <= rebal_date and ticker not in actions_applied:
                for acct in self.shares:
                    sh = self.shares[acct].get(ticker, 0)
                    if sh > 0:
                        if action == 'cash_acquired':
                            proceeds = sh * cash_ps
                            gain = sh * max(0, cash_ps - self.cost_basis[acct].get(ticker, 0))
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
                            self.shares[acct]['MGNI'] = \
                                self.shares[acct].get('MGNI', 0) + mgni
                            self.cost_basis[acct]['MGNI'] = \
                                self.cost_basis[acct].get('RUBI', 0) / 0.22
                            self.shares[acct][ticker] = 0.0
                actions_applied.add(ticker)

    def trim_and_redeploy(self, prices, rebal_date, default_cap,
                          special_caps=None):
        """
        special_caps: dict of ticker -> cap override (e.g. {'ENPH': 0.30})
        """
        total_value = self.portfolio_value(prices, rebal_date)
        if total_value <= 0:
            return

        pos_vals = self.position_values(prices, rebal_date)
        trims = {}
        for ticker, val in pos_vals.items():
            if special_caps and ticker in special_caps:
                cap = total_value * special_caps[ticker]
            else:
                cap = total_value * default_cap
            if val > cap:
                trims[ticker] = val - cap

        for ticker, trim_amount in trims.items():
            price = get_price(prices, ticker, rebal_date)
            if not price:
                continue
            shares_to_sell = trim_amount / price

            acct_holdings = []
            for acct in self.shares:
                sh = self.shares[acct].get(ticker, 0)
                if sh > 0:
                    acct_holdings.append((acct, sh, self.is_taxable(acct)))
            acct_holdings.sort(key=lambda x: x[2])

            shares_rem = shares_to_sell
            for acct, avail, is_taxable in acct_holdings:
                if shares_rem <= 0:
                    break
                sell = min(shares_rem, avail)
                proceeds = sell * price
                if is_taxable:
                    basis = self.cost_basis[acct].get(ticker, 0)
                    gain = sell * max(0, price - basis)
                    tax = gain * LTCG_RATE
                    self.taxes_paid += tax
                    proceeds -= tax
                self.shares[acct][ticker] = \
                    self.shares[acct].get(ticker, 0) - sell
                self.cash[acct] += proceeds
                shares_rem -= sell

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
                    old_b  = self.cost_basis[acct].get(ticker, 0)
                    if old_sh + new_sh > 0:
                        self.cost_basis[acct][ticker] = (
                            (old_sh * old_b + new_sh * p) /
                            (old_sh + new_sh)
                        )
                    self.shares[acct][ticker] = old_sh + new_sh
            self.cash[acct] = 0.0

# ── GENERIC RUNNER ────────────────────────────────────────────────────────────

def run_scenario(label, prices, accounts_def, default_cap,
                 special_caps_fn=None):
    """
    special_caps_fn: function(rebal_date) -> dict of ticker->cap overrides
    """
    state = PortfolioState(accounts_def)
    state.initialize()

    start_val = sum(
        float(sh) * STARTING_PRICES.get(t, 0.0)
        for acct_data in accounts_def.values()
        for t, sh in acct_data['positions'].items()
    )

    rebal_dates = get_rebalance_dates()
    history = [(START_DATE, start_val, 0.0)]
    actions_applied = set()
    prev_date = START_DATE

    for rebal_date in rebal_dates:
        state.apply_corporate_actions(prev_date, rebal_date, actions_applied)
        special_caps = special_caps_fn(rebal_date) if special_caps_fn else None
        state.trim_and_redeploy(prices, rebal_date, default_cap,
                                special_caps=special_caps)
        val = state.portfolio_value(prices, rebal_date)
        history.append((rebal_date, val, state.taxes_paid))
        prev_date = rebal_date

    today = date.today()
    final = state.portfolio_value(prices, today)
    history.append((today, final, state.taxes_paid))

    gain = (final / start_val - 1) * 100
    print(f"  {label:<45} Final=${final:>12,.0f} | "
          f"Gain={gain:>7.1f}% | Tax=${state.taxes_paid:>10,.0f}")
    return history, state.taxes_paid, start_val, final

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("SCENARIOS 5 & 6: SUBSTITUTION + VARIABLE CAP")
    print("=" * 70)

    prices = load_prices()

    # Fetch NVDA and SPY if not in cache
    prices = fetch_missing(prices, ['NVDA', 'SPY'])

    # Verify NVDA start price
    nvda_start = get_price(prices, 'NVDA', START_DATE)
    spy_start  = get_price(prices, 'SPY',  START_DATE)
    msft_start = get_price(prices, 'MSFT', START_DATE)

    print(f"\nStart prices on {START_DATE}:")
    print(f"  ENPH: $34.34  (known)")
    print(f"  NVDA: ${nvda_start:.2f}" if nvda_start else "  NVDA: not available")
    print(f"  MSFT: ${msft_start:.2f}" if msft_start else "  MSFT: not available")
    print(f"  SPY:  ${spy_start:.2f}"  if spy_start  else "  SPY:  not available")
    print(f"\n  ENPH starting value to substitute: ${ENPH_START_VALUE:,.0f}")

    starting_value = 2_191_066.0

    results = {}

    # ── SCENARIO 5a: ENPH -> NVDA ─────────────────────────────────────────────
    print("\n── SCENARIO 5: SUBSTITUTIONS (25% flat cap on all) ──")
    print("   Same starting $, same cap rules, different stock in the ENPH slot\n")

    if nvda_start:
        accts_nvda = build_substitution_accounts('NVDA', nvda_start)
        h, tax, sv, final = run_scenario(
            'Sc5a: ENPH->NVDA (25% cap)', prices, accts_nvda, 0.25)
        results['ENPH->NVDA 25%'] = (final, tax, sv)

        # Also run NVDA at 40% cap — same conviction level as ENPH
        h40, tax40, sv40, final40 = run_scenario(
            'Sc5b: ENPH->NVDA (40% cap)', prices, accts_nvda, 0.40)
        results['ENPH->NVDA 40%'] = (final40, tax40, sv40)

    if msft_start:
        accts_msft = build_substitution_accounts('MSFT', msft_start)
        h, tax, sv, final = run_scenario(
            'Sc5c: ENPH->MSFT (25% cap)', prices, accts_msft, 0.25)
        results['ENPH->MSFT 25%'] = (final, tax, sv)

    if spy_start:
        accts_spy = build_substitution_accounts('SPY', spy_start)
        h, tax, sv, final = run_scenario(
            'Sc5d: ENPH->SPY  (25% cap)', prices, accts_spy, 0.25)
        results['ENPH->SPY 25%'] = (final, tax, sv)

    # ── SCENARIO 6: VARIABLE CAP ON ENPH ─────────────────────────────────────
    print("\n── SCENARIO 6: VARIABLE CAP — ENPH cap adjusts with thesis health ──")
    print("   Cap schedule:")
    print("   Q1 2020–Q3 2022:  40%  (thesis intact, guidance met every quarter)")
    print("   Q4 2022:          30%  (NEM3.0 amber — language shift detected)")
    print("   Q1 2023:          20%  (first guidance miss — credibility debit)")
    print("   Q2 2023:          10%  (second miss — exit signal)")
    print("   Q3 2023+:          5%  (thesis broken)\n")

    def variable_caps(rebal_date):
        enph_cap = get_enph_cap(rebal_date)
        return {'ENPH': enph_cap}

    # Variable cap, other positions at 25%
    h_var, tax_var, sv_var, final_var = run_scenario(
        'Sc6a: Variable ENPH cap (others 25%)',
        prices, ACCOUNTS, 0.25,
        special_caps_fn=variable_caps
    )
    results['Variable ENPH cap'] = (final_var, tax_var, sv_var)

    # Variable cap, other positions at 40% (more aggressive on everything)
    h_var2, tax_var2, sv_var2, final_var2 = run_scenario(
        'Sc6b: Variable ENPH cap (others 40%)',
        prices, ACCOUNTS, 0.40,
        special_caps_fn=variable_caps
    )
    results['Variable ENPH cap (40% others)'] = (final_var2, tax_var2, sv_var2)

    # ── FULL COMPARISON TABLE ─────────────────────────────────────────────────
    actual_raw      = 3_225_224
    actual_adjusted = 3_925_000
    spy_final       = 6_357_823

    print()
    print("=" * 80)
    print("FULL COMPARISON TABLE — ALL SCENARIOS")
    print("=" * 80)
    print(f"{'Scenario':<45} {'Final':>12} {'Gain':>8} {'Tax':>12} {'vs Adj.':>12}")
    print("-" * 80)

    def row(label, final, gain, tax, baseline=actual_adjusted):
        diff = final - baseline
        sign = '+' if diff >= 0 else ''
        print(f"{label:<45} ${final:>11,.0f} {gain:>7.1f}% "
              f"${tax:>10,.0f} {sign}${diff:>10,.0f}")

    print(f"{'YOUR ACTUAL (adjusted ~$700K out)':<45} "
          f"${actual_adjusted:>11,.0f} {'~79%':>8} {'—':>13} {'—':>13}")
    print()

    # Reference scenarios from Test 1
    row('Test 1: 25% flat cap (original)',   3_984_881, 81.9,  866_003)
    row('Test 1: ENPH 40% cap (others 25%)', 4_077_136, 86.1, 1_086_613)
    print()

    # Scenario 5 substitutions
    for label, (final, tax, sv) in results.items():
        if 'ENPH->' in label or 'SPY' in label:
            gain = (final / sv - 1) * 100
            row(label, final, gain, tax)
    print()

    # Scenario 6 variable cap
    for label, (final, tax, sv) in results.items():
        if 'Variable' in label:
            gain = (final / sv - 1) * 100
            row(label, final, gain, tax)
    print()

    row('SPY benchmark (full portfolio)', spy_final, 190.2, 0)

    # ── KEY INSIGHTS ──────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("KEY QUESTIONS THIS ANSWERS:")
    print("=" * 80)

    if 'ENPH->NVDA 40%' in results:
        nvda_final = results['ENPH->NVDA 40%'][0]
        enph_40_final = 4_077_136
        diff = nvda_final - enph_40_final
        sign = '+' if diff >= 0 else ''
        print(f"\n1. LUCK VS SKILL — NVDA vs ENPH at same conviction (40% cap):")
        print(f"   ENPH 40% cap:  ${enph_40_final:>12,.0f}")
        print(f"   NVDA 40% cap:  ${nvda_final:>12,.0f}  ({sign}${abs(diff):,.0f})")
        print(f"   → The difference is the value of picking ENPH over NVDA,")
        print(f"     or NVDA over ENPH, with identical discipline applied.")

    if 'Variable ENPH cap' in results:
        var_final = results['Variable ENPH cap'][0]
        flat_final = 4_077_136
        diff = var_final - flat_final
        sign = '+' if diff >= 0 else ''
        print(f"\n2. VARIABLE VS FIXED CAP — does thesis signal add value?")
        print(f"   ENPH 40% fixed cap:     ${flat_final:>12,.0f}")
        print(f"   ENPH variable cap:      ${var_final:>12,.0f}  ({sign}${abs(diff):,.0f})")
        print(f"   → If variable > fixed: thesis-based sizing adds measurable value.")
        print(f"     If variable < fixed: the language shift signal was too late/aggressive.")

    print(f"\n3. HOW FAR FROM SPY?")
    print(f"   Best scenario so far vs SPY: "
          f"${spy_final - min(r[0] for r in results.values()):,.0f} gap to close")
    print(f"   This gap requires Layer 2: finding the NEXT high-conviction")
    print(f"   opportunity and deploying trim proceeds into it, not back into")
    print(f"   the existing portfolio.")

if __name__ == '__main__':
    main()
