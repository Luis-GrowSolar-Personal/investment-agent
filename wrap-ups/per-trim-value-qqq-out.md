# Per-trim value — the completed QQQ leg — wrap-up

**Prompt:** `prompts/per-trim-value-qqq.md`. **Run ID:** `per-trim-value-qqq`.
**Cost:** $0 in API/scoring/DB terms — one free `yfinance` fetch of QQQ was
the only network call, as the prompt allowed.

> QQQ added to the canonical price cache by the same method as SPY (commit
> `678017f`); legacy QQQ agrees to within **0.0000057%** on **1,591** shared
> dates. Into QQQ, moving 2.5 points of the book out of each of B's **374**
> flagged calls (pooled over both draws) made **0.2151** points per trim
> (**$215** on $100,000), against **0.1020** for a random name in the same
> quarter. The analyst's contribution is **0.1131** (range **−0.0941** to
> **0.3040**). Into SPY (unchanged): **0.1381** against **0.0283**,
> contribution **0.1098** (range **−0.0998** to **0.3038**). **Combined
> verdict under the fixed reading: protection does not pay — on both
> destinations, A's own range includes zero, so neither "the analyst pays"
> nor "the index does the work" applies.** Sized by P9 severity, the
> contribution per point moved into QQQ is **0.2286** (range **0.0982** to
> **0.3413**), against **0.2274** into SPY — nearly identical, and on both
> destinations about 5x the unsized figure.

---

## Step 1 — adding QQQ to the canonical cache

`analysis/add_qqq_to_scorer_cache.py` fetched QQQ with the two lines copied
from `scorer_price_cache_backfill_driver.py`'s `cmd_build`
(`yf.Ticker("QQQ").history(start="2019-06-01", end=..., auto_adjust=False)`,
then `{date: round(close, 4)}`) — that driver's fetch is inlined in a loop
keyed to its own ticker list and cache file, not importable as a standalone
function, so the two lines were copied verbatim, as the prompt allowed. `end`
was set to the day after SPY's last date in the canonical cache
(**2026-09-15**, one day past **2026-09-14**), not "today," so QQQ and SPY
cover the exact same span in a cache that itself predates this run.

| check | result |
|---|---|
| QQQ trading dates == SPY trading dates in the canonical cache | **match** (1,831 dates each, 2019-06-03 → 2026-09-14) |
| cross-check vs. frozen legacy `price_cache.json` QQQ, 1,591 shared dates | max relative difference **5.7e-8** (well under the 0.1% stop threshold) |
| every non-QQQ key in the canonical cache identical before/after | **yes** |
| legacy `price_cache.json` sha256 unchanged | **yes** (`50b6b283...183b7d1a1`) |

Canonical cache sha256: `f79cd0da...f5551d5e7` → `7fe2e23b...5804b65f3`
(172 tickers → 173). Commit `678017f`.

*Provenance:* `analysis/data/run_state/per-trim-value-qqq/add_qqq_preflight.json`,
`add_qqq_postwrite.json`.

## Step 2 — rerun, and the reproduction check

`analysis/per_trim_value.py` needed one change to avoid overwriting the first
run's output: an optional CLI arg naming the `run_state` output directory
(committed separately, `357f468`, before any output — default behavior with
no arg is unchanged). No other code changed.

**Assert: the SPY leg reproduces the first run exactly.** Every figure in
`run_state/per-trim-value/results.json` → `SPY` (Step 1, Step 2, Step 3, all
three draws) compared field-by-field against this run's SPY output:
**identical.** The only thing that changed between the two runs is that QQQ
now has prices.

Preflight for QQQ: all 1,217 train calls priced (0 dropped) once QQQ was
added — this is the same population Step 1 of the first run reported for
SPY (1,217/1,217), so the QQQ leg drops no calls SPY didn't already need to
have priced. Sanity check (name − SPY reproduces `fwd_rel_ret_tradeable`):
max mismatch 0.0001, same as the first run (SPY leg is unaffected by adding
QQQ).

## Step 3 — the pre-registered reading, both destinations

### Step 1 table (fixed 2.5-point trims), QQQ beside SPY

| | draw 1 | draw 2 | pooled |
|---|---|---|---|
| **QQQ** n | 191 | 183 | 374 |
| QQQ A mean | 0.2273 | 0.2023 | **0.2151** |
| QQQ A range | [−0.0211, 0.4682] | [−0.0845, 0.4775] | [−0.0518, 0.4699] |
| QQQ B matched | 0.1004 | 0.1036 | 0.1020 |
| QQQ B unmatched (ref.) | 0.0602 | 0.0602 | 0.0602 |
| **QQQ A − B** | **0.1269** | **0.0987** | **0.1131** |
| QQQ A − B range | [−0.0671, 0.3061] | [−0.1268, 0.3087] | [−0.0941, 0.3040] |
| **SPY** A mean | 0.1531 | 0.1223 | **0.1381** |
| SPY A range | [−0.0944, 0.3876] | [−0.1667, 0.3914] | [−0.1291, 0.3868] |
| SPY B matched | 0.0296 | 0.0269 | 0.0283 |
| **SPY A − B** | **0.1235** | **0.0954** | **0.1098** |
| SPY A − B range | [−0.0735, 0.3062] | [−0.1319, 0.3063] | [−0.0998, 0.3038] |

*Provenance:* `analysis/data/run_state/per-trim-value-qqq/results.json` →
`step1_base_result.{QQQ,SPY}`.

**Tail decomposition, QQQ pooled (n=374, 10% = 37 trims):** best 10% supplied
98.0% of the total, worst 10% cost 124.1%, middle 80% sums to 101.41 pts,
52 future big winners (beat S&P by 20+ pts) total **−109.16 pts**. Same shape
as SPY's tail (145% / −198% / 79.27 pts / −112.28 pts) — a small pooled total
sitting close to zero, dominated by a handful of large positive and negative
trims either way.

### The combined verdict

Applying `prompts/per-trim-value.md`'s reading exactly as written, to the
pooled rows, fixed 2.5-point trims:

- **The analyst pays** — A − B above zero for QQQ *and* SPY. **Does not
  hold** — both ranges include zero (QQQ: −0.0941 to 0.3040; SPY: −0.0998 to
  0.3038).
- **The index does the work** — A's range above zero, A − B's range includes
  zero. **Does not hold** — A's own range includes zero on *both*
  destinations (QQQ: −0.0518 to 0.4699; SPY: −0.1291 to 0.3868), so this
  clause's premise (A above zero) is never satisfied either.
- **Protection does not pay** — A's range includes or is below zero.
  **Holds on both destinations.**

**Combined verdict: protection does not pay.** The two legs read the same
way — this is not a case where QQQ and SPY disagree. The book test that was
queued to come next regardless (`docs/handoffs/2026-09-28-allocator-book-test-design.md`)
now has QQQ prices, but this per-trim result does not by itself send B's
trims forward into it.

### P9 severity layer, QQQ beside SPY

**Value per point by band, pooled:**

| band | trim size | QQQ value/point | QQQ range | SPY value/point | SPY range |
|---|---|---|---|---|---|
| 1 (most negative P9) | 5.0 | **0.3334** | [0.1357, 0.5020] | 0.3029 | [0.1139, 0.4612] |
| 2 | 2.5 | 0.1508 | [0.0520, 0.3165] | 0.1308 | [0.0415, 0.2835] |
| 3 | 0 | 0.1349 | [0.0245, 0.2407] | 0.1182 | [0.0040, 0.2242] |
| 4 | 0 | 0.0449 | [−0.1536, 0.1858] | −0.0029 | [−0.2055, 0.1421] |
| 5 (least negative) | 0 | −0.2381 | [−0.5918, 0.0543] | −0.2775 | [−0.6271, 0.0118] |

Ordering condition (band 1 > band 2 > n-weighted mean of bands 3–5) **holds
on QQQ**: 0.3334 > 0.1508 > −0.0185. Holds on SPY too (0.3029 > 0.1308 >
−0.0531), per the first wrap-up.

**Sized total, pooled:**

| | QQQ | SPY |
|---|---|---|
| sized A mean | 0.4099 [0.1966, 0.6293] | 0.3693 [0.1650, 0.5802] |
| sized A − B | 0.3438 [0.1485, 0.5154] | 0.3420 [0.1460, 0.5158] |
| **sized A − B per point moved** | **0.2286** [0.0982, 0.3413] | **0.2274** [0.0968, 0.3412] |
| Step 1's unsized A − B per point | 0.0452 | 0.0439 |
| P9 adds value vs. Step 1 | **yes** | **yes** |

Per-draw: QQQ sized A−B per point is 0.2344 (draw 1, vs. 0.0508 unsized) and
0.2125 (draw 2, vs. 0.0395 unsized) — same ≈5x pattern as SPY on both draws.
**Both parts of the P9 condition hold on QQQ**, same conclusion as SPY. Per
the prompt, this cannot change the Step 1 verdict.

*Provenance:* `results.json` → `step2_p9_severity.{QQQ,SPY}.{b1,b2,pooled}`.

### Diagnostic (labelled diagnostic-only, not a condition)

The design session expected the destination to move A a lot and A − B very
little, since the quarter-matched control absorbs most of a destination's own
tailwind. Pooled, fixed 2.5:

| | value |
|---|---|
| A(QQQ) − A(SPY) | **0.0770** |
| [A − B](QQQ) − [A − B](SPY) | **0.0033** |

Pooled, P9-sized:

| | value |
|---|---|
| sized A(QQQ) − sized A(SPY) | **0.0406** |
| sized [A − B](QQQ) − sized [A − B](SPY) | **0.0018** |

**Expectation confirmed both ways**: A moves by 7-8 hundredths of a point
between destinations, A − B by three-thousandths (fixed) or two-thousandths
(sized) — an order of magnitude smaller. The control is doing what it was
built to do.

### Veto layer

Not re-reported, per the prompt (one flagged call carries the beat-and-raise
tag; already closed in the first wrap-up). For completeness, QQQ pooled:
vetoed A mean 0.2156, vetoed A − B 0.1133 [−0.0943, 0.3042] — indistinguishable
from the un-vetoed pooled row above, same as SPY.

## Deviations from the prompt

1. **One code change beyond Step 1's driver**, as the prompt anticipated and
   pre-authorized: `per_trim_value.py` took an optional CLI arg for its
   output `run_state` directory, committed on its own (`357f468`) before any
   output, so this run's output does not overwrite the first run's
   `results.json`.
2. Everything else — the fetch method, the two asserts' thresholds, the
   reading, the P9 sizes, the diagnostic, the veto (not re-reported) — ran
   exactly as specified.

## What this cannot show (unchanged from the first wrap-up)

Train data, already seen elsewhere in this pipeline. Trims measured one at a
time, not as a book — nothing here speaks to drawdown, turnover, taxes, or
what happens when many names are flagged in the same month. That is the book
test.

## What it means

Both destinations land in the same bucket: **A's own range includes zero on
every row this run computed** — draw 1, draw 2, and pooled, QQQ and SPY
alike. Per the reading fixed before either run, that is **protection does
not pay**, and the allocator rebuild does not proceed on B's trims on this
evidence. This is a full stop before the sleeve/index question is reached —
the P9 layer's real-looking gain (sized contribution roughly 5x the unsized
figure, on both destinations) does not change that, per the prompt's own
rule that the P9 result cannot override the Step 1 verdict.

The book test design
(`docs/handoffs/2026-09-28-allocator-book-test-design.md`) now has the QQQ
prices it was written expecting to use; what this result means for whether
that test still runs on B's trims specifically is for the design session.

## Follow-up commands

Reproduce this run:

```
python3 analysis/per_trim_value.py per-trim-value-qqq
```

Reproduce the first (SPY-only) run, to re-verify the two agree on SPY:

```
python3 analysis/per_trim_value.py
```

Re-verify QQQ's presence and shape in the canonical cache:

```
python3 -c "import json; d=json.load(open('analysis/data/corpus_v2/scorer_price_cache_v1.json')); q=d['QQQ']; print(len(q), sorted(q.keys())[0], sorted(q.keys())[-1])"
```

## Git

- Prompt already committed at `45d4caa` (prior session, before this run
  started).
- `analysis/add_qqq_to_scorer_cache.py` + `progress.json` committed at
  `59fb1c5` before fetching QQQ.
- Cache update committed at `678017f` (data only — QQQ added, nothing else
  changed, legacy cache untouched).
- `per_trim_value.py`'s output-dir arg committed at `357f468` before the
  rerun.
- This wrap-up, `results.json`, `findings.md`, and the final `progress.json`
  committed next, then `git push` of `sweep/db-corpus-baseline` — pushed hash
  reported in chat.
