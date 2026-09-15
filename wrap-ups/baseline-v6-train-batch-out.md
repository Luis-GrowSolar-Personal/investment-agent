# Baseline — score v6 on the train split, via the Batch API — wrap-up

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/8nEiKbgmDvXDNvUmco9J3q>

**Run ID:** `baseline-v6-train-batch`. **Real spend: ~$47.15** ($0.41 pilot at
full rate + ~$46.74 batch at the 50% discount), against the $56 estimate.
1,240 transcripts scored, 0 errored, 0 expired. Branch `sweep/db-corpus-baseline`,
pushed at the end.

---

## 0. Defined terms

In plain English first: this run had the analyst read 1,240 real earnings-call
transcripts and produce a structured recommendation for each, at a real cost of
about $47. It then tried to check those recommendations against what actually
happened to the stock afterward — but the price-history file it needs for that
check only covers 8 of the 57 companies whose calls were scored, so only 149 of
the 1,240 calls could actually be graded yet. On those 149, the analyst did not
beat chance.

Terms this report uses:

- **train / tune / holdout** — the three-way split of the 164-company corpus.
  Only **train** is touched here. **Tune** is used for future prompt iteration;
  **holdout** is locked and never scored until a final promotion decision.
- **pp vs %** — a percentage-point (**pp**) figure is an arithmetic difference
  between two percentages (e.g. "22.8% minus 24.5% = −1.6pp"), not a relative
  change. Every gap/lift figure below is in pp.
- **gradable / scoreable** — a scored call becomes gradable only once (a) its
  ticker has price-history coverage and (b) enough calendar time has passed for
  its ~6-month forward return to exist in that price history. This report's
  central finding is that most of the 1,240 scored calls fail test (a), not (b).
- **per_call_rec** — the analyst's own recommendation for a single call (Hold /
  Add / Trim / Exit), as opposed to any downstream allocator or trend-layer
  action. This run scores only `per_call_rec` — no allocator logic ran.
  See CLAUDE.md's analyst/allocator firewall.
- **balanced accuracy** — the average hit-rate across the three possible answers
  (bullish/bearish/neutral), so a run of "always guess the common answer" does
  not score well by default. A skill-less three-way guesser scores 33.3% on this
  measure.
- **luck-corrected gap** — observed accuracy minus the accuracy you'd expect from
  guessing in proportion to how often each answer is given and how often each
  outcome actually occurs. Zero means "no better than a coin weighted by its own
  guessing habits."
- **95% range** — a ticker-block bootstrap confidence interval (resample tickers,
  not individual calls, with replacement). "Spans zero" means the data cannot
  rule out "no real effect."
- Portfolio-layer terms (Type A/B, tier cap, ratchet, ALL16, `X`, `K`,
  `swap_funding`) **do not appear in this report** — this run is Layer 2
  (analyst) only, per hard constraint 5. Not defined here because not used.

---

## Headline: the "representative universe" question is not yet answered

**This run cannot yet say whether v6 replicates near-chance on a representative
universe.** It scored all 57 train companies, but `analysis/data/price_cache.json`
— the cache `analyst_direct_scorer.py` reads for benchmark-relative forward
returns — only has price data for **8 of the 57 train tickers**
(AMPX, EOSE, JPM, MSFT, PG, QS, RUN, TTD). The other 49 (ABBV, AEP, AIG, ANTM,
BLK, BMY, BOX, CMCSA, CMI, COF, COST, DD, DIOD, DOW, DUK, EMR, EQIX, FRC, HCA,
HON, IBM, INTC, ITW, JKS, KMB, LLY, MAXN, MMM, MRK, MS, MU, NEM, NOW, NXPI, OXY,
PH, PSX, QCOM, ROK, SIRI, SLAB, SUNW, TEAM, TFC, TMO, TMUS, UPS, VIAC, WMB) have
no rows in that cache at all, so **none of their calls are gradable right now**
regardless of how many were scored.

This is a **different cache from the one corpus construction used.**
corpus-fix-6/-7/-8's price-coverage gate (A9) checked coverage via
`corpus_v2_price_cache.json` (yfinance/Yahoo), which is why those 49 companies
correctly passed corpus admission — that gate was never about
`analysis/data/price_cache.json`, which backs the scorer and was never expanded
past the original ~66-ticker legacy backtest universe. **Nobody has connected
these two caches.** That gap was invisible until this run tried to grade a call
outside the original small universe for the first time.

**Of the 8 gradable tickers, 5 (AMPX, EOSE, QS, RUN, TTD) are from the original
16-company pathological corpus** this run exists to get away from (solar/
battery/storage names that move together). Only JPM, MSFT, PG are genuinely new.
**So even the 149 calls that scored here are not the honest, representative test
the prompt asked for — they are dominated by the same universe this run was
built to escape.**

**Per this prompt's own standing rule** ("no cache refreshes... the staleness
warning is expected and must not be fixed") **this run does not expand
`price_cache.json` itself.** That is a decision for the design session: either
backfill `price_cache.json` for the other 49 tickers (yfinance/Yahoo, same
source corpus construction already used, frozen at the same 2026-05-11 cutoff
for consistency) or accept a much smaller gradable population than intended.
**No further scoring is needed to fix this — the transcripts and scores for all
49 tickers already exist**; only the price data is missing.

---

## What scoring found, on the 8 tickers/149 calls that ARE gradable

Not the headline result the prompt was written to get, but reported in full
since it's real and free (no incremental spend):

| | old 16-company corpus (legacy) | this run (n=149, 8 tickers) |
|---|---|---|
| observed accuracy | 40.4% | **22.8%** |
| expected by luck | 39.6% | **24.5%** |
| gap | 0.8pp | **−1.6pp** (95% range **−5.67 to +3.05pp — spans zero**) |
| balanced accuracy | 31.3% | **29.7%** (95% range **23.8–37.0% — spans the 33.3% chance line**) |
| bullish recall | 72.9% | **35.4%** |
| bearish recall | 13.9% | **7.8%** |
| neutral recall | — | **45.8%** |

95% ranges from a ticker-block bootstrap (5,000 resamples, seed `20201231`,
resampling the 8 covered tickers with replacement) — the smallest resampling
unit this project trusts, per `PROMOTION_GATE.md` §3.1's own convention. With
only 8 clusters, this interval is wide and should not be over-read.

**Always-bullish guesser:** 32.2% (labelled per the prompt, for continuity).
**Always-flat (neutral) guesser:** 16.1%.
**Always-bearish guesser (not requested, but reported as a diagnostic that
contradicts the prompt's framing):** 51.7% — higher than v6's own 22.8%. Ground
truth in this 149-call sample skews heavily bearish (77/149, 51.7%), which is
itself a sampling artifact of which calls happen to be old enough to be
scoreable yet (see below) — not evidence about the broader corpus.

**On this narrow, non-representative slice: v6 is not distinguishable from
chance, and if anything trails a naive always-bearish guess.** This *rhymes*
with the original finding but **is not the honest test this run set out to
run** — say so plainly rather than reporting it as if it were.

---

## Scale of what could not yet be graded

- **1,240 scored, 149 scoreable (12.0%), 1,011 "not yet scoreable."** Most of
  the 1,011 are excluded by the *other* standing limitation, unrelated to the
  price-cache gap above: `price_cache.json` (for the 8 tickers it does cover)
  stops at 2026-05-11, so any call within ~182 days of that cutoff has no
  forward price yet. This affects even the well-covered tickers and would
  persist even after a price-cache backfill for the other 49 — it is a
  frozen-cache-vs-horizon problem, not a coverage gap.
- 1,011 calls across all 57 tickers are sitting scored and ready the moment
  (a) the other 49 tickers get price coverage, and (b) enough time/backfill
  passes the 182-day horizon. No re-scoring needed for either.

---

## Spend, measured

| | estimate | actual |
|---|---|---|
| Pilot (5 calls, synchronous, full rate) | ~$0.47 (5 × $0.093) | **$0.4135** ($0.0827/call) |
| Batch (1,235 calls, 50% off) | ~$56 total programme estimate | **~$46.74** |
| **Total** | **$56** | **~$47.15** |

`$0.093/call` (the pilot's own measurement basis) held within 11% ($0.0827
measured) — well under the 30% stop threshold, so the batch was submitted as
planned. **Batch cache hit rate: 16.8%** (3,157,713 of 18,833,318 input+cache
tokens were cache reads) — lower than hoped, expected since batch requests
process out of order and in parallel, so the ephemeral system-prompt cache hits
inconsistently across a 1,235-request batch. Reported as measured, not assumed.

Token totals across all 1,240 calls: 15,657,678 input, 3,060,020 output,
3,157,713 cache-read, 17,927 cache-write —
`analysis/data/run_state/baseline-v6-train-batch/scores.jsonl` → per-row `usage`.

Batch id: `msgbatch_01CrFTtAKaAwDx1YDRy6ecNo`. 1,235/1,235 succeeded, 0 errored,
0 expired.

---

## Model substitution — flagged per the prompt's rule 4, before scoring, not after

**This run scored with `claude-sonnet-4-6`, not the model that produced v6's
known 40.4%/39.6% figures (`claude-sonnet-4-20250514`, retired 2026-06-15,
unregenerable).** `docs/architecture/VERSION_REGISTRY.json` →
`artifacts.model.promoted_version` names `claude-sonnet-4-6` as current, and
its own note records that the one formal gate run on this substitution
(`data/gate_ledger.json` entry 1, 2026-05-23) returned **HOLD** — the challenger
regressed by 7.4pp against a 4.2pp noise floor, and only 29% of tickers
improved (below the 50% robustness threshold) — yet the champion model was
retired 5 weeks later anyway, forcing the substitution with no new gate run.
**Any comparison between this run's numbers and the legacy 40.4%/39.6% figures
is confounded by this model change, not just by universe and sample size.**
`CLAUDE.md`'s own tech-stack section still says `claude-sonnet-4-20250514` —
that line is stale and should be corrected in the same pass that fixes the
`versions.js` re-export note.

---

## Resume status

Fresh start — no prior run state existed for `baseline-v6-train-batch`.
Superseded `prompts/baseline-score-v6-on-train.md` (per-call synchronous) was
never run; this batch version replaced it before any spend, per that prompt's
own header.

Steps completed in order: version guard (pass, hash matches registry) →
scoring protocol registered → vendor events resolved (114 calls, 1,244
in-window transcripts planned) → transcripts fetched (1,240/1,244; one
background-process kill from a system low-memory event mid-fetch, resumed
cleanly — the per-transcript flush-to-disk design meant zero re-fetches, only
a restart of the loop) → 3-transcript eyeball validation (passed, one minor
finding below) → 5-call synchronous pilot (passed, cost within tolerance) →
batch submitted → batch collected → eval cache written → graded. This is a
**complete run**, not partial — the incompleteness that matters (the 8-of-57
gradable-ticker gap) is a data-coverage limitation, not an unfinished step.

---

## Findings and coverage misses

- **Company-level coverage miss: MAXN/MAXNQ.** Not in the vendor's symbol
  list at all — consistent with corpus-fix-8's "possibly delisted" finding for
  MAXN at the Yahoo/yfinance layer. 56/57 train companies got transcripts.
- **Transcript-level coverage misses (404, not stored as empty): AEP 2021Q1,
  NXPI 2020Q1, NXPI 2020Q2, PARA 2025Q3.** 1,240 of 1,244 planned transcripts
  landed.
- **Minor: one unresolved speaker code in the 3-transcript validation sample.**
  `INTC 2022-01-26` has one turn attributed to `spk04` with no entry in that
  payload's `speaker_name_map_v2` (50 of 51 turns resolved correctly). Judged
  non-blocking — the vendor's own name map is occasionally incomplete; this is
  a known limit of the data source, not a bug in the reused fetch code, and
  doesn't corrupt the substantive transcript content.
- **Ground-truth distribution in the 149-call gradable sample is heavily
  bearish (51.7%)**, likely because the calls old enough to already be
  scoreable are concentrated in 2020–2023, a period with real drawdowns in
  several of the 8 covered names (RUN, QS, EOSE). Flagged as a property of
  *which calls happen to be scoreable yet*, not a property of the corpus.

---

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on `baseline_v6_train_batch_driver.py`
  after every edit — passed.
- Version guard (`analysis/version_guard.py assert_prompt_hash`) run before
  call one: actual sha256 of `docs/EVALUATION_PROMPT.md` matched the
  registry's `promoted_sha256` exactly. No candidate declaration needed.
- `custom_id` regex-checked against the vendor's `^[a-zA-Z0-9_-]{1,64}$`
  pattern for all 1,235 batch requests before submission — none violated it.
- Batch result counts reconciled: `succeeded=1235, errored=0, expired=0,
  canceled=0` matches `len(scores.jsonl)` for batch-sourced rows.
- Re-grepped `analysis/data/corpus_v2/transcripts/` (1,240 files) and
  `analysis/data/evals/v6_claude-sonnet-4-6/` (1,240 files) counts after
  writing, both match `scores.jsonl`'s row count.

---

## Deviations from the prompt, and why

- The prompt's Step 3 code sample used `Request`/`MessageCreateParamsNonStreaming`
  from `anthropic.types.messages.batch_create_params` /
  `anthropic.types.message_create_params` — confirmed these import correctly
  under the installed SDK (`anthropic==0.94.0`); used as specified, no change.
- Wrote a new driver (`analysis/baseline_v6_train_batch_driver.py`) rather than
  extending `ec_fidelity_benchmark_1/driver.py` directly, per that prompt's own
  instruction to import read-only from it rather than modify it.
- Did **not** attempt to backfill `price_cache.json` for the 49 uncovered
  tickers — that would violate the standing "no cache refreshes" rule and is,
  regardless, a decision for the design session (see Headline section).

---

## What was deliberately not done / left for the design session

1. **Whether/how to expand `price_cache.json`** to the other 49 train tickers
   (and eventually tune/holdout tickers) so the representative-universe
   question this run was built to answer can actually be answered. The
   transcripts and scores already exist; only price data is missing.
2. **Whether to re-run this exact grading in a few months**, once enough of the
   1,011 "not yet scoreable" calls cross the 182-day horizon relative to
   whatever the price cache's cutoff is at that time.
3. **No allocator, simulator, or portfolio logic touched**, per the prompt's
   hard constraint 5 — this is Layer-2-only.
4. **Tune and holdout remain unscored and untouched.**

## Limitations, stated plainly

- Train split only; tune and holdout unscored.
- The corpus over-represents failures by construction (per `PROMOTION_GATE.md`
  framing carried over from the legacy 16-company set).
- The existing 16 are hindsight-selected and excluded from headline figures
  (only 5 of them happen to overlap the 8 gradable tickers here; that overlap
  is exactly why this run's "representative" claim doesn't hold yet).
- Sector-relative grading (F2) is unresolved; everything here is benchmarked
  against SPY.
- **New this run: 8/57 gradable-ticker coverage is the binding limitation**,
  not sample size or spend — money is not the constraint here.

---

## Follow-up commands

Regenerate the eval cache from committed scores (gitignored, not committed):

```
cd analysis
python3 baseline_v6_train_batch_driver.py writescores
```

Re-grade after a `price_cache.json` backfill decision:

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6
```

Re-grade restricted to only the currently-gradable 8 tickers explicitly (same
result as above, for clarity in a future diff):

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6 \
    --tickers AMPX EOSE JPM MSFT PG QS RUN TTD
```

Check batch status/results again if ever needed (results retrievable 29 days
from submission, i.e. through 2026-10-14):

```
cd analysis
python3 baseline_v6_train_batch_driver.py poll
```
