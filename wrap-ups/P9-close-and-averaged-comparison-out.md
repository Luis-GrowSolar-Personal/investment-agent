# P9 close-out, and averaged B vs averaged P9. Wrap-up

**Run ID:** `p9-close-and-averaged`. Branch `sweep/db-corpus-baseline`. **Cost $0** (no API calls, DB writes or scoring). **Complete run.**
**Scope boundary: report, do not decide.** No tune pre-registration, no scoring, no champion change.

> Averaged over two draws per call, the minimal prompt ranked at **0.121** and the expected-return prompt at **0.140**, a paired difference of **+0.020** (range **−0.030 to +0.069**). Under the reading fixed before the run, averaged P9 is **worth a tune test — equal ranking, plus severity**, **by a margin of 0.0002** (see the flag below). Inside the bearish group, averaged P9 ranked outcomes at **0.222** (range **0.067 to 0.345**) against averaged B's **0.141** (range **−0.014 to 0.286**). Step 1's bookkeeping landed in commit **`e7c356a`**.

Source: `analysis/data/run_state/p9-close-and-averaged/results.json` (script `analysis/p9_averaged_comparison.py`, committed before any output). All averages are per call over the same 1,217 calls (asserted); ties by the seeded rule (seed 11); ranges are 95% ticker-block bootstrap, 2,000 draws, seed 11.

## The reading, applied as fixed

Rule: worth a tune test if the paired difference (averaged P9 minus averaged B) has its range's lower end no worse than −0.03; then say whether the range excludes zero. Result: lower end **−0.0298** (≥ −0.03, `paired_avgP9_minus_avgB.lower_end_ge_-0.03: true`); range **includes zero**, so **"equal ranking, plus severity"**, not "better ranking too". `reading` key.

**The one thing to know about this reading (diagnostic, not a condition):** the lower end clears the threshold by **0.0002**. Recomputing the same range with four other bootstrap seeds (`seed_sensitivity.json`) gives lower ends **−0.0335, −0.0286, −0.0322, −0.0308** (seeds 1, 2, 3, 4), so three of four alternates fall below −0.03. The pre-registered rule, at its fixed seed, says go; the margin is smaller than the bootstrap's own noise. I did not add a condition and the reading stands as written; I report the sensitivity because the design session should weigh it.

## Averaged numbers side by side (`avg_B`, `avg_P9`)

| figure | averaged B | averaged P9 |
|---|---|---|
| distinct values | 18 | 55 |
| **rank correlation** | **0.121** (0.043 to 0.194) | **0.140** (0.055 to 0.223) |
| **paired, avg P9 minus avg B** | | **+0.020 (−0.030 to +0.069)** |
| bottom 191 right | 61.3% (54.2–67.9), median −10.08 | 62.8% (55.8–69.4), median −10.75 |
| top 235 right | 38.3% (32.3–44.7), median +0.69 | 37.9% (31.9–44.2), median −1.36 |
| severity: rank correlation inside bottom 191 | 0.141 (−0.014 to 0.286); 7 distinct scores in the group | **0.222 (0.067 to 0.345)**; 20 distinct values |
| realized median by fifth, lowest to highest | −7.88, −5.32, −1.81, −0.81, −0.65 | −9.06, −5.32, +0.04, −1.90, +0.19 |
| slope of realized (clipped ±50) on the averaged number | 1.36, **not comparable in units** (per score point) | **0.629** (0.268 to 0.959), points per point |
| averaging's help: averaged ranking minus the mean of its two single-draw rankings | **+0.006** | **−0.001** |

Severity, read as the pre-registered condition: averaged P9's within-bottom-191 range excludes zero and its lowest fifth (−9.06) is below the second (−5.32). Averaged B's within-bottom-191 range includes zero; its lowest fifth is also below its second. Neither set of middle fifths is monotone.

## Single-draw figures beside them (from earlier wrap-ups)

| | B draw 1 | B draw 2 | P9 draw 1 | P9 draw 2 |
|---|---|---|---|---|
| rank correlation (`single_draw_rho`) | 0.130 | 0.099 | 0.171 | 0.111 |
| bottom 191 right | 62.3% | 61.3% | 62.8% | 61.8% |
| top 235 right | 39.6% | 36.2% | 40.4% | 35.3% |
| within-bottom-191 rank correlation | 0.081 | 0.145 | 0.257 | 0.184 |

Averaging did almost nothing for ranking: it moved each prompt to about the middle of its two single draws (B +0.006, P9 −0.001 from the mean). What it did was remove the outlier draws: averaged P9's 0.140 is between P9's 0.171 and 0.111, not above either. The extra resolution (55 distinct values against 18) is what averaging buys for severity, not for ranking.

## What this cannot show

The noise of an *averaged* draw cannot be measured without a third and fourth draw of each prompt; the averaged figures carry **no run-to-run band of their own**. All four draws were already scored and already seen, so this is not a fresh test. The reading justifies only a pre-registered tune test. It cannot re-open P9's verdict (falsified on train) and cannot promote anything.

## Step 1 — files changed (commit `e7c356a`)
- `docs/architecture/VERSION_REGISTRY.json`: P9-expected-return `status` → `falsified`, `falsified: "2026-09-26"`, `detail` (both gate-2 figures), `finding` (severity holds on both draws); sha kept. `python3 analysis/whats_live.py` exits 0 (prints v6 as the promoted evaluation prompt; nothing about candidates).
- `analysis/data/gate_ledger.json`: entry 4 (P9 vs B). 2×3 gate table with values, ranges and held/failed per B draw for each P9 draw; `final_verdict: FALSIFIED`; `final_reason`; `findings_of_record` (severity on two draws; P9's noise floor 17.0%, 0.060, half-width 0.037); `cost_usd` 60.31 (30.17 + 30.14). Sources cited per figure.
- `docs/architecture/PROMPT_ARCHITECTURE.md`: §2.2 P9 row → falsified; a five-line dated **Result** paragraph under the P9 block (verdict, severity "confirmed on two draws", higher wobble as cause, pointer to this wrap-up).

## Deviations and notes
1. **Git bookends (CLAUDE.md rule 9):** I verified the `CLAUDE.md` diff was only rule 9 (9 added lines, nothing else), then committed the prompt (`prompt: P9 close-out and averaged comparison`) and `CLAUDE.md` (`CLAUDE.md: git bookends rule for CLI prompts`) as separate commits before the clean-tree check. `progress.json` was written first. The tree was clean apart from this run's own state directory, which was committed with the analysis script.
2. **Seed-sensitivity check** was my addition, labelled diagnostic-only, so ground rule 3 (no added conditions) is respected: the reading is computed at the pre-registered seed and unchanged.
3. Averaged-B slope uses clipped realized return regressed on the half-point averaged score; labelled not comparable in units.
4. The "6 checks" bookkeeping used the prior wrap-up's counting; no gate was re-computed.

## What this means

**Worth a tune test, on the letter of the rule; but it is a close call and would rest on the same four draws that were already seen.** Equal ranking (range includes zero), with P9 adding a within-bearish severity signal that B's tied scores cannot produce. If it goes forward, the next prompt pre-registers "P9, scored twice and averaged" against "B, scored twice and averaged" on tune: one more B draw and two P9 draws on tune, about $85, P9's one look. The pre-registration should fix in advance how to treat a lower end that sits within bootstrap noise of the tolerance, since this reading does. If instead it is closed: B stays champion, and severity stays an open gap, recorded as something P9's wording can do but not steadily enough. Whichever it is, that is Luis's decision.

## Not done
No tune pre-registration, no scoring, no champion or gate changes, no DB writes, no cache refresh.

```bash
python3 analysis/p9_averaged_comparison.py
```
