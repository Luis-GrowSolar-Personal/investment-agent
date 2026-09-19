# P3a guidance ledger — Phase 1 checkpoint (stopped at the §5e gate)

**Run:** `p3-guidance-ledger` · **Branch:** `sweep/db-corpus-baseline` · **Prompt:** `prompts/P3-guidance-ledger.md`
**Status: PARTIAL RUN, by the prompt's own rule.** Pass A (extraction) and the free diagnostics are done. **The pre-flight and Pass B were not run.** The `N_eligible` gate fired: **93, against a floor of 150.** Luis approved Phase 1 only (cap $65). No Phase 2 go exists.

## Lead-with summary

- **Gate result.** `N_eligible` = **93** (floor 150) → stop before the pre-flight. It is 93 on the ledger I can defend. It was 375, then 205, on earlier builds I later found were wrong (§4). All four figures are in the sensitivity table.
- **Pass A succeeded mechanically.** 1,240 of 1,240 transcripts extracted, all finished normally. **Spend $46.15**, which is **$1.15 over** the $45 Pass A cap (§6).
- **The ledger is thinner than the prompt assumed.** Only **417 of 1,184** calls with a predecessor (**35.2%**) have at least one gradable promise. Pass A's standalone success bar was 90%. **It is not met.** The full-corpus drop rate is **5.63%**, against a bar of under 5%. **That is not met either**, though it is mostly not invention (§2).
- **The free diagnostic gives no strong signal for the mechanism** (§5). Calls with a miss went on to underperform the S&P by more than 5 points **47.4%** of the time, against 46.6% for all calls. The range is 38 to 57.
- **Nothing was promoted, tuned or decided.** No DB writes, no cache refresh, no holdout or tune contact.

---

## §0 Defined terms

Plain words first. Identifiers come after.

- **Promise.** A number or range management gave for a future period ("revenue of $8.1 to $8.3 billion next quarter").
- **Ledger.** For one call, the list of promises made on the *previous* call, each set beside what this call reported.
- **The six grades.** `met` = actual inside the promised range. `missed` = below it. `beat` = above it. `unreported` = promised, and the metric is not in this call at all. `withdrawn` = management explicitly retracted the promise. `basis_mismatch` = promise and actual are on different footings (GAAP vs adjusted, or growth vs level with no year-ago figure to convert). A seventh label, `ungradable_present`, is mine, not the prompt's. It marks a promise whose metric *is* in the transcript but was not captured by the extractor. Those rows are counted and excluded, never shown to the analyst.
- **Bearish / bullish / neutral call.** The analyst's own recommendation: Trim or Exit / Add / Hold.
- **Base rate.** How often something happened across *all* calls, whatever the analyst said. Bearish outcome (stock lagged the S&P by more than 5 points over about two quarters): 46.6%. Bullish outcome: 32.8%.
- **Coverage.** Share of calls that have a usable ledger. Not the same as the analyst's bearish coverage in the state of play.
- **Flip.** The candidate answers differently from v6 on the same call. **Noise flip:** a change that a plain re-run of v6 would also produce. Not measured in this run, because the pre-flight did not happen.
- **Stratum vs tier.** *Stratum* (S1–S5) is how the corpus was built (S1 large cap, S2 in-scope mixed cap, S3 other, S4 failures, S5 the ALL16 names). *Tier* (established / speculative) is a separate classifier. This run used stratum only.
- **Fidelity drop.** An extracted entry thrown away because its quote is not word-for-word in the transcript (*quote miss*), or because its number does not match the string it claims to come from (*mis-parse*).

---

## 1. What was done

| step | result |
|---|---|
| 0a hygiene | tree clean, `git_dirty=false` at start |
| 0c pre-registration | P3a and P3b added to `PROMPT_ARCHITECTURE.md` §2.2 before any spend |
| 0d candidate | `docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`, sha256 `d7a32308…5938`, registered as a candidate (parent v6) |
| 0d-bis extraction prompt | `EXTRACTION_PROMPT_P3A.md`, sha256 recorded in `SCORING_PROTOCOL_P3A.json` and `progress.json` |
| 0e protocol | `analysis/data/corpus_v2/SCORING_PROTOCOL_P3A.json` |
| 0f aliases | asserts pass: **1,240** files, **56** companies, **1,240** eval files all mapped, **1,184** predecessor-bearing. Unresolved it would have been 1,194 (46 calls lost). `MAXN` → `MAXNQ` has no files, as expected |
| Pass A | 1,240 / 1,240 succeeded; batch `msgbatch_01XSxnDnsUYifm1r4A1Pr357` |
| ledger build, 5c–5e | done, $0 |
| **5e gate** | **fired. Pre-flight and Pass B not run** |

**Resume status.** First run, nothing reused. State is in `analysis/data/run_state/p3-guidance-ledger/`. `phase2_go` is `false`.

## 2. Fidelity — the number that says how far the ledger can be trusted

Every entry the extractor returned was checked mechanically against the transcript (quote word-for-word; each as-written string inside the quote; parsed value agrees with its string).

| | entries | share |
|---|---|---|
| extracted | 15,081 | |
| kept | 14,232 | 94.4% |
| quote miss | 359 | 2.38% |
| mis-parse | 490 | 3.25% |
| **combined drop rate** | **849** | **5.63%** |

Source: `extractions_fidelity.json` → `totals`, `drop_rate`. One response was unparseable JSON (`TEAM_2023-02-02`); 3 were legitimately empty.

**What the drops are.** This is the vendor-formatting clustering the prompt told me to report, not tune away. Dropped entries by cause:

| cause | entries |
|---|---|
| "plus or minus" guide: extractor invented endpoints the transcript never states (e.g. "$3.7 billion, plus or minus $200 million") | 215 |
| vendor transcript lost the decimal point ("683 to 709 per share" for $6.83 to $7.09) | 105 |
| other unit or scale error (e.g. "$610 billion" for $610 million; a 5.5% growth figure recorded as $5.5 billion) — genuine extractor errors, correctly dropped | 170 |
| as-written string not inside the quote | 176 |
| quote not word-for-word | 140 |
| no quote given | 43 |

Two consequences. First, drops **cluster by company**: DIOD 28.7%, MU 26.8%, JKS 19.3%, DUK 18.2% at the top; BMY, PSX, QS, MSFT, INTC under 1%. Companies that phrase guidance as "±" lose guidance systematically. Second, the checker does not test whether a kept entry is *right*. It only tests that it is present in the text. Two wrong-but-present errors showed up by eye (§7).

**Validation history.** Four validation rounds on the same 20 calls, real spend $5.06 in total: 10.9% → 3.2% → 3.5% → **4.4%**. Each fix and its cause is in `findings.md`. Round 4 cleared the 5% stop. The full corpus then came in at 5.63%.

## 3. The ledger, as built

Source: `analysis/data/run_state/p3-guidance-ledger/diag_output.txt`, `analysis/data/corpus_v2/ledger_summary.csv`. Population: 1,184 predecessor-bearing train calls (WOLF and SPWR excluded entirely; neither is in train).

| | |
|---|---|
| calls with ≥1 gradable promise (**coverage**) | **417 of 1,184 = 35.2%** |
| promises per non-empty call | median 2, range 1–8 |
| gap-marked calls (prior call not exactly one quarter earlier, by the vendor's year/quarter labels) | 18 (the prompt measured 7 of 1,184 pairs; **premise differs**, cause not investigated) |
| framing conversions performed (growth ↔ level, prior-year base in the ledger) | 51 |
| framing mismatches left unconverted | 99 |
| `other`-metric promises excluded as ungradable by construction | 638 |
| promises excluded by the label check | 517 |

Grade shares of all rows built (n = 1,140 rows, of which 242 are the excluded `ungradable_present`):

| grade | rows | share of 1,140 |
|---|---|---|
| beat | 442 | 38.8% |
| met | 182 | 16.0% |
| missed | 144 | 12.6% |
| basis_mismatch | 114 | 10.0% |
| unreported | 14 | 1.2% |
| withdrawn | 2 | 0.2% |
| ungradable_present (excluded, not one of the six) | 242 | — |

Grade by year of the call (rows):

| year | beat | met | missed | unreported | withdrawn | basis_mismatch | ungradable_present |
|---|---|---|---|---|---|---|---|
| 2020 | 39 | 12 | 1 | 0 | 2 | 9 | 13 |
| 2021 | 74 | 17 | 10 | 3 | 0 | 18 | 38 |
| 2022 | 87 | 33 | 20 | 4 | 0 | 22 | 38 |
| 2023 | 77 | 45 | 36 | 3 | 0 | 17 | 53 |
| 2024 | 73 | 37 | 33 | 3 | 0 | 23 | 58 |
| 2025 | 92 | 38 | 44 | 1 | 0 | 25 | 42 |

**`withdrawn` is 2 rows, all of them in 2020.** The prompt's 2020-COVID confound argument stands, but this ledger has almost no material to test it on. `unreported` collapsed to 14 rows after the fixes in §4. It was 479 on the first build, nearly all of it a join defect.

## 4. Where the ledger was wrong, and what I did about it

I rebuilt the ledger **three times after looking at diagnostics**. Each rebuild fixed a defect I could show, but the sequence matters, because the gate quantity moved with it. All four values are recorded (`gate_sensitivity.json`).

| build | coverage | `N_eligible` | `N_eligible_bull` | `N_reassure` |
|---|---|---|---|---|
| A. naive: `other` promises graded, no label check | 52.4% | 375 | 99 | 9 |
| B. `other` graded, label check on | 48.4% | 314 | 94 | 10 |
| C. `other` excluded, no label check | 42.3% | 205 | 126 | 11 |
| **D. `other` excluded, label check on (final)** | **35.2%** | **93** | **122** | **11** |

1. **`other` promises (A → C).** 311 of the first build's 479 `unreported` rows were guides for niche metrics (net interest expense, O&M, FFO-to-debt targets). My extraction prompt capped `reported` at 10 headline items and told the extractor to skip `other` there, so those promises had no counterpart to join. Grading them `unreported` would have manufactured broken promises: exactly the reflexive-trim source the prompt warned about. **This is a design flaw in my extraction split, not the analyst's signal.**
2. **Label check (C → D).** The extractor files some promises under the wrong normalized metric: a five-year capital plan as `capex`, a 5–7% long-term growth target as `eps`, an insurance combined ratio as `gross_margin_pct`, R&D spend as `operating_income`. Each would grade `unreported`. The check requires the promise's own quote to name its metric. **Sampled by eye, roughly 70% of the 517 exclusions were true mislabels; about 30% were legitimate promises my synonym list missed** (e.g. "operating gain", "cash on hand"). That sample was 33 rows, eyeballed, not measured.
3. **Framing conversions** were added (growth ↔ level when the prior-year base is itself in the extractions): 51 performed.

**My judgment, stated plainly.** D is the build I can defend on correctness. It moves the gate *away* from passing, and the prompt says a correct fix that does that is still the correct fix. I did not loosen the synonym list to recover the missed 30%, because I would be doing it with the gate in view. That is a call for the design session, not for me.

## 5. The free diagnostics (5d) — reported, not gated

Population: predecessor-bearing train calls with a graded outcome. Ranges are 95%, ticker-block bootstrap (resampling whole companies, seed 11).

| question | calls | outcome share | range | reference |
|---|---|---|---|---|
| **5d-i.** ≥1 `missed`/`unreported`/`withdrawn` → lagged S&P by >5 points | 114 | **47.4%** | 39.7 – 56.7 | 46.6% base |
| …excluding 2020 | 111 | 46.8% | 38.7 – 56.1 | 46.6% |
| …2020 only | 3 | 66.7% | 0 – 100 | uninformative |
| **5d-ii.** clean beats, no miss → beat S&P by >5 points | 224 | **30.4%** | 25.5 – 34.8 | 32.8% base |
| …excluding 2020 | 201 | 29.4% | 23.6 – 35.0 | 32.8% |
| …2020 only | 23 | 39.1% | 16.0 – 65.0 | wide |

Neither is distinguishable from its base rate. **Both are a smaller, cleaner population than the first build showed.** The first build's 5d-i, at n = 235 and 50.6%, was inflated by the `other` defect. It is superseded. It was never written to a committed file.

Reported, never gated (§5e): **`N_eligible_bull` = 122, `N_reassure` = 11**, no-miss ledger-bearing v6-not-bearish pool = 291.

## 6. Cost

| item | USD |
|---|---|
| validation rounds 1–4 (sync, 20 calls each; round 1 stopped at 16) | 5.06 |
| Pass A batch (1,240 requests, batch rate from usage figures) | 41.09 |
| **Pass A total** | **46.15** |
| pre-flight | 0 (not run) |
| **Phase 1 total** | **46.15** of a $65 cap |

**Cap overrun, flagged.** Pass A was capped at $45. I projected $36.80 for the batch from round 4's sync cost, which put the total at $41.9 including validation. Measured batch cost was $41.09. The validation sample's calls were shorter than the full set. The overrun is $1.15 and was found after the batch ended; money commits at `create()`. Costs are computed from usage figures at published Sonnet 4.6 rates, not read from a bill.

## 7. Deviations from the prompt, and premises that were wrong

1. **v6 has no "STUMBLE CLASSIFICATION test 1".** That section is four bulleted classes; the numbered three-part test is in MITIGATION ARGUMENT. I attached the ledger paragraph to the end of STUMBLE CLASSIFICATION and reworded its first sentence to "did they give guidance and miss it, on something they had data to forecast?". It cites the "MITIGATION ARGUMENT TEST". Otherwise verbatim. The diff is `diff docs/EVALUATION_PROMPT.md docs/prompts/candidates/EVALUATION_PROMPT_v6+P3a.md`.
2. **`version_guard` does not check a candidate's hash.** It checks only that the candidate *name* is registered. The prompt says the candidate arm is "guarded against the candidate hash". My driver asserts the candidate sha256 against the registry itself, and the 21a arm against the promoted v6 hash. Not exercised, because no pre-flight ran.
3. **The "two with no numeric guidance" eyeball picks were wrong.** I selected them by keyword count. EOSE and TEAM both contain real numeric guidance. Only FRC 2023-04-24 was a true empty-guidance case, and the extractor handled it correctly (no guided entries, one retraction captured).
4. **The eyeball set was drawn by stratum, not tier,** because tier is a separate classifier and I did not label by it. The prompt's "established / speculative / pre-revenue" mix is approximated by S1 / S2 / S3 / S5 / S4.
5. **Batch machinery was written locally,** not imported. `baseline_v6_tune_batch_driver.py`'s functions are hard-bound to the tune split's state directory and eval cache. The request shape is copied from it.
6. **Grading is against the original promise.** `grade_vs_latest` is recorded on each row. The prompt does not say which to grade against; I chose the one that does not let a lowered bar hide a miss.
7. **Derived lines are not built.** The ledger text says "none computed". The extraction has no gross-profit metric, and the EPS-vs-operating-income gap needs year-ago bases that are rarely present.
8. **Extraction errors that pass the fidelity check exist.** Examples caught by eye: a cumulative "$2 billion in revenue" milestone extracted as FY revenue (fixed in prompt round 3); ABBV's 2020 revenue promise was for standalone AbbVie while the actual includes Allergan, so it grades a 28% "beat" that is a perimeter change, not a beat. The join cannot see perimeter changes. **Analyst-facing rows carry errors the checker cannot detect.** This would have contaminated Pass B.
9. **Order of commits.** The pre-registration and candidate files were committed before the driver's first commit. The driver produced no output before its commit.

## 8. Not done, and left for the design session

Not done: the pre-flight (four arms, ~376 calls, ≤$20); Pass B (≤$70); diagnostics 8.1–8.10; the Q2 re-run; the noise-floor measurement (21a) and instruction-effect arm (21b). **The gate stopped the run before the run's other main deliverable, a measured noise floor for this model on this corpus.** That gap is real and unrecovered.

Decisions for the design session. I have not made them:

1. **Is D the right ledger?** The naive build cleared the gate and the defensible one does not. Whether to recover the ~30% of label-check exclusions that are legitimate, and by what rule, is a design call. It should be made before anyone looks at pre-flight results.
2. **Does the pre-flight run anyway on 93?** The prompt says stop. It does not say what happens next, and 93 eligible calls cannot clear the ~100-flip floor even with every one converting.
3. **Is a re-extraction worth its cost?** The binding constraint on coverage is the 10-entry cap on `reported`, which was a cost decision. A targeted second pass that extracts *only* the reported figure for each guided metric would recover much of the 242 `ungradable_present` rows and the `other` promises. I have not costed it; it is the same order of magnitude as Pass A.
4. The "±" guidance loss (215 entries) is systematic by company. A schema that carries centre ± width would recover it.

## 9. Verification performed

- Alias, count and eval-map assertions at runtime (`step0f_alias_asserts.json`): pass.
- Extraction prompt and candidate hashed; candidate matches registry (asserted in the pre-flight builder; not exercised).
- Grade logic unit-tested on a synthetic five-metric, four-call company: met, missed, beat, withdrawn, gap, FY pending, revised-down all behaved as specified.
- Ledger text eyeballed for two real calls; two defects found (§4, §7 item 8).
- `ast.parse` on the driver after every edit; the driver is `analysis/p3_guidance_ledger_driver.py`.
- Not verified: extraction correctness beyond the mechanical check and 20 calls by eye.

## 10. Follow-up commands

```
# where everything is
cat analysis/data/run_state/p3-guidance-ledger/progress.json
cat analysis/data/run_state/p3-guidance-ledger/findings.md
cat analysis/data/run_state/p3-guidance-ledger/gate_sensitivity.json

# rerun the free diagnostics (no spend)
python3 analysis/p3_guidance_ledger_driver.py build-ledger
python3 analysis/p3_guidance_ledger_driver.py diag

# ONLY after an explicit decision to proceed despite the gate:
python3 analysis/p3_guidance_ledger_driver.py preflight-select
python3 analysis/p3_guidance_ledger_driver.py preflight-submit   # spends up to $20
```

Provenance: fidelity `analysis/data/run_state/p3-guidance-ledger/extractions_fidelity.json`; ledger `analysis/data/corpus_v2/ledger/<TICKER>/<date>.json`; gate `diag_5cde.json` → `N_eligible`; outcomes `analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv` (train rows, `ground_truth`); base rates 46.6% and 32.8% from the prompt §9, same file. Price cache path for any later scoring: `analysis/data/corpus_v2/scorer_price_cache_v1.json`.
