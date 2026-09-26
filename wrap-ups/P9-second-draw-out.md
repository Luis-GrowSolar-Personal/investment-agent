# P9 — second draw on train. Wrap-up

**Run ID:** `p9-second-draw`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial.**
**Real spend: $30.14** (1,217 calls, `cost_usd` summed over `scores_p9_rerun1.jsonl`), under the $36 cap Luis approved at Step 0 (recorded in `progress.json`; approval asked and given in chat).
**Scope boundary: report, do not decide.** No champion change, no tune, no registry status change, no ledger entry.

> On a second draw of the same 1,217 train calls, the expected-return prompt ranked at **0.111** (draw 1: 0.171), a paired difference over B of **−0.020** (range **−0.071 to +0.032**) against B draw 1 and **+0.011** (range **−0.039 to +0.059**) against draw 2; its clipped slope was **0.481** (range **0.132 to 0.804**) and its bottom 191 were right **61.8%**. Across both P9 draws, **5** of 6 gate checks held. **P9 is FALSIFIED on train.** On severity it is **better information** across both draws. Between its own two draws P9 changed group on **17.0%** of calls (B: 12.5%) and its ranking moved by **0.060** (B: 0.031).

Sources: `analysis/data/run_state/p9-second-draw/results_draw2.json` (draw 2, same computation as draw 1), `results_verdict.json` (this run's verdict and noise figures), and draw 1's `p9-expected-return-train/results.json`. Conventions unchanged from draw 1: groups bottom 191 / top 235 (seeded ties, seed 11), realized clipped at ±50, ticker-block bootstrap 2,000 draws seed 11.

## The verdict (pre-registered rule, applied once)

P9 earns tune only if **each** draw holds **all three** gates, gate 2 against **both** B draws. **One line: FALSIFIED, because gate 2 fails on draw 2 against both B draws.** No further ambiguity rule applies.

| P9 draw | Gate 1: clipped slope, range above 0 | Gate 2: paired rank diff, lower end ≥ −0.03 | Gate 3: bottom 191 right ≥ 57.0% |
|---|---|---|---|
| **draw 1** | **held.** 0.662 (0.332 to 0.959) | **held** vs B draw 1: +0.040 (−0.016 to +0.097); **held** vs B draw 2: +0.071 (+0.016 to +0.126) | **held.** 62.8% (55.8–69.4) |
| **draw 2** | **held.** 0.481 (0.132 to 0.804) | **FAILED** vs B draw 1: −0.020 (−0.071 to +0.032); **FAILED** vs B draw 2: +0.011 (−0.039 to +0.059) | **held.** 61.8% (54.7–68.4) |

Keys: `gates.draw1/draw2`, `gates_held_per_draw_[g1,g2_both_B,g3]`, `n_of_6_held`. Counting gate 2 as one check per P9 draw (held only if it holds against both B draws), 5 of 6 held. P9 draw 2's rank correlation is **0.111 (0.028 to 0.189)**, against B's 0.130 and 0.099; draw 1's 0.171 was the high draw. The single failing quantity is the ranking tolerance: draw 2 is not clearly no worse than B on either B draw.

Not gated, draw 2: top 235 right **35.3%**, median −1.20 (B 39.6% / 36.2%).

## Severity, both draws (`severity`)

| | (a) rank correlation inside bottom 191 | (a) range excludes zero | (b) fifths, lowest to highest, realized median | (b) lowest below second |
|---|---|---|---|---|
| draw 1 | 0.257 (0.094 to 0.373) | yes | −9.76, −5.52, −0.95, −1.63, +1.54 | yes |
| draw 2 | 0.184 (0.046 to 0.312) | yes | −8.27, −4.09, −1.16, −1.36, −1.82 | yes |

**Both draws meet both conditions, so by the pre-registered reading P9 is "better information"** on severity: its number grades how bad a bad call is, on both draws, where B's ranges inside its bottom 191 include zero (0.081 and 0.145; draw 1 quoted from the earlier wrap-up). Note the contradiction plainly: **severity is confirmed, and P9 is still falsified**, because the falsification is on ranking non-inferiority, not on severity. In draw 2 the top fifth (−1.82) is not above the middle fifths, so the top of the scale carries no signal in that draw. The prompt's closing text says the first-draw severity result would be recorded as "single-draw, unconfirmed" if P9 is falsified; the numbers here confirm it on a second draw, so that label would understate the evidence. What it is worth is the design session's decision.

## P9's own noise floor (draw 1 vs draw 2), beside B's (`noise_floor`)

| figure | P9 | B (`wrap-ups/B-champion-and-noise-floor-out.md`) |
|---|---|---|
| calls that changed group (bottom 191 / middle / top 235) | **17.0%** (207 of 1,217; Wilson 15.0–19.2) | 12.5% (10.8–14.5) |
| `expectedReturn` moved by ≥ 3 points | 28.4% (26.0–31.0) | n/a (integer score) |
| `expectedReturn` moved by ≥ 5 points | 13.3% (11.5–15.3) | n/a |
| paired rank difference, draw 1 minus draw 2 | **+0.060** (0.024 to 0.097) | +0.031 (0.005 to 0.058) |
| half-width, and the tolerance a P9-derived candidate would inherit | **0.037 → −0.04** | 0.027 → −0.03 |
| noise win rate (draw 1 right, decisive group changes) | 56.0% (79 of 141; 47.8–64.0) | 55.4% (45.7–64.8) |
| clipped slope, draw 1 / draw 2 | 0.662 / 0.481, difference **+0.181 (0.048 to 0.327)** | n/a |

Per stratum group-change rate: S1 16.0%, S2 18.8%, S3 15.9%, S5 22.3%, S4 18.8% (16 calls, not readable). 3×3 (draw 1 rows, draw 2 columns; bearish / neutral / bullish): 148 / 40 / 3; 39 / 691 / 61; 4 / 60 / 171. Bearish and bullish crossings are rare (7 of 1,217).

**P9 is shakier than B on every measure: more group changes (17.0% vs 12.5%; the ranges just touch), a larger run-to-run ranking difference (0.060 vs 0.031, and P9's range excludes zero as B's did), and a wider tolerance.** The paired ranking difference between P9's own draws exceeds B's, and P9's first draw was the high one.

## Averaged draws (diagnostic — not a gate, not a candidate)

Average of the two `expectedReturn`s per call: rank correlation **0.140** (0.055 to 0.223); clipped slope **0.629** (0.268 to 0.959); bottom 191 right **62.8%** (120 of 191), median −10.75 (`averaged_draw_diagnostic`). Scoring each call twice would land near B draw 1's ranking (0.130) and above B draw 2's (0.099); it is not a comparison against a B averaged the same way, which I did not compute.

## Draw 2 other figures (predictions, `predictions`)

Every pre-registered prediction landed inside its range on draw 2 (median +5.0; 74.1% positive; middle half 0 to 8, span 8; clipped slope 0.481; range coverage 60.3%; rank 0.111; cost $0.0248 per call, +5% vs B). On draw 1, three had missed (share positive, slope, rank). Range order violations 0, parse failures 0, `max_tokens` stops 0. Distribution is again coarse: 8 (247 calls), 5 (221), −5 (119), 3 (104), 4 (95).

## Flags, deviations, premises

1. **Approval:** no spend approval was in the invocation; I asked and Luis approved the $36 cap.
2. **"5 of 6" counting:** the prompt's sentence says "___ of 6 gate checks". I counted 2 draws × 3 gates, with gate 2 held only if it holds against both B draws, as the rule states. Counted per B draw (2 × 4 checks), it is 6 of 8 (draw 2 fails both gate-2 checks). Verdict is the same either way.
3. **Severity vs verdict:** stated above; the prompt's suggested "unconfirmed" label does not match the numbers.
4. **Commit ordering:** the prompt asks for the P9 row edit as its own commit before scoring. It shares a commit with the run's state files and the prompt file (`93ae8e1`); the row itself was not changed after the run and still reads "second draw running". Updating it to FALSIFIED is left for the design session.
5. **CLAUDE.md** changed on disk during the run (a new "Git bookends" rule). The prompt file was committed with the run's first commit, as that rule asks; I did not stage the user's uncommitted CLAUDE.md edit.
6. The driver's `--p9r` path and `p9_expected_return_analysis.py --draw2` extend the existing code; draw 1's `results.json` was not rewritten. Request shape asserted identical to B's `make_request()` except system text on 25 sampled calls, with the `__r1` suffix; no temperature parameter; prompt sha `a752e6b1…06a5` asserted. Batch id `msgbatch_018P74suPvhTF6bQJsCgx58t`, committed at creation.
7. Draw 2 values are not compared against B's tune counts; tune was not touched.

## What this means

**Falsified:** per the pre-registered rule P9 does not go to tune and B stays champion. The specific reason is ranking: P9's ranking swings between identical runs by more than B's (0.060 vs 0.031), and the low draw (0.111) is not clearly at least as good as B. The severity result is a separate and real finding: on both draws P9's number orders outcomes inside the bearish group (0.257 and 0.184, ranges above zero), which B's tied scores cannot do, and its scale is positive in sign on both draws (slope 0.66 and 0.48). Whether that is worth a different route (for example a severity-only use of the number in the allocator, or an averaged score) is not settled by this run and is Luis's decision. **If P9 held** the next step would have been a tune prompt at counts 161 / 242; that does not apply.

## Not done

No tune, no third draw, no change to B's status, no update of the P9 row to its result, no DB writes, no cache refresh.

```bash
python3 analysis/p9_expected_return_analysis.py --draw2
python3 analysis/p9_second_draw_analysis.py
```
