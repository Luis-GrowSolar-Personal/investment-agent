# Winners B missed, v2. Wrap-up

**Run ID:** `winners-missed-v2`. Branch `sweep/db-corpus-baseline`. **PARTIAL RUN by rule:** Step 1 and Step 3 are complete; **Step 2 stopped at its pre-flight** on the pre-registered stop rule, and the full classification (2c/2d) was not run.
**Real spend: $1.53** ($0.10 Step 2 pre-flight + $1.43 Step 3, `cost_usd` in `read_labels_v2.jsonl` and the pair batches) against the $8 cap Luis approved at Step 0.
**Scope boundary: report, do not decide.** Nothing promoted, no prompt changed, no tune or holdout touched.

> Reading only B's own notes, the classifier's **pre-flight** found a raised outlook on **27%**, a beat of guidance on **17%** and good news outweighing bad on **53%** of 60 calls, but it **stopped before the test**, so there is no comparison of future big winners with the rest: **not answered**. In 30 same-company pairs, the model picked the winner **18** times (chance is 15); **14** of its 18 right-pick reasons were a raise, a beat or both by its own tag (**10** by my strict reading). Step 1's bookkeeping landed in commit **`0049f7e`**.

## Step 1 — bookkeeping (commit `0049f7e`)
`docs/architecture/PROMPT_ARCHITECTURE.md`: §2.2 gets the row **P9-avg** (eligible for one tune look, parked 2026-09-26, with the one-line reason and the pointer to `wrap-ups/P9-close-and-averaged-comparison-out.md`); §2.1 gets the two dated winners findings (B's score carries no information about big winners; winners are not rebounds); §2.3a gets rule 7 (two draws on train from the start). Placement note: the two §2.1 lines sit at the end of §2.1, just before the §2.2 heading.

## Step 2 — READ classifier v2: STOPPED at the pre-flight
Classifier `docs/prompts/diagnostics/READ_CLASSIFIER_v2.md`, sha256 `60e76ff5da9ef8781b0e926a8881524951ec0514f73bd026242223051f7763c4` (recorded in `progress.json` before any call). v1 is unchanged on disk. It saw only B draw 1's READ paragraph (SCORE section and structured block stripped and asserted absent for all 1,217); `claude-sonnet-4-6`, `max_tokens` 400, no temperature; the same 60 calls as v1's pre-flight. Values are defined without reference to numbers or specifics, with a yes and no example for `raised` and `beat`.

| field | distribution on the 60 | most common value | v1 comparison |
|---|---|---|---|
| balance | outweighs 32 / balanced 7 / outweighed 21 | 53.3% | n/a |
| raised | yes 16 / no 44 | 73.3% (yes **26.7%**) | n/a |
| beat | yes 10 / no 50 | 83.3% (yes **16.7%**) | n/a |
| **discounted** | **yes 55 / no 5** | **91.7%** | v1 on the same 60: yes 35 / no 25 |

Key: `preflight_report.json`. **The stop rule (any field over 85% on one value) tripped on `discounted`.** 0 parse failures, 0 `max_tokens`. **Predictions:** raised yes 15–35% held (26.7%); beat yes 15–35% held (16.7%, near the low edge); balance none above 60% held (53.3%). So three of the four new fields behaved and one did not. Per the prompt I did not redefine the classifier and did not run the full 1,217 (projected $2.03). The pre-registered test (2d), the beat-and-raise combination and B's scores on it were therefore not computed.

**Likely cause of the `discounted` failure, not tested:** v2 widened its definition to include "outweighed by a risk". Nearly every B READ has a line beginning "the one genuine concern…", so almost every read "sets a positive aside". The definition change, not the reads, moved it from 58% to 92%.
**Note that raised, beat and balance had usable spread** on the pre-flight. A later run that drops or narrows `discounted` would not repeat the failure on those three; that is a design-session decision, since a changed classifier needs its own pre-registration.

## Step 3 — 30 same-company pairs (hypotheses only)
Source: `results_step3.json`; pair metadata `pairs.json`; redacted texts (gitignored, rebuildable from seed `winners-pairs-11`) in `analysis/data/evals/winners-missed-v2_pairs/`.
**Construction:** 46 companies had at least one big-winner call and one middle call; 30 were drawn (seeded), one winner call each, paired with that company's nearest middle call (median distance in `pairs.json` → `days_apart`); A/B order seeded (A was the winner in 17 of 30). Redaction: a fixed company-name alias list per ticker, the ticker, years and month names replaced mechanically; 0 of 60 transcripts kept an alias or ticker. The prompt said "where mechanically possible": the name list is a deterministic hand-made list for these 30 tickers, because extracting names from the opening line failed on 14 of 60 transcripts. Fiscal-quarter words remain.

**Right picks: 18 of 30 (60%; Wilson 42.3–75.4%; chance 15).** The model chose A 19 times.

**Mechanisms by kind** (the model's own `kind`): all 30: guidance 19, results vs expectations 7, margins 2, balance sheet/cash 1, demand/bookings 1. Right picks (18): guidance 12, results vs expectations 3, margins 1, balance sheet 1, demand 1. Wrong picks (12): guidance 7, results vs expectations 4, margins 1. Guidance is the most common reason among both right and wrong picks.

**Right-pick mechanisms** (one line each; full text in `results_step3.json`):
- Clear guidance raise or beat (my strict reading, 10): AEP raised full-year EPS midpoint; DIOD exceeded the high end of prior guidance and guided up; EOSE gave full-year revenue guidance above the earlier target; INTC beat and raised Q3 guidance; JPM raised NII guidance; LLY raised full-year EPS guidance; MRK raised its EPS midpoint; MS reached its long-term targets early; TEAM's operating margin beat by 6–7 points; TFC raised its cost-savings target.
- Other (8): MU and SLAB sequential guidance steps up (next-quarter guide far above the other call's); COF guided marketing up vs the other call withdrawing all guidance (COVID); NXPI growth guidance vs a cautious one; CMCSA doubled its buyback; COST ended COVID premium pay; PH record results with new guidance; QS announced a licensing partnership.

**Raise or beat among right picks:** the model's own tag says 14 of 18 (raise 10, both 2, beat 2). By my reading of the mechanism text, **10 of 18** are an unambiguous raise or beat; the tag counts sequential guides and a resumed guide as raises. I report both; the count is a judgment either way.
**Wrong picks:** 12, of which 7 cited guidance (for example WMB, BOX, JKS: a raise in the call the model chose that was not the winner), so a raise alone does not identify the winner.
**Recall/leak notes:** 0 pairs tagged "recall_not_in_text". But in PAIR 9's first-pass text the model named the company ("EOS Energy Storage, ticker EOSE") despite the redaction, and in IBM's the model referred to "the subsequent Q1 call": it can partly identify companies and infer chronology. Treat mechanisms that lean on the company's known story as recall.

## Deviations, flags, premises
1. **Step 2 stop:** as pre-registered. I did not redefine the classifier or run 2c/2d.
2. **Step 3 `max_tokens`:** the prompt fixes 400 for the classifier only. Pairs used 500; **4 of 30 stopped at 500** because the model wrote its reasoning before the block. I re-ran those 4 with `max_tokens` 2000, request otherwise identical (`batch_id_pairs_retry`, +$0.13, committed before collection), giving 30 of 30. The retry's rows replace the truncated ones (`results_step3.json` → `rows[].source`).
3. **Name redaction** is by a fixed alias list, not full "mechanical" extraction (see Step 3).
4. **Approval:** no spend approval was in the invocation; I asked and Luis approved the $8 cap.
5. **Driver commit:** `progress.json` → `driver_commit` advanced to the step 3 extension; the Step 2 code ran unchanged from the earlier commit.
6. Git bookends: prompt committed as its own commit before the first run commit; driver and classifier committed before output; batch ids `msgbatch_01V865mefnfhnQFhmbt3PDu1` (pre-flight), `msgbatch_01VigGuioaVTDShjmH5i5SEA` (pairs), `msgbatch_016RrvYfKEy7YqVQhz8ssSHx` (retry) committed at creation.

## What this means for the next step
- **Step 2's question is still open.** No comparison of winners with the rest on `balance`, `raised` or `beat` was made, so "seen and not committed" versus "not seen" is undecided. What the pre-flight does show is that the READs themselves distinguish raised outlooks (27%), beats (17%) and balance (53% outweighs) across calls, so a version without the broken `discounted` field can run for about $2.
- **Step 3 agrees with the direction of the hypothesis, weakly.** The model picked the winner 60% of the time and its reasons were mostly a guidance raise or a beat. That is the mechanism the prompt hypothesised. It does not show B saw it: the model read full transcripts, not B's notes, chronology and recall leaks are possible, and 30 pairs test nothing (the Wilson range 42–75% includes 50% as its near edge). If a change to B is suggested by it, it is the one the prompt named as an example: commit to +3 or higher when guidance is raised and results beat. That would be a new candidate with its own pre-registration; this run does not propose it as tested.
- **Not indicated:** outside data. Neither the stopped Step 2 nor the pairs argue for P4 or consensus yet.

## Not done
The full READ classification and its test, the beat-and-raise combination check, B's scores on tagged calls, any prompt or classifier redefinition, any DB write, any cache refresh.

```bash
python3 analysis/p6_output_format_driver.py --wv2 w-preflight-report
python3 analysis/winners_missed_analysis.py step3
```
