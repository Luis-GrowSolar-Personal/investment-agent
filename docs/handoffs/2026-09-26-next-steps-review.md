# Review of `2026-09-25-next-steps-proposal.md` — agreed, with answers and two additions

**Date:** 2026-09-26 · **Status:** review. Agrees with the proposal's order
(§1) and all four repo findings (§2). Answers its four questions (§4). Adds
two items the proposal did not cover. Nothing here re-opens a decision in
`2026-09-24-state-of-play.md` §5; the sentences marked **→ file** are edits
the step-1 bookkeeping commit should carry into the named file, so the
decisions live where future sessions read them.

---

## 1. Agreed without change

- **The order** (bookkeeping → B's noise floor → P7 → P9 → model gate, with
  the end-to-end check as veto only). Steps 1 and 2 are hard prerequisites
  for step 3; no overlap.
- **§2.1–2.3.** The registry still says `candidate`, the ledger has no P6B
  entry, and `PROMPT_ARCHITECTURE.md` §2.2 is stale (P1 "run first", P6 "run
  next", P7 "from whichever of B or C"). All three are fixed in one commit at
  step 1. → file: `PROMPT_ARCHITECTURE.md` §2.2 table and P7 text;
  `VERSION_REGISTRY.json`; `data/gate_ledger.json`.
- **§3.1.** The end-to-end check can veto a candidate and never pick one.
  → file: add that sentence to state of play §5.4.
- **§3.2.** Model gate last; "holds up on the most recent year alone" is a
  **diagnostic, not a gate** — the most recent year is ~170 calls and cannot
  carry one.

## 2. Answers to §4

**Q1 — ledger schema.** Add a `metrics` object keyed by the ruler actually
used. Keep the old fields where they apply: `primary_metric` = rank
correlation (score vs 182-day tradeable-entry return vs SPY), `delta` = the
paired difference over v6 with its ticker-block range as the noise basis
(gate §6 permits a bootstrap spread; B's re-run noise floor does not exist
yet). `holdout: "locked — not yet looked at"`. **Write the entry at step 1;
amend it with B's measured noise floor after step 2.** The entry records the
two honest qualifiers: the final-value margin over A0′ is thin and rests on
FSLR; gain-per-drawdown was not in the run's pre-registration though it is
the gate's §3.2 metric.

**Q2 — company split vs time split.** Not a conflict; they govern different
things. The **company split (train → tune)** is the promotion gate and
applies to every candidate, P8's survivors included. The **time split** is a
constraint on P8's *generator*: it iterates on train-company calls from
2020–2022 and screens on train-company calls from 2023–2024, so it cannot
learn a regime rule and pass it off as insight. A survivor of that screen is
then an ordinary candidate and gets its one look at tune. The 53-company
holdout is *the* holdout; P8's "holdout 2025" wording is dropped. Nothing
changes for P7 or P9. → file: `PROMPT_ARCHITECTURE.md` §2.6 / P8 block, when
P8 is built.

**Q3 — the lucky-cached-draw check.** Drop it. It is a question about v6's
archived baseline, and v6 stops being the comparator at step 1. Its only
consequence — the archive flattered v6 slightly, so B's result is
conservative — is already recorded. Closed as irrelevant unless v6 returns
as a comparator. → file: state of play §7, move to "closed".

**Q4 — a bullish target for P7.** Yes, pre-registered, with the arithmetic
stated. B's bullish bucket at score ≥ +3 is right **41.3%** on tune against a
**32.8%** base rate, on **242** calls. At that size two groups must differ by
roughly **6 points** before the data can tell them apart. Falsifier: P7's
bullish precision at the same cut must exceed B's by more than the band B's
own noise floor implies on ~240 calls (step 2 supplies the exact figure;
expect ~6 points, so a target near **47%**), **and** P7's rank correlation
must not fall below B's. Rank correlation stays the primary test; bullish
precision is the gap P7 exists to close. Also report the bullish bucket's
median return (B: +0.63 on tune) — a precision gain with no money gain is a
threshold artifact.

## 3. Two additions

**3.1 Step 2 needs "flip" defined before it runs.** B's output is an integer
score, not a label. Report three rates, per stratum, with Wilson ranges:
score disagreement at |Δ| ≥ 1; at |Δ| ≥ 2; and **mapped-direction
disagreement** under the pre-registered thresholds (≤ −2 / ≥ +3). The
direction rate is what P7's and P9's flip counts are netted against; the two
score-level rates say whether B wobbles within a bucket or across one, which
P9 (magnitude) needs to know. Sample: ~400 train calls, stratified as the
noise arms were, ~$10–15. Also record B's noise *win rate* per stratum, for
the win-rate netting (P3 §7 rule, unchanged).

**3.2 P9's pre-registration needs a calibration test named now.** An
expected return in percent is falsified differently from a score: not only
"does it rank" but "is −20% actually about −20%". Pre-register: bucket the
predicted return into deciles; report the realized median per decile; the
candidate is calibrated if the realized medians are monotone and the slope
of realized-on-predicted is within a stated band of 1 (declare the band
before the run; 0.5–1.5 is a reasonable first pass and should be written
down as such). A P9 that ranks but is systematically 3× too optimistic is
usable with a scale factor; one that ranks and is uncalibrated in *sign* is
not. Rank correlation stays primary; calibration is the second gate.

## 4. Nothing else

The proposal's §1 table is the execution order. Steps 1 and 2 can be one
prompt to Code's CLI; P7 is the next candidate prompt after they land.
