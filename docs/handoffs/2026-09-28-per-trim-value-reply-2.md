# Reply 2 — the control is right; two refinements

**Date:** 2026-09-28. **From:** review session, via Luis. **To:** architect session.
**Answers:** `docs/handoffs/2026-09-28-per-trim-value-counter.md`.

---

## Agreed

The counter is correct and the reply's reading was wrong. A trim into
QQQ can pay with no skill at all, and "range above zero" on row A alone
would have read "own QQQ" as "the analyst helps." Rows A, B and A − B,
both destinations, fixed P9 sizes, and the revised reading are all
accepted as written. Go.

## Refinement 1: match the control on time, not just on companies

Row B is "every train call." The value of trimming a random name into
QQQ depends heavily on *when*: in some quarters QQQ beat almost every
corpus name, in others (2022) it trailed most of them. B's flags are not
spread evenly over the calendar. If they cluster in quarters where QQQ
did badly against the corpus, A − B understates the analyst; if they
cluster where QQQ did well, it overstates.

**Fix.** Draw row B so its calendar-quarter mix matches row A's: for each
flagged call in A, one control call from the same calendar quarter,
drawn at random from all train calls (seed 11), resampled together with
A in each bootstrap draw. Report the unmatched "every train call" figure
beside it as a reference. The reading uses the matched version.

## Refinement 2: on the P9 sizes

Accept the fixed 5 / 2.5 / 0 sizes and the random-size control. Two
notes so the wrap-up is read correctly.

- **Per-trim value is linear in points moved.** So the P9 layer's
  question reduces to: is the per-point value in the most negative fifth
  larger than in the next fifth, and that larger than in the rest? Ask
  the CLI to report **value per point by P9 band** beside the sized
  version. It is the same information and easier to read.
- **5 points exceeds X.** The settled allocator moves a position at most
  2.5 points per session. A 5-point trim is two sessions' worth. That is
  fine for a per-trim value (it is just 2 × 2.5), but the eventual
  allocator would execute it over two months, and the second half would
  see one more month of price. Say so in the wrap-up; do not change the
  sizes.

## Nothing else

The veto layer as reported-only, the "index does the work" outcome
feeding the sleeve/index decision, and the order (per-trim → book test
with ALL16 first → P6D) all stand.
