# Session limit as the proven axis — and swap-funding's first fair test

`wrap-ups/diagnose-session-limit-and-donor-rule-out.md` settled one thing and
invalidated its own test of another.

**Settled:** the 10pp session limit's outcome advantage is real. Config C's worst
draw ($171,919) beats config A's best ($154,398); the distributions do not
overlap. `ALLOCATOR_OPERATING_MODEL.md` §5's line calling the per-session change
limit "a secondary axis, not the fix" is wrong on outcomes and will be amended by
the design session.

**Invalidated:** Step 2c proved the swap-funding code that Step 1 tested was
**non-conformant with §5** — it applied the 25% donor trim cap per *event* rather
than per *session*, compounding across events sharing a date. The conformant
version scored $160,219 at 38.0% drawdown, above all seven draws of the version
that was probed. **Swap-funding has not yet had a fair test**, and the conformant
variant was never seeded — its drawdown sits exactly on the 38.0% bar off a
single draw.

Two defects were also found in code that has now produced published numbers twice:

- **Displacement gains are ticker-filtered, not sale-attributed.** The figures
  `-$32,679` (cell 6) and `-$24,950` (cell 7) sum realized gains for *any ticker
  that was ever a donor*, including ordinary Trim/Exit sales on those same
  tickers. `RealizedSale` (`analysis/simulator/accounts.py:59`) carries no reason
  field. §5's requirement to report displacement gains separately from ordinary
  Trim/Exit is **unmet**, and both published figures are misdescribed.
- **Manifests do not pin the code that produced the numbers.** All fourteen
  record `git_commit: 82a8053`; `session_limit_and_donor_probe.py` was not
  committed until `2733c0c`, afterwards. Reproducing from the commit the manifest
  names would not find the driver. Combined with `git_dirty: true` on every one,
  §10b is not satisfied.

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §4, §5, §10 and §10b before
starting. Decisions there are closed. Do not re-derive them.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on** throughout. Work on `sweep/db-corpus-baseline`.
Write findings to
`./wrap-ups/sweep-session-limit-and-conformant-swap-out.md`.

---

## Step 0 — reproducibility, met this time rather than argued around

§10b was tested once and answered with "the dirt is unrelated." That reasoning is
unverifiable at citation time, which is why the contract is written as an
absolute. Meet it.

**0a. Clean the tree first.** Commit or stash `CLAUDE.md`; commit, ignore, or
stash `server/scripts/*.js` and `testing/`. Then run.

**Hard stop-gate:** if `git_dirty` cannot be recorded as `false`, **stop and
report**. Do not proceed and flag it afterwards — that path has been taken once
already and it produced fourteen non-citable manifests.

**0b. Pin the driver, not its predecessor.** Commit this run's driver script
*before* generating manifests, and have the manifest writer assert that the
recorded `git_commit` is a commit in which the driver file exists. A manifest
naming a commit that predates the code it describes is worse than no manifest.

**0c. Fix the event-count label.** `corpus.event_count` currently records the
full pre-window load (195/196) while the previous session reported the in-window
count (147/148). Same field name, two different quantities, two wrap-ups that
contradict each other on the record. Record **both**: `loaded_event_count` and
`in_window_event_count`, and hash each separately.

**0d. Standing assertion, unchanged.** `no_reserve`, dedup on, no limit, must
reproduce **$141,837**. If it moves, stop and report.

## Step 1 — fix displacement attribution before measuring anything

Add a `reason` field to `RealizedSale` and thread it from `_build_sell_trades`
through to the realized-sale record, so a sale tagged
`swap-funding-displacement` is identifiable as such. This touches shared
accounting code — make it additive with a default of `None` so nothing else
changes behavior.

Then report, for the conformant swap-funding cell:

- displacement realized gain/loss, **sale-attributed**, not ticker-filtered
- that figure split by donor verdict at time of draw: `Hold` (sells the analyst
  never asked for) versus `Trim`/`Exit` (accelerations of sells already wanted)
- ordinary Trim/Exit realized gains reported separately, per §5

**State plainly in the wrap-up that the previously published `-$32,679` and
`-$24,950` are superseded, and by how much.** A corrected number that quietly
replaces a wrong one is how the `$287k` problem started.

**Stop-gate:** if adding `reason` changes any existing cell's final value, stop —
the change was not additive and something else depends on that path.

## Step 2 — the session-limit sweep

The limit is now the proven axis, so sweep it properly instead of testing one
value. Two funding modes × four limit values:

| | limit off | 10pp | 15pp | 20pp |
|---|---|---|---|---|
| `no_reserve` | A | C | — | — |
| `swap_funding` + **per-date cap** | — | D | — | — |

Fill the row: eight configurations total. **Every swap-funding run in this and
every future sweep uses the per-date trim cap** — the per-event version is
non-conformant with §5 and is retired, not an option.

Run each configuration at seven draws: forward, reversed same-day order, and
seeds 1–5. Fifty-six runs, all free. Report per configuration: every individual
final value, min / median / max, spread as a percentage of median, max drawdown,
and the full funding diagnostics (days below 1% cash, Adds fully funded /
partial / unfunded, cumulative shortfall, distinct tickers held, displacement
count).

**Pre-declared decision rules — agreed before results are seen, per §10:**

> **Rule 1 (does a configuration beat the control):** a configuration's return
> advantage over A counts as real only if its median across draws exceeds A's
> maximum across draws. This is the rule already applied to B and C; it does not
> change.
>
> **Rule 2 (separating two configurations that both pass Rule 1):** two
> configurations are separable on return only if their seven-draw ranges do not
> overlap. If the ranges overlap, they are **tied on return**, and the wrap-up
> must say so rather than ranking them by median. Ties are then reported against
> the secondary axes — spread, drawdown, and funding diagnostics — without a
> winner being named.
>
> **Rule 3 (the shape of the limit surface):** per §10 rule 2, the finding is the
> shape, not the argmax. If final value across `off / 10 / 15 / 20pp` is smooth
> and monotone-ish within a mode, the surface is usable and the crossing point is
> reportable. **If it is jagged with an isolated peak at one oddly specific
> value, the experiment failed at that axis and nothing is spec'd from it** — say
> so explicitly rather than reporting the peak.

Do not soften these after seeing the numbers, and do not substitute an
alternative rule.

**Also report** the donor position-size distribution for every swap-funding
configuration — share of draws leaving the donor below 2%, 1% and 0.5% of
portfolio. The per-date cap should reduce the grinding the previous run found
(≈7 in 10 draws left the donor below 1%). The design session still needs this
distribution to choose a `minPositionDollar`. **Report it, do not choose one.**

## Step 3 — re-derive the drawdown bar once, and pin it

The 38.0% ceiling has been inherited across three sessions without being
recomputed. Compute the **max drawdown of each of the four baselines** (SPY, QQQ,
TMFC, equal-weight-of-universe) on the exact clean window from the frozen caches,
report all four, and show the median + 5pp arithmetic explicitly. Record the
result in a manifest so it is pinned rather than remembered.

**Stop-gate — read this one carefully.** If the re-derived ceiling differs from
38.0%, **report both figures and stop there.** Do not re-score any cell against a
newly derived bar, and do not describe a cell as passing under it. A prior
session already stopped a run over a fabricated threshold; a threshold that
moves after results are visible is the same failure wearing better clothes. The
design session decides which figure stands.

Score every configuration in this run against the **existing 38.0%** bar and the
four benchmarks, Pass / Soft pass / Fail per `BACKTEST_SIMULATOR.md`.

## Step 4 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a session-limit value, do not pick a `minPositionDollar`, do not amend any
spec, do not adopt a re-derived drawdown bar, do not resolve §12 items, do not
start the cadence / scope / veto sweep.

Lead with:

> **Conformant swap-funding vs. control: [passes / fails] Rule 1 —
> median $X vs A's max $Y. Against `no_reserve` at the same limit: [separable /
> tied] under Rule 2. Session-limit surface: [smooth / jagged] under Rule 3;
> best-scoring value [X]pp. Corrected displacement gain: $Z, of which $W on
> `Hold` donors. Cells passing the 38.0% bar: [list, or none].**

Then: the fifty-six-run distribution table, the limit surface per mode, the
corrected displacement accounting with the superseded figures named, the donor
size distribution, the re-derived drawdown baselines, and the full scoring.

Flag plainly: any rule that gives an uncomfortable answer, anything contradicting
§5's measurements, any ambiguity you stopped on, and any place where a previously
published number turns out to be wrong.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Alphabetical same-day ordering stays the default except where a draw varies it.
  The ordering *rule* is still a later thread.
- Report wall-clock runtime for the fifty-six runs, so the next sweep can be
  sized.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
