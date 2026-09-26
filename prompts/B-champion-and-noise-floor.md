# B as research champion, and B's own noise floor

**Run ID:** `b-champion-and-noise-floor`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/B-champion-and-noise-floor-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $30.** Step 1 is $0 (files only).
Step 2 re-scores all 1,217 train calls with the minimal prompt, unchanged, at
the measured ~$0.0236 per call ≈ $29, plus a 30-call pre-flight (~$0.70).
**Hard cap $35**, counted before every `create()`. Luis has approved $35;
record it in `progress.json` at Step 0 or stop and ask.

---

## Framing

**What this run exists to answer.**

1. **Step 1 ($0):** write down, in the files future sessions actually read,
   the decisions of 2026-09-25 and 2026-09-26. The minimal prompt (B) becomes
   the incumbent every new candidate is compared against. v6 stays in
   production.
2. **Step 2 (~$29):** how often does B change its own answer when asked the
   same question twice, and how far does its ranking strength move between
   two identical runs? No later candidate (P7, P9) can be read without these
   two numbers.

**Already established; do not spend budget rediscovering it.**

- B's train result: `wrap-ups/P6-output-format-round-out.md`. Tune:
  `wrap-ups/P6B-tune-confirmation-out.md`. Portfolio check against the
  same-model comparator: `wrap-ups/P6B-confound-and-concentration-out.md`.
- The decided plan: `docs/handoffs/2026-09-24-state-of-play.md` §5.
- The agreed amendments, in order: `docs/handoffs/2026-09-25-next-steps-proposal.md`,
  `2026-09-26-next-steps-review.md`, `2026-09-26-next-steps-review-comments.md`,
  `2026-09-26-next-steps-review-reply.md`. **The reply is final.** Where the
  documents disagree, the later one wins.

**Closed; do not re-open:** production cut-over (not on this list); the
≤ −2 / ≥ +3 mapping; company split as the promotion gate; the lucky-cached-
draw question (closed, see 1e); everything in `PROMPT_ARCHITECTURE.md` §1.

**Read first:** the four handoff documents above; state of play §0, §2, §4,
§5; `PROMPT_ARCHITECTURE.md` §2.2–2.6; `prompts/P6-output-format-round.md`
§5b, §7 (noise arm and netting; reused); `prompts/P3-guidance-ledger.md` §7
"The netting rule"; `analysis/p6_output_format_driver.py` (extend with a
`--rerun` path; do not fork); `analysis/gate_runner.py` `append_to_ledger()`.

---

## Ground rules

1. **Step 1 makes no API calls and no DB writes.** File edits only.
2. **Step 2 makes Claude API calls** (the Batch API, as the P6 run did). **No
   DB writes. No holdout. No tune.** Train only: the same 1,217 calls in
   `analysis/data/run_state/p6-output-format-round/scores_b.jsonl`.
3. **B is scored exactly as the original run scored it.** Same prompt file
   (sha `d1fa5e53fd743412503a0ba316d21b49a061e1ccf3e2064478bb83dfe9b430ab`,
   asserted by the driver), same model `claude-sonnet-4-6`, same
   `max_tokens` (4096), same system/user construction, **same absence of a
   temperature parameter.** Assert request-shape equality against a sample of
   `raw_arm_b.jsonl` before submission. A noise floor measured with
   different settings measures nothing.
4. **Do not overwrite the original B cache or scores.** The re-run writes to
   `analysis/data/evals/P6B-minimal_claude-sonnet-4-6_rerun1/` (gitignored
   like the others) and commits `scores_b_rerun1.jsonl`.
5. **Guard:** `PROMPT_CANDIDATE=P6B-minimal` via `version_guard.py` before
   call one. Record it.
6. **Do not change** `promoted_version` for any artifact, the scorer, the
   price cache, the mapping, or any threshold.
7. **Do not write P7's or P9's pre-registration.** Step 1 records the
   *rules* those pre-registrations must follow. The filled-in
   pre-registrations come in the next session, with step 2's numbers.

A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop.

---

## Step −1 — resume protocol

State in `analysis/data/run_state/b-champion-and-noise-floor/`. Write
`progress.json` as the **very first action**: `prompt_sha256`,
`driver_commit`, per-step status, `next_action`, `notes[]`, the approved cap.
Append to `findings.md` the moment a finding is established. Batch ids
(`batch_id_preflight`, `batch_id_rerun`) are committed the instant
`create()` returns. **One process, output to the terminal, no pipe to
`tail`, no background poller.** The P6 run lost a batch id that way.

Matching `prompt_sha256` → resume, skip done steps, and pick up an existing
batch id rather than resubmitting. A changed prompt archives the old state.

## Step 0 — hygiene

Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
change committed as its own commit before any output. Record the $35
approval.

---

## Step 1 — bookkeeping, $0 (one commit)

**1a. `docs/architecture/VERSION_REGISTRY.json`.**
- Under `artifacts.evaluation_prompt`, add a `research_champion` block:
  `version: "P6B-minimal"`, the sha, `since: "2026-09-25"`, `gate_ledger_ref`
  (the entry from 1b), and a note that production stays on v6
  (`promoted_version` unchanged) and that cut-over is a separate, later
  decision.
- Change P6B-minimal's candidate `status` from `candidate` to
  `research_champion`.
- Record the portfolio-side comparator: **A0′** (v6 on `claude-sonnet-4-6`
  through the overlay), with its manifest path from the confound run. The
  archived v6 verdicts (R, A0) are not a baseline for anything new.
- Run `python3 analysis/whats_live.py` afterwards; it must not error. Report
  what it prints for the evaluation prompt.

**1b. `analysis/data/gate_ledger.json` — entry 2, P6B-minimal vs v6.**
Append with `append_to_ledger()`, built by hand; do not run the analyst
gate, which measures the old metric. Shape (reply Q1):
- `change_class: "analyst"`, `change_class_detail: "prompt"`,
  `champion: "v6 (claude-sonnet-4-6)"`, `challenger: "P6B-minimal"`.
- `primary_metric`: rank correlation of score against the 182-day
  tradeable-entry return vs SPY.
- `delta`: paired difference over v6, with its ticker-block range as the
  noise basis.
- A `metrics` object keyed by ruler: train, tune and pooled rank
  correlation; bearish count and precision; swap median; end-to-end B3 vs
  A0′ final value and gain per point of drawdown, including leave-one-out
  (all 16 ahead on drawdown and gain per point; final value flips without
  FSLR). **Every figure cites its wrap-up and key.**
- `holdout: "locked — not yet looked at"`.
- `final_verdict: "RESEARCH_CHAMPION"` — not `PROMOTE`.
- `qualifiers` (both stated): the final-value margin over A0′ is thin and
  rests on FSLR; gain per point of drawdown was not in the run's
  pre-registration, though it is the gate's §3.2 metric.
- `amend_after: "b-champion-and-noise-floor step 2 — B's measured noise
  floor"`. Step 2c fills it.

**1c. `docs/architecture/PROMPT_ARCHITECTURE.md`.**
- §2.2 queue table: P1 → closed (superseded by B); C → closed; P6 → done
  (B held on tune; research champion); P7 → next, from B; **add rows** for
  P9 (expected return in percent, from B) and the model gate on B (§2.2b
  equivalence hurdle, last). P8 → after P7/P9. P6D → deferred to the
  allocator rebuild. Replace P7's "from whichever of arm B or arm C P6
  favours" with "from B".
- §2.4 / §2.5: the flip-count ceiling and the pre-flight threshold apply to
  **net** flips (raw minus the incumbent's own noise flips), never raw. v6's
  noise floor is ~17% (tune 17.7%, train 16.7%). For B-derived candidates
  the incumbent's floor is B's, measured in step 2; leave a marked
  placeholder that step 2d fills.
- New subsection **§2.3a — rules every B-derived pre-registration follows**
  (decided 2026-09-26; the reply is the source):
  1. **Matched coverage, both sides.** Bullish: the candidate's top N calls
     by score against B's top N, N = B's bullish count at ≥ +3 on the same
     split (train 235, tune 242). Bearish: bottom N, N = B's bearish count at
     ≤ −2 (train 191, tune 161). Ties broken by the seeded rule. The fixed
     cuts are reported, labelled secondary.
  2. **Ranking tolerance.** The paired difference in rank correlation
     (candidate minus B, same calls) must have its range's lower end no worse
     than **−0.03 (placeholder; step 2d replaces it)**.
  3. **Two baseline draws.** Every candidate is compared with **both** B runs
     (original and re-run) and both differences are reported. Beating one
     and not the other is a tie.
  4. **End-to-end check vetoes, never picks.**
  5. **For P9 (expected return):** the gate is a positive slope of realized
     on predicted return, with its range excluding zero. The slope's value
     (the allocator-side scale factor) and realized medians by fifths are
     reported, not gated. Predicted slope 0.2–0.6, written as a prediction.
  6. **The most-recent-year result** for the model gate is a diagnostic,
     not a gate (~170 calls).
- §2.6 / P8: add one sentence. The time split (iterate 2020–2022, screen
  2023–2024, on train companies only) constrains P8's generator. The
  company split is the promotion gate for its survivors. "Holdout 2025" is
  dropped; the 53-company holdout is the holdout.

**1d. `docs/handoffs/2026-09-24-state-of-play.md`.** Two edits, each marked
`(amended 2026-09-26)`; no other changes, no republish in this run:
- §5.4: add "The end-to-end check can veto a candidate; it never picks one."
- §7: move the lucky-cached-draw item to closed: v6 is no longer the
  comparator, and its only consequence (B's result is conservative) is
  already recorded.

**1e. Propagation check.** After the commit, grep the repo for any file
that still calls P1 "next" or "run first", or names v6 as the incumbent for
new candidates. List the hits in the wrap-up. Fix only the files named in
1a–1d; report the rest.

Commit: `docs: B research champion — registry, ledger entry 2, PROMPT_ARCHITECTURE queue and §2.3a rules, state-of-play amendments`.

---

## Step 2 — B's noise floor, ~$29 (highest-value step if budget is short)

### 2a. Pre-flight — 30 train calls, ~$0.70

Stratified across S1–S4 via `stratum_map()`. Structured block parses;
`score` in [−5, +5]; `noRead` boolean; no `max_tokens` stops; projected
full cost under $32. Any failure → stop and report.

### 2b. Re-score all 1,217 train calls, one batch

Same custom-id scheme, suffixed `__r1`. Output `scores_b_rerun1.jsonl`
(1,217 rows; assert). Reuse the pre-flight's 30 rather than scoring them
twice.

### 2c. What to measure, per stratum and pooled, Wilson ranges on rates

Pair each call's original score (`scores_b.jsonl`) with its re-run score.

1. **Score moves ≥ 1** — share of calls.
2. **Score moves ≥ 2** — share of calls.
3. **Direction changes** under ≤ −2 / ≥ +3 (bearish / neutral / bullish).
   **This is the rate every P7/P9 flip count is netted against.** Also
   report the 3×3 table: original direction by re-run direction.
4. **Noise win rate** per stratum, for the netted win rate (P3 §7 rule,
   unchanged): among direction changes where exactly one answer was right on
   the 182-day tradeable-entry ruler, how often the original won.
5. **Rank correlation, run against run.** Each run's rank correlation with
   the 182-day return, and the **paired difference (original minus re-run)
   with a ticker-block range**, 2,000 draws, same seed convention as P6.
   **This is the number that replaces −0.03 in §2.3a rule 2.** State the
   replacement explicitly: the tolerance is the negative of the range's
   half-width, rounded out to two decimals.
6. **Matched-coverage hit rates, both runs.** Top 235 and bottom 191 by
   score, per run, with hit rates. The spread between the two runs is how
   much the §2.3a rule 1 comparison moves from B's own instability.
7. **noRead** share per run, and how often it changes.

**Predictions, not gates:** direction changes 10–18% (v6 was ~17%, and B's
shorter output may wobble less); score moves ≥ 1 on 35–55%; paired
rank-correlation half-width 0.02–0.04.

### 2d. Fill the placeholders (second commit)

- `PROMPT_ARCHITECTURE.md` §2.3a rule 2: replace −0.03 with the measured
  tolerance, citing `findings.md` and the results key.
- `PROMPT_ARCHITECTURE.md` §2.4 / §2.5: B's direction-change rate, per
  stratum, as the incumbent's noise floor.
- `gate_ledger.json` entry 2: fill `amend_after` with the measured floor,
  the rank-correlation band and the direction-change rate.
- Register the re-run as B's **second baseline draw** in
  `VERSION_REGISTRY.json` → the research_champion block, with the path to
  `scores_b_rerun1.jsonl`.

Commit: `b-noise-floor: B re-run on train, measured floor filled into §2.3a, §2.4/2.5, ledger entry 2`.

---

## Rules carried forward

- Every figure cites its source file and key. Name the kind of every number
  (rate across calls, median, rank correlation, ticker-block range).
- The noise floor is a **counting** correction. It does not shift the rank
  correlation or the hit rates; it widens their ranges (P6 §7).
- Train exclusions exactly as the P6 run applied them (Paramount, corrupt
  prices); assert the same 1,217 calls.

---

## Report step

**Scope boundary: report, do not decide.** Do not write P7's or P9's
pre-registration, do not score anything else, do not promote.

`wrap-ups/B-champion-and-noise-floor-out.md`, **.md only** (a CLI wrap-up).
Open with this sentence, filled in:

> Asked the same 1,217 train calls twice, the minimal prompt changed its
> direction (bearish / neutral / bullish) on ___% of them (range ___–___%),
> against v6's ~17%; its score moved by at least one point on ___% and by
> two or more on ___%. Its ranking strength was ___ and ___ on the two runs,
> a paired difference of ___ (range ___ to ___), so a candidate must not
> rank worse than B by more than ___ . Step 1's bookkeeping landed in
> commit ___.

Then: the per-stratum table; the 3×3 direction table; noise win rates;
matched-coverage hit rates for both runs; the list of files changed in step
1 and the 1e propagation hits.

**Close with what it means for P7**, stated both ways: if B's direction
changes are well under v6's, P7's flip counts can be read on fewer changed
calls, and a P7 pre-flight (~150 calls) is enough to decide whether a full
round is worth $45. If they are at or above v6's, P7 needs a larger
pre-flight, and a round flipping under ~200 calls cannot be told apart from
B re-running itself.

Plain-language discipline is binding.

---

## Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. Commit
`scores_b_rerun1.jsonl` as it lands. **Budget stop:** step 1 is $0 and runs
first regardless. Step 2 is one batch, all or nothing. If the projection
breaches $35, stop and report, and do not score a subset.
