# P6B on tune: one look, pre-registered. Wrap-up

**Run ID:** `p6b-tune-confirmation`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial.** Pre-flight, arm B on all tune calls and the 250-call noise arm all landed; every test ran.
**Real spend: $38.14** (arm B $27.52, including the 50 pre-flight calls; noise arm $10.62) against the $60 cap. Committed estimate never exceeded $39.37.
**Reading version (renders correctly anywhere, phone included):** https://claude.ai/artifact/3RzF45PTLazN3SeNrQ41Rh
**Scope boundary: report, do not decide.** Nothing is promoted; `promoted_version` is untouched; holdout was not scored; no threshold was chosen beyond the two pre-registered mappings.

---

## §0. Defined terms

In plain words first. On the train companies, a short prompt with no rubric (arm B) turned out to rank forward stock returns about as well as the full v6 rubric. That could have been luck fitted to 55 companies. This run gives B one look at 51 companies it had never scored, with every pass/fail rule written down beforehand.

- **One look.** The single scoring of a final candidate on the tune split that `PROMOTION_GATE.md` §7 allows. Nothing is tuned against it. If B fails, it failed.
- **Held / falsified.** B *holds* only if conditions 1, 2 and 3 in §5 of the prompt all pass. Condition 4 is reported but cannot falsify.
- **Score.** The analyst's number from −5 (strong conviction the stock lags the S&P 500 over the next six months) to +5 (strong conviction it beats it).
- **No-read.** The analyst's flag that a score of 0 means "no basis for a view".
- **Bucket.** All calls with the same score, summarised together.
- **Rank-ordering.** Does a higher score go with a higher return? Reported as a **Spearman rank correlation** (0 = no relationship, 1 = perfect ordering) with a **95% range from a ticker-block bootstrap** (the computer resamples whole companies, not single calls, because calls from one company are not independent; 2,000 draws, seed 11).
- **Tradeable entry.** Every return starts from the first closing price *after* the call date and runs 182 days, in points ahead of or behind the S&P 500.
- **Money.** How far the stock actually moved. It has been the measure of record since 2026-09-20. **Accuracy** (finished more than 5 points ahead of or behind the S&P) is a footnote.
- **Swap.** Sell what the analyst flags bearish, buy what it flags bullish. Its worth here is the median return of the bullish bucket minus the median return of the bearish bucket, in points.
- **Edge / base rate.** Hit rate minus how often that outcome happens across all calls whatever the analyst said (tune: bearish 48.3% of the 1,168 old-ruler-gradable calls).
- **Noise flip / net flip.** A noise flip is a call where v6, asked twice, gives two different answers. A net flip count is the raw count of changes between two prompts minus the noise flips you would expect anyway.
- **Pooled.** Train and tune together (2,386 calls, 106 companies).
- **Thresholds, fixed before any result.** Pre-registered mapping: score ≤ −2 bearish, **≥ +3 bullish**, −1/0/+1/+2 neutral. The train run's original mapping (bullish ≥ +2) is reported alongside, labelled. The cut moved because +2 is B's resting score and carried no edge on train.
- **Strata S1–S5.** The corpus-construction groups, not market-cap tiers.

**Population.** 1,169 tune calls, 51 companies, every call with a 182-day return. Excluded entirely: WOLF and SPWR (ungradable). BNY (formerly BK) has 0 transcripts, a documented vendor gap; it is the third of the 54 tune companies. Model `claude-sonnet-4-6`, pinned. Prompt `P6B-minimal`, sha `d1fa5e53…`.

---

## Headline

> On **1,169** tune calls from **51** companies the minimal prompt had never seen, its score ranked forward returns at **0.140** (range **0.072** to **0.198**); it made **161** bearish calls against v6's **84** and was right on **60.9%** of them against v6's **59.5%**; the sell-bearish/buy-bullish swap was worth a median **8.34** points (range **1.46** to **12.88**). Of the four pre-registered conditions, **4** held. **B held on tune.**

**Plain reading.** Every number landed inside the range predicted on 2026-09-24. The train result was not a fit to 55 companies. Three caveats sit next to that, and they are in §6: the money range's lower end is close to zero, the ordering comes from the top of the score scale and not from graded bearish severity, and the pre-registered +3 mapping makes B's neutral pile larger than v6's, not smaller.

---

## §5. The four conditions, one line each

1. **Rank-ordering: HELD.** Spearman **0.140**, range 0.072 to 0.198, n=1,169. Train was 0.130 (0.051–0.208); the prediction was 0.08–0.16.
2. **Bearish coverage without precision loss: HELD.** B made **161** bearish calls (score ≤ −2) against v6's **84** on the same gradable calls: **1.92×** (needs ≥ 1.5×; predicted 1.7–2.2×). B's precision was **60.9%** against v6's **59.5%**, **+1.3 points** (needs no worse than −5). Base rate 48.3%.
3. **Money: HELD.** Swap median at score ≤ −2 / ≥ +3 is **8.34** points, range **1.46 to 12.88** (train, at the +2 mapping: 8.92, 4.12–15.34; predicted 6–12 with a range clear of zero).
4. **Old ruler at +3, non-gating: HELD.** B's luck-corrected gap is **+4.07** against v6's **+2.64** (bar: +0.21, the lower end of v6's own reported range; interpretation fixed in `findings.md` before the run).

**Pre-registered rule: falsified if any of 1–3 fails. None failed. B held on tune.**

---

## Diagnostics (not gated)

### Score buckets and rank-ordering

| bucket | n | median | mean | beat >5 % of calls | lagged >5 % of calls |
|---|---|---|---|---|---|
| −4 | 4 | −8.28 | −7.47 | 50.0 | 50.0 |
| −3 | 16 | −4.57 | −7.24 | 31.2 | 50.0 |
| −2 | 141 | −7.89 | −5.74 | 27.7 | 54.6 |
| −1 | 178 | −7.20 | −3.42 | 27.0 | 53.9 |
| +1 | 175 | −6.12 | −4.32 | 31.4 | 54.3 |
| +2 | 413 | −2.50 | −0.57 | 32.7 | 44.3 |
| +3 | 228 | 0.53 | 3.68 | 39.0 | 39.5 |
| +4 | 14 | 2.41 | −1.16 | 42.9 | 28.6 |

B never gave a score of 0 or ±5 on tune (noRead share 0.0%; train 0.2%). The ordering is carried by the top: the +2, +3 and +4 buckets beat everything below +2. The buckets from −4 to +1 are flat (medians −4.6 to −8.3), so the score separates "better" from "the rest" more than it grades how bad the bad calls are.

**v6 (A) on the same calls:**

| bucket | n | median | mean | beat >5 % | lag >5 % |
|---|---|---|---|---|---|
| bearish | 84 | −8.46 | −0.88 | 34.5 | 53.6 |
| neutral | 687 | −5.04 | −3.26 | 29.7 | 50.2 |
| bullish | 397 | −0.71 | 1.45 | 36.5 | 41.6 |

Top-minus-bottom spread (score ≥ +3 minus score ≤ −3): **5.20** points (range −14.85 to 36.94; only 20 calls at ≤ −3, so this figure is thin). v6's best-minus-worst: 7.75 (range −5.51 to 10.94).

**Post-hoc, not pre-registered:** v6's three answers coded −1/0/+1 give a Spearman of 0.080 (0.006 to 0.149). B minus v6, paired: **+0.059 (+0.010 to +0.107)**. A coarser v6 instrument accounts for part of that gap.

### Neutral pile

Neutral share: v6 **58.8%**. B at the pre-registered +3 mapping **65.5%**. B at the train run's +2 mapping 30.2%. The pre-registered mapping puts +2 (413 calls, 35% of all calls) in the neutral pile, so **B's neutral pile is larger than v6's under the mapping the conditions were registered on**. That is a consequence of the mapping decision, reported here as a finding.

### Old ruler at both mappings

| arm / mapping | n graded | accuracy % | luck % | gap (points) | bearish calls | bearish precision % | bullish calls | bullish precision % |
|---|---|---|---|---|---|---|---|---|
| v6 | 1,168 | 28.3 | 25.7 | +2.64 | 84 | 59.5 | 397 | 38.0 |
| B, +3 mapping (pre-registered) | 1,169 | 29.9 | 25.8 | +4.07 | 161 | 60.9 | 242 | 41.3 |
| B, +2 mapping (train run's original) | 1,169 | 33.4 | 30.7 | +2.62 | 161 | 60.9 | 655 | 36.2 |

v6's row reproduces the published tune reference exactly (28.3% / +2.64 / 84 / 59.5%, `v6_reference_repro_tune.json`). The +2 mapping's accuracy is higher only because it puts 56% of calls in the bullish bucket; its gap (+2.62) is the same as v6's.

### Flips against v6, raw and net (P6 §7 netting rule, tune noise arm)

| mapping | shared calls | raw flips | expected noise flips (S1–S5 re-weighted) | net flips | noise-count range | raw flip win rate % | noise win rate % | netted win rate |
|---|---|---|---|---|---|---|---|---|
| +3 (pre-registered) | 1,168 | 341 | 207 | **134** | 158 to 268 | 32.0 (wins 109, losses 91, both wrong 141) | 20.5 | 49.8, **unstable: net does not exceed the noise range's top (268)** |
| +2 (train run's) | 1,168 | 464 | 207 | 257 | 158 to 268 | 35.1 (wins 163, losses 104, both wrong 197) | 20.5 | 47.0, **unstable** |

"Win" = B is right and v6 is wrong. Caveat (netting rule): noise flips and real flips are not disjoint; the subtraction assumes independence.

### B vs v6 disagreement (+3 mapping)

| v6 answer → B answer | n | B right % | v6 right % | median return |
|---|---|---|---|---|
| bearish → bearish | 58 | 63.8 | 63.8 | −9.02 |
| bearish → neutral | 26 | 11.5 | 50.0 | −5.34 |
| neutral → bearish | **98** | **58.2** | 13.3 | −5.78 |
| neutral → neutral | 558 | 19.7 | 19.7 | −4.76 |
| neutral → bullish | 31 | 22.6 | 22.6 | −5.84 |
| bullish → bearish | 5 | 80.0 | 20.0 | −10.93 |
| bullish → neutral | 181 | 21.0 | 31.5 | −3.29 |
| bullish → bullish | 211 | 44.1 | 44.1 | 1.97 |

The one group that matters most replicates from train: the 98 calls v6 called neutral and B called bearish were right **58.2%** of the time against a 48.3% base rate (train: 112 calls, 62.5%). B's added bearish coverage is not diluting precision. B's neutral answers on calls v6 called bearish (26) were right 11.5% vs v6's 50.0%, so B gave up some of v6's bearish calls.

### Money (tradeable entry, 182 days, points vs the S&P)

| mapping | arm | bearish share % | bearish mean | bearish median | bullish share % | bullish mean | bullish median | swap mean | swap median |
|---|---|---|---|---|---|---|---|---|---|
| v6 | A | 7.2 | −0.88 | −8.46 | 34.0 | 1.45 | −0.71 | 2.33 | 7.75 |
| +3 (pre-registered) | B | 13.8 | −5.93 | −7.71 | 20.7 | 3.40 | 0.63 | 9.33 | 8.34 |
| +2 (train run's) | B | 13.8 | −5.93 | −7.71 | 56.0 | 0.90 | −1.32 | 6.83 | 6.39 |

At the train run's +2 mapping the swap median is 6.39 with a range of **−0.16 to 10.33**, which touches zero. Only the pre-registered +3 mapping clears zero (lower end 1.46).

**By stratum and year (swap median, points), +3 mapping vs v6:**

| slice | v6 swap median | B swap median | v6 bearish n / median | B bearish n / median |
|---|---|---|---|---|
| S1 | −2.64 | 5.41 | 17 / −0.58 | 44 / −6.32 |
| S2 | −8.46 | 8.47 | 33 / +3.97 | 54 / −8.73 |
| S3 | 12.51 | 10.26 | 31 / −12.77 | 45 / −9.30 |
| S5 | 37.91 | 6.52 | 3 / −35.39 | 18 / −3.08 |
| 2020 | −12.83 | 0.66 | 3 / +16.20 | 16 / +1.32 |
| excl. 2020 | 6.48 | 8.33 | 81 / −8.78 | 145 / −7.89 |

S4 has no tune calls. B's swap is positive in every stratum and better than v6's in S1 and S2. It is lower in S3 and S5, where v6 has few bearish calls (S5: 3) with extreme returns. 2020, reported separately, is near zero for B (0.66) and strongly negative for v6 (−12.83, three bearish calls).

**Length:** median completion 511 tokens for B, 2,462 for v6 (from the 248 noise re-scores).

---

## Pooled train + tune

2,386 calls from 106 companies: train 1,217 (PARA excluded) plus tune 1,169. The state of play's 2,385 equals 1,217 + 1,168, the old-ruler-gradable tune count; this pool is one call larger because one tune call has a tradeable-entry return but no old-ruler truth.

| pooled figure | value | 95% range |
|---|---|---|
| B rank correlation (Spearman) | **0.135** | 0.087 to 0.184 |
| B swap median, score ≤ −2 / ≥ +3 | **10.50** | 6.30 to 13.64 |
| B swap median, score ≤ −2 / ≥ +2 (train run's mapping) | 8.12 | 4.19 to 11.19 |
| v6 swap median | 7.70 | 0.51 to 12.30 |
| v6 swap mean | 2.45 | −7.17 to 13.25 |

The state of play quotes v6 at +8.7 (median) and +2.4 (mean). The mean reproduces; **my pooled v6 median is 7.70, not 8.7, and I have not reconciled the 1.0-point difference.** The state-of-play figure was computed in a different session on a population I did not re-derive. The B-vs-v6 comparison in this report uses the 7.70 computed here on the same calls.

---

## Noise arm: was v6's cached baseline a lucky draw?

250 v6 re-scores drawn proportional to the tune S1–S5 mix (S1 77, S2 46, S3 108, S5 19). 248 form usable pairs. **Two were dropped and both are legitimate:** ACN 2022-03-17 (the fresh v6 output's structured block did not parse) and ETN 2025-05-02 (an Investor Day transcript; v6 replied by asking which analysis was wanted, and the cached call also has no direction).

Disagreement with the cached call: **44 of 248, 17.7% (Wilson 13.5 to 23.0)**, in line with train's 16.7% and Test 4's 12.8%.

| stratum | n | flips | rate % | Wilson |
|---|---|---|---|---|
| S1 | 76 | 17 | 22.4 | 14.5 to 32.9 |
| S2 | 46 | 5 | 10.9 | 4.7 to 23.0 |
| S3 | 107 | 21 | 19.6 | 13.2 to 28.1 |
| S5 | 19 | 1 | 5.3 | 0.9 to 24.6 |

No stratum's range excludes the overall rate.

**Cached call vs fresh call, among graded noise flips where exactly one was right:**

| set | graded flips | cached call right | fresh call right | both wrong | sign-test p |
|---|---|---|---|---|---|
| tune (this run) | 44 | 17 | 9 | 18 | 0.169 |
| train (P6 run) | 20 | 6 | 3 | 11 | 0.508 |
| pooled | 64 | 23 | 12 | 29 | **0.090** |

**Plain answer: the evidence leans toward v6's cached baseline being a somewhat lucky draw, and it is still too thin to say.** The direction is the same in both splits (cached right about twice as often as fresh) and the pooled test sits at p=0.09, short of the usual 0.05 bar with 35 decisive flips. If it is real, v6's cached accuracy and gap are slightly flattering, which would make B's old-ruler result against v6 slightly conservative. Nothing in the four conditions depends on it: conditions 1 to 3 do not use v6's accuracy.

---

## What this means, both ways (not decided here)

**B held.** B is the working analyst candidate on this evidence: two independent splits, 106 companies, rank correlation 0.135 pooled (0.087 to 0.184), bearish coverage about double v6's at equal or better precision, a swap whose median is clear of zero at the pre-registered mapping, at roughly a fifth of v6's length. The questions this opens go to the design session:

- **Which v6 structured fields the allocator still needs**, and how B's score and those fields coexist. B's output has only `summary`, `score`, `noRead` and `wrongIf`; everything else v6 emits (thesis health, stumble type, ratchet inputs) is gone.
- **The bullish side.** B's bullish bucket at the +3 mapping is 242 calls with precision 41.3% and median +0.63 against the S&P, small and positive; at +2 it is a resting bucket with no edge. It has a small positive edge at best.
- **The mapping.** The pre-registered +3 mapping is the only one whose money range clears zero, and it enlarges the neutral pile above v6's. Thresholds are an allocator-side decision on `calls_tune.csv` and the train `calls.csv`.
- **The score's resolution below +1.** The buckets from −4 to +1 are flat; the score does not yet grade how bad a bad call is.

**Had B failed**, the queue would have reverted to the 2026-09-23 state of play §3 with P6 recorded as a train-only result. It did not fail, and no condition failed narrowly except that condition 3's lower bound (1.46) is close to zero.

---

## Premise flags, deviations, what was not done

**Premise flags (recorded in `findings.md` at Step 0):**
1. v6's tune **84 bearish / 59.5%** is documented in `wrap-ups/q2-bearish-strength-separation-out.md` §5b, not in `baseline-v6-tune-batch-out.md` (which carries 28.3% / +2.64 / 1,168 gradable). Both reproduced exactly (0g).
2. The prompt's "51–54 companies": the answer is 51. WOLF and SPWR are the two named exclusions. **BNY (BK) has 0 transcripts**, a documented vendor gap (`baseline-v6-tune-batch-out.md` §2). My first 0f assert treated it as a failure; I loosened it to record BNY as an expected empty company, in its own driver commit before any output, exactly as MAXN is handled on train.
3. `selection.json`'s `seeds` field prints the train seed names. The seeds actually used were `p6b-tune-preflight-11` and `p6b-tune-noise-11` (the protocol JSON is correct). Cosmetic manifest defect, not fixed to keep the committed file unchanged.
4. The prompt leaves condition 4's "noise band" and several "same calls" definitions open; my reading of each was written in `findings.md` before any tune result existed.

**Deviations:**
- The 50 pre-flight scores are reused as arm-B results, and the full-arm batch submitted only the remaining 1,119 transcripts (Step −1's skip-present-ids rule, as in the P6 run).
- Eval cache `analysis/data/evals/P6B-minimal_claude-sonnet-4-6_tune/` is gitignored like the others; `scores_b_tune.jsonl` and `scores_noise_tune.jsonl` carry identical content and are committed.
- The noise arm's fresh scores are in `scores_noise_tune.jsonl`; the v6 tune cache is untouched.

**Closure of a P6-run incident.** The P6 wrap-up said the duplicate batch's billed amount was unconfirmed. Its final counts are **canceled 1,237, succeeded 0**: no spend. That supersedes the P6 wrap-up's "unconfirmed" note. Nothing similar happened here: I ran one process at a time, wrote every batch id before doing anything else, and listed batches after submission (exactly two new in-progress batches).

**Not done:** no promotion, no registry `promoted_version` change, no threshold search beyond the two pre-registered mappings, no arm C on tune, no P7/P8, no holdout, no cache refresh, no DB writes.

**Left for the design session:** the four questions under "B held" above; the unreconciled 1.0-point difference in the pooled v6 swap median; whether a larger noise arm is worth buying (35 decisive flips leave p=0.09).

## Provenance and artifacts

Driver `analysis/p6_output_format_driver.py --split tune`; analysis `analysis/p6_output_format_analysis.py --split tune` (each committed before it produced output). State in `analysis/data/run_state/p6b-tune-confirmation/`: `progress.json`, `findings.md`, `scores_b_tune.jsonl`, `scores_noise_tune.jsonl`, `calls_tune.csv` (with `b_dir_plus2` and `b_dir_plus3`), `v6_reference_repro_tune.json`, `results_tune.json`, `tests_report_tune.md`, `per_call_diffs_tune.csv`. Protocol `analysis/data/corpus_v2/SCORING_PROTOCOL_P6B_TUNE.json`. Returns: `rel_ret` arm "B" (first close strictly after the call date), 182 days, SPY, `analysis/data/corpus_v2/scorer_price_cache_v1.json`. Every range is a ticker-block bootstrap, 2,000 draws, seed 11. Medians and means are across calls.

```bash
# reproduce everything from the scores on disk ($0)
python3 analysis/p6_output_format_analysis.py --split tune ref
python3 analysis/p6_output_format_analysis.py --split tune calls
python3 analysis/p6_output_format_analysis.py --split tune tests
```
