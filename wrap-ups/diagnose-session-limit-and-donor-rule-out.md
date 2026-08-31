# Session limit vs. funding mode — which one actually did the work — wrap-up

**Session limit verdict: REAL — config C (`no_reserve`+10pp) median $179,666
vs. config A (`no_reserve`, unmodified) max $154,398, against the
pre-declared rule. Swap-funding verdict: INSIDE THE NOISE BAND — config B
(`swap_funding`+10pp) median $151,504 sits below A's own max. Donor
decomposition: 139 of 266 (52.3%) displacements on cell 6, 224 of 426
(52.6%) on cell 7, were on `Hold`-verdict donors — sells the analyst never
asked for; roughly an even split with `Trim`/`Exit`-accelerated sells.
Cells passing the pre-declared bar: `prior-5 cash_reserve 20%` and the new
`7-datecap` (swap_funding + 10pp + per-date trim cap) — both by having the
lowest drawdowns in the grid, not the highest returns.**

All work committed to `sweep/db-corpus-baseline` at `2733c0c` (guard fix at
`82a8053`). No DB writes, no LLM calls, no cache refreshes. Full detail
below.

---

## Step 0 — three things before any cell ran

### 0a. The signature guard, made structural — with one deviation flagged

The prompt's literal instruction: *"raise if the resolved signature does
not accept `tier`, `is_first_call` and `driver_count` explicitly."*
**Implemented narrower than written, and here's why:** `analyzer/simulator/allocator.py`'s
`decide_v1` — used deliberately, by design, in `run_expanded_test.py`'s v1
comparison and elsewhere in this codebase — does **not** accept any of
those three parameters at all. It never has; v1 predates tier-awareness
entirely. A literal, unconditional guard would make every legitimate,
correct v1 invocation across the whole codebase "an impossible run,"
which is not the failure this guard exists to catch.

**What actually broke twice** was specifically a `**kwargs`-only wrapper
signature defeating `inspect.signature(decide_fn)`'s parameter-name check —
`"tier" in sig.parameters` is `False` for a bare `**kwargs` catchall even
though the function *would* accept `tier` if it were passed. The guard
implemented instead: raise `TypeError` if `decide_fn`'s signature contains
a `VAR_KEYWORD` parameter (`**kwargs`) **without also** naming `tier`,
`is_first_call`, and `driver_count` explicitly. A function that simply
doesn't declare these parameters at all (v1) is unaffected — the existing
`if "X" in sig.parameters` checks already no-op correctly for it. Only a
`**kwargs` catchall silently masking them is now impossible.

**Verified it catches the actual bug**, standalone:
```python
def broken_wrapper(**kwargs):
    return decide_v3(**kwargs)
# ... run_simulation(..., decide_fn=broken_wrapper, ...) raises:
# TypeError: decide_fn 'broken_wrapper' accepts **kwargs but does not
# explicitly declare ['tier', 'is_first_call', 'driver_count'] -- ...
```

**Stop-gate check:** re-ran the entire prior 8-cell funding-mode sweep
(`analysis/sweep_funding_modes.py`) under the new guard. **No cell failed.**
Every `decide_fn` in that script (and in this session's new
`session_limit_and_donor_probe.py`) already declares the three parameters
explicitly, by construction, after last session's fix — so the guard is a
regression fence, not a live blocker, for anything in this thread. Change
committed at `82a8053`; code at
`analysis/simulator/simulator.py` around the existing `inspect.signature`
call.

### 0b. Manifests

Every cell in this run, plus a fresh re-run of the prior 8-cell sweep under
the guard, now has a `<run_id>-manifest.json` in
`analysis/data/run_manifests/`, matching §10b's field list (git identity,
corpus window/hashes, DB snapshot hash, cache/type-classification hashes,
params, results, output hash).

**Deviation flagged:** `analysis/data/*` is blanket-gitignored (only
`type_classifications.json` and `trend_verdict_fixtures.json` were
allowlisted). §10b's own text says *"a result that has no manifest is not
citable"* and *"commit before citing"* — but the manifest directory itself
would have been silently gitignored, defeating the point. Added two lines
to `.gitignore` un-ignoring `analysis/data/run_manifests/` specifically (not
touching the blanket ignore for caches/evals), so the manifests this run
produced are actually committed and citable rather than existing only on
disk. This is a `.gitignore` edit, which is a broader-than-file-local
change — flagging it explicitly as a deviation made to satisfy §10b's own
stated requirement, not a unilateral policy call.

**git state at manifest-generation time: `git_dirty: true`** (recorded
faithfully in every manifest). The dirt is **`CLAUDE.md`** (modified) plus
three untracked items — `server/scripts/*.js`, `testing/`, and (before this
run's own commit) this run's own new files. **None of these are inputs to
the simulator, the loader, or any allocator code** — I did not touch
`CLAUDE.md`, and `server/scripts/`/`testing/` are unrelated to
`analysis/`. Per the prompt's own fallback ("if you cannot [stash/commit],
record `true` and say plainly"): I committed everything this run
touched (`82a8053`, `2733c0c`), leaving the pre-existing unrelated dirt in
place rather than staging files outside this task's scope. **The numbers
below are reproducible from commit `2733c0c` exactly; the repo's overall
working tree is not fully clean, for reasons unconnected to any of them.**

### 0c. Standing assertion

```
no_reserve control (dedup on): $141,836.57
Standing assertion PASSED.
```

(Matches `$141,837` to rounding; dedup removes the one duplicate FSLR
transcript per the prior session, hence 195 events vs. 196 without dedup —
consistent with `sweep-funding-modes-out.md`.)

---

## Step 1 — the decisive measurement: ordering probe under the session limit

Exact invocation: `cd analysis && python3 session_limit_and_donor_probe.py`.
Dedup **on** for all three configs, as instructed.

| Config | forward | reversed | seed1 | seed2 | seed3 | seed4 | seed5 | min | median | max | spread (% of median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** — `no_reserve`, no limit | $141,837 | $117,455 | $138,070 | $141,096 | $154,398 | $136,553 | $135,732 | $117,455 | **$138,070** | **$154,398** | $36,943 (26.8%) |
| **B** — `swap_funding` + 10pp | $154,392 | $148,759 | $149,133 | $153,215 | $153,374 | $149,830 | $151,504 | $148,759 | **$151,504** | $154,392 | $5,632 (**3.7%**) |
| **C** — `no_reserve` + 10pp | $189,134 | $171,919 | $179,666 | $176,952 | $189,528 | $176,758 | $183,420 | $171,919 | **$179,666** | $189,528 | $17,609 (9.8%) |

**Pre-declared rule, applied mechanically, not softened:**

> *The 10pp session limit's outcome advantage counts as real only if
> configuration C's median across seeds exceeds configuration A's maximum
> across seeds.*

- **Config C: median $179,666 > A's max $154,398 → REAL.** C's *worst*
  outcome across all 7 draws ($171,919) still exceeds A's *best* outcome
  ($154,398). The two distributions do not overlap at all. The session
  limit's outcome advantage is not arrival-order luck on this corpus.
- **Config B: median $151,504 < A's max $154,398 → INSIDE THE NOISE BAND.**
  Every single one of B's 7 draws falls inside A's own $117,455–$154,398
  range. **`sweep-funding-modes-out.md`'s cell 7 result ($154,392) was
  itself A's own seed-3 draw, to within $6.** Swap-funding's headline
  return number cannot be distinguished from a re-rolled tie-break on this
  measurement. This is the design session's suspicion, confirmed exactly.

**Fragility (§10 rule 2), reported alongside the medians as instructed:**
Config A is the most fragile config in the whole probe (spread = 26.8% of
its own median) — its own reported $141,837 sits almost exactly at its
median, meaning the historical figure is unremarkable inside a wide,
noisy range. **Config B is the least fragile (3.7% spread)** — its return
doesn't clear the bar, but it is by a wide margin the most reproducible
number in this table. Config C is in between (9.8%). **A configuration
can be simultaneously "the best-performing" (C) and the "same information
value regardless of which seed you happened to draw" (B) — they are
answering different questions**, and neither dominates the other on both
axes.

## Step 2 — the donor rule

### 2a. Displacement decomposition

Extended `displacement_log` to record, per sale: donor's latest
`final_action`, donor's position value as % of portfolio before/after, and
its gap-to-target.

**Cell 6 (`swap_funding`, no limit) — 266 displacements:**

| Split | Count | Share |
|---|---|---|
| On `Hold`-verdict donors (sells never asked for) | 139 | 52.3% |
| On `Trim`/`Exit`-verdict donors (accelerated sells) | 127 | 47.7% |
| Left donor below 2% of portfolio | 216 | 81.2% |
| Left donor below 1% of portfolio | 191 | 71.8% |
| Left donor below 0.5% of portfolio | 172 | 64.7% |

**Cell 7 (`swap_funding` + 10pp) — 426 displacements:**

| Split | Count | Share |
|---|---|---|
| On `Hold`-verdict donors | 224 | 52.6% |
| On `Trim`/`Exit`-verdict donors | 202 | 47.4% |
| Left donor below 2% of portfolio | 371 | 87.1% |
| Left donor below 1% of portfolio | 332 | 77.9% |
| Left donor below 0.5% of portfolio | 295 | 69.2% |

**Both cells split almost exactly 52/48 between `Hold` and `Trim`/`Exit`
donors.** Swap-funding is neither predominantly "a new allocation
mechanism" (raiding positions the analyst was content to hold) nor
predominantly "a timing shim" (front-running exits already coming) — it's
close to an even mix of both, consistently across the limited and
unlimited variants.

**The position-size distribution is the sharper finding for the design
session's `minPositionDollar` question:** roughly **7 in 10 draws leave the
donor below 1% of portfolio**, and nearly **7 in 10 leave it below 0.5%**
in the 10pp-limited cell. Whatever floor gets chosen, a floor at or below
1% would constrain almost nothing observed here; a floor materially above
1% (2–3%) would visibly change donor behavior. **Reported, not chosen** —
per instruction.

**Realized gain/loss split by donor-verdict type — not computed at
per-sale granularity.** `RealizedSale` records don't carry a back-reference
to which displacement event produced them, and a donor can be drawn on
multiple times across the window (e.g., `EOSE` 58–70 times), so a clean
per-sale Hold-vs-Trim/Exit gain attribution isn't available without
threading an id through `_build_sell_trades` (a change to shared
production code, out of scope here). What **is** available and reported:
aggregate realized gain from *all* displacement sells combined —
**-$32,679 (cell 6)** and **-$24,950 (cell 7)**, both losses, both already
reported in the prior sweep. Flagging this as a real gap in this session's
instrumentation rather than presenting a fabricated split.

### 2b. Inverted donor-ranking gap term

Ran `swap_funding` + 10pp with the gap-to-target term inverted for donors
only (furthest-below-own-target becomes the preferred donor):

| | Final value | Displacements | Realized gain |
|---|---|---|---|
| Cell 7, normal | $154,392 | 426 | -$24,950 |
| Cell 7, inverted | $154,291 | 426 | -$25,002 |

**Essentially no difference** — $101 apart on final value, identical
displacement count, and the donor-aggregate tables are nearly indistinguishable
(a one-event shift between AMD and ENVX is the only visible change):

| Donor | n (normal) | $ (normal) | n (inverted) | $ (inverted) |
|---|---|---|---|---|
| AAPL | 38 | $17,828 | 38 | $17,823 |
| MSFT | 15 | $13,986 | 15 | $13,986 |
| AMD | 13 | $12,798 | 14 | $12,771 |
| RUN | 65 | $10,340 | 65 | $10,335 |
| TSLA | 38 | $9,303 | 38 | $9,293 |
| GOOGL | 29 | $8,340 | 29 | $8,340 |
| EOSE | 70 | $6,127 | 70 | $6,127 |
| FSLR | 36 | $5,963 | 36 | $5,958 |
| ENVX | 21 | $5,748 | 20 | $5,717 |
| QS | 73 | $4,639 | 73 | $4,639 |
| NVDA | 10 | $4,190 | 10 | $4,190 |
| AMPX | 14 | $742 | 14 | $739 |
| SPWR | 4 | $13 | 4 | $13 |

**This contradicts the design session's stated concern about MSFT.** The
prior report flagged that the un-inverted gap term "preferentially harvests
the positions §3 relies on being allowed to drift up" and pointed at MSFT
(15 draws / $48,017 in the *unlimited* cell 6). But in **cell 7** (the
10pp-limited cell this probe actually inverted), MSFT is drawn on **15
times either way** for an **identical $13,986** — the gap term is not
what's driving MSFT's selection here. On this corpus, in this cell, the
**confidence and recency terms dominate** the donor ranking almost
entirely; the gap term is a tie-breaker that rarely changes which donor
gets picked. **The concern that motivated this test does not reproduce in
the cell it was tested against** — worth the design session knowing
directly rather than assuming the fix landed because it was tried.

### 2c. Per-date trim cap (not blocked — implementable with existing state)

**Stop-gate did not trigger.** The per-date cap is trackable entirely
within the existing `decide_fn` closure: since the simulator calls
`decide_fn` in strict chronological order, a trade-date change is a
reliable day-boundary signal. Added a `day_state` dict that (a) snapshots
every held ticker's value at the first event of each new date and (b)
accumulates dollars trimmed from each donor across all events sharing that
date, capping cumulative same-day trims at 25% of the **start-of-day**
value rather than 25% of the (possibly already-reduced) value seen at each
individual event.

| | Final value | Max DD | Displacements |
|---|---|---|---|
| Cell 7, per-event cap (uncapped by date) | $154,392 | 39.9% | 426 |
| Cell 7, per-date cap | **$160,219** | **38.0%** | **358** |

**The per-date cap is a real, if modest, improvement on both axes**: 68
fewer displacement sells (many small repeated same-day trims collapsed
into fewer, larger ones bounded correctly), a lower max drawdown, and a
higher final value. This is the literal, correct reading of "at most 25% of
the donor **per session**" — the previous implementation was measurably
more aggressive than the spec's own wording, by allowing each of several
same-day events to independently claim 25% of whatever the donor's value
was *at that moment*, compounding across events on a shared date.

## Step 3 — scoring every cell against the pre-declared bar

**Benchmarks, computed once on the exact clean window, frozen caches, no
substitution:**

```
SPY final:  $113,980.12
QQQ final:  $119,178.08
TMFC final: $120,511.89
Equal-weight-of-universe final: $120,427.18
```

Drawdown bar: **38.0%** (median baseline + 5pp, as given).

| Cell | Final | Max DD | Beats SPY/QQQ/TMFC | Score |
|---|---|---|---|---|
| prior-1 `no_reserve` dedup=off | $141,837 | 45.6% | all 3 | FAIL (DD) |
| prior-2 `no_reserve` dedup=on | $141,837 | 45.6% | all 3 | FAIL (DD) |
| prior-3 `cash_reserve` 5% | $128,304 | 41.7% | all 3 | FAIL (DD) |
| prior-4 `cash_reserve` 10% | $129,184 | 40.0% | all 3 | FAIL (DD) |
| **prior-5 `cash_reserve` 20%** | $126,349 | **37.1%** | all 3 | **PASS** |
| prior-6 `swap_funding` | $149,218 | 49.0% | all 3 | FAIL (DD) |
| prior-7 `swap_funding`+10pp | $154,392 | 39.9% | all 3 | FAIL (DD) |
| prior-8 `no_reserve`+10pp | $189,134 | 39.5% | all 3 | FAIL (DD) |
| this-run A forward | $141,837 | 45.6% | all 3 | FAIL (DD) |
| this-run B forward | $154,392 | 39.9% | all 3 | FAIL (DD) |
| this-run C forward | $189,134 | 39.5% | all 3 | FAIL (DD) |
| this-run 6 `swap_funding` | $149,218 | 49.0% | all 3 | FAIL (DD) |
| this-run 7 `swap_funding`+10pp | $154,392 | 39.9% | all 3 | FAIL (DD) |
| this-run 7-inverted | $154,291 | 39.9% | all 3 | FAIL (DD) |
| **this-run 7-datecap** | $160,219 | **38.0%** | all 3 | **PASS** |

**Every single cell beats all three named benchmarks on absolute return.**
Not one fails on the return leg of the bar — the drawdown leg is what
separates PASS from FAIL throughout the entire grid, in both sweeps. **The
two cells that pass are the two with the lowest drawdowns in the whole
table, not the two with the highest returns** — `cash_reserve 20%`
(lowest-risk, lowest-return of the funding modes) and `7-datecap` (this
session's own drawdown-reducing correction to swap-funding's trim-cap bug).
**Cell C — the single highest-return cell in either sweep at $189,134 —
fails the bar on drawdown alone (39.5% vs. the 38.0% ceiling), by a margin
of only 1.5 percentage points.** Flagging this precisely because it is
close enough that a different (but equally defensible) choice of "median
baseline" for the drawdown ceiling could flip it.

## Flagged plainly

- **The prior sweep's headline swap-funding result was noise, not signal.**
  `sweep-funding-modes-out.md` reported cell 7 ($154,392) without the context
  that this number is statistically indistinguishable from an unmodified
  control's own random seed draw. That report's framing ("cell 7:
  best-diagnostics cell") remains defensible on the *diagnostics* (0%
  unfunded, 16/16 tickers) but not on the *return* — this wrap-up is the
  correction for the return side specifically.
- **Cell C (`no_reserve`+10pp) is the one configuration in this entire
  two-session sweep whose return advantage survives the ordering-probe
  test.** It is also the one configuration that fixes nothing structurally
  about cash starvation (funding diagnostics barely move — see
  `sweep-funding-modes-out.md`). Both of those things are true at once and
  neither cancels the other; the design session should not read "C's return
  is real" as "C is therefore the fix."
- **The inverted-gap-term test's premise (MSFT's selection is gap-term-driven)
  did not reproduce** in cell 7 — see 2b. Worth re-testing against cell 6
  (unlimited) specifically, where the original MSFT observation was made,
  before concluding the gap term doesn't matter at all.
- **No ambiguity required stopping on** in Step 2's implementation — the
  per-date cap (2c) was fully implementable from existing state, contrary
  to what the stop-gate anticipated might be needed.
- `.gitignore` was edited (see 0b) — the one change in this run whose blast
  radius extends beyond this specific measurement.

## What was deliberately not done

- No funding mode selected, no session-limit value chosen, no
  `minPositionDollar` picked — Step 2a reports the distribution, not a
  recommendation.
- No spec amended; §12 items untouched.
- Cadence/scope/veto sweep not started.
- Per-sale (vs. per-donor-aggregate) realized gain/loss split not built —
  flagged as a real gap in 2a, not silently approximated.
- Confirmed the guard's stop-gate condition ("if adding the guard makes any
  existing cell fail") did not trigger — no cell was found to already be
  degraded.

## Repo state left behind

- `sweep/db-corpus-baseline` at commit `2733c0c` (guard fix at `82a8053`
  underneath it). `git status` still shows pre-existing, unrelated dirt
  (`CLAUDE.md` modified; `server/scripts/*.js`, `testing/` untracked) —
  none of it touched by, or relevant to, this run.
- `analysis/simulator/simulator.py` — new signature guard (additive,
  verified non-breaking against the existing sweep).
- `analysis/session_limit_and_donor_probe.py` — new, this session's driver.
- `analysis/data/run_manifests/*.json` — 14 manifests (8 regenerated prior
  cells + 6 new this-run cells/configs), now committed per the `.gitignore`
  fix above.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 session_limit_and_donor_probe.py

# Inspect any manifest:
cat data/run_manifests/step1-configC-manifest.json | python3 -m json.tool

# Confirm the guard fires on the historical bug shape:
python3 -c "
import sys; sys.path.insert(0,'..')
from datetime import date
from pathlib import Path
from analysis.simulator.allocator_v3 import decide as decide_v3
from analysis.simulator.data import load_call_events, PriceLookup
from analysis.simulator.simulator import run_simulation
from trend_analyst import build_tier_function
from type_classifier import build_type_function
def broken(**kwargs): return decide_v3(**kwargs)
events = load_call_events(tickers=['AAPL'], end_date=date(2022,6,1))
prices = PriceLookup.from_cache()
tier_fn = build_tier_function(Path('data/price_cache.json'), Path('data/fundamentals_cache.json'))
run_simulation(start_date=date(2022,1,1), end_date=date(2022,6,1),
                taxable_cash=50000, tax_advantaged_cash=50000,
                universe_tickers=['AAPL'], prices=prices, events=events,
                decide_fn=broken, type_for_ticker=build_type_function(), tier_for_ticker=tier_fn)
"
```
