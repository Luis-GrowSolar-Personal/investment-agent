# Diagnose the baseline shortfall (task #77, blocked)

`wrap-ups/run-allocator-sweep-db-corpus-out.md` stopped correctly at Step 1:
$110,069 against a $287k reference on ALL16 full-window. The design session
found the likely cause. This prompt tests it.

**Read-only apart from one loader change. No LLM calls. No API spend. No DB
writes of any kind.** Continue on branch `sweep/db-corpus-baseline`.

Write findings to `./wrap-ups/diagnose-baseline-shortfall-out.md`.

## What the design session concluded — do not re-derive

**The cutoff filter is one-sided, and that is the prime suspect.** The prompt
that specified it (mine) gave an upper bound only. Every version transition of
`docs/EVALUATION_PROMPT.md`:

```
2026-04-04  3a658b2a  (no version header — pre-v6)
2026-04-07  75596f26  (no version header — pre-v6)
2026-05-02  22d2c712  v6          ← v6 GOES LIVE 12:33:23 -0400
2026-05-30  3d9a9d68  v6
2026-06-27  70634653  v6          ← last v6 commit (the existing cutoff)
2026-08-01  87bcfaa8  v10+auto1
```

Your own histogram showed **194 of 805 rows created in 2026-04** — before v6
existed, produced by an earlier unversioned prompt. The reference ran on a
uniformly-v6 file cache. A ~24% pre-v6 blend is entirely consistent with a 62%
shortfall.

**Two corrections to your wrap-up's proposed options:**

- **Option B is struck. Do NOT refresh `price_cache.json` /
  `fundamentals_cache.json`.** They were last written **2026-05-11**, six days
  before the 2026-05-17 reference runs. They are frozen at the reference state,
  and that staleness is the only reason tier is reproducible at all. Refreshing
  them would recompute the 3-axis classifier against August 2026 data, flip an
  unknown number of tickers between the 15% and 35% caps, and move the baseline
  further away. **Treat the 111-day staleness warning as expected. Do not
  "fix" it.**
- **Option A is confirmed and is fix #2 below.** Your action counts support it:
  `final_action` 233/46/43 vs raw `per_call_rec` 234/50/38 — only ~4 events of
  322 differ, so the trend layer is doing essentially nothing, when it was
  measured at 44%→54% on 41 calls.

**Still standing:** do not run `sync_trend_to_db.py`. Do not build a prose
fallback for `type_classification`. Do not amend any spec. Do not resolve §12
open items.

---

## Step 1 — v6-window coverage. This is the gate.

Everything else depends on whether enough of the corpus survives a two-sided
window. Report these numbers before changing any code:

Define the v6 window as
`createdAt >= '2026-05-02 12:33:23-04' AND createdAt < '2026-06-27 16:26:16-04'`.

1. Rows inside the v6 window; rows before it; rows after it.
2. Of the **659 distinct corpus transcripts** (`_manifest.json`), how many have
   **at least one** Analysis row inside the v6 window?
3. Of the **ALL16 universe** — `AAPL AMD AVGO GOOGL MSFT NVDA ORCL TSLA AMPX
   ENVX EOSE FSLR QS RUN SPWR TTD` — how many of its transcripts have a v6-window
   row? Report per-ticker: total transcripts vs v6-window-covered.
4. How many transcripts have their **only** analysis before 2026-05-02? These
   are the ones a two-sided window drops. List them by ticker.
5. Day-level histogram of `createdAt` for 2026-05-01 → 2026-05-05, to confirm
   where the v6 boundary actually falls in the data.

**Gate:** if ALL16 coverage inside the v6 window is below ~90% of its
transcripts, **stop and report.** A corpus with large holes is not a baseline,
and the design session needs to decide between a narrower universe, a narrower
window, or abandoning the DB-corpus approach.

## Step 2 — fix #1: make the cutoff two-sided

In `data.py::load_call_events()`, add `analysis_created_after`, defaulted to
`'2026-05-02 12:33:23-04'`, alongside the existing `analysis_created_before`.
Both flow into the same `where_clauses` list, so both SQL blocks pick it up.
Both must be overridable (pass `None` to disable) so the runs in Step 4 can
toggle them independently.

## Step 3 — fix #2: recompute the trend layer fresh, in memory

The DB's stored `finalAction` / `trajectory` / `finalConfidence` were written
incrementally over months under varying inputs. The file-cache path instead
calls `attach_trend_verdicts()` **once**, over each ticker's full chronological
history, with a single `tier_fn` snapshot.

Mirror that for DB-sourced events: after `load_call_events()` returns, discard
the stored trend fields and recompute them in memory using
`compute_trend_verdict` / `apply_matrix` / `compute_final_confidence` from
`trend_analyst.py`, exactly as `data_from_cache.py::attach_trend_verdicts()`
does — same ordering, same history construction, same `tier_for_ticker`.

**In memory only. Nothing is written back to Postgres.** Make it a flag on the
loading path so Step 4 can run with it on and off.

## Step 4 — attribute the gap: run the 2×2

Run all four cells, ALL16, full window, `decide_v3`, frozen-JSON
`type_for_ticker`, unchanged caches. Report final value and max drawdown for
each:

| # | v6 window | fresh trend layer | Final value | Max DD |
|---|---|---|---|---|
| A | off | off | *(should reproduce $110,069)* | 58.5% |
| B | **on** | off | | |
| C | off | **on** | | |
| D | **on** | **on** | | |

Cell A is the control — if it no longer prints $110,069, something else moved
and that is itself the finding. Cell D is the candidate baseline.

Report the event count for each cell too; a large drop in D's event count
relative to A is the coverage cost of the window, and it matters for
interpretation.

## Step 5 — only if D still misses the reference

Do not start guessing. Run this one specific cross-check instead:

`analysis/data/evals_ENPH_run1|run2|run3/` are surviving **file-cache** evals
with intact `---STRUCTURED---` blocks — produced by `eval_cache_warmer.py`
calling the API directly. The DB rows were produced by the server's
`/api/evaluate` route. **Nobody has verified those two paths produce the same
verdicts.**

For each ENPH transcript present in both, compare the file-cache eval's
structured `recommendation` / `recommendedSize` / `thesisHealth` against the
DB row's columns for the same (ticker, call_date). Report agreement rate and
every disagreement.

If they disagree materially, the DB is **not** an equivalent substitute for the
file cache regardless of prompt version, and the whole DB-corpus approach needs
rethinking. That is a design-session decision — report it, do not act on it.

## Step 6 — report

Scope boundary: report, do not decide. Do not select a configuration, do not
amend specs, do not resolve §12 items.

Lead with the Step 1 gate number, then the 2×2 table, then Step 5 if reached.
State plainly whether the shortfall is explained, partly explained, or not
explained. If cells B and C each close part of the gap and D closes most of it,
say so with the numbers. If D still misses badly, say that too — a failed
diagnosis reported clearly is more useful than a plausible story.

Include the exact invocation for every run.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, no DB writes.
- Do not refresh the price or fundamentals caches.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
