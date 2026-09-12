# Wrap-up: version-registry-and-drift-guards

**Run:** `version-registry-and-drift-guards` | **Branch:** `sweep/db-corpus-baseline`
**Type:** Build only. **$0 API spend. No LLM calls made.** No DB writes.
**Wall-clock:** ~55 minutes.

---

> **Branch fix: `c514ae1` cherry-picked (new commit `21d0c03`) — prompt on this
> branch is now `v6` @ sha256 `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`.
> Pre-drift v6 blob `7063465` sha256 `357b6b0b...` vs restored `c514ae1` sha256
> `357b6b0b...` — **IDENTICAL**. Registry: **9** artifacts, **6** benchmarks
> (**2** marked stale), **7** decisions (**2** open, 1 gap, 1 pending
> enumeration). Guards: server **refuses on mismatch, candidate override
> works**; harness **hard-fails before call one, proven on the driver chain
> covering all 7 named scripts** (5 direct, 1 via shared reuse, 1 as the
> tool that itself generates candidates). `whats_live.py`: **all 7 hashable
> artifacts MATCH on the clean tree; Test 4 and Test 6 floors correctly
> reported STALE; fundamentals_cache correctly reported as a 124-day
> breach.** Doc hygiene: EVALUATION_PROMPT.md deployment claim **already
> absent post-rollback** (nothing to remove), `versions.js` **now re-exports
> the registry**, CLAUDE.md **Version truth section added**. Comparison
> protocol landed in **PROMOTION_GATE.md §11**. **All six Step 6
> demonstrations pass.** $0 API spend confirmed.**

---

## Resume status

No prior run state existed for this `run_id`; this was a fresh, complete run
of all 7 steps. Not a resume, not partial.

## 0. Hygiene

Working tree at start had one modified tracked file
(`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`), belonging
to a different, concurrently-running `run_id`. Not touched, per Step 0's
explicit instruction. All other entries were untracked inputs (the prompt
itself, several `docs/handoffs/*.md` this prompt names as reading material,
`docs/architecture/ALLOCATOR_PORTING_METHODOLOGY.md`, and unrelated scratch
files/dirs from other sessions) — none staged or committed on the user's
behalf.

### 0a/0b — branch fix and hash verification

- `c514ae1` ("fix: roll EVALUATION_PROMPT.md back to v6, the gated version")
  existed on `dev` but not on `sweep/db-corpus-baseline`. Before this run,
  the working tree here held **v10+auto1**, sha256
  `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14` — the
  exact known-bad content from the 2026-09-03 drift incident.
- Cherry-picked cleanly (no conflicts) as commit `21d0c03`.
- Verified: `git show 7063465:docs/EVALUATION_PROMPT.md`,
  `git show c514ae1:docs/EVALUATION_PROMPT.md`, and the post-cherry-pick
  working-tree file all hash to
  `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`.
  **IDENTICAL** — no stop condition.

## 1. Registry — `docs/architecture/VERSION_REGISTRY.json`

Built with 9 `artifacts`, 6 `benchmarks`, 7 `decisions`, and the
`comparison_protocol` reference. Every hash was computed this run from
on-disk content (`shasum -a 256` / Node `crypto` / Python `hashlib`), never
transcribed.

**Premises checked and corrected, per Step 4's instruction:**

| Claim in the prompt | Verified | Disposition |
|---|---|---|
| 09-07 §5 has "six figures" corrected | The section header literally says **"eight figures and claims corrected,"** and there are 8 rows | Registry and this report use "eight." Not a stop condition — flagged. |
| ALL16 "copy-pasted verbatim across ~15 files" | **17 files** define `ALL16 =` | All 17 agree (verified individually — 9 spell the 16 tickers out literally, 8 derive `ESTABLISHED + SPECULATIVE`, and the underlying `ESTABLISHED`/`SPECULATIVE` lists are byte-identical across every derived-form file). No disagreement found. `~15` was close but not exact. |
| `allocator_simulator` = `analysis/simulator/allocator_v*.py` (treated as one artifact) | There are **4 distinct files** (`allocator.py`, `_v2`, `_v3`, `_v4`), and they are not sequential drop-in replacements. `run_db_corpus_baseline.py` — the driver behind the settled $179,944.91/$184,819 figures — imports `allocator_v3`, **not** `allocator_v4`. `allocator_v4` (a consensus-modifier sizing change) is imported only by `run_expanded_test.py`. | Registered `promoted_version: allocator_v3` (what's actually load-bearing), with `allocator_v4` flagged as an untested candidate. All 4 hashes recorded. |
| `fundamentals_cache.json` "118 days stale" | As of **this run's date (2026-09-12)**, the cache is **124 days** stale (latest `fetchedAt` = 2026-05-11T02:36:57Z). | Not a real disagreement — the prompt's 118-day figure was almost certainly computed from the 2026-09-07 state-of-play's own vantage point (~119 days from the same cache date). `whats_live.py` computes this dynamically from `datetime.now()` rather than hardcoding a day count, so it will always report the correct age going forward. |

**New finding, outside the prompt's stated scope, surfaced by Step 1's own
instruction to "resolve how the live app sources Type A/B":** the live app
(`server/routes/moves.js`, `dashboard.js`, `radar.js`) **does not read
`analysis/data/type_classifications.json` at all**, and has **no fixed
35%/50% Type A/B cap rule anywhere in `server/`**. Caps come from
`Ticker.capPercent` / `OwnerTickerConfig.capPercent` — a hand-set percentage
per ticker with no automated Type A/B classification behind it. This is a
**second, previously undocumented divergence** between the validated design
and the deployed app, distinct from (and in addition to) the
`moves.js`-vs-`allocator_v3` divergence `ALLOCATOR_PORTING_METHODOLOGY.md`
already tracks. Registered in the `type_classifications` artifact entry.
**Not fixed** — out of this run's scope (no allocator logic changes
permitted).

**Comparison protocol (Step 1d):** ported verbatim in substance from
`ALLOCATOR_PORTING_METHODOLOGY.md`'s final section into **`PROMOTION_GATE.md`
new §11** (8 sub-rules, 11.1–11.8), referenced (not duplicated) from the
registry's `comparison_protocol` record. Changelog entry added.

## 2. Server guard

`server/routes/evaluate.js` now calls `checkPromptHash('evaluation_prompt',
systemPrompt)` once at startup (logs loudly on mismatch, does **not** refuse
to boot — see deviation below) and again on every POST, refusing with HTTP
409 and both hashes on mismatch. `PROMPT_CANDIDATE=<registered version>` is
the escape hatch; when used, the row is stamped with the candidate's
version (`effectivePromptVersion`), never the promoted one.

`server/lib/portfolioImport.js`'s inline prompt was refactored out of an
interpolated template literal into a named constant
(`POSITIONS_CSV_PROMPT_TEMPLATE`, with a `{{CSV_TEXT}}` placeholder so its
hash is independent of whatever CSV a user uploads) and is now asserted via
`assertPromptHash` before every call — **hard-refuses the import path on
mismatch, with no candidate escape hatch**, per the prompt's instruction.

**Deliberate deviation from §8's wording, flagged as instructed:** the
startup check logs loudly rather than refusing to boot. 2026-09-03's own
§7 and the 2026-09-05 state-of-play both proposed boot-refusal; this run
deviates because Luis tests against the deployed Railway app, and taking
the whole app down over a prompt hash is a worse failure mode than a
disabled scoring route. The scoring route itself (`POST /`) is the actual
enforcement point.

## 3. Harness guard

`analysis/version_guard.py` is the Python counterpart to
`server/lib/versionGuard.js`, reading the same `VERSION_REGISTRY.json`.
Wired into all 7 named drivers, verified individually:

| Driver | Wired at | Verified before first `messages.create`? |
|---|---|---|
| `backtest_runner.py` | `load_evaluation_prompt()` | Yes |
| `backtest_from_files.py` | `load_evaluation_prompt()` | Yes |
| `eval_cache_warmer.py` | `load_prompt()` | Yes |
| `test4_noise_floor.py` | `get_prompt_header()` | Yes |
| `test6_look_ahead.py` | `get_prompt_header_and_text()` | Yes |
| `test7_score_fidelity.py` | reuses `test4_noise_floor.get_prompt_header()` (already guarded) at its own line 135, before its line-220 call | Yes, transitively |
| `auto_iterate_prompt.py` | top of `main()`, before iteration 1 | Yes, with a documented limitation — see below |

**Deviation, flagged:** `auto_iterate_prompt.py`'s job is to mutate
`EVALUATION_PROMPT.md` into new, ungated candidates — the exact tool that
produced v10+auto1. It cannot require the on-disk file to match the
promoted hash without defeating its own purpose, so its guard call accepts
an explicit `PROMPT_CANDIDATE` the same way the others do, rather than
requiring an exact promoted-hash match. **Known limitation, not fixed this
run:** the guard checks `PROMPT_PATH.read_text()` (the file on disk at
startup), but when `--seed-run-dir`/`--seed-prompt-file` is used, the text
actually scored may come from a different path
(`seed_dir/prompt_candidate.md`). The startup check still catches the "silent
unrecognized baseline" failure mode that caused the original incident, but
does not re-check the seed file itself. Left as a documented gap for a
future session, since fixing it means touching `auto_iterate_prompt.py`'s
seeding logic beyond a guard call — out of this build's stated scope of "no
allocator or trend-analyst logic changes," and this isn't allocator logic,
but erred toward the smaller, provably-correct change.

## 4. `analysis/whats_live.py`

Built and run. All six required sections present (registered artifacts,
branch/dev-divergence, settled configuration, stale benchmarks, cache-age
breach, open decisions). Exits non-zero on any promoted-artifact mismatch.
Full output captured in Step 6 below (demos 5 and 6).

## 5. Doc hygiene

1. **`EVALUATION_PROMPT.md` deployment claim:** already absent. The
   "(live in production as of 2026-07-05)" text the drift investigation
   quoted was only ever present in the *later* v10+auto1 content (added
   after `7063465`); the restored v6 blob predates it. Verified by grep —
   nothing to remove.
2. **`versions.js`:** rewritten from a hand-maintained constant into a thin
   re-export of `VERSION_REGISTRY.json`'s `promoted_version` fields.
   Exported names (`PROMPT_VERSION`, `MODEL_VERSION`) unchanged. Registry's
   `model` artifact hash updated to reflect the new file content
   (`eb7d24c3...`); the pre-rewrite hash (`c1ef9016...`) is recorded as
   superseded in the registry's own note.
3. **CLAUDE.md:** new "Version truth" section added, directly after
   "Important Notes." States the registry/`whats_live.py` as the only
   source of truth, names the exact incident that motivates it, and states
   the standing rule that any scoring run asserts the prompt hash before
   call one.

**Not done:** Step 3 also asked to add the standing rule "to the prompt
template." No canonical prompt-template file exists anywhere in this repo
(only worked examples in `prompts/`, per `CLAUDE.md`'s own instruction to
read the two most recent ones) — flagged rather than guessed at a target.

## 6. Guard demonstrations — all six pass

Run live this session (transcripts below, no LLM calls in any of them):

1. **Server guard, deliberately wrong hash** → `checkPromptHash` returns
   `ok:false`, both hashes named (`promotedHash`/`actualHash`), reason
   string identifies the missing candidate declaration. **Pass.**
2. **`PROMPT_CANDIDATE=v10+auto1` (registered)** → `ok:true`,
   `candidateUsed:'v10+auto1'`. Tested twice: once with arbitrary content
   (returns `unverifiedCandidateHash:true` as an extra signal) and once
   with the actual historical v10+auto1 blob pulled from git (`git show
   87bcfaa:...`), which hashes to exactly the registered candidate sha256
   `b81d24c6...` with no warning flag. **Pass.**
3. **`PROMPT_CANDIDATE=totally-made-up-v999` (unregistered)** → `ok:false`,
   reason names the unregistered candidate string. **Pass.**
4. **Harness on a corrupted prompt file** → appended a line to
   `docs/EVALUATION_PROMPT.md`, ran `test4_noise_floor.get_prompt_header()`
   directly: raised `SystemExit` with both hashes, current branch, and
   dev-divergence status, **before any `anthropic.Anthropic().messages.create`
   call was reached** (confirmed by reading the traceback path — the
   exception fires inside `get_prompt_header()`, which is called before
   `step_score()`'s API call). **Pass.**
5. **`whats_live.py` on the still-corrupted tree** → `evaluation_prompt`
   reported `MISMATCH` with both hashes, exit code **1**. Also correctly
   surfaced (as a genuine, non-deliberate finding) that `server/lib/versions.js`
   diverges from `dev` — true, because this run's rewrite of that file
   hasn't been merged to `dev` yet. **Pass.**
6. **`whats_live.py` on the restored clean tree** → all 7 hashable
   artifacts `MATCH`, exit code **0**, Test 4 and Test 6 floors both
   correctly reported `STALE` with their reasons, `fundamentals_cache`
   correctly reported as a 124-day breach. **Pass.**

Breakage reverted (`git checkout -- docs/EVALUATION_PROMPT.md`) and
confirmed via `git status --short` — no residual diff on any file this run
touched; only pre-existing untracked files from other sessions remain.

## Deviations and scope calls, summarized

- Server startup logs loudly instead of refusing to boot (§2, flagged
  above with reasoning).
- `auto_iterate_prompt.py`'s guard checks the on-disk seed file at process
  start, not the actual seed-run text when `--seed-run-dir` is used
  (documented gap, §3).
- `promoted_version: allocator_v3` for the `allocator_simulator` artifact
  reflects what's actually load-bearing today, not a formal promotion
  event — there is no `gate_ledger.json` entry for any of the four
  allocator files. Recorded as such in the registry rather than implying a
  gate that never ran.
- No file exists to receive Step 3's "add to the prompt template"
  instruction; addressed via CLAUDE.md only.

## What was deliberately NOT done

Per the prompt's own scope boundary: no test was re-run, no benchmark
figure was recomputed, no allocator-parity work was attempted, no allocator
or trend-analyst logic was changed, and `analysis/test4_noise_floor/` /
`analysis/test6_look_ahead/` output directories were not touched. The
`type_classifications`-vs-live-app divergence found in Step 1 is recorded
in the registry but not fixed — that is allocator/app logic, explicitly out
of bounds here, and belongs to a design session.

## Follow-up commands

```zsh
# One-command version/drift/staleness status
python3 analysis/whats_live.py

# Score deliberately against a registered candidate (never the default path)
PROMPT_CANDIDATE=v10+auto1 python3 analysis/backtest_runner.py --help

# Re-verify the branch-fix hash chain independently
git show 7063465:docs/EVALUATION_PROMPT.md | shasum -a 256
git show c514ae1:docs/EVALUATION_PROMPT.md  | shasum -a 256
shasum -a 256 docs/EVALUATION_PROMPT.md
```

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018C47fL8C33NfRQYbdCsQhT
