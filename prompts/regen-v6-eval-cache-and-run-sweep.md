# Regenerate the v6 eval cache, then measure the allocator operating model

Supersedes `prompts/run-allocator-operating-model-sweep.md`. That run correctly
stopped at Step 0 because the prompt named the wrong tool. This one is corrected
and **spend is authorized** (see Step 0c). Read
`wrap-ups/run-allocator-operating-model-sweep-out.md` first — its Step 0a finding
is accepted and must not be redone.

Write findings to `./wrap-ups/regen-v6-eval-cache-and-run-sweep-out.md`.

This is a **measurement** task. Do not change `server/routes/moves.js`. Do not
build the new production allocator. Do not amend any spec.

## Read first, do not re-derive

1. **`docs/architecture/ALLOCATOR_OPERATING_MODEL.md`** — the spec this measures.
   Agreed 2026-08-30; its decisions are closed. §10 is the run plan, §9 the
   contract, §11 two known defects that stay in for the baseline.
2. `docs/architecture/BACKTEST_SIMULATOR.md` — harness design, success criteria.
3. `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` — caps, 2×2 matrix, the
   2026-05-17 variable-cap retirement.
4. `CLAUDE.md`, `docs/architecture/DESIGN_PRINCIPLES.md` — standing rules.
   `DESIGN_PRINCIPLES.md` §5 is known stale on the Type B cap; the spec wins.

**Settled, do not reopen:** universe composition, cap values, the barbell
target→ceiling decision, the veto model, cash-deployment scope. If you think one
is wrong, say so in the wrap-up; do not act on it.

---

## Step 0a — already done, do not repeat

Task #75 (`splitBucketTarget` zero-cap divisor) is **fixed, not pending** —
commit `37f535a` on `dev`. The tracker is stale. Carry that forward; spend no
time on it.

## Step 0b — restore the v6 evaluation prompt

The working tree's `docs/EVALUATION_PROMPT.md` is `v10+auto1`. The validated
reference result was produced under **v6**. The sweep must run on v6 so the
analyst is held constant and the baseline is reproducible.

`eval_cache_warmer.py::load_prompt()` reads `docs/EVALUATION_PROMPT.md` and
derives the cache directory from the **first token after `# Version:`**. So the
live file's version banner literally determines where output lands.

```zsh
# find the last commit whose EVALUATION_PROMPT.md was v6
git log --all --oneline -- docs/EVALUATION_PROMPT.md
git show <commit>:docs/EVALUATION_PROMPT.md | head -5    # confirm "# Version: v6"
```

Restore it to the working tree **on a scratch branch, not on `dev`**, and
confirm before dispatching anything:

```zsh
git checkout -b sweep/v6-eval-cache
git show <commit>:docs/EVALUATION_PROMPT.md > docs/EVALUATION_PROMPT.md
head -5 docs/EVALUATION_PROMPT.md          # MUST read "# Version: v6 ..."
```

**Directory-name trap — read before running the warmer.** The warmer writes to
`data/evals/<first-token-of-version>`, i.e. **`data/evals/v6`**. But
`data_from_cache.py` prefers `data/evals/v6_sonnet-4-20250514` and only falls
back to `data/evals/v6` when the former **does not exist**:

```python
EVALS_DIR = (_DATA_DIR / "v6_sonnet-4-20250514"
             if (_DATA_DIR / "v6_sonnet-4-20250514").exists()
             else _DATA_DIR / "v6")
```

So: let the warmer write `v6`, and **do not create an empty or partial
`v6_sonnet-4-20250514` directory** — if it exists, the loader will prefer it and
silently read nothing. Either leave only `v6`, or fully populate and rename to
`v6_sonnet-4-20250514`. Not both. State in the wrap-up which you did.

The warmer hardcodes `MODEL = "claude-sonnet-4-20250514"` and `temperature=0`,
matching the reference. Do not change either.

## Step 0c — warm the cache (spend authorized)

All 32 tickers; the manifest has 662 entries covering all of them.
`--ticker` is `action="append"`, so one flag per ticker. `--budget-seconds`
defaults to 38 (built for an old 45s sandbox); raise it and loop until the
warmer prints "All cached."

```zsh
cd analysis
TICKERS=(AAPL ADBE AMD AMPX AMZN AVGO BAC DIS ENPH ENVX EOSE FSLR GOOGL HD JNJ \
         JPM MA META MSFT NFLX NVDA ORCL PG PYPL QS RUN SPWR TSLA TTD UNH V WMT)
ARGS=(); for t in $TICKERS; do ARGS+=(--ticker $t); done

# first pass: small, to validate cost and output shape before committing
python3 eval_cache_warmer.py --ticker AAPL --parallel 5 --budget-seconds 120
```

**Before the full run, report the calibration:** from that first pass, the actual
input and output token counts per call. The prior wrap-up estimated $25–35 from
**input tokens only**; `max_tokens=4096` per call means output could add
substantially. Multiply out to a real projected total for 662 calls.

- **Authorized up to $75.** If the calibrated projection exceeds that, **stop and
  report** with the number rather than proceeding.
- If under, run the full set:

```zsh
while :; do
  python3 eval_cache_warmer.py $ARGS --parallel 15 --budget-seconds 600 | tee -a /tmp/warm.log
  grep -q "All cached." /tmp/warm.log && break
done
ls data/evals/v6/*.txt | wc -l     # expect ~659-662
```

Report any transcripts that failed repeatedly. **If more than ~1% fail, stop** —
do not sweep on a partial corpus.

## Step 0d — pin the reference universe

The `$287k` full-window v3 figure is the baseline gate, but the universe behind
it is ambiguous across docs (a 17-ticker set and a "top20-2021" set are both
referenced). Determine which universe and date window produce it —
`analysis/run_expanded_test.py`, `run_top20_2021_test.py`, and the
`PORTFOLIO_ANALYST_SPEC.md` changelog are the places to look. **Report the exact
universe, window, and invocation.** Everything downstream compares against it.

---

## Step 1 — reproduce the baseline

`allocator_v3`, unmodified, per-call cadence, alphabetical ordering, all-cash
start, on the universe pinned in Step 0d. Must reproduce the known figure. If it
does not, **stop and report the discrepancy** — every downstream number is
relative to this.

Bank the number and the exact invocation.

## Step 2 — instrument, without changing behavior

Diagnostics only, added to per-run output:

- aggregate **speculative share of portfolio** over time (determines whether the
  §6 ceiling would ever bind — do not implement the ceiling)
- average cash %, days in cash
- sessions where cash was the binding constraint
- contested rank decisions (eligible demand > cash)
- per-ticker mean staleness

## Step 3 — parameterize the harness

Per `ALLOCATOR_OPERATING_MODEL.md` §2–§5. Today the simulator is hardcoded to
per-call, immediate, alphabetical. Add as parameters:

- **`K`** — session interval in days; decisions batch to session boundaries; a
  call is in scope when `call_date <= session_date`; trades at that day's close
- **`phase`** — the session grid's start offset
- **`scope`** — `new_calls_only` | `cash_deployment` | `full_resizing`
- **`session_change_limit`** — max pp of portfolio one position may move/session
- **`veto`** — `none` | capitulation model (§8), with `p`
- **`tie_break_seed`**
- **`cash_ceiling`**, **`spec_ceiling`** — both default off

Existing behavior must be exactly recoverable (per-call, `new_calls_only`, no
limits, alphabetical). Assert that against Step 1's number.

### Unit tests are required for the new paths

The baseline-reproduction check only validates the **default** path. Session
batching, capitulation, and phase offsets have **no reference number** — if they
are subtly wrong, every downstream cell is quietly wrong and nothing catches it.
This codebase's two known defects (§11) are both state-mutation-order bugs, and
session batching is the same shape. Write small, specific tests:

- a call landing exactly on a session boundary is **included** (`<=`)
- a call one day after a boundary lands in the **next** session
- a session with zero calls still marks to market and deploys free cash under
  `cash_deployment`
- a pet position declines **both** Trim and Exit
- capitulation fires at −30% from trailing peak **position value**, not price
- capitulation is a **full exit**
- phase offset shifts the grid without dropping or duplicating any event
- under `cash_deployment`, a name whose call did **not** arrive this session is
  still eligible for cash if its latest verdict qualifies

## Step 4 — run the grid

Axes and values: §10. Order:

1. **Cadence** — `K` × `phase`, scope `cash_deployment`, no veto, no limits.
2. **Scope** — three values at the best `K` and at `K=90`.
3. **Session change limit** — at the best `K`.
4. **Veto** — capitulation p = 10/20/30, at the best `K` **and** `K=90`
   (path-dependent; interacts with cadence).
5. **Ordering variants** — reverse-alphabetical and seeded-random, best region
   only, to price the alphabetical bias.
6. **Ceilings** — cash and speculative, information only.
7. **Bug-fixed cell** — §11's two defects fixed, baseline settings, to quantify
   what they were worth. Do not fix them anywhere else.

## Step 5 — report

**Scope boundary — read before writing anything.**

Your job ends at reporting.

- **Do not select a winning configuration.** Present the surface; do not crown a
  cell. If you find yourself building a case for why one unusually good result
  should be believed, that is the signal to distrust it and say so.
- **Do not amend `ALLOCATOR_OPERATING_MODEL.md`** or any other spec.
- **Do not resolve the §12 open items** (session change limit, speculative
  ceiling level, verdict grace window). Report what the numbers say and stop.
- **Report shape and magnitude, flatly.** "Return declines monotonically from $X
  at K=7 to $Y at K=90, crossing SPY between K=30 and K=60" is the deliverable.
  "K=30 is the recommended cadence" is not.
- If a result **contradicts the spec**, say so plainly and prominently. Do not
  reconcile it, explain it away, or adjust a parameter until it agrees.

Favor complete tables over prose. Include the exact invocation for every run.

In the wrap-up, in this order:

1. Cache regeneration: calibrated cost, actual spend, files produced, failures,
   and which directory name you left in place.
2. Step 0d: the pinned reference universe, window, and invocation.
3. Baseline reproduction: expected vs actual.
4. **The cadence surface** — return and max drawdown by `K`, phase-averaged,
   with across-phase spread beside each. State plainly whether the surface is
   smooth or jagged; a jagged surface means nothing is spec'd from this run and
   you should say so.
5. **Where the surface crosses SPY / QQQ / TMFC / equal-weight.**
6. Seasonal-cadence variant vs uniform `K`, with session counts for both.
7. Scope comparison. §3 predicts full-re-sizing degrades sharply at small `K` by
   pinning winners near 25% — confirm or refute.
8. Veto results. The 0%-vs-capitulation gap is the headline product number.
9. Ordering variants — how much of the baseline was alphabetical bias.
10. Ceilings, **by sub-period with 2022 separate** (§10 rule 5). Both are
    structurally biased by this corpus (§10 rule 4) — report, do not recommend.
11. Bug-fixed cell delta.
12. Unit test results.
13. Anything contradicting the spec.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- Work on `sweep/v6-eval-cache`. Do not restore the v6 prompt onto `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Analyst/allocator firewall holds: the allocator never receives transcripts.
- Do not write new handoff docs. This prompt in, one wrap-up out.
- Selection is on **robustness across start dates and phases**, never peak
  return.
