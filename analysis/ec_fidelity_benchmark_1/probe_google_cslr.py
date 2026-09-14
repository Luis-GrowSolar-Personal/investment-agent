#!/usr/bin/env python3
"""
probe_google_cslr.py -- ad hoc follow-up to ec-fidelity-benchmark-1

Two named gaps from the wrap-up:
  1. GOOGL absent from EarningsCall's symbol list entirely -- Alphabet has
     both a GOOGL (Class A) and GOOG (Class C) ticker; the vendor may key
     off one and not the other.
  2. SPWR 2025Q3 returned a complete, well-formed transcript for the WRONG
     company (bankrupt-2024 SunPower's 2023Q3 call). The DB's SPWR is the
     former CSLR (Complete Solaria), which bought SunPower assets and was
     renamed. The vendor may still carry the pre-rename ticker CSLR as a
     separate, correct entry.

This is a cheap, targeted probe, not a re-run of the benchmark: it does NOT
touch ec-fidelity-benchmark-1's progress.json targets/fetched/matches. It
DOES read and update that file's calls_used_total / call_log, so the
running total against the 1,000-call refund condition stays accurate, and
it refuses to run if that would push the lifetime total past HARD_CALL_CAP.

Calls made: 1 (symbols-v2.txt, full list, not just the 15 portfolio
tickers) + up to 2 (events for whichever of GOOG / CSLR actually appear).
Transcript-level fetches are NOT made here -- that's a separate, explicit
follow-up once we know whether either symbol exists and has events near
the right dates.

Usage:
  python3 probe_google_cslr.py
"""
import os, sys, json, time, datetime
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent.parent
load_dotenv(repo_root / ".env")

RUN_ID = "ec-fidelity-benchmark-1"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
PROGRESS_PATH = STATE_DIR / "progress.json"
RAW_DIR = script_dir / "raw"

ECB_API_KEY = os.environ["ECB_API_KEY"]
BASE_URL = "https://v2.api.earningscall.biz"
HARD_CALL_CAP = 300
MIN_SPACING_SECONDS = 3.5

EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

# Known DB call dates this probe is checking against (from the wrap-up /
# prior Test 3 findings -- not re-queried here, no DB driver on this
# machine). SPWR Q1 2025 call 2025-04-30 (transcript id 32), SPWR Q3 2025
# call 2025-10-21 (transcript id 31, the wrong-company cell).
SPWR_TARGET_DATES = ["2025-04-30", "2025-10-21"]
DATE_MATCH_TOLERANCE_DAYS = 3


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_progress():
    if not PROGRESS_PATH.exists():
        print(f"No progress.json at {PROGRESS_PATH} -- run the main benchmark's `draw` first.")
        sys.exit(1)
    return json.loads(PROGRESS_PATH.read_text())


def save_progress(p):
    PROGRESS_PATH.write_text(json.dumps(p, indent=2, default=str))


def vendor_get(progress, endpoint, params, expect_json=True):
    if progress.get("calls_used_total", 0) >= HARD_CALL_CAP:
        raise RuntimeError(f"HARD_CALL_CAP={HARD_CALL_CAP} reached; refusing further vendor calls")
    last = progress.get("last_call_ts")
    if last:
        since = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last)).total_seconds()
        if since < MIN_SPACING_SECONDS:
            time.sleep(MIN_SPACING_SECONDS - since)
    q = dict(params)
    q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent probe_google_cslr"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress.setdefault("call_log", []).append({
        "ts": now_iso(), "endpoint": endpoint,
        "params": {k: v for k, v in params.items() if k != "apikey"},
        "status": "sent", "note": "probe_google_cslr",
    })
    save_progress(progress)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read(); status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read(); status = e.code
    text = body.decode("utf-8", errors="replace")
    progress["call_log"][-1]["status"] = status
    progress["last_call_ts"] = now_iso()
    save_progress(progress)
    if status == 429:
        raise RuntimeError(f"429 rate-limited on {endpoint} {params}: {text[:300]}")
    if status == 401:
        raise RuntimeError(f"401 invalid API key on {endpoint}: {text[:300]}")
    if status >= 400:
        return status, text
    if expect_json:
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text
    return status, text


def main():
    progress = load_progress()
    used = progress.get("calls_used_total", 0)
    print(f"Calls used so far (this run's cumulative total): {used}/{HARD_CALL_CAP} (refund condition: {used}/1000)")
    if used + 3 > HARD_CALL_CAP:
        print("Not enough headroom for this probe (up to 3 calls). Stopping.")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("\n=== Call 1: symbols-v2.txt (full list) ===")
    status, text = vendor_get(progress, "symbols-v2.txt", {}, expect_json=False)
    if status != 200:
        print(f"HTTP {status}: {str(text)[:300]}")
        return
    (RAW_DIR / "probe_symbols-v2.txt").write_text(text)

    candidates = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sym = parts[1].upper()
        if sym in ("GOOG", "CSLR", "GOOGL", "SPWR"):
            try:
                exch = EXCHANGES_IN_ORDER[int(parts[0])]
            except (ValueError, IndexError):
                exch = f"UNKNOWN({parts[0]})"
            candidates[sym] = {"exchange": exch, "name": parts[2]}

    print(f"Found in vendor symbol list: {candidates if candidates else '(none of GOOG/CSLR/GOOGL/SPWR)'}")
    for known_absent in ("GOOGL", "SPWR"):
        if known_absent in candidates:
            print(f"  NOTE: {known_absent} unexpectedly present now (main run recorded it "
                  f"{'absent' if known_absent=='GOOGL' else 'present but wrong-company'} on 2026-09-06) -- re-verify before trusting.")

    for sym in ("GOOG", "CSLR"):
        if sym not in candidates:
            print(f"\n{sym}: not in vendor symbol list. No events call made for it.")
            continue
        info = candidates[sym]
        print(f"\n=== Call: events for {sym} ({info['exchange']}) ===")
        status, data = vendor_get(progress, "events", {"exchange": info["exchange"], "symbol": sym})
        if status != 200 or not isinstance(data, dict):
            print(f"HTTP {status}: {str(data)[:300]}")
            continue
        (RAW_DIR / f"probe_events_{sym}.json").write_text(json.dumps(data, indent=2))
        events = data.get("events", [])
        print(f"{len(events)} events returned. First few: {events[:3]}")
        print(f"Last few: {events[-3:]}")

        if sym == "CSLR":
            for target_date_str in SPWR_TARGET_DATES:
                target = datetime.date.fromisoformat(target_date_str)
                best = None
                for e in events:
                    cd = e.get("conference_date")
                    if not cd:
                        continue
                    try:
                        d = datetime.datetime.fromisoformat(str(cd).replace("Z", "+00:00")).date()
                    except ValueError:
                        continue
                    delta = abs((d - target).days)
                    if delta <= DATE_MATCH_TOLERANCE_DAYS and (best is None or delta < best[1]):
                        best = (e, delta)
                if best:
                    print(f"  CSLR event near DB SPWR call {target_date_str}: {best[0]} (delta {best[1]}d) -- CANDIDATE MATCH")
                else:
                    print(f"  CSLR: no event within {DATE_MATCH_TOLERANCE_DAYS}d of {target_date_str}")

    print(f"\nTotal calls used now: {progress['calls_used_total']}/{HARD_CALL_CAP} "
          f"(refund condition: {progress['calls_used_total']}/1000)")
    print("\nNo transcript fetched yet. If a CSLR or GOOG event matched above, the next step "
          "is a single transcript?...&level=2 call to confirm content before deciding anything -- "
          "not run automatically by this script.")


if __name__ == "__main__":
    main()
