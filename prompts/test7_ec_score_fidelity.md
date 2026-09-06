# Test 7 — does EC's transcript text move the evaluator's score?

`wrap-ups/ec_transcript_fidelity_benchmark_1-out.md` established EC's text
fidelity (1.03% truncation, GOOGL fixed by a `GOOG` alias, SPWR unusable).
That measured **text similarity**, not **score similarity** — the open
question this test answers: for the same call, does scoring EC's text
instead of the DB's text change what the evaluator concludes, once you
account for the evaluator's own already-measured run-to-run noise?

**Read, in full, before starting:** `wrap-ups/ec_transcript_fidelity_benchmark_1-out.md`,
`wrap-ups/test4-analyst-noise-floor-out.md`, `docs/architecture/PROMOTION_GATE.md`
§6 ("how much is noise"), and `CLAUDE.md`'s analyst/allocator firewall section.

## Why this reuses Test 4 instead of measuring noise from scratch

Test 4 already ran 50 transcripts × 5 evaluator calls each (250 calls, real
spend, ~$23) specifically to characterize the evaluator's own instability —
**19.5% of (transcript, field) combinations are unstable across identical
repeated runs on identical DB text**, and that instability is wildly uneven
by tier (small/micro std 14.34pp vs large/mid ~0pp on the hit-rate metric).
Re-deriving a noise floor here would waste budget on something already paid
for. **34 of Test 4's 50 sampled transcripts are also in the EC benchmark's
195 classified cells** (cross-referenced by `transcript_id` — see Step 0).
For those 34, Test 4's `analysis/test4_noise_floor/raw/<id>.json` already
holds 5 real DB-side evaluator runs. This test spends new calls **only on
the EC-side** for a chosen subset of that overlap, and compares against
Test 4's existing DB-side distribution — half the cost of a from-scratch
paired comparison, using an already-validated baseline instead of a new one
built on 2-3 runs.

## This is a targeted stress test, not a representative sample

**Do not generalize this test's result to "EC is safe/unsafe for all 195
transcripts."** The cells below are deliberately chosen at the extremes —
lowest text similarity, confirmed truncation, confirmed ASR garbling — to
ask "does the score survive the worst cases we found," not "what's the
average effect." A clean result here is reassuring; it is not a
statistical guarantee about the other ~185 cells that looked fine on text
alone.

## Cell selection (fixed, reported, not drawn — see rationale per cell)

**Tier A — reuse Test 4's DB-side runs, spend only on EC-side (4 cells, one
per tier, chosen for lowest similarity ratio within tier among the 34-cell
overlap, to stress-test the cases where EC's text looked most different):**

| transcript_id | ticker | call_date | tier | EC similarity_ratio | EC classification |
|---|---|---|---|---|---|
| 16 | AMPX | 2025-08-07 | small_micro | 0.0056 | summarized_but_complete |
| 287 | FSLR | 2023-02-28 | mid | 0.0687 | summarized_but_complete |
| 220 | TSLA | 2022-10-19 | megacap | 0.0493 | summarized_but_complete |
| 348 | QS | 2024-04-24 | small_micro | 0.6220 | matches_closely (control — highest-similarity cell in the overlap, expected to show the least movement) |

**Tier B — fresh runs on both sides (3 named, load-bearing cells from the
EC wrap-up's own flags — not in the Test 4 overlap, so no baseline to
reuse):**

| transcript_id | ticker | call_date | Why this cell |
|---|---|---|---|
| 370 | RUN | 2022-Q3 (see wrap-up for exact call date) | **Confirmed truncated** — EC's text is missing the DB's full operator sign-off. If any cell should move the score, it's this one. |
| 154 | AAPL | 2022Q4-bucket / vendor 2023Q1 | **Confirmed truncated** — same failure mode, different ticker/tier. |
| 249 | AMD | 2022-Q2 | **ASR-garbled but content-complete** ("does conclude" → "does include"). Tests whether transcription noise on procedural language also corrupts extraction of substantive content elsewhere in the same transcript. |

**Tier C — optional, off by default (+1 cell, +6 calls):**

| transcript_id | ticker | call_date | Why optional |
|---|---|---|---|
| 757 | GOOGL (via `GOOG` alias) | 2026-07-22 | Already confirmed near-identical at the text level (tails matched almost word-for-word) in the alias-verification step. Lower expected information value than Tiers A/B; include only if budget allows. |

**Call budget, default (Tiers A+B only):** Tier A = 4 cells × 3 EC-side runs
= 12 calls. Tier B = 3 cells × 2 sides × 3 runs = 18 calls. **Total: 30
calls.** At Test 4's own observed rate (~19,178 tokens/call, ~$0.092/call
average) that is **≈$2.76** — a real but small number; state it plainly
rather than treating "LLM calls" as uniformly expensive. Tier C adds 6
calls / ≈$0.55 if enabled.

## Ground rules

- **This spends real Anthropic API dollars against `ANTHROPIC_API_KEY`.**
  Every other prompt in this chain (Test 3, both vendor benchmarks) banned
  LLM calls because a concurrent run (`test6-look-ahead-prohibition`) was
  under a spend ceiling. **Do not run Step 2 without first checking whether
  that ceiling still applies** — if `test6` or any other spend-bearing run
  is active, stop and ask before spending anything here.
- **Analyst/allocator firewall, unchanged.** Single-transcript evaluation
  only, `docs/EVALUATION_PROMPT.md` used exactly as found, no portfolio
  context passed, no `Analysis` table writes, ever.
- **Do not modify `EVALUATION_PROMPT.md`, `PROMOTION_GATE.md`, or
  `gate_ledger.json`.** This is a diagnostic, not a gate run.
- Reuse `analysis/test4_noise_floor.py`'s own `get_model_version()`,
  `get_prompt_header()`, and `parse_structured()` (import, don't
  reimplement) so Tier A's comparison is byte-for-byte apples-to-apples
  with the cached baseline. Same `max_tokens=8192`, `temperature=0`,
  single-user-message call shape.
- EC text comes from the already-saved
  `analysis/ec_fidelity_benchmark_1/raw/*.json` (Tiers A/B/C) — reconstruct
  with `vendor_payload_to_text_and_turns()` from
  `analysis/ec_fidelity_benchmark_1/driver.py` (import, don't reimplement).
  **Zero new vendor calls in this test.**
- DB text via direct `SELECT` on `Transcript.rawText` — no writes.

## Step −1 — resume protocol

`run_id` **`test7-ec-score-fidelity`**, state in
`analysis/data/run_state/test7-ec-score-fidelity/`. `progress.json` before
any call. Every completed (cell, side, run_idx) triple is checkpointed
immediately to `analysis/test7_score_fidelity/raw/<transcript_id>_<side>.json`
(same shape as Test 4's raw files, `side` added as a field) so an
interruption resumes without re-spending — Test 4's own wrap-up shows this
exact resume path working across two OS-level kills.

## Step 0 — hygiene and the hard version-match gate

Clean tree, commit driver + this prompt together before any manifest, as
Test 3/AV/EC all did.

**Before Step 2 can run at all:** read `get_model_version()` and
`get_prompt_header()` right now and compare against what's recorded in
each Tier A cell's `analysis/test4_noise_floor/raw/<id>.json` (`model` and
`prompt_version_header` fields — Test 4 used `claude-sonnet-4-6` /
`v10+auto1 (auto-iterate candidate — pending gate)`). **If either differs,
stop — do not run Tier A.** A model or prompt change since Test 4 would
confound "does the vendor change the score" with "did the prompt/model
already move the score," which is exactly the kind of contamination
`PROMOTION_GATE.md` §6 exists to prevent. Tier B has no such dependency
(both sides run fresh, same call) and may proceed even if Tier A is
blocked — report both outcomes separately if this happens.

## Step 1 — build both text sides for every cell (0 API calls)

For each of the 7 (or 8, with Tier C) cells: pull DB `rawText` by
`transcript_id` (`SELECT` only) and reconstruct EC text from the saved raw
JSON via `vendor_payload_to_text_and_turns()`. Print each cell's
`(db_word_count, ec_word_count)` before any evaluator call, as a sanity
check that the right file was loaded.

## Step 2 — scoring calls (real spend, gated — see ground rules)

Tier A: 3 EC-side runs per cell, `evaluate`-equivalent call reused from
`test4_noise_floor.py`. Tier B: 3 runs per side per cell. Save every raw
response (full text + parsed `structured` + token counts) exactly as Test
4's schema does.

## Step 3 — comparison (0 new calls)

For each cell, on the **primary four fields** Test 4 already tracks
(`thesisHealth`, `recommendation`, `stumbleType`,
`mitigationCapabilityTrackRecord`) plus the two numeric sizing fields
(`recommendedSize`, `freshMoneyAllocation`):

- **Categorical fields:** the distinct value-set observed across DB runs
  vs. across EC runs. **Disjoint sets** (no shared value) = **flagged
  divergence** — the score genuinely differs and it isn't explained by the
  evaluator's own known instability. **Any overlap** = **inconclusive, not
  a clean pass** — state plainly that a shared value across two small
  samples doesn't prove equivalence, only that this test found no
  contradiction.
- **Numeric fields:** the observed range on each side. Non-overlapping
  ranges = flagged divergence; overlapping = inconclusive-not-a-pass, same
  caveat.
- **Tier A only:** additionally report each DB-side field's Test-4-recorded
  instability rate (was this exact transcript already unstable on
  identical DB text across its 5 original runs?) — a field that was
  already flipping on DB text alone before EC ever entered the picture
  cannot be blamed on the vendor if EC also flips it.

Report every field for every cell — do not average across cells into a
single pass/fail number; Tier A/B/C are three different questions
(low-similarity stress, confirmed-defect stress, confirmed-clean control)
and collapsing them would hide which one, if any, actually matters.

## Step 4 — verdict, against a rule fixed before results

| Finding | Reading |
|---|---|
| No flagged divergence on any primary field, any cell | Score robustness supports EC as a Step 6 source on the cells tested here — explicitly **not** a claim about the untested 185+ cells. No Stage 2 primary-source audit needed from this test alone. |
| Flagged divergence on a primary field, confined to Tier A/B's already-known-unstable-on-DB-alone cells (per Step 3's instability cross-check) | Cannot attribute to EC — the evaluator was already unreliable on this exact transcript before EC entered the picture. Report as inconclusive, not as a vendor defect. |
| Flagged divergence on a primary field where the DB side was stable across its own repeats (Tier A) or the DB-side repeats agree with each other (Tier B), and EC's repeats land somewhere else entirely | **Real, load-bearing finding.** Name the transcript, the field, both value-sets. This is the trigger for the Stage 2 primary-source audit discussed with Luis (check the specific disputed passage against call audio or an official IR transcript) — do not perform that audit in this run; flag it as the next step. |

State explicitly which row applies, per cell, not just in aggregate.

## Report

**Scope boundary: report, do not decide.** No `PROMOTION_GATE.md` change,
no `Analysis` table writes, no vendor decision, no Stage 2 audit performed
here — flagged as a follow-up if Step 4's third row fires on any cell.

Open with resume status and **exact dollar spend** (sum of
`input_tokens`/`output_tokens` × the account's actual per-token rate if
knowable, else the same estimate-with-caveat Test 4 used), then, per cell:

> **[ticker] [call_date] (tier [X], transcript_id [N]): DB [field] = {values
> across N runs}, EC [field] = {values across N runs}. [Divergence flagged /
> inconclusive — overlap / no divergence]. [If Tier A: DB-side already
> unstable on this field per Test 4: yes/no.]**

Then the aggregate: **[N] cells tested, [N] flagged divergences, [N]
inconclusive-not-a-pass, [N] clean.** **Bottom line: [supports EC on tested
cells / Stage 2 audit needed on: list] — not a statement about the
untested remainder of the 195-cell corpus.**

## Standing rules

- `python3`/`pip3`, zsh-compatible, no `--break-system-packages`.
- **Real Anthropic spend — confirm the spend-ceiling situation before Step
  2, every invocation, not just the first.**
- `SELECT` only on the DB. No writes to `Transcript`, `Ticker`, or
  `Analysis`. No vendor (EarningsCall) calls at all.
- Do not modify `EVALUATION_PROMPT.md`, `PROMOTION_GATE.md`,
  `gate_ledger.json`, or any completed prompt/wrap-up, including this run's
  own inputs (`test4_noise_floor/`, `ec_fidelity_benchmark_1/`) — read-only
  access to both.
- Every figure quoted names its provenance — raw JSON path, field name,
  run index.
- Report wall-clock, cells run, cells reused, calls made, tokens spent,
  estimated cost.
- Do not write a new handoff doc. This prompt in, one wrap-up out to
  `wrap-ups/test7-ec-score-fidelity-out.md`.
