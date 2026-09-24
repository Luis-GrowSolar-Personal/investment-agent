# findings (append-only) - p6b-tune-confirmation

- PRE-REGISTERED INTERPRETATIONS, written before any tune result exists (the prompt leaves these open; they are fixed here and not revisited):
  1. Condition 1 holds iff the lower end of B's 95% ticker-block range on the score-vs-tradeable-return Spearman is > 0 (2,000 draws, seed 11).
  2. Condition 2 holds iff (B bearish count at score <= -2) >= 1.5 x (v6 bearish count) on the same gradable calls AND B bearish precision >= v6 bearish precision - 5 points (old-ruler truth: underperformed the S&P by >5 points, arm-A entry).
  3. Condition 3 holds iff the lower end of the ticker-block 95% range on swap = median(return | score >= +3) minus median(return | score <= -2) is > 0.
  4. Condition 4 (non-gating, a finding if it fails): the prompt's "not below v6's gap by more than the noise band" is read as: B's luck-corrected gap at the +3 mapping >= +0.21, the lower end of v6's own reported tune range (0.21 to 5.00). Ambiguity flagged; if it were read as half-width of that range, the bar would be +0.25, which changes nothing unless B lands between them.
  5. "Same calls" for the coverage/precision comparison = gradable tune calls (a 182-day return exists), WOLF/SPWR excluded entirely.
  6. Predictions carried from the prompt: rank correlation 0.08-0.16; bearish coverage 1.7-2.2x v6 and precision within +-5 of v6; swap median at +3 6-12 with range clear of zero.
- PREMISE FLAGS: (a) 84 bearish / 59.5% for v6 on tune is documented in wrap-ups/q2-bearish-strength-separation-out.md (s5b, line 137-138), NOT in baseline-v6-tune-batch-out.md, which carries 28.3% / +2.64 / 1,168 gradable only. (b) Tune has 54 companies but 51 gradable; WOLF and SPWR are the two named exclusions, one further company has no gradable calls (see 0f).
