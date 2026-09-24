# P6 — the output-format round: v6 vs a minimal prompt vs a continuous score

**Run ID:** `p6-output-format-round`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P6-output-format-round-out.md`
**Registered:** `docs/architecture/PROMPT_ARCHITECTURE.md` §2.2, P6, 2026-09-24.
**Do not re-litigate a decision that carries a citation to that block.**

**Cost: THIS RUN SPENDS REAL MONEY — about $105.** Two candidate arms on train
(~$45 each at the measured $0.0380/call), one pure-noise arm (~$5), one
pre-flight (~$8). **Hard cap $130, counted before every `create()`.** Money
commits at batch submission. Luis has approved $130 for this run; if that
approval is not recorded in `progress.json` at Step 0, stop and ask.

**Read first, in this order:** `docs/handoffs/2026-09-23-state-of-play.md` §0,
§2, §3.1–3.3, §4; `docs/architecture/PROMPT_ARCHITECTURE.md` §1, §2.2 (P6
block), §2.3–2.5; `docs/handoffs/2026-09-20-state-of-play.md` §0 (the money
ruler and the tradeable entry); `prompts/P3-guidance-ledger.md` §5f (the
noise arm, reused as-is) and §2 (ground rules, reused as-is);
`analysis/p3_guidance_ledger_driver.py` (batch machinery, stratum map,
alias resolution — import, do not rewrite); `analysis/r4b_tradeable_entry_driver.py`
(`rel_ret` arm B is the tradeable-entry forward return — reuse it);
`wrap-ups/test4-noise-floor-v6-rerun-out.md`.

---

## WHAT THIS RUN BUYS

Every candidate to date added information to the prompt and none paid. This
round changes the prompt's **shape** and holds its inputs fixed. It answers
two questions that have never been asked:

1. **Does the v6 rubric find signal, or lose it?** Arm B is a control with no
   rubric at all. If B matches A, 190 lines of rubric buy nothing and future
   iteration starts from 20 lines.
2. **Is there anything in the neutral pile?** 58% of v6's answers are Hold
   with zero edge. Hold is what the decision matrix emits for *Intact + no
   stumble* — a rule applied after the read. Arm C keeps the rubric and
   removes the matrix as the output. If the model's score ranks forward
   returns, the neutral pile was compression, not ignorance.

**Most likely outcome:** a ranking result on arm C that the three-bucket
ruler could never have shown, and a clean answer on the rubric. **Less
likely:** a headline accuracy move. Anyone authorizing $130 for the second
alone is authorizing the wrong run.

---

## 1. The three arms

| arm | prompt | what it is |
|---|---|---|
| **A** | `docs/EVALUATION_PROMPT.md` (v6, registry-promoted, sha `357b6b0b…`) | incumbent — **already scored on train**; do not re-score except for the noise arm |
| **B** | `docs/prompts/candidates/EVALUATION_PROMPT_P6B_minimal.md` | **the control.** No rubric. Objective, constraint, a −5..+5 score with `noRead`, a 3–5 sentence read, one framing question. Not a v6 derivative. |
| **C** | `docs/prompts/candidates/EVALUATION_PROMPT_P6C_score.md` | v6 with **only** the RECOMMENDATION section replaced by a SCORE section and `recommendation` replaced by `score`/`noRead`/`wrongIf` in the structured block. Every other v6 section and field is intact. |

**Both candidate files are already written and committed. Do not edit them.**
If you believe one is defective, stop and report; do not fix it in flight.
Diff C against v6 and include the diff in the wrap-up — it must touch nothing
but the RECOMMENDATION section, the structured block, and the header.

---

## 2. Ground rules

All of `prompts/P3-guidance-ledger.md` §2 applies unchanged — train only after
alias resolution, holdout untouched, version guard, pinned model
`claude-sonnet-4-6`, corpus_v2 price cache by exact string, WOLF and SPWR
excluded entirely, Paramount (`PARA`) excluded per the 2026-09-23 state of
play §4.1, no scorer edits, macOS/zsh. Plus:

1. **Two candidate prompts and one incumbent go through the guard.** Arms B
   and C run under `PROMPT_CANDIDATE=P6B-minimal` and `PROMPT_CANDIDATE=P6C-score`
   respectively — both registered at Step 0d. The noise arm runs against the
   **promoted v6 hash**. Three assertions, all recorded.
2. **Arm B's output has no `recommendation` field, and arm C's does not
   either.** `analyst_direct_scorer.direction_from_score` will return `None`
   for both. **Do not patch the scorer.** Build the mapping in the driver
   (§5) and feed the scorer a derived field where it needs one.
3. **The score-to-direction thresholds are fixed now, before any result:
   score ≤ −2 → bearish; score ≥ +2 → bullish; −1, 0, +1 → neutral.** They
   exist only so arms B and C can be compared to arm A on the old ruler. The
   primary test (§5.2) does not use them. **Do not tune them.** If a later
   session wants different thresholds, that is an allocator-side decision
   made on this run's per-call score file, without re-scoring.
4. **A diagnostic that contradicts a prediction in the P6 block is a finding,
   not a reason to stop.** Arm B is *expected* to lose; if it does not, that
   is the most important thing this run can report.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/p6-output-format-round/`. **Write
`progress.json` first**, with `prompt_sha256`, `driver_commit`, per-step
status, `next_action`, `notes[]`, `luis_approved_usd: 130`, and
`batch_id_preflight` / `batch_id_arm_b` / `batch_id_arm_c` / `batch_id_noise`
**written and committed the instant each `create()` returns.** On resume with
a matching `prompt_sha256` and an existing batch id: submit nothing, retrieve
and continue. `scores_b.jsonl`, `scores_c.jsonl`, `scores_noise.jsonl` keyed
by `custom_id`; skip present ids. `findings.md` append-only.

## 4. Step 0 — hygiene, registration, guard

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`.
**0b.** Driver `analysis/p6_output_format_driver.py`, committed as its own
commit before any output. Import batch submission, polling, cost accounting,
alias resolution and `stratum_map()` from `analysis/p3_guidance_ledger_driver.py`;
import `PriceCache` and `parse_structured` from `analysis/analyst_direct_scorer.py`;
import `rel_ret` (arm `"B"` = tradeable entry) from
`analysis/r4b_tradeable_entry_driver.py`. **Do not rewrite any of them.**
**0c.** Confirm the P6 block is present in `PROMPT_ARCHITECTURE.md` §2.2
(it is; registered 2026-09-24). Do not edit it.
**0d.** Register both candidates in `VERSION_REGISTRY.json` under
`artifacts.evaluation_prompt` as candidates (not promotions): keys
`P6B-minimal` and `P6C-score`, paths, sha256s, parent (`none` / `v6`),
status `candidate`, date. Run the guard under each `PROMPT_CANDIDATE`; record
both warnings. Commit.
**0e.** Scoring protocol `analysis/data/corpus_v2/SCORING_PROTOCOL_P6.json` —
new file — with the resolved train list, manifest/split sha256s, all three
prompt hashes, pinned model with the assertion it equals both baselines',
the price-cache path, the fixed thresholds from rule 3, the request caps, the
disjointness assertion, and the exclusion list (WOLF, SPWR, PARA).
**0f.** Alias resolution hard stop, exactly as `P3-guidance-ledger.md` §4 0f:
1,194 transcripts, 1,240 v6 eval files mapped, `MAXN` empty and expected.
**0g. Flip-count rules.** The 2026-09-23 state of play §4.2 says
`PROMPT_ARCHITECTURE.md` §2.4/§2.5 are computed on raw flips and mislead.
**Check whether that correction has landed** (`git log -- docs/architecture/PROMPT_ARCHITECTURE.md`
since 2026-09-23). If it has not, **do not edit the file** — record in
`findings.md` that this run reports every flip count raw and net per §7's
netting rule regardless, and continue. The run does not depend on the edit.

---

## 5. The work

### 5a. Pre-flight — ~200 calls, ~$8, before either full arm

Stratified by the four-way stratum from `stratum_map()`: **100 calls scored
with arm B, 100 with arm C**, same 100 transcripts for both, drawn by fixed
seed to match the train stratum mix. Confirm for each arm: the structured
block parses; `score` is an integer in [−5, +5]; `noRead` is boolean;
`stop_reason` is never `max_tokens` (log it — v9 was corrupted this way);
measured per-call cost. **Project each full arm from its measured cost;
either projection over $55 → stop and report.**

**One pre-flight read, reported not gated:** the share of `noRead: true` per
arm. Arm B's prompt says use 0 only with genuinely no read; if more than a
third of its pre-flight calls are `noRead`, the control is defaulting to
abstention and the wrap-up must say so.

### 5b. Noise arm — 120 calls, ~$5, same batch as arm C

**Exactly `prompts/P3-guidance-ledger.md` §5f arm 21a:** 120 train calls
already in the v6 eval cache, re-scored with unmodified v6, stratified
35 small/micro / 35 megacap / 25 mid / 25 large, disagreement with their own
cached call reported per stratum with ranges, pooled with Test 4's v6 pairs
only where consistent and only to narrow, never below 21a's point estimate.
Its noise **win rate** per stratum is also recorded (needed in §7).

### 5c. Full arms B and C — one batch each, all resolved train calls

Request shape as in `prompts/baseline-v6-tune-batch.md` §7: the candidate
prompt as the cached system block, the transcript as the user message,
nothing prepended. Eval caches to
`analysis/data/evals/P6B-minimal_claude-sonnet-4-6/` and
`analysis/data/evals/P6C-score_claude-sonnet-4-6/`. **Submit B first, then C;
commit each cache as it lands.** Score nothing until both are in.

### 5d. The per-call file — build once, everything reads it

`analysis/data/run_state/p6-output-format-round/calls.csv`, one row per
resolved train call (WOLF/SPWR/PARA excluded), columns:

`ticker, call_date, stratum, tier, fwd_rel_ret_tradeable` (from `rel_ret`
arm B, 182 days), `v6_rec, v6_dir, v6_hit`, `b_score, b_noRead, b_dir, b_hit`,
`c_score, c_noRead, c_dir, c_hit`, and every v6 structured field arm C still
emits (`c_thesisHealth`, `c_stumbleType`, …). `*_dir` uses the fixed
thresholds from rule 3. Commit it. **Reproduce the v6 train reference from
this file before anything else** — 30.3% accuracy, +2.48 points, 103 bearish,
60.2% right, per `wrap-ups/baseline-v6-train-batch-out.md` — adjusted for
the PARA exclusion and stated as adjusted. **Mismatch beyond the exclusion →
stop and report.**

---

## 6. The tests — pre-registered order; the first is the one that matters

### 6.1 Rank-ordering (arms B and C) — the primary test

For each arm, bucket calls by score (−5 … +5, `noRead` shown separately) and
report per bucket: n, **median** and mean forward return vs the S&P
(tradeable entry, 182 days), and the share that beat by >5 / lagged by >5.
Then two summary numbers per arm, each with a 95% range from a
**ticker-block bootstrap** (resample companies, not calls — calls within a
company are not independent):

- **Rank correlation** between score and forward return (Spearman; state it
  as "when the score goes up, does the return tend to go up" and give the
  number once).
- **Top-minus-bottom spread:** median return of scores ≥ +3 minus median
  return of scores ≤ −3, in points.

**Pre-registered reading (P6 block):** arm C's buckets order forward returns;
arm B lands between A and C or matches A. **Arm C is falsified** if its rank
correlation's range includes zero on train. Arm B cannot be falsified — it is
a control.

**Arm A has no score.** Its comparison row is its three buckets
(bearish / neutral / bullish) with the same per-bucket statistics, so the
reader can see whether C's −5..−2 range carries more than A's single
bearish bucket.

### 6.2 The neutral pile (arm C vs arm A)

Share of calls mapped neutral (A: Hold; C: score in {−1, 0, +1}); the edge of
that bucket against its own base rate. **Falsified** if C's neutral share does
not fall below A's 58%, or if the calls C moved *out* of neutral carry zero
edge. Report `noRead` separately from −1/+1 — "no read" and "weak read" are
different claims and the prompt asks for the distinction.

### 6.3 Old-ruler comparison — accuracy, bearish precision, flips

On the fixed thresholds: accuracy and gap over luck per arm; bearish call
rate and precision against the 46.6% base rate; bullish likewise against
32.8%. Flip counts B-vs-A and C-vs-A, **raw and net** per §7. The §2.4
ceiling on the net count. These are reported for continuity with every prior
round; **they are not the decision.**

### 6.4 Money — the measure of record since 2026-09-20

For each arm, the simple-average and median forward return of (i) the
bearish bucket, (ii) the bullish bucket, (iii) the sell-bearish/buy-bullish
swap, on the tradeable entry, in the exact form of the 2026-09-23 state of
play §2 so the rows line up. Per stratum. 2020 reported separately.

### 6.5 Diagnostics, all $0

- **Agreement between arms:** B-vs-C score correlation; on calls where they
  disagree by ≥3 points, which was right, with n.
- **What the rubric did:** for arm C, cross-tab `score` against
  `thesisHealth` and `stumbleType`. If every *Intact + None* call still
  scores in {−1,0,+1}, the model is reproducing the matrix from habit and
  the candidate did not take.
- **Length:** median completion tokens per arm — arm B is shorter by
  construction; note it beside any accuracy difference (the input-length
  confound from the P3 review, in reverse).
- **Q2 re-run** on arm C's `score` as a strength axis within its bearish
  bucket, discovery only, axis prediction written before looking.
- **Per-call diffs to disk.**

---

## 7. Netting and the noise floor — carried from P3, applied to counts only

Copy `prompts/P3-guidance-ledger.md` §7 "The netting rule" verbatim into
`findings.md` before scoring, and apply it: every flip count raw and net of
the per-stratum 21a rate re-weighted to the train mix; the win-rate guard
(report netted win rate only when `observed − noise` exceeds 100 and the
noise count's upper range); the non-disjointness caveat. **The rank-ordering
test in 6.1 is not a flip count and is not netted** — noise widens its range
(which the bootstrap captures) and does not shift it, provided 21a's noise
win rate is near 50%; report that rate beside 6.1.

---

## 8. Rules carried forward, with their numbers

- v6 train reference: 30.3% / +2.48 / 103 bearish / 60.2% —
  `wrap-ups/baseline-v6-train-batch-out.md`; restate after PARA exclusion.
- Bearish base rate 46.6%; bullish 32.8%; neutral 20.6% (P3a block).
- Money reference rows: bearish 7.4% of calls, edge +12.3, median −10.09%;
  bullish 34.3%, +4.4, −1.43%; swap +2.4 mean / +8.7 median — 2026-09-23 §2.
- v6 pairwise noise 12.8% (6.8–19.2), per-stratum large 3.1 / mid 6.7 /
  small-micro 19.6 / megacap 21.5 — `wrap-ups/test4-noise-floor-v6-rerun-out.md`.
- §1.3: arms B and C have no `per_call_rec`; the graded field is `score`,
  mapped by the fixed thresholds where a direction is needed. Never
  `final_action`; nothing through the trend layer.
- §1.4 / firewall: no portfolio data; transcript only.
- Do not gate on a known defect: WOLF/SPWR/PARA excluded; F2 unresolved,
  noted once; R1–R3 open, blocking nothing.
- Provenance for every figure.

---

## 9. Report step

**Scope boundary: report, do not decide.** Do not promote, do not pick
thresholds, do not run tune, do not start P7 or P8.

Write `wrap-ups/P6-output-format-round-out.md`, in three forms (.md, .docx
with real tables, published artifact). **Open with §0, defined terms:**
score, no-read, bucket, rank-ordering, top-minus-bottom spread, tradeable
entry, money, edge, base rate, noise flip, net flip, control arm. Plain
words first.

Open the body with this sentence, filled in:

> On ___ train calls, the minimal prompt (arm B) ranked forward returns with a
> correlation of ___ (range ___ to ___) and the score arm (C) with ___ (range
> ___ to ___); v6's three buckets, for comparison, separate their best from
> their worst by ___ points and arm C's by ___. Arm C moved ___ of v6's ___
> neutral calls out of neutral, and those calls carried an edge of ___ points.
> On the old ruler, accuracy was A ___ / B ___ / C ___.

Then §6 in order. Then one paragraph per finding. **State each P6-block
prediction and whether it held, in one sentence each, no hedging.**

**Close with what it means for a decision, all three ways:** if C ranks and B
does not, the rubric stays and the matrix goes, and thresholds are an
allocator decision on `calls.csv`; if B matches or beats A, the rubric is not
where the signal is and P7/P8 iterate from the minimal prompt; if neither
ranks, the transcript-only read has hit its ceiling on this model and the
next lever is the reader (a §2.2b model gate), not the prompt.

Plain-language discipline is binding: anchor every percentage, "points" not
"pp", lead with the finding, one idea per sentence, forbidden terms defined
in one line at first use.

---

## 10. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. Work on
`sweep/db-corpus-baseline`. Provenance for every figure. One prompt in, one
wrap-up out. Commit eval caches and `calls.csv` as they land. Running low on
budget: stop cleanly — **arm B alone, scored and ranked against A, is a
useful partial result**; arm C alone is more useful still. Say plainly which
it is.
