# sizing-channel-sensitivity — wrap-up

**Scope boundary: report, do not decide.** `analyst_sensitivity_harness.py`
untouched (new driver written alongside it), no file under
`analysis/simulator/` modified, `ALLOCATOR_OPERATING_MODEL.md`,
`PROMOTION_GATE.md` and `gate_ledger.json` untouched, the falsy-zero defect
not patched. No LLM calls, no API spend, no DB writes ($0 confirmed).

## Resume status

Fresh run, no prior state for `run_id=sizing-channel-sensitivity`.
`progress.json` written before any reading, driver
(`analysis/sizing_channel_sensitivity.py`) committed at `ef63a52` before any
manifest, as its own commit, together with the prompt file. All steps
completed in one pass — **this is a full run, not partial.** Wall clock:
census + control ≈3s, full 135-cell grid ≈15s. All 135 grid cells ran fresh
(no prior `run_id` state to reuse).

---

> **Control reproduced: $179,944.91 / 20.8523% — matches Test 1's
> $179,944.91 exactly.**
> Exposure: `Add` events 137 of 195 total (70.3% — the ceiling on this
> channel), all 137 carrying a non-null size, 66 of 137 (48%) already
> clamped by cap before any perturbation. Measured `recommendedSize` noise
> (from Test 4 raw): 3.07pp median std, 7.69pp max (cross-checked exactly
> against the design session's own figures — see §2).
> **Headline — `jitter_1x` (exactly the measured noise) costs $0 (0.00%)
> and moves drawdown 0.00pp (see §5 ruler caveat)** — bit-identical to
> control at all 15 seeds. Compare Test 1's recommendation channel: $24,886
> (13.8%) at the -7.44pp shock. **The sizing channel is dramatically LESS
> expensive than the recommendation channel at the noise magnitudes each
> run actually measured** — not comparable pp-for-pp (different units), but
> in dollars, one channel costs tens of thousands and the other costs
> nothing.
> `size_ignored` (delete the field, always take the cap): **$179,944.91 —
> exactly tied with control, not better or worse.**
> Tier prediction (established > speculative): **cannot be tested as
> literally stated — no Type-A-established Add events exist in this
> corpus (see §4)**; the closest adaptation (Type-B/cap-50 vs
> Type-A-speculative/cap-15) shows the predicted DIRECTION for *potential*
> sensitivity but the predicted difference never materializes at the
> measured noise magnitude — both are $0.
> Latent falsy-zero defect: **confirmed not live** (0 nulls, 0 zeros among
> 137 Add events). **$0 API spend confirmed.**

---

## 1. What this run is, and what it is not

No LLM calls, no API spend, no DB writes. Same loader
(`sweep_cadence_and_session_model.load_events_dedup_on()`) and settled cell
(`swap_funding`, K=30, `new_calls_only`, X=2.5pp, `pooled`,
`per_event_date`, phase 0, `tie_seed=0`) as Test 1
(`analysis/analyst_sensitivity_harness.py`, **not modified** — this run's
driver, `analysis/sizing_channel_sensitivity.py`, is a new file that
imports the same loader/cell-runner pattern). This is **phase 0 only**,
same caveat as Test 1's own report: not directly comparable to the
phase-averaged $184,819/17.32% headline.

## 2. Step 1 — exposure census (`analysis/data/run_state/sizing-channel-sensitivity/census.json`)

| Metric | Value | Provenance |
|---|---|---|
| Total events | 195 | `census.json` → `n_total_events` |
| `Add` | 137 (70.26%) | `.action_counts.Add`, `.add_share_pct` |
| `Trim` | 29 | `.action_counts.Trim` |
| `Hold` | 29 | `.action_counts.Hold` |
| `Exit` | 0 | (not in `action_counts`) |
| Add events w/ non-null size | 137 / 137 | `.n_add_with_size`, `.n_add_null_size=0` |
| `recommended_size==0.0` on Add | 0 | `.n_add_zero_size` |
| size min / median / max | 8.0 / 45.0 / 60.0 | `.size_min/median/max` |

**Latent falsy-zero defect (`if recommended_size_pct else cap_pct`, both
`None` and `0.0` fall through to full cap): confirmed NOT LIVE** in this
corpus — 0 nulls, 0 zeros among 137 Add events, consistent with Test 4's
250/250-call finding of the same. Per the prompt, **not patched.**

**Measured `recommendedSize` noise, derived directly from
`analysis/test4_noise_floor/raw/*.json`** (50 transcripts × 5 runs each,
already on disk, $0):

| Statistic | This run's derivation | Design session's cross-check |
|---|---|---|
| median std | 3.0697pp | ~3.07pp |
| mean std | 3.4639pp | ~3.46pp |
| max std | 7.6942pp | ~7.69pp |
| median spread (max−min) | 8.0pp | ~9pp |
| max spread | 22pp | 22pp |

No material divergence — both derivations agree to within rounding.

**Clamp breakdown, by (type, tier)** among the 137 Add events (direct
query over the loaded corpus, not in `census.json`'s flat output —
recorded in `findings.md`):

| group | cap | n | size median | size min/max | already over cap |
|---|---|---|---|---|---|
| Type A, speculative | 15% | 44 | 40.0 | 8.0 / 55.0 | **43/44 (98%)** |
| Type B, established | 50% | 82 | 45.0 | 29.0 / 60.0 | 23/93 (Type-B combined) |
| Type B, speculative | 50% | 11 | 45.0 | 42.0 / 55.0 | (Type B ignores tier for cap) |
| Type A, established | 35% | **0** | — | — | — |

**Premise flag (Step 1b's own instruction, and Step 4's below): the
"established vs speculative" tier split cannot be run as the prompt
literally frames it.** The prompt's mental model is Type-A-established
(35% cap) vs Type-A-speculative (15% cap). But **no Add event in this
corpus is Type-A-established** — every "established" name here is Type B
(flat 50% cap), and Type B's cap does not vary by tier at all. So the
actual absorption boundary in this corpus is Type-A-speculative (cap 15,
98% already over cap → **near-total absorption**) vs Type B (cap 50, 23/93
= 25% already over cap → **more room for noise to express**), not
established-Type-A vs speculative-Type-A as the prompt's prose assumed.
**66 of 137 Add events (48%) are already clamped before any perturbation
is applied** — the ceiling this run's noise operates under is smaller than
the raw exposure count (70.3%) suggests.

## 3. Step 2 — the perturbation grid

`analysis/data/run_state/sizing-channel-sensitivity/cells.jsonl`, 9 cells ×
15 seeds = 135 cells, all run fresh, **15s wall clock total** (corpus load
2.5s + 135 cells at well under 0.1s each). `tie_seed` fixed at 0.

| cell | final min / med / max | max_dd min / med / max | seed spread |
|---|---|---|---|
| control | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| jitter_0.5x | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| **jitter_1x** | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | **none** |
| jitter_2x | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| jitter_3x | 179,921.74 / 179,944.91 / 180,373.06 | 20.8523% (all) | **±$428 max, $0 median** |
| biased_high (+1σ) | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| biased_low (−1σ) | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| size_ignored (None → full cap) | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |
| size_fixed (corpus median, 45.0) | 179,944.91 / 179,944.91 / 179,944.91 | 20.8523% (all) | none |

All figures: `cells.jsonl` → `cell_key` → `results.final_value` /
`results.max_dd`, min/median/max across the 15 seed draws. **Flagged
plainly, per the prompt's own instruction: every cell's seed spread is
either exactly zero or (jitter_3x only) negligible ($428 on a $180k base,
0.24%)** — the medians here are not just "a meaningful summary," they are
in most cases the *only* value that ever occurs. `max_dd` never moves by
even 0.01pp in any cell at any seed, including jitter_3x.

**Domain clamp**: corrupted `recommended_size` was clamped to `[0, 100]`
(no observed shock in this grid actually hit either bound — jitter_3x's
worst single value stayed inside the corpus's own historical range).

## 4. Ruler caveat — drawdown figure named, not what the prompt asked for

**Premise flag, following Test 1's own precedent on unavailable
benchmarks.** The prompt asks for **daily-marked** drawdown as primary
(§0/§5.1 of the 09-05 state-of-play: session-sampled understates true
drawdown by 1.9–8.3pp because the session-boundary sampling grid steps
over troughs). `run_session_sweep_cell` — the same settled-cell driver
Test 1 reused — records `daily_snapshots` **only at session dates**
(`sweep_cadence_and_session_model.py:957-959`, comment: "only recorded AT
session dates for this lightweight session harness"), so its `max_dd` is
the **session-sampled** ruler, not daily-marked. Computing a true
daily-marked drawdown would require re-running the simulator at daily
granularity — out of this run's scope (same class of gap as Test 1's
missing EW benchmark). **All drawdown figures in this report, including
Test 1's own $24,886/13.8% comparison figure, are session-sampled** — that
comparison figure itself was reported on the session ruler by Test 1's own
driver, so the two are at least ruler-consistent with each other, but
neither is the daily-marked figure the current state-of-play prefers.
Given every cell in this run's grid shows **zero movement in drawdown at
all** (not a small movement — literally 20.8523% in every cell but the
control), the ruler choice does not change this run's conclusion, only its
comparability to a hypothetical daily-marked re-run.

## 5. Mechanism — why the sizing channel's measured noise costs $0 (diagnostic, not a grid cell)

Confirmed the harness actually threads `recommended_size` through
correctly (not a silent no-op) by forcing an extreme, unrealistic shock:
setting **every** Add event's `recommended_size` to 5.0 (well below every
cap) moves final value from $179,944.91 to $141,031.72 (**−$38,913,
−21.6%**). Isolating by group: forcing only Type-B Add events to 5.0 →
**−$32,223.65**; forcing only Type-A-speculative Add events to 5.0 →
**−$1,242.92**. So essentially all of this channel's *potential*
sensitivity lives in the Type-B (cap-50) cohort, matching the prompt's
cap-headroom intuition.

But this sensitivity is **not symmetric**. Forcing `recommended_size=None`
on every Add event (`size_ignored` — Type-B target rises from a typical 45
to the full 50% cap, a +5pp shift in the *opposite* direction from the
forced-to-5 test) produces **exactly $0 change**, isolated to Type-B or
not.

**Mechanism, confirmed by direct trace of the allocator's own code**
(`_decide_add`, both the standalone `allocator_v2.py` and the inlined copy
in `sweep_cadence_and_session_model.py:853-870`): the **X=2.5pp/session
throttle** means realized position weight almost never reaches its
*target* within a quarter before the next call resets the target again.
Raising the target from ~45 to 50 (or to whatever value jitter/bias/fixed/
None produces, since all of them land at or above the pre-corruption
target for the values actually in this corpus) changes nothing, because
the binding constraint is the session limit or available cash, **not** the
target ceiling — this matches the prompt's own framing exactly (§ "the
mechanism," `X` throttles speed, not destination) but goes one step
further: **at this corpus's noise magnitude, X does not just slow
convergence to a different target — it makes the target's exact value
almost irrelevant**, because convergence never gets close enough to
either value to tell them apart within the observation window. Only when
the target is pushed *below* a position's already-accumulated size (the
forced `=5` test) does a different code path bind (`delta_dollars <= 0`,
`_decide_add` returns no trade at all, halting further adds) — and the
measured noise (median std ~3pp on values with median 40-45) essentially
never crosses that threshold from above.

## 6. Step 4 — tier split against the pre-registered prediction

**Cannot be run as literally specified** (§2 above: zero Type-A-established
Add events exist). Adapted to the closest available split, Type-B
(cap 50, "established"-tagged 82/93 of the cohort) vs Type-A-speculative
(cap 15, 44 events):

- **Potential sensitivity** (the forced-to-5 diagnostic, §5): prediction's
  DIRECTION holds — Type-B is ~26x more sensitive than Type-A-speculative
  ($32,224 vs $1,243 under an identical extreme shock).
- **Measured-noise sensitivity** (the actual grid, §3): prediction **fails
  to materialize** — both groups show $0 cost at every jitter/bias/
  ignored/fixed cell. The cap-headroom mechanism the prediction describes
  is real (§5 confirms it exists), but it never activates at the noise
  magnitude Test 4 actually measured, because the X-throttle dominates
  first (§5).

**State plainly, per the prompt's Step 4 instruction**: the tier
prediction as stated (established matters more than speculative because
of cap headroom) is **technically correct in mechanism but empirically
inert at the measured noise level** — report both halves rather than
picking one.

## 7. Step 5 — reading (report, do not decide)

1. **Is `recommendedSize` instability a real risk or an absorbed one?**
   At the magnitude Test 4 actually measured (median std ~3pp, max
   ~7.7pp, even tripled to ~9-23pp in `jitter_3x`), it is **an absorbed
   risk** — every cell in this grid ties control to the cent, with one
   exception (`jitter_3x`) whose worst deviation is $428 (0.24%) on a
   single seed. The field's 96% instability rate (Test 4) is, on this
   backtest's own settled configuration, **cosmetic** — X and the caps
   are doing their job, more completely than the prompt's own framing
   anticipated (it hedged "do not conclude X absorbs the noise without
   measuring" — this run measured it, and at this noise scale, it does).

2. **Does `size_ignored` beat `control`?** **No — it ties it exactly**,
   to the cent, at every one of 15 seeds. Deleting `recommendedSize`
   entirely and always taking the cap performs **identically** to keeping
   the analyst's sizing, not better and not worse. **This does NOT
   contradict §5.2's "the analyst's entire contribution is sizing"
   claim** — it says something narrower and specific to this backtest's
   mechanics: whatever value the analyst emits for `recommendedSize`
   barely matters in practice, because X=2.5pp/session almost never lets
   the portfolio converge close enough to *any* target (recommended or
   capped) to tell the two apart. The claim in §5.2 is about *which*
   field carries the analyst's information (sizing, not selection); this
   run's finding is that the sizing field's specific numeric value is,
   at this X setting, nearly moot. **Reported as a finding, not an
   amendment to §5.2's claim** — per scope boundary, no requoting done
   here.

**Explicitly out of scope, not attempted**: feeding score dispersion into
position sizing as an uncertainty signal (`allocator_v4.py`'s
low-coverage/high-dispersion pattern).

## 8. Deviations from the prompt, and why

1. **Step 4's tier split could not be run as literally specified** (§2,
   §6) — no Type-A-established Add events exist in this corpus. Adapted
   to the closest available grouping and reported both the mechanism
   (holds) and the measured-noise result (doesn't materialize) rather
   than silently substituting one comparison for the other.
2. **Daily-marked drawdown not available from this driver** (§4) — same
   class of gap as Test 1's missing EW benchmark; `run_session_sweep_cell`
   only records session-boundary snapshots. Reported session-sampled,
   clearly labeled, and noted that it does not change this run's
   conclusion since every cell shows zero drawdown movement regardless of
   ruler.
3. **A mechanism diagnostic (forced `recommended_size=5.0` and
   `=None` isolation tests) added beyond the prompt's named cells** — not
   a grid cell, not counted in the headline, run to confirm the harness
   was not silently a no-op before reporting nine consecutive
   bit-identical cells as a real finding rather than a driver bug.

## 9. What was deliberately not done

- No conclusion on whether `recommendedSize` should be redesigned,
  whether X=2.5pp should change, or whether the score-dispersion-as-
  uncertainty-signal idea (`allocator_v4.py`) is worth building — all
  scope-boundary calls for the design session.
- No re-scoring or amendment of §5.2's "entire contribution is sizing"
  claim — reported as a finding that narrows its practical import at this
  X setting, not as a correction.
- No daily-marked drawdown re-run — flagged as unavailable from this
  driver, not built.
- No investigation of whether a lower X (e.g., X=1.0, already known from
  the 09-05 state-of-play to be a close competitor on the daily ruler)
  would let the sizing channel's noise express itself more — a natural
  follow-on this run's scope excludes.

## 10. Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/sizing_channel_sensitivity.py').read())"` — passed, before commit.
- Control cell reproduced Test 1's exact reference to the cent
  ($179,944.91 / 0.20852310359539084) before any perturbation cell ran —
  hard-stop gate honored (would have stopped the run had it failed).
- `derive_measured_std()`'s figures cross-checked against the design
  session's own independently-stated numbers (§2 table) — agree to
  within rounding, no material divergence.
- The apparent driver-no-op was independently checked with an out-of-grid
  extreme shock (§5) before accepting nine bit-identical cells as a
  finding rather than assuming a bug.
- `git log --oneline -1 -- analysis/sizing_channel_sensitivity.py` confirms
  `ef63a52` (the recorded `driver_commit`) actually contains the driver
  file.

## 11. Wall-clock, cells run, cells reused

Census: <1s (pure computation over already-loaded corpus). Control gate:
~3s (corpus load 2.5s + 1 cell). Full grid: **15s** for 135 cells (9 cells
× 15 seeds), corpus loaded once. **All 135 grid cells + 1 control cell run
fresh** — first and only run of this `run_id`, nothing reused.

## Reproduction

```bash
cd analysis
python3 sizing_channel_sensitivity.py census    # Step 1, <1s
python3 sizing_channel_sensitivity.py control   # Step 1a gate, ~3s
python3 sizing_channel_sensitivity.py grid      # Step 2, ~15s, 135 cells
```

State: `analysis/data/run_state/sizing-channel-sensitivity/{progress.json,
cells.jsonl, findings.md, census.json}`, all committed on
`sweep/db-corpus-baseline`.

## Commits this session

| Commit | What |
|---|---|
| `ef63a52` | driver (`sizing_channel_sensitivity.py`) + prompt, before any manifest |
| `b475010` | control gate + census + full grid results, `findings.md` |

## Flags (per the prompt's own instruction)

- **Any cell whose seed spread is too wide for its median to be
  meaningful**: none — every cell's spread is zero except `jitter_3x`
  ($428 max deviation, 0.24%), which is if anything narrower than usual.
- **Any result contradicting a figure published in Test 1, Test 4, or
  state-of-play**: none directly contradicted; this run's session-ruler
  drawdown figures are consistent with Test 1's own (both session-sampled,
  §4). No previously published number is corrected here.
- **Whether `size_ignored` beating `control` would require §5.2's claim to
  be requoted**: moot — it did not beat control, it tied exactly. Had it
  won, that would have been strong evidence against "the analyst's entire
  contribution is sizing" (implying the analyst's sizing judgment
  subtracts value vs. a flat cap); tying it instead says the analyst's
  sizing judgment is *inert*, not *harmful* — a different, milder finding
  that this report does not use to amend §5.2.
