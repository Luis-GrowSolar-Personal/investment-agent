#!/usr/bin/env python3
"""tier_return_attribution.py — which cap tier actually produced the returns?

Answers one question, off the existing settled-configuration backtest:
how much of the portfolio's gain over $100,000 is attributable to each
cap tier (megacap / large / mid / small_micro)?

Method: run the SAME control cell every recent run reproduces
($179,944.91, phase 0, seed 0, settled config), then decompose the gain
per ticker as:

    contribution = realized gains on that ticker
                 + unrealized gain on lots still held at window close

and reconcile the sum against (final_value - INITIAL) so the
decomposition is verified, not asserted.

No LLM calls, no DB writes ($0). Reads the DB for the corpus (SELECT
only, via the same loader Test 1 and both follow-on runs use).

Usage:
    cd analysis && python3 tier_return_attribution.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)

TIERS = {
    "megacap":     ["AAPL", "GOOGL", "NVDA", "MSFT", "TSLA"],
    "large":       ["AVGO", "AMD", "ORCL"],
    "mid":         ["FSLR", "TTD"],
    "small_micro": ["QS", "AMPX", "ENVX", "EOSE", "RUN", "SPWR"],
}
TIER_OF = {t: tier for tier, ts in TIERS.items() for t in ts}
EXPECTED_CONTROL = 179_944.91


def main() -> int:
    print("Loading corpus (SELECT only)...")
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")

    print("Running control cell (settled config, phase 0, seed 0)...")
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                 phase_offset=0, seed=0, **CELL)
    final = r["final_value"]
    gain = final - S.INITIAL
    ok = abs(final - EXPECTED_CONTROL) < 0.01
    print(f"  final_value = ${final:,.2f}  "
          f"({'MATCHES' if ok else 'DOES NOT MATCH'} the ${EXPECTED_CONTROL:,.2f} reference)")
    if not ok:
        print("  !! control did not reproduce -- attribution below is NOT comparable")
        print("     to any prior run's figures. Investigate before trusting it.")
    print(f"  gain over ${S.INITIAL:,} = ${gain:,.2f}\n")

    pf = r["portfolio"]

    # Realized, per ticker
    realized = defaultdict(float)
    for rs in pf.realized_sales:
        realized[rs.ticker] += rs.realized_gain

    # Unrealized on lots still held at window close, per ticker
    unrealized = defaultdict(float)
    held_value = defaultdict(float)
    missing_price = []
    for acc in pf.accounts.values():
        for ticker, lots in acc.lots.items():
            price = prices.price_on(ticker, S.C)
            if price is None:
                missing_price.append(ticker)
                continue
            for lot in lots:
                unrealized[ticker] += lot.shares * price - lot.total_cost_basis
                held_value[ticker] += lot.shares * price

    if missing_price:
        print(f"  !! no closing price for: {sorted(set(missing_price))} "
              f"-- excluded from unrealized (flagged, not silently dropped)\n")

    tickers = sorted(set(realized) | set(unrealized))
    contrib = {t: realized[t] + unrealized[t] for t in tickers}
    total_attributed = sum(contrib.values())
    residual = gain - total_attributed

    # --- per ticker -----------------------------------------------------
    print("=" * 78)
    print("PER-TICKER CONTRIBUTION TO GAIN")
    print("=" * 78)
    print("%-8s %-12s %14s %14s %14s %9s" %
          ("ticker", "tier", "realized", "unrealized", "total", "% of gain"))
    for t in sorted(tickers, key=lambda x: -contrib[x]):
        print("%-8s %-12s %14s %14s %14s %8.1f%%" % (
            t, TIER_OF.get(t, "?"),
            f"${realized[t]:,.0f}", f"${unrealized[t]:,.0f}",
            f"${contrib[t]:,.0f}", 100 * contrib[t] / gain if gain else 0))

    # --- per tier -------------------------------------------------------
    by_tier = defaultdict(float)
    by_tier_r = defaultdict(float)
    by_tier_u = defaultdict(float)
    for t in tickers:
        tier = TIER_OF.get(t, "?")
        by_tier[tier] += contrib[t]
        by_tier_r[tier] += realized[t]
        by_tier_u[tier] += unrealized[t]

    print()
    print("=" * 78)
    print("PER-TIER CONTRIBUTION TO GAIN  <-- the answer")
    print("=" * 78)
    print("%-14s %14s %14s %14s %9s" %
          ("tier", "realized", "unrealized", "total", "% of gain"))
    for tier in ["megacap", "large", "mid", "small_micro", "?"]:
        if tier not in by_tier:
            continue
        print("%-14s %14s %14s %14s %8.1f%%" % (
            tier, f"${by_tier_r[tier]:,.0f}", f"${by_tier_u[tier]:,.0f}",
            f"${by_tier[tier]:,.0f}",
            100 * by_tier[tier] / gain if gain else 0))

    # --- reconciliation --------------------------------------------------
    print()
    print("=" * 78)
    print("RECONCILIATION  (verify, do not assert)")
    print("=" * 78)
    print(f"  final_value                 ${final:>14,.2f}")
    print(f"  initial                     ${S.INITIAL:>14,.2f}")
    print(f"  gain                        ${gain:>14,.2f}")
    print(f"  sum of per-ticker contrib   ${total_attributed:>14,.2f}")
    print(f"  residual (gain - attributed)${residual:>14,.2f}"
          f"   ({100*residual/gain if gain else 0:+.2f}% of gain)")
    print()
    if abs(residual) < 1.0:
        print("  Residual is ~zero: the decomposition is complete.")
    else:
        print("  NON-ZERO RESIDUAL. Most likely tax paid out of the portfolio")
        print("  (state-of-play 5.1 notes two 'forced-liquidation-for-tax'")
        print("  transactions on AAPL). Treat tier shares as approximate to")
        print("  within this residual; do not quote them as exact.")
    print()
    print(f"  realized total  ${sum(realized.values()):>14,.2f}")
    print(f"  unrealized total${sum(unrealized.values()):>14,.2f}")
    print(f"  ending held mkt value ${sum(held_value.values()):>10,.2f}"
          f"  + cash ${pf.total_cash():,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
