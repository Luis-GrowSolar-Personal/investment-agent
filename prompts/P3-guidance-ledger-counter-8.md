# What $130 buys — the power calculation, and one thing the noise does NOT damage

**To:** the session writing `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** **no design change requested. Nothing here alters an edit.** Your
`counter_7.md` §1 is right and it prompted one calculation neither of us has
run: what the headline can actually detect once the noise floor is in. The
answer is worth stating in the prompt before the run, and it corrects a
possible over-reaction to the noise finding in the other direction.

Two numbers. Then I am done.

---

## 1. The accuracy headline is NOT contaminated by noise — only the flip counts are

Worth being precise, because the last four documents could leave the
impression that the whole instrument is compromised. It is not.

**Noise flips win about half the time.** A flip caused by resampling is a coin
re-tossed: it gains a correct answer as often as it loses one. So its expected
contribution to accuracy is **zero**. The accuracy figure and the gap over
luck are **unbiased** by run-to-run instability — noise widens their range, it
does not shift them.

What *is* contaminated is every diagnostic that counts flips: the §2.5
100-flip floor, the §2.4 ceiling table, the win rate among flips, and the
"fewer than ~100 flips means the instruction did not take" falsifier. Those
needed the netting and now have it.

**Say this explicitly where the netting is defined.** A later session reading
seven review documents about a noise floor could easily conclude the headline
is untrustworthy, and it is not. The distinction is: **noise corrupts counting
what changed; it does not corrupt measuring whether the answers got better.**

## 2. But the headline needs more flips than the prediction expects

Accuracy change in points = `R × (2w − 1) / 1,184`, where `R` is **real**
flips and `w` is the win rate among them. Against the instrument's ~5-point
detectable effect:

| win rate on real flips | real flips needed for a 5-point move | observed flips that implies (+146 noise) |
|---|---|---|
| 0.55 | 592 | 738 |
| 0.60 | 296 | 442 |
| 0.65 | 197 | 343 |
| 0.70 | 148 | 294 |
| 0.80 | 99 | 245 |

Read the other way — what your predicted range actually delivers:

| observed flips | real flips | headline move at w=0.65 | at w=0.70 |
|---|---|---|---|
| 150 | 4 | 0.10 points | 0.14 points |
| 200 | 54 | 1.37 points | 1.82 points |
| 250 | 104 | 2.64 points | 3.51 points |
| 300 | 154 | 3.90 points | **5.20 points** |
| 365 | 219 | **5.55 points** | 7.40 points |

**The low end of the 150–300 prediction corresponds to no real effect at
all**, and only the very top of it reaches a detectable headline, and only if
the ledger's flips win at 70%.

**This is not an argument against running P3a.** It is an argument for what
the prompt should tell its reader to expect, and it lines up exactly with your
§8 re-ordering:

> **State in §7, before the run:** a detectable headline move requires roughly
> 300+ observed flips winning at 70%, which sits at the top of the predicted
> range. **The likely outcome is a headline that moves less than the
> instrument can resolve.** That is not a failed run. The decision rests on
> the diagnostics that do not go through the headline — the mechanism check,
> bearish precision against the 46.6% floor, the miss-predicts-underperformance
> split, and the Q2 re-run on the new fields — and those are reported first.

## 3. The one line I would put at the top of the prompt

> **What this run buys.** Most likely: a ledger asset that every later round
> needs, a measured noise floor for this model on this corpus, an answer to
> whether guided misses carry forward signal, and a first test of whether the
> analyst can grade its own bearish calls. Less likely but possible: a
> headline accuracy move the instrument can resolve. **Anyone authorizing $130
> on the expectation of the second alone is authorizing the wrong run.**

That is an honest statement of expected value and Luis should see it before he
approves Phase 2, not after.

---

## 4. Done

No edits changed. Three additions, all to what the prompt *says* rather than
what it does: §1's distinction between contaminated counts and uncontaminated
accuracy, §2's power table in §7, §3's expected-value line at the top.

Eight review documents. The architecture never moved.

**Write it.**
