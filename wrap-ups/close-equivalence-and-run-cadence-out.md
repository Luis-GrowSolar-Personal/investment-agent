# Close equivalence and run cadence — PARTIAL RUN (updated)

**Resume status:** this wrap-up covers two sessions. Session 1 was a cold
start that did only Step -1 scaffolding and part of Step 0 hygiene. Session 2
(this update, 2026-09-01) resumed from `progress.json`'s `next_action` and
made real progress on Step 1 and ran Step 2 (Gate 1a) for real. No cells were
reused between sessions (session 1 ran none).

**This is still a partial run.** Steps 1 and 2 are now substantively worked
(Step 1 not yet closed; Step 2 run to a definitive result). Steps 3 through 8
were correctly **not attempted** — they are gated on Step 2 (Gate 1a) passing,
and it fails.

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

## What was deliberately NOT done

- The exact date/ticker of first divergence within `(2023-12-11, 2024-01-24]`
  was not pinned down (see next_action below for the concrete next step).
- No fix was applied for the fourth bug (root cause not yet found).
- Step 3 (spec-correction deltas), Step 4 (pooling re-derivation), Step 5
  (the full cadence grid), Step 6 (fold-ins), Step 7 (gates/rules scoring) —
  none attempted, all correctly gated on Step 2 passing.
- Nothing in this run disturbs the six settled sessions in §0 — the only
  code edit made (the backfill hypothesis) was reverted; the working tree
  has zero diff from HEAD.

## Exact resume point

`progress.json`'s `next_action`:

> Resume Step 1: pin the exact date within (2023-12-11, 2024-01-24] where
> ref's and new's portfolio share counts first diverge (total_value already
> disagrees by -$68.50 at 2024-01-24, the earliest common MTM-snapshot date
> after 2023-12-11, with zero funding/displacement/skip activity near that
> date in either implementation and no price-cache gaps). Do this by forcing
> `run_session_sweep_cell` to snapshot total_value AND per-ticker share
> counts every calendar day (not just session dates) in that window, or by
> instrumenting per-ticker share counts directly at every event boundary in
> both implementations, then diff. Once the exact date/ticker/trade is
> found, fix it (or classify as spec-vs-reference divergence per Step 3's
> toggle discipline), then rerun Gate 1a. Steps 3-8 remain untouched pending
> Gate 1a passing.

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
