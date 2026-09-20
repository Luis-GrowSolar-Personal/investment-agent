# Finnhub probe — the free key carries EPS estimates for nearly every company, but only four quarters deep

**Run:** `finnhub-coverage-probe` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0 in model calls; 121 vendor calls** of a 600 ceiling, none refused for rate.
**Status: complete.** The API was reachable from this terminal, so the network block the prompt anticipated for other environments did not occur. **The hypothesis was not tested, and could not be:** the free window holds 106 corpus calls, of which **6 are bearish**.

## §0 Defined terms

- **Consensus estimate.** The average of what professional analysts expect a company to earn for a quarter. Here, earnings per share only.
- **Earnings surprise.** The reported result minus the consensus estimate. The hypothesis this probe supports is that the surprise, not a company's comparison with its *own* past guidance, predicts the stock.
- **Point-in-time.** The estimate as it stood *before* the company reported, never restated afterwards. A restated figure would hand the analyst the answer.
- **Coverage.** The share of a company's quarters for which the vendor has a populated estimate.
- **Stratum.** How the corpus was built: S1 large cap, S2 in-scope mixed cap, S3 other, S4 failures, S5 continuity names (the ALL16).
- **Pre-revenue.** A company with little or no sales. Its earnings estimate is an expected *loss*, which says much less than an expected revenue figure.
- **Populated versus usable.** A field can be filled in and still not be comparable to what the company reported. This report keeps the two apart.

## Lead-with sentence

Of the six endpoints tested, **3** are reachable on the free key, **including the earnings history** (`/stock/earnings`). History reached back to **2025-09-30 (the last four quarters)**, which is **about a year, as reported**; asking for 100 quarters returns the same four. Across **108 companies (106 with any data)** and **424 quarters**, a consensus estimate was populated on **100%** of quarters. For the large companies that produced most of our worst calls (INTC, VZ, KHC, SBUX, UPS, SEDG) it was **100% (24 of 24 quarters)**, and for the speculative and pre-revenue names it was **100% for the five that return data (20 of 20 quarters); the sixth, SUNW, is a failed company with nothing returned**. Forward revenue estimates **are not** reachable. The estimates **could not be confirmed to be** point-in-time. This run used **121 calls**. **It did not test the hypothesis, and could not: the free window holds six bearish calls.**

## 1. Which endpoints the free key reaches

Called once each for MSFT. Source: `analysis/data/run_state/finnhub-coverage-probe/step1_endpoints.json` and `raw/`.

| endpoint | what it would give us | free key |
|---|---|---|
| `/stock/earnings` | EPS actual against estimate, with surprise | **reachable**: 4 quarters |
| `/stock/eps-estimate` | forward earnings estimates | **no access** (HTTP 403, "You don't have access to this resource") |
| `/stock/revenue-estimate` | **forward revenue estimates** | **no access** (HTTP 403) |
| `/stock/recommendation` | analyst recommendation trend | reachable: 4 monthly readings |
| `/stock/price-target` | consensus price target | **no access** (HTTP 403) |
| `/stock/metric` | basic fundamentals | reachable |
| `/calendar/earnings` (extra probe; not in the prompt) | report date, before/after market, revenue estimate | 200 but **empty**, even for a window inside the free year (2 calls) |

**The 403s are vendor plan restrictions, not a network block.** Each comes with a plain JSON message. Everything that gives forward estimates or revenue estimates is closed on this key. The one that matters most for the hypothesis, the estimate-against-actual history, is open but four quarters deep.

## 2. History depth

- `/stock/earnings` returns **the latest four quarters and nothing more**, with or without `limit=100` (`raw/stock_earnings__MSFT__*`: two files, identical). For MSFT that is fiscal quarters ending 2025-09-30, 2025-12-31, 2026-03-31 and 2026-06-30.
- **No response carries a warning about the free plan.** The depth limit is silent; you only see it by counting rows.
- The corpus begins February 2020. **The free key reaches 4 of a company's roughly 24 corpus quarters**, and only the last 89 days of the corpus (2025-09-20 to its last call, 2025-12-18).
- **Confirmed for the prompt's table:** 106 corpus calls (train and tune, WOLF and SPWR excluded) fall on or after 2025-09-20, **of which 6 are bearish**. That is where the hypothesis test dies on this key.

## 3. Coverage across the corpus

Source: `step2_coverage.json`, built from `raw/stock_earnings__<SYMBOL>__*.json` (one call per symbol; 112 symbols because renamed companies were probed under both symbols). One row per company, using whichever symbol returned data.

| stratum | companies | with any data | quarters returned | estimate populated |
|---|---|---|---|---|
| S1 large cap | 30 | 30 | 120 | 120 of 120 (100%) |
| S2 in-scope mixed | 20 | 20 | 80 | 80 of 80 (100%) |
| S3 other | 46 | 46 | 184 | 184 of 184 (100%) |
| **S4 failures** | **2** | **0** | **0** | **none** |
| S5 continuity | 10 | 10 | 40 | 40 of 40 (100%) |
| **all** | **108** | **106** | **424** | **424 of 424 (100%)** |

Every returned quarter also has an actual and a surprise field. Of the 108 companies, **106 return exactly four quarters and two return nothing: FRC and SUNW**, both failed companies. **Coverage for the companies that collapsed cannot be measured on this key at all.** The prompt's argument that coverage does not change from year to year does not hold for names that no longer trade.

### The call-outs

| company | stratum | quarters returned | estimate populated | period range | note |
|---|---|---|---|---|---|
| INTC | S1 | 4 | 4 | 2025-09-30 to 2026-06-30 | |
| VZ | S1 | 4 | 4 | same | |
| KHC | S3 | 4 | 4 | same | |
| SBUX | S1 | 4 | 4 | same | |
| UPS | S1 | 4 | 4 | same | |
| SEDG | S2 | 4 | 4 | same | |
| EOSE | S5 | 4 | 4 | same | actual −$4.91 against estimate −$0.23 in Sept 2025 |
| ENVX | S5 | 4 | 4 | same | |
| BLDP | S2 | 4 | 4 | same | |
| AMPX | S5 | 4 | 4 | same | |
| QS | S5 | 4 | 4 | same | |
| **SUNW** | S4 | **0** | **0** | none | failed company |

### Renamed companies

| pair | old symbol | new symbol |
|---|---|---|
| ANTM / ELV | 0 quarters | **4** |
| BK / BNY | 0 quarters | **4** |
| GOOGL / GOOG | 4 | 4 (two share classes) |
| MAXN / MAXNQ | 4, all stale (2024) | 4 |

The vendor prefers the **new** symbol. MAXN returns four quarters from **2024**, and its estimates sit on a different share basis from its actuals (for 2024-12-31: estimate −41.32, actual −6.57), which looks like a reverse-split mismatch.

## 4. "Populated" is not the same as "usable"

The estimate field is full. Whether it can be compared to what the company reported is a separate question, and the data suggest it often cannot for small and loss-making names.

Source: `quality_output.txt`.

| stratum | quarters with a **negative** (expected-loss) estimate | quarters where the "surprise" exceeds 100% of the estimate |
|---|---|---|
| S1 large cap | 2 of 120 | 2 of 120 |
| S2 in-scope mixed | **18 of 80** | 4 of 80 |
| S3 other | 4 of 184 | 2 of 184 |
| S5 continuity | **18 of 40** | **7 of 40** |

Two things follow.

1. **For a large share of the speculative names the estimate is an expected loss** (18 of 40 S5 quarters, 18 of 80 S2 quarters). The prompt warned that this is a weak signal. The free endpoint has no revenue estimate to fall back on.
2. **Percentage surprises blow up when the estimate is near zero, and some "actuals" look like a different accounting basis from the estimate.** Examples, all from the raw files: EOSE Sept 2025, estimate −$0.23, actual −$4.91 (a surprise of about −2,000%); INTC Sept 2025, estimate $0.01, actual $0.23 (+2,200%); RUN Mar 2026, estimate −$0.025, actual +$0.62 (+2,620%); Salesforce, estimate $3.31 against an actual of $5.90 (+78%) in a quarter labelled 2026-09-30. A percentage surprise from this feed could not be used as-is. A surprise measured in dollars, scaled by price, would be safer.

The vendor's own arithmetic is consistent: surprise equals actual minus estimate on **432 of 432** rows. That shows the two numbers are not misreported to each other; it does not show they are on the same basis.

## 5. Can the estimate be joined to our transcripts?

**Not on the report date.** `/stock/earnings` has no report-date field, only `period` (a quarter-end date), fiscal `year` and `quarter`. The extra calendar probe, which would give report dates and a before/after-market flag, was empty. So the join has to go through the quarter.

Source: `step2_coverage.json` → `alignment`. Using the 106 corpus calls on or after 2025-09-20:

- **96** matched a vendor quarter ending 0 to 120 days before the call (the other 10 did not match; the likeliest reason is that their quarter falls before the four the free key returns, which I did not check).
- **93 of 96** had the call **10 to 75 days after the quarter-end**, the normal reporting lag. The median lag is **30 days** (range 14 to 79).
- **92 of 96** carry the **same fiscal year and quarter label** as our transcript.
- **The 4 mismatches are companies with a fiscal year that does not follow the calendar:** COST, ACN, MU and GIS. Their labels differ by a quarter or a year, but the quarter-end date and the lag still match.

So a join on quarter-end plus a lag window works for about nine in ten overlapping calls, and on labels for 92 of 96. **Two cautions.** `period` is a calendar quarter-end even for off-cycle reporters (six companies, including ORCL, BOX, CRM, SNOW, WDAY and HRL, show a period of 2026-09-30 that has not ended). And one SLB row is dated 2000-09-30, a stale row I did not chase.

## 6. Point-in-time — could not be established

The endpoint returns the estimate recorded against a past quarter. Whether that is what analysts expected *before* the report, or a figure revised since, I cannot tell.

What I checked:

- **Re-fetched MSFT later in the run** under a different parameter: **identical** to the first fetch (period, estimate, actual). That rules out a figure that changes between calls minutes apart. It says nothing about revision over months.
- **Surprise equals actual minus estimate on all 432 rows**, so the fields are self-consistent.
- Estimates carry four decimal places (for example 3.7391), which looks like a stored analyst mean rather than a rounded restatement.

What would establish it, and I did not have: a dated snapshot of the same estimate taken before the report, or a fetch of the same quarter months apart. **I state it as "could not be confirmed to be point-in-time."** The consequence the prompt describes applies: a restated estimate would leak the answer.

## 7. What it means for the purchase decision

This is the prompt's second case, **"endpoints free, coverage good, history one year,"** with three complications.

- **Coverage is established for surviving companies:** 106 of 108 companies, every returned quarter populated, including the speculative names.
- **The hypothesis is not testable on the free key.** 106 corpus calls and 6 bearish calls sit inside four quarters.
- **The question becomes which paid tier.** I have not verified any Finnhub paid tier, its price or its history depth, so I cannot compare it to the $60 alternative in the state of play. The forward EPS estimate, revenue estimate and price target endpoints are the ones this key is refused, and they are the likeliest to sit behind a subscription. **Whether the paid earnings history goes back to 2020 is the thing to find out before buying anything.**
- **The $60 recommendation in the state of play is neither withdrawn nor confirmed by this run.** The free tier does not carry the depth the test needs, but it does carry the *kind* of data (estimate, actual, surprise, one year) that the paid tier would be expected to extend.
- **Complications for any paid test:** the failed companies (FRC, SUNW) that supplied the catastrophes have no data on the free window, so whether they are covered in history is unknown; an EPS-only estimate for loss-making names is weak; and the estimate-against-actual basis has to be checked before a surprise is computed.

## 8. Deviations and premises

1. **An extra probe was added:** `/calendar/earnings` (2 calls), because it would give report dates, the before/after-market flag and revenue estimates. It returned nothing on the free key.
2. **The key was sent in an HTTP header** (`X-Finnhub-Token`), so it never appears in a URL or a log. It was never written anywhere; raw responses contain no key.
3. **Call count is 121,** including the stability re-fetch and the two calendar probes. The ceiling was 600. The rate limit never bit; calls were spaced 1.2 seconds apart.
4. **The prompt says the free tier reportedly serves "about one year."** Confirmed for `/stock/earnings` (four quarters). The premise table (106 calls, 6 bearish in the window) was re-derived and matches.
5. **Surprise-size and negative-estimate statistics** in §4 were added because coverage alone would have overstated usability. They are diagnostics, not gates.
6. **The `docs/handoffs/2026-09-20-state-of-play.md` §6 the prompt cites exists** and says what the prompt describes.
7. **Version guard skipped:** no scoring calls.

## 9. Verification

- Endpoint statuses and item counts read from the cached raw files, not from console output.
- Coverage tables recomputed from `raw/` by `analysis/finnhub_probe.py analyze` at zero calls.
- The 106-call and 6-bearish figures re-derived from the eval caches.
- Not verified: point-in-time behaviour, any paid tier, whether the free feed's actuals share the estimates' accounting basis.

## 10. Follow-up commands

```
python3 analysis/finnhub_probe.py analyze        # recompute all tables from raw/ (0 calls)
cat analysis/data/run_state/finnhub-coverage-probe/analyze_output.txt
cat analysis/data/run_state/finnhub-coverage-probe/quality_output.txt
```

Provenance: `analysis/data/run_state/finnhub-coverage-probe/` — `progress.json` (`calls_used`, `call_log`), `raw/`, `step1_endpoints.json`, `step2_coverage.json`, `analyze_output.txt`, `quality_output.txt`, `findings.md`.
