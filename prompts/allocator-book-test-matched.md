# Allocator book test — rerun with money-matched controls — $0

**Run ID:** `allocator-book-test-matched`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/allocator-book-test-matched-out.md`
**Cost: $0.** No API calls, no DB writes, no scoring, no cache refresh, no
fetches.
**Corrects:** `prompts/allocator-book-test.md` / `wrap-ups/allocator-book-test-out.md`.

---

## Why this rerun exists

The first run's no-skill controls (arms 2R and 3R) matched arms 2 and 3 on
**number of trims**, not on **money moved**. Arm 3 keeps trimming names it
has already sold to zero (55% of its trims moved nothing), while the
control picks only from names still held. The design session recomputed
money moved on 60 random and 60 stratified books with the committed
driver:

| | median points of the book moved into QQQ |
|---|---|
| arm 3 | 38.5 |
| arm 3R | 70.4 |
| arm 2 | 51.3 |
| arm 2R | 87.0 |

The control moved more than its arm in **120 of 120 books**. On this
window, money in QQQ raises return per drawdown almost by itself (arm 1,
QQQ alone: 0.356; arm 0, the book held: 0.139). So reading 1b ("the
analyst chose the trims") was biased toward the control. The first run's
headline, "own more QQQ," does not stand. The same confound affects
arm 3 vs arm 2: arm 2 moved more money.

**What changes:** the two controls, and the reading that compared arm 3
with arm 2 directly. **What does not change:** t1 = −10.0 and t2 = −8.0
(frozen, commit `e105aba`), the books, the window, the sessions, arms 0,
1, 2, 3, 3F and 3S, the pass rule, and readings 1a, 4, 5 and 6. This
correction is fixed before any matched result is computed.

**Read first:** both documents above; `analysis/allocator_book_test.py`
(extend it; do not fork).

---

## Ground rules

1. $0. Train companies only. No new thresholds.
2. **Do not overwrite** `analysis/data/run_state/allocator-book-test/`.
   This run writes to `analysis/data/run_state/allocator-book-test-matched/`.
3. Every reading below is fixed now. Do not add conditions after seeing
   results. Diagnostics must be labelled diagnostic-only.
4. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

`progress.json` first, in the new state directory. Commit this prompt on
its own (`prompt: allocator book test, money-matched controls`). Clean
tree; hard stop if `git_dirty` cannot be recorded `false`. Driver changes
committed on their own before any output.

## Step 1 — reproduction (hard stop on mismatch)

- Read t1 and t2 from the first run's `results.json`. Do not recompute.
- Rebuild the 200 random and 200 stratified books with the same seeds.
  **Assert the book lists are identical** to the first run's.
- Rerun arms 0, 1, 2, 3, 3F and 3S. **Assert every saved figure matches
  the first run** (final value, CAGR, max drawdown, return per drawdown,
  per book). A mismatch means something other than the controls changed:
  stop and report.

## Step 2 — the money-matched controls

**Record each fixed arm's trim trace.** For arms 2 and 3, per book and
phase, record every trim step: its session, and the **points of the book
it actually moved** (sell value ÷ book value × 100, which is **0** when
the position was already empty).

**Arm 3M (replaces 3R as the control for arm 3).** Replay arm 3's trace.
At each step that moved p > 0 points, the control moves **p points of its
own book** into QQQ:
- Pick a call at random from the book's calls whose action session falls
  in the **same calendar quarter**, among names the control still holds
  (any call, flagged or not). Seed `(11, book_id, "3M", phase)`.
- For the second step of a two-step group, use the same name as the
  first step if the control still holds it; otherwise draw again.
- If the picked position is smaller than p, sell all of it and take the
  rest from another random eligible name, until p is moved or no eligible
  name is left. Record any shortfall.
- Steps where arm 3 moved 0 points produce **no** control trim.

**Arm 2M:** the same, replaying arm 2's trace.

**Check (report, and stop if it fails):** per book, the control's total
points moved equals its arm's to within 0.5 points in at least 95% of
books. Report the median and largest difference and the total shortfall.

Keep arms 2R and 3R in the output, labelled **"superseded: count-matched,
not money-matched,"** for reference only.

**Save per book and arm** (this was missing from the first run's
`results.json`): final value, CAGR, max drawdown, return per drawdown,
number of trims, **trims that moved nothing**, **points moved**, full-sell
share.

---

## Pre-registered readings (fixed now)

The pass rule is unchanged: in the random books, X beats Y in **at least
70%** of books, **and** the median gain's range (2,000 resamples of books,
seed 11) is above zero, **and** the win share stays at or above 70% with
each single company removed in turn (report the lowest share and which
company). Stratified books: the same test, reported separately.

1. **Headline — "Severity-sized trims add value"** requires both:
   - **1a. "Beat holding":** arm 3 beats arm 0. Reproduced from the first
     run.
   - **1b. "The analyst chose the trims":** arm 3 beats **arm 3M**.
   If 1a passes and 1b does not → **"own more QQQ."**
2. **"Plain trims add value"** — arm 2 vs arm 0, and arm 2 vs **arm 2M**.
3. **"Severity adds over plain" (replaces arm 3 vs arm 2).** Arms 2 and 3
   move different amounts of money, so they are compared by their edge
   over their own money-matched control. Per book:
   **(arm 3 − arm 3M) − (arm 2 − arm 2M)**, in return per drawdown.
   Severity adds if this is above zero in at least 70% of random books,
   with the same range and company-removal legs. The old direct arm 3 vs
   arm 2 comparison is reported, labelled "confounded by money moved."
4. Arm M: still not run (it needs a loader that works without the
   database). Reading deferred, as before.
5. Units (3 vs 3F): carried from the first run, not recomputed.

**Diagnostic, not a condition:** for arms 2, 3, 2M and 3M, the median
gain over arm 0 **per point moved**.

---

## Report step

`wrap-ups/allocator-book-test-matched-out.md`, `.md` only. Open with:

> The first run's controls moved ___ and ___ points into QQQ against arm
> 3's ___ and arm 2's ___ (medians, random books); matched here to within
> ___ points in ___% of books. In 200 random books, arm 3 beat its
> money-matched random control (arm 3M) in ___% of books (median gain
> ___, range ___ to ___; lowest with one company removed ___%, ___).
> Arm 3 vs holding (reproduced): ___%. **Headline: [severity-sized trims
> add value / own more QQQ / do not add value].** Plain trims vs their
> matched control (arm 2M): ___%. Severity over plain, by edge over
> matched control: ___% (range ___ to ___). Stratified books: 3 vs 3M
> ___%; 2 vs 2M ___%; severity over plain ___%.

Then: a money-moved table (every arm, median points moved and trims that
moved nothing, random and stratified); the gating tables; the per-point
diagnostic; the reproduction check; the match check; the superseded
2R/3R rows beside 2M/3M.

**Say plainly** that this corrects the first run's headline, and why, in
two sentences. Restate what the book test cannot show: the flags, t1 and
t2 come from the same train calls, so this tests the mechanics, not the
signal. Tune does that.

**Close with what it means:**
- Headline passes → P6D is written against "flagged and severe, trimmed
  into the index," with t1/t2 frozen. The tune look goes to that
  allocator, on tune-company books.
- 1a passes, 1b fails → "own more QQQ": the sleeve/index decision, not
  P6D.
- Severity over plain fails but arm 2 passes 2M → the rule is plain
  trims; P9 does not earn a place in the allocator.

Plain-language discipline is binding. Anchor every percentage to what it
is a percentage of.

## Standing rules

`python3`, zsh, macOS Tahoe. `sweep/db-corpus-baseline`. Provenance for
every figure (file and key). One prompt in, one wrap-up out. **Finish with
`git push`** after the wrap-up commit and report the pushed hash. If the
push fails, say so and never force.
