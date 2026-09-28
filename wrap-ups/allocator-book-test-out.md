# Allocator book test — severity-sized trims on hundreds of train books — wrap-up

**Prompt:** `prompts/allocator-book-test.md`. **Run ID:** `allocator-book-test`.
**Cost:** $0 — no API calls, no DB writes, no scoring, no cache refresh, no fetches.
**Driver:** `analysis/allocator_book_test.py`.

> Frozen before any arm ran: t1 = **−10.0**, t2 = **−8.0** (**160** flagged train
> calls). In **200** random 16-name books, trimming the names B flags and P9
> rates severe (arm 3) beat holding the book (arm 0) on return per drawdown in
> **96.0%** of books (median gain **0.0577**, range **0.0528** to **0.0660**;
> lowest with one company removed **94.2%**, FRC). It beat the same trims on
> random calls (arm 3R) in **69.0%** of books (median gain **0.0076**, range
> **0.0058** to **0.0110**; lowest with one company removed **59.6%**, LLY).
> **Headline: own more QQQ.** Plain trims (arm 2): **99.0%** vs arm 0, and arm
> 2 beats arm 3 itself in **95%** of books — sizing by severity did worse than
> trimming everything, not better (see "The arm 2 vs. arm 3 reversal," below).
> Stratified books: arm 3 vs arm 0 **100.0%**; arm 3 vs arm 3R **85.5%**
> (floor **72.0%**) — passes, unlike random. Final value, arm 3 vs arm 0,
> median across random books: **$170,563** vs **$145,426**. Daily drawdown:
> **41.53%** vs **41.94%**. Arm M: **not run** — the event loader
> (`load_events_dedup_on`) is DB-backed and hardcoded to ALL16, not
> parameterizable to the 55 train companies without a workaround. Units: **do
> not** matter (arm 3F **96.5%** vs arm 3 **96.0%**, within 10 points).

---

## What this run can and cannot show (per the prompt, stated plainly)

t1, t2, and every call's flag come from the same train calls the 400 books
are drawn from. **This is not a second look at the signal.** It tests
whether the signal survives the mechanics: position sizes, drift,
sequencing, compounding, drawdown, and two-step execution. A pass on arm 3
vs. arm 0 means the mechanics don't eat the per-trim edge on its own; it
does not confirm the signal itself. Only tune does that. The arm 3 vs. arm
3R result below is the part of this run that speaks to skill rather than
mechanics, and it did not clear the bar on random books.

## Step 0.5 — preflight

- **Companies:** 55, from `analysis/data/run_state/p6-output-format-round/calls.csv`
  (1,217 calls). None appears in `SPLIT_V7_RESERVE_REPLACEMENTS.json`'s tune
  or holdout lists — asserted.
- **Prices:** `analysis/data/corpus_v2/scorer_price_cache_v1.json`. QQQ
  present (added by `prompts/per-trim-value-qqq.md`) — asserted.
- **Window:** start **2020-01-02**; end **2026-06-17** (first trading day
  on/after last train call `2025-12-17` + 182 days). 2,358 days, 79 monthly
  sessions per phase.
- **Late listings:** AMPX first price 2022-09-15, EOSE 2020-11-02, QS
  2020-08-17 — matches the prompt's stated dates exactly. Each sits in QQQ
  from window start until its first session on/after that date, identical
  across every arm.
- **Every one of 1,217 calls** resolved a tradeable-entry action-session in
  every phase (`n_no_entry_date: 0`).
- **Strata pools** (`p3_guidance_ledger_driver.stratum_map()`): megacap =
  the 15 S1 tickers + MSFT (16); mid = the 9 S2 tickers (9); speculative =
  the 2 S4 tickers (FRC, SUNW) + AMPX, EOSE, QS, RUN, TTD (7) — asserted
  counts match R4 exactly.

## Step 1 — t1/t2, frozen before any arm ran

Flag = mean of B's two draws ≤ −2: **160** train calls (of 1,217). Among
those, averaged P9 `expectedReturn` at the 20% mark (nearest rank, ties by
seed 11): **t1 = −10.0**. At the 40% mark: **t2 = −8.0**. Committed at
`e105aba`, before any arm ran. `analysis/data/run_state/allocator-book-test/results.json`
→ `n_flagged`, `t1`, `t2`.

**Expected mismatch, as the prompt anticipated:** this flags on the mean of
B's two draws (160 calls), not each draw separately (374 pooled rows in
`per-trim-value-qqq-out.md`). Different populations; both point the same
direction, as required (see the arm 3 vs. arm 3R read below against the
per-trim $342/flagged-call lead — same sign, different mechanism).

---

## Step 1 result table — random books (n = 200)

| arm | rule | median final value | median CAGR | median daily DD | median return/DD | vs. arm 0 win share | vs. arm 0 range | floor (company removed) |
|---|---|---|---|---|---|---|---|---|
| 0 | hold, never trade | $145,426 | 5.97% | 41.94% | 0.1392 | — | — | — |
| 1 | QQQ alone | $216,073 | 12.67% | 35.62% | 0.3558 | 100.0% | [0.2067, 0.2254]* | 100.0%* |
| 2 | fixed 2.5% trim, every flag | $178,869 | 9.42% | 41.29% | 0.2162 | **99.0%** | [0.0693, 0.0841] | 98.5% (MS) |
| **3** | **severity-sized (t1/t2), QQQ** | **$170,563** | **8.62%** | **41.53%** | **0.1986** | **96.0%** | **[0.0528, 0.0660]** | **94.2% (FRC)** |
| 3F | severity-sized, position fraction | $170,702 | 8.63% | 41.47% | 0.1989 | 96.5% | [0.0532, 0.0671] | 94.8% (CMI) |
| 3S | arm 3, proceeds to SPY | $164,941 | 8.06% | 41.16% | 0.1870 | 93.0% | [0.0400, 0.0554] | 89.8% (FRC) |
| 2R | arm 2's no-skill control | $174,506 | 8.99% | 42.07% | 0.1977 | 98.0% | [0.0505, 0.0634] | 96.9% (BOX) |
| 3R | arm 3's no-skill control | $168,849 | 8.44% | 41.60% | 0.1867 | 97.5% | [0.0367, 0.0474] | 96.3% (PG) |

\* arm 1's "win share vs. arm 0" compares QQQ-alone to the 16-name book —
included for completeness, not part of any gate.

**The two readings that gate the headline, random books:**

| test | win share | range | company-removal floor | passes 70% rule |
|---|---|---|---|---|
| **1a. arm 3 vs. arm 0** ("beat holding") | 96.0% | [0.0528, 0.0660] | 94.2% (FRC) | **yes** |
| **1b. arm 3 vs. arm 3R** ("analyst chose the trims") | 69.0% | [0.0058, 0.0110] | 59.6% (LLY) | **no** |

1a passes comfortably. 1b misses on two of its three legs: win share sits
0.5 points under the 70% bar, and the company-removal floor (59.6%, dropping
every book with LLY) is 10 points under. The range does clear zero. Per the
pre-registered reading, **1a passing and 1b failing reads "own more QQQ":**
the trims beat leaving the book alone, but not because B and P9 chose better
trims than a random call in the same quarter would have — mostly because the
money moved into QQQ, which had a strong run over this window regardless of
which name funded it.

**Reading 2 — "plain trims add value":** arm 2 vs. arm 0 passes even more
cleanly than arm 3 (99.0%, floor 98.5%). Arm 2 vs. arm 2R: 74.5%, range
[0.0091, 0.0186], **floor 65.4% (BLK) — fails the company-removal leg.**
The prompt predicted arm 2 would fail or be mixed on the per-trim evidence;
instead it clears 1a's practical bar better than arm 3 does, and comes
closer to clearing 1b than arm 3 does. This is the first sign of the
reversal below.

**Reading 3 — "severity adds over plain": arm 3 vs. arm 2, both book sets,
fails hard** — see next section.

## The arm 2 vs. arm 3 reversal — a finding, not a reason to stop

The per-trim run found severity-sizing turns a losing rule into a winning
one (`per-trim-value-qqq-out.md`: unsized A − B included zero; sized A − B
per point was about 5x larger, on both destinations). This run found the
opposite sign at the book level:

| | random books | stratified books |
|---|---|---|
| arm 3 vs. arm 2, win share | **5.0%** | **1.5%** |
| range | [−0.0193, −0.0159] | [−0.0222, −0.0195] |
| company-removal floor | 2.2% | (not computed; win share extreme enough) |

Arm 2 beats arm 3 in essentially every book, on both book sets, with a range
nowhere near zero. **This is not a contradiction of the per-trim finding —
it is a different question answered by the same mechanics.** The per-trim
run measured value *per flagged call*, holding size fixed. Severity-sizing
there means trimming the two worst fifths *harder* than a flat rule would.
At the book level, arm 3's rule also trims the *mild* three-fifths of
flagged calls **not at all** (band size 0), where arm 2 trims every one of
them at 2.5%. Since QQQ's own return per unit of drawdown over this window
(arm 1: 0.3558) is more than double the book's (arm 0: 0.1392), **moving
more of the portfolio into QQQ — regardless of which name funded it — raises
return per drawdown almost mechanically.** Arm 2 moves more money into QQQ
than arm 3 does (it trims every flag, not two-fifths of them), so it wins on
this metric more often. Severity-sizing is *selective* about which names to
leave alone; on this ruler, in this window, being selective costs more than
it earns. State this plainly: **the per-call severity edge and the
book-level return/drawdown ruler are not the same test**, and this run does
not tell you the per-trim edge is wrong — it tells you return-per-drawdown,
on a book that also holds 15 un-trimmed names in a strong index period,
rewards moving money to the index more than it rewards trimming selectively.

## Stratified books (n = 200): a different verdict on 1b

| test | win share | range | floor | passes 70% rule |
|---|---|---|---|---|
| 1a. arm 3 vs. arm 0 | 100.0% | [0.0875, 0.0961] | 100.0% | yes |
| 1b. arm 3 vs. arm 3R | **85.5%** | [0.0176, 0.0283] | **72.0% (LLY)** | **yes** |
| arm 2 vs. arm 0 | 100.0% | [0.1083, 0.1166] | 100.0% | yes |
| arm 2 vs. arm 2R | 99.0% | [0.0420, 0.0562] | 97.8% | yes |
| arm 3 vs. arm 2 | 1.5% | [−0.0222, −0.0195] | — | no |

**On stratified books, both 1a and 1b pass — the headline would read
"severity-sized trims add value" on this set alone.** The two book sets
disagree on the skill question (1b), even though they agree on the reversal
(arm 2 still dominates arm 3). Stratified books force 4 speculative names
into every book (from a pool of only 7), which raises the share of
high-volatility, heavily-flagged names in every draw; random books can and
often do miss the speculative sleeve entirely. **State this plainly per the
prompt's own rule (R3): 400 books drawn from 55 companies overlap heavily,
and this book test's own random-vs-stratified split shows the practical
consequence** — the skill reading depends on which 55-company pool the
books are drawn from, not just on the rule being tested. The pre-registered
reading gates on the random-book result; the stratified result is reported
separately, as specified, and points the other way.

## Arm 3 sizing diagnostics (Amendment 1a item 2)

- **Full-sell share:** median across books, random 16.1%, stratified 13.7%
  — about one trim in seven or eight sells the whole remaining position
  rather than the intended 2.5 or 5 points.
- **Median position size at flag time:** the pooled median across *every*
  arm-3 trim event, random books, is **0.0%** — not a rounding artifact.
  **Diagnostic, investigated further:** of 23,472 arm-3 trim events across
  all 200 random books and 3 phases, **12,814 (55%) land on a position
  already fully sold to zero** by an earlier flag on the same name — B
  re-flags names it has already exited, and those later "trims" move
  nothing. Restricting to the 10,658 events that actually moved money, the
  median position size at flag time is **3.48%** of the book (10th–90th
  percentile 0.79%–7.06%), a sensible number for a 6.25%-start position that
  has drifted. **This means arm 3's real, money-moving trim rate is roughly
  half its raw trim count**, and it is a genuine property of running B's
  flag rule repeatedly on the same names over six years, not a simulation
  defect. It was not anticipated in the prompt and is reported here as
  found.

## TRAIN6 (reported only) and its leave-one-out

MSFT, AMPX, EOSE, QS, RUN, TTD at equal weight (1/6 each). This is a
concentrated, highly volatile speculative book — arm 0's daily drawdown is
**77.0%**, more than any random or stratified book's median.

| arm | final value | CAGR | daily DD | return/DD |
|---|---|---|---|---|
| 0 | $134,889 | 4.74% | 76.98% | 0.0615 |
| 1 (QQQ) | $216,073 | 12.67% | 35.62% | 0.3558 |
| 2 | $200,011 | 11.32% | 72.32% | 0.1565 |
| 3 | $199,247 | 11.27% | 71.76% | 0.1576 |
| 3F | $213,735 | 12.48% | 71.04% | 0.1763 |
| 3S | $192,317 | 10.66% | 70.69% | 0.1514 |
| 2R | $178,845 | 9.42% | 74.38% | 0.1269 |
| 3R | $187,381 | 10.08% | 73.40% | 0.1366 |

**6-way leave-one-out, arm 3 return/DD vs. arm 0 return/DD (dropping one
name, 5-name book at 1/5 weight):**

| dropped | arm 3 | arm 0 |
|---|---|---|
| MSFT | 0.1230 | 0.0133 |
| AMPX | 0.1680 | 0.0923 |
| EOSE | 0.1291 | 0.0991 |
| QS | 0.2182 | 0.1008 |
| RUN | 0.1680 | 0.0716 |
| TTD | 0.1002 | −0.0167 |

Arm 3 beats arm 0 in all six cuts — a consistent direction, unlike the
ALL16 result that flipped on FSLR alone (R1's precedent for adding the
company-removal check). As the review noted, a six-name equal-weight book
is an odd object; this is reported, not leaned on. TRAIN6's own arm 3 vs.
arm 2 (not tabulated per-cut) follows the same reversal as the two main
book sets — arm 2's fixed trim slightly outperforms arm 3 here too (return/DD
0.1565 vs. 0.1576 is the one near-exception in this run, and it is TRAIN6
only, n=1).

## Arm 3S (proceeds to SPY, reported only)

Random books: 93.0% win share vs. arm 0 (floor 89.8%, FRC), median gain
0.0455 [0.0400, 0.0554] — passes 1a's bar on its own, at a lower level than
arm 3's QQQ destination (96.0%), consistent with QQQ's own edge over SPY in
this window (`per-trim-value-qqq-out.md`'s diagnostic on the same point).

## Band 5 lead ($0, reported only, Amendment 1a item 4)

From the per-trim data (`per-trim-value-qqq/results.json` inputs), the
mildest P9 fifth of flagged calls, pooled:

| destination | n | median value/point | mean value/point | range |
|---|---|---|---|---|
| QQQ | 74 | **+0.0211** | **−0.2381** | [−0.5918, 0.0543] |
| SPY | 74 | **−0.0579** | **−0.2775** | [−0.6271, 0.0118] |

Top-3 contributors to the (negative) mean, both destinations: **EOSE**
(−11.47 QQQ / −11.68 SPY), **AMPX** (−3.91 / −3.98), **OXY** (−3.10 / −3.23)
— summed value in points, most-negative first (i.e., the biggest cost
trimming these names would have carried). The median sits just above zero
on QQQ and just below on SPY — both close to flat — while the mean is
solidly negative on both, made by these three names among 74. This matches
the review's expectation exactly: **the mean is made by a few names.** No
reading. It earns a line in the live forward test (score B and P9 live,
grade the mild-P9-flagged cases), not a train candidate or a tune look.

## Arm M — not run

`sweep_cadence_and_session_model.load_events_dedup_on()` — the loader for
the settled production CELL (`swap_funding`, K=30, `new_calls_only`, X=2.5,
`pooled`, `per_event_date`) — calls `simulator.data.load_call_events` (a DB
query against the Analysis/Transcript tables) and `fetch_extra_fields(ALL16, C)`
(also DB), and both are hardcoded to the 16-name ALL16 universe, not
parameterized for an arbitrary train-company book. The file-based path that
exists for train companies (`data_from_cache.load_events_from_cache` +
`attach_trend_verdicts`, confirmed present: `analysis/data/evals/v6_claude-sonnet-4-6`
has 1,240 files covering 56 tickers) feeds a **different**, simpler engine
(`simulator.simulator.run_simulation`), not the swap-funding session-sweep
engine the settled CELL actually names. Making arm M run on these books
would mean rewriting the DB-and-ALL16-specific loader for 55 train
companies without a DB path — the workaround the prompt explicitly forbids
building. **Arm M not run; reading 4 ("the matrix costs money") deferred.**

## Deviations from the prompt

1. **Gate metric formula copied, not imported**, from `analysis/e2e_scorer.py`:
   that file computes `cagr / max_dd if max_dd > 0.001 else 999.0` inline
   inside its `run_gate` function, not as a standalone importable function.
   Reproduced verbatim as `return_per_dd()` in the new driver, cited at the
   top of the file.
2. **Price marking uses a purpose-built fast path**, not
   `simulator.data.PriceLookup` directly: a pandas-built, forward-filled
   (`ffill(limit=7)`, the same lookback semantics as `PriceLookup.price_on`)
   daily array per ticker, for O(1) lookups. `maxdd` and `daily_nav_path`
   themselves are imported and called unchanged, fed `Snap` objects and this
   fast price object (which satisfies the same `price_on(ticker, date)`
   interface `daily_nav_path` expects). This was a performance necessity —
   ~9,800 book/arm/phase simulations × ~2,358 daily marks — not a pricing-rule
   change; the full run completed in 33 seconds.
3. **"Newer call acts before the second half" resolved as a strict
   session-index comparison** (`new_idx < pending_second_idx`): if a new
   call's action session lands *at or after* the scheduled second-half
   session, the pending second half is treated as already executed (its own
   entry) before the new call's rule is applied; only a strictly earlier
   new action cancels it. This is the more literal reading of "before" and
   is stated here since the prompt did not give a same-session tie-break.
4. **The no-skill control (2R/3R) draws its replacement ticker once per
   trim group** (both steps of a 5-point group replaced by the same
   ticker), using the group's own first session to determine eligibility
   (held, same calendar quarter) via a book-and-arm-seeded RNG
   (`random.Random((11, book_id, arm, phase))`, deterministic and
   reproducible). Eligible candidates are drawn from *calls*, not deduped
   tickers, so a ticker with more calls in that quarter is proportionally
   more likely to be picked — the more literal reading of "a call picked at
   random."
5. **Arm 1 (QQQ alone) was initially left unsimulated** (declared in the
   arm list but never run, giving NaN metrics on the first full pass) —
   caught before this report was written, fixed, and the full run repeated.
   Noted here per Step 7's re-verification discipline.

## What deliberately was not done

- Arm M (see above — a design-session call, not a workaround).
- Any change to production code, the version registry, or any gate.
- Any re-derivation of the closed decisions in
  `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` or the per-trim wrap-ups.

## What it means

- **1a passes, 1b fails on random books → "own more QQQ."** The trims beat
  leaving the book alone, but the company-removal and win-share legs of the
  skill test (arm 3 vs. arm 3R) do not clear 70% on the book pool this
  project actually draws from. This is a real result, but it names a
  different allocator than "trim what B flags and P9 rates severe": it
  names "trim something every quarter, send it to QQQ." That goes to the
  sleeve/index decision, not to P6D.
- **Units do not matter** (arm 3F within 0.5 points of arm 3 on both book
  sets) — if a rebuild proceeds on this rule, book-points and position-
  fraction sizing are interchangeable; pick whichever is simpler to run
  live.
- **The stratified read disagrees with the random read on 1b specifically**
  (passes there, fails on random) — a live, unresolved tension the design
  session needs to weigh: it depends on how much of the real sleeve looks
  like the stratified pool (4 speculative names guaranteed) versus a random
  draw.
- **Severity-sizing loses to plain trimming at the book level, on both book
  sets, decisively** — this is the sharpest finding in the run and cuts
  against the per-trim lead that motivated arm 3 as the candidate. It does
  not mean P9's per-call severity signal is wrong; it means that on this
  ruler, being selective about which flagged names to leave alone costs
  more than it earns, because the un-trimmed money stays in single names
  while QQQ was running hot.
- **Arm M deferred** — production's own cost, or lack of it, on these books
  remains unmeasured. Nothing here says anything about the matrix.

## Follow-up commands

Reproduce this run (freeze already committed; recomputes and overwrites
`results.json`'s arm sections in place):

```
python3 analysis/allocator_book_test.py run
```

Recompute only the band 5 lead:

```
python3 -c "import sys; sys.path.insert(0,'analysis'); import allocator_book_test as M; import json; print(json.dumps(M.band5_lead(), indent=1))"
```

## Git

- Prompt already committed at `17b1125` (prior session, before this run
  started).
- Driver committed at `ad89360`, before any output.
- t1/t2 frozen and committed at `e105aba`, before any arm ran.
- Bug fix (missing arm 1 simulation) at `fb522bf`; band-5 contributor sort
  fix at `8cb7040` — both before the results committed at `9de97b5`
  reflected them.
- This wrap-up committed next, then `git push` of `sweep/db-corpus-baseline`
  — pushed hash reported in chat.
