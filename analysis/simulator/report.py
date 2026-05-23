"""
report.py — Output generation for backtest simulations.

Three artifacts:
  - daily.csv      — one row per day: portfolio value, cash, baselines
  - transactions.csv — one row per buy/sell with realized gain detail
  - summary.txt    — human-readable verdict (final values, drawdown, Sharpe,
                     pass/fail vs the declared decision criterion)
"""
from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .simulator import SimulationResult


@dataclass
class SummaryMetrics:
    final_portfolio_value: float
    portfolio_cagr: float                # annualized
    max_drawdown_pct: float              # peak-to-trough as a positive number
    sharpe_ratio: float                  # annualized, daily returns, rf=0
    total_tax_paid: float
    n_buys: int
    n_sells: int
    realized_gains_total: float
    baseline_finals: dict[str, float]
    baseline_cagrs: dict[str, float]
    baseline_drawdowns: dict[str, float]
    days_in_market: int


def write_daily_csv(result: SimulationResult, path: Path) -> None:
    baseline_keys = sorted(result.baselines.keys())
    fields = [
        "date", "total_value", "taxable_value", "tax_advantaged_value",
        "cash_total", "n_positions",
    ] + [f"{b}_value" for b in baseline_keys]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for snap in result.daily_snapshots:
            row = {
                "date": snap.date.isoformat(),
                "total_value": round(snap.total_value, 2),
                "taxable_value": round(snap.taxable_value, 2),
                "tax_advantaged_value": round(snap.tax_advantaged_value, 2),
                "cash_total": round(snap.cash_total, 2),
                "n_positions": snap.n_positions,
            }
            for b in baseline_keys:
                row[f"{b}_value"] = round(snap.baseline_values.get(b, 0.0), 2)
            writer.writerow(row)


def write_transactions_csv(result: SimulationResult, path: Path) -> None:
    """All buys + sells. Sells are also linked to their RealizedSale rows
    (FIFO across lots, so one sell trade can produce multiple realized
    sales — one per lot drained)."""
    fields = [
        "date", "side", "ticker", "account", "shares", "price",
        "gross", "realized_gain", "is_long_term", "holding_days", "reason",
    ]
    # Build a map from (ticker, sale_date, account) → list of RealizedSale.
    # When we see a sell trade, we'll associate the matching sales.
    realized_by_key: dict[tuple, list] = {}
    for s in result.portfolio.realized_sales:
        key = (s.ticker, s.sale_date, s.account)
        realized_by_key.setdefault(key, []).append(s)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for trade in result.portfolio.transaction_log:
            base_row = {
                "date": trade.trade_date.isoformat(),
                "side": trade.side,
                "ticker": trade.ticker,
                "account": trade.account,
                "price": round(trade.price, 4),
                "reason": trade.reason,
            }
            if trade.side == "buy":
                writer.writerow({
                    **base_row,
                    "shares": round(trade.shares, 6),
                    "gross": round(trade.shares * trade.price, 2),
                    "realized_gain": "",
                    "is_long_term": "",
                    "holding_days": "",
                })
            else:
                # One trade may have produced multiple RealizedSale rows
                # (FIFO across lots). Emit one CSV row per sale so the gain
                # detail is preserved.
                key = (trade.ticker, trade.trade_date, trade.account)
                sales = realized_by_key.get(key, [])
                if not sales:
                    writer.writerow({
                        **base_row,
                        "shares": round(trade.shares, 6),
                        "gross": round(trade.shares * trade.price, 2),
                        "realized_gain": "",
                        "is_long_term": "",
                        "holding_days": "",
                    })
                else:
                    for s in sales:
                        writer.writerow({
                            **base_row,
                            "shares": round(s.shares_sold, 6),
                            "gross": round(s.proceeds, 2),
                            "realized_gain": round(s.realized_gain, 2),
                            "is_long_term": "yes" if s.is_long_term else "no",
                            "holding_days": s.holding_days,
                        })


def compute_summary(result: SimulationResult) -> SummaryMetrics:
    snaps = result.daily_snapshots
    if not snaps:
        return SummaryMetrics(
            final_portfolio_value=0, portfolio_cagr=0, max_drawdown_pct=0,
            sharpe_ratio=0, total_tax_paid=0, n_buys=0, n_sells=0,
            realized_gains_total=0,
            baseline_finals={}, baseline_cagrs={}, baseline_drawdowns={},
            days_in_market=0,
        )
    final_value = snaps[-1].total_value
    initial = result.initial_capital
    days = (snaps[-1].date - snaps[0].date).days or 1
    years = days / 365.25
    portfolio_cagr = (final_value / initial) ** (1 / years) - 1 if initial > 0 else 0

    # Daily returns + drawdown
    values = [s.total_value for s in snaps]
    daily_returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            daily_returns.append(values[i] / values[i - 1] - 1)
    sharpe = _annualized_sharpe(daily_returns)
    max_dd = _max_drawdown(values)

    # Total tax paid
    total_tax = sum(t.tax_owed for t in result.year_end_taxes)
    realized_gains_total = sum(s.realized_gain for s in result.portfolio.realized_sales)

    # Baselines
    baseline_finals: dict[str, float] = {}
    baseline_cagrs: dict[str, float] = {}
    baseline_drawdowns: dict[str, float] = {}
    for ticker, b in result.baselines.items():
        baseline_path = [s.baseline_values.get(ticker, 0.0) for s in snaps]
        if not baseline_path or baseline_path[-1] <= 0:
            continue
        baseline_finals[ticker] = baseline_path[-1]
        baseline_cagrs[ticker] = (baseline_path[-1] / initial) ** (1 / years) - 1
        baseline_drawdowns[ticker] = _max_drawdown(baseline_path)

    n_buys = sum(1 for t in result.portfolio.transaction_log if t.side == "buy")
    n_sells = sum(1 for t in result.portfolio.transaction_log if t.side == "sell")

    days_in_market = sum(1 for s in snaps if s.n_positions > 0)

    return SummaryMetrics(
        final_portfolio_value=final_value,
        portfolio_cagr=portfolio_cagr,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        total_tax_paid=total_tax,
        n_buys=n_buys,
        n_sells=n_sells,
        realized_gains_total=realized_gains_total,
        baseline_finals=baseline_finals,
        baseline_cagrs=baseline_cagrs,
        baseline_drawdowns=baseline_drawdowns,
        days_in_market=days_in_market,
    )


def _annualized_sharpe(daily_returns: list[float], rf: float = 0.0) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = statistics.mean(daily_returns)
    sd = statistics.stdev(daily_returns)
    if sd == 0:
        return 0.0
    daily_sharpe = (mean - rf / 252) / sd
    return daily_sharpe * math.sqrt(252)


def _max_drawdown(values: list[float]) -> float:
    """Returns max peak-to-trough drawdown as a positive percentage (e.g. 0.25 = 25%)."""
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def write_summary_text(result: SimulationResult, summary: SummaryMetrics, path: Path) -> None:
    """Human-readable verdict. Includes the pre-declared pass/fail criterion."""
    lines = []
    lines.append("=" * 70)
    lines.append("BACKTEST SIMULATOR — Phase 1 result")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Window:         {result.start_date} → {result.end_date} "
                 f"({(result.end_date - result.start_date).days} days)")
    lines.append(f"Initial:        ${result.initial_capital:>12,.0f}")
    lines.append(f"Final:          ${summary.final_portfolio_value:>12,.0f}  "
                 f"CAGR {summary.portfolio_cagr*100:+.1f}%")
    lines.append(f"Max drawdown:   {summary.max_drawdown_pct*100:>5.1f}%")
    lines.append(f"Sharpe (ann.):  {summary.sharpe_ratio:>5.2f}")
    lines.append(f"Total tax paid: ${summary.total_tax_paid:>12,.0f}")
    lines.append(f"Realized gains: ${summary.realized_gains_total:>12,.0f}")
    lines.append(f"Trades:         {summary.n_buys} buys / {summary.n_sells} sells")
    lines.append(f"Universe:       {len(result.universe_tickers)} ticker(s) "
                 f"({', '.join(result.universe_tickers)})")
    lines.append("")
    lines.append("BASELINES (buy-and-hold, total return, no taxes):")
    for b, v in sorted(summary.baseline_finals.items()):
        cagr = summary.baseline_cagrs.get(b, 0)
        dd = summary.baseline_drawdowns.get(b, 0)
        delta = summary.final_portfolio_value - v
        delta_pct = (summary.final_portfolio_value / v - 1) if v > 0 else 0
        lines.append(f"  {b:<6}: ${v:>12,.0f}  CAGR {cagr*100:+.1f}%  "
                     f"DD {dd*100:>4.1f}%  "
                     f"agent {'+' if delta >= 0 else ''}{delta:,.0f} "
                     f"({delta_pct*100:+.1f}%)")
    lines.append("")

    # Pre-declared pass/fail criterion (per BACKTEST_SIMULATOR.md):
    # Pass: beats all baselines on absolute return; max drawdown ≤ median + 5pp
    if summary.baseline_finals:
        baseline_values = list(summary.baseline_finals.values())
        baseline_drawdowns = list(summary.baseline_drawdowns.values())
        beats_all = all(summary.final_portfolio_value > v
                          for v in baseline_values)
        beats_count = sum(1 for v in baseline_values
                          if summary.final_portfolio_value > v)
        median_dd = statistics.median(baseline_drawdowns)
        dd_acceptable = summary.max_drawdown_pct <= median_dd + 0.05
        lines.append("VERDICT (pre-declared criterion):")
        lines.append(f"  Beats baselines:     {beats_count}/{len(baseline_values)}")
        lines.append(f"  Drawdown vs median:  {summary.max_drawdown_pct*100:.1f}% "
                     f"vs median {median_dd*100:.1f}% "
                     f"({'OK' if dd_acceptable else '⚠  worse than +5pp'})")
        if beats_all and dd_acceptable:
            lines.append(f"  → PASS")
        elif beats_count >= len(baseline_values) - 1 and dd_acceptable:
            close_misses = [
                b for b, v in summary.baseline_finals.items()
                if summary.final_portfolio_value <= v
                and (v - summary.final_portfolio_value) / v < 0.02
            ]
            if close_misses:
                lines.append(f"  → SOFT PASS (close on {', '.join(close_misses)})")
            else:
                lines.append(f"  → FAIL (missed by >2% on at least one baseline)")
        else:
            lines.append(f"  → FAIL")
    lines.append("")

    if result.skipped_events:
        lines.append(f"Skipped events: {len(result.skipped_events)} "
                     f"(see daily.csv for skipped-day details)")
        # Show first few
        for d, t, reason in result.skipped_events[:5]:
            lines.append(f"  [{d}] {t}: {reason}")
        if len(result.skipped_events) > 5:
            lines.append(f"  ... +{len(result.skipped_events) - 5} more")
    lines.append("")
    lines.append("=" * 70)

    path.write_text("\n".join(lines))


def write_all_artifacts(result: SimulationResult, output_dir: Path) -> SummaryMetrics:
    """Write daily.csv, transactions.csv, summary.txt to `output_dir`.
    Returns the SummaryMetrics computed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_daily_csv(result, output_dir / "daily.csv")
    write_transactions_csv(result, output_dir / "transactions.csv")
    summary = compute_summary(result)
    write_summary_text(result, summary, output_dir / "summary.txt")
    return summary
