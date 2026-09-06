# Test 6 — look-ahead prohibition as a probe

`docs/handoffs/2026-09-03-state-of-play.md` §7 Test 6. Read §0 of
`docs/handoffs/2026-09-06-state-of-play.md` first, then
`wrap-ups/test4-analyst-noise-floor-out.md` **in full** (this run is a
paired continuation of it and reuses its saved output as the control arm),
plus `docs/architecture/PROMOTION_GATE.md` §2.2a and §6.

**Cost: ~275 Anthropic API calls, ~$25 estimated.** The user approved a
real-cost run of this size. No DB writes.

## What this run measures, and what it cannot

Score the same transcripts twice: the evaluation prompt **exactly as
deployed**, and the same prompt **plus one sentence**:

> evaluate as of the call date; do not rely on knowledge of subsequent
> stock performance, later results, or later news

Nothing else changes. Pre-declared reading, per state-of-play §7:

- Scores barely move → look-ahead was not doing much work.
- Scores degrade materially → look-ahead was in there, and was helping.

**This is a measurement, not a defense.** The analyst has no tools and
cannot look up a price, so prohibiting lookup forbids the impossible. The
leak, if any, is *recall*, and a model cannot be instructed not to know.
Do not present a null result as evidence the analyst is clean, and do not
present a positive result as a fix.

**It is a §2.2a prompt change.** Even if the sentence looks beneficial it
cannot be adopted here — it would need its own gate run like any other
candidate. **Report, do not adopt. Do not modify
`docs/EVALUATION_PROMPT.md`.**

---

## The design: paired against Test 4, not a fresh measurement

**Use Test 4's exact 50-transcript sample** — the (ticker, call date,
transcript_id, tier) rows in
`analysis/data/run_state/test4-analyst-noise-floor/sample.json`. Do not
draw a new sample.

This matters for a specific technical reason, not convenience: **a
hit-rate noise floor is sample-size dependent.** Test 4's per-tier floors
were measured at n=13/13/12/12. They transfer to this run *only* if this
run scores the identical transcripts. A fresh draw of a different size
would need its own floor re-derived from scratch.

- **Control arm: already exists.** Test 4's 5 runs per transcript with the
  unmodified prompt are saved at
  `analysis/test4_noise_floor/raw/<transcript_id>.json`. Reuse them. Do
  not re-run the control arm at full scale.
- **Treatment arm: 50 transcripts × 5 runs = 250 calls**, identical in
  every respect except the added sentence.
- **Control replication check: 5 transcripts × 5 runs = 25 calls** (see
  Step 1b).

## The per-tier noise floors this run reads against

From Test 4 Step 4, on this identical sample:

| tier | n | hit-rate noise floor (std) | usable as a detector? |
|---|---|---|---|
| large | 13 | **0.0pp** | **yes — primary** |
| mid | 12 | **0.0pp** | **yes — primary** |
| megacap | 13 | 3.77pp | yes, but read against its own floor |
| small/micro | 12 | 14.34pp | **no — control arm only, see Step 4** |

**Read each tier against its own floor. Never pool them into one
threshold** — the aggregate 2.65pp figure is wrong for every individual
tier and must not be used as this run's detection threshold.

**`0.0pp` does not mean zero.** It means no variance was observed in 13
transcripts × 5 runs. The true floor is small, not provably nil. **Set a
minimum detectable effect that respects n=13, and state it explicitly
before reporting any result as significant** — do not declare a 0.1pp
shift meaningful on the strength of an observed zero. Report the binomial
or bootstrap interval you use and why.

---

## Step −1 — resume protocol (assume this run WILL be interrupted)

`run_id` is **`test6-look-ahead-prohibition`**, state in
`analysis/data/run_state/<run_id>/`. Write `progress.json` before any
reading; append `findings.md` when a finding is established.

**This run must be fully re-entrant at the level of a single API call.**
The user may hit a token-spend limit part-way through, and Test 4 was
killed twice by the OS for low memory. Test 4's transcript-level
checkpointing survived that but discarded up to 4 completed calls each
time. With a spend ceiling in play that waste is no longer acceptable.

1. **Persist every run individually, the moment it returns** — one record
   per (transcript_id, run_idx) under
   `analysis/test6_look_ahead/raw/<transcript_id>/run<idx>.json`, written
   atomically (temp file + rename) so a kill mid-write cannot leave a
   corrupt record. A transcript's 5 records are consolidated only when all
   5 exist.
2. **On start, enumerate what already exists and skip it.** Never re-issue
   a call whose record is on disk. Report at start: how many of the 250
   treatment runs are already complete, and how many remain.
3. **Distinguish a spend/quota stop from a transient error.**
   - Transient (timeout, 5xx, connection reset, transient 429 with a
     retry-after): retry with backoff, bounded — no more than 3 attempts
     per call, then record the failure and move on.
   - **Spend limit, quota exhausted, or credit/billing rejection: stop the
     run immediately and cleanly.** Do not retry into it, do not fall
     through to the next transcript. Write `progress.json`, append the
     reason to `findings.md`, print exactly how many calls this invocation
     made and how many remain, and exit non-zero with the resume command.
4. **Track spend per invocation and cumulatively.** `progress.json` keeps
   `calls_this_invocation`, `calls_total`, `tokens_total` and a
   `daily_batches`-style list of prior invocations, so the user can see
   cost accumulate across resumes rather than only at the end.
5. **Step 1b's control replication check is checkpointed separately** and
   is never re-run once it has passed. Record its verdict in
   `progress.json` so a resume does not spend 25 calls re-proving it.
6. **Analysis is gated on completeness.** Steps 3-6 must refuse to run
   until all 250 treatment runs exist, exactly as the AV benchmark gates
   its aggregate report. If invoked early, print how many remain and stop
   — do not emit a partial hit-rate comparison, which would be
   under-powered in a way the per-tier floors were not calibrated for.

Resuming is always the same command, run again with no arguments changed.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit. Work on
`sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.

---

## Step 1 — construct the two arms, and verify the control still holds

**1a. Build the treatment prompt in memory.** Read
`docs/EVALUATION_PROMPT.md` from disk, append the single sentence above,
change nothing else. **Do not write the modified prompt back to disk.**
Report: the header version string found (expect `v10+auto1 (auto-iterate
candidate — pending gate)`), the sha256 of the file as read, the sha256 of
the treatment string, and exactly where in the prompt the sentence was
appended. If the header string is not what Test 4 recorded, **stop** — the
control arm is no longer comparable.

**1b. Control replication check (25 calls) — do this before the 250.**
Pick 5 transcripts from the sample (one per tier, plus one extra megacap;
name them). Re-score each 5 times with the **unmodified** prompt and
compare against Test 4's saved runs for those same transcripts.

This exists because `server/lib/versions.js` pins a **bare, undated model
alias** (`claude-sonnet-4-6`) — `PROMOTION_GATE.md` §8 flags this, and
Test 4's wrap-up flags it again. If Anthropic has changed what that alias
resolves to since Test 4 ran, the paired comparison is invalid and any
difference this run measures would be model drift, not the added sentence.

- If the replication reproduces Test 4's distribution of values for those
  transcripts (same recommendations, comparable field stability), proceed.
- **If it does not, stop and report.** Do not proceed to the treatment arm
  and do not attribute the difference to the prohibition sentence. Say
  plainly that the control arm has decayed and the paired design is no
  longer available.

## Step 2 — treatment arm (250 calls), 5-way concurrent per transcript

For each of the 50 transcripts, 5 runs with the treatment prompt.
Temperature 0, no portfolio context, single-transcript evaluation
(firewall-consistent, `DESIGN_PRINCIPLES.md` §1). **No DB writes** — keep
everything under this run's own `analysis/test6_look_ahead/` directory.
Capture each response's own `model` field per call, as Test 4 did.

**Issue a transcript's 5 runs concurrently.** They are independent calls
at temperature 0 — running them in parallel cannot change any result. Test
4 ran strictly serially and took **5-6 hours** for 250 calls (measured
from its own checkpoint timestamps: ~6-7 minutes per transcript, ~78
seconds per call, output-generation bound at ~3,000 output tokens per
call). Note that Test 4's wrap-up estimate of "35-45 minutes of actual API
time" is **wrong** — it was inferred from per-call latency, not measured,
and its own text admits it was not separately logged. Do not repeat that
estimate. Five-way concurrency should bring this run to roughly **60-75
minutes**.

**Concurrency limits, deliberately conservative:**

- **Parallelize only within a transcript (5 at a time). Do not fan out
  across transcripts.** Test 4 was killed twice by the OS for low memory;
  wider concurrency multiplies memory pressure for a much smaller
  additional gain, and it would break the atomic per-transcript checkpoint.
- On any rate-limit response, **fall back to serial for the remainder of
  the run** and say so in the wrap-up. Throughput is not worth a confounded
  or half-failed arm.
- The per-run records of Step −1 are still written individually as each
  call returns, so an interruption mid-transcript loses at most the calls
  still in flight.

Consolidate and checkpoint after each transcript's 5 runs complete.

## Step 3 — the comparison, per tier

Compute the analyst-direct hit rate using
`analysis/analyst_direct_scorer.py`'s exact methodology (**import its
constants, do not reimplement**) — the same computation Test 4 Step 4 used,
so the two arms are directly comparable.

Report, per tier and overall:

| | control (Test 4) | treatment | delta (pp) | tier noise floor | exceeds floor? |
|---|---|---|---|---|---|

- Control hit rate per tier: the mean across Test 4's 5 runs.
- Treatment hit rate per tier: the mean across this run's 5 runs.
- **Also report each arm's own within-arm spread** (std across its 5
  runs). If the treatment arm's own spread is materially different from
  the control's, that is itself a finding — the sentence may change the
  *stability* of scoring, not just its level.

**Primary read: large and mid.** Their 0.0pp floor makes them the only
tiers where a small movement is interpretable. **Megacap: read against
3.77pp.** **Small/micro: report but do not use as a detector** — 14.34pp
of self-noise would swamp any plausible effect.

Also report, as a categorical companion to the hit-rate metric: how many
of the 50 transcripts changed their **modal `recommendation`** between
arms, broken out by tier.

## Step 4 — the differential test (the part that distinguishes recall from tone)

A uniform shift across all tiers would **not** be evidence of look-ahead.
The model has deep training-data recall about AAPL, NVDA, MSFT, GOOGL,
TSLA, AVGO and much less about AMPX, EOSE, QS, RUN. So:

- **Look-ahead predicts a differential**: scores move where recall is
  rich (megacap, large) and move *less* where it is thin (small/micro).
- **A uniform move across every tier, including small/micro, suggests the
  sentence changed the model's general caution or tone** — making it
  hedge more, score more conservatively — rather than removing recall.
  That reading substantially weakens any positive finding.

State explicitly which pattern the data shows. This is why small/micro is
scored at all despite being useless as a detector — **it is the control
group, and its low power is a known limitation to state, not a reason to
drop it.** If the small/micro delta is within its own 14.34pp floor, say
that the differential test is inconclusive rather than claiming it passed.

## Step 5 — NVDA, named specifically

`analysis/tier_return_attribution.py` (run this session) found the gain is
extraordinarily concentrated: **NVDA alone is 40.1% of the portfolio's
entire gain** ($32,065 of $79,945), with AVGO (27.0%) and ORCL (14.2%)
bringing three semis names to **81.4%** of the total.

NVDA is simultaneously (a) the single most important name to the backtest
result, (b) among the highest look-ahead risk in the corpus — its post-2022
AI-driven run is exceptionally well represented in training data — and (c)
in **megacap**, the noisier of the three usable tiers (3.77pp, not 0.0pp).

**Report NVDA's own transcripts separately and by name**: control vs
treatment recommendations and hit rate, transcript by transcript. n is
small and no significance claim will be available — report it as a named
case study, not a statistical result. **State plainly that a null result in
large/mid says little about NVDA**, because the tier that carries the
returns is not the tier that can be read cleanly.

## Step 6 — reading (report, do not decide)

1. Does the prohibition move scores beyond each tier's own floor? Give the
   per-tier verdict, not one global answer.
2. Does the movement show the differential pattern look-ahead predicts, or
   the uniform pattern that suggests tone change? (Step 4.)
3. What does this say — and explicitly, what does it **fail** to say —
   about NVDA and therefore about the 81% of returns concentrated in three
   names?
4. State the scope limit in the wrap-up's own words: this run measures
   look-ahead **on Test 4's 50-transcript sample**, not on the analyst
   generally. `docs/handoffs/2026-09-05-state-of-play.md` §5.4 records
   what happened last time a conclusion outran its scope (the model gate
   that "never measured the portfolio") — do not repeat it.

**Do not** adopt the sentence, amend `EVALUATION_PROMPT.md`, open a
`gate_ledger.json` entry, or recommend a prompt version change.

---

## Report

Scope boundary: **report, do not decide.** No DB writes, no modification
of `EVALUATION_PROMPT.md`, `versions.js`, `PROMOTION_GATE.md`, or
`gate_ledger.json`. Do not modify Test 4's saved output — it is this run's
control arm and must stay intact.

Open with resume status, then:

> **Control replication (25 calls): [reproduces Test 4 / DECAYED — run
> stopped]. Prompt version: [header string], file sha256 [X]. Model string:
> [X], response-reported model: [X]. Treatment arm: 50 transcripts × 5 runs.
> Per-tier hit-rate delta (treatment − control): large [X]pp (floor 0.0pp,
> MDE [Y]pp) → [moves / does not move]; mid [X]pp (floor 0.0pp) → [...];
> megacap [X]pp (floor 3.77pp) → [...]; small/micro [X]pp (floor 14.34pp,
> control arm only) → [...]. Modal recommendation changed on [N]/50
> transcripts ([breakdown by tier]). Differential test: [look-ahead pattern
> — moves in high-recall tiers only / uniform pattern — suggests tone
> change / inconclusive]. NVDA case study: [N] transcripts, [summary].
> Headline reading: [look-ahead was not doing much work / look-ahead was
> present and helping / inconclusive], scoped to this 50-transcript sample.
> Token spend: [N] tokens across [N] calls, ~$[X] estimated, over [N]
> invocation(s). Wall clock: [N] min (concurrency: [5-way / fell back to
> serial at call N]).**

Flag plainly: any tier where the treatment arm's own within-arm spread
differs materially from Test 4's floor for that tier; any transcript whose
recommendation changed in a direction that looks like *increased*
confidence under the prohibition (counter-intuitive, worth naming); and
whether the added sentence changed output length, structure, or field
completeness in ways unrelated to judgement (a confound worth catching).

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no
  Linux package managers or path assumptions.
- **No DB writes at all** — not even scoring output. `SELECT` only for
  forward-return lookups.
- Do not modify `docs/EVALUATION_PROMPT.md` or anything under
  `analysis/test4_noise_floor/`.
- Persist every individual run as it returns; checkpoint after every
  transcript's 5 runs. Track and report token usage per invocation and
  cumulatively.
- If a spend or quota limit stops the run, exit cleanly with the resume
  command — a partial arm is resumable, a corrupted one is not.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — file, manifest path, JSON
  key, or table/column.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
