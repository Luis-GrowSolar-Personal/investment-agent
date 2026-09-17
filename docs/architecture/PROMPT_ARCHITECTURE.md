# Prompt Architecture — analyst prompt shape, and the queue of candidates

**Created 2026-09-17.** Scope: **Layer 2 only** — the analyst prompt that reads a
single earnings-call transcript and emits `per_call_rec`. Nothing here concerns
the trend layer or the allocator.

**What belongs where.** This file holds (§1) closed decisions about the prompt's
shape and (§2) the ranked queue of candidate changes with their pre-registration.
It deliberately does **not** hold:

| Topic | Lives in |
|---|---|
| What the scorer measures, dead band, weighting, windows | `PROMOTION_GATE.md` §3.1 / §3.1a |
| Whether a candidate passed and may be promoted | `PROMOTION_GATE.md` §5, `VERSION_REGISTRY.json` |
| The prompt text itself | `docs/EVALUATION_PROMPT.md` |
| Exit-timing and allocator signal design | `docs/handoffs/2026-09-05-exit-latency-framework.md` |

---

## 1. Closed decisions about the prompt's shape

Do not re-derive these. Each was settled against measured data; the evidence is
named so a future session can overturn one with better evidence rather than with
an argument.

### 1.1 One prompt. Per-ticker **inputs**, never per-ticker **prompts**

A prompt fitted to a single company's own track record cannot be measured.
Median calls per company is 24. At n=24 a single ticker's hit rate carries a
**±18-point** 95% range; the observed best-minus-worst spread across 56 tickers
is 60 points, of which **47 points appear from luck alone** if every company is
identically average. Detecting a 5-point change on one ticker needs **662 calls**
for that ticker — 165 years of quarterly earnings. It also destroys the gate:
56 prompts at n=24 produce no pooled figure to grade.

**Permitted:** one prompt whose *inputs* vary by ticker — tier, cohort, the
company's own prior thesis, its own trailing ratios. n stays at 1,184 (1,240
train calls minus the first call of each company, which has no predecessor).

**Forbidden:** any feedback from realized **outcomes** into the prompt that is
not strictly forward-only (only calls before date T may inform the call at T).
Note that per-call prompt variation also defeats the cached system block that
makes a ~$47 scoring round possible.

Per-ticker *memory* — what management promised last quarter — is inputs, not
fitting, and is permitted.

### 1.2 Conditioning happens on tier/cohort, because a class has enough members

"Inventory up 50%" means different things for a pre-revenue speculative with
few customers and an established company with a forecasting record. That is a
property of the class, not of the ticker, and classes have enough members to
measure. The 3-axis speculative/established classifier already exists and `tier`
is already threaded through the pipeline. Same conclusion the two-template fact
sheet design reached independently
(`2026-09-05-exit-latency-framework.md` §4).

### 1.3 Grading field is `per_call_rec`

The analyst's own call, never `final_action`. Grading the post-trend-layer
action lets a trend-layer change read as a prompt improvement; Stage D hit
exactly this.

### 1.4 Firewall

No portfolio or position data reaches this layer. Non-transcript data *about the
company* — filings, XBRL facts, its own price history — is not portfolio data and
does not breach the firewall.

---

## 2. Candidate queue

### 2.1 What the baselines say is broken

Pooled train (56 companies, 1,236 calls) and tune (51 companies, 1,168 calls),
both `claude-sonnet-4-6`:

| | train | tune (fresh companies) |
|---|---|---|
| v6 accuracy | 30.3% | 28.3% |
| luck-corrected gap | +2.48pp (95% −0.06 to +5.08) | +2.64pp (95% 0.21 to 5.00) |
| times v6 said bearish | 103 (8.3%) | 84 (7.2%) |
| …and was right | 60.2% | 59.5% |
| base rate for bearish | 44.9% | 48.4% |
| times v6 said neutral | 57.3% | 58.8% |
| always-bearish guesser | 44.9% | 48.4% |

**The finding that drives the queue, and it replicated on companies it was not
derived from: v6's bearish calls are right ~60% against base rates of 45–48%,
and it makes them 7–8% of the time.** Its rarest answer is its best one.

**Two live explanations, not yet separated.** (a) The prompt retreats to a
non-answer — a commitment problem, fixable in the prompt. (b) The ±5% dead band
is tighter than what v6 treats as meaningful; at ±15% the outcome distribution
(56.1% neutral) nearly matches v6's own (58.1%), which would make v6 roughly
calibrated and the ruler too tight. **`PROMOTION_GATE.md` §3.1a R1 settles which,
costs $0, and blocks candidate P1.** Do not spend a scoring round before it is
settled.

Not a corpus artifact: the bearish skew holds in every stratum (S1 megacap
43.9%, S2 48.0%, S3 47.0%), and excluding the failures stratum moves the pooled
figure from 46.6% to 46.2%. It is the ordinary right-skew of stock returns.

### 2.2 Queue

Ranked by expected value per dollar, not by ambition. A round is ~$47 and
several hours.

| # | Candidate | New data? | Blocked by | Status |
|---|---|---|---|---|
| P1 | Decision-threshold / neutral-abstention change | none | §3.1a R1 | blocked |
| P2 | Post-call reaction at K≥1, three arms | none (price cache) | §3.1a R3 | blocked |
| P3 | Thesis / guidance ledger — score QN−1's promises at QN | none (transcripts on disk) | — | ready |
| P4 | Tier-conditioned reading of financial facts | XBRL build | P3 | not started |
| P5 | Peer read-through across cohort members | none (transcripts) | — | not started |

P1 and P2 are blocked on free decisions, not on work. P3 is the first candidate
that can run today: 1,184 usable calls, no vendor fetching, no new corpus.

### 2.3 Pre-registration — required before any candidate is run

Fill this in, in this file, **before** the round. Six candidates screened on one
sample hand back a winner that looks about 1.5 points better than it is; twenty
candidates about 2.45 points — the size of the effect currently under
investigation.

For each candidate: the change in one sentence · what it is expected to move and
in which direction · **predicted flip count** (see 2.4) · what result would
falsify it · which split it runs on · the date it was registered.

Name the two or three candidates to be tried **before running any of them.**

### 2.4 Required diagnostics after every round — all free, no model calls

A round that reports only a headline has wasted most of what it bought.

1. **Flip count** against the incumbent on the shared calls, and the win rate
   among flips. A paired comparison lives entirely on the disagreements.
2. **The confusion table** — did the neutral pile shrink, and did new bearish
   calls hold precision above the 45–48% base rate?
3. **Per-call diffs written to disk**, so a later round can re-read them.

A change that flips few calls has a hard ceiling regardless of how good it is:

| calls flipped (of ~1,200) | most it could possibly gain | flips that must be won | smallest visible gain |
|---|---|---|---|
| 40 | 3.2 pts | 29 of 40 | 1.4 pts |
| 100 | 8.1 pts | 64 of 100 | 2.3 pts |
| 200 | 16.2 pts | 120 of 200 | 3.2 pts |
| 400 | 32.4 pts | 228 of 400 | 4.5 pts |

Binomial, therefore optimistic — the ticker-block bootstrap gives wider ranges.
**"The idea failed" and "the idea barely fired" are different conclusions and
the headline cannot tell them apart.**

### 2.5 Pre-flight screen — run before committing a full round

Score ~150 calls (~$6) and count disagreements with the incumbent. If the
implied corpus-wide flip count is under ~100, **do not run the full round.** The
change cannot clear the noise floor whatever the reasoning behind it.

### 2.6 Automated iteration — generator, never judge

Feeding the model its own wrong calls plus the realized outcome and asking what
pattern it missed is nearly free (existing eval files, no re-scoring) and is
worth building as a source of hypotheses.

**Such a loop must never also select.** It will not try twenty candidates, it
will try two hundred, and the winner of two hundred is noise with a good story.
Design that keeps it honest: **split train in half** — the loop iterates freely
on train-A, survivors are screened on train-B, and only what survives both
reaches tune. Tune evaluations stay hand-counted and pre-registered. Holdout
stays locked.

---

## 3. Standing limits that apply to every candidate

- **Model confound.** All current figures are `claude-sonnet-4-6`. v6's original
  40.4%/39.6% came from `claude-sonnet-4-20250514`, retired 2026-06-15. Any
  weakness *or* the positive gap may be the model rather than the prompt, and
  available data cannot separate them. Both baselines share the model, so
  train-vs-tune is paired; anything compared against the legacy figures is not.
- **The gap is a cheap proxy for dollars, and an imperfect one.** It counts every
  call equally; the portfolio does not. See §3.1a R2.
- Sector-relative grading (F2) unresolved — everything is benchmarked against SPY.
- Holdout is locked and unscored.
