# Consensus-surprise full test — review

**Reviews:** `docs/handoffs/2026-09-27-consensus-full-test-review-brief.md`,
`prompts/consensus-surprise-test.md` (with amendments 1–6),
`wrap-ups/consensus-surprise-screen-out.md`.
**Verdict: go, with one primary reading declared and two conditions on
it.** Everything else in the prompt stands as reported-only.

The question Luis is asking is narrower than the prompt's three
readings: **does knowing the consensus surprise make B's non-bearish
calls better at finding winners?** The primary should ask exactly that.

---

## 1. One primary reading (answers Q1)

**Primary.** Among train calls that B scored **0 or higher** (mean of
its two draws), the rank correlation of **quarter-adjusted surprise**
with the 182-day return vs SPY. Pass: ticker-block range above zero.

Why this one and not the others:
- "Drift present" (surprise alone, all calls) can pass on the misses.
  Misses sit in the bearish pile, which B already reads. That is not a
  bullish signal.
- "Adds to B" (combined minus B) has the same flaw: the gain can come
  from the downside, where surprise and B agree.
- "Finds winners" (top-19% big-winner share) is the right question but a
  weak instrument: ~230 calls, a share near 13%, so it cannot see a
  difference under about 6 points.
- Restricting to B ≥ 0 removes the downside from the test by
  construction. About 1,000 train calls remain, so the instrument keeps
  its power. If surprise sorts winners among the calls B has already
  cleared, it improves B's bullish calls. If it does not, nothing else
  matters.

**Direction check, reported not gated.** Top 19% by combined (B and
surprise, average percentile rank) against top 19% by B alone: paired
big-winner share, with range. It should point the same way as the
primary.

Everything else in items 1–6 and amendments 1–6 stays, labelled
reported-only.

## 2. Two conditions on a pass

**(a) The sign must hold on the 37 unscreened companies** (answers Q3).
The screen saw 439 calls, and this review declares the primary after
seeing them. Report the primary on the pooled 57 and separately on the
~760 calls from companies the screen did not touch. A pass requires the
pooled range above zero **and** a positive point estimate on the
unscreened set. The unscreened set is not asked to clear zero on its
own; it is asked not to disagree.

**(b) The sign must survive dropping any one year.** The screen's
by-year figures were −0.22 in 2024 and +0.37 in 2025. Winners cluster
in sector-years (solar/storage 2025), and a ticker-block bootstrap does
not see that clustering: the same companies carry the same year. Recompute
the primary with each calendar year removed in turn. A pass requires the
point estimate to stay positive in every cut. A signal that vanishes
when 2025 is dropped is one year's story, not a signal.

## 3. Sector-adjusted surprise: a label, not a gate (answers Q2)

Do not gate on it. The sector-quarter cells are thin (5-call minimum
with fallback), and the screen's within-sector-year figure rested on 225
calls with a very wide range. Use it to **label** a pass:
- primary passes and the sector-quarter-adjusted version is also
  positive → "company-picking signal; candidate for the analyst";
- primary passes and the sector-quarter version is flat → "sector-level
  signal; allocator input for sector tilt, not for the analyst."

Both outcomes are useful. They go to different layers.

## 4. Point-in-time checks before the verdict (answers Q4)

Eight is enough, with one change to where they come from: the five
unflagged rows should be drawn from the top and bottom 5% **among the
calls that enter the primary** (B ≥ 0), since those decide the result.
The CLI writes the wrap-up with the verdict marked **provisional,
pending 8 checks**. Luis or Cowork checks them the same day, and the
verdict is recorded as final in the state of play, not by the CLI. If
any checked row is revised or mismatched, the reading drops to "can't
tell" as the prompt already says.

Note for the reader: the primary is rank-based, so the extreme rows from
EOSE, JKS and RUN cannot move it. They only move the medians in the
three-group comparison, which is reported-only. The flag matters for
whether the rows are *real*, not for their size.

## 5. Pre-register the tune test now (answers Q5)

If the primary passes with both conditions:
- **Tune test.** Same primary, same measure, same B ≥ 0 restriction, on
  the 51 tune companies using B's existing tune scores. Pass: ticker-block
  range above zero. Same two conditions: sign holds in every
  leave-one-year-out cut; no unscreened split needed (tune is untouched).
- **This spends the tune look** reserved under state of play §3.5. The
  candidate qualifies: it is an overlay on B's non-bearish calls and
  cannot touch the bearish side. Spend it only on a clean train pass,
  not a borderline one. "Borderline" means the pooled range's lower end
  is within 0.02 of zero.
- **What a tune pass buys.** A pre-registered candidate for how surprise
  enters the system: as a structured field the analyst sees at call
  time (it is company data, not portfolio data, so the firewall allows
  it) or as an allocator input. That choice is made after tune, by the
  sector label in §3.

## 6. What would still make a pass or fail misleading (answers Q6)

- **A pass with a beat rate near 75% in both groups** means the signal
  is in the *size* of the beat, not in beating. Say so; a beat/miss flag
  alone would not carry it.
- **A fail on the EPS-scale split's small-EPS side only.** If the primary
  passes on calls where the estimate is at least 1% of price and fails on
  the rest, the fail is about the measure, not the mechanism, and the
  next question is a revenue-surprise source for the growth names Luis
  actually holds.
- **Estimate vendor drift.** AV's estimate is one vendor's consensus.
  Two cents of vendor difference on a $50 stock is the same size as the
  effect being hunted. The eight checks are the only defence; there is
  no $0 fix, and the wrap-up should say the result is conditional on the
  vendor's number matching what the market saw.

## What it means

Pass with both conditions: the first bullish lead, and the tune look is
spent the same day. Pass on the primary but failing (b): report it as
"one year's effect" and do not spend the tune look. Fail: consensus
surprise joins the closed routes, and the analyst's role is downside
protection, with the live forward test as the only remaining route to a
bullish result.
