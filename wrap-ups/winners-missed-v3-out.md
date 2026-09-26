# Winners B missed, v3. Wrap-up

**Run ID:** `winners-missed-v3`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial.**
**Real spend: $1.83** (1,217 classifier calls, `cost_usd` summed over `read_labels_v3.jsonl`) against the $4 cap Luis approved at Step 0 (recorded in `progress.json`; approval asked and given in chat).
**Scope boundary: report, do not decide.** No candidate written, no prompt changed, nothing promoted.

> Reading only B's own notes, a classifier found a raised outlook / a beat of guidance / good news outweighing bad on **17.8% / 14.4% / 35.6%** of the calls B did not score bullish that went on to beat the S&P by 20+ points, against **23.3% / 14.1% / 46.3%** of the rest: **not seen**. Calls tagged beat-and-raise (**116** of 1,217) became big winners **11.2%** of the time, against **13.1%** for calls with neither (difference **−1.9** points, range **−7.9 to +3.6**), and B scored **51.7%** of them below +3 (all calls: 80.7%). **A "commit on beat-and-raise" candidate is not worth building on this evidence.**

Sources: `analysis/data/run_state/winners-missed-v3/results.json` (keys `2a`–`2d`), labels `read_labels_v3.jsonl`, script `analysis/winners_missed_analysis.py v3`. Ranges: Wilson for rates; 95% ticker-block bootstrap (2,000 draws, seed 11) for differences and medians. Big winner ≥ +20 points, big loser ≤ −20 (tradeable-entry 182-day return vs SPY).

## The classifier
`docs/prompts/diagnostics/READ_CLASSIFIER_v3.md`, sha256 `fe58344fe270d691190a03008465d004bbb1f3c01dabfe2889f218497c7c307c`, recorded in `progress.json` before any call. **Diff against v2, as required:** only the header, the `"discounted"` line in the block (and the trailing comma on `"beat"`), and the `discounted` definition bullet differ; the `balance`, `raised` and `beat` definitions and examples are identical (`diff` output in the run log; three hunks). Same setup as v2: B draw 1's READ paragraph only (SCORE section and structured block stripped and asserted absent), shuffled seed 11, `claude-sonnet-4-6`, `max_tokens` 400, no temperature. 1,217 of 1,217 parsed, 0 out-of-set values, 0 `max_tokens` stops.

## 2a. Stop rule, on the full set: not tripped
| field | full 1,217 | most common value | v2 pre-flight (60) |
|---|---|---|---|
| balance | outweighs 677 / balanced 135 / outweighed 405 | 55.6% | 32 / 7 / 21 |
| raised | yes 345 / no 872 | 71.7% (yes 28.3%) | 16 / 44 |
| beat | yes 219 / no 998 | **82.0%** (yes 18.0%) | 10 / 50 |

Key `2a`. The rule (85%) was not tripped, but `beat` sits 3 points under it; the pre-flight's near-edge was real.

## 2b. Winners vs the rest, among B's non-bullish calls (score ≤ +2: 118 winners, 864 others)
| share | winners | others | difference (pts) | range | excludes zero, higher for winners |
|---|---|---|---|---|---|
| (i) balance = outweighs | 35.6% (27.5–44.6) | 46.3% (43.0–49.6) | −10.7 | −22.1 to +0.8 | no |
| (ii) raised = yes | 17.8% (11.9–25.7) | 23.3% (20.6–26.2) | −5.5 | −12.4 to +1.9 | no |
| (iii) beat = yes | 14.4% (9.2–21.9) | 14.1% (12.0–16.6) | +0.3 | −6.1 to +8.0 | no |
| (iv) beat-and-raise | 6.8% (3.5–12.8) | 6.0% (4.6–7.8) | +0.8 | −3.6 to +6.0 | no |

**Pre-registered reading: "not seen"** (none of (i)–(iii) is higher for winners with its range above zero). If anything the READs of future winners note a raised outlook and a favorable balance *less* often, though those ranges include zero. Key `2b`.

## 2c. Beat-and-raise directly, all 1,217 calls (the decision-relevant check)
| group | calls | big-winner rate (base 12.6%) | big-loser rate | median return (range) | B draw 1 below +3 | B draw 2 below +3 |
|---|---|---|---|---|---|---|
| **beat-and-raise** | **116** | **11.2%** (6.7–18.2) | 8.6% (4.7–15.1) | −2.12 (−6.35 to +1.92) | **51.7%** (42.7–60.6) | 48.3% |
| raised only | 229 | 10.5% (7.1–15.1) | 10.9% | −0.54 (−2.28 to +1.71) | 70.7% | 72.1% |
| beat only | 103 | 14.6% (9.0–22.6) | 18.4% | −2.00 (−5.94 to +3.01) | 76.7% | 76.7% |
| neither | 769 | 13.1% (10.9–15.7) | 19.1% | −4.27 (−6.18 to −2.16) | 88.6% | 88.7% |
| all calls | 1,217 | 12.6% | 16.5% | | 80.7% | 80.7% |

B's score distributions per group (draws 1 and 2) are in `2c.*.B1_score_dist` and `B2_score_dist`; for beat-and-raise, draw 1: −1: 5, +1: 9, +2: 46, +3: 56.
**Pre-registered rule: not worth building.** Beat-and-raise minus neither on the big-winner rate is **−1.9 points (−7.9 to +3.6)**, so the range does not exclude zero and the difference is not even positive.
**Reported beside, not gated:**
- The median return of beat-and-raise calls is higher than "neither" by **+2.15** (range −2.04 to +6.74), inside noise. The tail is different: beat-and-raise calls became big losers less often (8.6% vs 19.1%), the only visible difference, and it is on the downside, not the winners.
- **B did not hold back on these calls; it committed more.** Only 51.7% of beat-and-raise calls were scored below +3, against 80.7% overall and 88.6% for "neither": B already scores about half of them +3 or higher. The v2/v3 hypothesis "B saw it and held back" is contradicted on the calls where the classifier says the good news was a beat-and-raise.

## 2d. Tie-in with v2's pairs (reported only)
Winner-side calls of the 18 right-pick pairs tagged `raised` or `beat` by v3: **6 of 18** (raised 5, beat 2). The chosen (non-winner) calls of the 12 wrong-pick pairs tagged: **5 of 12** (raised 5, beat 1). No separation; 30 pairs test nothing. Key `2d`.

## Deviations, flags
1. None from the prompt's design. The classifier was not redefined; the pre-flight was skipped as specified.
2. **Approval:** no spend approval in the invocation; I asked and Luis approved the $4 cap.
3. The per-call estimate ($0.00167) was v2's measured pre-flight cost; the full run cost $0.0015 per call, slightly under.
4. Git bookends: prompt committed as its own commit; classifier, driver `--wv3` path and analysis committed before any output; batch id `msgbatch_01Yb27nsxYyRtLuawpg48WLG` committed at creation.
5. **Limits of the method:** the classifier reads B's notes, not transcripts. A 12.6% base rate on 116 calls gives a Wilson half-width of about ±6 points for the beat-and-raise winner rate, so effects under about 8 points cannot be excluded either way. `beat` is a rare tag (18%); its calls are 103 + 116.

## What this means for the next step
**Not worth building, on this evidence.** The best-documented bullish pattern (beat and raise) is not visible in B's notes on this corpus: calls tagged beat-and-raise became big winners no more often than calls with neither (11.2% vs 13.1%), and future winners' READs did not note raises, beats or a favorable balance more often than other calls' READs. And B is not blind to beat-and-raise: it scores about half of those calls +3 or higher (against 19% of calls overall).
Of the two directions the prompt names, **the evidence here does not favor either strongly.** Outside data (P4 XBRL facts, consensus) is not tested by this run. A candidate that reads guidance changes from the transcript directly, rather than through B's notes, is also not tested: this run only shows that B's notes carry no beat-and-raise signal for winners, and the classifier may be reading B's wording of the event rather than the event. The pairs run (18 of 30) is the only evidence favoring a direct-read route and it cannot separate recall or chronology cues. If a "commit on beat-and-raise" change to B were built anyway, it would be the one-sentence change the prompt names, run as two draws on train (§2.3a rule 7, about $60), with the usual gates and bearish bottom-191 at or above 57%; this run does not support building it.

## Not done
No candidate, no prompt change, no redefinition, no tune or holdout, no DB writes, no cache refresh.

```bash
python3 analysis/winners_missed_analysis.py v3
```
