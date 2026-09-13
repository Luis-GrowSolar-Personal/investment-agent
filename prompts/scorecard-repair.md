# Scorecard repair — make the gate able to tell a real improvement from a lucky one

**Run ID:** `scorecard-repair`
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/scorecard-repair-out.md`

**Read first:** `wrap-ups/value-attribution-v2-stage-b-out.md` (Stage B — the
measurements this run builds on) and `PROMOTION_GATE.md` §3.1 and §10.

---

## 1. Why this run exists

Stage B established three things about the analyst-layer gate metric:

1. It grades against a fixed-answer dummy, and which dummy you pick decides the
   verdict. The same 359 calls produce **−5.8 points** against an always-bullish
   guesser and **+28.7 points** against an always-flat guesser.
2. It attaches no margin of error to anything. On the 195-call simulator subset,
   the gap against the always-bullish guesser runs from 9.7 points worse to 0.6
   points better — zero is inside that range.
3. Both dummies are artifacts of how often each outcome happens (beats 46.2%,
   lags 42.1%, moves-with 11.7%), not statements about skill.

**The consequence is not that v6 is bad. It is that the gate cannot currently
distinguish a better prompt from a luckier sample.** Five weeks were spent
arguing v10+auto1's 37.5–42.5% against v6's 37.5% on point estimates with no
interval. That argument was unresolvable by construction.

**This run does not evaluate any prompt.** It repairs the instrument and then
answers one question:

> **How large would a prompt improvement have to be before this scorecard could
> see it?**

If the answer is larger than a realistic prompt improvement, then prompt
iteration on this corpus cannot be validated at any version count, and that is
the finding.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** No re-scoring, no evaluator invocations, no LLM
   calls. Everything here is arithmetic over already-stored scores. If a step
   appears to need a model call, **stop and report it**. Assert this in the run
   log before the first computation.
2. **Read-only against the corpus.** No `Analysis` row modified. No DB writes.
3. **No price-cache refresh.** `price_cache.json` stays frozen at 2026-05-08.
4. **Do not resolve F2** (sector ETF vs SPY). Every figure here stays
   SPY-benchmarked. F2 is recorded as open in §10 and stays there.
5. **Do not change `analyst_direct_scorer.py`'s existing behavior.** New metrics
   are added; the old ones keep computing exactly as they do now. Both appear in
   every output.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by prod). **Do not gate on either.**

---

## 3. Step −1 — resume protocol

`run_id` = `scorecard-repair`. State in
`analysis/data/run_state/scorecard-repair/`, un-ignored in `.gitignore` and
committed. **Write `progress.json` as the very first action**, before reading
anything: `prompt_sha256`, `driver_commit`, per-step status, one-sentence
`next_action`, `notes[]`.

`cells.jsonl` flushed per computed cell. `findings.md` append-only, written the
moment a finding is established.

Step 3 (the detection threshold) is the highest-value step. If budget runs
short, Steps 1–3 alone are a successful run; mark 4–6 `pending` with a precise
`next_action` and say plainly it is partial.

---

## 4. Step 0 — hygiene and pre-registration

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b.** Write `analysis/data/scorecard_repair/PREREGISTRATION.json` before any
figure is computed: both populations (carried forward from Stage B's B0 — the
362/359-row scorer population and the 195-event simulator population, both
already defined and frozen), the resampling unit (ticker), resample count, fixed
seed, and the detection-threshold simulation's parameters. Abort on mismatch if
the file exists with different content.

**0c. Verify this prompt's arithmetic before relying on it.** Section 5 below
states that luck alone scores 39.6% and v6 scores 40.4%. Recompute both from the
stored corpus. **A contradiction is a finding, not a reason to stop** — report
it and carry the corrected figures through the rest of the run.

---

## 5. Step 1 — the luck-corrected score

The existing metric asks "did v6 beat a fixed-answer dummy." Replace that with
"did v6 beat luck."

**Luck** here means: given how often v6 says each answer, and how often each
outcome actually occurs, how often would v6 be right purely by coincidence?

```
expected-by-luck = Σ over the three answers of
                   (share of calls where v6 said X) × (share of calls where the outcome was X)
```

From Stage B's B2 table on the scorer population:

```
v6 said:     beats 251, lags 44, moves-with 64          (n = 359)
outcome was: beats 166, lags 151, moves-with 42

expected-by-luck = (251/359)(166/359) + (44/359)(151/359) + (64/359)(42/359)
                 = 0.3233 + 0.0516 + 0.0209
                 = 39.6%
observed         = 40.4%
```

Report, on **both** populations:

- observed accuracy, expected-by-luck accuracy, and the gap between them;
- the same figure expressed on a 0-to-1 scale where 0 is "no better than luck"
  and 1 is "perfect" — `(observed − expected) / (1 − expected)`. This is
  **Cohen's kappa**; name it once so it is findable in the literature, and
  report it as a plain gap everywhere else;
- **balanced accuracy** — the average of the three per-answer hit rates, which
  does not reward always guessing the common answer;
- the existing always-bullish-guesser and always-flat-guesser figures unchanged,
  side by side, so the old and new metrics are comparable in one table.

---

## 6. Step 2 — margins of error on everything

Reuse Stage B's ticker-block bootstrap (resample tickers with replacement,
2000 resamples, fixed recorded seed). Report a 95% range for:

- the luck-corrected gap
- balanced accuracy
- observed accuracy
- each per-answer hit rate

Report the number of independent blocks (16) beside every range, so the width is
legible against n.

**Any figure whose range includes zero must be labeled as such in the table
itself**, not in a note below it.

---

## 7. Step 3 — the detection threshold *(the deliverable)*

This is what the run is for. Two versions, and the difference between them
matters enormously.

**3a. Unpaired.** Two prompts scored on different samples. Simulate: take v6's
per-call right/wrong outcomes with their ticker labels. For a candidate
improvement of X points, synthesize a challenger with accuracy X points higher.
Resample tickers with replacement, compute the difference, and record whether
its 95% range excludes zero. Repeat across X = 1, 2, 3 … 15 points.

**3b. Paired — this is the one that matters.** Two prompts scored on the **same
calls**. Model the challenger as agreeing with v6 on most calls and disagreeing
on a minority, with a net gain of X points. Compare per call, resample tickers,
and test whether the paired difference's 95% range excludes zero. Same X sweep.

Pairing removes the between-stock variation that dominates the unpaired case, so
**3b's threshold should be substantially smaller than 3a's.** How much smaller is
the open question and the reason this step exists.

**Report for both:**

- a table of X against detection rate (the share of resamples where the
  improvement is detected);
- the **minimum detectable improvement** — the smallest X detected in at least
  80% of resamples;
- how many additional calls, or additional stocks, would be needed to bring the
  paired threshold down to **3 points**. Report stocks and calls separately —
  with 16 blocks, adding stocks and adding calls do very different things, and
  which one binds is decision-relevant.

**State the assumption behind 3b explicitly:** the disagreement rate between a
prompt and its successor is modeled, not measured. Use v6-vs-v10+auto1's
recorded accuracy spread as a sanity anchor if the per-call outcomes are
recoverable; if they are not, say so and report 3b across a range of
disagreement rates rather than one.

*A result contradicting this prompt's expectation that pairing helps a lot is a
finding, not a reason to stop.*

---

## 8. Step 4 — write the repaired metric into the gate

**4a. `PROMOTION_GATE.md` §3.1.** Replace the primary analyst metric with the
luck-corrected gap plus balanced accuracy, each reported with its 95% range and
its detection threshold. **Preserve the existing definition immediately below as
§3.1-legacy**, marked superseded, with a one-line note on why (Stage B: the
verdict depended on which dummy was chosen). Do not delete it — every benchmark
record in the registry was computed under it.

State in §3.1 that **no prompt-versus-prompt comparison may be cited unless it
reports the paired difference, its 95% range, and whether that range excludes
zero.**

**4b. `analysis/analyst_direct_scorer.py`.** Add the new metrics as additional
outputs. **Existing outputs unchanged.** Every report the scorer prints carries
old and new side by side.

**4c. `docs/architecture/VERSION_REGISTRY.json`.** Do not recompute or restate
any existing benchmark record. Add a note to each analyst-layer record that its
figures were computed under §3.1-legacy. This is a labeling change only.

---

## 9. Step 5 — re-read the v10 question with the repaired instrument

Do **not** re-score anything and do **not** adjudicate v10.

State only what the repaired scorecard implies about the existing v10+auto1
numbers: 37.5–42.5% against v6's 37.5%, given Step 3's detection threshold. If
that spread sits below the threshold, say plainly that the comparison was not
decidable on this corpus and that no amount of re-reading the existing runs will
decide it.

---

## 10. Step 6 — the report

**Scope boundary: report, do not decide.**

The wrap-up opens with a **plain-language summary** written to the project
instructions' language rules: no statistics vocabulary without a one-line plain
definition, every percentage anchored to what it is a percentage of, scoring
dummies called the **always-bullish guesser** and the **always-flat guesser**
(never "baseline"), short sentences. The technical sections follow it.

Lead with this sentence, filled in:

> This scorecard can detect a prompt improvement of **____ points or larger**
> when the two prompts are compared on the same calls, and **____ points or
> larger** when they are not. A realistic prompt improvement is 2 to 4 points.
> On this corpus, prompt iteration **is / is not** measurable.

Then: Step 1's old-vs-new comparison table, Step 2's ranges, Step 3's threshold
curves for both designs and the data-volume answer, Step 4's edits with their
commits, Step 5's reading, and the limitations below.

**Limitations to state, not argue past:**

- Every figure describes this universe and this window. Test 5 put this universe
  at the 100th percentile of 25 random draws, so it is not representative.
- The corpus is a score stream of unverified prompt vintage; the
  `2026-05-02 12:33:23-04` split comparison is still unrun.
- F2 is unresolved, so everything here is SPY-benchmarked, which §3.1 does not
  specify.
- The simulator population covers 2020 through mid-2024 only. It contains **zero
  2025 calls**, against 114 in the scorer population.
- Step 3b's disagreement rate between prompt versions is modeled, not measured.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number. A figure without provenance is a
  premise to verify, not a fact.
- Record every computation's `config_hash` and seed.
- Driver committed before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The two most likely: 0c's arithmetic check,
  and Step 3b's expectation that pairing lowers the threshold substantially.
- **Note anything encountered that contradicts this prompt's premises.** This
  prompt was written from Stage B's wrap-up; the repo outranks it.
