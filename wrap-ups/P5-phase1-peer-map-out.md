# P5 phase 1 — sector diagnostics, then the point-in-time peer map and coverage. Wrap-up

**Run ID:** `p5-phase1`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial.**
**Real spend: $19.24** (8 extraction batches, `progress.json` → `spend_actual_by_batch`) against the $20 cap Luis approved at Step 0. **1,433 of 1,600 SEC requests, 123 of 150 vendor calls.** No scoring, no digest, no P5 prompt run.
**Scope boundary: report, do not decide.**

> Within sector and year, B ranks calls at **0.070** and **0.046** on its two draws (overall 0.130 / 0.099): **B's ranking is mostly across sectors**. From **1,120** 10-Ks and **1,662** earnings calls with a match, the point-in-time peer map holds **14,348** directional links (**7,132** from filings, **7,216** from calls; **1,045** calls have a supply-chain link, **859** a shared-competitor link, **932** a partner link — a call can count in more than one). **1,168** of 1,217 train calls have at least one linked peer call dated before them, within 120 days, and readable: **P5 continues to phase 2**. Supply-chain links alone cover **1,045** calls.

Sources: `analysis/data/run_state/p5-phase1/` → `sector_diagnostics.json` (Step 1), `filings_index.json` / `prefilter_filings.json` / `final_report_F.json` (Step 2), `prefilter_calls.json` / `final_report_C.json` (Step 3), `build_map_report.json` / `peer_links.csv` (Step 4), `coverage_report.json` (Step 5). Scripts: `p5p1_common.py`, `p5p1_sectors_fetch.py`, `p5p1_solar_check.py`, `p5p1_step1.py`, `p5p1_filings_fetch.py`, `p5p1_prefilter.py`, `p5p1_prefilter_calls.py`, `p5p1_extract.py`, `p5p1_build_map.py`, `p5p1_coverage.py`.

## Step 0 — bookends and the hand-map check
Prompt, `docs/handoffs/2026-09-26-p5-design-review.md` (untracked), and `docs/peers/HAND_MAP.csv`/`.xlsx`/`README.md` (modified by Luis) were each committed as their own commit. **Hand-map check** (`p5_handmap_check.py`, `hand_links.json`): 165 rows, **42 kept** (linked_company filled), **0 invalid**, split into **103** links. The README's "fill the workbook, not the CSV" instruction was superseded by the prompt's "CSV is canonical, workbook is a helper"; the CSV (already filled) was used, matching what the prompt asks.

## Step 1 — sector diagnostics ($0 in model calls; ~182 SEC requests)
`docs/peers/SECTOR_MAP.csv`: 164 companies, SIC group + override + solar/storage move, each with a basis. **13** companies moved to solar/storage/clean energy, each with a verbatim quote from its own latest annual report (RUN, NOVA, SPWR, SUNW, SEDG, FSLR, ARRY, SHLS, CSIQ, EOSE, QS, MAXNQ, JKS). **Flagged, not moved:** AMPX, ENVX (their business is batteries for mobility/consumer devices, not grid/solar storage — their opening business text does not describe stationary or solar storage), AMSC (grid equipment; solar is one customer segment among several), BLDP (hydrogen fuel cells). **FRC** does not resolve on EDGAR (an FDIC-regulated bank holding company, not an SEC filer under that name); **PARA** resolves on EDGAR to Banzai International (a ticker reuse) — Paramount itself is excluded from train analysis for corrupt prices, as established.

**1b, winners by sector-year.** Cells with ≥ 12 calls, biggest winner shares: solar/storage 2025 (57.1%, 14 calls), materials 2025 (50.0%, 12), semis 2020 (41.7%, 12), semis 2025 (37.5%, 24), banks/financials 2020 (32.0%, 25), solar/storage 2024 (31.2%, 16), against a 12.6% overall share. **Winners do cluster somewhat in a few sector-years.**

**1c, B's ranking within sector-year.** 55 cells have ≥ 12 calls, covering 88.7% of train calls. Weighted-average rank correlation inside those cells: **draw 1 0.070 (range −0.032 to 0.140)**, **draw 2 0.046 (range −0.063 to 0.111)** — against B's overall 0.130 / 0.099. **Neither draw clears the 0.08 threshold with a range above zero, so the pre-registered reading is "B's ranking is mostly across sectors."** Per the prompt: P5's phase 3 gate is computed within sector-year as a diagnostic, but gates on the overall comparison.

**1d, call-over-call change.** For the 1,162 train calls with a prior call of the same company, the rank correlation of B's score change with the 182-day return: draw 1 **0.075 (0.032 to 0.120)**, draw 2 **0.020 (−0.030 to 0.070)**.

## Step 2 — filing links (~1,433 SEC requests; $8.71 for 3,838 extraction requests)
**2a.** 1,120 10-K/10-K/A filed 2019–2025 across the 164 companies (1,070 10-K + 50 10-K/A), fetched with selective overflow paging (131 overflow pages, keyed to each filer's known filing window, not fetched newest-first — the phase 0 JPM lesson). Companies with no 10-K in the window: FRC (not an SEC filer), JKS/MAXNQ/CSIQ/BLDP (foreign private issuers, file 20-F/40-F), and XOM (EDGAR's current ticker resolution points at a holding-company CIK created after 2025 with no 10-K on file; the pre-2025 CIK was not fetched — a coverage gap, not investigated further under budget).

**2b.** 3,838 unique paragraphs after two passes: the mechanical pre-filter (4,646 unique, whole document searched, not only Item 1) then a stop-list pass removing word collisions found by reading the most frequent matches (Northern, Southern, Strategy, Emerging, Reliability, Freedom, Bancorp fragments, and more — `docs/peers/NAME_STOPLIST.csv`, extended twice in this run).

**2c, extraction, amended after the first pre-flight failed.** **Pre-flight v1** (40 paragraphs) **tripped the stop rule**: 26.8% of 138 quotes failed verbatim verification (limit 10%), 2 of 40 replies didn't parse. Reading the failures showed no invented text: the model joined non-adjacent fragments with "…" and used curly quotes where the source had straight ones. **Luis approved an amendment**: the quote instruction now asks for one contiguous span (no "…"), `max_tokens` raised 1200→2000, and the verifier normalises quote/dash characters and accepts a "…"-joined quote only if every segment appears verbatim in order. **Pre-flight v2 passed**: 0 of 110 quotes failed (re-scoring the v1 replies under the v2 verifier also drops failures from 26.8% to 4.3%, confirming the fix, not a new sample), labels spread (top 35.5%), but 1 of 40 replies hit `max_tokens=2000` on a long name list. **Luis approved a second amendment**: any reply that doesn't parse or hits `max_tokens` is re-submitted once at `max_tokens=6000`; a reply still failing after that is dropped and counted; a guard stops the run if post-retry drops exceed 2% of a batch. **Full run: 3,838 requests, 33 needed the retry, 10 dropped after it (0.26%, well under the 2% guard)** — every dropped id is in `final_report_F.json` → `dropped_ids`. **13,833 links kept** (COMPETITOR 5,499, OTHER 3,676, PARTNER 2,205, CUSTOMER 1,773, SUPPLIER 808); 128 further quote failures on the full run were dropped separately. Cost $8.71.

**2d, anonymised customers.** Not separately tallied in this run (the extraction schema records only named links); qualitatively, phase 0/0b already established this is common (ENPH: "one customer accounted for approximately 34%"). Not re-measured here — a gap against the letter of 2d, flagged below.

## Step 3 — call links ($10.10 for 6,374 extraction requests)
**3a.** Every transcript on disk under `analysis/data/corpus_v2/transcripts/` — **train and tune, 2,447 calls**. Holdout and non-corpus calls were not fetched as sources in this phase (they are peer inputs, read in Step 5's vendor check). This is a coverage limit: any link that exists only in a holdout company's own calls (e.g., NVDA naming a supplier) cannot be a *source* here, only a *target* of others' links.

**3b, pre-filter.** After exclusions (operator turns not searched at all, analyst firms without a business-relation word, word collisions), **6,374 passages in 1,662 calls** — mentions in the same speaker turn were merged into one passage (cap 1,800 characters) rather than sent as separate requests, to control cost; this halved the raw match count (11,066 → 6,374) without dropping any name.

**3c, extraction.** Pre-flight (v2 prompt reused) passed cleanly: 1.4% quote failures, no parse failures, labels spread (top 43.7%). Full run: 6,374 requests, retry needed on truncated/unparsed replies, **10 dropped after retry (0.16%)**. **14,017 links kept** (CUSTOMER 5,181, PARTNER 4,754, OTHER 2,705, COMPETITOR 1,259, SUPPLIER 313); 195 quote failures dropped. Cost $10.10.

**3d, recurrence.** Computed and stored on every link (`peer_links.csv` → `recurrence`, `single_source`); reported in Step 5.

## Step 4 — the map
Named companies were resolved to tickers against the name list (SEC `company_tickers.json` + `docs/peers/NAME_ALIASES.csv`, extended by 31 entries after reading the most frequent unresolved names: SAP, GM, HP, T-Mobile, GE, Paramount, Red Hat/MuleSoft/Tableau tagged to their parent, private AI labs marked not-listed). **3,440 distinct named-company mentions across both extractions could not be resolved** to a ticker (`build_map_report.json` → `unresolved_count`; a sample is in that file) — mostly product/brand names (Azure, YouTube, GCP, Tableau before the alias fix), foreign or private companies with no US ticker, government or municipal entities (Georgia PSC, Alabama Power's regulator), and genuinely unlisted names. These mentions are **dropped, not guessed at**, per the ground rules.

Every ticker (company and peer, both extraction and hand-map) was normalised through `TICKER_ALIASES.json`. `peer_links.csv` (28,902 rows): 7,132 direct filing links, 7,216 direct call links, 14,348 reversed rows (a link is a directional fact, stored both ways for lookup), 206 hand-map rows (103 kept links, most reversible). Ten most-linked train companies by outbound link count (their own filings/calls naming peers): **MSFT (1,390), AMZN (895), GOOG (850), QCOM (657), ORCL (631), INTC (589), SWKS (542), IBM (535), VZ (531), AAPL (529)**.

Example quotes, top three:
- **MSFT ↔ BOX, PARTNER, recurs 16×**: "we announced Box AI for Microsoft 365 Copilot, a new plugin for Microsoft's next generation AI workplace tool" (2023-08-29 call).
- **AMZN ↔ PLD, SUPPLIER (from PLD's view: Amazon is PLD's customer), recurs 17×**: "we've had a clear market leader, which is Amazon in excess of 40% of the total volume" (2020-07-21 call).
- **GOOG ↔ TTD, COMPETITOR, recurs 19×**: "more competitive with more bidders than just Google" (2024-02-15 call).

## Step 5 — coverage
**5b, vendor readability.** 123 of 150 vendor calls used (event lists only, no transcripts); 150 peers fetched, 170 left unchecked at the cap, prioritised by how many train targets each peer would newly cover (top: AMZN, AAPL, WMT, Huawei, Samsung, VWAGY, NVDA, ADBE, SAP, AMD — several of the highest-priority peers are not US-listed and returned nothing).

**5c, coverage (FILING + CALL only, headline):**

| measure | value |
|---|---|
| **train calls with ≥ 1 eligible, readable peer** | **1,168 of 1,217 (96.0%)** |
| excluding single-source links | 1,079 |
| with HAND links added (reported separately, never mixed into the headline) | 1,177 |
| filing links only | 889 |
| call links only | 1,121 |
| supply-chain (CUSTOMER/SUPPLIER) links alone | 1,045 |

By link type (a call can count under more than one): supply-chain 1,045, shared-customer/competitor 859, partner 932. By sector: industrials 199, pharma/health 138, semis 129, banks/financials 129, software/IT 113, solar/storage/clean energy 80, consumer staples 69, materials 68, energy 67, internet/media 64, utilities 42, other 25, REITs 24, telecom 21.

**Stop rule: not triggered.** 1,168 ≥ 300 by a wide margin.

## Deviations, flags, premises
1. **Two pre-flight failures, two Luis-approved amendments** (Step 2c above) — both spend-adjacent decisions, both asked before proceeding, both logged in `findings.md`.
2. **Step 2d (anonymised customers) was not separately measured** in the extraction output; this is a gap against the prompt's letter. The schema captures named links only. Fixable cheaply in phase 2 if wanted.
3. **XOM has no fetched 10-K** in this run (EDGAR ticker-resolution artifact around a 2025 restructuring); not investigated further.
4. **3,440 unresolved named-company mentions** were dropped rather than guessed. The true link count is a floor, not a ceiling.
5. **Anonymous/product-name references were not attributed to a parent company beyond the 31 aliases added.** A more complete alias table would raise both the link count and coverage, at $0 marginal cost; not pursued exhaustively under time and to keep the aliasing auditable (every alias is a committed, hand-checked row).
6. Holdout/non-corpus calls are not link *sources* in this phase, only *targets* found via the vendor (Step 5), per the prompt.
7. Vendor priority reached only 150 of 320 distinct not-on-disk peers named; 170 stayed unchecked. The headline coverage is therefore a **floor**, not the true ceiling — some of the 49 currently-uncovered calls may have a readable peer among the unchecked 170.
8. Git bookends followed: prompt and design-review committed first; every script committed before its output; every batch id committed at `create()`.

## What this means for phase 2
**Continue.** Phase 2 is the digests: for each of the 1,168 covered train calls, fetch (if not already on disk) the eligible peer transcript(s) and produce factual, point-in-time digests to hand the analyst. **Peers that must be fetched as transcripts** (not just event lists): the on-disk peers need nothing; the 150 vendor-checked peers need their specific in-window call fetched (not just the event list); the 170 unchecked peers would need an events call first, then the transcript, if phase 2 wants to close that gap. A rough vendor budget: at least one transcript fetch per distinct (peer, in-window call) pair actually used by a covered target — that number is not yet computed and should be phase 2's first free step, since it decides the vendor budget to request.

## Not done
No digests, no scoring, no phase 2, no DB writes, no cache refresh, no promotion of any kind.

```bash
python3 analysis/p5p1_step1.py
python3 analysis/p5p1_coverage.py
```
