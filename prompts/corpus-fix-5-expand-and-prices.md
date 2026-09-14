# Corpus fix 5 — buy some margin, and get prices for the companies that failed

**Run ID:** `corpus-construction` — continuation.
**Cost:** **$0 Anthropic API. No transcript scored.** Vendor metadata and price
history only.
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/corpus-fix-5-expand-and-prices-out.md` — **short**. No
defined-terms table required.

**Read first:** `wrap-ups/corpus-fix-4-threshold-and-terminal-value-out.md`,
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (rules A1–A6 already
registered), and `analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json`
(77 companies after RMO's removal).

---

## 1. Two independent jobs

**Job 1 — price history for the four failures.** The corpus price cache holds a
completely empty `{}` for NOVA, SUNW, FRC and RMO: no prices at any date, not
just after they failed. The terminal-value rule (A6) graded them anyway, because
a total loss is −100% whatever the entry price was. **That only works for the
coarse one-reading-per-company measurement.** Per-call scoring needs a real
price on each call date, and there is none. Fix that before scoring.

**Job 2 — add roughly 30 companies.** The threshold projection puts the minimum
at 54 companies available for iteration. The corpus has **53**. One short, with
no margin at all. Going to about 110 total moves it from "exactly 2 points, no
margin" to comfortable.

**The two jobs are independent.** Job 1 is smaller — do it first. If budget
forces a stop, finish whichever job is in progress, mark the other `pending`
with a precise `next_action`, and say plainly it is partial.

---

## 2. Constraints

1. **ZERO Anthropic API calls.** Nothing is scored.
2. **No transcript text.** Vendor calls are for availability metadata only.
   **Respect the per-minute rate limit** — the plan allows 20 calls/minute, and
   there is no monthly quota (verified 2026-09-14; the old 1,000 figure was a
   refund condition, not a cap). Throttle and back off. **Do not use the
   vendor's own SDK**, which retries aggressively.
3. **Do not modify `analysis/data/price_cache.json`.** All new price data goes
   in `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
4. **No eligibility or threshold rule changes.** A1's 240-day rule and A2's
   failures rule apply to new candidates exactly as registered.
5. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Job 1 — prices for NOVA, SUNW, FRC

**RMO is out of the corpus. Do not fetch it.**

For each of the three, obtain **daily price history from 2020-01-01 to the last
day it actually traded**, and record that last trading day.

`yfinance` returned nothing under the original tickers. Try, in order, and
record what each attempt returned:

- the original ticker;
- the post-delisting symbol — `SUNWQ` is known to have traded OTC near $0.002;
  try the equivalent `Q` and five-letter forms for NOVA and FRC;
- a second provider if the first yields nothing. **State which provider supplied
  each series.**

Also **verify WOLF has usable price history** — it is still trading and should,
but it was never checked.

**Then confirm the composition rule works end to end:** for each of the three
companies, a call whose 182-day forward window closes **while the stock still
traded** grades from real prices; a call whose window closes **after the last
trading day** grades at terminal value zero per A6. Report how many calls fall
in each category, per company.

**If a series cannot be obtained**, say so plainly and state the consequence:
those companies remain gradable only at the company level, not per call. **Do
not substitute an estimated or interpolated price series.**

---

## 4. Job 2 — add about 30 companies

**4a. Register the expansion first**, dated, as `A7_expansion_round_2` in
`PREREGISTRATION_FIX.json`, **before examining any candidate**. It must state
the per-stratum quotas, the selection rule for each, the seed, and that
eligibility and availability rules are unchanged from A1–A3.

**Target: +30, weighted toward independence.** The ruler gains most from
companies uncorrelated with each other and with the existing set, and the
current corpus is already heavy in solar, storage and semiconductors.

| Stratum | Add | Rule |
|---|---|---|
| S3 — out of scope, mixed cap | **20** | Sector quotas as registered, at most 4 per sector, random within sector, fixed seed. Prefer sectors currently thin or absent in the corpus — report the existing sector counts first and let them drive the choice. |
| S1 — large cap, point-in-time | **6** | Ranks 41–60 by market cap on the same dated 2020-12-31 list, deterministic. |
| S2 — in scope, mixed cap | **4** | Within `DOMAIN.md`, stratified by size, random within band, fixed seed. |

**4b. The failures stratum — attempt, but do not force.** S4 sits at 4 of 8. The
previous attempt rejected all 15 candidates because they were outside
`DOMAIN.md` or not public in 2020.

Try once more with candidates **drawn from the domain itself** — solar, energy
storage, semiconductor, IT/software/cloud or scoped-crypto companies that were
public by 2020-12-31 and subsequently failed. Verify each against the dated 2020
list or the domain definition, with evidence, exactly as A3 required.

**If the target still cannot be reached, report the shortfall and stop there.**
Do not lower A2's thresholds, and do not admit an out-of-domain company.

**One thing to produce rather than decide:** many in-scope failures went public
by SPAC during 2021 and so fail the 2020 test, even though a 2021 listing still
yields four years of calls inside the window. **List the candidates that would
qualify under a relaxed "public by 2021-12-31" rule, with their call counts —
but do not add them.** That is Luis's decision, and this run's job is to put the
option in front of him with numbers attached.

**4c. Availability.** Test every new candidate under the existing rules. Apply
the drop-and-replace mechanically; report every drop.

**4d. Freeze, then re-split.** Write `CORPUS_MANIFEST_V3.json` as a new file,
leaving V2 intact. **No return is looked at before this freeze — confirm that in
the wrap-up.** Then re-run the split with the same seed (`20201231`), re-lock the
holdout, record old and new sha256, and update the dated note in
`PROMOTION_GATE.md` §10 — the only spec edit this run makes.

**4e. Re-check the threshold.** Re-run
`analysis/corpus_construction_stepC_independent_v3.py` at the new train+tune
count, all three spread brackets, 150 trials. Report the paired figure beside
the square-root estimates as that run did, and say whether the corpus now clears
2 points with margin.

---

## 5. Report

**Scope boundary: report and propose, do not decide.** No scoring is
commissioned.

Short. Plain-language summary to the project instructions' language rules, then:

- Job 1: which provider supplied each series, the last trading day per company,
  the split of calls between real-price grading and terminal-value grading, and
  anything still missing;
- Job 2: the new company counts per stratum, every drop and replacement, the
  freeze hash, the new split and holdout hash, and the re-checked threshold;
- the relaxed-rule failure candidates, listed but not added.

**Fill in:**

> The corpus is now **____ companies**, **____** available for iteration, and
> the paired threshold is **____ points**. Price history was recovered for
> **____ of 3** failed companies.

**Limitations to state, not argue past:**

- The corpus is selected, not scored.
- The threshold is a simulation, not a measurement of this corpus.
- The failures stratum is defined by an outcome and over-represents failures.
- Any price series from a second provider may not match the first provider's
  conventions — say which supplied what.

---

## 6. Git — Code runs these, in this order

1. Confirm a clean tree and record `git_dirty: false`. Hard stop if it cannot be
   recorded false.
2. **Commit the drivers first, as their own commit**, before any result file
   exists. *The previous run wrote all its outputs before committing anything —
   do not repeat that.*
3. Commit results — the pre-registration addendum, price cache additions, the
   new manifest, the split, the threshold output.
4. Commit the wrap-up and the `PROMOTION_GATE.md` §10 hash update.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 7. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed and the vendor calls consumed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: no provider having usable history for the failed
  companies, and the domain yielding too few 2020-eligible failures again.
- **Note anything contradicting this prompt's premises.** The repo, the vendor
  and the public record outrank it.
