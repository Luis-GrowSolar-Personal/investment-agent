# Session limit as the proven axis — and swap-funding's first fair test — wrap-up

**Conformant swap-funding vs. control: PASSES Rule 1 — median $155,377 vs.
A's max $154,398, by $979. Against `no_reserve` at the same 10pp limit:
SEPARABLE under Rule 2 — the ranges do not overlap ($171,919–$189,528 vs.
$141,598–$160,219); `no_reserve`+10pp wins outright. Session-limit surface:
JAGGED for `no_reserve` (isolated peak at 10pp — off=$141,837, 10pp=
$189,134, 15pp=$167,172, 20pp=$140,201 — not monotone; per Rule 3, nothing
is spec'd from this axis in `no_reserve`), smoother for conformant
swap-funding. Corrected displacement gain (sale-attributed, conformant
10pp cell): **-$19,924**, of which **-$9,003 on `Hold` donors**. Cells
passing the 38.0% bar: `D` (conformant `swap_funding`+10pp) only.**

**All work committed. `git_dirty: false` on every manifest this session —
Step 0's hard stop-gate was met for real, not argued around.** No DB
writes, no LLM calls, no cache refreshes.

---

## Step 0 — reproducibility, met this time

### 0a. Tree cleaned before running

The dirt was `CLAUDE.md` (modified) plus untracked `server/scripts/*.js`
and `testing/` (the latter contains real personal account CSVs — Andrea's
and Eduardo's custodial/Roth positions — definitely not something to
commit). **Stashed, not committed**, since none of it was mine to decide to
commit on the user's behalf:

```zsh
git stash push --include-untracked -- CLAUDE.md server/scripts testing
```

Also committed this session's own prompt file and the prior session's
wrap-up (both pending from before), since untracked files count toward
`git status --porcelain` too. Result: `git status --porcelain` returned
**zero lines** before any measurement code ran. **The stash was popped back
at the end of this session**, once all measurement and manifest-generation
was complete — the user's pre-existing, unrelated work is exactly as they
left it.

### 0b. Driver pinned, not its predecessor

New driver `analysis/sweep_session_limit_and_conformant_swap.py` is
**committed before any manifest is written** (`3de4fa4`, later `0b77a49`
after one in-session bugfix — see below). The manifest writer calls
`git cat-file -e <HEAD>:analysis/sweep_session_limit_and_conformant_swap.py`
and raises if it's absent, and separately raises if `git status --porcelain`
is non-empty — both checked at import time, before a single simulation
runs. **Verified: every manifest this session records `git_commit: 0b77a49`,
`git_dirty: false`, and `driver_file` pointing at the actual script that
produced it** — the exact defect named in this prompt (`82a8053` on all
fourteen prior manifests despite the driver landing at `2733c0c`) cannot
recur with this guard in place.

One in-session correction worth naming: my first version of Step 3's stop-
gate wrongly returned early on a bar mismatch, skipping Step 2's entire
56-run grid. Caught by inspecting the output (21 lines instead of the
expected ~150), fixed, re-committed (`0b77a49`), re-run. The corrected
version reports the mismatch but still runs Step 2 and still scores against
the existing 38.0% bar, per Step 3's own final, unconditional sentence.

### 0c. Event-count labeling fixed

`corpus.event_count` is now two separate, separately-hashed fields in every
manifest: `loaded_event_count` (195, the full pre-window load) and
`in_window_event_count` (147, what actually trades). No more silent
same-field-name collision between sessions.

### 0d. Standing assertion

```
no_reserve control: $141,836.57
Standing assertion PASSED.
```

## Step 1 — displacement attribution fixed, before measuring anything

`RealizedSale` (`analysis/simulator/accounts.py`) gained a `reason: Optional[str] = None`
field, threaded from `Trade.reason` (already present) through `execute_sell`:

```python
sales.append(RealizedSale(
    ...
    realized_gain=proceeds - cost_basis_total,
    reason=trade.reason,
    is_long_term=holding_days >= 365,
    ...
))
```

**Stop-gate verified: additive, non-behavior-changing.** Both
`sweep_funding_modes.py` and `session_limit_and_donor_probe.py` (last
session's drivers) still reproduce `$141,837` exactly after this change,
confirmed by re-running both before writing a single new line of measurement
code.

### The previously published numbers are superseded

**`-$32,679` (old cell 6) and `-$24,950` (old cell 7) are wrong and are
retracted, not silently replaced.** Both summed realized gains for *any*
sale on a ticker that was *ever* a donor — including that ticker's own
ordinary Trim/Exit sales, unrelated to displacement. With `reason`-based
attribution:

| | Old (ticker-filtered, non-conformant per-event cap) | New (sale-attributed, conformant per-date cap) | Delta |
|---|---|---|---|
| `swap_funding`, no limit | -$32,679 | **-$23,804** | +$8,875 |
| `swap_funding` + 10pp | -$24,950 | **-$19,924** (this is cell `D`) | +$5,026 |

**These deltas conflate two independent fixes made together and cannot be
cleanly separated**: the attribution fix (excluding ordinary Trim/Exit
gains on ex-donor tickers) *and* the conformant per-date trim cap (which
changes displacement count and which specific sales occur) both changed
between the old and new figures. Reporting this plainly rather than
implying the delta isolates one cause.

**New, correctly separated per §5** for the conformant 10pp cell (`D`):

- Displacement (sale-attributed) realized gain: **-$19,924**
- Of which, on `Hold`-verdict donors specifically: **-$9,003**
- Ordinary Trim/Exit realized gain (same run, same window): **+$9,726**

The sign split is worth sitting with: **swap-funding is realizing losses
while ordinary Trim/Exit activity in the same portfolio is realizing
gains.** Displacement is not harvesting winners; it's a distinct, worse-
performing sub-population of sales.

**Caveat on the Hold-donor gain split's matching method:** `RealizedSale`
doesn't carry a direct back-reference to which `displacement_log` entry
produced it, so the split matches by `(sale_date, ticker)`. This is exact
when a donor is drawn on at most once per date (true under the now-
mandatory per-date cap, by construction — a donor's cumulative trim for a
date is computed and applied as one `_build_sell_trades` call sequence
tagged to one `displacement_log` entry), so the caveat is more a
methodology note than an open uncertainty here.

## Step 2 — the session-limit sweep, properly

Exact invocation: `cd analysis && python3 sweep_session_limit_and_conformant_swap.py`.
**Wall-clock runtime for the full 56-run grid (plus setup, benchmark
computation, and scoring): 9.2 seconds.** Sizing note for the next sweep:
this corpus/window is cheap enough that a much larger grid (more limit
values, more seeds, more funding-mode variants) costs single-digit minutes,
not hours.

**Swap-funding now always uses the per-date trim cap.** The per-event
version from two sessions ago is retired, not offered as a toggle — §5 says
"per session," and the per-event version was measurably non-conformant
(`diagnose-session-limit-and-donor-rule-out.md`, Step 2c).

### Full 8×7 grid

| Config | forward | reversed | seed1 | seed2 | seed3 | seed4 | seed5 | min | median | max | spread (% median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** `no_reserve` off | $141,837 | $117,455 | $138,070 | $141,096 | $154,398 | $136,553 | $135,732 | $117,455 | $138,070 | $154,398 | 26.8% |
| **C** `no_reserve` 10pp | $189,134 | $171,919 | $179,666 | $176,952 | $189,528 | $176,758 | $183,420 | $171,919 | $179,666 | $189,528 | 9.8% |
| `no_reserve` 15pp | $167,172 | $133,768 | $157,403 | $166,937 | $143,044 | $156,854 | $166,374 | $133,768 | $157,403 | $167,172 | 21.2% |
| `no_reserve` 20pp | $140,201 | $122,688 | $131,610 | $142,330 | $145,593 | $127,151 | $139,959 | $122,688 | $139,959 | $145,593 | 16.4% |
| **D** `swap_funding` 10pp (conformant) | $160,219 | $141,598 | $144,963 | $158,432 | $157,433 | $146,038 | $155,377 | $141,598 | $155,377 | $160,219 | 12.0% |
| `swap_funding` 15pp | $158,058 | $133,521 | $134,257 | $153,199 | $154,777 | $138,572 | $150,753 | $133,521 | $150,753 | $158,058 | 16.3% |
| `swap_funding` 20pp | $155,800 | $137,312 | $134,916 | $153,892 | $155,281 | $153,058 | $154,023 | $134,916 | $153,892 | $155,800 | 13.6% |
| `swap_funding` off | $160,122 | $135,084 | $135,221 | $158,374 | $157,108 | $141,274 | $155,878 | $135,084 | $155,878 | $160,122 | 16.1% |

### Funding diagnostics (forward draw), per configuration

| Config | Max DD | Cash<1% days | Adds funded/partial/unfunded | Shortfall | Distinct tickers | Displacements |
|---|---|---|---|---|---|---|
| A | 45.6% | 88.7% | 4/20/74 of 98 | $2,351,360 | 12 | 0 |
| C | 39.5% | 77.6% | 13/18/67 of 98 | $831,310 | 15 | 0 |
| no_reserve 15pp | 46.4% | 85.2% | 7/16/75 of 98 | $1,238,816 | 14 | 0 |
| no_reserve 20pp | 46.0% | 89.3% | 7/19/72 of 98 | $1,491,489 | 13 | 0 |
| **D** | **38.0%** | 83.6% | 14/67/11 of 92 | $639,967 | 15 | 358 |
| swap_funding 15pp | 42.0% | 91.4% | 9/72/12 of 93 | $1,020,836 | 15 | 371 |
| swap_funding 20pp | 43.0% | 94.4% | 6/65/21 of 92 | $1,331,967 | 14 | 203 |
| swap_funding off | 45.6% | 92.8% | 2/57/32 of 91 | $2,453,260 | 14 | 167 |

### Donor position-size distribution (share of draws leaving the donor below threshold, forward draw)

| Config | Below 2% | Below 1% | Below 0.5% |
|---|---|---|---|
| **D** | 304/358 (84.9%) | 266/358 (74.3%) | 233/358 (65.1%) |
| swap_funding 15pp | 314/371 (84.6%) | 283/371 (76.3%) | 254/371 (68.5%) |
| swap_funding 20pp | 148/203 (72.9%) | 126/203 (62.1%) | 105/203 (51.7%) |
| swap_funding off | 119/167 (71.3%) | 98/167 (58.7%) | 83/167 (49.7%) |

**The per-date cap did not deliver the reduction the prompt anticipated.**
The prompt stated: *"The per-date cap should reduce the grinding the
previous run found (≈7 in 10 draws left the donor below 1%)."* At the same
10pp limit, the prior (non-conformant, per-event) run measured 77.9% of
draws below 1%; the conformant per-date-capped run measures **74.3%** —
a real but modest reduction (3.6pp), not the meaningfully different picture
the framing implied. **Flagging this directly rather than describing a
small change as validating the expectation.** The design session's
`minPositionDollar` question is essentially unchanged by this fix: whatever
floor gets chosen, most draws still land well under 1%.

## Pre-declared rules, applied mechanically

**Rule 1 — beats the control?**

> A configuration's return advantage over A counts as real only if its
> median across draws exceeds A's maximum across draws.

- **C vs. A: median $179,666 > A's max $154,398 → REAL**, by a wide margin
  (the same finding as last session, now re-confirmed inside the fuller
  grid).
- **D vs. A: median $155,377 > A's max $154,398 → REAL**, but **by only
  $979** — a razor-thin margin against a rule with a hard threshold. This
  is the uncomfortable-but-mechanical answer: conformant swap-funding
  technically clears the bar, on a margin so thin that a single different
  seed could plausibly have flipped it. **Not softened, not re-argued** —
  reported exactly as the rule renders it, with the margin stated so the
  design session can judge its own confidence in it.

**Rule 2 — separating two configs that both pass Rule 1:**

> Two configurations are separable on return only if their seven-draw
> ranges do not overlap. If the ranges overlap, they are tied.

**C's range ($171,919–$189,528) and D's range ($141,598–$160,219) do not
overlap. SEPARABLE — `no_reserve`+10pp wins outright on return over
conformant `swap_funding`+10pp**, at the identical limit value. This
resolves a question the prior two sessions left open: swap-funding's
diagnostics story (funds far more Adds, holds more tickers, zeroes out
fewer positions) does not translate into a superior return at the matched
limit — the plain session limit, with no funding mechanism at all, returns
more, every single draw, than the conformant swap-funding version does at
its best draw.

**Rule 3 — the shape of the limit surface, per §10 rule 2's "the finding is
the shape, not the argmax":**

```
no_reserve:    off=$141,837   10pp=$189,134   15pp=$167,172   20pp=$140,201
swap_funding:  off=$160,122   10pp=$160,219   15pp=$158,058   20pp=$155,800
```

**`no_reserve`'s surface is jagged with an isolated peak at 10pp — not
monotone, not smooth.** It rises sharply from $141,837 (off) to $189,134
(10pp), then falls back through $167,172 (15pp) to $140,201 (20pp) —
essentially back to the unmodified baseline. **Per the pre-declared rule,
this means the experiment failed at this axis and nothing is spec'd from
it — including the specific value 10pp.** This directly qualifies last
session's finding: config C's return advantage over the *unmodified
control* survived Rule 1 (it's not arrival-order noise *relative to no
limit at all*), but the *shape* of the limit axis itself gives no basis for
recommending 10pp over any other value — the same axis that produces
$189,134 at 10pp produces $140,201 at 20pp, a swing of $49k on a single
10-percentage-point change with no trend connecting the two. **Treat "10pp
is real" and "10pp is the right value" as two different claims — this run
supports the first and actively undermines the second.**

**`swap_funding`'s surface is smoother**: $160,122 (off) → $160,219 (10pp,
essentially flat) → $158,058 (15pp) → $155,800 (20pp) — a mild, gently
declining shape with no isolated spike. This is a case where the
diagnostics-favored mode (swap-funding) also produces the more
*interpretable* sweep surface, even though it loses on raw return per Rule 2.

## Step 3 — the drawdown bar, re-derived once and pinned

```
SPY:          final=$113,980.12  maxDD=25.36%
QQQ:          final=$119,178.08  maxDD=35.25%
TMFC:         final=$120,511.89  maxDD=32.99%
Equal-weight: final=$120,427.18  maxDD=42.76%

Median of the four drawdowns: 34.12%
Re-derived bar (median + 5pp): 39.12%
Inherited bar (three sessions): 38.00%
```

**MISMATCH: 39.12% ≠ 38.0%.** Per the stop-gate's precise instruction, this
did **not** trigger adopting the new figure or re-scoring against it — both
numbers are reported here, unresolved, and every cell below is still scored
against the **existing, unchanged 38.0% bar**, exactly as Step 3's own
final sentence requires. **The design session decides which figure stands.**
One observation, not a resolution: **equal-weight-of-universe's own
drawdown (42.76%) is the largest of the four inputs** and pulls the median
up — if a prior session computed "38.0%" from only SPY/QQQ/TMFC (excluding
equal-weight, which — per this session's own recon — may never have had its
drawdown series actually built before now), that would mechanically explain
a chunk of the 1.12pp gap. Not confirmed here; flagged as the most likely
explanation for the design session to check.

## Full scoring, all eight configs against the existing 38.0% bar

| Config | Final | Max DD | Beats | Score |
|---|---|---|---|---|
| A (`no_reserve`, off) | $141,837 | 45.6% | SPY,QQQ,TMFC | FAIL (DD) |
| C (`no_reserve`, 10pp) | $189,134 | 39.5% | SPY,QQQ,TMFC | FAIL (DD) |
| `no_reserve` 15pp | $167,172 | 46.4% | SPY,QQQ,TMFC | FAIL (DD) |
| `no_reserve` 20pp | $140,201 | 46.0% | SPY,QQQ,TMFC | FAIL (DD) |
| **D** (`swap_funding`, 10pp, conformant) | $160,219 | **38.0%** | SPY,QQQ,TMFC | **PASS** |
| `swap_funding` 15pp | $158,058 | 42.0% | SPY,QQQ,TMFC | FAIL (DD) |
| `swap_funding` 20pp | $155,800 | 43.0% | SPY,QQQ,TMFC | FAIL (DD) |
| `swap_funding` off | $160,122 | 45.6% | SPY,QQQ,TMFC | FAIL (DD) |

**Only `D` passes, and it passes by landing exactly on the bar (38.0% vs.
a 38.0% ceiling) off a single, un-seeded forward draw.** Every config beats
all three named benchmarks on return — as in every prior sweep, drawdown is
the only thing separating PASS from FAIL. **`D`'s pass is fragile in a way
the table alone doesn't show**: its own seven-draw max drawdown was not
computed here (only the forward draw was scored, per the prompt's scoring
instruction), so whether `D` clears 38.0% on its *other* six draws is
unknown — flagging this rather than implying the pass is robust across
seeds.

## Flagged plainly

- **Rule 1's verdict for `D` is real but wafer-thin** ($979 of margin on a
  hard threshold) — reported exactly as the rule renders it, not softened.
- **Rule 3 undermines "10pp" as a value, even though it does not undermine
  "the limit helps" as a direction** — the two most important sentences in
  this report are adjacent and easy to conflate; kept them separate above
  on purpose.
- **The per-date cap's improvement to donor grinding was real but smaller
  than the prompt anticipated** (77.9%→74.3% below 1%, not a qualitative
  change) — reported factually rather than rounded up to match the framing.
- **The re-derived drawdown bar disagrees with the inherited one by
  1.12pp**, most plausibly because equal-weight's own drawdown was never
  computed in whatever produced "38.0%" originally — not confirmed, flagged
  for the design session to check against its own records.
- **Two previously published numbers (-$32,679, -$24,950) are wrong and
  are superseded here**, not silently replaced — see Step 1.
- **No ambiguity required stopping on** in this session's implementation
  work — the driver, the reason-field threading, and the per-date cap were
  all mechanically specified enough to build without a design-session
  decision.

## What was deliberately not done

- No funding mode selected, no session-limit value chosen, no
  `minPositionDollar` picked.
- No spec amended; §12 items untouched; cadence/scope/veto sweep not started.
- The re-derived 39.12% drawdown bar was **not adopted** and **no cell was
  scored against it** — every score above uses the existing 38.0%.
- `D`'s (or any config's) seven-draw drawdown distribution was not computed
  — only the forward draw's drawdown was scored, matching the prompt's
  explicit scoring instruction; flagged above as an open question about
  `D`'s pass's robustness.
- Per-sale Hold-vs-Trim/Exit gain attribution required a `(date, ticker)`
  match rather than a direct id reference (see Step 1's caveat) — not
  built further given the per-date cap makes it exact in practice.

## Repo state left behind

- `sweep/db-corpus-baseline`, now at commit (after this session's work):
  guard-fix (`82a8053`, prior session) → `2733c0c` (prior session) →
  `6f8c1ad` (versioned this session's prompt + prior wrap-up) → `7dbc58a`
  (`RealizedSale.reason`, additive) → `3de4fa4` (driver committed before
  any manifest) → `0b77a49` (fixed the Step 3 early-return bug) →
  `234f46c` (nine grid manifests, all `git_dirty: false`).
- `analysis/simulator/accounts.py` — `RealizedSale.reason` field, additive.
- `analysis/sweep_session_limit_and_conformant_swap.py` — new driver.
- `analysis/data/run_manifests/step2-*.json`, `step3-drawdown-baselines-manifest.json`
  — nine new, fully citable manifests.
- **The user's pre-existing, unrelated working-tree changes (`CLAUDE.md`,
  `server/scripts/*.js`, `testing/`) were stashed for this run and popped
  back at the end** — exactly as they were before this session started.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 sweep_session_limit_and_conformant_swap.py

# Inspect any manifest:
cat data/run_manifests/step2-D-manifest.json | python3 -m json.tool

# Confirm git_dirty:false and the correct driver commit on every manifest
# from this session:
for f in data/run_manifests/step2-*.json data/run_manifests/step3-drawdown-baselines-manifest.json; do
  python3 -c "import json,sys; m=json.load(open('$f')); print('$f', m['git_commit'][:12], m['git_dirty'])"
done
```
