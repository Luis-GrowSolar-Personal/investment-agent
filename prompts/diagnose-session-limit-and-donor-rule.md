# Session limit vs. funding mode — which one actually did the work

`wrap-ups/sweep-funding-modes-out.md` ran the eight-cell funding grid. The design
session's reading of it:

**The grid separated *outcome* from *mechanism*, and the wrap-up's conclusion
does not survive its own Step 3.** The retrospective ordering probe measured a
spread of **$117,455–$154,443** on the unchanged control. Cell 7
(`swap_funding` + 10pp, $154,392) and cell 6 (`swap_funding`, $149,218) both sit
*inside* that band — seed 3 alone returned $154,443. On this corpus, return
cannot distinguish a funding mode from a re-rolled tie-break. Only cell 8
(`no_reserve` + 10pp, $189,134) lands outside it, and cell 8 is the cell where
nothing structural was fixed.

Meanwhile the diagnostics point the other way: swap-funding is the only mode that
takes entirely-unfunded Adds to zero and holds all 16 names.

So the open question is narrow and answerable: **is the 10pp session limit's
outcome advantage real, or is it arrival-order luck measured once?**

**Nothing is being selected in this run.** Funding mode remains open. Read
`docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §4, §5, §10 and §10b before
starting — the ranking rule, the swap-funding spec, the interpretation rules and
the manifest contract are all authoritative and closed. Do not re-derive them.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12, ALL16), `sweep/db-corpus-baseline`, `decide_v3`,
frozen-JSON `type_for_ticker`, unchanged caches. Write findings to
`./wrap-ups/diagnose-session-limit-and-donor-rule-out.md`.

---

## Step 0 — three things before any cell runs

**0a. Make the signature bug structural, not remembered.** The `**kwargs`
wrapper bug has now cost two sessions and produced the identical wrong number
(`$114,263`) twice, caught both times only by the `$141,837` assertion. Add a
hard guard in `analysis/simulator/simulator.py`: where it inspects
`decide_fn`, **raise** if the resolved signature does not accept `tier`,
`is_first_call` and `driver_count` explicitly. A silently degraded run must
become an impossible run.

**Stop-gate:** if adding the guard makes any existing cell fail, that cell was
already degraded. Report which, and stop — do not relax the guard.

**0b. Manifests, retro-fitted.** The eight cells from the previous run have no
`<run_id>-manifest.json`, so under §10b none of them is citable. Emit one per
cell for **every** cell in this run, and regenerate them for the previous
eight by re-running that grid under the guard from 0a. Field list is in §10b.

The working tree is currently dirty (`CLAUDE.md` modified, untracked
`server/scripts/` and `testing/`). Commit or stash before running so
`git_dirty` records `false`; if you cannot, record `true` and say plainly in
the wrap-up that the numbers are not citable.

**0c. Keep the standing assertion.** The `no_reserve` control, dedup off, no
limit, must still reproduce **$141,837** exactly. If it moves, stop and report.

## Step 1 — the decisive measurement: ordering probe under the session limit

The previous probe ran on cell 1 only — no session limit. That band cannot be
used to judge cells that *have* a limit. Re-run the probe inside each candidate
configuration.

`run_cell()` already takes `reverse_order` and `seed`. Three configurations:

| Config | funding_mode | session limit |
|---|---|---|
| **A** — control | `no_reserve` | off |
| **B** — cell 7 | `swap_funding` | 10pp |
| **C** — cell 8 | `no_reserve` | 10pp |

For each: forward (as-loaded), reversed same-day order, and **seeds 1–5**
(the previous run used three; five is the minimum here). Twenty-one runs, all
free. Dedup **on** for all three, so dedup is not a confound.

Report per configuration: every individual final value, plus min / median / max.

**Pre-declared decision rule — agreed before results are seen, per §10:**

> The 10pp session limit's outcome advantage counts as **real** only if
> configuration C's *median across seeds* exceeds configuration A's *maximum
> across seeds*. If C's distribution overlaps A's, the $189,134 was a draw from
> the arrival-order lottery and the limit is not an outcome fix.

Apply the identical test to B against A. Report both verdicts mechanically
against this rule. **Do not soften it if the answer is inconvenient, and do not
propose an alternative rule after seeing the numbers.**

Also report, for each configuration, the spread as a percentage of its own
median. §10 rule 2's fragility logic applies: a configuration whose result swings
widely by tie-break seed is fragile regardless of its mean.

## Step 2 — the donor rule: two questions the previous run left open

The wrap-up flagged that §4's ranking was written for candidates and its
extension to donors is the CLI's own construction. The design session has **not**
chosen between readings. Price both.

**2a. Decompose the displacements.** Extend `displacement_log` to record, per
sale: the donor's latest `final_action` at the time of the draw, the donor's
position value as a % of portfolio before and after, and its gap-to-target.
Then report, for cells 6 and 7:

- displacements on donors whose latest verdict was `Hold` — sells the analyst
  **never asked for** — versus `Trim`/`Exit` — accelerations of sells already
  wanted. This split determines whether swap-funding is a new allocation
  mechanism or a timing shim on the analyst's existing exits.
- realized gain/loss split the same way.
- how often a donor was drawn below 2%, 1% and 0.5% of portfolio value.
  `minPositionDollar` has no value in this codebase to port; the design session
  needs the distribution to choose one. **Report it, do not invent a floor.**

**2b. Donor ranking, inverted gap term.** Current construction ranks a donor
*near or above its own target* as a better donor, which is why MSFT is the
largest contributor at 15 draws / $48,017. That preferentially harvests the
positions §3 relies on being allowed to drift up.

Run one additional cell — `swap_funding` + 10pp, dedup on — with the
`gap_to_target` term **inverted for donors only** (furthest below its own target
becomes the preferred donor; confidence and recency terms unchanged). Report the
same diagnostics and the same donor-aggregate table as cell 7, side by side.

**2c. Trim quantum is specified per session, implemented per event.** §5 says
"at most 25% of the donor **per session**." `make_funding_decide_fn` applies
25% per `decide()` call, and multiple events land on the same date — 426
displacement sells in 894 trading days. Add a per-date cap so a donor cannot be
drawn on for more than 25% of its start-of-day value across all events that
date, and re-run cell 7 with it. Report the displacement count and final value
against the uncapped version.

**Stop-gate:** if enforcing the per-date cap requires state the harness does not
expose, stop and report what is missing rather than approximating it.

## Step 3 — score every cell against the pre-declared bar

The previous run reported eight cells with no benchmark column and no pass/fail
call. `BACKTEST_SIMULATOR.md`'s bar is closed and unchanged:

- **Pass:** beats SPY **and** QQQ **and** TMFC on absolute return; max drawdown
  no worse than median baseline + 5pp (**38.0%** on this window).
- **Soft pass:** beats 2 of 3, within 2pp on the third, drawdown acceptable.
- **Fail:** anything else.

Add **equal-weight-of-universe** as the fourth baseline.

Score all eight previous cells and every cell in this run. Report the four
benchmark final values for the clean window explicitly, once, so the bar is
auditable.

**Stop-gate:** if the benchmark series cannot be computed on the exact clean
window from the frozen caches, stop and report. Do not approximate a benchmark
or reuse a figure from a different window.

## Step 4 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a session-limit value, do not pick a `minPositionDollar`, do not amend any
spec, do not resolve §12 items, do not start the cadence / scope / veto sweep.

Lead with:

> **Session limit verdict: [real / inside the noise band] — config C median
> $X vs config A max $Y, against the pre-declared rule. Swap-funding verdict:
> [same]. Donor decomposition: N of M displacements were on `Hold` donors.
> Cells passing the pre-declared bar: [list, or none].**

Then: the twenty-one-run distribution table, the donor decomposition, the
inverted-ranking comparison, the per-date-cap comparison, and the full
pass/fail scoring of all cells.

Flag plainly: any cell whose manifest records `git_dirty: true`, any place the
pre-declared rule gives an uncomfortable answer, anything that contradicts §5's
measurements, and any ambiguity you had to stop on.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Alphabetical same-day ordering stays the default everywhere except where this
  prompt explicitly varies it. The ordering *rule* is still the next thread, not
  this one.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
