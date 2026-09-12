#!/usr/bin/env python3
"""test6_look_ahead.py -- driver for prompts/test6-look-ahead-prohibition.md.

Paired continuation of Test 4 (analysis/test4_noise_floor.py, NOT modified;
its saved raw/*.json is this run's control arm and is read-only here).
Reuses Test 4's exact 50-transcript sample
(analysis/data/run_state/test4-analyst-noise-floor/sample.json) so the
per-tier noise floors Test 4 measured transfer directly to this run.

Step 1a: build the treatment prompt in memory (EVALUATION_PROMPT.md as read
          from disk + one appended sentence). Never written back to disk.
Step 1b: control replication check -- 5 named transcripts (one per tier +
          one extra megacap) re-scored 5x each with the UNMODIFIED prompt,
          compared against Test 4's saved runs for those same transcripts.
          25 real API calls. If this does not reproduce Test 4's
          distribution, STOP -- do not proceed to Step 2.
Step 2:   treatment arm -- 50 transcripts x 5 runs with the treatment
          prompt. 250 real API calls. Checkpointed after every transcript.
Step 3/4: hit-rate comparison per tier (analyst_direct_scorer.py's own
          constants, imported not reimplemented), modal-recommendation
          change count, differential test, NVDA case study.

No DB writes anywhere -- SELECT only for transcript text and forward-return
lookups. Nothing written to the Analysis table. Test 4's raw/*.json is never
modified.

    cd analysis
    python3 test6_look_ahead.py build_treatment   # Step 1a, no API calls
    python3 test6_look_ahead.py replicate         # Step 1b, 25 calls, gate
    python3 test6_look_ahead.py treatment         # Step 2, 250 calls, resumable
    python3 test6_look_ahead.py analyze           # Step 3/4, no new calls
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPT_DIR))

RUN_ID = "test6-look-ahead-prohibition"
RUN_DIR = SCRIPT_DIR / "data" / "run_state" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)
CELLS_PATH = RUN_DIR / "cells.jsonl"
FINDINGS_PATH = RUN_DIR / "findings.md"
DRIVER_FILE = "analysis/test6_look_ahead.py"

OUT_DIR = SCRIPT_DIR / "test6_look_ahead"
REPL_DIR = OUT_DIR / "replication"
TREAT_DIR = OUT_DIR / "treatment"
REPL_DIR.mkdir(parents=True, exist_ok=True)
TREAT_DIR.mkdir(parents=True, exist_ok=True)

TEST4_SAMPLE_PATH = SCRIPT_DIR / "data" / "run_state" / "test4-analyst-noise-floor" / "sample.json"
TEST4_RAW_DIR = SCRIPT_DIR / "test4_noise_floor" / "raw"

LOOK_AHEAD_SENTENCE = ("evaluate as of the call date; do not rely on knowledge "
                       "of subsequent stock performance, later results, or later news")

# One per tier + one extra megacap, named per the prompt's Step 1b.
REPLICATION_TIDS = [212, 141, 132, 230, 23]  # MSFT(megacap), MSFT(megacap,extra), ORCL(large), TTD(mid), EOSE(small_micro)

TIERS_ORDER = ["megacap", "large", "mid", "small_micro"]
TIER_NOISE_FLOOR_PP = {"large": 0.0, "mid": 0.0, "megacap": 3.77, "small_micro": 14.34}

NVDA_TID = 315  # the one NVDA transcript in Test 4's sample (tier=megacap)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _git_state():
    """Only tracked (non-'??') lines count as dirty -- same precedent as
    the sizing-channel and small-cap-instability drivers."""
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    tracked_dirty = [l for l in status.splitlines() if l.strip() and not l.startswith("??")]
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    driver_tracked = DRIVER_FILE in ls
    return commit, branch, bool(tracked_dirty), tracked_dirty, driver_tracked


def append_cell(record: dict):
    with CELLS_PATH.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def append_finding(text: str):
    with FINDINGS_PATH.open("a") as f:
        f.write(text.rstrip() + "\n\n")


def load_progress():
    p = RUN_DIR / "progress.json"
    return json.loads(p.read_text())


def save_progress(progress):
    (RUN_DIR / "progress.json").write_text(json.dumps(progress, indent=2, default=str))


def db_conn():
    from dotenv import load_dotenv
    import psycopg2
    load_dotenv(REPO / ".env")
    return psycopg2.connect(os.environ["DATABASE_URL"])


def get_model_version():
    vjs = (REPO / "server" / "lib" / "versions.js").read_text()
    m = re.search(r"MODEL_VERSION\s*=\s*'([^']+)'", vjs)
    return m.group(1)


def get_prompt_header_and_text():
    text = (REPO / "docs" / "EVALUATION_PROMPT.md").read_text()
    from analysis.version_guard import assert_prompt_hash
    assert_prompt_hash(text, candidate=os.environ.get("PROMPT_CANDIDATE"))
    m = re.search(r"^# Version:\s*(.+)$", text, re.MULTILINE)
    return (m.group(1).strip() if m else "UNKNOWN"), text


_STRUCTURED_RE = re.compile(r"---STRUCTURED---\s*(\{[\s\S]*?\})\s*---END STRUCTURED---")


def parse_structured(text):
    m = _STRUCTURED_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Step 1a -- build the treatment prompt, report provenance
# ---------------------------------------------------------------------------

def step_build_treatment():
    header, eval_prompt = get_prompt_header_and_text()
    file_sha = sha256_bytes(eval_prompt.encode())
    treatment_prompt = eval_prompt.strip() + "\n\n" + LOOK_AHEAD_SENTENCE + "\n"
    treatment_sha = sha256_bytes(treatment_prompt.encode())

    expected_header = "v10+auto1 (auto-iterate candidate — pending gate)"
    ok = (header == expected_header)

    result = {
        "header_found": header,
        "expected_header": expected_header,
        "header_matches": ok,
        "eval_prompt_file_sha256": file_sha,
        "treatment_prompt_sha256": treatment_sha,
        "sentence_appended": LOOK_AHEAD_SENTENCE,
        "append_location": "end of file (after prompt.strip()), on its own line, "
                            "before the '---\\n\\nTRANSCRIPT:' separator that step_score "
                            "appends at call time -- identical to how the unmodified "
                            "prompt is used, just with the sentence inserted first.",
    }
    print(json.dumps(result, indent=2))
    append_finding("Step 1a: treatment prompt built in memory (not written to disk). "
                    f"header_matches={ok}. eval_prompt_file_sha256={file_sha}. "
                    f"treatment_prompt_sha256={treatment_sha}.")
    if not ok:
        append_finding("STOP: header string does not match Test 4's recorded header "
                        "-- control arm is no longer comparable.")
        print("FATAL: header mismatch, stop before Step 1b.")
        return 1
    return 0


def build_treatment_prompt_text():
    _, eval_prompt = get_prompt_header_and_text()
    return eval_prompt.strip() + "\n\n" + LOOK_AHEAD_SENTENCE + "\n"


# ---------------------------------------------------------------------------
# Shared scoring helper
# ---------------------------------------------------------------------------

def score_transcripts(tids, sample_by_tid, prompt_text, out_dir, arm_name, progress_key):
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = get_model_version()
    header, _ = get_prompt_header_and_text()

    progress = load_progress()
    done_ids = set(progress.get(progress_key, []))

    tok_path = RUN_DIR / f"token_usage_{arm_name}.json"
    total_input_tokens = total_output_tokens = 0
    if tok_path.exists():
        tok = json.loads(tok_path.read_text())
        total_input_tokens = tok.get("input_tokens", 0)
        total_output_tokens = tok.get("output_tokens", 0)

    conn = db_conn()
    for tid in tids:
        if tid in done_ids:
            continue
        entry = sample_by_tid[tid]
        with conn.cursor() as cur:
            cur.execute('SELECT "rawText" FROM "Transcript" WHERE id=%s', (tid,))
            row = cur.fetchone()
        if not row:
            print(f"transcript {tid} missing rawText, skipping")
            done_ids.add(tid)
            continue
        transcript_text = row[0]
        full_prompt = prompt_text.strip() + "\n\n---\n\nTRANSCRIPT:\n\n" + transcript_text

        runs = []
        for run_idx in range(5):
            resp = client.messages.create(
                model=model, max_tokens=8192, temperature=0,
                messages=[{"role": "user", "content": full_prompt}],
            )
            text = resp.content[0].text.strip()
            structured = parse_structured(text)
            total_input_tokens += resp.usage.input_tokens
            total_output_tokens += resp.usage.output_tokens
            runs.append({
                "run_idx": run_idx, "stop_reason": resp.stop_reason,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "structured": structured, "raw_text": text,
                "text_length_chars": len(text),
                "model_used_response_hint": getattr(resp, "model", None),
            })
            print(f"  [{arm_name}] transcript {tid} run {run_idx}: {resp.stop_reason}, "
                  f"{resp.usage.input_tokens}in/{resp.usage.output_tokens}out")

        out = {"transcript_id": tid, "ticker": entry["ticker"],
               "call_date": entry["call_date"], "tier": entry["tier"],
               "model": model, "prompt_version_header": header,
               "arm": arm_name, "runs": runs}
        (out_dir / f"{tid}.json").write_text(json.dumps(out, indent=2, default=str))

        done_ids.add(tid)
        progress[progress_key] = sorted(done_ids)
        progress["next_action"] = (
            f"{arm_name}: {len(done_ids)}/{len(tids)} transcripts scored. "
            f"Resume by re-running `python3 test6_look_ahead.py "
            f"{'replicate' if arm_name=='replication' else 'treatment'}`."
        )
        save_progress(progress)
        tok_path.write_text(json.dumps(
            {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens,
             "total_tokens": total_input_tokens + total_output_tokens,
             "n_transcripts_done": len(done_ids)}, indent=2))
        append_finding(f"[{arm_name}] checkpoint: transcript {tid} ({entry['ticker']} "
                        f"{entry['call_date']}, tier {entry['tier']}) 5/5 runs complete. "
                        f"{len(done_ids)}/{len(tids)} done, "
                        f"{total_input_tokens + total_output_tokens} tokens so far.")
        print(f"checkpoint [{arm_name}]: {len(done_ids)}/{len(tids)} done, "
              f"{total_input_tokens + total_output_tokens} tokens so far")
    conn.close()
    return total_input_tokens, total_output_tokens


# ---------------------------------------------------------------------------
# Step 1b -- control replication check (25 calls, unmodified prompt)
# ---------------------------------------------------------------------------

def step_replicate():
    commit, branch, dirty, tracked_dirty, driver_tracked = _git_state()
    if dirty:
        print(f"FATAL: tracked files dirty: {tracked_dirty}")
        return 1

    sample = json.loads(TEST4_SAMPLE_PATH.read_text())
    sample_by_tid = {e["transcript_id"]: e for e in sample}
    _, eval_prompt = get_prompt_header_and_text()

    print(f"Replicating {len(REPLICATION_TIDS)} transcripts x 5 runs (25 calls), unmodified prompt")
    score_transcripts(REPLICATION_TIDS, sample_by_tid, eval_prompt, REPL_DIR,
                       "replication", "replication_completed")

    # Compare against Test 4's saved runs for the same transcripts.
    comparison = {}
    all_reproduce = True
    for tid in REPLICATION_TIDS:
        repl = json.loads((REPL_DIR / f"{tid}.json").read_text())
        ctrl = json.loads((TEST4_RAW_DIR / f"{tid}.json").read_text())
        repl_recs = [r["structured"].get("recommendation") if r["structured"] else None
                     for r in repl["runs"]]
        ctrl_recs = [r["structured"].get("recommendation") if r["structured"] else None
                     for r in ctrl["runs"]]
        same_set = set(repl_recs) == set(ctrl_recs)
        comparison[tid] = {"ticker": repl["ticker"], "tier": repl["tier"],
                            "replication_recs": repl_recs, "test4_recs": ctrl_recs,
                            "distinct_values_match": same_set}
        if not same_set:
            all_reproduce = False

    progress = load_progress()
    progress["steps"]["step1b_replication"] = "done"
    progress["replication_reproduces_test4"] = all_reproduce
    save_progress(progress)

    (RUN_DIR / "replication_comparison.json").write_text(
        json.dumps(comparison, indent=2, default=str))
    print(json.dumps(comparison, indent=2, default=str))
    append_finding(f"Step 1b: replication_reproduces_test4={all_reproduce}. "
                    f"Detail in replication_comparison.json.")
    if not all_reproduce:
        append_finding("STOP: control replication did not match Test 4's recorded "
                        "recommendation-value set for at least one transcript -- "
                        "the control arm has decayed. Do not proceed to Step 2.")
        print("FATAL: replication does not match Test 4 -- STOP, do not run Step 2.")
        return 1
    print("Replication matches Test 4's recommendation-value distribution for all 5 transcripts. Proceed to Step 2.")
    return 0


# ---------------------------------------------------------------------------
# Step 2 -- treatment arm (250 calls)
# ---------------------------------------------------------------------------

def step_treatment():
    commit, branch, dirty, tracked_dirty, driver_tracked = _git_state()
    if dirty:
        print(f"FATAL: tracked files dirty: {tracked_dirty}")
        return 1

    progress = load_progress()
    if not progress.get("replication_reproduces_test4"):
        print("FATAL: Step 1b (replicate) has not passed yet -- refusing to run Step 2.")
        return 1

    sample = json.loads(TEST4_SAMPLE_PATH.read_text())
    sample_by_tid = {e["transcript_id"]: e for e in sample}
    tids = [e["transcript_id"] for e in sample]
    treatment_prompt = build_treatment_prompt_text()

    print(f"Treatment arm: {len(tids)} transcripts x 5 runs (250 calls)")
    ti, to = score_transcripts(tids, sample_by_tid, treatment_prompt, TREAT_DIR,
                                "treatment", "treatment_completed")
    print(f"Treatment scoring: {ti} in / {to} out / {ti+to} total tokens so far")
    progress = load_progress()
    if len(progress.get("treatment_completed", [])) >= len(tids):
        progress["steps"]["step2_treatment"] = "done"
        save_progress(progress)
    return 0


# ---------------------------------------------------------------------------
# Step 3/4 -- analysis, no new calls
# ---------------------------------------------------------------------------

def hit_rate_for_run(all_samples, run_idx, ticker_of_tid, calldate_of_tid, prices,
                      direction_from_score, FORWARD_DAYS, DEAD_BAND, BENCHMARK,
                      restrict_tids=None):
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


def modal_recommendation(structs):
    vals = [st.get("recommendation") for st in structs if st is not None]
    if not vals:
        return None
    counts = defaultdict(int)
    for v in vals:
        counts[v] += 1
    return max(counts.items(), key=lambda kv: (kv[1], vals.index(kv[0])))[0]


def step_analyze():
    from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH, direction_from_score, \
        FORWARD_DAYS, DEAD_BAND, BENCHMARK

    sample = json.loads(TEST4_SAMPLE_PATH.read_text())
    tier_of_tid = {e["transcript_id"]: e["tier"] for e in sample}
    ticker_of_tid = {e["transcript_id"]: e["ticker"] for e in sample}
    calldate_of_tid = {e["transcript_id"]: date.fromisoformat(e["call_date"]) for e in sample}
    tids_all = [e["transcript_id"] for e in sample]

    control_samples = [json.loads((TEST4_RAW_DIR / f"{tid}.json").read_text()) for tid in tids_all]
    treatment_files = sorted(TREAT_DIR.glob("*.json"))
    treatment_samples = [json.loads(f.read_text()) for f in treatment_files]
    assert len(treatment_samples) == len(tids_all), \
        f"{len(treatment_samples)} treatment-scored vs {len(tids_all)} drawn"

    prices = PriceCache(PRICE_CACHE_PATH)

    def per_tier_hit_rates(all_samples):
        by_tier = {}
        for tier in TIERS_ORDER:
            tids = {e["transcript_id"] for e in sample if e["tier"] == tier}
            hrs = []
            for i in range(5):
                hr, n = hit_rate_for_run(all_samples, i, ticker_of_tid, calldate_of_tid,
                                          prices, direction_from_score, FORWARD_DAYS,
                                          DEAD_BAND, BENCHMARK, restrict_tids=tids)
                hrs.append(hr)
            valid = [hr for hr in hrs if hr is not None]
            by_tier[tier] = {
                "hit_rates_per_run": hrs,
                "mean_pct": statistics.mean(valid) * 100 if valid else None,
                "std_pp": statistics.pstdev(valid) * 100 if len(valid) > 1 else None,
                "range_pp": (max(valid) - min(valid)) * 100 if len(valid) > 1 else None,
                "n_scoreable": len(tids),
            }
        return by_tier

    control_by_tier = per_tier_hit_rates(control_samples)
    treatment_by_tier = per_tier_hit_rates(treatment_samples)

    comparison_table = {}
    for tier in TIERS_ORDER:
        c = control_by_tier[tier]["mean_pct"]
        t = treatment_by_tier[tier]["mean_pct"]
        delta = (t - c) if (c is not None and t is not None) else None
        floor = TIER_NOISE_FLOOR_PP[tier]
        exceeds = (abs(delta) > floor) if (delta is not None) else None
        comparison_table[tier] = {
            "control_mean_pct": c, "treatment_mean_pct": t, "delta_pp": delta,
            "control_std_pp": control_by_tier[tier]["std_pp"],
            "treatment_std_pp": treatment_by_tier[tier]["std_pp"],
            "noise_floor_pp": floor, "exceeds_floor": exceeds,
        }

    # --- minimum detectable effect at n=13, binomial approx ---
    # A 0.0pp std observed at n=13 (large/mid) does not mean zero variance;
    # bound it via the Wilson/normal-approx half-width for a binomial
    # proportion at n=13, evaluated at p=0.5 (max-variance point) as a
    # conservative MDE for a single-run hit-rate estimate, then propagate
    # to a 5-run mean (divide by sqrt(5)).
    import math
    n_large_mid = 13  # matches Test 4's own n for large; mid is 12, close enough to state together
    z = 1.96
    p = 0.5
    single_run_se = math.sqrt(p * (1 - p) / n_large_mid)
    mde_single_run_pp = z * single_run_se * 100
    mde_5run_mean_pp = mde_single_run_pp / math.sqrt(5)

    # --- modal recommendation change, by tier ---
    modal_changes = {"overall": 0, "by_tier": defaultdict(int)}
    modal_detail = []
    ctrl_by_tid = {s["transcript_id"]: s for s in control_samples}
    treat_by_tid = {s["transcript_id"]: s for s in treatment_samples}
    for tid in tids_all:
        c_structs = [r["structured"] for r in ctrl_by_tid[tid]["runs"]]
        t_structs = [r["structured"] for r in treat_by_tid[tid]["runs"]]
        c_modal = modal_recommendation(c_structs)
        t_modal = modal_recommendation(t_structs)
        changed = c_modal != t_modal
        if changed:
            modal_changes["overall"] += 1
            modal_changes["by_tier"][tier_of_tid[tid]] += 1
        modal_detail.append({"transcript_id": tid, "ticker": ticker_of_tid[tid],
                              "tier": tier_of_tid[tid], "control_modal": c_modal,
                              "treatment_modal": t_modal, "changed": changed})

    # --- confound check: output length / structure ---
    def avg_len(samples):
        lens = [r.get("text_length_chars") for s in samples for r in s["runs"]
                if r.get("text_length_chars")]
        return statistics.mean(lens) if lens else None
    def avg_len_control(samples):
        lens = [len(r["raw_text"]) for s in samples for r in s["runs"] if r.get("raw_text")]
        return statistics.mean(lens) if lens else None
    confound = {
        "control_avg_output_chars": avg_len_control(control_samples),
        "treatment_avg_output_chars": avg_len(treatment_samples),
    }

    # --- NVDA case study ---
    nvda_ctrl = ctrl_by_tid.get(NVDA_TID)
    nvda_treat = treat_by_tid.get(NVDA_TID)
    nvda_case = None
    if nvda_ctrl and nvda_treat:
        c_recs = [r["structured"].get("recommendation") if r["structured"] else None
                  for r in nvda_ctrl["runs"]]
        t_recs = [r["structured"].get("recommendation") if r["structured"] else None
                  for r in nvda_treat["runs"]]
        c_hr, c_n = hit_rate_for_run(control_samples, 0, ticker_of_tid, calldate_of_tid,
                                      prices, direction_from_score, FORWARD_DAYS, DEAD_BAND,
                                      BENCHMARK, restrict_tids={NVDA_TID})
        nvda_case = {"transcript_id": NVDA_TID, "ticker": "NVDA",
                     "control_recommendations": c_recs, "treatment_recommendations": t_recs,
                     "control_modal": modal_recommendation([r["structured"] for r in nvda_ctrl["runs"]]),
                     "treatment_modal": modal_recommendation([r["structured"] for r in nvda_treat["runs"]]),
                     "note": "n=1 transcript, no significance claim possible; named case study only."}

    # --- differential test ---
    high_recall_tiers = ["megacap", "large"]
    low_recall_tiers = ["small_micro"]
    high_deltas = [abs(comparison_table[t]["delta_pp"]) for t in high_recall_tiers
                   if comparison_table[t]["delta_pp"] is not None]
    low_delta = comparison_table["small_micro"]["delta_pp"]
    small_micro_floor = TIER_NOISE_FLOOR_PP["small_micro"]
    small_micro_within_floor = (abs(low_delta) <= small_micro_floor) if low_delta is not None else None

    tok_ctrl_path = RUN_DIR / "token_usage_treatment.json"
    tok = json.loads(tok_ctrl_path.read_text()) if tok_ctrl_path.exists() else {}
    tok_repl_path = RUN_DIR / "token_usage_replication.json"
    tok_repl = json.loads(tok_repl_path.read_text()) if tok_repl_path.exists() else {}

    results = {
        "comparison_table": comparison_table,
        "mde": {"n_used": n_large_mid, "z": z, "mde_single_run_pp": mde_single_run_pp,
                "mde_5run_mean_pp": mde_5run_mean_pp,
                "method": "normal-approx 95% CI half-width for a binomial proportion "
                          "at p=0.5 (max-variance, conservative), n=13, propagated to "
                          "a 5-independent-run mean by dividing by sqrt(5)."},
        "modal_recommendation_changes": {"overall": modal_changes["overall"],
                                          "by_tier": dict(modal_changes["by_tier"]),
                                          "total": len(tids_all)},
        "modal_detail": modal_detail,
        "confound_check_output_length": confound,
        "nvda_case_study": nvda_case,
        "differential_test": {
            "high_recall_tier_deltas_pp": dict(zip(high_recall_tiers, high_deltas)),
            "small_micro_delta_pp": low_delta,
            "small_micro_floor_pp": small_micro_floor,
            "small_micro_within_its_own_floor": small_micro_within_floor,
        },
        "token_usage_treatment": tok,
        "token_usage_replication": tok_repl,
    }

    (RUN_DIR / "analysis_results.json").write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))

    progress = load_progress()
    progress["steps"]["step3_analysis"] = "done"
    save_progress(progress)
    return results


def main():
    if len(sys.argv) < 2:
        print("usage: test6_look_ahead.py [build_treatment|replicate|treatment|analyze]")
        return 1
    step = sys.argv[1]
    if step == "build_treatment":
        return step_build_treatment()
    elif step == "replicate":
        return step_replicate()
    elif step == "treatment":
        return step_treatment()
    elif step == "analyze":
        step_analyze()
        return 0
    else:
        print("unknown step")
        return 1


if __name__ == "__main__":
    sys.exit(main())
