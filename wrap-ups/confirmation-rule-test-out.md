# The confirmation-rule test — waiting for a second bearish call is not distinguishable from acting at once or holding

**Run:** `confirmation-rule-test` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0.** No model calls, no API spend, no DB writes, no cache refresh, holdout untouched, `analysis/analyst_direct_scorer.py` unmodified.
**Status: complete.** All four strategies, both splits and the pooled figures, three follow-up groups.

## Read this first: the price data for one company is corrupt, and it makes the prompt's "4 points" figure disappear

**PARA's price series in `analysis/data/corpus_v2/scorer_price_cache_v1.json` is wrong.** It reads **$106,000 in November 2023, $3,870 in April 2024, $212 in May 2025 and $36 in November 2025**. Paramount never traded near those levels. The series decays smoothly from about $100,000 to about $1 over the corpus. Any six-month return computed on it is a fake loss of 50% to 100%. I screened every ticker in the corpus for absurd price levels. **PARA is the only one.** (FRC and SUNW also go to zero, but those were real failures.) I did not touch the cache, per the standing rule.

**Why it matters here.** The prompt's premise that a flagged stock lags the S&P by about 4 points is driven by this error. PARA has 10 bearish calls with a following call in this run. Excluding them:

| pooled, 179 cases → 169 without PARA | with PARA (as the prompt specified) | without PARA (my sensitivity) |
|---|---|---|
| A. Hold, average benchmark-relative return | **−4.1** [−16.1, 6.5] | **0.0** [−8.7, 8.7] |
| Loss avoided by selling at once | +4.1 [−6.5, 16.1] | **0.0** [−8.7, 8.7] |
| Cost of waiting, before any decision | −3.6 [−10.8, 3.3] | −1.2 [−6.8, 4.7] |

Sources: `analysis/data/run_state/confirmation-rule-test/cells.jsonl` (with PARA) and `nopara.json` (without). **Every figure below is reported both ways.** With-PARA is the run the prompt specified. Without-PARA is a sensitivity I added after finding the defect, and the better guide to what the analyst's calls really did.

**How far the defect reaches into earlier work.** I re-ran the v6 bearish edge with PARA excluded (`r4check.txt`, `nopara.json`). It moves modestly, because those measures count calls that fall into a category and PARA's fake losses only push more of PARA's calls into the "lagged" category:

| bearish edge, points | with PARA | without PARA |
|---|---|---|
| 182 days, as-is entry, pooled (the +13.3 baseline) | +13.3 | **+12.3** |
| 182 days, as-is entry, train | +15.3 | +13.4 |
| 30 days, as-is entry, train (R4's headline) | +23.2 | +21.4 |
| 30 days, tradeable entry, train (R4b) | +18.7 | +17.3 |
| 10 days, tradeable entry, train | +16.2 | +14.2 |
| any horizon on tune | unchanged | unchanged (PARA is train only) |

**Previously published numbers this touches.** The +13.3 baseline is **+12.3** without PARA; the train figures in R4 and R4b are 1 to 3 points high. **No conclusion in R4 or R4b changes.** The shapes and the train-versus-tune splits are the same. The 4-point figure quoted in this run's own prompt (and attributed to the entry-price test's 90-day figures) is the one that does not survive; I have not traced its origin further. **PARA's series should be repaired or PARA excluded before the next round. That decision is not mine.**

## §0 Defined terms

- **Bearish call.** The analyst said Trim or Exit on that earnings call.
- **Benchmark-relative return.** The stock's return minus the S&P 500's (SPY) return over the same dates. Written in percent.
- **Tradeable entry.** Every entry and exit price is the close of the first trading day *after* the call date. The entry-price test (R4b) showed that using the call-date close credits a strategy with the overnight announcement move, which nobody can trade.
- **Confirmed pair.** A bearish call followed by a second bearish call from the same company, at its next call in the corpus.
- **The four strategies.** **A, Hold:** do nothing; return from the day after the bearish call to 182 days after it. **B, Sell now:** exit the day after the bearish call; you keep 0 relative to the S&P from then on, and "loss avoided" is minus A. **C, Wait and confirm:** hold until the day after the next call; if that call is bearish, exit then, otherwise keep holding to 182 days from the *original* call. **D, Wait and always exit:** hold to the next call, then exit whatever it says.
- **Cost of waiting.** The average benchmark-relative return between the day after the bearish call and the day after the next call, i.e. what you eat before any decision is made.
- **Ticker-block bootstrap.** To get a 95% range I redraw the set of companies 2,000 times with replacement (seed 11) and recompute the average each time. I redraw whole companies, not single calls, because one company's calls are not independent. Paired differences use the same redrawn companies.

## Lead-with sentence

Of **179** bearish calls with a following call, **78** were followed by a second bearish call. Doing nothing returned **−4.1%** against the S&P over six months (**0.0%** without the corrupt PARA series). Selling the day after the first bearish call avoided **4.1 points** (**0.0**). Waiting for the next call and exiting only on a second bearish call returned **−2.1%** (**+0.5%**). Waiting cost **3.6 points** in the quarter before the decision was made (**1.2**). None of these strategy differences is distinguishable from zero.

## 1. The population — the prompt's counts are right

Re-derived, not copied: 187 bearish calls (103 train, 84 tune, WOLF and SPWR excluded); 8 are a company's last call, leaving **179 cases: 100 train, 79 tune**. Next call was bearish **78**, neutral **91**, bullish **10**. All prices existed for all 179. One case (JKS, next call 202 days later) had its exit clipped to the 182-day end. The bullish arm has 10 cases from 9 companies.

## 2. The four strategies

Average benchmark-relative return, in percent. Brackets are 95% ticker-block ranges. Source: `cells.jsonl`; also `tables.txt`.

| | split | cases (companies) | **A. Hold** | **B. Sell now** (loss avoided) | **C. Wait and confirm** | **D. Wait, always exit** | cost of waiting | share ending negative (A) |
|---|---|---|---|---|---|---|---|---|
| with PARA | train | 100 (30) | −7.2 [−25.8, 9.8] | 0 (+7.2 [−9.8, 25.8]) | −2.5 [−15.9, 10.3] | −6.3 [−17.5, 3.9] | −6.3 [−17.5, 3.9] | 64% |
| | tune | 79 (27) | −0.1 [−8.4, 11.0] | 0 (+0.1 [−11.0, 8.4]) | −1.5 [−7.5, 7.6] | −0.2 [−6.6, 8.6] | −0.2 [−6.6, 8.6] | 58% |
| | pooled | 179 (57) | −4.1 [−16.1, 6.5] | 0 (+4.1 [−6.5, 16.1]) | −2.1 [−10.4, 6.0] | −3.6 [−10.8, 3.3] | −3.6 [−10.8, 3.3] | 61.5% |
| without PARA | train | 90 (29) | +0.2 [−14.7, 12.7] | 0 (−0.2 [−12.7, 14.7]) | +2.3 | −2.1 | −2.1 [−11.2, 5.7] | 60% |
| | tune | 79 (27) | −0.1 [−8.4, 11.0] | 0 (+0.1) | −1.5 | −0.2 | −0.2 | 58% |
| | pooled | 169 (56) | 0.0 [−8.7, 8.7] | 0 (0.0 [−8.7, 8.7]) | +0.5 | −1.2 | −1.2 [−6.8, 4.7] | 59% |

**The decision quantities** (mean, paired range):

| | with PARA, pooled | without PARA, pooled | train / tune, with PARA |
|---|---|---|---|
| C − A (does confirming beat holding?) | +2.0 [−2.0, 6.3] | +0.5 [−2.8, 3.6] | +4.6 [−0.8, 10.9] / −1.4 [−6.7, 2.3] |
| C − B (does confirming beat selling at once?) | −2.1 [−10.4, 6.0] | +0.5 [−6.4, 7.5] | −2.5 [−15.9, 10.3] / −1.5 [−7.5, 7.6] |

Every range spans zero. The share of flagged stocks that ended negative is 59% to 64% of cases, but the *average* return is close to zero: a lot of small losses, offset by a lot of gains, and a few collapses. **The median flagged stock returned −8.8% with PARA and −7.7% without.**

## 3. The three-way split — this is where the confirmation rule earns its keep or does not

Strategy C by what the next call said. Every figure is an average; brackets are ticker-block ranges. **For the neutral and bullish groups C is identical to A by construction** (you keep holding), so C − A is exactly zero there. Only in the confirmed group does C differ.

| next call | split | cases (companies) | A. Hold | C. Wait and confirm | cost of waiting | C − A |
|---|---|---|---|---|---|---|
| **bearish** (confirmed) | train | 45 (16) | −30.1 [−51.2, −6.5] | −19.8 [−30.4, −8.4] | −19.8 | +10.2 [−2.1, 22.1] |
| | tune | 33 (12) | −2.1 [−21.1, 27.2] | −5.4 [−18.7, 18.4] | −5.4 | −3.3 [−17.2, 5.1] |
| | pooled | 78 (28) | −18.2 [−35.4, −0.2] | −13.7 [−23.1, −2.4] | −13.7 | +4.5 [−4.8, 13.5] |
| | pooled, no PARA | 69 (27) | −11.4 [−26.1, 4.1] | −10.2 | −10.2 [−18.4, 1.0] | +1.2 [−6.6, 9.3] |
| **neutral** | train | 48 (27) | +12.2 [−4.9, 31.7] | +12.2 | +2.4 [−7.4, 11.1] | 0 |
| | tune | 43 (27) | +0.8 [−6.5, 9.9] | +0.8 | +3.8 [−1.6, 9.1] | 0 |
| | pooled | 91 (54) | +6.8 [−3.3, 17.9] | +6.8 | +3.1 [−2.8, 8.2] | 0 |
| **bullish** (10 cases; no conclusion rests on this) | pooled | 10 (9) | +7.5 [−15.1, 36.0] | +7.5 | +14.3 [−7.7, 40.9] | 0 |

**Confirmed minus neutral, A (does the second call carry information?)** Ticker-block ranges (`extra.json`): train **−42.3** [−64.4, −21.6]; tune **−2.9** [−26.8, 29.6]; pooled **−25.1** [−41.3, −6.2].

**How much of that is the decline that happens before the second call.** By the time a second call arrives, a confirmed stock has already fallen (cost of waiting −13.7 pooled against +3.1 for neutral). What the confirmation rule can still act on is the return *after* the exit day. That is minus (C − A) in the confirmed group: train **−10.2** (kept falling), tune **+3.3** (rebounded), pooled **−4.5** [−13.5, 4.8]. Confirmed stocks also did worse than neutral ones *after* the exit day on train (difference −20.0 [−36.5, −4.5], range excludes zero), but not on tune (+6.3 [−5.2, 22.4]); pooled −8.3 [−19.9, 3.1].

## 4. Findings

**1. The corrupt PARA series is the biggest finding, and it is not the one the run was built for.** See the top of this report. It converts a "flagged stocks lose 4 points" starting premise into "flagged stocks lose nothing on average," and hides that the typical flagged stock still lags (median about −8%).

**2. Selling at once does not beat holding, on average, once the data are right.** As specified: +4.1 loss avoided, range −6.5 to +16.1. Train +7.2, tune **+0.1**. Without PARA: **0.0**. The prompt's prediction (B beats A by roughly 4) is met by the pooled point estimate only, and only because of PARA. **It does not replicate on tune.**

**3. C lands between A and B on the pooled and train figures with PARA; on tune it does not.** Tune: A −0.1, B 0, C **−1.5**, below both. Without PARA: A 0.0, B 0, C +0.5. **The pre-registered prediction is partly met and cannot be distinguished from noise either way.**

**4. The second call clearly separates the groups on train and not on tune.** Confirmed calls did far worse than neutral-followed calls on train (−30.1 vs +12.2; difference −42.3 with a range excluding zero). On tune they differ by 2.9 points with a range from −26.8 to +29.6. The pre-registration said that if the confirmed group does not do clearly worse, the confirmation idea is dead. **Train says it does; tune cannot say.** By "train discovers, tune confirms," it is not shown. **The sign is the same on both splits and on the pooled figures, with or without PARA (−11.4 vs +8.0).**

**5. Most of the confirmed group's decline has already happened by the time you would confirm.** The median next call arrives 91 days after the first (range 3 to 202). Pooled, the confirmed group's average return in that quarter is −13.7 out of its −18.2 six-month total. Exiting at confirmation avoids the remaining −4.5 pooled, with a range from −13.5 to +4.8, and the sign flips between train (avoids 10.2) and tune (gives up 3.3).

**6. The cost side is real for the group where waiting hurts and small for the rest.** Waiting costs 3.6 points on average in the quarter before a decision (1.2 without PARA), but that is a blend: −13.7 for the 78 that turn out to be confirmed and **+3.1 for the 91 that are followed by a neutral call** (waiting *earns* 3.1 there).

**7. The averages are dominated by a few collapses.** The five worst hold outcomes pooled are PARA ×3 (fake), FRC and SUNW (real). Removing the worst five moves the pooled hold average from −4.1 to −1.1. The real collapses are the case for acting at once: **FRC 2023-01-13**: A −112, B 0, but C −96 (its next call came 101 days later and was bearish; waiting ate most of the loss). **SUNW 2023-08-14**: A −103, C −70. **SEDG** (four bearish calls in a row 2023 to 2024): A −74, −76, −86, −51 against C −58, −34, −59, −47. In these collapses C keeps between 14% and 92% of A's loss (SUNW 2023-05-25: A −85, C −12; SEDG 2024-08-07: A −51, C −47). That is the tail a single-call exit avoids, and it is not visible in the averages.

**8. Falsification check: C does not beat B with PARA in.** C −2.1 against B 0. **Without PARA, C is +0.5 against B 0 (paired range −6.4 to +7.5).** That is inside the noise, but it is the exact case the prompt says to treat as a reason to re-check the calculation. I re-checked: the difference is C's neutral group (+8.0 without PARA) being held rather than sold, offset by C's confirmed group (−10.2). No error found.

## 5. What Luis would do differently

- **If acting at once won:** it did not. The pooled loss avoided is 4.1 with PARA and 0.0 without, and tune is +0.1. There is no case here for a single-call exit trigger *on average return*. The case that remains is **tail protection**: it is FRC, SUNW and SEDG-type outcomes that a same-day exit would have avoided in full (finding 7).
- **If confirming won:** it did not either. C − A is +2.0 [−2.0, 6.3] with PARA and +0.5 [−2.8, 3.6] without. What the second call *does* do, on train, is sort the stocks that go on to do badly (−30%) from those that do not (+12%). But that sorting has mostly happened by the time you act on it.
- **Indistinguishable — this is the answer.** The choice between acting at once, waiting for a second call, and holding then rests on what this run does not model: **tax on realized gains and losses, trading costs, and the risk you are willing to carry in a position**, especially through a collapse. The graduated exit ratchet is a closed design decision; this run does not reopen it.

## 6. Deviations and premises

1. **PARA's price series is corrupt** (top of report). Not in the prompt. The prompt's "4.8 points over 90 days" figure was not re-derived here.
2. **"Next call" is the next call in the corpus,** not necessarily the next quarter. Three cases are more than 150 days out (JKS 181 and 202 days, GIS 175); one MMM pair is 3 days apart. I did not filter them.
3. **Robustness computations added after seeing the point estimates:** confirmed-minus-neutral ranges, the concentration check, the no-PARA sensitivity, and the R4/R4b PARA check. They are labelled as such and were committed before their outputs were used. The pre-registered tests are the ones in `findings.md`.
4. **For the no-PARA tables** I show ranges only where I computed them for the exact quantity; the rest are point estimates from `nopara.json`.
5. **B's "share negative" is not meaningful** (0 by construction) and is not shown.
6. **Version guard skipped:** no scoring calls.
7. **`prompts/disaster-profile-test.md` is untracked in the working tree.** It is not this run's prompt and I did not stage it.

## 7. Verification

- Population counts re-derived and match the prompt exactly (187 / 179 / 78 / 91 / 10 / 8).
- Fixed 182-day horizon from the *original* call for all four strategies. Entry and exit are strictly after the relevant call date.
- WOLF and SPWR excluded; holdout not read (the eval directories are train and tune only).
- The PARA defect was checked against the cache directly (series values) and against a screen of every corpus ticker.
- Not verified: a corrected PARA series (none available without a refresh, which is not permitted).

## 8. Follow-up commands

```
python3 analysis/confirmation_rule_driver.py run
python3 analysis/confirmation_rule_driver.py extra
python3 analysis/confirmation_rule_driver.py nopara
python3 analysis/confirmation_rule_driver.py r4check
cat analysis/data/run_state/confirmation-rule-test/tables.txt
```

Provenance: `analysis/data/run_state/confirmation-rule-test/cells.jsonl` (keys `split`, `group`, `results.<strategy>.mean_pct`, `mean_ci95`); per-case rows `cases.json`; robustness `extra.json`; no-PARA `nopara.json`; R4/R4b check `r4check.json`; price cache `analysis/data/corpus_v2/scorer_price_cache_v1.json` (PARA and VIAC keys); bootstrap seed 11, 2,000 redraws.
