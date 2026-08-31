# The limit axis, densely — wrap-up

**Limit surface: JAGGED for `no_reserve`, sign sequence `+--+----` (3
sign changes); JAGGED for conformant `swap_funding`, sign sequence
`+-----+-` (3 sign changes). Plateau: none — per Rule 3, the axis does not
qualify for a plateau derivation in either mode. Configurations robustly
passing the 38.0% bar: `no_reserve` at 2.5pp, 5pp, 7.5pp, and
`swap_funding` at 2.5pp, 5pp — all four clear on 100% of 15 draws. Best
`no_reserve` (2.5pp) vs. best `swap_funding` (2.5pp): SEPARABLE on return
($184,607–$185,296 vs. $189,414–$191,052 — swap wins), SEPARABLE on
drawdown (18.8%–18.9% vs. 22.7%–22.7% — no_reserve wins).**

**The mechanical rule and the eyeball read disagree, and the mechanical
rule wins by design.** Both axes visually look like they have a strong,
tight, high-quality peak somewhere in the 2.5–5pp region — return roughly
30% above the unmodified control, drawdown roughly half of it, spread near
zero. But the sign-change test correctly detects that the full nine-point
curve is not a single hump: there is a second local rise later in the axis
(a partial recovery around 10pp for `no_reserve`, a small tick up at 17.5pp
for `swap_funding`) that produces a third sign change in both modes. **Per
Rule 3, that makes the shape jagged, and nothing is spec'd from the shape
of either axis — even though individual points on it look excellent.**
This is flagged as exactly the kind of uncomfortable-but-correct result the
prompt asked to be reported plainly rather than rationalized away.

All work committed, `git_dirty: false` verified on every manifest, driver
committed before any manifest was generated. No DB writes, no LLM calls, no
cache refreshes. Wall-clock for the full 270-run grid: **35.8 seconds.**

---

## Step 0 — carried forward

Reused the reproducibility machinery exactly: clean tree confirmed
(`git status --porcelain` was already empty this session — no unrelated
dirt needed stashing this time), driver
(`analysis/sweep_limit_axis_dense.py`) committed at `15c74a8` before any
manifest was written, both assertions (`git_dirty: false`, driver present
at HEAD) enforced at import time, `loaded_event_count` (195) and
`in_window_event_count` (147) recorded separately in every manifest, and
the standing `$141,837` assertion (`$141,836.57` to rounding) confirmed
before any measurement.

**Housekeeping:** the four non-citable manifests from two sessions ago
(`step2-cell6`, `step2-cell7`, `step2-cell7-datecap`, `step2-cell7-inverted`
— `git_dirty: true`, drivers absent from the commits they named) are
renamed to `noncitable-step2-cell6` etc., not deleted, so they can't be
mistaken for this or last session's citable `step2-`/`dense-` prefixed
manifests.

## Step 1 — the dense grid: 270 runs

Exact invocation: `cd analysis && python3 sweep_limit_axis_dense.py`.
9 limit values (off, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20pp) × 2 funding
modes (`no_reserve`, conformant per-date-capped `swap_funding`) × 15 draws
(forward, reversed, seeds 1–13) = 270 runs. **Wall-clock: 35.8 seconds** —
comfortably under the "well under two minutes" estimate; a future sweep
sampling this densely again, or denser, remains cheap.

### Full 18-configuration table

| Config | Final min | Final median | Final max | Spread (% med) | DD min | DD median | DD max | Clears 38.0%/15 |
|---|---|---|---|---|---|---|---|---|
| no_reserve off | $117,455 | $139,355 | $154,398 | 26.5% | 43.0% | 45.3% | 45.7% | 0 |
| no_reserve 2.5pp | $184,607 | $185,180 | $185,296 | **0.4%** | 18.8% | 18.8% | 18.9% | **15** |
| no_reserve 5pp | $180,121 | $183,707 | $186,094 | 3.3% | 31.7% | 31.7% | 31.7% | **15** |
| no_reserve 7.5pp | $170,477 | $177,062 | $182,926 | 7.0% | 36.4% | 36.4% | 36.6% | **15** |
| no_reserve 10pp | $171,919 | $179,605 | $189,528 | 9.8% | 39.2% | 39.5% | 39.7% | 0 |
| no_reserve 12.5pp | $151,410 | $158,422 | $166,298 | 9.4% | 43.9% | 45.0% | 45.5% | 0 |
| no_reserve 15pp | $133,125 | $156,854 | $167,680 | 22.0% | 46.1% | 46.2% | 46.5% | 0 |
| no_reserve 17.5pp | $118,806 | $146,996 | $161,684 | 29.2% | 44.9% | 46.3% | 46.5% | 0 |
| no_reserve 20pp | $122,688 | $140,201 | $145,593 | 16.3% | 44.4% | 45.0% | 46.0% | 0 |
| swap_funding off | $135,084 | $155,878 | $160,687 | 16.4% | 45.6% | 47.8% | 47.8% | 0 |
| swap_funding 2.5pp | $189,414 | $190,481 | $191,052 | **0.9%** | 22.7% | 22.7% | 22.7% | **15** |
| swap_funding 5pp | $162,530 | $179,209 | $186,120 | 13.2% | 35.1% | 35.3% | 35.3% | **15** |
| swap_funding 7.5pp | $143,349 | $158,927 | $162,506 | 12.1% | 37.3% | 38.3% | 38.4% | 7 |
| swap_funding 10pp | $140,178 | $156,231 | $160,808 | 13.2% | 37.8% | 38.8% | 39.2% | 7 |
| swap_funding 12.5pp | $135,106 | $153,399 | $156,473 | 13.9% | 40.8% | 42.1% | 42.6% | 0 |
| swap_funding 15pp | $133,521 | $152,059 | $158,058 | 16.1% | 41.0% | 42.4% | 43.9% | 0 |
| swap_funding 17.5pp | $135,321 | $155,010 | $158,173 | 14.7% | 41.0% | 42.7% | 43.7% | 0 |
| swap_funding 20pp | $134,916 | $154,023 | $156,649 | 14.1% | 41.7% | 43.8% | 45.1% | 0 |

**The tight-limit region (2.5–5pp) is a different world from everything
sampled by the last two sessions.** Both modes at 2.5pp show final-value
spreads under 1% of median across 15 independent draws — the tightest,
most reproducible results anywhere in this entire thread — with drawdowns
roughly half the unmodified control's. This was invisible to the previous
4-point sweep (off/10/15/20), which never sampled below 10pp.

### Forward-draw funding diagnostics and donor distribution (selected rows; full data in every `dense-*-manifest.json`)

| Config | Cash<1% | Adds funded/partial/unfunded | Shortfall | Distinct tickers | Displacements |
|---|---|---|---|---|---|
| no_reserve off | 88.7% | 4/20/74 of 98 | $2,351,360 | 12 | 0 |
| no_reserve 2.5pp | 33.8% | **44/8/46** of 98 | $166,467 | 15 | 0 |
| no_reserve 5pp | 65.1% | 21/17/60 of 98 | $423,006 | 15 | 0 |
| swap_funding off | 92.8% | 2/57/32 of 91 | $2,453,260 | 14 | 167 |
| swap_funding 2.5pp | 41.1% | **54/34/8** of 96 | $119,065 | 15 | 198 |
| swap_funding 5pp | 65.3% | 37/48/8 of 93 | $297,582 | 15 | 304 |

**At 2.5pp, funding stops being chronically broken.** `no_reserve` at
2.5pp fully funds 44 of 98 Adds (44.9%) — an order of magnitude better than
the unmodified control's 4.0%. `swap_funding` at 2.5pp fully funds 54 of 96
(56.3%) and leaves only 8 entirely unfunded (8.3%, vs. the control's
75.8%). **A tight session limit does more for chronic cash starvation than
any funding mode tested alone in the last two sessions** — it forces the
book to build gradually across many sessions instead of being consumed by
whichever three names report first.

Donor position-size distribution (below 2%/1%/0.5% of portfolio, of total
displacements) for every `swap_funding` config with a nonzero displacement
count is in the manifests; at 2.5pp: 173/148/124 of 198 (87.4%/74.7%/62.6%)
— essentially unchanged from prior sessions' ~70–75% below 1% despite the
much healthier funding regime. **`minPositionDollar` stays exactly as
undetermined as before** — this sweep didn't touch that axis, per
instruction, and the distribution doesn't resolve itself just because
funding improved elsewhere.

## Rule 1 — beats the control

Every non-control configuration's median vs. the control's max, with
margin in dollars and as a percentage:

| Config | Median | Margin vs. control max ($154,398) | % | Verdict |
|---|---|---|---|---|
| no_reserve 2.5pp | $185,180 | +$30,783 | +19.9% | REAL |
| no_reserve 5pp | $183,707 | +$29,310 | +19.0% | REAL |
| no_reserve 7.5pp | $177,062 | +$22,664 | +14.7% | REAL |
| no_reserve 10pp | $179,605 | +$25,208 | +16.3% | REAL |
| no_reserve 12.5pp | $158,422 | +$4,024 | +2.6% | REAL |
| no_reserve 15pp | $156,854 | +$2,457 | +1.6% | REAL |
| no_reserve 17.5pp | $146,996 | -$7,401 | -4.8% | INSIDE THE NOISE BAND |
| no_reserve 20pp | $140,201 | -$14,196 | -9.2% | INSIDE THE NOISE BAND |
| swap_funding off | $155,878 | +$1,480 | +1.0% | REAL |
| swap_funding 2.5pp | $190,481 | +$36,084 | +23.4% | REAL |
| swap_funding 5pp | $179,209 | +$24,811 | +16.1% | REAL |
| swap_funding 7.5pp | $158,927 | +$4,530 | +2.9% | REAL |
| swap_funding 10pp | $156,231 | +$1,833 | +1.2% | REAL |
| swap_funding 12.5pp | $153,399 | -$999 | -0.6% | INSIDE THE NOISE BAND |
| swap_funding 15pp | $152,059 | -$2,338 | -1.5% | INSIDE THE NOISE BAND |
| swap_funding 17.5pp | $155,010 | +$613 | +0.4% | REAL |
| swap_funding 20pp | $154,023 | -$374 | -0.2% | INSIDE THE NOISE BAND |

**Note the non-monotone REAL/INSIDE pattern** — `swap_funding` at 17.5pp
registers REAL (barely, +0.4%) sandwiched between 15pp and 20pp, both
INSIDE THE NOISE BAND. A rule this sensitive to a few hundred dollars of
median, on an axis with this much internal structure, is itself evidence
supporting Rule 3's jagged classification below rather than contradicting it.

## Rule 3a — shape

**Sign sequence method, applied exactly as specified, no softening:**

**`no_reserve`:** medians `[$139,355, $185,180, $183,707, $177,062,
$179,605, $158,422, $156,854, $146,996, $140,201]` (off→20pp).
First-difference signs: **`+--+----`**. **3 sign changes.** The rule
tolerates at most one *additional* sign change beyond the first (the
expected single peak), and only if its magnitude is smaller than the
smaller of the two adjacent configs' own 15-draw spreads. Here there are
two additional sign changes (at 7.5→10pp, rising, and 10→12.5pp, falling
again) — **JAGGED AND UNUSABLE.**

**`swap_funding`:** medians `[$155,878, $190,481, $179,209, $158,927,
$156,231, $153,399, $152,059, $155,010, $154,023]`. Signs: **`+-----+-`**.
**3 sign changes** (the extra ones at 15→17.5pp, rising, and 17.5→20pp,
falling). **JAGGED AND UNUSABLE.**

**Per instruction, nothing is spec'd from either axis's shape.** The
tight-limit region's excellent numbers (Rule 4, below) stand on their own
as individual, well-measured points — they are not licensed by this rule
to be described as "the peak of a usable curve," because the curve isn't
one clean curve.

## Rule 3b — plateau

**Both modes are JAGGED under 3a, so no plateau is derived for either.**
Per the prompt: *"If it is jagged with an isolated peak at one oddly
specific value, the experiment failed at that axis and nothing is spec'd
from it."* Reported here rather than skipped: the design session should
not read the strong 2.5–5pp numbers below as "the answer this sweep
found" — they are real, individually well-measured points on an axis this
sweep's own pre-declared rule says is not currently interpretable as a
whole.

## Rule 4 — drawdown bar on the full distribution

Scored against the standing 38.0% bar using **median** drawdown across 15
draws (not a single forward draw, correcting last session's known gap):

| Config | Med. final | Med. DD | Beats 3 | Clears | Share clearing | Verdict |
|---|---|---|---|---|---|---|
| no_reserve off | $139,355 | 45.3% | yes | no | 0% | FAIL (drawdown) |
| **no_reserve 2.5pp** | $185,180 | 18.8% | yes | yes | **100%** | **ROBUSTLY PASSING** |
| **no_reserve 5pp** | $183,707 | 31.7% | yes | yes | **100%** | **ROBUSTLY PASSING** |
| **no_reserve 7.5pp** | $177,062 | 36.4% | yes | yes | **100%** | **ROBUSTLY PASSING** |
| no_reserve 10pp | $179,605 | 39.5% | yes | no | 0% | FAIL (drawdown) |
| no_reserve 12.5pp | $158,422 | 45.0% | yes | no | 0% | FAIL (drawdown) |
| no_reserve 15pp | $156,854 | 46.2% | yes | no | 0% | FAIL (drawdown) |
| no_reserve 17.5pp | $146,996 | 46.3% | yes | no | 0% | FAIL (drawdown) |
| no_reserve 20pp | $140,201 | 45.0% | yes | no | 0% | FAIL (drawdown) |
| swap_funding off | $155,878 | 47.8% | yes | no | 0% | FAIL (drawdown) |
| **swap_funding 2.5pp** | $190,481 | 22.7% | yes | yes | **100%** | **ROBUSTLY PASSING** |
| **swap_funding 5pp** | $179,209 | 35.3% | yes | yes | **100%** | **ROBUSTLY PASSING** |
| swap_funding 7.5pp | $158,927 | 38.3% | yes | no | 47% | FAIL (drawdown) |
| swap_funding 10pp | $156,231 | 38.8% | yes | no | 47% | FAIL (drawdown) |
| swap_funding 12.5pp | $153,399 | 42.1% | yes | no | 0% | FAIL (drawdown) |
| swap_funding 15pp | $152,059 | 42.4% | yes | no | 0% | FAIL (drawdown) |
| swap_funding 17.5pp | $155,010 | 42.7% | yes | no | 0% | FAIL (drawdown) |
| swap_funding 20pp | $154,023 | 43.8% | yes | no | 0% | FAIL (drawdown) |

**Every one of the eighteen configurations beats SPY, QQQ, and TMFC on
return, at every draw.** As in every prior sweep, drawdown alone decides
pass/fail. **Five configurations robustly pass, all in the 2.5–7.5pp
region, and all pass on literally 100% of 15 draws** — a materially
stronger and more confidently-measured result than last session's single
config (`D`) passing by landing exactly on the bar off one arbitrary draw.
**`no_reserve` 10pp and `swap_funding` 7.5pp/10pp are near-misses** —
`swap_funding` at 7.5–10pp clears on only 47% of draws (fragile, not
passing), consistent with sitting right at the boundary rather than
comfortably inside it.

**Diagnostic, not a score — clearing counts at 38.0% vs. the un-adopted
39.12%:**

| Config | Clears 38.0%/15 | Clears 39.12%/15 (diagnostic) |
|---|---|---|
| swap_funding 7.5pp | 7 | **15** |
| swap_funding 10pp | 7 | **14** |
| every other configuration | identical between the two bars | identical |

**Every configuration except these two clears the same count under both
ceilings — the 1.12pp difference is inert everywhere else in this grid.**
But at `swap_funding` 7.5pp and 10pp specifically, it is decisive: both
flip from "fragile" (clearing only 47% of draws under 38.0%) to fully or
nearly robust (100% and 93% under 39.12%). **Whichever bar the design
session eventually adopts will change the verdict on exactly these two
configurations, and nothing else in this sweep** — a cheap, precise thing
to know before spending another sweep on it.

## Step 3 — Rule 2 applied to drawdown, not just return

Top configuration per mode by median final value:

- **Top `no_reserve`: 2.5pp** — return range $184,607–$185,296, drawdown
  range 18.8%–18.9%.
- **Top `swap_funding`: 2.5pp** — return range $189,414–$191,052, drawdown
  range 22.7%–22.7%.

**Return: SEPARABLE.** Ranges do not overlap; `swap_funding` at 2.5pp beats
`no_reserve` at 2.5pp on every draw (worst `swap_funding` draw $189,414 >
best `no_reserve` draw $185,296).

**Drawdown: SEPARABLE.** Ranges do not overlap either; `no_reserve` at
2.5pp has the lower, tighter drawdown on every draw (18.8–18.9% vs. a flat
22.7%).

**The two modes' best configurations are not tied — they trade off cleanly
in opposite directions, both by a wide, non-overlapping margin.**
`swap_funding` wins on return, `no_reserve` wins on drawdown, and neither
result is close enough to call noise. This is a genuinely different, more
resolved picture than last session's matched-10pp comparison, where the
modes were separable on return but their drawdowns had never been measured
across draws at all.

## Flagged plainly

- **The mechanical Rule 3 and the visual impression of the data disagree,
  and the mechanical rule is followed, not overridden.** Both axes have an
  extremely strong, tight cluster of results at 2.5–5pp that would look,
  to an eye scanning the table, exactly like "the peak" — but the full
  nine-point shape has a second rise later on each axis, which the
  pre-declared sign-change test correctly flags as jaggedness. Per
  instruction, **that is the rule working, not a shortcoming of the
  sweep.**
- **Rule 4's individually-passing configurations should not be quietly
  treated as "the plateau Rule 3 failed to find."** They are five
  individual points with excellent, well-measured numbers; Rule 3
  explicitly withholds the license to describe them as a coherent, usable
  region of the axis.
- **`swap_funding` at 7.5pp and 10pp are fragile, not failing outright** —
  they clear the median but only 47% of individual draws, and the choice
  between the 38.0% and 39.12% ceilings would flip 10pp specifically from
  fragile to near-robust. Worth the design session's attention before
  either bar is adopted.
- **This sweep did not resolve `minPositionDollar`** — the donor-size
  distribution at every `swap_funding` limit still shows the large majority
  of draws leaving donors below 1% of portfolio, unchanged in character
  from prior sessions despite the much better-funded regime at tight
  limits.
- **No ambiguity required stopping on.** The replaced Rule 3 (shape, then
  plateau) and Rule 4 (median-across-draws scoring) were both concrete
  enough to implement without a design-session decision; the one place
  judgment was needed (what counts as a "material" sign-change violation)
  was specified precisely enough in the prompt (magnitude vs. the smaller
  adjacent draw-range) to apply mechanically.

## What was deliberately not done

- No funding mode selected, no limit value chosen, no `minPositionDollar`
  picked, no plateau asserted where Rule 3 says none exists.
- The 39.12% ceiling was not adopted and no cell was scored against it —
  only the diagnostic clearing-count was reported, clearly labeled.
- No spec amended, no §12 items resolved, no cadence/scope/veto sweep started.
- `price_cache.json` / `fundamentals_cache.json` untouched; `testing/`
  left gitignored, not touched.

## Repo state left behind

- `sweep/db-corpus-baseline`, now at (this session's commits, in order):
  `0a1647e` (housekeeping: renamed non-citable manifests, versioned prompt
  + prior wrap-up) → `15c74a8` (dense-grid driver, committed before any
  manifest) → `4ba36d3` (19 new manifests: 18 dense-grid configs +
  drawdown-baselines, all `git_dirty: false`).
- `analysis/sweep_limit_axis_dense.py` — new driver.
- `analysis/data/run_manifests/dense-*.json`,
  `drawdown-baselines-manifest.json` — 19 new, fully citable manifests.
- `analysis/data/run_manifests/noncitable-step2-cell*.json` — renamed, not
  deleted, per instruction.
- No stash was needed this session — the tree was already clean of
  unrelated changes at the start.
- `dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 sweep_limit_axis_dense.py

# Inspect any config's manifest:
cat data/run_manifests/dense-no_reserve-2.5pp-manifest.json | python3 -m json.tool

# Confirm git_dirty:false and the correct driver commit on every manifest
# from this session:
for f in data/run_manifests/dense-*.json data/run_manifests/drawdown-baselines-manifest.json; do
  python3 -c "import json; m=json.load(open('$f')); print('$f', m['git_commit'][:12], m['git_dirty'])"
done
```
