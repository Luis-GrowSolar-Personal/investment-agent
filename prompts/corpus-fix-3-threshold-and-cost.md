# Corpus fix 3 of 3 — what ruler did we buy, and what does it cost?

**Run ID:** `corpus-construction` — continuation. **This run does two things,
and the first is the deliverable the whole corpus effort exists to produce.**
**Cost:** **$0 Anthropic API. No transcript scored. No vendor calls.**
**Branch:** `sweep/db-corpus-baseline`. No merge, no push.
**Wrap-up:** `wrap-ups/corpus-fix-3-threshold-and-cost-out.md` — **short**. No
defined-terms table required.

**Read first:** `wrap-ups/corpus-fix-2-balance-and-split-out.md` for the split
sizes, and `wrap-ups/scorecard-repair-out.md` Step 3 for the methodology being
reused.

---

## 1. Step F — the minimum detectable improvement

Re-run `analysis/scorecard_repair_driver.py`'s Step 3 methodology at the **new
block count — train + tune companies only**, since the holdout is not used
during iteration. Reuse that driver; do not reimplement it.

Report, paired and unpaired, exactly as that run did:

- the table of candidate improvement against detection rate;
- the **minimum detectable improvement** — the smallest improvement caught in at
  least 80% of resamples;
- the same under two fallbacks: **half the companies surviving a future
  availability re-check**, and **in-scope strata only**.

**Fill in and report plainly:**

> With this corpus, two prompt versions compared on the same calls can be told
> apart when the real difference is **____ points or larger** — against **6
> points** today. A realistic single iteration is 2 to 4 points.

**Sanity check against a back-of-envelope, and report both.** Precision improves
roughly with the square root of the number of independent companies. From 16
companies at 6 points, the rough expectation is `6 / sqrt(n / 16)` — about 3.3
points at 52 companies, about 2.7 at 78. **If the simulation returns a figure
far below that, say so and treat it as suspect**: the earlier simulation created
extra companies by replaying existing ones under new names, which makes them
more alike than real companies and understates the wobble. **If the simulation
beats the estimate honestly** — because this corpus is spread across sectors
while the old 16 were four solar, four battery and three semiconductor names
moving together — say that too. Report the two numbers side by side either way.

**If the paired figure does not come in below 3 points, say so plainly and
recommend raising the company count before any scoring is commissioned**, with
an estimate of how many more companies would be needed. That recommendation is
the most valuable output available here.

---

## 2. Step G — cost

Report the scoring cost as a range: calls per company × companies, for
**train + tune only** and for **all three splits**, with the per-call assumption
stated explicitly.

Restate, in the summary and not only as a limitation:

> The model that scored the existing corpus was retired in June 2026. Anything
> scored now uses a current model, so this corpus is a **new baseline, not an
> extension of the old one.** Every existing benchmark figure becomes historical
> the moment this corpus is scored.

---

## 3. Constraints

1. **ZERO Anthropic API calls.** Nothing scored. This run commissions nothing.
2. **No vendor calls.**
3. **No spec edits.**
4. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 4. Report

**Scope boundary: report and propose, do not decide.**

Short. Lead with the filled-in sentence from Step F, then the cost, then the
back-of-envelope comparison, then the two fallbacks.

**Limitations to state, not argue past:**

- The projection is a simulation over synthetic challengers, not a measurement
  of a real prompt difference.
- The assumed disagreement rate between two prompt versions is modeled, not
  measured.
- The corpus is selected, not scored — nothing here measures the analyst.
- S4 is defined by an outcome and over-represents failures.
- S5's companies are hindsight-selected and excluded from ruler headlines.

---

## 5. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed.
- Driver reuse is expected; if the existing driver is modified, commit the
  modification before any result.
- Run-specific files only; no `git add .`.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the simulation disagreeing with the square-root
  estimate.
