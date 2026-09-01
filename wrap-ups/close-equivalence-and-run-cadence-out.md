# Close equivalence and run cadence — PARTIAL RUN

**Resume status:** cold start. `analysis/data/run_state/close-equivalence-and-run-cadence/`
did not exist before this session (confirmed). No steps were previously done, so
nothing was resumed and no cells were reused.

**This is a partial run.** Only Step -1 (resume-state scaffolding) and part of
Step 0 (hygiene checks) were completed. Steps 1 through 8 — the fourth-bug
instrumentation, Gate 1a, the spec-correction deltas, the pooling
re-derivation, the full cadence grid, the fold-ins, and the final gates/rules
— were **not executed** in this session. No backtests were run. No numbers in
this document are measured; none should be treated as findings.

## What was done

- Verified fresh start: no prior `run_state/close-equivalence-and-run-cadence/`
  directory existed.
- Confirmed `git_dirty = false` on `sweep/db-corpus-baseline` at session start.
- Confirmed the driver file and target function exist as described:
  `analysis/bracket_three_modes_s11_corrected.py`, `make_funding_decide_fn`
  starting at line 275 (prompt said ~257-494; actual start is line 275 —
  close enough not to be a premise failure, but worth noting for the next
  session).
- Confirmed `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` exists with
  numbered sections 0, 2, 3, 4, 5, 9, 10 present by header. §10b and §11 were
  not individually re-verified by heading text in this pass — the next
  session should confirm those before relying on them for Step 1's toggle
  discipline and Step 7's gate wording.
- Created run-state scaffolding at
  `analysis/data/run_state/close-equivalence-and-run-cadence/`:
  - `progress.json` — prompt_sha256, driver_commit, per-step status, and a
    precise `next_action` pointing at Step 1.
  - `cells.jsonl` — created empty; no cells run yet.
  - `findings.md` — created with only scaffolding notes; no measured
    findings yet.
- Un-ignored `analysis/data/run_state/` in `.gitignore`, following the same
  pattern used for `analysis/data/run_manifests/`.

## What was deliberately NOT done

- No instrumentation of `day_start_of_day_value[t]` / `day_trimmed_today[t]`
  (Step 1) — not started.
- No Gate 1a run (Step 2).
- No spec-correction delta pricing (Step 3).
- No pooling re-derivation or sequential-vs-pooled sweep (Step 4).
- No cadence grid (Step 5) — this step alone is a large multi-axis sweep
  (K × phase × scope × limit × draws) and was correctly not attempted given
  this session's budget.
- No `minPositionPct` / ordering / staleness fold-ins (Step 6).
- No gates/rules scoring (Step 7).
- Nothing in this run disturbs the six settled sessions in §0 — no code in
  the settled path was touched at all.

## Exact resume point

`progress.json`'s `next_action`:

> Resume at Step 1: instrument `day_start_of_day_value[t]` and
> `day_trimmed_today[t]` for every donor at every calendar date in
> `make_funding_decide_fn` (`analysis/bracket_three_modes_s11_corrected.py:275-494`)
> for both the reference path and the session-model path, starting
> 2022-01-01, to find the first ticker/date where they disagree (expected
> near QS on 2024-02-14 per prior findings, donor AAPL suspected). This
> requires actual code instrumentation and backtest runs — not done yet in
> this session.

## Follow-up commands for the next session

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git status --porcelain   # must be clean before resuming
cat analysis/data/run_state/close-equivalence-and-run-cadence/progress.json
tail -n 40 analysis/data/run_state/close-equivalence-and-run-cadence/findings.md
```

Re-read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b, §11
in full before writing any instrumentation, per the prompt's instruction that
those decisions are closed and must not be re-derived.
