# findings (append-only)

- 2026-09-26 step 1: analysis/data/gate_ledger.json is matched by .gitignore (analysis/data/*) and has never been tracked; entry 1 is also uncommitted. Entry 2 written to disk only.
- whats_live.py reports MATCH for evaluation_prompt (v6) and does not print the research_champion block.

## Step 2 (2026-09-26) — B asked the same 1,217 train calls twice
Source: results.json (this dir), from analysis/b_noise_floor_analysis.py over scores_b.jsonl-derived calls.csv (original) and scores_b_rerun1.jsonl (re-run). All figures are rates across calls or Spearman rank correlations with 95% ticker-block bootstrap (2,000 draws, seed 11) unless stated.
- Original arm-B rank correlation reproduces P6 exactly: 0.130 (0.051 to 0.208) → results.json `rank.original`.
- Direction changes (<= -2 / >= +3): 152 of 1,217 = 12.49% (Wilson 10.75 to 14.47) → `pooled.direction_change`. Prediction 10-18%: held. v6 ~17%: B is lower.
- Score moves >= 1: 30.9% (28.36 to 33.55); >= 2: 8.87% (7.40 to 10.60). Prediction for >= 1 was 35-55%: DID NOT HOLD (below range). Finding, not a stop.
- Re-run rank correlation 0.099 (0.025 to 0.170); paired difference original minus re-run +0.031 (0.005 to 0.058) → `rank.paired_diff_original_minus_rerun`. Range excludes zero: two identical runs of B differ measurably in ranking strength, original higher. Half-width 0.0268 → tolerance rounds out to -0.03, the same as the placeholder in PROMPT_ARCHITECTURE 2.3a rule 2.
- Prediction half-width 0.02-0.04: held (0.027).
- 3x3 (original rows x re-run cols): bearish 160/31/0, neutral 23/719/49, bullish 0/49/186. No bearish<->bullish crossings in either direction.
- Noise win rate (original right in exactly-one-right direction changes): 56 of 101 = 55.4% (45.7 to 64.8). No sign that the original draw was the luckier one on direction hits, even though its rank correlation is higher.
- Matched coverage (top 235 / bottom 191): original top-235 hit 39.6% (median +1.28), re-run 36.2% (median -1.79); bottom-191 hit 62.3% vs 61.3%. Re-run has only 183 calls at <= -2, so its bottom 191 includes 8 calls at -1 (seeded tie-break).
- noRead: 3 (0.25%) original, 4 (0.33%) re-run; changed on 7 calls.
- Spend: see wrap-up. 0 unparsed, 0 max_tokens on the re-run.
