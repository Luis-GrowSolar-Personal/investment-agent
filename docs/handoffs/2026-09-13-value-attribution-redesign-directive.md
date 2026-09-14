# Directive — value attribution, post-challenge redesign

**To:** the session holding `prompts/methodology-challenge-value-attribution.md`
**From:** the authoring session, after adjudication
**Read first:** `wrap-ups/methodology-challenge-value-attribution-out.md`
(full adjudication), then `docs/handoffs/2026-09-13-analyst-value-question.md`
(context, now partly superseded — see §3).

---

## 1. Adjudication accepted

Five challenges conceded in full (C1, C2, C3, C4, C8), four in part
(C5, C6, C7, C9), zero full defenses. The reasoning and file citations are in
the wrap-up. **You do not need to re-argue any of it.** Proceed on the basis
that the challenge stands.

Two findings surfaced during adjudication that neither document had caught;
both are in §6 below and both gate how any lift figure may be cited.

---

## 2. The objective has NOT changed — read this before redesigning anything

The challenge dissolved the *premise* of the original prompt. It did not
dissolve the *objective*, and the distinction is the single most important
thing in this directive.

**The objective, unchanged:**

> **Who is contributing most to the portfolio's lift, and who needs the most
> work — the analyst layer or the allocator layer?**

That question is a resource-allocation decision about where Luis spends his
time. It has two halves and both must be answered:

- **Contribution** — what each layer earned, in dollars, on this corpus.
- **Headroom** — what each layer could still earn if improved.

These can point to **different layers**. A layer can be large and near its
ceiling while a smaller one has room. That divergence is the decision-relevant
case and the reason the test is shaped around four numbers rather than two.

**The deliverable remains the Step 6 table** — floor, actual, two ceilings,
two contributions, one interaction term, two headroom lines — with the bias
corrections C8 requires. Do not replace it with a different deliverable.

**What to guard against.** C1 and C2 are strong enough to invite the
conclusion that there is nothing left to test. That would be wrong. C1 removes
a false motivating tension; it says nothing about which layer earns the money
or which has room. If the redesign ends without producing the contribution and
headroom figures, it has failed regardless of how sound its methodology is.

---

## 3. What the challenge actually changed

**The premise.** The original prompt opened with "Test 1 says +$59k, Test 2
says −5.8pp, both cannot be casually true." They can. Test 1's comparator is
zero-information; Test 2's is always-**bullish**
(`analyst_direct_scorer.py:18, 207`). Delete that framing entirely.

**The starting question.** It is no longer "how are both true." It is:

> Does v6, run through the real allocator, beat **always-bullish** run through
> the same allocator — in dollars?

That is C2's arm, and it is now **Arm 0**, below.

**Corrections to `docs/handoffs/2026-09-13-analyst-value-question.md`** — that
document is superseded on these points and should not be quoted on them:

- "v6 underperforms its baseline" must not be read as "worse than not having
  an analyst." The baseline is permanent bullishness, a strong long-only
  strategy on this universe and window.
- "When v6 says trim, it is wrong roughly four times in five" (§1) is
  unanchored. Correct it once the bearish ground-truth base rate is computed
  (change 3 below). With three classes and a bull-skewed tape, "at chance" is
  a live reading.
- §1's description of §3.1 as sector-ETF-relative is wrong about what ran.
  See F2 in §6.

---

## 4. Required sequence

Run in this order. Each stage can terminate the sequence, and terminating
early is a successful outcome, not a shortfall.

### Arm 0 — always-bullish through the real allocator  *(C2; run first)*

$0. Always-bullish = Add on every call, real allocator, settled config
(`swap_funding`, K=30, `new_calls_only`, X=2.5pp, `pooled`, `per_event_date`),
same locked corpus and window as every other arm. It will saturate against the
caps (15 / 35 / 50); saturation is the arm's answer, not a degeneracy.

Compare to the control, $179,944.91.

- **Always-bullish > control** — the indictment is real and dollar-denominated.
  Report it, then continue: the objective still needs contribution and
  headroom, and now has a third, more demanding comparator to place them
  against.
- **Always-bullish ≤ control** — then §3.1's lift figure is grading something
  this system does not monetize. That is a finding about the **promotion gate
  itself**, larger than the original test's scope, and it must be written up
  as such and carried into `PROMOTION_GATE.md` §10. Continue to the remaining
  stages regardless — the objective is unaffected.

Either way, Arm 0 becomes a permanent third reference line in the Step 6 table
alongside floor and actual.

### Stage 1 — uncertainty, before any further arms  *(C4)*

$0. McNemar on the paired per-call outcomes versus always-bullish, plus a
ticker-block bootstrap interval on the lift. If −5.8pp is inside noise, say so
plainly and prominently — it changes how every later number is read, though it
does not cancel the objective.

Also compute the **bearish ground-truth base rate** here (C3) and correct the
09-13 handoff's language in the same pass.

### Stage 2 — contribution

- **Timing** (C5): two permutation schemes, not one. Within-ticker as primary
  (Test 5 established that universe composition dominates, so schemes that
  perturb the universe measure the wrong thing); cross-sectional
  within-event-date as the second. Report both; they bracket the question.
  Report per-ticker event counts and distinct achievable arrangements. Delete
  "preserve chronology." Withdraw the 50th-percentile interpretation.
- **Structure** (C4, C6): the four ablation arms B1–B4, each read against the
  permutation null rather than as a bare point delta.
- **Per-call attribution** (C6): leave-one-call-out, not a bookkeeping split.
  Drop the reconciliation requirement. If 359 simulator runs is infeasible at
  this corpus size, run the bearish subset only and say so. Report the dollar
  axis **benchmark-relative as well as absolute**.

### Stage 3 — headroom, with bias declared

- **Analyst ceiling** (C7): the oracle arm, with the cap-binding frequency
  reported, the post-`2025-11-07` fallback specified explicitly, "flawless"
  qualified to 182d/±5%/SPY, the sanity check's denominator stated, and the
  non-direction field synthesis pre-registered. Relabel the Step 6 line
  **"Analyst headroom under the current allocator."**
  Pre-register **oracle ≤ actual as a finding**, not a defect: it would mean
  the allocator's direction→action mapping is misaligned with the horizon
  §3.1 grades on, and that would be the headline of the run.
- **Allocator ceiling** (C8): relabel as an **in-sample maximum over the
  searched space**. If no trustworthy sweep covers this corpus and window,
  report unavailable rather than substituting a figure from another loader
  path.

### Stage 4 — the deliverable

The Step 6 table, with **the sign of the bias printed on each ceiling line
inside the table**, not in a limitations section. Interaction term reported as
its own line and not forced to sum.

Close with the plain-language reading the objective asks for: which layer
earned more, which has more room, and whether those point to the same layer.
Where they diverge, say so explicitly.

---

## 5. The nineteen changes

All nineteen from `wrap-ups/methodology-challenge-value-attribution-out.md` §5
are **accepted**. Fourteen are free specification edits; the four pieces of new
work (items 1, 4, 6, 10) are all $0 in Anthropic API spend.

**You are authorized to write `prompts/value-attribution-and-headroom-v2.md`**
incorporating all of them, structured on §4's sequence. Do not run it without
Luis's go-ahead.

Carry forward unchanged from v1: the $0-API hard constraint, the Step 0
pre-registration freeze (`PREREGISTRATION.json`, abort on mismatch), the
requirement that every arm run on one identical locked corpus/window/control,
the firewall discipline around the oracle arm's scratch data, the macOS/zsh
constraints, and the instruction not to repair known defects in passing
(AMD classifying speculative; the app not reading `type_classifications.json`).

---

## 6. Two findings that gate any lift citation

Neither document caught these. Both are divergences between
`PROMOTION_GATE.md` §3.1 and `analysis/analyst_direct_scorer.py`.

**F1 — baseline.** §3.1 specifies *"lift over an **always-hold** baseline"* and
justifies it: *"an always-'bullish' coin scores ~55–60% in a bull sample, so raw
accuracy is misleading."* The scorer implements **always-bullish**. The spec
names the strategy it meant to guard against; the implementation adopted it as
the comparator.

**F2 — benchmark.** §3.1 specifies *"the stock's sector ETF where one applies
(e.g. TAN for solar), else SPY"*, with a worked ENPH-vs-TAN example. The scorer
uses **SPY for all tickers** — *"sector ETFs not yet in price cache; revisit
once TAN/SOXX/etc. are added."* On a universe heavy in solar, storage and semis
over 2021–2025 these are materially different instruments, and sector-driven
moves §3.1 intended to neutralize are being scored as analyst hits and misses.

**Consequence:** until F1 is resolved, no lift figure produced by this scorer —
including −5.8pp — may be cited as §3.1's metric. Cite it as
"always-bullish-relative lift, SPY-benchmarked" and nothing more.

Record both in `PROMOTION_GATE.md` §10. Resolving them is a separate decision
for Luis, not a task for the redesign; flag it and move on.

---

## 7. Standing note

The claude.ai Project copy of `PROMOTION_GATE.md` is the 2026-09-02 version.
The repo copy carries §8.1 (forced-migration protocol) and §11 (comparison
protocol). The project copy is stale and should be synced before it is cited.
