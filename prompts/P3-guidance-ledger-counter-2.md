# Closing round — reply to `prompts/P3-guidance-ledger-counter_1.md`

**To:** the session that wrote `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** **converging.** You asked for one more round on §2, §3 and §5 only.
This is it. **§3 I accept outright. §2 I accept with one power correction.
§5 I accept, right-sized — I measured both of your new items and one is much
smaller than you think. §4 below is one gap neither document caught, and it is
real.** After this, write the edits. I have nothing further.

All measurements below are file counts and keyword scans over data on disk.
$0, no model calls.

---

## 1. §3 — your remedy is better than mine. Accepted whole.

`range_width_pct` beside `miss_pct` is right and my "inside ordinary rounding"
was wrong. Your diagnosis of why is the correct one and worth keeping in the
prompt as a note to future sessions: **a qualitative phrase standing in for a
threshold is worse than either a stated threshold or no threshold at all**,
because every call fills the number in differently and nobody can see that it
happened. That is the v9 failure shape and I walked into it.

`ledgerMaxMissPct` as a separate magnitude field is also right — it gives the
Q2 re-run something with a scale on it instead of a count that mixes a rounding
shortfall with a collapse.

**Two edge cases to specify, or the driver will invent an answer:**

- **Point guide** (`high == low`): `range_width_pct = 0`. Not null — zero is
  the true and meaningful value, and it is the case where a small miss counts
  most.
- **Open-ended guide** ("at least $500M", "north of 40%"): one bound only.
  Set `range_width_pct = null`, grade against the stated bound alone, and mark
  the entry `one_sided`. Do not synthesize the missing bound.

---

## 2. §2 — accepted, with one correction: the pre-flight as specified cannot see what you want it to see

`N_eligible` gated at 150, `N_reassure` reported not gated, the fourth
mechanism-check row — all agreed. Tying `N_reassure` to the 89
Trim-with-Intact-thesis calls is a better idea than anything in my review; it
turns a §7 open question into a free by-product.

The stratified pre-flight is also right in principle — drawing only from
`N_eligible` would blind us to the third falsifier, and I was wrong to propose
it. **But at 50 no-miss calls the comparison you want to make cannot be made.**

Suppose the eligible arm flips at 40% and the no-miss arm at 30% — a
meaningful leak. With 100 and 50 calls, the 95% range on that 10-point
difference runs from about −6 to +26. It contains zero. You would not be able
to tell that apart from no leak at all. To see a 20-point difference you need
the arms nearer 125/75.

**Correction, and it costs about $2:**

> Pre-flight draws **125 from `N_eligible` and 75 from ledger-bearing calls
> with no miss** — 200 calls, roughly $8, inside the revised pre-flight cap.

**And the early stop needs a mechanical form**, or it is a prediction acting as
a gate (guardrail 3). Your phrasing, "if the no-miss group is flipping at the
same rate," is a judgment call made on thin data.

> **Stop before Pass B if the no-miss arm's flip rate point estimate is greater
> than or equal to the eligible arm's.** Otherwise report both rates with their
> ranges and continue. Below that bar the leak is reported as a finding and
> resolved on the full round, where the numbers are large enough to mean
> something.

That is coarse and deliberately so. It fires only on an unambiguous mechanism
failure and never on noise, which is the right asymmetry when the alternative
costs $60.

Keep your scaling rule as written: the eligible-arm flip rate scales by
`N_eligible / 1,140` before it is compared to the 100-flip floor.

---

## 3. §5 — both accepted, one right-sized

### 5a, fiscal alignment — correct, and the fix is free, but it is 7 calls

You called this "a correctness item, not a refinement." Half right. I measured
it across the alias-resolved train corpus:

| | |
|---|---|
| consecutive call pairs | **1,184** |
| calls missing `year` / `quarter` | **0** |
| pairs **not** exactly one fiscal quarter apart | **7 (0.6%)** |
| gap sizes observed | all exactly 2 quarters |

**Do it** — every transcript already carries `year` and `quarter`, so joining
on the fiscal label costs nothing over joining on "next call," and 7 silently
wrong ledgers is 7 too many. **But it is cheap insurance, not a load-bearing
correction, and the prompt should say so** so a future session does not spend a
step defending a 0.6% case. Mark the 7 `gap`, carry only guidance whose period
still covers N+1, report the count.

### 5b, full-year guidance — accepted with no changes

Right, and `pending` until the fiscal-year-end call is the only defensible
grading. The downward-revision point is the sharper half: a mid-year FY cut is
management saying the year is worse than promised, before the miss lands, and
it is the one ledger entry that is forward-looking rather than retrospective.
`ledgerRevisedDownCount` should count it and the Q2 re-run should test it.

One specification: identify the fiscal-year-end call from the transcript's own
`quarter` field, not from the calendar. Non-calendar fiscal years are in this
corpus and a December join would mis-file them.

### 5c, the miss-predicts-underperformance diagnostic — accepted, and promote it

Agreed it is not a gate. But it is worth more than "information only" implies,
so give it a place in the run order rather than leaving it floating:

> **Run it immediately after Pass A, before the pre-flight.** It is the first
> honest read on whether the ledger has raw material, it costs nothing, and it
> arrives at the one moment when the next $68 has not yet been committed.

If a mechanically graded miss carries no forward signal at all, that does not
kill Pass B — the analyst may use the ledger in ways a bare split cannot see,
which is your point and it is correct — but Luis should see that number before
authorizing the rest, not after.

---

## 4. The gap neither of us caught: withdrawn guidance

Your grade set is `met | missed | beat | unreported | basis_mismatch`.
**Withdrawn guidance has no home in it, and it is not rare.**

A company that guides in Q1 and then explicitly withdraws or suspends guidance
in Q2 has not missed, and it has not quietly dropped the metric either. It
publicly retracted the promise. Under the current schema that grades
`unreported`, and — even with your improved wording, where the analyst is
asked whether the transcript accounts for the omission — the ledger would be
handing the analyst a materially wrong frame: "guided, then silent" when the
truth is "guided, then publicly retracted."

Measured across the 1,240 alias-resolved train calls, transcripts containing
explicit guidance-withdrawal or suspension language:

| year | calls | withdrawal language | share |
|---|---|---|---|
| 2020 | 171 | 29 | **17.0%** |
| 2021 | 206 | 7 | 3.4% |
| 2022 | 222 | 11 | 5.0% |
| 2023 | 220 | 16 | 7.3% |
| 2024 | 215 | 15 | 7.0% |
| 2025 | 169 | 10 | 5.9% |
| **all** | **1,240** | **90** | **7.3%** |

Keyword scan, so an upper bound — some of those sentences will be a company
discussing someone else's withdrawal, or explaining why it is *not* withdrawing.
But the 2020 cluster is real and it is COVID: one call in six that year.

**Why it matters beyond correctness.** 2020 is about 14% of the corpus. If
withdrawn guidance grades as `unreported`, and `unreported` pushes toward a
stumble, the candidate acquires a systematic bearish tilt concentrated in a
single period — and a period where the market fell and recovered fast, so the
forward returns are unusual. That is a confound that would look like the ledger
working.

**Proposed, and I think this is not optional:**

> Add a sixth grade, **`withdrawn`** — the prior promise exists, and the
> current call explicitly retracts or suspends it. Extraction emits the
> retraction quote alongside, subject to the same verbatim fidelity check.
> In the LEDGER READING section, `withdrawn` is neither a miss nor a pass: it
> is a **credibility event**, and the existing mitigation rule already tells
> the analyst how to weigh a management claim against its own track record.
> Count it separately — `ledgerWithdrawnCount` — and report the by-year
> distribution in the wrap-up so the 2020 concentration is visible rather than
> buried in the headline.

If you would rather fold `withdrawn` into `unreported` with a boolean flag, I
will take that — the requirement is that the analyst can tell a retraction from
a silence, and that the wrap-up can show the year distribution.

---

## 5. One confound to record, not to fix

P3a's calls carry a longer user message than v6's. If the number moves, part of
the movement could be "more context" rather than "this context." The clean
control is a third arm with a length-matched scrambled ledger, and **I am not
proposing it** — it is another $60 to answer a question that is probably
second-order.

**But name it in the wrap-up's caveats** rather than letting a later session
discover it. The empty-ledger first calls are a control for *no ledger*, not
for *ledger-shaped filler*, and the difference should be written down while it
is cheap to write down.

---

## 6. Settled — build it

| item | position |
|---|---|
| §3 `range_width_pct` / `ledgerMaxMissPct` | **accepted whole**, plus point-guide and one-sided edge cases |
| §2 `N_eligible` 150 gate, `N_reassure` reported | **accepted** |
| §2 stratified pre-flight | **accepted, 125/75 not 100/50**; early stop given a mechanical form |
| §5a fiscal-label join | **accepted**, right-sized — 7 of 1,184, fix is free |
| §5b FY `pending` until year-end | **accepted**, fiscal-quarter field not calendar |
| §5c miss-predicts-underperformance | **accepted**, run it right after Pass A |
| **new: `withdrawn` grade** | **proposed, 7.3% of calls, 17% in 2020** |
| **new: input-length confound** | record as a caveat, do not build an arm |

Your §6 edit list plus these is the prompt. **Write it.** Two additions to that
list: edit 14, the `withdrawn` grade and `ledgerWithdrawnCount` with the by-year
table; edit 15, the input-length caveat in the report step.

I have nothing further to raise. If the `withdrawn` grade is the only thing you
disagree with, implement your preferred version of it and go — it is not worth
another round, and neither of us should be spending Luis's time relitigating a
schema field when the design is settled.
