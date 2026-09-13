# Value attribution v2 — Stage D: the ceiling, and whether the allocator can reach it

**Run ID:** `value-attribution-and-headroom-v2` — **continuation, not a new run.**
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/value-attribution-v2-stage-d-out.md` (leave Stages A, B,
C and C3 wrap-ups intact).

**Read first:** `wrap-ups/value-attribution-v2-stage-c3-out.md` (the ablations,
leave-one-out and drawdowns), `wrap-ups/value-attribution-v2-stage-c-out.md`
(C1's ladder), and
`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`.

---

## 1. Why this run exists

Every measurement so far says the analyst's calls carry almost no information
and the full machinery trails buying and holding. Stage C3 added two things that
change what Stage D must measure:

1. **The allocator can barely act.** Every first-purchase funding event in the
   control run records `binding: "session limit"` — the 2.5-point per-session
   speed limit (X) clips each buy before starter sizing or the type cap ever
   applies. Starter sizing is worth exactly $0.00 for this reason, and 26.02% of
   the portfolio sits in cash on average.
2. **Two of four allocator rules do nothing** (profit-take never fires; starter
   sizing never reaches a trade), one is worth $813 and unstable, and Rule 3
   costs $9,417.91.

So a perfect analyst routed through **today's** allocator would be throttled
exactly as the real one is. A ceiling measured only that way would understate
what a good analyst is worth, and it is the number that would become the
analyst's improvement target.

**Stage D therefore measures the ceiling twice, and splits it by direction:**

- **Is the analyst's ceiling limited by prediction, or by plumbing?** Perfect
  calls through today's allocator, and through an unthrottled one.
- **Which half of the analyst's job is worth funding?** Perfect on the upside
  only, perfect on the downside only, perfect on both.

**Do not treat these as rhetorical.** A ceiling that sits near today's
$179,944.91 is a finding about the allocator, not the analyst, and is the most
decision-relevant outcome this run can produce.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** Oracle labels are derived from price data only.
   If a step appears to need a model call, **stop and report it**. Assert this in
   the run log before the first arm.
2. **Do not modify any stored `Analysis` row.** No DB writes. Oracle scores live
   only in this run's scratch data.
3. **No price-cache refresh.** Frozen at 2026-05-08.
4. **Firewall.** No portfolio data reaches the analyst or trend layers; no
   transcript data reaches the allocator. **The oracle arm is where this is
   easiest to break — read §4's warning.**
5. **No spec edits.** `PROMOTION_GATE.md`, `VERSION_REGISTRY.json`,
   `EVALUATION_PROMPT.md`, `versions.js`, the production prompt: untouched.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production). **Do not gate on either.**
8. **Locked population.** Every arm runs on the 195-event simulator population
   frozen in `PREREGISTRATION.json`, settled configuration (`swap_funding`,
   K=30, `new_calls_only`, `pooled`, `per_event_date`), with **X varied only
   where Step 4 says so**. An arm that cannot run is reported unavailable, not
   substituted.

---

## 3. Step −1 — resume protocol, and where stopping is allowed

State continues in `analysis/data/run_state/value-attribution-and-headroom-v2/`.

**The changed-prompt-archives-state rule is waived**, as for Stages B, C and C3.
Record this prompt's sha256 as `prompt_sha256_stage_d` alongside existing keys;
do not overwrite them. Append to `cells.jsonl` and `findings.md`; never rewrite.
Leave completed steps `done`. C2 and C4 stay `pending` — this run does not
attempt them.

**Stopping is permitted only after Step 4 is complete**, not before. Steps 1
through 4 are roughly 15 simulator runs in total and none is expensive. Earlier
stages of this run stopped after their first step on a permission clause written
too early; that clause is deliberately placed here instead. If budget genuinely
runs out before Step 4 finishes, stop cleanly, mark the rest `pending` with a
precise `next_action`, and say plainly that it is partial.

---

## 4. Step 0 — hygiene, pre-registration, and the firewall

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b. Pre-register before any arm runs**, extending `PREREGISTRATION.json` under
`stage_d`:

- **Injection point: `per_call_rec`**, not `final_action`. Injecting at
  `final_action` bypasses the trend layer and would measure a perfect analyst
  *and* a perfect trend layer while wearing an analyst-ceiling label.
- **The label encoding** — how bullish / bearish / neutral map onto
  `per_call_rec`'s actual action vocabulary. Name this as an assumption that
  loosens the bound.
- **The non-direction field synthesis** — what the oracle supplies for
  `thesis_health`, `credibility_delta`, `stumble_type`,
  `mitigation_track_record`, `fresh_money_allocation`. These feed
  `compute_trend_verdict()` and `final_confidence` orders funding priority in
  `rank_key()`, so the choice moves results. Name it as a material
  bound-loosening assumption and state its expected direction on the bound.
- Every arm in Steps 2–5, and a fixed seed.

**0c. Firewall requirements for the oracle arm.** This arm builds calls from
forward returns — look-ahead by design, which is the point of a ceiling.

- Oracle scores exist **only** in this run's scratch data. Never written to the
  DB, never to a shared cache, never to any path another arm or future run
  reads.
- Labels derive from **price data only**. No transcript content and no portfolio
  state informs a label.
- Label the arm unambiguously as a **look-ahead ceiling, not a result**, in
  every output file and every table it appears in.

**0d. Confirm there is no unlabelable tail.** The scorer needs 182 days of
forward price; the cache is frozen at 2026-05-08, giving a cutoff near
2025-11-07. The 195-event population ends at **2024-06-12**, so every event
should be labelable and no fallback should be needed. **Verify this and report
the count.** If any event is unlabelable, report how many and stop to have a
fallback pre-registered rather than inventing one. *A contradiction here is a
finding.*

---

## 5. Step 1 — build the oracle labels

For every event in the locked population, assign the label that turns out
correct: bullish if the stock beat the benchmark by more than the dead band over
the forward window, bearish if it fell by more than the dead band, neutral if it
stayed inside. Use `analyst_direct_scorer.py`'s own constants (`FORWARD_DAYS`,
`DEAD_BAND`, `BENCHMARK`) — do not reimplement them.

Report the three-way split of the oracle labels and confirm it matches the
ground-truth distribution measured in Stage B.

---

## 6. Step 2 — the ceiling under today's allocator

Run the oracle labels through the **real, unmodified** trend layer and allocator
at the settled configuration, X=2.5pp.

**Required reporting, all of it:**

- **Two-level sanity check.** At the **call level**, the oracle's scorecard hit
  rate is 100% by construction among labelable events — state that denominator.
  At the **`final_action` level** it will be below 100%, because `apply_matrix`
  can override a correct call. **That gap measures how often the trend layer
  overrides correct information** and is a finding, not a failure. If the
  call-level rate is not ~100%, the label derivation disagrees with the scorer
  and this arm cannot be trusted; say so and stop.
- **What binds.** For every funding event, the `binding` reason — session limit,
  type cap, available cash, or nothing. Report the share of each. Stage C3 found
  `binding: "session limit"` on every first-purchase event in the control; **if
  the oracle arm is bound the same way, the ceiling is an allocator artifact and
  that is this run's headline.**
- Average cash share, dollar-years invested, return per dollar-year.
- Final value against the control ($179,944.91) and against buy-and-hold
  ($195,584.28).

**Pre-registered as a finding, not a defect: the oracle landing at or below the
control.** It would mean the mapping from direction to action is misaligned with
the horizon the scorecard grades, and it would be the headline of this run.

---

## 7. Step 3 — split the ceiling by direction

Three arms, all through today's allocator at X=2.5pp:

| Arm | Oracle labels used | Everything else |
|---|---|---|
| D-both | all three labels perfect | real calls nowhere |
| D-up | perfect **bullish** labels; every other event keeps the **real** analyst's call | — |
| D-down | perfect **bearish** labels; every other event keeps the **real** analyst's call | — |

**Why this split matters.** Bearish outcomes are 42.1% of events and the real
analyst catches 13.9% of them, so the downside is where the unexploited
information sits. But profit-take fired zero times in 2.4 years, so the
machinery for acting on a Trim is largely untested. **D-down landing near the
control would mean the downside half of the analyst's job is worth nothing here
because the allocator cannot act on it** — a finding about the allocator.

Report each arm's final value, what binds, cash share, and how many events its
labels actually changed relative to the real calls.

---

## 8. Step 4 — is the ceiling limited by prediction or by plumbing?

The core of this run.

Run a small grid: **the real analyst** and **D-both**, each at three session
speed limits — **X = 2.5pp (settled), X = 10pp, X = unlimited**. Everything else
stays at the settled configuration. Six runs.

For each cell report: final value, average cash share, dollar-years invested,
what binds, and maximum peak-to-trough decline.

**The readings, stated now so neither is reached by preference:**

- If **D-both at X=2.5** sits near the control, and **D-both at X=unlimited**
  sits far above it, the analyst's ceiling is limited by **plumbing**. Improving
  the analyst before raising the throttle earns nothing.
- If **D-both at X=unlimited** is also near the control, the ceiling is limited
  by something else again, and neither layer is the constraint. Report it
  plainly.
- If the real analyst improves as much as D-both does when X rises, the throttle
  is the binding constraint for **both**, and the analyst's contribution is
  unchanged by it.

**Do not raise any cap, disable any rule, or change any parameter other than X.**
Rule 3 and the configuration sweep are a separate run.

**This step supersedes the earlier "allocator ceiling from existing sweep
artifacts" idea.** Do not search old sweep outputs; `run-allocator-sweep-db-corpus`
recorded a stalled pipeline whose numbers are unusable, and an in-sample maximum
over a previously searched space is a weaker answer than this grid.

---

## 9. Step 5 — drawdowns

For every arm in this run, report maximum peak-to-trough decline in dollars and
percent, its date range, and the largest single-quarter decline — beside final
value, as Stage C3 did.

**Do not compute a risk-adjusted ratio and do not rank arms by one.** Raw figures
only. Stage C3 established that drawdown tracks how invested an arm is; the
oracle arms will be more invested than the control if the throttle allows it, so
report deployment beside risk and let the comparison stand.

---

## 10. Step 6 — the report

**Scope boundary: report, do not decide.**

Open with a **§0 defined-terms table**, then a **plain-language summary**, both
written to the project instructions' language rules: no statistics vocabulary
without a one-line plain definition, every percentage anchored to what it is a
percentage of, every arm described by what it actually buys and sells the first
time it appears, short sentences, "points" not "pp". **Every oracle figure is
labeled a look-ahead ceiling in the summary itself, not only in a footnote.**

Lead with these sentences, filled in:

> A perfect analyst — one that called every six-month move correctly — would
> have returned **$______** through the allocator as it is configured today,
> against the real system's $179,944.91 and buy-and-hold's $195,584.28. With the
> per-session speed limit removed, the same perfect analyst returns **$______**,
> and the real analyst returns **$______**. Perfect upside calls alone are worth
> **$______**; perfect downside calls alone are worth **$______**. On this
> evidence the analyst's ceiling is limited mainly by **prediction / plumbing /
> neither**.

Then: Step 1's label split, Step 2's ceiling with its sanity checks and binding
shares, Step 3's directional arms, Step 4's grid, Step 5's drawdowns.

**Limitations to state, not argue past:**

- Every oracle figure is a **look-ahead ceiling**, not an achievable result.
- The ceiling is perfect only at the scorecard's horizon and dead band, against
  SPY. An analyst calling shorter or longer moves is outside this bound.
- The oracle's non-direction fields are synthesized, and they move
  `final_action` and funding order through the trend layer. The bound is
  loosened by that choice.
- Every figure describes this 16-company universe and this window, 2020 through
  mid-2024, with **zero 2025 calls**. A prior run found this universe at the top
  of 25 random draws.
- The corpus is a score stream of unverified prompt vintage.
- **No figure here carries a confidence range.** C2 and C4 have not run.
- F2 is unresolved: everything is SPY-benchmarked, which §3.1 does not specify.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number.
- Record every arm's `config_hash` and seed.
- Driver committed before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The most likely: Step 0d's no-tail
  expectation, and Step 4's prediction that raising X lifts the ceiling.
- **Note anything contradicting this prompt's premises.** It was written from
  Stage C3; the repo outranks it.
