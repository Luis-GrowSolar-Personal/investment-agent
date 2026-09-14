# Value Attribution and Headroom — Step 0 gate FAILED, run stopped

**Run ID:** `value-attribution-and-headroom`
**Result:** Step 0's gate (0c) fails. Per the prompt's own instruction ("A clean
stop at Step 0 is a successful run of this prompt"), Steps 1–6 were not run.
No pre-registration file was written (0d is conditioned on the gate passing).
**Anthropic API calls made: zero.** DB writes made: zero. All queries below are
read-only `SELECT`s against the existing corpus, run from a throwaway script
outside the repo (`/tmp`, not committed — nothing needed committing, since no
arm ran and no driver was written).

**Git state:** branch `sweep/db-corpus-baseline`, commit `c122a79`, tree clean
for this task (two unrelated untracked files present —
`docs/handoffs/2026-09-13-next-session-opening-prompt.md` and this prompt file
itself — neither touched or staged). The pre-existing unrelated dirty state
(`analysis/data/run_state/ec-fidelity-benchmark-1/progress.json`,
`analysis/ec_fidelity_benchmark_1/probe_google_cslr.py`,
`analysis/ec_fidelity_benchmark_1/verify_alias_and_gate.py`,
`docs/handoffs/2026-09-13-analyst-value-question.md`,
`prompts/domain-midcap-universe.md`) was stashed before this run
(`git stash push -u -m "unrelated-wip-before-value-attribution-run"`) and is
restored (`git stash pop`) at the end of this session.

---

## 0a — is the Test 2 baseline a fixed strategy or realized-outcome-derived?

**Answer: fixed strategy — "always predict bullish."** Confirmed by reading
`analysis/analyst_direct_scorer.py`.

The ground truth for each call is computed from forward benchmark-relative
return (lines 199–207):

```python
if rel > DEAD_BAND:
    ground_truth = "bullish"
elif rel < -DEAD_BAND:
    ground_truth = "bearish"
else:
    ground_truth = "neutral"

hit = (predicted == ground_truth)
always_bullish_hit = (ground_truth == "bullish")
```

`always_bullish_hit` never looks at `predicted` — it is `True` exactly when the
*outcome* happened to be bullish, which is exactly what "the baseline predicts
bullish on every call" means (module docstring, line 18: `Always-bullish
baseline: predicts "bullish" on every call`). The baseline's hit rate is not
computed from a modeled outcome distribution; it is the fraction of calls that
happened to resolve bullish, under a fixed prediction rule you could actually
have run (predict "Add" every time, regardless of the transcript). `base_rate`
is then just `base_hits / len(scoreable)` (lines 243–245).

This satisfies 0a's condition for proceeding: the baseline is a fixed
strategy, so Test 2's −5.8pp aggregate lift is a real comparison against an
alternative strategy, not a descriptive residual. **0a passes.**

## 0b — provenance of the corpus scored in Test 2

**Answer: not confirmed — inferred, and the inference is ambiguous enough to
fail the gate.**

Test 2's own query (`analysis/test2_look_ahead.py`, `fetch_analysis_rows()`)
selects `a."promptVersion"` from every `Analysis` row. Re-running that exact
function plus `score_rows()`/`ALL16` filtering (read-only, no modification)
against the live DB:

```
total scoreable rows (ALL16, price-scoreable): 362
by year: 2020: 3, 2021: 45, 2022: 56, 2023: 60, 2024: 84, 2025: 114
  (2021–2025 sum to 359 — the 2020 n=3 year is below the n_scoreable<20
  thin-year threshold test2 uses and is simply not one of the 5 rows in its
  by-year table; this is consistent with the prompt's "359 calls" claim,
  not a contradiction)

prompt_version breakdown among these 362 rows: {None: 362}
```

**Every single one of the 362 rows has `promptVersion = NULL`.** There is no
stamped column value to confirm provenance from — 0b's "confirmed" branch is
unavailable, exactly as `PROMOTION_GATE.md` §8 warned. This matches the
project's own documented explanation
(`docs/handoffs/2026-09-03-prompt-version-drift.md` line 64): the bulk-loader
`analysis/rebackfill_v6_analyses.py` inserted the corpus before the
`add_version_columns` migration existed, so "its output is v6 *by construction
of its input source* — but the DB rows themselves carry no proof of that,
which is exactly why it remains circumstantial."

So provenance must be **inferred** from `createdAt`, per 0b's fallback
instruction, against the window used throughout `analysis/`:

```
analysis_created_after  = "2026-05-02 12:33:23-04"   (commit 22d2c71 — EVALUATION_PROMPT.md declares v6)
analysis_created_before = "2026-06-27 16:26:16-04"   (commit 7063465 — last commit before content drift)
```

Querying `createdAt` for the same 362 rows:

```
min createdAt: 2026-04-06 12:22:59.678000+00:00
max createdAt: 2026-05-10 22:58:30.759000+00:00

inside the v6 window (>= 2026-05-02 12:33:23-04, < 2026-06-27 16:26:16-04): 209 rows
outside the v6 window (before 2026-05-02 12:33:23-04):                     153 rows  (42.3%)
```

**153 of 362 rows (42.3%) were created *before* the commit that put the v6
prompt live**, i.e. before the timestamp the project uses everywhere else as
the start of the clean v6 window. This is not a rounding-edge case — it's over
five weeks of createdAt values (2026-04-06 to 2026-05-02) sitting entirely
outside the window, contributing more than 40% of the very corpus Test 2's
lift figure was computed over. Whatever scored those 153 rows predates the
`22d2c71` commit and cannot be asserted to be v6 on the window-inference logic
this project otherwise relies on.

**State plainly, as 0b requires: provenance is INFERRED, not confirmed, and
the inference is ambiguous** — the corpus is not cleanly inside the v6 window;
it is a mix straddling the window boundary, roughly 58% inside / 42% outside.

## 0c — GATE

0a passes. 0b fails ("ambiguous" branch — ~42% of the scored corpus falls
outside the window that is supposed to establish "these rows are v6"). Per the
prompt's own instruction:

> If either check fails or is ambiguous — stop here. Write the wrap-up with
> Step 0's findings only, and state explicitly what redesign the failure
> implies. Do not proceed to Steps 1–6 on a broken premise.

**This run stops here.** Steps 0d and 1–6 were not executed. No
`PREREGISTRATION.json` was written (0d is downstream of a passing gate). No
arms were run, no shuffle, no oracle construction, no sweep search.

---

## What the failure means, and what redesign it implies

Test 2's headline claim — "v6 underperforms its own always-bullish baseline by
roughly −5.8pp, aggregated across 359 calls" — **rests on a corpus that is not
demonstrably all v6.** Close to half the rows (153/362) were created over a month
before v6 went live by the project's own dating convention. Two live
possibilities, and this run cannot distinguish them without more evidence:

1. The pre-05-02 rows really were scored under an earlier prompt iteration
   (the header says v6 is "stable best after v5→v8 iteration" — so v5, v7, or
   an unstable pre-v6 v8 draft are all candidates), in which case Test 2's
   −5.8pp figure is not a clean "v6 vs. baseline" comparison at all — it's a
   mixed-vintage comparison, and the −5.8pp attributed to "the production
   analyst" partly describes prompts that were never promoted.
2. The pre-05-02 rows are in fact v6 output, just inserted by a bulk job that
   ran before the window's start timestamp for reasons unrelated to prompt
   content (e.g. the backfill script itself predates the commit that merely
   *documents* v6 in `EVALUATION_PROMPT.md`'s header, even though the prompt
   text scored against was already v6 in substance). This is plausible but
   is exactly the kind of claim `CLAUDE.md`'s version-truth section warns
   against inferring from a content header or a script's commit date.

**This run cannot settle which. That is precisely the ambiguity 0c is
designed to catch, and it is why the prompt gates on it rather than letting a
downstream step quietly average over both populations.**

What a redesign session needs before this test (or anything built on Test 2's
lift figure) can proceed:

- **Split the 362-row corpus by createdAt into the two populations** (before
  vs. at/after `2026-05-02 12:33:23-04`) and check whether their *content*
  differs — e.g. diff a sample of `rawOutput` against the v5 and v6 prompt
  text, or check for structured-score fields that only exist in later prompt
  versions (`thesisDelta`, `freshMoneyAllocation`, etc., added in
  `add_structured_score_fields` — a migration-date cross-check could bound
  which rows *could* have those fields populated and cross-reference against
  which actually do).
- **Re-run Test 2's by-year table restricted to the inside-window 209 rows
  only**, to see whether the −5.8pp aggregate lift and the bearish-accuracy
  range (8.3%–24.0%) survive on a population whose v6 provenance is at least
  timestamp-consistent. If the sub-corpus is too thin per-year (some years may
  drop under the n<20 thin-year threshold test2 itself uses), that itself is a
  finding worth stating rather than working around.
- Until that split is done, **Test 2's −5.8pp figure should be treated as
  provisional**, not as settled fact that this test (or any other) can build
  an apportionment on. This wrap-up does not correct that figure — it flags
  that its provenance is weaker than the number's confident presentation in
  this prompt implied, and that a downstream design decision ("where should
  development effort go — analyst or allocator") should not be made on it
  without the split above.

**This is a genuinely new finding, not a restatement of the known unfixed
defects the prompt told this run not to re-litigate** (AMD tier
misclassification, `type_classifications.json` not read by prod) — those are
unrelated and were not touched.

---

## Deviations from the prompt, and why

- **Step 0's read-only DB check was written to a throwaway script under
  `/tmp`**, not under `analysis/`, and was not committed. The prompt's
  reproducibility section (Step 6 of the execute-prompt skill / `CLAUDE.md`
  §10b) requires committing driver code *before* a manifest — but that
  applies to arms that produce citable results. Step 0 is verification against
  the gate, produces no manifest, and the prompt's own Step 0 doesn't ask for
  a committed driver — only 0d's pre-registration (never reached) does. If a
  future session wants this exact 0b query preserved and reproducible, it
  should be promoted into `analysis/` and committed as its own change; it is
  reproduced in full below so it isn't lost.
- **No `PREREGISTRATION.json`, no arm code, no manifests** — correct per the
  gate, not an omission.
- Everything else in "Absolute constraints" (zero API calls, no DB writes, no
  modification of `versions.js`/`EVALUATION_PROMPT.md`/`VERSION_REGISTRY.json`,
  firewall) was never at risk since Steps 1–5 never ran.

## What was deliberately not done

- Steps 1 (§3.1-vs-dollars 2×2), 2 (shuffle permutation), 3 (allocator-rule
  arms), 4 (oracle ceiling), 5 (allocator ceiling), 6 (the deliverable table)
  — all skipped per the gate. None of Test 1's ($120,800 floor / $179,944.91
  actual) or Test 2's other findings were re-verified beyond what 0a/0b
  needed.
- Did not attempt to repair or reduce the 42% out-of-window figure by
  re-slicing the corpus myself — that is a design decision (which population
  is "the" v6 corpus) that belongs to a design session, not this run.

## Reproduction — the exact query behind 0b

```python
import sys, json
sys.path.insert(0, "analysis")
from test2_look_ahead import fetch_analysis_rows, score_rows, ALL16
from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH, FORWARD_DAYS
from datetime import date, timedelta, datetime, timezone

rows = fetch_analysis_rows()
prices = PriceCache(PRICE_CACHE_PATH)
raw = json.loads(PRICE_CACHE_PATH.read_text())
last_price_date = max(raw["SPY"].keys())
cutoff = date.fromisoformat(last_price_date) - timedelta(days=FORWARD_DAYS)
scored_all16 = score_rows(rows, prices, cutoff, tickers_filter=ALL16)
scoreable = [r for r in scored_all16 if r["scoreable"]]   # 362 rows

win_after  = datetime.fromisoformat("2026-05-02 12:33:23-04:00")
win_before = datetime.fromisoformat("2026-06-27 16:26:16-04:00")
def ca(r):
    c = r["created_at"]
    return c if c.tzinfo else c.replace(tzinfo=timezone.utc)

inside  = [r for r in scoreable if win_after <= ca(r) < win_before]   # 209
outside = [r for r in scoreable if not (win_after <= ca(r) < win_before)]  # 153
```

Run against `price_cache.json` frozen at 2026-05-11 (no cache refresh
performed), same file Test 2 used. `last_price_date` read from the cache was
`2026-05-08`, giving `cutoff = 2025-11-07` — identical logic path to
`test2_look_ahead.py`'s `step_2()`.

## Follow-up commands for a future session

```bash
cd "/Users/luismorales/Library/CloudStorage/Dropbox/My Mac (MacBook-Pro.attlocal.net)/Desktop/investment-agent"
git checkout sweep/db-corpus-baseline
python3 - <<'PY'
import sys, json
sys.path.insert(0, "analysis")
from test2_look_ahead import fetch_analysis_rows, score_rows, ALL16
from analyst_direct_scorer import PriceCache, PRICE_CACHE_PATH, FORWARD_DAYS
from datetime import date, timedelta, datetime, timezone
rows = fetch_analysis_rows()
prices = PriceCache(PRICE_CACHE_PATH)
raw = json.loads(PRICE_CACHE_PATH.read_text())
last_price_date = max(raw["SPY"].keys())
cutoff = date.fromisoformat(last_price_date) - timedelta(days=FORWARD_DAYS)
scored = [r for r in score_rows(rows, prices, cutoff, tickers_filter=ALL16) if r["scoreable"]]
win_after  = datetime.fromisoformat("2026-05-02 12:33:23-04:00")
def ca(r):
    c = r["created_at"]; return c if c.tzinfo else c.replace(tzinfo=timezone.utc)
pre = [r for r in scored if ca(r) < win_after]
post = [r for r in scored if ca(r) >= win_after]
print("pre-window n:", len(pre), "post-window n:", len(post))
# next: diff rawOutput / structured-score-field presence between pre and post
# to determine whether they are genuinely different prompt vintages.
PY
```
