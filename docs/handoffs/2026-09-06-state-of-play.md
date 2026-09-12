# State of Play — 2026-09-06

**Supersedes** `docs/handoffs/2026-09-05-state-of-play.md` on §7 (test plan)
and §8 (open items) only. §§0–6 of that document — the settled allocator
configuration, the ruler discovery, Test 1, the five resolved questions, the
corpus archive — are unchanged and not repeated here. **Read that document
first**, then this one.

**Branch:** `sweep/db-corpus-baseline` (unchanged)
**Read first on return:** §7 (test plan, materially changed), then the AV
benchmark section (a parallel workstream, not one of the six numbered tests),
then §8 (open items).

---

## 7. Test plan — status update

| # | Test | Status |
|---|---|---|
| 1 | Analyst-quality sensitivity | **COMPLETE** — 09-05 §4, unchanged |
| 2 | Hit rate by year | **COMPLETE** — inconclusive by design, see below |
| 3 | Transcript ingestion fidelity | **COMPLETE** — corpus clean, one confirmed AV defect, see below |
| 4 | Analyst noise floor | **IN PROGRESS** — real API spend, see below |
| 5 | Universe substitution | **Prompt written, not yet run** — corrects a factual error in the original spec, see below |
| 6 | Look-ahead prohibition probe | Blocked by 4 (3 is cleared) |

### Test 2 — complete, inconclusive by design, low priority to revisit

Source: `wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`. Hit rate by
year, 2021–2025: **55.6% / 26.8% / 38.3% / 29.8% / 50.0%** — non-monotonic,
no decline toward the training cutoff. Fails the prompt's own pre-declared
"flat or declining" test for look-ahead evidence in either direction.

**Recorded characterization (agreed with the user):** tabled as
**inconclusive**, low priority to re-characterize. The limited evidence
available leans toward "little if any look-ahead," but the swing between
years is large enough that this is a weak read, not a confident one — see
09-05 §7's own note that a flat/non-declining result here is weak evidence,
not strong, given `sonnet-4-20250514`'s cutoff sits well past this corpus.

### Test 3 — complete, corpus clean, one confirmed AV defect (not two false alarms)

Source: `wrap-ups/test3-transcript-ingestion-fidelity-out.md`,
`analysis/test3_transcript_fidelity.py`. Split into Q1 (DB corpus integrity,
zero cost) and Q2 (AV viability, secondary), per this session's own reframing
of the original pilot's ambiguous finding.

- **Q1 — DB integrity: clean.** 0/337 ALL16 transcripts flagged for
  truncation or corruption.
- **Q2 — AV viability:** of the original pilot's three anomalies
  (`wrap-ups/av_transcript_fidelity_benchmark_1-out.md`), only **one is
  real**. **AMPX Q3 confirmed truncated** — AV's JSON cuts before the DB
  version's closing remarks and operator sign-off. **SPWR Q1/Q3 and EOSE
  Q2 confirmed NOT truncated** — the pilot's crude text-similarity-ratio
  proxy flagged them, but direct text comparison shows DB and AV end
  identically; the low ratios track paraphrasing density, not missing
  content. SPWR's case is a genuine "no operator sign-off" convention,
  unrelated to its April 2025 name change (a hypothesis this test
  specifically ruled out).

**This clears the prerequisite Tests 4, 5, and 6 were blocked on** — the
09-03 concern that "if transcripts are truncated, every score is corrupt at
the source" applies to AV, not to the DB corpus everything else is built on.

### Test 4 — in progress, real Anthropic API spend, no headline figure yet

Source: `analysis/data/run_state/test4-analyst-noise-floor/`, run_id
`test4-analyst-noise-floor`, driver commit `3c689a7`. User explicitly
approved this as a real-cost run before Step 0 began.

Design: 50 transcripts drawn by stratified rule across the four cap tiers
from the DB corpus (not ENPH, unlike the two historical Step 0 precedents
in `MODEL_SELECTION_BENCHMARK_SPEC.md`), scored 5 fresh times each = 250
evaluator calls, no DB writes. Extends `PROMOTION_GATE.md` §6's noise-floor
requirement, and is meant to supersede `gate_ledger.json` entry 1's weaker
bootstrap-over-tickers proxy (`noise_std_pp: 4.2`) with genuine
repeat-scoring on identical input.

**Status as of this writing: 29/50 transcripts scored (5 runs each),
checkpointing normally, no signs of being stuck.** Do not quote a
noise-floor figure until Step 4/5 complete — none exists yet. Two live
version-discipline issues are being tracked through this run rather than
fixed: `server/lib/versions.js` pins a bare/undated model alias
(`claude-sonnet-4-6`), and `docs/EVALUATION_PROMPT.md` on disk is
`v10+auto1`, not the `v6` `versions.js` claims — this run's result will
describe v10+auto1's behavior and must be reported as such, not as v6's.

### Test 5 — prompt written, not yet run; corrects a factual error in its own spec

Prompt: `prompts/test5-universe-substitution.md`. Cost: **$0** in Anthropic
API spend — AMZN, META, V, and JNJ are already scored back to 2021
(confirmed by the user), so this is a pure re-run of the existing backtest
simulator over already-scored data, the same cost profile as Test 1.

**Correction made during this design session, recorded here because the
09-03 spec (§7) got it wrong and a future reader should not silently trust
the original framing:** 09-03 claimed Arm B ("the eight largest S&P names
as of Jan 2021, by rule") overlaps the current established 8
(AAPL/AMD/AVGO/GOOGL/MSFT/NVDA/ORCL/TSLA) in five names, reducing to a
three-name swap with NVDA staying fixed. **Verified false** — NVIDIA
ranked 15th by year-end-2020 S&P 500 market cap (~$323B), not top 8. The
actual top 8 were Apple, Microsoft, Amazon, Alphabet, Meta, Tesla,
Berkshire Hathaway, and Visa; Berkshire has no earnings-call transcript to
score and is excluded, consistent with `analysis/audit_top20_2021.py`'s
own pre-existing `EXPECTED` list, landing on Johnson & Johnson (rank 9)
as the eighth name.

**Corrected Arm B: AAPL, MSFT, AMZN, GOOGL, META, TSLA, V, JNJ** — a
**four**-name swap against Arm A (AMD/AVGO/NVDA/ORCL out; AMZN/META/V/JNJ
in), not three. NVDA remains in Arm A only — Arm A is the real,
already-deployed portfolio and is not adjusted for this test (adjusting it
would answer a different question than the one being asked; see the
prompt's own framing).

The prompt requires reproducing Test 1's zero-information floor
($120,800, `wrap-ups/analyst-sensitivity-out.md`) on the unmodified
universe before trusting Arm B's number, and explicitly steers away from
the **stalled, unrelated** `run-allocator-sweep-db-corpus` pipeline
(`wrap-ups/run-allocator-sweep-db-corpus-out.md`: baseline never
reproduced, $110k vs. a $287k reference, stopped at Step 1) — a different
loader path built around `sync_trend_to_db.py`'s live-recomputed
tier/trajectory fields, not the one Test 1 and Test 5 both use.

### Test 6 — still blocked

Needs Test 4's noise floor as its own detection threshold, per 09-03 §7 —
"a one-sentence prompt change cannot be detected against a background where
the score moves on its own." Unblocks once Test 4 reports a number.

---

## AV transcript fidelity benchmark (stratified) — parallel workstream, in progress

Not one of the six numbered tests — a separate track evaluating whether
Alpha Vantage's `EARNINGS_CALL_TRANSCRIPT` API could replace hand-copied
transcripts as an ingestion source (a Step 6 build item, `BUILD_STATE.md`).
Prompt: `prompts/av_transcript_fidelity_benchmark_2_stratified.md`, run_id
`av-fidelity-benchmark-2-stratified`.

**Design:** 200 transcripts, stratified across the same four cap tiers,
drawn from the existing 14-ticker DB corpus (excludes SPWR — the
stratification pool was built before SPWR's inclusion was settled;
revisit if it matters). Free-tier AV rate limit is the real constraint
(25 calls/day/account, ~20 used defensively).

**Progress: 25/200 fetched and classified** (20 day 1, 5 day 2). **Zero
truncations found so far** — too early to read as a finding; the sample
so far is concentrated in the megacap and large tiers, which the working
hypothesis (fidelity degrades on smaller/less-followed names) predicts
should look cleanest. The real test is the small/micro tier's rate, not
yet drawn. 175 remain.

**Multi-key attempt did not pan out.** The user obtained 9 additional AV
API keys (10 total, on 10 separately registered accounts by his
confirmation) after day 1, hoping to round-robin across independent
25/day quotas. The driver was rewritten to do so, after flagging the
ToS-adjacent question directly and getting confirmation to proceed.
**Result: 5 of the 9 new keys got exactly 1 successful call before
hitting AV's real rate-limit response; the other 4 got 0.** Cause
undetermined from here — either AV throttles by something other than
account (e.g. IP), or the accounts already carried usage from something
else today. Effective outcome: the run reverts to single-key operation,
~9 more daily invocations at 20 calls/day, the same total timeline as if
the multi-key attempt had never been made.

**A real bug was caught and fixed before it corrupted the report.**
`is_rate_limited()` had a case-sensitive dict-key check for `"information"`
against AV's actual field `"Information"` — never matched. All 175
rate-limit responses from the 9 new keys were silently misfiled as
`coverage_miss` ("AV has no data for this ticker/quarter"), which would
have reported a false ~87.5% coverage-miss rate on three of four tiers.
Caught because that number was implausible next to day 1's 0% miss rate
on the same corpus with the original key; fixed and repaired via replay
of the append-only call log, at zero additional AV-call cost. Two smaller
$0-cost catches in the same run: a quarter-label date-mapping heuristic
that would have collapsed distinct quarters for five tickers
(FSLR/TTD/QS/ENVX/RUN), and one genuine duplicate DB row (FSLR ids
280/284) that had inflated the mid-tier pool count by one (322 actual,
not 323).

**Mechanically:** run once/day, `python3
analysis/av_fidelity_benchmark_2/driver.py fetch`. Step 2 (the aggregate
report — Wilson CIs, coverage-miss rates by tier, the pre-declared
threshold reading) is gated on all 200 items being processed or recorded
as a coverage miss; do not run it early.

---

## Sizing-channel sensitivity — complete, $0, and it closes a gap Test 1 left

Source: `wrap-ups/sizing-channel-sensitivity-out.md`, run_id
`sizing-channel-sensitivity`, driver commit `ef63a52`. Follow-on to Test 1
and Test 4, prompted by this finding: state-of-play §5.2 says the analyst's
entire contribution is *sizing*, Test 1 never perturbed the sizing field
(its harness explicitly leaves `recommended_size` untouched), and Test 4
found that field to be the least stable thing it measured (96% of
transcripts vary run-to-run; median per-transcript std ~3.07pp, spreads to
22pp).

**Result: at the measured noise magnitude, the sizing channel costs $0.**
Control reproduced Test 1's $179,944.91 exactly. Every perturbation cell —
jitter at 0.5x/1x/2x the measured noise, systematic +1σ/−1σ bias, the field
deleted entirely (`size_ignored`, always take the cap), the field replaced
with one constant — tied control **to the cent** across all 15 seeds. Only
`jitter_3x` deviated at all, by $428 (0.24%) on a single seed. Compare Test
1's recommendation channel: $24,886 at the −7.44pp shock.

**Mechanism (confirmed by direct code trace, and stronger than the prompt
anticipated):** at `X`=2.5pp/session, realized position weight almost never
converges close enough to *any* target within a quarter for the target's
value to matter — the binding constraint is the session limit or available
cash, not the target ceiling. `recommendedSize` is therefore not merely
noisy-but-absorbed; **its numeric value is very nearly inert at this X
setting.** The channel does have real potential sensitivity — forcing every
Add to `size=5.0` costs $38,913 — but only in the regime where the target
falls *below* an already-accumulated position, which the measured noise
never reaches from above. Latent falsy-zero defect (`None` and `0.0` both
fall through to the full cap) confirmed **not live**: 0 nulls, 0 zeros
across 137 Add events. Recorded, not patched.

**Two caveats this project should carry forward, neither in the wrap-up:**

1. **The $0 result was measured on v6-era corpus scores, whose sizing
   distribution does not match what production now emits.** Corpus Add
   events: median `recommendedSize` **45**, range 8–60, 48% already above
   cap. Test 4's fresh scoring under the live prompt+model (v10+auto1 /
   `sonnet-4-6`): median **18**, range 3–40, 94% below 35, none above the
   Type-B cap. The $0 finding depends on perturbed targets landing at or
   above the pre-corruption target; the current model's much lower sizes
   sit materially closer to the one regime that *did* cost money. **The
   conclusion is established for v6-era scores, not for what is being
   emitted today.** Separately, a systematic halving of recommended size is
   invisible to the promotion gate's direction-based hit-rate metric by
   construction.
2. **The wrap-up's own §9 follow-on suggestion is inverted.** It proposes
   testing whether a *lower* `X` (1.0) would let sizing noise express
   itself more. Lower `X` means smaller per-session steps and slower
   convergence, so the target would matter *less*. Raising `X` is what
   would make the target bind. Do not carry that suggestion forward as
   written.

**Structural fact worth recording:** no `Add` event in this corpus is
Type-A-established, so the 35% established cap is never exercised — every
"established" name is Type B on the flat 50% cap. The pre-registered tier
prediction (established more sensitive than speculative, because cap
headroom lets noise express) held in *mechanism* (Type-B is ~26x more
sensitive than Type-A-speculative under an identical extreme shock) but
never materialized at the measured noise level.

## 8. Open items — additions to 09-05 §8

09-05 §8's list stands; add:

- **`ESTABLISHED`/`SPECULATIVE` ticker-list constant is copy-pasted
  verbatim across at least 15 files in `analysis/`** (confirmed by grep
  during Test 5's design), rather than defined once and imported. Test
  5's Step 0 checks for drift before trusting its result, but the
  duplication itself is worth fixing at the source regardless of that
  test's outcome — it is exactly the kind of silent-drift risk this
  project has already been burned by once (the `PROMPT_VERSION`/
  `versions.js` drift).
- **Once Test 4 completes**, reconcile `gate_ledger.json` entry 1's
  `noise_std_pp: 4.2` (a weaker bootstrap-over-tickers proxy, per
  `PROMOTION_GATE.md` §10) against Test 4's genuine repeat-scoring noise
  floor. Report, do not re-adjudicate the existing HOLD verdict without a
  separate decision.
- **Backlog — noise-adjusted position caps (study, not yet designed).**
  Test 4 established that score instability is strongly tier-dependent
  (small/micro 14.34pp std vs 0.0pp for large and mid). The open question
  is whether *varying the concentration cap by a name's measured score
  noise* — a noisier verdict earns a smaller cap — produces any measurable
  improvement in final value or drawdown. `allocator_v4.py` already
  implements this shape of thing for a different uncertainty signal (low
  analyst coverage / high target dispersion → smaller cap), so the
  mechanism exists and would be extended rather than invented.
  **Constraint discovered by the sizing-channel run, which any such design
  must respect: the uncertainty signal must act on the cap, the starter
  percentage, or an exclusion rule — NOT on `recommendedSize`, which is
  inert at X=2.5pp.** Cost profile: 5x scoring calls on the small/micro
  tier only (a minority of the corpus) to measure per-name dispersion,
  plus $0 simulator re-runs to evaluate. Not scheduled.
- **AV's real throttling mechanism is unresolved** (per-account vs.
  per-IP vs. pre-existing account usage) and not diagnosable from inside
  a Code CLI session — would need the user to check Alpha Vantage's
  account dashboards or contact support directly if the multi-key
  approach is worth pursuing further. Not blocking — the benchmark
  proceeds at single-key pace regardless.
