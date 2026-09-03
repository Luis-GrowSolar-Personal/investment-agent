# Task: Alpha Vantage Transcript Fidelity Benchmark

## Context

We are evaluating whether Alpha Vantage's `EARNINGS_CALL_TRANSCRIPT` API
can serve as an automated data source for Step 6 (Automated Transcript
Ingestion). We already confirmed AV covers our tickers (AMPX, EOSE, SPWR,
ENVX) on the free tier. But manual inspection of one AV transcript (SPWR
Q2 2025) showed signs of paraphrasing rather than verbatim transcription —
compare AV's "We faced challenges related to ITC revenue, reminiscent of
my hometown's harsh winter" against the real call's disfluent, ASR-style
"I dragged out an old picture, to talk about the, the ITC and the weather
out there." The content was directionally accurate (there was a real
weather analogy — the 1967 Ice Bowl) but heavily smoothed.

The question this benchmark answers: **does that smoothing change what
the evaluator concludes?** Not "is the text identical" — some wording
variance is expected and fine. What matters is whether our analyst
prompt (`EVALUATION_PROMPT.md`), run against the AV version of a
transcript, produces a materially different structured score than the
same prompt run against our existing DB version of the same call.

## Environment

Run everything from the `investment-agent` repo root, and source
**only** the root `.env`. There is a second `.env` at
`testing/ec_ingestion/.env` containing just `AV_API_KEY` — do not use
it. The root `.env` has the same `AV_API_KEY` value plus the DB
connection variables this benchmark needs for Prisma access, so root
is the only `.env` that should be read here. If at any point the two
files' `AV_API_KEY` values don't match, stop and report it rather than
picking one — that would mean the key was rotated in one place and not
the other, and continuing on a stale key wastes today's call budget on
requests that may silently authenticate against a different account
tier than expected.

## Budget constraint

We have used ~8 of 25 free-tier Alpha Vantage API calls today (resets
daily). **Hard cap this run at 15 AV API calls total.** Sleep **more
than 60 seconds** between each AV call — the free tier rate limit for
this endpoint may be as strict as 1 request/minute, so pad it (aim for
70-75 seconds) rather than cutting it close. This means the AV-fetching
portion of this run (Step 2) will take on the order of 10-15+ minutes
wall-clock for a 7-sample batch — that's expected, don't try to
parallelize or shorten the spacing to speed it up. If the sample plan
would exceed 15 calls, reduce the sample size rather than exceeding the
cap — stop and report how many samples you could cover instead.

If any AV call returns a rate-limit error despite the spacing, stop
immediately, report which sample failed, and do not retry it
automatically — retrying into an active rate limit risks cascading
failures across the remaining budget.

## Critical constraint: re-score everything with today's model

The Analysis records already stored in the DB were scored by an older
LLM version, not the model currently in production use. **Do not use
any stored `Analysis` record or its structured score anywhere in this
benchmark.** Everywhere below that says "DB version" or "DB transcript,"
this means the DB-stored **transcript text only** — pull it from the
`Transcript` table, discard any linked `Analysis` row, and run the
current evaluation prompt against it fresh, with today's model, exactly
as you would for the AV version.

If any DB transcript is missing its full text and only the old stored
score survives, drop it from the sample — it cannot be used for this
test regardless of how well it otherwise fits the selection criteria
in Step 1.

This matters because if Step 5 compared the AV-transcript score (today's
model) against the old stored score (yesterday's model), any diff would
be confounded — indistinguishable between "AV's transcript is different"
and "the model changed." The whole point of Step 4's determinism check
is to establish a clean same-model, same-input baseline; reusing a
stored score would defeat that purpose even though the determinism
check itself would still pass.

## Step 1: Inventory existing DB transcripts

Query the Transcript/Analysis tables (via Prisma) for transcripts on
portfolio tickers (AAPL, AMPX, EOSE, SPWR, TSLA, TTD) that:
- Have a call date in a quarter Alpha Vantage is likely to cover
  (2024 onward — we confirmed AV has no data for SPWR before its
  April 2025 rename, so don't waste calls on pre-2024 quarters for
  any ticker without checking first)
- Have full Q&A content stored, not just prepared remarks (prioritize
  these — the fidelity risk we're testing is highest in Q&A, where
  language is spontaneous rather than scripted)

Select up to 7 transcripts across at least 3 different tickers,
prioritizing diversity of ticker over volume on any one ticker.
Print the selected (ticker, quarter, year) list before proceeding.

## Step 2: Fetch matching AV transcripts

For each selected transcript, call the AV `EARNINGS_CALL_TRANSCRIPT`
endpoint for that exact ticker + quarter combination using `AV_API_KEY`
from `.env`. Save raw responses to `analysis/av_fidelity_test/raw/`.

If AV returns empty for a ticker/quarter combination, note it and move
to the next sample — do not burn additional calls guessing at date
variants unless budget allows after the primary sample is exhausted.

## Step 3: Diagnostic text comparison (not the main verdict — informational)

For each matched pair, compute:
- Total word count, DB version vs AV version
- A rough structural similarity metric (e.g. sequence matcher ratio,
  or sentence-count comparison) — this is a diagnostic signal for
  "how much did this get rewritten," not a pass/fail gate
- Flag qualitatively whether the AV version preserves speech
  disfluencies (filler words, false starts, interruptions) or reads
  as cleaned/summarized prose

## Step 4: Determinism control (required before trusting any verdict diff)

Before comparing DB vs AV outputs, run the DB version of **each**
selected transcript through the analyst evaluation prompt **twice**,
at `temperature=0`, using the same model version currently in
production use. Diff the two structured JSON blocks field-by-field.

If any field differs between the two identical-input runs, stop and
report this — it means our own pipeline isn't deterministic yet, which
would invalidate any AV-vs-DB comparison until fixed. Do not proceed to
Step 5 for a given transcript unless its determinism check passes clean.

## Step 5: Run the evaluator on both versions

For each transcript that passed the determinism check, run the analyst
evaluation prompt (from `EVALUATION_PROMPT.md`) once against the DB
version and once against the AV version, same model, same
`temperature=0`, no portfolio context (single-transcript evaluation
only — consistent with the analyst/allocator firewall).

## Step 6: Field-by-field structured diff

For each pair, diff every field in the STRUCTURED JSON block:
thesisHealth, thesisDelta, recommendation, recommendedSize,
freshMoneyAllocation, typeClassification, stumbleType,
threatMechanismImpaired, credibilityDelta, activeDriverCount,
ratchetTranche, blindSpotsTriggered, capPercent,
mitigationArgumentPresent, mitigationCapabilityTrackRecord.

Do not collapse this to a single "same verdict y/n." Report every
field, flagged as MATCH or DIFFER. Weight nothing as more or less
important in the raw output — just show us all of it. Pay particular
attention to and call out explicitly if these differ:
credibilityDelta, mitigationArgumentPresent,
mitigationCapabilityTrackRecord, blindSpotsTriggered — these are the
fields most likely to be sensitive to language-smoothing rather than
factual content changes.

## Step 7: Report

Write `analysis/av_fidelity_test/REPORT.md` containing:
- AV call budget used vs the 15-call cap
- Per-sample: ticker/quarter, text similarity diagnostic, determinism
  check result, full field-by-field diff table
- A summary count: across all samples, how many fields differed in
  total, and how many of those were in the four flagged
  credibility/mitigation fields specifically
- No overall recommendation or conclusion — present the data plainly
  and let Luis draw the conclusion

## Do not

- Do not exceed 15 AV API calls
- Do not modify EVALUATION_PROMPT.md
- Do not pass portfolio data into any evaluation call
- Do not average or summarize away individual field mismatches into a
  single pass/fail score
- Do not use any stored `Analysis` record or its structured score —
  both DB and AV transcripts must be scored fresh, today, same model
