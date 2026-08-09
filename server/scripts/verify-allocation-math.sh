#!/usr/bin/env bash
# Thin wrapper: loads DATABASE_URL from the repo root .env (same pattern as
# every other DB-touching command in CLAUDE.md) and runs the reconciliation
# check for every owner. See verifyAllocationMath.js for what it actually
# checks.
#
# Usage: ./server/scripts/verify-allocation-math.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATABASE_URL=$(grep '^DATABASE_URL' "$REPO_ROOT/.env" | cut -d '=' -f2-) \
  node "$SCRIPT_DIR/verifyAllocationMath.js"
