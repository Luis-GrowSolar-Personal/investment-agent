# test5-universe-substitution — wrap-up

**Scope boundary: report, do not decide.** No change to the live allocator,
`ALLOCATOR_OPERATING_MODEL.md`, or any file under `analysis/simulator/`. No
`Analysis` rows written (none exist to write — pure read + in-memory
simulation). This run's result is not a verdict on the actual portfolio's
composition.

## Resume status

Fresh run, no prior `run_state` for `run_id=test5-universe-substitution`.
Steps 0, 1, 2, 3, 4, and the optional Step 5 all ran to completion this
session. **This is a full run, not partial.**

---

> **Arm A reproduction: $179,944.91 / 20.85% dd — matches the corrected
> reference exactly (not the prompt's cited $120,800 — see Flag 1 below).
> Arm B (AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ + unchanged speculative
> 8): final_value $119,134.95 (−33.79% vs Arm A), max_drawdown 19.93% vs
> 20.85% (−0.92pp). Reading: selection-matters-leaning — Arm A is
> substantially more concentrated in single-name/single-sector
> outperformance (semiconductors: NVDA+AVGO+ORCL+AMD = 68% of final value)
> than Arm B (top holding 17.4%, no semiconductor names). Step 5 (resampling
> distribution, 25 draws, seed 20260906, from the top-20-2021 pool): Arm A's
> real $179,944.91 falls at the 100th percentile — above every one of the 25
> random draws (range $107,344–$158,347) — but this comparison is weakened
> by Arm A's own established set including AMD/AVGO/ORCL, none of which are
> in the top-20-2021 pool being resampled (see caveat in §5). $0 Anthropic
> API spend confirmed — pure re-simulation over already-scored `Analysis`
> rows, no LLM calls, no DB writes.**

---

## Flag 1 (load-bearing) — the prompt's Step 1 "expected $120,800" is the wrong reference figure

The prompt says to run "uncorrupted (q=0.0)" and expect **$120,800** ("Test
1's own zero-information floor," citing `cells.jsonl` → `cell_key=="zero_info"`).
Verified directly against `analysis/data/run_state/analyst-sensitivity/cells.jsonl`:

| Cell | `final_value` | `max_dd` | What it actually is |
|---|---|---|---|
| `cell_key=="zero_info"` | $120,799.82 | 12.72% | Every recommendation force-set to Hold/Intact, size=None — **deliberately zero information** |
| `cell_key=="<mode>_q0.0"` (any mode) | **$179,944.91** | **20.85%** | Real recommendations, q=0 = **no corruption applied** — this is what "uncorrupted" means in Test 1's own gate text and in state-of-play §5.2 |

These are two different, deliberately different cells in Test 1's own
design. The prompt's Step 1 quotes Test 1's own hard-stop gate language
("q=0.0 must reproduce the uncorrupted result exactly in every mode") —
that gate is about the **second** row, not the first. $120,800 is the
answer to "what if the analyst knew nothing at all," not "what does the
real, uncorrupted analyst's settled-config backtest produce" — and Arm A
is explicitly framed by this same prompt as "the real, already-deployed
portfolio," which has real recommendations, not zero information.

**Used $179,944.91 / 20.85% as Arm A's reproduction target.** It reproduced
exactly (to the cent): `analysis/data/run_state/test5-universe-substitution/cells.jsonl`
→ `cell_key=="arm_a"` → `results.final_value` = `179944.90608455567`,
`results.max_dd` = `0.20852310359539084`.

## Flag 2 (load-bearing) — the named "ESTABLISHED/SPECULATIVE source of truth" file defines no such constant; tier is computed live, and AMD doesn't match its own label

The prompt's premise check #2 asks to verify the `ESTABLISHED`/`SPECULATIVE`
ticker-list constant is identical across its ~15 copies and use
`analysis/sweep_cadence_and_session_model.py`'s definition as source of
truth. **That file defines no such constant.** It has only `ALL16` (a flat
16-ticker list with no established/speculative split) and a `tier_fn`
(`trend_analyst.build_tier_function()`) that computes each ticker's tier
**live, per-ticker, from cached market cap / trailing P/E / trailing
volatility** — 2 of 3 axes firing → `"speculative"` — independent of any
hand-curated list.

The 7 other files' `ESTABLISHED = [AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA]`
constant is **not drifted** — verified programmatically (`grep` across all
`analysis/*.py`), all 7 copies identical, all 8 `SPECULATIVE` copies
identical. It's simply not what this pipeline's tier logic reads.

**More consequential finding, pre-existing, not caused by this run**:
computing `tier_fn` against the live caches —

```
AAPL established   AMD speculative    AVGO established  GOOGL established
MSFT established   NVDA established  ORCL established   TSLA established
AMZN established   META established  V established      JNJ established
```

— shows **AMD classifies as `speculative`** (trailing P/E 133.3 > 50
threshold, trailing volatility 62.8% > 50% threshold; its $567B market cap
alone doesn't save it — 2 of 3 axes fire), not established, despite being
one of Arm A's nominal "established eight" everywhere in this project's
docs and prompts. Every other established name in both arms computes as
established. **This means Arm A's real settled-config result has been
running AMD at the speculative Type-A cap, the speculative starter-position
size, and the faster (1-quarter, not 2-quarter) trend-layer upgrade rule —
not the established-tier behavior its label implies — in every prior sweep
on this branch, not introduced by this run.** Reported here, not corrected:
correcting it would mean adjusting Arm A, which the prompt explicitly
forbids ("Arm A is the real, already-deployed portfolio and is not adjusted
for this test").

**Effect on the Arm A/B comparison**: Arm B's eight established names are
unanimously `tier=established`; Arm A's are 7 established + 1
(AMD) speculative. This is a small confound on Arm A's side, worth knowing
when reading the comparison, not large enough to change its direction.

## Premise checks (Step 0), the ones that passed cleanly

1. **AMZN/META/V/JNJ Analysis coverage**, same `analysis_created_before`/
   `analysis_created_after` window `load_call_events()` defaults to
   (`2026-05-02 12:33:23-04` / `2026-06-27 16:26:16-04`):

   | Ticker | n (in-window) | Earliest | Latest |
   |---|---|---|---|
   | AMZN | 21 | 2021-04-29 | 2026-04-29 |
   | META | 22 | 2021-01-27 | 2026-04-29 |
   | V | 22 | 2021-01-28 | 2026-04-28 |
   | JNJ | 21 | 2021-04-20 | 2026-04-14 |

   Comparable to (in most cases denser than) the existing established
   tickers over the same window (AAPL 15, AMD 16, GOOGL 15, TSLA 14). **No
   gap, no thin coverage** — clean pass, no stop needed.
2. **ESTABLISHED/SPECULATIVE constant drift** — see Flag 2. No drift across
   the 7/8 copies that exist; the named source-of-truth file just doesn't
   define the constant the check assumed it would.

## Step 1 — Arm A reproduction

`analysis/test5_universe_substitution.py step1`. Universe: `AAPL, AMD, AVGO,
GOOGL, MSFT, NVDA, ORCL, TSLA` (established) + `AMPX, ENVX, EOSE, FSLR, QS,
RUN, SPWR, TTD` (speculative, unchanged in both arms). Settled config:
`swap_funding`, `K=30` (`cadence="30"`), `new_calls_only`, `X=2.5pp`
(`limit_pp=2.5`), `pooled`, `per_event_date`, `veto_p=0.0`. `n_events=195`,
`tie_seed=0`, no corruption applied.

**Result: `final_value=$179,944.91`, `max_dd=20.8523%`** — exact match to
the corrected reference (Flag 1), confirmed to the cent.
`distinct_tickers=15` (SPWR's single in-window event, identical in both
arms — see below — never results in a held end-of-window position; not an
Arm-B-specific artifact).

## Step 2 — Arm B run

`analysis/test5_universe_substitution.py step2`. Identical settled config.
Universe: `AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ` (established) +
same unchanged speculative 8. `n_events=193` (close to Arm A's 195 — no
"implausibly few events" gate trip for any of the four new names;
per-ticker in-window event counts: AMZN 13, META 14, V 14, JNJ 13, all
consistent with Step 0's coverage check).

**Result: `final_value=$119,134.95`, `max_dd=19.9297%`**, `distinct_tickers=15`
(same SPWR quirk as Arm A — SPWR has only 1 in-window event under the
`load_call_events()` cutoff, so it never carries an end-of-window position
in either arm; a pre-existing property of the speculative-8 corpus,
unrelated to the established-list substitution this test is measuring).

## Step 3 — the comparison

| | Arm A (real portfolio) | Arm B (rule-based top-8, no NVDA) |
|---|---|---|
| Established tickers | AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA | AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ |
| `final_value` | **$179,944.91** | **$119,134.95** |
| `max_drawdown` | **20.85%** | **19.93%** |
| `distinct_tickers` | 15 | 15 |
| `n_events` | 195 | 193 |

**Raw difference: −$60,809.96 (−33.79%) final value; −0.92pp max drawdown**
(Arm B has slightly *lower* risk as well as lower return).

**Concentration (final-day position value as % of `final_value`,** via each
arm's `portfolio` object at the last daily snapshot, priced at that day's
cache price):

| Arm A | % | Arm B | % |
|---|---|---|---|
| NVDA | 24.0% | TTD | 17.4% |
| AVGO | 20.3% | V | 17.2% |
| ORCL | 16.2% | FSLR | 12.2% |
| TTD | 13.1% | MSFT | 11.9% |
| AMD | 7.7% | META | 9.3% |
| (rest, 10 tickers) | 18.7% | (rest, 10 tickers) | 32.0% |

**Arm A's top 3 (all three semiconductor names) = 60.5% of final value;
adding AMD (also semiconductor) = 68%. Arm B's top 3 = 46.8%, no
semiconductor name present at all** (AMD/AVGO/ORCL/NVDA are exactly the
names swapped out). **Arm A is substantially more concentrated in
single-name and single-sector outperformance than Arm B.**

**Reading, stated per the prompt's own instruction to report whichever way
it goes**: this is a **large** difference (−33.8% of final value), and it
traces heavily to concentrated semiconductor exposure that Arm B's
selection rule (top-8 by year-end-2020 market cap) simply doesn't produce —
none of AMD/AVGO/ORCL/NVDA rank in the actual top-8 by 2020 market cap
(that's the whole premise correction in the prompt's own preamble). This
leans toward **"the specific picks mattered,"** not "any similarly-large
basket would have done about as well" — with the caveat in Step 4 below
about what a single point-in-time comparison can and cannot establish.

## Step 4 — what this comparison can and can't tell you

Per state-of-play's own framing and the prompt's explicit instruction: this
is **one draw, not a distribution.** It shows this *specific* rule-based
alternative (top-8-by-2020-cap) would have done substantially worse than
the real portfolio's actual established set — it does **not** by itself
say whether Arm A's performance is typical of what *any* similarly
constructed 8-name basket would produce, or an outlier. That question is
what Step 5 exists to probe, with its own caveat below.

## Step 5 — resampling distribution (25 draws, seed 20260906)

**Gate check, per the prompt**: ran `python3 analysis/audit_top20_2021.py`
first. All 20 names have transcripts loaded (avg 22.9 per ticker, 0
duplicates, 0 gaps ≥120 days) and — separately verified beyond what the
audit script itself checks — all 20 have **Analysis** coverage in the same
`analysis_created_before`/`after` window (range 14–25 rows per ticker, none
thin). **Gate passes cleanly: this step is cheap, ran it.**

Drew 8 names at random from the 20-name pool (`AAPL, MSFT, AMZN, GOOGL,
META, TSLA, ADBE, V, JNJ, WMT, JPM, PG, UNH, DIS, NVDA, MA, HD, PYPL, BAC,
NFLX` — `analysis/audit_top20_2021.py`'s `EXPECTED`, BRK.B already excluded
consistent with Step 0's exclusion rule), 25 times, fixed seed `20260906`,
speculative 8 held fixed every draw exactly as Steps 1–2 do. Full
per-draw output: `analysis/data/run_state/test5-universe-substitution/cells.jsonl`
→ `cell_key` matching `resample_<i>`.

| Statistic | Value |
|---|---|
| n draws | 25 |
| mean | $135,121.97 |
| std | $17,508.56 |
| min | $107,344.08 |
| max | $158,346.54 |
| Arm A's real `final_value` | $179,944.91 |
| **Arm A's percentile** | **100th** (above every one of the 25 draws) |

**Caveat, stated plainly rather than left implicit**: Arm A's own
established set (AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA) is **not**
a subset of the 20-name pool being resampled — AMD, AVGO, and ORCL are not
in the top-20-2021 list at all (that mismatch is exactly what this
prompt's own preamble corrects: the real portfolio's "established eight"
was never chosen by the top-2020-cap rule to begin with). So this
percentile compares the real portfolio's result against a population it
wasn't drawn from, not "how lucky was this draw from among its own peers."
**It answers "would a top-20-2021-constrained rule have matched the real
portfolio" (no, not even at its best draw) rather than "is the real
portfolio's specific 8-name choice an outlier among equivalent choices"** —
the latter would require resampling from a pool that could actually
produce AMD/AVGO/ORCL/NVDA-style semiconductor exposure, which is outside
this test's design (the pool is fixed by the prompt as the top-20-2021
S&P list). Reported as specified, with this caveat attached rather than
silently narrowing the claim.

## Deviations from the prompt, and why

1. **Arm A's reproduction target corrected from $120,800 to $179,944.91**
   (Flag 1) — the prompt's own cited figure is a different, deliberately
   different cell (zero information vs. uncorrupted real recommendations).
   Used the figure that's actually load-bearing for "reproduce the
   settled-config uncorrupted result," consistent with Arm A being framed
   as "the real portfolio."
2. **Premise check #2's named source-of-truth file doesn't define the
   constant it was asked to check** (Flag 2) — reported the actual
   mechanism (dynamic `tier_fn`) and its consequence (AMD's tier/label
   mismatch) instead of forcing the check to apply where it doesn't.
3. **Concentration analysis method** — the prompt says "this requires no
   new analysis — it's visible from Step 1/Step 2's event-level output."
   `compute_summary()`/`run_session_sweep_cell()`'s return dict has no
   direct per-ticker contribution field; computed final-day position value
   by ticker directly from each arm's `portfolio` object (lots × last
   snapshot's price), which is the most direct read of "concentration"
   available without adding a new metric — not a new analysis technique,
   just reading further into the same result object.

## What was deliberately not done

- **No correction applied to Arm A's AMD tier mismatch** (Flag 2) — the
  prompt explicitly forbids adjusting Arm A for this test.
- **No decision drawn on whether the analyst's selection process "adds
  value"** in general — Step 4's limits apply; even Step 5's 100th
  percentile result is against a population Arm A's own selection wasn't
  drawn from (see Step 5 caveat).
- **No re-derivation of why the original ESTABLISHED-8 list includes
  AMD/AVGO/ORCL and excludes AMZN/META** — that's state-of-play §6.1's
  open provenance question; this run measures the consequence, per the
  doc's own instruction, not the cause.
- **`docs/EVALUATION_PROMPT.md`, `ALLOCATOR_OPERATING_MODEL.md`, and
  everything under `analysis/simulator/`** — untouched, per standing rules.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/test5_universe_substitution.py').read())"` — passed.
- Arm A's `final_value`/`max_dd` matched the `analyst-sensitivity`
  `cells.jsonl` `*_q0.0` reference to the cent (`179944.90608455567` /
  `0.20852310359539084`), confirming the driver's generalized
  `load_universe()` reproduces `load_events_dedup_on()`'s exact behavior
  for the unmodified ALL16 universe before trusting it for Arm B.
- `ESTABLISHED`/`SPECULATIVE` constant drift check run programmatically
  (`grep -rn` across all `analysis/*.py`), not just cited from memory —
  7/8 copies respectively, 0 distinct values beyond the one each.
- `tier_fn` computed directly against the live caches for all 16 ALL16
  tickers plus AMZN/META/V/JNJ (not asserted) — AMD's speculative
  classification traced to its actual cached P/E (133.3) and volatility
  (62.8%) values, not assumed from the rule description alone.
- `python3 analysis/audit_top20_2021.py` run live (Step 5 gate) — output
  reproduced verbatim in this report, not summarized from a stale run.
- Git hygiene: tracked-file dirty check passed (`git status --porcelain`
  showed only untracked files from other concurrent sessions on this
  shared branch — `test4-analyst-noise-floor` run_state,
  `av_transcript_fidelity_benchmark_2_stratified`'s raw/, two other
  sessions' handoff/prompt files — none of which this run touches, stages,
  or depends on). Driver committed (`6f3c749`) before this run_state and
  wrap-up, as its own commit, per §10b.

## Wall-clock, cells run, cells reused

Fresh run, no prior state to reuse. Step 1: ~3s (corpus load + one cell).
Step 2: ~3s. Step 3: reused Step 1/2's `portfolio` objects computed inline
(not re-run) for the concentration table, plus one additional live
recomputation per arm to extract `portfolio`/`daily_snapshots` (not stored
in the `cells.jsonl` record, which only keeps summary fields) — ~6s total,
2 cells. Step 5: 25 fresh draws, each a full corpus load + one cell
(~3-4s each) ≈ 85s total. **27 cells written to `cells.jsonl`** (1 Arm A +
1 Arm B + 25 resample draws).

## Reproduction

```bash
cd analysis
python3 test5_universe_substitution.py step0   # hygiene + premise checks
python3 test5_universe_substitution.py step1   # Arm A reproduction
python3 test5_universe_substitution.py step2   # Arm B run
python3 test5_universe_substitution.py step5   # optional resampling (25 draws, seed 20260906)
```

State: `analysis/data/run_state/test5-universe-substitution/{progress.json,
cells.jsonl, findings.md}`.
