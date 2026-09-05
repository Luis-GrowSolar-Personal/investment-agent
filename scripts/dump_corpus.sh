#!/usr/bin/env bash
# dump_corpus.sh -- archive backup for Ticker/Transcript/Analysis.
#
# Runs on macOS/zsh locally AND on ubuntu-latest in GitHub Actions CI
# (see .github/workflows/corpus-archive.yml in the investment-agent-corpus
# archive repo). Written bash/POSIX-ish deliberately: no zsh-only syntax,
# no BSD-vs-GNU flag assumptions. Prefer python3 for anything fiddly.
#
# What it does:
#   1. Reads DATABASE_URL (or CORPUS_BACKUP_DATABASE_URL if set -- prefer
#      the read-only role) from the repo .env. Never echoes it.
#   2. Dumps ONLY "Ticker", "Transcript", "Analysis" -- schema and data as
#      two separate plain-SQL files, INSERT format (measured against COPY
#      format on 2026-09-04: 42,868,670 bytes INSERT vs 42,933,257 bytes
#      COPY on this corpus -- COPY was actually *larger* here, so INSERT
#      format is kept, matching the existing 20260830 artifacts).
#   3. Writes date-stamped output, never overwriting an existing dump.
#   4. Verifies: row counts (live vs dump), completion marker + restrict/
#      unrestrict token match, sha256 vs the most recent previous dump
#      (identical -> skip write, exit 0), size-drop truncation check (exit
#      non-zero), table-scope assertion (exit non-zero if a 4th table
#      appears).
#   5. Emits corpus_census_YYYYMMDD.txt.
#
# It never modifies the live database. It is read-only against Postgres.
#
# Usage:
#   ./scripts/dump_corpus.sh
#
# Output directory: OUT_DIR env var, default ~/Dropbox/LUIS/Backups/investment-agent-backups

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
OUT_DIR="${OUT_DIR:-$HOME/Dropbox/LUIS/Backups/investment-agent-backups}"

TABLES=("Ticker" "Transcript" "Analysis")

log() { printf '[dump_corpus] %s\n' "$1" >&2; }
fail() { printf '[dump_corpus] FAIL: %s\n' "$1" >&2; exit 1; }

# --- 1. Load DATABASE_URL, never echo it -----------------------------------
if [ -n "${CORPUS_BACKUP_DATABASE_URL:-}" ]; then
  DB_URL="$CORPUS_BACKUP_DATABASE_URL"
  log "using CORPUS_BACKUP_DATABASE_URL (read-only role) from environment"
elif [ -n "${DATABASE_URL:-}" ]; then
  DB_URL="$DATABASE_URL"
  log "using DATABASE_URL from environment"
elif [ -f "$ENV_FILE" ]; then
  DB_URL="$(python3 - "$ENV_FILE" << 'PYEOF'
import sys
path = sys.argv[1]
key_priority = ["CORPUS_BACKUP_DATABASE_URL", "DATABASE_URL"]
found = {}
with open(path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        found[k.strip()] = v.strip()
for k in key_priority:
    if k in found:
        print(found[k])
        break
PYEOF
)"
  [ -n "$DB_URL" ] || fail "no CORPUS_BACKUP_DATABASE_URL or DATABASE_URL found in $ENV_FILE"
  log "using database URL read from $ENV_FILE (not echoed)"
else
  fail "no DATABASE_URL available (checked env vars and $ENV_FILE)"
fi

command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found on PATH"
command -v psql >/dev/null 2>&1 || fail "psql not found on PATH"

mkdir -p "$OUT_DIR"

DATE_STAMP="$(date +%Y%m%d)"
DATA_FILE="$OUT_DIR/analysis_corpus_${DATE_STAMP}.sql"
SCHEMA_FILE="$OUT_DIR/analysis_corpus_schema_${DATE_STAMP}.sql"
SHA_FILE="${DATA_FILE}.sha256"
CENSUS_FILE="$OUT_DIR/corpus_census_${DATE_STAMP}.txt"

if [ -e "$DATA_FILE" ] || [ -e "$SCHEMA_FILE" ]; then
  fail "output for $DATE_STAMP already exists ($DATA_FILE) -- refusing to overwrite. Run at most once per day, or remove the stale file deliberately."
fi

# --- 2. Live row counts, read-only ------------------------------------------
log "querying live row counts"
LIVE_COUNTS="$(psql "$DB_URL" -t -A -F'|' -c \
  'SELECT (SELECT count(*) FROM "Ticker"), (SELECT count(*) FROM "Transcript"), (SELECT count(*) FROM "Analysis");')"
LIVE_TICKER="$(echo "$LIVE_COUNTS" | cut -d'|' -f1)"
LIVE_TRANSCRIPT="$(echo "$LIVE_COUNTS" | cut -d'|' -f2)"
LIVE_ANALYSIS="$(echo "$LIVE_COUNTS" | cut -d'|' -f3)"
log "live counts: Ticker=$LIVE_TICKER Transcript=$LIVE_TRANSCRIPT Analysis=$LIVE_ANALYSIS"

# --- 3. Dump schema and data, INSERT format (see header measurement note) --
TMP_DATA="$(mktemp)"
TMP_SCHEMA="$(mktemp)"
trap 'rm -f "$TMP_DATA" "$TMP_SCHEMA"' EXIT

log "dumping schema"
pg_dump "$DB_URL" --schema-only --no-owner --no-acl \
  -t '"Ticker"' -t '"Transcript"' -t '"Analysis"' \
  -f "$TMP_SCHEMA"

log "dumping data (INSERT format)"
pg_dump "$DB_URL" --data-only --inserts --column-inserts \
  -t '"Ticker"' -t '"Transcript"' -t '"Analysis"' \
  -f "$TMP_DATA"

# --- Verification: table scope ----------------------------------------------
log "asserting table scope"
FOUND_TABLES="$(grep -oE '^INSERT INTO [^ ]*\."[A-Za-z]+"' "$TMP_DATA" | sed -E 's/.*"([A-Za-z]+)"$/\1/' | sort -u)"
EXPECTED_SORTED="$(printf '%s\n' "${TABLES[@]}" | sort -u)"
if [ "$FOUND_TABLES" != "$EXPECTED_SORTED" ]; then
  fail "table scope leak -- dump contains [$FOUND_TABLES], expected [${TABLES[*]}]"
fi

# --- Verification: completion marker + restrict/unrestrict tokens ----------
log "asserting completion marker"
tail -5 "$TMP_DATA" | grep -q "PostgreSQL database dump complete" \
  || fail "data dump missing completion marker -- possible truncation"
tail -5 "$TMP_SCHEMA" | grep -q "PostgreSQL database dump complete" \
  || fail "schema dump missing completion marker -- possible truncation"

DATA_RESTRICT="$(grep -o '\\restrict [A-Za-z0-9]*' "$TMP_DATA" | head -1 | awk '{print $2}' || true)"
DATA_UNRESTRICT="$(grep -o '\\unrestrict [A-Za-z0-9]*' "$TMP_DATA" | head -1 | awk '{print $2}' || true)"
if [ -n "$DATA_RESTRICT" ] || [ -n "$DATA_UNRESTRICT" ]; then
  [ "$DATA_RESTRICT" = "$DATA_UNRESTRICT" ] || fail "restrict/unrestrict token mismatch in data dump"
fi

# --- Verification: per-table row counts vs live -----------------------------
DUMP_TICKER="$(grep -c '^INSERT INTO public."Ticker"' "$TMP_DATA" || true)"
DUMP_TRANSCRIPT="$(grep -c '^INSERT INTO public."Transcript"' "$TMP_DATA" || true)"
DUMP_ANALYSIS="$(grep -c '^INSERT INTO public."Analysis"' "$TMP_DATA" || true)"
log "dump counts: Ticker=$DUMP_TICKER Transcript=$DUMP_TRANSCRIPT Analysis=$DUMP_ANALYSIS"

if [ "$DUMP_TICKER" != "$LIVE_TICKER" ] || [ "$DUMP_TRANSCRIPT" != "$LIVE_TRANSCRIPT" ] || [ "$DUMP_ANALYSIS" != "$LIVE_ANALYSIS" ]; then
  fail "dump row counts do not match live DB counts -- Ticker $DUMP_TICKER/$LIVE_TICKER, Transcript $DUMP_TRANSCRIPT/$LIVE_TRANSCRIPT, Analysis $DUMP_ANALYSIS/$LIVE_ANALYSIS"
fi

# --- Verification: sha256 vs most recent previous dump ----------------------
NEW_SHA="$(shasum -a 256 "$TMP_DATA" 2>/dev/null | awk '{print $1}' || sha256sum "$TMP_DATA" | awk '{print $1}')"

PREV_DATA_FILE="$(ls -1 "$OUT_DIR"/analysis_corpus_[0-9]*.sql 2>/dev/null | grep -v '_schema_' | sort | tail -1 || true)"
if [ -n "$PREV_DATA_FILE" ] && [ -e "$PREV_DATA_FILE" ]; then
  PREV_SHA="$(shasum -a 256 "$PREV_DATA_FILE" 2>/dev/null | awk '{print $1}' || sha256sum "$PREV_DATA_FILE" | awk '{print $1}')"
  PREV_SIZE="$(wc -c < "$PREV_DATA_FILE" | tr -d ' ')"
  NEW_SIZE="$(wc -c < "$TMP_DATA" | tr -d ' ')"

  if [ "$NEW_SHA" = "$PREV_SHA" ]; then
    log "sha256 identical to most recent previous dump ($PREV_DATA_FILE) -- corpus unchanged. Skipping write."
    echo "UNCHANGED"
    echo "sha256=$NEW_SHA"
    echo "Ticker=$DUMP_TICKER Transcript=$DUMP_TRANSCRIPT Analysis=$DUMP_ANALYSIS"
    exit 0
  fi

  # Truncation signal: sharp size drop vs previous dump (more than 10% smaller)
  DROP_THRESHOLD=$(( PREV_SIZE * 90 / 100 ))
  if [ "$NEW_SIZE" -lt "$DROP_THRESHOLD" ]; then
    fail "size dropped sharply vs previous dump ($PREV_SIZE -> $NEW_SIZE bytes) -- possible truncation, refusing to write"
  fi
else
  log "no previous dump found in $OUT_DIR -- treating as first dump"
fi

# --- Write final files -------------------------------------------------------
cp "$TMP_SCHEMA" "$SCHEMA_FILE"
cp "$TMP_DATA" "$DATA_FILE"
echo "$NEW_SHA  $(basename "$DATA_FILE")" > "$SHA_FILE"

# --- Census -------------------------------------------------------------------
log "writing census"
psql "$DB_URL" -c "
SELECT a.\"promptVersion\", a.\"modelVersion\", COUNT(*) AS rows,
       MIN(t.\"callDate\")::date AS earliest, MAX(t.\"callDate\")::date AS latest
FROM \"Analysis\" a JOIN \"Transcript\" t ON a.\"transcriptId\" = t.id
GROUP BY 1,2 ORDER BY 1,2;
" > "$CENSUS_FILE"

log "wrote $DATA_FILE"
log "wrote $SCHEMA_FILE"
log "wrote $SHA_FILE"
log "wrote $CENSUS_FILE"

echo "OK"
echo "sha256=$NEW_SHA"
echo "size=$(wc -c < "$DATA_FILE" | tr -d ' ')"
echo "Ticker=$DUMP_TICKER Transcript=$DUMP_TRANSCRIPT Analysis=$DUMP_ANALYSIS"
