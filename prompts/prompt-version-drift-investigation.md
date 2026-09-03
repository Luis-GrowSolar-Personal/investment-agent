# Prompt- and model-version drift — establish scope, not mechanism

`av_transcript_fidelity_benchmark_1` surfaced that `docs/EVALUATION_PROMPT.md`
declares `v10+auto1 (auto-iterate candidate — pending gate)` while
`server/lib/versions.js` stamps `v6`.

**The mechanism is already established and this run must not spend budget
rediscovering it.** The design session read the working tree on 2026-09-02 and
confirmed, with provenance:

| Fact | Evidence |
|---|---|
| `evaluate.js` reads the prompt file directly | `server/routes/evaluate.js:12-13` — `PROMPT_PATH = path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md')`, then `const systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8')` |
| It is read **once, at module load**, not per request | same lines — module scope, not inside the handler |
| `PROMPT_VERSION` is a **hardcoded constant**, not derived from the file | `server/lib/versions.js:18` — `const PROMPT_VERSION = 'v6';` |
| The stamp is therefore structurally decoupled from the content | `evaluate.js:81` writes `promptVersion: PROMPT_VERSION` |
| Working-tree prompt file | sha256 `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14`, header line 2: `# Version: v10+auto1 (auto-iterate candidate — pending gate)` |

So on the working tree, a deployed build would send v10+auto1 and label it v6.
**What is not established is whether that build is deployed**, and that is the
question this run exists to answer first.

**A second, independent finding the benchmark did not raise.** `versions.js:19`
declares `MODEL_VERSION = 'claude-sonnet-4-6'` with the comment
`2026-06-27: dated snapshot retired by Anthropic; reverted to sonnet-4-6`. Two
things are wrong with that on its face:

- `data/gate_ledger.json` entry 1 records champion `v6_sonnet-4-20250514`,
  challenger `v6_sonnet-4-6`, `delta_pp: -7.44` against `noise_std_pp: 4.2`,
  `robustness_ok: false`, `final_verdict: "HOLD"`. Production is stamped with
  the model the gate **explicitly rejected**.
- `claude-sonnet-4-6` is not a dated snapshot, which `PROMOTION_GATE.md` §8
  requires ("never a bare / `-latest` alias"). If Anthropic genuinely retired
  the pinned snapshot the migration may have been forced — but a forced
  migration to a HOLD-verdict model is a process exception that should have been
  recorded, and this run must establish whether it was.

**Treat the model-version question as co-equal with the prompt-version
question.** It is arguably the larger one: the prompt affects what the analyst
says, the model affects that too *and* the gate has already measured this
specific substitution as a 7.44pp regression.

---

## Ground rule — investigate and report only

Per `PROMOTION_GATE.md` §1 ("Nothing auto-promotes") and §8, any decision to
promote, roll back, relabel or re-pin is Luis's, not this session's, **even if
the correct fix is obvious once found.**

**Do not:** edit `evaluate.js`, `versions.js`, `docs/EVALUATION_PROMPT.md`, the
Prisma schema, the database, or `analysis/data/gate_ledger.json`. Do not run the
promotion gate. Do not backfill, relabel or delete any stored row. Do not
redeploy, restart or roll back any Railway service. Do not re-run any
evaluation. **No LLM calls, no API spend, no DB writes** — every query in this
run is `SELECT` only.

Read `PROMOTION_GATE.md` §1, §2.2, §8 and §10, and
`ALLOCATOR_OPERATING_MODEL.md` §10b, before starting. Decisions there are closed.

Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.

---

## Step −1 — resume protocol

`run_id` is **`prompt-version-drift-investigation`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.

**Write state before reading anything.** Create the directory and an initial
`progress.json` — every step `pending`, `next_action` set to "spec reading not
yet started" — as the very first action of the session. Then update
`progress.json` after every step and **append to `findings.md` the moment a
finding is established**, in the wording the report will use. This run is a
sequence of independent facts rather than a cell grid; `cells.jsonl` is not
used, and `progress.json` should say so.

Findings here have unusual value per token. Never hold one in memory for a final
composition pass.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Record the
current commit. Do not stage or commit unrelated working-tree changes — stash and
pop. `testing/` stays gitignored.

## Step 1 — what is actually deployed (do this first)

**This gates everything downstream. Reading the working tree does not answer it:
the running process holds whatever `docs/EVALUATION_PROMPT.md` contained at the
moment it started.**

For **both** Railway services (dev and prod):

- the commit SHA currently deployed, and the deploy timestamp
- `docs/EVALUATION_PROMPT.md` **as it exists at that commit** — its declared
  version header, quoted exactly, and its sha256
- `server/lib/versions.js` at that commit — the literal `PROMPT_VERSION` and
  `MODEL_VERSION` values
- whether the service has restarted since deploy (a restart re-reads the file
  from the deployed image, not from disk, so it does not change the answer — but
  record it)

Use `railway status` / `railway deployments` or the Railway dashboard; if the
CLI is not authenticated, say so and get the SHA from the dashboard rather than
inferring it from `git log`.

**Early exit.** If the deployed commit's prompt file declares `v6` and hashes to
a v6 blob, there is **no live contamination** and hypothesis 2 holds: the working
tree carries a staged draft. Record that as the headline, skip Step 5's live-row
scoping, and go straight to Steps 3, 4 and 6 — the corpus and model questions
stand on their own regardless.

## Step 2 — how the labels are derived

Confirm the table at the top of this prompt against the **deployed** commit
rather than the working tree, and add:

- is there any other code path that sends a prompt to the analyst — a second
  copy of the file, an inline fallback string, an env-var override, a cached
  build artifact? Search rather than assume; `evaluate.js` being the only caller
  is a claim that needs evidence.
- does anything anywhere derive a version from file content (a hash, a header
  parse)? A hardcoded constant nobody updates and a broken derivation are
  different bugs with different fixes.

## Step 3 — corpus homogeneity (the load-bearing question)

**Scope the damage to the backtest corpus before scoping it to production
rows.** Every settled figure in `ALLOCATOR_OPERATING_MODEL.md` §0 — $184,819,
17.32% drawdown, K=30, 2.5pp — was tuned against
`analysis_corpus_20260830.sql`. Each run manifest records `prompt_version` and
`model_version` as a **single string for the whole corpus**. If the corpus is
internally mixed, that field is not stale, it is **false**, and under §10b a
result whose manifest misstates its inputs is not citable. That would put the
settled configuration in question, which relabelling cannot repair.

**Start from the prior recon, do not redo it.** Read
`wrap-ups/recon-analysis-table-v6-corpus-out.md`. The manifests already carry its
verdict in their own version fields, verbatim:

> `v6 (circumstantial -- see recon-analysis-table-v6-corpus-out.md; 6/805 rows explicitly tagged, rest inferred from createdAt window)`

Then establish, with counts and date ranges rather than estimates:

1. **Do the backtest and production share one `Analysis` table?** The simulator
   loads events from Postgres (`analysis/simulator/data.py:load_call_events`) and
   `evaluate.js` writes to Postgres. If those are the same rows, production drift
   contaminates the corpus *directly* and the two pipelines are not independent —
   which is the opposite of what the benchmark's framing assumed. Establish this
   explicitly; it is the hinge of the whole investigation.
2. The distribution of `promptVersion` and `modelVersion` across all `Analysis`
   rows **inside the backtest window** — `GROUP BY` both columns, with NULLs
   counted, not dropped.
3. The same distribution by `createdAt` month, so a seam is visible if one exists.
4. Read `analysis/rebackfill_v6_analyses.py`: what did it actually rewrite, over
   which rows, and did it stamp versions or leave them NULL? A wholesale
   regeneration under a single version is the reassuring answer and would make the
   corpus homogeneous regardless of what production drifted to. **Say which it is.**

The schema **does** carry the columns — `promptVersion` and `modelVersion` on
`model Analysis`, added in the `add_version_columns` migration
(`server/prisma/schema.prisma:103-104`), both nullable. So the queries are
answerable; the risk is that most rows are NULL, not that the columns are
missing. Report the NULL count as a first-class number.

Read-only, via the standing pattern:

```zsh
cd server && DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-) \
  psql "$DATABASE_URL" -c "SELECT ..."
```

## Step 4 — content-hash timeline, not header diffs

`git log -p` on the version header finds when the *header* changed. A file whose
header still says `v6` while its body was edited is the same bug with better
camouflage and is invisible to that scan.

For every commit that touched `docs/EVALUATION_PROMPT.md` (use `--follow`),
report a row: commit, date, declared version header (quoted), and the **sha256 of
the file's content at that commit** (`git show <commit>:docs/EVALUATION_PROMPT.md
| shasum -a 256`). The content-hash timeline is the real one; the header timeline
is a claim about it.

Do the same for `server/lib/versions.js`, and answer:

- the last commit that changed `PROMPT_VERSION`, and the last that changed
  `MODEL_VERSION`, with their messages quoted
- every commit where the prompt file's **content hash** changed and `versions.js`
  did not — the origin point if this is a missed label rather than something
  deliberate
- **name the commit at which the file last declared v6, and its content sha256.**
  Remediation option A below is not actionable without it, and no step in the
  original brief produced it.

## Step 5 — live contamination scope

Only if Step 1 found a drifted build deployed. Anchor the window to the **deploy
timestamp**, not the commit date — rows written before the deploy were scored by
the previous build.

Report exact counts and date ranges for `Analysis` rows created after that
timestamp, split by `promptVersion` and `modelVersion` as stored. State plainly
which stored labels are known false and which are merely unverified.

If the deploy timestamp cannot be established from Railway, say so and give the
count as a bounded estimate against the commit date, labelled as an estimate.

## Step 6 — gate records

- Quote `data/gate_ledger.json` entry 1's `champion` field exactly. That is the
  authoritative statement of what was supposed to be live, and it is stronger
  evidence than `versions.js`, which is a constant someone types by hand.
- Has any entry ever tested v7, v8, v9, v10 or v10+auto1, or any prompt /
  eval-logic change under §2.2a? A one-line "no" is the expected answer and
  should take seconds — the value here is the champion field, not the search.
- Is there any ledger entry, commit message or wrap-up recording the 2026-06-27
  model change as a deliberate process exception? If none exists, say so: an
  unrecorded migration to a HOLD-verdict model is itself a §8 finding.
- Quote `docs/EVALUATION_PROMPT.md`'s own iteration log on v7–v10 exactly, in
  particular anything it claims about its own gate status and about what v6 was.

## Step 7 — report

Luis has explicitly asked for a findings document, so `CLAUDE.md`'s handoff rule
applies: write it to **`docs/handoffs/<YYYY-MM-DD>-prompt-version-drift.md`**
**and** a `.docx` alongside it with the same base name, tables rendered as real
Word tables. Both are deliverables; keep them identical in content. The session's
own `wrap-ups/prompt-version-drift-investigation-out.md` stays a thin close-out
and stays `.md`-only.

The report carries, in this order:

1. **Headline** — is there live contamination, yes or no, with the deployed SHA
   and deploy timestamp as evidence.
2. **Corpus verdict** — homogeneous or seamed, with counts; and explicitly
   whether anything in §0's settled configuration is disturbed. If the corpus is
   clean, say so as plainly as if it were not.
3. **Model-version finding** — separately from the prompt finding.
4. **Timelines** — both content-hash tables.
5. **Contamination scope** — counts and ranges, or a labelled bounded estimate.
6. **Remediation options**, presented and **not chosen**:
   - **A. Roll back** `docs/EVALUATION_PROMPT.md` to the v6 blob named in Step 4
     and re-deploy, leaving v10+auto1 as an ungated candidate awaiting a §2.2a
     run. Restores the gate's intended order.
   - **B. Ratify** — leave v10+auto1 running, correct `versions.js`, relabel
     affected rows, and run the gate retroactively. Flag prominently that this
     inverts gate-then-promote and is a process exception, not a precedent.
   - **C. Quarantine** — stop generating new analyses until the decision is made.
     There is no time pressure, and every evaluation run during deliberation
     deepens whatever the problem turns out to be. **This is compatible with A
     and B and should be presented as an immediate step either way, not as a
     third alternative to them.**
   - **D.** Anything Steps 1–6 revealed that is none of the above — including
     "there is no live contamination," if that is what the evidence says.
   - The model-version question gets its **own** option set. Re-pinning to a
     dated snapshot may be impossible if `claude-sonnet-4-20250514` is genuinely
     retired; if so, say what the available dated snapshots are and note that
     adopting one is a §2.2b equivalence-hurdle gate run, not a config edit.
7. **Prevention** — separate from remediation, and required. At minimum: have the
   server hash the prompt file it loaded at startup and refuse to boot if the
   hash does not match the version `versions.js` declares. Roughly five lines,
   and it makes silent drift between the declared version and the loaded content
   structurally impossible. This is the live-system counterpart to
   `CONFORMANCE_FIXTURES.md` — the same principle, that the validated artifact
   and the running artifact must be provably the same object. Propose it; do not
   implement it.
8. **Your read of the evidence** — which option the evidence points toward and
   why, framed explicitly as a read for Luis to weigh, not an action taken.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**, no deploys, no restarts.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay frozen
  at 2026-05-11.
- **Every figure quoted must name its provenance** — the file and the exact key,
  or the commit and the path. A bare number is how the last two-session
  debugging detour started.
- Quote headers, commit messages and ledger fields **exactly**; do not paraphrase.
- **A finding that contradicts an expectation stated in this prompt is a finding,
  not a reason to stop.** The design session's reading of the working tree is a
  premise to verify against the deployed build, not a conclusion.
- Complex commands and SQL in fenced blocks in the report, not separate files.
- Report wall-clock runtime and whether the run was complete or partial.
