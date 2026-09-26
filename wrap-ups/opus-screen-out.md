# Opus screen. Wrap-up

**Run ID:** `opus-screen`. Branch `sweep/db-corpus-baseline`. **Complete run.**
**Real spend: $14.06** (300 calls incl. the 30-call pre-flight, `cost_usd` in `scores_b_opus.jsonl`) against the $50 cap Luis approved at Step 0 (recorded in `progress.json`; approval asked and given in chat). The pre-flight projected $13.62.
**Scope boundary: report, do not decide.** This is a screen, not the §2.2b model gate. No registry change (promoted model stays `claude-sonnet-4-6`), no model change, no full Opus run.

> On 300 train calls, B's prompt run on Opus changed direction against Sonnet's two runs on **33.3%** and **35.0%** of calls; Sonnet changed direction against itself on **15.0%** of the same calls. The difference is **+19.2 points** (range **+12.4 to +25.9**): **reads differently — worth a full test**. Opus cost **$0.0469** per call against Sonnet's $0.0236.

Source: `analysis/data/run_state/opus-screen/results.json` (keys `1_…`–`6_…`), script `analysis/opus_screen_analysis.py`. Mapping ≤ −2 bearish, ≥ +3 bullish, else neutral. Ranges: Wilson for rates; 95% ticker-block bootstrap (2,000 draws, seed 11, all three rates recomputed on each resample) for the screen figure. Selection: 300 train calls, stratified (S1 88, S2 47, S3 133, S4 4, S5 28), seed `opus-screen-11`, 43 big winners (≥ +20) and 59 big losers (≤ −20) (`selection.json`, committed before scoring).

**Say plainly: one Opus draw cannot tell "reads differently" from "noisier".** The pre-registered reading is only "worth a full test", not "better".

## Results

**1. Direction disagreement** (`1_direction_disagreement`)
| pair | disagree | Wilson |
|---|---|---|
| Opus vs B draw 1 | 100 of 300 (33.3%) | 28.2–38.8 |
| Opus vs B draw 2 | 105 of 300 (35.0%) | 29.8–40.6 |
| B draw 1 vs B draw 2 (Sonnet's own noise, same calls) | 45 of 300 (15.0%) | 11.4–19.5 |

**2. The screen figure** (`2_screen_figure`): mean of the two Opus-vs-Sonnet rates 34.2% minus Sonnet-vs-Sonnet 15.0% = **+19.2 points, range +12.4 to +25.9** (2,000 valid draws). Entirely above zero → **"reads differently — worth a full test"**. **The prediction ("nothing new", within 3 points) did not hold**; a diagnostic that contradicts the prompt's expectation, reported as a finding.

**3. Score moved** (`3_score_moves`)
| pair | ≥ 1 point | ≥ 2 points |
|---|---|---|
| Opus vs B1 | 65.3% (59.8–70.5) | 25.3% (20.7–30.5) |
| Opus vs B2 | 63.7% (58.1–68.9) | 25.0% (20.4–30.2) |
| B1 vs B2 | 29.3% (24.5–34.7) | 8.3% (5.7–12.0) |

**4. Direction tables** (rows B, columns Opus; bearish / neutral / bullish; `4_tables_rows_B_cols_opus`)
- Opus by B draw 1: bearish 49 / 6 / 0; neutral 32 / 143 / 0; bullish 2 / 60 / 8.
- Opus by B draw 2: bearish 48 / 8 / 0; neutral 33 / 140 / 1; bullish 2 / 61 / 7.

**The disagreement has a shape, not just a size.** Direction counts on the 300 (`5_direction_counts_all_300`): Opus **83 bearish / 209 neutral / 8 bullish**; B draw 1 55 / 175 / 70; draw 2 56 / 174 / 70. Opus moved 60 of B's 70 bullish calls to neutral and 32 of B's neutral calls to bearish; it almost never went the other way (2 bullish→bearish, 0 neutral→bullish on draw 1). So a large part of the "disagreement" is a shift of the whole scale downward (Opus rarely reaches +3), not random scatter around B's answer. A single draw cannot say whether that is a different reading, a lower-scoring habit, or both.

**5. Reported, not read as evidence** (300 calls; about ±0.11 on any rank correlation)
- **Rank correlation with the 182-day return** (`5_rank_correlation`): Opus **0.270** (0.137 to 0.381); B draw 1 0.138 (0.004 to 0.251); B draw 2 0.123 (−0.016 to 0.244). Opus is higher; the ranges overlap.
- **Hit rates at matched coverage** (bottom 47 bearish / top 58 bullish; `5_matched_hits_bottom47_top58`): bottom 47: Opus 70.2% (56.0–81.3), B 66.0% and 74.5%. Top 58: Opus **48.3%** (35.9–60.8, median return +3.86), B 39.7% and 32.8%. Opus's top 58 includes calls scored +2 or below (only 8 calls reach +3), so its "top 58" is not a bullish pile in the mapping's sense.
- **Big winners in the sample** (43; `5_big_winners`): mean score Opus **0.42**, B 1.00 and 0.93. Scored bullish (≥ +3): Opus **4**, B 13 and 11. Scored bearish (≤ −2): Opus **11**, B 8 and 7. Opus did **not** see the big winners better on the scale it used; it scored them slightly lower.

**6. Cost, tokens, noRead** (`6_cost_tokens`): **$0.0469/call** (batch, $4 in / $20 out per million tokens × 0.5) vs $0.0236 Sonnet, so 2.0×. Median output 1,116 tokens (B on Sonnet ~517). noRead: Opus 1 of 300 (0.3%), B 0 of 300. 300 of 300 parsed, 0 `max_tokens` stops, every response reported `claude-opus-5-5` (`models_seen`).

## Recall caveat (one sentence)
Earlier look-ahead tests found no detectable recall on Sonnet but could only see large effects, and a larger, newer model may remember more, so any accuracy gain shown by Opus (rank 0.270, top-58 hit 48.3%) is suspect for that reason.

## Deviations, flags, premises
1. **The request is not "only the model string" in effect.** Per Anthropic's model notes, `claude-opus-5-5` cannot disable thinking, runs adaptive thinking by default (effort default `medium`), and B's request omits `thinking`. **All 30 pre-flight responses carried a thinking block** (`rows_with_thinking_blocks: 30`), and thinking tokens count against `max_tokens` 4096 and are billed (median output 1,116 tokens vs ~517 on Sonnet). The request was byte-identical to Sonnet's apart from the model (`opus-check`: prompt sha `d1fa5e53…`, no temperature or thinking key), but the two models therefore ran with different reasoning behaviour by default. This is part of what "Opus" means here and cannot be separated by this screen.
2. **Prices** ($4 / $20 per MTok, cache read $0.20, batch ×0.5) come from the claude-api skill's cached model table (2026-06-24); I did not verify them against the console. Cache writes were assumed at 1.25× ($5). Actual billing should be checked in the console; the cost per call in this report is computed, not billed.
3. **Approval:** no spend approval in the invocation; I asked and Luis approved the $50 cap.
4. The pre-flight's proportional draw within the 300 gave S4 zero calls (S1 9, S2 5, S3 13, S5 3); S4 has 4 calls in the 300.
5. Git bookends: prompt committed as its own commit; driver `--opus` path committed before any output; selection committed before scoring; batch ids `msgbatch_01KsK96zJqvCtZRcpYmG1Z7X` (pre-flight) and `msgbatch_01L2BRfhQbE7NmaaN6mjyXQM` (270) committed at creation. `MODEL` is overridden only under `--opus`.
6. Model string accepted by the API; no substitution.

## What this means
**Worth a full test, on the pre-registered rule.** Opus disagrees with Sonnet about twice as often as Sonnet disagrees with itself (34% vs 15%), with a range well clear of zero. **Not established:** that Opus reads better or even reads differently in content. Most of the disagreement is a downward shift of the scale (8 bullish calls of 300, against 70), and 300 calls cannot separate that from noise, from the default-thinking difference (flag 1), or from recall. Its higher rank correlation (0.27) is inside the ±0.11 resolution of this sample and is where the recall caveat applies. It did not score the big winners better.
**Price of the full test:** two Opus draws on all 1,217 train calls at the measured cost = 1,217 × $0.0469 × 2 ≈ **$114** (about $57 per draw; a third and fourth draw of B on Sonnet are not needed, B's two draws exist). The recall caveat applies with more force to any gain found there. Whether to spend it is Luis's decision, as is whether to first control for the thinking default.

## Not done
No full Opus run, no registry or model change, no §2.2b gate, no tune or holdout, no DB writes, no cache refresh.

```bash
python3 analysis/p6_output_format_driver.py --opus opus-check
python3 analysis/opus_screen_analysis.py
```
