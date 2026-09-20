# disaster-profile-test findings (append-only)

## PRE-REGISTRATION -- written and committed before any contingency table was computed (2026-09-20)

Predictions (prompts/disaster-profile-test.md section 6):
- Controls F1 (stratum) and F8 (year) will separate; that is not a useful finding.
- F9 (prior 90-day return) will separate. If it beats every analyst field, a price filter beats the analyst here.
- Analyst fields F2-F6 will mostly not separate (consistent with the earlier ranking test).
- F7 (consecutive bearish calls) is the one bet.
- Falsified if nothing separates on both targets, both splits and per company.
- Train discovers, tune confirms. All nine features reported against all four conditions.

Definitions fixed here, in the driver, before outcomes were tabulated (mine, not the prompt's):
- Return = benchmark-relative (stock minus SPY), entry first close strictly after call date, end on/after call + 182 days.
- T1 = worst quartile of the POOLED 187 (n = floor(187/4) = 46), a fixed cut applied to both splits. T2 = return below -25%.
- Binary flagged buckets (predicted direction: flagged has MORE disasters): F1 stratum S4; F2 thesisHealth Weakening/Broken; F3 stumbleType Structural; F4 threatMechanismImpaired true; F5 blind spots >= 1; F6 recommendedSize <= pooled median (deeper cut); F7 >= 1 immediately preceding bearish call; F8 year >= 2023; F9 prior-90d benchmark-relative return below the pooled median (window: first close on/after d-90 to last close strictly BEFORE the call date). Medians are of the FEATURE only, not outcomes.
- "Separates on a split" = flagged-minus-unflagged disaster rate > 0 AND 95% ticker-block bootstrap range excluding zero (train); tune requires the same SIGN only (its 84 calls cannot carry a range test); per-company = company-level unweighted mean of within-company disaster rates, sign > 0 on both splits and pooled range excluding zero. A feature counts only if all four hold for BOTH targets.
- LOCO (5d): strongest analyst feature (F2-F7) by pooled call-level T1 difference, plus any feature meeting all four; 21 drop-one-company recomputations with the T1 cut held fixed.
- PARA: scorer_price_cache_v1.json carries a corrupt PARA/VIAC series (found in confirmation-rule-test). Everything is reported BOTH as the prompt specifies (PARA included) and with PARA excluded. Prediction: the prompt's PARA-driven "disasters" are largely a data artifact; the without-PARA run is the better guide.
- Version guard skipped: no scoring calls.

- 2026-09-20: premise reproduced (46 calls, 21 companies, 19 from PARA/SUNW/SEDG, 40 in 2023-25, 33/13; mean -61.3% vs prompt -61.5%). PARA supplies 8 of 46 and is a corrupt series. NO feature passes all four conditions, with or without PARA. F1 stratum S4 rests on FRC+SUNW (8 of 8 disasters), no tune calls. F3 Structural: train +32.6, tune -8.3. F9 prior-90d does NOT separate (prediction contradicted); F7 does not separate (bet lost). Falsified-if condition met.
