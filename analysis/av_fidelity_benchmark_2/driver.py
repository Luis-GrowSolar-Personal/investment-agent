#!/usr/bin/env python3
"""
driver.py -- av-fidelity-benchmark-2-stratified
See prompts/av_transcript_fidelity_benchmark_2_stratified.md for the full spec.

Usage:
  python3 driver.py draw      # Step 0: stratified draw from the existing corpus (idempotent, seeded)
  python3 driver.py fetch     # Step 1: one day's worth of AV fetches (<=20 calls, >=70s apart)
  python3 driver.py report    # Step 2: aggregate report (only once Step 1's drawn list is fully processed)
"""
import os, sys, json, time, random, difflib, hashlib, datetime, re
from pathlib import Path
from dotenv import load_dotenv
import urllib.request, urllib.parse

script_dir = Path(__file__).parent.resolve()
repo_root = script_dir.parent.parent
load_dotenv(repo_root / ".env")

import psycopg2
import psycopg2.extras

RUN_ID = "av-fidelity-benchmark-2-stratified"
STATE_DIR = repo_root / "analysis" / "data" / "run_state" / RUN_ID
RAW_DIR = script_dir / "raw"
PROGRESS_PATH = STATE_DIR / "progress.json"
CELLS_PATH = STATE_DIR / "cells.jsonl"
FINDINGS_PATH = STATE_DIR / "findings.md"

AV_API_KEY = os.environ["AV_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]


def enumerate_av_keys():
    """AV_API_KEY, AV_API_KEY2, AV_API_KEY3, ... generic enumeration, no
    hardcoded count, per prompt's Update (after Day 1)."""
    keys = {"AV_API_KEY": os.environ["AV_API_KEY"]}
    i = 2
    while True:
        name = f"AV_API_KEY{i}"
        val = os.environ.get(name)
        if not val:
            break
        keys[name] = val
        i += 1
    return keys

TIERS = {
    "megacap": ["AAPL", "GOOGL", "NVDA", "MSFT", "TSLA"],
    "large": ["AVGO", "AMD", "ORCL"],
    "mid": ["FSLR", "TTD"],
    "small_micro": ["QS", "AMPX", "ENVX", "EOSE", "RUN"],
}
TICKER_TIER = {t: tier for tier, ts in TIERS.items() for t in ts}

EXCLUDE_PAIRS = {
    ("AMPX", "2025Q1"), ("AMPX", "2025Q2"), ("AMPX", "2025Q3"),
    ("EOSE", "2025Q1"), ("EOSE", "2025Q2"),
}

TARGET_ALLOCATION = {"megacap": 52, "large": 51, "mid": 45, "small_micro": 52}
SEED = 20260905

DAILY_CALL_CAP = 20
MIN_SPACING_SECONDS = 70
QUOTA_RESET_HOURS = 24.0  # conservative: full 24h since last call of prior day's batch


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def quarter_label(call_date):
    """AV quarter label for the fiscal quarter a call reports on, by
    call-month bucket. Validated exactly against every known-correct
    label from benchmark_1 and Test 3 (AMPX 2025-05-08/08-07/11-06 ->
    2025Q1/Q2/Q3; EOSE 2025-05-06/07-31 -> 2025Q1/Q2; SPWR 2025-04-30/
    10-21 -> 2025Q1/Q3). An earlier draft used a flat 45-day offset,
    which collapses a company's Jan-Mar (prior-year-Q4) call and its
    Apr-Jun (current-year-Q1) call onto the same label whenever both
    occur in the same calendar year -- confirmed to actually happen in
    this corpus (FSLR, TTD, QS, ENVX, RUN each have both). Caught and
    fixed before any AV calls were spent, by re-running Step 0's draw."""
    m, y = call_date.month, call_date.year
    if m <= 3:
        return f"{y - 1}Q4"
    elif m <= 6:
        return f"{y}Q1"
    elif m <= 9:
        return f"{y}Q2"
    else:
        return f"{y}Q3"


def db_connect():
    return psycopg2.connect(DATABASE_URL)


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


def fetch_pool(conn):
    tickers = list(TICKER_TIER.keys())
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT t.id AS transcript_id, tk.symbol AS ticker, t."callDate"::date AS call_date
            FROM "Transcript" t
            JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE tk.symbol = ANY(%s)
            ORDER BY tk.symbol, t."callDate"
            """,
            (tickers,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    pool = []
    seen_keys = {}
    dupes_dropped = []
    for r in rows:
        q = quarter_label(r["call_date"])
        if (r["ticker"], q) in EXCLUDE_PAIRS:
            continue
        key = (r["ticker"], q)
        if key in seen_keys:
            # true DB-side duplicate row for the same reported quarter (confirmed
            # for FSLR 2023Q4, ids 280/284: identical callDate, identical title,
            # identical rawText length -- a genuine duplicate Transcript record,
            # not a quarter-mapping artifact). Keep the lower id, drop the rest,
            # so we don't spend two AV calls to compare against what is really
            # one DB transcript.
            dupes_dropped.append((r["transcript_id"], key, seen_keys[key]))
            continue
        seen_keys[key] = r["transcript_id"]
        pool.append({
            "transcript_id": r["transcript_id"],
            "ticker": r["ticker"],
            "call_date": r["call_date"].isoformat(),
            "quarter": q,
            "tier": TICKER_TIER[r["ticker"]],
        })
    if dupes_dropped:
        print(f"NOTE: dropped {len(dupes_dropped)} true DB-duplicate row(s) from the pool: {dupes_dropped}")
    return pool


def step0_draw():
    conn = db_connect()
    pool = fetch_pool(conn)
    conn.close()

    by_tier = {}
    for item in pool:
        by_tier.setdefault(item["tier"], []).append(item)

    print("Pool by tier (re-verified against live DB):")
    for tier in TIERS:
        print(f"  {tier}: {len(by_tier.get(tier, []))} available")

    # recompute allocation if pool sizes differ from the prompt's expectation
    total_target = sum(TARGET_ALLOCATION.values())
    allocation = dict(TARGET_ALLOCATION)
    expected_avail = {"megacap": 114, "large": 67, "mid": 45, "small_micro": 97}
    actual_avail = {t: len(by_tier.get(t, [])) for t in TIERS}
    if actual_avail != expected_avail:
        print(f"NOTE: pool sizes changed since 2026-09-05: {actual_avail} vs expected {expected_avail}")
        print("Recomputing allocation: cap each tier at its pool, spread remainder evenly.")
        allocation = {}
        remaining_target = total_target
        remaining_tiers = list(TIERS.keys())
        # first pass: cap at pool
        capped = {t: min(TARGET_ALLOCATION[t], actual_avail[t]) for t in TIERS}
        shortfall = total_target - sum(capped.values())
        if shortfall > 0:
            # spread shortfall evenly across tiers with headroom
            headroom = {t: actual_avail[t] - capped[t] for t in TIERS}
            while shortfall > 0 and any(h > 0 for h in headroom.values()):
                for t in TIERS:
                    if shortfall <= 0:
                        break
                    if headroom[t] > 0:
                        capped[t] += 1
                        headroom[t] -= 1
                        shortfall -= 1
        allocation = capped

    print(f"Target allocation: {allocation}")
    print(f"Seed: {SEED}")

    rng = random.Random(SEED)
    drawn = []
    for tier, n in allocation.items():
        candidates = by_tier.get(tier, [])[:]
        rng.shuffle(candidates)
        picked = candidates[:n]
        drawn.extend(picked)

    print(f"Drawn: {len(drawn)} total")
    for tier in TIERS:
        tier_drawn = [d for d in drawn if d["tier"] == tier]
        print(f"  {tier}: {len(tier_drawn)}")
        for d in sorted(tier_drawn, key=lambda x: (x["ticker"], x["quarter"])):
            print(f"    {d['ticker']} {d['quarter']} (id {d['transcript_id']}, call {d['call_date']})")

    progress = {
        "run_id": RUN_ID,
        "prompt_sha256": hashlib.sha256(
            (repo_root / "prompts" / "av_transcript_fidelity_benchmark_2_stratified.md").read_bytes()
        ).hexdigest(),
        "seed": SEED,
        "pool_sizes": actual_avail if actual_avail != expected_avail else expected_avail,
        "allocation": allocation,
        "drawn": drawn,
        "fetched": {},   # key: f"{ticker}_{quarter}" -> {status, transcript_id, call_ts}
        "calls_used_total": 0,
        "daily_batches": [],  # [{date, calls_used, first_call_ts, last_call_ts}]
        "steps": {
            "0_draw": "done",
            "1_fetch": "in_progress",
            "2_report": "pending",
        },
        "notes": [],
    }
    save_progress(progress)
    append_finding(
        f"## Step 0 -- draw ({now_iso()})\n\n"
        f"Pool sizes: {actual_avail}. Allocation: {allocation}. Seed {SEED}. "
        f"{len(drawn)} items drawn, saved to progress.json['drawn']."
    )
    print(f"\nprogress.json written to {PROGRESS_PATH}")


AV_URL = "https://www.alphavantage.co/query"


def av_fetch(ticker, quarter, api_key):
    params = {"function": "EARNINGS_CALL_TRANSCRIPT", "symbol": ticker, "quarter": quarter, "apikey": api_key}
    url = AV_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read()
    data = json.loads(body)
    return data


def is_rate_limited(data):
    # BUG FIXED (found during Day 2): AV's actual field name is "Information"
    # (capital I) or "Note" -- `"information" in data` is a case-sensitive dict
    # KEY lookup, not a substring search, so it never matched and every real
    # rate-limit response ("We have detected your API key as X and our
    # standard API rate limit is 25 requests per day...") silently fell through
    # to the empty-transcript coverage-miss branch. Confirmed 175/175 of Day 2's
    # "coverage_miss" records were actually this exact message, not genuine
    # AV data gaps. Fixed by matching on the dict's own keys directly.
    blob = " ".join(str(v) for v in data.values()).lower()
    if "rate limit" in blob or "frequency" in blob or "requests per day" in blob or "premium" in blob:
        return True
    return False


CLOSING_KEYWORDS = [
    "you may now disconnect", "you may disconnect", "concludes today", "concludes our",
    "this concludes", "does conclude", "have a good day", "thank you for joining",
    "thank you for attending", "thanks again, everybody", "appreciate your participation",
]


def av_transcript_to_text_and_turns(av_json):
    entries = av_json.get("transcript", [])
    lines = []
    for e in entries:
        speaker = e.get("speaker", "Unknown")
        title = e.get("title", "")
        content = e.get("content", "")
        lines.append(f"{speaker} ({title}): {content}")
    text = "\n\n".join(lines)
    return text, entries


def get_db_transcript(conn, transcript_id):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT "rawText" FROM "Transcript" WHERE id = %s', (transcript_id,))
        row = cur.fetchone()
        return row["rawText"] if row else None


def similarity_ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def closing_match(text):
    low = text.lower()
    return any(k in low for k in CLOSING_KEYWORDS)


def classify_sample(db_text, av_text, av_entries):
    ratio = similarity_ratio(db_text, av_text)
    turn_count = len(av_entries)
    av_closing = closing_match(av_text)
    db_tail = db_text[-600:]
    av_tail = av_text[-600:]
    # decisive check: does DB's tail content appear (approximately) beyond where AV stops?
    # Heuristic: find the longest suffix of av_text that is a substring-ish prefix match
    # within db_text; if db_text continues meaningfully past av's last matched content,
    # and av's last turn hands off to a named speaker without delivering their remarks,
    # classify truncated. This mirrors Test 3's manual method, automated:
    truncated = False
    reason = ""
    if av_entries:
        last_content = (av_entries[-1].get("content") or "").strip()
        last_content_low = last_content.lower()
        handoff_markers = ["turn the call back over to", "turn the call over to", "closing remarks", "for his closing", "for her closing"]
        # A handoff phrase is only evidence of truncation if nothing of substance
        # follows it within the same turn -- e.g. NVDA 2022Q3's AV transcript says
        # "...turn over to Jensen for closing remarks. Well, I think we just heard
        # the closing remarks. Thank you..." and continues for 200+ more chars,
        # resolving the handoff in the same breath. Only flag when the marker sits
        # near the literal end of the turn's content (<=80 trailing chars).
        for m in handoff_markers:
            idx = last_content_low.find(m)
            if idx != -1 and (len(last_content) - (idx + len(m))) <= 80 and not av_closing:
                truncated = True
                reason = "AV's last turn hands off to a named speaker for closing remarks that never appear"
                break
    if not truncated:
        if av_closing:
            classification = "matches_closely" if ratio >= 0.5 else "summarized_but_complete"
        else:
            # no closing keyword on AV side -- check DB side: if DB also lacks a closing
            # keyword and DB's own tail content appears verbatim in AV's tail, it's a
            # real no-outro convention, not truncation.
            db_closing = closing_match(db_text)
            if not db_closing:
                classification = "matches_closely" if ratio >= 0.5 else "summarized_but_complete"
                reason = reason or "neither side has an operator sign-off (officer-led close convention, per Test 3)"
            else:
                classification = "possibly_truncated_needs_manual_check"
                reason = reason or "DB has an operator sign-off AV lacks -- flag for manual tail read"
    else:
        classification = "truncated"
    return {
        "similarity_ratio": round(ratio, 4),
        "av_turn_count": turn_count,
        "av_closing_match": av_closing,
        "classification": classification,
        "reason": reason,
    }


def migrate_to_key_usage(progress):
    """One-time migration from the single-key daily_batches list (Day 1) to
    per-key accounting, per the prompt's Update (after Day 1). Day 1's batch
    (progress['daily_batches'], recorded against the default AV_API_KEY) is
    preserved as-is -- not re-fetched, not discarded."""
    if "key_usage" in progress:
        return progress
    key_usage = {}
    old_batches = progress.get("daily_batches", [])
    if old_batches:
        last = old_batches[-1]
        key_usage["AV_API_KEY"] = {
            "batch_date": last["date"],
            "calls_today": last["calls_used"],
            "last_call_ts": last["last_call_ts"],
            "disabled": False,
            "disabled_reason": None,
        }
    progress["key_usage"] = key_usage
    # tag pre-migration fetched records with the key that actually fetched them
    for rec in progress["fetched"].values():
        rec.setdefault("key", "AV_API_KEY")
    return progress


def key_eligible_today(key_state, today):
    """Returns (eligible_now, calls_used_today, remaining_today)."""
    if key_state is None:
        return True, 0, DAILY_CALL_CAP
    if key_state.get("disabled"):
        return False, key_state.get("calls_today", 0), 0
    if key_state.get("batch_date") != today:
        last_ts_str = key_state.get("last_call_ts")
        if last_ts_str is None:
            return True, 0, DAILY_CALL_CAP
        last_ts = datetime.datetime.fromisoformat(last_ts_str)
        elapsed_h = (datetime.datetime.now(datetime.timezone.utc) - last_ts).total_seconds() / 3600.0
        if elapsed_h >= QUOTA_RESET_HOURS:
            return True, 0, DAILY_CALL_CAP
        return False, key_state.get("calls_today", 0), 0
    used = key_state.get("calls_today", 0)
    remaining = DAILY_CALL_CAP - used
    return remaining > 0, used, max(0, remaining)


def seconds_since_last_call(key_state):
    if key_state is None or not key_state.get("last_call_ts"):
        return None
    last_ts = datetime.datetime.fromisoformat(key_state["last_call_ts"])
    return (datetime.datetime.now(datetime.timezone.utc) - last_ts).total_seconds()


def step1_fetch():
    progress = load_progress()
    if progress is None:
        print("No progress.json -- run `draw` first.")
        return
    progress = migrate_to_key_usage(progress)

    all_keys = enumerate_av_keys()
    today = datetime.date.today().isoformat()
    key_usage = progress["key_usage"]

    print(f"Enumerated {len(all_keys)} AV key(s): {list(all_keys.keys())}")

    eligible_today = {}
    for name in all_keys:
        state = key_usage.get(name)
        elig, used, remaining = key_eligible_today(state, today)
        eligible_today[name] = {"eligible": elig, "used_today": used, "remaining_today": remaining}
        if state and state.get("disabled"):
            print(f"  {name}: DISABLED ({state.get('disabled_reason')})")
        elif not elig:
            print(f"  {name}: not yet eligible today (used {used}/{DAILY_CALL_CAP} in its last batch, "
                  f"waiting on {QUOTA_RESET_HOURS}h reset)")
        else:
            print(f"  {name}: eligible, {remaining} calls remaining today")

    if not any(v["eligible"] and v["remaining_today"] > 0 for v in eligible_today.values()):
        print("No key is eligible right now. Nothing to do this invocation.")
        return

    fetched = progress["fetched"]
    remaining_items = [d for d in progress["drawn"] if f"{d['ticker']}_{d['quarter']}" not in fetched]
    if not remaining_items:
        print("All drawn items already fetched or recorded as a miss. Run `report` next.")
        return

    conn = db_connect()
    queue = list(remaining_items)
    item_idx = 0

    while item_idx < len(queue):
        # refresh remaining_today counts from key_usage (may change as we go)
        candidates = []
        for name in all_keys:
            state = key_usage.get(name)
            if state and state.get("disabled"):
                continue
            elig, used, remaining = key_eligible_today(state, today)
            if not elig or remaining <= 0:
                continue
            since = seconds_since_last_call(state)
            spacing_ok = (since is None) or (since >= MIN_SPACING_SECONDS)
            candidates.append((name, since, spacing_ok))

        if not any(c[2] for c in candidates):
            if not candidates:
                print("\nAll keys exhausted for today or disabled. Stopping this invocation.")
                break
            # all candidates are cooling down -- sleep only until the soonest clears
            waits = [MIN_SPACING_SECONDS - (c[1] or 0) for c in candidates]
            sleep_for = max(0.5, min(waits))
            print(f"  all eligible keys cooling down; sleeping {sleep_for:.0f}s for the soonest one...")
            time.sleep(sleep_for)
            continue

        # pick the eligible-and-spacing-ok key that has waited longest (None = never used -> pick first)
        ready = [c for c in candidates if c[2]]
        ready.sort(key=lambda c: (c[1] is not None, -(c[1] or 0)))
        key_name = ready[0][0]
        api_key = all_keys[key_name]

        item = queue[item_idx]
        cell_key = f"{item['ticker']}_{item['quarter']}"
        print(f"\n=== {cell_key} (transcript id {item['transcript_id']}, tier {item['tier']}) via {key_name} ===")

        call_ts = now_iso()
        key_state = key_usage.setdefault(key_name, {
            "batch_date": today, "calls_today": 0, "last_call_ts": None,
            "disabled": False, "disabled_reason": None,
        })
        if key_state.get("batch_date") != today:
            key_state["batch_date"] = today
            key_state["calls_today"] = 0

        try:
            data = av_fetch(item["ticker"], item["quarter"], api_key)
        except Exception as e:
            print(f"  AV fetch error: {e}")
            fetched[cell_key] = {"status": "error", "error": str(e), "call_ts": call_ts, "key": key_name}
            append_cell({"cell_key": cell_key, "params": item, "status": "error", "error": str(e), "key": key_name})
            key_state["calls_today"] += 1
            key_state["last_call_ts"] = call_ts
            save_progress(progress)
            item_idx += 1
            continue

        key_state["calls_today"] += 1
        key_state["last_call_ts"] = call_ts

        if is_rate_limited(data):
            calls_before_limit = key_state["calls_today"] - 1
            if key_name != "AV_API_KEY" and calls_before_limit < 15:
                # rate-limited well before this key's own count would predict --
                # per the prompt's defensive check, suspect it shares quota with
                # another already-used key rather than treat this as fatal.
                key_state["disabled"] = True
                key_state["disabled_reason"] = (
                    f"rate-limited after only {calls_before_limit} calls today on this key "
                    f"-- suspected shared quota with another key, per prompt's defensive check"
                )
                print(f"  RATE LIMITED on {key_name} after only {calls_before_limit} calls -- "
                      f"suspected shared quota. Disabling this key for the rest of the run, continuing with others.")
                append_finding(
                    f"**Suspected shared-quota key**: {key_name} rate-limited after {calls_before_limit} "
                    f"calls today (expected up to {DAILY_CALL_CAP}). Disabled for the rest of the run. ({now_iso()})"
                )
                save_progress(progress)
                continue  # do not advance item_idx -- retry this item on another key
            else:
                print(f"  RATE LIMITED on {key_name}: {data}")
                print("  Stopping this invocation immediately per prompt's no-auto-retry rule.")
                save_progress(progress)
                conn.close()
                print_day_summary(progress, all_keys, today)
                return

        entries = data.get("transcript", [])
        if not entries:
            print(f"  No AV coverage for {cell_key} (empty transcript). Recording as coverage miss.")
            fetched[cell_key] = {"status": "coverage_miss", "call_ts": call_ts, "key": key_name, "raw_keys": list(data.keys())}
            append_cell({"cell_key": cell_key, "params": item, "status": "coverage_miss", "raw": data, "key": key_name})
            append_finding(f"**Coverage miss**: {cell_key} (tier {item['tier']}) -- AV returned no transcript entries. ({now_iso()})")
            save_progress(progress)
            item_idx += 1
            continue

        raw_path = RAW_DIR / f"{cell_key}.json"
        raw_path.write_text(json.dumps(data, indent=2))

        db_text = get_db_transcript(conn, item["transcript_id"])
        if not db_text:
            print(f"  DB transcript text missing for id {item['transcript_id']} -- cannot run decisive check.")
            fetched[cell_key] = {"status": "fetched_no_db_text", "call_ts": call_ts, "key": key_name, "raw_path": str(raw_path)}
            append_cell({"cell_key": cell_key, "params": item, "status": "fetched_no_db_text", "key": key_name})
            save_progress(progress)
            item_idx += 1
            continue

        av_text, av_entries = av_transcript_to_text_and_turns(data)
        result = classify_sample(db_text, av_text, av_entries)
        result["db_word_count"] = len(db_text.split())
        result["av_word_count"] = len(av_text.split())
        print(f"  classification={result['classification']} ratio={result['similarity_ratio']} "
              f"turns={result['av_turn_count']} db_words={result['db_word_count']} av_words={result['av_word_count']}")

        fetched[cell_key] = {
            "status": "classified",
            "call_ts": call_ts,
            "key": key_name,
            "raw_path": str(raw_path.relative_to(repo_root)),
            "tier": item["tier"],
            "transcript_id": item["transcript_id"],
            **result,
        }
        append_cell({"cell_key": cell_key, "params": item, "status": "classified", "result": result, "key": key_name})
        if result["classification"] in ("truncated", "possibly_truncated_needs_manual_check"):
            append_finding(
                f"**{result['classification']}**: {cell_key} (tier {item['tier']}, transcript id {item['transcript_id']}, "
                f"fetched via {key_name}) -- ratio={result['similarity_ratio']}, turns={result['av_turn_count']}, "
                f"reason: {result['reason']}. DB tail: ...{db_text[-300:]!r} | AV tail: ...{av_text[-300:]!r} ({now_iso()})"
            )
        save_progress(progress)
        item_idx += 1

    conn.close()

    total_remaining = len(progress["drawn"]) - len(progress["fetched"])
    progress["calls_used_total"] = sum(s.get("calls_today", 0) for s in key_usage.values())
    if total_remaining <= 0:
        progress["steps"]["1_fetch"] = "done"
    save_progress(progress)
    print_day_summary(progress, all_keys, today)


def print_day_summary(progress, all_keys, today):
    key_usage = progress["key_usage"]
    total_remaining = len(progress["drawn"]) - len(progress["fetched"])
    print(f"\n=== Day summary ({today}) ===")
    per_key_today = 0
    for name in all_keys:
        state = key_usage.get(name, {})
        used = state.get("calls_today", 0) if state.get("batch_date") == today else 0
        flag = " [DISABLED: %s]" % state.get("disabled_reason") if state.get("disabled") else ""
        print(f"  {name}: {used}/{DAILY_CALL_CAP} today{flag}")
        per_key_today += used
    total_used = sum(s.get("calls_today", 0) for s in key_usage.values())
    print(f"Calls used today (all keys): {per_key_today}")
    print(f"Total calls used so far (all keys, all days): {total_used}")
    print(f"Total remaining in drawn sample: {total_remaining}")
    active_keys = sum(1 for n in all_keys if not key_usage.get(n, {}).get("disabled"))
    effective_daily_rate = active_keys * DAILY_CALL_CAP
    est_remaining_invocations = -(-total_remaining // effective_daily_rate) if total_remaining > 0 and effective_daily_rate > 0 else 0
    print(f"Estimated remaining invocations at current {active_keys}-key rate: {est_remaining_invocations}")


def wilson_ci(successes, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / denom
    return (p, max(0.0, center - margin), min(1.0, center + margin))


def step2_report():
    progress = load_progress()
    if progress is None:
        print("No progress.json -- run `draw` first.")
        return
    remaining = len(progress["drawn"]) - len(progress["fetched"])
    if remaining > 0:
        print(f"Not complete: {remaining} items remain unfetched. Run `fetch` again (another day's batch).")
        return

    fetched = progress["fetched"]
    by_tier = {t: [] for t in TIERS}
    misses_by_tier = {t: 0 for t in TIERS}
    classified_by_tier = {t: [] for t in TIERS}
    for item in progress["drawn"]:
        key = f"{item['ticker']}_{item['quarter']}"
        rec = fetched.get(key, {})
        tier = item["tier"]
        by_tier[tier].append(rec)
        if rec.get("status") == "coverage_miss":
            misses_by_tier[tier] += 1
        elif rec.get("status") == "classified":
            classified_by_tier[tier].append(rec)

    def truncated_count(records):
        return sum(1 for r in records if r.get("classification") == "truncated")

    all_classified = [r for tier_recs in classified_by_tier.values() for r in tier_recs]
    overall_n = len(all_classified)
    overall_trunc = truncated_count(all_classified)
    overall_p, overall_lo, overall_hi = wilson_ci(overall_trunc, overall_n)

    print(f"Overall: {overall_trunc}/{overall_n} truncated. Wilson 95% CI: "
          f"[{overall_lo*100:.1f}%, {overall_hi*100:.1f}%], point estimate {overall_p*100:.1f}%")
    for tier in TIERS:
        n = len(classified_by_tier[tier])
        tr = truncated_count(classified_by_tier[tier])
        p, lo, hi = wilson_ci(tr, n)
        misses = misses_by_tier[tier]
        pool_n = len(by_tier[tier])
        print(f"  {tier}: {tr}/{n} truncated ({p*100:.1f}%, CI [{lo*100:.1f}%,{hi*100:.1f}%]); "
              f"coverage misses {misses}/{pool_n}")

    out = {
        "overall": {"truncated": overall_trunc, "n": overall_n, "ci": [overall_lo, overall_hi]},
        "by_tier": {
            t: {
                "truncated": truncated_count(classified_by_tier[t]),
                "n": len(classified_by_tier[t]),
                "coverage_misses": misses_by_tier[t],
                "pool_n": len(by_tier[t]),
            } for t in TIERS
        },
    }
    (STATE_DIR / "aggregate_report.json").write_text(json.dumps(out, indent=2))
    print(f"\nWritten to {STATE_DIR / 'aggregate_report.json'}")


def step_reclassify():
    """Re-run classify_sample over already-fetched raw/ files with the current
    heuristic, no new AV calls. Use after fixing a classifier bug."""
    progress = load_progress()
    if progress is None:
        print("No progress.json.")
        return
    conn = db_connect()
    changed = []
    for key, rec in progress["fetched"].items():
        if rec.get("status") != "classified":
            continue
        raw_path = repo_root / rec["raw_path"]
        data = json.loads(raw_path.read_text())
        av_text, av_entries = av_transcript_to_text_and_turns(data)
        db_text = get_db_transcript(conn, rec["transcript_id"])
        new_result = classify_sample(db_text, av_text, av_entries)
        old_class = rec.get("classification")
        if old_class != new_result["classification"]:
            changed.append((key, old_class, new_result["classification"]))
            rec.update(new_result)
    conn.close()
    save_progress(progress)
    if changed:
        note = "## Reclassification after fixing handoff/keyword heuristic (" + now_iso() + ")\n\n"
        note += "Fixed two classifier bugs: (1) a handoff phrase (e.g. 'closing remarks') " \
                "anywhere in the last turn was flagged truncated even when resolved in the " \
                "same turn -- now only flagged when it sits within 80 trailing chars of the " \
                "turn's end; (2) closing-keyword list missed 'does conclude' phrasing. " \
                "Re-ran classify_sample over all already-fetched raw/ files, 0 new AV calls.\n\n"
        for key, old, new in changed:
            note += f"- **{key}**: {old} -> {new}\n"
        append_finding(note)
        print(f"Reclassified {len(changed)} samples:")
        for key, old, new in changed:
            print(f"  {key}: {old} -> {new}")
    else:
        print("No classifications changed.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "draw":
        step0_draw()
    elif cmd == "fetch":
        step1_fetch()
    elif cmd == "report":
        step2_report()
    elif cmd == "reclassify":
        step_reclassify()
    else:
        print(f"Unknown command {cmd}")
