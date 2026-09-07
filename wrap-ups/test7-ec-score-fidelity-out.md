# test7-ec-score-fidelity — wrap-up

**Scope boundary: report, do not decide.** No `PROMOTION_GATE.md` change,
no `Analysis` table writes, no vendor decision made. Step 4's third-row
trigger (see below) is flagged as a follow-up, not acted on here.

## Resume status

Fresh run, no prior `run_state` for `run_id=test7-ec-score-fidelity`. The
driver (`analysis/test7_score_fidelity.py`) already existed, fully written
but never executed, when this session started — a concurrent session on
this shared branch had built it (same pattern as the EC benchmark's own
driver in the prior run). Reviewed it fully before trusting it: correct
imports (Test 4's `get_model_version`/`get_prompt_header`/`parse_structured`,
the EC driver's `vendor_payload_to_text_and_turns`, both by import, neither
reimplemented), correct disjoint-set divergence logic, an explicit
human-confirmation gate before any spend. Found and fixed one cosmetic bug
before running (RUN mislabeled tier `"large"` in Tier B; corrected to
`small_micro`, the tier it has everywhere else in this project — display
field only, no effect on any computation). **All steps (0, 1, 2, 3) ran to
completion this session — full run, not partial.**

**Real spend check, per this prompt's own ground rule**: `test6-look-ahead-prohibition`
was confirmed **actively running** at the moment this run reached Step 2 —
a live background process, 46/50 treatment transcripts complete, under its
own separately user-approved ~$25 budget. Per the ground rule ("stop and
ask before spending anything here"), stopped and asked before Step 2. You
approved proceeding concurrently. Step 2 ran as approved.

**Exact spend: 30 calls, 577,225 tokens (489,195 in / 88,030 out).**
Estimated cost at standard Sonnet-family rates ($3/M in, $15/M out):
**$2.79** (Test 4's own observed-rate estimate for this run's own call
count was $2.76 — both are estimates, not billed figures; check the
Anthropic Console for the actual charge, per Test 4's own caveat, carried
forward here rather than re-derived).

---

> **7 cells tested (Tier A ×4, Tier B ×3; Tier C off by default, not run).
> 0 flagged divergences on any primary field (`thesisHealth`,
> `recommendation`, `stumbleType`, `mitigationCapabilityTrackRecord`) in
> any cell — every primary-field comparison is `inconclusive-overlap`,
> including AMPX(16)/FSLR(287)/TSLA(220)/QS(348) reusing Test 4's cached
> DB-side runs, and RUN(370)/AAPL(154)/AMD(249) run fresh on both sides.
> 2 flagged divergences on the two non-primary numeric sizing fields
> (`recommendedSize`, `freshMoneyAllocation`) — both on Tier B's confirmed-
> defect cells (AAPL id 154, AMD id 249), both non-overlapping ranges,
> both consistently HIGHER under EC than DB. Bottom line: **supports EC on
> the primary-field question tested here** (the verdict rule this prompt
> fixed in advance is scoped to the 4 primary fields, and none diverged) —
> **but the numeric-sizing divergence on 2/3 Tier B cells is a real,
> reported pattern the verdict table has no row for, and is not waved away
> as out of scope.** Not a statement about the untested remainder of the
> 195-cell corpus, and not a statement that numeric-field agreement was
> tested at all — only two cells showed it, and both diverged.**

---

## Step 0 — hygiene and the hard version-match gate

Clean tree confirmed for this run's own dependencies (see Deviations for
the concurrent-session tracked-file note, same situation as the EC run).
Driver committed (`6ecb714`) before this run_state, as its own commit,
together with the prompt.

**Version-match gate: passed.** `get_model_version()` → `claude-sonnet-4-6`,
`get_prompt_header()` → `v10+auto1 (auto-iterate candidate — pending gate)`
— both **exact matches** to what `analysis/test4_noise_floor/raw/{16,287,220,348}.json`
recorded (`model` / `prompt_version_header` fields). **All 4 Tier A cells
cleared to reuse Test 4's cached DB-side runs** — no model or prompt drift
since Test 4 ran, so this comparison is not confounded by a version change
in either direction.

## Step 1 — build both text sides (0 API calls)

All 8 cells (7 default + Tier C, built but not scored) resolved by
**content**, not by the guessed filename, per the driver's own
`resolve_ec_raw_path()` — every guessed EC raw filename happened to exist,
confirmed rather than assumed:

| Tier | id | Ticker | DB words | EC words |
|---|---|---|---|---|
| A | 16 | AMPX | 6,890 | 7,175 |
| A | 287 | FSLR | 9,791 | 9,840 |
| A | 220 | TSLA | 8,039 | 8,066 |
| A | 348 | QS | 4,206 | 4,334 |
| B | 370 | RUN | 10,742 | 11,442 |
| B | 154 | AAPL | 7,900 | 8,204 |
| B | 249 | AMD | 8,819 | 9,332 |
| C (not scored) | 757 | GOOGL | 9,163 | 8,600 |

No cell showed a missing file or an implausible word count — every EC side
is a substantial, complete-looking transcript (consistent with the EC
benchmark's own finding that none of these specific cells are coverage
misses).

## Step 2 — scoring calls (real spend)

Tier A: 4 cells × 3 EC-side runs = 12 calls (reusing Test 4's existing 5
DB-side runs per cell, 20 already-paid-for runs, 0 new DB-side calls).
Tier B: 3 cells × 2 sides × 3 runs = 18 calls, all fresh. **Total 30
calls**, exactly the prompt's default-scope estimate. Tier C not run
(off by default, not requested this session).

Same call shape as Test 4 throughout: `max_tokens=8192`, `temperature=0`,
single-user-message, `docs/EVALUATION_PROMPT.md` read fresh (unmodified),
no portfolio context — firewall-consistent. Zero `Analysis` table writes.
Raw output saved per Tier A/B cell/side to
`analysis/test7_score_fidelity/raw/<id>_{db,ec}.json`, same schema as Test
4's own raw files plus a `side` field.

## Step 3 — field-by-field comparison (0 new calls)

Full per-cell, per-field table (from
`analysis/data/run_state/test7-ec-score-fidelity/comparison_report.txt`):

### Tier A (Test 4's cached DB n=5, this run's fresh EC n=3)

> **AMPX 2025-08-07 (small_micro, id 16): DB thesisHealth = {Strengthening}×5,
> EC = {Strengthening}×3 — no divergence. DB recommendation = {Add}×5, EC =
> {Add}×3 — no divergence. DB stumbleType = {None}×5, EC = {None}×3 — no
> divergence. DB mitigationCapabilityTrackRecord = {strong}×5, EC =
> {strong}×3 — no divergence. [Inconclusive-overlap on all 4 primary
> fields — trivially, since every DB run and every EC run individually
> agree]. DB-side already unstable on this field per Test 4: no, on any
> primary field (all 5 DB runs identical on every primary field).**

> **FSLR 2023-02-28 (mid, id 287): thesisHealth/recommendation/stumbleType
> all stable and matching on both sides. mitigationCapabilityTrackRecord:
> DB = {mixed, strong, unproven} (3 distinct values across Test 4's own 5
> runs), EC = {mixed, strong} (2 of 3 runs). Overlapping — inconclusive,
> not divergence. DB-side already unstable on this field per Test 4:
> **yes** — this exact field on this exact transcript was already flipping
> across 3 of 5 identical-DB-text runs before EC ever entered the picture.**

> **TSLA 2022-10-19 (megacap, id 220): thesisHealth/recommendation/stumbleType
> stable and matching. mitigationCapabilityTrackRecord: DB = {unproven,
> mixed} (Test 4's 5 runs: 1 unproven, 4 mixed), EC = {mixed, strong} (this
> run's 3: 2 mixed, 1 strong). Shares "mixed" — overlapping, inconclusive.
> DB-side already unstable on this field per Test 4: **yes.** Note: EC's
> "strong" value never appeared in any of Test 4's 5 DB-side runs — the
> set-overlap rule reads this as inconclusive (not disjoint), but it is
> the one primary-field cell where EC produced a value the DB side never
> once produced in 5 tries. Flagged as a borderline case rather than
> silently absorbed into "overlap = fine."**

> **QS 2024-04-24 (small_micro, id 348, the control — highest EC
> similarity ratio in the overlap, 0.622): thesisHealth/stumbleType stable
> and matching. recommendation: DB = {Hold}×5 (**rock-solid** across all 5
> of Test 4's original runs — the tightest possible baseline), EC =
> {Add, Hold, Add} (2 of 3 runs said Add). Shares "Hold" — technically
> overlapping under the set rule, so **not** a flagged divergence — but
> this is the cell chosen specifically as the expected-cleanest control
> (highest text similarity), and it is the one where EC's own repeat
> distribution (2/3 Add) looks least like the DB baseline's (5/5 Hold).
> Reported plainly as a second borderline case, not smoothed into a clean
> pass: the control cell did not behave more stably than the low-similarity
> stress cells above it. mitigationCapabilityTrackRecord: DB = {mixed,
> unproven, strong} (already 3-way unstable per Test 4), EC = {mixed,
> unproven} — overlapping. DB-side already unstable on `recommendation`
> per Test 4: **no** (5/5 Hold, the most stable possible baseline) — this
> is the one primary-field instance in Tier A where the DB side was
> genuinely rock-solid and EC's repeats still landed on a different modal
> answer, even though the sets technically overlap.**

### Tier B (both sides fresh, n=3 each)

> **RUN 2022-Q3 (id 370, confirmed truncated on the EC side — see
> `ec_transcript_fidelity_benchmark_1-out.md`): all 4 primary fields
> identical value-sets on both sides (thesisHealth {Strengthening},
> recommendation {Add}, stumbleType {None}, mitigationCapabilityTrackRecord
> {strong} — every one of 3 DB runs and every one of 3 EC runs agree with
> each other and across sides). **No divergence, no borderline case
> either** — the one cell with a confirmed missing operator sign-off shows
> zero measurable effect on any primary field.**

> **AAPL bucket-2022Q4 / vendor 2023Q1 (id 154, confirmed truncated on the
> EC side): thesisHealth stable/matching (Intact×3/Intact×3). recommendation:
> DB = {Hold, Add} (2 Hold, 1 Add — **already unstable on DB text alone,
> fresh 3-run measurement**), EC = {Add}×3 — shares "Add", overlapping,
> not a flagged divergence, but worth stating plainly: DB was already split
> before EC entered the picture, so an EC-side unanimous "Add" is not
> distinguishable from the evaluator's own pre-existing coin-flip on this
> transcript. stumbleType: DB = {Execution, Discovery} (also split), EC =
> {Discovery}×3 — shares "Discovery", overlapping. **`recommendedSize`:
> DB = [20, 22, 20] (range 20–22), EC = [28, 28, 35] (range 28–35) — ZERO
> OVERLAP, flagged DIVERGENCE.** **`freshMoneyAllocation`: DB = [15, 18, 15]
> (range 15–18), EC = [22, 22, 28] (range 22–28) — ZERO OVERLAP, flagged
> DIVERGENCE.** EC's sizing runs consistently higher than DB's on both
> numeric fields, no exceptions across 3 runs each.**

> **AMD 2022-Q2 (id 249, ASR-garbled-but-content-complete control):
> thesisHealth/recommendation/stumbleType/mitigationCapabilityTrackRecord
> all stable and matching on both sides (Strengthening/Add/None/strong,
> 3-for-3 each side) — the ASR garbling of the closing phrase (`"does
> conclude"` → `"does include"`) that made the EC benchmark's classifier
> initially flag this cell as possibly-truncated has **zero measurable
> effect on any primary field**, confirming the EC wrap-up's own manual
> read that this cell is content-complete. **`recommendedSize`: DB =
> [22, 18, 22] (range 18–22), EC = [32, 32, 35] (range 32–35) — ZERO
> OVERLAP, flagged DIVERGENCE.** **`freshMoneyAllocation`: DB = [18, 14, 18]
> (range 14–18), EC = [22, 28, 25] (range 22–28) — ZERO OVERLAP, flagged
> DIVERGENCE.** Same direction as AAPL: EC consistently higher.**

## Step 4 — verdict, applied per cell against the rule fixed before results

| Cell | Row that applies |
|---|---|
| AMPX (16) | **Row 1** — no divergence on any primary field. |
| FSLR (287) | **Row 2** — `mitigationCapabilityTrackRecord` shows no divergence (overlapping), but it was already unstable on DB text alone per Test 4; not attributable to EC even if it had diverged. |
| TSLA (220) | **Row 2**, with the borderline note above — `mitigationCapabilityTrackRecord` already unstable on DB per Test 4 (1 unproven / 4 mixed); EC's "strong" is a new value not seen on DB, but the field was not stable to begin with. |
| QS (348, control) | **Row 1** on the letter of the rule (no disjoint set on any primary field) — but flagged as the weakest "Row 1" in this run: `recommendation` was DB-stable (5/5 Hold) and EC's own repeats (2/3 Add) landed on the opposite modal answer without technically diverging, only because one of three EC runs happened to say Hold. |
| RUN (370, confirmed truncated) | **Row 1**, cleanly — no divergence, no borderline note, on the cell most likely a priori to show one. |
| AAPL (154, confirmed truncated) | **Row 1 on primary fields; a real, reported effect on the two numeric fields the verdict table doesn't cover.** `recommendation`/`stumbleType` were already split on DB alone (fresh 3-run measurement), so any primary-field movement there would fall under Row 2's logic even though no primary-field disjoint set actually occurred. `recommendedSize`/`freshMoneyAllocation` both diverge cleanly, DB stable-ish (tight 20–22 / 15–18 ranges) vs EC higher (28–35 / 22–28). |
| AMD (249, ASR-garbled control) | **Row 1 on primary fields, cleanly** — all four primary fields stable and matching on both sides. **Same numeric-field divergence as AAPL**, same direction (EC higher), on a cell whose primary-field scoring was otherwise unaffected by the ASR garbling. |

**No cell triggers Step 4's Row 3** (a primary-field divergence where the
DB side was stable and EC's repeats land somewhere else entirely) — **the
Stage-2 primary-source audit is not triggered by this run.** The rule as
written is scoped to the 4 primary fields, and by that rule this run's
answer is clean.

**But the numeric-field pattern is reported here rather than filed under
"not primary, doesn't count."** Two of Tier B's three cells — both of the
confirmed-defect cells, not the ASR-only control's primary fields, and
notably not Tier A's four stress cells at all — show a clean, non-overlapping,
consistently-higher-under-EC pattern on both sizing fields. This prompt's
own Step 3 asked for numeric fields to be reported with the same
overlap/disjoint standard as categorical ones; the verdict table in Step 4
just doesn't have a row that names them. Read literally, this run's answer
is "clean" (Row 1 dominates); read for what actually moved, two of three
Tier B cells show a real, repeated, directional sizing effect that a
Step-6 ingestion design should not ignore just because it falls outside
this prompt's own primary-field gate.

## Deviations from the prompt, and why

1. **Reused a pre-existing, unrun driver** written by a concurrent session
   — reviewed fully before trusting it, same precedent as the prior EC
   benchmark run, to avoid a second independent implementation risking a
   double-count against the shared real-money spend.
2. **Fixed one cosmetic bug** (RUN's tier mislabeled `"large"`, corrected
   to `"small_micro"`) before running — a display-field-only bug, verified
   it did not affect any comparison logic (tier is never used in
   `compare_sets()` or the divergence rule).
3. **Stopped and asked before Step 2**, per the prompt's own ground rule,
   because `test6-look-ahead-prohibition` was confirmed actively running
   (live process, 46/50) at that exact moment. You approved proceeding
   concurrently; Step 2 ran as approved, 30/30 calls succeeded with no
   errors.
4. **The Step 4 verdict table has no row for a numeric-field-only
   divergence** — reported the mismatch explicitly (see above) rather than
   silently classifying these two cells as "Row 1, clean" and dropping the
   sizing finding, or inventing an unrequested new row to force a verdict
   the prompt didn't define.
5. **Tracked-file dirty tree from a concurrent session** — `git status`
   showed `test6-look-ahead-prohibition`'s own state files actively
   changing (the live process above) plus a modified
   `ec-fidelity-benchmark-1/progress.json` (a different concurrent
   session's GOOGL-alias verification work, confirmed real via its own
   `call_log` entries — not fabricated, not touched or re-verified further
   here since it is this run's read-only input, per the ground rule
   forbidding modification of `ec_fidelity_benchmark_1/`). Neither was
   staged, read for scoring, or altered by this run.

## What was deliberately not done

- **Tier C (GOOGL via `GOOG` alias)** — built (Step 1 confirmed the text
  resolves, 9,163 vs 8,600 words) but not scored; off by default per the
  prompt, not requested this session. Would cost 6 more calls
  (~$0.55) if enabled later — `python3 test7_score_fidelity.py score --tier-c`
  picks up exactly where this run left off (Tier A/B cells already scored
  are skipped by the existing-file check).
- **No Stage 2 primary-source audit** — not triggered (no Row 3 hit), and
  explicitly out of scope for this run regardless.
- **No root-cause investigation of the numeric-sizing divergence** — flagged
  as a pattern (2/3 Tier B cells, same direction, both confirmed EC-text
  defects) rather than traced to a specific rubric clause or text passage;
  that would be new analysis beyond this prompt's own Step 3/4 scope.
- **No re-verification of the GOOGL/`GOOG`-alias or SPWR findings** from
  the prior EC benchmark — read-only reuse only, per the ground rules.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/test7_score_fidelity.py').read())"`
  — passed, both before and after the tier-label fix.
- Step 0's version-match gate checked by direct field read against all 4
  Tier A cells' actual cached JSON (`analysis/test4_noise_floor/raw/{16,287,220,348}.json`),
  not assumed from Test 4's wrap-up text alone — confirmed `model` and
  `prompt_version_header` match exactly, all 4 cells.
- Step 1's EC file resolution verified by content (`resolve_ec_raw_path()`
  scans by `transcript_id` if the guessed filename is wrong) — all 8
  guessed filenames happened to be correct, confirmed by the printed path
  for each, not assumed.
- All 30 API responses' `stop_reason` = `end_turn` (no truncated
  responses), confirmed from the raw run output above — no partial or
  cut-off structured blocks entered the comparison.
- Token/cost totals read directly from `progress.json`'s running counters
  (`calls_made`, `input_tokens`, `output_tokens`), cross-checked against
  the sum of each individual call's logged tokens in the score-step output
  above (489,195 in / 88,030 out, matches).
- Every divergence and every borderline case in Step 3 was read from the
  actual `comparison_report.txt` value-sets quoted verbatim in this
  report, not summarized from memory.

## Wall-clock, cells run, cells reused

Fresh run, no prior state. Step 0 (check): <1s, 0 calls. Step 1 (build):
<1s, 0 calls (8 cells, all DB `SELECT`s + local JSON reads). Step 2
(score): 30 calls, ~2-3 minutes wall-clock (API latency dominated, no
artificial spacing needed — unlike the EarningsCall vendor calls, no rate
limit applies to Anthropic API calls at this volume). Step 3 (compare):
<1s, 0 calls. **7 cells scored this run** (4 Tier A EC-side-only + 3 Tier
B both-sides), **4 cells' DB-side reused from Test 4** (20 already-paid-for
runs, 0 new DB-side calls for Tier A). 30 total new calls, $2.79 estimated.

## Files written

- `analysis/test7_score_fidelity.py` (driver, adopted from a concurrent
  session, fixed, committed at `6ecb714`)
- `analysis/test7_score_fidelity/raw/{16,287,220,348}_ec.json`,
  `{370,154,249}_{db,ec}.json` (10 files, this run's new scoring output —
  not committed yet, pending this wrap-up's own commit)
- `analysis/data/run_state/test7-ec-score-fidelity/{progress.json,
  findings.md, comparison_report.txt}`

## Follow-up commands

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent/analysis"
python3 test7_score_fidelity.py compare              # regenerate the comparison report, 0 new calls
python3 test7_score_fidelity.py score --tier-c        # optional Tier C (GOOGL/GOOG), +6 calls, ~$0.55
```

To inspect any individual cell's raw runs directly:

```bash
python3 -c "
import json
d = json.load(open('analysis/test7_score_fidelity/raw/154_ec.json'))
for r in d['runs']:
    print(r['run_idx'], r['structured'].get('recommendedSize'), r['structured'].get('freshMoneyAllocation'))
"
```
