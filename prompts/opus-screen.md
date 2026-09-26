# Opus screen — does a larger model read calls differently? About $35–50

**Run ID:** `opus-screen`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/opus-screen-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — estimated $35–50, measured before
committing.** B's prompt, unchanged, on `claude-opus-5-5` over 300 train
calls. A 30-call pre-flight measures the real per-call cost first.
**Hard cap $50**, counted before every `create()`. Luis approves at Step
0; record it in `progress.json` or stop and ask.

---

## Framing

**What this run exists to answer.** One question, used as a screen: **does
a larger model read the same calls differently from Sonnet, by more than
Sonnet differs from itself?**

- **If not,** a bigger reader adds nothing on transcripts alone, and the
  question of what can be read from a transcript closes. Work moves to
  building around the analyst's downside skill, and to consensus data for
  the bullish side.
- **If so,** a full two-draw train test on Opus becomes worth pricing.

**This is a screen, not a gate.** It cannot promote a model, and it changes
nothing in the registry's promoted model (`claude-sonnet-4-6`). It is not
the §2.2b model gate.

**The screen is asymmetric, stated before it runs.** Opus disagrees with
Sonnet for two reasons: it reads differently, **or** it is noisier.
One Opus draw cannot separate them.
- **Opus-vs-Sonnet disagreement no larger than Sonnet-vs-Sonnet** →
  closes the question cleanly.
- **Larger** → "worth a full test", not "better". The full test (two Opus
  draws) is what separates reading from noise.

**Already established; do not rediscover.**
- B's two Sonnet draws on train (`p6-output-format-round/scores_b.jsonl`,
  `b-champion-and-noise-floor/scores_b_rerun1.jsonl`). Sonnet changes
  direction on itself on 12.5% of calls
  (`wrap-ups/B-champion-and-noise-floor-out.md`).
- B has no information about big winners, and beat-and-raise is not a
  winner signal on this corpus (`wrap-ups/winners-missed-v3-out.md`).
- **Recall:** earlier tests (`wrap-ups/test6-look-ahead-prohibition-out.md`,
  `wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`) found no detectable
  recall on Sonnet, but they could only see large effects. A larger, newer
  model may remember more. **Any accuracy gain Opus shows is suspect for
  that reason.**

**Read first:** the wrap-ups above; `analysis/p6_output_format_driver.py`
(the `--rerun` path is the model; add `--opus`, which overrides `MODEL`
**only on that path** and leaves every existing Sonnet assertion in place).

---

## Ground rules

1. **Train only**, 300 calls. No tune, no holdout, no DB writes, no cache
   refresh.
2. **B's prompt, byte for byte** (sha `d1fa5e53…`, asserted), same request
   construction, `max_tokens` 4096, no temperature parameter, Batch API.
   **The only change is the model string: `claude-opus-5-5`.** Assert
   every response reports an Opus model. If the API rejects the model
   string, stop and report. Do not substitute another model.
3. **Guard:** `PROMPT_CANDIDATE=P6B-minimal`. Record in `progress.json`
   that the model is a screen override, not a registry change.
4. **Custom ids suffixed `__opus`.** Cache
   `analysis/data/evals/P6B-minimal_claude-opus-5-5_screen/` (gitignored).
   Commit `scores_b_opus.jsonl`.
5. **The reading in §3 is fixed here.** Report, do not decide.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends (CLAUDE.md rule 9)

State in `analysis/data/run_state/opus-screen/`. `progress.json` first.
Commit this prompt file if untracked or modified, as its own commit.
Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
extension committed before any output, as its own commit. Batch ids
committed the instant `create()` returns. One process, no pipe to `tail`,
no background poller.

---

## Step 1 — selection, $0

300 train calls, stratified proportionally by `stratum_map()` (S1–S5, at
least one S4 call), seeded (`opus-screen-11`). Commit `selection.json`
before any scoring. Report how many big winners (≥ +20) and big losers
(≤ −20) the 300 contain.

## Step 2 — pre-flight, 30 calls (inside the 300)

Parse check (score in −5..+5, `noRead` boolean), no `max_tokens` stops,
and every response reports an Opus model. **Measure the cost per call and
project the other 270.** If the projection puts the total over $50, stop
and report the measured cost. Do not score a subset.

## Step 3 — the remaining 270, one batch; then the comparison ($0)

On the same 300 calls, using the pre-registered mapping (≤ −2 bearish, ≥
+3 bullish, else neutral):

1. **Direction disagreement**, with Wilson ranges:
   - Opus vs B draw 1;
   - Opus vs B draw 2;
   - **B draw 1 vs B draw 2 on these same 300** (Sonnet's own noise here).
2. **The screen figure:** the mean of the two Opus-vs-Sonnet rates, minus
   the Sonnet-vs-Sonnet rate. Give its ticker-block bootstrap range
   (2,000 draws, seed 11), resampling companies and recomputing all three
   rates together.
3. Score moved ≥ 1 and ≥ 2, for each of the three pairs.
4. The 3×3 direction tables: Opus by B draw 1, and Opus by B draw 2.
5. **Reported, not read as evidence** (300 calls; roughly ±0.11 on any
   rank correlation):
   - rank correlation with the 182-day return, for Opus and both B draws
     on these 300;
   - hit rates at matched coverage, scaled to 300 (bottom 47, top 58,
     the same shares as 191 / 235 of 1,217);
   - how Opus scored the big winners in the sample, beside B's scores.
6. Cost per call, completion tokens, noRead share.

### Pre-registered reading, fixed now, one rule

- **"Nothing new"** if the screen figure's range includes zero or sits
  below it. Opus disagrees with Sonnet no more than Sonnet disagrees with
  itself.
- **"Reads differently — worth a full test"** if the range is entirely
  above zero. State the point estimate. Say plainly that one Opus draw
  cannot tell "reads differently" from "noisier".

**Prediction, not a gate:** "nothing new". Opus-vs-Sonnet disagreement
within 3 points of Sonnet-vs-Sonnet.

---

## Report step

**Scope boundary: report, do not decide.** No registry change, no model
change, no full Opus run.

`wrap-ups/opus-screen-out.md`, `.md` only. Open with:

> On 300 train calls, B's prompt run on Opus changed direction against
> Sonnet's two runs on ___% and ___% of calls; Sonnet changed direction
> against itself on ___% of the same calls. The difference is ___ points
> (range ___ to ___): **[nothing new / reads differently — worth a full
> test]**. Opus cost $___ per call against Sonnet's $0.0236.

Then items 1–6. Then the recall caveat, in one sentence.

**Close with what it means, both ways.**
- **Nothing new:** the transcript question closes. Next is the allocator
  rebuild around the analyst's downside skill, with the consensus-data
  thread as the separate bullish project.
- **Worth a full test:** give the price of two Opus draws on all 1,217
  train calls at the measured cost. Say that the recall caveat applies
  with more force to any gain found there.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Finish with `git push`** of `sweep/db-corpus-baseline` after the
wrap-up commit, and report the pushed hash; on failure, say so and never
force. **Budget stop:** the pre-flight always runs first. The remaining
270 run as one batch, all or nothing.
