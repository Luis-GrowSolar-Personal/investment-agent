# P7 — three voices, from B, on train

**Run ID:** `p7-three-voices-train`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P7-three-voices-train-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $38.** A 150-call pre-flight
(~$4) that decides whether the full round runs, then all 1,217 train calls
(~$33 at an estimated ~$0.027 per call; P7 writes ~400 more output tokens
than B's measured $0.0236). **Hard cap $45**, counted before every
`create()`. Luis has approved $45; record it in `progress.json` at Step 0
or stop and ask. **A second P7 draw (§5, ambiguity rule) is NOT approved
here.** If it triggers, stop and ask.

**Status: review closed 2026-09-26** (`prompts/P7-three-voices-review.md`:
one change, applied — `pressure` split out of `gap`). Clear to run.

---

## Framing

**What this run exists to answer.** No prompt so far can pick winners. B's
top 235 train calls by score were right 39.6% of the time on one run and
36.2% on an identical second run. v6's bullish calls were no better. P7
asks whether separating the transcript's three voices, and scoring the gap
between them, gives the analyst a bullish signal. The voices are the
numbers (usually the CFO), the claims (usually the CEO), and what the
analysts pressed on.

**The mechanism, in one sentence.** A company whose numbers are ahead of
its claims, and whose pressed questions were answered, is under-promising.
That is the case B's single unguided read may miss.

**Already established; do not spend budget rediscovering it.**
- B is the research champion and the comparator: `VERSION_REGISTRY.json` →
  `artifacts.evaluation_prompt.research_champion`, with two baseline draws.
  Draw 1 is `p6-output-format-round/scores_b.jsonl`. Draw 2 is
  `b-champion-and-noise-floor/scores_b_rerun1.jsonl`.
- B's noise floor: `wrap-ups/B-champion-and-noise-floor-out.md`. It changes
  direction on 152 of 1,217 train calls, or 12.5%. Its ranking strength
  moved 0.130 → 0.099 between identical runs.
- The rules every B-derived round follows: `PROMPT_ARCHITECTURE.md` §2.3a.
  **Binding here.**

**Closed:** the ≤ −2 / ≥ +3 mapping, the score scale, the company split,
the 182-day tradeable-entry return vs SPY as the ruler, and everything in
`PROMPT_ARCHITECTURE.md` §1.

**Read first:** `PROMPT_ARCHITECTURE.md` §2.3, §2.3a, §2.4, §2.5, and the P7
block; `wrap-ups/B-champion-and-noise-floor-out.md` (all);
`wrap-ups/P6-output-format-round-out.md` §6; `prompts/P6-output-format-round.md`
§5, §7; `analysis/p6_output_format_driver.py` and
`analysis/b_noise_floor_analysis.py` (extend both; do not fork).

---

## 1. The candidate

`docs/prompts/candidates/EVALUATION_PROMPT_P7_three_voices.md`. It is B with
one added section (VOICES: numbers, claims, pressure, gap) before READ, and
two added structured fields: `gap` (`numbers_ahead`, `aligned` or
`claims_ahead`; numbers versus claims only) and `pressure` (`answered`,
`avoided` or `none`). Objective, constraint, score scale, READ,
SCORE and the other fields are B's, word for word. **Verify that with a
diff before registering, and report the diff.**

---

## 2. Ground rules

1. **Train only.** The same 1,217 calls as B's two draws (assert equality
   with `scores_b.jsonl`). No tune, no holdout, no DB writes.
2. **Scored like B:** model `claude-sonnet-4-6`, `max_tokens` 4096, **no
   temperature parameter**, same system/user construction, Batch API.
   Assert the request shape against B's `make_request()` with only the
   prompt text differing.
3. **Guard:** register `P7-three-voices` in `VERSION_REGISTRY.json` as a
   candidate with its sha256 (parent `P6B-minimal`) at Step 0, then run
   under `PROMPT_CANDIDATE=P7-three-voices`.
4. **No threshold, mapping, scorer or price-cache change.** Do not re-score
   B.
5. **Pre-registration first.** Copy §4 of this prompt into
   `PROMPT_ARCHITECTURE.md` §2.2 under P7, dated, as its own commit
   **before** the pre-flight batch is created. Mark the P7 table row
   "registered — running".

A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop.

---

## 3. Step −1 / Step 0

State in `analysis/data/run_state/p7-three-voices-train/`. `progress.json`
is the very first action. It records the prompt sha, driver commit, step
status, `next_action`, `notes[]`, and the $45 approval. Batch ids
(`batch_id_preflight`, `batch_id_full`) are committed the instant
`create()` returns. One process, output to the terminal, no pipe to
`tail`, no background poller. Clean tree; hard stop if `git_dirty` cannot
be recorded `false`. Commit the driver extension before any output, as its
own commit.

Commits in order: registry + pre-registration → driver → pre-flight → full
→ analysis script → results → wrap-up.

---

## 4. Pre-registration (copied into PROMPT_ARCHITECTURE.md before scoring)

**Change.** Add a three-voices section (numbers / claims / pressure / gap)
to B before its READ. Everything else is unchanged.

**Expected to move.** The bullish side: the top 235 by score get more hits
and a higher median return. Ranking strength rises slightly. The bearish
side is roughly unchanged.

**Predicted flip count.** P7 against B draw 1, direction under ≤ −2 / ≥ +3:
**250–400 raw**, i.e. **~100–250 net** of B's 152 noise changes.

**Pre-flight stop rule (§2.5).** 150 train calls, stratified by
`stratum_map()` (S1–S5, proportional, at least one S4 call). If P7 and B
draw 1 disagree on direction on **under 20% of them** (implying under ~250
raw corpus-wide, under ~100 net), **stop. Do not run the full round.**
Also stop on any parse failure, `max_tokens` stop, `gap` or `pressure` value
outside its three allowed values, or a projected full cost over $40.

**Gates. All three must hold on train for P7 to earn its one look at tune.**
Each gate is computed against **both** B draws (§2.3a rule 3). A gate
holds only if it holds against both.

1. **Bullish hits, matched coverage.** P7's top 235 calls by score (ties by
   the seeded rule, seed 11) are right on **at least 47.0%** of calls.
   (B: 39.6% draw 1, 36.2% draw 2.) The 47% target comes from sampling
   alone: a 235-call hit rate near 40% moves about ±6 points by chance. It
   also clears B's own 3.4-point wobble.
2. **Ranking, non-inferiority.** The paired difference in rank correlation
   (P7 minus B, same calls, ticker-block bootstrap, 2,000 draws, seed 11)
   has its range's lower end **no worse than −0.03** (§2.3a rule 2).
3. **Bearish hits, matched coverage.** P7's bottom 191 calls by score are
   right on **at least 57.0%** of calls. That is B's 62.3% / 61.3% less the
   5-point tolerance tune condition 2 used.

**Falsified** if gate 1 fails: P7 did not produce a bullish signal, which
is its purpose. If gate 1 holds and gate 2 or 3 fails, the bullish gain was
bought elsewhere. Report which, and P7 does not go to tune.

**Predictions, not gates.** Top-235 median return above +1.28 (B draw 1's)
on both comparisons. Rank correlation 0.12–0.17. `gap` shares: claims_ahead
30–45%, aligned 35–50%, numbers_ahead 10–25%. `pressure` shares: answered
40–60%. P7 costs 10–25% more per
call than B.

---

## 5. The work

**5a. Pre-flight (~$4).** As §4. Report the stop-rule figures before
anything else. A stop is a result, not a failure of the run. Write the
wrap-up and end.

**5b. Full round (~$33).** All 1,217 train calls, one batch, custom ids
`P7__<ticker>_<date>`. Reuse the 150 pre-flight rows. Commit
`scores_p7.jsonl` (1,217 rows; assert).

**5c. The gates**, each against B draw 1 and B draw 2, one line each,
held or not.

**5d. Ambiguity rule — stop and ask, do not decide.** If gate 1's hit rate
lands within 3.4 points of 47.0% (43.6–50.4%), or gate 2's lower end lands
within 0.03 of −0.03 (−0.06 to 0.00), a single P7 draw cannot settle the
result, because B alone moves that much between identical runs. Report it
as ambiguous. Recommend a second P7 draw (~$33) in which both P7 draws
must pass. **Do not run it.**

**5e. Diagnostics, all $0 (PROMPT_ARCHITECTURE.md §2.4 applies in full).**
- Flip counts vs each B draw: raw, and net of B's per-stratum noise rate.
  Netted win rate under the P3 §7 guard, using B's noise win rate (~55%).
- 3×3 direction table, B draw 1 by P7.
- **The group that matters:** calls B scored neutral (−1 to +2) that P7
  put in its top 235. Count, hit rate, and median return, against the
  bullish base rate. This is the bullish counterpart of the finding that
  made B the champion. Report its mirror too: B's top 235 that P7 dropped.
- Hit rate and median return by `gap` value. Does `numbers_ahead` carry the
  bullish edge the mechanism predicts?
- Hit rate and median return by `gap` × `pressure` (3×3, with counts).
  Prediction: `numbers_ahead` + `answered` is the cell that carries the
  bullish edge.
- Fixed cuts (≥ +3, ≤ −2), labelled secondary. Score bucket table.
- Per stratum; by year with 2020 separate; noRead share; tokens and cost
  per call.
- Per-call diffs to `per_call_diffs.csv`.

---

## 6. Report step

**Scope boundary: report, do not decide.** Do not register P7 as champion,
do not score tune, do not run a second draw, do not write P9.

`wrap-ups/P7-three-voices-train-out.md`, `.md` only. Open with:

> On the 1,217 train calls, the three-voices prompt's top 235 calls were
> right ___% of the time, against B's 39.6% and 36.2% on its two draws; its
> ranking strength was ___ , a paired difference of ___ (range ___ to ___)
> over B draw 1 and ___ (range ___ to ___) over draw 2; its bottom 191 were
> right ___%. Of the three gates, ___ held against both draws. **P7 [earns
> its look at tune / was falsified / is ambiguous under §5d].**

Then the gates, one line each. Then the neutral-to-top-235 group. Then the
`gap` and `gap` × `pressure` breakdowns. Then the rest.

**Close with what it means, both ways.** If P7 held: a tune prompt with the
same gates at tune's N (242 / 161), one look. If it failed on gate 1: the
three-voices mechanism does not find winners in a transcript. P9 is next,
and the bullish question may need information from outside the transcript
(consensus, P4's XBRL). If ambiguous: the second-draw decision is Luis's.

Plain-language discipline is binding.

---

## 7. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up out.
**Budget stop:** the pre-flight always runs first. The full round is one
batch, all or nothing. If the projection breaches $45, stop and report, and
do not score a subset.
