# Measure the allocator operating model (task #77)

## What this is

A **measurement** task, not a production build. You are running the backtest
harness to price a set of design decisions that have already been made. Do not
change `server/routes/moves.js`. Do not build the new allocator. The output is
numbers and a wrap-up.

Write findings to `./wrap-ups/run-allocator-operating-model-sweep-out.md`.

## Read first, do not re-derive

1. **`docs/architecture/ALLOCATOR_OPERATING_MODEL.md`** — the spec this measures.
   Agreed 2026-08-30 after a full design session. Its decisions are closed.
   §10 is your run plan; §9 is the contract; §11 lists two known defects that
   stay in for the baseline.
2. `docs/architecture/BACKTEST_SIMULATOR.md` — harness design and the
   pre-declared success criteria (adopted unchanged).
3. `docs/architecture/PORTFOLIO_ANALYST_SPEC.md` — cap authority, the 2×2 matrix,
   the 2026-05-17 variable-cap retirement.
4. `CLAUDE.md` and `docs/architecture/DESIGN_PRINCIPLES.md` — standing rules.
   Note `DESIGN_PRINCIPLES.md` §5 is known stale on the Type B cap; the spec
   above wins.

**Do not reopen:** universe composition, the cap values, the barbell
target→ceiling decision, the veto model, or the choice of cash-deployment scope.
All settled. If you believe one is wrong, say so in the wrap-up — do not act on
it.

## Step 0 — two reconciliations (do these first, they are quick)

**Task #75** (`splitBucketTarget` zero-cap divisor). The wrap-up
`wrap-ups/fix-splitbuckettarget-zerocap-divisor-out.md` says fixed and verified;
the tracker shows it pending. Check `git log` for the commit rather than
trusting either source. Report which is right in one line.

**The eval cache is missing.** `analysis/data/evals/v6_sonnet-4-20250514/` is not
in the working tree — only the 659 raw transcripts in
`analysis/data/transcripts/`. `load_events_from_cache()` will return an empty
list. Regenerate it before anything else:

```zsh
cd ~/path/to/investment-agent
python3 analysis/dump_transcripts.py          # confirm actual flags before running
ls analysis/data/evals/v6_sonnet-4-20250514/*.txt | wc -l   # expect ~659
```

If regeneration is expensive or partially fails, **stop and report** rather than
running a sweep on a partial corpus.

## Step 1 — reproduce the baseline

`allocator_v3`, unmodified, per-call cadence, alphabetical ordering, all-cash
start. This must reproduce the known full-window result (v3 flat-50% Type B
≈ $287k) before anything else runs. If it does not reproduce, **stop and report
the discrepancy** — every downstream number is relative to this.

Bank the number and the exact invocation in the wrap-up.

## Step 2 — instrument, without changing behavior

Add to the per-run outputs, as diagnostics only:

- aggregate **speculative share of portfolio** over time (this determines
  whether the §6 ceiling would ever bind — do not implement the ceiling yet)
- average cash %, days in cash
- count of sessions where cash was the binding constraint
- count of contested rank decisions (more eligible demand than cash)
- per-ticker mean staleness

## Step 3 — parameterize the harness

Per `ALLOCATOR_OPERATING_MODEL.md` §2–§5. The simulator today is hardcoded to
per-call, immediate, alphabetical. Add, as parameters:

- **`K`** — session interval in days; decisions batch to session boundaries;
  a call is in scope when `call_date <= session_date`; trades at that day's close
- **`phase`** — the session grid's start offset
- **`scope`** — `new_calls_only` | `cash_deployment` | `full_resizing`
- **`session_change_limit`** — max pp of portfolio one position may move per session
- **`veto`** — `none` | capitulation model (§8), with `p`
- **`tie_break_seed`**
- **`cash_ceiling`**, **`spec_ceiling`** — both default off

Existing behavior must be exactly recoverable: `K=0` (or per-call),
`scope=new_calls_only`, no limits, alphabetical. Assert that against Step 1's
number.

## Step 4 — run the grid

Axes and values: `ALLOCATOR_OPERATING_MODEL.md` §10. Order of work:

1. **Cadence first** — `K` × `phase`, scope held at `cash_deployment`, no veto,
   no limits. This is the headline result.
2. **Scope** — the three values at the best-performing `K` and at `K=90`.
3. **Session change limit** — at the best `K`.
4. **Veto** — capitulation at p = 10/20/30, at the best `K` **and** at `K=90`
   (it is path-dependent and interacts with cadence).
5. **Ordering variants** — reverse-alphabetical and seeded-random, on the best
   region only, to price the alphabetical bias.
6. **Ceilings** — cash and speculative, information only.
7. **Bug-fixed cell** — §11's two defects fixed, at baseline settings, to
   quantify what they were worth. Do not fix them anywhere else in this run.

## Step 5 — report

**Scope boundary — read this before writing anything.**

Your job ends at reporting. Specifically:

- **Do not select a winning configuration.** Present the surface; do not crown a
  cell. If you find yourself building a case for why one unusually good result
  should be believed, that is the signal to distrust it and say so.
- **Do not amend `ALLOCATOR_OPERATING_MODEL.md`** or any other spec or design
  doc. Interpretation and spec changes happen in the design session that has the
  full context; you produce the inputs to it.
- **Do not resolve the §12 open items** (session change limit, speculative
  ceiling level, verdict grace window). Report what the numbers say about each
  and stop.
- **Report shape and magnitude, flatly.** "Return declines monotonically from
  $X at K=7 to $Y at K=90, crossing SPY between K=30 and K=60" is the deliverable.
  "K=30 is the recommended cadence" is not.
- If a result **contradicts the spec**, say so plainly and prominently. Do not
  reconcile it, explain it away, or quietly adjust a parameter until it agrees.

Write the wrap-up to `./wrap-ups/run-allocator-operating-model-sweep-out.md`.
It gets loaded into the design session — so favor complete tables over prose
summaries, and include the exact invocation for every run so results can be
reproduced or extended without guesswork.

In the wrap-up, in this order:

1. Baseline reproduction: expected vs actual.
2. **The cadence surface.** A table of return and max drawdown by `K`,
   phase-averaged, with the across-phase spread beside each. State plainly
   whether the surface is smooth or jagged — per §10 interpretation rule 2, a
   jagged surface means nothing is spec'd from this run and you should say so.
3. **Where the surface crosses SPY / QQQ / TMFC / equal-weight.** That crossing
   is the spec's minimum viable cadence.
4. Seasonal-cadence variant vs uniform `K`, with session counts for both.
5. Scope comparison. §3 predicts full-re-sizing degrades sharply at small `K` by
   pinning winners near 25% — confirm or refute.
6. Veto results. The 0% vs capitulation gap is the headline product number.
7. Ordering variants — how much of the baseline was alphabetical bias.
8. Ceilings, **reported by sub-period with 2022 separate**, per §10 rule 5.
   Both are structurally biased by this corpus (§10 rule 4) — report, do not
   recommend.
9. Bug-fixed cell delta.
10. Anything that contradicts the spec. Say it plainly; do not smooth it over.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers, no Linux-only path assumptions.
- Complex commands and SQL go in fenced blocks in the wrap-up, not separate files.
- Analyst/allocator firewall holds: the allocator never receives transcripts.
- Do not write new handoff docs. This prompt in, one wrap-up out.
- Selection is on **robustness across start dates and phases**, never on peak
  return. If you find yourself explaining why one unusually good cell should be
  believed, that is the signal to distrust it.
