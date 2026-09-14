# Corpus fix 8 — expand to about 150 companies

**Run ID:** `corpus-construction` — continuation. **Supersedes `corpus-fix-5`'s
Job 2**, which stays unrun; its +30 target was computed from a simulation the
project has since decided to distrust.
**Cost:** **$0 Anthropic API. No transcript scored.** Vendor metadata and price
history only.
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/corpus-fix-8-expand-to-150-out.md`

**Read first:** `wrap-ups/corpus-fix-7-manifest-corrections-out.md`,
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (A1–A9),
`analysis/data/corpus_v2/CORPUS_MANIFEST_V4.json`, and
`analysis/data/corpus_v2/selection_working.json`.

---

## 1. The target, and the arithmetic behind it

The corpus is **75 companies, 48 available for iteration**. The paired threshold
is about **3 points** — agreed between the simulation and the square-root check,
which is why it is now the planning figure.

Precision improves with the square root of the companies available:

```
20 / sqrt(n available) = threshold

 48 available → 2.9 points   (today)
 64 available → 2.5 points
100 available → 2.0 points
```

Available runs about two-thirds of total, since a third is held out. So a
genuine **2-point threshold needs roughly 150 companies in total.**

**Target: 150 companies in the frozen corpus**, meaning about **75 new ones**.
Expect attrition — earlier rounds lost roughly 15% to the call-availability rule
and a few more to price coverage — so **select about 90 candidates** to land 75.

Report the actual attrition rate; if it runs far above 15%, say so rather than
quietly selecting more.

---

## 2. What is different this time

**Price coverage is a gate at selection, not an afterthought.** A9's
per-stratum price rule runs on every candidate **before** the freeze. The
original build verified calls and not prices, and it cost two rounds to find out.

**Every rule this run registers must propagate.** Three registered rules turned
out never to have reached the manifest downstream code reads. **Verdicts go into
the manifest itself, not only into a side file**, and the wrap-up carries a
propagation line for each new rule. This is now standing practice.

---

## 3. Constraints

1. **ZERO Anthropic API calls.** Nothing scored.
2. **Vendor metadata only** — call dates and counts, no transcript text.
   **Respect 20 calls per minute**; throttle and back off. **Do not use the
   vendor's SDK**, which retries aggressively. There is no monthly quota.
3. **Do not modify `analysis/data/price_cache.json`.** Use
   `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
4. **No changes to A1–A9.** They apply to new candidates exactly as registered.
5. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 4. Step −1 — resume protocol

State continues in `analysis/data/run_state/corpus-construction/`. Record this
prompt's sha256 as `prompt_sha256_fix8`. Append to `cells.jsonl` and
`findings.md`; never rewrite.

**Stopping is permitted only after Step D (the freeze).** Steps A–D are the work;
E is quick. If budget genuinely runs out mid-sweep, the candidate list and
whatever availability results exist must be committed so the next session
resumes rather than re-selects.

---

## 5. Step A — register the expansion

Write `A10_expansion_to_150` into `PREREGISTRATION_FIX.json`, dated, **before
examining any candidate**. It states the quotas below, the selection rule for
each, the seed, and that A1–A9 are unchanged.

**Justify the target on precision grounds only** — the square-root arithmetic
above. **No justification may reference any company's return, or which companies
would be added.**

### Quotas — weighted toward independence

The ruler gains most from companies uncorrelated with each other. The corpus is
already heavy in solar, storage and semiconductors.

| Stratum | Add (candidates) | Rule |
|---|---|---|
| **S3 — out of scope** | **50** | Stratified by **sector × size band**. At most **6 per sector** — raised from 4, because 11 sectors at 4 cannot supply 50; state that as the reason. Random within each cell, fixed seed. Report existing sector counts first and prefer cells currently thin or empty. |
| **S1 — large cap, point-in-time** | **25** | Ranks **41–80** by market cap on the same dated 2020-12-31 list. Deterministic. |
| **S2 — in scope** | **12** | Within `DOMAIN.md`, stratified by size band, random within band, fixed seed. |
| **S4 — failures** | attempt | Domain-drawn candidates public by 2020-12-31 that later failed. **Report the shortfall rather than forcing it**; do not relax A2 and do not admit an out-of-domain company. |

**Carry forward the open question, do not decide it:** many in-scope failures
listed by SPAC during 2021 and fail the 2020 test, though a 2021 listing still
yields four years of calls. **List those candidates with their call counts and do
not add them.** That decision is Luis's.

---

## 6. Step B — select

Apply the rules. Record every candidate with its stratum, the cell it came from,
and its point-in-time eligibility evidence. Build reserve lists per stratum, since
drops are expected.

---

## 7. Step C — call availability

Test every candidate under **A1** (240-day gap rule) or **A2** for the failures
stratum. Apply the drop-and-replace rule mechanically; report every drop, its
reason, and its replacement.

**Resolve identity before failing anything** — primary ticker, then
`TICKER_ALIASES.json`, then share-class variants and post-event forms. Alphabet
cost two rounds to find because nobody checked `GOOG`. Add any newly working
symbol to the alias file.

Report vendor calls consumed.

---

## 8. Step D — price coverage, then freeze

Run the **A9** price-coverage gate on every surviving candidate: each needs
enough gradable calls under its own stratum's floor, where a call is gradable
with real prices at both ends of its 182-day window, or under A6's terminal-value
rule. **Check SPY's coverage spans the full window first** — it underpins every
comparison.

Drop failures, replace from reserves, report each.

**Then freeze.** Write `CORPUS_MANIFEST_V5.json` as a new file, leaving earlier
manifests intact. **Write every A1/A2/A9 verdict into the manifest itself**, not
a side file. Record its sha256.

**No return is looked at before this freeze. Confirm that in the wrap-up.**

Report the counts: companies, gradable, **available for iteration**, and the
attrition rate at each gate.

---

## 9. Step E — split, lock, and the threshold

Re-run the split with the same seed (`20201231`), by company, stratified across
every stratum. Re-lock the holdout, record old and new sha256, and update the
dated note in `PROMOTION_GATE.md` §10 — the only spec edit this run makes.

Re-run `analysis/corpus_construction_stepC_independent_v3.py` at the new
available count, all three brackets, 150 trials.

**Report the square-root estimate beside the simulated figure and say which you
trust.** The two agreed at n=48 (3 points simulated, 2.89 by square root) after
disagreeing sharply at n=46; the square-root check is the stable anchor.

**Fill in:**

> The corpus is now **____ companies**, **____** available for iteration. The
> paired threshold is **____ points** simulated, **____ points** by the
> square-root check, against **3 points** before this run. Scoring it would cost
> roughly **$____**.

---

## 10. Step F — the report

**Scope boundary: report and propose, do not decide.** No scoring is
commissioned.

Short. Plain-language summary to the project instructions' language rules, then
Step E's filled-in sentence, the per-stratum counts with attrition at each gate,
every drop and replacement, the propagation lines for A10, the new hashes, and
the SPAC-era failure candidates listed but not added.

**Limitations to state, not argue past:**

- The corpus is selected, not scored.
- The threshold is a simulation plus an arithmetic check, not a measurement.
- Coverage is measured against providers reachable from this environment; a
  company failing only because free sources purged its history is a purchasing
  decision, not a permanent exclusion.
- The existing 16 remain hindsight-selected and excluded from ruler headlines.
- The failures stratum is defined by an outcome and over-represents failures.

---

## 11. Git — Code runs these, in this order

1. Confirm a clean tree and record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit**, before any result file exists.
3. Commit results — A10, the candidate list, availability and coverage sweeps,
   alias additions, the new manifest and split.
4. Commit the wrap-up and the `PROMOTION_GATE.md` §10 update.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 12. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed and the vendor calls consumed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: attrition well above 15%, the sector quotas running
  out of eligible companies, or the failures stratum again yielding nothing.
- **Note anything contradicting this prompt's premises.** The repo, the vendor
  and the public record outrank it.
