# av_transcript_fidelity_benchmark_2_stratified — wrap-up (Day 1 of ~10)

**Scope boundary: report, do not decide.** No commitment to a vendor, no
change to `DESIGN_PRINCIPLES.md`/`DOMAIN.md`, no Step 6 ingestion work
started. This run is explicitly multi-day (`run_id`
`av-fidelity-benchmark-2-stratified`) — this wrap-up will be updated in
place after each subsequent day's invocation and finalized only once
Step 2 (the aggregate report) can run.

---

## Resume status: Day 1 of an estimated ~10

Fresh run, no prior `run_state` for this `run_id`. Step 0 (draw) and one
day of Step 1 (fetch) are complete this session.

- **Calls used today: 20 / 20.** **Total calls used so far: 20.**
  **Total remaining in drawn sample: 180.** **Estimated remaining
  invocations: 9** (at ≤20 calls/day).
- 0 rate-limit errors. 0 coverage misses today. 0 samples dropped for
  missing DB text.

---

## Step 0 — the draw

Re-ran the pool-count query at execution time, per the prompt's
instruction not to trust the 2026-09-05 table blindly:

```sql
SELECT tk.symbol, COUNT(*) AS n, MIN(t."callDate")::date AS earliest, MAX(t."callDate")::date AS latest
FROM "Transcript" t
JOIN "Ticker" tk ON t."tickerId" = tk.id
WHERE tk.symbol IN ('MSFT','TSLA','AMPX','ENVX','AVGO','QS','RUN','EOSE','GOOGL','AMD','FSLR','AAPL','ORCL','NVDA','TTD')
GROUP BY tk.symbol
ORDER BY tk.symbol;
```

Per-ticker counts matched the prompt's table exactly (328 total across
the 14 tickers). Two issues surfaced during the draw itself, both
resolved before any AV call was made (per Step 4 of the standing
`execute-prompt` workflow — verify the premise before implementing):

### Flag 1 — quarter-label mapping bug (own derivation, not in the prompt)

The prompt names the exact SQL for the pool but doesn't specify how a DB
`callDate` maps to Alpha Vantage's `quarter` request parameter (e.g.
`2025Q1`). A first-draft heuristic (subtract 45 days from `callDate`,
take that date's calendar quarter) reproduced benchmark_1's three known
AMPX labels correctly, but **collapses two genuinely different quarters
onto the same label** whenever a company has both a Jan–Mar call
(reporting the *prior* year's Q4) and an Apr–Jun call (reporting the
*current* year's Q1) — confirmed present for FSLR, TTD, QS, ENVX, and
RUN, each of which reports Q4 in February and Q1 in April/May.

Replaced with a call-month bucket: Jan–Mar → prior-year Q4, Apr–Jun →
Q1, Jul–Sep → Q2, Oct–Dec → Q3. Re-validated against every known-correct
label from `av_transcript_fidelity_benchmark_1-out.md` and
`test3-transcript-ingestion-fidelity-out.md` (AMPX 2025-05-08/08-07/
11-06 → 2025Q1/Q2/Q3; EOSE 2025-05-06/07-31 → 2025Q1/Q2; SPWR
2025-04-30/10-21 → 2025Q1/Q3) — exact match on all seven. Caught and
fixed at Step 0, before spending any of the 200-call budget on a
mislabeled request.

### Flag 2 — one genuine DB-side duplicate row

FSLR transcript ids 280 and 284 are identical: same `callDate`
(2024-02-27), same title ("First Solar (FSLR) Q4 2023 Earnings Call
Transcript"), identical `rawText` length (57,254 chars). This is a real
corpus duplicate, not a quarter-mapping artifact — flagged here, not
fixed (no DB writes this run). Dropped the higher id (284) from the pool
so the draw doesn't spend two AV calls comparing against what is really
one DB transcript.

**Effect on the pool table** (mid tier loses 1 to the dedup; small/micro
recovers 2 relative to the buggy first draft, which had mis-collapsed
ENVX 2025Q1):

| Tier | Pool (re-verified) | Pool per prompt's 2026-09-05 table |
|---|---|---|
| Megacap | 114 | 114 |
| Large | 67 | 67 |
| Mid | **44** | 45 |
| Small/micro | 97 | 97 |
| **Total** | **322** | 323 |

Recomputed allocation per the prompt's own fallback rule ("cap any tier
at its actual available pool, spread the remainder evenly across the
others"):

| Tier | Draw target (this run) | Draw target (prompt's table) |
|---|---|---|
| Megacap | 53 | 52 |
| Large | 51 | 51 |
| Mid | 44 (full pool) | 45 |
| Small/micro | 52 | 52 |
| **Total** | **200** | 200 |

**Seed: `20260905`** (fixed, reported, deterministic — `random.Random(20260905)`,
per-tier shuffle then slice). Draw verified to contain **zero duplicate
(ticker, quarter) keys** after both fixes. Full 200-item drawn list is
in `analysis/data/run_state/av-fidelity-benchmark-2-stratified/progress.json`
(`drawn` key) and is not reproduced here for length — it is not
hand-picked, it is the seeded shuffle's output, checkable by re-running
`python3 analysis/av_fidelity_benchmark_2/driver.py draw` (idempotent;
does not re-fetch anything already in `progress.json["fetched"]`).

## Step 1 — Day 1 fetch

Ran `python3 analysis/av_fidelity_benchmark_2/driver.py fetch`: pulled
the first 20 unfetched items from the drawn list (all megacap, since the
draw's per-tier ordering happened to put megacap first), spaced ≥70s
apart (actual measured spacing ~70s, no auto-retry, no rate-limit
response encountered). Raw AV JSON saved to
`analysis/av_fidelity_benchmark_2/raw/<TICKER>_<QUARTER>.json` (20
files), mirroring Test 3/benchmark_1's layout.

**Decisive check run immediately per sample** (direct DB-vs-AV text
comparison, not deferred): sequence-matcher similarity ratio, AV speaker
turn count, closing-keyword match on both sides, and a handoff-phrase
check (does the AV transcript's last turn hand off to a named speaker
for closing remarks that never appear, as in Test 3's AMPX Q3 finding).

### Two classifier false positives caught and corrected before this report — 0 new AV calls spent

The automated classifier's first pass flagged **NVDA 2022Q3 truncated**
and **AAPL 2023Q1 possibly-truncated**. Direct text inspection (the same
method Test 3 used to confirm AMPX Q3) showed both are false positives:

- **NVDA 2022Q3**: AV's last turn contains the phrase "...turn over to
  Jensen for closing remarks. Well, I think we just heard the closing
  remarks. Thank you so much for joining us. ... Thanks again,
  everybody." — the handoff phrase is resolved **within the same turn**,
  not left dangling as in AMPX Q3. The classifier's handoff heuristic
  matched the phrase anywhere in the last turn; fixed to only fire when
  the phrase sits within the trailing 80 characters of the turn (i.e.
  nothing of substance follows it).
- **AAPL 2023Q1**: DB and AV both end word-for-word identically —
  *"...this does conclude today's conference. We do appreciate your
  participation."* — but the classifier's closing-keyword list only had
  "this concludes," not "does conclude," so it registered no AV-side
  match and defaulted to the manual-check bucket. Added "does conclude"
  and several other observed closing phrasings to the keyword list.

Reran `python3 analysis/av_fidelity_benchmark_2/driver.py reclassify`
(reuses the saved raw/ files, 0 new AV calls) — both samples now read
`summarized_but_complete`. Spot-checked two more low-ratio samples
(AAPL 2026Q2 ratio 0.0117, NVDA 2023Q2 ratio 0.0481) by direct tail-text
read; both end identically to their DB counterparts, confirming the
`summarized_but_complete` reading is not masking a genuine truncation —
low similarity ratio in this batch tracks mid-call paraphrasing, not a
missing ending.

### Day 1 results (all megacap — 20/20)

| Classification | Count |
|---|---|
| `matches_closely` | 3 |
| `summarized_but_complete` | 17 |
| `truncated` | 0 |
| coverage miss | 0 |

No truncated sample this batch — too early to read as a finding (only
one of four tiers has any data yet, and it's the tier the working
hypothesis predicts should have the *lowest* truncation rate). **This is
not evidence against the hypothesis, it's an empty draw from the
predicted-best tier** — held back explicitly per the prompt's "report
whichever way it goes" instruction; the actual test is the small/micro
tier's rate once its batch runs.

---

## Deviations from the prompt, and why

1. **Quarter-label mapping method** — not specified in the prompt at
   all; invented here, validated against both prior runs' known-correct
   labels before use, and corrected once (see Flag 1) before any AV call
   was spent on a bad label.
2. **Pool/allocation numbers differ from the prompt's 2026-09-05 table**
   (mid 44 vs 45, total 322 vs 323) — due to the genuine FSLR duplicate
   row (Flag 2), not new transcripts added since the table was written.
   Recomputed per the prompt's own explicit fallback rule.
3. **Two classifier corrections mid-run** (handoff-phrase and
   closing-keyword false positives) — caught by manual verification of
   every flagged truncated/possibly-truncated sample, as the prompt's
   own "decisive check" step requires. No AV budget was spent
   re-verifying — both corrections reused already-saved raw/ files.

## What was deliberately not done

- Step 2 (the aggregate report, Wilson CIs, coverage-miss rates by tier,
  pre-declared threshold reading) — explicitly gated on all 200 drawn
  items being processed. 180 remain.
- No LLM calls, no re-scoring, no DB writes this run (`SELECT` only, per
  Step -1/standing rules).
- No manual verification of the 17 `summarized_but_complete` samples not
  spot-checked above — the pattern (low ratio, identical or
  near-identical endings) is consistent enough across 4 checked samples
  (2 corrected + 2 spot-checked) that verifying all 17 individually
  would not be a good use of today's remaining time; flagged as a
  lighter-touch check than the "every flagged-truncated sample" the
  prompt requires for Step 2's final report, which will get full
  evidence citations for anything still flagged truncated at that point.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/av_fidelity_benchmark_2/driver.py').read())"` — passed, both
  before the initial run and after each fix.
- Per-ticker pool counts re-queried live and cross-checked against the
  prompt's 2026-09-05 table (exact match, 328 total, before dedup).
- Quarter-label heuristic validated against 7 known-correct labels from
  two prior wrap-ups before use (see Flag 1).
- Draw verified to contain zero duplicate `(ticker, quarter)` keys after
  both fixes (`analysis/data/run_state/.../progress.json["drawn"]`,
  200 items, checked programmatically).
- Both classifier corrections verified by direct `rawText` tail
  comparison (DB vs AV), not by re-trusting the mechanical checks alone
  — same standard Test 3 applied to AMPX Q3.
- `git status --short` before committing: only expected untracked files
  from concurrent sessions plus this run's own new files; nothing from
  `testing/` touched.

## Files written

- `analysis/av_fidelity_benchmark_2/driver.py` (driver, committed)
- `analysis/av_fidelity_benchmark_2/raw/*.json` (20 files, this run's AV
  responses — not committed; matches Test 3/benchmark_1's convention of
  not versioning raw API payloads)
- `analysis/data/run_state/av-fidelity-benchmark-2-stratified/{progress.json,
  cells.jsonl, findings.md}`

## Follow-up commands

Run once per day until the drawn sample (200 items) is exhausted
(~9 more invocations at ≤20 calls/day, ≥70s apart — each takes on the
order of 20-25 minutes wall-clock):

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
python3 analysis/av_fidelity_benchmark_2/driver.py fetch
```

Once all 200 are processed (fetched or recorded as a coverage miss):

```bash
python3 analysis/av_fidelity_benchmark_2/driver.py report
```

To re-run Day 1's classification without spending AV calls (uses saved
`raw/` files only):

```bash
python3 analysis/av_fidelity_benchmark_2/driver.py reclassify
```
