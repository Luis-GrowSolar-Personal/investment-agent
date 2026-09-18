# Q2 — does the analyst already know which of its bearish calls are the good ones?

**Run ID:** `q2-bearish-strength-separation`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/q2-bearish-strength-separation-out.md`
**Cost: $0. THIS RUN MAKES NO MODEL CALLS.** Everything it needs is already on
disk. If you find yourself about to call the Anthropic API, you have
misunderstood the task — stop and report.

**Read first:** `docs/handoffs/2026-09-17-state-of-play.md` §0 and §2,
`docs/architecture/PROMPT_ARCHITECTURE.md` §2.1–§2.5,
`docs/architecture/PROMOTION_GATE.md` §3.1, and
`analysis/analyst_direct_scorer.py` (specifically `direction_from_score`,
`parse_structured`, and `write_csv`).

---

## 1. What this run is for

P1 — "commit to bearish when the evidence supports it" — is pre-registered and
ready to run at ~$47. It buys **coverage**: more bearish calls, catching more of
the real declines. It explicitly predicts bearish **precision falls**, from
~60% toward the ~46.6% base rate, because the additional calls come from
thinner evidence.

That trade is only acceptable if something downstream can tell a strong bearish
call from a weak one. The allocator is the layer that knows position sizes, so
it is the layer that must do the sorting. It can only sort if the analyst's
output actually carries a strength signal that **predicts correctness**.

**This run answers exactly one question, on data already scored:**

> Within v6's existing bearish calls, do the analyst's own supporting fields
> separate the right calls from the wrong ones?

If they do, P1 is worth running: the allocator trims hard on strong calls and
lightly on weak ones, and coverage is close to free.
If they do not, the analyst has one undifferentiated signal, P1's precision drop
is a straight loss with nothing downstream to recover it, and the queue should
be reordered toward a precision candidate instead.

**What this run is NOT.** It is not a promotion decision. It does not run P1. It
does not modify the prompt, the scorer, the registry, or any candidate. It
commissions nothing. It reports a finding and stops.

---

## 2. Ground rules — the do-not list

1. **No LLM calls. No Anthropic API. No spend.** Read-only analysis of existing
   eval caches.
2. **No DB writes.** Nothing touches Railway Postgres.
3. **Do not modify** `analysis/analyst_direct_scorer.py`,
   `docs/EVALUATION_PROMPT.md`, `docs/architecture/VERSION_REGISTRY.json`, or any
   file under `docs/architecture/`. If you need scorer logic, import it or copy
   the function into the new driver — do not edit the scorer in place.
4. **Do not touch the holdout.** Train and tune only. Holdout is locked and
   hashed (`PROMOTION_GATE.md` §10). Assert zero holdout tickers in your input
   before doing anything else.
5. **Do not re-score, do not refresh the price cache.** Use
   `analysis/data/price_cache.json` as it stands.
6. **macOS Tahoe, zsh.** `python3`, never `python`. Never
   `--break-system-packages`. No `apt`. `brew` only if a system tool is
   genuinely missing.
7. **A diagnostic that contradicts an expectation stated in this prompt is a
   finding, not a reason to stop.** The illustrative numbers in §5 are
   illustrative. If the data says otherwise, report what the data says.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/q2-bearish-strength-separation/`. **Write
`progress.json` as the very first action, before reading anything.**

- `progress.json` — `prompt_sha256`, `driver_commit`, per-step status
  (pending / in_progress / done), a one-sentence `next_action`, `notes[]`.
- `cells.jsonl` — one line per completed axis (see §5): `axis_name`, `split`,
  the contingency counts, the computed rates. Flush after every axis.
- `findings.md` — append-only. Write each finding the moment it is established,
  never at the end.

This run is short, but the protocol is standing. Matching `prompt_sha256` on
restart means resume and skip completed axes.

---

## 4. Step 0 — hygiene

**0a.** Clean tree. Hard stop if `git_dirty` cannot be recorded `false` in
`progress.json`.

**0b.** Commit the driver as its own commit, before it produces any output.
Driver path: `analysis/q2_bearish_strength_driver.py`.

**0c.** No version guard is required — this run makes no scoring calls. Record
in `progress.json` that the guard was skipped **and why**, so a later reader does
not mistake it for an omission.

---

## 5. The work

### 5a. Build the joined table — highest-value step, do this first

The two baseline eval caches are:

- train — `analysis/data/evals/v6_claude-sonnet-4-6`
- tune  — `analysis/data/evals/v6_claude-sonnet-4-6_tune`

For every call in both caches, produce one row carrying:

| column | source |
|---|---|
| `ticker`, `call_date` | filename / eval |
| `split` | `train` or `tune` |
| `predicted` | `direction_from_score()` — bullish / bearish / neutral |
| `ground_truth` | scorer's ±5% benchmark-relative 2Q logic |
| `benchmark_rel_return_pct` | scorer |
| `hit` | scorer |
| `recommendation` | `parse_structured()` → `recommendation` (Hold/Add/Trim/Exit) |
| `thesisHealth` | `parse_structured()` |
| `thesisDelta`, `stumbleType`, `credibilityDelta` | `parse_structured()` |
| `ratchetTranche`, `activeDriverCount` | `parse_structured()` |
| `blindSpotsTriggered` | `parse_structured()` — keep the array AND its length |
| `threatMechanismImpaired`, `mitigationArgumentPresent` | `parse_structured()` |
| `recommendedSize`, `capPercent`, `freshMoneyAllocation` | `parse_structured()` |

Reuse the scorer's own `parse_structured()` and `direction_from_score()` by
import. Do not write a second parser — three separate bugs have already been
caused in this project by a parser built against one set of keys while the
consumer read another (`state-of-play` §6, six instances).

Write the joined table to
`analysis/data/run_state/q2-bearish-strength-separation/joined_calls.csv` and
commit it. Later rounds will want to re-read it.

**Coverage assertion, and it is a hard stop.** Report how many calls failed to
parse a structured block, and how many parsed but produced a null on each field.
**If more than 5% of bearish calls are missing a given field, that field is not
usable as an axis — say so and exclude it**, do not silently treat null as a
category. The scorer already refuses to report a score when calls go missing;
hold this run to the same standard.

### 5b. Restrict to bearish calls and establish the denominators

Filter to `predicted == "bearish"`. Expected, and **verify rather than assume** —
these are quoted from `PROMPT_ARCHITECTURE.md` §2.1, which sources them from
`wrap-ups/baseline-v6-train-batch-out.md` and
`wrap-ups/baseline-v6-tune-batch-out.md`:

- train: **103** bearish calls, **60.2%** of them right, base rate **44.9%**
- tune: **84** bearish calls, **59.5%** right, base rate **48.4%**
- pooled bearish base rate: **46.6%**

**If your counts disagree with these, stop and report the discrepancy before
continuing.** A mismatch means the joined table is wrong, and every number after
it would be wrong too.

Note that `WOLF` and `SPWR` are ungradable (2024/25 bankruptcies, ticker reuse,
pre-reorg prices purged at source) and `NOVA` is silently affected the same way
on train. Report how many bearish calls are lost to this.

### 5c. The axes — RANK THEM BEFORE YOU LOOK AT ANY RESULT

This is the part that can quietly ruin the run. You are about to cross-tab ~8
candidate strength axes against correctness on 187 calls. **Testing eight splits
and reporting the best one is the exact failure `PROMPT_ARCHITECTURE.md` §2.3
warns about** — six candidates screened on one sample hand back a winner that
looks ~1.5 points better than it is.

Three rules, all mandatory:

1. **Write the ranked axis list into `findings.md` BEFORE computing any
   contingency table**, with a one-line prediction for each. Commit that.
2. **Report every axis in the wrap-up, not just the ones that separated.** A
   table of eight axes where one looks good is a very different result from one
   axis tested and confirmed.
3. **Train discovers. Tune confirms.** Compute every axis on train first. Then
   compute the same axes on tune. An axis that separates on train and *not* on
   tune has not separated — say so plainly in one sentence and move on, no
   hedging, no re-litigating.

The axes, in the order I expect them to be informative. You may disagree with the
ranking, but record your ranking before looking:

| # | axis | split on | why it might carry signal |
|---|---|---|---|
| A1 | `recommendation` | **Exit vs Trim** | The scorer collapses these two into one "bearish" bucket. That collapse is a strength distinction already being discarded. Cleanest axis available, no interpretation needed. |
| A2 | `thesisHealth` | **Broken vs Weakening** | The analyst's own severity grade. |
| A3 | `blindSpotsTriggered` | **count 0 / 1 / 2+** | More independent warnings firing should mean a better-evidenced call. |
| A4 | `stumbleType` | Structural vs Execution vs Discovery | Structural damage should predict worse forward returns than an execution miss. |
| A5 | `ratchetTranche` | 1 vs 2 vs 3 vs null | A second or third consecutive weakening quarter is a confirmed deterioration, not a first read. |
| A6 | `credibilityDelta` | negative vs neutral/positive | Management losing credibility alongside a bearish call. |
| A7 | `threatMechanismImpaired` | true vs false | Whether the thing that makes the company work is actually broken. |
| A8 | `recommendedSize` / `capPercent` | continuous — bin it | How far the analyst wants the position cut. Largest cut = strongest conviction. |

For each axis and each split report: **n in each bucket, number right, hit rate,
and the hit rate's 95% range.** State the range as plain points ("55%, and with
only 60 calls that could plausibly be anywhere from 44% to 66%"), not as a
statistical term.

### 5d. The one number that decides it

For each axis, the deciding quantity is the **spread between its strongest and
weakest bucket, measured against the 46.6% base rate.**

An axis is worth building on if **both** hold:

- its strongest bucket beats the base rate by materially more than the
  all-bearish-calls figure of ~60% does, **and**
- the ordering survives on tune.

Report the spread and its range for every axis. **Do not declare a winner.**
Ranking axes is a decision, and this run's scope boundary forbids it.

---

## 6. Rules carried forward, with their numbers

- **§1.3** — the graded field is `per_call_rec`, never `final_action`. This run
  reads the analyst's own call. Do not let the trend layer into the join.
- **§1.4 / firewall** — no portfolio or position data enters this analysis. You
  are analyzing analyst outputs against price history only.
- **§2.3** — pre-registration before looking. Enforced in 5c.
- **Provenance rule** — every number quoted in the wrap-up names its source file
  and JSON key or CSV column. A figure without provenance is a premise to verify,
  not a fact.
- **Do not gate on a known unfixed defect.** WOLF/SPWR/NOVA terminal-value
  grading is a documented open item (`state-of-play` §6). Report the loss, do not
  fail the run on it.
- **Sector-relative grading is unresolved (F2).** Everything here is benchmarked
  to SPY. Note it once; do not attempt to fix it.

---

## 7. Report step

**Scope boundary: report, do not decide.** Do not reorder the candidate queue,
do not amend `PROMPT_ARCHITECTURE.md`, do not register anything, do not
recommend whether P1 runs. That decision is Luis's and it happens in
conversation, not in this wrap-up.

Write `wrap-ups/q2-bearish-strength-separation-out.md`. **Reports ship in three
forms** per `CLAUDE.md`: the `.md`, a `.docx` alongside it with real Word tables,
and a published artifact page as the reading version. **Open with §0, defined
terms** — at minimum: bearish call, base rate, hit, dead band, benchmark-relative
2Q return, precision, coverage, strength axis. Define each as used here, in plain
words, before any identifier appears.

Open the body with this sentence, filled in:

> Of v6's ___ bearish calls across train and tune, ___ were right (___%) against
> a base rate of ___%. Splitting them by ___ separates the right calls from the
> wrong ones by ___ points on train; on tune that separation ___ [held at ___
> points / did not hold]. Of the eight axes tested, ___ separated on both splits
> and ___ separated on neither.

Then: the full eight-axis table for both splits. Then a plain-language paragraph
per axis that separated. Then the axes that did not, in one line each.

**Close with what it means for a decision** — specifically, what Luis would do
differently depending on the result, stated both ways:

- if at least one axis separates on both splits, what that makes possible;
- if none do, what that rules out.

If nothing changes either way, say that plainly.

**Plain-language discipline is binding.** Luis is an experienced investor and not
a statistician. Anchor every percentage to what it is a percentage of — not "60%
precision" but "of the 103 times it said bearish, 62 turned out right." Write
"points," never "pp." Lead with the finding; put the method after or omit it.
Short sentences, one idea each. Forbidden without a plain one-line definition at
first use: lift, baseline, base rate, precision, recall, confidence interval,
significance, distribution, variance, artifact, null.

---

## 8. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. No `--break-system-packages`.
- Work on branch `sweep/db-corpus-baseline`.
- Provenance for every figure — manifest/CSV path plus the exact key or column.
- One prompt in, one wrap-up out to
  `wrap-ups/q2-bearish-strength-separation-out.md`.
- **Do not run `git commit` or `git push` yourself if that is this project's
  convention for your session type** — follow the repo's existing discipline.
- Running low on budget is a reason to stop cleanly, not to rush. Write the
  wrap-up with what is done, mark the rest `pending` with a precise
  `next_action`, and say plainly that it is a partial run. Axis A1 alone, done
  properly on both splits, is a useful result.
