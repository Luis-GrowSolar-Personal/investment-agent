# Clean-window baseline, corrected (task #77, Option A — second attempt)

Supersedes `prompts/clean-window-baseline.md`. Read
`wrap-ups/clean-window-baseline-out.md` first — Steps 1, 2 and 4's Gates 1/2/4
all passed and are **carried forward, not redone**.

**Gate 3 failed because the previous prompt was wrong, not because the trend
layer is inert.** Two errors, both mine:

1. **History truncation.** I told you to recompute the trend layer over the
   events `load_call_events()` returned — which were already filtered to
   `[2022-01-01, 2024-06-12]`. So each ticker's history began at the window
   boundary and `compute_trend_verdict` saw no prior calls. Your own evidence:
   **null `trajectory` rose from 3 to 31**. The layer was starved, not idle.
   The file path does it in the correct order — `load_events_from_cache()` loads
   everything, `attach_trend_verdicts()` computes over full per-ticker history,
   and only then does `run_simulation` filter by date.
2. **The ~5% floor was junk.** I derived it from "44%→54% on 41 calls," which is
   an *accuracy improvement*, not a disagreement rate. A layer that overrides a
   small minority of calls can move accuracy ten points if the overrides are
   well-targeted. Your measured 4.1% stored / 3.4% recomputed may be perfectly
   normal. **That threshold is withdrawn.** Gate 3 is replaced below.

Standing rules unchanged: read-only against the DB, no LLM calls, no API spend,
no DB writes, **do not refresh `price_cache.json` / `fundamentals_cache.json`**
(frozen 2026-05-11, which is what makes tier reproducible — the 111-day
staleness warning is expected). Do not run `sync_trend_to_db.py`. Do not build a
prose fallback for `type_classification`. Continue on
`sweep/db-corpus-baseline`.

Write findings to `./wrap-ups/clean-window-baseline-v2-out.md`.

---

## Carried forward — do not recompute

- Clean window: **2022-01-01 → 2024-06-12** (`C` = 2024-06-12; first coverage
  failure is TSLA 2024-07-23). 148 transcripts, 100% v6 coverage.
- Two-sided cutoff in `load_call_events()` — already added, keep it.
- `type_for_ticker` resolves for all 16; abort-if-absent assertion — keep it.

## Step 1 — fix the trend-history scoping

Load events for the universe with **no `start_date` restriction** (keep the v6
`createdAt` window and `end_date = 2024-06-12`), so each ticker's full prior
history back to its first call is present. Recompute the trend layer over **that
full list**. Then pass the whole list to `run_simulation` with
`start_date=2022-01-01` — the simulator already filters events to the window
itself (`simulator.py`, the `events = [e for e in events if start_date <=
e.call_date <= end_date]` step).

Coverage supports this: your Step 1 confirmed **zero v6 violations from
2020-09-10 through 2024-06-12**, so the pre-window history is available inside
the v6 window.

Report the event count fed to the recompute versus the count that survives into
the simulation. They should differ — that difference is the pre-window history
the earlier run was missing.

## Step 2 — Gate 3, replaced

The question is not "does the trend layer disagree enough." It is **"is the
recompute faithful."** Two checks with falsifiable predictions:

1. **Null `trajectory` should return to roughly the stored level (~3), not 31.**
   That is the direct test of whether history is now sufficient. Report the
   count. If it stays high, the fix didn't take — **stop and report.**
2. **Recomputed `final_action` vs stored `final_action` agreement.** Report the
   rate and list every disagreement with ticker, date, stored value, recomputed
   value.

Interpretation, stated in advance so it isn't rationalized after:

- **High agreement** → the recompute is faithful *and* the DB's stored trend
  fields were fine all along. That retires the concern that started this thread.
  Proceed, and say so plainly.
- **Low agreement** → the two paths genuinely differ and we need to know which
  is right before anything is built on either. **Stop and report** with the
  disagreement list.

Do not pick a threshold and do not treat either outcome as failure. Report the
number and which of the two readings it supports.

## Step 3 — ticker identity validation

The DB's rename mechanism (`server/routes/save.js`, `formerSymbol` → "simple
rename") **updates `Ticker.symbol` in place. There is no alias table, no
`formerSymbol` column, no audit.** A renamed ticker's prior identity is gone,
and nothing distinguishes:

- **Type 1** — same company, new ticker (FB → META). Continuous history correct.
- **Type 2** — ticker reassigned to a *different* company. Continuous history
  would be a fabrication.

A Type 2 case already exists in this dataset: **RUBI** has 193 days starting
2025-08-04 while **MGNI** — the company that used to trade as RUBI — has the
full 1596-day history. The ticker was reused.

For each of the 16 universe tickers, report:

1. Price-series first date, and first transcript date.
2. Any ticker whose price history starts **materially later than its peers**
   (most start 2020-01-02). Known short: SPWR 2023-01-03, AMPX 2022-09-15,
   ENVX 2021-01-05, EOSE 2020-11-02, QS 2020-08-17 — the last four are SPAC-era
   listings and expected; confirm rather than assume.
3. Whether the transcripts for that ticker name **one continuous entity**. Grep
   the company name from each transcript and report any ticker whose transcripts
   name more than one company.

Already established, carry forward rather than re-deriving: SPWR's seven
transcripts are all Complete Solaria (rebranded SunPower in early 2025), its
price series is Complete Solaria's own (SPAC ~$10 through 2023-07-19, then sub-$5),
and old SunPower Corporation's history is absent. META is continuous through the
FB rename. **Both are clean.** This step is to confirm nothing else is not.

Flag anything suspicious. Do not fix it.

## Step 4 — the substitute correctness gate

Run **v1, v2, v3** over the clean window, ALL16, $100,000 initial, 50/50
taxable/tax-advantaged, `type_for_ticker` from the frozen JSON, unchanged
caches — alongside **SPY, QQQ, TMFC, and equal-weight-of-universe** buy-and-hold
on the same dates.

Report final value and max drawdown for all seven.

**The check:** v3's tier-aware caps, profit-take and no-average-down were each
introduced to fix a diagnosed failure, so **v3 ≥ v2 ≥ v1 is the expected
ordering**. If it inverts, the harness or the corpus is wrong and nothing
downstream is trustworthy — report it plainly and stop.

Whether v3 beats SPY on a 2.5-year window is **information, not pass/fail**.
Short windows are noisy. Say which and move on.

**Also run v3 with SPWR excluded (ALL15).** SPWR contributes one transcript of
148 — it takes a 5% first-call starter and never gets another decision for the
rest of the window. That is a dead allocation, not a modelled position. Report
both and the difference.

## Step 5 — report

Scope boundary: report, do not decide. Do not select a configuration, do not
amend specs, do not resolve §12 open items, do not proceed to the cadence sweep.

Lead with:

> **Clean window 2022-01-01 → 2024-06-12, 148 events. Trend recompute:
> trajectory nulls X, stored-vs-recomputed agreement Y%. v1/v2/v3 = $A/$B/$C.
> Ordering holds / does not hold.**

Then Step 2's two checks with the disagreement list, Step 3's identity table,
Step 4's seven-row table plus the ALL15 variant, and — flagged plainly —
anything that looks wrong even where a gate passed.

End with an explicit statement: **is the harness sound enough to build the
cadence sweep on?** That is the one question this run exists to answer.

Note for context, not for you to act on: 148 events is roughly half the full
window's 312, which is thin for a cadence sweep sliced across five values of K
and three phase offsets. The design session is aware; this run is about
validating the machinery, not powering the experiment.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, no DB writes, no cache refreshes.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
