# autonomy-cadence-floor-and-veto — out

**Prompt:** `prompts/autonomy-cadence-floor-and-veto.md`
**run_id:** `autonomy-cadence-floor-and-veto`
**Branch:** `sweep/db-corpus-baseline` · **Date:** 2026-09-01
**Status: COMPLETE.** All five steps run. Not a partial run.

---

> **Cadence floor: `K`=1 best cell `new_calls_only`/3pp → $200,115 phase-averaged
> median (phase degenerate, so this is a plain 15-draw median), 26.63% median
> drawdown; versus `K`=30's $194,171 / 22.96% (`cash_deployment`/1.5pp) and
> $189,425 / 20.58% at matched scope and limit. Rate mechanism: `X*` **does**
> keep falling as K falls under `cash_deployment` — 1.5 / 0.5 / 0.25 / ≤0.1 pp
> at K = 30 / 7 / 3 / 1 — while `new_calls_only` wants 3pp at every K;
> `X* × sessions/yr` = 18.3 / 26.1 / 30.4 / 36.5, which **drifts upward as K
> falls rather than holding constant**, so the rate story is directionally right
> but incomplete. Proximity hypothesis: **refuted.** Veto: removing it is worth
> **$0 — a range of [−$597 .. +$86] at `K`=1, [−$194 .. +$274] at `K`=7,
> [$0 .. +$1,442] at `K`=30, [−$4,916 .. $0] at `K`=90** — **tied** under Rule 2
> at every cadence, and still tied in the loose-limit regime §8 was written for.
> Larger effect: **cadence, decisively — and it is the only one of the two that
> survives Rule 2** (K=1 vs K=30 at matched scope/limit: range-to-range
> **+$5,962 .. +$13,585**, separable). Cells passing the 39.12% bar: 52 of 80;
> above $180k, `K`1/new/3pp, `K`3/new/3pp, `K`30/cash/1.5pp, `K`30/cash/2pp,
> `K`1/new/2.5pp, `K`7/new/3pp, `K`30/new/3pp, `K`3/new/2.5pp, `K`1/new/5pp,
> `K`30/new/2.5pp, `K`30/cash/2.5pp, `K`7/new/2.5pp, `K`7/cash/0.5pp.**

**This contradicts the prompt's stated expectation.** The prompt predicted the
veto was "very likely where autonomy pays." It is not. In this corpus the veto
is worth nothing measurable and the cadence floor is worth ~5.6%.

---

## Two caveats that belong with every `K`=1 figure

1. **`K`=1 is this simulator's floor, not "continuous."** Transcripts publish
   intraday and execution is at the close, so a genuinely continuous agent is
   not representable here. `K`=1 is the fastest cadence the harness can express.
2. **The backtest models no slippage, no partial fills and no rejections** —
   the safety scaffolding `CLAUDE.md` Step 8(b) calls for. Every `K`=1 figure is
   an **upper bound**, not a forecast. A daily-cadence agent trades roughly 30×
   as often as `K`=30 for a 5.6% gross edge; nothing here prices that turnover.

---

## Resume status

| | |
|---|---|
| Seeded from a predecessor | **No.** Fresh `run_id`; `findings.md` and `cells.jsonl` created this session. `progress.json` pre-existed with all steps `pending`. |
| Cells run this session | **2,680** |
| Cells reused | **700** (Step 1 refine reusing the scan's seeds 0–6 within this same session; 0 reused from any prior session) |
| Wall clock, measurement only | ~15.2 min (Step 1 scan 516.5s · Step 1 refine 255.9s · Step 2 35.8s · Step 2 loose 112.2s · gates ~35s) |
| Driver commits | `730fb08` (the §8 model + proximity tagging), `3317860` (the sweep driver) |
| Partial? | **No.** |

`cells.jsonl` was flushed after every cell and `findings.md` appended the moment
each finding was established, per `CLAUDE.md`.

---

## Step 0 — hygiene

Tree clean on `sweep/db-corpus-baseline` at start (only the untracked run_state
directory for this run_id), so `git_dirty` is recordable `false`. Both drivers
were committed **before** any measurement, each as its own commit. `off` sits at
the **loose** end of the limit axis. Invariant #9 is scored per **session**;
invariant #5 conditionally.

`analysis/sweep_cadence_and_session_model.py` from the prior run was reused as
the starting point — the sweep infrastructure was not rebuilt.

**No manifest was written this session.** Every result here is a measurement
against existing manifests, not a new published baseline — the same posture the
prior run took, and appropriate because this run selects nothing.

---

## Step 0b — §8's capitulation model, implemented (not approximated)

`analysis/sweep_cadence_and_session_model.py::run_session_sweep_cell` gains
`veto_p` and `veto_seed` (commit `730fb08`). Implemented clause by clause:

| §8 clause | Implementation | Lines |
|---|---|---|
| pet at the **first** 25%-of-portfolio crossing, probability `p`, **sticky** | coin flipped once per position, at that ticker's own call — the only moment §3/§4 evaluate profit-take, since held positions are not re-sized between their own calls | `:797-813` |
| pet **declines all** recommended Trims **and** Exits | every `side == "sell"` trade for that ticker is suppressed and logged, the profit-take trim included | `:823-836` |
| capitulation at **−30% from the trailing peak position value since entry**, **full exit at that session's close** | peaks refreshed once per session, then the trigger tested; exit executes at that session's close, before that session's decisions, so proceeds join §3 step 2's cash pool | `:529-572` |

Position close clears the flag and the peak: a later re-entry is a new position,
and §8's flag is sticky "for that position."

`veto_seed` is independent of `seed` (the ordering/tie-break draw), per the
prompt's requirement that pet formation carry its own variance. `veto_p = 0.0`
draws no RNG at all.

### Gates 1 and 1a — the change is inert where it must be

Both **forward draws**, compared against **forward-draw** targets:

| Config | Measured | Target | Provenance | Diff |
|---|---|---|---|---|
| `no_reserve_raw`/`off` | $141,836.56574946275 | $141,836.57 | `analysis/data/run_manifests/step1-five-gates-manifest.json` → `results.detail[0]` | −$0.00425 (target quoted to the cent) |
| `swap_funding`/2.5pp | $189,781.58036163618 | $189,781.58036163618 | `analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value` | **$0.00 — bit-exact** |

**GATES 1 AND 1a PASS**, bit-exact, after the §8 change.

---

## Step 1 — the cadence floor

`swap_funding`, `pooled`, `trim_budget_scope = per_event_date`, conformant
per-date trim cap, dedup on, clean window. Limits `{0.1, 0.25, 0.5, 1, 1.5, 2,
2.5, 3, 5, off}` — extended **down** to 0.1pp so `cash_deployment`'s optimum
stays bracketed at fast cadences. 7 draws for the scan, 15 at the 1.0–3.0pp
band. **All grid figures are medians across draws, then averaged across phases —
never forward draws.**

**Phase at `K`=1 is degenerate** and one phase was run: with a one-day interval
every calendar day is a session date regardless of the offset, so the three
offsets would produce byte-identical grids. Its phase spread is therefore 0.00%
by construction, not by merit — do not read it as a robustness advantage over
the slower cadences.

### Anchor check — `K`=7 and `K`=30 reproduce

Both sides are **phase-averaged medians across 15 draws**:

| Cell | Measured | Prior grid | Diff |
|---|---|---|---|
| `K`7/`new_calls_only`/3pp | $189,537.84 | $189,538 | −$0.16 |
| `K`30/`new_calls_only`/3pp | $189,424.76 | $189,425 | −$0.24 |
| `K`30/`cash_deployment`/1.5pp | $194,171.25 | $194,171 | +$0.25 |
| `K`30/`cash_deployment`/2pp | $192,196.58 | $192,197 | −$0.42 |

Provenance for all four prior figures:
`wrap-ups/close-equivalence-corrected-targets-out.md`, Step 5 ranking table
(15-draw refine band). Every difference is rounding against a figure published
to the dollar. **The anchors reproduce; the cross-grid comparison is valid and
nothing needs flagging on that account.**

### The fast end

| K | scope | X* | Phase-avg median | DD median | Rule 4 |
|---|---|---|---|---|---|
| **1** | `new_calls_only` | **3pp** | **$200,115** | 26.63% | pass |
| 3 | `new_calls_only` | 3pp | $194,942 | 26.79% | pass |
| 7 | `new_calls_only` | 3pp | $189,538 | 25.29% | pass |
| 30 | `new_calls_only` | 3pp | $189,425 | 20.58% | pass |
| 1 | `cash_deployment` | **≤0.1pp** | $167,853 | 37.04% | pass (barely) |
| 3 | `cash_deployment` | 0.25pp | $175,027 | 35.84% | pass |
| 7 | `cash_deployment` | 0.5pp | $180,927 | 34.83% | pass |
| 30 | `cash_deployment` | 1.5pp | $194,171 | 22.96% | pass |

**The curve was not flat at its fast end after all.** The prior grid read K=7
and K=30 as tied and inferred flatness; extending to K=3 and K=1 finds a
**monotone rise under `new_calls_only`** — $189,425 → $189,538 → $194,942 →
$200,115 — worth **+5.64%** from K=30 to K=1. The prior wrap-up's statement
that "cadence buys almost nothing on return" was true of the range it sampled
and **false of the range it did not**. Stated as a correction, not a silent
replacement: nothing published was wrong, but the inference drawn from it
(that the fast end was flat and extrapolable) does not hold.

The risk side of the prior finding **does** hold and extends: drawdown rises
monotonically as cadence quickens under `new_calls_only`, 20.58% at K=30 →
25.29% at K=7 → 26.79% at K=3 → 26.63% at K=1. K=1 buys 5.64% of return for
6.05pp more drawdown.

**`cash_deployment` collapses at the fast end.** Every K=1 `cash_deployment`
cell from 0.25pp up fails Rule 4 (43.06%–58.29% median drawdown), and the
column's peak is at the **tightest sampled limit**, 0.1pp.

### The rate mechanism — supported in direction, not in magnitude

| K | sessions/yr | `X*` (`cash_deployment`) | `X* ×` sessions/yr |
|---|---|---|---|
| 30 | 12.18 | 1.5pp | 18.3 |
| 7 | 52.18 | 0.5pp | 26.1 |
| 3 | 121.75 | 0.25pp | 30.4 |
| 1 | 365.25 | ≤0.1pp | ≤36.5 |

`X*` **does keep falling as K falls**, exactly as the deployment-rate hypothesis
predicts, and `new_calls_only` holds at 3pp at every K, exactly as predicted —
the earnings calendar caps the rate there, so K cannot change it.

**But the product is not constant. It drifts, and it drifts in one direction:**
18.3 → 26.1 → 30.4 → 36.5, doubling from K=30 to K=1. Reported as it fell rather
than forced. A clean rate constraint would hold `X* × sessions/yr` fixed; this
says a faster cadence needs a *disproportionately* tighter limit, i.e. the
per-session limit is a weaker brake per unit of session frequency than a pure
rate model implies. That is consistent with the limit throttling the *first*
buy of a session rather than the session's aggregate exposure, but this run did
not test that and does not claim it.

### The competing hypothesis — call-proximity is REFUTED

Every funded Add was tagged with days-since-that-ticker's-nearest-call, and
dollar-weighted forward returns compared by that distance. Pooled over **1,060
`cash_deployment` cells** (all K, all limits except `off`, all phases and draws,
p=0):

| Days since nearest call | n | dollars deployed | +90d return | hold-to-end return |
|---|---|---|---|---|
| 0–3 d | 40,817 | $34.4M | −3.99% | +51.41% |
| 4–7 d | 37,535 | $30.0M | −6.26% | +49.63% |
| 8–30 d | 140,232 | $92.5M | −7.61% | +52.30% |
| **31–90 d** | 168,982 | $87.1M | **−0.87%** | **+102.71%** |
| 90 d+ | 4,950 | $2.1M | −7.72% | +75.86% |

**Under the proximity story near-call Adds should outperform. They do not.** At
90 days the ordering is non-monotone and the second-best bucket is 31–90 days
out; at hold-to-end the **31–90-day bucket is decisively the best**, at double
the near-call bucket's return, and the most distant bucket also beats every
near-call bucket. Cash deployed far from a call is not wasted in this corpus.

The proximity story is refuted; the rate story survives, with the product caveat
above. Note what this does **not** say: it does not say distance is *good*. The
31–90d bucket is dominated by 2023 deployments into names that later compounded,
which is a window property. It says only that proximity does not explain the
`X*` pattern, which is what it was asked.

---

## Step 2 — the veto sweep (§8)

15 draws per cell, `veto_seed` independent of the tie-break seed, at each
cadence's own best Rule-4-viable cell. K=90's cell comes from the prior grid
(`cash_deployment`/3pp — `wrap-ups/close-equivalence-corrected-targets-out.md`
Step 5 ranking table row 8). All figures are **medians across 15 draws** with
min/max as the range; none is a forward draw.

| K | cell | p | median | 15-draw range | DD median | pets formed (Σ15 draws) | capitulations |
|---|---|---|---|---|---|---|---|
| 1 | new/3pp | 0% | $200,115 | $200,115–$200,201 | 26.63% | 0 | 0 |
| 1 | new/3pp | 10% | $200,115 | $199,518–$200,201 | 26.63% | 2 | **0** |
| 1 | new/3pp | 20% | $200,115 | $199,518–$200,201 | 26.63% | 2 | **0** |
| 1 | new/3pp | 30% | $200,115 | $199,518–$200,201 | 26.63% | 3 | **0** |
| 7 | new/3pp | 0% | $185,435 | $185,241–$185,435 | 25.65% | 0 | 0 |
| 7 | new/3pp | 30% | $185,435 | $185,241–$185,515 | 25.65% | 3 | **0** |
| 30 | cash/1.5pp | 0% | $189,398 | $189,398–$189,485 | 24.54% | 0 | 0 |
| 30 | cash/1.5pp | 30% | $189,398 | $189,398–$190,840 | 24.54% | 3 | **0** |
| 90 | cash/3pp | 0% | $190,718 | $190,718–$190,718 | 17.96% | 0 | 0 |
| 90 | cash/3pp | 30% | $190,718 | $185,802–$190,718 | 17.96% | 3 | **0** |

(p=10% and 20% rows omitted where identical to p=30% on every column but pet
count; the full table is in `step2-results.json`.)

### The finding: at the settled limit, §8's trigger almost never arms

**Zero capitulations occur at any best cell, at any cadence, at any `p`.** With
the coin forced to `p = 1.0`, only **one** position in the entire 2.5-year run
ever crosses 25% of portfolio at its own call at `K`=30/cash/1.5pp (AVGO,
peaking at 31.3% on 2024-01-21), one at `K`=7/new/3pp (AVGO, 27.7%), one at
`K`=90/cash/3pp (AVGO, 26.8%), and three at `K`=1/cash/1.5pp (max MSFT 44.1%).
At `p` = 10–30% that yields 2–3 pets across fifteen whole draws, none of which
subsequently fell 30% from its peak.

**The per-session change limit has already removed the behaviour §8 models.**
§5 says the limit "prevents a name reaching its cap in one step"; the measured
consequence is that under the settled configuration positions barely reach the
*profit-take* threshold either, so there is nothing for a pet flag to attach to.
The veto and the limit are two instruments aimed at the same hazard, and in this
corpus the limit gets there first.

### Supplementary — the loose regime §8 was actually written for

Because the above risked being a null result about the *test conditions* rather
than the model, the same sweep was re-run at `cash_deployment` / limit `off`,
where drift is unpoliced and positions reach 79% of portfolio. Here the model
bites hard — 6–18 pets and up to 14 capitulations per 15 draws:

| K | p | median | 15-draw range | DD median | pets | capitulations |
|---|---|---|---|---|---|---|
| 1 | 0% | $123,112 | $123,112–$123,112 | 58.29% | 0 | 0 |
| 1 | 30% | $138,483 | $117,136–$147,181 | 51.13% | 18 | 14 |
| 7 | 0% | $131,165 | $131,165–$131,165 | 50.03% | 0 | 0 |
| 7 | 30% | $118,202 | $110,739–$131,165 | 50.03% | 16 | 5 |
| 30 | 0% | $162,076 | $162,076–$162,076 | 48.54% | 0 | 0 |
| 30 | 30% | $160,812 | $125,494–**$311,697** | 48.54% | 16 | 3 |
| 90 | 0% | $204,680 | $204,680–$204,680 | 36.97% | 0 | 0 |
| 90 | 30% | $207,689 | $198,514–**$338,070** | 36.97% | 12 | 0 |

**The sign is not even consistently negative.** At K=30 and K=90 the best draw
under a 30% veto rate is $311,697 and $338,070 — 1.9× and 1.7× the p=0%
baseline. Refusing to trim a winner in a 2022-01 → 2024-06 window that ends in a
mega-cap melt-up was, in several draws, enormously profitable. The median moves
by −0.8% to +1.5%; the *dispersion* explodes. That is the honest shape of the
result: **the veto in this corpus converts a determinate outcome into a
lottery, without a reliable direction.**

All loose cells except K=90 fail Rule 4 outright, so none of this is a viable
configuration — it is a demonstration that the model is implemented and can act,
which the best-cell nulls could not establish on their own.

---

## Step 3 — what autonomy is worth

**Pre-declared decision rule, Rule 2, applied unchanged:** the value of removing
the veto counts as real at a cadence only if the p=0% and capitulation-`p`
15-draw ranges **do not overlap**. Gaps are reported as ranges, never point
estimates.

### What removing the veto buys

| K | p=0% range | worst capitulation-`p` range | gap as a range | Rule 2 |
|---|---|---|---|---|
| 1 | $200,115–$200,201 | $199,518–$200,201 | **−$597 .. +$86** | **TIED** |
| 7 | $185,241–$185,435 | $185,241–$185,515 | **−$194 .. +$274** | **TIED** |
| 30 | $189,398–$189,485 | $189,398–$190,840 | **$0 .. +$1,442** | **TIED** |
| 90 | $190,718–$190,718 | $185,802–$190,718 | **−$4,916 .. $0** | **TIED** |

**Tied at every cadence.** Overlap is total at all four — reported as tied,
never ranked by median, per the rule agreed before results were seen. The same
verdict holds in the loose regime, where the ranges overlap even more heavily.
**Removing the veto buys nothing measurable in this corpus.**

### What driving `K` to 1 buys

At **matched scope and limit** (`new_calls_only` / 3pp), the only honest
like-for-like comparison:

| Comparison | median gap (phase-averaged medians) | range-to-range gap | Rule 2 |
|---|---|---|---|
| K=1 vs K=30 | +$10,691 (+5.64%) | **+$5,962 .. +$13,585** | **SEPARABLE** |
| K=1 vs K=7 | +$10,578 (+5.58%) | +$1,364 .. +$15,815 | **SEPARABLE** |

Against `K`=30's *best cell anywhere* (`cash_deployment`/1.5pp, $194,171) rather
than its matched cell, K=1's advantage narrows to +$5,944 (+3.06%) — still
positive, and the ranges ($200,115–$200,201 vs $189,398–$201,185) **overlap**,
so that particular comparison is **tied**. Both readings are given because they
answer different questions: matched-cell isolates cadence, best-cell-to-best-cell
answers "what would you actually run."

### Which is larger, and does either survive Rule 2

**Cadence, by roughly an order of magnitude, and it is the only one that
survives.** Removing the veto is worth a range straddling zero at every cadence
(widest bound: ±$4,916). Driving K to 1 is worth +$5,962 to +$13,585 at matched
scope and limit, with non-overlapping ranges.

**This inverts the prompt's expectation.** §10 calls the 0%-veto-versus-
capitulation gap "the dollar value of discipline… the product's thesis,
quantified against Luis's own tickers." Measured for the first time, against
this corpus and under the settled configuration, **that gap is not distinguishable
from zero.** Two readings are available and this run does not choose between
them:

- The discipline is already being enforced by the per-session change limit, so
  §8's veto has nothing left to add. (Supported by the pet counts: the trigger
  barely arms.)
- The corpus cannot see it. Sixteen frozen mega-cap-heavy names over a window
  that ends in a melt-up is close to the worst possible sample for pricing a
  refusal-to-sell. §10 rule 4's structural-bias argument applies here as much as
  to a cash reserve. ENPH and TTD are in the universe precisely to carry this
  shape, and in this window neither produced a capitulation at a viable cell.

---

## Step 4 — rules

### Rule 4 — 39.12% median-drawdown ceiling plus share-of-draws (robust ≥ 2/3)

**52 of 80 Step-1 cells pass; 28 fail.** Every failure is `cash_deployment` or
an `off` cell: the entire K=1 `cash_deployment` column from 0.25pp up, most of
K=3's, and every `off` cell at all four K. Where a cell passes it passes at
**100% share-of-draws** — as in the prior grid, there is no marginal 2/3 case
anywhere, so the share-of-draws clause again does no work.

Every Step-2 best cell passes (17.96%–26.63%) at every `p`. In the loose
supplementary sweep only K=90 (36.97%) passes.

### Rule 3 — single clause, `off` at the loose end, immaterial steps discarded

Materiality: `|Δ| ≥` the smaller of the two adjacent draw ranges.

| K | `new_calls_only` | `cash_deployment` |
|---|---|---|
| 1 | `+++++++−−` **unimodal** | `−−−−−−−−+` **jagged** |
| 3 | `+++++++−−` **unimodal** | `−−−−+` **jagged** |
| 7 | `++++++−−` **unimodal** | `++−−−−−+` **jagged** |
| 30 | `++++++−−` **unimodal** | `++++−−−` **unimodal** |

**All four `new_calls_only` surfaces are unimodal with an interior peak at 3pp.**
Three of four `cash_deployment` surfaces are **jagged**, and in every case the
jaggedness is the same artifact: the `off` cell turning back up at the loose end.
The prior grid found exactly one jagged surface (K=7/`cash_deployment`); this
grid finds that the jaggedness **extends to the whole fast-cadence
`cash_deployment` region**. Per §10 interpretation rule 2, nothing is spec'd from
a jagged surface — and Rule 4 rejects most of these cells independently.

### Rule 3b — plateau within 2.5% of the peak, sensitivity 1% / 2.5% / 5%

| (K, scope) | peak | 2.5% plateau | bracketed? |
|---|---|---|---|
| 1 / new | 3pp | {3pp} | yes |
| 3 / new | 3pp | {3pp} | yes |
| 7 / new | 3pp | {3pp} | yes |
| 30 / new | 3pp | {2.5pp, 3pp} | yes |
| **1 / cash** | **0.1pp** | **{0.1pp}** | **NO — peak at the tight end** |
| 3 / cash | 0.25pp | {0.1pp, 0.25pp} | yes |
| 7 / cash | 0.5pp | {0.5pp} | yes |
| 30 / cash | 1.5pp | {1.5pp, 2pp} | yes |

**The limit-axis extension worked, and it was needed.** At K=3 and K=7 the
extension down to 0.1pp is what keeps `cash_deployment` bracketed — without it
both would have peaked at the tight boundary. **At `K`=1 it was not enough:
`cash_deployment`'s optimum is at or below 0.1pp and remains unbracketed.**
Flagged per Rule 3b. Extending further down is a follow-up, not something this
run decides — and note Rule 4 fails that whole column anyway from 0.25pp up.

The prior run's open item stands and is now sharper: §12 says Rule 3b's plateau
test needs replacing because draw spreads collapse at tight limits. That is
visible again — at `K`=1/`new_calls_only` the 15-draw spread is $86 on $200,115,
which makes the non-overlap machinery return singletons out of precision rather
than isolation. Reported, not worked around.

### Rule 2 — overlapping ranges are tied

Applied throughout Step 3. One asymmetry worth naming: **`K`=1's ranges are
pathologically narrow** ($86 wide at the best cell) because phase is degenerate
and, at `new_calls_only`, the ordering draws are nearly all identical. Narrow
ranges make Rule 2 *easier* to satisfy for K=1, so the "separable" verdict on
the cadence delta rests partly on K=1 having almost no measured variance rather
than on a large gap. The gap is large too (+3.1% to +7.2% range-to-range), so the
conclusion does not hinge on this — but it is a real caveat on the mechanism.

### Rules 1 and 4 unchanged; the five carried-forward gates

| Gate | Result |
|---|---|
| **1** — standing assertion, `no_reserve_raw` control | **PASS.** $141,836.56574946275 vs $141,836.57. Forward draw both sides. |
| **1a** — `swap_funding`/2.5pp | **PASS, bit-exact.** $189,781.58036163618. Forward draw both sides. |
| **2** — invariant #2, `target_pct ≤ cap_pct` at decision time | **PASS.** Max excess 0.000000pp over a 60-cell sample spanning K ∈ {1,3,7,30,90}, both scopes, limits {1.5pp, 3pp, `off`}, `p` ∈ {0%, 30%}. |
| **3** — invariant #9, session move ≤ limit | **PASS** across all 2,680 recorded cells. Every limit's worst observed value equals the limit exactly and never exceeds it. **No apparent breach this run** — the prior run's per-date-vs-per-session artifact was specific to `single_event` cadence, which is not in this grid. |
| **4** — invariant #5, conditional | **PASS.** **Zero** skipped events across all 2,680 cells, so nothing to classify and no unclassifiable skip to stop on. |
| **5** — independent drawdown recompute within 0.01pp | **PASS.** Max \|diff\| 0.000000pp over the same 60-cell sample. |

No gate tests a condition §11 documents as a known unfixed defect.

---

## Flagged plainly

### Gates that fail
**None.** All six pass; 1a bit-exact.

### Anchors that do not reproduce
**None.** All four `K`=7 / `K`=30 anchors reproduce to within rounding of a
figure published to the dollar. The cross-grid comparison is valid.

### Rules giving an uncomfortable answer

1. **Rule 2 nullifies the entire headline measurement this run existed to
   make.** The veto is tied at every cadence, in both the settled and the loose
   regime. §10's "dollar value of discipline — the product's thesis, quantified"
   comes back as *unmeasurable in this corpus*. That is the single most
   uncomfortable result here, and it is reported rather than rescued.
2. **The loose-regime veto sweep is worse than a null: it is bidirectional.**
   The best draws under a 30% veto rate ($311,697 at K=30, $338,070 at K=90)
   are far above the p=0% baseline. In this window, falling in love with a
   winner and refusing to trim it was sometimes the single best decision
   available. Any narrative that the veto is simply costly is not supported.
3. **Rule 3b says `K`=1/`cash_deployment` is not bracketed** even after the
   axis was extended down to 0.1pp specifically to prevent that.
4. **Rule 3 flags three of four `cash_deployment` surfaces as jagged**, all at
   the fast end. Per §10 rule 2 the fast-cadence `cash_deployment` experiment
   should be treated as failed rather than mined for a setting.
5. **The `X*` product drifts.** The deployment-rate hypothesis survives in
   direction and fails in magnitude. It is not forced into a clean story.

### Previously published numbers now known to need correction

Stated explicitly rather than silently replaced:

| Where | Published | Correction | Why |
|---|---|---|---|
| `wrap-ups/close-equivalence-corrected-targets-out.md` and `prompts/autonomy-cadence-floor-and-veto.md` opening | "**Cadence buys almost nothing on return**… K=7 and K=30 are tied (0.06% apart)" | **True within K ∈ [7, 90]; false below 7.** K=3 is $194,942 and K=1 is $200,115 at `new_calls_only`/3pp, +5.64% over K=30. | The flatness was inferred from a range that stopped at K=7. The tie between K=7 and K=30 itself still stands and reproduces. |
| Same, "the existing curve is flat at its fast end" | flat | **Not flat — monotone rising below K=7 under `new_calls_only`.** | Same cause. The prompt correctly called this "an extrapolation the grid does not support"; the extrapolation turns out to have been wrong, not merely unsupported. |
| Same, minimum viable cadence `K`=90 | unchanged | **Undisturbed.** K=90 remains Rule-4-viable and is now the lowest-drawdown viable cadence measured (17.96% at its best cell). | — |

No figure published by the prior run is *wrong*; one **inference** drawn from it
is, and it is corrected above.

### Does anything disturb the settled decisions in §0?

**No settled decision is disturbed. Three are now differently supported.**

- **Funding mode `swap_funding`** — undisturbed, used throughout.
- **Drawdown ceiling 39.12%** — undisturbed, and doing more work than before:
  it rejects 28 of 80 Step-1 cells and the whole fast-cadence `cash_deployment`
  region.
- **`X` = 2.5pp, marked provisional pending `K`** — the grid again says
  provisional was right, and now says something stronger: **2.5pp is optimal
  for no (K, scope) pair at any K from 1 to 30.** `new_calls_only` wants 3pp
  everywhere; `cash_deployment` wants 1.5pp down to ≤0.1pp as K falls.
- **§8's user-behaviour model itself** — not a §0 item, but the finding that
  its trigger barely arms under the settled limit is new information about a
  closed spec section. **This run does not amend it.** It reports that the
  model as written is close to inert in the configuration the spec otherwise
  settles on, which is a question for a design session, not a sweep.
- **`minPositionPct`** — untouched this run.

---

## Verification performed

- Both gate targets re-read out of their manifests **by key** before relying on
  them, and every reference figure in this document carries manifest-plus-key or
  wrap-up-plus-table provenance.
- `python3 -c "import ast; ast.parse(...)"` on both edited/created Python files
  before every commit.
- The §8 change proved inert where it must be by **bit-exact reproduction** of
  an independently recorded forward draw (17 significant figures, diff = 0.0)
  with `veto_p = 0.0`.
- The §8 model proved **active** where it must be by a forced `veto_p = 1.0`
  diagnostic across six configurations, which located the exact positions and
  dates that cross 25% (AVGO 2024-01-21 at 31.3%, NVDA 2024-06-12 at 79.4% under
  `off`, MSFT 2024-04-10 at 44.1% at K=1) — establishing that the null result at
  the best cells is a property of the configuration, not a broken implementation.
- Gates 3 and 4 swept over all 2,680 recorded cells; Gates 2 and 5 re-derived
  independently over a 60-cell sample deliberately including `p`=30% cells.
- Anchor check run against four separate prior-grid cells, not one.
- Proximity test pooled over 1,060 cells rather than reported from a single run.
- Reproducibility: tree clean before running; both drivers committed **before**
  any measurement, each as its own commit; only specific files staged, never
  `git add .`; no unrelated working-tree changes existed to stash; `testing/`
  untouched.

---

## Deviations from the prompt, and why

1. **A pet is also excluded from swap-funding donor eligibility.** §8's text
   names Trims and Exits; a displacement trim is a sell of the beloved position
   to fund a different idea, which is exactly the reduction the modelled user
   refuses. Implemented that way and documented in the driver docstring. **This
   is an interpretation, not something §8 states**, and it is the one place this
   run went beyond the letter of a closed spec. Its effect is small — donors are
   only consulted when a candidate is short of cash, and pets are 0–3 positions
   per run — but it is flagged rather than buried.
2. **A supplementary loose-limit veto sweep (`cash_deployment`/`off`) was added**,
   240 cells beyond the prompt's grid. Without it the Step 2 result would have
   been an unfalsifiable null: zero capitulations could equally mean "the veto
   costs nothing" or "the implementation is broken." The supplementary sweep
   distinguishes them.
3. **Step 1's 15-draw refinement used the 1.0–3.0pp band** rather than a
   narrower "top region", matching the prior run's choice for comparability.
   Cells outside that band are 7-draw and are labelled as such in the tables.
4. **`K`=1 was run at one phase**, per the prompt's own instruction to say so
   when phase is degenerate.

---

## Deliberately not done — the scope boundary

**Report, do not decide.** This run selected nothing:

- **No `K` chosen.** K=1 has the highest return measured; K=90 has the lowest
  drawdown; K=30 has the best risk-adjusted cell. All reported, none recommended.
- **No limit chosen, no scope chosen, no `p` chosen, no `minPositionPct`
  chosen.**
- **No spec amended.** §0's `X` = 2.5pp still reads 2.5pp. §8 is unchanged in
  the document — only implemented.
- **No §12 open item resolved**, including Rule 3b's plateau-test replacement,
  which this run again found wanting and again only reported.
- **No manifest published.** No new baseline is claimed.
- **No production code touched.** Simulator/analysis only.

---

## Follow-up commands

Reproduce Gates 1 and 1a (fast, ~4s):

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import sys; from pathlib import Path
REPO = Path("/Users/luismorales/Desktop/investment-agent")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"analysis"))
import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup
ev, tf, df, tif = S.load_events_dedup_on()
px = PriceLookup.from_cache(S.SCRIPT_DIR/"data"/"price_cache.json")
for name, (fm, lim, tgt) in {
    "no_reserve_raw/off": ("no_reserve_raw", None, 141836.57),
    "swap_funding/2.5pp": ("swap_funding", 2.5, 189781.58036163618),
}.items():
    r = S.run_session_sweep_cell(ev, px, tf, df, tif, cadence="single_event",
        phase_offset=0, scope="new_calls_only", funding_mode=fm, limit_pp=lim)
    print(f"{name}: {r['final_value']!r}  target {tgt!r}  diff {r['final_value']-tgt:+.10f}")
EOF
```

Re-run the sweeps (resumable — recorded cells are skipped by `config_hash`, so
these return in seconds unless the driver commit changed):

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 analysis/run_autonomy_cadence_and_veto.py 1scan
python3 analysis/run_autonomy_cadence_and_veto.py 1refine
python3 analysis/run_autonomy_cadence_and_veto.py 2
python3 analysis/run_autonomy_cadence_and_veto.py 2loose
```

Show that §8's trigger barely arms — the forced `p = 1.0` diagnostic that
underwrites the Step 2 null:

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import sys; from pathlib import Path
REPO = Path("/Users/luismorales/Desktop/investment-agent")
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/"analysis"))
import analysis.sweep_cadence_and_session_model as S
from analysis.simulator.data import PriceLookup
ev, tf, df, tif = S.load_events_dedup_on()
px = PriceLookup.from_cache(S.SCRIPT_DIR/"data"/"price_cache.json")
for k, scope, lim in [("30","cash_deployment",1.5), ("7","new_calls_only",3.0),
                      ("90","cash_deployment",3.0), ("1","cash_deployment",1.5),
                      ("30","cash_deployment",None)]:
    r = S.run_session_sweep_cell(ev, px, tf, df, tif, cadence=k, phase_offset=0,
        scope=scope, funding_mode="swap_funding", limit_pp=lim, seed=0,
        veto_p=1.0, veto_seed=1)
    mx, who = 0.0, None
    for s in r["daily_snapshots"]:
        if s.total_value > 0:
            for t, v in s.position_values.items():
                if v / s.total_value > mx:
                    mx, who = v / s.total_value, (t, s.date)
    print(f"K={k:>2} {scope:16s} lim={lim}  pets={r['n_pets']} "
          f"caps={r['n_capitulations']}  max position {mx*100:.1f}% {who}")
EOF
```

Recheck Gates 3 and 4 over every recorded cell:

```bash
cd "/Users/luismorales/Desktop/investment-agent"
python3 - <<'EOF'
import json, collections
from pathlib import Path
cells = [json.loads(l) for l in Path(
  "analysis/data/run_state/autonomy-cadence-floor-and-veto/cells.jsonl"
).read_text().splitlines() if l.strip()]
worst, skipped = collections.defaultdict(float), 0
for c in cells:
    lim = c["params"].get("limit_pp")
    if lim is not None:
        worst[lim] = max(worst[lim], c["results"].get("max_session_pp_change", 0.0))
    skipped += c["results"].get("n_skipped", 0)
print("cells:", len(cells))
for lim in sorted(worst):
    print(f"  limit={lim}pp worst={worst[lim]:.6f}pp "
          f"{'OK' if worst[lim] <= lim + 1e-6 else 'BREACH'}")
print("total skipped events:", skipped)
EOF
```

---

## Artifacts

| Path | What |
|---|---|
| `analysis/sweep_cadence_and_session_model.py` | §8 capitulation model + proximity tagging (`730fb08`) |
| `analysis/run_autonomy_cadence_and_veto.py` | Steps 1–2 driver, resumable (`3317860`) |
| `analysis/data/run_state/autonomy-cadence-floor-and-veto/findings.md` | append-only findings |
| `.../cells.jsonl` | 2,680 cells, `config_hash`-keyed |
| `.../progress.json` | all steps `done` |
| `.../step1scan-results.json`, `step1refine-results.json` | the cadence grid |
| `.../step2-results.json`, `step2loose-results.json` | the veto sweeps |
| `.../step1scan.log`, `step1refine.log` | run logs with per-cell timings |

Standing constraints honoured: no LLM calls, no API spend, no DB writes (corpus
reads only), no cache refreshes (`price_cache.json` / `fundamentals_cache.json`
frozen at 2026-05-11; the 113-day staleness warning appeared and was ignored as
expected), work confined to `sweep/db-corpus-baseline`, nothing pushed,
`testing/` untouched.
