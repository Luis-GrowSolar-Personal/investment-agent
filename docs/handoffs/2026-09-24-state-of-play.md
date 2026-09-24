# State of play — 2026-09-24

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/CW96Nyoxsx4kM4B2JF1Q8r>

**Supersedes `docs/handoffs/2026-09-23-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** the first prompt change in this project's history
that held on companies it had never seen is a 50-line prompt with no rubric.
It ranks forward returns, doubles the analyst's bearish coverage at equal or
better precision, and costs a fifth of v6 per call. It also emits nothing the
allocator consumes. The next action is the gate's own end-to-end check, which
has never been run on any candidate: about $16. Start at §2, then §5.

---

## §0 — Defined terms

Read this once. Several read as their own opposite.

**The three prompts this document compares**

- **v6.** Today's promoted analyst prompt: ~190 lines of rubric (thesis
  health, stumble taxonomy, mitigation test, blind spots) ending in a decision
  matrix that emits Add / Hold / Trim / Exit. **Arm A.**
- **The minimal prompt.** ~50 lines, no rubric. States the objective (beat or
  lag the S&P 500 over the next two quarters), restricts the model to the
  transcript, asks one framing question, and asks for a **score**. **Arm B.**
  File: `docs/prompts/candidates/EVALUATION_PROMPT_P6B_minimal.md`.
- **The score arm.** v6 with only its last step changed: the same rubric, but
  it ends with a score instead of the matrix. **Arm C.** Indistinguishable
  from B on train; not taken to tune.

**The kinds of answer**

- **Score.** An integer from −5 (strong conviction the stock lags the S&P over
  six months) to +5 (strong conviction it beats it). 0 with `noRead` means
  "no basis for a view"; ±1 means a weak view.
- **Mapping / thresholds.** How a score becomes one of the three old answers.
  **Pre-registered, not tuned:** score ≤ −2 is **bearish**; score ≥ +3 is
  **bullish**; −1 through +2 is **neutral**. The bullish cut sits at +3, not
  +2, because +2 is the model's resting score and carried no edge on train.
  Thresholds are an allocator-side decision; the analyst emits the score.
- **Bearish / bullish / neutral** for v6 mean Trim-or-Exit / Add / Hold.

**The kinds of number**

- **Rank-ordering.** Does a higher score go with a higher return? Reported as
  a rank correlation from 0 (the score tells you nothing about the order of
  returns) to 1 (perfect ordering). A value near 0.13 is weak and real.
- **Money.** How far the stock actually moved, in points ahead of or behind
  the S&P, from the **tradeable entry** (the first close *after* the call)
  over 182 days. **The measure of record since 2026-09-20.**
- **Accuracy.** Whether the stock finished more than 5 points ahead of or
  behind the S&P. A footnote since 2026-09-20; reported for continuity.
- **Swap.** Sell what is flagged bearish, buy what is flagged bullish. Its
  worth is the median return of the bullish bucket minus that of the bearish
  bucket, in points.
- **Base rate / edge.** How often an outcome happens across all calls,
  whatever the analyst said; edge is hit rate minus base rate, in points.
- **Ticker-block range.** A 95% range from resampling whole companies, not
  calls. **If it includes zero, the data cannot tell the two things apart.**
- **Noise flip.** v6, asked the same question twice, answers differently on
  about one call in six. A **net** flip count subtracts the flips noise would
  produce anyway.
- **Train / tune / holdout.** 55 companies the candidates were built against
  (1,217 calls); 51 fresh companies each gets **one look** at (1,169 calls);
  53 companies locked and never scored.

**Allocator terms — unchanged, for orientation only.** The settled
configuration is `swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp,
`pooled`, `per_event_date`: trade once a month, put money only into names
that just reported, fund buys by trimming a holding, and never move one
position by more than 2.5 points of portfolio in a session (a 5% position may
end the month anywhere from 2.5% to 7.5%). Reference result $184,819 on
$100,000, daily-marked drawdown 23.46%. See the 2026-09-19 allocator
document for the full glossary; nothing here touches it.

**Plain-English summary before any identifier appears.** For five months
every attempt to improve the analyst added information to its prompt, and
none paid. This week the prompt's *shape* was changed instead. A short prompt
that asks for a number instead of a verdict turned out to carry more usable
signal than the long rubric — not because it reads better, but because the
rubric's final step was throwing the reading away. Checked on fresh
companies, it held. It now needs to be tested against the portfolio
simulator, because a score is not yet something the allocator can act on.

---

## §1 What changed since 2026-09-23

Two paid runs, $126 total, both complete.

**P6, the output-format round ($88, train).** Three arms on 1,217 train
calls: v6, the minimal prompt, and v6-with-a-score. Registered 2026-09-24 in
`PROMPT_ARCHITECTURE.md` §2.2 with predictions written down first.
`wrap-ups/P6-output-format-round-out.md`.

**P6B on tune ($38).** The minimal prompt's one permitted look at the tune
companies, with four pass/fail conditions fixed before the run.
`wrap-ups/P6B-tune-confirmation-out.md`. **All four held.**

**Also this week:** P7 (three-voices rubric) and P8 (auto-iterate loop, with
four constraints against fitting to remembered outcomes) were registered as
named follow-ons. The consensus-vendor thread is unchanged and still stalled.

## §2 The evidence

### 2.1 The minimal prompt against v6, both splits

| | v6, train | B, train | v6, tune | B, tune |
|---|---|---|---|---|
| rank correlation (score vs return) | 0.070 (3 answers coded −1/0/+1) | **0.130** (0.051–0.208) | 0.080 | **0.140** (0.072–0.198) |
| bearish calls | 93 | **191** | 84 | **161** |
| bearish precision (right when it said bearish) | 58.1% | **62.3%** | 59.5% | **60.9%** |
| bearish median return vs S&P | −9.46 | −10.39 | −8.46 | −7.71 |
| swap median, points | 8.12 (−2.4 to 18.0) | 8.92 (4.1 to 15.3)* | 7.75 (−5.5 to 10.9) | **8.34 (1.5 to 12.9)** |
| completion length, tokens | 2,428 | **514** | 2,462 | **511** |
| cost per call | $0.038 | **$0.024** | | |

*train swap at the +2 mapping; the +3 mapping was fixed before tune.

**Pooled, 2,386 calls, 106 companies:** B rank correlation **0.135 (0.087 to
0.184)**; B swap median **10.50 (6.30 to 13.64)**; v6 swap median 7.70
(0.51 to 12.30).

### 2.2 The four tune conditions, pre-registered, one line each

1. Rank correlation range excludes zero — **held** (0.072 to 0.198).
2. Bearish coverage ≥ 1.5× v6's with precision no more than 5 points worse —
   **held** (1.92×, +1.3 points).
3. Swap median range excludes zero — **held**, narrowly (lower end 1.46).
4. No old-ruler regression — **held** (gap +4.07 vs v6's +2.64; non-gating).

### 2.3 Where the signal is, and where it is not

**The calls v6 called neutral and B called bearish are the finding.** Train:
112 such calls, right 62.5% against a 44.7% base rate. Tune: 98 such calls,
right 58.2% against 48.3%. Same shape on two independent sets of companies.
Those calls were sitting in v6's Hold pile, which carries zero edge on both
splits, because the decision matrix maps *Intact + no stumble → Hold* after
the model has read the call. The reading was there; the matrix discarded it.

**The rubric adds nothing measurable.** Arm C — v6's full rubric ending in a
score — ranked returns at 0.140 on train, indistinguishable from B's 0.130
(paired difference 0.010, range −0.034 to +0.054). The signal came from the
output format, not from 190 lines of instruction.

**The bullish side is still nearly empty.** At the +3 cut B's bullish bucket
is 242 tune calls at 41.3% precision, median +0.63 — small and positive. At
+2 it is the model's resting answer and carries nothing. The analyst can say
what is going wrong; it still cannot say what is going right.

**The score does not grade severity.** Tune buckets from −4 through +1 have
medians between −4.6 and −8.3 with no ordering among them; the ordering is
carried entirely by +2, +3 and +4 beating everything below. B separates
"better" from "the rest." It does not yet rank how bad the bad calls are.

**Both prompts default mildly positive.** +2 and +3 are the most common
scores on both splits. Under the +3 cut, B's neutral pile is 65% of tune
calls — *larger* than v6's 59%. That is a consequence of the mapping, and it
is the mapping under which the money range clears zero; the +2 cut's range
touches zero (−0.16 to 10.33).

## §3 What this changes

1. **The working analyst candidate is the minimal prompt.** `P6B-minimal`,
   sha `d1fa5e53…`, registered as a candidate in `VERSION_REGISTRY.json`.
   Not promoted; see §5.
2. **P7 and P8 iterate from B, not from v6.** Fifty lines is the starting
   point. Any future rubric must earn its length against this control.
3. **P1 is closed.** It pushed v6 toward bearish by lowering the evidence
   bar; B reaches the same coverage by changing the output format, without
   the precision loss P1 predicted for itself.
4. **Arm C is closed** on train evidence: same signal as B at 66% more cost.
5. **The 09-23 queue is superseded.** §3.1 (neutral pile) and §3.3 (severity)
   there are answered by this round: the neutral pile held signal and the
   format released it; severity grading is still absent and is now a
   measured gap rather than a hypothesis.

## §4 The instrument — carried, with three additions

- **Noise floor is ~17%, not 12.8%.** Tune 17.7% (13.5–23.0), train 16.7%,
  Test 4's 12.8% inside both ranges. v6 disagrees with itself on one call in
  six.
- **v6's cached baseline leans lucky.** Among noise flips where exactly one
  answer was right, the cached call won 23 times and the fresh call 12
  (p=0.09, 35 decisive flips). Not settled. If real, every prior comparison
  flattered v6 slightly and B's result is conservative. **Nothing in §2.2
  depends on it** — conditions 1–3 do not use v6's accuracy.
- **Flip-count rules in `PROMPT_ARCHITECTURE.md` §2.4/§2.5 are still
  computed on raw flips** and still uncorrected. Every flip figure this week
  was reported raw and net; the file was not edited.
- **A 1.0-point discrepancy** in the pooled v6 swap median (7.70 here vs 8.7
  in the 09-23 document) is unreconciled. The mean reproduces.
- The 177-bearish-call resolution limit for subset questions stands; the
  rank test on all calls is how this round got around it.
- Paramount excluded on train (corrupt prices); WOLF, SPWR, BNY (no
  transcripts) excluded on tune. Dividends ignored. Sector-relative grading
  unresolved.

## §5 Next action — the end-to-end check, ~$16

**B cannot be promoted on §2 alone**, for a reason that is not about the
evidence: it emits `score`, `noRead`, `summary` and `wrongIf`, and nothing
else. The allocator consumes `recommendation`, `thesisHealth`,
`recommendedSize` and `capPercent`; the trend layer consumes `thesisHealth`,
`credibilityDelta`, `mitigationCapabilityTrackRecord`, `freshMoneyAllocation`.
None of those exist in B's output. A candidate that improves the analyst's
signal and disconnects the layers below it has not yet been shown to improve
the portfolio.

`PROMOTION_GATE.md` §4 already says what to do: **an analyst change is gated
on the analyst-direct metric and checked for no-regress on the end-to-end
portfolio metric.** The second half has never been run on any candidate.

**The run, in one paragraph.** Score the ALL16 simulator corpus (~660
transcripts, on disk, the settled-configuration inputs) with B — about $16
at B's measured cost. Map scores to actions with the pre-registered
thresholds (≤ −2 Trim, ≥ +3 Add, else Hold). Run the settled configuration
exactly as `resolve-open-four` did, phase-averaged, daily ruler, and compare
final value and drawdown against **$184,819 / 23.46%** (state of play
2026-09-05 §2). Also run the swapped-thresholds sensitivity (+2 bullish cut)
as a second cell, and report the deployment rate: fewer Adds under the +3
cut means slower deployment, which the 2026-09-05 document showed is the
mechanism that governs this allocator.

**Pre-registered reading.** B's portfolio result within Rule 2's overlap of
v6's is a pass (no-regress); above it is a finding worth its own document;
below it by more than the phase spread means the score does not translate to
sizing under this allocator and the design question is how B's score and
v6's structural fields coexist — which is the next candidate either way.

**Two things to settle in the same session, both $0:**

- Correct the flip-count rules (§4.2 of the 09-23 document). One edit.
- Write the design note on which v6 fields the allocator actually needs
  versus which it merely receives. The `recommendedSize` field is already
  known to be inert at X=2.5pp; `ratchetTranche` is known to be
  self-reported and unknowable per call. The list may be shorter than it
  looks.

## §6 Queue, after this week

| # | candidate | status |
|---|---|---|
| — | **B end-to-end check** (§5) | **next, ~$16** |
| P6D | B plus only the structured fields the allocator needs, tested for no change in rank correlation | named; depends on the §5 design note |
| P7 | three-voices rubric, from B | named, not run |
| P8 | auto-iterate as generator, from B, with the 2026-09-24 constraints | named, not built |
| P4 | tier-conditioned financial facts (XBRL) | unblocked, not started |
| P5 | peer read-through | not started |
| P1 | commit to bearish | **closed** — superseded by B |
| C | v6 with score | **closed** — same signal, 66% more cost |
| P2 | post-call reaction | downgraded (09-23), still blocked on R3 |

## §7 Open, not scheduled

- Simulate the allocator with B's scores — now §5, no longer open.
- A larger noise arm to settle the lucky-cached-draw question (35 decisive
  flips leave p=0.09; ~150 would decide it, ~$40).
- The pooled v6 swap-median discrepancy (7.70 vs 8.7).
- Bullish-side signal: none of B, C or v6 has any. P7 is the first candidate
  aimed at it (the gap between what the CFO reported and what the CEO
  claimed).
- Severity grading below +1: B's score is flat there. Whether a prompt can
  grade how bad a bad call is remains untested.
- Settle §3.1a R3; consensus vendors (stalled); ratchetTranche null on 26%
  of bearish calls; terminal-value grading; BK/BNY history; trend-layer
  override rate; Rule 3 guard; the state dashboard.

## §8 Commits this week

`aee70da` P6/P7/P8 registered · `647bae9` P6 prompt and candidates ·
`15c8331`…`58b33cc` P6 run, driver, analysis, wrap-up ·
`f9cc43f`…`ea20466` P6B tune run and wrap-up.
