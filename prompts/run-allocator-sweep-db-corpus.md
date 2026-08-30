# Allocator operating model sweep — against the Postgres corpus (task #77)

Supersedes `prompts/regen-v6-eval-cache-and-run-sweep.md`. The eval cache cannot
be regenerated — `claude-sonnet-4-20250514` is retired from the API. Recon
(`wrap-ups/recon-analysis-table-v6-corpus-out.md`) established that the
Postgres `Analysis` table covers the corpus, so **the sweep runs off the DB and
costs $0 in API spend. Make no LLM evaluation calls.**

Write findings to `./wrap-ups/run-allocator-sweep-db-corpus-out.md`.

Measurement task. Do not change `server/routes/moves.js`. Do not build the new
production allocator. Do not amend any spec.

## Read first, do not re-derive

1. **`docs/architecture/ALLOCATOR_OPERATING_MODEL.md`** — the spec this measures.
   §10 "Data source" records the corpus decision and its caveats; §9 the
   invariants; §11 two defects that stay in for the baseline; §12 open items you
   must NOT resolve.
2. `wrap-ups/recon-analysis-table-v6-corpus-out.md` — accepted, do not redo.
   Note one correction the design session made to it: the missing
   `---STRUCTURED---` blocks are **not** a blocker (see Step 0e).
3. `docs/architecture/BACKTEST_SIMULATOR.md`, `PORTFOLIO_ANALYST_SPEC.md`,
   `CLAUDE.md`, `DESIGN_PRINCIPLES.md` (§5 stale on Type B cap; the spec wins).

**Settled, do not reopen:** universe composition, cap values, barbell
target→ceiling, the veto model, cash-deployment scope, and the decision to use
the DB corpus. Disagree in the wrap-up if you must; do not act on it.

---

## Step 0a — verify the backup actually restores

`~/investment-agent-backups/analysis_corpus_20260830.sql` exists but has never
been restored. Everything downstream mutates the DB (Step 0b), so prove the
backup is real **first**, on a throwaway local database:

```zsh
createdb analysis_corpus_test
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_schema_20260830.sql
psql analysis_corpus_test < ~/investment-agent-backups/analysis_corpus_20260830.sql
psql analysis_corpus_test -c 'SELECT count(*) FROM "Analysis";'   # expect 805
```

If it does not restore cleanly, **stop and report.** Take a fresh dump and do
not proceed to any write.

## Step 0b — backfill the trend-layer nulls (DB write — read this carefully)

Pre-cutoff rows have nulls: 97 `tier`, 161 `trajectory`, 97 `finalAction`,
97 `finalConfidence`. `sync_trend_to_db.py` recomputes these from
`trend_analyst.py` — deterministic Python, no LLM calls.

**Before running it**, read both files and confirm in the wrap-up:

- whether it **only fills nulls** or **recomputes and overwrites every row**
- whether it has a `--dry-run` or equivalent
- whether it would touch post-cutoff rows (it must not — scope it to the
  corpus tickers and the pre-cutoff window if it can be scoped)

If it overwrites existing non-null values, **stop and report before running.**
Recomputing a field that already holds the validated value is how a baseline
quietly stops reproducing. Step 0a's backup is the only undo.

## Step 0c — classification drift check

`Ticker.type` (live, RADAR-editable) and `analysis/data/type_classifications.json`
(frozen 2026-05-23) are synced one-way, JSON → DB, and nothing checks agreement.

```sql
-- report every disagreement
SELECT symbol, type, "capPercent", "typeReviewedAt", "activeDriverCount",
       "tierOverride", "tierMechanical", "tierReviewedAt"
FROM "Ticker" ORDER BY symbol;
```

Diff against the JSON for all 32 corpus tickers. Report disagreements with
`typeReviewedAt`. **Do not reconcile them.** The baseline runs on the frozen
JSON; a later cell prices the drift.

Report as well how `tier_for_ticker` gets its values in the runners — there is no
`tier_classifications.json` in the repo, and tier drives the 15% vs 35% cap.

## Step 0d — add the `createdAt` cutoff filter

`load_call_events()` selects `MAX(a."createdAt")` per transcript. Recon found no
transcript straddles the cutoff today, so this changes nothing now — it is a
guard against a future re-score silently swapping a v10 row into the corpus.

Add `AND a."createdAt" < %s` to both SQL blocks (`data.py:157-176` and
`:194-210`), defaulted to `2026-06-27 16:26:16-04`, overridable. Assert the
event count is unchanged with and without it.

## Step 0e — do NOT "fix" the missing structured blocks

The recon flagged that 0 of 770 pre-cutoff rows contain `---STRUCTURED---`, so
`_extract_type_classification()` returns `None` for all of them, and proposed
recovering Type A/B by regexing `## POSITION TYPE` from the prose.

**Do not do this.** That is the validated configuration, not a defect:

- `simulator.py:129` — *"prefer the curated ticker-level classification (from
  `type_for_ticker`) over the per-event classification (which is usually None
  since the v6 prompt doesn't output it explicitly)."*
- Both reference runners pass `type_for_ticker=type_fn`
  (`run_expanded_test.py:237,248,260`; `run_top20_2021_test.py:259`).
- `PORTFOLIO_ANALYST_SPEC.md:104` — the per-call fallback *"should not be used
  for live decisions because the per-call classification noise produces inflated
  drawdowns (60.9% vs 37.1%)."*
- The 2026-05-17 changelog: the Phase D lift came from *"enforcement of
  consistent ticker-level classification, not introduction of A/B."*

A prose fallback would put every run on precedence rank 2 and **undo the 17%
lift**. Instead, **assert** that `type_for_ticker` is passed on every run and
fail loudly if it is not.

## Step 0f — pin the reference universe

Determine which universe and window produce the `$287k` full-window v3 figure —
`run_expanded_test.py`, `run_top20_2021_test.py`, the `PORTFOLIO_ANALYST_SPEC.md`
changelog. Report the exact universe, window, and invocation.

---

## Step 1 — reproduce the baseline

`allocator_v3`, unmodified, per-call cadence, alphabetical ordering, all-cash
start, DB-loaded events, frozen JSON classifications, on the Step 0f universe.
Must reproduce the known figure. **If it does not, stop and report the
discrepancy** — every downstream number is relative to this.

If it reproduces only approximately, say by how much and do not proceed until
the gap is explained. A near-miss on the baseline is a finding, not a rounding
error.

## Step 2 — instrument, without changing behavior

Diagnostics only: aggregate speculative share of portfolio over time; average
cash % and days in cash; sessions where cash bound; contested rank decisions;
per-ticker mean staleness.

## Step 3 — parameterize the harness

Per §2–§5 of the spec. Add as parameters: `K` (session interval, `call_date <=
session_date`, trades at that day's close), `phase`, `scope`
(`new_calls_only` | `cash_deployment` | `full_resizing`),
`session_change_limit`, `veto` (`none` | capitulation with `p`),
`tie_break_seed`, `cash_ceiling`, `spec_ceiling` (last two default off).

Existing behavior must be exactly recoverable and asserted against Step 1.

### Unit tests required for the new paths

The baseline check validates only the **default** path. Session batching,
capitulation, and phase offsets have no reference number — if subtly wrong,
every cell is quietly wrong. Both known defects in this codebase (§11) are
state-mutation-order bugs and session batching is the same shape. Test:

- a call landing exactly on a session boundary is **included** (`<=`)
- a call one day after a boundary lands in the **next** session
- a session with zero calls still marks to market and deploys free cash under
  `cash_deployment`
- a pet position declines **both** Trim and Exit
- capitulation fires at −30% from trailing peak **position value**, not price
- capitulation is a **full exit**
- phase offset shifts the grid without dropping or duplicating any event
- under `cash_deployment`, a name whose call did not arrive this session is
  still eligible for cash if its latest verdict qualifies
- `type_for_ticker` is asserted present; a run without it fails

## Step 4 — run the grid

Axes and values: §10. Order:

1. **Cadence** — `K` × `phase`, scope `cash_deployment`, no veto, no limits.
2. **Scope** — three values at the best `K` and at `K=90`.
3. **Session change limit** — at the best `K`.
4. **Veto** — capitulation p = 10/20/30, at the best `K` **and** `K=90`.
5. **Ordering variants** — reverse-alphabetical and seeded-random, best region
   only, to price the alphabetical bias.
6. **Ceilings** — cash and speculative, information only.
7. **Classification drift cell** — rerun the baseline settings using current
   `Ticker.type` instead of the frozen JSON, to price Step 0c's drift.
8. **Bug-fixed cell** — §11's two defects fixed, baseline settings.

## Step 5 — report

**Scope boundary.** Your job ends at reporting.

- **Do not select a winning configuration.** Present the surface; do not crown a
  cell. If you find yourself building a case for why one unusually good result
  should be believed, that is the signal to distrust it and say so.
- **Do not amend any spec**, including `ALLOCATOR_OPERATING_MODEL.md` and
  `PROMOTION_GATE.md`.
- **Do not resolve the §12 open items.** Report what the numbers say and stop.
- **Report shape and magnitude, flatly.** "Return declines monotonically from $X
  at K=7 to $Y at K=90, crossing SPY between K=30 and K=60" is the deliverable.
  "K=30 is the recommended cadence" is not.
- If a result **contradicts the spec**, say so plainly and prominently.

Favor complete tables over prose. Include the exact invocation for every run.

Order: Step 0 results (backup restore, backfill scope, classification drift,
cutoff filter, universe pinned) → baseline reproduction expected vs actual →
the cadence surface, phase-averaged with across-phase spread, and whether it is
smooth or jagged → benchmark crossings → seasonal variant vs uniform `K` with
session counts → scope comparison (§3 predicts full-re-sizing degrades sharply
at small `K`; confirm or refute) → veto results → ordering variants →
ceilings by sub-period with 2022 separate → classification drift cell →
bug-fixed cell → unit test results → anything contradicting the spec.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- **No LLM evaluation calls. No API spend.**
- Only one class of DB write is authorized: Step 0b's trend backfill, after
  Step 0a passes and after you have reported what it touches.
- Work on a scratch branch. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Analyst/allocator firewall holds: the allocator never receives transcripts.
- Do not write new handoff docs. This prompt in, one wrap-up out.
- Selection is on robustness across start dates and phases, never peak return.
