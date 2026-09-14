#!/usr/bin/env python3
"""
corpus_fix8_driver.py -- corpus-construction (fix pass 8)
See prompts/corpus-fix-8-expand-to-150.md.

Expands the corpus toward ~150 companies. ZERO Anthropic API calls. Vendor
(EarningsCall.biz) metadata calls only (call dates/counts, no transcript
text) for Step C availability; yfinance/Yahoo price fetches for Step D
coverage, written only to corpus_v2_price_cache.json.

Usage:
  python3 analysis/corpus_fix8_driver.py stepC   # call availability (vendor)
  python3 analysis/corpus_fix8_driver.py stepD   # price coverage + freeze
  python3 analysis/corpus_fix8_driver.py relaxed # SPAC-era candidate call counts
"""
import os, sys, json, datetime, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent
sys.path.insert(0, str(script_dir))
load_dotenv(repo_root / ".env")

import corpus_fix8_candidates as cand
import corpus_fix6_driver as fix6  # reuse price-fetch/categorize/resolve_identity

RUN_ID = "corpus-construction"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
CORPUS_DIR = repo_root / "analysis" / "data" / "corpus_v2"
PROGRESS_PATH = STATE_DIR / "progress.json"
CELLS_PATH = STATE_DIR / "cells.jsonl"
FINDINGS_PATH = STATE_DIR / "findings.md"
MANIFEST_V4_PATH = CORPUS_DIR / "CORPUS_MANIFEST_V4.json"
MANIFEST_V5_PATH = CORPUS_DIR / "CORPUS_MANIFEST_V5.json"
ALIASES_PATH = CORPUS_DIR / "TICKER_ALIASES.json"
AVAILABILITY_OUT = CORPUS_DIR / "FIX8_AVAILABILITY_SWEEP.json"
COVERAGE_OUT = CORPUS_DIR / "FIX8_COVERAGE_SWEEP.json"
RELAXED_OUT = CORPUS_DIR / "FIX8_SPAC_ERA_RELAXED_CANDIDATES.json"
V2_PRICE_CACHE_PATH = CORPUS_DIR / "corpus_v2_price_cache.json"
ROOT_PRICE_CACHE_PATH = repo_root / "analysis" / "data" / "price_cache.json"

ECB_API_KEY = os.environ.get("ECB_API_KEY")
BASE_URL = "https://v2.api.earningscall.biz"
MIN_SPACING_SECONDS = 3.5
HARD_CALL_CAP_THIS_SCRIPT = 400  # raised: the window-filter bugfix required a second full sweep,
                                    # and calls_used_fix8 persists cumulatively in progress.json
                                    # across invocations of this script (resume-protocol state).
                                    # No monthly vendor quota per the prompt; this is a safety
                                    # ceiling against runaway loops, not a budget.
EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

S4_TERMINAL_EVENTS = {"FRC": "2023-05-01", "SUNW": "2024-02-05", "NOVA": "2025-06-09", "WOLF": None}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    with open(p) as f:
        return json.load(f)


def save_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def append_finding(text):
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def append_cell(cell):
    CELLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CELLS_PATH, "a") as f:
        f.write(json.dumps(cell, default=str) + "\n")


def vendor_get(progress, endpoint, params):
    used = progress.get("calls_used_fix8", 0)
    if used >= HARD_CALL_CAP_THIS_SCRIPT:
        raise RuntimeError(f"HARD_CALL_CAP_THIS_SCRIPT={HARD_CALL_CAP_THIS_SCRIPT} reached")
    if progress.get("last_call_ts"):
        elapsed = time.time() - progress["last_call_ts"]
        if elapsed < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - elapsed)
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent corpus-fix-8"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress["calls_used_fix8"] = used + 1
    progress["last_call_ts"] = time.time()
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint, "params": params, "script": "fix8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read(); status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read(); status = e.code
    text = body.decode("utf-8", errors="replace")
    progress["call_log"][-1]["status"] = status
    save_json(PROGRESS_PATH, progress)
    if status == 200:
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text
    return status, text


def get_symtab(progress):
    status, text = vendor_get(progress, "symbols-v2.txt", {})
    symtab = {}
    if status == 200 and isinstance(text, str):
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                exch = EXCHANGES_IN_ORDER[int(parts[0])]
            except (ValueError, IndexError):
                continue
            symtab.setdefault(parts[1].upper(), []).append(exch)
    else:
        raise RuntimeError(f"symbols-v2.txt failed: {status}")
    return symtab


WINDOW_START = datetime.date(2020, 1, 1)
WINDOW_END = datetime.date(2025, 12, 31)


def get_call_dates(progress, symtab, ticker, aliases_by_original):
    """Returns dates restricted to the corpus's registered 2020-2025 window.
    (Bug found mid-run: the vendor's /events endpoint returns a company's
    FULL available history, not just 2020-2025 -- e.g. UNH's raw events span
    2019-01-15 to 2026-07-16. Every other corpus driver's n_calls_2020_2025
    figure implicitly assumed the window; this one now filters explicitly.)"""
    tried = [ticker]
    if ticker in aliases_by_original:
        tried.append(aliases_by_original[ticker])
    for t in tried:
        exchs = symtab.get(t)
        if not exchs:
            continue
        exch = exchs[0]
        status, data = vendor_get(progress, "events", {"exchange": exch, "symbol": t})
        if status == 200 and isinstance(data, dict):
            all_dates = []
            for e in data.get("events", []):
                cd = e.get("conference_date")
                if not cd:
                    continue
                try:
                    all_dates.append(datetime.date.fromisoformat(cd[:10]))
                except ValueError:
                    continue
            all_dates.sort()
            dates = [d for d in all_dates if WINDOW_START <= d <= WINDOW_END]
            return {"in_symbol_list": True, "symbol_used": t, "exchange": exch, "dates": dates,
                     "raw_first": all_dates[0].isoformat() if all_dates else None,
                     "raw_last": all_dates[-1].isoformat() if all_dates else None,
                     "raw_n": len(all_dates)}
    return {"in_symbol_list": False, "symbol_used": None, "dates": [], "raw_first": None, "raw_last": None, "raw_n": 0}


def max_gap_days(dates):
    if len(dates) < 2:
        return 0
    return max((b - a).days for a, b in zip(dates, dates[1:]))


def all_candidates():
    """Returns list of (ticker, stratum, sector_or_domain)."""
    out = []
    for t in cand.S1_CANDIDATES:
        out.append((t, "S1", None))
    for sector, tickers in cand.S3_CANDIDATES.items():
        for t in tickers:
            out.append((t, "S3", sector))
    for t in cand.S2_CANDIDATES:
        out.append((t, "S2", "in_domain_primary"))
    for t in cand.S2_RESERVES:
        out.append((t, "S2_reserve", "in_domain_reserve"))
    return out


def step_c():
    progress = load_json(PROGRESS_PATH, default={})
    progress.setdefault("run_id", RUN_ID)
    save_json(PROGRESS_PATH, progress)

    manifest = load_json(MANIFEST_V4_PATH)
    existing = set()
    for s, d in manifest["strata"].items():
        for c in d["frozen"]:
            existing.add(c["ticker"])

    aliases_doc = load_json(ALIASES_PATH, default={"entries": []})
    aliases_by_original = {e["original_symbol"]: e["working_symbol"] for e in aliases_doc.get("entries", [])}

    symtab = get_symtab(progress)

    candidates = all_candidates()
    dup = [t for t, s, sec in candidates if t in existing]
    if dup:
        append_finding(f"## Step C duplicate check ({now_iso()})\n\nCandidates already in corpus, dropped before any vendor call: {dup}")

    results = {}
    for t, stratum, sector in candidates:
        if t in existing:
            continue
        info = get_call_dates(progress, symtab, t, aliases_by_original)
        dates = info["dates"]
        gap = max_gap_days(dates)
        n = len(dates)
        meets_a1 = (n >= 12) and (gap <= 240)
        entry = {
            "ticker": t, "stratum": stratum, "sector_or_domain": sector,
            "in_symbol_list": info["in_symbol_list"], "symbol_used": info["symbol_used"],
            "n_calls": n, "first": dates[0].isoformat() if dates else None,
            "last": dates[-1].isoformat() if dates else None,
            "max_gap_days": gap, "rule": "A1", "meets_new_rule": meets_a1,
            "raw_first_all_history": info.get("raw_first"), "raw_last_all_history": info.get("raw_last"),
            "raw_n_all_history": info.get("raw_n"),
        }
        results[t] = entry
        append_cell({"cell_key": f"fix8_stepC_{t}", "result": entry})
        print(f"{t} ({stratum}/{sector}): n={n} gap={gap} meets_A1={meets_a1} vendor_calls_used={progress.get('calls_used_fix8')}")

    save_json(AVAILABILITY_OUT, {
        "generated_at": now_iso(),
        "candidates_checked": len(results),
        "duplicates_dropped_before_vendor_call": dup,
        "vendor_calls_used": progress.get("calls_used_fix8", 0),
        "results": results,
    })
    passing = [t for t, r in results.items() if r["meets_new_rule"]]
    failing = [t for t, r in results.items() if not r["meets_new_rule"]]
    append_finding(f"## Step C availability sweep ({now_iso()})\n\n"
                    f"{len(results)} candidates checked, {progress.get('calls_used_fix8')} vendor calls this script.\n\n"
                    f"Pass A1: {sorted(passing)}\n\nFail A1: {sorted(failing)}")
    print(f"\nPass: {len(passing)} / {len(results)}. Vendor calls used: {progress.get('calls_used_fix8')}")


def step_d():
    """Price coverage (A9) on every A1-passing candidate, then freeze V5."""
    avail = load_json(AVAILABILITY_OUT)
    results = avail["results"]
    passing = {t: r for t, r in results.items() if r["meets_new_rule"]}

    aliases_doc = load_json(ALIASES_PATH, default={"entries": []})
    aliases_by_original = {e["original_symbol"]: e["working_symbol"] for e in aliases_doc.get("entries", [])}
    root_cache = load_json(ROOT_PRICE_CACHE_PATH, default={})
    v2_cache = load_json(V2_PRICE_CACHE_PATH, default={})

    # SPY first, per A9/prior runs.
    spy = load_json(CORPUS_DIR / "COVERAGE_GATE_SWEEP_V2_A9.json")["spy"]
    spy_first, spy_last = spy["first_date"], spy["last_date"]
    max_needed_close = max(
        (datetime.date.fromisoformat(r["last"]) + datetime.timedelta(days=182)).isoformat()
        for r in passing.values() if r["last"]
    ) if passing else spy_last
    spy_finding = None
    if spy_last < max_needed_close:
        spy_finding = f"SPY series covers through {spy_last}, corpus needs through {max_needed_close} -- same frozen-cache staleness noted in fix-6, not new."

    coverage = {}
    for t, r in passing.items():
        symbol_used, source, rows, first, last, attempts = fix6.resolve_identity(
            r["symbol_used"] or t, aliases_by_original, v2_cache, root_cache)
        if symbol_used and rows and symbol_used not in v2_cache and source != "price_cache.json":
            v2_cache[symbol_used] = {"symbol_used": symbol_used, "provider": source,
                                       "first_date": first, "last_date": last,
                                       "daily": {k: {"close": vv} for k, vv in rows.items()}}
        call_dates = [datetime.date.fromisoformat(r["first"])] if r["n_calls"] == 1 else \
            fix6.approx_call_dates(r["first"], r["last"], r["n_calls"])
        cats = fix6.categorize_calls(t, call_dates, first, last, spy_first, spy_last, S4_TERMINAL_EVENTS.get(t))
        counts = {}
        for row in cats:
            counts[row["category"]] = counts.get(row["category"], 0) + 1
        gradable = counts.get("gradable_real_price", 0) + counts.get("gradable_terminal_rule", 0)
        floor = 4 if r["stratum"] == "S4" else 12
        verdict = "pass" if gradable >= floor else "fail"
        coverage[t] = {
            "stratum": r["stratum"], "sector_or_domain": r["sector_or_domain"],
            "symbol_used": symbol_used, "identity_source": source,
            "series_first_date": first, "series_last_date": last,
            "n_calls": r["n_calls"], "gradable_total": gradable, "floor_applied": floor,
            "counts_by_category": counts, "verdict": verdict,
            "cause_of_gap": None if verdict == "pass" else "insufficient real-price coverage",
        }
        append_cell({"cell_key": f"fix8_stepD_{t}", "result": coverage[t]})
        print(f"{t}: gradable={gradable}/{r['n_calls']} floor={floor} verdict={verdict}")

    save_json(V2_PRICE_CACHE_PATH, v2_cache)
    save_json(COVERAGE_OUT, {"generated_at": now_iso(), "spy": {**spy, "needed_through": max_needed_close, "finding": spy_finding},
                              "per_candidate": coverage})

    gate_pass = {t: c for t, c in coverage.items() if c["verdict"] == "pass"}
    gate_fail = {t: c for t, c in coverage.items() if c["verdict"] == "fail"}
    append_finding(f"## Step D price-coverage sweep ({now_iso()})\n\n"
                    f"{len(coverage)} A1-passing candidates checked.\n\nPass A9: {sorted(gate_pass)}\n\nFail A9: {sorted(gate_fail)}")

    # --- Build CORPUS_MANIFEST_V5.json ---
    manifest_v4 = load_json(MANIFEST_V4_PATH)
    v5 = json.loads(json.dumps(manifest_v4))  # deep copy
    added_by_stratum = {"S1": [], "S2": [], "S3": [], "S4": [], "S5": []}
    for t, c in gate_pass.items():
        target_stratum = "S2" if c["stratum"] == "S2_reserve" else c["stratum"]
        entry = {
            "ticker": t, "stratum": target_stratum, "sector_or_domain": c["sector_or_domain"],
            "in_vendor_symbol_list": True, "n_calls_2020_2025": c["n_calls"],
            "gradable_calls_under_A9": c["gradable_total"], "floor_applied": c["floor_applied"],
            "rule_applied": "A1" if target_stratum != "S4" else "A2",
            "meets_new_rule": True, "price_coverage_verdict_A9": "pass",
            "added_this_pass": "corpus-fix-8",
        }
        v5["strata"][target_stratum]["frozen"].append(entry)
        added_by_stratum[target_stratum].append(t)

    v5["corpus_fix_8_expansion"] = {
        "applied_at": now_iso(),
        "added_by_stratum": added_by_stratum,
        "candidates_checked": len(results),
        "dropped_a1": sorted(t for t, r in results.items() if not r["meets_new_rule"]),
        "dropped_a9": sorted(gate_fail.keys()),
        "vendor_calls_used": avail["vendor_calls_used"],
    }
    save_json(MANIFEST_V5_PATH, v5)

    total = sum(len(d["frozen"]) for s, d in v5["strata"].items())
    print(f"\nV5 total companies: {total}")
    print(f"Added by stratum: {added_by_stratum}")
    return v5


def relaxed_candidates():
    progress = load_json(PROGRESS_PATH, default={})
    save_json(PROGRESS_PATH, progress)
    symtab = get_symtab(progress)
    out = []
    for c in cand.SPAC_ERA_RELAXED_CANDIDATES:
        t = c["ticker"]
        info = get_call_dates(progress, symtab, t, {})
        dates = info["dates"]
        out.append({**c, "n_calls_found": len(dates), "first_call": dates[0].isoformat() if dates else None,
                     "last_call": dates[-1].isoformat() if dates else None, "in_symbol_list": info["in_symbol_list"]})
        print(t, len(dates), dates[0] if dates else None, dates[-1] if dates else None)
    save_json(RELAXED_OUT, {"generated_at": now_iso(), "candidates": out, "note": "Listed per A10 for Luis's decision -- NOT added to any manifest."})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "stepC":
        step_c()
    elif cmd == "stepD":
        step_d()
    elif cmd == "relaxed":
        relaxed_candidates()
    else:
        print(__doc__)
        sys.exit(1)
