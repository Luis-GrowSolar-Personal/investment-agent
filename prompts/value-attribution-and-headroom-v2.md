# Value attribution and headroom, v2 — three layers, five reference lines

**Run ID:** `value-attribution-and-headroom-v2`
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/value-attribution-and-headroom-v2-out.md`

Supersedes `prompts/value-attribution-and-headroom.md` entirely. That prompt's
Step 0 gate ran and stopped; its wrap-up stands as the record of that stop, and
nothing else in it should be run.

---

## 1. Framing

### The objective — unchanged across two rounds of redesign

> **Who is contributing most to the portfolio's lift, and who needs the most
> work?**

This is a resource-allocation decision about where Luis spends his time. It has
two halves and both must be answered:

- **Contribution** — what each layer earned, in dollars, on this corpus.
- **Headroom** — what each layer could still earn if improved.

**They can point to different layers.** A layer can be large and near its
ceiling while a smaller one has room. That divergence is the decision-relevant
case and the reason this test is shaped around reference lines rather than a
single number.

### What is closed — do not re-derive

Two adjudication rounds settled the methodology. Read them for reasoning, not
for instructions:

- `wrap-ups/methodology-challenge-value-attribution-out.md` (round 1)
- `prompts/methodology-challenge-round-2-response.md` (round 2, with the
  consolidated 26-change list in §8)

Closed conclusions this prompt is built on:

1. **There is no tension between Test 1 and Test 2.** Test 1's comparator is
   zero-information; Test 2's is always-**bullish** (`analyst_direct_scorer.py`
   lines 18, 207). "+$59k versus a coin flip" and "−5.8pp versus permanent
   bullishness" are jointly true with nothing to reconcile. Do not reintroduce
   that framing. [#11]
2. **This is a three-layer system**, not two: analyst → trend layer → allocator.
   `sweep_funding_modes.py:96–113` — `compute_trend_verdict(history, tier)` then
   `apply_matrix(per_call_rec, verdict)` produces the `final_action` the
   allocator acts on, and `compute_final_confidence(...)` produces the
   `final_confidence` that orders funding priority in `rank_key()`. The
   allocator never sees `per_call_rec` directly. [#6]
3. **The corpus is usable as is and must not be re-scored.** It is frozen as
   `corpus_2026-04-06_to_2026-05-10` — a score stream of unverified prompt
   vintage. "The v6 corpus" is retired vocabulary; do not use it anywhere in
   this run's output. [#24]
4. **§3.1's specified baseline is always-hold; the scorer implements
   always-bullish** (F1). Until F1 is resolved, no lift figure from this scorer
   may be cited as §3.1's metric — cite it as "always-bullish-relative lift,
   SPY-benchmarked" or "always-hold-relative lift, SPY-benchmarked," naming the
   baseline every time. [#26]

### The starting question

> Does the real system, run end to end, beat a portfolio that simply bought the
> universe and held it — and if so, which of the three layers earned the
> difference?

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** No re-scoring, no evaluator invocations, no LLM
   calls of any kind. Every arm runs the existing simulator over already-stored
   scores. If any step appears to require a model call, **stop and report it in
   the wrap-up** rather than making the call. Assert this explicitly in the run
   log before the first arm.
2. **Do not modify any stored `Analysis` row.** All arms are read-only against
   the corpus; arms needing altered scores build an in-memory or scratch-file
   copy.
3. **Do not modify** `docs/EVALUATION_PROMPT.md`, `server/lib/versions.js`,
   `docs/architecture/VERSION_REGISTRY.json`, or the production prompt.
4. **Firewall (`DESIGN_PRINCIPLES.md` §7) holds throughout.** No portfolio data
   reaches the analyst or trend layers; no transcript data reaches the
   allocator. Stage D's oracle arm is the one place this is easy to violate by
   accident — read its warning.
5. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. `brew install` only if a system
   tool is genuinely needed. No `watch`, no `ls --time-style`.
6. **Do not fix known defects encountered in passing.** Two will come up: AMD
   classifies `speculative` under the 3-axis `tier_fn` (P/E 133.3, vol 62.8%)
   and runs at the 15% cap; and the production app never reads
   `type_classifications.json`. Both are recorded. Note them if they affect a
   number; do not repair them inside this run, and **do not gate on either**.
7. **No price-cache refresh.** `price_cache.json` stays frozen at its current
   last date (2026-05-08 as of writing). Refreshing it changes every ground
   truth and orphans the control.

---

## 3. Step −1 — resume protocol

`run_id` = `value-attribution-and-headroom-v2`. State lives in
`analysis/data/run_state/value-attribution-and-headroom-v2/`, un-ignored in
`.gitignore` and committed.

**Write `progress.json` as the very first action, before reading anything else.**
It carries `prompt_sha256`, `driver_commit`, per-step status
(pending / in_progress / done), a one-sentence `next_action`, and `notes[]`.

- `cells.jsonl` — one line per completed arm or shuffle: `cell_key`, `params`,
  `config_hash`, `results`. Flushed after every cell.
- `findings.md` — append-only, written the moment a finding is established.
  Never hold findings for a final composition pass.

On start: matching `prompt_sha256` means resume, skipping completed steps and
any cell whose `config_hash` already appears. A changed prompt archives the old
state and starts fresh. A changed `driver_commit` invalidates `cells.jsonl` but
keeps `findings.md`. Report what was reused.

`config_hash` = sha256 over the driver commit plus the full sorted parameter set.

**Running low on budget is a reason to stop cleanly, not to rush.** Write the
wrap-up with what is done, mark the rest `pending` with a precise `next_action`,
and say plainly that it is a partial run.

---

## 4. Step 0 — hygiene, verification, pre-registration

**0a. Clean tree.** Hard stop if `git_dirty` cannot be recorded `false`. Commit
the driver before any manifest, as its own commit.

**0b. Resolve the control and floor figures with provenance.** This prompt
quotes **$179,944.91** (actual) and **$120,800** (Test 1 zero-information floor)
from conversation. Both are premises to verify, not facts. Resolve each against
its manifest and cite it as `<value>` — `<manifest path>` → `<json.key>`, and
state for each whether it is a **forward draw**, a **median across draws**, or
something else. Check `wrap-ups/analyst-sensitivity-out.md` and the
`settled_control` / `test1_zero_info_floor` registry records.

**If either disagrees with the figure quoted here, the discrepancy takes
priority over everything else in this run — report it and stop.**

**0c. State the eval-cache position.** `analysis/data/evals/` is absent from the
working tree, so the version-stamped artifact `analyst_direct_scorer.py` was
designed to read does not exist locally. Record that it was sought and found
absent, so a future session does not repeat the search. [#23]

**0d. Freeze the pre-registration.** Write
`analysis/data/value_attribution_v2/PREREGISTRATION.json` **before any arm
runs**, containing:

- the locked corpus, named `corpus_2026-04-06_to_2026-05-10`, with its ticker
  list (ALL16) and scoreable row count [#24];
- the window, the shared control, and the settled configuration
  (`swap_funding`, K=30, `new_calls_only`, X=2.5pp, `pooled`, `per_event_date`);
- the definition of every arm in Stages A–D;
- **the oracle's injection point** — `per_call_rec`, not `final_action` [#8];
- **the oracle's label encoding** — how bullish/bearish/neutral map onto
  `per_call_rec`'s action vocabulary — named as a bound-loosening assumption
  [#10];
- **the oracle's non-direction field synthesis** — what is supplied for
  `thesis_health`, `credibility_delta`, `stumble_type`,
  `mitigation_track_record`, `fresh_money_allocation` — named as a material
  bound-loosening assumption with its expected direction on the bound [#10];
- **the oracle's post-`2025-11-07` fallback** for events with no 182-day
  forward price [#20];
- the interaction-term convention;
- a fixed random seed for every stochastic arm;
- a UTC timestamp.

If the file already exists with different content, **abort** and report the
discrepancy — do not overwrite.

**All arms in Stages A–D run on this identical locked corpus, window and
control.** Stage E's arithmetic is invalid otherwise.

---

## 5. Stage A — the two reference arms *(highest value; run first)*

If budget permits only one stage, run this one. Arms 0b and 0 are the two
numbers most likely to change what Luis does next.

### Arm 0b — universe only (starter-only buy-and-hold) [#1]

Always-hold: `final_action` = Hold on every call, real allocator, settled
config, locked corpus.

`sweep_funding_modes.py:199–206` establishes that this is **not** a no-trade
degenerate arm:

```python
starter_fired = is_first_call and not had_position
```

`starter_fired` does not read `final_action`. Every ticker still receives its
starter (`STARTER_PCT_SPECULATIVE` 5.0 / `STARTER_PCT_ESTABLISHED` 8.0) on its
first call, and is then never added to and never trimmed. Arm 0b is a
starter-only buy-and-hold portfolio over the 16-name universe.

**This is the floor the whole table rests on.** Test 5 put Arm A at the 100th
percentile of 25 random universe draws and `tier_return_attribution.py` put
NVDA+AVGO+ORCL at 81.4% of P&L. Arm 0b isolates exactly that: what the universe
pays with no analyst, no trend layer, and no allocator discretion beyond entry.

**Everything the three layers add, together, is `actual − Arm 0b`.** Report that
difference explicitly and prominently. **If it is small, the honest answer to
the objective is "none of them — the universe did it," and that is a legitimate
and valuable outcome, not a failed run.**

### Arm 0 — always-bullish through the real allocator [#2]

Always-bullish: Add on every call, real allocator, settled config, same locked
corpus. It will saturate against the caps (`TYPE_A_SPECULATIVE_CAP_PCT` 15.0 /
`TYPE_A_ESTABLISHED_CAP_PCT` 35.0 / `TYPE_B_CAP_PCT` 50.0) and become
approximately a cap-weighted always-long portfolio. **Saturation is the arm's
answer, not a degeneracy.** Report the saturation frequency.

Compare to the control:

- **Arm 0 > control** — always-bullish beats the real system in dollars. Report
  it plainly, then continue; the objective still needs contribution and
  headroom, now against a more demanding reference.
- **Arm 0 ≤ control** — then the always-bullish-relative lift figure is grading
  something this system does not monetize. **That is a finding about the
  promotion gate itself**, larger than this test's original scope. Write it up
  as such and carry it into `PROMOTION_GATE.md` §10. Continue regardless.

Both arms become permanent reference lines in the Stage E table.

---

## 6. Stage B — uncertainty, before any further arms

Nothing downstream may be read as a magnitude until this stage runs.

**B1. Lift against both baselines.** [#3] Compute, on the same scoreable rows:

- always-**bullish**-relative lift (reproduces Test 2's aggregate)
- always-**hold**-relative lift — the baseline §3.1 actually specifies

Always-hold's hit rate is the fraction of scoreable events whose ground truth is
`neutral`, i.e. inside the ±5% dead band. Report both by year and in aggregate,
naming the baseline on every figure.

**Expectation, stated so a contradiction is legible — not a gate.** With bullish
fixed at 166/359, a bearish base rate near 20% puts always-hold near 33.7% and
the lift near **+6.7pp**, against **−5.8pp** for always-bullish. Same rows, same
predictions, opposite sign. *A result that contradicts this expectation is a
finding, not a reason to stop.*

**B2. Bearish ground-truth base rate.** [#4] The unconditional frequency of
bearish ground truth among scoreable events. This is the anchor the 09-13
handoff's "wrong roughly four times in five" lacks. Correct that language in the
same pass — with three classes and a bull-skewed tape, "at chance" is a live
reading.

**B3. Intervals.** [#5] McNemar on the paired per-call outcomes against **each**
baseline, plus a **ticker-block bootstrap** interval on every lift figure.
Effective n is far below 359: 182-day forward windows overlap heavily within
ticker, all 16 names are graded against one SPY factor, and P&L is concentrated.

**If a lift figure is inside its interval, say so plainly and prominently.** It
does not cancel the objective; it changes how every later number is read.

---

## 7. Stage C — contribution

### C1. Timing and selection — two permutation schemes [#12][#13][#14]

Keep every call the analyst made; destroy one mapping at a time, then run the
real system end to end (trend layer included).

- **Primary — within-ticker.** Shuffle which event each call attaches to, within
  the same ticker. Universe, per-ticker call distribution and call count all
  unchanged. Primary because Test 5 established that universe composition
  dominates, so a scheme perturbing the universe measures the wrong thing.
- **Second — cross-sectional.** Permute call labels across tickers **within the
  same event-date cohort**, holding the calendar fixed. This perturbs universe
  composition, which is its known symmetric weakness; it is here to bracket, not
  to arbitrate.

Requirements for both: **≥200 shuffles**, fixed recorded seed, full distribution
(median, 5th/95th, min, max), and the real arrangement's percentile. Report
**per-ticker event counts and the number of distinct achievable arrangements** —
a 4-event ticker admits 24, and 200 draws then quantize the percentile.

**Do not restate any "preserve chronology" constraint** — it was self-contradictory
and is deleted. **Step 2's 50th-percentile interpretation is withdrawn**: under
`pooled` funding the allocator is path-dependent and compounding, so the
within-ticker null is compound ("no timing skill **and** a calendar-invariant
allocator") and a mid-distribution result cannot distinguish the two. Report the
percentiles; do not pre-register a verdict on them.

### C2. Structure — four ablation arms [#15]

Hold the real calls fixed. Disable one mechanism at a time, re-run, report the
delta against the control **read against the C1 permutation null**, not as a
bare point delta.

| Arm | Disable |
|---|---|
| B1 | Type A/B caps (15.0 / 35.0 / 50.0) |
| B2 | Rule 3 — permit averaging down on speculative losers |
| B3 | Profit-take (`PROFIT_TAKE_THRESHOLD_PCT` 25.0 / `REDUCTION_PCT` 5.0) |
| B4 | Starter sizing — uniform entry instead of 5.0 / 8.0 |

State for each arm exactly what "disabled" means mechanically — removing a cap
requires defining what replaces it, and that choice changes the number. **Flag
any arm whose disable is ambiguous rather than picking silently.** All other
settled parameters stay fixed across every arm.

**A negative delta is a valid finding, not a bug.** A rule that costs money is
the most actionable result in this test; report it prominently.

### C3. The trend layer's contribution surface [#7]

Two measurements, both free, both from arms already running:

- the share of events where `apply_matrix` returns a `final_action` **differing
  from** `per_call_rec`;
- the share of funding decisions where `rank_key()`'s ordering would differ if
  `final_confidence` were held constant.

These size the third bucket. Without them the Stage E table cannot separate the
trend layer from the analyst.

### C4. Per-call attribution — leave-one-call-out [#16][#17]

**Do not use a bookkeeping split.** Set each call to neutral, re-run, take the
delta. That is a marginal contribution, and **it will not sum to the total —
that non-additivity is the honest signal, not a residual to manage.** The v1
reconciliation requirement is dropped; `tier_return_attribution.py`'s per-ticker
partition is additive by construction and does not transfer to a per-call one,
because calls interact through shared cash and `swap_funding`.

If 359 simulator runs is infeasible at this corpus size, **run the bearish
subset only and say so** — that is where the open question lives.

Report the 2×2 (§3.1 hit/miss × made/lost money) with counts and dollars, the
same 2×2 for bearish calls alone, and **label the dollar cells explicitly as
attributed, not causal.** Report the dollar axis **benchmark-relative as well as
absolute** — in this tape an absolute axis collapses the table into one
populated row.

---

## 8. Stage D — headroom, with bias declared

### D1. Analyst ceiling — the oracle arm [#8][#9][#10][#18][#20][#21]

For every event, replace the analyst's call with the one that turns out correct
— bullish if the stock subsequently beat the benchmark beyond the dead band,
bearish if it fell beyond it, neutral if it stayed inside — then run the **real,
unmodified trend layer and allocator**.

**Injection is at `per_call_rec`.** Injecting at `final_action` would bypass the
trend layer and measure a perfect analyst *and* a perfect trend layer while
wearing an analyst-ceiling label.

**Required reporting:**

- **Two-level sanity check.** At the **call level** the oracle's §3.1 hit rate
  is 100% by construction, among scoreable events — state that denominator. At
  the **`final_action` level** it will be below 100%, because `apply_matrix` can
  override a correct call. **That gap is a direct measurement of how often the
  trend layer overrides correct information**, and it is a finding, not a
  failure. If the call-level rate is not ~100%, the label derivation disagrees
  with the scorer and this arm cannot be trusted; say so.
- **Cap-binding frequency** — how often the oracle's desired target exceeded the
  cap. If it binds often, the "analyst ceiling" is largely an allocator artifact.
- **The post-`2025-11-07` tail** — its size, and the fallback used, exactly as
  pre-registered. A "use the real call" fallback silently deflates the contrast;
  if that is the choice, say so.
- **"Flawless" qualified** to flawless-at-182-days, ±5%, versus SPY. An analyst
  calling 30-day or multi-year moves is outside this bound entirely.

**Pre-registered as a finding, not a defect: oracle ≤ actual.** It would mean
the direction→action mapping is misaligned with the horizon §3.1 grades on, and
it would be the headline of this run.

**Firewall warning.** This arm constructs calls from forward returns — look-ahead
by design, which is the point of a ceiling. Oracle scores exist **only** in this
arm's scratch data: never written to the DB, never to a shared cache, never to
any path another arm or future run reads. Labels derive from price data only; no
transcript content and no portfolio state reaches the label. Label the arm
unambiguously as a look-ahead ceiling in every output file.

### D2. Allocator ceiling — an in-sample maximum [#22]

Search existing sweep outputs; do not launch a new sweep.

**Caution:** `wrap-ups/run-allocator-sweep-db-corpus-out.md` records a *stalled*
pipeline that never reproduced its baseline ($110k against a $287k reference,
stopped at Step 1). Its numbers are not usable. Establish which sweep artifacts,
if any, are trustworthy on this corpus, window and loader path.

**Label the result an in-sample maximum over the searched space, not a
ceiling** — it was selected on this same corpus and is upward biased. If no
trustworthy sweep covers this footing, **report it unavailable and say why.** Do
not substitute a figure from another corpus, window or loader path.

---

## 9. Stage E — the deliverable

**Scope boundary: report, do not decide.**

One table, with the sign of the bias printed **inside** it on each ceiling line
[#22], and the analyst headroom line labeled **"under the current allocator and
trend layer"** [#19]:

```
Arm 0b — universe only (starter-only buy-and-hold)      $ ______   ← floor
Test 1 — zero-information analyst                       $ ______   [verified 0b]
Arm 0  — always-bullish through the allocator           $ ______
Actual — real analyst + trend layer + allocator         $ ______   [verified 0b]

Total added by all three layers  (actual − Arm 0b)      $ ______

Contribution:   analyst ____ | trend ____ | allocator ____ | interaction ____
Headroom:       analyst ____ | trend ____ | allocator ____
                              [bias sign on each ceiling line]
```

**Report the interaction term as its own line. Do not force the terms to sum.**
The layers are genuinely coupled — allocator rules fire only in response to
trend-layer output, which fires only in response to analyst calls — and no exact
decomposition exists without a Shapley construction this run does not attempt.
**If the interaction term is large relative to the components, that is the
finding:** the layers are not separable and the question must be asked about the
set, not the parts.

Close with the plain-language reading the objective asks for, in this form:

> On this corpus, the universe alone paid ____; the three layers together added
> ____. Of that, the largest contribution came from the **____ layer**, and the
> largest remaining headroom is in the **____ layer**. These point to
> **the same layer / different layers**, which means ____________.

---

## 10. Scope — what this run does not answer

State these as limitations; do not let the conclusion overreach.

- Nothing here evaluates v10 or v10+auto1. That needs a challenger eval cache
  and real API spend.
- Every figure describes `corpus_2026-04-06_to_2026-05-10`, this universe, this
  window. Test 5 found Arm A at the 100th percentile of 25 random universe
  draws, so this universe is not representative and the apportionment may not
  generalize.
- The corpus is a score stream of **unverified prompt vintage**; 153 of 362
  scoreable rows fall outside the window the project uses to date v6. Run the
  `2026-05-02 12:33:23-04` split comparison (structured-field presence,
  `rawOutput` shape) [#25]. If it is a genuine vintage boundary, **these arms
  ran on a mixed-vintage stream** — state that as a property of the corpus here,
  not as a later discovery. If it is a batch boundary, note it and move on.
- Comparison arms are zero-information, always-hold, always-bullish and
  shuffled-self. This says nothing about whether the system beats a human, a
  rival model, or an index — no verified QQQ or SPY backtest comparison exists.
- Allocator headroom is bounded by the configuration space already searched.
- **F1 and F2 are unresolved** [#26]. Record both in `PROMOTION_GATE.md` §10:
  §3.1 specifies an always-**hold** baseline while the scorer implements
  always-**bullish**; and §3.1 specifies sector-ETF-relative grading (TAN for
  solar, worked ENPH example) while the scorer uses **SPY for all tickers**. F2
  is deferred — it needs TAN/SOXX history absent from `price_cache.json` and
  bears on no dollar arm — but no lift figure may be cited as §3.1's metric
  until F1 is resolved.

---

## 11. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Work on
  `sweep/db-corpus-baseline`; no merge to `dev`.
- **Provenance for every figure.** Quote a target as `<value>` —
  `<manifest path>` → `<json.key>`, and name the kind of number: forward draw,
  median across draws, phase-averaged median, or something else. A figure quoted
  without provenance is a premise to verify, not a fact.
- Record every arm's `config_hash` and random seed.
- One prompt in, one wrap-up out: `wrap-ups/value-attribution-and-headroom-v2-out.md`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The Stage B expectation about the sign flip is
  the most likely one to be contradicted.
- **Note anything encountered that contradicts this prompt's premises.** This
  prompt was written from an adjudication; the repo outranks it.
