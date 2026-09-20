# The confirmation-rule test — is it better to act on one bearish call, or wait for a second?

**Run ID:** `confirmation-rule-test`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/confirmation-rule-test-out.md`
**Cost: $0. NO MODEL CALLS.** Re-grades eval caches and prices already on
disk. **If you are about to call the Anthropic API, stop and report.**

**Read first:** `wrap-ups/R4b-tradeable-entry-out.md` (the entry-price rule
this run inherits), `docs/handoffs/2026-09-19-state-of-play.md` §0 and §2,
`docs/architecture/PROMPT_ARCHITECTURE.md` §2.3, and
`analysis/analyst_direct_scorer.py`.

---

## 1. The question, in plain terms

The analyst says "this will do badly" on about one call in thirteen. When it
does, it is right about 60% of the time against a 47% base rate. Measured
from the first price a reader could actually trade at, a flagged stock goes on
to lag the S&P by about 4 points more than an average stock over the next six
months — but that average is uncertain and is driven by a small number of
collapses.

**Luis's proposal: don't act on one bearish call. Wait for the next earnings
call. If it is bearish too, exit. If it isn't, hold.**

That trade has a known cost and an unknown benefit.

- **The cost is one quarter of decline.** Flagged stocks lag the S&P by about
  4.8 points over the 90 days after the call, from a tradeable entry. Waiting
  means eating roughly that.
- **The benefit is fewer false alarms.** About 40% of bearish calls are
  followed by the stock *not* lagging. Waiting filters some of those out.

**This run prices both sides.** It decides nothing.

## 2. The population, already counted

Of 187 bearish calls (both splits, WOLF and SPWR excluded), **179 have a
following call** by the same company; 8 are that company's last call in the
corpus. Of those 179:

| the next call was… | count | share |
|---|---|---|
| bearish again | **78** | 44% |
| neutral | 91 | 51% |
| bullish | 10 | 6% |

**78 confirmed pairs is a usable sample and 10 bullish follow-ups is not** —
report the bullish arm, never rest a conclusion on it.

## 3. Ground rules

1. **No model calls, no API spend, no DB writes, no cache refresh.**
2. **Do not modify `analysis/analyst_direct_scorer.py`.** Import from it.
3. **Holdout untouched.** Train and tune only; assert it.
4. **Price cache is `analysis/data/corpus_v2/scorer_price_cache_v1.json`.**
   Never `analysis/data/price_cache.json`.
5. **Resolve symbols through `TICKER_ALIASES.json` before enumerating**
   (`ANTM`→`ELV`, `VIAC`→`PARA`, `GOOGL`→`GOOG`). `MAXN` resolves to nothing,
   expected.
6. **Exclude `WOLF` and `SPWR` entirely.**
7. **Every entry and exit price is the close of the first trading day STRICTLY
   AFTER the call date.** This is the tradeable-entry rule established by the
   entry-price test. Using the call-date close would credit strategies with
   the overnight announcement move, which nobody can trade.
8. **`python3`, zsh, macOS Tahoe.** No `--break-system-packages`. No `apt`.
9. **A result that contradicts an expectation here is a finding.**

## 4. Steps −1 and 0

State in `analysis/data/run_state/confirmation-rule-test/`. `progress.json`
written first. `cells.jsonl` per strategy × split. `findings.md` append-only,
**carrying §6's pre-registration before any outcome is computed.** Clean tree,
hard stop on `git_dirty`. Driver `analysis/confirmation_rule_driver.py`
committed as its own commit before producing output. No version guard needed —
record that it was skipped and why.

## 5. The work — four strategies, same calls, same prices

For every bearish call that has a following call, compute the
benchmark-relative return under each of four rules. All returns start at the
close of the first trading day after the triggering call.

| strategy | what it does |
|---|---|
| **A. Hold** | do nothing. Return from the day after the bearish call to 182 days later. The do-nothing comparison every other strategy must beat. |
| **B. Sell now** | exit the day after the bearish call. Return is 0 relative to the benchmark from that point — you are out. Measured as the loss avoided versus A. |
| **C. Wait and confirm** | hold from the bearish call until the day after the *next* call. If that call is bearish, exit then. Otherwise keep holding to 182 days from the original call. |
| **D. Wait and always exit** | hold to the next call, then exit regardless of what it says. Isolates how much of C's result is the waiting and how much is the confirming. |

**Report for each strategy, each split:** number of cases, average
benchmark-relative return, median, the share that ended negative, and a 95%
range from a **ticker-block bootstrap** (resample whole companies, seed
recorded). **C minus A and C minus B are the decision quantities** — report
each with a paired range.

**Then the three-way split** of strategy C by what the next call said —
bearish (78), neutral (91), bullish (10) — with the same figures. This is
where the confirmation rule either earns its keep or does not.

**Also report, because it is the cost side in plain money:** the average
benchmark-relative return between the bearish call and the next call, i.e.
what waiting costs before any decision is made.

### Two traps to avoid

**The horizon must be held fixed at 182 days from the ORIGINAL bearish call**
for every strategy. If C is allowed to run 182 days from the *second* call it
gets a longer window and the comparison is meaningless.

**A company's calls are not independent**, and the earlier work found the
worst outcomes concentrated in a few names. Ranges come from resampling whole
companies, never single calls. **Report how many distinct companies each arm
rests on.**

## 6. Pre-registration — write to `findings.md` and commit BEFORE computing outcomes

Four strategies × three follow-up types is enough combinations to hand back a
flattering winner. Rules: predictions committed first; every arm reported;
**train discovers, tune confirms** — a rule that looks good on train and not on
tune has not been shown.

**Registered predictions, 2026-09-20:**

- Selling immediately (B) beats holding (A) on average, by roughly the 4 points
  the entry-price test implies, with a wide range that may include zero.
- **Waiting and confirming (C) lands between A and B** — better than holding,
  worse than acting at once — because the quarter of decline you eat is not
  recovered by the false alarms you dodge.
- Within C, the **confirmed** group (next call also bearish) does clearly worse
  than the **neutral** group. If it does not, the second call carries no
  information and the whole confirmation idea is dead.
- **Falsified if** C beats B: waiting would then be free or better, which would
  contradict the 90-day figures and should be treated as a reason to re-check
  the calculation before believing it.

## 7. Report step

**Scope boundary: report, do not decide.** Do not change the exit ratchet,
`DESIGN_PRINCIPLES.md`, or any allocator rule. The graduated exit ratchet is a
closed design decision and this run does not reopen it — it supplies evidence
for a conversation.

Write `wrap-ups/confirmation-rule-test-out.md`, three forms (`.md`, `.docx`
with real Word tables, published artifact page). **Open with §0, defined
terms** — at minimum: bearish call, benchmark-relative return, tradeable entry,
confirmed pair, the four strategies in one line each, ticker-block bootstrap.

Open the body with this sentence, filled in:

> Of ___ bearish calls with a following call, ___ were followed by a second
> bearish call. Doing nothing returned ___% against the S&P over six months.
> Selling the day after the first bearish call avoided ___%. Waiting for the
> next call and exiting only on a second bearish call returned ___%. Waiting
> cost ___% in the quarter before the decision was made.

Then the four-strategy table, the three-way split, and one plain paragraph per
finding. **Close with what Luis would do differently** under each outcome: if
acting at once wins, the case for a single-call exit trigger; if confirming
wins, the case for a two-call rule; if they are indistinguishable, say so
plainly and say that the choice should then rest on tax and trading costs,
which this run does not model.

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Short sentences. Lead with the
finding. Define any technical term in one plain line at first use.

## 8. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. Work on
`sweep/db-corpus-baseline`. Provenance for every figure — file path plus key
or column. One prompt in, one wrap-up out. Commit the outputs. Free and short;
no budget reason to stop early.
