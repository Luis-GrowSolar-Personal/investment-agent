# Three modes on equal footing — bracket the limit axis — wrap-up

**Gates: all five passed, on all nine gate configurations (3 modes × off /
0.5pp / 10pp). Anchors reproduce: YES, exactly (0.000000 diff on all
four). §11 defect #2's "cost" is not a cost at all — it is not
monotone, does not converge to zero, and at `off` it's actually
*negative*: "fixing" it drops the median from $139,355 to $114,620
(**-17.7%**), the only FAIL-on-return cell in the entire 30-configuration
Rule 4 table. Limit surface per mode: JAGGED for all three (7–8 of 9
first-differences material in every mode) — no plateau anywhere on this
denser, 10-point axis either. Robustly passing the 38.0% bar: 24 of 30
configurations (every limit from 0.5pp through 5pp, all three modes;
`off` and `10pp` fail on drawdown in all three modes except
`no_reserve_s11fixed`/`off`, which fails on return instead). Best of each
mode, pairwise: `swap_funding` (3pp, $197,437) > `no_reserve_raw` (3pp,
$189,322) > `no_reserve_s11fixed` (2.5pp, $183,629) — SEPARABLE on both
return and drawdown, all three pairs, no ties. Cap drift: largest excess
+12.3pp, MSFT against its 50% cap, appearing identically under
`swap_funding`/`off` and `no_reserve_s11fixed`/`off` — the same
mechanism, not two.**

Wall-clock for the full 450-run grid: **71.8 seconds.**

---

## Step 0 — carried forward, unchanged

Clean tree confirmed before running, driver
(`analysis/bracket_three_modes_s11_corrected.py`) committed at `77b541a`
before any manifest, both import-time assertions enforced, event counts
recorded separately (195 loaded / 147 in-window).

## The standing principle this session enforces

*"No gate may test a condition that §11 documents as a known unfixed
defect. Known defects are measured and reported, never used to stop a
run."* Gate 2 (decision-time target vs. cap) and the corrected Gate 4
(skipped events, classified) both honor this. **Confirmed empirically**:
Gate 2 passes on all 9 configurations at `0.0000pp` excess, and every one
of the 10 `no_reserve_raw` `off`/`10pp` `skipped_events` this session
classifies cleanly as `known_s11_concatenation` (6 at `off`, 3 at `10pp`)
— zero `other`/unexplained skips anywhere in the gate configurations.

## Step 1 — the five gates, all passed

Exact invocation: `cd analysis && python3 bracket_three_modes_s11_corrected.py`.

| Config | Gate 2 | Gate 3 | Gate 4 (known-§11 / other) | Gate 5 |
|---|---|---|---|---|
| no_reserve_raw, off | PASS (0.0000pp) | PASS (58.00pp, uncapped) | PASS (6 / 0) | PASS (45.5945% both) |
| no_reserve_raw, 0.5pp | PASS | PASS (0.50pp) | PASS (0 / 0) | PASS (5.6302%) |
| no_reserve_raw, 10pp | PASS | PASS (10.00pp) | PASS (3 / 0) | PASS (39.5323%) |
| no_reserve_s11fixed, off | PASS | PASS (58.00pp) | PASS (0 / 0) | PASS (45.5800%) |
| no_reserve_s11fixed, 0.5pp | PASS | PASS (0.50pp) | PASS (0 / 0) | PASS (8.3746%) |
| no_reserve_s11fixed, 10pp | PASS | PASS (10.00pp) | PASS (0 / 0) | PASS (38.9751%) |
| swap_funding, off | PASS | PASS (58.00pp) | PASS (0 / 0) | PASS (45.5943%) |
| swap_funding, 0.5pp | PASS | PASS (0.50pp) | PASS (0 / 0) | PASS (6.9613%) |
| swap_funding, 10pp | PASS | PASS (10.00pp) | PASS (0 / 0) | PASS (37.9667%) |

**No gate failed.** `no_reserve_s11fixed` and `swap_funding` never
produce a `skipped_events` entry at all in any gate configuration —
consistent with both sharing the same live-cash buy-leg rebuild.
`no_reserve_raw`'s 9 total skips across `off`/`10pp` are the same ones
identified two sessions ago, now formally classified rather than merely
observed.

**Diagnostics from the gate configurations (never gates, reported for
context):** binding-constraint counts and cap drift matched what the
prior session found at these same three points — carried forward without
re-deriving, superseded by the full census below.

## Step 2 — three modes on equal footing

`no_reserve_s11fixed` calls the **exact same `_rebuild_buy_leg()`
function** `swap_funding` calls for its own buy leg — same account-order
draining (`tax_advantaged` → `taxable`), same "live cash + this event's
raised amount" accounting, same code path, literally the same Python
function, called with `raised_by_account` fixed at zero (no donor
selling). **Confirmed by construction**, not just asserted: both modes'
implementations invoke `_rebuild_buy_leg(...)` in `bracket_three_modes_
s11_corrected.py`, and the function is defined once, module-level, shared.

## Step 3 — the grid: 450 runs, 71.8 seconds

10 limit values × 3 modes × 15 draws (forward, reversed, seeds 1–13).

### Anchor reproduction (exact, no tolerance)

```
no_reserve_raw  off:  prior $139,354.628764  this run $139,354.628764  diff $0.000000  MATCH
no_reserve_raw  10pp: prior $179,605.326944  this run $179,605.326944  diff $0.000000  MATCH
swap_funding    off:  prior $155,877.751721  this run $155,877.751721  diff $0.000000  MATCH
swap_funding    10pp: prior $156,231.062467  this run $156,231.062467  diff $0.000000  MATCH
```

**All four anchors reproduce to the last recorded digit.** This grid is
directly comparable to `sweep-limit-axis-dense-out.md`'s.

### Full 30-configuration table (final value)

| Limit | no_reserve_raw median | no_reserve_s11fixed median | swap_funding median |
|---|---|---|---|
| off | $139,355 | $114,620 | $155,878 |
| 0.5 | $123,677 | $126,982 | $123,277 |
| 1 | $148,069 | $154,884 | $147,297 |
| 1.5 | $167,712 | $168,090 | $165,226 |
| 2 | $176,655 | $178,827 | $177,907 |
| 2.5 | $185,180 | $183,629 | $190,481 |
| 3 | **$189,322** | $177,048 | **$197,437** |
| 4 | $183,591 | $175,575 | $188,915 |
| 5 | $183,707 | $179,093 | $179,209 |
| 10 | $179,605 | $165,272 | $156,231 |

`no_reserve_s11fixed`'s own peak is **2.5pp, $183,629** — the highest
value in its column.

### Full 30-configuration table (max drawdown, median across 15 draws)

| Limit | no_reserve_raw | no_reserve_s11fixed | swap_funding |
|---|---|---|---|
| off | 45.3% | 46.4% | 47.8% |
| 0.5 | 5.6% | 8.4% | 7.0% |
| 1 | 10.6% | 15.5% | 13.0% |
| 1.5 | 15.1% | 21.6% | 18.4% |
| 2 | 19.1% | 22.6% | 22.2% |
| 2.5 | 18.8% | 25.6% | 22.7% |
| 3 | 21.1% | 29.9% | 26.6% |
| 4 | 27.6% | 34.1% | 33.2% |
| 5 | 31.7% | 34.0% | 35.3% |
| 10 | 39.5% | 39.0% | 38.8% |

**`no_reserve_raw` has the lowest drawdown at every single limit value.**
This is consistent, not incidental — it holds at all 10 sampled points.

## Step 4 — what §11 defect #2 actually costs: it is not a cost, it is a confound

```
LIMIT    RAW MEDIAN   FIXED MEDIAN     DELTA $   DELTA %  RAW DD MED  FIXED DD MED  RAW SKIP  FIXED SKIP
  off    $139,355     $114,620       $-24,734    -17.7%      45.3%       46.4%         6          0
 0.5pp   $123,677     $126,982       $ +3,306     +2.7%       5.6%        8.4%         0          0
   1pp   $148,069     $154,884       $ +6,815     +4.6%      10.6%       15.5%         0          0
 1.5pp   $167,712     $168,090       $   +378     +0.2%      15.1%       21.6%         0          0
   2pp   $176,655     $178,827       $ +2,172     +1.2%      19.1%       22.6%         0          0
 2.5pp   $185,180     $183,629       $ -1,551     -0.8%      18.8%       25.6%         0          0
   3pp   $189,322     $177,048       $-12,273     -6.5%      21.1%       29.9%         0          0
   4pp   $183,591     $175,575       $ -8,016     -4.4%      27.6%       34.1%         0          0
   5pp   $183,707     $179,093       $ -4,615     -2.5%      31.7%       34.0%         0          0
  10pp   $179,605     $165,272       $-14,334     -8.0%      39.5%       39.0%         3          0
```

**Neither of the two questions this step exists to answer gets a clean
answer, and both are worth reporting exactly as awkward as they are:**

**"How much of the historical result is the defect?"** At `off` — the
figure every session's `$141,837` (raw, this session's exact anchor)
traces back to — fixing the defect makes the result **worse by $24,734
(17.7%)**, not better. The historical `$141,837`/`$139,355`-median result
is not "inflated by a bug"; if anything the bug appears to have been
*helping*, at this specific limit setting. **The direction of this
finding is the opposite of what "known defect, quantify its cost"
implies**, and it is reported exactly that way rather than softened into
"the defect's impact is modest."

**"Does the cost shrink as the limit tightens, converging to zero?"**
**No — the delta neither shrinks monotonically nor converges to zero.**
It is **positive** (the fix helps) across the tight end, 0.5pp through
2pp, then flips to **negative** (the fix hurts) from 2.5pp outward through
10pp — one sign change, not a shrinking trend toward zero — with `off`
(also negative) as the largest-magnitude cell in the whole surface.
**Skipped events
do converge to zero** — `no_reserve_raw` only loses trades to the defect
at `off` (6) and `10pp` (3); every limit from 0.5pp through 5pp already
has zero skips even in the raw mode, because (per two sessions ago's
finding) a tight-enough limit throttles individual buys below the
threshold where the starter-plus-Add pair can overdraw the account. **So
the *mechanical trigger* for the defect does vanish with tightening, but
its *net effect on return*, mediated through which trades get displaced
and which cash goes where, does not shrink in tandem** — a genuinely
counterintuitive result, reported plainly rather than reconciled.

**Drawdown moved in one consistent direction, unlike return:**
`no_reserve_s11fixed`'s median drawdown is higher than `no_reserve_raw`'s
at **every single limit value**, often by several points (46.4% vs 45.3%
at `off`; 34.1% vs 27.6% at 4pp). Whatever the fix changes about which
trades land, it consistently makes the resulting portfolio path rockier,
even in the handful of cases where it also happens to return more.

## Step 5 — censuses

### Cap drift (forward draw, every configuration; full data in every `bracket-*-manifest.json`)

**Largest excess anywhere in the grid: +12.28pp, MSFT, against its 50%
cap** — appearing **identically** under `swap_funding`/`off` (182 days
above) and `no_reserve_s11fixed`/`off` (251 days above). Same ticker, same
excess magnitude (62.28% vs. 50% cap), different day-counts because the
two modes diverge on other trades afterward, but **the same underlying
mechanism**: once a live-cash-rebuilt buy leg lets a position reach its
cap cleanly (rather than the raw-mode defect silently truncating it), the
position is free to drift upward from there with nothing pulling it back.

| Config | Tickers ever above cap | Total ticker-days above cap | Largest excess |
|---|---|---|---|
| no_reserve_raw, off | 0 | 0 | — |
| no_reserve_raw, 0.5–5pp | 0 | 0 | — |
| no_reserve_raw, 10pp | 1 (FSLR) | 37 | +4.08pp |
| no_reserve_s11fixed, off | 1 (MSFT) | 251 | **+12.28pp** |
| no_reserve_s11fixed, 10pp | 1 (TTD) | 1 | +0.01pp (essentially at the boundary) |
| swap_funding, off | 2 (MSFT, TTD) | 182 + 546 | **+12.28pp** (MSFT) |
| swap_funding, 10pp | 2 (ENVX, TTD) | 78 + 713 | +5.36pp (TTD) |

**Zero drift under `no_reserve_raw` at every tight limit (0.5–5pp) —
matching the two-mode partial data from last session exactly.** Drift
only ever appears under the live-cash-rebuild modes (`s11fixed` or
`swap_funding`), and only ever at the looser limits (`off`, `10pp`) —
**the hypothesis "drift-above-cap becomes reachable only once funding
works" holds cleanly across the full grid, not just the partial sample.**
**Nothing anywhere approaches the 25% profit-take threshold** — the
largest excess (+12.28pp on a 50% cap, i.e. 62.28%) is well short of it.
Per the prompt's own framing: the gap between "caps are inviolable" and
what the code enforces is real and now fully measured, but on this
corpus, at this scale, it stays a moderate-stakes gap, not a severe one.

### Binding constraint (forward draw, every configuration; full surface in the manifests)

`no_reserve_raw` never becomes limit-dominant anywhere in the grid up to
5pp — cash remains the majority constraint through at least 5pp (e.g.
77 cash / 17 limit at 5pp). At 0.5pp and 1pp specifically, both
`no_reserve_s11fixed` and `swap_funding` are **98/98 (100%) limit-bound** —
identical to each other, since both share the same rebuild — while
`no_reserve_raw` at those same limits is still 22/76 cash/limit. **The
crossover this thread has been looking for — where `no_reserve` itself
becomes limit-dominant — does not occur anywhere in the sampled range**;
cash remains a live constraint for the raw mode even at the loosest end
of what was tested as "tight."

## Step 6 — the rules

### Rule 1 (margins vs. both controls)

Reported in full in the run output (every one of 27 non-control
configurations × 2 control comparisons); headline: **every configuration
except `no_reserve_raw`/`0.5pp`, `no_reserve_s11fixed`/`off`,
`no_reserve_s11fixed`/`0.5pp`, and `swap_funding`/`0.5pp` is REAL against
the raw control's max.** Against the **s11fixed control's max ($123,931)**
— the secondary Rule 1 comparison this session adds — **almost every
configuration is REAL**, including several that were only "INSIDE THE
NOISE BAND" against the raw control (e.g. `no_reserve_raw`/1pp: real
against s11fixed's max, +19.5%, but not against raw's own max). **No
previously-REAL verdict narrows or vanishes when re-measured against the
s11fixed control** — if anything, more configurations clear the bar
against the (much lower) s11fixed-off max, because that control is itself
depressed by the defect-fix confound documented in Step 4.

### Rule 2 (pairwise, best-of-mode)

```
Top no_reserve_raw:       3pp,   median $189,322, return $189,265-$189,386,   DD 21.1%-21.1%
Top no_reserve_s11fixed:  2.5pp, median $183,629, return $181,616-$184,055,   DD 25.6%-25.6%
Top swap_funding:         3pp,   median $197,437, return $196,805-$198,069,   DD 26.6%-26.7%

no_reserve_raw (3pp) vs no_reserve_s11fixed (2.5pp): return SEPARABLE, drawdown SEPARABLE
no_reserve_raw (3pp) vs swap_funding (3pp):          return SEPARABLE, drawdown SEPARABLE
no_reserve_s11fixed (2.5pp) vs swap_funding (3pp):   return SEPARABLE, drawdown SEPARABLE
```

**All three pairs are separable on both axes — no ties anywhere.**
`swap_funding` wins on return at every pairing; `no_reserve_raw` wins on
drawdown at every pairing; `no_reserve_s11fixed` is dominated on return by
both other modes and comes in worst on drawdown too, at their respective
peaks. **This reverses last session's matched-10pp finding** (where
`no_reserve` beat `swap_funding` outright) — at the *optimal* limit for
each mode rather than a shared 10pp, `swap_funding` (3pp, $197,437) is the
single best return in the entire grid, ahead of `no_reserve_raw`'s own
best (3pp, $189,322) by **$8,115 (4.3%)**. The two sessions are not in
conflict — they answered different questions (matched-limit comparison
vs. optimal-limit comparison) — but the headline "no_reserve beats
swap_funding" from two sessions ago does not survive being re-asked at
each mode's own best setting.

### Rule 3a/3b (shape, plateau)

**All three modes classify JAGGED on the full 10-point axis** — 7 of 9
material differences for `no_reserve_raw` and `no_reserve_s11fixed`, 8 of
9 for `swap_funding`. Full material/immaterial breakdown, every
difference, both magnitudes, is in the run output above (Step 3a
section). **No plateau derived for any mode. This is the third
consecutive session (dense 9-point grid, bracket 10-point grid, this
10-point grid) in which every mode tested comes back jagged** — the
axis's non-monotonicity is not a small-sample artifact; it survives
denser sampling and a third funding-mode variant. **Per the pre-declared
rule, nothing is spec'd from any of the three shapes.**

### Rule 4 (drawdown bar, share-of-draws)

24 of 30 configurations **ROBUSTLY PASS** (100% share-clear in every
passing case — no fragile cells anywhere in this grid, unlike the last
session's swap_funding-7.5/10pp fragility). The 6 failures: `off` and
`10pp` for all three modes, **plus `no_reserve_s11fixed`/`off` fails on
*return*, not drawdown** — the only such case in the table, directly
reflecting Step 4's finding that the fix actively hurts the unconstrained
baseline.

## Follow the peak — trough analysis, per mode

All three modes' peaks share the **same drawdown trough date, 2023-01-05**
— not a coincidence of this corpus's own worst stretch, evidently common
to the whole grid's high-performing region.

| Mode (peak) | Trough invested % | Trough cash % |
|---|---|---|
| no_reserve_raw (3pp) | 72.4% | 27.6% |
| no_reserve_s11fixed (2.5pp) | 78.8% | 21.2% |
| swap_funding (3pp) | 76.8% | 23.2% |

**Cash-drag is refuted again, at every mode's own peak, not just at
2.5pp.** All three sit comfortably majority-invested (72–79%) at their
worst moment — none of them "sat out the decline in cash." Terminal
compositions (2024-06-12) all concentrate in NVDA/AVGO/ORCL as the top
three names across all three modes, with `swap_funding`'s peak notably
adding TTD at 12.4% (absent from `no_reserve_raw`'s terminal top-3) and
`no_reserve_s11fixed`'s peak showing the most even distribution of the
three (TTD 12.7%, ORCL 12.2%, MSFT/AMD both ~6.4%).

## Flagged plainly

- **§11 defect #2 is not simply "a bug that costs money"** — fixing it
  makes the unconstrained baseline meaningfully *worse* (-17.7%) and its
  effect on return never converges to zero as the limit tightens, even
  though the mechanical trigger (skipped events) does. This contradicts
  the framing in this session's own prompt ("the 0.5pp cell already
  showed zero skipped events, so the two modes should converge somewhere
  on the axis") — they converge on *skip count*, not on *return*.
- **`no_reserve_s11fixed` is the worst-performing mode at `off`**, the one
  cell where the design session's own reference figure ($141,837 /
  $139,355) lives — and it's the only FAIL-on-return cell in the entire
  30-row Rule 4 table.
- **`no_reserve_raw` has strictly lower drawdown than both other modes at
  every single one of the 10 sampled limits** — a consistent, not
  incidental, pattern worth the design session weighing against
  `swap_funding`'s return advantage at its own peak.
- **Cap drift is confirmed to be a live-cash-rebuild phenomenon, not a
  swap-funding-specific one** — `no_reserve_s11fixed` drifts exactly as
  far (same ticker, same magnitude) as `swap_funding` at `off`, which
  means any future cap-restoration discussion needs to address the
  rebuild mechanism generally, not swap-funding's donor-selling
  specifically.
- **No previously published verdict from this thread's return-vs-control
  Rule 1 checks turns out to be wrong** — the anchors reproduce exactly,
  and the secondary s11fixed-control comparison only adds REAL verdicts,
  never removes one.
- **No ambiguity required stopping on.** The shared `_rebuild_buy_leg()`
  function, the classified Gate 4, and the 450-run grid were all concrete
  enough to build and execute without a design-session decision mid-run.

## What was deliberately not done

- No funding mode selected, no limit value chosen, no `minPositionDollar`
  picked.
- No spec amended; §12 items untouched; cadence/scope/veto sweep not
  started.
- No cap-restoration rule added; §11 not fixed in the production path.
- The 39.12% ceiling was not adopted; every Rule 4 score uses 38.0% only.
- `price_cache.json` / `fundamentals_cache.json` untouched; `testing/`
  left gitignored, not touched.

## Repo state left behind

- `sweep/db-corpus-baseline`, now at (this session's commits, in order):
  `91b729c` (versioned this session's prompt) → `77b541a` (three-mode
  driver, committed before any manifest) → `f5c9057` (450-run grid + gate
  + baseline + peak-trough manifests, all `git_dirty: false`).
- `analysis/bracket_three_modes_s11_corrected.py` — new driver, containing
  `_rebuild_buy_leg()` shared by `no_reserve_s11fixed` and `swap_funding`.
- `analysis/data/run_manifests/bracket-*-manifest.json` (30),
  `drawdown-baselines-v4-manifest.json`, `step1-five-gates-manifest.json`,
  `peak-trough-analysis-per-mode-manifest.json` — 33 new, fully citable
  manifests.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 bracket_three_modes_s11_corrected.py

# Inspect any config's manifest, e.g. the swap_funding peak:
cat data/run_manifests/bracket-swap_funding-3pp-manifest.json | python3 -m json.tool

# Confirm git_dirty:false and the correct driver commit on every manifest
# from this session:
for f in data/run_manifests/bracket-*.json data/run_manifests/step1-five-gates-manifest.json \
         data/run_manifests/drawdown-baselines-v4-manifest.json \
         data/run_manifests/peak-trough-analysis-per-mode-manifest.json; do
  python3 -c "import json; m=json.load(open('$f')); print('$f', m['git_commit'][:12], m['git_dirty'])"
done
```
