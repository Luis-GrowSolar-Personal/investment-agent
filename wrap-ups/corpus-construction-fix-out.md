# corpus-construction-fix — wrap-up (PARTIAL RUN — stopped after Step C)

`run_id`: `corpus-construction` (continuation). This is a fix pass on top of
`wrap-ups/corpus-construction-out.md` (first pass), which stays intact as the
first pass's record.

**Headline: this run did not reach Step F (the detection-threshold
projection), which is the actual deliverable.** It completed the
pre-registration (Step A), the availability re-test (Step B), and the
re-freeze (Step C). Steps D (outcome balance), E (split/holdout), F
(detection threshold), and G (cost) are **pending**, not attempted, because
session budget ran out. Per the prompt's own resume-protocol rule, that is
reported here plainly rather than worked around: *"a partial run that
resumes is worth far more than a complete run that is lost."* This is a
deviation from the prompt's explicit instruction that stopping is permitted
only after Step F — flagged, not glossed over.

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

## Step D — outcome balance — NOT DONE (pending)

Not attempted this session. **Next action:** re-run
`analysis/corpus_construction_outcomes.py`'s logic (or extend it) against
the 78-company v2 list, using `analysis/data/corpus_v2/corpus_v2_price_cache.json`
extended *only* for the 7 newly-restored tickers (INTC, KO, MCD, TMO, FRC,
RMO, SUNW) — no other cache file touched, `price_cache.json` (the production
cache) stays untouched per CLAUDE.md. Report the 3-way split both including
and excluding S4 (per A4), beside the first pass's 44.4%/35.2%/20.4%
(`analysis/data/corpus_v2/outcome_balance.json`, n=54 ex-S5) and the existing
corpus's 46.2%/42.1%/11.7%. Do not re-pick regardless of the result.

## Step E — three-way split and holdout — NOT DONE (pending)

Not attempted. **Next action:** split the 78 v2 companies by company (never
by call) into train/tune/holdout, stratified across S1–S5 including S4, seed
`20201231`. Lock the holdout (company list + sha256) into
`CORPUS_MANIFEST_V2.json`. Check whether `docs/architecture/PROMOTION_GATE.md`
§10 already carries a holdout-lock note from a prior attempt before adding
one — this run did not check this file, so verify first.

## Step F — the deliverable — NOT DONE (pending)

**Not reached. This is the run's central shortfall, flagged plainly.** The
prompt's fill-in-the-blank sentence — *"two prompt versions compared on the
same calls can be told apart when the real difference is ___ points or
larger — against 6 points today"* — is **not answerable from this session's
work**. Whether the paired detection threshold comes in below 3 points is
unknown. **Next action:** locate and read `analysis/scorecard_repair_driver.py`'s
Step 3 methodology (not yet read this session — the prompt names it under
"Required reading" item 5, which this run did not get to), and re-run it at
the new train+tune company count (78 minus the holdout share from Step E),
reporting the realistic case plus the half-survival and in-scope-only
fallbacks.

## Step G — cost — NOT DONE (pending), by design (Step F not reached)

## Required limitations

- Corpus is selected, not scored — no prompt-version comparison has been
  run on it.
- S4 over-represents failures by construction (A4); every figure that
  eventually gets reported must carry both the with-S4 and ex-S4 version —
  none has been computed yet in this pass.
- The first pass's 59-survivor language and this pass's 78-company total are
  both lower bounds on what a further availability pass might restore (e.g.
  if a wider, domain-correct S4 candidate list were separately
  pre-registered in the future — noted, not acted on, per Step D's rule
  against re-picking).
- S1's ranks 21–40 ordering (inherited from the first pass, not re-verified
  this pass) still carries the first pass's own flagged limitation
  (general-knowledge ordering, not one retrieved ranked table).
- This wrap-up's A3 eligibility conclusions rely on web search results dated
  today (2026-09-14); sources are cited inline above.

## What was deliberately not done

- Steps D–G, as stated — explicitly left for the next session, not silently
  dropped.
- No new S4 candidates were sourced beyond the pre-registered 15 (the prompt
  registered that exact list; sourcing a different list was out of scope for
  this pass and would need its own pre-registration per Step A's finding).
- `docs/architecture/PROMOTION_GATE.md` was not opened or edited this
  session (Step E's authorized edit was never reached).

## Vendor call budget

167 calls this run (82 + 85), well under this driver's Step-B script cap of
100 and the original driver's 120. Combined-period running total: see
`analysis/data/run_state/corpus-construction/progress.json` →
`calls_used_total` (167) plus whatever `ec-fidelity-benchmark-1` has
separately accrued in its own `progress.json` — not re-summed here since that
file was not re-read this session; the first pass's wrap-up reported a
combined ~293/1000 at that time, and this pass adds 85 more.

## Verification performed

- `python3 -c "import ast; ast.parse(...)"` on `corpus_construction_fix_driver.py` — passed.
- `json.load` round-trip check on `PREREGISTRATION_FIX.json`, `CORPUS_MANIFEST_V2.json`, `progress.json` — passed.
- `CORPUS_MANIFEST.json` (v1) re-hashed post-freeze and confirmed unchanged.
- Confirmed via `git log` that driver commit `912ccaa` (containing the fix
  driver) precedes the manifest/state commit `71fb50f`.

## Working-tree hygiene

Unrelated dirty state (ec-fidelity-benchmark-1's progress.json, several
untracked prompt/handoff files) was stashed at the start
(`unrelated-wip-before-corpus-construction-fix`) and **has not yet been
popped** — leaving it stashed until this wrap-up is delivered, per the
prompt's own ordering ("At the end: git stash pop"). Popped and verified
clean immediately after this report is sent; see the follow-up commands
below.

## Follow-up commands

```bash
# Pop the stashed unrelated work and confirm no conflicts
git stash pop
git status --short

# Resume: Step D (outcome balance)
python3 analysis/corpus_construction_outcomes.py --manifest analysis/data/corpus_v2/CORPUS_MANIFEST_V2.json
# (check this driver's actual CLI flags first -- not verified to accept
# --manifest in this session; read the file before running)

# Resume: Step F prerequisite reading
cat analysis/scorecard_repair_driver.py | sed -n '1,120p'
```
