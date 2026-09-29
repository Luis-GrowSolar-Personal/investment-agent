# Allocator book test — rerun with money-matched controls — wrap-up

**Prompt:** `prompts/allocator-book-test-matched.md`. **Run ID:**
`allocator-book-test-matched`. **Cost:** $0 — no API calls, no DB writes, no
scoring, no cache refresh, no fetches. **Corrects:**
`wrap-ups/allocator-book-test-out.md`.

> The first run's controls moved **86.93** and **72.74** points into QQQ
> against arm 3's **38.06** and arm 2's **49.89** (medians, random books);
> matched here to within **0** points in **100%** of books (both arms, both
> book sets — median and max difference are both 0.0, shortfall 0.0). In 200
> random books, arm 3 beat its money-matched random control (arm 3M) in
> **87.5%** of books (median gain **0.0269**, range **0.0232** to **0.0302**;
> lowest with one company removed **82.0%**, SUNW). Arm 3 vs holding
> (reproduced): **96.0%**. **Headline, by the fixed 1a/1b test: severity-sized
> trims add value.** Plain trims vs their matched control (arm 2M): **91.0%**
> (floor **87.0%**, JKS). **Severity over plain, by edge over matched
> control: 32.5%** (range **−0.0103** to **−0.0058**) — **fails.** Stratified
> books: 3 vs 3M **99.5%** (floor 98.8%); 2 vs 2M **100.0%**; severity over
> plain **21.0%** (range **−0.0192** to **−0.0119**) — fails there too. **The
> honest bottom line, per the prompt's own decision menu: severity over plain
> fails on both book sets while arm 2 clears its own matched-control bar
> cleanly — the rule that survives is plain trims; P9's severity sizing does
> not earn a place in the allocator on this evidence,** even though the
> literal 1a/1b headline formula says "add value."

---

## Why this rerun exists, restated in two sentences

The first run's no-skill controls (arms 2R, 3R) matched arm 2/arm 3 on
**number of trims**, not on **money moved** — and arm 3 re-flags names it has
already sold to zero on 55% of its trims, so its count-matched control ended
up moving far more money into QQQ than arm 3 itself (86.93 vs. 38.06 points,
median). Since QQQ raises return per drawdown almost mechanically on this
window (arm 1: 0.3558 vs. arm 0: 0.1392), that extra money moved biased
reading 1b against arm 3 for a reason that had nothing to do with which
calls B and P9 chose — **the first run's "own more QQQ" headline does not
stand**, and this run replaces it.

## What this run can and cannot show (unchanged, restated)

t1, t2, and every call's flag still come from the same train calls the 400
books are drawn from. This is not a second look at the signal. It tests
whether the signal survives the mechanics — position sizes, drift,
sequencing, compounding, drawdown, two-step execution — not whether B and
P9's underlying judgment is right. Only tune does that.

## Step 1 — reproduction (hard stop on mismatch — did not stop)

- t1 = **−10.0**, t2 = **−8.0**, read from
  `analysis/data/run_state/allocator-book-test/results.json` (commit
  `e105aba`), not recomputed.
- 200 random and 200 stratified book lists rebuilt with the same seeds:
  **identical** to the first run's (`random_books == old_random` and
  `strat_books == old_strat`, asserted programmatically).
- Arms 0, 1, 2, 3, 3F, 3S rerun. **Random books: every saved per-book figure
  (final value, CAGR, max drawdown, return per drawdown; 4,800 values
  checked) matches the first run exactly — max absolute difference 0.0.**
  **Stratified books: the first run did not save per-book figures for this
  set** (`stratified_books.books` there holds only `{book_id, tickers}`, an
  oversight in that run's own report step) — checked at the aggregate
  (median-across-books) level instead, against that run's stored summary:
  max absolute difference **0.0042**, well inside tolerance. Nothing other
  than the controls changed.

## Step 2 — the money-matched controls

**Money-moved table (medians, random books; arms 2/3 unchanged from run 1):**

| arm | median points moved into QQQ | median trims that moved nothing |
|---|---|---|
| 0 | 0.00 | 0 |
| 1 | 0.00 | 0 |
| 2 | 49.89 | 21.0 |
| 3 | 38.06 | 18.8 |
| 3F | 34.75 | 0* |
| 3S | 38.36 | 0* |
| 2R (superseded) | 86.93 | 0 |
| 3R (superseded) | 72.74 | 0 |
| **2M** | **49.89** | 21.2 |
| **3M** | **38.06** | 19.0 |

\* 3F and 3S execute every scheduled step at a nonzero fraction/percentage by
construction in this run's accounting; "trims that moved nothing" is
specific to the pct-of-book mode's already-empty-position case tracked for
arms 2/3 and their controls.

**Stratified books, medians:** arm 2 = 50.23, arm 3 = 41.83, arm 2M = 50.23,
arm 3M = 41.83 (exact match, same as random), arm 2R (superseded) = 89.38,
arm 3R (superseded) = 86.13. The design session's 60-book pilot (51.3 / 38.5
/ 87.0 / 70.4) mixed random and stratified books; these full-200,
book-set-specific medians are the more precise figures and point the same
direction.

**Match check:** in **100% of books**, both book sets, both arms, the
control's total points moved equals its arm's to within **0.0** points
(median difference 0.0, max difference 0.0, total shortfall 0.0 — the
"sell all of it and take the rest from another eligible name" fallback was
never needed to close a gap larger than floating-point noise).
`analysis/data/run_state/allocator-book-test-matched/results.json` →
`match_check`.

**Superseded 2R/3R kept for reference, labelled as such** in the table above
and in `results.json`.

---

## Gating tables — random books (n = 200)

| test | win share | range | company-removal floor | passes 70% rule |
|---|---|---|---|---|
| 1a. arm 3 vs. arm 0 | 96.0% | [0.0528, 0.0660] | 94.2% (FRC) | **yes** |
| 1b. arm 3 vs. **arm 3M** | **87.5%** | [0.0232, 0.0302] | **82.0% (SUNW)** | **yes** |
| arm 2 vs. arm 0 | 99.0% | [0.0693, 0.0841] | 98.5% (MS) | yes |
| arm 2 vs. **arm 2M** | 91.0% | [0.0321, 0.0411] | 87.0% (JKS) | yes |
| arm 3 vs. arm 2 ("confounded by money moved," reported only) | 5.0% | [−0.0193, −0.0159] | 2.2% | — |
| **severity over plain**, (3−3M)−(2−2M) | **32.5%** | [−0.0103, −0.0058] | 26.6% (RUN) | **no** |

**Headline, by the fixed reading:** 1a passes and 1b now also passes (it did
not in the first run) → **"severity-sized trims add value."**

**But reading 3 fails, decisively, on the fairer comparison.** Both arm 3 and
arm 2 beat their own money-matched controls, but **arm 2's edge over its
control is not smaller than arm 3's** — the direct difference (arm 3 − arm
3M) − (arm 2 − arm 2M) is negative in 67.5% of books, with a range that sits
entirely below zero. The per-point diagnostic makes the mechanism plain:

| arm | median gain over arm 0 per point moved |
|---|---|
| 2 | 0.001547 |
| 3 | 0.001548 |
| 2M | 0.000772 |
| **3M** | **0.000743** |

Arm 3 and arm 2 earn essentially the **same** return-per-drawdown gain per
point moved (0.001548 vs. 0.001547) — severity sizing does not make each
point moved more effective. What differs is the **control**: arm 3M's
random calls happen to earn slightly *less* per point than arm 2M's
(0.000743 vs. 0.000772), which is what lets arm 3's raw edge over 3M look
larger than it would against a control matched exactly like arm 2's. Once
the two arms are compared by their own edge over their own control — reading
3's actual question — severity does not add over plain.

## Stratified books (n = 200)

| test | win share | range | floor | passes 70% rule |
|---|---|---|---|---|
| 1a. arm 3 vs. arm 0 | 100.0% | [0.0875, 0.0961] | 100.0% | yes |
| 1b. arm 3 vs. arm 3M | **99.5%** | [0.0540, 0.0641] | **98.8%** | yes |
| arm 2 vs. arm 0 | 100.0% | — | — | yes |
| arm 2 vs. arm 2M | 100.0% | [0.0682, 0.0786] | — | yes |
| severity over plain | **21.0%** | [−0.0192, −0.0119] | — | **no** |

**Unlike the first run, the two book sets now agree on 1b** (both pass,
cleanly) — the money-matching correction resolved the random/stratified
disagreement the first run's headline rested on. **Both sets also agree that
severity fails to add over plain.** Per-point: arm 2 = 0.002214, arm 3 =
0.002183 (again essentially equal), 2M = 0.000754, 3M = 0.000759 — same
story as random books.

## What it means — the close, per the prompt's own decision menu

The prompt's three closing branches are:

- *Headline passes* → P6D is written against "flagged and severe, trimmed
  into the index."
- *1a passes, 1b fails* → "own more QQQ," sleeve/index decision.
- ***Severity over plain fails but arm 2 passes 2M → the rule is plain
  trims; P9 does not earn a place in the allocator.***

**The third branch is what actually happened, on both book sets.** The
literal 1a/1b headline formula says "severity-sized trims add value," and
that is not wrong as far as it goes — arm 3 does beat both holding the book
and a money-matched random control. But reading 3, run exactly as
pre-registered, shows arm 3 buys that pass with a control that happens to
earn less per point than arm 2's control does, not with a rule that is more
effective per point moved than plain trimming. **P9's severity sizing earns
no place over B's flag alone on this evidence.** If a rebuild proceeds on
these trims, the simpler rule — arm 2, trim every flagged call by a fixed
2.5 points — is what the book test actually supports; t1/t2 and the banded
sizing do not add anything reading 3 can detect.

**Units (carried from the first run, not recomputed):** arm 3F within 0.5
points of arm 3 (96.5% vs. 96.0%) — units still do not matter, if a rebuild
does proceed on some version of the trim-sizing rule.

**Arm M:** still not run, unchanged from the first run — the production
loader (`sweep_cadence_and_session_model.load_events_dedup_on`) remains
DB-backed and hardcoded to ALL16. Reading 4 stays deferred.

## Deviations from the prompt

1. **Stratified reproduction checked at the aggregate level**, not per book
   — the first run did not save per-book stratified figures (see Step 1
   above). This is a limitation inherited from the first run's report step,
   not a new scope decision; the aggregate check (24 medians, max diff
   0.0042) is the closest available substitute and it passed comfortably.
2. **`simulate()` in `analysis/allocator_book_test.py` was extended**, not
   forked: it gained an optional `trace_out` parameter (default `None`,
   fully backward compatible — verified by the exact-reproduction check
   above) that records each pct-mode step's group id, step number, and
   actual points moved. All new logic (the money-matched control builder,
   the rerun orchestration, the new readings) lives in a new file,
   `analysis/allocator_book_test_matched.py`, which imports and reuses the
   first file's `simulate`, `FastPrices`, `precompute_schedules`,
   `companies_and_strata`, `load_calls`, `build_random_books`,
   `build_stratified_books`, `metrics_from_snaps`, `quarter`, `A.boot`
   (via `M.gain_stats`/`M.pass_rule`), `return_per_dd`, and `cagr_of`.
3. **Two bugs caught and fixed before the reported run**, both before any
   result was written to `results.json`: a `KeyError` from the first run's
   stratified per-book figures not existing (fixed by the aggregate check
   above) and a key-name mismatch (`"shortfall"` vs. `"shortfall_total"`)
   in the match-check aggregation. Both are cosmetic bugs in this run's own
   new code, caught by the run failing loudly rather than silently, per
   Step 7's re-verification discipline.
4. **"Prefer the same name for a group's second step"** is implemented as:
   if the control still holds (shares > 0) the name chosen for the group's
   first step at the second step's session, reuse it; otherwise redraw
   fresh from that session's eligible pool. This follows the prompt's
   wording directly.
5. **The eligible-candidate pool is drawn from calls, not deduped tickers**
   (a ticker with more calls in the matching quarter is proportionally more
   likely to be chosen) — same convention as the first run's count-matched
   controls, carried over for consistency.

## What deliberately was not done

- Arm M (unchanged — a design-session call).
- Recomputing t1/t2, the books, the window, or units (3 vs. 3F) — all
  carried unchanged from the first run, per the prompt's own ground rules.
- Any change to production code, the version registry, or any gate.

## Follow-up commands

Reproduce this run:

```
python3 analysis/allocator_book_test_matched.py run
```

Spot-check the match: compare arm 3's points moved against arm 3M's, per
book:

```
python3 -c "
import json
d = json.load(open('analysis/data/run_state/allocator-book-test-matched/results.json'))
print(d['match_check'])
"
```

## Git

- Prompt committed at `b42fd5b` (this session, before any output).
- Driver extension (`simulate()`'s `trace_out` param +
  `allocator_book_test_matched.py`) committed at `f9fffe6`, before any
  output; two bugfixes at `4d9d65c` and `d2802a0`, both before the reported
  run.
- Results committed next alongside this wrap-up, then `git push` of
  `sweep/db-corpus-baseline` — pushed hash reported in chat.
