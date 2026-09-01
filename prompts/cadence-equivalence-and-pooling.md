# Session-model equivalence — split the machinery from the algorithm

`wrap-ups/sweep-cadence-and-session-model-out.md` stopped at the Step 1
equivalence gate, correctly and as instructed. Three real bugs were found and
fixed on the way there — §4 ranking overriding draw order at per-call cadence
(which had silently made all fifteen draws identical), a starter wrongly gated
on `final_action`, and `no_reserve_raw`'s defect-preserving pass-through
collapsed into the s11-fixed rebuild. That debugging was sound and its fixes
stand.

**The remaining gap is very likely not a bug, and the gate was mis-specified by
the design session.** That is the fifth prompt-drafting error in this thread and
the same shape as the others: the gate encoded an assumption instead of a
correctness condition.

**Why.** The wrap-up dismissed sell-then-buy reordering on the grounds that
per-call sessions are dominated by single events. They are not: §2 measures that
**63.4% of calls land on a day with at least one other call**, so "one session
per distinct call date" bundles two or more events most of the time. On any
multi-event session the two algorithms genuinely differ:

- **Old harness** — event by event; each event's full trade set, sells *and*
  buys, executes before the next event is considered.
- **§3 session model** — all sells execute, then all cash is pooled ("standing
  balance plus this session's proceeds"), then buys deploy in rank order.

Every session containing a sell and a buy therefore gives the buy access to
proceeds it would not have seen under the old model. Across a run that
systematically increases deployable cash, and at `off` — with no ceiling to
throttle it — more early cash reaches the names that compounded. A +34% result
is entirely consistent with that.

**So the +34% may be the measured value of §3's pooling, not a defect.** This
run's job is to establish which, by separating the two things the last gate
conflated: *is the machinery faithful* (a correctness question) and *does the
algorithm differ* (a measurement).

Read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b and §11
before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**. Work on `sweep/db-corpus-baseline`. Write
findings to `./wrap-ups/cadence-equivalence-and-pooling-out.md`.

---

## Step 0 — carry forward, plus two hygiene fixes

Clean tree with a hard stop if `git_dirty` cannot be `false`; driver committed
**before** any manifest is written; import-time assertions on both; `loaded_`
and `in_window_event_count` recorded separately. `off` belongs at the **loose**
end of any limit axis.

**0a. Commit the previous wrap-up.** `wrap-ups/sweep-cadence-and-session-model-out.md`
is still untracked, and the last run's manifests appear to share the driver's
commit rather than following it. Commit the wrap-up, and keep driver-then-
manifests as separate commits in that order.

**0b. Stop duplicating shared helpers.** The last driver copied
`_rebuild_buy_leg` verbatim rather than importing it, because
`bracket_three_modes_s11_corrected.py` asserts `git_dirty=False` **at import
time**. That assertion is in the wrong place: it fires when the module is
imported rather than when a run is recorded. Move it into an explicit
`assert_clean_for_manifest()` called by the manifest writer, then **import** the
shared helpers instead of copying them.

This is not tidiness. Task #77 — the defect this entire thread began with — was
two implementations of the same sizing rule drifting apart in different
sessions. Duplicating `_rebuild_buy_leg` recreates exactly that hazard.

## Step 1 — two checks, only one of which is a gate

### 1a. Single-event equivalence — HARD GATE

Configure sessions so that **each session contains exactly one event**: where
several calls share a date, split them into consecutive single-event sessions in
draw order. In this configuration §3's pooling has nothing to pool and the two
algorithms must coincide exactly.

```
swap_funding, 2.5pp, single-event sessions, new_calls_only, forward draw  ->  $190,481.16304357877
no_reserve_raw, off, single-event sessions, new_calls_only, forward draw  ->  $141,836.57
```

**If either differs by a cent, stop and report.** In that configuration a
difference is a genuine faithfulness bug in the session machinery, and the right
response is the line-by-line diff the last wrap-up recommends —
`make_funding_decide_fn` (`bracket_three_modes_s11_corrected.py:257-494`)
against the new driver's Step A / Step C split — not another round of guessing
against symptoms.

Also report, for the record: the number of **distinct call dates** the 147
in-window events span, and the distribution of events per date. That is the
evidence for or against the premise above, and nobody has ever reported it.

### 1b. Per-call-date sessions — A MEASUREMENT, NOT A GATE

Same two configurations, but with same-day calls **bundled into one session**,
as §3 specifies. Report the delta against 1a, in dollars and percent, for both
reference configurations.

**Whatever this delta is, do not stop on it.** It is the quantity this run
exists to measure: the value of §3's evaluate-then-pool-then-deploy sequence
relative to per-event immediate execution. Report it as a finding.

## Step 2 — pooling as its own axis

If 1a passes, the machinery is faithful and the difference is algorithmic. Price
it properly rather than leaving it as a single number.

Add an explicit **execution-order** axis and sweep it:

| Value | Behavior |
|---|---|
| `sequential` | each event's full trade set executes before the next — reproduces the validated per-call harness |
| `pooled` | §3's specified sequence: all sells, then pool cash, then deploy in rank order |

Run both across the limit axis — `off`, 0.5, 1, 1.5, 2, 2.5, 3, 5 pp — at
per-call-date sessions, `swap_funding`, `new_calls_only`, 7 draws
(forward, reversed, seeds 1–5).

Two questions to answer explicitly:

- **Does pooling's advantage survive a tight ceiling?** At `off` it should be
  large — nothing throttles the extra cash. At 2.5pp the ceiling may absorb it.
  If pooling's benefit collapses at tight limits, then the settled 2.5pp result
  is unaffected by this discovery and the previous six sessions stand as
  measured. **If it does not collapse, every prior result understates the
  production design**, and that has to be said plainly.
- **Does it move the optimal limit?** Report the limit surface under each
  execution order, with Rule 3's material/immaterial classification.

## Step 3 — the cadence grid

Only if Steps 1a and 2 complete. `swap_funding`, `pooled` execution (the spec's
behavior), conformant per-date trim cap.

| Axis | Values |
|---|---|
| **`K`** | 7, 14, 30, 60, 90 days, plus the **seasonal** variant (weekly during days 15–42 after each quarter-end, monthly otherwise) |
| **Phase** | 3 offsets per `K`, reported phase-averaged with the spread |
| **Scope** | `new_calls_only`, `cash_deployment` |
| **Limit `X`** | 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5 pp, and `off` |
| **Draws** | 7 for the scan; re-run the top region at 15 |

Report per configuration: final value min / median / max and spread as a % of
median; max drawdown min / median / max; and forward-draw diagnostics — days
below 1% cash, Adds fully funded / partial / unfunded, cumulative shortfall,
distinct tickers held, displacement count, donor size distribution, and
**per-ticker mean information staleness**.

Phase handling per §2: every `K` at ≥3 offsets, reported phase-averaged, with
the spread across phases as a fragility signal.

## Step 4 — the fold-ins

**4a. `minPositionPct` and the stub rule.** At the best cadence/limit region,
sweep the floor as a percentage of portfolio — 0 (off), 0.25%, 0.5%, 1% — with
the rule *if a swap-funding trim would leave the donor below
`max(pct × portfolio, $100)`, sell the whole position instead*. Report effect on
final value, drawdown, displacement count, realized gains, distinct tickers.

**4b. Ordering confirmation, once.** At the winning cadence and limit, run
forward / reversed / 3 seeds and report the spread. Under 2% means the ordering
question is answered and §4's seeded tie-break stands on principle.

**4c. Staleness vs. return.** For each `K`, mean information staleness against
median final value. This is what prices Step 6 (automated transcript ingestion).

## Step 5 — the gates and the rules

**Gates** — the five from the last run, unchanged, plus 1a above. Invariant #9
is **per session**, not per event: cash-deployment scope can touch one ticker
twice in a session, so verify the aggregate. Invariant #5 stays conditional —
stop only on a skipped event not classified `known_s11_concatenation`; an
unclassifiable skip is a stop. **No gate may test a condition §11 documents as a
known unfixed defect, and a diagnostic that contradicts an expectation in this
prompt is a finding, never a reason to stop.**

**Rules 1, 2 and 4 unchanged.** Rule 4 scores against the **adopted 39.12%**
ceiling on median drawdown across draws, plus share-of-draws; robust requires
≥ 2/3. Rule 2: overlapping ranges are **tied**, never ranked by median.

**Rule 3** — single clause, `off` at the loose end. A difference is material if
`|Δ| ≥` the smaller of the two adjacent configurations' draw ranges; discard
immaterial ones; unimodal if what remains reads `+…+ −…−`.

**Rule 3b** — plateau is every value whose median is within **2.5%** of the
peak's median, with sensitivity reported at 1% / 2.5% / 5%. Never an argmax. If
the peak sits at either end of the sampled range, the optimum is **not
bracketed** — say so and recommend nothing.

## Step 6 — report

Scope boundary: **report, do not decide.** Do not select `K`, a limit, a scope,
an execution order, or a `minPositionPct`; do not amend any spec; do not resolve
§12 items; do not start the veto sweep.

Lead with:

> **Single-event equivalence gate: [passed / failed]. Distinct call dates: [N]
> for 147 events. Pooling delta at per-call-date sessions: [$X] ([Y]%) at `off`,
> [$X] ([Y]%) at 2.5pp — [survives / collapses under] a tight ceiling.
> Minimum viable cadence: `K` = [X]. Best cell: `K`=[X], scope=[Y], limit=[Z]pp
> — [return], [DD]. Limit surface: [unimodal / jagged]; plateau [set]; optimum
> [bracketed / NOT bracketed]. `minPositionPct`: [housekeeping / material].
> Ordering spread: [X]%.**

Then: the equivalence results, the call-date distribution, the pooling axis, the
cadence grid, the limit surface per cadence with classification and plateau, the
staleness/return frontier, the fold-ins, and Rule 4 scoring.

Flag plainly: any gate that fails, any rule that gives an uncomfortable answer,
and — specifically — **whether any previously settled result is invalidated by
the pooling finding**. If the six prior sessions measured a regime the
production design will not use, that is the most important sentence in the
report and it belongs near the top.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev`.
- Do not stage or commit the user's unrelated working-tree changes on their
  behalf — stash and pop. `testing/` stays gitignored.
- Report wall-clock runtime and the cell count actually run.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
