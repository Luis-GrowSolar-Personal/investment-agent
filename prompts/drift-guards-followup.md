# Drift guards — follow-up fixes

Small corrective run on top of `wrap-ups/version-registry-and-drift-guards-out.md`.
**$0 API spend. No LLM calls. No DB writes.** Branch
`sweep/db-corpus-baseline`; do not commit to `dev` or `main`.

`run_id` **`drift-guards-followup`**. Checkpoint per step.

## Standing context that scopes this run

**Production drift is a known, accepted condition and is NOT to be
corrected here.** The deployed app (`dev`) deliberately does not carry the
registry or the guards, and `server/routes/moves.js` deliberately differs
from the validated `allocator_v3` design. That divergence is the premise of
the Test 1-6 program, not a defect it found — see
`docs/architecture/ALLOCATOR_PORTING_METHODOLOGY.md`. **Do not merge
anything to `dev`. Do not propose it. Do not "fix" the divergence.**

The guards exist to protect the **backtest and test machinery** from
drifting away from proven benchmarks. That is the whole scope.

---

## Step 1 — `server/lib/versions.js`: fail safe, not fail dead

The rewrite reads the registry unguarded at module load:

```js
const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
const PROMPT_VERSION = registry.artifacts.evaluation_prompt.promoted_version;
```

A missing file, malformed JSON, a changed relative path in a deployed
layout, or a renamed registry key throws at `require()` time — so
`require('./versions')` failing means **the server does not start**, on a
file-read problem rather than a version mismatch.

That is the exact boot-refusal failure mode the previous run deliberately
rejected for the guard (its §2 deviation), reintroduced accidentally through
this file. Not urgent today because nothing merges to `dev` — but it is a
landmine, so defuse it now.

Wrap the read and the key lookups. On any failure: log loudly and
unmistakably, and export a clearly-marked unknown sentinel (e.g.
`'UNKNOWN-REGISTRY-UNREADABLE'`) rather than throwing. The **scoring
route's** hash check remains the enforcement point and already fails closed
— that is where refusal belongs, not at import.

**Do not apply the same softening to `analysis/version_guard.py`.** Its
line-41 registry read is also unguarded, but a harness crashing before it
can score is *correct* — fail-closed is the entire point there. Improve only
the error message if it is unclear; do not make it fall through.

## Step 2 — close the `auto_iterate_prompt.py` seed-path gap

The previous run guarded this driver at `main()` against
`PROMPT_PATH.read_text()`, but flagged that when `--seed-run-dir` /
`--seed-prompt-file` is used, the text actually scored comes from a
different path (`seed_dir/prompt_candidate.md`) and is never hash-checked.

**This is the tool that produced v10+auto1.** Close it: hash whatever text
is actually about to be scored, whatever path it came from, and require
either a promoted-hash match or an explicit registered `PROMPT_CANDIDATE`
declaration — the same contract every other driver now has. Log the
resolved source path and its hash on every run so a future incident is
traceable to a file, not inferred.

Touching this file's seeding logic is **in scope for this run** (the earlier
"no logic changes" boundary was about allocator and trend-analyst code).

## Step 3 — record the accepted divergence as a decision, not a finding

The registry currently encodes production divergence inside the
`allocator_live` artifact's `status` string. Promote it to a proper
`decisions` record so it reads as settled rather than outstanding:

- **Decision:** the deployed app is not brought into line with the validated
  machinery, and the registry/guards are not deployed to `dev`.
- **Reason:** the divergence is the premise of the validation program; the
  app will be brought to the settled design later via the porting
  methodology, once the design is settled.
- **Reopening condition:** the Test 1-6 program concludes and the conformance
  fixtures exist.

Have `whats_live.py` report this explicitly — something a future session
reads as *"known and accepted, do not act"*, not as an unresolved gap. The
goal is that nobody re-raises it, and nobody "helpfully" merges the guards
to `dev`.

Confirm while there that `whats_live.py` does **not** emit mismatch alerts
for `allocator_live` or any other informational, unhashed artifact — alert
fatigue would kill the tool. Report what it currently does.

## Step 4 — doc corrections

In `docs/architecture/ALLOCATOR_PORTING_METHODOLOGY.md`:

1. **`allocator_v3`, not `v4`.** The doc refers loosely to
   `analysis/simulator/allocator_v2/v3/v4`. The settled figures come from
   **`allocator_v3`** (`run_db_corpus_baseline.py` imports it; `v4` is used
   only by `run_expanded_test.py` and is an untested consensus-modifier
   sizing change). Correct every reference, and note `v4`'s status so it is
   not mistaken for the newer-and-therefore-better one.
2. **Add the Type A/B finding to the lever inventory.** The live app never
   reads `type_classifications.json` and has **no 15/35/50 Type A/B cap rule
   anywhere in `server/`** — caps come from hand-set `Ticker.capPercent` /
   `OwnerTickerConfig.capPercent`. So production does not implement the cap
   structure differently; **it does not implement the concept.** This joins
   `ratchetTranche`, `specExitSpeed`, `TRIM_SIGNAL`, `TRIM_MODEL`,
   `maxPositions`, full-reset mode and rank scores in the
   still-to-be-dispositioned list.

Also correct `prompts/version-registry-and-drift-guards.md`'s reference to
09-07 §5 as "six figures" — that section's own header says **eight**, with 8
rows. The prompt was wrong; the previous run caught it correctly.

## Step 5 — verify

Demonstrate, with output:

1. `versions.js` with the registry temporarily moved aside → **server module
   loads**, logs loudly, exports the sentinel. Restore afterward.
2. `auto_iterate_prompt.py` pointed at a seed file whose hash matches nothing
   registered → refuses **before any API call**, naming the resolved path and
   hash.
3. Same, with a registered `PROMPT_CANDIDATE` → proceeds, logging path and
   hash.
4. `whats_live.py` on the clean tree → exit 0, accepted-divergence decision
   shown as known/accepted, no mismatch alerts for informational artifacts.

Revert all deliberate breakage; confirm `git status --short` shows no
residual diff on files this run touched.

## Report

> **versions.js: fails safe [demonstrated]. version_guard.py: left
> fail-closed [confirmed]. auto_iterate seed-path gap: [closed / why not].
> Accepted-divergence decision recorded; whats_live.py reports it as
> [text]. Informational artifacts generate [N] mismatch alerts (target 0).
> Doc corrections: allocator_v3 [N refs fixed], Type A/B finding added,
> "six"→"eight" corrected. All 4 demos [pass]. $0 API spend.**

Flag plainly: anything in the previous run's output that this run found to
be inaccurate, and any place `allocator_v4` turns out to be load-bearing
after all.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers.
- No LLM calls, no DB writes, **no merge to `dev`**, no allocator or
  trend-analyst logic changes.
- Driver/helper changes committed before any manifest.
- Do not write new handoff docs. This prompt in, one wrap-up out.
