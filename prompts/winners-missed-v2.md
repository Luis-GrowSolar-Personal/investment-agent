# Winners B missed, v2 — redesigned classifier, and 30 same-company pairs. About $4

**Run ID:** `winners-missed-v2`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/winners-missed-v2-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $4.** Step 1 is $0
bookkeeping. Step 2 classifies B's short READ text for all 1,217 train
calls, ~$2. Step 3 compares 30 transcript pairs, ~$2. **Hard cap $8**,
counted before every `create()`. Luis approves at Step 0; record it in
`progress.json` or stop and ask.

---

## Framing

**What this run exists to answer.** The same question as
`prompts/winners-missed-analysis.md`: **did B see the good news on calls
that went on to beat the S&P by 20+ points, and not act on it — or was
there nothing to see?**

The first run answered part of it and stopped on the rest
(`wrap-ups/winners-missed-analysis-out.md`):
- **Settled:** B's scale carries no information about big winners. A
  −2 call is as likely to be a big winner as a +3 call (~14% each,
  against a 12.6% base).
- **Settled:** winners are not rebounds. Their prior six-month return
  (−3.6) is close to the middle group's (−2.2), so the stock's own price
  history is not indicated as an input.
- **Not settled:** the classifier's "strong positive" meant "specific,
  such as a number", and B's prompt tells it to cite numbers. 98% of
  READs scored strong-positive, and the pre-flight stop rule fired. That
  was a definition defect, and it is fixed here.

**What changes in v2.** The classifier asks about **balance and concrete
events**, not an inventory of evidence:
- whether good news outweighs bad in the read;
- whether management **raised** its outlook;
- whether results **beat** the company's own prior guidance;
- whether B named good news and then **set it aside**.

"Raised" and "beat" matter for a reason outside this project. Companies
that beat and raise tend to keep drifting up for months afterwards
(post-earnings-announcement drift, one of the best-documented patterns
in markets). If B's READs note beat-and-raise on future winners and B
still scores them neutral, B saw the signal and did not commit.

**Step 3 is independent of Step 2.** It runs even if Step 2's pre-flight
stops.

**Read first:** `wrap-ups/winners-missed-analysis-out.md` (all);
`prompts/winners-missed-analysis.md` (this prompt reuses its ground rules
and its Step 3 as written); `analysis/winners_missed_analysis.py` and the
driver's `--winners` path (extend; do not fork).

---

## Ground rules

1. **Train only.** No tune, no holdout, no DB writes, no cache refresh.
2. **The classifier never sees outcomes.** It gets only B's READ paragraph
   (draw 1), with the SCORE section and structured block stripped and
   asserted absent. No ticker, date, return or group. Seeded random order,
   seed 11. B's own company names inside its READ are passed verbatim, as
   in v1.
3. **Classifier:** `claude-sonnet-4-6`, Batch API, `max_tokens` 400, no
   temperature parameter. Written to
   `docs/prompts/diagnostics/READ_CLASSIFIER_v2.md`, with its sha recorded
   in `progress.json` before any call. v1 stays on disk, unchanged, as the
   record of the failed definition.
4. **Step 3 generates hypotheses only.** Nothing from it is scored or
   tested.
5. **Every reading below is fixed before any number is computed.** Report,
   do not decide.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/winners-missed-v2/`. `progress.json`
first. Commit this prompt file if untracked or modified, as its own
commit. Clean tree; hard stop if `git_dirty` cannot be recorded `false`.
Script and driver extensions committed before any output. Batch ids
committed the instant `create()` returns. One process, no pipe to `tail`,
no background poller.

---

## Step 1 — bookkeeping, $0 (one commit)

`docs/architecture/PROMPT_ARCHITECTURE.md`:

- **§2.2 queue:** add one row, **"P9 averaged (score twice, average) —
  eligible for one tune look, parked 2026-09-26"**. Give the reason in one
  line: it passed the fixed reading by 0.0002, three of four alternate
  seeds fell below the line, and its benefit (severity) serves the
  deferred allocator rebuild. The tune look is reserved for a bullish
  candidate if one emerges. Point to
  `wrap-ups/P9-close-and-averaged-comparison-out.md`.
- **§2.1 "what the baselines say is broken":** add two dated lines from
  `wrap-ups/winners-missed-analysis-out.md` step 1:
  1. B's score carries no information about big winners (+20 points or
     more): ~14% of both its −2 and its +3 calls became big winners,
     against a 12.6% base.
  2. Big winners are not rebounds (prior six-month median −3.6 against
     −2.2 for the middle group), so the stock's own price history is not
     indicated as an input.
- **Standing process rule, add to §2.3a as rule 7 (decided 2026-09-26):**
  "Every new prompt candidate runs **two draws on train** from the start.
  Single draws landed in the ambiguity band on P6B/B, P9 and P9-averaged;
  a second draw was needed each time."

Commit: `docs: P9-averaged parked for tune; winners findings in §2.1; §2.3a rule 7 (two draws on train)`.

---

## Step 2 — READ classifier v2 (~$2, the highest-value step)

### 2a. The classifier

It is given only an analyst's short read of one earnings call. Tell it
not to guess how the stock did. It returns:

```
---STRUCTURED---
{
  "balance": "",    // weighing only what the read says: does the positive
                    // evidence "outweighs", "balanced", or "outweighed" by
                    // the negative?
  "raised": "",     // does the read say management RAISED guidance or its
                    // outlook this quarter? "yes" / "no" (reaffirmed,
                    // maintained, lowered, or not mentioned are all "no")
  "beat": "",       // does the read say results came in clearly ABOVE the
                    // company's own prior guidance or stated targets?
                    // "yes" / "no" (in line, below, or not mentioned: "no")
  "discounted": ""  // does the read name a positive point and then set it
                    // aside (priced in, one-off, unproven, outweighed by a
                    // risk)? "yes" / "no"
}
---END STRUCTURED---
```

Give one plain-language definition per value, with a one-line example of
a "yes" and a "no" for `raised` and `beat`. **Do not define any value by
the presence of numbers or specifics.** v1 failed exactly that way.

### 2b. Pre-flight — 60 READs (~$0.10)

The same 60, stratified and seeded, as v1's pre-flight. Parse check.

**Stop rule, unchanged:** stop Step 2 if any one field takes a single
value on more than 85% of the 60. Also report v1's `discounted`
distribution on the same 60 beside v2's.

**Predictions, not gates:** `raised = yes` on 15–35%; `beat = yes` on
15–35%; `balance` spread across all three values, none above 60%.

If the pre-flight stops, **skip to Step 3.** Do not redefine the
classifier in this run.

### 2c. All 1,217 READs, one batch

Commit `read_labels_v2.jsonl`.

### 2d. The test, pre-registered

**Among B's non-bullish calls** (draw 1 score ≤ +2; 118 big winners
against 864 others), compare big winners (≥ +20) with everything else on
four shares:
- (i) `balance = outweighs`;
- (ii) `raised = yes`;
- (iii) `beat = yes`;
- (iv) `discounted = yes`.

Report each with a Wilson range, and each difference with a ticker-block
bootstrap range (2,000 draws, seed 11).

**Reading, fixed now.** Four comparisons at once will cross the line by
chance about 1 time in 5, so one crossing is not enough.
- **"Seen and not committed"**: at least **two of (i), (ii), (iii)** are
  higher for big winners, with the difference's range excluding zero.
- **"Suggestive"**: exactly one of (i)–(iii) excludes zero. Name it. It
  becomes the lead hypothesis for a candidate, not a finding.
- **"Not seen"**: none of (i)–(iii) excludes zero.
- (iv) is reported beside them. If it is higher for winners, with its
  range excluding zero, add **"and talked down"**.

**Also report, not gated:**
- The same four shares inside B's bullish pile (≥ +3) and bearish pile
  (≤ −2), winners against the rest.
- The **beat-and-raise combination** (`raised = yes` and `beat = yes`):
  how many calls, the big-winner rate among them, and their median
  six-month return, against all other calls. This is the
  post-earnings-drift check in one number.
- **What B scored the calls the classifier tagged beat-and-raise**: the
  distribution of B's score on them. If most sit at +1/+2, B saw them and
  held back.

**Small numbers, stated plainly.** 118 big winners are in the non-bullish
pile. A difference smaller than about 10 points cannot be told from
chance at that size.

---

## Step 3 — 30 same-company pairs (~$2, hypotheses only)

**Run exactly as `prompts/winners-missed-analysis.md` Step 3 specifies**,
unchanged:
- one big-winner call and the same company's nearest middle call;
- 30 pairs, seeded selection;
- both transcripts, labelled only "Call A" and "Call B" in seeded order;
- ticker, company name (where mechanically possible) and dates stripped;
- the model is told one call was followed by a much better six months,
  not which.

Ask for its pick, and **one concrete, checkable difference stated as a
mechanism**. Report:
- right picks out of 30 (chance is 15);
- the mechanisms grouped by kind;
- the mechanisms from right picks listed separately;
- **how many of the right-pick mechanisms are a raise, a beat, or both**.
  This connects Step 3 to Step 2.

Generator, never judge. 30 pairs test nothing. The model may remember
these companies; a mechanism that cannot be said in plain words is
treated as recall.

---

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/winners-missed-v2-out.md`, `.md` only. Open with:

> Reading only B's own notes, a classifier found [raised outlook / beat
> guidance / good news outweighing bad] on ___% / ___% / ___% of the calls
> B did not score bullish that went on to beat the S&P by 20+ points,
> against ___% / ___% / ___% of the rest. **[Seen and not committed /
> Suggestive: ___ / Not seen]**. Calls tagged beat-and-raise became big
> winners ___% of the time (base 12.6%), and B scored ___% of them below
> +3. In 30 same-company pairs, the model picked the winner ___ times; ___
> of its right-pick reasons were a raise or a beat. Step 1's bookkeeping
> landed in commit ___.

**Close with the next step, both ways.**
- If "seen and not committed" or "suggestive": name the one-sentence
  change to B it points to (e.g. "commit to +3 or higher when guidance is
  raised and results beat").
- If "not seen": the transcript read does not separate winners, and the
  next step is outside data (P4 XBRL facts, or consensus).
- State whether Step 3's right-pick mechanisms agree with Step 2's
  reading.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Finish with `git push`** of `sweep/db-corpus-baseline` after the
wrap-up commit, and report the pushed hash; on failure, say so and never
force. **Budget stop:** Step 1 always runs. Steps 2 and 3 are
independent; if the cap is tight, run Step 2 first.
