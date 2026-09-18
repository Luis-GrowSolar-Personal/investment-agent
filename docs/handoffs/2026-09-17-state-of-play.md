# State of play — 2026-09-17

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/EscyrQSgFPJwWEMKgLjFvc>

**Supersedes `docs/handoffs/2026-09-14-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** the measuring instrument is finished and trustworthy,
v6 is baselined on both train and tune, and the next action is a prompt
candidate that is already pre-registered and costs ~$47. Start at §5.

---

## 1. Where the project stands

The last three weeks went into building a ruler, not into improving the analyst.
That work is done.

- **Corpus:** 164 companies, three-way split (57 train / 54 tune / 53 holdout),
  point-in-time selected, holdout locked and hashed.
- **v6 baselined on both halves**, same model, apples-to-apples.
- **Scorer hardened**: it now refuses to report a score when calls go missing.
- **Holdout untouched.**

Two baselines cost **$92.24** total. A prompt iteration round is ~$47.

### What v6 actually scores

| | train (56 cos, 1,236 calls) | tune (51 of 54, 1,168 calls) |
|---|---|---|
| accuracy | 30.3% | 28.3% |
| gap over luck | +2.48pp (95% −0.06 to +5.08) | +2.64pp (95% **0.21 to 5.00**) |
| bearish calls made | 103 (8.3%) | 84 (7.2%) |
| …and right | 60.2% | 59.5% |
| base rate for bearish | 44.9% | 48.4% |
| neutral calls made | 57.3% | 58.8% |

**Pooled** (2,404 calls, 107 companies): **+2.53pp, 95% +0.79 to +4.19 — excludes
zero.** Pooling is legitimate for v6 only, which was never selected using train;
no candidate may be reported that way (`PROMOTION_GATE.md` §3.1a).

**Read that next to this:** a rule that says "bearish" every time scores 48.4% on
tune where v6 scores 28.3%. Both facts are true. **v6 has a real but small edge
and a badly-shaped answer distribution.**

---

## 2. The finding the next round is built on

v6's bearish calls are right ~60% against base rates of 45–48%, and it makes
them on 7–8% of calls. **Its rarest answer is its best one.** This replicated on
tune — companies the finding was not derived from — with precision within half a
point.

The edge is **band-independent**: 13 to 18 points over the base rate at ±5%,
±10%, ±15% and ±20% alike. So the fix does not depend on any unsettled question
about the ruler.

Do **not** restate this as "v6 over-calls neutral." That version is an artifact
of the ±5% dead band — at ±15% v6's neutral rate nearly matches reality. It was
briefly used to block the next round and should not be used again.

Not a corpus artifact either: the bearish skew holds in every stratum (S1 43.9%,
S2 48.0%, S3 47.0%), and dropping the failures stratum moves the pooled figure
46.6% → 46.2%. It is the ordinary right-skew of stock returns.

---

## 3. Where things are written down now

The docs were reorganized on 2026-09-17 so each fact sits where someone would
look for it.

| Question | File |
|---|---|
| What should the prompt do next? | `docs/architecture/PROMPT_ARCHITECTURE.md` |
| What does the scorer measure? | `docs/architecture/PROMOTION_GATE.md` §3.1 / §3.1a |
| Can a candidate be promoted? | `PROMOTION_GATE.md` §5, `VERSION_REGISTRY.json` |
| Exit timing, filings, allocator signals | `docs/handoffs/2026-09-05-exit-latency-framework.md` §0 |
| What the tune run found | `wrap-ups/baseline-v6-tune-batch-out.md` |

`PROMPT_ARCHITECTURE.md` is new. **Read it before touching the prompt.** It holds
the closed decisions about the prompt's shape, the ranked candidate queue, the
pre-registration each round owes, and the diagnostics each round must produce.

### Closed, do not re-derive

- **One prompt. Per-ticker *inputs*, never per-ticker *prompts*.** A prompt
  fitted per company cannot be measured: 24 calls per company gives a ±18-point
  range, and 47 of the 60-point observed spread across tickers is luck. Detecting
  a 5-point change on one ticker needs 662 calls — 165 years.
- **Grade `per_call_rec`**, never `final_action`.
- **Filings, XBRL and a company's own price history do not breach the firewall.**
  Portfolio and position data do.
- **A wider dead band is not an improvement.** It moves apparent accuracy 29% →
  52% and leaves the measured edge unchanged. Never widen it because the
  scoreboard looks better.

---

## 4. The instrument, and what it can and cannot see

**Detectable effect is about 5 points** on ~1,200 calls. Below that, a result is
not distinguishable from noise.

**A paired comparison lives entirely on the calls that changed answer.** A change
that flips 40 calls cannot gain more than 3.2 points even if every flip is right.
"The idea failed" and "the idea barely fired" are different conclusions, and the
headline cannot tell them apart. Flip-count table: `PROMPT_ARCHITECTURE.md` §2.4.

**The ruler grades one call at a time and cannot see exit timing at all.** Ideas
that fire *between* calls — 8-K triggers, insider clusters, price stops — need
the simulator, not this instrument. That is why Test 7 and Test 9 no longer lead
the analyst queue.

**Three ruler questions are open and none of them block anything**
(`PROMOTION_GATE.md` §3.1a): dead-band width (R1), magnitude weighting (R2),
grading-window placement for post-call inputs (R3). R3 must be settled before P2
runs; R1 and R2 are open for honesty, not for the critical path.

---

## 5. Next action

**Run P1.** It is pre-registered in `PROMPT_ARCHITECTURE.md` §2.2.

- **Change:** push the prompt to issue a bearish call whenever its own evidence
  supports one, instead of defaulting to a non-committal answer. This targets how
  often the analyst deploys a signal it already has, not its ability to find one.
- **Predicted:** >200 calls flip on train; bearish call rate rises from 7.8%;
  accuracy and the gap rise; bearish precision falls from 59.9% toward the 46.6%
  base rate.
- **Falsified if:** precision reaches the base rate (the prompt is guessing, not
  committing), or fewer than ~100 calls flip (the instruction did not take).
- **Before spending $47:** run the pre-flight screen — ~150 calls, ~$6 — and
  count disagreements with v6. Under ~100 implied flips corpus-wide, stop.
- **Runs on train.** Tune only if it clears, and only once. Holdout stays locked.

Also runnable today, no new data: **P3**, the thesis/guidance ledger — score last
quarter's promises at this quarter's call, 1,184 usable calls already on disk.

**Pre-register before running. Name two or three candidates, not eight.** Six
candidates screened on one sample hand back a winner that looks ~1.5 points
better than it is; twenty, about 2.45 points — the size of the effect currently
under investigation.

---

## 6. Standing caveats, carried

- **Model confound.** Everything is `claude-sonnet-4-6`. v6's original
  40.4%/39.6% came from `claude-sonnet-4-20250514`, retired 2026-06-15. Any
  weakness *or* the positive gap may be the model, not the prompt, and available
  data cannot separate them. Both baselines share the model, so train-vs-tune is
  paired; anything compared to the legacy figures is not.
- **The gap is a cheap proxy for dollars, and imperfect.** It counts every call
  equally; the portfolio does not. A 6% miss on a small position scores like a
  60% collapse in a large one. Bridge is ~$5,825 per point (Test 1, three-event
  basis, fragile). §3.1a R2 proposes fixing this.
- **WOLF and SPWR are ungradable** — 2024/25 bankruptcies where the ticker was
  reused and pre-reorg prices are purged at source. NOVA is silently affected the
  same way on train. Whether to wire A6 terminal-value grading into the scorer is
  an open design decision.
- **Sector-relative grading (F2) unresolved**; everything is benchmarked to SPY.
- **Six instances now** of one failure shape: a check or artifact built against
  one set of keys while the consumer reads another. The coverage guard caught the
  sixth (SPWR) automatically — the first time a machine caught one instead of a
  person noticing afterward.

---

## 7. Open, not scheduled

- Pool-vs-split policy for candidates beyond v6.
- A6 terminal-value grading in `analyst_direct_scorer.py` (WOLF, SPWR, NOVA).
- BK/BNY vendor gap — pre-rebrand history not carried forward under the new
  symbol; possibly fixable by querying the old symbol.
- C2: is the analyst's $6,843 above "add on every call" distinguishable from zero.
- Trend-layer override rate, never measured.
- Rule 3 removal and a real guard for falling speculative positions.
- The state dashboard (prompt version, allocator params, corpus composition,
  performance vs benchmarks).
