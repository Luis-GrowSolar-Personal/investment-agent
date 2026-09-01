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
