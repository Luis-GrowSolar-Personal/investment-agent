# Consensus-surprise screen and test — review

**Reviews:** `docs/handoffs/2026-09-27-consensus-screen-review-brief.md`,
`prompts/consensus-surprise-screen.md`, `prompts/consensus-surprise-test.md`.
**Verdict: go, with three changes.** All three are $0 and apply to both
prompts. Everything not named is accepted as written.

---

## Change 1 — "winners against the rest" can pass on the downside alone (error)

The screen's primary comparison is big-winner calls against the same
companies' **other** calls. "Other" includes the big losers. This project
already knows that bad news is readable: misses will sit in the loser
calls. So surprise can "separate winners" here while carrying no
information about winners at all. It would only be separating losers,
which B already does.

**Fix.** Three groups, not two: big winners (+20 or more), big losers
(−20 or worse), and the middle. The primary screen reading is **winners
against the middle**: median surprise difference, company-block range
above zero. Report losers against the middle beside it. The same
three-way split goes into the full test's item 2, so "finds winners" is
never earned by the misses.

## Change 2 — take the calendar quarter out of the surprise (error)

Winners cluster in a few sector-years (solar/storage 2025: 8 of 14).
Surprises cluster in time too: in 2020–21 almost every company beat by
a wide margin because estimates had been cut. Inside one company, its
winner calls and its other calls sit in different years. So a raw
within-company comparison can read the **year** as a surprise effect.
This is the bias the brief's Q1 asks about, and it is real.

**Fix.** Before any comparison, subtract from each call's SUE_p the
**median SUE_p of all fetched calls reported in the same calendar
quarter**. Call the result the quarter-adjusted surprise. It answers "did
this company beat by more than companies generally did that quarter?"
Use it as the primary measure in both prompts; report raw SUE_p beside
it. On 20 companies the per-quarter median rests on about 20 values,
which is enough for a median; on 57 it is comfortable. This does the
work of matching on year without throwing away calls.

## Change 3 — point the spot-checks at the numbers that decide the result

The five point-in-time checks are drawn at random (seed 11). The result
will be decided by the **largest** surprises, and those are exactly where
data problems live: a reported figure on a GAAP basis against an adjusted
estimate, or a stale estimate. A random draw will check five unremarkable
quarters and miss all of them.

**Fix.** Draw the five from the top and bottom 5% of quarter-adjusted
SUE_p among matched calls (three from the top, two from the bottom). Add
one diagnostic line: the share of matched quarters where AV's own
`surprisePercentage` exceeds 100% in either direction, by company. A
company with many such rows has a basis problem and its rows should be
flagged, not silently used.

---

## Answers to the brief's questions

1. **Validity of the winner-rich, within-company screen.** Valid for
   "does surprise separate winners from the middle" once changes 1 and 2
   are in. Selecting companies on outcomes does not bias a comparison
   made inside those companies; it only limits what the market-wide rates
   mean, and the prompt already labels those as inflated. Matching on
   year is the right instinct; quarter-adjustment does it better.
2. **Measure.** Keep price-scaled surprise. The classic version (divide
   by the company's own past surprise spread) needs eight or more
   quarters of history per company and would drop early calls; a rank
   within company is already what the within-company design does. One
   measure, fixed: quarter-adjusted SUE_p.
3. **Point-in-time.** Three verified quarters are enough to run a $0
   test. They are not enough to promote anything, and the test promotes
   nothing. Change 3 makes the next five checks count. If any of the five
   extreme rows turns out revised or mismatched, the wrap-up says so and
   the full test's reading drops to "can't tell" regardless of the
   numbers.
4. **Relation to the announcement-day move.** Do not close the lead on a
   failed screen alone; 20 companies cannot rule out a modest effect.
   The full test is free and its first day is the screen's fetch, so run
   it in any case, **except** if the screen is clearly negative **and**
   surprise relates to the day-one move at 0.5 or stronger. In that case
   the market already priced the surprise, the drift has already been
   shown absent on all 1,217 calls, and the lead is closed.
5. **EPS only.** Acceptable for the screen. But for the sectors Luis
   holds, EPS near zero makes the EPS surprise close to meaningless as
   information, whatever the scaling does to its size. Add one split to
   the full test: calls where the estimate is at least 1% of the share
   price against the rest. If the effect lives only in the first group,
   a revenue-surprise source is the next data question, not more EPS.

## What it means

If winners-against-middle clears zero on the quarter-adjusted measure,
this is the first bullish lead with a documented mechanism behind it,
and the pre-registered tune test is worth its three free days. If it
fails and change 3's checks are clean, consensus surprise joins the
closed routes, and the analyst's job is downside protection until a
revenue-surprise source or a live forward test says otherwise.
