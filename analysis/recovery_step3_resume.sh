#!/bin/zsh
# Step 3 of 3 -- recovery from the 2026-07-06 TTD DB-timeout crash.
# Resumes auto_iterate_prompt.py, seeding from whichever iteration
# step 2 determined is the real best (iter1 or iter3), with the
# already-confirmed examples pre-excluded so it doesn't waste time
# re-diagnosing patches already tested.
#
# Run with:
#   zsh recovery_step3_resume.sh

set -e

RUN_DIR="data/auto_iterate/2026-07-06_082945"
DECISION_FILE="recovery_decision.txt"

if [ ! -f "$DECISION_FILE" ]; then
  echo "ERROR: $DECISION_FILE not found. Run recovery_step2_score_iter3.py first."
  exit 1
fi

SEED_ITER=$(cat "$DECISION_FILE")
echo "=== Step 3: resuming harness, seeded from iter$SEED_ITER ==="

if [ "$SEED_ITER" = "3" ]; then
  python3 auto_iterate_prompt.py \
    --seed-run-dir "$RUN_DIR" \
    --seed-iter 3 \
    --seed-prompt-file "$RUN_DIR/iter3/prompt_candidate.md" \
    --max-iterations 6 \
    --already-tried "recommendation:2023-02-07" \
    --already-tried "recommendation:2023-04-25" \
    --already-tried "mitigation_track_record:2022-04-26"
else
  python3 auto_iterate_prompt.py \
    --seed-run-dir "$RUN_DIR" \
    --seed-iter 1 \
    --seed-prompt-file "$RUN_DIR/iter1/prompt_candidate.md" \
    --max-iterations 6 \
    --already-tried "recommendation:2023-02-07" \
    --already-tried "recommendation:2023-04-25"
fi
