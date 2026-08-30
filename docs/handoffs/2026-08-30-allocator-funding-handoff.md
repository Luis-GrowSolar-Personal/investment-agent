# Handoff: allocator operating model — task #77 and what it turned into

**Date:** 2026-08-30
**For:** a new Cowork session continuing the allocator thread.
**Primary artifact:** `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` — read it
in full. It is the spec; this document is orientation, not a substitute.

---

## 1. What this session did

Started on task #77 (two sizing formulas disagreeing 11x). Ended somewhere else:
**#77 was a symptom, and the allocator has never been the thing allocating.**

The session produced a design spec, resolved #77 by deletion rather than
unification, and then — through five deliberately-stopped CLI runs — discovered
that the validated backtest's results were determined mostly by the earnings
calendar rather than by any allocation rule.

**Read `ALLOCATOR_OPERATING_MODEL.md` before proposing anything.** Its decisions
are closed. Do not re-derive them.

## 2. Design decisions — closed, do not reopen

- **#77 resolves by deletion.** The barbell bucket targets (`estPoolPct` /
  `specPoolPct`) create the pool that `splitBucketTarget` must divide; that
  division was implemented twice, differently. Remove the targets and pools,
  `allocate` and `sizeSide` both go with them. Five divergences documented in §1.
- **Barbell becomes a ceiling on speculative exposure, not a two-sided target.**
  Luis, verbatim: *"I want to own the best names, period."* The est/spec mix is
  an output, with a backstop against the 90%-speculative case.
- **Session cadence `K`** is the operating parameter — open app, upload, execute.
  Ingestion timing is unobservable; there is no second cadence parameter.
- **Scope: cash-deployment re-evaluation.** Not new-calls-only (cash idles); not
  full re-sizing (pins winners near 25%, would destroy the compounder effect the
  Type B result depends on).
- **Deploy to cap, never above.** Caps inviolable. No over-cap holding to avoid
  cash drag — that is the capitulation pattern adopted as policy.
- **Ranking, not pool division**, rations cash: confidence filter → verdict
  recency → gap to target → **seeded-random tie-break, never alphabetical**.
- **Type A/B is a ceiling only**, never a relative weight. Production's 1.5×
  Type B multiplier (`moves.js:207`) is removed deliberately, not incidentally.
- **All-cash day 1** for simulation. Production has three transition paths; the
  hybrid (liquidate tax-advantaged, converge gradually in taxable) is recommended.
- **Veto model is capitulation, not random.** Random independent veto self-heals
  (99.97% survival at 20% over five recurrences) and would produce a false
  negative. Pets form at the 25% profit-take crossing, decline Trim *and* Exit,
  capitulate at −30% from trailing peak position value, full exit.
- **Funding before ordering** (settled at session end). Ordering is decisive only
  because funding is broken; measured now, the answer expires when funding is
  fixed.

## 3. The empirical findings — all measured, all in the spec

**Contention is the norm, not the exception.** 63.4% of calls in the 32-ticker
universe land on a day with at least one other call; 56.5% in top20-2021.

**Same-day order is resolved alphabetically** (`data.py:178`,
`data_from_cache.py:76`), consumed sequentially with immediate execution. AAPL
wins every contested day; TTD loses every one.

**Earnings cluster hard.** ~70% of calls fall in days 15–42 after quarter-end;
month 3 of each quarter carries 5–11%. A seasonal cadence (weekly in the wave,
monthly otherwise) is ~24 sessions/year vs uniform-weekly's 52.

**Phase is a nuisance parameter.** At a single fixed grid, per-ticker staleness
spread reaches 51 days at K=90; averaged across phases it collapses to ≤2 days
through K=60. Sweep phase, report phase-averaged, use the spread as a fragility
signal.

**And the finding that reframed everything:** cash below 1% of portfolio on
**88.7%** of trading days from **week 6 of 122**; **96% of Adds rationed**, 75.8%
entirely unfunded; **$2.37M** cumulative shortfall against $100k. The whole book
was set in 16 days by the three names that reported first. AVGO asked for $56k in
March 2022, got zero, and went ~8x in the window.

Root cause: `target_pct = min(recommended_size, type_cap)` makes the cap a
*target* when the analyst is bullish. Sixteen names at 15–50% caps sum to ~400%.

## 4. Data reality — read before trusting any number

- **$287k cannot be reproduced.** The v6 file eval cache was never committed
  (gitignored), no backup exists, and `claude-sonnet-4-20250514` is retired.
  Nobody had ever tried to reproduce it before this session.
- **The DB corpus is 71% v6-covered on ALL16**, and the gap is time-correlated —
  everything from ~mid-2024 carries a pre-v6 evaluation. Using it whole would
  confound the exact variable the cadence sweep measures.
- **The usable slice is 2022-01-01 → 2024-06-12**, ALL16, 148 events, 100% v6
  coverage. That is where all current numbers come from.
- **Do NOT refresh `price_cache.json` / `fundamentals_cache.json`.** Frozen
  2026-05-11, six days before the reference runs. The 111-day staleness warning
  is what makes tier reproducible. Refreshing breaks it.
- **Backup exists and restores**: `~/investment-agent-backups/analysis_corpus_20260830.sql`
  (41 MB) plus schema. Verified against a throwaway local Postgres.
- **Stored trend fields are trustworthy inside the v6 window** — recomputed vs
  stored `final_action` agreed 148/148.
- **`FSLR 2024-02-27` is duplicated** (`Transcript` 280 and 284) and sized twice
  daily. At least three duplicates exist across the manifest.
- **Ticker renames are destructive.** `save.js` updates `Ticker.symbol` in place;
  no alias table, no audit. SPWR (ex-CSLR) and META (ex-FB) are both clean, by
  luck. **RUBI is a live reassignment** — 193 days from 2025-08-04 while MGNI,
  the company that used to be RUBI, holds the full history.

## 5. Where things stand

Harness validated on the clean window: v1/v2/v3 = $112,118 / $116,286 / $141,837,
ordering holds, v3 beats SPY/QQQ/TMFC/equal-weight on return. **But by
`BACKTEST_SIMULATOR.md`'s own pre-declared bar it is a Fail on risk** — 45.6% max
drawdown against a median-baseline+5pp bar of 38.0%.

**Next action:** run `prompts/sweep-funding-modes.md` (CLI, Sonnet, $0). Eight
cells comparing `no_reserve` / `cash_reserve` / `swap_funding`, plus the
retrospective ordering probe.

**Then, in order:** ordering rule measured in the fixed funding regime → Option B
(re-evaluate ALL16's 312 transcripts under the v6 prompt and a current model,
~$25–35, to recover the full window) → the cadence / scope / veto sweep.

**Do not run the cadence sweep before funding is settled.** Changing K changes
which names report before the money runs out, so the surface would measure an
arrival-order lottery and read as information staleness.

## 6. How this thread works

`prompts/*.md` in → CLI session with DB access → `wrap-ups/*-out.md` out → design
session interprets. Cowork has no DB access. The CLI never selects a
configuration, amends a spec, or resolves an open item — it reports.

**Every prompt carries a hard stop-gate, and every one of them has fired.** Five
runs stopped: a wrong tool name, a retired model, a one-sided version filter, a
coverage gate, and a fabricated threshold of mine. Each stop found something real.
Keep writing gates, and keep the standing assertion that any instrumented run must
still reproduce **$141,837** — it caught a `**kwargs` signature bug that would
have silently disabled every tier cap and first-call starter across the sweep.

## 7. Open items

In `ALLOCATOR_OPERATING_MODEL.md` §12, and: correlation-based cohort caps
(promoted to committed backlog in `PORTFOLIO_ANALYST_SPEC.md`), transcript dedup
plus a uniqueness constraint on (tickerId, callDate), a persisted former-symbol
trail, and corpus preservation rules for `PROMOTION_GATE.md` — `promptVersion` /
`modelVersion` are null on 764 of 805 rows.

## 8. Reproducibility — the lesson of this session, made operational

This session spent five runs discovering that `$287k` cannot be reproduced at any
price. Nobody had ever tried. The corpus was gitignored, the prompt version was
recorded on 41 of 805 rows, the model is retired, and the tier inputs are mutable.

**`ALLOCATOR_OPERATING_MODEL.md` §10b is now a hard contract: a result without a
manifest is not citable.** Every run emits `<run_id>-manifest.json` pinning the
git commit and dirty flag, the corpus window and event hash, the DB snapshot
checksum, the prompt and model versions, checksums for `type_classifications.json`
and both tier caches, every parameter and seed, and the output hashes.

**Three immediate actions, before the next run:**

1. **Commit `sweep/db-corpus-baseline`.** Today's numbers — `$141,837`, the 96%
   rationing figures, the whole clean-window baseline — live on an *uncommitted*
   working tree. If it is lost they join `$287k`. This is the most urgent item on
   the board.
2. **Archive `price_cache.json` and `fundamentals_cache.json`** to a dated,
   backed-up location outside the repo. They are gitignored and mutable, frozen
   at 2026-05-11 only because nobody has re-run the fetch scripts. One
   `fetch_fundamentals.py` silently changes every tier assignment and every
   15%-vs-35% cap. **Never refresh them to clear the staleness warning.**
3. **Re-verify the corpus dump restores** and record its checksum, then keep
   snapshotting on change.

Going forward, stamp `promptVersion` / `modelVersion` server-side on every new
Analysis row — the columns exist and are null on 764 of 805.

## 9. Standing rules

`python3` / `pip3`, zsh, no `--break-system-packages`, no Linux package managers.
Analyst/allocator firewall holds. Handoff docs only when requested. Complex
commands in fenced blocks in chat, not separate files. Selection is on robustness
across start dates and phases, never peak return.
