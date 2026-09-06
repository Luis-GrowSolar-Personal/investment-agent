#!/usr/bin/env python3
"""
driver.py -- ec-fidelity-benchmark-1
See prompts/ec_transcript_fidelity_benchmark_1.md for the full spec.

EarningsCall.biz (v2.api.earningscall.biz) fidelity benchmark against the
hand-copied DB corpus. Same sample, same decisive check, same classification
buckets as the Alpha Vantage run (analysis/av_fidelity_benchmark_2/driver.py),
with the fetch layer swapped and one structural change: the vendor's own
/events list is matched to DB callDate, so no quarter label is ever derived
from a call month.

Usage:
  python3 driver.py draw       # Step 0: build the target list (AV draw + pilot control set), no vendor calls
  python3 driver.py symbols    # Step 1a: one call -- resolve exchange + company-level coverage for all 15 tickers
  python3 driver.py events     # Step 1b: one call per ticker -- event-level coverage, callDate matching
  python3 driver.py fetch      # Step 2/3: transcript fetch + immediate classification (resumable, hard-capped)
  python3 driver.py reclassify # re-run classify_sample over saved raw/ files, 0 vendor calls
  python3 driver.py report     # Step 4: aggregate report, only once every target is fetched or recorded as a miss

Every vendor call is counted in progress.json['calls_used_total'] and refused
once HARD_CALL_CAP is reached. The refund clause is "under 1,000 API calls";
the cap here is deliberately far below it.
"""
import os, sys, json, time, difflib, hashlib, datetime
from pathlib import Path
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent.parent
load_dotenv(repo_root / ".env")

import psycopg2
import psycopg2.extras

RUN_ID = "ec-fidelity-benchmark-1"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
RAW_DIR = script_dir / "raw"
PROGRESS_PATH = STATE_DIR / "progress.json"
CELLS_PATH = STATE_DIR / "cells.jsonl"
FINDINGS_PATH = STATE_DIR / "findings.md"
PROMPT_PATH = repo_root / "prompts" / "ec_transcript_fidelity_benchmark_1.md"

# The AV run's draw is the sample. Read-only -- never written to from here.
AV_PROGRESS_PATH = repo_root / "analysis" / "data" / "run_state" / "av-fidelity-benchmark-2-stratified" / "progress.json"

ECB_API_KEY = os.environ["ECB_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]

BASE_URL = "https://v2.api.earningscall.biz"

HARD_CALL_CAP = 300            # total vendor calls this run may ever make; refund clause is <1,000
MIN_SPACING_SECONDS = 3.5      # Premium plan: 20 calls/min -> 3s; 3.5s is the margin
TRANSCRIPT_LEVEL = 2           # Premium: speaker-segmented. Falls back to 1 once, with a finding, if refused.
DATE_MATCH_TOLERANCE_DAYS = 3  # DB callDate vs vendor conference_date (UTC vs local can shift a day)

TIERS = {
    "megacap": ["AAPL", "GOOGL", "NVDA", "MSFT", "TSLA"],
    "large": ["AVGO", "AMD", "ORCL"],
    "mid": ["FSLR", "TTD"],
    "small_micro": ["QS", "AMPX", "ENVX", "EOSE", "RUN", "SPWR"],
}
TICKER_TIER = {t: tier for tier, ts in TIERS.items() for t in ts}
ALL_TICKERS = list(TICKER_TIER.keys())

# Pilot control set: the 7 (ticker, quarter) pairs benchmark_1 fetched from AV,
# excluded from the AV benchmark_2 draw. Included here on purpose: AMPX 2025Q3
# is the one confirmed AV truncation (Test 3), and SPWR's two quarters are the
# known no-outro convention. Labels are the AV run's call-month-bucket labels,
# used ONLY to locate the DB rows -- the vendor lookup goes through /events.
PILOT_CONTROL_PAIRS = [
    ("AMPX", "2025Q1"), ("AMPX", "2025Q2"), ("AMPX", "2025Q3"),
    ("EOSE", "2025Q1"), ("EOSE", "2025Q2"),
    ("SPWR", "2025Q1"), ("SPWR", "2025Q3"),
]

# Exchange index order from the vendor SDK (earningscall/exchanges.py,
# FALLBACK_EXCHANGES_IN_ORDER). Used to decode symbols-v2.txt.
EXCHANGES_IN_ORDER = ["NYSE", "NASDAQ", "AMEX", "TSX", "TSXV", "OTC", "LSE", "CBOE", "STO"]

# Fetch order: the decisive tier first, so a budget-limited session answers
# the question the AV run could not reach.
TIER_FETCH_ORDER = ["small_micro", "mid", "large", "megacap"]


# ----------------------------------------------------------------------------
# state
# ----------------------------------------------------------------------------

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return None


def save_progress(p):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(p, indent=2, default=str))


def append_finding(text):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(FINDINGS_PATH, "a") as f:
        f.write(text.rstrip() + "\n\n")


def append_cell(cell):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CELLS_PATH, "a") as f:
        f.write(json.dumps(cell, default=str) + "\n")


def quarter_label(call_date):
    """Same call-month bucket as the AV driver. Used only to (a) locate the
    pilot-control DB rows and (b) report, as a diagnostic, how the vendor's
    own year/quarter relates to it. Never used to build a vendor request."""
    m, y = call_date.month, call_date.year
    if m <= 3:
        return f"{y - 1}Q4"
    elif m <= 6:
        return f"{y}Q1"
    elif m <= 9:
        return f"{y}Q2"
    return f"{y}Q3"


def db_connect():
    return psycopg2.connect(DATABASE_URL)


def get_db_transcript(conn, transcript_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT "rawText" FROM "Transcript" WHERE id = %s', (transcript_id,))
        row = cur.fetchone()
        return row["rawText"] if row else None


# ----------------------------------------------------------------------------
# vendor HTTP -- every call goes through here and is counted
# ----------------------------------------------------------------------------

class CallBudgetExceeded(Exception):
    pass


def _count_call(progress, endpoint, params, status, note=None):
    progress["calls_used_total"] = progress.get("calls_used_total", 0) + 1
    progress.setdefault("call_log", []).append({
        "ts": now_iso(), "endpoint": endpoint,
        "params": {k: v for k, v in params.items() if k != "apikey"},
        "status": status, "note": note,
    })
    progress["last_call_ts"] = now_iso()
    save_progress(progress)


def _respect_spacing(progress):
    last = progress.get("last_call_ts")
    if not last:
        return
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last)).total_seconds()
    if since < MIN_SPACING_SECONDS:
        time.sleep(MIN_SPACING_SECONDS - since)


def vendor_get(progress, endpoint, params, expect_json=True):
    """Returns (http_status, payload). payload is parsed JSON, or raw text for
    non-JSON endpoints, or the error body string on 4xx/5xx. Counts the call
    BEFORE it is made, so a crash mid-request still leaves it counted.
    Never retries: a 429 is recorded and raised to the caller, which stops."""
    if progress.get("calls_used_total", 0) >= HARD_CALL_CAP:
        raise CallBudgetExceeded(f"HARD_CALL_CAP={HARD_CALL_CAP} reached; refusing further vendor calls")
    _respect_spacing(progress)
    q = dict(params)
    q["apikey"] = ECB_API_KEY
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "investment-agent ec-fidelity-benchmark-1"})
    _count_call(progress, endpoint, params, "sent")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read()
        status = e.code
    text = body.decode("utf-8", errors="replace")
    progress["call_log"][-1]["status"] = status
    save_progress(progress)
    if status == 429:
        append_finding(f"**429 rate-limited** on {endpoint} {params} at {now_iso()}. Stopped; no auto-retry.")
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


# ----------------------------------------------------------------------------
# Step 0 -- draw (no vendor calls)
# ----------------------------------------------------------------------------

def fetch_pilot_control_rows(conn):
    """Locate the 7 pilot-control DB rows by (ticker, call-month-bucket label)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT t.id AS transcript_id, tk.symbol AS ticker, t."callDate"::date AS call_date
            FROM "Transcript" t JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE tk.symbol = ANY(%s) ORDER BY tk.symbol, t."callDate"
            """, (["AMPX", "EOSE", "SPWR"],))
        rows = [dict(r) for r in cur.fetchall()]
    wanted = set(PILOT_CONTROL_PAIRS)
    out, seen = [], set()
    for r in rows:
        key = (r["ticker"], quarter_label(r["call_date"]))
        if key in wanted and key not in seen:
            seen.add(key)
            out.append({"transcript_id": r["transcript_id"], "ticker": r["ticker"],
                        "call_date": r["call_date"].isoformat(), "quarter": key[1],
                        "tier": TICKER_TIER[r["ticker"]], "source": "pilot_control"})
    missing = wanted - seen
    if missing:
        print(f"WARNING: pilot-control rows not found in DB for {sorted(missing)}")
    return out


def step0_draw():
    if not AV_PROGRESS_PATH.exists():
        print(f"AV run state not found at {AV_PROGRESS_PATH}; cannot reuse its draw.")
        return
    av = json.loads(AV_PROGRESS_PATH.read_text())
    av_drawn = av["drawn"]
    av_fetched = av.get("fetched", {})
    targets = []
    for d in av_drawn:
        item = dict(d)
        item["source"] = "av_draw"
        key = f"{d['ticker']}_{d['quarter']}"
        rec = av_fetched.get(key)
        # carry AV's per-cell result over, read-only, so the report can put the
        # two vendors side by side on the identical cells
        if rec and rec.get("status") == "classified":
            item["av_result"] = {k: rec.get(k) for k in
                                 ("classification", "similarity_ratio", "av_turn_count", "av_word_count", "db_word_count")}
        targets.append(item)

    conn = db_connect()
    pilot = fetch_pilot_control_rows(conn)
    conn.close()
    targets.extend(pilot)

    # sanity: no duplicate transcript ids
    ids = [t["transcript_id"] for t in targets]
    assert len(ids) == len(set(ids)), "duplicate transcript ids in target list"

    # fetch order: decisive tier first, pilot controls first within small/micro
    tier_rank = {t: i for i, t in enumerate(TIER_FETCH_ORDER)}
    targets.sort(key=lambda t: (tier_rank[t["tier"]], 0 if t["source"] == "pilot_control" else 1, t["ticker"], t["call_date"]))

    by_tier = {}
    for t in targets:
        by_tier[t["tier"]] = by_tier.get(t["tier"], 0) + 1
    print(f"Targets: {len(targets)} = {len(av_drawn)} from AV draw (seed {av.get('seed')}) + {len(pilot)} pilot controls")
    print(f"By tier: {by_tier}")
    print(f"AV cells already classified (side-by-side available): {sum(1 for t in targets if 'av_result' in t)}")

    progress = {
        "run_id": RUN_ID,
        "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest() if PROMPT_PATH.exists() else None,
        "driver_commit": None,   # filled in by the session at Step 0 hygiene
        "av_seed": av.get("seed"),
        "av_progress_path": str(AV_PROGRESS_PATH.relative_to(repo_root)),
        "targets": targets,
        "symbols": {},           # ticker -> {exchange, name, sector, industry} or None
        "events": {},            # ticker -> [{year, quarter, conference_date}]
        "matches": {},           # transcript_id -> {year, quarter, conference_date, delta_days} or None
        "fetched": {},           # transcript_id -> record
        "calls_used_total": 0,
        "call_log": [],
        "last_call_ts": None,
        "hard_call_cap": HARD_CALL_CAP,
        "transcript_level": TRANSCRIPT_LEVEL,
        "steps": {"0_draw": "done", "1a_symbols": "pending", "1b_events": "pending",
                  "2_fetch": "pending", "3_report": "pending"},
        "next_action": "run `symbols` (1 vendor call)",
        "notes": [],
    }
    save_progress(progress)
    append_finding(f"## Step 0 -- draw ({now_iso()})\n\n{len(targets)} targets: {len(av_drawn)} reused from "
                   f"`{progress['av_progress_path']}` → `drawn` (seed {av.get('seed')}), plus {len(pilot)} pilot "
                   f"controls. By tier: {by_tier}. No vendor calls made.")
    print(f"progress.json written to {PROGRESS_PATH}")


# ----------------------------------------------------------------------------
# Step 1a -- symbols (1 call): exchange resolution + company-level coverage
# ----------------------------------------------------------------------------

def step1a_symbols():
    progress = load_progress()
    if progress is None:
        print("No progress.json -- run `draw` first."); return
    status, text = vendor_get(progress, "symbols-v2.txt", {}, expect_json=False)
    if status != 200:
        print(f"symbols-v2.txt returned HTTP {status}: {str(text)[:300]}"); return
    found = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            exch = EXCHANGES_IN_ORDER[int(parts[0])]
        except (ValueError, IndexError):
            exch = f"UNKNOWN({parts[0]})"
        sym = parts[1].upper()
        if sym in TICKER_TIER:
            found.setdefault(sym, []).append({"exchange": exch, "name": parts[2],
                                              "sector_idx": parts[3] if len(parts) > 3 else None,
                                              "industry_idx": parts[4] if len(parts) > 4 else None})
    for t in ALL_TICKERS:
        entries = found.get(t)
        if not entries:
            progress["symbols"][t] = None
            print(f"  {t}: NOT IN VENDOR SYMBOL LIST (company-level coverage miss)")
            append_finding(f"**Company-level coverage miss**: {t} (tier {TICKER_TIER[t]}) absent from symbols-v2.txt ({now_iso()})")
        else:
            if len(entries) > 1:
                print(f"  {t}: listed on multiple exchanges {entries} -- using the first, flag for manual check")
                append_finding(f"**Ambiguous exchange** for {t}: {entries}. Using {entries[0]['exchange']}. ({now_iso()})")
            progress["symbols"][t] = entries[0]
            print(f"  {t}: {entries[0]['exchange']}  {entries[0]['name']}")
    progress["steps"]["1a_symbols"] = "done"
    progress["next_action"] = "run `events` (1 vendor call per covered ticker)"
    save_progress(progress)
    print(f"\nCalls used so far: {progress['calls_used_total']}/{HARD_CALL_CAP}")


# ----------------------------------------------------------------------------
# Step 1b -- events (1 call per ticker): event-level coverage + callDate match
# ----------------------------------------------------------------------------

def _parse_conf_date(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def step1b_events():
    progress = load_progress()
    if progress is None:
        print("No progress.json -- run `draw` first."); return
    if progress["steps"]["1a_symbols"] != "done":
        print("Run `symbols` first."); return
    for t in ALL_TICKERS:
        if t in progress["events"]:
            print(f"  {t}: events already fetched ({len(progress['events'][t])}), skipping")
            continue
        info = progress["symbols"].get(t)
        if not info:
            progress["events"][t] = []
            print(f"  {t}: skipped (not in symbol list)")
            continue
        try:
            status, data = vendor_get(progress, "events", {"exchange": info["exchange"], "symbol": t})
        except CallBudgetExceeded as e:
            print(e); save_progress(progress); return
        if status != 200 or not isinstance(data, dict):
            print(f"  {t}: events HTTP {status}: {str(data)[:200]}")
            progress["events"][t] = []
            append_finding(f"**Events call failed** for {t}: HTTP {status} {str(data)[:200]} ({now_iso()})")
            save_progress(progress)
            continue
        evs = [{"year": e.get("year"), "quarter": e.get("quarter"), "conference_date": e.get("conference_date")}
               for e in data.get("events", [])]
        progress["events"][t] = evs
        dates = sorted(d for d in (_parse_conf_date(e["conference_date"]) for e in evs) if d)
        print(f"  {t} ({info['exchange']}): {len(evs)} events, {dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}")
        save_progress(progress)

    # match every target to a vendor event by conference_date
    n_match = n_miss = 0
    label_disagreements = []
    for tgt in progress["targets"]:
        tid = str(tgt["transcript_id"])
        if tid in progress["matches"]:
            continue
        call_date = datetime.date.fromisoformat(tgt["call_date"])
        best = None
        for e in progress["events"].get(tgt["ticker"], []):
            d = _parse_conf_date(e["conference_date"])
            if d is None:
                continue
            delta = abs((d - call_date).days)
            if delta <= DATE_MATCH_TOLERANCE_DAYS and (best is None or delta < best["delta_days"]):
                best = {"year": e["year"], "quarter": e["quarter"], "conference_date": e["conference_date"], "delta_days": delta}
        progress["matches"][tid] = best
        if best:
            n_match += 1
            vendor_label = f"{best['year']}Q{best['quarter']}"
            if vendor_label != tgt["quarter"]:
                label_disagreements.append((tgt["ticker"], tgt["call_date"], tgt["quarter"], vendor_label))
        else:
            n_miss += 1
            append_finding(f"**Event-level coverage miss**: {tgt['ticker']} call {tgt['call_date']} (bucket label "
                           f"{tgt['quarter']}, tier {tgt['tier']}, transcript id {tid}) -- no vendor event within "
                           f"±{DATE_MATCH_TOLERANCE_DAYS} days ({now_iso()})")
    progress["steps"]["1b_events"] = "done"
    progress["next_action"] = "run `fetch` (one transcript call per matched target, small/micro first)"
    save_progress(progress)
    print(f"\nMatched {n_match} targets to a vendor event; {n_miss} event-level coverage misses.")
    print(f"Vendor (year,quarter) disagrees with the call-month-bucket label on {len(label_disagreements)} targets "
          f"(diagnostic only -- the vendor label is the one used for the request):")
    for row in label_disagreements[:40]:
        print(f"    {row[0]} call {row[1]}: bucket {row[2]} vs vendor {row[3]}")
    if label_disagreements:
        append_finding("## Label diagnostic (Step 1b)\n\nVendor (year, quarter) vs call-month bucket label disagreed on "
                       f"{len(label_disagreements)}/{n_match} matched targets. First 40: {label_disagreements[:40]}. "
                       "This is expected wherever the vendor uses the company's fiscal quarter (AAPL, MSFT, NVDA, AVGO, ORCL "
                       "are the obvious cases). Not a defect on either side; recorded because it is the trap the AV run hit.")
    print(f"Calls used so far: {progress['calls_used_total']}/{HARD_CALL_CAP}")


# ----------------------------------------------------------------------------
# classification -- copied from analysis/av_fidelity_benchmark_2/driver.py
# (that directory is off-limits to modification; copied, not imported, so
# this driver has no runtime dependency on the AV driver's env requirements)
# ----------------------------------------------------------------------------

CLOSING_KEYWORDS = [
    "you may now disconnect", "you may disconnect", "concludes today", "concludes our",
    "this concludes", "does conclude", "have a good day", "thank you for joining",
    "thank you for attending", "thanks again, everybody", "appreciate your participation",
]


def similarity_ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def closing_match(text):
    low = text.lower()
    return any(k in low for k in CLOSING_KEYWORDS)


def classify_sample(db_text, vendor_text, vendor_turns):
    """vendor_turns: list of {'speaker':..., 'title':..., 'content':...} -- same
    shape the AV driver used, so the logic is byte-for-byte the AV run's."""
    ratio = similarity_ratio(db_text, vendor_text)
    turn_count = len(vendor_turns)
    v_closing = closing_match(vendor_text)
    truncated = False
    reason = ""
    if vendor_turns:
        last_content = (vendor_turns[-1].get("content") or "").strip()
        last_content_low = last_content.lower()
        handoff_markers = ["turn the call back over to", "turn the call over to", "closing remarks", "for his closing", "for her closing"]
        for m in handoff_markers:
            idx = last_content_low.find(m)
            if idx != -1 and (len(last_content) - (idx + len(m))) <= 80 and not v_closing:
                truncated = True
                reason = "vendor's last turn hands off to a named speaker for closing remarks that never appear"
                break
    if not truncated:
        if v_closing:
            classification = "matches_closely" if ratio >= 0.5 else "summarized_but_complete"
        else:
            db_closing = closing_match(db_text)
            if not db_closing:
                classification = "matches_closely" if ratio >= 0.5 else "summarized_but_complete"
                reason = reason or "neither side has an operator sign-off (officer-led close convention, per Test 3)"
            else:
                classification = "possibly_truncated_needs_manual_check"
                reason = reason or "DB has an operator sign-off the vendor text lacks -- flag for manual tail read"
    else:
        classification = "truncated"
    return {
        "similarity_ratio": round(ratio, 4),
        "vendor_turn_count": turn_count,
        "vendor_closing_match": v_closing,
        "classification": classification,
        "reason": reason,
    }


def vendor_payload_to_text_and_turns(payload):
    """Level 2: speakers[] with speaker / speaker_info{name,title} / text.
    Level 1: text (+ prepared_remarks / questions_and_answers). Returns the
    AV-shaped (text, turns) so classify_sample is unchanged."""
    speakers = payload.get("speakers")
    if speakers:
        turns, lines = [], []
        for s in speakers:
            info = s.get("speaker_info") or {}
            name = info.get("name") or s.get("speaker") or "Unknown"
            title = info.get("title") or ""
            content = s.get("text") or ""
            turns.append({"speaker": name, "title": title, "content": content})
            lines.append(f"{name} ({title}): {content}")
        return "\n\n".join(lines), turns
    text = payload.get("text") or ""
    return text, ([{"speaker": "?", "title": "", "content": text}] if text else [])


# ----------------------------------------------------------------------------
# Step 2 -- transcript fetch + immediate classification
# ----------------------------------------------------------------------------

def step2_fetch(max_calls_this_invocation=None):
    progress = load_progress()
    if progress is None:
        print("No progress.json -- run `draw` first."); return
    if progress["steps"]["1b_events"] != "done":
        print("Run `events` first."); return
    progress["steps"]["2_fetch"] = "in_progress"
    level = progress.get("transcript_level", TRANSCRIPT_LEVEL)
    conn = db_connect()
    n_this = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        for tgt in progress["targets"]:
            tid = str(tgt["transcript_id"])
            if tid in progress["fetched"]:
                continue
            if max_calls_this_invocation and n_this >= max_calls_this_invocation:
                print(f"Reached per-invocation limit {max_calls_this_invocation}; stopping cleanly."); break
            match = progress["matches"].get(tid)
            cell_key = f"{tgt['ticker']}_{tgt['quarter']}_id{tid}"
            if not match:
                progress["fetched"][tid] = {"status": "coverage_miss_event", "ts": now_iso(), "tier": tgt["tier"], "source": tgt["source"]}
                append_cell({"cell_key": cell_key, "params": tgt, "status": "coverage_miss_event"})
                save_progress(progress)
                continue
            info = progress["symbols"][tgt["ticker"]]
            params = {"exchange": info["exchange"], "symbol": tgt["ticker"],
                      "year": match["year"], "quarter": match["quarter"], "level": level}
            print(f"\n=== {cell_key} (tier {tgt['tier']}, {tgt['source']}) -> {params} ===")
            status, data = vendor_get(progress, "transcript", params)
            n_this += 1

            if status in (402, 403) and level != 1:
                # plan does not include this level -- fall back ONCE, for the whole run, with a finding
                append_finding(f"**Level {level} refused (HTTP {status})** on {cell_key}: {str(data)[:200]}. "
                               f"Falling back to level 1 for the rest of the run. ({now_iso()})")
                print(f"  level {level} refused (HTTP {status}); switching run to level 1 and retrying this cell once")
                level = 1
                progress["transcript_level"] = 1
                save_progress(progress)
                status, data = vendor_get(progress, "transcript", {**params, "level": 1})
                n_this += 1

            if status == 404 or (isinstance(data, dict) and not (data.get("speakers") or data.get("text"))):
                progress["fetched"][tid] = {"status": "coverage_miss_transcript", "ts": now_iso(), "http": status,
                                            "tier": tgt["tier"], "source": tgt["source"], "vendor_params": params}
                append_cell({"cell_key": cell_key, "params": tgt, "status": "coverage_miss_transcript", "http": status,
                             "raw": data if isinstance(data, dict) else str(data)[:500]})
                append_finding(f"**Transcript-level coverage miss**: {cell_key} (tier {tgt['tier']}) -- event exists "
                               f"({match['conference_date']}) but /transcript returned HTTP {status} / empty. ({now_iso()})")
                print(f"  transcript miss (HTTP {status})")
                save_progress(progress)
                continue
            if status != 200 or not isinstance(data, dict):
                progress["fetched"][tid] = {"status": "error", "ts": now_iso(), "http": status, "body": str(data)[:300],
                                            "tier": tgt["tier"], "source": tgt["source"], "vendor_params": params}
                append_cell({"cell_key": cell_key, "params": tgt, "status": "error", "http": status, "body": str(data)[:300]})
                print(f"  error HTTP {status}: {str(data)[:200]}")
                save_progress(progress)
                continue

            raw_path = RAW_DIR / f"{cell_key}.json"
            raw_path.write_text(json.dumps(data, indent=2))
            db_text = get_db_transcript(conn, tgt["transcript_id"])
            if not db_text:
                progress["fetched"][tid] = {"status": "fetched_no_db_text", "ts": now_iso(), "raw_path": str(raw_path.relative_to(repo_root))}
                append_cell({"cell_key": cell_key, "params": tgt, "status": "fetched_no_db_text"})
                save_progress(progress)
                continue
            v_text, v_turns = vendor_payload_to_text_and_turns(data)
            result = classify_sample(db_text, v_text, v_turns)
            result["db_word_count"] = len(db_text.split())
            result["vendor_word_count"] = len(v_text.split())
            result["word_ratio_vendor_over_db"] = round(result["vendor_word_count"] / max(1, result["db_word_count"]), 4)
            result["has_speaker_names"] = bool(data.get("speakers")) and any(
                (s.get("speaker_info") or {}).get("name") for s in data.get("speakers", []))
            result["has_prepared_qa_split"] = bool(data.get("prepared_remarks")) and bool(data.get("questions_and_answers"))
            print(f"  classification={result['classification']} ratio={result['similarity_ratio']} "
                  f"turns={result['vendor_turn_count']} db_words={result['db_word_count']} vendor_words={result['vendor_word_count']} "
                  f"word_ratio={result['word_ratio_vendor_over_db']}")
            rec = {"status": "classified", "ts": now_iso(), "tier": tgt["tier"], "source": tgt["source"],
                   "transcript_id": tgt["transcript_id"], "vendor_params": params, "level_used": level,
                   "raw_path": str(raw_path.relative_to(repo_root)), **result}
            if "av_result" in tgt:
                rec["av_result"] = tgt["av_result"]
            progress["fetched"][tid] = rec
            append_cell({"cell_key": cell_key, "params": tgt, "status": "classified", "result": result, "level": level})
            if result["classification"] in ("truncated", "possibly_truncated_needs_manual_check"):
                append_finding(f"**{result['classification']}**: {cell_key} (tier {tgt['tier']}) -- ratio={result['similarity_ratio']}, "
                               f"turns={result['vendor_turn_count']}, word_ratio={result['word_ratio_vendor_over_db']}, reason: {result['reason']}. "
                               f"DB tail: ...{db_text[-300:]!r} | vendor tail: ...{v_text[-300:]!r} ({now_iso()})")
            save_progress(progress)
    except (CallBudgetExceeded, RuntimeError) as e:
        print(f"\nSTOPPED: {e}")
    finally:
        conn.close()
        remaining = sum(1 for t in progress["targets"] if str(t["transcript_id"]) not in progress["fetched"])
        if remaining == 0:
            progress["steps"]["2_fetch"] = "done"
            progress["next_action"] = "run `report`"
        else:
            progress["next_action"] = f"run `fetch` again ({remaining} targets remaining)"
        save_progress(progress)
        print(f"\nThis invocation: {n_this} transcript calls. Total calls used: {progress['calls_used_total']}/{HARD_CALL_CAP}. "
              f"Targets remaining: {remaining}.")


def step_reclassify():
    progress = load_progress()
    if progress is None:
        print("No progress.json."); return
    conn = db_connect()
    changed = []
    for tid, rec in progress["fetched"].items():
        if rec.get("status") != "classified":
            continue
        data = json.loads((repo_root / rec["raw_path"]).read_text())
        v_text, v_turns = vendor_payload_to_text_and_turns(data)
        db_text = get_db_transcript(conn, rec["transcript_id"])
        new = classify_sample(db_text, v_text, v_turns)
        if new["classification"] != rec.get("classification"):
            changed.append((tid, rec.get("classification"), new["classification"]))
            rec.update(new)
    conn.close()
    save_progress(progress)
    if changed:
        append_finding("## Reclassification (" + now_iso() + ")\n\n0 vendor calls. " +
                       "\n".join(f"- id {t}: {o} -> {n}" for t, o, n in changed))
    print(f"Reclassified {len(changed)} samples: {changed}")


# ----------------------------------------------------------------------------
# Step 3 -- report
# ----------------------------------------------------------------------------

def wilson_ci(successes, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / denom
    return (p, max(0.0, center - margin), min(1.0, center + margin))


def step3_report():
    progress = load_progress()
    if progress is None:
        print("No progress.json."); return
    remaining = [t for t in progress["targets"] if str(t["transcript_id"]) not in progress["fetched"]]
    if remaining:
        print(f"Not complete: {len(remaining)} targets remain. Run `fetch` again."); return

    out = {"overall": {}, "by_tier": {}, "by_source": {}, "side_by_side_with_av": [], "company_coverage": progress["symbols"]}
    def summarize(recs):
        classified = [r for r in recs if r.get("status") == "classified"]
        trunc = sum(1 for r in classified if r["classification"] == "truncated")
        manual = sum(1 for r in classified if r["classification"] == "possibly_truncated_needs_manual_check")
        p, lo, hi = wilson_ci(trunc, len(classified))
        return {
            "n_targets": len(recs), "n_classified": len(classified),
            "truncated": trunc, "needs_manual_check": manual,
            "matches_closely": sum(1 for r in classified if r["classification"] == "matches_closely"),
            "summarized_but_complete": sum(1 for r in classified if r["classification"] == "summarized_but_complete"),
            "coverage_miss_event": sum(1 for r in recs if r.get("status") == "coverage_miss_event"),
            "coverage_miss_transcript": sum(1 for r in recs if r.get("status") == "coverage_miss_transcript"),
            "errors": sum(1 for r in recs if r.get("status") == "error"),
            "truncation_rate": p, "wilson95": [lo, hi],
            "median_similarity_ratio": (sorted(r["similarity_ratio"] for r in classified)[len(classified) // 2] if classified else None),
            "median_word_ratio": (sorted(r["word_ratio_vendor_over_db"] for r in classified)[len(classified) // 2] if classified else None),
        }
    all_recs = [progress["fetched"][str(t["transcript_id"])] for t in progress["targets"]]
    out["overall"] = summarize(all_recs)
    for tier in TIERS:
        out["by_tier"][tier] = summarize([r for r in all_recs if r.get("tier") == tier])
    for src in ("av_draw", "pilot_control"):
        out["by_source"][src] = summarize([r for r in all_recs if r.get("source") == src])
    for t in progress["targets"]:
        rec = progress["fetched"][str(t["transcript_id"])]
        if rec.get("status") == "classified" and rec.get("av_result"):
            out["side_by_side_with_av"].append({
                "ticker": t["ticker"], "quarter": t["quarter"], "transcript_id": t["transcript_id"],
                "ec": {k: rec.get(k) for k in ("classification", "similarity_ratio", "vendor_turn_count", "vendor_word_count")},
                "av": rec["av_result"],
            })
    out["calls_used_total"] = progress["calls_used_total"]
    (STATE_DIR / "aggregate_report.json").write_text(json.dumps(out, indent=2))

    o = out["overall"]
    print(f"Overall: {o['truncated']}/{o['n_classified']} truncated ({o['truncation_rate']*100:.1f}%, Wilson 95% "
          f"[{o['wilson95'][0]*100:.1f}%, {o['wilson95'][1]*100:.1f}%]); needs_manual={o['needs_manual_check']}; "
          f"event misses={o['coverage_miss_event']}, transcript misses={o['coverage_miss_transcript']}, errors={o['errors']}")
    for tier, s in out["by_tier"].items():
        print(f"  {tier}: {s['truncated']}/{s['n_classified']} truncated (CI [{s['wilson95'][0]*100:.1f}%,{s['wilson95'][1]*100:.1f}%]); "
              f"misses event/transcript {s['coverage_miss_event']}/{s['coverage_miss_transcript']}; "
              f"median ratio {s['median_similarity_ratio']}, median word ratio {s['median_word_ratio']}")
    print(f"Side-by-side cells with AV: {len(out['side_by_side_with_av'])}")
    print(f"Calls used: {out['calls_used_total']}/{HARD_CALL_CAP}")
    progress["steps"]["3_report"] = "done"
    progress["next_action"] = "write wrap-up"
    save_progress(progress)
    print(f"Written to {STATE_DIR / 'aggregate_report.json'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "draw":
        step0_draw()
    elif cmd == "symbols":
        step1a_symbols()
    elif cmd == "events":
        step1b_events()
    elif cmd == "fetch":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        step2_fetch(n)
    elif cmd == "reclassify":
        step_reclassify()
    elif cmd == "report":
        step3_report()
    else:
        print(f"Unknown command {cmd}")
