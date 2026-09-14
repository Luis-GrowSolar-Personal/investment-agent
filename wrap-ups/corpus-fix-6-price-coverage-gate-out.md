# corpus-fix-6: price coverage as an inclusion gate — wrap-up

**Run ID:** `corpus-construction` (continuation). **$0 Anthropic API. Zero
transcripts scored. Zero EarningsCall.biz vendor calls.** All price data via
yfinance/Yahoo (the free provider already used in corpus-fix-5) plus the
already-frozen `price_cache.json` where a ticker was already there. Branch
`sweep/db-corpus-baseline`. Pushed at the end.

**No return was looked at anywhere in this run** — only whether price data
exists on the right dates, never what it says. Confirmed by inspecting the
driver: it never computes a return or a hit/miss, only date-range coverage.

---

## Plain-language summary

Corpus construction checked that earnings calls exist for every company. It
never checked that stock prices exist too — and two companies (Sunnova,
Wolfspeed) already showed that gap can be large. This run made price
coverage its own pass/fail rule, exactly like the call-availability rule,
and swept all 77 companies against it before looking at any outcome.

**The result is worse than the two known cases suggested.** Eight of 77
companies fail, not two — but six of those eight fail for reasons that have
nothing to do with the price gaps this run was designed to catch:

- **A real corpus-bookkeeping bug, found by this run's sweep.** Two
  companies sitting in the corpus's "S1, large-cap" bucket with zero
  recorded earnings calls — Honeywell (HON) and UPS — turn out to be
  **industrials-sector reserve candidates that were never real S1 members
  in the first place** (see §3). They have plenty of price data; the
  problem is upstream of this run entirely.
- **Two companies in the failures bucket (FRC, SUNW) have perfectly good
  price data for every call they have — they just don't have enough
  calls** (6 and 10) to clear the same 12-call line this gate borrows from
  the ordinary availability rule. That line was set for ordinary
  companies, not for a bucket that exists precisely because its members
  stopped existing early.
- **Two long-standing portfolio names (GOOGL, SPWR)** fail on data grounds
  specific to each — GOOGL's failure is itself another instance of the
  first bug (see §3) — but per the prompt's own carve-out, both stay in the
  corpus; they just don't count toward the number used to size the ruler.

Only **Wolfspeed and Sunnova** fail for the reason this run was actually
built to catch: real, unrecoverable gaps in the price series itself.

**The number that matters:**

> Of 77 companies, **69** are gradable under the price-coverage gate. That
> leaves **46** available for iteration against **53** counted before this
> check. The paired threshold at n=46 is **1–2 points** (bracket-dependent),
> against the **2 points** previously claimed at 54 companies.

**46 is below the previously-registered 54-company bare minimum.** Stated
prominently, per the prompt's own instruction: the corpus-fix-5 Job 2
expansion is no longer optional margin-buying — it is required just to get
back to where the corpus was assumed to already be. See §6.

---

## 1. Step A — the gate, registered first

`A8_price_coverage_gate` written into `PREREGISTRATION_FIX.json`, dated,
before any company was examined. Rule, verbatim intent: a call is gradable
when real prices exist for the company **and** SPY on both the call date
and the close of its 182-day window, **or** the A6 terminal-value rule
applies. A company passes with **≥12 gradable calls**. Identity resolution
order (primary → `TICKER_ALIASES.json` → post-event/predecessor forms)
applied before any company is failed for an identity problem, per the
prompt.

Justification restricted, as required, to the two already-documented
provider failures (Sunnova's purged history, Wolfspeed's 2025-09-29
restructuring cutoff) — no company's return or pass/fail status was
referenced in the addendum. Provenance:
`analysis/data/corpus_v2/PREREGISTRATION_FIX.json` → `A8_price_coverage_gate`.

## 2. Step B — the sweep

**Driver:** `analysis/corpus_fix6_driver.py` (`sweep`). **Full output:**
`analysis/data/corpus_v2/COVERAGE_GATE_SWEEP.json`.

**SPY, checked first as instructed.** A real hole exists: the cached SPY
series (`price_cache.json`, frozen per project standing rules) runs
2020-01-02 → **2026-05-08**, but the corpus's latest calls need coverage
through 2026-06-18. This is the expected consequence of the project's
frozen-cache policy, not a new defect — it costs at most one call each on
16 otherwise-fully-covered companies (their most recent call's window
hasn't closed against cached SPY data yet) and **changes zero verdicts**.
Provenance: `COVERAGE_GATE_SWEEP.json` → `spy.finding`.

**Distribution.** 55 of 77 companies have full coverage (every call
gradable). 16 have exactly one ungradable call each (the SPY-staleness
edge above). 6 companies fail outright. **None of the 69 passing companies
sits within 2 calls of the 12-call line** — the only near-line cases are
the failures themselves (SUNW at 10, two calls short). The gate is not
brittle for the companies that pass it; it is a clean pass/fail split.

**Per-company table — the 8 failures, cause named:**

| Ticker | Stratum | Calls (manifest) | Gradable | Verdict | Cause |
|---|---|---|---|---|---|
| HON | S1 (mislabeled) | 0 | 0 | fail | **Not a real S1 candidate** — see §3 |
| UPS | S1 (mislabeled) | 0 | 0 | fail | **Not a real S1 candidate** — see §3 |
| GOOGL | S5 | 0 (manifest stale) | 0 | fail (carve-out, stays) | Manifest never updated after A5 resolved GOOGL→GOOG (24 calls) — see §3 |
| SPWR | S5 | 16 | 9 | fail (carve-out, stays) | Price series starts partway through the window — first_date after several early call dates |
| WOLF | S4 | 28 | 2 | fail | Confirmed in fix-5: price history starts 2025-09-29 (post-Ch.11 restructuring); 23 of 28 pre-restructuring calls have no price at all |
| NOVA | S4 | 18 | 0 | fail | Confirmed in fix-5: Yahoo has purged NOVA's entire history, no provider recovered it |
| FRC | S4 | 6 | 6 (all real-price) | fail | **Full price coverage** — fails purely on the 12-call line, inherited from ordinary A1, not built for a 4-8 call failures bucket |
| SUNW | S4 (holdout) | 10 | 10 (all real-price) | fail | Same as FRC — full coverage, fails only on the 12-call count |

Full detail (attempts, dates, per-call categorization) in
`COVERAGE_GATE_SWEEP.json` → `per_company.<ticker>`.

## 3. A finding this run wasn't looking for: two corpus-bookkeeping defects

**HON and UPS are not S1 members.** Cross-checking `CORPUS_MANIFEST_V2.json`
against `analysis/data/corpus_v2/selection_working.json` shows HON and UPS
were never in S1's actual 20-ticker selected list (`S1.selected`) — they
are `S3.reserves.industrials` candidates. Somehow both ended up frozen
under the `S1` stratum key with null call data, and from there into
`SPLIT_V3_RMO_REMOVED.json`'s S1 train/tune assignment (22 tickers total —
the real 20 plus these 2), inflating S1's "available" count by 2 companies
that were never legitimately selected for it. This surfaced only because
this run's sweep tried to fetch their calls and found nothing recorded —
**not a price problem**, a stratum-assignment bug. All 20 of S1's real
selected members pass the price gate cleanly (23-24 gradable calls each).

**GOOGL's manifest entry is stale, not broken.** `TICKER_ALIASES.json`'s
`A5_ticker_alias_resolution` addendum (corpus-fix-1) already established
that the vendor keys Alphabet's calls to `GOOG`, not `GOOGL` — 24 calls,
first 2020-02-03, last 2025-10-29, passes A1 cleanly. But
`CORPUS_MANIFEST_V2.json` still shows GOOGL with `n_calls_2020_2025: 0`
and `meets_new_rule: false` — the registered fix was never written back
into the manifest that the split and every downstream measurement actually
reads. This run did not fetch GOOGL/GOOG's price data because the manifest
told it there were no calls to check.

**Neither defect was fixed in this run.** Both are corpus-membership and
manifest-correctness questions, not price-coverage questions — fixing them
changes who's a corpus member, which is exactly the kind of "select, don't
just report" decision this run's scope boundary excludes. Flagged here for
the design session; see §7 for the precise next action.

## 4. Step C — applying the gate

**S5 carve-out, applied as the prompt requires:** GOOGL and SPWR stay in
the corpus (S5 is never dropped) but are excluded from the
available-for-iteration count. Both are in the `train` split segment (not
holdout).

**S4 — no reserve to replace with.** `selection_working.json`'s S4 entry
already records `shortfall_after_reserve: 2` from the original
construction — every candidate found beyond the original six (SIVB, FRC,
WOLF, NOVA, RMO, SUNW) was rejected as out-of-domain or not a 2020
constituent. FRC, NOVA, and WOLF are mechanically dropped from the
available-for-iteration count with **no replacement possible**; SUNW,
sitting in the holdout, fails the same way with no replacement available
either. **This confirms the prompt's own suspicion in reverse — the price
gate makes S4's existing 4-of-8 shortfall categorically worse, not because
of new failures but because two of the four "working" members (FRC, SUNW)
never had enough calls to begin with.**

**HON/UPS — mechanically excluded from the count, not "dropped," pending
§3's resolution.** Since they were never real S1 members, there is nothing
to replace them with as an S1 drop; the correct fix is stratum-membership
cleanup, not gate-driven replacement, and that decision is left to the
design session.

**Terminal-value arithmetic check, as the prompt asked:** confirmed FRC and
SUNW's calls do **not** rely on A6 at all under this gate — every one of
their calls has full real-price coverage on both ends (`counts_by_category`
= 100% `gradable_real_price` for both). They fail purely on count, not on
the terminal-value edge. A6 is not implicated in either failure.

## 5. What changed in the corpus_v2 price cache

`analysis/data/corpus_v2/corpus_v2_price_cache.json` gained fresh
2020-2025 series for every one of the 55 previously-uncached S1/S2/S3/S5
companies (fetched via yfinance, since only 22 of 77 companies had any
entry in either price cache going into this run) — all with full coverage,
which is why the 8 failures above are exactly the ones already flagged by
fix-5 or this run's own bookkeeping check, and nothing else. `price_cache.json`
(the root, frozen file) was not modified.

## 6. Step D — the corrected threshold

**Driver:** `analysis/corpus_fix6_threshold_recheck.py` — imports and reuses
`corpus_construction_stepC_independent_v3.py`'s functions verbatim (same
method fix-4 registered: each synthetic company draws its own accuracy and
its own i.i.d. per-call outcomes; 150 trials, `scorecard_repair_driver.py`'s
unchanged `step3_paired`/`step3_unpaired`). Does not touch or overwrite
fix-4's `STEP_C_INDEPENDENT_THRESHOLD.json`. Output:
`analysis/data/corpus_v2/STEP_C_AT_CORRECTED_COUNT.json`.

| n | observed (16.5pp) paired/unpaired | lower (8.2pp) paired/unpaired | higher (24.7pp) paired/unpaired |
|---|---|---|---|
| **46 (corrected)** | **1 / 9** | **1 / 7** | **2 / 11** |
| 53 (prior count) | 2 / 8 | 2 / 7 | 4 / 9 |
| 54 (registered minimum) | 2 / 7 | 2 / 6 | 2 / 8 |

The n=54 row matches fix-4's registered figures exactly (2/2/2 paired) —
a clean cross-check that this recheck used the identical method.

**Finding, stated plainly rather than smoothed over:** the paired MDE at
n=46 (1-2pp) is nominally as good as or *better* than at n=53 or the
registered n=54. This is **not** evidence that a smaller corpus performs
better — `corpus_construction_stepC_independent_v3.py` seeds each n
independently (`SEED + n`), so each row is a separate single-draw Monte
Carlo estimate, not a smooth curve; fix-4's own wrap-up already flagged
single-trial MDE as "a crude approximation." The honest reading is that
46, 53, and 54 are statistically indistinguishable at this trial count —
all landing in the same 1-2pp paired band — not that fewer companies help.

**The bare-minimum comparison that matters is company count, not MDE
value:** 46 < 54. **The corpus is now below its own previously-registered
minimum for reliable 2-point detection**, regardless of what this
particular simulated draw's MDE says.

> Of 77 companies, **69** are gradable under the price-coverage gate. That
> leaves **46** available for iteration against **53** counted before this
> check. The paired threshold is **1–2 points** (bracket-dependent), against
> the **2 points** previously claimed at 54 companies. **46 is below the
> 54-company bare minimum** — the fix-5 Job 2 expansion is now required, not
> optional margin.

## 7. Step E — re-freeze: deliberately NOT done this run

**Deviation, flagged plainly.** The prompt's Step E says to freeze
`CORPUS_MANIFEST_V4.json` and re-split "only if membership changed." This
run did not execute a mechanical drop-and-freeze, because §3's two
bookkeeping defects (HON/UPS misassigned to S1; GOOGL's stale manifest
entry) mean the *known-clean* membership isn't yet established — freezing
now would either (a) freeze HON/UPS's error into V4 as if they were a
legitimate S1 drop, or (b) require this run to unilaterally decide to
purge them, which is a membership decision the run's scope boundary
("report and propose, do not decide") puts outside this run's authority.
**No `CORPUS_MANIFEST_V4.json` was written. No re-split was run. No
`PROMOTION_GATE.md` §10 edit was made** — correctly, since Step E's edit is
conditioned on a freeze that didn't happen.

**Precise next action:** resolve §3 (confirm whether HON/UPS should be
purged from S1 entirely or backfilled with real S3-reserve replacements,
and whether GOOGL's manifest entry should be corrected to use the
already-registered GOOG alias data), then run a Step-E-only pass: freeze
`CORPUS_MANIFEST_V4.json` off the corrected membership, re-split with seed
`20201231`, re-lock the holdout, update `PROMOTION_GATE.md` §10.

---

## 8. Recommendation to close on

**How many more gradable companies does the expansion need?** At minimum
**8 net gradable-and-available companies** to reach the 54-company bare
minimum (46 → 54); **32** to reach fix-4's comfortable 78-company target
(46 → 78). Since corpus-fix-5's Job 2 targets +30 raw candidates before any
price-coverage filtering, and this run's sweep shows ~90% of an
unscreened batch of ordinary large/mid-caps clear the gate cleanly (69 of
77 here, and the 8 failures are concentrated in the already-known-fragile
S4/S1-bug/S5-carve-out buckets), 30 raw candidates should clear 54 with
room, **provided none of them land in a similarly fragile bucket** — i.e.
Job 2 should run this same A8 gate against its own candidates before
freezing them in, not after.

**Does anything else block commissioning the scoring run?** Yes, two
things, both already named: (1) §3's bookkeeping defects should be
resolved before any freeze, since scoring against a manifest with 2
mislabeled and 1 stale-but-fixable entry would silently under-count real
S1/S5 members; (2) the expansion itself, now confirmed required rather
than optional.

## 9. Verification performed

- `python3 -c "import ast; ast.parse(...)"` on both new drivers — passed.
- `json.load()` on every new/modified JSON file — valid.
- Cross-checked `STEP_C_AT_CORRECTED_COUNT.json`'s n=54 row against fix-4's
  registered `STEP_C_INDEPENDENT_THRESHOLD.json` figures — exact match
  (2/2/2 paired), confirming the recheck driver reproduces the registered
  method faithfully.
- Re-grepped `analysis/data/price_cache.json` to confirm it has no new
  entries (diff against the pre-run copy is empty).
- Cross-checked HON/UPS/GOOGL against `selection_working.json` and
  `TICKER_ALIASES.json` before concluding they were bookkeeping issues
  rather than genuine coverage failures.

## 10. Limitations (stated, not argued past)

- Coverage is measured against yfinance/Yahoo and the existing frozen
  cache — the providers reachable from this environment. NOVA and WOLF's
  pre-2025 gaps might exist at a paid provider; **if so, that is a
  purchasing decision, not a permanent exclusion** (repeating fix-5's
  finding, now formalized as a gate failure rather than a data note).
- The 12-call gate threshold is inherited from A1's ordinary-company rule,
  not independently derived for price coverage — and as §2/§4 show, it is
  a poor fit for the S4 failures bucket specifically (A2 already gives S4
  its own, lower call-count floor of 4 for exactly this reason; A8 does
  not carry that exception forward, which is why FRC and SUNW fail here
  despite having perfect price coverage for every call they have).
- The corpus remains selected, not scored — no return was computed or
  looked at anywhere in this run.
- The n=46/53/54 MDE comparison is three single-draw Monte Carlo estimates
  at different seeds, not a smooth trend — treat the ranking between them
  as noise, not signal (§6).

## 11. Git

1. `git_dirty: false` confirmed before any change.
2. `analysis/corpus_fix6_driver.py` committed first, alone (`2b1ab9b`).
3. `analysis/corpus_fix6_threshold_recheck.py` committed next, alone
   (`09bfa5e`) — still driver code, before its own results existed.
4. Results committed together (`a831da3`): the A8 addendum, the coverage
   sweep, the new `corpus_v2_price_cache.json` entries, and the threshold
   recheck output.
5. This wrap-up commits next; push follows once, to
   `origin sweep/db-corpus-baseline`.

No `PROMOTION_GATE.md` §10 edit this run (§7). No `CORPUS_MANIFEST_V4.json`
written (§7).

Provenance for every figure above: `<value>` — `<path>` → `<json.key>`,
e.g. `46 available` — `analysis/data/corpus_v2/COVERAGE_GATE_SWEEP.json` →
`per_company.<ticker>.verdict` (count of `pass` among the 53 train+tune
tickers in `SPLIT_V3_RMO_REMOVED.json`); `1pp at n=46 observed` —
`analysis/data/corpus_v2/STEP_C_AT_CORRECTED_COUNT.json` →
`spread_brackets.observed.results_by_n.46.paired_mde_pp`.
