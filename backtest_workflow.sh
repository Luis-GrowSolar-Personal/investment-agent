#!/bin/zsh
# backtest_workflow.sh
#
# Implements the prompt improvement validation workflow:
#   Phase 0 — Extract DB baseline for TTD + ENPH (v1 scores stored in app)
#   Phase 1 — Re-evaluate TTD + ENPH with v2 prompt via backtest runner
#   Phase 2 — Full suite: all tickers (new prompt)
#   Phase 3 — Diff: compare v2 results against DB baseline
#   all     — Run phases 0, 1, 3 in sequence with confirmation gates
#
# Usage:
#   ./backtest_workflow.sh phase0        # Extract DB baseline
#   ./backtest_workflow.sh phase1        # TTD + ENPH with v2 prompt (~$1)
#   ./backtest_workflow.sh phase2        # Full suite (~$5, 15-20 min)
#   ./backtest_workflow.sh phase3        # Diff v2 vs DB baseline
#   ./backtest_workflow.sh all           # Run phases 0, 1, 3 in sequence
#
# Prerequisites:
#   - Run from project root: investment-agent/
#   - New prompt at: docs/EVALUATION_PROMPT.md (replace with v2 before running)
#   - python3 -m pip install psycopg2-binary yfinance python-dotenv anthropic pandas

set -e

SCRIPT_DIR="${0:A:h}"
ANALYSIS_DIR="$SCRIPT_DIR/analysis"
DATA_DIR="$ANALYSIS_DIR/data"
RUNNER="$ANALYSIS_DIR/backtest_runner.py"
EXTRACT_SCRIPT="$ANALYSIS_DIR/extract_db_baseline.py"
DIFF_SCRIPT="$ANALYSIS_DIR/backtest_diff.py"
TODAY=$(date +%Y-%m-%d)
DB_BASELINE="$DATA_DIR/baseline_db_TTD_ENPH_${TODAY}.csv"
NEW_RESULTS="$DATA_DIR/backtest_${TODAY}.csv"

# ── Helpers ────────────────────────────────────────────────────────────────

check_prereqs() {
  if [[ ! -f "$RUNNER" ]]; then
    echo "❌  Cannot find backtest_runner.py at $RUNNER"
    exit 1
  fi
  if [[ ! -f "$EXTRACT_SCRIPT" ]]; then
    echo "❌  Cannot find extract_db_baseline.py at $EXTRACT_SCRIPT"
    exit 1
  fi
  if [[ ! -f "$DIFF_SCRIPT" ]]; then
    echo "❌  Cannot find backtest_diff.py at $DIFF_SCRIPT"
    exit 1
  fi
}

print_header() {
  echo ""
  echo "════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════════"
}

# ── Phase 0: Extract DB baseline ──────────────────────────────────────────

run_phase0() {
  print_header "PHASE 0 — Extract DB baseline for TTD + ENPH"
  python3 "$EXTRACT_SCRIPT" --tickers TTD ENPH --out "$DB_BASELINE"
  echo ""
  echo "✅  DB baseline written to: $DB_BASELINE"
}

# ── Phase 1: Mechanical validation — TTD + ENPH ────────────────────────────

run_phase1() {
  print_header "PHASE 1 — Mechanical validation: TTD + ENPH"
  echo "  Running TTD..."
  python3 "$RUNNER" --ticker TTD --save-evals
  echo ""
  echo "  Running ENPH..."
  python3 "$RUNNER" --ticker ENPH --save-evals
  echo ""
  echo "✅  Phase 1 complete."
  echo "    Review output CSV at: $NEW_RESULTS"
  echo "    Check: stumbleType and mitigationCapabilityTrackRecord"
  echo "    for TTD Q2/Q3 2025 and ENPH NEM3.0 window calls."
}

# ── Phase 2: Full suite ────────────────────────────────────────────────────

run_phase2() {
  print_header "PHASE 2 — Full suite (all portfolio tickers)"
  echo "  This will evaluate all tickers. Estimated time: 15-20 min, ~\$5."
  echo "  Press Enter to continue or Ctrl-C to abort."
  read -r
  python3 "$RUNNER"
  echo ""
  echo "✅  Phase 2 complete."
  echo "    Full results at: $NEW_RESULTS"
}

# ── Phase 3: Diff ──────────────────────────────────────────────────────────

run_phase3() {
  print_header "PHASE 3 — Diff: v2 prompt vs DB baseline"

  # Check DB baseline exists
  if [[ ! -f "$DB_BASELINE" ]]; then
    echo "❌  DB baseline not found at $DB_BASELINE"
    echo "    Run phase0 first."
    exit 1
  fi

  # Collect all today's backtest CSVs (single-ticker or full suite)
  NEW_FILES=($(ls "$DATA_DIR"/backtest_${TODAY}*.csv 2>/dev/null | grep -v "_merged.csv"))

  if [[ ${#NEW_FILES[@]} -eq 0 ]]; then
    echo "❌  No new backtest CSV found in $DATA_DIR for today ($TODAY)"
    echo "    Run phase1 or phase2 first."
    exit 1
  fi

  # If multiple single-ticker files exist, merge them
  if [[ ${#NEW_FILES[@]} -gt 1 ]]; then
    MERGED="$DATA_DIR/backtest_${TODAY}_merged.csv"
    echo "  Merging ${#NEW_FILES[@]} file(s) → $MERGED"
    python3 -c "
import pandas as pd, sys
out = sys.argv[1]
files = sys.argv[2:]
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
df.to_csv(out, index=False)
print(f'  {len(files)} files merged, {len(df)} total rows')
" "$MERGED" "${NEW_FILES[@]}"
    LATEST="$MERGED"
  else
    LATEST="${NEW_FILES[1]}"
  fi

  echo "  Baseline (DB v1): $DB_BASELINE"
  echo "  New (v2 prompt):  $LATEST"
  echo ""

  python3 "$DIFF_SCRIPT" --baseline "$DB_BASELINE" --new "$LATEST"
}

# ── Dispatch ───────────────────────────────────────────────────────────────

check_prereqs

case "${1:-}" in
  phase0) run_phase0 ;;
  phase1) run_phase1 ;;
  phase2) run_phase2 ;;
  phase3) run_phase3 ;;
  all)
    run_phase0
    echo ""
    run_phase1
    echo ""
    echo "  Phases 0 + 1 done. Review results before proceeding to full suite."
    echo "  Press Enter to run phase3 (diff) or Ctrl-C to stop."
    read -r
    run_phase3
    ;;
  *)
    echo "Usage: $0 phase0 | phase1 | phase2 | phase3 | all"
    echo ""
    echo "  phase0  — Extract DB baseline for TTD + ENPH (v1 scores)"
    echo "  phase1  — Re-evaluate TTD + ENPH with v2 prompt (~\$1)"
    echo "  phase2  — Full suite all tickers (~\$5, 15-20 min)"
    echo "  phase3  — Diff v2 results vs DB baseline"
    echo "  all     — Run phases 0, 1, 3 in sequence with confirmation gates"
    exit 1
    ;;
esac
