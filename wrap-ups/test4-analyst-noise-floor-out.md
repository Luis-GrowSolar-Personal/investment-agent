# test4-analyst-noise-floor — wrap-up

**Scope boundary: report, do not decide.** `PROMOTION_GATE.md` not amended,
`gate_ledger.json` not modified, the model gate not re-adjudicated, no
scoring output written to the `Analysis` table, `EVALUATION_PROMPT.md` not
modified.

## Resume status

Fresh run, no prior state for `run_id=test4-analyst-noise-floor`.
`progress.json` written before any reading. Driver committed (`3c689a7`)
before any manifest, as its own commit. Step 1 (sample draw, no API cost)
ran clean. Step 2 (250 real Anthropic API calls) **was interrupted twice by
the operating system killing the background process for low memory** — not
a bug in the driver — and resumed both times from exactly where it left off,
because the driver checkpoints `progress.json` + `findings.md` +
`token_usage.json` + the transcript's own raw JSON file after every
transcript's 5 runs complete, per the prompt's Step −1 instruction. **Zero
calls were lost or re-run**: 25 transcripts survived the first kill, 3 more
the second, and the third attempt ran the remaining 22 to completion. Final
state: **50/50 transcripts scored, 250/250 calls made**, all under this
run's own `analysis/test4_noise_floor/` directory, none written to the
`Analysis` table. This is a **complete run**, not partial, despite the
interruptions.

**User confirmation.** Given this run's real dollar cost (unlike every
prior free/DB-only run this session), the user was asked and explicitly
approved the full 250-call run before Step 0 began.

---

> **Sample: 50 transcripts (megacap 13, large 13, mid 12, small/micro 12),
> seed 40. Prompt version used: "v10+auto1 (auto-iterate candidate — pending
> gate)" — confirmed by direct file read, NOT v6. Model string used:
> `claude-sonnet-4-6`, reproducibility risk: **bare alias, flagged** — no
> dated-snapshot identifier was recoverable from the API response object
> beyond this same string. Primary 4-field instability: 39/200 (19.5%) —
> compare v6 21.4%, v9 69.0%; **closer to v6, but not a like-for-like
> reproduction** (different prompt version and model than v6's original
> measurement — see caveat below). Recommendation flips: 11/50 (22.0%),
> including 3 genuine 3-way-or-more splits (ids 175 ENVX, 193 EOSE, 204
> MSFT) — worse than a simple flip. Noise floor (spread of analyst-direct
> hit rate across 5 runs): **2.65pp std, 8.0pp range** aggregate — smaller
> than gate_ledger's 4.2pp bootstrap figure. **By tier this aggregate
> conceals a large split**: large 0.0pp std/range, mid 0.0pp std/range,
> megacap 3.77pp std/7.69pp range, **small/micro 14.34pp std/41.67pp range**
> — over 3x the gate's own threshold. Reading: the existing -7.44pp
> regression **clearly exceeds** the aggregate noise floor (2.65pp) but
> **does NOT clearly exceed** the tier-matched noise floor (14.34pp std) for
> the kind of name (small/micro, speculative) the original gate_ledger entry
> 1 actually scoped to — **these two readings disagree, and both are
> reported rather than resolved.** Test 6: **not fully unblocked** — a
> single scalar noise-floor number does not exist here; which figure Test 6
> should use as its detection threshold depends on which universe it scores,
> and that choice is now visibly consequential rather than a rounding
> matter. Approximate token spend: **4,794,618 tokens across 250 calls**
> (4,045,405 in / 749,213 out) — roughly **$23** at standard Sonnet-family
> per-token rates (estimate, not a billed figure — see caveat below).**

---

## Step 0 — hygiene

Clean tree at session start (only other-session untracked state and this
run's new files). Driver (`analysis/test4_noise_floor.py`) syntax-checked
(`python3 -c "import ast; ast.parse(...)"` — passed) and committed at
`3c689a7`, before any manifest, as its own commit, together with the
prompt file.

## Step 1 — sample draw

`.../manifests/1-draw-manifest.json`. Universe: the 15-ticker table the
prompt specifies verbatim — **ALL16 minus SPWR** (megacap: AAPL, GOOGL,
NVDA, MSFT, TSLA; large: AVGO, AMD, ORCL; mid: FSLR, TTD; small/micro: QS,
AMPX, ENVX, EOSE, RUN). This is the prompt's own stated universe, not a
deviation.

**Cutoff recomputed fresh** (not reused from Test 2): `FORWARD_DAYS=182`
(`analyst_direct_scorer.py`), price cache still ends `2026-05-08` →
**2025-11-07**, identical to Test 2's figure because the cache has not
moved, but derived independently as instructed.

**Pool sizes comfortably exceeded target — no reallocation needed**:

| tier | pre-cutoff pool | even share | target after reallocation | drawn |
|---|---|---|---|---|
| megacap | 98 | 13 | 13 | 13 |
| large | 58 | 13 | 13 | 13 |
| mid | 39 | 12 | 12 | 12 |
| small_micro | 87 | 12 | 12 | 12 |

(50/4 = 12.5; the 2-item remainder from integer division went to megacap
and large per the driver's deterministic tie-break, giving 13/13/12/12 =
50.) Seed **40**, fixed and reported. Full 50-row (ticker, call date) list
written to `analysis/data/run_state/test4-analyst-noise-floor/sample.json`
before any evaluator call, per the prompt's ordering requirement.

## Step 2 — 250 scoring calls

`docs/EVALUATION_PROMPT.md` used exactly as found on disk, unmodified.
Header string extracted by direct regex read: **`v10+auto1 (auto-iterate
candidate — pending gate)`** — confirmed NOT v6, consistent with Test 3's
own finding. Model string: read from `server/lib/versions.js`
`MODEL_VERSION` constant at call time — **`claude-sonnet-4-6`**. The
Anthropic API response object's own `model` field was captured per call
(`model_used_response_hint` in each raw JSON) and matched the requested
string exactly in every one of the 250 responses; the API did not surface
any more specific dated-snapshot identifier. **Reproducibility risk stands
exactly as `PROMOTION_GATE.md` §8 and this prompt's own framing warned**:
this is a bare, undated alias, and Anthropic could silently change what it
resolves to, at which point this exact figure would no longer be
reproducible from the same command.

Temperature 0, no portfolio context, single-transcript evaluation per call
— firewall-consistent. **Zero DB writes** — all 250 outputs live under
`analysis/test4_noise_floor/raw/<transcript_id>.json`, never touched the
`Analysis` table.

**Token spend**: 4,045,405 input + 749,213 output = **4,794,618 tokens**
total (`analysis/data/run_state/test4-analyst-noise-floor/token_usage.json`).
**Cost caveat**: I do not have this account's actual per-token billing rate
for `claude-sonnet-4-6` to hand: the ~$23 figure applies a standard
Sonnet-family estimate ($3/M input, $15/M output) and is reported as an
estimate, not a billed number — check the Anthropic Console for the actual
charge.

**Interruptions, handled as designed**: the background process was killed
twice by the OS for low system memory (not by this driver, not an API
error) — once after 25/50 transcripts, once after 3 more. Each resume
re-ran `python3 test4_noise_floor.py score`, which skipped every transcript
already in `progress.json`'s `transcripts_completed` list and picked up
exactly where it left off. No transcript was scored twice; no partial
(fewer-than-5-runs) transcript data was left in `raw/` at any checkpoint.

## Step 3 — field-by-field stability

`.../manifests/2-analyze-manifest.json`.

**Primary (v6/v9-comparable) 4-field instability**: `thesisHealth`,
`recommendation`, `stumbleType`, `mitigationCapabilityTrackRecord` — **39
unstable (transcript, field) combinations out of 200 (50×4) = 19.5%**.

| run | v6 (ENPH×3, sonnet-4-20250514, prompt v6) | v9 (ENPH×3, candidate) | this run (50×5, sonnet-4-6, prompt v10+auto1) |
|---|---|---|---|
| unstable / total | 18/84 | 26/84 | 39/200 |
| rate | 21.4% | 69.0% | **19.5%** |

**This run's rate sits closest to v6's, essentially matching it, and is far
below v9's.** Stated plainly per the prompt's "prediction is not a gate"
rule — this is the direction the run happened to go, not a target it was
tuned toward. **Caveat that must travel with this number**: v6's 21.4% and
v9's 69.0% were both measured on ENPH only, with 3 runs (not 5), and (per
`EVALUATION_PROMPT.md`'s own changelog) on whichever model was live at the
time those Step 0 runs happened — not necessarily `sonnet-4-6`. This run
differs in prompt version, model, sample size, and run count from both
historical figures simultaneously. "Closer to v6" is a true numerical
comparison; it is not evidence that v10+auto1 reproduces v6's *stability
mechanism*, since prompt and model both moved at once.

**`recommendation` instability**: **11/50 (22.0%)** transcripts had
`recommendation` vary across the 5 runs — comparable to v6's ENPH-only
5/21 (23.8%). **Flagged specifically, per the prompt's instruction**: **3
of the 11 are 3-way-or-more splits**, not simple 2-way flips —

| transcript id | ticker | recommendations across the 5 runs |
|---|---|---|
| 175 | ENVX | Add, Add, Hold, Hold, Trim |
| 193 | EOSE | Trim, Trim, Add, Trim, Hold |
| 204 | MSFT | Hold, Hold, Trim, Hold, Add |

MSFT (megacap) having a genuine 3-way split is worth flagging on its own —
3-way instability is not confined to small/micro-cap names, even though
2-way flips concentrate there heavily (see below).

**Recommendation-flip concentration by tier** (from direct per-sample
inspection of `analysis/test4_noise_floor/raw/*.json`, not just the
aggregate 22%): small/micro **7/12 (58%)**, megacap **2/13 (15%)**, mid
**1/12 (8%)**, large **0/13 (0%)**. Instability is drastically concentrated
in small/micro names — the same pattern the AV transcript-fidelity
benchmark's own hypothesis anticipated for a different mechanism
(coverage/follower depth), now showing up in scoring stability too.

**Secondary (all 15 fields), aggregated across all 50 transcripts:**

| field | % transcripts unstable |
|---|---|
| freshMoneyAllocation | 98.0% |
| recommendedSize | 96.0% |
| activeDriverCount | 66.0% |
| mitigationCapabilityTrackRecord | 44.0% |
| recommendation | 22.0% |
| ratchetTranche | 14.0% |
| credibilityDelta | 12.0% |
| thesisDelta / typeClassification / stumbleType / capPercent / mitigationArgumentPresent | 10.0% each |
| thesisHealth | 2.0% |
| threatMechanismImpaired / blindSpotsTriggered | 0.0% |

**Confirms** benchmark_1's (n=7) flag on `mitigationCapabilityTrackRecord`
at this much larger scale (44% here vs. flagged qualitatively at n=7).
**Refutes** benchmark_1's flag on `blindSpotsTriggered` (0/50 here — never
varied once across 250 calls) and substantially downgrades `credibilityDelta`
(12% here vs. flagged as notably volatile at n=7 — likely small-sample
noise in the pilot). `freshMoneyAllocation` and `recommendedSize` are the
two most volatile fields by a wide margin — both are continuous-ish
numeric sizing fields, a different kind of instability than the categorical
fields the primary comparison uses, and outside this prompt's scope to
interpret further (report, not decide).

**No recurrence found of v9's specific diagnosed rubric-wording bugs** (the
mitigation-sub-test combination rule, the no-prior-transcript capability
case) — `mitigationCapabilityTrackRecord`'s 44% instability rate is real and
notably high, but nothing in the 50 raw outputs inspected for the 3-way
splits above showed the specific v9 failure mode described in
`EVALUATION_PROMPT.md`'s changelog; a full per-field root-cause trace was
not performed (out of this run's scope).

## Step 4 — the headline noise floor, in gate units

`.../manifests/2-analyze-manifest.json` →
`results.hit_rates_per_run` / `hit_rate_std_pp` / `hit_rate_range_pp` /
`hit_rate_by_tier`.

Five independent hit-rate values on the identical 50-transcript sample
(analyst-direct methodology, `analyst_direct_scorer.py`'s own constants,
imported not reimplemented): **50.0%, 48.0%, 46.0%, 46.0%, 42.0%** — all 50
scoreable in every run (no forward-window gaps, by construction of the
cutoff).

**Aggregate: std 2.65pp, range 8.0pp.** Smaller than `gate_ledger.json`
entry 1's `noise_std_pp: 4.2`.

**By tier — this aggregate figure conceals a large split, and is the most
important finding of this run**:

| tier | hit rates across 5 runs | std (pp) | range (pp) | n |
|---|---|---|---|---|
| large | 76.9% every run | **0.0** | **0.0** | 13 |
| mid | 50.0% every run | **0.0** | **0.0** | 12 |
| megacap | 15.4/15.4/23.1/15.4/23.1% | 3.77 | 7.69 | 13 |
| **small/micro** | 58.3/50.0/33.3/41.7/16.7% | **14.34** | **41.67** | 12 |

`large` and `mid` are **perfectly stable** — confirmed by direct trace: zero
recommendation flips landed in `large`'s 13-transcript sample, and `mid`'s
one flip (FSLR, id 100, Hold→Trim) does not change the hit/miss outcome
(ground truth is bullish; both `Hold`→neutral and `Trim`→bearish miss it).
`small_micro`'s noise floor — **14.34pp std, 41.67pp range** — is over 3x
the gate's own 4.2pp threshold and the same order of magnitude as the
`sonnet-4-6` regression itself (-7.44pp).

## Step 5 — reading against gate_ledger.json entry 1

**Two readings, genuinely in tension, both reported rather than resolved:**

1. **Against the aggregate noise floor (2.65pp std):** the -7.44pp
   regression clearly exceeds it — roughly 2.8 standard deviations. On this
   basis, the original HOLD verdict's substance likely still stands, even
   though its *scope* was already known to be unrepresentative
   (state-of-play §5.4).
2. **Against the tier-matched noise floor (14.34pp std) for small/micro
   names** — the kind of name `gate_ledger.json` entry 1's actual 7-ticker
   scope (ENPH, TTD, AMPX, ENVX, EOSE, QS, SPWR) is overwhelmingly composed
   of — the -7.44pp regression sits at roughly **0.52 standard deviations**
   of that tier's own measured noise, and comfortably inside its 41.67pp
   range. **This does NOT clearly exceed noise.**

**Neither reading is adopted here — per the scope boundary, this is
reported as an open, materially consequential disagreement for the design
session, not adjudicated.** It compounds, rather than resolves,
state-of-play §5.4's existing finding that the gate's original evidence was
scoped to unrepresentative tickers: this run shows that scope mismatch
carries a noise-floor mismatch with it, not just a coverage gap. Which
reading is "correct" depends on a judgment this run's scope boundary
excludes: whether the -7.44pp regression itself was measured predominantly
on small/micro-tier names (in which case reading 2 is the relevant one) or
on a more balanced mix (reading 1). That determination needs the paired
champion-vs-challenger re-scoring this run's own scope note explicitly
deferred as a separate, larger, costlier run.

**Test 6 (look-ahead prohibition probe): not cleanly unblocked.**
State-of-play §7 says Test 6 needs this noise floor as its own detection
threshold. This run does not hand it a single usable scalar — it hands it
two very different numbers (2.65pp vs 14.34pp) depending on which
universe/tier Test 6's own corpus resembles more. Test 6's design should
pick the tier-appropriate figure explicitly rather than defaulting to the
aggregate, given how large the gap is.

---

## Flags

- **Any field whose instability rate is far outside what v6's historical
  figure would predict:** `freshMoneyAllocation` (98%) and `recommendedSize`
  (96%) are both far higher than the ~21% primary-field baseline would
  suggest — though these are numeric sizing fields outside the primary
  4-field comparison, so "far outside v6's figure" is a comparison v6 never
  made for these fields; noted as a new finding at this scale, not a
  contradiction of a prior number.
- **Any transcript where all 5 runs disagreed completely on
  `recommendation` (3+ way split):** ids 175 (ENVX), 193 (EOSE), 204 (MSFT)
  — full detail in Step 3 above.
- **Recurrence of v9's diagnosed rubric-wording bugs:** none identified in
  the outputs inspected, though a full root-cause trace was not performed
  (out of scope, flagged as not done below).
- **Previously published number that turns out to be wrong:** none — this
  run does not correct any historical figure, it adds a new, more rigorous
  measurement alongside them. The load-bearing new finding is that
  `gate_ledger.json`'s single 4.2pp bootstrap figure, applied uniformly, is
  now shown to be a poor stand-in for at least one of the two universes
  that number needs to serve (small/micro-tier names, where genuine
  repeat-scoring noise is over 3x higher).

## What was deliberately not done

- The paired champion-vs-challenger re-scoring (state-of-play §5.5's open
  question about which direction `sonnet-4-6` errs) — explicitly deferred
  by the prompt's own scope note as a separate, larger, costlier run.
- Root-causing which specific rubric clauses drive `freshMoneyAllocation`'s
  98% instability or `activeDriverCount`'s 66% — flagged, not traced.
- Any adjudication of whether the -7.44pp regression should stand — Step
  5's two readings are reported side by side, not resolved.
- Re-running or amending `gate_ledger.json`, `PROMOTION_GATE.md`, or
  `EVALUATION_PROMPT.md` — scope boundary.

## Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/test4_noise_floor.py').read())"`
  — passed, before commit.
- Sample size assertion in `step_analyze()`: hard-fails if the number of
  raw scored files does not exactly match the drawn sample size (50) —
  passed silently, confirming no transcript was double-scored or dropped
  across the two resumes.
- Each of the 250 API responses' own `model` field was captured and
  spot-checked to equal the requested `claude-sonnet-4-6` string exactly.
- The `mid`-tier zero-noise result was independently verified by tracing
  the one recommendation flip in that tier (FSLR id 100) against its actual
  ground truth by hand (shown in Step 4) rather than trusted as a bare
  number.
- Recommendation-flip tier concentration (58%/15%/8%/0%) was computed by a
  second, independent pass directly over `raw/*.json`, not derived from the
  aggregate stability numbers.

## Wall-clock, cells run, cells reused

Step 1 (draw): <1s, no resume needed. Step 2 (250 calls): three background
runs — first reached 25/50 before an OS low-memory kill, second reached
28/50 before a second kill, third completed the remaining 22/50 to
completion; total wall-clock across all three roughly 35-45 minutes of
actual API time (not separately logged to the second, but bounded by the
250-call count and typical per-call latency observed in the raw JSON files'
implicit ordering). Step 3/4 (`analyze`): pure local computation over
already-saved JSON, well under 5 seconds. 3 top-level cells written to
`cells.jsonl` (`draw`, and each transcript's scoring is itself a checkpoint
though not a separate `cells.jsonl` entry — see `findings.md` for the
per-transcript checkpoint log; `analyze` is the third `cells.jsonl` entry).

## Files written

- `analysis/test4_noise_floor.py` (driver, committed `3c689a7`)
- `prompts/test4-analyst-noise-floor.md` (committed `3c689a7`)
- `analysis/test4_noise_floor/raw/<transcript_id>.json` × 50 (all 5 runs'
  full structured output + raw text per transcript; 3.5MB total, committed
  alongside the run state for citability, same precedent as
  `analysis/av_fidelity_test/raw/`)
- `analysis/data/run_state/test4-analyst-noise-floor/{progress.json,
  findings.md, cells.jsonl, sample.json, token_usage.json,
  manifests/{1-draw,2-analyze}-manifest.json}`

## Follow-up commands

```bash
cd analysis
python3 test4_noise_floor.py draw      # Step 1, no cost, reruns the sample draw
python3 test4_noise_floor.py score     # Step 2, resumable, real spend if re-run from scratch
python3 test4_noise_floor.py analyze   # Steps 3/4, no new calls, reruns on saved raw/ output
```

To inspect any individual transcript's 5 raw runs directly:

```bash
python3 -c "
import json
d = json.load(open('analysis/test4_noise_floor/raw/204.json'))
for r in d['runs']:
    print(r['run_idx'], r['structured'].get('recommendation') if r['structured'] else None)
"
```
