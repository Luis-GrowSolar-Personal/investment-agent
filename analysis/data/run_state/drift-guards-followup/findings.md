# Findings — drift-guards-followup

## Step 1
- Confirmed premise: server/lib/versions.js's registry read was unguarded (throws at require() time on a missing/malformed VERSION_REGISTRY.json). Fixed with try/catch + UNKNOWN-REGISTRY-UNREADABLE sentinel.
- **Found beyond the prompt's stated scope:** server/routes/evaluate.js's own module-level `checkPromptHash()` call (the startup check) reads the same registry file via versionGuard.loadRegistry(), and would throw at require() time under the identical failure mode -- the prompt only named versions.js, but the landmine also existed here, one level over. Fixed the same way (try/catch, fail-safe startup log) plus wrapped the per-request handler's call so a registry read failure returns a clean 503 instead of crashing the async handler.
- Deliberately did NOT soften analysis/version_guard.py -- confirmed it remains fail-closed (a harness crash before scoring is correct there).

## Step 2
- Confirmed premise: auto_iterate_prompt.py's guard (added in the prior run) checked PROMPT_PATH.read_text() unconditionally, before the --seed-run-dir/--seed-prompt-file branch resolves best_prompt_text from a different path (seed_prompt_path). Closed by moving the check to after best_prompt_text is resolved, checking whatever text is about to be scored from whatever path it came from, and logging the resolved path + hash on every run.

## Step 3
- allocator_live previously carried a promoted_sha256 and was reported MATCH/MISMATCH like a gated artifact, contradicting its own "deliberately a different artifact" status. Nulled promoted_sha256, added last_observed_sha256 for reference, and added a proper `decisions.accepted_production_divergence` record. whats_live.py gained a dedicated "[6] Accepted / settled divergences" section, distinct from "[7] Open decisions". Confirmed 0 mismatch alerts across all 3 informational artifacts (trend_analyst, allocator_live, ticker_universe).

## Step 4
- Premise checked and confirmed correct (matches the prior run's own finding): ALLOCATOR_PORTING_METHODOLOGY.md loosely said "allocator_v2/v3/v4" and "allocator_v4" in two places where allocator_v3 is what actually backs the settled figures. Corrected both, with an explicit correction note (not a silent edit).
- Added the Type A/B finding to the still-to-be-dispositioned list, framed as qualitatively different from the other items on that list (moves.js implements no concept at all, vs. implementing extra machinery the simulator doesn't model).
- Confirmed and fixed: prompts/version-registry-and-drift-guards.md said "six figures" where 09-07 §5 has eight (its own header says so). The prior run's report already caught and used "eight" correctly -- only the prompt file itself needed the correction.
- No place found where allocator_v4 turns out to be load-bearing after all -- confirmed only run_expanded_test.py imports it, and that driver is not behind any settled/published figure.

## Step 5 — all 4 demonstrations passed, transcripts in the wrap-up.
