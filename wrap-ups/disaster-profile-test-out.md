# The disaster-profile test — none of nine known-at-the-time features separates the catastrophes from the ordinary bearish calls

**Run:** `disaster-profile-test` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0.** No model calls, no API spend, no DB writes, no cache refresh, holdout untouched, `analysis/analyst_direct_scorer.py` unmodified.
**Status: complete.** Nine features × two targets × train, tune and pooled, in two versions (PARA included as the prompt specified, and PARA excluded), plus the leave-one-company-out check.

## Read this first: some of the "disasters" are a data error

The prompt's worst 46 calls include **8 from PARA**, and PARA's price series in `analysis/data/corpus_v2/scorer_price_cache_v1.json` is corrupt (about $106,000 in November 2023 decaying to about $1; found in the confirmation-rule test, see `wrap-ups/confirmation-rule-test-out.md`). **Those 8 are not catastrophes; they are fake losses.** The other 38 include real failures (FRC, SUNW) and real collapses (SEDG, EOSE). I therefore report **every result twice: as the prompt specified (PARA included), and with PARA excluded.** Excluding PARA changes the worst quartile from 46 calls averaging −61.3% (cut at −29.5%) to 44 calls averaging −51.1% (cut at −23.8%). **The conclusion does not change.** I did not touch the cache.

## §0 Defined terms

- **Bearish call.** The analyst said Trim or Exit on that earnings call. 187 of them across train and tune (103 train, 84 tune), WOLF and SPWR excluded.
- **Tradeable entry.** Every return starts at the close of the first trading day *after* the call date, because the entry-price test (R4b) showed the call-date close credits a strategy with an announcement move nobody can trade.
- **Benchmark-relative return.** The stock's return minus the S&P 500's (SPY) return over the same dates, from that entry to 182 days after the call.
- **Disaster, two definitions.** **T1, worst quartile:** the 46 lowest returns among the 187 (a fixed cut, −29.5% with PARA, applied to both splits). **T2, fixed threshold:** the stock lagged the S&P by more than 25% (50 calls: 35 train, 15 tune).
- **Stratum.** How the corpus was built. S4 is the failures stratum by construction.
- **Per-call versus per-company counting.** *Per call:* every call counts once. *Per company:* each company's disaster rate is worked out first, then the companies are averaged, so a company with 8 calls counts the same as one with 1.
- **Leave-one-company-out.** Recompute a result 21 times, each time dropping one of the 21 companies that supplied a disaster, and report the range.
- **Ticker-block bootstrap.** To get a 95% range I redraw the set of companies 2,000 times with replacement (seed 11) and recompute the figure each time. Whole companies are redrawn, not single calls, because one company's calls are not independent.
- **Separation, in this report.** For a feature with a "flagged" group and an "other" group, the difference in disaster rate (flagged minus other), in points. Hypothetical example: if 60% of Structural-flagged calls were disasters against 27% of the others, the difference would be +33 points.

## Lead-with sentence

Of 187 bearish calls, the worst 46 averaged **−61.3%** against the S&P over six months (the prompt says −61.5%; my figure), and they came from **21 companies**, with **19 of the 46** from just three names (PARA, SUNW, SEDG). Of nine features known at the time of the call, **none** separated disasters from ordinary bearish calls on both halves of the data and when counted per company. The strongest was the **corpus stratum S4 (a control)**, at **+73.7 points on train**, which rests on **8 calls from two companies (FRC and SUNW) and has no calls at all on tune**. The strongest of the analyst's own fields was **stumbleType Structural**, at **+22.4 points pooled**; dropping a single company moved it between **16.0 (drop PARA) and 27.1 (drop BLDP)**, but **on tune it points the wrong way (−8.3)**.

## 1. The concentration problem, measured

Source: `analysis/data/run_state/disaster-profile-test/premise.json`, `extra_counts.txt`.

| | with PARA (prompt as specified) | without PARA |
|---|---|---|
| bearish calls graded | 187 | 177 |
| T1 worst quartile: calls, mean return | 46, −61.3% | 44, −51.1% |
| T1 distinct companies | 21 | 21 |
| T1 from the top three companies | 19 (PARA 8, SUNW 6, SEDG 5) | 15 (the three largest suppliers give 6, 5 and 4 calls) |
| T1 dated 2023–2025 | 40 of 46 | 37 of 44 |
| T1 split, train / tune | 33 / 13 | 28 / 16 |
| T2 (lagged by more than 25%) | 50 calls | 42 calls |

**The period effect is real but not selective.** Bearish calls in 2023–2025 numbered 138 of the 187, and 40 of them (29.0%) were T1 disasters, against 6 of the 49 earlier calls (12.2%). Most of the analyst's bearish calls came in those years, so "the disasters are recent" mostly restates "the calls are recent."

**Stratum S4 is a two-company story.** All **8** bearish calls in the failures stratum came from **FRC and SUNW**, and **all 8 were disasters**. Among the other 179 bearish calls, 38 (21.2%) were disasters. Tune has **zero** S4 bearish calls, so the S4 feature cannot be tested on tune at all.

## 2. Controls first

| feature | separates on train (T1 & T2) | same direction on tune | holds per company | both targets | **all four** |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | no | yes | yes | no | **no** |
| F9 prior-90d return below median (control) | no | yes | no | no | **no** |

**F8, year of the call (control).** T1 with PARA: train +15.9 [−5.8, +36.1], tune +15.8 [+2.7, +30.2]. It separates on tune, not on train (train range spans zero). Per company it points the same way on both splits with PARA included and does not without it. It fails the train test, so it is not a separating feature by the rule, though its sign agrees on both halves.

**F9, prior 90-day return (control).** T1: train +15.5 [−5.8, +33.3], tune +1.6 [−19.6, +21.2]. **Per company it points the wrong way on both splits** (−2.9 train, −4.3 tune). Stocks that had already fallen before the call were not more likely to become disasters once counted company by company. **This contradicts the pre-registered prediction that F9 would separate** and that a price filter would beat the analyst. It did not; it did nothing.

**F1, stratum (control).** T1: train +73.7 [+60.0, +86.6]. On tune: no calls in the bucket. See §1: two companies.

## 3. All nine features, all four conditions

A feature counts as separating only if, **for both targets**: it separates on train (difference above zero and the 95% range excludes zero); it points the same way on tune; and it holds per company (above zero on both splits, with the pooled per-company range excluding zero). The last column requires all three at once.

### As the prompt specified (PARA included)

| feature | separates on train (T1 & T2) | same direction on tune | holds per company | both targets | **all four** |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | no | yes | yes | no | **no** |
| F9 prior-90d return below median (control) | no | yes | no | no | **no** |
| F1 stratum S4 | yes | no | no | no | **no** |
| F2 thesisHealth Weakening/Broken | no | yes | no | no | **no** |
| F3 stumbleType Structural | yes | no | no | no | **no** |
| F4 mechanism impaired | no | no | no | no | **no** |
| F5 blind spots >= 1 | no | yes | no | no | **no** |
| F6 recommendedSize <= median | no | yes | no | no | **no** |
| F7 prior call also bearish | no | no | no | no | **no** |

### With PARA excluded

| feature | separates on train (T1 & T2) | same direction on tune | holds per company | both targets | **all four** |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | no | yes | no | no | **no** |
| F9 prior-90d return below median (control) | no | yes | no | no | **no** |
| F1 stratum S4 | yes | no | no | no | **no** |
| F2 thesisHealth Weakening/Broken | no | yes | no | no | **no** |
| F3 stumbleType Structural | yes | no | yes | no | **no** |
| F4 mechanism impaired | no | no | no | no | **no** |
| F5 blind spots >= 1 | no | yes | no | no | **no** |
| F6 recommendedSize <= median | no | yes | no | no | **no** |
| F7 prior call also bearish | no | no | no | no | **no** |

**No feature passes in either version.** Only two separate on train: F1 stratum (two companies, and untestable on tune) and F3 stumbleType Structural. Both fail on tune.

### The detail behind the table, T1 (worst quartile), PARA included

Difference = disaster rate in the flagged group minus the other group, in points. Source: `cells.jsonl`; both targets, both versions, per-company figures and ranges are all in that file.

| feature (flagged bucket) | train: flagged vs other, rate | **train diff** [range] | tune: flagged vs other, rate | **tune diff** | per company: train / tune / pooled range |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | 36% of 78 vs 20% of 25 | +15.9 [-5.8, +36.1] | 20% of 60 vs 4% of 24 | +15.8 | +13.8 / +9.7 / [+1.7, +23.4] |
| F9 prior-90d return below median (control) | 40% of 50 vs 24% of 53 | +15.5 [-5.8, +33.3] | 16% of 43 vs 15% of 41 | +1.6 | -2.9 / -4.3 / [-16.1, +8.3] |
| F1 stratum S4 | 100% of 8 vs 26% of 95 | +73.7 [+60.0, +86.6] | n/a | n/a (no calls in bucket) | +79.3 / n/a / [+76.0, +91.1] |
| F2 thesisHealth Weakening/Broken | 41% of 56 vs 21% of 47 | +19.8 [-4.6, +46.9] | 19% of 42 vs 12% of 42 | +7.1 | +13.2 / +1.7 / [-6.2, +23.2] |
| F3 stumbleType Structural | 55% of 31 vs 22% of 72 | +32.6 [+13.5, +50.5] | 8% of 12 vs 17% of 72 | -8.3 | +33.9 / -8.5 / [+2.7, +40.8] |
| F4 mechanism impaired | 42% of 55 vs 21% of 48 | +21.0 [-4.1, +48.0] | 7% of 30 vs 20% of 54 | -13.7 | +18.0 / -10.9 / [-8.5, +21.2] |
| F5 blind spots >= 1 | 38% of 8 vs 32% of 95 | +5.9 [-26.1, +49.0] | 40% of 5 vs 14% of 79 | +26.1 | +19.7 / +28.8 / [-4.3, +52.7] |
| F6 recommendedSize <= median | 32% of 72 vs 32% of 31 | -0.3 [-18.5, +19.0] | 17% of 42 vs 14% of 42 | +2.4 | -9.5 / -1.1 / [-16.8, +8.3] |
| F7 prior call also bearish | 40% of 45 vs 26% of 58 | +14.1 [-8.7, +40.4] | 15% of 33 vs 16% of 51 | -0.5 | +6.2 / -7.3 / [-9.4, +12.7] |

### T2 (lagged by more than 25%), PARA included

| feature (flagged bucket) | train: flagged vs other, rate | **train diff** [range] | tune: flagged vs other, rate | **tune diff** | per company: train / tune / pooled range |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | 38% of 78 vs 20% of 25 | +18.5 [-2.5, +38.5] | 23% of 60 vs 4% of 24 | +19.2 | +15.0 / +10.9 / [+2.5, +24.8] |
| F9 prior-90d return below median (control) | 44% of 50 vs 24% of 53 | +19.5 [-1.6, +36.2] | 21% of 43 vs 15% of 41 | +6.3 | -0.5 / -2.2 / [-14.0, +10.7] |
| F1 stratum S4 | 100% of 8 vs 28% of 95 | +71.6 [+57.0, +85.1] | n/a | n/a (no calls in bucket) | +78.1 / n/a / [+74.6, +90.2] |
| F2 thesisHealth Weakening/Broken | 45% of 56 vs 21% of 47 | +23.4 [-2.5, +50.2] | 21% of 42 vs 14% of 42 | +7.1 | +15.4 / +1.9 / [-4.8, +25.0] |
| F3 stumbleType Structural | 55% of 31 vs 25% of 72 | +29.8 [+11.5, +49.0] | 17% of 12 vs 18% of 72 | -1.4 | +30.4 / +11.0 / [+6.3, +46.5] |
| F4 mechanism impaired | 46% of 55 vs 21% of 48 | +24.6 [-2.2, +51.7] | 13% of 30 vs 20% of 54 | -7.0 | +20.3 / -7.9 / [-6.7, +24.5] |
| F5 blind spots >= 1 | 38% of 8 vs 34% of 95 | +3.8 [-26.4, +44.6] | 40% of 5 vs 16% of 79 | +23.5 | +18.3 / +27.7 / [-4.6, +51.0] |
| F6 recommendedSize <= median | 35% of 72 vs 32% of 31 | +2.5 [-15.4, +21.8] | 21% of 42 vs 14% of 42 | +7.1 | -7.4 / +0.4 / [-15.3, +9.7] |
| F7 prior call also bearish | 44% of 45 vs 26% of 58 | +18.6 [-5.5, +43.7] | 18% of 33 vs 18% of 51 | +0.5 | +9.3 / -6.8 / [-7.7, +15.0] |

### T1, PARA excluded

| feature (flagged bucket) | train: flagged vs other, rate | **train diff** [range] | tune: flagged vs other, rate | **tune diff** | per company: train / tune / pooled range |
|---|---|---|---|---|---|
| F8 year >= 2023 (control) | 34% of 68 vs 20% of 25 | +13.8 [-4.7, +31.7] | 23% of 60 vs 8% of 24 | +15.0 | +15.0 / +4.7 / [-2.5, +22.2] |
| F9 prior-90d return below median (control) | 36% of 45 vs 25% of 48 | +10.6 [-9.6, +27.3] | 21% of 43 vs 17% of 41 | +3.9 | -7.9 / -3.8 / [-19.4, +7.1] |
| F1 stratum S4 | 100% of 8 vs 24% of 85 | +76.5 [+65.5, +86.7] | n/a | n/a (no calls in bucket) | +78.4 / n/a / [+74.6, +90.2] |
| F2 thesisHealth Weakening/Broken | 37% of 46 vs 23% of 47 | +13.6 [-10.7, +41.2] | 21% of 42 vs 17% of 42 | +4.8 | +10.6 / -2.1 / [-10.5, +20.4] |
| F3 stumbleType Structural | 48% of 23 vs 24% of 70 | +23.5 [+5.6, +48.3] | 17% of 12 vs 19% of 72 | -2.8 | +29.2 / +9.2 / [+2.5, +47.0] |
| F4 mechanism impaired | 40% of 45 vs 21% of 48 | +19.2 [-7.8, +49.6] | 13% of 30 vs 22% of 54 | -8.9 | +25.3 / -9.7 / [-6.9, +27.3] |
| F5 blind spots >= 1 | 29% of 7 vs 30% of 86 | -1.7 [-34.5, +43.9] | 40% of 5 vs 18% of 79 | +22.3 | +7.1 / +27.1 / [-13.3, +47.5] |
| F6 recommendedSize <= median | 31% of 65 vs 29% of 28 | +2.2 [-18.1, +20.2] | 24% of 42 vs 14% of 42 | +9.5 | -8.5 / +1.6 / [-15.3, +9.5] |
| F7 prior call also bearish | 33% of 36 vs 28% of 57 | +5.3 [-11.9, +26.3] | 18% of 33 vs 20% of 51 | -1.4 | +3.2 / -8.6 / [-12.3, +9.9] |

## 4. The leave-one-company-out check

Source: `loco.json`. The T1 cut is held fixed while a company is dropped, so removing a company does not move the target.

| feature | version | full-sample difference, pooled T1 | lowest when one company is dropped | highest |
|---|---|---|---|---|
| F1 stratum S4 (strongest overall) | with PARA | +78.8 | +78.0 (drop INTC) | +82.2 (drop PARA) |
| | without PARA | +78.7 | +77.8 (drop INTC) | +80.6 (drop SEDG) |
| F3 Structural (strongest analyst field) | with PARA | +22.4 | +16.0 (drop PARA) | +27.1 (drop BLDP) |
| | without PARA | +15.3 | +11.3 (drop DOW) | +21.2 (drop BLDP) |

**Neither result collapses when one company is dropped, and that is the wrong reassurance.** Dropping a single company cannot test a result that rests on two: S4's whole effect comes from FRC and SUNW together, and dropping either one leaves the other's calls, every one of which was a disaster. Nor does a pooled figure show F3's problem: **it is train that carries it.** Train +32.6 [+13.5, +50.5], tune −8.3 [−19.7, +3.5]. A pooled range hides the flip between halves, which is exactly what the earlier ranking test found for five of its six fields.

## 5. Findings

**1. Nothing separates the disasters, with or without PARA.** The pre-registered "falsified if" condition is met: no feature separates on both targets, both splits and per company. The disasters are not identifiable from any of these nine things known at the call.

**2. Two features separate on train, and both fail on tune.** F1 (S4) fails for lack of data (0 tune calls). F3 (Structural) reverses: +32.6 on train, −8.3 on tune. Without PARA, F3 holds per company but its tune sign is still negative at the call level (−2.8). With PARA included, the two targets disagree on tune at the company level (T1 −8.5, T2 +11.0). **The prompt says that when the targets disagree, trust neither.**

**3. The analyst's own severity fields do not sort disasters.** F2 (thesisHealth Weakening/Broken) is +19.8 on train with a range spanning zero, +7.1 on tune. F4 (mechanism impaired) is +21.0 on train and −13.7 on tune with a range excluding zero: it reverses. F5 (blind spots) and F6 (size) have ranges wider than the effects. This matches the earlier ranking test's finding for hits; it now also holds for magnitude.

**4. F7, the pre-registered bet, does not separate.** Prior call also bearish: T1 train +14.1 [−8.7, +40.4], tune −0.5. Per company +6.2 on train, −7.3 on tune. History did not add information.

**5. The price filter did not beat the analyst; it did nothing.** F9 (already falling) does not separate, and per company it points the wrong way on both splits. Whatever gets a stock into the worst quartile, it is not visible in the previous quarter's move.

**6. Tune has too few disasters to confirm anything.** 13 T1 disasters (16 without PARA) among 84 calls. Only large, consistent effects could be told apart from noise there. F8 is the only feature whose tune range excludes zero in the predicted direction on both targets (F4's excludes zero in the wrong direction).

## 6. What it means for a decision

- **If a feature survived everything:** none did. There is no basis for a size-aware trim rule keyed on any of the nine.
- **If only the controls separated:** the closest to this is F1 and F8. Those disasters are a **period-and-failures artifact**: two companies from the failures stratum (FRC and SUNW, 8 of 8 calls) and the fact that 138 of the 187 bearish calls fell in 2023–2025. The analyst's own fields add nothing to spotting them.
- **If nothing separates:** this is the answer. **The bearish signal cannot be graded by severity from these fields and would have to be acted on as a whole**, or not at all. Combined with the confirmation-rule test (a second bearish call does not clearly help either), the available evidence is for treating a bearish call as one undifferentiated signal.

**One thing that should change regardless:** PARA's corrupt price series inflated the "disasters" this test was designed around. The prompt's own count of 46 and mean of −61.5% rest on it in part.

## 7. Deviations and premises

1. **PARA's price series is corrupt** (top of report). Not in the prompt. I report both versions and did not choose one as the headline; the sentence above uses the prompt's figures (with PARA) and the without-PARA figures are alongside.
2. **The prompt says the worst quartile averaged −61.5%.** I get −61.3% with the same 187 calls and the same 46, from the same rules. The counts (46, 21 companies, 19 from PARA/SUNW/SEDG, 40 in 2023–2025, 33 train and 13 tune) reproduce exactly.
3. **Every feature's binary bucket, direction and threshold was fixed by me** in the pre-registration before any table was computed: the prompt names the nine features but not the cut points. F6 and F9 use the pooled median of the *feature* (not the outcome). Other cut points could give different answers; I did not try them.
4. **"Separates on tune" is a sign test only,** because 84 calls cannot carry a range test. That is more lenient than on train, and no feature passed even so.
5. **The "both targets" column overlaps the first three:** each of those already requires both targets. The last column checks that one feature satisfies all three on both targets jointly.
6. **F9's window ends at the last close strictly before the call date,** not the call-date close, so that it is knowable at the call and excludes an announcement move.
7. **Leave-one-out was run for two features** (the strongest overall, F1, and the strongest analyst field, F3), not for all nine.
8. **Version guard skipped:** no scoring calls.

## 8. Verification

- Population and concentration figures re-derived and match the prompt (except −61.3% vs −61.5%).
- Pre-registration committed before any table (see `git log`).
- WOLF and SPWR excluded entirely; holdout not read; alias-resolved names come through the eval directories.
- All entry, exit and prior-return prices use the corpus_v2 cache.
- Not verified: a corrected PARA series, or cut points other than the pre-registered ones.

## 9. Follow-up commands

```
python3 analysis/disaster_profile_driver.py premise
python3 analysis/disaster_profile_driver.py run
python3 analysis/disaster_profile_driver.py loco
cat analysis/data/run_state/disaster-profile-test/run_output.txt
```

Provenance: `analysis/data/run_state/disaster-profile-test/cells.jsonl` (keys `label`, `feature`, `detail.<T1|T2>.<train|tune|pooled>.call_diff`, `call_ci`, `company_diff`, `conditions`); `premise.json`; `loco.json`; `extra_counts.txt`; analyst fields from `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`; prices `analysis/data/corpus_v2/scorer_price_cache_v1.json`; bootstrap seed 11, 2,000 redraws.
