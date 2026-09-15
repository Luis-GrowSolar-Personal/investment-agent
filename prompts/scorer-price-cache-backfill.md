# Scorer price cache — build the one the scorer actually reads

**Run ID:** `scorer-price-cache-backfill`
**Cost: $0 Anthropic API. No transcript scored. No vendor calls.** Price data
only.
**Branch:** `sweep/db-corpus-baseline`.
**Wrap-up:** `wrap-ups/scorer-price-cache-backfill-out.md` — **short**.

**Read first:** `wrap-ups/baseline-v6-train-batch-out.md`,
`analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json`,
`analysis/data/corpus_v2/TICKER_ALIASES.json`.

---

## 1. The one job, and the mistake behind it

The baseline run scored **1,240 calls successfully for $47** and could grade
**149**. Not because the scoring failed — it didn't — but because
`analysis/data/price_cache.json`, the cache `analyst_direct_scorer.py` reads,
holds price data for **8 of the 57 train companies**.

**The corpus price-coverage gate checked a different file.** A9 verified coverage
against `corpus_v2_price_cache.json`. The scorer opens
`analysis/data/price_cache.json`, which was never expanded past the original
~66-ticker legacy universe. Every company passed a coverage check against a cache
its consumer never opens.

**That is the fourth instance of one failure shape in this project** — a rule or
check applied to one artifact while the consumer reads another. The others: the
Alphabet alias registered but absent from the manifest; A8's verdicts left in a
side file; `versions.js` disagreeing with the version registry.

**The arithmetic, which corrects the baseline wrap-up.** That wrap-up attributes
most ungradable calls to the 182-day forward horizon. It is the reverse:

```
uncovered tickers   1,080 calls   lost to the cache gap
covered tickers       160 calls   → 149 graded, ~11 lost to the horizon
```

So the cache gap explains **1,080**, the horizon about **11**. Fixing this should
take gradable calls from 149 to roughly **1,090**. **No re-scoring is needed** —
transcripts and scores already exist.

---

## 2. Constraints

1. **ZERO Anthropic API calls. Zero vendor calls.** Price providers only.
2. **Do not modify `analysis/data/price_cache.json`.** It is frozen, and every
   legacy benchmark — `settled_control`, the zero-information floor, the
   sizing-channel null, the small-cap materiality record — replays off it. This
   run builds a **new** cache and leaves that file byte-identical. Verify by
   hashing it before and after and reporting both.
3. **No spec edits** except the documentation correction in Step E.
4. **macOS Tahoe, zsh.** `python3`. Never `--break-system-packages`. No `apt`.

---

## 3. Step A — register the cache, and close the gap that caused this

Write `A11_scorer_price_cache` into
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json`, dated, before building
anything. It states:

- the new cache's path and which runs read it;
- **explicitly: which cache `analyst_direct_scorer.py` opens**, so the connection
  between the coverage check and its consumer is written down rather than
  assumed;
- the as-of date every ticker is truncated to (Step B);
- the ticker list and the alias map used.

**Add a standing check to the propagation audit**
(`analysis/data/corpus_v2/PROPAGATION_AUDIT_A1_A9.json`, extended): *a coverage
rule must name the artifact its consumer actually reads, and be verified against
that artifact.* This is the fourth instance; the audit should be able to catch
the fifth.

---

## 4. Step B — build a new, internally consistent cache

Write `analysis/data/corpus_v2/scorer_price_cache_v1.json`, in the **same shape**
`analyst_direct_scorer.py` expects — `{ticker: {date: close}}`, the structure
`PriceCache` already parses.

**Cover the whole corpus, not just train.** All 164 companies from
`CORPUS_MANIFEST_V5.json`, plus **SPY**. Tune and holdout will need this later;
fetching now costs nothing extra and avoids repeating the exercise.

**One as-of date for every ticker.** Pick a single cutoff — today's available
close is fine — and truncate every series to it, including SPY. Record it in the
manifest. A cache where some tickers run to May and others to September grades
different companies against different horizons, which is the kind of quiet
inconsistency this project keeps paying for.

**Use `TICKER_ALIASES.json` for the delisted and renamed.** `SUNW` is `SUNWQ`,
`FRC` is `FRCB`, `MAXN` is `MAXNQ`, Bank of New York Mellon is `BNY`, Alphabet is
`GOOG`. Record which symbol supplied each series.

**Two known-unrecoverable companies**: NOVA and WOLF have documented price gaps
that no symbol resolves. Expected, not a failure — record them and move on. NOVA
remains gradable only through A6's terminal-value rule.

Report per ticker: symbol used, first and last date, row count, and whether it
spans every call in the manifest plus 182 days.

---

## 5. Step C — verify the fix

Re-run `analysis/analyst_direct_scorer.py` over the **existing** train eval cache
— the one the baseline run already paid for — pointed at the new price cache.
**No scoring. No API calls.**

Report:

| | before | after |
|---|---|---|
| calls scored | 1,240 | 1,240 |
| calls gradable | 149 | |
| companies gradable | 8 of 57 | |

**If the after figure is far below ~1,090, something else is wrong** — say what,
rather than accepting the number.

Then report the grading results on the enlarged population, in the same shape the
baseline run used: observed accuracy, expected-by-luck, the gap with its 95%
range, balanced accuracy against the 33.3% chance line, per-answer recall beside
each outcome's base rate, and the two guesser figures for continuity.

**Then answer the question the baseline run could not:**

> On a representative universe of **___ companies** and **___ gradable calls**,
> v6 scores **___%** against **___%** for luck — a gap of **___ points**, whose
> 95% range **does / does not** include zero.

**State plainly whether v6's near-chance performance replicates**, or whether the
old 16-company universe was the problem.

**Carry the model confound in the same breath.** These scores come from
`claude-sonnet-4-6`, not the retired model that produced the legacy figures — and
that substitution's one formal gate returned **HOLD** (a 7.4-point regression
against a 4.2-point noise floor, 29% of tickers improving against a 50%
threshold) before the champion was retired anyway. **Any weakness measured here
may be the model rather than the prompt**, and that cannot be separated with the
data available.

---

## 6. Step D — what is still ungradable, and why

Report the remaining ungradable calls split by cause: the 182-day horizon,
genuinely missing price history, and anything else. **Name the count for each.**
The horizon figure sets how much more of the corpus becomes gradable simply with
time.

---

## 7. Step E — one documentation correction

`CLAUDE.md`'s tech-stack section still names `claude-sonnet-4-20250514`, retired
2026-06-15. Correct it to the registered current model, **with the registry
entry cited as evidence**, and note the HOLD gate result alongside so the line
does not read as an endorsement.

This is the only spec edit this run makes.

---

## 8. Step F — the report

**Scope boundary: report, do not decide.** No scoring is commissioned.

Short. Plain-language summary to the project instructions' language rules, then
the before/after table, the filled-in sentence from Step C, the per-ticker
coverage, what remains ungradable and why, and the hash proving
`price_cache.json` is unchanged.

**Limitations to state, not argue past:**

- The model confound above. It is not separable with available data.
- Train split only for the grading figures; tune and holdout are unscored, though
  the new cache now covers them.
- The corpus over-represents failures by construction.
- Sector-relative grading (F2) remains unresolved.

---

## 9. Git — Code runs these, in this order

1. Confirm a clean tree; record `git_dirty: false`. Hard stop otherwise.
2. **Commit the driver first, as its own commit.**
3. Commit A11, the new cache, and the propagation-audit extension.
4. Commit the wrap-up and the `CLAUDE.md` correction.
5. **Push once, at the end**, to `origin sweep/db-corpus-baseline`.

Run-specific paths only — **no `git add .` and no `git add -A`.** No merge to
`dev`.

---

## 10. Standing rules

- Provenance for every figure: `<value>` — `<path>` → `<json.key>`. Record the
  as-of date and every alias used.
- **A diagnostic that contradicts this prompt is a finding, not a reason to
  stop.** The most likely: the gradable count landing well short of 1,090, or
  more companies than expected having purged history.
- **Note anything contradicting this prompt's premises.** The repo and the price
  providers outrank it.
