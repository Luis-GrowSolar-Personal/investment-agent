#!/usr/bin/env python3
"""
allocator_book_test_matched.py -- prompts/allocator-book-test-matched.md ($0).

Corrects prompts/allocator-book-test.md / wrap-ups/allocator-book-test-out.md:
the first run's no-skill controls (arms 2R, 3R) matched arm 2/3 on NUMBER OF
TRIMS, not on MONEY MOVED, and arm 3 re-flags names it has already sold to
zero 55% of the time -- so the control moved far more money into QQQ than
its arm, biasing the "analyst chose the trims" reading toward the control.

This script imports analysis/allocator_book_test.py (extend, do not fork):
reuses simulate() (now trace-capable), FastPrices, precompute_schedules,
companies_and_strata, load_calls, build_random_books, build_stratified_books,
metrics_from_snaps, quarter, A.boot, return_per_dd, cagr_of. It does NOT
recompute t1/t2 (read from the first run's results.json) and does NOT touch
analysis/data/run_state/allocator-book-test/ (writes to
analysis/data/run_state/allocator-book-test-matched/ instead).

Usage:
  python3 allocator_book_test_matched.py run
"""
from __future__ import annotations
import sys, json, random
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "analysis")); sys.path.insert(0, str(REPO))
import allocator_book_test as M              # noqa: E402
import p6_output_format_analysis as A        # noqa: E402
from analyst_direct_scorer import PriceCache  # noqa: E402

STATE_OLD = M.RS / "allocator-book-test"
STATE = M.RS / "allocator-book-test-matched"
ARMS_ALL = M.ARMS_FIXED + ["2M", "3M"] + M.ARMS_CONTROL   # ARMS_CONTROL (2R,3R) kept, superseded


def run_matched_control(control_arm_name, base_arm_events, book_tickers, weight, sessions, fp,
                         first_date, all_action_book, rng):
    """Replay base_arm_events (a trace from simulate(..., trace_out=...)) as a
    money-matched no-skill control. At each step with points_moved p > 0, move
    p points of the CONTROL's own book value into QQQ from a randomly chosen
    eligible name (same quarter as the step's session, held by the control,
    any call flagged or not). Step 2 of a two-step group prefers the group's
    step-1 name if the control still holds it. If the chosen name's position
    is smaller than p, sell it and draw another eligible name for the rest,
    until p is moved or no eligible name remains (shortfall recorded)."""
    shares = {t: 0.0 for t in book_tickers}
    embryo = {t: 0.0 for t in book_tickers}
    bought_in = {t: False for t in book_tickers}
    dest_shares = 0.0
    group_primary = {}   # group_id -> name chosen for step 1
    n_trims = 0
    points_moved = 0.0
    full_sells = 0
    trims_moved_nothing = 0
    shortfall_total = 0.0

    events_by_session = defaultdict(list)
    for ev in base_arm_events:
        events_by_session[ev["session_idx"]].append(ev)

    snaps = []
    for i, sd in enumerate(sessions):
        for t in book_tickers:
            if bought_in[t]:
                continue
            fdt = first_date.get(t)
            if fdt is None or fdt > sd:
                if i == 0:
                    qp = fp.price_on("QQQ", sd)
                    if qp:
                        embryo[t] = weight / qp
                continue
            if i == 0:
                pr = fp.price_on(t, sd)
                if pr:
                    shares[t] = weight / pr
                    bought_in[t] = True
            elif embryo[t] > 0:
                ev_val = embryo[t] * (fp.price_on("QQQ", sd) or 0.0)
                pr = fp.price_on(t, sd)
                if pr:
                    shares[t] = ev_val / pr
                    bought_in[t] = True
                    embryo[t] = 0.0

        total_val = (sum(shares[t] * (fp.price_on(t, sd) or 0.0) for t in book_tickers if bought_in[t])
                     + sum(embryo[t] * (fp.price_on("QQQ", sd) or 0.0) for t in book_tickers if not bought_in[t])
                     + dest_shares * (fp.price_on("QQQ", sd) or 0.0))

        for ev in events_by_session.get(i, []):
            n_trims += 1
            p_want = ev["points_moved"]
            if p_want <= 0:
                trims_moved_nothing += 1
                continue
            want_dollar = (p_want / 100.0) * total_val
            q = M.quarter(sd)

            def eligible(exclude):
                out = []
                for t in book_tickers:
                    if t in exclude or shares.get(t, 0.0) <= 0:
                        continue
                    for idx, _c in all_action_book.get(t, []):
                        if M.quarter(sessions[idx]) == q:
                            out.append(t)
                            break
                return out

            used = set()
            moved_dollar = 0.0
            preferred = None
            if ev["step_no"] == 2 and group_primary.get(ev["group_id"]) and shares.get(group_primary[ev["group_id"]], 0.0) > 0:
                preferred = group_primary[ev["group_id"]]

            first_pick_recorded = False
            while moved_dollar < want_dollar - 1e-9:
                if preferred is not None and preferred not in used:
                    name = preferred
                else:
                    elig = eligible(used)
                    if not elig:
                        break
                    name = elig[rng.randrange(len(elig))]
                price_n = fp.price_on(name, sd)
                pos_val = shares.get(name, 0.0) * (price_n or 0.0)
                if pos_val <= 0 or not price_n:
                    used.add(name)
                    preferred = None
                    continue
                take = min(pos_val, want_dollar - moved_dollar)
                shares[name] -= take / price_n
                moved_dollar += take
                if not first_pick_recorded and ev["step_no"] == 1:
                    group_primary[ev["group_id"]] = name
                    first_pick_recorded = True
                used.add(name)
                preferred = None
                if take >= pos_val - 1e-9:
                    full_sells += 1

            dp = fp.price_on("QQQ", sd)
            if dp and moved_dollar > 0:
                dest_shares += moved_dollar / dp
            if total_val > 0:
                points_moved += 100 * moved_dollar / total_val
            shortfall = max(0.0, want_dollar - moved_dollar)
            shortfall_total += shortfall
            if moved_dollar <= 0:
                trims_moved_nothing += 1

        pv = {}
        for t in book_tickers:
            if bought_in[t] and shares[t] > 0:
                pv[t] = pv.get(t, 0.0) + shares[t] * (fp.price_on(t, sd) or 0.0)
            elif not bought_in[t]:
                pv["QQQ"] = pv.get("QQQ", 0.0) + embryo[t] * (fp.price_on("QQQ", sd) or 0.0)
        if dest_shares > 0:
            pv["QQQ"] = pv.get("QQQ", 0.0) + dest_shares * (fp.price_on("QQQ", sd) or 0.0)
        snaps.append(M.Snap(sd, pv))

    return {"snaps": snaps, "n_trims": n_trims, "points_moved": points_moved,
            "full_sells": full_sells, "trims_moved_nothing": trims_moved_nothing,
            "shortfall_total": shortfall_total}


def run_book_matched(book_tickers, book_id, schedules, arrays, first_date, start, end):
    fp = M.FastPrices(arrays, start)
    weight = M.INITIAL / len(book_tickers)
    per_phase = {arm: [] for arm in ARMS_ALL}
    match_check = []   # per phase: {"arm": diff between arm and control's points_moved}

    for ph in M.PHASES:
        sched = schedules[ph]
        sessions = sched["sessions"]
        all_action_book = {t: sched["all_action"].get(t, []) for t in book_tickers}
        arm2_groups_book = [(t, g) for t in book_tickers for g in sched["arm2_groups"].get(t, [])]
        arm3_groups_book = [(t, g) for t in book_tickers for g in sched["arm3_groups"].get(t, [])]

        def rec(res, arm):
            per_phase[arm].append({
                **M.metrics_from_snaps(res["snaps"], fp, start, end),
                "n_trims": res["n_trims"], "points_moved": res["points_moved"],
                "full_sells": res["full_sells"],
                "trims_moved_nothing": res["trims_moved_nothing"],
            })

        r0 = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, [], "pct", M.fixed_resolver)
        rec({**r0, "trims_moved_nothing": 0}, "0")

        r1 = M.simulate(["QQQ"], M.INITIAL, sessions, "QQQ", fp, first_date, [], "pct", M.fixed_resolver)
        rec({**r1, "trims_moved_nothing": 0}, "1")

        trace2, trace3 = [], []
        r2 = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm2_groups_book, "pct",
                         M.fixed_resolver, trace_out=trace2)
        n2_nothing = sum(1 for e in trace2 if e["points_moved"] <= 0)
        rec({**r2, "trims_moved_nothing": n2_nothing}, "2")

        r3 = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "pct",
                         M.fixed_resolver, trace_out=trace3)
        n3_nothing = sum(1 for e in trace3 if e["points_moved"] <= 0)
        rec({**r3, "trims_moved_nothing": n3_nothing}, "3")

        r3f = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "frac", M.fixed_resolver)
        rec({**r3f, "trims_moved_nothing": 0}, "3F")

        r3s = M.simulate(book_tickers, weight, sessions, "SPY", fp, first_date, arm3_groups_book, "pct", M.fixed_resolver)
        rec({**r3s, "trims_moved_nothing": 0}, "3S")

        # superseded count-matched controls, kept for reference
        rng2 = random.Random((M.SEED, book_id, "2R", ph))
        resolver2 = M.make_control_resolver(book_tickers, all_action_book, sessions, rng2)
        r2r = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm2_groups_book, "pct", resolver2)
        rec({**r2r, "trims_moved_nothing": 0}, "2R")

        rng3 = random.Random((M.SEED, book_id, "3R", ph))
        resolver3 = M.make_control_resolver(book_tickers, all_action_book, sessions, rng3)
        r3r = M.simulate(book_tickers, weight, sessions, "QQQ", fp, first_date, arm3_groups_book, "pct", resolver3)
        rec({**r3r, "trims_moved_nothing": 0}, "3R")

        # money-matched controls
        rng2m = random.Random((M.SEED, book_id, "2M", ph))
        r2m = run_matched_control("2M", trace2, book_tickers, weight, sessions, fp, first_date, all_action_book, rng2m)
        rec(r2m, "2M")

        rng3m = random.Random((M.SEED, book_id, "3M", ph))
        r3m = run_matched_control("3M", trace3, book_tickers, weight, sessions, fp, first_date, all_action_book, rng3m)
        rec(r3m, "3M")

        match_check.append({
            "2": {"arm_points": r2["points_moved"], "control_points": r2m["points_moved"],
                  "diff": abs(r2["points_moved"] - r2m["points_moved"]), "shortfall": r2m["shortfall_total"]},
            "3": {"arm_points": r3["points_moved"], "control_points": r3m["points_moved"],
                  "diff": abs(r3["points_moved"] - r3m["points_moved"]), "shortfall": r3m["shortfall_total"]},
        })

    out = {"book_id": book_id, "tickers": book_tickers}
    for arm, runs in per_phase.items():
        out[arm] = {
            "final_value": float(np.mean([r["final_value"] for r in runs])),
            "cagr": float(np.mean([r["cagr"] for r in runs])),
            "max_dd": float(np.mean([r["max_dd"] for r in runs])),
            "return_per_dd": float(np.mean([r["return_per_dd"] for r in runs])),
            "n_trims": float(np.mean([r["n_trims"] for r in runs])),
            "points_moved": float(np.mean([r["points_moved"] for r in runs])),
            "trims_moved_nothing": float(np.mean([r["trims_moved_nothing"] for r in runs])),
            "full_sell_share": (sum(r["full_sells"] for r in runs) / sum(r["n_trims"] for r in runs)
                                 if sum(r["n_trims"] for r in runs) > 0 else None),
        }
    out["match_check"] = {
        "2": {"arm_points_avg": float(np.mean([m["2"]["arm_points"] for m in match_check])),
              "control_points_avg": float(np.mean([m["2"]["control_points"] for m in match_check])),
              "max_diff": max(m["2"]["diff"] for m in match_check),
              "shortfall_total": sum(m["2"]["shortfall"] for m in match_check)},
        "3": {"arm_points_avg": float(np.mean([m["3"]["arm_points"] for m in match_check])),
              "control_points_avg": float(np.mean([m["3"]["control_points"] for m in match_check])),
              "max_diff": max(m["3"]["diff"] for m in match_check),
              "shortfall_total": sum(m["3"]["shortfall"] for m in match_check)},
    }
    return out


def _worker(args):
    book_tickers, book_id, schedules, arrays, first_date, start, end = args
    return run_book_matched(book_tickers, book_id, schedules, arrays, first_date, start, end)


def gain_stats(results, arm, base="0"):
    return M.gain_stats(results, arm, base)


def pass_rule(results, pool, arm, base="0"):
    return M.pass_rule(results, pool, arm, base)


def diff_pass_rule(results, pool, arm_a, ctrl_a, arm_b, ctrl_b):
    """(arm_a - ctrl_a) - (arm_b - ctrl_b), per book, in return_per_dd. Pass rule
    applied to this difference series directly (reading 3)."""
    def d(b):
        return (b[arm_a]["return_per_dd"] - b[ctrl_a]["return_per_dd"]) - (b[arm_b]["return_per_dd"] - b[ctrl_b]["return_per_dd"])
    vals = [d(b) for b in results]
    win_share = 100 * sum(v > 0 for v in vals) / len(vals)
    rows = [{"ticker": f"book{i}", "gain": v} for i, v in enumerate(vals)]
    lo, hi, nv = A.boot(rows, lambda s: float(np.median([r["gain"] for r in s])))
    lowest = (101.0, None)
    for co in pool:
        kept = [b for b in results if co not in b["tickers"]]
        if len(kept) < 5:
            continue
        kv = [d(b) for b in kept]
        ws = 100 * sum(x > 0 for x in kv) / len(kv)
        if ws < lowest[0]:
            lowest = (ws, co)
    passed = win_share >= 70.0 and lo > 0 and lowest[0] >= 70.0
    return {"n": len(vals), "win_share_pct": round(win_share, 1), "median_gain": round(float(np.median(vals)), 4),
            "range": [round(lo, 4), round(hi, 4)], "valid_draws": nv,
            "company_removal": {"lowest_win_share_pct": round(lowest[0], 1), "company": lowest[1]},
            "passes_70pct_rule": bool(passed)}


def per_point_diagnostic(results, arm, base="0"):
    vals = []
    for b in results:
        pm = b[arm]["points_moved"]
        if pm and pm > 0:
            vals.append((b[arm]["return_per_dd"] - b[base]["return_per_dd"]) / pm)
    return {"n": len(vals), "median_gain_per_point": round(float(np.median(vals)), 6) if vals else None}


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    frozen = json.loads((STATE_OLD / "results.json").read_text())
    t1, t2 = frozen["t1"], frozen["t2"]
    megacap, mid, spec = frozen["megacap_pool"], frozen["mid_pool"], frozen["spec_pool"]

    calls = M.load_calls()
    companies, megacap2, mid2, spec2 = M.companies_and_strata(calls)
    assert megacap2 == megacap and mid2 == mid and spec2 == spec

    acache = PriceCache(M.CANON_CACHE)
    spy_dates = sorted(acache._data["QQQ"].keys())
    last_call = max(c["call_date"] for c in calls)
    start = date(2020, 1, 2)
    target_end = last_call + timedelta(days=M.DAYS_HORIZON)
    end = next(date.fromisoformat(d) for d in spy_dates if date.fromisoformat(d) >= target_end)
    assert start.isoformat() == frozen["window"]["start"] and end.isoformat() == frozen["window"]["end"]

    arrays, first_date = M.load_fast_prices(companies, start, end)
    schedules, n_no_entry = M.precompute_schedules(calls, start, end, t1, t2, acache)

    random_books = M.build_random_books(companies)
    strat_books = M.build_stratified_books(megacap, mid, spec)
    strat_pool = sorted(set(megacap) | set(mid) | set(spec))

    # Step 1: assert book lists identical to the first run
    old_random = [b["tickers"] for b in frozen["random_books"]["books"]]
    old_strat = [b["tickers"] for b in frozen["stratified_books"]["books"]]
    assert random_books == old_random, "random book lists differ from the first run"
    assert strat_books == old_strat, "stratified book lists differ from the first run"

    print(f"Window: {start} .. {end}  n_no_entry={n_no_entry}")
    print(f"Books match first run: random={random_books == old_random} stratified={strat_books == old_strat}")
    print("Simulating (reproduction + money-matched controls)...")

    def run_set(books, tag):
        jobs = [(b, f"{tag}{i}", schedules, arrays, first_date, start, end) for i, b in enumerate(books)]
        results = [None] * len(jobs)
        with ProcessPoolExecutor() as ex:
            futs = {ex.submit(_worker, j): i for i, j in enumerate(jobs)}
            done = 0
            for fut in as_completed(futs):
                i = futs[fut]
                results[i] = fut.result()
                done += 1
                if done % 50 == 0:
                    print(f"  {tag}: {done}/{len(jobs)}")
        return results

    random_results = run_set(random_books, "R")
    strat_results = run_set(strat_books, "S")

    # Step 1 reproduction check
    def repro_check(results, old_books):
        max_diff = 0.0
        n_checked = 0
        for r, old in zip(results, old_books):
            for arm in ("0", "1", "2", "3", "3F", "3S"):
                for k in ("final_value", "cagr", "max_dd", "return_per_dd"):
                    d = abs(r[arm][k] - old[arm][k])
                    max_diff = max(max_diff, d)
                    n_checked += 1
        return {"n_checked": n_checked, "max_abs_diff": max_diff}

    repro_random = repro_check(random_results, frozen["random_books"]["books"])
    repro_strat = repro_check(strat_results, frozen["stratified_books"]["books"])
    print("Reproduction check (random):", repro_random)
    print("Reproduction check (stratified):", repro_strat)
    if repro_random["max_abs_diff"] > 1e-6 or repro_strat["max_abs_diff"] > 1e-6:
        print("STOP: reproduction mismatch exceeds tolerance -- something other than the controls changed.")
        (STATE / "results.json").write_text(json.dumps({
            "STOPPED": True, "reason": "reproduction mismatch",
            "repro_random": repro_random, "repro_strat": repro_strat,
        }, indent=1, default=float))
        sys.exit(1)

    def match_stats(results):
        diffs2 = [b["match_check"]["2"]["max_diff"] for b in results]
        diffs3 = [b["match_check"]["3"]["max_diff"] for b in results]
        return {
            "2": {"median_diff": round(float(np.median(diffs2)), 4), "max_diff": round(max(diffs2), 4),
                  "pct_within_0.5": round(100 * sum(d <= 0.5 for d in diffs2) / len(diffs2), 1),
                  "shortfall_total": round(sum(b["match_check"]["2"]["shortfall"] for b in results), 2)},
            "3": {"median_diff": round(float(np.median(diffs3)), 4), "max_diff": round(max(diffs3), 4),
                  "pct_within_0.5": round(100 * sum(d <= 0.5 for d in diffs3) / len(diffs3), 1),
                  "shortfall_total": round(sum(b["match_check"]["3"]["shortfall"] for b in results), 2)},
        }
    match_random = match_stats(random_results)
    match_strat = match_stats(strat_results)
    print("Match check (random):", json.dumps(match_random))
    print("Match check (stratified):", json.dumps(match_strat))
    match_ok = (match_random["2"]["pct_within_0.5"] >= 95 and match_random["3"]["pct_within_0.5"] >= 95
                and match_strat["2"]["pct_within_0.5"] >= 95 and match_strat["3"]["pct_within_0.5"] >= 95)
    if not match_ok:
        print("STOP: money-matched control does not match its arm's points moved within 0.5pp in >=95% of books.")

    def summarize(results, pool):
        s = {}
        for arm in ARMS_ALL:
            s[arm] = {
                "median_final_value": round(float(np.median([b[arm]["final_value"] for b in results])), 2),
                "median_cagr": round(float(np.median([b[arm]["cagr"] for b in results])), 4),
                "median_max_dd": round(float(np.median([b[arm]["max_dd"] for b in results])), 4),
                "median_return_per_dd": round(float(np.median([b[arm]["return_per_dd"] for b in results])), 4),
                "median_points_moved": round(float(np.median([b[arm]["points_moved"] for b in results])), 2),
                "median_trims_moved_nothing": round(float(np.median([b[arm]["trims_moved_nothing"] for b in results])), 2),
            }
            if arm != "0":
                s[arm]["vs_arm0"] = pass_rule(results, pool, arm, "0")
        s["3_vs_3M"] = pass_rule(results, pool, "3", "3M")
        s["2_vs_2M"] = pass_rule(results, pool, "2", "2M")
        s["3_vs_2_confounded"] = pass_rule(results, pool, "3", "2")
        s["severity_over_plain"] = diff_pass_rule(results, pool, "3", "3M", "2", "2M")
        s["per_point"] = {a: per_point_diagnostic(results, a, "0") for a in ("2", "3", "2M", "3M")}
        return s

    random_summary = summarize(random_results, companies)
    strat_summary = summarize(strat_results, strat_pool)

    r3v0 = random_summary["3"]["vs_arm0"]
    r3v3m = random_summary["3_vs_3M"]
    headline = ("severity-sized trims add value" if r3v0["passes_70pct_rule"] and r3v3m["passes_70pct_rule"]
                else "own more QQQ" if r3v0["passes_70pct_rule"] and not r3v3m["passes_70pct_rule"]
                else "do not add value")

    out = {
        "t1": t1, "t2": t2, "n_flagged": frozen["n_flagged"],
        "window": frozen["window"],
        "reproduction_check": {"random": repro_random, "stratified": repro_strat},
        "match_check": {"random": match_random, "stratified": match_strat, "passes_95pct_rule": match_ok},
        "random_books": {"n": len(random_results), "summary": random_summary},
        "stratified_books": {"n": len(strat_results), "summary": strat_summary},
        "headline": headline,
        "units_carried_from_first_run": frozen.get("random_books", {}).get("summary", {}).get("units_reading")
                                          if "random_books" in frozen else None,
        "arm_M": {"ran": False, "note": "unchanged from the first run -- still needs a DB-free, non-ALL16 loader"},
    }
    (STATE / "results.json").write_text(json.dumps(out, indent=1, default=float))
    print("HEADLINE:", headline)
    print(json.dumps({"headline": headline, "3_vs_3M_random": r3v3m,
                       "2_vs_2M_random": random_summary["2_vs_2M"],
                       "severity_over_plain_random": random_summary["severity_over_plain"]},
                      indent=1, default=float))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "run":
        print(__doc__)
        sys.exit(1)
    main()
