# Test 2 — does the analyst do better on older calls?

`docs/handoffs/2026-09-03-state-of-play.md` §7 Test 2. **Read §0 of that document
before starting** — it defines every term used here. Also read
`wrap-ups/resolve-open-four-out.md`, whose Step 1c findings change how this test
must be cut.

This file **supersedes and replaces** two earlier drafts. Delete them in Step 0.

## Why this run exists

`DESIGN_PRINCIPLES.md` §4 records that transcript anonymization was attempted and
abandoned in April 2026 — companies are re-identifiable from financial structure
alone — and that *"backtests run with company identity known… a documented
limitation, not an oversight."* The scoring model was trained on data running well
past the 2022–2024 evaluation window, so it may in part be recalling how these
stories ended rather than reading the transcript.

**This run tests that with a signature rather than an argument.** Calls from 2021
and 2022 are more thoroughly represented in a model's training than calls from
2025. If recall is doing the work, measured analyst quality should **decline as
call dates approach the training cutoff**. If it is flat, the analyst is reading
the document.

**Counter-evidence already on the record, to be weighed rather than ignored —
with the caveats `resolve-open-four` established:**

- `data/gate_ledger.json` entry 1 found the *newer* model — later cutoff, more
  knowledge of how 2022–2024 resolved — scored **worse** (4.94pp → −2.5pp).
  **Caveat:** that entry scopes to seven tickers (`ENPH, TTD, AMPX, ENVX, EOSE,
  QS, SPWR`) with **no established names**, ENPH is not in ALL16, and its holdout
  arm never ran (n=0 both sides). Real counter-evidence, but narrower than it
  reads.
- The measured hit rate is 60% — **n=15**. Quote it with that attached or not at
  all.

**No LLM calls, no API spend, no DB writes, no cache refreshes.** This run scores
stored analyses against the frozen price cache. Nothing is re-evaluated.
`price_cache.json` / `fundamentals_cache.json` stay frozen at 2026-05-11; the
staleness warning is expected.

Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`test2-look-ahead-hit-rate-by-year`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.
Write an initial `progress.json` as the very first action, before any reading.
Append to `findings.md` the moment a finding is established.

**Keep `progress.json` in step with reality.** The `corpus-archive` run recorded
steps as `pending` in `progress.json` while `findings.md` showed them done, which
would have made a resume redo an expensive dump and restore. Update the step map
when you finish a step, not at the end.

**Step 3 is the substance.** If budget runs short, drop Step 6, then Step 1 —
never Steps 2–4.

## Step 0 — hygiene, and delete the superseded drafts

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver committed
**before** any manifest, as its own commit. Stash and pop rather than staging
unrelated changes. `testing/` stays gitignored.

**Delete these two files** — both are superseded by this one, and leaving
overlapping Test 2 prompts in the folder is exactly the doc-drift failure mode
`BUILD_STATE.md` records as recurring. Git history preserves them.

```
prompts/hit-rate-by-year.md
prompts/test2-hit-rate-by-year.md
```

You may also find `prompts/corpus-archive.md` and `prompts/resolve-open-four.md`
untracked, plus an incomplete `analysis/data/run_state/corpus-archive/` from a
run that stalled at its Step 1. **Leave all of that alone** — it is a separate
run's state and is not yours to clean up or commit.

---

## Step 1 — three loose ends, manifested (cheap, then move on)

All three are **already answered**; they need a manifest to be citable under
§10b, not investigation. Do not re-litigate them.

**1a. X limit.** `run_session_sweep_cell` returns `max_session_pp_change` (sum of
`pp_change` per `(date, ticker)`). Measured at the settled cell:
**exactly 2.500000pp at phases 0, 10 and 20** — the limit binds and does not
leak. Manifest it. **If it now exceeds 2.5pp, stop and report** — that would
invalidate the X axis and everything resting on it.

**1b. The off-session tax transactions.** Two exist, both `forced-liquidation-
for-tax` on AAPL: `2023-12-31` (0.0208 shares at **192.53**, which *is* that
day's close — in-window, legitimate, ~$4.00) and `2024-12-31` (0.1922 shares at
**213.07**, while that day's actual close was **250.42**). The second is priced
at the **last in-window close (2024-06-12)**, so it is a bookkeeping stamp, **not
look-ahead**. Manifest both. Note for the requote pile that a trade dated
2024-12-31 in a backtest ending 2024-06-12 will mislead anyone filtering the
transaction log by date — the economics are right, the label is not.

**1c. The risk-adjusted X table.** `resolve-open-four` Step 4 ranked the X axis on
**raw final value**, which is ruler-invariant by construction and therefore cannot
detect the effect it was asked about. §5.1 records that X was chosen **for
risk-adjusted return**. Recomputed from that run's own figures (gain over $100k
per point of max drawdown, phase-averaged, seed 0):

| X | gain | gain/dd **session** | gain/dd **daily** |
|---|---|---|---|
| 0.5 | 21,800 | 5,752 | 3,313 |
| **1.0** | 44,149 | **6,140** | 3,566 |
| 1.5 | 60,675 | 5,719 | 3,461 |
| 2.0 | 71,865 | 5,133 | 3,377 |
| **2.5** | 84,819 | 4,897 | **3,615** |
| 3.0 | 89,425 | 4,345 | 3,239 |
| 4.0 | 79,225 | 3,210 | 2,426 |
| 5.0 | 68,497 | 2,544 | 1,961 |
| off | 35,435 | 798 | 733 |

On the **session** ruler X=1.0 beats X=2.5 by **25.4%** risk-adjusted; on the
**daily** ruler X=2.5 wins with X=1.0 1.4% behind — a Rule 2 tie. **The ruler
correction reorders the risk-adjusted ranking, in the settled configuration's
favour.** Reproduce under a manifest and report it as a correction to that run's
"no reordering" conclusion, which holds only for raw final value. If the project
has a previously used risk-adjusted measure, use it and say so; otherwise state
that gain-per-drawdown-point is this run's choice and that it ignores path and
duration.

---

## Step 2 — establish what can actually be scored

Before computing anything, report the shape of the data.

- Scored `Analysis` rows **by call year**, and by (year × ticker), with counts.
- The **latest call date that can be scored at all.** The metric is a
  benchmark-relative forward return over two quarters
  (`analyst_direct_scorer.FORWARD_DAYS = 182`) and `price_cache.json` ends
  **2026-05-08**, so calls after roughly **2025-11-07** have no forward window.
  Derive the cutoff yourself, name it, and use it consistently.
- Which tickers exist in which years. AMPX has no 2021 calls; the universe is not
  constant across the series.

**If any year has fewer than ~20 scoreable calls, say so before reporting a
number for it.** A hit rate on eight calls is noise with a decimal point.

### 2a. Model-version segmentation — do this before any series is computed

**This is the confound that would otherwise invalidate the whole test.**
State-of-play §4.4's census:

```
v6 | claude-sonnet-4-20250514 |  6 rows | calls 2026-05-06 → 2026-06-11
v6 | claude-sonnet-4-6        | 36 rows | calls 2025-08-05 → 2026-08-26
```

**Every version-stamped row has a call date in 2025–2026.** The 764 unstamped rows
— circumstantially, not provably, v6/`sonnet-4-20250514` per §4.4 — carry
everything earlier. On top of that, the drift investigation found **18 August-2026
rows were scored by the ungated v10+auto1 prompt while labelled v6**.

So a decline at the recent end of the series has three explanations, perfectly
confounded: look-ahead diminishing (the hypothesis), `sonnet-4-6` simply being
worse (measured at −7.44pp on the ledger's scope), or v10+auto1 prompt drift. The
model delta alone is larger than any year-over-year movement this series is
likely to show.

**Therefore:** compute the primary series on **one model only** — the unstamped
presumed-v6 rows, roughly 2021–2024, which still gives a four-year lever arm.
Report the 2025 tail **separately and labelled as model-contaminated**, never
merged into the primary series. State how many rows survive the forward-window
cutoff in that tail and who scored them. State §4.4's provenance caveat plainly,
since the clean series rests entirely on rows whose version is inferred.

---

## Step 3 — the series, decomposed

Use `analysis/analyst_direct_scorer.py`'s methodology exactly as the gate computes
it — benchmark-relative, 182 days, ±5% dead band. No re-scoring; stored scores are
the input.

### 3a. Report the components, not just lift

`lift = analyst_hit_rate − baseline_hit_rate`, and the baseline is **always
predict bullish**. Per call year, report **all** of:

| column | why |
|---|---|
| n scored calls | so the reader can discount thin years |
| analyst hit rate | the quantity the look-ahead hypothesis is about |
| **baseline hit rate** | what the naive rule achieved that year |
| lift | the gate's own unit |
| **headroom captured** = (hit − baseline) / (1 − baseline) | the cross-year comparable — see 3b |
| ground-truth mix (bullish / bearish / neutral counts) | exposes the regime directly |
| distinct tickers | exposes mix changes |

### 3b. Why lift alone cannot answer this

Lift is **mechanically capped at (1 − baseline)**. With a baseline near 0.85, a
*perfect* analyst can score at most +15pp; with a baseline of 0.40 it could score
+60pp. 2022 was a bear market for these names and 2023–24 a bull market, so **a
declining lift series is the null expectation here, not a signal** — it is what
the metric does when the baseline rises, regardless of skill.

The earlier draft of this prompt claimed lift "substantially controls for" regime.
It does not, and that error would have manufactured the alarming result.

So: **the look-ahead hypothesis predicts the *analyst hit rate* declines. The
baseline confound predicts only *lift* declines.** Decomposed they are
distinguishable; aggregated they are not. Report both, and say which one moved.

### 3c. Accuracy on bearish outcomes specifically

Split the analyst hit rate by ground truth — accuracy on events that turned out
bullish, bearish, and neutral. In a rising window an analyst that says Add a lot
posts good aggregate accuracy while carrying no information. **Calling the downs
is where skill shows, and it is what the aggregate hides.** Report bearish-outcome
accuracy as a first-class series alongside the headline.

### 3d. Uncertainty

Attach a **binomial confidence interval to every rate**. The corpus is ~800
analyses across five call years, so a year bucket is small and a year × scope cell
smaller. **A slope that fits inside its own error bars is not a trend** and must
not be reported as one. Rule 2 applies to overlapping intervals exactly as it does
to overlapping draw ranges: **tied, reported as tied, never ranked.**

---

## Step 4 — control the confounds

**Ticker mix.** Recompute the series restricted to the subset of tickers present
in *every* year. Report both. If the two series disagree in shape, the
full-universe series is measuring mix, not time.

**Scope.** `resolve-open-four` Step 1c: lift is **−6.31pp on established (n=111)**
and **+1.19pp on speculative (n=84)** — a 7.5pp spread across the axis. If the
established/speculative share of calls shifts across years, and with speculatives
entering the corpus at different dates it probably does, an aggregate year trend
is confounded again. **Report the year × scope grid with n in every cell**, and
where a cell is too thin to carry a claim, say so and do not draw one.

**Regime.** Already covered by reporting each year's baseline and ground-truth mix
alongside its lift, so a year where the baseline itself moved is visible rather
than inferred.

**Model.** Per Step 2a, the primary series is single-model by construction.

State plainly if any control makes the series uninterpretable.

---

## Step 5 — read the shape, against a rule fixed before the numbers

- Is there a **monotonic decline** in the *analyst hit rate* toward recent call
  dates?
- Is any apparent decline larger than year-to-year variation in the early years,
  and larger than its own confidence intervals — a trend, or a wobble?
- **Do not assert a specific training-cutoff date.** No cutoff is established in
  this repo, and inventing one to fit an inflection would be exactly the error
  this run exists to avoid. Report the series and let its shape speak.

**Pre-declared reading, agreed before results are seen:**

| Shape | Reading |
|---|---|
| Flat, or no decline exceeding early-year variation and CI width | Evidence **against** look-ahead driving the scores. Report as a positive finding. |
| Monotonic decline in analyst hit rate, larger than early-year variation and CIs | Consistent with look-ahead, **not proof** — model quality, transcript quality and coverage all changed over the same period. Name the alternatives rather than concluding. |
| Lift declines but analyst hit rate is flat | **Baseline artifact**, not look-ahead. Report it as such explicitly. |
| Non-monotonic, or dominated by thin years or wide CIs | Inconclusive. Say inconclusive; do not pick the reading that is more interesting. |

### How strong a flat result actually is

§7 calls a flat line "strong evidence." **It is not, and the wrap-up must not say
so.** `claude-sonnet-4-20250514`'s training cutoff sits well after this corpus, so
the entire series is historical to the scorer and there is no in-window cutoff
boundary to exploit as a natural experiment. What is being tested is *density of
coverage* — a weak, indirect gradient.

Calibrate accordingly: a **declining** hit rate would be alarming and actionable;
a **flat** one is *weak* evidence against look-ahead, equally consistent with a
model whose recall of 2022 and 2024 is similar. Overstating a flat result would
put a false reassurance into the state of play. The §6.2 counter-evidence remains
the better argument, and this test adds to it rather than replacing it.

---

## Step 6 — optional, only if Steps 1–5 land with budget to spare

Hit rate by **position age at the time of the call** rather than by calendar year:
do calls scored early in a position's life do better than later ones? That bears
on whether the analyst adds information on re-evaluation or mostly at first
contact — which matters because the zero-information control showed all 16 names
receive a starter regardless of score. **Drop this before dropping anything
else.**

---

## Rules

**Rules 1, 2 and 4 unchanged.** Rule 2 extends to overlapping confidence intervals
as stated in 3d.

**Every drawdown figure must name its ruler** — session-sampled or daily-marked —
including any quoted from earlier work. **State for every figure whether it is a
forward draw, a median across draws, or a phase-averaged median.**

## Report

Scope boundary: **report, do not decide.** Do not amend `DESIGN_PRINCIPLES.md`, do
not adopt or reject the look-ahead prohibition (that is Test 6), do not change any
prompt, model, gate or configuration, do not resolve §4.5, and do not edit
`docs/handoffs/2026-09-03-state-of-play.md`.

Open with resume status, then:

> **X limit [holds at X pp / BREACHED]. 2024-12-31 txn: bookkeeping stamp
> confirmed. Risk-adjusted X: daily optimum [X]pp vs session optimum [X]pp —
> ruler [does / does not] reorder. Scoreable calls by year: [table]. Primary
> series (single-model, [years]): analyst hit rate [series], baseline [series],
> headroom captured [series], bearish-outcome accuracy [series]. Shape:
> [flat / declining / baseline artifact / inconclusive]. Full-universe and
> fixed-ticker series [agree / disagree]. Year × scope: [X]. Model-contaminated
> tail reported separately: [n rows]. Reading under the pre-declared rule: [X],
> at [strength], given the weak gradient this test can resolve.**

Flag plainly: any year too thin to report, any disagreement between the series,
any previously published number that turns out to be wrong, and whether this
changes the priority of §7 Test 6 — a clearly flat result makes that probe much
less urgent, and saying so is useful.

**A diagnostic that contradicts an expectation stated in this prompt is a finding,
not a reason to stop.** That includes the Step 1c table, computed by hand from
another run's stdout and a hypothesis until reproduced, and the Step 1a/1b
figures, which came from an unmanifested run.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**. All queries `SELECT` only.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay frozen
  at 2026-05-11.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — the manifest path and exact JSON
  key, or the commit and path.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
