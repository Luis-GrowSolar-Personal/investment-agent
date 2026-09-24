# P6B end-to-end check — does the minimal prompt's score translate to portfolio dollars?

**Run ID:** `p6b-end-to-end-check`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P6B-end-to-end-check-out.md`
**Cost: THIS RUN SPENDS A LITTLE REAL MONEY — about $5.** The ALL16 simulator
corpus is roughly 150–200 in-window transcripts; at B's measured $0.0236 per
call that is under $5. Plus a 100-call pure-noise arm on the same corpus
(~$4). **Hard cap $15.** Everything after scoring is simulator-only, $0.

**Why this run exists.** `PROMOTION_GATE.md` §4: an analyst change is gated
on the analyst-direct metric (done — B held on tune, 2026-09-24 state of
play §2) **and checked for no-regress on the end-to-end portfolio metric.**
That second check has never been run on any candidate. The 2026-09-23 state
of play §6 calls it "the measurement never done on the thing this project
keeps trying to improve." This is it.

**Read first, in this order:** `docs/handoffs/2026-09-24-state-of-play.md`
§0, §2, §5 (the pre-registered reading is there and is repeated in §6
below); `docs/handoffs/2026-09-05-state-of-play.md` §0, §2, §5.1, §5.6 (the
reference result, the two rulers, and why every drawdown names its ruler);
`analysis/sweep_cadence_and_session_model.py` (the settled-configuration
harness — `load_events_dedup_on`, `recompute_trend_layer`,
`eligible_for_cash`; read them, do not rewrite them);
`analysis/resolve_open_four.py` (`daily_nav_path`, `check_A` — the daily
ruler reconstruction, reuse it); `analysis/simulator/data.py::load_call_events`;
`analysis/p6_output_format_driver.py` (B's request shape and batch
machinery, reuse by import).

---

## 1. Two corpora, two price caches — get this right before anything else

This project has two separate worlds and they must not be mixed:

| | analyst-direct corpus | **simulator corpus (this run)** |
|---|---|---|
| companies | 164 (corpus_v2), train/tune/holdout | **ALL16** (`VERSION_REGISTRY.json` → `ticker_universe.canonical`) |
| events | ~2,400 calls | **in-window ALL16 events as `load_events_dedup_on()` returns them** (expect ~150–195; SPWR has 1, AMPX 6) |
| window | 2020–2025 | **2022-01-01 → 2024-06-12** (constant `C` in the harness) |
| transcript source | `analysis/data/corpus_v2/transcripts/` | **the DB `Transcript.rawText` for exactly those events** (fetch by transcript id; `analysis/dump_transcripts.py` shows the query). `analysis/data/transcripts/*.txt` has 147 of them on disk and may be used as a cross-check, not as the source. |
| price cache | `corpus_v2/scorer_price_cache_v1.json` — **NOT this run** | **`analysis/data/price_cache.json`** — the simulator's own cache, the one every settled-configuration result was computed on |

Every prior P6 prompt said "never `analysis/data/price_cache.json`." **That
rule was for corpus_v2 scoring. Here it is the correct and only cache**, and
`fundamentals_cache.json` beside it feeds the tier classifier. **Do not
refresh either** (10b standing protection #2). Record both sha256s in the
manifest.

---

## 2. Ground rules

1. **Version guard:** B's scoring calls under `PROMPT_CANDIDATE=P6B-minimal`
   (registered); noise arm against the promoted v6 hash. Pinned model
   `claude-sonnet-4-6`. Both assertions recorded.
2. **No DB writes.** The Analysis table is the archive of a retired model;
   B's scores go to a file, never to the DB. `SELECT` only.
3. **Do not modify** the harness, the allocator, `data.py`, the trend layer,
   the classifiers, or the scorer. The overlay in §4 is a new module that
   *feeds* the harness.
4. **Reproduce the reference before running any cell.** If §3's hard stop
   fails, nothing else in this run means anything.
5. **Every drawdown names its ruler.** Session-sampled and daily-marked are
   both reported; the daily ruler is the one compared. An unlabelled
   drawdown is not a number.
6. **Thresholds are the pre-registered ones** (2026-09-24 state of play §0):
   score ≤ −2 → Trim, ≥ +3 → Add, else Hold; the +2 bullish cut is the one
   sensitivity cell. **No other mapping is run.** If you want to see another
   mapping, that is a finding for the wrap-up, not a cell.
7. macOS Tahoe, zsh, `python3`. No `--break-system-packages`. Clean tree,
   driver committed as its own commit, `progress.json` first.

---

## 3. Step 0 — reproduce the reference (hard stop)

Run the settled configuration exactly as `resolve_open_four.py check_A`
does — `swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp, `pooled`,
`per_event_date`, seed 0, phases 0/10/20, events from
`load_events_dedup_on()` — and assert:

- phase-averaged final value **$184,819** (±$1);
- phase-averaged max drawdown **17.32% session-sampled** and **23.46%
  daily-marked** (±0.02pp);
- per-phase finals $179,945 / $189,914 / $184,599.

Provenance: `docs/handoffs/2026-09-05-state-of-play.md` §5.1 table, and
`analysis/data/run_state/resolve-open-four/cells.jsonl` (cite the exact
cell and key you matched). **Mismatch → stop and report.** Record the event
count and the sha256 of the event list (ticker, call_date, transcript id).

---

## 4. The overlay — how B's score enters a harness built for v6

The harness consumes, per event: `per_call_rec`, `final_action`,
`final_confidence`, `recommended_size`, `trajectory`, plus `type`, `tier`
and `driver_count` from the classifiers (analyst-independent). B emits a
score and nothing else. **The overlay is written down here so it cannot be
improvised:**

| harness field | B cell value | why |
|---|---|---|
| `per_call_rec` | mapping of `score` (rule 6) | the analyst's call |
| `final_action` | **= `per_call_rec`** | the trend layer needs `thesis_health`, `credibility_delta`, `mitigation_track_record`, `fresh_money_allocation`, none of which B emits. **The trend layer is bypassed**, not simulated. |
| `final_confidence` | `"confident"` | §4 eligibility requires not `unknown`; B has no confidence field. (The 2026-09-05 document notes this field is a coarse filter that most v6 events resolve to `confident` anyway.) |
| `recommended_size` | `None` | `BACKTEST_SIMULATOR.md`'s documented fallback: target = tier cap. Test 4 follow-ons found this field inert at X=2.5pp in any case. |
| `trajectory` | `None` | no trend layer |
| `type`, `tier`, `driver_count` | **unchanged** — from `type_classifications.json` and the 3-axis classifier | analyst-independent by design |
| starter, caps, profit-take, ratchet mechanics | **unchanged** | allocator rules |

Implement as `analysis/p6b_overlay.py`: take the event list from
`load_events_dedup_on()`, look up B's score by `(ticker, call_date)`, and
return a **copy** of the events with the fields above replaced. Events with
no B score (a transcript that failed to score) are **dropped from that cell
and counted**; more than 3% missing → stop and report.

**One control cell exists so the trend-layer bypass is not confounded with
the prompt.** See A0 in §5.

---

## 5. Cells — pre-registered, in this order

| cell | events | what it isolates |
|---|---|---|
| **R** | v6 as-is (reference) | reproduction, §3 |
| **A0** | v6 `per_call_rec` only: `final_action = per_call_rec`, `final_confidence = "confident"`, `recommended_size = None`, `trajectory = None` — **v6 fed through B's overlay** | the cost of the trend-layer bypass and the size fallback, on v6's own calls. **This is the fair comparator for B**, not R. |
| **B3** | B score, mapping ≤ −2 Trim / ≥ +3 Add / else Hold | the candidate |
| **B2** | B score, bullish cut at +2 | the one sensitivity |
| **N** | 100 events re-scored with unmodified v6, overlaid like A0 | the noise arm: how much R–A0 and A0–B3 move when v6 is merely re-rolled |

All cells: seed 0, phases 0/10/20, phase-averaged, both rulers. Also run
seeds 1 and 2 on B3 and A0 only, to confirm the draw spread is still ~0 at
X=2.5pp (2026-09-05 §5.3); if it is not, report the spread and use it as
the band in §6.

**Required diagnostics per cell** (all already emitted by the harness):
final value; max drawdown both rulers; per-ticker ending weights (the
`quarterly_composition` shape); Add / Trim / Exit / Hold counts; number of
sessions where cash bound; **deployment rate** — days to first full
deployment and average cash %; the `funding_log` and `target_cap_log`
paths; realized turnover. For B3 vs A0 additionally: the **decision-stream
diff** in the `PROMOTION_GATE.md` §2.3 form — `(session date, ticker, side,
shares)` — first divergence and count matched before it.

---

## 6. Pre-registered reading — copied from the 2026-09-24 state of play §5

**The band.** Rule 2 (`ALLOCATOR_OPERATING_MODEL.md` §10) uses overlapping
ranges across draws; at X=2.5pp the draw spread is ~0, so the band is the
**phase spread**: R's per-phase finals run $179,945–$189,914 (a $9,969
spread) and daily drawdowns 22.78–24.20%.

- **Pass (no-regress):** B3's phase-averaged final value is within A0's
  phase range **and** its daily-marked drawdown is not worse than A0's by
  more than A0's own phase spread. B is then cleared on the end-to-end
  check, and promotion becomes a design question (P6D).
- **Above:** B3 exceeds A0's phase range on final value with drawdown not
  worse → a finding worth its own document; **do not promote on it here**
  (one cell, one window, one seed family).
- **Below:** B3 falls below A0's phase range by more than the spread → the
  score does not translate to sizing under this allocator. Report *why* from
  the diagnostics: is it deployment rate (fewer Adds at the +3 cut), Add
  precision on the names that carry the portfolio (AVGO/NVDA/ORCL/TTD, ~73%
  of the book), or the trend-layer bypass (compare A0 to R — if A0 is
  already far below R, the bypass is the cost, not B).

**Predictions, written so they can be wrong.**

1. A0 lands below R: the trend layer's four ENPH-style Hold→Trim flips and
   the `final_confidence` gate were doing some work. Predicted gap $5k–$20k.
2. B3 lands **at or above A0** on final value. B's bearish calls are more
   numerous at equal precision, and under swap-funding a Trim on a loser
   funds an Add elsewhere; that is the mechanism the allocator rewards.
3. B3's daily drawdown is **not better** than A0's — Test 1 showed drawdown
   falls only through non-participation, and B3 at the +3 cut deploys
   *slower* (fewer Adds), so the drawdown result is ambiguous and the
   deployment-rate diagnostic is what explains it.
4. B2 (bullish at +2) deploys faster and ends higher than B3 in this rising
   window, with worse drawdown — the 2026-09-05 §5.6 finding that
   deployment rate is what this allocator pays for, reproduced through a
   threshold instead of X.
5. The four names that carry the portfolio (AVGO, NVDA, ORCL, TTD) end at
   similar weights under B3 and A0, because the starter fires regardless of
   score and X throttles the rest; the difference shows up in the
   speculatives, where B's extra Trims land.

**A diagnostic that contradicts a prediction is a finding, not a reason to
stop.**

---

## 7. Report step

**Scope boundary: report, do not decide.** Do not promote, do not edit the
registry's `promoted_version`, do not touch the trend layer, do not add a
mapping cell.

`wrap-ups/P6B-end-to-end-check-out.md`, three forms. **§0 defined terms**:
the six configuration settings with `X`'s worked example (a 5% position may
end the month between 2.5% and 7.5%), the two rulers, phase-averaged,
overlay, trend-layer bypass, the mapping, no-regress, deployment rate.
Restate the settled configuration in plain English before any identifier.

Open the body with this sentence, filled in:

> On the ALL16 window the settled configuration ends at $___ with v6 (R),
> $___ with v6 stripped to its per-call verdicts (A0), and $___ with the
> minimal prompt's score at the pre-registered mapping (B3); daily-marked
> drawdowns ___% / ___% / ___%. B3 is [inside / above / below] A0's phase
> range of $___–$___. On the pre-registered reading, B [passes / exceeds /
> fails] the end-to-end check.

Then each prediction in §6, held or not, one sentence each. Then the
diagnostics, B3 vs A0 first. Then the decision-stream diff. Then N, so the
reader can see how much of any R–A0–B3 movement is v6 re-rolling itself.

**Close with what it means, three ways** per §6, and name the design
question the result leaves: which v6 fields the allocator and trend layer
actually need (P6D), and whether the trend layer's contribution (R minus A0)
is worth carrying into a B-based analyst or is already inside B's score.

Plain-language discipline is binding: anchor every percentage, "points"
never "pp" in prose, lead with the finding, one idea per sentence.

---

## 8. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Provenance for every figure — manifest path and key. One prompt in, one
wrap-up out. Commit B's ALL16 scores (`scores_b_all16.jsonl`) and every cell
manifest as they land. Budget stop: the noise arm N may be dropped; the
seed-1/2 confirmation may be dropped; **R, A0 and B3 cannot be partial**.
