# P9 close-out, and averaged B vs averaged P9 — $0

**Run ID:** `p9-close-and-averaged`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P9-close-and-averaged-comparison-out.md`
**Cost: $0.** No API calls, no DB writes, no scoring. Reads existing
score files only.

---

## Framing

**What this run exists to answer.**

1. **Record P9's result** where future sessions read it. P9 was falsified
   on train: draw 2 failed ranking non-inferiority against both B draws.
   Its severity finding held on **both** draws. It grades how bad a bad
   call is; B cannot.
2. **One comparison nobody has made:** B's two draws averaged per call,
   against P9's two draws averaged per call, on the same 1,217 calls. In
   live use, scoring each call twice costs pennies. If averaged P9 is at
   least as good as averaged B at ranking, it brings severity with it, and
   "score twice and average" becomes a candidate worth a pre-registered
   tune test. If not, P9 is closed.

**This is an after-the-fact look at train data.** All four draws are
already scored and already seen. It can justify a pre-registered test on
tune. It cannot promote anything, and it cannot re-open P9's verdict.

**Already established; do not rediscover.**
- `wrap-ups/P9-second-draw-out.md` (all), `wrap-ups/P9-expected-return-train-out.md`,
  `wrap-ups/B-champion-and-noise-floor-out.md`.
- Draw files, 1,217 rows each:
  - B: `p6-output-format-round/scores_b.jsonl`,
    `b-champion-and-noise-floor/scores_b_rerun1.jsonl`
  - P9: `p9-expected-return-train/scores_p9.jsonl`,
    `p9-second-draw/scores_p9_rerun1.jsonl`
- Single-draw figures: B ranks 0.130 / 0.099; P9 0.171 / 0.111.
  P9 averaged ranks 0.140 (`p9-second-draw` → `averaged_draw_diagnostic`).

**Read first:** the three wrap-ups above;
`analysis/p9_second_draw_analysis.py` and
`analysis/p9_expected_return_analysis.py` (extend; do not fork).

---

## Ground rules

1. **$0.** No API calls, no DB writes, no cache refresh.
2. **Do not change** B's champion status, the promoted version, any gate,
   tolerance, mapping or clip, or §2.3a rules 1–6.
3. **The reading in Step 2 is fixed here, before any number is computed.**
   Do not add conditions after seeing results.
4. Report, do not decide.

A diagnostic that contradicts an expectation here is a finding, not a
reason to stop.

## Step −1 / Step 0 — git bookends (CLAUDE.md standing rule 9)

State in `analysis/data/run_state/p9-close-and-averaged/`. `progress.json`
is the very first action. **Then, before the clean-tree check:**

- Commit this prompt file if untracked or modified, as its own commit
  (`prompt: P9 close-out and averaged comparison`).
- `CLAUDE.md` carries one uncommitted addition, standing rule 9 "Git
  bookends". It was written between runs, and the previous run correctly
  left it alone. Check that the diff is only that rule, then commit it as
  its own commit (`CLAUDE.md: git bookends rule for CLI prompts`).
  **Anything else modified → stop and report.**

Then clean tree; hard stop if `git_dirty` cannot be recorded `false`.
Analysis-script extension committed before any output, as its own commit.

---

## Step 1 — bookkeeping, $0 (one commit)

**1a. `VERSION_REGISTRY.json`.** P9-expected-return candidate: `status` →
`falsified`, `falsified: "2026-09-26"`. Add a `detail` naming the
reason: draw 2 ranking non-inferiority, −0.020 (−0.071 to +0.032) vs B
draw 1 and +0.011 (−0.039 to +0.059) vs B draw 2. Add a `finding`: the
severity result holds on both draws. Keep the sha. Run
`python3 analysis/whats_live.py`; it must exit 0.

**1b. `gate_ledger.json` — entry 4, P9 vs B.** Shaped like entries 2 and 3.
- The 2×3 gate table from `wrap-ups/P9-second-draw-out.md`.
- `final_verdict: "FALSIFIED"`.
- `final_reason`: ranking non-inferiority failed on draw 2. P9 swings
  between identical runs by 0.060, against B's 0.031.
- `findings_of_record`: severity confirmed on two draws (within bottom 191:
  0.257 and 0.184, both ranges above zero; lowest fifth below second on
  both). P9's own noise floor (17.0% group changes; ranking difference
  0.060, half-width 0.037).
- `cost_usd`: 60.31 (both draws).
- Every figure cites its wrap-up and key.

**1c. `PROMPT_ARCHITECTURE.md`.**
- §2.2 P9 row → **falsified 2026-09-26 (train, two draws; ranking
  non-inferiority failed on draw 2; severity confirmed on both)**.
- Under the P9 block, a dated **Result** paragraph of at most six lines:
  the verdict; the severity finding, stated as **confirmed on two draws**
  (not "unconfirmed"); P9's higher run-to-run wobble as the cause; and a
  pointer to this run's Step 2 for the averaged comparison.

Commit: `docs: P9 falsified on train (ranking, draw 2); severity confirmed on two draws — registry, ledger entry 4, PROMPT_ARCHITECTURE`.

---

## Step 2 — averaged B vs averaged P9, $0 (the highest-value step)

**Construction.**
- **Averaged B** = the mean of B's two `score` values per call. It takes
  half-points, e.g. −2.5.
- **Averaged P9** = the mean of P9's two `expectedReturn` values per call.
- Same 1,217 calls (assert). Ties broken by the seeded rule, seed 11.
- Groups by matched coverage, as always: bottom 191 and top 235 by each
  averaged number.

**Compute, for each averaged number:**
1. Rank correlation with the 182-day tradeable-entry return vs SPY, with
   its ticker-block range (2,000 draws, seed 11).
2. **Paired difference, averaged P9 minus averaged B**, with its range.
   **This is the number the reading rests on.**
3. Bottom 191 hit rate and median return; top 235 hit rate and median.
4. Severity: rank correlation inside each bottom 191, with range; realized
   median by fifths.
5. Clipped slope (±50) for averaged P9. For averaged B, report the slope
   of realized return on averaged score, labelled as not comparable in
   units.
6. How much averaging helped each prompt: averaged ranking minus the mean
   of its two single-draw rankings.

**Pre-registered reading, fixed now.** Averaged P9 is **worth a tune
test** if the paired difference (averaged P9 minus averaged B) has its
range's lower end **no worse than −0.03**. That is the same tolerance
every B-derived candidate faces, and P9's severity is already confirmed
on two draws. In that case, also state whether the range **excludes
zero**: if so, it is "better ranking too", otherwise "equal ranking, plus
severity". If the lower end is below −0.03, P9 is **closed**: averaging
does not rescue it.

**Say plainly what this cannot show.** The noise of an *averaged* draw
cannot be measured without a third and fourth draw. The averaged
figures therefore carry no run-to-run band of their own. Four draws
already seen is not the same as a fresh test. That is why a positive
reading justifies only a pre-registered tune test.

---

## Report step

**Scope boundary: report, do not decide.** Do not write the tune
pre-registration, do not score anything, do not change champion status.

`wrap-ups/P9-close-and-averaged-comparison-out.md`, `.md` only. Open with:

> Averaged over two draws per call, the minimal prompt ranked at ___ and
> the expected-return prompt at ___, a paired difference of ___ (range ___
> to ___). Under the reading fixed before the run, averaged P9 is
> **[worth a tune test — better ranking too / worth a tune test — equal
> ranking, plus severity / closed]**. Inside the bearish group, averaged
> P9 ranked outcomes at ___ (range ___ to ___) against averaged B's ___
> (range ___ to ___). Step 1's bookkeeping landed in commit ___.

Then a table of both averaged numbers side by side, with every figure
from 2.1–2.6, then the single-draw figures beside them for context.

**Close with what it means, both ways.** If worth a tune test: the next
prompt pre-registers "P9, scored twice and averaged" against "B, scored
twice and averaged" on tune. That needs one more B draw and two P9 draws
on tune, about $85, and is P9's one look. If closed: B stays champion;
severity stays an open gap, recorded as something P9's wording could do
but not steadily enough.

Plain-language discipline is binding.

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure (file and key). One prompt in, one wrap-up out.
**Finish with `git push`** of `sweep/db-corpus-baseline` after the wrap-up
commit, and report the pushed hash. If the push fails, say so and never
force.
