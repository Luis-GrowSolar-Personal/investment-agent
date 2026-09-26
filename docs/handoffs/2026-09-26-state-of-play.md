# State of play — 2026-09-26

**Reading version (renders correctly anywhere, phone included):** <https://claude.ai/artifact/UgtKzgxJzdXRKGA8o8u5NW>

**Supersedes `docs/handoffs/2026-09-24-state-of-play.md`.**
Branch: `sweep/db-corpus-baseline`. Layer 2 (analyst) work.

**If you read one thing:** the analyst is a **downside detector**. The
minimal prompt (B) on Sonnet spots stocks that will lag the S&P, right
about 62% of the time against 47% by chance. That skill repeats between
runs. It has **no information about big winners.** Five routes were
tried today, and none found a bullish signal in the transcript. A
screen on Opus found it **sharper on the downside**, and no better on
winners. **Decided:** research stays on Sonnet, B stays the incumbent,
Opus and Fable are held back to confirm finished work, and each tune
look is reserved for a candidate that finds winners. Next: a live
forward test on Sonnet and Opus, and peer read-through (P5) as the next
bullish candidate. Start at §3.

---

## §0 — Defined terms

**Plain-English summary first.** The project scores earnings calls with
an AI analyst. It then asks whether higher scores went with better
six-month returns against the S&P 500. Everything is measured on past
calls whose outcomes are known. Train calls are used to build ideas.
Tune calls are used once per idea to check it. Holdout calls stay
locked until the very end.

**The prompts**

- **v6.** The long rulebook prompt (~190 lines). Still what production
  runs.
- **B (P6B-minimal).** The 50-line prompt that asks for a score from −5
  to +5. **The research incumbent**: every new idea is measured against
  it.
- **P7 (three voices).** B plus a section separating the CFO's numbers,
  the CEO's claims and the analysts' questions. **Failed.**
- **P9 (expected return).** B, but it answers with an expected six-month
  return in points (e.g. "−15") instead of a score. **Failed on ranking;
  grades severity.**
- **P9-avg.** P9 scored twice per call and averaged. **Parked**, eligible
  for one tune look.

**The kinds of number**

- **Ranking strength.** Do higher scores go with higher returns? 0 means
  no relationship; 1 means perfect order. B sits near 0.10–0.13: weak but
  real. (Technical name: rank correlation.)
- **Right / hit rate.** A bearish call is right if the stock lagged the
  S&P by more than 5 points over six months. A bullish call is right if
  it beat the S&P by more than 5 points.
- **Chance / base rate.** How often that outcome happens whatever the
  analyst said. Lagging by more than 5 points: about 47% of calls.
  Beating by more than 5 points: about 33%.
- **Bottom 191 / top 235.** The same-size groups used to compare prompts.
  They are the 191 lowest-scored and 235 highest-scored train calls,
  matching B's own bearish and bullish counts. Comparing equal-size
  groups stops a prompt looking better just by calling fewer.
- **Big winner / big loser.** Beat or lagged the S&P by 20+ points over
  six months. Big winners are 12.6% of train calls.
- **Run (draw).** One complete scoring pass. Scoring the same calls twice
  gives slightly different answers.
- **Wobble (noise floor).** How much a prompt differs from itself between
  identical runs. B changes direction on 12.5% of calls, and its ranking
  strength moved 0.130 → 0.099. A new idea must beat that wobble to
  count.
- **Range.** A 95% range from resampling whole companies. If it includes
  zero, the data cannot tell the difference from nothing.
- **Train / tune / holdout.** 55 companies (1,217 calls) for building; 51
  (~1,169) for one check per idea; 53 locked.

**Allocator terms — unchanged, for orientation only.** The settled
configuration trades once a month. It puts money only into names that
just reported, funds buys by trimming a holding, and never moves one
position by more than 2.5 points of the portfolio in a session. Worked
example: a 5% position can end the month anywhere from 2.5% to 7.5%. In
the identifiers: `swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp,
`pooled`, `per_event_date`. **`X` is a per-position speed limit, not a
budget and not a size cap.** Reference result $184,819 on $100,000;
daily-marked drawdown 23.46%. See the 2026-09-19 allocator document.
Nothing here changes it.

---

## §1 What ran since 2026-09-24

All on train. Total spend **$140.63**.

| run | cost | outcome | wrap-up |
|---|---|---|---|
| B made incumbent; B's wobble measured | $28.74 | B changes direction on 12.5% of calls against itself; ranking 0.130 vs 0.099 | `B-champion-and-noise-floor-out.md` |
| P7 three voices | $34.07 | **Falsified.** Top 235 right 31.5% vs 47% target | `P7-three-voices-train-out.md` |
| P9 expected return, two runs | $60.31 | **Falsified** on ranking (run 2). Severity grading **confirmed on both runs** | `P9-expected-return-train-out.md`, `P9-second-draw-out.md` |
| P9 averaged vs B averaged | $0 | Passed the fixed reading by 0.0002; three of four alternate seeds fell below | `P9-close-and-averaged-comparison-out.md` |
| Winners missed, v1–v3 | $3.45 | B's notes carry no winner signal; beat-and-raise is not a winner signal | `winners-missed-*-out.md` |
| Opus screen, 300 calls | $14.06 | Opus reads differently; sharper on the downside | `opus-screen-out.md` |

---

## §2 What we know now

### 2.1 The bearish skill is real and repeatable

B's 191 lowest-scored train calls were right **62.3%** and **61.3%** on
two identical runs, against 47% by chance. Every candidate today kept it
(P7 58.6%, P9 62.8% / 61.8%).

### 2.2 There is no bullish skill, and the transcript route is nearly exhausted

- **Big winners are spread evenly across B's scores.** About 14% of both
  B's −2 calls and its +3 calls became big winners, against a 12.6% base.
  B's scale says nothing about winners.
- **Winners are not rebounds.** Their prior six-month return (median
  −3.6) matched everyone else's (−2.2). The stock's own price history is
  not a winner signal.
- **B's own notes don't separate winners.** A classifier reading only
  B's notes found raised outlooks, beats and favourable balance **no more
  often** on future big winners than on other calls.
- **Beat-and-raise is not a winner signal here, but it is a safety
  signal.** Calls where the company beat and raised its own guidance
  became big winners 11.2% of the time (others 13.1%) and big losers only
  8.6% of the time (others 19.1%). The documented post-earnings drift
  keys on beating **analyst consensus**, which transcripts do not
  contain.
- **B already reads beat-and-raise.** It scores about half of those calls
  +3 or higher (19% overall), and it called only 15 of its 191 bearish
  calls on a raise or beat. Those 15 were right just 40% of the time.
  (After-the-fact, 15 calls.) **A lead for the allocator rebuild:** don't
  trim a flagged name whose call raised guidance.
- **P7 failed.** The model labelled ~80% of CEOs as overselling and ~80%
  of answers as evasive, so the labels could not separate companies.

### 2.3 Severity can be graded

P9's expected-return number ranks outcomes **inside the bearish group**
on both runs (0.257 and 0.184, ranges above zero). Its most negative
fifth fell a median 8–10 points; its next fifth fell 4–5.5. B's scores
cannot do this. P9 still failed as a replacement: it wobbles more than B
(17% direction changes vs 12.5%; ranking moved 0.060 vs 0.031), and its
second run could not show it ranks at least as well. **Use:** trim sizing
in the rebuilt allocator. P9-avg is parked, eligible for one tune look.

### 2.4 Opus is sharper on the downside

B's prompt, unchanged, on `claude-opus-5-5`, 300 train calls, one run:

- It disagreed with Sonnet on 34% of calls, against Sonnet's 15% with
  itself. It shifts the whole scale down: only 8 of 300 calls scored +3
  or higher, against Sonnet's 70.
- **Ranking strength 0.270 vs B's 0.131** (both B runs averaged). The
  paired gain is **+0.14** (range +0.07 to +0.22). *This comparison was
  computed after the run, not pre-registered.*
- **The gain is on the downside.** Opus marked future big losers down
  hardest (−1.25 points below B on average) and future big winners least
  (−0.55). It did not score winners higher.
- **Recall is not the leading explanation.** Famous winners were not
  lifted. The gain is as large on less-known companies (+0.15) as on
  megacaps (+0.13). It persists, smaller, on calls with no dramatic move
  (+0.09, range −0.02 to +0.19).
- **Cost:** $0.047 per call, 2× Sonnet. Opus always runs with built-in
  reasoning ("thinking"), which is part of what "Opus" means here.

### 2.5 The measuring instrument

- **Single runs are not enough.** B, P9 and P9-avg each landed in the
  too-close-to-call band on one run. Two runs per candidate are now
  standard.
- **Two classifier designs failed on their own definitions.** Each
  defined a label by something B writes in almost every note. The 60-call
  early check caught both, for under a dollar.
- **Fixed cut-offs don't transfer between models.** Opus rarely reaches
  +3, so "≥ +3 is bullish" makes it look useless on the bullish side
  whatever it saw. Compare models by ranking and same-size groups only.

---

## §3 Decisions, 2026-09-26

1. **B is the research incumbent. Production stays on v6.**
2. **Every candidate runs two times on train from the start**
   (`PROMPT_ARCHITECTURE.md` §2.3a rule 7).
3. **Model policy.** Research iterates on **Sonnet**. **Opus and Fable
   are used sparingly**, once, to confirm a finished Sonnet candidate:
   keep it if it's better, drop it if not. **Opus is recorded as a
   finding, not made the incumbent**, so future candidates are not forced
   onto the costlier model. A model step is judged **by ranking and
   same-size groups, never by fixed cut-offs.**
4. **The research incumbent and the production model are separate
   decisions.** At 15 names, live scoring on Opus costs pennies. If Opus
   holds up, production may run on Opus while research stays on Sonnet.
5. **Tune looks are reserved for a candidate that finds winners without
   hurting the bearish side.** P9-avg stays parked.
6. **Git bookends** (`CLAUDE.md` rule 9). CLI runs commit their own
   prompt at the start and push at the end.

---

## §4 Next

| # | step | cost | why |
|---|---|---|---|
| 1 | **Bookkeeping**: add the model-policy rule (§3.3) to `PROMPT_ARCHITECTURE.md` §2.3a as rule 8; record the Opus screen as a finding in the registry and ledger | $0 | decisions belong where future sessions read them |
| 2 | **Live forward test**: score each new earnings call for Luis's names with B on Sonnet **and** Opus as it comes out; grade six months later | pennies per call | the only test memory cannot touch; its results take six months, so start now |
| 3 | **P5, peer read-through**, on Sonnet, two runs | ~$60 | the one untried transcript-based route to winners: a supplier's call can reveal its customer's next quarter |
| 4 | **Consensus data** (restart the stalled vendor thread) | TBD | the documented bullish signal needs analyst expectations |
| 5 | **Allocator rebuild around the downside skill** | TBD | index-like by default; trim what the analyst flags; P9 severity sizes the trim; "raised guidance" as a trim veto. P6D is its first task |

---

## §5 Open, not scheduled (carried)

Settle `PROMOTION_GATE.md` §3.1a R3; terminal-value grading (WOLF, SPWR,
NOVA); BK/BNY history; `ratchetTranche` null on 26% of bearish calls;
trend-layer override rate; the Rule 3 guard; the state dashboard.
`whats_live.py` does not report the research incumbent. The pooled v6
swap-median discrepancy (7.70 vs 8.7) is moot now that v6 is not the
comparator. Sector-relative grading is unresolved; dividends are ignored.

---

## §6 Commits this period

B incumbent and noise floor (`de215db`, `7ba33b5`) · P7 (`0998735`…,
bookkeeping `f56745a`) · P9 (`a9664a1`…, second run `93ae8e1`…) · P9
close-out `e7c356a` · winners v2 bookkeeping `0049f7e` · Opus screen and
winners v3: see `git log`.
