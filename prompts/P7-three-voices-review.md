# Review of the P7 candidate and run prompt — one change, otherwise clear to run

**Date:** 2026-09-26 · **Reviewed:** `docs/prompts/candidates/EVALUATION_PROMPT_P7_three_voices.md`,
`prompts/P7-three-voices.md` (commit `45e579f`).
**Verdict:** one change to the candidate's structured block; the run prompt
is sound as written and needs only the matching one-line addition to §5e.

---

## The change — `gap` conflates two axes

The VOICES prose defines the gap on two things at once:

- `numbers_ahead` = numbers ahead of the claims **and** the analysts'
  concerns answered with evidence;
- `claims_ahead` = the story outruns the results **and** the pressed
  questions went unanswered.

A call where the numbers are ahead of the claims but the pressed question
was dodged has no value to take. The model will force it into `aligned` or
pick a side unpredictably, call by call. That matters because the run's
mechanism check (§5e, "does `numbers_ahead` carry the bullish edge the
mechanism predicts?") is the diagnostic that says whether the three-voices
idea worked or the score merely moved. A three-valued field that mixes two
axes cannot answer it cleanly.

**Fix, structured block only; the prose stays:**

```
"gap": "",         // exactly one of "numbers_ahead", "aligned", "claims_ahead"
                   // — numbers versus claims only
"pressure": ""     // exactly one of "answered", "avoided", "none"
                   // — were the pressed questions answered with evidence;
                   // "none" if nothing was pressed
```

And in the field definitions, one sentence each. The Gap paragraph in
VOICES can keep its wording; the two fields make the model record the two
judgments it is already being asked to make.

**Run prompt, §5e, add one line:** hit rate and median return by `gap` ×
`pressure` (a 3×3), with the prediction that `numbers_ahead` + `answered`
is the cell that carries the bullish edge. §4's `gap` share prediction is
unchanged; add `pressure` shares as a prediction (`answered` 40–60%).

**Pre-flight stop list (§4):** add "`pressure` value outside the three
allowed values" beside the existing `gap` check.

## Confirmed sound, no change

- Gates 1 and 3 are absolute targets (47.0%, 57.0%), so "holds against both
  B draws" cannot be gamed by the choice of draw; gate 2 is the paired
  difference against each draw, as §2.3a requires.
- The −0.03 tolerance equals B's measured wobble between identical runs
  (0.130 → 0.099); the ambiguity band (±3.4 points, ±0.03) is B's own
  movement, and the second draw is explicitly not approved.
- The pre-flight stop (under 20% direction disagreement on 150 calls) sits
  above B's 12.5% self-disagreement, so a P7 that merely re-rolls B stops
  before the full round.
- Matched coverage on both sides (top 235, bottom 191), seeded ties.
- Costs, cap, approval recording, batch-id discipline, commit order.

Nothing else. Once the two fields are in and the sha re-registered, run it.
