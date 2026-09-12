# Handoff — earnings-call transcript ingestion: vendor evaluation

**Purpose of this document:** hand the transcript-ingestion question to a
fresh session with everything it needs and none of the dead ends already
walked. Self-contained — a session that reads only this plus the files it
names has enough to proceed.

**Written:** 2026-09-06, from the allocator-validation session.
**Branch:** `sweep/db-corpus-baseline`.

---

## 1. The question

Can earnings-call transcripts be ingested automatically from a vendor at
quality equal to the hand-copied text already in the DB — and if so, from
whom, at what cost?

Today every transcript in the corpus was **manually copy-pasted from
Seeking Alpha / Motley Fool**. That is the bottleneck on
`docs/architecture/BUILD_STATE.md`'s Step 6 (Automated Transcript
Ingestion), and Step 6 unlocks a lot downstream — continuous scoring,
alerting on new calls, a universe wider than what a human will paste by
hand.

**The DB text is the gold standard for this comparison**, not a
convenience sample. Any vendor is measured against it, never the reverse.

## 2. What is already established — do not re-derive

### The corpus
15 portfolio tickers, ~328 transcripts across the 14 used for the AV
benchmark (SPWR excluded from that draw), ~662 transcripts total in
`analysis/data/transcripts/_manifest.json` including non-portfolio names
(AMZN, META, V, JNJ and others scored back to 2021).

Cap tiers, the project's own classification, used for stratification:

| tier | tickers |
|---|---|
| megacap | AAPL, GOOGL, NVDA, MSFT, TSLA |
| large | AVGO, AMD, ORCL |
| mid | FSLR, TTD |
| small/micro | QS, AMPX, ENVX, EOSE, RUN, SPWR |

### DB corpus integrity: clean
`wrap-ups/test3-transcript-ingestion-fidelity-out.md` — **0 of 337
transcripts flagged** for truncation or corruption. The hand-copied corpus
is sound. This is settled; do not re-open it.

### Alpha Vantage, what is actually known
- **Pilot (n=7)**, `wrap-ups/av_transcript_fidelity_benchmark_1-out.md`:
  three anomalies flagged, but Test 3 resolved two of them as **false
  alarms** from a crude similarity-ratio proxy. Only **AMPX Q3 is a
  confirmed truncation** (AV's JSON cuts before the closing remarks and
  operator sign-off present in the DB copy). SPWR Q1/Q3 and EOSE Q2 end
  word-for-word identically to the DB text; their low similarity ratios
  track *paraphrasing density*, not missing content.
- **Stratified benchmark in flight**, run_id
  `av-fidelity-benchmark-2-stratified`: 200-transcript target, **25
  fetched, 175 remaining, zero truncations so far.** Caveat that matters:
  the sample so far is concentrated in megacap/large, the tiers the
  working hypothesis expects to look cleanest. The real test is the
  small/micro rate, not yet drawn.
- **Rate limits.** Free tier: 25 requests/day, 5/minute (documented). The
  project uses ~70s spacing and a 20/day cap as defensive margin.
- **Multi-key rotation does not work.** Ten API keys on ten separately
  registered accounts behaved as ~one quota: five got exactly 1 call
  before rate-limiting, four got 0. Cause undetermined from inside a CLI
  session (IP-level throttling vs pre-existing account usage). Nine keys
  are now `disabled` in the run state. **Do not retry this approach**
  without new information from Alpha Vantage directly.

### A naming trap that has already caused one wrong conclusion
**The SPWR in this corpus is not the SunPower that went bankrupt in
August 2024.** It is the former CSLR (Complete Solaria), which bought some
SunPower assets and was later renamed to the SPWR ticker. Any reasoning
that treats the corpus SPWR as the bankrupt ~20-year-old SunPower is
wrong. Note `docs/handoffs/2026-09-05-state-of-play.md` §5.2 contains a
sentence that reads as making exactly this conflation and belongs on the
requote list.

## 3. The methodology already exists and works — reuse it

`analysis/av_fidelity_benchmark_2/driver.py` and
`prompts/av_transcript_fidelity_benchmark_2_stratified.md` implement a
validated comparison method. **A new-vendor evaluation is mostly a swap of
the fetch function.** Write a new driver and run_id so the AV run stays
reproducible, but keep:

- **Stratified draw from the DB corpus** across the four cap tiers, fixed
  reported seed, full drawn list written before any fetch.
- **The decisive per-sample check**, run immediately per fetch rather than
  deferred: direct text comparison against the DB `rawText` for that exact
  ticker/quarter — sequence-matcher similarity ratio, speaker-turn count,
  closing-keyword match on both sides, and a **dangling-handoff check**
  (does the last turn hand off to a named speaker for closing remarks that
  never appear — the signature that caught AMPX Q3).
- **Classification buckets**: `matches_closely` / `summarized_but_complete`
  / `truncated` / coverage miss.
- **Resumable daily-batch state** under
  `analysis/data/run_state/<run_id>/` with `progress.json`, `findings.md`,
  append-only `cells.jsonl`.
- **Wilson 95% intervals** on any rate estimate.

### Three bugs this methodology already earned the hard way — do not repeat
1. **Rate-limit detection must not be a case-sensitive dict-key check.**
   AV's field is `"Information"`; the driver tested for `"information"`
   and never matched, silently misfiling 175 rate-limit responses as
   "vendor has no data for this ticker/quarter." That would have reported
   a false ~87.5% coverage-miss rate. Match case-insensitively against the
   response's *values*, and treat an implausible coverage-miss rate as a
   bug hypothesis before a finding.
2. **Quarter labels cannot be derived by subtracting N days from the call
   date.** That collapses distinct quarters for any company reporting Q4
   in February and Q1 in April/May (confirmed for FSLR, TTD, QS, ENVX,
   RUN). Use a call-month bucket: Jan-Mar -> prior-year Q4, Apr-Jun -> Q1,
   Jul-Sep -> Q2, Oct-Dec -> Q3, and validate against the known-correct
   labels in the two prior wrap-ups before spending any call budget.
3. **One genuine duplicate row exists in the DB**: FSLR transcript ids 280
   and 284 are identical (same callDate 2024-02-27, same title, identical
   rawText length). Flagged, not fixed. De-duplicate in any draw.

## 4. What a vendor evaluation should actually measure

Fidelity is necessary but not sufficient. The full decision needs:

1. **Fidelity vs the hand-copied DB text** — the method above.
2. **Coverage** — does the vendor have these tickers at all, especially
   the small/micro names? Coverage misses are a separate failure mode from
   truncation and must be counted separately (that distinction is exactly
   what the case-sensitivity bug destroyed).
3. **History depth** — usable back to 2021, to match the existing corpus.
4. **Latency after the call** — how soon is a transcript available? This
   determines whether continuous scoring is possible or whether ingestion
   is always days behind.
5. **Cost at real volume** — and the volume is modest: ~15-45 tickers x 4
   calls/year, plus a one-time historical backfill.
6. **Terms** — whether programmatic access at that volume is permitted.
   (Relevant lesson: the multi-key attempt above was flagged as
   ToS-adjacent before it was built, and then did not work anyway.)

**Not yet decided, and worth deciding deliberately:** whether to keep
grinding the AV benchmark's remaining 175 transcripts at ~20/day (~9 more
daily invocations) while evaluating alternatives, or to treat the 25
clean samples as enough to keep AV a live candidate and spend the effort
elsewhere.

## 5. Constraints while the allocator work runs in parallel

- **Make no Anthropic LLM calls.** A separate run (`test6-look-ahead-
  prohibition`) is consuming the token budget, and a spend ceiling is in
  play. The comparison method above needs none — it is HTTP plus string
  comparison. Keep it that way.
- **`SELECT` only.** No DB writes.
- Same branch and working tree as the allocator work, so a simultaneous
  commit can hit `.git/index.lock`. Wait and retry rather than deleting
  the lock; confirm no other process is mid-commit first.
- Do not modify `analysis/av_fidelity_benchmark_2/`, its run state, or the
  prompts and wrap-ups of completed runs.

## 6. Read these, in this order

1. This document.
2. `wrap-ups/test3-transcript-ingestion-fidelity-out.md` — what is settled
   about corpus integrity and the AV anomalies.
3. `prompts/av_transcript_fidelity_benchmark_2_stratified.md` and
   `analysis/av_fidelity_benchmark_2/driver.py` — the methodology to reuse.
4. `wrap-ups/av_transcript_fidelity_benchmark_2_stratified-out.md` — the
   multi-key failure and the three bugs, in the run's own words.
5. `docs/architecture/BUILD_STATE.md` Step 6 — why this matters.
6. `CLAUDE.md` and `docs/architecture/DESIGN_PRINCIPLES.md` — project
   conventions, and the analyst/allocator firewall that any ingestion
   design must respect.
