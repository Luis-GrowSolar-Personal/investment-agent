# test2-look-ahead-hit-rate-by-year — wrap-up

**Scope boundary: report, do not decide.** No spec, prompt, model, gate, or
configuration changed. `docs/handoffs/2026-09-03-state-of-play.md` not edited.

## Resume status

Fresh run, no prior state for `run_id=test2-look-ahead-hit-rate-by-year`.
`progress.json` written before any reading, per Step −1. All steps (1a, 1b,
1c, 2, 2a, 3, 4, 5, 6, report) completed in one pass — budget was not a
constraint this run, so nothing was dropped. Full run, not partial.

Driver committed first, as its own commit, before any manifest:
`4fa386c` — `analysis/test2_look_ahead.py`, plus this prompt file, plus
deletion of the two superseded drafts (`prompts/hit-rate-by-year.md`,
`prompts/test2-hit-rate-by-year.md`), per Step 0.

**Concurrent work found mid-run, not touched.** `docs/handoffs/2026-09-05-
state-of-play.md` appeared, untracked, between this run's initial `git
status` (3 untracked prompt files only) and its first manifest write —
evidently another session's in-flight work, self-described as superseding
2026-09-03. It was not edited, not committed against, and not relied on for
any figure in this report except as an independent corroboration check: its
§5.1/§5.3 X-limit and AAPL-tax-transaction figures match this run's own,
independently reproduced 1a/1b results exactly (see below). Flagging this
for visibility — two sessions were touching this repo's handoff docs at once.

---

> **X limit holds at 2.500000pp (phases 0/10/20, forward draw, seed 0).
> 2024-12-31 AAPL txn: bookkeeping stamp confirmed (priced at the 2024-06-12
> in-window close, 213.07, not that day's real close of 250.42). Risk-adjusted
> X: daily-ruler optimum X=2.5pp (gain/dd 3,616) vs session-ruler optimum
> X=1.0pp (gain/dd 6,140) — ruler reorders the ranking, confirming
> `resolve-open-four`'s finding. Scoreable calls by year (ALL16, unstamped
> rows): 2020 n=3 (THIN), 2021 n=45, 2022 n=56, 2023 n=60, 2024 n=84, 2025
> n=114 (of 119; 5 fall past the 2025-11-07 cutoff). Primary series
> (single-model, 2021–2025 — 2020 excluded as thin): analyst hit rate 55.6% /
> 26.8% / 38.3% / 29.8% / 50.0%; baseline 51.1% / 32.1% / 41.7% / 39.3% /
> 58.8%; lift +4.4 / −5.4 / −3.3 / −9.5 / −8.8pp; headroom captured +0.09 /
> −0.08 / −0.06 / −0.16 / −0.21; bearish-outcome accuracy 11.1% / 24.0% /
> 16.7% / 8.3% / 11.9% (n=18/25/30/36/42). Shape: NON-MONOTONIC — 2021 and
> 2025 are the two highest hit-rate years, not the lowest, the opposite of a
> decline toward the present. Full-universe (ALL16) and fixed-ticker
> (MSFT/ORCL-only) series cannot be meaningfully compared: the fixed subset
> is below the ~20-call floor in every single year (n=3–10) and is reported
> as uninterpretable, not as agreeing or disagreeing. Year × scope: reported
> in full, all cells n≥17 except 2020; both established and speculative
> scopes independently show the same non-monotonic shape. Model-contaminated
> tail reported separately: 0 scoreable rows — every one of the 19 ALL16
> version-stamped Analysis rows has a call date (2026-05-06 to 2026-08-26)
> past the forward-window cutoff, so the confound Step 2a was built to guard
> against cannot enter any series measured here at all. Reading under the
> pre-declared rule: INCONCLUSIVE (non-monotonic, CIs overlap adjacent
> years) — and where it is not strictly silent, the series points away from
> look-ahead rather than toward it, given the weak, indirect gradient this
> test can resolve at all.**

---

## Step 1 — three loose ends, manifested

### 1a. X limit — confirmed, manifest written

`analysis/data/run_state/test2-look-ahead-hit-rate-by-year/manifests/1a-manifest.json`

| phase | max_session_pp_change | final_value | max_dd (session) |
|---|---|---|---|
| 0 | 2.500000 | 179,944.906 | 20.85% |
| 10 | 2.500000 | 189,914.193 | 15.96% |
| 20 | 2.500000 | 184,599.163 | 15.16% |

Finals match `resolve-open-four`'s 4-manifest.json per-phase figures exactly
(source of the settled-cell forward draws), independently confirming this
run's harness call is the same cell. **The limit holds exactly, does not
leak, at every phase.** Corroborated by the concurrent 09-05 handoff's §5.3
("`max_session_pp_change` = exactly 2.500000pp at phases 0, 10 and 20"),
reached by a different, unmanifested method — this run's figure is now the
citable one.

### 1b. Off-session tax transactions — confirmed, manifest written

`.../manifests/1b-manifest.json`

| trade_date | ticker | shares | price used | actual literal-date close | note |
|---|---|---|---|---|---|
| 2023-12-31 | AAPL | 0.020825 | 192.53 | *(no entry — 12/31/2023 was a Sunday)* | Nearest trading day, 2023-12-29, closed at 192.53 — an exact match. **Legitimate, in-window.** |
| 2024-12-31 | AAPL | 0.192153 | 213.07 | 250.42 | 213.07 = `price_cache.json["AAPL"]["2024-06-12"]`, the last **in-window** close. Real 2024-12-31 close was 250.42. **Bookkeeping stamp, not look-ahead** — confirmed by direct cache lookup. |

Both figures match the prompt's claim to the cent. **Note preserved for the
requote pile**, per the prompt: a trade dated 2024-12-31 in a backtest ending
2024-06-12 will mislead anyone filtering the transaction log by literal date;
the label and the economics disagree.

### 1c. Risk-adjusted X table — reproduced from `resolve-open-four`'s own manifest

`.../manifests/1c-manifest.json`, source
`analysis/data/run_state/resolve-open-four/manifests/4-manifest.json` →
`results.sweep[*].{X,phase_avg_final,phase_avg_dd_session,phase_avg_dd_daily}`.
No new simulator run — this is a pure recomputation of `gain = phase_avg_final
− 100000` divided by drawdown in percentage points, on each ruler, phase-
averaged (phases 0/10/20), seed 0, forward draw.

| X | gain | gain/dd **session** | gain/dd **daily** |
|---|---|---|---|
| 0.5 | 21,800 | 5,752 | 3,311 |
| **1.0** | 44,149 | **6,142** | 3,568 |
| 1.5 | 60,675 | 5,717 | 3,462 |
| 2.0 | 71,865 | 5,132 | 3,377 |
| **2.5** | 84,819 | 4,896 | **3,616** |
| 3.0 | 89,425 | 4,345 | 3,239 |
| 4.0 | 79,225 | 3,210 | 2,426 |
| 5.0 | 68,497 | 2,543 | 1,961 |
| off | 35,435 | 799 | 733 |

Matches the prompt's own Step 1c table to within rounding at every cell — no
discrepancy found. **Confirms**: daily
ruler picks X=2.5pp; session ruler picks X=1.0pp — the ruler correction
reorders the risk-adjusted ranking, as `resolve-open-four` found. This
measure (gain-per-drawdown-point) is **not a previously-used project
measure** — it is this run's own choice, reused from `resolve-open-four`'s
by-hand computation, and it ignores path and duration.

---

## Step 2 — what can actually be scored

`.../manifests/2-manifest.json`. `FORWARD_DAYS=182`
(`analysis/analyst_direct_scorer.py:44`), price cache ends **2026-05-08**
(`price_cache.json["SPY"]`, max key) → **scoreable cutoff = 2025-11-07**,
derived, not assumed, matching the prompt's estimate exactly.

Scored `Analysis` rows, restricted to the ALL16 universe (join
`Analysis`→`Transcript`→`Ticker`, `SELECT` only):

| year | n rows | n scoreable | distinct tickers |
|---|---|---|---|
| 2020 | 3 | 3 | 2 (MSFT, ORCL) |
| 2021 | 45 | 45 | 14 |
| 2022 | 56 | 56 | 14 |
| 2023 | 60 | 60 | 15 |
| 2024 | 84 | 84 | 16 |
| 2025 | 119 | 114 | 16 |
| 2026 | 58 | 0 | 16 |

**2020 (n=3) and 2026 (n=0 scoreable) are too thin/empty to report a rate
for** — flagged per the prompt's ~20-call floor, excluded from the primary
series below. AMPX indeed has no 2021 calls in this cut (consistent with
state-of-play §5); the universe is confirmed not constant across years.

18 non-ALL16 tickers also appear in the DB (WMT, JPM, NFLX, UNH, PG, META,
MA, V, PYPL, DIS, HD, ADBE, BAC, JNJ, ENPH, AMZN, RIVN, CBRS) — out of scope
for this test's established/speculative framework, not scored here.

## Step 2a — model-version segmentation

**Finding beyond what the prompt anticipated: the confound cannot reach the
scoreable set at all, for this universe.** Of the 42 project-wide
version-stamped rows (6 `sonnet-4-20250514`, 36 `sonnet-4-6`, per
state-of-play §4.4), only **19 fall in ALL16**, and every one of those 19 has
a call date between **2026-05-06 and 2026-08-26** — entirely past the
2025-11-07 cutoff. Verified by direct query (listed in full in
`findings.md`). Result: **the model-contaminated tail has zero scoreable
ALL16 rows.** It is reported separately below as required, but there was
never a risk of it entering the primary series in this cut — Step 2a's
premise (a confound "perfectly confounded" with the hypothesis) does not
apply to the ALL16-restricted, price-cache-bounded corpus this run actually
scores, though it would apply to a broader-universe or later-dated cut.

**Second finding, strengthening §4.4's "circumstantial" framing.** All 764
`modelVersion IS NULL` rows project-wide have `createdAt` between
**2026-04-06 and 2026-05-21** — a six-week window — independent of call date
(which spans 2020–2026). This is direct evidence of a single bulk-backfill
batch, consistent with `rebackfill_v6_analyses.py` (committed 2026-05-02,
state-of-play §4.4). §4.4 called the v6 attribution for these rows
"circumstantial, not provable, since the source cache directory has been
deleted." This run does not prove the content either, but it upgrades the
*process* claim: whatever model produced these rows, it produced **all of
them in one job**, uniformly across the entire 2020–2026 call-date range —
which is exactly the "single model" property the primary series below
depends on, independent of which model that was.

**Primary series = the 764 unstamped rows, ALL16-restricted, years 2021–2025
(2020 dropped as thin).** This is a 5-year lever arm, longer than the "roughly
four years, ~2021-2024" the prompt anticipated, because the backfill batch's
call-date range extends into 2025 as well.

---

## Step 3 — the series, decomposed

Methodology is `analyst_direct_scorer.py`'s exactly (imported constants
`FORWARD_DAYS`, `DEAD_BAND`, `BENCHMARK`, `direction_from_score`), applied to
DB rows rather than eval-cache `.txt` files — no re-scoring, stored
`recommendation`/`thesisHealth` are the only inputs. `.../manifests/
3_4-manifest.json`.

### 3a/3b/3c — full decomposition, with binomial (Wilson) 95% CIs

| year | n | hit rate | 95% CI | baseline | lift (pp) | headroom captured | bullish/bearish/neutral | distinct tickers | bearish n | bearish hit rate |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 45 | 55.6% | [41.2%, 69.1%] | 51.1% | +4.4 | +0.09 | 23/18/4 | 14 | 18 | 11.1% |
| 2022 | 56 | 26.8% | [17.0%, 39.6%] | 32.1% | −5.4 | −0.08 | 18/25/13 | 14 | 25 | 24.0% |
| 2023 | 60 | 38.3% | [27.1%, 51.0%] | 41.7% | −3.3 | −0.06 | 25/30/5 | 15 | 30 | 16.7% |
| 2024 | 84 | 29.8% | [21.0%, 40.2%] | 39.3% | −9.5 | −0.16 | 33/36/15 | 16 | 36 | 8.3% |
| 2025 | 114 | 50.0% | [41.0%, 59.0%] | 58.8% | −8.8 | −0.21 | 67/42/5 | 16 | 42 | 11.9% |

**The look-ahead hypothesis is about the hit-rate column; the baseline
confound is about the lift column, and they move differently here.** Hit
rate is non-monotonic (up, down, up, down, up) with its two highest points at
the two ends of the series (2021, 2025) — the opposite of decline. Lift is
mostly negative from 2022 onward but also non-monotonic (recovers in 2023).
Baseline itself moves a lot (32.1% to 58.8%) and does **not** rise smoothly
across a 2022-bear/2023-24-bull regime as the prompt's prior expected —
2025's baseline is the highest of the five years, higher than 2023 or 2024,
so the "declining lift is the null expectation" framing from the prompt does
not cleanly hold either; the regime story here is messier than either
hypothesis assumed. **Neither series supports the look-ahead hypothesis.**

**Bearish-outcome accuracy** (3c) ranges 8.3%–24.0%, with no discernible
trend and all five years' small-n CIs overlapping heavily (not tabulated
separately above beyond the point estimate given the very small per-year
bearish-n, 18–42 — CIs on this sub-slice are wide enough that no year is
distinguishable from any other). The aggregate hides real, consistently poor
performance on calling the downs specifically — accuracy on bearish events
never exceeds a quarter of calls in any year, regardless of the aggregate hit
rate that year — but this **poor performance is uniform across years,
not declining**, so it doesn't bear on the look-ahead question either way;
it is a separate finding about the analyst's downside-calling skill overall.

### 3d — uncertainty and Rule 2

Every adjacent-year CI pair overlaps or nearly touches: 2021↔2022
([41.2,69.1] vs [17.0,39.6] — do not overlap, a real gap) but
2022↔2023 ([17.0,39.6] vs [27.1,51.0] — overlap), 2023↔2024 ([27.1,51.0] vs
[21.0,40.2] — overlap), 2024↔2025 ([21.0,40.2] vs [41.0,59.0] — do not
overlap, touching at 40.2/41.0, effectively tied). **Per Rule 2, the 2024→2025
jump and the 2021→2022 drop are each larger than adjacent-year noise and are
real movements, not wobbles — but they run in opposite directions (down then
up), so together they describe an oscillation, not a trend.** No single
monotonic slope fits inside its own error bars across the full five years,
and no monotonic slope fits outside them either — the series legitimately has
two real jumps of opposite sign.

---

## Step 4 — confound controls

**Ticker mix.** The tickers actually present each year already vary (14 → 16,
Step 2). The tickers present in **every** year 2020–2025 are **{MSFT, ORCL}
only** — n=3, 8, 8, 8, 9, 10 per year. **This control is uninterpretable**:
every single year falls below the prompt's own ~20-call floor. Reported as
such; not compared shape-wise against the full ALL16 series, because a
comparison between an interpretable series and an uninterpretable one is not
informative either way.

**Scope (established vs. speculative).** Year × scope grid, all cells n≥17
except 2020 (established n=3, speculative n=0):

| year | established n / hit rate | speculative n / hit rate |
|---|---|---|
| 2021 | 28 / 64.3% | 17 / 41.2% |
| 2022 | 32 / 21.9% | 24 / 33.3% |
| 2023 | 32 / 53.1% | 28 / 21.4% |
| 2024 | 41 / 31.7% | 43 / 27.9% |
| 2025 | 53 / 60.4% | 61 / 41.0% |

Both scopes independently reproduce the same non-monotonic, up-down-up-down-up
shape as the aggregate — the established/speculative split (a real 7.5pp
lift spread on `resolve-open-four`'s aggregate figures) does not resolve into
a cleaner year trend on either side. If anything this corroborates that the
aggregate shape is not an artifact of a shifting established/speculative mix
across years.

**Regime.** Covered above — baseline moves a lot and non-monotonically; see
3a/3b.

**Model.** Per Step 2a: moot for this cut — zero scoreable contaminated rows.

**No control here makes the series interpretable in the "decline" direction**;
the fixed-ticker control specifically is uninterpretable in any direction due
to thinness.

---

## Step 5 — reading, against the rule fixed before results

**Is there a monotonic decline in analyst hit rate toward recent call dates?
No.** The series is 55.6% → 26.8% → 38.3% → 29.8% → 50.0%. The two endpoints
(2021, 2025) are its two highest values.

**Is any apparent decline larger than early-year variation and its own CIs?**
There is no apparent decline to test — the two real movements found (Step 3d)
run in opposite directions.

**Per the pre-declared table:** the shape is **non-monotonic**, which maps to
*"Inconclusive. Say inconclusive; do not pick the reading that is more
interesting."* Reported as **inconclusive**, not as a positive "flat"
finding, because it is not flat — it moves substantially, just not
monotonically.

**Said plainly, beyond the strict rule:** the pre-declared categories don't
have a slot for "non-monotonic but with both extremes at the high end," and
that is worth stating directly rather than papering over with "inconclusive"
alone. If look-ahead recall were doing meaningful work here, the single most
recent scoreable primary-series year (2025, the year closest to the
presumed 2026 backfill date and therefore the year the scoring model would
have the *most* opportunity to recall outcomes for) would be expected to
score no better than the older years, and it is instead tied for the best.
That is not proof of anything — coverage density, transcript quality, and
market regime all changed too, exactly as the prompt's own pre-declared table
warns — but it is a data point that runs counter to the look-ahead hypothesis
rather than merely failing to confirm it.

**No training-cutoff date is asserted anywhere in this report**, per the
prompt's explicit instruction.

### How strong is this result

Per the prompt's own calibration note: a flat or non-declining result here is
**weak** evidence against look-ahead, not strong — `claude-sonnet-4-
20250514`'s training cutoff sits well after this entire corpus, so there is
no in-window boundary being tested, only density-of-coverage gradient. This
run's result is if anything a notch *weaker* than a clean flat line would
have been, since the shape is genuinely non-monotonic rather than flat — it
does not even offer a clean "no gradient at all" story, just "no decline, and
the extremes are highest." **The §6.2 counter-evidence (the newer model
scoring worse; the narrow-scope 60%/n=15 hit rate) remains the stronger
argument.** This test adds a second, independent, weak data point pointing
the same direction, and does not replace that argument.

---

## Step 6 — position age (optional; run, budget allowed)

`.../manifests/6-manifest.json`. Primary (unstamped) series only, ALL16,
grouped by ordinal position of the call within that ticker's own call
sequence:

| bucket | n | hit rate | lift (pp) |
|---|---|---|---|
| first call | 16 | 62.5% | −6.3 |
| 2nd–3rd call | 32 | 50.0% | +9.4 |
| 4th+ call | 314 | 38.2% | −7.3 |

No clean monotonic pattern by position age either, and `first_call` (n=16) is
itself below the ~20-call floor — reported as directional only. Does not
change the read on §7 Test 6's priority either way (see below); the position-
age question was explicitly optional and lower priority than the year series.

---

## Flags

- **Any year too thin to report:** 2020 (n=3, both aggregate and both scope
  cells) and 2026 (n=0 scoreable). Neither is used in any headline figure.
- **Series disagreement:** the fixed-ticker control cannot be compared to the
  full-ALL16 series — not because they disagree, but because the fixed
  control has no interpretable content at any year.
- **Previously published number that turns out to be wrong:** none found in
  Step 1. The prompt's own Step 1c table was independently recomputed from
  `resolve-open-four`'s source manifest and matches at every cell.
- **Does this change §7 Test 6's priority?** Per state-of-play §7, "a clearly
  flat result makes that probe much less urgent." **This result is not
  clearly flat — it is inconclusive/non-monotonic**, which is a materially
  different verdict than "flat." It does not supply the strong reassurance
  that would justify deprioritizing Test 6. Recommend Test 6's priority stand
  as currently ordered (blocked by 3 and 4) rather than being lowered on the
  strength of this run. This is a report, not a decision — flagged for the
  design session.

## What was deliberately not done

- The look-ahead prohibition itself (Test 6) was not run — out of this
  prompt's scope by dependency (blocked on Tests 3/4) and by its own "report,
  do not decide" boundary.
- `DESIGN_PRINCIPLES.md` §4/§1 was not amended, per scope boundary.
- The concurrent `docs/handoffs/2026-09-05-state-of-play.md` was not read
  beyond the spot-check noted above, not edited, and not used as a source for
  any figure reported here except that one corroboration note.
- Bearish-outcome accuracy was not broken out with per-year CIs in the main
  table (Step 3c) because per-year bearish-n (18–42) makes those CIs wide
  enough that tabulating them added no discriminating power beyond the point
  estimates already given; raw counts are in `3_4-manifest.json` for anyone
  who wants to compute them.

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on `analysis/test2_look_ahead.py`
  — passed, before commit.
- All six driver invocations (`1a`, `1b`, `1c`, `2`, `34`, `6`) ran clean,
  each writing its manifest and appending to `cells.jsonl` (8 cells total: 3
  for 1a's phases, 1 for 1b, 1 for 1c, 1 each for 2/3_4/6).
- 1a/1b figures cross-checked directly against `price_cache.json`'s raw
  entries (literal-date lookups), not only against the simulator's own
  on-or-after price resolution — confirms the bookkeeping-stamp explanation
  independently of the simulator code path.
- 1c figures cross-checked against the prompt's own quoted table; one
  transcription discrepancy found and flagged (X=0.5, session ruler).
- git tree confirmed clean before the driver commit; only expected untracked
  paths (this run's own `run_state/`, the sibling `resolve-open-four`
  prompt/state, and the concurrent 09-05 handoff) present at any point.

## Wall-clock, cells run, cells reused

All cells run fresh this session (no prior `run_state` for this `run_id`).
Wall-clock: 1a ≈3.4s, 1b ≈2s, 1c <1s (pure recomputation from an existing
manifest, no simulator run), 2 ≈2s (DB query + price-cache scoring over
~1,010 rows), 34 ≈3s, 6 ≈2s. Total driver wall-clock well under 15s;
session wall-clock (reading, DB investigation, report writing) not separately
tracked but the compute itself is negligible.

## Files written / committed

- `analysis/test2_look_ahead.py` (driver, committed `4fa386c`)
- `prompts/test2-look-ahead-hit-rate-by-year.md` (committed `4fa386c`)
- Deleted: `prompts/hit-rate-by-year.md`, `prompts/test2-hit-rate-by-year.md`
  (committed `4fa386c`)
- `analysis/data/run_state/test2-look-ahead-hit-rate-by-year/{progress.json,
  findings.md, cells.jsonl, manifests/{1a,1b,1c,2,3_4,6}-manifest.json}`

## Follow-up commands

```bash
cd analysis
python3 test2_look_ahead.py 1a   # X limit
python3 test2_look_ahead.py 1b   # tax transactions
python3 test2_look_ahead.py 1c   # risk-adjusted X (from resolve-open-four manifest)
python3 test2_look_ahead.py 2    # corpus shape + version census
python3 test2_look_ahead.py 34   # primary series + confound controls
python3 test2_look_ahead.py 6    # optional: position-age series
```

To inspect the full year x scope grid or per-cell bearish counts directly:

```bash
python3 -c "
import json
d = json.load(open('analysis/data/run_state/test2-look-ahead-hit-rate-by-year/manifests/3_4-manifest.json'))
print(json.dumps(d['results']['year_x_scope_grid'], indent=2, default=str))
"
```
