# Corpus fix 4 — an honest threshold, and grading the companies that went to zero

**Run ID:** `corpus-construction` — continuation. **Desk work only.**
**Cost:** **$0 Anthropic API. No transcript scored. No vendor calls. No price
fetches beyond what is already cached.**
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/corpus-fix-4-threshold-and-terminal-value-out.md` —
**short**. No defined-terms table required.

**Read first:** `wrap-ups/corpus-construction-fix-out.md` Steps D–G, and
`analysis/corpus_construction_stepF_v2.py`.

**Supersedes prompts 2 and 3** (`corpus-fix-2-balance-and-split.md`,
`corpus-fix-3-threshold-and-cost.md`). Those were written before the previous
run completed Steps D–G on its own. Do not run them.

---

## 1. Two jobs

**Job 1 — the threshold projection is not trustworthy and must be redone.**
Step F built its 64 "companies" by replicating the real 16-ticker population
four times. Copies of a company carry that company's exact per-call outcome
sequence, so 64 synthetic blocks contained only 16 distinct patterns. That
understates the wobble, which is why it returned **1 point** where two
independent estimates say roughly **3**:

```
from the published 6 points at 16 companies:   MDE ≈ 24 / sqrt(n)  → 3.3 at n=54
from this run's own 5-point recheck:           MDE ≈ 20 / sqrt(n)  → 2.7 at n=54
```

**Job 2 — four companies in the failures stratum cannot currently be graded**,
because their price series end when they fail. Their outcomes are nonetheless
known, and a wipeout is an unambiguous result.

---

## 2. Constraints

1. **ZERO Anthropic API calls. Zero vendor calls.** If a step appears to need
   either, **stop and report it**.
2. **Do not modify `analysis/data/price_cache.json`.** Corpus work uses
   `analysis/data/corpus_v2/corpus_v2_price_cache.json`.
3. **No spec edits** except the holdout-hash update in Step D.
4. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step A — the terminal-value grading rule

Register as a **dated addendum** to
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` under
`A6_terminal_value_grading`, **before applying it**.

**This is grading, not selection.** The companies were frozen in Step C before
any return was measured. Deciding how to score a known outcome is not choosing
which companies to include. State that distinction in the addendum.

**The rule.** Use actual prices wherever they exist. Where a call's 182-day
forward window extends past the company's **last trading day**, use its
**terminal value** for the end of the window. Where the equity was wiped out,
terminal value is **zero**, so the forward return is −100% and the outcome
grades as "lags the benchmark" under the existing ±5-point dead band.

**The companies, and what must be verified.** Luis supplied these outcomes.
**Confirm each against public record — SEC filings, exchange delisting notices,
or company press releases — and cite the source. Do not take them on
assertion**, including from this prompt:

| Company | Asserted outcome | To verify |
|---|---|---|
| Sunnova (NOVA) | Bankruptcy ~June 2025; traded near $0.30 for months, then delisted; never rescued or acquired | filing date, last trading day, whether equity holders recovered anything |
| Sunworks (SUNW) | Filed ~February 2024; not acquired, did not survive as an entity | filing date, last trading day, terminal value |
| First Republic (FRC) | Assets acquired by JPMorgan; **shareholders wiped out** | receivership date, last trading day, confirmation common equity recovered nothing |
| Romeo Power (RMO) | — | **Remove from the corpus entirely.** Luis's instruction; no verification needed. |

**A guard against over-applying this.** Terminal value is zero **only** where
the equity was actually wiped out. A company acquired for cash or stock has a
positive terminal value — the deal consideration — not zero. **Check whether any
other corpus company was acquired during the window, and if so flag it rather
than grading it at zero.** Getting this backwards would manufacture losses that
did not happen.

Record per company: terminal date, terminal value, source URL, and which calls
in that company's history are affected — i.e. those whose forward window extends
past the terminal date. Calls whose window closes while the stock still traded
are graded normally from real prices.

---

## 4. Step B — re-grade and re-report the outcome balance

Apply A6. Re-run the outcome balance, and report it against the three prior
figures (v2 ex-S5 44.6/37.5/17.9; v1 ex-S5 44.4/35.2/20.4; existing corpus
46.2/42.1/11.7), **both including and excluding the failures stratum**, per A4.

Report how many failures-stratum companies are now gradable — it was 1 of 5.

**Do not re-pick companies on this result.**

---

## 5. Step C — the honest threshold projection *(the deliverable)*

Rebuild the projection so that synthetic companies are **independent**, not
copies.

**Method.** From the real 16-company scored population, estimate two quantities:
the **average per-company accuracy**, and the **spread of accuracy across
companies**. Then simulate a corpus of n independent companies by drawing each
company's own accuracy from that distribution and its per-call outcomes from
that accuracy, rather than duplicating whole companies. Run the same paired and
unpaired detection simulation on the result, at the driver's **default 150
trials**, not the reduced 60.

**Report MDE against n** for n = 16, 30, 54, 78, 100, 120, 150, 200, paired and
unpaired.

**Bracket the between-company spread, because it drives everything.** Report
three cases:

- **observed** — the spread measured across the real 16;
- **lower** — a diversified corpus. The current 16 are four solar, four battery
  and three semiconductor names that move together, so they are not 16
  independent blocks and their observed spread partly reflects sector
  clustering. A spread-out corpus should do better;
- **higher** — a corpus with more variable companies than today's.

**State the assumption behind each case explicitly.** The bracket is the
finding; a single number would be false precision.

**Then answer the question directly:**

> To detect a **2-point** improvement between two prompt versions compared on
> the same calls, the corpus needs **____ to ____ companies** available for
> iteration, which means **____ to ____ companies in total** with a third held
> out. Today's corpus has 54 available and 78 total.

**Report the square-root estimates beside every simulated figure.** Where they
disagree by more than a point, say which you trust and why. *A simulation that
lands far below the square-root estimate is suspect — that was Step F's failure
mode.*

---

## 6. Step D — apply Romeo's removal and re-lock

Removing RMO changes corpus membership from 78 to 77, and RMO currently sits in
the **holdout**. Re-run the split with the same seed (`20201231`) over the
corrected corpus, re-lock the holdout, and record **both the old and new
sha256** so the change is auditable.

**This is safe and must be justified in writing:** nothing has been scored, the
holdout has never been used, so re-locking costs nothing. Update the dated note
in `PROMOTION_GATE.md` §10 with the new hash — the only spec edit this run makes.

---

## 7. Step E — the report

**Scope boundary: report and propose, do not decide.** No scoring is
commissioned.

Short. Plain-language summary to the project instructions' language rules, then
Step C's filled-in sentence and its bracket table, then the terminal-value rule
with its sources, the re-graded balance, and the new split hashes.

**Limitations to state, not argue past:**

- The projection is a simulation, not a measurement of the new corpus, which
  remains unscored.
- The between-company spread is estimated from 16 correlated companies and is
  the projection's weakest input.
- The assumed disagreement rate between two prompt versions is modeled.
- The failures stratum is defined by an outcome and over-represents failures.
- Terminal values are sourced from public record, not from a price feed.

---

## 8. Git — Code runs these, in this order

Do not hand Luis a command sequence; run them here.

1. **Before anything:** confirm a clean tree and record `git_dirty: false`. Hard
   stop if it cannot be recorded false.
2. **Commit the driver first, as its own commit**, before any result file
   exists.
3. **Commit results** — the pre-registration addendum, the re-graded balance,
   the projection output, the corrected manifest and split.
4. **Commit the wrap-up** and the `PROMOTION_GATE.md` §10 hash update.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 9. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record every
  seed.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the independent-block simulation disagreeing with
  both square-root estimates, or a failures-stratum company turning out to have
  been acquired for value rather than wiped out.
- **Note anything contradicting this prompt's premises.** The repo and the
  public record outrank it.
