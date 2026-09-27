# Consensus surprise — one-day screen on 20 train companies. Wrap-up

**Run ID:** `consensus-surprise-screen`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial. $0.** **17 of 22 allowed Alpha Vantage requests used** (3 of the 20 companies reused their `EARNINGS` responses verbatim from `p5-close-sector-drift`'s probe: MU, RUN, JPM). No rate-limit message on any request. No Claude API calls, no scoring.
**Scope boundary: report, do not decide.**

> Inside **20** winner-rich companies, big-winner calls beat consensus **76.9%** of the time against **74.0%** for the same companies' middle calls; their median quarter-adjusted surprise was **+0.0097** against **+0.0005** (difference **+0.0092**, range **−0.0236 to +0.1341**): **can't tell — surprise does not separate winners at this size, but the range does not rule it out either**. Big losers against the middle: **−0.0220** (range **−0.0765 to +0.0638**). Surprise relates to the announcement-day move at **0.203**. Across the **439** matched calls, surprise against consensus (scaled by price) ranked six-month returns at **0.074** (range **−0.022 to 0.161**); this sample could detect an effect of about **0.091** or larger. Its top 19% held **33.7%** big winners against 12.6% (range 24.5 to 44.4) — **reported only, not evidence, because this sample is winner-rich by design**. Combined with B: **0.138** (range **0.049 to 0.224** — clears zero), combined minus B **+0.047** (range **−0.034 to +0.129**). **Screen reading: can't tell at this size** (the strict pre-registered case-control test reads "does not"; the pooled combined-with-B rank correlation reads positive; neither is decisive).

Sources: `analysis/data/run_state/consensus-surprise-screen/` → `selection.json` (Step 1), `fetch_status.json`, `screen_results.json` (Steps 2–3). Scripts: `consensus_screen_select.py`, `consensus_fetch.py` (shared, reused unchanged by the full test), `consensus_screen_test.py` (shared). Ranges are 95% ticker-block / company-block bootstrap (2,000 draws, seed 11).

## Step 0 — bookends and the review check
This prompt, `prompts/consensus-surprise-test.md` (the full prompt this screen reuses), and `docs/handoffs/2026-09-27-consensus-screen-review-brief.md` were each committed as their own commit; `docs/handoffs/2026-09-27-consensus-screen-review.md` was already tracked. **Verified before running:** the screen's and the full test's "Review amendments" sections are byte-identical (`diff` empty), so the review's changes are reflected in both, and no discrepancy required a stop.

## Step 1 — the 20 companies (`selection.json`)
51 train companies considered after excluding FRC, MAXN, SUNW, VIAC/PARA. Exactly **20** met the winner-rich bar (≥ 2 big-winner calls, ≥ 6 other) with no tie-break needed beyond the ranking itself. RUN (4 winners / 11 other), MU (9 / 15) and JPM (3 / 21) all qualified and are in the sample; their `EARNINGS` responses were reused verbatim from the earlier probe, at **0 additional cost**. The other 17 companies were fetched fresh: LLY, EOSE, NEM, PSX, OXY, COF, HCA, NOW, AMPX, MRK, QCOM, TMO, INTC, JKS, TTD, DD, WMB. **0 rate-limit messages** on any of the 17 fetches (13-second spacing, under 5/minute).

**Why this is a within-company comparison, restated:** these 20 companies were chosen *for having winners*, so item 2/3's market-wide rates below are inflated by construction and are not compared against 12.6% anywhere in this report's readings.

## Steps 2–3 — matching, quarter-adjusted surprise, the test
**Matching:** 439 of 445 train calls in the 20 companies matched an AV quarter within ±3 days (98.7%); 6 unmatched (missing EPS or price, or an overlap failure — none from a rate limit). **Quarter-adjusted SUE_p**: each matched call's SUE_p minus the median SUE_p of all matched calls reported in the same calendar quarter; quarter medians rest on 12–20 calls (one exception: 2025Q4 rests on 1 call, itself, so no comparison group used it as a denominator).

### Primary reading (review change 1: three groups, case-control)

| | median SUE_p_adj | n |
|---|---|---|
| big winners | +0.0097 | 104 |
| middle | +0.0005 | 245 |
| big losers | −0.0215 | 90 |

**Winner − middle: +0.0092, range −0.0236 to +0.1341.** The range's lower end is barely negative — the pre-registered reading is **"does not"** (surprise separates winners), but by a margin small enough that the range's upper end (+0.134) is a real positive possibility this sample cannot rule out. **Loser − middle: −0.0220, range −0.0765 to +0.0638** — reported beside it, as required; it does not earn "finds winners" on its own, and doesn't need to.

**Luis's original case-control framing** (winner calls vs. the same companies' other calls, not the three-way split): beat rate 76.9% vs 74.0% — both high, as the prompt itself predicted ("roughly three quarters of large companies beat consensus in a typical quarter"), so this gap is not informative on its own. Median SUE_p_adj difference **+0.0107, range −0.0169 to +0.1383** — same picture as the three-group version, range includes zero. **Within-company**: 12 of 20 companies (60%) had their winner-quarter mean SUE_p_adj above their other-quarter mean, against 50% expected by chance — a mild lean, not tested for significance at this n.

### Pooled rank correlation (test item 1)

| | with flagged companies (n=439) | excluding flagged (n=385) |
|---|---|---|
| SUE_p_adj alone | 0.074 (−0.022 to 0.161) | 0.095 (−0.010 to 0.190) |
| own B alone | 0.091 (−0.006 to 0.202) | 0.091 (−0.043 to 0.234) |
| **combined** | **0.138 (0.049 to 0.224)** | **0.154 (0.042 to 0.251)** |
| combined − own | 0.047 (−0.034 to 0.129) | 0.063 (−0.035 to 0.159) |

**Flagged companies** (review change 3): EOSE, JKS, RUN — each has ≥ 50% of matched quarters with `surprisePercentage` beyond ±100%, a sign of a small or negative EPS base (percentage surprise explodes near zero; this is exactly why SUE_p is scaled by price, not by the estimate). Excluding them makes every figure slightly stronger in the same direction, so the flag doesn't explain the pattern away.

**SUE_p_adj alone does not clear zero. The combined-with-B rank correlation does** (0.049 to 0.224). **This sample's resolution** (the half-width of SUE_p_adj's own range) is **0.091** — the point estimate (0.074) sits just below that, which is the textbook shape of "can't tell", not "confirmed."

**Item 2, winners question (reported only, not evidence — this sample is winner-rich by design):** top 19% by SUE_p_adj: 47.0% right, **33.7%** big winners (Wilson 24.5–44.4). By combined: 50.6% right, 30.1% (21.3–40.7).
**Item 3, downside:** bottom 16% by SUE_p_adj: 47.1% right (n=70) — unremarkable, but again not comparable to B's published 62.3%/61.3% in this sample.
**Item 4, persistence:** 260 of 438 testable calls beat both this and the prior fetched quarter; their big-winner share (22.7%) is actually **lower** than non-persistent calls (25.3%) — no persistence effect, wrong-signed if anything, small n, not gated.
**Item 5, by year and sector-year:** no consistent sign across years (2024: −0.223, n=80; 2025: +0.366, n=78; others mixed). Within sector-year (17 cells ≥ 12 calls, 225 of 439 calls, 51%): weighted rho **−0.001**, essentially zero.
**Item 6, overlap with r0:** rho(SUE_p_adj, r0) = **0.203** (n=439) — positive, but well under the 0.5 threshold that would trigger the closing-rule exception.

### Closing rule (review change 4)
Screen is not clearly negative, and rho with r0 (0.203) is under 0.5 → **the exception does not apply.** This screen alone cannot close the lead.

### Spot-check rows (review change 3)
Seeded within the top and bottom 5% of SUE_p_adj (3 top, 2 bottom): **JKS 2023-08-14** (SUE_p_adj +6.228), **EOSE 2024-03-05** (+8.830), **EOSE 2023-03-01** (+8.651), **EOSE 2022-02-25** (−3.043), **EOSE 2021-02-25** (−10.741). **All five are EOSE or JKS** — both flagged companies; small-EPS-base companies dominate the extreme tails of a price-scaled surprise measure. **Per the prompt: if any of these five is later found revised or mismatched, the reading drops to "can't tell" whatever the numbers say** — and the numbers already say "can't tell," so this caveat does not currently change the conclusion, but it does mean the five rows worth checking are concentrated in exactly the companies flagged for basis mismatch, which is itself worth noting to whoever checks them.

## Deviations, flags, premises
1. No deviations from the prompt's construction. The `screen_3groups_sue_p_raw` block (unadjusted SUE_p) was also computed, as the review requires reporting raw beside adjusted; not tabulated above for space, in `screen_results.json`.
2. `consensus_fetch.py` and `consensus_screen_test.py` are written to be reused unchanged by the full test, taking only a `run_dir` argument; verified by running against this screen's own `run_state` directory without modification needed.
3. The full test's Step 1 fetch order (alphabetical, 57 companies) differs from this screen's winner-rich order by design — the full test's `selection.json` shape (`fetch_order` vs `selected`) is handled by `consensus_fetch.py`'s fallback key lookup, though this was not exercised in this run since only the screen's `selected` key was used.

## What this means

**Not a clear positive, not a clear negative — can't tell at this size, which the prompt said to expect from 20 companies.** The case-control reading (the review's primary test) does not clear zero, but only barely, and the pooled rank correlation combined with B does clear zero. The point estimate for SUE_p_adj alone (0.074) sits below this sample's own detection floor (0.091) — a textbook "too small to tell," not a textbook "nothing there."

**Per the closing rule, this does not close the lead**, and the prompt's own framing (a screen can only reveal a large effect) means a flat reading here is expected, not damning. **The decision this sets up:** run the full test (`prompts/consensus-surprise-test.md`, all 57 train companies, resumable over about 3 free days) to get the resolution this screen doesn't have. Given the combined-with-B figure and the within-company 60%-of-20 lean both point the same direction as the pre-registered mechanism, even without clearing significance, this looks like the more promising of the closed-or-continuing leads to spend those 3 free days on, rather than a lead to abandon here — but that prioritization call is Luis's, not this run's.

## Not done
The full 57-company test, any point-in-time verification of the 5 spot-check rows against a dated external source, any pre-registered candidate, any scoring, any DB write, any cache refresh.

```bash
python3 analysis/consensus_screen_select.py
python3 -c "import sys; sys.path.insert(0,'analysis'); import consensus_screen_test as T; T.run('consensus-surprise-screen')"
```
