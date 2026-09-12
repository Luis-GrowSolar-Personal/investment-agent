# Test 4 re-run — the noise floor under v6, the prompt that is actually promoted

Read first: `wrap-ups/test4-analyst-noise-floor-out.md` (the original run,
whose numbers this supersedes), `docs/handoffs/2026-09-03-prompt-version-drift.md`,
`wrap-ups/version-registry-and-drift-guards-out.md` and
`wrap-ups/drift-guards-followup-out.md` (the guards this run relies on), and
`PROMOTION_GATE.md` §6 and §11 (the comparison protocol).

**Cost: ~275 Anthropic calls, ~$25 estimated.** User approved. No DB writes.

## Why this re-run exists

The original Test 4 measured the noise floor under **v10+auto1** — a
machine-generated candidate that never passed a gate, ran in production by
accident for five weeks, was rolled back on `dev` on 2026-09-03, and reached
this branch only on 2026-09-12. It is used in **neither production nor the
corpus**. The floors it produced (large 0.0 / mid 0.0 / megacap 3.77 /
small_micro 14.34pp) are correctly marked **STALE** in
`VERSION_REGISTRY.json`.

**The promoted prompt is v6** @ sha256
`357b6b0b8c2f33cc75d519ee9ad0a875ec632bb6dd18487a2a1935498b906e9b`, now
present on this branch. v6 is also the prompt that generated the corpus and
the prompt under which `gate_ledger.json` entry 1's **-7.44pp** regression
was measured.

**So this run does something the original could not: it puts the noise floor
and the regression on the same prompt version.** That removes one of the two
mismatches that made the `sonnet-4-6` HOLD verdict unreadable. The other —
the tier-scope mismatch, since the regression was measured on
overwhelmingly small/micro names — **remains, and this run does not fix it.**
Say so plainly in the report.

---

## Step −1 — resume protocol

`run_id` **`test4-analyst-noise-floor-v6`**. Real spend: checkpoint after
every transcript's 5 runs. Persist each run individually as it returns
(atomic temp-file + rename), enumerate what exists on start and skip it, and
on a spend/quota rejection **stop cleanly** with the resume command rather
than retrying into the wall. Track calls and tokens per invocation and
cumulatively.

## Step 0 — hygiene, and protect the prior run's output

Clean tree (a concurrent session's `ec-fidelity-benchmark-1` files may be
dirty — do not touch them; record and proceed). Driver committed before any
manifest.

**`RUN_ID` (line ~42) and `OUT_DIR` (line ~49) in
`analysis/test4_noise_floor.py` are hardcoded.** A naive re-run would
overwrite `analysis/test4_noise_floor/raw/` — which is **Test 6's control
arm** and this run's own comparison baseline.

Parameterize them (argparse or env, your choice) rather than copying the
driver, so one driver serves both arms and there is no forked logic to
drift. New outputs go to `analysis/test4_noise_floor_v6/`. **Assert at
startup that the original `analysis/test4_noise_floor/raw/` still holds its
50 files and is not writable by this run.** Report the assertion.

## Step 1 — reuse the identical sample; do NOT redraw

Read the 50 drawn transcripts from
`analysis/data/run_state/test4-analyst-noise-floor/sample.json` (seed 40;
megacap 13, large 13, mid 12, small_micro 12).

This is not convenience. Per `PROMOTION_GATE.md` §11.6, **a noise floor is
sample-scoped** — it transfers only to runs on the identical transcripts.
Reusing the sample is what makes the v6 floors directly comparable to the
v10+auto1 floors, and it is the same reason Test 6 was built as a paired
reuse. A fresh draw would produce a number comparable to nothing.

Verify the sample loads intact (50 rows, the tier counts above) before
spending anything.

## Step 2 — model-drift check FIRST (25 calls), using the candidate hatch

The original Test 4 ran 2026-09-05/06. It is now ~a week later, and
`MODEL_VERSION` is a **bare, undated alias** (`claude-sonnet-4-6`). If
Anthropic has changed what that alias resolves to, a v6-vs-v10+auto1
difference would be **model drift wearing a prompt costume**.

Before the v6 arm, re-score **5 transcripts (one per tier, plus one extra
megacap — name them) × 5 runs** with **v10+auto1**, via the registered
candidate hatch the drift-guards work built:

```zsh
PROMPT_CANDIDATE=v10+auto1 python3 analysis/test4_noise_floor.py ...
```

Compare against the original run's saved output for those same transcripts
(set of `recommendation` values across the 5 runs, and field stability),
exactly as Test 6's replication check did.

- **Reproduces** → the alias has not drifted; any v6-vs-v10+auto1 difference
  is attributable to the prompt. Proceed.
- **Does not reproduce** → **proceed with the v6 arm anyway** (the v6 floor
  is worth having on its own), but **mark the v6-vs-v10+auto1 comparison in
  Step 4 as confounded and do not report a prompt-attributable delta.**

This also exercises the candidate hatch in anger for the first time. Report
whether it behaved as specified — the row/output must record `v10+auto1`,
not the promoted version.

## Step 3 — the v6 arm (250 calls)

50 transcripts × 5 runs, temperature 0, no portfolio context,
single-transcript evaluation (firewall-consistent). Prompt:
`docs/EVALUATION_PROMPT.md` exactly as found — **the harness guard must pass
on the promoted v6 hash with no `PROMPT_CANDIDATE` set.** Report the header
string and hash it asserted against. No DB writes.

**Issue each transcript's 5 runs concurrently** — independent calls at
temperature 0, so parallelism cannot change a result. Serial cost ~6-7
min/transcript (~5-6 hours); 5-way concurrency should land near 60-75
minutes. Parallelize *within* a transcript only, never across transcripts
(three OS low-memory kills hit the original Test 4 run and three more hit
Test 6). Fall back to serial on any rate-limit response and say so.

**State explicitly in the wrap-up whether concurrency was implemented, and
if not, why.** The two previous prompts that specified it were both silently
ignored by their drivers; this is not a rhetorical request.

## Step 4 — results, and the three comparisons that matter

Compute per-tier hit-rate noise floors using
`analysis/analyst_direct_scorer.py`'s own constants (import, do not
reimplement) — identical methodology to the original Step 4.

Report:

**(a) The v6 floors, per tier** — std and range in pp, and the primary
4-field instability count out of 200, and recommendation flips out of 50 by
tier. These are the real numbers; everything else is context.

**(b) v6 vs v10+auto1, paired on identical transcripts.** Side by side:
per-tier floors, 4-field instability (v10+auto1 was 19.5%), recommendation
flips (v10+auto1: megacap 2/13, large 0/13, mid 1/12, small_micro 8/12).

**This is informative but it is NOT a §2.2a gate** — 50 transcripts is not a
full-sample comparison, there is no holdout, and no forward-return
regression is computed. **Do not present it as a gate result, do not open a
`gate_ledger.json` entry, and do not recommend promoting or condemning
v10+auto1 on the strength of it.** Say in the report that the §2.2a gate for
every prompt version from v7 onward still has never been run.

**(c) v6 here vs v6's historical figure.** `MODEL_SELECTION_BENCHMARK_SPEC.md`
records v6 at **18/84 (21.4%)** unstable — but ENPH-only, 3 runs, and on
whichever model was live in July. This run is the first measurement of v6's
stability on the actual portfolio corpus at 5 runs. Compare, and name every
axis on which the two differ so the comparison is not over-read.

## Step 5 — the gate reading, with one mismatch resolved and one not

Compare the v6 floors directly against `gate_ledger.json` entry 1
(`delta_pp: -7.44`, `noise_std_pp: 4.2`, verdict HOLD, scoped to ENPH, TTD,
AMPX, ENVX, EOSE, QS, SPWR).

**Now legitimate on the prompt axis:** the regression and the floor are both
v6. State the aggregate reading and the tier-matched reading, as the
original did.

**Still not legitimate on the scope axis:** entry 1's seven tickers are
overwhelmingly small/micro, so the tier-matched floor is the relevant one,
and the run's own champion/challenger arms had **zero paired rows** (n=6
all-`Add` vs n=36 — 09-05 §5.5), which §11.7 says makes a model comparison
confounded rather than weak.

**Report, do not adjudicate.** Do not re-run or amend the model gate. State
plainly what would settle it: the paired champion-vs-challenger re-scoring,
now additionally requiring that the prompt version be pinned, not just the
model.

## Step 6 — update the registry

Add a `benchmarks` record for the v6 floors: figures, the artifact versions
**and hashes** in effect, the corpus window, the sample identity (seed 40,
the 50 transcripts), and `valid_while`.

**Leave the v10+auto1 records in place and still marked stale** — per this
project's standing rule, a corrected figure supersedes the old one
explicitly and never replaces it quietly. Confirm `whats_live.py` still
exits 0 afterward and reports the new record.

---

## Report

Scope boundary: **report, do not decide.** No amendment to
`EVALUATION_PROMPT.md`, `versions.js`, `PROMOTION_GATE.md` or
`gate_ledger.json`. No merge to `dev`. Do not modify
`analysis/test4_noise_floor/` or `analysis/test6_look_ahead/`.

Open with resume status, then:

> **Prompt asserted: v6 @ [hash] (guard passed, no candidate set). Original
> v10+auto1 output intact: [50 files, unmodified]. Model-drift check (25
> calls, PROMPT_CANDIDATE=v10+auto1): [reproduces / DOES NOT — comparison
> marked confounded]; candidate hatch [behaved as specified]. **v6 per-tier
> noise floor: large [X]pp, mid [X]pp, megacap [X]pp, small/micro [X]pp**
> (std; ranges [...]). Primary 4-field instability [N]/200 ([X]%) — compare
> v10+auto1 19.5%, historical ENPH-only v6 21.4%. Recommendation flips
> [N]/50 by tier [...]. vs v10+auto1 paired: [summary] — **informative, not
> a §2.2a gate.** Gate reading vs -7.44pp: aggregate [exceeds / does not],
> tier-matched [exceeds / does not]; prompt-version mismatch **resolved**,
> scope mismatch **remains**. Concurrency: [5-way implemented / serial,
> reason]. Registry updated, whats_live.py exit [0]. Tokens [N] over [N]
> calls, ~$[X], [N] invocation(s), wall clock [N] min.**

Flag plainly: any tier whose v6 floor differs materially from its v10+auto1
value (either direction); whether small/micro remains the dominant noise
source; any transcript with a 3+ way recommendation split; and anything the
model-drift check revealed about the bare-alias risk.

## Standing rules

- `python3` / `pip3`, zsh-compatible, no `--break-system-packages`, no Linux
  package managers.
- **No DB writes at all.** `SELECT` only for forward-return lookups.
- Do not modify `docs/EVALUATION_PROMPT.md`.
- Work on `sweep/db-corpus-baseline`. Do not commit to `dev` or `main`.
- Every figure names its provenance. Every drawdown, if any, names its ruler.
- Do not write new handoff docs. This prompt in, one wrap-up out.
