# Winners B missed, v3 — the classifier test, three working labels. About $2

**Run ID:** `winners-missed-v3`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/winners-missed-v3-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $2.** It classifies B's short
READ text for all 1,217 train calls. **Hard cap $4**, counted before
every `create()`. Luis approves at Step 0; record it in `progress.json`
or stop and ask.

---

## Framing

**What this run exists to answer.** Did B see good news on calls that
went on to beat the S&P by 20+ points and not act on it? And, most
directly: **do beat-and-raise calls become big winners more often, and
did B hold back on them?**

**Why v3.** Two classifier versions stopped at their pre-flights on the
85% lopsided-label rule:
- v1's "strong positive" meant "specific", and B always cites specifics.
- v2's `discounted` included "outweighed by a risk", and nearly every B
  READ names "the one genuine concern".

Both times the definition matched B's standard phrasing. On v2's
pre-flight (`wrap-ups/winners-missed-v2-out.md`), the **other three
labels spread well**: `balance` (outweighs 53%), `raised` (yes 27%) and
`beat` (yes 17%).

**v3 is v2 with `discounted` removed and nothing else changed.** The
three remaining definitions and their examples are copied **verbatim**
from `docs/prompts/diagnostics/READ_CLASSIFIER_v2.md`. Their pre-flight
has already been done, on 60 calls, so there is no new pre-flight. The
stop rule applies to the full run instead (§2b).

**Supporting context, not evidence:** in v2's 30 same-company pairs, the
model picked the winner 18 of 30 times, mostly citing a guidance raise
or a beat. That is the mechanism this run tests properly.

**Read first:** `wrap-ups/winners-missed-v2-out.md`,
`wrap-ups/winners-missed-analysis-out.md`;
`docs/prompts/diagnostics/READ_CLASSIFIER_v2.md`;
`analysis/winners_missed_analysis.py` and the driver's `--wv2` path
(extend with `--wv3`; do not fork).

---

## Ground rules

1. **Train only.** No tune, no holdout, no DB writes, no cache refresh.
2. **The classifier never sees outcomes.** Exactly as v2: only B draw 1's
   READ paragraph, with the SCORE section and structured block stripped
   and asserted absent. No ticker, date, return or group. Seeded random
   order, seed 11.
3. **Classifier file:** `docs/prompts/diagnostics/READ_CLASSIFIER_v3.md`.
   **Diff it against v2 and report the diff.** The only differences
   allowed are removing the `discounted` field (definition, examples, and
   its line in the block) and the header. Record its sha in
   `progress.json` before any call. `claude-sonnet-4-6`, Batch API,
   `max_tokens` 400, no temperature parameter.
4. **Every reading below is fixed before any number is computed.** Report,
   do not decide. Do not redefine anything in this run.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/winners-missed-v3/`. `progress.json`
first. Commit this prompt file if untracked or modified, as its own
commit. Clean tree; hard stop if `git_dirty` cannot be recorded `false`.
Classifier file and driver/analysis extensions committed before any
output. Batch id committed the instant `create()` returns. One process,
no pipe to `tail`, no background poller.

---

## Step 1 — classify all 1,217 READs (~$2)

One batch. Commit `read_labels_v3.jsonl`. Report parse failures and
`max_tokens` stops. Any above 3 → stop and report.

## Step 2 — the stop check, then the test, $0

### 2a. Stop rule, on the full set

If any field takes a single value on more than **85%** of the 1,217
calls, stop and report the distributions. Do not run 2b–2d. **Report
the distributions either way,** beside the v2 pre-flight's.

### 2b. Winners vs the rest, among B's non-bullish calls (pre-registered)

B draw 1 score ≤ +2: 118 big winners (≥ +20 points) against 864 others.
Compare four shares, each with a Wilson range, and each difference with
a ticker-block bootstrap range (2,000 draws, seed 11):
- (i) `balance = outweighs`;
- (ii) `raised = yes`;
- (iii) `beat = yes`;
- (iv) `raised = yes` **and** `beat = yes`, reported.

**Reading, fixed now** (as v2 §2d; three comparisons, so one crossing by
chance is plausible):
- **"Seen and not committed":** at least **two of (i)–(iii)** are higher
  for big winners, with the range excluding zero.
- **"Suggestive: ___":** exactly one is. Name it.
- **"Not seen":** none is.

### 2c. Beat-and-raise, directly — the decision-relevant check

Across **all 1,217** calls, split by the classifier's tags into four
groups: beat-and-raise, raised only, beat only, neither. For each group
report:
- the call count;
- the **big-winner rate** (≥ +20), with a Wilson range, against the 12.6%
  base;
- the **median six-month return** vs the S&P, with a bootstrap range;
- the **big-loser rate** (≤ −20);
- the **distribution of B's score** on draw 1 and draw 2, and the share
  scored below +3, against 80.7% below +3 across all calls.

**Pre-registered reading, fixed now, one rule.** A **"commit on
beat-and-raise" candidate is worth building** if the beat-and-raise
group's big-winner rate is higher than the "neither" group's, with the
difference's ticker-block range (2,000 draws, seed 11) excluding zero.
Otherwise it is **not worth building** on this evidence.

Beside the reading, report without gating:
- whether that group's median return is also higher than "neither";
- whether B scored it below +3 more or less often than it does overall.
  More often means B held back on exactly those calls.

### 2d. Tie-in with the pairs

Of v2's 18 right-pick pairs, how many of the winner-side calls did v3's
classifier tag `raised` or `beat`? And how many of the 12 wrong-pick
pairs' **chosen** calls? Reported only; 30 pairs test nothing.

---

## Report step

**Scope boundary: report, do not decide.** Do not write a candidate, do
not change any prompt.

`wrap-ups/winners-missed-v3-out.md`, `.md` only. Open with:

> Reading only B's own notes, a classifier found a raised outlook / a
> beat of guidance / good news outweighing bad on ___% / ___% / ___% of
> the calls B did not score bullish that went on to beat the S&P by 20+
> points, against ___% / ___% / ___% of the rest: **[seen and not
> committed / suggestive: ___ / not seen]**. Calls tagged beat-and-raise
> (___ of 1,217) became big winners ___% of the time, against ___% for
> calls with neither (difference ___, range ___ to ___), and B scored
> ___% of them below +3 (all calls: 80.7%). **A "commit on
> beat-and-raise" candidate is [worth building / not worth building] on
> this evidence.**

Then 2a–2d, and costs.

**Close with the next step, both ways.**
- **Worth building:** state the one-sentence change to B. Note that it
  runs as two draws on train (§2.3a rule 7), about $60, with the usual
  gates. Bearish bottom-191 must stay at or above 57%.
- **Not worth building:** say so plainly. The best-documented bullish
  pattern is not visible through B's notes on this corpus. The next step
  is outside data (P4 XBRL facts or consensus), or a candidate that reads
  guidance changes from the transcript directly rather than through B's
  notes. Say which of the two the evidence here favours, if either.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Finish with `git push`** of `sweep/db-corpus-baseline` after the
wrap-up commit, and report the pushed hash; on failure, say so and never
force. **Budget stop:** one batch, all or nothing. If the projection
breaches $4, stop and report.
