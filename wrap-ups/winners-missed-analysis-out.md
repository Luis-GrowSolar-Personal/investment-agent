# Winners B missed. Wrap-up

**Run ID:** `winners-missed`. Branch `sweep/db-corpus-baseline`. **PARTIAL RUN, stopped by a pre-registered rule.** Step 1 is complete. Step 2 stopped at its pre-flight (2b). Step 2c/2d and Step 3 were **not run**.
**Real spend: $0.09** (60 pre-flight classifier calls, `cost_usd` in `read_labels.jsonl`) against the $12 cap Luis approved at Step 0 (recorded in `progress.json`).
**Scope boundary: report, do not decide.** No prompt changed, nothing promoted, no tune or holdout touched.

> Of 153 train calls followed by a gain of 20+ points over the S&P, B (draw 1) scored **35** bullish, **92** neutral and **26** bearish. Before the call, those winners had returned a median **−3.6** points over the prior six months, against **−2.2** for the middle group: **no rebound pattern**. Whether B saw the good news is **not answered**: the READ classifier failed its pre-flight (98% of B's READs came back "strong positive evidence", 95% "forward-looking positive"), so the full classification and the same-company pairs were not run.

## Step 1 — who are the winners ($0)

Definitions as fixed: big winner ≥ +20, big loser ≤ −20 (`fwd_rel_ret_tradeable`, tradeable-entry 182-day return vs SPY, points). 1,217 calls: **153 winners (12.6%, Wilson 10.8–14.6)**, 201 losers, 863 middle. Source: `analysis/data/run_state/winners-missed/results_step1.json`.

**1a. Score by outcome** (`1a_cross_draw1`, `1a_cross_draw2`). Winner share by B draw 1 score: −3 11.1% (3 of 27), −2 13.7% (22 of 161), −1 13.7% (25 of 183), +1 12.6% (21 of 167), +2 10.5% (46 of 438), +3 13.7% (31 of 226), +4 44.4% (4 of 9). The scale carries no gradient for winners: a −2 call is as likely to be a big winner as a +3 call. Draw 2 is the same picture (−2 15.3%, +1 8.0%, +3 14.0%).

**1b. Where the winners sit** (`1b_piles_draw1`; rate = winners inside the pile / pile size; base 12.6%):

| B draw 1 pile | calls | big winners in it | rate inside pile (Wilson) | share of all 153 winners |
|---|---|---|---|---|
| bearish (≤ −2) | 191 | 26 | 13.6% (9.5–19.2) | 17.0% |
| neutral (−1..+2) | 791 | 92 | 11.6% (9.6–14.1) | 60.1% |
| bullish (≥ +3) | 235 | 35 | 14.9% (10.9–20.0) | 22.9% |

No pile's rate differs from the 12.6% base; all ranges include it. Draw 2: 26 / 94 / 33 winners in bearish / neutral / bullish. **B's bearish pile holds as many winners, proportionally, as its bullish pile.**

**1c. By stratum and year** (B draw 1 bullish share of winners; `1c_*`): S1 12 of 36 (33%), S2 12 of 30 (40%), S3 **8 of 60 (13%)**, S4 0 of 2, S5 3 of 25 (12%). By year: 2020 5 of 30 (17%), 2021 7 of 22 (32%), 2022 6 of 21 (29%), 2023 7 of 18 (39%), 2024 3 of 20 (15%), 2025 7 of 42 (17%). S3 holds the most winners (60) and B catches the fewest of them; 2025 has the most (42, a third of B's rate elsewhere).
**Premise flag:** `calls.csv` has `tier = "NA"` for every call, so no by-tier table exists.

**1d. Before the call, own price history** (stock vs SPY, first close on/after call date − 182 days to the last close before the call; 1,215 of 1,217 calls have it, all 153 winners do; `1d_prior_by_outcome`):

| group | calls | median prior return | middle half | median's bootstrap range |
|---|---|---|---|---|
| big winners | 153 | **−3.56** | −17.84 to +13.56 | −7.80 to +2.18 |
| middle | 863 | −2.19 | −12.23 to +8.55 | −3.78 to −0.39 |
| big losers | 199 | −4.91 | −22.40 to +10.53 | −8.38 to −0.73 |

**Pre-registered reading: "no rebound pattern."** Winner minus middle is −1.4 points against the −15 needed, and the ranges overlap. Among B's bearish calls (`1d_bearish_calls`), the 26 that became big winners had a prior median of −22.8 (range −46.1 to −7.0) against −17.5 (−21.5 to −12.2) for the 163 that did not; the ranges overlap, so this is a lean, not a finding. The pre-registered reading has no rebound signal, so the stock's own price history is **not** indicated by this test as an input candidate.

## Step 2 — did B see it? STOPPED at the pre-flight

Classifier `docs/prompts/diagnostics/READ_CLASSIFIER_v1.md`, sha256 `99dd1107068f2a3ee23f4f9290706b1f4d97ee1c89dd5c20437fafeef36dda23` (recorded in `progress.json` before any call). It saw only B's READ paragraph: the `## SCORE` section (score, rationale, wrongIf) and the structured block were stripped and asserted absent for all 1,217; no ticker, date, return or group was supplied; calls were shuffled (seed 11); `claude-sonnet-4-6`, `max_tokens` 400, no temperature.

**Pre-flight (60 READs, stratified, `preflight_report.json`): the stop rule tripped.** The rule: stop if any one field takes one value on more than 85% of the 60 calls.

| field | distribution | most common value |
|---|---|---|
| positive | strong 59 / weak 1 / none 0 | **98.3%** |
| forwardPositive | yes 57 / no 3 | **95.0%** |
| negative | strong 41 / weak 19 / none 0 | 68.3% |
| discounted | yes 35 / no 25 | 58.3% |

0 parse failures, 0 `max_tokens` stops, projected full cost $1.86. **Per the rule I did not run the full 1,217.** A label that says the same thing about almost every call cannot separate winners from the rest, which is exactly P7's failure.

**Likely reason, not tested:** B's prompt tells it to cite numbers and guidance in its READ, and the classifier defines "strong" as specific and material "such as a number". So nearly every B READ scores "strong positive" and "forward-looking" by construction. That is a defect of the classifier's definitions as pre-registered, not of the run. It is also a small finding in itself: B's READs almost always cite specific positive evidence, on calls it then scores bearish as well; whether that evidence was set aside is what `discounted` (58% yes) was meant to catch, and the pre-flight is too small to say.

## Step 3 — not run
Step 3 (30 same-company pairs, ~$2) depends on no Step 2 output, but it sits under the same "stop" and the prompt makes no statement that it continues past a Step 2 stop, so I did not decide that. It is available to run on your instruction.

## Deviations and notes
1. **Stop, not adapt:** the prompt says stop on the classifier rule; I stopped rather than redefine the classifier, because redefining after seeing the pre-flight is a new pre-registration.
2. **READ text contains company names** written by B itself ("Williams", "Microsoft"). I passed it verbatim; stripping names was not required for Step 2 (only for Step 3's transcripts).
3. **Approval:** no spend approval was in the invocation; I asked and Luis approved the $12 cap.
4. Git bookends: prompt committed as its own commit before the clean-tree check; analysis script, driver (`--winners` path) and classifier committed before any output; pre-flight batch id `msgbatch_015EuGohNzM2mXmRU63p2Qj2` committed at creation.
5. Step 1's counts reproduce the prompt's figures (153 winners; B bullish 35, bearish 26).

## What this means for the next step

- **Not decided by this run:** the "seen and not committed" vs "not seen" question, the core of the prompt. Its two follow-ups (a prompt change aimed at commitment, or outside information) are both still open.
- **What Step 1 does settle:** own prior return does not mark winners, so "add the stock's own six-month return" is **not** supported. B's winners are spread evenly across its piles and its scale has no winner gradient.
- **If the classifier is redefined** (a design-session decision that needs its own pre-registration, e.g. "strong" only for evidence that outweighs the read's negatives, or a comparison of the READs' *emphasis* rather than their inventory), the pre-flight is ~$0.40 and the full batch ~$2, well inside the cap. If it is dropped, Step 3's pairs are the only remaining route to a hypothesis, at ~$2.

## Not done
Step 2c/2d, Step 3, any prompt or classifier change, any DB write, any cache refresh.

```bash
python3 analysis/winners_missed_analysis.py step1
python3 analysis/p6_output_format_driver.py --winners w-preflight-report
```
