# Does the analyst do better on older calls?

`docs/handoffs/2026-09-03-state-of-play.md` §7 Test 2. **Read §0 of that
document before starting** — it defines every term used here.

## Why this run exists

`DESIGN_PRINCIPLES.md` §4 records that transcript anonymization was attempted
and abandoned in April 2026 — companies are re-identifiable from financial
structure alone — and that *"backtests run with company identity known… a
documented limitation, not an oversight."* The scoring model was trained on data
running well past the 2022–2024 evaluation window, so it may in part be
recalling how these stories ended rather than reading the transcript.

**This run tests that with a signature rather than an argument.** Calls from
2021 and 2022 are far more thoroughly represented in a model's training than
calls from 2025 and 2026. If recall is doing the work, measured analyst quality
should **decline as call dates approach the training cutoff**. If it is flat,
the analyst is reading the document.

**Counter-evidence already on the record, to be weighed rather than ignored:**
`data/gate_ledger.json` entry 1 found the *newer* model — later cutoff, more
knowledge of how 2022–2024 resolved — scored **worse** (4.94pp lift to −2.5pp).
And the measured hit rate is only 60% (9/15), which is not what reading off
remembered outcomes looks like. This run is expected to come back flat. **A flat
result is the finding, not a null result**, and must be reported as such.

**No LLM calls, no API spend, no DB writes.** This run scores stored analyses
against the frozen price cache. Nothing is re-evaluated.

Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/hit-rate-by-year-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`hit-rate-by-year`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.
Write an initial `progress.json` as the very first action, before any reading.
This run is a small sequence of independent measurements rather than a cell
grid; say so in `progress.json` and do not create `cells.jsonl`. Append to
`findings.md` the moment a finding is established.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest. `testing/` stays gitignored.

## Step 1 — establish what can actually be scored

Before computing anything, report the shape of the data:

- scored `Analysis` rows **by call year**, and by (year × ticker), with counts
- the **latest call date that can be scored at all**. The §3.1 metric is a
  benchmark-relative forward return over two quarters, and `price_cache.json` is
  frozen at 2026-05-11, so calls within roughly six months of that date have no
  forward window. Name the cutoff date you derive and use it consistently.
- which tickers exist in which years. AMPX has no 2021 calls; the universe is
  not constant across the series.

**If any year has fewer than ~20 scoreable calls, say so before reporting a
number for it.** A hit rate on eight calls is noise with a decimal point.

## Step 2 — the series

Using `analysis/analyst_direct_scorer.py` and the §3.1 metric exactly as the
gate computes it — benchmark-relative, 2 quarters, ±5% band, lift over baseline
— report per call year:

| Column | Why |
|---|---|
| n scored calls | so the reader can discount thin years |
| raw hit rate | the headline anyone will look at first |
| **baseline hit rate** | what the naive rule achieved that year |
| **lift over baseline** | the gate's own unit, and the one that matters |
| distinct tickers | exposes mix changes |

**Report lift, not raw hit rate, as the primary series.** 2022 was a bear market
and 2023 a bull market; raw accuracy moves with regime, and lift over the
same-year baseline substantially controls for it. Say so in the report rather
than leaving the reader to assume raw accuracy is comparable across years.

## Step 3 — control the two confounds

**Ticker mix.** Recompute the series restricted to the subset of tickers present
in *every* year of the series. Report both. If the two series disagree in shape,
the full-universe series is measuring mix, not time.

**Regime.** Report each year's baseline alongside its lift, so a year where the
baseline itself collapsed is visible rather than inferred.

State plainly if either control makes the series uninterpretable.

## Step 4 — read the shape, carefully

Report the lift series and answer, without overclaiming:

- Is there a **monotonic decline** toward recent call dates?
- Is any apparent decline larger than the year-to-year variation in the early
  years — that is, is it a trend or a wobble?
- **Do not assert a specific training-cutoff date.** No cutoff is established in
  this repo, and inventing one to fit an inflection would be exactly the error
  this run exists to avoid. Report the series and let its shape speak.

**Pre-declared reading, agreed before results are seen:**

| Shape | Reading |
|---|---|
| Flat, or no decline exceeding early-year variation | Evidence **against** look-ahead driving the scores. Report as a positive finding. |
| Monotonic decline larger than early-year variation | Consistent with look-ahead, **not proof** — model quality, transcript quality and coverage all changed over the same period. Name the alternatives rather than concluding. |
| Non-monotonic or dominated by thin years | Inconclusive. Say inconclusive; do not pick the reading that is more interesting. |

## Step 5 — report

Scope boundary: **report, do not decide.** Do not amend `DESIGN_PRINCIPLES.md`,
do not adopt or reject the look-ahead prohibition (that is Test 6), do not
change any prompt.

Open with resume status, then:

> **Scoreable calls by year: [table]. Lift over baseline by year: [series].
> Shape: [flat / declining / inconclusive]. Full-universe and fixed-ticker
> series [agree / disagree]. Reading under the pre-declared rule: [reading].
> Thin years excluded: [list].**

Flag plainly: any year too thin to report, any disagreement between the two
series, and whether this changes the priority of §7 Test 6 — a clearly flat
result makes that probe much less urgent, and saying so is useful.

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop.** This prompt expects a flat series; if it
declines, that is the finding.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**. All queries `SELECT` only.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance.
- Report wall-clock runtime.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
