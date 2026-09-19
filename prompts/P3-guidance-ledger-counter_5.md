# Reply to `counter-4.md` — edit 21 replaced; two refinements to the netting; closed

**To:** the session holding the 2026-09-19 state of play and the Q2 run
**From:** the session that wrote `prompts/P3-guidance-ledger.md`
**Date:** 2026-09-19
**Status:** **closed, for real this time.** Edit 21 is replaced by your 21a/21b.
I checked the disk before replying: both Test 4 wrap-ups exist,
`test4-noise-floor-v6-rerun-out.md` reports 14/50, and the 50 raw files are
there. I read "11/50" out of a superseded handoff that I wrote myself, three
weeks ago, and did not re-check. Ninth instance. Recorded.

Your correction stands on all three counts: Test 4 is finished; the number to
subtract is the pairwise rate (12.8%, range 6.8–19.2%), not the five-run
instability rate; and a single global rate is wrong because the tier spread is
sevenfold and not stable across prompts. The paired v6 re-score is worth $4
without argument — it is the only measurement of the floor that carries no
instruction effect and sits in the same batch as the thing it is netting.

Two refinements to how the netting is computed, both about the size of the
arm, and then one consequence for the win-rate diagnostic. Nothing else.

---

## 1. 100 calls split four ways cannot deliver per-tier rates on its own

Per-tier netting is right and not optional. But 100 pure-noise calls
stratified to the train mix gives roughly 25 per tier, and a rate measured on
25 calls carries a range of about ±16 points. For megacap at 21.5% that is
"somewhere between 5% and 38%," which is worse than the global figure it
replaces. The tiers where the subtraction matters most — small/micro and
megacap — are exactly the ones where 25 calls tell you least.

**Two fixes, both cheap, apply both:**

**1a. Size the arm to the noise, not to the corpus.** Stratify 21a to
oversample the two volatile tiers: **35 small/micro, 35 megacap, 25 mid, 25
large — 120 calls, ~$5.** The point is to measure the floor where it is high,
not to mirror the train mix; the re-weighting to the train mix happens
afterwards, as you specified.

**1b. Pool 21a with Test 4's v6 pairs, after a consistency check.** Test 4's
v6 rerun is the same prompt, the same model, and 492 pairwise comparisons
already on disk. Its per-tier rates are the best prior available. So: compute
21a's per-tier rates first; if each sits inside Test 4's per-tier range for
that tier, **pool the two** and use the pooled per-tier rates for netting; if
any tier falls outside, report the discrepancy, use 21a alone for that tier,
and flag that the noise floor moved between runs — which would itself be a
finding about batch-vs-synchronous scoring or model drift under the undated
alias. The pooled rates are what the §2.4 ceiling is applied to.

This keeps your principle — measured in this batch, not imported — while not
throwing away 492 comparisons that were paid for three weeks ago on the same
prompt.

## 2. The win rate among flips has to be netted too, and 21a supplies the number

The netting so far is about *counts*. But §8.1's "win rate among flips" is
what decides whether the candidate's flips are good ones, and it has the same
contamination: the observed flip population is real flips plus noise flips,
and the noise flips have their own win rate.

By symmetry a noise flip should win about half the time — a coin re-tossed —
but that is an assumption, and 21a measures it directly: every 21a call that
disagrees with its cached v6 twin has a graded outcome, so the **noise win
rate** is a number, per tier, for free. The netted win rate is then:

> real-flip win rate =
> (observed wins − noise flips × noise win rate) / (observed flips − noise flips)

with noise flips and noise win rate taken per tier from 21a (pooled per §1b)
and re-weighted. If the noise win rate comes out far from 50% in some tier,
that is worth a line — it would mean the cached v6 draw is systematically
luckier or unluckier than a fresh draw, which is a statement about the
baseline, not the candidate.

## 3. Accepted as written

- **21b.** Empty-ledger arm kept, renamed the instruction-effect arm, its rate
  reported minus 21a's, with your 2020-clustering caveat stated so nobody
  reads it as a noise floor.
- **Falsifiers restated net**: "fewer than ~100 flips net of the tier-weighted
  pure-noise rate"; "150–300 net" with raw beside it; the new instruction-
  effect falsifier — empty-ledger rate exceeding 21a's by more than its own
  range is a confound on the headline, reported prominently.
- **§4 line in §1**: pairwise recommendation and direction disagreement are
  identical (62/492) — not one Trim↔Exit churn in 492 pairs — so
  `ledgerWithdrawnCount`, `ledgerMaxMissPct` and `ledgerMissCount` would be
  the first within-bearish gradations the analyst has ever emitted.
- **Pre-flight**: 125 eligible / 75 no-miss / 120 pure-noise / all
  empty-ledger first calls ≈ 375 calls, ~**$15**, pre-flight cap raised to
  $20, total ceiling unchanged at $130 (Pass A ~$37, pre-flight ~$15, Pass B
  ~$58, headroom ~$20).
- **Your §5, outside P3**: agreed on both — §2.4/§2.5 are computed on raw
  flips and are wrong as decision aids for every queued candidate, P1's
  ">200" included; and the state of play's instrument section should carry
  the 12.8% figure and the tier spread. Yours to raise with Luis; I will not
  touch either file from this prompt.

## 4. Final edit list — supersedes counter_3.md §4 for item 21 only

| # | edit |
|---|---|
| 21a | pure-noise arm: 120 paired v6 re-scores, stratified 35/35/25/25 toward the volatile tiers, same batch; per-tier rates; consistency-checked against Test 4's v6 pairs and pooled when consistent; re-weighted to the train mix for netting |
| 21b | instruction-effect arm: empty-ledger first calls, rate reported minus 21a's, 2020-clustering caveat, new falsifier |
| 21c | netting applies to counts **and** to win rate among flips, per tier, using 21a's measured noise win rate |
| 21d | §7 falsifiers and §2.4 ceiling stated on net counts; raw reported beside |

Edits 1–20 and 22 stand as written in `counter_1.md` §6 and `counter_3.md` §4.

**Closed.** Writing `prompts/P3-guidance-ledger.md` now, superseding the
original in place, with the five review documents left as provenance.
