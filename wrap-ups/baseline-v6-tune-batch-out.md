# Baseline — score v6 on the tune split, via the Batch API — wrap-up

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/93xfkzWVKXa6xriNqWbNkZ>

**Run ID:** `baseline-v6-tune-batch`. **Real spend: ~$46.34** (~$45.91 useful +
$0.43 wasted on a bug caught before batch submission — see Deviations), against
the $47 estimate. 1,207 tune calls scored (53/54 tickers), 0 errored, 0 expired.
Branch `sweep/db-corpus-baseline`, pushed at the end.

---

## 0. Defined terms

In plain English first: this run had the analyst read 1,207 real earnings-call
transcripts from 53 of the 54 companies in the "tune" group (a different set of
companies than the ones already scored in the prior "train" run), produce a
recommendation for each, and checked those recommendations against what actually
happened to the stock. Two companies — Wolfspeed (WOLF) and the current SunPower
(SPWR) — turned out to be cases where the stock ticker was reused by a different,
reorganized company after a 2024/2025 bankruptcy, so the price history needed to
grade their older calls no longer exists anywhere this project can fetch it. On
the other 51 companies (1,168 gradable calls), the analyst did slightly better
than chance, and — unlike the train result — the margin here is wide enough that
it cannot be explained by luck alone.

Terms this report uses:

- **train / tune / holdout** — the three-way split of the 164-company corpus.
  **Train** was scored first (`baseline-v6-train-batch`) and is the ruler every
  future candidate compares against. **Tune** (this run) is used for future
  prompt iteration. **Holdout** is locked and never scored until a final
  promotion decision.
- **pp vs %** — a percentage-point (**pp**) figure is an arithmetic difference
  between two percentages, not a relative change.
- **gradable / scoreable** — a scored call becomes gradable only once its ticker
  has price coverage spanning both the call date and ~6 months later, and enough
  time has passed for that forward window to exist in the (frozen) price data.
- **per_call_rec** — the analyst's own recommendation for a single call (Hold /
  Add / Trim / Exit), as opposed to any downstream allocator or trend-layer
  action. This run scores only `per_call_rec` — no allocator logic ran. See
  CLAUDE.md's analyst/allocator firewall.
- **balanced accuracy** — the average hit-rate across the three possible answers
  (bullish/bearish/neutral), so a run of "always guess the common answer" does
  not score well by default. A skill-less three-way guesser scores 33.3%.
- **luck-corrected gap** — observed accuracy minus the accuracy you'd expect from
  guessing in proportion to how often each answer is given and how often each
  outcome actually occurs. Zero means "no better than a coin weighted by its own
  guessing habits."
- **95% range** — a ticker-block bootstrap confidence interval (resample
  tickers, not individual calls, with replacement; 5,000 resamples, seed
  `20201231`, same convention the train wrap-up used). "Spans zero" means the
  data cannot rule out "no real effect."
- **A6 terminal-value grading** — an existing, registered project rule
  (`PREREGISTRATION_FIX.json`) for companies whose equity was wiped out: grade
  the forward return as a maximal loss without needing a real forward price.
  Referenced below because WOLF and SPWR are the kind of case it was built for,
  but it is **not currently wired into** `analyst_direct_scorer.py`, the scorer
  this run (and the train run) actually uses — see §4 below.
- Portfolio-layer terms (Type A/B, tier cap, ratchet, ALL16, `X`, `K`,
  `swap_funding`) **do not appear in this report** — this run is Layer 2
  (analyst) only, per hard constraint 5. Not defined here because not used.

---

## Headline

**On 51 of the 54 tune companies (1,168 gradable calls), v6 scores 28.3% against
25.7% expected by luck — a gap of +2.64 points, whose 95% range is 0.21 to
5.00pp. This range EXCLUDES zero** — the first time in this project's record
that a luck-corrected gap has cleared that bar. Balanced accuracy is 35.8% (95%
range 32.7–38.7%), which still spans the 33.3% chance line.

**Two of the 54 tune companies (WOLF, SPWR) could not be graded at all**, for a
reason that only surfaced because the scorer's own coverage guard refused to
report a score with them included (see §3) — both are 2024/2025 corporate-reorg
cases where the price history their pre-bankruptcy transcripts would need to be
graded against has been fully purged from this project's data source. **This
is not the full, honest 54-company test the prompt set out to run — it is a
51-company test, with the exclusion disclosed and investigated, not silently
dropped.**

**Carry the model confound in the same breath, as the prompt asked.** Every
figure above comes from `claude-sonnet-4-6`, not the retired model that
produced the legacy 40.4%/39.6% figures (`claude-sonnet-4-20250514`, retired
2026-06-15). That substitution's one formal gate returned **HOLD** (7.4pp
regression, 4.2pp noise floor, 29% of tickers improving against a 50%
threshold) before the champion was retired anyway. **Any weakness — or the
positive gap above — may be the model, not the prompt, and this data cannot
separate the two.**

---

## The comparison that matters

| | train (56 companies) | tune (51 of 54 companies — see below) |
|---|---|---|
| gradable calls | 1,236 | **1,168** |
| observed accuracy | 30.3% | **28.3%** |
| expected by luck | 27.8% | **25.7%** |
| gap | +2.48 points | **+2.64 points** |
| 95% range on the gap | −0.06 to +5.08 (**spans zero**) | **0.21 to 5.00 (EXCLUDES zero)** |
| balanced accuracy | 35.5% (95% 32.6–38.5%) | **35.8% (95% 32.7–38.7%)** |
| bullish recall | 38.2% | **39.4% (95% 31.2–47.6%)** |
| bearish recall | 11.2% | **8.7% (95% 5.2–12.9%)** |
| neutral recall | 57.1% | **59.1% (95% 49.1–67.7%)** |
| always-bullish guesser | 32.8% | **32.8%** |
| always-flat guesser | 22.2% | **18.8%** |

(Always-bearish guesser, not requested but reported for continuity with the
train wrap-up's diagnostic: **48.4%** — again higher than v6's own 28.3%.
Ground truth in this tune population skews bearish, same pattern train showed.)

**Which of the prompt's three named outcomes is this?** Closest to *"holds and
the range excludes zero"* — but with a real caveat the prompt's three options
didn't anticipate: it excludes zero on tune **alone** (51 companies), not on
the full 54, and not yet checked on the pooled 107 (56 train + 51 tune)
companies together. **Do not yet cite a pooled figure or a headroom-recomputation
number from this run** — that pooling, and any consequence for the $83,129
headroom estimate, is exactly the kind of promotion-adjacent step this run's
scope boundary excludes (§6 below). What can be said now: **the +2.48pp train
result replicates in both direction and magnitude on tune, and tune's own
interval — on its own, smaller, 51-company population — is tight enough to
exclude zero where train's wasn't.** That is real signal-shaped evidence, not
proof; the model confound and the 2-company exclusion both cut against reading
too much into it yet.

---

## 1. Resume status

Fresh start — no prior run state existed for `baseline-v6-tune-batch`. This is
a **complete run** through Step 6 (report), not partial. One in-run bug was
caught and fixed before it could affect the real batch spend (§5, Deviations).

Steps completed in order: version guard (pass) → split disjointness assertion
(pass) → alias sweep (GOOGL→GOOG, the only hit) → WOLF price-coverage
investigation → scoring protocol registered → events resolved (54/54 tickers,
0 coverage misses at the events level) → transcripts fetched (1,207/1,214
planned; 2 explicit 404s, BK/BNY contributed 0 — see §2) → 3-transcript eyeball
validation (passed) → 5-call synchronous pilot (**first attempt scored the
wrong ticker's transcripts — caught, fixed, re-run** — see §5) → batch
submitted → batch collected (1,202/1,202 succeeded) → eval cache written →
graded → **coverage guard failed on the full 53-ticker population** (WOLF,
SPWR) → investigated, explicit 51-ticker re-grade run and reported per the
prompt's "do not override, fix or explain" rule.

---

## 2. The three pre-checks (Step 1), reported explicitly

**2a. Ticker aliases.** Swept all 54 tune tickers against
`TICKER_ALIASES.json`. **Only GOOGL** has an entry (→ working symbol `GOOG`).
No other tune ticker is aliased. `custom_id`s and the price-cache lookup both
use `GOOG` consistently.

**2b. WOLF price coverage.** `scorer_price_cache_v1.json` (172 tickers) is
missing WOLF. Investigated live (not guessed, per the prompt's explicit
instruction):
- `scorer_price_cache_backfill_driver.py` hardcodes WOLF in a
  `KNOWN_UNRECOVERABLE` set alongside NOVA, without attempting a fetch.
- A first yfinance probe showed WOLF trading live today (~$24–29/share through
  2026-09-15) — **not** permanently delisted, which looked at first like a
  simple backfill gap.
- A second, more careful probe (querying 2019-06-01 through 2025-06-30)
  returned **zero rows** — Yahoo has purged WOLF's pre-petition price series
  entirely, not merely truncated it. This matches the exact empty-series shape
  `PREREGISTRATION_FIX.json` documents for the three already-verified A6
  companies (NOVA, SUNW, FRC): "fully EMPTY {} ... not just post-failure."
  The gap is consistent with Wolfspeed's 2025 Chapter 11 (filed ~2025-06;
  trading resumed 2025-09-29 post-emergence, under the same ticker but
  economically a different security).
- **Decision applied**: left WOLF's calls in the fetch/scoring scope (they
  were fetched and scored, so the transcripts and scores are a durable asset
  for any future run that does wire in a terminal-value override), but did
  **not** force a synthetic zero-price entry into the price cache. Full
  reasoning in `SCORING_PROTOCOL_TUNE.json` → `wolf_price_coverage`.
  **Why not force it**: A6's terminal-value mechanism lives in a separate,
  one-off script (`corpus_construction_outcomes_v3_terminal.py`), not in
  `analyst_direct_scorer.py` — the scorer this run and the train run both
  actually use has no terminal-value override path at all. NOVA (also an
  A6-verified wipeout) is *already* silently ungradable through this same
  scorer today, for the identical reason. Inventing a new scorer behavior to
  special-case WOLF mid-run, unauthorized by this prompt, was rejected in favor
  of leaving the gap visible and flagging it for the design session.

**2c. Coverage guard.** Confirmed present (`analyst_direct_scorer.py`, commit
on this branch 2026-09-15) and **passing on the existing train eval cache
without `--allow-partial-coverage`**, reproducing the committed train figures
exactly (30.3%/27.8%/+2.48pp/35.5%) before this run relied on it.

**What the guard then caught on tune, not anticipated by the prompt: SPWR.**
Grading the full 53-ticker population failed the guard — not just for WOLF
(100% loss, expected per 2b) but also for **SPWR, which lost 10/15 calls
(67%)**. Investigated: `scorer_price_cache_v1.json`'s SPWR series starts
2023-01-03, not the corpus window start (~2020). A live yfinance probe
(2019-06-01 to 2023-01-03) returned zero rows — **the identical purge pattern
as WOLF.** The original SunPower Corporation filed Chapter 11 in 2024; the
SPWR ticker was subsequently reused by a different, reorganized entity
(Complete Solaria's post-acquisition rebrand). `scorer_price_cache_v1.report.json`
had marked SPWR `"status": "ok"` because the *fetch itself* succeeded — it
never checked whether the returned series covers the corpus window, which is
why this gap was invisible until the coverage guard caught it here, on this
run, for the first time.

**Per the prompt's explicit rule — "Do not pass `--allow-partial-coverage` in
this run. If the guard fires on tune, that is a finding to fix, not to
override" — the guard was not overridden.** Instead, this run reports on the
51 tune tickers not affected by this bankruptcy-driven ticker-reuse pattern,
with WOLF and SPWR's exclusion stated explicitly, not silently dropped. This is
a disclosed scope restriction (declared before grading, same as the train
wrap-up's own documented `--tickers` re-grade convention), not the guard being
silenced.

---

## 3. Spend, measured

| | estimate | actual |
|---|---|---|
| Pilot (5 calls, synchronous, full rate) | ~$0.47 | **$0.3642** ($0.0728/call; a discarded first pilot attempt cost an additional $0.4321 — see §5) |
| Batch (1,202 calls, 50% off) | ~$47 total programme estimate | **~$45.54** |
| **Total (useful)** | | **~$45.91** |
| **Total (incl. the discarded pilot)** | **$47** | **~$46.34** |

Pilot cost ($0.0728/call, full synchronous rate) compared against train's own
full-rate pilot ($0.0827/call): **−12%**, well within the 30% stop threshold.
**Batch cache hit rate: 16.9%** (3,070,639 of 18,177,380 input+cache tokens
were cache reads) — consistent with train's 16.8%, expected since batch
requests process out of order and in parallel.

Token totals across the 1,202 batch calls: 15,106,741 input, 2,987,794 output,
3,070,639 cache-read, 7,683 cache-write —
`analysis/data/run_state/baseline-v6-tune-batch/scores.jsonl` → per-row
`usage`.

Batch id: `msgbatch_01MGo2MVdHaPdm8QN64LjYEU`. 1,202/1,202 succeeded, 0 errored,
0 expired.

**Revised programme budget**: two full baseline runs (train + tune) have now
cost **~$92.24** total (train ~$47.15 + tune ~$46.34, including the one wasted
pilot), against a combined original estimate of ~$103. A holdout run of similar
size, when the promotion decision needs it, should be budgeted similarly
(~$45–50), not scored until that decision is actually being made, per the
holdout-lock rule.

---

## 4. Model — same as train, no new substitution

`VERSION_REGISTRY.json` → `artifacts.model.promoted_version` is still
`claude-sonnet-4-6`, unchanged since the train run twelve days ago. No new
substitution was needed; the train-vs-tune comparison in this report is
apples-to-apples on the model axis. The standing model confound (vs the
retired `claude-sonnet-4-20250514` that produced v6's original 40.4%/39.6%)
applies identically to both runs and is carried forward, not re-litigated here.

---

## 5. Findings and coverage misses

- **Bug caught by the pilot, before it could touch the real batch spend:**
  `all_calls()` in the first version of `baseline_v6_tune_batch_driver.py`
  scanned the entire shared `transcripts/` directory (train and tune
  transcripts coexist there under separate ticker subdirectories), not
  filtered to tune's own working-symbol set. The first 5-call pilot run
  picked 5 **ABBV** transcripts — a train ticker — by mistake, spending
  $0.4321 re-scoring calls already scored and committed on train. Caught
  immediately (ABBV is not a tune company), fixed `all_calls()` to filter by
  tune's ticker set, re-ran the pilot correctly (5 ACN calls). The wrong-ticker
  results were discarded, not written to any eval cache — renamed to
  `scores_DISCARDED_wrong_ticker_pilot.jsonl` and kept for the record rather
  than deleted. **Had this shipped into `cmd_submit()` unfixed, the ~$47 batch
  would have re-scored up to 1,240 already-scored train calls alongside tune
  ones — violating hard constraint #1 ("Train split ONLY... Do not score train
  again") and roughly doubling real spend.** This is exactly the "check or
  artifact built against one set of keys while the consumer read another"
  failure shape the prompt's own Step 1 preamble warned had cost 46 calls on
  train — it recurred here in a different form (shared directory, not a ticker
  alias) and was caught the same way: before the money moved.
- **Company-level coverage gap: BK/BNY.** 0 transcripts. The vendor's only
  in-window-adjacent event for `BNY` is dated 2026-07-15, outside the
  2020-01-01–2025-12-31 corpus window — because BNY only began trading under
  that ticker in 2025 after Bank of New York Mellon's rebrand, and this
  vendor (unlike some others) does not carry pre-rebrand history forward under
  the new symbol. 53/54 tune companies got transcripts.
- **Transcript-level coverage misses (404, not stored as empty): GIS 2026Q1
  (call_date 2025-09-17), SRE 2020Q1 (call_date 2020-05-04).** 1,207 of 1,214
  planned in-window transcripts landed.
- **WOLF and SPWR: ungradable, not a transcript problem.** Both fetched and
  scored normally (23 and 15 calls respectively); both fail at the *grading*
  step because their pre-reorg price history is unrecoverable from this
  project's data source. Full investigation in §2b/§2c.
- **Two transient network drops mid-fetch**, both resumed cleanly with zero
  re-fetches (per-transcript flush-to-disk design) — one from a connection
  refusal, one from a system low-memory event that killed a monitoring
  process but not the fetch itself.
- **Ground-truth distribution in the 1,168-call gradable sample skews bearish
  (48.4%)**, the same pattern train showed (51.7% on its 149-call gradable
  slice). Flagged, not explained further here — this is the second run in a
  row to show it, which is itself worth noting for whoever looks at corpus
  construction next.

---

## 6. Deviations from the prompt, and why

- **Graded 51 of 54 tune companies, not all 54.** WOLF and SPWR excluded per
  the coverage guard's explicit refusal to report with them included, and per
  the prompt's own rule not to override that guard. This is the single most
  consequential deviation in this run — flagged prominently, not buried.
- **The pilot ran twice** (§5) — the first run's cost is real, spent money,
  reported rather than omitted, even though its results were discarded.
- Wrote a new driver (`analysis/baseline_v6_tune_batch_driver.py`, adapted
  from the train driver) rather than modifying the train driver in place, so
  the two runs' code and state never collide — consistent with the prompt's
  own framing of this run as train's twin.
- Did **not** attempt to wire A6's terminal-value grading into
  `analyst_direct_scorer.py` to recover WOLF/SPWR — that is new scorer
  behavior this prompt did not authorize, and a decision (whether to build it
  at all, and for which companies) that belongs to the design session, not a
  batch-scoring run.
- Did **not** attempt to backfill WOLF/SPWR price data by any other means —
  confirmed via live probes that the pre-reorg data does not exist at this
  project's data source (Yahoo/yfinance), not merely that it wasn't fetched.

---

## 7. What was deliberately not done / left for the design session

1. **Whether to wire a terminal-value (A6) override into
   `analyst_direct_scorer.py`**, and if so, for which companies — WOLF and
   SPWR are two data points; NOVA (train) is a third, already silently
   affected the same way. This would recover some but not all of the excluded
   calls (post-reorg calls, if any exist in-window, would still need real
   post-emergence prices, which are a different security's data).
2. **Whether/how to pool the train and tune results** (56 + 51 = 107
   companies) into a single combined-population statistic, and whether that
   changes the $83,129 headroom figure. Explicitly out of scope here per the
   prompt's "report, do not decide" boundary — this run states the two
   populations' figures side by side but does not pool them.
3. **No allocator, simulator, or portfolio logic touched**, per hard
   constraint 5 — this is Layer-2-only.
4. **Holdout remains unscored and untouched.**
5. Whether the BK/BNY vendor-side gap (pre-rebrand history not carried
   forward) is fixable by querying the vendor under the old `BK` symbol
   directly for pre-2025 quarters — not attempted here; flagged as a possible
   follow-up, not a blocker for this run's headline result.

---

## 8. Limitations, stated plainly

- **51 of 54 tune companies graded, not the full split** — WOLF and SPWR
  excluded for a specific, investigated, disclosed reason (§2b/§2c), not
  dropped silently.
- **The model confound stands.** `claude-sonnet-4-6` is not the model v6's
  original 40.4%/39.6% figures were measured on. Any weakness *or* the
  positive gap reported here may be the model rather than the prompt, and the
  two cannot be separated with available data.
- The corpus over-represents failures by construction (carried over from the
  legacy framing; unchanged by this run).
- Sector-relative grading (F2) unresolved; everything benchmarked against the
  broad market (SPY).
- **The tune interval excluding zero is on its own, standalone 51-company
  population** — it has not been checked against train under any joint/pooled
  test, and should not be read as a promotion-grade result on its own.

---

## Follow-up commands

Regenerate the tune eval cache from committed scores (gitignored, not
committed):

```
cd analysis
python3 baseline_v6_tune_batch_driver.py writescores
```

Re-grade at the full 53-ticker (WOLF+SPWR included, guard will fail as
documented):

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6_tune \
    --price-cache data/corpus_v2/scorer_price_cache_v1.json
```

Re-grade restricted to the 51 currently-gradable tickers explicitly (same
result as this report, for clarity in a future diff):

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6_tune \
    --price-cache data/corpus_v2/scorer_price_cache_v1.json \
    --tickers ACN ARRY BAC BLDP CI CL CRM DHR DIS ENVX EOG ETN EXC FCX GIS GOOG \
    GS HRL KHC KO LMT LRCX MCD MCHP MO MPWR NEE NFLX ORCL PFE PLD PM PNC PPG PSA \
    PYPL RTX SBUX SEDG SLB SNOW SRE SWKS T TSLA VLO VZ WDAY WEC WFC ZTS
```

Check batch status/results again if ever needed (results retrievable 29 days
from submission, i.e. through 2026-10-14):

```
cd analysis
python3 baseline_v6_tune_batch_driver.py poll
```
