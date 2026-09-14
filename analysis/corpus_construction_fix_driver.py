#!/usr/bin/env python3
"""
corpus_construction_fix_driver.py -- corpus-construction (fix pass)
See prompts/corpus-construction-fix.md and
analysis/data/corpus_v2/PREREGISTRATION_FIX.json (A1/A2/A3/A4, dated BEFORE
this script touched any company). Re-tests availability for every company
the first pass already selected, under the new day-based rule (A1) and the
new S4-specific rule (A2). Vendor (EarningsCall.biz) metadata only -- no
transcript text requested. ZERO Anthropic API calls. ZERO Analysis DB writes.

Usage:
  python3 analysis/corpus_construction_fix_driver.py stepB
"""
import os, sys, json, datetime, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent
load_dotenv(repo_root / ".env")

RUN_ID = "corpus-construction"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
CORPUS_DIR = repo_root / "analysis" / "data" / "corpus_v2"
PROGRESS_PATH = STATE_DIR / "progress.json"
CELLS_PATH = STATE_DIR / "cells.jsonl"
FINDINGS_PATH = STATE_DIR / "findings.md"
SELECTION_PATH = CORPUS_DIR / "selection_working.json"
PREREG_FIX_PATH = CORPUS_DIR / "PREREGISTRATION_FIX.json"

ECB_API_KEY = os.environ.get("ECB_API_KEY")
BASE_URL = "https://v2.api.earningscall.biz"
HARD_CALL_CAP_THIS_SCRIPT = 100
MIN_SPACING_SECONDS = 3.5
EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

# Terminal-event dates for S4 candidates (A2c: >=2 calls in the 12 months
# before the terminal event). Publicly documented dates, coverage-mechanics
# input only -- not a return or outcome figure.
S4_TERMINAL_EVENTS = {
    "FRC": "2023-05-01",   # First Republic Bank -- FDIC receivership / JPMorgan acquisition
    "RMO": "2022-08-19",   # Romeo Power -- forced/distressed merger into Nikola completed
    "SUNW": "2023-07-14",  # Sunworks -- Chapter 11 filing
    "SIVB": "2023-03-10",  # SVB Financial / Silicon Valley Bank -- FDIC receivership
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
    if progress.get("calls_used_this_fix_script", 0) >= HARD_CALL_CAP_THIS_SCRIPT:
        raise RuntimeError(f"HARD_CALL_CAP_THIS_SCRIPT={HARD_CALL_CAP_THIS_SCRIPT} reached")
    if progress.get("last_call_ts"):
        elapsed = time.time() - progress["last_call_ts"]
        if elapsed < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - elapsed)
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent corpus-construction-fix"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress["calls_used_this_fix_script"] = progress.get("calls_used_this_fix_script", 0) + 1
    progress["last_call_ts"] = time.time()
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint, "params": params, "script": "fix"})
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


def get_events(progress, symtab, ticker):
    exchs = symtab.get(ticker)
    if not exchs:
        return {"in_symbol_list": False, "dates": []}
    exch = exchs[0]
    status, data = vendor_get(progress, "events", {"exchange": exch, "symbol": ticker})
    if status != 200 or not isinstance(data, dict):
        return {"in_symbol_list": True, "exchange": exch, "dates": [], "vendor_error": f"HTTP {status}"}
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
    return {"in_symbol_list": True, "exchange": exch, "dates": dates}


def max_gap_days(dates):
    if len(dates) < 2:
        return 0
    return max((b - a).days for a, b in zip(dates, dates[1:]))


def step_b():
    prereg_fix = load_json(PREREG_FIX_PATH)
    if prereg_fix is None:
        print("PREREGISTRATION_FIX.json missing -- run Step A first."); return
    selection = load_json(SELECTION_PATH)
    if selection is None:
        print("selection_working.json missing (first pass artifact) -- cannot proceed."); return
    progress = load_json(PROGRESS_PATH, {})
    progress.setdefault("calls_used_total", 0)
    progress["calls_used_this_fix_script"] = 0

    s4_original_pool = [c["ticker"] for c in selection["S4"]["detail"]] if "detail" in selection["S4"] else []
    all_tickers = sorted(set(
        selection["S1"]["selected"] + selection["S2"]["selected"] +
        selection["S3"]["selected"] + selection["S4"]["selected"] + selection["S5"]["selected"] +
        s4_original_pool
    ))
    # Also explicitly include the originally-dropped names named in the prompt,
    # in case any fell outside selection_working.json's recorded lists.
    for extra in ["INTC", "KO", "MCD", "TMO", "LIN", "POWI", "FRC", "RMO", "SUNW", "SIVB", "GOOGL"]:
        if extra not in all_tickers:
            all_tickers.append(extra)
    all_tickers = sorted(set(all_tickers))

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
            sym = parts[1].upper()
            symtab.setdefault(sym, []).append(exch)
    else:
        print(f"symbols-v2.txt failed: {status}"); return

    results = {}
    s4_set = set(selection["S4"]["selected"]) | set(s4_original_pool) | set(S4_TERMINAL_EVENTS)
    for t in all_tickers:
        try:
            info = get_events(progress, symtab, t)
        except RuntimeError as e:
            print(f"STOPPED early: {e}"); break
        dates = info.get("dates", [])
        gap = max_gap_days(dates)
        is_s4 = t in s4_set

        if not info.get("in_symbol_list"):
            entry = {"in_symbol_list": False, "n_calls": 0, "first": None, "last": None,
                      "max_gap_days": None, "is_s4": is_s4, "meets_new_rule": False}
        elif is_s4:
            n = len(dates)
            terminal = S4_TERMINAL_EVENTS.get(t)
            calls_before_terminal_12mo = None
            internal_gap_ok = True
            if n >= 2:
                internal_gap_ok = gap <= 240
            if terminal:
                terminal_d = datetime.date.fromisoformat(terminal)
                window_start = terminal_d - datetime.timedelta(days=365)
                calls_before_terminal_12mo = sum(1 for d in dates if window_start <= d <= terminal_d)
            else:
                # No documented terminal event for this candidate (e.g. it isn't
                # actually a distress name) -- can't evaluate A2c, so meets_new_rule
                # is judged on (a) and (d) only, terminal-event test left null.
                calls_before_terminal_12mo = None
            meets = (n >= 4) and internal_gap_ok and (calls_before_terminal_12mo is None or calls_before_terminal_12mo >= 2)
            entry = {"in_symbol_list": True, "exchange": info.get("exchange"), "n_calls": n,
                      "first": dates[0].isoformat() if dates else None,
                      "last": dates[-1].isoformat() if dates else None,
                      "max_internal_gap_days": gap, "terminal_event_date": terminal,
                      "calls_in_12mo_before_terminal": calls_before_terminal_12mo,
                      "is_s4": True, "rule": "A2", "meets_new_rule": meets}
        else:
            n = len(dates)
            meets = (n >= 12) and (gap <= 240)
            entry = {"in_symbol_list": True, "exchange": info.get("exchange"), "n_calls": n,
                      "first": dates[0].isoformat() if dates else None,
                      "last": dates[-1].isoformat() if dates else None,
                      "max_gap_days": gap, "is_s4": False, "rule": "A1", "meets_new_rule": meets}
        results[t] = entry
        append_cell({"cell_key": f"stepB_{t}", "avail_fix": entry})
        print(f"  {t}: {entry}")

    save_json(CORPUS_DIR / "availability_fix_working.json", results)
    save_json(PROGRESS_PATH, progress)

    non_s4_gaps = [r["max_gap_days"] for t, r in results.items() if not r["is_s4"] and r.get("max_gap_days") is not None]
    near_line = [g for g in non_s4_gaps if abs(g - 240) <= 20]
    append_finding(
        f"## Step B availability re-test under PREREGISTRATION_FIX.json ({now_iso()})\n\n"
        f"Checked {len(results)} tickers, {progress['calls_used_this_fix_script']} vendor calls this script "
        f"(cumulative total this run: {progress['calls_used_total']}).\n\n"
        f"Non-S4 max-gap distribution (days): n={len(non_s4_gaps)}, "
        f"min={min(non_s4_gaps) if non_s4_gaps else None}, max={max(non_s4_gaps) if non_s4_gaps else None}, "
        f"within 20 days of the 240-day line: {len(near_line)} of {len(non_s4_gaps)} "
        f"({near_line}).\n\n"
        f"Passing under new rule: {sorted(t for t,r in results.items() if r['meets_new_rule'])}\n\n"
        f"Failing under new rule: {sorted(t for t,r in results.items() if not r['meets_new_rule'])}"
    )
    print(f"\nVendor calls this script: {progress['calls_used_this_fix_script']}; cumulative total: {progress['calls_used_total']}")


if __name__ == "__main__":
    cmds = {"stepB": step_b}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]]()
