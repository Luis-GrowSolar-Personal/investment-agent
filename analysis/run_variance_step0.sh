#!/bin/bash
#
# run_variance_step0.sh — Step 0 of MODEL_SELECTION_BENCHMARK_SPEC.md.
#
# Runs the evaluator 3x against ENPH's full transcript history, then
# compares the four tracked fields across runs to establish the current
# noise floor (post temperature=0 fix, post model-string fix).
#
# Usage:
#   cd analysis
#   ./run_variance_step0.sh
#   (kick it off, walk away, come back — progress + result land in
#    data/variance_step0.log)
#
# Check progress while it runs:
#   tail -f data/variance_step0.log

set -e

cd "$(dirname "$0")"

LOG="data/variance_step0.log"
TODAY=$(date +%F)

echo "=== Step 0 variance run started $(date) ===" | tee "$LOG"

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
echo "--- Comparing runs ---" | tee -a "$LOG"
python3 variance_check.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "=== Step 0 finished $(date) ===" | tee -a "$LOG"
echo "Full log: $LOG"
