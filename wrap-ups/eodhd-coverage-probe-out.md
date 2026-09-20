# EODHD probe — prices agree, but the free tier does not serve consensus estimates at all

**Run:** `eodhd-coverage-probe` · **Branch:** `sweep/db-corpus-baseline` · **Cost: $0 in model calls; 15 of the 300-call vendor budget.**
**Status: partial by design — a hard stop.** Question 1 (can we trust the prices) is answered. **Question 2 (does consensus exist for our companies) could not be asked:** the earnings calendar endpoint refused the request with **HTTP 403, "Only EOD data allowed for free users."** The prompt says to stop and report if the API refuses, and I did. I did not try other endpoints to work around it.

## §0 Defined terms

- **Consensus estimate.** The average of what professional analysts expect a company to report for a quarter (earnings per share, or revenue).
- **Earnings surprise.** Reported result minus consensus estimate. The hypothesis this probe was meant to feed is that surprise, not a company's comparison with its *own* past guidance, predicts the stock.
- **Point-in-time.** The estimate as it stood *before* the company reported, not revised afterwards. A consensus figure restated after the fact would leak the answer.
- **Coverage.** The share of a company's earnings events for which the vendor has a populated estimate.
- **Stratum.** How the corpus was built: S1 large cap, S2 in-scope mixed cap, S3 other, S4 failures, S5 continuity names (the ALL16).
- **Pre-revenue.** A company with no sales yet. Its earnings estimate measures an expected *loss*, which says much less than an estimate of sales.
- **Before/after market.** Whether a company reported before the open or after the close. This matters because the announcement's price move lands on a different day (see the entry-price test, R4b).
- **Close vs adjusted close.** *Close* is the price the stock actually ended the day at. *Adjusted close* is that price restated for splits and dividends. They differ for dividend payers.

## Lead-with sentence

Across **0** companies and **0** earnings events from 2020 onward, the vendor returned a populated consensus estimate on **no** events, because the free tier refused the earnings calendar with a 403. For the large companies that produced most of our worst calls it was **not measured**, and for the speculative and pre-revenue names it was **not measured**. Revenue estimates **could not be checked** (the same endpoint is where they would appear). On the five of six companies we believe our own prices are correct that our cache actually holds, the vendor's *close* agreed within 1% on **100% of shared dates (246 of 246 for each)**. Free-tier history reached back **only one year**, to **2025-09-22**, for prices. This run used **15 of its 300-call budget**.

## 1. Question 2 — the calendar endpoint is closed on the free tier

Call 9 (`calendar/earnings`, four symbols, 2020-01-01 to 2026-01-01) returned **HTTP 403: "Only EOD data allowed for free users."** Source: `analysis/data/run_state/eodhd-coverage-probe/raw/calendar_earnings__f0eacf72cd.json`. This is a **subscription restriction, not the network block** the prompt anticipated for the Cowork sandbox: the API is reachable from this terminal (account call and seven price calls all returned 200), and it says in plain words that free accounts get end-of-day prices only.

**What that means for the free tier's 500-call welcome bonus:** the bonus raises how many calls you can make (the account shows a 20-call daily limit plus a 500 extra allowance), not which endpoints you may use. It does not unlock the calendar.

**So the following were not measured and cannot be, on this key:** the share of events with a populated estimate, by company or by stratum; whether small and pre-revenue names have any coverage; whether a revenue estimate field exists; how far back calendar history goes; and whether `before_after_market` is populated. I have **not** guessed at any of them. The driver is ready (`analysis/eodhd_probe.py calendar`); on a paid key it would need about 10 calls (112 symbols in batches of 12).

## 2. Question 1 — the prices agree with ours

Source: `analysis/data/run_state/eodhd-coverage-probe/step1_price_comparison.json`, built from `raw/eod_<TICKER>.US__*.json` (endpoint `eod/<TICKER>.US`, from 2020-01-01 to 2026-09-14, daily). Every vendor request for prices returned exactly **246 trading days, 2025-09-22 to 2026-09-14** — the free tier's one-year window. The overlap with our cache is therefore one year, not six.

| company | shared dates | vendor **close** within 1% of ours | worst gap, date | vendor *adjusted close* within 1% |
|---|---|---|---|---|
| MSFT | 246 | **246 of 246** | 0.0% | 246 of 246 (worst 0.82%) |
| INTC | 246 | **246 of 246** | 0.0% | 246 of 246 |
| DUK | 246 | **246 of 246** | 0.0% | 83 of 246 (worst 3.39%) |
| ENPH | **0 — not in our cache** | n/a | n/a | n/a |
| EOSE | 246 | **246 of 246** | 0.0% | 246 of 246 |
| JKS | 246 | **246 of 246** | 0.0% | 59 of 246 (worst 8.35%) |

**The hard stop did not trigger.** On all five companies the vendor's *close* is identical to our cache on every shared date (worst gap 0.0%).

Two things to know:

1. **Our cache holds *unadjusted* closes.** It matches the vendor's `close` exactly and does not match `adjusted_close` for the dividend payers (DUK, JKS). **Any future comparison with this vendor must use `close`.**
2. **Split treatment could not be tested.** None of the five had a split inside the one-year window, so this probe cannot say whether the vendor's `close` is split-adjusted the way ours is. Historical splits fall outside the free window.

**Premise flagged: ENPH is not in `scorer_price_cache_v1.json`.** The prompt lists it as one of six companies "we believe are correct". The vendor returned ENPH (246 days), but our cache has no series for it, so it could not be compared. (This is consistent with ENPH not being in the corpus.)

### Paramount — the independent source is not independent

Documented as asked (`raw/eod_PARA.US__*.json`). The vendor's `PARA.US` also looks wrong over its one visible year: its raw *close* runs from **$0.22 to $7.66** (Sept 2025 $2.51; Dec 2025 $1.10; Mar 2026 $1.03; Sept 2026 $1.01), while its *adjusted close* runs from **$48.00 down to $1.01**. Neither is a normal price for a stock the prompt describes as never leaving a $10 to $100 range. Our cache's PARA sits close to the vendor's *adjusted* series (74.8% of shared dates within 1%; 184 of 246; our $50.20 on 2025-09-22 against the vendor's $48.00) and equals it exactly by June 2026 ($3.21) and September 2026 ($1.01).

**What I can say and what I cannot.** I can say the vendor's `PARA.US` series is itself abnormal, so it cannot serve as the independent check the prompt hoped for, and that our corrupt series resembles the vendor's adjusted series over the year we can see. **I cannot say why**, and I cannot see 2020 to 2024 at all on the free tier, which is where the worst corruption sits ($106,000 in Nov 2023). A plausible cause is a merger-related ticker reuse at the vendor (Paramount merged in August 2025) that our cache inherited, but that is a guess I have not tested.

## 3. Free-tier limits, established empirically

| | finding | evidence |
|---|---|---|
| plan | free; daily limit 20 calls; extra allowance 500 | `raw/user__*.json` (name, email and token redacted) |
| **endpoint access** | **end-of-day prices only; earnings calendar refused (403)** | call 9 |
| **price history** | **one year.** A request from 2020 returns 2025-09-22 onward, plus a `warning` field on the last row: "Data is limited by one year as you have free subscription" | every `eod` response |
| whether the calendar's history is also capped | **not determinable**, endpoint closed | — |
| a refused request still counted against my budget counter | yes, conservatively (call 9). I did not check whether the vendor also counts it | `progress.json` `call_log` |

## 4. Renamed companies — which symbol the vendor prefers

Source: `symbol_preference.json`, raw `eod_<SYM>.US__*.json`. Calls 10 to 15.

| pair | old symbol | new symbol | vendor prefers |
|---|---|---|---|
| ANTM / ELV | **no rows in the window** | 246 rows, close identical to our cache (246 of 246) | **new (ELV)** |
| BK / BNY | 167 rows, ends 2026-05-20 | 246 rows, full window, identical to ours | **new (BNY)**; carries the whole year |
| GOOGL / GOOG | 246 rows | 246 rows | **both exist**: they are two share classes, not a rename |

**A small finding about our own cache.** In `scorer_price_cache_v1.json`, the alias pairs are stored as **exact duplicates**: GOOGL equals GOOG on 1,831 of 1,831 dates, BK equals BNY on 1,831 of 1,831, ANTM equals ELV on 1,831 of 1,831. For BK and ANTM that is correct. **For GOOGL it means the corpus grades Alphabet on the Class C series (GOOG).** The vendor's real GOOGL differs from our GOOGL entry by more than 1% on 18 of 246 days, the ordinary spread between the two share classes. Immaterial at the ±5% dead band, but it is a substitution, so I am recording it.

## 5. What it means for a decision — three ways

The prompt asked for three cases about coverage. **None of them could be determined**, so I state what each would require rather than what it would show.

- **If coverage were good across both groups** (not measured): the next run would be the same probe on a paid key, then a consensus-based ledger. The prompt quotes a price of about $60 a month for this vendor and $99 for a competitor. I have not verified either figure and I am not recommending a purchase.
- **If coverage were good for large caps only** (not measured): the hypothesis could be tested on a reduced universe. Whether that is worth doing depends on data this run could not collect.
- **If coverage is poor or history is capped:** the free tier **is** capped, at **one year of prices**, which is unusable for a 2020–2025 corpus. **This key cannot answer Question 2.** What would: a paid tier with the calendar endpoint (then re-run this driver, about 10 calls), or a different vendor. Whether the paid tier also limits *calendar* history is unknown and worth asking before paying.

**The price side is reassuring.** Where the vendor and our cache can be compared, they are identical, so the cache is not systematically wrong. But the comparison is only one year deep, which is the period *after* most of the corpus, and it says nothing about 2020 to 2024, where the PARA defect lives.

## 6. Deviations and premises

1. **Question 2 not answered** (subscription 403). Not an anticipated failure: the prompt expected a network block, not a plan restriction.
2. **ENPH is not in our price cache** (prompt premise wrong). Five companies compared, not six.
3. **The free tier serves one year of prices,** so the prompt's six-year price comparison was not possible. It is stated as a finding, as the prompt asked.
4. **Extra six calls (10 to 15)** for the renamed-company symbol question, which ground rule 5 asks me to report. They use the price endpoint the free tier allows.
5. **Vendor account details** (name, email, invite token) in the cached account response were **redacted before commit**. The API token was never written anywhere; I scanned the raw files, driver and prompt directory for it.
6. **`raw/` committed** as instructed; it contains no token.

## 7. Verification

- Counter: 15 calls, logged with endpoint and parameters (no token) in `progress.json` → `call_log`; incremented before each request. Cap 300 never approached.
- Cached raw responses re-read for every comparison; a re-run costs no calls.
- Token scan across `raw/`, `analysis/eodhd_probe.py` and `prompts/`: no match.
- Not verified: split adjustment, calendar behaviour, any consensus figure.

## 8. Follow-up commands

```
# recompute the comparisons from cache (0 calls)
python3 analysis/eodhd_probe.py analyze1

# ONLY on a key that allows the earnings calendar (about 10 calls):
python3 analysis/eodhd_probe.py calendar 12
```

Provenance: `analysis/data/run_state/eodhd-coverage-probe/` — `progress.json` (`calls_used`, `call_log`), `raw/`, `step1_price_comparison.json`, `symbol_preference.json`, `findings.md`; our prices from `analysis/data/corpus_v2/scorer_price_cache_v1.json`.
