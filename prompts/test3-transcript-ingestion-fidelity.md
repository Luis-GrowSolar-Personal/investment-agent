# Test 3 — is the corpus itself truncated, and is AV viable as a future source?

`docs/handoffs/2026-09-05-state-of-play.md` §7 Test 3. **Read §0 of that
document before starting** — it defines every term used here. Also read
`wrap-ups/av_transcript_fidelity_benchmark_1-out.md` in full — this run does
not repeat that benchmark, it finishes the question it left open.

**This file does not supersede `prompts/av_transcript_fidelity_benchmark_1.md`.**
That run is complete (7/7 samples processed, wrap-up filed) and its outputs —
`analysis/av_fidelity_test/raw/*.json`, `analysis/av_fidelity_test/results.json`,
`av_fidelity_1-manifest.json` — are **inputs to this run**, not drafts to
delete. Do not re-fetch anything Step 1 of that run already saved.

## Why this run exists, and the one thing it must not conflate

The pilot found DB-vs-AV text similarity of **0.11-0.18 for two EOSE/SPWR
samples and 0.17-0.18 for two SPWR samples**, against **0.69-0.78 for every
AMPX sample and one EOSE sample**, and flagged it explicitly as "not
investigated further." State-of-play §7 escalates that from an interesting
anomaly to a **prerequisite**: *"If transcripts are truncated, every score
built on them is corrupt at the source."*

That sentence is actually **two different questions**, and the prompt that
would ask them together would fail guardrail 1 (one rule, one clause):

- **Q1 - corpus integrity (this run's priority, and what actually gates
  Tests 4/5/6).** Every backtest run so far, and every stored `Analysis` row,
  was scored from the **DB-stored transcript text**, never from Alpha Vantage.
  Tests 4, 5 and 6 reuse that same DB text. So the question that actually
  blocks them is: **is the DB corpus itself complete?** This is answerable
  from the database alone, at zero cost, and does not need Alpha Vantage at
  all.
- **Q2 - AV viability (secondary, gates only future Step 6 build work, not
  any test already planned).** Is AV's `EARNINGS_CALL_TRANSCRIPT` endpoint a
  usable automated ingestion source going forward? This was the pilot's
  original question. It remains open, but nothing currently in the test plan
  depends on its answer.

**Do Q1 first, completely, before spending anything on Q2.** If Q1 comes back
clean, Q2 drops from "prerequisite" to "Step 6 design input" and this run
should say so plainly rather than spending AV budget out of habit.

### What NOT to re-litigate or re-measure here

The pilot's determinism-gate failure (4/7 samples) is a **known, already-
logged defect** - it matches `EVALUATION_PROMPT.md`'s own v9/v10 changelog and
is exactly what `PROMOTION_GATE.md` §6 and Test 4 exist to measure at scale.
**Per "never gate on a known unfixed defect," this run must not try to fix it,
re-measure its rate, or wait for it to pass before doing useful work.** It is
the reason Steps 1-3 below are designed to need **zero re-scoring** - a text-
completeness census and a raw-transcript diff don't touch the analyst prompt
at all, so the instability can't contaminate them.

**No LLM calls in Steps 1-3.** No re-scoring, no evaluator runs, nothing that
would revisit the determinism question. **No DB writes** - `SELECT` only.
**Do not modify `EVALUATION_PROMPT.md`.**

Work on `sweep/db-corpus-baseline`. **Other sessions may be active on this
branch right now** - `resolve-open-four` and `corpus-archive` both left
untracked state behind them, and a concurrent session was found mid-run
during Test 2 editing `docs/handoffs/2026-09-05-state-of-play.md` directly.
**Leave any untracked file you did not create alone**, per Test 2's own
precedent, and if a git operation fails because `.git/index.lock` exists and
is fresh (check its mtime), **wait and retry - do not delete it.** Write
findings to `./wrap-ups/test3-transcript-ingestion-fidelity-out.md`.

---

## Step -1 - resume protocol

`run_id` is **`test3-transcript-ingestion-fidelity`**, state in
`analysis/data/run_state/<run_id>/` per the standing convention in
`CLAUDE.md`. Write `progress.json` before any reading. Update the step map
the moment a step finishes, not at the end - `corpus-archive`'s wrap-up
recorded a case where this drifted and cost a resume an expensive redo.
Append to `findings.md` the moment a finding is established.

**Step 1 is the substance and gates everything else.** If budget runs short,
stop after Step 1 and report - a clean or dirty Q1 answer is useful on its
own. Steps 2-3 are secondary; Step 4 is optional and gated explicitly below.

## Step 0 - hygiene

Confirm the tree's only untracked entries are ones already explained above
(other sessions' state) or your own new files. Driver committed **before**
any manifest, as its own commit - this run's driver script plus this prompt
file. `testing/` stays gitignored.

---

## Step 1 - DB corpus completeness census (highest priority, zero cost)

Query `Transcript` (`SELECT` only) for every row in the **ALL16** universe
(the same 16 tickers Tests 1/2 use - see state-of-play §2/§5.4 for the list),
joined to `Ticker` for the symbol. For each row, compute directly from the
stored `rawText`:

- **Word count** (`len(rawText.split())`) and character count. Name it as
  such - this is a count of the stored field, not an estimate.
- **Closing-language check**: does the text's final ~300 characters contain
  a call-closing marker (case-insensitive match against a short list:
  "concludes", "thank you for joining", "you may disconnect", "this
  concludes", "goodbye", "have a good day" - extend the list if a clear
  closing idiom shows up in the corpus that isn't on it, and say so)? Report
  match / no-match per row, not a single aggregate.
- **Q&A presence check**: does the text contain a Q&A section marker
  ("question-and-answer", "Q&A", or a run of "Operator:" / analyst-name
  speaker turns after the prepared remarks)? Report presence / absence.
- **Per-ticker outlier flag**: for each ticker, compute the median word count
  across its own rows, and flag any row below **40% of its own ticker's
  median** - a within-ticker comparison, not a cross-ticker one, since call
  length varies legitimately by company.

**Cross-tabulate against the pilot's flagged low-ratio samples by name**:
EOSE Q2 2025 (id 23), SPWR Q1 2025 (id 32), SPWR Q3 2025 (id 31), and AMPX
Q3 2025 (id 17, the one with the visually anomalous 15-vs-47/53 AV speaker-
turn count). For each of these four specific DB rows: does the **DB** side
show a closing-language match, a Q&A section, and a normal (non-outlier)
word count for that ticker? **This is the load-bearing comparison** - if the
DB version of these four rows looks complete by these checks while the AV
version was short, that points at AV as the truncated side, not the corpus
this project actually scores from.

State the result as a table: ticker, quarter, DB word count, DB per-ticker
median, ratio to median, closing-language match (Y/N), Q&A presence (Y/N),
outlier flag (Y/N).

---

## Step 2 - qualitative check on the AV side (zero new AV calls)

Reuse the seven raw AV responses already saved under
`analysis/av_fidelity_test/raw/`. For each:

- Count AV's own speaker-turn array length (the pilot found 15 for AMPX Q3
  against 47-53 for the ticker's other quarters - reproduce that count for
  all seven, not just the one already flagged).
- Check whether the **last** speaker turn ends with a closing/sign-off
  phrase (same list as Step 1) or cuts off mid-sentence / mid-topic.
- Classify each sample as one of: **truncated** (turn count or ending
  pattern indicates the transcript stops before the call plausibly ended),
  **summarized-but-complete** (fewer/shorter turns throughout, but the call's
  full arc - remarks through sign-off - is present), or **unclear**.

Report this classification next to each sample's already-known similarity
ratio from the pilot. The question this answers: is the low similarity for
EOSE Q2 / SPWR Q1 / SPWR Q3 the **same mechanism** as AMPX Q3's flagged
truncation, or something else?

---

## Step 3 - the SPWR rename-timing check

The pilot's own context notes AV has no SPWR data before its **April 2025**
corporate rename. Two of the three low-ratio SPWR-adjacent samples straddle
that: **Q1 2025 (call date 2025-04-30)** sits right at the rename, **Q3 2025
(call date 2025-10-21)** sits six months clear of it.

**This is a diagnostic, not a gate - report whichever way it points.** If
both the at-rename and well-past-rename samples show the same low ratio and
the same Step 2 classification, that argues **against** a rename-transition
artifact and **for** a persistent, ticker-specific AV coverage gap. If they
differ materially, that argues the opposite. Either answer is a finding.
Compare against AMPX and the one clean EOSE sample as a same-period control
group with no rename event.

---

## Step 4 - optional, gated explicitly on Step 1's result and a fresh budget check

**Do not run this step by default.** Two separate gates, both required:

1. **Step 1 must have left a DB-side completeness question actually open**
   for a specific ALL16 transcript - not merely "AV looked bad," which Steps
   2-3 already explain without new calls. If Step 1's census comes back clean
   for the whole ALL16 corpus, **say so and stop here** - the thing that
   gates Tests 4/5/6 is answered, and spending AV budget after that is
   scope creep on this run's actual job.
2. **Re-confirm today's remaining Alpha Vantage free-tier quota before
   calling anything.** The pilot used 7 of a 15-call self-imposed cap inside
   a 25/day account limit - **do not assume any of that carries over.** The
   quota resets daily; check the account or a lightweight probe call's
   response headers/fields for remaining calls before budgeting a sample
   size, exactly as the pilot did before its own Step 2.

If both gates pass, fetch at most 2 additional AV transcripts - a second
EOSE and a second SPWR quarter not already sampled - spaced >=70s apart, no
auto-retry into a rate limit, same as the pilot's corrected spacing. This is
to distinguish "one bad quarter" from "this ticker is systematically short
on AV" with more than n=1 per ticker in the low-ratio group.

---

## Step 5 - verdict, against a rule fixed before results

| Step 1 finding | Reading |
|---|---|
| No ALL16 transcript flagged as an outlier; closing-language and Q&A checks pass for the four named rows and the corpus generally | **Corpus integrity intact.** Tests 4, 5 and 6 are **not** blocked by a transcript-truncation defect. AV viability (Q2) is a Step 6 design question only - report Steps 2-4's findings as input to that future decision, not as a backtest-validity finding. |
| One or more ALL16 transcripts flagged as truncated/incomplete on the DB side | **Corpus defect.** Name the exact transcript id(s), ticker(s), quarter(s). This is a stop-the-line finding - every stored `Analysis` row scored from that transcript, and every backtest that included it, needs to be flagged before Tests 4/5/6 proceed. Do not soften this into a footnote. |

State explicitly which row of this table applies and why, citing the Step 1
table directly.

---

## Report

Scope boundary: **report, do not decide.** Do not amend `DESIGN_PRINCIPLES.md`
or `DOMAIN.md`, do not decide whether to build AV ingestion (Step 6 of the
build sequence), do not change `EVALUATION_PROMPT.md` or any gate, and do not
edit the state-of-play document.

Open with resume status, then:

> **Q1 - corpus integrity: [intact / defect found in N transcripts: list].**
> DB-side census: [N] ALL16 transcripts checked, [N] outliers flagged by the
> 40%-of-ticker-median rule, closing-language match [N/total], Q&A presence
> [N/total]. The four named pilot-flagged rows (EOSE Q2, SPWR Q1, SPWR Q3,
> AMPX Q3): DB-side looks [complete / also truncated] on [which checks].
> Q2 - AV classification: AMPX Q3 [confirmed truncated / other], EOSE Q2 /
> SPWR Q1 / SPWR Q3 [truncated / summarized-but-complete / unclear], same
> mechanism as AMPX Q3: [yes / no]. Rename-timing check: [argues for / argues
> against] a rename-transition artifact. Step 4: [not run, Step 1 clean /
> not run, budget exhausted / run - N additional samples, budget used N of
> [fresh daily quota]]. **Bottom line for Tests 4/5/6: [blocked / not
> blocked] by a transcript-completeness defect.**

Flag plainly: any transcript that fails the completeness check, any
disagreement between Step 1 and Step 2's readings for the same sample, and
whether this changes Test 3's blocking status on Tests 4/5/6 in §7.

**A diagnostic that contradicts an expectation stated in this prompt is a
finding, not a reason to stop** - including if Step 1 finds the DB corpus
itself has gaps, which this prompt does not currently expect but must not be
argued away if found.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers or path assumptions.
- No LLM calls, no re-scoring, in Steps 1-3. **No DB writes** - all queries
  `SELECT` only. Do not modify `EVALUATION_PROMPT.md`.
- AV API calls only in Step 4, only if both its gates pass, capped at 2,
  >=70s spacing, no auto-retry into a rate limit, budget reconfirmed fresh
  before the first call.
- No cache refreshes - `price_cache.json` / `fundamentals_cache.json` stay
  frozen.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`. Leave
  other sessions' untracked state alone; if `.git/index.lock` is fresh, wait
  and retry rather than removing it.
- Every figure quoted must name its provenance - table/column, manifest
  path and JSON key, or file and line.
- Report wall-clock runtime, cells run, and cells reused.
- Complex commands and SQL in fenced blocks in the wrap-up, not separate
  files.
- Do not write new handoff docs. This prompt in, one wrap-up out.
