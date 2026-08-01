#!/bin/zsh
# Step 1b -- the TTD backtest already ran successfully (confirmed: 21 rows
# written to data/backtest_2026-07-06_TTD.csv). The original step 1 script's
# archiving step failed silently because it used `find -newermt "@epoch"`,
# which is GNU find syntax -- macOS's BSD find doesn't support it. This
# script just does the archiving, using the exact known filename instead.
#
# Run with:
#   zsh recovery_step1b_archive_only.sh

set -e

RUN_DIR="data/auto_iterate/2026-07-06_082945"
ITER3="$RUN_DIR/iter3"
TTD_CSV="data/backtest_2026-07-06_TTD.csv"

if [ ! -f "$TTD_CSV" ]; then
  echo "ERROR: $TTD_CSV not found. Did the filename come out differently?"
  echo "Run: ls -la data/backtest_2026-07-06_TTD.csv"
  exit 1
fi

mv "$TTD_CSV" "$ITER3/TTD_holdout.csv"
rm -rf "$ITER3/evals_TTD_holdout"
mv "data/evals" "$ITER3/evals_TTD_holdout"

echo "Archived: $ITER3/TTD_holdout.csv"
ls -la "$ITER3/evals_TTD_holdout" | wc -l
echo ""
echo "STEP 1 COMPLETE -- now run: python3 recovery_step2_score_iter3.py"
