# Bracket the tight limit — corrected gates

`wrap-ups/verify-and-bracket-tight-limit-out.md` did its job. The verification
cleared the things that mattered and stopped exactly where it was told to.
**Both gate failures were errors in the previous prompt, not in the code or the
run.** The design session owns them.

**What the verification established, and the design session confirmed
independently:**

- Independent drawdown recomputation agrees to four decimal places (18.7825%,
  both derivations, no shared code). The number is not a calculation artifact.
- Invariant #9 exact: max single-session position change **2.50pp** against a
  2.5pp limit.
- Invariant #5: zero `skipped_events`, no `InsufficientCash` anywhere.
- **The cash-drag concern is refuted.** `no_reserve` at 2.5pp is **100% invested
  at its own drawdown trough**, holding 15 of 16 names. The low drawdown is
  diversification, not sitting out the decline in cash. This was the real
  question and it is answered.
- The wrap-up flagged a "~$60–100" difference from last session and did not chase
  it. **There is none.** Last session's `dense-no_reserve-2.5pp` manifest records
  a forward draw of `$185,241.776281105`; this session produced `$185,241.78`.
  Reproduces to the cent, which also confirms the `DailySnapshot.position_values`
  addition is inert. The comparison was forward-draw against last session's
  *median*, which is a different draw. Nothing to investigate.

**The two failures, corrected:**

**1. The invariant #2 "breach" is not one.** §9 invariant #2 reads: *"No
position's **target** may exceed its tier cap."* The previous prompt asked for
*maximum position weight observed* under that heading. Those are different
quantities. TTD's computed target was correctly ≤ 15% on 2023-05-10; price drift
afterward carried its realized weight to 16.4%. The invariant as written was
never violated. Gate corrected below to test targets at decision time; realized
drift becomes a **diagnostic** with a proper census, because it is a real and
previously unmeasured phenomenon worth understanding.

**2. The binding-constraint check was a prediction, not a correctness
condition.** The previous prompt asserted "at 2.5pp the session limit should
dominate" and made it a gate. It doesn't dominate for `no_reserve` (cash 54,
limit 44) — and that is **data, not a failure**. Demoted to a diagnostic.

**Standing instruction for this run: a diagnostic that contradicts an expectation
stated in this prompt is a finding to report, never a reason to stop.** Only the
five gates in Step 1 stop the run.

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §3, §4, §5, §9, §10 and
§10b before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, conformant per-date trim cap on every
swap-funding run. Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/bracket-tight-limit-corrected-gates-out.md`.

---

## Step 0 — carry forward, unchanged

Clean tree with a hard stop if `git_dirty` cannot be `false`; driver committed
before any manifest; import-time assertions on both; `loaded_` and
`in_window_event_count` recorded separately.

## Step 1 — the five gates, and only these five

Run on the `no_reserve` and `swap_funding` configurations at the tightest and
loosest sampled limits, plus the unmodified control. **A failure in any of these
five stops the run. Nothing else does.**

1. **Standing assertion** — `no_reserve` control reproduces **$141,837**.
2. **Invariant #2, at decision time.** Assert that every `target_pct` computed
   inside `_decide_add` (and the first-call starter path) is ≤ the ticker's
   `cap_pct` at the moment of the decision. This is the invariant as §9 states
   it. Report the maximum `target_pct − cap_pct` observed; it must be ≤ 0.
   Note §11 documents a known first-call starter breach — if that path fires
   and breaches, report it as the known defect rather than a new one, and do not
   stop for it.
3. **Invariant #9** — max single-session position change ≤ the configured limit
   plus rounding.
4. **Invariant #5** — zero `skipped_events`, no `InsufficientCash` or
   `InsufficientShares` caught.
5. **Independent drawdown recomputation** — the second, separately written
   function agrees with `compute_summary` to within 0.01pp.

## Step 2 — cap-drift census (diagnostic, never a gate)

The finding the last run surfaced is real and nobody has ever measured it:
**nothing restores a position to its cap after price drift.** Profit-take only
fires at 25%, so a 15%-cap speculative can sit above its cap indefinitely. §5
says caps are inviolable; §3 deliberately allows positions to drift between calls
and credits that for the Type B result. Those coexisted only because cash
starvation meant nothing ever reached its cap.

For **every configuration in Step 4's grid**, forward draw, report:

- per ticker: maximum realized weight (% of `portfolio.total_value`, the same
  denominator `_decide_add` uses), its cap, the number of trading days spent
  above cap, and the maximum excess in percentage points;
- per configuration: how many tickers ever exceed cap, and total ticker-days
  above cap;
- across the grid: **does drift-above-cap increase with tighter limits and with
  `swap_funding`?** The hypothesis is that it becomes reachable only once
  funding works — under `no_reserve` at 2.5pp the largest position anywhere was
  FSLR at 8.6%, nowhere near a cap. Test that hypothesis and report whether it
  holds.
- **the largest excess anywhere in the grid, and whether anything approaches the
  25% profit-take threshold.** If nothing exceeds ~20%, the gap between "caps are
  inviolable" and what the code enforces is narrow and the design decision is
  low-stakes. If something reaches 24%, it is not.

**Report only.** Do not implement a cap-restoration rule, do not amend §5 or §9.

## Step 3 — binding-constraint census (diagnostic)

For every configuration in the grid, forward draw, classify each Add-shaped
decision's binding constraint as `target gap`, `cash available`, or `session
limit`, and report the counts. The interesting question is how the mix shifts
across the limit axis and between modes — at 2.5pp it was cash-dominant for
`no_reserve` (54/44) and limit-dominant for `swap_funding` (53/42). Report the
whole surface rather than two points.

## Step 4 — the bracketing grid

This is the 300-run grid the previous prompt specified and never executed. The
code exists in `analysis/verify_and_bracket_tight_limit.py` and is **untested
past the point Step 1 stopped** — treat it as unverified.

Ten limit values × two funding modes × fifteen draws (forward, reversed, seeds
1–13) = 300 runs.

| | values |
|---|---|
| **Session limit** | off, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 10 pp |
| **Funding mode** | `no_reserve`; `swap_funding` (conformant per-date cap only) |

**Anchor check.** `off` and 10pp must reproduce the previous grid's medians
**exactly** — forward draws have now been shown to reproduce to the cent, so
there is no tolerance to allow. Report whether they do. A mismatch means
something changed and the cross-grid comparison is void; report it and continue,
flagging every affected conclusion.

Record per configuration: final value min / median / max and spread as a % of
median; **max drawdown min / median / max across all fifteen draws**; and the
forward-draw funding diagnostics (days below 1% cash, Adds fully funded /
partial / unfunded, cumulative shortfall, distinct tickers held, displacement
count, and for swap-funding the donor size distribution below 2% / 1% / 0.5%).

**Follow the peak.** Whatever configuration ends up with the highest median,
repeat last run's trough analysis on it: invested share and full holdings at its
drawdown trough, plus terminal composition. The cash-drag question was answered
for 2.5pp; if the peak moves, the answer has to move with it.

## Step 5 — the rules

**Rules 1, 2 and 4 unchanged.** Rule 1: median beats the control's max; report
margins in dollars and as a percentage. Rule 2: separability by non-overlapping
fifteen-draw ranges, applied to **both** return and drawdown; overlapping means
tied. Rule 4: score on **median** max drawdown across draws against the standing
**38.0%** bar, plus share-of-draws clearing it; "robustly passing" requires ≥ 2/3.

The **39.12%** ceiling is still not adopted — do not score against it; continue
reporting draws-below-39.12% as a labelled diagnostic only.

**Rule 3 — single clause, as rewritten last run.** Order configurations by limit
value, take median final values, compute first differences. A difference is
**material** if its absolute value is ≥ the smaller of the two adjacent
configurations' fifteen-draw ranges, **immaterial** otherwise. Discard immaterial
differences as noise. The surface is **unimodal and usable** if the remaining
material differences read `+…+ −…−`, either side possibly empty; **jagged and
unusable** otherwise. No second test, no violation counting. Report the
classification of every difference with both magnitudes so it is auditable.

**Rule 3b — plateau, with the boundary condition.** Report the plateau: every
limit value whose fifteen-draw range overlaps the peak's. Never a single best
value. **If the peak sits at either end of the sampled range, the optimum is not
bracketed** — say so explicitly, report the plateau as open at that end, and
state that no limit value can be recommended until the axis is bracketed on both
sides.

## Step 6 — report

Scope boundary: **report, do not decide.** Do not select a funding mode, do not
choose a limit value, do not pick a `minPositionDollar`, do not adopt the 39.12%
ceiling, do not add a cap-restoration rule, do not amend any spec, do not resolve
§12 items, do not start the cadence / scope / veto sweep.

Lead with:

> **Gates: [all five passed / failed on X]. Anchors reproduce: [yes / no].
> Limit surface: [unimodal / jagged]. Peak [X]pp, plateau [set], optimum
> [bracketed / NOT bracketed]. Robustly passing the 38.0% bar: [list]. Cap
> drift: [N] tickers exceed cap across the grid, largest excess [X]pp on
> [ticker] at [config]; drift [does / does not] increase with tighter limits and
> swap-funding. Binding constraint at the peak: [cash / limit / target gap]
> dominant.**

Then: gate results, the anchor check, the full 20-configuration table with
return and drawdown distributions, the material/immaterial classification, the
plateau derivation, the peak's trough analysis, the cap-drift census, the
binding-constraint surface, and Rule 4 scoring with pass-share.

Flag plainly: any gate that fails, any anchor that does not reproduce, any rule
that gives an uncomfortable answer, any configuration whose median and forward
draw disagree about passing, and any previously published number that turns out
to be wrong.

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
