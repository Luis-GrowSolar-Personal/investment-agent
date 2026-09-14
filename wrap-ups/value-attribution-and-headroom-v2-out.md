# Value attribution and headroom, v2 — Stage A complete, Stages B–E pending (partial run)

**Run ID:** `value-attribution-and-headroom-v2`
**Result:** Stage A (Arms 0b and 0) ran successfully, all constraints held,
zero API spend, zero DB writes. Stages B, C, D, E are **not started** — this
is a budget-constrained partial run, stopped cleanly per the prompt's own
instruction ("if budget permits only one stage, run this one") and
`CLAUDE.md`'s resumability rule ("a partial run that resumes is worth far
more than a complete run that is lost").

---

## Lead-with summary

| Line | Value | Provenance |
|---|---|---|
| Arm 0b — universe only (starter-only buy-and-hold) | **$120,799.82** | `analysis/data/value_attribution_v2/stage_a_manifest.json` → `results.arm_0b_universe_only.final_value` (forward draw, deterministic, seed 0) |
| Test 1 — zero-information floor | **$120,800.00** | `docs/architecture/VERSION_REGISTRY.json` → `benchmarks.test1_zero_info_floor.figures.final_value` (forward draw, deterministic replay) |
| Arm 0 — always-bullish through the real allocator | **$173,102.24** | `stage_a_manifest.json` → `results.arm_0_always_bullish.final_value` (forward draw, seed 0) |
| Actual — real analyst + trend layer + allocator (`settled_control`) | **$179,944.91** | `docs/architecture/VERSION_REGISTRY.json` → `benchmarks.settled_control.figures.final_value` (forward draw, deterministic replay) |
| Total added by all three layers (Actual − Arm 0b) | **$59,145.09** | computed; `stage_a_manifest.json` → `reference_lines.total_added_by_three_layers` |

**Arm 0 ≤ control.** Always-bullish through the real allocator ($173,102.24)
loses to the real system ($179,944.91) by $6,842.67. Per the prompt's Sec5:
this is a finding about the promotion gate, not a failed run — Test 2's
−5.8pp always-bullish-relative lift describes a comparator that, run
end-to-end through the real allocator, loses money relative to the real
system. That figure is not evidence the system underperforms a viable
dollar-denominated alternative. Carry into `PROMOTION_GATE.md` §10 — **not
done this session**, flagged for the design session.

**The honest reading, so far as Stage A can say it:** the three layers
together are not small. $59,145.09 on a $100,000 base roughly doubles the
gain the universe floor alone produced ($20,799.82 gained by Arm 0b vs.
$79,944.91 gained by the full system). Stage A cannot say *which* layer —
that is Stage C, not run.

---

## What was verified before running anything

**0a — clean tree.** Confirmed via `git status --porcelain=v1 -uall`
before this run's own writes began. The tree had substantial unrelated dirty
state at session start (listed in the launch prompt); every file needed for
Steps 2–5 of this task (both prompts, both adjudication documents, both
wrap-ups) was read in full **before** stashing. `git stash push -u -m
"unrelated-wip-before-value-attribution-v2-run"` then gave a clean tree at
commit `c122a79`, `git_dirty: false`, which the driver records in its
manifest.

**0b — control/floor provenance, no discrepancy.** The prompt quotes
$179,944.91 (actual) and $120,800.00 (Test 1 floor) "from conversation."
Both resolved against `docs/architecture/VERSION_REGISTRY.json`:
`benchmarks.settled_control.figures.final_value` = 179944.91 and
`benchmarks.test1_zero_info_floor.figures.final_value` = 120800.00, both
`"quotable": true`, both `"reproducibility_value": "deterministic_replay"`
(a single forward value, not a median across draws), both tied to the same
tuple (`evaluation_prompt` 357b6b0b… v6, model claude-sonnet-4-20250514
retired, `allocator_v3.py` efc649d5…, corpus window 2022-01-01 to
2024-06-12 ALL16). **No discrepancy — the run proceeded per the prompt's own
instruction (discrepancy would have forced a stop; there was none).**

**0c — eval cache absence, confirmed again.** `analysis/data/evals/` is
absent from the working tree (gitignored, per the prior run's finding).
Sought again this session, still absent. Recorded in `PREREGISTRATION.json`
so a future session does not repeat the search.

**0d — pre-registration frozen.** `analysis/data/value_attribution_v2/PREREGISTRATION.json`
did not exist before this session (checked and confirmed absent — no
abort-on-mismatch triggered). Written before any arm ran, containing the
locked corpus definition, the two-date-axis clarification below, the
settled configuration, the control/floor provenance, the checksums, and
Arm 0b/0's definitions. Stage B–D fields are present but explicitly marked
`"NOT YET DEFINED"` / `"NOT YET APPLICABLE THIS SESSION"` — a future
session extending this run must fill those in **before** running those
stages, not treat their placeholder status as license to skip
pre-registration.

---

## A premise mismatch found and corrected (Step 4)

The prompt's Stage A section cites `sweep_funding_modes.py:199–206` for the
`starter_fired` logic (confirmed correct — that logic is real and matches
the quoted code exactly). But that file's own `main()` function does **not**
run the settled configuration used to produce `settled_control`
($179,944.91): its cell grid is `no_reserve` / `cash_reserve` at 5/10/20% /
`swap_funding` at 0pp and 10pp session limits — none of these is the settled
**X = 2.5pp** session limit.

The actual settled-configuration production driver, confirmed by reading
`analysis/tier_return_attribution.py` (which the launch prompt separately
asked to be verified) is `analysis/sweep_cadence_and_session_model.py`'s
`run_session_sweep_cell()`, called with:

```python
CELL = dict(cadence="30", scope="new_calls_only", funding_mode="swap_funding",
            limit_pp=2.5, execution_order="pooled",
            trim_budget_scope="per_event_date", veto_p=0.0)
events, type_fn, driver_fn, tier_fn = S.load_events_dedup_on()
r = S.run_session_sweep_cell(events, prices, type_fn, driver_fn, tier_fn,
                              phase_offset=0, seed=0, **CELL)
```

`tier_return_attribution.py` itself asserts this reproduces `$179,944.91` to
the cent. `analysis/value_attribution_v2_driver.py` (written this session)
uses this exact path and **re-asserts the reproduction before running Arms
0b/0** — confirmed: `final_value=$179,944.91 (MATCHES $179,944.91)`. Flagged
here rather than silently building Arm 0b/0 against `sweep_funding_modes.py`'s
non-matching grid, which would have produced a number not comparable to
`settled_control`.

**Injection mechanism, and why it is not the same construction as
`test1_zero_info_floor`.** `run_session_sweep_cell` (line 782) computes
`final_action = event.final_action or event.per_call_rec or "Hold"` at
simulation time from each event's already-trend-layer-computed
`final_action`. The driver sets `event.final_action` directly on every event
**after** `load_events_dedup_on()`'s `recompute_trend_layer()` has already
run and set it from the real trend verdict — this discards the real verdict
outcome for `final_action` but leaves the trend layer's computation itself
intact (it ran, its output is simply overwritten). `test1_zero_info_floor`,
by contrast, is documented in the registry as "every verdict forced to
Hold" — a corruption one layer upstream, at the trend-verdict level rather
than at `final_action`. These are different constructions of "make every
call resolve to Hold," and this run does not assume in advance that they
must coincide.

## A finding not anticipated by the prompt

**Arm 0b ($120,799.82) and `test1_zero_info_floor` ($120,800.00) coincide to
within 18 cents**, despite the different injection points described above.
This is recorded in `findings.md` as a finding, not smoothed into an
assumption: either the two injection points are mechanically equivalent for
this corpus (a Hold verdict flows through `apply_matrix` to the same
`final_action` regardless of which layer it enters at), or it is
coincidence. **Not investigated further this session** — it does not change
Stage A's conclusions (both numbers are still reported, and remain
conceptually distinct: Arm 0b is a starter-only buy-and-hold; the zero-info
floor is a corrupted-trend-verdict replay), but it is worth a design
session's attention before treating them as interchangeable in any future
table.

## Row-count reconciliation flagged for Stage B

`analyst_direct_scorer.py`/Test 2's corpus is 362 total scoreable rows (359
after the thin-year exclusion the prior wrap-up describes). The settled-config
session-sweep driver used for Stage A operates on **195** call-events after
`load_events_dedup_on()`'s same-day dedup. These are not the same
denominator — one counts Analysis rows scored by the direct-hit scorer, the
other counts simulator call-events after collapsing same-day duplicate
transcripts into one event. **Recorded in `progress.json`'s `next_action`
as something Stage B must reconcile explicitly** before computing the
always-hold/always-bullish base rates and hit rates the prompt's Stage B
specifies — using the wrong denominator there would silently misstate the
bearish base rate and the lift figures.

---

## What ran, what didn't

**Ran (Stage A only):**
- Arm 0b — universe only, starter-only buy-and-hold: `$120,799.82`
- Arm 0 — always-bullish through the real allocator: `$173,102.24`
- Reproduction assertion of `settled_control` before both: passed exactly

**Not run this session (marked `pending` in `progress.json`, with a
one-sentence `next_action` for each):**
- Stage B — lift against both baselines, bearish base rate, McNemar,
  ticker-block bootstrap
- Stage C — timing/selection permutations (within-ticker + cross-sectional),
  four ablation arms, trend-layer contribution surface, leave-one-call-out
- Stage D — oracle analyst-ceiling arm, allocator in-sample-maximum search
- Stage E — the deliverable three-layer table with bias-signed ceiling lines

Nothing in Stages B–E was started, approximated, or guessed at. No number
from those stages appears anywhere in this wrap-up.

---

## Constraints honored

- **Zero Anthropic API calls.** Asserted explicitly in the driver's first
  print statement, before Arm 0b's first call. No LLM invocation anywhere
  in this session.
- **Zero DB writes.** `load_events_dedup_on()` / `fetch_extra_fields()` are
  read-only `SELECT`s, the same loader path every prior sweep in this
  project uses. Events are simulator-side dataclasses built fresh per
  invocation; `final_action` was overwritten only on that in-memory copy,
  never persisted.
- **No modification** of `docs/EVALUATION_PROMPT.md`, `server/lib/versions.js`,
  `docs/architecture/VERSION_REGISTRY.json`, or the production prompt.
- **Firewall held.** Stage A does not touch the oracle arm (Stage D, not
  reached) — the highest-risk spot the prompt names. No portfolio data
  reached the analyst/trend layers; no transcript content reached the
  allocator beyond what the real system already passes it (`final_action`,
  `recommended_size_pct`, `type_classification`, `tier`, `driver_count` —
  unchanged from the production path).
- **No price-cache refresh.** `price_cache.json` untouched, still last-dated
  2026-05-08 (the fundamentals-cache staleness warning printed and is
  expected, not fixed).
- **Known defects (AMD tier classification, `type_classifications.json` not
  read by prod) not touched, not repaired, not gated on.**
- **Branch `sweep/db-corpus-baseline` only.** No merge to `dev`, no push.
- **`.gitignore` updated** to add an exception for
  `analysis/data/value_attribution_v2/` (same reasoning as the existing
  `run_manifests/`/`run_state/` exceptions — this is a §10b citation record,
  not a regenerable cache) — this was necessary for `PREREGISTRATION.json`
  and the Stage A manifest to be committable at all; flagged as a deviation
  from "don't touch config" caution, but required by the prompt's own
  instruction to write `PREREGISTRATION.json` there and by `CLAUDE.md`'s
  reproducibility rule that a manifest be committed.

## Commits made

1. `d1597c5` — `feat: value-attribution-v2 -- Stage A driver, pre-registration, run state`
   (`.gitignore`, `analysis/value_attribution_v2_driver.py`,
   `analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`,
   `analysis/data/value_attribution_v2/PREREGISTRATION.json`). Driver
   committed before any manifest, as its own commit, per §10b.
2. `44207ae` — `data: value-attribution-v2 -- Stage A results (Arm 0b, Arm 0)`
   (`analysis/data/value_attribution_v2/stage_a_manifest.json`,
   `analysis/data/run_state/value-attribution-and-headroom-v2/cells.jsonl`,
   `analysis/data/run_state/value-attribution-and-headroom-v2/findings.md`,
   updated `progress.json`).

Both stage specific files only — no `git add .`/`git add -A` used anywhere
this session.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/value_attribution_v2_driver.py').read())"` — passed.
- The driver's own internal reproduction assertion against `$179,944.91` —
  passed exactly (`final_value=$179,944.91 (MATCHES $179,944.91)`), which is
  itself the strongest verification available: the driver would have
  printed `DOES NOT MATCH` and returned exit code 1 (refusing to run Arms
  0b/0) had the settled-config wiring been wrong.
- `git rev-parse HEAD` inside the driver confirms the recorded commit in the
  manifest actually matches the commit under which the driver ran.

## What was deliberately not done

- Stages B–E entirely, per the budget-discipline instruction quoted at the
  top of this document.
- Carrying the Arm 0 ≤ control finding into `PROMOTION_GATE.md` §10 — the
  prompt's Sec5 says to "write it up as such and carry it into
  `PROMOTION_GATE.md` §10," and this wrap-up records the finding, but the
  actual edit to `PROMOTION_GATE.md` is left for a session that also
  resolves F1/F2 in the same document, so §10 gets one coherent edit rather
  than three incremental ones across sessions.
- Investigating why Arm 0b and `test1_zero_info_floor` coincide to within 18
  cents — recorded as an open finding, not resolved.
- Reconciling the 362/359-row Test-2 denominator against the 195-event
  simulator denominator — recorded as Stage B's first task, not attempted
  here.

## Exact follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git checkout sweep/db-corpus-baseline
cat analysis/data/run_state/value-attribution-and-headroom-v2/progress.json
python3 analysis/value_attribution_v2_driver.py   # re-run Stage A idempotently; will re-assert
                                                   # the $179,944.91 reproduction and re-append
                                                   # to cells.jsonl (append-only -- dedupe on
                                                   # config_hash if re-running for real, not just
                                                   # to confirm reproducibility)
```

To resume this run and start Stage B, a future session should: read this
file and `progress.json`'s `next_action`, resolve the 362-vs-195 row-count
reconciliation first, then add Stage B's arm/seed definitions to
`PREREGISTRATION.json` before computing anything.
