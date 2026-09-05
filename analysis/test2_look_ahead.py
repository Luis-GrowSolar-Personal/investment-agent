#!/usr/bin/env python3
"""test2_look_ahead.py -- driver for prompts/test2-look-ahead-hit-rate-by-year.md.

Steps:
  1a. X limit -- max_session_pp_change at the settled cell, phases 0/10/20.
  1b. Off-session forced-liquidation-for-tax transactions on AAPL.
  1c. Risk-adjusted X table, recomputed from resolve-open-four's own
      4-manifest.json (gain / dd, both rulers). No new simulator run.
  2.  Scoreable Analysis rows by call year (DB, read-only), forward-window
      cutoff, model-version census, ticker coverage by year.
  3.  The hit-rate/lift/headroom/bearish-accuracy series, decomposed, with
      binomial CIs.
  4.  Confound controls: fixed-ticker subset, year x scope grid.

Read-only: no LLM calls, no API spend, no DB writes (SELECT only), no cache
refresh. Writes analysis/data/run_state/test2-look-ahead-hit-rate-by-year/
manifests/<step>-manifest.json and appends to cells.jsonl.

    cd analysis
    python3 test2_look_ahead.py 1a
    python3 test2_look_ahead.py 1b
    python3 test2_look_ahead.py 1c
    python3 test2_look_ahead.py 2
    python3 test2_look_ahead.py 3
    python3 test2_look_ahead.py 4
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

RUN_ID = "test2-look-ahead-hit-rate-by-year"
RUN_DIR = SCRIPT_DIR / "data" / "run_state" / RUN_ID
MANIFEST_DIR = RUN_DIR / "manifests"
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_DIR / "cells.jsonl"
DRIVER_FILE = "analysis/test2_look_ahead.py"

ALL16 = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA",
         "AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]
ESTABLISHED = ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"]
SPECULATIVE = ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"]

BASE_CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
                  limit_pp=2.5, execution_order="pooled",
                  trim_budget_scope="per_event_date", veto_p=0.0)


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_info():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      cwd=REPO).decode().strip()
    dirty_out = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                         cwd=REPO).decode()
    allowed_untracked = (
        "prompts/resolve-open-four.md",
        "prompts/test2-hit-rate-by-year.md",
        "prompts/test2-look-ahead-hit-rate-by-year.md",
        "analysis/data/run_state/corpus-archive/",
        "analysis/data/run_state/test2-look-ahead-hit-rate-by-year/",
        "docs/handoffs/2026-09-05-state-of-play.md",  # another session's in-flight doc, not ours
    )
    dirty_lines = [ln for ln in dirty_out.splitlines() if ln.strip()]
    unexpected = [ln for ln in dirty_lines if not any(p in ln for p in allowed_untracked)]
    dirty = bool(unexpected)
    ls = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO).decode()
    driver_tracked = DRIVER_FILE in ls
    return commit, branch, dirty, driver_tracked, unexpected


def config_hash(driver_commit, params):
    blob = driver_commit + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def write_cell(cell_key, params, chash, results):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps({"cell_key": cell_key, "params": params,
                             "config_hash": chash, "results": results}, default=str) + "\n")


def base_manifest(run_id, driver_commit, branch, dirty, driver_tracked, params, results, corpus_extra=None):
    m = {
        "run_id": run_id,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": driver_commit,
        "git_branch": branch,
        "git_dirty": dirty,
        "driver_file": DRIVER_FILE,
        "driver_file_tracked_at_commit": driver_tracked,
        "corpus": {
            "price_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "price_cache.json"),
            "fundamentals_cache_sha256": sha256_file(SCRIPT_DIR / "data" / "fundamentals_cache.json"),
            "type_json_sha256": sha256_file(SCRIPT_DIR / "data" / "type_classifications.json"),
        },
        "params": params,
        "results": results,
    }
    if corpus_extra:
        m["corpus"].update(corpus_extra)
    return m


def write_manifest(step, manifest):
    p = MANIFEST_DIR / f"{step}-manifest.json"
    p.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"manifest written -> {p}")


# ---------------------------------------------------------------------------
# Step 1a/1b -- settled-cell simulator run
# ---------------------------------------------------------------------------

def load_sim():
    import sweep_cadence_and_session_model as S
    from analysis.simulator.data import PriceLookup
    events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
    prices = PriceLookup.from_cache(SCRIPT_DIR / "data" / "price_cache.json")
    return S, events, type_fn, driver_fn, tier_fn, prices


def step_1a(driver_commit, branch, dirty, driver_tracked):
    S, events, type_fn, driver_fn, tier_fn, prices = load_sim()
    per_phase = {}
    for ph in (0, 10, 20):
        r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                      phase_offset=ph, seed=0, **BASE_CELL)
        per_phase[ph] = {"max_session_pp_change": r["max_session_pp_change"],
                          "final_value": r["final_value"], "max_dd_session": r["max_dd"]}
        chash = config_hash(driver_commit, {**BASE_CELL, "phase_offset": ph, "seed": 0, "step": "1a"})
        write_cell(f"1a-phase{ph}", {**BASE_CELL, "phase_offset": ph, "seed": 0}, chash, per_phase[ph])

    all_le_25 = all(v["max_session_pp_change"] <= 2.5 + 1e-9 for v in per_phase.values())
    all_eq_25 = all(abs(v["max_session_pp_change"] - 2.5) < 1e-6 for v in per_phase.values())
    results = {"per_phase": per_phase, "x_limit_configured_pp": 2.5,
               "x_limit_holds": all_le_25, "x_limit_binds_exactly": all_eq_25}
    write_manifest("1a", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked,
                                        {**BASE_CELL, "phases": [0, 10, 20], "seed": 0}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def step_1b(driver_commit, branch, dirty, driver_tracked):
    S, events, type_fn, driver_fn, tier_fn, prices = load_sim()
    r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                                  phase_offset=0, seed=0, **BASE_CELL)
    txns = r["portfolio"].transaction_log
    tax_txns = [t for t in txns if getattr(t, "reason", None) == "forced-liquidation-for-tax"]
    rows = []
    for t in tax_txns:
        actual_close, _ = prices_lookup_close(prices, t.ticker, t.trade_date)
        rows.append({
            "ticker": t.ticker, "trade_date": str(t.trade_date),
            "side": t.side, "shares": t.shares, "price_used": t.price,
            "actual_close_that_day": actual_close,
            "is_bookkeeping_stamp": (actual_close is not None and
                                      abs(actual_close - t.price) > 1e-6),
        })
    chash = config_hash(driver_commit, {**BASE_CELL, "phase_offset": 0, "seed": 0, "step": "1b"})
    write_cell("1b", {**BASE_CELL, "phase_offset": 0, "seed": 0}, chash, {"tax_transactions": rows})
    results = {"n_tax_transactions": len(tax_txns), "tax_transactions": rows}
    write_manifest("1b", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked,
                                        {**BASE_CELL, "phase_offset": 0, "seed": 0}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def prices_lookup_close(price_lookup, ticker, d):
    """Best-effort: read the raw price_cache.json for the literal calendar
    date (not the simulator's on-or-after lookup), to compare against the
    transaction's stamped price."""
    data = json.loads((SCRIPT_DIR / "data" / "price_cache.json").read_text())
    day = data.get(ticker, {})
    key = d.isoformat() if hasattr(d, "isoformat") else str(d)
    return day.get(key), key


# ---------------------------------------------------------------------------
# Step 1c -- risk-adjusted X, from resolve-open-four's own 4-manifest.json
# ---------------------------------------------------------------------------

def step_1c(driver_commit, branch, dirty, driver_tracked):
    src = REPO / "analysis" / "data" / "run_state" / "resolve-open-four" / "manifests" / "4-manifest.json"
    src_data = json.loads(src.read_text())
    rows = []
    for cell in src_data["results"]["sweep"]:
        X = cell["X"]
        final = cell["phase_avg_final"]
        gain = final - 100_000.0
        dd_s_pct = cell["phase_avg_dd_session"] * 100
        dd_d_pct = cell["phase_avg_dd_daily"] * 100
        rows.append({
            "X": X, "phase_avg_final": final, "gain": gain,
            "dd_session_pct": dd_s_pct, "dd_daily_pct": dd_d_pct,
            "gain_per_dd_session": gain / dd_s_pct if dd_s_pct else None,
            "gain_per_dd_daily": gain / dd_d_pct if dd_d_pct else None,
        })
    finite_x = [r for r in rows if isinstance(r["X"], (int, float))]
    best_session = max(finite_x, key=lambda r: r["gain_per_dd_session"])
    best_daily = max(finite_x, key=lambda r: r["gain_per_dd_daily"])
    results = {
        "rows": rows,
        "best_X_session_ruler": best_session["X"],
        "best_X_daily_ruler": best_daily["X"],
        "ruler_reorders": best_session["X"] != best_daily["X"],
        "source_manifest": str(src.relative_to(REPO)),
        "source_key": "results.sweep[*].{X,phase_avg_final,phase_avg_dd_session,phase_avg_dd_daily}",
        "measure": "gain-per-drawdown-point = (phase_avg_final - 100000) / (drawdown pct points), "
                   "phase-averaged (phases 0/10/20), seed 0, forward draw -- not this run's "
                   "choice of ruler for drawdown itself, only the derived ratio. Not a "
                   "previously-used project measure; ignores path and duration.",
    }
    chash = config_hash(driver_commit, {"step": "1c", "source": str(src)})
    write_cell("1c", {"source_manifest": str(src.relative_to(REPO))}, chash, results)
    write_manifest("1c", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked,
                                        {"source_manifest": str(src.relative_to(REPO))}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


# ---------------------------------------------------------------------------
# Step 2/2a/3/4 -- DB-scored series
# ---------------------------------------------------------------------------

def fetch_analysis_rows():
    from dotenv import load_dotenv
    import os, psycopg2, psycopg2.extras
    load_dotenv(REPO / ".env")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT tk.symbol AS ticker, t."callDate"::date AS call_date,
                   a.recommendation AS rec, a."thesisHealth" AS health,
                   a."modelVersion" AS model_version, a."promptVersion" AS prompt_version,
                   a."createdAt" AS created_at
            FROM "Analysis" a
            JOIN "Transcript" t ON a."transcriptId" = t.id
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            ORDER BY t."callDate"
        """)
        rows = cur.fetchall()
    conn.close()
    return rows


def wilson_ci(hits, n, z=1.96):
    if n == 0:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def score_rows(rows, prices, cutoff, tickers_filter=None):
    """Apply analyst_direct_scorer's exact methodology to DB rows.
    Returns list of dicts, one per row, with predicted/ground_truth/hit/
    always_bullish_hit/scoreable, restricted to rows whose ticker is in
    tickers_filter (default: ALL16) and call_date <= cutoff is NOT enforced
    here -- scoreability is determined purely by price data availability,
    matching the gate's own logic; `cutoff` is reported separately."""
    from analyst_direct_scorer import direction_from_score, FORWARD_DAYS, DEAD_BAND, BENCHMARK
    out = []
    for r in rows:
        ticker = r["ticker"]
        if tickers_filter is not None and ticker not in tickers_filter:
            continue
        score = {"recommendation": r["rec"], "thesisHealth": r["health"]}
        predicted = direction_from_score(score)
        call_date = r["call_date"]
        rec = {"ticker": ticker, "call_date": call_date, "predicted": predicted,
               "model_version": r["model_version"], "prompt_version": r["prompt_version"],
               "created_at": r["created_at"], "scoreable": False,
               "ground_truth": None, "hit": None, "always_bullish_hit": None}
        if predicted is None:
            out.append(rec)
            continue
        p0, _ = prices.price_on_or_after(ticker, call_date)
        b0, _ = prices.price_on_or_after(BENCHMARK, call_date)
        fwd_target = call_date + timedelta(days=FORWARD_DAYS)
        p1, _ = prices.price_on_or_after(ticker, fwd_target)
        b1, _ = prices.price_on_or_after(BENCHMARK, fwd_target)
        if not all([p0, b0, p1, b1]):
            out.append(rec)
            continue
        stock_ret = (p1 - p0) / p0
        bench_ret = (b1 - b0) / b0
        rel = stock_ret - bench_ret
        if rel > DEAD_BAND:
            gt = "bullish"
        elif rel < -DEAD_BAND:
            gt = "bearish"
        else:
            gt = "neutral"
        rec.update(scoreable=True, ground_truth=gt, hit=(predicted == gt),
                    always_bullish_hit=(gt == "bullish"))
        out.append(rec)
    return out


def series_stats(scored):
    """scored: list of score_rows() dicts, already scoreable-filtered."""
    n = len(scored)
    if n == 0:
        return None
    hits = sum(1 for r in scored if r["hit"])
    base_hits = sum(1 for r in scored if r["always_bullish_hit"])
    hit_rate = hits / n
    base_rate = base_hits / n
    lift = hit_rate - base_rate
    headroom = (hit_rate - base_rate) / (1 - base_rate) if base_rate < 1 else None
    ci_lo, ci_hi = wilson_ci(hits, n)
    gt_counts = Counter(r["ground_truth"] for r in scored)
    bearish = [r for r in scored if r["ground_truth"] == "bearish"]
    bearish_hits = sum(1 for r in bearish if r["hit"])
    bearish_rate = bearish_hits / len(bearish) if bearish else None
    bearish_ci = wilson_ci(bearish_hits, len(bearish)) if bearish else (None, None)
    return {
        "n": n, "hit_rate": hit_rate, "hit_rate_ci95": [ci_lo, ci_hi],
        "baseline_hit_rate": base_rate, "lift_pp": lift * 100,
        "headroom_captured": headroom,
        "ground_truth_mix": {"bullish": gt_counts.get("bullish", 0),
                              "bearish": gt_counts.get("bearish", 0),
                              "neutral": gt_counts.get("neutral", 0)},
        "distinct_tickers": len({r["ticker"] for r in scored}),
        "bearish_n": len(bearish), "bearish_hit_rate": bearish_rate,
        "bearish_hit_rate_ci95": list(bearish_ci),
    }


def step_2(driver_commit, branch, dirty, driver_tracked):
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH, FORWARD_DAYS
    rows = fetch_analysis_rows()
    prices = PriceCache(PRICE_CACHE_PATH)

    raw = json.loads(PRICE_CACHE_PATH.read_text())
    last_price_date = max(raw["SPY"].keys())
    cutoff = date.fromisoformat(last_price_date) - timedelta(days=FORWARD_DAYS)

    scored_all16 = score_rows(rows, prices, cutoff, tickers_filter=ALL16)

    by_year = defaultdict(list)
    for r in scored_all16:
        by_year[r["call_date"].year].append(r)
    year_counts = {y: {"n_rows": len(v), "n_scoreable": sum(1 for r in v if r["scoreable"]),
                        "distinct_tickers": sorted({r["ticker"] for r in v})}
                   for y, v in sorted(by_year.items())}

    year_ticker_counts = defaultdict(lambda: defaultdict(int))
    for r in scored_all16:
        year_ticker_counts[r["call_date"].year][r["ticker"]] += 1
    year_ticker_counts = {y: dict(sorted(d.items())) for y, d in sorted(year_ticker_counts.items())}

    all_rows_by_ticker = defaultdict(int)
    for r in rows:
        all_rows_by_ticker[r["ticker"]] += 1
    non_all16_tickers = {t: n for t, n in all_rows_by_ticker.items() if t not in ALL16}

    version_census = defaultdict(lambda: {"n": 0, "min_call": None, "max_call": None})
    for r in rows:
        key = (r["prompt_version"], r["model_version"])
        v = version_census[key]
        v["n"] += 1
        cd = r["call_date"]
        v["min_call"] = cd if v["min_call"] is None else min(v["min_call"], cd)
        v["max_call"] = cd if v["max_call"] is None else max(v["max_call"], cd)
    version_census_out = {f"{pv}|{mv}": {**v, "min_call": str(v["min_call"]), "max_call": str(v["max_call"])}
                           for (pv, mv), v in sorted(version_census.items(), key=lambda kv: str(kv[0]))}

    results = {
        "forward_days": FORWARD_DAYS,
        "price_cache_last_date": last_price_date,
        "scoreable_cutoff_call_date": str(cutoff),
        "year_counts_all16": year_counts,
        "year_x_ticker_counts_all16": year_ticker_counts,
        "non_all16_tickers_in_db": non_all16_tickers,
        "version_census": version_census_out,
        "thin_years_all16": [y for y, v in year_counts.items() if v["n_scoreable"] < 20],
    }
    chash = config_hash(driver_commit, {"step": "2"})
    write_cell("2", {}, chash, results)
    write_manifest("2", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def step_3_4(driver_commit, branch, dirty, driver_tracked):
    """Steps 3 (series decomposed) and 4 (confound controls) in one pass --
    they share the same scored corpus, only the grouping differs."""
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH
    rows = fetch_analysis_rows()
    prices = PriceCache(PRICE_CACHE_PATH)

    scored = score_rows(rows, prices, None, tickers_filter=ALL16)
    scoreable = [r for r in scored if r["scoreable"]]

    # 2a: primary series = unstamped (presumed v6) rows only
    primary = [r for r in scoreable if r["model_version"] is None]
    tail = [r for r in scoreable if r["model_version"] is not None]

    by_year_primary = defaultdict(list)
    for r in primary:
        by_year_primary[r["call_date"].year].append(r)
    primary_series = {y: series_stats(v) for y, v in sorted(by_year_primary.items())}

    tail_by_model = defaultdict(list)
    for r in tail:
        tail_by_model[r["model_version"]].append(r)
    tail_series = {m: series_stats(v) for m, v in tail_by_model.items()}
    tail_overall = series_stats(tail)

    # Step 4: fixed-ticker subset present in every primary year
    years_primary = sorted(by_year_primary.keys())
    ticker_sets = [set(r["ticker"] for r in v) for v in by_year_primary.values()]
    fixed_tickers = set.intersection(*ticker_sets) if ticker_sets else set()
    by_year_fixed = defaultdict(list)
    for r in primary:
        if r["ticker"] in fixed_tickers:
            by_year_fixed[r["call_date"].year].append(r)
    fixed_series = {y: series_stats(v) for y, v in sorted(by_year_fixed.items())}

    # Step 4: year x scope grid (established/speculative), primary series only
    grid = {}
    for y, v in sorted(by_year_primary.items()):
        est = [r for r in v if r["ticker"] in ESTABLISHED]
        spec = [r for r in v if r["ticker"] in SPECULATIVE]
        grid[y] = {"established": series_stats(est), "speculative": series_stats(spec)}

    results = {
        "years_primary": years_primary,
        "primary_series_by_year": primary_series,
        "model_contaminated_tail": {
            "n_rows_scoreable": len(tail),
            "by_model_version": tail_series,
            "overall": tail_overall,
        },
        "fixed_ticker_subset": sorted(fixed_tickers),
        "fixed_ticker_series_by_year": fixed_series,
        "year_x_scope_grid": grid,
    }
    chash = config_hash(driver_commit, {"step": "3_4"})
    write_cell("3_4", {}, chash, results)
    write_manifest("3_4", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def step_6(driver_commit, branch, dirty, driver_tracked):
    """Optional: hit rate by position age (call ordinal for that ticker),
    on the primary (unstamped) series."""
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH
    rows = fetch_analysis_rows()
    prices = PriceCache(PRICE_CACHE_PATH)
    scored = score_rows(rows, prices, None, tickers_filter=ALL16)
    scoreable = [r for r in scored if r["scoreable"] and r["model_version"] is None]

    by_ticker = defaultdict(list)
    for r in scoreable:
        by_ticker[r["ticker"]].append(r)
    for t in by_ticker:
        by_ticker[t].sort(key=lambda r: r["call_date"])

    by_age_bucket = defaultdict(list)
    for t, rs in by_ticker.items():
        for i, r in enumerate(rs):
            bucket = "first_call" if i == 0 else ("2nd-3rd" if i < 3 else "4th+")
            by_age_bucket[bucket].append(r)

    results = {bucket: series_stats(v) for bucket, v in by_age_bucket.items()}
    chash = config_hash(driver_commit, {"step": "6"})
    write_cell("6", {}, chash, results)
    write_manifest("6", base_manifest(RUN_ID, driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    commit, branch, dirty, driver_tracked, unexpected = git_info()
    if dirty:
        print("UNEXPECTED DIRTY TREE:")
        for ln in unexpected:
            print(" ", ln)
        # Not a hard stop for pure-report steps that don't write outside run_state,
        # since the driver itself is committed before any manifest per Step 0.
    print(f"git_commit={commit} branch={branch} dirty={dirty} driver_tracked={driver_tracked}")

    if step in ("1a", "all"):
        step_1a(commit, branch, dirty, driver_tracked)
    if step in ("1b", "all"):
        step_1b(commit, branch, dirty, driver_tracked)
    if step in ("1c", "all"):
        step_1c(commit, branch, dirty, driver_tracked)
    if step in ("2", "all"):
        step_2(commit, branch, dirty, driver_tracked)
    if step in ("3", "4", "34", "all"):
        step_3_4(commit, branch, dirty, driver_tracked)
    if step in ("6", "all"):
        step_6(commit, branch, dirty, driver_tracked)


if __name__ == "__main__":
    main()
