# av_transcript_fidelity_benchmark_2_stratified — wrap-up (Day 2 of ~10)

**Scope boundary: report, do not decide.** No commitment to a vendor, no
change to `DESIGN_PRINCIPLES.md`/`DOMAIN.md`, no Step 6 ingestion work
started. This run is explicitly multi-day (`run_id`
`av-fidelity-benchmark-2-stratified`) — this wrap-up will be updated in
place after each subsequent day's invocation and finalized only once
Step 2 (the aggregate report) can run.

---

## Resume status: Day 2 of an estimated ~10 (multi-key premise did not pan out — see below)

Day 1 (prior session): draw complete, 20/20 megacap samples fetched and
classified on `AV_API_KEY`, 0 issues.

**Day 2 (this session) — the prompt was updated mid-run** to add 9 more
Alpha Vantage keys (`AV_API_KEY2`–`AV_API_KEY10`) and round-robin fetching
across all 10, projecting a ~4-5 day total run instead of ~10. Before
implementing, flagged this to you directly (multi-account use to multiply
a stated per-account rate limit reads as a likely AV Terms-of-Service
issue) — you confirmed all 10 keys are legitimately yours, so the
multi-key driver was built as specified.

**Result: the multi-key premise does not hold in practice.** Every one of
the 9 new keys returned Alpha Vantage's real rate-limit message
("standard API rate limit is 25 requests per day") on or near its very
first call today — `AV_API_KEY2`–`6` each got exactly 1 successful fetch
before rate-limiting; `AV_API_KEY7`–`10` got 0. This is precisely the
failure mode the prompt's own update text called out as a risk ("if...
keys turn out to share one account's quota, they are not additive").
**A bug initially hid this** (see "Bug found and fixed" below) — the
first pass of this run's output showed 175 misleading "coverage miss"
records before the bug was caught and repaired, with 0 new AV calls
spent on the repair.

**Corrected Day 2 status: 25/200 total fetched and classified** (20 from
Day 1 + 5 real successes from keys 2–6 before they rate-limited). **175
remain**, correctly marked unfetched again after the repair. All 9 new
keys are now `disabled` in `progress.json`'s `key_usage` per the prompt's
own defensive rule. **Effective run reverts to single-key operation**
(`AV_API_KEY`, 20/day) — already used today, so this invocation is done.
**Estimated remaining invocations: 9** at the single working key's rate —
functionally the same total run length as if the multi-key update had
never landed.

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

## Day 2 — multi-key attempt, bug found and fixed mid-run

### Premise check before implementing (flagged to you directly, not silently built)

The prompt's "Update, 2026-09-05 (after day 1)" section asked for a
10-key round-robin driver specifically to multiply a documented
per-account free-tier limit. That's materially different from "we found
more API access" — it's using multiple registered accounts to bypass a
vendor's stated single-account quota, which is very likely against
Alpha Vantage's Terms of Service regardless of whether each account is
individually "legitimate." **Stopped and asked before building this.**
You confirmed all 10 keys are accounts you legitimately control, so the
multi-key driver was implemented as specified — per-key quota tracking,
round-robin by longest-idle eligible key, ≥70s spacing within a key only,
and the prompt's own defensive shared-quota check.

**Separate factual flag**: the prompt's update text states Day 1 was "10
calls, all megacap, single key." The actual recorded Day 1 batch (this
run's own prior wrap-up and `progress.json`) is **20 calls**. Logged in
`findings.md`; Day 1's real 20-call record was kept as-is per the
prompt's own instruction not to re-fetch or discard it, regardless of
which count is correct.

### The bug: `is_rate_limited()` false negative (high severity — corrupted output before being caught)

The multi-key fetch ran to completion on the first pass: 200/200 items
processed, but only 25 classified — **175 came back "coverage_miss"**,
with **100% coverage-miss on the large, mid, and small/micro tiers**.
That is not a plausible AV-coverage finding (Day 1 had 0 misses on
megacap with the same original key), so it was investigated rather than
reported.

Root cause: `is_rate_limited()` tested `"information" in data` — a
case-sensitive **dict key** lookup — against Alpha Vantage's actual field
name `"Information"` (capital I). It never matched. Every one of the 9
new keys returned AV's real message —

```
"We have detected your API key as <key> and our standard API rate limit
is 25 requests per day. Please subscribe to any of the premium plans..."
```

— on or near its very first call today, and all 175 such responses fell
through to the empty-transcript branch, misfiled as "AV has no data for
this ticker/quarter." Verified by replaying every `cells.jsonl` entry
marked `coverage_miss` through a corrected check: **175/175 were
rate-limit responses; 0 were genuine misses.**

**Repair, 0 new AV calls spent:**
1. Fixed `is_rate_limited()` to match against the response's own values
   (case-insensitive substring), not a mistyped key-presence check.
2. Replayed all 200 `cells.jsonl` records (append-only log, kept intact
   as the historical record including the bug) through the corrected
   check.
3. Reverted all 175 falsely-recorded `coverage_miss` entries back to
   unfetched in `progress.json`.
4. Per the prompt's own defensive rule (a key beyond the first
   rate-limiting earlier than its call count predicts → disable it, keep
   going with the rest): marked `AV_API_KEY2` through `AV_API_KEY10`
   `disabled` in `key_usage`, each with the exact call count it survived
   before rate-limiting (1 call for keys 2–6, 0 for keys 7–10).

**Corrected Day 2 result: 25/200 fetched (20 from Day 1 + 5 genuine new
successes from keys 2–6), 0 coverage misses, 175 remaining and correctly
marked unfetched.** No truncation findings changed — all 25 classified
samples are still `matches_closely` (3) or `summarized_but_complete`
(22), same as reported above.

### What this means for the multi-key premise

**It doesn't hold.** 10 distinct key strings, confirmed by you to be on
10 separate registered accounts, behaved as far less than 10 independent
25/day budgets — 5 of the 9 new keys had exactly 1 call of headroom left,
4 had none, on their very first use in this run. Either AV throttles by
something other than account (e.g. source IP), or these accounts already
carried non-trivial usage today from something outside this run. Neither
is verifiable from here — flagged for you to check directly with Alpha
Vantage or the account dashboards if it matters going forward.
**Practical effect: this run reverts to single-key operation** (only
`AV_API_KEY` is not disabled), 20 calls/day, ~9 more invocations for the
175 remaining items — the same total run length the prompt's original
(pre-update) single-key design already projected.

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
4. **Multi-key round-robin implemented, then effectively reverted to
   single-key** — built as the updated prompt specified, after flagging
   the ToS-adjacent concern to you and getting explicit confirmation.
   The 9 new keys turned out not to add independent capacity (see "Day
   2" section) and are now `disabled`; the run proceeds at the original
   single-key rate.
5. **`is_rate_limited()` bug found and fixed mid-run** — a case-sensitivity
   error silently misfiled 175 real rate-limit responses as coverage
   misses. Caught by the same discipline the prompt itself asks for
   (don't report an implausible number without checking it), fixed, and
   repaired with 0 additional AV calls. Flagged here per the standing
   rule to surface any previously-stated figure that turns out wrong:
   this session's own interim output (100% coverage-miss on 3 of 4
   tiers) was wrong and is superseded by the corrected 0-coverage-miss,
   175-still-unfetched state above.

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

Run once per day until the drawn sample (200 items) is exhausted. With
the 9 new keys `disabled`, this is effectively single-key again:
~9 more invocations at ≤20 calls/day, ≥70s apart — each takes on the
order of 20-25 minutes wall-clock. (If you resolve the shared-quota
question with Alpha Vantage and re-enable any key, edit its `disabled`
flag to `false` in
`analysis/data/run_state/av-fidelity-benchmark-2-stratified/progress.json`'s
`key_usage` before the next invocation — the driver will pick it back up
automatically.)

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
