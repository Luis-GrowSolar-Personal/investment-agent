# State of play — 2026-09-20

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/PJVMbf4SD9oxAbjABB7ECa>

**Supersedes `docs/handoffs/2026-09-19-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** the project has been measuring the wrong quantity.
Every result until now reported whether the analyst was *right*. Money was
measured for the first time this week and came out at zero on average — but
the median bearish call still lags the market by 10%, and the analyst was
shown not to be redundant with the market's own reaction. The next action is
to buy consensus-estimate data, which is the one input never tested and the
only one that remains plausible. Start at §2, then §6.

---

## §0 — Defined terms

Read this before anything else. Several of these read as their own opposite.

**The two ways of judging a call, and the difference is the theme of this
document**

- **Accuracy.** Was the call right? A bearish call counts as right if the
  stock ended more than 5% behind the S&P after about six months. **A stock
  that drifted down 6% and one that collapsed 60% count identically.**
- **Money.** How far it actually moved. This is what a portfolio feels.
  **Accuracy and money came apart this week, and that is the single most
  important finding in this document.**

**The kinds of number**

- **Base rate.** How often an outcome happened across *all* calls, whatever
  the analyst said. It moves with the horizon and with the entry price, so an
  edge is always measured against the base rate computed the same way.
- **Edge.** Hit rate minus base rate, in points.
- **Median versus mean.** The median is the typical case. The mean is dragged
  by extremes. **For bearish calls the two disagree sharply** (median −10.1%,
  mean −1.2%) and which one you use changes the conclusion.
- **Tail.** A call whose stock fell more than 25% behind the market. The
  disasters.
- **Ticker-block range.** A 95% range built by resampling whole companies, not
  single calls, because one company's calls are not independent. **If a range
  includes zero, the data cannot tell the two things apart.**

**The two entry prices, and why it matters**

- **As-is entry.** The closing price on the day of the call. This is what the
  scorer has always used. For a company reporting after the close, that price
  is from *before* the news, so the return includes an overnight move nobody
  could trade.
- **Tradeable entry.** The closing price the next day — the first price a
  person who read the transcript could actually reach. **Every money figure in
  this document uses the tradeable entry.**

**The analyst's three answers**

- **Bearish** = Trim or Exit. **Bullish** = Add. **Neutral** = Hold.

**Portfolio rules referenced later**

- **Type A / Type B.** Single-driver positions (35% cap), multi-driver
  platform positions (50% cap). **The 25% profit-take rule** trims winners.
  Together these mean the portfolio would not capture the full upside of a
  stock that doubles — which matters in §3.

**Plain-English summary, before any identifier appears**

The analyst is right more often than chance when it says a stock will do
badly. It says so rarely — about once every three years for any given stock.
Selling on those calls, measured as a simple average, made no money, because
the ones it got wrong went up as hard as the ones it got right went down. But
the typical flagged stock still lagged by 10%, and the analyst is seeing
something the market's own reaction to the same earnings call does not see.
What has never been tested is whether comparing a company to what professional
analysts expected — rather than to its own past promises — makes the calls
better. That needs data we do not have.

---

## §1 What happened since 2026-09-19

Eight runs, about **$61** spent. Everything below is new.

| run | cost | result |
|---|---|---|
| Guidance ledger, phase one | $46.15 | **stopped at its own gate.** Guided misses carry no forward signal |
| Grading-horizon sweep | $0 | edge falls with the horizon on one half, not the other |
| Entry-price test | $0 | that fall was the announcement move, not a real effect |
| Confirmation-rule test | $0 | waiting for a second warning buys nothing. **Found a corrupt price series** |
| Disaster-profile test | $0 | none of nine features spots the catastrophes in advance |
| Vendor coverage probe | $0 | prices validated; consensus data blocked on the free tier |
| Ask-it-twice test | $15.07 | repeated calls point the right way; **the corpus cannot resolve it** |
| Direction, swap and market-reaction analyses | $0 | §3 |

---

## §2 The measurement change, and it reframes everything

**Money was measured for the first time.** Selling a flagged stock the day
after the call, against holding it, over six months:

> **0.0%**, with a range from −8.7% to +8.7%.

Nothing. And the −4.1% figure that briefly looked like a result was one
corrupt company (§5).

**How can the analyst be right 59% of the time and be worth nothing?** Because
accuracy scores a 6% drift and a 60% collapse the same, and scores a miss the
same whether the stock rose 6% or 60%. The analyst wins slightly more often
than it loses, and when it loses the stock has often rallied hard enough to
cancel the wins.

**Standing rule from here on: every result reports money, and accuracy is a
footnote.** Every test before this week optimised a quantity nobody had shown
converts into dollars.

### But the average hides the shape, and the shape is the story

| the analyst said | calls | mean vs S&P | **median vs S&P** |
|---|---|---|---|
| bullish | 818 | +1.17% | −1.43% |
| neutral | 1,390 | −1.73% | −4.03% |
| **bearish** | **177** | **−1.24%** | **−10.09%** |

**The typical flagged stock lags by 10%.** The mean sits near zero only
because a minority rallied hard. "Bearish calls are worthless" is the wrong
reading; "bearish calls mostly decline, and occasionally a flagged stock
rockets" is the right one.

**This matters more for this portfolio than for an index fund**, because the
35%/50% caps and the 25% profit-take rule mean a rocket would have been
trimmed on the way up. The portfolio would not have captured the full upside
that drags the mean to zero, so its effective experience sits closer to the
median. **That has not been simulated and it should be.**

---

## §3 What the analyst is, and is not

### It is not redundant with the market — this is the week's best news

The market's own reaction to an earnings call was tested as a substitute
signal. It fails, and the way it fails is instructive.

| the day after the call | calls | forward median | share falling >25% behind |
|---|---|---|---|
| fell more than 10% | 76 | −8.04% | **25.0%** |
| fell 5–10% | 141 | −0.19% | 17.7% |
| fell 0–5% | 1,007 | −3.68% | 9.7% |
| rose 0–5% | 932 | −3.04% | 9.4% |
| **rose more than 5%** | 229 | −4.58% | **23.1%** |

It is not ordered — stocks that fell 5–10% did better afterwards than stocks
that fell 0–5%. And a big *rise* carried almost the same disaster rate as a
big fall. **A large reaction signals volatility, not direction.**

Head to head: the market's reaction gives a forward median of **−3.47%**
against an all-calls baseline of **−3.37%**. The analyst gives **−10.37%**.

**And the analyst adds most where the market disagreed with it:**

| analyst bearish, split by the market's reaction | calls | forward median |
|---|---|---|
| market also dropped more than 5% — already priced | 42 | −5.76% |
| market shrugged | 135 | −10.52% |
| **market actually rose on the call** | 80 | **−11.67%** |

Range on that difference is −21 to +12 points, so it is not established. But
the direction is coherent and it is the signature of real added information.
**Do not build a filter requiring the market to agree** — that cut the median
from −10.37% to −5.76%.

### Its neutral answers carry no information at all

| the analyst said | share of calls | edge over its own base rate |
|---|---|---|
| bearish | 7.4% | **+12.3** |
| bullish | 34.3% | +4.4 |
| **neutral** | **58.3%** | **+0.0** |

*As-is entry, Paramount excluded. On a tradeable entry: +10.1, +2.4, +0.0.*

**Saying "Hold" is exactly as accurate as guessing**, replicated on both
halves of the data independently, on 58% of all calls. Nothing has ever
targeted this, and it is the largest single block of wasted output.

### Its bullish calls are too weak to carry a swap

Selling a bearish-flagged stock and buying a bullish-flagged one is worth
**+2.4 points on means, +8.7 on medians**, range −7.0 to +12.4. Of the mean
spread, roughly half comes from each leg — and the bullish leg beats the index
by only 1.17%. **Improving bearish calls alone caps how much the swap can ever
be worth.**

---

## §4 What was closed this week

- **Guidance misses carry no forward signal.** A mechanically graded miss was
  followed by underperformance 47.4% of the time against a 46.6% base rate.
  Clean beats predicted outperformance 30.4% against 32.8% — slightly
  *negative*, consistent with companies that beat their own conservative
  guidance being priced for it. No metric cut and no magnitude cut rescued
  either. **The guidance-ledger candidate is dead on the evidence**, though
  §5 notes the extraction was imperfect.
- **Waiting for a second warning buys nothing.** Hold, sell now, wait and
  confirm, wait and always exit — all four indistinguishable.
- **The catastrophes are not spottable in advance.** Nine features known at
  the time of the call; none separated on both halves and per company. The
  strongest was a corpus category resting on two companies with no comparable
  cases in the other half.
- **Waiting longer or shorter does not change the edge** once the entry price
  is fixed. The earlier "shorter horizons are better" result was the
  announcement move and is withdrawn.
- **Voting across repeated runs does not help.** Majority of five scored −1.3
  points against a single run.
- **The market's reaction is not a substitute for the analyst** (§3).

---

## §5 The instrument, and five things wrong with it

**1. A corrupt price series, now excluded.** Paramount's cached prices show a
flat ~$100,000 decaying to about $1, against a stock that never left a $10–100
range. It is not a scale error — the shape is wrong — and the series also
starts a year late. **Paramount is excluded from the project as of
2026-09-20**, alongside WOLF and SunPower. It sat in the out-of-scope control
stratum, so nothing in the investment universe is lost.

> **Corrected headline: the bearish edge is +12.3, not +13.3.** Every earlier
> figure touching Paramount is 1 to 3 points high. No earlier conclusion
> changes.

An audit of all 172 tickers found **no other healthy company with a broken
series**. An independent vendor confirmed our prices match on five test
companies on every shared date.

**2. The flip-count rules are below the noise floor.** The analyst disagrees
with itself on about 12.8% of calls — roughly 152 of 1,184 would "flip" from
re-running the same prompt unchanged. `PROMPT_ARCHITECTURE.md` §2.5's 100-flip
floor sits *below* that, and §2.4's ceiling table is computed on raw flips.
**Both mislead every candidate in the queue.** Not yet corrected.

**3. On bearish calls the analyst is far less consistent than that.** Asked
again, it repeats a bearish call only **67% of the time**. The 12.8% figure is
an average dominated by Hold, which it says the same way every time. **One
bearish call in three it will not repeat.**

**4. The corpus has hit its resolution limit for subset questions.** Telling a
12-point difference between two groups of bearish calls apart needs roughly
190 calls in each group. The corpus holds **177 bearish calls in total**.
Unlocking the held-back companies would not close the gap. **More re-runs
cannot help; only more companies or more years can.**

**5. Returns ignore dividends.** The price cache holds unadjusted closing
prices — it matched an independent vendor's `close` exactly and not its
dividend-adjusted series. So a stock that fell 10% while paying 6% shows as
−10%. **Several of the worst-looking calls are high-yield names**: Verizon,
Kraft Heinz, Dow, UPS, Bristol-Myers, General Mills. The benchmark is also
price-only, so the bias is the difference in yields and it runs against
exactly these stocks. **Tabled by decision on 2026-09-20, but it biases the
ruler and must be settled before any result is promoted.**

---

## §6 Next action — buy consensus-estimate data

**The one input never tested.** The ledger work established that comparing a
company to *its own prior guidance* carries no forward signal. The untested
hypothesis is that comparing it to *what the market expected* does. A company
can beat its own conservative guide and still miss what the street wanted, and
the stock falls. **That gap is invisible in a transcript.**

§3 strengthens the case rather than weakening it: the price reaction is a poor
substitute for the surprise, because one day's move contains the surprise plus
guidance, tone, sector and volatility all at once. Consensus data separates
them.

**The free tier cannot answer it.** The vendor's earnings endpoint returns
HTTP 403, "Only EOD data allowed for free users." The 500-call bonus raises
volume, not endpoint access.

| option | cost | gives |
|---|---|---|
| **EODHD, Fundamentals feed** | **$60/mo** | earnings estimate vs actual back to the 1990s, plus a before/after-market flag, plus dividend-adjusted prices which would settle §5 item 5 |
| Benzinga Earnings | $99/mo | earnings **and revenue** estimates vs actuals, back to 2010. No free tier, no trial |
| Benzinga Corporate Guidance | $99/mo | structured company guidance — would replace the $46 extraction that had a 5.6% error rate and 35% coverage |

**Recommended: one month of the $60 tier.** It answers the coverage question
outright, and it fixes the dividend defect at the same time. Revenue estimates
are the reason to consider the $99 option, and that only matters once earnings
estimates alone are shown to be insufficient — especially for pre-revenue
names, where an earnings estimate measures an expected loss and says little.

**The probe is already written and costs about 10 calls**
(`prompts/eodhd-coverage-probe.md`, driver committed). It runs the day a paid
key exists.

**Also runnable today, no new data, and never attempted:** the neutral pile.
58% of the analyst's answers carry zero information (§3). No candidate has
ever targeted it.

---

## §7 Open, not scheduled

- **Simulate the allocator with the real caps and profit-take rule** (§2). All
  money figures so far are simple averages that assume full upside capture;
  the portfolio's own rules would have trimmed the rockets. **This is the
  measurement the project has never done on the thing it keeps trying to
  improve.**
- Correct `PROMPT_ARCHITECTURE.md` §2.4 and §2.5 for the noise floor (§5.2).
- Settle the dividend question (§5.5).
- Why did the analyst's un-repeated bearish calls *beat* the market by 13.7%
  on average? Unexplained.
- The ratchet field is null on 26% of bearish calls, against Key Design
  Decision #3.
- Pool-vs-split policy for candidates beyond v6.
- Terminal-value grading for delisted companies.
- BK/BNY pre-rebrand history.
- Trend-layer override rate, never measured.
- Rule 3 removal and a guard for falling speculative positions.
- The state dashboard.
