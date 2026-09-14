# Methodology challenge — `value-attribution-and-headroom`

**This is not a run prompt.** No code executes. No API spend, no DB reads, no
DB writes, no branch changes, no file edits other than the wrap-up named below.
`run_id` **`methodology-challenge-value-attribution`**. Branch
`sweep/db-corpus-baseline` (for reference only; nothing is committed by this
prompt except the wrap-up).

**Audience:** the session that authored `prompts/value-attribution-and-headroom.md`
and `docs/handoffs/2026-09-13-analyst-value-question.md`. You have context this
challenge does not. The challenges below were raised by a reviewing session that
read the prompt, `analysis/analyst_direct_scorer.py`, the 09-13 handoff and the
Step 0 wrap-up, and nothing else.

---

## Scope boundary — methodology only, do not adjudicate the findings

**In scope:** whether the *design* of `value-attribution-and-headroom.md` is
sound — its comparators, its nulls, its attribution convention, its ceilings,
and its deliverable's arithmetic.

**Explicitly out of scope, do not argue here:**

- Whether the 153/362 out-of-window rows really are v6.
- Whether `wrap-ups/value-attribution-and-headroom-out.md` was right to stop.
- Whether the window-start convention (`22d2c71`, a documentation commit) is a
  sound dating convention.

Those are a separate conversation happening after this one. A challenge below
that is right or wrong is right or wrong **independent of** how the provenance
question resolves — every one of them would still stand if the corpus were
cleanly v6. If you find yourself defending a design choice by appealing to the
provenance question, that is a sign the argument belongs in the other thread.

One exception: **C9** concerns where Step 0b placed its gate. That is a design
question about the prompt, not a question about what the gate found. Keep the
answer to the design.

---

## Ground rules

1. **Defend or concede, item by item.** For each of C1–C9, answer with exactly
   one of **DEFEND**, **CONCEDE**, or **PARTIAL**, then the reasoning. A
   PARTIAL must say precisely which part is conceded.
2. **The repo outranks both of us.** Where a challenge rests on a reading of
   `analyst_direct_scorer.py`, `ALLOCATOR_OPERATING_MODEL.md`,
   `PROMOTION_GATE.md` or `DESIGN_PRINCIPLES.md`, quote the code or section that
   settles it. A challenge refuted by a file citation is refuted; say so
   plainly.
3. **Do not rewrite the prompt in this pass.** The output is an adjudication,
   not `value-attribution-and-headroom-v2.md`. Design changes are proposed as a
   list at the end, for Luis to decide on.
4. **A challenge you agree with is not a failure of the original design.** Some
   of these are cheap-to-fix specification gaps. Treat a concession as
   information, not as a loss.
5. **A challenge that contradicts an expectation stated in this document is a
   finding, not a reason to stop.** If the reviewing session has misread the
   scorer, the allocator or the corpus, say which line it misread.
6. Do not re-propose mechanisms already refuted in `wrap-ups/` (transcript
   anonymization, the variable Type B cap, the cash-reserve knob, the mid-day
   `start_of_day_value` backfill).

---

## C1 — the prompt's motivating tension may be a comparator conflation

**Claim.** The prompt opens: "Test 1 says the analyst is worth ~$59,000…
Both cannot be casually true." They can. The two tests use different
comparators:

- Test 1's comparator is a **zero-information** arm.
- Test 2's comparator is **always-bullish** — `analyst_direct_scorer.py` line 18,
  `Always-bullish baseline: predicts "bullish" on every call`, and the Step 0
  wrap-up confirms `always_bullish_hit = (ground_truth == "bullish")`.

Always-bullish on a 16-name, momentum-weighted, analyst-selected universe over
2021–2025 is a strong long-only strategy, not an absence of information. The
year-to-year swing in the baseline hit rate (32.1% → 58.8%) is the SPY-relative
base rate moving, which is what a fixed bullish rule *is* on this universe.

"+$59k versus a coin flip" and "−5.8pp versus permanent bullishness" are
jointly true with no tension to resolve. If that is right, a meaningful share of
the six-step scaffolding exists to reconcile a difference in definitions.

**Why it matters.** It changes what the run is for. The remaining live question
is not "how are both true" but "does v6 beat always-bullish **in dollars**,"
which is C2.

**What would refute this.** A showing that Test 1's zero-information arm is
materially equivalent to always-bullish in its allocator behavior — i.e. that
both deploy capital at similar rates into similar names — in which case the two
comparators really are commensurable and the tension is real.

---

## C2 — the cheapest decisive arm is missing

**Claim.** The prompt never runs **always-bullish calls through the real
allocator**. That single arm is $0, uses machinery every other arm already
needs, and is the only thing that puts Test 1 and Test 2 in the same units.

- If always-bullish-through-allocator exceeds **$179,944.91**, the indictment is
  real, dollar-denominated, and Steps 2–6 are not needed to act on it.
- If it does not, then −5.8pp is a §3.1 artifact and **the promotion gate's
  primary analyst metric is grading something the system does not monetize** —
  a larger finding than anything Steps 1–6 can produce, and one the prompt as
  written cannot reach.

**Why it matters.** The prompt's stated purpose is to convert a
metric-space disagreement into a development decision. This arm does that
directly; the oracle and the ablations approach it obliquely.

**What would refute this.** A structural reason always-bullish cannot be fed
through the allocator coherently — e.g. it degenerates because Add-on-every-call
under `pooled` / `swap_funding` has no well-defined funding behavior, or it
collides with caps in a way that makes the arm meaningless rather than
informative. If that is the case, say so with the mechanics; it is a real
objection and it belongs in the record either way.

---

## C3 — the bearish-accuracy claim has no denominator

**Claim.** "When v6 says trim, it is wrong roughly four times in five" (09-13
handoff §1) reads 8.3%–24.0% against an implicit 50%. The correct anchor is the
**unconditional frequency of bearish ground truth** — the share of scoreable
events where the stock underperformed SPY by more than the ±5% dead band. On
this universe and window that is plausibly near 20%. If it is, bearish calls are
**at chance**, not catastrophically wrong.

This is a three-class problem with a bull-skewed prior; low precision on the
rare class is partly mechanical. The number needed to settle it is already
computable from Test 2's own scored rows.

**Why it matters.** "At chance on the short side" and "systematically wrong on
the short side" imply different remediation. The stronger phrasing is currently
in a handoff and will propagate.

**What would refute this.** The computed bearish base rate coming in well above
24%, which would make the original framing correct as stated.

---

## C4 — no uncertainty quantification anywhere except Step 2

**Claim.** −5.8pp is treated as a settled magnitude throughout the prompt and
the handoff. The underlying observations are strongly dependent: 182-day forward
windows overlap heavily within each ticker, all 16 tickers share one SPY factor,
and the universe is concentrated. The effective sample size is far below 359.

Nothing in Step 0 or Step 1 attaches an interval. A paired **McNemar** test
against always-bullish plus a **ticker-block bootstrap** would establish whether
−5.8pp is distinguishable from zero at all. Both are $0 and neither needs the
allocator.

The same gap appears in **Step 3**: four ablation arms reported as single-path
point deltas with no null. A ±$5k delta on a $180k terminal value is unreadable
without a distribution. Cheapest fix: re-run each ablation across the Step 2
permutation seeds so each delta is read against its own null.

**Why it matters.** If −5.8pp is inside noise, the entire test's premise is a
sampling artifact and the reconciliation question dissolves for a second,
independent reason.

**What would refute this.** An argument that the dependence structure is weak
enough that n≈359 is approximately honest, or a pre-existing interval in
`wrap-ups/` that this challenge missed.

---

## C5 — Step 2's within-ticker shuffle tests a compound null

**Claim.** The prompt pre-registers the null as "the analyst's timing
contributes nothing measurable." The shuffle does not isolate that. It destroys
the call→quarter mapping **within ticker across 2021–2025**, which moves calls
across market regimes, price levels and portfolio states. The allocator is
path-dependent and compounding under `pooled` funding — **when** capital deploys
moves terminal value independently of whether any call was correct.

So the realized null is "no timing skill **and** a calendar-invariant
allocator." A real result at the 30th percentile is consistent with "no timing
skill" and equally with "the real arrangement happened to deploy earlier."
The pre-registered interpretation ("at or below the 50th percentile means the
analyst's timing contributes nothing measurable") does not survive that
ambiguity.

**Proposed fix, for the list at the end:** add a second permutation scheme that
holds the calendar fixed — permute call labels **across tickers within the same
event-date cohort**. That destroys cross-sectional selection while preserving
the deployment schedule. The two schemes bracket the question; either alone is
confounded.

**Two smaller points in the same step:**

- "Preserve chronology within each shuffle" is self-contradictory as written.
  The described procedure is a full within-ticker label permutation over that
  ticker's own event dates, which preserves nothing about order. If something
  stronger was intended (e.g. block-preserving, or within-year), say which; if
  not, the phrase should be deleted so a CLI session does not invent a
  constraint.
- Per-ticker event counts are not reported. A ticker with 4 events has 24
  distinct arrangements; 200 draws are then mostly duplicates and the percentile
  is quantized. The prompt should require the per-ticker counts and the number
  of distinct achievable arrangements alongside the distribution.

**What would refute this.** A demonstration that terminal value is close to
invariant to deployment timing under this configuration — e.g. an existing sweep
showing negligible sensitivity to entry schedule — which would collapse the
compound null back to the simple one.

---

## C6 — Step 1's reconciliation requirement contradicts Step 6's non-additivity

**Claim.** Step 1 requires that attributed P&L reconcile to the control arm's
total within a stated tolerance, citing `tier_return_attribution.py`'s −$44.95
on ~$80k as the standard. That is a demand that an **additive decomposition
exist**. Step 6 then states, correctly, that an exact decomposition does not
exist without a Shapley-style construction this run does not attempt.

Both cannot hold. Any convention that reconciles to the cent is **bookkeeping**,
and the 2×2's dollar cells will be read causally no matter what caption sits
under them.

**Three specific things the convention must survive, none currently addressed:**

1. **Calls that produced no trade** — Hold, cap-blocked, or no cash available
   under `pooled`. Attributing the position's drift to them and attributing zero
   are both arbitrary, and they bias the 2×2 in opposite, known directions.
2. **`swap_funding` opportunity cost.** Buying X sells Y. A call's dollar
   consequence includes the cost imposed on the position that funded it; a
   per-position split either drops that term or double-counts it.
3. **Horizon mismatch, stated but not resolved.** §3.1 grades 182-day
   SPY-relative; the dollar axis is absolute over the allocator's holding
   period. In this tape nearly every cell lands in "made money" and the 2×2
   degenerates. The dollar axis should be reported **benchmark-relative as well
   as absolute**.

**Proposed alternative, for the list at the end:** **leave-one-call-out.** Set
each call to neutral, re-run the allocator, take the delta. That is a marginal
contribution rather than a bookkeeping share, it is still $0, and it will *not*
sum — which is the honest signal rather than a residual to be tolerance-managed.
If 359 re-runs is too slow, run it on the bearish subset alone, which is where
the open question lives.

**What would refute this.** A convention that is genuinely causal *and* additive
on this system, stated explicitly — or a showing that the simulator is too slow
for leave-one-out at this corpus size, which makes the bookkeeping split the
only affordable instrument and turns this into a labeling requirement rather
than a design change.

---

## C7 — the oracle arm does not bound what Step 4 says it bounds

Step 4 claims it "bounds the most money a flawless analyst could have made
inside this system." Four separate problems, in descending order of consequence.

**C7a — it is a joint ceiling, not an analyst ceiling.** The oracle runs through
the **current** allocator: caps 15/35/50, starter sizing, Rule 3, profit-take.
Those throttle how much perfect information can be converted into dollars. What
Step 4 measures is (perfect analyst × current allocator config). Step 6's
"Analyst headroom (analyst ceiling − actual)" line is therefore mislabeled — it
is analyst headroom **under the current allocator**.

*Minimum fix:* Step 4 must report **how often the oracle arm is cap-binding**
(how frequently the desired target exceeded the cap). If it binds often, the
"analyst ceiling" is substantially an allocator artifact and the Step 6
apportionment tilts accordingly.

**C7b — it understates, because direction is not all the allocator consumes.**
The allocator reads score magnitude, conviction, `recommendedSize`,
`thesisDelta`. The oracle has to synthesize those, and that arbitrary choice
drives the number. A genuinely flawless analyst would optimize them too. As
specified, Step 4 is a **lower** bound on the analyst ceiling while being
presented as an upper one. Whatever is chosen for the non-direction fields must
be pre-registered in 0d and named in the wrap-up as a bound-loosening
assumption.

**C7c — the unlabelable tail is unspecified and material.** The oracle label
needs 182 days of forward price. `price_cache.json` is frozen at 2026-05-08,
giving `cutoff = 2025-11-07` (the Step 0 wrap-up reproduces this path). Every
call after that cutoff is unscoreable — the oracle has **no information** on the
most recent stretch of the window while the real arm trades through it. The
fallback for those events is not specified anywhere in Step 4, and it drives the
ceiling. If the fallback is "use the real call," the ceiling silently inherits
real-arm behavior on the tail and the contrast deflates.

**C7d — horizon lock, and the sanity check's denominator.** The ceiling is
perfect only at 182 days, ±5%, versus SPY. An analyst who calls 30-day or
multi-year moves is outside the bound entirely; the wrap-up should say so rather
than let "flawless" stand unqualified. Separately, "should be at or very near
100% by construction" holds only **among scoreable events** — state the
denominator, or the sanity check will fire spuriously on the tail from C7c.

**And one thing Step 4 has no slot for:** if the oracle comes in **at or below**
the actual, that is not a defect to debug. It means the allocator's
direction→action mapping is misaligned with the horizon §3.1 grades on — which
would be the headline of the entire run. The prompt should pre-register that
outcome as a finding, per guardrail 3 (a prediction is not a gate).

**What would refute C7a–C7d.** For C7a: evidence the caps rarely bind even under
perfect calls. For C7b: an argument that the allocator's response is effectively
direction-only at X=2.5pp, given the sizing-channel test already found
`recommended_size_pct` worth $0 — this one may well be defensible, and if it is,
say so with the citation. For C7c: a fallback that was intended and simply not
written down. For C7d: nothing; it is a labeling requirement.

---

## C8 — the two ceilings are biased in opposite directions, and both favor the same conclusion

**Claim.** This is the structural problem with the Step 6 deliverable.

- **Allocator ceiling (Step 5)** = the best value achieved by any configuration
  **already searched on this same corpus**. That is an in-sample maximum over a
  searched space. **Upward biased.**
- **Analyst ceiling (Step 4)** = the oracle as specified, which is **downward
  biased** for every reason in C7.

Step 6 subtracts the actual from each and calls the differences "headroom." The
comparison is therefore a **deflated** analyst headroom against an **inflated**
allocator headroom. The error points toward "work on the allocator" — which is
precisely the working hypothesis already stated in 09-13 §2 as "constructed in
conversation, not measured."

The prompt is admirably careful about this hypothesis in prose and then builds
an instrument whose bias confirms it.

**Minimum fix:** the Step 6 table carries the **sign of the bias on each ceiling
line, in the table itself**, not in the limitations section at the bottom. Step 5
must additionally label its figure as an in-sample maximum over the searched
space rather than a ceiling.

**What would refute this.** A showing that the searched configuration space was
selected independently of this corpus (so the max is not in-sample), or that
C7's understatement is small enough that the two biases do not dominate the
comparison.

---

## C9 — Step 0b gated on the wrong artifact (design question only)

**Claim, strictly about design.** `analysis/analyst_direct_scorer.py` is built to
run against a **version-stamped eval cache directory** —
`--eval-dir data/evals/v6_sonnet-4-20250514`, per its usage block. Provenance is
supposed to come from the directory name. Test 2 instead applied §3.1's logic to
**DB `Analysis` rows**, which carry no version stamp, and Step 0b inherited that
substitution and went looking for provenance in `createdAt`.

The design point: the gate was placed on the artifact that **cannot** carry the
evidence, when the metric's own design has an artifact that **can**. Step 0b
should have asked first whether a stamped eval cache covering these calls exists
or is reconstructible, and only fallen back to timestamp inference if not.

(The reviewing session checked and `analysis/data/evals/` is absent from the
working tree, so the stamped path may not be recoverable in practice. That does
not change whether the gate was designed to look in the right place first.)

**Out of scope here, do not argue it:** whether the 42% out-of-window finding is
correct, and what it implies. That is the next conversation.

**What would refute this.** A reason the eval-cache path was known unavailable
when the prompt was written, making the DB the only possible corpus and the
timestamp fallback the only possible check — in which case the prompt should
have said so, and this becomes a documentation gap rather than a design error.

---

## Output

Write `wrap-ups/methodology-challenge-value-attribution-out.md`:

1. **Adjudication table** — one row per challenge: `C1 … C9`, verdict
   (DEFEND / CONCEDE / PARTIAL), and a one-line reason. This table is the
   deliverable; everything else supports it.
2. **Per-challenge reasoning**, in order, with file and line citations wherever
   the repo settles the point. Where a challenge is refuted by a citation, quote
   it.
3. **Anything the challenge got factually wrong** about the scorer, the
   allocator, the corpus or the prompt's own text — listed separately and
   plainly, not folded into the defenses.
4. **Design changes implied**, as a numbered list, each tagged with the
   challenge it comes from and an estimate of whether it is a specification edit
   (free) or new work.
5. **The one sentence**, filled in:

   > Of the nine challenges, ____ are conceded in full and ____ in part; the
   > design change with the largest effect on what this test would conclude is
   > ____________, and without it the test would have concluded ____________.

**Do not** write a v2 of `value-attribution-and-headroom.md` in this pass. **Do
not** run anything. **Do not** touch the provenance question.
