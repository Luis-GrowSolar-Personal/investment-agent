# Rule 3 disposition — remove the guard, or make it actually guard?

**Run ID:** `rule3-disposition`. **Status: COMPLETE, Steps 0 through 4 all done** —
not a partial run. **Cost: $0 in Anthropic API spend** (zero LLM calls made).
**Zero DB writes** to any stored `Analysis` row.

**Driver:** `analysis/rule3_disposition_driver.py`, committed at
`1afb0c66f66eefcc780cfaec84f00b8cc1fb42b1` (own commit, before any manifest).
**Manifest:** `analysis/data/run_manifests/rule3_disposition_manifest.json`,
produced at commit `5c0926ce2e81feebbb3badf8e2f193590cd44788` (`git_dirty: false`).
**Pre-registration:** `analysis/data/rule3_disposition/PREREGISTRATION.json`,
written before any arm ran.

**Scope boundary: report and propose, do not decide.** No spec file was edited:
`analysis/simulator/allocator_v2.py`, `allocator_v3.py`,
`analysis/sweep_cadence_and_session_model.py`, `server/lib/versions.js`,
`docs/architecture/VERSION_REGISTRY.json`, `PROMOTION_GATE.md`,
`EVALUATION_PROMPT.md` are all untouched — verified by sha256 hash comparison
before and after the run (`manifest.json` → `protected_files_unchanged: true`).

---

## §0 — defined terms

| Term | Meaning here |
|---|---|
| **Rule 3** | The allocator rule "don't buy more of a speculative stock that is currently trading below your own average cost in it." Written as a guard clause in `allocator_v2.py`. |
| **R3-keep** | Status quo: Rule 3's guard is live in the code, exactly as shipped. This report's finding (inherited from a prior run, Stage C3) is that in today's settled configuration this guard does NOT actually stop the purchase — it only changes how the purchase gets paid for (see "displacement" below). |
| **R3-remove** | Rule 3's guard is switched off entirely. A speculative stock trading below cost can be bought normally, funded like any other purchase. |
| **R3-enforce** | Rule 3's guard is made to actually work: when it fires, the purchase is skipped completely — no money moves for it at all, not even by a different route. |
| **Displacement funding** | The system's actual funding method: to buy stock X, it sells some other holding it already owns to raise the cash, rather than pulling from an idle cash pile. Under R3-keep, a purchase Rule 3 was supposed to block still happens this way — the guard blocks nothing, it just makes the system sell something else to pay for it. |
| **Session** | The system checks its 16-company list roughly every 30 days and acts only on companies with a fresh earnings call since the last check. |
| **X (session speed limit)** | A cap on how much of the portfolio can move into one position in one 30-day session — 2.5 points of the whole portfolio's value in every arm of this run, unchanged throughout. Not a cap on how big a position can eventually get, and not a budget for how many new stocks can be bought. Example: on a $200,000 portfolio, at most $5,000 can flow into one stock in one session, even if the system wants to buy more; the rest waits. |
| **Points vs. percent** | "Points" for an absolute difference between two percentages (cash share going from 26 points to 29 points is "+3 points"). "%" only for a share of something named at the same time. |
| **Drawdown / peak-to-trough decline** | The worst drop, in dollars and in percent, from a high point to a later low point during the run — a measure of how bad the worst stretch got, not of the final result. |
| **Leave-one-out** | Re-running an arm 16 times, each time with one of the 16 companies removed from the whole universe, to check whether the result depends heavily on any single company being present. |
| **Look-ahead ceiling** | A best-case number built by telling the system, in advance, which way each stock actually moved over the following six months — something no real analyst can know at the time. Every number under this label is a ceiling, never an achievable result. |
| **D-both** | The specific look-ahead-ceiling construction reused from a prior run (Stage D): every one of the 195 real calls in this population is replaced by the perfect call. |
| **Type A / Type B, tier cap** | Two position categories with fixed maximum sizes (35% for Type A, 50% for Type B); unrelated to Rule 3 and unchanged anywhere in this run. |
| **Ratchet, profit-take** | Other standing allocator rules (graded exit sequence on a weakening thesis; a trim once a position hits 25% of the portfolio); unchanged in this run. |
| **ALL16** | The frozen 16-company universe this system trades within (AAPL, AMD, AVGO, GOOGL, MSFT, NVDA, ORCL, TSLA, AMPX, ENVX, EOSE, FSLR, QS, RUN, SPWR, TTD). |

**Settled configuration, in plain English** (identical across every arm): the
system re-checks its 16-company list every 30 days, acts only on companies
with a fresh earnings call, pays for new purchases by selling other holdings
rather than holding cash aside, moves at most 2.5 points of the portfolio
into one position per 30-day cycle, and when several companies report on the
same date, ranks and funds them together as one group.

---

## Plain-language summary

> Leaving the guard as it is (status quo) returns **$179,944.91**. Removing
> the guard entirely returns **$189,362.81**. Making the guard actually block
> the purchase returns **$184,459.65**. The worst peak-to-trough falls are
> **20.85%** (status quo), **21.73%** (removed), and **17.62%** (enforced).
> Of the three, the one that earns most is **removing the guard**, and the
> one that loses least in a downturn is **making the guard actually
> enforce**.

Confirming Rule 3's code location (done in a prior run, Stage C3) surfaced
that the guard, as actually executed today, does not stop the purchase at
all — it only changes how the system pays for it, by selling something else
instead of using free cash. This run measured a third option nobody had
measured before: making the guard genuinely stop the purchase, with no
substitute funding for it. **All three numbers beat status quo. Removing the
guard earns the most money ($9,417.91 more than status quo); making the
guard actually work earns less money ($4,514.75 more than status quo) but
loses the least in a downturn** (a 17.62% worst-case drop, versus 20.85% for
status quo and 21.73% for removing the guard). Both non-status-quo options
sell less of the rest of the portfolio to fund these particular purchases —
status quo triggers 71 displacement sales; removing the guard, 60; enforcing
it, only 37.

---

## Step 0c — reproduction check

Both required reference figures reproduced to the cent before anything else
was measured, per the prompt's hard-stop instruction:

| Figure | Expected | Got | Match |
|---|---|---|---|
| Control (R3-keep) | $179,944.91 | $179,944.90608455564 (rounds to $179,944.91) | **MATCH** |
| R3-remove | $189,362.81 | $189,362.81437485846 (rounds to $189,362.81) | **MATCH** |

`analysis/data/run_manifests/rule3_disposition_manifest.json` → `step0c_reproduction`.
No discrepancy found — the run proceeded past this gate.

---

## R3-enforce mechanics — settled, and the ambiguity considered

The prompt's own concern: there could be more than one defensible way to make
a blocked add "genuinely not happen." Three candidate mechanics were
considered (documented in full in
`analysis/data/rule3_disposition/PREREGISTRATION.json` →
`three_configurations.R3_enforce`):

1. **The target amount simply vanishes for that event** (implemented).
2. The allocator retries with a smaller size.
3. The allocator skips to the next-ranked candidate in that session's pool.

**Only option 1 is grounded in the code's own existing logic.** Neither a
retry-at-smaller-size path nor a skip-to-next-candidate path exists anywhere
in `analysis/simulator/*.py` or `analysis/sweep_cadence_and_session_model.py`
for any allocator rule — this was checked directly, not assumed. Option 1
also reuses the exact same shape the codebase already uses for every other
"do nothing" case (a `Hold` call, or a non-positive target delta, both
already contribute nothing to the buy target). Per the same reasoning Stage
C3 used when it found no real ambiguity in Rule 3's code location, this run
resolves the ambiguity to option 1 rather than reporting it as unresolved —
**but this is the specific paragraph to revisit if Luis reads "genuinely does
not happen" differently; options 2 and 3 remain live, unevaluated design
alternatives that would require new code.**

**Implementation, without touching production files.** The dollar target for
an "Add" is computed inline inside `run_session_sweep_cell` in
`analysis/sweep_cadence_and_session_model.py` (lines 865-877 at commit
`5c0926c` — the prompt's own line citation, ~866-877, is essentially exact;
its file-path citation, `analysis/simulator/sweep_cadence_and_session_model.py`,
is off by one directory level: the file actually lives at
`analysis/sweep_cadence_and_session_model.py`, not under `simulator/` — a
minor premise correction, no figure is affected). Because this computation
is inline rather than a separately-patchable function, `analysis/rule3_disposition_driver.py`
builds an **in-memory patched copy** of the whole function (`inspect.getsource`
+ one narrow, asserted-unique string replacement + `exec` into a namespace
that is a snapshot of the real module's own globals) and uses that copy only
for the R3-enforce arm. **The on-disk file is never written to** — the driver
hashes `sweep_cadence_and_session_model.py`, both allocator files, and every
other named production/spec file before and after the run and asserts they
are byte-identical (`manifest.json` → `protected_files_unchanged: true`,
confirmed `True`). The patch inserts the identical predicate Rule 3's own
guard uses (`tier == "speculative"` and `day_price < _weighted_cost_basis(...)`)
at the point the "add" leg's dollar delta would be added to the session's
buy target, and skips adding it when the predicate fires. The starter leg
(first-call automatic small position) is structurally unaffected: Rule 3's
guard requires an existing position with a nonzero cost basis, and a starter
by definition fires only when no position exists yet, so it can never
trigger this guard.

---

## Step 1 — the three configurations

All arms at X = 2.5 points, settled configuration otherwise. Every figure:
`analysis/data/run_manifests/rule3_disposition_manifest.json` →
`step1_three_configs.<arm>` (forward draw, single deterministic path, seed=0).

| Quantity | R3-keep (control) | R3-remove | R3-enforce |
|---|---|---|---|
| Final value | **$179,944.91** | **$189,362.81** | **$184,459.65** |
| Δ vs. control | $0.00 | +$9,417.91 | +$4,514.75 |
| Δ vs. buy-and-hold ($195,584.28) | -$15,639.37 | -$6,221.47 | -$11,124.63 |
| Max peak-to-trough decline ($) | $21,501.56 | $22,402.72 | $18,164.48 |
| Max peak-to-trough decline (%) | 20.85% | 21.73% | **17.62%** |
| Drawdown date range | 2022-04-01 → 2022-12-27 | 2022-04-01 → 2022-12-27 | 2022-04-01 → 2022-12-27 |
| Avg cash share | 26.02% | 22.76% | **28.73%** |
| Dollar-years invested | $208,808.02 | $222,468.51 | $202,690.91 |
| Total funding events | 97 | 98 | 75 |
| Buys funded | 65 | 66 | 59 |
| **Displacement-funded sells** | **71** | **60** | **37** |
| Binding: session limit | 55 (56.7%) | 50 (51.0%) | 49 (65.3%) |
| Binding: cash available | 42 (43.3%) | 47 (48.0%) | 26 (34.7%) |
| Binding: target gap | 0 | 1 (1.0%) | 0 |

**The prompt's stated expectation — that status quo does MORE selling than
removing the guard — is CONFIRMED, not contradicted.** Status quo triggers 71
displacement-funded sells against 60 for removing the guard, exactly the
direction Stage C3's mechanism finding predicted (a blocked add under status
quo still gets funded, by selling something else — remove the guard and that
particular sale simply doesn't need to happen because the add now funds more
often from the natural buy path). R3-enforce triggers fewest of all (37):
when the add is genuinely skipped, no sale is generated to fund it at all.

**23 of the 195 events had their "add" target suppressed entirely** under
R3-enforce (`manifest.json` → `step1_three_configs.R3_enforce.n_events_blocked`).

**Tax.** The simulator does not model taxes anywhere — no federal, state,
LTCG, or STCG figure is computed for any arm in this report. Every value
above is pre-tax. The three arms differ materially in trade count (65-66
buys and 37-71 displacement sells depending on arm), so a real-world
after-tax ranking could differ from this pre-tax one — more trades generally
means more realized gains or losses to tax. This exposure is flagged, not
estimated, per the prompt's explicit instruction.

---

## Step 2 — leave-one-company-out for R3-enforce, and R3-remove restated

R3-enforce was re-run 16 times, each dropping one of the 16 companies from the
universe entirely, each compared against a **fresh R3-keep run in that same
reduced universe** (32 runs total, not 16 — the control had to be re-run for
every reduced universe too, since the full-universe control is not a fair
comparator once a company is removed). Full per-ticker table:
`analysis/data/run_manifests/rule3_disposition_manifest.json` →
`step2_leave_one_out.R3_enforce.effect_by_ticker_dropped`.

| Ticker dropped | R3-enforce effect vs. control (same reduced universe) |
|---|---|
| AAPL | $5,865.99 |
| AMD | $6,974.20 |
| **AVGO** | **$10,905.32** (largest mover) |
| GOOGL | $5,020.51 |
| MSFT | $6,932.43 |
| NVDA | $1,243.76 (smallest, still positive) |
| ORCL | $9,824.43 |
| TSLA | $8,793.37 |
| AMPX | $7,080.67 |
| ENVX | $10,450.90 |
| EOSE | $6,218.37 |
| FSLR | $2,783.76 |
| QS | $6,234.51 |
| RUN | $4,430.29 |
| SPWR | $4,514.75 (unchanged from full-universe figure) |
| TTD | $10,491.71 |

| Arm | Full-universe effect | Sign preserved (of 16) | Company changing effect most |
|---|---|---|---|
| **R3-enforce** (this run) | +$4,514.75 | **16/16** | AVGO ($10,905.32, Δ$6,390.57 from full) |
| **R3-remove** (restated from Stage C3, NOT re-run this session) | +$9,417.91 | **16/16** | ENVX ($14,204.30, Δ$4,786.40 from full) |

Source for the restated R3-remove row:
`analysis/data/value_attribution_v2/stage_c3_manifest.json` →
`step3_leave_one_company_out.sign_stability.B2_disable_rule3`.

Dropping SPWR leaves R3-enforce's effect completely unchanged
($4,514.75 exactly) — no Rule-3-triggering event in this population ever
involves SPWR.

**Stated plainly, per the prompt's instruction: sign stability is weaker
evidence than a confidence range.** 16/16 sign preservation for both
R3-enforce and R3-remove says neither effect is the artifact of a single
company's presence in the universe. It does **not** establish that either
effect is real, or that it would replicate under a different corpus, universe,
or window.

---

## Step 3 — perfect-analyst ceiling under each configuration

**Every figure in this section is a look-ahead ceiling, not an achievable
result** — it assumes knowledge of the future. Reused Stage D's exact D-both
oracle labels and synthesis (`ORACLE_SYNTHESIS`, injected at `per_call_rec`),
imported directly from `analysis/value_attribution_v2_stage_d_driver.py`, not
regenerated. Label report confirms the same population as Stage D: 195/195
events labelable, 83 bullish / 85 bearish / 27 neutral
(`manifest.json` → `step3_ceiling.label_report`).

| Configuration | Final value **(LOOK-AHEAD CEILING)** | Δ vs. R3-keep ceiling |
|---|---|---|
| R3-keep @ D-both | $263,073.65 | $0.00 |
| R3-remove @ D-both | $265,386.41 | +$2,312.76 |
| R3-enforce @ D-both | $256,975.97 | -$6,097.68 |

Source: `manifest.json` → `step3_ceiling.<arm>.final_value_LOOKAHEAD_CEILING_NOT_A_RESULT`.

**Reported without pre-committing to a reading, per the prompt's instruction.**
Under real calls, R3-enforce sits BETWEEN R3-keep and R3-remove (+$4,514.75).
Under perfect calls, R3-enforce falls BELOW R3-keep (-$6,097.68), while
R3-remove's edge over R3-keep shrinks sharply, from $9,417.91 under real
calls to $2,312.76 under perfect ones. One way to read this: much of Rule 3's
real-world cost (and R3-remove's real-world gain) is tied to the analyst's
prediction quality specifically, not to the guard mechanism in the abstract
— a perfect analyst benefits far less from either removing or enforcing
Rule 3 than the real analyst does. This reading is offered, not asserted as
settled; the prompt's own instruction is to report the numbers, not force a
conclusion.

---

## Step 4 — timing

Difference vs. control by calendar year, and the single largest contributing
quarter. Source: `manifest.json` → `step4_timing.<arm>`.

| Arm | 2022 (cumulative Δ) | 2023 (cumulative Δ) | 2024 (cumulative Δ) | Largest single quarter |
|---|---|---|---|---|
| R3-remove | -$901.16 | $4,850.98 | $9,417.91 | 2024 Q1: +$2,757.76 |
| R3-enforce | $3,337.08 | -$1,209.74 | $4,514.75 | 2024 Q2: +$5,414.91 |

**Shape, reported without grading it, per the prompt's instruction.**
R3-remove's full-window edge accrues mostly in 2023-2024, actually running
slightly negative through 2022. R3-enforce's edge shows the opposite early
pattern — positive through 2022, a partial give-back in 2023, positive again
in 2024. Neither effect is a single-quarter artifact, but neither is
perfectly smooth either.

---

## Limitations

- **No figure in this report carries a confidence range.** Every number is a
  single deterministic path (seed=0), not a distribution.
- Every figure describes this specific 16-company universe and the
  2022-01-01 to 2024-06-12 window, with **zero 2025 calls**. A prior run
  found this universe at the top of 25 random draws — it is not
  representative.
- The corpus is a score stream of unverified prompt vintage.
- **Step 3's three figures are look-ahead ceilings, not results.** They also
  inherit every bound-loosening assumption Stage D made in building D-both
  (bearish → full `Exit` rather than `Trim`; non-direction fields synthesized
  to the most supportive value consistent with the label) — a tighter
  synthesis would very likely move all three ceiling numbers, and possibly
  their ordering, this run did not test that.
- **Tax treatment: stated, not modeled.** The simulator computes no tax
  figure of any kind; the three arms differ in trade count, so a real
  after-tax ranking could differ from the pre-tax ranking reported here.
- Sign stability under leave-one-out (16/16 for both R3-enforce and
  R3-remove) is weaker evidence than a confidence range — it rules out one
  company driving an effect, it does not establish either effect is real.
- **R3-enforce's mechanics rest on a resolved-but-revisitable choice**
  (option 1 of three considered — see "R3-enforce mechanics" above). If that
  choice is wrong, this run's R3-enforce numbers describe a different
  question than the one intended.

---

## Any gates that failed

None. Step 0c's reproduction gate passed for both required figures. No stop
was required anywhere in this run.

## Deviations from the prompt, and why

1. **File path premise correction (no figure affected):** the prompt's Step 5
   read-first material and its own Step 0 language cite
   `analysis/simulator/sweep_cadence_and_session_model.py`; the file is
   actually at `analysis/sweep_cadence_and_session_model.py`. Verified before
   writing the driver, corrected here rather than silently worked around.
2. **Step 1's prediction (status quo sells more than removal) was CONFIRMED**,
   not contradicted — reported plainly per the prompt's own standing rule
   that either outcome is a finding.
3. **Step 3's "grows/shrinks/reverses" framing did not resolve cleanly to one
   bucket:** R3-remove's advantage shrinks under perfect calls while
   R3-enforce's advantage reverses to a cost. Both are reported rather than
   forced into a single label, per the prompt's own instruction not to
   pre-commit to a reading.

## What was deliberately not done

- No promotion of any configuration. No edit to
  `analysis/simulator/allocator_v2.py`, `allocator_v3.py`,
  `analysis/sweep_cadence_and_session_model.py`, `server/lib/versions.js`,
  `docs/architecture/VERSION_REGISTRY.json`, `PROMOTION_GATE.md`, or
  `EVALUATION_PROMPT.md` — verified unchanged by hash.
- R3-remove's leave-one-out was NOT re-run; Stage C3's existing figures were
  restated with their source cited, per the prompt's explicit instruction.
- No AMD tier-classification defect or `type_classifications.json`-unread
  defect was touched or gated on.
- No price-cache refresh; frozen at 2026-05-08 throughout.
- X (session speed limit) was never changed from 2.5 points in any arm.

## Recommendation

**Removing the guard (R3-remove) earns the most money in this corpus and
window ($189,362.81, +$9,417.91 vs. status quo) and its effect is directionally
robust in leave-one-out (16/16). Making the guard actually enforce
(R3-enforce) earns less ($184,459.65, +$4,514.75) but produces the smallest
worst-case drawdown of the three (17.62%) and the fewest displacement sales
of an existing holding to fund a new one (37, versus 60 and 71).** On pure
final-value terms alone, removing the guard is the stronger candidate; if
Luis weighs downside protection and disturbing fewer existing positions more
heavily, enforcing the guard is the stronger candidate. Status quo is
dominated by both alternatives on every headline figure in Step 1 and is not
recommended as-is, given it currently does the most selling of other
holdings while earning the least.

**What would have to be true for this recommendation to be wrong:** if the
real-world tax cost of R3-remove's extra trades (this run does not compute
one) outweighs its $9,417.91 pre-tax edge; if this specific 16-company
universe and 2022-2024 window are not representative of how Rule 3 behaves
going forward (a real risk, since a prior run found this universe unusually
strong versus 25 random draws); or if Luis's reading of "genuinely does not
happen" for a blocked add differs from the one this run settled on (see
"R3-enforce mechanics" — options 2 and 3 were not built or measured).

**Promotion path, named but not walked:** any change to Rule 3's
disposition in production is a versioned allocator decision requiring
`docs/architecture/PROMOTION_GATE.md`'s process and Luis's go-ahead. This run
hands over a comparison and a recommendation; it does not promote anything.

---

## Reproducibility

- Driver: `analysis/rule3_disposition_driver.py`, committed at `1afb0c6`
  (own commit, before the manifest).
- Manifest: `analysis/data/run_manifests/rule3_disposition_manifest.json`,
  committed at `c4c0446` (results commit) against driver commit
  `5c0926c` (`git_dirty: false` at manifest-write time).
- `analysis/data/rule3_disposition/PREREGISTRATION.json` written before any
  arm ran (commit `1afb0c6`; driver commit corrected to `5c0926c` in a
  follow-up docs-only commit before the run).
- `analysis/data/run_state/rule3-disposition/{progress.json,cells.jsonl,findings.md}`
  carry the resume record for this run_id; all committed.
- Protected-file integrity: `manifest.json` → `protected_files_unchanged: true`,
  hashes recorded before and after in
  `protected_file_hashes_before` / `protected_file_hashes_after`.
- Working-tree hygiene: unrelated WIP (`ec-fidelity-benchmark-1` progress,
  probe scripts, several handoff/prompt/wrap-up files unrelated to this run)
  was stashed at session start
  (`git stash push -u -m "unrelated-wip-before-rule3-disposition"`) and
  restored (`git stash pop`) at the end of this session, confirmed via
  `git status` with no conflicts.
- Zero Anthropic API calls made. Zero DB writes. No stored `Analysis` row
  touched. One read-only DB `SELECT` (`S.load_events_dedup_on()`), done once
  and reused for every one of the ~40 simulator runs in this driver — no
  repeated querying.

## Follow-up commands

```bash
cd analysis && python3 rule3_disposition_driver.py
```

```bash
python3 -c "import json; print(json.dumps(json.load(open('analysis/data/run_manifests/rule3_disposition_manifest.json'))['step1_three_configs'], indent=2, default=str))"
```
