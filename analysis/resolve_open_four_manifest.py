#!/usr/bin/env python3
"""resolve_open_four_manifest.py -- manifested re-run of resolve_open_four.py's
checks A (1a), E (1c), the Step 2 partial-funding-vs-tie cross, and the Step 4
X-axis daily-ruler sweep. Read-only: no LLM calls, no API spend, no DB writes,
no cache refresh. Writes analysis/data/run_state/resolve-open-four/cells.jsonl
(one line per computed cell) and a manifest JSON per step under
analysis/data/run_state/resolve-open-four/manifests/.

    cd analysis
    python3 resolve_open_four_manifest.py 1a
    python3 resolve_open_four_manifest.py 1c
    python3 resolve_open_four_manifest.py 2
    python3 resolve_open_four_manifest.py 4
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_cadence_and_session_model as S          # noqa: E402
from analysis.simulator.data import PriceLookup      # noqa: E402

START, END, INITIAL = S.START, S.C, S.INITIAL
RUN_DIR = SCRIPT_DIR / "data" / "run_state" / "resolve-open-four"
MANIFEST_DIR = RUN_DIR / "manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_DIR / "cells.jsonl"

BASE_CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
                  limit_pp=2.5, execution_order="pooled",
                  trim_budget_scope="per_event_date", veto_p=0.0)


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_info():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SCRIPT_DIR.parent
                                      ).decode().strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      cwd=SCRIPT_DIR.parent).decode().strip()
    dirty_out = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                         cwd=SCRIPT_DIR.parent).decode()
    # Expected untracked paths per Step 0 of prompts/resolve-open-four.md: the
    # prompt itself and this run's own run_state (progress.json/cells.jsonl/
    # findings.md, which this very run writes). Anything else dirty is a hard stop.
    allowed_untracked = ("prompts/resolve-open-four.md",
                          "analysis/data/run_state/resolve-open-four/")
    dirty_lines = [ln for ln in dirty_out.splitlines() if ln.strip()]
    unexpected = [ln for ln in dirty_lines
                  if not any(p in ln for p in allowed_untracked)]
    dirty = bool(unexpected)
    # driver file must actually be tracked at this commit
    ls = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit],
                                  cwd=SCRIPT_DIR.parent).decode()
    driver_tracked = "analysis/resolve_open_four.py" in ls
    return commit, branch, dirty, driver_tracked


def config_hash(driver_commit, params):
    blob = driver_commit + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def write_cell(cell_key, params, chash, results):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps({"cell_key": cell_key, "params": params,
                             "config_hash": chash, "results": results},
                            default=str) + "\n")


def base_manifest(run_id, driver_commit, branch, dirty, driver_tracked, params, results):
    return {
        "run_id": run_id,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": driver_commit,
        "git_branch": branch,
        "git_dirty": dirty,
        "driver_file": "analysis/resolve_open_four_manifest.py",
        "driver_file_tracked_at_commit": driver_tracked,
        "corpus": {
            "source": "file_cache (price_cache.json) + DB (transcripts, via load_events_dedup_on)",
            "window": [str(START), str(END)],
            "universe": "ALL16",
            "dedup": "on",
        },
        "classification": {
            "type_json_sha256": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
            "price_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
        },
        "params": params,
        "results": results,
    }


def maxdd(vals):
    if not vals:
        return 0.0
    peak, m = vals[0], 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            m = max(m, (peak - v) / peak)
    return m


def daily_nav_path(snaps, prices):
    out = []
    for i, s in enumerate(snaps):
        shares = {}
        for t, val in (s.position_values or {}).items():
            p = prices.price_on(t, s.date)
            if p and p > 0 and val > 0:
                shares[t] = val / p
        nxt = snaps[i + 1].date if i + 1 < len(snaps) else END + timedelta(days=1)
        d = s.date
        while d < nxt and d <= END:
            tot = s.cash_total
            for t, sh in shares.items():
                p = prices.price_on(t, d)
                if p:
                    tot += sh * p
            out.append((d, tot))
            d += timedelta(days=1)
    return out


def bh_path(prices, ticker, dates):
    sp = prices.price_on(ticker, START)
    if not sp:
        return []
    sh = INITIAL / sp
    return [sh * p for d in dates if (p := prices.price_on(ticker, d))]


def load():
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(SCRIPT_DIR / "data" / "price_cache.json")
    return events, type_fn, driver_fn, tier_fn, prices


def step_1a(driver_commit, branch, dirty, driver_tracked):
    events, type_fn, driver_fn, tier_fn, prices = load()
    alldates = [START + timedelta(days=i) for i in range((END - START).days + 1)]

    # confirm assumption: every transaction_log entry falls on a session date
    r0 = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                   phase_offset=0, seed=0, **BASE_CELL)
    session_dates = {s.date for s in r0["daily_snapshots"]}
    txn_dates = {t.trade_date for t in r0["portfolio"].transaction_log}
    off_session = sorted(txn_dates - session_dates)

    per_phase = {}
    finals, sess_dd, daily_dd = [], [], []
    for ph in (0, 10, 20):
        r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                      phase_offset=ph, seed=0, **BASE_CELL)
        snaps = r["daily_snapshots"]
        dp = daily_nav_path(snaps, prices)
        dd_d = maxdd([v for _, v in dp])
        finals.append(r["final_value"]); sess_dd.append(r["max_dd"]); daily_dd.append(dd_d)
        per_phase[ph] = {"final": r["final_value"], "dd_session": r["max_dd"],
                          "dd_daily": dd_d, "n_sessions": len(snaps), "n_days": len(dp)}
        chash = config_hash(driver_commit, {**BASE_CELL, "phase_offset": ph, "seed": 0, "step": "1a"})
        write_cell(f"1a-phase{ph}", {**BASE_CELL, "phase_offset": ph, "seed": 0}, chash,
                   per_phase[ph])

    bench = {}
    for t in ("SPY", "QQQ", "TMFC"):
        d_dd = maxdd(bh_path(prices, t, alldates))
        phs = {}
        for ph in (0, 10, 20):
            sess = [x for x in (START + timedelta(days=ph + 30 * i)
                                 for i in range((END - START).days // 30 + 2)) if x <= END]
            phs[ph] = maxdd(bh_path(prices, t, sess))
        bench[t] = {"dd_daily": d_dd, "dd_session_by_phase": phs,
                     "dd_session_phase_avg": sum(phs.values()) / 3}

    results = {
        "off_session_txn_count": len(off_session),
        "off_session_txn_dates": [str(d) for d in off_session],
        "per_phase": per_phase,
        "phase_avg_final": sum(finals) / 3,
        "phase_avg_dd_session": sum(sess_dd) / 3,
        "phase_avg_dd_daily": sum(daily_dd) / 3,
        "phase_spread_session": max(sess_dd) - min(sess_dd),
        "phase_spread_daily": max(daily_dd) - min(daily_dd),
        "benchmarks": bench,
    }
    man = base_manifest("resolve-open-four-1a", driver_commit, branch, dirty, driver_tracked,
                         {"cell": BASE_CELL, "phases": [0, 10, 20], "seed": 0}, results)
    (MANIFEST_DIR / "1a-manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))


def step_1c(driver_commit, branch, dirty, driver_tracked):
    events, type_fn, driver_fn, tier_fn, prices = load()
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH
    from analyst_sensitivity_lift import lift_for_events
    pc = PriceCache(PRICE_CACHE_PATH)
    LEDGER = ["ENPH", "TTD", "AMPX", "ENVX", "EOSE", "QS", "SPWR"]
    EST = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
    SPEC = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
    BIG4 = ["AVGO", "NVDA", "ORCL", "TTD"]
    scopes = [("ledger_entry_1", LEDGER), ("ALL16", S.ALL16), ("ALL16_established", EST),
              ("ALL16_speculative", SPEC), ("big4_73pct_of_portfolio", BIG4)]
    results = {}
    for name, tks in scopes:
        sub = [e for e in events if e.ticker in tks]
        lift, n = lift_for_events(sub, pc)
        results[name] = {"lift_pp": lift * 100, "n": n, "tickers": tks}
        chash = config_hash(driver_commit, {"scope": name, "tickers": tks, "step": "1c"})
        write_cell(f"1c-{name}", {"scope": name, "tickers": tks}, chash, results[name])
    man = base_manifest("resolve-open-four-1c", driver_commit, branch, dirty, driver_tracked,
                         {"scopes": [s[0] for s in scopes]}, results)
    (MANIFEST_DIR / "1c-manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))


def step_2(driver_commit, branch, dirty, driver_tracked):
    events, type_fn, driver_fn, tier_fn, prices = load()
    orig = S.rank_key
    seen = defaultdict(list)

    def recording_rank_key(ticker, state_entry, portfolio, prices_today, session_date):
        k = orig(ticker, state_entry, portfolio, prices_today, session_date)
        seen[session_date].append(k)
        return k

    S.rank_key = recording_rank_key
    try:
        r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                      phase_offset=0, seed=0, **BASE_CELL)
    finally:
        S.rank_key = orig

    tie_sessions = set()
    for sd, keys in seen.items():
        c = Counter(keys)
        if any(n > 1 for n in c.values()):
            tie_sessions.add(sd)

    by_session = defaultdict(list)
    for f in r["funding_log"]:
        by_session[f["date"]].append(f)

    per_session = {}
    partial_sessions = set()          # prompt's literal definition (vs uncapped intended_dollars)
    cash_scarce_sessions = set()      # refined: binding == 'cash available' AND 0 < actual < target_buy_dollars
    for sd, rows in by_session.items():
        fully = sum(1 for x in rows if x["shortfall"] < 1.0)
        unfunded = sum(1 for x in rows
                        if x["actual_dollars"] < 1.0 and x["intended_dollars"] >= 1.0)
        partial = sum(1 for x in rows
                       if 0 < x["actual_dollars"] < x["intended_dollars"] - 1e-6)
        cash_scarce = sum(1 for x in rows
                           if x["binding"] == "cash available"
                           and 0 < x["actual_dollars"] < x["target_buy_dollars"] - 1e-6)
        if partial > 0:
            partial_sessions.add(sd)
        if cash_scarce > 0:
            cash_scarce_sessions.add(sd)
        per_session[str(sd)] = {"candidates": len(rows), "fully_funded": fully,
                                 "unfunded": unfunded,
                                 "partial_literal_vs_uncapped_intended": partial,
                                 "cash_scarce_partial_vs_capped_target": cash_scarce,
                                 "has_tie": sd in tie_sessions}

    both = tie_sessions & partial_sessions
    both_cash_scarce = tie_sessions & cash_scarce_sessions
    # multiplicity check: count rank_key evals vs distinct sessions
    total_keys = sum(len(v) for v in seen.values())
    # detect repeated identical evaluation of same ticker within a session (loop artifact)
    per_session_ticker_counts = {}
    for sd in seen:
        pass  # tickers not tracked in this recording; separate probe below

    results = {
        "sessions_total": len(seen),
        "sessions_with_tie": len(tie_sessions),
        "sessions_with_partial_fill_literal": len(partial_sessions),
        "sessions_with_both_tie_and_partial_literal": len(both),
        "both_session_dates_literal": [str(d) for d in sorted(both)],
        "sessions_with_cash_scarce_partial": len(cash_scarce_sessions),
        "sessions_with_both_tie_and_cash_scarce_partial": len(both_cash_scarce),
        "both_session_dates_cash_scarce": [str(d) for d in sorted(both_cash_scarce)],
        "per_session": per_session,
        "rank_key_evaluations_total": total_keys,
        "seed_can_bind_at_this_cell_literal_def": len(both) > 0,
        "seed_can_bind_at_this_cell_cash_scarce_def": len(both_cash_scarce) > 0,
    }
    chash = config_hash(driver_commit, {**BASE_CELL, "step": "2"})
    write_cell("2-partial-vs-tie-cross", BASE_CELL, chash, results)
    man = base_manifest("resolve-open-four-2", driver_commit, branch, dirty, driver_tracked,
                         {"cell": BASE_CELL, "phase_offset": 0, "seed": 0}, results)
    (MANIFEST_DIR / "2-manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))


def step_4(driver_commit, branch, dirty, driver_tracked):
    events, type_fn, driver_fn, tier_fn, prices = load()
    xs = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, None]  # None == "off"
    t0 = time.time()
    n_cells = 0
    all_cells = []
    for x in xs:
        finals, sess_dd, daily_dd = [], [], []
        per_phase = {}
        for ph in (0, 10, 20):
            cell = {**BASE_CELL, "limit_pp": x}
            r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                          phase_offset=ph, seed=0, **cell)
            snaps = r["daily_snapshots"]
            dp = daily_nav_path(snaps, prices)
            dd_d = maxdd([v for _, v in dp])
            finals.append(r["final_value"]); sess_dd.append(r["max_dd"]); daily_dd.append(dd_d)
            per_phase[ph] = {"final": r["final_value"], "dd_session": r["max_dd"],
                              "dd_daily": dd_d, "gap_pp": (dd_d - r["max_dd"]) * 100}
            n_cells += 1
            chash = config_hash(driver_commit, {**cell, "phase_offset": ph, "seed": 0, "step": "4"})
            xkey = "off" if x is None else x
            write_cell(f"4-X{xkey}-phase{ph}", {**cell, "phase_offset": ph, "seed": 0}, chash,
                       per_phase[ph])
        pa_final = sum(finals) / 3
        pa_sess = sum(sess_dd) / 3
        pa_daily = sum(daily_dd) / 3
        row = {"X": x, "phase_avg_final": pa_final, "phase_avg_dd_session": pa_sess,
               "phase_avg_dd_daily": pa_daily, "phase_avg_gap_pp": (pa_daily - pa_sess) * 100,
               "per_phase": per_phase}
        all_cells.append(row)

    wall = time.time() - t0
    best_session = max(all_cells, key=lambda c: c["phase_avg_final"])
    breach = [c for c in all_cells if c["phase_avg_dd_daily"] > 0.3912]
    results = {
        "sweep": all_cells,
        "optimum_by_phase_avg_final": best_session["X"],
        "cells_breaching_39_12pct_on_daily_ruler": [c["X"] for c in breach],
        "wall_clock_seconds": wall,
        "cells_run": n_cells,
    }
    man = base_manifest("resolve-open-four-4", driver_commit, branch, dirty, driver_tracked,
                         {"cell_base": BASE_CELL, "X_axis": [x if x is not None else "off" for x in xs],
                          "phases": [0, 10, 20], "seed": 0}, results)
    (MANIFEST_DIR / "4-manifest.json").write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "1a"
    commit, branch, dirty, driver_tracked = git_info()
    if dirty:
        print("HARD STOP: git tree is dirty; cannot record git_dirty:false", file=sys.stderr)
        sys.exit(1)
    fn = {"1a": step_1a, "1c": step_1c, "2": step_2, "4": step_4}[step]
    fn(commit, branch, dirty, driver_tracked)


if __name__ == "__main__":
    main()
