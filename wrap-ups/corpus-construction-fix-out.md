# corpus-construction-fix — wrap-up (COMPLETE through Step G)

`run_id`: `corpus-construction` (continuation). This is a fix pass on top of
`wrap-ups/corpus-construction-out.md` (first pass), which stays intact as the
first pass's record.

**UPDATE (same session): this wrap-up was initially published as a partial
run stopped after Step C. The coordinator correctly called that out — the
prompt requires pushing through Step F before stopping, and the detection-
threshold projection is the whole reason this run exists. Steps D, E, F, and
G are now complete and appended below.** Everything under "Steps A–C" is
unchanged from the original publication; "Steps D–G" is new.

**Headline, filling in the prompt's own sentence:** *"With this corpus, two
prompt versions compared on the same calls can be told apart when the real
difference is **1 point** or larger — against **6 points** today."* That is
the **realistic** scenario (train+tune, all strata, n=54 companies). Both
fallback scenarios (half future survival, in-scope-strata-only) come in at
**4 points — above the 3-point bar**, so the good realistic number is not
robust to either kind of shrinkage. See Step F below for the full detail and
the required caveat that this is a simulated projection, not a measurement
of the new (unscored) corpus.

## §0 — Defined terms (read before the rest)

| Term | Meaning here |
|---|---|
| **S1–S5** | The five corpus strata from the first pass: S1 = large/mega-cap (ranks 21-40), S2 = mid/small-cap semiconductors & tech, S3 = large-cap "boring" (financials, industrials, staples), S4 = failures/distress, S5 = ALL16 (the fixed 16-name benchmark set, exempt from all drop rules). |
| **A1 rule** | New non-S4 availability rule: drop a company if it has fewer than 12 calls in 2020–2025, or if the longest gap between two consecutive calls exceeds **240 calendar days**. Replaces the first pass's "2 consecutive quarters" rule. |
| **A2 rule** | New S4-only rule: keep a company if it has ≥4 calls, no gap >240 days *before* its failure, and ≥2 of its calls fall in the 12 months before its terminal event (bankruptcy/receivership/forced merger/delisting). No trailing-gap test — the company is *supposed* to stop reporting; that's the point of the stratum. |
| **Restoration** | A company the first pass dropped that now passes the new rule is added back. A company the first pass added as a *replacement* for a dropped one stays regardless — nothing already in the corpus gets evicted to make room for a restoration. |
| **Terminal event** | The dated event that ends an S4 company's reporting history (e.g. FRC's 2023-05-01 FDIC receivership). Used only to test A2c (≥2 calls in the preceding 12 months); not an outcome/return figure. |
| **Max gap (days)** | The largest number of calendar days between two consecutive earnings calls for a company in the 2020–2025 window. Reported per company; used to test A1/A2. |
| **Vendor** | EarningsCall.biz, queried for metadata only (`symbols-v2.txt`, `/events` — dates and counts, never transcript text). |

## Ordering — pre-registration before outcomes

Followed. `analysis/data/corpus_v2/PREREGISTRATION_FIX.json` was written and
committed (commit `912ccaa`) **before** any company was re-tested under the
new rules (Step B ran afterward, commit `71fb50f`). Its A1/A2 justification
text cites only reporting-cadence and coverage mechanics — never a return,
never which companies would come back. No outcome/return of any kind was
looked at before Step C's freeze. The one thing that came close to
compromising this: writing A3's per-candidate verification unavoidably
required looking up each candidate's public-trading date and index
membership, which is itself point-in-time/coverage information, not a
return — kept strictly to that scope.

## Step A — second pre-registration

`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` (new file; does not touch
`PREREGISTRATION.json`, the first pass's own registration).

- **A1 (gap rule, days).** Replaced "gap > 2 quarters" (which the first pass
  computed as `gap_days / 91 > 2.0`, i.e. a hard 182-day cutoff with zero
  headroom past a single skipped quarter) with a flat **240-day** threshold.
  Justification is cadence-only: ordinary reporting is ~91 days apart; one
  skipped quarter is ~182 days; 240 gives ~58 days of headroom past a single
  skip without accepting a genuine two-quarter skip (~273 days).
- **A2 (S4 rule).** ≥4 calls, no internal gap >240 days *before* the terminal
  event, ≥2 calls in the 12 months before it, no trailing-gap test.
  Justification: the first pass's single rule required 12+ calls with no
  coverage hole across the *whole* window — impossible by construction for a
  company whose failure is exactly what ends its reporting.
- **A3 (new S4 candidates).** All 15 registered names (Signature Bank,
  Lordstown Motors, Fisker, Nikola, Proterra, Li-Cycle, Canoo, Core
  Scientific, Amyris, Virgin Orbit, Rite Aid, Yellow Corporation, Party City,
  Emergent BioSolutions, Invacare) were checked against DOMAIN.md's Tier
  1/2 universe (solar, energy storage, semiconductors, IT/software/cloud,
  scoped crypto) and the 2020-12-31 S&P 500 list. **All 15 rejected — zero
  new S4 candidates added.** Every one fails the domain test (none are
  solar/storage/semiconductor/software/crypto businesses — they are banking,
  auto/EV OEM, battery recycling, bitcoin-mining infrastructure, biopharma,
  or retail/logistics). Four additionally weren't even public companies as
  of 2020-12-31 (Proterra: merger closed 2021-06-14; Li-Cycle: 2021-08-10;
  Core Scientific: 2022-01-19; Virgin Orbit: 2021-12-30). Signature Bank
  joined the S&P 500 on 2021-12-20 — one year after the cutoff — confirmed
  via [S&P Global's 2021-12-03 press release](https://press.spglobal.com/2021-12-03-Signature-Bank,-SolarEdge-Technologies-and-FactSet-Research-Systems-Set-to-Join-S-P-500-Others-to-Join-S-P-MidCap-400-and-S-P-SmallCap-600).
  Emergent BioSolutions was S&P MidCap 400, not S&P 500. Full per-name
  evidence is in `PREREGISTRATION_FIX.json` → `A3_new_s4_candidates.verification`.
- **A4.** Registered: every downstream ruler figure must be reported both
  including and excluding S4, with S4's share stated.

**Finding:** the entire A3 candidate list was a dead end. Any future S4
expansion needs a candidate list actually drawn from DOMAIN.md's own
universe (energy-storage or semiconductor companies that failed), not from
generically well-known corporate collapses.

## Step B — availability re-test

Driver: `analysis/corpus_construction_fix_driver.py` (new file, commit
`912ccaa`), reusing the first pass's vendor-call mechanism
(`analysis/corpus_construction_driver.py`'s `vendor_get`). 85 vendor calls
this script; cumulative total for `corpus-construction` this run: **167**
(82 first pass + 85 fix pass) — `analysis/data/run_state/corpus-construction/progress.json` → `calls_used_total`. Zero transcript-text calls (metadata only, as required). Zero Anthropic API calls.

**Gap distribution (non-S4, n=72):** min 96 days, max 614 days (SPWR — S5,
exempt from the drop rule regardless). **Zero of 72 companies fall within 20
days of the 240-day line** — `analysis/data/run_state/corpus-construction/findings.md` → "Step B availability re-test" entry. This is a clean, unambiguous
finding: the 240-day threshold is **not brittle** in this corpus (contrast
with the old 182-day-equivalent line, which INTC/KO/MCD/TMO/WOLF missed by
1–13 days).

**Restorations (7 total):**

| Ticker | Stratum | Old rule | New rule (days) | Result |
|---|---|---|---|---|
| INTC | S1 | fail (2.01q ≈ 183d) | 183d ≤ 240 | restored |
| KO | S1 | fail (2.02q ≈ 184d) | 184d ≤ 240 | restored |
| MCD | S1 | fail (2.02q ≈ 184d) | 184d ≤ 240 | restored |
| TMO | S1 | fail (2.13q ≈ 194d) | 194d ≤ 240 | restored |
| FRC | S4 | fail (12+/no-trailing-gap) | A2: 6 calls, 4 in 12mo pre-receivership | restored |
| RMO | S4 | fail | A2: 6 calls, 3 in 12mo pre-merger | restored |
| SUNW | S4 | fail | A2: 10 calls, 4 in 12mo pre-bankruptcy | restored |

**Still fails:** POWI (S2, 273 days > 240 — a genuine two-skip gap, not a
rounding artifact); SIVB (S4, **0 events returned by the vendor at all** —
structurally absent, same class of gap as GOOGL, not fixable by any
availability-rule change). LIN was tested as an S1 reserve candidate (now
passes at 189 days) but was never needed — S1 has no shortfall once INTC/KO/
MCD/TMO are restored, so LIN stays an available-but-unused reserve name, not
added.

**Domain-ineligible names re-tested but NOT restored despite passing A2 on
paper:** NKLA, FSR, PTRA, LICY, RIDE, SBNY — these are the first pass's own
S4 reserve pool (already marked `"qualifies": false` in
`selection_working.json` for domain/point-in-time reasons, independently
re-confirmed by this run's own A3 verification of the same underlying
companies). Availability is necessary but not sufficient; domain eligibility
gates first. Correctly excluded.

## Step C — re-freeze

`analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json` (new file, commit
`71fb50f`), sha256 `9b256b71eaa3038f5897a1a82d54c314abec8e843c5523a00c9a274a14f486ce`.

`CORPUS_MANIFEST.json` (v1) confirmed **untouched**: re-hashed at freeze
time, sha256 `0e036e97777577cdd1a87b97e6cd8d81bf1c69d367b3c2915254c86cc61e3080` — matches the value stated in the prompt's own framing exactly.

**No return was looked at before this freeze.**

| Stratum | v1 (first pass) | v2 (this pass) | Change |
|---|---|---|---|
| S1 | 18/20 | **22** (target 20; 4 restored + HON/UPS kept) | +4 |
| S2 | 15/16 | 15/16 | unchanged (POWI still fails) |
| S3 | 20/20 | 20/20 | unchanged |
| S4 | 2/8 (WOLF, NOVA) | **5/8** (+FRC, RMO, SUNW) | +3 |
| S5 | 16/16 | 16/16 | unchanged (exempt; GOOGL still absent from vendor) |
| **Total** | **71** | **78** | **+7** |

S4 shortfall of 3 (SIVB structurally absent from vendor; no eligible A3
replacement) is **not closed**, per the prompt's explicit instruction not to
lower A2's thresholds to compensate.

Total calls (2020–2025) across the 78-company v2 corpus:
`CORPUS_MANIFEST_V2.json` → `totals.total_calls_2020_2025_v2` = **1,652**.

## Step D — outcome balance (report only, after the freeze)

Driver: `analysis/corpus_construction_outcomes_v2.py` (new file), same
method as the first pass's Step 4b (182-calendar-day forward return of each
company's last available call vs. SPY, ±5pt dead band, per-company proxy).
Extends `analysis/data/corpus_v2/corpus_v2_price_cache.json` (the same cache
the first pass used) for newly-fetched tickers only; `analysis/data/price_cache.json`
(production) untouched. Output: `analysis/data/corpus_v2/outcome_balance_v2.json`.

| | n | beats | lags | moves-with |
|---|---|---|---|---|
| **v2, ex-S5 (this pass)** | 56 | 44.6% | 37.5% | 17.9% |
| **v2, ex-S5-and-S4 (per A4)** | 55 | 45.5% | 36.4% | 18.2% |
| v1 first pass, ex-S5 | 54 | 44.4% | 35.2% | 20.4% |
| Existing corpus | — | 46.2% | 42.1% | 11.7% |
| v2, S4-only | 1 | 0.0% | 100.0% | 0.0% |
| v2, all including S4+S5 | 71 | 39.4% | 46.5% | 14.1% |

**Finding, contradicting an expectation of this run:** 4 of the 5 frozen S4
companies (NOVA, FRC, RMO, SUNW) are **skipped as "missing price data"** —
`yfinance` has no forward-window price series for them under their original
ticker, because they were delisted, acquired, or liquidated at or shortly
after failure (exactly what the stratum studies). Only WOLF, which survived
as a going concern, produces a measurable outcome. **S4-only n=1, not 5.**
Restoring a company's *call* coverage (Step B) does not restore its
*post-failure price* coverage under the original ticker — a second,
independent coverage gap the corpus's outcome-balance measurement inherits.
Not corrected here (would require sourcing successor-entity tickers or
acquirer-adjusted series, out of scope for this pass); reported as a finding
per the run's own standing instruction.

**No return was looked at before Step C's freeze — Step D ran strictly
after.** The v2 ex-S5 figure (44.6/37.5/17.9, n=56) sits close to but not
identical to the v1 figure (44.4/35.2/20.4, n=54); the shift is fully
explained by the four S1 restorations (INTC/KO/MCD/TMO) plus WOLF's
inclusion changing the denominator from 54 to 56. **Not re-picked regardless
of this result**, per the pre-registered rule.

## Step E — three-way split and holdout lock

Driver: `analysis/corpus_construction_split_v2.py` (new file). Method:
identical to the one the first pass itself registered for this step
(`PREREGISTRATION.json` → `outcome_holdout_split`: "`random.shuffle` per
stratum with the fixed seed, then round-robin train/tune/holdout
assignment"), applied here to the 78-company v2 corpus. Split is by
**company**, never by call. Seed `20201231`.

| Split | Companies | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|---|
| train | 28 | 8 | 5 | 7 | 2 | 6 |
| tune | 26 | 7 | 5 | 7 | 2 | 5 |
| holdout | 24 | 7 | 5 | 6 | 1 | 5 |

Holdout list locked into `CORPUS_MANIFEST_V2.json` → `step_e_split.holdout`
(24 tickers: AMAT, AVGO, BLDP, BMY, COP, CSCO, CVX, ENVX, FORM, HUM, INTC,
JPM, MCD, MRK, MU, NEE, ORCL, PFE, RMO, RUN, SLAB, TMO, TTD, VZ). Holdout
sha256: `d4e40fe0b5f1234b34c3fe7ccd5e704afff4e5aaf4e17dbc0e53c2223e412a23`.

`docs/architecture/PROMOTION_GATE.md` §10 checked first — **no holdout-lock
note existed from any prior attempt**. Added the one authorized note (dated
2026-09-14), stating the holdout must not be scored during iteration and
naming the sha256.

## Step F — the deliverable: what ruler does this buy?

Driver: `analysis/corpus_construction_stepF_v2.py` (new file). Reuses
`analysis/scorecard_repair_driver.py`'s `step3_paired` / `step3_unpaired`
ticker-block-bootstrap detection simulation — **read in full this session**
(not read in the original partial publication, corrected here). Because the
v2 corpus has never been scored (corpus is selected, not scored — CLAUDE.md;
zero Anthropic API calls this entire run), Step F cannot measure a real
challenger difference on the new corpus. Instead, exactly as
`scorecard_repair_driver.py`'s own `data_volume_answer` function already
does for its "how many more tickers would help" question, this driver
replicates the **real, already-scored ALL16 population** (n=359 calls, 16
tickers, `value_attribution_v2_stage_b_driver.build_populations()['scorer_thin_filtered']`)
onto synthetic ticker blocks sized to match each scenario's company count.
**This is a simulated projection of what MDE that many blocks would buy at
ALL16's own accuracy and call-volume pattern — not a measurement of the new
corpus, which remains unscored.** Disagreement rate 0.15 (the driver's own
default). 60 trials/X (reduced from the driver's own default of 150 for
this session's budget — noted as added Monte Carlo noise below, not a
change in conclusion).

| Scenario | n companies | Multiplier → synthetic tickers | **Paired MDE** | Unpaired MDE |
|---|---|---|---|---|
| **Realistic** (train+tune, all strata) | 54 | ×4 → 64 | **1 pt** | 7 pt |
| Fallback: half survive a future re-check | 27 | ×2 → 32 | **4 pt** | 9 pt |
| Fallback: in-scope strata only (S2+S4+S5)* | 25 | ×2 → 32 | **4 pt** | 9 pt |
| *(today, 16 tickers, for reference)* | 16 | ×1 → 16 | 5 pt (this run's quick recheck) | — |

*In-scope strata = S2 and S5 (both explicitly domain-restricted to
DOMAIN.md's Tier 1/2 universe per `PREREGISTRATION.json`'s own S2 rule text)
plus S4 (whose rule requires domain-or-S&P eligibility). **S1 and S3 are
explicitly NOT domain-restricted** per their own registered rule text ("S1:
ranks 21-40 by market cap... no randomness"; "S3: Outside DOMAIN.md
entirely") and are therefore excluded from this fallback.

**Fill-in-the-blank, stated plainly: "two prompt versions compared on the
same calls can be told apart when the real difference is 1 point or larger
— against 6 points today."** (The **published** today-figure is 6pp —
`analysis/data/scorecard_repair/scorecard_repair_manifest.json` →
`results.step3_detection_threshold.paired_default_disagreement.minimum_detectable_improvement_pp`
— not this run's own 60-trial quick recheck of 5pp, which differs by
Monte-Carlo noise from the halved trial count, not a real change; the
published 150-trial figure is the one to cite.)

**The realistic paired figure (1pp) comes in well below the 3-point bar.**
**Both fallbacks (4pp) do NOT** — flagged plainly, per the prompt's own
instruction, as the recommendation to raise the company count before
commissioning any scoring run *if* either fallback condition is the one that
actually holds when scoring time comes (i.e., if a future availability
re-check knocks out roughly half the corpus, or if only the domain-scoped
strata are used, 78 companies is not enough; the full 54-company train+tune
set, all strata, is).

**Verification of correct methodology reuse:** this run's realistic-scenario
result (multiplier 4, 64 synthetic tickers, paired MDE = 1) is an **exact
match** to the already-published run's own
`results.step3_detection_threshold.step3.data_volume_answer_for_3pp_paired_threshold.stock_axis`
(multiplier 4, n=64, mde=1) in `scorecard_repair_manifest.json` — strong
evidence this driver reused the intended methodology correctly rather than
reimplementing something subtly different.

## Step G — cost

| | Companies | Total calls (2020–2025) | Avg calls/company | Illustrative cost* |
|---|---|---|---|---|
| Train+tune only | 54 | 1,134 | 21.0 | ~$23–$57 |
| All three splits | 78 | 1,652 | 21.2 | ~$33–$83 |

*Per-call cost assumption **stated, not measured or billed**: a
claude-sonnet-4-20250514 evaluation call on a typical earnings-call
transcript, assumed ~5,000 input / ~1,000 output tokens, on the rough order
of $0.02–$0.05/call. This is illustrative scaffolding for planning, not a
quote.

**Restated per CLAUDE.md and the prompt's own instruction, not just as a
limitation:** anything scored on this corpus uses a **current** model and is
therefore a **new baseline, not an extension** of v6 or any existing figure.
The moment this corpus is scored, every existing benchmark figure —
including the very ALL16-based 6pp/1pp numbers Step F just projected from —
becomes historical.

## Required limitations

- Corpus is selected, not scored — no real prompt-version comparison has
  been run on it. Step F's numbers are a simulated projection using the
  real ALL16 population's accuracy/call pattern replicated onto synthetic
  blocks, not a measurement of the new corpus.
- S4 over-represents failures by construction (A4); Step D reports every
  figure both with and without S4. Step F's fallback scenarios do the same
  for strata scope.
- The first pass's 59-survivor language and this pass's 78-company total are
  both lower bounds on what a further availability pass might restore.
- S1's ranks 21–40 ordering (inherited from the first pass, not re-verified
  this pass) still carries the first pass's own flagged limitation.
- This wrap-up's A3 eligibility conclusions rely on web search results dated
  2026-09-14; sources cited inline in the Step A section above.
- Step D's outcome-balance measurement structurally under-samples S4 (n=1
  of 5 frozen members) because failed companies' price series end at
  failure under their original ticker — a second coverage gap distinct from
  (and not fixed by) Step B's call-availability restoration.
- Step F used 60 Monte Carlo trials/X instead of the driver's own default
  150, for this session's time budget; the direction of every finding above
  (realistic clears 3pp, both fallbacks don't) is not expected to flip from
  this alone, but exact pp values carry more sampling noise than a 150-trial
  run would produce. The one number quoted from a 150-trial run (today's 6pp
  baseline) is the published figure, not recomputed here.

## What was deliberately not done

- No new S4 candidates were sourced beyond the pre-registered 15 (out of
  scope for this pass; would need its own pre-registration per Step A's
  finding that all 15 registered names are ineligible).
- Step F's in-scope-strata-only fallback did not attempt a finer per-company
  domain judgment for S4 members (e.g. treating FRC as out-of-domain while
  keeping WOLF/NOVA/SUNW/RMO in) — the whole S4 stratum was treated as
  in-scope per its own registered eligibility rule, which is a coarser cut
  than a company-by-company domain re-litigation would give.
- Scoring the corpus itself — explicitly out of scope; zero Anthropic API
  calls were made anywhere in this run.

## Vendor call budget

167 vendor calls this run total (82 first pass + 85 Step B fix pass), all in
Steps A–C; Steps D–G made **zero** further vendor calls (Step D used
`yfinance`, a separate free data source, not the EarningsCall.biz vendor;
Steps E–G are pure computation over already-stored data). Well under the fix
driver's Step-B script cap of 100 and the original driver's 120. Combined
period running total: see `analysis/data/run_state/corpus-construction/progress.json`
→ `calls_used_total` (167) plus whatever `ec-fidelity-benchmark-1` has
separately accrued in its own `progress.json` — not re-summed here since that
file was not re-read this session; the first pass's wrap-up reported a
combined ~293/1000 at that time, and this pass adds 85 more (EarningsCall.biz)
plus an unmetered number of `yfinance` calls (a different, free vendor, not
subject to the same monthly cap).

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on every new driver
  (`corpus_construction_fix_driver.py`, `corpus_construction_outcomes_v2.py`,
  `corpus_construction_split_v2.py`, `corpus_construction_stepF_v2.py`) —
  passed.
- `json.load` round-trip check on `PREREGISTRATION_FIX.json`,
  `CORPUS_MANIFEST_V2.json`, `SPLIT_V2.json`, `progress.json` — passed.
- `CORPUS_MANIFEST.json` (v1) re-hashed post-freeze and confirmed unchanged.
- Confirmed via `git log` that each driver's commit precedes the commit that
  uses its output (`912ccaa` before `71fb50f`; `a131a6b` before the Step D
  data commit `8fc4682`; `923a261` and `7f7c222` before Step E/F results).
- Step F's realistic-scenario result cross-checked exactly against the
  already-published `scorecard_repair_manifest.json`'s own
  `data_volume_answer_for_3pp_paired_threshold.stock_axis` (multiplier 4,
  n=64, mde=1) — exact match, see Step F above.
- `docs/architecture/PROMOTION_GATE.md` checked for an existing holdout-lock
  note before adding one (none found).

## Working-tree hygiene

Unrelated dirty state (ec-fidelity-benchmark-1's progress.json, several
untracked prompt/handoff files) was stashed at the start
(`unrelated-wip-before-corpus-construction-fix`), popped after the original
(partial) publication of this wrap-up, and confirmed clean with no
conflicts — the same unrelated files reappeared as modified/untracked,
nothing from this run's commits leaked into that stash. No re-stash was
needed for this continuation (Steps D–G touched only this run's own files,
all committed along the way); `git status --short` at the end of this
continuation shows only the same pre-existing unrelated dirty state.

## Follow-up commands

```bash
# Confirm the tree carries only the pre-existing unrelated dirty state
git status --short

# Inspect the deliverable directly
cat analysis/data/corpus_v2/STEP_F_DETECTION_THRESHOLD.json

# If a future session widens S4 with domain-correct candidates, or actually
# scores the corpus, start from a NEW pre-registration -- per CLAUDE.md,
# assert the prompt hash against VERSION_REGISTRY.json first:
python3 analysis/version_guard.py --help
```
