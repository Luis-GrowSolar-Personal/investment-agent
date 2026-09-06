# Small-cap instability — does it cost anything?

Follow-on to Test 4 (`wrap-ups/test4-analyst-noise-floor-out.md`) and the
sizing-channel run (`wrap-ups/sizing-channel-sensitivity-out.md`). Read both
first, plus `docs/handoffs/2026-09-05-state-of-play.md` §4 (Test 1's
results, especially §4.2's dollar figures), §5.2 ("the allocator does not
select — it *weights*"), and §0 (the **ruler** term).

**Cost: $0 in Anthropic API spend.** No LLM calls. In-memory perturbation
over already-loaded scores, same harness pattern as Test 1 and the
sizing-channel run.

## Why this run exists

Test 4 found that `recommendation` — the categorical Add/Hold/Trim/Exit
verdict — flips across **identical** re-runs on **58-67% of small/micro-cap
transcripts**, against 0% for large, 8% for mid and 15% for megacap. That is
a striking measurement. **Nobody has measured what it costs.**

Test 1 measured the recommendation channel with corruption applied
*uniformly across all names*: a q=0.5 `adjacent` shock cost **$24,886
(13.8%)**. That does not answer this question, because the real pattern is
not uniform — it is concentrated almost entirely in speculative names that
are capped at 15% and subject to Rule 3 (no averaging down on speculative
losers).

The sizing-channel run is the precedent for why this matters: it found a
field with **96% instability** costs **exactly $0**, because caps and the
X=2.5pp throttle absorb it entirely. The same structural absorption may or
may not apply here. **Establish materiality before anyone designs a fix** —
that is the whole purpose of this run.

**Pre-registered prediction, to be confirmed or refuted, not assumed:**
given §5.2 (the allocator weights rather than selects), the 15% speculative
cap, and the sizing-channel precedent, the expected cost is **small**.
Report whichever way it goes; a prediction is not a gate.

## The distinction this run must actually isolate

A naive reading — "observed pattern costs less than Test 1's $24,886,
therefore small-cap noise is cheap" — would be **wrong**, because the
observed pattern also corrupts *far fewer events* than Test 1's uniform
q=0.5 did. Less noise costing less money is arithmetic, not a finding.

**The finding this run is after is whether noise concentrated in small caps
is cheaper than the same quantity of noise spread across all names.** That
requires holding the corruption *volume* constant and varying only its
*distribution* — the `uniform_equivalent` cell below. Design the driver so
that comparison is exact (same expected number of corrupted events, same
mode, same seeds), and state the realized corrupted-event counts per cell so
the reader can verify the volumes actually matched.

---

## Step −1 — resume protocol

`run_id` is **`small-cap-instability-materiality`**, state in
`analysis/data/run_state/<run_id>/`. Cheap deterministic cells (the
sizing-channel run did 135 cells in 15s). Checkpoint `progress.json`,
append `findings.md`, and write `cells.jsonl` per cell so a resume never
re-runs a finished cell.

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit. Work on
`sweep/db-corpus-baseline`. Do not commit to `dev` or `main`. **Do not
modify `analysis/analyst_sensitivity_harness.py` or
`analysis/sizing_channel_sensitivity.py`** — write a new driver alongside
them so both prior runs stay reproducible.

---

## Step 1 — census, control reproduction, and reconciling the flip rate

**1a. Reproduce the control exactly.** Settled configuration —
`swap_funding`, `K=30`, `new_calls_only`, `X=2.5pp`, pooled,
`per_event_date`, phase 0, `tie_seed=0`, via
`sweep_cadence_and_session_model.load_events_dedup_on()` and
`run_session_sweep_cell`. Expected `final_value` **$179,944.91**, the figure
both Test 1 and the sizing-channel run reproduced to the cent. **If it does
not reproduce, stop and report.**

**1b. Cap-tier assignment, stated explicitly.** The cap tiers used by Test 4
are a *sampling* classification, not the simulator's own `tier_fn`
(`speculative`/`established`) or `type_fn` (`A`/`B`). Use this mapping,
which is the project's own and is not being re-derived here:

| cap tier | tickers |
|---|---|
| megacap | AAPL, GOOGL, NVDA, MSFT, TSLA |
| large | AVGO, AMD, ORCL |
| mid | FSLR, TTD |
| small/micro | QS, AMPX, ENVX, EOSE, RUN, **SPWR** |

**SPWR is in the backtest corpus (ALL16) but was excluded from Test 4's
universe**, so it has no measured flip rate. Assign it the small/micro rate
and say so. Note that per state-of-play §5.2 its single event never funds
(`binding: cash available`), so it is immaterial either way — confirm that
still holds rather than assuming it.

**Report the event census**: total events, events per cap tier, and each cap
tier's share. Also report, from `tier_fn`/`type_fn`, how the cap tiers map
onto the simulator's own speculative/established and A/B classifications —
the sizing-channel run found **zero Type-A-established Add events** in this
corpus, so do not assume the mapping is the intuitive one. **A cap tier's
share of events is the ceiling on how much its noise can matter**; if
small/micro is a small share, carry that ceiling into every conclusion.

**1c. Reconcile the flip rate before using it.** Test 4's wrap-up reports
small/micro recommendation flips as **7/12 (58%)**. An independent pass over
the same saved raw output during the design session counted **8/12 (67%)** —
a one-transcript difference, most likely a definitional edge case (a null
`recommendation` in one run counted as a distinct value, or not). **Re-derive
the per-cap-tier flip rate directly from
`analysis/test4_noise_floor/raw/*.json`, state your definition of "flip"
explicitly, reconcile against both published figures, and say which is
right and why.** Use the reconciled rates as this run's `q` values. Do not
silently pick one.

Expected reconciled rates, as a cross-check (megacap 15%, large 0%, mid 8%,
small/micro 58-67%).

---

## Step 2 — the grid

Extend Test 1's `perturb_events` pattern to accept a **per-cap-tier `q`**
rather than one global `q`, perturbing `final_action` and `per_call_rec`
(and `thesis_health` in lockstep, exactly as Test 1 does — noting Test 1's
own docstring records that `thesis_health` is not read by `decide()` and so
contributes nothing). Leave `recommended_size` **untouched** — the
sizing-channel run established that channel is inert; this run isolates the
categorical one.

Mode is Test 1's **`adjacent`** (its "realistic" degradation) for the
primary cells, with `uniform` as a harsher variant on the headline cell
only. **15 corruption seeds** per cell, `tie_seed` fixed at 0, medians and
seed spread reported.

| cell | per-tier q | what it answers |
|---|---|---|
| `control` | all 0 | must equal $179,944.91 |
| `observed_pattern` | each cap tier at its own reconciled Test 4 rate | **the headline: what the instability we actually measured costs** |
| `small_micro_only` | small/micro at its rate, all others 0 | isolates the tier — removes the small megacap/mid contribution |
| `uniform_equivalent` | one flat q across ALL tickers, chosen so the **expected corrupted-event count equals `observed_pattern`'s** | **the real comparison: same noise volume, spread evenly instead of concentrated. Is small-cap noise structurally cheaper?** |
| `small_micro_q1` | small/micro at q=1.0, others 0 | ceiling — every small-cap verdict randomized |
| `small_micro_zero_info` | small/micro verdicts all forced to `Hold` | the zero-information floor for this tier: "what if the analyst said nothing at all about small caps?" |
| `observed_pattern_uniform_mode` | same q as `observed_pattern`, `uniform` mode | harsher error model, same distribution |

Report the **realized corrupted-event count** for every cell (not just the
intended q), so `observed_pattern` and `uniform_equivalent` can be verified
to have matched volumes.

---

## Step 3 — results, in Test 1's units

Report `final_value` and `max_drawdown` per cell, min/median/max across the
15 seeds.

**Ruler: report session-sampled and label it as such.** Do not attempt a
daily-marked figure. The sizing-channel run established (§4 of its wrap-up)
that `run_session_sweep_cell` records `daily_snapshots` only at session
dates, so its `max_dd` is session-sampled by construction; producing a
daily-marked figure would require a daily-granularity re-run, which is out
of scope here. Test 1's comparison figures are session-sampled too, so the
comparison is at least ruler-consistent — say so explicitly rather than
leaving an unlabelled drawdown in the report (09-05 §0).

Headline framing, in Test 1's units: Test 1's uniform q=0.5 `adjacent` shock
cost **$24,886 (13.8%)**. State plainly what `observed_pattern` costs, and
then — the comparison that actually matters — **what `uniform_equivalent`
costs at the same corruption volume.**

## Step 4 — reading (report, do not decide)

Answer these three, plainly, whichever way they go:

1. **Does the measured instability cost material money?** Give the dollar
   figure and the percentage of final value. If it is near $0, say so
   without hedging — that is a legitimate and useful result, and it is what
   the pre-registered prediction expects.
2. **Is small-cap noise structurally cheaper than the same volume of noise
   elsewhere?** `observed_pattern` vs `uniform_equivalent`. If yes, name the
   mechanism if it is visible (15% speculative cap, Rule 3's no-average-down
   on speculative losers, the X throttle, small share of events, or the
   first-call starter firing regardless of verdict per §5.2).
3. **What is the ceiling?** `small_micro_q1` and `small_micro_zero_info`
   bracket it. If even fully randomizing every small-cap verdict costs
   little, then the small/micro instability finding is **economically
   inert** on this configuration, and no prompt work, rubric work, or
   waiting-for-companies-to-mature is justified by it. Say that in those
   terms if the data supports it.

**Explicitly out of scope:** designing a small-cap rubric variant, the
paired rubric A/B re-scoring (a separate ~60-call, ~$6 run that should only
happen if this run shows material cost), the noise-adjusted-cap backlog item
(`docs/handoffs/2026-09-06-state-of-play.md` §8), and any change to
`EVALUATION_PROMPT.md`.

---

## Report

Scope boundary: **report, do not decide.** Do not modify Test 1's or the
sizing run's harness, any file under `analysis/simulator/`,
`EVALUATION_PROMPT.md`, `ALLOCATOR_OPERATING_MODEL.md`, `PROMOTION_GATE.md`,
or `gate_ledger.json`. No LLM calls. No DB writes; `SELECT` only, plus reads
of Test 4's saved `raw/*.json`.

Open with resume status, then:

> **Control reproduced: $[X] [matches $179,944.91 / DISCREPANCY]. Flip rate
> reconciled: small/micro [N]/12 ([X]%) — [7/12 published figure confirmed /
> 8/12 confirmed / neither, see §1c], definition: [stated]. Census:
> small/micro [N] of [M] events ([X]% — the ceiling). Headline —
> `observed_pattern` costs **$[X] ([Y]%)**, drawdown [moves Zpp /
> unchanged] (session-sampled). `uniform_equivalent` at matched volume
> ([N] vs [N] corrupted events): **$[X] ([Y]%)** — small-cap-concentrated
> noise is [cheaper / same / more expensive] than evenly-spread noise by
> [factor]. Ceiling: `small_micro_q1` $[X], `small_micro_zero_info` $[X].
> Compare Test 1's uniform q=0.5: $24,886 (13.8%). Verdict on materiality:
> [material / economically inert] at this configuration. $0 API spend
> confirmed.**

Flag plainly: any cell whose seed spread is wide enough that its median is
not a meaningful summary; any result contradicting a figure published in
Test 1, Test 4, the sizing-channel run, or state-of-play (name the figure
and the file); whether `observed_pattern` and `uniform_equivalent` actually
achieved matched corruption volumes (if not, the headline comparison is
invalid — say so rather than reporting it anyway); and — as the
sizing-channel run did — whether nine near-identical cells reflect a real
absorption result or a driver no-op, verified by an out-of-grid extreme
shock before the result is accepted.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no
  Linux package managers or path assumptions.
- **No LLM calls. No DB writes.**
- Write a new driver; do not modify the two existing harnesses.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — file, manifest path, JSON
  key, or table/column. Every drawdown must name its ruler.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
