# Clean-window baseline, corrected — wrap-up

**Clean window 2022-01-01 → 2024-06-12, 148 events. Trend recompute:
trajectory nulls 3 (back to stored baseline, down from v1's 31), stored-vs-
recomputed agreement 100.0%. v1/v2/v3 = $112,118 / $116,286 / $141,837.
Ordering HOLDS.**

The v1 diagnosis was right: the trend layer was starved by history
truncation, not inert. With full pre-window history restored, both of Step
2's checks come back clean, ticker identity checks out for all 16 names, and
the v1≤v2≤v3 ordering holds with v3 also beating all four benchmarks on this
window. **Assessment at the end: yes, sound enough to build on**, with one
caveat about statistical weight (SPWR) already known and one about window
size (148 events) already flagged by the prompt itself.

No DB writes, no LLM calls, no cache refreshes. Still on
`sweep/db-corpus-baseline`, nothing committed to `dev`.

---

## Carried forward, not redone

- Clean window: 2022-01-01 → 2024-06-12 (`C`, first coverage failure TSLA
  2024-07-23). 148 transcripts, 100% v6 coverage.
- Two-sided cutoff in `load_call_events()` — unchanged from the prior
  session.
- `type_for_ticker` abort-if-absent assertion — unchanged, re-confirmed
  below.

## Step 1 — trend-history scoping fixed

Rewrote `analysis/run_clean_window_baseline.py` (same file, not a new one)
to load full history with **no `start_date`**, only `end_date=2024-06-12`:

```python
events_full = load_call_events(tickers=ALL16, end_date=C)
```

```
Full-history events loaded (end_date=2024-06-12, no start_date): 196
Of those, events that survive into the window [2022-01-01, 2024-06-12]: 148
Difference (pre-window history available to the recompute only): 48
```

**48 pre-window events** (2020-09-10 through 2021-12-31) are now visible to
`compute_trend_verdict` for establishing each ticker's trajectory, exactly
the context v1's truncated run was missing. `run_simulation` then applies
its own `start_date <= e.call_date <= end_date` filter
(`simulator.py`, unchanged, confirmed by inspection) to restrict actual
trading to the 148-event window — the recompute sees 196, the simulator
trades on 148.

## Step 2 — Gate 3, replaced: both checks pass

**Check 1 — null `trajectory` should return to roughly the stored level
(~3):**

```
3/148
```

**Matches the stored baseline exactly** (v1's stored-value baseline was
also 3). Down from v1's starved-history run of 31/148. **The fix took.**

**Check 2 — recomputed vs. stored `final_action` agreement:**

```
100.0% (148/148)
```

**Zero disagreements.** Per the interpretation fixed in advance by this
prompt: **high agreement → the recompute is faithful, and the DB's stored
trend fields were fine all along.** That retires the concern that opened
this whole diagnostic thread (`run-allocator-sweep-db-corpus-out.md`'s
Option A hypothesis) — for this specific window, reading the DB's
already-baked `finalAction` values would have given an identical result to
recomputing them fresh. The two-sided cutoff (removing pre-v6 contamination)
was the load-bearing fix; the in-memory recompute confirms it rather than
adding anything further, on this corpus slice.

## Step 3 — ticker identity validation

| Ticker | Price series first date | Transcript first date |
|---|---|---|
| AAPL | 2020-01-02 | 2021-01-27 |
| AMD | 2020-01-02 | 2021-04-27 |
| AVGO | 2020-01-02 | 2021-06-03 |
| GOOGL | 2020-01-02 | 2021-04-27 |
| MSFT | 2020-01-02 | 2020-10-27 |
| NVDA | 2020-01-02 | 2021-02-24 |
| ORCL | 2020-01-02 | 2020-09-10 |
| TSLA | 2020-01-02 | 2021-04-26 |
| AMPX | 2022-09-15 | 2023-03-23 |
| ENVX | 2021-01-05 | 2021-08-10 |
| EOSE | 2020-11-02 | 2021-05-12 |
| FSLR | 2020-01-02 | 2021-04-29 |
| QS | 2020-08-17 | 2021-05-11 |
| RUN | 2020-01-02 | 2021-05-05 |
| SPWR | 2023-01-03 | 2024-05-02 |
| TTD | 2020-01-02 | 2021-05-10 |

**Short price histories match the prompt's expected list exactly**: SPWR
(2023-01-03), AMPX (2022-09-15), ENVX (2021-01-05), EOSE (2020-11-02), QS
(2020-08-17). All five are confirmed SPAC-era/recent listings, not a data
artifact — no new short-history ticker was found beyond the ones already
named.

**Continuous-entity check** — every ticker's manifest `company` field across
all its transcripts:

```python
{'AAPL': {'Apple Inc.'}, 'AMD': {'Advanced Micro Devices, Inc.'},
 'AVGO': {'Broadcom Inc.'}, 'GOOGL': {'Alphabet Inc.'},
 'MSFT': {'Microsoft Corporation'}, 'NVDA': {'NVIDIA Corporation'},
 'ORCL': {'Oracle Corporation'}, 'TSLA': {'Tesla, Inc.'},
 'AMPX': {'Amprius Technologies, Inc.'}, 'ENVX': {'Enovix Corporation'},
 'EOSE': {'Eos Energy Enterprises, Inc.'}, 'FSLR': {'First Solar, Inc.'},
 'QS': {'QuantumScape Corporation'}, 'RUN': {'Sunrun Inc.'},
 'SPWR': {'Sunpower Corporation (prev. Solaria)'},
 'TTD': {'The Trade Desk, Inc.'}}
```

**Every one of the 16 universe tickers maps to exactly one company name
across its entire transcript history — no ticker names more than one
company.** SPWR's manifest entry itself carries the `(prev. Solaria)`
annotation, consistent with the already-established rebrand story. **Nothing
new or suspicious found beyond what was already flagged (SPWR/META, both
confirmed clean previously).** The RUBI/MGNI reuse case named in the prompt
as a known Type 2 example is outside ALL16 and wasn't re-checked here (not
asked to).

## Step 4 — the substitute correctness gate

**ALL16, full clean window, $100,000 initial, 50/50 split:**

| | Final value | Max drawdown |
|---|---|---|
| v1 | $112,118 | 49.6% |
| v2 | $116,286 | 47.1% |
| v3 | $141,837 | 45.6% |
| SPY | $113,980 | 25.4% |
| QQQ | $119,178 | 35.2% |
| TMFC | $120,512 | 33.0% |
| Equal-weight-of-universe | $120,427 | — (not computed for this baseline; see note) |

**Ordering v3 ≥ v2 ≥ v1 HOLDS**: $141,837 ≥ $116,286 ≥ $112,118. Each
allocator version improves on the last, exactly the shape the changelog
predicts (tier-aware caps → profit-take/no-average-down improvements each
add value).

**v3 vs. benchmarks — information, not pass/fail, as instructed**: v3
($141,837) beats all four — SPY ($113,980), QQQ ($119,178), TMFC
($120,512), and equal-weight ($120,427) — on this 2.5-year window. Also
worth noting plainly: **v3's max drawdown (45.6%) is nearly double SPY's
(25.4%)** — it wins on absolute return but takes on materially more downside
risk to get there, which is exactly the kind of thing a short, noisy window
can either overstate or understate; not treated as a verdict, just reported.

**ALL15 (SPWR excluded), v3 only:**

| | Final value | Max drawdown |
|---|---|---|
| v3 (ALL15) | $141,837 | 45.6% |

**Delta from ALL16: $0, exactly.** Confirms the prompt's prediction precisely
— SPWR's single transcript triggers a first-call starter position and then
never receives another decision for the rest of the window, so it never
diverges from a static, tiny starting allocation that nets to zero
difference in the final portfolio value at this precision. It is, as
described, a dead allocation rather than a modelled position.

## Flagged plainly, even where a gate passed

- **v3's drawdown roughly doubles SPY's** while beating it on return — a
  real risk/return tradeoff visible in this window, not a red flag about the
  harness, but worth carrying into the design session's read of "v3 beats
  benchmarks."
- **SPWR remains statistically inert** in this universe/window (confirmed,
  not just asserted) — the ALL16 vs ALL15 zero-delta is about as clean a
  confirmation as this kind of check produces.
- **Equal-weight-of-universe's drawdown was not computed** — the
  `equal_weight_value()` helper carried over from the prior session computes
  final value only (buy-and-hold, no periodic mark-to-market path retained),
  not a running drawdown series. Noted as a gap in this run's own tooling,
  not a finding about the corpus; would need a small addition (an
  equal-weight NAV series, not just start/end values) to report a drawdown
  figure honestly rather than guessing at one.
- Window size (148 events) is thin for a 5-K × 3-phase cadence sweep, as the
  prompt itself already flagged for the design session — reaffirming rather
  than re-deriving it.

## Assessment: is the harness sound enough to build the cadence sweep on?

**Yes**, on the evidence from this run — with the scope understood
precisely: sound for *this* clean-window slice (2022-01-01 to 2024-06-12,
148 events, ALL16 minus SPWR's practical absence). Every mechanical check
that could fail did not: coverage is exact, event counts match exactly, the
trend-layer recompute is faithful to the stored values (so there's no
lingering "which source is right" ambiguity), ticker identity is clean
across all 16 names, and the allocator-version ordering behaves exactly as
the design history predicts. The one number produced by an unverified/loose
tool in this run (equal-weight drawdown) is flagged above rather than
reported.

What this run does **not** establish: whether 148 events across 2.5 years
is enough raw material for a cadence sweep sliced into 5 values of K × 3
phases (the prompt's own closing note, carried forward rather than acted
on) — that's a statistical-power question for the design session, separate
from "is the machinery correct."

## What was deliberately not done

- No configuration selected, no spec amended, no §12 items resolved, no
  proceeding to the cadence sweep — all explicitly out of scope here.
- RUBI/MGNI identity check not re-run (outside ALL16, not asked for).
- Equal-weight drawdown series not built (flagged above as a tooling gap,
  not fixed).
- `price_cache.json` / `fundamentals_cache.json` untouched.
- `sync_trend_to_db.py` not run. No prose fallback for `type_classification`
  built.

## Repo state left behind

Branch `sweep/db-corpus-baseline` (uncommitted):
- `analysis/simulator/data.py` — unchanged from the prior session (two-sided
  cutoff already in place).
- `analysis/run_db_corpus_baseline.py` — unchanged, from an earlier session.
- `analysis/run_clean_window_baseline.py` — rewritten in place for this
  session's full-history fix; this is the version that produced every number
  in this report.

`dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 run_clean_window_baseline.py
```
