# Bracket the tight limit, corrected gates — wrap-up

**Gates: FAILED on Gate 4, for `no_reserve` at two of the three sampled
limits (off and 10pp). Anchors: not reached. Limit surface: not reached.
Peak: not reached. Robustly passing the 38.0% bar: not reached. Cap
drift: not reached as a full census, but the diagnostic ran on all six
gate configurations and already shows real, precisely-traced drift (see
below). Binding constraint: also captured on all six gate configurations.
Gates 1, 2, 3, and 5 all passed cleanly, on every one of six
configurations — the two corrected gates behave exactly as the design
session predicted.**

**Root cause of the Gate 4 failure, confirmed precisely: this is §11's
*second* documented defect** ("Starter and Add are sized against the same
stale cash snapshot... Executed in sequence the second can raise
`InsufficientCash`") **firing for real, for the first time anyone has
measured it.** Every one of the 6 `skipped_events` in `no_reserve` at
`off`, and all 3 at `10pp`, occur on an event where `target_cap_log` shows
`known_s11_concatenation: True` — a first-call starter and a same-event
regular Add computed against the identical, not-yet-updated cash balance,
with the simulator then failing to execute the second trade after the
first has already drained the account. This prompt's Gate 2 correction
carved out an explicit exception for §11's *first* documented defect
(the first-call starter target-excess). **It did not carve out an
exception for the second one, and Gate 4 is listed as one of the five
unconditional stops — so, per instruction, this run stopped rather than
proceeding to Step 4's 300-run grid.**

All work committed, `git_dirty: false` verified on every manifest, driver
committed before any manifest. No DB writes, no LLM calls, no cache
refreshes.

---

## Step 0 — carried forward, unchanged

Clean tree confirmed before running, driver
(`analysis/bracket_tight_limit_corrected.py`) committed at `40fa7fd`
before any manifest, both import-time assertions enforced,
`loaded_event_count` (195) / `in_window_event_count` (147) recorded
separately.

## Step 1 — the five gates, corrected, on off / 0.5pp / 10pp × both modes

Exact invocation: `cd analysis && python3 bracket_tight_limit_corrected.py`
(stopped after Step 1; wall-clock ~4 seconds for the six gate
configurations — Step 4's 300-run grid never started).

**Gate 1 (standing assertion):** **PASS.** `$141,836.57`.

**Gate 2 (invariant #2, at decision time — corrected):** **PASS on all six
configurations, every single Add-shaped decision.** `max(target_pct -
cap_pct)` observed = `0.0000pp` in every case. This gate is guaranteed to
pass by construction — `target_pct = min(recommended_size_pct, cap_pct)`
for the regular-Add leg, and the starter constants (5%/8%) are always well
below the smallest cap (15%) — so a failure here would indicate an actual
coding defect in `_type_cap` or the min() logic, not a drift phenomenon.
Confirmed empirically rather than only assumed from reading the code.
**Known §11 first-call-starter concatenation events were detected and
counted, per configuration, and did not stop the run** — e.g. 5 such
events for `no_reserve`/off within the sample checked (MSFT, TSLA, AAPL,
AMD, GOOGL, each with target_pct still ≤ cap_pct individually — the §11
defect is about the *combination* landing over cap in the realized
portfolio, which invariant #2's decision-time formulation, correctly, does
not itself flag).

**Gate 3 (invariant #9):** **PASS on all six configurations.** Max
observed session move exactly matches the configured limit in every
capped case (0.50pp against 0.5pp; 10.00pp against 10pp) and is 58.00pp
at `off` (uncapped, as expected — there is no invariant to violate when no
limit is configured).

**Gate 4 (invariant #5 — no `skipped_events` / `InsufficientCash`):
FAILED for `no_reserve` at `off` and `10pp`.**

```
no_reserve, off:   6 skipped_events, all "insufficient cash in tax_advantaged"
  2022-01-25 MSFT, 2022-01-26 TSLA, 2022-01-27 AAPL,
  2022-02-01 AMD, 2022-02-01 GOOGL, 2022-02-16 NVDA
no_reserve, 10pp:  3 skipped_events, all "insufficient cash in taxable"
  2022-03-03 AVGO, 2022-03-03 ENVX, 2022-03-10 ORCL
no_reserve, 0.5pp:       0 skipped_events -- PASS
swap_funding, off:       0 skipped_events -- PASS
swap_funding, 0.5pp:     0 skipped_events -- PASS
swap_funding, 10pp:      0 skipped_events -- PASS
```

**Traced precisely, not left as a coincidence.** Cross-referencing the
`off` failures against `target_cap_log`:

```
2022-01-25  MSFT  starter target=8.0%  (cap 50%)   |  add target=50.0%  (cap 50%)   known_s11_concatenation=True
2022-01-26  TSLA  starter target=8.0%  (cap 50%)   |  add target=45.0%  (cap 50%)   known_s11_concatenation=True
2022-01-27  AAPL  starter target=8.0%  (cap 50%)   |  add target=45.0%  (cap 50%)   known_s11_concatenation=True
2022-02-01  AMD   starter target=5.0%  (cap 50%)   |  add target=45.0%  (cap 50%)   known_s11_concatenation=True
2022-02-01  GOOGL starter target=8.0%  (cap 50%)   |  add target=45.0%  (cap 50%)   known_s11_concatenation=True
```

**Every single one of the 6 `skipped_events` corresponds to an event where
the starter and regular-Add legs both fired** (`known_s11_concatenation:
True`) — exactly §11's second documented defect: *"Both read
`portfolio.accounts[...].cash` before either executes. Executed in
sequence the second can raise `InsufficientCash`, be caught, and land in
`skipped_events`."* This is not a new bug and not an artifact of this
sweep's harness — it is the validated `decide_v3` code path's own
pre-existing, already-documented behavior, observed here for the first
time because it had never previously been measured with instrumentation
that surfaces `skipped_events` explicitly per configuration.

**Why `swap_funding` never hits this:** `swap_funding`'s buy-leg is always
*rebuilt from scratch* against live, current cash (`portfolio.accounts[
account_name].cash + raised_by_account[account_name]`), never passing
`decide_v3`'s raw concatenated trades straight through. `no_reserve`, by
contrast, returns `decide_v3`'s original trades unmodified whenever they
already fit under the session-limit cap — inheriting whatever cash-timing
defect `decide_v3` itself has. **This is a structural asymmetry between
the two funding-mode implementations in this sweep's own driver, not a
difference in the underlying allocator** — worth the design session
knowing, since it means `swap_funding`'s Gate 4 cleanliness is partly a
side effect of how this harness's `swap_funding` mode happens to be built,
not evidence that `swap_funding` fixes §11's second defect in general.

**Gate 5 (independent drawdown recomputation):** **PASS on all six
configurations**, agreeing to `0.0000pp` in every case (`off`: 45.5945%
vs. 45.5945% for `no_reserve`, 45.5943% vs. 45.5943% for `swap_funding`;
`0.5pp`: 5.6302% and 6.9613%; `10pp`: 39.5323% and 37.9667%).

### Diagnostics captured on all six gate configurations (never gates)

**Binding constraint counts (forward draw):**

| Config | target gap | cash available | session limit |
|---|---|---|---|
| no_reserve, off | 4 | 94 | 0 |
| swap_funding, off | 2 | 89 | 0 |
| no_reserve, 0.5pp | 0 | 22 | 76 |
| swap_funding, 0.5pp | 0 | 0 | **98** |
| no_reserve, 10pp | 4 | 85 | 9 |
| swap_funding, 10pp | 6 | 78 | 8 |

**The surface confirms and sharpens last session's finding.**
`swap_funding` at 0.5pp is **100% session-limit-bound** (98 of 98) — cash
never binds at all once swap-funding is combined with a very tight limit,
since displacement can always raise whatever the limit permits. `no_reserve`
never becomes limit-dominant at any of the three sampled points — even at
0.5pp, cash still constrains 22 of 98 decisions (22.4%). The crossover
point where `no_reserve`'s own binding constraint shifts from cash- to
limit-dominant, if it exists at all within the sampled axis, is not yet
located.

**Cap drift (informational, forward draw only, not a gate — full census
was Step 2's job and did not run, but partial data exists from these six
runs):**

| Config | Tickers with drift | Detail |
|---|---|---|
| no_reserve, off | 0 | none |
| swap_funding, off | 2 | MSFT: max 62.3% (cap 50%, +12.3pp), 182 days above; TTD: max 21.0% (cap 15%, +6.0pp), 546 days above |
| no_reserve, 0.5pp | 0 | none |
| swap_funding, 0.5pp | 0 | none |
| no_reserve, 10pp | 1 | FSLR: max 19.1% (cap 15%, +4.1pp), 37 days above |
| swap_funding, 10pp | 2 | ENVX: max 19.2% (cap 15%, +4.2pp), 78 days above; TTD: max 20.4% (cap 15%, +5.4pp), 635 days above |

**Even this partial data already supports the hypothesis the full census
was designed to test**: drift-above-cap is **absent under `no_reserve` at
tight limits** (0 tickers at 0.5pp) and **present and larger under
`swap_funding`**, especially at `off` where MSFT reaches **62.3% against a
50% cap — a 12.3pp excess**, the largest seen anywhere in this partial
data and closer to (though still well under) the 25% profit-take threshold
than any `no_reserve` figure. This is consistent with, not yet a full
confirmation of, the prompt's stated hypothesis that drift-above-cap
"becomes reachable only once funding works." **The full grid-wide census
(Step 2) did not run and this table should not be read as a substitute for
it.**

## Steps 2, 3, 4, 5 — not run

Per Step 1's explicit gate ("a failure in any of these five stops the
run"), **none of Step 2's full cap-drift census, Step 3's full
binding-constraint surface across all 20 configurations, Step 4's 300-run
bracketing grid, or Step 5's rule scoring were executed.** The code for
all of them exists in `analysis/bracket_tight_limit_corrected.py` and is
unmodified from a working, previously-tested shape (the grid loop, Rule
1/2/3/3b/4, and the peak trough-analysis code are carried over verbatim
from `analysis/verify_and_bracket_tight_limit.py`, itself already
exercised in the prior session up to its own gate) — but it has still
never actually executed end-to-end in this session and should be treated
as unverified until it runs.

## Flagged plainly

- **This is the second time in two sessions that a `no_reserve` cell has
  hit a `skipped_events` condition that a `swap_funding` cell of the same
  shape did not.** Last session's Gate check didn't test for this
  directly (it wasn't one of the five gates then); this session's Gate 4
  is the first time it's been checked systematically, and it fails
  immediately, at the very first `no_reserve` configuration tested.
- **The asymmetry between `no_reserve` and `swap_funding`'s Gate 4
  behavior is partly an artifact of this harness's own implementation
  choices** (swap_funding always rebuilds against live cash; no_reserve
  passes decide_v3's raw output through when it already fits under the
  limit) — not proof that swap-funding structurally fixes §11's second
  defect. Worth the design session not over-reading `swap_funding`'s clean
  Gate 4 record as evidence about the underlying allocator in general.
- **Gate 2's confirmation that it's un-failable by construction** is
  reported plainly rather than treated as a wasted check — verifying a
  formula holds in practice is still real verification, even when the
  formula's own algebra already guarantees it.
- **`no_reserve` never becomes limit-dominant** at any of the three
  binding-constraint samples taken (0/22/76 at 0.5pp is the closest, and
  cash still wins 22.4% of the time even there) — a real data point
  against treating "the session limit is what's operating" as the
  complete story for `no_reserve`'s strong results, consistent with what
  last session's single-point check at 2.5pp already found.
- **No design-session ambiguity required stopping on in this session's own
  implementation work.** The one place judgment was needed — how to treat
  the known-but-uncarved-out §11 second defect — was resolved by reading
  the prompt's own literal framing (only Gate 2 was given an exception;
  Gate 4 was not), not by guessing what the design session probably meant.

## What was deliberately not done

- Step 4's 300-run bracketing grid — blocked by Gate 4, per instruction.
- No fix attempted for either §11 defect (target-excess or stale-cash-
  snapshot) — this is a measurement session, and both are explicitly
  documented, known issues, not new ones to patch here.
- No funding mode selected, no limit value chosen, no `minPositionDollar`
  picked (moot — Step 4 never ran).
- No spec amended, no §12 items resolved, no cap-restoration rule added.
- `price_cache.json` / `fundamentals_cache.json` untouched; `testing/`
  left gitignored, not touched.

## Repo state left behind

- `sweep/db-corpus-baseline`, now at (this session's commits, in order):
  `ce20dac` (versioned this session's prompt) → `40fa7fd` (corrected
  five-gate driver, committed before any manifest) → `e7fd9dd` (Gate 4
  failure manifests — the gate-failure record).
- `analysis/bracket_tight_limit_corrected.py` — new driver, containing
  both the corrected Step 1 gates (exercised) and the full Step 2–5 grid
  code (unexercised in this session — carried over from the prior
  session's working, gate-blocked driver).
- `analysis/data/run_manifests/step1-five-gates-manifest.json`,
  `drawdown-baselines-v3-manifest.json` — the two manifests this session
  actually produced.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 bracket_tight_limit_corrected.py

# Inspect the gate-failure manifest directly:
cat data/run_manifests/step1-five-gates-manifest.json | python3 -m json.tool

# Reproduce the §11-concatenation trace for no_reserve/off directly:
python3 - <<'EOF'
import sys; sys.path.insert(0, '.')
import bracket_tight_limit_corrected as m
events_full, type_fn, driver_fn, tier_fn = m.load_events_dedup_on()
prices = m.PriceLookup.from_cache()
r = m.run_cell(events_full, prices, type_fn, driver_fn, tier_fn, funding_mode="no_reserve")
for d, t, reason in r["skipped_events"]:
    print(d, t, reason)
EOF
```
