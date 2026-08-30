# Allocator operating model sweep — against the Postgres corpus — wrap-up

**Status: STOPPED at Step 1. Baseline does not reproduce.** $110k vs. the
$287k reference on the exact universe/window/allocator the reference used —
a 62% shortfall, not a rounding error. Per this prompt's own instruction
("if it does not [reproduce], stop and report the discrepancy — every
downstream number is relative to this"), Steps 2–4 (harness parameterization,
unit tests, the grid) were **not started**. $0 API spend throughout, as
required.

All work on branch `sweep/db-corpus-baseline` (off `dev`, not committed to
either `dev` or `main`).

---

## Step 0a — backup restore: verified

No local Postgres server existed on this machine (only `libpq` client tools
were present — `createdb` failed with "connection... failed: No such file or
directory"). Installed `postgresql@18` via Homebrew (matches the server's
`18.6`) to get a throwaway local instance — flagging this as a deviation: the
prompt assumed a working local Postgres; there wasn't one, so I added one
rather than stopping, since it's local, easily removed, and blocks nothing
downstream.

```zsh
brew install postgresql@18
brew services start postgresql@18
createdb analysis_corpus_test
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_schema_20260830.sql
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_20260830.sql
psql analysis_corpus_test -c 'SELECT count(*) FROM "Analysis";'
```

Result: **805** — exact match. `Transcript` = 708, `Ticker` = 45, also exact
matches. The only errors during restore were `ERROR: role "postgres" does not
exist` on four `ALTER ... OWNER TO postgres` statements — harmless; ownership
defaulted to the connecting role and every `CREATE TABLE` / `INSERT` line
succeeded. **Backup is confirmed restorable.**

Cleaned up afterward: `dropdb analysis_corpus_test`, `brew services stop
postgresql@18`. Homebrew's `postgresql@18` formula remains installed on this
machine (uninstalling it wasn't asked for and removing dev tooling
unilaterally seemed like the wrong default); say if you want it removed.

## Step 0b — trend-layer backfill: NOT RUN — stop, per the prompt's own gate

Read `sync_trend_to_db.py` in full before touching anything, per instruction.
Findings:

- **It does not "only fill nulls." It recomputes and overwrites every
  latest-per-transcript row's `tier`, `trajectory`, `suggestedOverride`,
  `finalAction`, `finalConfidence`, `trendRationale` unconditionally**
  (`sync_trend_to_db.py:264-276`, an `UPDATE ... WHERE id = %s` executed for
  every row in `updates`, built from *all* rows in `fetch_all_analyses()`,
  not just the null ones). The module docstring even calls this "idempotent
  — rerunning just overwrites the same fields with the same values," which
  is a *claim*, not something the code enforces.
- **That claim doesn't actually hold in practice.** `tier` comes from
  `build_tier_function()`, which reads `analysis/data/price_cache.json` and
  `analysis/data/fundamentals_cache.json` — **live, mutable snapshot files**,
  not something frozen to when the $287k reference or the original
  pre-cutoff rows were computed. Both files are stale right now (last
  modified 2026-05-10; `fundamentals_cache.json` triggers the script's own
  111-day-old staleness warning at a 30-day threshold). Rerunning today would
  compute tier from whatever those files hold *today*, not from whatever
  they held when the 673 already-non-null `tier` values were written. If a
  ticker's volatility/market-cap/P.E. axes have moved since, tier could flip
  (speculative ↔ established), silently changing the 15/35/50% cap applied
  to already-good historical rows — precisely the "baseline quietly stops
  reproducing" failure mode the prompt warned about.
- **Has `--dry-run`:** yes, confirmed (`sync_trend_to_db.py:180-195`) — prints
  a per-ticker verdict summary, no writes.
- **Scoping:** `--ticker` (repeatable) restricts by symbol, but **there is no
  date/cutoff scoping at all** — it operates on "latest Analysis per
  transcript" for whichever tickers are selected, irrespective of
  `createdAt`. It cannot be scoped to "the pre-cutoff window" as asked; only
  to a ticker list. Since no transcript straddles the cutoff (recon,
  confirmed again in Step 0d below), scoping to the 32 corpus tickers would
  in practice only touch pre-cutoff rows for those tickers — but that's a
  property of today's data, not something the script enforces or the prompt
  could have verified would still be true when someone reruns this later.

**This trips the prompt's explicit gate** — *"If it overwrites existing
non-null values, stop and report before running."* It does. **Not run.** The
Step 0a backup stands as the undo path if this is run later; it is not
needed here since nothing was written.

**Consequence carried forward:** the 97/161/97/97 nulls
(`tier`/`trajectory`/`finalAction`/`finalConfidence`) on pre-cutoff rows
remain unfilled. `data.py::load_call_events()` already has a fallback for
one of them — `final_action = r["final_action"] or r["per_call_rec"]`
(`data.py:216`, unchanged) — so a null `finalAction` degrades to "use the raw
per-call recommendation, no trend-layer override," not a crash or a dropped
event. The other three nulls (tier, trajectory, finalConfidence) have no such
fallback in the loader and are consumed as `None` downstream.

## Step 0c — classification drift check

```sql
SELECT symbol, type, "capPercent", "typeReviewedAt", "activeDriverCount",
       "tierOverride", "tierMechanical", "tierReviewedAt"
FROM "Ticker" ORDER BY symbol;
```

Diffed live `Ticker.type` against the frozen
`analysis/data/type_classifications.json` (32 corpus tickers, all present in
both):

**One disagreement: `V` (Visa) — frozen JSON says Type A, live `Ticker.type`
says Type B.** `typeReviewedAt` is `NULL` on every one of the 45 `Ticker`
rows (not just V's), so there is no timestamp to report for when or why this
drifted — the column exists but has never been populated. Not reconciled,
per instruction; the baseline (Step 1, below) used the frozen JSON, so this
drift did not affect the attempted reproduction.

**`tier_for_ticker` in the runners:** there is **no `tier_classifications.json`**
anywhere in the repo — confirmed by search. Every runner
(`run_expanded_test.py`, `run_v2_full_window.py`, `run_v3_established_per_year.py`,
`run_top20_2021_test.py`, `v3_quarterly_concentration.py`, and this recon's
own `run_db_corpus_baseline.py`) gets tier from
`trend_analyst.build_tier_function(price_cache_path, fundamentals_cache_path)`
— a **live 3-axis rule** (trailing annualized volatility ≥ 50%, market cap <
$50B, trailing P/E > 50 or negative/missing) evaluated fresh against
`analysis/data/price_cache.json` / `fundamentals_cache.json` every time it's
called. **Unlike Type A/B, tier is never frozen** — it is recomputed from
whatever those two snapshot files hold at run time, and those files are
currently 111+ days stale. This is a second, independent source of
non-reproducibility beyond Step 0b, and is very likely implicated in the
Step 1 failure below.

## Step 0d — `createdAt` cutoff filter: added

`analysis/simulator/data.py::load_call_events()` — added a fourth parameter,
`analysis_created_before`, defaulted to the cutoff timestamp
(`2026-06-27 16:26:16-04`), appended as `AND a."createdAt" < %s` into the
shared `where_clauses` list that both SQL blocks
(`data.py:158-176` main query, `data.py:197-211` rawOutput/type-classification
query) already interpolate via `{where_sql}` — one addition covers both, as
the prompt implied.

```python
def load_call_events(
    tickers: Optional[list[str]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    analysis_created_before: Optional[str] = "2026-06-27 16:26:16-04",
) -> list[CallEvent]:
    ...
    if analysis_created_before:
        where_clauses.append('a."createdAt" < %s')
        params.append(analysis_created_before)
```

**Assertion run, and it does NOT come back unchanged** — flagging this
explicitly since the prompt predicted it would:

```
with cutoff (default):     673 events
without cutoff (disabled): 708 events
```

This is not the re-score hazard (that's still confirmed at zero — no
transcript straddles the cutoff). It's simpler: **35 transcripts exist in
the DB with *only* post-cutoff Analysis rows** — new calls entered after the
`v10+auto1` prompt bump (Aug 2026 earnings, mostly), which were never part of
the frozen 659-transcript manifest corpus in the first place. Restricting to
`ALL16` (the actual baseline universe, see Step 0f) and the reference date
window makes this moot — none of those 35 fall inside `ALL16`'s 2022–2026-06
full-window run (confirmed: `run_db_corpus_baseline.py` loads exactly 322
events for `ALL16` with the cutoff active, and every one is a corpus
transcript). So the filter is safe and does what it's meant to; the "count
unchanged" expectation just wasn't stated precisely enough to survive the
DB's newer, out-of-corpus rows — worth having the design session note if this
gets written into a spec.

## Step 0e — did NOT touch the missing `---STRUCTURED---` blocks

Per instruction, left `_extract_type_classification()` as-is. Confirmed via
`run_db_corpus_baseline.py`'s explicit assertion
(`type_for_ticker OK for all 16 tickers`, printed before any simulation runs)
that `type_for_ticker` (the frozen-JSON `build_type_function()`) is passed
and resolves for every ticker in the universe — the run would have exited
with a `FATAL` line and return code 1 otherwise. This assertion lives in the
scratch baseline script only; **it is not yet in `simulator.py` itself**,
which is where Step 3 said it belongs as a permanent guard. Not added there —
Step 3 was not reached.

## Step 0f — reference universe pinned

**Universe: `ALL16`** — `ESTABLISHED = [AAPL, AMD, AVGO, GOOGL, MSFT, NVDA,
ORCL, TSLA]` + `SPECULATIVE = [AMPX, ENVX, EOSE, FSLR, QS, RUN, SPWR, TTD]`,
defined identically in `run_expanded_test.py`, `run_v2_full_window.py`,
`run_v3_established_per_year.py`, and `v3_quarterly_concentration.py`.

**One loose end, flagged rather than resolved:** `PORTFOLIO_ANALYST_SPEC.md`
describes the source of $287k as the *"original 17-ticker universe"*
(lines 57 and 738), but **no script in the repo defines a 17-ticker set** —
every runner uses exactly `ALL16` (16 tickers). "17-ticker" in the spec text
and `ALL16` in code very likely refer to the same universe with an
off-by-one in the prose (e.g., counting a ticker that was later dropped, or
a documentation typo) — but I did not find the discrepancy's origin and am
not asserting which is right. Used `ALL16` since it's the only universe
that actually exists in code and is what every downstream script (including
the ones that produced the $245k→$287k Phase D changelog entry) is built
around.

**Window: full window**, `start = max(earliest_event + 365 days, 2022-01-01)`,
`end = latest_event`, exactly `run_expanded_test.py`'s formula
(`_build_default_scenarios`, "Full window" row).

**Capital:** `$100,000` initial, 50/50 taxable/tax-advantaged split
(`INITIAL = 100_000` in every ALL16 runner).

**Allocator:** `decide_v3` (`analysis.simulator.allocator_v3.decide`), with
`tier_for_ticker=tier_fn` (live 3-axis rule, Step 0c), `type_for_ticker`
= frozen JSON, `driver_count_for_ticker` passed but a no-op under the flat
50% cap.

**Invocation used** (new scratch script, `analysis/run_db_corpus_baseline.py`,
committed to `sweep/db-corpus-baseline` only):

```zsh
cd analysis && python3 run_db_corpus_baseline.py
```

---

## Step 1 — baseline reproduction: FAILS by a wide margin

```
Loading events from DB (pre-cutoff only, default cutoff)...
  322 events loaded for ALL16
  Span: 2020-09-10 -> 2026-06-10
WARNING: fundamentals_cache.json is 111 days old (>30). Re-run fetch_fundamentals.py...
  type_for_ticker OK for all 16 tickers

Full window: 2022-01-01 -> 2026-06-10

Final value: $110,069
Max drawdown: 58.5%
Reference: $287k full-window v3 flat-50% Type B
```

**$110,069 actual vs. $287,000 reference — a 62% shortfall.** Drawdown is
also far worse than what's implied elsewhere in the docs for this run
(43.5%–46.1% range cited in `PORTFOLIO_ANALYST_SPEC.md` for the
classification-corrected v3 result). This is not a near-miss; it is a
different outcome. **Stopping here, per the prompt's own instruction, rather
than proceeding to Steps 2–4 on a foundation that doesn't reproduce.**

**Diagnosis attempted, not resolved — most likely cause, in order of
confidence:**

1. **`final_action`/`trajectory`/`finalConfidence` are read as already-computed
   DB columns, not recomputed in one consistent pass.** `decide_v3` consumes
   `event.final_action` directly (`allocator_v3.py:41`) — it does not
   recompute the trend layer itself. Those DB values were written
   incrementally, over months, by whatever `sync_trend_to_db.py` run was live
   at the time, each using **whatever `tier_for_ticker` result was live at
   that moment**. `run_expanded_test.py`'s file-cache path, by contrast, calls
   `attach_trend_verdicts()` **once**, fresh, over the whole corpus, with a
   **single** `tier_fn` snapshot — guaranteeing every event's trend verdict
   was computed under one consistent tier assignment. Reading the DB's
   already-baked `finalAction` values mixes verdicts computed under
   potentially different historical tier snapshots. This is a real
   structural mismatch between "read what's stored" and "recompute
   consistently," and it's exactly the risk Step 0b's gate was protecting
   against — which is part of why I didn't paper over it by running the
   backfill blind.
2. **Tier itself is unfrozen and the caches are 111 days stale (Step 0c).**
   Even a single consistent recomputation today would use different
   price/fundamentals snapshots than whatever originally produced $287k,
   which could shift several tickers between the 15% and 35% (Type A) caps.
3. Action counts look plausible on their face (233 Add / 46 Hold / 43 Trim
   out of 322, `final_action`; 234/50/38 on raw `per_call_rec` — reasonably
   close to each other, so this isn't a case of every event silently
   defaulting to Hold or being dropped). That rules out a gross data-loss
   bug and points back toward (1)/(2) — a sizing/cap discrepancy across many
   events, not a missing-data one.

**Not investigated further** — isolating exactly how much of the $177k gap
is (1) vs (2) vs something else entirely (e.g., a difference in which prior
calls the trend layer had visibility into, since the DB's per-transcript
history for `compute_trend_verdict` may differ subtly from the file-cache's)
would mean re-running `attach_trend_verdicts()` fresh over DB-sourced events
instead of trusting the stored fields — a real code change to the loading
path, which is Steps 2–3 territory, not Step 1 diagnosis. Flagging it as the
most promising next step rather than doing it here.

## What's needed before this can proceed

A decision on how the DB corpus's trend-layer fields get made trustworthy
again, since Step 0b's blind backfill is off the table and Step 1's "read
what's stored" also doesn't reproduce:

- **Option A** — recompute the trend layer fresh, once, over the entire
  DB-sourced corpus in memory (mirroring `attach_trend_verdicts()`'s
  file-cache approach) instead of trusting `Analysis.finalAction` etc. as
  stored. Never writes to the DB; only changes what the *loader* does with
  what it reads. This directly tests hypothesis (1) above without touching
  live data.
- **Option B** — refresh `price_cache.json` / `fundamentals_cache.json`
  first (there are `fetch_prices_*.py` / `fetch_fundamentals.py` scripts
  referenced in `sync_trend_to_db.py`'s docstring), then retry Step 0b's
  backfill deliberately (not blind) with the fresh, single, current
  snapshot, and re-run Step 1. This directly tests hypothesis (2) but is a
  real DB write, gated on Luis's go-ahead given the concern raised in 0b.
- Both could be tried, in that order (A first — it's read-only and cheaper to
  reason about), before touching the DB at all.

## What was deliberately not done

- Steps 2 (instrumentation), 3 (harness parameterization + unit tests), and
  4 (the grid) — all blocked on Step 1.
- No DB writes anywhere (Step 0b declined; nothing else in this prompt calls
  for one until Step 4, unreached).
- No spec amended.
- No `§12` open items resolved.
- `data.py`'s change (Step 0d) is the only code change, and it's inert by
  design given today's data (Step 3.6 of the recon: no straddling
  transcript) — a guard for the future, not a fix for anything live.

## Repo / environment state left behind

- Branch `sweep/db-corpus-baseline` (off `dev`): one modified file
  (`analysis/simulator/data.py`, the cutoff-filter addition) and one new
  scratch file (`analysis/run_db_corpus_baseline.py`). **Not committed** —
  left as working-tree changes on the scratch branch per "work on a scratch
  branch, do not commit to dev"; commit them if this thread continues, or
  discard the branch if the diagnosis above leads somewhere else first.
- `dev`/`main`: untouched.
- `postgresql@18` (Homebrew formula): installed, currently stopped
  (`brew services stop postgresql@18` was run). The `analysis_corpus_test`
  database was dropped after Step 0a's verification. No lingering local DB
  state.
- No `.env` values, secrets, or transcript text printed anywhere above.

## Follow-up / verification commands

```zsh
# Reproduce the failing baseline:
cd analysis && python3 run_db_corpus_baseline.py

# Reproduce the cutoff-filter assertion:
python3 -c "
import sys; sys.path.insert(0, '.')
from analysis.simulator.data import load_call_events
print(len(load_call_events()))                                  # 673
print(len(load_call_events(analysis_created_before=None)))      # 708
"

# Re-verify the backup restores (if postgresql@18 is reinstalled):
brew services start postgresql@18
createdb analysis_corpus_test
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_schema_20260830.sql
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_20260830.sql
psql analysis_corpus_test -c 'SELECT count(*) FROM "Analysis";'   # expect 805
dropdb analysis_corpus_test
brew services stop postgresql@18
```
