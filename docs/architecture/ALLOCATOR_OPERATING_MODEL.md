# Allocator Operating Model

**Status:** Design spec — agreed 2026-08-30. Not yet implemented.
**Resolves:** Task #77 (Established/Speculative individual sizing divergence).
**Supersedes:** the undocumented pool-splitting layer in `server/routes/moves.js`.
**Read with:** `PORTFOLIO_ANALYST_SPEC.md`, `BACKTEST_SIMULATOR.md`, `DESIGN_PRINCIPLES.md`.

New allocator code is written against **this document**, and validated by
reproducing (or improving on) the simulator results the measurement plan in
§10 defines. This spec is the test oracle; the code is the thing under test.

---

## 1. What #77 actually was

Production sized the same Established/Speculative ticker with two formulas:

| Path | Function | Divisor | Behavior |
|---|---|---|---|
| Currently held | `computeIndividualModelWeights.allocate` | `max(heldCount, targetSlotCount)` | reserves headroom for empty slots |
| New candidate | `sizeSide` | `min(targetSlotCount, qualifyingCount)` | fully deploys across current qualifiers |

Observed live: a sole qualifying candidate (NVDA) sized at 37.5% of portfolio —
the entire Established pool — where a held position on the same side, same day,
same pool would have been sized ~3.4%. 11x, zero thesis change.

**Root cause, established this session:** the divergence is a *symptom*. Both
formulas exist only because a **bucket target** (`estPoolPct` / `specPoolPct`,
the Admin-panel barbell parameter) creates a dollar pool:

```js
const bucketTargetValue = totalPortfolioValue * (b.poolPct / 100);  // moves.js:1824
function splitBucketTarget(groups, bucketTargetPct) { ... }         // moves.js:1224
  const evenShare = bucketTargetPct / claimants.length;             // moves.js:1248
```

A pool must be divided among claimants. That division got implemented twice,
with different divisors, in different sessions, with no shared spec.

**The validated model has no pool.** `analysis/simulator/allocator_v2/v3/v4.py`
and `simulator.py` contain no side, bucket, pool, or slot concept. `_type_cap()`
takes `type_classification` and `tier` and returns a per-position percentage.
That is the entire sizing constraint behind the $287k full-window result.

### Five divergences, not one (updated 2026-08-30)

Recon found that `allocate` and `sizeSide` differ in more ways than the
headroom/deploy split, and that production's use of Type A/B has drifted from
the validated model in two further ways. All five live inside the pool-splitting
layer; none was ever checked against a written spec.

1. `allocate` reserves headroom (`max(held, target)`); `sizeSide` deploys fully
   (`min(target, qualifying)`).
2. `allocate` ignores per-owner cap overrides (`OwnerTickerConfig`); `sizeSide`
   honors them.
3. `sizeSide` has a `minPositionDollar` floor-and-drop loop; `allocate` has none.
4. **Cap source differs.** Production uses
   `min(Ticker.capPercent, latestAnalysis.capPercent)` — a stored per-ticker
   value floored by the analyst's per-call suggested cap, with
   `OwnerTickerConfig` overriding on top (`moves.js:206`, `:1089-1094`). The
   simulator computes the cap from the 2×2 matrix `(type, tier) → 15/35/50`.
   Two different mechanisms; nothing enforces that they agree.
5. **Production tilts Type B by 1.5×** (`moves.js:207`):
   `raw = baseWeightPct * (ticker.type === 'B' ? 1.5 : 1.0)`. In the validated
   model Type A/B is *only* a ceiling. In production it is a ceiling **and a
   relative preference**. Because the following lines rescale the group to
   `fairShareSum`, this does not inflate the group total — it redistributes
   within the group, giving Platform names 1.5× the share of Pure-play names,
   and cancels entirely in an all-Type-B group. Unvalidated either way.

Also noted at `moves.js:225`: `min(raw * scale, hardCapPct)` applies the cap
last and **does not redistribute the capped excess**. A name that hits its cap
forfeits its remainder to nobody, so the group sums to less than its fair share.
This silent leakage is part of why the `(unallocated)` rows exist.

**Therefore #77 is resolved by deletion, not unification.** See §6.

---

## 2. Session cadence — the parameter `K`

The allocator does not run continuously. It runs when the user opens the app.

> **K** — the session interval in days. Every K days the user opens the app,
> uploads all transcripts released since the last session, and executes every
> recommended trade in that session at that day's close.

- A call is in scope for a session when `call_date <= session_date`.
- **Ingestion timing is unobservable.** Nothing acts between sessions, so
  uploading a transcript the day it drops or the morning of the session
  produces identical results. There is no ingestion-cadence parameter and no
  ingestion discipline to specify — only K.
- Effective information staleness is uniform on `[0, K]`, mean `K/2`.

### Why cadence is the primary variable

The validated model decides per call, same day. Real use batches. Measured
against the corpus in `analysis/data/transcripts/` (659 calls, 32 tickers,
2020-05 → 2026-05):

| K | Sessions/yr | Empty sessions (top20) | Mean calls/session | Max in one session |
|---|---|---|---|---|
| 7d | 52 | 49% | 1.4 | 10 |
| 14d | 26 | 30% | 2.8 | 13 |
| 30d | 12 | 7% | 5.9 | 16 |
| 90d | 4 | 0% | 17.3 | 23 |

Contention scales with K. So does staleness. The spec's headline output is the
**minimum cadence at which the strategy still beats its benchmarks** — stated as
a user requirement, not an internal constant.

### Seasonal cadence variant

Calls are not uniformly distributed. Measured by days after quarter-end:

| Window | full 32 | top20-2021 |
|---|---|---|
| Days 1–14 | 5% | 8% |
| **Days 15–42** | **69%** | **71%** |
| Days 43–56 | 14% | 16% |
| Days 57–95 | 12% | 6% |

Month 1 of each quarter carries 53–66% of all calls; month 3 carries 5–11%.

A **seasonal cadence** — weekly during days 15–42 after each quarter end,
monthly otherwise — is ~24 sessions/year against uniform-K=7's 52, while
catching ~70% of calls at comparable freshness. This is a first-class variant
in the measurement plan (§10) and, if it performs, the spec's recommended
default: it is a materially easier commitment to keep.

### Phase is a nuisance parameter, not a design parameter

K defines the interval; it does not define which calendar day the grid starts on.
That offset is the **phase**. Companies report on stable schedules, so a fixed
phase grants some tickers permanently fresher treatment than others, every
quarter, for the whole run.

Measured per-ticker staleness spread (most-favored vs least-favored ticker):

| K | Single fixed phase | Averaged across phases |
|---|---|---|
| 7d | 3.4d | **0.0d** |
| 14d | 5.2d | **0.5d** |
| 30d | 7.6d | **1.3d** |
| 60d | 15.2d | **1.8d** |
| 90d | **51.4d** | **6.0d** |

**Rule:** every K is run at multiple phase offsets and reported phase-averaged.
The *spread* across phases is reported as a fragility indicator — a K whose
result swings widely by start date is fragile regardless of its mean.

This satisfies, rather than adds to, `BACKTEST_SIMULATOR.md`'s existing rule
that a strategy must hold across multiple start dates.

Randomizing K is explicitly rejected: it models an inconsistent user. Each phase
run models a perfectly consistent user who started on a different day.

---

## 3. Scope of a session — cash-deployment re-evaluation

Three candidate scopes were considered. The middle one is specified.

| Scope | Behavior | Verdict |
|---|---|---|
| New-calls-only | act only on tickers that reported this session | **Rejected** — cash idles until an Add happens to arrive |
| **Cash-deployment** | act on this session's calls, then offer all free cash to the best eligible candidate anywhere in the universe | **Specified** |
| Full re-sizing | recompute every position's target and trade the delta | **Rejected** — see below |

### Session sequence

1. For each ticker reporting this session, evaluate in the order defined by §4:
   profit-take check first (it supersedes the call's action), otherwise the
   recommended Add / Trim / Exit / Hold.
2. Pool all free cash — standing balance plus this session's proceeds.
3. Deploy it to eligible candidates in rank order (§4) until exhausted or no
   candidate remains, subject to the per-session position-change limit (§5).
4. Held positions are **not** re-sized on price drift alone.

### Why full re-sizing is rejected

It trades on price drift with no new information, generating realized gains in
taxable accounts from market noise — against the grain of every tax-aware rule
in the architecture.

More seriously, it would fire profit-take every session rather than on each
ticker's own call. A winner at 30% would be shaved to 25%, then 20%, within two
sessions, and pinned in a 20–25% band permanently. `PORTFOLIO_ANALYST_SPEC.md`
(§"Where the cap actually binds") credits the opposite behavior for the Type B
result: *"Type B lets them reach 40-50% before the next call's profit-take
catches up... why Type B's impact is large on universes containing monster
compounders (e.g., AVGO 8x in our window)."*

The validated result depends on positions being **allowed to drift between
calls**. Full re-sizing removes exactly that.

---

## 4. Eligibility, ranking and rationing

This is what #77 should have been about: not which pool divisor, but **who gets
cash and in what order** when eligible demand exceeds supply.

### Eligible for cash

A ticker qualifies for cash deployment when **all** hold:

- Latest verdict is `Add`
- Position is below its tier cap (§5)
- Verdict is no older than one quarter plus a grace window
- **Quality floor:** `final_confidence` is not `unknown`; thesis health is not
  weakening; the existing no-average-down rule on speculatives has not fired
  (`day_price >= weighted_cost_basis` for `tier == "speculative"`)

Cash accumulating because nothing clears this floor is correct behavior, not a
failure. See §5.

### Rank order

1. **`final_confidence`** — `confident` before `advisory`; `unknown` is
   ineligible. Note this field is three-state
   (`compute_final_confidence`, `trend_analyst.py:733`) and most events resolve
   to `confident`. **It is a coarse filter, not a discriminator** — ties are the
   norm, so the keys below do the real work.
2. **Verdict recency** — freshest information first. This is the primary
   discriminator, and it directly counteracts the staleness introduced by K.
3. **Gap to target**, as a fraction of target — the most underweight name first.
4. **Final tie-break: seeded random. Never alphabetical.**

### Why the tie-break rule is mandatory

The simulator resolves same-day contention alphabetically —
`ORDER BY callDate ASC, symbol ASC` (`data.py:178`) and
`events.sort(key=lambda e: (e.ticker, e.call_date))` (`data_from_cache.py:76`),
consumed sequentially with immediate trade execution. When cash binds, **AAPL
wins every contest it enters and TTD loses every contest it enters**, for the
whole run.

This is not rare. 63.4% of calls in the 32-ticker universe (56.5% in
top20-2021) land on a day with at least one other call. The alphabet decided the
majority of contested events behind the validated numbers, and the front of this
alphabet is disproportionately the mega-cap tech complex that compounded hardest
in the window.

A deterministic tie-break hides its influence as bias. A seeded random one
exposes it as variance across seeds. Seeds are swept.

### Rationing

Fill in rank order until cash is exhausted. **No pool division.** There is no
bucket, no slot count, and no divisor.

---

## 5. Position sizing and cash policy

### Tier caps (authoritative)

|  | Type A (Pure-play) | Type B (Platform) |
|---|---|---|
| **Speculative** | **15%** | 50% |
| **Established** | **35%** | 50% |

Flat 50% for all Type B regardless of driver count. The variable 40–60% scheme
was tested and retired 2026-05-17 (full-window v3 $287k flat vs $266k variable,
no drawdown benefit); `driver_count` remains plumbed but is a no-op in cap math.
The `DESIGN_PRINCIPLES.md` §5 text describing a variable 40-60% Type B cap is
**stale** and should be reconciled.

Caps are computed against **in-scope portfolio value**, not total
(`PORTFOLIO_ANALYST_SPEC.md`, "Out-of-scope position handling").

### Add sizing

```
target_pct = min(recommended_size, tier_cap)      # % of in-scope portfolio value
delta_$    = target_pct * portfolio_value - current_position_value
buy_$      = min(delta_$, cash_available, session_change_limit)
```

Funding drains `tax_advantaged` first, then `taxable`. A single Add may create
lots in both accounts. Target is portfolio-wide; funding is account-sequenced.

### Per-session position-change limit

> **No session may move a single position by more than X percentage points of
> portfolio value.**

This is the control that prevents a name reaching its cap in one step on
information that may be up to K days stale. It generalizes v3's existing
first-call starter (5% speculative / 8% established) rather than fighting it,
and it is what actually addresses the NVDA case — the hazard was concentration
built in a single step, not the cash policy or the cap.

`X` is a swept parameter (§10).

### Cash policy: deploy to cap, no reserve

- **Deploy fully, up to caps. Never above.** Caps are inviolable.
- **No reserve parameter, no cash ceiling in the default.**
- Cash is a **residual**, not a policy instrument. It accumulates when few names
  clear the eligibility floor — verdict scarcity, the analyst declining to find
  buys, which is the system working in a poor tape.
- Cash earns no interest, matching `BACKTEST_SIMULATOR.md`.
- Reported as a diagnostic: average cash %, days in cash.

**Rejected: holding a position above its cap to avoid cash drag.** Mechanically
this is the capitulation pattern (§8) adopted as policy — hold oversized, plan
to reduce later, discover the reduction happens on the way down. The asymmetry
is unfavorable (bounded, known drag vs unbounded, unknown breach) and it would
contradict profit-take, which trims anything above 25% on that ticker's next
call. It also buys almost nothing: three concurrent Established Adds at 35%, or
two Type B at 50%, absorb an entire portfolio.

**Cap saturation is mostly a phantom in a mega-cap book** — twenty names at 35%
is 700% of headroom against 100% of portfolio. It is genuinely reachable in a
speculative-heavy book, where a 15% cap requires **seven** concurrent qualifying
Adds to reach full investment.

### Cash saturation is NOT a phantom — funding mode is a swept axis (added 2026-08-30)

Cap saturation and **cash** saturation are different problems, and the second one
is real. Discovered via SPWR in the clean-window baseline: its ALL16-vs-ALL15
delta was exactly $0.00, because a first-call starter arriving in month 29 of a
30-month run found both accounts empty.

Both the v3 starter and `_decide_add` fund the same way:

```python
for account_name in ("tax_advantaged", "taxable"):
    if remaining <= 1e-6: break
    cash_avail = portfolio.accounts[account_name].cash
    if cash_avail <= 1e-6: continue      # silently skips
    ...
return trades                            # empty list if both accounts are dry
```

No exception, no `skipped_events` entry, no warning. **A position that cannot be
funded simply never appears, and nothing records that it was wanted.** See §11.

The structural consequence: with deploy-to-cap and no reserve, nothing ever sells
one position to fund a better one. Cash appears only when a Trim, Exit, or
profit-take fires on a ticker whose *own* call arrives. A new candidate added to
a fully-invested portfolio is structurally unable to open — which is precisely
the case the Opportunity Scanner exists to produce.

This also raises the stakes on §4's arbitration rule: if cash binds most of the
time, the tie-break is deciding nearly every Add across the corpus, not the
occasional contested day.

**Three funding modes, swept rather than assumed:**

| Mode | Behavior | Cost |
|---|---|---|
| **No reserve** (today) | deploy to cap; new candidates get whatever cash exists | Free; late candidates may get nothing, silently |
| **Cash reserve** | hold X% back for future opportunity | Pays a drag premium every day for optionality that may go unused |
| **Swap-funding** | when a candidate outranks a holding, trim the lowest-ranked holding to fund it | Pays nothing until a genuinely better idea appears; adds turnover and realized gains |

**Swap-funding is not the full re-sizing rejected in §3.** That recomputed every
target on price drift. This fires only on a ranking inversion between a candidate
and a holding, and it reuses §4's ranking — the change is that rank may
*displace*, not only *fill*.

It is also the mirror of `DESIGN_PRINCIPLES.md` §2: that rule says trim proceeds
need a destination before the trim executes; swap-funding says a destination needs
proceeds before the buy executes. Same principle, opposite direction.

### Measured 2026-08-30 — the constraint is not marginal, it is the system

Clean-window instrumentation (ALL16 v3, 2022-01-01 → 2024-06-12, 894 trading
days):

| Measure | Value |
|---|---|
| Trading days with cash < 1% of portfolio | **88.7%** |
| Date cash hit the floor and stayed | **2022-02-16** — week 6 of 122 |
| Add-shaped decisions fully funded | **4 of 99 (4.0%)** |
| Cash-limited (partial) | 20 (20.2%) |
| **Entirely unfunded** | **75 (75.8%)** |
| Cumulative shortfall | **$2,369,889** against $100,000 of capital |

The entire initial capital was consumed in **16 days** by the three names that
reported first:

```
2022-02-01  GOOGL  intended $54,207 -> got $45,478
2022-02-16  NVDA   intended $54,007 -> got $20,915
2022-02-16  QS     intended  $5,095 -> got  $4,611
2022-02-16  TTD    intended $20,380 -> got      $0
2022-03-03  AVGO   intended $56,154 -> got      $0     (AVGO went ~8x in this window)
2022-03-10  ORCL   intended $49,832 -> got      $0
```

Portfolio composition was decided by the **reporting calendar** in the first six
weeks and then frozen for two years. The allocator's rules were not the operative
mechanism; arrival order was.

**Root cause is in the spec, not the code.** `target_pct = min(recommended_size,
type_cap)` makes the cap a *target* whenever the analyst is bullish. Sixteen names
at 15–50% caps sum to ~400% of portfolio. `BACKTEST_SIMULATOR.md`'s "capped by
available cash" was written as an occasional constraint; it has been the primary
allocation mechanism all along, invisibly, because unfunded trades leave no trace
(§11).

This also closes the loop on the same-day-ordering finding: with cash binding 96%
of the time, order is not the tie-break — **order is the allocator.**

### Sequencing decision (2026-08-30): funding before ordering

Ordering is decisive *because* funding is broken. Measured today, "how much does
pick order matter" is a property of a regime we are replacing, and the answer
expires the moment funding is fixed. Funding mode is therefore resolved **first**,
and ordering measured afterward in the regime that will actually operate.

A separate, clearly-labelled **retrospective** ordering probe on the current
corpus is worthwhile — it answers "how much of the historical result was arrival-
order luck" — but it is a diagnostic of the old regime, never a design input.

**Corollary: the cadence, scope and veto sweeps cannot run before funding mode is
settled.** Under current behaviour, changing K changes which names report before
the money runs out, so a cadence surface would measure an arrival-order lottery
and read as information staleness.

### Swap-funding — specification

The normal operating mode of a fully-invested portfolio: fund a new idea by
selling a weaker one.

- **Trigger:** an eligible candidate (§4) cannot be funded from available cash.
- **Donor eligibility:** only held positions whose latest verdict is `Hold`,
  `Trim` or `Exit`. **Never displace a position whose latest verdict is `Add`** —
  the analyst still wants more of it.
- **Donor selection:** lowest-ranked eligible donor first, by §4's ranking.
- **Trim quantum:** at most 25% of the donor per session, reusing the existing
  Trim semantics; never below the minimum position size; drain
  `tax_advantaged` before `taxable`.
- **Bound:** raise only what the candidate's target (subject to the per-session
  change limit) requires — not a wholesale rebalance.
- **Reporting:** realized gains attributable to displacement are reported
  separately from ordinary Trim/Exit, since this mechanism deliberately creates
  taxable events that would not otherwise occur.

This is not §3's rejected full re-sizing: it fires only on a ranking inversion
between a candidate and a holding, and reuses §4's ranking — rank may
*displace*, not only *fill*. It is the mirror of `DESIGN_PRINCIPLES.md` §2:
that rule says trim proceeds need a destination before the trim; this says a
destination needs proceeds before the buy.

**Note on the per-session change limit:** it slows the land grab but does not
bound aggregate demand — sixteen names at 10pp per session is still 160%. It
spreads deployment over a year rather than six weeks, which is a real
improvement, but cash still reaches zero. Only a funding mechanism (reserve or
swap) bounds the system. Treat the limit as a secondary axis, not the fix.

Open: which mode, and at what level. Decided by measurement (§10) plus the
judgment caveats in §10 rule 4 — not by the backtest alone, since a frozen
universe understates the value of being able to fund a new name.

---

## 6. The barbell is a ceiling, not a target

**Decision (Luis, 2026-08-30): "I want to own the best names, period."**

The barbell targets `estPoolPct` / `specPoolPct` are an implementation artifact,
not a portfolio-construction commitment. As *targets* they force purchases of
mediocre speculative names to fill a quota — allocation for allocation's sake,
which is the failure mode rejected throughout this spec.

### What is removed

- `estPoolPct` / `specPoolPct` as **allocation inputs**
- `bucketTargetValue` for the equity sides, and therefore the pools
- `splitBucketTarget` for equities
- `computeIndividualModelWeights.allocate` and `sizeSide` — both, deleted rather
  than reconciled
- **The Type B 1.5× weight multiplier** (`moves.js:207`). It multiplies
  `baseWeightPct`, which exists only because a pool needed dividing, so it dies
  with the pool. Removing it must be **deliberate and noted**, not incidental —
  under this spec Type A/B is a ceiling only, never a relative preference.
- **The cap-excess leakage** at `moves.js:225`, which disappears with the
  normalization step it lives in
- The `(unallocated)` scarcity-gap rows, which are
  `shortfall = bucketTargetValue - achievableValue` and are not a coherent
  concept without a bucket target. **Remove deliberately with a spec'd UI
  change** — do not let them silently zero out.

### What replaces it

> **A ceiling on aggregate speculative exposure. No target, no quota, no
> established-side constraint.**

The est/spec mix becomes an *output*, as in the validated model, with a backstop
against the case tier caps cannot see: six speculatives at 15% each is 90% of
portfolio with every rule respected. Worse, they are not independent — **ENPH,
SPWR, RUN, FSLR is four caps and one bet on solar policy and rates**, which is
60% of a portfolio in a single macro exposure. That is not hypothetical; it is
this portfolio's own 2022–23 history.

Set the ceiling loose enough to be a backstop rather than a shaper (50–60%
suggested). The baseline run's speculative-exposure diagnostic (§10) determines
whether it would ever have bound before any level is committed.

### Sequencing note

The ceiling is **not** built into the measurement baseline. The baseline
reproduces the validated model, which has no barbell at all, so results stay
comparable to the $287k reference. The baseline is *instrumented* to record
aggregate speculative share over time; the ceiling is swept only if that
diagnostic shows it would bind.

---

## 7. Day 1 — starting state

The backtest starts from all cash. Real day 1 starts from an existing portfolio
with embedded gains, per-account structure, and positions possibly over cap.

**Simulation baseline: all cash.** A hypothetical 2021 portfolio cannot be
reconstructed, and inventing one adds a fabricated variable.

**Production has three transition paths, not two:**

1. **Gradual convergence** — hold what you have, let the allocator move toward
   target over time. No forced realization; unknown convergence time.
2. **Full liquidation** — sell everything, start from cash. Reproduces the
   simulation's starting state, but **not for free**: realizing all embedded
   gains at once permanently removes capital before the first trade. The
   simulator pays no such toll, so this path does not reproduce simulated
   results either.
3. **Hybrid (recommended)** — liquidate fully inside tax-advantaged accounts,
   converge gradually in taxable. Zero tax cost on the first, no forced
   realization on the second. Consistent with every tax-aware sequencing rule
   already in the architecture.

**Deferred, not unknowable:** convergence time is measurable without inventing
history. Seed the simulator with synthetic starting portfolios (equal-weight,
deliberately concentrated-wrong, legacy-heavy) and measure sessions until each
trajectory merges with the all-cash path. Run only after the all-cash baseline
produces positive results.

---

## 8. User behavior model

The validated model assumes a perfect operator: every recommendation executed,
at the close, on the call date. Real use is not that, and the gap is where the
tool's value lives.

### Baseline

**0% veto.** Every recommendation executed. Establishes the ceiling.

### Rejected: random independent veto

Under cash-deployment scope a declined recommendation **recurs** — the name is
still `Add`, still under cap, still eligible next session. Redrawn independently
each session, a recommendation appearing five times survives a 20% veto rate
with probability 1 − 0.2⁵ = **99.97%**. The strategy arrives anyway, a few
sessions late. Random veto is nearly self-healing and would understate the risk
to the point of producing a false negative.

### Specified: capitulation model

Models the pattern the agent exists to prevent, on the tickers it happened to
(ENPH, TTD — both deliberately in the backtest universe).

- When a position **first crosses the profit-take threshold (25% of portfolio)**,
  it becomes a "pet" with probability `p`. The flag is sticky for that position.
  `p` is interpretable as *the fraction of your winners you fall in love with*.
  Swept at 10 / 20 / 30%.
- A pet position **declines all recommended Trims and Exits**. Declined `Exit`
  arms the rule as much as declined `Trim` — the ENPH shape was a held position
  through a broken thesis, not a skipped trim.
- Capitulation trigger: **−30% from the trailing peak position value** since
  entry. On trigger, **full exit** at that session's close.

The profit-take rule converts paper gains to cash near peaks. Capitulation
converts them to cash 30% below peaks. This is not a haircut on the strategy —
it is the same mechanism pointed the wrong way.

Being path-dependent, this interacts with K: a slower cadence gives a pet
position more room to run before anyone looks. It must be run **inside** the
cadence sweep, at minimum at the endpoints.

### What this measures

The gap between the 0% baseline and the capitulation runs is **the dollar value
of following the agent's advice when it is emotionally hardest.** For a tool
whose stated purpose is less emotional investment decisions, that is the
product's thesis, quantified against Luis's own tickers.

---

## 9. Invariants — the implementation contract

Any allocator implementation, production or simulator, must satisfy all of these.
These are the shared spec whose absence caused #77. **A conformance test suite
asserting them is part of the build.**

1. **One sizing function.** Exactly one code path computes a position's target.
   Held and candidate positions differ in inputs, never in formula.
2. **No position's target may exceed its tier cap**, at any time, including a
   ticker's first call. (Currently violated — see §11.)
3. **A position's target is a function of its own cap, its own recommended size,
   and portfolio value** — never of how many other candidates exist.
4. **Per-owner cap overrides (`OwnerTickerConfig`) apply identically** to held
   and candidate positions. (Currently violated — `allocate` ignores them,
   `sizeSide` respects them.)
5. **Trade sets are sized against post-trade state.** No two trade lists may be
   computed against the same pre-trade cash or position snapshot and then
   executed in sequence. (Currently violated — see §11.)
6. **No existing holding is dropped to satisfy a minimum-position floor.** The
   `minPositionDollar` floor-and-drop loop applies to candidates only.
7. **Contention is never resolved by a deterministic property of the ticker
   symbol.** Ranking is by §4; the terminal tie-break is seeded random.
8. **Aggregate speculative exposure never exceeds the ceiling** (§6).
9. **No session moves a single position by more than the per-session change
   limit** (§5).
10. **Any new mode flag is persisted into the `MovesCache` payload**, following
    the `isFreshStart` / `isRebaseline` pattern. An unpersisted flag silently
    reverts on refresh — this cost the project task #63 once already.
11. **Type A/B is a ceiling only.** It never acts as a relative weight,
    preference, or multiplier between candidates.
12. **Classification has one source of truth.** `Ticker.type` (live, RADAR-
    editable, "source of truth for the live allocator" per the schema) and
    `analysis/data/type_classifications.json` (frozen 2026-05-23, what the
    simulator reads) are synced one-way, JSON → DB, by
    `apply_type_classifications.js`. Nothing syncs back, and nothing checks
    they agree. Every run must assert agreement or declare which source it
    used. The same hazard applies to tier: no `tier_classifications.json`
    exists, so tier lives only in `Ticker.tierOverride` / `tierMechanical`.

---

## 10. Measurement plan

### Data source — resolved 2026-08-30

The file-based eval cache `analysis/data/evals/v6_sonnet-4-20250514/` is gone and
**cannot be regenerated**: `claude-sonnet-4-20250514`, the model behind the
reference result, has been retired from the API. The cache was never committed
(`.gitignore:15`).

**Resolution: load events from Postgres via `data.py::load_call_events()`.** The
`Analysis` table is an archive of exactly the prompt+model combination that can
no longer be reproduced. Recon 2026-08-30 found:

- **657 of 659** distinct corpus transcripts have a pre-cutoff `Analysis` row.
  The 2 gaps (`NVDA 2020-05-21`, `2020-08-19`) fall outside every test window
  (runs start 2022-01-01 / 2022-01-15), so effective coverage is complete.
- Cutoff is commit `7063465` (2026-06-27), the last v6 `EVALUATION_PROMPT.md`.
  770 of 805 rows predate it.
- **Zero transcripts straddle the cutoff**, so `load_call_events`'s
  `MAX(createdAt)` pick never mixes prompt eras on a usable transcript. A
  `createdAt` filter is still worth adding as a guard against future re-scores.
- 6 rows carry explicit `promptVersion=v6` / `modelVersion=claude-sonnet-4-20250514`
  stamps. The other 764 are untagged, so **pre-cutoff dating is circumstantial,
  not proof.** This caveat travels with every result produced from this corpus.
- No pre-cutoff row contains a `---STRUCTURED---` block, so
  `_extract_type_classification()` returns `None` for all of them. **This is the
  validated configuration, not a defect.** Type A/B comes from `type_for_ticker`
  (precedence rank 1); the per-call value is rank 2, "known to be noisy," and the
  spec forbids it for live decisions (60.9% vs 37.1% drawdown). **Do not build a
  prose fallback to recover it — that would undo the 17% Phase D lift, not
  preserve it.**
- Null trend-layer fields (97 `tier`, 161 `trajectory`, 97 `finalAction`,
  97 `finalConfidence`) are backfillable for $0 by rerunning
  `sync_trend_to_db.py` — deterministic Python, no LLM calls.
- Null `recommendedSize` (123 rows) is handled by design: `_decide_add` falls
  back to the cap, per `BACKTEST_SIMULATOR.md`'s edge-case table.

Backup: `~/investment-agent-backups/analysis_corpus_20260830.sql` (41 MB, data)
plus a schema dump. **Restorability not yet verified.**

### Baseline

`allocator_v3`, unmodified, per-call cadence, alphabetical ordering — reproducing
the existing full-window result. Every cell is reported relative to it.

Run the sweep on the code **as-is** for comparability with the existing corpus,
plus one bug-fixed cell at baseline settings to quantify what §11 was worth.

### Axes

| Axis | Values |
|---|---|
| **K** (session interval) | 7, 14, 30, 60, 90 days + seasonal variant |
| **Phase** | ≥3 offsets per K, reported phase-averaged with spread |
| **Scope** | new-calls-only, cash-deployment, full-re-sizing |
| **Session change limit X** | off, 10, 15, 20 pp |
| **Veto** | 0%; capitulation p = 10 / 20 / 30% |
| **Tie-break seed** | ≥3 seeds wherever ranking ties |
| **Funding mode** | `no_reserve` (today), `cash_reserve` at 5 / 10 / 20%, `swap_funding` |
| **Cash ceiling** | off, 10%, 20% (information only — see caveat) |
| **Spec ceiling** | off (default); swept only if the diagnostic shows it binds |

Arbitration is held at the §4 rule for the first pass so it does not confound the
cadence signal. Ordering variants (reverse-alphabetical, randomized) are run
afterward on the best region.

### Required diagnostics per run

Beyond `BACKTEST_SIMULATOR.md`'s standard outputs: aggregate speculative share
over time, average cash % and days in cash, count of sessions where cash bound,
count of contested rank decisions, and per-ticker mean staleness.

### Success criteria — pre-declared

Adopt `BACKTEST_SIMULATOR.md`'s existing bar unchanged:

- **Pass:** beats SPY **and** QQQ **and** TMFC on absolute return; max drawdown
  no worse than median baseline + 5pp.
- **Soft pass:** beats 2 of 3, within 2pp on the third, drawdown acceptable.
- **Fail:** anything else.

Add **equal-weight-of-universe** as a fourth baseline. It is the sharpest of the
four: it tests whether the *analyst* adds anything over simply owning the same
names.

### Interpretation rules — agreed before any results are seen

1. **Select on robustness, not peak return.** The winning configuration must
   hold across multiple start dates and phases.
2. **The shape of the surface is the finding, not the argmax.** A cadence sweep
   should produce a smooth, monotone-ish surface — fresher is better, with
   diminishing returns, crossing the benchmark line somewhere. If it does, the
   crossing point is the spec's cadence requirement. **If the surface is jagged
   with an isolated peak at some oddly specific setting, the experiment failed
   and nothing is spec'd from it.**
3. **Structural phase advantages may be recommended; statistical ones may not.**
   Timing sessions to follow the earnings wave is predictable a priori from a
   stable reporting calendar. "The 7th scored highest" is noise.
4. **Two parameters are structurally biased by this corpus and must not be
   decided by it alone:**
   - *Cash reserve* — the backtest has a frozen universe and no Layer 3. It
     cannot represent the opportunity that holding cash is a bet on. Any number
     it produces for a reserve variant is a floor.
   - *Speculative ceiling* — 2021–2026 was mostly rising, so any constraint
     reducing speculative exposure will tend to look expensive. Report 2022
     separately.
5. **Regime-sensitive parameters are reported by sub-period**, not as a single
   five-year number.

### Expected outputs

- **Minimum viable cadence** — "open it every K days, or use the index fund."
- **The price of Step 6** — the gap between per-call and realistic-K cadence is
  what automated transcript ingestion is worth, which sets its build priority.
- **The dollar value of discipline** — the 0%-veto vs capitulation gap.
- **Whether pool-splitting ever mattered** — cash-deployment vs the old
  bucket-target behavior on the same corpus.

---

## 10b. Reproducibility contract — mandatory for every run

Added 2026-08-30 after this session could not reproduce `$287k` at any price. The
cause was not one missing file; it was that **nothing about a result was ever
pinned**. The corpus lived in a gitignored directory on one laptop, the prompt
version was recorded on 41 of 805 rows, the model has since been retired, the
tier inputs are mutable and gitignored, and the code that produced the numbers
sat on an uncommitted branch.

**Rule: a result that has no manifest is not citable.** Not in a spec, not in a
changelog, not as a baseline. If it cannot be regenerated from its manifest, it
is an anecdote.

### Every run emits `<run_id>-manifest.json` beside its outputs

| Field | Why |
|---|---|
| `run_id`, `timestamp_utc` | identity |
| `git_commit`, `git_branch`, `git_dirty` | **`git_dirty: true` invalidates the run for citation.** Commit first. |
| `corpus.source` (`db` \| `file_cache`) | which path produced the events |
| `corpus.created_at_window` | the two-sided v6 bounds actually applied |
| `corpus.universe`, `corpus.event_count`, `corpus.transcript_ids_sha256` | exactly which events |
| `corpus.db_snapshot` + `sha256` | the `pg_dump` this is reproducible against |
| `prompt_version`, `model_version` | inferred from the window where columns are null — record *which* and say so |
| `classification.type_json_sha256` | `type_classifications.json` |
| `classification.tier_source`, `price_cache_sha256`, `fundamentals_cache_sha256` | **tier is recomputed live from mutable, gitignored caches** — the single largest un-pinned input |
| `params.*` | allocator version, window, capital, account split, and every swept knob |
| `params.seeds` | tie-break and any randomized ordering |
| `results.final_value`, `results.max_drawdown`, `results.output_sha256` | what to diff against |

### Standing protections

1. **Commit before citing.** Scratch branches are fine for iterating; a number
   quoted anywhere requires a commit SHA and `git_dirty: false`.
2. **Archive the tier caches.** `price_cache.json` and `fundamentals_cache.json`
   are gitignored, mutable, and frozen at 2026-05-11 only because nobody has
   re-run the fetch scripts. One `fetch_fundamentals.py` away from silently
   changing every tier assignment and every 15%-vs-35% cap. Copy them to a
   dated, backed-up archive and record their checksums in every manifest.
   **Never refresh them to "fix" the staleness warning.**
3. **Snapshot the corpus on any change.** `pg_dump` of `Analysis` / `Transcript`
   / `Ticker` to a path outside the repo, checksum recorded. Verify it restores —
   an unrestored dump is a hope, not a backup.
4. **Stamp `promptVersion` and `modelVersion` on every new Analysis row.** The
   columns exist and are null on 764 of 805. Server-side, never from client input.
5. **Retire nothing silently.** When a model or prompt version changes, the
   results measured under it become historical. Record the discontinuity rather
   than comparing across it.

## 11. Known defects in the validated code path

Both are in `allocator_v3`'s first-call starter and both are in the code that
produced the reference result. Neither has been fixed.

**Starter breaches the tier cap.** On a first call with `Add`, v3 emits the
starter trade and then calls `decide_v2` with the **unmutated** portfolio.
`_decide_add` reads `current_dollars = position_value(ticker)` = 0 and targets
the full cap on top of the starter. An Established Type A first call recommending
35% lands at **8% + 35% = 43%**, over a 35% hard cap. Violates invariant #2.

**Starter and Add are sized against the same stale cash snapshot.** Both read
`portfolio.accounts[...].cash` before either executes. Executed in sequence the
second can raise `InsufficientCash`, be caught, and land in `skipped_events` — a
silent partial fill that reads as a data gap in the report rather than an
allocation failure. Violates invariant #5.

**Unfundable trades fail silently.** When both accounts are dry, the starter and
`_decide_add` return an empty trade list — no exception, no `skipped_events`
entry, no counter. An intended position that never opens is indistinguishable
from one that was never wanted. This corrupts interpretation of every sweep cell,
because a cell can score differently purely from how many trades silently failed.
**Instrumenting this is a prerequisite for the sweep, not a follow-up:** every run
must report cash over time, days at/near zero cash, count of Adds capped by cash
rather than by target gap, and a log of every intended-but-unfunded trade.

**Handling:** baseline runs as-is for comparability; one bug-fixed cell at
baseline settings quantifies the impact; fix after the baseline is banked. The
unfunded-trade instrumentation is additive (counters only, no behavior change)
and goes in before the sweep.

---

## 12. Open items

- **Per-session change limit `X`** — default value pending the sweep.
- **Speculative ceiling level** — pending the baseline exposure diagnostic.
- **Verdict grace window** (§4) — how far past one quarter a stale `Add` stays
  eligible.
- **Duplicate transcripts in the DB.** `FSLR 2024-02-27` exists twice
  (`Transcript` ids 280 and 284, identical title and date) — it is evaluated and
  sized twice on the same day in every run. The manifest also shows 662 entries
  for 659 distinct (ticker, date) pairs, so at least three duplicates exist.
  Needs a dedup pass and a uniqueness constraint on (tickerId, callDate).
- **Ticker renames are destructive and unaudited.** `server/routes/save.js`
  updates `Ticker.symbol` in place with no alias table, no `formerSymbol`
  column, no audit. Nothing distinguishes a same-company rename (FB→META) from
  a ticker reassigned to a different company (RUBI, reused after Rubicon became
  MGNI — both are in `price_cache.json` today). Needs a persisted former-symbol
  trail plus an identity check in the backtest.
- **Reconcile `DESIGN_PRINCIPLES.md` §5**, which still documents the retired
  variable 40–60% Type B cap and a 6-transcript watchlist limit contradicted by
  `CLAUDE.md`.
- **Reconcile `BUILD_STATE.md`** against the live app — the recommendations
  table and per-account positions view are in use but undocumented there.
- **Day-1 convergence study** (§7) — deferred until the all-cash baseline is
  positive.
- **Cap source — needs an explicit decision.** The 2×2 tier matrix
  (15/35/50, what the simulator uses and what this spec assumes), the stored
  `Ticker.capPercent`, or `min()` of those with the analyst's per-call
  `latestAnalysis.capPercent` as production does today. `OwnerTickerConfig`
  overrides apply on top under invariant #4 regardless.
- **Classification drift** — diff `Ticker.type` against
  `type_classifications.json` for all 32 tickers and report disagreements with
  `typeReviewedAt`. Baseline runs on the frozen JSON for reproducibility; one
  sensitivity cell on current `Ticker.type` prices the drift.
- **Verify the corpus backup restores.** A 41 MB dump nobody has restored is a
  hope, not a backup.
- **Corpus preservation belongs in `PROMOTION_GATE.md`.** `promptVersion` /
  `modelVersion` are null on 764 of 805 rows and should be mandatory going
  forward; an eval corpus a validated result depends on needs an archive outside
  the dev database. The 2026-08-30 model retirement is the argument.
- **Correlation-based cohort caps** — see `PORTFOLIO_ANALYST_SPEC.md`,
  *Deferred enhancements*. The speculative ceiling in §6 is an acknowledged
  crude proxy.
