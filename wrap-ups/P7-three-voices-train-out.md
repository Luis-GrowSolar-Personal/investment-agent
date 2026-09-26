# P7 — three voices, from B, on train. Wrap-up

**Run ID:** `p7-three-voices-train`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial:** pre-flight, full round, every gate and diagnostic ran.
**Real spend: $34.07** (1,217 calls, `cost_usd` summed over `scores_p7.jsonl`, pre-flight included), against the prompt's $45 hard cap. Luis's chat approval was "up to $50"; I held the prompt's tighter $45 cap. Committed estimate peaked at $33.42. No second draw was run.
**Scope boundary: report, do not decide.** Not registered as champion; no tune, no second draw, no P9.

> On the 1,217 train calls, the three-voices prompt's top 235 calls were right **31.5%** of the time, against B's 39.6% and 36.2% on its two draws; its ranking strength was **0.113**, a paired difference of **−0.017** (range **−0.050 to +0.016**) over B draw 1 and **+0.014** (range **−0.017 to +0.046**) over draw 2; its bottom 191 were right **58.6%**. Of the three gates, **1** held against both draws. **P7 was falsified on gate 1.**

Source for every figure: `analysis/data/run_state/p7-three-voices-train/results.json` (keys named). "Right" = the call's tradeable-entry 182-day truth matched the direction (bullish for the top cut, bearish for the bottom); ranges are Wilson (rates across calls) or 95% ticker-block bootstrap (rank correlations; 2,000 draws, seed 11).

## The gates (each against both B draws)

1. **Bullish hits, top 235, at least 47.0%: FAILED.** 31.5% (Wilson 25.9–37.7), median return −2.46. This is 15.5 points under the target and below both B draws (39.6%, 36.2%), so it is not inside the §5d ambiguity band (43.6–50.4%). Absolute target, identical against both draws. `gates.gate1_*`, `matched_coverage.P7.top235`.
2. **Ranking, lower end no worse than −0.03: FAILED against draw 1, held against draw 2 → does not hold against both.** vs draw 1: −0.017 (−0.050 to +0.016); vs draw 2: +0.014 (−0.017 to +0.046). `gates.gate2`.
3. **Bearish hits, bottom 191, at least 57.0%: HELD.** 58.6% (51.6–65.4), median −8.09; B was 62.3% / 61.3%. `gates.gate3_*`.

**Pre-registered rule: gate 1 failed, so P7 is falsified for its purpose (a bullish signal) and does not go to tune.** P7's rank correlation was 0.113 (0.033–0.189), against B's 0.130 and 0.099.

**§5d ambiguity rule, stated plainly:** gate 1 is not ambiguous. Gate 2's lower end against draw 1 (−0.050) does sit in the −0.06 to 0.00 band, so the rule's second trigger fires literally. It cannot change the verdict, because gate 1 alone falsifies. I did not run, and do not recommend, a second draw for that reason; the decision is Luis's.

## The group that matters: B neutral, P7 top 235

Calls B scored −1 to +2 that P7 put in its top 235 (bullish base rate 33.2%, `base_rates_pct`):

| | calls | right | median return |
|---|---|---|---|
| vs B draw 1 | 83 | **22.9%** (15.2–33.0) | −3.95 |
| vs B draw 2 | 87 | 28.7% (20.3–39.0) | −2.27 |

Both are **below** the 33.2% base rate. The mirror, B's top 235 that P7 dropped: draw 1, 83 calls, **45.8%** right (35.5–56.5), median +3.77; draw 2, 87 calls, 41.4%, median +2.42. In short, P7 swapped a better group of bullish calls for a worse one (`neutral_to_top235`). Shared top-235 calls with B: 152 (draw 1), 148 (draw 2).

## `gap` and `gap × pressure`

`gap` shares: **claims_ahead 78.8%, aligned 14.1%, numbers_ahead 7.1%**. `pressure`: **avoided 79.7%, answered 20.0%, none 0.3%**. Both far from the pre-registered predictions (30–45 / 35–50 / 10–25; answered 40–60): the model calls nearly every call "claims ahead, pressed questions avoided" (`shares_pct`).

| gap | calls | bullish-truth rate | bearish-truth rate | median return |
|---|---|---|---|---|
| numbers_ahead | 86 | 30.2% | 39.5% | −2.12 |
| aligned | 172 | 32.6% | 33.7% | −1.94 |
| claims_ahead | 959 | 33.6% | 47.1% | −3.71 |

`numbers_ahead` does **not** carry a bullish edge: 30.2% against a 33.2% base. The differences across gap values are small and mostly within sampling spread; `claims_ahead` has the higher bearish rate (47.1% vs 44.7% base, a mild lean).

`gap × pressure` (calls; bullish-truth rate; median return): numbers_ahead+answered 55; **25.5%**; −3.03 · numbers_ahead+avoided 30; 40.0%; −0.08 · aligned+answered 112; 29.5%; −2.88 · aligned+avoided 58; 37.9%; +3.07 · claims_ahead+answered 76; 32.9%; −3.91 · claims_ahead+avoided 882; 33.7%; −3.63. Cells with `none` have 1–2 calls. **The predicted carrier cell, numbers_ahead + answered, is 55 calls at 25.5%, below base: the prediction did not hold.** Note `pressure` "answered" calls average a higher score (2.14) than "avoided" (0.41), yet their bullish-truth rate is lower (29.6% vs 34.1%): the score is being driven by the wrong thing (`by_pressure`, `gap_x_pressure`).

## Flips, raw and net

| vs | raw direction changes | expected noise (B's per-stratum rates) | net | decisive | P7 won | raw win rate | netted win rate |
|---|---|---|---|---|---|---|---|
| B draw 1 | 213 (17.5%) | 152.0 | 61.0 | 144 | 58 | 40.3% | unstable (guard failed: net not above B's noise upper 176) |
| B draw 2 | 219 (18.0%) | 152.0 | 67.0 | 151 | 67 | 44.4% | unstable |

Prediction was 250–400 raw and ~100–250 net: **raw 213 is below it and net 61–67 is below it** (finding). Netted win rate uses B's 55.4% noise win rate and is **not a headline** under the P3 §7 guard (net under 100). P7's raw flips against B were won on 40–44% of decisive flips, which is below half. `flips`.

**Direction tables** (rows B, columns P7; bearish / neutral / bullish). Draw 1: bearish 161 / 30 / 0; neutral 54 / 706 / 31; bullish 0 / 98 / 137. Draw 2: 158 / 25 / 0; 57 / 707 / 35; 0 / 102 / 133. P7 moved 98 of B's bullish calls to neutral and only 31 neutral calls to bullish: it made **fewer** bullish calls (168 at ≥ +3 vs 235), not more. `table_3x3_B1_by_P7`, `table_3x3_B2_by_P7`.

## The rest (diagnostics)

- **Fixed cuts (secondary):** ≥ +3: 168 calls, 32.1% right, median −2.41; ≤ −2: 215 calls, 58.6% right, median −8.64. `fixed_cuts_secondary`.
- **Score buckets (`buckets`):** medians −8.05 at −2, −6.54 at −1, −2.37 at +1, +0.29 at +2, −2.35 at +3 (163 calls): the top bucket is **below** the +2 bucket. Ordering is broken at the top, which is where a bullish signal has to live.
- **Predictions:** rank correlation 0.12–0.17 missed (0.113); top-235 median above +1.28 did not hold (−2.46); cost +10–25% held (**$0.0280 vs B $0.0236, +19%**, median 1,036 completion tokens vs B ~517).
- **Per stratum (`per_stratum`, rank correlation P7 vs B draw 1):** S1 0.098 vs 0.184; S2 −0.034 vs −0.061; S3 0.105 vs 0.089; S5 0.167 vs 0.249; S4 16 calls, not readable. Direction change vs B: S1 18.0%, S2 20.3%, S3 16.8%, S5 16.1%.
- **By year (`by_year`):** 2020 (162 calls): P7 −0.003, B1 0.031, B2 0.009; ex-2020 (1,055): P7 0.132, B1 0.149, B2 0.115. No year where P7 is clearly ahead.
- **noRead:** 4 of 1,217 (0.3%), B draw 1 3 (0.2%).
- Parse: 1,217 of 1,217, 0 `max_tokens`, 0 out-of-set `gap`/`pressure` on the full round. Per-call diffs: `per_call_diffs.csv`.

## Pre-flight, and one thing to notice

Pre-flight (150 calls, `preflight_report.json`): disagreement with B draw 1 was **20.7%**, against a 20% stop threshold, so the full round ran by 0.7 point. Across the full set it was 17.5%. The pre-flight `gap`/`pressure` skew (84% claims_ahead, 87% avoided) already contradicted the predictions and the full round confirmed it. The pre-flight stop rule tested disagreement, and disagreement was there; it was not the same as improvement.

## Flags, deviations, premises

1. **The candidate as drafted was not "B plus one section".** `EVALUATION_PROMPT_P7_three_voices.md` had replaced B's objective sentence ("What in this call should change what a well-informed holder believes? Say what it is and why it matters.") with "A call has three voices…". I stopped and asked Luis, who chose to restore B's two lines verbatim and keep the "three voices" line as the first line inside VOICES. **Diff against B after the fix:** the body differs only by the added VOICES section, the `gap` and `pressure` fields in the structured block, and their two field definitions (plus the comment header). New sha256 `0a34f5a926f6be89400a8191cac5455f0b5cd11d2bef8a51d3a6b97510b2bcaf`, registered under `P7-three-voices` (parent P6B-minimal) before any scoring. The draft's earlier sha (`ae563048…`) never scored anything.
2. **Cap:** the prompt says $45, the chat approval said $50. I held $45 (`progress.json` → `cap_usd`, `luis_approved_usd` 50).
3. **Pre-registration** copied into `PROMPT_ARCHITECTURE.md` §2.2 under P7 and the row marked "registered — running" in its own commit (`0998735`) before the pre-flight batch. **Not done:** the row was not updated afterward to "falsified"; that is a design-session edit.
4. **Request shape:** asserted identical to B's `make_request()` except the system text, on 25 sampled calls (`request_shape_check.json`); no temperature parameter.
5. The `--p7` driver path also reuses the pre-flight's 150 rows (no call scored twice).
6. Batch ids: preflight `msgbatch_01Q4cN16FSjCeDgM3c9XsDw7`, full `msgbatch_01LbWxKqan2jVMds6pAqPcTh`; both committed in `progress.json`.

## What this means

**Gate 1 failed**, so the three-voices mechanism as written does not find winners in a transcript on train: its top 235 were right less often than B's on either draw, its top score bucket had a lower median return than the bucket below it, and the calls it added to the top group were right less often than the base rate. Its bearish side held (gate 3) and its ranking is statistically close to B's, so it lost nothing large; it simply gained nothing on the bullish side. Per the prompt: **P9 is next**, and the bullish question may need information from outside the transcript (consensus, or P4's XBRL facts). Whether the model's near-uniform "claims ahead / avoided" labels point at a prompt-wording problem rather than a mechanism problem is a question for the design session; I did not test it, and running a wording variant would be a new candidate with its own pre-registration.

## Not done

No tune scoring, no second P7 draw, no champion change, no P9 pre-registration, no update of the P7 row to its result, no DB writes, no cache refresh.

## Follow-up

```bash
python3 analysis/p6_output_format_driver.py --p7 p7-check
python3 analysis/p7_three_voices_analysis.py
```
