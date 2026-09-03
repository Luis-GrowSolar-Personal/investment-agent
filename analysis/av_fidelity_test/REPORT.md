# Alpha Vantage Transcript Fidelity Benchmark — Report

`av_fidelity_1` — `analysis/av_fidelity_test/av_fidelity_1-manifest.json`

No overall recommendation is offered below, per the prompt's Step 7 instruction — this is data, not a verdict.

## AV call budget

**7 of 15** AV `EARNINGS_CALL_TRANSCRIPT` calls used. All 7 succeeded on the first attempt; no rate-limit errors, no retries. Spacing: 75s between calls (per the corrected prompt).

## Sample selection

AV coverage was pre-confirmed only for AMPX, EOSE, SPWR (not AAPL/TSLA/TTD; ENVX isn't a portfolio ticker in this DB — 0 rows). All 7 samples were drawn from those 3 confirmed-covered tickers, 2025 quarters only, to avoid spending budget on likely-empty lookups:

| Ticker | Quarter | Call Date | Transcript ID |
|---|---|---|---|
| AMPX | Q1 2025 | 2025-05-08 | 15 |
| AMPX | Q2 2025 | 2025-08-07 | 16 |
| AMPX | Q3 2025 | 2025-11-06 | 17 |
| EOSE | Q1 2025 | 2025-05-06 | 22 |
| EOSE | Q2 2025 | 2025-07-31 | 23 |
| SPWR | Q1 2025 | 2025-04-30 | 32 |
| SPWR | Q3 2025 | 2025-10-21 | 31 |

## Per-sample results

### AMPX Q1 2025 (id 15)

- Word count: DB=4900, AV=4948. SequenceMatcher ratio: **0.7071**
- Determinism check: **CLEAN**
- Field diff (DB vs AV), full evaluator run: **4/15 fields differ**

| Field | Status | DB | AV |
|---|---|---|---|
| thesisHealth | MATCH | Strengthening | Strengthening |
| thesisDelta | MATCH | unknown | unknown |
| recommendation | MATCH | Add | Add |
| recommendedSize | MATCH | 12 | 12 |
| freshMoneyAllocation | MATCH | 8 | 8 |
| **typeClassification** | **DIFFER** | B | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| **credibilityDelta** | **DIFFER** | positive | neutral |
| **activeDriverCount** | **DIFFER** | 4 | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| **capPercent** | **DIFFER** | 50 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| mitigationCapabilityTrackRecord | MATCH | strong | strong |

Note: `typeClassification` and `capPercent` differ together (B/50 vs A/35) — mechanically linked per DESIGN_PRINCIPLES.md §5, not two independent misses. `activeDriverCount` (Type B only) is consistent with that: 4 on the DB run, null on the AV run (since AV run classified Type A).

### AMPX Q2 2025 (id 16)

- Word count: DB=6890, AV=6589. SequenceMatcher ratio: **0.7801**
- Determinism check: **CLEAN**
- Field diff: **1/15 fields differ**

| Field | Status | DB | AV |
|---|---|---|---|
| thesisHealth | MATCH | Strengthening | Strengthening |
| thesisDelta | MATCH | unknown | unknown |
| recommendation | MATCH | Add | Add |
| **recommendedSize** | **DIFFER** | 22 | 18 |
| freshMoneyAllocation | MATCH | 12 | 12 |
| typeClassification | MATCH | A | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| credibilityDelta | MATCH | positive | positive |
| activeDriverCount | MATCH | null | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 35 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| mitigationCapabilityTrackRecord | MATCH | strong | strong |

None of the four flagged fields (credibilityDelta, mitigationArgumentPresent, mitigationCapabilityTrackRecord, blindSpotsTriggered) differ here.

### AMPX Q3 2025 (id 17)

- Word count: DB=8735, AV=2740. SequenceMatcher ratio: **0.3395**
- Determinism check: **FAILED** — Step 5 not run for this sample per the prompt's hard-stop rule.

| Field | Status | Run 1 | Run 2 |
|---|---|---|---|
| thesisHealth | MATCH | Strengthening | Strengthening |
| thesisDelta | MATCH | unknown | unknown |
| recommendation | MATCH | Add | Add |
| recommendedSize | MATCH | 18 | 18 |
| freshMoneyAllocation | MATCH | 12 | 12 |
| typeClassification | MATCH | B | B |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| credibilityDelta | MATCH | positive | positive |
| **activeDriverCount** | **DIFFER** | 5 | 4 |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 50 | 50 |
| mitigationArgumentPresent | MATCH | true | true |
| mitigationCapabilityTrackRecord | MATCH | strong | strong |

The AV word count here (2740) is far below the other samples relative to DB (8735) — the raw AV JSON for this quarter has only 15 speaker turns vs. 47–53 for the other AMPX quarters, i.e. AV appears to have truncated or abbreviated this specific transcript rather than just paraphrasing it. Diagnostic only, per the prompt — flagged here because it's visually anomalous.

### EOSE Q1 2025 (id 22)

- Word count: DB=8851, AV=8560. SequenceMatcher ratio: **0.6949**
- Determinism check: **FAILED** — Step 5 not run.

| Field | Status | Run 1 | Run 2 |
|---|---|---|---|
| thesisHealth | MATCH | Intact | Intact |
| thesisDelta | MATCH | unknown | unknown |
| **recommendation** | **DIFFER** | Hold | Add |
| recommendedSize | MATCH | 18 | 18 |
| **freshMoneyAllocation** | **DIFFER** | 8 | 10 |
| typeClassification | MATCH | A | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| credibilityDelta | MATCH | neutral | neutral |
| activeDriverCount | MATCH | null | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 35 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| **mitigationCapabilityTrackRecord** | **DIFFER** | strong | mixed |

This determinism failure involves `recommendation` itself flipping (Hold vs Add) on two identical-input, temperature=0 runs of the **same DB transcript**. One of the two flagged fields also differs (mitigationCapabilityTrackRecord: strong vs mixed).

### EOSE Q2 2025 (id 23)

- Word count: DB=9053, AV=5744. SequenceMatcher ratio: **0.1142**
- Determinism check: **FAILED** — Step 5 not run.

| Field | Status | Run 1 | Run 2 |
|---|---|---|---|
| thesisHealth | MATCH | Intact | Intact |
| **thesisDelta** | **DIFFER** | unknown | up |
| recommendation | MATCH | Add | Add |
| recommendedSize | MATCH | 8 | 8 |
| **freshMoneyAllocation** | **DIFFER** | 5 | 4 |
| typeClassification | MATCH | A | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| credibilityDelta | MATCH | neutral | neutral |
| activeDriverCount | MATCH | null | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 35 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| mitigationCapabilityTrackRecord | MATCH | strong | strong |

The 0.1142 similarity ratio here is the lowest of the 7 samples, notably lower than the other EOSE quarter (0.6949) — a diagnostic anomaly, not evaluated for cause.

### SPWR Q1 2025 (id 32)

- Word count: DB=11517, AV=4625. SequenceMatcher ratio: **0.1768**
- Determinism check: **CLEAN**
- Field diff: **4/15 fields differ**

| Field | Status | DB | AV |
|---|---|---|---|
| **thesisHealth** | **DIFFER** | Strengthening | Intact |
| thesisDelta | MATCH | unknown | unknown |
| **recommendation** | **DIFFER** | Add | Hold |
| recommendedSize | MATCH | 12 | 12 |
| freshMoneyAllocation | MATCH | 7 | 7 |
| typeClassification | MATCH | A | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| **credibilityDelta** | **DIFFER** | positive | neutral |
| activeDriverCount | MATCH | null | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 35 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| **mitigationCapabilityTrackRecord** | **DIFFER** | mixed | unproven |

This is the sample with the largest DB/AV word-count gap of the three that reached Step 5 (11517 vs 4625, ratio 0.1768), and it is also the sample with the most field disagreement, including the recommendation action itself (Add vs Hold) and two of the four flagged fields (credibilityDelta, mitigationCapabilityTrackRecord).

### SPWR Q3 2025 (id 31)

- Word count: DB=10839, AV=5472. SequenceMatcher ratio: **0.1717**
- Determinism check: **FAILED** — Step 5 not run.

| Field | Status | Run 1 | Run 2 |
|---|---|---|---|
| thesisHealth | MATCH | Strengthening | Strengthening |
| thesisDelta | MATCH | unknown | unknown |
| recommendation | MATCH | Add | Add |
| recommendedSize | MATCH | 18 | 18 |
| **freshMoneyAllocation** | **DIFFER** | 8 | 10 |
| typeClassification | MATCH | A | A |
| stumbleType | MATCH | None | None |
| threatMechanismImpaired | MATCH | false | false |
| credibilityDelta | MATCH | positive | positive |
| activeDriverCount | MATCH | null | null |
| ratchetTranche | MATCH | null | null |
| blindSpotsTriggered | MATCH | [] | [] |
| capPercent | MATCH | 35 | 35 |
| mitigationArgumentPresent | MATCH | true | true |
| mitigationCapabilityTrackRecord | MATCH | strong | strong |

## Summary counts

- Samples with a clean determinism check: **3 of 7** (AMPX Q1, AMPX Q2, SPWR Q1)
- Samples where determinism failed, Step 5 skipped per the prompt's hard-stop rule: **4 of 7** (AMPX Q3, EOSE Q1, EOSE Q2, SPWR Q3)
- Across the 3 completed DB-vs-AV comparisons: **9 field differences total** out of 45 field-checks (3 samples × 15 fields)
  - AMPX Q1: 4 differ
  - AMPX Q2: 1 differ
  - SPWR Q1: 4 differ
- Of those 9 differences, **3 are in the four flagged fields** (credibilityDelta, mitigationArgumentPresent, mitigationCapabilityTrackRecord, blindSpotsTriggered):
  - credibilityDelta: differs in AMPX Q1, SPWR Q1 (2 of 3 comparisons)
  - mitigationCapabilityTrackRecord: differs in SPWR Q1 (1 of 3 comparisons)
  - mitigationArgumentPresent: 0 differences across all 3 comparisons
  - blindSpotsTriggered: 0 differences across all 3 comparisons (all samples scored `[]` on both DB and AV in every comparison)
- Separately, across the 4 determinism-check runs on the **same DB transcript**, run-to-run: **8 field differences total** out of 60 field-checks (4 samples × 15 fields), including one flip of `recommendation` itself (EOSE Q1: Hold vs Add) and one flip of `thesisDelta` (EOSE Q2: unknown vs up).

## Flagged premises / deviations

1. **Prompt-version mismatch, found while reading required docs before implementing.** `server/lib/versions.js` states `PROMPT_VERSION = 'v6'` as the string stamped on production Analysis rows, with a comment that this constant is "the source of truth" and should be updated whenever `docs/EVALUATION_PROMPT.md` changes materially. The file at `docs/EVALUATION_PROMPT.md` itself, however, currently contains **v10+auto1** text — a candidate whose own changelog header says "Gate status: not yet run" (i.e. the v10 promotion gate has not been run/passed). There is no v6 text preserved anywhere in the file. This means the literal file the benchmark prompt names (`EVALUATION_PROMPT.md`) is the v10+auto1 candidate, not the v6 text `versions.js` claims is live. Per "Do not modify EVALUATION_PROMPT.md," this run used the file exactly as found — v10+auto1 — which is what the benchmark prompt explicitly names. But this means: (a) this benchmark's results describe v10+auto1's fidelity behavior, not v6's; (b) separately from this benchmark, production's `evaluate.js` route loads `docs/EVALUATION_PROMPT.md` from disk at module load and would today be serving v10+auto1 to real evaluations while `versions.js` stamps those rows `promptVersion: "v6"` — a mislabeling this session did not create but did surface. Flagging for the design session; not something a CLI run should resolve.
2. **AV coverage assumption narrowed the sample.** The prompt's context section states AV coverage was confirmed for AMPX, EOSE, SPWR, ENVX. ENVX is not a portfolio ticker in this DB (0 rows for that symbol among AAPL/AMPX/EOSE/SPWR/TSLA/TTD), and AAPL/TSLA/TTD were never confirmed. All 7 samples were drawn from the 3 confirmed tickers to avoid spending AV budget probing unconfirmed ones — this is a scope narrowing from "at least 3 different tickers" (satisfied, 3 used) but excludes AAPL/TSLA/TTD entirely rather than sampling across all 6 portfolio tickers as Step 1 describes. Deliberate call given the 15-call budget cap; flagging as a deviation.
3. **AV rate-limit spacing was corrected before running**, per your explicit instruction mid-session — the prompt file originally said 15s/5-req-min; it was updated to 70-75s/no-auto-retry before Step 2 ran (see commit `f9e2b02`, driver commit). All 7 calls succeeded on the corrected spacing with no rate-limit errors.
4. **My first fetch-loop's rate-limit detection was buggy** (grepped for the substring "Note" anywhere in the raw response, which false-matched on "please **note** that this presentation..." inside a legitimate transcript) and caused an unnecessary stop after call 1. Caught immediately, fixed to check AV's actual top-level JSON error keys (`Note`/`Information`/`Error Message`) before continuing. No AV call was wasted by this — the call that triggered the false stop was itself a valid, successful response and is included in the sample (AMPX Q3 2025).
5. **Not done / left for the design session:** no interpretation of *why* AV word counts are so much lower than DB for EOSE and SPWR specifically (all three SPWR/EOSE-Q2 ratios are ≤0.18, while both AMPX comparisons that reached Step 5 are ≥0.70) — this looks like more than paraphrasing-level smoothing for those tickers and may be a truncation or transcript-completeness issue on AV's side rather than pure rewriting, but this run did not diff the transcripts qualitatively to confirm which. Also left open: whether the underlying determinism instability (4/7 failures here) is materially worse than the 21.4%–69.0% instability rates already logged in `EVALUATION_PROMPT.md`'s own v9/v10 iteration notes, since those were measured on a different corpus (ENPH, 21 transcripts) under v9, not v10+auto1 on this 7-sample AMPX/EOSE/SPWR set.

## Reproducibility

Manifest: `analysis/av_fidelity_test/av_fidelity_1-manifest.json`. Driver committed at `f9e2b02552ddcb9c6d6d7b37f5aaba889878c8d2` (its own commit, before this report/manifest commit). Git tree was clean before the run. Raw AV responses: `analysis/av_fidelity_test/raw/*.json`. Full evaluator outputs: `analysis/av_fidelity_test/scored/*.json`. Structured results: `analysis/av_fidelity_test/results.json`.

## Follow-up commands

Re-run the full driver (uses saved raw AV JSON, makes no new AV calls, does make Anthropic API calls):

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 analysis/av_fidelity_test/driver.py
```

Inspect a specific full evaluator output (narrative + structured block):

```bash
cat analysis/av_fidelity_test/scored/SPWR_2025Q1_db.json
cat analysis/av_fidelity_test/scored/SPWR_2025Q1_av.json
```
