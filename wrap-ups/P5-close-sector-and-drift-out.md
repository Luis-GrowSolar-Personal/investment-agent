# Close P5; test a sector score and the announcement-day move; probe consensus data. Wrap-up

**Run ID:** `p5-close-sector-drift`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial. $0** (no Claude API calls, no vendor calls, no scoring). **3 of 6 Alpha Vantage requests used.**
**Scope boundary: report, do not decide.** These are after-the-fact checks on train data B has already been scored on. Nothing is promoted.

> P5 is recorded as closed (commit `cb41840`). A sector score built from B's recent calls in the same industry ranked six-month returns at **0.030** (range **−0.063 to 0.125**), against B's own **0.110**; combined, **0.094** (combined minus own **−0.016**, range **−0.071 to 0.043**): **no sector gain**. The announcement-day move ranked them at **−0.033** (range **−0.098 to 0.035**), and its top 235 held **14.5%** big winners against 12.6% (Wilson range 10.5 to 19.5, includes the base rate): **drift not present · does not find winners · does not add to B** (combining it with B's own score made ranking measurably **worse**, range −0.112 to −0.023). Alpha Vantage **does** hold consensus EPS back to **2019** for all three probe companies (30 of 30 quarters each), with `reportedDate`, `reportedEPS`, `estimatedEPS`, `surprise` and `surprisePercentage` present on nearly every row back to 1996 (MU, JPM) or 2015 (RUN).

Sources: `analysis/data/run_state/p5-close-sector-drift/` → `sector_score.json` (Step 2), `drift.json` (Step 3), `av_probe.json` + `av_MU.json`/`av_RUN.json`/`av_JPM.json` (Step 4). Scripts: `p5close_sector_score.py`, `p5close_drift.py`, `p5close_av_probe.py`. Ranges are 95% ticker-block bootstrap (2,000 draws, seed 11).

## Step 1 — P5 closed (commit `cb41840`)
- `PROMPT_ARCHITECTURE.md` §2.2 P5 row: "closed 2026-09-27 at phase 2a…", plus a five-line **P5 — Result** paragraph under the block, giving the by-rule figures (S1 +0.066; S2 −0.219, below zero; C1 flat; C2 strong but uncontrolled).
- `analysis/data/gate_ledger.json` entry 6: `final_verdict: "STOPPED (map gate)"`, every figure cited to the phase 2a wrap-up. **Cost correction while writing this entry:** the prompt suggested `cost_usd` ≈ 19.35 (with roughly $0.11 attributed to phase 0/0b probes); checking the actual wrap-ups, phase 0b's only spend was $0.0197 (its link-type read), and phase 0 was $0. The entry records **$19.26** (phase 1's $19.24 + phase 0b's $0.02), not the prompt's suggested figure, with a note explaining the correction.
- `docs/peers/README.md`: a new section naming `peer_links_tight.csv` as the kept allocator input, with its column meanings.

## Step 2 — sector score: **no sector gain**
| | rank correlation | range |
|---|---|---|
| sector score alone | 0.030 | −0.063 to 0.125 |
| own B score alone | 0.110 | 0.010 to 0.204 |
| combined (avg percentile rank) | 0.094 | −0.014 to 0.192 |
| combined − own | −0.016 | −0.071 to 0.043 |
| sector − own | −0.079 | −0.175 to 0.021 |

**Coverage:** 691 of 1,217 train calls (56.8%) have a sector score (≥ 3 eligible calls from ≥ 2 companies, dated strictly before and within 45 days, pooled train+tune). By sector: industrials 162, banks/financials 93, pharma/health 87, semis 79, software/IT 69, energy 44, consumer staples 39, solar/storage 37, materials 34, utilities 27, internet/media 20.

**Neither reading condition is met.** Sector alone doesn't clear zero, and combined minus own doesn't clear zero (its point estimate is even slightly negative). **Bottom-15%/top-20% cuts confirm it**: own-score cuts (bottom 61.5%, top 42.0%) are close to B's published bottom-191/top-235 figures (62.3%/61.3%, 39.6%/36.2%), while sector-based and combined cuts are weaker (sector bottom 48.1%; combined bottom 51.9%, top 36.2%) — blending in the sector average pulls B's own hit rate down, not up. **The portfolio-relevant sectors** (semis + solar/storage/clean energy + software/IT pooled, n=185) show the same pattern with wider ranges: sector 0.012 (−0.189 to 0.202), own 0.112 (−0.066 to 0.297), combined 0.084 (−0.101 to 0.255) — no sector gain there either.

## Step 3 — the announcement-day move: **drift not present**
All 1,217 train calls scored; 0 dropped for missing prices; the assertion that r0's end date equals the 182-day grading window's own start held for every row (no overlap).

| | rank correlation | range |
|---|---|---|
| r0 alone | **−0.033** | −0.098 to 0.035 |
| own B alone | 0.121 | 0.043 to 0.194 |
| combined | 0.051 | −0.021 to 0.120 |
| combined − own | **−0.070** | **−0.112 to −0.023** |

**All three pre-registered readings are false, and this contradicts the prompt's own framing** (post-earnings drift as "one of the best-documented patterns in markets") — reported as a finding, per the standing instruction, not a reason to adjust the method.
- **Drift present: false.** The range doesn't clear zero, and the point estimate is slightly negative.
- **Drift finds winners: false.** Top 235 by r0: 36.6% right, **14.5% big winners** (34 of 235) against the 12.6% base — the point estimate is above base, but the Wilson range (10.5 to 19.5) includes it. Top 235 by combined: 13.6% (9.8 to 18.6), same pattern. Bottom 191 by r0: 53.4% right, below B's 62.3%/61.3%.
- **Drift adds to B: false, and cleanly so.** Combined minus own's range is entirely **below** zero (−0.112 to −0.023) — adding the announcement-day move to B's own score makes the ranking measurably worse, not just "no better."

**By year**, no consistent positive drift: 2021 is the most negative (−0.200), 2023 the only clearly positive year (+0.060), the rest near zero or mildly negative; 2020 and the rest of the years are both near zero (−0.014 and −0.037). **Within sector-year** (55 cells with ≥ 12 calls, 86.9% of calls): weighted rho −0.039, consistent with the pooled figure — no sector or year hides a positive signal the pooled number is missing.

## Step 4 — Alpha Vantage consensus probe: **holds back to 2019, and much further**
3 requests (MU, RUN, JPM), 15 seconds apart, all status 200, no rate-limit notice in any response.

| | MU | RUN | JPM |
|---|---|---|---|
| quarters returned | 122 | 45 | 122 |
| earliest fiscal quarter | 1996-02-29 | 2015-06-30 (IPO year) | 1996-03-31 |
| fields present (of 122/45/122) | reportedDate 122, reportedEPS 122, estimatedEPS 121, surprise 122, surprisePercentage 121 | all fields, all 45 | all fields, all 122 |
| quarters from 2019 on | 30 | 30 | 30 |
| …with non-empty `estimatedEPS` | **30 of 30** | **30 of 30** | **30 of 30** |

All five fields the prompt asked about are present. **This cannot show whether `estimatedEPS` is the consensus as it stood before the report or a figure restated later** — the endpoint returns one value per historical quarter with no timestamp on the estimate itself, so a later analyst revision could be silently baked in. **Suggested check, not run:** compare 2–3 quarters' `estimatedEPS` against a dated external consensus source (e.g. a contemporaneous news article or a vendor with point-in-time snapshots) to see whether it matches the pre-report number or a later-settled one.

**Rate limit and plan, from the response and account:** no `Note`/`Information` throttling message appeared on any of the 3 calls; Alpha Vantage's free tier is documented elsewhere as 25 requests/day, 5/minute — this probe used 3 of a day's allowance. **A full corpus pull is 164 requests, one per company** (the `EARNINGS` endpoint returns full history in one call, no per-quarter pagination needed) — at 5/minute that is about 33 minutes of wall time, but at the free tier's 25/day cap it would take **7 days** minimum unless a paid plan is used.

## Deviations, flags, premises
1. **Cost correction in the ledger entry** (Step 1) — flagged above; the prompt's suggested `cost_usd` figure was not exact and I corrected it against source wrap-ups.
2. Step 2's sector score construction pools train (mean of two draws) and tune (single draw) scores for the sector average, exactly as specified; no deviation.
3. Step 3's `combined` uses percentile rank of r0 and own B, averaged, as specified.
4. No gate in this prompt stopped the run; every reading is reported as computed, including the two clean negatives (S3's combined-minus-own, and its false "drift present").

## What this means

**For the allocator rebuild:** the tight peer map stays a kept input for correlated positions, independent of today's null results. Neither the sector score nor the announcement-day move gives the allocator a usable signal on this evidence; both are closed leads, not just untested ones — the announcement-day move in particular is not just absent, it actively hurts B's own ranking when blended in.

**For finding winners:** three separate routes have now failed to find B's missing bullish signal — winners-missed (beat-and-raise, v1–v3), P5's peer read-through, and this run's sector average and announcement-day drift. **Consensus data remains untested and is now known to be cheaply available**: Alpha Vantage's free tier holds what's needed for the three probe companies, and a full 164-company pull is feasible in a week on the free tier or immediately on a paid one. That is the one lead this run adds rather than closes, with the important caveat that its point-in-time status is unverified.

## Not done
The suggested point-in-time check on `estimatedEPS`, the full 164-company Alpha Vantage pull, any consensus-based candidate, any scoring, any DB write, any cache refresh.

```bash
python3 analysis/p5close_sector_score.py
python3 analysis/p5close_drift.py
```
