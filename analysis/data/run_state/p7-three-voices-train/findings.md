# findings (append-only)
- Pre-flight (150 calls, preflight_report.json): direction disagreement with B draw 1 = 31/150 = 20.7% (draw 2: 19.3%); stop threshold 20% -> NOT stopped, but only by 0.7 point. 0 parse failures, 0 max_tokens, 0 bad gap/pressure. Projected full cost $33.50 (<$40). Median completion 1,039 tokens (B ~517).
- gap: claims_ahead 126 (84%), aligned 16 (11%), numbers_ahead 8 (5%) -- predictions were 30-45 / 35-50 / 10-25: DID NOT HOLD (claims_ahead far above). pressure: avoided 130 (87%), answered 20 (13%), none 0; prediction answered 40-60%: DID NOT HOLD. Diagnostics, not gates. numbers_ahead cell is 8 calls on pre-flight.
- Premise flag: candidate draft replaced B's objective sentence; restored per Luis before registration (sha 0a34f5a9).
- Full round (results.json): P7 top-235 hit 31.5% (25.9-37.7), median return -2.46; B draws 39.6% / 36.2%. Gate 1 (>= 47.0%) FAILED, 15.5 points under target, below both B draws. Falsified per pre-registration.
- Gate 2: paired rho diff P7 minus B draw1 -0.017 (-0.050 to +0.016), lower end < -0.03 -> fails vs draw 1; vs draw 2 +0.014 (-0.017 to +0.046) holds. Gate 3: bottom-191 hit 58.6% >= 57.0 holds. 1 of 3 gates held against both draws.
- P7 rank correlation 0.113 (0.033-0.189); prediction 0.12-0.17 missed by 0.007.
- Neutral-to-top-235 group (B draw1 neutral, P7 top 235): 83 calls, 22.9% hit vs 33.2% base, median -3.95: the mirror is B's top 235 that P7 dropped: 83 calls, 45.8% hit, median +3.77. P7 swapped good bullish calls for worse ones.
- gap shares: claims_ahead 78.8, aligned 14.1, numbers_ahead 7.1 (pred 30-45/35-50/10-25: missed). pressure: answered 20.0, avoided 79.7 (pred answered 40-60: missed). numbers_ahead + answered: 55 calls, 25.5% bullish hit (below base): prediction missed.
- Cost $0.0280/call vs B $0.0236: +19% (within predicted 10-25%). Total real spend $34.07.
