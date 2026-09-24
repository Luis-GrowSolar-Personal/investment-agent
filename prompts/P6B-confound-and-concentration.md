# P6B — close the two gaps: same-model comparator, and leave-one-ticker-out

**Run ID:** `p6b-confound-and-concentration`
**Branch:** `sweep/db-corpus-baseline`
**Wrap-up:** `wrap-ups/P6B-confound-and-concentration-out.md`
**Cost: about $8.** One scoring pass — unmodified v6 on `claude-sonnet-4-6`
over the 195 ALL16 events (95 of which the noise arm already scored; reuse
those, score the other ~100). Everything else is simulator-only, $0.
**Hard cap $12.**

**Why this run exists.** The end-to-end check
(`wrap-ups/P6B-end-to-end-check-out.md`) found B3 $26,571 above A0 with a
7-point better daily drawdown, and named two things it could not show: the
analyst model changed underneath the comparison (R and A0 carry v6 verdicts
archived from the older model; B ran on `claude-sonnet-4-6`), and the gap is
concentrated in four names (NVDA +$21.8k, FSLR +$16.2k, AVGO +$12.0k, MSFT
+$5.9k). The 2026-09-24 state of play §5.1 and §5.2 pre-register the fix for
each. This run is those two items and nothing else.

**Read first:** `docs/handoffs/2026-09-24-state-of-play.md` §2.4, §5;
`wrap-ups/P6B-end-to-end-check-out.md` (all of it — this run extends that
driver); `prompts/P6B-end-to-end-check.md` §1 (the two-corpora rule: the
simulator's cache is `analysis/data/price_cache.json`, and that is correct
here), §4 (the overlay, unchanged); `analysis/p6b_e2e.py` and
`analysis/p6b_overlay.py` (extend; do not fork, do not rewrite).

---

## 1. Ground rules

Everything in `prompts/P6B-end-to-end-check.md` §2 applies. Plus:

1. **The v6 re-score runs under the promoted v6 hash** (`357b6b0b…`), model
   `claude-sonnet-4-6`, pinned. Version guard recorded. The 95 events already
   re-scored by the noise arm (`scores_noise_all16.jsonl`) are reused
   verbatim; score only the remainder, and assert the union covers all 195.
2. **No new overlay logic.** A0′ uses `overlay_a0` exactly as A0 did, with
   the fresh v6 verdict in place of the archived one. B3 is re-used from the
   committed `scores_b_all16.jsonl`; **do not re-score B.**
3. **No new mapping, no new cell types.** The only cells are A0′, and the
   leave-one-out replays of A0, A0′ and B3.
4. **Reproduce before extending.** Re-run R and confirm $184,819 / 23.46%
   daily (±$1 / ±0.02pp) with the extended driver before any new cell.
5. Clean tree; driver commit its own commit before output; `progress.json`
   first; every drawdown names its ruler; provenance for every figure.

---

## 2. Step 1 — A0′: v6 on the same model as B (~$8)

Score the ~100 events not already in `scores_noise_all16.jsonl` with
unmodified v6 on `claude-sonnet-4-6`, same request shape as the noise arm.
Merge into `scores_v6_sonnet46_all16.jsonl` (195 rows; assert). Parse
`per_call_rec`; report parse failures and `max_tokens` stops (the wrap-up
noted one archived event where v6 produced no direction — record how the
fresh scoring handles it).

Run cell **A0′**: fresh v6 verdicts through `overlay_a0` — trend layer
bypassed, `final_confidence = "confident"`, `recommended_size = None` —
settled configuration, seed 0, phases 0/10/20, both rulers.

**Also report, before any simulator result:** the verdict-mix comparison —
archived v6 vs fresh v6 (Add / Hold / Trim / Exit counts), and the
per-event agreement table (archived → fresh). The noise arm saw fresh v6
give fewer Trims (18 vs 26 on 195-event-equivalent) and more Holds; state
whether that holds on all 195. **This is the number that says whether the
model change moved v6 at all.**

### Pre-registered reading (2026-09-24 state of play §5.1)

Compare **B3 to A0′**, both on `claude-sonnet-4-6`, both overlaid.

- **B3 above A0′'s phase range** → the prompt is the cause. The end-to-end
  result stands with the model confound removed.
- **A0′ rises into or above B3's phase range** → the model is the cause. The
  P6 analyst-direct result was also a cross-model comparison (v6 archive on
  the old model vs B on the new) and needs the same correction: report that
  the train/tune v6 baselines should be re-scored on `claude-sonnet-4-6`
  before B is compared to them again. **Do not run that here.**
- **In between** → report both contributions in dollars: (A0′ − A0) is the
  model's share, (B3 − A0′) the prompt's.

**Prediction:** A0′ lands between A0 ($183,780) and B3 ($210,351), closer to
A0 — the half-re-scored noise cell N moved v6 by only $2,265, so a full
re-score should move it by something of that order, not by $26k.

---

## 3. Step 2 — leave-one-ticker-out, $0

For each of the 16 names, drop that ticker's events entirely (it never
enters the universe — no starter, no Adds, no donor role) and re-run **A0,
A0′ and B3** at seed 0, phases 0/10/20. 16 × 3 cells × 3 phases = 144
simulator runs, seconds each.

**Report a 16-row table, NVDA first, then by size of the B3 − A0′ gap:**

| dropped | A0 final | A0′ final | B3 final | B3 − A0′ | B3 − A0′ / A0′ | B3 dd daily | A0′ dd daily |

with the full-universe row on top for reference.

**Note the mechanics before reading the table.** Removing a name changes
every cell, not only the ones that held it: the starter fires one fewer
time, the cash it would have taken is available to other names, and under
`swap_funding` it can no longer be a donor. So "B3 without NVDA" is not "B3
minus NVDA's contribution"; it is a different 15-name portfolio. The gap
column is the comparison that survives that, because A0′ and B3 lose the
same name.

### Pre-registered reading (2026-09-24 state of play §5.2)

- **The B3 − A0′ gap stays positive in all sixteen rows, including without
  NVDA** → the result is not one name. State the smallest gap and which
  drop produced it.
- **The gap flips sign on one drop** → the result is that name; say so in
  one sentence, name it, and report the gap without it as the honest
  figure.
- **The gap flips on several drops** → the result is fragile; report the
  count and do not characterize it further.

Also report, drawdown-side: whether B3's daily drawdown stays better than
A0′'s in every row.

**Prediction:** positive in all sixteen; smallest without NVDA, on the order
of $8k–$14k; drawdown advantage holds throughout because B's Trims on
speculatives (35 of 45) are spread across many small names, not one.

---

## 4. Diagnostics, all $0

- The A0 → A0′ decision-stream diff (`PROMOTION_GATE.md` §2.3 form): first
  divergence and count matched. How much of the trade list does the model
  change alone rewrite?
- Ending value by stock for A0′ beside the existing R / A0 / B3 / B2 table.
- For the four carrying names: the archived vs fresh v6 verdict on each of
  their events, side by side with B's score. If the fresh v6 says Add on
  NVDA where the archive said Hold, that is where the model's share of the
  gap lives.

---

## 5. Report step

**Scope boundary: report, do not decide.** No promotion, no registry
change, no mapping change, no trend-layer change.

`wrap-ups/P6B-confound-and-concentration-out.md`, three forms. **§0 defined
terms** as in the end-to-end wrap-up plus: A0′, leave-one-out, model share /
prompt share.

Open the body with this sentence, filled in:

> Re-scored on the same model as B, v6 through the overlay (A0′) ends at
> $___ (phase range $___–$___, daily drawdown ___%), against A0's $183,780
> and B3's $210,351. Of B3's $26,571 advantage over A0, $___ is the model
> and $___ is the prompt. Dropping each of the 16 names in turn, B3's gap
> over A0′ [stays positive in all 16 / flips on ___]; without NVDA it is
> $___.

Then the two pre-registered readings, each resolved in one sentence. Then
the verdict-mix and agreement tables. Then the 16-row table. Then the
diagnostics.

**Close with what it means for the promotion decision (§5.3 of the state of
play), stated both ways:** if the prompt's share is most of the gap and the
leave-one-out holds, the evidence for promoting `P6B-minimal` as the analyst
signal is closed on this corpus and the remaining work is P6D (fields); if
the model's share is most of it, promotion waits on re-baselining v6 on
`claude-sonnet-4-6` across train and tune, and the state of play's §2 table
carries a correction.

Plain-language discipline is binding.

---

## 6. Standing rules

`python3`, zsh, macOS Tahoe. No cache refresh. `sweep/db-corpus-baseline`.
Commit `scores_v6_sonnet46_all16.jsonl` and every cell manifest as they
land. Budget stop: Step 2 can run on A0 and B3 alone if Step 1's scoring
fails, and must say so; Step 1 cannot be partial.
