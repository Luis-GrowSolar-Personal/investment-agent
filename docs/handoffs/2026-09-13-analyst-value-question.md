# Handoff — 2026-09-13 — the analyst-value question

**Supersedes nothing.** Extends `docs/handoffs/2026-09-07-state-of-play.md`
with one finding that reframes the test plan. Read that document first.

**Branch:** `sweep/db-corpus-baseline`
**Next action:** run `prompts/value-attribution-and-headroom.md` ($0 API spend).

---

## 1. The finding

`wrap-ups/test2-look-ahead-hit-rate-by-year-out.md` contains a `baseline` and
`lift` column that were never read. Test 2 was framed as a look-ahead probe,
its pre-registered question was about the *shape* of the hit-rate series, the
shape came back non-monotonic, and the test was filed "inconclusive by design"
and closed. The lift column answers a different and more consequential
question.

Test 2's methodology is §3.1's exactly — it imports `FORWARD_DAYS`,
`DEAD_BAND`, `BENCHMARK` and `direction_from_score` from
`analysis/analyst_direct_scorer.py`. It is therefore **the promotion gate's
primary analyst metric, already computed**.

| year | n | hit rate | baseline | lift |
|---|---|---|---|---|
| 2021 | 45 | 55.6% | 51.1% | +4.4 |
| 2022 | 56 | 26.8% | 32.1% | −5.4 |
| 2023 | 60 | 38.3% | 41.7% | −3.3 |
| 2024 | 84 | 29.8% | 39.3% | −9.5 |
| 2025 | 114 | 50.0% | 58.8% | −8.8 |

n-weighted over 359 calls: 145 hits (40.4%) vs baseline 166 (46.2%) —
**aggregate lift ≈ −5.8pp**, negative in four of five years and most negative
in the two largest-n years.

Separately, the wrap-up records **bearish-outcome accuracy of 8.3%–24.0% in
every year, with no trend**. **Correction (`wrap-ups/value-attribution-v2-stage-b-out.md`,
Step B2, measured against the same 359-row scorer population — reproduces
this range exactly by year: 11.1/24.0/16.7/8.3/11.9% for 2021–2025):** this
is *recall* on true bearish outcomes — of the calls where the stock actually
underperformed its benchmark by more than 5% (n=151/359, a 42.1% bearish base
rate), v6 correctly flagged "trim/exit" only 13.9% of the time in aggregate.
That is **not** the same quantity as "when v6 says trim, it is wrong roughly
four times in five" — that phrasing describes *precision* on bearish
*predictions*, which is a different and better-looking number (47.7% of the
44 bearish predictions were right,
`analysis/data/value_attribution_v2/stage_b_manifest.json` →
`results.B2.scorer_population_aggregate_n359.precision_and_base_rate_by_predicted_class.bearish`).
The correct statement of the recall figure this section actually cites is:
**of the times a stock genuinely underperformed enough to count as a bearish
outcome, v6's call missed it 86.1% of the time — roughly six times in seven,
worse than the "four times in five" this section originally said, not
better.** The wrap-up itself flags this as "a separate finding about the
analyst's downside-calling skill overall"; it was set aside because it did
not bear on look-ahead.

**Two caveats, both unverified as of this handoff** and both gating Step 0 of
the new prompt: the exact definition of `baseline` in `analyst_direct_scorer.py`
(it ranges 32.1%→58.8% by year, a wide swing for a fixed strategy), and whether
those 359 rows were v6-scored. Neither has been checked. The −5.8pp figure is
provisional until they are.

---

## 2. Why this reframes the plan

Test 1 says the analyst is worth ~$59k over a zero-information arm ($120,800
floor, $179,944.91 control). Test 2 says its directional calls underperform
the baseline. Reconciling these is now the highest-value open question in the
project, and it is answerable for $0.

Supporting context already in hand:

- `analysis/tier_return_attribution.py`: NVDA alone = 40.1% of P&L;
  NVDA+AVGO+ORCL = 81.4%. Return is concentrated in names the *user* selected,
  not names the analyst picked.
- Test 5: Arm A sat at the **100th percentile of 25 random universe draws**.
  Universe selection was doing the heavy lifting.
- The sizing-channel test: the analyst's `recommended_size_pct` was worth
  **$0** — X=2.5pp makes the target value nearly inert.

Working hypothesis (constructed in conversation, **not measured**): the
allocator extracts value from the score *stream* through structure — caps,
Rule 3, profit-take, starter sizing — without requiring the directional calls
to be right. If true, improving directional accuracy has a low ceiling by
construction, and prompt iteration is optimizing a small term.

---

## 3. What the new prompt delivers

`prompts/value-attribution-and-headroom.md`, $0 API spend. Deliverable is a
six-line table separating **contribution** (what each layer earned) from
**headroom** (what it could still earn):

```
Floor (zero-info analyst)          $120,800     [Test 1]
Actual                             $179,944.91  [Test 1]
Analyst ceiling (oracle calls)     ?            [new, Step 4]
Allocator ceiling (best config)    ?            [Step 5, may be unavailable]
+ contribution, headroom and interaction terms
```

The design point: contribution and headroom can point to **different layers**.
A layer can be large and near its ceiling while a smaller one has room. That
divergence is the decision-relevant case and the reason the test is shaped
this way.

Steps: 0 verification+pre-registration (gated — a clean stop at Step 0 is a
successful run), 1 the hit/miss × made/lost-money 2×2 in dollars, 2 a ≥200-run
within-ticker permutation test, 3 four allocator ablations, 4 the oracle
ceiling, 5 the allocator ceiling, 6 the table.

---

## 4. Correction to the v10 record

The 2026-09-07 handoff and earlier statements in this session characterized
v10+auto1 as untested with an unmeasured accuracy position. **Both were wrong**,
and the correction matters:

- `analysis/auto_iterate/` (gitignored, local only) holds 8 run directories
  2026-07-05→07 proving extensive testing: best unstable 18→13, accuracy
  37.5–42.5%.
- `auto_iterate_prompt.py`'s header establishes that v6's recorded 60% was
  measured on a smaller, older ENPH+TTD set, and that **v6 itself scores 37.5%
  on the current full-history basis**. The 32.5% floor was that baseline minus
  a 5pp tolerance — not a 22pp concession. v10+auto1 therefore **matched or
  beat v6 on accuracy** while improving stability, on a held-out ticker (TTD,
  deliberately never used for tuning).
- v7/v8 and v9 have explicit, documented rejection reasons in
  `docs/EVALUATION_PROMPT.md`'s iteration log (v9: Gate A FAILED, 26/84 vs
  18/84, root-caused to an unscoreable sub-test and `max_tokens` exhaustion).
  **Only v10 lacks one** — "Gate status: not yet run."
- `git log --all --since=2026-07-05 --until=2026-07-10` returns **nothing**.
  The v9 gate scripts, recovery scripts, auto-iterate harness and the v7→v10
  changelog sat uncommitted for four weeks, then were swept into `87bcfaa`
  (2026-08-01) alongside `moves.js` account routing and 16 other files.

Disposition: v10+auto1 is **unadjudicated**, not rejected. If it is ever
gated, note that v10 and +auto1 are unrelated changes — v10 is two narrow
human-diagnosed fixes, +auto1 is a single machine-generated patch from one
ENPH disagreement. They should be gated separately, and it is unconfirmed
whether plain v10 is still recoverable (all `best_prompt.md` files in
`auto_iterate/` are post-auto1).

---

## 5. Open items added

- `PROMOTION_GATE.md` in the claude.ai Project is the 2026-09-02 version; the
  repo copy carries §8.1 (forced-migration protocol) and §11 (comparison
  protocol). **The project copy is stale** and should be synced before it is
  cited as the source of truth.
- The auto-iterate harness's objective function is itself a drift vector:
  unweighted stability count, no tier structure. The v6 re-run showed
  v10+auto1 bought large/mid zeros at the cost of a 14.34pp small/micro floor —
  a tradeoff invisible to the harness by construction. Worth a registry record.
- Test 6's null was measured under v10+auto1, where large/megacap floors were
  0.0. A null against a zero floor is close to vacuous. Re-running under v6
  (~$25) would establish whether it survives a real floor.
- No verified QQQ or SPY comparison for the backtest exists anywhere this
  session could find. Test 1's control was a zero-information arm, not an
  index. If a benchmark-beat claim is made, establish how it was computed.

---

## 6. Process note

Test 2's lift column sat unread for eight days in a wrap-up this project had
already filed as complete. The pre-registration worked exactly as designed —
it stopped the look-ahead question from being answered post hoc — but nothing
in the process asks whether a test produced findings *outside* its
pre-registered question. Worth considering a standing step: when closing a
test, list what it measured that its own question did not consume.
