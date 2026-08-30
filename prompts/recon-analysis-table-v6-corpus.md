# Recon: is the Analysis table a usable v6 / sonnet-4 eval corpus?

**Recon and backup only. No sweep, no harness changes, no spec edits, no LLM
evaluation calls, $0 of API spend.** Expected duration: well under an hour.

Write findings to `./wrap-ups/recon-analysis-table-v6-corpus-out.md`.

## Why this exists

`prompts/regen-v6-eval-cache-and-run-sweep.md` stopped at Step 0c: the model the
validated `$287k` reference was produced under — `claude-sonnet-4-20250514` — has
been **retired from the API** and cannot be called at any price. See
`wrap-ups/regen-v6-eval-cache-and-run-sweep-out.md`. That finding is accepted;
do not re-verify it.

The file-based eval cache was never committed and is gone. But the Railway
Postgres **`Analysis` table** was written by the app's `/api/evaluate` route
using the then-live `EVALUATION_PROMPT.md` and that same model. **If it covers
the corpus, it is an irreplaceable archive of exactly the prompt+model
combination that can no longer be reproduced**, and
`analysis/simulator/data.py::load_call_events()` already reads from it — no
cache, no regeneration, no spend.

This task determines whether that is true.

---

## Step 1 — BACK IT UP. Before reading anything else.

Non-negotiable and first. This table is currently the only surviving copy of an
artifact that cannot be regenerated at any price, and it lives in a **dev**
database. Do this before any analysis:

```zsh
# DATABASE_URL is in the repo root .env
pg_dump "$DATABASE_URL" -t '"Analysis"' -t '"Transcript"' -t '"Ticker"' \
  --data-only --column-inserts \
  -f ~/investment-agent-backups/analysis_corpus_$(date +%Y%m%d).sql
```

- Write it **outside the repo** (or to a gitignored path). Do not commit it.
- Take a schema-inclusive dump too if it's cheap.
- Report the file size and row counts written.
- If `pg_dump` version-mismatches against the server, say so and use whatever
  works (`--no-owner`, a matching client via `brew`, or a psql `\copy` to CSV).
  **Do not skip this step.** A CSV export of all three tables is an acceptable
  fallback; no backup at all is not.

Confirm the dump is non-empty and readable before continuing.

## Step 2 — establish the version cutoff date

Commit `87bcfaa` bumped `EVALUATION_PROMPT.md` from `v6` to `v10+auto1`; its
parent `7063465` is the last v6 commit. Get the dates:

```zsh
git show -s --format='%H %ci %s' 7063465 87bcfaa
```

Any `Analysis` row created **before** `87bcfaa` was deployed is v6-era. Note
that commit date ≠ deploy date — report both the commit date and, if you can
determine it (Railway deploy history, or a visible gap in `createdAt`), the
actual deploy date. If you cannot, use the commit date and say so.

## Step 3 — coverage and consistency

Report each of these as a number, not a narrative:

1. Total rows in `Analysis`; total rows in `Transcript`.
2. Distinct `transcriptId` values present in `Analysis`.
3. **Coverage against the corpus:** `analysis/data/transcripts/_manifest.json`
   has 662 entries across 32 tickers. How many of those (ticker, call_date)
   pairs have at least one `Analysis` row? List any that have none.
4. `createdAt` distribution by month — a simple histogram. Mark the Step 2
   cutoff on it.
5. **Coverage before the cutoff:** how many of the 662 have at least one
   `Analysis` row created *before* the cutoff? This is the number that decides
   everything. List the gaps.
6. **Re-scores:** how many transcripts have more than one `Analysis` row? For
   those, how many have rows on *both* sides of the cutoff? This is the
   latest-wins hazard — `load_call_events` takes the latest analysis per
   transcript, which would return a v10 row for any transcript re-scored after
   the bump.
7. **Field completeness on pre-cutoff rows**, since the simulator needs them:
   `recommendation`, `recommendedSize`, `thesisHealth`, and the trend-layer
   fields `tier`, `trajectory`, `finalAction`, `finalConfidence`. Count nulls
   for each.
8. Do pre-cutoff `rawOutput` values contain a parseable `---STRUCTURED---`
   block? Spot-check 5 across different tickers and dates.

## Step 4 — verify the loader can actually use it

Read `analysis/simulator/data.py::load_call_events()` and report:

- exactly which columns it selects and how it picks one analysis per transcript
- whether a `createdAt` cutoff (or earliest-per-transcript) could be added as a
  small, contained change — quote the lines that would change
- whether anything it needs is missing from pre-cutoff rows

**Do not make the change.** Report what it would be.

If `finalAction` / `tier` / trend-layer fields are null on pre-cutoff rows, note
that these are computed by `analysis/trend_analyst.py` and synced by
`sync_trend_to_db.py` — **deterministic Python, no LLM calls** — so they are
recoverable for free. Confirm that reading of those two files.

## Step 5 — is there any other archive?

Quick check, timeboxed to a few minutes each, then stop:

- Railway automated backups or snapshots on this Postgres instance — do they
  exist, how far back, are they restorable?
- `analysis/data/evals_ENPH_run1|run2|run3/` — what prompt version and how many
  files? (Partial, but confirms the naming/format.)
- Any other `evals` directory anywhere on this machine outside the repo.

## Step 6 — report

Scope boundary: **report, do not decide.** Do not pick between using the DB
corpus and swapping models. Do not amend `ALLOCATOR_OPERATING_MODEL.md`,
`PROMOTION_GATE.md`, or any other doc. The decision happens in the design
session.

Lead the wrap-up with a single line answering the one question that matters:

> **Of the 662 corpus transcripts, N have a usable pre-cutoff Analysis row.**

Then the numbers from Steps 2–5, the loader assessment, and — flagged plainly —
anything that would make the DB corpus unusable or ambiguous.

State explicitly what **cannot** be verified: `Analysis` has no prompt-version
or model field, so pre-cutoff dating is *circumstantial* evidence that a row was
produced under v6 and `claude-sonnet-4-20250514`, not proof. Say so rather than
implying certainty.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- Read-only against the database apart from nothing — **no writes, no
  migrations, no re-scores.**
- Do not run `eval_cache_warmer.py` or any other LLM evaluation.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
