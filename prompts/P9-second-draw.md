# P9 — second draw on train, to settle the ambiguity

**Run ID:** `p9-second-draw`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P9-second-draw-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $30.** The P9 prompt, unchanged,
re-scored on all 1,217 train calls at the measured $0.0248 per call. **No
pre-flight** (P9's output already passed one, and the first draw parsed
1,217 of 1,217). **Hard cap $36**, counted before every `create()`. Luis
approves the cap at Step 0; record it in `progress.json` or stop and ask.

---

## Framing

**What this run exists to answer.** P9's first draw passed all three gates
and both severity conditions. It was declared **ambiguous** under the rule
pre-registered in `PROMPT_ARCHITECTURE.md` §2.2 (P9). Against B draw 1,
gate 2's lower end was −0.016, inside the −0.06 to 0.00 band where a
single draw cannot settle it. That rule named its own remedy: a second P9
draw, and **both P9 draws must pass**. This run is that remedy and nothing
else.

**Already established; do not rediscover.**
`wrap-ups/P9-expected-return-train-out.md`, all of it. First draw: ranking
0.171; paired over B +0.040 (−0.016 to +0.097) vs draw 1 and +0.071
(+0.016 to +0.126) vs draw 2; clipped slope 0.662 (0.332 to 0.959); bottom
191 right 62.8%; within-bearish ranking 0.257 (0.094 to 0.373); fifths
−9.76 / −5.52 / −0.95 / −1.63 / +1.54.

**Closed; do not re-open:** the P9 prompt text (sha
`a752e6b1b2a00b755396a526bfe3007e788ebfb6a93b32076754cd0e078c06a5`), the
gates, the ±50 clip, the matched-coverage groups (bottom 191 / top 235,
seed 11), the severity reading, the tolerance −0.03, and §2.3a rules 1–6.
**Nothing in §4 of `prompts/P9-expected-return.md` is re-chosen here.**

**Read first:** `prompts/P9-expected-return.md` §2–§5;
`wrap-ups/P9-expected-return-train-out.md`; `analysis/p6_output_format_driver.py`
(the `--p9` path and the B `--rerun` path, which is the model for this
one); `analysis/p9_expected_return_analysis.py`. Extend both; do not fork.

---

## Ground rules

1. **Train only**, the same 1,217 calls (assert). No tune, no holdout, no
   DB writes.
2. **Scored exactly as P9 draw 1:** the same prompt file (driver asserts
   the sha above), model `claude-sonnet-4-6`, `max_tokens` 4096, no
   temperature parameter, same request construction, Batch API. Assert
   request-shape equality on 25 sampled calls, as the B re-run did.
3. **Guard:** `PROMPT_CANDIDATE=P9-expected-return` (already registered).
4. **Do not overwrite draw 1.** Custom ids suffixed `__r1`. Cache
   `analysis/data/evals/P9-expected-return_claude-sonnet-4-6_rerun1/`
   (gitignored). Commit `scores_p9_rerun1.jsonl`.
5. **Report, do not decide.** No champion change, no tune, no registry
   status change, no ledger entry.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0

State in `analysis/data/run_state/p9-second-draw/`. `progress.json` is the
very first action. It records the prompt sha, driver commit, step status,
`next_action`, `notes[]`, and the approved cap. `batch_id_full` is
committed the instant `create()` returns. One process, output to the
terminal, no pipe to `tail`, no background poller. Clean tree; hard stop
if `git_dirty` cannot be recorded `false`. Driver extension committed
before any output, as its own commit.

Before scoring, as its own commit: set the P9 row in
`PROMPT_ARCHITECTURE.md` §2.2 to **"draw 1 ambiguous (gate 2 lower end
−0.016 vs draw 1); second draw running"**, with a pointer to this prompt.

---

## Step 1 — the second draw (~$30)

Score all 1,217 calls in one batch. Output `scores_p9_rerun1.jsonl`
(1,217 rows; assert). Report parse failures, `max_tokens` stops and
range-order violations. Any of those above 3 calls → stop and report.

## Step 2 — the verdict, $0

Compute every §4 quantity for **P9 draw 2**, exactly as for draw 1, and
put the two draws side by side.

**The pre-registered rule, stated once.** P9 earns its look at tune only
if **each** of its two draws holds **all three** gates against **each** of
B's two draws. That is 2 P9 draws × 3 gates, with gates 2 and 3 checked
against both B draws.
- Gate 1: clipped slope range entirely above zero.
- Gate 2: paired rank difference (P9 minus B) with its lower end ≥ −0.03.
- Gate 3: bottom 191 right ≥ 57.0%.

Report a 2×3 table, P9 draw × gate, with the value, range and held/failed
for each B draw. **One line of verdict:**
- **HOLDS** if every cell holds;
- **FALSIFIED** if any gate fails on either draw.

**No further ambiguity rule applies.** This draw is the remedy; there is
no third.

**Severity, both draws, same pre-registered reading.** Severity holds if
**both** draws show: (a) the within-bottom-191 rank correlation with its
range excluding zero, **and** (b) the lowest fifth's realized median below
the second fifth's. Report "better information" only if both draws meet
both conditions. Otherwise report "same information, better units" or
"mixed", saying which condition failed on which draw.

## Step 3 — P9's own noise floor, $0

The same measurements the B re-run produced, now for P9 draw 1 against
draw 2. If P9 goes forward, every later candidate will be netted against
these.
- How often a call moves between the bottom 191 / middle / top 235 groups.
  Pooled and per stratum, with Wilson ranges. The 3×3 table.
- `expectedReturn` moves by ≥ 3 points and by ≥ 5 points: the share of
  calls.
- Noise win rate among group changes where exactly one draw was right.
- Paired rank-correlation difference, draw 1 minus draw 2, with its
  ticker-block range and half-width. **The half-width is the ranking
  tolerance a P9-derived candidate would inherit.**
- The clipped slope on each draw, and its difference.

Beside each figure, give B's equivalent from
`wrap-ups/B-champion-and-noise-floor-out.md`: 12.5% group changes, 0.031
rank difference, 0.027 half-width. Say plainly whether P9 is steadier or
shakier than B.

**Also report:** P9's two draws averaged per call. Give that average's
ranking, clipped slope, and bottom-191 hit rate, labelled **"diagnostic —
not a gate, not a candidate"**. It shows what scoring each call twice
would buy in live use, where the cost is trivial.

---

## Report step

**Scope boundary: report, do not decide.**

`wrap-ups/P9-second-draw-out.md`, `.md` only. Open with:

> On a second draw of the same 1,217 train calls, the expected-return
> prompt ranked at ___ (draw 1: 0.171), a paired difference over B of ___
> (range ___ to ___) against B draw 1 and ___ (range ___ to ___) against
> draw 2; its clipped slope was ___ (range ___ to ___) and its bottom 191
> were right ___%. Across both P9 draws, ___ of 6 gate checks held. **P9
> [HOLDS / is FALSIFIED] on train.** On severity it is **[better
> information / same information, better units / mixed]** across both
> draws. Between its own two draws P9 changed group on ___% of calls (B:
> 12.5%) and its ranking moved by ___ (B: 0.031).

Then the 2×3 gate table, the severity table for both draws, the noise
figures beside B's, and the averaged-draw diagnostic.

**Close with what it means, both ways.** If P9 holds, it goes to tune
under a separate prompt, one look, with the same gates at tune's counts
(bottom 161 / top 242) against B's single tune draw. If it holds with
better information, it would then become research champion; that is
Luis's decision, not this run's. If it is falsified, B stays champion.
P9's first-draw severity result is recorded as a single-draw finding,
unconfirmed.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up
out. **Budget stop:** one batch, all or nothing. If the projection
breaches $36, stop and report, and do not score a subset.
