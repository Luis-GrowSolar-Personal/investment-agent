# resolve-open-four — wrap-up

Run completed in full: Step -1 through Step 4 all done, this session, in one pass.
No partial run. `run_id`: `resolve-open-four`. State in
`analysis/data/run_state/resolve-open-four/` (`progress.json`, `cells.jsonl` —
36 lines/cells, `findings.md`). Nothing was resumed from a prior interrupted
run — this is the first execution of this `run_id`.

> **Ruler: published 17.32% is session-sampled; daily-marked is 23.46%.
> Advantage over SPY 1.90pp (daily-vs-daily, like-for-like), was 8.04pp
> (daily-SPY vs session-portfolio, mismatched ruler). §5.2 #2 IS a sampling
> artifact. SPWR: funding failure in a fully-invested portfolio, not a
> decision; §5.1 should read "SPWR was never held because its one starter
> leg queued on 2024-05-20 and failed funding (binding: cash available) in a
> portfolio that was fully deployed — a mechanical absence, not a rejection."
> Seed: does NOT bind because — unresolved; 8 of 27 sessions have BOTH a
> rank_key tie and a genuine cash-scarce partial fill, which refutes the
> tie/partial-fill-disjointness hypothesis as literally stated, yet the 15
> tie-break seeds still give one bit-identical final value; root mechanism
> not traced further within budget. 1 published range (the 15-draw tie-break
> sweep) is a single point. Gate scope: ledger 5.17pp (n=58) vs the four
> names carrying the portfolio -3.57pp (n=56). sonnet-4-6: undetermined at
> paired n=0. X-axis on the daily ruler: raw-final optimum sits at X=3.0pp
> (189,425), narrowly ahead of X=2.5pp (184,819, 97.6% of the X=3.0 value) —
> the same 2.5–3pp interior-optimum band already described in state-of-play
> §0.1, and daily-ruler drawdown understatement is a fairly uniform 2.8–8.0pp
> across every capped X (no reordering), so the settled configuration
> STANDS.**

---

## Step 0 — driver review and commit

`analysis/resolve_open_four.py` was untracked, written blind. Reviewed
line-by-line against the code it claims to read:
`sweep_cadence_and_session_model.py` (`run_session_sweep_cell` signature,
`rank_key`, `load_events_dedup_on`, `ALL16`, `funding_log`/`target_cap_log`
append sites), `simulator/data.py` (`CallEvent`, `PriceLookup.price_on`),
`simulator/accounts.py` (`Trade`, `transaction_log`), `simulator/simulator.py`
(`DailySnapshot.position_values`/`cash_total`), `analyst_direct_scorer.py`
(`PriceCache`, `PRICE_CACHE_PATH`), `analyst_sensitivity_lift.py`
(`lift_for_events`).

**Finding: the signature bug the prompt warned about is already fixed** in the
file as found — `cadence` is passed as the string `"30"`, kwargs are
`funding_mode` and `execution_order`, exactly matching
`run_session_sweep_cell`'s real signature (`sweep_cadence_and_session_model.py:356-361`).
Every other kwarg, dict key and dataclass field the driver reads matches the
real code. Ran all five checks (A/B/C/E/D) end to end and every first-pass
figure quoted in `prompts/resolve-open-four.md` reproduced exactly, including
the 15-decimal `179944.906085` tie-break final and the `+5.17pp`/`n=58` gate
scope figure. No functional change was needed.

Committed as its own commit before any manifest:
**`fb9ec8f`** — `analysis: commit resolve_open_four.py driver (reviewed, runs clean)`.

A second driver, `analysis/resolve_open_four_manifest.py`, was written to put
Steps 1a, 1c, 2 and 4 under a manifest (the original driver prints to stdout
only, with no `git_commit`/`git_dirty`/checksum record). Committed
**`04125e1`**; a dirty-check bug found immediately after (it flagged the
prompt file and this run's own `run_state/` as dirty) was fixed and
recommitted as **`9c2e159`** before any manifest was written against it. All
four manifests below cite `git_commit: 9c2e15970738c9d484d0cfc1370b40de938c2bda`,
`git_dirty: false`, `driver_file_tracked_at_commit: true` — asserted, not
assumed.

**Verification performed**: `python3 -c "import ast; ast.parse(...)"` on both
driver files before every commit; each driver executed and its stdout
inspected against the prompt's first-pass figures before commit.

---

## Step 1a — drawdown ruler

Manifest: `analysis/data/run_state/resolve-open-four/manifests/1a-manifest.json`.

**Assumption check**: the reconstruction assumes every `transaction_log` entry
falls on a session date. **2 of the entries do not** — `2023-12-31` and
`2024-12-31` (`1a-manifest.json` → `results.off_session_txn_dates`). Both are
year-end tax-lot settlement trades (the code has a dedicated December-31
partial-year-settlement path, separate from the session-driven Add/Trim/Exit
logic) — a known, distinct mechanism, not a violation of the reconstruction's
core assumption for session-driven trades. The daily-NAV reconstruction is
unaffected: these two dates are fixed and known, so share counts remain
recoverable across them.

| phase | final | dd session | dd daily | understated by |
|---|---|---|---|---|
| 0 | $179,945 | 20.85% | 22.78% | 1.93pp |
| 10 | $189,914 | 15.96% | 24.20% | 8.25pp |
| 20 | $184,599 | 15.16% | 23.39% | 8.23pp |
| **phase-avg** | **$184,819** | **17.32%** | **23.46%** | **6.13pp** |

Source for every cell: `1a-manifest.json` → `results.per_phase` /
`results.phase_avg_dd_session` / `results.phase_avg_dd_daily`. All figures are
**forward draws at seed 0**, phase-averaged where marked. Reproduces the
prompt's first-pass table exactly (published phase-avg drawdown 6.14pp vs.
6.13pp here — a rounding artifact of averaging three already-rounded
percentages, not a discrepancy).

**Benchmarks** (buy-and-hold from 2022-01-01, `1a-manifest.json` →
`results.benchmarks`):

| ticker | daily dd | session dd (ph-avg) |
|---|---|---|
| SPY | 25.36% | 21.13% |
| QQQ | 35.25% | 29.45% |
| TMFC | 32.99% | 27.57% |

The published §2 figures (SPY 25.36%, QQQ 35.25%, TMFC 32.99%) match the
**daily** column exactly; the published portfolio figure (17.32%) matches the
**session** column exactly. **The published §2 comparison is not like-for-like
— confirmed.**

**Restated §2 comparison, both sides on the daily ruler:**

| comparison | value |
|---|---|
| Published advantage (mismatched ruler: SPY daily − portfolio session) | 25.36 − 17.32 = **8.04pp** |
| Like-for-like, daily ruler (SPY daily − portfolio daily) | 25.36 − 23.46 = **1.90pp** |
| Like-for-like, session ruler (SPY session-avg − portfolio session) | 21.13 − 17.32 = **3.80pp** |

The portfolio's drawdown advantage over SPY shrinks from a nominal 8.04pp to
1.90pp once both sides are marked daily — most of the published advantage was
an artifact of comparing a coarsely-sampled portfolio curve against a
continuously-marked benchmark curve, not a real risk-management edge.

**Phase spread** (`1a-manifest.json` → `results.phase_spread_session` /
`phase_spread_daily`): session 15.16–20.85% (spread **5.69pp**), daily
22.78–24.20% (spread **1.42pp**) — reproduces first pass exactly.
**State-of-play §5.2 anomaly #2 closes as a sampling artifact**, not a fact
about trade timing: the large apparent phase-sensitivity of drawdown almost
entirely disappears once drawdown is measured on a continuous ruler.

The reconstruction starts at the first session date, so phases 10/20 omit
their leading all-cash days at $100k. This cannot lower measured drawdown
(it can only raise the running peak marginally, per the prompt's own
reasoning) — not independently re-tested, no reason found to doubt it.

**EW is unmeasured on both rulers** — `analysis/baseline.py` computes SPY/QQQ/
TMFC only; the published EW drawdown figure was not reproduced or checked
here and should not be quoted as measured by this run.

---

## Step 1b — SPWR

Reproduced verbatim from `resolve_open_four.py` check B (stdout, this session):
SPWR has exactly **one** scored event, `2024-05-02`, `per_call_rec='Trim'`,
`final_action='Trim'`, `confidence='unknown'`, `size=3.0`. Its one starter leg
did queue at the 2024-05-20 session (`target_cap_log`: `leg='starter'`,
`target_pct=5.0`, `cap_pct=15.0`). `funding_log` for that leg:
`intended_dollars=8062.74`, `target_buy_dollars=4031.37` (halved by the
X=2.5pp session limit), `actual_dollars=0`, **`binding='cash available'`**.
Zero SPWR trades execute in the settled cell; 15 tickers ever traded, 15 held
at end.

**Confirmed: this is a funding failure in a fully-invested portfolio, not an
analyst decision.**

**Replacement sentence for state-of-play §5.1** (not applied to the doc — for
the design session):

> The claim *"the only genuine rejection is SPWR — never held, in any draw, at
> any point"* does not survive: SPWR's one Trim event in the corpus queued a
> 5% starter leg at the 2024-05-20 session, and that leg failed to fund
> (`funding_log`: `binding='cash available'`, `actual_dollars=0` against an
> `intended_dollars` of $8,062.74) because the portfolio was fully deployed at
> that point, not because the analyst declined it. SPWR is a mechanical
> absence, not a rejection — the table's most encouraging framing loses its
> footing.

**Cost of the exclusion**: SPWR traded $1.17 → $1.48 between 2024-05-20 and
window-end 2024-06-12, **+26.5%**. A funded 5%-of-portfolio starter at that
session (~$4,031 intended-halved amount, or ~$8,063 uncapped) would have
gained roughly **$1,069** (uncapped-intended basis) inside the window — this
run did not re-verify the dollar figure independently of the prompt's stated
arithmetic; it follows directly from the funding_log dollar amounts and the
price move, both confirmed above. The August 2024 SPWR bankruptcy sits
outside the window (ends 2024-06-12) and is invisible to this backtest either
way.

**Zero-information arm's 16th ticker**: not independently re-derived under a
manifest this run (out of the four manifested driver's scope; would need a
separate zero-information-arm cell). The mechanism the prompt proposes —
under zero information the analyst never issues an Add, so less cash is
deployed and SPWR's starter can fund — is consistent with the funding_log
evidence above (SPWR's starter fails specifically because of cash scarcity,
which is exactly what a zero-information arm would relax) but was not run to
confirm directly. **Flagged as not independently verified this run** — the
sensitivity wrap-up's original 15/16 explanation is confirmed not to survive
1b (SPWR is not "the only rejection"), but the positive claim about *why* the
zero-info arm has 16 should be treated as a strong hypothesis, not a
reproduced fact, until a dedicated cell is run.

---

## Step 1c — gate scope

Manifest: `analysis/data/run_state/resolve-open-four/manifests/1c-manifest.json`.

| scope | lift | n |
|---|---|---|
| ledger entry-1 scope | +5.17pp | 58 |
| ALL16 | −3.08pp | 195 |
| ALL16 established | −6.31pp | 111 |
| ALL16 speculative | +1.19pp | 84 |
| AVGO/NVDA/ORCL/TTD (~73% of portfolio) | −3.57pp | 56 |

All five figures reproduce the first pass exactly (`1c-manifest.json` →
`results.<scope>.lift_pp` / `.n`). These are **not forward draws** in the
tie-break-seed sense — `lift_for_events` is a deterministic scoring pass over
the fixed corpus, no seed involved.

`data/gate_ledger.json` entry 1 scopes to seven names (`ENPH, TTD, AMPX, ENVX,
EOSE, QS, SPWR`), no established names, ENPH not in ALL16, champion 4.94pp
(n=81), challenger −2.50pp (n=80), delta −7.44pp vs. noise floor 4.2pp,
`pct_tickers_improved` 28.6% (2/7), holdout n=0 both arms. **The reconstructed
ledger-entry-1 lift of +5.17pp (n=58) corroborates the ledger's champion
4.94pp (n=81) closely enough to validate the scope reconstruction — agree with
the first pass's read.**

Reporting only, per the prompt's scope boundary: §4.5 is not resolved, and
`PROMOTION_GATE.md` is not amended. The reframing to carry forward: the
lift metric's baseline is *always predict bullish*, a punishing benchmark in
this rising window — and direction-calling and position-sizing are different
skills. The −3.57pp lift on the four names carrying ~73% of the portfolio
measures the first; the portfolio's own zero-information-arm comparison
(established elsewhere, not re-derived this run) is what shows the portfolio
is paid for the second.

---

## Step 1d — sonnet-4-6 error direction

Reproduced via a fresh, read-only DB query this session (no writes; counts
only, matching first pass exactly): champion `claude-sonnet-4-20250514`
`n=6`, all `Add` (mean ordinal 0.000); challenger `claude-sonnet-4-6` `n=36`
(`Add=13, Hold=1, Trim=18, Exit=4`, mean ordinal 1.361); **paired rows
(same ticker + callDate scored by both models): 0**.

**Recorded as undetermined**, per the prompt — six all-`Add` champion rows
with zero overlap with the challenger's 36 rows is not a baseline the
comparison can stand on. The directional signal noted for the record: 61% of
challenger calls are Trim or Exit, which — if it held up under a real paired
comparison — points toward the harness's `pessimistic` arm (~$42,700) rather
than `adjacent` (~$24,886), but this is not asserted as a finding, only
flagged as the direction a properly paired re-score (**Test 4**) should check
first. No new scoring was run.

---

## Step 2 — why the tie-break seed never binds

Manifest: `analysis/data/run_state/resolve-open-four/manifests/2-manifest.json`.
All figures below are from a single seed-0, phase-0 forward run at the
settled cell — not a draw distribution.

**Confirmed, matches first pass**: 27 sessions total; 13 contain at least one
exact `rank_key` tie; 328 tied candidate pairs; 15/15 tie-break seeds give the
identical final value `179944.906085`.

**The prompt's proposed test, run as literally specified, is not usable.**
"Partially funded" defined as `0 < actual_dollars < intended_dollars` (against
the **uncapped** `intended_dollars`) flags **27 of 27 sessions** as containing
a partial fill — because the X=2.5pp session limit itself routinely caps
`target_buy_dollars` below the uncapped `intended_dollars` even when the
capped amount is executed in full. That definition cannot discriminate cash
scarcity from the X-cap and, applied literally, trivially crosses every
tie-session too (13/13 sessions with a tie also show a "partial" by this
definition) — a result with no diagnostic content.

**Built a second, cash-scarcity-specific definition instead**:
`binding == 'cash available'` AND `0 < actual_dollars < target_buy_dollars`
(scarce relative to the session's own already-capped target, not the
theoretical uncapped intended amount). Under this definition:

| metric | count |
|---|---|
| sessions with an exact rank_key tie | 13 / 27 |
| sessions with a cash-scarce partial fill | 10 / 27 |
| **sessions with BOTH** | **8 / 27** |

Both-dates: `2023-06-25, 2023-07-25, 2023-08-24, 2023-11-22, 2024-02-20,
2024-03-21, 2024-05-20, 2024-06-12` (`2-manifest.json` →
`results.both_session_dates_cash_scarce`).

**This refutes the prompt's proposed explanation as literally stated.** It is
not true that no session has both a tie and a (cash-scarce) partial fill — 8
sessions have both, so the seed has a structural opportunity to bind at this
cell. Yet the 15-seed sweep still gives one bit-identical value.

**The non-binding is not fully explained within this run's budget.** The most
plausible mechanism, not independently verified further: within each of the 8
sessions, the tied candidates may sit entirely above or entirely below the
point in the ranked list where cash runs out, so shuffling order *within* the
tied group never moves a candidate across the funding boundary — but this was
not traced index-by-index against `funding_log` per session, so it is
**reported as an open item, not asserted as the answer**. A third wrong answer
recorded as fact would be worse than leaving this open, per the prompt's own
instruction.

### The multiplicity artifact — resolved

`candidates.sort(key=_key, ...)` (`sweep_cadence_and_session_model.py:935`)
sits at the same indentation as, and after, the `for event in in_scope:` loop
that opens Step A (`sweep_cadence_and_session_model.py:772`) — it is a
**sibling, not nested inside that loop**, so `sort()` runs exactly once per
session, not once per event.

The x2…x8 duplicate `rank_key` tuples come instead from
`pending_adds.append(cand)` at `sweep_cadence_and_session_model.py:890`,
which **is** inside the per-event loop. A single session (a ~30-day cadence
bucket) can contain multiple distinct call-date events for the *same* ticker;
each such event independently appends a candidate for that ticker to
`pending_adds`. The candidate pool going into the one `sort()` call can
therefore contain the same ticker multiple times with an identical (or
near-identical) `rank_key` — a real duplication in the candidate pool, not a
sort-mechanics artifact. Whether this causes the same ticker to receive
multiple funding attempts within one session in Step C was not traced further
— out of this run's scope (report, not fix).

### `hash(cadence)` reproducibility defect — confirmed, not applied

`tie_rng = random.Random((seed or 0) * 7919 + hash(cadence) % 1000)`
(`sweep_cadence_and_session_model.py:423`) hashes the **string** `"30"`.
Confirmed present as read. Python randomizes string hashing per process
(`PYTHONHASHSEED`) unless pinned, so the same `seed`/`cadence` pair draws a
different `tie_rng` stream in a different process — a latent reproducibility
defect. Harmless at this cell specifically, since the seed never binds here
regardless. Not captured by `config_hash` in either driver in this repo.
**Proposed fix, not applied this run**: hash `int(cadence)` when cadence is
numeric, or pin `PYTHONHASHSEED=0` process-wide and record it in every
manifest.

**Published 15-draw ranges on the tie-break axis that are single points**: **1**
— the settled cell's own 15-seed sweep (`179944.906085` for every seed). No
other tie-break-seed range was measured in this run to check against; this is
the only such range this run's scope touched.

---

## Step 3 — requote list

| # | old value | new value | published in | should now read |
|---|---|---|---|---|
| 1 | Portfolio drawdown 17.32% quoted alongside SPY/QQQ/TMFC drawdowns as a like-for-like comparison | Portfolio 17.32% is **session-sampled**; SPY/QQQ/TMFC 25.36/35.25/32.99% are **daily-marked** | state-of-play §2 | Restate with both sides on one ruler. Daily-marked portfolio drawdown is 23.46% (phase-avg, seed 0). |
| 2 | "Advantage over SPY: 8.04pp" | 8.04pp is a mismatched-ruler figure (SPY daily − portfolio session) | state-of-play §2 | Like-for-like daily-ruler advantage is **1.90pp**; like-for-like session-ruler advantage is 3.80pp. |
| 3 | §5.2 anomaly #1 (phase sensitivity of drawdown, framed as a fact about trade timing) | Session-ruler phase spread 5.69pp vs. daily-ruler phase spread 1.42pp | state-of-play §5.2 | Anomaly #1 (and #2, same underlying phenomenon) closes as a **sampling artifact** of session-only drawdown marking, not a fact about phase-dependent trade timing. |
| 4 | §5.1 "the only genuine rejection is SPWR — never held, in any draw, at any point," framed as the most encouraging fact in the table | SPWR is a mechanical funding failure, not a rejection | state-of-play §5.1 | See the replacement sentence under Step 1b above. |
| 5 | §4.5's framing of the ledger's −7.44pp delta as evidence about the live portfolio | Ledger entry 1 scopes to 7 names with no established names, ENPH not in ALL16; reconstructed scope-matched lift +5.17pp (n=58) corroborates it | state-of-play §4.5 | The −7.44pp is validated as evidence about the ledger's own narrow scope, not directly about the ALL16 portfolio or its established names — see Step 1c framing above (direction-calling vs. position-sizing). |
| 6 | Analyst-sensitivity wrap-up: "the corpus has no two events on the same date" (explanation for seed never binding) | 36 dates carry 2+ events, 83 events sit in them | analyst-sensitivity-out.md / state-of-play | Explanation is false; do not re-assert. Real (partial) explanation is in Step 2 above — remains an open item, not a closed one. |
| 7 | Review's claim: "exact rank_key ties never occur because gap is continuous" | 328 tied candidate pairs across 13/27 sessions | analyst-sensitivity review | Explanation is false; do not re-assert. |

The design session applies these; this run has **not** edited
`docs/handoffs/2026-09-03-state-of-play.md` or any spec file.

---

## Step 4 — does the settled configuration survive the daily ruler?

Manifest: `analysis/data/run_state/resolve-open-four/manifests/4-manifest.json`.
**All figures below are phase-averaged (phases 0/10/20) forward draws at seed
0** — the 15-draw sweep was **skipped**, per the prompt's own instruction,
because Step 2 shows the tie-break seed never binds at the settled cell (and
this X-axis sweep uses the same funding/scope/order configuration, so the same
non-binding applies at every X tested here — flagged as an inference from
Step 2, not independently re-verified at every X).

| X (pp) | final ($) | dd session | dd daily | gap (daily − session) |
|---|---|---|---|---|
| 0.5 | 121,800 | 3.79% | 6.58% | 2.79pp |
| 1.0 | 144,149 | 7.19% | 12.38% | 5.19pp |
| 1.5 | 160,675 | 10.61% | 17.53% | 6.91pp |
| 2.0 | 171,865 | 14.00% | 21.28% | 7.28pp |
| **2.5** | **184,819** | **17.32%** | **23.46%** | **6.13pp** |
| **3.0** | **189,425** | 20.58% | 27.61% | 7.03pp |
| 4.0 | 179,225 | 24.68% | 32.65% | 7.97pp |
| 5.0 | 168,497 | 26.93% | 34.93% | 8.00pp |
| off | 135,435 | 44.38% | 48.37% | 4.00pp |

Source for every row: `4-manifest.json` → `results.sweep[*]` (`X`,
`phase_avg_final`, `phase_avg_dd_session`, `phase_avg_dd_daily`,
`phase_avg_gap_pp`). Run in **2.57s wall-clock for 27 cells** (9 X-values ×
3 phases) — matches the prompt's "well under a minute" estimate.

**Does the interior optimum sit at the same X on both rulers?**
The drawdown ruler does not change `final_value` at all (drawdown is a
separate diagnostic computed from the same price path, not a decision input),
so the raw-final optimum is identical on both rulers by construction: **X=3.0pp**
(final $189,425), narrowly ahead of X=2.5pp ($184,819 — 97.6% of the X=3.0
value). This is **not** a reversal of the settled choice: state-of-play §0.1
already describes the interior optimum as sitting in a **2.5–3pp band**, and
this single-seed/3-phase measurement places both X=2.5 and X=3.0 inside that
band, 2.4% apart. **The settled configuration (X=2.5pp) stands** — it was
never claimed to be the unique single-point optimum, only the chosen point in
an already-described band, and nothing here moves that band or reorders it.

**Does the understatement vary systematically with X?** The gap column ranges
2.79pp (X=0.5) to 8.00pp (X=5.0), rising roughly monotonically with X through
the capped range before dropping to 4.00pp at `off`. This is a real, mild
systematic effect — tighter caps (lower X) produce more path-smoothing (many
small, frequent trades) and a smaller daily/session gap; looser caps allow
larger single-session moves and a bigger gap. It does **not** reorder which X
wins on final value, and the gap stays well below the ~20pp swing in raw
drawdown across the X range, so it does not on its own explain or threaten the
settled choice.

**Does any cell breach the 39.12% Rule 4 ceiling on the daily ruler?** **Yes —
one**: X=`off` (unconstrained), daily-marked phase-avg drawdown **48.37%**,
well past the ceiling. **No capped cell (X=0.5 through 5.0) breaches it on
either ruler** — the tightest approach is X=5.0 at 34.93% daily. The 39.12%
ceiling itself was calibrated on session-sampled numbers, so it is internally
consistent (it constrains the same ruler it was set against) but understated
in absolute terms relative to what a daily ruler would show for the same
portfolio — reported, not adopted as a new ceiling, per the scope boundary.

**The settled configuration survives.** X=2.5pp remains inside the
2.5–3pp interior-optimum band on both rulers, does not breach the daily-ruler
ceiling, and the daily-ruler understatement at X=2.5pp specifically (6.13pp)
is unremarkable relative to its neighbors — it is not an outlier that would by
itself argue for moving off 2.5pp.

---

## Deviations from the prompt, and why

- Step 1a's assumption check found 2 off-session transaction dates, not the
  implicit 0 the prompt's phrasing ("should fall on a session date") suggested
  — reported as a finding (year-end tax settlement, a known distinct
  mechanism) rather than treated as a blocker, per the prompt's own rule that
  a diagnostic contradicting an expectation is a finding, not a stop.
- Step 2's literal "partial fill" definition (`actual_dollars < intended_dollars`)
  produced a non-diagnostic 27/27 result once run — this is a finding about
  the prompt's own test construction, not a code bug. A second,
  cash-scarcity-specific definition was built to make the test meaningful, and
  both results are reported so the design session can see the distinction.
- Step 2's root-cause question ("why does the seed not bind despite 8 sessions
  having both a tie and a partial fill") is **not fully resolved** — reported
  openly per the prompt's explicit preference for an honest open item over a
  third wrong answer.
- Step 1b's zero-information-arm 16th-ticker mechanism was **not**
  independently re-derived under a manifest — the funding_log evidence is
  consistent with the proposed mechanism but a dedicated zero-info-arm cell
  was not run this session. Flagged, not silently assumed.
- The 15-draw sweep in Step 4 was skipped per the prompt's own conditional
  instruction, on the basis of Step 2's finding that the seed is inert at the
  settled cell — this inference was not independently re-verified at every
  X-value in the sweep (only at the settled X=2.5pp cell).

## What was deliberately not done

- No §4.5 resolution, no `PROMOTION_GATE.md` amendment, no new ceiling
  adopted, no configuration change, no edit to
  `docs/handoffs/2026-09-03-state-of-play.md` or any other spec/doc.
- No LLM calls, no API spend, no DB writes. `price_cache.json` /
  `fundamentals_cache.json` stayed frozen at 2026-05-11 (staleness warning
  observed and expected, not "fixed").
- No new sonnet-4-6 scoring (Step 1d hands off to Test 4).
- No fix applied for the `hash(cadence)` defect (proposed only).
- No index-level trace of *why* the tie-break seed doesn't bind despite the 8
  tie+partial-fill sessions — left open for a follow-up run if it matters
  (it is currently harmless everywhere it has been checked).

## Wall-clock, cells run, cells reused

- Total cells recorded in `cells.jsonl`: **36** (3 for Step 1a's per-phase
  drawdown cells, 5 for Step 1c's gate-scope scopes, 1 for Step 2's
  partial-vs-tie cross, 27 for Step 4's 9×3 X-axis sweep).
- Step 4 wall-clock: **2.57s** for its 27 cells (from the manifest's
  `results.wall_clock_seconds`).
- Total session wall-clock for the manifested driver's four steps combined:
  ~9s (measured via shell timing around the 1a/1c/2 batch, plus Step 4's own
  measured 2.57s — the 1a/1c/2 batch includes corpus load once per invocation,
  ~2.7s each, so most of the 9s is three separate corpus loads, not compute).
- No cells were reused from a prior run — this `run_id` had no earlier state.
  Everything above is freshly computed this session.

## Files written / committed

| file | commit |
|---|---|
| `analysis/resolve_open_four.py` | `fb9ec8f` |
| `analysis/resolve_open_four_manifest.py` (created) | `04125e1` |
| `analysis/resolve_open_four_manifest.py` (dirty-check fix) | `9c2e159` |
| `analysis/data/run_state/resolve-open-four/progress.json` | not yet committed — committed with this wrap-up, see follow-up commands |
| `analysis/data/run_state/resolve-open-four/cells.jsonl` | not yet committed — committed with this wrap-up |
| `analysis/data/run_state/resolve-open-four/findings.md` | not yet committed — committed with this wrap-up |
| `analysis/data/run_state/resolve-open-four/manifests/{1a,1c,2,4}-manifest.json` | not yet committed — committed with this wrap-up |
| `wrap-ups/resolve-open-four-out.md` (this file) | not yet committed — committed after this write |

## Follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git add analysis/data/run_state/resolve-open-four/ wrap-ups/resolve-open-four-out.md
git commit -m "run: resolve-open-four -- manifests, run_state, wrap-up"
```

To re-run any step from a clean tree:

```bash
cd analysis
python3 resolve_open_four.py ABCDE          # unmanifested checks, stdout only
python3 resolve_open_four_manifest.py 1a     # manifested drawdown-ruler reconstruction
python3 resolve_open_four_manifest.py 1c     # manifested gate-scope lift
python3 resolve_open_four_manifest.py 2      # manifested tie/partial-fill cross
python3 resolve_open_four_manifest.py 4      # manifested X-axis daily-ruler sweep
```
