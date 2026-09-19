# P3 — the guidance ledger: hand the analyst last quarter's promises

**Run ID:** `p3-guidance-ledger`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P3-guidance-ledger-out.md`
**Cost: THIS RUN SPENDS REAL MONEY.** Two paid passes on the train split plus a
pre-flight: roughly **$30 (Pass A, extraction) + $6 (pre-flight) + $47 (Pass B,
scoring) ≈ $85**, batch rate, using the train run's measured $0.0380/call as the
scoring reference. **Hard cap: $110 total.** Money commits at batch submission;
every cap below is checked *before* `create()`.

**Read first, in this order:** `docs/handoffs/2026-09-19-state-of-play.md` §0,
§2, §5; `docs/architecture/PROMPT_ARCHITECTURE.md` in full (§1.1 says
per-ticker *inputs* are permitted — this run is exactly that — and §2.3–2.5
are binding); `docs/architecture/PROMOTION_GATE.md` §3.1 and §8;
`prompts/baseline-v6-tune-batch.md` §3–§7 (the batch machinery, reused
verbatim); `analysis/version_guard.py`; `docs/EVALUATION_PROMPT.md` (the v6
text — note its STUMBLE CLASSIFICATION test 1 and the MITIGATION ARGUMENT rule,
both of which this candidate feeds rather than replaces).

---

## 1. What this run is for

Today the analyst reads one transcript. When management says "gross margin
expanded to a record 50%," the analyst has no way to know that revenue was
guided to $1,000M and came in at $900M, or that the margin beat never reached
operating profit. It cannot see last quarter's promise, so its stumble test
("did they give guidance and miss it?") runs on whatever the current call
happens to mention. Management chooses the camera angle.

**P3 hands the analyst a ledger of last quarter's stated numbers, graded
mechanically against this quarter's reported numbers, before it reads the
transcript.** The analyst still decides what the misses mean. The ledger only
guarantees it sees them.

Worked example the design was agreed on. Call N guides revenue $1,000M, gross
margin 40%, operating margin 15%, EPS $1.00. Call N+1 reports $900M, 50%, 15%,
$0.80. The ledger computes: revenue missed by 10% on a guided number; gross
profit up 12% on less revenue; operating profit *down* 10%, so the margin beat
was eaten by operating expense, which rose 26%; EPS fell twice as fast as
operating profit, so ~10% went missing below the line. Whether that is a Trim
depends on which promise the thesis rests on — the analyst's job. Without the
ledger it sees "record gross margin." With it, it sees a guided miss and a
$65M hole to explain.

**Three things the ledger does that the analyst cannot be trusted to:**

1. **Keeps the original promise, not the latest one.** Guided $500M in Q1,
   quietly lowered to $420M in Q2, delivered $430M, call opens "we beat
   guidance." Against the promise actually made, that is a 14% miss. The ledger
   records the original, the revision, and the actual.
2. **Grades every promise the same way every time.** Inside the guided range =
   met; below the low end = missed, stated as a % of the low end; above the high
   end = beat. No weights. No ranking of which miss matters — that was decided
   against, because which miss matters depends on the thesis.
3. **Derives the lines management didn't state.** If gross profit and operating
   profit are both known, operating expense is arithmetic. If revenue and EPS
   move by different amounts, the ledger says so.

**What this run is NOT.** It is not a promotion. It does not touch the allocator,
the trend layer, the simulator, or the holdout. It does not rank misses or
weight metrics. It scores one candidate on train, reports, and stops.

---

## 2. Ground rules — the do-not list

1. **Train split ONLY** — the 57 companies in
   `analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json` → `train`.
   **Do not score tune. Do not touch the holdout.** Assert zero intersection
   with both before any submission; record the assertion.
2. **Version guard before any scoring call.** This is a candidate, so it runs
   under `PROMPT_CANDIDATE=v6+P3a` and the candidate must be **registered in
   `docs/architecture/VERSION_REGISTRY.json` first** (Step 0d). Guard fails or
   candidate unregistered → stop, submit nothing.
3. **Same model as both baselines: `claude-sonnet-4-6`, pinned**, for Pass B.
   Pass A (extraction) also uses it unless its measured cost would breach the
   cap, in which case stop and report — do not substitute a model on your own.
4. **Hard caps, counted before `create()`:** Pass A ≤ 1,300 requests; Pass B ≤
   1,300 requests; total spend ≤ $110. Exceeded → stop and report, do not submit
   a trimmed batch.
5. **Price cache is `analysis/data/corpus_v2/scorer_price_cache_v1.json`.**
   Never `analysis/data/price_cache.json` — it is a stale 66-ticker cache from
   an earlier era and the 2026-09-17 prompt named it by mistake. State the path
   you pass to the scorer; it must be this string.
6. **Exclude `WOLF` and `SPWR` entirely** — every call, not only calls missing
   price data. Partial exclusion silently inflated a bearish count from 84 to
   97 on 2026-09-18.
7. **Do not modify `analysis/analyst_direct_scorer.py`** (import from it), and
   do not edit the v6 text in place. The candidate is a **new file**,
   `docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`, so v6 remains
   byte-identical for the guard.
8. **No DB writes. No trend layer. No `final_action`.** Grade `per_call_rec`.
9. **macOS Tahoe, zsh.** `python3`, never `python`. Never
   `--break-system-packages`. No `apt`. `brew` only if a system tool is missing.
10. **A diagnostic that contradicts an expectation stated in this prompt is a
    finding, not a reason to stop.** The predictions in §7 are predictions.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/p3-guidance-ledger/`. **Write `progress.json`
as the very first action, before reading anything.**

- `progress.json` — `prompt_sha256`, `driver_commit`, per-step status,
  `next_action`, `notes[]`, and **`batch_id_pass_a` / `batch_id_pass_b` written
  and committed the instant each `create()` returns** — before polling. The
  batch id is the recovery key; results persist 29 days.
- `extractions.jsonl` — one line per Pass A result, keyed by `custom_id`;
  skip ids already present on resume.
- `scores.jsonl` — same for Pass B.
- `findings.md` — append-only; each finding the moment it is established.

On resume with a matching `prompt_sha256`: if a batch id exists, **submit
nothing** — retrieve and continue collecting.

---

## 4. Step 0 — hygiene, registration, guard

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`.

**0b.** Write and commit the driver as its own commit before it produces
output: `analysis/p3_guidance_ledger_driver.py`. Reuse the batch machinery from
`analysis/baseline_v6_tune_batch_driver.py` by import; do not rewrite it.

**0c. Pre-register in `docs/architecture/PROMPT_ARCHITECTURE.md` §2.2**, as a
new block under P1's, dated, **before any spend**, with exactly the content of
§7 of this prompt (change, expected movement, predicted flip count, falsifiers,
split, pre-flight). Commit it. Also add the follow-on **P3b** (the analyst's own
prior watch condition as a second ledger input) as *named but not run*, so the
"name two or three before running any" rule in §2.3 is satisfied.

**0d. Register the candidate** in `docs/architecture/VERSION_REGISTRY.json` as
a *candidate*, not a promotion: key `v6+P3a`, path
`docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`, its sha256, parent
`v6`, status `candidate`, registered date. Then run
`python3 analysis/version_guard.py` under `PROMPT_CANDIDATE=v6+P3a` and record
the loud warning it prints. Commit.

**0e. Register the scoring protocol** at
`analysis/data/corpus_v2/SCORING_PROTOCOL_P3A.json` — new file — carrying
split, company list, manifest and split sha256s, candidate hash and parent
hash, pinned model with an assertion it equals both baselines'
`model_version_pinned`, grading field `per_call_rec`, both eval-cache paths,
the price-cache path from rule 5, the request caps, and the disjointness
assertion.

---

## 5. Step 1 — Pass A: extract promises and actuals (highest-value step)

If the budget only allows one paid pass, **run this one.** The ledger is a
durable asset reused by every later round (P3b, P4) and by the exit-latency
work; the scoring pass can be re-run later.

### 5a. What is extracted, per transcript

One batch call per train transcript (transcripts are on disk under
`analysis/data/corpus_v2/transcripts/<TICKER>/<call_date>.json`). The
extraction prompt is short, system-cached, and asks for a JSON block with two
lists:

**`reported`** — what this call says happened *this* quarter. One entry per
metric management states a number for: `{metric, value, unit, basis
(GAAP|non-GAAP|unspecified), period, quote}`.

**`guided`** — what this call promises for a *future* period. One entry per
explicit number or range: `{metric, low, high, unit, basis, period
(next_quarter|next_two_quarters|fiscal_year|other), quote}`. Plus a separate
list **`stated_intents`** — non-numeric commitments with a date attached
("exit the residential line by Q3", "reach breakeven by year end"), as
`{intent, by_period, quote}`.

**Rules the extraction prompt must carry:**

- Only explicit numbers and ranges count as guidance. "Strong growth" is not a
  promise. "40 to 42% gross margin" is.
- Metric names are normalized to a fixed list you define in the driver and
  commit before running: revenue, gross_margin_pct, operating_margin_pct,
  operating_income, eps, free_cash_flow, capex, backlog, unit_shipments,
  customer_count, cash_balance, other (with the raw name kept).
- **The quote is mandatory.** Every entry cites the sentence it came from.
  An entry without a quote is dropped by the driver, and the drop count is
  reported.
- Basis is recorded, never reconciled. A non-GAAP guide graded against a GAAP
  actual is a mismatch the driver flags, not a miss.

### 5b. Validate on five before submitting the rest

Extract five transcripts synchronously — two established, two speculative, one
pre-revenue. Inspect by eye: does every guided entry quote a real sentence with
a real number? Are actuals and guidance kept apart (the classic error is
recording "we delivered $500M" as guidance)? Is the period right? **Any of the
five fails → fix the extraction prompt and re-validate. Do not submit 1,240
requests through an unvalidated extractor.** Record measured per-call cost;
if the implied Pass A total exceeds $40, stop and report before submitting.

### 5c. Build the ledger — $0, driver only

For every call N+1 with a predecessor N for the same company (first call of
each company gets an **empty ledger**), the driver joins:

- each `guided` entry from call N whose period covers N+1 (and any
  **earlier** call whose period covers N+1 — the original promise is kept even
  if N revised it; both are recorded, `original` and `latest_revision`);
- the matching `reported` entry from N+1 on the same metric and basis;
- the grade: `met` (inside [low, high]), `missed` (below low, with
  `miss_pct = (low − actual) / low`), `beat` (above high, with `beat_pct`),
  `unreported` (guided, but N+1 states no number — **this is itself a
  finding**: metric dropped), `basis_mismatch`;
- derived lines when inputs exist: operating expense = gross profit −
  operating income (guided and actual); the gap between the % change in
  operating income and the % change in EPS;
- `stated_intents` from N due by N+1, with the driver marking only whether N+1
  mentions them at all (the analyst judges whether they were kept).

Write `analysis/data/corpus_v2/ledger/<TICKER>/<call_date>.json` and a flat
`ledger_summary.csv` (one row per promise). Commit. Report: calls with a
non-empty ledger (expect ~1,184 of ~1,240), promises per call (median and
range), share of promises graded `missed`, share `unreported`, share
`basis_mismatch`. **If fewer than 60% of calls with a predecessor have at
least one graded promise, stop and report** — the extractor is not finding
guidance and Pass B would be scoring against empty ledgers.

---

## 6. Step 2 — Pass B: score the candidate

### 6a. The candidate prompt — the only text that changes

`docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md` is v6 plus **exactly**
these changes. Diff it against v6 and include the diff in the wrap-up.

1. A new input section, delivered in the **user message ahead of the
   transcript** (so the cached system block is unchanged and the round stays
   at batch cost):

   ```
   ---PRIOR-CALL LEDGER---
   (rendered ledger table: metric | original guide | latest revision | actual | grade | quote)
   (derived lines)
   (stated intents due this quarter)
   ---END LEDGER---
   ```
   For a first call, the block reads `No prior call on record.`

2. In **STUMBLE CLASSIFICATION**, test 1 gains one sentence: *"Consult the
   PRIOR-CALL LEDGER first. A promise graded `missed` on a metric management
   guided is a missed specific guidance by definition — apply test 1 on that
   basis. A `unreported` grade (guided last quarter, no number this quarter)
   is to be treated as a miss unless the transcript explains the omission."*

3. A new short section before RECOMMENDATION, **LEDGER READING**, with three
   ordered questions: *Which ledger promise is the one the thesis rests on?
   Was it met? If missed, does any beat elsewhere repair the specific mechanism
   that failed — or is it a different thing?* — followed by the existing
   mitigation rule restated in one line: a beat on one line does not lend
   credibility to a miss on another.

4. Four new structured fields, diagnostics only, never gated:
   `ledgerLoadBearingMetric` (string or null), `ledgerLoadBearingOutcome`
   (`met|partial|missed|none`), `ledgerMissCount` (int),
   `ledgerRevisedDownCount` (int).

**Nothing else changes.** The decision matrix is untouched. No weights, no
scoring of misses, no new action labels. If you find yourself adding a rule
about *how much* a miss matters, stop — that is the design decision this
candidate exists to leave with the analyst.

### 6b. Pre-flight (mandatory, `PROMPT_ARCHITECTURE.md` §2.5)

Score ~150 train calls **that have a non-empty ledger**, chosen by fixed seed,
synchronously or as a small batch. Count disagreements in `per_call_rec`
against v6's cached call on the same transcripts. **If the implied corpus-wide
flip count is under ~100, do not run the full round** — report and stop. Also
confirm the four new fields populate and that the ledger block did not push
completions into `max_tokens` (log `stop_reason`; v9 was corrupted exactly this
way).

### 6c. Full round

Submit one batch of all train calls (including empty-ledger first calls, so the
eval cache is complete), request shape as in `baseline-v6-tune-batch.md` §7
with the ledger block prepended to the user content. Eval cache to
`analysis/data/evals/v6+P3a_claude-sonnet-4-6/`. Score with
`analysis/analyst_direct_scorer.py` against the corpus_v2 price cache;
`--allow-partial-coverage` is forbidden.

---

## 7. Pre-registration — copy this into PROMPT_ARCHITECTURE.md §2.2 at Step 0c

**P3a — guidance ledger, registered [date].**

- **Change.** Prepend to each call a mechanically graded table of the
  promises the prior call made and what this call reported against them; point
  stumble test 1 at it; ask which promise the thesis rests on. No change to the
  decision matrix.
- **Expected to move.** Bearish call rate up, concentrated on calls whose
  ledger shows a `missed` or `unreported` grade on a guided metric. Bearish
  precision holds above the base rate. Overall gap over luck up.
- **Predicted flip count.** 150–300 of ~1,184 ledger-bearing calls on train,
  the large majority neutral → bearish.
- **Falsified if.** Flip count under ~100 (the ledger was ignored), **or**
  bearish precision at or below the 46.6% base rate (the ledger produced
  reflexive trims, not better-evidenced ones), **or** the flips concentrate in
  calls whose ledger shows *no* miss (the change is acting through something
  other than its mechanism).
- **Runs on.** Train. Tune only if it clears, and only once.
- **Pre-flight.** §2.5, ~150 ledger-bearing calls.

**P3b — own prior thesis, named, not run.** Add the analyst's own "measurable
condition that would change this recommendation" from call N to the ledger at
N+1. Sequential by construction (needs N's output before N+1), so it cannot
batch; deferred.

---

## 8. Required diagnostics after the round — all $0

1. **Flip count and win rate among flips** against v6 on the shared train
   calls, restricted to ledger-bearing calls, with the ceiling table from
   `PROMPT_ARCHITECTURE.md` §2.4 alongside.
2. **The confusion table**, both prompts.
3. **The mechanism check — the one that matters for this candidate.** Split
   the ledger-bearing calls three ways: ledger shows ≥1 `missed`/`unreported`
   on a guided metric; ledger shows only `met`/`beat`; ledger empty. For each:
   v6 bearish rate and hit rate, P3a bearish rate and hit rate, flip count.
   **P3a should differ from v6 mostly in the first group.** If it differs
   equally in all three, the ledger is not what moved it.
4. **By tier** (established / speculative), because §1.2 says inventory means
   different things by class and the same will be true of a 10% revenue miss.
5. **`ledgerLoadBearingMetric` frequency table** — which metrics the analyst
   says theses rest on. This is free information for P4's template design.
6. **Per-call diffs to disk**, `analysis/data/run_state/p3-guidance-ledger/diffs/`.

---

## 9. Rules carried forward, with their numbers

- Detectable effect ≈ **5 points** on ~1,200 calls; a bearish-only subset of
  ~190 carries ±10–20 point ranges. State ranges as plain points.
- Bearish base rate **46.6%** pooled (44.9% train). Bearish precision floor for
  the falsifier: 46.6%.
- v6 train reference: **30.3%** accuracy, **+2.48 points** over luck,
  **103** bearish calls, **60.2%** right — `wrap-ups/baseline-v6-train-batch-out.md`.
  If your reproduction of v6 from the cached evals disagrees, stop and report
  before comparing anything.
- §1.3: grade `per_call_rec`, never `final_action`.
- §1.4 / firewall: the ledger is data *about the company*, from its own
  transcripts. No portfolio or position data enters.
- Do not gate on a known unfixed defect: WOLF/SPWR excluded, F2 (sector-relative
  grading) unresolved and noted once, R1–R3 open and blocking nothing here.
- Provenance for every figure: file path plus key or column.

---

## 10. Report step

**Scope boundary: report, do not decide.** Do not promote, do not reorder the
queue, do not run tune, do not amend the decision matrix. Promotion is a
`PROMOTION_GATE.md` §5 decision and happens in conversation.

Write `wrap-ups/P3-guidance-ledger-out.md`. **Reports ship in three forms**:
the `.md`, a `.docx` with real Word tables, and a published artifact page.
**Open with §0, defined terms** — at minimum: promise, ledger, grade
(met/missed/beat/unreported), load-bearing metric, bearish call, hit, dead band,
base rate, precision, coverage, flip. Plain words, before any identifier.

Open the body with this sentence, filled in:

> On ___ train calls that had a prior call on record, v6 said bearish on ___
> (___%) and was right on ___% of those; with the ledger, the candidate said
> bearish on ___ (___%) and was right on ___%. It changed its answer on ___
> calls, winning ___ of them. Of those flips, ___ were on calls whose ledger
> showed a missed or dropped promise, and ___ were not.

Then the diagnostics of §8, in order. Then one paragraph per finding.

**Close with what it means for a decision, stated both ways:** if the candidate
clears its falsifiers, what running it on tune would cost and what a pass
would allow; if it fails, which falsifier fired and what that rules out (a
ledger the analyst ignored is a different failure from a ledger that made it
trigger-happy, and the fixes are different). If nothing changes either way, say
that.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Lead with the finding. Short
sentences. Forbidden without a one-line plain definition at first use: lift,
baseline, base rate, precision, recall, confidence interval, significance,
distribution, variance, artifact, null.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. No `--break-system-packages`.
- Work on `sweep/db-corpus-baseline`.
- Provenance for every figure.
- One prompt in, one wrap-up out to `wrap-ups/P3-guidance-ledger-out.md`.
- Commit transcripts, ledger files and eval caches as they land — they are the
  durable asset.
- Running low on budget is a reason to stop cleanly, not to rush. **Pass A
  alone, validated and committed, is a useful result** — it is the input P3b,
  P4 and the exit-latency ledger all need. Write the wrap-up with what is
  done, mark the rest `pending` with a precise `next_action`, and say plainly
  that it is a partial run.
