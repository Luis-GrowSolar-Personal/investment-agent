# The disaster-profile test — are the catastrophes identifiable before they happen?

**Run ID:** `disaster-profile-test`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/disaster-profile-test-out.md`
**Cost: $0. NO MODEL CALLS.** Everything is on disk. **If you are about to
call the Anthropic API, stop and report.**

**Read first:** `wrap-ups/q2-bearish-strength-separation-out.md` **in full** —
this run is its close cousin and must not repeat its mistakes;
`wrap-ups/R4b-tradeable-entry-out.md` (the tradeable-entry rule);
`docs/handoffs/2026-09-19-state-of-play.md` §0 and §2;
`docs/architecture/PROMPT_ARCHITECTURE.md` §2.3.

---

## 1. The question, and why it is not a repeat of the ranking test

Measured from a tradeable entry, the analyst's bearish calls lag the S&P by
about 4 points more than average over six months. **That average is almost
entirely the tail.** The worst quarter of flagged calls — 46 of 187 —
averaged **−61.5%** against the index. The rest are only mildly bad.

So the value of a bearish call is not "this stock will drift down a bit." It
is "one flagged call in four is a catastrophe." **The question is whether
those are distinguishable, at the time of the call, from the ordinary ones.**

**Why this is a different question from the earlier ranking test.** That test
asked whether the analyst's own fields predict a *hit* — a binary, whether the
stock lagged by more than 5%. Six fields were tried; five reversed between the
two halves of the data and the sixth could not be told from zero. **This run
asks a different question of the same fields: do they predict the
*magnitude*, specifically the tail?** A field can be useless at sorting a −6%
outcome from a −4% one and still flag the −60% ones. Nothing in the earlier
result rules that out.

**It also may well fail, and for a reason already visible.** See §2.

## 2. The concentration problem — read before designing anything

The 46 worst calls are **not** 46 independent events:

| | |
|---|---|
| distinct companies | **21** |
| PARA / SUNW / SEDG alone | **19 of 46** |
| calls dated 2023–2025 | **40 of 46** |
| split | 33 train, 13 tune |

Several are outright failures — a bank that was seized, a solar name that
collapsed. **A "profile of a disaster" fitted to 46 calls from 21 companies,
three of which supply 40% of them, will mostly be a profile of those three
companies.** Any finding that does not survive being measured per company
rather than per call is not a finding.

**Therefore, and this is binding:** every figure in this run is reported **per
company as well as per call**, and the headline classification test is run
with **whole companies held out**, never single calls.

## 3. Ground rules

1. **No model calls, no API spend, no DB writes, no cache refresh.**
2. **Do not modify `analysis/analyst_direct_scorer.py`.** Import from it.
3. **Holdout untouched.** Train and tune only; assert it.
4. **Price cache `analysis/data/corpus_v2/scorer_price_cache_v1.json`.** Never
   `analysis/data/price_cache.json`.
5. **Resolve symbols through `TICKER_ALIASES.json`.** Exclude `WOLF` and
   `SPWR` entirely. `MAXN` resolves to nothing, expected.
6. **Tradeable entry: the close of the first trading day STRICTLY AFTER the
   call date**, for every return in this run.
7. **`python3`, zsh, macOS Tahoe.** No `--break-system-packages`. No `apt`.
8. **A result that contradicts an expectation here is a finding.**

## 4. Steps −1 and 0

State in `analysis/data/run_state/disaster-profile-test/`. `progress.json`
first. `cells.jsonl` per feature × split. `findings.md` append-only, carrying
§6's pre-registration **before any contingency table is computed.** Clean
tree, hard stop on `git_dirty`. Driver
`analysis/disaster_profile_driver.py` committed as its own commit before
output. No version guard — record that it was skipped and why.

## 5. The work

### 5a. Define the target, two ways, and report both

Take the 187 bearish calls with a graded 182-day tradeable return.

- **Target 1 — worst quartile.** The 46 with the lowest return. Simple, and
  the one the earlier finding used.
- **Target 2 — a fixed threshold.** Lagged the S&P by more than **25%**.
  Report the count. A fixed line does not move when the sample does, which
  makes it the more honest target if the two disagree.

**If the two targets disagree on a feature, say so and trust neither.**

### 5b. The features, ranked and committed before looking

All are known at the time of the call. Source for the analyst's own fields:
`analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`.

| # | feature | why it might separate |
|---|---|---|
| F1 | corpus stratum (S1–S5) | S4 is the failures stratum by construction; if the disasters are simply S4, that is the answer and it is not a prompt finding |
| F2 | `thesisHealth` (Weakening / Intact / Broken) | the analyst's own severity label |
| F3 | `stumbleType` (Structural / Execution / Discovery) | structural damage should precede collapse more often than an execution miss |
| F4 | `threatMechanismImpaired` | whether the thing that makes the company work is broken |
| F5 | number of blind spots flagged | more independent warnings |
| F6 | `recommendedSize` / `capPercent` | how far the analyst wanted the position cut |
| F7 | consecutive bearish calls before this one | a company already in decline |
| F8 | year of the call | tests whether "disaster" is really "2023–2025" |
| F9 | prior 90-day return before the call | tests whether it is just falling-knife momentum, i.e. the market already knew |

**F8 and F9 are controls, not candidates.** If either separates as strongly as
the analyst's own fields, the profile is a period effect or a momentum effect
and not analyst insight. **Report them first.**

### 5c. How to test each feature — and the rule that decides

For each feature and each target, on **train first, then tune**:

- the share of disasters in each bucket, and the share of non-disasters;
- **the same counted by company, not by call**;
- a 95% range from a **ticker-block bootstrap** (resample whole companies,
  seed recorded).

**A feature counts as separating only if all four hold:** it separates on
train; it separates the same direction on tune; it still separates when
counted per company; and it separates on **both** targets in §5a. **Report all
nine features against all four conditions in one table, whatever the result.**

### 5d. The leave-one-company-out check — the one that matters

Take the strongest feature from 5c. Recompute its separation **21 times**,
each time dropping one of the 21 companies that contributed a disaster.
**Report the range of results.** If dropping a single company (PARA, SUNW or
SEDG most likely) collapses the finding, **say so in the headline** — a
profile that depends on one name is a description of that name.

## 6. Pre-registration — write to `findings.md` and commit BEFORE computing anything

Nine features × two targets × two splits is enough to manufacture a winner.
Predictions committed first; all nine reported; train discovers, tune confirms.

**Registered predictions, 2026-09-20:**

- **The controls will do well, and that is the expected outcome.** Stratum
  (F1) and year (F8) will separate, because the disasters cluster in the
  failures stratum and in 2023–2025. **That is not a useful finding** — it
  says the corpus contains failures and that recent years were harsh.
- **Prior 90-day return (F9) will separate**, because collapsing companies are
  usually already falling. If it separates *more strongly* than every analyst
  field, the honest conclusion is that a price filter beats the analyst for
  this purpose, and that is worth knowing.
- **The analyst's own fields (F2–F6) will mostly not separate**, consistent
  with the earlier ranking test.
- **Consecutive bearish calls (F7) is the one I would bet on**, because it is
  the only feature that carries history rather than a single reading.
- **Falsified if** nothing separates on both targets, both splits and per
  company. Then the disasters are not identifiable in advance from anything
  available at the call, and the bearish signal must be used as an
  undifferentiated whole or not at all.

## 7. Report step

**Scope boundary: report, do not decide.** Do not change any allocator rule,
sizing rule, or the exit ratchet. Do not propose a prompt candidate.

Write `wrap-ups/disaster-profile-test-out.md`, three forms (`.md`, `.docx`
with real Word tables, published artifact page). **Open with §0, defined
terms** — at minimum: bearish call, tradeable entry, benchmark-relative
return, disaster (both definitions), stratum, per-call vs per-company
counting, leave-one-company-out, ticker-block bootstrap.

Open the body with this sentence, filled in:

> Of 187 bearish calls, the worst 46 averaged −61.5% against the S&P over six
> months, and they came from ___ companies, with ___ of the 46 from just three
> names. Of nine features known at the time of the call, ___ separated
> disasters from ordinary bearish calls on both halves of the data and when
> counted per company. The strongest was ___, and dropping a single company
> moved it from ___ to ___.

Then the nine-feature table, the leave-one-out result, and one plain paragraph
per finding. **Controls reported before candidates.**

**Close with what it means for a decision, three ways:** if a feature survives
everything, what a size-aware trim rule built on it would look like and what
would have to be true before trusting it; if only the controls separate, say
plainly that the disasters are a period-and-failures artifact and the analyst
adds nothing to spotting them; if nothing separates, say that the bearish
signal cannot be graded by severity and must be acted on as a whole.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of — not "24.6% of the sample" but "46 of the 187 bearish
calls." Write "points," never "pp." Short sentences. Lead with the finding.

## 8. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. Work on
`sweep/db-corpus-baseline`. Provenance for every figure. One prompt in, one
wrap-up out. Commit the outputs. Free and short; no budget reason to rush.
