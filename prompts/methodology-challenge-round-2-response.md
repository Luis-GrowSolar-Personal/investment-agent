# Round 2 — adjudication and authorization to write v2

**Not a run prompt.** No code executes; no API spend; no DB access. The only
files written are `wrap-ups/methodology-challenge-round-2-out.md` (if you want
the adjudication mirrored there) and
`prompts/value-attribution-and-headroom-v2.md`.
`run_id` **`methodology-challenge-round-2`**. Branch `sweep/db-corpus-baseline`.

**From:** the authoring session.
**To:** the reviewing session that wrote `prompts/methodology-challenge-round-2.md`.

---

## 1. Adjudication

| # | Verdict | Reason |
|---|---|---|
| A1 | **CONCEDE** | Both changes. The sign of the headline finding is one query away and has never been run. Arm 0b does not degenerate — see §2. |
| A2 | **CONCEDE** | Trend layer confirmed at `sweep_funding_modes.py:96–113`. This is a three-layer system and the deliverable assumed two. |
| A3 | **CONCEDE** | Injection point pinned at `per_call_rec`; the two-level sanity check is a free measurement of trend-layer override rate. |
| A4 | **CONCEDE** | The conviction channel is live and runs through the trend layer, not sizing. Round 1's concession was right on the citation, wrong on the channel. |
| CORPUS | **CONCEDE** | Usable as is; rename, do not re-score. No arm in the sequence requires vintage homogeneity for validity. |

**Four conceded in full, zero in part, zero defenses.** Round 1 produced five
full concessions and four partials; round 2 produces five full concessions.
Both rounds improved the design. Neither is a reason to slow the sequence down.

---

## 2. A1 — conceded, and the refutation I went looking for failed

**Change 20 (lift against both baselines) is conceded without reservation** and
is the most consequential item across both rounds. §3.1's direction mapping
makes "always-hold" mean "predict neutral on every call," so the always-hold
hit rate is the neutral share of scoreable events — already present in the rows
Test 2 scored. The arithmetic in A1 is sound: with bullish fixed at 166/359, any
bearish base rate near 20% puts always-hold in the low 30s and flips the lift
from −5.8pp to roughly +6.7pp. **Same rows, same predictions, opposite sign.**

**Change 21 (Arm 0b) — I attempted the refutation A1 invited and the code
refuted me.** My intended objection was that always-hold through the allocator
degenerates to a no-trade portfolio worth its starting cash, making the arm
uninformative rather than complementary. That is wrong:

```python
# analysis/sweep_funding_modes.py
199:  starter_fired = is_first_call and not had_position
201:  if starter_fired:
205:      intended += (starter_pct / 100.0) * portfolio_value_before
206:  v2_leg_applies = (not starter_fired) or (final_action not in ("Hold", None))
```

`starter_fired` depends only on `is_first_call and not had_position`. It does
**not** read `final_action`. So under always-hold every ticker still receives
its starter (`STARTER_PCT_SPECULATIVE` 5.0 / `STARTER_PCT_ESTABLISHED` 8.0) on
its first call, and is then never added to and never trimmed.

Arm 0b is therefore a **starter-only, buy-and-hold-forever portfolio over the
16-name universe** — well-defined, non-degenerate, and distinct from Test 1's
zero-information arm.

**It is also, on reflection, the single most decision-relevant number in the
design.** Test 5 established that universe composition dominates (Arm A at the
100th percentile of 25 draws) and `tier_return_attribution.py` put NVDA+AVGO+ORCL
at 81.4% of P&L. Arm 0b isolates exactly that: what the universe pays with no
analyst, no trend layer and no allocator discretion beyond entry. Everything the
three layers add together is `actual − Arm 0b`. That is the denominator the
whole apportionment has been missing.

Promote Arm 0b accordingly — it is not a sibling of Arm 0, it is the floor the
Step 6 table should be built on.

---

## 3. A2 — conceded; the code is exactly as described

`analysis/sweep_funding_modes.py:96–113` confirms the seven-field history, the
`compute_trend_verdict(history, tier=tier)` call, `apply_matrix(per_call_rec,
verdict)` producing `final_action`, and `compute_final_confidence(...)`
producing `final_confidence`. `CONFIDENCE_RANK` at line 47 and its use in
`rank_key()` at line 150 confirm that `final_confidence` orders funding priority
under `swap_funding`. Line 207 confirms the allocator's Add leg keys off
`final_action`, not the analyst's raw call.

So the allocator never sees `per_call_rec` directly. A two-bucket apportionment
was structurally unable to answer the objective, because the component with the
best recorded return-on-effort — the v2.1 trend layer, 44%→54% on 41 calls — was
folded invisibly into "analyst."

**Change 22 accepted and strengthened:** the Step 6 table names **three** layers.
Not "states which bucket it sits in" — names it. The objective is a
resource-allocation decision between things Luis could work on, and the prompt,
the trend matrix and the caps are three different things to work on.

I am not defending on the inertness ground, so no refutation measurement is
owed. But run it anyway, because it is free and it sizes the third bucket:
**the share of events where `apply_matrix` returns a `final_action` differing
from `per_call_rec`, and the share of funding decisions where `rank_key`'s
ordering would differ if `final_confidence` were held constant.** Those two
numbers are the trend layer's contribution surface.

---

## 4. A3 — conceded

Injection at `per_call_rec` is correct and must be pre-registered in 0d.
Injecting at `final_action` would measure a perfect analyst *and* a perfect
trend layer while wearing an analyst-ceiling label — precisely the mislabeling
C7a identified one layer down.

**Change 23 accepted in full**, including the two-level sanity check. The gap
between call-level 100% and final-action-level <100% is a direct measurement of
how often the trend layer overrides correct information, at no cost beyond an
arm already budgeted. It also resolves the C7d denominator ambiguity conceded in
round 1 — that check was underspecified because the injection point was unnamed.

The encoding question A3 raises is real: oracle labels are
bullish/bearish/neutral, `per_call_rec`'s value space is the analyst's action
vocabulary. Pre-register the mapping in 0d as a bound-loosening assumption
alongside the non-direction fields; it is not a reason to inject downstream.

---

## 5. A4 — conceded, and it corrects round 1's reasoning

Round 1 conceded C7b narrowly on the sizing-channel citation and left
"conviction and `thesisDelta`" as open terms. A2's evidence closes them against
the concession: `credibility_delta`, `stumble_type`, `thesis_health`,
`mitigation_track_record` and `fresh_money_allocation` all enter
`compute_trend_verdict()`, and `final_confidence` orders funding.

The conviction channel is live. It simply does not run through sizing — X=2.5pp
renders that inert, exactly as the sizing-channel test found — it runs through
the trend layer.

**Consequence for change 13:** the oracle's non-direction field synthesis is a
material bound-loosening term, not a formality. Whatever the oracle supplies for
those fields will move `final_action` and funding order. Pre-register it, name it
in the wrap-up, and state its expected direction on the bound.

---

## 6. Corpus — conceded

**The corpus is usable as is, with a rename and no re-scoring.**

The refutation condition was: name an arm that requires prompt-vintage
homogeneity to be **valid**, not merely to generalize. I cannot, and I looked.
Every arm — Arm 0, Arm 0b, both permutation schemes, B1–B4, leave-one-call-out,
the oracle — consumes the stored scores as a given signal stream and asks how
the three layers convert that stream into dollars. A heterogeneous stream makes
the conversion question no less well-posed.

The three supporting arguments all hold:

- Re-scoring changes prompt vintage **and** model together (the producing model
  retired 2026-06-15), violating §11.1's tuple rule by construction.
- It orphans `settled_control` ($179,944.91), `test1_zero_info_floor`,
  `sizing_channel_null` and `small_cap_materiality` — which would delete the
  **Actual** line the Step 6 table is built around. This argument alone is
  decisive.
- `recompute_trend_layer()` regenerates derived signals from stored raw fields
  at load time, so "the v6 corpus" was never an accurate name for what runs.

**Freeze it in `PREREGISTRATION.json` as `corpus_2026-04-06_to_2026-05-10`** — a
frozen score stream of unverified prompt vintage — and retire "v6 corpus"
everywhere in v2.

**One addition.** If the `2026-05-02 12:33:23-04` split turns out to be a genuine
vintage boundary rather than a batch boundary, that is not only the natural
experiment round 2 describes — it also means the permutation and ablation arms
run on a **mixed-vintage** stream. That does not invalidate them, but it belongs
in v2's limitations as a stated property of the corpus rather than a discovery
made later. Run the structured-field/`rawOutput` comparison for that reason as
well as for the upside.

---

## 7. What round 2 got wrong

Nothing material. A2, A3 and A4 rest on a reading of the trend layer that the
code confirms line for line.

The only correction runs the other way: **A1's own refutation condition for
change 21 does not hold**, for the reason in §2. Round 2 offered me an exit that
the code closed. Recorded here because A1 flagged it as the thing that would
change the answer, and it does — in favor of the change, and more strongly than
A1 argued for it.

---

## 8. Revised change list

Rounds 1 and 2 combined, renumbered. Round-1 numbering in brackets.

| # | Change | Source | Cost |
|---|---|---|---|
| 1 | **Arm 0b — always-hold (starter-only) through the real allocator.** The universe-only floor; Step 6 is built on it | A1 | New work, $0 |
| 2 | **Arm 0 — always-bullish through the real allocator** | [1] C2 | New work, $0 |
| 3 | **Stage 1 computes lift against BOTH baselines**, always-bullish and always-hold, with McNemar against each | A1, [4] C4 | Spec + trivial compute |
| 4 | Compute the **bearish ground-truth base rate**; correct the 09-13 handoff's "four times in five" | [3] C3 | Spec + trivial compute |
| 5 | **Ticker-block bootstrap** interval on every lift figure | [4] C4 | New work, $0 |
| 6 | **Step 6 names three layers** — analyst, trend, allocator — in the table | A2 | Spec edit |
| 7 | Measure the **trend layer's override rate** (`final_action` ≠ `per_call_rec`) and its funding-order effect | A2 | New work, $0 |
| 8 | **Oracle injects at `per_call_rec`**, pre-registered in 0d | A3 | Spec edit |
| 9 | **Two-level oracle sanity check** (call level = 100%; final-action level = the override measurement) | A3, [15] C7d | Spec edit |
| 10 | Pre-register the oracle's **non-direction field synthesis and label encoding** as material bound-loosening assumptions | A4, [13] C7b | Spec edit |
| 11 | Delete the motivating-tension framing; restate the question in dollars | [2] C1 | Spec edit |
| 12 | Two permutation schemes — within-ticker primary, cross-sectional second | [6] C5 | New work, $0 |
| 13 | Delete "preserve chronology"; require per-ticker event and distinct-arrangement counts | [7] C5 | Spec edit |
| 14 | Withdraw Step 2's 50th-percentile interpretation | [8] C5 | Spec edit |
| 15 | Read each ablation against the permutation null | [5] C4 | Spec edit |
| 16 | Drop Step 1's reconciliation requirement; label the 2×2 non-causal; add a benchmark-relative dollar axis | [9] C6 | Spec edit |
| 17 | **Leave-one-call-out** attribution; bearish subset if 359 runs is infeasible | [10] C6 | New work, $0 |
| 18 | Oracle reports **cap-binding frequency** | [11] C7a | Spec edit |
| 19 | Relabel as "Analyst headroom **under the current allocator and trend layer**" | [12] C7a, A2 | Spec edit |
| 20 | Specify the post-`2025-11-07` oracle fallback; report the tail's size | [14] C7c | Spec edit |
| 21 | Pre-register **oracle ≤ actual as a finding** | [16] C7 | Spec edit |
| 22 | **Bias sign on each ceiling line inside the Step 6 table**; Step 5 relabeled an in-sample maximum | [17] C8 | Spec edit |
| 23 | Step 0b states the stamped eval cache was sought and found absent | [18] C9 | Spec edit |
| 24 | Freeze the corpus as `corpus_2026-04-06_to_2026-05-10`; retire "v6 corpus" | CORPUS | Spec edit |
| 25 | Run the `2026-05-02` split comparison — for the natural experiment **and** to establish whether the stream is mixed-vintage | CORPUS | New work, $0 |
| 26 | Record **F1** (always-hold vs always-bullish) and **F2** (sector ETF vs SPY) in `PROMOTION_GATE.md` §10 | [19] F1/F2 | Spec edit |

**Justification altered by round 2:** #10 (was a formality, now material — A4),
#19 (now two layers deep, not one — A2), #9 (was ambiguous, now well-defined — A3).

**F1's disposition changes.** Round 1 filed it as a §10 footnote. It is now
change 3 and runs in Stage 1. F2's deferral stands — it needs TAN/SOXX history
absent from `price_cache.json` and bears on no dollar arm.

---

## 9. The objective — unchanged, and now better served

> **Who is contributing most to the portfolio's lift, and who needs the most
> work?**

Round 2 changes the shape of the answer in one important way: **it is a
three-way split, not two.** The table v2 must produce:

```
Arm 0b — universe only (starter-only buy-and-hold)     $ ______   ← the floor
Test 1 — zero-information analyst                      $120,800
Arm 0  — always-bullish                                $ ______
Actual — real analyst + real trend layer + allocator   $179,944.91

Contribution:  analyst  ____ | trend ____ | allocator ____ | interaction ____
Headroom:      analyst  ____ | trend ____ | allocator ____   [bias sign on each]
```

Everything the three layers add, together, is `actual − Arm 0b`. If that number
is small, the honest answer to Luis's question is "none of them — the universe
did it," and that is a legitimate and valuable outcome, not a failed run.

---

## 10. Authorization

Write **`prompts/value-attribution-and-headroom-v2.md`** now, incorporating all
26 changes, structured on the directive's §4 sequence as amended:

**Arm 0b → Arm 0 → Stage 1 (both baselines, base rate, McNemar, bootstrap) →
Stage 2 (contribution: permutations, ablations, leave-one-out, trend override
rate) → Stage 3 (headroom, bias declared) → Stage 4 (the three-layer table).**

Carry forward unchanged: the $0-API hard constraint, the 0d pre-registration
freeze with abort-on-mismatch, one identical locked corpus/window/control across
every arm, firewall discipline on the oracle's scratch data, the macOS/zsh
constraints, and the instruction not to repair known defects in passing.

**Do not run it without Luis's go-ahead.**

No round-3 challenge is needed before writing. If one surfaces during drafting,
raise it inside v2 as a stated open question rather than as another round.
