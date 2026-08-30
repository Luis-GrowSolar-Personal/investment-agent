# Funding mode sweep (task #77) — the prerequisite for everything else

`wrap-ups/diagnose-spwr-and-cash-instrumentation-out.md` established that the
allocator has never been the operative mechanism: cash sits below 1% of portfolio
on **88.7%** of trading days from **week 6 of 122**, **96% of Add-shaped
decisions are rationed** (75.8% entirely unfunded), and cumulative unmet demand
is **$2.37M against $100k of capital**. The whole book was set by the three names
that reported first, in sixteen days.

**Design-session decision, settled: funding mode is fixed before ordering, and
before the cadence / scope / veto sweeps.** Ordering is decisive only *because*
funding is broken; measured now, that number describes a regime we are replacing.

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` §5 in full — it carries the
measurements above, the sequencing decision, and the swap-funding specification
you are implementing. Do not re-derive any of it.

**No LLM calls, no API spend.** Clean window (2022-01-01 → 2024-06-12, ALL16,
148 events), `sweep/db-corpus-baseline`. Write findings to
`./wrap-ups/sweep-funding-modes-out.md`.

---

## Step 0 — carry forward, and one data fix

Carried forward, do not redo: the clean window and its 100% v6 coverage; the
two-sided cutoff; the `DailySnapshot` cash fields; the funding/event-log wrapper
from `diagnose_spwr_and_cash.py`.

**Keep the standing assertion.** Every run must reproduce **$141,837** under
`funding_mode=no_reserve` with all new parameters off. If it moves, the
implementation changed behavior — report it, do not work around it. That
assertion already caught one silent signature bug; it stays.

**FSLR duplicate.** `Transcript` ids 280 and 284 are the same call. It is
currently evaluated and sized twice on the same day. **Do not write to the DB.**
De-duplicate **in the loader** — when two Transcript rows share (ticker,
callDate), keep the lower id and drop the other — and report the resulting event
count (expect 147 for ALL16). Report whether any other (ticker, callDate) pair is
duplicated. Run the `no_reserve` control both with and without dedup so its
effect is isolated rather than mixed into the funding comparison.

## Step 0b — reproducibility, before any run

**Commit the branch first.** `sweep/db-corpus-baseline` currently holds every
result this thread has produced, uncommitted. Commit it (do not merge to `dev`)
so this run has a real SHA to record.

**Archive the tier caches.** Copy `price_cache.json` and `fundamentals_cache.json`
to `~/investment-agent-backups/tier-caches-YYYYMMDD/` and record their sha256.
They are gitignored and mutable; they are the largest un-pinned input to every
number here. **Do not refresh them.**

**Emit a manifest per cell**, per `ALLOCATOR_OPERATING_MODEL.md` §10b — read it
for the field list. At minimum: git SHA + dirty flag, corpus window and event
count, checksums for `type_classifications.json` and both tier caches, every
parameter and seed, and the resulting final value and max drawdown. Write them
beside the outputs and reference them in the wrap-up.

A cell whose manifest records `git_dirty: true` is not citable. Say so if it
happens rather than quoting the number.

## Step 1 — implement three funding modes

**`no_reserve`** — today's behavior. Control.

**`cash_reserve`** — never deploy below X% of portfolio value in combined cash.
An Add that would breach the floor is truncated to what the floor allows.
Levels: 5 / 10 / 20%.

**`swap_funding`** — per §5's specification, which is authoritative. Summary:

- fires when an eligible candidate (§4) cannot be funded from available cash
- donors are held positions whose latest verdict is `Hold` / `Trim` / `Exit`
  — **never a position whose latest verdict is `Add`**
- lowest-ranked eligible donor first, by §4's ranking
- at most **25% of the donor per session**; never below minimum position size;
  drain `tax_advantaged` before `taxable`
- raise only what the candidate's target requires, subject to the per-session
  change limit — not a wholesale rebalance
- realized gains from displacement reported **separately** from ordinary
  Trim/Exit

Where §5 is ambiguous, **stop and report the ambiguity** rather than choosing.
This mechanism deliberately creates taxable events and its guards are the point.

## Step 2 — run the grid

ALL16, clean window, `decide_v3`, frozen-JSON `type_for_ticker`, unchanged
caches, alphabetical ordering held constant throughout (it is the *next*
question, not this one).

| Cell | funding_mode | session change limit |
|---|---|---|
| 1 | `no_reserve` (dedup off) | off |
| 2 | `no_reserve` (dedup on) | off |
| 3 | `cash_reserve` 5% | off |
| 4 | `cash_reserve` 10% | off |
| 5 | `cash_reserve` 20% | off |
| 6 | `swap_funding` | off |
| 7 | `swap_funding` | 10pp |
| 8 | `no_reserve` | 10pp |

For every cell report: final value, max drawdown, **and the full funding
diagnostics** — days below 1% cash, share of Adds fully funded / partial /
unfunded, cumulative shortfall, number of distinct tickers ever held, and (for
`swap_funding`) displacement count and realized gains attributable to it.

The diagnostics matter as much as the returns. A cell that scores well while
still leaving 70% of Adds unfunded has not fixed anything.

## Step 3 — the retrospective ordering probe

Separate, clearly labelled, **not a design input.** On cell 1 only, re-run with
same-day ordering reversed and with three random seeds. Report the spread of
final values.

This answers one question and no others: **how much of the historical result was
arrival-order luck?** Do not use it to recommend an ordering rule — that is the
next thread, and it will be measured in the fixed funding regime.

## Step 4 — report

Scope boundary: report, do not decide. Do not select a funding mode, do not amend
any spec, do not resolve §12 items, do not proceed to the cadence sweep.

Lead with:

> **no_reserve control reproduces $141,837. Best-diagnostics cell: [cell], with
> X% of Adds funded (vs 4% today) and N distinct tickers held (vs today's [N]).
> Retrospective ordering spread on the current model: $A–$B.**

Then the eight-cell table with full diagnostics, the swap-funding displacement
log, and the ordering probe.

Flag plainly: any cell where returns improve but the funding diagnostics do not
(a warning sign that something else is driving the number), any ambiguity in §5
you had to stop on, and anything that contradicts §5's measurements.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes** (dedup happens in the loader).
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
