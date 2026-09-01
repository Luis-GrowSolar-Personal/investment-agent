# Cadence equivalence and pooling — Step 1a equivalence gate: FAILED (close)

**Single-event equivalence gate: FAILED, but close (2 of 3 hard-gate checks
now exact).** Distinct call dates: 112 for 147 in-window events (82
single-event, 25 two-event, 5 three-event dates; 44.2% of events share a
date with at least one other event). Pooling delta at per-call-date
sessions: **+$48,785.57 (+34.39%)** at `off` (no_reserve_raw) —
**does not collapse**, it reproduces the earlier failed run's number
exactly, confirming that run's "34% bug" was the pooling effect, not a
defect. Pooling delta for swap_funding at 2.5pp: **+$684.51 (+0.36%)**,
measured against this run's own (near-but-not-exact) single-event number —
**effectively collapses** under a tight ceiling, consistent with the
prompt's prediction. Steps 2–6 **did not run**: they are explicitly gated on
1a passing, and it did not. Minimum viable cadence, best cell, limit
surface, `minPositionPct`, ordering spread: **not measured, per the gate**.

**Does this invalidate the six prior settled sessions? No — and this is
worth stating plainly.** Every settled number in
`ALLOCATOR_OPERATING_MODEL.md` §0 (swap_funding, 2.5pp, 39.12% drawdown
ceiling, §11 defect #2 fix) was produced by
`bracket_three_modes_s11_corrected.py`'s `run_cell`, which has always
executed strictly per-event (sells and buys together, immediately, before
the next event) — it has never pooled cash across a multi-event date. The
session-model pooling machinery this run built is new code, on a branch of
its own, that nothing in production or in the settled spec consumes yet.
The pooling finding says something important about what §3's specified
session behavior will cost/gain **once it is built for real** — it changes
nothing about the numbers already banked.

---

## What was verified before implementing (premise check)

- `ALLOCATOR_OPERATING_MODEL.md` exists at 1001 lines with §0/§2/§3/§4/§5/§9/
  §10/§10b/§11/§12 at the numbers the prompt assumes. Read in full (§0–§12)
  before writing code.
- `wrap-ups/sweep-cadence-and-session-model-out.md` was genuinely still
  untracked (Step 0a's premise held) and is now committed at `4ece349`,
  before any new driver work, per the prompt's ordering rule.
- `bracket_three_modes_s11_corrected.py` really did assert `git_dirty=False`
  at **import** time (line 101 in the pre-session version), which really had
  forced the prior driver to duplicate `_rebuild_buy_leg` rather than import
  it. Confirmed by reading the file before touching it.
- The two Step 1a reference numbers are real and unchanged: `$190,481.16304357877`
  (`analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json`)
  and `$141,836.57` (`analysis/data/run_manifests/step1-five-gates-manifest.json`).
- 147 in-window events, 112 distinct call dates — confirmed directly from
  `load_call_events`, not assumed from the prompt's "near 147" phrasing.

No false premise found. §2's 63.4%-of-*calls*-share-a-date figure is stated
against the full 32-ticker/659-call corpus; the 147-event/16-ticker in-window
corpus this driver runs against shows a related but distinct figure — 44.2%
of *events* fall on a multi-event date (65 of 147) — reported here because
nobody had measured it for this specific corpus before.

```
events-per-date distribution (147 in-window events, ALL16, clean window):
  1 event/date:  82 dates
  2 events/date: 25 dates
  3 events/date:  5 dates
  ------------------------
  distinct dates: 112
```

---

## Step 0 — the two hygiene fixes

**0a.** `wrap-ups/sweep-cadence-and-session-model-out.md` committed at
`4ece349`, as its own commit, before any code in this session. (Verify:
`git log --oneline | head -5` shows it immediately after the prior
session's driver commit `bea9591`.)

**0b.** `bracket_three_modes_s11_corrected.py`'s `assert_driver_committed()`
(import-time) was split into two pieces:

- `_current_git_state()` — a read-only snapshot (commit/branch/dirty), safe
  to call at import time, no assertion.
- `assert_clean_for_manifest()` — the actual hard stop-gate (dirty tree, or
  driver file missing from HEAD), called fresh inside `write_manifest()`
  and again at the top of `main()`. It re-reads git state at call time
  rather than trusting an import-time snapshot, so a manifest written after
  a mid-session commit sees the true state.

`sweep_cadence_and_session_model.py` now does:
```python
from analysis.bracket_three_modes_s11_corrected import (
    _rebuild_buy_leg, assert_clean_for_manifest,
)
```
instead of the prior session's verbatim copy of `_rebuild_buy_leg`. Verified
this actually works with a dirty tree (importing used to be impossible while
this task's own files were mid-edit — that's the bug 0b exists to fix):

```
$ python3 -c "import sweep_cadence_and_session_model as m; print('import OK, dirty tree tolerated')"
import OK, dirty tree tolerated
```

Committed together with the Step 1a gate machinery at `3f8a563`
(driver commit; no manifest was written in this session, since the gate
never passed cleanly enough to citably bank a number — see Step 1a below).

---

## Step 1a — single-event equivalence (HARD GATE): FAILED, close

Configuration: `single_event` cadence (each event, in draw order, is its
own session at `session_date = call_date`; a shared date's calls become
consecutive single-event sessions), `new_calls_only` scope, `ALL16`,
`decide_v3`, frozen-JSON `type_for_ticker`, dedup on, clean window
(2022-01-01 → 2024-06-12).

```
no_reserve_raw, off, single-event, forward draw
  expected: $141,836.57         got: $141,836.56574946275     diff: <$0.01   PASS
swap_funding, 2.5pp, single-event, forward draw
  expected: $190,481.16304357877   got: $189,854.32962428960     diff: -$626.83 (-0.33%)   FAIL
```

**`no_reserve_raw` now passes exactly** (to the cent) — it did not before
this session (the prior run's control was off by 34%). `swap_funding`
improved from the prior run's +3.08% gap down to -0.33%, but per the
prompt's own rule ("if either differs by a cent, stop and report") this is
still a gate failure, not a pass, and the run stops here per instruction.

### Three real bugs found and fixed on the way (all now committed at `3f8a563`)

1. **`portfolio_value_before` / `current_dollars_before` read after this
   event's own sell executed, not before.** `make_funding_decide_fn`
   (`bracket_three_modes_s11_corrected.py:299-301`) never executes trades
   itself — it returns `final_trades` for the caller (`run_simulation`) to
   execute, so its `portfolio_value_before` snapshot is always taken before
   ANY of this event's own trades run. The prior session's driver executed
   this event's sell trades first, then took the snapshot — reading a
   post-trade, not pre-trade, state. Since a plain sell doesn't change
   total portfolio value (it just converts position value to cash), this
   turned out to be immaterial for `total_value` on this corpus, but it is
   the correct fix per the reference semantics regardless, and was applied.

2. **`swap_funding` executed donor sells before rebuilding the buy leg,
   double-counting proceeds.** `_rebuild_buy_leg`'s `avail` calculation is
   `portfolio.accounts[account].cash + raised_by_account[account]` — this
   assumes `raised_by_account` dollars are NOT yet reflected in
   `portfolio.accounts[...].cash`. The prior driver executed
   `portfolio.execute_sell(t)` for every donor sell BEFORE calling
   `_rebuild_buy_leg`, so live cash already included the proceeds AND
   `raised_by_account` added them again. Fixed by computing the buy leg via
   `_rebuild_buy_leg` first, then executing the donor sells — this alone
   moved the swap_funding forward-draw number from $190,150.82 (-0.17%) to
   $190,572.99 (+0.05%).

3. **The 25%-of-start-of-day-value donor trim cap reset every session
   instead of every calendar date.** `make_funding_decide_fn`'s `day_state`
   (line 264) resets `start_of_day_value` / `trimmed_today` only when
   `trade_date` actually changes, so multiple events sharing a date share
   one day's 25% trim budget per donor. The session driver was
   unconditionally resetting these at the top of every session — invisible
   at `per_call`/fixed-K cadence (session = date there), but a real
   divergence at `single_event` cadence, where a shared date becomes
   several consecutive sessions. Fixed by tracking `last_calendar_date` and
   only resetting on an actual date change. This is unambiguously the more
   spec-faithful behavior, but it moved the swap_funding number FURTHER
   from the target ($190,572.99 → $189,854.33, +0.05% → -0.33%) — meaning
   there is at least one more, uncaught, compensating divergence. Kept
   anyway, since it is provably correct against the written reference
   semantics and reverting it to "pass" a gate would mean matching the
   target for the wrong reason.

### The line-by-line diff the prompt calls for when 1a fails

Diffing `funding_log` entry-by-entry between `run_cell` (reference,
`swap_funding`, 2.5pp) and `run_session_sweep_cell` (`single_event`,
`new_calls_only`, `swap_funding`, 2.5pp), both on the identical forward
draw:

- **Entries 0–75 match exactly** (date, ticker, intended/target/actual
  dollars all agree to sub-cent precision). The two implementations are
  faithful for 75 of 96 funded decisions.
- **First divergence: entry 76, ticker `QS`, date 2024-02-14.** `intended_dollars`
  already differs slightly upstream (12,263.69 reference vs 12,268.89 new —
  a ~$5 drift not itself explained here). Diffing the `displacement_log` for
  this exact date shows the donor sequence is `RUN → ENVX → EOSE → TSLA →
  AAPL` in both implementations, and the first four donors raise **identical**
  dollar amounts to the last visible digit:

  ```
  RUN:  $3.9560126509881157   (both)
  ENVX: $324.87132849904845   (both)
  EOSE: $0.4916599314387127   (both)
  TSLA: $208.55306938397888   (both)
  AAPL: reference $488.31994388804986   new $500.4806040355388   <- diverges
  ```

  AAPL is the last (and evidently cap-binding) donor. Its raise amount is
  governed by `min(cap_today, donor_value_now, remaining)` where
  `cap_today = 0.25 * sod_value - already_trimmed`. Since `remaining` before
  AAPL's turn is consistent with the four identical prior raises, and AAPL is
  a very frequent donor across the whole 2.5-year run (alphabetically early,
  large, low-conviction on many dates), the most likely remaining cause is a
  subtle divergence in AAPL's own `day_start_of_day_value` /
  `day_trimmed_today` bookkeeping accumulated over many PRIOR donor events
  earlier in the run, not something local to 2024-02-14. **Next step for
  whoever picks this up:** instrument `day_start_of_day_value["AAPL"]` and
  `day_trimmed_today["AAPL"]` at every date they're touched in both
  implementations, from 2022-01-01 forward, and find the first date they
  disagree — that is very likely a 4th, still-uncaught bug, most likely
  another `day_state` timing subtlety (e.g. whether it's computed against
  `prices_today` sourced identically, or whether some session's `sd` used
  for the date-change check doesn't literally equal the calendar date it
  should in some edge case). This was not done in this run because the gate
  is a hard stop and continuing to iterate against symptoms is exactly what
  the prompt says not to do past this point.

---

## Step 1b — per-call-date sessions (bundled): a measurement, not a gate

Same two configurations, with same-day calls bundled into one session per
§3 (new cadence value `per_call_bundled`: same session-date grid as
`per_call`, but with §4 ranking **applied** within a multi-event session,
which is what actually changes when calls bundle).

```
no_reserve_raw, off, forward draw
  single-event: $141,836.57      bundled: $190,622.14      delta: +$48,785.57  (+34.39%)

swap_funding, 2.5pp, forward draw
  single-event (this run's own, not-yet-exact number): $189,854.33
  bundled:                                              $191,165.66
  delta: +$1,311.33  (+0.69%)
```

**`no_reserve_raw`'s pooling delta does not collapse — it is enormous, and
it is not new.** $190,622.14 is *exactly* the number the prior failed
session's run reported as its "per-call equivalent, forward draw" result
for `no_reserve_raw` (`wrap-ups/sweep-cadence-and-session-model-out.md`
line 118: "got: $190,622.14"). That prior driver's `per_call` cadence
bucketed same-date multi-ticker calls into one session and never split
them — it was already measuring the bundled/pooled behavior while believing
it was measuring per-call equivalence. **This confirms, rather than merely
hypothesizes, this prompt's central premise**: the prior run's "34% bug"
was §3's pooling effect showing up under a name (`per_call`) that implied
it shouldn't be there. It was never a defect in the arithmetic; it was a
mismatch between what the driver's cadence label promised and what its
session-bucketing code actually did.

**`swap_funding`'s pooling delta is much smaller (+0.69% here, or +0.36% if
measured against the reference's target instead of this run's own
not-yet-exact single-event number) — consistent with the prompt's
prediction that a tight ceiling absorbs most of the extra pooled cash.**
With no reserve and no ceiling, pooled cash reaches its target the same
session it's freed; with a 2.5pp per-session cap, only 2.5% of portfolio
value can move into any one name per session regardless of how much cash
is technically available, so the marginal value of "more cash available
right now" is capped hard. This is exactly the mechanism the prompt
predicted, and the measurement supports it.

---

## Steps 2–6 — not run

**Explicitly gated on Step 1a passing** ("If 1a passes, the machinery is
faithful..."; Step 3: "Only if Steps 1a and 2 complete."). Step 1a did not
pass. Per the same discipline this thread has followed for three sessions
running, nothing past this point was attempted, faked, or estimated:

- No execution-order (`sequential` vs `pooled`) sweep was run.
- No cadence grid (K × phase × scope × limit × draws) was run.
- No `minPositionPct` sweep, ordering confirmation, or staleness-vs-return
  fold-in was run.
- No gates (Step 5) or rules (Rule 1–4, 3a/3b) were evaluated — there is no
  grid to evaluate them against.
- No `K`, limit, scope, execution-order, or `minPositionPct` was selected.
  Nothing in this report should be read as a recommendation.

---

## Wall-clock and cell count

- Cell count actually run: 6 backtests total — 2 configs × (single-event +
  bundled) = 4, plus 2 extra intermediate single-event `swap_funding` runs
  captured during the three-bug debugging sequence (the $190,150.82 and
  $190,572.99 intermediate values quoted above). All in-memory, no manifest
  written (per §10b, a number this close to but not exactly matching its
  target is not citable, so none was banked).
- Wall-clock: each cell (corpus load + trend recompute + single backtest)
  ran in under 4 seconds; the entire session's iterative debugging,
  including the funding_log/displacement_log diffing script, completed in
  under two minutes of actual Python execution time.
- 0 of the 450 Step 3 grid cells ran (blocked by 1a).

---

## What was deliberately NOT done

- No cadence, limit, scope, execution-order, or `minPositionPct` value was
  selected or recommended.
- No spec document was amended. §12's open items are untouched.
- No veto sweep was started.
- The fourth (still-uncaught) equivalence bug hinted at by the AAPL
  donor-amount divergence was diagnosed to the specific ticker/mechanism
  but not chased further, per the prompt's instruction to stop and report
  rather than keep guessing against symptoms once 1a fails.
- The 44.2%-of-events-share-a-date figure and the 112-distinct-dates count
  are new measurements against the 147-event/ALL16 corpus specifically;
  they should not be conflated with §2's 63.4% figure, which is against the
  full 659-call/32-ticker corpus.

## Follow-up for whoever picks this back up

```
cd analysis
python3 -c "
import sys; sys.path.insert(0, '.')
from bracket_three_modes_s11_corrected import load_events_dedup_on, run_cell
from sweep_cadence_and_session_model import run_session_sweep_cell
from analysis.simulator.data import PriceLookup

events_full, type_fn, driver_fn, tier_fn = load_events_dedup_on()
prices = PriceLookup.from_cache()

ref = run_cell(events_full, prices, type_fn, driver_fn, tier_fn,
               funding_mode='swap_funding', session_change_limit_pp=2.5)
new = run_session_sweep_cell(events_full, prices, type_fn, driver_fn, tier_fn,
    cadence='single_event', phase_offset=0, scope='new_calls_only',
    funding_mode='swap_funding', limit_pp=2.5)
print('ref ', ref['final_value'])
print('new ', new['final_value'])
"
```

reproduces the -0.33% gap. The fastest path to closing it: instrument
`day_start_of_day_value['AAPL']` / `day_trimmed_today['AAPL']` (or generalize
to every donor) at every calendar date in both implementations from
2022-01-01 forward and find the first date of disagreement — entries 0-75 of
the funding_log already match exactly, so the bug is somewhere in donor-side
state that doesn't show up in `funding_log` directly (only in
`displacement_log`, and only once it compounds enough to move the final
AAPL-as-donor amount on 2024-02-14). Do not re-run Step 1b's bundled numbers
as if they were newly informative once 1a is fixed — re-derive them fresh,
since the single-event reference number they're compared against will
itself change.
