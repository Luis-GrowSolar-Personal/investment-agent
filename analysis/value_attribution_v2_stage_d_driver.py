#!/usr/bin/env python3
"""
value_attribution_v2_stage_d_driver.py -- Stage D of value-attribution-and-
headroom-v2 (prompts/value-attribution-v2-stage-d.md).

Measures the look-ahead ceiling of a perfect analyst, run through the REAL,
unmodified trend layer and allocator -- both at today's session speed limit
(X=2.5pp) and with that limit removed -- and splits the ceiling by direction
(upside-only, downside-only, both).

ZERO Anthropic API calls. ZERO DB writes to any stored Analysis row. Oracle
labels are derived from price data only (analyst_direct_scorer.py's own
FORWARD_DAYS / DEAD_BAND / BENCHMARK constants, imported not reimplemented)
and live only in this run's own scratch files -- never in a shared cache, the
DB, or any path another arm/run reads.

Firewall: the oracle arm builds "calls" from forward returns (look-ahead by
construction -- the point of a ceiling), but those calls are still fed into
the REAL, unmodified trend layer and allocator through the same per_call_rec
/ thesis_health / extra-fields shape a real analyst call would occupy. No
portfolio data is read to build a label (labels come only from price_cache.json
via analyst_direct_scorer.PriceCache). No transcript text is read by the
allocator at any point (it never was, in this codebase's simulator).

Usage:
    cd analysis && python3 value_attribution_v2_stage_d_driver.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import date as _date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

import analysis.sweep_cadence_and_session_model as S  # noqa: E402
from analysis.simulator.data import PriceLookup, load_call_events  # noqa: E402
from analysis.analyst_direct_scorer import (  # noqa: E402
    PriceCache, FORWARD_DAYS, DEAD_BAND, BENCHMARK,
)

CELL_BASE = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
                  execution_order="pooled", trim_budget_scope="per_event_date",
                  veto_p=0.0)
INITIAL_CAPITAL = 100_000.0
EXPECTED_CONTROL = 179_944.91
BUY_AND_HOLD = 195_584.28
ALL16 = S.ALL16
WINDOW_START = S.START
WINDOW_END = S.C

REPO_ROOT = SCRIPT_DIR.parent
RUN_STATE_DIR = REPO_ROOT / "analysis" / "data" / "run_state" / "value-attribution-and-headroom-v2"
PREREG_PATH = REPO_ROOT / "analysis" / "data" / "value_attribution_v2" / "PREREGISTRATION.json"
MANIFEST_PATH = SCRIPT_DIR / "data" / "run_manifests" / "value_attribution_v2_stage_d_manifest.json"

# -----------------------------------------------------------------------
# 0b/0c pre-registered oracle-label -> synthetic-field mapping.
#
# Label encoding (per_call_rec): bullish -> "Add", neutral -> "Hold",
# bearish -> "Exit" (NOT "Trim"). Choosing "Exit" over "Trim" for bearish is
# the single largest bound-LOOSENING choice in this driver: it gives the
# oracle full de-risking on every correctly-called decline, which is a
# stronger action than any real analyst call in this corpus ever issued for
# a bearish outcome (13.9% catch rate at Trim/Exit combined, per Stage B).
# This inflates the ceiling versus a Trim-only encoding; the pre-
# registration and report both name this as a real assumption, not the
# floor of what "perfect direction calls" could mean.
#
# Non-direction field synthesis (thesis_health, credibility_delta,
# stumble_type, mitigation_track_record, fresh_money_allocation,
# recommended_size): set to the most SUPPORTIVE possible values consistent
# with the label, rather than reusing the real (possibly conflicting)
# fields the actual call carried. compute_trend_verdict() and
# compute_final_confidence() read these to decide overrides and confidence,
# and rank_key() reads final_confidence/thesis trajectory to order swap-
# funding donors -- feeding the trend layer values that never fight the
# oracle's own direction is bound-LOOSENING (it removes friction/overrides
# a noisy real analyst would sometimes trigger against itself) and is named
# here as such, not silently assumed.
# -----------------------------------------------------------------------
ORACLE_SYNTHESIS = {
    "bullish": dict(per_call_rec="Add", thesis_health="Strengthening",
                     recommended_size=35.0, credibility_delta="positive",
                     stumble_type=None, mitigation_track_record="strong",
                     fresh_money_allocation=100.0),
    "neutral": dict(per_call_rec="Hold", thesis_health="Intact",
                     recommended_size=15.0, credibility_delta="neutral",
                     stumble_type=None, mitigation_track_record="mixed",
                     fresh_money_allocation=50.0),
    "bearish": dict(per_call_rec="Exit", thesis_health="Broken",
                     recommended_size=0.0, credibility_delta="negative",
                     stumble_type="Structural", mitigation_track_record="unproven",
                     fresh_money_allocation=0.0),
}

SEED = 0
PHASE_OFFSET = 0


def git_commit_and_dirty():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT
    ).decode().strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT
    ).decode().strip())
    return commit, dirty


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------
# Step 1 -- oracle labels
# ---------------------------------------------------------------------

def build_oracle_labels(events):
    """One label per (ticker, call_date) in the locked 195-event population,
    using analyst_direct_scorer's own constants. Returns (labels, report)."""
    prices = PriceCache(SCRIPT_DIR / "data" / "price_cache.json")
    labels = {}
    unlabelable = []
    for e in events:
        key = (e.ticker, e.call_date)
        if key in labels:
            continue
        p0, _ = prices.price_on_or_after(e.ticker, e.call_date)
        b0, _ = prices.price_on_or_after(BENCHMARK, e.call_date)
        fwd_target = e.call_date + timedelta(days=FORWARD_DAYS)
        p1, _ = prices.price_on_or_after(e.ticker, fwd_target)
        b1, _ = prices.price_on_or_after(BENCHMARK, fwd_target)
        if not all([p0, b0, p1, b1]):
            unlabelable.append(key)
            continue
        stock_ret = (p1 - p0) / p0
        bench_ret = (b1 - b0) / b0
        rel = stock_ret - bench_ret
        if rel > DEAD_BAND:
            labels[key] = "bullish"
        elif rel < -DEAD_BAND:
            labels[key] = "bearish"
        else:
            labels[key] = "neutral"
    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    for v in labels.values():
        counts[v] += 1
    report = {
        "n_events_total": len(set((e.ticker, e.call_date) for e in events)),
        "n_labelable": len(labels),
        "n_unlabelable": len(unlabelable),
        "unlabelable_keys": [[t, str(d)] for t, d in unlabelable],
        "label_counts": counts,
    }
    return labels, report


def apply_oracle(events, oracle_labels, mode):
    """Return a deep-copied event list + extra_fields dict with oracle
    overrides applied at the per_call_rec injection point (BEFORE the trend
    layer runs), per mode:
      - 'D-both': every event gets its oracle label's synthesis.
      - 'D-up':   only events whose oracle label is 'bullish' get the
                  synthesis; every other event keeps its REAL per_call_rec /
                  thesis_health / recommended_size and REAL extra_fields.
      - 'D-down': only events whose oracle label is 'bearish' get the
                  synthesis; everything else stays real.
    Real extra_fields are fetched the same way load_events_dedup_on() does.
    """
    events_copy = copy.deepcopy(events)
    real_extra = S.fetch_extra_fields(ALL16, WINDOW_END)
    extra_fields = {}
    n_overridden = 0
    for e in events_copy:
        key = (e.ticker, e.call_date)
        label = oracle_labels.get(key)
        override = False
        if mode == "D-both":
            override = label is not None
        elif mode == "D-up":
            override = label == "bullish"
        elif mode == "D-down":
            override = label == "bearish"
        else:
            raise ValueError(mode)

        if override:
            syn = ORACLE_SYNTHESIS[label]
            e.per_call_rec = syn["per_call_rec"]
            e.thesis_health = syn["thesis_health"]
            e.recommended_size = syn["recommended_size"]
            extra_fields[key] = {
                "fresh_money_allocation": syn["fresh_money_allocation"],
                "credibility_delta": syn["credibility_delta"],
                "mitigation_track_record": syn["mitigation_track_record"],
                "stumble_type": syn["stumble_type"],
            }
            n_overridden += 1
        else:
            extra_fields[key] = real_extra.get(key, {})
    return events_copy, extra_fields, n_overridden


def run_arm(events, extra_fields, tier_fn, type_fn, driver_fn, prices, limit_pp):
    """Recompute the trend layer (real, unmodified code) on the given
    events/extra_fields, then run the real, unmodified allocator via
    run_session_sweep_cell at the given session speed limit."""
    events_local = copy.deepcopy(events)
    S.recompute_trend_layer(events_local, tier_fn, extra_fields)
    cell = dict(CELL_BASE, limit_pp=limit_pp)
    r = S.run_session_sweep_cell(events_local, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=PHASE_OFFSET, seed=SEED, **cell)
    return r, events_local


def call_level_hit_rate(events_local, oracle_labels, mode, only_overridden=True):
    """Call-level sanity check: among events this arm actually overrode with
    an oracle label, does final per_call_rec's IMPLIED direction match the
    oracle label? (Not final_action -- final_action is graded separately as
    the trend-layer-override gap.)"""
    direction_of_rec = {"Add": "bullish", "Hold": "neutral", "Trim": "bearish", "Exit": "bearish"}
    n = 0
    hits = 0
    for e in events_local:
        key = (e.ticker, e.call_date)
        label = oracle_labels.get(key)
        if label is None:
            continue
        if mode == "D-up" and label != "bullish":
            continue
        if mode == "D-down" and label != "bearish":
            continue
        n += 1
        if direction_of_rec.get(e.per_call_rec) == label:
            hits += 1
    return hits, n


def final_action_hit_rate(events_local, oracle_labels, mode):
    direction_of_action = {"Add": "bullish", "Hold": "neutral", "Trim": "bearish", "Exit": "bearish"}
    n = 0
    hits = 0
    for e in events_local:
        key = (e.ticker, e.call_date)
        label = oracle_labels.get(key)
        if label is None:
            continue
        if mode == "D-up" and label != "bullish":
            continue
        if mode == "D-down" and label != "bearish":
            continue
        n += 1
        if direction_of_action.get(e.final_action) == label:
            hits += 1
    return hits, n


def binding_shares(r):
    fl = r["funding_log"]
    counts = {}
    for f in fl:
        counts[f["binding"]] = counts.get(f["binding"], 0) + 1
    total = len(fl)
    shares = {k: v / total for k, v in counts.items()} if total else {}
    return counts, shares, total


def cash_share_and_dollar_years(r):
    snaps = r["daily_snapshots"]
    shares = [s.cash_total / s.total_value for s in snaps if s.total_value]
    avg_cash_share = sum(shares) / len(shares) if shares else None
    dyi = 0.0
    for i in range(1, len(snaps)):
        gap_days = (snaps[i].date - snaps[i - 1].date).days
        inv_prev = snaps[i - 1].total_value - snaps[i - 1].cash_total
        inv_cur = snaps[i].total_value - snaps[i].cash_total
        dyi += (inv_prev + inv_cur) / 2.0 * gap_days / 365.25
    return avg_cash_share, dyi


def return_per_dollar_year(final_value, dyi):
    if not dyi:
        return None
    return (final_value - INITIAL_CAPITAL) / dyi


def drawdown_stats(dates, values):
    """Max peak-to-trough decline in $ and %, date range, and largest
    single-quarter decline (bucketing by calendar quarter, last-observed
    snapshot value per quarter, most negative quarter-over-quarter change)."""
    if not dates:
        return None
    peak = values[0]
    peak_date = dates[0]
    max_dd_dollar = 0.0
    max_dd_pct = 0.0
    dd_peak_date = dates[0]
    dd_trough_date = dates[0]
    for d, v in zip(dates, values):
        if v > peak:
            peak = v
            peak_date = d
        dd = peak - v
        dd_pct = dd / peak if peak else 0.0
        if dd > max_dd_dollar:
            max_dd_dollar = dd
            max_dd_pct = dd_pct
            dd_peak_date = peak_date
            dd_trough_date = d

    quarter_marks = {}
    for d, v in zip(dates, values):
        q = (d.year, (d.month - 1) // 3 + 1)
        quarter_marks[q] = v  # last-observed wins (dates are sorted ascending)
    q_keys = sorted(quarter_marks.keys())
    largest_q_decline_pct = 0.0
    largest_q_decline_dollar = 0.0
    largest_q_range = None
    for i in range(1, len(q_keys)):
        prev_v = quarter_marks[q_keys[i - 1]]
        cur_v = quarter_marks[q_keys[i]]
        change_pct = (cur_v - prev_v) / prev_v if prev_v else 0.0
        change_dollar = cur_v - prev_v
        if change_pct < largest_q_decline_pct:
            largest_q_decline_pct = change_pct
            largest_q_decline_dollar = change_dollar
            largest_q_range = (q_keys[i - 1], q_keys[i])

    return {
        "max_drawdown_dollars": max_dd_dollar,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_date_range": [str(dd_peak_date), str(dd_trough_date)],
        "largest_single_quarter_decline_pct": largest_q_decline_pct,
        "largest_single_quarter_decline_dollars": largest_q_decline_dollar,
        "largest_single_quarter_range": (
            [f"{largest_q_range[0][0]}Q{largest_q_range[0][1]}",
             f"{largest_q_range[1][0]}Q{largest_q_range[1][1]}"]
            if largest_q_range else None
        ),
    }


def snap_series(r):
    snaps = r["daily_snapshots"]
    return [s.date for s in snaps], [s.total_value for s in snaps]


def main() -> int:
    commit, dirty = git_commit_and_dirty()
    print(f"git commit={commit[:12]} dirty={dirty}")
    if dirty:
        print("HARD STOP: git_dirty cannot be recorded false.")
        return 1

    checksums = {
        "type_classifications.json": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
        "price_cache.json": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
        "fundamentals_cache.json": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
    }

    # --- Step 0d: no-unlabelable-tail check, on the RAW (real-call) events
    # from load_events_dedup_on() -- the locked 195-event simulator
    # population. ---
    events_real, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(SCRIPT_DIR / "data" / "price_cache.json")
    print(f"n locked population events (post-dedup): {len(events_real)}")

    oracle_labels, label_report = build_oracle_labels(events_real)
    print("Step 0d / Step 1 oracle label report:", json.dumps(label_report, indent=2))

    if label_report["n_unlabelable"] > 0:
        print("FINDING: unlabelable tail is NONZERO -- contradicts the "
              "prompt's Step 0d expectation. Stopping per Sec4/0d to have a "
              "fallback pre-registered rather than inventing one.")
        manifest = {"step0d_finding_unlabelable_tail": label_report,
                     "aborted": True}
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
        return 2

    results = {"label_report": label_report}

    # --- Step 2: ceiling under today's allocator, D-both at X=2.5pp ---
    print("\n--- Step 2: D-both @ X=2.5pp (ceiling under today's allocator) ---")
    events_dboth, extra_dboth, n_over_dboth = apply_oracle(events_real, oracle_labels, "D-both")
    r_dboth_25, ev_local_dboth_25 = run_arm(events_dboth, extra_dboth, tier_fn, type_fn,
                                             driver_fn, prices, limit_pp=2.5)
    call_hits, call_n = call_level_hit_rate(ev_local_dboth_25, oracle_labels, "D-both")
    action_hits, action_n = final_action_hit_rate(ev_local_dboth_25, oracle_labels, "D-both")
    counts_b, shares_b, total_b = binding_shares(r_dboth_25)
    cash_b, dyi_b = cash_share_and_dollar_years(r_dboth_25)
    rpdy_b = return_per_dollar_year(r_dboth_25["final_value"], dyi_b)
    step2 = {
        "n_events_overridden": n_over_dboth,
        "call_level_hit_rate": call_hits / call_n if call_n else None,
        "call_level_n": call_n,
        "call_level_hits": call_hits,
        "final_action_level_hit_rate": action_hits / action_n if action_n else None,
        "final_action_level_n": action_n,
        "final_action_level_hits": action_hits,
        "trend_layer_override_gap": (call_hits / call_n - action_hits / action_n)
                                      if call_n and action_n else None,
        "binding_counts": counts_b,
        "binding_shares": shares_b,
        "n_funding_events": total_b,
        "avg_cash_share": cash_b,
        "dollar_years_invested": dyi_b,
        "return_per_dollar_year": rpdy_b,
        "final_value": r_dboth_25["final_value"],
        "delta_vs_control": r_dboth_25["final_value"] - EXPECTED_CONTROL,
        "delta_vs_buy_and_hold": r_dboth_25["final_value"] - BUY_AND_HOLD,
        "lands_at_or_below_control": r_dboth_25["final_value"] <= EXPECTED_CONTROL,
    }
    print(json.dumps(step2, indent=2, default=str))
    results["step2_ceiling_x2_5"] = step2

    if call_hits / call_n < 0.999 if call_n else True:
        print("WARNING: call-level hit rate is not ~100%% -- label derivation "
              "may disagree with the scorer. See report for disposition.")

    # --- Step 3: D-up / D-down / D-both (D-both already run above @ 2.5pp) ---
    print("\n--- Step 3: directional split @ X=2.5pp ---")
    step3 = {"D-both": step2}
    for mode in ("D-up", "D-down"):
        events_m, extra_m, n_over = apply_oracle(events_real, oracle_labels, mode)
        r_m, ev_local_m = run_arm(events_m, extra_m, tier_fn, type_fn, driver_fn, prices, limit_pp=2.5)
        counts_m, shares_m, total_m = binding_shares(r_m)
        cash_m, dyi_m = cash_share_and_dollar_years(r_m)
        n_changed = sum(
            1 for e_real, e_m in zip(events_real, ev_local_m)
            if e_real.per_call_rec != e_m.per_call_rec
        )
        entry = {
            "n_events_overridden": n_over,
            "n_final_calls_changed_vs_real": n_changed,
            "binding_counts": counts_m,
            "binding_shares": shares_m,
            "n_funding_events": total_m,
            "avg_cash_share": cash_m,
            "dollar_years_invested": dyi_m,
            "final_value": r_m["final_value"],
            "delta_vs_control": r_m["final_value"] - EXPECTED_CONTROL,
            "delta_vs_buy_and_hold": r_m["final_value"] - BUY_AND_HOLD,
        }
        print(f"{mode}: {json.dumps(entry, indent=2, default=str)}")
        step3[mode] = entry
        step3[f"_{mode}_result_obj"] = r_m  # kept only in-memory for step5
    results["step3_directional_split"] = {
        k: v for k, v in step3.items() if not k.startswith("_")
    }

    # --- Step 4: real analyst vs D-both, X in {2.5, 10, unlimited} ---
    print("\n--- Step 4: prediction-vs-plumbing grid ---")
    grid = {}
    grid_result_objs = {}
    x_values = {"2.5": 2.5, "10": 10.0, "unlimited": None}
    # real analyst arm: events_real already carries the REAL per_call_rec /
    # trend layer (as produced by load_events_dedup_on()); re-run it fresh
    # per X value using the same real extra_fields captured at "D-up"/"D-down"
    # time above is unnecessary -- recompute directly from events_real via
    # recompute_trend_layer, which load_events_dedup_on() already did once at
    # limit_pp-independent trend-layer time (trend layer doesn't depend on X).
    for x_label, x_val in x_values.items():
        cell = dict(CELL_BASE, limit_pp=x_val)
        r_real = S.run_session_sweep_cell(events_real, prices, type_fn, driver_fn, tier_fn,
                                           phase_offset=PHASE_OFFSET, seed=SEED, **cell)
        counts_r, shares_r, total_r = binding_shares(r_real)
        cash_r, dyi_r = cash_share_and_dollar_years(r_real)
        dates_r, values_r = snap_series(r_real)
        dd_r = drawdown_stats(dates_r, values_r)
        grid[f"real_analyst_X{x_label}"] = {
            "final_value": r_real["final_value"],
            "avg_cash_share": cash_r,
            "dollar_years_invested": dyi_r,
            "binding_shares": shares_r,
            "max_drawdown_dollars": dd_r["max_drawdown_dollars"],
            "max_drawdown_pct": dd_r["max_drawdown_pct"],
        }
        grid_result_objs[f"real_analyst_X{x_label}"] = (r_real, dd_r)

        r_dboth, ev_local = run_arm(events_dboth, extra_dboth, tier_fn, type_fn,
                                     driver_fn, prices, limit_pp=x_val)
        counts_d, shares_d, total_d = binding_shares(r_dboth)
        cash_d, dyi_d = cash_share_and_dollar_years(r_dboth)
        dates_d, values_d = snap_series(r_dboth)
        dd_d = drawdown_stats(dates_d, values_d)
        grid[f"D-both_X{x_label}"] = {
            "final_value": r_dboth["final_value"],
            "avg_cash_share": cash_d,
            "dollar_years_invested": dyi_d,
            "binding_shares": shares_d,
            "max_drawdown_dollars": dd_d["max_drawdown_dollars"],
            "max_drawdown_pct": dd_d["max_drawdown_pct"],
        }
        grid_result_objs[f"D-both_X{x_label}"] = (r_dboth, dd_d)
        print(f"X={x_label}: real=${r_real['final_value']:,.2f}  D-both=${r_dboth['final_value']:,.2f}")

    results["step4_grid"] = grid

    # reading classification
    real_25 = grid["real_analyst_X2.5"]["final_value"]
    real_10 = grid["real_analyst_X10"]["final_value"]
    real_unl = grid["real_analyst_Xunlimited"]["final_value"]
    dboth_25 = grid["D-both_X2.5"]["final_value"]
    dboth_10 = grid["D-both_X10"]["final_value"]
    dboth_unl = grid["D-both_Xunlimited"]["final_value"]

    dboth_25_near_control = abs(dboth_25 - EXPECTED_CONTROL) < 0.05 * EXPECTED_CONTROL
    dboth_unl_far_above = (dboth_unl - EXPECTED_CONTROL) > 0.10 * EXPECTED_CONTROL
    dboth_unl_near_control = abs(dboth_unl - EXPECTED_CONTROL) < 0.05 * EXPECTED_CONTROL
    real_gain_from_x = real_unl - real_25
    dboth_gain_from_x = dboth_unl - dboth_25
    real_tracks_dboth_gain = (
        dboth_gain_from_x != 0 and
        abs(real_gain_from_x - dboth_gain_from_x) < 0.25 * abs(dboth_gain_from_x)
    )

    if dboth_25_near_control and dboth_unl_far_above:
        reading = "limited_by_plumbing"
    elif dboth_unl_near_control:
        reading = "limited_by_neither"
    elif real_tracks_dboth_gain:
        reading = "limited_by_throttle_for_both"
    else:
        reading = "mixed_or_inconclusive"

    results["step4_reading"] = {
        "classification": reading,
        "dboth_25_near_control_5pct": dboth_25_near_control,
        "dboth_unlimited_far_above_control_10pct": dboth_unl_far_above,
        "dboth_unlimited_near_control_5pct": dboth_unl_near_control,
        "real_gain_from_removing_x": real_gain_from_x,
        "dboth_gain_from_removing_x": dboth_gain_from_x,
        "real_tracks_dboth_gain": real_tracks_dboth_gain,
    }
    print(f"\nStep 4 reading: {reading}")

    # --- Step 5: drawdowns for every arm in this run ---
    print("\n--- Step 5: drawdowns ---")
    step5 = {}
    dates2, values2 = snap_series(r_dboth_25)
    step5["D-both_X2.5"] = drawdown_stats(dates2, values2)
    for mode in ("D-up", "D-down"):
        r_m = step3[f"_{mode}_result_obj"]
        dm, vm = snap_series(r_m)
        step5[mode] = drawdown_stats(dm, vm)
    for key, (r_obj, dd) in grid_result_objs.items():
        step5[key] = dd
    results["step5_drawdowns"] = step5
    print(json.dumps({k: v for k, v in step5.items()}, indent=2, default=str))

    # --- manifest ---
    manifest = {
        "run_id": "value-attribution-and-headroom-v2",
        "stage": "stage_d",
        "git_commit": commit,
        "git_dirty": dirty,
        "driver_file": "analysis/value_attribution_v2_stage_d_driver.py",
        "corpus_window": f"{WINDOW_START} to {WINDOW_END}, ALL16",
        "n_events": len(events_real),
        "checksums": checksums,
        "params": {
            "settled_configuration": dict(CELL_BASE, limit_pp=2.5),
            "seed": SEED,
            "phase_offset": PHASE_OFFSET,
            "oracle_synthesis": ORACLE_SYNTHESIS,
        },
        "reference_figures": {
            "settled_control": EXPECTED_CONTROL,
            "buy_and_hold": BUY_AND_HOLD,
        },
        "results": results,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nManifest written to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
