# Findings — q2-bearish-strength-separation

Append-only. Each finding is written the moment it is established.

## Pre-registered axis ranking (§5c rule 1) — written BEFORE any contingency table

Ranking as given in the prompt (§5c), used as-is; no disagreement with the
prompt's ordering.

1. **A1 — `recommendation`, Exit vs Trim.** Prediction: Exit separates from
   Trim — the scorer collapses both into "bearish," discarding a distinction
   the analyst already draws explicitly.
2. **A2 — `thesisHealth`, Broken vs Weakening.** Prediction: Broken beats
   Weakening — it is the analyst's own severity label.
3. **A3 — `blindSpotsTriggered` count, 0 / 1 / 2+.** Prediction: more
   triggered blind spots -> higher hit rate (more independent warnings firing
   = better-evidenced call).
4. **A4 — `stumbleType`, Structural vs Execution vs Discovery.** Prediction:
   Structural beats Execution and Discovery (structural damage should predict
   worse forward returns than an execution miss).
5. **A5 — `ratchetTranche`, 1 vs 2 vs 3 vs null.** Prediction: higher tranche
   beats lower (a second/third consecutive weakening quarter is confirmed
   deterioration, not a first read).
6. **A6 — `credibilityDelta`, negative vs neutral/positive.** Prediction:
   negative beats neutral/positive (credibility loss alongside a bearish call
   compounds it).
7. **A7 — `threatMechanismImpaired`, true vs false.** Prediction: true beats
   false (the thing that makes the company work is actually broken).
8. **A8 — `recommendedSize`/`capPercent`, binned.** Prediction: deeper cuts
   (lower recommended size / cap) beat shallower ones (largest cut = strongest
   conviction).

No axis reordered. Contingency tables computed next, on train first, then tune,
per §5c rule 3.

## Flagged premise 1 — price cache path (prompt §2 ground rule 5)

The prompt's literal instruction ("Use `analysis/data/price_cache.json` as it
stands") fails the coverage guard on both splits: that file covers only 66
tickers from an older 8-ticker-era cohort and does not include MMM, ABBV, or
any of the other 56/54 train/tune tickers. The actual v6 train/tune baselines
this run is meant to reproduce were scored against
`analysis/data/corpus_v2/scorer_price_cache_v1.json` (172 tickers), per the
`--price-cache` invocations recorded in `wrap-ups/baseline-v6-tune-batch-out.md`.
Used that cache instead — still frozen, still read-only, zero API spend — to
honor the run's actual purpose. Reported here rather than silently switched.

## Flagged premise 2 — WOLF/SPWR must be excluded entirely, not just where unscoreable

The coverage guard trips on WOLF (23/23 calls unscoreable) and SPWR (10/15) in
tune. This is the documented, expected loss (prompt §5b, state-of-play §6).
Continuing past the guard with only per-call price-data exclusion left 97
bearish-predicted calls on tune (not the reference 84) because 5 SPWR calls
still have surviving pre-reorg price data. The reference figures (84 bearish,
59.5% right, 48.4% base rate) require dropping WOLF and SPWR ENTIRELY — every
call from those tickers, not only the ones missing price data — matching the
`--tickers` allowlist the original baseline runs used. Implemented that way;
confirmed exact match to all three reference figures (train 103/60.2%/44.9%,
tune 84/59.5%/48.4%, pooled 187/59.9%/46.6%).

NOVA does not appear in either eval directory at all as of this run (0 files
under either `data/evals/v6_claude-sonnet-4-6*`) — the state-of-play's "NOVA
silently affected the same way on train" note does not currently apply to this
corpus; noted, not chased further (out of scope).

## Base-rate computation bug caught and fixed before any axis was computed

First implementation computed "base rate for bearish" as the ground-truth-
bearish share *within the bearish-predicted subset* — which is mathematically
identical to `pct_right` (hit for a bearish-predicted call is true exactly
when ground_truth=="bearish"), so it silently printed 60.2%/60.2% for both
quantities on train, i.e. no daylight between what the analyst got right and
what "actually happened." Base rate must be computed over ALL scoreable calls
in the split (any predicted direction), which is what `PROMOTION_GATE.md`
§3.1's "expected-by-luck" and the state-of-play's 44.9%/48.4% figures mean.
Fixed before producing the joined table's coverage report; verified against
the reference figures (see above) before touching axis computation.

## Coverage exclusion (prompt §5a hard stop)

`ratchetTranche` is null on 26.0% of pooled bearish calls (52/200) — exceeds
the 5% threshold. **A5 (ratchetTranche) is excluded as an axis**, per the
prompt's explicit instruction not to silently treat null as a category. All
other axis fields are 0% null on bearish calls.

## Per-axis results (train computed first, then tune; §5c rule 3)

- **A1 (recommendation: Exit vs Trim).** Exit is essentially unused: 1 Exit
  call in train (n=1, 100% hit — not a usable sample), 0 Exit calls in tune.
  The scorer's Trim/Exit collapse does not lose a real strength distinction
  here because the analyst almost never actually issues "Exit" as a first
  call. Does not separate — no tune bucket exists to confirm against.
- **A2 (thesisHealth: Broken vs Weakening).** Same shape as A1: "Broken" is
  used once in each split (n=1). Weakening is effectively the entire bearish
  population (55/103 train, 41/84 tune — the rest fall elsewhere in
  thesisHealth, e.g. "intact" mixed with a bearish recommendation). Does not
  separate — Broken too rare to use as a bucket.
- **A3 (blindSpotsTriggered count).** Train: 0 blind spots 57.9% (n=95), 2+
  87.5% (n=8) — 29.6-point spread, direction as predicted. Tune: 0 blind
  spots 60.8% (n=79), 2+ 40.0% (n=5) — spread REVERSES to −20.8 points.
  Did not hold on tune. One sentence, no hedging: A3 does not separate.
- **A4 (stumbleType).** Train: Structural 71.0% (n=31) is the strongest
  bucket, Discovery 44.4% (n=9) weakest — as predicted. Tune: Structural
  drops to 33.3% (n=12), now the WEAKEST bucket; Execution (64.2%, n=67) is
  strongest. Direction reverses. A4 does not separate.
- **A6 (credibilityDelta sign).** Train: negative 63.4% (n=71) vs
  neutral/positive 53.1% (n=32) — negative stronger, as predicted (+10.3 pt
  spread). Tune: negative 62.9% (n=62) vs neutral/positive 50.0% (n=22) —
  same direction (+12.9 pt spread). **This is the only axis whose ordering
  holds on both splits.** Magnitude is modest: the strongest bucket beats its
  split's base rate by 18.5 points (train) and 14.5 points (tune), only
  slightly more than the ~15.3/11.1-point lift the undifferentiated
  all-bearish-calls figure already gets over base rate — and the buckets'
  95% ranges overlap substantially (train: 51.8–73.6% vs 36.4–69.1%; tune:
  50.5–73.8% vs 30.7–69.3%). Direction survives; the separation it adds
  beyond "just trust every bearish call more" is small and not clearly
  outside noise at this n.
- **A7 (threatMechanismImpaired).** Train: true 72.7% (n=55) vs false 45.8%
  (n=48) — true much stronger, as predicted (+26.9 pts). Tune: true 50.0%
  (n=30) vs false 64.8% (n=54) — REVERSES; true is now weaker. Does not
  separate.
- **A8 (recommendedSize/capPercent, binned).** Train: <=15% 61.5% (n=96) vs
  15-30% 42.9% (n=7) — shallower cuts scored HIGHER, opposite of the
  predicted direction (deeper cut = stronger conviction). Tune: <=15% 58.8%
  (n=68) vs 15-30% 66.7% (n=15) vs >30% 0% (n=1) — direction flips again
  relative to train, and the >30% bucket has only one call. Thin buckets at
  every depth beyond 15%; does not separate.

**Summary: of the seven axes computed (A5 excluded for coverage), one
(A6) held its direction on both splits, and its margin is a few points, not
a clean break. Six of seven either had no usable second bucket or reversed
direction from train to tune.**
