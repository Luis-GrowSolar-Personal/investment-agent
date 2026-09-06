# Test 5 — universe substitution, 16 versus 16

`docs/handoffs/2026-09-03-state-of-play.md` §7 Test 5. Read §0 of that
document first, plus `docs/architecture/ALLOCATOR_OPERATING_MODEL.md`
(the settled configuration this measures against) and
`wrap-ups/analyst-sensitivity-out.md` (Test 1 — this run reuses its exact
harness and reproduces its zero-information baseline as a hygiene check).

**Cost: $0 in Anthropic API spend.** AMZN, META, V, and JNJ are already
scored back to 2021 in the DB (confirmed directly by the user, not
assumed — verify in Step 0 anyway per this project's own repeated
"verify the premise" discipline). This is a pure backtest-simulator
re-run over already-scored `Analysis` rows, the same as Test 1 — no new
LLM calls, no new transcripts to load.

## Why this run exists, and a correction to the doc it's based on

The question: does the portfolio's real performance come from the
analyst's specific stock selections, or just from generic exposure to
being invested in large, well-known growth names? Swap the "established"
half of the universe for a different large-cap set chosen by an explicit
rule (not by hand) and see whether the backtest result changes much. A
small change points toward "any similarly-large basket would have done
about as well" (category exposure, not selection skill). A large change
points toward the specific picks mattering.

**`docs/handoffs/2026-09-03-state-of-play.md`'s own Test 5 section
contains a factual error, corrected here before this run starts.** It
describes Arm B as "the eight largest S&P names as of Jan 2021, by rule,"
states this overlaps Arm A in **five** names, and reduces to a
three-name swap (AMD/AVGO/ORCL out; AMZN/META/one more in) — implying
NVDA is one of the "top 8" and stays fixed in both arms.

Actual year-end-2020 S&P 500 market cap ranking (source: aggregated
market-cap-by-year data, cross-checked against the multiple independent
rankings for that period): Apple, Microsoft, Amazon, Alphabet, Meta
(Facebook), Tesla, Berkshire Hathaway, Visa — in that order. **NVIDIA
ranked 15th (~$323B), not top 8.** Berkshire Hathaway holds no
quarterly earnings-call transcript to score (annual shareholder
letter/meeting only, not a standard analyst call) — consistent with
`analysis/audit_top20_2021.py`'s own `EXPECTED` list, which already
excludes BRK.B and lists Johnson & Johnson as the next name in rank
(#9). This is not a new decision being made here; it is this run
following a documented exclusion the project already made elsewhere.

**Corrected Arm B, applying the actual rule (top 8 by year-end-2020
market cap, excluding BRK.B per the project's own existing convention):
AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ.** Against Arm A, this is a
**four**-name overlap (AAPL, GOOGL, MSFT, TSLA) and a **four**-name swap
(AMD, AVGO, NVDA, ORCL out; AMZN, META, V, JNJ in) — not three. Do not
"correct" this back toward the doc's original three-name framing; the
doc was wrong about the rule it invoked, not this run.

**NVDA stays in Arm A only.** Arm A is the real, already-deployed
portfolio and is not adjusted for this test — see the design-session
discussion for why excluding NVDA from Arm A as well would defeat the
purpose (it would silently swap the question being asked, from "did the
real portfolio's actual decisions add value" to "would a portfolio that
never existed have done well," and would hide rather than reveal
whether NVDA's outsized real-world return is what's actually separating
the two arms).

---

## Step −1 — resume protocol

`run_id` is **`test5-universe-substitution`**, state in
`analysis/data/run_state/<run_id>/`. Cheap, deterministic, in-memory
simulation runs (same profile as Test 1) — checkpoint after each named
simulation cell completes (Arm A reproduction, Arm B run, and — if
reached — each draw of the optional Step 5 resampling distribution).

## Step 0 — hygiene, and the premise checks this run actually needs

Clean tree, hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit. Work on
`sweep/db-corpus-baseline` (same branch Test 1 and Test 4 used). Do not
commit to `dev` or `main`.

**Before running anything else, verify by query (`SELECT` only):**

1. AMZN, META, V, and JNJ each have `Analysis` rows covering roughly
   2021 onward, joined to `Transcript`/`Ticker`, **within the same
   `analysis_created_before`/`analysis_created_after` window**
   `analysis/simulator/data.py`'s `load_call_events()` already defaults
   to (the v6-era guard against v10+auto1 contamination — see
   `docs/handoffs/2026-09-03-prompt-version-drift.md`). If any of the
   four names has rows outside that window, or has gaps that would make
   its per-quarter coverage materially thinner than the existing
   `ESTABLISHED` tickers over the same period, **stop and report** —
   do not silently proceed with a lopsided universe.
2. Confirm the `ESTABLISHED`/`SPECULATIVE` ticker-list constant is
   identical everywhere it's defined. It is copy-pasted verbatim across
   at least 15 files in `analysis/` (confirmed by grep during this
   design session) — if any copy has drifted, name which file and which
   ticker differs, and use the definition in
   `analysis/sweep_cadence_and_session_model.py` (the file Test 1's
   harness actually imports) as the source of truth for this run.

**Do not use the `run-allocator-sweep-db-corpus` pipeline or reference
figures.** That is a separate, currently-stalled effort
(`wrap-ups/run-allocator-sweep-db-corpus-out.md`: baseline did not
reproduce, $110k vs. a $287k reference, stopped at Step 1) built around
a different loader path and `sync_trend_to_db.py`'s live-recomputed
tier/trajectory fields. This run uses **Test 1's pipeline only** —
`sweep_cadence_and_session_model.load_events_dedup_on()`'s pattern
(`load_call_events` → `build_type_function`/`build_tier_function` →
`recompute_trend_layer`), which already produced a reproducible,
trusted result once. Do not conflate the two pipelines or their
reference numbers.

---

## Step 1 — reproduce Arm A before trusting Arm B

Re-run the exact settled configuration Test 1 used — **`swap_funding`
funding mode, `K=30`, `new_calls_only`, `X=2.5pp` lift-drop dead band,
pooled account mode, `per_event_date` ordering** — on the unmodified
`ESTABLISHED + SPECULATIVE` (`ALL16`) universe, uncorrupted (`q=0.0`,
same as Test 1's own hard-stop check: "q=0.0 must reproduce the
uncorrupted result exactly in every mode").

**Expected: `final_value` = $120,800** (Test 1's own zero-information
floor, `wrap-ups/analyst-sensitivity-out.md` → `cells.jsonl` →
`cell_key=="zero_info"` → `results.final_value`). **If this does not
reproduce, stop and report the discrepancy** — every downstream number
in this run is relative to it, exactly as the (stalled) operating-model
sweep's own Step 0 instruction says, and for the same reason.

Record `max_drawdown` and any other `compute_summary()` fields alongside
`final_value`, for the same-units comparison Step 3 needs.

---

## Step 2 — build Arm B's universe and run it

**Arm B established set:** AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ.
**Arm B speculative set: unchanged** — AMPX, ENVX, EOSE, FSLR, QS, RUN,
SPWR, TTD (identical to Arm A; this is the one-variable-at-a-time design
the doc specifies and this run is not revisiting that choice).

Run the identical settled configuration from Step 1 (`swap_funding`,
`K=30`, `new_calls_only`, `X=2.5pp`, pooled, `per_event_date`,
uncorrupted) against this 16-name universe. Nothing besides the
established-ticker list changes between Step 1 and Step 2 — same date
window, same cutoff guards, same allocator version (`decide_v3` /
whatever Test 1's harness actually called — confirm and report which).

If `load_call_events` returns zero or implausibly few events for any of
AMZN/META/V/JNJ despite Step 0's check passing, stop and report rather
than proceeding on a thin or empty ticker.

---

## Step 3 — the comparison

Report, side by side:

| | Arm A (real portfolio) | Arm B (rule-based top-8, no NVDA) |
|---|---|---|
| Established tickers | AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA | AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ |
| `final_value` | [$X, reproduced] | [$Y] |
| `max_drawdown` | [X%] | [Y%] |
| Other `compute_summary()` fields available | [...] | [...] |

Compute the raw dollar and percentage difference, and state plainly
which arm's tickers were more concentrated in single-name outperformance
(this requires no new analysis — it's visible from Step 1/Step 2's
event-level output: how much of each arm's return traces to one ticker's
price path versus being spread across several).

**Report whichever way it goes.** A small difference is evidence for the
"category exposure, not selection skill" reading; a large difference is
evidence the specific picks mattered — do not characterize either
outcome as validating or invalidating the analyst's process beyond what
a single point-in-time comparison can support (see Step 4).

---

## Step 4 — what a two-arm comparison can and can't tell you (report, do not decide)

State plainly, per state-of-play's own framing: this is one draw, not a
distribution. It can show whether *this specific* rule-based alternative
would have done about as well, but it cannot say whether Arm A's
performance is typical of what any similarly-constructed 8-name basket
would produce, or an outlier. Do not conclude "the analyst's selection
adds/doesn't add value" from this step alone — that claim needs Step 5.

## Step 5 — optional stronger version (gated, only if cheap)

The doc's "stronger version": sample 8 names at random from the full
top-20 (2021) universe, 20-30 times, build a distribution of
`final_value`, and see where Arm A's actual result falls (a percentile,
not a binary pass/fail).

**Gate this on data availability, checked by query before doing any
simulation work:** run `python3 analysis/audit_top20_2021.py` and report
its output. If most of the 20 names already have adequate `Analysis`
coverage back to 2021 within the same contamination-guard window Step 0
checked, this step is cheap (pure re-simulation, still $0 API spend) and
worth doing. **If several names are missing or thin, do not load new
transcripts or spend API calls to fill them in this run** — report the
gap and stop at Step 4's two-arm comparison instead. This step is
explicitly optional; the two-arm comparison in Steps 1-4 is the core
deliverable regardless.

If run: fix a seed, report it, report the full distribution's mean,
std, min, max, and where Arm A's real `final_value` falls as a
percentile. Keep the speculative 8 fixed in every draw, exactly as
Steps 1-2 do — only the established 8 are resampled each draw, drawn
from the 20-name pool (BRK.B excluded, consistent with Step 0's
established exclusion rule).

---

## Report

Scope boundary: **report, do not decide.** Do not change the live
allocator, do not amend `ALLOCATOR_OPERATING_MODEL.md`, do not write any
simulation output to the `Analysis` table (there is none to write — this
is a pure read + in-memory simulation), do not treat this run's result
as a verdict on whether to change the actual portfolio's composition.

Open with resume status, then:

> **Arm A reproduction: [$X, matches Test 1's $120,800 / DISCREPANCY —
> see report]. Arm B (AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ +
> unchanged speculative 8): final_value $[Y] ([+/-Z]% vs Arm A),
> max_drawdown [Y%] vs [X%]. Reading: [category-exposure-leaning /
> selection-matters-leaning / inconclusive at n=1]. Step 5 (resampling
> distribution): [run, Arm A at Nth percentile / not run, data gap
> reported / not run, deferred as optional]. $0 Anthropic API spend
> confirmed.**

Flag plainly: any of the four premise checks in Step 0 that didn't pass
cleanly, any drift found in the `ESTABLISHED`/`SPECULATIVE` constant
across its ~15 copies, and anything about AMZN/META/V/JNJ's data quality
that would make Arm B's number less trustworthy than Arm A's (thinner
history, different `analysis_created_at` distribution, etc.) even if the
final numbers themselves look clean.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no
  Linux package managers or path assumptions.
- **No DB writes at all.** `SELECT` only.
- Do not modify `docs/EVALUATION_PROMPT.md`, `ALLOCATOR_OPERATING_MODEL.md`,
  or any file under `analysis/simulator/`.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure quoted must name its provenance - file, manifest path,
  JSON key, or table/column.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
