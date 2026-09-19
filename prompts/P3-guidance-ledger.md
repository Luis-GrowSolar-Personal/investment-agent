# P3a — the guidance ledger: hand the analyst last quarter's promises

**Run ID:** `p3-guidance-ledger`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P3-guidance-ledger-out.md`
**Supersedes** the 2026-09-19 21:31 draft of this file. Provenance for every
decision below: `prompts/P3-guidance-ledger-counter*.md` (ten review
documents, two sessions). **Do not re-litigate a decision that carries a
citation to one of them.**

---

## WHAT THIS RUN BUYS — read before authorizing anything

**Most likely:** a ledger asset that every later round needs, a measured
noise floor for this model on this corpus, an answer to whether guided misses
carry forward signal, and a first test of whether the analyst can grade its
own bearish calls.

**Less likely but possible:** a headline accuracy move the instrument can
resolve.

**Anyone authorizing $130 on the expectation of the second alone is
authorizing the wrong run.**

## COST AND AUTHORIZATION — two phases, hard stop between them

**THIS RUN SPENDS REAL MONEY.** It is split so the second half is authorized
with the first half's numbers in hand.

| phase | contents | cost |
|---|---|---|
| **Phase 1** | Pass A extraction, fidelity check, ledger build, the $0 diagnostics, the pre-flight | Pass A ≤ **$45** · pre-flight ≤ **$20** |
| **hard stop** | checkpoint report to Luis. **Phase 2 does not begin without his explicit go.** | — |
| **Phase 2** | Pass B scoring, full diagnostics, wrap-up | Pass B ≤ **$70** |

**Total ceiling $130. That number requires Luis's approval before Phase 1
begins.** If this prompt is running and he has not approved $130, stop and
ask. Money commits at batch submission; every cap is checked *before*
`create()`. Pass B's per-call cost is measured on the pre-flight and the full
round projected before submission — projection over $70 → stop and report, do
not submit a trimmed batch.

**Phase 1 alone is a legitimate outcome**, not a truncation. See §7's
standalone success criterion.

**Read first, in this order:** `docs/handoffs/2026-09-19-state-of-play.md`
§0, §2, §5; `docs/architecture/PROMPT_ARCHITECTURE.md` in full (§1.1 permits
per-ticker *inputs* — this run is exactly that — and §2.3–2.5 are binding);
`docs/architecture/PROMOTION_GATE.md` §3.1 and §8;
`prompts/baseline-v6-tune-batch.md` §3–§7 (batch machinery, reused verbatim);
`wrap-ups/test4-noise-floor-v6-rerun-out.md` (the noise floor this run nets
against); `analysis/version_guard.py`; `docs/EVALUATION_PROMPT.md` (v6 —
note STUMBLE CLASSIFICATION test 1 and the MITIGATION ARGUMENT rule, both of
which this candidate feeds rather than replaces).

---

## 1. What this run is for

Today the analyst reads one transcript. When management says "gross margin
expanded to a record 50%," the analyst has no way to know revenue was guided
to $1,000M and came in at $900M, or that the margin beat never reached
operating profit. Its stumble test — "did they give guidance and miss it?" —
runs on whatever the current call happens to mention.

**P3a hands the analyst a ledger of last quarter's stated numbers, graded
mechanically against this quarter's reported numbers, before it reads the
transcript.** The analyst still decides what the misses mean. The ledger only
guarantees it sees them.

### Why this candidate and not P1

**P1 lowers the evidence threshold on what the analyst already sees, so its
extra bearish calls are weaker by construction. P3a adds evidence the analyst
never had, so its extra calls can be better-evidenced than the existing
ones.**

That distinction is what makes P3a runnable and P1 not, given Q2 (2026-09-18):
the analyst has no usable way to rank its own bearish calls, so nothing
downstream can size a trim by conviction. P1's entire case rested on the
allocator doing that sorting. It cannot. P3a does not need it to.

**Honesty caveat that travels with that claim:** P3a *can* lower precision
too, if the ledger makes the analyst reflexive rather than better informed.
That is why §6a.2's wording matters and why the 46.6% precision floor stays
as a falsifier.

### How much room the mechanism has — measured

A keyword scan of 200 random train transcripts (seed 11,
`prompts/P3-guidance-ledger-counter.md` §2a):

| | |
|---|---|
| contain forward guidance **and** a number | 197 of 200 (**98%**) |
| explicitly reference **their own prior guidance** | 54 of 200 (**27%**) |

**In roughly three calls out of four, management never compares what happened
against what it promised.** The analyst reading one transcript cannot make
the comparison — the sentence is not there. That is the gap the ledger fills,
and the ledger's leverage is concentrated in that ~73%, not spread evenly.
Stated as an expectation in §7, diagnosed in §8, never gated (guardrail 3).

### What the new fields would be, in this project's history

Test 4's v6 raw runs give 492 pairwise comparisons of the same prompt on the
same transcripts. **Pairwise `recommendation` disagreement and pairwise
graded-*direction* disagreement are identical — 62 of 492 in both cases.** Not
one flip in 492 pairs is a Trim↔Exit churn, because the analyst does not use
Exit. Combined with Q2's finding that it says "Broken" twice in 187 bearish
calls: **`ledgerMissCount`, `ledgerMaxMissPct` and `ledgerWithdrawnCount`
would be the first within-bearish gradations this analyst has ever emitted.**

### The direction picture, measured — and why this run is two-sided

v6's three answers, across 2,404 gradable calls, both splits
(`analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`):

| v6 says | share of calls | right | base rate | edge | train | tune |
|---|---|---|---|---|---|---|
| bearish | 7.8% | 59.9% | 46.6% | **+13.3** | +15.3 | +11.2 |
| bullish | 34.2% | 37.2% | 32.8% | **+4.4** | +3.6 | +5.2 |
| neutral | 58.0% | 20.6% | 20.6% | **0.0** | −0.1 | +0.1 |

**Neutral carries no information at all.** Saying "Hold" is exactly as
accurate as guessing the base rate, on both splits independently — and the
analyst says Hold on 58% of calls, 1,395 of 2,404. **Bullish carries a real
but small edge** that replicates across splits.

**So the ledger's job is not "make more bearish calls." It is to move Holds
to a committed answer when the evidence supports one — in either
direction.** A clean sweep of beats on the load-bearing metric is evidence
for the thesis exactly as a miss is evidence against it. **This run therefore
measures both directions**, while changing the prompt text on only one — see
the scope note below.

### Scope note: two-sided measurement, one-sided instruction

**The candidate prompt text (§6a) addresses misses only.** Its stumble-test
change and its LEDGER READING questions are the bearish mechanism, and that
is the single mechanism this candidate pre-registers.

**The measurement is two-sided throughout** — §5d, §5e and every diagnostic
in §8 report bullish alongside bearish. This is deliberate and it is the Q2
pattern: **measure whether beats carry signal before building a candidate
around them.** A symmetric instruction ("a beat on the load-bearing metric is
evidence for the thesis") would put two mechanisms in one candidate, and a
headline move could not be attributed to either. **Do not add it to this
round.** If §5d and §8 show beats predicting outperformance, that earns its
own pre-registered candidate.

**What this run is NOT.** Not a promotion. Does not touch the allocator, the
trend layer, the simulator, or the holdout. Does not rank misses or weight
metrics. Scores one candidate on train, reports, stops.

---

## 2. Ground rules — the do-not list

1. **Train split ONLY** — the 57 companies in
   `analysis/data/corpus_v2/SPLIT_V7_RESERVE_REPLACEMENTS.json` → `train`,
   **after alias resolution (§4, Step 0f)**. Do not score tune. Do not touch
   the holdout. Assert zero intersection with both before any submission.
2. **Version guard before any scoring call.** Runs under
   `PROMPT_CANDIDATE=v6+P3a`; the candidate must be registered in
   `docs/architecture/VERSION_REGISTRY.json` first (Step 0d). Guard fails or
   candidate unregistered → stop, submit nothing.
3. **Same model as both baselines: `claude-sonnet-4-6`, pinned.** If it is
   unavailable, **stop and report** — do not substitute.
4. **Per-phase caps** as in the header. Counted before `create()`.
5. **Price cache is `analysis/data/corpus_v2/scorer_price_cache_v1.json`.**
   Never `analysis/data/price_cache.json` — a stale 66-ticker cache from an
   earlier era that the 2026-09-17 prompt named by mistake. State the path you
   pass to the scorer; it must be this string.
6. **Exclude `WOLF` and `SPWR` entirely** — every call, not only those missing
   price data. Partial exclusion silently inflated a bearish count from 84 to
   97 on 2026-09-18.
7. **Do not modify `analysis/analyst_direct_scorer.py`** (import from it) and
   do not edit v6 in place. The candidate is a **new file**,
   `docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`, so v6 stays
   byte-identical for the guard.
8. **No DB writes. No trend layer. No `final_action`.** Grade `per_call_rec`.
9. **macOS Tahoe, zsh.** `python3`, never `python`. Never
   `--break-system-packages`. No `apt`. `brew` only if a system tool is
   missing.
10. **A diagnostic that contradicts an expectation in this prompt is a
    finding, not a reason to stop.** The predictions in §7 are predictions.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/p3-guidance-ledger/`. **Write
`progress.json` as the very first action, before reading anything.**

- `progress.json` — `prompt_sha256`, `driver_commit`, per-step status,
  `next_action`, `notes[]`, `phase` (1 or 2), and **`batch_id_pass_a` /
  `batch_id_preflight` / `batch_id_pass_b` written and committed the instant
  each `create()` returns**, before polling. The batch id is the recovery key;
  results persist 29 days.
- `extractions.jsonl` — one line per Pass A result, keyed by `custom_id`.
- `scores.jsonl` — same for Pass B.
- `findings.md` — append-only, each finding the moment it is established.

On resume with matching `prompt_sha256`: if a batch id exists, **submit
nothing** — retrieve and continue collecting. **Resuming into Phase 2 requires
Luis's recorded go in `progress.json`.**

---

## 4. Step 0 — hygiene, registration, guard, aliases

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`.

**0b.** Write and commit the driver as its own commit before it produces
output: `analysis/p3_guidance_ledger_driver.py`. Reuse the batch machinery
from `analysis/baseline_v6_tune_batch_driver.py` by import; do not rewrite it.

**0c. Pre-register in `docs/architecture/PROMPT_ARCHITECTURE.md` §2.2**, as a
new block under P1's, dated, **before any spend**, with exactly §7's content.
Commit it.

Also add **P3b** — the analyst's own prior watch condition as a second ledger
input — as *named but not run*. **The reason, which must be written down:**
naming the follow-on now commits it before P3a's per-call diffs exist, so no
later session can back its next candidate out of those diffs and call it
design. That is the same discipline §2.6 imposes on the auto-iterate loop.
**Add the prohibition explicitly:** any candidate other than P3b derived from
reading P3a's diffs goes through the §2.6 split-half screen before it may
touch tune.

**0d. Write and register the candidate.** **The candidate file is created
HERE, to §6a's specification** — §6a describes it, it does not create it. It
must exist and be committed before 0e, because Step 0f's pre-flight scores
200 calls with it and the registry records its hash. Write
`docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md` per §6a, commit it, then
register it in `VERSION_REGISTRY.json` as a *candidate*, not a promotion: key
`v6+P3a`, path
`docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`, sha256, parent `v6`,
status `candidate`, date. Run `python3 analysis/version_guard.py` under
`PROMPT_CANDIDATE=v6+P3a`, record the warning. Commit.

**Two prompts run in this batch, so two guard assertions are required and both
are recorded.** The candidate (eligible arm, no-miss arm, empty-ledger arm,
Pass B) is guarded against the **candidate** hash. **The 21a pure-noise arm
submits unmodified v6 and is guarded against the promoted v6 hash.** A session
that runs one guard for the whole batch will either block 21a or let a wrong
file through for it.

**0d-bis. The extraction prompt is a versioned artifact too.** The Pass A
extraction prompt determines every ledger row. Write it to
`docs/prompts/candidates/EXTRACTION_PROMPT_P3A.md`, commit it, and record its
sha256 in both `SCORING_PROTOCOL_P3A.json` and `progress.json`. Without this
the ledger is unreproducible from the day that prompt is next edited.

**0e. Register the scoring protocol** at
`analysis/data/corpus_v2/SCORING_PROTOCOL_P3A.json` — new file — carrying
split, resolved company list, manifest and split sha256s, candidate and parent
hashes, the extraction-prompt sha256, pinned model with an assertion it equals both baselines'
`model_version_pinned`, grading field `per_call_rec`, eval-cache paths, the
price-cache path from rule 5, request caps, disjointness assertion.

**0f. Alias resolution — HARD STOP.** Resolve every split symbol through
`analysis/data/corpus_v2/TICKER_ALIASES.json` (`original_symbol` →
`working_symbol`) **before enumerating anything.** The split names `ANTM`,
`VIAC` and `GOOGL`; transcripts and eval files are stored under `ELV`, `PARA`
and `GOOG`. Unresolved, Pass A silently skips 46 calls and Pass B's join to
v6's cached evals lands on a corpus 46 calls smaller than its own baseline.

Assert at runtime — re-establish these counts, do not copy them:

- the resolved train symbol set yields **1,240** transcript files across
  **56** companies — *unresolved it yields 1,194 across 54, and that 46-call
  gap is exactly the bug this step exists to prevent*;
- every one of the **1,240** eval files in
  `analysis/data/evals/v6_claude-sonnet-4-6/` maps to a resolved symbol, one
  per transcript;
- **1,184** resolved train calls have a predecessor (1,240 − 56 first calls);
- **`MAXN` resolves to no files under any symbol form. Expected — record it,
  do not fail on it.** It is why both baselines report 56 of 57 companies.

Any *other* unmatched symbol is a hard stop. This is the eighth instance of
this project's signature failure — an artifact built against one set of keys
while the consumer reads another.

---

# PHASE 1

## 5. Step 1 — Pass A: extract promises and actuals

**If the budget only allows one paid pass, this is the one.** The ledger is a
durable asset reused by P3b, P4 and the exit-latency work; scoring can be
re-run later.

### 5a. What is extracted, per transcript

One batch call per resolved train transcript
(`analysis/data/corpus_v2/transcripts/<RESOLVED_TICKER>/<call_date>.json`).
The extraction prompt is short, system-cached, and returns JSON with:

**`reported`** — what this call says happened *this* quarter, one entry per
metric management states a number for:
`{metric, value, value_as_written, unit, framing, basis (GAAP|non-GAAP|unspecified), fiscal_period, quote}`.

**`guided`** — what this call promises for a *future* period, one entry per
explicit number or range:
`{metric, low, high, low_as_written, high_as_written, unit, framing, basis, fiscal_period, one_sided, quote}`.

**`stated_intents`** — non-numeric commitments with a date
(`{intent, by_fiscal_period, quote}`).

**`retractions`** — explicit withdrawals or suspensions of prior guidance
(`{metric_or_all, quote}`). See the `withdrawn` grade in 5c.

**Rules the extraction prompt must carry:**

- Only explicit numbers and ranges are guidance. "Strong growth" is not a
  promise; "40 to 42% gross margin" is.
- **Periods are extracted as fiscal labels** (`Q3 FY2024`), never as "next
  quarter." See 5c.
- Metric names normalized to a fixed list defined in the driver and committed
  before running: revenue, gross_margin_pct, operating_margin_pct,
  operating_income, eps, free_cash_flow, capex, backlog, unit_shipments,
  customer_count, cash_balance, other (raw name kept).
- **Both `value` and `value_as_written` are mandatory.** "$1.2 billion" and
  `1200000000` are the same value and different strings; the fidelity check
  in 5b needs the string as written.
- **The quote is mandatory.** An entry without one is dropped and counted.
- **`framing` is mandatory on every entry: `level` | `growth_pct` |
  `margin_pct`.** Guidance is very often stated as growth ("revenue growth of
  20–22%") while the actual is stated as a level ("revenue of $912M, up
  14%"), or the reverse. Without `framing` the join sees two different things
  and grades `unreported` or `basis_mismatch` at scale — and `unreported`
  feeds both `N_eligible` and the stumble test, so this is **the single most
  likely source of reflexive trims, and it would look like the mechanism
  firing.**
- Basis is recorded, never reconciled. A non-GAAP guide against a GAAP actual
  is `basis_mismatch`, flagged, not a miss.

### 5b. Validate the extractor mechanically, then by eye

**The fidelity check — $0, runs on every extracted call, not just the
sample.** For every entry in `reported`, `guided` and `retractions`:

1. the `quote` appears as a **verbatim substring** of the transcript text
   after normalization — collapse whitespace, lowercase, unify curly/straight
   quotes and dash variants, strip trailing punctuation inside the quote.
   **Nothing fuzzier.**
2. every `*_as_written` value appears **verbatim inside that quote**;
3. each parsed `value` is a plausible parse of its `*_as_written` string —
   unit and scale agree.

An entry failing 1 or 2 is **dropped and counted as a quote miss**. An entry
failing 3 is **dropped and counted separately as a mis-parse** — invention and
mis-parsing are different defects with different fixes. Report both rates,
overall and per ticker.

**HARD STOP: a drop rate above 5% on the validation sample means the
extractor is inventing numbers.** Fix and re-validate before submitting the
batch. Report the final rate in the wrap-up whatever it is — **it is the
single number that says how much the ledger can be trusted.** If the rate is
high because of normalization rather than invention, the per-ticker breakdown
will show it clustering by vendor formatting; report that, do not tune it
away.

**Then the eyeball pass, on 15 transcripts** — four established, four
speculative, three pre-revenue, two from the failures stratum, and **two with
no numeric guidance at all** (confirm the extractor returns empty rather than
inventing). Check: guidance kept apart from actuals; fiscal period correct;
basis recorded. **Any failure → fix the extraction prompt and re-validate. Do
not submit ~1,240 requests through an unvalidated extractor.** Record measured
per-call cost; implied Pass A total over $45 → stop and report.

### 5c. Build the ledger — $0, driver only

For every call N+1 with a predecessor, the driver joins:

**Join on fiscal label, not on "next call."** Every transcript carries `year`
and `quarter`; use them. **Cheap insurance, not a load-bearing correction** —
measured, 7 of 1,184 consecutive pairs are not exactly one fiscal quarter
apart, all of them two quarters. Mark those ledgers `gap`, carry only guidance
whose period still covers N+1, report the count. Do not spend a step defending
this case.

- each `guided` entry from call N whose fiscal period covers N+1, **and from
  any earlier call whose period covers N+1** — the original promise is kept
  even if N revised it; both recorded as `original` and `latest_revision`;
- the matching `reported` entry from N+1 on the same metric, **framing** and
  basis. **The driver grades level-to-level and growth-to-growth.** It
  converts between framings **only when the prior-year base is itself in the
  ledger**, and records the conversion on the row. Report the count of
  framing conversions and framing mismatches as their own line.
- **the grade**, one of six:

  | grade | meaning |
  |---|---|
  | `met` | actual inside [low, high] |
  | `missed` | below low. Carries `miss_pct = (low − actual) / low` |
  | `beat` | above high. Carries `beat_pct` |
  | `unreported` | guided, and the metric is **absent from the call entirely**. **A metric present in any numeric framing is never `unreported`** — before assigning this grade the driver searches the transcript for the metric's name and synonyms, and records that it looked |
  | `withdrawn` | the prior promise exists and N+1 **explicitly retracts or suspends it** |
  | `basis_mismatch` | guided and reported on different bases |

- **`range_width_pct = (high − low) / low`** beside every graded promise.
  **Point guide (`high == low`) → `0`, not null** — zero is the true value and
  the case where a small miss counts most. **One-sided guide → `null`, marked
  `one_sided`, graded against the stated bound alone; never synthesize the
  missing bound.**
- **Full-year guidance is `pending`**, carrying its original and latest
  revision, and is graded **only at the fiscal-year-end call** — identified
  from the transcript's own `quarter` field, **never the calendar**; this
  corpus contains non-calendar fiscal years. A **downward revision** of FY
  guidance mid-year is counted by `ledgerRevisedDownCount`: it is management
  admitting the year is worse than promised, in advance, and it is the one
  ledger entry that is forward-looking rather than retrospective.
- derived lines where inputs exist: operating expense = gross profit −
  operating income (guided and actual); the gap between the % change in
  operating income and the % change in EPS;
- `stated_intents` from N due by N+1, with the driver marking only whether
  N+1 mentions them (the analyst judges whether they were kept).

**Why `withdrawn` is its own grade and not a flavour of `unreported`.**
Measured: transcripts containing explicit guidance-withdrawal language run at
**7.3% across the train corpus and 17.0% in 2020** (COVID). A company that
guides and then publicly retracts has not missed and has not gone quiet. If
withdrawal grades as `unreported`, and `unreported` leans toward a stumble,
the candidate acquires a systematic bearish tilt concentrated in a single
year whose forward returns are unusual — **a confound that would look like the
ledger working.**

Write `analysis/data/corpus_v2/ledger/<TICKER>/<call_date>.json` and a flat
`ledger_summary.csv` (one row per promise). Commit. Report: calls with a
non-empty ledger; promises per call (median and range); share of promises at
each of the six grades; **the full grade-by-year table** — the 2020 argument
above applies to `missed` just as much as to `withdrawn`.

### 5d. The $0 diagnostic — run it here, before the pre-flight

**Two symmetric questions, same code, same data, $0. Run both.**

**5d-i. Does a mechanically graded miss predict underperformance?** Split
predecessor-bearing calls by whether the ledger shows ≥1 `missed`,
`unreported` or `withdrawn` on a guided metric, and compare the share that
underperformed the S&P by more than 5 points over the next two quarters —
against the **46.6%** bearish base rate.

**5d-ii. Does a mechanically graded beat predict outperformance?** Split by
whether the ledger shows ≥1 `beat` **and no** `missed`/`unreported`/
`withdrawn`, and compare the share that outperformed the S&P by more than 5
points — against the **32.8%** bullish base rate.

**Report both with ranges, and report the size of each population.** 5d-ii is
the cheapest possible answer to whether a bullish candidate is worth
building; it costs nothing and it arrives before any of it is committed.

**Neither is a gate** — a prediction is not a gate, and the analyst may use
the ledger in ways a bare split cannot see. But they are the cheapest read on
whether the mechanism has raw material in each direction, and they arrive at
the one moment when the next ~$58 has not been committed. **Report 2020
separately for both.**

### 5e. The gate — on the flip population, not on guidance prevalence

**Only the bearish population is gated in this round**, because only the
bearish mechanism is in the prompt text (§1 scope note). The bullish
populations below are measured and reported.

**Report** ledger coverage (share of predecessor-bearing calls with ≥1 graded
promise) as a finding, **with no threshold attached** — at 98% guidance
prevalence a coverage gate cannot fire and would guard the wrong quantity.

**Gate on this instead.** Count calls where the ledger shows ≥1 `missed`,
`unreported` **or `withdrawn`** on a guided metric **and** v6's cached call
was not already bearish. Call it `N_eligible`.

**`withdrawn` belongs in `N_eligible`, not in the no-miss arm.** §7 expects
flips on withdrawn calls and diagnostic 8.1 groups them with misses. If they
sit in the no-miss arm, a withdrawn call flipping bearish — the mechanism
working exactly as designed — counts as a leak, and enough of them fire the
mechanism-failure stop on a candidate that is fine.

> **If `N_eligible` < 150, stop before the pre-flight and report.** Even
> complete conversion would not clear the ~100-flip floor with margin. Commit
> the ledger and the finding; Pass A stands on its own.

**The bullish mirror — `N_eligible_bull`, reported, never gated.** Count
calls where the ledger shows ≥1 `beat` and **no** `missed`/`unreported`/
`withdrawn`, **and** v6's cached call was not already bullish. This is the
population a two-sided candidate would act on, and its size is the other half
of the answer §5d-ii starts. **It is not gated in this round** — this
candidate's prompt text does not address beats (§1 scope note), so a low
count is information about a future candidate, not a reason to stop this one.

Also count and **report, never gate**, `N_reassure` — all graded promises
`met`/`beat` and v6 said bearish. The ledger is *reassuring* there, and a flip
to Hold is through the mechanism. A high flip rate on these is information
about whether v6's existing trims were over-reactions, which bears on the
state of play's open question about the 89 Trim-with-Intact-thesis calls.

### 5f. Pre-flight — four strata, ~375 calls, ~$15

| stratum | n | purpose |
|---|---|---|
| from `N_eligible` | 125 | the candidate's own population |
| ledger-bearing, **no miss, no withdrawal, v6 not already bearish** | 75 | the third falsifier — is it moving calls with no miss? Also supplies the bullish read below |
| **pure noise (21a)** | 120 | **v6 re-scored unchanged** — the floor |
| **instruction effect (21b)** | all empty-ledger first calls (~54) | new prompt text with no ledger content |

**Two different things are called "tier" in this project. Keep them apart.**

- **stratum** — the corpus construction strata **S1–S5**, present on every
  company in `CORPUS_MANIFEST_V7.json`. **All netting and all noise reporting
  use stratum.**
- **tier** — the two-way established / speculative classifier from §1.2.
  **Used only for diagnostic 8.7.** Never for netting.

Define both in §0 of the wrap-up.

**21a, the pure-noise arm.** 120 train calls already in the v6 eval cache,
**re-scored with the unmodified v6 prompt**, same model, same batch, guarded
against the promoted v6 hash. Their disagreement with their own cached v6 call
is this run's measured noise floor, free of any instruction effect. **Draw
them proportional to the train corpus's S1–S5 composition**, and report the
overall rate plus the per-stratum breakdown with ranges.

**Do NOT pool with Test 4, and do not import its per-stratum rates.** Test 4's
four-way megacap/large/mid/small_micro split is a **hardcoded 15-ticker list
in `analysis/test4_noise_floor.py`, not a field on anything** — and only **6
of those 15 tickers are in the train split** (1 megacap, 0 large, 1 mid, 4
small/micro). Its rates were measured on a tech-and-solar universe that barely
overlaps this corpus of 56 companies spanning healthcare, utilities, insurance
and media. **21a is the sole source of the noise floor.** Test 4's 12.8%
overall figure is context for sizing expectations, not an input to the
subtraction.

**What the arm size buys.** 120 calls spread over five strata leaves roughly
20–30 per stratum, and a rate measured on 25 carries a range of about ±16
points. **Therefore: net on the overall 21a rate, and use the per-stratum
breakdown only as a check on whether one global rate is defensible.** If one
stratum's rate sits far outside the others with a range that excludes the
overall figure, report that and net that stratum separately. **No gate turns
on a single stratum's rate.**

Why this and not the empty-ledger calls: those conflate noise with the
instruction effect of the new prompt text, they cluster entirely in the corpus
start (2020, the atypical year), and **a single scalar cannot represent this
quantity** — v6's pairwise flip rate by tier is large 3.1%, mid 6.7%,
small/micro 19.6%, megacap 21.5%, a sevenfold spread whose *shape* is not even
stable across prompts (under v10+auto1 it was small/micro 37.5%, megacap
8.5%). Test 4's own wrap-up: *"a single scalar noise-floor number does not
exist here."*

**Why 21a and not an imported figure.** 21a is the comparison P3a actually
makes — a weeks-old cached call against a fresh one, batch against
synchronous, drift under an undated model alias. Test 4's within-session pairs
are a lower bound on it and a different universe besides. If 21a comes out
well above 12.8%, that excess is drift plus batch effect, it belongs in the
floor, and it is a finding worth its own line.

**21b, the instruction-effect arm.** Keep the empty-ledger first calls, but
**do not call them a noise floor.** Their flip rate **minus** 21a's is the
effect of the new prompt text with no ledger content. State the
2020-clustering caveat beside it.

**Projection and stop rules.**

- Scale the eligible arm's flip rate by `N_eligible / 1,184` before comparing
  it to the ~100-flip floor. **Net of 21a first** (see the netting rule in §7).
- **Mechanism-failure stop:** stop before Pass B if the no-miss arm's
  **bearish-direction** flip rate (neutral/bullish → bearish) is **greater
  than or equal to** the eligible arm's bearish-direction flip rate.
  **Compute both rates over v6-non-bearish calls only.** A bearish-direction
  flip is impossible on a call v6 already called bearish, so leaving those in
  the no-miss denominator pads it with unflippable calls, biases its rate
  down, and makes the stop *less* likely to fire than it should be. The
  eligible arm already excludes them by construction; the no-miss arm must
  too.
- **The no-miss arm does two jobs and they must not be mixed.** A
  **bearish-direction** flip there is a leak — the candidate moving calls
  with no miss — and it is what the stop above tests. A **bullish-direction**
  flip there (neutral → bullish on a clean-beat ledger) is **not a leak**;
  with a one-sided instruction it is unprompted, and it is the earliest
  evidence that a two-sided candidate would work. **Report bullish-direction
  flips in the no-miss arm separately, as a finding, and never let them enter
  the stop.** Report the same for `N_eligible_bull` calls that fall in this
  arm.
  Reassurance flips (bearish → neutral/bullish) are reported for both arms and
  **never enter the stop** — an `N_reassure` call flipping to Hold is the
  mechanism working, and counting it would trigger a false stop on a candidate
  that is fine. Deliberately coarse: it fires only on unambiguous failure,
  never on noise.
- Confirm the **six** new fields (§6a.4) populate, and that the ledger block did not push
  completions into `max_tokens` — **log `stop_reason`; v9 was corrupted exactly
  this way.**

## PHASE 1 CHECKPOINT — STOP HERE

Write the checkpoint report and **stop**. It carries: fidelity drop rates
(quote miss and mis-parse, overall and per ticker); ledger coverage; the
grade-by-year table; `N_eligible` and `N_reassure`; 5d's
miss-predicts-underperformance split with 2020 separate; all four pre-flight
arms' flip rates with ranges, per tier; the netted projection; and the
projected Pass B cost.

**Phase 2 begins only on Luis's explicit go, recorded in `progress.json`.**

---

# PHASE 2 — requires Luis's recorded go

## 6. Step 2 — Pass B: score the candidate

### 6a. The candidate prompt — the only text that changes

`docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md` is v6 plus **exactly**
these changes. Diff it against v6 and include the diff in the wrap-up.

**1. A new input section, in the user message ahead of the transcript** (so
the cached system block is unchanged and the round stays at batch cost):

```
---PRIOR-CALL LEDGER---
metric | original guide | latest revision | actual | grade | miss_pct | range_width_pct | quote
(derived lines)
(full-year promises, pending)
(stated intents due this quarter)
(retractions this quarter)
---END LEDGER---
```

For a first call: `No prior call on record.`

**2. STUMBLE CLASSIFICATION, test 1 gains:**

> *"Consult the PRIOR-CALL LEDGER first. Apply test 1 on the basis of the
> ledger grade. Weigh `miss_pct` against how tightly the company itself
> guided (`range_width_pct`) — a miss small relative to the company's own
> stated precision may not be a stumble; say which and why. A promise graded
> `unreported` — guided last quarter, no number this quarter — is a question
> you must answer explicitly: does the transcript account for the omission?
> Say which, and why. An unexplained omission on a metric the thesis rests on
> is a stumble; an explained one is not. A promise graded `withdrawn` is
> neither a miss nor a pass: it is a credibility event, and the MITIGATION
> ARGUMENT rule already tells you how to weigh a management claim against its
> own track record."*

**No fixed numeric threshold anywhere in this text.** A threshold would be
the ranking decision this candidate exists to avoid. **And no qualitative
phrase standing in for one** — "inside ordinary rounding" and its cousins are
worse than either a stated threshold or no threshold, because every call
fills the number in differently and nobody can see that it happened. That is
the v9 failure shape. Show the magnitude; let the analyst weigh it.

**3. A new short section before RECOMMENDATION, LEDGER READING**, three
ordered questions: *Which ledger promise is the one the thesis rests on? Was
it met? If missed, does any beat elsewhere repair the specific mechanism that
failed — or is it a different thing?* — followed by the existing mitigation
rule in one line: a beat on one line does not lend credibility to a miss on
another.

**4. Six new structured fields, diagnostics only, never gated:**
`ledgerLoadBearingMetric` (string|null), `ledgerLoadBearingOutcome`
(`met|partial|missed|none`), `ledgerMissCount` (int), `ledgerMaxMissPct`
(float|null), `ledgerRevisedDownCount` (int), `ledgerWithdrawnCount` (int).

**Nothing else changes.** The decision matrix is untouched. No weights, no
scoring of misses, no new action labels. **If you find yourself adding a rule
about *how much* a miss matters, stop** — that is the design decision this
candidate exists to leave with the analyst.

### 6b. Full round

One batch of all resolved train calls, including empty-ledger first calls so
the eval cache is complete. Request shape as in `baseline-v6-tune-batch.md`
§7 with the ledger block prepended to the user content. Eval cache to
`analysis/data/evals/v6+P3a_claude-sonnet-4-6/`. Score with
`analysis/analyst_direct_scorer.py` against the corpus_v2 price cache.
**`--allow-partial-coverage` is forbidden.**

---

## 7. Pre-registration — copy into PROMPT_ARCHITECTURE.md §2.2 at Step 0c

**P3a — guidance ledger, registered [date].**

- **Change.** Prepend to each call a mechanically graded table of the promises
  the prior call made and what this call reported against them; point stumble
  test 1 at it; ask which promise the thesis rests on. No change to the
  decision matrix.
- **Expected to move.** Bearish call rate up, concentrated on calls whose
  ledger shows `missed`, `unreported` or `withdrawn` on a guided metric.
  Bearish precision holds above the 46.6% base rate. Gap over luck up.
- **Expected concentration.** Flips concentrate in the ~73% of calls that do
  not already discuss their own prior guidance. *Diagnostic, not a gate.*
- **Expected of the neutral pile.** v6's neutral calls carry **zero** edge
  over their base rate on both splits, on 58% of calls. The ledger should
  convert some of them into committed answers that beat their base rate.
  Report the neutral share before and after. *Diagnostic, not a gate.*
- **Measured but not instructed: the bullish side.** §5d-ii,
  `N_eligible_bull`, bullish precision against **32.8%**, and bullish
  movement in the clean-beats group are all reported. **This candidate's text
  does not address beats**, so any bullish movement is unprompted. It
  falsifies nothing here and pre-registers nothing for later — it is the
  evidence base for deciding whether a two-sided candidate is worth writing.
- **Predicted flip count: 150–300 net** of the tier-weighted pure-noise rate,
  with the raw count reported beside it.
- **Falsified if** — all stated **net**:
  - fewer than ~100 flips net of the tier-weighted pure-noise rate (the
    instruction did not take); **or**
  - bearish precision at or below 46.6% (reflexive trims, not
    better-evidenced ones) — **note this is a bearish-only falsifier by
    design; bullish precision moving in any direction falsifies nothing in
    this round**; **or**
  - flips concentrate in calls whose ledger shows *no* miss (acting through
    something other than its mechanism); **or**
  - the instruction-effect arm (21b) exceeds the pure-noise arm (21a) by more
    than its own range — the new prompt text is moving calls without a
    ledger. **Report this one prominently; it is a confound on the headline.**
- **Runs on.** Train. Tune only if it clears, and only once.
- **Pass A standalone success criterion.** Pass A succeeds on its own if the
  fidelity drop rate is under 5% and the ledger covers ≥90% of resolved
  predecessor-bearing train calls, **whether or not Pass B runs.**

### What the headline can and cannot resolve — state this before the run

**Two denominators, and they are not the same. Anchor every figure to the
right one, and re-derive both at runtime rather than copying them.**

- **Flip population — 1,184**, the resolved predecessor-bearing train calls
  (§0f). *Not 1,140 — that is the pre-alias count and it is wrong.* Flip counts, noise counts and `N_eligible` are all shares of this.
- **Accuracy denominator — the gradable train set, ~1,236** (v6's train
  baseline). Pass B scores every train call, so the headline accuracy and the
  gap over luck are shares of this, not of 1,184.

Accuracy change = `real flips × (2 × win rate − 1) / 1,236`. Noise flips win
about half the time, so they add variance without adding expected movement.
The right comparator is **§2.4's paired "smallest visible gain" floor at the
*observed* count**, not the flat ~5-point single-prompt detectable effect:

| observed flips | real flips | move at 65% | move at 70% | §2.4 paired floor |
|---|---|---|---|---|
| 200 | 48 | 1.2 | 1.6 | ~3.2 |
| 250 | 98 | 2.4 | 3.2 | ~3.5 |
| 300 | 148 | 3.6 | **4.8** | ~3.9 |
| 365 | 213 | **5.2** | 6.9 | ~4.3 |

Flips and real flips are counts out of the **1,184** flip population; the move
is a share of the **1,236** accuracy denominator. Expected noise flips:
**12.8% × 1,184 ≈ 152**, range 81–227.

**A detectable headline needs roughly 300+ observed flips winning at ~70%,
which sits at the top of the predicted range. The likely outcome is a
headline below resolution. That is not a failed run.** The decision rests on
the diagnostics that bypass the headline — the mechanism check, bearish
precision against the 46.6% floor, 5d's split, and the Q2 re-run — and §8
reports those first. §2.4's floor is binomial and therefore optimistic
against the ticker-block bootstrap.

### The netting rule

**Noise corrupts counting what changed; it does not corrupt measuring whether
the answers got better.** The accuracy figure and the gap over luck are
unbiased by run-to-run instability **provided a noise flip wins half the
time** — 21a measures that per tier, and **that check is what licenses this
claim.** If the cached v6 draw is systematically luckier than a fresh one, the
headline carries a bias of `noise flips × (2·w_noise − 1) / 1,236`: at 152
noise flips and a 45% noise win rate, −1.2 points, a quarter of the
detectable effect, from nothing.

Every flip count is reported **raw, and net of 21a's measured rate**, with
the per-stratum breakdown reported alongside and used to net a stratum
separately where its range excludes the overall figure (§5f). §2.4's ceiling
applies to the net count.

**Win rate among flips is netted too:**

> real-flip win rate = (observed wins − noise flips × noise win rate)
>                      ÷ (observed flips − noise flips)

with both taken from 21a — overall, or per stratum where §5f says a stratum
needs netting separately.

> **Guard.** Report the netted win rate only when `observed flips − noise
> flips` exceeds **100** *and* exceeds the upper end of the noise count's own
> range (**~227**). Below that, report the raw win rate, the noise win rate, and
> the netted point estimate marked **"unstable, denominator too small"** —
> never as the headline. At 170 observed flips a single call moves the netted
> figure by four points; below the noise count the arithmetic is meaningless.
> **This guard will probably fire**, since it needs roughly **380** observed
> flips and the prediction tops out at 300. **That is the correct outcome, not a
> defect** — §10's opening sentence takes the raw figures with the noise
> figures beside them.

**Caveat, one line where the netting is defined:** noise flips and real flips
are not disjoint — a call can be one the ledger moved *and* one resampling
would have moved. The subtraction assumes independence and no overlap. At
these rates it is a reasonable first-order correction, and it biases the net
count. Treat the net figure as an estimate with a known simplification, not
as arithmetic truth.

**P3b — own prior thesis, named, not run.** Add the analyst's own "measurable
condition that would change this recommendation" from call N to the ledger at
N+1. Sequential by construction, so it cannot batch; deferred. Named now to
commit the follow-on before P3a's diffs exist (§0c).

---

## 8. Required diagnostics — ordered so the headline-independent ones come first

1. **The mechanism check.** Split ledger-bearing calls four ways: ≥1
   `missed`/`unreported`/`withdrawn` on a guided metric; **clean beats
   (`N_eligible_bull` plus `N_reassure`)**; ledger empty; and `gap`-marked.
   For each, report **bearish and bullish rates separately** — v6 rate and
   hit rate, P3a rate and hit rate, flip count raw and net, **split by flip
   direction**. **P3a's bearish movement should concentrate in the first
   group.** Equal bearish movement across all four means the ledger is not
   what moved it. **Any bullish movement in the clean-beats group is
   unprompted by this candidate's text and is a finding for the next one.**
2. **Precision in both directions**, with ranges: bearish against the
   **46.6%** base rate, **bullish against the 32.8% base rate**, and
   **neutral against its own 20.6% base rate**. v6's reference edges are
   +13.3, +4.4 and 0.0 respectively. **The neutral row is the one to watch:
   58% of v6's answers carry no information, and the ledger's value is
   largely whether it converts those into committed answers that beat their
   base rate — in either direction.**
3. **5d-i and 5d-ii restated post-scoring** — misses against
   underperformance, beats against outperformance.
4. **The Q2 re-run** on `ledgerMissCount`, `ledgerMaxMissPct`,
   `ledgerWithdrawnCount`, `ledgerLoadBearingOutcome`, reusing
   `analysis/q2_bearish_strength_driver.py`. **Train only, therefore discovery
   only** — there is no tune arm to confirm on until P3a earns a tune run.
   **Rank the four axes and write predictions into `findings.md` before
   looking at the outputs**, per Q2's own rule. The wrap-up says plainly that
   a train-only separation is a candidate, not a result. **Five of six axes
   reversed last time; these get no exemption for being new.**
5. **Flip count and win rate among flips**, raw and net per §7, with §2.4's
   ceiling table alongside. Restricted to ledger-bearing calls.
6. **The confusion table**, both prompts.
7. **By tier** (established / speculative) — §1.2 says inventory means
   different things by class, and so will a 10% revenue miss.
8. **`ledgerLoadBearingMetric` frequency table** — which metrics the analyst
   says theses rest on. Free input for P4's template design.
9. **Grade-by-year table for all six grades**, with 2020 reported separately
   throughout, including in diagnostics 1 and 4.
10. **Per-call diffs to disk**,
    `analysis/data/run_state/p3-guidance-ledger/diffs/`.

---

## 9. Rules carried forward, with their numbers

- Detectable effect ≈ 5 points on ~1,200 calls for a single prompt against
  luck; **for this paired comparison use §2.4's floor at the observed flip
  count.** A bearish-only subset of ~190 carries ±10–20 point ranges. State
  ranges as plain points.
- Base rates, pooled across both splits, from
  `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`:
  **bearish 46.6%** (44.9% train), **bullish 32.8%**, **neutral 20.6%**.
  v6's edges over them: **+13.3**, **+4.4**, **0.0**. Bearish precision
  falsifier floor: 46.6%.
- v6 train reference: **30.3%** accuracy, **+2.48 points** over luck, **103**
  bearish calls, **60.2%** right —
  `wrap-ups/baseline-v6-train-batch-out.md`. **If your reproduction from the
  cached evals disagrees, stop and report before comparing anything.**
- v6 run-to-run pairwise flip rate: **12.8%, range 6.8–19.2%**, ≈152 noise
  flips on 1,184 calls — `wrap-ups/test4-noise-floor-v6-rerun-out.md` and
  `analysis/test4_noise_floor_v6/raw/*.json`. **Context for sizing
  expectations only.** Only 6 of Test 4's 15 tickers are in train, so the
  number actually subtracted is 21a's, measured on this corpus (§5f).
- §1.3: grade `per_call_rec`, never `final_action`.
- §1.4 / firewall: the ledger is data *about the company*, from its own prior
  transcripts, strictly backward-looking. No portfolio or position data.
- Do not gate on a known unfixed defect: WOLF/SPWR excluded; F2
  (sector-relative grading) unresolved, noted once; R1–R3 open, blocking
  nothing here.
- Provenance for every figure: file path plus key or column.

---

## 10. Report step

**Scope boundary: report, do not decide.** Do not promote, do not reorder the
queue, do not run tune, do not amend the decision matrix. Promotion is a
`PROMOTION_GATE.md` §5 decision and happens in conversation.

Write `wrap-ups/P3-guidance-ledger-out.md`. **Reports ship in three forms**:
the `.md`, a `.docx` with real Word tables, and a published artifact page.
**Open with §0, defined terms** — at minimum: promise, ledger, the six grades,
load-bearing metric, bearish call, **bullish call, neutral call**, hit, dead
band, base rate, precision, coverage, flip, **flip direction**, noise flip,
net flip, **stratum vs tier**. Plain words, before any identifier.

Open the body with this sentence, filled in:

> On ___ train calls that had a prior call on record, v6 said bearish on ___
> (___%) and was right on ___% of those; with the ledger, the candidate said
> bearish on ___ (___%) and was right on ___%. It changed its answer on ___
> calls raw, of which about ___ are expected from run-to-run noise, leaving
> ___ net. Of the flips, ___ were on calls whose ledger showed a missed,
> dropped or withdrawn promise, and ___ were not. On the other side, a
> mechanically graded beat predicted the stock beating the S&P by more than 5
> points ___% of the time against a base rate of 32.8%, and the share of
> calls answered "Hold" moved from 58.0% to ___%.

Then §8's diagnostics in order. Then one paragraph per finding.

**Caveats that must appear.** The input-length confound: P3a's calls carry a
longer user message than v6's, so part of any movement could be "more
context" rather than "this context." The empty-ledger calls control for *no
ledger*, not for *ledger-shaped filler*. **No third arm is being built** — the
confound is recorded, not resolved.

**Close with what it means for a decision. Three questions, answered
separately:** (i) did the bearish mechanism work — if the candidate clears
its falsifiers, what a tune run would cost and what a pass
would allow; if it fails, which falsifier fired and what that rules out — a
ledger the analyst ignored is a different failure from a ledger that made it
trigger-happy, and the fixes are different. (ii) **Do beats predict
outperformance** — 5d-ii's answer, and whether a two-sided candidate is worth
pre-registering. (iii) **Did the neutral pile shrink, and did what came out
of it beat its base rate** — this is where 58% of the analyst's answers live
and where they currently carry no information. If nothing changes on any of
the three, say that.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Lead with the finding. Short
sentences, one idea each. Forbidden without a one-line plain definition at
first use: lift, baseline, base rate, precision, recall, confidence interval,
significance, distribution, variance, artifact, null.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. No `--break-system-packages`.
- Work on `sweep/db-corpus-baseline`.
- Provenance for every figure.
- One prompt in, one wrap-up out to `wrap-ups/P3-guidance-ledger-out.md`.
- Commit ledger files and eval caches as they land — they are the durable
  asset.
- Running low on budget is a reason to stop cleanly, not to rush. **Phase 1
  alone, validated and committed, is a useful result** — it is the input P3b,
  P4 and the exit-latency ledger all need, plus a measured noise floor this
  project did not have in usable form. Write the wrap-up with what is done,
  mark the rest `pending` with a precise `next_action`, and say plainly that
  it is a partial run.
