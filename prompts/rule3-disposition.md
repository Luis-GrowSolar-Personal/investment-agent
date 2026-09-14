# Rule 3 disposition — remove the guard, or make it actually guard?

**Run ID:** `rule3-disposition`
**Cost:** **$0 in Anthropic API spend.** Hard constraint, not a target.
**Branch:** `sweep/db-corpus-baseline`. No merge to `dev`. **No promotion.**
**Wrap-up:** `wrap-ups/rule3-disposition-out.md`

**Read first:** `wrap-ups/value-attribution-v2-stage-c3-out.md` (Step 2, where
Rule 3's effect and its real mechanism were found) and
`wrap-ups/value-attribution-v2-stage-d-out.md` (the ceiling, and why the session
speed limit must not be raised).

---

## 1. Why this run exists

Stage C3 measured the four allocator rules. Two do nothing at all. One is worth
$813 and flips sign when NVDA is dropped. **Rule 3 — "don't buy more of a
speculative stock trading below your average cost" — costs $9,417.91.** Turning
it off takes the system from $179,944.91 to $189,362.81, and that effect held
its sign in all 16 tests that each dropped one company.

But confirming Rule 3's code location surfaced something that changes what the
decision even is. `analysis/simulator/allocator_v2.py` lines 143-147:

```python
if tier == "speculative":
    cb = _weighted_cost_basis(portfolio, ticker)
    if cb is not None and day_price < cb:
        return []  # don't average down on speculative losers
```

Under the settled `swap_funding` / `pooled` path, when that clause returns `[]`,
the session driver's shortfall logic (`sweep_cadence_and_session_model.py`
~866-877) sizes the target from `recommended_size` and the type cap — it never
reads cost basis — treats the entire target as unfunded, and **funds it anyway
by selling another held position.**

**So Rule 3 does not currently prevent averaging down. It only changes how the
purchase is paid for: by displacing another holding instead of from cash.**

That makes this a three-way decision, not a two-way one:

| Option | What it means |
|---|---|
| **Keep it** | Status quo. The guard is written but does not guard, and costs $9,417.91. |
| **Remove it** | Delete the guard. Speculative adds fund normally from cash. |
| **Enforce it** | Make the guard real — a blocked add is genuinely skipped, not re-funded by displacement. |

Nobody has measured the third option. It is the one that matches what the rule
was written to do.

**This run measures all three and proposes. It does not promote.** Changing the
allocator is a versioned decision for Luis.

---

## 2. Absolute constraints

1. **ZERO Anthropic API calls.** Every arm replays the simulator over stored
   scores. If a step appears to need a model call, **stop and report it**.
   Assert this in the run log before the first arm.
2. **Do not modify any stored `Analysis` row.** No DB writes.
3. **No promotion, no production edit.** `analysis/simulator/allocator_v2.py`,
   `allocator_v3.py`, `server/lib/versions.js`,
   `docs/architecture/VERSION_REGISTRY.json`, `PROMOTION_GATE.md`,
   `EVALUATION_PROMPT.md` and the production prompt are **all untouched**. Every
   configuration in this run is a monkeypatch inside the driver, restored after
   each arm.
4. **Do not change the session speed limit.** X stays at 2.5 points in every
   arm. Stage D found that raising X makes the real system **$28,947 worse**;
   this run must not confound Rule 3's effect with that.
5. **No price-cache refresh.** Frozen at 2026-05-08.
6. **Environment: macOS Tahoe, zsh.** `python3`, `pip3` / `python3 -m pip`.
   Never `--break-system-packages`. No `apt`. No `watch`.
7. **Do not fix known defects in passing** (AMD tier classification;
   `type_classifications.json` unread by production). **Do not gate on either.**
8. **Locked population.** The 195-event simulator population frozen in
   `PREREGISTRATION.json`, settled configuration otherwise (`swap_funding`,
   K=30, `new_calls_only`, X=2.5, `pooled`, `per_event_date`).

---

## 3. Step −1 — resume protocol

`run_id` = `rule3-disposition`. State in
`analysis/data/run_state/rule3-disposition/`, un-ignored in `.gitignore` and
committed. **Write `progress.json` as the very first action**, before reading
anything: `prompt_sha256`, `driver_commit`, per-step status, one-sentence
`next_action`, `notes[]`. `cells.jsonl` flushed per arm; `findings.md`
append-only.

**Stopping is permitted only after Step 3 is complete**, not before. Steps 1
through 3 are roughly 22 simulator runs and none is expensive.

---

## 4. Step 0 — hygiene, pre-registration, reproduction

**0a.** Clean tree; hard stop if `git_dirty` cannot be recorded `false`. Driver
committed before any manifest, as its own commit.

**0b. Pre-register before any arm runs.** Write
`analysis/data/rule3_disposition/PREREGISTRATION.json` with all three
configurations' exact mechanics, the locked population, the leave-one-out
design, and a fixed seed. Abort on mismatch if it exists with different content.

**The "enforce it" arm's mechanics must be stated precisely and are the one
place this run could go wrong.** Make the blocked add genuinely not happen: the
shortfall path must not treat a Rule-3 refusal as an unfunded target to be
covered by displacement. **If there is more than one defensible way to wire
that, report the ambiguity and pick none** — do not resolve it silently. Say
what each option would mean.

**0c. Reproduce before measuring.** Re-run the control and the
Rule-3-off arm and confirm **$179,944.91** and **$189,362.81** to the cent.
**If either disagrees, stop and report** — the discrepancy takes priority over
everything else in this run.

---

## 5. Step 1 — the three configurations

All at X=2.5, settled configuration otherwise.

| Arm | Rule 3 | Displacement funding for blocked adds |
|---|---|---|
| **R3-keep** (control) | on | allowed (status quo) |
| **R3-remove** | off | n/a — nothing is blocked |
| **R3-enforce** | on | **suppressed** — a blocked add does not happen |

For each arm report:

- final value, and the difference against the control and against buy-and-hold
  ($195,584.28);
- **maximum peak-to-trough decline**, in dollars and percent, with its date
  range. Buying more of losing positions is the obvious risk of removing the
  guard; measure it rather than assuming;
- average cash share and dollar-years invested;
- **trade counts** — total buys, total sells, and specifically **how many sells
  were displacement-funded**. Stage C3's finding predicts the status quo does
  *more* selling than removing the guard, because refusals trigger displacement.
  Confirm or contradict that directly;
- what binds each funding event (session limit, type cap, cash available,
  target gap), as a share.

**Does the simulator model tax at all?** State plainly whether these figures are
before or after tax. If before, say so and note that the three arms differ in
trade count, so their real-world after-tax ranking may differ from this one.
Do not estimate a tax figure — just flag the exposure.

---

## 6. Step 2 — does each effect survive dropping any single company?

For **R3-enforce**, re-run 16 times, each dropping one of the 16 companies from
the universe entirely. Compute each effect against the control **run in the same
reduced universe**, not against the full-universe control.

Report the effect per company dropped, how many of the 16 preserve the sign, and
which company's removal changes the effect most.

R3-remove's leave-one-out already exists from Stage C3 (16/16 sign preserved,
ENVX the largest mover). **Restate it beside the new figures; do not re-run it.**

State plainly that sign stability is **weaker evidence than a confidence range**
— it shows an effect is not the work of one company; it does not establish the
effect is real.

---

## 7. Step 3 — would a better analyst change the answer?

Three runs: each configuration under the **perfect-analyst labels from Stage D**
(`D-both`, injected at `per_call_rec`, same pre-registered synthesis), at X=2.5.

**Label every figure in this step a look-ahead ceiling, not a result.**

The question: is Rule 3 costing money *because the calls are poor*, or
regardless? A guard against buying into losers should matter more when the
analyst is wrong and less when it is right — or the reverse, if the losers it
blocks are the ones that recover.

- If Rule 3's cost **grows** under perfect calls, the guard is blocking genuinely
  good purchases and removing it is right independent of analyst quality.
- If its cost **shrinks or reverses**, the guard is partly protecting the system
  from its own bad calls, and removing it becomes a bet on the analyst improving
  — which Stage D says has real headroom but no near-term measurability.

**Do not pre-commit to either reading.** Report the three numbers.

---

## 8. Step 4 — where in time does the difference come from?

For R3-remove and R3-enforce against the control, report the difference **by
calendar year** across the window, and name the single largest contributing
quarter with its dollar amount.

A $9,417.91 effect concentrated in one quarter of 2022 is a fragile basis for a
permanent configuration change. One spread evenly across the window is not.
**Report the shape; do not grade it.**

---

## 9. Step 5 — the report

**Scope boundary: report and propose, do not decide.** This run does not promote
a configuration. It hands Luis a comparison and a recommendation he can act on.

Open with a **§0 defined-terms table**, then a **plain-language summary**, both
written to the project instructions' language rules: no statistics vocabulary
without a one-line plain definition, every percentage anchored to what it is a
percentage of, every arm described by what it actually buys and sells the first
time it appears, short sentences, "points" not "pp".

Lead with these sentences, filled in:

> Leaving the guard as it is returns **$179,944.91**. Removing it returns
> **$______**. Making it actually block the purchase returns **$______**. The
> worst peak-to-trough falls are **____%**, **____%** and **____%**. Of the
> three, the one that earns most is **______**, and the one that loses least in
> a downturn is **______**.

Then: Step 0c's reproduction check, Step 1's three-way table, Step 2's
single-company robustness, Step 3's look-ahead ceilings, Step 4's timing.

Close with a short **recommendation section** naming which option you would put
forward and what would have to be true for it to be wrong. **Name the
promotion path but do not walk it** — any change here is a versioned allocator
decision requiring `PROMOTION_GATE.md`'s process and Luis's go-ahead.

**Limitations to state, not argue past:**

- **No figure here carries a confidence range.** Single deterministic paths.
- Every figure describes this 16-company universe and this window, 2020 through
  mid-2024, with **zero 2025 calls**. A prior run found this universe at the top
  of 25 random draws.
- The corpus is a score stream of unverified prompt vintage.
- Step 3's figures assume perfect foresight and are ceilings, not results.
- Tax treatment as found in Step 1 — state it, do not model it.

---

## 10. Standing rules

- `python3`, zsh, macOS Tahoe. No cache refresh. Branch
  `sweep/db-corpus-baseline`; no merge to `dev`; no push.
- **Provenance for every figure.** `<value>` — `<manifest path>` →
  `<json.key>`, and name the kind of number.
- Record every arm's `config_hash` and seed.
- Driver committed before any manifest, as its own commit. Stage-specific files
  only — no `git add .` or `git add -A`.
- **A diagnostic that contradicts an expectation stated in this prompt is a
  finding, not a reason to stop.** The most likely: Step 1's prediction that the
  status quo does more selling than removing the guard.
- **Note anything contradicting this prompt's premises.** It was written from
  Stages C3 and D; the repo outranks it.
