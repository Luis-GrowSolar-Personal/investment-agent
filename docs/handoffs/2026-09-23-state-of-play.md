# State of play — 2026-09-23

**Reading version (renders correctly anywhere, phone included):**
https://claude.ai/artifact/TtBzBoVTTQoKobmXfTS4h9

**Supersedes `docs/handoffs/2026-09-20-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** consensus-estimate data is stalled — the vendor did
not answer the evaluation request, and there is no free path to it. **The
findings in the 2026-09-20 document all stand; only the next action changes.**
This document exists to answer one question: what can be done to improve the
analyst without buying anything. There are six candidates, none has been tried,
and three need no new data at all. Start at §3.

---

## §0 — Defined terms

Carried from 2026-09-20; read that document's §0 for the full set. The terms
this one leans on:

- **Accuracy.** Was the call right — did the stock end more than 5% behind or
  ahead of the S&P after about six months. **A 6% drift and a 60% collapse
  count identically.**
- **Money.** How far the stock actually moved. **Since 2026-09-20 this is the
  measure of record; accuracy is a footnote.** The two came apart, and that
  change is what unblocks one of the candidates below.
- **Edge.** Hit rate minus the base rate for that answer, in points.
- **Median versus mean.** The median is the typical case; the mean is dragged
  by extremes. For bearish calls: median −10.09%, mean −1.24%.
- **Tradeable entry.** The closing price the day *after* the call — the first
  price a transcript reader could reach. All money figures use it.
- **The three answers.** Bearish = Trim or Exit. Bullish = Add. Neutral = Hold.
- **Candidate.** A proposed change to the analyst's prompt, pre-registered
  before it runs, scored against v6 on the train companies and confirmed on
  tune only if it clears.

**Plain-English summary before any identifier appears.** The analyst has a
real but narrow skill: when it says a stock will do badly it is right about
59% of the time against a 47% base rate, and the typical flagged stock lags by
10%. It says so on 7% of calls. Its neutral answers — 58% of everything it
says — carry no information at all. Buying analyst-consensus data was the plan
to improve it; that is stalled. What remains is a set of changes to the prompt
itself, none of which has ever been tried.

---

## §1 What changed since 2026-09-20

**One thing: the consensus path stalled.**

- The free vendor probe established the data exists in the right shape for
  106 of 108 companies, but only **four quarters deep** — the corpus needs
  twenty-four. Forward earnings, revenue estimates and price targets are all
  behind the paywall.
- The **$75/month Estimate-1 tier has everything needed**: EPS surprises and
  revenue estimates both 10 years historical, an earnings calendar with report
  dates and before/after-market timing. Billing shows quarterly, so the real
  commitment may be **$225**.
- **An evaluation-licence request went unanswered.** No reply.

**Two questions remain unanswered for every vendor**, and they matter more
than the price: whether the historical estimate is **point-in-time** (the
value as it stood before the report, not revised since — a revised figure
leaks the answer), and whether the estimate and the actual sit on the **same
accounting basis**. The free probe found pairs that look inconsistent — Eos
Energy at an estimate of −$0.23 against an actual of −$4.91.

**Nothing else moved.** No runs, no spend.

---

## §2 The evidence, in brief — all carried forward

| measure | result |
|---|---|
| bearish calls | 7.4% of calls, edge **+12.3**, median **−10.09%** |
| bullish calls | 34.3% of calls, edge **+4.4**, median −1.43% |
| **neutral calls** | **58.3% of calls, edge +0.0** — replicated on both halves |
| selling on a bearish call | **0.0%** against holding, range −8.7 to +8.7 |
| sell bearish, buy bullish | +2.4 on means, **+8.7 on medians** |
| the analyst vs the market's own reaction | −10.37% against −3.47%, on a −3.37% baseline |

**Closed and not to be re-opened:** guided misses carry no forward signal;
waiting for a second bearish call buys nothing; nine features fail to spot the
catastrophes in advance; the horizon does not matter once the entry price is
fixed; voting across repeated runs does not help; the market's own reaction is
not a substitute for the analyst.

---

## §3 Six ways to iterate the prompt — none has been tried

Ranked by expected value against effort. **Every one is measured in money,
with accuracy reported alongside.** A scoring round is about $45 plus a
noise-floor arm.

### 1. The neutral pile — the largest untouched block

**58% of the analyst's answers carry zero edge over their own base rate**, on
both halves of the data independently. That is 1,390 calls of 2,385 producing
nothing.

**This is not the retired "over-calls neutral" argument.** That one was a
dead-band artifact and was correctly retired. This is different: measured
against neutral's *own* base rate, at the same band, the edge is exactly zero.
The analyst is not hedging toward a defensible middle — when it says Hold it
knows nothing.

**The candidate:** press the analyst to say Hold only when it genuinely has no
read, and to commit otherwise. **Distinct from the earlier P1**, which pushed
it toward bearish specifically; this is direction-agnostic and targets the
answer that is demonstrably empty.

*No new data. Largest available block. Never attempted.*

### 2. The bullish leg — never had a candidate at all

Every candidate this project has written — P1, the guidance ledger, the
ranking test, the repeat test — has been about bearish calls. **The bullish
side has never been touched.**

It matters because of the swap. Selling a flagged stock and buying a
bullish-flagged one is worth +2.4 points on means, and **roughly half of that
comes from each leg**. The bullish leg beats the index by only 1.17%.
**Improving bearish calls alone caps how much the swap can ever be worth.**

*No new data. Addresses a structural ceiling nothing else can lift.*

### 3. Severity grading — the measurement change unblocked it

Across 187 bearish calls the analyst said **"Exit" once** and called a thesis
**"Broken" twice**. It has a four-level scale and uses one level. That is an
unused vocabulary, not a missing signal.

**This candidate was previously unrunnable and now is not.** Changing a call
from Trim to Exit does not change its *direction*, so under the old
accuracy-based ruler it flipped zero calls and was invisible. **Money is
sensitive to magnitude**, so a severity field that tracks how far a stock
falls is now measurable. The measure change did this, not any new data.

*No new data. Was blocked by the ruler; the ruler moved.*

### 4. The auto-iterate loop — a hypothesis generator, nearly free

`PROMPT_ARCHITECTURE.md` §2.6 describes it and it was never built: feed the
model its own wrong calls plus what actually happened, and ask what pattern it
missed. It uses eval files already on disk and makes no scoring calls.

**It must never also select.** §2.6's own design holds: it iterates on half of
train, survivors are screened on the other half, and only what survives both
reaches tune. Tune evaluations stay hand-counted and pre-registered.

*Nearly free. Produces candidates rather than being one.*

### 5. Peer read-through — P5, never started

Read a company's call against what its cohort peers said the same quarter. All
transcripts are on disk.

*No new data. Untried. No reason recorded for why it was never picked up.*

### 6. Tier-conditioned financial facts — P4, and **its blocker is gone**

P4 was "blocked by P3." **The guidance ledger ran and is dead, so P4 is
unblocked.** It needs an XBRL build — structured financial facts — and
`PROMPT_ARCHITECTURE.md` §1.4 explicitly permits filings and XBRL without
breaching the firewall.

**The data is free.** SEC EDGAR publishes XBRL company facts at no cost. This
is the one candidate that adds a genuinely new input without a subscription.
The cost is engineering, not money.

*Free data, real engineering. The only new-input candidate that does not need
a vendor.*

### Downgraded: P2, post-call reaction

P2 would feed the market's post-call price move to the analyst as an input.
**The market-reaction analysis on 2026-09-20 weakens it considerably**: that
move is not ordered against forward returns — stocks that fell 5–10% did
better afterwards than stocks that fell 0–5% — and a large move in either
direction signals volatility rather than direction. It also remains blocked on
the §3.1a R3 grading-window decision, which is free to make and has not been
made.

---

## §4 The instrument — unchanged, and still carrying five defects

1. **Paramount excluded** (corrupt price series). Headline edge is **+12.3**,
   not +13.3.
2. **The flip-count rules sit below the noise floor.** The analyst disagrees
   with itself on ~12.8% of calls, about 152 of 1,184. `PROMPT_ARCHITECTURE.md`
   §2.5's 100-flip floor is *below* that and §2.4's ceiling table is computed
   on raw flips. **Both mislead every candidate in §3. Correcting them is free
   and should happen before the next round runs.**
3. **On bearish calls consistency is 67%, not 87%.** One bearish call in three
   it will not repeat.
4. **The corpus has hit its resolution limit for subset questions.** 177
   bearish calls; telling a 12-point difference apart needs ~190 per group.
   **Every candidate in §3 inherits this** — a real improvement may be
   unprovable on this corpus.
5. **Returns ignore dividends.** Tabled by decision; the holdings in question
   rarely pay dividends, so the effect on this portfolio is small. Recorded,
   not pursued.

---

## §5 Next action

**Fix the flip-count rules first (§4.2). It is free, it takes one edit, and
every candidate below is scored against a floor that is currently wrong.**

Then pick one candidate. **The neutral pile (§3.1) is the recommendation** —
largest block, no new data, a finding that replicated on both halves, and
nothing has ever targeted it.

**If a second is wanted in the same round, the bullish leg (§3.2)** addresses
the ceiling that caps everything else. Two candidates pre-registered together
is within `PROMPT_ARCHITECTURE.md` §2.3's "name two or three before running
any."

**On consensus data:** the $75 tier still answers the question the free tier
could not, and $900 a year needs to produce 0.09% on a $1M portfolio to pay
for itself. It is not a close call on price. It is stalled on a non-reply and
on two unanswered technical questions. **Leaving it open costs nothing while
the §3 candidates run.**

---

## §6 Open, not scheduled

- Simulate the allocator with the real caps and the profit-take rule. Every
  money figure so far is a simple average assuming full upside capture; the
  portfolio's own rules would have trimmed the rockets. **Still the
  measurement never done on the thing this project keeps trying to improve.**
- Settle §3.1a R3, which unblocks P2 for free whatever its merit.
- Why did the analyst's un-repeated bearish calls *beat* the market by 13.7%
  on average? Unexplained.
- Consensus vendors: point-in-time and accounting-basis questions unanswered.
- The ratchet field is null on 26% of bearish calls, against Key Design
  Decision #3.
- Pool-vs-split policy for candidates beyond v6.
- Terminal-value grading for delisted companies.
- BK/BNY pre-rebrand history.
- Trend-layer override rate, never measured.
- Rule 3 removal and a guard for falling speculative positions.
- The state dashboard.
