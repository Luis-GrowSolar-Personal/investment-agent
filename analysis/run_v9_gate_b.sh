#!/bin/bash
#
# run_v9_gate_b.sh — Gate B: accuracy check for EVALUATION_PROMPT.md v9.
#
# Only run this after Gate A (run_v9_gate.sh) shows stability at or
# below v6's 18/84 (21.4%) baseline. If Gate A didn't clear, don't
# spend the API calls here — a prompt that already failed stability
# has no real path to promotion regardless of what accuracy comes back.
#
# Single pass each on ENPH + TTD -- same 15-transcript basis as v6's
# recorded 9/15 (60%) baseline. Uses --ticker explicitly for both,
# which ignores current portfolio/watchlist status (necessary since
# ENPH is currently 'watchlist', not 'portfolio').
#
# Always runs with --save-evals so raw model output is available for
# diagnosis without a re-run. Evals are archived per-ticker
# (data/evals_gateB_ENPH/, data/evals_gateB_TTD/) since this script
# only runs each ticker once, no overwrite risk between them, but
# archiving keeps the naming consistent with run_v9_gate.sh.
#
# Usage:
#   cd analysis
#   ./run_v9_gate_b.sh
#   tail -f data/v9_gate_b.log

set -e

cd "$(dirname "$0")"

LOG="data/v9_gate_b.log"
TODAY=$(date +%F)

echo "=== v9 Gate B (accuracy) run started $(date) ===" | tee "$LOG"

echo "" | tee -a "$LOG"
echo "-- ENPH --" | tee -a "$LOG"
python3 backtest_runner.py --ticker ENPH --save-evals 2>&1 | tee -a "$LOG"
mv "data/backtest_${TODAY}_ENPH.csv" "data/v9_gate_ENPH.csv"
if [ -d "data/evals" ]; then
  rm -rf "data/evals_gateB_ENPH"
  mv "data/evals" "data/evals_gateB_ENPH"
  echo "Archived raw evals → data/evals_gateB_ENPH/" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "-- TTD --" | tee -a "$LOG"
python3 backtest_runner.py --ticker TTD --save-evals 2>&1 | tee -a "$LOG"
mv "data/backtest_${TODAY}_TTD.csv" "data/v9_gate_TTD.csv"
if [ -d "data/evals" ]; then
  rm -rf "data/evals_gateB_TTD"
  mv "data/evals" "data/evals_gateB_TTD"
  echo "Archived raw evals → data/evals_gateB_TTD/" | tee -a "$LOG"
fi

echo "" | tee -a "$LOG"
echo "=== Gate B finished $(date) ===" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "MANUAL STEP: compare the 'Overall: X/Y = Z% correct' lines above" | tee -a "$LOG"
echo "(ENPH + TTD combined) against the v6 baseline: 9/15 = 60.0%." | tee -a "$LOG"
echo "Full log: $LOG"
