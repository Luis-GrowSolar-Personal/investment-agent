# P6B on tune — one look, pre-registered

**Run ID:** `p6b-tune-confirmation`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P6B-tune-confirmation-out.md`
**Cost: THIS RUN SPENDS REAL MONEY — about $45.** Arm B on the tune split
(~1,170 calls × the measured $0.0236 ≈ $28) plus a **larger** pure-noise arm
on tune (250 v6 re-scores × $0.038 ≈ $10) plus a 50-call pre-flight (~$1.50).
**Hard cap $60**, counted before every `create()`. Luis has approved $60;
record it in `progress.json` at Step 0 or stop and ask.

**This is the one look at tune that `PROMOTION_GATE.md` §7 allows the final
candidate.** Nothing is tuned here. Every threshold and falsifier below was
fixed on 2026-09-24 from the train result and is written down before the run.
**Do not iterate against tune. If B fails here, it failed.**

**Read first:** `wrap-ups/P6-output-format-round-out.md` (the train result
this run confirms or refutes — §6.1–6.4 and the "Findings" list);
`prompts/P6-output-format-round.md` §2, §7 (ground rules and netting, reused
verbatim); `prompts/baseline-v6-tune-batch.md` §2, §5 (tune-side aliases —
GOOGL is keyed `GOOG`; WOLF/SPWR ungradable); `wrap-ups/baseline-v6-tune-batch-out.md`
(v6's tune reference); `analysis/p6_output_format_driver.py` and
`analysis/p6_output_format_analysis.py` (reuse; add a `--split tune` path,
do not fork).

---

## 1. What this run is for

On train, the minimal prompt (arm B, `docs/prompts/candidates/EVALUATION_PROMPT_P6B_minimal.md`,
sha `d1fa5e53…`) ranked forward returns (Spearman 0.130, range 0.051–0.208),
doubled v6's bearish coverage (191 calls vs 93) without losing precision
(62.3% vs 58.1%, base 46.6%), and produced a sell-bearish/buy-bullish swap
whose median range excluded zero (8.92, range 4.12–15.34). It did this in
514 tokens against v6's 2,428, with no rubric.

**The question here is one question: does that hold on 51–54 companies B has
never seen?** If it does, B replaces v6 as the working analyst candidate and
P7/P8 iterate from it. If it does not, the train result was fitted to 55
companies and the queue reverts to the 2026-09-23 state of play §3.

**What this run is NOT.** Not a threshold search. Not a second candidate.
Not arm C — C was indistinguishable from B on train and costs 66% more; it
does not get a tune look unless B fails and a later session pre-registers it.

---

## 2. Ground rules

`prompts/P6-output-format-round.md` §2 applies unchanged, with the split
swapped: **tune ONLY** — the 54 companies in
`SPLIT_V7_RESERVE_REPLACEMENTS.json` → `tune`, alias-resolved, **WOLF and
SPWR excluded entirely** (ungradable; 2026-09-19 state of play §6). Holdout
untouched; assert disjointness against train and holdout before submission.
Guard under `PROMPT_CANDIDATE=P6B-minimal` (already registered); noise arm
against the promoted v6 hash. Pinned `claude-sonnet-4-6`. Corpus_v2 price
cache by exact string. No scorer edits. macOS/zsh.

**Fixed thresholds — copied from train, not re-chosen:** score ≤ −2 →
bearish; score ≥ +3 → bullish; −1, 0, +1, **+2** → neutral.

**Note the bullish cut moved from +2 to +3 relative to the train run's old-
ruler mapping.** That is a pre-registered change, decided 2026-09-24 on the
train evidence that +2 is the model's resting score (438 of 1,217 calls) with
no edge (median −2.29), while +3 carries a small positive median (+1.16,
n=226). It is stated here so it cannot be presented later as a post-hoc
choice. **Report the +2 mapping as well**, labelled as the train run's
original mapping, so the two are side by side.

---

## 3. Step −1 / Step 0 — as P6, with these differences

- State in `analysis/data/run_state/p6b-tune-confirmation/`. Batch ids
  `batch_id_preflight`, `batch_id_arm_b`, `batch_id_noise`, each committed the
  instant `create()` returns. **The P6 run lost a batch id by piping output to
  `tail` while a background poller ran; do neither.** One process, output to
  the terminal, id written before anything else happens.
- Driver: extend `analysis/p6_output_format_driver.py` with `--split tune`
  (own commit before output). Tune transcripts are on disk from the
  baseline run; v6's tune cache is `analysis/data/evals/v6_claude-sonnet-4-6_tune/`.
- Protocol `analysis/data/corpus_v2/SCORING_PROTOCOL_P6B_TUNE.json`, new file:
  tune list, exclusions (WOLF, SPWR), aliases applied, prompt hash, model
  assertion, thresholds (both mappings, labelled), caps.
- **0f, tune-side alias hard stop:** every tune symbol resolved through
  `TICKER_ALIASES.json`; assert the resolved set maps every file in the v6
  tune cache; report the count (expect ~1,168 gradable after WOLF/SPWR).
- **0g:** reproduce v6's tune reference from the v6 tune cache before scoring
  anything — **28.3% / +2.64 / 84 bearish / 59.5%** per
  `wrap-ups/baseline-v6-tune-batch-out.md` (post-backfill figures; if the
  wrap-up on disk shows pre-backfill numbers, use
  `wrap-ups/scorer-price-cache-backfill-out.md` as the P6 run did, and say
  which). Mismatch → stop and report.

---

## 4. The work

### 4a. Pre-flight — 50 tune calls, arm B, ~$1.50

Structured block parses; `score` in [−5, +5]; `noRead` boolean; no
`max_tokens` stops; measured cost projects the full arm under $32. Any
failure → stop and report.

### 4b. Noise arm — 250 v6 re-scores on tune, ~$10

Same construction as P6 §5b but **250 calls, not 120**: the train run got
only 20 graded noise flips and could not tell whether the cached v6 draw is
systematically luckier than a fresh one (6 vs 3). At ~17% disagreement, 250
calls yield ~40 flips — still thin, but twice the evidence, and it is the
cheapest place to buy it. Draw proportional to the tune S1–S5 mix. Report:
disagreement rate with Wilson range, per stratum; **graded noise win rates
for cached and fresh**, pooled with the train run's 20 flips and reported
both ways.

### 4c. Arm B — all tune calls, one batch

Eval cache `analysis/data/evals/P6B-minimal_claude-sonnet-4-6_tune/`
(gitignored like the others; commit `scores_b_tune.jsonl`). Then
`calls_tune.csv` in the same columns as the train run's `calls.csv`, with
both threshold mappings as separate `b_dir_plus2` / `b_dir_plus3` columns.

---

## 5. Pre-registration — what "held" means, decided before the run

B **holds on tune** only if **all four** are true:

1. **Rank-ordering.** B's Spearman between score and 182-day tradeable-entry
   return vs SPY, ticker-block bootstrap 2,000 draws, has a 95% range that
   **excludes zero.** (Train: 0.130, 0.051–0.208. Prediction: 0.08–0.16.)
2. **Bearish coverage without precision loss.** At the ≤ −2 cut, B's bearish
   call count is **at least 1.5× v6's** on the same calls (v6 tune: 84), **and**
   B's bearish precision is **not more than 5 points below v6's** on tune
   (v6: 59.5%). (Train: 2.05×, +4.2 points. Prediction: 1.7–2.2×, within
   ±5 points of v6.)
3. **Money.** B's sell-bearish/buy-bullish swap **median** at the ≤ −2 / ≥ +3
   cuts has a 95% ticker-block range that **excludes zero.** (Train, at the
   +2 mapping: 8.92, 4.12–15.34. Prediction at +3: 6–12, range clear of zero.)
4. **No regression on the old ruler.** B's gap over luck at the +3 mapping
   is **not below v6's tune gap by more than the noise band** (v6: +2.64,
   range 0.21–5.00).

**Falsified** if any of 1–3 fails. If only 4 fails, report it as a finding
and not a failure — the old ruler is a footnote since 2026-09-20, and a
bullish-cut change moves accuracy mechanically.

**Also report, not gated:** every train-run diagnostic on tune — the score
bucket table (6.1), neutral share and `noRead` share (6.2), the old-ruler
table at both mappings (6.3), money by stratum and by year with 2020
separate (6.4), flips vs v6 raw and net per the P6 §7 netting rule using
the tune noise arm, and the B-vs-v6 disagreement analysis. **Pooled
train+tune figures** (2,385 calls) for rank correlation and the swap, since
that is the population the 2026-09-23 state of play quotes v6 on.

---

## 6. Report step

**Scope boundary: report, do not decide.** Do not promote, do not touch the
registry's `promoted_version`, do not choose thresholds beyond the two
pre-registered mappings, do not start P7 or P8, do not score holdout.

`wrap-ups/P6B-tune-confirmation-out.md`, three forms. **§0 defined terms**
as in the P6 wrap-up plus: one look, held/falsified, pooled. Open the body
with this sentence, filled in:

> On ___ tune calls from ___ companies the minimal prompt had never seen, its
> score ranked forward returns at ___ (range ___ to ___); it made ___ bearish
> calls against v6's ___ and was right on ___% of them against v6's ___%; the
> sell-bearish/buy-bullish swap was worth a median ___ points (range ___ to
> ___). Of the four pre-registered conditions, ___ held. **B [held / was
> falsified] on tune.**

Then the four conditions, one line each, held or not, no hedging. Then the
diagnostics. Then the pooled figures. Then the noise-arm result on the
cached-vs-fresh question, plainly: does the evidence now say v6's cached
baseline was a lucky draw, or is it still too thin to say.

**Close with what it means, both ways:** if B held — B is the working analyst
candidate; the design questions it opens (which v6 structural fields the
allocator still needs, and how B's score and those fields coexist; the
bullish side still carries nothing) go to the design session. If B was
falsified — which condition failed, and whether it failed narrowly (a
range touching zero) or clearly; the queue reverts to the 2026-09-23 §3
list with P6 recorded in the ledger as a train-only result.

Plain-language discipline is binding.

---

## 7. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure. One prompt in, one wrap-up out. Commit
`scores_b_tune.jsonl`, `scores_noise_tune.jsonl`, `calls_tune.csv` as they
land. Budget stop: the noise arm can be dropped to 120 if the projection
breaches $60; arm B cannot be partial — it is one look or none.
