# Value attribution v2 — Stage C: what actually earns the money

**Run ID:** `value-attribution-and-headroom-v2` (continuation). **Stage:** C.
**Status: PARTIAL RUN.** C1 and C2 attempted (as instructed, in that order,
since they were named cheapest and most decision-relevant). C1 is complete
and produced this run's headline finding. **C2 did not produce a usable
result** — see §6. **C3, C4, C5, C6 are not started** and remain `pending`.
This is reported plainly, not softened: the prompt explicitly authorizes
stopping cleanly on a partial run rather than rushing, and running C1/C2
first was itself the prompt's instruction because they "decide whether the
rest of the stage is worth running." They do — see §1.

**Driver:** `analysis/value_attribution_v2_stage_c_driver.py` (git commit
`cc908a3`, clean tree, reproduced verbatim). **Manifest:**
`analysis/data/value_attribution_v2/stage_c_manifest.json`.
**Cost:** $0 in Anthropic API spend — no LLM calls were made; every arm reads
already-stored `Analysis` rows and the frozen price cache.

---

## §0 — defined terms

Read this before the numbers below; several read as their own opposite.

| term | what it means here |
|---|---|
| **the control** | The real system: real analyst scores → real trend layer → real allocator (caps, ratchet, profit-take, starter sizing), on the settled configuration. Final value **$179,944.91**. |
| **Arm 0b** | A portfolio that buys a small starter stake in each of the 16 companies the first time it appears, then never buys or sells again for the rest of the window — as if you froze the account. Final value $120,799.82. |
| **Arm 0** — "the always-bullish guesser, run through the real portfolio machinery" | Every earnings call is treated as if the analyst said "buy more," ignoring what the analyst actually said. Still goes through the real caps, ratchet, and funding rules. Final value $173,102.24. |
| **Arm 0c** (new this stage) | Split $100,000 into 16 equal $6,250 slices, one per company. Buy each slice the first time that company shows up in this dataset. Never trade again — no caps, no ratchet, no rebalancing, nothing. This is the "just buy and hold, evenly, and do nothing" floor. Final value **$195,584.28**. |
| **cash share** | The fraction of the portfolio sitting in cash (not invested in any stock) on a given date. Higher cash share means more of the money is doing nothing that day. |
| **dollar-year invested** | One dollar invested for one year. A way of measuring "how much money, for how long" was actually at work in the market, so returns can be compared per dollar-year rather than just by final balance. |
| **bootstrap / 95% range** | A way of asking "if the 16 companies had been slightly different, would this result still hold?" by repeatedly re-drawing the 16 companies at random (with repeats allowed) and recomputing the answer each time. A 95% range that includes zero means "we cannot rule out that the true effect is nothing." |
| **the analyst's share ($6,842.67)** | Stage A's arithmetic: control ($179,944.91) minus Arm 0 ($173,102.24). This is everything the human-style analyst scoring and the trend layer add, net, once the allocator's rules and being-invested are already accounted for by Arm 0. |
| **reconciliation** | Whether a number built by adding up smaller pieces actually equals the total those pieces are supposed to explain. A decomposition that reconciles is trustworthy; one that doesn't is a warning sign, not a result. |
| Type A / Type B, tier cap, ratchet, profit-take, X=2.5pp, K=30, `swap_funding`, `pooled`, `per_event_date` | Unchanged from Stage A/B — see `wrap-ups/value-attribution-v2-stage-b-out.md` §0 for full definitions. This stage does not redefine the settled configuration; every arm runs on it. |

Plain-English restatement of the settled configuration, no identifiers: the
system checks in on the portfolio roughly every 30 calendar days, it only
acts on brand-new earnings calls (not stale ones), it lets winning trades
crowd out losing ones for a shared pool of that session's spending money
(rather than giving each stock its own separate budget), it caps how fast
any single position can grow in one check-in to 2.5 percentage points of the
whole portfolio, and when several companies report on the same day it treats
that whole day as one funding decision rather than several.

---

## Plain-language summary

**The single most important number from this stage: just buying all 16
companies equally, on the day each first shows up, and never touching them
again, made more money ($195,584.28) than the entire real system did
($179,944.91).** That is $15,639.37 more. The prompt asked whether the real
system's edge over a lazy floor was "skill or just being more invested." The
honest floor built this session (Arm 0c) is not just close to the real
system — it beats it outright. This is a stronger result than the prompt
anticipated (it expected "most of the advantage is deployment," not "the
machinery is a net drag versus doing nothing at all").

Filling in the prompt's requested lead sentence, adapted because the sign
came out the opposite of what the sentence assumed (see the note right
after it):

> Simply owning the 16 companies, fully invested and never trading, returned
> **$195,584.28**. The full system returned **$179,944.91** — **$15,639.37
> less**, not more. The three-way split the prompt asked for (deployment /
> allocator rules / analyst) only makes sense when the system beats the
> floor; here it does not, so the honest statement is: deploying capital
> fully and evenly is worth more than everything the allocator's rules,
> the trend layer, and the analyst add up to, combined, on this corpus and
> window. Of the smaller, positive-direction comparisons that Stage A did
> support: going from starter-only (Arm 0b) to always-adding (Arm 0)
> gained **$52,302.42** — capturing 88.4% of Arm 0b's gap to the control, as
> already reported in Stage A. On top of Arm 0, the analyst and trend layer
> add a further **$6,842.67** — and that share's distinguishability from
> zero is **not resolved this session** (see §6 — the bootstrap needed to
> answer that did not produce a trustworthy number).

**Deviation from the prompt, flagged:** the prompt's lead-sentence template
assumes the difference (floor to full system) is positive and splits it
three ways. C1's result makes that template inapplicable as written. This is
reported as a finding, not corrected by silently flipping a sign or
re-defining "the floor" to make the arithmetic come out the way the template
expects.

---

## §1 — C1: how much of the gap is just being invested?

**Ladder (final values, all four arms on the identical 195-event population,
identical settled configuration):**

| arm | what it actually buys/sells | final value | avg. cash share | return per dollar-year invested |
|---|---|---:|---:|---:|
| Arm 0b | starter stake per company, then nothing, forever | $120,799.82 | 65.5% | 0.242 |
| Arm 0 | always "buy more" on every call, real caps/ratchet apply | $173,102.24 | 15.3% | 0.312 |
| Control (the real system) | real analyst + trend layer + allocator | $179,944.91 | 26.0% | 0.383 |
| **Arm 0c (new)** | equal $6,250 slice per company, bought once, never touched | **$195,584.28** | n/a (never holds cash after each slice is bought) | 0.332 |

All figures — `analysis/data/value_attribution_v2/stage_c_manifest.json` →
`c1_deployment_ladder.<arm>.final_value` (each a forward draw: one
deterministic replay, not a median across draws — matches Stage A's
`kind` for the same three arms). Cash shares and return-per-dollar-year are
also read from that same key, `.avg_cash_share` /
derived from `.dollar_years_invested`.

**The idle-cash story holds up as a mechanism, even though it doesn't fully
explain the floor's win.** Arm 0b, which holds the most idle cash (65.5% on
average), makes the least money. Arm 0, which holds the least idle cash
(15.3%), beats it by $52,302.42. The control sits in between on cash share
(26.0%) and in between on value. **That part of the prompt's hypothesis is
confirmed: less idle cash tracks more money, monotonically, across these
three arms.**

What the prompt did not anticipate: Arm 0c, which by construction holds
*zero* idle cash after each of the 16 initial buys (there is nothing left to
buy or sell), beats all three of them — including the control that
supposedly has every advantage (real analyst input, real trend layer, real
allocator discipline) working for it. **Being maximally, permanently
invested and doing nothing else outperforms all three arms that use the
allocator's active machinery on this corpus.**

One caveat on "return per dollar-year invested," reported because it
complicates a simple "Arm 0c just wins" story: Arm 0c's dollar-years-invested
figure (288,261) is the largest of the four, because its capital stays fully
deployed for the whole remaining window from each stock's first appearance,
whereas the control cycles capital in and out. Per dollar-year, the control's
0.383 is actually the *highest* of the four — higher than Arm 0c's 0.332. So
by one lens (total dollars) Arm 0c wins outright; by another (dollars per
year of capital tied up) the control is the most capital-efficient. Both are
reported; neither is picked as "the" answer, per the scope boundary.

**Arm 0b's "never invested" share of starting capital**, approximated as the
final cash balance divided by the $100,000 starting capital (an
approximation, not an exact "touched vs. never touched" count, because Arm
0b's forced-Hold mechanism means cash placed by the last funding session
never gets deployed later either — see driver docstring): **59.6%** of the
original $100,000 ends the window as cash that was never converted to
shares beyond the single starter buys. (`stage_c_manifest.json` →
`c1_deployment_ladder.arm_0b_universe_only.never_invested_approx_share_of_initial`.)

---

## §2 — C2: is the analyst's $6,842.67 distinguishable from zero?

**Not answered this session.** The point figure reproduces cleanly: control
minus Arm 0 = **$6,842.67 exactly**
(`stage_c_manifest.json` → `c2_bootstrap.actual_point_diff_control_minus_arm0`),
matching the prompt's and Stage A's quoted figure to the cent.

The attempt to bootstrap a 95% range around that figure **failed at the
decomposition step**, and this is reported as a methodological finding, not
papered over with a number that looks plausible:

- The per-ticker split built from each arm's realized gains/losses plus
  final mark-to-market positions was supposed to add up to $6,842.67. It
  instead summed to **-$6,168.18** — the opposite sign.
  (`stage_c_manifest.json` → `c2_bootstrap.total_diff_approx`, `.reconciliation_check_passed: false`.)
- **Why it fails:** the decomposition ignores that the two arms hold
  different cash balances, buy and sell at different times (different tax
  lots), and — because funding here is `pooled` and compounding across a
  shared session budget — one arm's trade in one ticker changes how much
  cash is available for a different ticker in the same session. This is the
  same non-additivity the prompt itself warns about for C6's leave-one-out
  step; it turns out to also break a same-session per-ticker split for C2.
- The bootstrap 95% range computed on top of this broken decomposition is
  **[-$81,686.55, $74,499.01]** and is recorded in the manifest under the key
  `bootstrap_95_range_UNRELIABLE_see_reconciliation_note` — the key name
  itself flags that it must not be cited as a confidence interval on
  $6,842.67. It spans zero, but that fact carries no evidentiary weight given
  how it was built, and is not reported as "the range" in this summary for
  that reason.
- 4 of 16 tickers showed a positive contribution under this (unreliable)
  split; the single largest-magnitude ticker was AVGO ($24,341.42), which
  happens to be one of the three names `tier_return_attribution.py` already
  flagged as dominant (NVDA 40.1% of P&L; NVDA+AVGO+ORCL 81.4%) — but because
  the decomposition doesn't reconcile, this concentration finding is **not
  independently confirmed** by this run and should not be treated as new
  evidence of AVGO-specific attribution.

**What a valid version would require:** resampling the 16-ticker universe
itself (not a derived per-ticker P&L split) and re-running both arms' full
195-event simulation for each of ≥2000 resampled universes. That is roughly
2000 full simulator invocations per arm — expensive, and not attempted this
session. This is the single most important unfinished piece of Stage C:
**Stage B already found the analyst's calls indistinguishable from an
informed coin flip; Stage C was supposed to settle whether the analyst's
*dollar* contribution is distinguishable from zero, and it still isn't
settled.**

---

## §3 — C3 (ablations): NOT REACHED

Pending. `next_action` in `progress.json` names this as one of two viable
next steps (the other being a corrected C2). C3 does not require universe
resampling and is comparatively cheap; a future session could run it before
returning to C2.

## §4 — C4 (permutation): NOT REACHED

Pending — depends on C3's ablation arms being defined precisely enough to
know what "the real system" being permuted actually consists of (B2's
disable mechanic in particular needs to be pinned down first, per the
pre-registration's flag that it is the most likely ablation to be
ambiguous).

## §5 — C5 (trend-layer surface): NOT REACHED

Pending — this step reads off arms that C3/C4 would already be running; it
was not run as a standalone measurement this session because doing so would
have meant re-deriving the C3/C4 machinery early, out of the prompt's stated
value order.

## §6 — C6 (leave-one-call-out): NOT REACHED

Pending — the most expensive step (up to 195 full simulator runs). Per the
prompt's own fallback, if reached next session before C3/C4 are done, the
bearish subset only should run first.

---

## Pre-registration and hygiene

- Stage C fields were added to
  `analysis/data/value_attribution_v2/PREREGISTRATION.json` under a new
  `stage_c` key **before** any Stage C arm ran (arm definitions, C1's cash
  methodology, C2's bootstrap plan, C3's four disable mechanics — with B2
  flagged as possibly ambiguous, per the prompt's explicit instruction — C4's
  two permutation schemes, and C6's leave-one-out design). No pre-existing
  `stage_c` content was found, so no abort-on-mismatch was triggered.
- `progress.json` gained `prompt_sha256_stage_c` alongside the existing
  `prompt_sha256` / `prompt_sha256_stage_b` keys, per the waiver — none were
  overwritten. `steps.stage_c_contribution` was set to `in_progress` (not
  `done`, since C3-C6 remain outstanding) as the first action of this
  session, before the larger source files were read.
- **0c arithmetic check: PASSED.** The prompt's cited $52,302.42,
  $59,145.09 and 88.4% were re-verified by rerunning Stage A's control, Arm
  0b, and Arm 0 cells inside this session's own driver
  (`value_attribution_v2_stage_c_driver.py`'s reproduction-check step) —
  control $179,944.91, Arm 0b $120,799.82, Arm 0 $173,102.24, all matching
  to the cent. $179,944.91 − $120,799.82 = $59,145.09; $173,102.24 −
  $120,799.82 = $52,302.42; $52,302.42 / $59,145.09 = 88.4%. No contradiction
  found — this is one arithmetic check that came out clean, unlike C2's
  decomposition.
- Working tree: `git stash push -u -m "unrelated-wip-before-stage-c"` was run
  before any Stage C file was written, capturing the unrelated dirty state
  named in the prompt (ec-fidelity-benchmark-1 progress.json, two probe
  scripts, several domain-midcap/methodology-challenge files, two 2026-09-13
  handoff documents, and the untracked prompts/wrap-ups for the earlier
  stages of this same run — all of which were read for required context
  before being stashed, per the prompt's instruction). `git stash pop` was
  run at the end of this session (see below); `git status` afterward showed
  the same untracked/modified files as at the start, no conflicts.
- Driver committed before any manifest, as its own commit
  (`e3b3279`), followed by a bugfix commit (`7e02550`) once the
  dollar-years-invested integral was found to be wrong (see next bullet),
  then two manifest-only commits (`cc908a3` interim, `ef384bc` final,
  clean-tree, `git_dirty: false`).
- **Bug caught and fixed before the final manifest was written:**
  `DailySnapshot` objects are recorded once per funding *session*
  (~28-30 calendar days apart, matching the settled `K=30` cadence), not
  once per calendar day, despite the class's name. The first draft of the
  dollar-years-invested integral assumed a 1-day gap between consecutive
  snapshots and understated every arm's dollar-years by roughly 30×. Fixed
  to use the actual gap between snapshot dates. This is exactly the kind of
  premise-verification the project's standing rules ask for — caught before
  it reached a report, not after.
- Verified: `python3 -c "import ast; ast.parse(...)"` passed on the driver
  before every run. `git log` shows the recorded commit
  (`cc908a3`) contains the driver file used to produce the final manifest.

---

## Limitations (stated, not argued past)

- Every figure describes this 16-company universe and this window only. A
  prior run found this universe sat at the top of 25 random draws — it is
  **not representative**.
- The 195-event population covers 2020 through mid-2024. It has **zero 2025
  calls**, against 114 in the separate scorer population Stage B used for
  its hit-rate figures.
- The corpus is a score stream of unverified prompt vintage; the
  `2026-05-02 12:33:23-04` split comparison is still unrun.
- **Stage C measures contribution only.** Headroom — what the analyst or
  allocator could achieve at their ceiling — is Stage D, still `pending`,
  untouched by this session.
- No spec file was edited this session (`PROMOTION_GATE.md`,
  `VERSION_REGISTRY.json`, `EVALUATION_PROMPT.md`, `versions.js`, the
  production prompt) — none of these were in scope for Stage C and none was
  touched.

## Superseded figures

None. Every previously published figure this session touched (control,
Arm 0b, Arm 0, and the $6,842.67 / $52,302.42 / $59,145.09 / 88.4% derived
figures) reproduced exactly. Arm 0c and the C1 ladder are new figures, not
corrections to prior ones. C2's bootstrap range is **not** a supersession of
anything published before — it is a new attempt that failed its own
reconciliation check and is reported as failed, not as a number to be relied
on.

---

## What's next (exact follow-up)

Two viable next steps, either is reasonable to run first:

```
# (a) Build a valid C2: resample the 16-ticker universe with replacement,
#     re-run BOTH the control and Arm-0 full 195-event simulation for each
#     resampled universe (~2000 runs per arm), and bootstrap the
#     control-minus-Arm-0 difference on the resulting distribution of
#     final-value differences rather than on a per-ticker P&L split.
cd analysis && python3 -c "print('scaffold this against value_attribution_v2_stage_c_driver.py run_arm()')"

# (b) Run C3's four ablation arms (caps, Rule 3, profit-take, starter sizing)
#     against the already-defined disable mechanics in
#     analysis/data/value_attribution_v2/PREREGISTRATION.json -> stage_c.ablations_c3,
#     pinning B4's exact uniform starter percentage before it runs.
cd analysis && python3 value_attribution_v2_stage_c_driver.py  # extend with C3 arms
```

Either path should update `analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`'s
`next_action` and append to `findings.md` the moment each result lands, per
the resume protocol.
