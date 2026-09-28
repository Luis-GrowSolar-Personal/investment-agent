# Book test, Amendment 1 — review

**Reviews:** Amendment 1 of `docs/handoffs/2026-09-28-allocator-book-test-design.md`,
with `wrap-ups/per-trim-value-out.md`. **Verdict: agree, with one
addition (a reported-only arm) and two things to say in the wrap-up.**
Items 1–6 of the amendment stand as written.

---

## What the per-trim run showed, in one paragraph

Trimming everything B flags does not clearly pay: +$138 per trim on
$100,000, range includes zero, and only $110 better than a no-skill trim
in the same quarter. The reason is in the tail table: 52 of 374 flagged
calls went on to beat the S&P by 20+ points and cost more than the
avoided losses earned. P9 fixes it. Its five severity bands, within
flagged calls, run in perfect order: the most severe fifth fell 30
points per point trimmed, the next 13, then 12, then 0, and the mildest
fifth **rose 28**. Trimming only the two most severe fifths earns $342
per flagged call more than a no-skill trim, range above zero on both
draws. That is the strongest allocator-side result in the project so
far. It is on train, on the same calls where P9's severity was first
found, so it is a lead until tune says otherwise. The amendment says
this and it is right.

## Agreed

- **Arm 3 is the candidate; arm 2 is expected to fail.** The choice is
  informed by a pre-registered per-trim result, not by peeking at the
  book test. Fine.
- **t1 and t2 fixed before any arm runs and carried unchanged to tune.**
  This is the right fix for the look-ahead in the per-trim run's fifths.
  One expectation to write down: the amendment's flag set (mean of B's
  two draws ≤ −2) is not the per-trim run's pooled set (each draw's
  flags, 374 rows), so the book test's flagged count and the $342 figure
  will not match. They should point the same way.
- **Speed limit, drop the veto, arm 3S, QQQ prerequisite.** All as
  written. The veto is dead for a good reason: B already does not flag
  beat-and-raise calls, so there is nothing to veto. The QQQ prompt's
  integrity checks (every existing key identical, legacy cache frozen)
  are the right way to add a ticker to a frozen file.

## Addition: one reported-only arm, because trim units decide who gets sold

Trims are in **points of the book**. Sixteen names at equal start are
6.25% each, so a 5-point trim is 80% of a starting position. After
drift, the same rule sells a 2% laggard outright and gives a 20% winner
a 12.5% haircut. So arm 3's value on a given book depends on how large
each flagged name is at flag time, which is Luis's original objection
returning through the sizing units. That is how the real allocator
works (X is in book points), so arm 3 stays as it is. But the book test
should separate the signal from the units:

- **Arm 3F, reported only:** the same t1/t2 rule, with the trim as a
  **fraction of the position**: band 1 sells 80%, band 2 sells 40% (the
  same 5/6.25 and 2.5/6.25 ratios at equal start). Same speed limit, in
  position fractions.
- **Per book, report the share of trims that sold the whole position**
  under arm 3.

If arm 3 and arm 3F agree, the units don't matter and the P6D spec can
pick whichever is simpler to run live. If they disagree, the book test
has found that the allocator's value comes from *which* positions
happen to be small when flagged, and that is a design question for the
sleeve/index decision, not a finding about B or P9.

## Two things for the wrap-up

1. **What the book test can and cannot show for arm 3.** Its thresholds
   and its selection come from the same train calls the books are
   drawn from. The per-trim value is the same data in a different
   aggregation. So the book test is not a second look at the signal. It
   tests whether the signal survives the *mechanics*: position sizes,
   drift, sequencing, compounding, drawdown, and the two-session
   execution of a 5-point trim. A pass means the mechanics don't eat
   it. A fail means they do, and the fix is in the mechanics. Tune is
   the only second look at the signal, and it is spent once.

2. **Band 5 is the first thing in the project that looks like a bullish
   lead, and it should be written down as one, not spent on.** Flagged
   calls that P9 rated mildest rose 28 points against the S&P on average
   (74 calls). That is a mean, and means are made by a few names. Ask
   for the median and the top three contributors in the book test
   wrap-up, at $0. If the median is also well above zero, the lead is
   "B and P9 disagree → watch, do not trim." It is transcript-derived,
   so under the closed-routes rule it earns no train candidate and no
   tune look. It earns a line in the live forward test: score both B
   and P9 live, and grade the disagreement cases in a year.

## What it means

Run the book test as amended, with arm 3F beside arm 3. If arm 3 clears
its 70% rule and arm 3F agrees, P6D is written against P9-sized trims
into the index with t1/t2 frozen, and the tune look goes to that
allocator on tune-company books. If arm 3 clears and arm 3F does not,
the sleeve/index decision has to settle position sizing before P6D.
