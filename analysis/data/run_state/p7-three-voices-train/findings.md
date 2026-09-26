# findings (append-only)
- Pre-flight (150 calls, preflight_report.json): direction disagreement with B draw 1 = 31/150 = 20.7% (draw 2: 19.3%); stop threshold 20% -> NOT stopped, but only by 0.7 point. 0 parse failures, 0 max_tokens, 0 bad gap/pressure. Projected full cost $33.50 (<$40). Median completion 1,039 tokens (B ~517).
- gap: claims_ahead 126 (84%), aligned 16 (11%), numbers_ahead 8 (5%) -- predictions were 30-45 / 35-50 / 10-25: DID NOT HOLD (claims_ahead far above). pressure: avoided 130 (87%), answered 20 (13%), none 0; prediction answered 40-60%: DID NOT HOLD. Diagnostics, not gates. numbers_ahead cell is 8 calls on pre-flight.
- Premise flag: candidate draft replaced B's objective sentence; restored per Luis before registration (sha 0a34f5a9).
