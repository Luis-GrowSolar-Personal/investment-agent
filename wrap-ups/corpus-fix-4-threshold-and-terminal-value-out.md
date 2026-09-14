# corpus-fix-4: an honest threshold, and grading the companies that went to zero — wrap-up

**Run ID:** `corpus-construction` (continuation). **Desk work only — zero
Anthropic API calls, zero vendor calls, zero new price fetches.** Branch
`sweep/db-corpus-baseline`.

Supersedes prompts 2 and 3, per this prompt's own instruction. Not run.

---

## Plain-language summary

Two jobs. **Job 1**: the last run's "how many companies do we need" answer (1
point) was built by literally copying the real 16 companies four times, so it
was really only measuring 16 companies' worth of variation and came out too
optimistic. This run rebuilds it so every synthetic company has its own,
independently drawn accuracy and its own independent coin-flips — no company
is a copy of another. The honest answer is **2 points at 54 companies**, not
1 — much closer to the two outside sanity checks (2.7–3.3 points) that flagged
the old number as wrong in the first place.

**Job 2**: four companies in the failures bucket (S4) went to zero and their
price history simply stops, so the existing measurement script skipped them.
Three of the four (Sunnova, Sunworks, First Republic) really did go to zero —
verified against SEC filings and the FDIC's own record, not taken on say-so —
so they're now graded as a −100% return, which lands them where you'd expect:
"lags the benchmark." The fourth (Romeo Power) is removed from the corpus
entirely, per your instruction, not graded.

**A genuine surprise, reported not hidden:** the price cache for those three
companies isn't just missing prices *after* they failed — it has **no price
data for them at all**, at any date. The terminal-value rule still works
without a new price fetch, because a stock going to exactly zero produces a
−100% return no matter what its price was on the call date — but this is a
bigger data gap than the prompt assumed, and it's flagged below.

---

## Step C — the honest threshold projection (the deliverable)

**Method.** From the real 16-company scored population (359 calls), each
company's own accuracy averages 40.2%, with a company-to-company spread
(standard deviation) of 16.5 percentage points. Independent synthetic
companies are built by drawing each one's own accuracy from that
distribution and its own i.i.d. per-call outcomes — not by duplicating any
real company. 150 trials (driver default `N_SYNTH_TRIALS`), same 15%
disagreement rate, same bootstrap machinery
(`analysis/scorecard_repair_driver.py`'s `step3_paired` / `step3_unpaired`,
unchanged).

New driver: `analysis/corpus_construction_stepC_independent_v3.py`. Output:
`analysis/data/corpus_v2/STEP_C_INDEPENDENT_THRESHOLD.json`.

### MDE (percentage points) vs n, paired / unpaired, three spread brackets

| n | observed (16.5pp spread) paired / unpaired | lower (8.2pp) paired / unpaired | higher (24.7pp) paired / unpaired | sqrt-published `24/√n` | sqrt-recheck `20/√n` |
|---|---|---|---|---|---|
| 16 | 9 / 13 | 5 / 11 | 9 / n/a* | 6.0 | 5.0 |
| 30 | 3 / 11 | 3 / 8 | 4 / 13 | 4.4 | 3.7 |
| **54** | **2 / 7** | **2 / 6** | **2 / 8** | 3.3 | 2.7 |
| 78 | 1 / 6 | 1 / 5 | 1 / 7 | 2.7 | 2.3 |
| 100 | 1 / 6 | 1 / 5 | 1 / 7 | 2.4 | 2.0 |
| 120 | 1 / 5 | 1 / 4 | 1 / 6 | 2.2 | 1.8 |
| 150 | 1 / 5 | 1 / 4 | 1 / 6 | 2.0 | 1.6 |
| 200 | 1 / 4 | 1 / 4 | 1 / 5 | 1.7 | 1.4 |

\* n=16, higher-spread, unpaired: no X in the 1–15pp sweep reached the 80%
detection threshold, so `minimum_detectable_improvement_pp` is `None`, not a
number — reported as-is, not papered over.

**Assumptions behind each bracket, stated not derived:**
- **observed** — spread as measured across the real 16 companies (16.5pp,
  sample stdev, n=16).
- **lower** (0.5× observed, 8.2pp) — today's 16 are 4 solar / 4 battery / 3
  semiconductor names that move together; their observed spread is inflated
  by that sector clustering. A halving is an illustrative, stated guess at
  what a more diversified corpus would show — not derived from any
  diversified sample, because none exists yet.
- **higher** (1.5× observed, 24.7pp) — a corpus deliberately including more
  variable/idiosyncratic companies than today's (more failures-stratum names,
  more small caps) would plausibly show more spread. Also a stated guess.

**Provenance:** `analysis/data/corpus_v2/STEP_C_INDEPENDENT_THRESHOLD.json` →
`spread_brackets.<bracket>.results_by_n.<n>.paired_mde_pp` /
`.unpaired_mde_pp`; `real_population_stats.spread_stdev_pp_observed` = 16.5;
`sqrt_estimates.published_baseline_24_over_sqrt_n` /
`.this_run_recheck_20_over_sqrt_n`.

### The filled-in sentence

> To detect a **2-point** improvement between two prompt versions compared on
> the same calls, the corpus needs **54 to 78 companies** available for
> iteration, which means **78 to 113 companies in total** with a third held
> out. Today's corpus has 53 available and 77 total (post-RMO-removal — see
> Step D).

Reasoning: paired MDE first reaches ≤2pp at n=54 across **all three** spread
brackets — but exactly at 2, no margin. n=78 clears it with margin (1pp in
every bracket). 54 is the bare-minimum answer; 78 is the comfortable one.
Scaling by the corpus's current available:total ratio (53:77 ≈ 0.69, a third
held out) gives a total-corpus range of 78–113.

### Square-root estimates: which to trust

At n=54, the simulated paired MDE (2pp, all three brackets) sits **below**
both outside checks — the published-baseline scaling (3.3pp) and this run's
own quick recheck (2.7pp) — by roughly 0.7–1.3pp. This is a real disagreement,
worth flagging, but it is **not** Step F's failure mode: Step F's flaw was
using literal company copies, collapsing 64 "companies" into 16 distinct
patterns and producing an implausible 1pp. This run's companies are
genuinely independent (own accuracy draw, own coin-flips), and the
below-sqrt gap is more plausibly explained by the sqrt formula being a crude
single-parameter approximation, while this simulation directly incorporates
the real (non-uniform) shape of the 16 companies' accuracy distribution and
the bootstrap/pairing mechanics of `step3_paired`. **Trust the recheck
(2.7pp) over the published baseline (3.3pp)** as the closer external check —
they're both built the same way, just at different X inputs (24 vs 20), and
the recheck used this run's own corpus scale. The simulated 2pp is close to,
not wildly divergent from, the recheck. Flagged as a finding, not corrected
by tuning parameters to match.

---

## Step A/B — terminal-value grading

Addendum `A6_terminal_value_grading` registered in
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` **before** any return was
computed, per the prompt's ordering requirement. States explicitly: this is
grading a known outcome (all five S4 companies were already frozen into the
corpus, before any return was measured), not a selection decision.

**Rule:** where a company's forward-return window has no real end-of-window
price because the equity was wiped out, terminal value = 0, so forward
return = exactly −100% (this holds for *any* positive entry price, so no
entry-price fetch was needed to apply it).

### The three verified companies

| Company | Outcome | Key dates | Source |
|---|---|---|---|
| Sunnova (NOVA) | Chapter 11, equity holders received **zero recovery** | Filed 2025-06-08; NYSE suspended trading 2025-06-09, delisted 2025-06-23; plan confirmed with 0% equity recovery, effective 2025-11-14 | SEC 8-K [nova-20250609.htm](https://www.sec.gov/Archives/edgar/data/1772695/000177269525000110/nova-20250609.htm); NYSE delisting notice [Form 25-NSE](https://www.sec.gov/Archives/edgar/data/1772695/000087666125000435/ruleprovisionnotice.htm); plan confirmation [ChemAnalyst](https://www.chemanalyst.com/NewsAndDeals/NewsDetails/sunnova-chapter-11-bankruptcy-plan-confirmed-paving-way-for-final-wind-down-40043) |
| Sunworks (SUNW) | Chapter 7 **liquidation** (not a going-concern reorg) | Filed 2024-02-05; Nasdaq delisting notice 2024-02-06, trading suspended by 2024-02-15 | SEC 8-K [form8-k.htm](https://www.sec.gov/Archives/edgar/data/1172631/000149315224004968/form8-k.htm) |
| First Republic (FRC) | FDIC receivership, assets/deposits sold to JPMorgan, **common equity received nothing** | Receivership 2023-05-01 | [FDIC.gov failed-bank record](https://www.fdic.gov/resources/resolutions/bank-failures/failed-bank-list/first-republic.html) |

None of the three was flagged as "acquired for value" — all three are
confirmed zero-recovery events for common shareholders, not acquisitions.
**Guard check:** scanned the full 77-company corpus (S1–S3, S5 — 73
companies, all large- or mid-cap names still independently trading) for any
other acquisition during 2020–2025; found none. The zero-terminal-value rule
is applied only to the three verified wipeouts.

**Finding not anticipated by the prompt, flagged explicitly:** the prompt's
framing ("their price series end when they fail") implies partial pre-failure
price data exists. It does not —
`analysis/data/corpus_v2/corpus_v2_price_cache.json` holds a fully **empty**
`{}` for all four of NOVA, SUNW, FRC, RMO: no price data at *any* date, not
just post-failure. Grading was still possible only because a terminal value
of exactly zero produces a forward return of exactly −100% independent of
the (missing, and under this run's zero-new-fetch constraint, unfetchable)
entry price. Sunworks also continued trading OTC post-delisting under
`SUNWQ` at near-zero (public quotes near $0.002 and below) rather than
literally $0 — graded as terminal zero because the residual value is
immaterial against the ±5pp dead band; stated, not hidden.

**S4 gradability:** 1 of 5 before this fix (WOLF only) → **4 of 4** after
this fix, once RMO is excluded (RMO was never a candidate for terminal-value
grading — it is removed from the corpus entirely, not graded).

New driver: `analysis/corpus_construction_outcomes_v3_terminal.py`. Output:
`analysis/data/corpus_v2/outcome_balance_v3_terminal.json`.

### Re-graded outcome balance

| Figure | beats | lags | moves-with | n |
|---|---|---|---|---|
| **This run, ex-S5** | 42.4% | 40.7% | 16.9% | 59 |
| **This run, ex-S5 and ex-S4** | 45.5% | 36.4% | 18.2% | 55 |
| **This run, S4 only** | 0.0% | 100.0% | 0.0% | 4 |
| v2 ex-S5 (prior) | 44.6% | 37.5% | 17.9% | 56 |
| v1 ex-S5 (prior) | 44.4% | 35.2% | 20.4% | 54 |
| existing corpus (prior) | 46.2% | 42.1% | 11.7% | — |

Provenance: `analysis/data/corpus_v2/outcome_balance_v3_terminal.json` →
`distribution_excluding_S5_only.pct` / `distribution_excluding_S5_and_S4_per_A4.pct`
/ `s4_only.pct`. Ex-S4 figures are unchanged from v2 (45.5/36.4/18.2, n=55)
because A6 only affects S4 companies. The ex-S5-only figure shifts from
44.6/37.5/17.9 (n=56) to 42.4/40.7/16.9 (n=59): three more companies are now
gradable, all three grade as "lags" (a wipeout cannot grade any other way
under the dead band), which pulls the "lags" share up. **Not re-picked** on
this result, per the prompt.

---

## Step D — RMO removal and re-lock

RMO removed from `CORPUS_MANIFEST_V2.json`'s S4 stratum entirely (Luis's
explicit instruction; no verification required). Corpus: 78 → **77**
companies; S4: 5 → 4 (WOLF, NOVA, FRC, SUNW).

Split re-run with the **same seed** (`20201231`), same method
(`analysis/corpus_construction_split_v3_rmo_removed.py`, a same-logic copy of
`corpus_construction_split_v2.py`), over the corrected 77-company manifest.
Output: `analysis/data/corpus_v2/SPLIT_V3_RMO_REMOVED.json`.

- **Old holdout** (78 companies, RMO included): 24 companies, sha256
  `d4e40fe0b5f1234b34c3fe7ccd5e704afff4e5aaf4e17dbc0e53c2223e412a23`
- **New holdout** (77 companies, RMO removed): 24 companies, sha256
  `5ab7ef18c3e3f22160f6b6ae60a82c99638b70c26b1c17d6477e6b5615795c84`
- New split: train 28, tune 25, holdout 24 (train+tune = 53 available, up
  one company net in "tune" vs "train" balance from re-shuffling S4's
  reduced list; SUNW moved from tune to holdout under the new shuffle).

**Justification for re-locking (written, as required):** this is safe
because nothing in either corpus (78- or 77-company) has ever been scored,
and the holdout has never been used for any measurement — re-locking after a
membership change costs nothing. Recorded both hashes for audit.

`docs/architecture/PROMOTION_GATE.md` §10 updated in place with the new
hash, old hash kept visible as a superseded value — the only spec edit this
run makes.

---

## Limitations (stated, not argued past)

- This is a **simulation**, not a measurement of the actual (still-unscored)
  77-company corpus.
- The between-company spread is estimated from only **16 correlated
  companies** — the projection's weakest input; the "lower"/"higher" brackets
  are stated illustrative multipliers (0.5×/1.5×), not derived from any
  independent diversified sample.
- The 15% modeled disagreement rate between prompt versions is an assumption
  carried over unchanged from `scorecard_repair_driver.py`.
- The failures stratum (S4) is defined by its outcome and by construction
  over-represents failures relative to the general population.
- Terminal values are sourced from public record (SEC filings, FDIC record),
  not from a price feed — and for these three tickers, no price-feed data
  exists at all, at any date, in `corpus_v2_price_cache.json` (see the
  finding above).

## What was NOT done / left for the design session

- The corpus (77 companies) has not been scored. No scoring is commissioned
  by this run.
- No independent verification of a diversified-corpus spread figure exists;
  the "lower" bracket is a stated guess, not a measurement.
- SUNW's continued OTC trading at near-zero (not literally $0) is graded as
  terminal zero for simplicity; a stricter treatment would carry its actual
  residual quoted value, which would not change the "lags" bucket outcome
  given the ±5pp dead band.

## Git sequence run

1. Clean tree confirmed before starting (`git status` showed only the
   untracked prompt file). `git_dirty: false` recorded.
2. Driver commit (first, before any result file): `corpus_construction_stepC_independent_v3.py`,
   `corpus_construction_outcomes_v3_terminal.py`, `corpus_construction_split_v3_rmo_removed.py`.
3. Results commit: `PREREGISTRATION_FIX.json` (A6), `CORPUS_MANIFEST_V2.json`
   (RMO removed), `STEP_C_INDEPENDENT_THRESHOLD.json`,
   `outcome_balance_v3_terminal.json`, `SPLIT_V3_RMO_REMOVED.json`,
   `analysis/data/run_state/corpus-construction/progress.json`.
4. Wrap-up + spec-hash commit: this file, `docs/architecture/PROMOTION_GATE.md`.
5. Pushed once to `origin sweep/db-corpus-baseline`.

## Follow-up commands

```bash
# Re-inspect the Step C projection in full
python3 -c "import json; print(json.dumps(json.load(open('analysis/data/corpus_v2/STEP_C_INDEPENDENT_THRESHOLD.json')), indent=2))" | less

# Re-inspect the re-graded outcome balance
python3 -c "import json; print(json.dumps(json.load(open('analysis/data/corpus_v2/outcome_balance_v3_terminal.json')), indent=2))" | less

# Confirm the new split/holdout
python3 -c "import json; d=json.load(open('analysis/data/corpus_v2/SPLIT_V3_RMO_REMOVED.json')); print(d['holdout_sha256'], d['counts'])"
```
