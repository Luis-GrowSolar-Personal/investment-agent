# Findings — test4-analyst-noise-floor

(append-only)

- Checkpoint: transcript 212 (MSFT 2020-10-27, tier megacap) 5/5 runs complete. Running total: 1/50 transcripts, 98938 tokens so far.

- Checkpoint: transcript 141 (MSFT 2024-10-30, tier megacap) 5/5 runs complete. Running total: 2/50 transcripts, 201730 tokens so far.

- Checkpoint: transcript 204 (MSFT 2023-01-24, tier megacap) 5/5 runs complete. Running total: 3/50 transcripts, 303784 tokens so far.

## Scoring complete (50/50, resumed twice after OS-level low-memory kills of the
background process; per-transcript checkpointing meant zero lost calls beyond
whatever was in-flight at kill time). Total: 4,794,618 tokens (4,045,405 in /
749,213 out) across 250 calls. Model: claude-sonnet-4-6 (bare alias, matches
`server/lib/versions.js` exactly). Prompt header: "v10+auto1 (auto-iterate
candidate — pending gate)" — NOT v6, confirmed by direct file read, exactly
as Test 3 and the pilot already flagged.

## Step 3 — field stability
Primary 4-field instability: 39/200 (19.5%) — very close to v6's historical
21.4% (18/84), far below v9's 69.0%. **Caveat, load-bearing**: this run used
v10+auto1 + claude-sonnet-4-6, not v6's original prompt+model combination, so
"closer to v6" is a numerical proximity, not a validated apples-to-apples
reproduction — flag explicitly, do not imply v10+auto1 = v6's stability.

Recommendation flips: 11/50 (22.0%) transcripts had `recommendation` vary
across the 5 runs — comparable to v6's ENPH-only 5/21 (23.8%). **3 of the 11
are 3-way-or-more splits** (genuinely 3 distinct values across 5 runs, not
just a 2-way flip): id 175 ENVX (Add/Add/Hold/Hold/Trim), id 193 EOSE
(Trim/Trim/Add/Trim/Hold), id 204 MSFT (Hold/Hold/Trim/Hold/Add). MSFT (id
204, megacap) is notable — 3-way instability is not confined to small/micro
names.

Flip distribution by tier (from raw per-sample inspection, not just the
aggregate 22%): small_micro 7/12 (58%), megacap 2/13 (15%), mid 1/12 (8%),
**large 0/13 (0%)** — recommendation instability is drastically concentrated
in small/micro names, consistent with the AV-fidelity benchmark's own
hypothesis about coverage/follower depth.

Noisiest fields at this scale (all-15-field census): `freshMoneyAllocation`
98% of transcripts unstable, `recommendedSize` 96%, `activeDriverCount` 66%,
`mitigationCapabilityTrackRecord` 44% — confirms benchmark_1's flag on the
last of these at n=50 rather than n=7. `credibilityDelta` only 12% here
(benchmark_1 flagged it from n=7, likely noise in that small sample) and
`blindSpotsTriggered` 0% (never varied in 50 transcripts x 5 runs) —
**refutes** benchmark_1's flag on that field at this larger scale.

## Step 4 — noise floor
Aggregate: std 2.65pp, range 8.0pp across the 5 independent hit-rate values
(50 transcripts each) — SMALLER than gate_ledger.json's 4.2pp bootstrap
figure.

**By tier — the aggregate figure conceals enormous heterogeneity**:
- large: std 0.0pp, range 0.0pp (perfectly stable — zero recommendation
  flips landed in this tier's 13-transcript sample)
- mid: std 0.0pp, range 0.0pp (1 recommendation flip present, FSLR id 100,
  but it did not change the hit/miss outcome against ground truth)
- megacap: std 3.77pp, range 7.69pp
- **small_micro: std 14.34pp, range 41.67pp** — over 3x the gate's own 4.2pp
  threshold, and the same order of magnitude as the -7.44pp regression
  itself.

**This is the load-bearing finding for Step 5.** The original gate_ledger
entry 1 scoped to ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR — overwhelmingly
small/micro-cap-like speculative names, i.e. much closer to this run's
small_micro tier than to the aggregate ALL-tier figure. Judged against the
aggregate noise floor (2.65pp), -7.44pp clearly exceeds noise. Judged
against the tier-matched noise floor (14.34pp std) that better reflects the
ledger's actual scope, -7.44pp sits well inside one standard deviation of
observed noise for that kind of name and does NOT clearly exceed it. Report
both readings; do not pick one.

- Checkpoint: transcript 156 (AAPL 2022-01-27, tier megacap) 5/5 runs complete. Running total: 4/50 transcripts, 392684 tokens so far.

- Checkpoint: transcript 297 (GOOGL 2024-01-30, tier megacap) 5/5 runs complete. Running total: 5/50 transcripts, 487564 tokens so far.

- Checkpoint: transcript 113 (GOOGL 2025-04-24, tier megacap) 5/5 runs complete. Running total: 6/50 transcripts, 582159 tokens so far.

- Checkpoint: transcript 220 (TSLA 2022-10-19, tier megacap) 5/5 runs complete. Running total: 7/50 transcripts, 678855 tokens so far.

- Checkpoint: transcript 224 (TSLA 2021-10-20, tier megacap) 5/5 runs complete. Running total: 8/50 transcripts, 777738 tokens so far.

- Checkpoint: transcript 303 (GOOGL 2022-10-25, tier megacap) 5/5 runs complete. Running total: 9/50 transcripts, 873268 tokens so far.

- Checkpoint: transcript 52 (AAPL 2025-01-30, tier megacap) 5/5 runs complete. Running total: 10/50 transcripts, 967034 tokens so far.

- Checkpoint: transcript 46 (TSLA 2025-10-22, tier megacap) 5/5 runs complete. Running total: 11/50 transcripts, 1068675 tokens so far.

- Checkpoint: transcript 315 (NVDA 2022-05-25, tier megacap) 5/5 runs complete. Running total: 12/50 transcripts, 1164290 tokens so far.

- Checkpoint: transcript 114 (GOOGL 2025-02-04, tier megacap) 5/5 runs complete. Running total: 13/50 transcripts, 1263718 tokens so far.

- Checkpoint: transcript 132 (ORCL 2025-06-10, tier large) 5/5 runs complete. Running total: 14/50 transcripts, 1345264 tokens so far.

- Checkpoint: transcript 336 (ORCL 2023-03-09, tier large) 5/5 runs complete. Running total: 15/50 transcripts, 1428978 tokens so far.

- Checkpoint: transcript 240 (AMD 2023-10-31, tier large) 5/5 runs complete. Running total: 16/50 transcripts, 1530954 tokens so far.

- Checkpoint: transcript 331 (ORCL 2024-06-11, tier large) 5/5 runs complete. Running total: 17/50 transcripts, 1613764 tokens so far.

- Checkpoint: transcript 266 (AVGO 2021-09-02, tier large) 5/5 runs complete. Running total: 18/50 transcripts, 1694250 tokens so far.

- Checkpoint: transcript 120 (AMD 2025-02-04, tier large) 5/5 runs complete. Running total: 19/50 transcripts, 1792065 tokens so far.

- Checkpoint: transcript 131 (ORCL 2025-09-09, tier large) 5/5 runs complete. Running total: 20/50 transcripts, 1873767 tokens so far.

- Checkpoint: transcript 258 (AVGO 2023-06-01, tier large) 5/5 runs complete. Running total: 21/50 transcripts, 1959225 tokens so far.

- Checkpoint: transcript 264 (AVGO 2022-03-03, tier large) 5/5 runs complete. Running total: 22/50 transcripts, 2047613 tokens so far.

- Checkpoint: transcript 343 (ORCL 2021-09-13, tier large) 5/5 runs complete. Running total: 23/50 transcripts, 2119862 tokens so far.

- Checkpoint: transcript 255 (AVGO 2024-06-12, tier large) 5/5 runs complete. Running total: 24/50 transcripts, 2211346 tokens so far.

- Checkpoint: transcript 344 (ORCL 2021-03-10, tier large) 5/5 runs complete. Running total: 25/50 transcripts, 2289395 tokens so far.

- Checkpoint: transcript 338 (ORCL 2022-09-12, tier large) 5/5 runs complete. Running total: 26/50 transcripts, 2371163 tokens so far.

- Checkpoint: transcript 230 (TTD 2023-08-09, tier mid) 5/5 runs complete. Running total: 27/50 transcripts, 2481164 tokens so far.

- Checkpoint: transcript 292 (FSLR 2022-03-01, tier mid) 5/5 runs complete. Running total: 28/50 transcripts, 2600011 tokens so far.

- Checkpoint: transcript 284 (FSLR 2024-02-27, tier mid) 5/5 runs complete. Running total: 29/50 transcripts, 2704694 tokens so far.

- Checkpoint: transcript 238 (TTD 2021-05-10, tier mid) 5/5 runs complete. Running total: 30/50 transcripts, 2818254 tokens so far.

- Checkpoint: transcript 287 (FSLR 2023-02-28, tier mid) 5/5 runs complete. Running total: 31/50 transcripts, 2925971 tokens so far.

- Checkpoint: transcript 100 (FSLR 2025-02-25, tier mid) 5/5 runs complete. Running total: 32/50 transcripts, 3046285 tokens so far.

- Checkpoint: transcript 36 (TTD 2025-02-12, tier mid) 5/5 runs complete. Running total: 33/50 transcripts, 3157931 tokens so far.

- Checkpoint: transcript 285 (FSLR 2023-07-27, tier mid) 5/5 runs complete. Running total: 34/50 transcripts, 3256218 tokens so far.

- Checkpoint: transcript 233 (TTD 2022-08-09, tier mid) 5/5 runs complete. Running total: 35/50 transcripts, 3365965 tokens so far.

- Checkpoint: transcript 34 (TTD 2024-08-08, tier mid) 5/5 runs complete. Running total: 36/50 transcripts, 3467100 tokens so far.

- Checkpoint: transcript 234 (TTD 2021-08-09, tier mid) 5/5 runs complete. Running total: 37/50 transcripts, 3580108 tokens so far.

- Checkpoint: transcript 239 (TTD 2022-11-09, tier mid) 5/5 runs complete. Running total: 38/50 transcripts, 3693003 tokens so far.

- Checkpoint: transcript 23 (EOSE 2025-07-31, tier small_micro) 5/5 runs complete. Running total: 39/50 transcripts, 3791785 tokens so far.

- Checkpoint: transcript 348 (QS 2024-04-24, tier small_micro) 5/5 runs complete. Running total: 40/50 transcripts, 3860734 tokens so far.

- Checkpoint: transcript 193 (EOSE 2022-02-25, tier small_micro) 5/5 runs complete. Running total: 41/50 transcripts, 3967086 tokens so far.

- Checkpoint: transcript 355 (QS 2022-10-26, tier small_micro) 5/5 runs complete. Running total: 42/50 transcripts, 4038688 tokens so far.

- Checkpoint: transcript 172 (ENVX 2023-11-07, tier small_micro) 5/5 runs complete. Running total: 43/50 transcripts, 4127251 tokens so far.

- Checkpoint: transcript 170 (ENVX 2024-05-01, tier small_micro) 5/5 runs complete. Running total: 44/50 transcripts, 4224247 tokens so far.

- Checkpoint: transcript 16 (AMPX 2025-08-07, tier small_micro) 5/5 runs complete. Running total: 45/50 transcripts, 4310045 tokens so far.

- Checkpoint: transcript 169 (AMPX 2023-03-23, tier small_micro) 5/5 runs complete. Running total: 46/50 transcripts, 4381938 tokens so far.

- Checkpoint: transcript 173 (ENVX 2023-07-26, tier small_micro) 5/5 runs complete. Running total: 47/50 transcripts, 4493225 tokens so far.

- Checkpoint: transcript 168 (AMPX 2023-05-10, tier small_micro) 5/5 runs complete. Running total: 48/50 transcripts, 4568202 tokens so far.

- Checkpoint: transcript 175 (ENVX 2023-02-22, tier small_micro) 5/5 runs complete. Running total: 49/50 transcripts, 4671857 tokens so far.

- Checkpoint: transcript 186 (EOSE 2023-11-07, tier small_micro) 5/5 runs complete. Running total: 50/50 transcripts, 4794618 tokens so far.
