# Baseline — score v6 on the tune split, via the Batch API

**Run ID:** `baseline-v6-tune-batch`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/baseline-v6-tune-batch-out.md`
**Cost: THIS RUN SPENDS REAL MONEY.** Roughly **$47** at the batch rate, based on
the train run's *measured* $0.0380 per call over 1,240 calls. **Hard cap below.**

**Read first:** `prompts/baseline-v6-train-batch.md` (this run is its twin — same
machinery, different split), `wrap-ups/baseline-v6-train-batch-out.md`,
`wrap-ups/scorer-price-cache-backfill-out.md`,
`analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json`,
`analysis/data/corpus_v2/CORPUS_MANIFEST_V7.json`, and
`docs/architecture/PROMOTION_GATE.md` §3.1.

---

## 1. What this run is for

v6 has been scored on **train**: 1,236 gradable calls across 56 of 57 companies,
30.3% observed against 27.8% expected by luck, a gap of **+2.48 points** whose
95% range is −0.06 to +5.08.

This run scores **v6 on the tune split** and produces the second of the two
numbers every future candidate needs.

**Two reasons it exists, and the first is the one that matters.**

1. **A comparison needs both arms on the same ground.** When a candidate prompt
   survives train and moves to tune, it must be compared against v6 *on tune*.
   v6's train figure cannot stand in — different companies, different number.
2. **The model will not be available forever.** Every figure above was scored
   with `claude-sonnet-4-6`. v6's *original* 40.4% was measured on
   `claude-sonnet-4-20250514`, retired 2026-06-15, which is precisely why it is
   unusable today and why a model confound sits on every current figure. Scoring
   v6 on tune now, on the same model as its train score, keeps the pair
   comparable. Deferring risks repeating a failure this project has already had.

**What this run is NOT.** It is not a second opinion on the +2.48. It is not a
promotion decision. It commissions nothing further.

---

## 2. Hard constraints

1. **Tune split ONLY.** The 54 companies in
   `SPLIT_V7_RESERVE_REPLACEMENTS.json` → `tune`. **Do not score train again**
   — it is already scored and committed. **Do not touch the holdout**; it is
   locked and hashed in `PROMOTION_GATE.md` §10. Assert zero intersection
   between the request list and both other splits *before* submitting, and
   record the assertion.
2. **Hard cap: 1,400 requests.** Count the list **before** `create()`. Money
   commits at submission. **List exceeds 1,400 → stop and report**, do not
   submit a trimmed batch.
3. **Version guard before submission.** Assert the prompt hash against
   `docs/architecture/VERSION_REGISTRY.json` via `analysis/version_guard.py`.
   **Guard fails → stop, submit nothing.**
4. **Same prompt, same model as the train run.** v6, `claude-sonnet-4-6`. This
   run's entire value is comparability. **If that model is unavailable, STOP and
   report before submitting** — do not substitute. A tune score on a different
   model than the train score answers no question.
5. **No allocator, no simulator, no portfolio.** Transcripts in, graded calls
   out. Nothing through the trend layer.
6. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/baseline-v6-tune-batch/`. **Write
`progress.json` as the very first action.**

**The batch id is the recovery key.** Results persist 29 days and are retrievable
by id, so once submitted the money cannot be lost.

- **Write `batch_id` to `progress.json` and commit it the instant `create()`
  returns**, before polling. Single most important line in the run.
- On resume: if `batch_id` exists, **do not submit anything.** Retrieve that
  batch and continue collecting.
- Append each result to `scores.jsonl` keyed by `custom_id`; skip ids already
  present.

---

## 4. Step 0 — hygiene, guard, protocol

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any result.

**0b.** Run the version guard. Record prompt hash, registry's expected hash,
result. Stop on mismatch.

**0c. Register the scoring protocol** at
`analysis/data/corpus_v2/SCORING_PROTOCOL_TUNE.json` — **a new file; do not
overwrite `SCORING_PROTOCOL.json`, which records the train run.** Dated, before
submission, carrying:

- split scored (`tune`), its 54-company list, manifest sha256, split sha256;
- prompt version and hash;
- **model version, pinned**, and an assertion it equals the train run's
  `model_version_pinned`;
- **grading field: `per_call_rec`** — the analyst's own call, never
  `final_action`. Grading the post-trend-layer action lets a trend-layer change
  read as a prompt improvement; Stage D hit exactly this;
- the eval-cache path from Step 4;
- the request cap and the split-disjointness assertion from §2.1.

---

## 5. Step 1 — the three pre-checks *(do this before fetching anything)*

The train run lost calls three separate times to the same failure shape: a
check or artifact built against one set of keys while the consumer read another.
Three specific instances are already visible on the tune side. **Resolve all
three and report them before Step 2.**

### 5a. Ticker aliases — GOOGL is in tune

`analysis/data/corpus_v2/TICKER_ALIASES.json` records that the vendor keys
Alphabet's transcripts to **GOOG**, not GOOGL. GOOGL is in the tune split. On
train this class of problem cost 46 calls, via `ANTM`/`ELV` and `VIAC`/`PARA`.

Sweep **all 54 tune tickers** against the alias table and against a vendor
`events` probe. For every alias found, record the manifest ticker, the working
vendor symbol, and which of the two the eval filenames will use. **Then write
both keys into the price cache** (Step 5b), as `scorer-price-cache-backfill`
had to do retroactively.

### 5b. Price-cache coverage — WOLF is missing

`analysis/data/corpus_v2/scorer_price_cache_v1.json` holds 172 tickers and
covers **53 of the 54** tune companies plus SPY. **`WOLF` is absent.**

Determine which it is and act accordingly:

- a straightforward fetch gap → backfill it with
  `analysis/scorer_price_cache_backfill_driver.py`;
- a terminal-value case → grade it under **A6**
  (`PREREGISTRATION_FIX.json` → `A6_terminal_value_grading`), which grades
  wiped-out equity at −100% without needing prices.

**Do not guess which.** Check the company's actual status and say which rule you
applied and why.

**Then verify coverage against the file the scorer actually opens.** The scorer
reads whatever `--price-cache` points at; A9 previously verified coverage
against `corpus_v2_price_cache.json` while the consumer read
`analysis/data/price_cache.json`, and the mismatch was invisible for weeks.
State the path you verified and the path the scoring command will pass — **they
must be the same string.**

### 5c. Confirm the coverage guard is live

`analysis/analyst_direct_scorer.py` now refuses to report a score when calls go
missing (commit on this branch, 2026-09-15): >1% of in-scope files yielding no
prediction, or missing price data either >5% of the corpus or concentrated in
any ticker losing >50% of its calls.

Confirm it is present and passing on the existing train eval cache before
relying on it here. **Do not pass `--allow-partial-coverage` in this run.** If
the guard fires on tune, that is a finding to fix, not to override.

---

## 6. Step 2 — fetch the tune transcripts

**Nothing is on disk.** All 56 transcript directories under
`analysis/data/corpus_v2/transcripts/` are train companies; **0 of 54 tune
companies have any.** Budget for ~1,238 transcript fetches plus events
resolution.

**Do not write new vendor code.** Import read-only from
`analysis/ec_fidelity_benchmark_1/driver.py`, exactly as
`analysis/test7_score_fidelity.py` does:

```python
from driver import vendor_get, vendor_payload_to_text_and_turns
```

| What | Where | Detail |
|---|---|---|
| Endpoint | `transcript` | params `{exchange, symbol, year, quarter, level}` |
| Base URL | `https://v2.api.earningscall.biz` | key `ECB_API_KEY`, passed as `apikey` |
| Rate limiting | `MIN_SPACING_SECONDS = 3.5` | enforced inside `vendor_get` |
| Error handling | inside `vendor_get` | raises on 429 and 401 rather than looping |

**The gotcha that makes rewriting dangerous.** At level 2 the payload's
`speakers[]` entries carry an anonymous code (`spk06`) and text — real names are
**not** inline. They live in a separate top-level `speaker_name_map_v2` dict
keyed by that code. An earlier version of this project assumed inline
`speaker_info{name,title}` and silently read **0 of 195** speaker names.
`vendor_payload_to_text_and_turns()` handles this correctly.

**Preserve both existing behaviours:** level-2 → level-1 fallback **once for the
whole run** on 402/403, recorded as a finding, never retried per call; and
coverage-miss detection — a 404, or a payload with neither `speakers` nor
`text`, is a miss to record, never an empty transcript to store.

**Fiscal quarters, not calendar months.** Resolve each call through the `events`
endpoint and match the manifest call date to `conference_date` within **±3
days**. Never derive a quarter label from the call month — that was a real bug in
the Alpha Vantage run.

**Timing.** At 3.5s spacing, ~1,238 fetches is **at least 72 minutes** of
wall-clock before any events calls. This will likely span sessions. Commit
transcripts as they land; they are the durable asset and are reused by every
future scoring round.

### Validate on three before pulling the rest

Fetch **three**, inspect by eye, then continue:

- word count plausible for an earnings call — **a suspiciously short transcript
  is a truncation bug, not a short call**;
- prepared remarks *and* Q&A present, not one or the other;
- real speaker names resolved, not `spk06` codes — this is the
  `speaker_name_map_v2` check;
- company and date match the manifest.

**Any of the three fails → stop and report.** Do not pull 1,238 transcripts
through an unvalidated path.

**Storage:** `analysis/data/corpus_v2/transcripts/<TICKER>/<call_date>.json`,
holding the raw vendor payload, the derived text, the vendor params used, and a
timestamp. Files, not the `Transcript` table — the DB rows are the source of the
provenance problem that started this investigation.

---

## 7. Step 3 — pilot, then submit

**Pilot (do not skip).** Batch request validation is asynchronous: a malformed
shape fails 1,238 times and tells you an hour later. Score **five** transcripts
through the ordinary synchronous Messages API with the exact request shape the
batch will use. Confirm the response parses into the structured score, that
`per_call_rec` is populated and in the expected value space, and **the real
per-call cost** from the usage figures.

**Compare measured cost against the train run's $0.0380.** Differs by more than
~30% → stop and report before submitting.

**Submit one batch** of all remaining tune calls:

```python
Request(
    custom_id=f"{ticker}_{call_date}",          # e.g. GOOG_2023-04-25
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

- **`custom_id` must match `^[a-zA-Z0-9_-]{1,64}$`** — confirm for all 54 before
  submitting.
- **Use the working vendor symbol from 5a in `custom_id`**, and make sure the
  price cache carries that same key. This is the exact pairing that broke on
  train.
- Cached system block identical across requests so the caching discount stacks
  on the batch discount; report the hit rate from usage figures rather than
  assuming one.
- Commit the batch id immediately, per Step −1.

Poll `processing_status` until `ended`. **Results return out of order — match on
`custom_id`, never position.** Record every `errored` and `expired` result with
its id; never silently drop them.

---

## 8. Step 4 — write scores where they carry their own provenance

Write into a version-stamped eval cache **separate from train's**:
`analysis/data/evals/v6_claude-sonnet-4-6_tune/`.

**Do not write into `analysis/data/evals/v6_claude-sonnet-4-6/`** — that holds
the train scores, and mixing the splits in one directory would make every future
`--eval-dir` run silently score both. **Do not write into the `Analysis`
table.**

Record per call: ticker, call date, structured score, prompt version, model
version, batch id, timestamp.

---

## 9. Step 5 — grade, and report the tune baseline

Run `analysis/analyst_direct_scorer.py` against the new eval cache, passing the
price cache path verified in 5b. The coverage guard must pass without
`--allow-partial-coverage`.

Report on tune:

- observed accuracy, expected-by-luck accuracy, and the gap;
- **balanced accuracy**, against the 33.3% a random three-way guesser gets;
- per-answer recall — beat the market, lagged, moved with it — beside each
  outcome's base rate;
- a **95% range** on every figure from the ticker-block bootstrap, and whether it
  includes zero;
- the always-bullish-guesser and always-flat-guesser figures alongside, labelled
  as such.

**Then the comparison that matters:**

| | train (56 companies) | tune (54 companies) |
|---|---|---|
| gradable calls | 1,236 | |
| observed accuracy | 30.3% | |
| expected by luck | 27.8% | |
| gap | +2.48 points | |
| 95% range on the gap | −0.06 to +5.08 | |
| balanced accuracy | 35.5% | |
| bullish recall | 38.2% | |
| bearish recall | 11.2% | |
| neutral recall | 57.1% | |
| always-bullish guesser | 32.8% | |
| always-flat guesser | 22.2% | |

**State plainly whether the +2.48 replicates on companies v6 has never seen.**
Three outcomes, all informative, and say which one it is in one sentence:

- **holds, range still spans zero** → v6 is near chance on both halves; that is
  now the settled baseline and the ruler is trustworthy;
- **holds and the range excludes zero on the pooled 110 companies** → v6 has a
  small real edge, and the $83,129 headroom figure needs recomputing;
- **collapses toward zero** → the train +2.48 was a quirk of those 57 companies,
  and any future candidate must clear a bar set by tune, not by train.

---

## 10. Step 6 — the report *(this is the deliverable)*

**Scope boundary: report, do not decide.** This run promotes nothing and
commissions no further scoring.

Short, plain language, to the project instructions' language rules. Lead with the
finding, not the method. Anchor every percentage to what it is a percentage of.
Then the comparison table, the intervals, and the eval-cache path future runs
read.

**Report actual spend** — batch usage figures, cache hit rate, effective per-call
cost — against the $47 estimate, and the revised programme budget that follows.
Report any `errored` or `expired` requests and whether they need re-submitting.

**Report the three pre-checks from Step 1 explicitly**: aliases found, WOLF's
disposition and the rule applied, and whether the coverage guard fired.

**Limitations to state, not argue past:**

- Tune split only. Holdout remains locked and unscored.
- The corpus over-represents failures by construction.
- **The model confound stands.** `claude-sonnet-4-6` is not the model v6's
  original 40.4% was measured on. Any weakness *or* any positive gap may be the
  model rather than the prompt, and the two cannot be separated with available
  data. State this; do not argue around it.
- Sector-relative grading (F2) unresolved; everything benchmarked against the
  broad market.

**Stopping is permitted only after this report exists**, or at one of the
explicit stop points above (guard failure, model unavailable, pilot cost
divergence, validation failure, cap exceeded). A fetch that consumes the session
is not a stop: commit the transcripts, mark scoring `pending`, and record exactly
where to resume.

---

## 11. Git — Code runs these, in this order

1. Confirm a clean tree; record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit.**
3. Commit the pre-check results, scoring protocol, and transcripts **before**
   submitting the batch.
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
  stop.** Most likely here: an alias beyond GOOGL, WOLF's disposition differing
  from either option in 5b, per-call cost diverging from $0.0380, or the
  coverage guard firing on a cause not anticipated above.
- **Note anything contradicting this prompt's premises.** The repo, the registry,
  the vendor and the API outrank it.
