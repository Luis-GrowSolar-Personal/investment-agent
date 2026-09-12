# Findings — version-registry-and-drift-guards

## Step 0
- Branch fix: cherry-picked `c514ae1` onto `sweep/db-corpus-baseline` (new commit `21d0c03`). Working-tree `docs/EVALUATION_PROMPT.md` now v6.
- Hash verification: `7063465` blob sha256 `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b` == `c514ae1` blob == post-cherry-pick working tree. IDENTICAL. No stop condition triggered.
- Pre-fix state: working tree held v10+auto1, sha256 `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14` (matches the known-bad deployed hash from 2026-09-03-prompt-version-drift.md).
- git_dirty at run start: technically true (one modified tracked file), but that file (`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`) belongs to a different, concurrently-running run_id. Not touched. All other entries were untracked inputs/scratch, not staged.

## Step 1 — premises checked
- Prompt claims 09-07 state-of-play §5 has "six figures" corrected. **Actual: eight** (header literally says "eight figures and claims corrected"). Flagged, not a stop condition.
- Prompt claims fundamentals_cache.json is "118 days stale." As of this run's date (2026-09-12) it is **124 days** (latest fetchedAt 2026-05-11T02:36:57Z). Difference fully explained by the prompt's figure being computed on an earlier date (~2026-09-07, which would be ~119 days) — not a real disagreement. whats_live.py computes this dynamically, not hardcoded.
- Prompt claims ALL16 is "copy-pasted verbatim across ~15 files." Actual count: **17 files** define `ALL16 =`. All 17 agree (verified: 9 spell it out literally, 8 derive it as ESTABLISHED+SPECULATIVE with identical underlying lists). No disagreement found.
- Prompt names `analysis/simulator/allocator_v*.py` as one artifact for `allocator_simulator`. There are 4 distinct files (allocator.py, v2, v3, v4) that are not sequential replacements. The settled-configuration driver (`run_db_corpus_baseline.py`) imports `allocator_v3`, not `allocator_v4`. Registered promoted_version as v3 (what's actually in use), v4 flagged as an untested candidate used only by `run_expanded_test.py`.
- New finding, not in the prompt: the live app (`server/routes/moves.js`, `dashboard.js`, `radar.js`) does not read `type_classifications.json` at all, and has no fixed 35%/50% Type A/B cap rule anywhere — caps come from `Ticker.capPercent`/`OwnerTickerConfig.capPercent`, a hand-set number per ticker. This is a second, previously undocumented app/backtest divergence, separate from the moves.js-vs-allocator_v3 divergence the porting methodology already tracks. Registered in `type_classifications.status`; not fixed (out of scope — no allocator logic changes).

## Step 0b / registry hashes computed this run (verified sha256, not transcribed)
See docs/architecture/VERSION_REGISTRY.json for the full set.
