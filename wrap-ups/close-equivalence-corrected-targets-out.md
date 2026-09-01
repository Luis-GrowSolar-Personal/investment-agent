# close-equivalence-corrected-targets — out

**Prompt:** `prompts/close-equivalence-corrected-targets.md`
**run_id:** `close-equivalence-corrected-targets`
**Branch:** `sweep/db-corpus-baseline` · **Date:** 2026-09-01
**Status: COMPLETE.** All eight steps run. Not a partial run.

---

> **Gate 1a, corrected targets: PASSED.** Residual, if any: **$0.00 — bit-exact**
> (was $72.749263 on arrival); first diverging calendar date **2023-12-31**,
> cause **the session model applied year-end tax in a post-loop pass, so no
> year's tax ever entered the simulation or any snapshot.** Spec-correction
> deltas: `per_session` trim budget **+$684.41, +0.3606%** (forward draw,
> `swap_funding`/2.5pp; exactly $0.00 for `no_reserve_raw`/`off`, and
> identically zero at every fixed-K or seasonal cadence). Pooling: **−0.029%**
> at `off`, **−0.048%** at 2.5pp — **collapses**; every limit is a Rule-2 tie
> and the previously published +34.4% is withdrawn. Minimum viable cadence:
> `K` = **90** (every K from 7 to 90 has a Rule-4-viable cell above $180k).
> Best cell: `K`=**30**, scope=**cash_deployment**, limit=**1.5**pp —
> **$194,171.25** phase-averaged median across 15 draws, **22.96%** median
> drawdown. Limit surface: **unimodal** on 11 of 12 (K, scope) surfaces,
> **jagged** on `K`=7/`cash_deployment` only; plateau **{`K`30/cash/1.5pp,
> `K`30/cash/2pp}** at 2.5%; optimum **bracketed** globally, but **NOT
> bracketed** at `K`=90 (both scopes). `minPositionPct`: **material** —
> +2.07% return, −44% displacements, drawdown flat. Ordering spread:
> **1.21%**.

---

## Resume status

| | |
|---|---|
| Seeded from superseded run | `findings.md` only, verbatim as prior context, from `close-equivalence-and-run-cadence`. Its `cells.jsonl` was **not** reused, per the prompt. |
| Cells run this session | **3,908** |
| Cells reused | **1,260** (Step 5 refine reusing the scan's seeds 0-6 within this same session; 0 reused from any prior session) |
| Wall clock, measurement only | ~8.5 min (Step 4 13.6s · Step 5 scan 280.0s · Step 5 refine 182.7s · Step 6a 12.0s · Step 6b 2.8s · gates ~15s) |
| Driver commits | `a7df857` (the fix), `b324a11` (toggle + sweep driver) |
| Partial? | **No.** |

`cells.jsonl` was flushed after every cell and `findings.md` appended the
moment each finding was established, per `CLAUDE.md`.

---

## Step 1 — target re-verification (the pre-run check)

The prompt required re-reading both figures out of their manifests before
running. Both match; no hard stop.

| Target | Kind | Value in manifest | Manifest → key |
|---|---|---|---|
| `swap_funding`, 2.5pp | **forward draw** | `189781.58036163618` | `analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value` |
| (the superseded prompt's wrong target) | **median across 15 draws** | `190481.16304357877` | same file → `results.final.median` |
| `no_reserve_raw`, `off` | **forward draw** | `$141,836.57` | `analysis/data/run_manifests/step1-five-gates-manifest.json` → `results.detail[0]` |

The design session's diagnosis is confirmed from the source: the two figures
live in the same file, and the superseded prompt quoted the median.

---

## Step 2 — what was found

### The bug: year-end tax ran outside the session loop

`analysis/sweep_cadence_and_session_model.py`, `run_session_sweep_cell`.

**Before** (old lines 774-808) — indentation 4, i.e. *outside* the
`for skey, sd, in_scope in sessions_list:` loop:

```python
    # Year-end tax: apply once per year at the last session in that year
    from analysis.simulator.tax import compute_year_end_tax
    session_dates_seq = [sd for _, sd, _ in sessions_list]
    loss_carryforward = 0.0
    year_end_taxes = []
    for i, sd in enumerate(session_dates_seq):
        is_last_of_year = (i == len(session_dates_seq) - 1) or (session_dates_seq[i + 1].year != sd.year)
        if is_last_of_year:
            year_end_date = date(sd.year, 12, 31)
            mark_prices = prices.all_prices_on(list(held_tickers), year_end_date)
            tax_result = compute_year_end_tax(portfolio, year=sd.year, ...)
```

Two consequences, both fatal to the comparison:

1. **Every `daily_snapshots.append(...)` had already happened.**
   `compute_summary` takes `final_portfolio_value = snaps[-1].total_value`
   (`analysis/simulator/report.py:134`), so **the headline final value was
   entirely tax-free** — no year's tax reached it, nor max drawdown.
2. The shares sold to fund the forced liquidation kept compounding for the
   rest of the run instead of being gone from 2023-12-31.

The reference (`analysis/simulator/simulator.py:207-227`) walks every calendar
day and settles tax at its step 2 — after that day's trades, **before** that
day's mark-to-market — on Dec 31 of each year, plus a partial-year settlement
on the final day when that day is not Dec 31.

**After** — inside the loop, in two places (`analysis/sweep_cadence_and_session_model.py:436-459` and `:790-795`):

```python
    def _settle_year_end_tax(year, price_anchor_date):
        nonlocal loss_carryforward
        anchor_prices = prices.all_prices_on(list(held_tickers), price_anchor_date)
        tax_result = compute_year_end_tax(portfolio, year=year,
                                           loss_carryforward_in=loss_carryforward,
                                           prices_for_liquidation=anchor_prices)
        year_end_taxes.append(tax_result); loss_carryforward = tax_result.loss_carryforward_out
        taxed_years.add(year)

    for _sess_i, (skey, sd, in_scope) in enumerate(sessions_list):
        for _y in range(START.year, sd.year):                    # pending Dec 31s
            if _y not in taxed_years and date(_y, 12, 31) < sd:
                _settle_year_end_tax(_y, date(_y, 12, 31))
        ...
        _is_dec31 = (sd.month == 12 and sd.day == 31)            # before the snapshot
        _is_last_session = (_sess_i == n_sessions_total - 1)
        if sd.year not in taxed_years and (_is_dec31 or _is_last_session):
            _settle_year_end_tax(sd.year, date(sd.year, 12, 31) if _is_dec31 else sd)
```

No trades occur between sessions, so settling year Y at the first session
on/after Jan 1 of Y+1 leaves the portfolio in exactly the state Dec-31
settlement would — provided liquidation **prices** stay anchored to the
literal Dec 31, which is commit `cbba37e`'s fourth-bug fix, preserved.

### First diverging calendar date: **2023-12-31**

Not 2024-01-24. The reference settles 2023 tax that day — `net_taxable`
$452.06, `tax_owed` $67.81, funded by force-selling ≈0.3522 AAPL shares at the
Dec-31-anchored price — and the session model did not. The previously reported
"first divergence 2024-01-24, −$68.50" was **a snapshot-granularity artifact
only**: the session model snapshots on session dates, the reference on every
calendar day, so 2024-01-24 was simply the earliest date they had in common
after the real 2023-12-31 split. $68.50 is the same shares marked at the
2024-01-24 price; **$72.75 is those same shares marked at 2024-06-12** — which
is precisely the residual the prompt predicted.

### The three candidates, resolved

| Candidate | Verdict |
|---|---|
| (a) cash-only bookkeeping path with no `Trade` object (dividends/interest) | **Refuted.** No such path exists. **§5's "cash earns no interest" is NOT violated** — nothing to report separately. |
| (b) per-account cash aggregation in `portfolio.total_value`, session-native vs daily | **Refuted.** |
| (c) an effect just outside the searched window surfacing in the 2024-01-24 mark | **Confirmed** — and it was not a trade but a tax settlement, which is why the last run's exhaustive trade-by-trade diff of `(2023-12-11, 2024-01-25]` came back bit-identical and found nothing. |

### Gate 1a result

Both configs `single_event` / `new_calls_only` / **forward draw**, compared
against **forward-draw** targets on both sides:

| Config | Measured (forward draw) | Target (forward draw) | Provenance | Diff |
|---|---|---|---|---|
| `no_reserve_raw`, `off` | $141,836.56574946275 | $141,836.57 | `step1-five-gates-manifest.json` → `results.detail[0]` | −$0.00425 (target quoted to the cent; rounding only) |
| `swap_funding`, 2.5pp | $189,781.58036163618 | $189,781.58036163618 | `bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value` | **$0.00000000 — bit-exact** |

**GATE 1a PASSES.**

Side effect: `realized_gains` for `swap_funding`/2.5pp moved from
−$6,214.656367282603 to −$6,208.332154513496 (forced liquidation now runs
against the mid-run portfolio). `max_dd` unchanged at 0.1878154040258339 —
a $67.81 hit on a ~$150k portfolio cannot move a peak-to-trough.

`no_reserve_raw`/`off` was never affected: it realizes only losses, so its tax
is zero in every year.

---

## Step 3 — spec-correction deltas: `trim_budget_scope`

`trim_budget_scope` **did not exist** as a parameter. Added as a toggle,
default `per_event_date` (reference behavior, unchanged). §5 denominates the
25%-of-start-of-day donor trim budget in **sessions**; the reference's
`make_funding_decide_fn` keys its `day_state` off `trade_date` — **calendar
dates**.

All figures are **forward draws** (`single_event`, `new_calls_only`, no seed):

| Config | `per_event_date` (reference) | `per_session` (spec-faithful) | Δ$ | Δ% |
|---|---|---|---|---|
| `no_reserve_raw`, `off` | $141,836.56574946275 | $141,836.56574946275 | **$0.00** | 0.0000% |
| `swap_funding`, 2.5pp | $189,781.58036163618 | $190,465.98615398916 | **+$684.41** | **+0.3606%** |

Secondary effects (`swap_funding`/2.5pp, forward draw): max drawdown
0.1878154040258339 → 0.18461344585456324 (**improves** 0.32pp); displacements
198 → 241 (+21.7%); Adds attempted 96 → 96; fully funded 1 → 1; cumulative
shortfall $3,077,679.73 → $3,082,594.55. `no_reserve_raw` is untouched because
it never trims a donor (0 displacements), so the budget is never consulted.

**Structural point that matters more than the number:** the two scopes can
only differ where one calendar date carries more than one session — i.e. at
`single_event` / `per_call` cadence. At any fixed-`K` or seasonal cadence one
session *is* one date, so this correction is **identically zero** across the
entire Step 5 grid. It is not a knob that interacts with the cadence decision.

Step 2 surfaced no other reference-versus-spec divergence to price.

**Report only — the default was not switched.**

> **Trap flagged so nobody trips on it later.** $190,465.99 sits within $15 of
> the superseded prompt's bad target $190,481.16304357877. These are unrelated
> quantities: the first is a **forward draw under a spec correction**, the
> second a **median across 15 draws under the reference**. The near-match is
> coincidence and corroborates nothing.

---

## Step 4 — pooling, re-derived. The +34.4% is REFUTED.

`execution_order` `sequential` vs `pooled`, `per_call` cadence,
`swap_funding`, `new_calls_only`, **7 draws (seeds 0-6)**. Both columns are
**medians across those 7 draws** — neither is a forward draw. Ranges are
min/max over the same draws; per Rule 2, overlapping ranges are **tied**,
never ranked by median.

| Limit | `sequential` median | `pooled` median | Δ% | `seq` DD median | `pooled` DD median | Rule 2 |
|---|---|---|---|---|---|---|
| `off` | $146,260.37 | $146,218.41 | −0.029% | 35.81% | 35.81% | **tied** |
| 0.5pp | $123,290.06 | $123,276.80 | −0.011% | 6.10% | 6.11% | **tied** |
| 1pp | $147,326.65 | $147,296.53 | −0.020% | 11.45% | 11.46% | **tied** |
| 1.5pp | $165,240.91 | $165,185.21 | −0.034% | 16.22% | 16.23% | **tied** |
| 2pp | $177,069.49 | $177,007.16 | −0.035% | 19.47% | 19.46% | **tied** |
| 2.5pp | $189,994.57 | $189,903.31 | −0.048% | 18.80% | 18.84% | **tied** |
| 3pp | $199,436.70 | $199,481.77 | +0.023% | 22.19% | 22.24% | **tied** |
| 5pp | $183,500.25 | $185,095.67 | +0.869% | 30.33% | 30.31% | **tied** |

**Every cell ties.** The draw-to-draw range swamps the execution-order effect
at every limit. The largest median gap anywhere is +0.87pp at 5pp, and it has
the opposite sign from six of the other seven.

- *Does pooling's advantage survive a tight ceiling?* **There is no measurable
  advantage to survive.** Pooling is a no-op within noise from `off` to 5pp.
- *Does it move the optimal limit?* **No.** Both orders peak at 3pp
  (sequential $199,436.70, pooled $199,481.77 — medians) and fall away at 5pp.

**Why the old +34.4% at `off` and +0.7% at 2.5pp do not reproduce.** They were
measured against a baseline that was not yet exact, and they do not appear to
have held cadence fixed. With cadence pinned at `per_call` the mechanism is
nearly inert by construction: a per-call-date session usually contains exactly
one event, so §3's evaluate-then-pool-then-deploy has nothing to pool.
**Treat +34.4% as withdrawn** (see "previously published numbers" below).

---

## Step 5 — the cadence grid

`swap_funding`, `pooled`, conformant per-date trim cap. 2,268 cells at 7 draws
(scan) plus 1,440 more at 15 draws (refine, limits 1.0-3.0pp). Three phase
offsets per K (0, K/3, 2K/3; seasonal 0/10/20), phase-averaged with spread
reported. **All grid figures are medians across draws, then averaged across
the 3 phases — never forward draws.**

**Best cell: `K`=30, `cash_deployment`, 1.5pp — $194,171.25 (15 draws), median
drawdown 22.96%, phase spread 5.84%.** At 7 draws the same cell reads
$194,820.44 / 22.96% / 6.01%; the ranking is stable between draw counts, so
the 15-draw refinement changed nothing material.

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
| 10 | seasonal | cash_deployment | 1pp | $182,533 | 29.38% | 0.96% | pass |

Full per-cell output including min/median/max, drawdown distribution,
days-below-1%-cash, funded/partial/unfunded, cumulative shortfall, distinct
tickers, displacement count, donor size quantiles and per-ticker mean staleness
is in `analysis/data/run_state/close-equivalence-corrected-targets/` —
`step5scan-results.json`, `step5refine-results.json`, `step5-analysis.json`,
and the raw `cells.jsonl`.

**Minimum viable cadence: `K` = 90.** Every K from 7 to 90, plus seasonal, has
at least one Rule-4-viable cell above $180k. Nothing in this grid forces a fast
cadence — and the trade is favourable in the slow direction:
`K`=90/`new_calls_only`/3pp reaches $185,509 at 15.10% drawdown against
`K`=7's best of $189,538 at 25.29%. **2.1% of return for 10.2pp less
drawdown.** (Reported, not chosen — Step 8's scope boundary.)

---

## Step 7 — gates and rules

### Gates

| Gate | Result |
|---|---|
| **1** — standing assertion, `no_reserve_raw` control | **PASS.** $141,836.56574946275 vs $141,836.57 (`step1-five-gates-manifest.json` → `results.detail[0]`), rounding only. Forward draw both sides. |
| **1a** — this prompt's, `swap_funding`/2.5pp | **PASS, bit-exact.** $189,781.58036163618 vs `bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value`. Forward draw both sides. |
| **2** — invariant #2, `target_pct <= cap_pct` at decision time | **PASS.** Max excess 0.000000pp over a 36-cell sample spanning K ∈ {7,30,90,seasonal,single_event}, both scopes, limits {1.5pp, 2.5pp, off}. |
| **3** — invariant #9, session move ≤ limit, **verified in aggregate** per the prompt's `cash_deployment` caveat | **PASS** across all 3,908 recorded cells. Every limit's worst observed aggregate equals the limit exactly and never exceeds it. See the dismissed apparent breach below. |
| **4** — invariant #5, conditional | **PASS.** **Zero** skipped events across all 3,908 grid cells — nothing to classify, so no unclassifiable skip to stop on. (The 6 known-§11 `insufficient cash in tax_advantaged` skips live in the `no_reserve_raw`/`off` control only.) |
| **5** — independent drawdown recompute within 0.01pp | **PASS.** Max \|diff\| 0.000000pp over the same 36-cell sample. |

No gate tests a condition §11 documents as a known unfixed defect.

**A diagnostic that contradicts the prompt, reported rather than acted on.**
Gate 3 initially read as a breach: at `single_event` cadence with
`cash_deployment` scope, the aggregate showed **4.5pp against a 1.5pp limit**
(and 7.5pp against 2.5pp) on 2022-02-16, on TSLA, MSFT and GOOGL alike. That
date carries **three separate sessions** — `single_event` makes one session per
event and three calls share the date — each moving **exactly 1.5pp**.
Invariant #9 is **per session**, so per session it sits precisely at the limit.
The 3× is an artifact of aggregating by calendar date rather than by session.
This combination is not in the grid either: `single_event` exists only for the
equivalence gate, which uses `new_calls_only`. **Not a breach. Not a stop.**

### Rule 4 — 39.12% median-drawdown ceiling plus share-of-draws (robust ≥ 2/3)

**90 of 108 scan cells pass.** All 18 failures are `cash_deployment` at loose
limits: the whole `K`=7 `cash_deployment` column from 0.5pp up
(34.83%-51.30%), `K`=14 `cash_deployment` from 1.5pp up, and every `off` cell
at K ≤ 30. Where a cell passes, it passes with **100% share-of-draws** —
there is no marginal 2/3 case anywhere in the grid, so the share-of-draws
clause does no work here.

### Rule 3 — single clause, `off` at the loose end, immaterial steps discarded

Materiality: `|Δ| ≥` the smaller of the two adjacent draw ranges.

**11 of 12 (K, scope) surfaces are unimodal with an interior, bracketed peak.**
The single exception: **`K`=7 / `cash_deployment` is JAGGED** — signs read
`+ − − − − − +`, peak at 0.5pp, and it is the one surface where the loose end
turns back up. It is also the column Rule 4 rejects outright, so nothing rests
on it.

### Rule 3b — plateau within 2.5% of the peak; sensitivity 1% / 2.5% / 5%

| Tolerance | Plateau |
|---|---|
| 1% | {`K`30/cash_deployment/1.5pp} |
| **2.5%** | **{`K`30/cash_deployment/1.5pp, `K`30/cash_deployment/2pp}** |
| 5% | 12 cells spanning `K`=7 through 90 and both scopes |

Never an argmax: the 2.5% plateau is two cells, and the 5% plateau being that
wide is the real signal — **the cadence choice is worth roughly 5% of terminal
value, and the limit choice is worth more.**

**Optimum bracketed globally** — 1.5pp is interior to the sampled range
[0.25pp … `off`].

**NOT bracketed at `K`=90, both scopes.** Their 2.5% plateaus run
`{3pp, 5pp, off}` — touching the loose end. At a 90-day cadence the limit stops
binding, so the sampled range does not bracket that surface's optimum. Flagged
per Rule 3b; extending the range there is a follow-up, not something this run
decides.

---

## Step 6 — fold-ins

### 6a. `minPositionPct` and the stub rule (`K`=30, `cash_deployment`, 1.5pp)

Rule: *if a swap-funding trim would leave the donor below
`max(pct × portfolio, $100)`, sell the whole position instead.* Verified
implemented as specified at `analysis/sweep_cadence_and_session_model.py:576-585`.
3 phases × 7 draws = 21 runs per floor; all columns are **medians across those
21**.

| `minPositionPct` | Final median | DD median | Displacements | Realized gains | Distinct tickers |
|---|---|---|---|---|---|
| 0 | $193,791.35 | 22.70% | 184 | −$4,337.58 | 15 |
| 0.25% | $193,714.87 | 22.65% | 130 | −$4,598.87 | 11 |
| 0.5% | $195,015.80 | 22.65% | 115 | −$4,925.75 | 10 |
| 1.0% | $197,808.57 | 22.53% | 103 | −$2,849.44 | 10 |

**Material, not housekeeping — and favourably so.** 0 → 1.0% is **+2.07%**
final value with drawdown essentially flat (22.70% → 22.53%) and **44% fewer
displacements**.

**But the honest reading is narrower.** The draw ranges overlap heavily — 0%
spans $189,398-$201,185, 1.0% spans $194,980-$205,565 — so **under Rule 2 the
return figures are tied.** The floor's defensible benefit is the displacement
count and the collapse of the stub tail (distinct tickers 15 → 10), not the
return. Calling the +2.07% a return improvement would be over-reading it.

### 6b. Ordering confirmation, once (`K`=30, `cash_deployment`, 1.5pp, phase 0)

All five are **single forward draws**, not medians:

| | Final value |
|---|---|
| forward | $189,397.52 |
| reversed | $191,689.55 |
| seed 1 | $189,397.52 |
| seed 2 | $189,484.69 |
| seed 3 | $189,397.52 |

**Spread = 1.21% of the median — under 2%, so the question is answered and no
further ordering sweep is needed.** Three of the five are bit-identical, which
is expected: at a 30-day cadence most sessions carry one event, so shuffling
within a session is usually a no-op.

### 6c. Staleness vs return, per K

| K | Mean staleness | Best Rule-4-viable cell | Median final | DD median |
|---|---|---|---|---|
| 7 | 3.3 d | new_calls_only / 3pp | $189,538 | 25.29% |
| 14 | 6.7 d | new_calls_only / 3pp | $186,610 | 24.02% |
| **30** | **14.1 d** | **cash_deployment / 1.5pp** | **$194,171** | **22.96%** |
| 60 | 28.5 d | cash_deployment / 2.5pp | $187,706 | 18.47% |
| 90 | 42.7 d | cash_deployment / 3pp | $185,795 | 15.03% |
| seasonal | 10.5 d | cash_deployment / 1pp | $182,533 | 29.38% |

Measured staleness tracks §2's predicted `K/2` closely (7→3.3, 14→6.7, 30→14.1,
60→28.5, 90→42.7), confirming the uniform-on-`[0,K]` model.

**Return is NOT monotonically decreasing in staleness.** The peak sits at
`K`=30 / 14.1 days — above both the fresher `K`=7 (−2.4%) and the staler
`K`=90 (−4.3%). Drawdown, by contrast, **is** monotone in staleness, falling
steadily from 25.29% at `K`=7 to 15.03% at `K`=90. Fresher information buys
return only up to a point, and buys drawdown nowhere. The seasonal variant is
the worst risk-adjusted row in the table: 10.5 days of staleness for a 29.38%
drawdown and the lowest return of the six.

---

## Flagged plainly

### Gates that fail
**None.** All six pass, Gate 1a bit-exact. One apparent Gate 3 breach was
investigated and dismissed as a per-date-vs-per-session aggregation artifact
(above), not explained away — the underlying per-session moves were checked and
sit exactly at the limit.

### Rules giving an uncomfortable answer

1. **Rule 2 defangs Step 4 entirely.** Every sequential-vs-pooled cell ties.
   Pooling — §3's specified execution sequence, a real piece of the spec — is
   unmeasurable at per-call cadence in this corpus. The spec may still be
   right; the backtest simply cannot see it.
2. **Rule 2 also defangs the return half of 6a.** The +2.07% headline is a tie
   once draw ranges are honoured.
3. **Rule 3b says the `K`=90 optimum is not bracketed.** The one cadence with
   the best drawdown profile is the one whose limit surface this grid does not
   pin down.
4. **Rule 3 flags `K`=7/`cash_deployment` as jagged.** Convenient that Rule 4
   rejects it anyway — but note the two rules are agreeing for different
   reasons, not corroborating each other.

### Previously published numbers now known to be wrong

Stated explicitly rather than silently replaced:

| Where | Published | Corrected | Why |
|---|---|---|---|
| `prompts/close-equivalence-and-run-cadence.md` Gate 1a target | `$190,481.16304357877` as a forward-draw target | `$189,781.58036163618` | The published figure is `results.final.median`, a **median across 15 draws**. The forward draw sits in the same manifest at `results.forward_diagnostics.final_value`. Already corrected by this prompt; **now verified against the manifest**. |
| Superseded run, session-model result | `$189,854.3296242896` | `$189,781.58036163618` | Measured with the year-end tax outside the loop. |
| Superseded run, gap | `−$626.83` (−0.329%) | **$0.00** | Was a forward draw compared against a median. Void. |
| Superseded run, first diverging date | `2024-01-24`, −$68.50 | **2023-12-31** | 2024-01-24 was the earliest *common* snapshot date, not the divergence. $68.50 and $72.75 are the same ≈0.3522 AAPL shares marked on two different days. |
| Superseded run, pooling advantage | **+34.4% at `off`, +0.7% at 2.5pp** | **−0.029% and −0.048% — a tie at every limit** | **Withdrawn.** Measured against a non-exact baseline and, on the evidence, not holding cadence fixed. |

### Does anything disturb the six settled sessions in §0?

**No settled decision is disturbed, but two are now differently supported.**

- **Funding mode `swap_funding` — undisturbed.** Unaffected by the fix.
- **Drawdown ceiling 39.12% — undisturbed**, and now doing real work: it
  rejects 18 of 108 cells, all `cash_deployment` at loose limits.
- **`X` = 2.5pp, marked *provisional* pending `K`** — the grid says this was
  right to mark provisional. The best limit is **cadence-dependent**: 3pp for
  `new_calls_only` at every K, but 1.5pp for `cash_deployment` at `K`=30.
  2.5pp is optimal for **no** (K, scope) pair in the grid. Re-deriving `X`
  after `K` is chosen is now required, not merely prudent.
- **§11 defect #2 fix in the production path — undisturbed.**
- **Cap restoration — undisturbed.** Gate 2 clean at 0.000000pp excess.
- **`minPositionPct` "form agreed, value unmeasured"** — now measured at one
  region; the form is confirmed implementable and behaves as specified.

**Everything published from the session model before commit `a7df857` was
computed tax-free.** Any figure from that harness in an earlier wrap-up should
be treated as an overstatement of roughly the compounded value of every year's
unsettled tax, and re-derived rather than trusted.

---

## Verification performed

- Both Step 1 targets re-read out of their manifests by key before any run.
- `python3 -c "import ast; ast.parse(...)"` on both edited/created Python files
  before every commit.
- Fix confirmed by **bit-exact reproduction** of an independently recorded
  forward draw — 17 significant figures, `diff = 0.0`.
- `no_reserve_raw`/`off` re-run post-fix to confirm the change is inert where
  it should be (no realized gains → no tax): unchanged to all digits.
- Gates 2 and 5 re-derived independently over a 36-cell sample; Gates 3 and 4
  swept over all 3,908 recorded cells.
- Gate 3's apparent breach traced to the specific date, tickers and session
  count before being dismissed.
- Reproducibility: tree clean before each run; driver committed (`a7df857`)
  **before** any measurement; only specific files staged, never `git add .`;
  no unrelated working-tree changes existed to stash.

---

## Deviations from the prompt, and why

1. **Step 2's daily-`total_value` debug flag was not implemented.** The prompt
   prescribed forcing daily snapshots in the session model to pin the first
   diverging date. The cause was instead found by reading the code —
   the tax block's indentation — and confirmed to **bit-exactness**, which is
   a strictly stronger result than a daily diff would have produced. The first
   diverging date (2023-12-31) follows from the mechanism, not from a diff.
   Adding the instrument afterwards would have measured a divergence that no
   longer exists. **If a future run wants the instrument anyway, it is a small
   change and worth having; it was not worth the budget here.**
2. **`trim_budget_scope` had to be built before Step 3 could run.** The prompt
   spoke of it as an existing setting; it did not exist. Added as a
   default-off toggle, per Step 3's own toggle discipline.
3. **Step 5's grid used one 15-draw refinement band** (limits 1.0-3.0pp across
   all cadences and scopes) rather than a narrower "top region". The band is
   wider than strictly required and costs little.

---

## Deliberately not done — the scope boundary

**Report, do not decide.** This run selected nothing:

- **No `K` chosen.** `K`=30 is where the peak sits; `K`=90 is the slowest
  cadence that stays viable. Both are reported, neither is recommended.
- **No limit chosen.** No scope chosen. No execution order chosen.
- **No `trim_budget_scope` change.** Default stays `per_event_date`.
- **No `minPositionPct` chosen.**
- **No spec amended.** §0's `X` = 2.5pp still reads 2.5pp; the grid's evidence
  that it is optimal nowhere is reported, not applied.
- **No §12 open item resolved. No veto sweep started.**

---

## Follow-up commands

Reproduce Gate 1a:

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import sys; from pathlib import Path
REPO = Path("/Users/luismorales/Desktop/investment-agent")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"analysis"))
import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup
ev, tf, df, tif = S.load_events_dedup_on()
px = PriceLookup.from_cache(S.SCRIPT_DIR/"data"/"price_cache.json")
for name, (fm, lim, tgt) in {
    "no_reserve_raw/off": ("no_reserve_raw", None, 141836.57),
    "swap_funding/2.5pp": ("swap_funding", 2.5, 189781.58036163618),
}.items():
    r = S.run_session_sweep_cell(ev, px, tf, df, tif, cadence="single_event",
        phase_offset=0, scope="new_calls_only", funding_mode=fm, limit_pp=lim)
    print(f"{name}: {r['final_value']!r}  target {tgt!r}  diff {r['final_value']-tgt:+.8f}")
EOF
```

Re-run the sweeps (resumable — already-recorded cells are skipped by
`config_hash`, so these return in seconds unless the driver commit changed):

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 analysis/run_corrected_targets_sweeps.py 4
python3 analysis/run_corrected_targets_sweeps.py 5scan
python3 analysis/run_corrected_targets_sweeps.py 5refine '[1.0,1.5,2.0,2.5,3.0]'
python3 analysis/run_corrected_targets_sweeps.py 6a 30 30 cash_deployment 1.5
python3 analysis/run_corrected_targets_sweeps.py 6b 30 30 cash_deployment 1.5
```

Price the Step 3 spec correction again:

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import sys; from pathlib import Path
REPO = Path("/Users/luismorales/Desktop/investment-agent")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"analysis"))
import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup
ev, tf, df, tif = S.load_events_dedup_on()
px = PriceLookup.from_cache(S.SCRIPT_DIR/"data"/"price_cache.json")
for tbs in ("per_event_date", "per_session"):
    r = S.run_session_sweep_cell(ev, px, tf, df, tif, cadence="single_event",
        phase_offset=0, scope="new_calls_only", funding_mode="swap_funding",
        limit_pp=2.5, trim_budget_scope=tbs)
    print(f"{tbs:16s} {r['final_value']!r}  dd={r['max_dd']!r}  disp={r['n_displacements']}")
EOF
```

Recheck the gates:

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import json, collections
from pathlib import Path
cells = [json.loads(l) for l in Path(
  "analysis/data/run_state/close-equivalence-corrected-targets/cells.jsonl"
).read_text().splitlines() if l.strip()]
worst, skips = collections.defaultdict(float), collections.Counter()
for c in cells:
    lim = c["params"].get("limit_pp")
    if lim is not None:
        worst[lim] = max(worst[lim], c["results"].get("max_session_pp_change", 0.0))
    for _, _, why in c["results"].get("skipped_events", []):
        skips[why] += 1
print("cells:", len(cells))
for lim in sorted(worst):
    print(f"  limit={lim}pp worst={worst[lim]:.4f}pp "
          f"{'OK' if worst[lim] <= lim + 1e-6 else 'BREACH'}")
print("skip reasons:", dict(skips))
EOF
```

---

## Artifacts

| Path | What |
|---|---|
| `analysis/sweep_cadence_and_session_model.py` | the fix (`a7df857`) + `trim_budget_scope` (`b324a11`) |
| `analysis/run_corrected_targets_sweeps.py` | Steps 4-6 driver, resumable |
| `analysis/data/run_state/close-equivalence-corrected-targets/findings.md` | append-only findings, seeded with the superseded run's |
| `.../cells.jsonl` | 3,908 cells, `config_hash`-keyed |
| `.../progress.json` | all steps `done` |
| `.../step4-results.json`, `step5scan-results.json`, `step5refine-results.json`, `step5-analysis.json`, `step6a-results.json`, `step6b-results.json` | per-step aggregates |

**No manifest was written this session** — every result here is a measurement
against existing manifests, not a new published baseline. Writing one is the
natural next step once a cadence is actually chosen, which this run does not do.

Standing constraints honoured: no LLM calls, no API spend, no DB writes (corpus
reads only), no cache refreshes (`price_cache.json` and `fundamentals_cache.json`
frozen at 2026-05-11; the staleness warning appeared and was ignored as
expected), work confined to `sweep/db-corpus-baseline`, nothing pushed,
`testing/` untouched.
