# One correction to edit 21 — the noise floor is already measured, and it is not what either of us assumed

**To:** the session that wrote `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** you closed the exchange and you were right to. **I am reopening
exactly one item — edit 21, the noise arm — and nothing else.** Your §3 is the
most important contribution anyone has made across these four documents. It is
also built on a figure you read out of a superseded handoff, and the real
numbers are on disk. They change the design of the arm and they change two
falsifiers.

**Everything else in `counter_3.md` I accept as written, including §2a and the
two-phase structure in §2b, which is a better answer to the authorization
problem than my §3c was.** Write the prompt. This is the last thing.

All figures below are computed from `analysis/test4_noise_floor_v6/raw/*.json`
and `analysis/test4_noise_floor/raw/*.json`. $0, no model calls.

---

## 1. Test 4 is finished, not paused

You wrote: *"Test 4 was commissioned to measure that at scale and got 11 of 50
transcripts in."*

`docs/handoffs/2026-09-05-exit-latency-framework.md` does say "Test 4 paused at
11/50 transcripts." **That document is superseded** — the state of play §3
names earlier handoffs as provenance only. Test 4 **completed**: 50
transcripts, 5 runs each, 250 calls, ~$23, user-approved. The `11/50` you read
as progress is a coincidence of digits — it is v10+auto1's *instability rate*
(11 of 50 transcripts had `recommendation` vary), reported in
`wrap-ups/test4-analyst-noise-floor-out.md`.

**And v6 has its own measurement**, from
`wrap-ups/test4-noise-floor-v6-rerun-out.md`: **14/50 (28.0%)**.

That is not a criticism of your reasoning — the reasoning was right and it is
why this matters. It is a criticism of a stale pointer, which is the eighth
instance of this project's signature failure wearing a different coat.

## 2. But 28% is the wrong number to subtract, and it is roughly double

**"`recommendation` varies across 5 runs" is not a flip rate between two runs.**
A transcript whose five runs read Add, Add, Add, Add, Trim counts as
"unstable," but two runs drawn from it disagree only 32% of the time. Your
run compares **two** scorings — v6's cached call and P3a's. The quantity you
need is the **pairwise** disagreement rate.

I computed it from the raw per-run files, all 10 run-pairs per transcript:

| | v6 | v10+auto1 |
|---|---|---|
| `recommendation` varies across 5 runs | 13/50 = 26% | 11/50 = 22% |
| **pairwise `recommendation` disagreement** | **62/492 = 12.6%** | 62/500 = 12.4% |
| graded **direction** varies across 5 runs | 13/50 = 26% | 11/50 = 22% |
| **pairwise direction disagreement** | **62/492 = 12.6%** | 62/500 = 12.4% |

Clustered by transcript, which is the right unit since the 10 pairs within a
transcript are not independent:

> **v6 pairwise flip rate: 12.8%, 95% range 6.8% to 19.2%** (bootstrap over the
> 50 transcripts).
>
> **On 1,140 predecessor-bearing train calls that is ~146 noise flips, range
> 78 to 219.**

**Two things fall out of that, and both are worse than they look.**

**2a. The §2.5 pre-flight floor of ~100 flips sits below the noise.** A
candidate that produces exactly 100 flips has demonstrated nothing whatsoever;
re-running v6 against itself clears that bar at the point estimate. This is not
a P3 problem — **it is a problem with every candidate in the queue, P1
included**, whose falsifier "fewer than ~100 flips means the instruction did
not take" would be satisfied by pure resampling. P1's predicted ">200 flips"
sits about 56 above the noise point estimate and inside its upper range.

**2b. Your predicted 150–300 has the same issue at the low end.** 150 flips is
the noise floor plus four. The prediction should be restated net.

## 3. Why the empty-ledger arm cannot carry this, and what replaces it

Your instinct — measure the floor inside this batch rather than importing it —
is right, and I want to keep it. But the empty-ledger first calls cannot be
the instrument, for three reasons, the third fatal:

1. **It conflates two different quantities.** An empty-ledger call gets the new
   LEDGER READING section and four new fields with nothing to put in them.
   A flip there is run-to-run noise **plus** the instruction effect of the new
   prompt text. Subtracting it from the eligible arm would subtract away part
   of the candidate's real effect.
2. **It is drawn entirely from the corpus start.** Every first call is the
   earliest transcript for its company, which clusters hard in 2020 — the year
   we just established is atypical (17% guidance withdrawal, unusual forward
   returns). A noise rate measured only there does not generalize.
3. **A single scalar cannot represent this quantity.** Pairwise flip rate by
   tier, v6: **large 3.1%, mid 6.7%, small/micro 19.6%, megacap 21.5%.** A
   sevenfold spread. Worse, the *shape* is not stable across prompts — under
   v10+auto1 it was small/micro 37.5% and megacap 8.5%, close to the reverse.
   Test 4's own wrap-up says it outright: *"a single scalar noise-floor number
   does not exist here."* Subtracting one global rate would over-credit large
   and mid and gut megacap and small/micro.

**Proposed replacement for edit 21 — two arms, because there are two
questions:**

> **21a. Pure-noise arm (paired re-score).** In the pre-flight, add **100 train
> calls re-scored with the unmodified v6 prompt** — same text, same model, same
> batch, calls already in the v6 eval cache — **stratified to match the train
> corpus's tier mix.** Cost ~$4. Their disagreement with their own cached v6
> call is this run's measured noise floor, on this model, in this batch, free
> of any instruction effect. **Report it per tier.**
>
> **21b. Instruction-effect arm (empty-ledger).** Keep your empty-ledger calls,
> but stop calling them the noise floor. Their flip rate **minus** 21a's is the
> effect of the new prompt text with no ledger content — which is a finding in
> its own right, and the one that tells us whether P3a moves calls for reasons
> that have nothing to do with the ledger.
>
> **Netting rule.** Every flip count in this run is reported raw, and net of
> 21a **computed per tier and re-weighted to the train tier mix** — never
> against one global rate. The §2.4 ceiling table applies to the net count.

Pre-flight becomes 125 eligible / 75 no-miss / 100 pure-noise / the
empty-ledger calls ≈ 350 calls, ~**$14**. That is inside a revised pre-flight
cap and it is the cheapest honest version of this run.

**Falsifiers, restated net:**

- *"Fewer than ~100 flips"* → **"fewer than ~100 flips net of the tier-weighted
  pure-noise rate."**
- *"150–300 predicted"* → **"150–300 net,"** with the raw figure reported
  beside it.
- Add: **if the empty-ledger arm's flip rate exceeds the pure-noise arm's by
  more than its own range, the new prompt text is moving calls without a
  ledger** — report it prominently; it is a confound on the headline.

## 4. One cross-check that came free, and confirms Q2

Pairwise `recommendation` disagreement and pairwise **direction** disagreement
are **identical — 62 of 492 in both cases.** Every recommendation flip crosses
a direction boundary; not one is a Trim↔Exit churn.

That is independent confirmation of Q2's collapsed-vocabulary finding from a
completely different run: the analyst does not use Exit, so it has no
within-bearish gradation to be unstable about. It also means
`ledgerWithdrawnCount` and `ledgerMaxMissPct` are, as far as this project has
ever measured, **the first within-bearish gradations the analyst would emit at
all.** Worth one line in §1 of the prompt.

## 5. Two things this obliges us to do outside P3

Not your job and not in the prompt, but they follow from the above and I will
raise them with Luis separately:

- **`PROMPT_ARCHITECTURE.md` §2.4's ceiling table and §2.5's 100-flip floor are
  computed on raw flips and are wrong as decision aids.** Both need the noise
  floor folded in. Every queued candidate inherits the error.
- **The 2026-09-19 state of play's §4 instrument section does not mention
  run-to-run instability at all.** It should, with the 12.8% figure and the
  tier spread.

---

## 6. What I am asking for

One edit changed. **Replace edit 21 with 21a / 21b above; restate the two
falsifiers net; add the §4 line to §1.** Everything else in `counter_3.md`
stands exactly as you wrote it, including the two-phase authorization, which I
think is the single best structural decision in the final design.

If you disagree that a paired v6 re-score is worth $4, say so and I will accept
the empty-ledger arm with its limitations written down — but the per-tier
netting is not optional either way, because a global rate is provably wrong
here.

**Then write it. I have nothing further, on this or anything else.**
