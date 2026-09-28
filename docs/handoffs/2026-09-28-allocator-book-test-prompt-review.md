# Allocator book test prompt — review

**Reviews:** `prompts/allocator-book-test.md`. **Verdict: go, with one
material addition (a no-skill control arm) and one change to the
stratified pools.** R1–R4 answered below.

---

## Addition: a random-trim control, or the headline can pass on QQQ alone

The per-trim run taught this lesson two days ago and the prompt has not
carried it over. Arm 3 moves money from single names into QQQ. QQQ is
less volatile than any single name and beat most of the corpus over the
period. So arm 3 will beat arm 0 on return per drawdown in most books
**whatever B and P9 say**, because holding more QQQ lowers drawdown
almost mechanically. Prediction 7 in the prompt admits as much. Arm 1
(QQQ alone) is in the table, but it is not a control for the trims: it
holds no names at all.

**Add arm 3R.** Same number of trims as arm 3 on that book, same sizes,
same calendar quarters, applied to **randomly chosen calls** of the
book's names (seed 11, one draw per book). It is arm 3 with the
analyst's choice of *which* call replaced by chance. Everything else
identical, including proceeds to QQQ.

**Readings, revised:**
- **"Severity-sized trims beat holding"** — arm 3 vs arm 0, as written
  (70% of books, median gain's range above zero, holds under
  company removal). This is the practical question.
- **"The analyst chose the trims"** — arm 3 vs arm 3R, same rule. This
  is the skill question. **The headline requires both.** A pass on the
  first alone reads "own more QQQ," which is a real result but a
  different allocator.

Arm 2 gets the same treatment (arm 2R) so reading 2 can be read the
same way. Cost: one more arm per book, minutes.

## Change: stratified pools 8 / 4 / 4, not 8 / 2 / 6

With 7 speculative names and 6 per book, every stratified book holds
almost the same six speculative names; there are only 7 ways to choose
them. The stratified set then varies only on its megacap side and tells
us nothing new about the speculative sleeve, which is where the trims
land. Use **8 megacap, 4 mid, 4 speculative**: 12,870 × 126 × 35
combinations instead of 12,870 × 36 × 7. It is one step further from
Luis's 8/2/6 shape and much closer to a test. State both the change and
the reason.

## R1–R4

- **[R1] Drop ALL16 here — agree, with the reason corrected.** B's
  scores on all 195 ALL16 calls already exist (the end-to-end run scored
  them, holdout names included), so the lock argument is partly moot.
  The real blocker is that P9 has no ALL16 scores, and scoring them is
  $10 of new spend outside a $0 prompt. ALL16 with P9 scored is exactly
  the tune/holdout confirmation of the finished allocator, so it belongs
  there. TRAIN6 reported-only is fine; a six-name equal-weight book is
  an odd object and the wrap-up should not lean on it.
- **[R2] Monthly sessions — agree.** Matches production, and the
  second half of a 5-point trim landing a session later is the
  behaviour the amendment asked to be stated.
- **[R3] Company-removal condition — agree.** 400 books from 55 names
  overlap heavily; this is the right guard, and the FSLR flip is the
  precedent.
- **[R4]** — see the change above.

## Small points, no change required

- Late listings sitting in QQQ until first price is identical across
  arms and cannot favour one. Fine.
- Trims measured in points of the book at each session, so a 5-point
  trim is two 2.5s at two valuations. Fine, and 3F is the check on it.
- Arm M feasibility-gated with no workaround: right. If it does not run,
  reading 4 waits.

## What it means

With arm 3R in, a pass says two things at once: the trims beat leaving
the book alone, and the analyst, not the index, chose them. Without it,
a pass cannot distinguish the analyst from a rule that says "sell
something every quarter and buy QQQ." That distinction is the whole
point of the rebuild.
