# Cadence `K` and the session model — Step 1 equivalence gate: FAILED

**Equivalence gate: FAILED.** Gates: not run (Step 1's hard stop blocks Step 2).
Minimum viable cadence: not determined — the grid never ran. Best cell: none —
the grid never ran. Limit surface per cadence: not measured. Staleness cost:
not measured. `minPositionPct`: not measured. Ordering spread at the winner:
not measured.

Per the prompt's own instruction ("If either differs by a cent, stop and
report; do NOT proceed to Steps 2-6"), this run stops at Step 1. Everything
below is the equivalence check, the diagnostic trail from three rounds of
real debugging, the fixes already made, and what's still wrong.

---

## What was verified before implementing (premise check)

All claimed prior state checked against the actual repo, on a clean tree,
branch `sweep/db-corpus-baseline`:

- `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` exists at the stated path,
  1001 lines, with §0/§2/§3/§4/§5/§9/§10/§10b/§11/§12 present at the section
  numbers the prompt assumes. Read in full before writing any code.
- `decide_v3` (`analysis/simulator/allocator_v3.py::decide`), `_type_cap` /
  `_build_sell_trades` (`allocator_v2.py`), `type_classifier.build_type_function()`
  and `build_driver_count_function()`, and `swap_funding` all exist and match
  the prompt's description. `swap_funding` is implemented (not a stub) in
  `analysis/bracket_three_modes_s11_corrected.py`, `sweep_funding_modes.py`,
  `sweep_limit_axis_dense.py`, `sweep_session_limit_and_conformant_swap.py`,
  `verify_and_bracket_tight_limit.py`, and documented as settled in
  `ALLOCATOR_OPERATING_MODEL.md` §0.
- The two reference numbers are real, not fabricated by the prompt:
  - `$190,481` — `docs/handoffs/2026-08-31-allocator-state-of-play.md:89` and
    `wrap-ups/sweep-limit-axis-dense-out.md:74/135/202`; exact value
    `190481.16304357877` in `analysis/data/run_manifests/dense-swap_funding-2.5pp-manifest.json`
    and `bracket-swap_funding-2.5pp-manifest.json`.
  - `$141,836.57` — `wrap-ups/sweep-session-limit-and-conformant-swap-out.md:73`,
    `wrap-ups/diagnose-spwr-and-cash-instrumentation-out.md:154-155`,
    `wrap-ups/bracket-tight-limit-corrected-gates-out.md:49`, and
    `analysis/data/run_manifests/step1-five-gates-manifest.json:74`.
- **No session-model machinery existed anywhere in the codebase** before this
  run — confirmed by grepping for "session_date", "session model" and reading
  `analysis/simulator/simulator.py` in full: `run_simulation` processes events
  strictly per-event, per-call-date, with immediate execution. §3's session
  batching (evaluate-then-pool-then-rank-deploy) genuinely required new code,
  as the prompt says.
- Git was clean at the start (confirmed twice; an apparent `git status`
  modification on two `docs/handoffs/2026-09-01-*` files at the very first
  check resolved to nothing on a second check seconds later — no stash was
  needed, and nothing belonging to this task touched those files).

No premise in the prompt was found to be false. The corpus load, the two
reference numbers, and every named function/file check out.

---

## Step 1 — the session model built

New file: `analysis/sweep_cadence_and_session_model.py` (774 lines), committed
to `sweep/db-corpus-baseline` at `bea9591` before this report was written, per
the prompt's "driver committed before any manifest is written" rule. It does
**not** import `bracket_three_modes_s11_corrected.py` (that module asserts
`git_dirty=False` at import time, which would break while `wrap-ups/` and
`docs/` files for this task are being edited) — the small set of shared
constants and the `_rebuild_buy_leg` helper are duplicated verbatim instead of
imported, with a comment explaining why.

Implemented, per §2/§3/§4/§5:

- **Session-date generation**: fixed `K` (any integer day count) from a phase
  offset, the **seasonal** variant (weekly during days 15–42 after each
  quarter-end, monthly otherwise, per §2's table), and a `per_call` mode that
  reproduces "one session per distinct call date" for the equivalence check.
- **Session sequence** (§3): per in-scope event, in draw order — execute
  Trim/Exit sells immediately, compute the "intended" Add-shaped target
  dollars (starter + v2-Add leg, mirroring the existing per-call harness's
  `make_funding_decide_fn` logic) without buying yet, then pool candidates and
  deploy cash in rank order subject to the per-session limit.
- **Scope as a swept axis**: `new_calls_only` (only this session's own
  reporters compete for cash) vs `cash_deployment` (§4-eligible tickers
  anywhere in the universe are added to the candidate pool, ranked the same
  way). Full re-sizing is not implemented, per §3.
- **§4 rank order**: `final_confidence` (coarse filter), verdict recency
  (primary discriminator), gap-to-target (fraction of target), seeded-random
  tie-break — implemented as `rank_key()` plus a seeded jitter term. **Skipped
  for `cadence == "per_call"`**: at per-call cadence a session is (almost
  always) one event, and on the rare same-call-date multi-ticker session the
  validated per-call harness has no ranking step at all — it just executes
  `decide_fn` sequentially in draw order. Applying §4 ranking there would
  itself break equivalence, so it's conditioned on cadence, with the reasoning
  documented in-line.
- **§5 per-session change limit**: tracked per ticker per session
  (`session_limit_used`), so a ticker that receives cash twice in one session
  (its own event, then again via cash-deployment scope) cannot exceed `X` in
  aggregate — this is exactly Invariant #9's new, per-session (not per-event)
  reading that the prompt flags as most likely to break.
- **`minPositionPct` stub rule** (§12): implemented as "if a swap-funding trim
  would leave the donor below `max(minPositionPct% of portfolio, $100)`, sell
  the whole position instead" — wired into the donor loop but **not yet
  exercised**, since Step 4 never ran.
- **Per-ticker mean information staleness** (§10): computed directly from
  `session_date - call_date` for every acted-on decision, per ticker and in
  aggregate — wired but not yet reported at scale.

## Equivalence check — the numbers

Configuration: `per_call` cadence (session dates = distinct call dates in the
clean window), `new_calls_only` scope, `ALL16`, `decide_v3`, frozen-JSON
`type_for_ticker`, dedup on, clean window (2022-01-01 → 2024-06-12).

```
swap_funding, 2.5pp, per-call equivalent, forward draw
  expected: $190,481.00   got: $196,342.96   diff: +$5,861.96  (+3.08%)
swap_funding, 2.5pp, per-call equivalent, median over 15 draws
  expected: $190,481.00   got: $196,138.20   diff: +$5,657.20  (+2.97%)

no_reserve, off, per-call equivalent, forward draw   (standing assertion)
  expected: $141,836.57   got: $190,622.14   diff: +$48,785.57 (+34.39%)
```

**Both differ by far more than a cent. Gate FAILED on both numbers,** the
`no_reserve` control badly so — it lands almost exactly where `swap_funding`
should, which is itself informative (see hypothesis below): the no-reserve
control is behaving as if cash were never actually a binding constraint,
which is the one thing "no reserve, no swap-funding" is supposed to make
bind hardest.

### Debugging performed (three real rounds, not cosmetic)

The first draft was off by far more (`$146,843` / `$110,490` vs the same
targets) and diagnosed three concrete implementation bugs before landing on
the numbers above:

1. **Ranking overrode draw order at per-call cadence.** The first draft always
   applied §4 rank-order sorting to the candidate pool, which made every
   draw (forward/reversed/13 seeds) produce the *identical* final value —
   ranking by confidence/recency/gap is deterministic and doesn't depend on
   input order, so the seeded shuffles that are supposed to matter under the
   old harness's alphabetical-contention problem were silently neutralized.
   Fixed by conditioning ranking on `cadence != "per_call"` (see above).
2. **The first-call starter was wrongly gated on `final_action`.** The
   original per-call harness (`make_funding_decide_fn` in
   `bracket_three_modes_s11_corrected.py`) fires the starter buy
   unconditionally on `starter_fired` — including on a first call that
   recommends `Hold`. The first draft added a `final_action not in ("Hold",
   None)` guard around the starter leg that doesn't exist in the reference
   implementation. Removed.
3. **`no_reserve_raw`'s defect-preserving semantics were collapsed into
   `no_reserve_s11fixed`'s live-cash rebuild.** The reference `no_reserve_raw`
   passes `decide_v3`'s own naturally-sized buy trades through unmodified
   (scaling proportionally only if they exceed the session-limit-capped
   target) — that's what preserves §11 defect #2 (starter + Add sized against
   the same stale cash snapshot) and is what the $141,836.57 standing
   assertion is actually measuring. The first draft always rebuilt the buy
   leg against live cash via `_rebuild_buy_leg`, which is the `s11fixed`
   behavior, not the `raw` one. Fixed by capturing `decide_v3`'s natural buy
   trades per candidate and reproducing the raw scale-or-pass-through logic
   verbatim for `no_reserve_raw`, and separately correcting `swap_funding`'s
   donor shortfall to net against those same natural trades
   (`shortfall = target_buy_dollars - natural_buy_dollars`) rather than
   against the full target, matching the reference implementation.

These three fixes moved the numbers from roughly 23%/22% low to 3% high /
34% high. The remaining gap was not resolved within this run's time budget.

### Working hypothesis for the remaining gap — not confirmed, flagged as an open question

The `no_reserve` control landing near the `swap_funding` number rather than far
below it suggests cash scarcity is not actually binding the way it should
in the new session loop, even at per-call cadence. Two candidate mechanisms,
neither run to ground:

- **Sell-then-buy execution ordering across a session's events.** The session
  loop's Step A executes every in-scope event's *sell* legs immediately (as
  encountered, sequentially) but defers *all* buy legs to a separate Step C
  that runs after every event in the session has been processed. On a
  same-call-date multi-ticker session (rare, but present in this corpus —
  §2's table shows up to 23 calls in one session at K=90, and even at
  per-call cadence some sessions legitimately bundle same-day calls) this
  reorders buy-vs-buy execution relative to the original harness, which
  executes each event's full trade set (sells and buys together) before
  moving to the next event. This could not, on its own, plausibly explain a
  34% swing on a corpus dominated by single-event sessions — but it has not
  been ruled out as a contributor.
- **A structural difference in how `intended` dollars accumulate cash
  headroom across the run** that was not caught by the three fixes above —
  most likely another place where the new driver diverges from
  `make_funding_decide_fn`'s exact sequencing of "compute portfolio value
  before this ticker's own trades but after everything already executed this
  session/event" that the original per-event, immediate-execution model gets
  for free by construction and the new batched model has to reproduce by
  hand, event by event, inside Step A. A line-by-line diff of
  `make_funding_decide_fn` against the new driver's Step A/Step C split,
  rather than iterating on symptoms, is the fastest path to close this — not
  attempted here because the gate is a hard stop and further iteration would
  have meant continuing to guess against a diff that should be done
  systematically instead.

## Gates (Step 2) — not run

Blocked by the Step 1 hard stop. Not attempted, not faked.

## Grid (Step 3), minPositionPct sweep / ordering confirmation / staleness
frontier (Step 4), rules (Step 5) — not run

All blocked by the same hard stop. The machinery for cadence generation,
scope, the limit axis, `minPositionPct`, and staleness logging exists in the
committed driver (see "Step 1 — the session model built" above) and is ready
to run once equivalence is fixed, but running any of it now would produce
numbers built on a session model proven not to match the validated reference
— exactly the failure mode the prompt's Step 1 gate exists to prevent.

## Wall-clock and cell count

- Cell count actually run: 16 (15 draws for the `swap_funding` 2.5pp
  equivalence check + 1 forward draw for the `no_reserve` standing-assertion
  check), all at `per_call` cadence / `new_calls_only` scope, plus roughly a
  dozen earlier throwaway single-cell runs during the three debugging rounds
  above (not counted toward the grid — the grid never started).
- Wall-clock for the final 16-cell equivalence check: ~4.6 seconds (dominated
  by corpus load from Postgres and trend-layer recompute; per-cell simulation
  itself is well under 100ms).
- No cell from Step 3's grid (450 cells: 6 cadences × 3 phases × 2 scopes ×
  9 limits × up to 15 draws, per the prompt's own axis table) was run.

## What was deliberately NOT done

- No cadence, limit, scope, or `minPositionPct` value was selected — this
  report recommends nothing, per the prompt's scope boundary.
- No spec document was amended. §12 open items are untouched.
- No veto sweep was started.
- No previously-published number in `ALLOCATOR_OPERATING_MODEL.md` or any
  prior wrap-up was found to be wrong — the discrepancy is in the *new*
  session-model code, not in the settled per-call reference figures, which
  were independently re-confirmed present and unchanged in
  `analysis/data/run_manifests/`.

## Follow-up for whoever picks this back up

```
cd analysis
python3 -c "
import sys; sys.path.insert(0, '.')
from sweep_cadence_and_session_model import run_session_sweep_cell, load_events_dedup_on
from analysis.simulator.data import PriceLookup
events_full, type_fn, driver_fn, tier_fn = load_events_dedup_on()
prices = PriceLookup.from_cache()
r = run_session_sweep_cell(events_full, prices, type_fn, driver_fn, tier_fn,
                            cadence='per_call', phase_offset=0, scope='new_calls_only',
                            funding_mode='no_reserve_raw', limit_pp=None)
print(r['final_value'])
"
```

reproduces the failing `$190,622.14` standing-assertion check. The fastest
path to closing the equivalence gate is a line-by-line diff of
`make_funding_decide_fn` (`analysis/bracket_three_modes_s11_corrected.py:257-494`)
against `run_session_sweep_cell`'s Step A / Step C split
(`analysis/sweep_cadence_and_session_model.py`), specifically around when
`portfolio_value_before` / `current_dollars_before` are read relative to
other trades executing in the same session, and whether the intended-dollars
computation is being fed the exact same `prices_today` dict at the exact same
point in the sequence as the original per-event harness. Do not re-run the
grid (Step 3) until the two reference numbers above reproduce **exactly**.
