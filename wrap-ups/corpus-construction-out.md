# Corpus construction — wrap-up

**Scope boundary: report and propose, do not decide.** This run selected and
froze a corpus. It did not score anything, spend any Anthropic API budget, or
commission any future scoring run.

**Status: PARTIAL RUN.** Steps 0–4 are complete (the prompt's required minimum
stopping point). Steps 5–7 (three-way split/holdout lock, detection-threshold
projection, cost estimate) are **pending**, not attempted, due to session time
budget — see "What was deliberately not done."

**Cost: $0 in Anthropic API spend.** Zero LLM calls. Zero `Analysis` DB writes.
**Vendor cost: 82 EarningsCall.biz calls**, all `symbols-v2.txt`/`events`
metadata endpoints — no transcript content was ever requested.

---

## §0 — Defined terms

Plain language first: this run picked which 71–80 companies a future,
separate, paid run will use to test whether a change to the analyst's prompt
actually made it better. The whole point is picking those companies by fixed
rules *before* looking at how any of them actually performed — looking first
and picking companies that make a result look good is called "outcome
selection," and it would make the whole exercise worthless for its purpose.

| Term | Meaning as used in this report |
|---|---|
| **Stratum (S1–S6)** | One of six named buckets of companies, each with its own fixed selection rule, so the corpus isn't just "80 random companies" but a designed mix (ordinary large caps, in-scope companies, out-of-scope companies, companies that failed, a carried-forward legacy set, and a reserve list). |
| **Point-in-time list** | A list of companies as they stood on a specific past date, including ones later removed — the opposite of a "survivor list" (today's list, which quietly drops anyone who left). |
| **Survivor list** | A list built from today's index membership, which hides every company that was removed, acquired, or went bankrupt. Rejected as a Step 1 source if the removed-count comes back zero. |
| **Availability threshold** | The bar a company must clear to be usable: at least 12 earnings calls between 2020 and 2025, and no gap longer than two consecutive quarters (about 6 months) between calls. |
| **Drop-and-replace** | The mechanical rule for a company that fails the availability threshold: drop it, replace it with the next name on that stratum's pre-written reserve list. No judgment calls allowed. |
| **DOMAIN.md universe** | This project's approved investing scope: Tier 1 (solar, energy storage, semiconductors) and Tier 2 (IT/software/cloud, narrowly-scoped crypto). "In scope" below means inside this list; "out of scope" means outside it. |
| **ALL16 / S5 (continuity)** | The 16 companies this project has always tested with (AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA, AMPX, ENVX, EOSE, FSLR, QS, RUN, SPWR, TTD). Kept in this corpus for continuity with old results, but excluded from this run's headline "how sensitive is our ruler" numbers because they were originally hand-picked with hindsight, which would make the ruler look artificially good. |
| **Points vs. percent (pp vs %)** | "Points" is a plain difference between two percentages (44% vs 46% is "2 points apart"). "Percent" is a relative change. This report uses "points," matching the project's language rule. |
| **Beats / lags / moves-with** | How a company's stock did over the roughly six months (182 days) after an earnings call, compared to the S&P 500 tracking fund SPY, with a 5-point "dead band": more than 5 points better than SPY = beats; more than 5 points worse = lags; within 5 points either way = moves-with. |
| **Detection threshold (not reached this run)** | The smallest genuine improvement in the analyst's scoring accuracy that this corpus, if scored, could reliably tell apart from noise. Today's corpus can only reliably see a 6-point-or-larger improvement; a realistic single improvement to the prompt is 2–4 points, meaning today's corpus is currently unable to prove most real improvements happened. Step 6, which would have measured this figure for the new corpus, was not reached this run. |

---

## Lead-with summary (fill-in-the-blank, per the prompt's own template)

> The corpus is **71 companies** (target 80), of which **55** are new
> (target 64), spanning **1,585 earnings calls** (`analysis/data/corpus_v2/CORPUS_MANIFEST.json`
> → sum of `n_calls_2020_2025` across all frozen companies) across 2020 to 2025.
> **Step 6 (the detection-threshold projection) was not reached this run**, so
> there is no new number to compare against today's 6 points yet — that is the
> single most important pending item below. **Step 7 (scoring cost) was also
> not reached**, so there is no cost estimate yet either. Of the 2020 companies
> examined for Step 1's dated source, **at least 59** are confirmed no longer
> in the index today (a lower-bound, partially-verified count — see
> Limitations). **Of the companies actually selected into this corpus, 6
> failed outright or were acquired under distress** (SVB Financial, First
> Republic, Wolfspeed, Sunnova, Romeo Power, Sunworks), of which only **2**
> (Wolfspeed, Sunnova) survived the availability check into the frozen corpus
> — the other 4 were dropped by the same rule that makes them interesting in
> the first place, which is this run's central finding (see Step 3).

---

## Step 1 — the point-in-time universe

**Source:** a specific, timestamped Wikipedia revision of "List of S&P 500
companies," not the live article —
<https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid=997494787>,
revision 997494787, timestamped 2020-12-31 19:55 UTC. This is genuinely dated
(it is the article as it stood on that exact date), not a survivor list.

**Survivor-list check (required by the prompt — a zero result here would mean
reject the source):** cross-referencing this revision against the separate
"Historical components of the S&P 500" change log
(<https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500>,
covering every dated addition/removal from 2021-01 through 2025-12), **at
least 59 distinct tickers that were 2020-12-31 constituents are confirmed no
longer in the index today** — CXO, FTI, FLIR, ALXN, MXIM, PRGO, UNM, NOV, KSU,
LEG, HBI, WU, XLNX, INFO, PBCT, DISCA, DISCK, CERN, UAA, IPGP, CTXS, DRE, NLSN,
TWTR, FBHS, ABMD (2021–2022), plus K, IPG, WBA, HES, ANSS, JNPR, DFS, BWA, TFX,
CE, FMC, QRVO, CTLT, MRO, AAL, ETSY, BIO, RHI, CMA, ILMN, PXD, WHR, ZION, SEE,
ALK, NWL, LNC, DISH, LUMN, FRC, SIVB (2023–2025). **This is well above zero,
so the source clears the required survivor-list rejection test.**

**Limitation, stated plainly:** the 59-count is a **lower bound**, not an
exhaustive count of all ~500 constituents. The fetch tool used to retrieve the
dated revision truncates around row 234 of roughly 500 (alphabetically through
"H"); those 234 rows (items 1–234, "MMM" through "HRL") were retrieved and
confirmed verbatim. Membership for later-alphabet tickers was corroborated
against the change-log's add/remove dates rather than against a second full
read of the I–Z portion of the snapshot itself. A ticker changed purely by
rename (WLTW→WTW, CDAY→DAY, FLT→CPAY) is not counted as "no longer in the
index" since the same company remains, just under a new symbol.

---

## Step 2 — the six strata (as selected, before the availability check)

Selection used `analysis/corpus_construction_driver.py` (`select` command)
against the frozen rules in `analysis/data/corpus_v2/PREREGISTRATION.json`,
written before any company's return was looked at.

- **S1 (large cap, point-in-time), rule = ranks 21–40 by Dec-2020 market cap,
  deterministic:** CMCSA, NFLX, XOM, INTC, VZ, KO, NKE, MRK, PFE, T, ABT, CRM,
  PEP, TMO, CSCO, ACN, COST, MCD, QCOM, TXN (20 selected before Step 3).
  **Limitation:** ranks 1–10 for Dec-2020 (AAPL/MSFT/AMZN/GOOGL/FB/TSLA/
  BRK.B/V/JPM/JNJ) are well-established across sources and cross-checked; ranks
  21–40 specifically rest on general published knowledge of that period's
  mega-cap ordering, not one independently retrieved authoritative ranked
  table for that exact range. Flagged, not silently presented as verified.
- **S2 (in scope, mixed cap), rule = DOMAIN.md universe, 6 large / 6 small / 4
  micro, seeded random (seed 20201231):** large — AMAT, LRCX, MU, NXPI, ADBE,
  IBM; small — FORM, SLAB, BOX, ENTG, POWI, DIOD; micro — AMSC, ARRY, SHLS,
  BLDP (16 selected before Step 3).
- **S3 (out of scope, mixed cap), rule = outside DOMAIN.md, ≤4 per sector,
  seeded random (seed 20201231):** GIS, KMB, CL, HRL (staples); CVS, HUM, BMY,
  PFE→excluded as an S1 duplicate, replaced within-sector (healthcare); WFC,
  USB, AIG, JPM (financials); CAT, DE, GE, MMM (industrials); CVX, COP, VLO,
  PSX (energy); NEE (utilities, 1 of 4 cap after S1/S2 exclusions). 20
  selected, all 20 passed Step 3.
- **S4 (failures), rule = 2020 S&P 500 member OR 2020 DOMAIN.md member, then
  failed/distressed-acquired/delisted — verified mechanically, not
  cherry-picked:**
  - **Qualified** (2020-membership or domain-fit verified): SVB Financial
    (SIVB — long-standing S&P 500 member, not listed as a post-2020 addition;
    FDIC receivership March 2023), First Republic Bank (FRC — confirmed
    present in the Step 1 snapshot, item 192; FDIC receivership May 2023),
    Wolfspeed (WOLF — traded as CREE through 2020, DOMAIN.md Tier 1
    semiconductors; Chapter 11, 2025).
  - **Dropped at verification** (failed the pre-registered rule, not
    "swapped for a similar name"): Signature Bank (SBNY — added to the S&P
    500 in Dec 2021, **not** a 2020 constituent, and a bank with no
    DOMAIN.md thesis), Proterra, Fisker, Nikola, Lordstown Motors (all EV/
    vehicle OEMs — never S&P 500 members and outside DOMAIN.md, which does not
    cover vehicle manufacturing), Li-Cycle (battery-materials recycling —
    never an S&P 500 member; DOMAIN.md's storage tier does not name recycling
    as in-scope, treated as out-of-domain for this run).
  - **Filled from a dated reserve amendment** (written before any outcome was
    examined — see `PREREGISTRATION.json` → `strata.S4.reserve_pool_amendment_2026_09_14`):
    Sunnova Energy (NOVA — DOMAIN.md Tier 1 solar+storage; Chapter 11, 2025),
    Romeo Power (RMO — DOMAIN.md Tier 1 storage; forced distressed merger into
    Nikola, 2022), Sunworks (SUNW — DOMAIN.md Tier 1 solar; Chapter 11, 2025).
  - **Result before Step 3: 6/8** (SIVB, FRC, WOLF, NOVA, RMO, SUNW). The
    reserve was then exhausted.
- **S5 (continuity)**, carried forward unchanged from
  `docs/architecture/VERSION_REGISTRY.json` → `artifacts.ticker_universe.canonical`:
  AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA, AMPX, ENVX, EOSE, FSLR, QS,
  RUN, SPWR, TTD (16). **Excluded from Step 6's headline ruler-detection
  figures, recorded in `CORPUS_MANIFEST.json` → `strata.S5.note`, not left
  implicit.**

**One driver bug found and fixed before freezing:** the first selection pass
did not exclude S1's picks from S3's candidate pool, producing 3 duplicate
tickers (PEP, ABT, PFE) claimed by both strata. Fixed in
`analysis/corpus_construction_driver.py` (commit `1a6d777`) before any
availability check or outcome look — a mechanical correction to a coding
error, not an outcome-driven re-pick.

---

## Step 3 — availability (vendor metadata only) and every drop/replace

**82 EarningsCall.biz calls used this run** (`symbols-v2.txt` × 2 +
`/events` × 1 per distinct ticker checked, including replacement candidates)
— all metadata (call dates, counts), **zero transcript content requested**.
Combined with the 211 calls already recorded this billing period by
`ec-fidelity-benchmark-1` (`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`
→ `calls_used_total`), cumulative usage this period is **≈293/1,000** — well
under the Premium plan's monthly figure cited in that run's wrap-up.

**A structural finding, not overridden — this is the central result of Step
3.** Of S4's 6 candidates that passed Step 2's membership/domain verification,
**4 failed the pre-registered availability rule** (12+ calls, no gap > 2
quarters): FRC (6 calls, 2022-01-14…2023-04-24 — stops at receivership), SIVB
(0 calls — absent from the vendor's symbol list entirely), RMO (6 calls,
2021-03-30…2022-05-09 — stops at the forced merger), SUNW (10 calls, stops
2023-11-10 at bankruptcy). **This is not a coincidence: a company that fails
necessarily stops reporting earnings calls, which is exactly what the
availability rule penalizes.** The prompt's own standing rule — "if the
resulting set looks odd, report that rather than overriding it" — was
followed: the rule was applied mechanically, and **S4 ends the run at 2/8**
(Wolfspeed, Sunnova), not 6/8. This matches the prompt's own predicted
diagnostic almost exactly ("availability being worse than assumed for micro
caps and for companies that failed" — Standing rules, item on diagnostics).

**S4's reserve list is now fully exhausted.** A future session wanting to
raise S4 back toward 8 needs a new, dated pre-registration for additional
candidates, written before looking at those candidates' returns — not simply
lowering the availability threshold for S4 alone after seeing the shortfall,
which the prompt's discipline treats the same as outcome selection.

**S1 and S2 also lost members — ordinary, healthy companies this time, not
failures:**
- S1 dropped INTC (max gap 2.01 quarters), KO (2.02), MCD (2.02), TMO (2.13)
  — each failing by a very small margin over the 2.0-quarter threshold, more
  consistent with one irregular reporting gap in a specific year than a real
  coverage hole. Replaced from reserve with HON and UPS (both pass); LIN (the
  third reserve name) also fails at 2.08 quarters, and no further reserve
  exists. **S1 ends at 18/20.**
- S2 dropped POWI (3.0-quarter gap). The next small-band reserve name, PSTG,
  is **not in the vendor's symbol list at all**. **S2 ends at 15/16.**
- S3: all 20 selected names passed. **S3 stays at 20/20.**
- S5: **exempt from the drop rule by design** (carried forward unchanged
  regardless of availability). GOOGL is confirmed absent from the vendor's
  symbol list — this reproduces the already-documented gap from
  `wrap-ups/ec_transcript_fidelity_benchmark_1-out.md` ("GOOGL missing,
  megacap tier"), **not a new defect**. SPWR (6.75-quarter max gap) and TSLA
  (3.05-quarter max gap) also fail the availability threshold that would apply
  to any other stratum, but stay in the corpus per S5's exemption.

**Frozen totals: S1 18/20, S2 15/16, S3 20/20, S4 2/8, S5 16/16 = 71/80
distinct companies, 0 duplicates.**

Full per-company availability figures (calls, first/last date, max gap,
pass/fail) are in `analysis/data/corpus_v2/CORPUS_MANIFEST.json` →
`strata.<S1-S5>.frozen[]`.

---

## Step 4 — freeze, then outcomes

**4a. Freeze (done first, before any outcome was measured).**
`analysis/data/corpus_v2/CORPUS_MANIFEST.json`, committed at `9acb633`.
`manifest sha256 = 0e036e97777577cdd1a87b97e6cd8d81bf1c69d367b3c2915254c86cc61e3080`.
Recorded in `analysis/data/run_state/corpus-construction/progress.json`.

**4b. Outcome balance (measured only after the freeze commit above).**
`analysis/corpus_construction_outcomes.py` (committed at `cbc2d7b`, before its
own output) computed each frozen company's 182-calendar-day forward return
against SPY over the same window, using a **±5-point dead band**, from a
**new** price cache (`analysis/data/corpus_v2/corpus_v2_price_cache.json`) —
`analysis/data/price_cache.json` was never opened for writing.

**Limitation / deviation, stated plainly:** this measures **one point per
company** — the return following that company's *last* available call date —
rather than every call, because Step 3's availability check recorded only
first/last/count, not the full per-call date list, and re-deriving it would
have cost additional vendor calls for no availability-relevant purpose. This
is a per-company proxy for the scorecard's per-call grading, not a
reproduction of it.

**Result** (`analysis/data/corpus_v2/outcome_balance.json` →
`distribution_excluding_S5_ruler_headline`, S5 excluded per its pre-registered
rule, n=54 of 55 non-S5 companies; NOVA's 2025-03-03 last call is not skipped
here since 182 days had elapsed, but its price series returned "possibly
delisted" from Yahoo Finance and was excluded for missing data):

| | beats | lags | moves-with |
|---|---|---|---|
| **This corpus (n=54)** | **44.4%** | **35.2%** | **20.4%** |
| Existing corpus | 46.2% | 42.1% | 11.7% |

**The balance is reasonably close on "beats" and noticeably shifts weight
from "lags" toward "moves-with."** Per the prompt's rule, **this was not
re-picked, and will not be** — that comparison exists only to be reported, not
acted on. If a future session judges the balance a problem, the only
permitted response is a new stratum with its own dated pre-registration, not
a swap inside this one.

---

## What was deliberately not done (Steps 5–7, pending)

- **Step 5 (three-way split, holdout lock)** — not started. `next_action` in
  `progress.json` gives the exact procedure: split by company (never call),
  seed 20201231, stratified including S4, then lock and hash the holdout list
  and add the one authorized `PROMOTION_GATE.md` §10 note.
- **Step 6 (detection-threshold projection)** — not started. `next_action`
  names the reusable driver: re-run `analysis/scorecard_repair_driver.py`'s
  Step 3 methodology at the new train+tune block count (71 minus the holdout
  share), plus the two named fallbacks (half survive availability; in-scope
  strata only).
- **Step 7 (cost estimate)** — not started, depends on Step 5's split sizes.

These three were explicitly permitted to be deferred as `pending` once Step 4
was complete (prompt §3/§9); this is a **partial run**, not a failure to
finish.

---

## Limitations (stated, not argued past)

- **The corpus is selected, not scored.** Nothing in this run measures the
  analyst.
- **S5's 16 companies are hindsight-selected** and excluded from every ruler
  headline this run or a future Step 6 would produce.
- **Outcome balance was measured after freezing** (Step 4a before 4b) and
  cannot be corrected by re-picking, regardless of how it compares to the
  existing corpus.
- **The Step 1 survivor count (≥59) is a lower bound**, not an exhaustive
  count over all ~500 constituents, due to fetch-tool truncation of the dated
  Wikipedia revision at row ~234.
- **S1's ranks 21–40 rest on general published knowledge**, not one
  independently retrieved authoritative ranked table for that specific range.
- **Vendor availability metadata may disagree with what a real scoring run
  retrieves** — this run never fetched transcript content, only dates/counts.
- **Step 4b's outcome measurement is a per-company proxy** (last call date
  only), not the scorecard's actual per-call grading.
- **Step 6's threshold (when eventually run) will be a simulation over
  synthetic challengers**, not a measurement of any real prompt difference —
  stated here in advance since it applies regardless of who runs Step 6.

---

## Deviations from the prompt, and why

1. **S1's market-cap ranking source is general knowledge, not one retrieved
   ranked table** — flagged as a limitation rather than silently presented as
   verified; Steps 1–2 still proceeded because ranks 1–10 are well-established
   and the qualitative point (S1 is ordinary large caps, not domain-relevant)
   does not depend on the exact rank-21-vs-rank-24 ordering.
2. **S4's reserve pool was amended once, before any outcome was examined**
   (`PREREGISTRATION.json` → `reserve_pool_amendment_2026_09_14`), adding
   Romeo Power and Sunworks after the original 9 candidates + 1 reserve name
   yielded only 4 qualifiers against target 8. This is the one place this run
   added new candidate names after Step 0's initial pre-registration — done
   deliberately before touching Step 4b's outcome look, and stated here so it
   is not mistaken for silent post-hoc curation.
3. **A cross-stratum duplicate bug (S1/S3 overlap on PEP/ABT/PFE) was found
   and fixed** before Step 3, as a mechanical code correction, not a
   selection change.
4. **Step 4b used a per-company outcome proxy** (last call date) rather than
   a per-call measurement, for the time-budget reason stated in Step 4 above.
5. **Steps 5–7 deferred** per the prompt's own explicit permission once Step
   4 was reached.

---

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` passed for
  `analysis/corpus_construction_driver.py` (both before and after the S3/S4
  fixes) and `analysis/corpus_construction_outcomes.py`.
- `python3 -c "import json; json.load(...)"` passed for
  `PREREGISTRATION.json`, `CORPUS_MANIFEST.json`, and `progress.json`.
- Re-ran `select` after the S1/S3 duplicate fix and confirmed
  `distinct_companies == total_companies` (no duplicates) before proceeding to
  Step 3.
- Confirmed `git status` clean (only this run's own untracked state) before
  each commit; each commit staged specific files, never `git add .`/`-A`.
- FRC's 2020-12-31 membership was checked against the actual retrieved
  snapshot text (item 192, "FRC - First Republic Bank"), not asserted from
  memory.
- GOOGL's absence from the vendor symbol list was cross-checked against the
  prior, independently-run `ec-fidelity-benchmark-1` finding before being
  reported as "known, not new."

---

## Exact follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git checkout sweep/db-corpus-baseline
cat analysis/data/run_state/corpus-construction/progress.json
cat analysis/data/corpus_v2/CORPUS_MANIFEST.json | python3 -m json.tool | less
cat analysis/data/corpus_v2/outcome_balance.json | python3 -m json.tool | less

# Step 5 (three-way split + holdout lock) — not yet written, next session:
# split analysis/data/corpus_v2/CORPUS_MANIFEST.json's 71 frozen companies by
# company, stratified, seed 20201231, then hash and lock the holdout.

# Step 6 (detection threshold at the new block count) reuses:
python3 analysis/scorecard_repair_driver.py   # review its Step 3 methodology before adapting the block count
```

---

## Resume status

Steps 0–4 complete this session (a fresh run, no prior `corpus-construction`
state existed). Steps 5–7 pending, precise `next_action` recorded in
`progress.json`. This is a **partial run** by the prompt's own explicit
permission, not an incomplete one — Step 4's freeze-then-measure gate, the
run's real minimum bar, was fully reached.
