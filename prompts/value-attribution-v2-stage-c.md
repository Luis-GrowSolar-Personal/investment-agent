# Value attribution v2 — Stage C: what actually earns the money

**Run ID:** `value-attribution-and-headroom-v2` — **continuation, not a new run.**
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/value-attribution-v2-stage-c-out.md` (leave Stage A's and
Stage B's wrap-ups intact).

**Read first:** `wrap-ups/value-attribution-and-headroom-v2-out.md` (Stage A),
`wrap-ups/value-attribution-v2-stage-b-out.md` (Stage B),
`wrap-ups/scorecard-repair-out.md`, and
`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`.
Stage C is specified in §7 of `prompts/value-attribution-and-headroom-v2.md`;
this prompt supersedes that section.

---

## 1. What changed, and why Stage C is now a narrower question

Stage A measured three portfolios on the same 195 call-events:

| arm | what it does | final value |
|---|---|---|
| Arm 0b | buys a starter position in each of the 16 names on its first call, never trades again | $120,799.82 |
| Arm 0 | adds on **every** call, ignoring the analyst entirely | $173,102.24 |
| Actual | real analyst → trend layer → allocator | $179,944.91 |

**Arm 0 captures $52,302.42 of the $59,145.09 that the full system earned over
Arm 0b — 88.4% of it — while using no analyst information whatsoever.**

That bounds the question. Everything the analyst and trend layer contribute,
net, is at most the remaining **$6,842.67**. Stage B separately found the
analyst's calls indistinguishable from an educated guess.

**So Stage C's question is no longer "how do we split the money three ways."
It is:**

1. **Is Arm 0's $52,302 advantage skill, or is it just being more invested?**
   Arm 0b holds starter positions only (5% speculative / 8% established) and may
   sit on a large idle cash balance for the whole window. If so, most of the
   gap is exposure to a rising market, not allocator discipline — and the floor
   Stage A built the table on is too low.
2. **Is the analyst's remaining $6,842.67 distinguishable from zero?**
3. **If the money is in the allocator, which rule produces it?**

**Do not treat these as rhetorical.** A result showing the allocator's advantage
is mostly cash deployment is a finding, not a failure, and is the most
decision-relevant outcome this run can produce.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** Every arm runs the existing simulator over
   already-stored scores. If a step appears to need a model call, **stop and
   report it**. Assert this in the run log before the first arm.
2. **Do not modify any stored `Analysis` row.** Arms needing altered scores
   build in-memory or scratch-file copies.
3. **No price-cache refresh.** Frozen at 2026-05-08.
4. **Firewall holds.** No portfolio data reaches the analyst or trend layers; no
   transcript data reaches the allocator.
5. **No modification** of `docs/EVALUATION_PROMPT.md`, `server/lib/versions.js`,
   `docs/architecture/VERSION_REGISTRY.json`, `PROMOTION_GATE.md`, or the
   production prompt. Stage C reports; it does not edit specs.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production). **Do not gate on either.**
8. **Every arm runs on the locked 195-event simulator population** defined in
   Stage B's B0 and frozen in `PREREGISTRATION.json`, with the settled
   configuration (`swap_funding`, K=30, `new_calls_only`, X=2.5pp, `pooled`,
   `per_event_date`). Any arm that cannot is reported as unavailable, not
   substituted.

---

## 3. Step −1 — resume protocol, same waiver as Stage B

State continues in `analysis/data/run_state/value-attribution-and-headroom-v2/`.

**The changed-prompt-archives-state rule is waived**, as it was for Stage B.
Record this prompt's sha256 as `prompt_sha256_stage_c` alongside the existing
keys. Do not overwrite them. Do not clear `cells.jsonl` or `findings.md` —
append only. Leave Stage A's and Stage B's step statuses `done`. Set
`steps.stage_c_contribution` to `in_progress` as the first action.

**Run order is by value, not by number: C1 and C2 first.** They are cheap and
they decide whether the rest of the stage is worth running. If budget runs
short after them, that is a successful partial run.

---

## 4. Step 0 — hygiene and pre-registration

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b.** Fill in the Stage C fields of
`analysis/data/value_attribution_v2/PREREGISTRATION.json` **before any arm
runs**: every arm's definition, each ablation's disable mechanics, both
permutation schemes, the leave-one-out design, and a fixed seed for every
stochastic arm. Abort on mismatch if they already exist with different content.

**0c. Verify this prompt's arithmetic.** Recompute $52,302.42, $59,145.09 and
88.4% from Stage A's manifest. *A contradiction is a finding, not a reason to
stop.*

---

## 5. Step C1 — how much of the gap is just being invested? *(run first)*

The cheapest and most consequential diagnostic in this stage.

For **Arm 0b, Arm 0 and the control**, over the full window, report:

- average share of portfolio value held in cash, and the same figure at each
  event date;
- total dollars deployed and when — a deployment curve per arm;
- for Arm 0b specifically: what share of the starting $100,000 was **never
  invested at all**;
- each arm's return **per dollar-year actually invested**, alongside its final
  value.

**Then the fair-floor arm.**

**Arm 0c — equal-weight, fully invested, never traded.** Divide the starting
capital equally across the 16 names, buying each at its first appearance in the
window, and never trade again. No starter percentages, no idle cash. Report its
final value.

**Arm 0c is the honest floor** for the question "did the machinery beat simply
owning these companies." Arm 0b answers a different and weaker question,
because it leaves capital idle by construction.

Report the full ladder: Arm 0b, Arm 0c, Arm 0, control. **If Arm 0c lands near
or above the control, that is the headline of this run** and every later step
should be read against it.

---

## 6. Step C2 — is the analyst's $6,842.67 distinguishable from zero?

The control beat Arm 0 by $6,842.67 on one path. That is the entire net
contribution of the analyst and trend layer together.

Test whether it survives noise. Resample **tickers** with replacement (16
blocks), ≥2000 resamples, fixed recorded seed, and recompute the
control-minus-Arm-0 difference each time. Report the 95% range.

**If the range includes zero, say so in the wrap-up's opening summary**, not in
a note. It would mean the analyst and trend layer together cannot be shown to
add anything over "add on every call," which — combined with Stage B — is the
single most consequential finding available from this corpus.

Report alongside: how many of the 16 names contribute positively to the
difference, and how much of it comes from the single largest contributor.
`tier_return_attribution.py` recorded NVDA at 40.1% of P&L and NVDA+AVGO+ORCL at
81.4%; if the $6,842.67 is one name, say which.

---

## 7. Step C3 — which allocator rule produces the money?

Hold the real calls fixed. Disable one mechanism at a time, re-run, report the
dollar change against the control, **read against the permutation range from C4
rather than as a bare point figure**.

| Arm | Disable |
|---|---|
| B1 | Type A/B caps (15.0 / 35.0 / 50.0) |
| B2 | Rule 3 — permit averaging down on speculative losers |
| B3 | Profit-take (`PROFIT_TAKE_THRESHOLD_PCT` 25.0 / `REDUCTION_PCT` 5.0) |
| B4 | Starter sizing — uniform entry instead of 5.0 / 8.0 |

State for each arm exactly what "disabled" means mechanically — removing a cap
requires defining what replaces it, and that choice changes the number. **Flag
any arm whose disable is ambiguous rather than picking silently.** All other
settled parameters stay fixed.

**A rule that costs money is the most actionable result in this test.** Report
it prominently if one appears.

Add one diagnostic, because C1's hypothesis predicts it: for each ablation,
report the change in average invested share alongside the change in dollars. If
the dollar changes track deployment rather than selection, say so.

---

## 8. Step C4 — timing and selection

Keep every call the analyst made; destroy one mapping at a time, then run the
real system end to end including the trend layer.

- **Primary — within-ticker.** Shuffle which event each call attaches to inside
  the same ticker. Universe, per-ticker call mix and call count unchanged.
- **Second — cross-sectional.** Permute call labels across tickers within the
  same event-date cohort, holding the calendar fixed. This perturbs universe
  composition, which is its known weakness; it is here to bracket, not to
  arbitrate.

Both: **≥200 shuffles**, fixed recorded seed, full range (median, 5th and 95th
values, min, max), and where the real arrangement sits within it. Report
**per-ticker event counts and the number of distinct possible arrangements** —
a 4-event ticker admits only 24, and 200 draws then repeat themselves.

**Do not restate any "preserve chronology" constraint** — it was
self-contradictory and is deleted. **Do not pre-register a verdict on the
result.** Under `pooled` funding the allocator is path-dependent and
compounding, so a mid-range result cannot separate "no timing skill" from "the
real arrangement deployed capital earlier." Report the position; do not
interpret it as a verdict.

---

## 9. Step C5 — the trend layer's own surface

Two measurements, both free, from arms already running:

- the share of events where `apply_matrix` returns a `final_action` **differing
  from** `per_call_rec`;
- the share of funding decisions where `rank_key()`'s ordering would differ if
  `final_confidence` were held constant.

These size the third layer. Without them the deliverable cannot separate the
trend layer from the analyst.

---

## 10. Step C6 — per-call attribution

**Leave-one-call-out.** Set each call to neutral, re-run, take the difference.
This is a marginal contribution, and **it will not sum to the total — that
non-additivity is the honest signal, not a residual to manage.** Do not use a
bookkeeping split and do not impose a reconciliation requirement.

If 195 simulator runs is infeasible, run the bearish subset only and say so.

Report the cross-tabulation of scorecard hit/miss against made/lost money, with
counts and dollars, **labeled explicitly as attributed, not causal**, and report
the dollar axis **benchmark-relative as well as absolute** — in this window an
absolute axis collapses the table into one populated row.

---

## 11. Step C7 — the report

**Scope boundary: report, do not decide.**

The wrap-up opens with a **§0 defined-terms section** and then a
**plain-language summary**, both written to the project instructions' language
rules: no statistics vocabulary without a one-line plain definition, every
percentage anchored to what it is a percentage of, scoring dummies called the
**always-bullish guesser** and the **always-flat guesser**, portfolio arms
described by what they actually buy and sell, short sentences.

Lead with this sentence, filled in:

> Simply owning the 16 companies, fully invested and never trading, returned
> **$______**. The full system returned **$179,944.91**. Of the difference,
> **$______** comes from deploying more capital, **$______** from the
> allocator's rules, and **$______** from the analyst and trend layer — and the
> analyst's share **is / is not** distinguishable from zero.

Then: C1's deployment ladder, C2's range, C3's per-rule figures, C4's
permutation positions, C5's trend-layer surface, C6's attribution.

**Limitations to state, not argue past:**

- Every figure describes this 16-company universe and this window. A prior run
  found this universe sat at the top of 25 random draws — it is not
  representative.
- The 195-event population covers 2020 through mid-2024 only. It contains **zero
  2025 calls**, against 114 in the scorer population.
- The corpus is a score stream of unverified prompt vintage; the
  `2026-05-02 12:33:23-04` split comparison is still unrun.
- Stage C measures contribution only. Headroom — the analyst and allocator
  ceilings — is Stage D, still `pending`.

---

## 12. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number: forward draw, median across draws,
  or something else. A figure without provenance is a premise to verify.
- Record every arm's `config_hash` and seed.
- Driver committed before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** C1's hypothesis — that most of Arm 0's
  advantage is capital deployment — is the one most likely to be contradicted,
  and a contradiction there is valuable.
- **Note anything contradicting this prompt's premises.** It was written from
  Stages A and B; the repo outranks it.
