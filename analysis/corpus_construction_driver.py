#!/usr/bin/env python3
"""
driver.py -- corpus-construction
See prompts/corpus-construction.md for the full spec and
analysis/data/corpus_v2/PREREGISTRATION.json for the frozen selection rules
this driver implements mechanically. Selects and freezes an 80-company
corpus. Makes ZERO Anthropic API calls and writes ZERO Analysis rows.
Vendor (EarningsCall.biz) calls are metadata-only (symbols-v2.txt, /events)
-- no transcript text is ever requested by this driver.

Usage:
  python3 analysis/corpus_construction_driver.py select    # Steps 1-2: build the 80-name list (no vendor calls)
  python3 analysis/corpus_construction_driver.py avail     # Step 3: vendor metadata-only availability check
  python3 analysis/corpus_construction_driver.py freeze    # Step 4a: write CORPUS_MANIFEST.json
  python3 analysis/corpus_construction_driver.py outcomes  # Step 4b: yfinance-based outcome balance (new cache file)
  python3 analysis/corpus_construction_driver.py split     # Step 5: three-way split + holdout lock
"""
import os, sys, json, random, hashlib, datetime, time
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
PREREG_PATH = CORPUS_DIR / "PREREGISTRATION.json"
MANIFEST_PATH = CORPUS_DIR / "CORPUS_MANIFEST.json"
NEW_PRICE_CACHE = CORPUS_DIR / "corpus_v2_price_cache.json"

ECB_API_KEY = os.environ.get("ECB_API_KEY")
BASE_URL = "https://v2.api.earningscall.biz"
HARD_CALL_CAP = 120           # this run's own cap -- ~81 calls expected (1 symbols + 80 events)
MIN_SPACING_SECONDS = 3.5

EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

ALL16 = {
    "ESTABLISHED": ["AAPL", "AMD", "AVGO", "GOOGL", "MSFT", "NVDA", "ORCL", "TSLA"],
    "SPECULATIVE": ["AMPX", "ENVX", "EOSE", "FSLR", "QS", "RUN", "SPWR", "TTD"],
}
ALL16_FLAT = ALL16["ESTABLISHED"] + ALL16["SPECULATIVE"]

# S1 -- ranks 21-40 of Dec 2020 US mega/large caps by market cap, per general
# published knowledge (ranks 1-10 well-established across sources; 11-40 not
# independently re-verified against a single retrieved ranked table in this
# run -- see PREREGISTRATION.json "known_limitation" and the wrap-up).
S1_RANK_ORDER = [
    "CMCSA", "NFLX", "XOM", "INTC", "VZ", "KO", "NKE", "MRK", "PFE", "T",
    "ABT", "CRM", "PEP", "TMO", "CSCO", "AVGO", "ACN", "COST", "MCD", "QCOM",
    "TXN", "HON", "UPS", "LIN",  # extras, used only if a rank-21-40 name collides with ALL16
]


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_json(p, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=str))


def append_finding(text):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def append_cell(cell):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CELLS_PATH, "a") as f:
        f.write(json.dumps(cell, default=str) + "\n")


# ----------------------------------------------------------------------------
# Steps 1-2: selection (zero API/vendor calls)
# ----------------------------------------------------------------------------

def build_s1(prereg):
    picks = []
    for t in S1_RANK_ORDER:
        if t in ALL16_FLAT or t in picks:
            continue
        picks.append(t)
        if len(picks) == 20:
            break
    return picks


def build_s2_or_s3(pool, quota_by_band, seed, exclude):
    rnd = random.Random(seed)
    out = {}
    for band, n in quota_by_band.items():
        candidates = [t for t in pool[band] if t not in exclude and t not in ALL16_FLAT]
        rnd.shuffle(candidates)
        out[band] = candidates[:n]
        out[band + "_reserve"] = candidates[n:]
    return out


def build_s3(prereg, exclude):
    pool = prereg["strata"]["S3"]["candidate_pool"]
    seed = prereg["strata"]["S3"]["seed"]
    sector_cap = prereg["strata"]["S3"]["sector_cap"]
    rnd = random.Random(seed)
    chosen, reserves = [], {}
    for sector, tickers in pool.items():
        cands = [t for t in tickers if t not in ALL16_FLAT and t not in exclude]
        rnd.shuffle(cands)
        take = cands[:sector_cap]
        chosen.extend(take)
        reserves[sector] = cands[sector_cap:]
    return chosen[:20], reserves


def build_s4(prereg):
    """Verify each of the prompt's suggested S4 candidates against the
    pre-registered rule (2020 S&P500 membership OR 2020 DOMAIN.md membership),
    mechanically, using facts established in Step 1 research. Verification
    notes are the record of that check -- not a post-hoc justification."""
    candidates = [
        {"name": "SVB Financial Group", "ticker": "SIVB",
         "verify": "2020 S&P 500 constituent (long-standing member; not listed as an addition in the 2021-2025 change log, and removed only via the 2023-03-15 FDIC receivership event, which reads as departure of an existing member, not a new one)",
         "qualifies": True, "failure_mode": "FDIC receivership, March 2023"},
        {"name": "First Republic Bank", "ticker": "FRC",
         "verify": "Confirmed present in the Wikipedia 2020-12-31 revision, item 192 ('FRC - First Republic Bank')",
         "qualifies": True, "failure_mode": "FDIC receivership, May 2023"},
        {"name": "Signature Bank", "ticker": "SBNY",
         "verify": "NOT a 2020-12-31 constituent -- added 2021-12-20 per the Historical-components change log, and not in DOMAIN.md's universe (bank, no solar/storage/semiconductor/software/crypto thesis). FAILS the pre-registered rule.",
         "qualifies": False, "failure_mode": None},
        {"name": "Proterra Inc.", "ticker": "PTRA",
         "verify": "Never an S&P 500 constituent (SPAC-listed 2021, small cap). Core business is electric bus manufacturing, not energy storage as a business in its own right (DOMAIN.md's storage tier is about grid/behind-the-meter storage systems and market dynamics, not vehicle OEMs) -- treated as NOT in DOMAIN.md's 2020 universe. FAILS the pre-registered rule.",
         "qualifies": False, "failure_mode": None},
        {"name": "Fisker Inc.", "ticker": "FSR",
         "verify": "Never an S&P 500 constituent; EV OEM, not an energy-storage or semiconductor business -- outside DOMAIN.md. FAILS.",
         "qualifies": False, "failure_mode": None},
        {"name": "Nikola Corporation", "ticker": "NKLA",
         "verify": "Never an S&P 500 constituent; hydrogen/EV truck OEM, not solar/storage/semiconductor/software -- outside DOMAIN.md. FAILS.",
         "qualifies": False, "failure_mode": None},
        {"name": "Lordstown Motors", "ticker": "RIDE",
         "verify": "Never an S&P 500 constituent; EV truck OEM -- outside DOMAIN.md. FAILS.",
         "qualifies": False, "failure_mode": None},
        {"name": "Li-Cycle Holdings", "ticker": "LICY",
         "verify": "Never an S&P 500 constituent; battery-materials recycler. DOMAIN.md's storage tier does not name recycling/materials-recovery as in-scope -- treated as outside DOMAIN.md for this run. FAILS (kept on the S6 reserve list as a borderline case worth a future explicit domain ruling).",
         "qualifies": False, "failure_mode": None},
        {"name": "Wolfspeed, Inc.", "ticker": "WOLF",
         "verify": "Traded as CREE through 2020 (renamed Wolfspeed, ticker WOLF, October 2021). Core business is silicon-carbide power semiconductors -- squarely DOMAIN.md Tier 1 (Semiconductors). Not verified as an S&P 500 constituent in 2020 (mid-cap at the time), but qualifies via the DOMAIN.md branch of the rule.",
         "qualifies": True, "failure_mode": "Chapter 11 bankruptcy filing, 2025"},
    ]
    reserve = [
        {"name": "Sunnova Energy International", "ticker": "NOVA",
         "verify": "DOMAIN.md Tier 1 (residential solar + storage). Not a 2020 S&P 500 constituent, qualifies via DOMAIN.md branch.",
         "qualifies": True, "failure_mode": "Chapter 11 bankruptcy filing, 2025"},
        {"name": "Romeo Power", "ticker": "RMO",
         "verify": "DOMAIN.md Tier 1 (battery/energy storage systems). Not a 2020 S&P 500 constituent, qualifies via DOMAIN.md branch. Added via the dated 2026-09-14 reserve-pool amendment in PREREGISTRATION.json, written before any outcome look.",
         "qualifies": True, "failure_mode": "Forced distressed all-stock merger into Nikola, 2022, after going-concern warnings"},
        {"name": "Sunworks", "ticker": "SUNW",
         "verify": "DOMAIN.md Tier 1 (residential/commercial solar EPC). Not a 2020 S&P 500 constituent, qualifies via DOMAIN.md branch. Added via the dated 2026-09-14 reserve-pool amendment in PREREGISTRATION.json, written before any outcome look.",
         "qualifies": True, "failure_mode": "Chapter 11 bankruptcy filing, 2025"},
    ]
    qualified = [c for c in candidates if c["qualifies"]]
    return qualified, [c for c in candidates if not c["qualifies"]], reserve, candidates


def cmd_select():
    prereg = load_json(PREREG_PATH)
    if prereg is None:
        print("PREREGISTRATION.json missing -- run Step 0b first."); return

    s1 = build_s1(prereg)
    s2 = build_s2_or_s3(prereg["strata"]["S2"]["candidate_pool"],
                         prereg["strata"]["S2"]["size_bands"],
                         prereg["strata"]["S2"]["seed"],
                         exclude=set(s1))
    s2_flat = s2["large"] + s2["small"] + s2["micro"]
    s3_list, s3_reserves = build_s3(prereg, exclude=set(s1) | set(s2_flat))
    s4_qualified, s4_dropped, s4_reserve, s4_all = build_s4(prereg)

    # S4 shortfall fill from reserve, mechanically, in listed order
    need = 8 - len(s4_qualified)
    s4_final = list(s4_qualified)
    if need > 0:
        s4_final.extend(s4_reserve[:need])
        remaining_short = need - len(s4_reserve[:need])
    else:
        remaining_short = 0

    s5 = ALL16_FLAT

    selection = {
        "run_id": RUN_ID,
        "generated_at": now_iso(),
        "S1": {"target": 20, "selected": s1, "rule": "ranks 21-40 minus ALL16 collisions"},
        "S2": {"target": 16, "selected": s2["large"] + s2["small"] + s2["micro"],
               "by_band": {k: v for k, v in s2.items() if not k.endswith("_reserve")},
               "reserves": {k: v for k, v in s2.items() if k.endswith("_reserve")}},
        "S3": {"target": 20, "selected": s3_list, "reserves": s3_reserves},
        "S4": {"target": 8, "selected": [c["ticker"] for c in s4_final],
               "detail": s4_all, "dropped_candidates": s4_dropped,
               "used_from_reserve": s4_reserve[: max(need, 0)],
               "shortfall_after_reserve": max(remaining_short, 0)},
        "S5": {"target": 16, "selected": s5, "note": "carried forward unchanged; excluded from Step 6 headline figures"},
    }
    all_selected = (selection["S1"]["selected"] + selection["S2"]["selected"] +
                    selection["S3"]["selected"] + selection["S4"]["selected"] + s5)
    dupes = [t for t in set(all_selected) if all_selected.count(t) > 1]
    selection["total_companies"] = len(all_selected)
    selection["distinct_companies"] = len(set(all_selected))
    selection["duplicate_tickers_across_strata"] = dupes

    save_json(CORPUS_DIR / "selection_working.json", selection)
    for stratum in ("S1", "S2", "S3", "S4", "S5"):
        append_cell({"cell_key": stratum, "selected": selection[stratum]["selected"]})
    append_finding(f"## Step 1-2 selection ({now_iso()})\n\nS1={len(selection['S1']['selected'])}, "
                   f"S2={len(selection['S2']['selected'])}, S3={len(selection['S3']['selected'])}, "
                   f"S4={len(selection['S4']['selected'])} (shortfall {selection['S4']['shortfall_after_reserve']}), "
                   f"S5={len(s5)}. Total selected: {selection['total_companies']}, distinct: {selection['distinct_companies']}, "
                   f"duplicates: {dupes or 'none'}.")
    print(json.dumps({k: v for k, v in selection.items() if k in
                      ("S1", "S2", "S3", "S4", "S5", "total_companies", "distinct_companies", "duplicate_tickers_across_strata")},
                     indent=2, default=str))


# ----------------------------------------------------------------------------
# Step 3: vendor metadata-only availability check
# ----------------------------------------------------------------------------

def vendor_get(progress, endpoint, params):
    if progress.get("calls_used_total", 0) >= HARD_CALL_CAP:
        raise RuntimeError(f"HARD_CALL_CAP={HARD_CALL_CAP} reached")
    if progress.get("last_call_ts"):
        elapsed = time.time() - progress["last_call_ts"]
        if elapsed < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - elapsed)
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent corpus-construction"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress["last_call_ts"] = time.time()
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint, "params": params})
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


def cmd_avail():
    if not ECB_API_KEY:
        print("ECB_API_KEY not set -- cannot run Step 3 vendor calls."); return
    selection = load_json(CORPUS_DIR / "selection_working.json")
    if selection is None:
        print("Run `select` first."); return
    progress = load_json(PROGRESS_PATH, {})
    progress.setdefault("calls_used_total", 0)
    all_tickers = sorted(set(
        selection["S1"]["selected"] + selection["S2"]["selected"] +
        selection["S3"]["selected"] + selection["S4"]["selected"] + selection["S5"]["selected"]
    ))
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

    avail = {}
    for t in all_tickers:
        exchs = symtab.get(t)
        if not exchs:
            avail[t] = {"in_symbol_list": False, "n_calls_in_window": 0, "first": None, "last": None,
                        "max_gap_quarters": None, "meets_threshold": False}
            append_finding(f"**Availability: {t} not in vendor symbol list** ({now_iso()})")
            continue
        exch = exchs[0]
        try:
            status, data = vendor_get(progress, "events", {"exchange": exch, "symbol": t})
        except RuntimeError as e:
            print(e); break
        if status != 200 or not isinstance(data, dict):
            avail[t] = {"in_symbol_list": True, "exchange": exch, "n_calls_in_window": 0,
                        "first": None, "last": None, "max_gap_quarters": None, "meets_threshold": False,
                        "vendor_error": f"HTTP {status}"}
            append_cell({"cell_key": t, "avail": avail[t]})
            continue
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
        max_gap_q = 0
        if len(dates) > 1:
            for a, b in zip(dates, dates[1:]):
                gap_days = (b - a).days
                gap_q = gap_days / 91.0
                max_gap_q = max(max_gap_q, gap_q)
        meets = (len(dates) >= 12) and (max_gap_q <= 2.0 or len(dates) <= 1)
        avail[t] = {"in_symbol_list": True, "exchange": exch, "n_calls_in_window": len(dates),
                    "first": dates[0].isoformat() if dates else None,
                    "last": dates[-1].isoformat() if dates else None,
                    "max_gap_quarters": round(max_gap_q, 2), "meets_threshold": meets}
        append_cell({"cell_key": t, "avail": avail[t]})
        print(f"  {t}: {len(dates)} calls, {dates[0] if dates else '-'}..{dates[-1] if dates else '-'}, "
              f"max_gap={round(max_gap_q,2)}q, meets_threshold={meets}")

    save_json(CORPUS_DIR / "availability_working.json", avail)
    print(f"\nVendor calls used this run: {progress['calls_used_total']} (this driver's own cap {HARD_CALL_CAP})")
    dropped = [t for t, a in avail.items() if not a.get("meets_threshold")]
    append_finding(f"## Step 3 availability ({now_iso()})\n\nChecked {len(all_tickers)} tickers, "
                   f"{progress['calls_used_total']} vendor calls used. Failing the drop threshold: {dropped or 'none'}.")
    print(f"Failing drop rule: {dropped}")


if __name__ == "__main__":
    cmds = {"select": cmd_select, "avail": cmd_avail}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__); sys.exit(1)
    cmds[sys.argv[1]]()
