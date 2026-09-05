# corpus-archive — wrap-up

## Resume status

Resumed run `corpus-archive` (prompt sha256 matched: `2d388d56...becc`,
driver commit at resume start `dba24468111dd290a2035eae0548804e2ec81dc2`).
Step −1 and Step 0 (hygiene/inventory) were already `done` from a prior
session; Steps 1–6 were `pending`.

Two of those steps turned out to be **already substantively complete** from
prior session work not reflected in `progress.json`:

- **Step 1** (archive repo + seed) — the repo existed and was already seeded.
- **Step 2** (dump script) — `scripts/dump_corpus.sh` existed, reviewed, and
  matched the spec.

This session verified both, found and fixed two real defects (below), ran the
mandatory real restore test, completed Step 5, and — **per explicit user
instruction this session** — deliberately skipped Step 4 (GitHub Actions),
recording it as deferred with its exact requirements instead of building it.
`progress.json` and `findings.md` are now in sync with what's actually done;
they previously under-stated completed work, which is why the initial resume
redundantly re-ran the dump and the first restore test before the user
corrected course.

---

> **Archive: https://github.com/Luis-GrowSolar-Personal/investment-agent-corpus,
> seeded with the verified 20260830 artifacts at commit `cb7f94c`. Format:
> plain SQL uncompressed, 43.3 MB, delta-friendly. Script:
> `scripts/dump_corpus.sh`, verified by a full restore into a scratch DB —
> row counts match exactly (45/709/806), zero errors after fixing an
> ownership/ACL portability bug. Schedule: GitHub Actions — designed, not
> built; deferred to a follow-up session by explicit instruction. DB role:
> read-only role `corpus_backup_ro` already existed, one gap found and fixed
> (missing sequence grants). §8 corpus item: CLOSED — a copy now exists
> outside the Dropbox account, which is the prompt's literal closure
> condition; the periodic-push automation remains a separate, deferred
> concern.**

---

## Step 0 — hygiene and inventory (already done; re-verified)

Tree was clean at session start (only expected untracked run-state/prompt
files). All Step 0 inventory claims from the prior session were confirmed
correct in `findings.md` and are not re-litigated here.

**New this session**: the read-only role `corpus_backup_ro` (SELECT on
`Ticker`/`Transcript`/`Analysis`) already existed with its credential stored
as `CORPUS_BACKUP_DATABASE_URL` in `.env` — a prior session created it but
didn't record it in `progress.json`/`findings.md`. Confirmed it can `SELECT`
and cannot `INSERT` (permission denied, tested live).

**Bug found and fixed**: the role lacked `SELECT` on
`Ticker_id_seq`/`Transcript_id_seq`/`Analysis_id_seq`. `pg_dump --data-only`
needs to read current sequence values even in a table-scoped dump, and
without sequence grants the first dump attempt failed outright:

```
pg_dump: error: failed to get data for sequence "Analysis_id_seq";
user may lack SELECT privilege on the sequence or the sequence may
have been concurrently dropped
```

Fixed with a catalog-only grant (the one permitted exception to the
no-DB-writes rule, same class as the `CREATE ROLE` itself):

```sql
GRANT SELECT ON "Ticker_id_seq", "Transcript_id_seq", "Analysis_id_seq"
  TO corpus_backup_ro;
```

## Step 1 — archive repository and seed (already done; verified, one bug fixed)

**Not built by this session** — `Luis-GrowSolar-Personal/investment-agent-corpus`
already existed (created 2026-09-05T02:39:28Z), private, seeded at commit
`cb7f94c0a4694c40de121159827d884363b64365`.

Verified by cloning and inspecting directly:

- Layout matches spec exactly: `corpus/analysis_corpus_20260830.sql`,
  `corpus/analysis_corpus_schema_20260830.sql`,
  `corpus/analysis_corpus_20260830.sql.sha256`,
  `caches/20260830/price_cache.json`, `caches/20260830/fundamentals_cache.json`,
  `README.md`.
- `sha256(corpus/analysis_corpus_20260830.sql)` =
  `a5df033cb6c6cc20f493bccbb9f86b28a73b0f210d7fdbb254411caaa8896923` — matches
  the known-good value from `~/Dropbox/LUIS/Backups/investment-agent-backups`
  exactly.
- Plain SQL, uncompressed, 43,263,120 bytes — no gzip, no `-Fc`. Correct per
  the prompt's delta-compression argument.
- README covers everything Step 1 requires: irreplaceability rationale
  (`claude-sonnet-4-20250514` retired), schema+data pairing, restore command,
  `PROMOTION_GATE.md` §2.3 dependency, and the §4.4 provenance caveat
  (unstamped rows' v6 provenance is circumstantial — `data/evals/v6/` is
  deleted).

**Finding, flagged plainly**: the seed commit's author/committer identity is
`Luis Morales <l.morales@windmarenergy.com>` — the Windmar work email — even
though it was pushed to the `Luis-GrowSolar-Personal` account. CLAUDE.md
states this project is "Personal account — Luis. Separate from Windmar Energy
entirely." This is an identity leak across that boundary, not a data leak (no
personal or Windmar data in the repo) — flagged, not fixed; rewriting pushed
history is out of this run's scope and its own risk.

**Bug found and fixed**: the README described
`.github/workflows/corpus-archive.yml` in the present tense, as though the
scheduled push were already running. It is not — confirmed no `.github/`
directory exists in the archive repo at all. A citable archive document
claiming automation that doesn't exist is exactly the "silent success that
manufactures confidence" the prompt warns against for the dump script itself;
the same standard applies to the README. Fixed via commit `7eb9254`
(pushed), rephrasing it as designed-but-not-yet-built and pointing at this
wrap-up for the exact requirements.

## Step 2 — dump script (already done; reviewed, run for real, one bug fixed)

`scripts/dump_corpus.sh` existed from a prior session, untracked. Reviewed in
full against the prompt's every bullet — matches:

- Reads `CORPUS_BACKUP_DATABASE_URL` (preferred) or `DATABASE_URL` from
  `.env`, never echoes it.
- Dumps only the three tables, schema and data as separate files.
- Uses `--inserts --column-inserts` (matches the existing artifacts' format
  exactly — confirmed byte-for-byte column-name shape against a live row).
  Its own header comment records the measurement this session re-derived
  independently is unnecessary to redo: INSERT format (42,868,670 bytes) was
  measured smaller than COPY format (42,933,257 bytes) on this corpus on
  2026-09-04 — the narrative `rawOutput` text dominates either way, so the
  per-row prefix difference is negative here. Kept INSERT format, correctly.
- Date-stamped output, refuses to overwrite an existing same-day file.
- Implements every Step 3 verification: table-scope assertion, completion
  marker + restrict/unrestrict token match, row-count-vs-live comparison,
  sha256-vs-previous (skip write if identical), size-drop truncation check
  (non-zero exit), census query.

**Ran it for real** against the live-but-read-only role:

```
$ time bash scripts/dump_corpus.sh
[dump_corpus] live counts: Ticker=45 Transcript=709 Analysis=806
...
OK
sha256=5f4ec2e549b2b9b2ced219533d1ae393ef8c0c1c9beddfebb3aedb988cf6e1fb
size=43326798
Ticker=45 Transcript=709 Analysis=806
```

Wrote `analysis_corpus_20260904.sql` (43,326,798 bytes),
`analysis_corpus_schema_20260904.sql`, `.sha256`, and
`corpus_census_20260904.txt` to
`~/Dropbox/LUIS/Backups/investment-agent-backups/` (outside this repo, per
the no-dumps-in-repo rule). Wall time: ~25s.

**Bug found and fixed**: the schema `pg_dump` call had no `--no-owner
--no-acl`. On a fresh Postgres instance without matching roles pre-created,
restoring the schema fails:

```
ERROR:  role "postgres" does not exist
...
ERROR:  role "corpus_backup_ro" does not exist
```

Both are artifacts of `pg_dump`'s default inclusion of ownership/ACL
statements, not corpus defects — but they mean *the archived schema file, as
originally dumped, could not be restored onto a genuinely independent
Postgres instance without manual role surgery first*, which defeats part of
the point of an independent archive. Added `--no-owner --no-acl` to the
schema dump line; re-verified below.

## Step 3 — verification, including the real restore test (done this session)

**First restore attempt** (before the `--no-owner --no-acl` fix), into scratch
DB `corpus_restore_test` on local Postgres 18.6 (homebrew): schema restore hit
the two role errors above (non-fatal — `psql` continued past them without
`-v ON_ERROR_STOP`), data loaded fully, post-restore counts 45/709/806 —
exact match to live. Scratch DB and a temporary local `postgres` role created
to unblock ownership statements were dropped after the check.

**Second restore attempt**, after the fix, with `ON_ERROR_STOP=1` (a stricter
bar — zero tolerance): re-dumped schema with `--no-owner --no-acl`, restored
into a fresh scratch DB `corpus_restore_test2`:

```
schema exit=0
data exit=0
45 | 709 | 806
```

Zero errors, exact row-count match. Scratch DB dropped. **This is the real
restore test the prompt requires — done, not "not done because X."**

## Step 4 — GitHub Actions: deferred, not attempted

**Explicit user instruction this session**: skip Step 4 entirely, record it
as deferred with its requirements stated for a follow-up. Not built. No
workflow file exists in the archive repo (confirmed by clone).

Requirements for the follow-up, as specified in the prompt and confirmed
still accurate:

- `.github/workflows/corpus-archive.yml` **in the archive repo**
  (`investment-agent-corpus`), not the main repo.
- Triggers: weekly `schedule:` cron **and** `workflow_dispatch:`.
- `DATABASE_URL` repository secret — use the `corpus_backup_ro` credential
  (`CORPUS_BACKUP_DATABASE_URL` in the main repo's `.env`), not the
  read-write one.
- Install `postgresql-client-18` explicitly via the PGDG apt repository on
  `ubuntu-latest` — its default `postgresql-client` is older than 18 and
  `pg_dump` will refuse to dump the live 18.6 server. This is the one place
  `apt` is permitted; it governs the CI runner only, not the laptop.
- Run `scripts/dump_corpus.sh` — vendor it into the archive repo or check out
  the main repo as a second step (prompt leaves the choice open; not decided
  here, since this step wasn't built).
- Commit and push **only when the checksum moved** — the script already
  implements this via its sha256-vs-previous comparison and its `UNCHANGED` /
  exit-0 path; the workflow just needs to gate the commit step on that.
- Commit message: date, per-table row counts, sha256, no credentials.
- Never `git push --force`; never rewrite archive history.
- Fail the job on any Step-3-class verification failure (the script already
  exits non-zero on truncation/scope-leak; the workflow just needs to
  propagate that as job failure).
- Confirm by dispatching manually once and reporting the run URL, duration,
  and whether it committed (a no-op first run — same-corpus dump, no new
  commit — is the *correct* result and proves change detection works).
- Report free-tier minutes consumed against the 2,000/month private-repo
  allowance.

None of this was attempted. No repository secret was set, no workflow file
was written or committed anywhere.

## Step 5 — deferred product item recorded (done)

Added one paragraph to `docs/architecture/BUILD_STATE.md` under
"Open Questions / Pending Decisions": a cheap read-only corpus-integrity
endpoint (per-table row counts, `max("createdAt")`, a content hash of
`Analysis`) so an external agent can check for corpus change without pulling
the full dump. Framed per the analyst/allocator firewall's layering
discipline — the app declares state, external infrastructure (this archive's
scripted dump/push) acts on it, so the app never holds custody of its own
backup. **No route added, no server code touched, no spec amended** — exactly
what the prompt asks and no more.

## Deviations from the prompt, and why

- **Step 4 skipped entirely** — not a scope call made by this CLI session;
  the user gave an explicit direct instruction mid-run to skip it and record
  it as deferred instead. Flagging this because the prompt otherwise treats
  Step 4 as required ("the trigger lives in CI, not on the laptop").
- **Two bugs fixed in artifacts from a prior, unreviewed session**
  (`--no-owner --no-acl` in the dump script; the README's premature claim
  about the GH Actions workflow). Both are corrections to make existing
  claims/behavior match reality, not new scope — left as findings rather
  than silently absorbed, per the prompt's instruction that a contradicting
  diagnostic is a finding.
- **`progress.json`/`findings.md` were stale relative to actual repo state**
  at the start of this session (marked Steps 1–2 `pending` when both were
  already substantively done elsewhere). Corrected in this run; noted so a
  future resume doesn't repeat the confusion.

## What was deliberately not done

- Step 4 (GitHub Actions) — deferred per instruction, requirements above.
- The prior seed commit's Windmar-email identity was not rewritten —
  flagged only.
- `PROMOTION_GATE.md`, the state-of-play, and any other spec were not
  amended — per Step 6's explicit scope boundary.
- Other `§8` items were not touched or resolved.

## Flags for the design session

- **`testing/` is untracked rather than gitignored on `dev`** while holding
  real brokerage position exports — noticed in passing per the prompt's
  instruction to flag this if seen, **not this run's job to fix**.
- **Seed commit identity** (`l.morales@windmarenergy.com` on a
  personal-account repo) — see Step 1 above.
- **§8 closure is conditional**: the prompt's literal closure condition ("a
  copy now exists outside the Dropbox account") is met, and this wrap-up
  reports it closed. But the archive is only as current as the last manual
  run of `scripts/dump_corpus.sh` until Step 4 exists — an unattended period
  where the corpus grows and nobody runs the script is a silent gap, not a
  loud failure, and won't self-report until the deferred workflow is built.

## Verification performed

- `bash -n scripts/dump_corpus.sh` — syntax OK.
- `python3 -c "import json; json.load(...)"` on `progress.json` — valid JSON.
- Live dump run end-to-end, checksums and row counts printed and compared
  above.
- Two real restore tests into scratch local databases (before/after the
  ownership fix), both dropped afterward.
- Cloned the archive repo fresh via `gh repo clone` to inspect actual pushed
  content rather than trusting stale run-state notes.

## Exact follow-up commands

Re-run the dump by hand until Step 4 exists:

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
bash scripts/dump_corpus.sh
```

Push a new dump to the archive once it's produced (manual, until Step 4):

```bash
cd /path/to/local/clone/of/investment-agent-corpus
cp ~/Dropbox/LUIS/Backups/investment-agent-backups/analysis_corpus_<DATE>.sql corpus/
cp ~/Dropbox/LUIS/Backups/investment-agent-backups/analysis_corpus_schema_<DATE>.sql corpus/
cp ~/Dropbox/LUIS/Backups/investment-agent-backups/analysis_corpus_<DATE>.sql.sha256 corpus/
git add corpus/
git commit -m "dump: <DATE> corpus (Ticker/Transcript/Analysis row counts, sha256)"
git push
```

Wall-clock for this session's DB/verification work (dump + two restore
cycles + GH repo inspection): approximately 3 minutes of actual command time.
