# State of play — 2026-09-24

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/CW96Nyoxsx4kM4B2JF1Q8r>

**Supersedes `docs/handoffs/2026-09-23-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** the first prompt change in this project's history
that held on companies it had never seen is a 50-line prompt with no rubric.
It ranks forward returns, doubles the analyst's bearish coverage at equal or
better precision, and costs a fifth of v6 per call. Through the portfolio
simulator, against v6 on the same model, it is close to a tie on final
value and **30% better on the gate's own risk-adjusted metric, in every
leave-one-ticker-out cut.** It has cleared both halves of the gate's test
for an analyst change. **Decided 2026-09-25: the analyst is improved on its
own from here, with B as the research champion and production untouched;
the allocator is rebuilt afterwards around whatever the analyst turns out
to be good at.** Start at §2.4, then §5.

**Updated three times** — after the end-to-end check, after the same-model
comparator and leave-one-out runs corrected it, and on 2026-09-25 when §5
became a decided plan rather than a recommendation. The reading version is
republished to the same link.

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

**P6B end-to-end check ($7.75, simulator).** The gate's secondary test,
never before run on any candidate: B's score fed through the settled
allocator on the ALL16 corpus, against v6 and against v6 stripped to its
per-call verdicts. `wrap-ups/P6B-end-to-end-check-out.md`. **B exceeded
the check.** See §2.4.

**P6B confound and concentration ($3.56).** v6 re-scored on the same
model as B and fed through the same overlay (**A0′**), plus all sixteen
leave-one-ticker-out cuts. `wrap-ups/P6B-confound-and-concentration-out.md`.
**Corrects §2.4:** most of the end-to-end gap was the model, not the
prompt; the prompt's share is thin on final value and robust on drawdown.

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

### 2.4 The end-to-end check — B through the allocator, corrected

Settled configuration, 195 events, seed 0, phase-averaged. Every drawdown
names its ruler. **The fair comparator is A0′**: v6 re-scored on
`claude-sonnet-4-6` (B's model) and fed through the same overlay. The
archived v6 verdicts (R, A0) come from a retired model and cannot serve as
a baseline for anything new.

| cell | what it is | final value | phase range | drawdown, daily | **gain per point of drawdown** |
|---|---|---|---|---|---|
| R | v6 archive, the published reference | $184,819 | $179,945–$189,914 | 23.46% | $3,616 |
| A0 | v6 archive through the overlay | $183,780 | $175,269–$192,981 | 23.91% | $3,504 |
| **A0′** | **v6 on sonnet-4-6 through the overlay — the comparator** | **$200,214** | $194,407–$206,925 | **20.12%** | **$4,981** |
| **B3** | **B's score, ≤ −2 Trim / ≥ +3 Add / else Hold** | **$210,351** | $207,495–$214,227 | **16.97%** | **$6,503** |
| B2 | B's score, Add cut at +2 | $242,415 | $237,175–$249,799 | 19.77% | $7,204 |

"Gain per point of drawdown" is `PROMOTION_GATE.md` §3.2's end-to-end
metric — return per unit of max drawdown, locked 2026-05-23 — computed here
as (final − $100,000) ÷ daily-marked drawdown. **It was not in the run's
pre-registration**, which used final-value phase ranges; it is stated here
because it is the metric the gate names, and the omission was mine.

**The split of the original $26,570.** A0′ − A0 = **$16,433 is the model**
(62%); B3 − A0′ = **$10,137 is the prompt** (38%). On final value B3 is
formally above A0′'s phase range, by $569 at the closest phases — a thin
margin.

**Leave-one-ticker-out, sixteen cuts.** On final value the B3 − A0′ gap
stays positive in 15 of 16 and **flips to −$2,279 without FSLR**; without
NVDA it is +$2,366. **On daily drawdown B3 is better than A0′ in all
sixteen** (15–17% against 19–21%). **On gain per point of drawdown B3 is
ahead in all sixteen**: without FSLR $5,901 vs $4,783; without NVDA $4,120
vs $3,054.

**Reading.** On final value, B and v6-on-the-same-model are close to a tie,
and the tie depends on one name. On risk, B wins in every cut. On the
gate's own end-to-end metric, B is ~30% better and never behind. The
mechanism is the one the first end-to-end run showed: B's 45 Trims landed
on stocks that fell a median 24% (v6's: −6%), 35 of them speculatives; B
made 7 speculative Adds (median +24%) where v6 made 29 (median −14%). B
deploys more slowly — 61 funded Adds vs 97, 34% average cash — and is paid
for it in drawdown.

**Two findings that change the design.** The trend layer is worth
**+$1,039** on this corpus (R minus A0), inside R's own phase spread.
`recommended_size` was null in every overlaid cell at no visible cost.

**Two things noted, not concluded.** v6 on the newer model is itself worth
$16k on this window; both models post-date the window, so the run cannot
separate "reads calls better" from recall the older model lacked, and the
same caveat covers B. And FSLR — the diagnostic case in the 2026-09-05
winners-runway thread, the name the allocator sized wrong — is the name B
sized right ($23.5k held at the end vs A0′'s $12.5k). One name; a note.

**What it does not show.** One window, one seed family; the band is the
phase spread. Recall is the documented limitation of
`DESIGN_PRINCIPLES.md` §4 and applies to every cell equally. **The
analyst-direct evidence (§2.1–2.3) is untouched by the correction**: train,
tune and pooled v6 baselines were already scored on `claude-sonnet-4-6`;
the confound existed only on the simulator corpus.

## §3 What this changes

1. **The working analyst candidate is the minimal prompt.** `P6B-minimal`,
   sha `d1fa5e53…`, registered as a candidate in `VERSION_REGISTRY.json`.
   Not promoted; see §5. It has cleared both halves of the gate's test
   for an analyst change (`PROMOTION_GATE.md` §4): PROMOTE on the
   analyst-direct metric on two splits, and no regression — an
   improvement — on the end-to-end metric against the same-model
   comparator.
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

## §5 Decided 2026-09-25 — improve the analyst on its own; rebuild the allocator after

**The reasoning, in Luis's words.** The benchmark-beating result was mostly
the allocator's; v6 is barely better than luck overall, with one real skill
(bearish calls); the minimal prompt and the newer model have now shown the
analyst *can* be improved, and by how much is unknown. Developing both
layers at once for five months hid which one was adding value. So: improve
the analyst alone, on its own ruler, and build the allocator around whatever
it turns out to be good at.

**5.1 Bookkeeping, $0, first.** Record the `data/gate_ledger.json` entry for
`P6B-minimal` vs `v6` (§2.2a prompt change: analyst-direct PROMOTE on two
splits; end-to-end no regression against A0′ in sixteen cuts, +30% on gain
per point of drawdown). **Make B the research champion** — the incumbent
every future candidate is compared against — in the registry. **Production
stays on v6**; cut-over is a separate, later decision and is not on this
list. Correct the flip-count rules (`PROMPT_ARCHITECTURE.md` §2.4/§2.5).
Record that the portfolio-side comparator is A0′ from here on.

**5.2 B's noise floor, ~$15, before any B-derived candidate.** v6 disagrees
with itself on one call in six. B's run-to-run consistency has never been
measured. A paired re-score of B on train, per stratum, is the floor every
P7/P8 flip count is netted against. Without it the first candidate result is
unreadable.

**5.3 The campaign — three open questions, one candidate each, in this
order.** Each runs train → tune on B's ruler (rank correlation across all
calls; money; bearish and bullish precision against base rates), against B
as incumbent, pre-registered in `PROMPT_ARCHITECTURE.md` §2.2 before it
runs.

| question | candidate | what it changes |
|---|---|---|
| **Bullish discrimination** — no prompt has any | **P7, three voices, from B**: what the CFO's numbers say, what the CEO claims beyond them, what the analysts actually pressed on; score the gap | the expectations-gap question asked of the transcript alone |
| **Magnitude below +1** — B's score is flat from −4 to +1 | **P9, expected return**: ask for an expected six-month return vs the S&P in percent, with a range, instead of a −5..+5 label | severity becomes a number; tested on rank correlation *and* calibration (do the −20% calls fall ~20%?) |
| **The reader** — the model moved v6 by $16k, the prompt by $10k | **model gate on B** (§2.2b, equivalence hurdle): a newer or larger model on the unchanged minimal prompt | the second lever; recall exposure rises with newer models, so tune/holdout discipline matters more, not less |

Then **P8** (auto-iterate from B, generator never judge, the 2026-09-24
constraints) as the hypothesis source, and **P4** (XBRL facts) last, once
the prompt's shape has settled.

**5.4 One tether to the allocator, ~$8 per promoted candidate.** Not
co-development: the end-to-end check run once per research promotion,
against A0′, as a smoke test that the signal is still convertible to
dollars by *some* allocator. The current allocator's preferences (it pays
for bearish precision and slow deployment, ignores bullish ranking beyond
the starter) are facts about the old allocator and are not design targets.

**The end-to-end check can veto a candidate; it never picks one.** (amended 2026-09-26)

**5.5 Holdout discipline.** B has had its one look at tune. Every
B-derived candidate runs train → tune. **Holdout stays locked until the
campaign produces a final candidate, and gets one look.**

**P6D (the allocator fields) is deferred**, not dropped: it is the first
task of the allocator rebuild, and the rebuild consumes a continuous score
with thresholds on the allocator side.

## §6 Queue, after 2026-09-25

| # | candidate | status |
|---|---|---|
| — | ledger entry; B = research champion; flip-count rules; A0′ as comparator | **next, $0** (§5.1) |
| — | B's noise floor (paired re-score, train, per stratum) | **next, ~$15** (§5.2) |
| P7 | three-voices rubric, from B — bullish discrimination | next candidate (§5.3) |
| P9 | expected-return output, from B — magnitude and calibration | named (§5.3) |
| — | model gate on B, §2.2b equivalence hurdle | named (§5.3) |
| P8 | auto-iterate as generator, from B, with the 2026-09-24 constraints | after P7/P9 |
| P4 | tier-conditioned financial facts (XBRL) | after the prompt shape settles |
| P6D | B plus the structured fields the allocator needs | **deferred to the allocator rebuild** |
| P5 | peer read-through | not started |
| P1 | commit to bearish | **closed** — superseded by B |
| C | v6 with score | **closed** — same signal, 66% more cost |
| P2 | post-call reaction | downgraded (09-23), blocked on R3 |

## §7 Open, not scheduled

- The pooled v6 swap-median discrepancy (7.70 vs 8.7).
- Bullish-side signal: none of B, C or v6 has any. P7 is the first candidate
  aimed at it (the gap between what the CFO reported and what the CEO
  claimed).
- Severity grading below +1: B's score is flat there. Whether a prompt can
  grade how bad a bad call is remains untested.
- Settle §3.1a R3; consensus vendors (stalled); ratchetTranche null on 26%
  of bearish calls; terminal-value grading; BK/BNY history; trend-layer
  override rate; Rule 3 guard; the state dashboard.

**Closed (amended 2026-09-26).** The lucky-cached-draw question (35 decisive flips, p=0.09; ~150 would decide it, ~$40) is closed: v6 is no longer the comparator, and its only consequence (B's result is conservative) is already recorded.

## §8 Commits this week

`aee70da` P6/P7/P8 registered · `647bae9` P6 prompt and candidates ·
`15c8331`…`58b33cc` P6 run, driver, analysis, wrap-up ·
`f9cc43f`…`ea20466` P6B tune run and wrap-up ·
`57f75d1`…`522763b` P6B end-to-end check and wrap-up ·
`f7e1d98`…`16078ce` P6B confound and concentration.
