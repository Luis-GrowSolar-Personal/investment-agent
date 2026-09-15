# Baseline — score v6 on the train split

**Run ID:** `baseline-v6-train`
**Cost: THIS RUN SPENDS REAL MONEY.** Roughly **$117** in Anthropic API at this
project's observed ~$0.093 per call. **Hard cap below — respect it.**
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/baseline-score-v6-on-train-out.md`

**Read first:** `wrap-ups/corpus-fix-8-expand-to-150-out.md`,
`analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json`,
`analysis/data/corpus_v2/SPLIT_V5_EXPANSION.json`, and
`docs/architecture/PROMOTION_GATE.md` §3.1.

---

## 1. What this run is for

The corpus is frozen at 164 companies, 109 available for iteration, with a
paired threshold of about 1.9 points. **Nothing has been scored.**

This run scores **v6 on the train split only** and establishes the baseline every
future prompt candidate is compared against.

**It also answers a question nobody has been able to answer.** Everything known
about v6 — that it scores 40.4% against 39.6% for luck, that its calls are
indistinguishable from an educated guess — was measured on 16 companies that sat
at the top of 25 random draws, four solar, four battery, three semiconductor,
all moving together. That universe is pathological.

**This is the first honest test of v6.** Both outcomes are informative:

- **v6 again lands at chance** on a representative universe → the problem is the
  prompt, not the measuring set, and that argues for a structural rewrite rather
  than incremental edits.
- **v6 shows real signal** → the diagnosis changes, and the $83,129 headroom
  figure needs recomputing on honest data.

Either way it shapes what the first candidate should be.

---

## 2. Hard constraints

1. **Train split ONLY.** Do not score tune. **Do not touch the holdout** — it is
   locked, hashed in `PROMOTION_GATE.md` §10, and not to be scored during
   iteration.
2. **Hard spend cap: 1,400 scoring calls.** Count every call. **Stop at the cap
   and report**, even mid-company. Do not raise it. No automatic retries that
   could multiply spend — a failed call is logged and skipped, not retried in a
   loop.
3. **Version guard before call one.** `CLAUDE.md`'s standing rule: assert the
   prompt hash against `docs/architecture/VERSION_REGISTRY.json` via
   `analysis/version_guard.py`, or declare the candidate explicitly. **If the
   guard fails, stop. Do not score.**
4. **Pin and record the model.** Every score carries the prompt version **and**
   the model version. A comparison where the model differs is not a prompt
   comparison. If the registered v6 model is retired and a substitute is used,
   **that is a finding to report before scoring, not a detail to note after.**
5. **No allocator, no simulator, no portfolio.** This run scores transcripts and
   grades calls. Nothing runs through the trend layer or the allocator.
6. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step −1 — resume protocol, and why it matters more here

State in `analysis/data/run_state/baseline-v6-train/`. **Write `progress.json`
as the very first action.**

**This is the first run in the project that loses money if it restarts from
zero.** Therefore:

- **Flush after every single call**, not every company: append the scored result
  to `scores.jsonl` immediately, keyed by `(ticker, call_date)`.
- On resume, **skip any call already present in `scores.jsonl`.** Never re-score
  a call that has a stored result.
- Track `calls_used_total` in `progress.json` and update it per call.

A killed session must lose at most one call.

---

## 4. Step 0 — hygiene, guard, and the scoring protocol

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any result, as its own commit.

**0b. Run the version guard.** Record the prompt hash, the registry's expected
hash, and the result. **Stop on mismatch.**

**0c. Register the scoring protocol** in
`analysis/data/corpus_v2/SCORING_PROTOCOL.json`, dated, before call one:

- the split scored (train), its company list, and the manifest sha256 it came
  from;
- the prompt version and its hash;
- **the model version, pinned**;
- **the grading field: `per_call_rec` — the analyst's own call, not
  `final_action`.** Grading the post-trend-layer action would let a trend-layer
  change read as a prompt improvement; Stage D hit exactly this;
- where scores are written (Step 2);
- the spend cap.

---

## 5. Step 1 — fetch the train transcripts

Pull transcripts for the train companies from the vendor. **Throttle to 20 calls
per minute** and back off on errors. **Do not use the vendor's SDK** — it retries
aggressively. Expect roughly an hour of wall clock.

Store them so they never need fetching again. Record the count and any call the
vendor could not supply.

**Fetching is not scoring.** If the fetch consumes the session, stop there,
commit the transcripts, and mark scoring `pending`. The transcripts are the
durable asset.

---

## 6. Step 2 — score v6

Score each train transcript with v6, writing results into a **version-stamped
eval cache directory** — `analysis/data/evals/v6_<model>/`, the layout
`analyst_direct_scorer.py` was built to read.

**This fixes a problem that started the whole investigation.** The existing
corpus lives as DB rows with no version column, which is why 153 of 362 rows
have unverifiable provenance and why `analysis/data/evals/` has been sought and
found absent three times. **Scores written to a version-stamped directory carry
their own provenance.** Do not write these into the `Analysis` table.

Record per call: ticker, call date, the structured score, prompt version, model
version, and timestamp.

---

## 7. Step 3 — grade, and report the baseline

Run `analysis/analyst_direct_scorer.py` against the new eval cache. Report, on
the train split:

- observed accuracy, expected-by-luck accuracy, and the gap between them;
- **balanced accuracy** — the average of the three per-answer hit rates, against
  the 33.3% a random three-way guesser gets;
- per-answer recall — beat the market, lagged, moved with it — beside each
  outcome's base rate;
- a **95% range** on every figure, from the ticker-block bootstrap, and whether
  each includes zero;
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

**Say plainly whether v6's near-chance performance replicates on a
representative universe, or whether the old universe was the problem.** If the
gap's 95% range excludes zero here where it did not before, that is the
headline.

---

## 8. Step 4 — the report

**Scope boundary: report, do not decide.** This run promotes nothing and
commissions no further scoring.

Short. Plain-language summary to the project instructions' language rules, then
the comparison table, the intervals, the spend, and the eval-cache path future
runs will read.

**Report actual spend** — calls made × observed rate — against the $117 estimate,
and say whether the $0.093-per-call figure held. That figure came from a 30-call
sample and drives the whole programme budget; this is the first real measurement
of it.

**Limitations to state, not argue past:**

- Train split only. Tune and holdout are unscored.
- The corpus over-represents failures by construction.
- The existing 16 are hindsight-selected and excluded from headline figures.
- Sector-relative grading (F2) is still unresolved; everything here is
  benchmarked against the broad market.

---

## 9. Git — Code runs these, in this order

1. Confirm a clean tree; record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit.**
3. Commit the scoring protocol and transcripts before scoring begins.
4. Commit scores and run state **incrementally** — do not hold a thousand scored
   calls uncommitted.
5. Commit the wrap-up.
6. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 10. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the per-call cost differing materially from $0.093,
  or the registered v6 model being unavailable.
- **Note anything contradicting this prompt's premises.** The repo, the registry
  and the vendor outrank it.
