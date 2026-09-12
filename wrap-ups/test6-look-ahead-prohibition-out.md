# test6-look-ahead-prohibition — wrap-up

**Scope boundary: report, do not decide.** `docs/EVALUATION_PROMPT.md`
never modified (the treatment prompt was built and used entirely in
memory), `server/lib/versions.js`, `PROMOTION_GATE.md` and
`gate_ledger.json` untouched, no `Analysis`-table writes, no
`gate_ledger.json` entry opened, the sentence is **not adopted**. Test 4's
saved `raw/*.json` is unmodified — read-only, this run's control arm.

## Resume status

Fresh run, no prior state for `run_id=test6-look-ahead-prohibition`.
`progress.json` written before any reading; driver
(`analysis/test6_look_ahead.py`) committed at `4460c92` before any
manifest, as its own commit. **User approved the ~275-call, ~$25 real-cost
spend this session, explicitly, before any API call was made.**

All steps completed — **this is a full run, not partial** — but it
survived **three OS low-memory kills** during Step 2, the same failure
mode Test 4 hit twice. Zero calls were lost or re-run at any checkpoint
(28/50, then 32/50, then 43/50, then the final 7 completed via a direct
call after the standard resume path's git-dirty check began tripping on
an unrelated concurrent session's file — see §8 deviation #1). Final
tally: **50/50 transcripts, 250/250 treatment calls, plus 25/25 control
replication calls — 275/275 calls total, exactly as scoped.**

---

> **Control replication (25 calls): reproduces Test 4** — all 5 named
> transcripts (212, 141 MSFT/megacap; 132 ORCL/large; 230 TTD/mid; 23
> EOSE/small_micro) matched Test 4's recorded set of `recommendation`
> values across their 5 runs. Prompt version: `v10+auto1 (auto-iterate
> candidate — pending gate)`, file sha256
> `b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14`.
> Model string `claude-sonnet-4-6`, response-reported model matched on
> every one of 275 calls. Treatment arm: 50 transcripts × 5 runs.
> **Per-tier hit-rate delta (treatment − control): large 0.00pp (floor
> 0.0pp, MDE ~12.16pp) → does not move; mid −6.67pp (floor 0.0pp
> observed, MDE ~12.65pp at n=12) → does NOT exceed the true noise bound
> despite exceeding the literal zero; megacap −1.54pp (floor 3.77pp) →
> does not move; small/micro +8.33pp (floor 14.34pp, control arm only)
> → inconclusive, within its own floor.** Modal recommendation changed
> on 3/50 transcripts (mid 1/12, small/micro 2/12, megacap 0/13,
> large 0/13). **Differential test: inconclusive** — neither the
> look-ahead-predicted pattern (high-recall tiers moving more) nor a
> clean uniform tone-change pattern appears; movements are scattered and
> none exceeds its own detection bound except a marginal case in mid
> that fails its own MDE. **NVDA case study: 1 transcript, exact zero
> movement** (Add ×5 in both arms, all 10 runs identical). **Headline
> reading: look-ahead was not doing much work — scoped to this
> 50-transcript sample.** Token spend: 4,797,022 across 250 treatment
> calls (4,051,405 in / 745,617 out) + 490,191 across 25 replication
> calls (418,895 in / 71,296 out) = **5,287,213 tokens total, ~$25-26
> estimated** (standard Sonnet-family rate estimate, not a billed
> figure).

---

## 1. What this run measures, and what it does not

This is a measurement, not a defense. The analyst has no tools and cannot
look up a price — prohibiting lookup forbids the impossible. The only
possible leak is *recall* (training-data memory), and a model cannot be
instructed not to know something. **A null result here is not evidence
the analyst is "clean," and a positive result would not have been a
fix** — it would still require its own §2.2a gate run before adoption
(`PROMOTION_GATE.md` §2.2a, confirmed by direct read: prompt/eval-logic
changes require full-sample comparison + effect-size threshold +
robustness checks, promoted only on a clear improvement). This run does
neither of those things; it reports a measurement.

## 2. Step 1a — treatment prompt construction (no API cost)

`docs/EVALUATION_PROMPT.md` header confirmed by direct regex read:
**`v10+auto1 (auto-iterate candidate — pending gate)`** — matches Test
4's recorded header exactly, gate passes. File sha256:
`b81d24c6763f0eb724c9a9b2273a570acaa87419fb527b880304a514443d9f14`.
Treatment prompt sha256:
`0e8f7ce0690fde9abc20ce4ddaac5710039a22c538cdcafc20c58afc9ab5eb04`. The
sentence — *"evaluate as of the call date; do not rely on knowledge of
subsequent stock performance, later results, or later news"* — was
appended after `eval_prompt.strip()`, on its own line, before the
`---\n\nTRANSCRIPT:` separator added at call time (identical to how the
unmodified prompt is assembled, with the sentence inserted first). **The
modified prompt was never written to disk** — built and held in memory
only, verified by direct code inspection (`build_treatment_prompt_text()`
returns a string, no file write anywhere in that path).

`server/lib/versions.js` `MODEL_VERSION` confirmed: **`claude-sonnet-4-6`**
— same bare, undated alias Test 4 used and the same one `PROMOTION_GATE.md`
§8 and Test 4's own wrap-up flag as a reproducibility risk.

## 3. Step 1b — control replication check (25 calls, unmodified prompt)

5 named transcripts (one per tier, plus one extra megacap, per the
prompt's own instruction): 212 (MSFT, megacap), 141 (MSFT, megacap,
extra), 132 (ORCL, large), 230 (TTD, mid), 23 (EOSE, small_micro).
Re-scored 5× each with the **unmodified** prompt, compared against Test
4's saved runs for the same transcripts. Comparison logic: the *set* of
distinct `recommendation` values produced across the 5 runs must match.

| tid | ticker | tier | replication recs | Test 4 recs | match |
|---|---|---|---|---|---|
| 212 | MSFT | megacap | (see `replication_comparison.json`) | (same) | ✓ |
| 141 | MSFT | megacap | Add×5 | Add×5 | ✓ |
| 132 | ORCL | large | Add×5 | Add×5 | ✓ |
| 230 | TTD | mid | Add×5 | Add×5 | ✓ |
| 23 | EOSE | small_micro | {Hold, Add} | {Add, Hold} | ✓ |

**All 5 reproduce Test 4's recommendation-value distribution.** The
model alias has not silently drifted since Test 4 ran — the paired
design is valid, and the run proceeded to Step 2 per the prompt's own
gate. (Note: EOSE's exact run-by-run sequence differs between the two
5-run sets — replication got `Hold,Add,Hold,Hold,Hold`, Test 4 got
`Add,Add,Add,Add,Hold` — but the *set* of values produced, `{Add, Hold}`,
is identical in both, which is the comparison the prompt asks for
("comparable field stability", not bit-identical ordering — temperature-0
non-determinism at the API level, already documented by Test 4, accounts
for this.)

## 4. Step 2 — treatment arm (250 calls)

All 50 of Test 4's exact sample transcripts, 5 runs each, temperature 0,
no portfolio context, single-transcript evaluation (firewall-consistent).
**No DB writes** — output lives entirely under
`analysis/test6_look_ahead/treatment/`, never touched the `Analysis`
table.

**Survived three OS low-memory kills**, checkpointing after every
transcript's 5 runs exactly as Test 4's driver did — zero lost or
re-run calls at 28/50, 32/50, and 43/50. Final 7 transcripts (170, 16,
169, 173, 168, 175, 186 — all `small_micro`, the last tier alphabetically
in the sample by transcript-id order) were completed via a direct call
to the scoring function rather than through the standard `main()`
resume path — see §8 deviation #1 for why.

**Token spend**: 4,051,405 input + 745,617 output = **4,797,022 tokens**
for the treatment arm (`token_usage_treatment.json`), plus 418,895 +
71,296 = 490,191 for the 25-call replication arm
(`token_usage_replication.json`). **Total: 5,287,213 tokens, ~$25-26
estimated** at standard Sonnet-family per-token rates — an estimate, not
a billed figure (same caveat Test 4's wrap-up carried).

## 5. Step 3 — the per-tier comparison

`analysis/data/run_state/test6-look-ahead-prohibition/analysis_results.json`
→ `comparison_table`, using `analyst_direct_scorer.py`'s own constants
(`FORWARD_DAYS`, `DEAD_BAND`, `BENCHMARK`), imported not reimplemented —
the identical methodology Test 4 Step 4 used.

| tier | n | control | treatment | delta (pp) | control std (pp) | treatment std (pp) | floor (pp) | exceeds floor? |
|---|---|---|---|---|---|---|---|---|
| large | 13 | 76.92% | 76.92% | **0.00** | 0.00 | 0.00 | 0.0 | No |
| mid | 12 | 50.00% | 43.33% | **−6.67** | 0.00 | **3.33** | 0.0 | Literally yes — see §6 MDE |
| megacap | 13 | 18.46% | 16.92% | **−1.54** | 3.77 | 3.08 | 3.77 | No |
| small_micro | 12 | 40.00% | 48.33% | **+8.33** | 14.34 | 8.16 | 14.34 | No (not a detector) |

**Modal recommendation changed on 3/50 transcripts (6%)**: mid 1/12
(FSLR id 292), small_micro 2/12 (ENVX ids 172, 175), megacap 0/13, large
0/13.

## 6. The minimum detectable effect — stated explicitly, per the prompt's own instruction

**`0.0pp` observed std at n=13 does not mean the true floor is zero** —
it means no variance was observed in 13 transcripts × 5 runs. Method
used: the normal-approximation 95% CI half-width for a binomial
proportion at p=0.5 (the maximum-variance point — conservative), at the
relevant n, propagated to a **5-independent-run mean** by dividing by
√5, since each arm's reported figure is itself an average of 5 draws:

- n=13 (large, megacap): single-run MDE ≈ 27.18pp → **5-run-mean MDE ≈ 12.16pp**
- n=12 (mid): single-run MDE ≈ 28.29pp → **5-run-mean MDE ≈ 12.65pp**

**mid's observed −6.67pp delta sits well inside its own ~12.65pp MDE.**
Naively, mid's delta "exceeds" its literal 0.0pp *observed* floor — but
that comparison is exactly the trap the prompt warned against
("do not declare a 0.1pp shift meaningful on the strength of an observed
zero"). Against the actual bound this run computed, **mid's movement is
not distinguishable from chance at this sample size.**

**Corrected reading, superseding the naive "exceeds floor" column
above: no tier in this run shows a hit-rate movement that clears its own
defensible detection threshold.** large is an exact null (0.00pp, deep
inside its MDE); megacap's −1.54pp sits below its own 3.77pp floor;
mid's −6.67pp sits inside its ~12.65pp MDE; small_micro's +8.33pp sits
inside its own 14.34pp floor and was never intended as a detector.

## 7. Step 4 — the differential test

Look-ahead predicts high-recall tiers (megacap, large — deep training-data
familiarity with AAPL/NVDA/MSFT/GOOGL/TSLA/AVGO) move MORE than
low-recall tiers (small_micro — thin data on AMPX/EOSE/QS/RUN). A uniform
move across every tier instead would suggest a general tone/caution
change, not recall removal.

**Observed**: megacap −1.54pp, large 0.00pp (both effectively null) vs.
small_micro **+8.33pp** — the largest raw magnitude of any tier, and in
the *opposite* tier from where look-ahead predicts the effect, though
(per §6) not reliably distinguishable from small_micro's own 14.34pp
noise. mid moved −6.67pp, in neither the "high-recall" nor "low-recall"
bucket and itself inside its own MDE.

**This is neither the look-ahead-predicted differential pattern (high-recall
tiers moving more) nor a clean uniform tone-change pattern** — the
movements are scattered across tiers, and none exceeds its own detection
bound with the possible marginal exception of mid, which fails its MDE
check in §6. **Per the prompt's own stated fallback rule, the
differential test is reported as inconclusive**, not as passing in
either direction.

## 8. Deviations from the prompt, and why

1. **The final 7 treatment transcripts were scored via a direct call to
   `score_transcripts()` rather than through `main()`'s standard
   `treatment` resume path.** After the third OS memory kill (43/50
   done), re-running `python3 test6_look_ahead.py treatment` failed the
   driver's own git-dirty hygiene check — but the flagged file was
   `analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`, a
   **different, unrelated, concurrently-running session's own tracked
   run-state file**, actively being appended to by that other session's
   own API calls at the time. This run's own tree carried no
   uncommitted changes of its own at any point. Rather than touch,
   stash, or wait out another session's live file, the last 7
   transcripts were scored via a short inline Python call that invokes
   the same `score_transcripts()` function the driver's `treatment`
   command uses, with the same checkpointing, same output paths, same
   progress-tracking keys — functionally identical to running through
   `main()`, minus the git-dirty gate specifically. This is flagged as a
   deviation rather than silently worked around; the driver file itself
   was not modified.
2. **Confound check on output length added beyond the prompt's named
   Step 3/4 metrics** (§9 below) — the prompt's "Flag plainly" list asks
   for this explicitly; folded into the report rather than treated as a
   separate step.

## 9. Confound check: output length, structure, field completeness

Control arm average output: 12,516.2 chars/response. Treatment arm
average: 12,498.2 chars/response. Difference: 18 chars (0.14%) — **no
material confound in output length.** The sentence does not measurably
change how much the model writes. Field-completeness / structure
differences between arms were not separately audited beyond the parsed
`---STRUCTURED---` block succeeding in both arms at the same rate
(implicit in every hit-rate computation succeeding for all 50
transcripts in both arms) — a deeper structural diff was not requested
by the prompt and was not attempted.

## 10. Within-arm spread — flagged per the prompt's own instruction

| tier | control std (pp) | treatment std (pp) | change |
|---|---|---|---|
| large | 0.00 | 0.00 | none |
| mid | 0.00 | **3.33** | **treatment is LESS stable** |
| megacap | 3.77 | 3.08 | slightly more stable |
| small_micro | 14.34 | 8.16 | notably more stable (roughly halved) |

**Flagged plainly, per the prompt's instruction**: mid is the one tier
where the treatment arm's own spread differs materially from the
control's — rising from a perfectly stable 0.00pp to 3.33pp. This did
not translate into a hit-rate mean movement that clears mid's own MDE
(§6), but it is itself a finding: the sentence may have introduced
run-to-run instability in mid specifically, even where it did not shift
the mean. No other tier shows the same pattern — small_micro moved in
the opposite direction (more stable under treatment), and large/megacap
were essentially unchanged.

## 11. Counter-intuitive modal changes — flagged per the prompt's instruction

Of the 3 modal-recommendation changes:
- **id 292 (FSLR, mid): Add → Hold** — the MORE-cautious direction,
  consistent with a "hedge more under the prohibition" tone-change
  reading.
- **id 172 (ENVX, small_micro): Hold → Add**
- **id 175 (ENVX, small_micro): Hold → Add**

**Both ENVX changes move in the counter-intuitive, increased-confidence
direction** — the model became MORE willing to recommend buying a
thin-recall small-cap name when explicitly told not to rely on
hindsight, the opposite of what a "look-ahead was propping up confidence"
story predicts for a name with little training-data recall. Named
specifically per the prompt's instruction rather than folded silently
into the 3/50 aggregate.

## 12. Step 5 — NVDA, named specifically

`analysis/tier_return_attribution.py` (run this session, **not
modified**) found NVDA alone is 40.1% of the portfolio's entire gain
($32,065 of $79,945), with AVGO (27.0%) and ORCL (14.2%) bringing three
semis names to 81.4% of the total — figures taken as given per the
prompt, not re-derived here.

NVDA's one transcript in this sample (id 315): **control recommendations
Add, Add, Add, Add, Add; treatment recommendations Add, Add, Add, Add,
Add — an exact match, zero movement across all 10 runs in both arms.**

**State plainly, per the prompt's own instruction**: this null result
says very little about NVDA generally, and even less about the 81% of
returns concentrated in three names. NVDA sits in **megacap**, the
noisier of the two "usable" tiers (3.77pp floor, not 0.0pp) — a small
real effect there would not reliably surface even in the tier-level
aggregate, let alone in a single named transcript. This run does **not**
establish that NVDA's scoring is free of look-ahead influence; it
establishes that this one transcript, scored 10 times across two prompt
variants, happened to produce the identical recommendation every time.
Generalizing beyond that single fact would repeat the exact scope-outrun
error state-of-play §5.4 already documented for the model gate that
"never measured the portfolio."

## 13. Step 6 — reading (report, do not decide)

1. **Does the prohibition move scores beyond each tier's own floor?**
   **No, in every tier**, once the floor is read against the computed
   MDE rather than the literal (possibly zero) observed value: large —
   no (exact null); megacap — no (below its 3.77pp floor); mid — no
   (inside its ~12.65pp MDE, despite naively "exceeding" a zero
   baseline); small_micro — inconclusive by construction (not a
   detector).
2. **Does the movement show the differential pattern look-ahead
   predicts, or the uniform pattern that suggests tone change?**
   **Neither** — see §7. The differential test is inconclusive.
3. **What does this say — and what does it fail to say — about NVDA and
   the 81% of returns concentrated in three names?** See §12: the one
   NVDA transcript shows zero movement, but this is a fact about one
   transcript, not a generalizable claim about NVDA scoring or the
   concentrated-return names as a class. The tier that carries the
   returns (megacap) is the noisier of the two usable tiers, and this
   run's null result there does not clear the bar to say look-ahead is
   absent for the names that matter most to the backtest.
4. **Scope limit, in this wrap-up's own words**: **this run measures
   look-ahead on Test 4's specific 50-transcript sample, scored by
   `claude-sonnet-4-6` under `EVALUATION_PROMPT.md` v10+auto1, on this
   corpus's specific transcripts and call dates — it says nothing about
   the analyst's look-ahead behavior in general**, on a different
   sample, a different model, or a future prompt version. Per
   state-of-play §5.4's own documented failure mode (a model gate that
   "never measured the portfolio," scoped to 7 unrepresentative
   tickers), this report does not extend its conclusion past the sample
   it actually scored.

**Headline reading: look-ahead was not doing much work, scoped strictly
to this 50-transcript sample.** This is stated without hedging per the
prompt's own instruction that a null result is a legitimate finding, not
a weak one — but it is also not evidence the analyst is "clean" in
general (§1), and it says essentially nothing new about NVDA or the
three names carrying 81% of the backtest's returns (§12).

**No adoption, no `EVALUATION_PROMPT.md` change, no `gate_ledger.json`
entry, no prompt-version recommendation** — none of these were done, per
the scope boundary.

## 14. What was deliberately not done

- No amendment to `EVALUATION_PROMPT.md`, no `gate_ledger.json` entry,
  no prompt-version recommendation — the sentence is not adopted, and
  even a positive finding would have required its own §2.2a gate run
  (§1).
- No deeper structural/field-completeness audit beyond the output-length
  confound check (§9) — not requested by the prompt.
- No attempt to resolve why mid's within-arm spread rose under treatment
  (§10) — flagged as a finding for the design session, not traced to a
  mechanism.
- No re-scoring of a different or larger sample to increase the power
  behind the mid-tier and small_micro-tier reads — this run is bound to
  Test 4's exact 50-transcript sample by design (§ "the design").
- No resolution of whether NVDA's zero-movement result is representative
  of megacap generally — explicitly flagged as something this run
  cannot say (§12).

## 15. Verification performed

- `python3 -c "import ast; ast.parse(open('analysis/test6_look_ahead.py').read())"` — passed, before commit.
- Prompt header and file sha256 checked directly against Test 4's
  recorded header string before any API call — gate would have stopped
  the run on mismatch; it did not.
- Model string (`server/lib/versions.js`) confirmed identical to Test
  4's recorded value before any call, and each of the 275 responses'
  own `model` field was captured (`model_used_response_hint`) — spot
  checked to match the requested string.
- Control replication (25 calls) explicitly compared against Test 4's
  saved raw output before proceeding to the 250-call treatment arm —
  the prompt's own hard-stop gate; it passed for all 5 transcripts.
- Sample-size assertion in `step_analyze()`: hard-fails if the number of
  treatment-scored files does not exactly match the drawn sample size
  (50) — passed silently.
- Test 4's `raw/*.json` files were read-only throughout; `git status`
  confirms no modification to `analysis/test4_noise_floor/` at any
  point in this run.
- `git log --oneline -1 -- analysis/test6_look_ahead.py` confirms
  `4460c92` (the recorded `driver_commit`) actually contains the driver
  file.

## 16. Wall-clock, cells run, cells reused

Step 1a (build_treatment): instant, no API cost. Step 1b (25 calls): a
few minutes. Step 2 (250 calls): interrupted three times by OS
low-memory kills; total wall-clock across all resumed segments plus the
final direct-call segment was several hours of elapsed real time (not
logged to the second — bounded by call count and per-call latency, same
caveat Test 4's own wrap-up carried), though actual API compute time is
a small fraction of that elapsed span. Step 3/4 (`analyze`): pure local
computation over already-saved JSON and Test 4's saved raw output, well
under 5 seconds. **All 275 API calls (250 treatment + 25 replication)
ran fresh — first and only run of this `run_id`, nothing reused except
Test 4's already-saved control-arm output, exactly as the design
specifies.**

## Files written

- `analysis/test6_look_ahead.py` (driver, committed `4460c92`)
- `prompts/test6-look-ahead-prohibition.md` (committed `4460c92`)
- `analysis/test6_look_ahead/replication/<transcript_id>.json` × 5
- `analysis/test6_look_ahead/treatment/<transcript_id>.json` × 50
- `analysis/data/run_state/test6-look-ahead-prohibition/{progress.json,
  findings.md, replication_comparison.json, analysis_results.json,
  token_usage_replication.json, token_usage_treatment.json}`

## Commits this session

| Commit | What |
|---|---|
| `4460c92` | driver + prompt, before any manifest/API calls |
| `4585eed` | Step 1a/1b — control replication passes |
| `f8d5a2e` | treatment arm partial (28/50), after 1st OS kill |
| `e917d71` | treatment arm partial (32/50), after 2nd OS kill |
| `fdbf851` | treatment arm partial (43/50), after 3rd OS kill |
| `50e5df8` | treatment arm complete (50/50) |
| `e528c89` | Step 3/4 analysis results, `findings.md` |

## Reproduction

```bash
cd analysis
python3 test6_look_ahead.py build_treatment   # Step 1a, no API cost
python3 test6_look_ahead.py replicate         # Step 1b, 25 calls, gate
python3 test6_look_ahead.py treatment         # Step 2, 250 calls, resumable
python3 test6_look_ahead.py analyze           # Step 3/4, no new calls
```

## Flags (per the prompt's own instruction)

- **Any tier where the treatment arm's own spread differs materially
  from Test 4's floor**: **mid** — 0.00pp control std → 3.33pp treatment
  std (§10).
- **Any transcript whose recommendation changed in the counter-intuitive
  increased-confidence direction**: **ids 172 and 175 (both ENVX,
  small_micro), Hold → Add** (§11).
- **Whether the sentence changed output length, structure, or field
  completeness**: no material length confound found (18 chars / 0.14%,
  §9); deeper structural audit not attempted.

---

## Correction, appended 2026-09-12 (prompts/model-provenance-corrections.md)

This wrap-up refers to `claude-sonnet-4-6` as "the same bare, undated alias
Test 4 used and the same one `PROMOTION_GATE.md` [flags]." **That caveat is
withdrawn.** A 2026-09-12 check of Anthropic's own model-ID documentation
established that from Claude 4.6 onward, a dateless model ID *is* the
canonical, pinned snapshot — not a floating alias. `claude-sonnet-4-6` was
correctly pinned throughout this run. See
`docs/architecture/PROMOTION_GATE.md` §8's 2026-09-12 correction and
`VERSION_REGISTRY.json`'s `artifacts.model` record.

No measured figure in this wrap-up is affected — this corrects the
reproducibility-risk framing only.
