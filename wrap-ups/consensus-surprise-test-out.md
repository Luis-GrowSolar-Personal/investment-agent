# Consensus surprise — full test. Wrap-up

**Run ID:** `consensus-surprise`. Branch `sweep/db-corpus-baseline`. **Complete run, in one session** (premium key removed the daily cap). **$0 marginal.** 37 of 57 companies fetched fresh with `AV_API_KEY_PREMIUM` (never printed or logged); 20 reused verbatim from the screen. 0 rate-limit messages. No Claude API calls, no scoring.
**Scope boundary: report, do not decide.** The verdict below is **PROVISIONAL, pending 8 point-in-time checks** the CLI cannot perform; it is not recorded as final anywhere in this run.

> Among the **859** train calls B did not score bearish, surprise against consensus (quarter-adjusted) ranked six-month returns at **0.069** (range **−0.013 to +0.148**). On the **542** unscreened companies' calls: **0.010** (positive, essentially flat). With each year left out, the lowest figure was **0.020** (year dropped: **2025**). **Provisional reading: fail** (the primary's own range includes zero, so neither "clean", "borderline", nor "one year's effect" applies); sector label: **n/a** (no label is assigned when the primary does not pass). **Pending 8 point-in-time checks.**

Source: `analysis/data/run_state/consensus-surprise/full_results.json`. Script: `analysis/consensus_full_test.py` (extends `consensus_screen_test.py`'s matching/SUE_p logic to all 57 train companies and the review's amendments). Ranges: 95% ticker-block bootstrap, 2,000 draws, seed 11.

## Step 0 — bookends and the review check
This prompt, `docs/handoffs/2026-09-27-consensus-screen-review.md` (already tracked), `docs/handoffs/2026-09-27-consensus-full-test-review-brief.md`, and `docs/handoffs/2026-09-27-consensus-full-test-review.md` (already tracked) were committed. **Verified before running:** the prompt's "Full-test review amendments" (A–F) match the six numbered answers in `2026-09-27-consensus-full-test-review.md` point for point — one primary reading (A), the two conditions (B), the sector label as a non-gating classification (C), the point-in-time provisional handling (D), the tune pre-registration (E), and the misleading-result guards (F). No discrepancy required a stop. **CS1 pre-registered** in `PROMPT_ARCHITECTURE.md` §2.2 as its own commit, before any return was computed.

## Step 1 — fetch (one session)
All **57** train companies fetched or reused: the screen's 20 were already saved and cost nothing further; the other **37** were fetched fresh with the premium key, 0 rate-limit messages, no retry needed. FRC, MAXNQ, SUNW returned empty (as expected); PARA returned data but stays excluded for corrupt prices.

## The primary (review amendment A)
Among train calls B scored **≥ 0** (mean of two draws) — **859** of 1,171 matched calls — the rank correlation of quarter-adjusted SUE_p with the 182-day return:

**ρ = 0.069, range −0.013 to +0.148.** The range includes zero. **The primary does not pass.**

**Direction check (reported, not gated):** top 19% by combined (surprise + B) held **19.6%** big winners against **15.3%** for top 19% by B alone — the same direction the mechanism predicts, but the difference's range (−2.5 to +10.3) includes zero.

## The two conditions (review amendment B)
| | n | ρ | range | met? |
|---|---|---|---|---|
| **(a) unscreened companies** (33 of 53 with data; the review's brief estimated "~37" — see flag below) | 542 | 0.010 | −0.081 to +0.115 | **yes** (positive point estimate) |
| **(b) leave-one-year-out**, all 6 years | 859 (minus the dropped year) | 0.020–0.097 | — | **yes** (positive in every cut; lowest with 2025 dropped) |

**Both conditions individually hold, and neither rescues the primary.** The review's own logic is that a primary failing on its own range cannot be relabelled "clean", "borderline" or "one year's effect" just because its satellite checks look fine — those checks exist to catch a primary that *does* pass for the wrong reason, not to promote one that doesn't pass at all. **Overall reading: fail.**

## Sector label (review amendment C, not a gate)
Sector-and-quarter-adjusted primary: ρ = 0.058, range −0.020 to +0.136 — also includes zero. **41.7% of matched calls fell back to the corpus-wide quarter median** (their sector-quarter cell had under 5 calls). **Label: n/a — no label is assigned when the primary itself does not pass**, per the review's own conditional wording ("primary passes and… ").

## Point-in-time (review amendment D) — 8 rows for manual checking, not run here
**5 unflagged**, from the top and bottom 5% of SUE_p_adj among the B ≥ 0 calls (3 top, 2 bottom, seed 11): MS 2020-07-16, AIG 2023-11-02, HCA 2020-07-22 (top); PSX 2025-04-25, CMI 2022-02-03 (bottom). **3 flagged** (largest |SUE_p_adj| among EOSE/JKS/RUN): EOSE 2023-11-07, EOSE 2025-11-06, EOSE 2025-03-05 — all three landed in EOSE this time, not spread across the three flagged companies as the screen's five were. **None of these 8 rows have been checked against a dated external source in this run.** Since the primary already fails on its own numbers, the 8 checks cannot turn a fail into a pass — but per the prompt, if any of the 8 turns out revised or mismatched, the reading would in any case drop no lower than it already sits ("can't tell", which for a failing primary is not a materially different practical conclusion).

## Guards (review amendment F)
- **Beat-rate guard:** B ≥ 0 beat rate is **83.1%**, above the 70–80% flag band the guard describes — so the specific guard wording doesn't trigger, though the underlying point (most non-bearish calls beat consensus) still holds and is part of why the effect is hard to isolate.
- **EPS-scale split** (review amendment 5, full test only): estimate ≥ 1% of price (n=558): ρ 0.073 (−0.033 to +0.178); estimate < 1% of price (n=301): ρ 0.044 (−0.053 to +0.140). **Neither sub-split passes**, so the "revenue-surprise is the next question" branch does not apply (it requires a pass on the ≥ 1% side specifically, which did not happen).

## Reported-only items (screen amendments 1–6 and full-test items 1–6)
- **Pooled rank correlation, all 1,171 matched calls (not the primary):** SUE_p_adj alone 0.059 (−0.002 to 0.114, essentially touching zero); own B alone 0.112 (0.039 to 0.185); **combined 0.113 (0.054 to 0.170, clears zero)**. This is the same shape the screen showed and is exactly the reading the review excluded from being the decision criterion, because it can pass on the downside where surprise and B already agree — reported for completeness, not as evidence for or against CS1.
- **Item 2/3 (all matched, unrestricted):** top 19% by SUE_p_adj: 42.3% right, 22.1% big winners (Wilson 17.1–28.0). Bottom 16%: 47.6% right.
- **Item 4, persistence:** 754 of 1,171 matched calls beat both their AV quarter and the prior one; their big-winner share (11.3%) is **lower** than non-persistent calls (15.0%) — no persistence effect, same wrong-signed pattern the screen found.
- **Item 5, by year and sector-year:** no strong pattern by year (all small, 0.03–0.09). Within sector-year (47 cells ≥ 12 calls, 942 of 1,171 calls, 80%): weighted ρ **0.045** — small but positive, an improvement over the screen's −0.001, still not gated.
- **Item 6, relation to r0:** ρ(SUE_p_adj, r0) = **0.240** (n=1,171) — a real but moderate relationship, well under the 0.5 threshold that would matter for a closing rule (not applicable here; that rule belongs to the screen).
- **Three-group, all matched:** winner median SUE_p_adj +0.030, middle 0.000, loser −0.013 — the predicted order, consistent with the screen, on the full corpus.

## Deviations, flags, premises
1. **Unscreened-company count:** the review brief estimated "~37 companies the screen did not fetch." The actual count with usable AV data is **33** (53 companies with data, minus the 20 screened) — 4 of the nominal 57 train companies have no AV data at all (FRC, MAXNQ, SUNW empty; PARA excluded for corrupt prices), which the review's approximation did not net out. This does not change any reading; condition (a) is reported at its true n (542 calls, 33 companies).
2. **The beat-rate guard's exact numeric band (70–80%) did not trigger** even though the underlying concern it describes (a high beat rate compressing the signal) is visibly present at 83.1%; flagged as a literal-vs-substantive gap in the guard's wording, not corrected here.
3. No other deviations from the prompt or its amendments.

## What this means

**Fail, provisionally.** The one pre-registered primary reading — the question the review said this test should actually answer, "does knowing the consensus surprise make B's non-bearish calls better at finding winners?" — does not clear zero, even though its two safety conditions (the sign holding on unseen companies, and surviving every leave-one-year-out cut) were each individually satisfied. **The tune test is not run and the reserved tune look is not spent**, per the review's own rule that it is spent only on a clean train pass. **Consensus surprise joins the closed routes** (winners-missed, P5's peer read-through, the sector score, the announcement-day move) as a route that does not clear its own bar on train, pending the 8 checks that could in principle move it to "can't tell" but cannot move it to "pass." The analyst's role, on the evidence assembled across this whole thread, remains downside protection; picking winners has not found a working machine-side lead, and the live forward test — the one route not yet available on historical data alone — is the remaining path to a bullish signal.

## Not done
The 8 point-in-time checks (Luis or Cowork's task, not the CLI's), the tune test (not earned), any candidate write-up, any scoring, any DB write, any cache refresh.

```bash
python3 analysis/consensus_full_test.py
```
