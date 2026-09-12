# Wrap-up: benchmark-validity-taxonomy

**Run:** `benchmark-validity-taxonomy` | **Branch:** `sweep/db-corpus-baseline`
**Type:** Corrective build. **$0 API spend. No LLM calls. No DB writes. No merge to `dev`.**
**Wall-clock:** ~20 minutes.

---

> **States: 0 VALID, 6 SUPERSEDED, 1 UNREPRODUCIBLE. Corpus four
> (`settled_control`, `test1_zero_info_floor`, `sizing_channel_null`,
> `small_cap_materiality`) classified SUPERSEDED / `deterministic_replay`
> with a permanence note; `test4_per_tier_noise_floors` /
> `test6_look_ahead_null` classified SUPERSEDED / `requires_rescoring_under_candidate`
> (the v10+auto1 blob is recoverable); `ew_baseline` classified
> **UNREPRODUCIBLE**, not merely `quotable: false` — no driver ever computed
> it and its ruler is unknown. `whats_live.py` exit 0, SUPERSEDED prints its
> citation rule inline, UNREPRODUCIBLE printed first and unmissable.
> `PROMOTION_GATE.md` §11.5 refined to the three states, old boolean wording
> preserved as explicitly superseded. Demo 2 passes on a scratch copy — 4
> records flip VALID→SUPERSEDED as the copy's promoted model changes — live
> registry never mutated. $0 API spend.**

---

## Precondition (checked first, per this prompt's own hard stop)

**PASS.** `test4-analyst-noise-floor-v6`'s `progress.json` confirmed halted,
never started, exactly as the prompt itself expected: all 6 work steps
`pending`, `transcripts_completed: []`. `ps aux` confirmed no
`test4_noise_floor.py` process running. Swept every other
`analysis/data/run_state/*/progress.json` for an incomplete scoring
step — none found. Safe to rewrite `VERSION_REGISTRY.json`.

`docs/architecture/PROMOTION_GATE.md` had been modified on disk directly
by the user, outside this session, before this run started (its §8/§8.1
model-pinning correction). Read as current authoritative state, not
touched or reverted; this run's own §11.5 edit lands in the same file
alongside it.

## Why (verified, not assumed)

Confirmed the premise exactly as stated: `wrap-ups/model-provenance-corrections-out.md`
did flag its own consequence — implementing §11.5's boolean literally made
6 of 7 benchmark records read `STALE`, 4 of them (the corpus-anchored
records) permanently. `ew_baseline`, the one record `09-05` §8 already says
must never be quoted as measured, was the *only* one left unflagged by the
old boolean — exactly backwards, and confirmed by re-reading the pre-change
registry state before editing anything.

## Step 1 — the three states, declared per record

Added a `reproducibility` field (state, value, note) to all 7
`benchmarks` records in `VERSION_REGISTRY.json`. Per this prompt's own
instruction that the tool cannot infer reproducibility from a hash
comparison — it must be declared — each assignment was checked against its
own source text, not assumed from the expected table:

| record | state | value | verified against |
|---|---|---|---|
| `settled_control` | SUPERSEDED | `deterministic_replay` | replays from frozen `Analysis` rows under the deterministic `allocator_v3` simulator; repeated reproduction to the cent this project has made across multiple sessions (cross-referenced against prior wrap-ups' own repeated citation of $179,944.91 — not independently re-run this session, since doing so would mean re-executing an hour-plus backtest for a figure already established as stable; noted as the verification method used, not left silent) |
| `test1_zero_info_floor` | SUPERSEDED | `deterministic_replay` | same corpus mechanism, every verdict forced Hold |
| `sizing_channel_null` | SUPERSEDED | `deterministic_replay` | 09-07 §4.1's own text: "every cell tied the $179,944.91 control to the cent" — an in-simulator sweep over the settled_control corpus rows, not a fresh scoring run |
| `small_cap_materiality` | SUPERSEDED | `deterministic_replay` | 09-07 §4.2, same basis as `sizing_channel_null` |
| `test4_per_tier_noise_floors` | SUPERSEDED | `requires_rescoring_under_candidate` | confirmed the v10+auto1 blob survives at commit `87bcfaa` (sha256 `b81d24c6...`), already registered as a `candidates` entry under `artifacts.evaluation_prompt` from the `version-registry-and-drift-guards` build — re-measurement is a `PROMPT_CANDIDATE=v10+auto1` invocation away, not a lost input |
| `test6_look_ahead_null` | SUPERSEDED | `requires_rescoring_under_candidate` | same basis, paired reuse of the same 50-transcript sample |
| `ew_baseline` | **UNREPRODUCIBLE** | `no_known_method` | confirmed `baseline.py` computes SPY/QQQ/TMFC only — no driver on record ever produced this figure, and its ruler (session-sampled vs daily-marked) is unknown per its own existing note; a future EW computation would be a *new* figure under a chosen methodology, not a reproduction of this one |

All 4 corpus-anchored records carry an explicit note that the model-axis
mismatch (`claude-sonnet-4-20250514`, retired 2026-06-15, vs the currently
promoted `claude-sonnet-4-6`) is **permanent and has no remediation to look
for** — the corpus was scored once and can never be rescored.

## Step 2 — `whats_live.py` reworked

`[4]` renamed from "Stale benchmarks" to "Benchmark validity (three states,
not a boolean)". Behavior:

- **Computed, not read from a static flag, for VALID vs SUPERSEDED**: a
  `classify()` helper checks each record's declared `stale` flag (prompt-axis
  cases) or dynamically compares its recorded `model` against the live
  promoted model (comparison-protocol rule 5). Only `UNREPRODUCIBLE` is
  taken as a pure declaration, per Step 1's own instruction that it cannot
  be inferred.
- **Ordering**: `UNREPRODUCIBLE` prints first, under a `**...**`-bracketed
  header calling out that it "needs attention, unlike the states below" —
  so it cannot be buried under the (expected, larger) `SUPERSEDED` group.
- **SUPERSEDED prints its own citation rule inline** — "cite ONLY within
  its own tuple... never extrapolate" — so a future session gets the right
  conclusion without having to separately recall or look up §11.1.
- **`--registry-path`** added so the flip demo (Step 4) can point the
  checker at a scratch copy without ever touching the live file.
- **Exit-code behavior unchanged**: confirmed live — `Exit code: 0` printed
  after the new `[4]` section, same as before this run.

Live output today: **0 VALID, 6 SUPERSEDED, 1 UNREPRODUCIBLE.** Zero VALID
is a true, non-alarming fact about the current moment (every one of the 7
records has *some* caveat — prompt drift, model retirement, or a genuinely
unreproduced figure) — not a defect in the classification.

## Step 3 — `PROMOTION_GATE.md` §11.5 refined

Old boolean sentence ("stale the moment any artifact hash... changes")
**kept visible**, explicitly labeled superseded, immediately followed by
the corrected three-state definition, the `settled_control` /
`ew_baseline` contrast that motivates it, and an explicit statement that
the corpus-four's model-axis supersession is permanent and non-actionable
by design. Changelog entry `2026-09-12b` added, appended after the
existing `2026-09-12` §11 entry (not overwriting it).

## Step 4 — verification, all pass

1. **`whats_live.py` on the clean/live tree** → exit **0**; the four corpus
   records grouped SUPERSEDED with the permanence note; test4/test6 grouped
   SUPERSEDED with their own (different, actionable) reason; counts printed
   (`0 VALID, 6 SUPERSEDED, 1 UNREPRODUCIBLE`). **Pass.**
2. **VALID → SUPERSEDED flip, on a scratch copy only** (never the live
   file, per this prompt's explicit instruction):
   - **BEFORE**: copy's `artifacts.model.promoted_version` set to
     `claude-sonnet-4-20250514` (matching the corpus records' recorded
     model) → `settled_control`, `test1_zero_info_floor`,
     `sizing_channel_null`, `small_cap_materiality` all read **VALID**
     (4 VALID, 2 SUPERSEDED, 1 UNREPRODUCIBLE).
   - **AFTER**: set to `claude-sonnet-4-6` (the real current value) → all
     four flip to **SUPERSEDED** (0 VALID, 6 SUPERSEDED, 1 UNREPRODUCIBLE).
   - Proves the mechanism recomputes from live state rather than reading a
     static label. **Pass.**
3. **`git status --short`** after cleanup shows only this run's real edits
   — the scratch copy was deleted immediately after the demo, no residue.
   **Pass.**

## Flags, as instructed

- **Any record whose reproducibility could not be determined from its own
  provenance rather than assumed:** none. All 7 were verified against
  their own source text (09-07 §4.1/§4.2 for the sizing/small-cap
  sensitivity sweeps; `baseline.py`'s actual scope for `ew_baseline`;
  `87bcfaa`'s existence in git history for the v10+auto1 candidates) rather
  than transcribed from this prompt's own expected-assignments table.
- **`ew_baseline`: UNREPRODUCIBLE fits it better than `quotable: false`
  alone**, as this run's own question asked. The distinction that matters:
  `quotable: false` alone reads as "don't cite this (yet)," which could be
  misread as "not cited *yet*, but could be validated later." `UNREPRODUCIBLE`
  states the stronger, more accurate fact — there is no known methodology
  behind this number to even attempt validating, so a future EW computation
  would be a new figure, not a confirmation of this one. Applied.
- **The one previously-published number that turns out affected**: none of
  the underlying *figures* changed — this run only reclassifies how they
  may be cited. No number in any wrap-up needed a corrected value.

## Deviations and scope calls

- `settled_control`'s "reproduces to the cent across repeated runs" claim
  was verified by cross-referencing its repeated citation across multiple
  prior wrap-ups and state-of-plays this session already had context on,
  **not** by independently re-executing the backtest this run (that would
  mean re-running an hour-plus deterministic simulation for a figure this
  project has already established as stable many times over). Disclosed
  as the verification method used, per Step 4's instruction to confirm
  premises rather than assume them.
- Both `test4_per_tier_noise_floors` and `test6_look_ahead_null` already
  carried a static `stale: true` flag from the prior `model-provenance-corrections`
  build; `classify()` reads that flag as the SUPERSEDED trigger for these
  two (prompt-axis) rather than re-deriving it from a prompt-hash
  comparison, since `VERSION_REGISTRY.json` does not currently store a
  clean, single comparable prompt-hash field per benchmark record the way
  it does for `model`. Noted rather than silently built around.

## What was deliberately NOT done

- No re-derivation of `valid_while`'s prompt-axis condition into a
  dynamically-hash-checkable field (would require adding a per-record
  prompt-hash field, a larger registry-schema change not asked for here).
- No redesign of whether corpus-anchored records should eventually gain a
  `model_locked: true`-style flag instead of appearing in the `SUPERSEDED`
  group forever — `model-provenance-corrections-out.md` raised this as an
  open design question; this run answers it with the three-state taxonomy
  (which already makes the "permanent, non-actionable" distinction
  explicit via the note field) rather than a fourth registry flag. If the
  design session wants an even more explicit signal, that is a further
  decision, not made here.
- No action on `gate_ledger.json` entry 1's still-open HOLD verdict — out
  of scope, unrelated to this run's taxonomy work.

## Follow-up commands

```zsh
# Confirm the corrected three-state classification
python3 analysis/whats_live.py

# Re-run the VALID -> SUPERSEDED flip demo safely, on a fresh scratch copy
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
