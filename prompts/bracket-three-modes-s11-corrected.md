# Three modes on equal footing — bracket the limit axis

`wrap-ups/bracket-tight-limit-corrected-gates-out.md` stopped on Gate 4. **That
was a fourth drafting error by the design session, and it is the one worth naming
as a principle:** Gate 4 tested §9 invariant #5, which **§11 documents as a known,
unfixed defect in the validated code path**, with an explicit handling policy —
*baseline runs as-is for comparability; one bug-fixed cell quantifies the impact;
fix after the baseline is banked.* The previous prompt carved out an exception
for §11's *first* defect at Gate 2 and not its *second* at Gate 4, so the gate
could never pass. The CLI resolved the ambiguity by reading the prompt literally
rather than guessing, which was correct.

**Standing principle from here on: no gate may test a condition that §11
documents as a known unfixed defect.** Known defects are measured and reported,
never used to stop a run.

**The finding that matters more than the gate.** The two funding modes in this
harness are not comparable, and have not been for three sessions:

- `swap_funding` always **rebuilds its buy leg against live cash**
  (`portfolio.accounts[acct].cash + raised_by_account[acct]`).
- `no_reserve` passes `decide_v3`'s **raw concatenated trades** through whenever
  they already fit under the session limit.

So `swap_funding` has been running with §11's second defect effectively fixed and
`no_reserve` has not. At `off`, `no_reserve` loses 6 trades to it and
`swap_funding` loses 0. **Part of every mode comparison in this thread is a
bugfix, not a funding mode.** The CLI found this itself and warned against
over-reading its own clean Gate 4 record — correctly.

**Three further findings from that run, all worth keeping:**

- **The reference result contains six silently skipped trades.** `$141,837` — the
  number every run is asserted against — is missing MSFT 2022-01-25, TSLA 01-26,
  AAPL 01-27, AMD and GOOGL 02-01, NVDA 02-16. All six land inside the six weeks
  §5 shows decided the entire book. At 10pp the three skipped are AVGO and ENVX
  (2022-03-03) and ORCL (03-10) — AVGO being the name that went ~8x. §11's second
  defect is concentrated exactly where it costs the most.
- **A tight limit incidentally eliminates the defect.** `no_reserve` at 0.5pp
  produced zero skipped events: throttling each buy to 0.5% of portfolio means
  the starter-plus-Add pair no longer overdraws. Tight-limit cells are *cleaner*
  than the baseline, not only better-performing.
- **The uncapped baseline moved a single position by 58.00pp of portfolio in one
  event** (Gate 3, `off`).

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §3, §4, §5, §9, §10, §10b
and §11 before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, conformant per-date trim cap on every
swap-funding run. Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/bracket-three-modes-s11-corrected-out.md`.

---

## Step 0 — carry forward, unchanged

Clean tree with a hard stop if `git_dirty` cannot be `false`; driver committed
before any manifest; import-time assertions on both; `loaded_` and
`in_window_event_count` recorded separately.

## Step 1 — the five gates, with Gate 4 corrected

Run on all three modes at `off`, 0.5pp and 10pp. **A failure in any of these five
stops the run. Nothing else does. A diagnostic that contradicts an expectation
stated in this prompt is a finding to report, never a reason to stop.**

1. **Standing assertion** — `no_reserve` (raw) control reproduces **$141,837**.
2. **Invariant #2, at decision time** — every `target_pct` ≤ that ticker's
   `cap_pct` at the moment of decision. Report `max(target_pct − cap_pct)`; must
   be ≤ 0. §11's first defect (starter + Add landing over cap in the *realized*
   portfolio) is a known defect and does not stop the run.
3. **Invariant #9** — max single-session position change ≤ the configured limit
   plus rounding. Not applicable where no limit is configured.
4. **Invariant #5 — CONDITIONAL.** Stop **only** on a skipped event that is
   **not** attributable to §11's second defect. Classify every `skipped_events`
   entry as `known_s11_concatenation` or `other`; report the counts, dates and
   tickers per configuration as a diagnostic. **A skipped event that cannot be
   classified either way is itself a stop** — an unexplained one is exactly what
   this gate is for.
5. **Independent drawdown recomputation** — the separately written function
   agrees with `compute_summary` to within 0.01pp.

## Step 2 — three modes, not two

| Mode | Behavior |
|---|---|
| **`no_reserve_raw`** | today's baseline: `decide_v3`'s trades passed through unmodified when they fit under the limit. Carries §11 defect #2. **This is the comparability anchor for the existing corpus.** |
| **`no_reserve_s11fixed`** | identical, except the buy leg is **rebuilt against live cash**, using the *same code path* `swap_funding` already uses. Nothing else changes. |
| **`swap_funding`** | conformant per-date trim cap, buy leg already rebuilt against live cash. |

The middle mode is §11's own prescribed "one bug-fixed cell at baseline settings
to quantify the impact," generalized across the axis. **Use the same rebuild
function for `no_reserve_s11fixed` as for `swap_funding`** — if the two rebuild
differently, the comparison reintroduces the confound this step exists to remove.
State explicitly in the wrap-up that they share the code path.

## Step 3 — the grid

Ten limit values × three modes × fifteen draws (forward, reversed, seeds 1–13) =
**450 runs**. The 270-run grid took 35.8 seconds; report actual wall-clock.

| | values |
|---|---|
| **Session limit** | off, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 10 pp |

**Anchor check.** `no_reserve_raw` at `off` and 10pp must reproduce the previous
grid's medians **exactly** — forward draws have been shown to reproduce to the
cent, so allow no tolerance. Report whether they do. A mismatch does **not** stop
the run: report it and continue, flagging every conclusion it affects.

Record per configuration: final value min / median / max and spread as a % of
median; **max drawdown min / median / max across all fifteen draws**; and
forward-draw funding diagnostics (days below 1% cash, Adds fully funded /
partial / unfunded, cumulative shortfall, distinct tickers held, displacement
count, skipped-event count by classification, and for swap-funding the donor size
distribution below 2% / 1% / 0.5%).

## Step 4 — what §11 defect #2 actually costs

For each limit value, compare `no_reserve_raw` against `no_reserve_s11fixed`:
difference in median final value (dollars and %), difference in median drawdown,
and the skipped-event count that disappears. Report the surface, not one point.

Two questions this answers, both open since the defect was documented:

- **How much of the historical result is the defect?** At `off` the raw mode
  loses six trades in the six weeks that set the whole book. Quantify it.
- **Does the defect's cost shrink as the limit tightens?** The 0.5pp cell already
  showed zero skipped events, so the two modes should converge somewhere on the
  axis. Report where.

## Step 5 — censuses (diagnostics, never gates)

**Cap drift**, every configuration, forward draw: per ticker, maximum realized
weight (% of `portfolio.total_value`, the denominator `_decide_add` uses), its
cap, days above cap, maximum excess in pp. Per configuration: tickers exceeding
cap, total ticker-days above cap. Across the grid: does drift-above-cap increase
with `swap_funding` and change with the limit? Partial data from the last run
showed MSFT at 62.3% against a 50% cap under `swap_funding`/`off` and **zero**
drift under `no_reserve` at 0.5pp. Report the largest excess anywhere and whether
anything approaches the 25% profit-take threshold.

**Binding constraint**, every configuration, forward draw: counts of `target
gap` / `cash available` / `session limit`. The last run found `swap_funding` at
0.5pp is 98/98 limit-bound while `no_reserve` at 0.5pp is still cash-bound on 22
of 98. Report the whole surface and identify where, if anywhere,
`no_reserve` becomes limit-dominant.

**Report only.** No cap-restoration rule, no spec amendment.

## Step 6 — the rules

**Rule 1 — control is `no_reserve_raw` at `off`**, for continuity with every
prior session's verdicts. A configuration's advantage is real only if its median
across draws exceeds that control's maximum across draws. Report margins in
dollars and as a percentage.

**Additionally**, report each configuration's margin against
**`no_reserve_s11fixed` at `off`** as a clearly labelled secondary. If fixing the
defect raises the control, some previously "REAL" verdicts may narrow or vanish —
that is a legitimate outcome and must be reported as such, not smoothed over.

**Rule 2 — separability** by non-overlapping fifteen-draw ranges, on **both**
return and drawdown. With three modes, run the comparison pairwise between each
mode's best configuration. Overlapping ranges mean **tied**, reported as tied,
never ranked by median.

**Rule 3 — single clause.** Per mode, order by limit value, take medians, compute
first differences. A difference is **material** if its absolute value is ≥ the
smaller of the two adjacent configurations' fifteen-draw ranges, **immaterial**
otherwise. Discard immaterial differences. The surface is **unimodal and usable**
if the remaining material differences read `+…+ −…−`, either side possibly empty;
**jagged and unusable** otherwise. No second test, no violation counting. Report
the classification of every difference with both magnitudes.

**Rule 3b — plateau with boundary condition.** Report every limit value whose
range overlaps the peak's. Never a single best value. **If the peak sits at
either end of the sampled range, the optimum is not bracketed** — say so, report
the plateau as open at that end, and state that no limit value can be recommended
until the axis is bracketed on both sides.

**Rule 4 — drawdown on the distribution.** Score against the standing **38.0%**
bar using **median** max drawdown across fifteen draws, plus share-of-draws
clearing it; "robustly passing" requires ≥ 2/3. The **39.12%** ceiling is not
adopted — do not score against it; report draws-below-39.12% as a labelled
diagnostic only.

**Follow the peak.** For the highest-median configuration in each mode, report
invested share and full holdings at its drawdown trough, plus terminal
composition — the cash-drag question has to be re-answered wherever the peak
lands.

## Step 7 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a limit value, do not pick a `minPositionDollar`, do not adopt the 39.12%
ceiling, do not add a cap-restoration rule, do not fix §11 in the production path,
do not amend any spec, do not resolve §12 items, do not start the cadence /
scope / veto sweep.

Lead with:

> **Gates: [all five passed / failed on X]. Anchors reproduce: [yes / no].
> §11 defect #2 costs [$X] ([Y]%) at `off`, converging to zero at [Z]pp.
> Limit surface per mode: [unimodal / jagged]. Peak [mode] at [X]pp, plateau
> [set], optimum [bracketed / NOT bracketed]. Robustly passing 38.0%: [list].
> Best of each mode, pairwise: [separable / tied] on return, [separable / tied]
> on drawdown. Cap drift: largest excess [X]pp on [ticker] at [config].**

Then: gate results with the skipped-event classification, the anchor check, the
full 30-configuration table, the §11 cost surface, the material/immaterial
classification and plateau derivation per mode, the peak trough analyses, the cap
drift and binding-constraint censuses, and Rule 4 scoring with pass-share.

Flag plainly: any gate that fails, any anchor that does not reproduce, any rule
that gives an uncomfortable answer, any prior verdict that narrows or vanishes
once measured against the s11-fixed control, and any previously published number
that turns out to be wrong.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop. `testing/` stays gitignored.
- Report wall-clock runtime for the 450 runs.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
