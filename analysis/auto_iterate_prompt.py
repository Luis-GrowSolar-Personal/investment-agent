#!/usr/bin/env python3
"""
auto_iterate_prompt.py — Autonomous prompt-refinement harness for
EVALUATION_PROMPT.md.

Context: manual iteration (v6 -> v9 -> v10, 2026-07-05) showed that
prompt-side fixes for run-to-run instability are real and findable, but
each round requires reading raw model output side-by-side to isolate
the specific rubric ambiguity causing a disagreement -- a generic "make
it more stable" instruction is not enough (v9 proved that: a
plausible-sounding fix regressed stability from 21.4% to 29.8% before
being caught). This script automates that same diagnose -> patch ->
retest loop instead of relaying logs back and forth by hand.

GUARDRAILS (read before running unattended):

1. Stability is NOT the sole objective. A prompt that always outputs
   "Hold" / "mixed" would be perfectly stable and useless. Every
   candidate patch is scored on stability AND checked against a
   held-out accuracy floor (TTD, never used for tuning) before being
   accepted. The floor is RELATIVE, not the historical v6 figure
   (60%, 9/15) -- that number was measured on a much smaller, older
   ENPH+TTD transcript set and is not comparable to today's larger
   history (confirmed 2026-07-05: today's full-history baseline
   scored 37.5% on the same measurement basis v6 scored 60% on a
   smaller sample -- using 60% as a hard floor here would reject
   every candidate regardless of patch quality). Instead, the floor
   is set from THIS run's own first measured baseline (iteration 1,
   or the seeded iteration) minus --accuracy-tolerance percentage
   points (default 5). A patch that drops accuracy more than that
   tolerance below where this run started is REJECTED regardless of
   its stability number.

2. Best-so-far, not most-recent. The loop never builds on a rejected
   patch. Each round proposes a new patch against the best ACCEPTED
   version so far, so a bad iteration can't drag the next one down
   with it (this is the exact failure mode that made v9 -> v10 costly
   to recover from when done by hand).

3. TTD is held out from tuning. The diagnostic step only ever looks at
   ENPH disagreements to decide what to patch. TTD is used only to
   check the patch didn't break something -- never fed to the
   patch-proposing model as an example to fix. This is meant to guard
   against overfitting prompt wording to this one ticker's 21
   transcripts.

4. NO AUTO-PROMOTION. This script never touches server/lib/versions.js
   or production. It writes the best version found back to
   EVALUATION_PROMPT.md on disk and stops. Promotion is a manual
   decision, same as the existing Promotion Gate practice already in
   this codebase (see PROMOTION_GATE.md, versions.js history).

5. Full audit trail. Every iteration's prompt version, patch reasoning,
   scores, and accept/reject decision is written to
   data/auto_iterate/<run_id>/ and appended to EVALUATION_PROMPT.md's
   own iteration log -- nothing here should be a black box afterward.

6. Seeding never trusts live disk state. --seed-run-dir requires an
   explicit prompt-text snapshot (<seed-dir>/prompt_candidate.md, or
   --seed-prompt-file) rather than reading whatever's currently in
   EVALUATION_PROMPT.md. Confirmed 2026-07-06: a crashed run left a
   REJECTED candidate patch sitting on disk, and the next run silently
   inherited it as its "clean" baseline -- the run's whole accept/reject
   bookkeeping (score numbers) stayed correct, but the actual prompt
   text being tested and reverted-to was wrong for the entire run,
   with no error raised. Manually caught and fixed after the fact.

7. A failed patch application doesn't get retried on the same example
   forever. Confirmed 2026-07-06: 8 of 9 iterations in one run were
   wasted retrying one identical failing diagnosis (patch's old_string
   never matched) because prev_unstable_rows/prev_iter_dir were never
   advanced after a failure -- the loop looked like it was working
   (no errors, iterations counting up) but was making zero progress.
   Fixed via a per-dataset `tried_examples` exclusion set so a failed
   attempt moves on to the next-most-unstable example instead.

Usage:
    cd analysis
    python3 auto_iterate_prompt.py
    python3 auto_iterate_prompt.py --max-iterations 5 --target-unstable 5

Cost: each iteration runs 3x ENPH (21 transcripts) + 1x TTD (~6
transcripts) through the evaluator, plus 1-2 meta-model calls for
diagnosis/patching. At ~$0.50-1/full ENPH+TTD pass (rough, matches
today's ~$30 all-in for the day's manual runs), budget roughly
$3-6/iteration, $30-60 for a full 10-round run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_PATH = SCRIPT_DIR.parent / "docs" / "EVALUATION_PROMPT.md"
DATA_DIR = SCRIPT_DIR / "data"

env_path = SCRIPT_DIR.parent / ".env"
load_dotenv(env_path)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    sys.exit("ERROR: ANTHROPIC_API_KEY not found -- check .env")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# The model used to DIAGNOSE and PATCH the prompt. Deliberately separate
# from MODEL in backtest_runner.py (the evaluator model under test) --
# keep this in sync with server/lib/versions.js by hand, same caveat as
# backtest_runner.py's MODEL constant (no cross-language auto-sync).
META_MODEL = "claude-sonnet-4-6"

FIELDS_TO_CHECK = ["thesis_health", "recommendation", "stumble_type", "mitigation_track_record"]
KEY_FIELD = "call_date"

# Recorded baselines -- see EVALUATION_PROMPT.md iteration log.
V6_UNSTABLE_COUNT = 18       # out of 84 (21 transcripts x 4 fields), v6
V6_ACCURACY_PCT = 60.0       # ENPH+TTD combined, 9/15, v6 baseline

TODAY = datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str, indent: int = 0) -> None:
    """Timestamped print so a stalled step is visible instead of silent."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[{ts}] {prefix}{msg}", flush=True)


class Heartbeat:
    """Prints a '...still running (Ns)' line every `interval` seconds while
    inside a `with` block that has no output of its own (e.g. a single
    blocking API call). Runs in a background thread so it doesn't block."""

    def __init__(self, label: str, interval: int = 15):
        self.label = label
        self.interval = interval
        self._stop = None
        self._thread = None

    def __enter__(self):
        import threading
        self._stop = threading.Event()

        def _tick():
            start = datetime.now()
            while not self._stop.wait(self.interval):
                elapsed = int((datetime.now() - start).total_seconds())
                log(f"...{self.label} still running ({elapsed}s)", indent=2)

        self._thread = threading.Thread(target=_tick, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=1)


# ---------------------------------------------------------------------------
# Running the evaluator
# ---------------------------------------------------------------------------

def run_backtest(ticker: str, save_evals: bool = True) -> pd.DataFrame:
    """Run backtest_runner.py for one ticker, streaming its output live so a
    long/stuck run is visible instead of appearing hung until it exits."""
    cmd = [sys.executable, "-u", "backtest_runner.py", "--ticker", ticker]
    if save_evals:
        cmd.append("--save-evals")
    log(f"running: {' '.join(cmd)}", indent=2)

    start = datetime.now()
    proc = subprocess.Popen(
        cmd, cwd=SCRIPT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    last_line_time = datetime.now()
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.strip():
            print(f"        {line}", flush=True)
        last_line_time = datetime.now()
    proc.wait()
    elapsed = (datetime.now() - start).total_seconds()

    if proc.returncode != 0:
        raise RuntimeError(f"backtest_runner.py failed for {ticker} (exit {proc.returncode})")
    log(f"{ticker} pass finished in {elapsed:.0f}s", indent=2)

    # Don't trust a fixed TODAY string -- backtest_runner.py computes its own
    # date fresh inside the subprocess, and a run spanning midnight (this loop
    # runs for hours) will write a DIFFERENT date than whatever TODAY was when
    # THIS script started. Instead, find whichever backtest_*_<TICKER>.csv is
    # newest and was created after this subprocess launched.
    candidates = [
        p for p in DATA_DIR.glob(f"backtest_*_{ticker.upper()}.csv")
        if p.stat().st_mtime >= start.timestamp()
    ]
    if not candidates:
        raise RuntimeError(
            f"No backtest_*_{ticker.upper()}.csv found with mtime after "
            f"{start.isoformat()} -- backtest_runner.py may not have written output."
        )
    csv_path = max(candidates, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(csv_path)
    return df, csv_path


def archive_run(iter_dir: Path, csv_path: Path, label: str) -> Path:
    """Move a backtest CSV + its evals/ dir into the iteration's archive."""
    dest_csv = iter_dir / f"{label}.csv"
    shutil.move(str(csv_path), str(dest_csv))
    evals_src = DATA_DIR / "evals"
    if evals_src.exists():
        dest_evals = iter_dir / f"evals_{label}"
        if dest_evals.exists():
            shutil.rmtree(dest_evals)
        shutil.move(str(evals_src), str(dest_evals))
    return dest_csv


def compute_accuracy(*dfs: pd.DataFrame) -> tuple[float, int, int]:
    """Combined signal accuracy across one or more scored DataFrames."""
    combined = pd.concat(dfs, ignore_index=True)
    scored = combined[combined["signal_correct"].notna()]
    correct = int(scored["signal_correct"].astype(bool).sum())
    total = int(len(scored))
    # Cast to native float explicitly -- pandas/numpy arithmetic here produces
    # numpy.float64, and numpy 2.0 renamed its bool scalar's __class__.__name__
    # to literally "bool", which makes any numpy-typed value that later feeds
    # into a Python `and`/`or` short-circuit (see `accepted` in main()) look
    # like a plain bool in error messages while still failing json.dumps().
    pct = float(correct / total * 100) if total else 0.0
    return pct, correct, total


def compute_stability(dfs: list[pd.DataFrame]) -> tuple[int, list[dict]]:
    """Same logic as variance_check.py, returned as data instead of printed."""
    dfs = [d.fillna("<none>") for d in dfs]
    call_dates = sorted(set(dfs[0][KEY_FIELD]) & set(dfs[1][KEY_FIELD]) & set(dfs[2][KEY_FIELD]))

    unstable = []
    for cd in call_dates:
        rows = [d.loc[d[KEY_FIELD] == cd].iloc[0] for d in dfs]
        for field in FIELDS_TO_CHECK:
            values = [r[field] for r in rows]
            if len(set(values)) > 1:
                unstable.append({"call_date": cd, "field": field, "values": values})

    return len(unstable), unstable


# ---------------------------------------------------------------------------
# Diagnosis + patch proposal
# ---------------------------------------------------------------------------

def pick_diagnostic_example(
    unstable: list[dict], iter_dir: Path, exclude: set[tuple[str, str]] = frozenset()
) -> dict | None:
    """
    Pick the most useful single unstable field-transcript combination to
    hand to the meta-model: prefer the dominant field (most unstable
    rows this round), and within that field prefer a date where it's the
    ONLY unstable field (a clean isolated diff, same as the manual
    2023-02-07 example that worked).

    `exclude` is a set of (field, call_date) pairs already attempted (and
    failed to apply) against this SAME unstable-rows dataset -- without
    this, a patch-application failure causes the exact same example to be
    picked again next iteration, forever, since the diagnostic input never
    changes on its own. See 2026-07-06 run: 8 of 9 iterations wasted
    retrying one identical failing diagnosis instead of trying the next.
    """
    candidates_all = [
        row for row in unstable
        if (row["field"], row["call_date"]) not in exclude
    ]
    if not candidates_all:
        return None

    field_counts: dict[str, int] = {}
    for row in candidates_all:
        field_counts[row["field"]] = field_counts.get(row["field"], 0) + 1
    dominant_field = max(field_counts, key=field_counts.get)

    by_date: dict[str, list[dict]] = {}
    for row in unstable:  # isolation check uses ALL unstable rows, not just candidates_all
        by_date.setdefault(row["call_date"], []).append(row)

    candidates = [row for row in candidates_all if row["field"] == dominant_field]
    isolated = [row for row in candidates if len(by_date[row["call_date"]]) == 1]
    chosen = isolated[0] if isolated else candidates[0]

    # Find two runs whose values actually differ, and load their raw eval text.
    values = chosen["values"]
    idx_a, idx_b = 0, next(i for i in range(1, 3) if values[i] != values[0])
    date = chosen["call_date"]
    text_a = (iter_dir / f"evals_ENPH_run{idx_a + 1}" / f"ENPH_{date}.txt").read_text()
    text_b = (iter_dir / f"evals_ENPH_run{idx_b + 1}" / f"ENPH_{date}.txt").read_text()

    return {
        "field": dominant_field,
        "call_date": date,
        "value_a": values[idx_a],
        "value_b": values[idx_b],
        "text_a": text_a,
        "text_b": text_b,
    }


def propose_patch(prompt_text: str, example: dict) -> dict:
    """Call the meta-model to diagnose the ambiguity and propose a minimal patch."""
    meta_prompt = f"""You are diagnosing run-to-run instability in an earnings-call \
evaluation prompt used by an investment analysis tool. The SAME prompt, SAME \
transcript, SAME model, temperature=0, produced two DIFFERENT values for the \
field `{example['field']}` on transcript call_date {example['call_date']}:

Run A produced: {example['value_a']}
Run B produced: {example['value_b']}

Here is Run A's full evaluator output:
---RUN A---
{example['text_a']}
---END RUN A---

Here is Run B's full evaluator output:
---RUN B---
{example['text_b']}
---END RUN B---

Here is the CURRENT full prompt that produced both runs:
---PROMPT---
{prompt_text}
---END PROMPT---

Your task, in order:
1. Diagnose the SPECIFIC ambiguity in the prompt's wording that let both \
readings be defensible. Look for: undefined combination rules, missing \
edge cases, vague thresholds, or unaddressed input conditions (e.g. what \
to do when certain context isn't provided). Do not guess broadly -- find \
the actual sentence or missing rule.
2. Propose the SMALLEST possible patch to the prompt that closes this \
specific gap, without rewriting unrelated sections, without changing the \
decision matrix, position sizing logic, or any Type A/B/cap rule. A \
narrow, targeted patch is strongly preferred over a broad rewrite -- a \
prior broad rewrite attempt (v9) made stability WORSE, not better, \
precisely because it introduced more surface area for new ambiguity.

Respond with ONLY a JSON object (no markdown fences, no commentary \
outside the JSON), with this exact shape:
{{
  "diagnosis": "1-3 sentences describing the specific ambiguity found",
  "old_string": "the EXACT existing text to replace -- must appear \
verbatim and exactly once in the prompt above",
  "new_string": "the replacement text"
}}
"""

    log(f"calling {META_MODEL} to diagnose + propose patch...", indent=2)
    with Heartbeat("meta-model call"):
        response = client.messages.create(
            model=META_MODEL,
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": meta_prompt}],
        )
    log(f"meta-model responded ({response.usage.output_tokens} output tokens)", indent=2)
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Meta-model did not return valid JSON: {e}\nRaw:\n{raw}")


def apply_patch(prompt_text: str, patch: dict) -> str:
    """Apply old_string -> new_string, requiring an exact unique match."""
    count = prompt_text.count(patch["old_string"])
    if count != 1:
        raise ValueError(
            f"old_string appears {count} times (need exactly 1) -- rejecting patch"
        )
    return prompt_text.replace(patch["old_string"], patch["new_string"])


def bump_version_and_log(prompt_text: str, new_version_label: str, diagnosis: str) -> str:
    """Bump the header version line and append an auto-generated iteration log entry."""
    prompt_text = re.sub(
        r'^# Version: .*$',
        f'# Version: {new_version_label} (auto-iterate candidate — pending gate)',
        prompt_text,
        count=1,
        flags=re.MULTILINE,
    )
    entry = (
        f"#\n#   {new_version_label} ({datetime.now().date()}, auto_iterate_prompt.py): "
        f"{diagnosis}\n"
    )
    # Insert right after the "# Iteration log:" marker's existing block --
    # simplest safe approach: insert right before the "---" line that ends
    # the header comment block.
    marker = "\n---\n"
    idx = prompt_text.find(marker)
    if idx == -1:
        raise RuntimeError("Could not find header/body separator '---' in prompt file")
    return prompt_text[:idx] + entry + prompt_text[idx:]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--target-unstable", type=int, default=0,
                         help="Stop early if unstable count reaches this or below")
    parser.add_argument("--patience", type=int, default=3,
                         help="Stop early after this many rounds with no improvement")
    parser.add_argument("--seed-run-dir", type=str, default=None,
                         help="Path to a previous run's directory (e.g. "
                              "data/auto_iterate/2026-07-05_203925) containing a "
                              "completed baseline iteration to reuse instead of "
                              "re-running it. The prompt is NOT re-scored -- the "
                              "seeded iteration's ENPH/TTD CSVs are read directly "
                              "and the first new iteration goes straight to "
                              "diagnosing + patching against that data.")
    parser.add_argument("--seed-iter", type=int, default=1,
                         help="Which iteration number inside --seed-run-dir to use "
                              "as the seed (default: 1, i.e. that run's baseline pass)")
    parser.add_argument("--already-tried", action="append", default=[],
                         metavar="FIELD:CALL_DATE",
                         help="Pre-populate the excluded-examples set with a "
                              "(field, call_date) pair already known to fail or "
                              "already tested and rejected in a prior run, so the "
                              "first iteration skips straight to the next candidate "
                              "instead of re-running ~2 hours to reconfirm a known "
                              "result. Repeatable, e.g. "
                              "--already-tried recommendation:2022-02-08")
    parser.add_argument("--seed-prompt-file", type=str, default=None,
                         help="Explicit path to the exact prompt text that produced "
                              "the seeded scores. If omitted, defaults to "
                              "<seed-run-dir>/iter<seed-iter>/prompt_candidate.md. "
                              "REQUIRED (one way or the other) -- this script will "
                              "NOT fall back to trusting whatever is currently in "
                              "EVALUATION_PROMPT.md, because that file can be left "
                              "in an inconsistent 'candidate, not yet judged' state "
                              "by a crashed prior run (this happened on 2026-07-06: "
                              "a crash left a rejected candidate on disk, and the "
                              "next run silently inherited it as its 'baseline').")
    parser.add_argument("--accuracy-tolerance", type=float, default=5.0,
                         help="Reject a patch if its accuracy drops more than this "
                              "many percentage points BELOW the measured baseline "
                              "(iteration 1 or the seeded iteration) -- NOT compared "
                              "against the historical V6_ACCURACY_PCT constant, which "
                              "was measured on a much smaller transcript set (9/15) "
                              "and is not a fair comparison against today's larger "
                              "ENPH/TTD history (40+ scored transcripts). See "
                              "2026-07-05 auto-iterate run: v10 baseline scored 37.5% "
                              "on today's full set vs the old 60% figure from a "
                              "smaller historical sample -- using the old number as a "
                              "hard floor would reject every candidate regardless of "
                              "patch quality.")
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = DATA_DIR / "auto_iterate" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.json"
    summary = {"run_id": run_id, "iterations": []}

    log(f"=== auto_iterate_prompt.py run {run_id} ===")
    log(f"Max iterations: {args.max_iterations}, target unstable: {args.target_unstable}, "
        f"patience: {args.patience}")
    log(f"Run log directory: {run_dir}")

    best_unstable = None
    best_accuracy = None
    accuracy_floor = None  # set once a baseline (seeded or iteration-1) is known;
                            # NOT the historical V6_ACCURACY_PCT constant -- see
                            # --accuracy-tolerance help text for why.
    rounds_without_improvement = 0
    prev_unstable_rows = None
    prev_iter_dir = None
    tried_examples: set[tuple[str, str]] = set()  # (field, call_date) already
                                                    # attempted against the current
                                                    # prev_unstable_rows dataset

    for spec in args.already_tried:
        try:
            field, call_date = spec.split(":", 1)
        except ValueError:
            sys.exit(f"ERROR: --already-tried expects FIELD:CALL_DATE, got {spec!r}")
        tried_examples.add((field, call_date))
        log(f"Pre-excluding known-tried example: {field} @ {call_date}")

    if args.seed_run_dir:
        seed_dir = Path(args.seed_run_dir) / f"iter{args.seed_iter}"
        log(f"Seeding baseline from {seed_dir} (skipping re-run of that iteration)")

        # Resolve the EXACT prompt text that produced the seeded scores.
        # Deliberately NOT falling back to PROMPT_PATH.read_text() here --
        # EVALUATION_PROMPT.md can be left in an inconsistent "candidate,
        # not yet judged" state by a crashed prior run (confirmed 2026-07-06:
        # a crash left a rejected candidate on disk, and the next run
        # silently inherited it as its "clean" baseline, corrupting the
        # whole run's accept/reject bookkeeping without any error).
        if args.seed_prompt_file:
            seed_prompt_path = Path(args.seed_prompt_file)
        else:
            seed_prompt_path = seed_dir / "prompt_candidate.md"
        if not seed_prompt_path.exists():
            sys.exit(
                f"ERROR: {seed_prompt_path} not found. Refusing to fall back to "
                f"whatever is currently in EVALUATION_PROMPT.md -- that file's "
                f"state is not trustworthy after a crash (see 2026-07-06 incident). "
                f"Pass --seed-prompt-file pointing to the exact prompt text that "
                f"produced the seeded scores (e.g. a manually-saved copy of "
                f"EVALUATION_PROMPT.md from before that iteration ran)."
            )
        best_prompt_text = seed_prompt_path.read_text()
        log(f"Seed prompt text: {seed_prompt_path}")

        try:
            enph_dfs = [pd.read_csv(seed_dir / f"ENPH_run{n}.csv") for n in (1, 2, 3)]
            ttd_csv = seed_dir / "TTD_holdout.csv"
            if not ttd_csv.exists():
                sys.exit(
                    f"ERROR: {ttd_csv} not found. That iteration may not have "
                    f"finished (or was run before TTD-holdout support existed). "
                    f"Wait for it to complete, or seed from a different iteration."
                )
            ttd_df = pd.read_csv(ttd_csv)
        except FileNotFoundError as e:
            sys.exit(f"ERROR: seed files missing: {e}")

        best_unstable, prev_unstable_rows = compute_stability(enph_dfs)
        best_accuracy, correct, total = compute_accuracy(enph_dfs[0], ttd_df)
        accuracy_floor = best_accuracy - args.accuracy_tolerance
        prev_iter_dir = seed_dir
        log(f"Seeded: unstable {best_unstable}/84, accuracy {correct}/{total} "
            f"= {best_accuracy:.1f}%")
        log(f"Accuracy floor for this run: {accuracy_floor:.1f}% "
            f"(seeded {best_accuracy:.1f}% minus {args.accuracy_tolerance}pp tolerance -- "
            f"NOT the historical v6 60% figure, which was measured on a much smaller "
            f"transcript set and isn't comparable to today's larger history)")
    else:
        best_prompt_text = PROMPT_PATH.read_text()

    # Force disk into a known-consistent state immediately, matching
    # best_prompt_text exactly -- don't wait for the loop's first iteration
    # to do this, in case anything inspects EVALUATION_PROMPT.md before then.
    PROMPT_PATH.write_text(best_prompt_text)

    for i in range(1, args.max_iterations + 1):
        iter_start = datetime.now()
        iter_dir = run_dir / f"iter{i}"
        iter_dir.mkdir(exist_ok=True)
        log("")
        log(f"=== Iteration {i}/{args.max_iterations} ===")

        # Write the candidate we're about to test (starts from best-so-far).
        PROMPT_PATH.write_text(best_prompt_text)

        # Diagnose+patch as soon as ANY baseline is known (either this run's own
        # iteration 1, or a seeded one from --seed-run-dir) -- otherwise this is
        # a fresh run's iteration 1, which just scores the prompt as-is first.
        patch_info = None
        if best_unstable is not None:
            log("Step 1/3: diagnosing last round's instability...", indent=1)
            # Diagnose off the LAST iteration's ENPH runs -- either the
            # previous iteration in THIS run, or the seeded directory on
            # the very first iteration of a seeded run.
            example = pick_diagnostic_example(prev_unstable_rows, prev_iter_dir, exclude=tried_examples)
            if example is None:
                log("No untried unstable rows left to diagnose from this data — "
                    "stopping early (converged, or exhausted this dataset).", indent=1)
                break
            tried_examples.add((example["field"], example["call_date"]))
            log(f"picked: {example['field']} @ {example['call_date']} "
                f"({example['value_a']!r} vs {example['value_b']!r})", indent=2)
            try:
                patch = propose_patch(best_prompt_text, example)
                candidate_text = apply_patch(best_prompt_text, patch)
                candidate_text = bump_version_and_log(
                    candidate_text, f"v10+auto{i}", patch["diagnosis"]
                )
                (iter_dir / "patch.json").write_text(json.dumps(patch, indent=2))
                log(f"diagnosis: {patch['diagnosis']}", indent=2)
                log("patch applied (old_string matched exactly once)", indent=2)
            except (RuntimeError, ValueError) as e:
                log(f"Patch proposal/application failed: {e} — skipping this round.", indent=1)
                summary["iterations"].append({"iter": i, "status": "patch_failed", "error": str(e)})
                summary_path.write_text(json.dumps(summary, indent=2))
                continue
            PROMPT_PATH.write_text(candidate_text)
            patch_info = patch
        else:
            log("Step 1/3: scoring current prompt as-is (no patch this round — establishing baseline)", indent=1)

        # Snapshot the exact prompt text being scored this round, regardless
        # of whether it ends up accepted or rejected -- so any iteration's
        # full prompt can be inspected later without replaying patches in
        # sequence by hand.
        (iter_dir / "prompt_candidate.md").write_text(PROMPT_PATH.read_text())

        # --- Score this candidate: 3x ENPH (stability) + 1x TTD (held-out accuracy) ---
        log("Step 2/3: running stability gate (3x ENPH, ~21 transcripts each)...", indent=1)
        enph_dfs = []
        for run_n in range(1, 4):
            log(f"ENPH run {run_n}/3...", indent=2)
            df, csv_path = run_backtest("ENPH", save_evals=True)
            archive_run(iter_dir, csv_path, f"ENPH_run{run_n}")
            enph_dfs.append(df)

        log("Step 3/3: running held-out accuracy check (1x TTD, never used for tuning)...", indent=1)
        ttd_df, ttd_csv = run_backtest("TTD", save_evals=True)
        archive_run(iter_dir, ttd_csv, "TTD_holdout")

        unstable_count, unstable_rows = compute_stability(enph_dfs)
        accuracy_pct, correct, total = compute_accuracy(enph_dfs[0], ttd_df)

        iter_elapsed = (datetime.now() - iter_start).total_seconds()
        log(f"RESULT: unstable {unstable_count}/84   accuracy (ENPH run1 + TTD) "
            f"{correct}/{total} = {accuracy_pct:.1f}%   (iteration took {iter_elapsed/60:.1f} min)", indent=1)

        # First baseline of a FRESH (non-seeded) run: establish the accuracy
        # floor here, relative to what this evaluator actually scores on
        # today's transcript set -- not the historical V6_ACCURACY_PCT
        # constant, which was measured on a much smaller sample and would
        # reject every future candidate if used as a hard floor here. If
        # --seed-run-dir was used, accuracy_floor is already set before the
        # loop started and this is a no-op.
        if accuracy_floor is None:
            accuracy_floor = accuracy_pct - args.accuracy_tolerance
            log(f"Accuracy floor for this run: {accuracy_floor:.1f}% "
                f"(this baseline's {accuracy_pct:.1f}% minus "
                f"{args.accuracy_tolerance}pp tolerance)", indent=1)

        # bool(...) wrapper is deliberate, not decorative -- see compute_accuracy()
        # comment. Without it, a numpy-typed operand short-circuiting through
        # `and`/`or` can silently produce a numpy bool that LOOKS like a plain
        # bool in tracebacks but still breaks json.dumps().
        accepted = bool(
            accuracy_pct >= accuracy_floor
            and (best_unstable is None or unstable_count < best_unstable)
        )

        record = {
            "iter": i,
            "unstable_count": unstable_count,
            "accuracy_pct": accuracy_pct,
            "correct": correct,
            "total": total,
            "patch": patch_info,
            "accepted": accepted,
            "elapsed_sec": iter_elapsed,
        }
        summary["iterations"].append(record)
        summary_path.write_text(json.dumps(summary, indent=2))

        if accepted:
            log(f"ACCEPTED — new best (was {best_unstable}, now {unstable_count})", indent=1)
            best_prompt_text = PROMPT_PATH.read_text()
            best_unstable = unstable_count
            best_accuracy = accuracy_pct
            rounds_without_improvement = 0
        else:
            reason = "accuracy below this run's floor" if accuracy_pct < accuracy_floor else "no stability improvement"
            log(f"REJECTED ({reason}) — reverting to best-known version", indent=1)
            rounds_without_improvement += 1
            if best_unstable is None:
                # First iteration itself failed the accuracy floor -- unusual,
                # but keep going from the original prompt rather than stall.
                best_unstable = unstable_count
                best_accuracy = accuracy_pct

        prev_unstable_rows = unstable_rows
        prev_iter_dir = iter_dir
        tried_examples = set()  # fresh scoring data -- old exclusions no longer apply

        if best_unstable is not None and best_unstable <= args.target_unstable:
            log(f"Target unstable count ({args.target_unstable}) reached — stopping.")
            break
        if rounds_without_improvement >= args.patience:
            log(f"No improvement in {args.patience} consecutive rounds — stopping early.")
            break

    # Always leave EVALUATION_PROMPT.md at the best-known version, not
    # whatever the last (possibly rejected) iteration left behind.
    PROMPT_PATH.write_text(best_prompt_text)
    (run_dir / "best_prompt.md").write_text(best_prompt_text)

    # Write the final verdict INTO summary.json, not just the console --
    # this is the field to check to answer "did the run succeed" without
    # having captured the live output.
    #
    # Stability comparison against V6_UNSTABLE_COUNT is valid -- both use the
    # same 21-transcript ENPH set (84 = 21 x 4 fields), unchanged. Accuracy
    # comparison against V6_ACCURACY_PCT is NOT valid -- that figure (60%,
    # 9/15) was measured on a much smaller, older ENPH+TTD transcript set.
    # accuracy_floor (this run's own baseline minus tolerance) is the number
    # that actually gated acceptance during this run.
    improved_stability = best_unstable is not None and best_unstable < V6_UNSTABLE_COUNT
    summary["result"] = {
        "best_unstable_count": best_unstable,
        "best_accuracy_pct": best_accuracy,
        "accuracy_floor_used": accuracy_floor,
        "v6_baseline_unstable_count": V6_UNSTABLE_COUNT,
        "v6_baseline_accuracy_pct_NOTE": (
            f"{V6_ACCURACY_PCT}% -- measured on a smaller transcript set, "
            f"NOT comparable to best_accuracy_pct above, informational only"
        ),
        "improved_stability_over_v6": improved_stability,
        "iterations_run": len(summary["iterations"]),
        "final_prompt_path": str(run_dir / "best_prompt.md"),
        "promoted_to_production": False,
        "note": "NOT auto-promoted. Review before touching server/lib/versions.js.",
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    log("")
    log("=== auto_iterate_prompt.py finished ===")
    log(f"Best result: {best_unstable}/84 unstable, {best_accuracy:.1f}% accuracy "
        f"(accuracy floor used this run: {accuracy_floor:.1f}%; "
        f"v6 stability baseline for reference: {V6_UNSTABLE_COUNT}/84)")
    log(f"Improved stability over v6: {improved_stability}")
    log(f"Full run log: {run_dir}")
    log(f"Final result written to: {summary_path}")
    log("EVALUATION_PROMPT.md has been updated to the best version found.")
    log("NOT auto-promoted. Review the diagnosis log and run the full run_v9_gate.sh")
    log("+ run_v9_gate_b.sh one more time before touching server/lib/versions.js.")


if __name__ == "__main__":
    main()
