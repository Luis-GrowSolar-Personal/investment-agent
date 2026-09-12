# State of Play — 2026-09-07

**Supersedes** `docs/handoffs/2026-09-06-state-of-play.md` (which superseded
`2026-09-05-state-of-play.md` on §7-§8 only). **§§0-6 of the 09-05 document
still stand and are not repeated here** — the settled allocator
configuration, the ruler discovery, Test 1, the five resolved questions,
the corpus archive. Read 09-05 §0 (terms, especially **ruler**) first.

**Branch:** `sweep/db-corpus-baseline`
**Read first on return:** §1 (what changed), §2 (test plan), §7 (Test 5 —
the result is the universe), §5 (requote list — eight figures/claims
corrected across the 09-07 sessions).

---

## 1. Where things stand in one paragraph

**The six-test validation plan is complete.** Test 4
delivered the noise floor `PROMOTION_GATE.md` §6 has always required, and
it is not one number: large and mid are perfectly stable (0.0pp),
megacap 3.77pp, small/micro **14.34pp**. That split leaves the existing
`sonnet-4-6` HOLD verdict genuinely ambiguous — the -7.44pp regression
clearly exceeds the aggregate floor but sits inside the tier-matched floor
for the small-cap names the gate actually scored. Three $0 follow-on runs
then established that **none of the measured instability costs money**:
the sizing channel is inert (caps and the X-throttle absorb it entirely),
and small-cap categorical instability costs $533 (0.30%) — 31x cheaper
than the same volume of noise elsewhere. Test 6 found **no
instruction-removable look-ahead** on its sample. Return attribution
revealed extreme concentration: NVDA alone is 40.1% of the gain, three
semis names are 81.4%, and the small/micro cohort is a **net -8.1%
drag**. **Test 5 then showed why: the result is the universe.** Swapping
the established eight for the rule-based top-8 by 2020 market cap drops
final value 33.8% to $119,135 — within $50 of QQQ — and across 25 random
baskets a single indicator, NVDA in or out, explains 94% of the variance
(+$33k). The universe was hand-built on 2026-05-23 with outcomes known,
so the published figure is mostly a property of that choice, not of the
analyst or allocator. The run also found the tier classifier is not
point-in-time (NVDA tiered on 2026 fundamentals) — a second look-ahead
channel, in the allocator's inputs. Two EC-ingestion workstreams are
running in a parallel session.

## 2. Test plan — final status

| # | Test | Status |
|---|---|---|
| 1 | Analyst-quality sensitivity | **COMPLETE** — 09-05 §4 |
| 2 | Hit rate by year | **COMPLETE** — inconclusive, low priority |
| 3 | Transcript ingestion fidelity | **COMPLETE** — corpus clean |
| 4 | Analyst noise floor | **COMPLETE** — §3 below |
| 5 | Universe substitution | **COMPLETE** — §7 below |
| 6 | Look-ahead prohibition probe | **COMPLETE** — §6 below |

Plus three unplanned $0 follow-on runs Test 4 spawned (§4), and a return
attribution (§8).

## 3. Test 4 — the analyst noise floor

`wrap-ups/test4-analyst-noise-floor-out.md`. 50 transcripts × 5 identical
re-runs = 250 calls, ~4.8M tokens, ~$23. Prompt **v10+auto1** (not v6),
model `claude-sonnet-4-6` (bare alias — reproducibility risk stands).

**There is no single noise floor.** Aggregate 2.65pp std, but by tier:

| tier | n | hit-rate noise floor (std) |
|---|---|---|
| large | 13 | **0.0pp** |
| mid | 12 | **0.0pp** |
| megacap | 13 | 3.77pp |
| small/micro | 12 | **14.34pp** |

**The `sonnet-4-6` HOLD verdict is now ambiguous, and this run does not
resolve it.** Against the aggregate floor the -7.44pp regression is ~2.8σ
— real. Against the **tier-matched** floor for small/micro names — which
is what `gate_ledger.json` entry 1's seven-ticker scope is overwhelmingly
composed of — it is ~0.5σ, i.e. indistinguishable from noise. Both
readings are on record; neither is adopted. Resolving it needs the paired
champion-vs-challenger re-scoring that Test 4's scope explicitly deferred.

**Other findings:** `recommendation` flips on 22% of transcripts across
identical runs (small/micro 67%, megacap 15%, mid 8%, large 0%), three
of them 3-way splits including one megacap (MSFT). Sizing fields are
barely reproducible anywhere — `freshMoneyAllocation` 98%,
`recommendedSize` 96% unstable across all tiers. Field-level:
`mitigationCapabilityTrackRecord` genuinely noisy (44%, and 83% in
small/micro); `blindSpotsTriggered` never varied once in 250 calls,
refuting an earlier n=7 flag.

**Test 6 was NOT cleanly unblocked by this** — it had to pick a
tier-appropriate floor rather than one scalar. See §6.

## 4. Three $0 follow-on runs — the instability costs nothing

### 4.1 Sizing channel is inert
`wrap-ups/sizing-channel-sensitivity-out.md`. Test 1 never perturbed
`recommended_size`; Test 4 found it 96% unstable; 09-05 §5.2 says the
analyst's entire contribution *is* sizing. That gap is now closed:
**at the measured noise magnitude the sizing channel costs $0** — every
cell tied the $179,944.91 control to the cent, including deleting the
field entirely and always taking the cap.

**Mechanism, stronger than expected:** at X=2.5pp/session a position
almost never converges close enough to *any* target within a quarter for
the target's value to matter. `recommendedSize` is not merely
noisy-but-absorbed — **its numeric value is very nearly inert at this X
setting.** Real sensitivity exists (forcing every Add to `size=5.0` costs
$38,913) but only where the target falls *below* an accumulated position,
which measured noise never reaches from above.

Latent defect recorded, not patched: `if recommended_size_pct else
cap_pct` is a truthiness test, so **`0.0` and `None` both fall through to
the full cap** — a model emitting `0` would produce a maximum-size
position. Confirmed not live (0 nulls, 0 zeros in 137 Add events).

### 4.2 Small-cap instability costs $533
`wrap-ups/small-cap-instability-materiality-out.md`. The measured
instability pattern costs **$533.29 (0.30%)**. At matched corruption
volume (51 vs 52 realized corrupted events), evenly-spread noise costs
**$16,682 (9.27%)** — so **small-cap-concentrated noise is 31.3x cheaper
than the same quantity of noise elsewhere**, not merely less abundant.
Mechanism: small/micro is 100% Type-A-speculative (15% cap, Rule 3
no-average-down), and carries less capital.

**Both ceiling cells IMPROVE the portfolio**: fully randomizing every
small-cap verdict gains $679; forcing them all to Hold gains $5,076
(2.82%), deterministically. **Read with care** — the Hold arm never
trims, exits, or adds, and small caps broadly fell in this window, so
"do nothing beats acting" in a falling cohort is close to tautological.
It is not established that the verdicts carry no information.

**Verdict: the small/micro instability finding is economically inert on
this configuration.** No rubric work, prompt variant, or
waiting-for-companies-to-mature is justified by it. The ~$6 paired rubric
A/B that would have come next is **not** warranted.

A tested hypothesis that failed: instability does **not** track history
depth (38%/58%/40% at 0-2/3-7/8+ priors) but does track tier even
controlling for it (small/micro 78% vs large 22% at 5+ priors), and every
tier has a median of 9 prior transcripts. The "rubric has no answer for a
company with no prior transcript" explanation is largely dead.

### 4.3 Test 5 — now run
`prompts/test5-universe-substitution.md`, $0. Arm B corrected during
design to the real top-8 by year-end-2020 market cap: **AAPL, MSFT, AMZN,
GOOGL, META, TSLA, V, JNJ** — a **four**-name swap, not the three the
09-03 spec described (see §5 row 1). Results and reading in **§7**.

## 5. Requote list — eight figures and claims corrected

| # | Was | Now |
|---|---|---|
| 1 | 09-03 §7: Test 5's Arm B overlaps Arm A in five names, three-name swap, NVDA stays | **False.** NVDA ranked **15th** by year-end-2020 market cap, not top 8. Real Arm B is a **four**-name swap (AMD/AVGO/NVDA/ORCL out; AMZN/META/V/JNJ in), BRK.B excluded for having no earnings call, consistent with `audit_top20_2021.py`'s own `EXPECTED` list |
| 2 | 09-05 §5.2: "The August 2024 bankruptcy is outside the window" (re SPWR) | **Conflates two companies.** The SPWR in this corpus is the former **CSLR (Complete Solaria)**, which bought SunPower assets and took the ticker. The company that went bankrupt is the old ~20-year-old SunPower. Any reasoning treating them as one is wrong |
| 3 | Test 4 wrap-up §3: small/micro recommendation-flip rate **7/12 (58%)** | **8/12 (66.67%)** — independently re-counted twice; the missed transcript is id **355 (QS)**, `Trim, Hold, Trim, Hold, Hold` |
| 4 | Test 4 wrap-up §16: "roughly 35-45 minutes of actual API time" | **Wrong** — inferred, not measured, as its own text admits. Checkpoint timestamps show **~6-7 min/transcript, ~5-6 hours** for 250 serial calls |
| 5 | Test 6 wrap-up §6: MDE derived by dividing a binomial CI by √5 | **Not defensible.** The 5 runs re-score the *same* transcripts — averaging reduces scoring noise, not sampling uncertainty about which transcripts were drawn. Separately, an unpaired binomial is too conservative for what is a **paired** design; the natural test is on discordant pairs (McNemar). Does not change any conclusion — everything is null either way — but **do not reuse this recipe** |
| 6 | This session's claim (mine): the small-cap weight decline from ~5% to ~0.8% is pure passive decay | **Overstated.** Attribution shows **-$4,820 realized** losses in small/micro — real selling happened. Passive decay (QS -76%, EOSE -88%, plus an 80% denominator increase) still explains the bulk of the weight decline, but not all of it |
| 7 | Test 5 prompt Step 1: "uncorrupted (q=0.0) … Expected: `final_value` = $120,800" | **Wrong cell.** $120,800 is Test 1's `zero_info` cell (every verdict forced to Hold). Uncorrupted q=0.0 is **$179,944.91 / 20.85%**. Driver caught it; the two cells are deliberately different and must not be conflated again |
| 8 | 09-03 §5.1: "SPWR — never held, in any draw, at any point … if it was a real decline, it is the most encouraging single fact in this table" | **Coverage artifact.** SPWR has exactly **one** in-window event under `load_call_events()`'s cutoff, so it can never carry an end-of-window position. Not a rejection by the analyst. (And per row 2 it is not the SunPower that went bankrupt) |

Also recorded: a prediction of mine that FSLR would be a top-two
contributor was **wrong** — +239% on price, only **4.5%** of the gain.
Price appreciation is not contribution; position size and entry timing
are (§8).

## 6. Test 6 — look-ahead prohibition: null

`wrap-ups/test6-look-ahead-prohibition-out.md`. 275 calls (250 treatment +
25 control replication), ~5.3M tokens, ~$25-26. Paired against Test 4's
exact 50-transcript sample, reusing Test 4's runs as the control arm —
which is what makes the per-tier floors transferable at all.

Control replication **passed** (the bare model alias had not drifted), so
the paired design is valid.

| tier | delta (treatment − control) | floor | moves? |
|---|---|---|---|
| large | **0.00pp** | 0.0pp | no — exact null |
| megacap | -1.54pp | 3.77pp | no |
| mid | -6.67pp | 0.0pp observed / ~12.65pp MDE | no |
| small/micro | +8.33pp | 14.34pp (not a detector) | inconclusive |

**No tier clears its own detection bound.** The strongest evidence is not
the MDE arithmetic (see §5 row 5) but the raw counts: **3 of 50
transcripts changed modal recommendation**, and zero of those were in
large or megacap — the two high-recall tiers where look-ahead should live.

**Two of the three changes are artifacts, not findings.** Both ENVX
transcripts (ids 172, 175) that flipped Hold→Add under the prohibition
were **already** in Test 4's small/micro flip list, and id 175 was one of
Test 4's three **3-way splits** (`Add, Add, Hold, Hold, Trim`). A modal
change on a transcript whose mode is barely defined is noise. The real
count is closer to **one genuine change** (FSLR id 292, Add→Hold) plus
two coin flips. Similarly, mid's within-arm spread rising 0.00→3.33pp is
plausibly that same single FSLR transcript at n=12.

**The correct summary, narrower than "no look-ahead":**

> Adding an explicit hindsight prohibition produces no measurable change
> in scoring on this 50-transcript sample under `sonnet-4-6` / v10+auto1.
> In the two high-recall tiers nothing moved at all. **That rules out
> *instruction-removable* look-ahead on this sample.** It does not
> establish the analyst is free of recall-driven bias — the analyst has no
> tools and cannot look up a price, so the only possible leak is recall,
> and a model cannot be instructed not to know. A null is consistent both
> with "no look-ahead" and with "look-ahead an instruction cannot remove."

**Coverage is thin where it matters most: NVDA has n=1** in this sample
(identical Adds across all 10 runs, both arms), and the three names
carrying 81% of returns are barely represented. Note also this is a
finding about the **analyst** (Layer 2). The allocator never sees a
transcript and structurally cannot carry transcript look-ahead
(`DESIGN_PRINCIPLES.md` §1).

This is now the third weak-to-moderate line pointing the same way,
alongside Test 2's non-declining hit-rate series and 09-05's observation
that the *newer* model with more knowledge of how 2022-24 resolved scored
*worse*. Three agreeing signals beat one; none is proof.

## 7. Test 5 — universe substitution: the result is the universe

`wrap-ups/test5-universe-substitution-out.md`. $0, 27 in-memory cells
(Arm A, Arm B, 25 resampling draws), driver `6f3c749`, run state
`analysis/data/run_state/test5-universe-substitution/`. Arm A reproduced
the $179,944.91 / 20.85% control **to the cent** before Arm B was trusted.
Settled configuration throughout; speculative eight identical in both arms.

### 7.1 The two arms

| | Arm A (real) | Arm B (top-8 by YE-2020 cap) | SPY | QQQ |
|---|---|---|---|---|
| established | AAPL AMD AVGO GOOGL MSFT NVDA ORCL TSLA | AAPL MSFT AMZN GOOGL META TSLA V JNJ | | |
| `final_value` | **$179,945** | **$119,135** | $113,980 | $119,178 |
| `max_drawdown` | 20.85% | 19.93% | 21.99% | 33.75% |
| top 3 at window end | NVDA 24.0, AVGO 20.3, ORCL 16.2 = **60.5%** | TTD 17.4, V 17.2, FSLR 12.2 = 46.8% | | |

Swapping four established names costs **−$60,810 (−33.8%)** and changes
drawdown by 0.9pp. Arm B lands within $50 of QQQ on return.

### 7.2 The resampling distribution is two clusters, not a curve

25 random 8-name draws from the 20-name top-20-2021 pool (seed 20260906):
mean $135,122, sd $17,509, range $107k–$158k; Arm A above all 25. But the
spread is not smooth — **one name decides which cluster a draw falls in:**

| draws | n | mean final | sd | range |
|---|---|---|---|---|
| containing NVDA | 14 | **$149,669** | $5,241 | $142k–$158k |
| without NVDA | 11 | **$116,608** | $7,574 | $107k–$128k |

Two-indicator fit over the 25 draws (computed this session from
`cells.jsonl`, not in the wrap-up):

```
final_value ≈ $120,664 + $33,467·[NVDA in] − $8,923·[TSLA in]     R² = 0.94
max_dd      ≈  13.5%   +  0.8pp·[NVDA in] +  5.3pp·[TSLA in]     R² = 0.93
```

No other name in the pool moves the mean by more than the within-cluster
noise. The drawdown split is clean: **every TSLA draw finished ≥ 17.9%
drawdown, every non-TSLA draw ≤ 14.9%.** NVDA sets the return; TSLA sets
the drawdown. Both arms hold TSLA, which is why their drawdowns match.

The $33,467 NVDA coefficient and §8's independently computed **$32,065
NVDA attribution** are the same number from two unrelated methods. The
remaining ~$30k between Arm A and the best NVDA draw ($158k) is AVGO and
ORCL, exactly as §8's attribution says.

### 7.3 Reading — who did the selecting

The test asked "selection or exposure?" and the answer is selection — but
**the selecting was not done by the analyst.** Under `new_calls_only` at
X=2.5pp the analyst weights, it does not select (09-03 §5.1: 15 of 16
names held, none rejected). The choice that produced the $60k gap was
made when AMD/AVGO/ORCL/NVDA were put into `ESTABLISHED` on **2026-05-23**
(`e35f978`), with 2022–24 outcomes known and no recorded rationale
(09-03 §6.1, still open). **The 100th-percentile result measures the
universe-builder, not the analyst or the allocator.**

That does not make the universe illegitimate — semiconductors are Tier 1
in `DOMAIN.md`, so a semi-heavy eight is principled. What is *not*
established is whether choosing NVDA/AVGO/ORCL/AMD **within the domain**,
over INTC/QCOM/TXN/CSCO/IBM, was a rule or hindsight. The pool the prompt
fixed (top-20 S&P) cannot answer that — it contains none of those names
except NVDA. The wrap-up's own caveat says this; stated plainly:
**the published $184,819 is mostly a property of the universe, and the
universe was built after the fact.**

**The fairest hindsight-free statement of what the system does** is Arm
B: a universe chosen by a mechanical rule from 2020 data, same allocator,
same analyst → **QQQ's return at ~60% of QQQ's drawdown, and a modest edge
over SPY on both.** Real, but a much smaller claim than the published
one, and the one to put in front of anyone asking whether this works.

### 7.4 Two things this shakes

1. **The settled configuration.** The X=2.5pp interior optimum, K=30, and
   the funding-mode result were all swept on a universe containing one
   ~10x name. On that universe the rate limit and the 25% profit-take are
   what bind; on Arm B they may not, and the optimum may sit elsewhere.
   Until the X sweep is repeated on Arm B it is not known whether the
   configuration is a property of the allocator or of NVDA.
2. **The drawdown advantage.** 17.32% vs SPY 25.36% was read as better
   decisions. §7.2 says drawdown is set by TSLA membership and by
   deployment mechanics (73% cash through 2022, 09-03 §5.1) and selection
   barely moves it — Arm A and Arm B are 0.9pp apart. This corroborates
   the start-date-artifact reading over the skill reading.

### 7.5 Two flags from the run

1. **The prompt's Step 1 reference figure was wrong.** It told the driver
   to expect $120,800 for "uncorrupted q=0.0"; that is Test 1's
   *zero-information* cell (every verdict forced to Hold). The uncorrupted
   cell is $179,944.91. The driver caught it and used the right target.
   §5 row 7.
2. **The tier classifier is not point-in-time.** `build_tier_function`
   reads one snapshot of `fundamentals_cache.json` (current market cap,
   trailing P/E, trailing vol) and applies that single tier to every
   session of a 2022–24 backtest. Visible symptom: **AMD classifies as
   speculative** (P/E 133, vol 62.8%) despite being in the "established
   eight" everywhere in the docs, so every sweep on this branch has run
   AMD at the speculative starter, cap and Rule 3. The invisible symptom
   is worse: **NVDA classifies as established on its 2026 fundamentals.**
   In January 2022 NVDA's trailing P/E was well above 50 and its trailing
   vol near the 50% threshold, so a point-in-time classifier would
   plausibly have called it speculative for at least the first year — a
   5% starter, 15% cap, and Rule 3 blocking adds through the 52% 2022
   drawdown that §9 identifies as exactly where NVDA's contribution was
   built. Since NVDA is 40% of the gain, the tier assigned to it is not a
   detail. This is a **second look-ahead channel, in the allocator's
   inputs rather than the analyst**, separate from §6 and outside Test
   6's reach. Record it in `DESIGN_PRINCIPLES.md` §4 alongside the
   analyst-recall limitation.

Also observed: SPWR has only **one** in-window event under
`load_call_events()`'s cutoff, in both arms. 09-03 §5.1's "SPWR never
held — the most encouraging single fact" is a coverage artifact, not a
rejection. §5 row 8.

### 7.6 Follow-ups, all $0 except the last

In order of information per cell: **(a)** the zero-information cell on
Arm B's universe — Arm B with real scores ($119,135) sits *below* Test
1's zero-info floor on ALL16 ($120,800), which proves nothing across
universes but is uncomfortable enough to check with one cell; **(b)** Arm
A minus NVDA as a *diagnostic* (the prompt correctly forbade it as a
test) to size the NVDA contribution directly rather than by regression;
**(c)** the X sweep on Arm B (§7.4 item 1); **(d)** a point-in-time tier
for NVDA and AMD at the window's start, to see whether the classifier's
verdict flips (§7.5 item 2). **Costed:** resample from a **domain-
constrained** pool — top-N by 2021 market cap within `DOMAIN.md`'s circle
of competence, a rule that holds the semi losers alongside the winners.
That is the test that actually settles "were these names lucky"; scope
its transcript/scoring spend only after (a)–(d) confirm the picture.

## 8. Return attribution — extreme concentration

`analysis/tier_return_attribution.py` (new, this session, $0). Control
reproduced $179,944.91 exactly; reconciliation residual -$44.95 (0.06%).

| tier | contribution | % of gain |
|---|---|---|
| megacap | $37,023 | 46.3% |
| large | $36,832 | 46.1% |
| mid | $12,620 | 15.8% |
| **small/micro** | **-$6,485** | **-8.1%** |

**Megacap vs large is a dead heat** ($191 apart). The real structure is
single-name: **NVDA $32,065 = 40.1%**, AVGO 27.0%, ORCL 14.2% — three
semis names are **81.4%** of the entire gain. Megacap's share is 87%
NVDA; strip NVDA and megacap contributes less than mid. TSLA *lost*
$2,004. Portfolio ends fully deployed, $0 cash.

## 9. The allocator design question this raised (deferred, not dropped)

Diagnostic case NVDA vs FSLR: NVDA +416% on price → ~26% of portfolio;
FSLR +239% → ~2.6%. The gap is **classification**, not performance —
NVDA is Type B / established (8% starter, 50% cap, Rule 3 exempt), FSLR
is Type A / speculative (5% starter, 15% cap, Rule 3 applies). FSLR's
*held* shares gained only +68% against the stock's +239%; ~75% of the
position was sold off.

**Correction to the obvious intuition:** the 15% cap does **not** block
appreciation — there is no cap-enforcement trim. Only the **tier-agnostic
25% profit-take** ceilings a grown position. A 5% starter that 10x's
becomes ~25% of the book without ever graduating to established. The real
constraints on a winning spec are **Rule 3** (blocks adding exactly
during the drawdown that precedes most 10x runs — NVDA, being
established, was exempt and added through its 52% 2022 drawdown),
**swap-funding displacement**, and the 1.6x smaller starter.

**Never swept:** starter percentage, tier caps, Rule 3's applicability.
Swept to date: X, cadence/K, funding mode, scope, execution order,
veto_p, phase. **Deferred by decision** to a separate allocator-improvement
prioritization; full write-up handed off in that session.

## 10. Parallel workstreams (separate sessions)

- **`av-fidelity-benchmark-2-stratified`**: 25/200 fetched, 175 remaining,
  **zero truncations so far** but the sample is still concentrated in
  megacap/large. Reverted to single-key (~20/day, ~9 more invocations)
  after the 10-key rotation failed. **Open decision: whether this daily
  ritual is still worth it** given the vendor evaluation below.
- **`ec-fidelity-benchmark-1`**: 207 targets, all steps done,
  **wrap-up pending** — results not reviewed here.
- **`test7-ec-score-fidelity`**: early (steps 0-1 done).
- Handoff written: `docs/handoffs/2026-09-06-ec-ingestion-handoff.md` —
  self-contained context for the ingestion-vendor question, including the
  three bugs the AV methodology already earned and the SPWR naming trap.

## 11. Open items — 09-05 §8 and 09-06 §8 stand; add:

- **Test 5's follow-ups (§7.6).** Four $0 cells — zero-info on Arm B, Arm
  A minus NVDA, X sweep on Arm B, point-in-time tier for NVDA/AMD — then
  a decision on the costed domain-constrained resampling pool.
- **The published $184,819 should not be quoted without Arm B beside it**
  ($119,135, §7.1) until the domain-constrained resampling settles how
  much of it is universe hindsight.
- **09-03 §6.1's universe-provenance question is now load-bearing**, not
  a curiosity: the four names added on 2026-05-23 are 81% of the gain.
- **The `sonnet-4-6` gate ambiguity (§3) was the most consequential
  unresolved item in this document until Test 5; it is now second to the
  universe question (§7.3).** It needs the paired
  champion-vs-challenger re-scoring, and until then the live model choice
  rests on evidence that may or may not clear a properly measured bar.
- **Five OS low-memory kills across two runs** (Test 4 twice, Test 6 three
  times). Both survived via checkpointing, but Test 6's driver did not
  implement the per-call persistence or the 5-way concurrency its prompt
  specified — costing ~5 hours of wall clock it did not need to spend.
  Worth checking why prompt instructions were dropped.
- **`fundamentals_cache.json` is 118 days stale — and, more seriously,
  the tier classifier is not point-in-time at all (§7.5 item 2).** One
  snapshot tiers every session of the backtest. AMD runs as speculative
  in every sweep on this branch; NVDA runs as established on 2026
  fundamentals. Two separate fixes: refresh the cache (live app), and
  give the backtest a point-in-time tier (or at least measure what a
  2022-01 tier would have done to NVDA). Record in `DESIGN_PRINCIPLES.md`
  §4.
- **Tests 4 and 6 measured v10+auto1, not the deployed v6.** The drivers
  read `docs/EVALUATION_PROMPT.md` from the working tree, and on
  `sweep/db-corpus-baseline` that file is still v10+auto1 — the 09-03
  rollback (`c514ae1`, sha `357b6b0b…`) landed on `dev` only. So the noise
  floor the `sonnet-4-6` gate needs was measured on the wrong prompt (and
  instability is strongly prompt-dependent: v9 69.0% vs v6 21.4%). **Re-run
  Test 4 on v6** — same 50-transcript sample, same 5 re-runs, paired
  against the existing v10+auto1 output, which also runs v10's never-run
  stability gate for free. Test 6 deferred until that returns. Before
  either: bring the v6 file onto the branch, and make the drivers hash
  the prompt they load, record it in the manifest, and refuse to run on a
  mismatch with `versions.js`. Being handled in a separate session.
- **The MDE recipe in Test 6 §6 must be fixed before reuse** (§5 row 5).
