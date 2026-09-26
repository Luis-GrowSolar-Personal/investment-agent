# Review of the P9 candidate and run prompt — three changes, otherwise clear to run

**Date:** 2026-09-26 · **Reviewed:** `docs/prompts/candidates/EVALUATION_PROMPT_P9_expected_return.md`,
`prompts/P9-expected-return.md` (commit `680f377`).
**Verdict:** agree with the design — same reading as B, only the last step
changed, matched-coverage groups, calibration sign as the first gate, and
the honest "same information, better units" outcome named in advance.
Three changes; the first two bear on the one thing P9 exists to measure.

---

## 1. Cut the timidity clause; keep the base rate (candidate, §EXPECTED RETURN)

The reviewer question in the run prompt §1 was keep-or-cut for:

> "Most stocks land within 20 points of the S&P over six months, and a
> typical call does not move the odds much."

**Keep the first half, cut the second.** The base rate ("most stocks land
within 20 points") is a true, non-company-specific fact and it stops the
model defaulting to ±30. The second clause is an instruction to be timid.
P9's purpose is severity — a spread at the bearish tail that B's score
lacks — and "a typical call does not move the odds much" pushes every
estimate toward 0, which is the exact failure the **bunched** stop rule
exists to catch. The sentence "size your number to how much this call
actually tells you" already carries the intended restraint without
pre-judging that the answer is small.

Replacement:

> "Most stocks land within 20 points of the S&P over six months. Size your
> number to how much this call actually tells you: a weak read belongs
> close to 0, and a large number needs strong evidence."

## 2. Gate 1's slope needs outlier protection (run prompt §4, gate 1)

Realized returns on this corpus include −100% wipeouts and multi-baggers.
An ordinary least-squares slope of realized on predicted is dominated by
those few points; with ~1,200 calls and a weak signal, three catastrophes
in the negative-prediction tail can carry the slope's sign on their own,
and three in the positive tail can flip it. The ticker-block bootstrap
does not fix this: the same outliers recur in most draws.

**Fix:** compute gate 1's slope on realized returns **winsorized at ±50
points** (clip, do not drop). Report the raw slope beside it. The gate is
on the winsorized figure. State the clip level in the pre-registration so
it cannot move.

## 3. The severity reading declares a result on noise (run prompt §4, purpose check (a))

Check (a) says P9 "grades severity" if its within-bearish-group rank
correlation is above both B figures. B's are near zero by construction
(ties). A rank correlation on **191 calls** has a 95% range of roughly
**±0.14**, so P9 at +0.08 would clear "above B" and mean nothing.

**Fix:** (a) requires P9's within-group rank correlation to have its
**ticker-block range exclude zero**, not merely to exceed B's. Report B's
figures beside it for context. The (b) fifths test stays as written — at
~243 calls per fifth the median comparison is sound.

---

## Confirmed sound, no change

- Groups by matched coverage (bottom 191 / top 235), no thresholds, seeded
  ties — the right way to compare a unitless-free output with B.
- "No disagreement threshold" and the arm-C precedent: correct, and
  stated.
- The bunched / one-sided / noRead / range-order stop rules, and P7's
  lesson that a parsing output can still be a stop.
- Gates 2 and 3 against both B draws; the ambiguity band sized to B's
  wobble; the second draw not approved.
- The pre-registered predictions, including that the model's 80% ranges
  will cover only 50–70% — worth having written down before the run.
- Budget, cap, batch-id discipline, commit order; `.md`-only wrap-up.

Once 1–3 are in and the candidate's sha re-registered, run it.
