# Close the open questions from the analyst-sensitivity review

Follow-up to `prompts/analyst-sensitivity.md` /
`wrap-ups/analyst-sensitivity-out.md`. **Read §0 of
`docs/handoffs/2026-09-03-state-of-play.md` before starting** — it defines every
term used here.

## Why this run exists

A first pass has already been run from an uncommitted scratch driver
(`analysis/resolve_open_four.py`, currently untracked). It answered four of five
questions and refuted the fifth. **Its numbers are not citable** — no manifest,
no `git_dirty` record, no `config_hash`, and the driver was written by a session
that could not execute it. This run's job is to put those answers on a clean
footing, close the one that reopened, and test the one consequence that could
move the settled configuration.

Three published figures and two documented claims are blocked until it lands.

**No LLM calls, no API spend, no DB writes, no cache refresh.**
`price_cache.json` / `fundamentals_cache.json` stay frozen at 2026-05-11; the
staleness warning is expected. Clean window (2022-01-01 → 2024-06-12), ALL16,
`decide_v3`, frozen-JSON `type_for_ticker`, dedup **on**. Settled cell unless a
step says otherwise: `swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp,
`pooled`, `per_event_date`. Work on `sweep/db-corpus-baseline`. Write findings
to `./wrap-ups/resolve-open-four-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`resolve-open-four`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.

**Write state before reading anything.** Create the directory and an initial
`progress.json` — every step `pending`, `next_action` "spec reading not yet
started" — as the very first action of the session. Then flush `cells.jsonl`
after every cell, update `progress.json` after every step, and append to
`findings.md` the moment a finding is established.

**Step 4 is the highest-stakes item** — it is the only one that can disturb the
settled configuration. **Step 2 is the only one still genuinely open.** If
budget runs short, do Steps 1–3 (cheap, mostly re-runs) and stop cleanly with a
precise `next_action` for Step 4 rather than rushing it.

## Step 0 — hygiene and the driver

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Do not stage
unrelated working-tree changes — stash and pop. `testing/` stays gitignored.

`analysis/resolve_open_four.py` exists and runs, but was authored blind and has
already had one signature bug (`cadence_days` / `funding` / `exec_order` — the
real kwargs are `cadence` as a **string**, `funding_mode`, `execution_order`).
**Review it line by line against the code it claims to read**, fix anything else
wrong, then **commit it as its own commit before any manifest**. Do not run a
manifest against an uncommitted driver. If you would rather rewrite it, do — but
commit the driver first either way.

---

## Step 1 — put the settled answers on a clean footing

These four are believed resolved. Re-establish each **under a manifest**, and
treat any mismatch as a finding.

### 1a. Drawdown granularity — the ruler

`report.py:_max_drawdown` runs over `SimulationResult.daily_snapshots`, which
the session harness fills **one entry per session date**
(`sweep_cadence_and_session_model.py:958-959` says so in its own comment) — for
the portfolio and, via `compute_summary`, for every benchmark.

Daily NAV is recoverable without touching the simulator or allocator, because
share counts are constant between session dates:

```
for each session snapshot s, with `nxt` = the next session date (else END+1):
    shares[t] = s.position_values[t] / prices.price_on(t, s.date)
    for each calendar day d in [s.date, min(nxt, END)]:
        nav(d) = s.cash_total + sum(shares[t] * prices.price_on(t, d))
```

**Confirm this assumption explicitly**: every entry in
`portfolio.transaction_log` should fall on a session date. Say so, with a count.

Figures to reproduce (first pass, phases 0/10/20, seed 0):

| phase | final | dd session | dd daily | understated by |
|---|---|---|---|---|
| 0 | 179,945 | 20.85% | 22.78% | 1.93pp |
| 10 | 189,914 | 15.96% | 24.20% | 8.25pp |
| 20 | 184,599 | 15.16% | 23.39% | 8.23pp |
| **phase-avg** | **184,819** | **17.32%** | **23.46%** | **6.14pp** |

Benchmarks, buy-and-hold from 2022-01-01: daily **SPY 25.36 / QQQ 35.25 /
TMFC 32.99**; K30 phase-0 session-sampled **21.99 / 33.75 / 31.60**.

The phase-averaged final and the session drawdown reproduce the published
headline exactly, which is what identifies the published figure as
session-sampled while the published benchmark figures are daily. **Restate the
§2 comparison with both sides on the daily ruler** and report the advantage over
each benchmark before and after.

Also report the phase spread on each ruler — first pass gave session 15.16–20.85
(5.69pp) against daily 22.78–24.20 (1.42pp). If that holds, **state-of-play
§5.2 anomaly #2 closes as a sampling artifact**, not a fact about trade timing.

Note the reconstruction starts at the first session date, so phases 10 and 20
omit 10/20 leading all-cash days at $100k. Say whether including them changes
anything (it should not — they can only raise the running peak marginally).

**EW is still not computed by this driver** (`baseline.py` has SPY/QQQ/TMFC
only). Do not quote the published EW figure as if it were measured here; say it
is unmeasured on both rulers.

### 1b. SPWR

First pass: SPWR has **one** scored event, `2024-05-02`, `rec='Trim'`,
`confidence='unknown'`, `size=3.0`. The first-call starter **did** queue at the
2024-05-20 session — `target_cap_log` shows a 5.0% starter leg — and
`funding_log` shows `intended_dollars 8062.74`, `target_buy_dollars 4031.37`
(halved by `X`=2.5pp), `actual_dollars 0`, **`binding: 'cash available'`**.
Ever-traded and held-at-end are both 15.

So the absence is a **funding failure in a fully-invested portfolio**, not a
decision. Confirm, and additionally: SPWR traded 1.17 → 1.48 (**+26.5%**)
between that session and 2024-06-12, so the exclusion **cost** roughly $1,069
inside the window; the August 2024 bankruptcy is outside it and invisible to the
backtest.

**Write the replacement sentence for state-of-play §5.1** (do not edit the
document). The claim being retired is *"the only genuine rejection is SPWR —
never held, in any draw, at any point"* and its framing as the most encouraging
fact in the table.

Then re-derive the **zero-information arm's 16th ticker**. Under zero
information the analyst never issues an Add, so far less cash is deployed and
SPWR's starter can fund — confirm that is the mechanism, since the sensitivity
wrap-up's explanation of the 15/16 split does not survive 1b.

### 1c. Gate scope

First pass, `analyst_direct_scorer` methodology unmodified, via
`analyst_sensitivity_lift.lift_for_events`:

| scope | lift | n |
|---|---|---|
| ledger entry-1 scope | +5.17pp | 58 |
| ALL16 | −3.08pp | 195 |
| ALL16 established | −6.31pp | 111 |
| ALL16 speculative | +1.19pp | 84 |
| AVGO/NVDA/ORCL/TTD (~73% of portfolio) | −3.57pp | 56 |

`data/gate_ledger.json` entry 1 scopes to `ENPH, TTD, AMPX, ENVX, EOSE, QS,
SPWR` — seven names, **no established names at all**, ENPH not in ALL16 — with
champion 4.94pp (n=81), challenger −2.50pp (n=80), `delta_pp −7.44`,
`noise_std_pp 4.2`, `pct_tickers_improved 28.6` (2 of 7), and **holdout n=0 on
both arms**. The +5.17pp corroborates the champion's 4.94pp closely enough to
validate the scope reconstruction; say whether you agree.

**Report the numbers and the reframing; do not resolve §4.5 and do not amend
`PROMOTION_GATE.md`.** State plainly that the lift baseline is *always predict
bullish*, which is a punishing benchmark for mega-caps in a rising window, and
that direction-calling and position-sizing are different skills — the metric
measures the first while the zero-information control shows the portfolio is
paid for the second.

### 1d. sonnet-4-6 error direction — record as undetermined

First pass: champion `n=6`, all `Add` (mean ordinal 0.000); challenger `n=36`
(Add 13 / Hold 1 / Trim 18 / Exit 4, mean ordinal 1.361); **paired rows: 0**.

With no overlap the comparison is confounded and six all-`Add` rows are not a
baseline. Record it as **undetermined**, note the directional signal (61% of
challenger calls are Trim or Exit, which if real is the harness's `pessimistic`
arm at ~$42,700 rather than `adjacent` at ~$24,886), and **hand it to Test 4**,
which needs paired re-scoring anyway. Do not run new scoring here.

---

## Step 2 — the one still open: why the tie-break seed never binds

**Both prior explanations are refuted; do not re-assert either.**

- The analyst-sensitivity wrap-up said the corpus has no two events on the same
  date. First pass: **36 dates carry 2+ events, 83 events sit in them.**
- The review said exact `rank_key` ties never occur because `gap` is continuous.
  First pass: **328 tied candidate pairs across 13 of 27 sessions**, e.g.
  `(1, -35, 0.9211…)` seven times in one session.

Ties are abundant. The RNG has every opportunity to bind. 15 seeds still give
exactly one final value, `179944.906085`.

**Hypothesis to test.** Ordering changes an outcome only when funding is
scarce-but-nonzero. Through 2022 the portfolio is ~73% cash, so every candidate
is fully funded and order is irrelevant; from mid-2023 it is at 0% cash, so
nearly every candidate receives $0 (SPWR's log entry is exactly this) and order
is equally irrelevant. The tie-break can only matter where cash runs out
**partway down** the ranked list.

**Measure it.** From `funding_log` at the settled cell, per session: candidates,
fully funded (`shortfall < 1.0`), unfunded (`actual_dollars < 1.0` with
`intended_dollars >= 1.0`), and **partially funded
(`0 < actual_dollars < intended_dollars`)**. Report the count of sessions with
at least one partial fill, and cross it against the sessions that contain
`rank_key` ties. If no session has both a tie and a partial fill, the seed
provably cannot change an outcome at this cell — and the cause is the **funding
regime**, not the corpus and not the sort key.

**If that is not the explanation, say so and find the real one.** A third wrong
answer recorded as fact is worse than an open item.

Two things to resolve while in here:

1. **The multiplicity artifact.** `sort(key=…)` calls the key once per element,
   so one ticker producing 7 or 8 identical `rank_key` tuples inside a single
   session means either the sort runs repeatedly or the candidate pool is
   rebuilt in a loop. Explain which. It may be benign; it may mean the pool is
   larger than intended.
2. **`hash(cadence)` is a reproducibility defect.**
   `tie_rng = random.Random((seed or 0) * 7919 + hash(cadence) % 1000)` hashes
   the *string* `"30"`, and Python randomizes string hashing per process, so the
   same cell with the same seed draws a different stream in a different process.
   Harmless while the RNG never binds; not captured by `config_hash`; latent at
   any cell where it does bind. Report it, propose the fix (int cadence or a
   pinned `PYTHONHASHSEED`), **do not apply it in this run.**

Then state, with a number: **how many published 15-draw ranges on the tie-break
axis are single points**, and which figures that affects.

---

## Step 3 — write the requote list

Not a computation. A plain list, in the wrap-up, of every published figure and
documented claim that this run changes, each with the old value, the new value,
where it is published, and what it should say instead. At minimum: the §2
drawdown headline, the SPY comparison, §5.2 anomalies #1 and #2, §5.1's SPWR
claim, and §4.5's framing.

The design session will apply these; **this run must not edit
`docs/handoffs/2026-09-03-state-of-play.md` or any spec.**

---

## Step 4 — does the settled configuration survive the correct ruler?

**The consequence that matters.** `X`=2.5pp was adopted as an interior optimum
chosen **for risk-adjusted return** (state-of-play §0.1: every funding mode
produces a smooth curve with an interior optimum at 2.5–3pp, roughly doubling
the unconstrained result). Every drawdown in that sweep was session-sampled.
Step 1a shows the understatement is large (up to 8.25pp) and **varies by phase**;
if it also varies with `X` — plausible, since `X` governs how concentrated and
therefore how volatile the path becomes — the optimum can move.

**Re-measure the `X` axis on the daily ruler.** Settled cell in every other
respect; `X` ∈ {0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, off}; phases 0/10/20;
seed 0 (Step 2 establishes whether draws add anything — if it confirms the seed
is inert here, **say so and do not run 15 pointless draws**).

Per cell report final value, session-sampled dd, daily-marked dd, and the gap.
Then answer directly:

- Does the interior optimum sit at the same `X` on both rulers?
- Does the understatement itself vary systematically with `X`? Report it as its
  own column — that is the mechanism, and it is more informative than either
  drawdown alone.
- On the daily ruler, does any cell breach the **39.12%** Rule 4 ceiling? Note
  that the ceiling was itself calibrated on session-sampled numbers, so it is
  internally consistent but understated in absolute terms. **Report both, and
  do not adopt a new ceiling.**

Cheap: the analyst-sensitivity run measured ~0.09s per cell after a ~2.7s corpus
load, so this whole grid is well under a minute of compute.

**If the optimum holds at 2.5pp on the daily ruler, say so plainly and
prominently** — that is the outcome that leaves the settled configuration
standing, and it deserves as clear a statement as the alternative.

---

## Rules

**Rules 1, 2 and 4 unchanged.** Rule 2: overlapping ranges are **tied**,
reported as tied, never ranked by median.

**Every drawdown figure in the wrap-up must say which ruler it uses** —
session-sampled or daily-marked — including figures quoted from earlier work.
That distinction is the point of this run and an unlabelled drawdown is not a
usable number. **State for every figure whether it is a forward draw, a median
across draws, or a phase-averaged median.**

## Report

Scope boundary: **report, do not decide.** Do not adopt a configuration, a
ceiling or a model; do not amend a spec, a gate or `versions.js`; do not resolve
any open item; do not edit the state of play.

Open with resume status, then:

> **Ruler: published 17.32% is session-sampled; daily-marked is [X]%.
> Advantage over SPY [X]pp, was 8.04pp. §5.2 #2 [is / is not] a sampling
> artifact. SPWR: [reason]; §5.1 should read [X]. Seed: never binds because
> [reason]; [N] published ranges are single points. Gate scope: ledger [X]pp
> (n=) vs the four names carrying the portfolio [X]pp (n=). sonnet-4-6:
> undetermined at paired n=0. X-axis on the daily ruler: optimum at [X]pp,
> settled configuration [stands / moves].**

Flag plainly: every previously published number that turns out to be wrong, any
figure that must now be requoted, any rule that gives an uncomfortable answer,
and whether anything disturbs the settled configuration.

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop** — and that explicitly includes the first-pass
figures quoted throughout, which were produced without a manifest and are
hypotheses until you reproduce them.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**, no cache refreshes.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — the manifest path and exact
  JSON key, or the commit and path.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
