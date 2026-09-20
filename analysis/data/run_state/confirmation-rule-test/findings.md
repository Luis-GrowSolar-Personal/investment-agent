# confirmation-rule-test findings (append-only)

## PRE-REGISTRATION -- written and committed before any outcome was computed (2026-09-20)

From prompts/confirmation-rule-test.md section 6.

- B (sell now) beats A (hold) on average, by roughly the ~4 points the entry-price test implies; range may include zero.
- C (wait and confirm) lands between A and B: better than holding, worse than acting at once.
- Within C, the confirmed group (next call also bearish) does clearly worse than the neutral group. If not, the second call carries no information and the confirmation idea is dead.
- Falsified if C beats B (C's average benchmark-relative return is above 0, since B is 0 by construction) -- treat as a reason to re-check the calculation.
- Train discovers, tune confirms. Every arm reported. The 10-case bullish arm is reported and never rests a conclusion.

Definitions fixed before computing (mine):
- Entry E = close of first trading day strictly after the bearish call; exit X = same rule after the NEXT call; END = close on/after call date + 182 days for ALL strategies. Benchmark-relative return = stock return minus SPY return over the same dates.
- B = 0 relative return after E, so "loss avoided" = -A. Share-negative for B is 0 by construction.
- C for non-bearish follow-ups equals A by construction (keeps holding). So C-A is nonzero ONLY in the confirmed group; C-B in the other groups equals A. Reported as-is.
- Next call = next chronological eval file by the same company in the same split. If X falls after END the exit is clipped to END and counted.
- "Distinct companies" reported per arm. Ranges: ticker-block bootstrap, seed 11, 2,000 resamples, of the mean; paired differences use the same resampled companies.
- Version guard skipped: no scoring calls.
