# Reply to `2026-09-26-next-steps-review-comments.md` — all four changes accepted

**Date:** 2026-09-26 · **Status:** concurrence. All four changes go in as
written. Two of them correct errors in my review; both are named below so
the record shows who was wrong about what. Two small refinements, neither
of which alters a decision. Settled; steps 1 and 2 can go to Code's CLI.

## Accepted

**Change 1 — matched coverage.** Correct, and it fixes an error of mine: a
precision test at a fixed cut can be passed by calling bullish less often,
and the bearish test on tune already knew this (coverage ≥ 1.5× *and*
precision within 5 points). Compare P7's top-N by score against B's top-N,
N = B's bullish count **on the same split** (235 on train, 242 on tune),
ties broken by the seeded rule; the ≥ +3 cut reported as secondary. Also
correct that the ~6 points is sampling spread on 242 calls, not something
B's noise floor supplies — I conflated the two. The ~47% target is written
down now from the arithmetic.

**Change 2 — the ranking clause.** Correct: "not below B's" fails a true tie
half the time and is two clauses in one. Replace with the paired difference
(P7 − B, same calls) having its range's lower end no worse than −0.03,
placeholder until step 2 measures B's own band.

**Change 3 — full-train re-score.** Accepted; ~$29. The direct B-vs-B′
paired rank-correlation band is exactly what change 2 needs, and ~400 calls
per stratum halves the flip-rate ranges.

**Change 4 — P9's calibration gate.** Correct on both counts, and the
second is an error of mine: monotone deciles cannot pass at this signal
strength, and a 0.5–1.5 slope band rejects the "3× too optimistic" case my
own text called usable. Gate: slope of realized on predicted positive with
its range excluding zero. Reported, not gated: the slope's value (the
allocator-side scale factor), realized medians by fifths. Predicted slope
0.2–0.6, as a prediction.

## Two refinements, no decision changed

**R1 (change 1).** Apply matched coverage on the **bearish side too** when
P7 and P9 are scored: P7's bottom-N by score against B's bottom-N (191 on
train, 161 on tune). P7 is aimed at the bullish gap, but a rubric change can
move bearish coverage as a side effect, and the state of play's bearish
result should be shown to survive it. Same rule, same seed, reported
alongside.

**R2 (change 3).** The second B run is not only a noise measurement; it is
a **second baseline draw**. When P7 is compared to B, compare to **both** B
runs and report both differences. If P7 beats one and not the other, the
difference is inside B's own band and the result is a tie — the same
cached-draw hazard the v6 archive had, caught before it costs a round.

## Nothing else

Step 1 (bookkeeping) is unaffected. Steps 1 and 2 go to Code's CLI as one
prompt; P7's pre-registration is written after step 2 lands, with the
measured band in place of the −0.03 placeholder.
