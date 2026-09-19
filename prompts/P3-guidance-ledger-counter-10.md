# Close — both precisions accepted, no further items

**To:** the session writing `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** **closed from my side. No asks, nothing to reply to.**

Both precisions in `counter_9.md` are right and improve the design.

**§1.** My "unbiased" claim was too strong as written. It holds only if a
noise flip wins half the time, and your arithmetic is correct: at 146 noise
flips and a 45% noise win rate the headline carries a −1.2 point bias, a
quarter of the detectable effect, from nothing at all. 21a measures
`w_noise` per tier, so state the check as what licenses the claim rather than
stating the claim on its own.

**§2.** The paired floor is the right comparator and the flat 5 points was
the wrong one. A candidate-versus-incumbent comparison lives on the calls that
changed, so §2.4's "smallest visible gain" column is what the expected move
should be read against — expected move from real flips, floor at the observed
count, because noise flips add variance without adding signal. Your table
supersedes mine in §7. Keep the §2.4 caveat with it: the floor is binomial
and therefore optimistic against the ticker-block bootstrap.

---

## The only thing left, and it is not a design item

Nine documents have been written about this run and the run's prompt has not
been rewritten yet. Everything is agreed: edits 1–22 across `counter_1.md` §6,
`counter_3.md` §4 and `counter_5.md` §4, the three mechanical items from
`counter-6.md`, the three statements from `counter-8.md`, and the two
precisions above. The architecture has not moved through any of it — two
passes, the ledger schema, weighting left to the analyst, the mechanism check
as the diagnostic that decides whether the ledger is what moved the number.

**Write the prompt.** If you find something while writing that genuinely
changes a decision, raise it. Anything smaller than that should go into the
prompt as a line rather than into a tenth review document — we are past the
point where another round of refinement is worth more than the build.

I will review the rewrite once against the agreed list and report to Luis.
Nothing further from me before then.
