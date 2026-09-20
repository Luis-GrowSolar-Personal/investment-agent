# R4b — the entry price: R4's steep short-horizon shape was mostly the announcement move

**Run:** `r4b-tradeable-entry` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0.** No model calls, no API spend, no DB writes, no cache refresh, holdout untouched, `analysis/analyst_direct_scorer.py` unmodified.
**Status: complete.** All 40 sweep cells (10 horizons × 2 arms × train and tune), 20 paired-difference cells, and 120 timing-split plus 60 timing-difference cells computed. Reproduction gate passed before anything else.

## §0 Defined terms

- **Horizon.** How many days after the call we look at the stock's return before deciding whether the call was right.
- **Entry price.** The price the return is measured *from*.
- **Arm A (as-is).** Entry price is the close on the call date. This is what the project has always done.
- **Arm B (tradeable).** Entry price is the close on the first trading day *after* the call date, the earliest price a reader of the transcript could reach. The end price is the same in both arms, so B's window is **one trading day shorter**. I did not correct for that, as the prompt directs; it changes what B measures a little, at short horizons a lot (§3, finding 1).
- **The announcement gap.** The move a stock makes when earnings come out. If the company reports after the close on day D, the close on D is the *pre-announcement* price, and arm A's return includes that move. If it reports before the open on day D, the close on D is already post-announcement.
- **Tradeable.** A signal you could have acted on with information you had at the time.
- **Gap-on-D / gap-on-D+1.** My inference of when the announcement landed, from the stock's own moves: *gap on D* means the big move came on the call date (so arm A already starts after the announcement); *gap on D+1* means the big move came the next day (so arm A includes it). *Ambiguous* means neither dominates. Threshold, fixed before computing: one day's benchmark-relative move at least 2× the other's and at least 2 points in size.
- **Dead band.** A stock within 5 points of the S&P over the horizon counts as "went sideways," i.e. the right answer was Hold.
- **Hit.** The call matched what happened.
- **Base rate.** How often that outcome happened across *all* calls, whatever the analyst said. It moves with the horizon and with the arm, so **every edge below uses the base rate of its own arm and horizon.**
- **Edge.** Hit rate minus base rate, in points. Example: at 182 days, arm A, train: 62 of 103 bearish calls were right (60.2%) and 44.9% of *all* calls lagged, so the edge is +15.3.
- **Ticker-block bootstrap.** To get a 95% range I redraw the set of companies 2,000 times with replacement and recompute the figure each time (seed 11). Whole companies are redrawn, not single calls, because one company's calls are not independent of each other. For differences between arms I redraw the same companies in both arms (a *paired* range).

## Lead-with sentence

Measured the way this project has always measured it, v6's bearish calls beat the base rate by 13.3 points at 182 days (both splits pooled) and by 23.2 points at 30 days on train. Measured from the first price a transcript reader could actually have traded, those become **10.6** (pooled; train 14.5, tune 6.0) and **18.7** (train). The difference is the announcement move, which is **9.2 to 14.4 points at 1 to 3 days, 5.5 at 30 days and 2.7 at 182 days** (pooled). Of the calls, **27.3%** appear to have announced after the close, which is the group where the old measurement included the gap. **A further 41.7% are ambiguous** and cannot be assigned.

## 1. The reproduction gate passed

Arm A was recomputed by an independent implementation inside the new driver and compared against R4's stored 3×3 count matrices. It matched **exactly** in all eight cells checked (train and tune at 30, 60, 90, 182 days), a stricter test than the rounded figures the prompt names. Pooled 182-day edges: bullish +4.4, bearish +13.3, neutral 0.0. Source: `analysis/data/run_state/r4b-tradeable-entry/gate.json`.

## 2. The two-arm table

Bearish calls, edge in points. Brackets are 95% ticker-block ranges. **A−B** is the announcement move, with a paired range. Train has 103 bearish calls, tune 84. Every cell had all 1,236 (train) or 1,168 (tune) calls gradable. Source: `cells.jsonl` (`kind=sweep`, `kind=diff`); printed in `sweep_tables.txt`.

### Train (56 companies)

| horizon | base rate lag, A / B | A edge | B edge | **A − B** [paired range] | bullish edge A / B | neutral edge A / B |
|---|---|---|---|---|---|---|
| 1 day | 9.0 / 0.0 | +15.3 [5.8, 25.1] | 0.0 (zero-length window) | +15.3 [5.8, 25.1] | +4.6 / 0.0 | +2.3 / 0.0 |
| 2 days | 9.7 / 2.3 | +14.6 [4.5, 25.3] | +2.5 [−0.7, 6.6] | +12.1 [0.8, 23.4] | +3.5 / −0.5 | +1.6 / +0.6 |
| 3 days | 11.1 / 3.6 | +15.1 [3.7, 25.4] | +4.2 [−0.5, 8.8] | +10.9 [0.3, 21.9] | +3.6 / −0.5 | +2.1 / +0.5 |
| 5 days | 13.0 / 5.5 | +20.0 [8.4, 29.5] | +8.1 [1.4, 14.6] | +11.9 [0.7, 22.2] | +3.7 / −0.3 | +2.2 / +0.6 |
| 10 days | 18.6 / 12.9 | +26.1 [15.6, 35.5] | +16.2 [5.5, 26.4] | +9.9 [2.0, 19.1] | +5.0 / +0.6 | +4.4 / +2.7 |
| 21 days | 23.6 / 20.3 | +23.0 [13.4, 31.1] | +16.6 [8.1, 24.8] | +6.4 [−1.8, 14.9] | +4.5 / +0.8 | +3.7 / +1.1 |
| 30 days | 26.3 / 25.0 | +23.2 [13.5, 32.4] | +18.7 [10.6, 26.7] | +4.5 [−1.9, 11.4] | +6.0 / +1.8 | +4.0 / +3.3 |
| 60 days | 35.2 / 34.7 | +20.1 [10.2, 30.4] | +13.8 [2.1, 25.6] | +6.3 [0.6, 13.0] | +5.6 / +2.6 | +2.8 / +2.3 |
| 90 days | 39.2 / 37.7 | +20.0 [9.8, 30.6] | +17.6 [6.8, 29.0] | +2.3 [−3.6, 7.9] | +3.1 / +2.2 | −0.3 / 0.0 |
| 182 days | 44.9 / 45.7 | +15.3 [3.0, 26.0] | +14.5 [1.8, 26.5] | +0.8 [−4.1, 5.7] | +3.6 / +1.7 | −0.1 / −0.2 |

### Tune (51 companies with gradable calls)

| horizon | base rate lag, A / B | A edge | B edge | **A − B** [paired range] | bullish edge A / B | neutral edge A / B |
|---|---|---|---|---|---|---|
| 1 day | 9.2 / 0.0 | +13.4 [2.1, 27.2] | 0.0 (zero-length window) | +13.4 [2.1, 27.2] | +4.8 / 0.0 | +3.9 / 0.0 |
| 2 days | 10.6 / 2.1 | +12.0 [0.6, 25.5] | +6.2 [−1.3, 14.8] | +5.8 [−2.6, 14.8] | +4.7 / +0.3 | +4.1 / +2.1 |
| 3 days | 11.6 / 2.3 | +13.4 [2.5, 26.8] | +4.8 [−1.8, 13.3] | +8.5 [0.6, 17.2] | +4.0 / −0.2 | +3.8 / +1.9 |
| 5 days | 12.9 / 4.5 | +12.1 [1.7, 24.9] | +6.3 [−0.7, 14.3] | +5.8 [−2.1, 14.2] | +2.8 / 0.0 | +3.0 / +1.6 |
| 10 days | 17.8 / 11.1 | +9.6 [−1.3, 22.3] | +9.1 [−1.2, 19.1] | +0.5 [−8.4, 9.5] | +2.8 / +0.8 | +3.0 / +3.0 |
| 21 days | 24.2 / 20.7 | +9.1 [−1.0, 19.9] | +3.1 [−5.4, 12.7] | +6.0 [−3.1, 14.0] | +5.3 / +2.0 | +3.6 / +2.5 |
| 30 days | 28.3 / 23.5 | +7.4 [−4.2, 19.3] | +0.3 [−9.5, 10.3] | +7.1 [−0.2, 14.4] | +2.7 / +0.1 | +1.7 / +1.2 |
| 60 days | 36.0 / 33.9 | +8.1 [−2.9, 18.9] | +7.8 [−2.5, 17.5] | +0.3 [−7.4, 9.3] | +4.4 / +1.0 | +1.9 / +0.3 |
| 90 days | 40.5 / 41.4 | +9.5 [−1.7, 20.7] | +6.3 [−5.7, 16.8] | +3.2 [−3.5, 11.0] | +6.9 / +5.1 | +1.4 / +0.8 |
| 182 days | 48.4 / 47.5 | +11.2 [−1.7, 22.2] | +6.0 [−6.7, 17.3] | +5.1 [−1.2, 12.0] | +5.2 / +4.2 | +0.1 / 0.0 |

### Pooled train + tune, for reference only (no ranges; train discovers, tune confirms)

| horizon | A: hit / base / edge | B: hit / base / edge | A − B | bullish edge A / B |
|---|---|---|---|---|
| 1 | 23.5 / 9.1 / +14.4 | 0.0 / 0.0 / 0.0 | +14.4 | +4.7 / 0.0 |
| 2 | 23.5 / 10.1 / +13.4 | 6.4 / 2.2 / +4.2 | +9.2 | +4.0 / −0.1 |
| 3 | 25.7 / 11.4 / +14.3 | 7.5 / 3.0 / +4.5 | +9.8 | +3.8 / −0.3 |
| 5 | 29.4 / 13.0 / +16.4 | 12.3 / 5.0 / +7.3 | +9.1 | +3.3 / −0.2 |
| 10 | 36.9 / 18.2 / +18.7 | 25.1 / 12.1 / +13.1 | +5.6 | +3.9 / +0.7 |
| 21 | 40.6 / 23.9 / +16.7 | 31.0 / 20.5 / +10.5 | +6.2 | +4.9 / +1.4 |
| 30 | 43.3 / 27.3 / +16.0 | 34.8 / 24.3 / +10.5 | +5.5 | +4.4 / +1.0 |
| 60 | 50.3 / 35.6 / +14.7 | 45.5 / 34.3 / +11.1 | +3.6 | +5.0 / +1.8 |
| 90 | 55.1 / 39.9 / +15.2 | 51.9 / 39.5 / +12.4 | +2.8 | +4.9 / +3.6 |
| 182 | 59.9 / 46.6 / +13.3 | 57.2 / 46.6 / +10.6 | +2.7 | +4.4 / +2.9 |

## 3. Findings

**1. At 1 day, arm B is not a measurement.** Its start and end price are the same close, so every call lands in the sideways band and its edge is exactly 0.0 by construction. The 1-day A−B of +15.3 (train) and +13.4 (tune) is therefore the whole of arm A's 1-day edge, not a measured reaction. Read the 2-day row instead, where B's window is one trading day. A single trading day is also a large share of a two-day return, so B at 2–5 days is a very short and noisy window with base rates of 2–5%.

**2. The announcement move is large at short horizons and shrinks steadily.** On train, A−B is +12.1, +10.9 and +11.9 at 2, 3, 5 days, +9.9 at 10 days, +4.5 at 30, +2.3 at 90 and **+0.8 at 182**. Pooled it is +9.2, +9.8, +9.1, +5.6, +5.5, +2.8, +2.7. The pre-registered primary prediction (large at 1–5 days, moderate at 30, near zero at 182) **holds on train and in the pooled figures.** On tune the direction agrees but only 3 days is distinguishable from zero.

**3. R4's steep short-horizon shape was mostly this move, but its level was not.** Arm A's train edge climbs from +15.3 at 1 day to **+26.1 at 10 days**, then falls to +15.3 at 182. That rise-then-fall is the shape R4 reported. In arm B, train is +16.2, +16.6, +18.7, +13.8, +17.6, +14.5 from 10 days to 182: **roughly flat at 14 to 19 points.** The declining slope is gone. But **the level did not go away.** Train arm B at 30 days is **+18.7 (range 10.6 to 26.7)**, so the pre-registered consequence ("the +23.2 at 30 days shrinks materially") is **only partly met**: it fell by 4.5 points, not by more than half, and the paired range on that difference spans zero.

**4. Tune shows no arm-B edge at 30 days at all.** Arm B at 30 days on tune is +0.3 (range −9.5 to 10.3), against +18.7 on train. Every tune arm-B range spans zero at every horizon. This is the same train-versus-tune divergence R4 found, and it is **larger** in arm B (the two splits differ by 18.4 points at 30 days) than in arm A (15.8). Removing the announcement move did not reconcile the splits.

**5. The 182-day figure holds up on train and is uncertain on tune.** Train: A +15.3, B +14.5, difference +0.8 (range −4.1 to 5.7). Tune: A +11.2, B **+6.0**, difference +5.1 (range −1.2 to 12.0). By the pre-registered rule ("differ materially" = at least 5 points *and* a paired range excluding zero) the 182-day arms **agree** on both splits. But tune's point estimate for the tradeable edge is about half arm A's, and tune's arm-B range (−6.7 to 17.3) cannot exclude zero. Pooled: A +13.3, B +10.6. **The secondary prediction ("+13.3 is largely clean") is supported on train and not contradicted on tune, and the honest reading is that the tradeable 182-day edge is about +10 to +11 pooled, with wide ranges.**

**6. The bullish edge is nearly all announcement move at short horizons.** Pooled bullish edge in arm A is +3.3 to +5.0 at every horizon. In arm B it is 0.0 or negative through 5 days and only reaches +2.9 to +3.6 by 90 to 182 days. Whatever the analyst's Add calls capture on the announcement day, it is gone if you cannot trade until the next close.

**7. Arm B keeps something at 5 to 10 days on train; tune is the same sign but inconclusive.** Train arm B: +8.1 at 5 days (range 1.4 to 14.6) and +16.2 at 10 days (range 5.5 to 26.4). Tune: +6.3 and +9.1, both with ranges spanning zero. Pooled: +7.3 and +13.1. **This is what a post-announcement drift signal would look like, and it is the same sign on both splits, but only train excludes zero, so it is not shown.** Caution: the base rate at 5 days is 5.5% (train, arm B). A 13.6% hit rate against that is 14 correct calls out of 103, from a small number of tickers.

## 4. The call-timing diagnostic

Per call: benchmark-relative move on the call date (previous close to close D) and the next day (close D to close D+1), 2,404 calls, source `call_timing.csv`. Classification rule fixed before computing (2× and 2 points). **4 calls were unclassifiable** (missing price legs).

| rule | gap on D (arm A already post-announcement) | gap on D+1 (arm A includes the gap) | ambiguous |
|---|---|---|---|
| **registered: ratio 2×, minimum 2 points** | 744 (30.9%) | **657 (27.3%)** | 1,003 (41.7%) |
| minimum 1 point | 847 (35.2%) | 749 (31.1%) | 808 (33.6%) |
| minimum 4 points | 459 (19.1%) | 456 (18.9%) | 1,489 (61.8%) |
| ratio 1× (whichever is larger), 2 points | 986 (40.9%) | 822 (34.1%) | 596 (24.8%) |
| ratio 4×, 2 points | 450 (18.7%) | 442 (18.4%) | 1,512 (62.8%) |

Source: `timing_sensitivity.json`. **The share classed as after-close ranges from 18.4% to 34.1% depending on the rule, and the share classed as on-the-day from 18.7% to 40.9%.** The two are close to equal at every rule. **Nothing in these figures lets me say most calls are after the close; the data supports "roughly as many after the close as on the day, and a large unassignable middle."** The classification uses the stock's own price move, so it is a noisy proxy: a quiet announcement is "ambiguous" whatever time it landed.

### Bearish edge split by the classification (registered rule)

30 to 42 bearish calls per group per split. Every range is wide.

| group | horizon | train: A / B [paired A−B range] | tune: A / B [paired A−B range] |
|---|---|---|---|
| gap on D (30–42 bearish calls) | 3 days | +5.3 / −0.1 [−1.0, 12.6] | 0.0 / +2.3 [−4.0, −0.8] |
| | 30 days | +16.2 / +13.2 [−5.2, 13.2] | +2.4 / +5.3 [−10.3, 7.3] |
| | 182 days | +0.9 / +3.9 [−9.3, 2.1] | +6.2 / +5.3 [−0.5, 2.5] |
| **gap on D+1** (30 bearish calls each) | 1 day | **+38.6 / 0.0 [25.0, 57.3]** | **+26.7 / 0.0 [5.3, 47.3]** |
| | 3 days | +30.7 / +6.6 [−5.7, 44.9] | +28.2 / +5.2 [10.0, 39.6] |
| | 30 days | +15.8 / +5.5 [−10.6, 34.2] | +12.4 / −5.2 [5.0, 33.9] |
| | 90 days | +24.8 / +6.6 [7.2, 34.4] | +18.8 / +9.4 [−6.4, 29.2] |
| | 182 days | +15.9 / +5.6 [0.4, 17.1] | +21.2 / +7.9 [−5.3, 31.2] |
| ambiguous (25–31 bearish calls) | 30 days | +39.6 / +38.4 [−3.2, 8.3] | +5.2 / +2.4 [−12.4, 16.2] |
| | 182 days | +33.7 / +36.5 [−6.9, 1.2] | +5.9 / +6.3 [−2.0, 1.0] |

Source: `cells.jsonl` (`kind=timing_split`, `kind=timing_diff`).

**This is where the contamination is visible.** In the calls where the big move came on D+1, arm A's bearish edge is +38.6 (train) and +26.7 (tune) at 1 day, and arm B is zero, on both splits, with paired ranges that exclude zero on both. Where the big move came on D, arm A's short-horizon edge is near zero (+1.1 train and +2.9 tune at 1 day). **The entry-price effect is concentrated in exactly the group the mechanism predicts.** It also persists at long horizons within that group: at 182 days, A−B is +10.3 (train) and +13.3 (tune) for gap-on-D+1 calls, against roughly zero for gap-on-D, with the caveat that each group has only 30 bearish calls.

**A caution on interpreting the classification.** It uses the day-D and day-D+1 stock moves, and arm A's return contains one of them. Conditioning on "the big move came on D+1" therefore selects calls with a large D+1 move by construction. The table shows the analyst's bearish calls tend to sit on the *falling* side of such moves, which is what a post-close negative announcement would produce, but the classification cannot say whether the analyst read the news or the transcript. It says only that arm A cannot be traded.

## 5. What it means for a decision — three ways

**If the 182-day figure is clean and the short-horizon lift is mostly the gap** *(this is mostly what happened)*: the project's existing 182-day baselines stand on train (+15.3 vs +14.5), and on pooled data the tradeable 182-day edge is +10.6 against the measured +13.3. **R4's short-horizon result should be read as largely announcement-driven at 1 to 10 days, and its steep slope is not real.** Its train level at 10 to 30 days (+16 to +19 in arm B) is not explained by the entry price and is not confirmed on tune. R4's reading changes here; I have not retracted anything.

**If arm B keeps a real edge at 1–10 days:** it keeps a train edge (+8.1 at 5 days, +16.2 at 10 days, ranges excluding zero) that is not confirmed on tune (+6.3 and +9.1, ranges spanning zero). That is **a lead, not a finding.** It is the first look this project has taken at post-announcement drift. It would need its own pre-registered test on tune, with a proper entry rule.

**If arms A and B differ at 182 days:** by the pre-registered rule, they do not, on either split. On tune the point estimates are 11.2 and 6.0 and the difference range is −1.2 to +12.0. **Not established, not excluded.** It is a reason to state 182-day figures with the entry-price caveat, not a reason to re-audit every baseline.

**What did not change:** the scorer's `p0` rule, `PROMOTION_GATE.md`, any candidate, and the queue.

## 6. Deviations and premises

1. **Arm B is degenerate at 1 day** (finding 1). The prompt lists 1 day as a horizon; I computed it and report it, but it carries no information. The prompt did not anticipate this.
2. **"Strictly after the call date" is one trading day later, not the next open.** I used the close of the first trading day after the call date. A reader of a before-the-open call could trade that same morning; arm B is conservative for those calls and for the gap-on-D group in general. The prompt specifies this arm; I flag that it is stricter than "the earliest price you could reach" in that case.
3. **The prompt's threshold "e.g. one move at least twice the other and at least 2%"** was adopted as registered. It leaves 41.7% ambiguous, a lot. The sensitivity table shows the split moves substantially with the rule.
4. **"Materially differ" was defined by me** before computing (difference of at least 5 points and paired range excluding zero). It is not the prompt's. Under it, several short-horizon train cells qualify (2, 3, 5, 10, 60 days), and 60 days is one I did not predict.
5. **Date and time-zone caveat.** `call_date` is the vendor's conference date. A call on the evening of D in the U.S. may carry D+1 in the vendor's UTC-based date for some records; I did not check.
6. **The 4 unclassifiable calls** are excluded from the timing split only, not from the sweep.

## 7. Verification

- Arm A matches R4's stored matrices exactly in all eight gate cells; pooled 182 edges match the reference.
- Asserts inherited from R4's check: 1,240 train eval files across 56 companies, none in the holdout, WOLF and SPWR excluded.
- Every sweep cell was fully gradable (1,236 train, 1,168 tune), so no horizon silently dropped calls; 182 days is the longest horizon here.
- One numerical coincidence was checked and cleared: train arm A's bearish edge at 1 day and at 182 days are both +15.29, from completely different count matrices (25 of 103 hits vs 62 of 103).
- Scorer file unmodified (no diff).
- Not verified: an independent check of the day-D versus day-D+1 announcement timing against an earnings calendar. The classification is inferred from prices only.

## 8. Follow-up commands

```
python3 analysis/r4b_tradeable_entry_driver.py gate
python3 analysis/r4b_tradeable_entry_driver.py sweep
python3 analysis/r4b_tradeable_entry_driver.py timing
cat analysis/data/run_state/r4b-tradeable-entry/sweep_tables.txt
cat analysis/data/run_state/r4b-tradeable-entry/findings.md
```

Provenance: cells `analysis/data/run_state/r4b-tradeable-entry/cells.jsonl` (keys `kind`, `split`, `arm`, `horizon`, `cls`, `results.<direction>.edge_pts`, `results.ci95`, `paired_ci95_edge_diff`); per-call timing `call_timing.csv`; price cache `analysis/data/corpus_v2/scorer_price_cache_v1.json`; reference `wrap-ups/R4-grading-horizon-out.md`; bootstrap seed 11, 2,000 redraws.
