# P6B on tune: tests report ($0). Tune, WOLF/SPWR excluded. 1169 calls scored, 1169 with a 182-day tradeable-entry return, 51 companies.

## The four pre-registered conditions

1. **Rank-ordering: HELD.** Spearman 0.140, range 0.072 to 0.198 (train 0.130, 0.051-0.208; prediction 0.08-0.16), n=1169.
2. **Bearish coverage without precision loss: HELD.** B 161 bearish calls vs v6 84 = 1.92x (needs >= 1.5x); B precision 60.9% vs v6 59.5% = +1.3 points (needs >= -5). Base rate on these calls: 48.3%.
3. **Money: HELD.** Swap median at score <= -2 / >= +3: 8.34 points, range 1.46 to 12.88 (train at +2: 8.92, 4.12-15.34; prediction 6-12). Labelled train mapping (>= +2): 6.39, range -0.16 to 10.33.
4. **Old ruler, +3 mapping (non-gating): HELD.** B gap +4.07 vs v6 +2.64 (bar +0.21, the lower end of v6's own range).

**4 of 4 held. Pre-registered rule: falsified if any of 1-3 fails -> B HELD on tune.**

## Diagnostics: score buckets and rank-ordering

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| -4 | 4 | -8.28 | -7.47 | 50.0 | 50.0 |
| -3 | 16 | -4.57 | -7.24 | 31.2 | 50.0 |
| -2 | 141 | -7.89 | -5.74 | 27.7 | 54.6 |
| -1 | 178 | -7.20 | -3.42 | 27.0 | 53.9 |
| +1 | 175 | -6.12 | -4.32 | 31.4 | 54.3 |
| +2 | 413 | -2.50 | -0.57 | 32.7 | 44.3 |
| +3 | 228 | 0.53 | 3.68 | 39.0 | 39.5 |
| +4 | 14 | 2.41 | -1.16 | 42.9 | 28.6 |

**v6 (A) three buckets on the same calls:**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| bearish | 84 | -8.46 | -0.88 | 34.5 | 53.6 |
| neutral | 687 | -5.04 | -3.26 | 29.7 | 50.2 |
| bullish | 397 | -0.71 | 1.45 | 36.5 | 41.6 |

Spread (median score >= +3 minus median score <= -3): 5.20 points (range -14.85 to 36.94); n(>=+3)=242, n(<=-3)=20. v6 best-minus-worst 7.75 (range -5.51 to 10.94).

Post-hoc comparators (not pre-registered): v6's three answers coded -1/0/+1 give Spearman 0.080 (0.006 to 0.149); B minus v6, paired: +0.059 (+0.010 to +0.107).

## Diagnostics: neutral pile and noRead

Neutral share: v6 58.8%; B at the +3 mapping 65.5%; B at the train run's +2 mapping 30.2%. noRead share 0.0% (train: 0.2%).

## Diagnostics: old ruler at both mappings

| arm / mapping | n graded | accuracy % | luck % | gap (points) | bearish calls | bearish precision % | bullish calls | bullish precision % |
|---|---|---|---|---|---|---|---|---|
| v6 (A) | 1168 | 28.3 | 25.7 | +2.64 | 84 | 59.5 | 397 | 38.0 |
| B, +3 mapping (pre-registered) | 1169 | 29.9 | 25.8 | +4.07 | 161 | 60.9 | 242 | 41.3 |
| B, +2 mapping (train run's original) | 1169 | 33.4 | 30.7 | +2.62 | 161 | 60.9 | 655 | 36.2 |

**Noise arm (tune, v6 re-scored vs its cached call):** n=248, disagreement 44 (17.7%, Wilson 13.5 to 23.0).

| stratum | n | flips | rate % | Wilson |
|---|---|---|---|---|
| S1 | 76 | 17 | 22.4 | 14.5 to 32.9 |
| S2 | 46 | 5 | 10.9 | 4.7 to 23.0 |
| S3 | 107 | 21 | 19.6 | 13.2 to 28.1 |
| S5 | 19 | 1 | 5.3 | 0.9 to 24.6 |

Strata whose range excludes the overall rate: none.

**Cached vs fresh, graded noise flips (a flip where exactly one of the two calls matched the truth is decisive):**

| set | graded flips | cached call right | fresh call right | both wrong | sign-test p (cached vs fresh) |
|---|---|---|---|---|---|
| tune (this run) | 44 | 17 | 9 | 18 | 0.169 |
| train (P6 run) | 20 | 6 | 3 | 11 | 0.508 |
| pooled | 64 | 23 | 12 | 29 | 0.090 |

## Diagnostics: flips against v6, raw and net (P6 section 7 netting rule, tune noise arm)

| mapping | shared calls | raw flips | expected noise flips (S1-S5 re-weighted) | net | noise-count range | raw win rate % | noise win rate % | netted win rate |
|---|---|---|---|---|---|---|---|---|
| +3 (pre-registered) | 1168 | 341 | 207 | 134 | 158 to 268 | 32.0 (wins 109, losses 91, both wrong 141) | 20.5 | 49.8 (UNSTABLE, denominator too small -- not a headline) |
| +2 (train run's) | 1168 | 464 | 207 | 257 | 158 to 268 | 35.1 (wins 163, losses 104, both wrong 197) | 20.5 | 47.0 (UNSTABLE, denominator too small -- not a headline) |

Caveat (netting rule): noise flips and real flips are not disjoint; the subtraction assumes independence and no overlap.

## Diagnostics: B vs v6 disagreement (+3 mapping)

| v6 answer -> B answer | n | B right % | v6 right % | median return |
|---|---|---|---|---|
| bearish -> bearish | 58 | 63.8 | 63.8 | -9.02 |
| bearish -> neutral | 26 | 11.5 | 50.0 | -5.34 |
| neutral -> bearish | 98 | 58.2 | 13.3 | -5.78 |
| neutral -> neutral | 558 | 19.7 | 19.7 | -4.76 |
| neutral -> bullish | 31 | 22.6 | 22.6 | -5.84 |
| bullish -> bearish | 5 | 80.0 | 20.0 | -10.93 |
| bullish -> neutral | 181 | 21.0 | 31.5 | -3.29 |
| bullish -> bullish | 211 | 44.1 | 44.1 | 1.97 |

## Diagnostics: money (tradeable entry, 182 days, points vs S&P)

| mapping | arm | bearish share % | bearish mean | bearish median | bullish share % | bullish mean | bullish median | swap mean | swap median |
|---|---|---|---|---|---|---|---|---|---|
| v6 | A | 7.2 | -0.88 | -8.46 | 34.0 | 1.45 | -0.71 | 2.33 | 7.75 |
| +3 | B | 13.8 | -5.93 | -7.71 | 20.7 | 3.40 | 0.63 | 9.33 | 8.34 |
| +2 | B | 13.8 | -5.93 | -7.71 | 56.0 | 0.90 | -1.32 | 6.83 | 6.39 |

**By stratum (S1-S5) and year, +3 mapping vs v6:**

| slice | arm | n | bearish n | bearish median | bullish n | bullish median | swap median |
|---|---|---|---|---|---|---|---|
| S1 | A | 357 | 17 | -0.58 | 83 | -3.22 | -2.64 |
| S1 | B | 357 | 44 | -6.32 | 48 | -0.91 | 5.41 |
| S2 | A | 216 | 33 | 3.97 | 92 | -4.49 | -8.46 |
| S2 | B | 216 | 54 | -8.73 | 57 | -0.26 | 8.47 |
| S3 | A | 505 | 31 | -12.77 | 174 | -0.26 | 12.51 |
| S3 | B | 506 | 45 | -9.30 | 107 | 0.96 | 10.26 |
| S5 | A | 90 | 3 | -35.39 | 48 | 2.52 | 37.91 |
| S5 | B | 90 | 18 | -3.08 | 30 | 3.45 | 6.52 |
| 2020 | A | 165 | 3 | 16.20 | 52 | 3.37 | -12.83 |
| 2020 | B | 165 | 16 | 1.32 | 43 | 1.97 | 0.66 |
| ex-2020 | A | 1003 | 81 | -8.78 | 345 | -2.30 | 6.48 |
| ex-2020 | B | 1004 | 145 | -7.89 | 199 | 0.44 | 8.33 |

Median completion tokens: B 511; v6 (noise re-scores) 2462. Score distribution: -4: 4, -3: 16, -2: 141, -1: 178, +1: 175, +2: 413, +3: 228, +4: 14.

## Pooled train + tune

2386 calls (2386 with a tradeable-entry return) from 106 companies: train 1,217 (PARA excluded) + tune 1169. The state of play's 2,385 equals 1,217 + 1,168, the old-ruler-gradable tune count; this pool is one call larger because one tune call has a tradeable-entry return but no old-ruler truth.

| pooled figure | value | 95% range |
|---|---|---|
| B rank correlation (Spearman) | 0.135 | 0.087 to 0.184 |
| B swap median, score <= -2 / >= +3 | 10.50 | 6.30 to 13.64 |
| B swap median, score <= -2 / >= +2 (train run's mapping) | 8.12 | 4.19 to 11.19 |
| v6 swap median (state of play: +8.7) | 7.70 | 0.51 to 12.30 |
| v6 swap mean (state of play: +2.4) | 2.45 | -7.17 to 13.25 |
