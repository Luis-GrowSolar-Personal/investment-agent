# P9 — expected return in points, from B, on train. Wrap-up

**Run ID:** `p9-expected-return-train`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial.**
**Real spend: $30.17** (1,217 calls, `cost_usd` summed over `scores_p9.jsonl`, pre-flight included), under the $40 cap Luis approved at Step 0 (recorded in `progress.json`). No second draw was run.
**Scope boundary: report, do not decide.** No champion change, no tune, no second draw, no mapping or allocator work.

> On the 1,217 train calls, the expected-return prompt's number pointed the right way (slope **0.66**, range **0.33 to 0.96**); it ranked calls at **0.171**, a paired difference of **+0.040** (range **−0.016 to +0.097**) against B draw 1 and **+0.071** (range **+0.016 to +0.126**) against draw 2; its bottom 191 were right **62.8%**. Of the three gates, **3** held against both draws. On severity it is **better information**: inside the bearish group it ranked outcomes at **0.257** (range 0.094 to 0.373) against B's **0.081** / **0.145** (both ranges include zero), and its lowest fifth returned a median **−9.76** against **−5.52** for the second fifth. **P9 is ambiguous under the pre-registered rule.**

Source for every figure: `analysis/data/run_state/p9-expected-return-train/results.json`, keys named below. "Right" = the tradeable-entry 182-day truth matched (bearish for the bottom cut, bullish for the top). Ranges: Wilson for rates, 95% ticker-block bootstrap (2,000 draws, seed 11) for correlations and slopes. Groups: bottom 191 / top 235 by `expectedReturn`, ties by the seeded rule.

## Why "ambiguous" although all three gates held

The pre-registered ambiguity rule: if gates 1 and 3 hold and gate 2's lower end lands between −0.06 and 0.00 against **either** draw, one draw cannot settle it. Gate 2's lower end against draw 1 is **−0.016**, inside that band (`ambiguity.triggered: true`). So the verdict is ambiguous, not "earns its look". The point estimate is above B on both draws and draw 2's range is entirely above zero, so the ambiguity is about whether P9 is *clearly* not worse than B's better draw, not a sign that it is. **Per the prompt, a second P9 draw (~$30) is recommended and was not run. The decision is Luis's.**

## The gates

1. **Calibration sign: HELD.** Clipped slope (realized return clipped at ±50, 76 calls clipped) **0.662**, range **0.332 to 0.959**, entirely above zero. Unclipped: 0.957 (0.353 to 1.492) (`calibration`). The clipped value is the allocator-side scale factor: a stated +10 goes with about +6.6 realized, on average.
2. **Ranking non-inferiority: HELD against both.** vs draw 1: +0.040 (−0.016 to +0.097); vs draw 2: +0.071 (+0.016 to +0.126). Lower ends against the −0.03 tolerance (`gates.gate2`). P9's rank correlation **0.171 (0.085 to 0.251)**; B 0.130 (0.051 to 0.208) and 0.099 (0.025 to 0.170) (`rank`).
3. **Bearish hits: HELD.** Bottom 191 right **62.8%** (55.8–69.4), median −9.92; B 62.3% / 61.3% (`bottom191`).

Top 235 (reported, not gated): P9 **40.4%** right, median +1.28; B 39.6% (+1.28) and 36.2% (−1.79) (`top235_not_gated`). No difference worth reading.

## Severity (reported, not gated)

- **(a) inside the bottom 191:** P9 **0.257** (0.094 to 0.373), range excludes zero. B draw 1: 0.081 (−0.094 to 0.301, 4 distinct scores in the group); draw 2: 0.145 (−0.019 to 0.288, 5 distinct scores). As pre-registered, B's ranges are wide and its scores heavily tied, so P9 beating B's point estimates means little by itself; the reading rests on P9's own range excluding zero.
- **(b) realized median return by fifth, lowest to highest:** P9 `expectedReturn` **−9.76, −5.52, −0.95, −1.63, +1.54**; B draw 1 score −7.98, −4.23, −1.81, −2.71, +0.73; B draw 2 −7.31, −4.30, −1.20, −2.05, −1.82 (`severity`). The lowest fifth is below the second, as required. The middle two fifths are not monotone, for P9 or B. (Fifths of B's tied scores are split by the seeded tie rule.)
- **Pre-registered reading: both conditions hold, so P9 grades severity ("better information")**, on this one draw. The severity claim inherits the same single-draw caveat as the gates.

## Distribution and calibration (`distribution`, `range_coverage`)

- `expectedReturn`: median **+5.0**, **75.3% positive** (23.3% negative), middle half **2 to 8 (span 6)**, 25 distinct values. Most common: 8 (233 calls), 5 (230), −5 (108), 4 (104), 6 (99), 3 (87), −8 (83), 12 (65). Realized: median −2.94, middle half span 24.0. The model's numbers are coarse and mildly optimistic, as B's were.
- Stated ranges (median width 32 points) contained the outcome **60.9%** of the time against the 80% asked. Wider ranges go with bigger misses: rank correlation of width with absolute error **0.326**.
- One noRead call (B draw 1: 3).

## Flips against B, and the rest

- Direction groups (P9 bottom 191 / top 235 vs B's ≤ −2 / ≥ +3): raw changes **301 (24.7%)** against draw 1, 304 (25.0%) against draw 2; expected from B's own noise 152; net ~149–152. Decisive flips won 98 of 196 (50.0%) and 107 of 203 (52.7%). Netted win rate is **unstable and not a headline** under the P3 §7 guard (net not above B's noise upper of 176) (`flips`).
- Direction table, B draw 1 (rows) by P9 group (bearish / neutral / bullish): bearish 132 / 55 / 4; neutral 58 / 643 / 90; bullish 1 / 93 / 141. Draw 2: 131/47/5; 59/646/94; 1/98/136 (`table_3x3_*`).
- Per stratum, rank correlation P9 vs B draw 1: S1 0.199 vs 0.184; S2 −0.001 vs −0.061; S3 0.160 vs 0.089; S5 0.314 vs 0.249; S4 16 calls, not readable (`per_stratum`). By year: 2020 P9 0.175 (B 0.031 / 0.009); ex-2020 0.170 (B 0.149 / 0.115) (`by_year`).
- Cost **$0.0248/call**, +5% vs B's $0.0236; median 630 completion tokens (B ~517). Parse: 1,217 of 1,217, 0 `max_tokens`, 0 range-order violations. Per-call diffs: `per_call_diffs.csv`.

## Pre-flight

150 calls (`preflight_report.json`): no stop rule tripped. Middle half [0.5, 8.0] (span 7.5), 18 distinct values, 74.7% positive, noRead 0%, range order broken 0, projected full cost $29.82 (actual full $30.17).

## Predictions, not gates (`predictions`)

Held: median +2 to +8 (5.0), middle half span 6–15 (6.0, at the edge), range coverage 50–70% (60.9%), cost within ±15% of B (+5%). **Missed:** share positive 55–75% (75.3%, just above); clipped slope 0.2–0.6 (0.66, above); rank correlation 0.10–0.15 (0.171, above). All three misses are in P9's favour or marginal.

## Flags, deviations, premises

1. **Approval:** this invocation gave no explicit spend approval; I asked, and Luis approved the $40 cap. Recorded in `progress.json`.
2. **Candidate diff against B:** identical from "You are an experienced investor" through the end of READ (verified before registration); differences are the header comment, EXPECTED RETURN in place of SCORE, the three structured fields replacing `score`, and reworded field definitions. sha256 `a752e6b1b2a00b755396a526bfe3007e788ebfb6a93b32076754cd0e078c06a5`, registered before scoring.
3. **A wording note, not a deviation:** the candidate's EXPECTED RETURN text contains, besides the pre-registered base-rate sentence, "a weak read belongs close to 0, and a large number needs strong evidence". The prompt says a second *base-rate* clause ("a typical call does not move the odds much") was cut; this different sentence remains. It is in the sha that ran and may be part of why P9's numbers cluster; not tested.
4. **Pre-registration** was copied into `PROMPT_ARCHITECTURE.md` §2.2 under P9 in its own commit (`a9664a1`) before any scoring; the P9 row reads "registered — running". It was **not** updated to the result afterward (design-session edit). No registry status change, no ledger entry (none was asked for).
5. Request shape asserted identical to B's `make_request()` except system text on 25 sampled calls (`request_shape_check.json`); no temperature parameter.
6. The two untracked P9 files present at start (`prompts/P9-expected-return.md`, the candidate file) were committed with the registration, as they are this run's inputs.
7. Batch ids: preflight `msgbatch_01SFeXcY9T1v5D3qAd4wopLp`, full `msgbatch_01NCiZsivaiX6phgtTqpfGZm`, both committed at creation.

## What this means

**Ambiguous under §4's rule, with a favourable lean.** All three gates held and both severity conditions hold, so on this single draw P9 looks like *better information* than B, not only better units: it ranks outcomes inside the bearish group, which B's tied scores cannot, and its number is calibrated in sign with a usable scale (0.66). The one thing a single draw cannot settle is whether its ranking is clearly no worse than B's better draw (lower end −0.016 vs a −0.03 tolerance and B's own wobble of 0.031). If Luis wants the second draw (~$30, both draws must pass), that is the pre-registered way to close it; if it also holds, tune is next with the same gates at 242 / 161. Whether to go to tune on one draw is Luis's call, not mine. If instead P9 were dropped, B's −5..+5 score stays the output and severity remains an open gap.

## Not done

No second draw, no tune, no champion change, no allocator work, no update of the P9 row to its result, no DB writes, no cache refresh.

```bash
python3 analysis/p6_output_format_driver.py --p9 p9-check
python3 analysis/p9_expected_return_analysis.py
```
