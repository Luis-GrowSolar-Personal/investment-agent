# How much does analyst quality actually matter

`docs/handoffs/2026-09-03-state-of-play.md` §7 Test 1. **Read §0 of that
document before starting** — it defines every term used here.

## Why this run exists

Anthropic retires models. `server/lib/versions.js` is pinned to
`claude-sonnet-4-6`, which `data/gate_ledger.json` entry 1 rejected with verdict
**HOLD** — a **−7.44pp** change in analyst lift against a **4.2pp** noise floor.
Prompt tuning has been tried as the answer four times (v7 through v10) and every
measured attempt regressed.

The question nobody has asked is the one that decides how much any of that
matters: **if the analyst gets worse by some amount, how much worse does the
portfolio get?** If a 7pp drop in analyst lift costs almost nothing, forced
model migration is an annoyance and scoring instability and look-ahead all fall
in importance together. If it costs a great deal, that is a fragility more
important than any prompt, and it must be known before execution is built on top
of this allocator.

**No LLM calls, no API spend, no DB writes.** This run perturbs the *already
stored* scores in memory. Nothing is re-scored and nothing is written back.

Clean window (2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON
`type_for_ticker`, unchanged caches, dedup **on**. Work on
`sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/analyst-sensitivity-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`analyst-sensitivity`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in `CLAUDE.md`.

**Write state before reading anything.** Create the directory and an initial
`progress.json` — every step `pending`, `next_action` "spec reading not yet
started" — as the very first action of the session. Then flush `cells.jsonl`
after every cell, update `progress.json` after every step, and append to
`findings.md` the moment a finding is established.

Running low on budget is a reason to stop cleanly with a precise `next_action`,
not to rush. **Step 2 is the highest-value single cell in this run — if budget
is tight, run Step 2 before the full Step 3 grid.**

## Step 0 — hygiene

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed **before** any manifest, as its own commit. Do not stage unrelated
working-tree changes — stash and pop. `testing/` stays gitignored.

## Step 1 — build the corruption harness

Perturb the structured score **after it is loaded and before the allocator sees
it**, in memory only. The firewall is unaffected: the allocator still receives
nothing but a score, it is simply a degraded one.

Implement four independent degradation modes, each parameterised by `q`:

| Mode | What it does | What it models |
|---|---|---|
| `uniform` | with probability `q`, replace `recommendation` with one drawn uniformly from {Add, Hold, Trim, Exit} | an analyst that is `q` fraction pure noise |
| `adjacent` | with probability `q`, move `recommendation` one step along the ordinal scale Add↔Hold↔Trim↔Exit, direction chosen at random | a subtly worse analyst — the realistic degradation |
| `optimistic` | with probability `q`, shift `recommendation` one step **toward Add** | a miscalibrated model, not a noisy one |
| `pessimistic` | with probability `q`, shift one step **toward Exit** | the same miscalibration, other direction |

`thesisHealth` must be moved consistently with `recommendation` wherever the
allocator reads both — state in the wrap-up exactly which score fields the
allocator consumes and which ones you perturbed. **Do not perturb a field the
allocator ignores and report it as a degradation.**

Corruption is stochastic, so it needs its own seed, separate from the
tie-break seed. Say which is which.

## Step 2 — the zero-information control (run this first)

**One cell, and the most informative in the run.** Replace *every* score with a
single constant — every call scored `Intact` / `Hold`, recommendedSize at its
neutral default — so the analyst carries no information whatsoever, and run the
settled configuration against it.

This is the floor. Everything the portfolio earns in this cell comes from the
universe, the deployment discipline and the concentration rules, and **none of
it from the analyst.**

Report its final value and drawdown against the four benchmarks and against the
uncorrupted settled result. **If the zero-information arm still beats the
benchmarks, say so plainly and put it at the top of the report** — it would mean
the analyst is not what produces the measured advantage, which is a larger
finding than anything else this run can produce.

## Step 3 — the sensitivity grid

| Axis | Values |
|---|---|
| **Mode** | `uniform`, `adjacent`, `optimistic`, `pessimistic` |
| **`q`** | 0.0 (control), 0.1, 0.2, 0.3, 0.5, 1.0 |
| **Configuration** | the §0 settled cell, unchanged: `swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp, `pooled`, `per_event_date` |
| **Draws** | 15 corruption seeds per cell — corruption is stochastic and needs its own variance |

`q`=0.0 must reproduce the uncorrupted result exactly in every mode. **Hard stop
if it does not** — that means the harness is perturbing something even at zero.

Per cell report final value min / median / max, max drawdown min / median / max,
distinct tickers held, and the gap to each of the four benchmarks.

## Step 4 — put the x-axis in the gate's units

**This is what makes the run answer the actual question, so do not skip it.**

`q` is not a unit anyone can act on. The gate measures the analyst in
**percentage points of lift over baseline** — entry 1's champion scored 4.94pp
and the challenger −2.5pp.

For every (mode, `q`) cell, use `analysis/analyst_direct_scorer.py` to compute
the **analyst-direct lift of the corrupted score set**, exactly as the gate
computes it. That converts the x-axis from an arbitrary corruption rate into
lift-pp, and makes the result directly readable against the ledger.

Then report the headline the whole run exists for:

> **A drop of 7.44pp in analyst lift — the exact regression the ledger
> measured — costs $X in final value and Ypp in drawdown.**

Also report the local gradient in dollars of final value per 1pp of lift, at the
champion's operating point rather than averaged over the whole curve.

If the scorer cannot be driven from perturbed in-memory scores without
modification, say so and report the relationship as far as it can be
established, rather than silently dropping the step.

## Step 5 — rules

**Rules 1, 2 and 4 unchanged.** Rule 2: overlapping 15-draw ranges are
**tied**, reported as tied, never ranked by median. Rule 4 scores against the
adopted **39.12%** ceiling on median drawdown across draws plus share-of-draws;
robust requires ≥ 2/3.

**State for every number whether it is a forward draw, a median across draws, or
a phase-averaged median.** This run is phase 0 only unless you run more; say
which.

**Note before starting.** The state of play §5.2 records that at this cell all
15 tie-break draws returned identical results — the seed had no effect, where
the spec's §5 reports a 0.9% ordering spread at 2.5pp in the per-call model.
**If your `q`=0 control shows the same zero spread across tie-break seeds,
report it** — it is an open question and a second independent observation is
worth having. It does not block this run: corruption seeds are a different axis
and will vary regardless.

## Step 6 — report

Scope boundary: **report, do not decide.** Do not adopt a model, amend a spec,
change `versions.js`, or resolve any §12 item.

Open with resume status, then:

> **Zero-information floor: $[X], [DD] — [beats / trails] the benchmarks.
> Sensitivity at the settled cell: a 7.44pp lift drop costs $[X] ([Y]%) and
> [Z]pp of drawdown. Gradient: $[X] per 1pp of lift. Shape: [linear /
> threshold / flat until X]. Most damaging mode: [mode]. Cells still passing
> the 39.12% bar: [list]. Verdict on forced model migration: [tolerable /
> serious], with the number that supports it.**

Flag plainly: any gate that fails, any rule that gives an uncomfortable answer,
any previously published number that turns out to be wrong, and whether anything
disturbs the settled configuration.

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop.**

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance — the manifest path and exact
  JSON key, or the commit and path.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
