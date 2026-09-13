#!/usr/bin/env python3
"""
value_attribution_v2_stage_c_driver.py -- Stage C (C1, C2 only) of
value-attribution-and-headroom-v2.

Runs the two cheapest/highest-value Stage C diagnostics per
prompts/value-attribution-v2-stage-c.md Sec3 ("Run order is by value, not by
number: C1 and C2 first"):

  C1 -- cash/deployment ladder: Arm 0b, the new Arm 0c (equal-weight, fully
        invested, never traded), Arm 0, and the control.
  C2 -- bootstrap (ticker resampling, 16 blocks, 2000 resamples, fixed seed)
        of control-minus-Arm-0 ($6,842.67), plus per-ticker contribution
        concentration.

Zero Anthropic API calls. Zero DB writes. Reuses the same override mechanism
as value_attribution_v2_driver.py (Stage A): event.final_action is
overwritten in-memory, post-recompute_trend_layer(), before
run_session_sweep_cell() is called. No stored Analysis row is modified.

C3-C6 are NOT run by this driver -- see the Stage C wrap-up for why (budget).

Usage:
    cd analysis && python3 value_attribution_v2_stage_c_driver.py
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import analysis.sweep_cadence_and_session_model as S  # noqa: E402
from analysis.simulator.data import PriceLookup  # noqa: E402

CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
INITIAL_CAPITAL = 100_000.0
EXPECTED_CONTROL = 179_944.91
EXPECTED_ARM_0B = 120_799.82
EXPECTED_ARM_0 = 173_102.24
ALL16 = S.ALL16
WINDOW_END = S.C
SEED_BOOTSTRAP = 20260913
N_RESAMPLES = 2000


def git_commit_and_dirty():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SCRIPT_DIR.parent
    ).decode().strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=SCRIPT_DIR.parent
    ).decode().strip())
    return commit, dirty


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_arm(forced_final_action):
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    if forced_final_action is not None:
        for e in events:
            e.final_action = forced_final_action
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=0, **CELL)
    return r, events, prices


def cash_deployment_series(r):
    """Per-day (date, cash_total, total_value, cash_share) plus summary stats."""
    snaps = r["daily_snapshots"]
    series = []
    for s in snaps:
        share = (s.cash_total / s.total_value) if s.total_value else None
        series.append({"date": str(s.date), "cash_total": s.cash_total,
                        "total_value": s.total_value, "cash_share": share})
    avg_cash_share = (sum(x["cash_share"] for x in series if x["cash_share"] is not None)
                       / len(series)) if series else None
    # dollar-years invested = integral over days of (total_value - cash_total)/365.25
    dollar_years_invested = sum(
        (x["total_value"] - x["cash_total"]) for x in series
    ) / 365.25 if series else 0.0
    final = snaps[-1] if snaps else None
    final_cash_share = (final.cash_total / final.total_value) if final and final.total_value else None
    return {
        "avg_cash_share": avg_cash_share,
        "final_cash_total": final.cash_total if final else None,
        "final_cash_share": final_cash_share,
        "never_invested_approx_share_of_initial": (
            (final.cash_total / INITIAL_CAPITAL) if final else None
        ),
        "dollar_years_invested": dollar_years_invested,
        "n_days": len(series),
        # trimmed series (every 30th day) to keep manifest small; full curve
        # is reconstructable from run_session_sweep_cell's daily_snapshots.
        "cash_share_curve_every_30_days": series[::30],
    }


def build_arm_0c(events, prices):
    """Equal-weight, fully invested, never traded. One slice per ALL16
    ticker, $100,000/16 each, bought at that ticker's first call_date within
    the 195-event population; held to WINDOW_END, no further trades."""
    first_call = {}
    for e in events:
        if e.ticker not in first_call or e.call_date < first_call[e.ticker]:
            first_call[e.ticker] = e.call_date
    slice_dollars = INITIAL_CAPITAL / len(ALL16)
    holdings = {}
    detail = {}
    uninvested_slices = []
    for t in ALL16:
        buy_date = first_call.get(t)
        if buy_date is None:
            uninvested_slices.append(t)
            holdings[t] = {"shares": 0.0, "buy_price": None, "buy_date": None}
            continue
        p0 = prices.price_on(t, buy_date)
        if p0 is None or p0 <= 0:
            uninvested_slices.append(t)
            holdings[t] = {"shares": 0.0, "buy_price": None, "buy_date": str(buy_date)}
            continue
        shares = slice_dollars / p0
        holdings[t] = {"shares": shares, "buy_price": p0, "buy_date": str(buy_date)}

    final_value = 0.0
    for t in ALL16:
        h = holdings[t]
        if h["shares"] <= 0:
            # slice sits as cash if the ticker never appears in-population
            final_value += slice_dollars
            continue
        p1 = prices.price_on(t, WINDOW_END)
        v = h["shares"] * p1 if p1 else 0.0
        detail[t] = {"buy_date": h["buy_date"], "buy_price": h["buy_price"],
                      "sell_date_na": "never traded",
                      "price_at_window_end": p1, "final_value": v}
        final_value += v

    return {
        "final_value": final_value,
        "slice_dollars_per_ticker": slice_dollars,
        "n_tickers": len(ALL16),
        "tickers_never_appearing_in_population": uninvested_slices,
        "per_ticker_detail": detail,
    }


def bootstrap_control_minus_arm0(r_control, r_arm0, seed):
    """Approximate per-ticker contribution to (control_final - arm0_final)
    via each arm's realized_sales + final position mark-to-market, grouped by
    ticker, then resample tickers with replacement, 16 blocks, N times."""
    def per_ticker_value(r):
        by_ticker = {}
        # realized gains/losses by ticker from realized_sales
        for rs in r["portfolio"].realized_sales:
            by_ticker[rs.ticker] = by_ticker.get(rs.ticker, 0.0) + rs.realized_gain
        # final unrealized mark-to-market contribution: use last daily
        # snapshot's position_values (already marked to market)
        final_snap = r["daily_snapshots"][-1] if r["daily_snapshots"] else None
        if final_snap:
            for t, v in final_snap.position_values.items():
                by_ticker[t] = by_ticker.get(t, 0.0) + v
        return by_ticker

    pv_control = per_ticker_value(r_control)
    pv_arm0 = per_ticker_value(r_arm0)
    tickers = sorted(set(pv_control) | set(pv_arm0) | set(ALL16))
    diff_by_ticker = {t: pv_control.get(t, 0.0) - pv_arm0.get(t, 0.0) for t in tickers}

    # NOTE: this per-ticker split is additive by construction (sums to the
    # cash-adjusted difference of the two arms' invested value, not exactly
    # control_final_value - arm0_final_value, because cash balances also
    # differ between arms). Reported as an approximation; the wrap-up must
    # state this plainly.
    total_diff_approx = sum(diff_by_ticker.values())

    rng = random.Random(seed)
    values = list(diff_by_ticker.values())
    n = len(values)
    resampled_totals = []
    for _ in range(N_RESAMPLES):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        resampled_totals.append(sum(draw))
    resampled_totals.sort()
    lo = resampled_totals[int(0.025 * N_RESAMPLES)]
    hi = resampled_totals[int(0.975 * N_RESAMPLES) - 1]

    n_positive = sum(1 for v in values if v > 0)
    sorted_contribs = sorted(diff_by_ticker.items(), key=lambda kv: -abs(kv[1]))
    largest = sorted_contribs[0] if sorted_contribs else (None, 0.0)
    largest_share = (largest[1] / total_diff_approx) if total_diff_approx else None

    return {
        "diff_by_ticker_approx": diff_by_ticker,
        "total_diff_approx": total_diff_approx,
        "n_tickers_positive": n_positive,
        "n_tickers_total": n,
        "largest_contributor_ticker": largest[0],
        "largest_contributor_value": largest[1],
        "largest_contributor_share_of_total_approx": largest_share,
        "bootstrap_95_range": [lo, hi],
        "bootstrap_seed": seed,
        "bootstrap_n_resamples": N_RESAMPLES,
    }


def main() -> int:
    print("=== value_attribution_v2_stage_c_driver.py -- Stage C (C1, C2) ===")
    print("ASSERTION: zero Anthropic API calls. Read-only against the corpus; "
          "no stored Analysis row is modified.")
    commit, dirty = git_commit_and_dirty()
    print(f"git commit: {commit}  dirty: {dirty}")

    print("\n--- Reproduction check: control, Arm 0b, Arm 0 ---")
    r_control, events_c, prices = run_arm(None)
    r_0b, events_0b, _ = run_arm("Hold")
    r_0, events_0, _ = run_arm("Add")
    checks = {
        "control": (r_control["final_value"], EXPECTED_CONTROL),
        "arm_0b": (r_0b["final_value"], EXPECTED_ARM_0B),
        "arm_0": (r_0["final_value"], EXPECTED_ARM_0),
    }
    all_ok = True
    for label, (got, expected) in checks.items():
        ok = abs(got - expected) < 0.01
        all_ok = all_ok and ok
        print(f"  {label}: got=${got:,.2f} expected=${expected:,.2f} "
              f"{'MATCH' if ok else 'MISMATCH'}")
    if not all_ok:
        print("STOP: reproduction of Stage A figures failed. Flagging as a "
              "finding, proceeding with the actually-computed numbers "
              "(not the prompt's stale ones) per Sec4 0c instructions.")

    print("\n--- C1: cash/deployment ladder ---")
    c1 = {
        "control": {"final_value": r_control["final_value"],
                    **cash_deployment_series(r_control)},
        "arm_0b_universe_only": {"final_value": r_0b["final_value"],
                                  **cash_deployment_series(r_0b)},
        "arm_0_always_bullish": {"final_value": r_0["final_value"],
                                  **cash_deployment_series(r_0)},
    }
    arm_0c = build_arm_0c(events_c, prices)
    c1["arm_0c_equal_weight_never_traded"] = arm_0c
    print(f"  Arm 0b: ${c1['arm_0b_universe_only']['final_value']:,.2f}  "
          f"avg_cash_share={c1['arm_0b_universe_only']['avg_cash_share']:.3f}")
    print(f"  Arm 0c: ${arm_0c['final_value']:,.2f}")
    print(f"  Arm 0 : ${c1['arm_0_always_bullish']['final_value']:,.2f}  "
          f"avg_cash_share={c1['arm_0_always_bullish']['avg_cash_share']:.3f}")
    print(f"  Control: ${c1['control']['final_value']:,.2f}  "
          f"avg_cash_share={c1['control']['avg_cash_share']:.3f}")

    print("\n--- C2: bootstrap of control-minus-Arm-0 ---")
    c2 = bootstrap_control_minus_arm0(r_control, r_0, SEED_BOOTSTRAP)
    print(f"  point diff (control-arm0, actual final values): "
          f"${r_control['final_value'] - r_0['final_value']:,.2f}")
    print(f"  approx per-ticker-additive diff: ${c2['total_diff_approx']:,.2f}")
    print(f"  95% bootstrap range: [${c2['bootstrap_95_range'][0]:,.2f}, "
          f"${c2['bootstrap_95_range'][1]:,.2f}]")
    print(f"  tickers positive: {c2['n_tickers_positive']}/{c2['n_tickers_total']}")
    print(f"  largest contributor: {c2['largest_contributor_ticker']} "
          f"(${c2['largest_contributor_value']:,.2f}, "
          f"{c2['largest_contributor_share_of_total_approx']:.1%} of approx total)"
          if c2['largest_contributor_share_of_total_approx'] is not None else "")

    manifest = {
        "run_id": "value-attribution-and-headroom-v2",
        "stage": "C",
        "steps_run": ["C1", "C2"],
        "steps_not_run": ["C3", "C4", "C5", "C6"],
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "driver_file": "analysis/value_attribution_v2_stage_c_driver.py",
        "cell_params": CELL,
        "reproduction_check": {
            "control": {"got": checks["control"][0], "expected": checks["control"][1],
                        "match": abs(checks["control"][0] - checks["control"][1]) < 0.01},
            "arm_0b": {"got": checks["arm_0b"][0], "expected": checks["arm_0b"][1],
                       "match": abs(checks["arm_0b"][0] - checks["arm_0b"][1]) < 0.01},
            "arm_0": {"got": checks["arm_0"][0], "expected": checks["arm_0"][1],
                      "match": abs(checks["arm_0"][0] - checks["arm_0"][1]) < 0.01},
        },
        "checksums": {
            "type_classifications.json": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
            "price_cache.json": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache.json": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
        },
        "c1_deployment_ladder": c1,
        "c2_bootstrap": c2,
    }

    out_path = SCRIPT_DIR / "data" / "value_attribution_v2" / "stage_c_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nWrote manifest: {out_path}")

    run_state_dir = SCRIPT_DIR / "data" / "run_state" / "value-attribution-and-headroom-v2"
    with open(run_state_dir / "cells.jsonl", "a") as f:
        for cell_key, payload in (
            ("stage_c_c1_arm_0c", {"final_value": arm_0c["final_value"]}),
            ("stage_c_c2_bootstrap", {"range": c2["bootstrap_95_range"],
                                       "largest_contributor": c2["largest_contributor_ticker"]}),
        ):
            f.write(json.dumps({
                "cell_key": cell_key,
                "params": {**CELL, "seed": SEED_BOOTSTRAP if "c2" in cell_key else None},
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "cell_key": cell_key}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": payload,
            }) + "\n")
    print(f"Appended to {run_state_dir / 'cells.jsonl'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
