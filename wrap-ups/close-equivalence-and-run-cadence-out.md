# Close equivalence and run cadence — PARTIAL RUN, HARD STOP at Gate 1a

**Resume status:** this wrap-up covers three passes across two sessions.
Pass 1 was a cold start that did only Step -1 scaffolding and part of
Step 0 hygiene. Pass 2 resumed from `progress.json`'s `next_action`,
diagnosed and ruled out one hypothesis, and ran Gate 1a to a failing
result. Pass 3 (this update, still 2026-09-01) found and fixed one genuine
bug, reran Gate 1a, and **it still fails identically** — a hard stop per
the prompt's own rule. No cells were reused between passes (pass 1 ran
none).

**This is a partial run that ends in a deliberate hard stop, not a rush
through the remaining steps.** Step 1 produced one verified, committed
fix; Step 2 (Gate 1a) was run for real, twice, and fails both times.
**Steps 3 through 8 were correctly NOT attempted** — they are explicitly
gated on Gate 1a passing, and it does not.

## Headline result

> **Fourth bug: partially found.** One genuine bug was found and fixed —
> the session model priced the year-end forced-liquidation-for-tax sale
> off the year's last session date instead of literal Dec 31 (reference
> behavior), verified bit-exact for 2022/2023 after the fix (commit
> `cbba37e`). **Gate 1a under `per_event_date`: FAILED.**
> `no_reserve_raw`/`off` passes to sub-cent ($141,836.5657 vs
> $141,836.57). `swap_funding`/2.5pp fails by exactly **-$626.83341928917692
> (-0.329%)** against $190,481.16304357877 — **unchanged, to 12 significant
> figures, before and after the genuine fix.** A separate, still-unlocated
> divergence remains, first visible as a -$68.50 total_value gap at
> 2024-01-24 with no matching trade or tax event found in either
> implementation. Steps 3-8: not run (correctly gated on Gate 1a passing).

## What was done (session 2)

- Confirmed the corpus is stable, not drifted: `load_events_dedup_on()`
  returns 195 total events, 147 in the clean window
  (2022-01-01..2024-06-12) — matching the prompt's stated 147-event figure
  exactly. No corpus-drift concern.
- **Fourth-bug hypothesis tested and ruled out.** `make_funding_decide_fn`
  backfills `day_state["start_of_day_value"][ticker]` the moment a ticker
  first acquires a position mid-day (reference lines 337-338).
  `run_session_sweep_cell` had no equivalent backfill. Implemented it
  (mirroring the reference exactly) and reran Gate 1a: the swap_funding/2.5pp
  output was numerically **identical to 12 significant figures** before and
  after (diff from target unchanged at exactly -$626.83341928917692). AAPL —
  the donor where the known symptom appears — was already held before
  2024-02-14, so this backfill branch never fires for it. **Change reverted;
  the working tree is back at HEAD with zero net diff from this hypothesis.**
- **Localized the true first divergence much earlier than previously known.**
  Diffing `daily_snapshots` total_value between the reference (`run_cell`)
  and the session model (`run_session_sweep_cell`, `single_event`,
  `new_calls_only`, `swap_funding`, 2.5pp) shows exact agreement through at
  least 2023-12-11. The next date the two harnesses share a snapshot
  (`new` only snapshots at session/event dates) is 2024-01-24, where they
  already disagree by **-$68.5020827826811** (new higher). No funding,
  displacement, or skip events register near that date in **either**
  implementation — the only event that day is a plain TSLA "Hold" with no
  Add and no donor activity. All 16 ALL16 tickers' prices (including SPWR,
  checked specifically since it delisted in 2024) resolve identically with
  no cache gaps on 2024-01-24, ruling out a stale-price fallback as the
  cause. The gap is a fixed dollar amount that persists (~$65-68) through at
  least 2024-02-01, consistent with a one-time share-count/lot-basis
  divergence on one ticker riding forward at that ticker's price, not a
  recurring daily drift.
- **This is real progress, not yet closure:** the previously-known
  2024-02-14 QS/AAPL symptom ($488.32 vs $500.48) is now understood to be a
  *late, cumulative manifestation* of a root cause that occurred somewhere
  in the 6-week window `(2023-12-11, 2024-01-24]`, not the root cause
  itself. The exact date/ticker/trade that first diverges is not yet pinned
  down, because the two harnesses' snapshot cadences differ (`ref` snapshots
  every calendar day; `new` only at session dates), so a like-for-like daily
  diff across that window hasn't been done yet.
- **Gate 1a (Step 2) run for real, against the two literal hard-coded
  targets:**
  - `no_reserve_raw`, `off`, `single_event`, `new_calls_only`, `forward` →
    **$141,836.56574946275** vs target $141,836.57 → **PASS** (diff
    -$0.0043, rounding only).
  - `swap_funding`, 2.5pp, `single_event`, `new_calls_only`, `forward` →
    **$189,854.3296242896** vs target $190,481.16304357877 → **FAIL** by
    exactly **-$626.83341928917692 (-0.329%)**, unchanged from the prior
    session's reported figure.
  - **Per the prompt's Step 2 instruction this is a hard stop:** "Hard stop
    if either differs by a cent... a failure here is a real bug." The
    fourth bug is real and not yet fixed.
- One tangential, non-blocking observation for context: calling `run_cell`
  directly (the raw per-call harness, no session wrapper) for
  swap_funding/2.5pp returns $189,781.58036163618 — neither the session
  model's fresh output nor the prompt's stated gate target. The gate target
  is evidently the *session model's* expected value under
  `single_event`/`new_calls_only`/`forward` specifically, not `run_cell`'s
  raw default-order output; the two are not directly interchangeable
  outside that specific invocation. Not itself a bug, just worth keeping
  straight.

## What was done (pass 3, this update)

- Instrumented `Portfolio.execute_buy`/`execute_sell` to log every trade
  in `(2023-12-11, 2024-01-25]` for both implementations. Found exactly one
  divergent trade: on 2023-12-31, `forced-liquidation-for-tax` sold AAPL at
  $193.179993/0.351011sh in the session model vs $192.529999/0.352196sh in
  the reference.
- Root-caused it: `run_session_sweep_cell`'s year-end tax block priced the
  forced liquidation off the year's **last session date**, while the
  reference (`simulator.py`, which walks every calendar day) triggers and
  prices it on the **literal Dec 31 calendar date**. Different anchor date
  → different `all_prices_on` lookup → different price → different shares
  needed to cover the same dollar shortfall.
- **Fixed** (`analysis/sweep_cadence_and_session_model.py`, in the
  year-end-tax loop): anchor `prices_for_liquidation` to
  `date(sd.year, 12, 31)` directly, keeping the session-native trigger
  timing but fixing the price-lookup date. Committed as `cbba37e`.
- **Verified the fix is correct on its own terms:** captured
  `compute_year_end_tax`'s return value for both implementations across
  2022-2024. 2022 and 2023 are now bit-identical (net_taxable, tax_owed,
  loss_carryforward_out, forced_liquidation_proceeds all match to full
  float precision). 2024 still differs slightly (net_taxable
  -640.5381671561415 ref vs -642.7135084763096 new) but that computation
  runs at year-end 2024, well after the 2024-01-24 divergence already
  exists, so it's a downstream symptom, not upstream cause, of whatever
  remains unequal.
- **Reran Gate 1a after the fix: identical failure.** `swap_funding`/2.5pp
  = $189,854.3296242896, diff -$626.833419289178 — the same value to 12
  significant figures as before the fix. The `daily_snapshots` total_value
  diff still first appears at 2024-01-24 (-$68.50), even though every
  trade in the surrounding window (Dec-31 forced liquidation included) is
  now confirmed bit-identical. This means the fix was real and correct,
  but it was not the (or not the whole) fourth bug — a separate,
  still-unlocated divergence is producing the $68.50/$626.83 gap through
  some mechanism that leaves no trace in the trade log or the year-end tax
  computation.

## What was deliberately NOT done

- The mechanism producing the residual -$68.50 total_value gap at
  2024-01-24 was NOT found. Candidates not yet checked: (a) a cash-only
  bookkeeping path with no `Trade` object, e.g. dividend/interest accrual
  if the simulator has one; (b) a subtle difference in how
  `portfolio.total_value`'s per-account cash is aggregated
  session-native vs daily; (c) a trade dated just outside the searched
  `(2023-12-11, 2024-01-25]` window whose effect only surfaces in the
  2024-01-24 mark-to-market.
- No further fix was attempted once the first genuine fix didn't close the
  gate — per the prompt's explicit instruction, this is now treated as a
  hard stop rather than guessed at further.
- Step 3 (spec-correction deltas), Step 4 (pooling re-derivation), Step 5
  (the full cadence grid), Step 6 (fold-ins), Step 7 (gates/rules scoring) —
  none attempted, all correctly gated on Step 2 (Gate 1a) passing, which it
  does not.
- Nothing in this run disturbs the six settled sessions in §0. One earlier
  hypothesis (day_start_of_day_value mid-day backfill) was tested, found to
  have zero effect, and reverted before this fix was made — the only
  surviving code change is the year-end tax anchor fix in `cbba37e`.

## Exact resume point

`progress.json`'s `next_action`:

> HARD STOP per Step 2 — a genuine fix was made (year-end tax price anchor,
> commit cbba37e, verified bit-exact for 2022/2023) but Gate 1a still fails
> identically (-$626.83341928917692 at swap_funding/2.5pp, unchanged to 12
> sig figs). The remaining divergence produces a -$68.50 total_value gap
> first visible at 2024-01-24 with NO matching trade or tax event in either
> implementation in (2023-12-11, 2024-01-25] (all trades in that window,
> including the now-fixed Dec-31 forced liquidation, are confirmed
> bit-identical). Next session should check: (a) any cash-only bookkeeping
> path with no Trade object (dividends/interest, if the simulator has one —
> not checked); (b) per-account cash aggregation in portfolio.total_value
> for a session-vs-daily tracking discrepancy; (c) whether a trade exists
> just outside the searched date window whose effect only shows in the
> 2024-01-24 mark-to-market. Do NOT proceed to Steps 3-8 until Gate 1a
> passes — this is a hard stop per the prompt.

## Follow-up commands for the next session

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git status --porcelain   # must be clean before resuming
cat analysis/data/run_state/close-equivalence-and-run-cadence/progress.json
tail -n 80 analysis/data/run_state/close-equivalence-and-run-cadence/findings.md
```

To reproduce the Step 1/2 diagnostics from this session:

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent/analysis"
python3 - << 'PYEOF'
import sys; sys.path.insert(0, '.')
import bracket_three_modes_s11_corrected as ref_mod
from bracket_three_modes_s11_corrected import load_events_dedup_on
from sweep_cadence_and_session_model import run_session_sweep_cell
from analysis.simulator.data import PriceLookup

events_full, type_fn, driver_fn, tier_fn = load_events_dedup_on()
prices = PriceLookup.from_cache()

ref = ref_mod.run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
               funding_mode='swap_funding', session_change_limit_pp=2.5)
new = run_session_sweep_cell(events_full, prices, type_fn, driver_fn, tier_fn,
    cadence='single_event', phase_offset=0, scope='new_calls_only',
    funding_mode='swap_funding', limit_pp=2.5)

rs = {s.date: s.total_value for s in ref['daily_snapshots']}
ns = {s.date: s.total_value for s in new['daily_snapshots']}
common = sorted(set(rs) & set(ns))
for d in common:
    diff = rs[d] - ns[d]
    if abs(diff) > 1e-6:
        print(d, rs[d], ns[d], diff)
        break
PYEOF
```

Re-read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b, §11
in full before writing any further instrumentation or a fix, per the
prompt's instruction that those decisions are closed and must not be
re-derived.
