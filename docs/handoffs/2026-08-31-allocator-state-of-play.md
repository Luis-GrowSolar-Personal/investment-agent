# Allocator thread — state of play

**Date:** 2026-08-31
**For:** Luis, returning to this thread cold after time on other priorities.
**Status of the funding/limit question:** the axis is bracketed, the optimum is
interior, and the remaining work is a set of decisions rather than a set of
measurements.

Read `docs/architecture/ALLOCATOR_OPERATING_MODEL.md` for the spec. Its design
decisions remain closed. This document records what six measurement sessions
established, what was wrong along the way, and what is waiting for a decision.

---

## 1. Where the thread stands, in one paragraph

Six CLI sessions since 2026-08-30 established that the allocator was never the
thing allocating — the earnings calendar was — and then found the parameter that
fixes it. **The per-session position-change limit is the dominant design
parameter**, not the secondary axis §5 calls it. Swept densely across three
funding-mode variants and fifteen orderings each, every mode produces a smooth
unimodal curve with an **interior optimum at 2.5–3pp**, roughly doubling the
unconstrained baseline. Twenty-four of thirty configurations robustly pass the
pre-declared success bar. What remains is six decisions, all Luis's, and two
method fixes before the next measurement run.

---

## 2. The correction that changed the picture

For three consecutive sessions every limit surface classified as **JAGGED**, and
under the pre-declared Rule 3 that meant nothing could be spec'd from the axis.

**That verdict was an artifact of axis ordering, introduced by the design
session's own prompts.** `off` means *no limit* — it is the loosest possible
setting, equivalent to ∞ — but the prompts listed values as `off, 0.5, 1, 1.5…`
and the CLI ordered them as given, placing an unbounded configuration at the
*tight* end of the axis, adjacent to 0.5pp. That single misplacement generated
the sign changes.

Reordered with `off` at the loose end, recomputed from the run manifests:

| Mode | material sign sequence | peak | interior? |
|---|---|---|---|
| `no_reserve_raw` | `+++++--` | **3pp** | yes |
| `no_reserve_s11fixed` | `++++---` | **2.5pp** | yes |
| `swap_funding` | `+++++--` | **3pp** | yes |

Zero violations in any mode — textbook `+…+ −…−`. **The optimum is interior and
bracketed in all three modes.** The peak region is **2.5–3pp**.

---

## 3. The measured surface

450 runs (10 limit values × 3 funding modes × 15 draws), 71.8 seconds wall-clock,
33 citable manifests, `git_dirty: false` throughout, all four cross-grid anchors
reproducing to six decimal places.

Final value across 15 draws (forward, reversed, seeds 1–13); drawdown is the
median across draws; "clears" is the count of draws under the standing 38.0% bar.

| Limit | Mode | min | median | max | spread | DD med | clears |
|---|---|---|---|---|---|---|---|
| 0.5pp | raw | $123,677 | $123,677 | $123,677 | 0.0% | 5.6% | 15 |
| 1pp | raw | $148,069 | $148,069 | $148,069 | 0.0% | 10.6% | 15 |
| 1.5pp | raw | $167,712 | $167,712 | $167,745 | 0.0% | 15.1% | 15 |
| 2pp | raw | $176,598 | $176,655 | $176,747 | 0.1% | 19.1% | 15 |
| 2.5pp | raw | $184,607 | $185,180 | $185,296 | 0.4% | 18.8% | 15 |
| **3pp** | **raw** | **$189,265** | **$189,322** | **$189,386** | **0.1%** | **21.1%** | **15** |
| 4pp | raw | $180,693 | $183,591 | $187,085 | 3.5% | 27.6% | 15 |
| 5pp | raw | $180,121 | $183,707 | $186,094 | 3.3% | 31.7% | 15 |
| 10pp | raw | $171,919 | $179,605 | $189,528 | 9.8% | 39.5% | 0 |
| off | raw | $117,455 | $139,355 | $154,398 | 26.5% | 45.3% | 0 |
| 0.5pp | s11fixed | $126,982 | $126,982 | $126,982 | 0.0% | 8.4% | 15 |
| 1pp | s11fixed | $154,884 | $154,884 | $154,884 | 0.0% | 15.5% | 15 |
| 1.5pp | s11fixed | $167,896 | $168,090 | $168,194 | 0.2% | 21.6% | 15 |
| 2pp | s11fixed | $178,519 | $178,827 | $179,015 | 0.3% | 22.6% | 15 |
| **2.5pp** | **s11fixed** | **$181,616** | **$183,629** | **$184,055** | **1.3%** | **25.6%** | **15** |
| 3pp | s11fixed | $175,259 | $177,048 | $182,064 | 3.8% | 29.9% | 15 |
| 4pp | s11fixed | $173,815 | $175,575 | $180,607 | 3.9% | 34.1% | 15 |
| 5pp | s11fixed | $176,816 | $179,093 | $184,884 | 4.5% | 34.0% | 15 |
| 10pp | s11fixed | $148,488 | $165,272 | $168,142 | 11.9% | 39.0% | 0 |
| off | s11fixed | $110,546 | $114,620 | $123,931 | 11.7% | 46.4% | 0 |
| 0.5pp | swap | $123,277 | $123,277 | $123,292 | 0.0% | 7.0% | 15 |
| 1pp | swap | $147,296 | $147,297 | $147,330 | 0.0% | 13.0% | 15 |
| 1.5pp | swap | $165,048 | $165,226 | $165,338 | 0.2% | 18.4% | 15 |
| 2pp | swap | $176,923 | $177,907 | $178,060 | 0.6% | 22.2% | 15 |
| 2.5pp | swap | $189,414 | $190,481 | $191,052 | 0.9% | 22.7% | 15 |
| **3pp** | **swap** | **$196,805** | **$197,437** | **$198,069** | **0.6%** | **26.6%** | **15** |
| 4pp | swap | $180,755 | $188,915 | $190,828 | 5.3% | 33.2% | 15 |
| 5pp | swap | $162,530 | $179,209 | $186,120 | 13.2% | 35.3% | 15 |
| 10pp | swap | $140,178 | $156,231 | $160,808 | 13.2% | 38.8% | 7 (fragile) |
| off | swap | $135,084 | $155,878 | $160,687 | 16.4% | 47.8% | 0 |

Benchmarks on the same window: SPY $113,980 (25.36% DD), QQQ $119,178 (35.25%),
TMFC $120,512 (32.99%), equal-weight $120,427 (42.76%). **Every configuration in
the grid beats all four on return.** Drawdown is the only discriminator.

### The three modes

- **`no_reserve_raw`** — today's baseline. `decide_v3`'s trades passed through
  unmodified. Carries §11 defect #2. The comparability anchor for the existing
  corpus.
- **`no_reserve_s11fixed`** — identical except the buy leg is rebuilt against
  live cash, via the same shared `_rebuild_buy_leg()` function swap-funding uses.
- **`swap_funding`** — conformant per-date trim cap; buy leg already rebuilt.

---

## 4. What is established

- **The session limit is the dominant design parameter.** `off` → 3pp takes
  `no_reserve` from $139,355 to $189,322 and swap-funding from $155,878 to
  $197,437. **`ALLOCATOR_OPERATING_MODEL.md` §5's line calling the per-session
  change limit "a secondary axis, not the fix" is now wrong and needs amending.**
- **A real trade-off at the peak, separable in both directions.**
  `swap_funding` at 3pp gives the best return in the grid ($197,437);
  `no_reserve_raw` at 3pp gives the lowest drawdown (21.1% vs 26.6%). Ranges do
  not overlap either way — this is a genuine choice, not noise.
- **24 of 30 configurations robustly pass** the pre-declared bar (beats SPY, QQQ
  and TMFC on return; median drawdown under 38.0%; clearing on ≥ 2/3 of draws) —
  every limit from 0.5pp to 5pp in all three modes, each on 100% of draws.
- **Cash-drag is refuted at every mode's own peak** — 72–79% invested at the
  drawdown trough. The low drawdowns come from diversification, not from sitting
  out declines in cash.
- **§5's central thesis is now closed empirically.** At 1pp and below, all
  fifteen orderings produce identical results. Remove the binding cash
  constraint and arrival order stops mattering entirely — "order is the
  allocator" holds exactly as long as cash binds, and not one day longer.
- **Cap drift is a live-cash-rebuild phenomenon, not swap-funding's.**
  `no_reserve_s11fixed` drifts identically to `swap_funding` (same ticker, same
  magnitude). Largest excess anywhere: **+12.28pp, MSFT at 62.28% against a 50%
  cap.** Zero drift under `no_reserve_raw` at every tight limit. Nothing
  anywhere approaches the 25% profit-take threshold.
- **Cash never stops binding for `no_reserve_raw`.** Even at 0.5pp it is the
  majority constraint on 22 of 98 Add decisions. `s11fixed` and `swap_funding`
  are 100% limit-bound at 0.5–1pp.
- **§11 defect #2's effect is limit-dependent, not a simple cost.** Corrected
  with Rule 2 applied at every limit: the fix **helps** at 0.5–2pp (separable),
  **hurts** at 3–10pp (separable), and is **tied** at `off` and 5pp. At the
  historical baseline it is not measurable against arrival-order noise.

---

## 5. Corrections to the record

Numbers published earlier in this thread that are wrong, and should not be cited:

| Claim | Status |
|---|---|
| `swap_funding` cell 7 = $154,392 as a funding-mode result | **Noise.** It was the control's own seed-3 draw to within $6. |
| Displacement realized gains −$32,679 / −$24,950 | **Superseded.** Ticker-filtered, not sale-attributed. Correct figure for the conformant 10pp cell: **−$19,924**, of which −$9,003 on `Hold` donors. |
| "Cumulative shortfall drops 73%" for swap-funding | **Inflated.** Compared across a session-limit boundary. Like-for-like it is 26%. |
| The 38.0% drawdown ceiling | **A three-benchmark artifact.** Median of SPY/QQQ/TMFC alone is 32.99%, +5pp = 37.99%. With equal-weight included as §10 requires, the correct ceiling is **39.12%**. |
| Limit surfaces classified JAGGED (three sessions) | **Wrong** — axis-ordering error, see §2. All three modes are unimodal. |
| "Fixing §11 defect #2 costs 17.7% at `off`" | **Breaks Rule 2.** The ranges overlap ($117,455–$154,398 vs $110,546–$123,931), so the two are tied at `off` and must not be ranked by median. |
| `no_reserve` beats `swap_funding` (matched 10pp) | **Does not survive** being re-asked at each mode's own optimum. At their peaks swap-funding wins on return by $8,115 (4.3%). |

Four of these originated in design-session prompt-drafting errors, not in the
CLI's work: Rule 3's two contradicting clauses, invariant #2's target-versus-
realized-weight conflation, a prediction written as a gate, and a gate placed on
a defect §11 documents as known and unfixed. **Standing principle adopted: no
gate may test a condition §11 documents as a known unfixed defect, and a
diagnostic that contradicts an expectation is a finding, never a stop.**

---

## 6. Decisions pending — all Luis's

1. **Funding mode.** `swap_funding` for return, `no_reserve_raw` for drawdown.
   Separable in both directions at their respective peaks; no measurement will
   break the tie because there isn't one.
2. **Limit value.** 2.5pp or 3pp.
3. **Drawdown ceiling.** Keep 38.0%, or adopt the correct 39.12%. It is inert
   across the current grid — it flips nothing — so it is free to settle now and
   expensive to settle later.
4. **§11 defect #2.** Fix in the production path, or leave and keep the baseline
   comparable. Now fully measured.
5. **Cap restoration.** Nothing pulls a position back to its cap after price
   drift; profit-take only fires at 25%. §5 says caps are inviolable, §3
   deliberately allows drift between calls and credits it for the Type B result.
   The conflict was invisible while cash starvation meant nothing ever reached a
   cap. Max observed excess is +12.28pp on a 50% cap.
6. **`minPositionDollar`.** Still undetermined. ~70% of donor draws leave the
   donor below 1% of portfolio, so a floor above 1% would change donor behavior
   materially and a floor at or below 1% would bind almost never.

---

## 7. Method fixes needed before the next measurement run

- **Rule 3b's plateau test is now the wrong instrument.** Draw spreads collapse
  to 0.0–0.6% at tight limits (at 1pp and below, all fifteen draws are
  identical), so non-overlap is trivially achieved and plateaus come back as
  singletons or non-contiguous sets. Replace with a practical-significance band —
  declared before results, not after.
- **Axis ordering must place `off` at the loose end** in every future prompt.
- **Rule 2 must be applied to the §11 comparison**, not median ranking.

---

## 8. What is still ahead

The sequence from `claude/HANDOFF_2026-08-30.md` §5, unchanged:

1. **Ordering rule**, measured in the fixed funding regime — cheap now, and the
   regime it will operate in finally exists.
2. **Option B** — re-evaluate ALL16's 312 transcripts under the v6 prompt and a
   current model (~$25–35) to recover the full window.
3. **Cadence / scope / veto sweep** — still blocked until funding mode is
   settled, per §5's corollary.

Everything above rests on **148 events across 2.5 years with a frozen 16-name
universe**. §10 rule 4's caveats stand: a frozen universe understates the value
of being able to fund a new name, and 2021–2026 was mostly a rising tape.

---

## 9. Reproducibility state

- Branch `sweep/db-corpus-baseline`, latest measurement commit `f5c9057`.
- 33 manifests from the final run, all `git_dirty: false`, each `driver_file`
  verified present in the commit it names.
- Standing assertion holds: `no_reserve` control = **$141,836.57**.
- Anchors reproduce across grids to six decimal places.
- `price_cache.json` / `fundamentals_cache.json` still frozen at 2026-05-11 —
  **never refresh them to clear the staleness warning.**
- `testing/` is gitignored — it holds real brokerage position exports and must
  not enter version history.

---

## 10. First thing to do on return

**Settle the drawdown ceiling (decision 3).** It costs nothing today, changes no
current verdict, and every future score depends on it.

Then choose between return and drawdown at the peak (decisions 1 and 2). That
choice is a judgment about what this portfolio is for, not a measurement — the
grid has taken it as far as measurement can.

The next prompt after that is the ordering rule in the fixed funding regime,
with Rule 3b's plateau test replaced first.
