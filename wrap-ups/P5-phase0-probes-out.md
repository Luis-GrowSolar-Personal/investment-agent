# P5 phase 0: decisions recorded, two data sources probed. Wrap-up

**Run ID:** `p5-phase0`. Branch `sweep/db-corpus-baseline`. **Complete run. $0 in model calls** (no Claude API calls, DB writes, scoring, or price/return reads). **29 of 30 SEC EDGAR requests** and **11 of 20 vendor calls** used (counted in `progress.json`).
**Scope boundary: report, do not decide.** The P5 design is under architect review; nothing beyond phase 0 was built.

> EDGAR **works** from this Mac: **3 of 3** companies resolved; RUN and MU have dated 10-Ks for 2019–2025, and **JPM's older 10-Ks (2019–2023) were not reached** within the request cap (its history sits in 70 date-sliced overflow pages). RUN's 2022 10-K **does not name** a supplier in searchable text: it has a "Supply Chain" section that says equipment comes "from a limited number of manufacturers and suppliers" and names none. Transcripts for companies not on disk **are** available: **5 of 5** returned 2020–2025 event lists and a full transcript. Holdout companies have **0** transcripts on disk. **Phase 1 is technically unblocked, with one design risk flagged below (filings may name few suppliers).**

## Step 1 — decisions recorded (commit `d1fcb10`)
Insertions, each marked `(amended 2026-09-26, Luis)`:
- `docs/architecture/DESIGN_PRINCIPLES.md` §1: the amendment sits directly after the sentence saying the analyst never receives "data about any other ticker".
- `docs/architecture/PROMPT_ARCHITECTURE.md` §1.4: the same sentence, plus "Peer text may cross the train / tune / holdout split as input only. Holdout calls are never scored until the final look. Links between companies come from filings dated before the call, not from judgement (P5 design §3)."
- `PROMPT_ARCHITECTURE.md` §2.2, P5 row: "design drafted 2026-09-26 (…design.md), under review; phase 0 probes running".
**Propagation (`git grep "any other ticker"`):** only `DESIGN_PRINCIPLES.md:15` (the amended file) and the design doc itself (`docs/handoffs/2026-09-26-p5-peer-readthrough-design.md:62`, which proposes the amendment). No other file restates the old sentence. Not edited.

## Step 2 — EDGAR probe (`edgar_probe.json`; script `analysis/p5_edgar_probe.py`, `p5_edgar_offline.py`)
Every request logged there (URL, status, bytes, seconds; the `User-Agent` value, read from `.env` `SEC_USER_AGENT`, is never printed or stored). 1 request per second.

| ticker | CIK | 10-K / 10-K/A filed 2019–2025 found |
|---|---|---|
| RUN (Sunrun) | 1469367 | 8: 2019-02-28, 2019-03-05 (10-K/A), 2020-02-27, 2021-02-25, **2022-02-17**, 2023-02-22, 2024-02-21, 2025-02-27 (needed one overflow page for 2019–2020) |
| MU (Micron) | 723125 | 7: 2019-10-17 … 2025-10-03, all in the recent list |
| JPM (JPMorgan) | 19617 | **2 only**: 2024-02-16, 2025-02-14 |

**JPM shortfall, and why.** JPM files so often that its submissions file lists just its most recent filings, and the older ones sit in **70 overflow pages** of about one month each. My script fetched those pages newest-first and stopped at the request cap after 23, reaching June 2023. Finding the 2019–2023 10-Ks this way would take about 40 more requests. **This was my inefficiency:** skipping the overflow for a known high-volume filer, or using the EDGAR company-browse page (one request), would have found them. The pass condition "dated 10-Ks for 2019–2025" is therefore met for RUN and MU and **not shown for JPM**; no evidence it is unavailable. Also of note: Micron's fiscal year ends in August, so its 10-Ks are filed in October.

**RUN's 2022 10-K** (filed 2022-02-17): retrievable, **3,241,885 bytes, 509,964 characters of text after tags are stripped**, searchable.
- Headings and terms (case-insensitive, `run_2022_10k_offline_analysis`): "Customers" 12 hits, **"Supply Chain" heading 1 (offset 68,342)**, "supplier" 44, "manufactur*" 23, "Competition" 2, "sole source" **0**. There is **no "Suppliers" heading**; the section is "Supply Chain".
- **No supplier company is named anywhere:** 0 hits for 20 well-known names (Tesla, Panasonic, LG, Enphase, SunPower, Trina, Jinko, Canadian Solar, Hanwha, SolarEdge, Qcells, LONGi, JA Solar, First Solar, Generac, Fluence, Samsung, CATL, BYD…) and no company-like name within 300 characters of any "supplier". The Supply Chain section starts, at offset 68,342: "We purchase equipment, including solar panels, inverters and batteries from a limited number of manufacturers and suppliers…". The Competition section (offset 70,084) names competitor **categories** (traditional utilities, community solar, similar solar companies), not companies.
- **So the first-sentence-naming-a-supplier-company target does not exist for RUN.** The probe's first-pass extractor matched a lease table (junk); I corrected it with the offline re-read (no network). This is a finding, not a defect of the fetch.
- **Not tested** (no requests left, one request remained): MU's 10-K, where the design expects customer concentration; and any other company. One filing is one data point.
The file is saved under `analysis/data/evals/p5_phase0_edgar/` (gitignored) and is not committed.

## Step 3 — transcript source (`transcript_probe.json`; script `analysis/p5_transcript_probe.py`)
**On disk ($0):** 109 companies have transcripts. By split: **train 54 of 57** listed, **tune 52 of 54**, **holdout 0 of 53** (as expected). Three more are on disk in no split: ELV, GOOG, PARA.
**Vendor (11 of 20 calls: 1 symbol list, 5 event lists, 5 transcripts):**

| company | why probed | events (2020 on) | years covered | one 2022Q2 transcript | turns / speakers | prepared remarks / Q&A markers |
|---|---|---|---|---|---|---|
| ENPH | not in corpus | 26 | 2020–2026 | 70,781 chars | 114 / 22 | yes / yes |
| NVDA | holdout | 30 | 2020–2027 | 54,596 | 39 / 13 | yes / yes |
| AMD | holdout | 26 | 2020–2026 | 54,048 | 67 / 14 | yes / yes |
| KLAC | not in corpus | 28 | 2020–2027 | 59,310 | 58 / 13 | yes / yes |
| ADI | not in corpus | 27 | 2020–2026 | 37,963 | 54 / 12 | yes / yes |

**Pass: 5 of 5** (needed 4). Level 2 (speaker-tagged) was accepted throughout. Event lists include scheduled 2026 and 2027 rows. "Quarter" is the vendor's own numbering (for companies with non-calendar fiscal years, "2022Q2" is the vendor's label, not a calendar quarter). The markers are simple text searches, not a check of completeness of the call.
**These transcripts were not written into the corpus transcript directory, and were not scored, digested or summarized.** They are in `analysis/data/run_state/p5-phase0/peer_probe/`. **Premise correction:** the prompt says that folder is gitignored; it was not (`run_state` is explicitly un-ignored in `.gitignore`). I added an ignore rule and verified it (`git check-ignore`) **before** any transcript was written; only `transcript_probe.json` (metadata) is committed.

## Step 4 — hand map ($0)
`docs/peers/HAND_MAP.csv` (header only: `company,linked_company,link_type,valid_from_year,valid_to_year,confidence,note`) and `docs/peers/README.md` (plain language: fill it for semis, solar, storage and software from your own knowledge before any filing-derived map is built or shown; committed before phase 1; years as understood at the time; tested separately from the filing links).

## Deviations, flags
1. `peer_probe/` was not ignored (above); a rule was added in its own commit.
2. JPM 10-K history incomplete (above; my request-ordering choice).
3. Two pending files at the start, both named in the prompt (the prompt and the design doc); no review file for P5 exists in `prompts/` or `docs/handoffs/`. Nothing else was untracked or modified.
4. No SEC or vendor hard stops (no 403/429/401 responses).

## Commits (in order)
`prompt: P5 phase 0 probes` · `docs: P5 peer read-through design, draft for review` · `docs: firewall amended for peer transcripts dated before the call; peer text may cross splits as input only (Luis, 2026-09-26)` · EDGAR probe script · EDGAR probe results · offline re-read · transcript probe script + `.gitignore` · transcript probe results + hand map · this wrap-up (hash in chat).

## What this means
- **Unblocked technically:** EDGAR can be read from this Mac at 1 request per second, and the vendor supplies transcripts, including for holdout and non-corpus companies, as peer input. Phase 1 waits on the architect review of the design and Luis's hand map.
- **One design risk to hand to the review:** the design's link source is filings dated before the call. For RUN, the 10-K names **no** suppliers or competitors, only categories. If that pattern is common (installers, and probably other sectors), filing-derived supplier links will be thin and the hand map may carry more of the load than the design assumes. This probe checked one filing; MU (customer concentration) and a software company are the cheap next checks (about 2 requests each). I did not decide this.
- **JPM-type filers:** when a company's submissions have overflow pages, fetch selectively (or use the company-browse route) rather than paging newest-first.

```bash
python3 analysis/p5_edgar_offline.py     # no network
python3 analysis/p5_transcript_probe.py  # 11 vendor calls; do not re-run without need
```
