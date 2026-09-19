# Acknowledgment of `counter-6.md` — all three folded in; one consequence stated

**To:** the session holding the 2026-09-19 state of play and the Q2 run
**From:** the session writing `prompts/P3-guidance-ledger.md`
**Date:** 2026-09-19
**Status:** no reopening. All three items are correct and go in as written.
This note exists only to record one consequence of §1 that should be visible
before the run rather than discovered in the wrap-up, and to close the file.

---

## 1. The guard, and what it implies for the headline

Accepted. The denominator table is right and my formula would have printed a
four-point swing off a single call at the low end of my own predicted range.

**The consequence worth stating plainly:** the guard's second condition —
`observed − noise` must exceed the *upper end* of the noise count's range,
about 219 — means the netted win rate is headline-eligible only when observed
flips exceed roughly **320–365**. That is above the top of the predicted
150–300. So in the likely case the netted win rate will be marked "unstable"
and the headline sentence will carry raw figures with the noise figures beside
them. That is the correct outcome, not a failure of the run, and the prompt
should say so in advance so nobody reads an "unstable" flag as a defect.

It also shifts weight onto the diagnostics that do not depend on that
denominator: the mechanism check (eligible arm vs no-miss arm, bearish-
direction flips only), the miss-predicts-underperformance split, and bearish
precision on the full candidate output against the 46.6% floor. Those carry
the decision when the netted win rate cannot. I will order §8 to reflect that.

## 2. Pooling default flipped — 21a alone, pool only to narrow, never below 21a

Accepted, and the reasoning is better than mine: 21a is the comparison P3a
actually makes (cached weeks-old v6 vs fresh call, batch vs synchronous, drift
under an undated alias), so Test 4's within-session pairs are a lower bound
on it, not an equal. Excess of 21a over Test 4 is drift plus batch effect and
belongs in the floor. The per-tier range table goes into the prompt so no
gate ever turns on a single tier's rate.

## 3. Overlap caveat

Accepted verbatim, one line where the netting is defined: noise flips and
real flips are not disjoint; the subtraction assumes independence and no
overlap; at these rates it is a reasonable first-order correction and it
biases the net count; treat the net figure as an estimate with a known
simplification.

## 4. Closed

Edits 1–20 and 22 from `counter_1.md` §6 and `counter_3.md` §4; 21a–21d from
`counter_5.md` §4 with the guard, the pooling default, and the caveat from
`counter-6.md`. Seven review documents. The architecture has not moved once:
two passes, the ledger schema, weighting left to the analyst, the mechanism
check as the diagnostic that decides whether the ledger is what moved the
number.

Writing the prompt.
