# Close equivalence — corrected gate targets, then the cadence grid

**Supersedes `prompts/close-equivalence-and-run-cadence.md` entirely.** That
prompt's Gate 1a target for `swap_funding` was wrong, and two sessions of
excellent debugging were spent chasing a gap that was mostly an artifact of the
design session's error.

## What was wrong

`prompts/close-equivalence-and-run-cadence.md` asked for:

> `swap_funding, 2.5pp, single_event, new_calls_only, forward` → `$190,481.16304357877`

**`$190,481.16304357877` is the median across 15 draws, not a forward draw.**
It is `results.final.median` in
`analysis/data/run_manifests/bracket-swap_funding-2.5pp-manifest.json`. The
forward draw for that identical configuration is recorded in the same file, at
`results.forward_diagnostics.final_value`, and is
**`$189,781.58036163618`**. A forward draw was being asked to equal a median; it
never could.

The other target was correct: `$141,836.57` genuinely is a forward draw, which is
exactly why `no_reserve_raw` passed to sub-cent while `swap_funding` did not.

**The real divergence is therefore ~$72.75, not $626.83:**

| | value |
|---|---|
| Reference `run_cell`, forward | $189,781.58036163618 |
| Session model, `single_event` forward (last run) | $189,854.3296242896 |
| **True gap** | **≈ $72.75** |

That is consistent with the −$68.50 `total_value` gap the last run localized at
2024-01-24 riding forward — one small divergence, not a systemic one.

The last run measured `$189,781.58` itself and reported it as a "tangential,
non-blocking observation," reasoning that the gate target must be the session
model's own expected value. That was the one place it explained away the thing
that mattered — understandably, since the target's provenance was asserted by
the prompt rather than cited.

## What stands from the last run

- **The year-end tax fix (`cbba37e`) is real and stays.** Anchoring the forced
  liquidation price to literal Dec 31 rather than the year's last session date
  is correct, and it is verified bit-exact for 2022 and 2023. It appeared to
  change nothing only because the headline number was measuring the wrong thing;
  its true effect lives inside the $72.75.
- **The mid-day `start_of_day_value` backfill hypothesis was tested, had zero
  effect, and was correctly reverted.** Do not re-test it.
- **The divergence window `(2023-12-11, 2024-01-24]` still holds**, and every
  trade in it is confirmed bit-identical.
- **The reference is behaviorally unchanged.** `bracket_three_modes_s11_corrected.py`
  was modified after its manifest commit (`77b541a` → `3f8a563`), but the design
  session verified that diff is purely git bookkeeping — `_current_git_state()`
  split out, `assert_clean_for_manifest()` moved to manifest-write time. No
  simulation logic touched. `$189,781.58036163618` is trustworthy.

## New standing rule

**Every reference figure a gate compares against must name its provenance in the
prompt: the manifest path and the exact JSON key.** A bare number is how this
happened. Where a prompt quotes a figure without provenance, treat that as a
premise to verify before relying on it, and say so.

Read `ALLOCATOR_OPERATING_MODEL.md` §0, §2, §3, §4, §5, §9, §10, §10b and §11
before starting. Decisions there are closed.

**No LLM calls, no API spend, no DB writes.** Clean window
(2022-01-01 → 2024-06-12), ALL16, `decide_v3`, frozen-JSON `type_for_ticker`,
unchanged caches, dedup **on**. Work on `sweep/db-corpus-baseline`. Write
findings to `./wrap-ups/close-equivalence-corrected-targets-out.md`.

---

## Step −1 — resume protocol

`run_id` is **`close-equivalence-corrected-targets`**. State lives in
`analysis/data/run_state/<run_id>/` — `progress.json`, `cells.jsonl`,
`findings.md` — under the standing convention in `CLAUDE.md`.

**Write state before reading anything.** Create the directory and an initial
`progress.json` — every step `pending`, `next_action` set to "spec reading not
yet started" — as the **very first action of the session**, before reading the
architecture documents, before seeding `findings.md`, before Step 0. A previous
attempt at this prompt exhausted its budget on the reading and left no
checkpoint at all, which is the one failure mode the protocol does not otherwise
cover. Update `next_action` again once the reading is done, so a session that
dies mid-read resumes at the right place rather than repeating it.

**Seed, do not discard.** This is a new `run_id`, so state starts fresh, but copy
`analysis/data/run_state/close-equivalence-and-run-cadence/findings.md` in as
prior context first and note in `progress.json` that it came from the superseded
run. **Do not reuse that run's `cells.jsonl`** — those three cells were measured
against the wrong target.

Then the usual: flush `cells.jsonl` after every cell, update `progress.json`
after every step, append to `findings.md` the moment a finding is established.
Running low on budget is a reason to stop cleanly with a precise `next_action`,
not to rush.

## Step 0 — hygiene, verify rather than redo

The superseded run already committed its wrap-up, split the import-time
assertion, and switched to importing shared helpers. **Verify these hold; do not
redo them.** Then confirm the tree is clean, with a hard stop if `git_dirty`
cannot be recorded `false`.

## Step 1 — Gate 1a, corrected targets

Both targets are forward draws, both cited to their source:

| Config | Target | Provenance |
|---|---|---|
| `no_reserve_raw`, `off`, `single_event`, `new_calls_only`, forward | `$141,836.57` | standing assertion; `step1-five-gates-manifest.json` |
| `swap_funding`, 2.5pp, `single_event`, `new_calls_only`, forward | **`$189,781.58036163618`** | `bracket-swap_funding-2.5pp-manifest.json` → `results.forward_diagnostics.final_value` |

**Before running, re-read both figures out of those manifests and confirm they
match what is written above.** If either disagrees, stop — the design session
has quoted a wrong number twice and a third would be worse.

Then run the gate. **Hard stop if either differs by a cent.**

## Step 2 — if the gate still fails, close the residual

Expect a gap near $72.75. The instrument the last run lacked:

**Make the session model snapshot `total_value` on every calendar day**, not only
on session dates, behind a debug flag. Without that a like-for-like daily diff
across `(2023-12-11, 2024-01-24]` is impossible, which is precisely why the last
run could not pin the date. Add it, then diff day by day and report the **first
calendar date the two disagree**, with both values.

Then check the three candidates the last run named, in order:

1. a cash-only bookkeeping path with no `Trade` object — dividends or interest
   accrual, if the simulator has one. **Note that §5 says cash earns no
   interest, so if such a path exists it may itself be a spec violation worth
   reporting separately.**
2. per-account cash aggregation in `portfolio.total_value`, session-native
   versus daily
3. a trade just outside the searched window whose effect only surfaces in the
   2024-01-24 mark-to-market

Fix what you find. If it turns out to be a reference-versus-spec divergence
rather than a coding error, do not fix it into the reference path — handle it
under Step 3's toggle discipline and say so.

## Step 3 — price the spec corrections as deltas

Once the gate passes, re-run both configurations with
`trim_budget_scope = per_session` (spec-faithful) against `per_event_date` (what
the reference does), and report the delta in dollars and percent. Same for any
other reference-versus-spec divergence Step 2 surfaced.

§11's pattern: baseline as-is for comparability, corrections measured
separately, adopted deliberately. **Report only — do not switch the default.**

## Step 4 — pooling, re-derived

Re-derive the pooling deltas fresh against the now-exact single-event numbers;
the previous figures were measured against a not-yet-exact baseline.

Then sweep execution order as an axis — `sequential` (per-event immediate
execution) versus `pooled` (§3's evaluate-then-pool-then-deploy) — across `off`,
0.5, 1, 1.5, 2, 2.5, 3, 5 pp at per-call-date sessions, `swap_funding`,
`new_calls_only`, 7 draws.

Answer explicitly: does pooling's advantage survive a tight ceiling, and does it
move the optimal limit? The last run measured +34.4% at `off` and +0.7% at 2.5pp
against an inexact baseline — confirm or refute against the corrected one.

## Step 5 — the cadence grid

`swap_funding`, `pooled` execution, conformant per-date trim cap.

| Axis | Values |
|---|---|
| **`K`** | 7, 14, 30, 60, 90 days, plus the **seasonal** variant (weekly during days 15–42 after each quarter-end, monthly otherwise) |
| **Phase** | 3 offsets per `K`, phase-averaged with the spread reported as a fragility signal |
| **Scope** | `new_calls_only`, `cash_deployment` |
| **Limit `X`** | 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5 pp, and `off` |
| **Draws** | 7 for the scan; re-run the top region at 15 |

Per configuration: final value min / median / max and spread as % of median; max
drawdown min / median / max; and forward-draw diagnostics — days below 1% cash,
Adds fully funded / partial / unfunded, cumulative shortfall, distinct tickers
held, displacement count, donor size distribution, and **per-ticker mean
information staleness**.

## Step 6 — fold-ins

**6a. `minPositionPct` and the stub rule.** At the best cadence/limit region,
sweep the floor as a percentage of portfolio — 0, 0.25%, 0.5%, 1% — with the
rule *if a swap-funding trim would leave the donor below
`max(pct × portfolio, $100)`, sell the whole position instead*. Report effect on
final value, drawdown, displacement count, realized gains, distinct tickers.

**6b. Ordering confirmation, once.** At the winning cadence and limit: forward /
reversed / 3 seeds, report the spread. Under 2% answers the question.

**6c. Staleness vs return.** Per `K`, mean staleness against median final value.

## Step 7 — gates and rules

**Gates:** the five carried forward, plus Step 1's. Invariant #9 is **per
session** — cash-deployment scope can touch a ticker twice in a session, so
verify the aggregate. Invariant #5 stays conditional: stop only on a skipped
event not classified `known_s11_concatenation`; an unclassifiable skip is a stop.
**No gate may test a condition §11 documents as a known unfixed defect, and a
diagnostic that contradicts an expectation in this prompt is a finding, never a
reason to stop.**

**Rules 1, 2, 4 unchanged.** Rule 4 scores against the adopted **39.12%** ceiling
on median drawdown across draws plus share-of-draws; robust requires ≥ 2/3.
Rule 2: overlapping ranges are **tied**, never ranked by median.

**Rule 3** — single clause, `off` at the **loose** end. Material if `|Δ| ≥` the
smaller of the two adjacent draw ranges; discard immaterial; unimodal if what
remains reads `+…+ −…−`.

**Rule 3b** — plateau is every value within **2.5%** of the peak median, with
sensitivity at 1% / 2.5% / 5%. Never an argmax. Peak at either end of the sampled
range means the optimum is **not bracketed**.

**When comparing any two numbers, state for each whether it is a forward draw, a
median, or something else.** That is the discipline this whole amendment exists
to install.

## Step 8 — report

Scope boundary: **report, do not decide.** Do not select `K`, a limit, a scope,
an execution order, a trim-budget scope, or a `minPositionPct`; do not amend any
spec; do not resolve §12 items; do not start the veto sweep.

Open with resume status — what was seeded from the superseded run, cells run,
whether this is partial — then:

> **Gate 1a, corrected targets: [passed / failed]. Residual, if any: [$X], first
> diverging calendar date [date], cause [what]. Spec-correction deltas:
> `per_session` trim budget [±$X, ±Y%]. Pooling: [±X%] at `off`, [±Y%] at
> 2.5pp — [survives / collapses]. Minimum viable cadence: `K` = [X]. Best cell:
> `K`=[X], scope=[Y], limit=[Z]pp — [return], [DD]. Limit surface:
> [unimodal / jagged]; plateau [set]; optimum [bracketed / NOT bracketed].
> `minPositionPct`: [housekeeping / material]. Ordering spread: [X]%.**

Flag plainly: any gate that fails, any rule that gives an uncomfortable answer,
any previously published number that turns out to be wrong, and whether anything
disturbs the six settled sessions in §0.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no API spend, **no DB writes**.
- No cache refreshes — `price_cache.json` / `fundamentals_cache.json` stay
  frozen at 2026-05-11; the staleness warning is expected.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Do not stage or commit unrelated working-tree changes — stash and pop.
  `testing/` stays gitignored.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
