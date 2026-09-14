# Value attribution v2 — Stage D wrap-up: the ceiling, and whether the allocator can reach it

**Run ID:** `value-attribution-and-headroom-v2` (continuation — Stages A, B, C, C3 wrap-ups
are untouched). **Stage:** D. **Status: COMPLETE, Steps 0–5 all done.** Not a partial run.
**Cost: $0 in Anthropic API spend** (zero LLM calls made). **Zero DB writes** to any
stored `Analysis` row.

**Driver:** `analysis/value_attribution_v2_stage_d_driver.py`, committed at
`c08a56bb2f9f193680c86c0233df474797666c7a` (driver-only commit, before any manifest).
**Manifest:** `analysis/data/run_manifests/value_attribution_v2_stage_d_manifest.json`,
produced at commit `f4fbd950145f5266869042c3e93448dab254423e` (`git_dirty: false`).
**Pre-registration:** `analysis/data/value_attribution_v2/PREREGISTRATION.json` →
`stage_d` block, written *before* any arm ran.

---

## §0 — Defined terms

Plain-language settled configuration first: the allocator being measured rebalances
roughly once a month (a "session"), only when a new earnings call arrives, funds new
buys by selling from existing lower-priority holdings rather than by holding cash in
reserve, pools all of a session's cash together before deciding what to buy, and
resets its per-day trim allowance once per calendar date rather than once per call.

| Term | Meaning as used in this report |
|---|---|
| **`swap_funding`** | The settled funding rule: to buy a new position, the allocator sells (trims) other held positions rather than drawing from an idle cash reserve. |
| **`K` = 30** | The session cadence: the allocator re-evaluates roughly every 30 calendar days, not on every single call. |
| **`new_calls_only`** | Only tickers with a fresh earnings call in a session are eligible to be bought that session — the allocator does not re-scan the whole universe every session. |
| **`X` (session speed limit)** | A **per-position, per-session speed limit**, in percentage **points** of total portfolio value — NOT a budget for how many new tickers can be bought and NOT a cap on how big a position can eventually get. Example: at X=2.5pp, if the portfolio is worth $200,000, at most $5,000 can move into (or within) one position in one session, even if the model wants to buy much more; the rest waits for a later session. Step 4 of this run tests X = 2.5pp (today's setting), 10pp, and unlimited (no limit at all). |
| **`pooled`** | All of a session's sell proceeds are combined into one cash pool and then handed out in ranked order to that session's buy candidates, rather than each candidate being funded one at a time in isolation. |
| **`per_event_date`** | The daily trim allowance (see Type A/B below) resets once per calendar date, not once per individual call — matters only when several calls land on the same date. |
| **pp vs %** | "pp" (percentage points) is an absolute difference between two percentages (e.g. going from 25% cash to 27.5% cash is "+2.5pp"). "%" is a relative change (e.g. a return of 8%). This report uses "points," not "pp," in prose per the project's language rule, and reserves "%" for relative changes. |
| **cell / draw / forward draw** | A "cell" is one configuration (a fixed set of parameters). Every figure in this report is a **single deterministic replay** ("forward draw") of one cell — never a median across multiple random draws, because none of this stage's arms use randomized ordering. |
| **Type A / Type B** | Two position categories: Type A (single-driver company) caps at 35% of portfolio (15% if speculative); Type B (multi-driver platform company) caps at 50%. Neither cap changes in this run. |
| **Tier cap / ratchet / profit-take** | Standing allocator rules, unchanged in this run: a hard ceiling on position size by tier (Type A/B above); a graduated multi-quarter trim-then-exit sequence when a thesis weakens; and a rule that trims 25% out of any position that reaches 25% of the portfolio. None of these rules is disabled or altered anywhere in Stage D. |
| **The pet / capitulation model** | A separate, unrelated allocator behavior (§8 of `ALLOCATOR_OPERATING_MODEL.md`) where a position that crosses a size threshold can become "sticky" and resist being trimmed. `veto_p=0.0` in every cell this run touches, so this model is fully disabled and plays no role in any figure below. |
| **ALL16** | The frozen 16-ticker universe (AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA, AMPX, ENVX, EOSE, FSLR, QS, RUN, SPWR, TTD) every arm in this run trades within. |
| **Oracle / look-ahead ceiling** | An arm built by telling the system, in advance, which direction a stock actually moved over the following ~6 months — something no real analyst can know at call time. **Every oracle figure in this report is a look-ahead ceiling: a best-case bound on what a perfect analyst could be worth, not a result any real system could achieve.** |
| **D-both / D-up / D-down** | Three oracle arms. **D-both** replaces every one of the 195 real calls with the perfect (look-ahead) call. **D-up** replaces only the calls that turn out to be genuine winners (buy signals), leaving every other call as the real analyst actually made it. **D-down** replaces only the calls that turn out to be genuine losers (sell/avoid signals), leaving every other call real. |
| **Binding reason** | For every dollar the allocator tries to deploy into a buy, the driver records why it deployed less than intended: `"session limit"` (X capped it), `"target gap"` (nothing else was stopping it — it bought exactly what it wanted), or `"cash available"` (there wasn't enough cash even after selling donors). |

---

## Plain-language summary

**A perfect analyst — one that called every six-month move correctly — would have
returned $263,073.65 through the allocator as it is configured today (X=2.5 points),
against the real system's $179,944.91 and buy-and-hold's $195,584.28. This $263,073.65
figure is a look-ahead ceiling, not an achievable result: it assumes knowledge of the
future.** With the per-session speed limit removed entirely, the same perfect analyst
returns $510,894.01 — also a look-ahead ceiling. The real analyst, run through the same
unthrottled allocator, actually gets *worse*: $150,997.56, down from $179,944.91 at
today's setting. Perfect upside calls alone (real calls kept everywhere else) are worth
$243,917.54; perfect downside calls alone are worth $201,898.84. **On this evidence,
the analyst's ceiling is limited mainly by prediction, not plumbing** — a perfect
analyst already earns $83,128.74 more than the real system even fully throttled at
today's speed limit, so most of the available headroom has nothing to do with the
speed limit at all. Loosening the speed limit adds a further, separate slice of
look-ahead-only headroom that the real analyst cannot reach, because its calls, not the
throttle, are what is holding it back.

---

## Resume status

This is a continuation of run_id `value-attribution-and-headroom-v2`. Stages A, B, C,
and C3 were already `done` before this session (see
`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`). This
session executed **all of Steps 0 through 5 of Stage D in one pass — this is a complete
run, not a partial one.** `prompt_sha256_stage_d` was recorded alongside the existing
`prompt_sha256` / `_stage_b` / `_stage_c` / `_stage_c3` keys, none of which were
overwritten. `PREREGISTRATION.json`, `cells.jsonl`, and `findings.md` were extended,
never rewritten. C2 and C4 remain `pending`, exactly as instructed — **not attempted**
in this session.

---

## Step 0 — hygiene, pre-registration, firewall

**0a.** Tree was dirty at session start with unrelated in-flight work (an
`ec-fidelity-benchmark-1` progress file, two probe scripts, several handoff/prompt/
wrap-up files unrelated to this task). All were left unread beyond a `git status`
listing (none looked relevant to this run) and stashed:
`git stash push -u -m "unrelated-wip-before-stage-d"`. The driver was committed in its
own commit (`c08a56b`) before any manifest was written, confirmed by
`git show c08a56b:analysis/value_attribution_v2_stage_d_driver.py` returning the file.
The pre-registration edit was committed separately (`f4fbd95`) before the driver ran
for real. At manifest-write time: `git commit=f4fbd950145f`, `git_dirty=False`.

**0b.** `PREREGISTRATION.json` → `stage_d` was written **before** any arm ran (commit
`f4fbd95`, driver commit `c08a56b` at write time). It records:
- **Injection point: `per_call_rec`, not `final_action`** — confirmed against
  `sweep_cadence_and_session_model.py` lines 85–111 (`recompute_trend_layer`) and line
  782 (`run_session_sweep_cell` consumes `event.final_action`, which
  `recompute_trend_layer` already set from the oracle's `per_call_rec`).
- **Label encoding:** bullish → `Add`, neutral → `Hold`, bearish → **`Exit`** (not
  `Trim`) — named explicitly as **bound-loosening**: `Exit` gives full de-risking on
  every correctly-called decline, stronger than any real call in this corpus ever
  issued for a genuinely bearish outcome (13.9% catch rate at Trim/Exit combined, per
  Stage B).
- **Non-direction field synthesis:** for every overridden event, `thesis_health`,
  `credibility_delta`, `stumble_type`, `mitigation_track_record`, and
  `fresh_money_allocation` are all set to the single most supportive value consistent
  with the label (see `ORACLE_SYNTHESIS` in the driver) — named explicitly as
  **bound-loosening**, because it removes the friction a genuinely noisy real call
  would sometimes trigger against itself in `compute_trend_verdict()` /
  `rank_key()`.

**0c.** Firewall requirements restated and honored: oracle scores exist only in
`analysis/data/run_manifests/value_attribution_v2_stage_d_manifest.json` and this run's
own `run_state/` files — never in the DB, never in a shared eval cache. Labels derive
**only** from `analysis/data/price_cache.json` (SPY + the 16 tickers) via
`analyst_direct_scorer.PriceCache` — no transcript text and no portfolio/position state
is read anywhere inside `build_oracle_labels()`. D-up/D-down still read real
`Analysis` rows for the *non-overridden* events via `S.fetch_extra_fields` — this is
the same, pre-existing, unchanged read path every prior stage of this run has used; it
is a read, not a write, and does not touch portfolio state or leak into the analyst.
Every oracle figure below is labeled a look-ahead ceiling.

**0d. No-unlabelable-tail check: 0 of 195 events unlabelable — confirmed, matches the
prompt's expectation.** `price_cache.json` frozen at 2026-05-08 gives a labelability
cutoff near 2025-11-07 (2026-05-08 minus `FORWARD_DAYS`=182 days); the locked
population's last `call_date` is 2024-06-12, well inside it. See
`...manifest.json` → `results.label_report`.

---

## Step 1 — oracle labels

Population: the same 195-event, dedup'd, ALL16, call-date ≤ 2024-06-12 simulator
population locked in Stage B/C/C3 (`analysis/data/value_attribution_v2/
PREREGISTRATION.json` → `stage_b.populations.simulator_population`). Labels built with
`analyst_direct_scorer.py`'s own, unmodified `FORWARD_DAYS=182`, `DEAD_BAND=0.05`,
`BENCHMARK="SPY"` constants (imported, not reimplemented).

**Split:** bullish 83 (42.6%), bearish 85 (43.6%), neutral 27 (13.8%) —
`...manifest.json` → `results.label_report.label_counts` (a single deterministic
count, not a draw). This is directionally close to but not identical to Stage B's
ground-truth distribution (the Stage D prompt itself cites bearish at 42.1% of
events); the ~1.5-point gap is attributable to Stage B's scorer population (n=359,
thin-year-filtered, no simulator call-date ceiling) differing from this run's
195-event simulator population, not to any difference in label logic.

---

## Step 2 — the ceiling under today's allocator

D-both at X=2.5 points (today's settled speed limit), run through the real,
unmodified trend layer and allocator.

**Final value: $263,073.65** (`...manifest.json` → `results.step2_ceiling_x2_5.
final_value`, single deterministic replay) — **a look-ahead ceiling, not an achievable
result.** +$83,128.74 vs. the real control ($179,944.91) and +$67,489.37 vs.
buy-and-hold ($195,584.28). **The pre-registered "lands at or below control" finding
did NOT occur** — the ceiling sits well above the real system.

**Two-level sanity check:** call-level hit rate 195/195 = **100%**, and — unlike the
prompt's stated expectation — the `final_action`-level hit rate is *also* 195/195 =
**100%**, so the trend-layer-override gap the prompt anticipated did not appear.
Reported as a finding, not a failure: because the non-direction field synthesis was
pre-registered as deliberately never conflicting with the oracle's own direction, the
trend layer has nothing left to override. This is a direct, expected consequence of
that (named, bound-loosening) synthesis choice, not evidence the label derivation
disagrees with the scorer.

**What binds:** of 71 funding events, 69 (97.2%) bind on `"session limit"`, 2 (2.8%) on
`"target gap"`, 0% on `"cash available"` — the *same* dominant binding reason Stage C3
found in the real control. Even a perfect analyst is overwhelmingly throttle-bound at
X=2.5.

**Cash / deployment:** average cash share 50.83%, dollar-years invested $182,248.07,
return per dollar-year invested $0.89 (`...manifest.json` →
`results.step2_ceiling_x2_5`).

---

## Step 3 — the ceiling split by direction

All three arms at X=2.5 points, real, unmodified allocator.

| Arm | Final value | Δ vs. control | Events overridden | Final calls changed vs. real | Binding |
|---|---|---|---|---|---|
| D-both | $263,073.65 | +$83,128.74 | 195 | — | 97.2% session limit |
| D-up | $243,917.54 | +$63,972.63 | 83 | 22 | 48.2% session limit / 50.0% cash available / 1.8% target gap |
| D-down | $201,898.84 | +$21,953.93 | 85 | 85 | 100% session limit |

(`...manifest.json` → `results.step3_directional_split`, each a single deterministic
replay.)

D-up overrode 83 events but changed only 22 final calls — most bullish oracle
overrides coincided with what the real analyst already, correctly, called there.
D-down overrode 85 events and changed all 85 final calls — none coincided with the
real analyst's actual call on those same events, consistent with Stage B's finding
that the real analyst catches very few genuine bearish outcomes. **D-down landed well
above control (+$21,953.93), not near it** — the prompt's scenario ("D-down near
control would mean the downside half is worth nothing here") did not occur: downside-
only perfect calls are worth something even under today's allocator, though
substantially less than upside-only calls ($21,953.93 vs. $63,972.63).

---

## Step 4 — limited by prediction, or by plumbing?

Six cells: {real analyst, D-both} × {X = 2.5, 10, unlimited}. Nothing but X changes.

| X | Real analyst | D-both |
|---|---|---|
| 2.5 (settled) | **$179,944.91** | **$263,073.65** |
| 10 | $145,059.93 | $423,293.79 |
| unlimited | $150,997.56 | $510,894.01 |

(`...manifest.json` → `results.step4_grid`, each cell a single deterministic replay.)

Max cash share and dollar-years invested per cell, plus max peak-to-trough decline, are
in Step 5 below and in the manifest under `results.step4_grid.<cell>`.

**Finding that contradicts the prompt's own stated expectation (flagged explicitly, not
silently absorbed):** raising X *lowers* the real analyst's value (-$28,947.35 from
settled to unlimited), while it sharply *raises* D-both's (+$247,820.37). None of the
three pre-registered readings fits cleanly:

- "D-both@2.5 near control, D-both@unlimited far above → limited by plumbing" —
  D-both@2.5 ($263,073.65) is 46% above control, not near it, so this reading's
  premise fails.
- "D-both@unlimited also near control → limited by neither" — D-both@unlimited
  ($510,894.01) is 184% above control, so this reading also fails.
- "Real analyst improves as much as D-both when X rises → throttle binds both" — the
  real analyst moves in the *opposite* direction, so this reading fails hardest of the
  three.

**Best-supported reading, stated plainly rather than forced into one of the three
pre-registered options: the ceiling is limited mainly by prediction, not plumbing.**
Even fully throttled at today's X=2.5, a perfect analyst already earns $83,128.74 more
than the real system — most of the achievable headroom exists without touching the
throttle at all. The real analyst is not throttle-starved; it is prediction-starved,
and giving it more room to act (raising X) makes it worse because it lets wrong calls
compound faster. The additional ceiling unlocked by *also* loosening X ($263,073.65 →
$510,894.01, look-ahead only) is real but is headroom the real analyst cannot reach
regardless of X, because direction, not the session limit, is its binding constraint.

**Not raised or changed:** every cap, rule, and parameter other than X was left exactly
at the settled configuration in every one of the six cells.

---

## Step 5 — drawdowns

Raw figures only; no risk-adjusted ratio computed or used to rank arms.

| Arm | Max drawdown ($) | Max drawdown (%) | Date range | Largest single-quarter decline |
|---|---|---|---|---|
| D-both @ X=2.5 | $18,167.38 | 8.17% | 2024-03-21 → 2024-04-20 | -8.00% ($7,971.91), 2022Q1→Q2 |
| D-up | $24,488.93 | 12.10% | 2024-03-21 → 2024-04-20 | -12.94% ($12,895.80), 2022Q1→Q2 |
| D-down | $13,201.36 | 12.80% | 2022-04-01 → 2022-06-30 | -9.77% ($9,731.80), 2022Q1→Q2 |
| Real analyst @ X=2.5 | $21,501.56 | 20.85% | 2022-04-01 → 2022-12-27 | -12.73% ($12,679.72), 2022Q1→Q2 |
| Real analyst @ X=10 | $46,622.85 | 43.73% | 2022-04-01 → 2022-12-27 | -27.23% ($26,845.49), 2022Q1→Q2 |
| Real analyst @ X=unlimited | $50,203.81 | 46.80% | 2022-04-01 → 2022-12-27 | -34.07% ($29,497.18), 2022Q3→Q4 |
| D-both @ X=10 | $50,748.07 | 14.23% | 2024-03-21 → 2024-04-20 | -21.02% ($20,782.69), 2022Q1→Q2 |
| D-both @ X=unlimited | $52,954.97 | 12.65% | 2024-03-21 → 2024-04-20 | -16.86% ($16,672.23), 2022Q1→Q2 |

(`...manifest.json` → `results.step5_drawdowns`.)

D-both @ X=2.5 has the *smallest* drawdown of any arm in this stage despite the highest
final value at that X — consistent with Stage C3's finding that drawdown tracks how
invested an arm is, not how well it calls direction: D-both is only ~51% invested on
average (avg cash share 0.508) at X=2.5. The real analyst's drawdown worsens sharply as
X rises (20.85% → 43.73% → 46.80%) while D-both's stays modest and roughly flat (8.17%
→ 14.23% → 12.65%) — raising X lets the real analyst's wrong calls compound losses
faster, while a perfect analyst's gains are structurally protected by being correct.

---

## Limitations

- **Every oracle figure ($263,073.65; $510,894.01; D-up $243,917.54; D-down
  $201,898.84; and every "D-both" cell in the Step 4 grid) is a look-ahead ceiling, not
  an achievable result.** It assumes knowledge of the stock's actual forward return.
- **The ceiling is perfect only at the scorecard's horizon (182 days) and dead band
  (±5%), against SPY.** An analyst calling shorter or longer moves, or graded against a
  different benchmark, is outside this bound.
- **The oracle's non-direction fields are synthesized** (thesis_health,
  credibility_delta, stumble_type, mitigation_track_record, fresh_money_allocation),
  and they move `final_action` and swap-funding donor order through the trend layer.
  Both the label encoding (bearish → Exit) and the field synthesis were pre-registered
  as **bound-loosening** — the true ceiling under a stricter, less generous synthesis
  (e.g. bearish → Trim only, or reusing real, possibly conflicting non-direction
  fields) would very likely be lower than every oracle figure reported here.
- **Every figure describes this 16-company universe and this window, 2020 through
  mid-2024, with zero 2025 calls.** A prior run found this universe at the top of 25
  random draws.
- **The corpus is a score stream of unverified prompt vintage.**
- **No figure here carries a confidence range.** C2 and C4 have not run (both remain
  `pending`, explicitly out of scope for this stage).
- **F2 is unresolved:** everything in this run is SPY-benchmarked, which §3.1 of
  `PROMOTION_GATE.md` does not specify.
- **The Step 0d cutoff arithmetic (2025-11-07) checks out** on inspection — no
  correction needed there, despite an initial concern raised mid-session that turned
  out to be a misreading on this session's own part, not an error in the prompt.
- **Determinism was spot-checked, not exhaustively re-verified.** A brief interactive
  smoke-test run (before the driver was committed) produced X=10/unlimited figures
  within ~$190 of the final, committed, git-clean manifest run — plausibly floating-
  point/library-version noise between separate Python process invocations rather than
  a logic nondeterminism, but this was not chased further given this session's budget.
  **The manifest's committed, git-clean run (`f4fbd95...`) is the citable source for
  every figure in this report** — the smoke-test numbers were never cited above.

---

## Any gates that failed

**None of Step 2's hard-stop gates failed.** The call-level hit-rate gate (expected
~100%) passed at exactly 100%. No gate in this stage required a stop.

## Deviations from the prompt, and why

1. **The Step-2 trend-layer-override gap the prompt expected did not appear** (both
   call-level and `final_action`-level hit rates are 100%, not just the call-level
   one). This is reported above as a finding, not worked around — it follows directly
   from the (named, bound-loosening) non-direction field synthesis choice, which was
   deliberately built to never fight the oracle's own direction.
2. **Step 4's mechanical three-way classifier returned "mixed / inconclusive"** because
   none of the three pre-registered thresholds fit the data exactly as worded. Rather
   than forcing the data into one of the three, this report states the best-supported
   reading in prose ("limited mainly by prediction") with the actual numbers, per the
   prompt's own instruction to report a diagnostic that contradicts a prompt
   expectation as a finding, not to reach a forced-fit "close enough" answer.
3. **A momentary premise concern about the Step 0d cutoff date was raised, checked, and
   found to be a misreading on this session's own part** (see Limitations) — not a
   real prompt error, so nothing was changed in response to it.

## What was deliberately not done

- C2 (bootstrap on control-minus-Arm-0) and C4 (permutation tests) were left `pending`,
  per explicit instruction — not attempted this session.
- No cap, rule, or parameter other than X was ever raised, disabled, or changed.
- No AMD tier-classification defect or `type_classifications.json`-unread defect was
  touched or gated on.
- No price-cache refresh was performed; the staleness warning on
  `fundamentals_cache.json` (125 days old) printed during every run and was left as-is,
  per standing instruction.

## What's left for a future session / the design session

- Stage E (deliverable) remains `pending`.
- C2, C4, C5, C6 remain `pending`, out of scope for this stage.
- Whether to loosen the oracle's bound-loosening assumptions (Trim-only bearish
  encoding, real-not-synthesized non-direction fields) and re-measure a tighter ceiling
  is a design decision, not made here.

## Follow-up commands

```bash
cd analysis && python3 value_attribution_v2_stage_d_driver.py
```

```bash
python3 -c "import json; print(json.dumps(json.load(open('analysis/data/run_manifests/value_attribution_v2_stage_d_manifest.json'))['results']['step4_grid'], indent=2))"
```
