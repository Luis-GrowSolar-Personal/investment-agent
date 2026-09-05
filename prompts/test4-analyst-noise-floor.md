# Test 4 — analyst noise floor, at scale

`docs/handoffs/2026-09-05-state-of-play.md` §7 Test 4. Read §0 of that
document first. Also read `docs/architecture/PROMOTION_GATE.md` §6 and §8,
`docs/architecture/MODEL_SELECTION_BENCHMARK_SPEC.md` in full, and
`wrap-ups/test3-transcript-ingestion-fidelity-out.md` (Test 3 cleared the
corpus-integrity block on this test - see its Step 5 verdict).

**Scope, decided explicitly before this run**: noise-floor measurement
only. A paired champion-vs-challenger re-scoring (to resolve state-of-play
§5.5's open question about which direction `sonnet-4-6` actually errs) was
considered and deferred - it is a separate, larger, costlier run, not
folded into this one. Sample: **50 transcripts x 5 fresh scoring runs each
= 250 evaluator calls**, drawn from the existing portfolio corpus, not
ENPH.

## Why this run exists, and what it extends

`PROMOTION_GATE.md` §6 requires: *"re-run the evaluation N times at the
chosen temperature and take the spread of the metric. The candidate must
clear it."* This is not a new idea for the project -
`MODEL_SELECTION_BENCHMARK_SPEC.md`'s **Step 0** is exactly this
measurement, already run twice, both times on **ENPH only** - a ticker
that is not in the current ALL16 portfolio universe:

- **v6** (current production prompt logic, per its own changelog):
  **18/84 field-transcript combos unstable (21.4%)** across 21 ENPH
  transcripts x 3 runs, including `recommendation` itself flipping on
  **5 of 21 transcripts**.
- **v9** (a later candidate, gate-tested): got *worse*, not better -
  **26/84 (69.0%)** - traced to two specific rubric-wording bugs (the
  mitigation sub-test combination rule, and the capability-track-record
  no-prior-transcript case), not model or temperature. That candidate's
  gate **FAILED** and did not ship.

`PROMOTION_GATE.md` §10 separately flags that the existing model gate
(`gate_ledger.json` entry 1, sonnet-4-20250514 vs sonnet-4-6) used a
**bootstrap-over-tickers** noise estimate (4.2pp) on a single scoring pass -
a different, weaker proxy for "noise" than genuine repeat-scoring of
identical input, and scoped to only 7 unrepresentative tickers. **This run
produces the number PROMOTION_GATE §6 actually asks for, on a properly
balanced corpus**, directly comparable to both the historical Step 0
figures above and the gate ledger's bootstrap figure.

### Two live version-discipline issues to record, not fix

1. `server/lib/versions.js` currently pins `MODEL_VERSION =
   'claude-sonnet-4-6'` - **a bare, undated alias**, against §8's own rule
   ("must be a dated snapshot... never a bare/-latest alias"). This is a
   known forced exception (comment: "dated snapshot retired by Anthropic"),
   not something to fix here - but it means this run's result may not be
   exactly reproducible later if Anthropic updates what that alias
   resolves to. Record the model identity as precisely as the API response
   allows, and flag this risk plainly in the report.
2. `docs/EVALUATION_PROMPT.md` on disk is **v10+auto1** ("gate status:
   pending" per its own header), not the `v6` that `versions.js` stamps on
   production rows. **Use the file exactly as found - do not modify it -**
   and report which version string its own header actually carries. This
   run's noise-floor figure describes v10+auto1's behavior, not v6's;
   state that plainly rather than letting it read as a v6 result.

---

## Step −1 — resume protocol

`run_id` is **`test4-analyst-noise-floor`**, state in
`analysis/data/run_state/<run_id>/`. This is a single-session run (no
external rate limit like Alpha Vantage's), but **checkpoint after every
transcript's 5 runs complete** - an Anthropic API call can transiently
fail even within one session, and a resume must not redo finished
transcripts. Write `progress.json` before any reading; append to
`findings.md` the moment a finding is established.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

---

## Step 1 — draw the sample (50 transcripts, by rule)

**Universe**: the 15-ticker portfolio corpus already censused this session
(not ENPH):

| Tier | Tickers |
|---|---|
| Megacap | AAPL, GOOGL, NVDA, MSFT, TSLA |
| Large | AVGO, AMD, ORCL |
| Mid | FSLR, TTD |
| Small/micro | QS, AMPX, ENVX, EOSE, RUN |

**Restrict to call dates on or before the scoreable cutoff** - recompute
this fresh, the same way Test 2 did (`FORWARD_DAYS` from
`analysis/analyst_direct_scorer.py`, against the current max date in
`price_cache.json`), rather than reusing Test 2's number blindly - the
cache may have moved. This restriction is required because Step 4 below
needs a forward return for every drawn transcript.

**Target ~12-13 per tier for 50 total.** Query each tier's actual
pre-cutoff pool size first (`SELECT` only) - do not assume the raw counts
from this session's earlier census apply once the cutoff filter is
applied. If a tier's pre-cutoff pool is short of its even share,
reallocate the shortfall across the other tiers, the same way the AV
stratified benchmark did, and show the arithmetic.

**Draw with a fixed, reported random seed.** Print the per-tier pool size
(post-cutoff), the target allocation, the seed, and the full drawn list of
50 (ticker, call date) pairs before any evaluator call is made.

---

## Step 2 — five fresh scoring runs per transcript (250 calls total)

For each of the 50 drawn transcripts, run the evaluator **5 times**,
identical input each time:

- **Prompt**: `docs/EVALUATION_PROMPT.md` exactly as found on disk, **not
  modified**. Report its header's version string verbatim.
- **Model**: whatever `server/lib/versions.js` `MODEL_VERSION` currently
  resolves to. Report the exact string sent to the API, and anything the
  API response itself reveals about which underlying snapshot served the
  request, if available.
- **Temperature 0.** No portfolio context - single-transcript evaluation
  only, consistent with the analyst/allocator firewall (`DESIGN_PRINCIPLES.md`
  §1).
- **No DB writes.** These 250 scoring runs are a measurement exercise, not
  new production data - do **not** write any of them to the `Analysis`
  table. Keep all output under this run's own
  `analysis/test4_noise_floor/` directory.

Checkpoint (`progress.json` + `findings.md`) after each transcript's 5 runs
complete. Track approximate token usage (input + output tokens summed
across all 250 calls) and report it - this run has a real dollar cost,
unlike the free-tier AV benchmarks, and that cost should be visible.

---

## Step 3 — field-by-field stability

**Primary (for direct comparison to the two historical Step 0 figures
above)**: the same four fields `MODEL_SELECTION_BENCHMARK_SPEC.md` used -
`thesisHealth`, `recommendation`, `stumbleType`,
`mitigationCapabilityTrackRecord`. Report **unstable (transcript, field)
combinations out of 200 (50 x 4)**, as a count and a percentage, in the
same units as the v6 (18/84, 21.4%) and v9 (26/84, 69.0%) figures. State
plainly whether this run's rate sits closer to v6's, v9's, or neither -
**prediction is not a gate**, report whichever way it goes.

**Call out `recommendation` instability specifically** - how many of the
50 transcripts had `recommendation` itself vary across the 5 runs (v6's
ENPH-only figure was 5 of 21). This is the single most consequential
instability, since it's the categorical direction the whole downstream
gate metric depends on.

**Secondary (fuller diagnostic)**: all 15 structured fields from Test
3/benchmark_1's Step 6 field list. For each (transcript, field), report the
number of distinct values across the 5 runs. Aggregate per field across
all 50 transcripts, so the noisiest fields are visible by name (benchmark_1
flagged `credibilityDelta`, `mitigationArgumentPresent`,
`mitigationCapabilityTrackRecord`, `blindSpotsTriggered` as worth watching
- confirm or refute that at this larger scale).

---

## Step 4 — the headline noise floor, in gate units (pp)

For **each of the 5 runs independently**, compute the sample's
analyst-direct hit rate using `analysis/analyst_direct_scorer.py`'s exact
methodology (import its constants, do not reimplement) - benchmark-relative
2-quarter forward return, ±5% dead band, direction from
`thesisHealth`/`recommendation` per `PROMOTION_GATE.md` §3.1's predictand
rule - across all 50 transcripts, for that run.

This produces **5 independent hit-rate values on the identical 50-
transcript sample.** Report:

- The spread across these 5 values - **standard deviation and range
  (max−min), in percentage points.** This is the noise floor
  `PROMOTION_GATE.md` §6 actually asks for, measured by genuine
  repeat-scoring rather than the bootstrap-over-tickers proxy already in
  `gate_ledger.json` (4.2pp).
- The same spread broken out by cap tier - does noise correlate with
  smaller/less-followed names, an interesting parallel to the AV fidelity
  benchmark's own hypothesis. Report whichever way it goes.

---

## Step 5 — reading, against what's already on record (report, do not decide)

Compare this run's measured noise floor **directly** against
`gate_ledger.json` entry 1's existing figures: `noise_std_pp: 4.2`, and the
`sonnet-4-6` regression of `-7.44pp` measured against it.

- If this run's more rigorously measured noise floor is **similar to or
  smaller than 4.2pp**, the original HOLD verdict's substance likely still
  stands even though its *scope* was unrepresentative (per state-of-play
  §5.4) - the regression clearly exceeds genuine noise either way.
- If this run's noise floor is **materially larger than 4.2pp**, that is a
  more serious finding: it would mean the gate's own noise threshold was
  understated, and the -7.44pp regression may not clear a properly
  measured bar by as much margin as the ledger currently states. **Do not
  re-adjudicate the gate verdict here** - flag it for the design session.

State plainly whether Test 6 (look-ahead prohibition probe) - which
state-of-play §7 says needs this noise floor as its own detection
threshold - is now unblocked with a usable number.

---

## Report

Scope boundary: **report, do not decide.** Do not amend
`PROMOTION_GATE.md`, do not modify `gate_ledger.json`, do not re-run or
re-adjudicate the model gate, do not write any scoring output to the
`Analysis` table, do not modify `EVALUATION_PROMPT.md`.

Open with resume status, then:

> **Sample: 50 transcripts (megacap [N], large [N], mid [N], small/micro
> [N]), seed [N]. Prompt version used: [header string]. Model string used:
> [exact string], reproducibility risk: [bare alias, flagged / dated
> snapshot confirmed]. Primary 4-field instability: [N]/200 ([X]%) -
> compare v6 21.4%, v9 69.0%. Recommendation flips: [N]/50. Noise floor
> (spread of analyst-direct hit rate across 5 runs): [X]pp std, [Y]pp range
> - compare gate_ledger's 4.2pp bootstrap figure. By tier: [table]. Reading:
> the existing -7.44pp regression [clearly exceeds / does not clearly
> exceed] this more rigorously measured noise floor. Test 6: [unblocked
> with a usable threshold / still needs more]. Approximate token spend:
> [N] tokens across 250 calls.**

Flag plainly: any field whose instability rate is far outside what v6's
historical figure would predict, any transcript where all 5 runs disagreed
completely on `recommendation` (a 3+ way split, not just a 2-way flip), and
anything that looks like the same rubric-wording defects v9's gate
already diagnosed (the mitigation combination rule, the no-prior-transcript
capability case) recurring in v10+auto1.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no
  Linux package managers or path assumptions.
- **No DB writes at all** - not even the scoring output. `SELECT` only for
  the sample draw and the forward-return lookups.
- Do not modify `docs/EVALUATION_PROMPT.md`.
- Checkpoint after every transcript's 5 runs. Track and report approximate
  token usage.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance - file, manifest path, JSON
  key, or table/column.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
