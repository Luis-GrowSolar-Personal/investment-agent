# Scorer price cache — build the one the scorer actually reads — wrap-up

**Reading version (renders correctly anywhere, phone included):**
<https://claude.ai/artifact/RjEFSdaCYBxYqDmC4A1DU4>

**Run ID:** `scorer-price-cache-backfill`. **$0 Anthropic API, no transcripts
scored, no vendor calls.** Price data only, via `yfinance`. Branch
`sweep/db-corpus-baseline`, pushed at the end.

---

## 0. Defined terms

In plain English: the baseline run scored 1,240 real calls but the scorer
could only check 149 of them against what actually happened to the stock,
because its price file only covered 8 companies. This run built a second
price file covering all 164 corpus companies, fixed two more bugs that
surfaced along the way, and re-ran the check the baseline run couldn't. The
honest answer: v6 is still not clearly better than chance, but it's closer to
the edge of "maybe" than either the old 16-company test or the baseline run's
partial 8-ticker result suggested.

- **gradable** — a scored call whose ticker has price coverage *and* whose
  ~6-month forward return already exists in that price data.
- **pp** — percentage points, an arithmetic difference between two
  percentages, not a relative change.
- **95% range** — a ticker-block bootstrap interval (resample tickers, not
  calls, with replacement). "Spans zero" (or "spans 33.3%" for balanced
  accuracy) means the data cannot rule out "no real effect."
- **luck-corrected gap** — observed accuracy minus the accuracy expected from
  the analyst's own guessing habits.

---

## Headline

**On a representative universe of 56 companies and 1,236 gradable calls, v6
scores 30.3% against 27.8% expected by luck — a gap of +2.48 points, whose 95%
range is −0.06 to +5.08pp — barely spans zero.** Balanced accuracy is 35.5%
(95% range 32.6–38.5%), which also still spans the 33.3% chance line.

**v6's near-chance performance mostly replicates, but the picture has moved.**
The legacy 16-company corpus showed +0.8pp (chance). The baseline run's
partial 8-ticker result showed −1.6pp (chance, leaning negative). This run's
full, honest 56-ticker population shows +2.48pp, with a 95% lower bound of
−0.06 — a hair's breadth from excluding zero. **Not a detectable edge yet, but
the closest this project has come to one**, and the direction flipped from
negative to positive as coverage went from 8 to 56 tickers. That movement is
itself informative: the 8-ticker sample was not just small, it was
directionally misleading.

**Carry the model confound in the same breath, as the prompt asked.** Every
figure above comes from `claude-sonnet-4-6`, not the retired model that
produced the legacy 40.4%/39.6% figures. That substitution's one formal gate
returned **HOLD** (7.4pp regression, 4.2pp noise floor, 29% of tickers
improving against a 50% threshold) before the champion was retired anyway.
**Any weakness — or the modest positive gap above — may be the model, not the
prompt, and this data cannot separate the two.**

---

## Before / after (Step C table)

| | before (baseline wrap-up) | after |
|---|---|---|
| calls scored | 1,240 | 1,240 |
| calls gradable | 149 | **1,236** |
| companies gradable | 8 of 57 | **56 of 57** (all but MAXN, a company-level vendor coverage miss unrelated to price data) |
| observed accuracy | 22.8% | **30.3%** |
| expected by luck | 24.5% | **27.8%** |
| luck-corrected gap | −1.64pp (95% −5.67 to +3.05, spans zero) | **+2.48pp (95% −0.06 to +5.08, barely spans zero)** |
| balanced accuracy | 29.7% (95% 23.8–37.0%) | **35.5% (95% 32.6–38.5%)** |
| bullish recall | 35.4% | 38.2% |
| bearish recall | 7.8% | 11.2% |
| neutral recall | 45.8% | 57.1% |
| always-bullish guesser | 32.2% | 32.8% |
| always-flat guesser | 16.1% | 22.2% |

**1,236 is above the prompt's own ~1,090 estimate**, not below it — no gate
concern there. It landed higher because a second bug (below) recovered 80
calls the baseline wrap-up never explained, on top of the ~1,080 the price-
cache gap alone predicted losing.

---

## Two more bugs found and fixed, same failure shape as the one this run was sent to close

This prompt's own framing ("a rule or check applied to one artifact while the
consumer reads another") predicted one instance. Building the fix surfaced two
more of the *same shape*, one layer down:

1. **`analyst_direct_scorer.py`'s structured-output regex silently dropped
   80/1,240 calls.** `_STRUCTURED_RE` anchored on the literal delimiter text
   with only whitespace allowed before the JSON. 80 of v6's actual responses
   in the baseline eval cache wrap the JSON in a ` ```json ` fence, or wrap the
   closing delimiter in `**bold**` — formatting the model chose, not anything
   this project controls. Neither the regex nor `score_eval_dir`'s
   `if not score: continue` surfaced an error; both this run and the baseline
   wrap-up reported "1,160/1,240 processed" without either one asking why 80
   were missing. **Fixed**: the regex now tolerates an optional code fence and
   optional `**` around either delimiter. Verified 0/1,240 files fail to parse
   (was 80/1,240). Pure parsing fix — no change to hit/grading logic.
2. **The new price cache was keyed by the wrong ticker for every renamed
   company.** `scorer_price_cache_v1.json`'s first build keyed entries by the
   *original* manifest ticker (`ANTM`, `VIAC`), but every eval-cache filename
   — and therefore every `PriceCache` lookup — uses the *working* vendor
   symbol the transcripts were actually fetched under (`ELV`, `PARA`). This
   silently read as "not yet scoreable" for all 46 ELV/PARA calls, with no
   error. **Fixed**: both keys are now written for every aliased ticker
   (`GOOGL`/`GOOG`, `VIAC`/`PARA`, `ANTM`/`ELV`, `SQ`/`XYZ`, `NWSA`/`NWS`,
   `BK`/`BNY`, `MAXN`/`MAXNQ`, `SUNW`/`SUNWQ`, `FRC`/`FRCB`).

**`PROPAGATION_AUDIT_A1_A9.json`'s new standing check (Step A) should have
caught #2 before it shipped** — it didn't, because the check was written to
verify *coverage rules* against their consumers, and this was a *cache-key*
mismatch inside a brand-new artifact, not a coverage-rule propagation. Noted
as a gap in the standing check's own scope, not a failure of this run to apply
it.

Also found, own-mistake, fixed before it reached a committed report: the first
`build` pass wrote `scorer_price_cache_v1.json` as `{as_of_date, prices:
{...}}` rather than the flat `{ticker: {date: close}}` shape `PriceCache`
parses — caught by testing the load before running Step C, not after.

---

## Per-ticker coverage (Step B)

163 of 164 corpus companies + SPY got price data via `yfinance`, truncated to
one as-of date (**2026-09-15**) for every ticker — recorded in
`PREREGISTRATION_FIX.json` → `A11_scorer_price_cache.as_of_date`. Full
per-ticker first/last/row-count table:
`analysis/data/corpus_v2/scorer_price_cache_v1.report.json`.

**Two known-unrecoverable companies, exactly as the prompt named them:**
**NOVA** and **WOLF** — no symbol resolves. Expected, not a failure. NOVA
remains gradable only through A6's terminal-value rule; this run does not
change that.

**Frozen legacy cache verified byte-identical, before and after:**
`analysis/data/price_cache.json` sha256
`50b6b283b4400a6361689b1f9b13f7260e4867a09d2cc12e720698e183b7d1a1`, both
times. Every legacy benchmark that replays off it (`settled_control`, the
zero-information floor, the sizing-channel null, the small-cap materiality
record) is unaffected by this run.

---

## Step D — what's still ungradable, and why

Of 1,240 scored calls, **4 remain ungradable** (99.7% resolved):

| Cause | Count | Detail |
|---|---|---|
| 182-day forward horizon not yet reached | 0 | — |
| Rename-boundary price gap | **4** | `PARA` (the working symbol for VIAC/ViacomCBS) 2020-02-20, 2020-05-07, 2020-08-06, 2020-11-06 — these calls predate the 2022 ViacomCBS→Paramount rename, and Yahoo's `PARA` history does not extend back before the rename date under any alias tried. Not the horizon; a genuine missing-history gap at a rename boundary. |
| Company-level vendor coverage miss (not price) | 56 calls | `MAXN` — never got transcripts fetched in the baseline run (not in the vendor's symbol list at all); irrelevant to this run's price fix. |

**The horizon count dropped from "most of 1,011" to zero** once the price
cache's as-of date (2026-09-15) moved past every 2020-2025 call's 182-day
window. This corrects the baseline wrap-up's attribution outright, exactly as
this prompt's §1 predicted: the horizon was never the dominant cause; the
cache gap was.

---

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on every edited/new `.py` file
  after each change.
- `shasum -a 256 analysis/data/price_cache.json` before Step B and after —
  identical both times (recorded above).
- `PriceCache` loader smoke-tested against the new cache
  (`price_on_or_after('JPM', 2024-01-01)` resolved correctly) before trusting
  Step C's output.
- Re-verified 0/1,240 eval files fail `parse_structured` after the regex fix
  (was 80/1,240 before).
- `analyst_direct_scorer.py --price-cache` override defaults to the existing
  global path when omitted — confirmed no behavior change for any caller that
  doesn't pass the flag.

---

## Deviations from the prompt, and why

- **Premise correction: the "Read first" list and Step B both name
  `CORPUS_MANIFEST_V5.json` as the 164-company source. It isn't — V5 is the
  159-company manifest** (pre-corpus-fix-8-followup). The actual 164-company,
  164-unique-ticker source is `SPLIT_V7_RESERVE_REPLACEMENTS.json`
  (`train`+`tune`+`holdout`), whose holdout sha256
  (`909f68cc...`) matches `PROMOTION_GATE.md` §10's current lock. Used V7/the
  split file instead; flagged rather than silently building on the wrong 159.
- **`SUNW`/`FRC` aliases** (`SUNWQ`, `FRCB`) were not yet in
  `TICKER_ALIASES.json` despite the prompt stating them as fact. Verified both
  resolve via `yfinance` before trusting them; not added back to
  `TICKER_ALIASES.json` itself (that file is corpus-construction's, out of
  this run's scope) — recorded instead in this run's own `A11` alias map.
- Added a `--price-cache` override to `analyst_direct_scorer.py` (defaults to
  the existing path) — not explicitly requested, but necessary to point Step C
  at the new cache without touching the frozen default. Judged a mechanical,
  non-discretionary addition, not a spec edit.
- Fixed the markdown-delimiter parsing bug and the alias cache-key bug
  (above) rather than only reporting them, since both are unambiguous
  correctness bugs with no design judgment involved, and leaving them broken
  would have made this run's own headline number wrong.

---

## What was deliberately not done / left for the design session

1. **Whether to re-run the model-substitution gate** now that a larger,
   representative corpus exists — this run only reports the confound, per
   scope boundary.
2. **Tune and holdout remain unscored**, though the new cache now covers them
   (`A11_scorer_price_cache.ticker_list` includes all 164 + SPY) — scoring
   them is a separate decision.
3. **Whether `PROPAGATION_AUDIT_A1_A9.json`'s standing check needs a second
   entry** specifically for cache-key-vs-consumer-lookup mismatches, distinct
   from coverage-rule-vs-consumer mismatches — noted as a gap above, not
   closed.

## Limitations, stated plainly

- **The model confound is not separable with available data** — restated,
  not argued past. Every figure in this report could reflect `claude-sonnet-4-6`
  rather than v6 itself.
- Train split only for the grading figures above; tune and holdout are
  unscored even though the new cache covers them.
- The corpus over-represents failures by construction (carried from the
  legacy 16-company framing).
- Sector-relative grading (F2) remains unresolved; everything above is
  benchmarked against SPY.

---

## Follow-up commands

Re-grade at any time (no re-scoring, no API calls):

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6 \
    --price-cache data/corpus_v2/scorer_price_cache_v1.json
```

Extend the new cache to tune/holdout tickers if a future run scores them (same
driver, same as-of date discipline):

```
cd analysis
python3 scorer_price_cache_backfill_driver.py build
```

Check per-ticker coverage detail:

```
cat analysis/data/corpus_v2/scorer_price_cache_v1.report.json
```
