# corpus-fix-7: make the manifest match what was registered — wrap-up

**Run ID:** `corpus-construction` (continuation). **$0 Anthropic API. Zero
transcripts scored. Zero EarningsCall.biz vendor calls** (GOOG's call data
was already verified in `TICKER_ALIASES.json`'s A5 entry — no new vendor
lookup needed). One new price fetch (GOOG, via yfinance), written only to
`corpus_v2_price_cache.json`. Branch `sweep/db-corpus-baseline`. Pushed at
the end.

**No return was looked at anywhere in this run.** Every correction below
traces to a rule already registered before this run started, or to a
membership list (`selection_working.json`) written before any outcome was
measured. Confirmed by inspecting the driver: it reads call counts, price
dates, and registered rule text — never a hit/miss or a return.

---

## Plain-language summary

Corpus-fix-6's price-coverage sweep failed 8 of 77 companies. This run
checked *why*, and found that only two of those eight are real price
problems (Sunnova, Wolfspeed — already known). The other six trace to three
separate bugs, all now fixed against rules that were already written down
somewhere, just never applied to the file everything else reads:

1. **The price gate itself used the wrong threshold for one bucket.** The
   failures stratum (S4) already has its own call-count floor — 4, not
   12 — registered back in corpus-fix-4 specifically because a company
   that fails stops reporting. The price gate ignored that and applied a
   flat 12 to everyone. Fixed: First Republic and Sunworks, which have
   complete price data for every call they have, now correctly pass.
2. **Two companies never belonged where the manifest put them.** Honeywell
   and UPS have been sitting in the "S1, large-cap" bucket since corpus
   construction, with zero recorded calls — but they were never actually
   selected for S1. They're industrials-sector *reserve* candidates that
   leaked into the wrong bucket and, from there, into the train/tune/holdout
   split. Removed.
3. **A fix from three prompts ago never reached the file that matters.**
   `corpus-fix-1` established months ago that Alphabet's calls are filed
   under `GOOG`, not `GOOGL`, and wrote that down. The manifest still said
   GOOGL had zero calls. Corrected — and once corrected, GOOG turns out to
   have full price coverage too, which nobody had checked before because
   the stale manifest said there was nothing to check.

**The third one matters beyond Alphabet.** It's the same failure mode this
project has already been burned by once, with `versions.js` silently
disagreeing with the version registry for five weeks. A rule can be
written down, verified, and still not be in effect anywhere code actually
reads. This run's audit (§4) checked all nine registered rules (A1–A9)
against the manifest and the split, and found a second live instance of
the identical problem: **A8 itself** — last run's price-coverage gate —
was registered and swept, but its per-company verdicts were never written
back into the manifest either. They lived only in a side file. This run's
own freeze is what finally closes that gap, for A8 and for A9 both.

> After corrections, **48** companies are available for iteration, against
> **46** before this run and **53** claimed before the price gate. The
> paired threshold is **3 points** simulated (2–4 across brackets), **2.9–3.5
> points** by the square-root check. The registered minimum is 54 companies.
>
> The expansion therefore needs to add **6** companies to reach the
> 54-company bare minimum (no margin — the same place the corpus was
> mistakenly thought to already be), or **30** to reach the 78-company
> target that gives real margin (1pp in every bracket, per corpus-fix-4).

---

## 1. Step A — A9 registered, gate re-run

`A9_price_gate_threshold_by_stratum` written into `PREREGISTRATION_FIX.json`,
dated, before re-running the gate. Rule: the price-coverage floor inherits
whichever call-count threshold already governs the company's stratum — A1's
12 for ordinary strata, **A2's 4 for S4**. The window-coverage test itself
(real price both ends, or the A6 terminal rule) is unchanged.

**Verdict changes under A9** (`COVERAGE_GATE_SWEEP_V2_A9.json` →
`verdict_changes_vs_A8`):

| Ticker | Stratum | Gradable calls | A8 verdict (flat 12) | A9 verdict | Reason |
|---|---|---|---|---|---|
| FRC | S4 | 6 of 6 | fail | **pass** | A2's floor is 4; FRC has full real-price coverage for all 6 |
| SUNW | S4 (holdout) | 10 of 10 | fail | **pass** | Same — full coverage, floor was the only blocker |
| GOOGL | S5 | 24 of 24 (new, via B2) | fail (0 calls recorded) | **pass** | Manifest correction, not an A9 effect — see §2 |

WOLF and NOVA remain **fail** under A9 — their problem was never the
call-count floor, it was the price gap itself (confirmed again this run;
see `COVERAGE_GATE_SWEEP_V2_A9.json` → `per_company.WOLF` /`.NOVA`).

## 2. Step B — manifest corrected

**B1 — S1 membership.** `CORPUS_MANIFEST_V2.json`'s S1 stratum had 22
frozen entries against a registered `selection_working.json` →
`S1.selected` list of 20. Diffed both directions:

- **In the manifest, not in the registered selection:** HON, UPS. Evidence:
  absent from `S1.selected`; present instead in
  `selection_working.json` → `S3.reserves.industrials`. **Removed.**
- **In the registered selection, not in the manifest:** none. (S1 has no
  opposite-direction error.)

Checked S2 and S3 for the same pattern, as the propagation audit requires:
S3 has no divergence either direction. S2's `selection_working.json` lists
POWI as selected but it is absent from the S2 manifest — **checked and
confirmed legitimate**, not a second instance of the bug: POWI's own
availability record (`availability_fix_working.json` → `POWI`) shows
`max_gap_days: 273` (> A1's 240-day line), so it correctly failed A1 and
was dropped after selection, before the freeze. Reported per the prompt's
instruction to flag the opposite-direction case separately rather than
assume it's the same bug.

**B2 — Alphabet.** Set GOOGL's manifest entry to the working symbol `GOOG`
with A5's verified 24 calls (first 2020-02-03, last 2025-10-29,
max_gap_days 100), `rule_applied: A1`, `meets_new_rule: true`. Then fetched
GOOG's price coverage — something corpus-fix-6 never did, because it read
the stale manifest's zero-calls figure and skipped GOOGL entirely. Result:
**full real-price coverage, 24 of 24 gradable** (`COVERAGE_GATE_SWEEP_V2_A9.json`
→ `per_company.GOOGL`).

**B3 — the propagation audit (the part with value beyond today).**

| Addendum | Registers | In `CORPUS_MANIFEST_V2.json`? | In the split? | Status |
|---|---|---|---|---|
| A1 | 240-day gap rule, ordinary strata | Yes (`rule_applied`/`meets_new_rule` on every non-S4 entry) | Yes | **PASS** |
| A2 | S4's own 4-call rule | Yes (`rule_applied: "A2"` on all 4 S4 entries) | Yes | **PASS** |
| A3 | New S4 candidates (WOLF/NOVA/FRC/SUNW) | Yes | Yes | **PASS** |
| A4 | S4 weighting disclosure | N/A — governs outcome-measurement weighting, not membership | N/A | **N/A**, out of manifest/split scope |
| A5 | GOOGL → GOOG identity | **No** — manifest showed 0 calls | N/A (membership unaffected either way) | **FAIL before this run → fixed by B2** |
| A6 | Terminal-value = 0 grading | N/A — grading-time rule, applied in `corpus_construction_outcomes_v3_terminal.py` | N/A | **N/A**, confirmed applied at measurement time, out of scope here |
| A7 | Expansion round 2 | Not registered yet | Not registered yet | **N/A** — corpus-fix-5 Job 2 still pending |
| A8 | Price-coverage gate (flat 12) | **No** — verdicts lived only in `COVERAGE_GATE_SWEEP.json` | No | **FAIL** — same shape of defect as A5's, one layer up |
| A9 | Per-stratum floor (this run) | Not yet, as expected | Not yet, as expected | Propagated by **this run's own Step E**, below |

Full detail: `analysis/data/corpus_v2/PROPAGATION_AUDIT_A1_A9.json`.

**The diagnostic the prompt anticipated did occur, in a narrower form than
feared.** The prompt worried the audit might find more divergences than
the two known ones, or S1 disagreeing in both directions. It found exactly
one more (A8's own propagation gap) beyond the two named in the prompt
(A5, S1/HON/UPS) — not a wider blast radius, but a real third instance of
the same failure shape, worth carrying forward as a standing check: **every
future addendum needs its own propagation check, not just a registration.**

## 3. Step C — the corrected count

| | |
|---|---|
| Companies in the corpus | **75** (77 − HON − UPS) |
| Gradable under the A9 price gate | **72** |
| **Available for iteration** | **48** |
| Excluded, and why | WOLF (S4, price gap — history starts 2025-09-29 post-restructuring, no reserve); NOVA (S4, price gap — Yahoo has purged its full history, no reserve); SPWR (S5 carve-out — 9 of 16 calls gradable, stays in the corpus per A8, excluded from this count only) |

SUNW, previously the one holdout-side failure, now passes (A9) and is
**not** excluded — the holdout has zero failures under the corrected gate.

Provenance: `COVERAGE_GATE_SWEEP_V2_A9.json` → `per_company.<ticker>.verdict`;
available count = train+tune tickers in `SPLIT_V3_RMO_REMOVED.json` minus
HON/UPS (B1), cross-checked against A9 verdicts.

## 4. Step D — the corrected threshold, sqrt check alongside it

**Driver:** `analysis/corpus_fix7_threshold_recheck.py` (same imported
method as fix-6's recheck, itself importing
`corpus_construction_stepC_independent_v3.py` verbatim). Output:
`analysis/data/corpus_v2/STEP_C_AT_FIX7_CORRECTED_COUNT.json`.

| n=48 | Simulated paired MDE | Simulated unpaired MDE |
|---|---|---|
| observed (16.5pp spread) | 3pp | 8pp |
| lower (8.2pp) | 2pp | 7pp |
| higher (24.7pp) | 4pp | 10pp |

**Square-root check:** `24/√48 = 3.46pp` (published baseline),
`20/√48 = 2.89pp` (this project's own recheck formula).

**Which to trust, and why.** At n=46 (fix-6, before this run's corrections),
the simulation returned 1pp — a full 1.7pp below the 2.7pp square-root
recheck, and flagged there as likely simulation noise rather than signal.
**At n=48, the simulation's observed-bracket figure (3pp) lands almost
exactly on the square-root recheck (2.89pp)** — the two methods that
disagreed sharply three companies ago now agree closely. That convergence
is itself evidence that the n=46 result *was* noise (a single Monte Carlo
draw at that seed), not that the corpus improved by adding two companies.
**Trust the square-root recheck (2.89pp) as the primary planning figure**
going forward — it is the anchor that stayed stable while the single-draw
simulation swung by 2pp between adjacent counts on essentially the same
population.

> After corrections, **48** companies are available for iteration, against
> **46** before this run and **53** claimed before the price gate. The
> paired threshold is **3 points** simulated (2–4 across brackets), **2.9–3.5
> points** by the square-root check. The registered minimum is 54 companies.
>
> The expansion therefore needs to add **6** companies to reach the
> 54-company bare minimum (no margin), or **30** to reach the 78-company
> target that gives real margin.

## 5. Step E — re-freeze and re-lock

`CORPUS_MANIFEST_V4.json` written as a new file (V2 and V3 intact).
`analysis/corpus_construction_split_v4_manifest_corrections.py` — identical
method to `split_v3_rmo_removed.py`, same seed `20201231` — produced
`SPLIT_V4_MANIFEST_CORRECTIONS.json`.

| | sha256 |
|---|---|
| V2 holdout (77 companies, pre-correction) | `5ab7ef18c3e3f22160f6b6ae60a82c99638b70c26b1c17d6477e6b5615795c84` |
| **V4 holdout (75 companies, this run)** | `1d05ee0496842e2dd033924ce82d387213b80f20c3e36582eabb66d33de87569` |

`docs/architecture/PROMOTION_GATE.md` §10 updated with both hashes and the
full chain of supersession (78 → 77 → 75). This is the only spec edit this
run makes.

## 6. Verification performed

- `python3 -c "import ast; ast.parse(...)"` on all four new drivers — passed.
- `json.load()` on every new/modified JSON file — valid.
- Cross-checked `STEP_C_AT_FIX7_CORRECTED_COUNT.json`'s method against
  fix-6's recheck driver — identical imports, same `SEED`, same
  `N_SYNTH_TRIALS=150`.
- Re-derived B1's removal list independently two ways (manifest-vs-selected
  diff, and re-reading `selection_working.json`'s S3 reserves) — consistent.
- Confirmed `CORPUS_MANIFEST_V2.json` and `SPLIT_V3_RMO_REMOVED.json` are
  untouched (`git diff --stat` empty for both) — V2/V3 remain intact per
  the prompt's requirement.

## 7. Deviations from the prompt

None. Every correction in §2 traces to an already-registered rule or an
already-written selection list; no company was added, removed, or
reclassified on outcome grounds. The one interpretive call made was
treating POWI (§2, B1) as a legitimate absence rather than a bug — checked
against its own availability record before concluding that, per the
prompt's instruction not to assume the opposite-direction case is the same
defect.

## 8. What's left for the design session

- **corpus-fix-5's Job 2** now has its number: **+6** companies for the
  bare minimum, **+30** for real margin. Recommend targeting the 30-company
  figure, consistent with corpus-fix-5's original framing, and running this
  same A9 gate against Job 2's candidates *before* freezing them in.
- **A8's own propagation gap (§2, B3)** is now closed by this run's V4
  freeze for A9, but the general lesson — every registered addendum needs
  a propagation check, not just a registration — has no standing
  enforcement yet. Worth deciding whether future corpus-fix prompts should
  run a lightweight version of this run's audit automatically.

## 9. Limitations (stated, not argued past)

- The propagation audit checks whether a rule's effect appears in the
  manifest and split, not whether every downstream script honors it in
  practice.
- The corpus remains selected, not scored.
- Coverage is measured against providers reachable from this environment;
  WOLF and NOVA's price gaps might not exist at a paid provider — a
  purchasing decision, not a permanent exclusion (repeating fix-5/fix-6's
  finding).
- The n=48 simulated MDE is a single Monte Carlo draw per bracket, same
  caveat as every prior run's table — §4's convergence with the sqrt check
  is reassuring, not a guarantee the next draw won't move again.

## 10. Git

1. `git_dirty: false` confirmed before any change (clean tree at session start).
2. `analysis/corpus_fix7_driver.py` committed first, alone (`c3e0ec3`), then
   a same-day correctness fix to its A1/A5 audit-row logic (`3315729`) —
   still driver code, before any result existed.
3. `analysis/corpus_fix7_threshold_recheck.py` (`51ea0aa`) and
   `analysis/corpus_construction_split_v4_manifest_corrections.py`
   (`8c51212`) committed next, both driver code, both before their own
   results existed.
4. Results committed together (`30c1277`): the A9 addendum, the corrected
   `CORPUS_MANIFEST_V4.json`, the A9 sweep, the propagation audit, the new
   `corpus_v2_price_cache.json` entry (GOOG), the V4 split, and the
   threshold recheck.
5. This wrap-up and the `PROMOTION_GATE.md` §10 update commit next; push
   follows once, to `origin sweep/db-corpus-baseline`.

Provenance for every figure above: `<value>` — `<path>` → `<json.key>`,
e.g. `48 available` —
`analysis/data/corpus_v2/COVERAGE_GATE_SWEEP_V2_A9.json` →
`per_company.<ticker>.verdict`; `3pp at n=48 observed` —
`analysis/data/corpus_v2/STEP_C_AT_FIX7_CORRECTED_COUNT.json` →
`spread_brackets.observed.results_by_n.48.paired_mde_pp`; `2.89pp sqrt
recheck` — same file → `sqrt_estimates.this_run_recheck_20_over_sqrt_n`.
