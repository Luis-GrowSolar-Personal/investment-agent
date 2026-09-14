#!/usr/bin/env python3
"""
corpus_fix5_driver.py -- corpus-construction (fix pass 5)
See prompts/corpus-fix-5-expand-and-prices.md.

Job 1: price history for NOVA, SUNW, FRC (all currently empty {} in the
corpus price cache) and a WOLF sanity check. ZERO Anthropic API calls.
Price data from a second provider (yfinance/Yahoo), NOT the earnings-call
vendor. Writes only to analysis/data/corpus_v2/corpus_v2_price_cache.json
-- never touches analysis/data/price_cache.json.

Job 1 also uses the EarningsCall.biz vendor (metadata only, no transcript
text) to fetch each S4 company's actual call dates, needed to categorize
each call's 182-day forward window as real-price-graded or
terminal-value-graded.

Usage:
  python3 analysis/corpus_fix5_driver.py job1
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
V2_PRICE_CACHE_PATH = CORPUS_DIR / "corpus_v2_price_cache.json"

ECB_API_KEY = os.environ.get("ECB_API_KEY")
BASE_URL = "https://v2.api.earningscall.biz"
MIN_SPACING_SECONDS = 3.5  # well under the 20 calls/minute (3s) limit
EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

S4_TERMINAL_EVENTS_VERIFIED = {
    # SEC/FDIC-verified dates from wrap-ups/corpus-fix-4-threshold-and-terminal-value-out.md.
    # NOTE: analysis/corpus_construction_fix_driver.py's S4_TERMINAL_EVENTS carries
    # SUNW = "2023-07-14", which CONFLICTS with the fix-4 verified date below
    # (2024-02-05, matching the SEC 8-K). Flagged in the wrap-up; not edited here.
    "FRC": "2023-05-01",
    "SUNW": "2024-02-05",
    "NOVA": "2025-06-09",   # NYSE delisting per fix-4 (filed 2025-06-08)
    "WOLF": None,           # not a wipeout -- still trading, restructured under Ch.11
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
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def append_cell(cell):
    CELLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CELLS_PATH, "a") as f:
        f.write(json.dumps(cell, default=str) + "\n")


def vendor_get(progress, endpoint, params):
    if progress.get("last_call_ts"):
        elapsed = time.time() - progress["last_call_ts"]
        if elapsed < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - elapsed)
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent corpus-fix-5"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress["calls_used_fix5"] = progress.get("calls_used_fix5", 0) + 1
    progress["last_call_ts"] = time.time()
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint, "params": params, "script": "fix5"})
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
            sym = parts[1].upper()
            symtab.setdefault(sym, []).append(exch)
    else:
        raise RuntimeError(f"symbols-v2.txt failed: {status}")
    return symtab


def get_call_dates(progress, symtab, ticker):
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
            dates.append(datetime.date.fromisoformat(cd[:10]))
        except ValueError:
            continue
    dates.sort()
    return {"in_symbol_list": True, "exchange": exch, "dates": dates}


def job1():
    """Price history for NOVA, SUNW, FRC + WOLF sanity check. Requires yfinance."""
    import yfinance as yf

    progress = load_json(PROGRESS_PATH, default={})
    progress.setdefault("run_id", RUN_ID)
    save_json(PROGRESS_PATH, progress)

    attempts = {
        "NOVA": ["NOVA", "NOVAQ", "NOVAQQ", "SNOVQ"],
        "SUNW": ["SUNW", "SUNWQ"],
        "FRC": ["FRC", "FRCB"],
        "WOLF": ["WOLF"],
    }
    provider_results = {}
    price_cache = load_json(V2_PRICE_CACHE_PATH, default={})

    for corpus_ticker, cands in attempts.items():
        attempt_log = []
        recovered = None
        for cand in cands:
            try:
                d = yf.download(cand, start="2020-01-01", end="2026-09-14",
                                 progress=False, auto_adjust=False)
            except Exception as e:
                attempt_log.append({"symbol": cand, "provider": "yfinance/Yahoo", "rows": 0, "error": str(e)})
                continue
            n = len(d)
            attempt_log.append({
                "symbol": cand, "provider": "yfinance/Yahoo", "rows": n,
                "first_date": d.index.min().date().isoformat() if n else None,
                "last_date": d.index.max().date().isoformat() if n else None,
            })
            if n > 0 and recovered is None:
                recovered = (cand, d)
            time.sleep(1)
            append_cell({"cell_key": f"job1_price_attempt_{corpus_ticker}_{cand}", "result": attempt_log[-1]})

        if recovered:
            symbol_used, d = recovered
            series = {}
            for idx, row in d.iterrows():
                series[idx.date().isoformat()] = {
                    "open": None if row["Open"] != row["Open"] else float(row["Open"]),
                    "close": None if row["Close"] != row["Close"] else float(row["Close"]),
                    "high": None if row["High"] != row["High"] else float(row["High"]),
                    "low": None if row["Low"] != row["Low"] else float(row["Low"]),
                    "volume": None if row["Volume"] != row["Volume"] else int(row["Volume"]),
                }
            price_cache[corpus_ticker] = {
                "symbol_used": symbol_used,
                "provider": "yfinance/Yahoo",
                "note": ("symbol differs from corpus ticker -- see provenance"
                         if symbol_used != corpus_ticker else None),
                "first_date": min(series.keys()),
                "last_date": max(series.keys()),
                "daily": series,
            }
            provider_results[corpus_ticker] = {"recovered": True, "symbol_used": symbol_used,
                                                 "n_days": len(series),
                                                 "last_trading_day_in_series": max(series.keys()),
                                                 "attempts": attempt_log}
        else:
            provider_results[corpus_ticker] = {"recovered": False, "attempts": attempt_log}

    save_json(V2_PRICE_CACHE_PATH, price_cache)

    # Second-provider attempt for NOVA only (the one that failed on Yahoo).
    second_provider_note = (
        "Stooq (https://stooq.com) attempted for NOVA via direct CSV endpoint "
        "(nova.us, novaq.us, nova.pk); all three returned a JavaScript proof-of-work "
        "challenge page instead of data (no headless browser available in this "
        "environment) -- not usable. No other free daily-history provider without an "
        "API key was attempted. NOVA's pre-delisting history is also gone from Yahoo "
        "(NOVA returns 0 rows for the full 2020-2025 window, not just post-delisting), "
        "so this is not solely a post-delisting gap."
    )

    # Call-date categorization for the composition rule, S4 companies with
    # documented terminal events.
    symtab = get_symtab(progress)
    categorization = {}
    for t in ["NOVA", "SUNW", "FRC", "WOLF"]:
        info = get_call_dates(progress, symtab, t)
        dates = info.get("dates", [])
        terminal = S4_TERMINAL_EVENTS_VERIFIED.get(t)
        last_trading_day = None
        if provider_results.get(t, {}).get("recovered"):
            last_trading_day = provider_results[t]["last_trading_day_in_series"]
        rows = []
        for d in dates:
            window_close = (d + datetime.timedelta(days=182))
            if terminal is None:
                category = "real_price (no terminal event)"
            elif window_close.isoformat() <= (last_trading_day or "0000-00-00"):
                category = "real_price"
            elif last_trading_day is None:
                category = "ungradable_per_call (no price series)"
            else:
                category = "terminal_value_zero (A6)"
            rows.append({"call_date": d.isoformat(), "window_close": window_close.isoformat(),
                          "category": category})
        categorization[t] = {
            "terminal_event_date": terminal,
            "last_trading_day_in_recovered_series": last_trading_day,
            "n_calls": len(dates),
            "calls": rows,
            "counts_by_category": {
                cat: sum(1 for r in rows if r["category"] == cat)
                for cat in set(r["category"] for r in rows)
            } if rows else {},
        }
        append_cell({"cell_key": f"job1_categorization_{t}", "result": categorization[t]})

    out = {
        "generated_at": now_iso(),
        "job": "job1_prices_and_composition_check",
        "provider_attempts": provider_results,
        "second_provider_note": second_provider_note,
        "call_window_categorization": categorization,
        "vendor_calls_used_this_script": progress.get("calls_used_fix5", 0),
    }
    save_json(CORPUS_DIR / "JOB1_PRICE_RECOVERY_RESULT.json", out)
    append_finding(f"## Job 1 -- price recovery + composition check ({now_iso()})\n\n"
                    + json.dumps({t: provider_results[t].get("recovered") for t in provider_results}, indent=2))
    save_json(PROGRESS_PATH, progress)
    print(json.dumps({t: {"recovered": provider_results[t].get("recovered"),
                            "symbol_used": provider_results[t].get("symbol_used")}
                        for t in provider_results}, indent=2))
    print(f"Vendor calls used this script: {progress.get('calls_used_fix5', 0)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "job1":
        job1()
    else:
        print(__doc__)
        sys.exit(1)
