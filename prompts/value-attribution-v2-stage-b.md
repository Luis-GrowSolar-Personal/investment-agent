# Value attribution v2 — Stage B: uncertainty and the gate's baseline

**Run ID:** `value-attribution-and-headroom-v2` — **this is a continuation, not
a new run.**
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/value-attribution-v2-stage-b-out.md` (leave
`wrap-ups/value-attribution-and-headroom-v2-out.md` intact — it is Stage A's
record).

**Read first:** `wrap-ups/value-attribution-and-headroom-v2-out.md` (Stage A,
complete) and
`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`.
Stage B is specified in §6 of `prompts/value-attribution-and-headroom-v2.md`;
this prompt supersedes that section with the reconciliation work Stage A's
`next_action` identified.

---

## 1. What Stage B is for

Stage A answered the dollar question. Always-bullish run end to end through the
real allocator returned **$173,102.24** against the real system's
**$179,944.91** — it loses by $6,842.67. Whatever Stage B finds about
percentage points does not reverse that.

**So Stage B is not a decision input about where development effort goes.** It
is repair of the instrument that decides whether a future analyst prompt ships.
That instrument — `PROMOTION_GATE.md` §3.1, implemented in
`analysis/analyst_direct_scorer.py` — currently grades against a baseline the
spec did not specify, on a benchmark the spec did not specify, with no interval
on any figure. Stage B fixes the first and third and measures the size of the
second.

Concretely, what Stage B is worth: a prompt scoring 44.0% reads as **−2.2pp
(fail)** against always-bullish and **+10.3pp (pass)** against always-hold. Same
calls, opposite verdict. And a prompt scoring +2.6pp over v6 is an improvement
or a coin flip depending on an interval nobody has computed. The v10+auto1
question — 37.5–42.5% against v6's 37.5% — was argued for five weeks on point
estimates with no interval attached.

**Scope boundary for the whole run: report, do not decide.** Stage B produces
corrected figures and intervals. It does not promote, reject, or recommend any
prompt version.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** No re-scoring, no evaluator invocations, no LLM
   calls. Every figure comes from already-stored scores and the existing price
   cache. If a step appears to require a model call, **stop and report it**.
   Assert this in the run log before the first computation.
2. **Read-only against the corpus.** No `Analysis` row is modified. No DB writes.
3. **No modification** of `docs/EVALUATION_PROMPT.md`, `server/lib/versions.js`,
   `docs/architecture/VERSION_REGISTRY.json`, or the production prompt. Two
   documentation edits are explicitly authorized in Step B4 and only there.
4. **No price-cache refresh.** `price_cache.json` stays frozen at 2026-05-08.
   Refreshing changes every ground truth and orphans Stage A's arms.
5. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
6. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by prod). **Do not gate on either.**
7. **Do not resolve F2.** Sector-ETF benchmarking needs TAN/SOXX history absent
   from the price cache. Stage B measures F2's likely size (Step B4) and records
   it. It does not fetch prices and does not re-grade.

---

## 3. Step −1 — resume protocol, with one waiver

State continues in `analysis/data/run_state/value-attribution-and-headroom-v2/`.

**Waiver, stated explicitly so it is not applied by mistake:** `CLAUDE.md`'s
resume rule says a changed `prompt_sha256` archives the old state and starts
fresh. **That rule is waived here.** This prompt is a continuation of the same
run under the same `run_id`; Stage A's completed state must be preserved.

- Record this prompt's sha256 as a new key `prompt_sha256_stage_b` **alongside**
  the existing `prompt_sha256`. Do not overwrite it.
- Do not clear `cells.jsonl` or `findings.md`. Append only.
- Leave `steps.stage_a_arm_0b` and `steps.stage_a_arm_0` as `done`.
- Update `steps.stage_b_uncertainty` to `in_progress` as the first action, with
  a one-sentence `next_action`, before reading anything else.

`findings.md` is append-only and written the moment a finding is established —
never held for a final composition pass. Flush `cells.jsonl` per computed cell.

**Running low on budget is a reason to stop cleanly, not to rush.** Mark what
remains `pending` with a precise `next_action` and say plainly that it is a
partial run. B0 and B1 are the highest-value steps; run them first.

---

## 4. Step 0 — hygiene and pre-registration

**0a. Clean tree.** Hard stop if `git_dirty` cannot be recorded `false`. Commit
the Stage B driver before any manifest, as its own commit.

**0b. Extend the pre-registration before computing anything.**
`analysis/data/value_attribution_v2/PREREGISTRATION.json` carries Stage B fields
marked `"NOT YET DEFINED"`. Fill them in **before** the first figure is
computed — their placeholder status is not license to skip pre-registration.
Register:

- both denominators (see B0) and which one each figure below is computed on;
- both baselines (always-bullish, always-hold) and their definitions;
- the bootstrap's resampling unit (ticker), resample count, and **fixed seed**;
- McNemar's variant (exact binomial on discordant pairs) and the significance
  level;
- the thin-year threshold carried from `test2_look_ahead.py` (`n_scoreable < 20`),
  applied identically here.

If the Stage B fields already exist with different content, **abort** and report
the discrepancy — do not overwrite.

---

## 5. Step B0 — reconcile the two denominators *(run first; everything downstream depends on it)*

Stage A's `next_action` flagged this and it is larger than a row count.

Two populations are in play:

- **The scorer's population.** `analyst_direct_scorer.py` / `test2_look_ahead.py`
  grade **362 scoreable ALL16 `Analysis` rows** (359 after the thin-year
  exclusion), across call dates spanning 2020–2025.
- **The simulator's population.** The settled-config driver
  (`sweep_cadence_and_session_model.py` → `run_session_sweep_cell`, via
  `load_events_dedup_on()`) runs **195 call-events**, after same-day dedup,
  over the call-date window the registry records for `settled_control`:
  **2022-01-01 to 2024-06-12**.

These differ on **two axes at once**, and Stage A's note named only one:

1. **Same-day dedup** — multiple transcripts on one date collapse to one event.
   `CLAUDE.md` guardrail 5 records that 44.2% of events in this corpus share a
   date.
2. **Call-date window** — the simulator's window is materially narrower than the
   scorer's span. Test 2's by-year table reports n=45 for 2021 and n=114 for
   2025; neither year is inside 2022-01-01 → 2024-06-12.

**Consequence, and the reason this step runs first:** Test 2's −5.8pp and Stage
A's dollar figures are computed on **different event populations**. Any table
that places a lift figure beside a dollar figure without saying so is comparing
two different samples.

**Required output:**

- The exact mapping: how many of the 362 scoreable rows correspond to the 195
  simulated events; how many are lost to dedup; how many to the call-date
  window; the residual, if any, with an explanation.
- A per-year table of both populations side by side.
- A named, frozen definition of each population, registered in
  `PREREGISTRATION.json`, used consistently for the rest of the run.

**Do not force the two to agree.** `CLAUDE.md` guardrail 5: do not ask a
different algorithm to reproduce another bit-exactly. §3.1's metric is defined
per call, so the scorer's population is the correct denominator for the gate's
own figures. The simulator's population is the correct denominator for anything
compared against dollars. **Every figure in B1–B3 is reported on both**, each
labeled with which population it used.

---

## 6. Step B1 — lift against both baselines

On both populations, by year (applying the `n_scoreable < 20` thin-year
threshold) and in aggregate:

- **always-bullish-relative lift** — `ground_truth == "bullish"`, reproducing
  Test 2's figures as a cross-check on the scorer's population;
- **always-hold-relative lift** — `ground_truth == "neutral"`, i.e. inside the
  ±5% dead band. This is the baseline `PROMOTION_GATE.md` §3.1 actually
  specifies (F1).

**Name the baseline on every figure.** No number in this run's output may appear
as a bare "lift."

**Reproduction cross-check.** On the scorer's population, the always-bullish
aggregate should reproduce Test 2's 40.4% hit / 46.2% baseline / −5.8pp. If it
does not, the discrepancy takes priority over the rest of the step — report it
and stop B1.

**Expectation, stated so a contradiction is legible — this is a diagnostic, not
a gate.** With bullish fixed at 166/359 and a bearish base rate near 20%,
always-hold lands near 33.7% and the lift near **+6.7pp**, against **−5.8pp**
for always-bullish. *A result that contradicts this is a finding, not a reason
to stop.*

---

## 7. Step B2 — the ground-truth distribution

On both populations, report the full three-class distribution of ground truth —
**bullish / bearish / neutral** shares, with counts — in aggregate and by year.

The **bearish base rate** is the figure the 09-13 handoff's "when v6 says trim,
it is wrong roughly four times in five" lacks. Report bearish-call accuracy
beside the bearish base rate so the comparison is explicit.

Also report, for each of the three predicted classes: count, precision, and the
corresponding base rate. With three classes and a bull-skewed tape, precision on
a rare class is mechanically low, and the report should let a reader see that
rather than asserting it.

---

## 8. Step B3 — intervals

**McNemar**, exact binomial on discordant pairs, comparing the analyst's
per-call outcomes against **each** baseline separately. Report the discordant
counts, not only the p-value — b and c are more informative than p here.

**Ticker-block bootstrap.** Resample **tickers** with replacement (the block
unit is the ticker, because 182-day forward windows overlap heavily within a
name and all 16 names share one SPY factor), **≥2000 resamples**, fixed recorded
seed. Report a 95% interval on:

- always-bullish-relative lift
- always-hold-relative lift
- overall hit rate
- bearish-call accuracy

**If a lift figure's interval spans zero, say so plainly and prominently in the
wrap-up's opening summary**, not in a footnote. That is the single most
consequential thing Stage B can find, because it would mean the gate cannot
currently distinguish a real improvement from a lucky draw — and it would apply
retroactively to the v10+auto1 accuracy comparison.

Report the number of independent blocks (16) explicitly alongside n, so a reader
can see why the interval is wider than n would suggest.

---

## 9. Step B4 — record the findings in their home documents

Three documentation edits, authorized here and nowhere else. Make them as one
coherent edit per file, not incrementally.

**B4a — `docs/architecture/PROMOTION_GATE.md` §10.** Record three open items:

1. **F1 — baseline divergence.** §3.1 specifies *"lift over an always-hold
   baseline"* and justifies it (*"an always-'bullish' coin scores ~55–60% in a
   bull sample"*); `analyst_direct_scorer.py` lines 18 and 207 implement
   always-bullish. Include B1's measured figures for both baselines. State that
   until F1 is resolved, no lift figure from this scorer may be cited as §3.1's
   metric — cite it as "always-bullish-relative" or "always-hold-relative,"
   SPY-benchmarked, naming the baseline.
2. **F2 — benchmark divergence.** §3.1 specifies the stock's sector ETF where
   one applies (worked ENPH-vs-TAN example), else SPY; the scorer uses SPY for
   all tickers (*"sector ETFs not yet in price cache"*). Record it as open and
   deferred. **Measure its likely size without resolving it:** report the share
   of scoreable events in Tier 1 domains (solar, storage, semis), since those
   are the rows where SPY-relative and sector-relative grading diverge most.
   Do not fetch prices; do not re-grade.
3. **Arm 0 ≤ control.** Always-bullish through the real allocator returned
   $173,102.24 against $179,944.91 — a comparator that looks superior in §3.1's
   percentage points loses $6,842.67 in dollars. Cite Stage A's manifest and
   key. This is the empirical case that §3.1's current metric grades something
   the system does not monetize.

**B4b — `docs/handoffs/2026-09-13-analyst-value-question.md` §1.** Correct the
"wrong roughly four times in five" language against B2's measured bearish base
rate. Correct it to what the numbers support; do not soften it if they support
it. Leave the rest of the document alone — it is superseded on other points by
the redesign directive, which says so itself.

**B4c — `analysis/analyst_direct_scorer.py`.** Add a comment block at the
`always_bullish_hit` computation recording the F1 divergence and pointing at
§10. **Do not change its behavior** — no new baseline is implemented in this
run. Changing the gate's metric is a decision for Luis, not a Stage B task.

---

## 10. Step B5 — the report

Open the wrap-up with **Scope boundary: report, do not decide.**

Lead with this sentence, filled in:

> On the scorer's population of ____ calls across ____ tickers, v6-era scores
> hit ____%, against an always-bullish baseline of ____% (lift ____pp, 95% CI
> ____ to ____) and an always-hold baseline of ____% (lift ____pp, 95% CI ____
> to ____). The bearish base rate is ____%, against bearish-call accuracy of
> ____%. On §3.1's specified baseline the lift is **positive / negative**, and
> its interval **does / does not** span zero.

Then, in order: B0's reconciliation table, B1's two-baseline lift tables on both
populations, B2's distribution, B3's intervals and discordant counts, B4's edits
with their commit, and the limitations below.

**Limitations to state, not to argue past:**

- Every figure describes `corpus_2026-04-06_to_2026-05-10`, this universe, this
  window. Test 5 put Arm A at the 100th percentile of 25 random universe draws,
  so this universe is not representative.
- The corpus is a score stream of **unverified prompt vintage** — 153 of 362
  scoreable rows fall outside the window the project uses to date v6. The
  `2026-05-02 12:33:23-04` split comparison is still unrun.
- F2 is unresolved, so every figure here is SPY-benchmarked, which §3.1 does not
  specify.
- Stage B says nothing about contribution or headroom. Stages C, D and E remain
  `pending` and are where the layer-attribution question is answered.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** Quote a target as `<value>` —
  `<manifest path>` → `<json.key>`, and name the kind of number: forward draw,
  median across draws, or something else. A figure quoted without provenance is
  a premise to verify, not a fact.
- Record every computation's `config_hash` and random seed.
- Commit the driver before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** B1's +6.7pp expectation is the one most
  likely to be contradicted.
- **Note anything encountered that contradicts this prompt's premises.** This
  prompt was written from Stage A's wrap-up and two adjudication rounds; the
  repo outranks all three.
