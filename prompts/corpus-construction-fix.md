# Corpus construction — fix the availability rules, then finish the run

**Run ID:** `corpus-construction` — **continuation, not a new run.**
**Cost:** **$0 in Anthropic API spend. No transcript is scored in this run.**
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/corpus-construction-fix-out.md` (leave
`wrap-ups/corpus-construction-out.md` intact — it is the first pass's record).

**Read first:** `wrap-ups/corpus-construction-out.md` (Steps 0–4, complete),
`analysis/data/corpus_v2/CORPUS_MANIFEST.json` (frozen, sha256
`0e036e97…`), and `analysis/data/run_state/corpus-construction/progress.json`.

---

## 1. Why this run exists

The first pass applied its availability rules mechanically and surfaced a
design error in those rules. That was the correct behavior and this run does not
second-guess it.

**The error: a company that fails stops holding earnings calls.** The rule
required 12 calls in the window and no gap longer than two quarters. So it
deleted First Republic (6 calls, stopping at receivership), Romeo Power (6,
stopping at the forced merger) and Sunworks (10, stopping at bankruptcy), and
SVB Financial was absent from the vendor entirely. **The failures stratum ended
at 2 of 8 — the rule requires survival, and survival is the one thing that
stratum exists to not require.**

**A second, smaller error:** the two-quarter gap limit, measured in quarters,
dropped Intel (2.01), Coca-Cola (2.02), McDonald's (2.02) and Thermo Fisher
(2.13). Those are calendar rounding artifacts on companies with complete
coverage, not coverage holes.

This run fixes both rules, re-runs the availability check, re-freezes, and
**finishes Steps 5 through 7 — the split, the detection-threshold projection and
the cost estimate — which the first pass did not reach.** Those three are the
decision inputs; without them nothing can be commissioned.

---

## 2. The process rule that governs this run

Changing an availability rule after seeing which companies it dropped is
legitimate: **that is selection on data coverage, not on returns.** But the
outcome balance is now known (44.4% / 35.2% / 20.4%), so the change must be
insulated from it.

**Therefore:**

1. Write the new rules as a **second, dated pre-registration** before touching
   any company.
2. **Justify each new rule solely by the coverage finding**, in writing, in that
   file. No justification may reference the outcome balance, any company's
   return, or which companies would come back in.
3. **Do not look at any return until Step D.** The re-freeze happens first.

State in the wrap-up that this ordering was followed, and name anything that
compromised it.

---

## 3. Absolute constraints

1. **ZERO Anthropic API calls.** Nothing is scored. If a step appears to need a
   model call, **stop and report it**. Assert this in the run log before Step A.
2. **No bulk transcript download.** Vendor metadata only. Report the call budget
   consumed and the running total for the period.
3. **Do not modify `analysis/data/price_cache.json`.** New price data goes in
   `analysis/data/corpus_v2/corpus_v2_price_cache.json`, as the first pass did.
4. **Do not write `Analysis` rows.**
5. **No spec edits except the one authorized in Step E** (the holdout note in
   `PROMOTION_GATE.md` §10). `VERSION_REGISTRY.json`, `EVALUATION_PROMPT.md`,
   `versions.js` and the production prompt: untouched.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production; GOOGL absent from the
   vendor — already documented, not new).

---

## 4. Step −1 — resume protocol, and where stopping is allowed

State continues in `analysis/data/run_state/corpus-construction/`.

**The changed-prompt-archives-state rule is waived.** Record this prompt's
sha256 as `prompt_sha256_fix` alongside the existing key; do not overwrite it.
Append to `cells.jsonl` and `findings.md`. Leave Steps 0–4 `done`.

**Stopping is permitted only after Step F is complete** — the detection-threshold
projection. Steps A through F are cheap: one pre-registration, one availability
pass, one freeze, one balance measurement, one split, one simulation. **The
first pass stopped at the freeze and left the decision inputs unmeasured; do not
repeat that.** If budget genuinely runs out, stop cleanly with a precise
`next_action` and say plainly it is partial.

---

## 5. Step A — the second pre-registration

Write `analysis/data/corpus_v2/PREREGISTRATION_FIX.json`, dated, **before any
company is examined**. It contains:

**A1. The gap rule, in days.** Replace "no gap longer than two quarters" with a
threshold in **calendar days**. Default **240 days**. Justify the number in the
file by reference to reporting cadence — roughly 91 days between ordinary calls,
roughly 182 for one skipped quarter — and state that the purpose is to separate
a real coverage hole from calendar drift.

**Report the distribution of maximum gaps across every candidate**, and how many
companies sit within 20 days on either side of the threshold. **If a large
share sits near the line, the threshold is brittle and that is a finding**, not
something to tune away.

**A2. A separate rule for the failures stratum (S4).** The general rule cannot
apply. Register instead:

- **at least 4 calls** in the window;
- **no trailing-gap test** — the trailing gap is the company's death and is the
  reason the company is in this stratum;
- **at least 2 calls in the 12 months before the terminal event** (bankruptcy,
  receivership, forced merger, delisting). This is the substantive requirement:
  without calls close to the end, the stratum cannot test what it exists to
  test;
- internal gaps before the terminal event still subject to A1's day threshold.

**A3. New S4 candidates, with membership verified before selection.** S4's
reserve list is exhausted. Register a new candidate list, and for each name
record **why it was eligible in 2020** — an S&P 500 constituent on the
2020-12-31 dated list, or within `DOMAIN.md`'s universe in 2020 — with the
evidence. A company that was neither is not eligible, however well-known its
collapse.

Candidates to verify and consider, not a pre-approved list: Signature Bank,
Lordstown, Fisker, Nikola, Proterra, Li-Cycle, Canoo, Core Scientific, Amyris,
Virgin Orbit, Rite Aid, Yellow Corporation, Party City, Emergent BioSolutions,
Invacare. **Verify each before including it. Report every rejection and its
reason.**

**A4. The S4 weighting disclosure.** S4 is a stratum defined by an outcome, so
it deliberately over-represents failures relative to any real population. **Every
ruler figure computed on this corpus must be reported twice — including S4 and
excluding it — and S4's share of companies and of calls must be stated.**
Register this now so it cannot be forgotten later.

---

## 6. Step B — re-run availability under the new rules

Using vendor metadata only:

- re-test the companies the first pass **dropped** (INTC, KO, MCD, TMO, LIN,
  POWI, FRC, RMO, SUNW, and any others recorded in the first pass) against the
  new rules;
- test the new S4 candidates from A3;
- re-test every company **already frozen**, so the whole corpus is evaluated on
  one consistent rule set.

**A company that failed the old rule and passes the new one is restored to its
original stratum.** A replacement brought in under the old rule stays — do not
evict a passing company to make room for a restored one; report the resulting
stratum sizes as they fall.

Report, per stratum: members before, members after, every restoration, every new
addition, and every remaining shortfall. **If S4 still cannot reach 8, report
the number it reaches and why**, and do not lower A2's thresholds to close the
gap.

---

## 7. Step C — re-freeze

Write `analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json` — a new file, leaving
the first manifest intact as the record of the first pass. Commit it. Record its
sha256 in `progress.json`. Report the total company count and the total calls.

**No return has been looked at up to this point. Confirm that in the wrap-up.**

---

## 8. Step D — outcome balance, reported only

Re-measure the three-way outcome split on the re-frozen corpus, using the same
method as the first pass, and report it beside the first pass's 44.4% / 35.2% /
20.4% and the existing corpus's 46.2% / 42.1% / 11.7%.

Report it **including and excluding S4**, per A4.

**Do not re-pick on the result.** The only permitted response to a balance
judged poor is a new stratum under its own dated pre-registration.

Carry forward the first pass's stated weakness: this is one reading per company,
not per call. **If the full per-call date list is now available from Step B's
metadata at no extra vendor cost, compute the per-call version instead and say
so.** Do not spend vendor calls solely to improve this figure.

---

## 9. Step E — the three-way split and the holdout lock

Split **by company, never by call.** Train / tune / holdout, roughly equal
thirds, stratified so each split carries a proportional share of every stratum
including S4. Fixed, recorded seed — `20201231`, as `progress.json` already
names.

**Lock the holdout:** record its company list and sha256 in the manifest, and
add the single authorized note to `PROMOTION_GATE.md` §10 stating that the
holdout is not to be scored during prompt iteration, and that any run touching
it must say so prominently in its wrap-up.

Report each split's company count, call count, and stratum composition.

---

## 10. Step F — what ruler does this buy? *(the deliverable)*

**This is why the run exists. Do not stop before it.**

Re-run `analysis/scorecard_repair_driver.py`'s Step 3 methodology at the new
block count — **train + tune companies only**, since the holdout is not used for
iteration — and report the minimum detectable improvement, paired and unpaired,
exactly as that run did.

Report it for the realistic case and for two fallbacks: **if only half the
companies survive a future availability re-check**, and **if only the in-scope
strata are used**.

**Fill in and report plainly:**

> With this corpus, two prompt versions compared on the same calls can be told
> apart when the real difference is **____ points or larger** — against **6
> points** today. A realistic single iteration is 2 to 4 points.

**If the paired figure does not come in below 3 points, say so plainly and
recommend raising the company count before any scoring is commissioned.** That
recommendation is the most valuable output this run can produce.

---

## 11. Step G — cost

Report the scoring cost as a range: calls per company × companies, for train+tune
only and for all three splits, with the per-call assumption stated.

Restate, in the summary and not only as a limitation:

> The model that scored the existing corpus was retired in June 2026. Anything
> scored now uses a current model, so this corpus is a **new baseline, not an
> extension of the old one.** Every existing benchmark figure becomes historical
> the moment this corpus is scored.

---

## 12. Step H — the report

**Scope boundary: report and propose, do not decide.** This run commissions no
scoring.

Open with a **§0 defined-terms table**, then a **plain-language summary**, both
written to the project instructions' language rules: no statistics vocabulary
without a one-line plain definition, every percentage anchored to what it is a
percentage of, short sentences, "points" not "pp".

Lead with the Step F sentence above, then the corpus size, then the cost.

Then: Step A's new rules and their coverage-only justification, Step B's
restorations and shortfalls with the gap distribution, Step C's freeze hash,
Step D's balance both ways, Step E's splits and holdout hash, Step F's
projections, Step G's cost.

**Limitations to state, not argue past:**

- The corpus is selected, not scored. Nothing here measures the analyst.
- S4 is defined by an outcome and over-represents failures; every ruler figure
  is reported with and without it.
- S5's 16 companies are hindsight-selected and excluded from ruler headlines.
- The first pass's survivor count (59) is a lower bound, not exhaustive.
- Outcome balance was measured after freezing and cannot be corrected by
  re-picking.
- Step F's projection is a simulation over synthetic challengers, not a
  measurement of a real prompt difference.
- Vendor metadata may disagree with what a scoring run actually retrieves.

---

## 13. Standing rules

- `python3`, zsh, macOS Tahoe. Branch `sweep/db-corpus-baseline`; no merge to
  `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number.
- Record the vendor call budget consumed and every random seed.
- Driver committed before any manifest, as its own commit. Run-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The most likely: S4 still failing to reach 8
  even under A2's rules, and the gap-threshold distribution being more brittle
  than 240 days assumes.
- **Note anything contradicting this prompt's premises.** The repo and the
  vendor outrank it.
