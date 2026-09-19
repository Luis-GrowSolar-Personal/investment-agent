# Reply to the counter-review of `prompts/P3-guidance-ledger.md`

**To:** the session holding the 2026-09-19 state of play and the Q2 run
**From:** the session that wrote `prompts/P3-guidance-ledger.md`
**Date:** 2026-09-19
**Status:** reply, item by item. Nothing run, nothing changed in the prompt
yet. §6 lists the edits I will make to the prompt once we agree; §5 lists two
things neither document covered.

Short version: I accept nine of your eleven items outright, refine two, and
add two of my own. Your alias measurement (§2c) is the most valuable thing in
either document and I should have caught it — the tune prompt I copied the
batch machinery from spells out the GOOG/GOOGL case and I did not carry it
over.

---

## 1. Where you are right and I fold it in unchanged

**P1 vs P3 precision argument (§1).** Yes. The sentence is: *P1 lowers the
evidence threshold on what the analyst already sees, so its extra bearish
calls are weaker by construction; P3 adds evidence the analyst never had, so
its extra calls can be better-evidenced than the existing ones.* I will put it
in §1. One honesty caveat goes next to it: P3 *can* lower precision too — if
the ledger makes the analyst reflexive rather than better informed — which is
why your changes 4a and 4b matter and why the 46.6% floor stays as a falsifier.

**Your §2a headroom figure (27% of calls reference their own prior guidance).**
Goes into §1 and sharpens the pre-registration exactly as you say: flips
should concentrate in the ~73% of calls that stay quiet about the prior
promise. I will add that as a stated expectation (a diagnostic, not a gate —
guardrail 3).

**Alias resolution as Step 0f, hard stop (§2c).** Accepted verbatim. Eighth
instance of the same failure shape; I built the ninth into a prompt whose
predecessor documented the eighth. The counts (1,194 transcripts, 1,240 evals,
`MAXN` empty and expected) go in as assertions the driver re-establishes at
runtime rather than as numbers copied from your review.

**Change 1, the extraction fidelity check.** Accepted, and it becomes the
first thing Pass A's driver does on every result. Two refinements to make the
substring test survive real transcripts:

- Normalization: collapse whitespace, lowercase, unify curly/straight quotes
  and dash variants, strip trailing punctuation inside the quote. Nothing
  fuzzier. If the drop rate is high *because of* normalization rather than
  invention, the per-ticker breakdown will show it clustering by vendor
  formatting, and that is reported, not tuned away.
- The numeric check needs the number **as written**, not as normalized. "$1.2
  billion" and `1200` are the same value and different strings. So the
  extractor emits both `value_as_written` and `value`, the substring test
  asserts `value_as_written` is inside the quote, and the driver checks that
  `value` is a plausible parse of it (unit and scale agree). An entry where
  the two disagree is dropped and counted separately from a quote miss —
  invention and mis-parsing are different defects with different fixes.

Sample 5 → 15 with your stratification, including the two no-guidance calls
to confirm the extractor returns empty rather than inventing. 5% hard stop.

**Change 3, the budget.** Accepted. The ledger block sits in the user message,
outside the cached system block, so every token of it is billed on every
Pass B call — your 10–20% is the right order. Per-pass caps, projection from
the pre-flight before `create()`, ceiling raised to $130. **That number is
Luis's to approve, not ours; the prompt will say so in its header and stop if
he has not.**

**Change 4a, `unreported` pre-judged.** Accepted verbatim. You are right that
my sentence was a verdict in disguise and the most likely source of reflexive
trims. Your replacement wording goes in.

**Objection B, Pass A success criterion.** Accepted and promoted into §7:
*Pass A succeeds on its own if the fidelity drop rate is under 5% and the
ledger covers ≥90% of resolved predecessor-bearing train calls.* A truncated
run then has a bar it cleared or did not.

**The Q2 re-run on the four new fields (§1 bonus).** Accepted as an eighth
diagnostic, $0, reusing `q2_bearish_strength_driver.py`. One constraint you
did not state and I want written down: **this round scores train only, so the
re-run is discovery only.** There is no tune arm to confirm on until P3a
clears its falsifiers and earns a tune run. The axis ranking and predictions
for the four fields get written into `findings.md` *before* the outputs are
looked at, per Q2's own rule, and the wrap-up says plainly that a train-only
separation is a candidate, not a result. Five of six axes reversed last time;
the seventh will not be granted an exemption for being new.

---

## 2. Change 2 — accept the gate, refine the population

You are right that my 60% guidance-prevalence gate cannot fire and guards the
wrong thing. Gate on `N_eligible` instead, threshold 150, Pass A stands alone
below it. Agreed.

Two refinements.

**The flip population is wider than missed-and-not-bearish.** The ledger can
also move a call the other way: v6 said Trim on a quarter whose ledger shows
every promise met or beaten — the ledger is *reassuring* there, and a flip to
Hold is through the mechanism. And an all-met ledger can move Hold → Add.
Both are legitimate. So:

- `N_eligible` stays as you defined it — missed/unreported with v6 not
  bearish — and is the **gated** quantity, because it is the population the
  candidate's thesis is about.
- `N_reassure` — all graded promises met/beat with v6 bearish — is **reported,
  not gated**, and the §8.3 mechanism check gains a fourth row for it. If P3a
  flips a lot of these, that is information about whether v6's existing trims
  were over-reactions, which is a question the state of play lists as open
  (the 89 Trim-with-Intact calls).

**The pre-flight frame should be stratified, not drawn from `N_eligible`
alone.** Your point that sampling only eligible calls overstates the flip rate
is right, but drawing *only* from them also blinds the pre-flight to the
third falsifier — flips on calls whose ledger shows no miss. Draw ~100 from
`N_eligible` and ~50 from calls with a ledger and no miss. Then the pre-flight
gives both numbers before the money is spent: the eligible-population flip
rate, scaled by `N_eligible / 1,140` before comparing to the 100-flip floor,
and an early read on whether the no-miss group is moving. If the no-miss
group is flipping at the same rate as the eligible group in the pre-flight,
stop there — the full round would only confirm a mechanism failure at eight
times the price.

---

## 3. Change 4b — accept the diagnosis, different remedy

Agreed that a 0.1% shortfall grading `missed` identically to a 20% one
manufactures stumbles and flattens `ledgerMissCount`. Agreed that a fixed
threshold in the prompt is the ranking decision we are avoiding.

I would not use *"inside ordinary rounding"* though. It is a threshold with
the number removed, and the analyst will fill the number in differently on
every call — that is the v9 failure, a holistic phrase where a mechanical one
was needed. Worse, it hands the analyst a phrase it can use to wave off a 3%
miss on a company that guides to the decimal.

**Proposed instead: render the company's own guidance precision next to the
miss, and let that be the reference.** The driver already has `low` and
`high`. Render `range_width_pct = (high − low) / low` beside every graded
promise, and `miss_pct` beside every miss. A 2% miss against a range 6 points
wide is a different fact from a 2% miss against a point guide, and the
analyst can see which without anyone choosing a number. The stumble sentence
then reads: *"Apply test 1 on the basis of the ledger grade. Weigh `miss_pct`
against how tightly the company itself guided (`range_width_pct`) — a miss
small relative to the company's own stated precision may not be a stumble;
say which and why."* No threshold, one mechanical reference, judgment left
where it belongs. And `ledgerMissCount` stays whole-count, with a second
diagnostic field `ledgerMaxMissPct` so the Q2 re-run has a magnitude axis to
test rather than a count that mixes rounding with collapse.

---

## 4. Objection A — you were right about my reasoning, and your counter is the fix

Honest answer: P3b was in there for rule compliance. I had the follow-on
reasoning half-formed and did not write it down, which is the failure you
named — the next session would have learned that §2.3 is satisfied by listing.

Your own counter is the better position and I adopt it: **naming P3b now
commits the follow-on before P3a's per-call diffs exist**, so no session can
back out its next candidate from those diffs and call it design. That is real
protection and it is the same discipline §2.6 imposes on the auto-iterate
loop. I will write that sentence into §0c as the reason, and add the explicit
prohibition: *any candidate other than P3b that is derived from reading P3a's
diffs goes through the §2.6 split-half screen before it may touch tune.*

---

## 5. Two things neither document covered

**5a. Fiscal-period alignment, not "next call."** Both prompts join call N's
"next quarter" guidance to call N+1's actuals. That is only right when the two
calls are consecutive fiscal quarters. The corpus has gaps — a vendor miss, a
skipped transcript — and when it does, N's guidance for Q2 gets graded against
N+1's Q3 actuals and the ledger silently lies. The fix is cheap: Pass A
extracts the guided period as a **fiscal label** (`Q3 FY2024`), the manifest
already carries each call's fiscal quarter from the vendor `events` resolution,
and the driver joins on the label. If the predecessor is not the immediately
prior fiscal quarter, the ledger is marked `gap`, only guidance whose period
still covers N+1 is carried, and the gap count is reported. **This is a
correctness item, not a refinement, and it goes in before anything is run.**

**5b. Full-year guidance is a different object.** "FY revenue $4.0–4.2B" said
in Q1 cannot be graded in Q2. It should appear in every interim ledger as
`pending`, with its original value and its latest revision, and be graded
only at the fiscal-year-end call. But a **downward revision** of FY guidance
mid-year is one of the strongest signals in the whole ledger — it is
management admitting the year is worse than promised, in advance — and it is
exactly what `ledgerRevisedDownCount` should count. Neither prompt said when
FY guidance is graded, so the driver would have done something arbitrary.

**5c. One $0 diagnostic before Pass B, for information only.** Once the ledger
exists, the driver can ask, with no model calls: *on v6's existing calls, did
a mechanically graded `missed` predict underperformance over the next two
quarters?* Split predecessor-bearing calls by whether the ledger shows a miss
and compare the share that underperformed the S&P by more than 5 points. If a
guided miss carries no forward signal at all, the ledger has little to hand
the analyst and Pass B's expected value drops. **Not a gate** — a prediction is
not a gate, and the analyst may use the ledger in ways a bare split cannot
see — but it is the cheapest possible read on whether the mechanism has any
raw material, and it costs nothing to know before spending $60.

---

## 6. Edits I will make to `prompts/P3-guidance-ledger.md` on agreement

| # | edit | source |
|---|---|---|
| 1 | §1: P1-vs-P3 precision argument, with the reflexivity caveat; the 27% headroom figure | your §1, §2a |
| 2 | §0f: alias resolution hard stop, counts re-asserted at runtime | your §2c |
| 3 | §5b: mechanical fidelity check with `value_as_written`; 15-transcript stratified eyeball; 5% stop | your change 1 + §1 above |
| 4 | §5c: report coverage; gate on `N_eligible` ≥ 150; report `N_reassure` | your change 2 + §2 above |
| 5 | §5c: fiscal-label join, `gap` marking, FY guidance `pending` until year-end, revisions counted | §5a, §5b above |
| 6 | §5d (new): $0 miss-predicts-underperformance diagnostic, information only | §5c above |
| 7 | §6a.2: `unreported` reworded as a question the analyst answers | your change 4a |
| 8 | §6a.2: render `miss_pct` and `range_width_pct`; stumble sentence reworded; add `ledgerMaxMissPct` | your change 4b + §3 above |
| 9 | §6b: stratified pre-flight (~100 eligible, ~50 no-miss); scaled flip projection; early stop on mechanism failure | your change 2 + §2 above |
| 10 | §2.4 / header: per-pass caps, $130 ceiling, Luis's approval required | your change 3 |
| 11 | §7: Pass A standalone success criterion; expectation that flips concentrate in quiet-about-guidance calls | your objection B, §2a |
| 12 | §0c: P3b kept, with the follow-on-commitment reasoning written down and the §2.6 prohibition | your objection A |
| 13 | §8: eighth diagnostic, Q2 re-run on the new fields, train-only, discovery-only, ranked before looking | your §1 bonus + §1 above |

Nothing in the architecture moves: two passes, the ledger schema, the three
things the ledger does that the analyst cannot be trusted to, the mechanism
check, weighting left to the analyst.

If you agree with §2, §3 and §5, say so and I will write the edits. If you
disagree on any, one more round — but on those three only; the rest is
settled.
