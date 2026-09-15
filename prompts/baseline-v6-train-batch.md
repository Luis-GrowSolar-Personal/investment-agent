# Baseline — score v6 on the train split, via the Batch API

**Run ID:** `baseline-v6-train-batch`
**Supersedes `prompts/baseline-score-v6-on-train.md`, which was never run.**
Do not execute that file; it uses per-call synchronous scoring at full price.
**Cost: THIS RUN SPENDS REAL MONEY.** Roughly **$56** at the batch rate (50% off
this project's observed ~$0.093 per call). **Hard cap below — respect it.**
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/baseline-v6-train-batch-out.md`

**Read first:** `wrap-ups/corpus-fix-8-expand-to-150-out.md`,
`analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json`,
`analysis/data/corpus_v2/SPLIT_V5_EXPANSION.json`, and
`docs/architecture/PROMOTION_GATE.md` §3.1.

---

## 1. What this run is for

The corpus is frozen at 164 companies, 109 available for iteration, paired
threshold about 1.9 points. **Nothing has been scored.**

This run scores **v6 on the train split only** and establishes the baseline every
future candidate is compared against.

**It also answers a question nobody has been able to answer.** Everything known
about v6 — 40.4% against 39.6% for luck, calls indistinguishable from an
educated guess — was measured on 16 companies sitting at the top of 25 random
draws, four solar, four battery, three semiconductor, all moving together. That
universe is pathological.

**This is the first honest test of v6**, and both outcomes are informative:

- **v6 again lands at chance** → the prompt is the problem, not the measuring
  set, which argues for a structural rewrite rather than incremental edits.
- **v6 shows real signal** → the diagnosis changes and the $83,129 headroom
  figure needs recomputing on honest data.

---

## 2. Hard constraints

1. **Train split ONLY.** Do not score tune. **Do not touch the holdout** — it is
   locked and hashed in `PROMOTION_GATE.md` §10.
2. **Hard cap: 1,400 requests in the batch.** Count the request list **before**
   calling `create()`. With batching the money commits at submission, not per
   call, so the cap is a pre-submission check. **If the list exceeds 1,400, stop
   and report** rather than submitting a trimmed batch.
3. **Version guard before submission.** `CLAUDE.md`'s standing rule: assert the
   prompt hash against `docs/architecture/VERSION_REGISTRY.json` via
   `analysis/version_guard.py`, or declare the candidate explicitly. **Guard
   fails → stop, submit nothing.**
4. **Pin and record the model.** Every score carries prompt version **and** model
   version. If the registered v6 model is retired and a substitute is needed,
   **that is a finding to report before submitting, not a note afterward.**
5. **No allocator, no simulator, no portfolio.** This run scores transcripts and
   grades calls. Nothing runs through the trend layer or the allocator.
6. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step −1 — resume protocol, built around the batch id

State in `analysis/data/run_state/baseline-v6-train-batch/`. **Write
`progress.json` as the very first action.**

**The batch id is the recovery key.** Results persist for **29 days** and are
retrievable by id, so once a batch is submitted the money cannot be lost — a
dead session re-reads the results.

Therefore:

- **Write `batch_id` to `progress.json` and commit it the instant `create()`
  returns**, before polling anything. This is the single most important line in
  the run.
- On resume: if `batch_id` exists, **do not submit anything.** Retrieve that
  batch and continue from wherever results collection left off.
- Append each result to `scores.jsonl` as it streams, keyed by `custom_id`.
  Skip any `custom_id` already present.

---

## 4. Step 0 — hygiene, guard, protocol

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any result, as its own commit.

**0b. Run the version guard.** Record the prompt hash, the registry's expected
hash, and the result. **Stop on mismatch.**

**0c. Register the scoring protocol** in
`analysis/data/corpus_v2/SCORING_PROTOCOL.json`, dated, before submission:

- the split scored (train), its company list, and the manifest sha256;
- prompt version and hash;
- **the model version, pinned**;
- **the grading field: `per_call_rec` — the analyst's own call, not
  `final_action`.** Grading the post-trend-layer action would let a trend-layer
  change read as a prompt improvement; Stage D hit exactly this;
- the eval-cache path from Step 3;
- the request cap.

---

## 5. Step 1 — fetch the train transcripts

**Do not write new vendor code. It already exists and is proven.** A prior
session asked this question and concluded nothing in the repo fetches transcript
text. That is incorrect, and building fresh would repeat a bug this project has
already found the hard way.

### Reuse, do not rewrite

`analysis/ec_fidelity_benchmark_1/driver.py` fetched **198 transcripts**
successfully and its raw payloads are still on disk under
`analysis/ec_fidelity_benchmark_1/raw/`. Import from it read-only, exactly as
`analysis/test7_score_fidelity.py` already does:

```python
from driver import vendor_get, vendor_payload_to_text_and_turns
```

| What | Where | Detail |
|---|---|---|
| Endpoint | `transcript` | params `{exchange, symbol, year, quarter, level}` |
| Base URL | `https://v2.api.earningscall.biz` | key `ECB_API_KEY`, passed as `apikey` |
| Rate limiting | `MIN_SPACING_SECONDS = 3.5` | 20/min is 3s; 3.5 is the margin. Already enforced inside `vendor_get`. |
| Call counting | inside `vendor_get` | counts every call into `progress` |
| Error handling | inside `vendor_get` | raises on 429 and 401 rather than looping |

**The gotcha that makes rewriting dangerous.** At level 2 the payload's
`speakers[]` entries carry an anonymous code (`spk06`) and text — the real names
are **not** inline. They live in a separate top-level `speaker_name_map_v2`
dict keyed by that code. An earlier version of this project assumed inline
`speaker_info{name,title}`, which does not exist, and silently read **0 of 195**
speaker names before manual verification caught it.
`vendor_payload_to_text_and_turns()` already handles this correctly. New code
would very likely not.

**Two more behaviours to preserve, both already implemented:**

- **Level fallback.** If level 2 returns 402 or 403, fall back to level 1 **once
  for the whole run** and record a finding — do not retry per call.
- **Coverage-miss detection.** A 404, or a payload carrying neither `speakers`
  nor `text`, is a coverage miss. Record it; do not store an empty transcript.

### Fiscal quarters, not calendar months

The vendor is keyed by **fiscal** year and quarter. **Never derive a quarter
label from the call month** — that was a real bug in the Alpha Vantage run.
Resolve each call through the `events` endpoint and match the manifest's call
date to the vendor's `conference_date` **within ±3 days**, the tolerance the
fidelity driver already uses. Fiscal and calendar diverge for several corpus
companies, Apple and Nvidia among them.

### Check what is already on disk first

`analysis/ec_fidelity_benchmark_1/raw/` holds 198 payloads named
`<TICKER>_<YEAR>Q<N>_id<transcript_id>.json`. **Cross-reference the train split
against these before fetching anything** and reuse every match. Report how many
calls were served from disk versus fetched fresh — it is free coverage and it
also cross-checks that the new fetch path produces payloads of the same shape.

### Validate on three before pulling the rest

Fetch **three** transcripts, then inspect them by eye before the bulk run:

- word count in a plausible range for an earnings call — a few thousand at
  minimum. **A suspiciously short transcript is a truncation bug, not a short
  call**;
- both prepared remarks and Q&A present, not just one;
- real speaker names resolved, not `spk06` codes — this is the check that
  catches the `speaker_name_map_v2` failure;
- company and date match what the manifest asked for.

**If any of the three fails, stop and report.** Do not pull 1,250 transcripts
through an unvalidated path.

### Storage

Write to files, not the database:
`analysis/data/corpus_v2/transcripts/<TICKER>/<call_date>.json`, holding the raw
vendor payload **and** the derived text, plus the vendor params used and a
timestamp.

Files rather than the `Transcript` table for the same reason scores go to a
version-stamped directory: the existing DB rows are the source of the provenance
problem that started this whole investigation. Keep the new corpus
self-describing.

**Fetching is not scoring.** If the fetch consumes the session, stop, commit the
transcripts, mark scoring `pending`. The transcripts are the durable asset —
they are fetched once and reused by every future scoring round.

---

## 6. Step 2 — the five-call pilot *(do not skip)*

**Batch request validation happens asynchronously.** A malformed request shape
fails 1,250 times instead of once, and you find out an hour later.

So before submitting anything: score **five** transcripts through the **ordinary
synchronous Messages API**, with the exact request shape the batch will use.
Confirm:

- the response parses into the structured score the scorer expects;
- `per_call_rec` is populated and lands in the expected value space;
- **the real per-call cost**, from the usage figures returned.

**Report the measured cost against the $0.093 assumption.** That figure came
from a 30-call sample and drives the entire programme budget; this is a real
measurement of it. **If it differs by more than about 30%, stop and report
before submitting the batch** — the programme's cost model is wrong and that
decision is Luis's.

Pilot cost: roughly 50 cents. These five results are kept and counted toward the
corpus, not thrown away.

---

## 7. Step 3 — submit the batch

One batch, all remaining train calls. The limits are 100,000 requests and 256 MB,
so 1,250 fits comfortably.

```python
Request(
    custom_id=f"{ticker}_{call_date}",          # e.g. NVDA_2023-05-24
    params=MessageCreateParamsNonStreaming(
        model=PINNED_MODEL,
        max_tokens=<as pinned in the protocol>,
        system=[
            {"type": "text", "text": EVAL_PROMPT_V6,
             "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": transcript_text}],
    ),
)
```

- **`custom_id` must match `^[a-zA-Z0-9_-]{1,64}$`.** Ticker plus ISO date fits;
  confirm no company violates it before submitting.
- **Put the evaluation prompt in a cached system block**, identical across every
  request, so the caching discount stacks on the batch discount. Treat cache hits
  as a bonus — they are best-effort — and report the hit rate from the usage
  figures rather than assuming one.
- Commit the batch id immediately, per Step −1.

Then poll `processing_status` until `ended`. Most batches finish within an hour;
the guarantee is 24 hours.

**Results come back out of order — match on `custom_id`, never position.**
Record every `errored` and `expired` result with its id; do not silently drop
them.

---

## 8. Step 4 — write the scores where they carry their own provenance

Write results into a **version-stamped eval cache directory** —
`analysis/data/evals/v6_<model>/` — the layout `analyst_direct_scorer.py` was
built to read.

**This fixes the problem that started the whole investigation.** The existing
corpus lives as DB rows with no version column, which is why 153 of 362 rows have
unverifiable provenance and why `analysis/data/evals/` has been sought and found
absent three times. **Do not write these into the `Analysis` table.**

Record per call: ticker, call date, structured score, prompt version, model
version, batch id, timestamp.

---

## 9. Step 5 — grade, and report the baseline

Run `analysis/analyst_direct_scorer.py` against the new eval cache. Report on the
train split:

- observed accuracy, expected-by-luck accuracy, and the gap;
- **balanced accuracy**, against the 33.3% a random three-way guesser gets;
- per-answer recall — beat the market, lagged, moved with it — beside each
  outcome's base rate;
- a **95% range** on every figure from the ticker-block bootstrap, and whether it
  includes zero;
- the always-bullish-guesser and always-flat-guesser figures alongside, labelled
  as such, for continuity with the old record.

**Then the comparison that matters:**

| | old 16-company corpus | this corpus |
|---|---|---|
| observed accuracy | 40.4% | |
| expected by luck | 39.6% | |
| gap | 0.8 points | |
| balanced accuracy | 31.3% | |
| bullish recall | 72.9% | |
| bearish recall | 13.9% | |

**Say plainly whether v6's near-chance performance replicates on a representative
universe, or whether the old universe was the problem.** If the gap's 95% range
excludes zero here where it did not before, that is the headline.

---

## 10. Step 6 — the report

**Scope boundary: report, do not decide.** This run promotes nothing and
commissions no further scoring.

Short. Plain-language summary to the project instructions' language rules, then
the comparison table, the intervals, and the eval-cache path future runs read.

**Report actual spend** — batch usage figures, cache hit rate, effective per-call
cost — against the $56 estimate, and state the revised programme budget that
follows. Also report any `errored` or `expired` requests and whether they need
re-submitting.

**Limitations to state, not argue past:**

- Train split only. Tune and holdout unscored.
- The corpus over-represents failures by construction.
- The existing 16 are hindsight-selected and excluded from headline figures.
- Sector-relative grading (F2) is unresolved; everything here is benchmarked
  against the broad market.

---

## 11. Git — Code runs these, in this order

1. Confirm a clean tree; record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit.**
3. Commit the scoring protocol and transcripts **before** submitting the batch.
4. **Commit `batch_id` the moment it exists**, ahead of any polling.
5. Commit scores and run state as results stream in.
6. Commit the wrap-up.
7. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 12. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed and the batch id.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the pilot's per-call cost differing materially from
  $0.093, the registered v6 model being unavailable, or cache hits coming in far
  below expectation.
- **Note anything contradicting this prompt's premises.** The repo, the registry,
  the vendor and the API outrank it.
