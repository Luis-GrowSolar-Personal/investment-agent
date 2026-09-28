# Reply to "Where things stand (26 Sept)" — per-trim value first, then the book test

**Date:** 2026-09-28. **From:** review session, via Luis. **To:** architect session.
**Answers:** the three items to settle, and the "what I'd do first" proposal.

---

## Agreed: measure whether protection pays, before building on it

Item 1 is the right first step. One change to how it is defined, so the
answer is about the analyst and not about a book.

**Measured per book, "dollars saved" is a fact about the book.** A book
of winners shows no savings; a book of losers shows huge savings; a book
with small positions in its losers shows small savings. None of that is
the analyst's value. It is the initial conditions.

**Measured per trim, it is a fact about the analyst.** Define the value
of one trim as follows, and average it over every flagged call on train.

- A flag moves **X = 2.5 points of the book** from the name to **QQQ**.
- Its value over the next 182 days is
  **2.5 points × (QQQ's return − the name's return)**, tradeable entry
  as everywhere.
- Worked: a name that falls 15 while QQQ rises 1 saves 0.4 points of the
  book, $400 on $100,000. A clipped winner that rises 30 while QQQ rises
  1 costs 0.725 points, $725.
- Average over B's flagged calls (score ≤ −2, both draws, reported
  separately and pooled). Clipped winners are already inside the average
  as negative entries; they do not need a separate accounting.

**Report the mean, not the median.** Dollars add. Then decompose it:
how much of the total comes from the **best 10%** of trims (avoided
disasters) and the **worst 10%** (clipped winners). That shows whether
the result is a few big saves against a few big misses, or a broad
small edge. Ticker-block range on the mean, 2,000 draws, seed 11.

**Layer P9 on top the same way:** the same per-trim value, with the trim
sized by P9's severity band instead of a fixed 2.5. And the guidance
veto: the same mean with raised-guidance calls removed from the flagged
set.

**Pre-registered reading.** "Protection pays" if the mean per-trim value
has its range above zero. If it does not, the allocator rebuild does not
proceed on B's trims, and the rest of this note is moot.

**One correction to the proposal's wording.** "Flagged versus unflagged
average return" is not the right comparison. The counterfactual to a
trim is *holding the name*, and the money goes to *QQQ*, not to the
unflagged names. The definition above uses both.

Cost: $0, half a day. The scores exist.

## ALL16 whole-portfolio: already measured once, and that is the problem

Luis's instinct is to start with ALL16 and see how the whole portfolio
fares. That was done in the end-to-end run: B3 finished at $210,351 with
a 16.97% drawdown, against $200,214 and 20.12% for v6 on the same model.
Then the 16-way leave-one-out showed the final-value result **flipping
on FSLR alone**, while drawdown was better in all 16 cuts.

That is the per-book problem from the other side. One book is one draw,
and its answer depends on which names are in it. So ALL16 should be run
as the **first row of the allocator book test**
(`docs/handoffs/2026-09-28-allocator-book-test-design.md`), read
against 200 random and 200 stratified 16-name books from the train
companies, all in the same script. The per-trim value above says whether
that test is worth running at all.

**Order:** per-trim value → book test (ALL16 first, then the
distribution) → P6D written against the result.

## Item 2: the tune look — partly moot, and pointed at the wrong layer

B's bearish skill has **already been confirmed on tune**: ranking 0.140,
bearish coverage about twice v6 at equal accuracy (P6B tune
confirmation). So the tune look does not need to go to "does the
bearish skill hold on unseen companies." It already did.

Decision 5 should still be rewritten, but to say: **the next tune and
holdout look goes to the finished allocator**, run on tune-company books
the way the book test runs on train-company books. Not to the analyst.

## Item 3: agreed, and it needs its own written decision

Trim proceeds go to the index. That makes the index the default holding
and the direct names deliberate bets against it. This is a real change
to the barbell and should be decided in a document, not inherited from
allocator code.

The shape proposed in review: a **direct sleeve** of Luis's names, held
at their starting weights and never rebalanced toward equal weight, and
**QQQ or SPY as the second line**, which carries the long tail and
receives every trim. The number Luis is deciding is the **sleeve/index
split** (60/40 was offered as a starting point, not a finding). That
decision and the veto rule belong in the same document, before P6D.

## What to write next

The per-trim value prompt (`./prompts` → `./wrap-ups`), with the
definition, the 10% tail decomposition, the P9 and veto layers, and the
reading above fixed before the run.
