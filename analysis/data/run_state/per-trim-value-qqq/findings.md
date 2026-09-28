# per-trim-value-qqq — findings (append-only)

## Finding 1 — combined verdict: both legs read "protection does not pay"

QQQ pooled A range [−0.0518, 0.4699] includes zero, same shape as SPY's
[−0.1291, 0.3868]. Per the pre-registered reading (`prompts/per-trim-value.md`),
"protection does not pay" applies whenever A's own range includes or is below
zero — true on both destinations, per draw and pooled. Neither "the analyst
pays" (A − B above zero both destinations) nor "the index does the work"
(A above zero, A − B includes zero) applies to either leg, since A itself
never clears zero on either destination.

## Finding 2 — the diagnostic confirms the design session's expectation

A(QQQ) − A(SPY), pooled, fixed 2.5: 0.0770. [A−B](QQQ) − [A−B](SPY), pooled,
fixed 2.5: 0.0033 — nearly zero, as expected: the quarter-matched control
absorbs almost all of QQQ's tailwind advantage over SPY in this period, since
both A and its control are drawn from the same quarters. Same pattern holds
sized by P9 (diff in A: 0.0406; diff in A−B: 0.0018). This is diagnostic
only, not a condition, per the prompt.

## Finding 3 — P9 severity layer adds value on both legs, same shape as SPY-only run

QQQ pooled: sized A−B per point 0.2286 vs. step 1's unsized 0.0452 (≈5x).
Band ordering (band1 > band2 > rest) holds: 0.3334 > 0.1508 > −0.0185
(n-weighted mean of bands 3-5). Same conclusion as SPY, same conclusion per
draw. This cannot change the Step 1 verdict, per the prompt.
