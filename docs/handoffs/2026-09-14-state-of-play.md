# State of play — 2026-09-14

**Supersedes** `docs/handoffs/2026-09-07-state-of-play.md` and everything before
it. Earlier state-of-play documents are kept for provenance, not orientation.

**Branch:** `sweep/db-corpus-baseline`
**Written after:** the value-attribution investigation (Stages A–D), the
scorecard repair, the Rule 3 disposition, and four rounds of corpus
construction.

---

## §0 — Defined terms

Read this first. Several terms read as their own opposite, and two look alike
but are completely different things.

### Scoring dummies — these do not buy anything

A **scoring dummy** is a fixed answer on a quiz. It exists only to give the
analyst's score something to be compared against. Nobody trades it.

| Term | What it means |
|---|---|
| **Always-bullish guesser** | Answers "this stock will beat the market" on every single call, regardless of the transcript. Scores 46.2% on this data, because that is how often stocks actually beat the market. |
| **Always-flat guesser** | Answers "this stock will move roughly with the market" every time. Scores 11.7%, because that outcome is rare over six months in volatile names. |
| **Luck** | What the analyst would score by coincidence alone, given how often it says each answer and how often each outcome happens. Scores 39.6%. |

Older documents call these "baselines," which made them sound like portfolios.
They are not. Do not reuse that word for them.

### Portfolio arms — these do buy and sell

| Arm | What it actually does |
|---|---|
| **The control** | The real system end to end: analyst reads transcript, trend layer converts the call into an action, allocator sizes and funds the trade. |
| **Arm 0b** | Buys a small starter stake in each of the 16 companies the first time it appears, then never trades again. Leaves most of the money in cash. |
| **Arm 0c** | Splits the money into 16 equal slices, buys each company once, never trades again. The honest "do nothing" comparison. |
| **Arm 0** | Adds on every call, ignoring what the analyst said. Uses the real caps and funding rules. |
| **Oracle arms (D-both, D-up, D-down)** | Perfect calls, derived from knowing the future. **Look-ahead ceilings, never achievable results.** |

### The settled configuration, in plain English

The system checks the portfolio roughly every 30 days. It acts only on new
earnings calls, not stale ones. When it wants to buy something and has no spare
cash, it sells part of another holding to fund the purchase. It handles all of a
day's calls together rather than one at a time. And it limits how much any one
position can change in a single session.

That last limit is the one people misread. It is a **speed limit**, not a budget
and not a cap on position size. At its current setting of 2.5 points, a position
worth 10% of the portfolio can move to at most 12.5% in one session — even if
every rule says buy more. Worked example: the analyst says "add heavily" to a
name sitting at 5% of the portfolio, and the type cap would allow 35%. The
speed limit still stops the purchase at 7.5% that session.

### Kinds of number

- **Points** — the unit for differences between percentages. The analyst scores
  40.4%, luck scores 39.6%, so the gap is 0.8 **points**. Older documents write
  "pp"; do not.
- **Forward draw** — a single deterministic replay of the simulator. Every
  dollar figure in this document is one of these.
- **Median across draws** — the middle value of several randomized runs. Not
  used here. If you see a figure quoted without saying which it is, verify it
  before relying on it.
- **95% range** — how much a figure moves when the sample of companies changes.
  If the range includes zero, the effect cannot be told apart from nothing.

### Portfolio rules

- **Type A / Type B** — single-driver companies are capped at 35% of the
  portfolio, multi-driver platforms at 50%. Speculative names are capped at 15%.
- **Ratchet** — the graduated exit: trim to cap, then 40% more, then to 3%, then
  out.
- **Profit-take** — a rule that trims 5% of a position after a 25% gain. **It
  has never fired.**
- **Rule 3** — a guard that refuses to buy more of a speculative stock trading
  below its average cost. **It does not actually do this** — see §5.
- **ALL16** — the 16 companies the whole backtest runs on.

---

## §1 — The short version

Three findings, in the order they landed.

**The analyst's calls carry almost no information.** It gets 40.4% of calls
right. Luck gets 39.6%. The gap is under one point and cannot be told apart from
zero.

**The full machinery loses to doing nothing.** Buying the 16 companies in equal
amounts and never trading again returned $195,584. The complete system —
analyst, trend layer, allocator, every rule — returned $179,945. Doing nothing
wins by $15,639.

**But a perfect analyst would be worth $83,129 on the same machinery.** That is
the largest number measured anywhere in this project, and it is what says the
analyst is worth improving rather than abandoning.

Those three are consistent. The system is built to convert good calls into
money, and it does so efficiently. It is currently being fed calls that are
indistinguishable from guessing.

---

## §2 — The numbers

### What each portfolio made

| Arm | Final value | Worst fall | Cash idle |
|---|---|---|---|
| Buy starters, never trade (Arm 0b) | $120,800 | 12.7% | 65.5% |
| Zero-information analyst (Test 1) | $120,800 | — | — |
| Add on every call, ignore analyst (Arm 0) | $173,102 | 19.6% | 15.3% |
| **The real system** | **$179,945** | **20.9%** | **26.0%** |
| **Buy equally, never trade (Arm 0c)** | **$195,584** | **36.5%** | 8.3% |
| Perfect analyst, today's settings | $263,074 | — | 50.8% |
| Perfect analyst, no speed limit | $510,894 | — | — |

The last two are look-ahead ceilings. They assume knowing the future.

### Two ways the system looks good

**Per dollar actually invested per year**, the real system returns 0.383 against
buy-and-hold's 0.332. Its decisions are the most capital-efficient of any arm.
It ends with less money because a quarter of the account sits in cash.

**Per unit of loss**, it returns 79.9% with a 20.9% worst fall, against
buy-and-hold's 95.6% with a 36.5% fall — roughly 3.8 against 2.6. It is not
simply an under-invested version of buy-and-hold; scaling a portfolio down would
preserve that ratio, and this does better.

### What the analyst actually does

Across 359 calls on 16 companies:

| | |
|---|---|
| Calls right | 40.4% |
| Luck would get | 39.6% |
| Always-bullish guesser | 46.2% |
| Always-flat guesser | 11.7% |

Per answer:

| The outcome was | How often | The analyst caught |
|---|---|---|
| Beat the market | 46.2% (166) | 72.9% |
| Lagged the market | 42.1% (151) | **13.9%** |
| Moved with the market | 11.7% (42) | 7.1% |

It says "beat the market" on 70% of calls in a period when that was right 46% of
the time. It misses six of every seven real declines. When it does say sell, it
is right 47.7% of the time against a 42.1% base rate — slightly better than
chance, not catastrophic.

---

## §3 — The analyst has real headroom

A perfect analyst, run through the allocator exactly as configured today, would
have returned **$263,074** against the real $179,945. That is **$83,129** of
headroom without touching anything else.

Split by direction, per call actually changed:

| | Value | Calls changed | Per call |
|---|---|---|---|
| Perfect on the upside | +$63,973 | 22 | **$2,908** |
| Perfect on the downside | +$21,954 | 85 | **$258** |

Fixing one bullish call is worth about eleven times fixing one bearish call.
Counterintuitive, given that missing declines is the analyst's obvious failure —
but the upside fixes are rare and each is worth a great deal.

**Do not raise the speed limit.** With the current analyst, removing it makes
the system **$28,947 worse**. With a perfect analyst it is worth $247,820 more.
Speed amplifies whatever signal quality you have, and the current signal is
noise.

One caveat on the $83,129: the check meant to separate the analyst from the
trend layer came back at 100% on both levels, because the oracle's supporting
inputs were set never to contradict its own calls. So the figure is really
"perfect analyst **and** perfect trend layer." The direction holds; the size is
inflated.

---

## §4 — The scorecard was broken, and is now mostly fixed

### What was wrong

**It graded against the wrong dummy.** The promotion gate's §3.1 specifies an
always-**hold** comparison; the code implements always-**bullish** — the very
strategy §3.1 names as the thing to guard against. The same 359 calls produce
−5.8 points against one and +28.7 against the other. (Recorded as **F1**.)

**It reported no margin of error.** On the 195-call population the money
simulations use, the gap against the always-bullish guesser runs from 9.7 points
worse to 0.6 points better. Zero is inside that range.

**It could not see an improvement.** The smallest detectable difference between
two prompt versions was **6 points** compared on the same calls, 12 points on
different calls. A realistic single iteration is 2 to 4 points. So prompt
iteration was unverifiable at any version count.

That last one retroactively closes the v10 question: the published spread was 5
points at most, below both thresholds. **It was never decidable on this data.**

### What was done

The gate's primary metric is now the luck-corrected score plus balanced
accuracy, each with its 95% range, with the old definition preserved below it as
superseded. §3.1 now also requires that no prompt-versus-prompt comparison be
cited without its paired difference and range.

### Still open

**F2** — §3.1 specifies grading against each stock's sector ETF where one
applies; the code uses SPY for everything. Ten of the 16 companies sit in sectors
where that matters. Deferred, not resolved: it needs sector price history the
cache does not have, and it does not affect any dollar figure.

---

## §5 — The allocator: three of four rules do nothing useful

| Rule | Effect of turning it off |
|---|---|
| Profit-take at 25% | **$0** — it has never fired, not once in 2.4 years |
| Starter sizing | **$0** — the speed limit clips every purchase below the starter size, so it never reaches a trade |
| Position caps | +$813 earned, and the sign flips when NVDA is dropped — treat as noise |
| **Rule 3** | **−$9,418 — it costs money** |

**Rule 3 does not do what its name says.** When it refuses a purchase, the
funding logic treats the whole amount as unfunded and pays for it by selling
another holding. The stock still gets bought. The rule only changes *how it is
paid for*.

Three options were measured:

| | Final value | Worst fall | Forced sales |
|---|---|---|---|
| Keep it (today) | $179,945 | 20.9% | 71 |
| Remove it | $189,363 | 21.7% | 60 |
| Make it actually block | $184,460 | **17.6%** | **37** |

The status quo is beaten by both alternatives on money *and* on forced selling.
Under a perfect analyst, removing stays positive (+$2,313) while enforcing turns
negative (−$6,098) — so enforcing gets worse as the analyst improves.

**Decision: backlogged, not promoted.** Removing the guard and designing a real
one for falling speculative positions is a backlog item. The analyst is the
priority.

---

## §6 — The corpus

Sixteen companies was the binding constraint on the scorecard — and they are not
even 16 independent ones, being four solar, four battery and three semiconductor
names that move together.

A replacement corpus has been built, selected and frozen but **not scored**:

| | |
|---|---|
| Companies | **77** |
| Earnings calls, 2020–2025 | ~1,650 |
| Split | 28 train / 26 tune / 24 holdout (before Romeo's removal) |
| Projected detectable improvement | **2 points** at 54 companies available |
| Cost to score | **$33–83** |

**The holdout is locked**, with its hash recorded in the promotion gate document
and a standing instruction that it must not be scored during iteration.

### Selection discipline

Companies were picked from a **dated 2020-12-31 index snapshot** including names
later removed — at least 59 of the 2020 constituents are gone today, which is
what proves the source is not a survivor list. Selection rules were written down
and committed before any return was looked at. Outcome balance was measured only
after the list was frozen, and the rules forbid re-picking on it.

### What the corpus rounds taught us

**A failed company stops holding earnings calls.** The original rule required 12
calls, which meant it required survival, and it deleted exactly the companies
most worth studying. Fixed with a separate rule for that group.

**The vendor has no usage cap.** The 1,000-call figure was a refund condition,
not a quota. The plan allows 20 calls a minute with no monthly limit, so
transcript volume is bounded by clock time — about four hours for a
4,500-transcript ingest — and each extra transcript costs nothing.

**Alphabet is filed under GOOG, not GOOGL.** Your hint; confirmed. SVB Financial
is a genuine gap — the vendor has the company and not its calls.

**Three failures were verified as total losses** against SEC filings and the
FDIC record, so they grade as −100% without needing prices.

### Where it stands

Today: **53 companies available for iteration, 77 total.** The minimum for a
2-point threshold is 54 available. One short, with no margin. `corpus-fix-5`
adds about 30 and fetches the missing price history.

---

## §7 — Decisions made

1. **The analyst is the priority**, not the allocator. It has the largest
   measured headroom.
2. **Do not raise the session speed limit.** It makes the current system worse.
3. **Rule 3 changes are backlogged**, along with designing a real guard for
   falling speculative positions.
4. **Expand the corpus before iterating the prompt.** Improvements cannot be
   verified otherwise.
5. **Do not re-score the old corpus.** The model that produced it was retired in
   June 2026; re-scoring would change the prompt and the model at once and
   orphan every existing benchmark.
6. **Prompt files go to Code via `/execute-prompt`**, which handles git. No
   separate command sequences.

---

## §8 — Open items

**Blocking the scoring run**

- Price history for the three failed companies. The cache is completely empty
  for them, so per-call grading is impossible until it is filled.
- Corpus expansion to roughly 110 companies for margin.

**Unresolved measurements**

- Whether the analyst and trend layer's net contribution of **$6,843** above
  "add on every call" is distinguishable from zero. The attempt failed its own
  arithmetic check; a valid version needs roughly 2,000 full simulator runs.
- The trend layer's override rate — how often it changes the analyst's call, and
  how often it reorders funding priority. Never measured.
- The timing and selection shuffle tests. Never run.
- Per-call attribution by leaving one call out at a time. Never run.

**Data quality**

- **F2**: sector-relative grading, specified but not implemented.
- Stale availability fields. Honeywell was recorded as absent from the vendor
  and has 24 calls. Others may be wrong the same way.
- The failures group sits at 4 of 8. Most in-scope failures listed via SPAC in
  2021 and miss the 2020 eligibility rule.

**Backlog**

- Remove Rule 3; design a real guard for falling speculative positions.
- A dashboard showing live prompt version, allocator parameters, corpus
  composition, timeframe, and performance against benchmarks. Worth building
  only after the benchmarks are trustworthy again.

---

## §9 — What happens next, in order

1. **Run `prompts/corpus-fix-5-expand-and-prices.md`** — adds about 30
   companies, fetches the missing prices, re-checks the threshold.
2. **Commission the scoring run.** Roughly $50–100. This creates a new baseline;
   every existing benchmark becomes historical the moment it completes.
3. **Re-measure the analyst on the new corpus** with the repaired scorecard, to
   establish where it actually stands.
4. **Then iterate the prompt**, focusing on bullish accuracy, checking each
   version against the tune split and leaving the holdout alone.

---

## §10 — Where things live

| What | Where |
|---|---|
| Corpus manifest | `analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json` |
| Selection rules | `analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (A1–A7) |
| Ticker aliases | `analysis/data/corpus_v2/TICKER_ALIASES.json` |
| Holdout lock | `docs/architecture/PROMOTION_GATE.md` §10 |
| Value attribution | `wrap-ups/value-attribution-v2-stage-*-out.md` |
| Scorecard repair | `wrap-ups/scorecard-repair-out.md` |
| Rule 3 | `wrap-ups/rule3-disposition-out.md` |
| Corpus rounds | `wrap-ups/corpus-construction*-out.md`, `wrap-ups/corpus-fix-*-out.md` |
| Run state | `analysis/data/run_state/` |

---

## §11 — Limitations on everything above

- Every dollar figure describes 16 companies over 2020 to mid-2024, with **zero
  2025 calls**. A prior test put this universe at the top of 25 random draws — it
  is not representative, and buy-and-hold's strength here partly reflects that
  the companies were well chosen.
- The existing corpus is a score stream of **unverified prompt vintage**. 153 of
  362 rows fall outside the window used to date v6, and the comparison that would
  settle it has never been run.
- No dollar figure carries a margin of error. All are single deterministic
  replays.
- Every oracle figure assumes knowing the future.
- The new corpus is selected, not scored. Its projected threshold is a
  simulation, not a measurement.
