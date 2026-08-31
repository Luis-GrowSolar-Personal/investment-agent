# Verify the tight-limit result, then bracket it

`wrap-ups/sweep-limit-axis-dense-out.md` was a clean run — 18 citable manifests,
`git_dirty: false` throughout, drivers present in the commits they name, the four
stale manifests renamed rather than deleted, standing assertion held. The
design session verified all of that independently.

**Correction to the record, and it is the design session's error, not the CLI's.**
Rule 3a as written contained two clauses that contradict each other: it allowed
"at most **one violation** whose magnitude is smaller than the smaller adjacent
draw range," then declared jagged on "two or more **material sign changes**." A
single out-of-place uptick *is* one violation but mechanically produces *two*
sign changes, so the clauses cannot both hold. The previous run applied the
second clause strictly and returned JAGGED for both axes, while flagging that the
mechanical verdict disagreed with the visual read — exactly the right behavior.

Applying the tolerance clause instead:

| Axis | uptick | smaller adjacent draw range | verdict |
|---|---|---|---|
| `no_reserve` 7.5→10pp | +$2,543 | $12,449 | immaterial |
| `swap_funding` 15→17.5pp | +$2,951 | $22,852 | immaterial |

**Both axes are unimodal.** Plateaus under Rule 3b: `no_reserve` **{2.5, 5, 10}pp**
(non-contiguous only because 10pp's range is wide enough to reach the peak's —
its median is $5,600 below), `swap_funding` **{2.5}pp**. Rule 3 is rewritten as a
single clause below so this cannot recur a third time.

**Two things follow, and they are why this run exists.**

**1. The optimum is not bracketed.** 2.5pp is the peak in both modes *and* the
tightest value sampled. A limit tight enough must eventually starve deployment,
so an interior optimum exists — this sweep found the boundary of its own grid,
not the optimum. Same error as the previous sweep, moved to the other end of the
axis.

**2. The 2.5pp cell is now load-bearing and has never been checked.** It reports
an 18.8% max drawdown for `no_reserve` against SPY's own 25.36%, while returning
$185,180 to SPY's $113,980 — beating the index on both axes at once. Five
configurations now rest on that region. The near-zero draw spread (0.4%) has a
coherent explanation — with no name able to exhaust the account on one call,
contention nearly stops and the seed-varied tie-break almost never fires, which
is §5's "order is the allocator" running backwards — and the design session has
already confirmed the limit is applied per position per event, conformant with
§5, not as a global throttle. **But a number this good, in a thread where two
too-clean results have turned out to be defects, gets verified before anything
else is built on it.**

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §4, §5, §9, §10 and §10b
before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, conformant per-date trim cap on every
swap-funding run. Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/verify-and-bracket-tight-limit-out.md`.

---

## Step 0 — carry forward, unchanged

The reproducibility machinery works. Reuse it exactly: clean tree before running
with a hard stop if `git_dirty` cannot be `false`, driver committed before any
manifest is written, import-time assertions on both, `loaded_` and
`in_window_event_count` recorded separately, standing **$141,837** assertion on
the `no_reserve` control.

## Step 1 — verify the 2.5pp cell BEFORE sweeping anything

This step runs first and gates the rest. **If any check below fails, stop and
report — do not proceed to Step 2.** A bracketing sweep around a number that
turns out to be an artifact is wasted work, and running the measurement before
the conformance check is the exact sequencing error this thread already made once
with swap-funding.

Run every check on `no_reserve` at 2.5pp, forward draw, and repeat the invariant
checks on `swap_funding` at 2.5pp.

**1a. Independent drawdown recomputation.** Recompute max drawdown directly from
the `DailySnapshot` equity series with a second, separately written function —
do not reuse `compute_summary`'s path. Assert the two agree to within $1 /
0.01pp. A drawdown of 18.8% against a control's 45.3% is the single most
surprising number in the grid; it needs two independent derivations.

**1b. Invariant checks, per §9.** Report pass/fail on each, with the observed
extreme value:

- **#2** — no position's target ever exceeds its tier cap. Report the maximum
  position weight observed at any point in the run, by ticker.
- **#9** — no session moves a single position by more than the limit. Report the
  **maximum single-session position change actually observed**, in percentage
  points. At a 2.5pp setting this must be ≤ 2.5pp plus rounding. If it exceeds
  that, the limit is not doing what the grid assumes.
- **#5** — no trade set is sized against pre-trade state and executed after
  another. Report any `InsufficientCash` catches or `skipped_events` entries.

**1c. Where does the drawdown reduction come from?** The concern is that a tight
limit lowers drawdown mainly by leaving the portfolio in cash — beta reduction,
not skill, the same critique that applies to `cash_reserve 20%`. Report for the
2.5pp run and the unmodified control side by side:

- average cash as a % of portfolio across the window, and the median
- invested share at the drawdown trough specifically, and what the portfolio
  held at that date
- terminal portfolio composition: every position and its weight

**1d. What is actually binding?** For every Add-shaped decision, classify the
binding constraint as `target gap`, `cash available`, or `session limit`, and
report the counts. At 2.5pp the session limit should dominate; at the control,
cash should. If neither is true, the mental model behind this whole sweep is
wrong.

**1e. Sanity floor.** Confirm the 2.5pp run still beats SPY, QQQ, TMFC and
equal-weight on return, and report its own final value alongside all four —
recomputed in this run, not carried forward.

## Step 2 — bracket the low end

Only if Step 1 passes. Ten limit values × two funding modes × fifteen draws
(forward, reversed, seeds 1–13) = 300 runs. The previous 270-run grid took 35.8
seconds; report actual wall-clock.

| | values |
|---|---|
| **Session limit** | off, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 10 pp |
| **Funding mode** | `no_reserve`; `swap_funding` (conformant per-date cap only) |

`off` and 10pp are retained as anchors so this grid is directly comparable with
the previous one — their medians should reproduce the previous run's to the
dollar. **Report whether they do; a mismatch means something changed and the
comparison is void.**

Record, per configuration: final value min / median / max and spread as a % of
median; **max drawdown min / median / max across all fifteen draws**; and the
forward-draw funding diagnostics (days below 1% cash, Adds fully funded /
partial / unfunded, cumulative shortfall, distinct tickers held, displacement
count, and for swap-funding the donor size distribution below 2% / 1% / 0.5%).

## Step 3 — the rules

**Rule 1 (beats the control), Rule 2 (separability by range overlap, applied to
both return and drawdown), and Rule 4 (median drawdown across draws against the
standing 38.0% bar, plus share-of-draws clearing, with "robustly passing"
requiring ≥ 2/3) are unchanged.** Report Rule 1 margins in dollars and as a
percentage.

The **39.12%** ceiling is still not adopted. Do not score against it. Continue
reporting, as a labelled diagnostic only, the count of draws each configuration
puts below it — on the previous grid that difference was inert everywhere except
`swap_funding` at 7.5pp and 10pp, and knowing where it bites is cheap.

**Rule 3 — REWRITTEN AS A SINGLE CLAUSE. This supersedes all prior versions.**

Order configurations by limit value and take each one's median final value.
Compute first differences. Classify each difference as **material** if its
absolute value is greater than or equal to the smaller of the two adjacent
configurations' own fifteen-draw ranges, and **immaterial** otherwise. Discard
immaterial differences — they are noise, not shape. Then:

- the surface is **unimodal and usable** if the remaining material differences
  read `+…+ −…−`, either side possibly empty;
- **jagged and unusable** otherwise.

There is no second test and no counting of violations. Report the material /
immaterial classification of every difference, with both magnitudes, so the
classification is auditable rather than asserted.

**Rule 3b — plateau, with a boundary condition.** If the surface is unimodal,
report the plateau: every limit value whose fifteen-draw range overlaps the peak
configuration's range. Never report a single best value.

**New:** if the peak configuration sits at either **end** of the sampled range,
the optimum is **not bracketed**. Say so explicitly, report the plateau as open
at that end, and state that no limit value can be recommended until the axis is
bracketed on both sides. This is the condition the previous sweep hit and did not
have language for.

Do not soften any rule after seeing results, and do not substitute an
alternative.

## Step 4 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a limit value, do not pick a `minPositionDollar`, do not adopt the 39.12%
ceiling, do not amend any spec, do not resolve §12 items, do not start the
cadence / scope / veto sweep.

Lead with:

> **Step 1 verification: [passed / failed on X]. Independent drawdown
> recomputation agrees / disagrees. Max single-session position change observed:
> [X]pp against a [Y]pp limit. Average cash: [X]% at 2.5pp vs [Y]% at control.
> Limit surface: [unimodal / jagged], material differences [..]. Peak [X]pp,
> plateau [set]; optimum [bracketed / NOT bracketed]. Robustly passing the 38.0%
> bar: [list].**

Then: the Step 1 verification detail, the anchor-reproduction check, the full
20-configuration table with return and drawdown distributions, the material/
immaterial difference classification, the plateau derivation, the funding
diagnostics, and the Rule 4 scoring with pass-share.

Flag plainly: any invariant that fails, any anchor that does not reproduce, any
rule that gives an uncomfortable answer, any configuration whose median and
forward draw disagree about passing, and any previously published number that
turns out to be wrong.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop. `testing/` stays gitignored.
- Report wall-clock runtime for the 300 runs.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
