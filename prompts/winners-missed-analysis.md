# Winners B missed — is the signal in the transcript? About $8

**Run ID:** `winners-missed`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/winners-missed-analysis-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $8.** Step 1 is $0. Step 2
classifies B's own short READ text (not transcripts) for all 1,217 train
calls, ~$6. Step 3 is ~$2. **Hard cap $12**, counted before every
`create()`. Luis approves at Step 0; record it in `progress.json` or stop
and ask.

---

## Framing

**What this run exists to answer.** Every prompt so far is blind to big
winners. On train, 153 calls were followed by a gain of 20 or more points
over the S&P in six months. B scored only 35 of them bullish (≥ +3) and
26 of them **bearish** (≤ −2). Big winners are about as common in B's
bearish pile (26 of 191, ~14%) as in its bullish pile (35 of 235, ~15%).
Two prompt changes aimed at winners have failed (v6's rubric, P7).

The question decides the next month of work: **did B see the good news
and not commit to it, or was there nothing in the transcript to see?**
- If B saw it and discounted it, the fix is a prompt change. That is how
  B fixed the bearish side: the reading was there, the old output threw
  it away.
- If there was nothing to see, the next step is information from outside
  the transcript.

**Scope.** This is diagnosis, not a candidate. Nothing is promoted, no
prompt is changed, and nothing touches tune or holdout.

**Already established; do not rediscover.**
- B draw 1: `p6-output-format-round/scores_b.jsonl` (the `content` field
  holds B's READ and structured block).
- Per-call table: `p6-output-format-round/calls.csv` (`fwd_rel_ret_tradeable`,
  `b_score`, `stratum`, `tier`).
- B draw 2: `b-champion-and-noise-floor/scores_b_rerun1.jsonl`.
- P7's failure: `wrap-ups/P7-three-voices-train-out.md`. Its labels
  collapsed to "claims ahead / avoided" on ~80% of calls. Step 2's
  classifier must not repeat that; see its stop rule.
- **A company's own price history does not breach the analyst firewall**
  (2026-09-17 state of play, §3 closed decisions). Step 1d uses it.

**Read first:** `wrap-ups/B-champion-and-noise-floor-out.md`,
`wrap-ups/P7-three-voices-train-out.md`, `wrap-ups/P9-close-and-averaged-comparison-out.md`;
`analysis/p6_output_format_driver.py` (reuse its batch machinery; add a
`--winners` path, do not fork).

---

## Ground rules

1. **Train only.** No tune, no holdout, no DB writes, no cache refresh.
2. **The classifier never sees outcomes.** It sees only B's READ text,
   the paragraph B wrote, and nothing about what the stock did next. No
   ticker, no date, no return, no hint of which group the call belongs to.
   Calls are submitted in seeded random order (seed 11). Strip B's
   structured block and its score from what the classifier sees, so the
   classifier judges the words, not B's number.
3. **Classifier:** `claude-sonnet-4-6`, Batch API, `max_tokens` 400, no
   temperature parameter. The classifier prompt (§2a) is written to
   `docs/prompts/diagnostics/READ_CLASSIFIER_v1.md` and its sha recorded
   in `progress.json` before any call. It is a measuring tool, not a
   candidate, so it gets no registry entry.
4. **Step 3 generates hypotheses only.** Its output is a list for Luis to
   vet. Nothing is scored or tested.
5. **Report, do not decide.** Every reading below is fixed before any
   number is computed.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/winners-missed/`. `progress.json` first.
Then commit this prompt file if untracked or modified, as its own commit
(`prompt: winners-missed analysis`). Then clean tree; hard stop if
`git_dirty` cannot be recorded `false`. Driver/analysis extension
committed before any output, as its own commit. Batch ids committed the
instant `create()` returns. One process, no pipe to `tail`, no background
poller.

---

## Step 1 — who are the winners? $0 (run first)

Definitions, fixed:
- **Big winner:** `fwd_rel_ret_tradeable` ≥ +20.
- **Big loser:** ≤ −20.
- **Everything else:** "middle".

1a. **Cross-table**: B draw 1 score (each value −5..+5) by outcome (big
winner / middle / big loser), counts and row shares. The same for B
draw 2.

1b. **Where the winners sit**: share of big winners inside B's bearish
(≤ −2), neutral (−1..+2) and bullish (≥ +3) piles, with Wilson ranges,
against their 12.6% share of all calls.

1c. **By stratum, tier and year** (2020 separate): big-winner counts, and
B's bullish hit rate on them.

1d. **What happened before the call ($0, own price history).** For every
call, the stock's return vs SPY over the 182 days **before** the call.
Use the same price cache and the same tradeable convention, mirrored
backward: from the close 182 days before the call to the last close
before the call. Report its median and middle half for big winners,
middle calls and big losers. **Also:** among B's bearish calls, compare
the prior return of those that became big winners with those that did
not.

**Pre-registered reading for 1d.** If big winners' median prior return
is **at least 15 points below** the middle group's, and the Wilson or
bootstrap ranges do not overlap, report **"winners are
disproportionately rebounds"**. That points to the stock's own price
history, which the firewall allows, as an input candidate. Otherwise
report "no rebound pattern".

---

## Step 2 — did B see it? (~$6, the highest-value step)

### 2a. The classifier (write it to the file named in ground rule 3)

Given only an analyst's short read of an earnings call, return:

```
---STRUCTURED---
{
  "positive": "",        // strongest positive evidence cited: "none", "weak", "strong"
  "negative": "",        // strongest negative evidence cited: "none", "weak", "strong"
  "forwardPositive": "", // is any positive evidence about the FUTURE (guidance,
                         // bookings, pipeline, new product, margin path), not only
                         // past results? "yes" / "no"
  "discounted": ""       // does the read name positive evidence and then set it
                         // aside (priced in, one-off, not yet proven, uncertain)?
                         // "yes" / "no"
}
---END STRUCTURED---
```

With one plain-language definition per value. "Strong" means specific
and material, such as a number, a raised guide, or a named contract.
"Weak" means general or qualitative. Tell the classifier not to guess
how the stock did.

### 2b. Pre-flight — 60 calls (~$0.30)

Parse check. **P7's lesson, as a stop rule:** stop if any one field
takes a single value on more than 85% of the 60 calls. A label that
says the same thing about almost every call cannot separate them.

### 2c. All 1,217 READs, one batch

Commit `read_labels.jsonl`.

### 2d. The test, pre-registered

**Among B's non-bullish calls (score ≤ +2, draw 1),** compare big
winners with everything else on:
- (i) share with `positive = strong`;
- (ii) share with `forwardPositive = yes`;
- (iii) share with `discounted = yes`.

Report each share with its Wilson range, and the difference with a
ticker-block bootstrap range (2,000 draws, seed 11).

**Reading, fixed now:**
- **"Seen and not committed"** if (i) **or** (ii) is higher for big
  winners, with the difference's range excluding zero. B read good news
  on calls that went on to win big and did not act on it. The next step
  is a prompt candidate aimed at committing on that evidence, by analogy
  with how B fixed the bearish side.
- **"Not seen"** if neither difference excludes zero. B's reading does
  not separate future big winners from other calls. The next step is
  outside information: own price history (if 1d found rebounds), XBRL
  facts (P4), or consensus.
- (iii) is reported beside them. If (iii) is higher for winners with its
  range excluding zero, say **"seen, then talked down"**. That points to
  the prompt's caution, not its reading.

**Also report, not gated:**
- The same comparison inside B's **bullish** calls (≥ +3): big winners
  against the rest.
- The same inside B's **bearish** calls: are the 26 bearish-pile big
  winners labelled differently from the other bearish calls?

**Small numbers, stated plainly.** 118 big winners sit in the non-bullish
pile. A difference smaller than about 10 points cannot be told from
chance at that size.

---

## Step 3 — what differs? (~$2, hypotheses only)

**Contrastive pairs, same company.** For companies with at least one
big-winner call and at least one middle call on train, pair one
big-winner call with the same company's nearest middle call. Cap at 30
pairs, seeded selection.

For each pair, give the classifier-model **both transcripts**, labelled
only "Call A" and "Call B" in seeded random order. Strip the ticker,
company name where mechanically possible, and dates. Tell it that one of
the two calls was followed by a much better six months, **without saying
which**. Ask:
- which it thinks, and
- **the one concrete difference in the transcripts that drove its pick,
  stated as a mechanism a person can check.** Example: "Call A raised
  full-year guidance while Call B only reaffirmed it."

Report:
- how often it picks right, out of 30 (chance is 15);
- the list of stated mechanisms, grouped by kind;
- the mechanisms from right picks separately.

**This is a generator, never a judge** (`PROMPT_ARCHITECTURE.md` §2.6).
30 pairs cannot test anything. A mechanism on this list becomes a
candidate only if Luis vets it and a later run pre-registers it. **The
model may remember these companies' outcomes.** A mechanism that cannot
be explained in plain words is treated as recall, not insight.

---

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/winners-missed-analysis-out.md`, `.md` only. Open with:

> Of 153 train calls followed by a gain of 20+ points over the S&P, B
> scored ___ bullish, ___ neutral and ___ bearish. Before the call, those
> winners had returned a median ___ over the prior six months, against
> ___ for the middle group: **[winners are disproportionately rebounds /
> no rebound pattern]**. In B's own words on its non-bullish calls,
> strong positive evidence appeared on ___% of future big winners against
> ___% of the rest (difference ___, range ___ to ___), and
> forward-looking positive evidence on ___% against ___%: **[seen and not
> committed / not seen]**. In 30 same-company pairs the model picked the
> winner ___ times.

Then 1a–1d, 2d with both side comparisons, the step 3 mechanism list,
and costs.

**Close with what it means for the next step, both ways.** If "seen and
not committed", name the candidate it suggests, as a one-sentence change
to B. If "not seen" with rebounds, the next candidate adds the stock's
own prior six-month return as an input. If "not seen" without rebounds,
the next step is outside data (P4 XBRL or consensus). The Opus check
(`2026-09-26` discussion) can run in parallel either way.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Finish with `git push`** of `sweep/db-corpus-baseline` after the
wrap-up commit, and report the pushed hash; on failure, say so and never
force. **Budget stop:** Step 1 always runs. If Step 2's projection
breaches the cap, stop and report. Step 3 is dropped first if budget is
short.
