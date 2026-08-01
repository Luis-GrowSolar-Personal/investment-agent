#!/bin/zsh
# Step 1 of 3 — recovery from the 2026-07-06 TTD DB-timeout crash.
# Finishes iteration 3's held-out TTD leg and archives it into iter3/,
# matching the layout auto_iterate_prompt.py itself would produce.
#
# Run with:
#   cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent/analysis"
#   zsh recovery_step1_finish_ttd.sh
#
# Wait for it to print "STEP 1 COMPLETE" before running step 2.

set -e

RUN_DIR="data/auto_iterate/2026-07-06_082945"
ITER3="$RUN_DIR/iter3"
START_EPOCH=$(date +%s)

echo "=== Step 1: running TTD backtest ==="
python3 backtest_runner.py --ticker TTD --save-evals

echo ""
echo "=== Archiving into $ITER3 ==="
TTD_CSV=$(find data -maxdepth 1 -name 'backtest_*_TTD.csv' -newermt "@$START_EPOCH" | sort | tail -1)
if [ -z "$TTD_CSV" ]; then
  echo "ERROR: no new TTD CSV found -- the backtest may not have actually finished."
  exit 1
fi
mv "$TTD_CSV" "$ITER3/TTD_holdout.csv"
rm -rf "$ITER3/evals_TTD_holdout"
mv "data/evals" "$ITER3/evals_TTD_holdout"

echo "Archived: $ITER3/TTD_holdout.csv"
echo ""
echo "STEP 1 COMPLETE -- now run: python3 recovery_step2_score_iter3.py"
