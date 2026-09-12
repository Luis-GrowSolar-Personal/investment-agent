# Test 4 re-run — the noise floor under v6

**Run:** `test4-analyst-noise-floor-v6` | **Branch:** `sweep/db-corpus-baseline`
**Real spend: ~275 Anthropic calls, ~4.17M tokens across the v6 arm plus
the driftcheck bridge sample. No DB writes.** User approved before Step 0
(confirmed explicitly, this session, before any call was made).

---

## Resume status — reconciliation happened before Step 2, as instructed

This invocation resumed a run that had been stopped mid-session (user
interrupt) before it could checkpoint its own `progress.json`. Per the
user's explicit instruction, reconciliation ran **before spending
anything**:

- **`progress.json` said `step1_reuse_sample: pending` and
  `step2_model_drift_check: pending`. Disk was ahead of both.**
  `sample.json` already existed (50 rows, correct tier counts: megacap 13 /
  large 13 / mid 12 / small_micro 12) — Step 1 had already completed.
  `analysis/test4_noise_floor_v6/driftcheck/raw/{23,132,141,212,230}.json`
  all existed, each with exactly 5 complete runs and valid structured
  output, `prompt_candidate_used: "v10+auto1"` in every one.
  `run_state/test4-analyst-noise-floor-v6-driftcheck/progress.json`
  independently confirmed `step2_250_scoring_calls: "done"`.
- **Verified complete. No calls re-issued.** Both steps marked `done` in
  this run's `progress.json` without spending anything. Full detail in
  `analysis/data/run_state/test4-analyst-noise-floor-v6/findings.md`.
- **This is the second time this project's checkpointing has correctly
  protected spend across an interruption** — the first was the original
  Test 4 run's two OS low-memory kills. This time the interruption was a
  user-directed stop rather than a crash; the same discipline held.

From that point, this run completed all remaining steps to a full report:
Step 3 (the 250-call v6 arm) ran to 50/50 across two background
invocations (the *monitoring* loop was killed twice for system low memory;
the *scoring process itself* was never interrupted and completed both
times it was checked — no calls lost, no partial transcripts).

---

> **Prompt asserted: v6 @ `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`
> (guard passed, no candidate set). Original v10+auto1 output intact: 50
> files, unmodified (asserted at every invocation via
> `assert_original_protected()`). Model-drift check (25 calls,
> `PROMPT_CANDIDATE=v10+auto1`): 4/5 transcripts reproduce exactly,
> transcript 23 (EOSE) does not — reported per the corrected
> post-4.6-pinning understanding as ordinary sampling noise on a
> known-unstable name, NOT evidence of drift; candidate hatch behaved
> exactly as specified (every row correctly stamped `v10+auto1`, never the
> promoted version). **v6 per-tier noise floor: megacap 4.87pp, large
> 3.08pp, mid 3.33pp, small/micro 4.17pp** (std; ranges 15.38/7.69/8.33/11.36pp).
> Primary 4-field instability **60/200 (30.0%)** — compare v10+auto1
> 19.5%, historical ENPH-only v6 21.4%, v9 69.0%. Recommendation flips
> **14/50 (28.0%)**, including 3 three-way-or-more splits (ids 175 ENVX,
> 204 MSFT, 355 QS — the last with one unparseable run). vs v10+auto1
> paired: **v6 is noisier in aggregate AND differently shaped** —
> informative, NOT a §2.2a gate. Gate reading vs -7.44pp: aggregate
> **exceeds** (~3.2 SD), tier-matched (small_micro) **now marginal**
> (~1.78 SD, no longer comfortably inside noise) — prompt-version mismatch
> **resolved**, scope mismatch **remains**. Concurrency: **5-way
> implemented and held throughout, zero serial fallback**. Registry
> updated — `test4_v6_per_tier_noise_floors` is the registry's **first and
> only VALID record**; `whats_live.py` exit **0**. Tokens: 4,147,250 (v6
> arm) + 426,423 (driftcheck) = 4,573,673 total over 275 calls, 2
> background invocations, wall clock ~50 minutes of active scoring
> (bounded by checkpoint timestamps, not separately logged to the second).**

---

## Step 0 — hygiene and protection

Original `analysis/test4_noise_floor/raw/` asserted intact at every
invocation of the parameterized driver: 50/50 files, and never equal to
this run's `--out-dir`. `assert_original_protected()` (built in the prior
`drift-guards-followup` session) refuses to proceed otherwise — confirmed
firing correctly (PASS printed at both the driftcheck and v6-arm
invocations). `docs/architecture/PROMOTION_GATE.md` §6/§11, this project's
CLAUDE.md rules, and the three prerequisite wrap-ups
(`test4-analyst-noise-floor-out.md`, `version-registry-and-drift-guards-out.md`,
`drift-guards-followup-out.md`) were read in full before any code ran, per
this prompt's own instruction, in the parent session before this
resumption.

## Step 1 — sample reused, not redrawn

`analysis/data/run_state/test4-analyst-noise-floor/sample.json` copied
verbatim into this run's own `run_state/test4-analyst-noise-floor-v6/`
directory. Verified: 50 rows, tier counts megacap 13 / large 13 / mid 12 /
small_micro 12 — matching `PROMOTION_GATE.md` §11.6's requirement that a
noise floor is sample-scoped and transfers only to the identical
transcripts.

## Step 2 — model-drift check, reframed per the user's added note

**The check is now known-moot as drift detection.** `PROMOTION_GATE.md` §8
(corrected 2026-09-12): from Claude 4.6 onward a dateless model ID is a
pinned, immutable snapshot — Anthropic does not repoint existing IDs. So
`claude-sonnet-4-6` cannot have silently changed underneath this project.
This 25-call exercise is reported as **a candidate-hatch functional test
and a bridge sample**, not as evidence about drift, per the user's explicit
instruction.

**Candidate hatch: worked exactly as specified.** All 5 driftcheck output
files record `prompt_candidate_used: "v10+auto1"` — the escape hatch
correctly overrode the promoted-prompt guard, and every row is traceable
to the candidate, never silently mislabeled as the promoted version (the
exact 2026-09-03 incident this machinery exists to prevent).

**Reproduction against the original Test 4 run's saved output** for the
same 5 named transcripts (212/141 megacap, 132 large, 230 mid, 23
small_micro), comparing recommendation sets across the 5 runs:

| transcript | ticker | tier | original | bridge (this run) | match |
|---|---|---|---|---|---|
| 132 | ORCL | large | Add×5 | Add×5 | YES |
| 141 | MSFT | megacap | Add×5 | Add×5 | YES |
| 212 | MSFT | megacap | Add×5 | Add×5 | YES |
| 230 | TTD | mid | Add×5 | Add×5 | YES |
| **23** | **EOSE** | **small_micro** | **Add,Add,Add,Add,Hold** | **Hold×5** | **NO** |

**4/5 reproduce exactly. Transcript 23 (EOSE) does not** — a full flip from
4-Add/1-Hold to unanimous 5-Hold. Per the corrected understanding, this is
**not** evidence of alias drift (a pinned ID cannot silently change); the
more likely explanation is ordinary temperature-0 sampling variance on a
name Test 4's own original run already flagged as the most unstable tier
(small_micro, 58% flip rate, 14.34pp std). Flagged, not adjudicated — it
does not change any conclusion about the v6 arm, which is a v6 question,
not a v10+auto1-vs-v10+auto1 one.

## Step 3 — the v6 arm, 250 calls

`docs/EVALUATION_PROMPT.md` used exactly as found, no `PROMPT_CANDIDATE`
set. **Guard asserted the promoted v6 hash and passed** — confirmed
directly before launch (`assert_prompt_hash` returned `ok: True,
candidate_used: None`). Verified across all 50 output files:
`prompt_version_header: "v6 (stable best after v5→v8 iteration)"`,
`prompt_candidate_used: null`, `model: "claude-sonnet-4-6"`.

**5-way concurrency implemented and held throughout — this is not a
rhetorical confirmation, it is verified from the data.** Every one of the
50 raw files records `"concurrency": "5-way concurrent"`; no file shows a
serial-fallback note, meaning zero rate-limit responses were hit across
250 calls. `concurrency_notes_seen` in `progress.json` contains exactly one
value: `["5-way concurrent"]`.

**50/50 transcripts, 250/250 calls, zero calls lost or re-run** despite
the monitoring loop being killed twice by the OS for low system memory —
the scoring process itself ran uninterrupted both times it was checked
(41/50 → 50/50 between the two checks). Token spend: **4,147,250 tokens**
(3,464,905 in / 682,345 out).

## Step 4 — results and the three comparisons

**(a) v6 per-tier noise floor** — the real numbers:

| tier | hit rates across 5 runs | std (pp) | range (pp) | n |
|---|---|---|---|---|
| megacap | 23.1/15.4/23.1/30.8/23.1% | **4.87** | 15.38 | 13 |
| large | 76.9/69.2/76.9/76.9/76.9% | **3.08** | 7.69 | 13 |
| mid | 41.7/41.7/50.0/41.7/41.7% | **3.33** | 8.33 | 12 |
| small_micro | 33.3/36.4/36.4/33.3/25.0% | **4.17** | 11.36 | 12 |

Aggregate: std 2.31pp, range 6.12pp. Primary 4-field instability:
**60/200 = 30.0%**. Recommendation flips: **14/50 = 28.0%**, with **3
three-way-or-more splits**: id 175 (ENVX: Add,Trim,Hold,Hold,Hold), id 204
(MSFT: Trim,Hold,Hold,Add,Trim), id 355 (QS: Hold,**null**,Trim,Trim,Trim —
one run's output failed to parse; flagged as a data-quality note distinct
from genuine recommendation instability). Recommendation-flip concentration
by tier (direct per-sample inspection): **megacap 5/13 (38.5%)**, large
1/13 (7.7%), mid 2/12 (16.7%), **small_micro 6/12 (50.0%)**.

**(b) v6 vs v10+auto1, paired on the identical 50-transcript sample:**

| metric | v10+auto1 (original) | v6 (this run) |
|---|---|---|
| primary 4-field instability | 39/200 (19.5%) | **60/200 (30.0%)** |
| recommendation flips | 11/50 (22.0%) | **14/50 (28.0%)** |
| aggregate noise std/range | 2.65pp / 8.0pp | 2.31pp / 6.12pp |
| megacap noise std/range | 3.77pp / 7.69pp | **4.87pp / 15.38pp** |
| large noise std/range | **0.0pp / 0.0pp** | **3.08pp / 7.69pp** |
| mid noise std/range | **0.0pp / 0.0pp** | **3.33pp / 8.33pp** |
| small_micro noise std/range | **14.34pp / 41.67pp** | **4.17pp / 11.36pp** |
| flip rate, megacap | 2/13 (15%) | **5/13 (38.5%)** |
| flip rate, large | 0/13 (0%) | 1/13 (7.7%) |
| flip rate, mid | 1/12 (8%) | 2/12 (16.7%) |
| flip rate, small_micro | 7/12 (58%) | 6/12 (50.0%) |

**LOAD-BEARING FINDING, contradicting an expectation this prompt itself
implicitly carried: v6 is not a cleaner-behaving prompt than v10+auto1 on
this sample — it is noisier in aggregate (30.0% vs 19.5% primary
instability; 28.0% vs 22.0% flips), and the *shape* of the noise is
different, not just its magnitude.** v10+auto1 showed a striking
large/mid-tier floor of exactly **0.0pp** — perfectly stable — with all
measured noise concentrated in small_micro (14.34pp). **v6 spreads noise
across every tier** (3.08–4.87pp each), and its single highest-std tier is
now **megacap** (4.87pp), not small_micro (which, at 4.17pp, is actually
the *lowest* of the three non-large tiers under v6). Reported as a
diagnostic finding per this project's own rule that a diagnostic
contradicting an expectation is a finding, not a reason to stop — no
implementation was adjusted to make this look different, and no gate was
worked around.

**Per the prompt's own scope boundary, restated: this is informative, NOT
a §2.2a gate.** No holdout, no forward-return regression computed, no
`gate_ledger.json` entry opened, no recommendation to promote or condemn
either prompt. **The §2.2a gate for every prompt version from v7 onward
has still never been run** — unchanged by this result.

**(c) v6 here vs v6's historical figure (21.4%, 18/84, ENPH-only, 3 runs,
whichever model was live in July).** This run's 30.0% (60/200) is **the
first measurement of v6's stability on the actual portfolio corpus at 5
runs** — every axis differs simultaneously from the historical figure
(sample size, run count, and very possibly model, since §8.1 records the
model-forcing migration only starting late June). Not a like-for-like
comparison; not treated as one.

## Step 5 — the gate reading, one mismatch resolved and one not

**Now legitimate on the prompt axis**: both the regression
(`gate_ledger.json` entry 1, 2026-05-23, HOLD, `delta_pp -7.44`,
`noise_std_pp 4.2`) and this floor are measured under v6. That was the
entire purpose of this re-run.

**Still not legitimate on the scope axis, and this run does not fix it**:
entry 1's 7 tickers (ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR) are
overwhelmingly small/micro-cap.

- **Aggregate reading**: -7.44pp against 2.31pp aggregate std ≈ **3.2
  standard deviations**. Clearly exceeds noise.
- **Tier-matched reading (small_micro)**: -7.44pp against **4.17pp** std ≈
  **1.78 standard deviations.**

**This tier-matched reading has materially changed from the original,
v10+auto1-measured Test 4.** That run's small_micro floor was 14.34pp,
putting the same regression at only ~0.52 SD — comfortably inside noise,
the basis for reading the HOLD verdict's substance as questionable. **Under
v6, the small_micro floor is much tighter (4.17pp), and the same
regression now sits at ~1.78 SD — no longer comfortably inside noise**,
though still short of a conventional ~2 SD bar. Both readings now point
the same rough direction (regression not clearly absorbed by noise), where
the original run's two readings disagreed sharply.

**Report, not adjudicate — no re-run or amendment of the model gate made
here.** What would settle it, unchanged in kind from the original
conclusion but now sharper in what it needs: the paired champion-vs-
challenger re-scoring, pinning **both** the model and the prompt version to
v6 — which this run's result suggests may genuinely change the reading,
not merely tighten the measurement.

## Step 6 — registry updated

`docs/architecture/VERSION_REGISTRY.json` gained
`benchmarks.test4_v6_per_tier_noise_floors`, carrying `model`,
`artifact_versions_and_hashes`, `valid_while`, and the full three-state
`reproducibility` field this project's registry schema now uses (the
`VALID`/`SUPERSEDED`/`UNREPRODUCIBLE` states live under the field named
`reproducibility` — there is no separate `validity` field in the current
schema; the two names describe the same mechanism, noted here since this
prompt's own wording used both terms).

**Both `valid_while` conditions (`evaluation_prompt unchanged`,
`model unchanged`) currently hold** — the record was measured under the
promoted v6 prompt and the promoted `claude-sonnet-4-6` model, both still
live. **This makes `test4_v6_per_tier_noise_floors` the registry's first
and only `VALID` benchmark record**, stated explicitly per this run's
instruction and confirmed live:

```
Counts: 1 VALID, 6 SUPERSEDED, 1 UNREPRODUCIBLE
```

**This VALID status is not permanent** — like every VALID record, it will
flip to `SUPERSEDED` the instant the promoted prompt or model changes,
exactly as `benchmark-validity-taxonomy`'s own Step 5 demo proved the
mechanism does (on a scratch copy, never the live file — the same
discipline was not needed here since this was a real, not a demonstrated,
registry write).

`whats_live.py` confirmed: **exit 0** after this update. The 6 prior
`SUPERSEDED` records and the 1 `UNREPRODUCIBLE` record (`ew_baseline`) are
unchanged in state — only a new record was added, nothing was reclassified.

## Flags, as instructed

- **Any tier whose v6 floor differs materially from its v10+auto1 value
  (either direction)**: **all four tiers differ materially.** Large and mid
  moved from an exact 0.0pp floor to 3.08pp/3.33pp respectively (from
  perfectly stable to modestly noisy). Small_micro moved from 14.34pp down
  to 4.17pp (from by far the noisiest tier to comparable with the others).
  Megacap moved from 3.77pp up to 4.87pp, becoming the new highest-std
  tier. Every direction is represented; none is uniform.
- **Whether small/micro remains the dominant noise source**: **no.** Under
  v6 it is not even the highest-std tier (megacap is, at 4.87pp vs
  small_micro's 4.17pp) — a direct reversal of the original finding's
  headline conclusion, which was specific to v10+auto1.
- **Any transcript with a 3+ way recommendation split**: ids 175 (ENVX),
  204 (MSFT), 355 (QS, with one unparseable run) — full detail in Step 4.
- **What the model-drift check revealed about the bare-alias risk**:
  nothing, by design — per the corrected §8 understanding, there is no
  bare-alias risk to reveal for a post-4.6 pinned ID. The one genuine
  observation it did produce (transcript 23's non-reproduction) is
  attributed to ordinary sampling noise on a known-unstable name, not to
  model identity drift, and is reported as such rather than mislabeled.

## Deviations and scope calls

- The registry schema uses a single field, `reproducibility`, to hold the
  three-state classification (`VALID`/`SUPERSEDED`/`UNREPRODUCIBLE`) —
  this run's own prompt referred to this as a `validity` field distinct
  from `reproducibility`. No second field was added; the existing one
  already serves both purposes, as built in `benchmark-validity-taxonomy`
  earlier this session. Noted rather than silently reconciled.
- Wall-clock time is bounded, not logged to the second — the monitoring
  loop being killed twice for system memory means there is a gap in
  continuous observation between 41/50 and 50/50; the process's own
  checkpoint timestamps in `findings.md` bound the true duration to
  well under an hour of active scoring.

## What was deliberately NOT done

- No amendment to `EVALUATION_PROMPT.md`, `versions.js`,
  `PROMOTION_GATE.md`, or `gate_ledger.json` — scope boundary, held.
- No merge to `dev`.
- `analysis/test4_noise_floor/` and `analysis/test6_look_ahead/` were not
  modified — only read, to protect Test 6's control arm and the original
  comparison baseline. Verified intact at 50/50 files throughout.
- No adjudication of the -7.44pp regression's significance — Step 5's two
  readings are reported side by side, not resolved. That determination
  still needs the paired champion-vs-challenger re-scoring this run's own
  scope explicitly defers.
- No root-causing of the field-level instability shifts (e.g. why
  `recommendedSize` is 90% unstable under v6 vs whatever it was under
  v10+auto1) — out of this run's scope, flagged as a further question for
  the design session.

## Follow-up commands

```zsh
# Re-run the analysis step on the already-scored v6 output (no new calls)
cd analysis
python3 test4_noise_floor.py analyze --run-id test4-analyst-noise-floor-v6 --out-dir test4_noise_floor_v6

# Inspect any individual v6-arm transcript's 5 raw runs directly
python3 -c "
import json
d = json.load(open('analysis/test4_noise_floor_v6/raw/204.json'))
for r in d['runs']:
    print(r['run_idx'], r['structured'].get('recommendation') if r['structured'] else None)
"

# Confirm the registry's new VALID record and overall state
python3 analysis/whats_live.py
```

---

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018C47fL8C33NfRQYbdCsQhT
