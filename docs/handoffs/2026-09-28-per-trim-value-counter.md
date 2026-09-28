# Counter to "per-trim value first, then the book test"

**Date:** 2026-09-28. **From:** architect session, via Luis. **To:** review session.
**Answers:** `docs/handoffs/2026-09-28-per-trim-value-reply.md`.

---

## Accepted without change

- **Per-trim, not per-book.** A single book is one draw. ALL16 flipping on
  FSLR alone shows it. Per-trim value is a fact about the analyst.
- **The counterfactual.** A trim replaces *holding the name*, and the money
  goes to the index. Not "flagged versus unflagged."
- **Mean, not median, with the best-10% / worst-10% breakdown.** Dollars add.
- **Order.** Per-trim value → book test (ALL16 first) → P6D.
- **Item 2 correction.** B's bearish skill was already confirmed on tune
  (ranking 0.140). Decision 5 is rewritten so the next tune and holdout look
  goes to the finished allocator, not the analyst.
- **Item 3.** The sleeve/index split and the veto rule get their own written
  decision before P6D.

## The one change: the pass/fail reading has no control

The reply's reading is: *protection pays if the mean per-trim value has its
range above zero.*

That can pass with an analyst that has **no skill at all.** A trim only needs
QQQ to beat the stock that was sold. On train, about 47% of all calls lagged
the S&P by more than 5 points, whatever the analyst said. QQQ beat the S&P
over most of the period. So moving 2.5 points from a **randomly chosen** name
into QQQ very likely pays on its own.

If it does, a positive mean says **"own QQQ,"** not **"the analyst helps."**
Those point to different allocators.

### Fix, fixed before the run

Compute the same per-trim value, same definition, for two sets of calls:

| row | trims applied to | what it measures |
|---|---|---|
| **A** | B's flagged calls (score ≤ −2), each draw and pooled | the reply's number |
| **B** | **every** train call | what a trim rule with no skill earns |
| **A − B** | — | **what the analyst adds** |

Ticker-block range on A − B, 2,000 draws, seed 11, with A and B resampled
together from the same companies in each draw.

**Pre-registered reading, revised:**

- **The analyst pays** if A − B has its range above zero.
- If A is above zero but A − B is not, the finding is that **index-by-default
  does the work and the flags add nothing.** That is still a result. It feeds
  directly into the sleeve/index split decision.
- If A itself is not above zero, the rebuild does not proceed on B's trims
  (unchanged from the reply).

## Two smaller additions

1. **Run both destinations: QQQ and SPY.** The bearish skill was measured
   against the S&P. With QQQ as the only destination, QQQ's lead over the S&P
   in this period mixes into the result. Report A, B and A − B for each. If
   A − B holds against both, it is not a QQQ effect.

2. **Fix P9's trim sizes before the run.** Otherwise the P9 layer is fitted
   after the fact rather than tested. Proposed:

   | P9 severity band (within flagged calls) | trim size |
   |---|---|
   | most negative fifth | 5 points |
   | next fifth | 2.5 points |
   | remaining three fifths | 0 |

   Row B for this layer: the same size mix applied to every call at random,
   seed 11, so the control makes the same total number of trims.

The guidance-veto layer uses the same A − B reading, with raised-guidance calls
removed from A. It is reported as found after the fact (15 calls on the
original count) and cannot pass the gate by itself.

## What gets written next

The per-trim value prompt (`./prompts` → `./wrap-ups`), carrying: the reply's
per-trim definition; rows A, B and A − B; both destinations; the fixed P9
sizes; the veto layer; and the revised reading above, all fixed before the
run. Cost unchanged: $0, scores exist.
