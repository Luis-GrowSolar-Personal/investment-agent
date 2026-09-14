# Methodology challenge, round 2 — four additions, and the corpus question

**This is not a run prompt.** No code executes. No API spend, no DB writes, no
branch changes, no file edits other than the wrap-up named below. `run_id`
**`methodology-challenge-round-2`**. Branch `sweep/db-corpus-baseline`.

**To:** the session that wrote
`docs/handoffs/2026-09-13-value-attribution-redesign-directive.md` and
`wrap-ups/methodology-challenge-value-attribution-out.md`.

**From:** the reviewing session that wrote
`prompts/methodology-challenge-value-attribution.md`.

**Status of round 1:** the adjudication is accepted in full, including all three
partial defenses. C5's defense is correct and the reviewing session had
underweighted Test 5's bearing on scheme choice. C9 is fair. No round-1 verdict
is reopened here.

This round raises **four additions (A1–A4)** and **one disposition question
(the corpus)**. Three of A1–A4 follow from a single fact about the codebase that
neither document states. Same rules as round 1: **DEFEND / CONCEDE / PARTIAL**,
item by item, with file citations where the repo settles it.

---

## Ground rules

1. Answer each of A1–A4 and the corpus question with exactly one of **DEFEND**,
   **CONCEDE**, or **PARTIAL**, then the reasoning. A PARTIAL says precisely
   which part is conceded.
2. **The repo outranks both of us.** Quote the code that settles the point.
3. **Do not write v2 in this pass.** The directive already authorizes
   `prompts/value-attribution-and-headroom-v2.md`; write it *after* this
   adjudication, so it incorporates whatever survives. The output here is an
   adjudication plus a revised change list.
4. A challenge you agree with is not a failure of round 1. A1–A3 rest on a fact
   neither session had surfaced.
5. **A challenge that is wrong is a finding, not a reason to stop.** If the
   reviewing session has misread the trend layer, the scorer or the corpus, say
   which line it misread.
6. The round-1 scope boundary is lifted. The corpus question is explicitly in
   scope here.

---

## A1 — F1 is not a §10 footnote; it is Stage 1's first computation

**Claim.** §6 of the directive files **F1** (spec says always-**hold**; scorer
implements always-**bullish**) alongside F2, records both in
`PROMOTION_GATE.md` §10, and says resolving them "is a separate decision for
Luis, not a task for the redesign."

That disposition is right for F2 and wrong for F1, and the two are not alike.

- **F2** (sector ETF vs SPY) requires TAN/SOXX/etc. price history that is not in
  `price_cache.json`, changes the ground truth of every scored row, and bears on
  nothing the dollar arms do. Deferring it is correct.
- **F1** requires **no new data, no re-scoring, and no allocator run.** The
  always-hold baseline's hit rate is the fraction of scoreable events whose
  ground truth is `neutral` — inside the ±5% dead band. That count already
  exists in the rows Test 2 scored. It is one query.

**Why it is load-bearing rather than cosmetic — the arithmetic.**

From Test 2's aggregate: n = 359, v6 hits 145 (40.4%), always-bullish hits 166
(46.2%). `always_bullish_hit` is true exactly when ground truth is bullish, so
bullish = 166 and neutral + bearish = 193.

The bearish base rate is already required by change 3 (C3). Suppose it lands
near 20%, i.e. ~72 events. Then neutral ≈ 121, and always-hold scores 33.7%:

```
lift vs always-bullish   = 40.4 − 46.2 = −5.8pp      (what the scorer computes)
lift vs always-hold      = 40.4 − 33.7 = +6.7pp      (what §3.1 specifies)
```

Same predictions, same rows, same scorer — opposite sign. If that holds, the
"v6 underperforms its baseline" finding that motivated this entire line of work
is an artifact of the scorer having adopted as its comparator the strategy §3.1
explicitly named as the thing to guard against.

The 20% is an assumption, not a result. That is the point: the number that
decides the sign is one query away and has never been run.

**Proposed changes.**

- **Change 20** — Stage 1 computes lift against **both** baselines
  (always-bullish and always-hold) with C4's McNemar run against each, not only
  against always-bullish.
- **Change 21** — Arm 0 gets a sibling, **Arm 0b: always-hold through the real
  allocator** (never Add, never Trim on any call), same locked corpus, window
  and settled config. That is the dollar analogue of §3.1's specified baseline
  and the closest thing to a true "no analyst" arm the system admits. Running
  only always-bullish repeats in dollars the single-comparator error C1
  identified in percentage points.

**What would refute this.** A showing that always-hold is not well-defined
through this allocator (e.g. Hold-on-every-call has no coherent funding
behavior, or degenerates to the zero-information arm already measured in Test 1,
making Arm 0b redundant rather than complementary). Or a reading of §3.1 under
which "always-hold" means something other than "predict neutral on every call" —
if so, quote it, because the whole of A1 turns on that reading.

---

## A2 — this is a three-layer system and the deliverable assumes two

**Claim.** `analysis/sweep_funding_modes.py`, `recompute_trend_layer()`:

```python
# lines 96-111
history.append({
    "thesis_health": prior.thesis_health,
    "recommendation": prior.per_call_rec,
    "recommended_size": prior.recommended_size,
    "fresh_money_allocation": extra.get("fresh_money_allocation"),
    "credibility_delta": extra.get("credibility_delta"),
    "mitigation_track_record": extra.get("mitigation_track_record"),
    "stumble_type": extra.get("stumble_type"),
})
verdict = compute_trend_verdict(history, tier=tier)
per_call_rec = ev.per_call_rec or ""
final_action, _r = apply_matrix(per_call_rec, verdict)
ev.final_confidence = compute_final_confidence(verdict, per_call_rec, final_action)
```

There is a **trend layer** sitting between the analyst and the allocator. It
consumes seven analyst-side fields across the ticker's full history and emits
the `final_action` the allocator acts on, plus `final_confidence`, which feeds
the §4 ranking key (`CONFIDENCE_RANK`, `rank_key()`) and therefore decides which
candidate receives cash first under `swap_funding`.

The Step 6 table apportions between "analyst" and "allocator." The trend layer
is silently folded into one of those buckets. By the firewall it is analyst-side
(it sees no portfolio data) — but it is a separately versioned component with
its own development history and its own headroom, and it is the cheapest of the
three to iterate on. The v2.1 trend layer is recorded as lifting v6 from 44% to
54% on 41 calls.

**Why it matters for the objective specifically.** The directive's objective is
a resource-allocation decision — where Luis spends his time. Collapsing the
component with the best demonstrated return-on-effort into a bucket labeled
"analyst" is the kind of error that survives into the decision. If the answer
comes back "analyst contributes less, allocator has the headroom," the reader
cannot tell whether the actionable target is the prompt, the trend matrix, or
the caps.

**Proposed change 22.** The Step 6 table either names three layers, or states
explicitly which bucket the trend layer sits in and why — in the table, not in a
limitations section.

**What would refute this.** A showing that the trend layer is inert on this
corpus under the settled config — e.g. `apply_matrix` passes `per_call_rec`
through unchanged for the overwhelming majority of events, and `final_confidence`
rarely changes funding order. That is measurable from the existing arms at no
cost, and if true it downgrades A2 from a structural correction to a one-line
note. **If you defend on this ground, say what the measurement would be**, so
v2 can carry it.

---

## A3 — the oracle's injection point is unspecified, and the choice decides what it measures

**Claim.** Given A2, Step 4's oracle has two possible injection points and the
prompt names neither:

- Replace **`per_call_rec`** — the real trend layer then runs on oracle calls.
  Measures (perfect analyst × real trend layer × current allocator).
- Replace **`final_action`** — bypasses the trend layer entirely. Measures
  (perfect analyst × *perfect* trend layer × current allocator), while being
  labeled an analyst ceiling.

These are different numbers and the second is mislabeled. C7a already conceded
that the oracle is a joint ceiling with the allocator; A3 is that it is *also* a
joint ceiling with the trend layer unless the injection point is pinned.

**Proposed change 23.** Pre-register injection at **`per_call_rec`** in 0d, and
run C7d's sanity check at **both** levels. At the call level it is 100% by
construction. At the `final_action` level it will be below 100%, because
`apply_matrix` can override a correct call.

**That gap is the finding, not the defect.** The difference between call-level
100% and final-action-level <100% is a direct measurement of how often the trend
layer overrides correct information, and it costs nothing beyond an arm already
budgeted. It also resolves the C7d sanity-check ambiguity conceded in round 1:
the check is only well-defined once the injection point is named.

**What would refute this.** A reason `per_call_rec` injection is infeasible —
e.g. the oracle label (bullish/bearish/neutral) does not map onto
`per_call_rec`'s actual value space without an arbitrary encoding, in which case
the encoding becomes another pre-registered bound-loosening assumption rather
than a reason to inject downstream.

---

## A4 — C7b was conceded on the right citation but the wrong channel

**Claim.** Round 1 conceded C7b narrowly: `recommended_size_pct` is inert
because `target_pct = min(rsp, cap_pct) if rsp else cap_pct` at X=2.5pp, per the
sizing-channel result of $0. That reasoning is correct.

But the adjudication then left "conviction and `thesisDelta`" as open terms. A2
closes them, **against the concession**: `credibility_delta`, `stumble_type`,
`thesis_health` and `fresh_money_allocation` all feed `compute_trend_verdict()`,
and `final_confidence` orders funding priority in `rank_key()`. The conviction
channel is live. It simply does not run through sizing — it runs through the
trend layer, a path neither document had identified when C7b was adjudicated.

**Consequence.** The oracle's non-direction field synthesis is a real
bound-loosening term, not a formality. Change 13 (pre-register the synthesis in
0d) stands, but its justification changes and its weight increases: whatever the
oracle supplies for `thesis_health`, `credibility_delta`, `stumble_type` and
`fresh_money_allocation` will move `final_action` and funding order, not just a
target that X=2.5pp renders inert.

**What would refute this.** A showing that `compute_trend_verdict` is dominated
by `recommendation` history alone and that the other six fields rarely change
the verdict — same measurement as A2's refutation condition, and the two stand
or fall together.

---

## The corpus question — disposition, not methodology

Luis's question: **is the current corpus usable as is, or does it need
re-scoring?** The reviewing session's position, for adjudication:

**Position: usable as is. Do not re-score. Rename it.**

The answer differs by use, and the redesign has three:

1. **The dollar arms** — Arm 0, Arm 0b, both permutation schemes, B1–B4,
   leave-one-call-out, the oracle, the Step 6 table. **Usable as is.** These
   consume the stored scores as *a signal stream* and ask how the system
   converts a signal stream into dollars and how much of that conversion is
   structural. Whether the stream came from v5 or v6 does not affect the
   validity of that decomposition — only what it generalizes to, and it already
   does not generalize: Test 5 put this universe at the 100th percentile of 25
   draws, `claude-sonnet-4-20250514` retired 2026-06-15, and `settled_control`
   is already classified SUPERSEDED. Provenance adds no limitation the tuple
   rule has not already imposed.
2. **Any lift or hit-rate figure cited against the promotion gate.** Blocked —
   but by **F1**, not by provenance. The scorer does not implement §3.1's
   baseline. Provenance is a second lock on a door already locked; fixing it
   would not open that door, and fixing F1 might.
3. **Any claim of the form "v6 does X."** Blocked by provenance — and nothing in
   the redesign needs such a claim. The objective is layer attribution, not
   prompt evaluation, and the directive already scopes v10 out for the same
   reason.

**So the fix is a rename, not a re-score.** Freeze the corpus in
`PREREGISTRATION.json` as `corpus_2026-04-06_to_2026-05-10` — a frozen score
stream of unverified prompt vintage — and stop calling it the v6 corpus. Every
conclusion then reads as being about the system's conversion of *this* stream,
which is all the arms were ever going to support.

Supporting point: `recompute_trend_layer()` regenerates the derived signals from
stored raw fields **at load time**. The trend logic applied is today's code, not
2026-04's. "The v6 corpus" was never an accurate name for what actually runs.

**Re-scoring would be harmful, not merely expensive**, in this order:

1. The model that produced these rows retired 2026-06-15. Re-scoring changes
   prompt vintage **and** model in one move — §11.1's tuple rule violated by
   construction.
2. It orphans all four corpus-anchored benchmark records — `settled_control`
   ($179,944.91), `test1_zero_info_floor`, `sizing_channel_null`,
   `small_cap_materiality`. Each replays deterministically off these exact rows.
   A new corpus means the control the redesign compares against ceases to exist,
   and Step 6 loses its **Actual** line.
3. It spends real API money to answer a question the redesign does not ask.

**One provenance check is still worth running — for upside, not as a gate.**
Split the 362 rows at `2026-05-02 12:33:23-04` and compare the two populations
on structured-field presence and `rawOutput` shape. If the split is a batch
boundary, note it and move on. If it is a genuine vintage boundary, the corpus
contains a natural experiment — two prompt versions scoring overlapping tickers
— and Arm 0's machinery yields a v5-vs-v6 dollar comparison at $0. A reason to
look, not a gate to pass.

**What would refute this position.** An arm in the redesigned sequence that
genuinely requires prompt-vintage homogeneity to be valid — not merely to
generalize. If one exists, name it; that would convert this from a renaming into
a re-scoring decision, and it is the single thing that would change the answer.

---

## Output

Write `wrap-ups/methodology-challenge-round-2-out.md`:

1. **Adjudication table** — one row per item: `A1 … A4`, `CORPUS`; verdict; a
   one-line reason.
2. **Per-item reasoning**, with file and line citations where the repo settles
   it. Quote the code that refutes, where it refutes.
3. **Anything round 2 got factually wrong** — listed separately, not folded into
   the defenses. In particular: if the trend layer does not work the way A2
   describes, say so first and plainly, because A2, A3 and A4 all rest on it.
4. **The revised change list** — changes 1–19 from round 1 plus whatever of
   20–23 survives, renumbered, each tagged spec-edit (free) or new work. Mark
   any round-1 change whose justification A1–A4 alters.
5. **The corpus disposition**, in one sentence, in the form:

   > The corpus is **usable as is / usable with <condition> / requires
   > re-scoring**, because ____________.

6. **The one sentence**, filled in:

   > Of the four additions, ____ are conceded in full and ____ in part; the one
   > with the largest effect on what the redesigned test would conclude is
   > ____________.

**Then** write `prompts/value-attribution-and-headroom-v2.md` per the directive's
§4 sequence, incorporating the surviving change list. Do not run it without
Luis's go-ahead.
