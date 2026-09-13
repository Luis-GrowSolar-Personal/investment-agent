# Value attribution v2 — Stage C3: which rule earns, which rule costs

**Status: COMPLETE.** Step 0 (hygiene, pre-registration, the 0c cash-share
fill), Step 1 (the cash-parked arm), Step 2 (four ablations), Step 3
(leave-one-company-out) and Step 4 (drawdowns) are all done. This document
was extended in a second, resumed session that ran Steps 2-4 to completion
(see "Steps 2-4" below); Steps 0/1 content above the fold is unchanged from
the first session.

**Scope boundary: report, do not decide.** No spec edits were made:
`PROMOTION_GATE.md`, `VERSION_REGISTRY.json`, `EVALUATION_PROMPT.md`,
`versions.js`, and the production prompt are all untouched.

---

## §0 — defined terms

| Term | Meaning here |
|---|---|
| **Control** | The real system: real allocator, real analyst scores, real trend layer, unmodified. Buys, trims and holds per the actual scored recommendations. |
| **Arm 0b** (universe-only) | Every call forced to "Hold" — the allocator never buys anything new. Only starter positions from the very first call in a name ever exist. |
| **Arm 0** (always-bullish) | Every call forced to "Add" — the allocator buys as much as its caps allow on every single call. |
| **Arm 0c** (buy-and-hold, equal-weight) | $100,000 split into 16 equal $6,250 slices, one per company, each bought the moment that company's first call appears in the population, then never traded again. Bypasses the allocator, analyst and trend layer entirely. |
| **Cash-parked arm** (this run, Step 1) | The control's own decisions, unmodified, except: any dollar not currently invested in a position is parked in the S&P 500 (SPY) instead of sitting as literal cash, and sold back first whenever the control's decisions need funding. This is a **measurement device**, not a proposed product feature — see "Guardrail against misreading" below. |
| **Cash share** | The fraction of total portfolio value sitting as uninvested cash (or, for the parked arm, unparked cash) at a given date, averaged across every ~30-day session snapshot in the window. |
| **Dollar-years invested** | A measure of how much capital was at work and for how long — $1 invested for 2 years counts the same as $2 invested for 1 year. Lets you compare arms that hold very different average cash levels. |
| **Return per dollar-year** | (final value − starting capital) ÷ dollar-years invested. A measure of how well the capital that WAS deployed was used, independent of how much cash sat idle. |
| **Funding shortfall** (this run's finding) | A gap that opens when the cash-parked arm needs to sell its parked SPY position to fund a real trade, but SPY's market value has fallen below the dollar amount originally parked — so selling it back does not recover the full amount needed. |
| **X (session speed limit)** | 2.5 percentage points of portfolio per position per session — a speed limit on how fast a position can grow, not a budget for new names and not a position-size cap. Held fixed at 2.5pp in every arm this run. |
| **Points vs. percent** | This report uses "points" for a change measured in percentage points (e.g., cash share going from 26 points to 8 points), and "%" only when describing a share of something stated at the same time. |

**Settled configuration, in plain English** (identical across every arm): the
system re-evaluates its 16-company universe every 30 days, only acts on calls
it has not already acted on, funds new buys by swapping money out of existing
holdings rather than drawing down a separate cash reserve, moves any one
position by at most 2.5 points of the portfolio per 30-day cycle, and when
several companies report on the same date, ranks and funds them as one pooled
group rather than one at a time.

---

## Lead-with summary

> Holding the system's idle cash in the benchmark instead of leaving it idle
> changes the final value from $179,944.91 to **$192,679.64 on its face — but
> that figure is entirely a $12,734.74 accounting artifact (a funding
> shortfall assumed covered for free); the honest, conservative reading is
> $179,944.91, statistically the same as doing nothing with the idle cash at
> all** — against buy-and-hold's $195,584.28. Of the four allocator rules,
> the one that costs the most money is **disabling the Type A/B position
> caps** (**-$812.60** against control), and the one that earns the most is
> **disabling Rule 3, the no-averaging-down-on-speculative-losers guard**
> (**+$9,417.91** against control) — but see the finding below on what that
> second number actually measures — and **2 of the 4** keep their sign in
> EVERY one of the 16 leave-one-company-out worlds (disabling Rule 3 and
> disabling starter sizing); the other two flip sign at least once
> (disabling the caps flips in 3 of 16 worlds; disabling profit-take flips
> in 1 of 16 — though that ablation's effect is $0.00 in 15 of those 16
> worlds to begin with, so "flips" there means a $56.42 nonzero effect in
> exactly one world, ORCL, not a large reversal).

This is a genuinely different shape of result than either of the two readings
the prompt anticipated ("at/above $195,584.28 → idle capital" or "well below
→ strategy problem"). Both plausible readings of the cash-parked arm land
**well below** buy-and-hold, so on the strict either/or test in the prompt,
this is a strategy-problem result — but the more useful finding is the *reason*
the naive parking number looked encouraging in the first place, which is a
bookkeeping artifact, not a real gain. See "Step 1" below.

---

## Step 0c — the corrected C1 ladder

Stage C reported Arm 0c's average cash share as "not applicable." It is not:
Arm 0c holds each ticker's $6,250 slice as idle cash from the window start
(2022-01-01) until that ticker's own first call date in the 195-event
population, then converts it to shares. Measuring this at the control run's
own ~30-day session-snapshot dates:

| Arm | What it buys/sells | Final value | Avg cash share |
|---|---|---|---|
| Arm 0b (universe-only, forced Hold) | Buys nothing beyond first-call starters; never adds | `analysis/data/value_attribution_v2/stage_c_manifest.json` → `c1_deployment_ladder.arm_0b_universe_only.final_value` | high (never deploys further — carried over from Stage C, not recomputed this session) |
| **Arm 0c (buy-and-hold, equal-weight)** | Buys 16 equal slices once, at each company's first call; never trades again | `$195,584.28` — `stage_c3_manifest.json` → `step_0c_arm_0c_cash_share.final_value` (forward draw) | **`8.31%`** — `stage_c3_manifest.json` → `step_0c_arm_0c_cash_share.avg_cash_share` (CORRECTED from Stage C's "not applicable") |
| Arm 0 (always-bullish, forced Add) | Buys the maximum allowed on every call | `analysis/data/value_attribution_v2/stage_c_manifest.json` → `c1_deployment_ladder.arm_0_always_bullish.final_value` | carried over from Stage C |
| Control | Real system | `$179,944.91` — `docs/architecture/VERSION_REGISTRY.json` → `benchmarks.settled_control.figures.final_value` (forward draw) | `26.02%` — `stage_c3_manifest.json` → `control_avg_cash_share_recomputed_for_reference` (recomputed this session; matches Stage C's reported 26.0% to rounding) |

**Finding, not a quiet correction:** Arm 0c is not a zero-idle-cash
construction. It carries 8.31 points of average idle cash — real, but far
below the control's 26.02 points. Buy-and-hold beats the control while
carrying *less* idle cash than the control does, which sharpens rather than
undercuts the original C1 concern: the control's 26-point average cash share
looks even more like a real drag once the "do-nothing" comparator turns out
to be mostly invested too.

---

## Step 1 — the cash-parked arm: is the shortfall idle cash?

**Construction** (registered in `PREREGISTRATION.json` →
`stage_c3.cash_parked_arm` before this arm was computed): built as a
post-hoc overlay on the control run's own `daily_snapshots.cash_total`
series — the allocator is never re-invoked and no decision changes. At each
~30-day session snapshot, if cash rose since the last snapshot, the increase
is parked in SPY at that date's price; if cash fell (the control's own
decisions needed funding), SPY is sold back first, at that date's price, up
to the amount needed. This does **not** redeploy idle cash into existing
positions — proportional redeployment into positions is the closed "Never
Do" in `docs/architecture/DESIGN_PRINCIPLES.md` (§2: "trim proceeds have a
destination before the trim executes... proportional redeployment into
existing positions is the explicit failure mode being avoided"). Parking in
a benchmark index, sold back only to fund the *same* real trades the control
already made, is a measurement device, not that. State this plainly so no
future session reads this arm as a recommended feature.

**Result, and the complication:**

| Quantity | Value | Provenance |
|---|---|---|
| Literal overlay final value | $192,679.64 | `stage_c3_manifest.json` → `step1_cash_parked_arm.final_value` |
| Funding shortfall (total) | $12,734.74 | `stage_c3_manifest.json` → `step1_cash_parked_arm.shortfall_total` |
| Conservative final value (shortfall not backfilled) | $179,944.91 (to the cent, after rounding: $179,944.906) | `stage_c3_manifest.json` → `step1_cash_parked_arm.final_value_conservative_no_shortfall_addback` |
| Dollar-years invested | $253,283.06 | `stage_c3_manifest.json` → `step1_cash_parked_arm.dollar_years_invested` |
| Control final value (for reference) | $179,944.91 | `docs/architecture/VERSION_REGISTRY.json` → `benchmarks.settled_control.figures.final_value` |
| Buy-and-hold final value (for reference) | $195,584.28 | `stage_c3_manifest.json` → `step_0c_arm_0c_cash_share.final_value` |

**What happened, plainly:** whenever the control's own decisions needed to
pull cash back out for a real trade, the overlay sells the parked SPY
position at that date's price. Several of those sell-backs happened during
or shortly after the 2022 SPY drawdown, when SPY's market value was below
what had originally been parked — so selling it back recovered less than the
dollar amount needed. The literal `final_value` figure ($192,679.64) treats
every one of those gaps as costlessly covered, which is an optimistic
assumption, not something the real system could actually do. Once you don't
backfill that gap, the arm's honest value is **$179,944.91 — the same,
to the cent, as the control that never parked anything at all.**

**The reading, stated plainly, per the prompt's instruction not to spin a
middling result either way:**

- Neither figure ($192,679.64 nor $179,944.91) reaches buy-and-hold's
  $195,584.28. On the prompt's own either/or test, this is the
  **strategy-problem** reading: parking idle cash in the benchmark, done
  honestly, does not close the gap.
- But the more informative finding is that the naive "parking helps" number
  is not really about the benefit of holding SPY instead of cash — it is
  entirely the funding-shortfall accounting artifact. **This is a diagnostic
  that contradicts the prompt's clean two-way framing**, per the prompt's own
  standing rule that such a contradiction is a finding, not a reason to stop.
- This does not resolve which mechanism is costing the system money relative
  to buy-and-hold — that is what Step 2 (not run this session) and Step 3
  (not run this session) exist to test.

---

## Step 2 — the four ablations

Ran using the mechanics already registered in `PREREGISTRATION.json` →
`stage_c.ablations_c3`, implemented as module-global monkeypatches (restored
after each run) in `analysis/value_attribution_v2_stage_c3_step234_driver.py`,
committed at `acbceee` (later corrected for B4 at `0d65718` — see below).

**B2 confirmation (required before running it):** `PREREGISTRATION.json`
flagged B2 as "the one ablation most likely to have an ambiguous disable
mechanic." On inspection, **it is not ambiguous as a code location**: Rule 3
is a single, unconditional guard clause, `analysis/simulator/allocator_v2.py`
lines 143-147 inside `_decide_add()`:

```python
if tier == "speculative":
    cb = _weighted_cost_basis(portfolio, ticker)
    if cb is not None and day_price < cb:
        return []  # don't average down on speculative losers
```

Grepped for any second implementation of "averaging down" avoidance across
`analysis/simulator/*.py` — there is none. Disabled by monkeypatching
`_weighted_cost_basis` to always return `None`.

**But confirming that location surfaced a real, unregistered finding.** The
settled cell uses `funding_mode="swap_funding"` with pooled execution. In
that path, the session driver's own target-dollar computation for an Add
(`sweep_cadence_and_session_model.py` lines ~866-877) sizes the buy from
`recommended_size` and the type cap only — it never reads cost basis. When
Rule 3 makes `decide_v2`'s own "natural" buy return `[]`, the swap-funding
shortfall logic (`target − natural`) simply treats the whole target as a
shortfall and funds it anyway, by selling ("displacing") another held
position. **Rule 3, as actually executed in this configuration, does not
prevent the system from adding to a speculative loser — it only changes
whether that add is funded from free cash or by selling something else.**
"B2" therefore measures the value of *displacement* funding versus
*free-cash* funding, not "allow vs. block averaging down." This is reported
here as a finding, per the prompt's standing rule that a diagnostic
contradicting an expectation (here, an unstated one baked into the ablation's
name) is a finding, not a reason to stop or silently rename the arm.

**B4 driver bug, caught and fixed before this result was finalized.** The
first implementation patched `allocator_v3.STARTER_PCT_SPECULATIVE` /
`STARTER_PCT_ESTABLISHED` and got EXACTLY $0.00 effect on the full universe
and on all 16 leave-one-out worlds — too clean to trust. Tracing the actual
code path found `sweep_cadence_and_session_model.py` imports those two names
BY VALUE at its own module-load time (`from ... import NAME`), so patching
`allocator_v3`'s attribute afterward never reaches the function that
actually computes starter dollars in the executed
`scope="new_calls_only", execution_order="pooled"` path. Fixed (commit
`0d65718`) to patch `sweep_cadence_and_session_model`'s own module
attributes. **Re-running with the corrected target produced the identical
$0.00 result** — confirming the zero is genuine, not the bug. Verified
independently by inspecting the control run's `funding_log`: every
first-call funding event shows `binding: "session limit"` — the 2.5-point
per-session speed limit (X) clips the buy far below both the starter target
(5%/8%/6.5%) and the type cap, so differences in starter sizing never reach
the executed trade.

**B3 (disable profit-take) is also a genuine, verified zero**, confirmed by
direct inspection of the control run's transaction log: zero trades anywhere
in the 195-event, ~2.4-year run carry the reason
`"profit-take-25pct-trigger"`. The rule never fires under this corpus and
configuration, so disabling it changes nothing. (This is distinct from the
separate `PROFIT_TAKE_PCT = 25.0` local constant that gates the §8
pet-formation/capitulation model inside the session driver, which is moot
here since `veto_p = 0.0` in the settled cell.)

**Results, ranked by size (point figures, no confidence range — C4 has not
run — do not read any of these as significant, material, or decisive):**

| Arm | Final value | Δ vs. control ($179,944.91) | Δ vs. buy-and-hold ($195,584.28) | Avg cash share | Δ cash share vs. control |
|---|---|---|---|---|---|
| **B2 — disable Rule 3** | $189,362.81 | **+$9,417.91** | -$6,221.47 | 22.76% | -3.27 points |
| **B4 — uniform starter (6.5%)** | $179,944.91 | $0.00 | -$15,639.37 | 26.02% | 0.00 points |
| **B3 — disable profit-take** | $179,944.91 | $0.00 | -$15,639.37 | 26.02% | 0.00 points |
| **B1 — disable Type A/B caps** | $179,132.31 | **-$812.60** | -$16,451.97 | 26.02% | 0.00 points |

All values: `stage_c3_manifest.json` → `step2_ablations.arms.<arm>` (forward
draw, single path, seed=0). B4's cash share is identical to control to the
precision shown because the ablation changes nothing about deployed dollars,
per the finding above.

**Prompt's C1-derived prediction — checked, and it does not hold as stated.**
C1 predicted that ablations changing *deployment* (caps, starter sizing) would
move more money than ablations changing *selection* (averaging-down
avoidance). The opposite happened: the single largest mover is B2 (a
selection-tier rule), while both deployment-tier ablations (B1, B4) are
smaller or exactly zero. **Flagged per the prompt's own standing rule that a
contradicting diagnostic is a finding, not a reason to stop** — though as
noted above, B2's real mechanism is displacement-funding, which blurs the
deployment/selection line the prediction assumed.

No ablation, individually disabled, closes the gap to buy-and-hold
($195,584.28); the closest (B2) still trails by $6,221.47.

---

## Step 3 — leave-one-company-out

80 runs: control plus each of the four ablations, each re-run 16 times with
one of the 16 ALL16 tickers removed from the universe entirely (not held via
`final_action` — genuinely absent from the events passed to the simulator),
per the design in `PREREGISTRATION.json` → `stage_c3.leave_one_company_out_design`.
Each ablation's dollar effect in a given leave-out world is computed as
(that ablation's final value with ticker X dropped) − (control's final value
with the SAME ticker X dropped) — apples-to-apples within the reduced
universe, not mixed with the full-universe control.

| Arm | Full-universe effect | Sign preserved (of 16) | Company changing effect most | Change caused |
|---|---|---|---|---|
| B1 — disable caps | -$812.60 | **13/16** | NVDA | $862.60 (drop NVDA → +$50.00, flips positive) |
| B2 — disable Rule 3 | +$9,417.91 | **16/16** | ENVX | $4,786.40 (drop ENVX → +$14,204.30, nearly +50% larger) |
| B3 — disable profit-take | $0.00 | **15/16** | ORCL | $56.42 (drop ORCL → -$56.42; every other world is exactly $0.00) |
| B4 — uniform starter | $0.00 | **16/16** | — | $0.00 (every one of the 16 worlds is exactly $0.00) |

Full per-ticker tables: `stage_c3_manifest.json` →
`step3_leave_one_company_out.sign_stability.<arm>.effect_by_ticker_dropped`.

**Where the NVDA/AVGO/ORCL concentration bites, and where it doesn't.** Prior
work (Stage C2 diagnostics) put NVDA at 40.1% of the control's profit over
Arm 0, and NVDA+AVGO+ORCL at 81.4%. That concentration visibly affects B1
(dropping NVDA is what flips its sign) but does **not** break B2's sign
stability at all — B2 stays positive in every one of the 16 worlds, including
with NVDA dropped (effect falls from $9,417.91 to $5,926.13, still clearly
positive). This is worth stating plainly since the prompt's own framing
("this check is expected to bite") predicted a bigger problem than what
actually showed up for the arm carrying the largest dollar effect.

**Stated plainly, per the prompt's instruction:** sign stability under
leave-one-out is **weaker evidence than a confidence range.** It says B2's
positive effect and B4's null effect are not artifacts of any single
company's presence in the universe. It does **not** establish that either
effect is real, would replicate out-of-sample, or survives a correction for
the multiple comparisons across four ablations — that is what C4 (not run)
would be for.

---

## Step 4 — drawdowns

Maximum peak-to-trough decline (dollars and percent), its date range, and the
largest single calendar-quarter decline, for every arm in this run and C1's
ladder. Quarter marks use the last available session snapshot within each
calendar quarter; no risk-adjusted ratio is computed, and arms are **not**
ranked by one, per the prompt's Step 4 instruction — raw figures only,
alongside final value for context.

| Arm | Final value | Max drawdown ($) | Max drawdown (%) | Drawdown date range | Largest single-quarter decline |
|---|---|---|---|---|---|
| Control | $179,944.91 | $21,501.56 | 20.85% | 2022-04-01 → 2022-12-27 | $12,679.72 (2022-03-02 → 2022-06-30) |
| B1 — disable caps | $179,132.31 | $21,501.56 | 20.85% | 2022-04-01 → 2022-12-27 | $12,679.72 (same window) |
| B2 — disable Rule 3 | $189,362.81 | $22,402.72 | 21.73% | 2022-04-01 → 2022-12-27 | $12,989.18 (2022-03-02 → 2022-06-30) |
| B3 — disable profit-take | $179,944.91 | $21,501.56 | 20.85% | 2022-04-01 → 2022-12-27 | $12,679.72 (same window) |
| B4 — uniform starter | $179,944.91 | $21,501.56 | 20.85% | 2022-04-01 → 2022-12-27 | $12,679.72 (same window) |
| Arm 0b (universe-only, forced Hold) | $120,799.82 | $13,119.42 | 12.72% | 2022-04-01 → 2022-06-30 | $9,649.86 (2022-03-02 → 2022-06-30) |
| Arm 0 (always-bullish, forced Add) | $173,102.24 | $26,605.71 | 19.58% | 2023-07-25 → 2023-10-23 | $15,203.63 (2022-09-28 → 2022-12-27) |
| **Arm 0c (buy-and-hold)** | **$195,584.28** | **$48,320.98** | **36.53%** | **2022-01-01 → 2022-06-30** | **$26,218.14 (2022-03-02 → 2022-06-30)** |
| Cash-parked (conservative reading) | $179,944.91 | $31,694.60 | 31.69% | 2022-01-01 → 2022-12-27 | $19,125.46 (2022-03-02 → 2022-06-30) |

All values: `stage_c3_manifest.json` → `step4_drawdowns.<arm>`. Arm 0b and
Arm 0 were re-run fresh this step to get a full session-level snapshot series
(the Stage C manifest only stored two points per arm, start and end — not
enough for a drawdown calculation); both reproduced their previously
published final values exactly (`step4_drawdowns.arm_0b_universe_only
.reproduction_check` / `.arm_0_always_bullish.reproduction_check`, both
`match: true`).

**Finding: the system's shortfall against buy-and-hold in dollars does NOT
coexist with an advantage in losses — it's the opposite.** Buy-and-hold has
by far the worst drawdown of every arm measured, 36.53% peak-to-trough
(nearly double the control's 20.85%), concentrated in the first half of
2022. The control's much smaller loss in the same window is not a rule
"protecting" against buy-and-hold's drawdown by design — the control simply
hadn't deployed most of its capital yet by early 2022 (26.02% average cash
share; Arm 0b, which deploys least of all, has the smallest drawdown of any
arm at 12.72%). **The corpus's highest-return arm is also its highest-risk
arm by this raw measure, and the control's comparative safety during the
2022 drawdown is a byproduct of being under-invested, not of any exit
discipline earning its keep** — a finding neither Stage C nor this prompt's
framing anticipated.

---

## Limitations (restated, not argued past)

- Every figure describes this specific 16-company universe and this specific
  2022-01-01 to 2024-06-12 window. A prior run found this universe at the top
  of 25 random draws — it is not representative, and buy-and-hold's strength
  here partly reflects that the companies were well chosen.
- The 195-event population covers 2020 through mid-2024, with **zero 2025
  calls**.
- The corpus is a score stream of unverified prompt vintage.
- **No ablation figure in this run carries a confidence range.** C4, the
  permutation step that would supply one, has not run. Do not describe B1,
  B2, B3, or B4 as significant, material, or decisive — they are single-path
  point figures.
- **Sign stability under leave-one-out is weaker evidence than a confidence
  range.** It rules out a single company driving an effect; it does not
  establish that any effect (B2's earn, B1's cost) is real, or that B3/B4's
  zero effects would remain zero under a different corpus or configuration.
- **C2 remains unresolved** — whether the analyst's $6,842.67 above "add on
  every call" is distinguishable from zero is still open; this run does not
  address it.
- Stage D (headroom, the oracle ceiling) remains `pending`, untouched.
- The cash-parked arm's funding-shortfall mechanic (this session's main
  finding) has not been cross-checked against an alternative overlay
  construction (e.g., one that lets the arm draw on genuine reserve cash when
  SPY proceeds fall short, rather than either backfilling for free or
  refusing to fund at all). Both readings reported here are honest bounds,
  not a resolved single number.

---

## What's left, precisely

All of Stage C3 (Steps 0-4) is now done.

| Step | Status |
|---|---|
| 0a hygiene | done |
| 0b pre-registration | done |
| 0c ladder fill | done |
| 1 cash-parked arm | done |
| 2 four ablations | done |
| 3 leave-one-company-out | done |
| 4 drawdowns | done |

Remaining for the whole `value-attribution-and-headroom-v2` run_id (not
attempted, no work started this or any prior session unless noted):

- **C2** — the bootstrap on control-minus-Arm-0 ($6,842.67) failed its own
  reconciliation check in the original Stage C run and remains unresolved.
  Not touched by Stage C3.
- **C4, C5, C6** — never started. C4 (permutation range) is the step that
  would give this run's ablation figures a confidence interval.
- **Stage D** — headroom / oracle-ceiling analysis. Pending, untouched.
- **Stage E** — final deliverable composition. Pending, untouched.

`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json` →
`next_action` carries the precise state above for a future session.

---

## Reproducibility

**Steps 0/1 (prior session):**
- Driver: `analysis/value_attribution_v2_stage_c3_driver.py`, committed at
  `12fcb4f` (own commit, before the manifest).
- Manifest: `analysis/data/value_attribution_v2/stage_c3_manifest.json`,
  committed at `2ed4efd`.
- Control reproduction check: `$179,944.91` got vs. `$179,944.91` expected —
  MATCH (`stage_c3_manifest.json` → `reproduction_check.control`).

**Steps 2-4 (this session):**
- Driver: `analysis/value_attribution_v2_stage_c3_step234_driver.py`,
  committed BEFORE its results at `acbceee` (initial version); the B4
  patch-target bug fix committed separately, also before any manifest
  write reflecting it, at `0d65718`.
- Manifest update: `analysis/data/value_attribution_v2/stage_c3_manifest.json`
  (new keys `step2_ablations`, `step3_leave_one_company_out`,
  `step4_drawdowns` added; the Step 0c/1 keys from the prior session are
  untouched), plus `progress.json`, `cells.jsonl` (per-arm and per-leave-out
  appends, flushed as each of the 80 Step-3 runs completed) and
  `findings.md` appends, committed together at `5866eab`.
- Arm 0b and Arm 0 reproduction checks (re-run fresh this step for a full
  drawdown-capable snapshot series): `$120,799.82` got vs. `$120,799.82`
  expected — MATCH; `$173,102.24` got vs. `$173,102.24` expected — MATCH
  (`stage_c3_manifest.json` → `step4_drawdowns.arm_0b_universe_only
  .reproduction_check` / `.arm_0_always_bullish.reproduction_check`).
- One read-only DB `SELECT` (via `S.load_events_dedup_on()`), done ONCE and
  reused (by filtering the returned event list) across all 85 simulator
  runs in this step (1 control + 4 ablations, full universe, reused for
  Step 4's control/ablation drawdowns; 80 leave-one-out runs; 2 fresh
  reruns for Arm 0b/Arm 0) — no repeated querying.
- `git_dirty: true` is recorded honestly in the manifest — the driver
  commits land, and the working tree goes dirty again from the
  manifest-writing run itself (same pattern every driver in this run
  follows); the driver files are present at their recorded commits,
  verified via `git cat-file -e`.
- Working tree hygiene: unrelated WIP (ec-fidelity-benchmark-1
  progress.json, two probe scripts, several handoff/prompt/wrap-up files
  unrelated to this run) was stashed at session start (`git stash push -u
  -m "unrelated-wip-before-stage-c3-resume"`) and restored (`git stash
  pop`) at the end of this session, confirmed by `git status` with no
  conflicts.
- Zero Anthropic API calls made in either session. Zero DB writes. No
  stored `Analysis` row touched. No price-cache refresh (frozen at
  2026-05-08; the fundamentals cache staleness warning at runtime is
  expected and not "fixed").
- No spec file (`PROMOTION_GATE.md`, `VERSION_REGISTRY.json`,
  `EVALUATION_PROMPT.md`, `versions.js`, production prompt) was touched in
  either session.
