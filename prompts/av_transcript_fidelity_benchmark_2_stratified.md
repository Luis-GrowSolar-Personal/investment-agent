# AV fidelity benchmark 2 — full-corpus sample, cap-tier stratified

`docs/handoffs/2026-09-05-state-of-play.md` §0 defines every term used here.
Read `wrap-ups/av_transcript_fidelity_benchmark_1-out.md` and
`wrap-ups/test3-transcript-ingestion-fidelity-out.md` in full before starting
- this run reuses both their method and their findings.

**This is a separate, standalone benchmark, not Test 4/5/6.** It runs in
parallel with those tests, on its own branch, and blocks nothing in §7's test
plan. Its job is to answer two specific vendor questions, as posed directly:
**(1) is Alpha Vantage's transcript quality as good as the project's existing
hand-copied (Seeking Alpha / Motley Fool) transcripts, and (2) does that
quality vary with ticker size / how closely a company is followed?**

## Why this run exists, and what changed from the first draft of this prompt

`CLAUDE.md` states the DB transcript source plainly: **"Manual copy-paste"**,
and `BUILD_STATE.md`: **"All transcripts loaded manually from Seeking Alpha /
Motley Fool."** This means the DB-stored `rawText` for every existing
Transcript row already **is** the ground truth this benchmark needs - there
is no reason to draw from tickers outside the corpus, and doing so would be
strictly worse: it would leave most samples with nothing to directly compare
against, forcing reliance on the weaker turn-count/sign-off proxy instead of
the decisive text comparison that actually confirmed AMPX Q3's truncation in
Test 3.

**This run therefore samples exclusively from tickers already in the
corpus**, drawing on whatever quarters of hand-copied transcript already
exist for them - so every single sample gets the decisive DB-vs-AV text
comparison, not a subset of one.

An earlier draft of this prompt proposed building an out-of-corpus universe
from a public sector classification, snapshotted at a point in time to avoid
survivorship bias. **That was solving the wrong problem** - point-in-time
universe construction exists in this project to keep a *backtest* fair
(Test 5). This is not a backtest; no returns are measured, so today's ticker
set and today's cap-tier labels are fine. That machinery is dropped entirely.

## Update, 2026-09-05 (after day 1) — ten API keys now available

Nine additional Alpha Vantage keys were obtained after the first daily
batch ran (`AV_API_KEY2` through `AV_API_KEY10` in `.env`, alongside the
original `AV_API_KEY` - 10 total, registered under different names/emails).
**This changes Step -1 and Step 1 below** - fetches now round-robin across
every available key, each with its own independent
25/day budget, cutting the run from ~10 days to as few as 4-5.

**One assumption this depends on, unverified: that each key belongs to a
genuinely separate Alpha Vantage account (separate registered email), not
multiple keys issued under one account.** Alpha Vantage's free-tier limit
is per-account, not per-key-string - if some or all of these keys turn
out to share an account's quota, they are not additive and this design
would trip a shared rate limit rather than multiplying throughput. **The
driver must detect this defensively** (see Step 1) rather than assume it's
fine: if any key beyond the first returns a rate-limit/quota-exceeded
response earlier than its own call count would predict, stop using that key
immediately for
the rest of the run, report it plainly, and fall back to whichever keys
are still behaving independently. Do not retry into it.

Day 1's partial batch (10 calls, all megacap, single key, already recorded
in `progress.json`) stands as-is - do not re-fetch or discard it. Multi-key
rotation applies from the next invocation onward.

## Step 0 — the sample, drawn only from the existing corpus

**Ticker universe and cap tiers, as given, not re-derived.** Corrected from
the prior draft, which dropped AAPL from every tier by mistake:

| Tier | Tickers |
|---|---|
| Megacap | AAPL, GOOGL, NVDA, MSFT, TSLA |
| Large | AVGO, AMD, ORCL |
| Mid | FSLR, TTD |
| Small/micro | QS, AMPX, ENVX, EOSE, RUN |

`SPWR` is excluded from the draw pool - it was the subject of 2 of the 7
`av_transcript_fidelity_benchmark_1` samples already, and Test 3 already
resolved its low-similarity finding directly (not a truncation - a genuine
company-specific call-ending style, confirmed identical in both DB and AV
text). Re-including it would spend budget re-establishing something already
settled.

**Pool, as observed 2026-09-05** (query below; **re-run it at execution
time and use the fresh counts** - this is a live database and more
transcripts may have been added by then):

```sql
SELECT tk.symbol, COUNT(*) AS n, MIN(t."callDate")::date AS earliest, MAX(t."callDate")::date AS latest
FROM "Transcript" t
JOIN "Ticker" tk ON t."tickerId" = tk.id
WHERE tk.symbol IN ('MSFT','TSLA','AMPX','ENVX','AVGO','QS','RUN','EOSE','GOOGL','AMD','FSLR','AAPL','ORCL','NVDA','TTD')
GROUP BY tk.symbol
ORDER BY tk.symbol;
```

| Tier | Tickers (n) | Tier total | Already fetched by benchmark_1 | Available |
|---|---|---|---|---|
| Megacap | AAPL 23, GOOGL 22, NVDA 23, MSFT 24, TSLA 22 | 114 | 0 | 114 |
| Large | AVGO 21, AMD 22, ORCL 24 | 67 | 0 | 67 |
| Mid | FSLR 23, TTD 22 | 45 | 0 | 45 |
| Small/micro | QS 22, AMPX 15, ENVX 21, EOSE 22, RUN 22 | 102 | 5 (AMPX Q1/Q2/Q3 2025, EOSE Q1/Q2 2025) | 97 |
| **Total** | | **328** | **5** | **323** |

**323 available against a 200 target - comfortably sufficient**, no need to
reduce scope or reach outside the corpus. **Mid's pool (45) is short of an
even 50-per-tier split by 5** - do not force it. Reallocate:

| Tier | Draw target |
|---|---|
| Megacap | 52 |
| Large | 51 |
| Mid | 45 (full pool) |
| Small/micro | 52 |
| **Total** | **200** |

**If the re-run count at execution time differs from the table above** (new
transcripts added since 2026-09-05), recompute this allocation the same way
- cap any tier at its actual available pool, spread the remainder evenly
across the others - rather than using these exact numbers blindly.

**Query every existing `Transcript` row for these 14 tickers** (`SELECT`
only), joined to `Ticker` for the symbol, excluding the 5 (ticker, quarter)
pairs `benchmark_1` already fetched: AMPX Q1/Q2/Q3 2025, EOSE Q1/Q2 2025.

**Draw with a fixed, reported random seed**, per the target allocation
above. This is a full-corpus draw, not a hand-picked one: do not substitute
your own judgment for which quarters "look interesting."

Print the per-tier pool size (re-verified, not assumed from this table), the
target allocation, the seed, and the drawn list before any AV call is
made.

---

## Step −1 — resume protocol (daily-resumable, multi-key)

`run_id` is **`av-fidelity-benchmark-2-stratified`**, state in
`analysis/data/run_state/<run_id>/`. Invoked **once per day, manually**,
across as many days as the drawn sample requires. Each invocation must:

1. **Enumerate available keys** by reading `AV_API_KEY`, `AV_API_KEY2`,
   `AV_API_KEY3`, and any further `AV_API_KEY<N>` present in `.env` -
   generic enumeration, not hardcoded to exactly three, so a fourth key
   added later needs no prompt change.
2. Read `progress.json` for what has already been fetched, and - **per
   key** - how many calls that key has used today and its last call
   timestamp. Track usage **per key**, not as one global counter, since
   each key has its own independent daily budget.
3. **Per-key daily reset**: a key is eligible again once a full 24 hours
   have passed since *that key's* last call in its last active batch -
   conservative, since Alpha Vantage's exact reset time isn't confirmed.
   Keys reset independently of each other; one key having budget left does
   not mean another does.
4. **Fetch up to 20 calls per key this invocation** (same 5-call safety
   margin as before, per key) - so with all 10 keys behaving independently,
   up to 200 calls in one invocation (the entire remaining draw, in principle,
   in one day), in roughly the same wall-clock time the single-key version
   took to do 20 (see Step 1's interleaving). In practice, stop as soon as
   the drawn list is exhausted - there's no need to keep pulling once the
   200-transcript sample is complete.
5. For each successful fetch, immediately run the **decisive check**: a
   direct text comparison against the DB `rawText` for that exact
   ticker/quarter (the method Test 3 used to confirm AMPX Q3), plus the
   cheaper heuristic (speaker-turn count, last-turn closing-language match)
   as a secondary signal. Classify immediately as **truncated /
   summarized-but-complete / matches closely**. Do not defer classification.
6. Update `progress.json` (per-key usage and per-key last-call-timestamp)
   and append to `findings.md`, then **stop** and print: calls used today
   **per key**, total used so far, total remaining, estimated remaining
   invocations at the current effective multi-key rate.

**No LLM calls, no re-scoring, no DB writes** (`SELECT` only). This is a
fetch-and-classify benchmark - the completeness question does not require
running the evaluator.

---

## Step 1 — daily fetch, round-robin across available keys

Each day: pull the next unfetched targets from Step 0's drawn list. Fetch
using a **round-robin over eligible keys** (per Step -1: under its 20/day
cap, and ≥70s since its own last call) rather than one key at a time:

- Maintain each key's own last-call timestamp. To fetch the next target,
  pick whichever eligible key has waited longest since its last call (or
  any eligible key if none have been used yet this invocation).
- If **no** key is currently eligible (all cooling down), sleep only until
  the soonest one clears its 70s window - do not sleep a flat 70s
  regardless of key count, that would waste the whole point of having
  multiple keys.
- If **all** keys have hit their 20/day cap, or the drawn list is
  exhausted, stop the invocation.
- **Never call the same key twice within 70s of itself.** Calls to
  *different* keys have no minimum spacing between them - that's what
  makes this faster than the single-key version.
- **Defensive check for shared quota (see the update note above)**: if any
  key beyond the first returns a rate-limit or quota error well before it
  should - i.e., clearly inconsistent with its own recorded call count
  today - stop using that specific key for the rest of the run, log it as
  a suspected shared-quota key, and continue with whichever keys are still
  behaving independently. Do not treat this as a fatal error for the whole
  run.

If a (ticker, quarter) returns no AV coverage, record the miss, do not
retry it, and note it against that tier's count (a coverage-miss rate by
tier is itself a finding - AV's breadth may differ by how closely a
company is followed, which is directly one of the two questions this run
exists to answer). Save every raw response to
`analysis/av_fidelity_benchmark_2/raw/`, mirroring Test 3/benchmark 1's
file layout, and record which key fetched it in `progress.json` for
per-key accounting.

---

## Step 2 — once the drawn sample is complete: the aggregate report

Do not run this step until Step 1 has processed every item in Step 0's
drawn list (fetched or recorded as a miss).

- **Truncation rate with a Wilson 95% CI**, overall and broken out by cap
  tier. Because every sample in this design has a DB transcript to compare
  against, this rests on the decisive direct-comparison check for the whole
  sample - state that plainly, this is the improvement over the first draft
  of this prompt.
- Does the tier breakdown support or refute the working hypothesis that
  truncation correlates with smaller/less-followed names? Report whichever
  way it goes - **prediction is not a gate**.
- **Coverage-miss rate by tier** - does AV even have data for smaller names
  at the same rate as megacaps? This is itself an answer to "is AV worse for
  less-followed tickers," independent of the truncation question.
- Report every flagged-truncated sample's specific evidence (the exact text
  where AV's version stops and the DB version continues, as Test 3 did for
  AMPX Q3) rather than a bare count.

### Pre-declared decision thresholds (state and use exactly as written; flag if you believe these need revision before applying them, but do not silently substitute your own)

| Truncation rate (95% CI upper bound) | Reading |
|---|---|
| Below 10% | Fidelity supports moving forward with AV - the tier decision turns on whether Alpha Vantage's paid tier changes the underlying transcript data at all (unconfirmed from public docs as of this writing - flag for direct confirmation from AV support before paying) |
| 10-25% | Marginal - usable only with a mandatory per-transcript completeness check (this run's own heuristic, productionized) in any future ingestion pipeline |
| Above 25% | Do not build production ingestion on AV; evaluate a different vendor |

---

## Report

Scope boundary: **report, do not decide.** Do not commit to a vendor, do not
change `DESIGN_PRINCIPLES.md`/`DOMAIN.md`, do not start building Step 6
ingestion.

Open with resume status (day N of the run, cumulative calls used), then on
final completion:

> **Pool: [N] transcripts across 4 cap tiers in the existing corpus
> (megacap [N], large [N], mid [N], small/micro [N]). Drawn [N] (seed [N]),
> [N] coverage misses. Keys used: [N] ([N] calls / [N] calls / [N] calls per
> key; [N] suspected shared-quota, if any). Days to complete: [N].
> Truncation rate: [N]% (95% CI [X-Y]%), by tier: megacap [X]%, large [X]%,
> mid [X]%, small/micro [X]%. Coverage-miss rate by tier: [X]. Reading per
> the pre-declared table: [below 10% / 10-25% / above 25%]. Paid-tier
> data-fidelity premise: [confirmed same data / confirmed different data /
> unconfirmed - flagged for design session].**

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no re-scoring, no DB writes (`SELECT` only).
- Hard cap 20 AV calls **per key** per invocation, ≥70s spacing **within
  the same key** (no minimum spacing required between different keys), no
  auto-retry into a rate limit. Never assume a fresh daily quota for any
  key without checking that key's own prior recorded usage and elapsed
  time.
- Enumerate `AV_API_KEY`, `AV_API_KEY2`, `AV_API_KEY3`, ... generically -
  do not hardcode a key count. If a key beyond the first shows signs of
  sharing quota with another (rate-limited earlier than its own call count
  predicts), stop using it and report - do not treat it as fatal to the
  run.
- This run is explicitly multi-day, though now shorter with multiple keys.
  Each invocation does one day's work across all eligible keys and stops -
  it is not a bug if the process exits after each key hits ~20 calls.
- Every figure quoted must name its provenance - file, manifest path, JSON
  key, or table/column.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one (continuously updated)
  wrap-up out, finalized only once Step 2 completes.
