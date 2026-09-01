# Close the equivalence gate, then run the cadence grid — resumable

`wrap-ups/cadence-equivalence-and-pooling-out.md` was the most productive
failure in this thread. Three things landed:

- **The prior run's "34% bug" was §3's pooling, confirmed exactly.**
  `$190,622.14` reproduces to the cent under bundled sessions. That driver's
  `per_call` cadence bucketed same-date calls into one session while its label
  promised per-event equivalence.
- **`no_reserve_raw` now reproduces the control exactly** — `$141,836.5657`
  against `$141,836.57`. The session machinery is faithful for the control; the
  residual gap is swap-funding-specific, i.e. donor-side bookkeeping.
- **Pooling collapses under a tight ceiling**, as predicted: +34.4% at `off`,
  **+0.7% at 2.5pp**. The six settled sessions stand — nothing in §0 is
  disturbed.

Corrected for the record: §2's 63.4% share-a-date figure is measured against the
full 32-ticker / 659-call corpus. For the 147-event ALL16 window the real
figures are **112 distinct dates, 44.2% of events sharing one**. The design
session transferred a number across corpora without checking; the CLI measured
it instead. Use the measured figures.

**The gate still fails at `swap_funding` 2.5pp by −$626.83 (−0.33%), and the
design session's gate was mis-specified again.** Fix #3 (resetting the donor
trim budget per calendar date rather than per session) is provably more
spec-faithful and moved the number *further* from target. Keeping it was
correct — matching a target for the wrong reason is worse than missing it. But
it exposes the real problem: **the reference implementation is not itself
spec-perfect, and a gate demanding bit-exact reproduction of it therefore
demands reproducing its quirks.** Faithfulness-to-reference and
faithfulness-to-spec are two different goals and this prompt separates them,
using §11's own handling policy — reproduce the reference as-is for
comparability, bank the equivalence, then measure spec corrections as deltas.

Read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b and §11
before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**. Work on `sweep/db-corpus-baseline`. Write
findings to `./wrap-ups/close-equivalence-and-run-cadence-out.md`.

---

## Step −1 — RESUME PROTOCOL (do this first, every time)

**This run is long enough to exhaust a session. It must be restartable without
losing work.** Before anything else, establish or resume run state.

`run_id` for this prompt is **`close-equivalence-and-run-cadence`**. State lives
in `analysis/data/run_state/<run_id>/`:

| File | Contents |
|---|---|
| `progress.json` | `prompt_sha256`, `driver_commit`, per-step status (`pending` / `in_progress` / `done`), `next_action` (one sentence), `notes[]` |
| `cells.jsonl` | one JSON line per completed backtest cell: `cell_key`, `params`, `config_hash`, `results` |
| `findings.md` | append-only; every established finding written the moment it is established |

**On start:**

1. If `progress.json` exists **and** its `prompt_sha256` matches the sha256 of
   this prompt file → **resume.** Report at the top of the wrap-up exactly which
   steps were already done and which cells were reused. Skip completed steps.
2. If `prompt_sha256` differs → the prompt changed. Archive the old directory to
   `<run_id>-superseded-<timestamp>/`, start fresh, and say so.
3. If `driver_commit` differs from HEAD for the driver file → behaviour may have
   changed. **Invalidate `cells.jsonl`** (delete or archive it) but keep
   `findings.md`. Say so.

**While running:**

- Compute `config_hash` per cell as sha256 over the driver commit plus the
  full sorted parameter set. **Skip any cell already in `cells.jsonl` with a
  matching `config_hash`**; count and report reused cells.
- **Flush after every cell.** Append to `cells.jsonl` and fsync before starting
  the next one. A killed session must lose at most one cell.
- Update `progress.json`'s step status and `next_action` after **every** step,
  not at the end.
- Append to `findings.md` the moment a finding is established, in the wording
  you would use in the wrap-up. Never hold findings in memory for a final
  composition pass.

**If you are running low on budget:** stop cleanly. Write the wrap-up with
everything completed so far, mark the remaining steps `pending` in
`progress.json` with a precise `next_action`, and say plainly in the wrap-up
that this is a partial run and what remains. **A partial run that resumes is
worth far more than a complete run that is lost.**

`analysis/data/run_state/` must be un-ignored in `.gitignore` the same way
`run_manifests/` was, and committed — state that exists only on disk defeats
the purpose.

## Step 0 — carry forward

Clean tree with a hard stop if `git_dirty` cannot be `false`; driver committed
**before** any manifest, as its own commit; manifests in a following commit;
`loaded_` and `in_window_event_count` recorded separately. `off` belongs at the
**loose** end of any limit axis.

## Step 1 — find the fourth bug

Entries 0–75 of the funding log already match to sub-cent. The first divergence
is `QS` on 2024-02-14, where donors `RUN → ENVX → EOSE → TSLA` raise identical
amounts to the last digit and only the final cap-binding donor `AAPL` differs
($488.32 reference vs $500.48 new). That points at accumulated donor state, not
anything local to that date.

Instrument `day_start_of_day_value[t]` and `day_trimmed_today[t]` for **every**
donor at **every** calendar date they are touched, in both implementations, from
2022-01-01 forward. Report the **first date and ticker where they disagree**,
with both values and the trades that produced them.

Fix what that reveals. If it turns out to be a further spec-versus-reference
divergence rather than a coding error, say so and treat it under Step 3's toggle
discipline rather than "fixing" it into the reference path.

## Step 2 — Gate 1a, under reference-faithful settings

Make the trim-budget scope an explicit parameter:

| Value | Behaviour |
|---|---|
| `per_event_date` | one 25% donor budget per calendar date, shared across events on that date — **what `make_funding_decide_fn` actually does** |
| `per_session` | one budget per session — spec-faithful under §5's "per session" wording |

**Run the gate with `per_event_date`**, i.e. reproducing the reference exactly,
quirks included:

```
no_reserve_raw, off, single_event, new_calls_only, forward  ->  $141,836.57
swap_funding, 2.5pp, single_event, new_calls_only, forward  ->  $190,481.16304357877
```

**Hard stop if either differs by a cent.** This is now a pure faithfulness
question with no spec ambiguity left in it, so a failure here is a real bug.

## Step 3 — price the spec corrections as deltas

Once the gate passes, re-run the same two configurations with
`trim_budget_scope = per_session` and report the delta in dollars and percent.
Do the same for any other reference-versus-spec divergence Step 1 surfaced.

This is the §11 pattern: baseline as-is for comparability, corrections measured
separately, adopted deliberately rather than by accident. **Report only** — do
not switch the default.

## Step 4 — pooling, re-derived

Re-derive the pooling deltas fresh against the now-exact single-event numbers
— the previous run's figures were measured against a not-yet-exact baseline and
should not be carried forward.

Then sweep execution order as an axis: `sequential` (per-event immediate
execution) versus `pooled` (§3's evaluate-then-pool-then-deploy), across `off`,
0.5, 1, 1.5, 2, 2.5, 3, 5 pp at per-call-date sessions, `swap_funding`,
`new_calls_only`, 7 draws.

Answer explicitly: does pooling's advantage survive a tight ceiling, and does it
move the optimal limit? The expectation from the last run is that it collapses;
confirm or refute it against the corrected baseline.

## Step 5 — the cadence grid

`swap_funding`, `pooled` execution, conformant per-date trim cap.

| Axis | Values |
|---|---|
| **`K`** | 7, 14, 30, 60, 90 days, plus the **seasonal** variant (weekly during days 15–42 after each quarter-end, monthly otherwise) |
| **Phase** | 3 offsets per `K`, reported phase-averaged with the spread |
| **Scope** | `new_calls_only`, `cash_deployment` |
| **Limit `X`** | 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5 pp, and `off` |
| **Draws** | 7 for the scan; re-run the top region at 15 |

Per configuration: final value min / median / max and spread as % of median; max
drawdown min / median / max; and forward-draw diagnostics — days below 1% cash,
Adds fully funded / partial / unfunded, cumulative shortfall, distinct tickers
held, displacement count, donor size distribution, and **per-ticker mean
information staleness**.

Phase per §2: ≥3 offsets per `K`, phase-averaged, spread reported as a fragility
signal.

## Step 6 — the fold-ins

**6a. `minPositionPct` and the stub rule.** At the best cadence/limit region,
sweep the floor as a percentage of portfolio — 0, 0.25%, 0.5%, 1% — with the
rule *if a swap-funding trim would leave the donor below
`max(pct × portfolio, $100)`, sell the whole position instead*. Report effect on
final value, drawdown, displacement count, realized gains, distinct tickers.

**6b. Ordering confirmation, once.** At the winning cadence and limit: forward /
reversed / 3 seeds, report the spread. Under 2% answers the ordering question.

**6c. Staleness vs return.** Per `K`, mean staleness against median final value
— this prices Step 6 (automated ingestion) in §10's expected outputs.

## Step 7 — gates and rules

**Gates:** the five carried forward, plus Step 2's. Invariant #9 is **per
session** — cash-deployment scope can touch a ticker twice in a session, so
verify the aggregate. Invariant #5 stays conditional: stop only on a skipped
event not classified `known_s11_concatenation`; an unclassifiable skip is a
stop. **No gate may test a condition §11 documents as a known unfixed defect,
and a diagnostic that contradicts an expectation in this prompt is a finding,
never a reason to stop.**

**Rules 1, 2, 4 unchanged.** Rule 4 scores against the adopted **39.12%**
ceiling on median drawdown across draws plus share-of-draws; robust requires
≥ 2/3. Rule 2: overlapping ranges are **tied**, never ranked by median.

**Rule 3** — single clause, `off` at the loose end. Material if `|Δ| ≥` the
smaller of the two adjacent draw ranges; discard immaterial; unimodal if what
remains reads `+…+ −…−`.

**Rule 3b** — plateau is every value within **2.5%** of the peak median, with
sensitivity at 1% / 2.5% / 5%. Never an argmax. Peak at either end of the
sampled range means the optimum is **not bracketed**.

## Step 8 — report

Scope boundary: **report, do not decide.** Do not select `K`, a limit, a scope,
an execution order, a trim-budget scope, or a `minPositionPct`; do not amend any
spec; do not resolve §12 items; do not start the veto sweep.

Open the wrap-up with the resume status — which steps were already done, how
many cells were reused, whether this is a partial run — then:

> **Fourth bug: [what it was, first date/ticker of disagreement]. Gate 1a under
> `per_event_date`: [passed / failed]. Spec-correction deltas: `per_session`
> trim budget [±$X, ±Y%]. Pooling: [±X%] at `off`, [±Y%] at 2.5pp —
> [survives / collapses]. Minimum viable cadence: `K` = [X]. Best cell:
> `K`=[X], scope=[Y], limit=[Z]pp — [return], [DD]. Limit surface:
> [unimodal / jagged]; plateau [set]; optimum [bracketed / NOT bracketed].
> `minPositionPct`: [housekeeping / material]. Ordering spread: [X]%.**

Flag plainly: any gate that fails, any rule that gives an uncomfortable answer,
any previously published number that turns out to be wrong, and whether anything
here disturbs the six settled sessions in §0.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop. `testing/` stays gitignored.
- Report wall-clock runtime, cells run, and cells reused from state.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
