# Value attribution v2 — Stage C3: which rule earns, which rule costs

**Run ID:** `value-attribution-and-headroom-v2` — **continuation, not a new run.**
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`.
**Wrap-up:** `wrap-ups/value-attribution-v2-stage-c3-out.md` (leave the Stage A,
B and C wrap-ups intact).

**Read first:** `wrap-ups/value-attribution-v2-stage-c-out.md` (C1 complete, C2
failed its own check), `analysis/data/value_attribution_v2/PREREGISTRATION.json`
→ `stage_c.ablations_c3` (disable mechanics already pre-registered), and
`analysis/data/run_state/value-attribution-and-headroom-v2/progress.json`.

---

## 1. Why this run exists, and what changed

Stage C1 measured a floor nobody had built before: buying all 16 companies in
equal amounts once and never trading again returned **$195,584.28**, against the
full system's **$179,944.91**. **The machinery currently trails doing nothing by
$15,639.37 on this corpus and window.**

That reverses the question. It is no longer "how much does each rule
contribute." It is **"which rule is the drag."**

C1 also produced a second figure that points somewhere specific. Measured per
dollar actually invested per year, the control returns **0.383** against
buy-and-hold's **0.332** — the control's decisions are the *most* capital
efficient of the four arms, but it ends with less money because it holds an
average **26.0%** of the portfolio in cash. On this evidence the problem may be
idle capital rather than bad decisions. This run tests that directly.

**Two questions, both answerable here for $0:**

1. Which of the four allocator mechanisms earns money and which costs it?
2. How much of the system's shortfall against buy-and-hold is idle cash?

**Do not treat either as rhetorical.** A rule that costs money is the most
actionable result available from this corpus, and a finding that cash drag
explains most of the shortfall would make this a configuration problem rather
than a strategy problem.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** Every arm replays the existing simulator over
   already-stored scores. If a step appears to need a model call, **stop and
   report it**. Assert this in the run log before the first arm.
2. **Do not modify any stored `Analysis` row.** No DB writes.
3. **No price-cache refresh.** Frozen at 2026-05-08.
4. **Firewall holds.** No portfolio data to the analyst or trend layers; no
   transcript data to the allocator.
5. **No spec edits.** `PROMOTION_GATE.md`, `VERSION_REGISTRY.json`,
   `EVALUATION_PROMPT.md`, `versions.js` and the production prompt are all
   untouched. This run reports.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production). **Do not gate on either.**
8. **Every arm runs on the locked 195-event simulator population** with the
   settled configuration (`swap_funding`, K=30, `new_calls_only`, X=2.5pp,
   `pooled`, `per_event_date`). An arm that cannot is reported unavailable, not
   substituted.

---

## 3. Step −1 — resume protocol, same waiver as Stages B and C

State continues in `analysis/data/run_state/value-attribution-and-headroom-v2/`.

**The changed-prompt-archives-state rule is waived**, as for Stages B and C.
Record this prompt's sha256 as `prompt_sha256_stage_c3` alongside the existing
keys; do not overwrite them. Append to `cells.jsonl` and `findings.md`; never
rewrite them. Leave every completed step `done`. C2, C4, C5 and C6 stay
`pending` — this run does not attempt them.

**Run order: Step 1, then Step 2, then Step 3.** Step 1 is the cheapest and
answers the "is it just idle cash" question. If budget runs short after it, that
is a successful partial run.

---

## 4. Step 0 — hygiene and pre-registration

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b.** Extend `PREREGISTRATION.json` with this run's new arms **before any arm
runs** — the cash-parked arm's mechanics, the leave-one-company-out design, and
a fixed seed. The four ablation disable mechanics are **already pre-registered**
under `stage_c.ablations_c3`; use them as written. If they are ambiguous, **flag
the ambiguity and report it rather than picking silently** — do not amend a
pre-registered definition to make an arm runnable.

**0c. Fill the hole in C1's ladder.** Arm 0c's average cash share was reported
as "not applicable." It is not: Arm 0c must hold cash between each company's
first appearance and the next. **Measure it** and restate the C1 ladder with all
four cash shares present. *A result contradicting C1's implicit "zero idle cash"
assumption is a finding, not a correction to be made quietly.*

---

## 5. Step 1 — how much of the shortfall is idle cash?

**The cash-parked arm.** Run the real system, unmodified in every decision it
makes, with one change: **idle cash is held in SPY rather than at 0%.** At each
event date, any portfolio cash not deployed by the allocator's own decisions is
parked in SPY; it is sold back to cash first whenever the allocator needs
funding.

**This is a measurement device, not a proposed feature.** It deliberately does
**not** redeploy idle cash into existing positions, because proportional
redeployment is a closed design decision (`DESIGN_PRINCIPLES.md`; "Never Do").
Parking in the benchmark isolates the cost of idle capital without touching
position sizing at all. State this in the wrap-up so no future session reads the
arm as a recommendation.

Report: final value, average cash share, dollar-years invested, and return per
dollar-year, beside the four arms from C1's ladder.

**Then the reading, stated plainly:**

- If the cash-parked arm lands at or above **$195,584.28**, the system's
  shortfall against buy-and-hold is substantially **idle capital**. That is a
  configuration problem with a specific target.
- If it lands well below, idle cash is not the explanation and the shortfall is
  in what the system chooses to do. That is a strategy problem.
- Report the figure either way. **Do not interpret a middling result as
  supporting whichever reading the prompt appears to prefer.**

---

## 6. Step 2 — the four ablations

Hold the real calls fixed. Disable one mechanism at a time, per the mechanics
already in `PREREGISTRATION.json` → `stage_c.ablations_c3`. Re-run. Report each
arm's final value and its difference from the control.

| Arm | Disable |
|---|---|
| B1 | Type A/B caps (15.0 / 35.0 / 50.0) |
| B2 | Rule 3 — permit averaging down on speculative losers |
| B3 | Profit-take (`PROFIT_TAKE_THRESHOLD_PCT` 25.0 / `REDUCTION_PCT` 5.0) |
| B4 | Starter sizing — uniform entry instead of 5.0 / 8.0 |

All other settled parameters stay fixed across every arm.

**Report each difference against two references, not one:** against the control
($179,944.91) and against buy-and-hold ($195,584.28). A rule that improves on
the control while the whole system still trails buy-and-hold is a different
finding from one that closes the gap.

**For each arm also report the change in average cash share**, beside the change
in dollars. C1's evidence predicts that ablations which change deployment will
move money more than ablations which change selection. *A contradiction there is
a finding.*

**These are single-path point figures with no range attached.** The permutation
step that would supply one (C4) has not run. **Say so explicitly in the wrap-up
and do not describe any ablation as significant, material or decisive** — rank
them by size and let Step 3 speak to their stability.

---

## 7. Step 3 — is any rule's effect driven by one company?

The cheap substitute for a range, and the reason this run is worth more than a
table of four numbers.

For the control and each of the four ablation arms, re-run the full 195-event
simulation **16 times, each time dropping one of the 16 companies** from the
universe. That is 80 runs total, which is tractable where C2's ~2000-run
universe bootstrap was not.

For each ablation, report:

- the ablation's dollar effect in each of the 16 leave-one-out worlds;
- **how many of the 16 preserve the sign** of the effect measured on the full
  universe;
- which single company's removal changes the effect most, and by how much.

**A rule whose effect flips sign when one company is dropped is not a finding
about the rule.** Prior work put NVDA at 40.1% of profit and NVDA+AVGO+ORCL at
81.4%, so this check is expected to bite. Report where it does.

State plainly that sign stability under leave-one-out is **weaker evidence than
a confidence range** — it says an effect is not driven by a single company; it
does not establish that the effect is real.

---

## 8. Step 4 — drawdown for every arm

Buy-and-hold has no exit discipline. Nothing in Stage C looked at risk, so the
system's shortfall in dollars may coexist with an advantage in losses. Measure
it rather than assuming it either way.

For **every** arm in this run and in C1's ladder — Arm 0b, Arm 0c, Arm 0, the
control, the cash-parked arm, and the four ablations — report:

- maximum peak-to-trough decline in portfolio value over the window, in dollars
  and as a percentage;
- the date range of that decline;
- the largest single-quarter decline.

**Do not compute a risk-adjusted ratio and do not rank the arms by one.** Report
the raw figures beside the final values and let the comparison stand.

---

## 9. Step 5 — the report

**Scope boundary: report, do not decide.**

Open with a **§0 defined-terms table**, then a **plain-language summary**, both
written to the project instructions' language rules: no statistics vocabulary
without a one-line plain definition, every percentage anchored to what it is a
percentage of, every portfolio arm described by what it actually buys and sells
the first time it appears, short sentences, "points" not "pp".

Lead with these two sentences, filled in:

> Holding the system's idle cash in the benchmark instead of leaving it idle
> changes the final value from $179,944.91 to **$______**, against buy-and-hold's
> $195,584.28. Of the four allocator rules, the one that costs the most money is
> **______** (**$______**), and the one that earns the most is **______**
> (**$______**) — and **______ of the four** keep their sign when any single
> company is dropped from the universe.

Then: Step 0c's corrected ladder, Step 1's cash-parked arm, Step 2's four
ablations against both references with their deployment changes, Step 3's
leave-one-out table, Step 4's drawdowns.

**Limitations to state, not argue past:**

- Every figure describes this 16-company universe and this window. A prior run
  found this universe at the top of 25 random draws — it is not representative,
  and buy-and-hold's strength here partly reflects that the companies were
  well chosen.
- The 195-event population covers 2020 through mid-2024, with **zero 2025
  calls**.
- The corpus is a score stream of unverified prompt vintage.
- **No ablation figure in this run carries a confidence range.** C4 has not run.
- **C2 remains unresolved** — whether the analyst's $6,842.67 above "add on
  every call" is distinguishable from zero is still open, and this run does not
  address it.
- Stage D (headroom, the oracle ceiling) remains `pending`, untouched.

---

## 10. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number: forward draw, median across draws,
  or something else.
- Record every arm's `config_hash` and seed.
- Driver committed before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The most likely: Step 1's cash-drag
  hypothesis, and Step 2's prediction that deployment-changing ablations move
  more money than selection-changing ones.
- **Note anything contradicting this prompt's premises.** It was written from
  Stage C1; the repo outranks it.
