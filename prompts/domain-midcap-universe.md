# Domain mid-cap universe — does the machinery pick winners, outside a raging bull?

`run_id` **`domain-midcap-universe`**. Branch: cut
**`sweep/domain-midcap-universe`** from `sweep/db-corpus-baseline`. No merge
to `dev`.

**Spend: Anthropic API calls permitted in Step 4 only**, behind an explicit
confirmation gate, ~$40 expected. **EC vendor calls permitted in Steps 2 and
4a**, under a hard cumulative cap (see Ground rules). **No DB writes
anywhere — `SELECT` only.**

---

## 1. Framing — what this run exists to answer

Two questions, deliberately separated, because a run that conflates them
answers neither:

- **Q1 — discrimination.** Within one universe, does the evaluator's verdict
  carry information about which names go up and which go down? Measured at
  the analyst layer, on excess forward returns, against a shuffled-label
  null. Step 5.
- **Q2 — production.** What does the settled allocator, fed those verdicts,
  actually produce on an in-domain universe that is *not* the megacap cohort
  that carried the S&P over 2022–2025? Measured against equal-weight
  buy-and-hold of **the same universe**, a zero-information arm, and a
  randomized arm. Step 6.

**A null on Q1 with a positive Q2 means exposure, not skill.** Say so in the
report if that is what comes back.

### What is already established — do not spend budget rediscovering it

- **The result is the universe.** `wrap-ups/test5-universe-substitution-out.md`
  and `docs/handoffs/2026-09-07-state-of-play.md` §7: swapping four
  established names costs −$60,810 (−33.8%); across 25 random baskets a
  single indicator, NVDA in or out, explains **94%** of the variance
  (+$33,467). The published figure is mostly a property of a universe that
  was hand-built on 2026-05-23 with outcomes known. **This run exists
  because of that finding.** Do not re-derive it.
- **The analyst weights, it does not select**, under `new_calls_only` at
  X=2.5pp — 15 of 16 names held, none rejected (09-03 §5.1). Whether it
  *could* select is Q1, and has never been measured directly.
- **Per-tier noise floors** (`wrap-ups/test4-analyst-noise-floor-out.md`):
  large 0.0pp, mid 0.0pp, megacap 3.77pp, **small/micro 14.34pp**;
  `recommendation` flips on **67%** of small/micro transcripts across
  identical re-runs. A universe built to exclude megacaps is a universe
  where this matters most — which is why Step 4a and Step 5's stability
  bound exist.
- **That instability is economically inert on the canonical configuration**
  — $533 (0.30%), 31x cheaper than the same noise volume elsewhere
  (`wrap-ups/small-cap-instability-materiality-out.md`). It is **not**
  established that it is inert for a *rank statistic*, which is a different
  quantity. Do not import that conclusion into Step 5.
- **No instruction-removable look-ahead** on the analyst
  (`wrap-ups/test6-look-ahead-prohibition-out.md`). Recall-driven bias
  remains unfalsifiable and is not this run's problem.
- **The hand-copied DB corpus is clean** — 0 of 337 flagged
  (`wrap-ups/test3-transcript-ingestion-fidelity-out.md`).
- **EC (earningscall.biz) is the transcript source.**
  `wrap-ups/ec_transcript_fidelity_benchmark_1-out.md`: 1.03% truncation
  (Wilson [0.3%–3.7%]), median similarity 0.242 vs AV's 0.048.
  `wrap-ups/test7-ec-score-fidelity-out.md`: 0 divergences on all four
  primary fields across 7 cells. **Two known EC defects carry into this
  run:** whole-company coverage misses (GOOGL absent entirely), and
  returning **a different company's transcript from a different year**
  (old SunPower Q3 2023 under SPWR). Step 2 tests for both.

### Closed — do not reopen

`docs/architecture/DOMAIN.md` (the circle of competence, incl. Defense
removed as standalone), `DESIGN_PRINCIPLES.md` §1 (analyst/allocator
firewall), the settled allocator configuration
(`ALLOCATOR_OPERATING_MODEL.md`), and the refuted mechanisms listed in
`CLAUDE.md` ("Do not re-propose what has been refuted"): transcript
anonymization, the variable Type B cap, the cash-reserve knob, the mid-day
`start_of_day_value` backfill.

---

## 2. Ground rules — the do-not list

1. **No DB writes.** `SELECT` only. New scores go to a **file-based eval
   cache**, never to the `Analysis` table. The canonical corpus is not
   touched, extended, or re-scored by this run.
2. **No merge to `dev` or `main`.** Own branch.
3. **Anthropic calls: Step 4 only**, after the confirmation gate in Step 4
   prints the exact transcript count and estimated cost and a human answers.
   Zero calls in Steps 0, 1, 2, 3, 5, 6, 7.
4. **EC calls: hard cumulative cap of 700.** 211 are already used
   (`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json` →
   `calls_used_total`). The refund condition is **under 1,000 total calls**
   and the window closes **2026-09-13**; the owner has elected to preserve
   that option. The driver **refuses call 701** and stops cleanly. If the
   refund decision has since been made and recorded, a human may raise the
   cap — the driver reads it from a constant, never infers it.
5. **Run the promoted prompt and model, not a candidate.**
   `evaluation_prompt` v6, sha256 `357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`;
   `model` `claude-sonnet-4-6`. Assert both via `analysis/version_guard.py`
   **before call one**, record the loaded prompt's hash in the manifest, and
   refuse to run on a mismatch. Do **not** set `PROMPT_CANDIDATE`.
6. **Do not modify** `analysis/test4_noise_floor*/`,
   `analysis/test6_look_ahead/`, `analysis/av_fidelity_benchmark_2/`,
   `analysis/ec_fidelity_benchmark_1/`, any existing `run_state` directory,
   or the prompts and wrap-ups of completed runs. Reuse the EC driver's fetch
   helpers **by import**; do not reimplement and do not edit them in place.
7. **Never mutate `docs/architecture/VERSION_REGISTRY.json` for a
   demonstration.** Step 6 registers one new benchmark record; it does not
   overwrite `ew_baseline` (see §6.4).
8. **Do not write a handoff document.** One prompt in, one wrap-up out to
   `wrap-ups/domain-midcap-universe-out.md`.

---

## 3. Step −1 — resume protocol

State in `analysis/data/run_state/domain-midcap-universe/`, un-ignored in
`.gitignore` and committed.

- `progress.json` — written as the **very first action, before any reading**:
  `prompt_sha256`, `driver_commit`, per-step status
  (pending / in_progress / done), a one-sentence `next_action`, `notes[]`,
  plus `ec_calls_this_run`, `ec_calls_cumulative`, `anthropic_calls`,
  `anthropic_tokens_in`, `anthropic_tokens_out`.
- `cells.jsonl` — one line per completed cell (`cell_key`, `params`,
  `config_hash`, `results`), **flushed after every cell**. A killed session
  loses at most one.
- `findings.md` — append-only, written **the moment** a finding is
  established. Never held in memory for a final composition pass.

`config_hash` = sha256 over the driver commit plus the full sorted parameter
set. On start: matching `prompt_sha256` → resume, skipping completed steps
and any cell whose `config_hash` already appears. A changed prompt archives
the old state and starts fresh. A changed `driver_commit` invalidates
`cells.jsonl` but keeps `findings.md`. **Report what was reused.**

Scored transcripts are their own resume unit: a transcript whose eval file
already exists with a matching prompt hash is never re-scored.

---

## 4. Step 0 — hygiene, and the one gate that proves the harness

1. **Clean tree.** Hard stop if `git_dirty` cannot be recorded `false`.
   Note: the working tree currently carries untracked
   `analysis/test4_noise_floor_v6/` and `test4-analyst-noise-floor-v6*` run
   state from a halted run — **do not delete, do not commit, do not run**
   them; record their presence and treat them as out of scope.
2. **Driver committed before any manifest, as its own commit.**
3. **Harness reproduction gate (hard).** On the frozen DB corpus, ALL16,
   settled configuration, window **2022-01-01 → 2024-06-12**, reproduce
   `final_value` = **$179,944.91** —
   `docs/architecture/VERSION_REGISTRY.json` →
   `benchmarks.settled_control.figures.final_value` — **to the cent**, via
   Test 1's pipeline (`load_call_events` → `build_type_function` /
   `build_tier_function` → `recompute_trend_layer`), the same path Test 5
   used. If it does not reproduce, **stop and report**; the harness is
   broken and nothing downstream is trustworthy.
   **This figure is a harness check and nothing else.** It is anchored to
   the retired `claude-sonnet-4-20250514` analyst and to ALL16. Per
   `PROMOTION_GATE.md` §11.1 it is **never** a comparison target for any
   number this run produces. Do not put it in a table beside a Step 6 arm.
4. **Version guard** as in Ground rule 5. Record prompt hash, model id, and
   `allocator_simulator` hash in the manifest.
5. **Do not use** the `run-allocator-sweep-db-corpus` pipeline or its
   reference figures (`wrap-ups/run-allocator-sweep-db-corpus-out.md`:
   stalled, baseline did not reproduce, $110k vs a $287k reference).

### Known unfixed defects — record them, never gate on them

Per `CLAUDE.md` guardrail 4, a gate testing a documented unfixed defect can
never pass. State explicitly in the wrap-up that these were known going in:

- **The tier classifier is not point-in-time** (09-07 §7.5). One snapshot of
  `fundamentals_cache.json` tiers every session of the backtest. This run
  treats it as an **axis** (§6.5), not a gate.
- **`fundamentals_cache.json` is ~124 days stale** — `whats_live.py` [5]
  reports a cache-age breach. Step 3 refreshes it; the breach is expected
  before that and is not a stop.
- **FSLR transcript ids 280 and 284 are a genuine duplicate.** De-duplicate
  in any draw that touches the DB corpus.
- **EC returns a different company's transcript on at least one known cell.**
  Step 2's identity check exists for this.
- **`if recommended_size_pct else cap_pct` is a truthiness test** — `0.0`
  and `None` both fall through to the full cap (09-07 §4.1). Confirmed not
  live on the canonical corpus; **count zeros and nulls on this universe**
  and report the count, since these are different companies.

---

## 5. The work

### Step 1 — build the pool and the universe ($0, no vendor calls)

The whole point of the rule is that it is applied to **2021-12-31 data with
no knowledge of what happened next**. Every judgement call made here is a
place hindsight can re-enter; write each one down.

**1a. Candidate pool.** Enumerate in-domain candidates as of 2021-12-31 from
a **dated, citable, survivorship-including source** — archived index or
sector-ETF constituent lists as of that date (solar, battery/storage,
semiconductor, and — labeled separately — IT/software/cloud), or an
equivalent point-in-time constituent source. Record, per name, the source
and the as-of date. `DOMAIN.md` decides in-domain membership; Tier 2 names
(IT/software/cloud, scoped crypto) are carried as a **separately labeled
subset** so a weak result there reads as a domain-expansion question, not as
the allocator underperforming inside its stated edge.

> **Pool integrity gate (hard).** The pool **must contain at least one name
> per Tier 1 domain that ceased to trade by 2026-05-08** (delisted,
> acquired, or bankrupt). A pool with zero dead names is not a lucky draw —
> it is proof the source is survivorship-filtered. **Stop and report**
> rather than proceeding with a clean pool.

**1b. Point-in-time market cap.** Close on 2021-12-31 × shares outstanding
at the nearest reported quarter (yfinance `get_shares_full` over
2021-10-01 → 2022-03-31). Record the method and both inputs per name.
**Cross-check the five largest against an independent published figure** and
report the discrepancies; a >10% disagreement on any of the five means the
method is not trustworthy for ranking — say so.

**1c. The rule.** Exclude any name with 2021-12-31 cap **≥ $150B**
(the megacap cut). Take the **top 20 by cap** among the remainder.
**Print the full cut list with each name's cap**, so the reader sees exactly
who the threshold removed. Also print the universe the rule yields at
**$100B** and **$200B** — as a *sensitivity table only*, not as arms, and
not as a reason to move the threshold after seeing it.

**1d. Write the universe before any fetch.** Final list with, per name: cap,
domain tier (1 or 2), sub-domain, alive/dead as of 2026-05-08, and for dead
names the last trading date. Commit it. **A universe that changes after Step
2's coverage results are known is hindsight** — if coverage forces a drop,
the name is *dropped and reported*, never *replaced*.

### Step 2 — coverage probe (EC calls, 0 Anthropic calls)

Coverage decides spend. **No scoring until this step's table is written.**

For every name in the Step 1d universe, including the dead ones, establish
EC coverage for **2022Q1 through 2025Q4** (16 quarters). Reuse, by import
from `analysis/ec_fidelity_benchmark_1/driver.py`:

- the vendor-native event matching and `vendor_payload_to_text_and_turns`;
- the **call-month quarter bucket** (Jan–Mar → prior-year Q4, Apr–Jun → Q1,
  Jul–Sep → Q2, Oct–Dec → Q3) — **never** derive a quarter by subtracting N
  days from the call date;
- **case-insensitive** rate-limit detection against the response's *values*
  (the bug that once misfiled 175 rate-limit responses as coverage misses);
- the dangling-handoff and closing-keyword checks;
- the `speaker_name_map_v2` handling (speaker names live in a top-level map,
  not inline).

Count misses by **kind**, separately: company absent / event absent /
**wrong company or wrong year returned**. The third kind gets an explicit
identity check — company name and fiscal period in the returned payload must
match the requested ticker and quarter. Treat an implausible miss rate as a
bug hypothesis before a finding.

> **Coverage gate (hard, one clause).** A name with fewer than **12 of 16**
> quarters available is dropped from the portfolio arm and reported. **If
> more than 5 of the 20 drop, stop and report** — the universe is not
> measurable at the intended depth, and the right next move is a different
> pool, not a thinner one.

Report, separately, the coverage rate for **dead** names against live ones.
That number bounds how much survivorship this design can actually remove,
and it is a finding in its own right.

### Step 3 — prices and fundamentals ($0, no vendor calls)

- `analysis/fetch_prices_for_tickers.py` for every surviving name,
  2020-01-01 → 2026-05-08, merged into `analysis/data/price_cache.json`.
  Dead names need history through their last trading day; record the
  delisting date and last close.
- Any name with a gap inside the backtest window that would break daily
  mark-to-market is **dropped and reported**, under the same one-clause rule
  as Step 2.
- `analysis/fetch_fundamentals.py` for the universe (this also clears the
  `whats_live.py` [5] cache-age breach). Snapshot values — see §6.5.
- Confirm `SPY` and `QQQ` cover the full window for Step 6 arm 5.

### Step 4 — scoring (the only paid step)

**Confirmation gate before call one.** Print: exact transcript count, the
per-transcript rate used, the resulting estimate, and the cumulative EC
calls. Wait for a human. Observed rate for the estimate:
**~$0.09/transcript** — `wrap-ups/test7-ec-score-fidelity-out.md` (30 calls,
577,225 tokens, ~$2.79) and `wrap-ups/test4-analyst-noise-floor-out.md`
(250 calls, ~4.8M tokens, ~$23). **Both are estimates at list rates, not
billed figures** — carry that caveat into the wrap-up rather than dropping
it.

**4a. Fetch and score the corpus.** ≤20 names × 16 quarters ≈ 320
transcripts ≈ **$29**. Promoted v6 + `claude-sonnet-4-6`. Write each result
to `analysis/data/evals/v6_sonnet-4-6_domainmid/<TICKER>_<YYYY-MM-DD>.txt`
in the `---STRUCTURED--- {...} ---END STRUCTURED---` shape
`analysis/simulator/data_from_cache.py:load_events_from_cache` parses —
verify the parse round-trips on the first file before scoring the rest.
**No `Analysis` rows. No DB writes.**

Persist per call; run **5-way concurrency**. Test 6's driver silently
dropped both instructions from its prompt and spent ~5 hours of wall clock
it did not need to — check at the end that both were actually honored and
report if not.

**4b. Stability subsample.** Re-score a **stratified 60-transcript
subsample** (stratified by domain sub-tier and by 2021-12-31 cap quartile,
fixed reported seed) **2 further times**, 3 runs total ≈ **+$11**. This
exists only to bound Step 5; it is not a noise-floor measurement and must
not be quoted as one. Expected total spend ≈ **$40**.

### Step 5 — the discrimination measurement ($0) — run this first if budget is short

Once Step 4's cache exists, **this is the highest-value step in the run**
and costs nothing. A budget-limited session does Step 5 before Step 6.

**Quantities, each named by kind every time it is quoted:**

- **forward draw, raw**: the ticker's return from T+1 to T+63 trading days
  after the call, and separately T+1 to the next call date for that ticker.
- **forward draw, excess**: the same span, minus the equal-weight universe's
  return over the **identical** span. Excess is the primary; raw is reported
  beside it so a reader can see how much is beta.

**Primary statistic.** Spearman rank correlation between the ordinal verdict
(`Exit` = −2, `Trim` = −1, `Hold` = 0, `Add` = +1) and **excess** forward
draw, computed on **`final_action`** (post-trend-layer), pooled and split by
domain tier. Report the same statistic on `per_call_rec` beside it — if the
trend layer adds nothing, that comparison is where it shows.

**The null.** Shuffle verdict labels **within ticker**, preserving each
ticker's own marginal verdict distribution, **2,000 times**; recompute.
Report the observed statistic, the null's 95% band, and p. **The comparison
of observed against that band is the answer to Q1.** Nothing else is.

**The stability bound.** Recompute the primary statistic from each of the
three Step 4b runs on the subsample; report the spread across them. **A
statistic whose re-run spread covers the null band is not a finding** —
state that outcome plainly if it occurs, rather than quoting the pooled
point estimate.

**Secondary.** `Add` minus (`Trim` ∪ `Exit`) mean excess forward draw, in
pp, with n per side and a Mann-Whitney U on the same data. Report the
verdict mix (counts per verdict per tier) — if the analyst issues almost no
`Trim`/`Exit`, say so; that is a live hypothesis from 09-03 §5.1 and a
one-sided verdict distribution caps any achievable rank correlation.

**Diagnostic, not a gate:** verdict distribution by realized full-window
return decile. **A diagnostic that contradicts an expectation stated in this
prompt is a finding, not a reason to stop.**

### Step 6 — portfolio arms and controls ($0)

Settled configuration throughout: **`swap_funding`, K=30, `new_calls_only`,
X=2.5pp lift-drop dead band, pooled accounts, `per_event_date` ordering.**
X is a per-position, per-session **speed limit** in percentage points of
portfolio (§9 invariant 9) — not a budget for new tickers, not a cap on
position size. Do not re-tune it here; §7.4 item 1 of the 09-07 state of
play notes the X optimum may not transfer off the canonical universe, but
**measuring that is a separate run**, not a silent parameter change in this
one.

Window: **2022-01-01 → 2025-12-31** primary. Also report
**2022-01-01 → 2024-06-12**, which has the same *shape* as the canonical
corpus window — a shape comparison only. Per `PROMOTION_GATE.md` §11.1 no
value from this run is comparable to `settled_control` or
`test1_zero_info_floor`; different model, different universe.

**Arms — all on the same universe, same events, same window, same ruler:**

1. **Live** — the real Step 4 scores.
2. **Equal-weight** — buy-and-hold of the same universe, equal dollars at
   window open, never rebalanced; plus a monthly-rebalanced variant.
   Dead names go to zero at delisting in the never-rebalanced variant and
   are redistributed at the next rebalance in the monthly one — state which
   treatment each figure used.
3. **Zero-information** — every verdict forced to `Hold`. Re-derive the
   value **on this universe**. **Do not quote $120,800** — that is ALL16's
   figure (`VERSION_REGISTRY.json` →
   `benchmarks.test1_zero_info_floor.figures`), a different universe and a
   retired analyst.
4. **Randomized** — verdicts shuffled within ticker, **25 seeds**, report
   median and full range.
5. **SPY / QQQ** over the identical window from `analysis/simulator/baseline.py`
   — orientation only, never the headline comparison.

**Arm 2 is the comparison that matters.** SPY and QQQ answer "was this a
good universe"; equal-weight of the *same* universe answers "did the
machinery add anything to holding it."

**6.4 The `ew_baseline` registry gap.** `whats_live.py` [4] flags
`ew_baseline` **UNREPRODUCIBLE** — no driver on record ever computed it and
its ruler is unknown. Arm 2 is a **new** figure under a stated methodology,
not a reproduction of that one. Register it under its **own key** with its
ruler declared explicitly (daily-marked; both-sided drawdown per
`PROMOTION_GATE.md` §11.3) and its `valid_while` list. **Do not overwrite,
edit, or reclassify the `ew_baseline` record.**

**6.5 Tier axis (an axis, not a gate).** The tier classifier is not
point-in-time (09-07 §7.5), and on a universe with no megacaps the tier
assignment decides starter size, cap, and Rule 3 for nearly every name — so
it cannot be left as one unexamined snapshot. Run arms **1 and 3** twice:

- **as-is**: the snapshot `build_tier_function` on the refreshed cache;
- **point-in-time**: tier computed from 2021-12-31 fundamentals and trailing
  volatility to 2021-12-31, using the same production 3-axis rule
  (vol ≥ threshold, cap < threshold, P/E > threshold or negative or null;
  speculative if ≥2 of 3 fire).

Report both, and the per-name tier disagreements. If the two differ by more
than the randomized arm's own spread, say so plainly — that makes the tier
input, not the analyst, the dominant term on this universe.

**Gates:**

- **G1 (hard).** The live arm and the zero-information arm must run on the
  identical event set, prices, and window. A difference in event count
  between them is a bug — stop.
- **G2 (hard).** Arm 1 and arm 2 must use the identical drawdown ruler, and
  the ruler must be named in the output beside every drawdown figure.
- **No gate on the live arm beating anything.** Whether it does is the
  finding, not the pass condition (`CLAUDE.md` guardrail 3).

### Step 7 — report

Open with: **`Scope boundary: report, do not decide.`** No change to
`DOMAIN.md`, `DESIGN_PRINCIPLES.md`, `BUILD_STATE.md`, or the settled
configuration. No vendor decision. No promotion.

Headline sentence, filled in:

> **Universe: [N] in-domain names, top-[N] by 2021-12-31 market cap below
> $[X]B, [D] of them no longer trading, built from [source, as-of date].
> Coverage: [n]/[N] usable at ≥12 of 16 quarters; dead-name coverage [a]/[b]
> vs live [c]/[d]. Q1 — analyst discrimination: Spearman [r] on
> `final_action` vs excess forward draw (n=[n]), shuffled-label null 95%
> band [lo, hi], p=[p]; re-run spread across 3 identical runs [s]. Add minus
> Trim/Exit excess gap [g]pp. Verdict mix: [counts]. Q2 — portfolio over
> 2022-01-01→2025-12-31: live $[v] / [dd]% dd, equal-weight (same universe)
> $[v] / [dd]%, zero-information $[v], randomized median $[v] (range
> [lo]–[hi]), SPY $[v], QQQ $[v]; ruler [named]. Tier axis: point-in-time
> minus snapshot = $[d] on the live arm. Spend: $[x] Anthropic ([c] calls,
> [t] tokens), [e] EC calls ([cum] cumulative of the 1,000 refund
> condition).**

Then, in plain English and with no identifiers in it, one paragraph: what
this says the system does on a universe chosen by rule rather than by
hindsight, and — separately — what it does not say.

**Flag plainly:** any figure whose provenance could not be established
rather than assumed; every name dropped and why; whether the pool integrity
gate passed on its own evidence; whether 5-way concurrency and per-call
persistence were actually honored; and whether the verdict distribution was
one-sided enough to cap the rank statistic mechanically.

---

## 6. Rules and gates carried forward, with their numbers

- **`DESIGN_PRINCIPLES.md` §1** — the analyst never receives portfolio data;
  the allocator never receives transcripts. Nothing in Step 5 or 6 crosses
  it.
- **`PROMOTION_GATE.md` §11.1** — every figure this run produces is new,
  under the tuple (v6 / `claude-sonnet-4-6` / this universe / allocator_v3).
  It is cited only within that tuple and is never set beside
  `settled_control`'s $179,944.91 or `test1_zero_info_floor`'s $120,800.
- **`PROMOTION_GATE.md` §11.3** — name the ruler beside every drawdown.
- **`CLAUDE.md` six guardrails** — one rule one clause (the Step 2 and Step 3
  drop rules are each a single test); a gate names the right quantity; a
  prediction is not a gate; never gate on a known unfixed defect (§4's
  list); do not ask a different algorithm to reproduce an old one
  bit-exactly (the only bit-exact gate here is Step 0's frozen-corpus
  replay); name the kind of every number.
- **Provenance** — every reference figure quoted as
  `<value>` — `<manifest path>` → `<json.key>`. Every comparison states, for
  each side, whether it is a forward draw, a median, or something else.

---

## 7. Standing rules

- `python3` / `pip3`, zsh-compatible, macOS Tahoe; no `--break-system-packages`,
  no `apt`/`apt-get`, `brew install` if a system tool is needed.
- No cache refresh beyond Step 3's explicit price/fundamentals fetch.
- Work on `sweep/domain-midcap-universe`. Driver committed as its own commit
  before any manifest. No merge to `dev`.
- One prompt in, one wrap-up out: `wrap-ups/domain-midcap-universe-out.md`.
  No proactive handoff document.
- **Running low on budget is a reason to stop cleanly, not to rush.** Write
  the wrap-up with what is done, mark the rest `pending` with a precise
  `next_action`, and say plainly that it is a partial run. A partial run
  that resumes is worth far more than a complete run that is lost.
