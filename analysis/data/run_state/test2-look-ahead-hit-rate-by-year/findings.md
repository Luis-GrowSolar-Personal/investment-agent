# Findings — test2-look-ahead-hit-rate-by-year

(append-only; each entry timestamped by step)

## Step 1a — X limit
`max_session_pp_change` = exactly 2.500000pp at phases 0, 10, 20 (1a-manifest.json).
X limit holds, does not leak. Confirms the prompt's claim independently (also
independently corroborated by a concurrent, uncommitted 2026-09-05 handoff doc
found mid-run — see note below).

## Step 1b — tax transactions
Both AAPL forced-liquidation-for-tax transactions confirmed exactly as claimed:
2023-12-31 sale at 192.53 (= 2023-12-29 close, the last trading day of that
year; 12-31 fell on a Sunday) — legitimate. 2024-12-31 sale at 213.07 = the
2024-06-12 close (last in-window trading day), NOT that day's real close of
250.42 — a bookkeeping stamp, confirmed (1b-manifest.json).

## Step 1c — risk-adjusted X reproduced
Recomputed gain/dd from resolve-open-four's own 4-manifest.json (no new sim
run). Session-ruler optimum X=1.0 (gain/dd 6140), daily-ruler optimum X=2.5
(gain/dd 3616). Ruler reorders the ranking — confirmed (1c-manifest.json).

## Step 2 — corpus shape
Scoreable cutoff = 2025-11-07 (price cache ends 2026-05-08, FORWARD_DAYS=182).
ALL16-restricted year counts: 2020 n=3 (THIN), 2021 n=45, 2022 n=56, 2023 n=60,
2024 n=84, 2025 n=119 (114 scoreable, 5 fall after cutoff), 2026 n=58 (0
scoreable). 2020 and 2026 flagged thin/unscoreable per the prompt's ~20-call
floor.

## Step 2a — model-version confound is MOOT for this test, not merely controlled
Of the 42 version-stamped Analysis rows project-wide, only 19 fall in ALL16 —
and all 19 have call dates 2026-05-06 through 2026-08-26, entirely past the
2025-11-07 scoreable cutoff. The "model-contaminated tail" is therefore
**zero scoreable rows** within ALL16 — not merely reported separately, it
literally cannot enter any hit-rate series. This is stronger than the prompt
anticipated (it worried the confound could dwarf a real signal; here it simply
doesn't reach the scoreable set at all).

Separately verified: all 764 model_version-NULL ("presumed v6") rows have
`createdAt` between 2026-04-06 and 2026-05-21 — a six-week window — regardless
of call date (which spans 2020-2026). This is direct evidence for a single
bulk backfill batch (matches `rebackfill_v6_analyses.py`, committed 2026-05-02
per state-of-play §4.4), which upgrades §4.4's "circumstantial, not provable"
single-model claim for the unstamped rows to something closer to provable:
one batch job, one model, uniform across the whole call-date range.

## Step 3/4 — primary series (2021-2025, ALL16, unstamped rows only)
| year | n | hit rate | 95% CI | baseline | lift pp | headroom | bearish n | bearish hit |
|---|---|---|---|---|---|---|---|---|
| 2021 | 45 | 0.556 | [0.412,0.691] | 0.511 | +4.44 | 0.091 | 18 | 0.111 |
| 2022 | 56 | 0.268 | [0.170,0.396] | 0.321 | -5.36 | -0.079 | 25 | 0.240 |
| 2023 | 60 | 0.383 | [0.271,0.510] | 0.417 | -3.33 | -0.057 | 30 | 0.167 |
| 2024 | 84 | 0.298 | [0.210,0.402] | 0.393 | -9.52 | -0.157 | 36 | 0.083 |
| 2025 | 114| 0.500 | [0.410,0.590] | 0.588 | -8.77 | -0.213 | 42 | 0.119 |

Non-monotonic: 2021 and 2025 are the two HIGHEST hit-rate years, not the
lowest — the opposite of what look-ahead predicts. All adjacent-year CIs
overlap or nearly touch. Baseline is not monotonically rising either (lowest
in 2022, a bear year, as expected, but 2025's baseline is the highest of all
five years).

Fixed-ticker subset present in every year 2020-2025 = {MSFT, ORCL} only, n=3
to n=10 per year — below the ~20-call floor in every single year. This control
is uninterpretable due to thinness, reported as such, not compared shape-wise
to the full ALL16 series.

Year x scope grid: all cells n>=17 except 2020 (thin, established n=3,
speculative n=0). Established hit rate: 2021 0.643 (n=28), 2022 0.219 (n=32),
2023 0.531 (n=32), 2024 0.317 (n=41), 2025 0.604 (n=53). Speculative hit rate:
2021 0.412 (n=17), 2022 0.333 (n=24), 2023 0.214 (n=28), 2024 0.279 (n=43),
2025 0.410 (n=61). Both scopes show the same non-monotonic up-down-up-down-up
shape as the aggregate. Full per-cell figures in 3_4-manifest.json ->
results.year_x_scope_grid.

## Step 6 — position age (optional, run; primary series only)
first_call n=16 hit=0.625 lift=-6.25; 2nd-3rd n=32 hit=0.500 lift=+9.38;
4th+ n=314 hit=0.382 lift=-7.32. No clean monotonic pattern by position age
either; first-call n is thin (16).

## Note — concurrent session
`docs/handoffs/2026-09-05-state-of-play.md` appeared, untracked, mid-run
(not present at Step 0's git-status check, present by Step 1). It is another
session's in-flight work, superseding 2026-09-03 per its own header. Not
read for reliance beyond a corroboration spot-check (its §5.1/§5.3 figures
for the X limit and AAPL tax transactions match this run's independently
reproduced 1a/1b figures exactly); not edited, not committed against.
