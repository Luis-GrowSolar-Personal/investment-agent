# Sizing-channel sensitivity — what `recommendedSize` instability actually costs

Follow-on to Test 1 (`wrap-ups/analyst-sensitivity-out.md`) and Test 4
(`wrap-ups/test4-analyst-noise-floor-out.md`). Read both first, plus
`docs/handoffs/2026-09-05-state-of-play.md` §4 (Test 1's results), §5.2 (the
"the allocator does not select — it weights" finding) and §0 (the **ruler**
term — every drawdown figure in this run must name its ruler).

**Cost: $0 in Anthropic API spend.** No LLM calls. This is an in-memory
perturbation harness over already-loaded scores, exactly like Test 1, plus a
read of Test 4's already-saved raw output.

## Why this run exists — a gap between two completed tests

Three established findings, which together leave a hole:

1. **State-of-play §5.2:** the first-call starter fires for every name
   regardless of score, so the allocator does not *select*, it *weights* —
   "the analyst's entire contribution is **sizing**."
2. **Test 1 measured the recommendation channel only.** Its harness
   (`analysis/analyst_sensitivity_harness.py`) perturbs `final_action`,
   `per_call_rec` and `thesis_health`. Its own docstring states
   `recommended_size` is "untouched by this harness." So the channel §5.2
   identifies as the analyst's entire contribution has **never been
   perturbation-tested.**
3. **Test 4 found that channel is the least stable thing it measured.**
   `recommendedSize` varied across 5 identical re-runs on **96% of
   transcripts**; `freshMoneyAllocation` on 98%. Direct measurement of the
   saved raw output during the design session: per-transcript **std ~3.07pp
   median, 7.69pp max**; spread (max−min) **~9pp median, 22pp max** (FSLR
   swinging 18 → 40 on one transcript). Unlike the categorical instability,
   this is **not** concentrated in small/micro — megacap, large and mid all
   show ~10pp median spreads while small/micro shows ~4.5pp.

So: the load-bearing channel is the noisiest one, and nobody has measured
what that noise costs. **This run produces that number.**

## The mechanism — encoded here so it is not rediscovered or misread

Read `analysis/simulator/allocator_v2.py` `_decide_add()` and
`analysis/simulator/allocator_v3.py` `decide()` before writing any code, and
confirm each of these against the source rather than trusting this summary:

- **`recommended_size_pct` is consumed on the `Add` branch only.** `Hold`
  returns immediately, `Trim`/`Exit` never receive it. **The exposure
  surface is therefore bounded by the Add rate**, which Step 1 must measure
  before anything else — if `Add` is rare in this corpus, the ceiling on
  this whole channel's importance is low no matter how noisy the field is.
- **The clamp:** `target_pct = min(recommended_size_pct, cap_pct) if
  recommended_size_pct else cap_pct` (allocator_v2). Caps are speculative
  **15%**, established **35%**, Type B **50%**. Test 4's observed values run
  **3.0 to 40.0**. So for a speculative name most variation above 15 is
  absorbed by the cap, while for an established name an 18 → 35 swing is
  **fully expressed**. **Pre-registered prediction, to be confirmed or
  refuted, not assumed: the sizing channel should matter MORE for
  established names than speculative ones — the opposite of Test 4's
  categorical-instability tier pattern.** Report whichever way it goes.
- **`X=2.5pp` throttles speed, not destination.** The per-session change cap
  slows convergence toward `target_pct`; it does not change what the target
  is. Do not conclude "X absorbs the noise" without measuring — a persistent
  difference in target is reached eventually, just later.
- **Latent defect, record do not fix:** `if recommended_size_pct else
  cap_pct` is a Python truthiness test, so **both `None` and `0.0` fall
  through to the FULL cap** — a model emitting `0` ("do not size this")
  would produce a *maximum-size* position. Test 4's 250 runs contained
  **zero nulls and zero zeros**, so this is not live today. Verify that
  independently against the corpus in Step 1, then log it in `findings.md`
  and the wrap-up as a latent defect. **Do not patch the allocator.**

---

## Step −1 — resume protocol

`run_id` is **`sizing-channel-sensitivity`**, state in
`analysis/data/run_state/<run_id>/`. Cheap deterministic cells, same profile
as Test 1 — checkpoint `progress.json` + append `findings.md` after each
grid cell completes, and write `cells.jsonl` per cell so a resume never
re-runs a finished cell.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit. Work on
`sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.

---

## Step 1 — exposure census and control reproduction (do this before any perturbation)

**1a. Reproduce Test 1's uncorrupted control exactly.** Same settled
configuration Test 1 used — `swap_funding`, `K=30`, `new_calls_only`,
`X=2.5pp`, pooled, `per_event_date`, phase 0, `tie_seed=0`, via
`sweep_cadence_and_session_model.load_events_dedup_on()` and
`run_session_sweep_cell`. Expected `final_value` **$179,944.91** (Test 1's
phase-0 uncorrupted cell; state-of-play §5.1 records the same figure).
**If it does not reproduce, stop and report** — every number below is
relative to it. This is the same hard-stop gate Test 1 applied to its own
`q=0.0` cell.

**1b. Measure the exposure surface.** Over the loaded corpus, report:

- Count of events by `final_action` (the value `decide()` actually reads:
  `event.final_action or event.per_call_rec or "Hold"`), and the **`Add`
  count as a share of all events**. This is the ceiling on how much the
  sizing channel can possibly matter.
- Of those `Add` events, how many carry a non-null `recommended_size`, and
  the distribution of those values (min/median/max, and a histogram
  coarse enough to read).
- **How many would be clamped**, split by tier: `Add` events on speculative
  names with `recommended_size` > 15, and on established names with
  `recommended_size` > 35. A value above the cap is *already* absorbed
  today, so noise in that region costs nothing — quantify how much of the
  observed noise lands in the absorbed region versus the expressed region.
- Any `recommended_size` equal to `0` or `None` on an `Add` event (the
  latent-defect check above).

**If Step 1b shows `Add` events are a small share of the corpus, say so
plainly and carry that ceiling into every conclusion below.** A large
percentage swing on a rarely-consumed field is a small dollar number.

---

## Step 2 — perturb the sizing channel, calibrated to measured noise

Extend Test 1's harness pattern — **do not modify
`analyst_sensitivity_harness.py` in place**; write a new driver that imports
the same loader and cell runner, so Test 1 stays reproducible.

**Calibrate the perturbation to Test 4's actual measured dispersion, not to
invented `q` values.** Derive the per-transcript standard deviation of
`recommendedSize` directly from `analysis/test4_noise_floor/raw/*.json`
(50 transcripts × 5 runs, already on disk, $0). Report the derived figures
and cross-check them against the design session's own measurement — median
**~3.07pp**, mean ~3.46pp, max **~7.69pp**. A material divergence means one
of the two derivations is wrong; investigate before proceeding rather than
picking the more convenient number.

Cells to run (each over **15 corruption seeds**, `tie_seed` fixed at 0, same
as Test 1's grid, reporting medians and the seed spread):

| cell | what it does |
|---|---|
| `control` | untouched, must equal Step 1a's figure exactly |
| `jitter_0.5x` / `jitter_1x` / `jitter_2x` / `jitter_3x` | add Gaussian noise to `recommended_size` at 0.5/1/2/3× the measured per-transcript std, clamped to a sane domain (report the clamp) |
| `biased_high` / `biased_low` | shift every `recommended_size` by +1σ / −1σ — separates *random jitter* from *systematic mis-sizing*, the same way Test 1's `optimistic`/`pessimistic` separated direction from magnitude |
| `size_ignored` | set every `recommended_size` to `None`, so every Add takes the full cap. **This is the zero-information floor for this channel** — the direct analogue of Test 1's §4.1 floor, and it answers "what if we deleted this field entirely?" |
| `size_fixed` | set every `recommended_size` to the corpus median from Step 1b — "what if we replaced the analyst's sizing with one constant?" |

`jitter_1x` is the headline cell: **it is the portfolio cost of exactly the
noise Test 4 measured**, not a hypothetical.

---

## Step 3 — the result, in Test 1's units

Report `final_value` and `max_drawdown` per cell, **naming the ruler on
every drawdown figure** (§0 of 09-05: an unlabelled drawdown is not a usable
number). Report **daily-marked** drawdown as the primary, since that is the
ruler §5.1 established as correct; session-sampled may be reported
alongside for continuity with Test 1's own table, clearly labelled.

Put the headline in the same units as Test 1 §4.2 so the two channels are
directly comparable: Test 1 found a 7.44pp lift drop costs **$24,886
(13.8%)** in the `adjacent` mode and ~**$42,700 (23.8%)** in `pessimistic`.
State plainly whether the sizing channel's measured noise costs **more or
less than** the recommendation channel's, in dollars.

## Step 4 — tier split, against the pre-registered prediction

Break every cell's result by established vs speculative exposure and state
whether the prediction above (sizing matters more for established names,
because their 35% cap leaves room for the noise to express itself, while the
15% speculative cap absorbs most of it) **held or failed**. If it failed,
say so and give the mechanism if it is visible in the data.

## Step 5 — reading (report, do not decide)

Two questions this run informs but must not settle:

1. **Is `recommendedSize` instability a real risk or an absorbed one?** If
   `jitter_1x` costs little, the field's 96% instability rate is cosmetic
   and the caps/throttle are doing their job. If it costs a lot, then the
   analyst's load-bearing channel is materially unreliable run-to-run and
   that belongs in front of the promotion gate, not buried in a field-
   stability table.
2. **Does `size_ignored` beat `control`?** If deleting the analyst's sizing
   entirely and always taking the cap performs as well or better, that is a
   significant finding about where the analyst's value actually sits —
   directly relevant to §5.2's "the entire contribution is sizing" claim,
   which it would contradict. Report it plainly either way; **do not adjust
   the claim or any spec here.**

**Explicitly out of scope:** the design idea of feeding score dispersion
into position sizing as an uncertainty signal (the `allocator_v4.py`
low-coverage/high-dispersion pattern). This run produces the number that
says whether that is worth building; it does not build or evaluate it.

---

## Report

Scope boundary: **report, do not decide.** Do not modify
`analyst_sensitivity_harness.py`, any file under `analysis/simulator/`,
`ALLOCATOR_OPERATING_MODEL.md`, `PROMOTION_GATE.md`, or `gate_ledger.json`.
Do not patch the falsy-zero defect. No DB writes; `SELECT` only.

Open with resume status, then:

> **Control reproduced: $[X] [matches Test 1's $179,944.91 / DISCREPANCY].
> Exposure: `Add` events [N] of [M] total ([X]% — the ceiling on this
> channel), [N] carrying a non-null size, [N] already clamped by cap.
> Measured `recommendedSize` noise (from Test 4 raw): [X]pp median std,
> [Y]pp max. Headline — `jitter_1x` (exactly the measured noise) costs
> **$[X] ([Y]%)** and [moves] drawdown [Z]pp (daily-marked). Compare Test
> 1's recommendation channel: $24,886 (13.8%) at the -7.44pp shock. Sizing
> channel is [more / less / comparably] expensive than the recommendation
> channel. `size_ignored` (delete the field, always take the cap): $[X]
> ([better / worse] than control by [Y]%). Tier prediction (established >
> speculative): [held / failed]. Latent falsy-zero defect: [confirmed not
> live / found live on N events]. $0 API spend confirmed.**

Flag plainly: any cell whose seed spread is wide enough that its median is
not a meaningful summary; any result that contradicts a figure published in
Test 1, Test 4 or state-of-play (name the figure and the file); and whether
`size_ignored` beating `control` would, if real, require §5.2's "the
analyst's entire contribution is sizing" to be requoted.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no
  Linux package managers or path assumptions.
- **No LLM calls. No DB writes.** `SELECT` only, plus reads of Test 4's
  saved `raw/*.json`.
- Do not modify Test 1's harness — write a new driver alongside it.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — file, manifest path, JSON
  key, or table/column. Every drawdown must name its ruler.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
