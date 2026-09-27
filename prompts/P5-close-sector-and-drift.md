# Close P5; test a sector score and the announcement-day move; probe consensus data. $0

**Run ID:** `p5-close-sector-drift`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P5-close-sector-and-drift-out.md`
**Cost: $0.** No Claude API calls, no vendor calls, no scoring. At most
**6 Alpha Vantage requests** (Step 4). Uses B scores and prices already on
disk.

---

## Framing

1. **P5 stopped on its pre-registered gate** (`wrap-ups/P5-phase2a-tight-map-out.md`).
   - A linked peer's reaction predicted the target's pre-call move at
     0.093 against 0.063 for controls. The difference range was −0.027 to
     +0.146, which includes zero.
   - Against the target's next six months it predicted nothing (0.005).

   Record that. Keep the tight peer map as an allocator input.
2. **Sector score.** Phase 1 found B ranks **across** sectors better than
   **within** them: 0.070 and 0.046 within sector-year, against 0.130 and
   0.099 overall. If B's edge is largely industry-level, an **average of
   B's scores across a sector's recent calls** may predict better than
   one company's score. For a portfolio concentrated in a few sectors,
   that is the useful form.
3. **The announcement-day move.** Nothing so far helps pick winners.
   - Stocks that jump on their earnings tend to keep drifting for months
     (post-earnings-announcement drift). The jump is the market's verdict
     on whether the quarter beat expectations.
   - It has never been tested here. It uses the company's **own** price
     history, which the firewall allows (`PROMPT_ARCHITECTURE.md` §1.4).
   - Our 182-day grading starts at the first close **after** the call,
     so the jump itself is outside the graded window.
4. **Consensus data probe.** The documented bullish signal is beating
   **analyst consensus**. Finnhub's free tier holds 4 quarters. Check
   whether Alpha Vantage's earnings endpoint (key `AV_API_KEY` in `.env`)
   holds consensus EPS history back to 2019, before any subscription is
   bought.

**Read first:** `wrap-ups/P5-phase2a-tight-map-out.md`,
`wrap-ups/P5-phase1-peer-map-out.md` (Step 1: sector diagnostics),
`wrap-ups/winners-missed-v3-out.md`; `docs/peers/SECTOR_MAP.csv`;
`analysis/p5p1_step1.py` (extend it for Step 2 and Step 3; do not fork).

## Ground rules

1. **Train targets only.** Returns are read for train calls only. Tune
   **B scores** may be read as sector inputs (scores, not returns). No
   holdout anything.
2. Prices from `analysis/data/corpus_v2/scorer_price_cache_v1.json`. No
   fetching prices.
3. **Every reading is fixed here before any number is computed.**
4. These are after-the-fact checks on train data B has already been
   scored on. A pass justifies a pre-registered candidate. It promotes
   nothing.
5. Report, do not decide.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/p5-close-sector-drift/`. `progress.json`
first. Commit this prompt as its own commit. Any other modified or
untracked file → stop and report. Clean tree. Scripts committed before
output.

---

## Step 1 — close P5 ($0, one commit)

- **`PROMPT_ARCHITECTURE.md` §2.2 P5 row:** "closed 2026-09-27 at phase
  2a. The lead-lag gate failed (x→y1 +0.030, range −0.027 to +0.146;
  x→y2 +0.036, range −0.120 to +0.275). Tight peer map kept as an
  allocator input." Add a result paragraph of at most five lines under
  the P5 block. It records by-rule:
  - S1 +0.066 (range −0.012 to +0.331);
  - S2 −0.219 (range −0.500 to −0.093), **below zero**;
  - C1 flat;
  - C2 strong but uncontrolled (27 pairs).
- **`gate_ledger.json` entry 6:** P5 phase 2a, `final_verdict: "STOPPED
  (map gate)"`, figures cited to the phase 2a wrap-up, `cost_usd` 19.24
  (phase 1) plus about 0.11 (phase 0b and earlier probes).
- **`docs/peers/README.md`:** add that `peer_links_tight.csv` in
  `analysis/data/run_state/p5-phase2a/` is the kept allocator input, and
  what its columns mean.

Commit: `docs: P5 closed at phase 2a (lead-lag gate); tight peer map kept for the allocator`.

## Step 2 — sector score ($0)

**Construction, point in time.** For each **train** call T (sector group
from `SECTOR_MAP.csv`):
- **Sector score** = the mean B score of **other companies' calls** in
  T's sector group, dated **strictly before** T and **within the prior 45
  days**, from train and tune.
  - For train calls use the mean of B's two draws.
  - For tune calls use B's single tune draw (`scores_b_tune.jsonl`).
  - Require at least **3** such calls, from at least **2** companies.
    Otherwise T has no sector score.
- **Own score** = T's B score, the mean of its two draws.
- **Combined** = the average of the two, each first converted to a
  percentile rank across the eligible calls.

Report, on train calls with a sector score:
1. **Coverage:** how many train calls, overall and by sector group.
2. **Rank correlation with the 182-day tradeable-entry return vs SPY**,
   for sector score, own score and combined, each with a ticker-block
   range (2,000 draws, seed 11).
3. **Paired differences:** combined minus own, and sector minus own, with
   ranges.
4. **Bottom 15% and top 20% by each score**, the same shares as B's
   191/235 of 1,217: hit rate (lag / beat by more than 5 points) and
   median return.
5. **The portfolio-relevant line:** the same three correlations restricted
   to semis, solar/storage/clean energy, and software/IT, pooled.

**Pre-registered reading:**
- **"Sector score carries B's edge"** if the sector score's own range is
  above zero.
- **"Sector score adds to B"** if combined minus own has its range above
  zero.
- Otherwise **"no sector gain"**.

## Step 3 — the announcement-day move ($0)

For each **train** call:
- **r0** = the stock's return vs SPY from the **last close before the
  call** to the **first close after the call** (the tradeable entry). If
  those are the same day, use the next close. **r0 ends exactly where the
  182-day grading window begins.** Assert no overlap.
- Test r0 alone, B alone, and combined (average percentile rank of r0
  and B's own score).

Report:
1. Rank correlation with the 182-day return, for r0, own B and combined,
   each with its range. Paired combined minus own B, with its range.
2. **The winners question.** The top 235 calls by r0: how many were right
   (beat by more than 5 points), and how many became **big winners**
   (+20 or more)? Compare against B's top 235 (39.6% / 36.2% right) and
   the 12.6% big-winner share. The same for the top 235 by combined
   score.
3. The bottom 191 by r0: hit rate against B's 62.3% / 61.3%.
4. By year, with 2020 separate.
5. **The within-sector line:** r0's rank correlation within sector-year,
   pooled as in phase 1 Step 1c.

**Pre-registered reading:**
- **"Drift present"** if r0's rank correlation has its range above zero.
- **"Drift finds winners"** if r0's top-235 big-winner share is above
  12.6%, with its Wilson range above 12.6%.
- **"Drift adds to B"** if combined minus own B has its range above
  zero.

Report each reading separately.

## Step 4 — Alpha Vantage consensus probe (≤ 6 requests)

Call the `EARNINGS` function for **MU, RUN, JPM** (one request each), at
1 request every 15 seconds. Report:
- whether `quarterlyEarnings` includes `reportedDate`, `reportedEPS`,
  `estimatedEPS`, `surprise` and `surprisePercentage`;
- how far back the history goes;
- how many quarters from 2019 onward have a non-empty `estimatedEPS`.

State plainly that the probe **cannot** show whether `estimatedEPS` is
the consensus as it stood before the report (point in time), or a figure
restated later. Suggest one check for that: compare with a
dated external source for 2–3 quarters, and do not run it.

Also report the AV rate limit and plan the key shows (free-tier notices
in the response), and what a full corpus pull would take. That is 164
companies, one request each.

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/P5-close-sector-and-drift-out.md`, `.md` only. Open with:

> P5 is recorded as closed (commit ___). A sector score built from B's
> recent calls in the same industry ranked six-month returns at ___
> (range ___ to ___), against B's own ___; combined, ___ (combined minus
> own ___, range ___ to ___): **[sector score carries B's edge / adds to
> B / no sector gain]**. The announcement-day move ranked them at ___
> (range ___ to ___), and its top 235 held ___% big winners against
> 12.6%: **[drift present / not] · [finds winners / not] · [adds to B /
> not]**. Alpha Vantage [does / does not] hold consensus EPS back to ___
> for the three probe companies.

Close with what each result means for the allocator rebuild and for
finding winners. Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. **Finish with
`git push`** after the wrap-up commit, and report the pushed hash; on
failure, say so and never force.
