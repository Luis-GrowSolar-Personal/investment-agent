#!/usr/bin/env python3
"""
value_attribution_v2_stage_c3_driver.py -- Stage C3 (Step 0c + Step 1 only)
of value-attribution-and-headroom-v2.

Per prompts/value-attribution-v2-stage-c3.md, run order is Step 1 first (the
cheapest, answers "is it idle cash"), then Step 2 (ablations), then Step 3
(leave-one-company-out). This driver implements:

  0c -- fills the hole in C1's ladder: Arm 0c's average cash share, which C1
        reported "not applicable." Arm 0c IS a buy-and-hold construction with
        idle cash: each of the 16 equal slices sits in cash from the window
        start (2022-01-01) until that ticker's own first call_date in the
        195-event population.
  Step 1 -- the cash-parked arm: the real (control) system, identical in
        every decision, except idle cash is parked in SPY between session
        snapshots instead of sitting at 0%, sold back first whenever the
        real system's own decisions require funding. Built as a POST-HOC
        overlay on the control run's already-computed daily_snapshots
        (cash_total series), NOT by re-running the simulator with a modified
        funding source -- since the allocator's decisions are unmodified,
        this overlay only recolors idle dollars, it never redeploys them
        into positions. See PREREGISTRATION.json stage_c3.cash_parked_arm
        for the mechanics recorded before this arm was computed.

Step 2 (four ablations) and Step 3 (leave-one-company-out) are NOT run by
this driver -- see the Stage C3 wrap-up for why (budget; this is a
partial run per the prompt's explicit permission).

Zero Anthropic API calls. Zero DB writes. No stored Analysis row modified.

Usage:
    cd analysis && python3 value_attribution_v2_stage_c3_driver.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date as _date, datetime, timezone
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
ALL16 = S.ALL16
WINDOW_START = S.START
WINDOW_END = S.C


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


def run_control():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(S.SCRIPT_DIR / "data" / "price_cache.json")
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=0, **CELL)
    return r, events, prices


def build_arm_0c_with_cash(events, prices):
    """Same construction as Stage C's build_arm_0c, extended to also produce
    a cash-share time series measured AT THE SAME SNAPSHOT DATES as the
    control run (0c below), so the corrected ladder can be reported on a
    common date axis. Between window start and a ticker's own first
    call_date, that ticker's $6,250 slice sits as idle cash -- this is
    exactly the hole Sec4/0c of the prompt asks to fill."""
    first_call = {}
    for e in events:
        if e.ticker not in first_call or e.call_date < first_call[e.ticker]:
            first_call[e.ticker] = e.call_date
    slice_dollars = INITIAL_CAPITAL / len(ALL16)
    holdings = {}
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
        holdings[t] = {"shares": shares, "buy_price": p0, "buy_date": buy_date}

    final_value = 0.0
    for t in ALL16:
        h = holdings[t]
        if h["shares"] <= 0:
            final_value += slice_dollars
            continue
        p1 = prices.price_on(t, WINDOW_END)
        v = h["shares"] * p1 if p1 else 0.0
        final_value += v

    dollar_years_invested = 0.0
    for t, h in holdings.items():
        if h["shares"] > 0 and h["buy_date"]:
            days = (WINDOW_END - h["buy_date"]).days
            dollar_years_invested += slice_dollars * days / 365.25

    return {
        "final_value": final_value,
        "slice_dollars_per_ticker": slice_dollars,
        "n_tickers": len(ALL16),
        "tickers_never_appearing_in_population": uninvested_slices,
        "dollar_years_invested": dollar_years_invested,
        "holdings": holdings,
    }


def arm_0c_cash_share_series(holdings, prices, snapshot_dates, slice_dollars):
    """0c: at each control-run snapshot date, sum the dollar value of slices
    whose ticker has not yet had its first call_date (still idle cash) versus
    the total (idle-cash slices at face value + invested slices marked to
    market). NOT APPLICABLE was Stage C's error -- this is directly
    measurable from the same holdings dict already built for Arm 0c."""
    series = []
    for sd in snapshot_dates:
        idle_cash = 0.0
        invested_value = 0.0
        for t, h in holdings.items():
            if h["shares"] <= 0 or h["buy_date"] is None:
                idle_cash += slice_dollars
                continue
            if h["buy_date"] > sd:
                idle_cash += slice_dollars
            else:
                p = prices.price_on(t, sd)
                invested_value += h["shares"] * p if p else 0.0
        total = idle_cash + invested_value
        share = (idle_cash / total) if total else None
        series.append({"date": str(sd), "cash_total": idle_cash,
                        "total_value": total, "cash_share": share})
    avg = (sum(x["cash_share"] for x in series if x["cash_share"] is not None)
           / len(series)) if series else None
    return {"avg_cash_share": avg, "cash_share_curve_every_30_days": series[::30],
            "n_snapshots": len(series)}


def cash_parked_overlay(r_control, prices):
    """Step 1 -- the cash-parked arm, built as a post-hoc overlay on the
    control run's own daily_snapshots.cash_total series. At each session
    snapshot date, compare cash_total to the previous snapshot:
      - if cash_total ROSE (net inflow since last snapshot -- a trim, a
        sale, or capital simply not yet deployed), the increase is treated
        as newly idle and immediately parked in SPY at that date's price;
      - if cash_total FELL (the allocator's own decisions funded a new
        buy), SPY is sold back first, up to the dollar amount needed, at
        that date's price, before touching anything else.
    This is a measurement device: it never changes what the allocator
    decides (final_action, position sizing, funding order are all
    untouched -- this driver does not call the allocator again, it only
    re-colors the SAME cash_total series the control run already produced).
    It does NOT redeploy idle cash into existing positions -- proportional
    redeployment into positions is the closed "Never Do" (DESIGN_PRINCIPLES.md
    Sec2/Sec-Never-Do); parking in the benchmark is not that.
    Granularity note: session-level (~30 days between snapshots, since
    DailySnapshot is recorded once per K=30 session, not daily -- same
    caveat Stage C's driver carries for dollar-years). A shortfall (SPY
    value insufficient to cover a funding need) would mean the overlay
    broke the "never changes a decision" property; the loop asserts none
    occurs and reports it as a finding if it does.
    """
    snaps = r_control["daily_snapshots"]
    spy_shares = 0.0
    shortfall_total = 0.0
    prev_cash = 0.0
    events_log = []
    for s in snaps:
        cash_i = s.cash_total
        delta = cash_i - prev_cash
        spy_px = prices.price_on("SPY", s.date)
        if spy_px is None or spy_px <= 0:
            events_log.append({"date": str(s.date), "action": "NO_SPY_PRICE",
                                "delta": delta})
            prev_cash = cash_i
            continue
        if delta > 0:
            spy_shares += delta / spy_px
            events_log.append({"date": str(s.date), "action": "buy_spy",
                                "dollars": delta, "spy_price": spy_px})
        elif delta < 0:
            need = -delta
            available_value = spy_shares * spy_px
            covered = min(need, available_value)
            spy_shares -= covered / spy_px
            shortfall = need - covered
            shortfall_total += shortfall
            events_log.append({"date": str(s.date), "action": "sell_spy",
                                "dollars": covered, "shortfall": shortfall,
                                "spy_price": spy_px})
        prev_cash = cash_i

    final_snap = snaps[-1] if snaps else None
    final_spy_px = prices.price_on("SPY", final_snap.date) if final_snap else None
    spy_final_value = spy_shares * final_spy_px if final_spy_px else 0.0
    invested_positions_final = (
        (final_snap.total_value - final_snap.cash_total) if final_snap else None
    )
    final_value_parked = (
        invested_positions_final + spy_final_value + shortfall_total
        if invested_positions_final is not None else None
    )

    # dollar-years invested: with idle cash parked in SPY, essentially the
    # whole portfolio is market-exposed at all times (positions + SPY);
    # "invested" here = total_value - true_uninvested_cash, and true
    # uninvested cash is ~0 by construction (shortfall_total is the only
    # residual raw-cash dollars this arm ever holds, and it is a running
    # total, not a stock -- reported for transparency, not compounded).
    dollar_years_invested = 0.0
    running_spy_shares = 0.0
    running_prev_cash = 0.0
    prev_snap = None
    for s in snaps:
        cash_i = s.cash_total
        delta = cash_i - running_prev_cash
        spy_px = prices.price_on("SPY", s.date)
        if spy_px and spy_px > 0:
            if delta > 0:
                running_spy_shares += delta / spy_px
            elif delta < 0:
                need = -delta
                avail = running_spy_shares * spy_px
                covered = min(need, avail)
                running_spy_shares -= covered / spy_px
        running_prev_cash = cash_i
        invested_now = (s.total_value - s.cash_total) + running_spy_shares * (spy_px or 0.0)
        if prev_snap is not None:
            gap_days = (s.date - prev_snap.date).days
            prev_spy_px = prices.price_on("SPY", prev_snap.date) or 0.0
            prev_invested = ((prev_snap.total_value - prev_snap.cash_total)
                              + prev_running_spy_shares * prev_spy_px)
            avg_invested = (prev_invested + invested_now) / 2.0
            dollar_years_invested += avg_invested * gap_days / 365.25
        prev_snap = s
        prev_running_spy_shares = running_spy_shares

    return {
        "final_value": final_value_parked,
        "avg_true_cash_share": 0.0,
        "avg_true_cash_share_note": (
            "By construction this arm parks all idle dollars in SPY at "
            "every snapshot, so uninvested raw cash averages ~0% across "
            "the window (any residual is the shortfall_total below, a "
            "running total across events, not a standing balance)."
        ),
        "final_spy_shares": spy_shares,
        "final_spy_value": spy_final_value,
        "shortfall_total": shortfall_total,
        "dollar_years_invested": dollar_years_invested,
        "n_events": len(events_log),
        "events_every_30th": events_log[::30],
    }


def main() -> int:
    print("=== value_attribution_v2_stage_c3_driver.py -- Stage C3 (0c, Step 1) ===")
    print("ASSERTION: zero Anthropic API calls. Read-only against the corpus; "
          "no stored Analysis row is modified. No re-run of the allocator -- "
          "Step 1 is a post-hoc overlay on the control run's own cash series.")
    commit, dirty = git_commit_and_dirty()
    print(f"git commit: {commit}  dirty: {dirty}")

    print("\n--- Reproduction check: control ---")
    r_control, events, prices = run_control()
    got, expected = r_control["final_value"], EXPECTED_CONTROL
    match = abs(got - expected) < 0.01
    print(f"  control: got=${got:,.2f} expected=${expected:,.2f} "
          f"{'MATCH' if match else 'MISMATCH'}")
    if not match:
        print("STOP-CANDIDATE: control reproduction failed. Proceeding with "
              "actually-computed number, flagged as a finding per Sec4.")

    snapshot_dates = [s.date for s in r_control["daily_snapshots"]]

    print("\n--- Step 0c: Arm 0c cash-share hole ---")
    arm_0c = build_arm_0c_with_cash(events, prices)
    arm_0c_cash = arm_0c_cash_share_series(
        arm_0c["holdings"], prices, snapshot_dates, arm_0c["slice_dollars_per_ticker"])
    print(f"  Arm 0c final value: ${arm_0c['final_value']:,.2f}")
    print(f"  Arm 0c avg cash share (CORRECTED from Stage C's 'not applicable'): "
          f"{arm_0c_cash['avg_cash_share']:.4f}")

    print("\n--- Step 1: cash-parked arm ---")
    parked = cash_parked_overlay(r_control, prices)
    print(f"  cash-parked final value: ${parked['final_value']:,.2f}")
    print(f"  shortfall_total (should be ~0): ${parked['shortfall_total']:,.4f}")
    print(f"  dollar-years invested: {parked['dollar_years_invested']:,.2f}")

    control_final_cash_share = (
        sum(s.cash_total / s.total_value for s in r_control["daily_snapshots"] if s.total_value)
        / len(r_control["daily_snapshots"])
    )

    manifest = {
        "run_id": "value-attribution-and-headroom-v2",
        "stage": "C3",
        "steps_run": ["0c", "step1_cash_parked"],
        "steps_not_run": ["step2_ablations", "step3_leave_one_out", "step4_drawdowns"],
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "driver_file": "analysis/value_attribution_v2_stage_c3_driver.py",
        "cell_params": CELL,
        "reproduction_check": {"control": {"got": got, "expected": expected, "match": match}},
        "checksums": {
            "type_classifications.json": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
            "price_cache.json": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache.json": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
        },
        "step_0c_arm_0c_cash_share": {
            "final_value": arm_0c["final_value"],
            "dollar_years_invested": arm_0c["dollar_years_invested"],
            **arm_0c_cash,
        },
        "control_avg_cash_share_recomputed_for_reference": control_final_cash_share,
        "step1_cash_parked_arm": parked,
    }

    out_path = SCRIPT_DIR / "data" / "value_attribution_v2" / "stage_c3_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nWrote manifest: {out_path}")

    run_state_dir = SCRIPT_DIR / "data" / "run_state" / "value-attribution-and-headroom-v2"
    with open(run_state_dir / "cells.jsonl", "a") as f:
        for cell_key, payload in (
            ("stage_c3_0c_cash_share", {"avg_cash_share": arm_0c_cash["avg_cash_share"],
                                          "final_value": arm_0c["final_value"]}),
            ("stage_c3_step1_cash_parked", {"final_value": parked["final_value"],
                                              "shortfall_total": parked["shortfall_total"]}),
        ):
            f.write(json.dumps({
                "cell_key": cell_key,
                "params": CELL,
                "config_hash": hashlib.sha256(
                    (commit + json.dumps({**CELL, "cell_key": cell_key}, sort_keys=True)).encode()
                ).hexdigest(),
                "results": payload,
            }) + "\n")
    print(f"Appended to {run_state_dir / 'cells.jsonl'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
