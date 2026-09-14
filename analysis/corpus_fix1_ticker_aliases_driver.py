#!/usr/bin/env python3
"""
corpus_fix1_ticker_aliases_driver.py -- corpus-construction, corpus-fix-1
See prompts/corpus-fix-1-ticker-aliases.md and
analysis/data/corpus_v2/PREREGISTRATION_FIX.json -> A5_ticker_alias_resolution
(addendum written BEFORE any query in this script ran).

Resolves whether the zero/near-zero-event companies in CORPUS_MANIFEST_V2.json
(GOOGL, SIVB, and -- per the A5 addendum's widened scope -- HON, UPS) are
IDENTITY failures (wrong ticker symbol at the vendor) rather than genuine
coverage gaps. Reuses corpus_construction_fix_driver.py's exact vendor
mechanism (symbols-v2.txt for the symbol table, /events per candidate
ticker+exchange). Vendor metadata only -- no transcript text. ZERO Anthropic
API calls. ZERO Analysis DB writes. Does not modify price_cache.json.

Usage:
  python3 analysis/corpus_fix1_ticker_aliases_driver.py run
"""
import os, sys, json, datetime, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir
load_dotenv(repo_root / ".env")

RUN_ID = "corpus-construction"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
CORPUS_DIR = repo_root / "analysis" / "data" / "corpus_v2"
PROGRESS_PATH = STATE_DIR / "progress.json"
CELLS_PATH = STATE_DIR / "cells.jsonl"
FINDINGS_PATH = STATE_DIR / "findings.md"

ECB_API_KEY = os.environ.get("ECB_API_KEY")
BASE_URL = "https://v2.api.earningscall.biz"
HARD_CALL_CAP_THIS_SCRIPT = 40
MIN_SPACING_SECONDS = 3.5
EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

# Candidate aliases, per PREREGISTRATION_FIX.json A5's ordering:
#   (a) share-class variants, (b) post-bankruptcy symbols, (c) name search.
# GOOGL/SIVB are the two the prompt names directly; HON/UPS are added per the
# addendum's widened scope (both show 0/null events + in_vendor_symbol_list
# False in CORPUS_MANIFEST_V2.json, carried from the first pass, never
# re-queried in the fix pass).
CANDIDATES = {
    "GOOGL": ["GOOG"],                    # (a) share-class variant
    "SIVB": ["SIVBQ", "SIVB.Q"],           # (b) post-bankruptcy suffix forms
    "HON": ["HON"],                        # no known alias; re-query original only
    "UPS": ["UPS"],                        # no known alias; re-query original only
}
NAME_SEARCH_TERMS = {
    "GOOGL": ["alphabet", "google"],
    "SIVB": ["svb", "silicon valley bank", "sivb"],
    "HON": ["honeywell"],
    "UPS": ["united parcel"],
}


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
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def append_cell(cell):
    with open(CELLS_PATH, "a") as f:
        f.write(json.dumps(cell, default=str) + "\n")


def vendor_get(progress, endpoint, params):
    if progress.get("calls_used_this_fix1_script", 0) >= HARD_CALL_CAP_THIS_SCRIPT:
        raise RuntimeError(f"HARD_CALL_CAP_THIS_SCRIPT={HARD_CALL_CAP_THIS_SCRIPT} reached")
    if progress.get("last_call_ts_fix1"):
        elapsed = time.time() - progress["last_call_ts_fix1"]
        if elapsed < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - elapsed)
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent corpus-fix-1-ticker-aliases"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress["calls_used_this_fix1_script"] = progress.get("calls_used_this_fix1_script", 0) + 1
    progress["last_call_ts_fix1"] = time.time()
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint, "params": params, "script": "fix1_ticker_aliases"})
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


def build_symtab(progress):
    status, text = vendor_get(progress, "symbols-v2.txt", {})
    symtab = {}
    name_index = []  # list of (symbol, exchange, name-ish) -- symbols-v2.txt has no company name column
    if status == 200 and isinstance(text, str):
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                exch = EXCHANGES_IN_ORDER[int(parts[0])]
            except (ValueError, IndexError):
                continue
            sym = parts[1].upper()
            symtab.setdefault(sym, []).append(exch)
    else:
        raise RuntimeError(f"symbols-v2.txt failed: {status}")
    return symtab


def get_events(progress, symtab, ticker):
    exchs = symtab.get(ticker)
    if not exchs:
        return {"in_symbol_list": False, "dates": [], "company_name": None}
    exch = exchs[0]
    status, data = vendor_get(progress, "events", {"exchange": exch, "symbol": ticker})
    if status != 200 or not isinstance(data, dict):
        return {"in_symbol_list": True, "exchange": exch, "dates": [], "vendor_error": f"HTTP {status}", "company_name": None}
    dates = []
    for e in data.get("events", []):
        cd = e.get("conference_date")
        if not cd:
            continue
        try:
            d = datetime.date.fromisoformat(str(cd)[:10])
        except ValueError:
            continue
        if datetime.date(2020, 1, 1) <= d <= datetime.date(2025, 12, 31):
            dates.append(d)
    dates.sort()
    company_name = data.get("company_name") or (data.get("events", [{}])[0].get("company_name") if data.get("events") else None)
    return {"in_symbol_list": True, "exchange": exch, "dates": dates, "company_name": company_name}


def max_gap_days(dates):
    if len(dates) < 2:
        return 0
    return max((b - a).days for a, b in zip(dates, dates[1:]))


def run():
    progress = load_json(PROGRESS_PATH, {})
    progress.setdefault("calls_used_total", 0)
    progress["calls_used_this_fix1_script"] = 0

    print("Building symbol table (symbols-v2.txt)...")
    symtab = build_symtab(progress)

    results = {}
    for orig, aliases in CANDIDATES.items():
        results[orig] = {}
        candidates_to_try = [orig] + [a for a in aliases if a != orig]
        for cand in candidates_to_try:
            try:
                info = get_events(progress, symtab, cand)
            except RuntimeError as e:
                print(f"STOPPED early: {e}"); save_json(PROGRESS_PATH, progress); return
            dates = info.get("dates", [])
            entry = {
                "candidate_symbol": cand,
                "in_symbol_list": info.get("in_symbol_list"),
                "exchange": info.get("exchange"),
                "n_calls_2020_2025": len(dates),
                "first_call": dates[0].isoformat() if dates else None,
                "last_call": dates[-1].isoformat() if dates else None,
                "max_gap_days": max_gap_days(dates),
                "company_name": info.get("company_name"),
            }
            results[orig][cand] = entry
            append_cell({"cell_key": f"fix1_alias_{orig}_{cand}", "result": entry})
            print(f"  {orig} -> {cand}: in_symbol_list={entry['in_symbol_list']} n_calls={entry['n_calls_2020_2025']} range={entry['first_call']}..{entry['last_call']}")

    save_json(CORPUS_DIR / "alias_probe_working.json", results)
    save_json(PROGRESS_PATH, progress)

    append_finding(
        f"## corpus-fix-1-ticker-aliases vendor probe ({now_iso()})\n\n"
        f"Candidates tried: {json.dumps({k: list(v.keys()) for k,v in results.items()})}\n\n"
        f"Raw results: {json.dumps(results, indent=2, default=str)}\n\n"
        f"Vendor calls this script: {progress['calls_used_this_fix1_script']} "
        f"(cumulative total this run/billing period: {progress['calls_used_total']})."
    )
    print(f"\nVendor calls this script: {progress['calls_used_this_fix1_script']}; cumulative total: {progress['calls_used_total']}")


if __name__ == "__main__":
    cmds = {"run": run}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]]()
