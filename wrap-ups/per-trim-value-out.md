# Per-trim value of B's bearish flags, against a no-skill control — wrap-up

**Prompt:** `prompts/per-trim-value.md`. **Run ID:** `per-trim-value`.
**Cost:** $0 — no API calls, no DB writes, no scoring, no cache refresh.
**Status: blocked on one of two destinations.** SPY is fully computed and
reported below. QQQ could not be computed at all — it is absent from the
price cache this pipeline's tradeable-entry ruler is built from. **This is
not a "close enough" partial result; it is a hard stop the prompt's own Step
0.5 preflight calls for**, so the full pre-registered reading (which needs
both destinations) cannot be delivered. What follows is what the reading
would say if only the SPY leg existed.

> Over the 374 calls B flagged on train (pooled over both draws), moving 2.5
> points of the book into SPY made **0.1381** points per trim (**$138** on
> $100,000); a trim of a random name in the same quarter made **0.0283**. The
> analyst's contribution is **0.1098** points per trim (range **−0.0998** to
> **0.3038**). **Into QQQ: not computed — QQQ is absent from the price
> cache** (see "What blocked the QQQ leg," below); the pre-registered reading
> needs both. Under the reading fixed before the run, applied to the leg that
> exists: **A's own range includes zero, so on this evidence alone, protection
> does not clearly pay** — before even netting the no-skill control. The best
> 10% of trims supplied 145% of the pooled total; the worst 10% cost 198% of
> it (the total itself is small and sits close to zero, so these shares swing
> on a handful of calls — see the tail table). Sized by P9 severity, the
> contribution per point moved is **0.2274** against **0.0439** unsized: the
> P9 layer **adds value** on the SPY leg, on the pre-registered per-band
> ordering and on sized A − B per point.

---

## What blocked the QQQ leg

`prompts/per-trim-value.md` names `analysis/p6_output_format_analysis.py` as
the pattern to follow for prices. That module resolves prices via
`PriceCache(REPO / d.PRICE_CACHE_REL)`, where
`p6_output_format_driver.PRICE_CACHE_REL` =
`analysis/data/corpus_v2/scorer_price_cache_v1.json`. This is the same file
`r4_horizon_driver.PRICE_CACHE` points at and the one the tradeable-entry
ruler (`rel_ret()`, and `calls.csv`'s `fwd_rel_ret_tradeable`) is built from
everywhere else in this pipeline.

That file holds 172 tickers. SPY is one of them. **QQQ is not in it at all**
— confirmed by listing every key in the file; there is no `QQQ` entry at any
date, not a gap in an otherwise-present series.

There is a different, unrelated file, `analysis/data/price_cache.json`, that
does hold QQQ (1,591 dates) and SPY (1,596 dates). It is not the cache this
pipeline's ruler is built from, and using it would mean computing the SPY leg
from one price series and the QQQ leg from a different one — an undeclared
substitution, not a fix, and exactly the kind of thing Step 4 of the
execute-prompt workflow says to flag rather than route around. **No fetch was
made and no substitution was made**, per the prompt's own ground rules ($0,
no cache refresh) and per Step 0.5's "If QQQ is missing or has gaps, stop and
report. Do not fetch."

**This run does not decide** whether to add QQQ to the canonical cache and
re-run, drop QQQ as a destination going forward, or something else. That is
for the design session.

---

## Preflight (Step 0.5)

- SPY: present, full span. QQQ: absent entirely (see above).
- All 1,217 train calls priced on the name + SPY legs (0 dropped).
- Sanity check (name return minus SPY return reproduces `fwd_rel_ret_tradeable`
  to 4 decimals): **max mismatch 0.0001** — within rounding of the two
  independent computations (this script's own price lookups vs. the value
  already stored in `calls.csv`).

## Step 1 — base result: fixed 2.5-point trims into SPY

Rows: **A** = B's flagged calls (score ≤ −2). **B matched** = quarter-matched
no-skill control (reply 2's refinement — same calendar quarter as each flagged
call, not just any train call). **B unmatched** = every train call, reference
only. **A − B** = the analyst's contribution. All in points of the book; $ is
on $100,000. Ranges: 95% ticker-block bootstrap, 2,000 draws, seed 11, A / the
quarter averages / A − B recomputed together in each draw.

| | draw 1 (n=191) | draw 2 (n=183) | pooled (n=374) |
|---|---|---|---|
| A mean | 0.1531 ($153) | 0.1223 ($122) | 0.1381 ($138) |
| A range | [−0.0944, 0.3876] | [−0.1667, 0.3914] | [−0.1291, 0.3868] |
| B matched mean | 0.0296 | 0.0269 | 0.0283 |
| B unmatched mean (ref.) | 0.0033 | 0.0033 | 0.0033 |
| **A − B** | **0.1235** ($124) | **0.0954** ($95) | **0.1098** ($110) |
| A − B range | [−0.0735, 0.3062] | [−0.1319, 0.3063] | [−0.0998, 0.3038] |
| median (ref. only) | 0.2597 | 0.2519 | 0.2521 |

*Provenance:* `analysis/data/run_state/per-trim-value/results.json` →
`step1_base_result.SPY.{b1,b2,pooled}`.

**Tail decomposition (pooled, n=374, 10% = 37 trims):**

| | share of A's total | n |
|---|---|---|
| best 10% (avoided disasters) | 144.6% | 37 |
| worst 10% (clipped winners) | −198.1% | 37 |
| middle 80% | sums to 79.27 pts | 300 |
| future big winners (beat S&P by 20+ pts) | 52 calls, total value **−112.28 pts** | 52 |

The pooled A total (374 × 0.1381 ≈ 51.7 pts) is close to zero relative to the
size of its best- and worst-10% slices, so those percentages are large and
swing on a handful of calls rather than describing a broad, evenly spread
edge — the same shape the reply anticipated when it asked for this
breakdown. `results.json` → `step1_base_result.SPY.pooled.tail`.

## Step 2 — the P9 severity layer (SPY)

Bands: within each A set, rank by averaged P9 `expectedReturn` (most negative
first, ties broken by a seed-11 shuffle over calls in that A set), cut into
fifths, size = 5 / 2.5 / 0 / 0 / 0 points.

**Value per point by band, pooled (n=374):**

| band | n | trim size | value/point | range |
|---|---|---|---|---|
| 1 (most negative P9) | 75 | 5.0 | **0.3029** | [0.1139, 0.4612] |
| 2 | 75 | 2.5 | 0.1308 | [0.0415, 0.2835] |
| 3 | 75 | 0 | 0.1182 | [0.0040, 0.2242] |
| 4 | 75 | 0 | −0.0029 | [−0.2055, 0.1421] |
| 5 (least negative) | 74 | 0 | −0.2775 | [−0.6271, 0.0118] |

Ordering condition (band 1 > band 2 > rest of bands 3–5, n-weighted mean
≈ −0.053): **holds** — 0.3029 > 0.1308 > −0.053.

**Sized total, pooled:**

| | value |
|---|---|
| sized A mean | 0.3693 [0.1650, 0.5802] |
| sized A − B | **0.3420** [0.1460, 0.5158] |
| sized A − B per point moved | **0.2274** [0.0968, 0.3412] |
| Step 1's (unsized) A − B per point | 0.0439 |
| **P9 adds value vs. Step 1** | **yes** |

Per-draw sized A − B per point: draw 1 = 0.2335 (vs. Step 1's 0.0494), draw 2
= 0.2118 (vs. 0.0382). Same conclusion both draws.

**Note per reply 2, not a change to the sizes.** The settled allocator moves
a position at most 2.5 points per session. The 5-point band would execute
over two monthly sessions on the real allocator; its second half would see
one more month of price than this per-trim measurement assumes. The 2.5 and
0 sizes are unaffected.

`results.json` → `step2_p9_severity.SPY.{b1,b2,pooled}`.

## Step 3 — the guidance-veto layer (reported only, SPY)

Beat-and-raise calls removed from A (`raised == "yes" and beat == "yes"` in
`analysis/data/run_state/winners-missed-v3/read_labels_v3.jsonl`).

| | draw 1 | draw 2 | pooled |
|---|---|---|---|
| n removed | 0 | 1 | 1 |
| vetoed A mean | 0.1531 | 0.1225 | 0.1382 |
| vetoed A − B | 0.1235 [−0.0735, 0.3062] | 0.0959 [−0.1339, 0.3065] | 0.1100 [−0.1000, 0.3047] |
| removed calls' mean value | n/a | 0.0840 | 0.0840 |

One flagged call carries the beat-and-raise tag on this train sample (not
the 15 the prompt's framing note mentions from the original count — this run
only removes tags that land inside B's flagged set, which is a much smaller
population than "all train calls"). Removing it moves the pooled A − B by
about 0.002 points, essentially nothing. As specified, **this cannot change
the Step 1 verdict** and is not part of the pass/fail reading.

`results.json` → `step3_guidance_veto_reported_only.SPY.{b1,b2,pooled}`.

## Deviations from the prompt

1. **QQQ leg not computed — reported above, not a scope call made by this
   run.** Everything else in the prompt (both draws, pooled, the tail
   breakdown, the P9 bands and sizing, the veto layer, the sanity check) ran
   exactly as specified, on the SPY leg.
2. `analysis/per_trim_value.py` reuses `p6_output_format_analysis.load_calls`,
   `.spearman` (unused here but imported per the "import, don't fork" rule),
   `p3_guidance_ledger_driver.read_jsonl` / `.wilson`, and
   `r4b_tradeable_entry_driver.p_after`, plus a fresh `PriceCache` read for
   name/SPY/QQQ raw returns (the existing `rel_ret` only returns the
   name-minus-benchmark difference, not the two legs separately, which this
   prompt's per-destination definition needs).
3. P9's severity values were read from `per_call_diffs.csv` /
   `per_call_diffs_draw2.csv` (already-computed `expectedReturn` per call)
   rather than re-parsing `scores_p9.jsonl` / `scores_p9_rerun1.jsonl` raw
   content — same numbers, already validated by `p9_averaged_comparison.py`,
   cheaper to read.

## What this cannot show (per the prompt, restated)

This is train data, already seen elsewhere in this pipeline. Trims are
measured one at a time, not as a book — it says nothing about drawdown,
turnover, taxes, or what happens when many names are flagged in the same
month. That is the book test, which was already queued to come next
regardless of this result.

## What it means, both ways

- **If the QQQ leg, once computed, also lands with A's own range including
  zero** (which is what the reply's framing treated as the likely outcome for
  a destination that didn't have QQQ's own tailwind over the period): the
  reading is **protection does not pay**, and the allocator rebuild does not
  proceed on B's trims — full stop, before the sleeve/index question is even
  reached.
- **If the QQQ leg instead clears zero on A itself** but A − B does not: the
  reading becomes **the index does the work**, which sends the sleeve/index
  decision ahead as "index by default, flags optional," not as evidence the
  analyst adds anything.
- **If the QQQ leg clears zero on both A and A − B**: only then does the
  P9-layer result above (which already shows real work — sized A − B per
  point roughly 5× the unsized figure, and a clean band ordering) become
  something to act on, and the book test proceeds with B's trims.

**The SPY evidence alone points toward the first of these**, but the run
cannot say which one holds without the QQQ leg, and per the prompt's own
Step 0.5, this run does not substitute or fetch to get there.

## Follow-up commands

Reproduce this run's output:

```
python3 analysis/per_trim_value.py
```

Confirm QQQ's absence directly:

```
python3 -c "import json; d=json.load(open('analysis/data/corpus_v2/scorer_price_cache_v1.json')); print('QQQ' in d, sorted(d.keys()))"
```

## Git

- Prompt already committed at `5465845` (prior session, before this run
  started).
- Driver (`analysis/per_trim_value.py`) + `progress.json` committed at
  `f0b5e6a` before running, per Step 0/CLAUDE.md rule 9.
- This wrap-up, `results.json`, and `findings.md` committed next, then
  `git push` of `sweep/db-corpus-baseline` — pushed hash reported in chat.
