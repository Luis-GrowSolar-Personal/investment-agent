# Wrap-up: model-provenance-corrections

**Run:** `model-provenance-corrections` | **Branch:** `sweep/db-corpus-baseline`
**Type:** Corrective build. **$0 API spend. No LLM calls. No DB writes. No merge to `dev`.**
**Wall-clock:** ~20 minutes.

---

> **Registry: bare-alias flag withdrawn (old text preserved as superseded),
> retirement of 4-20250514 verified (2026-06-15), retirement_date
> 2027-02-17 recorded. Benchmarks: model added to 7/7 records (5
> sonnet-4-20250514 / 2 sonnet-4-6 / 1 explicitly N/A — ew_baseline is a
> market-price benchmark with no analyst-scoring step); valid_while
> extended on all 6 applicable records. whats_live.py: countdown 157 days,
> warning threshold 90d, exit 0. Wrap-up caveats withdrawn in 3 files
> (2 wrap-ups + the 09-07 state-of-play) by appended note, originals
> unaltered. Demo 2 (staleness flips on model change) passes. $0 API
> spend.**
>
> **Load-bearing finding, not anticipated by the prompt's own framing:**
> implementing Step 2's `valid_while` extension literally makes **4**
> corpus-anchored benchmark records (`settled_control`,
> `test1_zero_info_floor`, `sizing_channel_null`, `small_cap_materiality`)
> report **STALE on the model axis in the live registry, right now** — not
> only in a demo — and **permanently, with no possible remediation**, since
> the corpus they derive from was scored once under
> `claude-sonnet-4-20250514` (retired, unregenerable) and the currently
> promoted model is `claude-sonnet-4-6`. See "Load-bearing finding" below.

---

## Precondition check (Step 0)

**PASS.** Checked every `analysis/data/run_state/*/progress.json` for an
incomplete scoring phase before touching the registry, per this prompt's
hard precondition. `test4-analyst-noise-floor-v6-driftcheck` (the 25-call
model-drift check from the prior, interrupted `test4-noise-floor-v6-rerun`
session) had already completed cleanly — `step2_250_scoring_calls: "done"`,
5/5 transcripts. `test4-analyst-noise-floor-v6` (the 250-call v6 arm) had
never started — all steps `pending`, `transcripts_completed: []`, and
`ps aux` confirmed no `test4_noise_floor.py` process running. Safe to
proceed. Per this prompt's own instruction, none of that state (or
`analysis/test4_noise_floor/`, `analysis/test6_look_ahead/`) was touched.

Tree hygiene: the only pre-existing dirt was the concurrent
`ec-fidelity-benchmark-1` session's own files (not touched) and this run's
own new untracked prompt file. `docs/architecture/PROMOTION_GATE.md` was
modified on disk by the user directly, outside this run — read as
authoritative current state (its §8 correction and new §8.1 are exactly
what this run implements), not touched or reverted.

## Step 1 — registry `model` artifact corrected

`docs/architecture/VERSION_REGISTRY.json`'s `artifacts.model` record:

- **Old note preserved verbatim** under a new key,
  `note_superseded_2026-09-12`, exactly as it read before — per this
  project's standing rule that a correction supersedes explicitly and is
  never quietly replaced.
- **New `note`** cites `PROMOTION_GATE.md` §8's 2026-09-12 correction:
  post-4.6 dateless IDs are canonical pinned snapshots, not floating
  aliases; the bare-alias flag was written against the pre-4.6 convention
  and doesn't apply.
- **`status`** changed from `"promoted, flagged"` to `"promoted --
  correctly pinned (bare-alias flag withdrawn 2026-09-12)"`.
- **Added** `retirement_date: "2027-02-17"` and
  `retirement_policy_notice_days: 60`, plus a `retirement_date_note`
  flagging it as tentative ("not sooner than").
- **Retired candidate's own record** (`claude-sonnet-4-20250514` under
  `candidates`) gained `retired_date: "2026-06-15"` and a note that this is
  now independently verified, not just claimed in a commit message.

## Step 2 — `model` added to every benchmark record

All 7 records in `benchmarks` now carry a top-level `model` field (distinct
from the informal `model` string that already existed inside some records'
`artifact_versions_and_hashes` sub-object — that was descriptive prose, not
a field `whats_live.py` could read programmatically):

| record | model | how determined |
|---|---|---|
| `settled_control` | `claude-sonnet-4-20250514` | already named in `artifact_versions_and_hashes` |
| `test1_zero_info_floor` | `claude-sonnet-4-20250514` | already named in `artifact_versions_and_hashes` |
| `test4_per_tier_noise_floors` | `claude-sonnet-4-6` | already named in `artifact_versions_and_hashes` |
| `test6_look_ahead_null` | `claude-sonnet-4-6` | already named in `artifact_versions_and_hashes` |
| `sizing_channel_null` | `claude-sonnet-4-20250514` | **verified, not assumed** — 09-07 §4.1's own text says this is a deterministic in-simulator sizing-perturbation sweep replayed against `settled_control`'s corpus rows, not a fresh scoring run; it inherits the corpus model. Recorded as `model_note` on the record itself. |
| `small_cap_materiality` | `claude-sonnet-4-20250514` | same basis as `sizing_channel_null` — verified against 09-07 §4.2's text |
| `ew_baseline` | `null` | **flagged explicitly, per the report instruction** — this is an equal-weight *market-price* benchmark, not an analyst-scored figure at all. "Model could not be determined" would mischaracterize it; the correct statement is that a model field doesn't apply here the way it does to the other six. Recorded as an explicit `null` with a `model_note` explaining why, so it reads as "N/A, considered" rather than a silent gap. |

`valid_while` extended with `"model unchanged"` on all 6 records that have
a real model value (not `ew_baseline`, where it's inapplicable).

## Step 3 — retirement countdown in `whats_live.py`

New section `[6] Model retirement countdown`, inserted after `[5] Cache-age
breaches` (bumping the former `[6]`/`[7]` to `[7]`/`[8]`). For every
registered artifact carrying a `retirement_date`, prints days remaining
against a **90-day warning threshold** (ahead of Anthropic's 60-day notice
policy, so the deadline is a countdown rather than an email). Live output
today: `model (claude-sonnet-4-6): retires 2027-02-17 -- 157 days left
(warning threshold 90d)` — no warning flag, correctly, since 157 > 90.

Per §8.1 step 2, the section carries the actual consequence, not just the
date: within the warning window it prints the instruction to capture a
paired bridge sample under both models before retirement, naming the
corpus-under-`claude-sonnet-4-20250514` precedent as why this cannot be
recovered afterward. **Exit-code behavior unchanged** — this section never
sets a non-zero exit; confirmed live (`Exit code: 0` after Step 6's
section prints).

## Step 4 — wrap-up caveats withdrawn by appended note

Appended a dated correction section (not a rewrite) to:

1. `wrap-ups/test4-analyst-noise-floor-out.md` — its headline block and
   Step 2 both said "reproducibility risk: **bare alias, flagged**."
2. `wrap-ups/test6-look-ahead-prohibition-out.md` — described
   `claude-sonnet-4-6` as "the same bare, undated alias Test 4 used."
3. `docs/handoffs/2026-09-07-state-of-play.md` — §6 said
   "(bare alias — reproducibility risk stands)."

Each note states the caveat is withdrawn, cites `PROMOTION_GATE.md` §8's
correction, and states plainly that no *measured figure* in that document
is affected — only the reproducibility-risk framing. Originals left
otherwise unaltered, per the standing rule that historical wrap-ups are
appended to, never rewritten.

**Not reached, flagged per the report's instruction:** the same "bare
alias" language also appears, unchanged, in
`docs/handoffs/2026-09-06-state-of-play.md`,
`docs/handoffs/2026-09-05-exit-latency-framework.md`,
`analysis/data/run_state/test4-analyst-noise-floor/findings.md`, and
several historical `prompts/*.md` files (`test4-noise-floor-v6-rerun.md`,
`test4-analyst-noise-floor.md`, `version-registry-and-drift-guards.md`,
`prompt-version-drift-investigation.md`, `test6-look-ahead-prohibition.md`).
This prompt's Step 4 scoped the correction to exactly two wrap-ups plus the
09-07 state-of-play; the others were left untouched deliberately, not
missed.

## Step 5 — verification, all pass

1. **`whats_live.py` on the live registry** → exit **0**; retirement
   countdown present and correct (157 days); all 7 benchmark records
   display a `model` value (6 real, 1 explicit `null`). **Pass.**
2. **Staleness flip on model change, on a scratch copy only** — copied
   `VERSION_REGISTRY.json` to the scratchpad, never touched the live file:
   - **BEFORE**: set the copy's `artifacts.model.promoted_version` to
     `claude-sonnet-4-20250514` (simulating the pre-migration state) → the
     4 corpus-anchored records show **no** model-axis staleness; only the
     pre-existing prompt-axis staleness (`test4_per_tier_noise_floors`,
     `test6_look_ahead_null`) remains.
   - **AFTER**: set it to `claude-sonnet-4-6` (the real current value) →
     all 4 corpus-anchored records flip to **STALE (model axis)**, with
     the reason naming both the recorded and currently-promoted models.
   - This proves the `valid_while` mechanism actually recomputes staleness
     from the live promoted model, not merely that a `model` field exists
     on the record. **Pass.**
3. **`git status --short`** after cleanup shows no demo residue — the
   scratch copy was deleted, and the only changes present are this run's
   real, intended edits. **Pass.**

## Load-bearing finding: literal Step 2 causes real, permanent live staleness

This is the one thing in this run that deserves emphasis beyond the
checklist. Running `whats_live.py` on the **actual, current**
`VERSION_REGISTRY.json` (no demo, no mutation) now shows:

```
[4] Stale benchmarks (valid_while artifacts have moved)

  STALE  settled_control  (model axis)
  STALE  test1_zero_info_floor  (model axis)
  STALE  sizing_channel_null  (model axis)
  STALE  small_cap_materiality  (model axis)
```

This is **not a bug** — it is `PROMOTION_GATE.md` §11.5 ("staleness is
computed, not remembered") and §11.1 (absolute figures are tuple-scoped,
including model) doing exactly what they say, now mechanized instead of
left to prose. But it has a consequence the prompt's own framing did not
anticipate: **these 4 records can never stop being stale.** The corpus
underlying them was scored once, under `claude-sonnet-4-20250514`, which is
retired and cannot be regenerated at any price (already established,
`ALLOCATOR_PORTING_METHODOLOGY.md` comparison-protocol rule 1). Every
future `whats_live.py` run — forever, regardless of what model is
subsequently promoted — will report these 4 records as stale on the model
axis, with no action that resolves it.

Contrast with `test4_per_tier_noise_floors` / `test6_look_ahead_null`:
those *are* re-scoreable (a fixed 50-transcript sample, not the historical
corpus), so their model-axis staleness is actionable — a future model
change really does mean "go re-measure this." The corpus-anchored four are
categorically different: their staleness is a permanent fact about the
world, not a to-do.

**Flagging, not deciding** (per this run's scope boundary): the design
session should decide whether corpus-anchored records need a distinct
`valid_while` semantic — e.g., a `model_locked: true` flag meaning "this
model is permanently part of the record's identity, not a staleness
trigger" — versus accepting that `[4] Stale benchmarks` will always list
these four and treating that as expected background noise the same way
`[5] Cache-age breaches` already reports an expected, frozen-by-design
breach every run. Implemented literally as instructed here; not
redesigned, since redesigning `valid_while` semantics is a decision this
run's scope explicitly excludes.

## Deviations and scope calls

- The prompt's Step 2 line "All seven `benchmarks` records currently carry
  no model field" was true only for a top-level `model` field — four of
  the seven already carried an informal `model` string nested inside
  `artifact_versions_and_hashes`. Added the top-level field as asked
  without removing the pre-existing nested prose (kept for its narrative
  value alongside the new machine-readable field).
- `ew_baseline` recorded as `model: null` with an explanatory note rather
  than a guessed value, since it is a market-price benchmark with no
  scoring step at all — flagged explicitly per the report's own
  instruction to name any record whose model could not be determined
  "from provenance rather than assumed."

## What was deliberately NOT done

- The five additional files carrying the withdrawn bare-alias language
  (listed under Step 4 above) — out of this prompt's stated scope.
- No redesign of `valid_while` semantics for corpus-anchored vs.
  re-scoreable benchmark records, despite the finding above — a design
  decision, not this run's to make.
- No re-adjudication of `gate_ledger.json` entry 1's HOLD verdict, no
  forced-exception ledger entry written (both still open per
  `PROMOTION_GATE.md` §8.1's own "Open" line) — explicitly out of scope,
  this run only implements the documentation/registry correction.

## Follow-up commands

```zsh
# Confirm the corrected registry and countdown
python3 analysis/whats_live.py

# Re-run the staleness-flip demo safely, on a fresh scratch copy
cp docs/architecture/VERSION_REGISTRY.json /tmp/registry_demo.json
python3 -c "
import json
d = json.load(open('/tmp/registry_demo.json'))
d['artifacts']['model']['promoted_version'] = 'claude-sonnet-4-20250514'
json.dump(d, open('/tmp/registry_demo.json', 'w'), indent=2)
"
python3 analysis/whats_live.py --registry-path /tmp/registry_demo.json
rm /tmp/registry_demo.json
```

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018C47fL8C33NfRQYbdCsQhT
