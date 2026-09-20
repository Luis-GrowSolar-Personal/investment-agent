# R4 — the grading horizon: is 182 days the right question to ask?

**Run ID:** `r4-grading-horizon`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/R4-grading-horizon-out.md`
**Cost: $0. THIS RUN MAKES NO MODEL CALLS.** It re-grades eval caches already
on disk against a price cache already on disk. **If you are about to call the
Anthropic API, you have misunderstood the task — stop and report.**

**Read first:** `docs/handoffs/2026-09-19-state-of-play.md` §0 and §2;
`docs/architecture/PROMOTION_GATE.md` §3.1 and §3.1a;
`docs/architecture/PROMPT_ARCHITECTURE.md` §2.1 and §2.3;
`analysis/analyst_direct_scorer.py` in full; and the closing sections of
`wrap-ups/q2-bearish-strength-separation-out.md` and
`wrap-ups/P3-guidance-ledger-out.md` — this run exists because both of them
came back flat.

---

## 1. What this run is for

Two prompt-candidate rounds have now failed, and they failed the same way:
**every mechanically decomposable feature of an earnings call measures flat,
while the analyst's undecomposable bearish judgment carries about 13 points
of edge that replicates on fresh companies.**

- Q2: six ways to rank v6's own bearish calls. Five reversed between train
  and tune. The sixth had a 95% range of −4.3 to +27.0.
- P3a: guidance misses graded mechanically predicted underperformance
  **47.4%** of the time against a **46.6%** base rate. Clean beats predicted
  outperformance **30.4%** against **32.8%** — slightly *negative*. No metric
  cut and no magnitude cut rescued either.

There are two explanations for that pattern and this project has only
explored one of them.

1. **The signal is genuinely thin** — earnings information is priced quickly,
   and +13 points on 7.8% of calls is the residue that survives. If so, no
   prompt fixes it.
2. **We are grading against the wrong question.** Every number in this
   project — v6's 30.3%, the +2.53 gap, Q2's axes, P3a's diagnostics — is
   measured at **182 days, benchmark-relative, ±5%**. The dead band has been
   varied (±5/10/15/20, `PROMOTION_GATE.md` §3.1a R1). **The horizon never
   has.** `FORWARD_DAYS = 182` is a hardcoded constant in
   `analysis/analyst_direct_scorer.py` line 53 and has been since the scorer
   was written.

If an analyst reading one earnings call is making a statement about the next
quarter, and we grade it against six months, we would see exactly what we
see: a weak signal that does not decompose, because the outcome measure is
not aligned to the claim.

**This run varies the horizon and nothing else.** It is free, it re-uses
completed work, and it either reopens the question or closes it.

### The unreconciled inconsistency that prompted this

This project already measures forward returns at two different horizons and
has never reconciled them:

| file | `FORWARD_DAYS` |
|---|---|
| `analysis/analyst_direct_scorer.py` | **182** |
| `analysis/backtest_runner.py` | **90** |
| `analysis/backtest_from_files.py` | **90** |
| `analysis/corpus_construction_outcomes*.py` | 182 |

The analyst is graded at six months; the backtest measures at three. Nobody
has written down why. **That is a finding to report even if the horizon sweep
comes back flat.**

**What this run is NOT.** Not a promotion. Does not change the scorer's
default. Does not touch the prompt, the allocator, the trend layer, or the
holdout. It reports and stops.

---

## 2. Ground rules — the do-not list

1. **No model calls. No Anthropic API. No spend. No DB writes.**
2. **Do not modify `analysis/analyst_direct_scorer.py`.** Import from it, or
   copy the functions you need into the new driver. The 182-day default must
   stay the default until a design decision changes it, and that decision is
   not this run's to make.
3. **Do not touch the holdout.** Train and tune only. Assert zero holdout
   tickers in the input before anything else.
4. **Price cache is `analysis/data/corpus_v2/scorer_price_cache_v1.json`**
   (172 tickers). Never `analysis/data/price_cache.json` — a stale 66-ticker
   cache from an earlier era. **No cache refresh, no vendor calls.**
5. **Resolve every split symbol through
   `analysis/data/corpus_v2/TICKER_ALIASES.json` before enumerating.** The
   split names `ANTM`, `VIAC`, `GOOGL`; storage uses `ELV`, `PARA`, `GOOG`.
   Unresolved this silently loses 46 train calls. Assert 1,240 train eval
   files all map; `MAXN` resolves to nothing and that is expected.
6. **Exclude `WOLF` and `SPWR` entirely** — every call, not only those
   missing price data.
7. **Grade `per_call_rec`**, never `final_action`.
8. **macOS Tahoe, zsh.** `python3`, never `python`. Never
   `--break-system-packages`. No `apt`.
9. **A diagnostic that contradicts an expectation in this prompt is a
   finding, not a reason to stop.**

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/r4-grading-horizon/`. **Write
`progress.json` as the very first action.**

- `progress.json` — `prompt_sha256`, `driver_commit`, per-step status,
  `next_action`, `notes[]`.
- `cells.jsonl` — one line per (horizon × split × arm) cell, flushed as
  completed.
- `findings.md` — append-only, written the moment each finding is
  established, **including the §5 pre-registration, which is written before
  any cell is computed.**

---

## 4. Step 0 — hygiene

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`.
**0b.** Commit the driver as its own commit before it produces output:
`analysis/r4_horizon_driver.py`.
**0c.** No version guard is required — no scoring calls. Record that it was
skipped **and why**, so a later reader does not mistake it for an omission.

---

## 5. Pre-registration — write this to `findings.md` and commit BEFORE computing anything

This run sweeps six horizons. **Six is enough to hand back a winner that
looks better than it is** (`PROMPT_ARCHITECTURE.md` §2.3: six candidates
screened on one sample inflate the winner by about 1.5 points, and the effect
under investigation is ~2.5). Three rules, all mandatory:

1. **Write the predictions below into `findings.md` and commit, before the
   first contingency table.**
2. **Report every horizon, always.** A table of six where one looks good is a
   completely different result from one horizon tested and confirmed.
3. **Train discovers. Tune confirms.** Compute the full sweep on train first,
   then on tune. **A horizon that looks better on train and not on tune has
   not been shown to be better — say so in one sentence and move on.**

**Registered predictions, 2026-09-19:**

- **Primary:** v6's bearish-call edge over the base rate is largest at a
  **shorter** horizon than 182 days, most likely 60–90 days, because a single
  transcript speaks to the coming quarter.
- **Secondary:** the neutral-call edge stays at approximately zero at every
  horizon. Its 0.0 at 182 days replicated on both splits and is unlikely to
  be a horizon artifact.
- **Falsified if:** the bearish edge is flat across all six horizons (the
  horizon is not the problem, and explanation 1 in §1 gains a great deal of
  weight), **or** it is largest at 182 days or longer (the current default is
  already right).
- **A result where the edge peaks at a short horizon on train and not on tune
  is a negative result**, not a partial success.

---

## 6. The work

### 6a. Build the sweep — the only computation

Horizons: **30, 60, 90, 182, 270, 365 days.** All are feasible on the current
cache (latest price 2026-09-14, latest train call 2025-12-17): coverage is
100% through 270 days and 96% at 365. **Report the gradable count at each
horizon** — a horizon that silently drops calls is not comparable to one that
does not, and 365 days drops about 55 train calls.

Dead band stays at **±5%** throughout. Benchmark stays **SPY**. **Vary one
thing.**

For each horizon × split (train, tune), recompute ground truth from the price
cache and report, for each of the three predicted directions:

- calls made, share of all calls;
- hit rate;
- the **base rate for that direction at that horizon** — this moves with the
  horizon and is the whole point, so never quote a hit rate without it;
- **edge = hit rate − base rate**, with a 95% range from a **ticker-block
  bootstrap** (resample whole companies, fixed seed, recorded);
- overall accuracy and the luck-corrected gap.

Reference values at 182 days, from
`analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`
(pooled train+tune, WOLF/SPWR excluded): bearish 59.9% against 46.6% base
(**+13.3**); bullish 37.2% against 32.8% (**+4.4**); neutral 20.6% against
20.6% (**0.0**). **Your 182-day cell must reproduce these. If it does not,
stop and report the discrepancy before computing any other horizon** — a
mismatch means the re-grade is wrong and every other cell would be too.

### 6b. Two things to watch that are not the headline

**The base rates move with the horizon and that alone can look like a
result.** Over a longer window more stocks drift outside ±5%, so the neutral
base rate shrinks and the directional ones grow. **An edge is hit rate minus
the base rate at that same horizon** — never against 46.6%, which is the
182-day figure. Report the base-rate triple at every horizon in its own
column so the reader can see it moving.

**Overlapping windows.** At 365 days a company's consecutive calls cover
overlapping periods, so its observations are not independent. This is why the
range must come from a ticker-block bootstrap and not a binomial. Say so once
where the ranges are defined.

### 6c. Free extensions, only if the sweep shows something

**Do not run these unless the bearish edge varies materially with the
horizon.** If it is flat, the question is answered and the run is over.

- **Re-run Q2's axis test at the best-performing horizon.** Q2's six axes
  were all measured at 182 days. If a different horizon is the right ruler,
  they deserve one re-test at it — pre-registered, train-discovers,
  tune-confirms, all six reported.
- **Re-run P3a's 5d-i and 5d-ii** from `ledger_summary.csv` at that horizon.
  Same reasoning; the ledger is already built and costs nothing to re-grade.

Both are $0. Both are conditional. **Ranking them before the sweep is done is
the multiple-comparisons trap in a different coat.**

---

## 7. Report step

**Scope boundary: report, do not decide.** **Do not change `FORWARD_DAYS`, do
not amend `PROMOTION_GATE.md`, do not re-open any candidate.** Whether the
project's grading horizon changes is a §3.1a decision and it happens in
conversation with Luis, on the strength of this report.

Write `wrap-ups/R4-grading-horizon-out.md`. **Three forms** per `CLAUDE.md`:
the `.md`, a `.docx` with real Word tables, and a published artifact page.
**Open with §0, defined terms** — at minimum: horizon, dead band,
benchmark-relative return, base rate, edge, hit, bearish/bullish/neutral
call, ticker-block bootstrap, overlapping windows. Plain words, before any
identifier.

Open the body with this sentence, filled in:

> Graded at the current 182 days, v6's bearish calls beat the base rate by
> 13.3 points. Across horizons from 30 days to 365, that edge ranged from ___
> to ___ points, largest at ___ days. On tune the same sweep put the largest
> edge at ___ days. The neutral-call edge was ___ at every horizon.

Then the full six-horizon table for both splits, all three directions, base
rates in their own column. Then one plain paragraph per finding.

**Report the 90-versus-182 inconsistency (§1) whatever the sweep shows**, with
whichever horizon the evidence favours, and note that the backtest and the
analyst scorer currently disagree.

**Close with what it means for a decision, stated both ways.** If a shorter
horizon carries materially more edge: what changes — the scorer's default,
whether Q2 and P3a deserve a re-test at it, and whether the two closed
candidate rounds were closed against the wrong ruler. If the edge is flat
across horizons: say plainly that the horizon is not the explanation, that
this removes the last free hypothesis for why mechanical features measure
flat, and that the evidence then favours the thin-signal reading. **If
nothing changes either way, say that.**

**Plain-language discipline is binding.** Anchor every percentage to what it
is a percentage of — not "59.9% precision" but "of the 187 times it said
bearish, 112 turned out right." Write "points," never "pp." Lead with the
finding; method after or omitted. Short sentences, one idea each. Forbidden
without a one-line plain definition at first use: lift, baseline, base rate,
precision, recall, confidence interval, significance, distribution, variance,
artifact, null, bootstrap.

---

## 8. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. No `--break-system-packages`.
- Work on `sweep/db-corpus-baseline`.
- Provenance for every figure: file path plus key or column.
- One prompt in, one wrap-up out to `wrap-ups/R4-grading-horizon-out.md`.
- Commit the sweep output — it is the durable asset and every later round may
  want to re-read it.
- This run is short and free. There is no budget reason to stop early; if you
  do stop, mark the remaining cells `pending` with a precise `next_action`
  and say plainly that it is a partial run.
