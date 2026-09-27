# P5 phase 2a — tighten the peer map, check that news passes from peer to target. Wrap-up

**Run ID:** `p5-phase2a`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial. $0 in model calls.** 175 of 400 SEC requests used (173 non-corpus peer SIC codes, 2 for XOM). No vendor calls, no Claude API calls, no scoring, no digests.
**Scope boundary: report, do not decide.**

> Under the tight rule, the peer map keeps **1,201** links (from 19,034 pooled loose-map rows), and **643** of 1,217 train calls have at least one selected peer (**521** via filings supply chain, **559+27** via competitors [C1+C2], **109** via call supply chain); AAPL goes from **529** links to **26**. A peer's reaction to its own call predicted the target's move before the target's call at **0.093**, against **0.063** for matched control peers (difference **+0.030**, range **−0.027 to +0.146**), scored on **99.4%** of selections (but only **52.1%** had a matched control): **P5 stops**. Against the target's next six months the same figure is **0.005** (control **−0.032**, difference **+0.036**, range **−0.120 to +0.275** — includes zero either way). Phase 2b's cost was not projected (Step 3 is conditional on the gate).

Sources: `analysis/data/run_state/p5-phase2a/` → `tight_report.json`, `coverage_tight.json` (Step 1); `leadlag_report.json`, `leadlag_pairs.csv` (Step 2); `gaps_4a_anonymised.json`, `gaps_4b_xom.json` (Step 4). Scripts: `p5p2a_tight.py`, `p5p2a_select.py`, `p5p2a_leadlag.py`, `p5p2a_gaps.py`.

## Step 0 — bookends
Prompt, `docs/peers/PEER_MAP_REVIEW.csv` (Cowork review aid), and `docs/handoffs/2026-09-27-p5-phase2a-review-brief.md` were each committed as their own commit. `docs/handoffs/2026-09-27-p5-phase2a-review.md` was already tracked from an earlier commit (`ac90fec`). **Verified before running:** the prompt's Step 2 correctly reflects the review's two changes (control drawn from the peer's sector, excluding every phase 1 peer of the target; the gate is lead-lag x→y1, not co-movement) and its small fix (the scorer's frozen cache, not the raw one). The review does not mention the C2 mutual-competitor rule the prompt's header claims came from it; C2 is a separate Luis addition, not asked for by the review file — noted, not treated as a discrepancy requiring a stop, since the review asks for nothing the prompt omits.

## Step 1 — the tight rule

**How links were pooled (a documented interpretation, not in the prompt's literal wording).** `peer_links.csv` already stores, for every extracted mention, both the "direct" row (a company's own document naming a peer) and its algebraic mirror (same source, relation inverted, company/peer swapped). For S1/S2 ("either company's filing/call counts"), a triple (company, peer, relation) was judged qualified by pooling **all** rows matching it — direct and mirrored — since a mirrored row still traces to a real filing or call, just re-expressed from the other side. For C1/C2, where "who named it" cannot be read off the relation label (COMPETITOR mirrors to COMPETITOR), each row's true source owner was recovered from its `source_id` (the filing's accession → filer, or the call's ticker prefix) via `filings_index.json`.

**Non-corpus peer sectors:** 178 non-corpus peers survived to the COMPETITOR test and needed a SIC code; 173 SEC requests fetched them (some already tagged `unknown` for not-US-listed names, no request needed).

**Result (`tight_report.json`):** **1,201 tight links**, down from 19,034 pooled rows (14,348 distinct pairs' worth from phase 1) — **S1 606, S2 302, C1 278, C2 15**.

**Peer selection and coverage (`coverage_tight.json`).** Up to 3 peers per target, ordered S1 → C1/C2 → S2, ties by more sources then the most recent peer call. **Readability used on-disk transcript dates only** — this run's ground rules bar vendor calls, unlike phase 1's coverage check, which also used 150 vendor-verified peers. This is a real scope narrowing, not a like-for-like re-measurement of phase 1's number.

| | value |
|---|---|
| train calls covered | **643 of 1,217 (52.8%)** |
| by rule | S1 521, C1 559, S2 109, C2 27 (selections, not links — a call can select more than one) |
| mean peers per covered call | 1.89 |
| stop rule (< 300) | **not triggered** |

By sector: semis 128, software/IT 96, industrials 91, pharma/health 63, banks/financials 50, internet/media 48, consumer staples 38, solar/storage/clean energy 34, utilities 40, REITs 24, telecom 16, energy 15.

**Ten most-linked companies after tightening:** MSFT (127), GOOG (59), INTC (54), SWKS (52), ORCL (49), NVDA (46), AMZN (44), CRM (44), QCOM (42), AVGO (39). **AAPL: 529 → 26** (13 pairs, each counted both ways), all under S1 (supplier/customer). AAPL's 13 surviving peers, one quote each: QCOM ("share within Apple", 2019-11-06), AVGO ("Apple is seeking indemnification from Broadcom", 2019-12-20), NXPI ("Our 10 largest OEM end customers… Apple…", 2020-02-27), SWKS ("Apple broad markets piece", 2019-11-14), NWS ("including Amazon, Apple, Barnes & Noble and Tesco", 2020-08-11), ADBE ("Apple's App Store", 2023-01-17), TMUS ("phones… more expensive from Apple", 2019-02-07), FSLR ("our first corporate related PPA with Apple Inc.", 2019-02-22), CHTR ("new devices including 5G models from Apple, Google and Samsung", 2021-01-29), XYZ ("the Apple App Store and Google Play", 2021-02-23), INTC ("ramp down of modem and Apple Mac revenue", 2021-01-22), VZ ("everyone knows Apple comes out with a new product", 2025-10-29, S2).

**One residual concern, flagged plainly:** **AAPL–CHTR survives**, on a different quote than the "TV content" pairing Luis flagged as weak. S1 only requires one filing source with a customer/supplier word and a name match — it does not judge whether the substance is material. The tight rule cut AAPL's link count by 95%, but it is a volume filter, not a substance filter, and at least one of the pairings Luis named as an example of the problem is still present in a different guise.

## Step 2 — does news pass from peer to target?

**Prices:** `analysis/data/corpus_v2/scorer_price_cache_v1.json` throughout, as named.
**Whose prices were read:** train and tune peers only; 0 of this run's selections turned out to involve a holdout or non-corpus peer (both exclusion counters are 0 — the tight rule's peer-readability step already restricts peers to on-disk train/tune companies, so the holdout/non-corpus exclusion is satisfied by construction here, not by a separate filter catching cases). 7 selections were dropped for missing price data.

**Scored: 1,209 of 1,216 selections (99.4%).** But **only 630 of those (52.1%) got a matched control** — no eligible same-sector train/tune company (excluding every phase 1 peer of both the target and the real peer) had a call within ±10 days for the rest. **Per the reviewer's own standard, quoted back: "a pass on a minority of pairs is not a pass on the map."** The *scoring* rate is fine (99.4%); the *control* rate, which the gate actually depends on, is not — under 6,300 requests, 630. **The gate figure below is computed only on the 630 pairs with a control**, so effectively the check speaks for about half the tight map, not 99.4% of it.

| | tight | control | diff | range |
|---|---|---|---|---|
| **x → y1 (the gate)** | 0.093 (n=1,209) | 0.063 (n=630) | **+0.030** | **−0.027 to +0.146** |
| x → y2 (reported, train targets) | 0.005 | −0.032 | +0.036 | −0.120 to +0.275 |

**Gate: the range includes zero. Pre-registered reading: "P5 stops."** y1 window under 5 trading days on 174 of 1,209 pairs (14.4%) — most windows are longer, so the check is not dominated by same-day noise.

**By rule** (only rules with ≥ 15 scored pairs reported, as pre-registered by the report's own structure):

| rule | n | tight x→y1 | control x→y1 | diff | range |
|---|---|---|---|---|---|
| **S1** | 521 | 0.125 | 0.060 (n=248) | +0.066 | −0.012 to +0.331 |
| **S2** | 106 | **−0.025** | **0.194** (n=14) | **−0.219** | **−0.500 to −0.093** |
| **C1** | 555 | 0.072 | 0.068 (n=368) | +0.004 | −0.119 to +0.109 |
| **C2** | 27 | **0.559** (0.210 to 0.717) | — (n=0) | — | — |

**S1 alone comes closest to a positive gate** (range's lower end −0.012, just below zero) and has the most controls. **S2 is a genuine negative finding, not noise**: its diff range sits entirely below zero — call-sourced supply-chain links underperform their own sector's control on lead-lag, the opposite of what the mechanism predicts, with a range that excludes zero in the wrong direction. **C1 is flat.** **C2's tight figure (0.559) is the strongest single number in the whole check**, but it has zero eligible controls (no non-peer same-sector train/tune company had a call within ±10 days of any of the 27 C2 peer calls), so it cannot be compared to a baseline and is reported, not read as evidence.

## Step 3 — not run

**The gate failed, so Step 3 (phase 2b's projected digest cost) was not run**, per "only if Step 2 continues."

## Step 4 — two small gaps

**4a, anonymised customers ($0, regex, no model).** **29 distinct filers**, 2019–2025, disclosed a revenue-percentage customer concentration without naming the customer, in at least one 10-K (12–22 filers per year). Repeat filers: AAPL, AMD, AVGO, DIOD, FORM, FOXA, NVDA, PM, PYPL, SEDG, TMUS. Quotes: AAPL "one customer that represented 10%" (2019, 2022, 2023, 2025 10-Ks); AMD "Customer A 19%" (2019 10-K); three more in `gaps_4a_anonymised.json`. This confirms, at corpus scale, what phase 0/0b found on single filings.

**4b, XOM ($0, 2 SEC requests, heading search only, no extraction re-run).** XOM's pre-2025 CIK is **34088**, and it holds all **6** expected 10-Ks (filed 2020–2025, covering fiscal years 2019–2024). Phase 1's gap was an EDGAR ticker-resolution artifact: the CIK the ticker currently resolves to (created around a 2025 restructuring) has no 10-K; the historical CIK does. The latest 10-K (filed 2025-02-19) has Customers (2 hits), Competition (1), Supply/Manufacturing (1) — headings present, so **a link would very likely change if extraction were re-run** for XOM (an oil major naming named competitors is typical of the sector, as seen for OXY/PSX/COP in the existing map), but this was not tested; extraction was deliberately not re-run here.

## Deviations, flags, premises
1. **S1/S2 pooling logic** (documented above) is an interpretation of "either company's filing/call counts", not a literal instruction in the prompt; I believe it is the intended reading and explained why.
2. **My own bookkeeping error:** `progress.json` → `edgar_requests_used` was mistakenly hand-set to 7 partway through the run; corrected to 175 (173 + 2) before this wrap-up, with the correction itself committed and noted in `findings.md`.
3. **Peer-selection eligibility used on-disk dates only** (no vendor calls, as this run's ground rules require) — a real scope difference from phase 1's coverage number, not a re-measurement of it. The 643-call figure and phase 1's 1,168 are not directly comparable.
4. **Control coverage (52.1%) is thin**, and is itself the reason the gate result should be read cautiously in either direction — a wider control search (more days, or relaxing to ±15/±20) was not tried, since the rule was fixed before any price number was computed, per ground rule 3.
5. **C2 has zero controls**; its strong tight-only figure is not evidence under this design, only a number worth a second look if the map's future.

## What this means

**Under the pre-registered rule, P5 stops here on the primary gate.** The tight map's lead-lag signal (0.093, control 0.063) is higher than its control, but the ticker-block range of the difference includes zero, so it cannot be told from chance at this sample. **Two things complicate reading that as a clean "no":** the control sample is half the size of the scored sample, and the rules disagree with each other — S1 is closest to positive, C1 is flat, S2 is genuinely negative, and C2 (uncontrolled) is the largest positive number in the table. A digest-based read of these calls will not find, on average, a signal that the raw price move itself does not show over the same window — that is what the gate tested, and it did not clear.

**Is the tight map still worth keeping as an allocator input?** For the correlated-positions question (not gated here, and not computed in this run since Step 2's weekly co-movement line was superseded by the lead-lag gate per the review), the map itself — 1,201 point-in-time, sourced, quoted links — is a real asset independent of whether P5 as a *read-ahead* analyst input works. Whether it is worth maintaining for that purpose, separate from digests, is Luis's call, not this run's.

## Not done
No digests, no scoring, no Step 3 cost projection, no re-extraction for XOM, no phase 2b, no DB writes, no cache refresh.

```bash
python3 analysis/p5p2a_tight.py
python3 analysis/p5p2a_leadlag.py
```
