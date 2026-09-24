# P6 — the output-format round: v6 vs a minimal prompt vs a continuous score — wrap-up

**Run ID:** `p6-output-format-round`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial:** pre-flight, arm B, arm C and the noise arm all landed; every test in §6 ran.
**Real spend: about $87.91** (pre-flight $6.51 + arm B $28.72 + arm C $47.86 + noise arm $4.82) against the $130 cap. One duplicate batch was created by mistake and cancelled with 0 calls processed; its billed amount, if any, must be read from the console (§8).
**Reading version (renders correctly anywhere, phone included):** https://claude.ai/artifact/2oRhWpFfctc6qddUt7ATQ6 **Scope boundary: report, do not decide.**

---

## §0 — Defined terms

In plain words first: the analyst read 1,217 earnings calls three ways. **v6** is today's prompt: a long rubric that ends in Add / Hold / Trim / Exit. **Arm B** is a short prompt with no rubric that just asks for a number from −5 to +5. **Arm C** is v6 with its last step swapped: the same rubric, but the analyst ends with the −5 to +5 number instead of Add / Hold / Trim / Exit. Then we asked whether the numbers line up with what the stocks actually did afterwards.

- **Score.** The analyst's number from −5 (strong conviction the stock lags the S&P 500 over the next six months) to +5 (strong conviction it beats it).
- **No-read (`noRead`).** The analyst's own flag that a score of 0 means "this call gives me no basis for a view", as opposed to a weak view (+1 or −1).
- **Bucket.** All calls that got the same score, grouped so their forward returns can be summarised together. Arm A's buckets are its three answers: bearish (Trim/Exit), neutral (Hold), bullish (Add).
- **Rank-ordering.** Does a higher score go with a higher return? Reported as a **Spearman rank correlation**: 0 means the score tells you nothing about the order of returns, +1 means a perfect ordering. Each figure carries a 95% range from a **ticker-block bootstrap** (the computer resamples whole companies, not single calls, because calls from one company are not independent).
- **Top-minus-bottom spread.** The typical (median) return of the calls scored +3 or higher, minus the typical return of the calls scored −3 or lower, in points.
- **Tradeable entry.** Every return in this report starts from the first closing price *after* the call date, the first price a reader of the transcript could actually trade at, and runs 182 days, measured as points ahead of or behind the S&P 500.
- **Money.** How far the stock actually moved, in those points. This has been the measure of record since 2026-09-20. **Accuracy** is a footnote: it only asks whether the stock finished more than 5 points ahead of or behind the S&P.
- **Edge.** Hit rate minus the **base rate** for that answer, in points. The base rate is how often that outcome happens across all calls whatever the analyst said (here: bearish 44.7%, neutral 22.1%, bullish 33.2% of 1,217 calls).
- **Noise flip.** A call where v6, asked the same question twice, gives two different answers. **Net flip:** a count of changes between two prompts, minus the number of noise flips you would expect anyway. **Control arm:** a deliberately simple comparison (arm B) run to see whether the complicated thing (the rubric) earns its length.
- **Fixed thresholds (needed only for the old ruler).** Score ≤ −2 counts as bearish, ≥ +2 as bullish, −1/0/+1 as neutral. Set before any result, not tuned.
- **Strata S1–S5.** The corpus-construction groups from `SPLIT_V7_RESERVE_REPLACEMENTS.json`. Not market-cap tiers (§9, flag 2).

**Population.** 1,217 train calls, 55 companies, every call with a 182-day return. Excluded entirely: WOLF and SPWR (no price data) and Paramount/PARA (corrupt price series, 2026-09-23 state of play §4.1). Model `claude-sonnet-4-6`, pinned.

---

## Headline

> On **1,217** train calls, the minimal prompt (arm B) ranked forward returns with a correlation of **0.130** (range 0.051 to 0.208) and the score arm (C) with **0.140** (range 0.061 to 0.219); v6's three buckets, for comparison, separate their best from their worst by **8.12** points (range −2.41 to +17.96) and arm C's by **90.28** points, a figure that rests on just two calls at −3 or below (on the wider "−2 or below" cut, post-hoc, it is 23.0, range 5.5 to 46.1). Arm C moved **502 of v6's 703** neutral calls out of neutral, and those calls carried an edge of **+1.4** points (range −4.1 to +7.1, which includes zero). On the old ruler, accuracy was **A 29.9 / B 35.3 / C 33.4**.

**Plain reading.** Both new prompts produce a score that tracks returns, weakly but measurably, and the two are statistically indistinguishable from each other (paired difference 0.010, range −0.034 to +0.054). The score format carried the signal; the rubric added nothing visible. The control did not lose. The neutral pile shrank from 58% to 20% for C, but the calls that left it did not carry a measurable edge.

---

## 6.1 Rank-ordering — the primary test

Returns are tradeable-entry, 182 days, points vs the S&P. Ranges are 95%, ticker-block bootstrap (2,000 draws).

**Arm A (v6), three buckets**

| bucket | n | median | mean | beat by >5 % of calls | lagged by >5 % of calls |
|---|---|---|---|---|---|
| bearish | 93 | −9.46 | −2.22 | 31.2 | 57.0 |
| neutral | 703 | −3.10 | −0.12 | 32.4 | 46.4 |
| bullish | 421 | −1.33 | 0.31 | 34.7 | 41.1 |

**Arm B score buckets**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| −5 | 1 | −102.80 | −102.80 | 0.0 | 100.0 |
| −4 | 2 | −33.86 | −33.86 | 50.0 | 50.0 |
| −3 | 27 | −10.39 | −14.71 | 25.9 | 63.0 |
| −2 | 161 | −10.08 | −3.74 | 29.8 | 60.2 |
| −1 | 183 | −5.35 | 4.56 | 32.8 | 50.8 |
| 0 (noRead) | 3 | −0.69 | 0.29 | 33.3 | 0.0 |
| +1 | 167 | −2.98 | −1.55 | 34.1 | 43.7 |
| +2 | 438 | −2.29 | −0.70 | 32.4 | 41.1 |
| +3 | 226 | 1.16 | 1.65 | 36.3 | 38.5 |
| +4 | 9 | 16.95 | 40.12 | 55.6 | 33.3 |

**Arm C score buckets**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| −4 | 1 | −102.80 | −102.80 | 0.0 | 100.0 |
| −3 | 1 | −77.75 | −77.75 | 0.0 | 100.0 |
| −2 | 42 | −18.72 | −22.02 | 19.0 | 69.0 |
| −1 | 51 | −9.46 | 7.81 | 35.3 | 54.9 |
| 0 (noRead) | 17 | −6.66 | −3.25 | 23.5 | 64.7 |
| +1 | 170 | −7.77 | −1.01 | 24.1 | 59.4 |
| +2 | 485 | −2.30 | 0.45 | 34.8 | 41.9 |
| +3 | 428 | 0.12 | 0.75 | 36.4 | 38.8 |
| +4 | 22 | −9.47 | 10.55 | 31.8 | 54.5 |

**Summary numbers (registered)**

| arm | Spearman | range | spread (≥+3 minus ≤−3), points | range | n(≥+3) / n(≤−3) |
|---|---|---|---|---|---|
| B | 0.130 | 0.051 to 0.208 | 14.16 | −2.22 to 79.37 | 235 / 30 |
| C | 0.140 | 0.061 to 0.219 | 90.28 | 75.29 to 104.23 (1,745 of 2,000 draws valid) | 450 / **2** |

Excluding noRead calls changes nothing (B 0.131, C 0.137). **C's registered spread is not a usable number**: only 2 calls score −3 or lower, and both are outliers (−102.80 and −77.75). Arm C almost never goes below −2; its floor is −4. Read C's ordering from the buckets instead: median return climbs from −18.72 at −2, through −9.46, −7.77 at +1, −2.30, to +0.12 at +3. It is ordered across the populated range and breaks only at +4 (n=22, median −9.47).

**Post-hoc comparators (not pre-registered; from `analysis/p6_posthoc.py`, `posthoc.json`).**

| comparison | value | range |
|---|---|---|
| A's three answers coded −1/0/+1, Spearman | 0.070 | −0.004 to 0.144 |
| C minus A, paired | +0.070 | 0.022 to 0.120 |
| B minus A, paired | +0.061 | 0.005 to 0.119 |
| C minus B, paired | +0.010 | −0.034 to 0.054 |
| spread, score ≥+3 minus score ≤−2, B | 11.67 | 4.99 to 18.05 (n(≤−2)=191, median −10.39) |
| spread, score ≥+3 minus score ≤−2, C | 23.00 | 5.45 to 46.09 (n(≤−2)=44, median −23.00) |

A's 3-level answers are a coarser instrument by construction, so part of the gap over A is resolution, not only quality. That is the neutral-pile point restated.

**Noise win rate beside 6.1 (prompt §7):** rank-ordering is not netted. The 21a noise win rate sits well below 50% on this sample (fresh call right in 15.0% of graded noise flips, cached call right in 30.0%, n=20 graded flips), so the "noise doesn't shift the rank test" licence is **not confirmed at n=20**; see §6.3.

## 6.2 The neutral pile

| | neutral share | of which noRead | weak (±1) | score 0 with a read |
|---|---|---|---|---|
| A (Hold) | 57.8% | n/a | n/a | n/a |
| B | 29.0% | 0.2% | 28.8% | 0.0% |
| C | 19.6% | 1.4% | 18.2% | 0.0% |

**Neutral share fell** for both, far below 58%. But the neutral bucket itself still carries no edge: A neutral edge −0.1 (22.0% of those calls really were neutral vs base 22.1%), B −0.6, C −5.7 (n=238).

**Calls that left neutral.**

| arm | of A's 703 neutral calls, moved out | pooled edge | range | detail |
|---|---|---|---|---|
| C | 502 | **+1.4** | −4.1 to +7.1 | bearish n=2 (hit 100%, median −64.61); bullish n=500, hit 34.4% vs base 33.2%, median −1.88, mean +0.88 |
| B | 399 | +4.2 | −1.8 to +10.4 | bearish n=112, hit 62.5% vs base 44.7%, median −10.05, mean −4.19; bullish n=287, hit 32.1% vs base 33.2%, median −1.81 |

Registered falsifier (6.2): *"the calls C moved out of neutral carry zero edge."* **Met**: +1.4 with a range that includes zero. Nearly all of C's movers went to the bullish side (500 of 502) because C's habitual answer is +2 or +3, which the fixed thresholds call bullish. B is the arm whose movers show a signal: 112 new bearish calls at 62.5%, median −10.05.

**Arm C did not reproduce the matrix from habit** (6.5): Intact + no stumble calls score in {−1,0,+1} only 28.5% of the time (median score +2, n=386).

## 6.3 Old ruler, on the fixed thresholds — continuity, not the decision

| arm | n graded | accuracy % | luck % | gap (points) | bearish calls | bearish precision % (base 46.6) | bullish calls | bullish precision % (base 32.8) |
|---|---|---|---|---|---|---|---|---|
| A | 1,217 | 29.9 | 27.7 | +2.24 | 93 | 58.1 | 421 | 36.8 |
| B | 1,217 | 35.3 | 31.8 | +3.55 | 191 | 62.3 | 673 | 34.9 |
| C | 1,217 | 33.4 | 31.4 | +2.00 | 44 | 75.0 | 935 | 35.8 |

A's row is v6's published train reference re-stated after the PARA exclusion (with PARA it reproduces **30.3% / +2.48 / 103 bearish / 60.2%** exactly; `v6_reference_repro.json`). C's accuracy figure is inflated by the thresholds putting 77% of its calls in the bullish bucket, where the base rate is 33%. The gap column corrects for that: C's gap (+2.00) is not above A's.

**Noise arm (21a).** 120 train calls already in the v6 cache, re-scored with unmodified v6, drawn proportional to the S1–S5 mix (S1 35 / S2 19 / S3 53 / S4 2 / S5 11). Disagreement with their own cached call: **20 of 120, 16.7% (Wilson 11.1 to 24.3)**. Test 4's 12.8% (6.8–19.2) sits inside that range.

| stratum | n | flips | rate % | Wilson |
|---|---|---|---|---|
| S1 | 35 | 5 | 14.3 | 6.3 to 29.4 |
| S2 | 19 | 3 | 15.8 | 5.5 to 37.6 |
| S3 | 53 | 7 | 13.2 | 6.5 to 24.8 |
| S4 | 2 | 1 | 50.0 | 9.5 to 90.5 |
| S5 | 11 | 4 | 36.4 | 15.2 to 64.6 |

No stratum's range excludes the overall rate, so one global rate is defensible (per-stratum re-weighting is still what is subtracted below). **Uncomfortable detail:** among the graded noise flips the cached v6 call was right in 6 (30.0%) and the fresh call in 3 (15.0%). That is n=20, far too few to call, but it points the direction the netting rule warns about (a cached draw luckier than a fresh one). It also means A's accuracy row is, if anything, a slightly lucky draw.

**Flips against A, raw and net.** "Flip win" = the arm's answer is right and A's is wrong. "Win rate" here is wins over all graded flips, the same definition applied to the noise arm, so both sides of the netting subtraction use one definition.

| arm | shared calls | raw flips | expected noise flips (21a, S1–S5 re-weighted) | net flips | noise-count range | raw flip win rate % | noise win rate % | netted win rate |
|---|---|---|---|---|---|---|---|---|
| B | 1,217 | 453 | 201 | **252** | 135 to 296 | 38.9 (wins 176, losses 110, both wrong 167) | 15.0 | 57.9, **unstable: net 252 does not exceed the noise range's upper end (296)** |
| C | 1,217 | 555 | 201 | **354** | 135 to 296 | 33.3 (wins 185, losses 142, both wrong 228) | 15.0 | 43.8 (guard passed: net 354 > 100 and > 296) |

Both net counts clear the ~100-flip floor; C's clears the top of the noise range, B's does not. The 6.2/6.3 falsifier "net flip count below the corrected noise floor" is **not met for C**. Caveat (netting rule): noise flips and real flips are not disjoint; the subtraction assumes independence. C's netted win rate leans on a noise win rate measured on 20 flips.

## 6.4 Money — the measure of record

Tradeable entry, 182 days, points vs the S&P. **The prompt's reference rows are pooled train+tune (2,385 calls), so they will not match a train-only A row** (A here: bearish 7.6% of calls vs 7.4%, median −9.46 vs −10.09; bullish 34.6% vs 34.3%; swap +2.54 mean / +8.12 median vs +2.4 / +8.7).

| arm | bearish share % | bearish mean | bearish median | bullish share % | bullish mean | bullish median | swap mean | swap median |
|---|---|---|---|---|---|---|---|---|
| A | 7.6 | −2.22 | −9.46 | 34.6 | 0.31 | −1.33 | 2.54 | 8.12 |
| B | 15.7 | −6.13 | −10.39 | 55.3 | 0.64 | −1.46 | 6.76 | 8.92 |
| C | 3.6 | −25.13 | −23.00 | 76.8 | 0.82 | −1.63 | 25.95 | 21.37 |

Swap ranges (95%, ticker-block): A mean −12.55 to 19.80, median −2.41 to 17.96. B mean −3.32 to 16.57, median 4.12 to 15.34. C mean 8.54 to 47.01, median 3.95 to 44.55.

C's swap figure is large but rests on **44 bearish calls**, several of them the extreme names; its range runs from 4 to 45 points. B's is the tighter of the two: its median swap range (4.12 to 15.34) excludes zero, on a bearish bucket of 191 calls against A's 93 and C's 44.

**By stratum and by year (swap median, points)**

| slice | A | B | C | A bearish n / median | B bearish n / median | C bearish n / median |
|---|---|---|---|---|---|---|
| S1 | 4.13 | 7.20 | −0.46 | 21 / −4.47 | 38 / −7.01 | 6 / +0.21 |
| S2 | −9.61 | 2.74 | −2.48 | 16 / +5.44 | 33 / −7.50 | 4 / −1.31 |
| S3 | 10.53 | 4.39 | 23.90 | 36 / −10.24 | 70 / −6.61 | 21 / −25.62 |
| S4 | 93.06 | n/a (0 bullish) | 74.00 | 8 / −93.92 | 12 / −79.07 | 7 / −85.04 |
| S5 | 11.05 | 27.03 | 32.39 | 12 / −12.51 | 38 / −26.83 | 6 / −36.13 |
| 2020 | −5.31 | 1.59 | 11.86 | 9 / +4.35 | 25 / −1.63 | 5 / −10.09 |
| excl. 2020 | 9.70 | 11.60 | 23.79 | 84 / −11.03 | 166 / −13.17 | 39 / −25.62 |

S4 is the failures stratum (16 calls); it drives the top of every swap figure. S1 (large caps, 356 calls) is where C's bearish calls carry nothing (6 calls, median +0.21). 2020, reported separately as asked, is the atypical year and is where A's bearish calls did worst (median +4.35, n=9).

## 6.5 Diagnostics

- **B vs C agreement:** Spearman 0.744 (0.688 to 0.791). On the 205 calls where they differ by ≥3 points, only B's sign matched the realised return in 127 and only C's in 78.
- **What the rubric did (C's score by thesis health and stumble type).** Strengthening + None: median +3, 0% in {−1,0,+1} (n=482). Intact + None: median +2, 28.5% (n=386). Intact + Execution: +2, 49.6% (n=137). Weakening + Execution: −2, 43.4% (n=53). C's scores follow the rubric's thesis-health ordering closely.
- **Length (median completion tokens):** B 514, C 2,450, v6 2,428 (from the 120 noise re-scores). B is one-fifth the length; note it beside any accuracy comparison (the input-length confound from the P3 review, in reverse).
- **Q2 re-run on C's score (discovery only).** Prediction written in `findings.md` before any C result: more negative half has higher bearish precision by ≥5 points, and within-bucket Spearman positive. **Not testable:** 42 of C's 44 bearish calls score exactly −2, so the "stronger half" is 2 calls (precision 100% vs 73.8%, range 12.5 to 40.7 on a two-call arm). Within-bucket Spearman is +0.310, driven by the two extreme outliers. Recorded as a finding: **C's score has almost no resolution on the bearish side.**
- **Per-call diffs:** `analysis/data/run_state/p6-output-format-round/per_call_diffs.csv`. **Per-call file:** `calls.csv`.

---

## Predictions in the P6 block: each one, held or not

1. *Arm C's score buckets order forward returns; falsified if the rank correlation's range includes zero.* **Held**: 0.140, range 0.061 to 0.219 excludes zero. The ordering is coarse and breaks at +4.
2. *Arm C's neutral share falls well below 58%.* **Held**: 19.6%.
3. *The calls that leave neutral show a non-zero edge.* **Did not hold**: +1.4, range −4.1 to +7.1.
4. *Net flip count above the corrected noise floor.* **Held for C** (354 vs a noise range top of 296); **not for B** (252).
5. *Arm C beats arm A on rank-ordering.* **Held on the post-hoc paired comparison** (+0.070, range 0.022 to 0.120) and could not be tested on the registered spread (C's rests on 2 calls).
6. *Arm B lands between A and C or matches A.* **It did not lose to A**: B is indistinguishable from C (paired +0.010, range −0.034 to +0.054) and above A on rank correlation (+0.061, range 0.005 to 0.119) and on old-ruler accuracy and gap. The control was expected to lose; this is the finding the P6 block said would redirect the queue.

## Findings, one each

1. **Both new prompts rank returns; the ranking is small.** A correlation of 0.13–0.14 is weak. Its lower ends sit at 0.05–0.06, clear of zero. It is what a 1,217-call sample from 55 companies can show.
2. **The rubric adds nothing measurable to the ranking.** B (514 tokens, no rubric) and C (2,450 tokens, full rubric) are indistinguishable. B cost $0.0236 a call against C's $0.0393 (full-run batch averages).
3. **Removing the matrix did shrink the neutral pile but did not release information from it.** C's 502 movers are overwhelmingly weak-bullish (+2), at edge +1.4 (range includes zero). B's 112 new bearish calls out of A's neutrals are the one place a mover group shows a signal (62.5% precision vs 44.7% base; median −10.05).
4. **Both models default to a mildly positive score.** The single most common scores are +2 (B 438, C 485) and +3 (B 226, C 428). Under the fixed thresholds that makes 55% (B) and 77% (C) of calls bullish. The score distribution, not the rubric, is what the thresholds act on. Thresholds are an allocator-side decision on `calls.csv`, not made here.
5. **Low scores on C are informative but thin.** The −2 bucket (n=42) has median return −18.72 and lagged the S&P by >5 points 69% of the time; only 44 calls score ≤ −2 at all. B's ≤−2 group is 191 calls with median −10.39.
6. **The noise floor is high and the cached draw may be lucky.** 16.7% disagreement (11.1 to 24.3), and 6 of 20 graded noise flips favoured the cached call against 3 for the fresh one. Flip counts against A are therefore inflated by noise by about 200 of every ~450–550.

## What this means for a decision — all three ways (not decided here)

- **If C ranks and B does not** (the rubric stays, the matrix goes, thresholds are allocator-side): *not the case.* B ranks as well as C.
- **If B matches or beats A** (the rubric is not where the signal is; P7/P8 iterate from the minimal prompt): *this is the branch the data sits on.* B matches C, beats A's ordinal ranking, and costs 40% less per call. The signal came from the output format (a graded score), not from the rubric.
- **If neither ranks** (the transcript-only read is at its ceiling on this model; the next lever is the reader, a §2.2b model gate): *partly.* Both rank, but weakly (0.13–0.14), so a ceiling on this model is also consistent with the data.

## §9 Deviations, premise flags, and what was not done

**Premise flags (all recorded in `findings.md` at Step 0):**
1. The prompt's 0f says "1,194 transcripts"; 1,194 is the *unresolved* count. Resolved is 1,240 (1,217 after the PARA exclusion), and the assertions checked 1,240 / 56 / 1,184.
2. `stratum_map()` returns corpus strata S1–S5, not the four-way megacap/large/mid/small-micro split the prompt names (that split exists only as a hardcoded 15-ticker list with 6 in train and none "large"). The noise arm was drawn proportional to S1–S5 as `P3-guidance-ledger.md` §5f specifies, and every "per stratum" figure here is S1–S5. The prompt's 35/35/25/25 allocation was not attainable.
3. The 30.3% / +2.48 v6 reference is from `wrap-ups/scorer-price-cache-backfill-out.md`. The wrap-up the prompt cites (`baseline-v6-train-batch-out.md`) reports the pre-backfill 22.8% / −1.64.
4. The prompt's registered date (2026-09-24) is a day after today's date (2026-09-23), harmless. The P6 block asks for rank-ordering "across all ~2,385 calls"; this run is train only (1,217).
5. The `tier` column in `calls.csv` is "NA": no established/speculative field exists for the train companies (`type_classifications.json` covers 32 other tickers).
6. The flip-count-rule correction to `PROMPT_ARCHITECTURE.md` §2.4/§2.5 had **not landed** (last commit is the P6 registration). I did not edit it, and reported every flip count raw and net.

**Deviations from the prompt:**
- Pre-flight scores were reused as arm results, and the full-arm batches submitted only the remaining transcripts (Step −1's skip-present-ids rule). Saves about $7.
- The eval caches (`analysis/data/evals/P6B-minimal_claude-sonnet-4-6/`, `…P6C-score…/`) are gitignored, like the v6 cache, and were not force-added. `scores_b.jsonl`, `scores_c.jsonl`, `scores_noise.jsonl` in run_state carry identical content and are committed.
- The noise arm's re-scores are stored in `scores_noise.jsonl`, not in the v6 eval cache (which is untouched).

**Incident (cost).** A first `submit-c` created a duplicate arm-C+noise batch (`msgbatch_01XBKE7mSMWe9S8xiwArCd46`, 1,237 requests, ~$51 if it had completed) whose id was not persisted. I had piped the output to `tail`, so I lost the error, and I ran a concurrent background poller. I found the duplicate by listing batches and cancelled it; the cancel response showed 0 succeeded and 1,237 processing. **Its billed amount is unconfirmed** and should be checked in the Anthropic console. Cause not established. A separate bug in `commit_spend` (it counted a retried key's earlier estimate again) was found and fixed in its own driver commit. Committed spend never exceeded $85.25.

**Deliberately not done:** no promotion, no threshold choice, no P7/P8, no tune or holdout scoring, no edits to the candidate prompts, the scorer, or `PROMPT_ARCHITECTURE.md`; no cache refresh; no DB writes.

**Left for the design session:**
- Whether B's 514-token prompt is the new starting point (P7/P8 would iterate from it).
- Thresholds, on `calls.csv`, allocator-side. Note both models sit at +2/+3 by default.
- Whether a confirmatory tune run of B is warranted; B is the one arm with a signal in its bearish movers.
- Re-run the noise arm larger (120 calls gave 20 flips; the cached-vs-fresh luck question needs several hundred graded flips).
- The C bearish bucket has 44 calls; the swap figure on it is not established.
- Read the console for the orphan batch's billed amount.

## Provenance and artifacts

Driver `analysis/p6_output_format_driver.py`; analysis `analysis/p6_output_format_analysis.py`; post-hoc `analysis/p6_posthoc.py` (each committed before it produced output). State in `analysis/data/run_state/p6-output-format-round/`: `progress.json`, `findings.md`, `scores_b.jsonl`, `scores_c.jsonl`, `scores_noise.jsonl`, `calls.csv`, `v6_reference_repro.json`, `results.json`, `tests_report.md`, `per_call_diffs.csv`, `posthoc.json`. Protocol `analysis/data/corpus_v2/SCORING_PROTOCOL_P6.json`. Candidates registered in `docs/architecture/VERSION_REGISTRY.json` as `P6B-minimal` (sha `d1fa5e53…`) and `P6C-score` (sha `da5edc6f…`). All returns: `rel_ret` arm "B" (first close strictly after the call date), 182 days, SPY, `analysis/data/corpus_v2/scorer_price_cache_v1.json`. Every rank and range figure is a ticker-block bootstrap, 2,000 draws, seed 11. Every "median" and "mean" is across calls (not draws).

```bash
# reproduce everything from the scores on disk ($0)
python3 analysis/p6_output_format_analysis.py calls
python3 analysis/p6_output_format_analysis.py tests
python3 analysis/p6_posthoc.py
```
