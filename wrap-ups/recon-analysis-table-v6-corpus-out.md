# Recon: is the `Analysis` table a usable v6/sonnet-4 eval corpus? — wrap-up

**Of the 662 corpus transcripts, 657 have a usable pre-cutoff Analysis row.**
(662 is the manifest's row count; it contains 659 *distinct* (ticker, call_date)
pairs — 3 duplicate manifest entries, see Step 3.3.) That is strong coverage.
But **one real blocker survives the recon**: every pre-cutoff row's
`rawOutput` is markdown prose with no `---STRUCTURED---` JSON block, and
`data.py::_extract_type_classification()` requires that exact block. Today,
Type A/B classification — which sets the tier cap — resolves to `None` for
all 770 pre-cutoff rows via the existing loader. That's not a coverage gap,
it's a parser mismatch, fixable, but not yet fixed. See Step 4.

No sweep, no harness change, no LLM calls, $0 spend, all queries read-only.

---

## Step 1 — backup

```zsh
DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-)
pg_dump "$DATABASE_URL" -t '"Analysis"' -t '"Transcript"' -t '"Ticker"' \
  --data-only --column-inserts \
  -f ~/investment-agent-backups/analysis_corpus_20260830.sql
pg_dump "$DATABASE_URL" -t '"Analysis"' -t '"Transcript"' -t '"Ticker"' \
  --schema-only \
  -f ~/investment-agent-backups/analysis_corpus_schema_20260830.sql
```

- `pg_dump` 18.4 (Homebrew `libpq`) against a Postgres 18.6 server — no version
  mismatch, ran clean, no fallback needed.
- Data dump: 43,263,120 bytes (~41 MB), written to
  `~/investment-agent-backups/analysis_corpus_20260830.sql` — outside the repo,
  not committed, not gitignored-in-repo (it's simply not under the repo at all).
- Schema dump: 6,220 bytes, same directory.
- Verified non-empty and readable:

  ```
  INSERT INTO public."Analysis"    805 rows
  INSERT INTO public."Transcript"  708 rows
  INSERT INTO public."Ticker"       45 rows
  ```

  matching live `SELECT count(*)` on all three tables. Confirmed before
  proceeding.

## Step 2 — version cutoff

```
$ git show -s --format='%H %ci %s' 7063465 87bcfaa
70634653bc0378c515203ec900aa98937f9807b2 2026-06-27 16:26:16 -0400  feat: add summary field to Analysis — plain-English finding for Advisory Feed
87bcfaa883d8d47b0fc254cd196600519fdcc891 2026-08-01 16:00:12 -0400  Add account routing for new-position moves
```

Cutoff used throughout: **`2026-06-27 16:26:16-04`** (commit `7063465`, last
v6 commit). **This is a commit timestamp, not a deploy timestamp** — I could
not determine actual Railway deploy time from anything available (no CLI
subcommand for deploy history within the timebox; see Step 5). If deploys lag
commits by hours, the true cutoff is later than used here, which would only
*add* more usable rows, not remove any — so this is a conservative bound, not
an optimistic one.

## Step 3 — coverage and consistency

1. **Row counts:** `Analysis` = 805. `Transcript` = 708.
2. **Distinct `transcriptId` in `Analysis`:** 708 — every Transcript row has
   at least one Analysis row.
3. **Coverage against the file corpus:** `_manifest.json` has 662 *entries*
   but only **659 distinct (ticker, call_date) pairs** (3 duplicates in the
   manifest itself — not investigated further, out of scope here). Of those
   659: **657 have a matching Transcript row in the DB; 2 do not**:
   - `NVDA 2020-05-21`
   - `NVDA 2020-08-19`

   (Separately, the DB has 50 (ticker, call_date) pairs — mostly more-recent
   quarters — that aren't in the file manifest at all; irrelevant to this
   recon, noted for completeness.)
4. **`createdAt` histogram** (all 805 Analysis rows):

   | Month | Count |
   |---|---|
   | 2026-04 | 194 |
   | 2026-05 | 573 |
   | 2026-06 | 4 |
   | 2026-07 | 17 |
   | 2026-08 | 17 |

   Cutoff (2026-06-27 16:26) falls inside the 2026-06 bucket. 770 of 805 rows
   predate it; 35 postdate it.
5. **Coverage before the cutoff — the number that matters:**

   **657 of 659 manifest pairs have ≥1 pre-cutoff `Analysis` row.**
   The 2 gaps are exactly the 2 pairs from Step 3.3 that have no Transcript
   row in the DB at all (`NVDA 2020-05-21`, `NVDA 2020-08-19`) — there is no
   pair present in the DB with only post-cutoff rows. Coverage loss is 100%
   attributable to those two transcripts never having been loaded into
   Postgres, not to timing.
6. **Re-scores / latest-wins hazard:** 97 transcripts have more than one
   `Analysis` row. **Zero of those 97 straddle the cutoff** — every re-scored
   transcript's rows are either entirely pre-cutoff or entirely post-cutoff.
   So `load_call_events()`'s `MAX(createdAt)` pick, applied unmodified, never
   silently swaps a v6 row for a v10 row on any of the 657 usable transcripts.
   This eliminates the hazard the prompt flagged, for this corpus as it
   stands today — but it is a property of the current data, not a structural
   guarantee; a future re-score of an old transcript would reintroduce it.
7. **Field completeness on the 770 pre-cutoff rows:**

   | Field | Nulls |
   |---|---|
   | `recommendation` | 0 |
   | `recommendedSize` | 123 |
   | `thesisHealth` | 0 |
   | `tier` | 97 |
   | `trajectory` | 161 |
   | `finalAction` | 97 |
   | `finalConfidence` | 97 |

   `recommendation` and `thesisHealth` are fully populated (they're
   `NOT NULL` columns). The trend-layer fields (`tier`, `trajectory`,
   `finalAction`, `finalConfidence`) and `recommendedSize` have real gaps —
   see Step 4 on why these are recoverable without any LLM call.
8. **`---STRUCTURED---` block parseability — spot check, then full scan:**
   5 random pre-cutoff rows across 5 tickers (NVDA, ENVX, EOSE ×2, DIS), all
   different dates: **0 of 5 contained a `---STRUCTURED---` block.** All 5
   were markdown with `## THESIS HEALTH`, `## POSITION TYPE`,
   `## RECOMMENDATION`, etc. headers instead — the older prompt format.
   Followed up with a full-corpus regex scan rather than trusting 5 samples:

   ```sql
   SELECT count(*) AS total,
          count(*) FILTER (WHERE "rawOutput" ~ '---STRUCTURED---') AS has_structured_block,
          count(*) FILTER (WHERE "rawOutput" ~ '## POSITION TYPE') AS has_position_type_header
   FROM "Analysis" WHERE "createdAt" < '2026-06-27 16:26:16-04';
   ```
   ```
    total | has_structured_block | has_position_type_header
   -------+----------------------+--------------------------
      770 |                    0 |                      770
   ```

   **This is universal, not a sampling artifact: 0 of 770 pre-cutoff rows
   have the JSON block; all 770 have the prose header instead.**

## Step 4 — can the loader actually use this?

`analysis/simulator/data.py::load_call_events()`:

- Selects, per transcript, the row with `MAX(a."createdAt")` (a self-join on
  `(transcriptId, MAX(createdAt))`), for columns `recommendation`,
  `recommendedSize`, `thesisHealth`, `finalAction`, `finalConfidence`,
  `trajectory` directly from typed `Analysis` columns — **no regex needed for
  these**, they're real columns, already populated per Step 3.7.
- Separately, in a **second query + Python pass**, it extracts
  `type_classification` by regexing `rawOutput` for the same
  `---STRUCTURED---...---END STRUCTURED---` block
  (`data.py:233-240`, `_extract_type_classification`).

**The blocker:** since 0 of 770 pre-cutoff rows contain that block (Step
3.8), `_extract_type_classification()` returns `None` for literally every
pre-cutoff row, unmodified. `type_classification` (Type A vs B, which decides
the 15/35/50% tier cap) would be `None` for the entire pre-v6-cutoff corpus if
`load_call_events()` is used as-is today.

**A `createdAt` cutoff filter would be a one-line, contained addition** —
`load_call_events()` already accepts `start_date`/`end_date` params
(`data.py:127-129`) filtered against `t."callDate"`, not `a."createdAt"`.
Adding an analogous `AND a."createdAt" < %s` to both of the two SQL blocks
(`data.py:157-176` main query, `data.py:194-210` rawOutput query) would
restrict to pre-cutoff rows. Given Step 3.6 (no transcript straddles the
cutoff), this changes nothing about *which* row wins for the 657 usable
transcripts — it would only matter as a safety net against a *future*
re-score. **Not applied — reporting only, per scope.**

**The `type_classification` gap is the one that actually blocks anything**,
and it is not a cutoff-filter problem — it's that the extraction regex
targets a JSON shape this era of output never had. The Type A/B text *is*
present in every row, just as prose (`"## POSITION TYPE" / "Type B:
multi-driver platform thesis"`, confirmed in all 5 spot-checked rows and
present in all 770 by the header count in Step 3.8). A second regex against
`## POSITION TYPE\s*\n+(?:\*\*)?Type ([AB])` (or similar) could recover it —
**not implemented**, this is a code change belonging to whoever picks up this
thread, not this recon.

**Trend-layer fields, confirmed deterministic and free to recompute:**
`analysis/trend_analyst.py` is pure Python — reads a CSV or in-memory
structured scores, applies `docs/architecture/TREND_LAYER.md`'s §6 matrix,
makes zero LLM or network calls (confirmed by reading the file: only
`argparse`, `csv`, `datetime`, `json`, `sys`, `Path` imports). It states this
itself in its own docstring: *"Firewall: reads only structured scores...
Output is a trend verdict; final-action override is a mechanical matrix."*
`analysis/sync_trend_to_db.py` imports `compute_trend_verdict`,
`apply_matrix`, `compute_final_confidence` from it and writes results back to
the DB — also pure Python, no LLM calls, confirmed by the same import check.
So the 97/161/97/97 nulls in `tier`/`trajectory`/`finalAction`/
`finalConfidence` (Step 3.7) are backfillable for $0 by rerunning
`sync_trend_to_db.py` — **not run here**, since the standing rules for this
recon are read-only/no-writes.

## Step 5 — other archives (timeboxed)

- **Railway backups:** logged into `railway` CLI (`investment-agent-DEV`
  project, `production` environment). The CLI has **no backup/snapshot
  subcommand** — `railway --help` returns nothing for `backup`. Railway's
  managed Postgres backups (if enabled) are only visible/restorable from the
  web dashboard, which I did not access. **Not checked** — flagging as
  something only Luis can look at via the dashboard, timeboxed as instructed.
- **`analysis/data/evals_ENPH_run1|run2|run3/`:** all three exist, 21 files
  each, all ENPH-only. Spot-checked `run1/ENPH_2021-04-27.txt`: **does**
  contain a `---STRUCTURED---` block (2 occurrences — open+close markers).
  So the structured-JSON format existed in *some* local eval runs; these
  three directories are a different, small, single-ticker corpus, not a
  substitute for the missing 659-transcript v6 cache. Confirms the
  cache-format naming/parsing convention is real and worked at some point —
  just not what's sitting in the DB pre-cutoff.
- **Any other `evals` directory on this machine:** `find ~ -iname
  "*evals*"` (outside the repo, outside `Library/CloudStorage` sync
  duplicates, outside `node_modules`) returned nothing.

## What cannot be verified

`Analysis` **does** have `promptVersion` and `modelVersion` columns — contrary
to this prompt's premise that no such field exists. Flagging this as a
correction to the prompt, not something acted on beyond reporting:

```sql
SELECT "promptVersion", "modelVersion", count(*) FROM "Analysis" GROUP BY 1,2 ORDER BY 3 DESC;
```
```
 promptVersion |       modelVersion       | count
---------------+--------------------------+-------
               |                          |   764
 v6            | claude-sonnet-4-6        |    35
 v6            | claude-sonnet-4-20250514 |     6
```

764 of 805 rows have **both fields NULL** — so for the overwhelming majority,
including most of the 657 usable pre-cutoff rows, dating by `createdAt` vs.
the git commit history remains **circumstantial, not proof**, exactly as the
prompt anticipated. The 6 rows that *do* carry an explicit tag are
corroborating, not conclusive: all 6 say `promptVersion=v6`,
`modelVersion=claude-sonnet-4-20250514`, and all 6 fall before the cutoff
(`createdAt` between 2026-05-31 and 2026-06-14) — consistent with, but not
sufficient to prove, that the other 764 untagged pre-cutoff rows were produced
the same way. Separately, the 35 `claude-sonnet-4-6`-tagged rows are **all
post-cutoff** (2026-06-28 through 2026-08-24) — i.e., whatever backfilled
`modelVersion` onto some rows started tagging with a still-current model only
after the cutoff, which is circumstantially consistent with a re-scoring pass
using a newer model, but not something this recon traced further (out of
scope — no writes, no re-score analysis beyond what the existing rows show).

## What was deliberately not done

- No code changes to `data.py`, `data_from_cache.py`, `trend_analyst.py`, or
  `sync_trend_to_db.py`.
- No `sync_trend_to_db.py` run (would write to the DB — against standing
  rules here even though it's a deterministic/free operation).
- No decision made between "use the DB corpus" and "swap models and rebase
  the baseline." That's explicitly for the design session.
- No Railway dashboard check for managed backups — CLI has no path to it
  within this recon's timebox.
- Did not investigate the 3 duplicate manifest entries or the 50 DB pairs
  absent from the manifest — noted, not chased, as tangential to the one
  question this recon answers.

## Follow-up commands for whoever picks this up

```zsh
# Reproduce the coverage numbers:
DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-)
psql "$DATABASE_URL" -c "
SELECT count(*) FILTER (WHERE \"rawOutput\" ~ '---STRUCTURED---') AS has_json,
       count(*) FILTER (WHERE \"rawOutput\" ~ '## POSITION TYPE') AS has_prose
FROM \"Analysis\" WHERE \"createdAt\" < '2026-06-27 16:26:16-04';
"

# Confirm the backup is restorable (do this on a throwaway local DB, not prod/dev):
createdb analysis_corpus_test
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_schema_20260830.sql
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_20260830.sql
psql analysis_corpus_test -c 'SELECT count(*) FROM "Analysis";'   # expect 805
```
