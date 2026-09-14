# Corpus fix 7 — make the manifest match what was registered

**Run ID:** `corpus-construction` — continuation. **Corrections only.**
**Cost:** **$0 Anthropic API. No transcript scored.** Price fetches for one
company; no vendor calls expected.
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/corpus-fix-7-manifest-corrections-out.md` — **short**.

**Read first:** `wrap-ups/corpus-fix-6-price-coverage-gate-out.md` §3 (the two
bookkeeping defects), `analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (A1–A8),
`analysis/data/corpus_v2/selection_working.json`, and
`analysis/data/corpus_v2/TICKER_ALIASES.json`.

**`corpus-fix-5`'s Job 2 (the expansion) stays pending** and runs after this. Its
target depends on the corrected count this run produces.

---

## 1. Why this run exists

The price-coverage sweep failed 8 of 77 companies, and only two failed for price
reasons. The rest expose problems upstream:

**A threshold applied to the wrong bucket.** The gate borrowed A1's 12-call line.
The failures bucket has its own rule — **A2, which requires 4 calls** — precisely
because a company that fails stops reporting. First Republic (6 calls) and
Sunworks (10) have complete price data for every call they have and fail only
against a line never meant for them. This is the same mistake the original corpus
build made; it was flagged then and repeated in the gate.

**Two companies that were never selected.** Honeywell and UPS are
`S3.reserves.industrials` candidates in `selection_working.json`. They are frozen
in the manifest under the **S1** key with null call data, and flowed from there
into the split — inflating S1 to 22 against its real selected list of 20.

**A registered fix that never reached the file everything reads.**
`corpus-fix-1` established that the vendor files Alphabet under `GOOG`, recorded
it in `TICKER_ALIASES.json`, and registered it as `A5`. The manifest still shows
`GOOGL` with `n_calls_2020_2025: 0`. The split, the counts and every downstream
measurement read the manifest.

That third one is the one that matters beyond its own case. **A rule can be
registered, verified and still not be in effect.** This project has been bitten
by exactly this shape before, with `versions.js` disagreeing with the version
registry.

---

## 2. What this run is and is not

**Every change here moves the manifest toward what was already registered.** None
of it is a new selection decision:

- Restoring S1 to its registered `selected` list is a correction, not a re-pick.
- Writing A5's alias into the manifest applies a rule registered in September.
- Applying A2's threshold to the bucket A2 governs is applying the rule as
  written.

**No return is looked at anywhere in this run. Confirm that in the wrap-up.** If
any step starts to look like choosing which companies to keep on grounds other
than a registered rule, **stop and report it** rather than deciding.

---

## 3. Constraints

1. **ZERO Anthropic API calls. No vendor calls expected** — if one appears
   necessary, report why rather than spending it.
2. **Do not modify `analysis/data/price_cache.json`.** Use
   `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
3. **No spec edits** except the holdout-hash update in Step E.
4. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 4. Step A — correct the gate's threshold

Register `A9_price_gate_threshold_by_stratum` in `PREREGISTRATION_FIX.json`,
dated, before re-running anything.

**The rule:** the price-coverage gate inherits **whichever call-count threshold
already governs that company's stratum** — A1's 12 calls for ordinary strata,
**A2's 4 calls for the failures stratum**. A8 set a single 12-call line across
all strata; that was an error, and A9 corrects it.

**Justify it on coverage grounds only** — that A2 exists because failed companies
stop reporting, and a gate that ignores A2 re-imposes the survival requirement
A2 was written to remove. **No justification may reference any company's return
or which companies this recovers.**

Re-run the gate under A9 and report which companies change verdict.

---

## 5. Step B — correct the manifest

**B1 — S1 membership.** Compare `CORPUS_MANIFEST_V2.json`'s S1 members against
`selection_working.json` → `S1.selected`. Remove any company present in the
manifest but absent from the registered selection, and report each one with the
evidence. **Do not add anything** — if the manifest is missing a registered
member, report that separately rather than fixing it silently, since that is the
opposite error and may have a different cause.

**B2 — Alphabet.** Apply A5: set the manifest's entry to the working symbol
`GOOG` with its verified 24 calls (first 2020-02-03, last 2025-10-29) and the
availability verdict that follows from A1. Then **fetch and check its price
coverage**, which `corpus-fix-6` skipped because the manifest told it there were
no calls.

**B3 — the propagation audit.** This is the part with value beyond today.

For **every registered addendum A1 through A9**, check whether it is actually
reflected in `CORPUS_MANIFEST_V2.json` and in the split file, and report a
pass/fail line for each. Specifically: does each rule's effect appear in the
files that downstream code reads, or only in the pre-registration?

**Report every divergence. Fix only the two named above (B1, B2).** Anything
else found goes in the wrap-up as a numbered finding for the design session —
this run corrects the two known cases, not everything the audit turns up.

---

## 6. Step C — re-count

With A9 applied and the manifest corrected, report:

| | |
|---|---|
| Companies in the corpus | |
| Gradable under the price gate | |
| **Available for iteration** | |
| Excluded, and why | one line per company |

The available count excludes the existing-16 carve-out companies where they are
ungradable, as A8 requires.

---

## 7. Step D — the corrected threshold

Re-run `analysis/corpus_construction_stepC_independent_v3.py` at the corrected
count, all three brackets, 150 trials.

**Report the square-root estimates beside the simulated figure**, as every prior
run has. The simulation has read optimistic at every count so far — at 46
companies it returned 1–2 points where the square-root check gives closer to 3.
**Say which you trust and why.**

**Fill in:**

> After corrections, **____** companies are available for iteration, against
> **46** before this run and **53** claimed before the price gate. The paired
> threshold is **____ points** simulated, **____ points** by the square-root
> check. The registered minimum is 54 companies.
>
> The expansion therefore needs to add **____** companies to reach a 2-point
> threshold with margin.

That last number is what `corpus-fix-5`'s Job 2 needs, and is the most useful
thing this run produces.

---

## 8. Step E — re-freeze and re-lock

Write `CORPUS_MANIFEST_V4.json` as a new file, leaving earlier manifests intact.
Re-run the split with the same seed (`20201231`), re-lock the holdout, record old
and new sha256, and update the dated note in `PROMOTION_GATE.md` §10 — the only
spec edit this run makes.

---

## 9. Step F — the report

**Scope boundary: report and propose, do not decide.**

Short. Plain-language summary to the project instructions' language rules, then
Step D's filled-in sentence, the verdict changes under A9, the manifest
corrections with evidence, **the full A1–A9 propagation audit table**, the
corrected counts, and the new hashes.

**Limitations to state, not argue past:**

- The propagation audit checks whether a rule's effect appears in the manifest
  and split, not whether every line of downstream code honours it.
- The corpus remains selected, not scored.
- Coverage is measured against providers reachable from this environment; a
  company failing only because free sources purged its history is a purchasing
  decision, not a permanent exclusion.

---

## 10. Git — Code runs these, in this order

1. Confirm a clean tree and record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit**, before any result file exists.
3. Commit results — the A9 addendum, the corrected manifest, the audit output,
   the split, the threshold recheck.
4. Commit the wrap-up and the `PROMOTION_GATE.md` §10 update.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 11. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the propagation audit finding more divergences than
  the two known ones, or S1's manifest disagreeing with the registered selection
  in both directions rather than one.
- **Note anything contradicting this prompt's premises.** The repo outranks it.
