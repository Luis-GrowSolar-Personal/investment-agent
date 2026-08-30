# SPWR root cause + cash instrumentation — wrap-up

**SPWR: Hypothesis A, because both accounts held exactly $0.00 cash on
2024-05-02 (and every day around it), so its $6,048 first-call starter
returned zero trades — no exception, no `skipped_events` entry. Cash was
below 1% of portfolio value on 88.7% of trading days, from 2022-02-16
onward (six weeks into a 2.33-year window). 95 of 99 Add-shaped decisions
(96.0%) were cash-limited or entirely unfunded; total shortfall
$2,369,889.**

No DB writes, no LLM calls, no cache refreshes. Still on
`sweep/db-corpus-baseline`, nothing committed to `dev`.

---

## A bug in the instrumentation itself, caught by the standing assertion

Before any of the numbers below: the first version of the funding-tracking
wrapper broke the ALL16 v3 reproduction — it returned $114,263 instead of
$141,837. Per the standing rule ("if it moved, that is a bug to report, not
work around"), stopped and diagnosed rather than accepting the number.

**Root cause:** the wrapper was defined as `def instrumented(**kwargs)`.
`simulator.py` decides whether to pass `tier`, `driver_count`, and
`is_first_call` to `decide_fn` by introspecting its signature
(`inspect.signature(decide_fn)`, checking `"tier" in sig.parameters` etc.).
A `**kwargs`-only signature has no named parameters at all, so none of those
checks matched — `tier`, `driver_count`, and `is_first_call` were silently
never passed to the wrapper, which meant they were never passed to the real
`decide_v3` inside it either. Every call ran with `tier=None`,
`is_first_call=False`, `driver_count=None`, silently changing every
tier-dependent cap and disabling every first-call starter.

**Fix:** rewrote the wrapper with an explicit signature mirroring
`decide_v3`'s exactly (`ticker, final_action, recommended_size_pct,
type_classification, portfolio, day_price, trade_date, prices_today,
tier=None, is_first_call=False, driver_count=None`), then forwards those
named parameters to `decide_v3` explicitly. Re-ran:

```
ALL16 v3 (instrumented): final=$141,837  (expected $141,837)
Assertion PASSED: instrumented run reproduces the uninstrumented result exactly.
```

**Every number below is from the corrected, assertion-passing run.**
Flagging this prominently since it's exactly the kind of instrumentation
mistake that would have silently corrupted the sweep if it had shipped
without the assertion.

## Two small, additive code changes (not behavior-changing)

`analysis/simulator/simulator.py` — added two fields to `DailySnapshot`,
both defaulted so no existing caller breaks:

```python
@dataclass
class DailySnapshot:
    ...
    cash_taxable: float = 0.0          # diagnostic only
    cash_tax_advantaged: float = 0.0   # diagnostic only
```

and populated them at the one place `DailySnapshot` is constructed
(`simulator.py`), from values (`taxable_acc.cash`, `tax_adv_acc.cash`)
already computed in that loop for the existing `cash_total` field — no new
computation, just also storing the per-account split instead of discarding
it:

```python
cash_total=taxable_acc.cash + tax_adv_acc.cash,
n_positions=n_positions,
baseline_values=baseline_values,
cash_taxable=taxable_acc.cash,
cash_tax_advantaged=tax_adv_acc.cash,
```

New scratch script `analysis/diagnose_spwr_and_cash.py` does the rest via a
decide_fn wrapper (see above) — no core file beyond the two additive
`DailySnapshot` fields was touched.

---

## Step 1 — SPWR root cause

**1. Cash balance in each account on 2024-05-02, and the days either
side:**

```
2024-04-29: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-04-30: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-05-01: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-05-02: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-05-03: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-05-04: taxable=$0.00  tax_adv=$0.00  combined=$0.00
2024-05-05: taxable=$0.00  tax_adv=$0.00  combined=$0.00
```

Both accounts are at exactly $0.00 for the entire week surrounding SPWR's
call. This is not a SPWR-specific event — by this point in the run, the
whole portfolio had been cash-starved for over two years (see Step 2).

**2. Was SPWR's event processed at all?**

```
SPWR events processed by decide(): 1
  {'date': 2024-05-02, 'ticker': 'SPWR', 'final_action': 'Trim', 'is_first_call': True, 'n_trades': 0}
```

Yes — `decide()` was called for SPWR, exactly once, with `final_action='Trim'`
(not `'Add'`) and `is_first_call=True`. Per `allocator_v3.decide()`'s logic:
since `is_first_call` is true and no position exists, the starter fires
first regardless of `final_action`; since both accounts had $0 cash, the
starter loop's `cash_avail <= 1e-6: continue` branch fires for both
accounts and appends nothing. Because `final_action` (`'Trim'`) is not in
`('Hold', None)`, execution falls through to `decide_v2`'s `Trim` path
(`_decide_trim`), which itself requires an existing position
(`total_shares = portfolio.position_shares(ticker); if total_shares <= 1e-9:
return []`) — none exists, since the starter never executed — so that
returns `[]` too. **Net result: `decide()` legitimately returns an empty
list.** `n_trades: 0` confirms it.

**3. `skipped_events` for SPWR:**

```
SPWR entries in skipped_events: 0
```

**Zero**, as the hypothesis predicted — an empty trade list from `decide()`
is indistinguishable, from the simulator's point of view, from "nothing was
recommended." There's no `InsufficientCash` exception (nothing was ever
attempted against `portfolio.execute_buy`), so nothing lands in
`skipped_events` either. **Nothing in the existing output records that SPWR
was ever wanted.**

**4. SPWR position at window end (2024-06-12):**

```
SPWR shares at window end: 0
SPWR position value at window end: 0.0
```

Confirms the position never opened, for the entire remaining six weeks of
the window (SPWR's only call was 2024-05-02, and nothing else acts on SPWR
absent a new call).

**5. Proof that ALL15 actually excluded SPWR** — universe lists and event
counts printed for both runs:

```
ALL16 universe list (16): ['AAPL','AMD','AVGO','GOOGL','MSFT','NVDA','ORCL','TSLA','AMPX','ENVX','EOSE','FSLR','QS','RUN','SPWR','TTD']
ALL16 event count (window): 148
ALL15 universe list (15): ['AAPL','AMD','AVGO','GOOGL','MSFT','NVDA','ORCL','TSLA','AMPX','ENVX','EOSE','FSLR','QS','RUN','TTD']
ALL15 event count (window): 147
ALL16 v3 final: $141,836.57
ALL15 v3 final: $141,836.57
Delta: $0.0000
```

**ALL15 genuinely excludes SPWR** (15 tickers, 147 events, SPWR absent from
the list) — this rules out Hypothesis B outright. The $0.00 delta is real,
not a test artifact: SPWR contributes literally nothing to either universe's
outcome because its only decision produced zero trades in both cases.

**Conclusion: Hypothesis A, confirmed on every one of the five checks.**
Hypothesis B is refuted directly by item 5.

## Step 2 — cash over the whole run (ALL16 v3, clean window)

```
Trading days: 894
Days with combined cash < 1% of portfolio value: 793 (88.7%)
First date cash hits the floor and stays there (>90% of remaining days): 2022-02-16
Cash as % of portfolio value -- min: -0.00%  median: 0.00%  max: 100.00%
```

- **88.7% of all trading days** in the 2.33-year window have combined cash
  under 1% of portfolio value.
- **Cash hits the floor just six weeks in** (2022-02-16, against a window
  start of 2022-01-01) and stays there for essentially the rest of the run.
- **Median cash share is 0.00%.** The `-0.00%` minimum is floating-point
  noise around zero, not a real negative cash balance (no `InsufficientCash`
  was raised uncaught — those are caught and logged to `skipped_events`,
  none of which mention a negative-balance condition).
- The `max: 100.00%` is trivially day one, before any trade has executed.

**This portfolio spent essentially its entire run — over two years — with
no meaningful cash reserve.**

## Step 3 — how often was the allocator rationing?

```
Total Add-shaped decisions (incl. first-call starters) with intended $>0: 99
  Fully funded:      4 (4.0%)
  Cash-limited (partial): 20 (20.2%)
  Entirely unfunded: 75 (75.8%)

Total dollar shortfall: $2,369,889.32
```

**96.0% of all Add-shaped decisions in the window were rationed in some
way** — either partially funded or entirely denied. Only 4 of 99 (4.0%) got
exactly what they asked for. This is not an edge case; it is close to the
normal operating condition of this allocator on this corpus.

**Full unfunded/partially-funded list** (date, ticker, intended $, actual $,
shortfall $; `[starter]` marks a first-call starter leg):

```
2022-02-01  GOOGL   intended=$    54,207  actual=$    45,478  shortfall=$     8,729  [starter]
2022-02-16  NVDA    intended=$    54,007  actual=$    20,915  shortfall=$    33,092  [starter]
2022-02-16  QS      intended=$     5,095  actual=$     4,611  shortfall=$       484  [starter]
2022-02-16  TTD     intended=$    20,380  actual=$         0  shortfall=$    20,380  [starter]
2022-02-17  RUN     intended=$     4,888  actual=$         0  shortfall=$     4,888  [starter]
2022-02-25  EOSE    intended=$     4,928  actual=$         0  shortfall=$     4,928  [starter]
2022-03-01  FSLR    intended=$     4,870  actual=$         0  shortfall=$     4,870  [starter]
2022-03-03  AVGO    intended=$    56,154  actual=$         0  shortfall=$    56,154  [starter]
2022-03-03  ENVX    intended=$    19,364  actual=$         0  shortfall=$    19,364  [starter]
2022-03-10  ORCL    intended=$    49,832  actual=$         0  shortfall=$    49,832  [starter]
2022-04-20  TSLA    intended=$    30,360  actual=$         0  shortfall=$    30,360
2022-04-26  MSFT    intended=$    35,121  actual=$         0  shortfall=$    35,121
2022-04-28  AAPL    intended=$    20,627  actual=$         0  shortfall=$    20,627
2022-05-03  AMD     intended=$    20,006  actual=$         0  shortfall=$    20,006
2022-05-10  TTD     intended=$    12,457  actual=$         0  shortfall=$    12,457
2022-05-11  ENVX    intended=$    12,002  actual=$         0  shortfall=$    12,002
2022-05-25  NVDA    intended=$    30,076  actual=$         0  shortfall=$    30,076
2022-05-26  AVGO    intended=$    34,312  actual=$         0  shortfall=$    34,312
2022-06-13  ORCL    intended=$    33,560  actual=$         0  shortfall=$    33,560
2022-07-20  TSLA    intended=$    28,062  actual=$         0  shortfall=$    28,062
2022-08-02  AMD     intended=$    17,844  actual=$         0  shortfall=$    17,844
2022-08-02  EOSE    intended=$    13,056  actual=$     4,679  shortfall=$     8,376
2022-08-09  TTD     intended=$    12,963  actual=$         0  shortfall=$    12,963
2022-08-10  ENVX    intended=$    13,363  actual=$         0  shortfall=$    13,363
2022-09-01  AVGO    intended=$    35,346  actual=$     1,324  shortfall=$    34,022
2022-09-12  ORCL    intended=$    36,882  actual=$         0  shortfall=$    36,882
2022-10-19  TSLA    intended=$    24,945  actual=$         0  shortfall=$    24,945
2022-10-25  MSFT    intended=$    24,172  actual=$     3,492  shortfall=$    20,681
2022-10-27  AAPL    intended=$    15,745  actual=$         0  shortfall=$    15,745
2022-11-02  RUN     intended=$     9,604  actual=$     3,847  shortfall=$     5,757
2022-11-09  TTD     intended=$     9,317  actual=$       550  shortfall=$     8,766
2022-12-08  AVGO    intended=$    29,386  actual=$         0  shortfall=$    29,386
2022-12-12  ORCL    intended=$    30,943  actual=$         0  shortfall=$    30,943
2023-01-25  TSLA    intended=$    25,676  actual=$         0  shortfall=$    25,676
2023-02-15  TTD     intended=$    10,820  actual=$     2,700  shortfall=$     8,120
2023-02-22  NVDA    intended=$    28,167  actual=$         0  shortfall=$    28,167
2023-02-22  RUN     intended=$     6,707  actual=$         0  shortfall=$     6,707
2023-02-28  FSLR    intended=$    11,137  actual=$         0  shortfall=$    11,137
2023-03-02  AVGO    intended=$    31,432  actual=$       572  shortfall=$    30,860
2023-03-09  ORCL    intended=$    36,977  actual=$         0  shortfall=$    36,977
2023-03-23  AMPX    intended=$     4,082  actual=$         0  shortfall=$     4,082  [starter]
2023-04-25  GOOGL   intended=$    26,934  actual=$     1,607  shortfall=$    25,327
2023-04-25  MSFT    intended=$    23,268  actual=$         0  shortfall=$    23,268
2023-04-26  ENVX    intended=$    11,702  actual=$         0  shortfall=$    11,702
2023-05-02  AMD     intended=$    16,714  actual=$         0  shortfall=$    16,714
2023-05-04  AAPL    intended=$    19,906  actual=$       890  shortfall=$    19,016
2023-05-10  TTD     intended=$     9,031  actual=$         0  shortfall=$     9,031
2023-05-24  NVDA    intended=$    32,461  actual=$         0  shortfall=$    32,461
2023-06-01  AVGO    intended=$    40,412  actual=$         0  shortfall=$    40,412
2023-06-12  ORCL    intended=$    45,389  actual=$         0  shortfall=$    45,389
2023-07-19  TSLA    intended=$    39,562  actual=$         0  shortfall=$    39,562
2023-07-25  GOOGL   intended=$    40,103  actual=$         0  shortfall=$    40,103
2023-07-25  MSFT    intended=$    36,561  actual=$         0  shortfall=$    36,561
2023-07-26  ENVX    intended=$    15,315  actual=$         0  shortfall=$    15,315
2023-07-27  FSLR    intended=$    15,157  actual=$         0  shortfall=$    15,157
2023-08-01  AMD     intended=$    21,604  actual=$         0  shortfall=$    21,604
2023-08-09  TTD     intended=$    10,077  actual=$         0  shortfall=$    10,077
2023-08-10  AMPX    intended=$    14,416  actual=$         0  shortfall=$    14,416
2023-08-23  NVDA    intended=$    33,246  actual=$       678  shortfall=$    32,568
2023-08-31  AVGO    intended=$    41,609  actual=$         0  shortfall=$    41,609
2023-09-11  ORCL    intended=$    44,256  actual=$         0  shortfall=$    44,256
2023-10-24  GOOGL   intended=$    29,210  actual=$         0  shortfall=$    29,210
2023-10-24  MSFT    intended=$    32,669  actual=$         0  shortfall=$    32,669
2023-10-31  AMD     intended=$    16,367  actual=$         0  shortfall=$    16,367
2023-10-31  FSLR    intended=$    13,400  actual=$         0  shortfall=$    13,400
2023-11-02  AAPL    intended=$    24,923  actual=$       316  shortfall=$    24,607
2023-11-09  AMPX    intended=$     7,786  actual=$       245  shortfall=$     7,541
2023-11-09  TTD     intended=$    10,411  actual=$         0  shortfall=$    10,411
2023-11-21  NVDA    intended=$    33,619  actual=$         0  shortfall=$    33,619
2023-12-07  AVGO    intended=$    43,340  actual=$         0  shortfall=$    43,340
2023-12-11  ORCL    intended=$    47,318  actual=$         0  shortfall=$    47,318
2024-01-30  AMD     intended=$    16,715  actual=$         0  shortfall=$    16,715
2024-01-30  GOOGL   intended=$    39,934  actual=$     5,963  shortfall=$    33,971
2024-01-30  MSFT    intended=$    42,607  actual=$         0  shortfall=$    42,607
2024-02-14  QS      intended=$     8,264  actual=$         0  shortfall=$     8,264
2024-02-15  TTD     intended=$    14,163  actual=$     4,712  shortfall=$     9,451
2024-02-20  ENVX    intended=$    17,821  actual=$         0  shortfall=$    17,821
2024-02-21  NVDA    intended=$    42,555  actual=$         0  shortfall=$    42,555
2024-02-27  FSLR    intended=$    18,529  actual=$         0  shortfall=$    18,529
2024-02-27  FSLR    intended=$    18,529  actual=$         0  shortfall=$    18,529   <- duplicate transcript, see below
2024-03-07  AVGO    intended=$    60,281  actual=$       148  shortfall=$    60,133
2024-03-11  ORCL    intended=$    53,241  actual=$         0  shortfall=$    53,241
2024-03-21  AMPX    intended=$    18,828  actual=$         0  shortfall=$    18,828
2024-04-25  GOOGL   intended=$    39,274  actual=$       965  shortfall=$    38,309
2024-04-25  MSFT    intended=$    17,921  actual=$         0  shortfall=$    17,921
2024-04-30  AMD     intended=$    22,636  actual=$         0  shortfall=$    22,636
2024-05-01  ENVX    intended=$    17,806  actual=$         0  shortfall=$    17,806
2024-05-01  FSLR    intended=$    17,806  actual=$         0  shortfall=$    17,806
2024-05-02  AAPL    intended=$    47,389  actual=$         0  shortfall=$    47,389
2024-05-02  SPWR    intended=$     6,048  actual=$         0  shortfall=$     6,048  [starter]
2024-05-08  TTD     intended=$     8,713  actual=$       287  shortfall=$     8,426
2024-05-09  AMPX    intended=$    18,547  actual=$         0  shortfall=$    18,547
2024-05-22  NVDA    intended=$    42,901  actual=$         0  shortfall=$    42,901
2024-06-11  ORCL    intended=$    62,413  actual=$         0  shortfall=$    62,413
2024-06-12  AVGO    intended=$    65,308  actual=$         0  shortfall=$    65,308
```

**Timing:** shortfall events split 28 (early third) / 30 (middle third) /
37 (late third) of the window, first at 2022-02-01 and last on the final
trading day, 2024-06-12. **Spread evenly across the entire run, not
concentrated at either edge** — this is chronic, not a one-time cash crunch.
The count trending slightly upward in the late third tracks portfolio value
growth (larger intended-target dollars per Add as the portfolio compounds,
same cash-flow problem, bigger absolute numbers).

**Data-quality issue found and flagged, not fixed:** the two identical
`2024-02-27 FSLR` rows above are not a script bug — there are genuinely
**two separate `Transcript` rows in the DB** for the same FSLR Q4 2023
call, same title, same date:

```sql
SELECT t.id, tk.symbol, t."callDate", t.title
FROM "Transcript" t JOIN "Ticker" tk ON tk.id=t."tickerId"
WHERE tk.symbol='FSLR' AND t."callDate"='2024-02-27';
```
```
 id  | symbol |      callDate       |                        title
-----+--------+---------------------+-----------------------------------------------------
 280 | FSLR   | 2024-02-27 00:00:00 | First Solar (FSLR) Q4 2023 Earnings Call Transcript
 284 | FSLR   | 2024-02-27 00:00:00 | First Solar (FSLR) Q4 2023 Earnings Call Transcript
```

This is also why FSLR's per-ticker window count was 11 rather than the
other tickers' 10 in the prior session's report — noted there as an
unexplained discrepancy, now root-caused. **Not deduplicated here** (that's
a DB write / data cleanup, out of scope for a read-only diagnostic) —
flagging for the design session, since a duplicate transcript means FSLR
gets evaluated (and, if it were `Add`, sized) twice on the same day in every
run that includes it.

## What this means for the sweep design (per the prompt's own framing)

**"If most Adds across the run were cash-limited, the allocator has been
rationing constantly — which means §4's arbitration rule and the
alphabetical tie-break have been deciding nearly every Add, and the
funding-mode axis (§5) is a first-order parameter rather than a
refinement."**

At 96.0% of Add-shaped decisions rationed and cash pinned near zero for
88.7% of trading days starting six weeks into a 2.33-year window, this
isn't a marginal case for that conditional — it's close to the ceiling.
Every sweep cell run on this corpus without accounting for this will be
comparing configurations whose actual differentiator, in practice, was
**who won the alphabetical tie-break in a chronically cash-starved system**,
not the nominal parameter being swept. This reframes the funding-mode axis
(§5) from "a refinement to test" to "the variable the rest of the sweep's
results are conditional on."

## Assessment

Both diagnostic threads confirm and quantify problems the design session
already suspected qualitatively (§4's arbitration rule, §11's known
defects, §5's funding modes) — this run turns them into numbers: 96%
rationing rate, $2.37M cumulative shortfall, cash floor reached in week six
of 122 weeks. The instrumentation itself (after the signature bug was
caught and fixed) reproduces the exact $141,837 baseline, so these numbers
are trustworthy inputs to the sweep design, not artifacts of measurement
error introduced this session.

## What was deliberately not done

- No cash reserve or swap-funding implemented — instrumentation only, as
  scoped.
- `ALLOCATOR_OPERATING_MODEL.md` not amended (§5's funding modes and §11's
  silent-failure defect already document what this run measured; not
  edited).
- No configuration selected, no design-session decision made.
- FSLR's duplicate transcript not deduplicated (flagged only).
- `price_cache.json` / `fundamentals_cache.json` untouched, no DB writes.

## Repo state left behind

Branch `sweep/db-corpus-baseline` (uncommitted):
- `analysis/simulator/simulator.py` — two new, defaulted `DailySnapshot`
  fields (`cash_taxable`, `cash_tax_advantaged`), populated at the existing
  construction site from values already computed there. No behavior change;
  confirmed by the $141,837 assertion.
- `analysis/diagnose_spwr_and_cash.py` — new, this session's diagnostic
  script. Designed to be reusable for the sweep (per the prompt's
  instruction) — the `funding_log`/`event_log` wrapper pattern can wrap any
  `decide_fn` version as long as its signature is mirrored exactly (the bug
  this session caught).
- `analysis/run_clean_window_baseline.py`, `analysis/run_db_corpus_baseline.py`
  — unchanged, from prior sessions.

`dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 diagnose_spwr_and_cash.py

# Reproduce the FSLR duplicate-transcript finding directly:
DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-)
psql "$DATABASE_URL" -c "
SELECT t.id, tk.symbol, t.\"callDate\", t.title
FROM \"Transcript\" t JOIN \"Ticker\" tk ON tk.id=t.\"tickerId\"
WHERE tk.symbol='FSLR' AND t.\"callDate\"='2024-02-27';
"
```
