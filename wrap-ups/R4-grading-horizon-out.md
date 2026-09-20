# R4 — the grading horizon: v6's bearish edge is larger on train at short horizons and does not confirm on tune

**Run:** `r4-grading-horizon` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0.** No model calls, no API spend, no DB writes, no cache refresh, holdout untouched.
**Status: complete, not partial.** All 12 cells (6 horizons × train and tune) computed. The pre-registered 6c extensions were **not run**, because their pre-registered condition was not met (§4).

## §0 Defined terms

- **Horizon.** How many days after the call we look at the stock's return before deciding whether the call was right. The project has used 182 days.
- **Benchmark-relative return.** The stock's return minus the S&P 500's return (SPY) over the horizon.
- **Dead band.** A stock that lands within 5 points of the S&P over the horizon counts as "went sideways," i.e. the right answer was Hold. Kept at ±5 throughout.
- **Bearish / bullish / neutral call.** The analyst said Trim or Exit / Add / Hold.
- **Hit.** The call matched what happened: a bearish call on a stock that lagged the S&P by more than 5 points, and so on.
- **Base rate.** How often that outcome happened across *all* calls, whatever the analyst said. It moves with the horizon: over longer windows fewer stocks stay within ±5 points, so the "sideways" share shrinks and the lag and beat shares grow. **Every edge below is measured against the base rate at the same horizon.**
- **Edge.** Hit rate minus base rate, in points. Example: of 103 bearish calls on train at 182 days, 62 were right (60.2%), and 44.9% of *all* train calls lagged by more than 5 points, so the edge is +15.3 points.
- **Ticker-block bootstrap.** To get a 95% range, I redraw the whole set of companies 2,000 times, with replacement, and recompute the edge each time (seed 11). Whole companies are redrawn, not single calls, because one company's calls are not independent of each other. The range is where 95% of those redraws fall.
- **Overlapping windows.** At 270 and 365 days, a company's consecutive calls look at overlapping stretches of the same stock's history. That is the other reason ranges come from company-level redraws and not from a simple binomial.
- **Gradable.** A call with enough price history to be graded at that horizon.

## Lead-with sentence

Graded at the current 182 days, v6's bearish calls beat the base rate by 13.3 points (of 187 bearish calls across both splits, 112 were right). Across horizons from 30 days to 365, that edge ranged from **10.1 to 23.2 points on train** and from **4.7 to 11.2 points on tune**, largest at **30 days** on train. On tune the same sweep put the largest edge at **182 days**. The neutral-call edge was **near zero at 90 days and longer** on both splits, but **+4.0 (30 days) and +2.8 (60 days) on train**, so the pre-registered "zero at every horizon" holds only at 90 days and beyond.

**Verdict, per the pre-registration:** the bearish edge peaks at a short horizon on train and not on tune. **That is a negative result, not a partial success.** No horizon has been shown to be better than 182 days.

## 1. The reproduction gate passed

Before any other horizon, the 182-day cell was checked against the reference figures from `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`. Pooled train + tune, 2,404 graded calls:

| call | calls made | hit rate | base rate | edge | reference edge |
|---|---|---|---|---|---|
| bearish | 187 (7.8%) | 59.9% | 46.6% | +13.3 | +13.3 |
| bullish | 822 (34.2%) | 37.2% | 32.8% | +4.4 | +4.4 |
| neutral | 1,395 (58.0%) | 20.6% | 20.6% | 0.0 | 0.0 |

Exact match. Train alone also reproduces the state of play: 103 bearish calls, 60.2% right, 44.9% base rate; tune 84 calls, 59.5%, 48.4%.

## 2. The full sweep

Source for every row: `analysis/data/run_state/r4-grading-horizon/cells.jsonl` → `results` (also printed to `sweep_tables.txt`). Edge = hit rate minus base rate at the same horizon, in points. Brackets are 95% ticker-block ranges. Price cache: `analysis/data/corpus_v2/scorer_price_cache_v1.json`. Benchmark SPY, dead band ±5.

### Train (56 companies)

| horizon | graded | base rate: beat / lag / sideways | bearish: calls, hit rate | **bearish edge** | bullish edge | neutral edge | gap over luck |
|---|---|---|---|---|---|---|---|
| 30 days | 1,236 of 1,240 | 23.5 / 26.3 / 50.2 | 103, 49.5% | **+23.2** [13.5, 32.4] | +5.9 [2.5, 9.2] | +4.0 [0.6, 7.2] | +6.27 |
| 60 days | 1,236 | 28.1 / 35.2 / 36.7 | 103, 55.3% | **+20.2** [10.2, 30.4] | +5.6 [2.2, 9.0] | +2.8 [0.1, 5.6] | +5.21 |
| 90 days | 1,236 | 29.9 / 39.2 / 30.9 | 103, 59.2% | **+20.0** [9.8, 30.6] | +3.1 [−0.4, 6.7] | −0.3 [−2.6, 2.2] | +2.58 |
| 182 days | 1,236 | 32.8 / 44.9 / 22.2 | 103, 60.2% | **+15.3** [3.0, 26.0] | +3.6 [−0.4, 7.6] | −0.1 [−2.2, 2.1] | +2.48 |
| 270 days | 1,236 | 34.6 / 49.7 / 15.7 | 103, 60.2% | **+10.5** [−2.8, 22.4] | +3.5 [−0.9, 7.6] | 0.0 [−1.6, 1.5] | +2.07 |
| 365 days | 1,181 of 1,240 | 34.5 / 50.7 / 14.8 | 102, 60.8% | **+10.1** [−3.2, 23.8] | +2.6 [−2.0, 7.2] | −1.2 [−2.8, 0.3] | +1.01 |

### Tune (51 companies with gradable calls)

| horizon | graded | base rate: beat / lag / sideways | bearish: calls, hit rate | **bearish edge** | bullish edge | neutral edge | gap over luck |
|---|---|---|---|---|---|---|---|
| 30 days | 1,168 of 1,168 | 22.5 / 28.3 / 49.1 | 84, 35.7% | **+7.4** [−4.2, 19.3] | +2.7 [−0.8, 5.9] | +1.7 [−1.3, 4.6] | +2.41 |
| 60 days | 1,168 | 28.1 / 36.0 / 36.0 | 84, 44.0% | **+8.1** [−2.9, 18.9] | +4.4 [1.1, 7.6] | +1.9 [−0.4, 4.0] | +3.19 |
| 90 days | 1,168 | 29.4 / 40.5 / 30.1 | 84, 50.0% | **+9.5** [−1.7, 20.7] | +6.9 [3.2, 10.7] | +1.5 [−0.8, 3.7] | +3.88 |
| 182 days | 1,168 | 32.8 / 48.4 / 18.8 | 84, 59.5% | **+11.2** [−1.7, 22.2] | +5.2 [0.7, 9.8] | +0.1 [−1.7, 1.9] | +2.64 |
| 270 days | 1,168 | 33.2 / 51.5 / 15.2 | 84, 58.3% | **+6.8** [−5.7, 18.0] | +5.6 [0.6, 10.0] | 0.0 [−1.8, 1.8] | +2.41 |
| 365 days | 1,117 of 1,168 | 32.9 / 56.0 / 11.0 | 79, 60.8% | **+4.7** [−8.7, 16.5] | +5.5 [−0.1, 10.6] | +0.2 [−2.0, 2.0] | +2.30 |

Calls made are the same at every horizon except 365 days, because the analyst's answers do not change; only the yardstick does. Tune's 1,168 excludes WOLF and SPWR (38 files) and matches the state of play.

### Pooled train + tune, for reference only (no ranges; train discovers, tune confirms)

| horizon | graded | base rate: beat / lag / sideways | bearish: calls, hit | bearish edge | bullish edge | neutral edge |
|---|---|---|---|---|---|---|
| 30 | 2,404 | 23.0 / 27.3 / 49.7 | 187, 43.3% | +16.0 | +4.4 | +2.8 |
| 60 | 2,404 | 28.1 / 35.6 / 36.4 | 187, 50.3% | +14.7 | +5.0 | +2.4 |
| 90 | 2,404 | 29.6 / 39.9 / 30.5 | 187, 55.1% | +15.2 | +4.9 | +0.6 |
| 182 | 2,404 | 32.8 / 46.6 / 20.6 | 187, 59.9% | +13.3 | +4.4 | 0.0 |
| 270 | 2,404 | 33.9 / 50.6 / 15.5 | 187, 59.4% | +8.8 | +4.5 | 0.0 |
| 365 | 2,298 | 33.7 / 53.3 / 13.0 | 181, 60.8% | +7.5 | +4.0 | −0.6 |

## 3. Findings

**1. On train the bearish edge falls steadily as the horizon lengthens.** It is +23.2 points at 30 days and +10.1 at 365, in every step the same direction. The best horizon on train is 30 days, so the pre-registered primary prediction ("largest at a shorter horizon than 182, most likely 60–90") is right about the direction and wrong about the horizon on this split. The 30-, 60- and 90-day ranges all exclude zero. The 270- and 365-day ranges do not.

**2. Tune does not show this.** Tune's bearish edge is +7.4, +8.1, +9.5 at 30, 60, 90 days, then **+11.2 at 182 days**, its largest, then +6.8 and +4.7. Every one of its six ranges spans zero. At 30 days the analyst's 84 bearish calls on tune were right 35.7% of the time, against 28.3% for the base rate. On train the same horizon was 49.5% against 26.3%. **The train-to-tune difference in bearish edge at 30 days is 15.8 points** (23.2 vs 7.4), against 4.1 points at 182 days (15.3 vs 11.2). Under the pre-registration a short-horizon peak on train that does not appear on tune is **a negative result**. It has not been shown that any horizon beats 182 days.

**3. The neutral edge is not zero at short horizons on train.** At 30 days it is +4.0 (range 0.6 to 7.2) on 708 neutral calls, and +2.8 at 60 days (range 0.1 to 5.6). From 90 days on it is zero within the ranges on both splits. On tune it is +1.5 to +1.9 at 30–90 days with ranges spanning zero. **This partly contradicts the secondary prediction.** It is small, it barely clears zero on train, and it does not replicate on tune. It is reported as a finding and not treated as a result.

**3b. Why the neutral edge appears at short horizons at all** is a base-rate effect worth stating: at 30 days half of all calls (50.2% on train) land inside the dead band, so a Hold is right half the time by construction. The analyst says Hold on 58% of calls, so a small positive edge there is a small excess over a large base.

**4. The bullish edge is positive at every horizon on both splits,** between +2.6 and +6.9 points, with ranges that exclude zero in about half the cells. It is the steadiest signal in the table and it does not depend on the horizon. It matches the +4.4 the state of play already reports.

**5. The gap over luck falls with horizon on train** (+6.27 at 30 days to +1.01 at 365) and is flat on tune (+2.3 to +3.9, peaking at 90 days). At 30 and 60 days on train the gap's range excludes zero (2.97 to 9.26 at 30 days), the only train cells where it does. Tune's gap range excludes zero at 60, 90 and 182 days.

**6. Pooled figures look like a stronger result than they are.** Pooled, the bearish edge is largest at 30 days (+16.0) and smallest at 365 (+7.5). That is train's shape, carried by train's 103 calls with tune's flatter shape averaged in. Pooling is shown for reference only. It is the "train discovers, tune confirms" rule that decides, and the rule says not confirmed.

## 4. The pre-registered conditional step was not run

`findings.md` defined, before any cell was computed, that 6c (re-running Q2's axis test and P3a's 5d at the best horizon) would run only if the bearish edge varied by more than 10 points across horizons on train **and** the best horizon agreed on tune. The first holds (range 13.1 points on train). The second fails (train's best is 30 days, tune's is 182). **6c was not run.** Ranking those two re-tests before the sweep finished would have been the multiple-comparisons trap the prompt describes.

## 5. The 90-versus-182 inconsistency (reported whatever the sweep showed)

| file | `FORWARD_DAYS` |
|---|---|
| `analysis/analyst_direct_scorer.py:53` | 182 |
| `analysis/backtest_runner.py:85` | 90 |
| `analysis/backtest_from_files.py:71` | 90 |
| **`analysis/extract_db_baseline.py:50`** | **90** (not in the prompt's table; found by grep) |
| `analysis/corpus_construction_outcomes.py:35`, `_v2.py:37`, `_v3_terminal.py:35`, `corpus_fix6_driver.py:32` | 182 |

`PROMOTION_GATE.md` §3.1 (line 241) documents the 182-day choice: *"1Q is mostly noise; 4Q blurs attribution as later calls overlap."* That was asserted at drafting, not measured. **No file documents why the backtest and DB baseline use 90.** The two rulers are different, and the analyst is graded on one while the backtest measures on the other.

What this sweep says about the documented reasons: "1Q is mostly noise" is not supported on train, where the 90-day bearish edge is +20.0 with a range of 9.8 to 30.6, well above zero. It is also not contradicted on tune, where every bearish range spans zero at every horizon. "4Q blurs attribution" is consistent with the fall in bearish edge and gap at 270–365 days on train. The evidence does not favour changing the analyst scorer's 182-day default, and it does not show that 90 days is wrong for the backtest either. It shows the two figures are not comparable.

## 6. What it means for a decision — stated both ways

**If a shorter horizon really carries more edge:** the scorer's default would change, and Q2 and P3a would deserve a re-test at that horizon, because both closed against the 182-day ruler. **This run does not show that.** The evidence for it is one split.

**If the edge is flat across horizons:** it is not flat on train, so the strict version of that reading fails. What holds is a weaker statement: **no horizon has been shown to be better than 182 days on data the choice was not made on.** The horizon is therefore not established as the explanation for why mechanical features measure flat. That leaves the thin-signal reading in place, with less weight removed from it than the prompt's "removes the last free hypothesis" wording assumes, because train's short-horizon pattern remains unexplained.

**The honest summary is that nothing changes.** The scorer default stays 182. Q2 and P3a are not reopened. What has changed is one open question: **why does tune's 30-day bearish hit rate (35.7%) fall 14 points below train's (49.5%) when 182 days shows no such split (60.2% vs 59.5%)?** If the analyst's bearish calls are stronger on train companies at short horizons, that is a train/tune difference in the companies or the period and not a horizon effect. It is not investigated here.

## 7. Deviations and premises

1. **The prompt's inconsistency table missed a file.** `analysis/extract_db_baseline.py` also uses 90 days (§5).
2. **A bug in my resume logic** (`done_keys()` parsed cells.jsonl incorrectly once it existed) crashed the first tune command. It was fixed in its own commit; the grading code was untouched and the train cells were computed before it and reused. `driver_commit` therefore has two values; the train and tune cells were both produced by the same grading logic.
3. **The prompt's "1,168 tune" figure** matches after removing 38 WOLF/SPWR files from the 1,207 tune evals. Tune covers 53 companies on disk, 51 after exclusion. I did not re-derive the state of play's "51 of 54" beyond that.
4. **Version guard skipped:** no scoring calls are made, so no prompt hash is at stake.
5. **My definition of "materially varies"** for the 6c gate (train range above 10 points and best horizon agreeing on tune) was written into `findings.md` before computing. It is mine, not the prompt's.
6. **The ±5 dead band moves with the horizon in effect,** because a 5-point move is a much larger event at 30 days than at 365. The prompt says to vary one thing, so it was held fixed. A horizon-scaled band is a separate question and was not tested.

## 8. Verification

- 182-day pooled reproduction matches the reference to the tenth of a point (§1).
- Asserts: 1,240 train eval files across 56 companies, none in the holdout, all mapped through the alias table (`check.json`); tune files all in the tune split, none in the holdout.
- WOLF and SPWR excluded from every call (38 tune files).
- `ast.parse` on the driver. Scorer file unmodified (`git diff` clean for `analysis/analyst_direct_scorer.py`).
- Not verified: an independent re-grade by a second implementation.

## 9. Follow-up commands

```
# reproduce the sweep (free)
python3 analysis/r4_horizon_driver.py check
python3 analysis/r4_horizon_driver.py sweep train
python3 analysis/r4_horizon_driver.py sweep tune

# state and outputs
cat analysis/data/run_state/r4-grading-horizon/sweep_tables.txt
cat analysis/data/run_state/r4-grading-horizon/findings.md
```

Provenance: cells `analysis/data/run_state/r4-grading-horizon/cells.jsonl` (keys `split`, `horizon`, `results.<direction>.edge_pts`, `results.ci95`); reference figures `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`; price cache `analysis/data/corpus_v2/scorer_price_cache_v1.json`; bootstrap seed 11, 2,000 redraws.
