# Corpus construction — build a ruler that can see a 2-point improvement

**Run ID:** `corpus-construction`
**Cost:** **$0 in Anthropic API spend. No transcript is scored in this run.**
Scoring is a separate, later, paid run. This run selects, verifies and freezes.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/corpus-construction-out.md`

**Read first:** `wrap-ups/scorecard-repair-out.md` (the detection threshold and
why 16 companies is the binding constraint),
`wrap-ups/value-attribution-v2-stage-d-out.md` (the analyst's headroom), and
`docs/architecture/DOMAIN.md` (the investable scope).

---

## 1. Why this run exists

The scorecard cannot currently detect a prompt improvement smaller than **6
points** when two prompts are compared on the same calls. A realistic single
iteration is 2 to 4 points. So prompt work cannot be validated at any version
count on the present corpus.

The binding constraint is **independent companies, not calls.** The ticker-block
bootstrap has 16 blocks, and those 16 are heavily correlated — four solar names,
four battery names, three semiconductor names. Correlated companies do not buy
independent information. Quadrupling the companies brought the simulated
threshold to about 1 point; quadrupling the calls on the same 16 only reached 2.

**This run produces one deliverable: a frozen, committed corpus manifest** —
which companies, in which stratum, in which split, with transcript and price
availability confirmed and a cost estimate attached. It scores nothing.

**Two things it must not do**, because either would waste the scoring budget
that follows:

- **Select on outcomes.** Companies are chosen by rules fixed before any return
  is looked at.
- **Select survivors.** Every index-derived stratum is built from a **dated
  point-in-time constituent list**, including companies later removed, acquired
  or collapsed.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** No transcript is scored, summarized or passed
   to any model. If a step appears to need one, **stop and report it**. Assert
   this in the run log before Step 1.
2. **No bulk transcript download.** The vendor is used for **availability
   metadata only** — which companies have which call dates. Check the vendor's
   remaining call budget before enumerating anything
   (`wrap-ups/ec_vendor_evaluation`-era constraints still apply) and report the
   budget consumed by this run.
3. **Do not modify `analysis/data/price_cache.json`.** It is frozen at
   2026-05-08 and every existing benchmark replays off it. Any new price data
   goes in a **new file** under a new name.
4. **Do not write `Analysis` rows.** No DB writes of scored output. A corpus
   manifest and its state files are the only artifacts.
5. **No spec edits.** `PROMOTION_GATE.md`, `VERSION_REGISTRY.json`,
   `EVALUATION_PROMPT.md`, `versions.js`, the production prompt: untouched.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production).

---

## 3. Step −1 — resume protocol

`run_id` = `corpus-construction`. State in
`analysis/data/run_state/corpus-construction/`, un-ignored in `.gitignore` and
committed. **Write `progress.json` as the very first action**, before reading
anything. `cells.jsonl` per stratum; `findings.md` append-only.

**Stopping is permitted only after Step 4 is complete.** Steps 1–4 are the
selection and the availability check; stopping before them leaves nothing usable.

---

## 4. Step 0 — hygiene and pre-registration

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b. Pre-register the entire selection procedure before looking at a single
company's returns.** Write `analysis/data/corpus_v2/PREREGISTRATION.json`
containing: every stratum and its quota, the exact selection rule for each, the
random seed, the point-in-time source and its date, the availability thresholds,
the drop-and-replace rule, and the three-way split procedure. Abort on mismatch
if it exists with different content.

**This ordering is the whole point of the run.** Any rule written after a return
is observed is outcome selection, however innocent it looks.

---

## 5. Step 1 — the point-in-time universe

Build a **dated constituent list of the S&P 500 as of 2020-12-31**, from a
source that records the index as it stood then, **including companies later
removed, acquired, or failed.**

- Name the source, its URL, and its as-of date in the manifest.
- Report how many of the 2020 constituents are **no longer** in the index today.
  **If that number is zero, the source is a survivor list and must be
  rejected** — say so and stop rather than proceeding on it.
- Record each company's 2020 market-cap rank where the source supplies it.

*A source that cannot supply a dated list is a finding. Report what was tried.*

---

## 6. Step 2 — the strata

Six strata, quotas fixed here, selection rules pre-registered in 0b.

| # | Stratum | Target | Rule |
|---|---|---|---|
| S1 | Large cap, point-in-time | 20 | Ranks 21–40 by market cap on the 2020-12-31 list. Deterministic, no randomness. |
| S2 | In scope, mixed cap | 16 | Within `DOMAIN.md`'s universe. Stratified by size: 6 large, 6 small, 4 micro. Random within each size band, fixed seed. |
| S3 | Out of scope, mixed cap | 20 | Outside `DOMAIN.md`. Sector quotas — at most 4 per sector — then random within sector, fixed seed. Stratify by size as in S2. |
| S4 | Failures | 8 | Companies on the 2020-12-31 list, or in `DOMAIN.md`'s universe in 2020, that subsequently failed, were acquired under distress, or delisted. Selection is by **2020 membership**, not by knowing they failed. |
| S5 | Continuity | 16 | The existing ALL16. Carried forward unchanged. |
| S6 | Reserve | — | Named replacements per stratum, ranked, used only by Step 4's drop rule. |

**S4 exists because the analyst catches 14% of real declines and nothing has
tested whether that is fixable.** Companies with earnings calls in the quarters
before they collapsed are the direct test. Candidates to consider, each to be
verified as a 2020 constituent or in-scope name before inclusion: SVB Financial,
First Republic, Signature Bank, Proterra, Fisker, Nikola, Lordstown, Li-Cycle,
Wolfspeed.

**S5 carries a permanent warning.** The existing 16 were chosen by hand with
hindsight and sit at the top of 25 random universe draws. They are kept for
continuity with every prior measurement. **They must be excluded from the
ruler's headline figures** and that exclusion must be recorded in the manifest,
not left to a future session to remember.

Target total: **80 companies, of which 64 are new.**

---

## 7. Step 3 — availability, before any commitment

For every selected company, using vendor **metadata only**:

- how many earnings calls exist in the window **2020-01-01 to 2025-12-31**;
- the first and last available call date;
- any gap longer than two consecutive quarters.

And, separately, whether **daily price history** covers the full window plus 182
days beyond the last call, for the company and for SPY. Report which price
source would supply it and what it would cost. **Write nothing to
`price_cache.json`.**

**Drop rule, pre-registered in 0b and applied mechanically:** a company with
fewer than **12** calls in the window, or a gap longer than two quarters, is
dropped and replaced by the next name in that stratum's S6 reserve list. Record
every drop and its replacement. **Do not exercise judgment here** — if the rule
produces an odd-looking set, report that rather than overriding it.

---

## 8. Step 4 — freeze the selection, then look at outcomes

**In this order, and the order is the point.**

**4a. Freeze.** Write the final company list to
`analysis/data/corpus_v2/CORPUS_MANIFEST.json` with each company's stratum,
availability figures, and provenance. Commit it. Record its sha256 in
`progress.json`.

**4b. Only then, measure outcome balance.** Using the same grading the scorecard
uses — 182-day forward return against SPY with a ±5% dead band — report the
three-way split of outcomes across the frozen corpus: beats / lags / moves-with.
Compare to the existing corpus's 46.2% / 42.1% / 11.7%.

**If the balance is poor, do not re-pick.** Swapping companies after seeing
returns is outcome selection and would destroy the corpus's value. The permitted
response is to **add a new stratum with its own pre-registered rule**, recorded
as a second, dated pre-registration. State this explicitly in the wrap-up so a
future session does not quietly "improve" the list.

---

## 9. Step 5 — the three-way split, and lock the holdout

Split the corpus **by company**, never by call — calls from one company must
never straddle two splits.

| Split | Share | Purpose |
|---|---|---|
| Train | ~1/3 | Prompt iteration. |
| Tune | ~1/3 | Checking a candidate before it goes near the holdout. |
| **Holdout** | ~1/3 | **Scored only when a prompt is believed finished.** |

Stratified so each split carries a proportional share of every stratum,
including S4's failures. Fixed, recorded seed.

**Lock the holdout.** Record its company list and sha256 in the manifest, and
write a standing note into `PROMOTION_GATE.md` §10 stating that the holdout is
not to be scored during iteration and that any run touching it must say so
prominently in its wrap-up. **This is the one thing that keeps the ruler
meaningful after twenty iterations**, and it is worth more than the third of
measurement power it costs.

---

## 10. Step 6 — what ruler are we actually buying?

Before any money is spent, say what this corpus would be able to detect.

Re-run `scorecard-repair`'s Step 3 simulation at the **new block count** — the
number of companies in train + tune, since the holdout is not used for iteration
— and report the minimum detectable improvement, paired and unpaired, exactly as
that run did.

Report it for the realistic case and for two fallbacks: **if only half the
selected companies survive the availability check**, and **if only the in-scope
strata are used**.

**If the projected paired threshold does not come in below 3 points, say so
plainly and recommend raising the company count before any scoring is
commissioned.** That is a cheaper correction now than after 1,600 scoring calls.

---

## 11. Step 7 — cost, and one consequence to state plainly

Report the scoring cost of the corpus as a range: calls per company × companies,
for train+tune only and for all three splits, with the per-call assumption
stated.

Then state this, in the wrap-up's summary and not only in a limitation:

> The model that scored the existing corpus was retired in June 2026. Anything
> scored now uses a current model, so **this corpus is a new baseline, not an
> extension of the old one.** Every existing benchmark figure — the settled
> control, the zero-information floor, the sizing-channel null, the small-cap
> materiality record — becomes historical the moment this corpus is scored, and
> cannot be compared against figures computed on it.

---

## 12. Step 8 — the report

**Scope boundary: report and propose, do not decide.** This run does not
commission any scoring.

Open with a **§0 defined-terms table**, then a **plain-language summary**, both
written to the project instructions' language rules: no statistics vocabulary
without a one-line plain definition, every percentage anchored to what it is a
percentage of, short sentences, "points" not "pp".

Lead with these sentences, filled in:

> The corpus is **____ companies**, of which **____** are new, spanning
> **____ earnings calls** across 2020 to 2025. With this corpus, the scorecard
> would be able to detect a prompt improvement of **____ points or larger** when
> two prompts are compared on the same calls — against **6 points** today.
> Scoring it would cost roughly **$____**. Of the 2020 companies selected,
> **____** are no longer in the index, and **____** failed outright.

Then: Step 1's source and its survivor check, Step 2's strata with every
company listed, Step 3's availability and every drop-and-replace, Step 4's
outcome balance, Step 5's three splits with the holdout's hash, Step 6's
projected threshold, Step 7's cost.

**Limitations to state, not argue past:**

- The corpus is selected, not scored. Nothing here measures the analyst.
- S5's 16 companies are hindsight-selected and excluded from ruler headlines.
- Outcome balance was measured after freezing and cannot be corrected by
  re-picking.
- Step 6's projected threshold is a simulation over synthetic challengers, not a
  measurement of a real prompt difference.
- Vendor availability metadata may disagree with what the scoring run actually
  retrieves.

---

## 13. Standing rules

- `python3`, zsh, macOS Tahoe. Branch `sweep/db-corpus-baseline`; no merge to
  `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number.
- Record the vendor call budget consumed, and every random seed.
- Driver committed before any manifest, as its own commit. Run-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The most likely: Step 3's availability being
  worse than assumed for micro caps and for companies that failed.
- **Note anything contradicting this prompt's premises.** The repo and the
  vendor outrank it.
