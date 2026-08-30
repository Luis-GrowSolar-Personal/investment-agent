# Clean-window baseline — wrap-up

**Clean window: 2022-01-01 → 2024-06-12. 148 transcripts, 100% v6 coverage
(Gates 1 and 2 pass). Gate 3 (trend-layer recompute) FAILS: 3.4%
disagreement, under the ~5% floor. Per instruction, stopped before Step 5 —
no v1/v2/v3/benchmark simulation was run.**

No DB writes, no LLM calls, no cache refreshes. Still on
`sweep/db-corpus-baseline`, nothing committed to `dev`.

---

## Step 1 — clean-window boundary, computed empirically

Scanned every ALL16 (ticker, `callDate`) pair, sorted chronologically, and
found the first date at which v6-window coverage breaks:

```sql
SELECT t."callDate"::date, tk.symbol,
  bool_or(a."createdAt" >= '2026-05-02 12:33:23-04'
          AND a."createdAt" < '2026-06-27 16:26:16-04') as has_v6
FROM "Transcript" t
JOIN "Ticker" tk ON tk.id = t."tickerId"
LEFT JOIN "Analysis" a ON a."transcriptId" = t.id
WHERE tk.symbol IN ('AAPL','AMD','AVGO','GOOGL','MSFT','NVDA','ORCL','TSLA',
                     'AMPX','ENVX','EOSE','FSLR','QS','RUN','SPWR','TTD')
GROUP BY t."callDate", tk.symbol
ORDER BY t."callDate";
```

First coverage failure: **`2024-07-23`** (TSLA). The latest date `C` such
that every ALL16 transcript with `callDate <= C` has a v6-window row is
therefore **`C = 2024-06-12`**. Confirmed **zero violations** in
`[earliest event 2020-09-10, C]` — every ALL16 transcript up to and
including 2024-06-12 has at least one Analysis row inside the v6 window.

**C = 2024-06-12 is well after 2023**, so the "stop if C lands before 2023"
gate does not trigger.

**Start** of the run window: kept consistent with every other ALL16 runner's
convention, `max(earliest_event + 365 days, 2022-01-01)` = **2022-01-01**
(earliest event is 2020-09-10; +365 days = 2021-09-10, which is before
2022-01-01, so the floor wins).

**Per-ticker transcript counts, `[2022-01-01, 2024-06-12]`:**

| Ticker | Count |
|---|---|
| AAPL | 10 |
| AMD | 10 |
| AVGO | 10 |
| GOOGL | 10 |
| MSFT | 10 |
| NVDA | 10 |
| ORCL | 10 |
| TSLA | 10 |
| AMPX | 6 |
| ENVX | 10 |
| EOSE | 10 |
| FSLR | 11 |
| QS | 10 |
| RUN | 10 |
| **SPWR** | **1** |
| TTD | 10 |
| **Total** | **148** |

**Flagging plainly, even though it doesn't fail the stated gate:** SPWR has
exactly **one** transcript in this window (2024-05-02). Its other calls in
the corpus (2024-08-14 onward) all fall after `C`. A "16-ticker universe"
where one ticker contributes 1 of 148 events (0.7%) is not really a 16-name
backtest for that ticker — SPWR is present in name only. This doesn't
violate the ~90%/100%-coverage gates as written (which are about *whether* a
transcript has a v6-window row, not about *how many* transcripts a ticker
has), but it's a real distortion the design session should know about before
treating this window's SPWR contribution as meaningful.

## Step 2 — two-sided cutoff added to the loader

`analysis/simulator/data.py::load_call_events()` — added
`analysis_created_after`, defaulted to `'2026-05-02 12:33:23-04'`, appended
to the same `where_clauses` list as the existing `analysis_created_before`
(so both SQL blocks pick it up automatically, as before):

```python
def load_call_events(
    tickers: Optional[list[str]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    analysis_created_before: Optional[str] = "2026-06-27 16:26:16-04",
    analysis_created_after: Optional[str] = "2026-05-02 12:33:23-04",
) -> list[CallEvent]:
    ...
    if analysis_created_before:
        where_clauses.append('a."createdAt" < %s')
        params.append(analysis_created_before)
    if analysis_created_after:
        where_clauses.append('a."createdAt" >= %s')
        params.append(analysis_created_after)
```

Both parameters default to the v6 window and are independently overridable
with `None`. Verified: a transcript whose only/latest Analysis row falls
outside `[after, before)` is **dropped from the result set entirely**
(matches the "latest per transcript" join requiring the row that satisfies
the window bound to also be the global max) — it does not fall back to a
stale pre- or post-window row. This is exactly the intended behavior: a hole
in coverage should be visible as a missing event, not silently filled with
wrong-vintage data.

## Step 3 — trend layer recomputed in memory

New scratch script, `analysis/run_clean_window_baseline.py` (not committed).
`recompute_trend_layer()` mirrors `data_from_cache.py::attach_trend_verdicts()`
— same per-ticker chronological ordering, same history-dict construction,
same `tier_for_ticker` snapshot, same `compute_trend_verdict` /
`apply_matrix` / `compute_final_confidence` calls from `trend_analyst.py`.
The one necessary difference: `attach_trend_verdicts()` reads
`freshMoneyAllocation` / `credibilityDelta` / `mitigationCapabilityTrackRecord`
/ `stumbleType` by re-parsing a cached eval **file**; there is no file here,
so a small read-only helper (`fetch_extra_fields()`) pulls the same four
values from the corresponding `Analysis` columns for the same
(ticker, call_date) pairs, same v6-window bounds. **Nothing written back to
Postgres** — the recompute mutates only the in-memory `CallEvent` list.

## Step 4 — verification gates

**Gate 1 — coverage is 100% for all 16 tickers: PASS.** Every ticker has
`count > 0` (table above; SPWR's count of 1 still counts as covered, per the
gate's literal definition).

**Gate 2 — no dropped events: PASS.** Direct SQL count of `Transcript` rows
for ALL16 in `[2022-01-01, 2024-06-12]`:

```sql
SELECT count(*) FROM "Transcript" t
JOIN "Ticker" tk ON tk.id = t."tickerId"
WHERE tk.symbol IN (...ALL16...)
  AND t."callDate" >= '2022-01-01' AND t."callDate" <= '2024-06-12';
-- 148
```

`load_call_events(tickers=ALL16, start_date=2022-01-01, end_date=2024-06-12)`
also returns exactly **148** events. Exact match.

**Gate 3 — the trend layer should now materially disagree with raw
`per_call_rec`: FAIL.**

```
Stored (DB) final_action vs per_call_rec disagreement:      6/148 (4.1%)
Recomputed final_action vs per_call_rec disagreement:        5/148 (3.4%)
```

**3.4% is under the ~5% floor Step 4.3 set. Per instruction, stopping here
rather than running Step 5's simulation.** The recompute did not just fail
to "materially exceed" the stored rate — it came in slightly *lower*.

**A likely, and important, confound, flagged rather than acted on:**
`recompute_trend_layer()` was fed only the events already restricted to
`[2022-01-01, 2024-06-12]` — i.e., **each ticker's trend history starts at
the window boundary, not at its actual first-ever call**. `AAPL`'s first
in-window call (2022-01) is treated by the recompute as `AAPL`'s *first call
ever* (no prior history to detect a trend against), when in reality AAPL has
years of pre-2022 calls that `attach_trend_verdicts()`'s file-cache
equivalent would have had visibility into when run over the *full* corpus.
This is consistent with a second symptom: **null trajectory rose from 3 to
31 (out of 148) after the recompute** — `compute_trend_verdict` returning
"insufficient history" far more often than the DB's originally-stored
values, which were computed with full ticker history available at the time.
**This strongly suggests the 3.4% figure understates what a correctly-scoped
recompute (one that loads full per-ticker history and only *reports* the
windowed slice) would show, rather than confirming the trend layer is
inert.** Not corrected here — Step 4's gate is written as a hard stop on the
number as measured, and this run measured it as specified. Flagging the
confound for the design session rather than re-running with a fix, since
"do not start guessing" is the standing instruction once a gate fails.

**Gate 4 — `type_for_ticker` resolves for all 16, aborts if not: PASS.**
Printed `type_for_ticker resolves for all 16 tickers` before any
recompute or simulation step; the script has an explicit `FATAL`/return-1
path if any ticker lacks a classification (mirrors the assertion pattern
from the prior session's `run_db_corpus_baseline.py`).

**Gate 5 — null counts after recompute:**

| Field | Before | After |
|---|---|---|
| `trajectory` | 3 | 31 |
| `finalConfidence` | 0 | 0 |

`tier` was not tracked as a null-count field in this script (tier is
supplied per-call from the live `tier_for_ticker` function, not read as a
nullable DB column, so "null tier" isn't a meaningful state here — every
event gets a tier assignment by construction). `finalConfidence` stayed at
zero nulls both before and after — `compute_final_confidence` apparently
always returns a value once `final_action` and `per_call_rec` are known,
regardless of trajectory availability.

## Step 5 — not run

**Explicitly skipped, per Step 4.3's stop condition.** No v1/v2/v3
simulation, no SPY/QQQ/TMFC/equal-weight comparison. The script
(`run_clean_window_baseline.py`) has this logic implemented and gated behind
the disagreement check — it prints the `STOP` message and returns before
reaching the simulation block. It has not been exercised past that point;
treat the simulation code in it as unverified.

## Assessment: is the harness sound enough to build the cadence sweep on?

**No, not on this evidence, and not for the reason the design session
expected.** The harness mechanics themselves (loader, cutoff filters, event
counts, universe/type-classification wiring) all check out cleanly — Gates
1, 2, and 4 passed exactly as specified, with no ambiguity. But the one gate
that was supposed to *prove the trend layer matters* failed, and the most
likely explanation is a flaw in how this test itself was constructed (window
truncation cutting off pre-window trend history), not a flaw in the trend
layer or the corpus. That means:

- The infrastructure (DB loading, cutoff filters, universe wiring, type
  classification) is solid and reusable.
- The specific claim this run was supposed to establish — "the recomputed
  trend layer does something material on this corpus" — is **neither
  confirmed nor refuted**. It's confounded by test construction.
- Re-running the recompute with full pre-window ticker history available
  (only *reporting* on the `[start, C]` slice) is the obvious next check,
  and it's cheap (no DB writes, no LLM calls) — but that's a re-run of this
  same gate with a fix, which the instructions for this prompt didn't
  authorize me to do unilaterally once the gate failed as specified.

## What was deliberately not done

- Step 5's full v1/v2/v3 + benchmark simulation — blocked by Step 4.3.
- No fix attempted for the history-truncation confound identified above,
  despite having a strong hypothesis — "do not start guessing" instruction
  taken literally; flagged instead.
- No spec amended, no §12 items resolved, no configuration selected.
- `price_cache.json` / `fundamentals_cache.json` untouched.
- `sync_trend_to_db.py` not run.
- No prose fallback built for `type_classification`.

## Repo state left behind

Branch `sweep/db-corpus-baseline` (uncommitted):
- `analysis/simulator/data.py` — now has both `analysis_created_before` and
  `analysis_created_after` on `load_call_events()`.
- `analysis/run_db_corpus_baseline.py` — from the prior session, unchanged.
- `analysis/run_clean_window_baseline.py` — new, this session's gate/harness
  script. Simulation code inside it is untested past the Gate 3 stop point.

`dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 run_clean_window_baseline.py

# Reproduce the boundary-scan (Step 1) independently:
DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-)
psql "$DATABASE_URL" -c "
SELECT t.\"callDate\"::date, tk.symbol,
  bool_or(a.\"createdAt\" >= '2026-05-02 12:33:23-04'
          AND a.\"createdAt\" < '2026-06-27 16:26:16-04') as has_v6
FROM \"Transcript\" t
JOIN \"Ticker\" tk ON tk.id = t.\"tickerId\"
LEFT JOIN \"Analysis\" a ON a.\"transcriptId\" = t.id
WHERE tk.symbol IN ('AAPL','AMD','AVGO','GOOGL','MSFT','NVDA','ORCL','TSLA',
                     'AMPX','ENVX','EOSE','FSLR','QS','RUN','SPWR','TTD')
GROUP BY t.\"callDate\", tk.symbol
ORDER BY t.\"callDate\";
"
```
