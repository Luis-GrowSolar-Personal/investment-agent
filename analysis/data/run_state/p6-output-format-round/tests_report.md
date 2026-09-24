# P6 tests report ($0). Train, WOLF/SPWR/PARA excluded. 1217 calls, 1217 with a 182-day tradeable-entry return.

## 6.1 Rank-ordering (tradeable entry, 182 days, points vs S&P; ticker-block bootstrap 95% range)

**Arm A (v6), three buckets:**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| bearish | 93 | -9.46 | -2.22 | 31.2 | 57.0 |
| neutral | 703 | -3.10 | -0.12 | 32.4 | 46.4 |
| bullish | 421 | -1.33 | 0.31 | 34.7 | 41.1 |

A best-minus-worst (median bullish minus median bearish): 8.12 points (range -2.41 to 17.96).

**Arm B score buckets:**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| -5 | 1 | -102.80 | -102.80 | 0.0 | 100.0 |
| -4 | 2 | -33.86 | -33.86 | 50.0 | 50.0 |
| -3 | 27 | -10.39 | -14.71 | 25.9 | 63.0 |
| -2 | 161 | -10.08 | -3.74 | 29.8 | 60.2 |
| -1 | 183 | -5.35 | 4.56 | 32.8 | 50.8 |
| +0 noRead | 3 | -0.69 | 0.29 | 33.3 | 0.0 |
| +1 | 167 | -2.98 | -1.55 | 34.1 | 43.7 |
| +2 | 438 | -2.29 | -0.70 | 32.4 | 41.1 |
| +3 | 226 | 1.16 | 1.65 | 36.3 | 38.5 |
| +4 | 9 | 16.95 | 40.12 | 55.6 | 33.3 |

Arm B: Spearman rank correlation **0.130** (range 0.051 to 0.208), n=1217; excluding noRead 0.131 (0.052 to 0.208). Top-minus-bottom spread (median of score >= +3 minus median of score <= -3): **14.16** points (range -2.22 to 79.37; 2000/2000 valid draws); n(>=+3)=235, n(<=-3)=30.

**Arm C score buckets:**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| -4 | 1 | -102.80 | -102.80 | 0.0 | 100.0 |
| -3 | 1 | -77.75 | -77.75 | 0.0 | 100.0 |
| -2 | 42 | -18.72 | -22.02 | 19.0 | 69.0 |
| -1 | 51 | -9.46 | 7.81 | 35.3 | 54.9 |
| +0 noRead | 17 | -6.66 | -3.25 | 23.5 | 64.7 |
| +1 | 170 | -7.77 | -1.01 | 24.1 | 59.4 |
| +2 | 485 | -2.30 | 0.45 | 34.8 | 41.9 |
| +3 | 428 | 0.12 | 0.75 | 36.4 | 38.8 |
| +4 | 22 | -9.47 | 10.55 | 31.8 | 54.5 |

Arm C: Spearman rank correlation **0.140** (range 0.061 to 0.219), n=1217; excluding noRead 0.137 (0.056 to 0.217). Top-minus-bottom spread (median of score >= +3 minus median of score <= -3): **90.28** points (range 75.29 to 104.23; 1745/2000 valid draws); n(>=+3)=450, n(<=-3)=2.

## 6.2 The neutral pile

Base rates in this population (old ruler, arm-A entry, n=1217): bearish 44.7%, neutral 22.1%, bullish 33.2% (prompt reference: {'bearish': 46.6, 'bullish': 32.8, 'neutral': 20.6}).

- Arm B: neutral share 29.0% vs A 57.8%; of which noRead 0.2%, weak (+/-1) 28.8%, score 0 with a read 0.0% (n=1217).
- Arm C: neutral share 19.6% vs A 57.8%; of which noRead 1.4%, weak (+/-1) 18.2%, score 0 with a read 0.0% (n=1217).

- A neutral bucket: n=703, share of calls that really were neutral 22.0% vs base 22.1% -> edge -0.1.
- C neutral bucket: n=238, share of calls that really were neutral 16.4% vs base 22.1% -> edge -5.7.
- B neutral bucket: n=353, share of calls that really were neutral 21.5% vs base 22.1% -> edge -0.6.

**Arm C: 502 of 703 of A's neutral (Hold) calls left neutral.** Pooled edge (hit rate minus each direction's own base rate) +1.4 points (range -4.1 to 7.1). bearish: n=2, hit 100.0% vs base 44.7%, median return -64.61, mean -64.61; bullish: n=500, hit 34.4% vs base 33.2%, median return -1.88, mean 0.88.

**Arm B: 399 of 703 of A's neutral (Hold) calls left neutral.** Pooled edge (hit rate minus each direction's own base rate) +4.2 points (range -1.8 to 10.4). bearish: n=112, hit 62.5% vs base 44.7%, median return -10.05, mean -4.19; bullish: n=287, hit 32.1% vs base 33.2%, median return -1.81, mean 0.63.

## 6.3 Old ruler (fixed thresholds): accuracy, precision, flips

| arm | n graded | accuracy % | luck % | gap (pp) | bearish calls | bearish precision % (base 46.6) | bullish calls | bullish precision % (base 32.8) |
|---|---|---|---|---|---|---|---|---|
| A | 1217 | 29.9 | 27.7 | +2.24 | 93 | 58.1 | 421 | 36.8 |
| B | 1217 | 35.3 | 31.8 | +3.55 | 191 | 62.3 | 673 | 34.9 |
| C | 1217 | 33.4 | 31.4 | +2.0 | 44 | 75.0 | 935 | 35.8 |

**Noise arm (21a: v6 re-scored vs its own cached call):** n=120, disagreement 20 (16.7%, Wilson 11.1 to 24.3); fresh call right in 15.0% of graded noise flips (n=20), cached call right in 30.0%. Per stratum:

| stratum | n | flips | rate % | Wilson |
|---|---|---|---|---|
| S1 | 35 | 5 | 14.3 | 6.3 to 29.4 |
| S2 | 19 | 3 | 15.8 | 5.5 to 37.6 |
| S3 | 53 | 7 | 13.2 | 6.5 to 24.8 |
| S4 | 2 | 1 | 50.0 | 9.5 to 90.5 |
| S5 | 11 | 4 | 36.4 | 15.2 to 64.6 |

Strata whose range excludes the overall rate (16.7%): none.

**Flips against A, raw and net (netting rule, findings.md):**

| arm | shared calls | raw flips | expected noise flips (21a, re-weighted) | net | noise-count range | flip win rate raw % | noise win rate % | netted win rate |
|---|---|---|---|---|---|---|---|---|
| B | 1217 | 453 | 201 | 252 | 135 to 296 | 38.9 | 15.0 | 57.9 (UNSTABLE, denominator too small -- not a headline) |
| C | 1217 | 555 | 201 | 354 | 135 to 296 | 33.3 | 15.0 | 43.8 (reportable) |

Caveat (netting rule): noise flips and real flips are not disjoint; the subtraction assumes independence and no overlap.

## 6.4 Money (tradeable entry, 182 days, points vs S&P)

Reference rows in the prompt (bearish 7.4% of calls, edge +12.3, median -10.09%; bullish 34.3%, +4.4, -1.43%; swap +2.4 mean / +8.7 median) are pooled TRAIN+TUNE (2,385 calls) -- they will not match a train-only A row.

| arm | bearish share % | bearish mean | bearish median | bullish share % | bullish mean | bullish median | swap mean | swap median |
|---|---|---|---|---|---|---|---|---|
| A | 7.6 | -2.22 | -9.46 | 34.6 | 0.31 | -1.33 | 2.54 | 8.12 |
| B | 15.7 | -6.13 | -10.39 | 55.3 | 0.64 | -1.46 | 6.76 | 8.92 |
| C | 3.6 | -25.13 | -23.00 | 76.8 | 0.82 | -1.63 | 25.95 | 21.37 |

Arm A swap range: mean -12.55 to 19.80; median -2.41 to 17.96.
Arm B swap range: mean -3.32 to 16.57; median 4.12 to 15.34.
Arm C swap range: mean 8.54 to 47.01; median 3.95 to 44.55.

**Per stratum (S1-S5) and 2020 vs the rest:**

| slice | arm | n | bearish n | bearish median | bullish n | bullish median | swap median |
|---|---|---|---|---|---|---|---|
| S1 | A | 356 | 21 | -4.47 | 140 | -0.34 | 4.13 |
| S1 | B | 356 | 38 | -7.01 | 237 | 0.19 | 7.20 |
| S1 | C | 356 | 6 | 0.21 | 303 | -0.25 | -0.46 |
| S2 | A | 192 | 16 | 5.44 | 90 | -4.17 | -9.61 |
| S2 | B | 192 | 33 | -7.50 | 100 | -4.76 | 2.74 |
| S2 | C | 192 | 4 | -1.31 | 146 | -3.80 | -2.48 |
| S3 | A | 541 | 36 | -10.24 | 145 | 0.29 | 10.53 |
| S3 | B | 541 | 70 | -6.61 | 284 | -2.22 | 4.39 |
| S3 | C | 541 | 21 | -25.62 | 417 | -1.72 | 23.90 |
| S4 | A | 16 | 8 | -93.92 | 1 | -0.86 | 93.06 |
| S4 | B | 16 | 12 | -79.07 | 0 | n/a | n/a |
| S4 | C | 16 | 7 | -85.04 | 2 | -11.05 | 74.00 |
| S5 | A | 112 | 12 | -12.51 | 45 | -1.46 | 11.05 |
| S5 | B | 112 | 38 | -26.83 | 52 | 0.20 | 27.03 |
| S5 | C | 112 | 6 | -36.13 | 67 | -3.74 | 32.39 |
| 2020 | A | 162 | 9 | 4.35 | 36 | -0.97 | -5.31 |
| 2020 | B | 162 | 25 | -1.63 | 81 | -0.03 | 1.59 |
| 2020 | C | 162 | 5 | -10.09 | 134 | 1.77 | 11.86 |
| ex-2020 | A | 1055 | 84 | -11.03 | 385 | -1.33 | 9.70 |
| ex-2020 | B | 1055 | 166 | -13.17 | 592 | -1.57 | 11.60 |
| ex-2020 | C | 1055 | 39 | -25.62 | 801 | -1.82 | 23.79 |

## 6.5 Diagnostics

- **B vs C score agreement:** Spearman 0.744 (range 0.688 to 0.791), n=1217.
- **Disagree by >=3 points:** 205 calls; only B's sign matches the realized return in 127, only C's in 78, neither/both 0 (sign of tradeable-entry return).
- **What the rubric did (arm C score by thesisHealth x stumbleType):**

| thesisHealth | stumbleType | n | median score | share in {-1,0,+1} % |
|---|---|---|---|---|
| Strengthening | None | 482 | 3 | 0.0 |
| Intact | None | 386 | 2 | 28.5 |
| Intact | Execution | 137 | 2 | 49.6 |
| Intact | Discovery | 80 | 2 | 26.2 |
| Weakening | Execution | 53 | -2 | 43.4 |
| Strengthening | Discovery | 24 | 3 | 0.0 |
| Strengthening | Execution | 21 | 3 | 0.0 |
| Weakening | Structural | 17 | -2 | 29.4 |
| Intact | Structural | 11 | 1 | 63.6 |
| Weakening | None | 3 | -1 | 100.0 |
| Weakening | Discovery | 2 | -1.5 | 50.0 |
| Broken | Structural | 1 | -4 | 0.0 |

  Intact + None: n=386, 28.5% score in {-1,0,+1} (100% would mean the matrix is being reproduced from habit).
- **Length (median completion tokens):** B 514, C 2450, v6 (from the 120 noise re-scores) 2428.
- **Q2 re-run (discovery only):** inside C's bearish bucket (n=44), split at median score -2.0: stronger half (n=2) precision 100.0% vs weaker (n=42) 73.8% -> difference +26.2 points (range 12.5 to 40.7); Spearman of score vs return within the bucket 0.310.
