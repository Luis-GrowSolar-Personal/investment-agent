# Wrap-up: drift-guards-followup

**Run:** `drift-guards-followup` | **Branch:** `sweep/db-corpus-baseline`
**Type:** Corrective build on `wrap-ups/version-registry-and-drift-guards-out.md`.
**$0 API spend. No LLM calls. No DB writes. No merge to `dev`.**
**Wall-clock:** ~25 minutes.

---

> **versions.js: fails safe [demonstrated]. version_guard.py: left
> fail-closed [confirmed]. auto_iterate seed-path gap: [closed]. Accepted-
> divergence decision recorded; whats_live.py reports it in a dedicated
> "[6] Accepted / settled divergences" section, distinctly from "[7] Open
> decisions." Informational artifacts generate 0 mismatch alerts (target 0,
> confirmed across all 3: trend_analyst, allocator_live, ticker_universe).
> Doc corrections: allocator_v3 [2 refs fixed in ALLOCATOR_PORTING_METHODOLOGY.md],
> Type A/B finding added to the still-to-be-dispositioned list, "six"→"eight"
> corrected in prompts/version-registry-and-drift-guards.md. All 4 demos
> pass. $0 API spend.**

---

## Resume status

No prior run state for this `run_id`; fresh, complete run of all 5 steps.
Not a resume, not partial.

## 0. Hygiene

Same pre-existing condition as the prior run: one modified tracked file
(`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`) belonging
to a different, concurrently-running session — not touched. All other
entries untracked inputs/scratch, none staged on the user's behalf beyond
what this prompt specifically asked to correct.

## Step 1 — `versions.js` fail-safe

Confirmed the premise: the registry read at module scope
(`JSON.parse(fs.readFileSync(REGISTRY_PATH, ...))`) threw uncaught on any
read/parse failure, meaning `require('./versions')` failing took the whole
server down on a file-read problem rather than a version mismatch — the
exact boot-refusal failure mode the original build's §2 deviation
deliberately rejected for the *hash-mismatch* case, reintroduced by this
*file-read* case.

Fixed: wrapped the read and both key lookups in try/catch. On any failure,
logs loudly (`[versions.js] FAILED TO LOAD VERSION_REGISTRY.json...`) and
exports `PROMPT_VERSION = MODEL_VERSION = 'UNKNOWN-REGISTRY-UNREADABLE'`
instead of throwing.

**Found beyond the prompt's stated scope, while fixing this:**
`server/routes/evaluate.js`'s own startup check
(`const startupCheck = checkPromptHash('evaluation_prompt', systemPrompt)`,
added in the previous run) calls into `versionGuard.js`, which reads the
*same* `VERSION_REGISTRY.json` file via an unguarded `loadRegistry()`. An
unreadable registry would throw there too, at `require()` time — the
identical landmine, one file over, that the prompt didn't name because it
predates this follow-up prompt being written. Fixed identically (try/catch,
fail-safe log, `startupCheck = {ok:false, ...UNREADABLE...}` on failure) and
additionally wrapped the **per-request** `checkPromptHash()` call in the
`POST /` handler, which would otherwise throw *inside* an async Express
handler with no catch — not a boot crash, but an unhandled-rejection crash
on the first request after the registry broke. Both now return clean error
responses (409 for a hash mismatch, 503 for an unreadable registry) instead
of throwing.

**`analysis/version_guard.py` deliberately left untouched**, per the
prompt's explicit instruction — a harness crashing before it can spend
money scoring is the correct behavior there, not a landmine.

## Step 2 — `auto_iterate_prompt.py` seed-path gap, closed

Confirmed the premise exactly as stated: the previous run's guard call
(`assert_prompt_hash(PROMPT_PATH.read_text(), ...)`) ran once at the top of
`main()`, **before** the `if args.seed_run_dir:` branch resolves
`best_prompt_text` from `seed_prompt_path` (defaulting to
`seed_dir/iter{N}/prompt_candidate.md`, or an explicit
`--seed-prompt-file`). So a seeded run's actual scored text was never
hash-checked — only whatever happened to be sitting in
`docs/EVALUATION_PROMPT.md` at process start, which is unrelated once
seeding takes over.

Fixed: removed the early check; added `_guard_source_path` tracking in both
branches of the `if args.seed_run_dir: / else:` block, then run
`assert_prompt_hash(best_prompt_text, candidate=...)` once **after**
`best_prompt_text` is fully resolved (covers both the seeded-from-file and
the plain-`PROMPT_PATH` cases with one call), and log the resolved source
path and hash unconditionally on every run, before `PROMPT_PATH.write_text()`
and before iteration 1's diagnose/patch/score loop.

Added a public `sha256_text` alias in `analysis/version_guard.py` (was only
the private `_sha256`) so this logging didn't need to reach into a
name-mangled internal.

**Verified this is now "the same contract every other driver has,"** per
the prompt's phrasing: an unregistered hash hard-fails before any API call
naming the resolved path and hash; a registered `PROMPT_CANDIDATE` proceeds
and logs the same. See Step 5 demos 2–3.

## Step 3 — accepted divergence recorded as a decision

Confirmed the premise: `allocator_live`'s divergence lived only inside a
`status` string (`"deliberately a different artifact -- do not
parity-check"`), which reads as an ordinary artifact note, not a closed
decision a future session should not re-litigate.

Added `decisions.accepted_production_divergence` with `disposition:
"ACCEPTED -- KNOWN, DO NOT ACT"`, the reason (Test 1-6's premise, per
`ALLOCATOR_PORTING_METHODOLOGY.md`), the reopening condition (program
concludes AND conformance fixtures exist), and an explicit `do_not` list
(no merge to `dev`, no "helpfully" bringing `moves.js` in line, no treating
`allocator_live`'s hash as a thing that should match).

**Also confirmed and fixed a real problem this surfaced:** `allocator_live`
previously carried a `promoted_sha256` and was reported `MATCH`/`MISMATCH`
by `whats_live.py` like any gated artifact — which is exactly backwards for
something declared "deliberately a different artifact." A future,
completely unrelated edit to `moves.js` (a new feature, a bugfix) would
have flipped it to `MISMATCH` and looked like a drift alarm about something
explicitly out of the guards' scope. Nulled `promoted_sha256`, added
`last_observed_sha256` for reference only, and updated `whats_live.py`'s
`check_artifact()` to special-case it as informational (same treatment
`trend_analyst` and `ticker_universe` already had).

`whats_live.py` gained a new **"[6] Accepted / settled divergences — known,
do not act"** section, printed distinctly from **"[7] Open decisions"**
(renumbered from the old [6]), so the accepted divergence reads as settled
rather than outstanding.

**Confirmed, as asked:** `whats_live.py` emits **0 mismatch alerts** for any
informational/unhashed artifact. Verified for all three: `trend_analyst`
(two hashes shown, no promoted value, no match/mismatch verdict),
`allocator_live` (informational note, current hash shown for reference,
no match/mismatch verdict), `ticker_universe` (informational note, no
match/mismatch verdict). See the full run in Step 5 demo 4.

## Step 4 — doc corrections

1. **`allocator_v3`, not `v4`**, in `ALLOCATOR_PORTING_METHODOLOGY.md`: both
   references corrected (the "Why this exists" section's opening paragraph,
   and the version-vocabulary paragraph further down), each with an
   explicit 2026-09-12 correction note rather than a silent edit — per this
   project's standing rule that a corrected figure must supersede the old
   one explicitly. Confirmed (again) that `allocator_v4` is imported only
   by `analysis/run_expanded_test.py`, which is not behind any settled or
   published figure — **no place found where `allocator_v4` is load-bearing
   after all.**
2. **Type A/B finding added** to the "Still to be dispositioned" list in the
   same document, with an explanatory paragraph distinguishing it from the
   other items on that list: `ratchetTranche`/`TRIM_SIGNAL`/etc. are cases
   where `moves.js` implements *extra* machinery the simulator doesn't
   model; Type A/B is the reverse — `moves.js` implements **no concept at
   all**, not merely a different threshold.
3. **`prompts/version-registry-and-drift-guards.md`'s "six figures" →
   "eight"** corrected, with a note that the prior run's own wrap-up already
   used "eight" correctly and this was purely the source prompt catching up
   to its own report.

## Step 5 — verification, all four demonstrations pass

1. **`versions.js` with the registry moved aside** → module still loads
   (`require()` does not throw), logs loudly, exports
   `PROMPT_VERSION = MODEL_VERSION = 'UNKNOWN-REGISTRY-UNREADABLE'`.
   **Bonus, same demo extended:** `server/routes/evaluate.js` was also
   `require()`'d with the registry moved aside and **did not throw**,
   confirming the extra fix found in Step 1. Registry restored immediately
   after (`mv ... .movedaside` → `mv ... back`); re-required to confirm
   normal values return (`{PROMPT_VERSION: 'v6', MODEL_VERSION:
   'claude-sonnet-4-6'}`). **Pass.**
2. **`auto_iterate_prompt.py`'s seed-path check, unregistered hash** →
   built a scratch seed file (`.../fake_seed_dir/iter1/prompt_candidate.md`)
   with deliberately unregistered content, resolved it exactly as the
   fixed code path does, called `assert_prompt_hash` directly: raised
   `SystemExit` naming the resolved source path, its sha256
   (`13f6b4b6...`), the promoted hash, current branch, and dev-divergence —
   **before any API call**. **Pass.**
3. **Same seed file, `PROMPT_CANDIDATE=v10+auto1` declared** → proceeded
   (`candidate_used='v10+auto1'`), logged the resolved path and hash exactly
   as the driver's own logging line does. **Pass.**
4. **`whats_live.py` on the clean tree** → exit code **0**; the accepted-
   divergence decision printed under its own "[6] Accepted / settled
   divergences" heading with the reopening condition and all three `do_not`
   items; **zero** mismatch alerts among the three informational artifacts.
   **Pass.**

All deliberate breakage (the moved-aside registry copies) was restored
immediately after each demo. `git status --short` after all demos shows
only this run's real, intended edits — no residual diff from the
demonstrations themselves.

## Deviations and scope calls

- Fixed the same landmine in `evaluate.js` that the prompt asked to fix
  only in `versions.js` — flagged above as "found beyond the prompt's
  stated scope," not silently folded in.
- `analysis/version_guard.py` deliberately left fail-closed, per explicit
  instruction — confirmed unchanged, not a fix that was skipped.

## What was deliberately NOT done

No test was re-run, no benchmark figure recomputed, no allocator-parity
work attempted, no merge to `dev`, no change to allocator or trend-analyst
*logic* (only `auto_iterate_prompt.py`'s prompt-*seeding* logic was
touched, which the prompt explicitly carved out of the "no logic changes"
boundary). The accepted divergence itself is recorded as closed, not
resolved differently — no attempt was made to bring `moves.js` toward
`allocator_v3`.

## Follow-up commands

```zsh
# Re-run all four Step-5 demonstrations end to end
python3 analysis/whats_live.py

# Confirm versions.js and evaluate.js both fail safe (registry moved aside, then restored)
mv docs/architecture/VERSION_REGISTRY.json docs/architecture/VERSION_REGISTRY.json.bak
node -e "console.log(require('./server/lib/versions.js'))"
node -e "require('./server/routes/evaluate.js'); console.log('required OK')"
mv docs/architecture/VERSION_REGISTRY.json.bak docs/architecture/VERSION_REGISTRY.json
```

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018C47fL8C33NfRQYbdCsQhT
