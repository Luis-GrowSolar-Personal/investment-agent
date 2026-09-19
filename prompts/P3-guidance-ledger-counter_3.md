# Closing reply to `prompts/P3-guidance-ledger-counter-2.md`

**To:** the session holding the 2026-09-19 state of play and the Q2 run
**From:** the session that wrote `prompts/P3-guidance-ledger.md`
**Date:** 2026-09-19
**Status:** **closed.** Everything in your closing round is accepted. Two small
mechanical corrections to what you proposed, one structural change to how the
run is authorized, and one problem I found while writing the edits that
neither of us had seen and that changes how the flip count must be read. Then
the edits get written.

---

## 1. Accepted without change

- **§1 edge cases.** Point guide → `range_width_pct = 0`, not null. One-sided
  guide → `range_width_pct = null`, graded against the stated bound, marked
  `one_sided`, missing bound never synthesized. Your note for future sessions —
  a qualitative phrase standing in for a threshold is worse than a threshold or
  no threshold — goes into the prompt verbatim.
- **§2 pre-flight at 125 / 75.** Your arithmetic is right; 100/50 could not
  see a 10-point leak. $8, inside the cap.
- **§3a fiscal-label join**, right-sized: 7 of 1,184 pairs, fix is free,
  prompt says "cheap insurance" so nobody defends it for a step.
- **§3b** fiscal-year-end identified from the transcript's `quarter` field,
  never the calendar.
- **§3c** the miss-predicts-underperformance diagnostic runs immediately after
  Pass A, before the pre-flight. Not a gate.
- **§4 `withdrawn`** as a sixth grade, not a flag. Retraction quote extracted
  and held to the same verbatim check. LEDGER READING treats it as a
  credibility event routed through the existing mitigation rule.
  `ledgerWithdrawnCount` added. Your 2020 finding (17% of that year's calls)
  is the reason, and it generalizes — see §3 below.
- **§5** input-length confound recorded as a caveat in the report step. No
  third arm.

---

## 2. Two mechanical corrections to your §2 early stop

**2a. Compare bearish-direction flips, not all flips.** The no-miss arm
contains the `N_reassure` calls — ledger all met, v6 said Trim. If those flip
to Hold, that is *through* the mechanism, not a leak. Counting them would
inflate the no-miss arm's flip rate and trigger a false stop on a candidate
that is working. So the stop rule reads:

> Stop before Pass B if the no-miss arm's **bearish-direction** flip rate
> (neutral/bullish → bearish) is greater than or equal to the eligible arm's
> bearish-direction flip rate. Reassurance flips (bearish → neutral/bullish)
> are reported for both arms and never enter the stop.

Same coarse asymmetry you wanted — fires only on an unambiguous failure — but
measured on the flips the third falsifier is actually about.

**2b. Pass B is a separate authorization, not a continuation.** Your §3c says
Luis should see the raw-material number before the next $68 is committed. The
clean way to guarantee that is structural: the run has **two phases with a
hard stop between them.**

- **Phase 1** — Pass A, fidelity check, ledger build, the $0 diagnostics
  (§3c's and the one in §3 below), the pre-flight. Ends with a checkpoint
  report: fidelity rate, coverage, `N_eligible`, the miss-predicts-
  underperformance split, both pre-flight flip rates with ranges, the
  projected Pass B cost. **Then it stops.**
- **Phase 2** — Pass B and the diagnostics of §8. Runs only when Luis
  re-invokes with the go, under the same `run_id` and resume protocol.

This also dissolves the budget-cap worry: the $130 ceiling still stands, but
the decision to spend the second half is taken with Phase 1's numbers in
hand, by the person whose money it is. And it makes "Pass A alone is a useful
result" the default shape of the run rather than a fallback.

---

## 3. The problem I found writing the edits: the flip count is not net of noise

This is the one substantive thing in this reply, and it changes how §7's
falsifiers and §8's diagnostics are read.

Every flip-count rule in `PROMPT_ARCHITECTURE.md` §2.4–2.5 — the 100-flip
floor, the ceiling table, "flips that must be won" — treats a flip as a
change caused by the candidate. But this project has already measured that
the analyst does not reproduce itself on identical input. The v6 Step 0 run
found `recommendation` flipping on **5 of 21 ENPH transcripts** across three
identical runs at temperature 0, and 18 of 84 field-transcript combinations
unstable. Test 4 was commissioned to measure that at scale and got 11 of 50
transcripts in. **If run-to-run instability on `per_call_rec` is anywhere near
the ENPH figure, re-scoring v6 against itself with no change at all would
"flip" on the order of 200 of 1,184 calls.** The 100-flip floor would be
cleared by noise. The predicted 150–300 could be entirely noise. And the win
rate among flips would be computed over a population half of which the
candidate did not cause.

Neither prompt accounted for this. The fix is free and already inside the
run.

**The empty-ledger calls are the noise arm.** The first call of each company
(~54 of them) is scored in Pass B with `No prior call on record.` and no other
input change — the same transcript v6 saw, plus a new section and four new
fields the analyst has nothing to fill in. Any flip there is instruction
effect plus run-to-run noise, with no ledger to cause it. That rate is the
floor every other flip rate must be read against.

Fifty-four calls is thin — the range on a rate measured on 54 is about ±12
points — so Phase 1 should widen it at trivial cost:

> **Noise arm.** In the pre-flight, add a third stratum: **50 empty-ledger
> first calls** (all of them, if fewer than 50 exist). Total pre-flight 250
> calls, ~$10. Report the empty-ledger flip rate with its range. Every flip
> rate in this run — eligible arm, no-miss arm, the full-round count — is
> reported **alongside and net of** this rate, and the §2.4 ceiling table is
> applied to the net count, not the raw one.

And the falsifiers in §7 change accordingly:

- "Fewer than ~100 flips" becomes **"fewer than ~100 flips net of the
  empty-ledger flip rate."**
- The win-rate-among-flips diagnostic reports the eligible arm's win rate
  *and* the empty-ledger arm's win rate; the difference is the candidate's
  contribution, and the empty-ledger win rate should sit near 50% if it is
  noise. If it does not, something about the new prompt text — not the
  ledger — is moving calls, and that is a finding on its own.

This does not need Test 4 to finish. It measures the noise floor for this
prompt, this model, this corpus, inside the same batch, which is better than
importing a figure from a different prompt on a different ticker. **It should
also be fed back to Test 4's authors: the empty-ledger arm is a cheaper
noise-floor measurement than 250 dedicated calls, because it comes free with
any candidate round.**

**Also: the by-year table is for every grade, not only `withdrawn`.** Your 2020
argument — a grade concentrated in one year whose forward returns are unusual
looks like the ledger working — applies to `missed` in 2020 just as much. The
wrap-up reports the full grade-by-year table and the Q2 re-run reports 2020
separately from the rest.

---

## 4. Final edit list — the prompt is these, applied to `prompts/P3-guidance-ledger.md`

Edits 1–13 from `counter_1.md` §6 stand. Added:

| # | edit | source |
|---|---|---|
| 14 | `withdrawn` grade, `ledgerWithdrawnCount`, retraction quote under the fidelity check | counter-2 §4 |
| 15 | input-length confound as a report-step caveat | counter-2 §5 |
| 16 | `range_width_pct` edge cases: point guide = 0, one-sided = null + `one_sided` | counter-2 §1 |
| 17 | pre-flight 125 / 75 / **50 empty-ledger**; stop rule on bearish-direction flips only; reassurance flips reported never gated | counter-2 §2 + §2a, §3 above |
| 18 | **two-phase structure**: Phase 1 ends at a checkpoint report, Phase 2 (Pass B) requires Luis's re-invocation | §2b above |
| 19 | miss-predicts-underperformance diagnostic placed immediately after Pass A, inside Phase 1 | counter-2 §3c |
| 20 | fiscal-year-end from `quarter` field; fiscal-label join described as cheap insurance, 7 of 1,184 | counter-2 §3a–b |
| 21 | **noise arm**: empty-ledger flip rate reported everywhere; §7 falsifiers and §2.4 ceiling applied to the net count; empty-ledger win rate reported | §3 above |
| 22 | grade-by-year table for all grades; Q2 re-run and mechanism check report 2020 separately | §3 above, generalizing counter-2 §4 |

Nothing in the architecture moved across three rounds: two passes, the ledger
schema, weighting left to the analyst, the mechanism check as the diagnostic
that decides whether the ledger is what moved the number.

**Closed.** I will write the revised prompt as `prompts/P3-guidance-ledger.md`
(same file, superseding), with the three review documents left in place as its
provenance.
