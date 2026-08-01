#!/bin/bash
#
# run_v9_gate.sh — Gate A ONLY: stability check for EVALUATION_PROMPT.md v9.
#
# Stops automatically after Gate A so results can be reviewed before
# spending API calls on Gate B (accuracy). Gate B lives in
# run_v9_gate_b.sh — run it manually, only after Gate A looks good.
#
# Always runs with --save-evals so the raw model output for every
# transcript is on disk afterward. Diagnosing an anomaly (e.g. a
# missing structured block) should never require re-running the whole
# battery just to see what the model actually said -- that's what
# burned an extra full pass the first time this gate ran.
#
# Each of the 3 runs evaluates the same 21 transcripts, so raw evals
# get archived per-run (data/evals_ENPH_run{1,2,3}/) instead of being
# overwritten by the next run.
#
# Also logs each call's stop_reason (see backtest_runner.py
# evaluate_transcript()) -- if a "No structured block found" warning
# shows up below, check whether the matching call above it says
# stop_reason=max_tokens. That distinguishes "model ran out of room
# before finishing" (a token-budget problem) from "model finished but
# didn't follow the output format" (a prompt problem) -- two different
# fixes. The saved eval text for that transcript is the definitive
# answer either way.
#
# Usage:
#   cd analysis
#   ./run_v9_gate.sh
#   tail -f data/v9_gate_a.log
#
# Prerequisite: EVALUATION_PROMPT.md header must say version v9 (or
# whatever candidate version you're gating) before running this.

set -e

cd "$(dirname "$0")"

LOG="data/v9_gate_a.log"
TODAY=$(date +%F)

echo "=== v9 Gate A (stability) run started $(date) ===" | tee "$LOG"

for i in 1 2 3; do
  echo "" | tee -a "$LOG"
  echo "--- Run $i/3 ---" | tee -a "$LOG"
  python3 backtest_runner.py --ticker ENPH --save-evals 2>&1 | tee -a "$LOG"

  SRC="data/backtest_${TODAY}_ENPH.csv"
  DEST="data/variance_ENPH_run${i}.csv"

  if [ ! -f "$SRC" ]; then
    echo "ERROR: expected output $SRC not found — run $i may have failed. Aborting." | tee -a "$LOG"
    exit 1
  fi

  mv "$SRC" "$DEST"
  echo "Saved $DEST" | tee -a "$LOG"

  if [ -d "data/evals" ]; then
    EVALS_DEST="data/evals_ENPH_run${i}"
    rm -rf "$EVALS_DEST"
    mv "data/evals" "$EVALS_DEST"
    echo "Archived raw evals → $EVALS_DEST/" | tee -a "$LOG"
  fi
done

echo "" | tee -a "$LOG"
echo "--- Comparing stability across the 3 runs (v6 baseline: 18/84, 21.4% unstable) ---" | tee -a "$LOG"
python3 variance_check.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== Gate A finished $(date) ===" | tee -a "$LOG"
echo "Raw evals for any unstable/failed transcript are in data/evals_ENPH_run{1,2,3}/<TICKER>_<date>.txt" | tee -a "$LOG"
echo "Review data/v9_gate_a.log before running run_v9_gate_b.sh." | tee -a "$LOG"
echo "STOPPING HERE — Gate B is a separate script, run manually." | tee -a "$LOG"
echo "Full log: $LOG"
