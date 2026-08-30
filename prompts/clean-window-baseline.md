# Establish a clean-window baseline (task #77, Option A)

`wrap-ups/diagnose-baseline-shortfall-out.md` closed the question: the DB
corpus is only 71.2% v6-covered on ALL16, and the gap is **time-correlated** —
everything from roughly mid-2024 onward carries a pre-v6 evaluation, everything
earlier carries v6. Since this project measures the cost of acting on stale
information, a corpus whose analyst quality is a step function in call date
would confound the exact variable under study.

**Exact reproduction of $287k is not achievable** — the file cache was never
committed, no backup exists, and `claude-sonnet-4-20250514` is retired. That is
settled; do not attempt it and do not treat any number here as a failure to hit
it.

**This run's purpose is different: prove the harness works end-to-end on a
corpus we trust.** The v6-covered slice is contiguous and internally
consistent. If the sweep's machinery is sound, it will show here.

**Read-only against the DB. No LLM calls. No API spend. No DB writes. Do not
refresh `price_cache.json` or `fundamentals_cache.json`** — they are frozen at
2026-05-11, which is what makes tier reproducible; the 111-day staleness warning
is expected.

Continue on `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/clean-window-baseline-out.md`.

---

## Step 1 — compute the clean-window boundary empirically

Do not hardcode a date. For the ALL16 universe — `AAPL AMD AVGO GOOGL MSFT
NVDA ORCL TSLA AMPX ENVX EOSE FSLR QS RUN SPWR TTD` — find the **latest
`callDate` C such that every ALL16 transcript with `callDate <= C` has at least
one Analysis row inside the v6 window**
(`createdAt >= '2026-05-02 12:33:23-04' AND < '2026-06-27 16:26:16-04'`).

Report C, the resulting per-ticker transcript counts, and confirm coverage
inside `[start, C]` is **100%, not 99%**. A single hole reintroduces the
contamination this run exists to avoid.

If C lands before 2023, **stop and report** — a window that short won't support
a cadence sweep and the design session needs to know before you build anything.

## Step 2 — two-sided cutoff in the loader

Add `analysis_created_after` to `data.py::load_call_events()`, defaulted to
`'2026-05-02 12:33:23-04'`, alongside the existing `analysis_created_before`.
Both feed the shared `where_clauses` list; both overridable with `None`.

## Step 3 — recompute the trend layer fresh, in memory

The DB's stored `finalAction` / `trajectory` / `finalConfidence` were written
incrementally over months under varying inputs. Prior evidence that they are
effectively inert: `final_action` 233/46/43 vs raw `per_call_rec` 234/50/38 —
only ~4 of 322 events differed.

After `load_call_events()` returns, **discard the stored trend fields and
recompute** using `compute_trend_verdict` / `apply_matrix` /
`compute_final_confidence`, exactly as `data_from_cache.py::attach_trend_verdicts()`
does — same ordering, same per-ticker history construction, same
`tier_for_ticker` snapshot.

**In memory only. Nothing written back to Postgres.** Flag-controlled so it can
be toggled.

## Step 4 — verification gates, before any simulation

Report each; any failure stops the run.

1. **Coverage is 100%** inside `[start, C]` for all 16 tickers.
2. **No dropped events** — event count matches the transcript count for the
   window exactly.
3. **The trend layer is now doing something.** Compare recomputed `final_action`
   against raw `per_call_rec` and report the disagreement rate. It should be
   materially above the ~1% seen with stored fields; `trend_layer_v1_result`
   measured 44%→54% on 41 calls, so a low-single-digit rate means the recompute
   didn't take. **If disagreement is still under ~5%, stop and report** rather
   than running the simulation.
4. **`type_for_ticker` resolves for all 16 tickers** from the frozen JSON, and
   the run aborts if it is not passed.
5. Null counts for `tier` / `trajectory` / `finalConfidence` after the recompute
   — these should now be filled in memory.

## Step 5 — the substitute correctness gate

We cannot gate on $287k. Use a relative gate instead, which is stronger than a
single dollar figure anyway.

Run **v1, v2, and v3 allocators** over the identical clean window, same
universe, same capital ($100,000, 50/50 taxable/tax-advantaged), alongside
**SPY, QQQ, TMFC, and equal-weight-of-universe** buy-and-hold on the same dates.

Report final value and max drawdown for all seven.

**What we're checking:** the allocator versions should order the way the
changelog says they do — v3's tier-aware caps, profit-take, and no-average-down
were each introduced to fix a diagnosed failure, so v3 ≥ v2 ≥ v1 on this window
is the expected shape. **If the ordering inverts, the harness or the corpus is
wrong and nothing downstream is trustworthy** — report it plainly and stop.

This is a directional check, not a threshold. v3 beating or losing to SPY on a
2.5-year window is information, not a pass/fail — say which and move on.

## Step 6 — report

Scope boundary: report, do not decide. Do not select a configuration, do not
amend specs, do not resolve §12 open items, do not proceed to the cadence sweep.

Lead with:

> **Clean window: [start] → [C]. N transcripts, 100% v6 coverage. v1/v2/v3 =
> $X / $Y / $Z. Ordering holds / does not hold.**

Then the Step 4 gates, the Step 5 table, and — flagged plainly — anything that
looks wrong even if it passed a gate. Include the exact invocation for every run.

State explicitly whether, in your assessment, **the harness is sound enough to
build the cadence sweep on**. That is the one question this run exists to
answer.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, no DB writes, no cache refreshes.
- Do not run `sync_trend_to_db.py`.
- Do not build a prose fallback for `type_classification`.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
