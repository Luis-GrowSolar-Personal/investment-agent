# R4b — short horizons, and the entry price: how much of the edge could you actually have traded?

**Run ID:** `r4b-tradeable-entry`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/R4b-tradeable-entry-out.md`
**Cost: $0. NO MODEL CALLS.** Re-grades eval caches already on disk against a
price cache already on disk. **If you are about to call the Anthropic API you
have misunderstood the task — stop and report.**

**Read first:** `wrap-ups/R4-grading-horizon-out.md` in full (this extends it),
`analysis/analyst_direct_scorer.py` (especially `PriceCache.price_on_or_after`
and the `p0` / `p1` fetch at lines ~360–365),
`docs/handoffs/2026-09-19-state-of-play.md` §0 and §2,
`docs/architecture/PROMPT_ARCHITECTURE.md` §2.3.

---

## 1. What this run is for, and why R4 cannot be read without it

R4 swept horizons from 30 to 365 days and found, **on train**, a bearish edge
that falls steadily as the horizon lengthens: **+23.2 points at 30 days,
+15.3 at 182, +10.1 at 365.** On tune it did not reproduce — but every tune
range spans zero, so tune could not adjudicate it either way.

**There is a defect in how that was measured, and it bites hardest exactly
where R4 found its largest numbers.**

The scorer's starting price is `price_on_or_after(ticker, call_date)` — the
close **on the call date**. Most US earnings calls happen after the close or
before the open:

- **Call after the close on day D.** The close on D is the **pre-announcement**
  price. The measured return therefore **includes the overnight announcement
  gap** — the 20% move the stock makes before anyone has read the transcript.
- **Call before the open on day D.** The close on D is already
  **post-announcement**. The gap is excluded.

So the current measurement **credits the analyst, on an unknown share of
calls, for a price move that happened before the transcript existed.** That is
not a signal anybody could trade. And because a one-day gap is a large
fraction of a 30-day return and a small fraction of a 182-day return, **the
contamination is concentrated precisely in the short-horizon cells R4 found
most promising.**

Test 6 examined look-ahead **in the prompt** — whether the model uses
hindsight. **Nobody has examined look-ahead in the ruler.** This run does.

**The question in one line:** how much of v6's measured edge survives if you
can only trade at the first price a transcript reader could actually reach?

**What this run is NOT.** Not a promotion. Does not change the scorer's
defaults. Does not touch the prompt, the allocator, the trend layer, the
ledger, or the holdout. It reports and stops.

---

## 2. Ground rules

1. **No model calls, no API, no spend, no DB writes, no cache refresh.**
2. **Do not modify `analysis/analyst_direct_scorer.py`.** Import from it or
   copy what you need into `analysis/r4b_tradeable_entry_driver.py`. The
   `p0 = price_on_or_after(call_date)` behaviour must remain the default until
   a design decision changes it, and that decision is not this run's.
3. **Do not touch the holdout.** Train and tune only; assert it.
4. **Price cache is `analysis/data/corpus_v2/scorer_price_cache_v1.json`**
   (172 tickers, daily, dense — verified: no gaps over 4 calendar days on a
   sampled series, runs to 2026-09-14). Never `analysis/data/price_cache.json`.
5. **Resolve split symbols through `TICKER_ALIASES.json` before enumerating**
   (`ANTM`→`ELV`, `VIAC`→`PARA`, `GOOGL`→`GOOG`). Assert 1,240 train eval
   files map; `MAXN` resolves to nothing, expected.
6. **Exclude `WOLF` and `SPWR` entirely.**
7. **Grade `per_call_rec`.** Dead band ±5%, benchmark SPY, unchanged.
8. **macOS Tahoe, zsh.** `python3`. No `--break-system-packages`. No `apt`.
9. **A diagnostic that contradicts an expectation here is a finding, not a
   reason to stop.**

---

## 3. Step −1 / Step 0

State in `analysis/data/run_state/r4b-tradeable-entry/`. `progress.json`
first, before reading anything. `cells.jsonl` flushed per cell.
`findings.md` append-only, **carrying §5's pre-registration before any cell is
computed.** Clean tree, hard stop on `git_dirty`. Driver committed as its own
commit before it produces output. No version guard needed — record that it was
skipped and why.

---

## 4. The two arms — this is the whole design

Every cell is computed **twice**, identically except for the starting price.

| arm | starting price `p0` | what it measures |
|---|---|---|
| **A — as-is** | close on the call date (`price_on_or_after(call_date)`) — **the current scorer's behaviour** | includes the announcement gap on after-close calls |
| **B — tradeable** | close on the **first trading day strictly after** the call date | the earliest price a transcript reader could actually reach |

The benchmark leg uses the same rule in each arm, so the comparison stays
benchmark-relative. The end price `p1` is unchanged: `price_on_or_after(call
date + horizon)` in both arms, so B measures a window one trading day shorter.
**State that asymmetry once; do not try to correct for it** — shifting the end
date too would change two things at once.

**A − B at each horizon is the announcement reaction.** That difference is the
quantity this run exists to produce.

### Horizons

**1, 2, 3, 5, 10, 21, 30, 60, 90, 182 days.** The first six are new; 30, 60,
90 and 182 overlap R4 so arm A must reproduce it.

**Reproduction gate, hard stop.** Arm A at 182 days must reproduce the
reference figures: pooled bearish **59.9%** hit against **46.6%** base
(**+13.3**), bullish **37.2%** / **32.8%** (**+4.4**), neutral **20.6%** /
**20.6%** (**0.0**); train bearish **+15.3**, tune **+11.2**. Arm A at 30, 60
and 90 days must reproduce R4's train edges of **+23.2, +20.2, +20.0**.
**If any of these disagree, stop and report before computing anything else.**

### Reporting per cell

For each arm × horizon × split, and for each of bearish / bullish / neutral:
calls made, hit rate, **the base rate at that arm and horizon** (it moves —
never quote a hit rate without it), **edge = hit rate − base rate**, and a 95%
range from a **ticker-block bootstrap** (resample whole companies, seed
recorded). Plus overall accuracy and the gap over luck. Report the gradable
count in every cell.

---

## 5. Pre-registration — write to `findings.md` and commit BEFORE computing anything

Ten horizons × two arms is twenty cells per split. **That is more than enough
to hand back a winner that is noise with a good story**
(`PROMPT_ARCHITECTURE.md` §2.3). Rules, all mandatory:

1. **Predictions committed before the first table.**
2. **Every cell reported, always.**
3. **Train discovers, tune confirms.** A pattern on train that does not appear
   on tune has not been shown. Say so in one sentence and move on.

**Registered predictions, 2026-09-20:**

- **Primary.** Arm A minus arm B is **large at 1–5 days, moderate at 30 days,
  and near zero at 182 days** — because one trading day is a large share of a
  three-day return and a negligible share of a six-month one.
- **Consequence if primary holds.** R4's headline — that the bearish edge is
  much larger at short horizons on train — is **substantially an artifact of
  the entry price**, and the +23.2 at 30 days shrinks materially in arm B.
- **Secondary.** v6's **+13.3 at 182 days is largely clean**: arms A and B
  agree there within their ranges, because a one-day shift cannot matter much
  over six months. **This run is as likely to vindicate the 182-day figure as
  to undermine it, and that is the point.**
- **Falsified if:** A and B agree at short horizons too (the entry price is
  not the issue, and R4's short-horizon shape is real), **or** they differ
  materially at 182 days (something is wrong beyond the announcement gap and
  the whole price join needs auditing).
- **Not predicted, reported either way:** whether arm B retains any edge at
  all at 1–5 days. A genuine post-announcement drift signal would show up
  there, and this project has never looked.

---

## 6. The call-timing diagnostic — free, and it interprets everything above

We do not know, per call, whether the announcement landed before or after the
close on the call date. **Infer it and report the split**, because arm A's
contamination applies only to after-close calls.

For each call, compute the benchmark-relative move on day D (previous close →
D close) and on day D+1 (D close → D+1 close). Classify:

- **gap on D** — |move on D| is much larger than |move on D+1| → the
  announcement was digested on D, so arm A already starts post-announcement
  and is uncontaminated for this call;
- **gap on D+1** — the reverse → the announcement was after the close on D, so
  **arm A includes the gap** for this call;
- **ambiguous** — neither dominates.

Use a stated, committed threshold (e.g. one move at least twice the other and
at least 2% in absolute terms). **The threshold is a judgment call: state it,
and report how the split moves if it is doubled or halved.**

Then report the headline figures **split three ways by this classification.**
If arm A's edge is concentrated in "gap on D+1" calls, that is the
contamination made visible, and it is the single most informative table this
run can produce.

---

## 7. Report step

**Scope boundary: report, do not decide.** Do not change the scorer's `p0`
rule, do not amend `PROMOTION_GATE.md` or `PROMPT_ARCHITECTURE.md`, do not
re-open a candidate, do not retract R4 — **note where R4's reading changes and
leave the decision in conversation with Luis.**

Write `wrap-ups/R4b-tradeable-entry-out.md`. **Three forms** per `CLAUDE.md`:
`.md`, `.docx` with real Word tables, published artifact page. **Open with §0,
defined terms** — at minimum: horizon, entry price, arm A / arm B, the
announcement gap, tradeable, dead band, base rate, edge, hit, ticker-block
bootstrap, gap-on-D / gap-on-D+1.

Open the body with this sentence, filled in:

> Measured the way this project has always measured it, v6's bearish calls
> beat the base rate by 13.3 points at 182 days and by 23.2 points at 30 days
> on train. Measured from the first price a transcript reader could actually
> have traded, those become ___ and ___. The difference is the announcement
> move, which is ___ points at 1 day, ___ at 30 days and ___ at 182 days. Of
> the calls, ___% appear to have announced after the close, which is the group
> where the old measurement included the gap.

Then the full two-arm table, both splits, all horizons. Then the §6 timing
split. Then one plain paragraph per finding.

**Close with what it means for a decision, stated three ways.** If the
182-day figure is clean and the short-horizon lift is mostly the gap: the
project's existing baselines stand, R4's short-horizon result is withdrawn,
and the tradeable edge is the modest one we already knew about. If arm B keeps
a real edge at 1–10 days: there is a post-announcement drift signal this
project has never measured, and that is a new and live direction. If arms A
and B differ at 182 days: every baseline figure in this project needs
re-examining, and that outranks everything else in the queue. **If nothing
changes, say that.**

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of. Write "points," never "pp." Lead with the finding. Short
sentences, one idea each. Forbidden without a one-line plain definition at
first use: lift, baseline, base rate, precision, confidence interval,
significance, distribution, variance, artifact, null, bootstrap.

---

## 8. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. No `--break-system-packages`.
- Work on `sweep/db-corpus-baseline`.
- Provenance for every figure: file path plus key or column.
- One prompt in, one wrap-up out to `wrap-ups/R4b-tradeable-entry-out.md`.
- Commit the sweep output; later rounds will want to re-read it.
- Free and short — no budget reason to stop early. If you do, mark remaining
  cells `pending` with a precise `next_action` and say it is a partial run.
