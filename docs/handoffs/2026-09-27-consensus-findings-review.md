# Consensus findings — review, and the "how would you beat QQQ" question

**Reviews:** `docs/handoffs/2026-09-27-consensus-findings-for-review.md`.
**Verdict on §3: agree on all three, with one sharpening of 3.2 and one
addition to 3.3.**

---

## 1. The three proposals

**3.1 Waive the eight checks — agree.** The checks could only lower a
result. The result is already at the bottom. Record FAIL as final.

**3.2 Close historical bullish research — agree, and say why it
closed.** Six routes failed, and they failed the same way: every one of
them used information that was public on the day of the call (the
transcript, the price history, the consensus estimate). The market had
that information too. The clean reading is that the market prices what
is said on a call, and how it compares with expectations, within days.
That is not a defeat of the analyst. It is a finding about the market,
and it tells us where not to look.

Sharpen the reopen rule: reopen only for information that is **not
derivable from the transcript, price history or reported-versus-expected
EPS**. Two named candidates stay on the list, both dormant: analyst
**revisions** in the weeks before the call (a documented effect, distinct
from surprise, and untested here; needs an estimate-history source), and
a **revenue** surprise source for the near-zero-EPS names. Neither is run
without a data source in hand and a pre-registered primary.

**3.3 Next work — agree on the order.** Allocator rebuild first. Live
forward test on the full corpus on Sonnet plus Luis's names on Opus:
agree; 650 calls a year gets a first bullish reading inside a year, and
the downside confirmation sooner. Cancel the premium key now; a month of
it is $50 if the allocator design wants "big miss" as a trim confirmer.

**One addition to 3.3, from §2 below:** the allocator rebuild should be
specified against QQQ-style cap weighting as the *default book*, not
against the current speculative/established matrix. Reason follows.

---

## 2. How SPY, QQQ, VGT and XLK "do it", and what it means here

Luis's question: these funds return 10% or more a year and beat our
benchmarks, so they must have a method we haven't considered.

**They don't pick.** Each one holds everything in its universe in
proportion to company size. SPY holds the S&P 500 that way. QQQ holds
the 100 largest non-financial companies listed on Nasdaq that way. XLK
holds the S&P 500's technology sector; VGT holds the technology sector
of a broader US index. Nobody at those funds decides that NVDA is
undervalued. The rules are public and a few pages long.

**Three things fall out of cap weighting, and they are the whole
"method":**

1. **It never sells a winner.** A stock that doubles becomes twice the
   weight, automatically, with no decision and no tax. Our own data says
   this matters: big winners were spread evenly across B's scores, and
   they were not prior losers or prior winners. Nothing we tested could
   find them in advance. A cap-weighted book does not need to find them.
   It holds them all and lets the ones that win grow.
2. **It rides losers to the bottom.** The same rule holds a stock all the
   way down until it drops out of the index. Cap weighting has no
   downside skill at all. This is the one thing B has that the index
   does not.
3. **It costs almost nothing.** Fees of 0.03–0.20% a year and very low
   turnover. Most active funds lose to their index over 15 years mostly
   through cost and through trading away from the winners.

**Why QQQ, VGT and XLK beat SPY.** They are concentrated slices, and the
slice they hold (large US technology) was the best-performing part of the
market for the last fifteen years. That is sector exposure, not skill.
QQQ ended the 2000s **below** where it started the decade, while SPY
did not. XLK lost roughly four fifths of its value from 2000 to 2002.
"Beat the benchmark for a few years" is what any concentrated slice does
in the years its slice wins. In every period, about half of all
concentrated slices beat the broad index. The ones we notice are the
ones that did.

**The efficient-market point is half right.** Public information about
a company is priced within days; our six failed routes are consistent
with that and nothing more. But the *structure* of a book is not
information, and structure is where the documented, persistent edges
live: momentum (buy what rose over the last year, skipping the last
month), quality (high, stable profitability), low volatility, and value.
Each has decades of evidence, each has had decade-long droughts, and each
has been shrunk by crowding. None of them is stock-picking. All of them
are allocation rules.

## 3. So how would I build the ETF?

Not by picking winners. The evidence, ours and the literature's, says a
small participant cannot do that from public information. The book that
has a real chance of beating QQQ on **return per unit of drawdown**, and
some chance on raw return, is:

- **Start from QQQ's holdings and weights.** That gives us the
  never-sell-a-winner property for free, and the same sector exposure as
  the benchmark, so we are not making a hidden sector bet.
- **Trim what B flags, sized by P9's severity, vetoed by raised
  guidance.** This is the one edge the index does not have. B's bottom
  191 were right 62% of the time against 47% by chance, and the
  end-to-end runs showed the analyst's value is in drawdown, not
  selection.
- **Trim proceeds go to the benchmark itself** (QQQ or SPY), never spread
  across the other names. Cash and the index are the only two places
  that do not require a bullish view.
- **Nothing else.** No stock selection, no sector tilt, no leverage. If a
  factor tilt is ever added, it is a separate pre-registered test on the
  same ruler, and momentum is the first one worth the look.

**What we would be claiming.** Same holdings and sector exposure as QQQ,
lower drawdown from flagged names, and therefore a better return per
unit of drawdown. On raw return the claim is weaker: trimming costs
return when B is wrong (38% of the time), and the market may recover a
flagged name. The 16-way leave-one-out on the current allocator already
showed this shape: better drawdown in all 16 cuts, better gain per unit
of drawdown in all 16, final value better in 15.

**What we would not be claiming.** That we found winners. Winner
selection stays with Luis, and the book carries them by default the way
the index does.

This is the P6D specification in one paragraph, and it is why 3.3's
first item should be written against cap weighting as the base book.

## 4. What it means for the decision

Nothing in the last three days changed the analyst. It changed what we
know about the market: call content and consensus are priced fast, and
the value of reading them is in seeing bad news clearly, not in seeing
good news early. The allocator rebuild is the place that knowledge pays.
The live forward test tells us in about a year whether it survives
contact with a market the model has never seen.
