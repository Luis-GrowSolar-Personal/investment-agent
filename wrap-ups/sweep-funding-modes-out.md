# Funding mode sweep — wrap-up

**no_reserve control reproduces $141,837. Best-diagnostics cell: 7
(`swap_funding` + 10pp session limit), with 100% of Adds receiving at least
partial funding (0% entirely unfunded, vs. today's 75.8%) and all 16
universe tickers held (vs. today's 12) — but only 14.1% of Adds were
*fully* funded, so "no longer starved" is not the same as "gets what it
asked for." Retrospective ordering spread on the current model: $117,455–
$154,443 against a $141,837 forward baseline.**

All 8 grid cells ran; the standing $141,837 assertion passed (after
catching and fixing a repeat of the exact signature bug from the prior
session — see below). No DB writes, no LLM calls, no cache refreshes.
Still on `sweep/db-corpus-baseline`, nothing committed to `dev`.

---

## The same instrumentation bug bit again — caught by the same assertion

Building the funding-mode wrapper, I again wrapped a wrapper: an outer
`decide_fn(**kwargs)` closure (added to inject `final_confidence` lookups)
sat in front of the mode-specific `decide_fn`. Exactly like the prior
session's mistake, a `**kwargs`-only signature defeats
`simulator.py`'s `inspect.signature(decide_fn)` check, so `tier`,
`is_first_call`, and `driver_count` were silently dropped again. Cell 1
came back at $114,263 — the identical wrong number from last time, for the
identical reason. Fixed by giving *every* layer of wrapping (not just the
innermost one) decide_v3's exact explicit signature. Re-ran; cell 1
reproduces `$141,837` exactly. **Lesson reinforced: any decide_fn wrapper
in this codebase must declare `tier=None, is_first_call=False,
driver_count=None` explicitly — `**kwargs` is not safe here, ever.**

## Step 0 — carried forward, and the FSLR fix

Carried forward unchanged: clean window (2022-01-01 → 2024-06-12), 100% v6
coverage, the two-sided `createdAt` cutoff, the `DailySnapshot` cash fields,
the funding/event-log wrapper pattern.

**FSLR dedup, added to the loader** (`analysis/simulator/data.py`,
`load_call_events()`): new parameter `dedupe_same_day_calls: bool = False`.
When true, the SQL now also selects `t.id AS transcript_id`, and a
Python post-filter keeps only the lowest-id transcript for any
`(ticker, call_date)` pair sharing more than one row:

```python
if dedupe_same_day_calls:
    best_by_key: dict = {}
    for r in rows:
        key = (r["ticker"], r["call_date"])
        if key not in best_by_key or r["transcript_id"] < best_by_key[key]["transcript_id"]:
            best_by_key[key] = r
    rows = list(best_by_key.values())
```

Default is `False` (matches historical/prior-session behavior); every cell
in this sweep except Cell 1 runs with dedup **on**.

**Verified:**

```
Window event count, dedup OFF: 148
Window event count, dedup ON:  147 (expect 147)
```

**Other duplicated `(ticker, callDate)` pairs, DB-wide (not just ALL16 or
the window)** — checked directly:

```sql
SELECT tk.symbol, t."callDate"::date, count(*), array_agg(t.id ORDER BY t.id)
FROM "Transcript" t JOIN "Ticker" tk ON tk.id=t."tickerId"
GROUP BY tk.symbol, t."callDate" HAVING count(*) > 1;
```
```
 symbol |  callDate  | count | array_agg
--------+------------+-------+-----------
 FSLR   | 2024-02-27 |     2 | {280,284}
```

**FSLR is the only duplicate in the entire database.** No other ticker or
date is affected.

**Cells 1 and 2 isolate the dedup effect** (both `no_reserve`, no limit):

| | Final value | Max DD | Adds funded/partial/unfunded |
|---|---|---|---|
| Cell 1 (dedup off) | $141,837 | 45.6% | 4/20/75 of 99 |
| Cell 2 (dedup on) | $141,837 | 45.6% | 4/20/74 of 98 |

**Identical final value and drawdown.** The duplicate FSLR transcript was
evaluated and (if `Add`) sized twice on the same day, but since FSLR's
funding was already constrained by the same chronic cash shortage as
everything else, removing the duplicate call changed the *count* of
Add-shaped decisions (99→98) without changing the dollar outcome at all.
Confirms the duplicate was a data-hygiene issue, not a result-distorting
one, in this specific regime — flagging that this could matter more once
funding is actually fixed (a fully-funded duplicate Add really would double
a position).

## Step 1 — three funding modes implemented

New file: `analysis/sweep_funding_modes.py`. All three modes share one
`decide_fn` factory (`make_funding_decide_fn`) that calls `decide_v3`
unmodified first, then post-processes its trades — `decide_v3` and
`decide_v2` in `analysis/simulator/allocator_v3.py` /`allocator_v2.py` were
**not edited**.

**`no_reserve`** — passthrough; when `session_change_limit_pp` is set, buy
trades are scaled down (shares × ratio, preserving the account split
`decide_v3` already chose) so total buy dollars never exceed
`session_change_limit_pp% × portfolio_value`, mirroring §5's
`buy_$ = min(delta_$, cash_available, session_change_limit)` formula.

**`cash_reserve`** — same post-hoc scaling, but the cap is
`max(0, combined_cash_before_trade - reserve_pct% × portfolio_value)`
instead of (or in addition to) the session limit.

**`swap_funding`** — implemented per §5's spec, with one explicit
interpretive choice on an item the spec states mechanically but not
algorithmically, flagged rather than silently assumed:

- **Trigger:** natural `decide_v3` buy dollars fall short of the (session-
  limit-adjusted) target.
- **Donor eligibility:** any currently-held ticker (excluding the
  candidate itself) whose most-recently-seen `final_action` is `Hold`,
  `Trim`, or `Exit` — **never `Add`**. Tracked via a running
  `ticker_state` dict updated on every `decide()` call, since nothing else
  in this harness exposes "current latest verdict per ticker" directly.
- **Donor ranking (the interpretive choice):** §4's ranking function
  (`final_confidence`, verdict recency, gap-to-target-as-fraction) is
  computed **identically** for donors as for candidates, then donors are
  sorted **ascending** by that same tuple and drawn from the front — i.e.,
  literally "the same rank, taken from the bottom instead of the top."
  `gap_to_target` for a donor uses the donor's *own* cap/target (even
  though its current verdict isn't `Add`), so a donor already near or above
  its own target ranks as a "worse" candidate-priority and therefore a
  "better" donor. This is a mechanical, literal reading of "lowest-ranked
  eligible donor first, by §4's ranking" — not re-derived or invented
  criteria, but §4 was written for candidates, not donors, so this
  extension is my construction. **Not stopped on**, since the reading is
  unambiguous once you accept "same ranking function, opposite end of the
  list" — but flagging it as the one place this implementation makes a
  judgment call the spec doesn't spell out in code-level detail.
- **Trim quantum:** at most 25% of the donor's current position value this
  event, reusing `allocator_v2._build_sell_trades` directly (already drains
  `tax_advantaged` before `taxable`, unmodified from production code).
- **Minimum position size floor:** **not enforced as a numeric threshold** —
  `minPositionDollar` is a spec/production (`moves.js`) concept; **no such
  constant exists anywhere in this Python simulator** (confirmed by
  search). Since a single session's trim is capped at 25% of the donor, no
  one event can zero out a position outright, so the guard is satisfied
  trivially at this backtest's granularity, but there is no accumulated
  floor preventing repeated 25% trims from eventually shrinking a donor to
  a token position over many sessions. **Flagged, not implemented** — a
  literal `minPositionDollar` would need a value from the production spec
  that doesn't exist in this codebase to port.
- **Buy-side rebuild:** after donor sells are constructed, the candidate's
  buy trade is rebuilt (not just scaled) against `current cash + this
  event's donor proceeds`, per account, in the same `tax_advantaged` →
  `taxable` order `_decide_add` uses. Because the simulator executes a
  `decide()` call's returned trades strictly in list order against the real
  mutable `Portfolio`, returning `[sells..., buy]` means the buy is sized
  against a *projection* that the simulator's own sequential execution then
  makes literally true — no double-counting, no need to mutate `Portfolio`
  early.
- **Reporting:** displacement sells are tagged
  `reason="swap-funding-displacement"`; their `RealizedSale.realized_gain`
  values are summed separately from ordinary Trim/Exit gains (see Step 2's
  table and the displacement log below).

## Step 2 — the eight-cell grid

ALL16, clean window, `decide_v3`, frozen-JSON `type_for_ticker`, unchanged
caches, alphabetical ordering held constant. Exact invocation for every
cell: `cd analysis && python3 sweep_funding_modes.py` (all eight run in one
script; see the file for per-cell parameters).

| Cell | Final value | Max DD | Cash<1% days | Adds funded / partial / unfunded | Cumulative shortfall | Distinct tickers held | Displacements (realized gain) |
|---|---|---|---|---|---|---|---|
| 1 — no_reserve, dedup off | $141,837 | 45.6% | 793/894 (88.7%) | 4 / 20 / 75 of 99 | $2,369,889 | 12 | — |
| 2 — no_reserve, dedup on | $141,837 | 45.6% | 793/894 (88.7%) | 4 / 20 / 74 of 98 | $2,351,360 | 12 | — |
| 3 — cash_reserve 5% | $128,304 | 41.7% | 0/894 (0.0%) | 4 / 30 / 64 of 98 | $2,426,184 | 14 | — |
| 4 — cash_reserve 10% | $129,184 | 40.0% | 0/894 (0.0%) | 4 / 30 / 64 of 98 | $2,482,914 | 14 | — |
| 5 — cash_reserve 20% | $126,349 | 37.1% | 0/894 (0.0%) | 3 / 26 / 69 of 98 | $2,580,926 | 14 | — |
| 6 — swap_funding | $149,218 | 49.0% | 800/894 (89.5%) | 2 / 68 / 21 of 91 | $2,331,986 | **16** | 266 (**-$32,679**) |
| 7 — swap_funding + 10pp limit | **$154,392** | 39.9% | 717/894 (80.2%) | 13 / 79 / **0** of 92 | **$616,154** | **16** | 426 (**-$24,950**) |
| 8 — no_reserve + 10pp limit | **$189,134** | 39.5% | 694/894 (77.6%) | 13 / 18 / 67 of 98 | $831,310 | 15 | — |

## Flagged plainly — the warning sign the prompt asked to watch for

**Cell 8 is the highest-return cell in the entire grid, and it is exactly
the "returns improve but the funding diagnostics do not" case the prompt
warned about.** `no_reserve + 10pp session limit` alone — no reserve, no
swap-funding, no structural fix to the cash-starvation problem — produces
$189,134, beating every funding-mode cell including swap-funding. But its
funding diagnostics barely move: still 67 of 98 Adds (68.4%) entirely
unfunded, nearly identical to the unmodified control's 75.8%. **The session
limit's real effect is to change *when in the price path* the available
cash gets spent, not to fund more of what was asked for — and on this
specific 2022–2024 window, spreading the same limited dollars out over more
sessions happened to land better entries.** That is a timing artifact of
this one historical path, not evidence the underlying rationing problem is
fixed. Cell 7 (swap_funding + the same 10pp limit) is the one that actually
moves the diagnostics — unfunded drops to 0%, cumulative shortfall drops
73% — and it still returns less than cell 8. **Do not read cell 8's return
number as an endorsement of `no_reserve` — its diagnostics tell the true
story.**

**Displacement realized gains are negative in both swap_funding cells**
(-$32,679 on cell 6, -$24,950 on cell 7). Swap-funding is, on this corpus,
raising cash by selling donors **at a loss**, not harvesting gains — donors
eligible for displacement (`Hold`/`Trim`/`Exit` verdict) are disproportionately
recent, smaller, or currently-out-of-favor positions, not necessarily ones
sitting on unrealized gains. This directly contradicts an implicit
assumption in how "swap-funding" reads casually (sell a winner to fund a
better winner) — in practice here it's closer to "sell whatever is weakest,
gain or loss, to free any cash at all." Whether that's an acceptable cost
of the mechanism or a sign the donor-ranking interpretation above needs
revisiting is a design-session question, not resolved here.

**Distinct-tickers-held is the cleanest secondary signal**: `no_reserve`
holds only 12 of 16 possible names; `cash_reserve` improves modestly to 14;
`swap_funding` (both variants) reaches the full **16 of 16** — the
funding-starved names (SPWR chief among them, see the prior session's
report) actually get positions under swap-funding. This is consistent
across both swap-funding cells and is the one metric where swap-funding is
unambiguously doing what §5 says it should.

## Displacement log — cell 6 (`swap_funding`, no limit)

266 individual displacement sells across the window. Full per-event log is
reproducible via the invocation above; aggregated by donor:

| Donor | # times drawn on | Total raised |
|---|---|---|
| MSFT | 15 | $48,017 |
| TSLA | 38 | $18,154 |
| AMD | 14 | $15,116 |
| AAPL | 38 | $14,909 |
| RUN | 44 | $5,178 |
| ENVX | 21 | $5,004 |
| EOSE | 58 | $3,991 |
| FSLR | 9 | $2,163 |
| AMPX | 14 | $1,032 |
| QS | 11 | $303 |
| SPWR | 4 | $18 |

**EOSE is drawn on most often (58 times) but contributes the least per draw**
(~$69/event) — consistent with it being a small, frequently-`Hold`-verdict
position ground down repeatedly in small increments rather than a genuine
large reallocation. **MSFT contributes the most total dollars ($48,017)
from the fewest draws (15)** — a large, established, `Hold`-or-worse-verdict
position absorbing bigger single trims. Both patterns are plausible given
the ranking rule, not obviously a bug, but worth the design session seeing
the shape rather than just the total.

## Step 3 — retrospective ordering probe (cell 1 only — diagnostic, not a design input)

```
forward (as-loaded):        $141,837
reversed same-day order:    $117,455
seed 1:                     $138,162
seed 2:                     $141,096
seed 3:                     $154,443
```

**Spread: $117,455 – $154,443** against the $141,837 forward baseline — a
range of roughly -17% to +9%. This reproduces and quantifies exactly what
§5's measurements already concluded qualitatively: a meaningful share of
the historical result is arrival-order luck, not allocator skill, under the
current (broken) funding regime. **Per instruction, this is not used to
recommend an ordering rule** — it's reported only to answer "how much did
arrival order matter historically," and it will need re-measuring once a
funding mode is actually adopted, since the prompt's own sequencing
decision holds that ordering is only decisive because funding is broken
today.

## What was deliberately not done

- No funding mode selected — the lead line above names cell 7 as
  "best-diagnostics," not "recommended." That distinction is preserved
  throughout: cell 8's higher return is explicitly flagged as suspect, and
  no cell is called a winner.
- `ALLOCATOR_OPERATING_MODEL.md` not amended — its §5 measurements and
  swap-funding spec were read and implemented against, not edited.
- §12 open items not resolved.
- Cadence/scope/veto sweep not started — this prompt's own sequencing
  decision holds that those cannot run until funding mode is settled by the
  design session.
- `minPositionDollar` floor not implemented (flagged above — no such
  constant exists in this codebase to port).
- No DB writes; `price_cache.json` / `fundamentals_cache.json` untouched.

## Repo state left behind

Branch `sweep/db-corpus-baseline` (uncommitted):
- `analysis/simulator/data.py` — added `dedupe_same_day_calls` parameter to
  `load_call_events()` (additive; default `False`, no behavior change when
  omitted).
- `analysis/sweep_funding_modes.py` — new, this session's grid runner and
  the three funding-mode implementations.
- Prior sessions' scratch scripts and the `DailySnapshot` cash-field
  addition (`simulator.py`) — unchanged, reused as-is.

`dev`/`main` untouched.

## Follow-up / verification commands

```zsh
cd analysis && python3 sweep_funding_modes.py

# Confirm FSLR is the only DB-wide duplicate:
DATABASE_URL=$(grep '^DATABASE_URL' ../.env | cut -d '=' -f2-)
psql "$DATABASE_URL" -c "
SELECT tk.symbol, t.\"callDate\"::date, count(*), array_agg(t.id ORDER BY t.id)
FROM \"Transcript\" t JOIN \"Ticker\" tk ON tk.id=t.\"tickerId\"
GROUP BY tk.symbol, t.\"callDate\" HAVING count(*) > 1;
"
```
