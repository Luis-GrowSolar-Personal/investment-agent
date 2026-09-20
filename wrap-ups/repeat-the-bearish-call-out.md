# Ask it twice — repeating a bearish call points the right way, but the evidence cannot tell it apart from chance

**Run:** `repeat-the-bearish-call` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $15.07** (batch $14.91, two-call pilot $0.16) against a $14 estimate and a $20 cap. Model `claude-sonnet-4-6`, prompt unchanged v6, version guard passed against the promoted hash.
**Status: complete.** All 354 fresh readings collected (0 errored, 0 truncated, 0 unreadable). No DB writes, no cache refresh, holdout untouched, `analysis/analyst_direct_scorer.py` unmodified.

## §0 Defined terms

- **Bearish call.** The analyst said Trim or Exit on that earnings call.
- **Tradeable entry.** Every return starts at the close of the first trading day *after* the call date, because the call-date close credits a strategy with an announcement move nobody can trade.
- **Benchmark-relative return.** The stock's return minus the S&P 500's return over the same dates, from that entry to 182 days after the call.
- **The three groups.** Each call has three readings: the original and two fresh ones from the same prompt. **3 of 3:** bearish all three times. **2 of 3:** bearish on the original and one re-run. **1 of 3:** bearish only on the original; neither re-run agreed.
- **Tail.** A call whose stock fell more than 25% behind the S&P over the six months. The disasters.
- **Worst quarter.** The average of the worst quarter of calls in a group (the lowest 25%).
- **Accuracy versus money.** *Accuracy* counts a call as right if the stock lagged the S&P by more than 5%, however far it fell. *Money* is how far it actually fell. A 6% lag and a 60% collapse count the same in accuracy and very differently in money.
- **Ticker-block bootstrap.** To get a 95% range I redraw the set of companies 2,000 times with replacement (seed 11) and recompute the figure each time. I redraw whole companies, not single calls, because one company's calls are not independent. Differences use the same redrawn companies. If a range includes zero, the data cannot tell the two groups apart.

## Lead-with sentence

The analyst was asked twice more about the **177** calls it had already called bearish (the prompt's 187 minus 10 Paramount calls, whose price series is corrupt). It repeated the call both times on **101** of them, once on **34**, and not at all on **42**. Of the 101 calls it repeated every time, **29 (28.7%)** went on to lag the S&P by more than 25%, against **13 of 76 (17.1%)** of the calls it did not repeat every time (7 of 42, 16.7%, for the ones it never repeated). The worst quarter of the repeated group averaged **−61.0%** against **−36.7%** for the rest. Selling the day after a repeated bearish call would have saved **8.6%** against holding, with a range from −2.1% to +21.0%; for a call that was not repeated every time, it would have **cost 7.8%** (saving range −18.7% to +3.2%).

**Read that with the ranges.** In every comparison below, the range for the difference between groups includes zero on the tail measure, on both splits. The direction matches the prediction. The evidence does not establish it.

## 1. Something the prompt did not expect: the analyst repeats itself less than 87% of the time

The prompt reasoned that a 12.8% run-to-run disagreement rate means about 87% of re-runs come back bearish and about three-quarters of calls land in 3-of-3. **Measured, only 66.7% of re-runs came back bearish** (236 of 354; 116 neutral, 2 bullish), and **101 of 177 (57.1%)** landed in 3-of-3, 34 (19.2%) in 2-of-3 and 42 (23.7%) in 1-of-3. Source: `analysis/data/run_state/repeat-the-bearish-call/groups.json`, `scores.jsonl`.

The sanity gate I registered before any outcome (3-of-3 share between 50% and 95%) **passed**, so I proceeded. But the gap from the prompt's expectation has a plain explanation, and it is not a fault in the driver: **these calls were chosen because the original reading was bearish.** The 12.8% figure is an average over all calls, most of which the analyst reads the same way every time (Hold). For a call it has said bearish once, a fresh reading says bearish about two times in three. That is the analyst's real consistency on exactly the calls that matter, and it is lower than the headline noise figure suggests. (Calls in the 1-of-3 group, 42 of 177, are ones it called bearish once and then declined to repeat twice.)

## 2. The money result

Source for every row: `analysis/data/run_state/repeat-the-bearish-call/cells.jsonl`, driver `analysis/repeat_bearish_driver.py analyze`. Brackets are 95% ticker-block ranges. "Saves" is what selling the day after the call would have saved against holding to 182 days; a negative number means selling would have cost money.

### Both splits pooled (177 calls, 57 companies)

| group | calls (companies) | fell more than 25% behind: count, share [range] | worst-quarter average | median | mean | worst call | selling the day after saves vs holding [range] |
|---|---|---|---|---|---|---|---|
| 3 of 3 (bearish every time) | 101 (41) | 29 of 101 = 28.7% [15.6, 42.1] | -61.0% | -10.1% | -8.6% [-21.0, 2.1] | -112.5% | +8.6% [-2.1, 21.0] |
| 2 of 3 | 34 (26) | 6 of 34 = 17.6% [5.9, 30.9] | -41.2% | -10.2% | 0.5% [-12.5, 15.9] | -77.7% | -0.5% [-15.9, 12.5] |
| 1 of 3 (never repeated) | 42 (33) | 7 of 42 = 16.7% [6.5, 29.5] | -34.0% | -1.6% | 13.7% [-1.9, 32.2] | -57.2% | -13.7% [-32.2, 1.9] |
| not 3 of 3 (2 + 1) | 76 (46) | 13 of 76 = 17.1% [9.0, 25.4] | -36.7% | -5.3% | 7.8% [-3.2, 18.7] | -77.7% | -7.8% [-18.7, 3.2] |
| all bearish calls | 177 (57) | 42 of 177 = 23.7% [14.9, 32.9] | -51.1% | -8.8% | -1.6% [-10.9, 7.5] | -112.5% | +1.6% [-7.5, 10.9] |

### Train (93 calls, 29 companies)

| group | calls (companies) | fell more than 25% behind: count, share [range] | worst-quarter average | median | mean | worst call | selling the day after saves vs holding [range] |
|---|---|---|---|---|---|---|---|
| 3 of 3 (bearish every time) | 53 (21) | 18 of 53 = 34.0% [14.1, 56.1] | -73.0% | -11.7% | -13.1% [-35.7, 4.1] | -112.5% | +13.1% [-4.1, 35.7] |
| 2 of 3 | 18 (13) | 4 of 18 = 22.2% [5.9, 43.8] | -54.3% | -13.6% | -5.5% [-24.1, 9.1] | -77.7% | +5.5% [-9.1, 24.1] |
| 1 of 3 (never repeated) | 22 (18) | 5 of 22 = 22.7% [6.2, 41.7] | -39.1% | 0.1% | 26.6% [-0.6, 57.8] | -46.7% | -26.6% [-57.8, 0.6] |
| not 3 of 3 (2 + 1) | 40 (23) | 9 of 40 = 22.5% [10.3, 35.9] | -43.4% | -5.3% | 12.1% [-5.1, 27.6] | -77.7% | -12.1% [-27.6, 5.1] |
| all bearish calls | 93 (29) | 27 of 93 = 29.0% [15.8, 43.3] | -61.3% | -9.5% | -2.2% [-19.5, 11.7] | -112.5% | +2.2% [-11.7, 19.5] |

### Tune (84 calls, 28 companies)

| group | calls (companies) | fell more than 25% behind: count, share [range] | worst-quarter average | median | mean | worst call | selling the day after saves vs holding [range] |
|---|---|---|---|---|---|---|---|
| 3 of 3 (bearish every time) | 48 (20) | 11 of 48 = 22.9% [6.9, 38.6] | -45.4% | -9.0% | -3.8% [-12.5, 7.5] | -85.8% | +3.8% [-7.5, 12.5] |
| 2 of 3 | 16 (13) | 2 of 16 = 12.5% [0.0, 26.7] | -27.9% | -3.2% | 7.3% [-10.9, 37.3] | -40.4% | -7.3% [-37.3, 10.9] |
| 1 of 3 (never repeated) | 20 (15) | 2 of 20 = 10.0% [0.0, 26.7] | -28.5% | -5.3% | -0.5% [-12.7, 8.8] | -57.2% | +0.5% [-8.8, 12.7] |
| not 3 of 3 (2 + 1) | 36 (23) | 4 of 36 = 11.1% [2.7, 20.8] | -28.2% | -5.3% | 3.0% [-9.2, 17.7] | -57.2% | -3.0% [-17.7, 9.2] |
| all bearish calls | 84 (28) | 15 of 84 = 17.9% [6.3, 28.7] | -38.5% | -8.5% | -0.9% [-9.2, 9.4] | -85.8% | +0.9% [-9.4, 9.2] |

## 3. Accuracy, for comparison with the earlier work

Accuracy counts a call as right if the stock lagged the S&P by more than 5%.

### Pooled

| group | calls | lagged by more than 5%: count, share [range] |
|---|---|---|
| 3 of 3 (bearish every time) | 101 | 60 of 101 = 59.4% [48.2, 70.5] |
| 2 of 3 | 34 | 19 of 34 = 55.9% [40.0, 70.8] |
| 1 of 3 (never repeated) | 42 | 19 of 42 = 45.2% [30.6, 60.0] |
| not 3 of 3 (2 + 1) | 76 | 38 of 76 = 50.0% [39.1, 61.8] |
| all bearish calls | 177 | 98 of 177 = 55.4% [46.7, 64.0] |

### Train

| group | calls | lagged by more than 5%: count, share [range] |
|---|---|---|
| 3 of 3 (bearish every time) | 53 | 33 of 53 = 62.3% [44.7, 78.8] |
| 2 of 3 | 18 | 11 of 18 = 61.1% [38.1, 84.0] |
| 1 of 3 (never repeated) | 22 | 9 of 22 = 40.9% [21.1, 61.1] |
| not 3 of 3 (2 + 1) | 40 | 20 of 40 = 50.0% [35.1, 65.9] |
| all bearish calls | 93 | 53 of 93 = 57.0% [43.8, 69.8] |

### Tune

| group | calls | lagged by more than 5%: count, share [range] |
|---|---|---|
| 3 of 3 (bearish every time) | 48 | 27 of 48 = 56.2% [38.5, 72.1] |
| 2 of 3 | 16 | 8 of 16 = 50.0% [25.0, 71.4] |
| 1 of 3 (never repeated) | 20 | 10 of 20 = 50.0% [30.0, 70.6] |
| not 3 of 3 (2 + 1) | 36 | 18 of 36 = 50.0% [33.3, 65.6] |
| all bearish calls | 84 | 45 of 84 = 53.6% [39.5, 65.9] |

**The 48-call sample's accuracy pattern (50% for unanimous calls against 25% for split calls) does not reproduce at that size.** Here it is 59.4% for 3 of 3 against 45.2% for 1 of 3, a 14-point gap, and only 6 points on tune.

## 4. The differences, with ranges

Points, group minus group. Each range is a paired ticker-block bootstrap of the difference. A range that includes zero means the data cannot tell the groups apart.

| comparison | split | tail share (points) [range] | accuracy (points) [range] | worst-quarter average (points) [range] | mean return (points) [range] |
|---|---|---|---|---|---|
| 3 of 3 minus 1 of 3 | train | +11.2 [-19.1, 43.1] | +21.4 [-6.1, 50.6] | -33.9 [-73.3, 5.1] | -39.6 [-74.4, -8.2] |
| 3 of 3 minus 1 of 3 | tune | +12.9 [-9.4, 30.4] | +6.2 [-19.1, 30.7] | -16.9 [-46.7, 16.5] | -3.3 [-14.9, 12.3] |
| 3 of 3 minus 1 of 3 | pooled | +12.0 [-7.1, 30.6] | +14.2 [-5.3, 33.1] | -26.9 [-56.2, 0.4] | -22.3 [-43.0, -3.0] |
| 3 of 3 minus not 3 of 3 | train | +11.5 [-11.6, 36.2] | +12.3 [-9.3, 34.7] | -29.6 [-60.2, 6.4] | -25.2 [-48.4, -2.9] |
| 3 of 3 minus not 3 of 3 | tune | +11.8 [-5.4, 28.4] | +6.2 [-14.2, 25.5] | -17.2 [-44.8, 8.7] | -6.8 [-21.8, 9.4] |
| 3 of 3 minus not 3 of 3 | pooled | +11.6 [-3.1, 26.8] | +9.4 [-5.1, 23.8] | -24.3 [-46.2, -0.5] | -16.4 [-31.1, -1.6] |

**The registered primary comparison is 3 of 3 minus 1 of 3 on the tail share.** Pooled +12.0 points, range −7.1 to +30.6. Train +11.2 (−19.1 to +43.1). Tune +12.9 (−9.4 to +30.4). **The direction is what was predicted on both splits. Neither range excludes zero.** Only the *mean return* separates with a range that excludes zero (pooled −22.3, range −43.0 to −3.0; train −39.6, range −74.4 to −8.2), and it does not on tune (−3.3, range −14.9 to +12.3).

## 5. The concentration check

Source: `concentration.json`. The eight companies with the most tail calls in the 3-of-3 group, dropped one at a time. Tail share, 3 of 3 against 1 of 3:

| dropped | pooled: 3 of 3 vs 1 of 3 | train | tune |
|---|---|---|---|
| nobody | 28.7% (29 of 101) vs 16.7% (7 of 42) | 34.0% vs 22.7% | 22.9% vs 10.0% |
| SUNW (5 tail calls) | 25.0% vs 16.7% | **27.1% vs 22.7%** | 22.9% vs 10.0% |
| SEDG (5) | 25.8% vs 17.1% | 34.0% vs 22.7% | **15.0% vs 10.5%** |
| SIRI (4) | 26.0% vs 17.1% | 29.2% vs 23.8% | 22.9% vs 10.0% |
| EOSE, FRC, KHC, BMY, DOW | 27.3% to 28.3% vs 14.6% to 17.1% | 31.4% to 34.0% vs 19.0% to 23.8% | 20.9% to 22.9% vs 10.0% |

**Pooled, the gap survives dropping any one company** (at least 8 points every time). **On each split it does not**: dropping SUNW takes train's gap from 11.3 to 4.4 points, and dropping SEDG takes tune's from 12.9 to 4.5. Each split's difference rests largely on one company. The two splits' deciding companies are different names (SUNW on train, SEDG on tune), so "repetition points the right way on both splits" is two single-company stories, not one repeated result.

## 6. Findings

**1. The registered falsifier did not fire.** The 3-of-3 tail share is higher than the 1-of-3 share on both splits (34.0% against 22.7% on train; 22.9% against 10.0% on tune). The lead is **not closed**.

**2. It is not shown either.** The ranges for the tail difference include zero on all three cuts, and 3-of-3's own tail share (28.7%, range 15.6 to 42.2) overlaps the whole bearish group's (23.7%, range 14.9 to 32.9). By the registered rule ("also falsified in practice if the ranges overlap so heavily that no group can be told from the whole") **this is the case on the tail measure.**

**3. The money gap was predicted to exceed the accuracy gap. The answer depends on the measure.** On the tail share the gap is 12.0 points pooled against 14.2 on accuracy, so **no**. On the worst quarter it is 26.9 points (3 of 3 averaged −61.0%, 1 of 3 −34.0%) and on mean return 22.3 points, so **yes**. On train, accuracy separates by 21.4 points and the tail by 11.2; on tune, the tail by 12.9 and accuracy by 6.2. Money and accuracy move apart here too, but in opposite directions on the two splits.

**4. The calls the analyst declined to repeat went up on average.** The 42 calls in the 1-of-3 group had a *mean* return of **+13.7%** against the S&P and a median of −1.6%. Selling the day after those would have **cost** 13.7 points on average (range −32.2 to +1.9). On train the mean was +26.6%. The mean is being pulled up by a few large winners; I did not investigate which.

**5. Repeated calls averaged a loss of 8.6%, driven by a few collapses.** Median −10.1%, worst call −112.5% (FRC). Selling the day after a 3-of-3 call would have saved 8.6 points on average (range −2.1 to +21.0): train +13.1, tune +3.8. Neither range excludes zero.

**6. Two companies carry the split-by-split result.** See §5.

## 7. What Luis would do differently — three ways

- **If repetition picks out the tail:** this is the weaker version of it. A rule that acts only on calls repeated on both re-runs would send about 57% of bearish calls to action (101 of 177) and hold the rest. It would cost **two extra analyst calls for each bearish call**, which is about 8% of all calls, so roughly **16% more scoring spend** per round (this run's batch cost about $0.042 per request). Before trusting it, three things would have to be true: the difference must hold on companies it was not derived from *and* with a range that excludes zero; it must survive losing SUNW and SEDG; and the 1-of-3 group's +13.7% mean must be explained, because that group's stocks did not fall.
- **If it does not:** the lead is not closed by this run. The falsifier did not fire.
- **If the ranges are too wide to tell (the honest reading):** they are. The tail-share difference of about 12 points would need roughly **190 calls in each group** to be told apart at conventional standards, on the simplest arithmetic (which understates the need, because calls cluster by company). This corpus supplies 101 in the larger group and **42 in the smaller**, and it holds 177 bearish calls in total. **The current corpus cannot resolve an effect of this size**, and adding the locked holdout would not close the gap. A larger test would need more bearish calls, which means more companies or more years, not more re-runs of the same calls.

## 8. Deviations and premises

1. **The prompt's expected split (about 75% in 3-of-3) was wrong** for a selected sample (§1). The registered gate passed at 57.1%; I report the gap as a finding.
2. **The bearish list is 177, not 187,** after excluding PARA (10 calls). The prompt said to expect a lower figure.
3. **The two pilot calls were kept as the first re-run for ABBV 2022-10-28 and BMY 2023-10-26.** They used the same prompt and model with the exact request shape, but synchronously rather than in the batch. Registered before submission.
4. **Cost overshot the $14 estimate slightly** ($15.07), inside the $20 cap. Per-request batch cost was about 11% above the $0.0380 baseline figure.
5. **"Sell now" is scored as zero relative return from the entry,** as in the confirmation-rule test. Saving is minus the hold return, so its range is the hold range reversed.
6. **The worst-quarter figures rest on 10 to 25 calls per group** and should be read as descriptions of those calls.
7. **Sampling settings are the API default,** as in the baselines. I did not set or vary temperature.

## 9. Verification

- Bearish list re-derived from the eval caches; 177 with all transcripts on disk; WOLF, SPWR and PARA excluded.
- Version guard asserted against the promoted v6 hash (`357b6b0b…`), no candidate; request shape identical to the baseline batches.
- Pilot before submission confirmed model availability, parsing and cost per call.
- All 354 responses ended normally (`end_turn`); none truncated; all directions parsed.
- Pre-registration committed before submission and before any outcome; group split computed and gated before outcomes.
- Not verified: an independent re-implementation of the bootstrap; whether the +13.7% mean of the 1-of-3 group is driven by particular companies.

## 10. Follow-up commands

```
python3 analysis/repeat_bearish_driver.py groups
python3 analysis/repeat_bearish_driver.py analyze
cat analysis/data/run_state/repeat-the-bearish-call/analyze_output.txt
```

Provenance: `analysis/data/run_state/repeat-the-bearish-call/` — `scores.jsonl` (354 readings; keys `custom_id`, `direction`, `stop_reason`, `usage`), `cells.jsonl`, `concentration.json`, `groups.json`, `outcome_rows.json`; batch `msgbatch_01WMERpikWAk8gdC5QqeCCYp`; prices `analysis/data/corpus_v2/scorer_price_cache_v1.json`; bootstrap seed 11, 2,000 redraws.
