#!/usr/bin/env python3
"""
variance_check.py — Measure run-to-run stability of the evaluator's
structured output.

Context:
    The backtest runner (backtest_runner.py) had been producing different
    values for fields like mitigation_track_record on identical transcripts
    across runs. That was traced to the Anthropic API default temperature
    of 1.0. temperature=0 has since been applied to the runner. This script
    verifies the fix by comparing three back-to-back ENPH runs.

Inputs (expected in analysis/data/):
    variance_ENPH_run1.csv
    variance_ENPH_run2.csv
    variance_ENPH_run3.csv

Output:
    A per-transcript stability report across four fields:
      - thesis_health
      - recommendation
      - stumble_type
      - mitigation_track_record

    And a summary of how many of the 36 (9 transcripts * 4 fields)
    combinations were stable vs. variable.

Usage:
    cd analysis && python3 variance_check.py
    python3 analysis/variance_check.py            # from repo root
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FIELDS_TO_CHECK = [
    "thesis_health",
    "recommendation",
    "stumble_type",
    "mitigation_track_record",
]

KEY_FIELD = "call_date"  # one transcript per call_date for a single ticker

# Resolve data dir relative to this file so the script works from any cwd.
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

RUN_FILES = [
    DATA_DIR / "variance_ENPH_run1.csv",
    DATA_DIR / "variance_ENPH_run2.csv",
    DATA_DIR / "variance_ENPH_run3.csv",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_runs() -> list[pd.DataFrame]:
    """Load all three variance CSVs. Fail loudly if any are missing."""
    missing = [p for p in RUN_FILES if not p.exists()]
    if missing:
        names = "\n  ".join(str(p) for p in missing)
        sys.exit(f"ERROR: missing variance CSV(s):\n  {names}")

    dfs = []
    for i, path in enumerate(RUN_FILES, start=1):
        df = pd.read_csv(path)
        # Some fields may come back as NaN (e.g. mitigation_track_record when
        # mitigation_argument_present is False). Normalize so comparisons work.
        df = df.fillna("<none>")
        df["_run"] = i
        dfs.append(df)
    return dfs


def compare_field(values: list) -> tuple[bool, str]:
    """Return (is_stable, display_string).

    is_stable == all three runs agree.
    display_string is always 'v1 | v2 | v3' for readability.
    """
    stable = len(set(values)) == 1
    return stable, " | ".join(str(v) for v in values)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    dfs = load_runs()

    # Sanity check: all three runs should have the same set of call_dates.
    call_date_sets = [set(df[KEY_FIELD]) for df in dfs]
    if not (call_date_sets[0] == call_date_sets[1] == call_date_sets[2]):
        print("WARNING: run CSVs do not cover the same set of transcripts.")
        print(f"  run1: {sorted(call_date_sets[0])}")
        print(f"  run2: {sorted(call_date_sets[1])}")
        print(f"  run3: {sorted(call_date_sets[2])}")

    call_dates = sorted(call_date_sets[0] & call_date_sets[1] & call_date_sets[2])

    # Prompt version check — a silent mismatch here would invalidate the test.
    versions = [df["prompt_version"].unique().tolist() for df in dfs]
    flat_versions = {v for vs in versions for v in vs}
    print("=" * 72)
    print("VARIANCE CHECK — ENPH, 3 runs")
    print("=" * 72)
    print(f"Prompt versions present across runs: {sorted(flat_versions)}")
    if len(flat_versions) > 1:
        print("WARNING: runs span multiple prompt versions — variance is "
              "confounded with prompt change.")
    print(f"Transcripts compared: {len(call_dates)}")
    print(f"Fields compared per transcript: {len(FIELDS_TO_CHECK)}")
    print(f"Total field-transcript combinations: "
          f"{len(call_dates) * len(FIELDS_TO_CHECK)}")
    print()

    # Per-transcript comparison.
    unstable_rows: list[tuple[str, str, str]] = []  # (call_date, field, display)
    stable_count = 0
    variable_count = 0

    for cd in call_dates:
        rows = [df.loc[df[KEY_FIELD] == cd].iloc[0] for df in dfs]
        transcript_unstable: list[tuple[str, str]] = []
        for field in FIELDS_TO_CHECK:
            values = [row[field] for row in rows]
            stable, display = compare_field(values)
            if stable:
                stable_count += 1
            else:
                variable_count += 1
                transcript_unstable.append((field, display))
                unstable_rows.append((cd, field, display))

        status = "stable" if not transcript_unstable else "UNSTABLE"
        print(f"[{status:8}] {cd}")
        for field, display in transcript_unstable:
            print(f"              {field}: {display}")

    # Summary block.
    total = stable_count + variable_count
    print()
    print("-" * 72)
    print("SUMMARY")
    print("-" * 72)
    print(f"  stable:   {stable_count} / {total}")
    print(f"  variable: {variable_count} / {total}")
    if total:
        pct = 100.0 * stable_count / total
        print(f"  stability rate: {pct:.1f}%")

    if variable_count == 0:
        print()
        print("RESULT: temperature=0 fix appears to have eliminated "
              "run-to-run variance on the four tracked fields.")
        print("NEXT: per handoff decision tree, revert prompt to v3 and "
              "diagnose ENPH 2023-10-26 and 2024-04-23 specifically.")
    else:
        print()
        print("RESULT: variance remains even with temperature=0.")
        print("NEXT: consider majority-vote across N=3 runs, or drop the "
              "unstable field(s) from the signal-accuracy measurement.")
        print()
        print("Unstable field-transcript combinations:")
        for cd, field, display in unstable_rows:
            print(f"  {cd}  {field:24s}  {display}")

    return 0 if variable_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
