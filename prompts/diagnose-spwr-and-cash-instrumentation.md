# SPWR root cause + cash instrumentation (task #77)

`wrap-ups/clean-window-baseline-v2-out.md` validated the harness — carried
forward, not redone. One result in it needs explaining before the sweep is
built: **ALL16 vs ALL15 came out at exactly $0.00.**

Exactly zero is not what "SPWR is a small position" looks like. A 5% first-call
starter on a $100k portfolio is ~$5,000 deployed for six weeks, and capital spent
on SPWR is capital unavailable to others. The delta should be small, not nil.

**Read-only. No LLM calls, no API spend, no DB writes, no cache refreshes**
(`price_cache.json` / `fundamentals_cache.json` stay frozen at 2026-05-11 — the
staleness warning is expected). Continue on `sweep/db-corpus-baseline`, same
clean window (2022-01-01 → 2024-06-12, ALL16, 148 events).

Write findings to `./wrap-ups/diagnose-spwr-and-cash-instrumentation-out.md`.

---

## Step 1 — SPWR root cause

Two candidate explanations. Distinguish them; do not assume either.

**Hypothesis A — no cash.** Both the v3 starter and `_decide_add` fund via:

```python
for account_name in ("tax_advantaged", "taxable"):
    if remaining <= 1e-6: break
    cash_avail = portfolio.accounts[account_name].cash
    if cash_avail <= 1e-6: continue      # silently skips
    ...
return trades                            # empty list if both accounts dry
```

If both accounts are empty on 2024-05-02, SPWR's starter returns `[]` — no
exception, no `skipped_events` entry, nothing. The position never opens and
nothing records that it was wanted.

**Hypothesis B — test bug.** The ALL15 run didn't genuinely exclude SPWR, so both
runs were identical. If so, the $0 delta means nothing and Step 2's premise is
unfounded.

Report, specifically:

1. Cash balance in each account on 2024-05-02 (and the days either side).
2. Whether SPWR's event was processed at all — was it in the filtered event list,
   did `decide()` get called for it, what did it return?
3. Whether `skipped_events` contains any SPWR entry.
4. SPWR's position shares and value at window end (2024-06-12). Zero confirms it
   never opened.
5. **Prove ALL15 actually excluded SPWR** — print the universe list each run used
   and its event count. ALL16 should load 148; ALL15 should load 147.

If B is the answer, say so and stop — Steps 2 and 3 rest on A.

## Step 2 — cash over the whole run

Instrumentation only. **No behavior changes.** For the ALL16 v3 clean-window run:

1. Cash balance (both accounts, and combined) as a daily series alongside the
   existing portfolio-value series.
2. Percentage of trading days where combined cash is below 1% of portfolio value.
3. The first date cash effectively hits the floor and stays there.
4. Cash as a share of portfolio value: min, median, max over the run.

## Step 3 — how often was the allocator rationing?

For every `Add` decision in the run (including first-call starters), record
whether the trade was **fully funded** (`buy_$ == delta_$`) or **cash-limited**
(`buy_$ < delta_$`, including `buy_$ == 0`).

Report:

1. Count and share of Adds fully funded vs cash-limited vs entirely unfunded.
2. Total dollar shortfall — summed `delta_$ - buy_$` across all cash-limited Adds.
3. The unfunded/partially-funded list: date, ticker, target %, intended $,
   actual $.
4. Whether the shortfall is concentrated early, late, or spread evenly across
   the window.

**This is the number that matters for the sweep design.** If most Adds across the
run were cash-limited, the allocator has been rationing constantly — which means
§4's arbitration rule and the alphabetical tie-break have been deciding nearly
every Add, and the funding-mode axis (§5) is a first-order parameter rather than
a refinement.

Note this instrumentation is a **prerequisite** for the sweep, not a
side-quest: without it, every sweep cell's result is uninterpretable, because a
cell could score differently purely from how many trades silently failed to
fund. Build it to be reusable — it will be carried into the sweep runs.

## Step 4 — report

Scope boundary: report, do not decide. Do not implement cash reserve or
swap-funding. Do not amend `ALLOCATOR_OPERATING_MODEL.md` (§5 already records
the three funding modes and §11 already records the silent-failure defect —
read them, don't edit them). Do not select a configuration.

Lead with:

> **SPWR: [hypothesis A or B], because [one line]. Cash below 1% of portfolio on
> X% of trading days, from [date]. Y of Z Adds were cash-limited, total shortfall
> $W.**

Then Steps 1–3 in order, with the unfunded-trade list in full. Include the exact
invocation for every run.

Flag plainly anything that contradicts the hypotheses above, and anything that
looks wrong even where a check passed.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, no DB writes, no cache refreshes.
- Instrumentation adds counters and series only — **no change to any allocation
  decision.** Assert the ALL16 v3 result is still $141,837 after instrumenting;
  if it moved, the instrumentation changed behavior and that is a bug to report,
  not to work around.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
