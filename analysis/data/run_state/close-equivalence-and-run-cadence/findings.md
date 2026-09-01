# findings — close-equivalence-and-run-cadence

Append-only. Nothing established yet beyond scaffolding.

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

## Step 1 (fourth bug) — substantive progress, not yet closed

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
  was numerically IDENTICAL before and after the fix (diff from the
  $190,481.16304357877 target unchanged at exactly -$626.83341928917692).
  AAPL was already held before 2024-02-14 (not a same-day starter), so the
  backfill branch never fires for this divergence. Change reverted (tree
  restored to HEAD) since it had zero verified effect and isn't validated
  elsewhere either.
- Localized the TRUE first point of disagreement much earlier than
  2024-02-14: diffing `daily_snapshots` total_value between `ref` and `new`
  (swap_funding, 2.5pp) shows exact agreement through at least 2023-12-11,
  then the first common sampled date after that -- 2024-01-24 -- already
  disagrees by -$68.5020827826811 (new higher than ref). No funding_log or
  displacement_log entries exist near 2024-01-24 in EITHER implementation
  (the only event that day is a plain TSLA "Hold", no Add, no donor
  activity), and per-ticker prices from `PriceLookup.from_cache()` for all
  16 tickers (including SPWR, which delisted in 2024 -- checked
  specifically) resolve identically and with no gaps on 2024-01-24. This
  rules out a stale/missing-price fallback difference as the cause.
- Because no funding/displacement/skip events register in either
  implementation between 2023-12-11 and 2024-01-24, and the two harnesses
  only share MTM snapshot dates at session/event boundaries (`new` only
  snapshots on session dates; `ref` snapshots every calendar day), the
  exact date the two portfolios' SHARE COUNTS first diverge within that
  ~6-week window is not yet isolated -- it is bracketed to
  (2023-12-11, 2024-01-24] but not pinned to a single day. The $68.50 gap
  is a fixed dollar amount that persists (~$65-68) through at least
  2024-02-01, consistent with a one-time share-count or lot-basis
  divergence on ONE ticker that then just rides forward at that ticker's
  price, rather than a recurring per-day drift.
- Next concrete step to pin the exact date: force `new`
  (`run_session_sweep_cell`) to record a snapshot every calendar day (not
  only at session dates) for a like-for-like diff against `ref`'s daily
  snapshots across 2023-12-11..2024-01-24, OR instrument portfolio share
  counts per ticker (not just total_value) at every event/session boundary
  in that window in both implementations and diff those directly -- this
  is more direct than total_value and immediately names the ticker.
- Gate 1a result under `per_event_date` (Step 2, literal comparison against
  the two hard-coded targets): `no_reserve_raw`/`off` PASSES to sub-cent
  ($141,836.56574946275 vs target $141,836.57, diff -$0.0043 -- rounding
  only). `swap_funding`/2.5pp FAILS by exactly -$626.83341928917692
  (-0.329%) against target $190,481.16304357877, unchanged from the prior
  session's reported figure. **Per the prompt's Step 2 instruction, this is
  a HARD STOP** -- the fourth bug is real, substantive, and not yet fixed.
  Steps 3 (spec-correction deltas), 4 (pooling re-derivation), 5 (cadence
  grid), 6 (fold-ins), and 7 (gates/rules scoring) were NOT attempted this
  session because they are explicitly gated on Gate 1a passing (Step 3
  opens with "Once the gate passes...") or depend on numbers Gate 1a would
  validate.
- Noted but not chased (tangential, does not block the above): calling
  `run_cell` directly for `swap_funding`/2.5pp with no seed/draw concept
  returns $189,781.58036163618, which is neither the fresh `new` output
  ($189,854.3296242896) nor the prompt's stated gate target
  ($190,481.16304357877). The gate target is evidently the SESSION MODEL's
  own expected value under `single_event`/`new_calls_only`/`forward`, not
  `run_cell`'s raw output under its own default draw ordering -- the two
  functions are not directly comparable 1:1 outside of the specific
  session-model invocation Step 2 specifies. This is worth a one-line
  clarification in the next session's context but is not itself a bug.

## Step 1 (fourth bug) — one genuine bug found and fixed; Gate 1a still fails

- **Found and fixed a real bug** (commit cbba37e): `run_session_sweep_cell`'s
  year-end tax computation priced the forced-liquidation-for-tax sale off
  the year's LAST SESSION date, not the literal Dec 31 calendar date the
  reference (`simulator.py`, which walks every calendar day) uses. Trade
  log confirmed the exact effect: on 2023-12-31, AAPL's forced sale priced
  at $193.179993/0.351011sh in the buggy session model vs
  $192.529999/0.352196sh in the reference. Fixed by anchoring
  `prices_for_liquidation` to `date(sd.year, 12, 31)` directly (still
  computed at the session-native trigger point, only the price-lookup date
  changed). **Verified: 2022 and 2023 year-end tax results (net_taxable,
  tax_owed, loss_carryforward_out, forced_liquidation_proceeds) are now
  bit-identical between the reference and the session model** (both:
  2022 → all zero; 2023 → net_taxable=452.05504419983913,
  tax_owed=67.80825662997587, forced_liquidation_proceeds=67.80825662997587).
- **This fix does NOT close Gate 1a.** Rerunning swap_funding/2.5pp after
  the fix gives the exact same final_value as before
  ($189,854.3296242896), an unchanged -$626.833419289178 gap against the
  $190,481.16304357877 target, matching to 12 significant figures. The
  daily_snapshots total_value diff still first disagrees at 2024-01-24 by
  the same -$68.5020827826811, even though every buy/sell trade in
  (2023-12-11, 2024-01-25] is now confirmed bit-identical between ref and
  new (the Dec-31 forced-liquidation trade included, post-fix).
- **This is a genuine, still-unresolved puzzle worth flagging plainly:**
  trades match, the two 2023-year-end-tax computations match bit-exactly,
  yet total portfolio value still diverges by $68.50 with no visible
  trade or tax event to explain it in that window. The only lead not yet
  chased: the 2024 year-end tax computation shows a real difference
  (net_taxable -640.5381671561415 ref vs -642.7135084763096 new, a
  $2.17 difference) -- but that computation runs at END of 2024, after
  the 2024-01-24 divergence already exists, so it cannot be upstream of
  it; if anything it's a downstream symptom of whatever is still unequal.
  The actual mechanism producing the $68.50 gap was not identified this
  session -- it is NOT a trade, NOT the (now-fixed) tax price anchor, and
  NOT a price-cache gap (checked). Candidate next places to look: (a) a
  cash-only bookkeeping path with no Trade object (e.g. dividend/interest
  accrual, if any exists in the simulator -- not checked this session);
  (b) `portfolio.total_value`'s per-account cash aggregation if one
  implementation is tracking cash in a subtly different way session-to-
  session vs day-to-day; (c) a genuine but as-yet-uncaptured trade whose
  `trade.trade_date` doesn't fall inside the (2023-12-11, 2024-01-25]
  window I searched (e.g. a trade dated slightly outside that range
  whose effects only become visible in the mark-to-market on 2024-01-24).
- **Gate 1a final status this session, per Step 2's literal instruction:
  HARD STOP.** `no_reserve_raw`/`off` passes to sub-cent
  ($141,836.56574946275 vs $141,836.57). `swap_funding`/2.5pp fails by
  exactly -$626.83341928917692 (-0.329%), unchanged by the genuine fix
  applied this session. A real fix attempt was made and verified correct
  on its own terms (2022/2023 tax now bit-exact); the gate still fails, so
  per the prompt this is a hard stop -- Steps 3 through 8 remain untouched.
