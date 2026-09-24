# findings (append-only)

- 0g: flip-count correction to PROMPT_ARCHITECTURE.md 2.4/2.5 has not landed (last commit aee70da is the P6 registration). File not edited; this run reports every flip count raw and net per section 7 regardless.

- PREMISE FLAGS at Step 0 (see progress.json notes): (1) prompt's "1,194 transcripts" is the unresolved count; resolved = 1,240 and that is what the asserts check. (2) stratum_map() is S1-S5 corpus strata, not four-way cap tiers; the four-way split exists only as a hardcoded 15-ticker list (P3 5f) - 21a drawn proportional to S1-S5 per P3 5f, and every "per stratum" figure in this run is S1-S5. (3) v6 train reference 30.3%/+2.48 lives in scorer-price-cache-backfill-out.md, not baseline-v6-train-batch-out.md (22.8%/-1.64, pre-backfill). (4) Prompt's registered date 2026-09-24 vs today 2026-09-23.
- 0f: PARA carries 23 resolved train calls; P6 universe = 1,217 calls / 55 companies / 1,162 predecessor-bearing.
- Netting rule (verbatim from prompts/P3-guidance-ledger.md section 7, copied before scoring):

  > **Noise corrupts counting what changed; it does not corrupt measuring whether the answers got better.** The accuracy figure and the gap over luck are unbiased by run-to-run instability **provided a noise flip wins half the time** - 21a measures that per tier, and **that check is what licenses this claim.** If the cached v6 draw is systematically luckier than a fresh one, the headline carries a bias of `noise flips x (2*w_noise - 1) / N`.
  >
  > Every flip count is reported **raw, and net of 21a's measured rate**, with the per-stratum breakdown reported alongside and used to net a stratum separately where its range excludes the overall figure (P3 5f). Section 2.4's ceiling applies to the net count.
  >
  > **Win rate among flips is netted too:** real-flip win rate = (observed wins - noise flips x noise win rate) / (observed flips - noise flips), with both taken from 21a - overall, or per stratum where 5f says a stratum needs netting separately.
  >
  > **Guard.** Report the netted win rate only when `observed flips - noise flips` exceeds **100** *and* exceeds the upper end of the noise count's own range (~227). Below that, report the raw win rate, the noise win rate, and the netted point estimate marked "unstable, denominator too small" - never as the headline.
  >
  > **Caveat:** noise flips and real flips are not disjoint - a call can be one the ledger moved and one resampling would have moved. The subtraction assumes independence and no overlap; the net count is an estimate with a known simplification.
  >
  > Applies to counts only. The rank-ordering test (6.1) is not a flip count and is not netted (P6 prompt section 7).

- Q2 axis prediction, written BEFORE any arm-C result is read (discovery only, no gate): within arm C's bearish bucket (score <= -2), the more negative half of scores has HIGHER bearish precision than the less negative half, by at least 5 points; and the within-bucket Spearman of score vs tradeable return is positive (more negative score, lower return). A result the other way, or inside noise, is a finding, not a failure.
- Analysis script (p6_output_format_analysis.py) committed before any scores exist. Definitions fixed in it: flip = A-vs-arm direction difference on shared calls; flip "win" = the arm's direction matches the old-ruler truth (so the arm was right and A wrong); noise win rate = fresh v6 call right among graded 21a flips; netting subtracts sum over S1-S5 of (21a stratum rate x stratum call count); tier column is "NA" (no per-company established/speculative field exists for the train companies - type_classifications.json covers 32 other tickers).
