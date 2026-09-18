# Q2 — does the analyst already know which of its bearish calls are the good ones?

**Prompt:** `prompts/q2-bearish-strength-separation.md`
**Run:** `q2-bearish-strength-separation` — complete, both splits, all steps done.
**Cost: $0.** No LLM calls, no Anthropic API spend, no DB writes. Read-only
analysis of two already-scored eval caches and the frozen price cache.
**Scope boundary honored: this is a report, not a decision.** It does not
run P1, does not reorder the candidate queue, and does not amend
`PROMPT_ARCHITECTURE.md`.

---

## §0 — Defined terms

Read this before anything else. Several of these read as their own opposite.

- **Bearish call.** A call where the analyst's structured output says "Trim"
  or "Exit" (or, if that field is missing, "weakening"/"broken" thesis
  health). Out of every ~13 calls it scores, it says this about 1.
- **Base rate (for bearish).** How often the stock genuinely underperformed
  its benchmark by more than 5 points over the next two quarters — across
  *all* calls, regardless of what the analyst said. This is "what actually
  happened," not "what the analyst predicted." On train that's 44.9% of
  calls; on tune, 48.4%.
- **Hit.** The analyst's call matched what actually happened. A bearish call
  is a hit if the stock underperformed by more than 5 points over the next
  ~6 months.
- **Dead band.** Moves within ±5 points of the benchmark count as neither a
  hit for bullish nor for bearish — they're graded as if the analyst should
  have said "hold."
- **Benchmark-relative 2-quarter return.** The stock's return minus the
  S&P 500's return, measured from the call date to about 6 months later.
  This is what "outperformed" or "underperformed" means throughout.
- **Precision.** Of the times the analyst said "bearish," what share turned
  out right. Different from "coverage," which is how *often* it says
  bearish at all.
- **Coverage.** How often the analyst is willing to make a bearish call, out
  of everything it could grade. Right now: about 1 in 13.
- **Strength axis.** A field in the analyst's own structured output — recommendation
  type, how bad it thinks the thesis is, how many red flags it flagged, etc.
  — that might separate its better bearish calls from its worse ones, the
  same way a sharper knife cuts better than a duller one, even though both
  are called "knives."

---

Of v6's **187** bearish calls across train and tune, **112** were right
(**59.9%**) against a base rate of **46.6%**. Splitting them by
**management-credibility direction (worsening vs. not)** separates the
right calls from the wrong ones by **10.3 points** on train; on tune that
separation **held**, at **12.9 points**. Of the eight axes tested, **one**
(that same credibility split) separated on both splits, and **one** was
excluded outright for missing too much data; **five** did not separate — three
of them because the ordering flipped between train and tune, and two because
the analyst almost never uses one side of the split (Exit as distinct from
Trim; "Broken" as distinct from "Weakening").

**What this means in plain terms: the analyst's bearish calls are, right
now, close to one undifferentiated signal.** It has one field — whether it
thinks management is losing credibility — that points the right direction on
both halves of the data, but the gap it draws is modest (10–13 points) and
sits inside overlapping error bars. Every other field tested — how the call
is labeled, how many warning signs it flagged, what kind of problem it thinks
the company has, whether it thinks the core business is broken, how deep a
cut it recommends — either flipped direction between train and tune, or
wasn't used often enough to test at all.

---

## Coverage report (§5a hard stop)

Every bearish call across both eval caches parsed a structured block except
one file. Of the 200 pooled bearish calls, every field used by an axis is
present in every call **except one: `ratchetTranche`, missing on 26.0%
(52/200)**. Per the prompt's hard stop, that field is excluded as an axis
rather than treated as its own "null" category.

| field | % null on bearish calls | used as an axis? |
|---|---|---|
| recommendation | 0.0% | yes (A1) |
| thesisHealth | 0.0% | yes (A2) |
| blindSpotsTriggered | 0.0% | yes (A3) |
| stumbleType | 0.0% | yes (A4) |
| ratchetTranche | **26.0%** | **no — excluded, exceeds 5% threshold** |
| credibilityDelta | 0.0% | yes (A6) |
| threatMechanismImpaired | 0.0% | yes (A7) |
| recommendedSize / capPercent | 0.0% | yes (A8) |

Source: `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv`
(200 rows, `predicted == "bearish"`), coverage counts printed by
`analysis/q2_bearish_strength_driver.py`.

---

## §5b — bearish denominators, verified against the reference figures

Two flagged premises had to be resolved before the reference figures
(train 103/60.2%/44.9%, tune 84/59.5%/48.4%) would reproduce. Both are
documented in full in
`analysis/data/run_state/q2-bearish-strength-separation/findings.md`; summary:

1. **Price cache.** The prompt's literal instruction ("use
   `analysis/data/price_cache.json` as it stands") points at a stale
   66-ticker cache from an earlier, smaller corpus era that doesn't cover
   MMM, ABBV, or nearly any of this corpus's 56/54 train/tune tickers.
   `analyst_direct_scorer.py`'s own `--price-cache` help text calls that file
   "the frozen default, which legacy benchmarks replay off" — the actual v6
   baselines were scored against `analysis/data/corpus_v2/scorer_price_cache_v1.json`
   (172 tickers), per the `--price-cache` flag recorded in
   `wrap-ups/baseline-v6-tune-batch-out.md`. Used that cache instead —
   still frozen, still read-only, zero spend.
2. **WOLF / SPWR must be dropped entirely, not just where price data is
   missing.** The coverage guard correctly flags WOLF (23/23 calls
   unscoreable) and SPWR (10/15) on tune — the documented bankruptcy/
   ticker-reuse loss. But 5 of SPWR's 15 calls still have surviving
   pre-reorg prices; counting those in left 97 bearish-predicted calls on
   tune, not the reference 84. The reference figures require excluding
   WOLF and SPWR **entirely** (every call, not only the unscoreable ones),
   matching the `--tickers` allowlist the original baseline runs used.
   NOVA — also named in the prompt as affected — does not appear in either
   eval directory at all as of this run; noted, not investigated further
   (out of scope for this report).

A third issue was a bug in this run's own first draft, caught before any
axis was computed: the initial "base rate" calculation measured the share of
bearish-*predicted* calls that turned out bearish, which is mathematically
the same number as precision (a bearish call is a hit exactly when the
outcome was bearish) — so it printed 60.2% for both "precision" and "base
rate" on train, hiding the entire point of the comparison. Fixed to measure
the base rate over *all* scoreable calls, any predicted direction, before
producing anything downstream.

With both fixes applied, all three reference figures reproduce exactly:

| | train | tune | pooled |
|---|---|---|---|
| bearish calls made | 103 | 84 | 187 |
| …and right | 62 (60.2%) | 50 (59.5%) | 112 (59.9%) |
| base rate | 44.9% | 48.4% | 46.6% |
| calls lost to WOLF/SPWR | 0 | 13 (WOLF 9, SPWR 4) | — |

**No discrepancy to report** — these match `PROMPT_ARCHITECTURE.md` §2.1 and
`wrap-ups/baseline-v6-tune-batch-out.md` exactly.

Source: `analysis/data/run_state/q2-bearish-strength-separation/cells.jsonl`
and driver stdout, `bearish_denominators()` output.

---

## §5c — the eight-axis table, both splits

Ranking and one-line predictions were written to `findings.md` **before** any
contingency table was computed (pre-registration, per §2.3 / §5c rule 1).
Train was computed first in every case; tune second, to confirm or refute.

| # | axis | train: strongest bucket | train: weakest bucket | train spread | tune: strongest | tune: weakest | tune spread | held on tune? |
|---|---|---|---|---|---|---|---|---|
| A1 | recommendation: Exit vs Trim | Exit 100% (n=1) | Trim 59.8% (n=102) | 40.2 pts (n=1, not usable) | Trim 59.5% (n=84) | — no Exit calls | n/a | **no usable second bucket** |
| A2 | thesisHealth: Broken vs Weakening | Broken 100% (n=1) | Weakening 70.9% (n=55) | 29.1 pts (n=1, not usable) | Weakening 58.5% (n=41) | Broken 0% (n=1) | 58.5 pts (n=1, not usable) | **no usable second bucket** |
| A3 | blindSpotsTriggered count (0 / 1 / 2+) | 2+ 87.5% (n=8) | 0 57.9% (n=95) | +29.6 pts | 0 60.8% (n=79) | 2+ 40.0% (n=5) | **−20.8 pts** | **no — reversed** |
| A4 | stumbleType (Structural / Execution / Discovery) | Structural 71.0% (n=31) | Discovery 44.4% (n=9) | +26.6 pts | Execution 64.2% (n=67) | Structural 33.3% (n=12) | **Structural now weakest** | **no — reversed** |
| A5 | ratchetTranche | — | — | — | — | — | — | **excluded, 26% missing** |
| A6 | credibilityDelta: negative vs neutral/positive | negative 63.4% (n=71) | neutral/pos 53.1% (n=32) | +10.3 pts | negative 62.9% (n=62) | neutral/pos 50.0% (n=22) | +12.9 pts | **yes — direction held** |
| A7 | threatMechanismImpaired: true vs false | true 72.7% (n=55) | false 45.8% (n=48) | +26.9 pts | false 64.8% (n=54) | true 50.0% (n=30) | **true now weaker** | **no — reversed** |
| A8 | recommendedSize/capPercent (binned) | <=15% 61.5% (n=96) | 15-30% 42.9% (n=7) | −18.6 pts (opposite of predicted direction) | 15-30% 66.7% (n=15) | <=15% 58.8% (n=68), >30% 0% (n=1) | reversed again, thin buckets | **no — reversed, thin data** |

All 95% ranges (Wilson score interval) and the full per-bucket counts are in
`analysis/data/run_state/q2-bearish-strength-separation/cells.jsonl`. In
plain terms: with samples this small (most buckets are 30–100 calls, several
are single digits), a "44% to 66%" range means the true rate could
plausibly be almost anywhere in that band — several of these apparent splits
are well within the range you'd see from coin-flip noise.

---

## The axis that separated: A6, credibility direction

**On train:** bearish calls where the analyst flagged management credibility
as worsening were right 63.4% of the time (45 of 71 calls, range roughly
52% to 74%). Bearish calls where credibility wasn't flagged as worsening
were right only 53.1% of the time (17 of 32 calls, range roughly 36% to
69%) — a 10.3-point gap.

**On tune (companies this wasn't derived from):** the same split, same
direction — credibility-worsening calls right 62.9% of the time (39 of 62,
range roughly 51% to 74%), the other bucket right 50.0% of the time (11 of
22, range roughly 31% to 69%) — a 12.9-point gap.

**The direction survived on fresh companies. The size of the gap is modest
and the ranges overlap heavily** — on both splits, the lower bound of the
stronger bucket's range sits below the upper bound of the weaker bucket's
range. This axis beats the base rate by 18.5 points (train) and 14.5 points
(tune) in its strongest bucket — only a few points more than the 15.3/11.1-point
lift the whole undifferentiated bearish-call population already gets over
base rate. It is not nothing, but it is not a clean break either.

## The axes that did not separate, in one line each

- **A1 (Exit vs. Trim).** The analyst essentially never issues "Exit" on its
  own — 1 call in train, 0 in tune — so there's no real second bucket to test.
- **A2 (Broken vs. Weakening).** Same shape: "Broken" appears once per split.
  Weakening is effectively the whole bearish population.
- **A3 (number of blind spots flagged).** Looked promising on train (more
  flags, higher hit rate) but reversed on tune (more flags, lower hit rate).
- **A4 (type of problem: structural vs. execution vs. discovery).**
  Structural was the strongest bucket on train and the weakest on tune.
- **A7 (whether the core business mechanism is impaired).** True was the
  strongest bucket on train, the weakest on tune.
- **A8 (how deep a cut the analyst recommends).** Direction flipped between
  splits, and the deeper-cut buckets are too thin (7–15 calls) to trust
  either way.

---

## What this means for a decision

This run does not decide whether P1 should run — that is Luis's call, made
in conversation, not here. What it establishes is the premise P1's case
depends on: **can something downstream sort strong bearish calls from weak
ones, so that added coverage (more bearish calls, from thinner evidence) can
be trimmed lightly instead of uniformly?**

- **If Luis wants P1 to run as-is:** the allocator currently has only one
  reasonably reliable lever to size trims by — credibility direction — and
  it's a soft one (10–13 points, overlapping ranges), not a hard cutoff. P1's
  predicted precision drop (toward the 46.6% base rate) would land on calls
  the allocator can only partly distinguish. That's a real but limited
  safety net, not the clean "sort by conviction" story the run set out to
  test for.
- **If Luis wants a stronger sorting signal before running P1:** this run
  found none among the fields the analyst currently emits. The candidates
  that reversed (blind-spot count, stumble type, mechanism-impaired, cut
  depth) aren't just weak — they actively point the wrong way on fresh
  data, which rules out using any of them as-is for sizing. A precision-
  focused prompt candidate, or a redesign of what the analyst reports for a
  bearish call, would need to happen before — or instead of — P1, if the
  allocator is meant to lean on analyst-reported strength.
- **If nothing changes:** say so plainly — and here, something did change:
  this run gives Luis one real (if modest) lever that didn't exist as a
  documented, tested fact before. It is not free of noise, but it is not
  nothing either.

---

## What was deliberately not done

- No candidate queue reordering, no `PROMPT_ARCHITECTURE.md` edits, no
  registration of a new candidate. Out of this run's scope by design.
- No attempt to chase why NOVA doesn't appear in either eval directory
  despite being named in the prompt and state-of-play as affected — flagged,
  not resolved.
- No attempt to combine axes (e.g., credibility-negative AND high blind-spot
  count) — the prompt scoped this to single-axis splits only; a combined
  read would need its own pre-registration to avoid the same
  screened-on-one-sample trap this run was built to avoid.
- No weighting by dollar exposure (position size) — this run, like the
  underlying scorer, counts every call equally. `PROMOTION_GATE.md` §3.1a
  R2 (magnitude weighting) is open and unrelated to this run's scope.

---

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on the driver — passed, both
  before and after the two mid-run fixes.
- Reproduced all three reference figures exactly (train 103/60.2%/44.9%,
  tune 84/59.5%/48.4%, pooled 187/59.9%/46.6%) before computing any axis.
- Re-ran the full driver end-to-end after each fix; confirmed deterministic
  output (re-running produces identical `cells.jsonl`).
- `git status` confirmed clean before Step 0 (only this run's own new files
  present); driver committed (`8a022ff`) before it produced any output, per
  the resume protocol.

## Follow-up commands

Re-run the full analysis from scratch:

```
cd analysis
python3 q2_bearish_strength_driver.py
```

Re-grade the reference denominators directly against the scorer, for a
cross-check outside this run's driver:

```
cd analysis
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6 \
    --price-cache data/corpus_v2/scorer_price_cache_v1.json
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_claude-sonnet-4-6_tune \
    --price-cache data/corpus_v2/scorer_price_cache_v1.json \
    --allow-partial-coverage
```

Inspect the full per-call join (200 bearish rows, all fields, both splits):

```
cd analysis
column -s, -t data/run_state/q2-bearish-strength-separation/joined_calls.csv | less
```
