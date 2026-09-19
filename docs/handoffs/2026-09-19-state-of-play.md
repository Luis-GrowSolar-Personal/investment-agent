# State of play — 2026-09-19

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/KzFqjsAEiSWaM6vU7qYGiX>

**Supersedes `docs/handoffs/2026-09-17-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** P1 was the next action and it rested on a premise
that has now been tested and failed. The analyst has no usable way to tell its
strong bearish calls from its weak ones, so adding more bearish calls would
arrive as trim pressure nothing downstream can sort. A decision is required
before anything is spent. Start at §5.

---

## §0 — Defined terms

Read this before anything else. Several of these read as their own opposite.

**The kinds of thing being measured**

- **Bearish call.** A call where the analyst's own output says *Trim* or *Exit*.
  It makes one on roughly 1 call in 13.
- **Base rate for bearish.** How often the stock actually underperformed the
  S&P 500 by more than 5 points over the following two quarters — across *all*
  calls, whatever the analyst said. This is what happened, not what was
  predicted: 44.9% on train, 48.4% on tune, 46.6% pooled.
- **Hit.** The call matched what happened.
- **Dead band.** A move within ±5 points of the benchmark counts as neither
  bullish nor bearish — it is graded as though the right answer was "hold."
- **Benchmark-relative 2-quarter return.** The stock's return minus the S&P
  500's, from the call date to about six months later.

**The two things that get confused, and this document depends on the difference**

- **Precision — how often it is right when it speaks.** Of the times the
  analyst said bearish, the share that turned out right. Currently ~60%.
- **Coverage — how often it speaks at all.** Of everything it could have
  called, how often it is willing to say bearish. Currently ~8%, which works
  out to catching roughly 1 in 9 of the declines that actually happened.

  These move in opposite directions. Pushing the analyst to call bearish more
  often raises coverage and lowers precision, because the extra calls come from
  thinner evidence. That trade is the whole subject of §2 and §5.

**The new term this round introduces**

- **Strength axis.** A field the analyst already emits alongside a bearish call
  — how it labels the call, how bad it says the thesis is, how many warning
  flags it raises, how deep a cut it wants — that might separate its better
  bearish calls from its worse ones. If one existed, the allocator could trim
  hard on strong calls and lightly on weak ones. §2 is the test of whether any
  of them does. None does.
- **Direction held / reversed.** An axis was tested on train first, then on
  tune. "Held" means the same bucket came out on top both times. "Reversed"
  means the bucket that looked best on train looked worst on tune — which is
  what you see when a field carries no signal and you are reading noise.

**The portfolio rules referenced later**

- **Type A / Type B.** Single-driver positions (35% cap) and multi-driver
  platform positions (50% cap).
- **Graduated exit ratchet.** Weakening → trim to cap; no improvement after a
  quarter → trim 40% more; second quarter → 3%; third → exit. Tracked per call
  in a field called `ratchetTranche`. §6 reports a problem with it.
- **The firewall.** The analyst never sees portfolio or position data. The
  allocator never sees transcripts. They communicate only through the
  structured score. This is why the analyst cannot know which position is large
  and why sizing must be done downstream.

**Plain-English statement of where things stand, before any identifier appears**

The analyst is right about 60% of the time when it says a stock will
underperform, against a 46.6% rate of that happening anyway. It only says it
about once every thirteen calls. The plan was to make it say so more often,
accepting that the extra calls would be less reliable, on the theory that the
layer that knows position sizes could lean lightly on the weak ones. That
theory has now been tested. The analyst gives that layer nothing to lean on.

---

## §1 Where the project stands

Nothing was spent since 2026-09-17. One free diagnostic ran.

- **The measuring instrument is unchanged and still trustworthy.** Corpus of
  164 companies, three-way split (57 train / 54 tune / 53 holdout), holdout
  locked and hashed and untouched.
- **v6 remains baselined on both train and tune**, same model, apples to
  apples. Those figures did not move.
- **Q2 ran at $0** — no model calls, read-only analysis of the two eval caches
  already on disk. It reproduced all three reference figures exactly before
  computing anything, which is the strongest evidence yet that the joined
  scoring path is sound.

Two baselines cost **$92.24**. A prompt iteration round remains ~$47.

### What v6 scores — carried forward unchanged

| | train (56 cos, 1,236 calls) | tune (51 of 54, 1,168 calls) |
|---|---|---|
| accuracy | 30.3% | 28.3% |
| gap over luck | +2.48 points (95% −0.06 to +5.08) | +2.64 points (95% 0.21 to 5.00) |
| bearish calls made | 103 (8.3%) | 84 (7.2%) |
| …and right | 60.2% | 59.5% |
| base rate for bearish | 44.9% | 48.4% |

Pooled (2,404 calls, 107 companies): **+2.53 points, 95% +0.79 to +4.19 —
excludes zero.** Legitimate for v6 only, which was never selected using train.

---

## §2 What Q2 found, and it changes the plan

**The question.** Within v6's existing bearish calls, does any field the
analyst already emits separate the right calls from the wrong ones?

**The answer is no.** Six axes were testable. One held its direction on tune.
That is fewer than chance would produce.

### Why "one axis survived" is not a result

If none of these fields carried any signal at all, each one still has a 50/50
chance of pointing the same way on tune as on train, purely by luck. Across
six usable axes, pure chance predicts about **3** would appear to hold.

**One did.** The panel came in below what nothing would produce. There is no
sense in which this is a set of results with one winner in it.

| | |
|---|---|
| usable axes tested | 6 |
| expected to "hold" if every field is meaningless | ~3 |
| actually held | 1 |

### The one that held does not hold up either

The surviving axis was credibility direction — whether the analyst flagged
management credibility as worsening. Pooling both splits, which is the most
generous reading available:

| | calls | right | |
|---|---|---|---|
| credibility worsening | 133 | 84 | 63.2% (range 55–71) |
| not worsening | 54 | 28 | 51.9% (range 39–65) |

An 11.3-point gap whose 95% range runs **−4.3 to +27.0**. It crosses zero. Even
given the best possible treatment, it is not distinguishable from no effect.

**Do not build allocator sizing on credibility direction.** The 2026-09-18
wrap-up described it as "one real if modest lever." That reading is withdrawn
here.

### The full panel

| axis | train | tune | verdict |
|---|---|---|---|
| Exit vs Trim | Exit used once | Exit never used | no second bucket |
| Broken vs Weakening | Broken used once | Broken used once | no second bucket |
| Weakening vs Intact thesis | +24.1 points | −3.4 points | **reversed** |
| number of warning flags raised | +29.6 points | −20.8 points | **reversed** |
| kind of problem (structural / execution / discovery) | structural best | structural worst | **reversed** |
| core business mechanism impaired | +26.9 points | reversed | **reversed** |
| how deep a cut is recommended | −18.6 points | reversed again | **reversed** |
| credibility worsening | +10.3 points | +12.9 points | held, but see above |
| consecutive-deterioration tranche | — | — | excluded, 26% missing |

Note the shape of the reversals. Five axes did not merely fail to separate —
they **pointed the wrong way on fresh companies**, several of them by 20 points
or more. Anything that swings that far between two halves of the same corpus is
being read off noise, and none of them can be used for sizing as they stand.

### The finding underneath the finding: the analyst has a collapsed vocabulary

This is the part worth carrying forward, and it was not what the run set out to
look for.

Across **187** bearish calls in both splits:

- it said **"Exit" once**;
- it said the thesis was **"Broken" twice**;
- and on **89 of them — nearly half — it recommended a Trim while calling the
  thesis Intact.**

The analyst has a four-level recommendation scale and a four-level thesis-health
scale. For bearish calls it uses one level of each, and pairs it about half the
time with a thesis judgment that contradicts the direction of the call.

**That is not a missing signal. It is an unused vocabulary.** The reason no
strength axis separates may simply be that the analyst never says anything but
"Trim / Weakening," so there is nothing to sort on. A field cannot carry
gradations the prompt never asks it to express.

It also means the Trim-with-Intact-thesis population — half of all bearish calls
— has never been characterized. Those are presumably valuation or cap trims
rather than deterioration calls. Whether they are a different animal from the
Weakening trims is not known.

---

## §3 What this does to the candidate queue

**P1 is not refuted. Its supporting argument is.**

P1 ("commit to bearish when the evidence supports it") buys coverage and pays
in precision. The case for accepting that trade was that the allocator, which
knows position sizes, could sort the weak calls from the strong ones and size
its trims accordingly. Q2 says it cannot. There is nothing to sort on.

Run P1 as it stands and the additional bearish calls arrive as undifferentiated
trim pressure, landing on large positions exactly as hard as on small ones —
the outcome the coverage objective was specifically meant to avoid.

**P1 remains pre-registered in `PROMPT_ARCHITECTURE.md` §2.2 and is unchanged.
This document does not reorder the queue.** That is a decision, and it is
recorded as open in §5.

### The candidate Q2 implies, not yet registered

Make the analyst grade severity when it goes bearish, and only then run P1.

It has an awkward property that has to be faced before anyone registers it:
changing a call from Trim to Exit does not change its **direction**, so such a
candidate flips **zero** calls in the graded sense. **The existing ruler cannot
see it at all.** Its success criterion would not be accuracy. It would be "re-run
Q2 and the severity axes become real" — a different kind of test from anything
in the queue, needing its own pre-registration and its own gate language.

That is a design question, not a scheduling one, and it is open.

---

## §4 The instrument — carried forward, unchanged

- **Detectable effect is about 5 points** on ~1,200 calls. Below that, a result
  is not distinguishable from noise.
- **A paired comparison lives entirely on the calls that changed answer.** A
  change flipping 40 calls cannot gain more than 3.2 points even if every flip
  is right. Flip-count table: `PROMPT_ARCHITECTURE.md` §2.4.
- **The ruler grades one call at a time and cannot see exit timing.** Ideas that
  fire between calls need the simulator.
- **Three ruler questions remain open and none blocks anything**
  (`PROMOTION_GATE.md` §3.1a): dead-band width (R1), magnitude weighting (R2),
  grading-window placement (R3). R3 must be settled before P2.

**Q2 adds one instrument lesson.** A bearish-only diagnostic runs on ~187 calls,
not ~1,200. Buckets of 20–90 carry ranges of ±10 to ±21 points. Anything
measured on a subset of the bearish calls needs confirmation on the other split
before it means anything, and a 20-point train-only spread should be assumed to
be noise until tune says otherwise. Four of them were.

---

## §5 Next action — a decision, not a run

**Nothing should be spent until this is settled.** The three options:

1. **Run P1 anyway**, accepting that the extra bearish calls cannot be sorted
   downstream and will be acted on uniformly. Cost ~$47 plus a $6 pre-flight.
   Buys coverage now; defers the sizing problem.
2. **Design the severity-grading candidate first** (§3), run it, re-run Q2 to
   see whether the severity fields became real, then run P1 on top. Slower,
   more expensive overall, and needs new gate language because the current
   ruler is blind to it.
3. **Reopen magnitude weighting (`PROMOTION_GATE.md` §3.1a R2) instead.** Q2
   asked whether the *analyst* can rank its own calls. R2 asks whether the
   *scorer* should stop counting every call equally. If the objective is
   protecting large positions, R2 is closer to the target than either prompt
   candidate, and it costs no model calls.

**Also still runnable today, unaffected by Q2 and needing no new data:** P3, the
thesis/guidance ledger — score last quarter's promises at this quarter's call,
1,184 usable calls already on disk.

---

## §6 Standing caveats, carried

- **Model confound.** Everything is `claude-sonnet-4-6`. v6's original
  40.4%/39.6% came from `claude-sonnet-4-20250514`, retired 2026-06-15. Any
  weakness *or* the positive gap may be the model, not the prompt. Both
  baselines share the model, so train-vs-tune is paired; anything compared to
  the legacy figures is not.
- **The gap is a cheap proxy for dollars, and imperfect.** It counts every call
  equally; the portfolio does not. Bridge is ~$5,825 per point (Test 1, fragile).
  §3.1a R2 proposes fixing this — see §5 option 3.
- **WOLF and SPWR are ungradable** and must be excluded **entirely**, every
  call, not only the ones missing price data. Q2 established that partial
  exclusion silently inflates the tune bearish count from 84 to 97. NOVA,
  previously listed as affected the same way, **does not appear in either eval
  directory at all** — that note is withdrawn pending investigation.
- **`analysis/data/price_cache.json` is a trap and every future prompt must
  avoid it.** It is a stale 66-ticker cache from an earlier corpus era and
  covers almost none of the current corpus. The baselines were scored against
  `analysis/data/corpus_v2/scorer_price_cache_v1.json` (172 tickers). The
  2026-09-17 prompt named the wrong one and Q2 caught it. **Name the corpus_v2
  cache explicitly in every prompt from here on.**
- **The ratchet may not be recording.** `ratchetTranche` is null on **26% of
  bearish calls** (52 of 200). The graduated exit ratchet is Key Design
  Decision #3. A quarter of bearish calls not recording a tranche suggests the
  rule is not doing what the spec says. Not investigated. See §7.
- **Sector-relative grading (F2) unresolved**; everything is benchmarked to SPY.
- **Seven instances now** of one failure shape: a check or artifact built
  against one set of keys while the consumer reads another. Q2 contributed the
  seventh — its own first draft computed the base rate over the bearish-predicted
  subset, which is arithmetically identical to precision, and printed 60.2% for
  both. Caught before any axis was computed.

---

## §7 Open, not scheduled

- **Decision required:** which of the three paths in §5. Everything else waits.
- **The `ratchetTranche` gap** — 26% null on bearish calls, against Key Design
  Decision #3. Possibly a real pipeline defect; unexamined.
- **The Trim-with-Intact-thesis population** — 89 of 187 bearish calls. Never
  characterized. Presumably valuation or cap trims rather than deterioration
  calls; unknown whether they behave differently.
- Whether the severity-grading candidate is worth building a new gate for (§3).
- Pool-vs-split policy for candidates beyond v6.
- A6 terminal-value grading in `analyst_direct_scorer.py` (WOLF, SPWR).
- BK/BNY vendor gap — pre-rebrand history not carried forward under the new
  symbol; possibly fixable by querying the old symbol.
- C2: is the analyst's $6,843 above "add on every call" distinguishable from zero.
- Trend-layer override rate, never measured.
- Rule 3 removal and a real guard for falling speculative positions.
- The state dashboard (prompt version, allocator params, corpus composition,
  performance vs benchmarks).
