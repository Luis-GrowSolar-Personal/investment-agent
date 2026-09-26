# Comments on `2026-09-26-next-steps-review.md` — four changes, rest agreed

**Date:** 2026-09-26 · **Status:** comments for review. Nothing run or changed.

## Agreed as written

- The order, and the veto-only role of the end-to-end check (review §1).
- Q1 ledger shape: write at step 1, amend after step 2.
- Q2: the company split is the promotion gate; the time split only constrains
  P8's generator. P8's "holdout 2025" wording is dropped.
- Q3: drop the lucky-cached-draw check.
- §3.1: the three flip definitions for B's noise floor (score moves ≥1, score
  moves ≥2, direction changes under the ≤ −2 / ≥ +3 mapping).

Nothing below touches the step-1 bookkeeping. Change 3 touches step 2.
Changes 1, 2 and 4 are pre-registration text for P7 and P9, and can be
settled any time before those runs.

---

## Change 1 — P7's bullish test must hold coverage fixed

**The problem.** The review's falsifier compares bullish precision at the
same cut (score ≥ +3). A prompt can raise precision at a fixed cut simply by
calling bullish less often. If P7 gives +3 to 120 calls instead of 242, and
they are the 120 most obvious, precision rises and nothing was learned. The
review's median-return check would not catch this. Fewer, better calls
raise the median too.

The bearish test already handled this correctly. Condition 2 on tune
required coverage of at least 1.5× v6's count *and* precision no worse than
5 points below v6's. The bullish test should carry the same pairing.

**Proposed.** Compare at matched coverage. Take P7's top 242 calls by score
(B's bullish count on tune), with ties broken by the seeded rule. Compare
their hit rate with B's 41.3% on its 242. This takes the threshold out of
the question entirely. Report the ≥ +3 cut too, labelled as secondary.

**On the "~6 points" figure.** It is right, but its source is mislabelled.
It is how much a 242-call hit rate near 41% moves from sampling alone:
roughly ±6 points. It is not something B's re-run noise floor supplies.
The noise floor measures how often B changes its own answer, which is a
different quantity. So the ~47% target can be written down now, from the
arithmetic, and step 2 does not need to supply it.

## Change 2 — "rank correlation must not fall below B's" fails a tie half the time

A candidate exactly as good as B lands below B about half the time, from
noise alone. As written, the second clause is a coin flip for any candidate
that doesn't improve ranking. That fails guardrail 1: one rule, one clause.

**Proposed.** "The paired difference in rank correlation (P7 minus B, on
the same calls) has its range's lower end no worse than −0.03." The −0.03
is a placeholder. Replace it with B's own run-to-run band once step 2
measures it (see change 3).

## Change 3 — step 2 should re-score all of train, not ~400 calls

**The difference.** About 400 calls cost ~$10. All 1,217 train calls cost
~$29 at B's $0.024 per call. That is ~$19 more.

**What the extra $19 buys.**

- **It measures the noise band for the primary metric directly.** Two B
  runs on the exact calls P7 will be compared on show how far B's rank
  correlation moves against *itself*. That is the number change 2 needs, and
  a 400-call subset can only estimate it indirectly.
- **It gives tighter flip rates per stratum.** Each stratum gets about 400
  calls instead of about 130. At a 15% flip rate, the range tightens from
  about ±6 points to about ±3.5. P7's net flip count is only as readable as
  this number.

**Proposed.** Full train re-score, ~$29, and the three flip rates from the
review's §3.1. Add one output: B-vs-B′ paired rank-correlation difference
with its ticker-block range.

## Change 4 — P9's calibration gate would reject the case the review calls usable

**The problem, in two parts.**

- **Monotone decile medians will fail even with real signal.** On ~1,200
  calls a decile holds ~120. Six-month returns against the S&P spread
  widely, so each decile's median carries roughly ±9 points of sampling
  noise. At a ranking strength near B's (0.13), neighbouring deciles differ
  by a point or two. Ten medians in strict order would be luck. That fails
  guardrail 4: a gate that cannot pass.
- **The 0.5–1.5 slope band rejects the "3× too optimistic" case.** The
  review says that case is usable with a scale factor, and it is right. But
  3× optimistic means a slope near 0.33, which the band rejects. The gate
  and the reasoning disagree. A model asked for a percentage will probably
  forecast wide (±20%) where the honest spread for a weak signal is narrow,
  so a low slope is the *expected* outcome.

**Proposed.**

- **Gate:** the slope of realized return on predicted return is positive,
  with its ticker-block range excluding zero. This rejects the case the
  review calls unusable, "uncalibrated in sign", and nothing else.
- **Reported, not gated:** the slope's value, which becomes the
  allocator-side scale factor. Also realized medians by fifths rather than
  tenths. Write down the expected slope now (my guess: 0.2–0.6) as a
  prediction, not a gate (guardrail 3).

---

## What changes either way

- **If change 3 is accepted,** step 2 costs ~$29 instead of ~$10, and P7's
  pre-registration gets its ranking tolerance from a direct measurement.
- **If changes 1 and 4 are rejected,** P7 can pass by making fewer bullish
  calls, and P9 can fail while being usable. Both are wrong-direction errors
  that would each cost a round (~$45) to discover.
- **Step 1 is unaffected** and can go as soon as this is settled. Steps 1
  and 2 then go to Code's CLI as a single prompt.
