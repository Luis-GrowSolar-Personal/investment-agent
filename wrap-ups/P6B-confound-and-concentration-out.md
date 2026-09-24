# P6B, close the two gaps: same-model comparator and leave-one-ticker-out. Wrap-up

**Run ID:** `p6b-confound-and-concentration`. Branch `sweep/db-corpus-baseline`. **Complete run, not partial:** both steps ran in full (v6 re-score of all 195 events, A0′, and all 144 leave-one-out runs).
**Real spend: $3.56** (95 new v6 re-scores; the other 100 were reused verbatim from the noise arm) against the $12 cap. Everything after scoring is simulator-only, $0.
**Reading version (renders correctly anywhere, phone included):** https://claude.ai/artifact/Wu64THHHVgxNQsfUHxz5zD
**Scope boundary: report, do not decide.** Nothing is promoted; the registry, the mapping and the trend layer are untouched.

---

## §0. Defined terms

**In plain English first.** The end-to-end check found that the minimal prompt's score (B3) made the portfolio $26,570 richer than v6's verdicts (A0), with a smaller drawdown. It could not say two things. First, the v6 verdicts came from an older analyst model, while B ran on the newer `claude-sonnet-4-6`, so the gap might be the model, not the prompt. Second, most of the gap sat on four stocks, so it might be one lucky name. This run tests each: it re-scores v6 on the same new model as B, and it drops each of the 16 stocks in turn.

Everything from the end-to-end wrap-up carries over unchanged: the settled configuration (`swap_funding`, `K`=30, `new_calls_only`, `X`=2.5pp, `pooled`, `per_event_date`: trade once a month, put money only into names that just reported, fund buys by trimming a holding, and never move one position by more than 2.5 points of portfolio in a session; **`X` is a per-position, per-session speed limit, so a 5% position may end the month anywhere between 2.5% and 7.5%**), the two drawdown rulers (session-sampled and daily-marked; **every drawdown here names its ruler and the daily one is compared**), phase-averaged (the mean of the three 30-day schedules starting on day 0, 10 and 20), the overlay, the trend-layer bypass, and the pre-registered mapping (score ≤ −2 Trim, ≥ +3 Add, else Hold).

New terms:

- **A0′ ("A0 prime").** Unmodified v6, re-scored on `claude-sonnet-4-6` for all 195 events, then fed through the same overlay A0 uses (trend layer bypassed, `final_confidence = "confident"`, `recommended_size = None`). It is the true comparator for B3: same model, same overlay, only the prompt differs.
- **Model share / prompt share.** Of B3's advantage over A0, the model share is A0′ minus A0 (what changing the model alone did to v6) and the prompt share is B3 minus A0′ (what changing the prompt did once the model is the same).
- **Leave-one-out.** Drop one stock's events entirely (it never enters the universe: no starter buy, no Adds, no role as a donor for swap funding), then re-run A0, A0′ and B3. It is a different 15-stock portfolio, not "B3 minus that stock's contribution"; the **gap column (B3 − A0′)** survives that because both cells lose the same stock.

**Corpus.** The same 195 events across 16 stocks up to 2024-06-12, event-list sha256 `724bba09…85dd`. Prices `analysis/data/price_cache.json` (the simulator's own frozen cache).

---

## Headline

> Re-scored on the same model as B, v6 through the overlay (A0′) ends at **$200,214** (phase range **$194,407 to $206,925**, daily drawdown **20.12%**), against A0's **$183,780** and B3's **$210,351**. Of B3's **$26,570** advantage over A0, **$16,433** is the model and **$10,137** is the prompt. Dropping each of the 16 names in turn, B3's gap over A0′ **flips on 1 (FSLR)**; without NVDA it is **$2,366**.

**Plain reading.** Moving v6 to the newer model, with no change to its prompt, lifted the portfolio by $16,433, more than the prompt change (the last $10,137). The model changed almost none of the four carrying names' verdicts (54 of 56 identical), so its effect comes through the other names and the funding paths. On the prompt's own share, the pre-registered range test says "B3 is above A0′" (its worst phase clears A0′'s best by only $569), but that $10,137 (5.1% of A0′) is thin: it disappears if FSLR is removed and shrinks to $2,366 if NVDA is. B3's smaller daily drawdown holds in all 16 drops.

*Rounding note:* the end-to-end wrap-up quoted the B3 − A0 gap as $26,571 (from rounded cell values). From the unrounded phase-averaged finals it is $26,570.20. This report uses $26,570 and it supersedes the $26,571.

---

## Step 0. R reproduces, bit-exactly, with the extended driver

Phase-averaged final **$184,819.42** (reference $184,819 ±$1), daily-marked drawdown **23.458%** (reference 23.46% ±0.02), session-sampled **17.324%** (17.32%); per-phase finals equal `analysis/data/run_state/resolve-open-four/cells.jsonl` keys `1a-phase0`, `1a-phase10`, `1a-phase20` → `results.final` to 1e-6 (`repro.json`, `manifest_repro.json`). The full-universe A0 and B3 cells re-run in this run equal the end-to-end run's values exactly (difference $0.00 and 1e-14 points).

## Step 1. A0′: the model comparison

### Verdict mix first, before any simulator result (all 195 events)

| verdict | archived v6 (older model) | fresh v6 (`claude-sonnet-4-6`) |
|---|---|---|
| Add | 136 | 105 |
| Hold | 33 | 75 |
| Trim | 26 | 15 |
| Exit | 0 | 0 |

**Answer to the question the prompt flagged:** the model change did move v6. Trims fell from 26 to 15 and Holds rose from 33 to 75, and the direction seen in the noise arm holds across all 195 (on the noise arm's 100 events: archived Add 65 / Hold 17 / Trim 18, fresh 54 / 36 / 10; on the 95 new events: archived 71 / 16 / 8, fresh 51 / 39 / 5). The prompt's "18 vs 26" pair compared mixed cells and is superseded by this table.

**Per-event agreement (archived → fresh):**

| archived → fresh | events |
|---|---|
| Add → Add | 102 |
| Add → Hold | 34 |
| Hold → Hold | 29 |
| Hold → Add | 3 |
| Trim → Trim | 14 |
| Trim → Hold | 12 |
| Hold → Trim | 1 |

The two verdicts agree on **145 of 195 events (74.4%)**. Nearly every change is a step toward Hold (46 events: 34 Add→Hold plus 12 Trim→Hold). Only 4 events move the other way (3 Hold→Add, 1 Hold→Trim), and no event flips from Add to Trim or the reverse. Parse: 195 of 195 fresh outputs parsed, none lacked a direction, none stopped at `max_tokens` (`merge_v6_report.json`).

### Results (phase-averaged, seed 0)

| cell | final value | phase finals (0 / 10 / 20) | phase spread | drawdown, session-sampled | drawdown, **daily-marked** |
|---|---|---|---|---|---|
| A0: archived v6 through the overlay | $183,780 | 183,091 / 192,981 / 175,269 | $17,712 | 17.26% | **23.91%** |
| **A0′: fresh v6 (same model as B) through the overlay** | **$200,214** | 194,407 / 206,925 / 199,309 | $12,519 | 13.29% | **20.12%** |
| B3: B's score at the pre-registered mapping | $210,351 | 214,227 / 209,330 / 207,495 | $6,733 | 11.26% | **16.97%** |

Daily-marked drawdown by phase: A0′ 19.91% / 20.05% / 20.39%; B3 17.54% / 16.82% / 16.56%.

**Model share $16,433** (A0′ − A0, 62% of the gap). **Prompt share $10,137** (B3 − A0′, 38%). Total $26,570.

### The pre-registered reading (2026-09-24 state of play §5.1), resolved in one sentence

**B3 is above A0′'s phase range, so on the pre-registered rule the prompt is the cause**; the margin is narrow (B3's lowest phase, $207,495, is $569 above A0′'s highest, $206,925; B3's average is $3,426 above A0′'s best phase). **The prediction did not hold:** A0′ landed between A0 and B3 as predicted, but closer to B3 than to A0 (the model moved v6 by $16,433, not "something of the order of" the noise cell's $2,265).

*Superseding note on that noise cell.* N replaced only 100 of 195 verdicts and its dollar movement (+$2,265) understated the full re-score's (+$16,433). N's small movement is not a bound on the model effect.

## Step 2. Leave-one-ticker-out

144 simulator runs (16 names × A0, A0′, B3 × 3 phases), seed 0. Ordered as asked: the full-universe reference on top, NVDA first, then the rest by size of the B3 − A0′ gap, smallest first (so the fragile rows read first).

| dropped | A0 final | A0′ final | B3 final | B3 − A0′ | B3 − A0′ as % of A0′ | B3 dd, daily | A0′ dd, daily |
|---|---|---|---|---|---|---|---|
| **none (full universe)** | $183,780 | $200,214 | $210,351 | $10,137 | 5.1% | 16.97% | 20.12% |
| NVDA | $148,521 | $162,201 | $164,566 | $2,366 | 1.5% | 15.67% | 20.37% |
| FSLR | $180,432 | $191,264 | $188,984 | **−$2,279** | −1.2% | 15.08% | 19.08% |
| ORCL | $181,962 | $201,562 | $204,696 | $3,134 | 1.6% | 14.80% | 19.66% |
| RUN | $189,121 | $203,519 | $212,387 | $8,868 | 4.4% | 16.21% | 19.02% |
| ENVX | $183,677 | $202,703 | $211,659 | $8,956 | 4.4% | 16.61% | 19.29% |
| TSLA | $189,437 | $202,051 | $211,630 | $9,579 | 4.7% | 16.74% | 19.54% |
| GOOGL | $181,923 | $201,688 | $211,384 | $9,696 | 4.8% | 16.79% | 20.20% |
| EOSE | $185,780 | $203,201 | $213,193 | $9,992 | 4.9% | 16.79% | 20.05% |
| AVGO | $166,478 | $187,077 | $197,254 | $10,177 | 5.4% | 16.51% | 21.27% |
| AMPX | $189,694 | $202,412 | $212,613 | $10,201 | 5.0% | 16.10% | 19.29% |
| AAPL | $181,802 | $200,819 | $211,270 | $10,451 | 5.2% | 16.77% | 20.09% |
| QS | $186,475 | $202,125 | $212,629 | $10,503 | 5.2% | 16.74% | 19.96% |
| SPWR | $183,780 | $199,775 | $210,688 | $10,913 | 5.5% | 16.97% | 20.12% |
| MSFT | $180,307 | $201,082 | $212,031 | $10,950 | 5.4% | 16.31% | 20.37% |
| AMD | $182,958 | $201,612 | $215,890 | $14,278 | 7.1% | 16.60% | 19.86% |
| TTD | $181,133 | $199,905 | $214,648 | $14,743 | 7.4% | 15.34% | 18.85% |

### The pre-registered reading (§5.2), resolved in one sentence

**The B3 − A0′ gap flips sign on exactly one drop, FSLR: the prompt's share of the result is FSLR, and the honest figure without it is −$2,279** (B3 $188,984 against A0′ $191,264). Without NVDA the gap is still positive but only $2,366 (1.5% of A0′), against $10,137 with every name.

**Drawdown side: B3's daily drawdown is better than A0′'s in all 16 rows** (B3 14.80% to 16.97%, A0′ 18.85% to 21.27%; no row where it is worse). B3's lowest phase clears A0′'s highest in only 10 of the 16 rows.

**Predictions:** positive in all sixteen **did not hold** (15 of 16); smallest without NVDA at $8k to $14k **did not hold** (the smallest positive gap is NVDA's at $2,366, and FSLR's is negative); the drawdown advantage holding throughout **held**.

**Reading the table with the mechanics in mind.** The table's A0 and A0′ columns fall sharply when NVDA (−$35k and −$38k) or AVGO (−$17k and −$13k) is removed: these two names carry every cell. That is why the gap, not the level, is the comparison. FSLR is the opposite case: dropping it lowers A0′ by $8,950 and B3 by $21,367. B3 held $23,520 of FSLR at the end against A0′'s $12,546 and A0's $7,326.

---

## Diagnostics

### Decision-stream diff, A0 → A0′ (`PROMOTION_GATE.md` §2.3 form; the model change alone)

| phase | A0 trades | A0′ trades | first divergence | matched before it | first A0 trade there | first A0′ trade there | rows appearing in both streams |
|---|---|---|---|---|---|---|---|
| 0 | 188 | 177 | index 14 | 14 | 2022-05-01 sell FSLR | 2022-05-01 buy MSFT | 23 |
| 10 | 195 | 197 | index 14 | 14 | 2022-05-11 sell FSLR | 2022-05-11 sell EOSE | 21 |
| 20 | 177 | 163 | index 15 | 15 | 2022-05-21 sell FSLR | 2022-05-21 sell EOSE | 21 |

The first 14 trades are the starter buys, one per stock. The two streams diverge at the first session after them. **Only 11% to 13% of A0's trade rows appear in A0′: the model change alone rewrites about 87% to 89% of the trade list**, from a verdict set that agrees on 74% of events. Small changes in which names are trimmed or held early change every later share count.

### Ending value by stock, A0′ beside R / A0 / B3 / B2 (phase-averaged, seed 0, dollars)

| stock | R | A0 | **A0′** | B3 | B2 |
|---|---|---|---|---|---|
| NVDA | 43,508 | 38,275 | 48,821 | 60,116 | 70,135 |
| AVGO | 38,627 | 39,167 | 45,747 | 51,154 | 46,299 |
| ORCL | 29,023 | 34,102 | 28,259 | 20,227 | 35,451 |
| TTD | 23,436 | 23,343 | 27,163 | 18,126 | 30,076 |
| FSLR | 5,358 | 7,326 | 12,546 | 23,520 | 34,429 |
| MSFT | 11,637 | 10,197 | 10,978 | 16,117 | 6,086 |
| AMD | 16,378 | 15,401 | 17,049 | 13,310 | 8,663 |
| GOOGL | 7,701 | 9,233 | 3,860 | 5,286 | 6,036 |
| all other (AAPL, AMPX, ENVX, EOSE, QS, RUN, SPWR, TSLA) | 9,153 | 6,739 | 5,791 | 2,493 | 5,238 |

A0′ versus A0: NVDA +$10,546, AVGO +$6,580, FSLR +$5,220, TTD +$3,820, SPWR +$3,247, against ORCL −$5,843 and GOOGL −$5,373. **The model's share is spread across the same names that carry the portfolio** and is not concentrated in one.

### The four carrying names: archived v6 against fresh v6 against B (56 events)

On AVGO (13 events), NVDA (14), ORCL (16) and TTD (13), archived and fresh v6 give the **same verdict on 54 of 56 events** (53 Add→Add, 1 Hold→Hold). The two that differ are **NVDA 2022-08-24 (archived Trim, fresh Hold)** and ORCL 2023-03-09 (archived Add, fresh Hold). B3 said Hold on the NVDA event too (score 2). So the model's $16,433 share **does not come from the carrying names' verdicts, with two exceptions, of which NVDA 2022-08-24 is the larger.** A0 trims NVDA there and A0′ does not; NVDA ends $10.5k higher in A0′. This run did not isolate that one event, so it is the visible candidate for NVDA's share, not a measured one.

Where B3 differs from fresh v6 on the carrying names, it is mostly by being stricter: B3 says Hold where fresh v6 says Add on 15 events (8 ORCL, 4 TTD, 2 AVGO, 1 NVDA on 2022-05-25), and Add where fresh v6 says Hold on 2 (NVDA 2022-11-16, ORCL 2023-03-09). Those Holds hold cash back, which is part of where B3's slower deployment comes from.

---

## What this does not show

1. **B3's edge over A0′ ($10,137, 5.1%) is one window, three phases of one seed, and it rests on FSLR.** Without FSLR it reverses. This run does not say whether B's FSLR verdicts were insight or luck: the pre-registered reading says "the result is that name", nothing more.
2. **Hindsight exposure is unchanged.** Both models were trained after the whole window, and fresh v6 on `claude-sonnet-4-6` now shares B's exposure, which is why A0′ is the fair comparator, and also why A0′'s $16,433 rise over A0 may partly be recall the older model lacked. This run cannot separate that from "the newer model reads calls better".
3. **The trend layer stays bypassed** in A0, A0′ and B3, so R minus A0 (+$1,039) remains the whole measured trend-layer effect.
4. **Seed 0 only**, as pre-registered (the draw spread at X = 2.5pp is zero).

## What this means for the promotion decision (state of play §5.3), both ways

- **If the prompt's share is most of the gap and leave-one-out holds** (evidence for promoting `P6B-minimal` closed on this corpus): **not the case.** The prompt's share is 38% of the gap, and leave-one-out does not hold (it flips on FSLR).
- **If the model's share is most of it** (promotion waits on re-baselining v6 on `claude-sonnet-4-6`): **this is the branch the dollars sit on** (62% model, 38% prompt), even though the range test formally credits the prompt. The 2026-09-24 state of play's §2.4 table carries a correction for this: its A0 row is a cross-model comparator, and its "B3 beat v6 by $26,600" is $26,570 = $16,433 model + $10,137 prompt.
- **The correction does not reach the analyst-direct evidence.** The P6, tune and pooled v6 baselines were scored with `claude-sonnet-4-6` (`analysis/data/evals/v6_claude-sonnet-4-6/` and `…_tune/`), the same model as B. **The prompt's branch text ("the P6 analyst-direct result was also a cross-model comparison") is wrong**, so the re-baselining it prescribes for train and tune is already done. The confound exists only on the ALL16 simulator corpus, whose v6 verdicts come from the archived DB analyses.

**Design questions this leaves (not decided here):** whether the portfolio-side comparator should be A0′ from now on (the archived A0 cannot serve as one); whether the FSLR result deserves its own look (B held $23,520 of it at the end against A0′'s $12,546); and P6D, which v6 fields the allocator needs, still open.

---

## Premise flags, deviations, what was not done

**Premise flags (recorded in `findings.md` at the start):**
1. The prompt says 95 events were already re-scored by the noise arm and about 100 remain. **It is the other way round**: 100 were reused verbatim and 95 were scored. Cost $3.56, not about $8.
2. The "18 vs 26" Trim comparison was mixed cells (superseded above).
3. The "archived event with no direction" was an ETN/ACN call in the tune or train split, not an ALL16 event; all 195 ALL16 verdicts parse.
4. **The branch text in §2's reading 2 misstates the analyst-direct baselines' model** (see above).
5. State-of-play §5.1 to §5.3 exist only in the user's uncommitted rewrite of `docs/handoffs/2026-09-24-state-of-play.md`; the committed copy still says "the end-to-end check, ~$16".

**Deviations:**
- **Working-tree hygiene.** The tree carried the user's uncommitted edits to `docs/handoffs/2026-09-24-state-of-play.{md,docx}`. Per the standing rule they were copied aside, stashed for the run so the clean-tree gate could be satisfied, and restored at the end. They are in no commit of this run.
- **A0 and B3 were re-run** (full universe) in this run's state directory, at the final driver commit, and equal the end-to-end values exactly.
- The leave-one-out cells store only aggregate results per run (no funding logs), to keep the repository small; full logs are kept for the full-universe cells.
- Leave-one-out row order: NVDA first, then smallest gap first (the prompt did not say ascending or descending).

**Not done:** no promotion, no registry change, no mapping cell, no trend-layer change, no re-scoring of B, no re-baselining of train/tune (already on the same model), no DB writes (read-only connection), no cache refresh.

## Provenance and artifacts

Driver `analysis/p6b_e2e.py --run confound` (extended in its own commit before any output; the driver commit is in `progress.json`), overlay `analysis/p6b_overlay.py` (unchanged). State in `analysis/data/run_state/p6b-confound-and-concentration/`: `progress.json`, `findings.md`, `repro.json`, `manifest_repro.json`, `scores_v6_sonnet46_all16.jsonl` (195 rows: 100 `noise_arm_reused_verbatim`, 95 `this_run`), `scores_v6_sonnet46_new_rows.jsonl`, `merge_v6_report.json`, `cells.jsonl` (12 full-universe runs plus 144 leave-one-out runs, each with `config_hash`, `driver_commit`, `overlay_sha256`), `logs/`, `summary.json`. Every dollar and drawdown figure is `cells.jsonl` → `results.final` and `results.dd_daily` / `results.dd_session`, phase-averaged. Guard: promoted v6 hash `357b6b0b…` recorded in `progress.json` → `guards`.

```bash
python3 analysis/p6b_e2e.py --run confound repro
python3 analysis/p6b_e2e.py --run confound full
python3 analysis/p6b_e2e.py --run confound loo
python3 analysis/p6b_e2e.py --run confound summary-confound
```
