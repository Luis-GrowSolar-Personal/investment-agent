# repeat-the-bearish-call findings (append-only)

## PRE-REGISTRATION -- written and committed before any batch was submitted and before any outcome was computed (2026-09-20)

Predictions (prompts/repeat-the-bearish-call.md section 5):
- Primary: the 3-of-3 group has a HIGHER share of calls lagging the S&P by more than 25% than the 1-of-3 group. Direction predicted, size not.
- The money gap (tail share, worst-quarter average) will be larger than the accuracy gap (share lagging by more than 5%).
- Falsified if the 3-of-3 tail share is at or below the 1-of-3 tail share on EITHER split. Then repetition carries no information about money and the lead is closed.
- Also falsified in practice if group ranges overlap so heavily that no group can be told from the whole -- to be said plainly, not hidden behind a point estimate.
- Not predicted, reported either way: whether the 48-call-sample accuracy pattern (50% unanimous vs 25% split) reproduces.
- Train discovers, tune confirms. Every group and measure reported.

Definitions fixed here (mine):
- Population: v6's bearish calls (Trim/Exit) re-derived from the eval caches, PARA (corrupt series), WOLF, SPWR excluded: 177 calls (93 train, 84 tune, 57 companies). The prompt's 187 was the pre-exclusion figure.
- Readings: cached original (bearish by construction) + two fresh runs r1, r2 with the unchanged promoted v6 prompt, model claude-sonnet-4-6, default sampling settings as in the baseline batches, max_tokens 4096. Group k-of-3 = 1 + number of re-runs whose direction is bearish (Trim/Exit). Direction from per_call_rec via analyst_direct_scorer.direction_from_score.
- Pilot: 2 synchronous calls with the exact request shape become r1 for those two calls (same prompt, model; sync rather than batch).
- Unreadable readings (missing, unparsable direction, stop_reason max_tokens) are excluded from the groups and counted.
- SANITY GATE before any outcome: 3-of-3 share must lie between 50% and 95% (expected about 75%). Outside it: stop and check the driver.
- Return: benchmark-relative (stock minus SPY), entry = close of first trading day strictly after the call, end = close on/after call + 182 days.
- Primary measure ("tail"): return below -25%. Accuracy ("lagged by more than 5%"): return below -5%. Worst quarter = mean of the lowest floor(n/4) (at least 1) returns in the group. Sell-now saving = minus the mean hold return (selling from the tradeable entry returns 0).
- Comparisons: 3-of-3 vs 1-of-3 (the registered prediction) and 3-of-3 vs "not 3-of-3" (2-of-3 + 1-of-3, the headline sentence). Ranges: ticker-block bootstrap (whole companies), seed 11, 2,000 resamples; differences use the same resampled companies.
- Concentration check: drop each of the 8 companies with most 3-of-3 tail calls in turn and recompute the 3-of-3 and 1-of-3 tail shares.
- "Ranges too wide to tell": if the 95% range of the 3-of-3 minus 1-of-3 tail-share difference includes zero on a split, that split cannot tell them apart.
- Version guard: run against the promoted v6 hash (357b6b0b...), no candidate; recorded in progress.json.
- Spend cap $20; request cap 400 (354 planned).

- 2026-09-20: batch ended 352/352 succeeded; 354 readings, all end_turn, 0 unreadable. Spend $15.07 (cap $20). Groups: 3-of-3 = 101 (57.1%), 2-of-3 = 34 (19.2%), 1-of-3 = 42 (23.7%). Only 66.7% of re-runs came back bearish (236 of 354; 116 neutral, 2 bullish) vs ~87% implied by the prompt's 12.8% pairwise disagreement. Sanity gate PASS (50-95%). Likely selection effect: calls chosen BECAUSE the cached draw was bearish. Outcomes not yet computed at this point.
