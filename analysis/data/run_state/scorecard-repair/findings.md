# scorecard-repair — findings log (append-only)


## Finding -- 2026-09-13T21:24:55Z

**Step 0c CONFIRMED.** Prompt's Sec5 worked example (pred 251/44/64, outcome 166/151/42, expected-by-luck 39.6%, observed 40.4%) reproduces exactly from the stored corpus. No contradiction to carry forward.

## Finding -- 2026-09-13T21:24:55Z

**Step 1 luck-corrected score.** Scorer pop (n=359): observed 40.4%, expected-by-luck 39.6%, gap 0.82pp, kappa 0.0136, balanced accuracy 31.3%. Simulator pop (n=195): gap 0.11pp, balanced accuracy 29.6%.

## Finding -- 2026-09-13T21:24:56Z

**Step 2 intervals.** (2000 resamples, seed 20260913, 16 independent ticker blocks scorer pop / 16 simulator pop). Scorer luck-corrected-gap 95% CI [-2.36, 3.89]pp (spans zero: True). Simulator luck-corrected-gap 95% CI [-4.82, 4.47]pp (spans zero: True). ANY interval spans zero: True.

## Finding -- 2026-09-13T21:25:44Z

**Step 3 confirms the prompt's expectation.** Unpaired MDE=12pp, paired MDE=6pp (disagreement rate 0.15) -- pairing lowers the threshold as expected. Data-volume answer for a 3pp paired threshold: {'target_pp': 3, 'stock_axis': {'stock_multiplier': 4, 'n_tickers': 64, 'mde_at_multiplier': 1}, 'call_axis': {'call_multiplier': 4, 'n_calls_per_ticker_scaled': 4, 'mde_at_multiplier': 2}}.

## Finding -- run complete

Step 5: v10+auto1's existing published spread (37.5-42.5% vs v6 37.5%, max
5pp) is below every detection threshold measured in Step 3 (12pp unpaired,
6pp paired at 15% disagreement, 4-7pp across the paired sensitivity sweep).
The v10+auto1-vs-v6 comparison was not decidable on this corpus at this
sample size, under either design. Wrap-up written to
wrap-ups/scorecard-repair-out.md.
