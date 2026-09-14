# Value Attribution and Headroom — who creates the value, and who has room to grow

**Run ID:** `value-attribution-and-headroom`
**Cost:** **$0 in Anthropic API spend.** This is a hard constraint, not a target.
See "Absolute constraints" below.
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/value-attribution-and-headroom-out.md`

---

## Why this test exists

Test 2 (`wrap-ups/test2-look-ahead-hit-rate-by-year-out.md`) was run to probe
look-ahead bias and was filed "inconclusive by design." Its `lift` column was
never read. Read now, it says the production analyst prompt (v6) **underperforms
its own baseline on directional calls** — roughly −5.8pp aggregate across 359
calls, negative in four of five years, with bearish-call accuracy of 8.3%–24.0%
every year.

Test 1 says the analyst is worth ~$59,000 over a zero-information arm
($120,800 floor vs $179,944.91 control).

Both cannot be casually true. This test explains how they are jointly true, and
converts the explanation into a decision: **where should development effort go
next — the analyst layer, or the allocator layer?**

The deliverable is a six-line table (Step 6). Everything else is scaffolding for it.

---

## Absolute constraints

1. **ZERO Anthropic API calls.** No transcript re-scoring, no evaluator
   invocations, no LLM calls of any kind. Every arm in this test runs the
   existing simulator over already-stored scores. If any step appears to
   require a model call, **stop and report it in the wrap-up** rather than
   making the call. Before Step 1, assert this explicitly in the run log.
2. **Do not modify any stored `Analysis` row.** All arms are read-only against
   the corpus; arms that need altered scores build an in-memory or
   scratch-file copy.
3. **Do not modify the production prompt, `server/lib/versions.js`,
   `docs/EVALUATION_PROMPT.md`, or `docs/architecture/VERSION_REGISTRY.json`.**
4. **Firewall (`DESIGN_PRINCIPLES.md` §1) holds throughout.** No portfolio data
   reaches the analyst layer; no transcript data reaches the allocator layer.
   The oracle arm in Step 4 is the one place this is easy to violate by
   accident — read its warning.
5. **Environment: macOS Tahoe, zsh.** Use `python3`, `pip3`/`python3 -m pip`.
   Never `--break-system-packages`. No `apt`. `brew install` if a system tool
   is genuinely needed. No `watch`, no `ls --time-style`.
6. **Do not fix known defects encountered in passing.** Two will come up:
   AMD classifies as `speculative` under the 3-axis `tier_fn` (P/E 133.3,
   vol 62.8%) and so runs at the 15% cap; and the production app never reads
   `type_classifications.json`. Both are recorded. Note them if they affect a
   number; do not repair them inside this run.

---

## Step 0 — verification, then pre-registration (gated)

**0a. Resolve what `baseline` means.**

Read `analysis/analyst_direct_scorer.py` and determine exactly how the
`baseline` column in Test 2's table is computed. The specific question: **is it
a fixed strategy (e.g. "always neutral") whose hit rate happens to vary by
year, or is it derived from the realized outcome distribution of the same
events being scored?**

This matters and is not cosmetic. If the baseline is a strategy, then "lift"
means "the analyst versus an alternative you could actually have run," and
−5.8pp is a real indictment. If the baseline is computed from realized
outcomes, "lift" is closer to a descriptive residual and does not support the
claim that v6 is worse than not having an analyst.

Report the answer with the code that establishes it — quote the function.

**0b. Confirm provenance of the 359 calls.**

Establish which prompt version produced the `Analysis` rows Test 2 scored.
Check for a `promptVersion` column; `PROMOTION_GATE.md` §8 notes the schema may
not carry one, in which case reconstruct from `createdAt` against the corpus
window guards used elsewhere in `analysis/`:

    analysis_created_after  = "2026-05-02 12:33:23-04"
    analysis_created_before = "2026-06-27 16:26:16-04"

State plainly whether provenance is **confirmed** (a stamped column) or
**inferred** (reconstructed from timestamps), and report the count of rows
falling inside vs outside the window. Do not describe an inference as a
confirmation.

**0c. GATE.**

- If 0a shows the baseline is a **fixed strategy** and 0b puts the rows
  **inside the v6 window** — proceed to 0d.
- If either check fails or is ambiguous — **stop here.** Write the wrap-up
  with Step 0's findings only, and state explicitly what redesign the failure
  implies. Do not proceed to Steps 1–6 on a broken premise. A clean stop at
  Step 0 is a successful run of this prompt.

**0d. Freeze the pre-registration.**

Write `analysis/data/value_attribution/PREREGISTRATION.json` **before any arm
runs**, containing: the locked corpus (ticker list and transcript count), the
shared control arm, the window, the definition of each arm below, the
interaction-term convention, and a UTC timestamp. If the file already exists
with different content, **abort** and report the discrepancy — do not
overwrite. This is `PROMOTION_GATE.md` §5's pre-registration discipline and
§10's corpus-locking constraint applied to a $0 test.

**All arms in Steps 1–5 must run on this identical locked corpus, window and
control.** Step 6's arithmetic is invalid otherwise, and an apportionment that
looks precise while its terms were measured on different footings is worse
than no apportionment.

---

## Step 1 — H3: is "wrong by §3.1" the same thing as "lost money"?

§3.1 grades benchmark-relative return over 2 quarters with a ±5% dead band.
The portfolio earns absolute dollars over whatever holding period the allocator
chooses. These can diverge: a call can be a §3.1 miss and a large dollar winner.

Join, per call: the §3.1 verdict (hit/miss, using `analyst_direct_scorer.py`'s
own constants — do not reimplement them) against the realized dollar P&L of the
position that call drove in the control arm.

Produce the 2×2, with both **call counts and summed dollars** in every cell:

|  | §3.1 hit | §3.1 miss |
|---|---|---|
| made money | n, $ | n, $ |
| lost money | n, $ | n, $ |

Then report, for the same corpus:

- count-weighted hit rate (should reproduce Test 2's ~40.4%)
- **dollar-weighted hit rate** — the share of total P&L attributable to calls
  §3.1 graded as hits
- the same 2×2 split out for **bearish calls alone**, since that is where
  accuracy is worst (8.3%–24.0%)

Attributing P&L to an individual call requires a convention — a position is
touched by many calls over its life. State the convention chosen, justify it,
and show that total attributed P&L reconciles to the control arm's total within
a stated tolerance. Report the residual explicitly; `analysis/tier_return_attribution.py`
did this and carried a −$44.95 residual on ~$80k, which is the standard to meet.

---

## Step 2 — H1: does the analyst's *timing* matter?

A permutation test, sharper than Test 1's zero-information arm — zero-info
removes the analyst entirely and so conflates "its timing" with "its existence."

Keep every recommendation the analyst made. **Shuffle which event each one
attaches to, within the same ticker**, so the universe, the per-ticker call
distribution, and the call count are all unchanged; only the mapping between
call and quarter is destroyed. Then run the real allocator.

- **≥200 shuffles.** Report the full distribution: median, 5th/95th percentile,
  min, max.
- Report where the real arrangement ($179,944.91) sits, as a percentile.
- Use a **fixed, recorded random seed** so the result is reproducible.
- Preserve chronology within each shuffle — a call may only be assigned to an
  event date that existed for that ticker; do not create events.

**Interpretation to pre-register now, before seeing the number:** a real result
at or below the 50th percentile means the analyst's timing contributes nothing
measurable and the money came from the universe and the allocator's structure.
Above the 95th percentile means timing is contributing beyond chance.

---

## Step 3 — H2: what is each allocator rule worth?

Hold the analyst's real calls fixed. Disable one structural mechanism at a
time, re-run, report the dollar delta against the control:

| Arm | Disable |
|---|---|
| B1 | Type A/B caps (`TYPE_A_SPECULATIVE_CAP_PCT` 15.0, `TYPE_A_ESTABLISHED_CAP_PCT` 35.0, `TYPE_B_CAP_PCT` 50.0) |
| B2 | Rule 3 — permit averaging down on speculative losers |
| B3 | Profit-take (`PROFIT_TAKE_THRESHOLD_PCT` 25.0 / `REDUCTION_PCT` 5.0) |
| B4 | Starter sizing — uniform entry instead of `STARTER_PCT_SPECULATIVE` 5.0 / `STARTER_PCT_ESTABLISHED` 8.0 |

State for each arm exactly what "disabled" means mechanically — removing a cap
requires defining what replaces it, and the choice changes the number. Flag any
arm where the disable is ambiguous rather than picking silently.

**A negative delta is a valid finding, not a bug.** A rule that costs money is
the most actionable result in this test; report it prominently if one appears.

All other settled parameters stay fixed across every arm: `swap_funding`,
K=30, `new_calls_only`, X=2.5pp, `pooled`, `per_event_date`.

---

## Step 4 — the analyst ceiling (oracle arm)

The mirror of Test 1's zero-information floor. For every event, replace the
analyst's call with the one that turns out correct — bullish if the stock
subsequently rose beyond the dead band, bearish if it fell beyond it, neutral
if it stayed inside. Then run the **real, unmodified allocator** on those
perfect calls.

This bounds the most money a flawless analyst could have made inside this
system.

**Firewall warning.** This arm deliberately constructs calls from forward
returns, which is look-ahead by design — that is the point of a ceiling. It is
therefore the one arm that could contaminate everything else if its output
leaks. Requirements:

- The oracle scores exist **only** in this arm's scratch data. Never written to
  the DB, never to the shared eval cache, never to any path another arm or
  future run reads.
- The oracle label is derived from price data only. **No transcript content
  reaches this step**, and no portfolio state informs the label.
- Label the arm unambiguously in every output file and in the wrap-up as a
  look-ahead ceiling, not a result.

Also report the oracle arm's own §3.1 hit rate as a sanity check — it should be
at or very near 100% by construction. If it is not, the label derivation
disagrees with the scorer and Step 4's number cannot be trusted; say so.

---

## Step 5 — the allocator ceiling

Determine the best final portfolio value achieved by **any** allocator
configuration on this same corpus and window, versus the settled configuration.

Search the existing sweep outputs rather than running a new sweep. **Caution:**
`wrap-ups/run-allocator-sweep-db-corpus-out.md` records a *stalled* pipeline
that never reproduced its baseline ($110k against a $287k reference, stopped at
Step 1). Its numbers are not usable. Establish which sweep artifacts, if any,
are trustworthy on this corpus and window.

If no trustworthy sweep covers this footing, **report the allocator ceiling as
unavailable and say why.** Do not substitute a number from a different corpus,
window or loader path, and do not launch a new sweep inside this run — that is
a separate decision with its own overfitting exposure (`PROMOTION_GATE.md` §2.1).

State clearly that this ceiling is bounded by **the space already searched**,
not by what the allocator could achieve in principle.

---

## Step 6 — the deliverable

One table. This is what the whole run is for.

```
Floor (zero-information analyst, real allocator)   $120,800
Actual (real analyst, real allocator)             $179,944.91
Analyst ceiling (oracle calls, real allocator)    $ ______
Allocator ceiling (real calls, best config)       $ ______   [or: unavailable]

Analyst contribution   (actual − floor)           $ ______
Allocator contribution (from Step 3 arms)         $ ______
Interaction / residual                            $ ______

Analyst headroom   (analyst ceiling − actual)     $ ______
Allocator headroom (allocator ceiling − actual)   $ ______
```

**Report the interaction term honestly as its own line. Do not force the terms
to sum.** The allocator's rules only fire in response to analyst signals, so
the components are genuinely coupled and an exact decomposition does not exist
without a Shapley-style construction that this run does not attempt. If the
interaction term is large relative to the components, **that is the finding**:
it means analyst and allocator are not separable and the "where do I invest"
question must be asked about the pair, not the parts.

Verify the Floor and Actual figures against `wrap-ups/analyst-sensitivity-out.md`
rather than taking them from this prompt. If either disagrees, the discrepancy
takes priority over everything else in the run — report it and stop.

Close the wrap-up with a plain-language reading of **contribution versus
headroom**: which layer earned more, which has more room left, and whether
those point to the same layer or to different ones. Where they point to
different layers, say so explicitly — that is the decision-relevant case and
the reason this test was designed this way.

---

## Scope — what this test does not answer

State these as limitations in the wrap-up; do not let the conclusion overreach:

- Nothing here evaluates v10 or v10+auto1. That requires a challenger eval
  cache and real API spend.
- Every figure describes this corpus, this universe, this window. Test 5 found
  Arm A sitting at the 100th percentile of 25 random universe draws, so this
  universe is not representative and the apportionment may not generalize.
- The comparison set is zero-information and shuffled-self. This says nothing
  about whether the analyst beats a human or a rival model.
- Allocator headroom is bounded by the configuration space already searched.

---

## Output

Write `wrap-ups/value-attribution-and-headroom-out.md` containing: Step 0's two
verification answers with supporting code, the Step 1 2×2 with dollars, the
Step 2 distribution and percentile, the Step 3 per-arm deltas with each
disable's mechanics stated, Steps 4 and 5 with their caveats, and the Step 6
table with its plain-language reading.

Record every arm's config hash and random seed. Note anything encountered that
contradicts this prompt's premises — this prompt was written from a
conversation, and the repo outranks it.
