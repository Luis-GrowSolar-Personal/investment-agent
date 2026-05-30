#!/usr/bin/env python3
"""
e2e_scorer.py — Promotion Gate §3.2: End-to-end portfolio metric.

Runs the simulator from the file-based eval cache (no DB, no API calls) and
emits the gate metric: return per unit of max drawdown (CAGR / max_drawdown).
Raw CAGR is reported alongside but is NOT the gate metric.

This is the PRIMARY gate metric for allocator-layer changes (caps, profit-take,
sizing parameters). For analyst-layer changes it serves as the secondary
no-regress check.

See docs/architecture/PROMOTION_GATE.md §3.2 and §2 for full methodology.

Usage:
    cd analysis

    # Champion (current config):
    python3 e2e_scorer.py \\
        --start 2022-01-01 --end 2025-12-31 \\
        --taxable 50000 --tax-advantaged 50000 \\
        --eval-dir data/evals/v6_sonnet-4-20250514 \\
        --label "champion_v6_4-20250514"

    # Challenger (new eval cache — analyst change):
    python3 e2e_scorer.py \\
        --start 2022-01-01 --end 2025-12-31 \\
        --taxable 50000 --tax-advantaged 50000 \\
        --eval-dir data/evals/v6_sonnet-4-6 \\
        --label "challenger_v6_4-6"

    # JSON output for the gate runner:
    python3 e2e_scorer.py ... --json-out data/gate_runs/run_001_champion.json

Pre-reqs:
    - Versioned eval cache exists at --eval-dir
    - analysis/data/price_cache.json has prices for all tickers + SPY/QQQ/TMFC
    - analysis/data/type_classifications.json exists
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from analysis.simulator.data_from_cache import load_events_from_cache, attach_trend_verdicts
from analysis.simulator.simulator import run_simulation
from analysis.simulator.report import compute_summary
from analysis.type_classifier import build_type_function


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def run_e2e(
    start: date,
    end: date,
    taxable_cash: float,
    tax_advantaged_cash: float,
    eval_dir: Path,
    tickers: list[str] | None = None,
    verbose: bool = False,
) -> dict:
    """
    Run the simulation from the file-based eval cache and return the gate metrics.

    Returns a dict with:
        cagr            — annualised total return (decimal, e.g. 0.18 = 18%)
        max_drawdown    — peak-to-trough drawdown (decimal, e.g. 0.20 = 20%)
        return_per_dd   — CAGR / max_drawdown (the gate metric; higher is better)
        sharpe          — annualised Sharpe ratio
        final_value     — final portfolio value ($)
        initial_capital — starting capital ($)
        n_buys, n_sells — trade count
        universe        — list of tickers included
        baseline_cagrs  — {ticker: cagr} for SPY/QQQ/TMFC baselines
    """
    # Load and enrich events
    type_fn = build_type_function()
    events = load_events_from_cache(eval_dir=eval_dir)
    attach_trend_verdicts(events, tier_for_ticker=None)  # uses "established" default

    if not events:
        raise ValueError(f"No events loaded from {eval_dir}")

    result = run_simulation(
        start_date=start,
        end_date=end,
        taxable_cash=taxable_cash,
        tax_advantaged_cash=tax_advantaged_cash,
        universe_tickers=tickers,
        verbose=verbose,
        events=events,               # file-based path (bypasses DB)
        type_for_ticker=type_fn,
    )

    summary = compute_summary(result)

    max_dd = summary.max_drawdown_pct
    cagr   = summary.portfolio_cagr
    # Avoid division by zero: if drawdown is 0 (pristine run), cap at 999
    return_per_dd = (cagr / max_dd) if max_dd > 0.001 else 999.0

    return {
        "cagr":           round(cagr, 6),
        "max_drawdown":   round(max_dd, 6),
        "return_per_dd":  round(return_per_dd, 4),
        "sharpe":         round(summary.sharpe_ratio, 4),
        "final_value":    round(summary.final_portfolio_value, 2),
        "initial_capital": round(result.initial_capital, 2),
        "n_buys":         summary.n_buys,
        "n_sells":        summary.n_sells,
        "universe":       sorted(result.universe_tickers),
        "baseline_cagrs": {k: round(v, 6) for k, v in summary.baseline_cagrs.items()},
        "baseline_drawdowns": {k: round(v, 6) for k, v in summary.baseline_drawdowns.items()},
        "window_start":   start.isoformat(),
        "window_end":     end.isoformat(),
    }


def print_result(label: str, metrics: dict, eval_dir: Path) -> None:
    print("=" * 68)
    print(f"END-TO-END SCORER  —  Promotion Gate §3.2")
    print(f"Label:    {label}")
    print(f"Eval dir: {eval_dir}")
    print(f"Window:   {metrics['window_start']} → {metrics['window_end']}")
    print(f"Capital:  ${metrics['initial_capital']:,.0f}")
    print("=" * 68)
    print(f"\nGATE METRIC")
    print(f"  Return / max-drawdown:  {metrics['return_per_dd']:+.4f}   ← primary gate metric")
    print(f"\nSUPPORTING METRICS")
    print(f"  CAGR:           {metrics['cagr']*100:+.1f}%")
    print(f"  Max drawdown:   {metrics['max_drawdown']*100:.1f}%")
    print(f"  Sharpe (ann.):  {metrics['sharpe']:.2f}")
    print(f"  Final value:    ${metrics['final_value']:,.0f}")
    print(f"  Trades:         {metrics['n_buys']} buys / {metrics['n_sells']} sells")
    print(f"  Universe:       {', '.join(metrics['universe'])}")
    print(f"\nBASELINES (CAGR / max_dd)")
    for b, bcagr in sorted(metrics['baseline_cagrs'].items()):
        bdd = metrics['baseline_drawdowns'].get(b, 0)
        bpdd = (bcagr / bdd) if bdd > 0.001 else 999.0
        print(f"  {b:<6}: CAGR {bcagr*100:+.1f}%  DD {bdd*100:.1f}%  r/dd {bpdd:.4f}")
    print("=" * 68)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--start",          type=parse_date, required=True)
    ap.add_argument("--end",            type=parse_date, required=True)
    ap.add_argument("--taxable",        type=float, required=True)
    ap.add_argument("--tax-advantaged", type=float, required=True)
    ap.add_argument("--eval-dir",       type=Path,  required=True,
                    help="Versioned eval cache dir (e.g. data/evals/v6_sonnet-4-20250514)")
    ap.add_argument("--tickers",        nargs="*", default=None)
    ap.add_argument("--label",          default="run", help="Human label for this run")
    ap.add_argument("--json-out",       type=Path, default=None,
                    help="Write metrics as JSON to this file (for gate runner)")
    ap.add_argument("--verbose",        action="store_true")
    args = ap.parse_args()

    eval_dir = args.eval_dir
    if not eval_dir.is_absolute():
        eval_dir = SCRIPT_DIR / eval_dir
    if not eval_dir.exists():
        ap.error(f"--eval-dir not found: {eval_dir}")

    if args.start >= args.end:
        ap.error("--start must be before --end")

    metrics = run_e2e(
        start=args.start,
        end=args.end,
        taxable_cash=args.taxable,
        tax_advantaged_cash=args.tax_advantaged,
        eval_dir=eval_dir,
        tickers=args.tickers,
        verbose=args.verbose,
    )
    metrics["label"] = args.label
    metrics["eval_dir"] = str(eval_dir)

    print_result(args.label, metrics, eval_dir)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(metrics, indent=2))
        print(f"\nJSON written → {args.json_out}")


if __name__ == "__main__":
    main()
