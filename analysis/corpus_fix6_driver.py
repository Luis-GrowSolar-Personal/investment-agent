#!/usr/bin/env python3
"""
corpus_fix6_driver.py -- corpus-construction (fix pass 6)
See prompts/corpus-fix-6-price-coverage-gate.md.

Price coverage as an inclusion gate. ZERO Anthropic API calls, ZERO
EarningsCall.biz vendor calls (call-date summaries already exist in
CORPUS_MANIFEST_V2.json). Price data comes from yfinance/Yahoo, the same
free provider used in corpus-fix-5's Job 1, and is written ONLY to
analysis/data/corpus_v2/corpus_v2_price_cache.json -- the root
analysis/data/price_cache.json is never touched.

Usage:
  python3 analysis/corpus_fix6_driver.py sweep
"""
import os, sys, json, datetime, time
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent

CORPUS_DIR = repo_root / "analysis" / "data" / "corpus_v2"
MANIFEST_PATH = CORPUS_DIR / "CORPUS_MANIFEST_V2.json"
ALIASES_PATH = CORPUS_DIR / "TICKER_ALIASES.json"
ROOT_PRICE_CACHE_PATH = repo_root / "analysis" / "data" / "price_cache.json"
V2_PRICE_CACHE_PATH = CORPUS_DIR / "corpus_v2_price_cache.json"
JOB1_RESULT_PATH = CORPUS_DIR / "JOB1_PRICE_RECOVERY_RESULT.json"
SWEEP_OUT_PATH = CORPUS_DIR / "COVERAGE_GATE_SWEEP.json"

FETCH_START = "2020-01-01"
FETCH_END = "2026-09-14"
FORWARD_DAYS = 182
GATE_MIN_GRADABLE_CALLS = 12

# Post-event / predecessor identity forms tried in order, per A8's registered
# identity-resolution-before-coverage rule. Only tried if the primary ticker
# and any TICKER_ALIASES.json entry come back empty.
POST_EVENT_FORMS = {
    "NOVA": ["NOVAQ", "NOVAQQ", "SNOVQ"],
    "SUNW": ["SUNWQ"],
    "FRC": ["FRCB"],
    "WOLF": ["CREE"],  # predecessor ticker, pre-2021 rename
    "GOOGL": ["GOOG"],  # already resolved in TICKER_ALIASES.json A5; tried again here for coverage purposes
}

# S4_TERMINAL_EVENTS: SEC/FDIC-verified dates (fix-4 wrap-up), matching
# corpus_fix5_driver.py's S4_TERMINAL_EVENTS_VERIFIED.
S4_TERMINAL_EVENTS = {
    "FRC": "2023-05-01",
    "SUNW": "2024-02-05",
    "NOVA": "2025-06-09",
    "WOLF": None,  # restructured, not wiped out -- A6 does not apply
}


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


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fetch_series(symbol):
    """Returns (rows_dict date->close, first_date, last_date) or (None, None, None)."""
    import yfinance as yf
    try:
        d = yf.download(symbol, start=FETCH_START, end=FETCH_END, progress=False, auto_adjust=False)
    except Exception:
        return None, None, None
    if d is None or len(d) == 0:
        return None, None, None
    if hasattr(d.columns, "nlevels") and d.columns.nlevels > 1:
        d.columns = d.columns.get_level_values(0)
    rows = {}
    for idx, row in d.iterrows():
        c = row.get("Close")
        if c is None or c != c:
            continue
        rows[idx.date().isoformat()] = float(c)
    if not rows:
        return None, None, None
    return rows, min(rows.keys()), max(rows.keys())


def resolve_identity(ticker, aliases_by_original, existing_v2_cache, existing_root_cache):
    """Returns (symbol_used, source, rows, first, last, attempts_log) using the
    A8 identity-resolution order: primary -> alias -> post-event forms.
    Prefers already-cached data (root cache, then v2 cache) before a new fetch."""
    attempts = []
    candidates = [("primary", ticker)]
    alias = aliases_by_original.get(ticker)
    if alias and alias != ticker:
        candidates.append(("alias(A5)", alias))
    for form in POST_EVENT_FORMS.get(ticker, []):
        candidates.append(("post_event_form", form))

    for kind, sym in candidates:
        # 1. root cache (already vetted, frozen 2026-05-11)
        if sym in existing_root_cache:
            series = existing_root_cache[sym]
            if isinstance(series, dict) and series:
                dates = sorted(series.keys())
                attempts.append({"symbol": sym, "kind": kind, "source": "price_cache.json (existing)", "rows": len(dates)})
                return sym, "price_cache.json", series, dates[0], dates[-1], attempts
        # 2. v2 cache (already fetched this run or in fix-5)
        if sym in existing_v2_cache:
            entry = existing_v2_cache[sym]
            daily = entry.get("daily") if isinstance(entry, dict) else None
            if daily:
                dates = sorted(daily.keys())
                attempts.append({"symbol": sym, "kind": kind, "source": "corpus_v2_price_cache.json (existing)", "rows": len(dates)})
                return sym, "corpus_v2_price_cache.json", daily, dates[0], dates[-1], attempts
        # 3. fresh yfinance fetch
        rows, first, last = fetch_series(sym)
        n = len(rows) if rows else 0
        attempts.append({"symbol": sym, "kind": kind, "source": "yfinance/Yahoo (new fetch)", "rows": n,
                          "first_date": first, "last_date": last})
        time.sleep(0.6)
        if rows:
            return sym, "yfinance/Yahoo", rows, first, last, attempts
    return None, None, None, None, None, attempts


def approx_call_dates(first_call, last_call, n_calls):
    """No vendor calls this run for the 73 non-S4-Job1 companies -- approximate
    evenly-spaced call dates between first_call and last_call (real quarterly-
    earnings cadence). Used ONLY to categorize gradability when a company's
    price series does not fully span [first_call, last_call+182d]; when it
    does fully span that window, every real call (whatever its exact date)
    is gradable and this approximation is moot."""
    f = datetime.date.fromisoformat(first_call)
    l = datetime.date.fromisoformat(last_call)
    if n_calls <= 1:
        return [f]
    step = (l - f).days / (n_calls - 1)
    return [f + datetime.timedelta(days=round(step * i)) for i in range(n_calls)]


def categorize_calls(ticker, call_dates, series_first, series_last, spy_first, spy_last, terminal_event):
    rows = []
    for d in call_dates:
        window_close = d + datetime.timedelta(days=FORWARD_DAYS)
        call_iso, close_iso = d.isoformat(), window_close.isoformat()
        has_series = series_first is not None
        company_covers_call = has_series and (series_first <= call_iso)
        company_covers_close = has_series and (series_last >= close_iso)
        spy_covers_call = spy_first is not None and (spy_first <= call_iso)
        spy_covers_close = spy_last is not None and (spy_last >= close_iso)
        real_price_ok = company_covers_call and company_covers_close and spy_covers_call and spy_covers_close
        if real_price_ok:
            category = "gradable_real_price"
        elif terminal_event and close_iso > terminal_event and company_covers_call and spy_covers_call:
            category = "gradable_terminal_rule"
        else:
            category = "ungradable"
        rows.append({"call_date": call_iso, "window_close": close_iso, "category": category})
    return rows


def sweep():
    manifest = load_json(MANIFEST_PATH)
    aliases_doc = load_json(ALIASES_PATH, default={"entries": []})
    aliases_by_original = {e["original_symbol"]: e["working_symbol"] for e in aliases_doc.get("entries", [])}
    root_cache = load_json(ROOT_PRICE_CACHE_PATH, default={})
    v2_cache = load_json(V2_PRICE_CACHE_PATH, default={})
    job1 = load_json(JOB1_RESULT_PATH, default={})
    job1_cats = job1.get("call_window_categorization", {})

    # --- SPY first, per the prompt ---
    spy_sym, spy_src, spy_rows, spy_first, spy_last, spy_attempts = resolve_identity(
        "SPY", {}, v2_cache, root_cache)
    spy_finding = None
    if spy_rows is None:
        spy_finding = "CRITICAL: SPY price coverage could not be established at all -- every comparison in the corpus needs it."
    else:
        needed_last = None  # computed after we know max window close, checked below
    print(f"SPY: source={spy_src} first={spy_first} last={spy_last}")

    new_alias_additions = []
    per_company = {}
    strata_map = {}
    for stratum, sdata in manifest["strata"].items():
        for c in sdata["frozen"]:
            strata_map[c["ticker"]] = stratum

    max_needed_close = None
    for stratum, sdata in manifest["strata"].items():
        for c in sdata["frozen"]:
            t = c["ticker"]
            n_calls = c.get("n_calls_2020_2025") or 0
            first_call = c.get("first_call")
            last_call = c.get("last_call")
            if not first_call or not last_call or n_calls == 0:
                per_company[t] = {
                    "stratum": stratum, "n_calls": 0, "verdict": "fail",
                    "reason": "no calls recorded in manifest",
                }
                continue
            close = (datetime.date.fromisoformat(last_call) + datetime.timedelta(days=FORWARD_DAYS)).isoformat()
            if max_needed_close is None or close > max_needed_close:
                max_needed_close = close

            symbol_used, source, rows, first, last, attempts = resolve_identity(
                t, aliases_by_original, v2_cache, root_cache)

            if symbol_used and symbol_used != t and t not in aliases_by_original:
                new_alias_additions.append({"original_symbol": t, "working_symbol": symbol_used, "source": source})

            terminal_event = S4_TERMINAL_EVENTS.get(t)

            # Use EXACT call dates from Job 1 for the 4 S4 companies; approximate
            # for everyone else (zero vendor calls this run -- see A8/finding).
            if t in job1_cats:
                call_dates = [datetime.date.fromisoformat(r["call_date"]) for r in job1_cats[t]["calls"]]
                date_source = "exact (corpus-fix-5 Job 1 vendor fetch)"
            else:
                call_dates = approx_call_dates(first_call, last_call, n_calls)
                date_source = "approximated (evenly spaced, first_call..last_call -- no vendor calls this run)"

            cats = categorize_calls(t, call_dates, first, last, spy_first, spy_last, terminal_event)
            counts = {}
            for r in cats:
                counts[r["category"]] = counts.get(r["category"], 0) + 1
            gradable = counts.get("gradable_real_price", 0) + counts.get("gradable_terminal_rule", 0)
            ungradable = counts.get("ungradable", 0)
            verdict = "pass" if gradable >= GATE_MIN_GRADABLE_CALLS else "fail"
            near_line = abs(gradable - GATE_MIN_GRADABLE_CALLS) <= 2

            cause = None
            if symbol_used is None:
                cause = "no price data found under any tried identity (primary/alias/post-event form)"
            elif symbol_used != t:
                cause = f"identity resolved via {source}, symbol '{symbol_used}' (ticker change/delisting/predecessor)"
            elif ungradable > 0:
                cause = "partial price coverage under the primary ticker (approximate call dates -- see date_source)"

            per_company[t] = {
                "stratum": stratum,
                "n_calls_manifest": n_calls,
                "date_source": date_source,
                "symbol_used": symbol_used,
                "identity_source": source,
                "series_first_date": first,
                "series_last_date": last,
                "counts_by_category": counts,
                "gradable_total": gradable,
                "ungradable_total": ungradable,
                "verdict": verdict,
                "near_12_line": near_line,
                "cause_of_gap": cause,
                "attempts": attempts,
            }
            print(f"{t} ({stratum}): symbol_used={symbol_used} gradable={gradable}/{n_calls} verdict={verdict}")

    # Now that we know the true max needed close date, re-flag SPY coverage precisely.
    spy_ok = spy_rows is not None and spy_first <= FETCH_START[:10] and spy_last >= (max_needed_close or FETCH_END)
    if spy_rows is not None and not spy_ok:
        spy_finding = (f"SPY series covers {spy_first}..{spy_last} but the corpus needs coverage through "
                        f"{max_needed_close} -- a real hole affecting every comparison whose window closes after {spy_last}.")

    out = {
        "generated_at": now_iso(),
        "spy": {"symbol_used": spy_sym, "source": spy_src, "first_date": spy_first, "last_date": spy_last,
                "needed_through": max_needed_close, "finding": spy_finding, "attempts": spy_attempts},
        "gate_min_gradable_calls": GATE_MIN_GRADABLE_CALLS,
        "per_company": per_company,
        "new_alias_additions_recommended": new_alias_additions,
    }
    save_json(SWEEP_OUT_PATH, out)

    # Persist any newly-fetched series into corpus_v2_price_cache.json (only
    # series NOT already sourced from price_cache.json -- that file stays
    # frozen and untouched).
    for t, rec in per_company.items():
        sym = rec.get("symbol_used")
        if not sym or rec.get("identity_source") == "price_cache.json":
            continue
        if sym in v2_cache:
            continue
        # Re-fetch to persist (resolve_identity didn't return the raw series here
        # to keep per_company JSON-small); cheap, cached-friendly re-pull.
        rows, first, last = fetch_series(sym)
        if rows:
            v2_cache[sym] = {"symbol_used": sym, "provider": "yfinance/Yahoo",
                              "first_date": first, "last_date": last, "daily": {k: {"close": v} for k, v in rows.items()}}
    if spy_sym and spy_src != "price_cache.json" and spy_sym not in v2_cache:
        rows, first, last = fetch_series(spy_sym)
        if rows:
            v2_cache[spy_sym] = {"symbol_used": spy_sym, "provider": "yfinance/Yahoo",
                                  "first_date": first, "last_date": last, "daily": {k: {"close": v} for k, v in rows.items()}}
    save_json(V2_PRICE_CACHE_PATH, v2_cache)

    if new_alias_additions:
        for add in new_alias_additions:
            aliases_doc.setdefault("entries", []).append({
                "original_symbol": add["original_symbol"],
                "working_symbol": add["working_symbol"],
                "source": add["source"],
                "added_by": "corpus-fix-6-price-coverage-gate",
                "added_at": now_iso(),
            })
        save_json(ALIASES_PATH, aliases_doc)

    print(f"\nWrote {SWEEP_OUT_PATH}")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "sweep":
        sweep()
    else:
        print(__doc__)
        sys.exit(1)
