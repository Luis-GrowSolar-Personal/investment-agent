# Corpus fix 2 of 3 — outcome balance, split, holdout lock

**Run ID:** `corpus-construction` — continuation. **This run does two things.**
**Cost:** **$0 Anthropic API. No transcript scored. No vendor calls needed.**
**Branch:** `sweep/db-corpus-baseline`. No merge, no push.
**Wrap-up:** `wrap-ups/corpus-fix-2-balance-and-split-out.md` — **short**. No
defined-terms table required.

**Read first:** `wrap-ups/corpus-fix-1-ticker-aliases-out.md` and the newest
corpus manifest it names (V3 if membership changed, otherwise
`CORPUS_MANIFEST_V2.json`). **Use that manifest and no other.**

**Drivers already exist** — `analysis/corpus_construction_fix_driver.py`'s Step D
work (commit `a131a6b`) and Step E work (commit `923a261`). Reuse them rather
than rewriting.

---

## 1. Step D — outcome balance, reported only

Re-measure the three-way outcome split on the current frozen corpus, same method
as the first pass, from `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
**Never open `analysis/data/price_cache.json` for writing.**

Report it **twice — including the failures stratum (S4) and excluding it** — per
`PREREGISTRATION_FIX.json` → A4, and state S4's share of companies and of calls.

Report beside the two prior figures: the first pass's 44.4% / 35.2% / 20.4% and
the existing corpus's 46.2% / 42.1% / 11.7%.

**Do not re-pick on the result.** The only permitted response to a balance judged
poor is a new stratum under its own dated pre-registration.

Carry forward the known weakness: this is one reading per company, not per call.
**If the full per-call date list is already in the manifest at no extra vendor
cost, compute the per-call version instead and say so.** Do not spend vendor
calls to improve this figure.

---

## 2. Step E — the split, and lock the holdout

Split **by company, never by call.** Train / tune / holdout, roughly equal
thirds, stratified so each split carries a proportional share of every stratum
including S4. Seed `20201231`.

**Lock the holdout:**

- record its company list and sha256 in the manifest and in `progress.json`;
- add one note to `PROMOTION_GATE.md` §10 — the only spec edit this run is
  permitted — stating that the holdout is not to be scored during prompt
  iteration, and that any run touching it must say so prominently in its
  wrap-up.

Report each split's company count, call count, and stratum composition.

---

## 3. Constraints

1. **ZERO Anthropic API calls.** Nothing scored.
2. **No vendor calls should be needed.** If one appears necessary, report why
   rather than spending it.
3. **No spec edits except the single `PROMOTION_GATE.md` §10 holdout note.**
4. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 4. Report

Short. Plain-language summary to the project instructions' language rules, then
the balance table both ways, the three splits with their counts and composition,
and the holdout's hash.

Do not attempt the detection-threshold projection or the cost estimate. That is
prompt 3.

---

## 5. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record the
  seed.
- Driver committed before any manifest, as its own commit. Run-specific files
  only; no `git add .`.
- **A diagnostic that contradicts this prompt is a finding.**
