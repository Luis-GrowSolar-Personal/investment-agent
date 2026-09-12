#!/usr/bin/env python3
"""test4_noise_floor.py -- driver for prompts/test4-analyst-noise-floor.md
and its v6 re-run, prompts/test4-noise-floor-v6-rerun.md.

Step 1: draw a 50-transcript, tier-stratified, cutoff-restricted sample from
        the 15-ticker (not ALL16 -- SPWR excluded per the prompt's own table)
        portfolio corpus.
Step 2: run the evaluator (docs/EVALUATION_PROMPT.md as found, temperature 0,
        MODEL_VERSION from server/lib/versions.js) 5x per transcript = 250
        real Anthropic API calls. Checkpointed after every transcript.
Step 3/4: field-by-field stability + the analyst-direct hit-rate spread
        across the 5 runs, using analyst_direct_scorer.py's own constants.

No DB writes anywhere in this driver -- SELECT only for the sample draw and
forward-return lookups. Scoring output goes under
<out-dir>/{raw,scored}/, never to the Analysis table.

RUN_ID / OUT_DIR are parameterized (2026-09-12,
prompts/test4-noise-floor-v6-rerun.md) so one driver serves both the
original v10+auto1 arm and any re-run (e.g. under the promoted v6 prompt)
without forking the file -- a naive copy would drift the two out of sync.
Defaults preserve the original arm's exact behavior when no --run-id/
--out-dir is passed.

    cd analysis
    python3 test4_noise_floor.py draw        # Step 1 only, no API calls
    python3 test4_noise_floor.py score       # Step 2, resumable, real spend
    python3 test4_noise_floor.py analyze     # Steps 3/4/5, no new calls

    # A separate arm, writing under its own run-state/output dirs:
    python3 test4_noise_floor.py score --run-id test4-analyst-noise-floor-v6 \\
        --out-dir test4_noise_floor_v6

    # Model-drift check: score only a subset of transcripts, under the
    # registered v10+auto1 candidate hatch, into its own scratch location:
    PROMPT_CANDIDATE=v10+auto1 python3 test4_noise_floor.py score \\
        --run-id test4-analyst-noise-floor-v6-driftcheck \\
        --out-dir test4_noise_floor_v6/driftcheck \\
        --transcript-ids 212,296,150,100,193
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

DEFAULT_RUN_ID = "test4-analyst-noise-floor"
DEFAULT_OUT_DIR_NAME = "test4_noise_floor"

# Original arm's paths, fixed regardless of what this invocation is
# configured for -- used only by assert_original_protected() below to make
# sure a re-run (any --run-id/--out-dir) can never write into these.
ORIGINAL_OUT_DIR = SCRIPT_DIR / DEFAULT_OUT_DIR_NAME
ORIGINAL_RAW_DIR = ORIGINAL_OUT_DIR / "raw"
ORIGINAL_EXPECTED_FILE_COUNT = 50

RUN_ID = DEFAULT_RUN_ID
RUN_DIR = SCRIPT_DIR / "data" / "run_state" / RUN_ID
MANIFEST_DIR = RUN_DIR / "manifests"
CELLS_PATH = RUN_DIR / "cells.jsonl"
DRIVER_FILE = "analysis/test4_noise_floor.py"

OUT_DIR = SCRIPT_DIR / DEFAULT_OUT_DIR_NAME
RAW_DIR = OUT_DIR / "raw"


def configure_run(run_id: str, out_dir_name: str) -> None:
    """Point every path this driver writes at run_id/out_dir_name instead of
    the hardcoded originals. Must be called before any step function."""
    global RUN_ID, RUN_DIR, MANIFEST_DIR, CELLS_PATH, OUT_DIR, RAW_DIR
    RUN_ID = run_id
    RUN_DIR = SCRIPT_DIR / "data" / "run_state" / RUN_ID
    MANIFEST_DIR = RUN_DIR / "manifests"
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    CELLS_PATH = RUN_DIR / "cells.jsonl"
    OUT_DIR = SCRIPT_DIR / out_dir_name
    RAW_DIR = OUT_DIR / "raw"
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def assert_original_protected() -> None:
    """Hard-fail before any write if this invocation's OUT_DIR would collide
    with the original arm's output, or if that original output has already
    been disturbed by something else. Prints the assertion either way, per
    prompts/test4-noise-floor-v6-rerun.md Step 0."""
    if OUT_DIR.resolve() == ORIGINAL_OUT_DIR.resolve():
        raise SystemExit(
            f"REFUSING: this invocation's --out-dir resolves to the ORIGINAL "
            f"test4_noise_floor/ directory ({ORIGINAL_OUT_DIR}), which holds "
            f"Test 6's control arm and the original Test 4 comparison baseline. "
            f"Pass a different --out-dir (e.g. test4_noise_floor_v6)."
        )
    original_files = sorted(ORIGINAL_RAW_DIR.glob("*.json"))
    n = len(original_files)
    ok = n == ORIGINAL_EXPECTED_FILE_COUNT
    msg = (
        f"ASSERTION -- original {ORIGINAL_RAW_DIR} holds {n}/"
        f"{ORIGINAL_EXPECTED_FILE_COUNT} expected files, and is not this "
        f"invocation's OUT_DIR ({OUT_DIR}) -- {'PASS' if ok else 'FAIL'}."
    )
    print(msg)
    if not ok:
        raise SystemExit(
            f"REFUSING to proceed: original test4_noise_floor/raw/ has {n} files, "
            f"expected {ORIGINAL_EXPECTED_FILE_COUNT}. It may have been modified "
            f"by something else. STOP and investigate before running anything."
        )


SEED = 40  # fixed, reported

TIERS = {
    "megacap": ["AAPL", "GOOGL", "NVDA", "MSFT", "TSLA"],
    "large": ["AVGO", "AMD", "ORCL"],
    "mid": ["FSLR", "TTD"],
    "small_micro": ["QS", "AMPX", "ENVX", "EOSE", "RUN"],
}
UNIVERSE = [t for ts in TIERS.values() for t in ts]
TARGET_TOTAL = 50

PRIMARY_FIELDS = ["thesisHealth", "recommendation", "stumbleType",
                  "mitigationCapabilityTrackRecord"]
ALL_FIELDS = ["thesisHealth", "thesisDelta", "recommendation", "recommendedSize",
              "freshMoneyAllocation", "typeClassification", "stumbleType",
              "threatMechanismImpaired", "credibilityDelta", "activeDriverCount",
              "ratchetTranche", "blindSpotsTriggered", "capPercent",
              "mitigationArgumentPresent", "mitigationCapabilityTrackRecord"]


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git_info():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      cwd=REPO).decode().strip()
    dirty_out = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                         cwd=REPO).decode()
    allowed_untracked = (
        "prompts/resolve-open-four.md",
        "prompts/test4-analyst-noise-floor.md",
        "analysis/av_fidelity_benchmark_2/",
        "docs/handoffs/2026-09-05-state-of-play.md",
        "analysis/data/run_state/test4-analyst-noise-floor/",
        "analysis/test4_noise_floor/",
        # 2026-09-12 v6 re-run (prompts/test4-noise-floor-v6-rerun.md) and
        # its own new paths:
        "prompts/test4-noise-floor-v6-rerun.md",
        "analysis/data/run_state/test4-analyst-noise-floor-v6",
        "analysis/test4_noise_floor_v6/",
        # Other sessions running concurrently -- not this run's to touch or
        # wait on, per this prompt's own Step 0 instruction.
        "analysis/data/run_state/ec-fidelity-benchmark-1/",
        "analysis/ec_fidelity_benchmark_1/",
    )
    dirty_lines = [ln for ln in dirty_out.splitlines() if ln.strip()]
    unexpected = [ln for ln in dirty_lines if not any(p in ln for p in allowed_untracked)]
    dirty = bool(unexpected)
    ls = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO).decode()
    driver_tracked = DRIVER_FILE in ls
    return commit, branch, dirty, driver_tracked, unexpected


def config_hash(driver_commit, params):
    blob = driver_commit + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def write_cell(cell_key, params, chash, results):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps({"cell_key": cell_key, "params": params,
                             "config_hash": chash, "results": results}, default=str) + "\n")


def write_manifest(step, manifest):
    p = MANIFEST_DIR / f"{step}-manifest.json"
    p.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"manifest written -> {p}")


def base_manifest(driver_commit, branch, dirty, driver_tracked, params, results):
    return {
        "run_id": RUN_ID,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": driver_commit, "git_branch": branch, "git_dirty": dirty,
        "driver_file": DRIVER_FILE, "driver_file_tracked_at_commit": driver_tracked,
        "params": params, "results": results,
    }


def db_conn():
    from dotenv import load_dotenv
    import psycopg2
    load_dotenv(REPO / ".env")
    return psycopg2.connect(os.environ["DATABASE_URL"])


# ---------------------------------------------------------------------------
# Step 1 -- sample draw
# ---------------------------------------------------------------------------

def scoreable_cutoff():
    from analyst_direct_scorer import FORWARD_DAYS, PRICE_CACHE_PATH
    raw = json.loads(PRICE_CACHE_PATH.read_text())
    last = max(raw["SPY"].keys())
    return date.fromisoformat(last) - timedelta(days=FORWARD_DAYS), last, FORWARD_DAYS


def step_draw(driver_commit, branch, dirty, driver_tracked):
    cutoff, last_price_date, fwd_days = scoreable_cutoff()
    conn = db_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tk.symbol, t.id, t."callDate"::date
            FROM "Transcript" t JOIN "Ticker" tk ON t."tickerId" = tk.id
            WHERE tk.symbol = ANY(%s) AND t."callDate"::date <= %s
            ORDER BY tk.symbol, t."callDate"
        """, (UNIVERSE, cutoff))
        rows = cur.fetchall()
    conn.close()

    pool = defaultdict(list)
    for sym, tid, cdate in rows:
        pool[sym].append((sym, tid, str(cdate)))

    tier_pool = {tier: [r for sym in syms for r in pool.get(sym, [])]
                 for tier, syms in TIERS.items()}
    tier_pool_size = {t: len(v) for t, v in tier_pool.items()}

    n_tiers = len(TIERS)
    even_share = TARGET_TOTAL // n_tiers  # 12
    remainder = TARGET_TOTAL - even_share * n_tiers  # 2, goes to first tiers
    base_target = {t: even_share for t in TIERS}
    tiers_sorted = list(TIERS.keys())
    for i in range(remainder):
        base_target[tiers_sorted[i % n_tiers]] += 1

    # Reallocate shortfalls
    target = dict(base_target)
    shortfall_total = 0
    for t in TIERS:
        if tier_pool_size[t] < target[t]:
            shortfall_total += target[t] - tier_pool_size[t]
            target[t] = tier_pool_size[t]
    if shortfall_total > 0:
        eligible = [t for t in TIERS if tier_pool_size[t] > target[t]]
        while shortfall_total > 0 and eligible:
            for t in list(eligible):
                if shortfall_total <= 0:
                    break
                if tier_pool_size[t] > target[t]:
                    target[t] += 1
                    shortfall_total -= 1
                if tier_pool_size[t] <= target[t]:
                    eligible.remove(t)

    rng = random.Random(SEED)
    drawn = []
    for t in TIERS:
        pool_t = tier_pool[t]
        k = min(target[t], len(pool_t))
        drawn.extend(rng.sample(pool_t, k))

    drawn_list = [{"ticker": s, "transcript_id": tid, "call_date": cd, "tier": tier}
                  for tier, syms in TIERS.items()
                  for (s, tid, cd) in [x for x in drawn if x[0] in syms]]
    # dedupe rebuild cleanly by tier membership
    tier_of = {}
    for tier, syms in TIERS.items():
        for s in syms:
            tier_of[s] = tier
    drawn_list = [{"ticker": s, "transcript_id": tid, "call_date": cd, "tier": tier_of[s]}
                  for (s, tid, cd) in drawn]

    results = {
        "scoreable_cutoff_call_date": str(cutoff),
        "price_cache_last_date": last_price_date,
        "forward_days": fwd_days,
        "seed": SEED,
        "tier_pool_size_post_cutoff": tier_pool_size,
        "even_share_before_reallocation": base_target,
        "target_after_reallocation": target,
        "n_drawn": len(drawn_list),
        "drawn": sorted(drawn_list, key=lambda d: (d["tier"], d["ticker"], d["call_date"])),
    }
    chash = config_hash(driver_commit, {"step": "draw", "seed": SEED})
    write_cell("draw", {"seed": SEED}, chash, {k: v for k, v in results.items() if k != "drawn"})
    write_manifest("1-draw", base_manifest(driver_commit, branch, dirty, driver_tracked,
                                            {"seed": SEED}, results))
    (RUN_DIR / "sample.json").write_text(json.dumps(drawn_list, indent=2))
    print(json.dumps({k: v for k, v in results.items() if k != "drawn"}, indent=2, default=str))
    print(f"\n{len(drawn_list)} transcripts drawn -> {RUN_DIR / 'sample.json'}")
    return results


# ---------------------------------------------------------------------------
# Step 2 -- 5 fresh scoring runs per transcript
# ---------------------------------------------------------------------------

_STRUCTURED_RE = re.compile(r"---STRUCTURED---\s*(\{[\s\S]*?\})\s*---END STRUCTURED---")


def parse_structured(text):
    m = _STRUCTURED_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def get_model_version():
    vjs = (REPO / "server" / "lib" / "versions.js").read_text()
    m = re.search(r"MODEL_VERSION\s*=\s*'([^']+)'", vjs)
    return m.group(1)


def get_prompt_header():
    text = (REPO / "docs" / "EVALUATION_PROMPT.md").read_text()
    from analysis.version_guard import assert_prompt_hash
    assert_prompt_hash(text, candidate=os.environ.get("PROMPT_CANDIDATE"))
    m = re.search(r"^# Version:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "UNKNOWN", text


def _init_progress_if_missing(progress_path, driver_commit):
    if progress_path.exists():
        return json.loads(progress_path.read_text())
    prompt_path = REPO / "prompts" / "test4-noise-floor-v6-rerun.md"
    progress = {
        "run_id": RUN_ID,
        "prompt_sha256": sha256_file(prompt_path) if prompt_path.exists() else None,
        "driver_commit": driver_commit,
        "steps": {"step2_250_scoring_calls": "in_progress"},
        "transcripts_completed": [],
        "next_action": "Resume by re-running `python3 test4_noise_floor.py score` with the same --run-id/--out-dir.",
        "notes": [],
    }
    progress_path.write_text(json.dumps(progress, indent=2, default=str))
    return progress


def _do_one_run(client, model, full_prompt, run_idx):
    resp = client.messages.create(
        model=model, max_tokens=8192, temperature=0,
        messages=[{"role": "user", "content": full_prompt}],
    )
    text = resp.content[0].text.strip()
    return {
        "run_idx": run_idx, "stop_reason": resp.stop_reason,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "structured": parse_structured(text), "raw_text": text,
        "model_used_response_hint": getattr(resp, "model", None),
    }


def _run_five_for_transcript(anthropic_mod, client, model, full_prompt, tid):
    """Issue the 5 runs for one transcript CONCURRENTLY (never across
    transcripts -- see prompts/test4-noise-floor-v6-rerun.md Step 3, and the
    three OS low-memory kills that hit when a prior run parallelized across
    transcripts instead). Falls back to serial for any run that hits a rate
    limit, logging the fallback explicitly."""
    runs_by_idx = {}
    rate_limited_idxs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        future_to_idx = {ex.submit(_do_one_run, client, model, full_prompt, i): i
                          for i in range(5)}
        for fut in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                runs_by_idx[idx] = fut.result()
            except anthropic_mod.RateLimitError as e:
                print(f"  transcript {tid} run {idx}: RATE LIMITED ({e}) -- "
                      f"will retry serially")
                rate_limited_idxs.append(idx)

    concurrency_note = "5-way concurrent"
    missing = [i for i in range(5) if i not in runs_by_idx]
    if missing:
        concurrency_note = f"serial fallback for {len(missing)}/5 run(s) after rate limit"
        print(f"  transcript {tid}: falling back to serial for run(s) {missing}")
        for idx in missing:
            runs_by_idx[idx] = _do_one_run(client, model, full_prompt, idx)

    return [runs_by_idx[i] for i in range(5)], concurrency_note


def step_score(transcript_ids_filter=None):
    import anthropic
    model = get_model_version()
    prompt_version_str, eval_prompt = get_prompt_header()
    conn = db_conn()

    sample = json.loads((RUN_DIR / "sample.json").read_text())
    if transcript_ids_filter is not None:
        wanted = set(transcript_ids_filter)
        sample = [e for e in sample if e["transcript_id"] in wanted]
        found = {e["transcript_id"] for e in sample}
        missing = wanted - found
        if missing:
            print(f"WARNING: --transcript-ids requested {sorted(missing)} "
                  f"but they are not in this run's sample.json")
        print(f"Restricting this invocation to {len(sample)} transcript(s): "
              f"{sorted(found)}")

    load_dotenv_key()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    progress_path = RUN_DIR / "progress.json"
    driver_commit_for_init = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    progress = _init_progress_if_missing(progress_path, driver_commit_for_init)
    done_ids = set(progress.get("transcripts_completed", []))

    total_input_tokens = 0
    total_output_tokens = 0
    concurrency_notes_seen = set()
    # reload running token totals if resuming
    tok_path = RUN_DIR / "token_usage.json"
    if tok_path.exists():
        tok = json.loads(tok_path.read_text())
        total_input_tokens = tok.get("input_tokens", 0)
        total_output_tokens = tok.get("output_tokens", 0)

    for entry in sample:
        tid = entry["transcript_id"]
        if tid in done_ids:
            continue
        with conn.cursor() as cur:
            cur.execute('SELECT "rawText" FROM "Transcript" WHERE id=%s', (tid,))
            row = cur.fetchone()
        if not row:
            print(f"transcript {tid} missing rawText, skipping")
            done_ids.add(tid)
            continue
        transcript_text = row[0]
        full_prompt = eval_prompt.strip() + "\n\n---\n\nTRANSCRIPT:\n\n" + transcript_text

        runs, concurrency_note = _run_five_for_transcript(
            anthropic, client, model, full_prompt, tid
        )
        concurrency_notes_seen.add(concurrency_note)
        for r in runs:
            total_input_tokens += r["input_tokens"]
            total_output_tokens += r["output_tokens"]
            print(f"  transcript {tid} run {r['run_idx']}: {r['stop_reason']}, "
                  f"{r['input_tokens']}in/{r['output_tokens']}out")

        out = {"transcript_id": tid, "ticker": entry["ticker"],
               "call_date": entry["call_date"], "tier": entry["tier"],
               "model": model, "prompt_version_header": prompt_version_str,
               "prompt_candidate_used": os.environ.get("PROMPT_CANDIDATE"),
               "concurrency": concurrency_note,
               "runs": runs}
        (RAW_DIR / f"{tid}.json").write_text(json.dumps(out, indent=2, default=str))

        done_ids.add(tid)
        progress["transcripts_completed"] = sorted(done_ids)
        progress["steps"]["step2_250_scoring_calls"] = (
            "done" if len(done_ids) >= len(sample) else "in_progress"
        )
        progress["concurrency_notes_seen"] = sorted(concurrency_notes_seen)
        progress["next_action"] = (
            f"{len(done_ids)}/{len(sample)} transcripts scored (5 runs each). "
            f"Resume by re-running with the same --run-id/--out-dir."
        )
        progress_path.write_text(json.dumps(progress, indent=2, default=str))
        tok_path.write_text(json.dumps(
            {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens,
             "total_tokens": total_input_tokens + total_output_tokens,
             "n_transcripts_done": len(done_ids)}, indent=2))
        with (RUN_DIR / "findings.md").open("a") as f:
            f.write(f"\n- Checkpoint: transcript {tid} ({entry['ticker']} "
                    f"{entry['call_date']}, tier {entry['tier']}) 5/5 runs complete "
                    f"({concurrency_note}). "
                    f"Running total: {len(done_ids)}/{len(sample)} transcripts, "
                    f"{total_input_tokens + total_output_tokens} tokens so far.\n")
        print(f"checkpoint: {len(done_ids)}/{len(sample)} transcripts done, "
              f"{total_input_tokens + total_output_tokens} tokens so far")

    conn.close()
    print(f"\nScoring complete. Total tokens: {total_input_tokens + total_output_tokens} "
          f"({total_input_tokens} in, {total_output_tokens} out). "
          f"Concurrency modes used: {sorted(concurrency_notes_seen)}")


def load_dotenv_key():
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")


# ---------------------------------------------------------------------------
# Steps 3/4/5 -- analysis, no new calls
# ---------------------------------------------------------------------------

def step_analyze(driver_commit, branch, dirty, driver_tracked):
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH, direction_from_score, \
        FORWARD_DAYS, DEAD_BAND, BENCHMARK

    sample = json.loads((RUN_DIR / "sample.json").read_text())
    tier_of_tid = {e["transcript_id"]: e["tier"] for e in sample}
    ticker_of_tid = {e["transcript_id"]: e["ticker"] for e in sample}
    calldate_of_tid = {e["transcript_id"]: date.fromisoformat(e["call_date"]) for e in sample}

    raw_files = sorted(RAW_DIR.glob("*.json"))
    all_samples = [json.loads(f.read_text()) for f in raw_files]
    assert len(all_samples) == len(sample), f"{len(all_samples)} scored vs {len(sample)} drawn"

    tok = json.loads((RUN_DIR / "token_usage.json").read_text())

    model_used = all_samples[0]["model"]
    prompt_header = all_samples[0]["prompt_version_header"]

    # --- Step 3: field-by-field stability ---
    primary_unstable = 0
    primary_total = 0
    recommendation_flip_count = 0
    recommendation_3way_split = []
    field_distinct_counts = defaultdict(list)  # field -> list of distinct-value counts per transcript

    for s in all_samples:
        tid = s["transcript_id"]
        structs = [r["structured"] for r in s["runs"]]
        valid = [st for st in structs if st is not None]

        for field in ALL_FIELDS:
            vals = [json.dumps(st.get(field), sort_keys=True) if st else "__PARSE_FAIL__"
                    for st in structs]
            distinct = len(set(vals))
            field_distinct_counts[field].append(distinct)
            if field in PRIMARY_FIELDS:
                primary_total += 1
                if distinct > 1:
                    primary_unstable += 1

        rec_vals = [st.get("recommendation") if st else None for st in structs]
        distinct_recs = set(rec_vals)
        if len(distinct_recs) > 1:
            recommendation_flip_count += 1
        if len(distinct_recs) >= 3:
            recommendation_3way_split.append({"transcript_id": tid,
                                               "ticker": ticker_of_tid[tid],
                                               "recommendations": rec_vals})

    field_instability_summary = {}
    for field in ALL_FIELDS:
        counts = field_distinct_counts[field]
        n_unstable = sum(1 for c in counts if c > 1)
        field_instability_summary[field] = {
            "n_transcripts_unstable": n_unstable, "n_transcripts_total": len(counts),
            "pct_unstable": round(100 * n_unstable / len(counts), 1) if counts else None,
        }

    # --- Step 4: hit-rate spread across the 5 independent runs ---
    prices = PriceCache(PRICE_CACHE_PATH)

    def hit_rate_for_run(run_idx, restrict_tids=None):
        hits, n = 0, 0
        for s in all_samples:
            tid = s["transcript_id"]
            if restrict_tids is not None and tid not in restrict_tids:
                continue
            st = s["runs"][run_idx]["structured"]
            if st is None:
                continue
            predicted = direction_from_score(st)
            if predicted is None:
                continue
            ticker = ticker_of_tid[tid]
            call_date = calldate_of_tid[tid]
            p0, _ = prices.price_on_or_after(ticker, call_date)
            b0, _ = prices.price_on_or_after(BENCHMARK, call_date)
            fwd = call_date + timedelta(days=FORWARD_DAYS)
            p1, _ = prices.price_on_or_after(ticker, fwd)
            b1, _ = prices.price_on_or_after(BENCHMARK, fwd)
            if not all([p0, b0, p1, b1]):
                continue
            rel = (p1 - p0) / p0 - (b1 - b0) / b0
            gt = "bullish" if rel > DEAD_BAND else ("bearish" if rel < -DEAD_BAND else "neutral")
            n += 1
            if predicted == gt:
                hits += 1
        return (hits / n if n else None), n

    hit_rates = []
    ns = []
    for i in range(5):
        hr, n = hit_rate_for_run(i)
        hit_rates.append(hr)
        ns.append(n)

    valid_hrs = [hr for hr in hit_rates if hr is not None]
    hr_std = statistics.pstdev(valid_hrs) * 100 if len(valid_hrs) > 1 else None
    hr_range = (max(valid_hrs) - min(valid_hrs)) * 100 if len(valid_hrs) > 1 else None

    by_tier = {}
    for tier in TIERS:
        tids = {e["transcript_id"] for e in sample if e["tier"] == tier}
        tier_hrs = []
        for i in range(5):
            hr, n = hit_rate_for_run(i, restrict_tids=tids)
            tier_hrs.append(hr)
        valid_tier_hrs = [hr for hr in tier_hrs if hr is not None]
        by_tier[tier] = {
            "hit_rates_per_run": tier_hrs,
            "std_pp": statistics.pstdev(valid_tier_hrs) * 100 if len(valid_tier_hrs) > 1 else None,
            "range_pp": (max(valid_tier_hrs) - min(valid_tier_hrs)) * 100 if len(valid_tier_hrs) > 1 else None,
            "n_scoreable": len(tids),
        }

    results = {
        "n_transcripts": len(all_samples),
        "model_used": model_used, "prompt_header": prompt_header,
        "token_usage": tok,
        "primary_field_instability": {
            "unstable_combos": primary_unstable, "total_combos": primary_total,
            "pct": round(100 * primary_unstable / primary_total, 1) if primary_total else None,
            "fields": PRIMARY_FIELDS,
        },
        "recommendation_flip_count": recommendation_flip_count,
        "recommendation_3way_or_more_splits": recommendation_3way_split,
        "all_field_instability": field_instability_summary,
        "hit_rates_per_run": hit_rates, "n_scoreable_per_run": ns,
        "hit_rate_std_pp": hr_std, "hit_rate_range_pp": hr_range,
        "hit_rate_by_tier": by_tier,
        "gate_ledger_noise_std_pp_reference": 4.2,
        "gate_ledger_sonnet_4_6_regression_pp_reference": -7.44,
    }
    chash = config_hash(driver_commit, {"step": "analyze"})
    write_cell("analyze", {}, chash, {k: v for k, v in results.items()
                                       if k not in ("all_field_instability",)})
    write_manifest("2-analyze", base_manifest(driver_commit, branch, dirty, driver_tracked, {}, results))
    print(json.dumps(results, indent=2, default=str))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["draw", "score", "analyze"])
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID,
                         help=f"run_id under analysis/data/run_state/ (default: {DEFAULT_RUN_ID})")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR_NAME,
                         help=f"output dir name under analysis/ (default: {DEFAULT_OUT_DIR_NAME})")
    parser.add_argument("--transcript-ids", default=None,
                         help="comma-separated transcript ids to restrict `score` to "
                              "(e.g. for the model-drift check subset). Ignored by draw/analyze.")
    args = parser.parse_args()

    configure_run(args.run_id, args.out_dir)
    assert_original_protected()

    commit, branch, dirty, driver_tracked, unexpected = git_info()
    if dirty:
        print("UNEXPECTED DIRTY TREE:")
        for ln in unexpected:
            print(" ", ln)
    print(f"git_commit={commit} branch={branch} dirty={dirty} driver_tracked={driver_tracked}")
    print(f"run_id={RUN_ID} out_dir={OUT_DIR}")

    if args.step == "draw":
        step_draw(commit, branch, dirty, driver_tracked)
    elif args.step == "score":
        ids_filter = None
        if args.transcript_ids:
            ids_filter = [int(x) for x in args.transcript_ids.split(",") if x.strip()]
        step_score(transcript_ids_filter=ids_filter)
    elif args.step == "analyze":
        step_analyze(commit, branch, dirty, driver_tracked)


if __name__ == "__main__":
    main()
