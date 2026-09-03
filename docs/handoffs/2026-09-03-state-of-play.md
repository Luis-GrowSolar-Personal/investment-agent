# State of Play — 2026-09-03

**Branch:** `sweep/db-corpus-baseline` (pushed) · `dev` (pushed, `c514ae1`)
**Read first on return:** this document, then §7's test plan. The two spec
documents written today (`PROMOTION_GATE.md` §2.3, `CONFORMANCE_FIXTURES.md`)
are the build-side output; everything else here is validation.

---

## 1. Where things stand in one paragraph

The allocator configuration settled on 2026-09-01 is unchanged and its backtest
corpus was confirmed clean today. Two defects were found and one was fixed: the
production analyst was running an ungated prompt while labelling its output as
the gated one (**fixed**, rolled back), and production is pinned to a model a
gate run explicitly rejected (**open**, needs a decision). Separately, the
promotion gate was extended to cover a class of change it never addressed —
whether the app actually implements the design that was validated. The session
closed by looking at what the simulated portfolio actually held, which raised two
questions about the backtest itself that are now a queued test plan (§7).

---

## 2. Settled configuration — unchanged

`swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp, `pooled`, `per_event_date`.

Published figures (`docs/handoffs/2026-09-01-allocator-state-of-play.md`):
**$184,819 final value, 17.32% max drawdown**, versus SPY $113,980/25.36%,
QQQ $119,178/35.25%, TMFC $120,512/32.99%, EW $120,427/42.76%.

**Nothing found today disturbs these.** See §4.

---

## 3. Promotion gate extended — implementation fidelity

`PROMOTION_GATE.md` as locked answered *"should we adopt this design?"* and never
asked *"did we build the design we adopted?"* §2.1 runs the simulator against the
frozen evaluation cache and never executes production code, so task #77's 11x
sizing divergence would have passed it unchanged.

Added (commit `d51d005`):

- **§2.3, implementation-layer changes**, fidelity hurdle. Comparison is on the
  **decision stream** — `(session date, ticker, side, shares, account)` — not
  dollars. Python-to-JavaScript bit-exactness is unachievable, and a trade-list
  diff localizes a defect where a dollar gap does not; this project has already
  paid two CLI sessions for that lesson.
- **§5d**, binary **CONFORM / DIVERGE**. There is no EQUIVALENT for fidelity.
- **Two headless tiers, neither of them a UI:**

| Tier | Fed by | Catches | Cadence |
|---|---|---|---|
| 1 — golden fixtures | state the fixture supplies | the decision function diverging from the validated model | CI, every commit |
| 2 — headless replay driver | state the app assembles itself, seeded DB, advanced date by date | input assembly: stale cash, per-account mis-aggregation, drift across sessions | per release |

  Tier 2 exists because tier 1 is blind by construction to exactly where §9
  invariant #5 and §11 defect #2 live.
- **§8** fixture version discipline; **§9.6–9.7** build steps, both prerequisites
  for `CLAUDE.md` Step 8(a); **§10** records the instrumentation UI as a deferred
  product feature, bound to §2.1's pre-registration so a knob panel cannot select
  settings on its own.
- **`CONFORMANCE_FIXTURES.md`** — the mechanics: fixture schema, manifest, the
  §8 coverage census, failure reporting, and the regeneration policy.

**This is still the next build work, ahead of Step 8(a).**

---

## 4. Prompt- and model-version drift

Full investigation: `docs/handoffs/2026-09-03-prompt-version-drift.md` (+ `.docx`).

### 4.1 What was wrong

`evaluate.js:12-13` reads `docs/EVALUATION_PROMPT.md` directly at module load;
`versions.js:18` hardcodes `PROMPT_VERSION = 'v6'`. The label and the content
were never connected. Since `87bcfaa` (2026-08-01) the file declared
`v10+auto1 (auto-iterate candidate — pending gate)` while every row was stamped
`v6`.

### 4.2 Fixed today

Rolled back on `dev` at **`c514ae1`** to the file's content at `7063465`,
sha256 `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`,
verified byte-identical. `versions.js` needed no change — `PROMPT_VERSION = 'v6'`
is true again. v10+auto1 remains at `87bcfaa` as an ungated candidate; its own
log records that v9 failed its stated gate (69.0% unstable vs v6's 21.4%) and
that v10's gate was never run.

### 4.3 Blast radius

**18 Analysis rows** — everything created in August. The original report said one
row because it anchored to the most recent deploy; Railway retains only 20
deployment records (earliest `2026-08-22T18:02:05Z`), so the first drifted deploy
cannot be dated from Railway. `87bcfaa` is itself a `dev` commit and `dev` took
44 commits between 2026-08-01 and 2026-08-23, so with deploy-on-push the drifted
build went live within days of 2026-08-01. Report corrected at `3efbf29`.

### 4.4 Corpus verdict — clean

The question that mattered. Every version-stamped row is outside the simulation
window:

```
 promptVersion |       modelVersion       | rows | earliest_call | latest_call | inside_backtest
---------------+--------------------------+------+---------------+-------------+-----------------
 v6            | claude-sonnet-4-20250514 |    6 | 2026-05-06    | 2026-06-11  |               0
 v6            | claude-sonnet-4-6        |   36 | 2025-08-05    | 2026-08-26  |               0
```

`inside_backtest` counts rows the simulator actually loads (call date in
2022-01-01 – 2024-06-12 **and** ticker in ALL16). Zero for both. The earliest
call date on any stamped row is 2025-08-05, over a year after the window closes.

The 764 unstamped rows are explained: `rebackfill_v6_analyses.py` was committed
2026-05-02, three weeks before the `add_version_columns` migration, so it had no
columns to populate. It regenerated wholesale from a single `data/evals/v6/`
cache directory — v6 by construction of its input. That directory has since been
deleted, so this remains circumstantial, not provable. The one attempt to
regenerate it stopped without spending anything
(`wrap-ups/regen-v6-eval-cache-and-run-sweep-out.md`: *"No sweep run. No cache
regenerated. $0 spent."*).

### 4.5 Model version — still open

`versions.js:19` pins `claude-sonnet-4-6`. `gate_ledger.json` entry 1 records
champion `v6_sonnet-4-20250514`, challenger `v6_sonnet-4-6`, `delta_pp -7.44`
against `noise_std_pp 4.2`, `robustness_ok false`, verdict **HOLD**. The
substitution was reintroduced at `9028d0e` (2026-06-27) with a code comment
claiming the dated snapshot was retired — never verified, never logged as a
process exception. 36 analyses have been scored by the rejected model.

**Accepted reality:** model retirement will force migrations indefinitely.
Prompt tuning is not the answer — v7 through v10 attempted it four times and
every measured attempt regressed. The response is §7's Test 1 plus a scheduled
§2.2b gate run, not a constant edited under pressure.

---

## 5. Portfolio composition — what the simulation actually held

`analysis/quarterly_composition.py` (commit `48c055a`), output
`analysis/data/quarterly_composition/runs.json`, generated at `3efbf29`,
`git_dirty: false`.

Median weight, percent of total portfolio, phase 0:

```
        22-03  22-06  22-09  22-12  23-03  23-06  23-09  23-12  24-03  24-06
AVGO       -    4.5    6.6   11.4   13.4   17.0   17.9   21.5   21.0   20.3
NVDA     2.5    4.0    1.6    2.0    5.9   10.2   10.5   13.3   20.3   24.0
ORCL       -    5.0    6.7   12.4   14.1   17.1   18.0   17.5   17.3   16.2
TTD      2.5    3.6    7.8    8.6   12.5   15.7   16.5   14.0   13.2   13.1
AMD      2.5    3.9    5.3    5.1    5.0    5.5    7.5    9.6   10.0    7.7
MSFT     2.4    4.9    3.2    6.4    4.7    7.0    7.0    7.3    6.8    6.0
GOOGL    2.5    1.7    0.8    0.5    0.3    2.7    5.5    5.3    4.5    4.7
ENVX       -    3.8    9.8    3.2    2.2    4.3    3.9    2.2    2.5    3.3
FSLR     2.5    1.6    2.2    2.8    5.8    3.1    2.2    2.1    1.5    2.6
AAPL     2.4    4.6    3.5    5.8    4.5    6.3    3.5    3.4    0.9    1.0
AMPX       -      -      -      -    2.5    0.9    0.4    0.3    0.9    0.7
TSLA     2.4    4.2    7.5    4.6    9.5    5.9    5.9    3.0    0.9    0.3
EOSE     2.5    0.7    3.2    1.7    1.5    2.1    0.4    0.1      -      -
QS       2.5    1.2    0.9    0.3    0.4    0.3    0.1    0.1      -      -
RUN      2.5    1.3    1.2    3.1    3.9    2.0    0.7    0.3    0.1      -
CASH    72.8   55.1   39.9   32.3   13.8    0.0    0.0    0.0    0.0    0.0
#names    11     14     14     14     15     15     15     15     15     15
```

Concentration:

| Quarter end | Largest position | Top 3 | Top 5 | HHI |
|---|---|---|---|---|
| 2022-03-31 | 2.5% | 7.5% | 12.5% | 67 |
| 2022-12-31 | 12.4% | 32.3% | 44.5% | 512 |
| 2023-06-30 | 17.1% | 49.7% | 66.9% | 1126 |
| 2023-12-31 | 21.5% | 53.0% | 75.9% | 1345 |
| 2024-06-12 | 24.0% | 60.5% | 81.3% | 1557 |

### 5.1 What it shows

- **It does not select; it weights.** 15 of 16 names held from Q1 2023 onward.
  The only genuine rejection is **SPWR — never held, in any draw, at any point.**
  SunPower filed for bankruptcy in August 2024, after the window closed. Worth
  confirming SPWR had scoreable events in the window rather than being excluded
  for a data reason; if it was a real decline, it is the most encouraging single
  fact in this table.
- **Early positions carry no signal.** Everything opens at exactly 2.5% — one
  session's maximum under `X`. Conviction only appears through repeated adds.
- **Four names are the portfolio:** AVGO, NVDA, ORCL, TTD ≈ 73% by the window's
  end. AVGO and ORCL do the most work and are the least-discussed.
- **Tier caps never bound.** Largest position ever is 24%, against a 35% Type A
  and 50% Type B cap. The binding constraint throughout is `X`, chosen for
  risk-adjusted return — not the concentration rules.
- **73% cash through the 2022 drawdown.** Full deployment takes until mid-2023,
  because 2.5pp per month from all-cash is slow. **A material part of the 17.32%
  drawdown advantage over SPY's 25.36% may be this start-date artifact rather
  than better decisions**, and it would not repeat for someone starting fully
  invested. Not yet quantified.

### 5.2 Two anomalies found while producing this — both need follow-up

1. **All 15 draws returned identical results.** Final value $179,945 and 20.85%
   drawdown for min, median and max; every quarterly weight identical across
   draws. The `seed` parameter had no effect at this cell. That is *plausible* —
   seeds break ties, and there may be no ties here — but it means the "15-draw
   range" reported for this configuration is a single point, and Rule 2's
   overlapping-range test has nothing to compare. **Verify whether this is
   correct behaviour or a seed that is not being threaded through.**
2. **Phase 0 alone gives $179,945 / 20.85%, against the published
   $184,819 / 17.32%.** The published figures are phase-averaged across three
   offsets; this run used phase 0 only. If that is the whole explanation, then
   *which day of the month you trade* moves drawdown by **3.5 percentage
   points** — a larger phase sensitivity than has been acknowledged anywhere.
   **Reconcile before either number is quoted again.**

---

## 6. Two questions about the backtest itself

### 6.1 The universe — open

Every sweep uses `ESTABLISHED = [AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA]`
plus eight speculatives. A genuine point-in-time list exists in the repo —
`verify_top20_2021_loaded.py`: *"Top 20 S&P 500 from Jan 2021, ADBE substituted
for BRK.B"* — but **the backtest did not use it**. Only five names overlap
(AAPL, MSFT, GOOGL, TSLA, NVDA).

- Dropped: AMZN, META, ADBE, NFLX, V, JNJ, WMT, JPM, PG, UNH, DIS, MA, HD, PYPL, BAC
- Added: AMD, AVGO, ORCL

The circle of competence explains eleven of the fifteen drops on a principled
rule (banks, healthcare, retail, payments, consumer are out of domain). It does
**not** explain dropping AMZN, META, NFLX and ADBE, all Tier 2 by
`DOMAIN.md`, nor adding AMD, AVGO and ORCL. The eight-name list first appears
2026-05-23 (`e35f978`) with no recorded rationale in any commit, spec or handoff.

**No conclusion is drawn.** The cause is unknown and may be entirely reasonable.
Test 5 measures the consequence either way, which is why the provenance question
does not need resolving first.

### 6.2 Look-ahead — documented, not ignored

`DESIGN_PRINCIPLES.md` §4 records this explicitly: anonymization was attempted
and abandoned April 2026 because companies are re-identifiable from financial
structure alone; the pipeline survives commented out in `backtest_runner.py`,
with `ANON_PROMPT.md` preserved. *"Backtests run with company identity known,
which matches production conditions. This is a documented limitation, not an
oversight."*

**One spec inconsistency to fix.** §1 of the same document claims the
analyst/allocator firewall is *"the primary structural defense against look-ahead
bias."* It is not, and §4 concedes as much. The firewall stops portfolio-aware
scoring; it does nothing about the analyst recognising a company and recalling
what followed, and because the allocator's only input is the score, a
contaminated score passes through perfectly. §1 should be narrowed to
portfolio-aware scoring and point at §4 for look-ahead.

**Counter-evidence worth keeping in view.** `gate_ledger.json` entry 1: the
*newer* model, with a later training cutoff and therefore more knowledge of how
2022–2024 resolved, scored **worse** (4.94pp lift to −2.5pp). If look-ahead were
the dominant driver, it should have scored better. The analyst's measured hit
rate is also only 60% (9/15). Neither is proof, but both point away from
leakage being what drives these results.

The prompt already carries `- Reference only information in the transcript`
(v6, line 168). That governs citation, not judgement.

---

## 7. Test plan — ordered, with dependencies

Ordering is by cost and by what blocks what, not by interest.

| # | Test | Cost | Blocked by |
|---|---|---|---|
| 1 | Analyst-quality sensitivity | none (simulator only) | — |
| 2 | Hit rate by year | none (existing scores + price cache) | — |
| 3 | Transcript ingestion fidelity (AV vs hand-entered) | AV API calls | — |
| 4 | Analyst noise floor | re-scoring, N runs | 3 |
| 5 | Universe substitution | transcript load + scoring | 3 |
| 6 | Look-ahead prohibition probe | full corpus re-score | 3, 4 |

### Test 1 — how much does analyst quality actually matter

Degrade the scores inside the backtest deliberately — flip a percentage of
recommendations, add noise — and measure the effect on final value and drawdown.

**Why first:** no API spend, and it prices everything else. If a 7-point drop in
analyst accuracy barely moves the portfolio, then model churn, scoring
instability and look-ahead all fall in importance at once. If it moves things
sharply, that is a fragility more important than any prompt, and it should be
known before execution is built on top.

Directly answers how worried to be about forced model migrations.

### Test 2 — hit rate by year

Calls from 2022 are more thoroughly represented in the scoring model's training
than calls from 2024. If look-ahead drives the scores, accuracy should decline
toward the cutoff. A flat line is strong evidence the analyst reads the
transcript rather than recalling the outcome.

Free — existing scores, existing price cache, no gate.

### Test 3 — transcript ingestion fidelity

`wrap-ups/av_transcript_fidelity_benchmark_1-out.md` found DB-vs-AV text
similarity of **0.18 or below** for EOSE and SPWR against 0.70+ for AMPX. If
transcripts are truncated, every score built on them is corrupt at the source.

**This is a prerequisite, not a peer.** Tests 5 and 6 load or re-score
transcripts through the same path; running them first would bake the defect in.

### Test 4 — analyst noise floor

The same benchmark found **4 of 7 samples failed the determinism gate** — same
transcript, temperature 0, and on EOSE Q1 the `recommendation` itself flipped
between Hold and Add.

n=7 on three tickers is not a noise floor. `PROMOTION_GATE.md` §6 already
requires this measurement; it has not been done at scale. **Test 6 is unreadable
without it** — a one-sentence prompt change cannot be detected against a
background where the score moves on its own.

### Test 5 — universe substitution, 16 versus 16

Hold the universe **size** constant. Under `new_calls_only` the number of names
*is* the deployment rate, so a 20-name arm would deploy faster and post a
different return from breadth alone, carrying no information about selection.

**Hold the eight speculatives fixed and swap only the eight established** — one
variable, and the speculatives are identical in both arms.

- **Arm A:** AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA (current)
- **Arm B:** the eight largest S&P names as of Jan 2021, by rule

Five overlap, so it reduces to a **three-name swap** — AMD/AVGO/ORCL out,
AMZN/META/one more in. Run `python3 analysis/audit_top20_2021.py` first: those
transcripts may already be loaded, which would make this far cheaper than it
sounds.

**Stronger version if the result is close.** Sample eight names at random from
the 2021 top twenty, twenty or thirty times, and build a distribution. Then see
where the actual eight land in it. That converts "were these names lucky?" into
a percentile. Needs all twenty loaded — the real cost — but answers the question
properly rather than suggestively.

**Selection must be by rule, not by hand.** Hand-picking the challenger arm
rebuilds the exact problem under test.

### Test 6 — look-ahead prohibition as a probe

Score the corpus twice: v6, and v6 plus one sentence — *evaluate as of the call
date; do not rely on knowledge of subsequent stock performance, later results, or
later news* — nothing else changed.

- Scores barely move → look-ahead was not doing much work.
- Scores degrade materially → look-ahead was in there, and was helping.

Either result is informative. **Note this is not a defense**: the analyst has no
tools and cannot look up a price, so prohibiting lookup forbids the impossible.
The leak is recall, and a model cannot be instructed not to know. Its value is as
a measurement.

**It is also a §2.2a prompt change** and cannot simply be adopted if it looks
good — it needs a gate run like any other candidate.

---

## 8. Open items that are not tests

- **Relabel the 18 August Analysis rows** — stamped `v6`, actually scored by
  v10+auto1. Relabel rather than delete; they are the evidence.
- **Startup hash-check.** Have the server hash the prompt file it loaded and
  refuse to boot if it does not match the version `versions.js` declares. Roughly
  five lines. It makes today's failure structurally impossible and is the live
  counterpart to `CONFORMANCE_FIXTURES.md`.
- **Model-version decision** (§4.5) plus a retroactive ledger entry recording the
  June change as a forced exception.
- **`testing/` is not gitignored on `dev`** — it holds real brokerage position
  exports and is currently untracked rather than ignored there, so a `git add -A`
  on `dev` would stage it. One line.
- **`CLAUDE.md` hosting line** still describes dev and prod services;
  `investment-agent-PROD` last deployed 2026-04-04, status FAILED, zero
  instances. All real work is on DEV.
- **`DESIGN_PRINCIPLES.md` §1** look-ahead claim (§6.2 above).
- **Corpus backup.** `~/investment-agent-backups/analysis_corpus_20260830.sql`
  still needs an off-machine copy. §2.3 now makes it a formal **release
  dependency**, not just a backup — without it the conformance fixtures cannot be
  regenerated at all, and the model that produced it is retired.

---

## 9. Build sequence position

Unchanged and not displaced by any of the above:

1. **Conformance fixtures** (`CONFORMANCE_FIXTURES.md`, `PROMOTION_GATE.md` §9.6)
2. **Headless replay driver** (§9.7)
3. **Step 8(a)** — in-app trading, per `CLAUDE.md`

§7's tests are validation and compete for the same hours. Test 1 is cheap enough
to run alongside; Tests 3, 5 and 6 are not.

---

## 10. Commits from this session

| Commit | Branch | What |
|---|---|---|
| `d51d005` | sweep | `PROMOTION_GATE.md` §2.3/§5d + `CONFORMANCE_FIXTURES.md` |
| `48c055a` | sweep | `quarterly_composition.py` |
| `96d5e81` | sweep | drift investigation prompt |
| `a4936c1` | sweep | drift investigation findings (CLI session) |
| `3efbf29` | sweep | drift report corrected — 18 rows, corpus clean |
| `c514ae1` | **dev** | **prompt rolled back to v6** |
