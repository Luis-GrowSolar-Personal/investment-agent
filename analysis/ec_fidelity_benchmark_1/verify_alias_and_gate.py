#!/usr/bin/env python3
"""
verify_alias_and_gate.py -- follow-up to ec-fidelity-benchmark-1 / probe_google_cslr.py

Two things, in order:

1. **Company-name mismatch gate.** EarningsCall has no rename-detection
   endpoint (checked the SDK source, the GitHub org's other repos, and the
   changelog -- no CIK/ISIN/former_names/ticker_history field anywhere).
   But /symbols-v2.txt and /events both return a `company_name` string.
   That is a de facto proxy: compare it against the DB's own Ticker.name /
   Ticker.shortName before trusting any content from that symbol. This
   would have caught SPWR ("SunPower Inc.") without knowing the naming
   trap in advance. Runs against the DB tickers this project actually
   tracks (ALL16 + watchlist), 0 new vendor calls -- reuses the saved
   probe_symbols-v2.txt.

2. **GOOG alias confirmation.** GOOGL is absent from the vendor entirely;
   probe_google_cslr.py found GOOG (Alphabet Inc., 32 events back to 2018).
   Match GOOG's most recent *published* event to the nearest DB GOOGL
   callDate, fetch exactly ONE transcript, and run the same decisive
   classify_sample check the whole benchmark uses -- to confirm GOOG is
   really Alphabet's content, not assume it from the company_name field
   alone (same standard applied to every other cell in the run).

Calls made: 0 for the gate (reuses saved files) + 1 transcript fetch for
the GOOG confirmation, IF a DB GOOGL row matches within tolerance. Reads
and updates ec-fidelity-benchmark-1/progress.json's calls_used_total /
call_log so the running total against the 1,000-call refund condition
stays accurate. Does not touch that file's targets/fetched/matches.

Usage:
  python3 verify_alias_and_gate.py
"""
import os, sys, json, time, difflib, datetime
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent.parent
load_dotenv(repo_root / ".env")

import psycopg2, psycopg2.extras

sys.path.insert(0, str(script_dir))
from driver import classify_sample, vendor_payload_to_text_and_turns  # reuse, byte-for-byte

RUN_ID = "ec-fidelity-benchmark-1"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
PROGRESS_PATH = STATE_DIR / "progress.json"
RAW_DIR = script_dir / "raw"

ECB_API_KEY = os.environ["ECB_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]
BASE_URL = "https://v2.api.earningscall.biz"
HARD_CALL_CAP = 300
MIN_SPACING_SECONDS = 3.5
DATE_MATCH_TOLERANCE_DAYS = 5  # widened slightly for this one-off check; not the benchmark's own tolerance

ALL_TICKERS = ["AAPL", "GOOGL", "NVDA", "MSFT", "TSLA", "AVGO", "AMD", "ORCL",
               "FSLR", "TTD", "QS", "AMPX", "ENVX", "EOSE", "RUN", "SPWR"]

# Known vendor-symbol substitutions worth checking even though the vendor
# doesn't call them out anywhere -- built from what this and the prior
# probe found, not an exhaustive or maintained list.
ALIAS_CANDIDATES = {"GOOGL": "GOOG"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_progress():
    if not PROGRESS_PATH.exists():
        print(f"No progress.json at {PROGRESS_PATH}."); sys.exit(1)
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
    q = dict(params); q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent verify_alias_and_gate"})
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress.setdefault("call_log", []).append({"ts": now_iso(), "endpoint": endpoint,
        "params": {k: v for k, v in params.items() if k != "apikey"}, "status": "sent", "note": "verify_alias_and_gate"})
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
    if status >= 400:
        return status, text
    if expect_json:
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text
    return status, text


def name_similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def part1_name_gate():
    print("=== Part 1: company-name mismatch gate (0 vendor calls, reuses saved symbol list) ===\n")
    symbols_path = RAW_DIR / "probe_symbols-v2.txt"
    if not symbols_path.exists():
        print(f"Missing {symbols_path} -- run probe_google_cslr.py first."); return
    EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]
    vendor_by_symbol = {}
    for line in symbols_path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        vendor_by_symbol[parts[1].upper()] = parts[2]

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT symbol, name, "shortName" FROM "Ticker" WHERE symbol = ANY(%s)', (ALL_TICKERS,))
        db_rows = {r["symbol"]: r for r in cur.fetchall()}
    conn.close()

    print(f"{'ticker':<8} {'DB name':<28} {'vendor company_name':<28} {'best sim':<8} verdict")
    flagged = []
    for t in ALL_TICKERS:
        db = db_rows.get(t)
        db_name = (db or {}).get("name") or ""
        db_short = (db or {}).get("shortName") or ""
        vendor_name = vendor_by_symbol.get(t)
        if vendor_name is None:
            print(f"{t:<8} {db_name:<28} {'(absent from vendor)':<28} {'-':<8} COVERAGE MISS")
            flagged.append((t, "absent"))
            continue
        sim = max(name_similarity(db_name, vendor_name), name_similarity(db_short, vendor_name) if db_short else 0)
        verdict = "OK" if sim >= 0.4 or db_short.lower() in vendor_name.lower() or vendor_name.lower() in db_name.lower() else "MISMATCH -- verify before use"
        print(f"{t:<8} {db_name:<28} {vendor_name:<28} {sim:<8.2f} {verdict}")
        if verdict.startswith("MISMATCH"):
            flagged.append((t, vendor_name))

    print(f"\nFlagged: {flagged}")
    print("This check is a proxy, not a guarantee -- it would not have caught a rename where the vendor's")
    print("name field itself was also stale in a way that still string-matches (not the case here: SPWR")
    print("failed outright, 'SunPower Inc.' vs the DB's actual name, below).")


def part2_google_alias():
    print("\n=== Part 2: GOOG alias confirmation (up to 1 vendor call) ===\n")
    progress = load_progress()
    events_path = RAW_DIR / "probe_events_GOOG.json"
    if not events_path.exists():
        print(f"Missing {events_path} -- run probe_google_cslr.py first."); return
    events = json.loads(events_path.read_text()).get("events", [])
    published = [e for e in events if e.get("is_published")]
    if not published:
        print("No published GOOG events found."); return

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""SELECT t.id, t."callDate"::date AS call_date, t."rawText" AS raw_text FROM "Transcript" t
                       JOIN "Ticker" tk ON t."tickerId" = tk.id WHERE tk.symbol = 'GOOGL'
                       ORDER BY t."callDate" DESC""")
        googl_rows = cur.fetchall()

    best = None
    for e in published:
        try:
            ed = datetime.datetime.fromisoformat(e["conference_date"].replace("Z", "+00:00")).date()
        except (ValueError, KeyError):
            continue
        for row in googl_rows:
            delta = abs((row["call_date"] - ed).days)
            if delta <= DATE_MATCH_TOLERANCE_DAYS and (best is None or delta < best[2]):
                best = (e, row, delta)

    if not best:
        print(f"No DB GOOGL callDate within {DATE_MATCH_TOLERANCE_DAYS}d of any published GOOG event. "
              f"GOOG events span {published[-1]['conference_date']} .. {published[0]['conference_date']}; "
              f"DB GOOGL rows span {googl_rows[-1]['call_date']} .. {googl_rows[0]['call_date']}." if googl_rows else "No DB GOOGL rows at all.")
        conn.close(); return

    event, db_row, delta = best
    print(f"Match: GOOG {event['year']}Q{event['quarter']} (conference_date {event['conference_date']}) "
          f"<-> DB GOOGL id {db_row['id']} (callDate {db_row['call_date']}), delta {delta}d")

    print("\nFetching GOOG transcript (1 call, level=2)...")
    status, data = vendor_get(progress, "transcript",
                               {"exchange": "NASDAQ", "symbol": "GOOG", "year": event["year"], "quarter": event["quarter"], "level": 2})
    if status != 200 or not isinstance(data, dict):
        print(f"HTTP {status}: {str(data)[:300]}"); conn.close(); return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"probe_GOOG_{event['year']}Q{event['quarter']}.json"
    raw_path.write_text(json.dumps(data, indent=2))

    db_text = db_row["raw_text"]
    v_text, v_turns = vendor_payload_to_text_and_turns(data)
    result = classify_sample(db_text, v_text, v_turns)
    result["db_word_count"] = len(db_text.split())
    result["vendor_word_count"] = len(v_text.split())
    print(f"\nclassification={result['classification']} ratio={result['similarity_ratio']} "
          f"turns={result['vendor_turn_count']} db_words={result['db_word_count']} vendor_words={result['vendor_word_count']}")
    print(f"DB tail:     ...{db_text[-200:]!r}")
    print(f"Vendor tail: ...{v_text[-200:]!r}")
    if result["classification"] in ("matches_closely", "summarized_but_complete") and result["similarity_ratio"] > 0.05:
        print("\n-> GOOG resolves to the same content as the DB's GOOGL transcripts. Alias is usable:")
        print("   treat GOOGL -> GOOG as a request-time substitution for this vendor, same idea as any")
        print("   dual-class-ticker alias table (GOOG/GOOGL, BRK.A/BRK.B), not a vendor-side rename fix.")
    else:
        print("\n-> Low similarity / no closing match -- do NOT assume GOOG==GOOGL from this alone; "
              "read both tails manually before using it.")
    conn.close()
    print(f"\nTotal calls used now: {progress['calls_used_total']}/{HARD_CALL_CAP} "
          f"(refund condition: {progress['calls_used_total']}/1000)")


if __name__ == "__main__":
    part1_name_gate()
    part2_google_alias()
