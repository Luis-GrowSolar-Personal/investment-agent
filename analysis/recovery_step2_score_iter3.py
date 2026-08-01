#!/usr/bin/env python3
"""
Step 2 of 3 -- recovery from the 2026-07-06 TTD DB-timeout crash.

Scores iteration 3's patch (mitigation_track_record ambiguity, isolated
diff on ENPH 2022-04-26) against iteration 1's REAL accepted baseline
(13/84 unstable, 37.5% accuracy) -- exactly the same accept/reject logic
auto_iterate_prompt.py itself uses -- instead of assuming iteration 3 is
automatically the new best just because it's the most recent.

Run with:
    python3 recovery_step2_score_iter3.py

Wait for it to print "STEP 2 COMPLETE" and the ACCEPTED: True/False line
before running step 3.
"""

import json
from pathlib import Path

import pandas as pd

RUN_DIR = Path("data/auto_iterate/2026-07-06_082945")
ITER1, ITER3 = RUN_DIR / "iter1", RUN_DIR / "iter3"
FIELDS = ["thesis_health", "recommendation", "stumble_type", "mitigation_track_record"]

BEST_UNSTABLE = 13     # iteration 1's accepted result
BEST_ACCURACY = 37.5   # iteration 1's accepted result
TOLERANCE = 5.0        # default --accuracy-tolerance used throughout this run

DECISION_FILE = Path("recovery_decision.txt")


def stability(dfs):
    dfs = [d.fillna("<none>") for d in dfs]
    dates = sorted(set(dfs[0]["call_date"]) & set(dfs[1]["call_date"]) & set(dfs[2]["call_date"]))
    unstable = []
    for cd in dates:
        rows = [d.loc[d["call_date"] == cd].iloc[0] for d in dfs]
        for f in FIELDS:
            vals = [r[f] for r in rows]
            if len(set(vals)) > 1:
                unstable.append({"call_date": cd, "field": f, "values": vals})
    return len(unstable), unstable


def accuracy(*dfs):
    c = pd.concat(dfs, ignore_index=True)
    s = c[c["signal_correct"].notna()]
    correct = int(s["signal_correct"].astype(bool).sum())
    total = int(len(s))
    return (float(correct / total * 100) if total else 0.0), correct, total


def main():
    print("=== Step 2: scoring iteration 3 ===")
    ttd_path = ITER3 / "TTD_holdout.csv"
    if not ttd_path.exists():
        raise SystemExit(
            f"ERROR: {ttd_path} not found. Run recovery_step1_finish_ttd.sh first "
            f"and wait for it to print STEP 1 COMPLETE."
        )

    enph_dfs = [pd.read_csv(ITER3 / f"ENPH_run{n}.csv") for n in (1, 2, 3)]
    ttd_df = pd.read_csv(ttd_path)

    unstable_count, unstable_rows = stability(enph_dfs)
    accuracy_pct, correct, total = accuracy(enph_dfs[0], ttd_df)
    floor = BEST_ACCURACY - TOLERANCE
    accepted = bool(accuracy_pct >= floor and unstable_count < BEST_UNSTABLE)

    print(f"iter3 RESULT: unstable {unstable_count}/84   accuracy {correct}/{total} = {accuracy_pct:.1f}%")
    print(f"Compared against iter1 best: {BEST_UNSTABLE}/84 unstable, {BEST_ACCURACY}% accuracy, floor {floor:.1f}%")
    print(f"ACCEPTED: {accepted}")

    # Patch the true iter3 record into the original run's summary.json
    summary_path = RUN_DIR / "summary.json"
    summary = json.loads(summary_path.read_text())
    patch = json.loads((ITER3 / "patch.json").read_text())
    # Avoid duplicating the entry if this script is re-run
    summary["iterations"] = [it for it in summary["iterations"] if it.get("iter") != 3]
    summary["iterations"].append({
        "iter": 3,
        "unstable_count": unstable_count,
        "accuracy_pct": accuracy_pct,
        "correct": correct,
        "total": total,
        "patch": patch,
        "accepted": accepted,
    })
    summary_path.write_text(json.dumps(summary, indent=2))

    decision = "3" if accepted else "1"
    DECISION_FILE.write_text(decision)
    print("")
    print(f"Decision written to {DECISION_FILE}: seed next run from iter{decision}")
    print("")
    print("STEP 2 COMPLETE -- now run: zsh recovery_step3_resume.sh")


if __name__ == "__main__":
    main()
