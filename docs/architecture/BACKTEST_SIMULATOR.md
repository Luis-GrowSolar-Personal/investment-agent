# Backtest Simulator — Phase 1 Design

## Purpose

Prove (or disprove) that the agent's analyst + trend layer + allocator stack
produces better portfolio outcomes than passive baselines (SPY, QQQ, TMFC)
over a multi-year horizon. The bar: beat all three on absolute return with
similar or slightly higher max drawdowns.

This is the first quantitative answer to *"is this agent worth using?"* —
per-call accuracy (51% on the v2.2 backtest) doesn't guarantee portfolio
outperformance. We need to wire decisions to dollars to find out.

## Scope

- Single starting date (sweep across multiple later)
- Two account types: **taxable** and **tax-advantaged**
- Universe: every ticker in the watchlist + portfolio with ≥3 prior transcripts
  by the start date (the trend layer's minimum history requirement)
- Decisions driven by the post-trend-layer `final_action` field (already
  computed on every Analysis row in the DB)
- Tax-aware from day one (15% STCG, 15% LTCG, FL no state tax)
- Output: portfolio value over time + transaction log + comparison vs baselines

## Architecture

### Core loop: daily mark-to-market, event-driven decisions

```
for day in start_date..end_date:
    if day is a call_date for any ticker T:
        for each call on this day:
            apply_allocator_decision(T, day, call.final_action, call.recommended_size)
    if day is December 31:
        run_year_end_tax(year)
    record_portfolio_value(day)
```

Daily granularity is needed for proper max-drawdown tracking. Decisions are
event-driven (only fire on call dates), but mark-to-market happens daily so
we have a continuous portfolio-value time series.

## Allocator decision rules (Phase 1)

The simplest rules that match CLAUDE.md's intent:

### Add (final_action = "Add")

```
target_pct = min(recommended_size, type_cap)
  where type_cap = 35 if typeClassification == "A" else 50

target_$  = target_pct * current_portfolio_value
current_$ = current_position_value(T)
delta_$   = target_$ - current_$

if delta_$ > 0:
    cash_available = cash_in_target_account
    buy_$ = min(delta_$, cash_available)
    buy_shares = floor(buy_$ / day_close_price)
    create_lot(account=target_account, ticker=T, shares=buy_shares,
               cost_basis=day_close_price, date=day)
elif delta_$ <= 0:
    no_op  # already at/above target
```

### Hold (final_action = "Hold")

No action. Position stays as-is.

### Trim (final_action = "Trim")

```
shares_to_sell = floor(current_shares * 0.25)  # sell 25% of position
sell_lots(T, shares_to_sell, FIFO_order, prefer_tax_advantaged_first)
```

(25% per quarterly call is roughly a slow-roll exit — 4 consecutive Trims
would liquidate ~70% over a year. If the agent escalates from Trim to Exit,
the remaining position sells at once.)

### Exit (final_action = "Exit")

```
sell_all_lots(T, prefer_tax_advantaged_first)
```

### Type cap rationale

- Type A (single-driver, e.g. AMPX battery thesis): hard cap 35%
- Type B (multi-driver platform, e.g. NVDA AI ecosystem): hard cap 50%

If `typeClassification` is missing on a row, default to Type A (35%).

## Account routing

Two accounts: **taxable** and **tax_advantaged**. Each holds its own cash
balance and positions.

- **Buys** route to `tax_advantaged` first (shelter gains), fall back to
  `taxable` if insufficient cash.
- **Sells (Trim/Exit)** route to `tax_advantaged` first (zero tax cost on
  realized gains), fall back to `taxable`. Within an account, FIFO across lots.

## Cash management

- Initial state: user-specified cash amount per account.
- Cash flows: buy decrements, sell credits.
- No external dividends modeled (per-ticker dividends are negligible in our
  universe; baseline ETFs use Adj Close which is total return).
- Cash earns no interest (could add a money-market floor later — Phase 2+).

## Lot tracking & tax handling

### Lot model

Each buy creates a `Lot` record:
```
Lot:
  account: "taxable" | "tax_advantaged"
  ticker: str
  shares: float
  cost_basis_per_share: float
  acquired_date: date
```

### Sales

Sales are FIFO (IRS default when no specific lot is identified):
- Identify oldest lot in target account first
- If multiple accounts to sell from (Trim/Exit), drain `tax_advantaged` first
- Each sale produces a realized gain/loss row:
  ```
  realized_gain = shares_sold * (sale_price - cost_basis_per_share)
  is_long_term = (sale_date - acquired_date) >= 365 days
  ```

### Year-end tax

On December 31 (or last day of backtest if before EOY):
- Sum YTD realized gains in taxable account
- Net long-term and short-term gains separately (though both at 15% in our spec)
- Net losses can offset gains; net residual loss carries forward (no refund)
- `tax_owed = max(0, 0.15 * net_gain)`
- Withdraw `tax_owed` from taxable account cash
- If insufficient cash, liquidate positions FIFO to cover (taxable shortfall
  liquidation creates additional realized gains — recursive but rare)

### Tax-advantaged

No tax. Period. Simple to model.

## Universe management

Each ticker enters the universe on the date of its **first** transcript in
the DB. The simulator acts on every call from day one, even when the trend
layer can't yet produce a verdict (which requires ≥3 prior calls).

When the trend layer can't produce a verdict, `final_action` falls back to
the raw per-call recommendation (`apply_matrix` already does this — it
returns the per-call rec unchanged when `verdict is None`). So a fresh-IPO
ticker like EOSE or CSLR with only 1-2 transcripts gets simulated using
the per-call analyst's judgment until it accumulates enough history for
trend-layer overlay.

This is intentionally permissive. Pre-revenue / recently-public names are
exactly the cases where waiting 3 quarters before acting cedes the upside
window. The simulator follows the agent's call from day one and we live
with the consequences in the results.

## Baselines

Three buy-and-hold benchmarks, each starting with the same total capital
on `start_date`:

- **SPY** — broad market
- **QQQ** — NASDAQ-100, tech-tilted
- **TMFC** — Motley Fool 100, curated growth (overlap with our universe)

Each baseline buys one ETF on `start_date` at the close price (Adj Close,
total return), reinvests dividends implicitly, and holds to `end_date`.
No taxes, no rebalancing — pure buy-and-hold.

(The agent gets taxed; the baselines don't. This is conservative *for* the
agent — it has to overcome a tax handicap to beat passive holdings. If we
wanted apples-to-apples we'd model dividend tax on baselines, but the
asymmetry favors caution.)

## Output

### Per-day time series CSV

```
date, total_value, taxable_value, tax_advantaged_value, cash, n_positions,
spy_value, qqq_value, tmfc_value
```

### Transaction log CSV

```
date, ticker, action, account, shares, price, cost_basis, realized_gain,
holding_days, is_long_term
```

### Summary report

- Final portfolio value vs. each baseline ($ and %)
- Total return (CAGR if multi-year)
- Max drawdown vs. each baseline (peak-to-trough)
- Sharpe ratio (daily returns, annualized)
- Total tax paid
- Number of trades (buys vs sells)
- Per-ticker P&L contribution
- Days in market vs. days in cash

### Decision criterion (success/fail)

Pre-declared (avoiding post-hoc rationalization):

- **Pass**: agent beats SPY AND QQQ AND TMFC on absolute return; max drawdown
  no worse than the median baseline + 5pp.
- **Soft pass**: agent beats 2 of 3; close on the third (within 2pp); drawdown
  acceptable.
- **Fail**: anything else.

Run on multiple starting dates to test robustness. A strategy that beats on
one date but fails on others isn't an honest pass.

## File layout

```
analysis/simulator/
  __init__.py
  simulator.py    # core daily loop
  allocator.py    # decision rules
  tax.py          # lot tracking, year-end tax
  accounts.py     # Account, Lot, Portfolio classes
  baseline.py     # SPY/QQQ/TMFC buy-and-hold
  report.py       # output CSVs + summary text
  data.py         # load analyses + prices from local files / DB
```

Lives in `analysis/` because it reads from price_cache.json + the DB and
runs on the laptop (same network constraints as our other analysis tools).

## Edge cases

| Case | Behavior |
|---|---|
| Multiple calls same day | Process in any order; they're independent |
| Cash shortage on buy | Buy what we can, log a warning |
| Position with size=null + Add action | Use 35% default target (Type A) |
| Position already at target on Add | No-op |
| Trim a position with 0 shares | No-op, log warning |
| Year-end with insufficient taxable cash for tax | FIFO-liquidate to cover |
| Last day before backtest end | Mark to market, no new trades |
| Ticker exits universe (e.g., delisted) | Treat as Exit at last available price |

## Open questions / Phase-2+ deferred

- **freshMoneyAllocation**: Phase 1 uses recommendedSize directly; Phase 2
  could moderate buys with the freshMoneyAllocation gradient.
- **48-hour waiting period for >30% positions** (CLAUDE.md item 5):
  not modeled in Phase 1. Trades execute on call_date.
- **Ratchet rule** (CLAUDE.md item 3): graduated trim → trim more → exit
  pattern. Phase 1 just uses Trim/Exit directly. Phase 2 could simulate
  the ratchet timing.
- **Wash sale rule**: ignored in Phase 1 (rare in this universe at this scale).
- **Dividend reinvestment**: ignored.
- **Slippage / spread**: ignored (close prices used).
- **Rebalancing on no-call days**: not done. Targets only adjust on call dates.

## Phase 1 success means

- The framework runs end-to-end on real data.
- We get a single number: agent vs SPY vs QQQ vs TMFC over the backtest window.
- We can iterate on the allocator (Phase 2-4) and re-measure.

It's the foundation, not the final answer.
