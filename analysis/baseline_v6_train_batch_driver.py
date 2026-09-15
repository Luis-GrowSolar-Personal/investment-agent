#!/usr/bin/env python3
"""
baseline_v6_train_batch_driver.py -- prompts/baseline-v6-train-batch.md

Fetches train-split transcripts (reusing analysis/ec_fidelity_benchmark_1's
proven vendor client, read-only import per that prompt's instruction), then
scores v6 via the Anthropic Batch API. See the prompt for full protocol.

Usage:
  python3 baseline_v6_train_batch_driver.py events    # resolve symbols + events for all train tickers
  python3 baseline_v6_train_batch_driver.py plan       # reconcile against cached raw/, build fetch plan
  python3 baseline_v6_train_batch_driver.py fetch      # fetch missing transcripts (throttled)
  python3 baseline_v6_train_batch_driver.py validate3  # print 3 transcripts for eyeball validation
  python3 baseline_v6_train_batch_driver.py pilot5     # synchronous 5-call pilot
  python3 baseline_v6_train_batch_driver.py submit     # submit the batch (all remaining requests)
  python3 baseline_v6_train_batch_driver.py poll       # poll batch status, collect results as they land
  python3 baseline_v6_train_batch_driver.py writescores  # write results into version-stamped eval cache
"""
import os, sys, json, time, hashlib, datetime, re
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

sys.path.insert(0, str(REPO_ROOT / "analysis" / "ec_fidelity_benchmark_1"))
import driver as ecf  # vendor_get, vendor_payload_to_text_and_turns, MIN_SPACING_SECONDS

RUN_ID = "baseline-v6-train-batch"
STATE_DIR = REPO_ROOT / "analysis" / "data" / "run_state" / RUN_ID
PROGRESS_PATH = STATE_DIR / "progress.json"
FINDINGS_PATH = STATE_DIR / "findings.md"
TRANSCRIPTS_DIR = REPO_ROOT / "analysis" / "data" / "corpus_v2" / "transcripts"
RAW_CACHE_DIR = REPO_ROOT / "analysis" / "ec_fidelity_benchmark_1" / "raw"

SPLIT_PATH = REPO_ROOT / "analysis" / "data" / "corpus_v2" / "SPLIT_V7_RESERVE_REPLACEMENTS.json"
ALIASES_PATH = REPO_ROOT / "analysis" / "data" / "corpus_v2" / "TICKER_ALIASES.json"
EVAL_PROMPT_PATH = REPO_ROOT / "docs" / "EVALUATION_PROMPT.md"

WINDOW_START = datetime.date(2020, 1, 1)
WINDOW_END = datetime.date(2025, 12, 31)
DATE_MATCH_TOLERANCE_DAYS = 3

HARD_REQUEST_CAP = 1400
MODEL = "claude-sonnet-4-6"


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_progress():
    if not PROGRESS_PATH.exists():
        return None
    return json.loads(PROGRESS_PATH.read_text())


def save_progress(p):
    PROGRESS_PATH.write_text(json.dumps(p, indent=2, default=str))


def append_finding(text):
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS_PATH.open("a") as f:
        f.write(f"\n- {now_iso()}: {text}\n")


def load_train_tickers():
    split = json.loads(SPLIT_PATH.read_text())
    aliases_raw = json.loads(ALIASES_PATH.read_text())
    amap = {e["original_symbol"]: e["working_symbol"]
            for e in aliases_raw["entries"] if e.get("working_symbol")}
    train = split["train"]
    return [(t, amap.get(t, t)) for t in train]


# A dedicated progress dict is used here (not ecf's own progress.json) because
# this run has its own call budget, state dir, and target set.
def _vendor_progress():
    p = load_progress()
    if "calls_used_total" not in p:
        p["calls_used_total"] = 0
    if "spacing_last_call_at" not in p:
        p["spacing_last_call_at"] = 0
    return p


def vendor_get_local(progress, endpoint, params):
    """Thin re-implementation of ecf.vendor_get against THIS run's progress
    dict (ecf.vendor_get is bound to ecf's own module-level progress file)."""
    elapsed = time.time() - progress.get("spacing_last_call_at", 0)
    if elapsed < ecf.MIN_SPACING_SECONDS:
        time.sleep(ecf.MIN_SPACING_SECONDS - elapsed)
    import urllib.request, urllib.parse, urllib.error
    qs = urllib.parse.urlencode({**params, "apikey": os.environ["ECB_API_KEY"]})
    url = f"https://v2.api.earningscall.biz/{endpoint}?{qs}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")
    progress["spacing_last_call_at"] = time.time()
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    save_progress(progress)
    if status in (401, 429):
        raise SystemExit(f"vendor_get: HARD STOP status={status} endpoint={endpoint} body={body[:300]}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = body
    return status, data


def cmd_events():
    progress = _vendor_progress()
    progress.setdefault("symbols", {})
    progress.setdefault("events", {})
    tickers = load_train_tickers()
    for orig, working in tickers:
        if working in progress["events"]:
            continue
        status, data = vendor_get_local(progress, "symbols-v2.txt", {}) if working not in progress["symbols"] else (200, None)
        # symbols-v2.txt is a single global call; fetch once and cache lookups
        if "symtab" not in progress:
            status2, text = vendor_get_local(progress, "symbols-v2.txt", {})
            symtab = {}
            for line in text.splitlines() if isinstance(text, str) else []:
                parts = line.split("\t")
                if len(parts) >= 2:
                    symtab.setdefault(parts[1].upper(), []).append(parts[0])
            progress["symtab"] = symtab
            save_progress(progress)
        exch_idx = progress["symtab"].get(working)
        if not exch_idx:
            progress["events"][working] = {"error": "not_in_symbol_list", "events": []}
            append_finding(f"**Coverage miss**: {orig}/{working} not in vendor symbol list")
            save_progress(progress)
            continue
        # exchange codes: reuse ecf's EXCHANGES_IN_ORDER mapping
        try:
            exch = ecf.EXCHANGES_IN_ORDER[int(exch_idx[0])]
        except Exception:
            exch = "NASDAQ"
        status, data = vendor_get_local(progress, "events", {"exchange": exch, "symbol": working})
        if status != 200 or not isinstance(data, dict):
            progress["events"][working] = {"error": f"http_{status}", "events": []}
            append_finding(f"**Events call failed** for {orig}/{working}: HTTP {status}")
            save_progress(progress)
            continue
        evs = [{"year": e.get("year"), "quarter": e.get("quarter"),
                "conference_date": e.get("conference_date")}
               for e in data.get("events", [])]
        progress["events"][working] = {"exchange": exch, "events": evs}
        save_progress(progress)
        print(f"{orig}/{working}: {len(evs)} events (calls used: {progress['calls_used_total']})")
    print(f"\nTotal vendor calls used: {progress['calls_used_total']}")


def _parse_conf_date(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def build_plan(progress):
    """One row per (working_ticker, year, quarter) event in the corpus window.
    Cross-references RAW_CACHE_DIR for free coverage."""
    tickers = load_train_tickers()
    plan = []
    coverage_misses = []
    for orig, working in tickers:
        info = progress["events"].get(working)
        if not info or info.get("error"):
            coverage_misses.append({"original": orig, "working": working,
                                     "reason": info.get("error") if info else "no_events_entry"})
            continue
        for e in info["events"]:
            d = _parse_conf_date(e["conference_date"])
            if not d or not (WINDOW_START <= d <= WINDOW_END):
                continue
            cached = None
            candidate = RAW_CACHE_DIR / f"{working}_{e['year']}Q{e['quarter']}_id*.json"
            matches = list(RAW_CACHE_DIR.glob(f"{working}_{e['year']}Q{e['quarter']}_id*.json"))
            if matches:
                cached = str(matches[0])
            plan.append({
                "original": orig, "working": working, "year": e["year"],
                "quarter": e["quarter"], "conference_date": e["conference_date"],
                "call_date": d.isoformat(), "exchange": info["exchange"],
                "cached_raw_path": cached,
            })
    return plan, coverage_misses


def cmd_plan():
    progress = load_progress()
    plan, misses = build_plan(progress)
    plan_path = STATE_DIR / "fetch_plan.json"
    plan_path.write_text(json.dumps({"plan": plan, "coverage_misses": misses}, indent=2))
    n_cached = sum(1 for p in plan if p["cached_raw_path"])
    print(f"Plan: {len(plan)} transcripts in window, {n_cached} already cached on disk, "
          f"{len(plan) - n_cached} to fetch.")
    print(f"Coverage misses (companies): {misses}")
    print(f"Total (transcripts to score, incl. cached): {len(plan)} -- hard cap {HARD_REQUEST_CAP}")
    if len(plan) > HARD_REQUEST_CAP:
        print(f"*** EXCEEDS CAP by {len(plan) - HARD_REQUEST_CAP}. Must trim before proceeding. ***")


def cmd_fetch():
    progress = _vendor_progress()
    plan_path = STATE_DIR / "fetch_plan.json"
    plan_data = json.loads(plan_path.read_text())
    plan = plan_data["plan"]
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    reused = 0
    failed = 0
    for row in plan:
        out_path = TRANSCRIPTS_DIR / row["working"] / f"{row['call_date']}.json"
        if out_path.exists():
            continue  # already fetched this run (resume)
        payload = None
        source = None
        if row["cached_raw_path"]:
            payload = json.loads(Path(row["cached_raw_path"]).read_text())
            source = "disk_cache"
            reused += 1
        else:
            level = progress.get("transcript_level", 2)
            status, data = vendor_get_local(progress, "transcript", {
                "exchange": row["exchange"], "symbol": row["working"],
                "year": row["year"], "quarter": row["quarter"], "level": level,
            })
            if status in (402, 403) and progress.get("transcript_level", 2) == 2:
                append_finding(f"Level 2 refused (HTTP {status}) for {row['working']} "
                                f"{row['year']}Q{row['quarter']} -- falling back to level 1 for the whole run.")
                progress["transcript_level"] = 1
                save_progress(progress)
                status, data = vendor_get_local(progress, "transcript", {
                    "exchange": row["exchange"], "symbol": row["working"],
                    "year": row["year"], "quarter": row["quarter"], "level": 1,
                })
            if status == 404 or (isinstance(data, dict) and not data.get("speakers") and not data.get("text")):
                append_finding(f"Coverage miss (transcript): {row['working']} {row['year']}Q{row['quarter']} "
                                f"call_date={row['call_date']} status={status}")
                failed += 1
                continue
            if status != 200:
                append_finding(f"Transcript fetch failed: {row['working']} {row['year']}Q{row['quarter']} "
                                f"status={status} body={str(data)[:200]}")
                failed += 1
                continue
            payload = data
            source = "vendor_fetch"
            fetched += 1
        text, turns = ecf.vendor_payload_to_text_and_turns(payload)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "ticker": row["working"], "original_ticker": row["original"],
            "call_date": row["call_date"], "year": row["year"], "quarter": row["quarter"],
            "vendor_params": {"exchange": row["exchange"], "symbol": row["working"],
                               "year": row["year"], "quarter": row["quarter"]},
            "source": source, "fetched_at": now_iso(),
            "raw_payload": payload, "text": text, "n_turns": len(turns),
        }, indent=2))
        if (fetched + reused) % 25 == 0:
            print(f"  progress: fetched={fetched} reused={reused} failed={failed} "
                  f"vendor_calls={progress['calls_used_total']}")
    print(f"\nDone. fetched_fresh={fetched} reused_from_cache={reused} failed={failed} "
          f"total_vendor_calls_used={progress['calls_used_total']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "events":
        cmd_events()
    elif cmd == "plan":
        cmd_plan()
    elif cmd == "fetch":
        cmd_fetch()
    else:
        print(__doc__)
