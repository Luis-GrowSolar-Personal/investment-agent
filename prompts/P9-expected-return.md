# P9 — expected return in points, from B, on train

**Run ID:** `p9-expected-return-train`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P9-expected-return-train-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $32.** A 150-call pre-flight
(~$4) that decides whether the full round runs, then the rest of the
1,217 train calls (~$28 at B's measured ~$0.024 per call; P9's output
length should be close to B's). **Hard cap $40**, counted before every
`create()`. Luis approves the cap at Step 0; record it in
`progress.json` or stop and ask. **A second P9 draw is NOT approved
here.**

**Status: review closed 2026-09-26** (`prompts/P9-expected-return-review.md`:
three changes, applied). P7 bookkeeping is done. Clear to run.

---

## Framing

**What this run exists to answer.** B's score says *which* calls are bad.
It does not say *how* bad. On tune, B's score buckets from −4 through +1
had median returns between −4.6 and −8.3 in no particular order. A −4
was no worse than a −1. P9 asks the same model, reading the same way, for
a number with units instead of a label: "this stock will lag the S&P by
about 15 points over six months." If that number means what it says, it
grades severity. It also hands the rebuilt allocator a quantity it can
size with directly.

**What P9 is not.** It is not a new reading of the call. B's text is kept
word for word through READ. Only the final answer changes: SCORE (−5 to
+5) is replaced by EXPECTED RETURN (points versus the S&P, with a range).
This is the same kind of change as P6's arm C (v6's rubric, only the last
step changed), which is why it can be read cleanly.

**The honest possible outcome.** P9 may rank calls exactly as well as B
and grade severity no better. That is a pass on the gates below: the
same information in a more useful unit. The report must say plainly
which of the two P9 is, "better information" or "same information,
better units". The design session decides what that is worth.

**Already established; do not rediscover.**
- B is champion with two draws: `p6-output-format-round/scores_b.jsonl`
  and `b-champion-and-noise-floor/scores_b_rerun1.jsonl`. It ranks at
  0.130 / 0.099. Its bottom 191 are right 62.3% / 61.3% of the time and
  its top 235 39.6% / 36.2%.
- P7 failed on the bullish side (`wrap-ups/P7-three-voices-train-out.md`).
  P9 is **not** aimed at the bullish side. The top 235 is reported, not
  gated.
- Realized six-month returns vs the S&P on train, from
  `p6-output-format-round/calls.csv` → `fwd_rel_ret_tradeable` (1,217
  calls): median −2.9. The middle half runs −14.5 to +9.5. 71% of calls
  land within 20 points.

**Closed:** the ruler (182-day tradeable-entry return vs SPY), the company
split, §2.3a rules 1–6 (binding), everything in `PROMPT_ARCHITECTURE.md` §1.

**Read first:** `PROMPT_ARCHITECTURE.md` §2.3, §2.3a, §2.4, §2.5 and the P9
row; `wrap-ups/B-champion-and-noise-floor-out.md`;
`wrap-ups/P7-three-voices-train-out.md`; `prompts/P7-three-voices.md`
(this prompt reuses its structure); `analysis/p6_output_format_driver.py`
and `analysis/p7_three_voices_analysis.py` (extend; do not fork).

---

## 1. The candidate

`docs/prompts/candidates/EVALUATION_PROMPT_P9_expected_return.md`. It is
**identical to B from "You are an experienced investor" through the end
of READ.** Verify with a diff and report it. After READ it replaces B's
SCORE section with EXPECTED RETURN. The structured block replaces
`score` with `expectedReturn`, `rangeLow` and `rangeHigh`. `summary`,
`noRead` and `wrongIf` are kept, with their definitions reworded only to
refer to the estimate.

**One sentence in EXPECTED RETURN adds information B does not carry:**
"Most stocks land within 20 points of the S&P over six months." It is a
general market fact, true of this corpus (71%, above), and it is there to
stop the model defaulting to ±30 on every call. It is **not**
company-specific and is not an outcome of any call. Decided in review:
the base rate is kept. A second clause ("a typical call does not move the
odds much") was cut, because it pushed every estimate toward 0, the
failure the bunched stop rule exists to catch.

---

## 2. Ground rules

1. **Train only**, the same 1,217 calls as B's two draws (assert). No tune,
   no holdout, no DB writes.
2. **Scored like B:** model `claude-sonnet-4-6`, `max_tokens` 4096, no
   temperature parameter, same system/user construction, Batch API.
   Assert the request shape against B's `make_request()` with only the
   prompt text differing.
3. **Register** `P9-expected-return` in `VERSION_REGISTRY.json` (parent
   `P6B-minimal`) with its sha256 at Step 0. Run under
   `PROMPT_CANDIDATE=P9-expected-return`.
4. **Pre-registration first:** copy §4 into `PROMPT_ARCHITECTURE.md` §2.2
   under P9, dated, as its own commit, before the pre-flight batch. Mark
   the row "registered — running".
5. No threshold, mapping, scorer or price-cache change. Do not re-score B.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## 3. Step −1 / Step 0

As `prompts/P7-three-voices.md` §3, with run id `p9-expected-return-train`
and batch ids `batch_id_preflight`, `batch_id_full`. One process, no pipe
to `tail`, no background poller, batch id committed the instant
`create()` returns. Commits in order: registry + pre-registration →
driver → pre-flight → full → analysis script → results → wrap-up.

---

## 4. Pre-registration (copied into PROMPT_ARCHITECTURE.md before scoring)

**Change.** B's final answer, a −5..+5 score, becomes an expected
six-month return versus the S&P in points, with a low–high range. The
reading is unchanged.

**How P9's number is turned into B-comparable groups.** P9 has no
thresholds. Its **bottom 191** by `expectedReturn` are "bearish", its
**top 235** are "bullish", the rest "neutral" (§2.3a rule 1, matched to
B draw 1's counts). Ties are broken by the seeded rule, seed 11. Every
comparison with B uses these groups.

**Pre-flight stop rules (150 train calls, stratified by `stratum_map()`,
at least one S4).** P7's lesson (`PROMPT_ARCHITECTURE.md` §2.5): a new
output that behaves far from its prediction is a stop, even if it
parses. **Stop the run if any one of these holds:**
- any parse failure or `max_tokens` stop;
- `rangeLow ≤ expectedReturn ≤ rangeHigh` broken on more than 3 calls;
- **bunched:** the middle half of `expectedReturn` spans under 4 points,
  or there are fewer than 8 distinct values;
- **one-sided:** more than 85% of `expectedReturn` on the same side of 0;
- `noRead` on more than 10% of calls;
- projected full cost over $36.

**No disagreement threshold.** §2.5's "fewer than ~100 flips, stop" rule
does not apply. P9's value can come from its units even if it orders
calls exactly as B does, and arm C is the precedent. State this in the
pre-registration.

**Gates. All three must hold on train for P9 to earn its one look at
tune.** Gates 2 and 3 are computed against **both** B draws.

1. **Calibration sign (§2.3a rule 5).** Fit the slope of realized return
   on predicted `expectedReturn`, across all calls, with realized returns
   **clipped at ±50 points** (values beyond are set to ±50, not dropped).
   Its ticker-block range (2,000 draws, seed 11) must be **entirely above
   zero**. This rejects a number that points the wrong way, and nothing
   else. The clip level is fixed here and cannot move. Why: a few −100%
   wipeouts or multi-baggers would otherwise set the slope's sign by
   themselves, and resampling companies keeps the same outliers in most
   draws. Report the unclipped slope beside it; the gate is on the
   clipped figure.
2. **Ranking, non-inferiority (§2.3a rule 2).** The paired difference in
   rank correlation (P9 minus B, same calls) must have its range's lower
   end **no worse than −0.03**, against each B draw.
3. **Bearish hits, matched coverage.** P9's bottom 191 must be right on
   **at least 57.0%** of calls (B: 62.3% / 61.3%, less 5 points).

**Falsified** if gate 1 fails: the number does not mean what it says. If
gate 1 holds and gate 2 or 3 fails, the new unit cost information B had.
Report which one. P9 does not go to tune.

**Ambiguity rule — stop and ask, do not decide.** If gates 1 and 3 hold
and gate 2's lower end lands between −0.06 and 0.00 against either draw,
a single P9 draw cannot settle it. Report it as ambiguous and recommend a
second draw (~$30). **Do not run it.**

**The purpose check — severity — reported, not gated, with a
pre-registered reading.** Two numbers answer "does P9 grade how bad a bad
call is?":
- **(a) Within the bearish group:** the rank correlation between
  predicted and realized return inside P9's bottom 191, with its
  ticker-block range. Beside it, for context, the same figure inside B's
  bottom 191 on each draw (B's scores are heavily tied there, so expect
  near zero). On 191 calls the range is roughly ±0.14 wide, so beating
  B's near-zero figure means nothing by itself.
- **(b) Across fifths:** realized median return for each fifth of
  `expectedReturn`, lowest to highest. Beside it, B's median for each
  fifth of `score`, both draws.

**Reading.** P9 grades severity if (a)'s range **excludes zero** **and**
the lowest fifth's realized median is below the second fifth's. If
neither holds, P9 is "same information, better units". If only one
holds, say so and do not characterize it further.

**Predictions, not gates.**
- Median `expectedReturn` between +2 and +8 (both prompts default mildly
  positive). 55–75% of calls positive.
- The middle half of `expectedReturn` spans 6–15 points. Realized spans
  24.
- Slope 0.2–0.6 (clipped); unclipped may differ.
- 50–70% of outcomes land inside the stated range, against the 80% asked
  for. The model's ranges will be too narrow.
- Rank correlation 0.10–0.15.
- Cost within ±15% of B's per call.

---

## 5. The work

**5a. Pre-flight (~$4).** Report every §4 stop figure first. A stop is a
result: write the wrap-up and end.

**5b. Full round (~$28).** The remaining calls, one batch, custom ids
`P9__<ticker>_<date>`. Reuse the 150 pre-flight rows. Commit
`scores_p9.jsonl` (1,217 rows; assert).

**5c. Gates**, one line each, held or not, against each B draw where
comparative.

**5d. Diagnostics, all $0 (§2.4 in full).**
- The severity check (a) and (b), and its reading.
- The slope's value and range, clipped and unclipped. The clipped value
  becomes the allocator-side scale factor.
- Range coverage: the share of outcomes inside [rangeLow, rangeHigh].
  Also: do wider ranges go with bigger misses? Report the rank
  correlation of range width with the absolute error.
- Top 235: hit rate and median return, both B draws beside it. Not
  gated.
- Direction table (B draw 1 by P9 groups) and flips, raw and net of B's
  per-stratum noise. Win rates under the P3 §7 guard.
- The distribution of `expectedReturn`: median, middle half, share
  positive, and the 10 most common values.
- Per stratum, by year with 2020 separate, noRead share, tokens and cost
  per call. Per-call diffs to `per_call_diffs.csv`.

---

## 6. Report step

**Scope boundary: report, do not decide.** No champion change, no tune,
no second draw, no mapping or allocator work.

`wrap-ups/P9-expected-return-train-out.md`, `.md` only. Open with:

> On the 1,217 train calls, the expected-return prompt's number pointed
> the right way (slope ___, range ___ to ___); it ranked calls at ___, a
> paired difference of ___ (range ___ to ___) against B draw 1 and ___
> (range ___ to ___) against draw 2; its bottom 191 were right ___%. Of
> the three gates, ___ held against both draws. On severity it is
> **[better information / same information, better units / mixed]**:
> inside the bearish group it ranked outcomes at ___ against B's ___ /
> ___, and its lowest fifth returned a median ___ against ___ for the
> second fifth. **P9 [earns its look at tune / was falsified / is
> ambiguous].**

Then the gates, the severity reading, the distribution and calibration
figures, and the rest.

**Close with what it means, both ways.** If P9 holds with better
information, tune is next with the same gates at tune's counts (242 /
161). If it holds with the same information in better units, whether to
take it to tune is Luis's decision. It would be the allocator rebuild's
input format, not a better analyst. If it is falsified, B's −5..+5
score stays the analyst's output and severity remains an open gap.

Plain-language discipline is binding.

## 7. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. **Budget
stop:** the pre-flight always runs first. The full round is one batch,
all or nothing. If the projection breaches $40, stop and report, and do
not score a subset.
