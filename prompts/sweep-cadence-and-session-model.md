# Cadence `K` — and the session model the limit is denominated in

§5's corollary ("the cadence, scope and veto sweeps cannot run before funding
mode is settled") is satisfied. Funding mode is **`swap_funding`**, decided
2026-09-01. See `ALLOCATOR_OPERATING_MODEL.md` §0 for the settled configuration
and `docs/handoffs/2026-08-31-allocator-state-of-play.md` for the evidence.

**Why this run exists, and why it is not just another parameter sweep.**

The settled per-session change limit of **2.5pp is provisional**, because every
measurement to date ran at **per-call cadence**: `decide_fn` fires once per
earnings event, so a position can only receive on its own call — roughly four
times a year. Under §2's session model a session happens every `K` days and
§3's **cash-deployment scope** offers free cash to the best eligible candidate
*anywhere*, not only to names that reported. The same 2.5pp therefore deploys
at a completely different rate: ~10pp/year at per-call cadence, up to ~130pp/year
at K=7.

**The limit value and the cadence are the same measurement.** Re-deriving one
without the other is meaningless.

This also means the run requires **new machinery, not a new knob**: §3's session
model has never been implemented. That is Step 1, and it is gated.

Read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b and §11
before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**, `swap_funding` with the conformant per-date trim
cap throughout. Work on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/sweep-cadence-and-session-model-out.md`.

---

## Step 0 — carry forward, unchanged

Clean tree with a hard stop if `git_dirty` cannot be `false`; driver committed
before any manifest is written; import-time assertions on both; `loaded_` and
`in_window_event_count` recorded separately. **Place `off` at the LOOSE end of
any limit axis** — putting it first produced three false "jagged" verdicts.

## Step 1 — implement the session model, and prove it changed nothing

Per §2 and §3:

- A **session** occurs every `K` days from a phase offset. A call is in scope
  when `call_date <= session_date` and it has not been acted on before.
- Session sequence (§3): evaluate every ticker that reported since the last
  session — profit-take check first, then the recommended action — then pool all
  free cash and deploy it in §4's rank order to eligible candidates **anywhere
  in the universe**, subject to the per-session change limit.
- Held positions are **not** re-sized on price drift alone.
- **Scope is a swept axis**: `new_calls_only` and `cash_deployment`. Do not
  implement full re-sizing — §3 rejects it.

**Equivalence gate (hard stop).** Configure the session model to be
behaviourally identical to the existing per-call harness — one session per
distinct call date, `new_calls_only` scope — and confirm it reproduces the
settled configuration's numbers **exactly**:

```
swap_funding, 2.5pp, per-call equivalent, forward draw  ->  $190,481 (median $190,481 over 15 draws)
no_reserve, off, per-call equivalent, forward draw      ->  $141,836.57   (standing assertion)
```

**If either differs by a cent, stop and report.** New machinery that changes the
old answer means the two sweeps cannot be compared, and everything downstream is
void.

## Step 2 — the five gates

Unchanged from the last run, on a sample of configurations spanning the grid:

1. **Standing assertion** — `$141,837`.
2. **Invariant #2, decision time** — `max(target_pct − cap_pct) ≤ 0`.
3. **Invariant #9 — now per SESSION, not per event.** With the session model in
   place this becomes the literal reading of §5: no session may move a single
   position by more than `X` pp, summed across every trade in that session.
   Report the maximum observed. This is the invariant most likely to break under
   the new machinery, because cash-deployment scope can touch one ticker twice
   in a session.
4. **Invariant #5 — conditional.** Stop only on a skipped event *not* classified
   `known_s11_concatenation`. An unclassifiable skip is a stop.
5. **Independent drawdown recomputation** agrees within 0.01pp.

**A diagnostic that contradicts an expectation in this prompt is a finding to
report, never a reason to stop.** No gate may test a condition §11 documents as
a known unfixed defect.

## Step 3 — the grid

`swap_funding` only. The other modes are settled out; do not re-run them.

| Axis | Values |
|---|---|
| **`K`** | 7, 14, 30, 60, 90 days, plus the **seasonal** variant (weekly during days 15–42 after each quarter-end, monthly otherwise) |
| **Phase** | 3 offsets per `K`, reported phase-averaged with the spread |
| **Scope** | `new_calls_only`, `cash_deployment` |
| **Limit `X`** | 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5 pp, and `off` |
| **Draws** | 7 (forward, reversed, seeds 1–5) for the scan |

Re-run the **top region only** at 15 draws before any rule is applied to it.

Report per configuration: final value min / median / max and spread as a % of
median; max drawdown min / median / max across draws; and forward-draw
diagnostics — days below 1% cash, Adds fully funded / partial / unfunded,
cumulative shortfall, distinct tickers held, displacement count, donor size
distribution, and **per-ticker mean information staleness** (§10 requires it and
it is the whole point of the cadence axis).

**Phase handling per §2:** every `K` is run at ≥3 offsets and reported
phase-averaged. The *spread across phases* is a fragility signal — a `K` whose
result swings widely by start date is fragile regardless of its mean.

## Step 4 — fold in three cheap things

**4a. `minPositionPct` and the stub rule (§12, unmeasured).** At the best
cadence/limit region, sweep the floor as a **percentage of portfolio** —
0 (off), 0.25%, 0.5%, 1% — with the rule: *if a swap-funding trim would leave
the donor below the floor, sell the whole position instead.* Add an absolute
tradability sub-floor of $100. Report effect on final value, drawdown,
displacement count, realized gains, and distinct tickers held. Expected to be
housekeeping rather than performance — say plainly if it is.

**4b. Ordering confirmation, not a sweep.** At the settled configuration the
spread across fifteen orderings is 0.9%; at 1pp and below it is zero. Run the
forward / reversed / 3-seed comparison **once** at the winning cadence and limit
and report the spread. If it stays under ~2%, record that the ordering rule is
answered and §4's seeded-random tie-break stands on principle rather than
measured impact.

**4c. Staleness vs. return.** Report the frontier directly: for each `K`, mean
information staleness against median final value. This is what answers "the
price of Step 6" (automated transcript ingestion) in §10's expected outputs.

## Step 5 — the rules

**Rules 1, 2 and 4 unchanged**, except that Rule 4 now scores against the
**adopted 39.12%** ceiling (settled 2026-09-01), using **median** max drawdown
across draws plus share-of-draws clearing; robustly passing requires ≥ 2/3.
Report margins as percentages.

**Rule 3 — single clause, unchanged.** Order by limit value with `off` at the
loose end, take medians, compute first differences. A difference is **material**
if `|Δ| ≥` the smaller of the two adjacent configurations' draw ranges. Discard
immaterial differences. Unimodal and usable if the remaining material
differences read `+…+ −…−`; jagged otherwise. Report every classification with
both magnitudes.

**Rule 3b — REPLACED. Declared before results.** The overlap test has become
useless: draw spreads collapse below 1% at tight limits, so non-overlap is
trivially achieved and it returns singletons. Replace with a
practical-significance band:

> **The plateau is every value whose median is within 2.5% of the peak's
> median.** Report the band's sensitivity — which values enter or leave at 1%,
> 2.5% and 5% — so the choice of band is visible rather than load-bearing.
> Never report a single best value. **If the peak sits at either end of the
> sampled range, the optimum is not bracketed** — say so and recommend nothing
> until it is.

Apply Rule 3/3b **per cadence**, and separately across cadences at each
cadence's own best limit.

## Step 6 — report

Scope boundary: **report, do not decide.** Do not select `K`, a limit value, a
scope, or a `minPositionPct`; do not amend any spec; do not resolve §12 items; do
not start the veto sweep.

Lead with:

> **Equivalence gate: [passed / failed]. Gates: [all five passed / failed on X].
> Minimum viable cadence: `K` = [X] days ([the smallest K still clearing the
> §10 bar]). Best cell: `K`=[X], scope=[Y], limit=[Z]pp — [return], [DD], vs
> the per-call reference $190,481 / 22.7%. Limit surface per cadence:
> [unimodal / jagged]; plateau [set]; optimum [bracketed / NOT bracketed].
> Staleness cost: [X] days of mean staleness costs [Y]% of return.
> `minPositionPct`: [housekeeping / material]. Ordering spread at the winner:
> [X]%.**

Then: the equivalence check, gate results, the full grid with phase-averaged
values and phase spreads, the limit surface per cadence with material/immaterial
classification and plateau, the staleness/return frontier, the
`minPositionPct` sweep, the ordering confirmation, and Rule 4 scoring.

Flag plainly: any gate that fails, any cadence whose phase spread makes it
fragile, any rule that gives an uncomfortable answer, and any previously
published number that turns out to be wrong.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop. `testing/` stays gitignored.
- Report wall-clock runtime, and the cell count actually run.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
