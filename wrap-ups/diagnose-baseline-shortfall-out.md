# Diagnose the baseline shortfall — wrap-up

**Status: STOPPED at Step 1's gate. ALL16 v6-window coverage is 71.2%, well
below the ~90% threshold.** Per the prompt's own instruction, this is a stop
condition — Steps 2–4 (two-sided cutoff filter, in-memory trend-layer
recompute, the 2×2 grid) were **not implemented and not run**. No code
changed, no DB writes, no LLM calls, $0 spend. Still on
`sweep/db-corpus-baseline`, nothing committed.

---

## Step 1 — v6-window coverage (the gate)

Window: `createdAt >= '2026-05-02 12:33:23-04' AND createdAt < '2026-06-27 16:26:16-04'`.

### 1. Row counts

```sql
SELECT
  count(*) FILTER (WHERE "createdAt" < '2026-05-02 12:33:23-04') AS before_v6,
  count(*) FILTER (WHERE "createdAt" >= '2026-05-02 12:33:23-04'
                      AND "createdAt" < '2026-06-27 16:26:16-04') AS in_v6_window,
  count(*) FILTER (WHERE "createdAt" >= '2026-06-27 16:26:16-04') AS after_v6
FROM "Analysis";
```

```
 before_v6 | in_v6_window | after_v6
-----------+--------------+----------
       194 |          576 |       35
```

`before_v6` (194) matches the earlier recon's April histogram bucket exactly
— consistent, as expected, since v6 went live 2026-05-02.

### 2. Manifest-wide (659 distinct corpus transcripts) coverage

**560 of 659 manifest pairs have ≥1 Analysis row inside the v6 window.
99 do not.**

### 3. ALL16 per-ticker coverage

| Ticker | Total transcripts | v6-window rows | Coverage |
|---|---|---|---|
| AAPL | 22 | 15 | 68% |
| AMD | 20 | 15 | 75% |
| AVGO | 20 | 14 | 70% |
| GOOGL | 21 | 15 | 71% |
| MSFT | 23 | 23 | **100%** |
| NVDA | 23 | 18 | 78% |
| ORCL | 23 | 17 | 74% |
| TSLA | 21 | 14 | 67% |
| AMPX | 13 | 8 | 62% |
| ENVX | 19 | 12 | 63% |
| EOSE | 20 | 14 | 70% |
| FSLR | 20 | 15 | 75% |
| QS | 20 | 14 | 70% |
| RUN | 20 | 14 | 70% |
| SPWR | 7 | 1 | **14%** |
| TTD | 20 | 13 | 65% |
| **ALL16 total** | **312** | **222** | **71.2%** |

**Gate: FAIL.** 71.2% is well under the ~90% threshold, and no ticker except
MSFT clears 90% on its own. SPWR is the extreme outlier at 14% (its
transcripts are concentrated in periods this DB corpus barely covers inside
the v6 window). This is not a marginal miss — a two-sided window drops
nearly 3 in 10 of ALL16's transcripts.

### 4. Transcripts with their only analysis before 2026-05-02 (dropped by a two-sided window)

**97 transcripts**, all 16 ALL16 tickers represented plus ENPH (not in
ALL16, listed for completeness since it shares history with the universe
discussion elsewhere in the specs):

```
AAPL (7): 2024-08-01, 2024-10-31, 2025-01-30, 2025-05-01, 2025-07-31, 2025-10-30, 2026-01-29
AMD (5): 2024-10-29, 2025-02-04, 2025-05-06, 2025-08-05, 2025-11-04
AMPX (5): 2024-08-08, 2024-11-07, 2025-05-08, 2025-08-07, 2025-11-06
AVGO (6): 2024-12-12, 2025-03-06, 2025-06-05, 2025-09-04, 2025-12-11, 2026-03-04
ENPH (9): 2022-04-26, 2022-07-26, 2022-10-25, 2023-02-07, 2023-04-25, 2023-07-27, 2023-10-26, 2024-02-06, 2024-04-23
ENVX (7): 2024-07-31, 2024-10-29, 2025-02-19, 2025-04-30, 2025-07-31, 2025-11-05, 2026-02-25
EOSE (6): 2024-11-06, 2025-03-05, 2025-05-06, 2025-07-31, 2025-11-06, 2026-02-26
FSLR (5): 2025-02-25, 2025-04-29, 2025-07-31, 2025-10-30, 2026-02-24
GOOGL (6): 2024-10-29, 2025-02-04, 2025-04-24, 2025-07-23, 2025-10-29, 2026-02-04
NVDA (3): 2024-11-20, 2025-02-26, 2025-05-28
ORCL (6): 2024-12-09, 2025-03-10, 2025-06-10, 2025-09-09, 2025-12-10, 2026-03-10
QS (6): 2024-10-23, 2025-02-12, 2025-04-23, 2025-07-23, 2025-10-22, 2026-02-11
RUN (6): 2024-11-07, 2025-02-27, 2025-05-07, 2025-08-06, 2025-11-06, 2026-02-26
SPWR (6): 2024-08-14, 2024-11-13, 2025-01-15, 2025-04-30, 2025-10-21, 2026-01-20
TSLA (7): 2024-07-23, 2024-10-23, 2025-01-29, 2025-04-22, 2025-07-23, 2025-10-22, 2026-01-28
TTD (7): 2024-08-08, 2024-11-07, 2025-02-12, 2025-05-08, 2025-08-07, 2025-11-06, 2026-02-25
```

These are a mix of pre-v6-era rows (2024) and, notably, calls dated well
into 2025–2026 whose *only* Analysis row still predates 2026-05-02 — i.e.
these transcripts were evaluated once, early, and never re-scored, so they
carry a pre-v6 verdict regardless of how recent the call itself is. That
distinction matters: this isn't just "old calls have old evals," it's "some
calls were never touched again after an early, non-v6 evaluation."

Of the 99 manifest pairs lacking a v6-window row, **97 fit this
only-before-2026-05-02 pattern; the remaining 2** (`NVDA 2020-05-21`,
`NVDA 2020-08-19`) have **no Analysis row of any kind** — the same two gaps
already known from the prior recon, unrelated to windowing.

### 5. Day-level histogram, 2026-05-01 → 2026-05-05

```sql
SELECT to_char("createdAt", 'YYYY-MM-DD HH24') AS hour, count(*)
FROM "Analysis"
WHERE "createdAt" >= '2026-05-01' AND "createdAt" < '2026-05-06'
GROUP BY 1 ORDER BY 1;
```

```
     hour      | count
---------------+-------
 2026-05-02 15 |    10
 2026-05-02 16 |     2
 2026-05-02 17 |     2
 2026-05-02 18 |    33
 2026-05-02 19 |    31
 2026-05-02 21 |    32
 2026-05-02 22 |    21
 2026-05-03 22 |     6
 2026-05-03 23 |    72
 2026-05-04 00 |    14
 2026-05-04 02 |     9
```

Nothing on 2026-05-01. The burst starts 2026-05-02 and continues into
2026-05-03/04 — consistent with a batch re-evaluation run kicked off around
the v6 commit rather than a clean instantaneous cutover. **Caveat on hour
values:** `to_char` on this `timestamp without time zone` column reflects
whatever the connecting session's timezone setting renders it as, not
necessarily `America/New_York`; I did not verify the session timezone
matches the `-04` offset used in the cutoff literals elsewhere in this
report. The day-level pattern (nothing before 05-02, a multi-hour burst
starting 05-02) is unambiguous regardless of hour-label precision; treat the
specific hour labels above as approximate.

## Gate verdict

**ALL16 coverage inside the v6 window is 71.2%, not ~90%+. Per instruction,
stopping here rather than proceeding to Steps 2–4.**

This is a coverage problem, not a code problem — no filter change or
trend-layer recompute fixes a transcript that was simply never re-evaluated
after 2026-05-02. The 97-transcript list above is exactly the set a
two-sided window would silently drop, and it's concentrated in recent
2025–2026 calls (i.e., the freshest, most decision-relevant part of the
corpus) — MSFT is the only ticker fully covered; SPWR is nearly the opposite
case at 14%.

## What was deliberately not done

- **Step 2** (two-sided cutoff parameter in `data.py`) — not added.
  `analysis/simulator/data.py` is unchanged from the prior session's state
  (still carries only the one-sided `analysis_created_before` guard from
  `run-allocator-sweep-db-corpus.md`'s Step 0d).
- **Step 3** (in-memory trend-layer recompute) — not implemented.
- **Step 4** (the 2×2 grid) — not run. Cell A (both filters off) would just
  reproduce the already-known $110,069 figure; cells B–D were never reached.
- **Step 5** (ENPH file-cache vs DB-row cross-check) — not reached; the
  prompt scoped it to "only if D still misses the reference," and D was
  never computed.
- No DB writes, no cache refreshes (`price_cache.json` /
  `fundamentals_cache.json` untouched, per standing rule), no LLM calls.

## What's needed from the design session

The three options the prompt named at the top (narrower universe, narrower
window, or abandon the DB-corpus approach) are now grounded in numbers
rather than a guess:

- **Narrower universe:** dropping SPWR (14% coverage) would help ALL16's
  average, but AAPL/AVGO/GOOGL/TSLA are all also sub-75% — this isn't a
  one-ticker problem.
- **Narrower window:** the 97-transcript list (Step 1.4) shows the gap isn't
  concentrated at one edge of the window; it's spread across 2024 through
  early 2026, so narrowing the window's *end* wouldn't recover much, and
  narrowing the *start* earlier than 2026-05-02 reopens exactly the pre-v6
  contamination this diagnosis exists to close.
- **Abandon the DB-corpus approach:** given 71.2% coverage even before
  attempting a fix, and that the one attempted fix (the one-sided cutoff)
  already turned out to be the wrong shape of guard rather than a complete
  answer, this is a live option, not a fallback.

None of these were decided here, per scope.

## Follow-up / verification commands

```zsh
DATABASE_URL=$(grep '^DATABASE_URL' .env | cut -d '=' -f2-)

# Reproduce the gate numbers:
psql "$DATABASE_URL" -c "
SELECT
  count(*) FILTER (WHERE \"createdAt\" < '2026-05-02 12:33:23-04') AS before_v6,
  count(*) FILTER (WHERE \"createdAt\" >= '2026-05-02 12:33:23-04'
                      AND \"createdAt\" < '2026-06-27 16:26:16-04') AS in_v6_window,
  count(*) FILTER (WHERE \"createdAt\" >= '2026-06-27 16:26:16-04') AS after_v6
FROM \"Analysis\";
"

# Per-transcript v6-window coverage (used to build the ALL16 table above):
psql "$DATABASE_URL" -t -A -F'|' -c "
SELECT tk.symbol, t.\"callDate\"::date,
  bool_or(a.\"createdAt\" >= '2026-05-02 12:33:23-04'
          AND a.\"createdAt\" < '2026-06-27 16:26:16-04') as has_v6_row,
  min(a.\"createdAt\") as earliest_analysis
FROM \"Transcript\" t
JOIN \"Ticker\" tk ON tk.id = t.\"tickerId\"
LEFT JOIN \"Analysis\" a ON a.\"transcriptId\" = t.id
GROUP BY tk.symbol, t.\"callDate\";
"
```
