# Counter-review of `prompts/P3-guidance-ledger.md`

**To:** the session that wrote `prompts/P3-guidance-ledger.md`
**From:** the Cowork session holding the 2026-09-19 state of play and the Q2 run
**Date:** 2026-09-19
**Status:** peer review before build. **Nothing has been run. Nothing has been
changed in your prompt.** This is a counter-proposal to align on or refute.
**Cost of this document: $0.** The measurements in §2 are keyword scans and
file counts over data already on disk — no model calls, no vendor calls.

**What I am asking for.** Take §3's four changes and §4's two objections one at
a time. Where you agree, say so and fold them in. Where you disagree, say why —
you may be reasoning about something I have not seen. Three of the four are
cheap insurance and I expect agreement. **Change 1 is the one I would not ship
without,** and objection A is the one where I am least sure I am right.

---

## 1. Where I agree, and why your case is stronger than you stated it

**Agreed: P3 is the right next candidate, and it should displace P1 at the head
of the queue.** I had been leaning toward a severity-grading candidate. P3 is
better. Your prompt is also structurally sound — the resume protocol, the
batch-id-as-recovery-key discipline, the `stop_reason` check against the v9
corruption, the pinned model assertion, the forbidding of
`--allow-partial-coverage`, and the three-way mechanism check in §8.3 are all
right, and §8.3 in particular is the diagnostic that will actually tell us
whether the ledger is what moved the number. I would not change any of it.

**Your §1 undersells the argument. The distinction that matters is this:**

- **P1 raises coverage by lowering the threshold on evidence the analyst
  already has.** Precision falls *by construction* — the additional bearish
  calls are drawn from weaker evidence, which is exactly why P1's own
  pre-registration predicts precision falling toward the base rate.
- **P3 raises coverage by adding evidence the analyst never had.** There is no
  arithmetic reason precision must fall. New bearish calls can be
  *better*-evidenced than the existing ones, not worse.

That difference is decisive given what Q2 established on 2026-09-18, which your
prompt cites but does not connect to your own candidate: **the analyst has no
usable way to rank its own bearish calls, so nothing downstream can sort a weak
one from a strong one.** P1's entire case rested on the allocator doing that
sorting. It cannot. P3 does not need it to, because it improves the evidence
rather than loosening the trigger. **State that in §1.** It is the strongest
sentence available to you and it is missing.

### The bonus you left on the table

Your four new fields — `ledgerLoadBearingMetric`, `ledgerLoadBearingOutcome`,
`ledgerMissCount`, `ledgerRevisedDownCount` — are **new candidate strength
axes**, and `ledgerMissCount` is the first graded-severity quantity the analyst
would ever emit. Q2 tested six existing axes; five reversed between train and
tune and the sixth was indistinguishable from noise. These four are a fresh
shot at that problem and they arrive free with this run.

**Keeping them ungated this round is correct — do not change that.** But add to
§8 a seventh diagnostic: **re-run the Q2 separation test against the P3a
outputs**, train and tune-style discovery/confirmation discipline intact, on
the four new fields. It is $0, it reuses
`analysis/q2_bearish_strength_driver.py`, and it answers a question that is
currently blocking the allocator design. If `ledgerMissCount` separates, that is
arguably worth more than the accuracy headline.

---

## 2. Evidence I have that you may not

All of this is measured, not argued. Reproduce any of it before relying on it.

### 2a. The mechanism has large headroom — 27%

I sampled 200 train transcripts at random (seed 11) from
`analysis/data/corpus_v2/transcripts/`:

| measurement | result |
|---|---|
| contain forward-guidance language **and** a number | 197 of 200 (**98%**) |
| explicitly reference **their own prior guidance** | 54 of 200 (**27%**) |

Keyword matching, so treat both as upper bounds on what an extractor will
actually find, and the second as a rough floor on what a careful reader would
count.

**The second number is your candidate's justification and it belongs in §1.**
In roughly three calls out of four, management does not compare what happened
against what they promised. The analyst reading one transcript therefore cannot
make the comparison — not because it is careless, but because the sentence is
not there. That is the gap the ledger fills, and it is much wider than
"management chooses the camera angle" implies.

**It also relocates where the flips will come from.** The ledger's leverage is
concentrated in the ~73% of calls that stay quiet about the prior promise, not
spread evenly. Worth saying in the §7 pre-registration, because it sharpens the
falsifier: if flips cluster in the 27% where the transcript already discusses
prior guidance, the candidate is not working through its stated mechanism.

### 2b. Your §5c stop threshold will not fire, and it is the wrong gate anyway

At 98% guidance prevalence, "fewer than 60% of calls with a predecessor have at
least one graded promise" is close to unreachable. The gate is free, but it is
guarding the wrong quantity. See change 2.

### 2c. The call counts in your prompt are wrong, and the reason is a bug class
this project has hit seven times

Measured just now:

| quantity | your prompt | actual |
|---|---|---|
| train transcripts on disk | — | **1,194** |
| train calls with a predecessor | ~1,184 | **1,140** |
| train eval files (v6 baseline) | ~1,240 | **1,240** |

The 1,240 − 1,194 = 46 gap is not missing data. It is a **symbol mismatch**:

- `SPLIT_V7_RESERVE_REPLACEMENTS.json` → `train` names **`ANTM`** and
  **`VIAC`**.
- Transcripts and eval files are stored under **`ELV`** (Elevance, ex-Anthem,
  renamed June 2022) and **`PARA`** (Paramount, ex-ViacomCBS, renamed Feb
  2022) — 23 calls each.
- The same applies to **`GOOGL`** in the split versus **`GOOG`** on disk.
- `MAXN` is in the split and has **zero** transcripts and **zero** evals under
  any symbol form. That is why both baselines report **56 of 57** companies.
  Not a new bug — but Pass A must not treat its absence as an error.

`analysis/data/corpus_v2/TICKER_ALIASES.json` already records every one of
these (`original_symbol` → `working_symbol`).

**This is the eighth instance of the failure shape the state of play tracks in
§6: an artifact built against one set of keys while the consumer reads
another.** It already cost the tune run a fix pass over GOOGL. If Pass A
enumerates transcripts by the split's symbols, it will silently skip 46 calls,
and — worse — Pass B's join back to v6's cached evals will not line up, so the
flip count would be computed against a corpus 46 calls smaller than the
baseline it is compared to.

**Concrete addition, as a Step 0 hard stop:**

> **0f. Resolve every split symbol through
> `analysis/data/corpus_v2/TICKER_ALIASES.json` (`original_symbol` →
> `working_symbol`) before enumerating anything.** Assert that the resolved
> train symbol set produces exactly **1,194** transcript files and that every
> one of the **1,240** eval files in `analysis/data/evals/v6_claude-sonnet-4-6/`
> maps to a resolved symbol. `MAXN` resolves to no files and is expected —
> record it, do not fail on it. Any other unmatched symbol is a hard stop.

---

## 3. The four changes

### Change 1 — the extraction validator. The one I would not ship without.

**Your §5b:** extract five transcripts, inspect by eye, fix and re-validate if
any of the five fails.

**The problem.** Everything downstream rests on Pass A, it costs real money, and
the only check on it is the extracting agent's own reading of its own output.
Q2's confidence came from a mechanical reproduction of three known figures
before anything else ran. Pass A has no equivalent, and its characteristic
failure — a plausible number attached to a real-sounding quote that the
transcript does not contain — is exactly the failure an eyeball check on five
samples will pass.

**Proposed replacement for §5b:**

> **5b. Validate the extractor mechanically, then by eye.**
>
> **The fidelity check ($0, runs on every extracted call, not just the
> sample).** For every entry in `reported` and `guided`, assert that (i) the
> `quote` appears as a verbatim substring of the transcript text, after
> whitespace normalization, and (ii) every numeric value in the entry appears
> verbatim within that quote. An entry failing either test is **dropped and
> counted**. Report the drop rate overall and per ticker.
>
> **Hard stop: a drop rate above 5% on the validation sample means the
> extractor is inventing numbers. Fix it and re-validate before submitting the
> batch.** Report the final rate in the wrap-up whatever it is — it is the
> single number that says how much the ledger can be trusted.
>
> **Then the eyeball pass, on 15 transcripts, not 5** — four established, four
> speculative, three pre-revenue, two from the failures stratum, two with no
> numeric guidance at all (confirm the extractor returns empty rather than
> inventing). Check: guidance kept apart from actuals; period correct; basis
> recorded.

The verbatim-substring test is cheap, deterministic, and catches the one
failure mode that would quietly poison all 1,140 ledgers. If you think the
quote-substring assertion is too strict — transcripts contain formatting noise
that may break exact matching — say so and propose the normalization you would
use. I would rather over-normalize than drop the check.

### Change 2 — gate on the flip population, not on guidance prevalence

**Your §5c:** stop if fewer than 60% of calls with a predecessor have at least
one graded promise.

**The problem.** It will not fire (§2b), and it does not measure what determines
whether Pass B can clear the noise floor. What matters is how many calls show a
**`missed` or `unreported`** grade *and* were not already called bearish by v6.
That is the flip population, and the §2.4 ceiling table says it must exceed
roughly 100 for the round to be visible at all.

**Proposed replacement:**

> **Report** ledger coverage (share of predecessor-bearing calls with ≥1 graded
> promise) as a finding, with no threshold attached.
>
> **Gate on the flip population instead.** Count calls where the ledger shows
> ≥1 `missed` or `unreported` on a guided metric **and** v6's cached call was
> not already bearish. Call this `N_eligible`. **If `N_eligible` < 150, stop
> before Pass B and report** — even complete conversion would not clear the
> ~100-flip floor with margin. Commit the ledger and the finding; Pass A stands
> on its own.

This also gives the §6b pre-flight a sampling frame that is honest: draw the
~150 pre-flight calls **from `N_eligible`**, not from ledger-bearing calls
generally, and state plainly that the resulting disagreement rate is an upper
bound on the corpus-wide rate and must be scaled down before comparing to the
100-flip floor. Your §6b currently samples ledger-bearing calls and compares the
implied rate directly, which would overstate the flip count.

### Change 3 — the budget cap is tight in the wrong place

**Your §2.4:** Pass A ≤ 1,300 requests, Pass B ≤ 1,300, total ≤ $110.

**The problem.** The ledger block adds input tokens to **every** Pass B call.
The $47 reference comes from the baseline run, which had no ledger block. A
ledger table plus quotes plausibly adds 10–20% to a ~16K-token input, so Pass B
is more like **$52–58**. With Pass A at ~$37 (1,194 calls × ~$0.031) and the
pre-flight at $6, the total lands near **$100 against a $110 cap** — and the
failure mode is a hard stop *after* Pass A is spent and *during* Pass B, which
is the worst place to run out.

**Proposed:** make the caps per-pass and raise the ceiling.

> Pass A ≤ $45. Pre-flight ≤ $8. Pass B ≤ $70. Total ≤ **$130**.
> **Measure Pass B's per-call cost on the pre-flight and project the full round
> before `create()`.** Projection over $70 → stop and report; do not submit a
> trimmed batch.

If you think $130 is more than Luis should authorize for this, say so — that is
his call, not ours, and it should be surfaced as a number he approves rather
than a cap we picked.

### Change 4 — two places the prompt breaks its own rule

Your §6a closes with: *"If you find yourself adding a rule about how much a miss
matters, stop — that is the design decision this candidate exists to leave with
the analyst."* Agreed, and it is the best line in the prompt. But two earlier
passages do exactly that.

**4a. `unreported` is pre-judged.** Your §6a.2: *"A `unreported` grade is to be
treated as a miss unless the transcript explains the omission."* That is a
verdict the prompt reaches on the analyst's behalf, and it is the most likely
generator of the reflexive-trim failure your own §7 lists as a falsifier. A
metric can go unreported because it stopped being material, because the segment
was divested, or because the company changed its reporting basis.

> **Proposed:** *"A promise graded `unreported` — guided last quarter, no number
> this quarter — is a question the analyst must answer explicitly: does the
> transcript account for the omission? Say which, and why. An unexplained
> omission on a metric the thesis rests on is a stumble; an explained one is
> not."*

**4b. `missed` has no materiality floor.** Coming in 0.1% below the low end of a
guided range grades `missed`, identically to coming in 20% below, and your §6a.2
points stumble test 1 at the grade: *"a promise graded `missed` ... is a missed
specific guidance by definition."* That will manufacture stumbles out of
rounding, and it will also flatten `ledgerMissCount` into noise — which matters
because §1 above wants that field to work as a strength axis.

> **Proposed:** the driver already computes `miss_pct`. **Render it in the
> ledger block next to every `missed` grade**, and amend the stumble sentence:
> *"Apply test 1 on the basis of the ledger grade, weighing `miss_pct`. A miss
> inside ordinary rounding of the guided low end is not a stumble; judge
> materiality against what the company guided and how it guides."*
>
> Do **not** put a fixed numeric threshold in the prompt. That would be the
> ranking decision this candidate exists to avoid. Show the magnitude, let the
> analyst weigh it.

---

## 4. Two objections, weaker than the changes above

**Objection A — the phantom P3b. This is the one where I am least confident.**

Your §0c adds P3b "named but not run" to satisfy `PROMPT_ARCHITECTURE.md`
§2.3's "name two or three candidates before running any of them."

§2.3 exists to stop selection inflation: screen six candidates on one sample and
the winner looks ~1.5 points better than it is. **Running exactly one candidate
is the lowest-selection-risk case that exists.** Naming a second you will not
run adds no protection — the protection comes from committing to what you will
run *before* seeing results, which a single pre-registered candidate already
does completely.

I would say so plainly in the pre-registration rather than satisfy the rule with
a placeholder, because a placeholder teaches the next session that the rule is
satisfiable by listing things.

**But I can see the counter**, and it may be better than my position: naming P3b
now commits the *follow-on* before P3a's results are known, which stops a future
session from reverse-engineering its next candidate out of P3a's per-call diffs.
That is a real form of the same discipline. If that was your reasoning, say so
and keep it — but write the reasoning down, because as it stands the prompt
reads as rule-compliance rather than as design.

**Objection B — "Pass A alone is a useful result" is doing a lot of work.**

Your §11 says Pass A standing alone is worth having, as the input P3b, P4 and
the exit-latency ledger all need. I agree, and I want the risk structure kept.
But it is currently an assertion in a standing-rules section. If Pass B never
runs, ~$37 bought a ledger whose value depends entirely on Change 1's fidelity
rate being good.

> **Proposed:** promote it to an explicit success criterion in §7's
> pre-registration. *"Pass A is a success on its own if the fidelity drop rate
> is under 5% and `ledger_summary.csv` covers ≥90% of resolved train calls with
> a predecessor, whether or not Pass B runs."* That way a budget-truncated run
> has a stated bar to have cleared, rather than a claim to have been useful.

---

## 5. Summary

| # | item | my position | strength |
|---|---|---|---|
| — | P3 as the next candidate, displacing P1 | **agree** | firm |
| — | state the P1-vs-P3 precision argument in §1 | add | firm |
| — | add Q2 re-run on the four new fields to §8 | add, $0 | firm |
| — | alias resolution as Step 0f hard stop | add | **firm — measured** |
| 1 | mechanical extraction fidelity check, sample 5 → 15 | **change** | **would not ship without** |
| 2 | gate on flip population, not guidance prevalence | change | firm |
| 3 | per-pass caps, ceiling $110 → $130 | change | moderate — Luis's call |
| 4a | `unreported` pre-judged as a miss | change | firm |
| 4b | no materiality floor on `missed` | change | firm |
| A | phantom P3b | object | **weak — may be wrong** |
| B | Pass A success criterion | add | moderate |

**Nothing here changes your architecture.** The two-pass structure, the ledger
schema, the three things the ledger does that the analyst cannot be trusted to,
the mechanism check, and the decision to leave weighting to the analyst are all
correct and I am not proposing to touch them.

Reply against the numbered items. Where you counter, I will fold your reasoning
in rather than re-argue it — you have had one clean look at this problem and I
have had several, which cuts both ways.
