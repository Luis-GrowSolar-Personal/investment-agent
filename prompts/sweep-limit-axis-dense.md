# The limit axis, densely — and drawdown measured on every draw

`wrap-ups/sweep-session-limit-and-conformant-swap-out.md` was the cleanest run of
this thread. Step 0's hard gate was met for real — all nine manifests verified
independently as `git_dirty: false` with each `driver_file` present in the commit
it names. `RealizedSale.reason` is real and threaded, so the corrected
**-$19,924** is sale-attributed rather than the old ticker-filtered figure.

Three things it settled, and two it exposed.

**Settled:** a session limit helps — config C beat the unmodified control on every
draw, ranges non-overlapping. Swap-funding does **not** beat `no_reserve` on
return at a matched 10pp limit — Rule 2, ranges disjoint, `no_reserve` wins
outright. And the inherited **38.0%** drawdown ceiling is a three-benchmark
artifact: the median max-drawdown of SPY/QQQ/TMFC alone is 32.99%, +5pp = 37.99%.
With equal-weight included as §10 requires (42.76%), the median is 34.12% and the
ceiling is **39.12%**. Confirmed arithmetically by the design session.

**Exposed, and both are the design session's errors to fix:**

**1. Rule 3 was mis-specified, by me.** I imported §10 rule 2's "smooth and
monotone-ish" language, which was written for the *cadence* axis where monotone
with diminishing returns is the right prior. On a **limit** axis, theory predicts
an *interior* optimum — no limit means the reporting calendar consumes the book
in six weeks; too large a limit is the same thing; too small and the portfolio
cannot build into its compounders. The observed `no_reserve` medians
(off $138,070 → 10pp $179,666 → 15pp $157,403 → 20pp $139,959) are a clean
inverted-U, not a jagged surface. **The previous run applied my rule correctly;
the rule was wrong for this axis.** Rule 3 is replaced below, before any new
results exist.

The previous run's *conclusion* nonetheless stands and is not being reopened:
**10pp is not established as the right value.** Four points, with a large gap
between "off" and 10pp and nothing below 10 or between 10 and 15, cannot locate a
peak. The fix is to sample the axis densely, not to discard it.

**2. Pass/fail was rendered on a single draw.** `D` passed by landing on exactly
38.0% against a 38.0% ceiling, on one arbitrary draw out of seven, in a
configuration whose returns swing 12%. Its other six draws' drawdowns were never
computed. **Drawdown must be measured on every draw**, or the bar is being
applied to a sample of one.

The full 56-run grid took **9.2 seconds**. Dense sampling is free; size the grid
accordingly.

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §4, §5, §10 and §10b before
starting. Decisions there are closed. Do not re-derive them.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, conformant per-date trim cap on every
swap-funding run. Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/sweep-limit-axis-dense-out.md`.

---

## Step 0 — carry forward, unchanged

The reproducibility machinery from last run works. Reuse it exactly: clean tree
before running (hard stop if `git_dirty` cannot be `false`), driver committed
before any manifest is written, import-time assertions on both, `loaded_` and
`in_window_event_count` recorded separately, and the standing **$141,837**
assertion on the `no_reserve` control.

**One housekeeping item.** Four manifests from two sessions ago —
`step2-cell6`, `step2-cell7`, `step2-cell7-datecap`, `step2-cell7-inverted` —
carry `git_dirty: true` with drivers absent from the commits they name. They are
not citable and they share the `step2-` prefix with last run's citable ones, so
the verification loop published in the last wrap-up flags them. Rename them to a
`noncitable-` prefix so they cannot be mistaken for valid pins. Do not delete
them.

## Step 1 — the dense grid

Nine limit values × two funding modes × fifteen draws.

| | values |
|---|---|
| **Session limit** | off, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20 pp |
| **Funding mode** | `no_reserve`; `swap_funding` (conformant per-date cap only) |
| **Draws** | forward, reversed, seeds 1–13 |

270 runs. At the last run's measured rate that is well under two minutes; report
actual wall-clock.

**Record max drawdown on every single draw**, not only the forward one. This is
the central change in this prompt. For each configuration report, across its
fifteen draws: final value min / median / max and spread as a % of median, **and
max drawdown min / median / max**, plus the full funding diagnostics on the
forward draw as before (days below 1% cash, Adds funded / partial / unfunded,
cumulative shortfall, distinct tickers held, displacement count, and for
swap-funding the donor position-size distribution below 2% / 1% / 0.5%).

## Step 2 — the rules, declared before results

**Rule 1 — beats the control (unchanged).** A configuration's return advantage
over the unmodified control (`no_reserve`, limit off) counts as real only if its
median across draws exceeds the control's maximum across draws. Report the margin
in dollars and as a percentage of the control's max, so a knife-edge pass is
visible as one. Last run's `D` cleared by $979 — 0.6% — and that margin is the
kind of thing fifteen draws exist to resolve.

**Rule 2 — separating two configurations (unchanged).** Two configurations are
separable on return only if their draw ranges do not overlap. Overlapping ranges
mean **tied**, reported as tied, never ranked by median.

**Rule 3 — REPLACED. Shape, then plateau.**

*3a — shape.* Take each configuration's median final value, ordered by limit
value. Compute first differences. The surface is:

- **Unimodal and usable** if the sign sequence of those differences is
  `+…+ −…−` — any number of each, either side possibly empty — allowing at most
  **one** violation whose magnitude is smaller than the smaller of the two
  adjacent configurations' draw ranges.
- **Jagged and unusable** otherwise: two or more material sign changes. In that
  case nothing is spec'd from the axis, exactly as before.

Report the sign sequence explicitly so the classification is auditable.

*3b — plateau, not argmax.* If 3a passes, **do not report a single best value.**
Identify the peak configuration by median, then report the **plateau**: every
limit value whose fifteen-draw range overlaps the peak's range, by Rule 2's
overlap test. That set — not its argmax — is the recommendable region. If the
plateau spans most of the axis, say plainly that the axis does not discriminate.

**Rule 4 — the drawdown bar, applied to a distribution.** Score against the
standing **38.0%** ceiling using each configuration's **median** max drawdown
across its fifteen draws, not a single draw. Then report, separately, the
**share of draws clearing the ceiling**. A configuration is:

- **Passing** if its median drawdown clears 38.0% (and it beats SPY, QQQ and
  TMFC on return, per `BACKTEST_SIMULATOR.md`);
- **Robustly passing** only if it also clears on **at least two thirds of its
  draws**;
- **Fragile** if it passes on the median but on fewer than two thirds.

The 38.0% ceiling remains the authoritative bar for scoring — the design session
has not adopted 39.12%. **Do not score anything against 39.12%.** You may report,
as a plain diagnostic, the count of draws each configuration puts below 39.12%,
clearly labelled as a diagnostic and not a score, so that adopting or rejecting
the corrected ceiling later is a cheap decision rather than another sweep.

Do not soften any of these after seeing the numbers, and do not substitute an
alternative rule. If a rule produces an awkward result, that is the rule working.

## Step 3 — apply Rule 2 to drawdown as well

Last run left `no_reserve`+10pp and conformant `swap_funding`+10pp incomparable:
one wins on return, the other on the bar. With drawdown now measured on every
draw, run the overlap test on the **drawdown** distributions of the top
configurations of each mode as well as their return distributions, and report
both. Two configurations that overlap on drawdown are tied on risk, whatever
their point estimates say.

## Step 4 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a limit value, do not pick a `minPositionDollar`, do not adopt the 39.12%
ceiling, do not amend any spec, do not resolve §12 items, do not start the
cadence / scope / veto sweep.

`minPositionDollar` stays out of this sweep deliberately — one axis at a time
until the limit axis is resolved. Keep reporting its distribution as input for
the decision that follows.

Lead with:

> **Limit surface: [unimodal / jagged] for `no_reserve`, sign sequence [..];
> [same] for conformant `swap_funding`. Plateau: [set of limit values, or "the
> axis does not discriminate"]. Configurations robustly passing the 38.0% bar:
> [list, or none]. Best `no_reserve` vs best `swap_funding`: [separable /
> tied] on return, [separable / tied] on drawdown.**

Then: the full 18-configuration table with return and drawdown distributions, the
sign sequences, the plateau derivation, the funding diagnostics, the donor
size distribution, and the Rule 4 scoring with pass-share.

Flag plainly: any rule that gives an uncomfortable answer, any configuration
whose median and forward draw disagree about passing, anything contradicting §5's
measurements, and any previously published number that turns out to be wrong.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop, as last run did correctly. `testing/` is now
  gitignored; leave it that way.
- Report wall-clock runtime for the 270 runs.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
