# Model Selection Benchmark Spec

**Status:** Draft — for review before execution.
**Objective:** decide which Claude model (Sonnet 5, Opus 4.8, Fable 5,
Haiku 4.5) to use for which part of building the investment agent, based
on evidence rather than intuition about relative capability on
finance-specific reasoning tasks.

---

## Framing

The project is not uniformly complex. It decomposes into a small number
of genuinely hard reasoning cores, wrapped in a much larger amount of
ordinary engineering (CRUD, infra, mechanical business-logic
implementation once a spec exists). Model tier should track that split,
not apply uniformly to the whole project.

Two decisions are in scope for this benchmark round:

- **Task A — the analyst/evaluator judgment task.** Extracting
  structured signals (`thesisHealth`, `stumbleType`,
  `mitigationTrackRecord`, etc.) from unstructured earnings-call
  transcripts against the rubric in `EVALUATION_PROMPT.md`.
- **Task B — architecture/spec design pressure-testing.** Holding
  multiple interacting constraints in tension (barbell ratio, position
  caps, minimums, conviction ranking) and catching contradictions or
  edge cases in a proposed design before it's built. Current live
  example: the cold-start portfolio construction spec (see
  `memory: small_account_diversification` from 2026-07-04).

Explicitly **out of scope** for this benchmark round: which model to use
for implementation/engineering once a spec is fixed. Default assumption
is Sonnet for that regardless of what these benchmarks conclude — that
work is mechanical, not a reasoning-depth question. Revisit only if
evidence suggests otherwise.

---

## Group 1 — decide the model for Task A (the evaluator)

### Step 0 (gate, not a benchmark — must complete before Benchmark 1)

**Variance / noise-floor test.** Run the current evaluation prompt
(whichever version is live in `docs/EVALUATION_PROMPT.md`) 3x on the same
model, same temperature setting, against the four problem transcripts
already identified in `HANDOFF_2026-04-19.md`:

- ENPH 2023-04-25 (Q1 2023)
- ENPH 2023-07-27 (Q2 2023)
- ENPH 2023-10-26 (Q3 2023)
- ENPH 2024-04-23 (Q1 2024)

Compare `stumble_type`, `mitigation_track_record`, `recommendation`,
`thesis_health` across the 3 runs. This establishes the noise floor:
how much a single model disagrees with itself on identical input. Any
cross-model difference in Benchmark 1/2 smaller than this noise floor is
not a usable signal.

**Update 2026-07-04:** checked `backtest_runner.py` — `temperature=0` was
already added on 2026-05-02 (commit `22d2c712`), two weeks after the April
handoff flagged the missing-temperature theory. So that fix has been live
for ~2 months, including through the v3→v5 prompt iteration testing that
still showed reversing results. This means either (a) temperature=0
resolved the instability and the v3-v5 reversals were genuine prompt-logic
sensitivity, or (b) temperature=0 reduces but doesn't eliminate variance,
and some instability remains. Nobody has run the rerun-same-model-3x test
*since* the temperature fix landed — Step 0 still needs to run, just
without the "set temperature" action item, since that part is already
done.

### Benchmark 1 — aggregate backtest performance across models

Run the full backtest regression (current prompt version, temperature
fixed per Step 0) across candidate models on the existing ticker corpus.
Compare:

- Overall simulated return
- Max drawdown
- Signal accuracy (recommendation correct vs. actual outcome), per the
  methodology already used in the v1–v5 prompt comparisons

**Candidate models (confirmed 2026-07-04):** Sonnet 5 (baseline), Fable 5.
Opus excluded — Fable is positioned as the deeper-reasoning model, so it's
the relevant comparison point for Task A. *(Note: no confident prior on
how these two actually rank on finance-specific structured extraction —
that's the point of running this rather than reasoning about it
abstractly.)*

### Benchmark 2 — classification-level accuracy on known hard cases

On the same four ENPH transcripts from Step 0, plus TTD Q4 2024 (flagged
in `HANDOFF_2026-04-19.md` as the other known-hard case), compare each
candidate model's classification against the already-established correct
answer for each field. This is a more direct quality signal than
aggregate P&L, which can mask a wrong classification that happened to
net a good return in one backtest window.

### Decision rule for Group 1

Pick the model for Task A only if it clears the Step 0 noise floor on
both Benchmark 1 (aggregate return/drawdown) **and** Benchmark 2
(hard-case classification accuracy). If a model wins on one but not the
other, that's a real finding to think about, not a tiebreaker to average
away — write down which axis it won on before deciding.

---

## Group 2 — decide the model for Task B (design pressure-testing)

### Benchmark 3 — blind independent pressure-test

Give each candidate model the *original, uncontaminated* framing of a
design problem — i.e., the initial intuition as first stated, not any
critique or refined version that emerged from discussion with another
model. First subject: the cold-start portfolio construction idea, as
originally framed ("divide N by hardCap, allocate to strongest tickers
in domain").

Each model runs independently, with no visibility into the other's
output (avoids anchoring). Luis reviews both outputs and judges: which
model surfaced more/sharper/more actionable objections? Concrete
criteria, not vibes — did the critique identify a specific failure mode
that would have produced a bad outcome if built as originally proposed?

**Candidate models:** Sonnet 5, Fable 5.

### Benchmark 4 — spec-quality stress test on a fixed spec

Once the open policy questions from Benchmark 3 are resolved (by Luis,
not by either model — those are product decisions, not something a
benchmark should decide), give both models the same fixed, unambiguous
spec and ask each to identify remaining edge cases, ambiguities, or
failure modes in it. This tests spec-review quality on a problem that's
no longer ambiguous, isolating "does this model catch subtle
contradictions" from "does this model happen to guess my intent."

### Decision rule for Group 2

Pick the model whose pressure-testing surfaced more concrete, adopted
findings across Benchmarks 3 and 4 — adopted meaning Luis actually
changed the spec because of it, not just "raised a point." A critique
that sounds thorough but doesn't change anything isn't evidence of
better pressure-testing.

---

## Explicitly not decided by this benchmark round

- Which model implements code once a spec is fixed (default: Sonnet).
- Which model handles routine engineering, infra debugging, or UI work
  (default: Sonnet — the entire Railway/Railpack cron debugging session
  on 2026-07-04 was handled without needing escalation).
- Whether a "smarter" model reduces backtest overfitting risk. It
  doesn't — that's a discipline/methodology problem (out-of-sample
  testing, avoiding look-ahead bias per `DOMAIN.md`), not something model
  tier fixes.

---

## Cost note

Group 1 involves the full backtest regression run 2–3x per model
(Step 0 variance test) plus additional full runs per candidate model
(Benchmark 1), which is a non-trivial number of API calls against
the existing multi-quarter, multi-ticker corpus.

**Cost approved 2026-07-04.** Rationale: a 1-2% return edge from correct
model selection pays for the benchmark cost many times over across the
life of the portfolio. Proceed with full Group 1 execution.
