# Findings — prompt-version-drift-investigation

Append-only. Each entry written the moment it is established.

## Premise check: §0 figure attribution

The drift prompt says "Every settled figure in `ALLOCATOR_OPERATING_MODEL.md` §0
— $184,819, 17.32% drawdown, K=30, 2.5pp — was tuned against
`analysis_corpus_20260830.sql`." `ALLOCATOR_OPERATING_MODEL.md` §0 ("Settled
configuration") does NOT contain $184,819 or 17.32% — it lists drawdown ceiling
39.12% and X=2.5pp (2.5pp does match). The figures $184,819 / 17.32% / K=30 are
real and settled, but they live in `docs/handoffs/2026-09-01-allocator-state-of-play.md`
(lines 37, 45, 55) and in `analysis/data/run_state/autonomy-cadence-floor-and-veto/`
run logs, not in `ALLOCATOR_OPERATING_MODEL.md` §0. Minor misattribution in the
drift prompt's framing -- does not change the substance of Step 3's question
(whether the backtest corpus is prompt/model-homogeneous), since the corpus
(`analysis_corpus_20260830.sql`) is the same regardless of which doc quotes the
result. Flagging per Step 4 (verify premise) rather than silently substituting.

## Step 1: deployed builds

**DEV** (`railway status --json`, project `investment-agent-DEV`, service `investment-agent-DEV`,
environment `production`):
- Deployed commit: `37f535acb85e8edf9d48b663e41b24ec6b852777`, branch `dev`
- Deploy timestamp: `2026-08-25T14:36:46-04:00` (deployment id `2ecd3a86-9c37-4a26-a671-eca5b6c18165`, status SUCCESS)
- `docs/EVALUATION_PROMPT.md` at that commit: header line 2 = `# Version: v10+auto1 (auto-iterate candidate — pending gate)`;
  sha256 = `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14`
  -- **identical hash to the current working-tree file** quoted in the drift
  prompt's own evidence table. The v10+auto1 candidate was deployed, not staged.
- `server/lib/versions.js` at that commit: `PROMPT_VERSION = 'v6'`,
  `MODEL_VERSION = 'claude-sonnet-4-6'` (`git show 37f535a:server/lib/versions.js`)
- **VERDICT: LIVE CONTAMINATION CONFIRMED on DEV.** The deployed build sends
  v10+auto1 and labels stored rows `promptVersion: "v6"`. No early exit --
  proceed to Steps 3-6 with live-row scoping (Step 5) in scope.

**PROD** (project `investment-agent-PROD`, service `investment-agent-PROD`,
environment `production`):
- Deployed commit: `2830d274374ec20a41b02f06bd09b50d9c525a5e`, branch `main`,
  commit message "Add investment agent handoff brief", commit date `2026-04-04T16:32:59-04:00`
- **Deployment status: `FAILED`, `deploymentStopped: true`, `instances: []`**
  (deployment id `2bf4ba44-2b78-4675-bb5b-ddc578fb1a27`, created `2026-04-04T20:38:18.892Z`).
  Railway detected `nixpacksProviders: ["python"]` for this deploy, not Node.
- This commit **predates the current Node/Express application entirely**: `git
  ls-tree 2830d274 ` shows no `server/` directory at all -- only root-level
  Python backtest scripts (`backtest.py`, `backtest_extra.py`,
  `backtest_scenarios*.py`) and a top-level `EVALUATION_PROMPT.md` (not
  `docs/EVALUATION_PROMPT.md` -- different path, different era, sha256
  `cd9aeaba59e7b52fc0b0a7e5f7a8be6b567f4efc20969c9713a7829eacd8d01c`, not
  compared further since there is no `evaluate.js` at this commit to read it).
  `server/routes/evaluate.js` and `server/lib/versions.js` do not exist at this
  commit (`git show 2830d274:server/routes/evaluate.js` -> "exists on disk, but
  not in" that commit).
- **VERDICT: PROD is not running the analyst at all.** Its last deployment
  failed and the service holds zero instances. There is no prompt/model-version
  drift question for PROD because there is no live analyst evaluation happening
  there -- it predates the feature. Flagging plainly: **PROD (`investment-agent-PROD`
  on Railway) is not currently serving the application**, contrary to what
  `CLAUDE.md`'s "Hosting: Railway (dev and prod services)" line would suggest.
  This is a finding for the design session, not something this investigation
  resolves.

**Which DB the corpus queries hit.** Root `.env`'s `DATABASE_URL` host is
`interchange.proxy.rlwy.net:10140`. `investment-agent-db-dev`'s
`RAILWAY_TCP_PROXY_DOMAIN`/`PORT` (via `railway variables --service
investment-agent-db-dev`) is exactly `interchange.proxy.rlwy.net` / `10140`.
`Investment-agent-db-PROD`'s proxy domain is `shuttle.proxy.rlwy.net` (different
host) -- confirmed not a match. **All `SELECT` queries in this investigation
(and the prior `av_transcript_fidelity_benchmark_1` run) hit
`investment-agent-db-dev` -- the same database the live, contaminated DEV
service writes into.** This makes Step 3's corpus-homogeneity question directly
load-bearing rather than hypothetical: DEV's `evaluate.js` writes
`promptVersion: PROMPT_VERSION` (`'v6'`, hardcoded) into this same `Analysis`
table on every real evaluation it runs.

**Restart-since-deploy:** not independently established beyond the deployment
timestamp above; Railway's deployment record does not expose a separate
"process restart" event distinct from deploy in the CLI output available here.
Per the prompt's own note, this does not change the answer (a restart re-reads
from the deployed image, not from disk) -- recording as unestablished rather
than guessing.

## Step 2: how the labels are derived (confirmed against the deployed DEV commit)

`git show 37f535a:server/routes/evaluate.js` lines 12-13, verified against the
deployed commit (not just working tree): `PROMPT_PATH =
path.resolve(__dirname, '../../docs/EVALUATION_PROMPT.md')`, then `const
systemPrompt = fs.readFileSync(PROMPT_PATH, 'utf8')` at module scope --
confirms the table in the drift prompt's own preamble against the actual
deployed build, not just the working tree.

`git grep` across the deployed commit's full `*.js` tree for
`EVALUATION_PROMPT|systemPrompt|messages.create` found exactly three hits
beyond `evaluate.js` itself: `server/lib/portfolioImport.js:93` (a *separate*
Anthropic call, for Schwab CSV import parsing -- uses `claude-haiku-4-5-20251001`
per its own model constant, unrelated to the analyst prompt) and two doc-comment
references. **No second copy of the prompt file, no inline fallback string, no
env-var override was found.** `evaluate.js` being the only caller is confirmed
by search, not assumed.

**Second write site found:** `server/routes/save.js` also imports
`{ PROMPT_VERSION, MODEL_VERSION }` from `server/lib/versions.js` and stamps
them onto the persisted `Analysis` row (lines 175-176, comment: "Version
stamps — always server-controlled, never from client input"). This is not a
second bug -- `save.js` is the actual DB-write path (the frontend flow is
`evaluate.js` returns the LLM output, then a separate `/save` call persists
it); both call sites pull from the same hardcoded `versions.js` constants, so
there is exactly one source of truth for the stamp (correct in principle) and
it happens to be wrong in content (the finding above).

**No code anywhere derives a version from file content** (no hash, no header
parse) in the deployed commit's `*.js` tree -- `git grep` for
`shasum|sha256|crypto.createHash|Version:` found only the `versions.js`
doc-comment describing the *intended* manual-sync convention ("PROMPT_VERSION:
matches the 'Version: vN' header...") and the two write-site usages already
noted. **This is confirmed to be bug type "hardcoded constant nobody updated,"
not "broken derivation logic"** -- there is no derivation logic to break; a
human is expected to hand-edit the constant every time the prompt file
changes materially, and that manual step was missed for the v10+auto1 deploy.

## Step 3: corpus homogeneity (load-bearing)

**3.1 -- Do the backtest and production share one `Analysis` table? YES, confirmed.**
`analysis/simulator/data.py:167` reads `DATABASE_URL` from `os.environ.get("DATABASE_URL")`,
loaded from `../../.env` (`data.py:155` docstring, `ENV_PATH` construction) --
the same root `.env` already confirmed in Step 1 to point at
`investment-agent-db-dev` (`interchange.proxy.rlwy.net:10140`), the identical
database the live, contaminated DEV service's `evaluate.js`/`save.js` write
into. **Production drift contaminates the backtest corpus directly** -- the
two pipelines are not independent, confirming the hinge the prompt named.

**3.2/3.3 -- distribution of `promptVersion`/`modelVersion`, by column and by
month.** Starting from the prior recon (`wrap-ups/recon-analysis-table-v6-corpus-out.md`,
which already ran and reported this exact GROUP BY as of its 2026-08-30
snapshot: 764 NULL/NULL, 35 `v6`/`claude-sonnet-4-6`, 6 `v6`/`claude-sonnet-4-20250514`,
total 805). Re-running the same query live (this run, 2026-09-02/03) to check
for drift since the recon:

```sql
SELECT to_char("createdAt",'YYYY-MM') AS month, "promptVersion", "modelVersion", count(*)
FROM "Analysis" GROUP BY 1,2,3 ORDER BY 1,2,3;
```
```
  month  | promptVersion |       modelVersion       | count 
---------+---------------+--------------------------+-------
 2026-04 |               |                          |   194
 2026-05 | v6            | claude-sonnet-4-20250514 |     3
 2026-05 |               |                          |   570
 2026-06 | v6            | claude-sonnet-4-20250514 |     3
 2026-06 | v6            | claude-sonnet-4-6        |     1
 2026-07 | v6            | claude-sonnet-4-6        |    17
 2026-08 | v6            | claude-sonnet-4-6        |    18
```

**Total is now 806, not the recon's 805** -- one new row was written between
the recon's snapshot (2026-08-30) and this investigation (see 3.5/Step 5
below). Pre/post cutoff split (`createdAt` vs `2026-06-27 16:26:16-04`, same
cutoff timestamp the recon established as the last-v6-header commit):
**770 pre-cutoff, 36 post-cutoff** (recon had 770/35 -- the +1 is the new row).
The June bucket (4 rows) does not straddle the cutoff at the row level: the 3
`claude-sonnet-4-20250514` rows are 2026-06-14 (pre-cutoff), the 1
`claude-sonnet-4-6` row is 2026-06-28 (post-cutoff) -- consistent with the
recon's finding that no transcript's rows straddle the cutoff.

**3.4 -- `analysis/rebackfill_v6_analyses.py`: what it wrote, and whether it
stamped versions.** Read in full. Its `insert_v6_analysis()` function
(`rebackfill_v6_analyses.py:170-212`) issues an `INSERT INTO "Analysis" (...)`
whose column list **does not include `promptVersion` or `modelVersion` at
all** -- not set to a literal, simply absent from the statement, so those
columns take their NULL default on every row this script inserts. This is not
a bug in the sense of "should have stamped and didn't": the script's only git
commit is `22d2c71` (2026-05-02T12:33:23-04:00, "Full agent build..."), which
**predates** the `add_version_columns` migration
(`server/prisma/migrations/20260523191336_add_version_columns`, folder
timestamp 2026-05-23 19:13, committed to git 2026-05-30) by three weeks -- the
columns did not exist yet when this script was written, and it was never
revisited afterward to add them. **This fully explains the 764/770 NULL rows
as an artifact of migration ordering, not a mystery or active bug.**
By design (docstring: "Append a v6-consistent Analysis row per Transcript...
using the cached v6 evaluator outputs" from `data/evals/v6/<SYMBOL>_<DATE>.txt`),
it performs a **wholesale, single-source regeneration** -- every row it
inserts comes from the same `data/evals/v6/` cache directory, i.e. is v6 by
construction of its input source, even though the row itself carries no
explicit tag. This is "the reassuring answer" the prompt named as one
possibility. (The `data/evals/v6/` cache directory itself is empty on disk
today -- gitignored working data, presumably cleaned up after the one-time
backfill ran; its historical contents were not recoverable within this
investigation's read-only, no-new-LLM-calls scope, so "v6 by construction" is
supported by the script's stated design and commit-date reasoning above, not
by inspecting the actual cached text files that produced the 764 NULL rows.)

**Verdict on 3.1-3.4, stated plainly: the corpus is circumstantially
homogeneous, not provably so** -- exactly the recon's own prior conclusion,
now re-confirmed live and extended with the *why* (migration-ordering
explanation for the NULL rows, and confirmation the DB is shared with
production). Nothing in this investigation newly disturbs the settled §0
configuration figures ($184,819 / 17.32% / K=30, see the premise-check note
above for their correct location) -- those were computed from the same
`analysis_corpus_20260830.sql` backup the recon already vetted as
657/659-transcript-complete and internally cutoff-consistent for the pre-v10
window. The one new post-recon row (Step 3.5/Step 5) postdates that backup
entirely and was not part of any settled-configuration run.

**3.5 -- live drift since the recon snapshot.** `SELECT count(*) FROM
"Analysis"` returns **806** today, one more than the recon's 805
(`analysis_corpus_20260830.sql`, dumped 2026-08-30). The new row:

```sql
SELECT a.id, tk.symbol, t."callDate", t.title, a."createdAt", a.recommendation, a."thesisHealth"
FROM "Analysis" a JOIN "Transcript" t ON t.id=a."transcriptId" JOIN "Ticker" tk ON tk.id=t."tickerId"
WHERE a.id = 895;
```
```
 id  | symbol |      callDate       |                     title                      |        createdAt        | recommendation | thesisHealth  
-----+--------+---------------------+------------------------------------------------+-------------------------+----------------+---------------
 895 |   NVDA | 2026-08-26 00:00:00 | NVIDIA (NVDA) Q2 2027 Earnings Call Transcript | 2026-08-31 14:41:11.369 |            Add | Strengthening
```

This is a live, real evaluation (not a benchmark run -- `av_transcript_fidelity_benchmark_1`
made zero DB writes, confirmed by its own driver code) written through the
production `evaluate.js`/`save.js` path on **2026-08-31**, six days *after*
DEV's deploy at `2026-08-25T14:36:46-04:00` that carries the v10+auto1
content. It is stamped `promptVersion: "v6"`, `modelVersion:
"claude-sonnet-4-6"`. See Step 5 for full scoping.

## Step 4: content-hash timeline (not header diffs)

**`docs/EVALUATION_PROMPT.md` — every commit that ever touched it, content
hash at each, header quoted exactly:**

| Commit | Date | Path | Header (line 2, or none) | sha256 |
|---|---|---|---|---|
| `3bf13fa` | 2026-03-31T17:15:52-04:00 | `EVALUATION_PROMPT.md` (root) | *(no version header yet -- file predates the convention)* | `06a5f1ae55a7c6030d8e32c2d31c3ba9d55d87297391a006b69eca12597cc056` |
| `3a658b2` | 2026-04-04T16:54:42-04:00 | renamed root -> `docs/EVALUATION_PROMPT.md` | *(same, pure rename)* | `06a5f1ae55a7c6030d8e32c2d31c3ba9d55d87297391a006b69eca12597cc056` (unchanged) |
| `75596f2` | 2026-04-07T21:01:32-04:00 | `docs/EVALUATION_PROMPT.md` | *(structured score fields added; still no version header)* | `714ba3cc7517afa8a4956bab9f242566699192e9800882975ef5f193468940a6` |
| `22d2c71` | 2026-05-02T12:33:23-04:00 | `docs/EVALUATION_PROMPT.md` | `# Version: v6 (stable best after v5→v8 iteration)` | `74ec94ae166b649bb3d8639288f49b6b7076dcb26f1cde727da1a6f98e19ba15` |
| `3d9a9d6` | 2026-05-30T10:17:08-04:00 | `docs/EVALUATION_PROMPT.md` | `# Version: v6 (stable best after v5→v8 iteration)` (unchanged) | `1734ea8c9795f53ab5b3ba3a68c520bdb52dbb3f0a3607d20ca02c6f3255dfc1` (**content changed, header did not**) |
| `7063465` | 2026-06-27T16:26:16-04:00 | `docs/EVALUATION_PROMPT.md` | `# Version: v6 (stable best after v5→v8 iteration)` (unchanged) | `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b` (**content changed, header did not**) |
| `87bcfaa` | 2026-08-01T16:00:12-04:00 | `docs/EVALUATION_PROMPT.md` | `# Version: v10+auto1 (auto-iterate candidate — pending gate)` | `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14` (**== deployed content, == current working tree**) |

**The header changed exactly twice in this file's entire history**
(no-header→`v6` at `22d2c71`; `v6`→`v10+auto1` at `87bcfaa`), **but content
changed at every single commit that touched the file.** Two commits
(`3d9a9d6`, `7063465`) are exactly the pattern the prompt warned about --
content edited while the header still said `v6`. Read both diffs directly
(not inferred from commit messages):

- `22d2c71`→`3d9a9d6`: Type B cap changed from `"Variable cap 40-60% tracking
  driver count."` to `"Fixed cap 50%; profit-take rule at 25% gain binds
  first."`, plus `typeClassificationRationale` field added to the structured
  block. **This matches `DESIGN_PRINCIPLES.md` §5's documented "Design-intent
  variable cap retired (2026-05-17)"** -- a real, already-adopted,
  already-documented decision, not undisclosed drift. Whether it went through
  a §2.2a gate run as a *prompt* change specifically (as opposed to being
  validated only as an allocator-layer change) is answered in Step 6.
- `3d9a9d6`→`7063465`: added the `summary` field + its field definition.
  Matches the commit's own message ("feat: add summary field to Analysis") and
  the `add_summary_field` schema migration -- a documented, intentional
  addition, not disguised drift.

**Neither of these two mid-timeline changes is the kind of silent drift `87bcfaa`
represents** -- both correspond to already-documented product decisions found
independently in `DESIGN_PRINCIPLES.md` and the DB schema history. They are,
however, real evidence that this file's header has never reliably signaled
"content changed here" even before the v10+auto1 episode -- camouflage was
already possible, just not exploited maliciously in these two instances.

**Commit at which the file last declared `v6`, and its content sha256** (the
figure Step 4 says the report needs and no prior step produced):
**`70634653bc0378c515203ec900aa98937f9807b2`, sha256
`357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`.**
(This matches the recon's independently-derived cutoff commit and timestamp
exactly -- `7063465`, `2026-06-27 16:26:16-04` -- corroborating that recon's
methodology from a different angle: content-hash timeline vs. header-search.)

**`server/lib/versions.js` — every commit that ever touched it:**

| Commit | Date | `PROMPT_VERSION` | `MODEL_VERSION` | sha256 | Commit message (quoted) |
|---|---|---|---|---|---|
| `1d79015` | 2026-05-23T20:58:12-04:00 | `'v6'` | `'claude-sonnet-4-20250514'` | `6598cca3ae128718e43be824615aac63da136c4dd44f1e30d1ffabdecb6b12e8` | "Portfolio Analyst Phase 1: Position/Lot/CashBalance schema + entry UI; two-hurdle gate logic; model-pin gate result (HOLD)" |
| `9028d0e` | 2026-06-27T16:44:31-04:00 | `'v6'` (unchanged) | `'claude-sonnet-4-6'` | `c1ef9016a839f4da464890210b69eebbbadd43f9ef749fa915a5b16bd3f5bdbb` | "fix: update model to sonnet-4-6 (dated snapshot retired); feat: analysis summary field" |

Only two commits ever touched this file. Current working-tree sha256
(`c1ef9016...`) == `9028d0e`'s content -- **`versions.js` has not been touched
since 2026-06-27**, confirming `PROMPT_VERSION = 'v6'` is now 68 days stale
against the file it claims to describe (`87bcfaa`, 2026-08-01, is 35 days
*after* the last `versions.js` edit).

- **Last commit that changed `PROMPT_VERSION`:** `1d79015`
  (2026-05-23T20:58:12-04:00) -- the commit that *created* the constant,
  set to `'v6'`. It has never been edited since.
- **Last commit that changed `MODEL_VERSION`:** `9028d0e`
  (2026-06-27T16:44:31-04:00), quoted message above.

**Origin point, stated plainly: `87bcfaa` (2026-08-01T16:00:12-04:00) is the
single commit where `docs/EVALUATION_PROMPT.md`'s content hash changed to
v10+auto1 and `server/lib/versions.js` did not change at all** (its last edit
was 5 weeks earlier, `9028d0e`). This is the missed-label origin point --
one commit, one author action, no accompanying `versions.js` edit.

**A second, independent timing observation:** `9028d0e` (the `MODEL_VERSION`
bump to `sonnet-4-6`) landed 18 minutes after `7063465` (the last v6-header
prompt commit), same day, same apparent session. `PROMOTION_GATE.md` §8
already documents an *earlier*, separate "accidental `claude-sonnet-4-20250514`
→ `claude-sonnet-4-6` bump caught 2026-05-23" that motivated writing the
version-discipline rules and running the 2026-05-23 gate (HOLD verdict,
champion retained). `9028d0e`, over a month later on 2026-06-27, **reintroduces
the exact same substitution the gate rejected**, this time via a commit
message asserting the dated snapshot was "retired by Anthropic" -- a claim
this investigation did not and cannot independently verify (would require
querying Anthropic's model-availability API/docs, out of scope for a read-only
DB/git investigation). See Step 6 for whether this reintroduction was ever
recorded anywhere as a deliberate process exception.

## Step 5: live contamination scope

Step 1 found a drifted build deployed (DEV, commit `37f535a`, deployed
`2026-08-25T14:36:46-04:00`), so this step is in scope (not skipped).

Anchored to the deploy timestamp, not the commit date, per the prompt's own
instruction:

```sql
SELECT id, "transcriptId", "createdAt", "promptVersion", "modelVersion"
FROM "Analysis" WHERE "createdAt" >= '2026-08-25 14:36:46-04' ORDER BY "createdAt";
```
```
 id  | transcriptId |        createdAt        | promptVersion |   modelVersion    
-----+--------------+-------------------------+---------------+-------------------
 895 |          786 | 2026-08-31 14:41:11.369 | v6            | claude-sonnet-4-6
```

**Exactly one row: id 895 (NVDA, call date 2026-08-26, "NVIDIA (NVDA) Q2 2027
Earnings Call Transcript"), created 2026-08-31T14:41:11.369, six days after
the contaminated build went live.** Stored label: `promptVersion: "v6"`,
`modelVersion: "claude-sonnet-4-6"`.

**Known false vs. merely unverified, stated plainly:**
- `promptVersion: "v6"` on row 895 is **known false** -- the deployed build
  serving it was confirmed in Step 1 to hold v10+auto1 content
  (sha256 `b81d24c6...`), not v6.
- `modelVersion: "claude-sonnet-4-6"` is **accurate as a description of what
  model ran** (matches `versions.js`'s `MODEL_VERSION` at the deployed
  commit) -- but see Step 6: that model is the one the 2026-05-23 gate
  returned a HOLD verdict on, so "accurate label" does not mean "validated
  choice."
- Row 895's `recommendation` ("Add") and `thesisHealth` ("Strengthening") are
  real LLM output from the live v10+auto1 prompt -- not evaluated here for
  correctness (would require re-running the analyst under both prompt
  versions, which is an LLM call and out of scope for this investigation's
  standing rules).

**Deploy timestamp was establishable directly from Railway** (`railway
status --json`, not the dashboard), so no bounded-estimate fallback was
needed -- this count (1 row) is exact, not an estimate.

This is a small, precisely-bounded blast radius: **one stored `Analysis` row**
is currently mislabeled in a way that is now provably false, out of 806 total
rows and 1 row created since the contaminated deploy.

## Step 6: gate records

**`data/gate_ledger.json` entry 1, `champion` field quoted exactly:**
`"champion": "v6_sonnet-4-20250514"`. Full entry (`analysis/data/gate_ledger.json`,
the only entry in the file):
```json
{
  "date": "2026-05-23T19:55:18",
  "label": "model_pin: sonnet-4-20250514 vs sonnet-4-6",
  "change_class": "analyst",
  "change_class_detail": "model_version",
  "hurdle": "equivalence",
  "primary_metric": "analyst_direct_lift_pp",
  "champion": "v6_sonnet-4-20250514",
  "challenger": "v6_sonnet-4-6",
  "training": {
    "n_champion": 81, "n_challenger": 80,
    "champion_lift_pp": 4.94, "challenger_lift_pp": -2.5,
    "delta_pp": -7.44, "noise_std_pp": 4.2,
    "pct_tickers_improved": 28.6, "robustness_ok": false, "verdict": "HOLD"
  },
  "final_verdict": "HOLD",
  "final_reason": "challenger clearly regresses (Δ=-7.4pp < −4.2pp noise floor) — keep incumbent"
}
```

**Has any entry ever tested v7, v8, v9, v10, v10+auto1, or any §2.2a
prompt/eval-logic change? No.** This is the ledger's only entry, and it is a
§2.2b model-version change, not a §2.2a prompt change. No prompt version has
ever been gate-tested via the formal ledger mechanism.

**Is there any record anywhere of the 2026-06-27 model change as a deliberate
process exception? No record found.** Searched `docs/handoffs/`, `wrap-ups/`,
`docs/architecture/`, and `git log --all -i --grep` for
"process exception", "sonnet-4-6...exception", "forced migration", "dated
snapshot retired" -- zero hits beyond the commit message and `versions.js`'s
own code comment. **This is itself the Step 8 §8 finding the prompt
anticipated: an unrecorded migration to a HOLD-verdict model.** Full timeline
now established (Step 4 + this step):
1. `a31f3c0` (2026-05-23T13:31:42-04:00, "Bump evaluator model to
   claude-sonnet-4-6") -- the original accidental bump, hardcoded directly
   into `evaluate.js` (`server/routes/evaluate.js:50`,
   `model: 'claude-sonnet-4-20250514'` → `model: 'claude-sonnet-4-6'`), before
   `versions.js` existed.
2. Same day, `1d79015` (2026-05-23T20:58:12-04:00) creates `versions.js` and
   reverts to `MODEL_VERSION = 'claude-sonnet-4-20250514'`, introducing the
   version-pin discipline. `PROMOTION_GATE.md` §8's "accidental...bump caught
   2026-05-23" refers to this same-day catch-and-revert.
3. Gate run same evening (`data/gate_ledger.json` entry 1, `date:
   "2026-05-23T19:55:18"`) tests exactly this substitution, verdict **HOLD**,
   champion (`claude-sonnet-4-20250514`) retained, explicit note to "Re-run
   when sonnet-4-7 or later snapshot is available" (`PROMOTION_GATE.md` §10).
4. **Five weeks later**, `9028d0e` (2026-06-27T16:44:31-04:00, "fix: update
   model to sonnet-4-6 (dated snapshot retired); feat: analysis summary
   field") **reintroduces the identical substitution the gate rejected**,
   this time via a code comment asserting Anthropic retired the dated
   snapshot -- with no new gate run, no ledger entry, no wrap-up, no design
   doc note beyond the comment itself. Whether `claude-sonnet-4-20250514` was
   in fact retired by Anthropic by 2026-06-27 is **not independently
   verified** by this investigation (would require querying Anthropic's
   model catalog, out of scope for a read-only DB/git run) -- reporting the
   claim as unverified, not confirming or refuting it.
5. This model has been live ever since (confirmed still `claude-sonnet-4-6`
   in the current working tree and at DEV's deployed commit, Step 1).

**`docs/EVALUATION_PROMPT.md`'s own iteration log on v7-v10, quoted exactly**
(the file's header comment block, lines 4-119):

> `v6: added explicit Execution-stumble handling + clarified no-stumble cases.
> Backtest: ENPH 6/9 + TTD 3/6 = 9/15 (60%). Current best (live in production
> as of 2026-07-05).`

**This self-description is itself now known stale/false** -- v6 is not what
is live in production; v10+auto1 is (Step 1). The file makes this exact claim
about itself and it is wrong as of this investigation.

> `v7: added Red Flag Protocol...Net: 8/15 (53%).`
> `v8: tightened v7...Same net result (8/15)...`
> `Conclusion (v7/v8): the credibility-to-action gap can't be closed with a
> prompt-side rule without regressing clean calls.`

v7 and v8 were tried and abandoned (regressed vs. v6), narratively -- no
formal gate entry exists for either (consistent with "no entry ever tested
v7/v8" above; these look like informal/pre-gate-mechanism iteration, both
predating the ledger's first entry).

> `v9 (2026-07-05, candidate): ... Gate status: must clear BOTH (a) Step 0
> rerun showing reduced instability, AND (b) full backtest regression
> matching or beating v6's 60% (9/15) baseline before promotion to
> production. ... RESULT (Gate A, 2026-07-05): FAILED. Stability got WORSE,
> not better — 26/84 unstable (69.0%) vs v6's 18/84 (21.4%).`

**v9 explicitly failed its own stated gate**, by the file's own record.

> `v10 (2026-07-05, candidate): ... Gate status: not yet run. Must clear the
> same two gates as v9 ... before promotion.`

**v10's own header says its gate has not been run.**

> `v10+auto1 (2026-07-06, auto_iterate_prompt.py): [describes a specific
> Run-B mislabeling defect in the decision matrix]`

**v10+auto1 carries no gate-status statement at all** -- not "not yet run,"
not "in progress," nothing. It is the most recent entry and the least
gate-documented one, and it is what is currently deployed to DEV.

**Stated plainly, combining Steps 1, 4 and 6:** the file currently live in
production (DEV) is a candidate that, by its own internal iteration log, sits
downstream of a version (v9) that **failed** its gate, a version (v10) whose
gate **was never run**, and is itself (v10+auto1) an even-later patch with
**no gate status recorded at all**. This is not merely a labeling
mismatch -- it is an ungated candidate, several iterations past the last
version that ever passed anything, running in the environment `CLAUDE.md`
describes as hosting the application.
