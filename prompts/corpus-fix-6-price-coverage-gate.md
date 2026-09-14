# Corpus fix 6 — price coverage as an inclusion gate

**Run ID:** `corpus-construction` — continuation. **One job.**
**Cost:** **$0 Anthropic API. No transcript scored. No vendor calls.**
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/corpus-fix-6-price-coverage-gate-out.md` — **short**. No
defined-terms table required.

**Read first:** `wrap-ups/corpus-fix-5-expand-and-prices-out.md` (the WOLF and
NOVA findings), `analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (rules
A1–A7), `analysis/data/corpus_v2/TICKER_ALIASES.json`, and
`analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json`.

**This run comes before `corpus-fix-5`'s Job 2 (the expansion), which stays
pending.** There is no point buying 30 more companies until we know how many of
the 77 can actually be graded.

---

## 1. The one job, and why it is a gate

Corpus construction verified that **earnings calls** exist for every company. It
never checked that **prices** exist. Those are different questions, and the gap
between them has now bitten twice:

- **Sunnova** — the price provider appears to have purged its entire history,
  not just the part after it delisted.
- **Wolfspeed** — it restructured through Chapter 11, and history now starts on
  2025-09-29 when the new equity began trading. **23 of its 28 calls have no
  price at all**, and because it restructured rather than going to zero, the
  terminal-value rule does not rescue them.

Wolfspeed passed every existing check. It is in the corpus, in the split, and
counted toward the threshold — and it is mostly ungradable.

**So price coverage becomes an inclusion rule, checked like any other.** A
company that cannot be graded contributes nothing to the ruler while inflating
the company count the threshold is computed from. That is the specific harm: not
a missing number, but an **overstated precision estimate**.

---

## 2. Constraints

1. **ZERO Anthropic API calls. Zero vendor calls.** This run needs neither.
2. **Do not modify `analysis/data/price_cache.json`.** Everything goes in
   `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
3. **No eligibility rule changes** other than the one registered in Step A.
4. **No spec edits** except the holdout-hash update in Step E.
5. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step A — register the gate first

Write `A8_price_coverage_gate` into `PREREGISTRATION_FIX.json`, dated, **before
examining any company**.

**This is a coverage rule, not an outcome rule.** The outcome balance is already
known, so the justification must rest **only** on the two failures above and on
the fact that call availability was never a proxy for price availability. **No
justification may reference any company's return**, or which companies would
fail. State that in the addendum.

**Definition — a call is gradable when either:**

- **real prices exist** for the company and for SPY on the call date and at the
  end of its 182-day forward window; **or**
- **the terminal-value rule (A6) applies** — the company's equity was verified
  wiped out and the window closes after that event.

**The gate:** a company passes with **at least 12 gradable calls**, matching
A1's existing 12-call threshold so the two rules agree. Register that number and
its reasoning.

**Order of resolution before failing anything** — identity first, coverage
second:

1. the company's primary ticker;
2. any symbol already in `TICKER_ALIASES.json`;
3. post-event forms — the `Q` suffix, five-letter delisted variants, and a
   pre-merger predecessor ticker where one exists (Wolfspeed traded as `CREE`
   before 2021).

**Do not fail a company for an identity problem.** Record every symbol tried and
what it returned, and add any newly working symbol to `TICKER_ALIASES.json`.

---

## 4. Step B — sweep all 77 companies

For every company in the corpus, report:

| Column | Meaning |
|---|---|
| calls in window | total 2020–2025 |
| gradable, real price | both ends of the window covered |
| gradable, terminal rule | window closes after a verified wipeout |
| ungradable | neither |
| first / last price date | the span actually available |
| verdict | pass or fail against the 12-call gate |

**Check SPY separately and first.** Every grading comparison needs it. If SPY's
coverage has a hole, that is a finding that affects every company and the run
should report it before anything else.

**Report the distribution, not just the failures.** How many companies have
full coverage, how many are partial, how many sit within two calls of the
12-call line. **If many cluster near the line, the gate is brittle and that is a
finding** — do not tune the threshold to move them.

**Name the cause of each gap where determinable** — delisting, bankruptcy,
restructuring, ticker change, or simply absent — so a future session knows
whether a gap is fixable.

---

## 5. Step C — apply the gate

Drop failing companies and replace from the reserve lists where any remain,
mechanically, exactly as the availability rule does. Report every drop and every
replacement.

**Two carve-outs, both to be reported rather than silently applied:**

- **The existing 16 (S5)** are exempt from drop rules by design, so they stay.
  **But they must not count toward the number of companies available for
  iteration** if they are ungradable — that number feeds the threshold, and
  counting an ungradable company inflates it. Report the S5 companies' coverage
  and state which are excluded from the count.
- **A company that fails only because of the terminal-value edge** — enough
  calls, but they sit after a wipeout — is already handled by A6 and passes.
  Confirm the arithmetic rather than assuming.

**If dropping companies leaves a stratum below target, report the shortfall.**
Do not lower the gate to close it.

---

## 6. Step D — the number that matters

Re-run `analysis/corpus_construction_stepC_independent_v3.py` at the
**corrected** count of gradable companies available for iteration, all three
spread brackets, 150 trials.

**Fill in and report plainly:**

> Of 77 companies, **____** are gradable under the price-coverage gate. That
> leaves **____** available for iteration against **53** counted before this
> check. The paired threshold is **____ points**, against the **2 points**
> previously claimed at 54 companies.

**If the corrected count drops the corpus below the 54-company minimum, say so
prominently.** That would mean the expansion is not optional margin but a
requirement, and it changes how many companies `corpus-fix-5`'s Job 2 needs to
add. Report that revised target.

---

## 7. Step E — re-freeze and re-lock

Only if membership changed: write `CORPUS_MANIFEST_V4.json` as a new file,
leaving V2 and V3 intact. Re-run the split with the same seed (`20201231`),
re-lock the holdout, record old and new sha256, and update the dated note in
`PROMOTION_GATE.md` §10 — the only spec edit this run makes.

**No return is looked at anywhere in this run.** Confirm that in the wrap-up.

---

## 8. Step F — the report

**Scope boundary: report and propose, do not decide.**

Short. Plain-language summary to the project instructions' language rules, then
the Step D sentence, the per-company coverage table, the cause of each gap, every
drop and replacement, and the new hashes.

**One recommendation to close on:** given the corrected count, how many
companies does the expansion now need to add, and does anything else block
commissioning the scoring run?

**Limitations to state, not argue past:**

- Coverage is measured against the providers reachable from this environment.
  A paid provider might have history that a free one has purged — **if a company
  fails only because free sources lack history, say so**, since that is a
  purchasing decision rather than a permanent exclusion.
- The gate uses the same 12-call threshold as call availability; that number was
  chosen for calls and is inherited here, not independently justified.
- The corpus remains selected, not scored.

---

## 9. Git — Code runs these, in this order

1. Confirm a clean tree and record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit**, before any result file exists.
3. Commit results — the A8 addendum, the coverage sweep output, any alias
   additions, the new manifest and split.
4. Commit the wrap-up and the `PROMOTION_GATE.md` §10 update.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 10. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: far more companies failing than the two known cases
  suggest, or a hole in SPY's own coverage.
- **Note anything contradicting this prompt's premises.** The repo and the
  price providers outrank it.
