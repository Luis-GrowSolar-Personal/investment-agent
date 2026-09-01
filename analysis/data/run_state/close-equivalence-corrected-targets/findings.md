# findings — close-equivalence-corrected-targets

Append-only.

## Seeded from superseded run `close-equivalence-and-run-cadence`

The following is copied in verbatim as prior context from
`analysis/data/run_state/close-equivalence-and-run-cadence/findings.md`
(that run's `cells.jsonl` is explicitly NOT reused — those 3 cells were
measured against the wrong target per this prompt's premise).

---

- Fresh start confirmed at session open: analysis/data/run_state/close-equivalence-and-run-cadence/
  did not exist. Step -1 resume protocol executed as a cold start, not a resume.
- Driver commit at session start: 3f8a5633c42908baa45c2b4648b18acfccc44575
  (analysis/bracket_three_modes_s11_corrected.py). No edits made to the driver
  in this session -- Step 1 (fourth-bug instrumentation) was not reached.
- This session stopped after scaffolding only (Step -1 and part of Step 0) due
  to a tight per-invocation reasoning/turn budget that is not sufficient for
  the bug-hunt instrumentation (Step 1), the hard gate (Step 2), the pooling
  re-derivation (Step 4), or the full cadence grid (Step 5), all of which
  require running and cross-checking real backtests. No cells were run; no
  numbers in this file are asserted as measured. See progress.json next_action
  for the precise resume point.

### Step 1 (fourth bug) — substantive progress, not yet closed

- Confirmed with the fresh 2026-09-01 corpus (n_events=195 total loaded,
  147 in the 2022-01-01..2024-06-12 window -- matches the prompt's stated
  figure exactly, ruling out corpus drift as a concern) that the divergence
  reproduces EXACTLY as previously reported: at QS on 2024-02-14, donors
  RUN, ENVX, EOSE, TSLA raise bit-identical dollar amounts in both the
  reference (`run_cell`/`make_funding_decide_fn`) and the session model
  (`run_session_sweep_cell`, cadence=single_event, scope=new_calls_only),
  but donor AAPL diverges: $488.31994388804986 (ref) vs $500.4806040355388
  (new).
- Tested and RULED OUT one hypothesis: `make_funding_decide_fn` backfills
  `day_state["start_of_day_value"][ticker]` the instant a ticker acquires a
  position mid-day (ref lines 337-338), and `run_session_sweep_cell` had no
  equivalent backfill anywhere. Implemented the missing backfill (mirroring
  the reference exactly) and reran Gate 1a: the swap_funding/2.5pp output
  was numerically IDENTICAL before and after the fix. AAPL was already held
  before 2024-02-14 (not a same-day starter), so the backfill branch never
  fires for this divergence. Change reverted (tree restored to HEAD).
- Localized the TRUE first point of disagreement much earlier than
  2024-02-14: diffing `daily_snapshots` total_value between `ref` and `new`
  (swap_funding, 2.5pp) shows exact agreement through at least 2023-12-11,
  then the first common sampled date after that -- 2024-01-24 -- already
  disagrees by -$68.5020827826811 (new higher than ref). No funding_log or
  displacement_log entries exist near 2024-01-24 in EITHER implementation.
  Per-ticker prices from `PriceLookup.from_cache()` for all 16 tickers
  (including SPWR, which delisted in 2024) resolve identically with no gaps
  on 2024-01-24. This rules out a stale/missing-price fallback difference.
- Because no funding/displacement/skip events register in either
  implementation between 2023-12-11 and 2024-01-24, and the two harnesses
  only share MTM snapshot dates at session/event boundaries (`new` only
  snapshots on session dates; `ref` snapshots every calendar day), the
  exact date the two portfolios' SHARE COUNTS first diverge within that
  ~6-week window is bracketed to (2023-12-11, 2024-01-24] but not pinned to
  a single day. The $68.50 gap is a fixed dollar amount that persists
  (~$65-68) through at least 2024-02-01, consistent with a one-time
  share-count or lot-basis divergence on ONE ticker riding forward at that
  ticker's price, rather than a recurring per-day drift.
- Next concrete step to pin the exact date: force `new`
  (`run_session_sweep_cell`) to record a snapshot every calendar day for a
  like-for-like diff against `ref`'s daily snapshots across
  2023-12-11..2024-01-24, OR instrument portfolio share counts per ticker
  (not just total_value) at every event/session boundary in that window in
  both implementations and diff those directly.
- Gate 1a result under `per_event_date` (Step 2, literal comparison against
  the two hard-coded targets from the SUPERSEDED prompt):
  `no_reserve_raw`/`off` PASSES to sub-cent ($141,836.56574946275 vs target
  $141,836.57, diff -$0.0043 -- rounding only). `swap_funding`/2.5pp FAILED
  by exactly -$626.83341928917692 (-0.329%) against the superseded prompt's
  target $190,481.16304357877 (now known to be a median, not a forward
  draw — that target is DISCARDED by this prompt).
- **[NOW KNOWN CRITICAL]** Noted but not chased at the time (tangential,
  does not block the above): calling `run_cell` directly for
  `swap_funding`/2.5pp with no seed/draw concept returns
  $189,781.58036163618, which is neither the fresh `new` output
  ($189,854.3296242896) nor the (superseded, wrong) prompt's stated gate
  target ($190,481.16304357877). **This corrected-targets prompt confirms
  $189,781.58036163618 IS the correct forward-draw target** — it is
  `results.forward_diagnostics.final_value` in
  `analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json`.
  The prior session dismissed this number as "tangential" reasoning
  incorrectly that the gate target must be the session model's own
  expected value — that reasoning was the actual error the design session
  is now correcting.

### Step 1 (fourth bug) — one genuine bug found and fixed; Gate 1a still fails (superseded gate)

- **Found and fixed a real bug** (commit cbba37e): `run_session_sweep_cell`'s
  year-end tax computation priced the forced-liquidation-for-tax sale off
  the year's LAST SESSION date, not the literal Dec 31 calendar date the
  reference (`simulator.py`, which walks every calendar day) uses. Trade
  log confirmed the exact effect: on 2023-12-31, AAPL's forced sale priced
  at $193.179993/0.351011sh in the buggy session model vs
  $192.529999/0.352196sh in the reference. Fixed by anchoring
  `prices_for_liquidation` to `date(sd.year, 12, 31)` directly. **Verified:
  2022 and 2023 year-end tax results (net_taxable, tax_owed,
  loss_carryforward_out, forced_liquidation_proceeds) are now bit-identical
  between the reference and the session model** (2022 → all zero; 2023 →
  net_taxable=452.05504419983913, tax_owed=67.80825662997587,
  forced_liquidation_proceeds=67.80825662997587).
- **This fix does NOT close the superseded Gate 1a** (against the wrong
  $190,481.16 target) — rerunning swap_funding/2.5pp after the fix gives
  the exact same final_value as before ($189,854.3296242896), an unchanged
  -$626.833419289178 gap. **Under the corrected target
  ($189,781.58036163618), this same $189,854.3296242896 result is only
  ≈$72.75 off (+0.038%)** — this is the "true gap" this prompt now asks
  Gate 1a to close.
- The daily_snapshots total_value diff still first disagrees at 2024-01-24
  by the same -$68.5020827826811, even though every buy/sell trade in
  (2023-12-11, 2024-01-25] is confirmed bit-identical between ref and new
  (the Dec-31 forced-liquidation trade included, post-fix). Trades match,
  the two 2023-year-end-tax computations match bit-exactly, yet total
  portfolio value still diverges by $68.50 with no visible trade or tax
  event to explain it in that window.
- Candidate next places to look (not yet chased, per this prompt's Step 2):
  (a) a cash-only bookkeeping path with no Trade object (dividend/interest
  accrual, if any exists in the simulator — §5 says cash earns no interest,
  so if such a path exists it may itself be a spec violation); (b)
  `portfolio.total_value`'s per-account cash aggregation, session-native vs
  daily; (c) a genuine trade whose `trade.trade_date` falls slightly
  outside the searched window but surfaces in the 2024-01-24 mark-to-market.
- The 2024 year-end tax computation shows a real difference (net_taxable
  -640.5381671561415 ref vs -642.7135084763096 new, a $2.17 difference) —
  but that computation runs at END of 2024, after the 2024-01-24 divergence
  already exists, so it is downstream, not upstream, of the $68.50 gap.

## This run (close-equivalence-corrected-targets) — new findings

(none yet — see progress.json next_action)

### Step 1 — target re-verification (this run)

- **VERIFIED.** `analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json`
  → `results.forward_diagnostics.final_value` = `189781.58036163618` — matches the
  prompt exactly. The same file's `results.final.median` = `190481.16304357877`,
  confirming the superseded prompt's target was indeed the **median across draws**,
  not a forward draw.
- **VERIFIED.** `analysis/data/run_manifests/step1-five-gates-manifest.json`
  → `results.detail[0]` = "[PASS] Gate 1: standing assertion (no_reserve_raw
  control = $141,837): $141,836.57". This is a **forward draw**
  (`no_reserve_raw`, `off`, forward draw section follows immediately). Matches.
- Neither figure disagrees with the prompt. No hard stop at Step 1's
  pre-run check.

### Step 2 — the residual $72.75 found and closed. GATE 1a PASSES BIT-EXACT.

**Root cause (fifth bug): the session model applied year-end tax in a
post-loop pass, so it never entered the simulation at all.**

`analysis/sweep_cadence_and_session_model.py`, `run_session_sweep_cell`: the
year-end-tax block sat at indent 4 — *outside* the `for skey, sd, in_scope in
sessions_list:` loop (old lines 774-808). It iterated `session_dates_seq` and
called `compute_year_end_tax(portfolio, ...)` for each year's last session, but
by then the session loop had finished. Two consequences:

1. **Every `daily_snapshots.append(...)` had already happened.** `compute_summary`
   takes `final_portfolio_value = snaps[-1].total_value`
   (`analysis/simulator/report.py:134`), so the headline final value was
   **entirely tax-free** — no year's tax was ever reflected in any snapshot,
   nor in max drawdown.
2. The shares sold to fund the forced liquidation kept compounding for the
   remainder of the run instead of being gone from 2023-12-31 onward.

The reference (`analysis/simulator/simulator.py:207-227`) walks every calendar
day and settles tax at its step 2 — after that day's trades, **before** that
day's mark-to-market — on Dec 31 of each year, plus a partial-year settlement
on the final day when that day is not Dec 31.

**First diverging calendar date: 2023-12-31.** That is the day the reference
settles 2023 tax (net_taxable = $452.06, tax_owed = $67.81, forced liquidation
proceeds $67.81 raised by selling AAPL at the Dec-31-anchored price) and the
session model did not. The previously-reported "first divergence at 2024-01-24,
−$68.50" was an artifact of snapshot granularity only: the session model
snapshots on session dates and the reference on every calendar day, so
2024-01-24 was simply the earliest *common* date after the true 2023-12-31
split. $68.50 is the same ~0.3522 AAPL shares marked at the 2024-01-24 price;
$72.75 is those shares marked at 2024-06-12. **This confirms candidate (c) from
the last run's list — an effect just outside the searched window — and refutes
candidates (a) and (b). No dividend/interest-accrual path exists, so §5's
"cash earns no interest" is NOT violated.**

**Fix** (`run_session_sweep_cell`): year-end tax moved inside the session loop.
- Before each session's decisions, settle any year whose Dec 31 has passed
  since the previous session (no trades occur between sessions, so the
  portfolio state is identical to settling on Dec 31 itself), with liquidation
  prices still anchored to the literal Dec 31 — commit `cbba37e`'s fourth-bug
  fix preserved.
- On a session falling on Dec 31, and on the final session when it is not
  Dec 31 (partial-year settlement), settle after that session's trades and
  before its mark-to-market, mirroring the reference exactly.

**Gate 1a result, both configs `single_event` / `new_calls_only` / forward draw:**

| Config | Measured (forward draw) | Target (forward draw) | Provenance of target | Diff |
|---|---|---|---|---|
| `no_reserve_raw`, `off` | $141,836.56574946275 | $141,836.57 | `analysis/data/run_manifests/step1-five-gates-manifest.json` → `results.detail[0]` | −$0.00425 (target quoted to the cent; rounding only) |
| `swap_funding`, 2.5pp | $189,781.58036163618 | $189,781.58036163618 | `analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value` | **$0.00000000 — bit-exact** |

**GATE 1a PASSES.** Both are forward draws on both sides of every comparison.

Side effect worth noting: `realized_gains` for `swap_funding`/2.5pp moved from
−$6,214.656367282603 (pre-fix) to −$6,208.332154513496 (post-fix), because the
forced liquidation now happens against the mid-run portfolio rather than the
final one. `max_dd` is unchanged at 0.1878154040258339 — the 2023 tax hit
($67.81 on a ~$150k portfolio) is far too small to move the peak-to-trough.

**Correction to a previously published number:** the superseded run reported
the swap_funding/2.5pp session-model forward draw as $189,854.3296242896 and
the divergence as first appearing 2024-01-24. Both are now superseded: the
correct forward draw is $189,781.58036163618 and the true first divergence is
2023-12-31. The −$626.83 gap that run reported was measured against a median
($190,481.16304357877) and is void.

### Step 3 — spec-correction delta: `trim_budget_scope`

`trim_budget_scope` did not exist as a parameter; added as a toggle to
`run_session_sweep_cell` (default `per_event_date` = reference behavior,
unchanged). §5 denominates the 25%-of-start-of-day donor trim budget in
**sessions**; the reference's `make_funding_decide_fn` keys its `day_state` off
`trade_date`, i.e. **calendar dates**.

**Structural point:** the two can only differ where one calendar date carries
more than one session — i.e. at `single_event` / `per_call` cadence. At any
fixed-`K` or seasonal cadence one session *is* one date, so the correction is
**identically zero** there. It is therefore not a knob that interacts with the
Step 5 cadence grid at all.

All figures below are **forward draws** (`single_event`, `new_calls_only`, no seed):

| Config | `per_event_date` (reference) | `per_session` (spec-faithful) | Δ$ | Δ% |
|---|---|---|---|---|
| `no_reserve_raw`, `off` | $141,836.56574946275 | $141,836.56574946275 | **$0.00** | 0.0000% |
| `swap_funding`, 2.5pp | $189,781.58036163618 | $190,465.98615398916 | **+$684.41** | **+0.3606%** |

Secondary effects, `swap_funding`/2.5pp, forward draw: max drawdown
0.1878154040258339 → 0.18461344585456324 (**improves** by 0.32pp);
displacements 198 → 241 (+21.7%); Adds attempted 96 → 96 unchanged; fully
funded 1 → 1; cumulative shortfall $3,077,679.73 → $3,082,594.55.

`no_reserve_raw` is untouched because it never trims a donor (0 displacements),
so the trim budget is never consulted.

**Report only — the default stays `per_event_date`.** Note this is the *forward
draw only*; it is not a median and has not been re-measured across draws.

**Coincidence worth flagging so nobody trips on it:** $190,465.99 sits within
$15 of the superseded prompt's bad target $190,481.16304357877
(`bracket-swap_funding-2.5pp-manifest.json` → `results.final.median`, a
**median across 15 draws**). These are unrelated quantities — one is a
forward draw under a spec correction, the other a median under the reference.
Do not read the near-match as corroboration of anything.

### Step 4 — pooling re-derived. The +34.4% claim is REFUTED.

Axis: `execution_order` `sequential` vs `pooled`, at `per_call` cadence,
`swap_funding`, `new_calls_only`, **7 draws (seeds 0-6)**. All figures below
are **medians across those 7 draws** — not forward draws. Ranges are
min/max across the same 7 draws; per Rule 2, overlapping ranges are **tied**.

| Limit | `sequential` median | `pooled` median | Δ% | `sequential` DD median | `pooled` DD median | Rule 2 |
|---|---|---|---|---|---|---|
| `off` | $146,260.37 | $146,218.41 | −0.029% | 35.81% | 35.81% | **tied** |
| 0.5pp | $123,290.06 | $123,276.80 | −0.011% | 6.10% | 6.11% | **tied** |
| 1pp | $147,326.65 | $147,296.53 | −0.020% | 11.45% | 11.46% | **tied** |
| 1.5pp | $165,240.91 | $165,185.21 | −0.034% | 16.22% | 16.23% | **tied** |
| 2pp | $177,069.49 | $177,007.16 | −0.035% | 19.47% | 19.46% | **tied** |
| 2.5pp | $189,994.57 | $189,903.31 | −0.048% | 18.80% | 18.84% | **tied** |
| 3pp | $199,436.70 | $199,481.77 | +0.023% | 22.19% | 22.24% | **tied** |
| 5pp | $183,500.25 | $185,095.67 | +0.869% | 30.33% | 30.31% | **tied** |

**Every cell is tied at 7 draws — the draw-to-draw range swamps the
execution-order effect at every limit.** The largest median gap anywhere is
+0.87pp at 5pp, and it has the opposite sign from six of the other seven.

**Answers to Step 4's explicit questions:**
- *Does pooling's advantage survive a tight ceiling?* There is **no measurable
  advantage to survive.** At per-call-date sessions pooling is a no-op within
  noise at every limit from `off` to 5pp.
- *Does it move the optimal limit?* **No.** Both orders peak at 3pp
  ($199,436.70 sequential / $199,481.77 pooled, medians) and both fall away at
  5pp.

**Why the last run's +34.4% at `off` and +0.7% at 2.5pp do not reproduce.**
Those were measured against a baseline that was not yet exact, and — more
importantly — they do not appear to have been an execution-order comparison
holding cadence fixed. Held fixed at `per_call`, the mechanism is nearly inert
by construction: a per-call-date session usually contains exactly one event, so
§3's evaluate-then-pool-then-deploy has nothing to pool. **Treat +34.4% as
withdrawn.**

**Limit surface at `per_call`, `pooled`, 7 draws (medians):**
`off` $146,218 · 0.5pp $123,277 · 1pp $147,297 · 1.5pp $165,185 · 2pp $177,007 ·
2.5pp $189,903 · **3pp $199,482 (peak)** · 5pp $185,096.
Rule 3: with `off` at the loose end the sign sequence reads `− + + + + + −`
across 0.5→5pp — a single sign change after the peak, **unimodal**, and the
peak at 3pp is interior, so the optimum **is bracketed**.

### Step 5 — the cadence grid (complete)

2268 cells at 7 draws (scan) + 1440 more at 15 draws (refine, limits 1.0-3.0).
`swap_funding`, `pooled`, conformant per-date trim cap. 3 phase offsets per K
(0, K/3, 2K/3; seasonal 0/10/20), phase-averaged. All grid figures are
**medians across draws, then averaged across the 3 phases** — never forward
draws.

**Best cell: `K`=30, `cash_deployment`, 1.5pp — $194,171.25 (15 draws), DD
median 22.96%, phase spread 5.84%.** At 7 draws the same cell reads
$194,820.44 / 22.96% / 6.01%; the ranking is stable between draw counts.

Top of the surface (phase-averaged medians; 15 draws where limit ∈ 1.0-3.0,
otherwise 7):

| Rank | K | Scope | Limit | Phase-avg median | DD median | Phase spread | Rule 4 |
|---|---|---|---|---|---|---|---|
| 1 | 30 | cash_deployment | 1.5pp | $194,171 | 22.96% | 5.84% | pass |
| 2 | 30 | cash_deployment | 2pp | $192,197 | 27.42% | 2.58% | pass |
| 3 | 7 | new_calls_only | 3pp | $189,538 | 25.29% | 7.56% | pass |
| 4 | 30 | new_calls_only | 3pp | $189,425 | 20.58% | 3.98% | pass |
| 5 | 60 | cash_deployment | 2.5pp | $187,706 | 18.47% | 8.60% | pass |
| 6 | 60 | new_calls_only | 3pp | $186,772 | 17.64% | 8.45% | pass |
| 7 | 14 | new_calls_only | 3pp | $186,610 | 24.02% | 1.03% | pass |
| 8 | 90 | cash_deployment | 3pp | $185,795 | 15.03% | 4.56% | pass |
| 9 | 90 | new_calls_only | 3pp | $185,509 | 15.10% | 7.26% | pass |

**Minimum viable cadence.** Every K from 7 to 90, and the seasonal variant,
has at least one Rule-4-viable cell above $180k. Nothing in the grid forces a
fast cadence: `K`=90/`new_calls_only`/3pp reaches $185,509 at 15.10% drawdown
against `K`=7's best of $189,538 at 25.29%. **The 90-day cadence gives up
2.1% of return for 10.2pp less drawdown.** In this corpus a slow cadence is
not the constraint people assumed.

**Rule 4** (median drawdown across draws ≤ 39.12% AND ≥2/3 of draws under it):
**90 of 108 scan cells pass.** All 18 failures are `cash_deployment` at loose
limits — the whole `K`=7 `cash_deployment` column from 0.5pp up (34.83-51.30%),
`K`=14 `cash_deployment` from 1.5pp up, and every `off` cell at K ≤ 30.
Where a cell passes, it passes with 100% share-of-draws; there is no marginal
2/3 case anywhere in the grid.

**Rule 3 (unimodality), per (K, scope), `off` at the loose end, immaterial
steps discarded (|Δ| < the smaller adjacent draw range):**
11 of the 12 (K, scope) surfaces are **unimodal** with an **interior,
bracketed** peak. The single exception is **`K`=7 / `cash_deployment`, which
is JAGGED** — signs read `+ - - - - - +`, peak at 0.5pp, and it is the one
surface where the loose end turns back up. That is also the column Rule 4
rejects outright, so nothing rests on it.

**Rule 3b (plateau = within 2.5% of the peak, sensitivity 1/2.5/5%):**
- globally: **1%** → {`K`30/cash/1.5pp} alone; **2.5%** → {`K`30/cash/1.5pp,
  `K`30/cash/2pp}; **5%** → 12 cells spanning `K`=7 through 90 and both scopes.
  The 5% plateau being that wide is the real signal: **the cadence choice is
  worth about 5% of terminal value, and the limit choice is worth more.**
- The global optimum is **bracketed** — 1.5pp is interior to [0.25pp, off].
- **Not bracketed** in two places: `K`=90 at both scopes has its 2.5% plateau
  running `{3pp, 5pp, off}` — i.e. touching the loose end. At a 90-day cadence
  the limit stops binding, so the sampled range does not bracket that
  surface's optimum. Flagging as Rule 3b requires.

### Step 6a — `minPositionPct` and the stub rule (K=30, cash_deployment, 1.5pp)

3 phases × 7 draws = 21 runs per floor. Medians across those 21.

| `minPositionPct` | Final median | DD median | Displacements (median) | Realized gains (median) | Distinct tickers (median) |
|---|---|---|---|---|---|
| 0 | $193,791.35 | 22.70% | 184 | −$4,337.58 | 15 |
| 0.25% | $193,714.87 | 22.65% | 130 | −$4,598.87 | 11 |
| 0.5% | $195,015.80 | 22.65% | 115 | −$4,925.75 | 10 |
| 1.0% | $197,808.57 | 22.53% | 103 | −$2,849.44 | 10 |

**Verdict: not pure housekeeping — mildly material, and favourably so.**
0 → 1.0% is **+2.07% final value** with drawdown flat (22.70% → 22.53%) and
**44% fewer displacements** (184 → 103). The draw ranges overlap heavily
(0% spans $189,398-$201,185; 1.0% spans $194,980-$205,565), so under Rule 2
these are **tied on return** — the floor's defensible benefit is the
displacement count and the collapse of the long tail of stub positions
(distinct tickers 15 → 10), not the return. Reported, not chosen.

### Step 6b — ordering confirmation (K=30, cash_deployment, 1.5pp, phase 0)

forward $189,397.52 · reversed $191,689.55 · seed1 $189,397.52 ·
seed2 $189,484.69 · seed3 $189,397.52. All are **single forward draws**, not
medians. **Spread = 1.21% of the median — under 2%, so ordering is answered
and needs no further sweep.** Three of the five are bit-identical, which is
expected: at a 30-day cadence most sessions carry one event, so shuffling
within a session is usually a no-op.

### Step 6c — staleness vs return per K

| K | Mean staleness | Best Rule-4-viable cell | Median final | DD median |
|---|---|---|---|---|
| 7 | 3.3 d | new_calls_only / 3pp | $189,538 | 25.29% |
| 14 | 6.7 d | new_calls_only / 3pp | $186,610 | 24.02% |
| 30 | 14.1 d | cash_deployment / 1.5pp | $194,171 | 22.96% |
| 60 | 28.5 d | cash_deployment / 2.5pp | $187,706 | 18.47% |
| 90 | 42.7 d | cash_deployment / 3pp | $185,795 | 15.03% |
| seasonal | 10.5 d | cash_deployment / 1pp | $182,533 | 29.38% |

Measured staleness tracks the predicted `K/2` closely (7→3.3, 14→6.7, 30→14.1,
60→28.5, 90→42.7), confirming §2's uniform-on-[0,K] model.

**Return is NOT monotonically decreasing in staleness.** The peak sits at
K=30 / 14.1 days, above both the fresher K=7 (−2.4%) and the staler K=90
(−4.3%). Drawdown, by contrast, IS monotone in staleness — it falls steadily
from 25.29% at K=7 to 15.03% at K=90. Fresher information buys return only up
to a point, and buys drawdown nowhere. The seasonal variant is the worst
risk-adjusted cell in the table: 10.5 days of staleness for a 29.38% drawdown
and the lowest return of the six.

### Step 7 — gates

- **Gate 1 (standing assertion, `no_reserve_raw` control):** PASS —
  $141,836.56574946275 vs $141,836.57 (`step1-five-gates-manifest.json` →
  `results.detail[0]`), rounding only. Forward draw both sides.
- **Gate 1a (this prompt's, `swap_funding`/2.5pp):** **PASS, bit-exact** —
  $189,781.58036163618 vs `bracket-swap_funding-2.5pp-manifest.json` →
  `results.forward_diagnostics.final_value`. Forward draw both sides.
- **Gate 2 (invariant #2, `target_pct <= cap_pct` at decision time):** PASS —
  max excess 0.000000pp over a 36-cell sample spanning K ∈ {7,30,90,seasonal,
  single_event}, both scopes, limits {1.5pp, 2.5pp, off}.
- **Gate 3 (invariant #9, session move ≤ limit, verified in AGGREGATE per the
  prompt's cash_deployment caveat):** PASS across all 3,908 recorded cells —
  every limit's worst observed aggregate move equals the limit exactly and
  never exceeds it.
  **One apparent breach, investigated and dismissed — reporting it because
  the prompt says a contradicting diagnostic is a finding.** At
  `single_event` cadence with `cash_deployment` scope, the aggregate reads
  4.5pp against a 1.5pp limit (and 7.5pp against 2.5pp) on 2022-02-16. That
  date carries **three separate sessions** — `single_event` makes one session
  per event, and three calls share that date — each moving exactly 1.5pp.
  Invariant #9 is **per session**, so per session it sits exactly at the
  limit. The 3× is an artifact of aggregating by calendar date rather than by
  session. This combination is not in the Step 5 grid either (`single_event`
  exists only for the equivalence gate, which uses `new_calls_only`).
- **Gate 4 (invariant #5, conditional):** PASS — **zero** skipped events across
  all 3,908 grid cells; nothing to classify, so no unclassifiable skip. (The
  6 known-§11 `insufficient cash in tax_advantaged` skips live in the
  `no_reserve_raw`/`off` control only.)
- **Gate 5 (independent drawdown recompute agrees within 0.01pp):** PASS —
  max |diff| 0.000000pp over the same 36-cell sample.

**No gate tests a condition §11 documents as a known unfixed defect.**
