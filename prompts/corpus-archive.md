# Corpus archive — backup discipline and a second failure domain

Closes `docs/handoffs/2026-09-03-state-of-play.md` §8's oldest open item:
*"Corpus backup. `~/investment-agent-backups/analysis_corpus_20260830.sql` still
needs an off-machine copy. §2.3 now makes it a formal release dependency, not
just a backup — without it the conformance fixtures cannot be regenerated at
all, and the model that produced it is retired."*

## Why this run exists

This is an **archive** problem, not a backup problem. A backup protects mutable
state you can recreate; the analysis corpus was scored by
`claude-sonnet-4-20250514`, which is retired, so it **cannot be regenerated at
any price** — and `PROMOTION_GATE.md` §2.3 makes it a release dependency for the
conformance fixtures.

Current state: the artifacts exist at
`~/Dropbox/LUIS/Backups/investment-agent-backups`, and the working tree lives
under `~/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/`.
**Both are inside one Dropbox account** — one failure domain. That survives disk
failure and an accidental `rm`, but not account compromise, a billing lapse, a
sync bug, or ransomware propagating through Dropbox.

This run builds the discipline and puts a copy in a genuinely independent
provider.

**No LLM calls, no API spend, no DB writes, no cache refresh.** A dump and a
scratch-database restore are reads. Work on `sweep/db-corpus-baseline`. Write
findings to `./wrap-ups/corpus-archive-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`corpus-archive`**, state in `analysis/data/run_state/<run_id>/`
per the standing convention in `CLAUDE.md`. Write `progress.json` before reading
anything, update it after every step, append to `findings.md` as findings land.

## Step 0 — hygiene, and verify the inventory before touching anything

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Stash and pop
rather than staging unrelated changes. `testing/` stays gitignored.

**Never commit a dump, a cache, or `.env` content to THIS repo.** The archive is
a separate repository (Step 2). Add `.gitignore` entries if needed.

Inventory as observed 2026-09-04 — **confirm each before relying on it**:

```
~/Dropbox/LUIS/Backups/investment-agent-backups/
  analysis_corpus_20260830.sql           43.3 MB   data only, INSERT format
  analysis_corpus_schema_20260830.sql     6.1 KB   DDL only
  caches_20260830/price_cache.json        3.2 MB
  caches_20260830/fundamentals_cache.json  13 KB

sha256(analysis_corpus_20260830.sql) =
  a5df033cb6c6cc20f493bccbb9f86b28a73b0f210d7fdbb254411caaa8896923
```

Established by inspection, to re-confirm:

- The data dump covers **exactly three tables** — `Ticker`, `Transcript`,
  `Analysis` — and no others. No Clerk or auth tables. The artifact contains
  only analyses of public earnings calls, which is what makes it safe to store
  outside Dropbox.
- It is **complete, not truncated**: ends `PostgreSQL database dump complete`,
  and the `\restrict` / `\unrestrict` tokens match.
- **1,558 INSERT statements: 45 `Ticker`, 708 `Transcript`, 805 `Analysis`.**
  Cross-check: state-of-play §4.4 accounts for 42 stamped + 764 unstamped = 806
  Analysis rows, one more than this dump, which predates that work. Confirm the
  reconciliation or report the discrepancy.
- Schema and data are **separate files**. A data-only dump is unrestorable
  without its schema, and that dependency is not obvious from the filenames.
  Treat them as one indivisible artifact everywhere below.

### A read-only database role (recommended, not blocking)

Create a Postgres role with `SELECT` on `Ticker`, `Transcript` and `Analysis`
and nothing else, and use its URL for every backup path — the local script and
the workflow in Step 4.

This is **not a confidentiality measure** — the corpus is analyses of public
earnings calls, and none of the three tables holds personal data. It is a
blast-radius measure: a backup credential with write access can damage the live
corpus it exists to protect, and the archive must be harder to destroy than the
thing it protects. `CREATE ROLE` plus `GRANT SELECT` is a write to the *catalog*
and is the one exception to this run's no-DB-writes rule; it touches no table
data. If it cannot be created for any reason, proceed with the existing
credential and **record that as a known weakness** rather than blocking.

**Do not regenerate this dump before it has been copied out.** It is verified
complete now; a fresh dump is a new artifact with new failure modes, and the
corpus has grown by roughly one row since. Replacing a known-good file with an
unverified one is the exact anti-pattern this run exists to prevent. The
existing artifacts seed the archive; the script produces the *next* one.

---

## Step 1 — create the archive repository and seed it with what exists

A **new private GitHub repository**, suggested `investment-agent-corpus`,
separate from the main repo. It supplies the three properties the current setup
lacks: a provider independent of both the laptop and Dropbox, version history,
and content addressing.

Seed it with the **existing verified 20260830 artifacts**, unmodified:

```
corpus/analysis_corpus_20260830.sql
corpus/analysis_corpus_schema_20260830.sql
corpus/analysis_corpus_20260830.sql.sha256
caches/20260830/price_cache.json
caches/20260830/fundamentals_cache.json
README.md
```

### Commit the SQL uncompressed — this reverses earlier advice, deliberately

The obvious move is to gzip first: 43.3 MB compresses to 13.5 MB (31.2%). **Do
not do that.** Git delta-compresses similar blobs across commits, and this
corpus is **append-mostly** — each new dump is the previous one plus a few
hundred KB of new rows. Committing plain text lets git store later versions as
small deltas. Gzipping (or `pg_dump -Fc`) defeats delta compression entirely,
because compressed streams diverge completely from one byte of change, and every
version then costs a full ~13 MB forever.

Rough arithmetic over a year of weekly runs, assuming the corpus changes maybe
monthly: compressed ≈ 13 MB × 12 ≈ 160 MB of history; plain text ≈ 13 MB once
(git's own zlib) plus small deltas ≈ well under 20 MB.

Two consequences to record in the README:

- 43.3 MB is above GitHub's **50 MB warning** threshold and below the **100 MB
  hard limit**. The push works and warns. No Git LFS.
- Growth is slow — 805 analyses today, and the corpus only grows when a
  transcript is evaluated — so the 100 MB wall is years away. **Note it as a
  known future limit** with the fallback (LFS, or splitting `Analysis` by year)
  rather than pre-solving it.

If a dump ever approaches 100 MB, that is a finding, not a thing to work around
silently.

### README.md must record

What the artifact is; that `claude-sonnet-4-20250514` produced it and is
retired, so it is irreplaceable; the schema+data pairing; the exact restore
command; that it is a `PROMOTION_GATE.md` §2.3 release dependency; and the §4.4
provenance caveat — that the unstamped rows have **circumstantial, not
provable** v6 provenance and the `data/evals/v6/` directory that would have
proved it has been deleted.

The dump plus that context is the citable artifact. The dump alone is not.

---

## Step 2 — the dump script

`scripts/dump_corpus.sh` in the **main** repo — one implementation, invoked
both from your terminal and from the GitHub Actions runner in Step 4.

**Portability constraint, and it overrides the usual macOS-only standing rule
for this file only.** The script runs on macOS/zsh locally *and* on
`ubuntu-latest` in CI. Write it `#!/usr/bin/env bash`, POSIX-ish, no zsh-only
syntax, no BSD-vs-GNU flag assumptions (`sed -i` and `stat` differ; prefer
`python3` for anything fiddly). Everything else in Standing Rules still holds
for the local path.

- Reads `DATABASE_URL` from the repo `.env`. **Never echo it**, never write it
  to any output file, never include it in a manifest or commit message.
- Dumps **only** `"Ticker"`, `"Transcript"`, `"Analysis"`, data and schema as
  two files, plain SQL, matching the existing artifacts' shape.
- Prefer `COPY` format over `--inserts` **only if** it materially reduces size;
  measure and report. The bulk here is narrative `rawOutput` text, so the
  per-row `INSERT INTO …` prefix may be negligible — do not assume, measure.
  Keeping the existing INSERT format for continuity is an acceptable answer.
- Output `analysis_corpus_YYYYMMDD.sql` + `_schema_YYYYMMDD.sql` + `.sha256`,
  **date-stamped, never overwriting.** An overwriting copy is a mirror, and
  mirrors propagate corruption.
- Also emits `corpus_census_YYYYMMDD.txt`:

```sql
SELECT a."promptVersion", a."modelVersion", COUNT(*) AS rows,
       MIN(t."callDate")::date AS earliest, MAX(t."callDate")::date AS latest
FROM "Analysis" a JOIN "Transcript" t ON a."transcriptId" = t.id
GROUP BY 1,2 ORDER BY 1,2;
```

## Step 3 — verification, or it is not a backup

The script **verifies and reports; it never silently succeeds**:

- Per-table row counts from the live DB, and from the dump, recorded and
  compared.
- Assert the completion marker and matching `\restrict` / `\unrestrict` tokens.
- Compare `sha256` against the most recent previous dump. **Identical means the
  corpus did not change** — record that, skip the write, exit 0.
- Compare size against the previous dump. **A sharp drop is a truncation signal
  and must exit non-zero**, not warn.
- Assert the dump contains only the three expected tables — if a fourth ever
  appears, that is a scope leak and must fail.

**Once, in this run, do a real restore**: create a scratch local Postgres
database, restore schema then data, count rows, confirm they match live, drop
it. Report it. A dump that has never been restored is untested, and §2.3 makes
this a release dependency. If no local Postgres is available, say so and record
the restore test as **not done** — do not substitute a parse check for it.

Every run ends printing checksum, per-table row counts and file size. A silent
backup failure is worse than no backup: it manufactures confidence.

## Step 4 — GitHub Actions owns the periodic push

**The trigger lives in CI, not on the laptop and not in the app.** A device-
bound scheduled task only fires when the laptop happens to be awake, and a
backup that silently does not run is the failure mode this whole run exists to
design out.

Add `.github/workflows/corpus-archive.yml` **to the archive repository**:

- `schedule:` weekly cron, plus `workflow_dispatch:` so it can be run by hand.
- `DATABASE_URL` as a repository secret — the read-only role's URL if Step 0
  created one.
- **Install a PostgreSQL 18 client on the runner.** This is the gotcha that will
  break the first attempt: `ubuntu-latest` ships an older `postgresql-client`,
  and `pg_dump` refuses to dump a newer server (live server is **18.6**). Add
  the PGDG apt repository and install `postgresql-client-18` explicitly. Pin the
  major version; do not rely on whatever the image happens to carry. **This is
  the one place `apt` is permitted** — the no-Linux-package-manager standing
  rule governs the laptop, not the CI runner.
- Run `scripts/dump_corpus.sh` (vendor it into the archive repo, or check out
  the main repo as a second step — pick one and say why).
- Commit and push **only when the checksum moved**. An unchanged corpus produces
  no commit.
- Commit message: date, per-table row counts, sha256. No credentials.
- Never `git push --force`. Never rewrite archive history.
- Fail the job on any verification failure from Step 3, so GitHub's default
  failure email fires. **A green run that backed nothing up is worse than a red
  one.**

Confirm by dispatching it manually once and reporting the run URL, the duration,
and whether it produced a commit (it should not, if it dumps the same corpus the
20260830 artifacts already hold — a no-op first run is the *correct* result and
proves the change detection works).

Report the free-tier minutes the job consumes against the 2,000/month private-
repo allowance.

## Step 5 — the app's half, recorded as a deferred product item

The app is the only thing that knows the *moment* the corpus changes, but it
must not own custody: a backup taken by the thing being backed up shares its
bugs, and an app with push rights to the archive can also destroy it.

The right split is **the app declares state, external infrastructure acts on
it** — the same layering discipline as the analyst/allocator firewall.

Record in `BUILD_STATE.md` under Open Questions, as a **deferred product item,
not work for this run** (the way `PROMOTION_GATE.md` §10 records the
instrumentation UI): a cheap read-only corpus-integrity endpoint exposing
per-table row counts, `max("createdAt")`, and a content hash of `Analysis`, so
any external agent can ask whether the corpus changed without pulling 43 MB to
find out. Note it as the same family as §8's startup hash-check item.

**Do not build it, do not add a route, do not touch the server.** One paragraph
in `BUILD_STATE.md`.

## Step 6 — report

Scope boundary: **build the script and the archive; decide nothing else.** Do
not amend `PROMOTION_GATE.md` or any spec, do not edit the state of play, do not
resolve other §8 items.

Open with resume status, then:

> **Archive: [repo URL], seeded with the verified 20260830 artifacts at
> [commit]. Format: plain SQL uncompressed, [N] MB, delta-friendly. Script:
> `scripts/dump_corpus.sh`, verified by [full restore into scratch DB — row
> counts match / not done because X]. Schedule: GitHub Actions weekly, first
> manual dispatch [run URL] took [N]s and [did / did not] commit. DB role:
> [read-only role created / existing credential, weakness recorded]. §8 corpus
> item: [closed — a copy now exists outside the Dropbox account / still open
> because X].**

Flag plainly: anything that makes the artifact less durable than it appears, any
precondition that would make an unattended run fail **silently**, and — if
noticed in passing — that `testing/` is untracked rather than gitignored on
`dev` while holding real brokerage exports, which is a **flag only, not this
run's job to fix**.

**§8 may only be recorded closed once a copy exists outside the Dropbox
account.** Two folders in one Dropbox are one failure domain.

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop** — including the inventory figures in Step 0 and
the compression arithmetic in Step 1.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions. `brew install` if a tool is genuinely
  missing. **Two scoped exceptions, both stated above:** the dump script is
  `bash`/POSIX-ish because CI also runs it (Step 2), and the Actions workflow
  uses `apt` to install `postgresql-client-18` (Step 4).
- **No DB writes**, with one exception: the `CREATE ROLE` / `GRANT SELECT` in
  Step 0, which touches the catalog and no table data. Dumps and a scratch-
  database restore are reads.
- Never print, log or commit `DATABASE_URL` or any credential.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Do not commit dumps, caches or `.env` to the main repo.
- Report wall-clock runtime.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
