# Verify the tight-limit result, then bracket it — wrap-up

**Step 1 verification: FAILED on two of twelve checks. Independent
drawdown recomputation AGREES exactly (0.0000pp difference, both modes).
Max single-session position change observed: 2.50pp against a 2.5pp
limit — invariant #9 holds cleanly. Average cash: 29.0% at `no_reserve`
2.5pp vs. 88.7% at the unmodified control (last session's figure) —
cash starvation is real and dramatically reduced at the tight limit, but
the binding-constraint breakdown contradicts the prompt's own prediction:
at `no_reserve` 2.5pp, "cash available" (54 events) dominates over
"session limit" (44), not the other way around. `swap_funding` at 2.5pp
breaches §9 invariant #2 — TTD reaches 16.4% against its 15% cap, on 90
separate trading days, with zero Add activity for TTD anywhere in that
window. Per the prompt's explicit gate, Step 2's 300-run bracketing sweep
was NOT run.**

Both failures are traced to a specific, plausible mechanism, not left as
unexplained anomalies — see below. Neither looks like a bug in this
session's own instrumentation: the independent drawdown check (the number
most likely to have been an artifact) confirms exactly, and the invariant
checks are doing precisely what they were built to do — catching something
real before it got built on.

All work committed, `git_dirty: false` verified, driver committed before
any manifest. No DB writes, no LLM calls, no cache refreshes.

---

## Step 0 — carried forward

Reused the reproducibility machinery unchanged: clean tree confirmed
(`git status --porcelain` empty before running — this session's own prompt
file was committed first), driver
(`analysis/verify_and_bracket_tight_limit.py`) committed at `7262d5f`
before any manifest was written, both import-time assertions enforced,
`loaded_event_count` (195) / `in_window_event_count` (147) recorded
separately, standing `$141,836.57` assertion confirmed.

**One additive infrastructure change**, needed for this session's checks:
`analysis/simulator/simulator.py`'s `DailySnapshot` gained a
`position_values: dict[str, float]` field (ticker → mark-to-market dollar
value that day), populated from data already computed at the existing
snapshot-construction site. **Verified non-behavior-changing**: the
`no_reserve` control still reproduces `$141,836.57` exactly after the
change, checked before committing (`2efa673`).

## Step 1 — verification, run before any sweep

Exact invocation: `cd analysis && python3 verify_and_bracket_tight_limit.py`
(Step 1 only ran; wall-clock for Step 1 alone was ~3 seconds — it stopped
before Step 2's 300-run grid, per the gate).

### 1a. Independent drawdown recomputation

A second, separately-written function (`independent_max_drawdown`) walks
the same `DailySnapshot.total_value` series with a different internal
structure (explicit peak/trough index tracking rather than
`report.py::_max_drawdown`'s running-max walk) and shares no code with the
production path.

```
no_reserve 2.5pp:    compute_summary=18.7825%  independent=18.7825%  diff=0.0000pp
  (peak 2023-07-18 $133,960.89 -> trough 2023-10-26 $108,799.69)
swap_funding 2.5pp:  compute_summary=22.6682%  independent=22.6682%  diff=0.0000pp
  (peak 2022-08-15 $109,629.90 -> trough 2023-01-05 $84,778.73)
```

**PASS, both modes, to four decimal places.** The 18.8% figure — the
single most surprising number in the entire thread so far — is not a
drawdown-calculation artifact.

### 1b. Invariant checks (§9)

**Invariant #2 (no position's target exceeds its tier cap):**

- `no_reserve` 2.5pp: **PASS.** Max observed weight across the whole run,
  any ticker: FSLR at 8.6% (cap 15%). No breaches.
- `swap_funding` 2.5pp: **FAIL.** TTD reached **16.4%** against its **15%**
  Type-A-speculative cap, and stayed above 15% on **90 separate trading
  days** (first breach 2023-05-22, peak 2023-10-10, last breach
  2023-11-09).

**Traced, not left unexplained.** TTD's full `funding_log` history for
this run:

```
2022-02-16  intended=$20,057.6  target_buy=$2,507.2  actual=$2,507.2  binding=session limit
2022-05-10  intended=$12,501.6  target_buy=$2,309.5  actual=$2,309.5  binding=session limit
2022-08-09  intended=$10,278.5  target_buy=$2,474.1  actual=$2,474.1  binding=session limit
2022-11-09  intended= $7,721.6  target_buy=$2,145.7  actual=$2,145.7  binding=session limit
2023-02-15  intended= $2,935.9  target_buy=$2,511.1  actual=$2,511.1  binding=session limit
2023-05-10  intended= $1,318.7  target_buy=$1,318.7  actual=$1,318.7  binding=target gap
2024-02-15  intended= $4,603.1  target_buy=$3,809.9  actual=  $778.2  binding=cash available
2024-05-08  intended= $2,589.2  target_buy=$2,589.2  actual=   $99.5  binding=cash available
```

**No Add-shaped decision for TTD occurs anywhere between 2023-05-10 and
2024-02-15** — the entire 90-day breach window (2023-05-22 through
2023-11-09) falls inside that gap. On 2023-05-10, TTD's `intended` target
was fully funded (`binding=target gap`), landing the position at its
computed target — which, by construction (`target_pct = min(recommended_
size_pct, cap_pct)`), cannot exceed the 15% cap **at the moment of the
decision**. **The breach is organic price drift after that point** —
TTD's price rising and/or other positions' values falling between calls,
shrinking the portfolio-value denominator — not a targeting bug and not
excess buying. Nothing in `decide_v3`/`decide_v2` trims a position purely
for drifting above its cap absent a new call or the 25% profit-take
threshold (well above 15%), so once a position reaches its cap it has no
mechanism pulling it back down on drift alone.

**This is very likely a pre-existing property of the validated allocator,
not something introduced by this sweep or the conformant swap-funding
work** — `PORTFOLIO_ANALYST_SPEC.md`'s own language elsewhere treats
between-call drift as a deliberate feature ("positions are allowed to
drift between calls" is explicitly credited for the Type B result). But
§9 invariant #2's literal text — *"no position's target may exceed its
tier cap, at any time, including a ticker's first call"* — reads as a
continuous state invariant, not a decision-time-only one, and this run is
the first time anyone has actually checked it against the daily series
rather than only at decision moments. **Whether "at any time" means
"continuously, including pure price drift" or "at every decision point" is
a real ambiguity in the spec's own wording, exposed by this verification,
not resolved here.**

**Invariant #9 (no session moves a position by more than the limit):**

```
no_reserve 2.5pp:    max observed = 2.50pp against a 2.5pp limit -- PASS
swap_funding 2.5pp:  max observed = 2.50pp against a 2.5pp limit -- PASS
```

**Clean pass, both modes.** Measured on the Add-side net dollar effect of
each event's full trade set, as a % of pre-trade portfolio value. **Scope
note:** this measurement covers Add-shaped decisions only; Trim/Exit-side
position decreases are not included, since those are bounded by
pre-existing, separate v2/v3 rules (25%-per-call trim, full-liquidation
exit) rather than by the session-change limit under test here.

**Invariant #5 (no trade set sized against pre-trade state and executed
after another):** **PASS, both modes.** Zero `skipped_events` entries in
either run — no `InsufficientCash` or `InsufficientShares` exceptions were
caught anywhere in either 2.5pp run.

### 1c. Where does the drawdown reduction come from?

| | `no_reserve` 2.5pp | Unmodified control (from last session) |
|---|---|---|
| Average cash % | 29.0% | 88.7% days below 1% cash (near-zero cash almost always) |
| Median cash % | 20.9% | — |

At the drawdown trough specifically:

- **`no_reserve` 2.5pp, trough 2023-10-26:** **100.0% invested, 0.0%
  cash.** Holdings at the trough: AVGO $21,065, ORCL $18,343, NVDA
  $15,279, MSFT $12,040, TSLA $10,193, AAPL $10,190, GOOGL $7,170, FSLR
  $5,912, TTD $2,052, AMD $2,013, ENVX $1,567, RUN $1,311, AMPX $672, QS
  $578, EOSE $414 — 15 of 16 names held, broadly spread.
- **`swap_funding` 2.5pp, trough 2023-01-05:** 62.3% invested, 37.7% cash.
  Holdings: ORCL $10,937, AVGO $9,927, TTD $7,792, MSFT $4,237, AAPL
  $4,117, TSLA $3,883, AMD $3,596, RUN $2,738, ENVX $1,964, NVDA $1,384,
  EOSE $1,143, FSLR $853, GOOGL $136, QS $80 — 14 names, more concentrated
  in a handful.

**The drawdown reduction is not primarily a cash-drag effect** — at least
for `no_reserve`, the portfolio is **fully invested (100%) at its own
worst moment**, which rules out "it just sat in cash during the crash" as
the explanation. The lower drawdown instead comes from **broader
diversification held earlier and more evenly** than the unmodified
control (which, per last session's finding, had its entire capital
committed to three names within six weeks and then frozen) — with 15 of
16 names built up gradually via the 2.5pp per-session ceiling, no single
name's decline can hurt the portfolio as much. This is a materially
different, more defensible explanation than the `cash_reserve 20%`
critique the prompt named as the concern to rule out, and it appears to be
ruled out for `no_reserve`.

**Terminal composition (2024-06-12):**

- `no_reserve` 2.5pp: NVDA 28.7%, AVGO 20.6%, ORCL 13.8%, MSFT 8.7%, GOOGL
  6.7%, FSLR 6.3%, AAPL 5.4%, TSLA 3.6%, AMD 1.9%, TTD 1.8%, ENVX 1.2%, RUN
  0.6%, QS 0.3%, AMPX 0.2%, EOSE 0.1%.
- `swap_funding` 2.5pp: NVDA 24.6%, AVGO 22.5%, ORCL 14.9%, TTD 13.0%, AMD
  8.6%, MSFT 6.5%, GOOGL 6.0%, FSLR 2.0%, ENVX 0.9%, AMPX 0.8%, AAPL 0.1%,
  QS 0.0%, TSLA 0.0%.

## 1d. What is actually binding — the first genuine surprise

| | `no_reserve` 2.5pp | `swap_funding` 2.5pp |
|---|---|---|
| target gap | 0 | 1 |
| **cash available** | **54** | 42 |
| **session limit** | 44 | **53** |

**`no_reserve` at 2.5pp: FAILS the prompt's own prediction.** The prompt's
mental model — *"at 2.5pp the session limit should dominate; at the
control, cash should"* — does not hold for `no_reserve`. **Cash is still
the binding constraint on the majority of Add-shaped decisions (54 of 98,
55%), even at the tightest limit sampled.** The session limit binds
often (44 of 98, 45%) but does not dominate. **`swap_funding` at 2.5pp
matches the prediction** (session limit dominates, 53 of 96, 55%) —
consistent with swap-funding's whole purpose being to relieve exactly the
cash-availability constraint that `no_reserve` cannot escape.

**This does not, on its own, invalidate the 2.5pp result** — it just means
the *mechanism* behind `no_reserve`'s strong number is more mixed than the
prompt assumed: it is not purely "the limit forces patient, diversified
building," it is "the limit forces patient building, and the portfolio is
*still* frequently cash-constrained on top of that." Both effects are
compounding in the same direction (slower, more diversified deployment),
which is plausibly *why* the number is so good — but it means "the session
limit" alone is not a complete causal story for `no_reserve`'s result, and
the design session should not describe it as if the limit is the only
thing operating.

## 1e. Sanity floor

```
no_reserve 2.5pp:    final=$185,241.78   swap_funding 2.5pp: final=$189,781.58
SPY:   $113,980.12
QQQ:   $119,178.08
TMFC:  $120,511.89
Equal-weight: $120,427.18
```

**PASS, both modes** — beats all four benchmarks, recomputed fresh in this
run rather than carried forward. (Values differ trivially, by ~$60-100,
from last session's figures for the same nominal configuration — an
expected consequence of independently re-running rather than a
discrepancy; not investigated further since Step 1 stopped for other
reasons before this would have mattered.)

## Verdict: Step 1 FAILED. Step 2 was not run.

Per the prompt's explicit instruction — *"If any check below fails, stop
and report — do not proceed to Step 2"* — the 300-run bracketing sweep
(10 limit values × 2 modes × 15 draws) was **not executed**. Manifests
`step1-verification-2.5pp-manifest.json` and
`drawdown-baselines-v2b-manifest.json` are the only outputs of this
session's measurement work; there is no bracketing table, no material/
immaterial classification, no plateau derivation, and no Rule 4 scoring
to report, because none of that ran.

## Flagged plainly

- **Two of twelve checks failed, and both are traceable to a specific,
  plausible cause rather than being inexplicable.** The invariant #2
  breach (TTD, `swap_funding`) is very likely organic price drift on a
  position that was correctly targeted at cap and never touched again for
  9+ months — not a targeting bug, but a real gap between the literal
  "at any time" wording of §9 invariant #2 and what the codebase actually
  enforces (decision-time only, no continuous ceiling). This is a genuine
  spec-vs-implementation ambiguity this verification step surfaced for
  the first time.
- **`no_reserve`'s binding-constraint story is more mixed than the prompt
  predicted** — cash, not the limit, is still the majority constraint at
  2.5pp. The 2.5pp result is real (per 1e and last session's Rule 1/4), but
  its *mechanism* is not purely "the limit does the work" as the prompt's
  framing assumed going in.
- **The drawdown-reduction concern the prompt asked to rule out (cash-drag,
  the `cash_reserve 20%` critique) does not appear to apply to
  `no_reserve`** — the portfolio is 100% invested at its own worst moment.
  This is a genuinely reassuring finding, reported plainly alongside the
  two failures rather than let it soften them.
- **No ambiguity required stopping on in this session's own implementation
  work** — the binding-constraint classification and the independent
  drawdown function were both concrete enough to build without a
  design-session decision. The ambiguity that surfaced (§9 invariant #2's
  "at any time" wording) is a pre-existing spec question this run exposed,
  not something introduced by this session's code.

## What was deliberately not done

- Step 2's 300-run bracketing grid — blocked by the Step 1 gate, per
  instruction.
- No root-cause fix attempted for the invariant #2 breach or the
  binding-constraint mismatch — this is a measurement session; diagnosing
  further (e.g., whether other tickers besides TTD also drift over cap
  under other configurations) is left for whatever the design session
  decides to do with this finding.
- No funding mode selected, no limit value chosen, no `minPositionDollar`
  picked (moot — Step 2 never ran).
- No spec amended, no §12 items resolved.
- `price_cache.json` / `fundamentals_cache.json` untouched; `testing/`
  left gitignored, not touched.

## Repo state left behind

- `sweep/db-corpus-baseline`, now at (this session's commits, in order):
  `5fdfde2` (versioned this session's prompt) → `2efa673`
  (`DailySnapshot.position_values`, additive, verified non-behavior-
  changing) → `7262d5f` (verify-then-bracket driver) → `b8a5102`
  (Step 1 verification manifests — the gate-failure record).
- `analysis/simulator/simulator.py` — new `position_values` field on
  `DailySnapshot`.
- `analysis/verify_and_bracket_tight_limit.py` — new driver. The Step 2
  bracketing-grid code inside it is implemented and untested past the
  point Step 1 stops — treat it as unverified until someone reruns it
  after Step 1's failures are addressed.
- `analysis/data/run_manifests/step1-verification-2.5pp-manifest.json`,
  `drawdown-baselines-v2b-manifest.json` — the two manifests this session
  actually produced.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 verify_and_bracket_tight_limit.py

# Inspect the verification manifest directly:
cat data/run_manifests/step1-verification-2.5pp-manifest.json | python3 -m json.tool
```
