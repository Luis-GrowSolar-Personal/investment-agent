# per-trim-value — findings (append-only)

## Finding 1 — Step 0.5 preflight hard stop: QQQ is absent from the canonical price cache

**The file.** `analysis/p6_output_format_analysis.py` (the pattern the prompt
names) resolves prices via `PriceCache(REPO / d.PRICE_CACHE_REL)`, and
`p6_output_format_driver.PRICE_CACHE_REL` = `analysis/data/corpus_v2/scorer_price_cache_v1.json`.
This is the same file `r4_horizon_driver.PRICE_CACHE` points at, and the one
`rel_ret()` (the tradeable-entry ruler used everywhere in this pipeline, and
in `calls.csv`'s `fwd_rel_ret_tradeable`) is built from.

**The check.** `analysis/data/corpus_v2/scorer_price_cache_v1.json` holds 172
tickers. SPY is present. QQQ is not present at all (confirmed by listing every
key in the file — no `QQQ` entry, at any date).

There is a *different*, unrelated cache at `analysis/data/price_cache.json`
that does hold QQQ (1591 dates) and SPY (1596 dates) — but that is not the
cache this pipeline's tradeable-entry ruler is built from, and substituting it
would mean computing the SPY leg from one price series and the QQQ leg from a
different one, which the prompt did not authorize and which is exactly the
kind of undeclared substitution Step 4 says to flag rather than route around.

**Per the prompt's own Step 0.5:** "QQQ and SPY must both be in the price
cache over the full span of train call dates + 182 days. If QQQ is missing or
has gaps, stop and report. Do not fetch." QQQ is missing entirely, not merely
gapped. This is a hard stop, not a workaround-able diagnostic.

**What ran.** `analysis/per_trim_value.py` requires a priced row to have a
name return, an SPY return, and a QQQ return. Since QQQ never resolves,
`n_priced = 0` across all 1217 calls, and Step 1/2/3 all report empty
populations. No number in the printed JSON is meaningful; none is being
reported as a result.

**Decision.** Stop here and report. Do not fetch QQQ into the price cache
(ground rule 1: no cache refresh — and it is also outside this run's scope to
extend the canonical corpus). Whether to (a) add QQQ to
`scorer_price_cache_v1.json` in a future run, (b) drop QQQ as a destination
and run SPY-only, or (c) something else, is a design-session call, not one
this run makes.
