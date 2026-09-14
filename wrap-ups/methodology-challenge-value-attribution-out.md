# Adjudication — methodology challenge, `value-attribution-and-headroom`

**Answered by:** the session that authored `prompts/value-attribution-and-headroom.md`
and `docs/handoffs/2026-09-13-analyst-value-question.md`.
**Scope honored:** methodology only. The provenance question (153/362
out-of-window, the `22d2c71` dating convention, whether Step 0 was right to
stop) is not argued here.

---

## 1. Adjudication table

| # | Verdict | One-line reason |
|---|---|---|
| C1 | **CONCEDE** | Baseline is always-**bullish** (scorer line 18, 207), not always-hold. The motivating tension does not exist. |
| C2 | **CONCEDE** | Always-bullish through the real allocator is the cheapest decisive arm and is missing. No structural reason it can't run. |
| C3 | **CONCEDE** | "Wrong four times in five" implies a 50% anchor. The correct anchor is the bearish base rate, uncomputed. |
| C4 | **CONCEDE** | No interval anywhere outside Step 2. Overlapping 182-day windows and a shared SPY factor put effective n well below 359. |
| C5 | **PARTIAL** | Compound null conceded, "preserve chronology" conceded, arrangement-count conceded. Within-ticker scheme defended as necessary but insufficient. |
| C6 | **PARTIAL** | Additivity/non-additivity contradiction conceded, as are all three convention gaps. The 2×2 retains descriptive value only if labeled non-causal. |
| C7 | **PARTIAL** | a, c, d and the oracle-below-actual point conceded in full. b is partly defensible on the sizing-channel citation the challenge itself offers. |
| C8 | **CONCEDE** | Opposite-signed biases on the two ceilings, both tilting toward the prior stated in 09-13 §2. The most consequential item here. |
| C9 | **PARTIAL** | Design order conceded — the stamped artifact should have been sought first. In practice the artifact appears unrecoverable, making it also a documentation gap. |

**Zero full defenses.** That is the correct outcome; the challenge is largely right.

---

## 2. Per-challenge reasoning

### C1 — CONCEDE

Settled by the repo. `analysis/analyst_direct_scorer.py`:

```
line 6:   and lift over an always-bullish baseline, broken out by call type.
line 18:    - Always-bullish baseline: predicts "bullish" on every call
line 207:   always_bullish_hit = (ground_truth == "bullish")
```

`always_bullish_hit` never reads `predicted`. The baseline is a fixed strategy —
permanent long conviction — and on a 16-name analyst-selected universe over
2021–2025 that is a strong strategy, not an absence of information. The 32.1%→58.8%
year swing is that strategy's base rate moving with the tape.

So "+$59k versus zero-information" and "−5.8pp versus permanent bullishness" are
jointly true with nothing to reconcile. The prompt's opening framing — *"Both
cannot be casually true"* — is wrong, and so is the stronger claim carried into
conversation that v6 is "worse than not having an analyst." Always-bullish is not
"not having an analyst"; it is a specific, aggressive, and in this window
well-performing alternative.

The reviewing session's refutation condition (show zero-info and always-bullish
behave equivalently through the allocator) fails on its face: zero-info deploys
on noise, always-bullish deploys maximally into every name on every call. Nothing
to salvage.

### C2 — CONCEDE

No structural obstacle exists. Always-bullish = Add on every call. Under
`swap_funding` / `pooled` / K=30 / X=2.5pp this is well-defined: the arm saturates
against `TYPE_A_SPECULATIVE_CAP_PCT` 15.0 / `TYPE_A_ESTABLISHED_CAP_PCT` 35.0 /
`TYPE_B_CAP_PCT` 50.0 and becomes approximately a cap-weighted always-long
portfolio. Saturation is not degeneracy — it is the arm's answer.

The challenge's framing of the two outcomes is correct and is the strongest
argument in the document. In particular the second branch — if always-bullish
does *not* beat $179,944.91, then §3.1 is grading something the system does not
monetize — is a finding about the promotion gate itself, larger than anything
Steps 1–6 were designed to produce, and unreachable by the prompt as written.

This arm should run first, before Steps 1–6.

### C3 — CONCEDE

`docs/handoffs/2026-09-13-analyst-value-question.md` §1 states "When v6 says
'trim,' it is wrong roughly four times in five." That is a precision figure read
against an unstated 50% anchor. With three classes, a bull-skewed tape and a ±5%
dead band, the informative anchor is the unconditional frequency of bearish
ground truth among scoreable events. It is computable from the rows Test 2
already scored and was not computed.

If that base rate is near 20%, bearish calls are at chance; if it is well above
24%, the original phrasing stands. The handoff should not carry the stronger
claim until the number exists. Flagged for correction.

### C4 — CONCEDE

No interval is attached to −5.8pp anywhere in Step 0, Step 1, the prompt or the
handoff. The dependence structure is exactly as described: 182-day forward
windows overlap heavily within ticker, all 16 names are graded against a single
SPY factor, and P&L is concentrated (NVDA 40.1%, NVDA+AVGO+ORCL 81.4% per
`analysis/tier_return_attribution.py`). Effective sample size is far below 359.

Both proposed instruments are correct and free: McNemar against always-bullish on
the paired per-call outcomes, and a ticker-block bootstrap for the interval.

The Step 3 half of this challenge is equally correct and I had not seen it. Four
ablation arms reported as single-path point deltas have no null. The proposed fix
— read each ablation against the Step 2 permutation seeds — is the right one and
costs nothing beyond compute already budgeted.

### C5 — PARTIAL

**Conceded:** the null is compound. Under `pooled` funding the allocator is
path-dependent and compounding, so a within-ticker permutation across 2021–2025
moves capital deployment across regimes and price levels. A mid-distribution
result is consistent with "no timing skill" and with "the real arrangement
deployed earlier." The pre-registered interpretation in Step 2 does not survive
that and must be withdrawn.

**Conceded:** "Preserve chronology within each shuffle" is self-contradictory.
Nothing stronger was intended — the phrase should be deleted, not clarified.

**Conceded:** per-ticker arrangement counts must be reported. A 4-event ticker
admits 24 arrangements; 200 draws quantize the percentile.

**Defended:** the within-ticker scheme remains the correct primary. Test 5's
finding that Arm A sat at the 100th percentile of 25 random universe draws is the
reason: universe selection dominates, so any scheme that perturbs the universe
measures the wrong thing. The challenge's cross-sectional scheme (permute labels
across tickers within an event-date cohort) is a genuine improvement as a
*second* scheme, and the bracketing argument is right. Both, not either.

### C6 — PARTIAL

**Conceded, and it is a real contradiction.** Step 1 demands reconciliation to a
tolerance while citing `tier_return_attribution.py`'s −$44.95 residual as the
standard; Step 6 states no exact decomposition exists. Both cannot hold. The
`tier_return_attribution.py` precedent does not transfer: partitioning realized
P&L *by ticker* is genuinely additive because every dollar belongs to exactly one
ticker. Partitioning by *call* is not, because calls interact through shared cash
and through `swap_funding`.

**Conceded** on all three unaddressed cases. The `swap_funding` one is the most
damaging — a per-position split structurally cannot carry the cost imposed on the
funding position, so it either drops or double-counts that term.

**Conceded and independently important:** the dollar axis must be reported
benchmark-relative as well as absolute. In a tape where nearly everything rose,
an absolute-dollar axis makes the 2×2 degenerate into one populated row.

**Defended, narrowly:** the 2×2 retains descriptive value as a cross-tabulation
if the dollar cells are labeled explicitly as attributed-not-causal and the
reconciliation requirement is dropped rather than tightened. The challenge is
right that captions lose to numbers, so this is weak.

Leave-one-call-out is the better instrument and I accept it. Feasibility is
unestablished — 359 simulator runs at this corpus size is the open question, and
the bearish-subset fallback is a sound contingency.

### C7 — PARTIAL

**C7a — CONCEDE.** The oracle runs through the current allocator with caps
15/35/50, Rule 3, profit-take and starter sizing intact. It measures
(perfect analyst × current allocator), and Step 6's "Analyst headroom" line is
mislabeled. The minimum fix is right: report cap-binding frequency under the
oracle. If the oracle binds often, the "analyst ceiling" is largely an allocator
artifact.

**C7b — PARTIAL.** The logic is correct in principle: a flawless analyst would
optimize conviction and sizing, not only direction, so the arm is a lower bound
presented as an upper one. But the challenge offers its own refutation and it
holds — `prompts/sizing-channel-sensitivity.md` found `recommended_size_pct`
worth **$0**, because `target_pct = min(recommended_size_pct, cap_pct) if
recommended_size_pct else cap_pct` combined with X=2.5pp makes the target value
nearly inert. The sizing channel specifically is not a live loosening term.
Conviction and `thesisDelta` are not covered by that citation and remain open.
Whatever is chosen must still be pre-registered in 0d and named as a
bound-loosening assumption.

**C7c — CONCEDE.** `price_cache.json` frozen at 2026-05-08 gives
`cutoff = 2025-11-07`. Every call after that is unscoreable, so the oracle has no
information across the tail while the real arm trades through it. Step 4
specifies no fallback. This is a specification hole that drives the headline
number, and the challenge is right that a "use the real call" fallback would
silently deflate the contrast.

**C7d — CONCEDE.** Labeling, on both counts. "Flawless" must be qualified as
flawless-at-182-days-±5%-versus-SPY, and the sanity check's denominator must be
stated as scoreable events only.

**Oracle at or below actual — CONCEDE, and this is the best point in the
document.** Step 4 has no slot for it and should. If perfect 182-day SPY-relative
direction, run through this allocator, does not beat the real arm, the finding is
that the allocator's direction→action mapping is misaligned with the horizon
§3.1 grades on. That would be the headline of the run, and as written the prompt
would have sent a CLI session off to debug it as a defect.

### C8 — CONCEDE

The most consequential item. The asymmetry is exactly as described: Step 5's
figure is an in-sample maximum over a space already searched on this corpus
(upward biased), while Step 4's oracle is downward biased for every reason in C7.
Step 6 subtracts the actual from each and labels both differences "headroom."

The resulting comparison — deflated analyst headroom against inflated allocator
headroom — points toward "invest in the allocator," which is the working
hypothesis 09-13 §2 explicitly flags as *constructed in conversation, not
measured*. The prompt disclaims the prior in prose and then builds an instrument
biased toward it. That is the failure mode the whole project's pre-registration
discipline exists to prevent, and it got past me.

Both minimum fixes accepted: bias sign on each ceiling line **inside** the Step 6
table, and Step 5 relabeled as an in-sample maximum over the searched space
rather than a ceiling.

### C9 — PARTIAL

**Conceded on design.** The scorer's usage block shows the intended artifact:

```
python3 analyst_direct_scorer.py --eval-dir data/evals/v6_sonnet-4-20250514
```

Provenance is carried by the directory name. Step 0b inherited Test 2's
substitution of DB `Analysis` rows — which carry no version stamp — and then
looked for provenance in `createdAt`. The gate was placed on the artifact that
structurally cannot carry the evidence. It should have asked first whether a
stamped eval cache covering these calls exists or is reconstructible.

**In practice:** `analysis/data/*` is gitignored (`.gitignore:15`), so no eval
cache was ever in the repo and none is in the working tree. The stamped path is
likely unrecoverable. That makes this simultaneously a documentation gap — the
prompt should have stated that the stamped artifact was checked for and found
absent, rather than silently proceeding on timestamps.

---

## 3. What the challenge got factually wrong

Nothing material. Two small notes:

- C5 characterizes the within-ticker scheme as moving calls "across market
  regimes, price levels and portfolio states." Correct, but it should be noted
  that the proposed cross-sectional alternative has a symmetric problem — it
  destroys the universe composition that Test 5 identified as dominant. The
  challenge's own bracketing recommendation already accounts for this; the
  framing just reads as though only one scheme is confounded.
- C6 cites `tier_return_attribution.py`'s −$44.95 residual as the standard the
  prompt set. That is accurate as a quote of the prompt, but the precedent is
  weaker than the prompt implied — per-ticker partition is additive by
  construction, per-call is not. This strengthens C6 rather than weakening it.

---

## 4. Additional findings — the gate's metric does not implement the gate's spec

Neither the challenge nor the original prompt caught these. Both concern
divergence between `PROMOTION_GATE.md` §3.1 and `analyst_direct_scorer.py`.

**F1 — baseline.** §3.1 specifies *"lift over an **always-hold** baseline"* and
justifies it: *"an always-'bullish' coin scores ~55–60% in a bull sample, so raw
accuracy is misleading."* The scorer implements **always-bullish** (line 18, 207).
The spec names the very strategy it intended to guard against, and the
implementation adopted it as the comparator. Whichever is correct, the two
documents disagree, and the gate's primary analyst metric is not the one §3.1
describes.

**F2 — benchmark.** §3.1 specifies *"the stock's sector ETF where one applies
(e.g. TAN for solar), else SPY"* and gives a worked ENPH-vs-TAN example. The
scorer states: *"Benchmark: SPY for all tickers (sector ETFs not yet in price
cache; revisit once TAN/SOXX/etc. are added)."* On a universe heavy in solar,
storage and semis over 2021–2025, SPY-relative and sector-relative grading are
very different instruments. Sector-driven moves that §3.1 intended to neutralize
are scored as analyst hits or misses.

F2 also corrects the 09-13 handoff, which described §3.1's sector-relative design
as though it had run. It did not.

Both belong in `PROMOTION_GATE.md` §10 as open items. Until F1 is resolved, no
lift figure computed by this scorer — including −5.8pp — should be cited against
§3.1's stated methodology.

---

## 5. Design changes implied

| # | Change | From | Cost |
|---|---|---|---|
| 1 | Add an **always-bullish-through-the-allocator** arm, run before Steps 1–6 | C2 | New work, $0 API |
| 2 | Delete the motivating-tension framing; restate the question as "does v6 beat always-bullish in dollars" | C1 | Spec edit (free) |
| 3 | Compute the **bearish ground-truth base rate**; correct the handoff's "four times in five" | C3 | Spec edit + trivial compute |
| 4 | Add **McNemar vs always-bullish** and a **ticker-block bootstrap** to Step 0/1 | C4 | New work, $0 |
| 5 | Read each Step 3 ablation against the Step 2 permutation null | C4 | Spec edit, reuses budgeted compute |
| 6 | Add a **cross-sectional (within-event-date) permutation** as a second scheme; keep within-ticker as primary | C5 | New work, $0 |
| 7 | Delete "preserve chronology"; require per-ticker event counts and distinct-arrangement counts | C5 | Spec edit (free) |
| 8 | Withdraw Step 2's pre-registered 50th-percentile interpretation | C5 | Spec edit (free) |
| 9 | Drop Step 1's reconciliation requirement; label the 2×2 non-causal; add a **benchmark-relative** dollar axis | C6 | Spec edit (free) |
| 10 | Replace the attribution convention with **leave-one-call-out**, bearish subset if 359 runs is infeasible | C6 | New work, $0 |
| 11 | Step 4 reports **cap-binding frequency** under the oracle | C7a | Spec edit (free) |
| 12 | Relabel Step 6's line as "Analyst headroom **under the current allocator**" | C7a | Spec edit (free) |
| 13 | Pre-register the oracle's non-direction field synthesis in 0d as a bound-loosening assumption | C7b | Spec edit (free) |
| 14 | Specify the **post-2025-11-07 fallback** explicitly; report the tail's size | C7c | Spec edit (free) |
| 15 | Qualify "flawless" to 182d/±5%/SPY; state the sanity check's denominator | C7d | Spec edit (free) |
| 16 | Pre-register **oracle ≤ actual** as a finding, not a defect | C7 | Spec edit (free) |
| 17 | Carry the **sign of the bias** on each ceiling line inside the Step 6 table; relabel Step 5 as an in-sample maximum | C8 | Spec edit (free) |
| 18 | State in Step 0b that the stamped eval cache was sought and found absent | C9 | Spec edit (free) |
| 19 | Record **F1** (always-hold vs always-bullish) and **F2** (sector ETF vs SPY) in `PROMOTION_GATE.md` §10 | F1/F2 | Spec edit (free) |

Fourteen of nineteen are free specification edits. The new work — items 1, 4, 6,
10 — is all $0 in API spend.

---

## 6. The one sentence

> Of the nine challenges, **five** are conceded in full and **four** in part; the
> design change with the largest effect on what this test would conclude is
> **adding the always-bullish-through-the-allocator arm (C2), together with
> dropping the motivating-tension framing it invalidates (C1)**, and without it
> the test would have concluded **that a real tension existed between Test 1 and
> Test 2 and spent five steps reconciling what is only a difference between two
> comparators — while Step 6's oppositely-biased ceilings (C8) delivered a
> headroom comparison tilted toward the allocator, the answer the authoring
> session had already guessed.**
