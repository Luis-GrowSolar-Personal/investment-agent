# corpus-fix-8: expand to about 150 companies — wrap-up

**Run ID:** `corpus-construction` (continuation). **$0 Anthropic API. Zero
transcripts scored.** 238 EarningsCall.biz vendor metadata calls (call
dates/counts only, no transcript text), well spaced under the 20/min limit.
Price data via yfinance/Yahoo, written only to `corpus_v2_price_cache.json`.
Branch `sweep/db-corpus-baseline`. Pushed at the end.

**No return was looked at anywhere in this run.** Every selection, drop,
and freeze decision traces to call dates, price-series dates, and the
registered A1/A2/A9 rules — never a hit/miss or a return. Confirmed by
inspecting the driver: it never computes one.

---

## Plain-language summary

The corpus needed roughly 150 companies to get precision down to about 2
points, using the square-root arithmetic this project now trusts over a
single Monte Carlo draw. This run drafted about 90 new candidates —
large-caps, out-of-domain sector names, and in-domain software/semiconductor/
solar names — checked every one against the same rules already governing
the existing 75 companies, and froze the result.

**Fewer candidates were lost than expected.** The prompt planned for roughly
15% attrition (select 90, expect to land ~75). Only 6 were dropped —
**6.7% attrition**, well under plan — so the corpus landed at **159**
companies instead of ~150, a modest overshoot rather than a shortfall. Worth
noting for next time: this project's attrition estimate, based on two
earlier rounds, is now looking high rather than low.

**A data anomaly, not a corpus defect, cost three more candidates.** Two of
the three price-coverage drops — Interpublic Group and Bank of New York
Mellon, both large, obviously still-trading NYSE companies — came back
"possibly delisted" from Yahoo at the raw API level, not just through
yfinance. That's almost certainly a transient provider issue, not a real
gap, and is flagged as worth a retry rather than a permanent exclusion.

**Identity resolution worked as designed.** Four candidates that looked
dead on their primary ticker (ViacomCBS, Anthem, Square, News Corp Class A)
all turned out to have complete data under a renamed or share-class
ticker — exactly the Alphabet/GOOG lesson from two runs ago, now
applied before anything was failed rather than after.

> The corpus is now **159 companies**, **107** available for iteration. The
> paired threshold is **1 point** simulated (flat across all three brackets),
> **1.9–2.3 points** by the square-root check, against **3 points** before
> this run. Scoring it would cost roughly **$336** (3,618 total calls in the
> corpus at this project's own observed ~$0.093/call rate — see §5).

**Trust the square-root check, again.** The simulation returned a flat 1pp
in every bracket at n=107 — implausibly tight, and the same optimistic
pattern flagged at n=46 three runs ago, before the corpus was smaller and
the two methods happened to converge at n=48/54. **1.9pp (this project's
own recheck formula) is the number to plan against, not the simulated 1pp.**

---

## 1. Step A — the expansion registered

`A10_expansion_to_150` written into `PREREGISTRATION_FIX.json`, dated,
before any candidate was examined. Justified only on the precision
arithmetic (`20/√n`): 48→2.9pp today, 100→2.0pp, ~150 total (~100 available)
needed for a genuine 2-point ruler.

**Premise correction, noted in the addendum itself:** the prompt states the
S3 sector cap was "raised from 4 to 6 because 11 sectors at 4 cannot supply
50." `selection_working.json` → `S3.reserves` has **9** registered sector
keys, not 11. The arithmetic conclusion still holds (9×4=36 < 50, so the
cap still needed raising) — only the sector count is corrected here.

**Quotas as registered:** S1 +25 (ranks ~41-80, general knowledge, same
caveat the original S1 selection carried), S3 +50 (9 sectors × ≤6, weighted
toward materials/real_estate/media_telecom/utilities/healthcare_pharma —
all thin or empty in today's 20-member S3), S2 +12 primary +3 reserve,
S4 attempt.

## 2. Step B — the roster

`analysis/corpus_fix8_candidates.py`. 90 candidates drafted (25 S1, 50 S3,
15 S2 including reserves), cross-checked against `CORPUS_MANIFEST_V4.json`
for duplicates before any vendor call — none found. **No S4 candidate was
identified** — general-knowledge search only, not exhaustive; reported as a
shortfall, matching the prior two rounds' experience exactly.

**SPAC-era candidates, listed and not added, per A10:**

| Ticker | Domain fit | Public since | Real call count (this run's vendor fetch) |
|---|---|---|---|
| SUNL (Sunlight Financial) | Residential solar financing | 2021-07-09 (SPAC) | 8 calls, 2021-08-16 → 2023-05-15 |
| MVST (Microvast) | Battery/energy storage manufacturer | 2021-07-23 (SPAC) | 17 calls, 2021-11-15 → 2025-11-10 |
| VLTA (Volta Industries) | Borderline — EV charging, not squarely storage | 2021-08-26 (SPAC) | 4 calls, 2022-04-18 → 2022-11-14 |

`analysis/data/corpus_v2/FIX8_SPAC_ERA_RELAXED_CANDIDATES.json`.

## 3. Step C — call availability

**A methodology bug found and fixed mid-run.** The vendor's `/events`
endpoint returns a company's **entire** available history, not just
2020-2025 — e.g. UNH's raw events span 2019-01-15 to 2026-07-16. The first
pass over all 90 candidates used unfiltered dates (n=31 for UNH instead of
the correct 24), which would have corrupted every gap/count check. Every
other corpus driver's `n_calls_2020_2025` figure implicitly assumed the
window; the original 77-company corpus apparently has no vendor history
before 2020 for its own candidates, so this bug was real but never
previously visible. **Fixed**: `get_call_dates` now filters explicitly to
`[2020-01-01, 2025-12-31]`; the driver was committed with the fix before
any candidate result was recorded a second time (`3abdf9b`).

**87 of 90 pass A1**, after identity resolution on four that initially
failed:

| Ticker | Failed as | Resolved to | Mechanism |
|---|---|---|---|
| VIAC | 0 calls | **PARA** | ViacomCBS renamed Paramount Global, Feb 2022 |
| ANTM | 10 calls, gap 364d | **ELV** | Anthem renamed Elevance Health, June 2022 |
| SQ | 0 calls | **XYZ** | Block Inc. ticker change from SQ, Jan 2024 |
| NWSA | 0 calls | **NWS** | Vendor keys News Corp's calls to the Class B ticker |

All four added to `TICKER_ALIASES.json`.

**Real A1 failures, dropped, no reserve available (S1/S3 had none built this
round):**

| Ticker | Stratum | n calls | Max gap | Why |
|---|---|---|---|---|
| SCHW | S1 | 16 | 539d | Genuine multi-year reporting gap in vendor data (TD Ameritrade merger period, Oct 2020) |
| ED | S3/utilities | 11 | 1,099d | Large, unexplained vendor coverage hole for Con Edison — surprising for a major utility, flagged as a possible vendor data-quality issue rather than a real reporting lapse |
| MSTR | S2 reserve | 13 | 553d | Reserve candidate; not needed since the S2 primary list already met target |

Vendor calls consumed: 238 (`FIX8_AVAILABILITY_SWEEP.json` →
`vendor_calls_used`), all metadata-only, spaced at 3.5s.

## 4. Step D — price coverage, then freeze

SPY checked first: same frozen-cache staleness already flagged in fix-6/
fix-7 (cached through 2026-05-08, corpus needs through later dates) — not
new, no verdict changes.

**84 of 87 pass A9.** Three drops:

| Ticker | Stratum | Finding |
|---|---|---|
| IPG | S3/media_telecom | **Anomaly, not a real gap.** Yahoo/yfinance returns "possibly delisted" for Interpublic Group — a large, continuously-traded NYSE company. Verified at the raw `query1.finance.yahoo.com/v8/finance/chart/IPG` level (not a yfinance bug): 404, "No data found, symbol may be delisted." A control ticker (JPM) succeeded on the same endpoint at the same time. **Recommend a retry next session** rather than treating this as permanent. |
| BK | S3/financials | Same anomaly as IPG — Bank of New York Mellon, same raw-API 404. Same recommendation. |
| MAXN | S2 primary | Same "possibly delisted" pattern from Yahoo; Maxeon Solar's public status was not independently re-verified against a second source this run — plausible this is the same provider anomaly as IPG/BK, or a genuine gap; not distinguished here. |

**CORPUS_MANIFEST_V5.json frozen** — every A1/A2/A9 verdict written into the
manifest entry itself for each of the 84 newly added companies (`rule_applied`,
`meets_new_rule`, `gradable_calls_under_A9`, `price_coverage_verdict_A9`),
not left in a side file — the standing practice this prompt required,
closing the exact gap corpus-fix-7 found in A8's own propagation.

### Counts and attrition

| Stage | S1 | S3 | S2 | S4 | Total |
|---|---|---|---|---|---|
| Candidates selected (Step B) | 25 | 50 | 15 (12+3 reserve) | 0 | 90 |
| Pass A1 (Step C) | 24 | 49 | 14 | — | 87 |
| Pass A9 (Step D) | 24 | 47 | 13 | — | **84** |

**Attrition: 6/90 = 6.7%**, well under the prompt's 15% planning estimate.
**Flagged as a diagnostic contradicting the prompt's expectation, in the
opposite direction it anticipated** — the prompt asked to flag attrition
running *far above* 15%; this run's attrition ran far *below* it. Net effect:
the corpus landed at 159 instead of the ~150 target — a small overshoot, not
a shortfall, but worth revising the planning assumption for any future
expansion round.

**Total: 159 companies (75 existing + 84 added), 156 gradable** (WOLF, NOVA,
SPWR carried forward ungradable from V4, per their existing carve-outs —
unchanged by this run).

## 5. Step E — split, lock, and the threshold

`analysis/corpus_construction_split_v5_expansion.py` — identical method to
v3/v4, same seed `20201231`. `SPLIT_V5_EXPANSION.json`: 108 train+tune, 51
holdout. **Available for iteration: 107** (108 minus WOLF's S4 carve-out
exclusion — same treatment A8/A9 established for ungradable carve-out
companies).

| | sha256 |
|---|---|
| V4 holdout (75 companies) | `1d05ee0496842e2dd033924ce82d387213b80f20c3e36582eabb66d33de87569` |
| **V5 holdout (159 companies, this run)** | `019eeee338e00b23d8a4c0c8e42bf032a595b374e8ebfbbf36228fe10f39a310` |

`docs/architecture/PROMOTION_GATE.md` §10 updated with the full chain of
supersession (78 → 77 → 75 → 159). Only spec edit this run makes.

**Threshold recheck** (`analysis/corpus_fix8_threshold_recheck.py`, same
imported method as every prior recheck): at n=107, **simulated paired MDE
is a flat 1pp in all three spread brackets** — observed, lower, and higher
alike. Square-root check: `24/√107 = 2.32pp` (published baseline),
`20/√107 = 1.93pp` (this project's recheck formula).

**A flat 1pp across brackets that otherwise always differ is itself a red
flag, not a good result.** At every prior count (46, 48, 54), the three
brackets produced distinct MDEs; at n=107 they collapse to identically 1,
which reads as the simulation hitting a floor artifact (X_SWEEP's coarsest
step, or a bootstrap resolution limit) rather than a genuine spread-
insensitive result. **Trust the square-root recheck (1.93pp) over the
simulated 1pp** — consistent with the standing guidance since fix-6/fix-7,
and reinforced here by the simulation's implausible flatness.

> The corpus is now **159 companies**, **107** available for iteration. The
> paired threshold is **1 point** simulated (flat, likely a simulation floor
> artifact — see above), **1.9–2.3 points** by the square-root check,
> against **3 points** before this run. Scoring it would cost roughly
> **$336**.

## 6. Scoring-cost estimate

3,618 total calls across the frozen V5 corpus
(`CORPUS_MANIFEST_V5.json` → sum of `n_calls_2020_2025`). Rate: **~$0.093
per call**, this project's own observed rate from
`wrap-ups/test7-ec-score-fidelity-out.md` (30 calls → $2.79 estimated;
6 calls → $0.55 — both at standard Sonnet-family rates, $3/M in, $15/M out).
3,618 × $0.093 ≈ **$336**. This is an extrapolation from a 30-36-call sample,
not a bulk-run measurement — stated as an estimate, not a quote.

---

## 7. Verification performed

- `python3 -c "import ast; ast.parse(...)"` on all five new drivers — passed.
- `json.load()` on every new/modified JSON file — valid.
- Cross-checked the window-filter bug independently: `UNH`'s raw (unfiltered)
  event history vs. windowed count, confirmed 31→24 after the fix.
- Verified IPG/BK's "delisted" result at the raw Yahoo chart-API level with
  a working control ticker (JPM) queried in the same window — ruled out a
  local/session-specific yfinance bug before accepting the finding.
- Re-grepped `analysis/data/price_cache.json` — no new entries (untouched).
- Confirmed `CORPUS_MANIFEST_V2/V3/V4.json` are untouched (`git diff --stat`
  empty for all three).

## 8. Deviations from the prompt

- No S1/S3 reserve lists were built before Step C, so SCHW/ED (and IPG/BK
  at Step D) are reported as shortfalls rather than replaced — the prompt's
  Step B asked for reserve lists "since drops are expected," and this run
  under-provisioned them. Flagged rather than silently under-delivering the
  quota.
- IPG/BK/MAXN's "possibly delisted" result was investigated one level
  deeper than a routine drop (raw API check, control ticker) because it
  contradicted general knowledge sharply enough to warrant it — consistent
  with "verify the premise" rather than a scope expansion.

## 9. What's left for the design session

- **IPG, BK, MAXN** — retry next session; likely a transient provider issue,
  not a real gap.
- **SCHW, ED** (S1/S3) — no reserve exists; decide whether to draft
  replacements or accept the corpus at 159 rather than the full 90-candidate
  yield.
- **S4 remains at 4 of 8** — no new candidate found again. The SPAC-era
  relaxed-rule candidates (§2) are the concrete option on the table.
- **The attrition-rate planning assumption** (15%) should probably be
  revised down for future rounds, based on two data points now (this run's
  6.7%, and corpus-fix-5/7's experience).
- **Commissioning a scoring run** is now a live option at ~$336 for the full
  corpus — not decided here.

## 10. Limitations (stated, not argued past)

- The corpus remains selected, not scored.
- The threshold is a simulation plus an arithmetic check, not a measurement
  — and this run found the simulation newly unreliable at large n (§5).
- Coverage is measured against providers reachable from this environment;
  IPG/BK/MAXN's failures may be provider-side, not real (§4).
- The existing 16 (S5) remain hindsight-selected and excluded from ruler
  headlines.
- The failures stratum (S4) is defined by an outcome and over-represents
  failures; it did not grow this round.

## 11. Git

1. `git_dirty: false` confirmed before any change.
2. `analysis/corpus_fix8_candidates.py` + `analysis/corpus_fix8_driver.py`
   committed first, together, before any result existed (`09ee64a`).
3. Two same-day driver fixes, each its own commit, before results:
   the window-filter bug (`3abdf9b`) and the vendor-call-cap raise
   (`fc5e2df`).
4. Step C identity-resolution results + alias additions (`ff03e5b`).
5. `analysis/corpus_construction_split_v5_expansion.py` (`115060d`) and
   `analysis/corpus_fix8_threshold_recheck.py` (`e439078`), both driver
   code, both before their own results.
6. Main results commit (`33592ca`): A10 addendum, coverage sweep, V5
   manifest, SPAC-era candidates, V5 split.
7. This wrap-up and the `PROMOTION_GATE.md` §10 update commit next; push
   follows once, to `origin sweep/db-corpus-baseline`.

Provenance for every figure above: `<value>` — `<path>` → `<json.key>`,
e.g. `107 available` — `analysis/data/corpus_v2/SPLIT_V5_EXPANSION.json` →
`counts.train`+`counts.tune` minus WOLF; `1.93pp sqrt recheck` —
`analysis/data/corpus_v2/STEP_C_AT_FIX8_CORRECTED_COUNT.json` →
`sqrt_estimates.this_run_recheck_20_over_sqrt_n`; `3,618 calls` —
`analysis/data/corpus_v2/CORPUS_MANIFEST_V5.json` (sum of
`strata.*.frozen[].n_calls_2020_2025`).

---

## 12. Same-day follow-up correction — §4/§9's IPG/BK/MAXN finding was wrong for two of three

**§4 and §9 above called IPG/BK/MAXN's Yahoo "possibly delisted" result a
likely transient provider anomaly and recommended a retry. On retry, that
was the wrong characterization for two of the three — corrected here,
explicitly, per this project's own rule that a corrected figure must
supersede the old one rather than quietly replace it.**

**BK — genuinely re-ticked, not delisted.** The Bank of New York Mellon
Corporation rebranded to "BNY" and changed its exchange ticker from BK to
BNY (2025). Yahoo has fully purged BK (confirmed via `finance.yahoo.com`'s
own search endpoint, which returns BNY as the only match for "Bank of New
York Mellon"), but **BNY has complete price coverage, 2020-01-02 through
today.** 24 of 24 calls gradable.

**MAXN — genuinely delisted to OTC Pink, same pattern as SUNW/SUNWQ.**
Maxeon Solar Technologies moved to the Pink Markets under **MAXNQ**.
**Full coverage, 2020-08-26 through today.** 14 of 14 calls gradable.

**IPG — the original "anomaly" call was wrong here too, but the underlying
drop was right, for a different and more concrete reason than stated.**
Yahoo has no IPG price data at **any** date, including 2020 (tested
directly with a historical date range, not just recent) — not a rate-limit
or symbol-lookup quirk. This is consistent with a **real, merger-driven
delisting**: Omnicom's acquisition of Interpublic Group — both companies
were independently drafted as candidates in this run's own
`media_telecom` sector cell (§2's roster), which is itself worth noting as
a near-miss the roster's general-knowledge sourcing didn't catch in
advance. IPG **stays dropped** — the correction is only to *why*.

**Corrected counts, superseding §4/§5/§6's figures:**

| | Before this correction | After |
|---|---|---|
| Total companies | 159 | **161** |
| Gradable | 156 | **158** |
| Available for iteration | 107 | **108** |
| Holdout sha256 | `019eeee...` (V5) | **`a281a7b4...` (V6)** |
| Paired threshold, simulated | 1pp (n=107) | 1pp (n=108, unchanged) |
| Paired threshold, sqrt recheck | 1.93pp | **1.92pp** (unchanged in practice) |

New files: `CORPUS_MANIFEST_V6.json`, `SPLIT_V6_BK_MAXN_FOLLOWUP.json`,
`STEP_C_AT_FIX8_FOLLOWUP_COUNT.json`. `TICKER_ALIASES.json` gained BK→BNY
and MAXN→MAXNQ entries. `PROMOTION_GATE.md` §10 updated again with the new
holdout hash and the full chain of supersession.

**The revised recommendation for the design session:** only **SCHW, ED, and
IPG** remain as unresolved drops with no reserve built this round (down
from five) — worth drafting replacements for these three specifically
before the next scoring commission, rather than the broader set §9
originally listed.

**Lesson, stated plainly:** the original "anomaly, recommend a retry"
finding was itself under-verified — a first Yahoo search-endpoint check
would have surfaced BNY and MAXNQ immediately, the same identity-resolution
work already applied successfully to VIAC/ANTM/SQ/NWSA in §3. Flagged here
rather than left standing.

---

## 13. Second same-day follow-up — reserve replacements for SCHW, ED, IPG

§12 narrowed the unresolved-drops list to three (SCHW, ED, IPG), all
dropped with no reserve built at selection time. This follow-up drafted
one replacement each, same method as the original roster (general
knowledge, cross-checked against the manifest for duplicates before any
vendor call, then mechanically tested against A1 and A9 — no outcome was
looked at before selecting any of the three):

| Replacement | Stratum | Replaces | n calls | Gradable | Verdict |
|---|---|---|---|---|---|
| **BLK** (BlackRock) | S1 | SCHW (A1 fail, gap 539d) | 24 | 24/24 | pass |
| **WEC** (WEC Energy Group) | S3/utilities | ED (A1 fail, gap 1,099d) | 24 | 24/24 | pass |
| **SIRI** (Sirius XM) | S3/media_telecom | IPG (A9 fail — merger delisting) | 20 | 20/20 | pass |

All three passed A1 and A9 cleanly on the first attempt.

**Corrected counts, superseding §12's:**

| | §12 | After this replacement |
|---|---|---|
| Total companies | 161 | **164** |
| Gradable | 158 | **161** |
| Available for iteration | 108 | **109** |
| Holdout sha256 | `a281a7b4...` (V6) | **`909f68cc...` (V7)** |
| Paired threshold, simulated | 1pp (n=108) | 1pp (n=109, unchanged) |
| Paired threshold, sqrt recheck | 1.92pp | **1.92pp** (unchanged) |

New files: `CORPUS_MANIFEST_V7.json`, `SPLIT_V7_RESERVE_REPLACEMENTS.json`,
`STEP_C_AT_FIX8_FOLLOWUP2_COUNT.json`. `PROMOTION_GATE.md` §10 updated
again with the new holdout hash.

**No unresolved drops with no reserve remain from this run's original
selection.** MSTR (S2, real A1 gap) needed no replacement, since the S2
primary list already met its target of 12 without it.

**The corpus is now 164 companies, 109 available for iteration, threshold
~1.9pp by the square-root check** — the number that should be used going
forward in place of every earlier figure in this document.
