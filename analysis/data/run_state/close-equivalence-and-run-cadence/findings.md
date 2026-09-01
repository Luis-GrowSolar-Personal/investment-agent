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
