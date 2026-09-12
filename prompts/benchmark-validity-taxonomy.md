# Benchmark validity — three states instead of a boolean

Small corrective run. **$0 API spend. No LLM calls. No DB writes.** Branch
`sweep/db-corpus-baseline`; no merge to `dev`. `run_id`
**`benchmark-validity-taxonomy`**.

## Precondition — check first, STOP if it fails

This run rewrites `docs/architecture/VERSION_REGISTRY.json`. Every scoring
driver reads it as a hard gate before each call and
`version_guard._load_registry()` does **not** cache. A scoring run that
catches the file mid-write aborts — a paid run killed for the wrong reason.

**Confirm no scoring run is in flight** (check every
`analysis/data/run_state/*/progress.json` for an incomplete scoring phase,
and `ps aux`). `test4-analyst-noise-floor-v6` is expected to be **halted,
never started** — its steps read pending and its `transcripts_completed` is
empty. If any run is actually live, **stop and report.**

## Why

`wrap-ups/model-provenance-corrections-out.md` correctly flagged its own
load-bearing consequence: **6 of 7 benchmark records now read STALE**, four
of them permanently with no possible remediation. The only unflagged record
is `ew_baseline` — which `09-05` §8 says explicitly must **not** be quoted
as measured. That is exactly backwards, and a flag that fires on nearly
everything stops carrying information (the alert-fatigue failure the
`allocator_live` handling correctly avoided, reintroduced via the model
axis).

**The deeper problem: STALE conflates two different facts.**

- **Reproducibility** — `settled_control` replays to the cent. Frozen corpus
  rows, deterministic simulator; every run this week hit $179,944.91 exactly.
  It is not stale in any reproducibility sense.
- **Representativeness** — it describes a system driven by an analyst that
  no longer exists, permanently.

Those demand opposite responses. "Cannot reproduce" is a data-integrity
alarm. "Reproducible but describes a retired configuration" is a
don't-extrapolate warning — which is just `PROMOTION_GATE.md` §11.1's tuple
rule restated.

**Concrete harm, with a worked case that already happened:** Test 5
(`wrap-ups/test5-universe-substitution-out.md`, complete 2026-09-06)
reproduced Arm A against `settled_control`'s $179,944.91 **to the cent** and
built its entire comparison on corpus-anchored figures. Under the current
boolean flag, every figure it relied on now reads STALE. A session reading
that could reasonably conclude Test 5's comparison was invalid. **It was
not** — Test 5 ran on the same corpus, the same tuple, so §11.1 is satisfied
exactly. The flag would discredit a sound, completed result.

## Step 1 — the three states

Replace the boolean with:

| state | meaning | how to cite |
|---|---|---|
| **VALID** | every `valid_while` artifact unchanged | freely |
| **SUPERSEDED** | a `valid_while` artifact moved, but the figure can still be regenerated from surviving inputs | **only within its own tuple** (§11.1); never extrapolate to the current system |
| **UNREPRODUCIBLE** | the inputs no longer exist; the figure can never be re-verified | historical record only |

The tool cannot infer reproducibility from hashes — it must be **declared**.
Add to each benchmark record a `reproducibility` field with a value and a
short note. Expected assignments, to be **verified per record, not assumed**:

- **The four corpus-anchored records** (`settled_control`,
  `test1_zero_info_floor`, `sizing_channel_null`, `small_cap_materiality`) →
  **SUPERSEDED**, reproducibility `deterministic_replay`. The figure replays
  exactly from frozen `Analysis` rows. Carry a distinct note that the
  underlying *scoring* can never be redone (`claude-sonnet-4-20250514`
  retired 2026-06-15), which is why the model axis can never be cleared for
  them — that is a permanent property, not a defect awaiting a fix.
- **`test4_per_tier_noise_floors`, `test6_look_ahead_null`** →
  **SUPERSEDED**, reproducibility `requires_rescoring_under_candidate` (the
  v10+auto1 blob survives at `87bcfaa`; re-running means deliberately
  invoking a registered candidate).
- **`test5_universe_substitution`** → **add this record if absent** (Test 5
  completed 2026-09-06 and may predate the registry). Arm A $179,944.91 /
  20.85% dd; Arm B $119,134.95 (−33.79%) / 19.93% dd; Step 5 resampling, 25
  draws, seed 20260906, Arm A at the 100th percentile of a $107,344–$158,347
  range. Corpus-anchored, `claude-sonnet-4-20250514`, so **SUPERSEDED**,
  `deterministic_replay`, same permanence note as the other four. Record the
  wrap-up's own two caveats with it: the resampling pool excludes AVGO/AMD/ORCL
  — three of Arm A's eight, and part of the semis concentration that drives
  its result — so the 100th-percentile figure is structurally flattered; and
  it is one draw, not a distribution.
- **`ew_baseline`** → keep its existing `quotable: false`. It was never
  reproduced and its ruler is unknown; make sure the new scheme does not
  leave it looking like the one clean record. If `UNREPRODUCIBLE` fits it
  better than the quotable flag alone, say so and apply it.

## Step 2 — `whats_live.py`

Rework the `[4]` section from "Stale benchmarks" into validity states,
grouped, with counts. Requirements:

- **SUPERSEDED must not read as a defect.** Print the citation rule with it
  — safe within its own tuple, never extrapolated — so a future session
  draws the right conclusion without reading §11.
- **State explicitly that permanent model-axis supersession on the corpus
  records is expected and has no remediation.** A reader must not go looking
  for a fix that does not exist.
- **UNREPRODUCIBLE, if any record qualifies, is the one that deserves
  attention.** Order the output so it is not buried under four expected
  entries.
- Exit-code behaviour unchanged: validity states are informational, never a
  non-zero exit. Only a promoted-artifact hash mismatch exits non-zero.

## Step 3 — `PROMOTION_GATE.md` §11.5

§11.5 currently reads that a figure "is stale the moment any artifact hash it
was measured under changes" — the boolean framing this run replaces. Refine
it to the three states, note the corrected date, and keep the old sentence
visible as superseded per this project's standing rule. Add a changelog
entry.

## Step 4 — verify

Show output for each:

1. `whats_live.py` on the clean tree → exit **0**; the four corpus records
   grouped as SUPERSEDED with the permanence note; test4/test6 as SUPERSEDED
   with their own reason; counts per state.
2. A record flips VALID → SUPERSEDED when an artifact it depends on changes
   — **on a COPY of the registry at a temp path, never the live file**, even
   briefly and even with a revert. Delete the copy after.
3. `git status --short` clean of demo residue.

## Report

> **States: [N] VALID, [N] SUPERSEDED, [N] UNREPRODUCIBLE. Corpus four
> classified [X] with permanence note; test4/test6 [X]; ew_baseline [X].
> whats_live.py exit 0, SUPERSEDED prints its citation rule.
> PROMOTION_GATE §11.5 refined, old wording preserved. Demo 2 passes on a
> copy, live registry never mutated. $0 API spend.**

Flag plainly: any record whose reproducibility could not be determined from
its own provenance rather than assumed, and whether `ew_baseline` is better
served by `UNREPRODUCIBLE` than by its existing `quotable: false`.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers.
- No LLM calls, no DB writes, no merge to `dev`.
- Do not touch `analysis/test4_noise_floor/`, `analysis/test6_look_ahead/`,
  or any `test4-analyst-noise-floor-v6*` state.
- Never mutate the live registry for a demonstration.
- Do not write new handoff docs. This prompt in, one wrap-up out.
