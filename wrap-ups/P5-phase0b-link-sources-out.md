# P5 phase 0b: how often do filings and calls name linked companies? Wrap-up

**Run ID:** `p5-phase0b`. Branch `sweep/db-corpus-baseline`. **Complete run.** **Real spend $0.02** (Step 3: ten small model calls, `linktype_probe.json`), against the $3 cap Luis approved (the model step was approved in chat). **9 of 15 SEC EDGAR requests** used; no vendor calls; no DB writes, scoring, or price data. Only train transcripts were read.
**Scope boundary: report, do not decide.**

> Of 4 more 10-Ks, **3** named at least one competitor or customer company (**2** named customers: MU and Intel; **1** anonymised them: Enphase). Of 30 train earnings calls, **66.7%** named at least one other listed company by my by-eye count (**73.3%** on an automatic cleaning, **100%** raw), a mean of **1.9** per call (semis **3.3**, solar **1.8**, other **1.6**). **Sources sufficient.** Step 3: the link type read **9 of 10** plausibly by my own check (Luis's check-list is still to be applied; see below).

Sources: `analysis/data/run_state/p5-phase0b/` → `filings_probe.json` (Step 1, plus `offline_second_pass`), `calls_probe.json` (Step 2), `linktype_probe.json` (Step 3). Scripts: `analysis/p5b_names.py`, `p5b_filings.py`, `p5b_filings_offline.py`, `p5b_calls.py`, `p5b_linktype.py`. Alias list (committed): `docs/peers/NAME_ALIASES.csv`.

## Step 0 — bookends
The prompt and the design doc's Addendum A were each committed as their own commit before anything else. No P5 review file exists. Nothing else was modified or untracked.

## Step 1 — four 10-Ks filed in 2022 (`filings_probe.json`; 9 requests)
Name list (Step 2a, built once, saved gitignored): **11,477 names** (11,402 from SEC `company_tickers.json` after stripping suffixes and keeping names of 2+ words or 7+ letters; 75 from the hand alias list). MU's filing came from phase 0's saved accession, so no submissions request was spent on it. Overflow pages were not needed for INTC, ENPH or NOW.

| company (filed) | competitors named | customers | suppliers named |
|---|---|---|---|
| **MU** (2022-10-07) | **yes:** "Intel; Kioxia Holdings Corporation; Samsung Electronics Co., Ltd.; SK hynix Inc.; and Western Digital Corporation" | **named, in the financial notes ("Certain Concentrations"):** "Revenue from Kingston Technology Company, Inc. was 12% … of total revenue"; WPG Holdings Limited also | none seen |
| **INTC** (2022-01-27) | **yes:** "we compete with AMD and vendors … such as Qualcomm Inc.… and, increasingly, Apple Inc." | **named:** notes: "our three largest customers accounted for 43% … with Dell Inc. accounting for 21% …, Lenovo Group Limited … 12%, and HP Inc."; Item 1: "our first IFS customer, Amazon Web Services" | foundries named: TSMC, Samsung Electronics |
| **ENPH** (2022-02-11) | **yes:** "Competitors in the inverter market include, among others, SolarEdge Technologies, Inc., Fronius …, SMA …, Generac, Tesla, Inc., Huawei…"; storage: "Tesla, SolarEdge, LG Chem, Sonnen, Generac, Panasonic, BYD…" | **anonymised:** "In 2021, one customer accounted for approximately 34% of total net revenues"; sells "primarily to solar distributors", unnamed | none named |
| **NOW** (2022-02-03) | **no.** Its Competition section names no company. Business section names "Oracle, SAP, Salesforce, and Workday" as "well-established, enterprise application software vendors" it is designed to "integrate with, and complement" (a partner/complement relation, not stated as competitor or customer) | none named ("approximately 7,400 enterprise customers", by industry) | none |

Headings found by search: MU (Customers 1, Supply/Manufacturing 2, Competition 0 in Item 1; competition sits under "Competitive Conditions"), ENPH (1/3/1), NOW (6/1/1). **INTC's Item 1 span measured only 159 characters** (its 10-K is organised differently), so the offline second pass read INTC over the whole document (`offline_second_pass`); that is where its named customers and competitors were found. Named customers in **financial-statement notes** (MU, INTC) are outside the sections the prompt names, and I counted them; the design's "10-K of either company" source covers them.
**Count for the reading:** at least one competitor or customer company named in **3 of 4** (MU, INTC, ENPH). NOW does not, on a strict reading. **Named customers: 2** (MU, INTC). **Anonymised: 1** (ENPH's "one customer … 34%"). Quotes above are verbatim from the saved filings.

## Step 2 — company names in 30 train calls (`calls_probe.json`; $0)
Sample (seed `p5-0b-11`): the required six (one 2022 call each: RUN 2022-08-03, MU 2022-12-21, INTC 2022-10-27, JKS 2022-08-26, QCOM 2022-04-27, NXPI 2022-02-01) plus 24 other train companies, one 2021–2023 call each.
**The first-pass count was misleading, and I corrected it after reading the matches.** Raw matching gave **30 of 30 calls (100%), mean 4.37 companies per call**. Reading the matches, most were **analyst firms named by the operator** ("Our next question is from … with **Morgan Stanley**": 39 mentions; **Evercore** 27; **Credit Suisse** 26; **Barclays** 21; **Oppenheimer** 18; **Citigroup** 10) and word collisions ("Perfect." as an acknowledgement, "Eastern Europe", battery "Celsius", "Amplitude" the product, "Verizon Conferencing"). I therefore report three tiers, with the exclusions written into the script (`ANALYST_FIRMS`, `WORD_COLLISIONS`, `BY_EYE_FALSE`):

| tier | calls naming ≥ 1 other listed company | mean distinct per call | semis (4) | solar (4) | other (22) |
|---|---|---|---|---|---|
| raw (all matches) | 30 of 30 (100%) | 4.37 | — | — | — |
| second pass (operator turns, analyst firms, word collisions removed) | **22 of 30 (73.3%)** | 2.03 | 4/4, 3.25 | 4/4, 2.25 | 14/22 (63.6%), 1.77 |
| **by eye** (5 more non-company matches removed: "wet AMD" (an eye disease), "Dell Rent" (Delrin), "Northern California", "Exponent", "Lithium") | **20 of 30 (66.7%)** | **1.87** | 4/4, **3.25** | 4/4, **1.75** | **12/22 (54.5%)**, 1.64 |

**Where the mentions sit** (second pass): 44 in prepared remarks, 72 in Q&A. The Q&A share is high partly because analysts name competitors and customers in their questions.
**What the real mentions look like** (verbatim examples): RUN: "Our partnership with **Ford** has officially kicked off…"; MU: "validated for the new **AMD** EPYC 9004 series processors"; "validated for **Qualcomm**'s latest platform"; JKS: "**Canadian Solar** has expressed an intention to get into the polysilicon business"; QCOM: "multi-year contract technology collaboration with **Stellantis**"; "OEMs such as **Samsung**, Xiaomi, Oppo, Vivo, and Honor"; NXPI: "the announcement … in November with **Ford Motor Company**"; INTC: "**Amazon** will be accelerating large transform models with Gaudi instances"; AIG: "strategic partnership with **Blackstone** … partnership with **BlackRock**"; CMI: "We shipped 38,000 engines to **Stellantis**"; NEM: "strategic alliance with **Caterpillar**". Eight of the 22 "other" calls name nothing listed (COF, DUK, ELV, HON, KMB, MS, PG, TMO) besides the excluded analyst firms.
**Usability of the required six's peers** (a link needs the peer's calls to be readable; `required_six_peer_usability`, by-eye mentions only):
- RUN → Ford: in no split file, not verified fetchable.
- MU → **AMD** (holdout; fetched in phase 0), **Qualcomm** (train, on disk).
- INTC → **IBM, Microsoft** (train, on disk), **NVIDIA** (holdout; fetched in phase 0), **Alphabet/Google** (tune split), **Amazon, Meta** (in no split file).
- JKS → **Canadian Solar** (holdout).
- QCOM → **Apple** (holdout), **Microsoft** (train), **Stellantis** (no), **Samsung** (not US-listed).
- NXPI → Ford (no).
Vendor fetchability was verified in phase 0 only for ENPH, NVDA, AMD, KLAC and ADI; **the vendor's full symbol list was not saved in phase 0** and no vendor calls were allowed here, so fetchability for the others is not assessed. A peer in the holdout or tune split can be read as input under the amended firewall.

## Step 3 — can the link type be read? ($0.0197; `linktype_probe.json`)
Ten seeded mentions from Step 2's by-eye list (5 from semis/solar calls, 5 from other), each shown to `claude-sonnet-4-6` as only the sentence plus two sentences either side.

| # | call | named | label | supporting quote (verbatim) | my read |
|---|---|---|---|---|---|
| 1 | QS | Tesla | OTHER | "welcome Celina Mikolajczak from Panasonic and Tesla as our VP of Manufacturing Engineering" | ok (an employee's past employer) |
| 2 | QCOM | Microsoft | PARTNER | "We have been working with Microsoft for many years." | ok |
| 3 | INTC | Microsoft | OTHER | "PC usage is high as seen by Microsoft and their metrics" | ok (a market reference) |
| 4 | QCOM | Apple | CUSTOMER | "your prior commentary about Apple exposure and so on" | plausible (an analyst's question) |
| 5 | RUN | Ford | PARTNER | "Our partnership with Ford has officially kicked off" | ok |
| 6 | NOW | Microsoft | PARTNER | "the Microsoft partnership and the CoSell agreement" | ok |
| 7 | MSFT | Adobe | PARTNER | "Leading third-party SaaS vendors, including Adobe, Atlassian, Salesforce…" | ok |
| 8 | COST | Amazon | COMPETITOR | "you've seen I think Amazon and Walmart have moved up" | **arguable** (an analyst comparing wage moves; could be OTHER) |
| 9 | MSFT | Walmart | CUSTOMER | "Walmart is using Cosmos DB to handle billions of online requests daily" | ok |
| 10 | SIRI | Salesforce | SUPPLIER | "utilizing Salesforce's marketing and data clouds" | ok |

Label counts: PARTNER 4, CUSTOMER 2, OTHER 2, COMPETITOR 1, SUPPLIER 1. **The stop rule (one label over 8 of 10) is not tripped.** Every quote was checked to appear verbatim in the passage (`quote_in_passage`). **The score against Luis's check-list is not computed:** it needs Luis to read the table; my read above (9 of 10 defensible) is labelled mine. Note the model is told only the passage, so "the speaker's company" is inferred; two of the ten (#3, #8) are where that inference is weakest.

## Pre-registered reading, applied
- Calls: **66.7% ≥ 60%** (holds at every tier: 73.3%, 100%). Filings: **3 of 4** name a competitor or customer company. → **"Sources sufficient."**
- Fragility, plainly: it is 30 calls; the pass on calls is 6 percentage points above the line at the strictest tier, and the "other" sector (22 calls) alone is 54.5%, under 60%. The filings pass is exactly 3 of 4, and NOW is the miss. The count of "real named companies" needed my by-eye layer; the alias/name matcher misses unlisted names (Kingston, Xiaomi, Oppo, Sonnen, Fronius…) and mislabels analyst firms, so a phase 1 extractor will need a model step to separate company references from analyst-firm mentions, as the design already assumes.

## Deviations, flags
1. The first-pass "100%" was wrong as a measure of link sources (above). It is reported as the raw tier, and superseded for the reading by the by-eye tier.
2. **Step 3 cost $0.02, not ~$1**: ten short passages. Well inside the $3 cap.
3. **Vendor symbol list** was not saved in phase 0, so "fetchable as peers" is answered only for the five phase 0 verified; no vendor calls were made.
4. INTC's Item 1 heading parse failed (159 characters); handled offline over the whole document.
5. Named customers in the financial notes were counted; the prompt's sections (Customers, Suppliers, Competition) would have missed INTC's and MU's named customers.
6. Sector lists for the split (semis: MU, INTC, QCOM, NXPI, SLAB, DIOD; solar/storage: RUN, JKS, EOSE, QS, AMPX, SUNW) are mine (`sector_lists`); the 'semis' and 'solar' groups have 4 calls each, so their means are indicative only.

## What this means for phase 1's source hierarchy
- **Calls carry most of the load, with filings as a second source.** Calls name other companies on about two thirds of calls (by eye), more in semis (4 of 4, ~3 per call) than outside the corpus's focus sectors (55%); filings name competitors in 3 of 4 cases and, in the two where customers are named, do it in the financial notes rather than in the business section. The two sources name different things: filings give lists of competitors and large customers with percentages; calls give partnerships, named customers and competitor references, mostly in Q&A.
- **Phase 1 needs three things the probe did not test:** a step that separates company references from analyst-firm names and word collisions; a check that the named peer's calls are readable (only three of the required six calls' peers are in the corpus or verified fetchable); and how often a named link recurs in more than one call (a link seen once is thin).
- Hand links remain a tagged supplement, as the design says. This run does not decide anything about them.

```bash
python3 analysis/p5b_calls.py            # $0, no network
python3 analysis/p5b_filings_offline.py  # $0, no network (needs the gitignored saved 10-Ks)
```
